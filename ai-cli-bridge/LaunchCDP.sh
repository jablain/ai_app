#!/bin/bash
# Launch CDP browser with fresh AI chat sessions
# Part of ai-cli-bridge daemon system

set -e

# Configuration
CDP_PORT=9223
PROJECT_ROOT="$HOME/dev/ai_app/ai-cli-bridge"
SHARED_ROOT="$HOME/dev/ai_app/shared"
PROFILE_DIR="$PROJECT_ROOT/runtime/profiles/multi_ai_cdp"
PID_FILE="$PROJECT_ROOT/runtime/browser.pid"

# Fresh session URLs (always open new chats)
CLAUDE_URL="https://claude.ai/new"
GEMINI_URL="https://gemini.google.com/app"
CHATGPT_URL="https://chat.openai.com/"

# Activate shared virtual environment
if [ -f "$SHARED_ROOT/scripts/activate.sh" ]; then
    source "$SHARED_ROOT/scripts/activate.sh"
else
    echo "✗ Error: Shared venv activation script not found"
    echo "  Expected: $SHARED_ROOT/scripts/activate.sh"
    exit 1
fi

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "✓ CDP browser already running (PID: $OLD_PID)"
        exit 0
    else
        echo "→ Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Also check via HTTP
if curl -s http://127.0.0.1:$CDP_PORT/json >/dev/null 2>&1; then
    echo "✓ CDP browser already running on port $CDP_PORT"
    echo "  Warning: No PID file found, but browser is responding"
    exit 0
fi

echo "🚀 Launching CDP browser with fresh AI sessions..."

# Ensure directories exist
mkdir -p "$PROFILE_DIR"
mkdir -p "$(dirname "$PID_FILE")"

# Get Playwright Chromium path
CHROMIUM_PATH=$(python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()" 2>/dev/null)

if [ -z "$CHROMIUM_PATH" ] || [ ! -f "$CHROMIUM_PATH" ]; then
    echo "✗ Error: Could not locate Playwright Chromium"
    echo "  Install with: playwright install chromium"
    exit 1
fi

echo "  Chromium: $CHROMIUM_PATH"
echo "  Profile: $PROFILE_DIR"
echo "  Opening fresh chat sessions for all AIs"

# Launch browser with fresh session tabs (no --restore-last-session)
"$CHROMIUM_PATH" \
  --remote-debugging-port=$CDP_PORT \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "$CLAUDE_URL" \
  "$GEMINI_URL" \
  "$CHATGPT_URL" 2>/dev/null &

BROWSER_PID=$!

# Save PID
echo "$BROWSER_PID" > "$PID_FILE"
echo "  PID: $BROWSER_PID (saved to $PID_FILE)"

# Wait for CDP to be ready
echo "→ Waiting for CDP endpoint..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:$CDP_PORT/json/version >/dev/null 2>&1; then
        echo "✓ CDP browser ready on port $CDP_PORT"
        
        # Get WebSocket URL
        WS_URL=$(curl -s http://127.0.0.1:$CDP_PORT/json/version | python3 -c "import sys, json; print(json.load(sys.stdin).get('webSocketDebuggerUrl', 'N/A'))" 2>/dev/null)
        
        if [ "$WS_URL" != "N/A" ]; then
            echo "  WebSocket: $WS_URL"
        fi
        
        echo ""
        echo "✓ Browser launched with fresh AI chat sessions"
        echo "  - Already logged in (cookies preserved)"
        echo "  - 3 new chat tabs ready to use"
        echo "  - Use StopCDP.sh to stop the browser"
        exit 0
    fi
    sleep 1
done

echo "✗ Error: CDP endpoint did not become ready after 15 seconds"
echo "  Browser may have crashed. Check process: ps -p $BROWSER_PID"
exit 1
