🧭 Purpose

A general-purpose development tool that generates chunked AI-readable context reports for any portion of your codebase.
Used to inject project or module context into a new AI session for comprehension, analysis, or refactoring.

⚙️ Core Behavior
Starting point

Default: starts at the current working directory (CWD).
→ Includes everything of relevance under that directory only.

Optional discovery modes:

--discover-project: walk upward until a project root is found (.git, pyproject.toml, setup.cfg, etc.).

--discover-module: walk upward until a module root is found (highest directory with __init__.py, or a src/ boundary).

If both flags are given: --discover-module takes precedence.

You can always override explicitly with --root PATH.

📂 Output location

Default output prefix:

<chosen-root>/context_reports/<YYYYMMDD_HHMMSS>/


A symlink context_reports/latest points to the most recent run.

You can override with:

--output-dir /custom/path


The tool creates the directory tree automatically.

All report folders (context_reports/) are excluded from scanning to prevent recursion.

🧱 File structure

Example:

context_reports/
└── 20251027_214512/
    ├── chunk_0001.txt
    ├── chunk_0002.txt
    ├── chunk_0003.txt
    └── MANIFEST.json


Each run produces timestamped chunks + a MANIFEST.json containing:

root path

generation timestamp

number of chunks

chunk size

SHA-256 per file

discovery mode used

🪶 Report composition
Preface (always at the top of chunk_0001.txt)
=========================
AI CONTEXT REPORT PREFACE
=========================
Generated at: <timestamp>
Root directory: <absolute path of chosen root>
Output prefix: <path to this report folder>
Chunk size: <lines per chunk>
Total chunks: <N>

Purpose:
  This report provides complete Python source context for the given directory tree.
  It is designed for injection into a new AI session so the assistant can
  fully understand the codebase before performing any operations.

Instructions to the assistant:
  1) Use only the information contained in these report files.
  2) Do not infer or assume context outside what is shown here.
  3) Wait for explicit confirmation from the user after receiving the final chunk
     before taking *any* action.
  4) File boundaries are marked as:
         --- BEGIN FILE: <path> ---
         --- END FILE: <path> ---
  5) Directory trees and metadata may be omitted if unnecessary for comprehension.

Delivery:
  This report is split into <N> chunk(s) named chunk_0001.txt ... chunk_<N>.txt.
  You are reading chunk 1 of <N>.

--- END PREFACE ---

Sections

PROJECT METADATA — timestamp, Python version, root, options used.

(Optional) DIRECTORY TREE — only included if it meaningfully aids comprehension:

Auto-enabled for medium-sized trees.

Skipped for small or massive trees.

Manual override: --force-tree or --no-tree.

FILE CONTENTS — every relevant text file under the root, bounded by:

--- BEGIN FILE: path/to/file.py ---
# Outline: imports/classes/functions (for .py)
<source lines>
--- END FILE: path/to/file.py ---

Final line of last chunk
Await further instructions !!

🧰 Options (CLI interface)
Flag	Description	Default
--root PATH	Explicit start directory	CWD
--discover-project	Walk up to project root	off
--discover-module	Walk up to module root	off
--chunk N	Lines per output chunk	1500
--include-tests	Include test files	off
--include-dotfiles	Include hidden files	off
--max-file-bytes N	Skip files larger than this	350 000
--force-tree / --no-tree	Force include or exclude directory tree	auto
--output-dir PATH	Override output base folder	<root>/context_reports/
--dry-run	Don’t write files, just show summary	off
--redact PATTERN	Optional custom redactions	none
--redact-env	Hide env-style secrets (KEY=VALUE)	off
🧩 Inclusion rules
Included by default

Python (.py), Markdown, reStructuredText, TOML, INI, YAML, JSON, text files.

Shell scripts and basic config files.

Only files within the chosen root (never climbs up).

Excluded always

context_reports/, project_reports/

.git/, __pycache__/, .venv/, .tox/, .nox/, .mypy_cache/, .ruff_cache/, .pytest_cache/, .idea/, .vscode/, node_modules/, dist/, build/, .cache/

Hidden dot-directories unless --include-dotfiles

Binary or huge files (per --max-file-bytes)

🛡️ Safety / redaction

By default, the tool does not redact content beyond skipping obviously sensitive files (.env, *.pem, etc.).

Optional user-driven redaction rules via --redact and --redact-env.

No automatic “guessing” redaction patterns unless requested.

🧮 Chunking logic

Lines are grouped sequentially up to the --chunk limit.

Preface counts toward total line count.

MANIFEST.json is always written last, not chunked.
