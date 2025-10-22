# ai_cli_bridge/commands/init_cdp_cmd.py

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def die(message: str, exit_code: int = 1):
    """Print error and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(exit_code)


def _is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _ensure_dir(p: str):
    d = Path(p)
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)


def _launch_playwright(port: int, user_data_dir: str, startup_urls: list) -> subprocess.Popen:
    """
    Launch Playwright-bundled Chromium with:
      --remote-debugging-port
      --user-data-dir
      startup URLs
    """
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
        die(f"Unable to locate Playwright Chromium: {e}")

    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--new-window",
    ] + startup_urls

    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _wait_for_ws(port: int, wait_seconds: int) -> str | None:
    """Poll /json/version until webSocketDebuggerUrl is present, or timeout."""
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
    Launch a CDP-enabled browser for the given AI and print a ws:// URL.
    Returns exit code: 0 on success, 1 on failure.
    
    V2.0.0 simplified version - uses hardcoded multi-AI setup.
    """
    # V2.0.0 hardcoded configuration
    port = 9223
    wait_seconds = 10
    
    # Project root detection
    project_root = Path.home() / "dev/ai_app/ai-cli-bridge"
    user_data_dir = str(project_root / "runtime/profiles/multi_ai_cdp")
    
    # AI-specific startup URLs
    startup_urls_map = {
        "claude": ["https://claude.ai/new"],
        "gemini": ["https://gemini.google.com/app"],
        "chatgpt": ["https://chat.openai.com/"],
    }
    
    startup_urls = startup_urls_map.get(ai_name.lower())
    if not startup_urls:
        die(f"Unknown AI: '{ai_name}'. Available: claude, gemini, chatgpt")

    # If something is already listening, don't double-launch
    proc = None
    try:
        if not _is_port_open(port):
            print("Launching CDP browser...")
            proc = _launch_playwright(port, user_data_dir, startup_urls)

        ws = _wait_for_ws(port, wait_seconds)
        if not ws:
            if proc and proc.poll() is not None:
                try:
                    _, err = proc.communicate(timeout=0.5)
                    err_txt = err.decode("utf-8", "ignore")
                except Exception:
                    err_txt = "(no stderr)"
                die(f"DevTools endpoint not available. Browser exited early.\n{err_txt}")
            die("DevTools endpoint not available. Is the browser blocked?")

        print(f"CDP ready: {ws}")
        print("Tip: export this in your shell:")
        print(f'export AI_CLI_BRIDGE_CDP_URL="{ws}"')
        return 0
    finally:
        pass
