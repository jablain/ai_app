#!/bin/bash
# Create unified ai_app directory structure
# Run this first to create the skeleton

set -e

echo "🏗️  Creating unified AI app structure at ~/dev/ai_app"

BASE_DIR="$HOME/dev/ai_app"

# Create main structure
mkdir -p "$BASE_DIR"/{ai-cli-bridge,ai-chat-ui,shared,docs}

# ai-cli-bridge project
mkdir -p "$BASE_DIR/ai-cli-bridge"/{src,runtime}
mkdir -p "$BASE_DIR/ai-cli-bridge/runtime"/{profiles/main,logs,cache}

# ai-chat-ui project
mkdir -p "$BASE_DIR/ai-chat-ui"/{src,runtime}
mkdir -p "$BASE_DIR/ai-chat-ui/runtime"/{logs,config}

# Shared resources
mkdir -p "$BASE_DIR/shared"/{runtime,scripts}

echo "✓ Directory structure created"
echo ""
echo "Structure:"
tree -L 3 "$BASE_DIR" 2>/dev/null || find "$BASE_DIR" -type d | sed 's|[^/]*/| |g'

echo ""
echo "Next: Run migrate_existing.sh to move your current setup"
