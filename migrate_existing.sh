#!/bin/bash
# Migrate existing ai-cli-bridge and ai-chat-ui to unified structure
# SAFE: Creates backups before moving anything

set -e

BASE_DIR="$HOME/dev/ai_app"
BACKUP_DIR="$HOME/dev/ai_app_backup_$(date +%Y%m%d_%H%M%S)"

echo "🔄 Migrating existing projects to unified structure"
echo ""

# Verify source directories exist
if [ ! -d "$HOME/dev/ai-cli-bridge" ]; then
    echo "❌ Error: ~/dev/ai-cli-bridge not found"
    exit 1
fi

if [ ! -d "$HOME/dev/ai-chat-ui" ]; then
    echo "❌ Error: ~/dev/ai-chat-ui not found"
    exit 1
fi

# Create backup
echo "📦 Creating backup at $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp -r "$HOME/dev/ai-cli-bridge" "$BACKUP_DIR/" 2>/dev/null || true
cp -r "$HOME/dev/ai-chat-ui" "$BACKUP_DIR/" 2>/dev/null || true
cp -r "$HOME/.ai_cli_bridge" "$BACKUP_DIR/" 2>/dev/null || true
echo "✓ Backup created"
echo ""

# Migrate ai-cli-bridge source
echo "→ Migrating ai-cli-bridge source code..."
cp -r "$HOME/dev/ai-cli-bridge"/* "$BASE_DIR/ai-cli-bridge/src/" 2>/dev/null || true
# Move LaunchCDP.sh to shared scripts
if [ -f "$HOME/dev/ai-cli-bridge/LaunchCDP.sh" ]; then
    mv "$HOME/dev/ai-cli-bridge/LaunchCDP.sh" "$BASE_DIR/shared/scripts/" 2>/dev/null || true
fi
echo "✓ ai-cli-bridge source migrated"

# Migrate ai-cli-bridge runtime data
echo "→ Migrating ai-cli-bridge runtime data..."
if [ -d "$HOME/.ai_cli_bridge/data/profiles/claude" ]; then
    echo "  → Copying browser profile (THIS IS YOUR VALUABLE DATA)"
    cp -r "$HOME/.ai_cli_bridge/data/profiles/claude" "$BASE_DIR/ai-cli-bridge/runtime/profiles/main"
    
    # Verify cookies were copied
    if [ -f "$BASE_DIR/ai-cli-bridge/runtime/profiles/main/Default/Cookies" ]; then
        SIZE=$(du -h "$BASE_DIR/ai-cli-bridge/runtime/profiles/main/Default/Cookies" | cut -f1)
        echo "  ✓ Cookies copied (${SIZE})"
    fi
fi

if [ -d "$HOME/.ai_cli_bridge/logs" ]; then
    cp -r "$HOME/.ai_cli_bridge/logs"/* "$BASE_DIR/ai-cli-bridge/runtime/logs/" 2>/dev/null || true
fi
echo "✓ ai-cli-bridge runtime migrated"

# Migrate ai-chat-ui source
echo "→ Migrating ai-chat-ui source code..."
cp -r "$HOME/dev/ai-chat-ui"/* "$BASE_DIR/ai-chat-ui/src/" 2>/dev/null || true
echo "✓ ai-chat-ui source migrated"

echo ""
echo "✅ Migration complete!"
echo ""
echo "Your data is safe in:"
echo "  Backup:      $BACKUP_DIR"
echo "  New location: $BASE_DIR"
echo ""
echo "Next steps:"
echo "  1. Run setup_venv.sh to create shared virtual environment"
echo "  2. Verify your browser profile at: $BASE_DIR/ai-cli-bridge/runtime/profiles/main/"
