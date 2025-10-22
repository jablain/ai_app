#!/usr/bin/env bash
# Launch CDP browser with fresh AI chat sessions
# Part of ai-cli-bridge daemon system
set -euo pipefail

# --- Configuration ---
CDP_PORT=9223
PROJECT_ROOT="$HOME/dev/ai_app"
PROFILE_DIR="$PROJECT_ROOT/runtime/daemon/browser/profiles/multi_ai_cdp"
PID_FILE="$PROJECT_ROOT/runtime/daemon/browser/browser.pid"

# Fresh session URLs (always open new chats)
CLAUDE_URL="https://claude.ai/new"
GEMINI_URL="https://gemini.google.com/app"
CHATGPT_URL="https://chat.openai.com/"

# Chromium command (Flatpak)
CHROMIUM_CMD="flatpak run io.github.ungoogled_software.ungoogled_chromium"

# --- If already running, exit cleanly ---
if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE" || true)"
    if [ -n "${OLD_PID:-}" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "✓ CDP browser already running (PID: $OLD_PID)"
        exit 0
    else
        echo "→ Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Also check via HTTP (in case PID file was lost)
if curl -sSf "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    echo "✓ CDP browser already running on port ${CDP_PORT}"
    echo "  Warning: No PID file found, but browser is responding"
    exit 0
fi

echo "🚀 Launching CDP browser with fresh AI sessions..."

# Ensure directories exist
mkdir -p "$PROFILE_DIR" "$(dirname "$PID_FILE")"

echo "  Browser: ungoogled-chromium (Flatpak)"
echo "  Profile: $PROFILE_DIR"
echo "  Opening fresh chat sessions for all AIs"

# Launch browser with the three tabs
$CHROMIUM_CMD \
  --remote-debugging-port="${CDP_PORT}" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "$CLAUDE_URL" \
  "$GEMINI_URL" \
  "$CHATGPT_URL" >/dev/null 2>&1 &

BROWSER_PID=$!
echo "$BROWSER_PID" > "$PID_FILE"
echo "  PID: $BROWSER_PID (saved to $PID_FILE)"

# Wait for CDP endpoint to be ready (max ~15s)
echo "→ Waiting for CDP endpoint..."
for _ in {1..30}; do
    if curl -sSf "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
        echo "✓ CDP browser ready on port ${CDP_PORT}"
        WS_URL="$(curl -s "http://127.0.0.1:${CDP_PORT}/json/version" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("webSocketDebuggerUrl","N/A"))' 2>/dev/null || echo "N/A")"
        [ "$WS_URL" != "N/A" ] && echo "  WebSocket: $WS_URL"
        echo
        echo "✓ Browser launched with fresh AI chat sessions"
        echo "  - Already logged in (cookies preserved)"
        echo "  - 3 new chat tabs ready to use"
        echo "  - Use StopCDP.sh to stop the browser"
        exit 0
    fi
    sleep 0.5
done

echo "✗ Error: CDP endpoint did not come up on port ${CDP_PORT}"
echo "  Check the browser process (PID $BROWSER_PID) or logs."
exit 1
