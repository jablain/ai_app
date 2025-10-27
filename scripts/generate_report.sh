#!/usr/bin/env bash
set -euo pipefail

# Thin wrapper to call the Python module living under src/tools/generate_report.py
# Usage examples:
#   scripts/generate_report.sh
#   scripts/generate_report.sh --chunk 2000
#   scripts/generate_report.sh --help

# Prefer repo-local Python if you have a venv activated; otherwise rely on python3 in PATH.
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Run from repo root if invoked elsewhere
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
exec "${PYTHON_BIN}" -m tools.generate_report "$@"

