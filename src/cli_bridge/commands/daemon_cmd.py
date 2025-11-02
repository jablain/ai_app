"""
Daemon management commands for AI-CLI-Bridge.

This module provides CLI commands to start, stop, and check the status of the
self-managing AI daemon. The daemon owns its own lifecycle and browser process
management. The CLI simply manages the daemon process group.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

import requests
import typer

from daemon.config import (
    DAEMON_LOG_FILE,
    EXIT_CDP_CONFLICT_OR_TIMEOUT,
    EXIT_DAEMON_PORT_BUSY,
    EXIT_FLATPAK_MISSING,
    EXIT_GENERIC_FAILURE,
    EXIT_PROFILE_DIR_NOT_WRITABLE,
    EXIT_SUCCESS,
    load_config,
)

from ..constants import (
    API_HEALTH_CHECK_TIMEOUT_S,
    DAEMON_READINESS_DEFAULT_TIMEOUT_S,
    DAEMON_READINESS_POLL_INTERVAL_S,
    DAEMON_READINESS_TIMEOUT_BUFFER_S,
    FORCE_KILL_RETRY_WAIT_S,
    GRACEFUL_SHUTDOWN_TIMEOUT_S,
    SIGTERM_RETRY_INTERVAL_S,
)

# Import error types and constants
from ..errors import (
    DaemonNotRunning,
    DaemonShutdownFailed,
    DaemonStartupFailed,
    InvalidConfiguration,
)

# Create Typer app for daemon subcommands
app = typer.Typer(help="Manage the AI daemon process.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def is_process_alive(pid: int) -> bool:
    """Check if a process with given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def get_daemon_pid_from_api(host: str, port: int) -> int | None:
    """
    Get daemon PID from /status API endpoint.

    Returns:
        Daemon PID if available, None if unreachable or missing.
    """
    try:
        response = requests.get(
            f"http://{host}:{port}/status",
            timeout=API_HEALTH_CHECK_TIMEOUT_S,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("daemon", {}).get("pid")
    except Exception:
        pass
    return None


def check_daemon_health(
    host: str, port: int, timeout: float = API_HEALTH_CHECK_TIMEOUT_S
) -> tuple[bool, str | None]:
    """
    Check daemon health via /health endpoint.

    Returns (is_healthy, error_message).
    """
    try:
        response = requests.get(f"http://{host}:{port}/health", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            if str(data.get("status", "")).lower() == "ok":
                return True, None
            reason = data.get("reason", data.get("message", "unknown"))
            return False, f"Unhealthy: {reason}"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def wait_for_daemon_ready(
    host: str, port: int, timeout_s: float = DAEMON_READINESS_DEFAULT_TIMEOUT_S
) -> bool:
    """
    Poll /health until daemon is ready or timeout.
    Uses exponential backoff for efficiency.

    Returns True if daemon became healthy, False if timeout.
    """
    end_time = time.time() + timeout_s
    delay = 0.1  # Start with 100ms
    last_error = None

    while time.time() < end_time:
        is_healthy, error = check_daemon_health(host, port, timeout=API_HEALTH_CHECK_TIMEOUT_S)
        if is_healthy:
            return True

        last_error = error
        time.sleep(delay)
        delay = min(delay * 2, DAEMON_READINESS_POLL_INTERVAL_S)  # Cap at 0.5s

    if last_error:
        typer.echo(f"  Timeout waiting for daemon (last error: {last_error})")
    return False


def wait_for_process_death(pid: int, timeout_s: float = GRACEFUL_SHUTDOWN_TIMEOUT_S) -> bool:
    """
    Wait for process to die.

    Returns True if process died, False if still alive after timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        if not is_process_alive(pid):
            return True
        time.sleep(SIGTERM_RETRY_INTERVAL_S)
    return False


def explain_exit_code(exit_code: int) -> str:
    """Return human-readable explanation of daemon exit code."""
    explanations = {
        EXIT_SUCCESS: "Success",
        EXIT_GENERIC_FAILURE: "Generic failure",
        EXIT_PROFILE_DIR_NOT_WRITABLE: "Profile directory not writable",
        EXIT_DAEMON_PORT_BUSY: "Daemon port already in use",
        EXIT_FLATPAK_MISSING: "Flatpak or ungoogled-chromium not installed",
        EXIT_CDP_CONFLICT_OR_TIMEOUT: "CDP port conflict or timeout",
    }
    return explanations.get(exit_code, f"Unknown exit code {exit_code}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("start")
def start_daemon(
    wait: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="Wait for daemon to become ready (default: --wait)",
    ),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        min=1.0,
        help="Seconds to wait for readiness (default: config + 5s)",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show daemon logs during startup"),
):
    """
    Start the AI daemon in the background.

    The daemon will:
    - Spawn CDP browser with all AI tabs
    - Start health monitoring
    - Listen on configured port (default: 8000)

    Use --no-wait to return immediately after spawning.
    Use --verbose to see startup logs.
    """
    # Load config
    try:
        config = load_config()
        host = config.daemon.host
        port = config.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load config: {e}", fg=typer.colors.RED)
        raise typer.Exit(InvalidConfiguration.exit_code)

    # Check if already running
    healthy, _ = check_daemon_health(host, port, timeout=API_HEALTH_CHECK_TIMEOUT_S)
    if healthy:
        pid = get_daemon_pid_from_api(host, port)
        if pid:
            typer.secho(f"✓ Daemon already running (PID: {pid})", fg=typer.colors.GREEN)
        else:
            typer.secho("✓ Daemon already running", fg=typer.colors.GREEN)
        typer.echo(f"  API: http://{host}:{port}")
        typer.echo(f"  Logs: {DAEMON_LOG_FILE}")
        raise typer.Exit(EXIT_SUCCESS)

    # Spawn daemon
    typer.echo("Starting daemon...")

    try:
        stdout = None if verbose else subprocess.DEVNULL
        stderr = None if verbose else subprocess.DEVNULL

        process = subprocess.Popen(
            [sys.executable, "-m", "daemon.main"],
            start_new_session=True,
            stdout=stdout,
            stderr=stderr,
            env=os.environ.copy(),
        )

        spawn_pid = process.pid
        typer.echo(f"  Spawned process (PID: {spawn_pid})")

        if not verbose:
            typer.echo(f"  Logs: {DAEMON_LOG_FILE}")

        # Wait for readiness if requested
        if wait:
            typer.echo("  Waiting for daemon to become ready...")

            # Safe config access
            start_cdp = getattr(getattr(config, "cdp", object()), "start_timeout_s", 10.0)
            ready_timeout = timeout or max(
                DAEMON_READINESS_DEFAULT_TIMEOUT_S,
                float(start_cdp) + DAEMON_READINESS_TIMEOUT_BUFFER_S,
            )

            if wait_for_daemon_ready(host, port, timeout_s=ready_timeout):
                # Get actual daemon PID from API (may differ from spawn PID in edge cases)
                pid = get_daemon_pid_from_api(host, port) or spawn_pid
                typer.secho(f"✓ Daemon ready (PID: {pid})", fg=typer.colors.GREEN)
                typer.echo(f"  API: http://{host}:{port}")
            else:
                # Check if process crashed
                exit_code = process.poll()
                if exit_code is not None:
                    typer.secho(
                        f"✗ Daemon crashed during startup (exit code: {exit_code})",
                        fg=typer.colors.RED,
                    )
                    typer.echo(f"  {explain_exit_code(exit_code)}")
                else:
                    typer.secho("✗ Daemon did not become ready in time", fg=typer.colors.RED)
                    typer.echo("  The daemon process may still be initializing")

                typer.echo(f"  Check logs: {DAEMON_LOG_FILE}")
                if not verbose:
                    typer.echo("  Tip: re-run with --verbose")
                raise typer.Exit(DaemonStartupFailed.exit_code)
        else:
            typer.echo("  Daemon starting in background")
            typer.echo("  Use 'aicli daemon status' to check readiness")

    except FileNotFoundError:
        typer.secho("✗ Could not find Python or daemon module", fg=typer.colors.RED)
        typer.echo("  Ensure the package is installed or PYTHONPATH is set")
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    except Exception as e:
        typer.secho(f"✗ Failed to start daemon: {e}", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)

    raise typer.Exit(EXIT_SUCCESS)


@app.command("stop")
def stop_daemon(
    force: bool = typer.Option(False, "--force", help="Force kill if graceful shutdown fails"),
):
    """
    Stop the running AI daemon.

    Sends SIGTERM to the daemon process group for graceful shutdown.
    The daemon will clean up all child processes (browser, helpers, etc).

    Use --force to send SIGKILL if graceful shutdown times out.
    """
    # Load config
    try:
        config = load_config()
        host = config.daemon.host
        port = config.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load config: {e}", fg=typer.colors.RED)
        raise typer.Exit(InvalidConfiguration.exit_code)

    # Get daemon PID from API
    pid = get_daemon_pid_from_api(host, port)
    if not pid:
        typer.secho("✗ Daemon not running", fg=typer.colors.YELLOW)
        raise typer.Exit(DaemonNotRunning.exit_code)

    # Send SIGTERM to process group
    typer.echo(f"Stopping daemon (PID: {pid})…")
    try:
        # We ONLY kill the daemon pid and trust it to clean up its own children.
        # Killing the process group (os.killpg) races with the daemon's
        # own shutdown handler, causing a SIGKILL and the "Restore" popup.
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        typer.secho("✓ Daemon already stopped", fg=typer.colors.GREEN)
        raise typer.Exit(EXIT_SUCCESS)
    except PermissionError:
        typer.secho(f"✗ Permission denied (cannot kill PID {pid})", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    except Exception as e:
        # This will catch other errors, but we still want to log the attempt
        typer.echo(f"  Encountered error ({e}), proceeding to wait...")
        pass

    typer.echo("  Sent SIGTERM, waiting for graceful shutdown…")

    # Wait for process to die
    if wait_for_process_death(pid, timeout_s=GRACEFUL_SHUTDOWN_TIMEOUT_S):
        typer.secho("✓ Daemon stopped gracefully", fg=typer.colors.GREEN)
        raise typer.Exit(EXIT_SUCCESS)

    # Timeout - process still alive
    typer.secho("⚠ Daemon did not stop gracefully", fg=typer.colors.YELLOW)

    if force:
        typer.echo("  Sending SIGKILL (force)…")
        try:
            # Only kill the daemon pid. The OS will reap the children.
            os.kill(pid, signal.SIGKILL)
            time.sleep(FORCE_KILL_RETRY_WAIT_S)

            if is_process_alive(pid):
                typer.secho("✗ Failed to kill daemon", fg=typer.colors.RED)
                raise typer.Exit(DaemonShutdownFailed.exit_code)
            else:
                typer.secho("✓ Daemon killed (forced)", fg=typer.colors.GREEN)
                raise typer.Exit(EXIT_SUCCESS)
        except Exception as e:
            typer.secho(f"✗ Failed to force kill: {e}", fg=typer.colors.RED)
            raise typer.Exit(EXIT_GENERIC_FAILURE)
    else:
        typer.echo("  Daemon still running. Use --force to send SIGKILL")
        raise typer.Exit(DaemonShutdownFailed.exit_code)


@app.command("status")
def daemon_status(
    json_output: bool = typer.Option(False, "--json", help="Output status as JSON"),
):
    """
    Check the health of the AI daemon process.

    Shows daemon process status only (running, PID, health).
    For detailed AI instance status, use 'aicli status'.

    Exit codes:
      0 = Daemon running and healthy
      1 = Daemon not running
    """
    # Load config
    try:
        config = load_config()
        host = config.daemon.host
        port = config.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load config: {e}", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)

    # Check health
    is_healthy, error = check_daemon_health(host, port, timeout=API_HEALTH_CHECK_TIMEOUT_S)

    if not is_healthy:
        if json_output:
            envelope = {
                "ok": False,
                "code": 1,
                "message": error or "Daemon not running",
                "data": {"running": False, "pid": None, "api_url": f"http://{host}:{port}"},
            }
            typer.echo(json.dumps(envelope, indent=2))
        else:
            typer.secho("Daemon status: 🛑 Not Running", fg=typer.colors.RED)
            if error:
                typer.echo(f"  Error: {error}")
            typer.echo("  Start with: aicli daemon start")
        raise typer.Exit(DaemonNotRunning.exit_code)

    # Healthy: Get PID
    pid = get_daemon_pid_from_api(host, port)

    if json_output:
        envelope = {
            "ok": True,
            "code": 0,
            "message": "Daemon running and healthy",
            "data": {"running": True, "pid": pid, "api_url": f"http://{host}:{port}"},
        }
        typer.echo(json.dumps(envelope, indent=2))
    else:
        typer.secho(f"Daemon status: ✅ Running (PID: {pid or 'unknown'})", fg=typer.colors.GREEN)
        typer.secho("  Health: ✅ OK", fg=typer.colors.GREEN)
        typer.echo(f"  API: http://{host}:{port}")
        typer.echo("")
        typer.echo("  (Use 'aicli status' for AI instance details)")

    raise typer.Exit(EXIT_SUCCESS)


# ---------------------------------------------------------------------------
# Standalone Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
