#!/bin/bash
# gather_source.sh - Gather complete AI-CLI-Bridge project tree and source code

set -e

PROJECT_ROOT="$HOME/dev/ai_app/ai-cli-bridge"
OUTPUT_FILE="src.txt"

# Check if project directory exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: Project directory not found at $PROJECT_ROOT"
    exit 1
fi

cd "$PROJECT_ROOT"

# Start fresh
: > "$OUTPUT_FILE"

echo "Gathering AI-CLI-Bridge project source code..."

# Header
cat >> "$OUTPUT_FILE" << EOF
================================================================================
AI-CLI-BRIDGE v2.0.0 - COMPLETE SOURCE CODE DUMP
================================================================================
Generated: $(date)
Project Root: $(pwd)
================================================================================

EOF

# Section 1: Project Tree (EXCLUDING runtime/)
echo "==> Generating project tree..."
cat >> "$OUTPUT_FILE" << EOF

################################################################################
# SECTION 1: PROJECT DIRECTORY TREE
################################################################################

EOF

if command -v tree >/dev/null 2>&1; then
    tree -a -I 'runtime|__pycache__|*.pyc|.git|*.egg-info|dist|build|.pytest_cache|.mypy_cache' >> "$OUTPUT_FILE"
else
    find . -not -path '*/\.*' -not -path '*/__pycache__/*' -not -path '*/runtime/*' \
        -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/*.egg-info/*' \
        -print | sort >> "$OUTPUT_FILE"
fi

# Section 2: Source Code Files
echo "==> Gathering source code files..."
cat >> "$OUTPUT_FILE" << EOF


################################################################################
# SECTION 2: SOURCE CODE FILES
################################################################################

EOF

# Function to add file to output
add_file() {
    local filepath="$1"

    echo "" >> "$OUTPUT_FILE"
    echo "================================================================================" >> "$OUTPUT_FILE"
    echo "FILE: $filepath" >> "$OUTPUT_FILE"
    echo "================================================================================" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"

    cat "$filepath" >> "$OUTPUT_FILE"

    echo "" >> "$OUTPUT_FILE"
}

# Gather Python source files from src/
echo "  - Python source files..."
if [ -d "src/ai_cli_bridge" ]; then
    find src/ai_cli_bridge -name "*.py" -type f | sort | while read -r file; do
        add_file "$file"
    done
fi

# Gather configuration files
echo "  - Configuration files..."
for file in pyproject.toml README.md usermanual.md; do
    if [ -f "src/$file" ]; then
        add_file "src/$file"
    elif [ -f "$file" ]; then
        add_file "$file"
    fi
done

# Gather shell script
echo "  - Shell scripts..."
if [ -f "src/ai_cli_bridge/LaunchCDP.sh" ]; then
    add_file "src/ai_cli_bridge/LaunchCDP.sh"
fi

# Section 3: Statistics
echo "==> Generating statistics..."
cat >> "$OUTPUT_FILE" << EOF


################################################################################
# SECTION 3: PROJECT STATISTICS
################################################################################

File Count by Type:
-------------------
Python files:    $(find src -name '*.py' -type f 2>/dev/null | wc -l)
Config files:    $(ls src/pyproject.toml src/README.md 2>/dev/null | wc -l)
Shell scripts:   $(find src -name '*.sh' -type f 2>/dev/null | wc -l)

Lines of Code:
--------------
EOF

find src -name "*.py" -type f -exec wc -l {} + 2>/dev/null | tail -1 >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << EOF

Module Breakdown:
-----------------
EOF

for dir in src/ai_cli_bridge/*/; do
    if [ -d "$dir" ]; then
        module=$(basename "$dir")
        count=$(find "$dir" -name "*.py" -type f -exec cat {} \; 2>/dev/null | wc -l)
        printf "%-20s %s lines\n" "$module:" "$count" >> "$OUTPUT_FILE"
    fi
done

# Footer
cat >> "$OUTPUT_FILE" << EOF


################################################################################
# END OF SOURCE CODE DUMP
################################################################################
EOF

# Summary
echo ""
echo "✓ Source code gathered successfully!"
echo ""
echo "Output file: $OUTPUT_FILE"
echo "File size:   $(du -h "$OUTPUT_FILE" | cut -f1)"
echo "Total lines: $(wc -l < "$OUTPUT_FILE")"
echo ""
echo "Next steps:"
echo "  - Review the file: less $OUTPUT_FILE"
echo "  - Share with Claude for analysis"
