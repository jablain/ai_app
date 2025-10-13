#!/bin/bash
# Create shared virtual environment and install both projects

set -e

BASE_DIR="$HOME/dev/ai_app"
VENV_DIR="$BASE_DIR/shared/runtime/venv"

echo "🐍 Setting up shared virtual environment"
echo ""

# Create venv with system site packages (for GTK)
echo "→ Creating venv at $VENV_DIR"
python3 -m venv --system-site-packages "$VENV_DIR"
echo "✓ Venv created"

# Activate
source "$VENV_DIR/bin/activate"

# Upgrade pip and build tools
echo "→ Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel
echo "✓ Build tools upgraded"

# Install ai-cli-bridge
echo "→ Installing ai-cli-bridge in editable mode..."
pip install -e "$BASE_DIR/ai-cli-bridge/src"
echo "✓ ai-cli-bridge installed"

# Install ai-chat-ui
echo "→ Installing ai-chat-ui in editable mode..."
pip install -e "$BASE_DIR/ai-chat-ui/src"
echo "✓ ai-chat-ui installed"

# Verify installations
echo ""
echo "📦 Installed packages:"
pip list | grep -E "ai-cli-bridge|ai-chat-ui|playwright"

echo ""
echo "🔧 Executables available:"
which ai-cli-bridge
which ai-chat-ui

echo ""
echo "✅ Virtual environment ready!"
echo ""
echo "To activate:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or use the helper script:"
echo "  source ~/dev/ai_app/shared/scripts/activate.sh"
