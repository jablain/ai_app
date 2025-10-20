#!/bin/bash
# Remove all V1.3.1 remnants and obsolete files from ai-cli-bridge V2.0.0

set -e

# Navigate to project source directory
cd ~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge

echo "🗑️  Removing V1.3.1 remnants and obsolete files..."

# Delete V1.3.1 core files
echo "  → Removing browser_manager.py (V1.3.1 browser launch logic)"
rm -f browser_manager.py

echo "  → Removing lock_manager.py (daemon has internal locks)"
rm -f lock_manager.py

echo "  → Removing display.py (daemon doesn't need display checks)"
rm -f display.py

echo "  → Removing errors.py (unnecessary abstraction)"
rm -f errors.py

echo "  → Removing config.py (replaced by daemon/config.py)"
rm -f config.py

# Delete obsolete commands
echo "  → Removing commands/init_cmd.py (no per-AI init needed)"
rm -f commands/init_cmd.py

echo "  → Removing commands/open_cmd.py (browser opened externally)"
rm -f commands/open_cmd.py

echo "  → Removing commands/doctor_cmd.py (optional diagnostics)"
rm -f commands/doctor_cmd.py

# Also clean up LaunchCDP.sh from inside src (it should be at project root only)
if [ -f "LaunchCDP.sh" ]; then
    echo "  → Removing LaunchCDP.sh from src/ (should be at project root)"
    rm -f LaunchCDP.sh
fi

echo ""
echo "✅ Cleanup complete! Removed 8-9 obsolete files."
echo ""
echo "⚠️  IMPORTANT: You must now fix the following files:"
echo "   1. cli.py - Remove imports and commands for deleted files"
echo "   2. commands/init_cdp_cmd.py - Remove config.py and errors.py imports"
echo ""
echo "Run these commands to verify the package structure:"
echo "   tree -I '__pycache__|*.pyc' ~/dev/ai_app/ai-cli-bridge/src/ai_cli_bridge"
echo "   python3 -c 'import ai_cli_bridge' # Will FAIL until you fix imports"
