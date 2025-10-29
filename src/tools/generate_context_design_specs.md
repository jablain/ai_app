Complete Description of generate_context.py
Purpose
A Python command-line tool that scans a directory tree and generates multi-file, chunked plain-text "context packs" that can be pasted into AI chat sessions. This gives an AI complete understanding of a Python codebase without needing internet or repository access.
Core Functionality
What It Does

Scans a directory tree (Python code + config files)
Collects relevant files (filtering out binaries, caches, build artifacts)
Chunks the content into multiple numbered text files respecting a line limit
Packages everything with:

A preface explaining delivery mechanics to the AI
Clear file boundary markers (--- BEGIN FILE: path --- / --- END FILE: path ---)
Python file outlines (imports/classes/functions) for quick scanning
Optional directory tree for orientation
A final instruction line in the last chunk



Output Structure
<output-location>/
└── context_reports/
    ├── YYYYMMDD_HHMMSS/
    │   ├── chunk_0001.txt
    │   ├── chunk_0002.txt
    │   ├── ...
    │   ├── chunk_NNNN.txt
    │   └── MANIFEST.json
    └── latest -> YYYYMMDD_HHMMSS/  (symlink)
Command-Line Interface
Basic Usage
bashgenerate_context [OPTIONS]
```

### Key Options

**Content Control:**
- `--chunk N` - Max lines per chunk (default: 1500, minimum: 200)
- `--max-file-bytes N` - Skip files larger than N bytes (default: 300000)
- `--include-tests` - Include test directories (excluded by default)
- `--no-tree` - Exclude directory tree from output

**Discovery Modes (determines what to scan):**
- No flag (default) - Scan exactly current directory
- `--discover project` - Find and scan project root (has `pyproject.toml` or `.git`)
- `--discover module` - Find and scan module root (highest directory with `__init__.py`)

**Output Location (determines where to write):**
- No flag (default) - Write under scan root
- `--to-project-root` - Write under project root
- `--to-module-root` - Write under module root

**Template Customization:**
- `--preface-file PATH` - Custom preface text (supports `{chunk_count}` placeholder)
- `--suffix-file PATH` - Custom suffix text

**Other:**
- `--dry-run` - Don't write files, just show preview and stats
- `--help` - Show all options

### Discovery Logic
The spec requires: "First evaluate the current directory; if it already qualifies, use it. Otherwise walk upward appropriately."

For `--discover project`:
- If cwd has `pyproject.toml` or `.git` → use cwd
- Else walk up to find project root → use that
- Else use cwd with warning

For `--discover module`:
- If cwd has `__init__.py` → check if there's a higher module root
- Walk up while `__init__.py` exists, track the highest package directory
- Use the highest package found
- Else use cwd with warning

## File Selection Rules

### Always Included (if not in exclusion list)
- Python: `.py`
- Documentation: `.md`, `.rst`, `.txt`
- Config: `.toml`, `.ini`, `.cfg`, `.yml`, `.yaml`, `.json`
- Shell: `.sh`
- Other: `.service`, `.desktop`, `.sql`, `.csv`, `.tsv`, `.xml`, `.conf`, `.properties`, `.env`

### Always Excluded Directories
`.git`, `context_reports`, `project_reports`, `__pycache__`, `.venv`, `venv`, `env`, `build`, `dist`, `.tox`, `.nox`, `node_modules`, `.ruff_cache`, `.mypy_cache`, `.pytest_cache`, `.cache`, `.idea`, `.vscode`

### File Processing Order
1. **Priority repo metadata** (if in scan root): `pyproject.toml`, `Makefile`, `setup.py`, `setup.cfg`, `requirements.txt`
2. **Optional directory tree** (conditional or forced via flags)
3. **All other files** (depth-first, lexicographically sorted within each directory)

## Output Format

### Chunk Structure
Each `chunk_NNNN.txt` contains plain text with:

**Chunk 1 only - Preface:**
```
==================
AI CONTEXT PREFACE
==================
Generated at: <ISO timestamp>
Project root: <path or "(unknown)">

<Custom or default preface text with instructions>

--- END PREFACE ---

Scan root: <absolute path>
```

**All chunks - File blocks:**
```
--- BEGIN FILE: relative/path/to/file.py ---
# imports=..., classes=..., defs=...  (Python files only)
<file contents>
--- END FILE: relative/path/to/file.py ---
```

**Last chunk only - Suffix:**
```
<Custom or default suffix text: "Await further instructions !!">
Python File Outlines
Before each .py file's contents, a one-line comment shows:

imports= - Top-level imports (comma-separated, max 12)
classes= - Class names (comma-separated, max 20)
defs= - Top-level function names (comma-separated, max 25)

MANIFEST.json
Contains metadata:
json{
  "scan_root": "/absolute/path",
  "output_dir": "/absolute/path/to/output",
  "total_lines": 12345,
  "chunk_lines": 1500,
  "chunks": [
    {
      "filename": "chunk_0001.txt",
      "sha256": "abc123...",
      "line_count": 1500,
      "byte_count": 87432
    }
  ],
  "generated_at": "2025-10-29T12:00:00-04:00",
  "project_root": "/path/or/null",
  "module_root": "/path/or/null"
}
```

## Implementation Details

### Key Functions

**Discovery:**
- `discover_project_root(start)` - Walk up finding `pyproject.toml` or `.git`
- `discover_module_root(start)` - Walk up while `__init__.py` exists, return highest package dir

**File Handling:**
- `collect_files(scan_root, include_tests)` - Walk tree, filter by exclusions and extensions
- `read_text_file(path, max_bytes)` - Safely read file, return lines or None if too large/unreadable
- `python_one_line_outline(lines)` - Parse Python file for imports/classes/functions

**Content Assembly:**
- `build_body_lines(...)` - Assemble priority files + tree + all files into line list
- `chunk_by_lines(lines, chunk_lines)` - Split lines into chunks respecting max size
- `make_preface_lines(...)` - Generate preface with custom or default text
- `add_final_suffix(...)` - Append custom or default suffix to last chunk
- `chunk_with_preface_and_suffix(...)` - Orchestrate chunking with preface/suffix

**Output:**
- `ensure_reports_dir(base)` - Create timestamped output dir + `latest` symlink
- `write_chunks_and_manifest(...)` - Write all chunk files + MANIFEST.json

### Default Text Templates

**Default Preface:**
```
You are an AI assistant. You are receiving a multi-part, plain-text context that
serves as the single source of truth for this codebase. Use it for navigation,
analysis, refactoring, bug fixing, packaging, and related development tasks.

Delivery: This context is split into {chunk_count} chunk(s) named chunk_0001.txt …
up to chunk_{chunk_count:04d}.txt. You are reading chunk 1 of {chunk_count}.

Instructions:
  1) Use only the information in this context unless explicitly provided more.
  2) When the last chunk (chunk_{chunk_count:04d}.txt) arrives, wait
     for further instructions before acting.
  3) Respect file boundaries marked as:
         --- BEGIN FILE: <path> ---
         --- END FILE: <path> ---
  4) Python files include a one-line outline of imports/classes/functions to speed scanning.
```

**Default Suffix:**
```
Await further instructions !!
Error Handling
Exit Codes:

0 = Success
2 = Invalid arguments or file access errors
3 = Output directory creation failure
4 = Scan root invalid
7 = Internal exception

Critical Bugs Fixed During Development
Bug 1: Wrapper Script Changed Working Directory
Problem: The bash wrapper script did cd "$REPO_ROOT" before running Python, causing Path.cwd() to return project root instead of where the user ran the command.
Fix: Removed cd from wrapper, set PYTHONPATH instead.
Bug 2: Module Discovery Logic Inverted
Problem: discover_module_root() broke on first directory without __init__.py instead of continuing upward.
Fix: Continue walking up, track last directory with __init__.py, stop when hitting one without (after finding some with it).
Bug 3: stat_result Doesn't Have is_file() Method
Problem: Code called st.is_file() on an os.stat_result object, which doesn't have this method.
Fix: Check path.is_file() before calling stat(), not after.
Testing Scenarios Validated

✅ Default (scan current dir, output to current dir)
✅ --discover project (scan project root)
✅ --discover module (scan module root)
✅ --to-project-root (output to project root while scanning current)
✅ --to-module-root (output to module root while scanning current)
✅ Combined flags work correctly
✅ Custom preface/suffix files with {chunk_count} substitution
✅ Dry-run mode shows accurate preview

Current Known Issue
The directory tree is not appearing in output despite include_tree=True by default. Investigation ongoing - tree generation code exists and should execute, but output shows files without the tree section that should precede them.Retry
