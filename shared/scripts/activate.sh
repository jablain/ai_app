#!/bin/bash
# Quick helper to activate the shared venv
# Usage: source ~/dev/ai_app/shared/scripts/activate.sh

VENV_DIR="$HOME/dev/ai_app/shared/runtime/venv"

if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo "✓ Activated shared venv"
    echo "  ai-cli-bridge: $(which ai-cli-bridge)"
    echo "  ai-chat-ui:    $(which ai-chat-ui)"
else
    echo "❌ Venv not found at $VENV_DIR"
    echo "Run setup_venv.sh first"
fi
