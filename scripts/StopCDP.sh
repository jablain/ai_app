#!/bin/bash
# Stop CDP browser gracefully
# Part of ai-cli-bridge daemon system
set -euo pipefail

# Configuration
PROJECT_ROOT="$HOME/dev/ai_app"
PID_FILE="$PROJECT_ROOT/runtime/daemon/browser/browser.pid"
PROFILE_DIR="$PROJECT_ROOT/runtime/daemon/browser/profiles/multi_ai_cdp"

echo "🛑 Stopping CDP browser..."

# Kill all chromium processes using our specific profile
# This is safe because only our CDP browser uses this profile path
pkill -f "user-data-dir=$PROFILE_DIR" 2>/dev/null || true

# Wait for processes to stop (max 5 seconds)
for i in {1..5}; do
    COUNT=$(ps aux | grep -F "user-data-dir=$PROFILE_DIR" | grep -v grep | wc -l)
    if [ "$COUNT" -eq 0 ]; then
        echo "✓ Browser stopped successfully"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
echo "⚠ Forcing browser shutdown..."
pkill -9 -f "user-data-dir=$PROFILE_DIR" 2>/dev/null || true
sleep 1

# Final check
COUNT=$(ps aux | grep -F "user-data-dir=$PROFILE_DIR" | grep -v grep | wc -l)
if [ "$COUNT" -eq 0 ]; then
    echo "✓ Browser stopped (forced)"
    rm -f "$PID_FILE"
    exit 0
else
    echo "✗ Error: Could not stop browser"
    exit 1
fi
