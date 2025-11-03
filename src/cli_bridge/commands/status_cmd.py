"""
Status command (daemon-backed).

This version makes the CLI a *pure client* of the daemon:
- Calls GET /status on the running daemon (host/port from daemon config)
- Optionally filters to a single AI if an AI name is provided
- Supports --json output

Exit codes:
  0  success
  1  daemon not reachable / other unexpected error
  2  requested AI not found in daemon status
"""

from __future__ import annotations

import json as jsonlib
from typing import Any

import requests
import typer

from ..constants import API_STATUS_CHECK_TIMEOUT_S
from ..errors import DaemonNotRunning, UnknownAI


def _print_human_status(full_status: dict[str, Any], ai_name: str | None) -> int:
    """Pretty-print daemon status, optionally filtered to one AI."""
    daemon = full_status.get("daemon", {})
    ais = full_status.get("ais", {})

    typer.echo("Daemon:")
    typer.echo(f"  Version:           {daemon.get('version', 'unknown')}")
    typer.echo(f"  PID:               {daemon.get('pid', 'unknown')}")
    available = daemon.get("available_ais") or list(ais.keys())
    typer.echo(f"  Available AIs:     {', '.join(available) if available else '(none)'}")
    typer.echo(
        f"  Browser Pool:      {'active' if daemon.get('browser_pool_active') else 'inactive'}"
    )
    typer.echo(f"  CDP Health:        {'OK' if daemon.get('cdp_healthy') else 'unhealthy'}")
    typer.echo("")

    # If a specific AI was requested, show only that
    target = (ai_name or "").strip() or None
    if target and target.lower() not in {a.lower() for a in ais.keys()}:
        typer.echo(f"✗ AI '{ai_name}' not found. Available: {', '.join(ais.keys()) or '(none)'}")
        return UnknownAI.exit_code

    def render_ai(k: str, v: dict[str, Any]) -> None:
        typer.echo(f"[{k}]")

        # Transport information (new structure)
        transport = v.get("transport", {})
        if isinstance(transport, dict):
            transport_name = transport.get("name", "unknown")
            transport_kind = transport.get("kind", "unknown")
            connected = transport.get("connected", False)

            # Display transport info
            typer.echo(f"  Transport:         {transport_name}")
            typer.echo(f"  Type:              {transport_kind}")

            # Connected status with color
            if connected:
                typer.secho("  Connected:         True", fg=typer.colors.GREEN)
            else:
                typer.secho("  Connected:         False", fg=typer.colors.YELLOW)

            # Additional transport details if available
            transport_status = transport.get("status", {})
            if isinstance(transport_status, dict):
                if "base_url" in transport_status:
                    typer.echo(f"  Base URL:          {transport_status['base_url']}")
                if "cdp_origin" in transport_status:
                    typer.echo(f"  CDP Origin:        {transport_status['cdp_origin']}")
        else:
            # Fallback for old format
            typer.echo(f"  Transport:         {transport if transport else 'unknown'}")
            typer.echo("  Connected:         False")

        # Session metrics from BaseAI
        if "message_count" in v:
            typer.echo(f"  Message Count:     {v.get('message_count')}")

        if "session_duration_s" in v:
            try:
                dur = float(v.get("session_duration_s") or 0.0)
                typer.echo(f"  Session Duration:  {dur:.1f}s")
            except Exception:
                pass

        # Context window information
        if "ctaw_size" in v:
            ctw = v.get("ctaw_size")
            typer.echo(f"  Context Window:    {ctw:,} tokens")

        # Context usage with color coding
        if "ctaw_usage_percent" in v:
            usage = v.get("ctaw_usage_percent", 0)
            usage_str = f"  Context Used:      {usage}%"

            # Color code based on usage
            if usage >= 95:
                typer.secho(usage_str, fg=typer.colors.RED)
            elif usage >= 85:
                typer.secho(usage_str, fg=typer.colors.YELLOW)
            elif usage >= 70:
                typer.secho(usage_str, fg=typer.colors.YELLOW)
            else:
                typer.echo(usage_str)

        # Token breakdown if available
        if "sent_tokens" in v and "response_tokens" in v:
            sent = v.get("sent_tokens", 0)
            received = v.get("response_tokens", 0)
            typer.echo(f"  Tokens Sent:       {sent:,}")
            typer.echo(f"  Tokens Received:   {received:,}")

        # Performance metrics if available
        if "avg_response_time_ms" in v and v.get("avg_response_time_ms"):
            avg_time = v.get("avg_response_time_ms")
            typer.echo(f"  Avg Response:      {avg_time:.0f}ms")

        if "tokens_per_sec" in v and v.get("tokens_per_sec"):
            tps = v.get("tokens_per_sec")
            typer.echo(f"  Tokens/sec:        {tps:.1f}")

        # Error information
        error_data = v.get("error")
        if isinstance(error_data, dict):
            # New structured error
            msg = error_data.get("message", "Unknown error")
            typer.secho(f"  Error:             {msg}", fg=typer.colors.RED)
            if error_data.get("user_action"):
                typer.secho(
                    f"  Suggested Action:  {error_data['user_action']}", fg=typer.colors.YELLOW
                )
        elif error_data:
            # Old error (string) or unexpected format
            typer.secho(f"  Error:             {error_data}", fg=typer.colors.RED)

        typer.echo("")

    # Render one or all
    if target:
        # Find the exact key with case-insensitive match
        key_map = {k.lower(): k for k in ais.keys()}
        render_ai(key_map[target.lower()], ais[key_map[target.lower()]])
    else:
        if not ais:
            typer.echo("(no AI instances reported)")
        else:
            for name, payload in ais.items():
                render_ai(name, payload)

    return 0


def run(host: str, port: int, ai_name: str, json_out: bool = False) -> int:
    """
    Get status from the daemon.

    Args:
        host: Daemon host (from config)
        port: Daemon port (from config)
        ai_name: Target AI to display, or use 'all' to show every AI.
        json_out: If True, print JSON instead of human-readable output.

    Returns:
        Exit code (0 success, 1 daemon error, 2 unknown AI)
    """
    try:
        url = f"http://{host}:{port}/status"

        resp = requests.get(url, timeout=API_STATUS_CHECK_TIMEOUT_S)
        resp.raise_for_status()
        status = resp.json()

        # Normalize the "all" convention: if user passes "all" or "*", don't filter
        requested = (ai_name or "").strip()
        if requested in {"all", "*", ""}:
            requested = None

        if json_out:
            if requested:
                # Filter to a single AI (return the AI payload directly if present)
                ais = status.get("ais", {})
                # Case-insensitive lookup
                key_map = {k.lower(): k for k in ais.keys()}
                if requested.lower() not in key_map:
                    envelope = {
                        "ok": False,
                        "code": UnknownAI.exit_code,
                        "message": f"AI '{ai_name}' not found",
                        "data": {"available": list(ais.keys())},
                    }
                    typer.echo(jsonlib.dumps(envelope, indent=2))
                    return UnknownAI.exit_code

                only = {key_map[requested.lower()]: ais[key_map[requested.lower()]]}
                envelope = {
                    "ok": True,
                    "code": 0,
                    "message": "Status retrieved",
                    "data": {"daemon": status.get("daemon", {}), "ais": only},
                }
                typer.echo(jsonlib.dumps(envelope, indent=2))
            else:
                envelope = {"ok": True, "code": 0, "message": "Status retrieved", "data": status}
                typer.echo(jsonlib.dumps(envelope, indent=2))
            return 0

        # Human-readable output
        return _print_human_status(status, requested)

    except requests.exceptions.ConnectionError:
        typer.echo("✗ Daemon not running")
        typer.echo("  Start it with: ai-cli-bridge daemon start")
        return DaemonNotRunning.exit_code

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "unknown"
        typer.echo(f"✗ Daemon error (HTTP {code})")
        try:
            detail = e.response.json()
            typer.echo(f"  {detail.get('detail', 'No details provided')}")
        except Exception:
            pass
        return 1

    except Exception as e:
        typer.echo(f"✗ Unexpected error: {e}")
        return 1
