#!/bin/bash
# Launch Playwright Chromium with session restoration

source ~/.ai_cli_bridge/venv/bin/activate

# Check if already running
if curl -s http://127.0.0.1:9223/json >/dev/null 2>&1; then
    echo "✓ CDP browser already running on port 9223"
    exit 0
fi

echo "🚀 Launching Playwright Chromium with saved session..."

CHROMIUM_PATH=$(python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()")

# CORRECT profile path - must match your existing CDP profile!
PROFILE_DIR="/home/jacques/.ai_cli_bridge/data/profiles/claude_cdp_pw"

# Ensure profile directory exists
mkdir -p "$PROFILE_DIR"

"$CHROMIUM_PATH" \
  --remote-debugging-port=9223 \
  --user-data-dir="$PROFILE_DIR" \
  --restore-last-session \
  --no-first-run \
  --no-default-browser-check &

# Wait for CDP
echo "→ Waiting for CDP..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:9223/json >/dev/null 2>&1; then
        echo "✓ Browser ready!"
        break
    fi
    sleep 1
done
