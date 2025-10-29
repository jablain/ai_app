#!/bin/bash
# Quick helper to activate the shared venv
# Usage: source ~/dev/ai_app/scripts/activate.sh

VENV_DIR="$HOME/dev/ai_app/.venv"

if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo "✓ Activated venv"
    echo "  ai-cli-bridge: $(which ai-cli-bridge)"
    echo "  ai-chat-ui:    $(which ai-chat-ui)"
else
    echo "❌ Venv not found at $VENV_DIR"
    echo "  Expected: $VENV_DIR/bin/activate"
    exit 1
fi
