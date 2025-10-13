#!/bin/bash
# Launch Playwright Chromium with CDP for all AIs
# Single browser, multiple tabs, one profile

set -e

BASE_DIR="$HOME/dev/ai_app"
VENV_DIR="$BASE_DIR/shared/runtime/venv"
PROFILE_DIR="$BASE_DIR/ai-cli-bridge/runtime/profiles/main"

# Check if already running
if curl -s http://127.0.0.1:9223/json >/dev/null 2>&1; then
    echo "✓ CDP browser already running on port 9223"
    exit 0
fi

echo "🚀 Launching Playwright Chromium with CDP..."

# Activate venv to get Playwright
source "$VENV_DIR/bin/activate"

# Get Playwright Chromium path
CHROMIUM_PATH=$(python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()")

echo "  → Chromium: $CHROMIUM_PATH"
echo "  → Profile:  $PROFILE_DIR"
echo "  → CDP Port: 9223"

# Ensure profile directory exists
mkdir -p "$PROFILE_DIR"

# Launch browser
"$CHROMIUM_PATH" \
  --remote-debugging-port=9223 \
  --user-data-dir="$PROFILE_DIR" \
  --restore-last-session \
  --no-first-run \
  --no-default-browser-check \
  --restore-on-startup=5 &

BROWSER_PID=$!

# Wait for CDP to be ready
echo "→ Waiting for CDP..."
for i in {1..15}; do
    if curl -s http://127.0.0.1:9223/json >/dev/null 2>&1; then
        echo "✓ Browser ready (PID: $BROWSER_PID)"
        echo ""
        echo "Open tabs for:"
        echo "  - https://claude.ai"
        echo "  - https://chat.openai.com"
        echo "  - https://gemini.google.com"
        echo ""
        echo "Authenticate in each tab, then use:"
        echo "  ai-cli-bridge status claude"
        echo "  ai-chat-ui"
        exit 0
    fi
    sleep 1
done

echo "⚠️  Timeout waiting for CDP"
exit 1
