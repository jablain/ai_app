#!/bin/bash
# Launch Playwright Chromium with session restoration
# All AI sites in one browser, Claude automated via CDP

source ~/.ai_cli_bridge/venv/bin/activate

# Check if already running
if curl -s http://127.0.0.1:9223/json >/dev/null 2>&1; then
    echo "✓ CDP browser already running on port 9223"
    exit 0
fi

echo "🚀 Launching Playwright Chromium with saved session..."

CHROMIUM_PATH=$(python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()")

"$CHROMIUM_PATH" \
  --remote-debugging-port=9223 \
  --user-data-dir=/home/jacques/.ai_cli_bridge/data/profiles/claude \
  --restore-last-session \
  --no-first-run \
  --no-default-browser-check &

# Wait for CDP
echo "→ Waiting for CDP..."
for i in {1..10}; do
    if curl -s http://127.0.0.1:9223/json >/dev/null 2>&1; then
        echo "✓ Browser ready - all tabs restored!"
        break
    fi
    sleep 1
done
