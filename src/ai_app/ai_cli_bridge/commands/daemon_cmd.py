"""
Daemon management commands for AI-CLI-Bridge.

This module provides CLI commands to start, stop, and check the status of the
self-managing AI daemon. The daemon now owns its own lifecycle, PID files, and
browser process management.

Commands:
- start: Spawn the daemon process and optionally wait for readiness
- stop: Send SIGTERM to daemon and wait for graceful shutdown
- status: Check if daemon is running and healthy
"""

from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
from typing import Optional

import typer

# Early check for requests dependency
try:
    import requests
except ImportError:
    print("✗ The 'requests' package is required.\n  Install: pip install requests", file=sys.stderr)
    sys.exit(1)

from daemon.config import (
    load_config,
    PID_FILE,
    DAEMON_LOG_FILE,
    EXIT_SUCCESS,
    EXIT_GENERIC_FAILURE,
    EXIT_PID_LOCK_HELD,
    EXIT_PROFILE_DIR_NOT_WRITABLE,
    EXIT_DAEMON_PORT_BUSY,
    EXIT_FLATPAK_MISSING,
    EXIT_CDP_CONFLICT_OR_TIMEOUT,
)

# Create Typer app for daemon subcommands
app = typer.Typer(
    help="Manage the AI daemon process.",
    no_args_is_help=True
)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def get_daemon_pid() -> Optional[int]:
    """
    Read daemon PID from PID file.
    
    Returns None if file doesn't exist or PID is invalid.
    """
    if not PID_FILE.exists():
        return None
    
    try:
        pid_str = PID_FILE.read_text().strip()
        return int(pid_str)
    except (ValueError, IOError):
        return None


def is_process_alive(pid: int) -> bool:
    """
    Check if a process with given PID is alive.
    
    Uses os.kill(pid, 0) which doesn't actually send a signal,
    just checks if the process exists.
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't own it
        return True


def check_daemon_health(host: str, port: int, timeout: float = 1.0) -> tuple[bool, Optional[str]]:
    """
    Check daemon health via /healthz endpoint.
    
    Returns (is_healthy, error_message).
    """
    try:
        response = requests.get(
            f"http://{host}:{port}/healthz",
            timeout=timeout
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return True, None
            else:
                reason = data.get("reason", "unknown")
                return False, f"Unhealthy: {reason}"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def wait_for_daemon_ready(host: str, port: int, timeout_s: float = 15.0) -> bool:
    """
    Poll /healthz until daemon is ready or timeout.
    
    Returns True if daemon became healthy, False if timeout.
    """
    start_time = time.time()
    last_error = None
    
    while time.time() - start_time < timeout_s:
        is_healthy, error = check_daemon_health(host, port, timeout=1.0)
        if is_healthy:
            return True
        
        last_error = error
        time.sleep(0.5)
    
    # Timeout
    if last_error:
        typer.echo(f"  Timeout waiting for daemon (last error: {last_error})")
    return False


def wait_for_process_death(pid: int, timeout_s: float = 12.0) -> bool:
    """
    Wait for process to die.
    
    Returns True if process died, False if still alive after timeout.
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout_s:
        if not is_process_alive(pid):
            return True
        time.sleep(0.1)
    
    return False


def explain_exit_code(exit_code: int) -> str:
    """
    Return human-readable explanation of daemon exit code.
    """
    explanations = {
        EXIT_SUCCESS: "Success",
        EXIT_GENERIC_FAILURE: "Generic failure",
        EXIT_PID_LOCK_HELD: "Daemon already running (PID lock held)",
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
        help="Wait for daemon to become ready (default: --wait)"
    ),
    timeout: Optional[float] = typer.Option(
        None,
        "--timeout",
        min=1.0,
        help="Seconds to wait for readiness (default: config + 5s)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show daemon logs during startup"
    ),
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
    # Load config to get daemon host/port
    try:
        config = load_config()
        host = config.daemon.host
        port = config.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load config: {e}", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    
    # Check if daemon is already running
    existing_pid = get_daemon_pid()
    if existing_pid and is_process_alive(existing_pid):
        typer.secho(f"✓ Daemon already running (PID: {existing_pid})", fg=typer.colors.GREEN)
        
        # Check health if already running
        is_healthy, error = check_daemon_health(host, port)
        if is_healthy:
            typer.echo(f"  Daemon is healthy on http://{host}:{port}")
        else:
            typer.secho(f"  Warning: Daemon may be unhealthy ({error})", fg=typer.colors.YELLOW)
        
        typer.echo(f"  Logs: {DAEMON_LOG_FILE}")
        raise typer.Exit(EXIT_SUCCESS)
    
    # Spawn daemon process
    typer.echo("Starting daemon...")
    
    try:
        # Prepare spawn arguments
        if verbose:
            # Inherit stdout/stderr to show logs
            stdout = None
            stderr = None
        else:
            # Redirect to /dev/null
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL
        
        # Spawn daemon in new session (detached)
        process = subprocess.Popen(
            [sys.executable, "-m", "daemon.main"],
            start_new_session=True,
            stdout=stdout,
            stderr=stderr,
            env=os.environ.copy(),  # Explicit env passthrough (allows AI_APP_CONFIG injection)
        )
        
        # Brief wait to see if it crashes immediately
        time.sleep(0.5)
        
        # Check if process is still alive
        if process.poll() is not None:
            # Process died immediately
            exit_code = process.returncode
            typer.secho(
                f"✗ Daemon failed to start (exit code: {exit_code})",
                fg=typer.colors.RED
            )
            typer.echo(f"  {explain_exit_code(exit_code)}")
            typer.echo(f"  Spawn cmd: {sys.executable} -m daemon.main")
            typer.echo(f"  Check logs: {DAEMON_LOG_FILE}")
            if not verbose:
                typer.echo(f"  Tip: re-run with --verbose or tail {DAEMON_LOG_FILE}")
            raise typer.Exit(exit_code)
        
        typer.secho(f"✓ Daemon spawned (PID: {process.pid})", fg=typer.colors.GREEN)
        
        # Show log location if not in verbose mode
        if not verbose:
            typer.echo(f"  Logs: {DAEMON_LOG_FILE}")
        
        # Wait for readiness if requested
        if wait:
            typer.echo(f"  Waiting for daemon to become ready...")
            # Derive timeout from config or use override
            ready_timeout = timeout or max(10.0, float(config.cdp.start_timeout_s) + 5.0)
            if wait_for_daemon_ready(host, port, timeout_s=ready_timeout):
                typer.secho(f"✓ Daemon ready on http://{host}:{port}", fg=typer.colors.GREEN)
            else:
                typer.secho(
                    "✗ Daemon did not become ready in time",
                    fg=typer.colors.RED
                )
                typer.echo(f"  Check logs: {DAEMON_LOG_FILE}")
                typer.echo("  The daemon may still be starting up...")
                raise typer.Exit(EXIT_GENERIC_FAILURE)
        else:
            typer.echo(f"  Daemon starting in background (use 'daemon status' to check)")
        
    except FileNotFoundError:
        typer.secho(
            "✗ Could not find Python or daemon module",
            fg=typer.colors.RED
        )
        typer.echo("  Ensure the package is installed or PYTHONPATH is set")
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    except Exception as e:
        typer.secho(f"✗ Failed to start daemon: {e}", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    
    raise typer.Exit(EXIT_SUCCESS)


@app.command("stop")
def stop_daemon(
    force: bool = typer.Option(
        False,
        "--force",
        help="Force kill if graceful shutdown fails"
    ),
):
    """
    Stop the running AI daemon.
    
    Sends SIGTERM to trigger graceful shutdown. The daemon will:
    - Cancel health monitoring
    - Close browser connections
    - Kill browser process group
    - Clean up PID files
    
    Use --force to send SIGKILL if graceful shutdown times out.
    """
    # Load config
    try:
        config = load_config()
        host = config.daemon.host
        port = config.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load config: {e}", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    
    # Get daemon PID
    pid = get_daemon_pid()
    if not pid:
        typer.secho("✗ Daemon not running (no PID file)", fg=typer.colors.RED)
        raise typer.Exit(1)
    
    # Check if process is alive
    if not is_process_alive(pid):
        typer.secho(
            f"✗ Daemon not running (PID {pid} not found)",
            fg=typer.colors.RED
        )
        typer.echo("  Cleaning up stale PID file...")
        PID_FILE.unlink(missing_ok=True)
        raise typer.Exit(1)
    
    # Optional: Verify it's our daemon by checking health
    is_healthy, _ = check_daemon_health(host, port, timeout=1.0)
    if not is_healthy and not force:
        typer.secho(
            f"⚠ Warning: Process {pid} exists but daemon API not responding",
            fg=typer.colors.YELLOW
        )
        typer.echo("  This may not be the daemon process.")
        if not typer.confirm("  Continue anyway?"):
            # Do NOT unlink PID file here - process may still be alive
            raise typer.Exit(1)
    
    # Send SIGTERM
    typer.echo(f"Stopping daemon (PID: {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        typer.secho("✗ Process already stopped", fg=typer.colors.YELLOW)
        PID_FILE.unlink(missing_ok=True)
        raise typer.Exit(EXIT_SUCCESS)
    except PermissionError:
        typer.secho(f"✗ Permission denied (cannot kill PID {pid})", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    
    typer.echo("  Sent SIGTERM, waiting for graceful shutdown...")
    
    # Wait for process to die (daemon has 10s grace + 2s buffer)
    if wait_for_process_death(pid, timeout_s=12.0):
        typer.secho("✓ Daemon stopped gracefully", fg=typer.colors.GREEN)
        
        # Verify CDP port is closed
        time.sleep(0.5)
        cdp_port = config.cdp.port
        try:
            response = requests.get(
                f"http://127.0.0.1:{cdp_port}/json/version",
                timeout=1.0
            )
            typer.secho(
                f"  Warning: CDP still responding on port {cdp_port}",
                fg=typer.colors.YELLOW
            )
        except requests.exceptions.ConnectionError:
            # Good - CDP is dead
            pass
        except Exception:
            pass
        
        # Verify PID file is cleaned up
        if PID_FILE.exists():
            typer.secho("  Warning: PID file still exists", fg=typer.colors.YELLOW)
        
        raise typer.Exit(EXIT_SUCCESS)
    
    # Timeout - process still alive
    typer.secho(
        "⚠ Daemon did not stop gracefully within 12s",
        fg=typer.colors.YELLOW
    )
    
    if force:
        typer.echo("  Sending SIGKILL (force)...")
        try:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1.0)
            
            if is_process_alive(pid):
                typer.secho("✗ Failed to kill daemon", fg=typer.colors.RED)
                raise typer.Exit(EXIT_GENERIC_FAILURE)
            else:
                typer.secho("✓ Daemon killed (forced)", fg=typer.colors.GREEN)
                PID_FILE.unlink(missing_ok=True)
                raise typer.Exit(EXIT_SUCCESS)
        except Exception as e:
            typer.secho(f"✗ Failed to force kill: {e}", fg=typer.colors.RED)
            raise typer.Exit(EXIT_GENERIC_FAILURE)
    else:
        typer.echo("  Daemon still running. Use --force to send SIGKILL")
        raise typer.Exit(EXIT_GENERIC_FAILURE)


@app.command("status")
def daemon_status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show detailed daemon status"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output status as JSON"
    ),
):
    """
    Check the status of the AI daemon.
    
    Shows:
    - Whether daemon process is running
    - Health status (/healthz)
    - Available AIs and uptime (if --verbose)
    
    Exit codes:
      0 = Daemon running and healthy
      1 = Daemon not running
      2 = Daemon running but unhealthy
    """
    # Load config
    try:
        config = load_config()
        host = config.daemon.host
        port = config.daemon.port
    except Exception as e:
        typer.secho(f"✗ Failed to load config: {e}", fg=typer.colors.RED)
        raise typer.Exit(EXIT_GENERIC_FAILURE)
    
    # Check PID file
    pid = get_daemon_pid()
    if not pid:
        if json_output:
            import json
            typer.echo(json.dumps({"running": False, "reason": "No PID file"}))
            raise typer.Exit(1)
        
        typer.secho("Daemon status: 🛑 Not Running", fg=typer.colors.RED)
        typer.echo("  No PID file found")
        typer.echo("  Start the daemon with your CLI's 'daemon start' command.")
        raise typer.Exit(1)
    
    # Check if process is alive
    if not is_process_alive(pid):
        if json_output:
            import json
            typer.echo(json.dumps({"running": False, "pid": pid, "reason": "Stale PID file"}))
            raise typer.Exit(1)
        
        typer.secho("Daemon status: 🛑 Not Running", fg=typer.colors.RED)
        typer.echo(f"  PID {pid} not found (stale PID file)")
        typer.echo("  Start the daemon with your CLI's 'daemon start' command.")
        raise typer.Exit(1)
    
    # Process is alive, check health
    is_healthy, error = check_daemon_health(host, port, timeout=2.0)
    
    # JSON output mode
    if json_output:
        import json
        status_data = {
            "running": True,
            "pid": pid,
            "healthy": is_healthy,
            "error": error,
            "api_url": f"http://{host}:{port}",
        }
        
        # Add detailed info if healthy
        if is_healthy:
            try:
                response = requests.get(
                    f"http://{host}:{port}/status",
                    timeout=3.0
                )
                if response.status_code == 200:
                    status_data["daemon_info"] = response.json()
            except Exception:
                pass
        
        typer.echo(json.dumps(status_data, indent=2))
        raise typer.Exit(0 if is_healthy else 2)
    
    # Human-readable output
    typer.secho(f"Daemon status: ✅ Running (PID: {pid})", fg=typer.colors.GREEN)
    
    if is_healthy:
        typer.secho(f"  Health: ✅ OK", fg=typer.colors.GREEN)
        typer.echo(f"  API: http://{host}:{port}")
        
        # Get detailed status if verbose
        if verbose:
            try:
                response = requests.get(
                    f"http://{host}:{port}/status",
                    timeout=3.0
                )
                if response.status_code == 200:
                    data = response.json()
                    daemon_info = data.get("daemon", {})
                    ais = data.get("ais", {})
                    
                    typer.echo("")
                    typer.echo("Daemon Info:")
                    typer.echo(f"  Version: {daemon_info.get('version', 'unknown')}")
                    typer.echo(f"  Uptime: {daemon_info.get('uptime_s', 0):.1f}s")
                    typer.echo(f"  Browser Pool: {'active' if daemon_info.get('browser_pool_active') else 'inactive'}")
                    typer.echo(f"  CDP Health: {'OK' if daemon_info.get('cdp_healthy') else 'unhealthy'}")
                    
                    available = daemon_info.get('available_ais', [])
                    if available:
                        typer.echo(f"  Available AIs: {', '.join(available)}")
                    
                    typer.echo("")
                    typer.echo(f"AI Instances ({len(ais)}):")
                    for ai_name, ai_data in ais.items():
                        connected = "✓" if ai_data.get('connected') else "✗"
                        transport = ai_data.get('transport_type', 'unknown')
                        typer.echo(f"  {connected} {ai_name} ({transport})")
                
            except Exception as e:
                typer.secho(f"  Warning: Could not fetch detailed status: {e}", fg=typer.colors.YELLOW)
        
        raise typer.Exit(EXIT_SUCCESS)
    
    else:
        # Daemon running but unhealthy
        typer.secho(f"  Health: ⚠ Unhealthy ({error})", fg=typer.colors.YELLOW)
        typer.echo(f"  Check logs: {DAEMON_LOG_FILE}")
        typer.echo(f"  Tip: tail {DAEMON_LOG_FILE} to diagnose startup health.")
        raise typer.Exit(2)


# ---------------------------------------------------------------------------
# Standalone Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
