#!/bin/bash
# Stop CDP browser gracefully
# Part of ai-cli-bridge daemon system

set -e

# Configuration
PROJECT_ROOT="$HOME/dev/ai_app/ai-cli-bridge"
PID_FILE="$PROJECT_ROOT/runtime/browser.pid"

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "✗ No PID file found at $PID_FILE"
    echo "  Browser may not be running, or was started manually"
    exit 1
fi

# Read PID
BROWSER_PID=$(cat "$PID_FILE")

# Check if process exists
if ! kill -0 "$BROWSER_PID" 2>/dev/null; then
    echo "✗ Browser process (PID: $BROWSER_PID) is not running"
    echo "→ Removing stale PID file"
    rm -f "$PID_FILE"
    exit 1
fi

echo "🛑 Stopping CDP browser (PID: $BROWSER_PID)..."

# Send SIGTERM for graceful shutdown
kill -TERM "$BROWSER_PID"

# Wait for process to exit (max 10 seconds)
for i in {1..10}; do
    if ! kill -0 "$BROWSER_PID" 2>/dev/null; then
        echo "✓ Browser stopped successfully"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# If still running after 10 seconds, force kill
echo "⚠ Browser did not stop gracefully, forcing..."
kill -9 "$BROWSER_PID" 2>/dev/null || true

# Wait a bit more
sleep 1

if ! kill -0 "$BROWSER_PID" 2>/dev/null; then
    echo "✓ Browser stopped (forced)"
    rm -f "$PID_FILE"
    exit 0
else
    echo "✗ Error: Could not stop browser process"
    exit 1
fi
