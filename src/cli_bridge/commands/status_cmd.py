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
from typing import Any

# Reuse the daemon's config reader to discover host/port
from daemon import config as daemon_config


def _print_human_status(full_status: dict[str, Any], ai_name: str | None) -> int:
    """Pretty-print daemon status, optionally filtered to one AI."""
    daemon = full_status.get("daemon", {})
    ais = full_status.get("ais", {})

    print("Daemon:")
    print(f"  Version:           {daemon.get('version', 'unknown')}")
    available = daemon.get("available_ais") or list(ais.keys())
    print(f"  Available AIs:     {', '.join(available) if available else '(none)'}")
    print(f"  Browser Pool:      {'active' if daemon.get('browser_pool_active') else 'inactive'}")
    print()

    # If a specific AI was requested, show only that
    target = (ai_name or "").strip() or None
    if target and target.lower() not in {a.lower() for a in ais.keys()}:
        print(f"✗ AI '{ai_name}' not found. Available: {', '.join(ais.keys()) or '(none)'}")
        return 2

    def render_ai(k: str, v: dict[str, Any]) -> None:
        print(f"[{k}]")
        print(f"  Transport:         {v.get('transport_type', 'unknown')}")
        print(f"  Connected:         {bool(v.get('connected'))}")
        if v.get("cdp_source"):
            print(f"  CDP Source:        {v.get('cdp_source')}")
        if v.get("cdp_url"):
            print(f"  CDP URL:           {v.get('cdp_url')}")
        if v.get("last_page_url"):
            print(f"  Page URL:          {v.get('last_page_url')}")
        # Domain/session metrics from BaseAI
        if "message_count" in v:
            print(f"  Message Count:     {v.get('message_count')}")
        if "session_duration_s" in v:
            try:
                dur = float(v.get("session_duration_s") or 0.0)
                print(f"  Session Duration:  {dur:.1f}s")
            except Exception:
                pass
        if "ctaw_size" in v or "context_window_tokens" in v:
            # Show whichever field exists (v2 currently exposes ctaw_size)
            ctw = v.get("context_window_tokens", v.get("ctaw_size"))
            print(f"  Context Window:    {ctw} tokens")
        if "ctaw_usage_percent" in v:
            print(f"  Context Used:      {v.get('ctaw_usage_percent')}%")
        if "error" in v:
            print(f"  Error:             {v.get('error')}")
        print()

    # Render one or all
    if target:
        # Find the exact key with case-insensitive match
        key_map = {k.lower(): k for k in ais.keys()}
        render_ai(key_map[target.lower()], ais[key_map[target.lower()]])
    else:
        if not ais:
            print("(no AI instances reported)")
        else:
            for name, payload in ais.items():
                render_ai(name, payload)

    return 0


def run(ai_name: str, json_out: bool = False) -> int:
    """
    Get status from the daemon.

    Args:
        ai_name: Target AI to display, or use 'all' to show every AI.
                 (Kept for CLI compatibility; filtering happens client-side.)
        json_out: If True, print JSON instead of human-readable output.

    Returns:
        Exit code (0 success, 1 daemon error, 2 unknown AI)
    """
    try:
        cfg = daemon_config.load_config()
        host = cfg.daemon.host
        port = cfg.daemon.port
        url = f"http://{host}:{port}/status"

        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        status = resp.json()

        # Normalize the "all" convention: if user passes "all" or "*", don't filter
        requested = (ai_name or "").strip()
        if requested in {"all", "*"}:
            requested = None

        if json_out:
            if requested:
                # Filter to a single AI (return the AI payload directly if present)
                ais = status.get("ais", {})
                # Case-insensitive lookup
                key_map = {k.lower(): k for k in ais.keys()}
                if requested.lower() not in key_map:
                    print(
                        jsonlib.dumps(
                            {
                                "ok": False,
                                "error": "unknown_ai",
                                "message": f"AI '{ai_name}' not found",
                                "available": list(ais.keys()),
                            },
                            indent=2,
                        )
                    )
                    return 2
                only = {key_map[requested.lower()]: ais[key_map[requested.lower()]]}
                print(jsonlib.dumps({"daemon": status.get("daemon", {}), "ais": only}, indent=2))
            else:
                print(jsonlib.dumps(status, indent=2))
            return 0

        # Human-readable output
        return _print_human_status(status, requested)

    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to the AI daemon. Is it running?")
        print("  Try: ai-cli-bridge daemon start")
        return 1
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "unknown"
        print(f"✗ Daemon responded with HTTP {code}")
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text if e.response is not None else "(no body)"
        print(detail)
        return 1
    except Exception as e:
        print(f"✗ Unexpected error while fetching status: {e}")
        return 1
