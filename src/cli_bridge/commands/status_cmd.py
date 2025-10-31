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
import requests
import typer
from typing import Any

from ..errors import DaemonNotRunning, UnknownAI
from ..constants import API_STATUS_CHECK_TIMEOUT_S


def _print_human_status(full_status: dict[str, Any], ai_name: str | None) -> int:
    """Pretty-print daemon status, optionally filtered to one AI."""
    daemon = full_status.get("daemon", {})
    ais = full_status.get("ais", {})

    typer.echo("Daemon:")
    typer.echo(f"  Version:           {daemon.get('version', 'unknown')}")
    typer.echo(f"  PID:               {daemon.get('pid', 'unknown')}")
    available = daemon.get("available_ais") or list(ais.keys())
    typer.echo(f"  Available AIs:     {', '.join(available) if available else '(none)'}")
    typer.echo(f"  Browser Pool:      {'active' if daemon.get('browser_pool_active') else 'inactive'}")
    typer.echo(f"  CDP Health:        {'OK' if daemon.get('cdp_healthy') else 'unhealthy'}")
    typer.echo("")

    # If a specific AI was requested, show only that
    target = (ai_name or "").strip() or None
    if target and target.lower() not in {a.lower() for a in ais.keys()}:
        typer.echo(f"✗ AI '{ai_name}' not found. Available: {', '.join(ais.keys()) or '(none)'}")
        return UnknownAI.exit_code

    def render_ai(k: str, v: dict[str, Any]) -> None:
        typer.echo(f"[{k}]")
        typer.echo(f"  Transport:         {v.get('transport_type', 'unknown')}")
        typer.echo(f"  Connected:         {bool(v.get('connected'))}")
        if v.get("cdp_source"):
            typer.echo(f"  CDP Source:        {v.get('cdp_source')}")
        if v.get("cdp_url"):
            typer.echo(f"  CDP URL:           {v.get('cdp_url')}")
        if v.get("last_page_url"):
            typer.echo(f"  Page URL:          {v.get('last_page_url')}")
        # Domain/session metrics from BaseAI
        if "message_count" in v:
            typer.echo(f"  Message Count:     {v.get('message_count')}")
        if "session_duration_s" in v:
            try:
                dur = float(v.get("session_duration_s") or 0.0)
                typer.echo(f"  Session Duration:  {dur:.1f}s")
            except Exception:
                pass
        if "ctaw_size" in v or "context_window_tokens" in v:
            # Show whichever field exists (v2 currently exposes ctaw_size)
            ctw = v.get("context_window_tokens", v.get("ctaw_size"))
            typer.echo(f"  Context Window:    {ctw} tokens")
        if "ctaw_usage_percent" in v:
            typer.echo(f"  Context Used:      {v.get('ctaw_usage_percent')}%")
        if "error" in v:
            typer.echo(f"  Error:             {v.get('error')}")
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
                        "data": {
                            "available": list(ais.keys())
                        }
                    }
                    typer.echo(jsonlib.dumps(envelope, indent=2))
                    return UnknownAI.exit_code
                
                only = {key_map[requested.lower()]: ais[key_map[requested.lower()]]}
                envelope = {
                    "ok": True,
                    "code": 0,
                    "message": "Status retrieved",
                    "data": {
                        "daemon": status.get("daemon", {}),
                        "ais": only
                    }
                }
                typer.echo(jsonlib.dumps(envelope, indent=2))
            else:
                envelope = {
                    "ok": True,
                    "code": 0,
                    "message": "Status retrieved",
                    "data": status
                }
                typer.echo(jsonlib.dumps(envelope, indent=2))
            return 0

        # Human-readable output
        return _print_human_status(status, requested)

    except requests.exceptions.ConnectionError:
        typer.echo("✗ Daemon not running")
        typer.echo("  Start it with: aicli daemon start")
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
