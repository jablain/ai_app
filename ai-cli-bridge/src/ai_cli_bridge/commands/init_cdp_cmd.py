# ai_cli_bridge/commands/init_cdp_cmd.py

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

from ..config import load
from ..errors import E, die


def _is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _ensure_dir(p: str):
    d = Path(p)
    d.mkdir(parents=True, exist_ok=True)
    # lock down perms per spec
    os.chmod(d, 0o700)


def _launch_playwright(cdp_cfg: Dict[str, Any]) -> subprocess.Popen:
    """
    Launch Playwright-bundled Chromium with:
      --remote-debugging-port
      --user-data-dir
      startup URLs
    """
    port = int(cdp_cfg.get("port", 9223))
    user_data_dir = cdp_cfg.get("user_data_dir")
    if not user_data_dir:
        die(E.E003, "cdp.user_data_dir is required for launcher=playwright")

    _ensure_dir(user_data_dir)

    # Locate the Playwright Chromium executable
    py = (
        "from playwright.sync_api import sync_playwright; "
        "p=sync_playwright().start(); "
        "print(p.chromium.executable_path); "
        "p.stop()"
    )
    try:
        exe = subprocess.check_output(["python", "-c", py], text=True).strip()
    except Exception as e:
        die(E.E003, f"Unable to locate Playwright Chromium: {e}")

    urls = list(cdp_cfg.get("startup_urls") or [])
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--new-window",
    ] + urls

    # Launch detached so CLI can return while browser lives
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _launch_flatpak(cdp_cfg: Dict[str, Any]) -> subprocess.Popen:
    """
    Launch Ungoogled Chromium Flatpak with remote debugging.
    """
    port = int(cdp_cfg.get("port", 9222))
    user_data_dir = cdp_cfg.get("user_data_dir")
    flatpak_id = cdp_cfg.get("flatpak_id", "io.github.ungoogled_software.ungoogled_chromium")

    if not user_data_dir:
        die(E.E003, "cdp.user_data_dir is required for launcher=flatpak")

    _ensure_dir(user_data_dir)

    urls = list(cdp_cfg.get("startup_urls") or [])
    base = [
        "flatpak", "run", flatpak_id,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--new-window",
    ]
    args = base + urls
    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _wait_for_ws(port: int, wait_seconds: int) -> str | None:
    """
    Poll /json/version until webSocketDebuggerUrl is present, or timeout.
    """
    import urllib.request
    deadline = time.time() + max(1, wait_seconds)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as r:
                meta = json.loads(r.read().decode("utf-8", "ignore"))
            ws = meta.get("webSocketDebuggerUrl") or meta.get("websocketDebuggerUrl")
            if ws and ws != "null":
                return ws
        except Exception:
            pass
        time.sleep(0.4)
    return None


def run(ai_name: str) -> int:
    """
    Launch a CDP-enabled browser for the given AI config and print a ws:// URL.
    Returns exit code: 0 on success, 1 on failure.
    """
    cfg = load(ai_name)
    cdp = cfg.get("cdp") or {}
    if not cdp:
        die(E.E003, f"No 'cdp' block found in config for '{ai_name}'")

    launcher = (cdp.get("launcher") or "flatpak").strip().lower()
    port = int(cdp.get("port") or (9223 if launcher == "playwright" else 9222))
    wait_seconds = int(cdp.get("wait_seconds") or 10)

    # If something is already listening, don't double-launch; just try to read the ws endpoint.
    proc = None
    try:
        if not _is_port_open(port):
            print("Launching CDP browser...")
            if launcher == "playwright":
                proc = _launch_playwright(cdp)
            elif launcher == "flatpak":
                proc = _launch_flatpak(cdp)
            else:
                die(E.E003, f"Unknown cdp.launcher '{launcher}'. Expected 'playwright' or 'flatpak'.")

        ws = _wait_for_ws(port, wait_seconds)
        if not ws:
            if proc and proc.poll() is not None:
                # Process died early; show a hint
                try:
                    _, err = proc.communicate(timeout=0.5)
                    err_txt = err.decode("utf-8", "ignore")
                except Exception:
                    err_txt = "(no stderr)"
                die(E.E002, f"DevTools endpoint not available. Browser exited early.\n{err_txt}")
            die(E.E002, "DevTools endpoint not available. Is the browser blocked by pop-ups or policy?")

        print(f"CDP ready: {ws}")
        print("Tip: export this in your shell if you want it available to subsequent commands:")
        print(f'export AI_CLI_BRIDGE_CDP_URL="{ws}"')
        return 0
    finally:
        # Do NOT kill the browser; leave it running for the session.
        pass

