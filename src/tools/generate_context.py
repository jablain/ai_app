#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, List, Optional

# ============================================================
# Configuration knobs (safe defaults)
# ============================================================

DEFAULT_CHUNK_LINES = 1500
DEFAULT_MAX_FILE_BYTES = 300_000  # skip unusually large text files

# Default preface and suffix text
DEFAULT_PREFACE_TEXT = """You are an AI assistant. You are receiving a multi-part, plain-text context that
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
  4) Python files include a one-line outline of imports/classes/functions to speed scanning."""

DEFAULT_SUFFIX_TEXT = "Await further instructions !!"

CONTEXT_DIRNAME = "context_reports"
TIMESTAMP_FMT = "%Y%m%d_%H%M%S"
CHUNK_PREFIX = "chunk_"
CHUNK_SUFFIX = ".txt"
MANIFEST_NAME = "MANIFEST.json"
LATEST_SYMLINK = "latest"

# Exclusions for tree walk
TREE_EXCLUDES = {
    ".git",
    CONTEXT_DIRNAME,  # always exclude context outputs
    "project_reports",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".tox",
    ".nox",
    "node_modules",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".cache",
    ".idea",
    ".vscode",
}

# Extensions considered text; others skipped unless tiny (still skipped by default)
TEXT_EXTS = {
    ".py",
    ".md",
    ".toml",
    ".txt",
    ".ini",
    ".cfg",
    ".yml",
    ".yaml",
    ".json",
    ".sh",
    ".rst",
    ".xml",
    ".csv",
    ".tsv",
    ".conf",
    ".properties",
    ".env",
    ".desktop",
    ".service",
    ".sql",
}

# ============================================================
# Helpers
# ============================================================


def is_text_ext(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTS


def read_text_file(path: Path, max_bytes: int) -> Optional[List[str]]:
    """
    Safely read a text-ish file into lines.
    Skip if too large or unreadable.
    """
    try:
        if not path.is_file():
            return None
        st = path.stat()
        if st.st_size > max_bytes:
            return None
        # Try text decode
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        return text.splitlines()
    except Exception:
        return None


def safe_relpath(p: Path, base: Path) -> str:
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_dir(p: Path) -> Path:
    return p.expanduser().resolve()


def load_text_file_or_default(file_path: Optional[str], default_text: str) -> str:
    """
    Load text from a file if provided, otherwise return the default text.
    """
    if file_path is None:
        return default_text

    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            print(f"Error: specified file does not exist: {file_path}", file=sys.stderr)
            sys.exit(2)
        if not path.is_file():
            print(f"Error: specified path is not a file: {file_path}", file=sys.stderr)
            sys.exit(2)

        return path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(2)


def should_skip_dir(name: str) -> bool:
    if name in TREE_EXCLUDES:
        return True
    if name.startswith(".") and name not in {".github"}:
        # skip generic hidden dirs, keep .github as it may have workflows
        return True
    return False


def discover_project_root(start: Path) -> Optional[Path]:
    """
    Project root: a directory containing pyproject.toml OR .git.
    Walk up; return first match. None if not found.
    """
    cur = normalize_dir(start)
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    return None


def discover_module_root(start: Path) -> Optional[Path]:
    """
    Module root: walk upward while __init__.py exists in each directory.
    Return the LAST (highest) directory that contained __init__.py before
    encountering a directory without one.

    Spec: "find the module root (walk up while __init__.py exists; root is
    first directory without __init__.py, using the last one that had it)"
    """
    cur = normalize_dir(start)
    last_with_init: Optional[Path] = None

    # Walk upward through the hierarchy
    for p in [cur, *cur.parents]:
        if (p / "__init__.py").exists():
            last_with_init = p  # Keep tracking the highest package dir
        elif last_with_init is not None:
            # We've hit a directory without __init__.py after finding some with it
            # Return the last valid package directory
            break

    return last_with_init


# ============================================================
# Outline (for Python files)
# ============================================================


def python_one_line_outline(lines: List[str]) -> str:
    """
    Produce a compact one-line outline from import/class/def statements.
    """
    imports: List[str] = []
    defs: List[str] = []
    classes: List[str] = []

    imp_re = re.compile(r"^\s*(from\s+\S+\s+import\s+\S+|import\s+\S+)")
    def_re = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(")
    cls_re = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*(\(|:)")

    for ln in lines:
        if len(imports) < 12:
            m = imp_re.match(ln)
            if m:
                # Show first token of import for brevity
                tok = m.group(1)
                imports.append(tok.strip())
        m = def_re.match(ln)
        if m:
            defs.append(m.group(1))
        m = cls_re.match(ln)
        if m:
            classes.append(m.group(1))

    parts: List[str] = []
    if imports:
        parts.append("imports=" + ",".join(imports[:12]))
    if classes:
        parts.append("classes=" + ",".join(classes[:20]))
    if defs:
        parts.append("defs=" + ",".join(defs[:25]))

    return " | ".join(parts) if parts else ""


# ============================================================
# Directory Tree (optional)
# ============================================================


def iter_filtered_tree(root: Path) -> Iterator[str]:
    """
    Lightweight ASCII tree for orientation. Respects exclusions.
    """
    root = normalize_dir(root)
    yield "."
    for entry in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if should_skip_dir(entry.name):
            continue
        yield from _tree_walk(entry, prefix="")


def _tree_walk(path: Path, prefix: str) -> Iterator[str]:
    name = path.name
    if path.is_dir():
        if should_skip_dir(name):
            return
        children = [
            p
            for p in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            if not should_skip_dir(p.name)
        ]
        yield f"{prefix}{name}/"
        new_prefix = prefix
        for child in children:
            yield from _tree_walk(child, prefix=new_prefix + "  ")
    else:
        yield f"{prefix}{name}"


# ============================================================
# Content harvesting
# ============================================================


def collect_files(scan_root: Path, include_tests: bool) -> List[Path]:
    """
    Depth-first collection of files (filtered).
    """
    scan_root = normalize_dir(scan_root)
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        # Filter dirnames in-place for os.walk
        pruned: List[str] = []
        for d in dirnames:
            if should_skip_dir(d):
                continue
            # optionally skip tests when not requested
            if not include_tests and d.lower() in {"tests", "test"}:
                continue
            pruned.append(d)
        dirnames[:] = pruned

        # files
        for fname in filenames:
            # skip dotfiles except .envrc (explicitly allowed)
            if fname.startswith(".") and fname not in {".envrc"}:
                continue
            p = Path(dirpath) / fname
            if is_text_ext(p):
                out.append(p)

    # sort by path for deterministic ordering
    out.sort(key=lambda x: str(x).lower())
    return out


@dataclass
class ManifestChunk:
    filename: str
    sha256: str
    line_count: int
    byte_count: int


@dataclass
class Manifest:
    scan_root: str
    output_dir: str
    total_lines: int
    chunk_lines: int
    chunks: List[ManifestChunk]
    generated_at: str
    project_root: Optional[str] = None
    module_root: Optional[str] = None
    git_head: Optional[str] = None


def ensure_reports_dir(base: Path) -> Path:
    """
    Create context_reports/<timestamp>/ and a 'latest' symlink inside base.
    """
    base = normalize_dir(base)
    ctx_dir = base / CONTEXT_DIRNAME
    ctx_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime(TIMESTAMP_FMT)
    out_dir = ctx_dir / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    # Update symlink (best effort)
    try:
        latest_link = ctx_dir / LATEST_SYMLINK
        if latest_link.is_symlink() or latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(ts, target_is_directory=True)
    except Exception:
        pass

    return out_dir


def build_body_lines(
    scan_root: Path,
    include_tests: bool,
    max_file_bytes: int,
    include_tree: bool,
    project_root: Optional[Path],
) -> List[str]:
    """
    Build the body of the context (everything after the preface).
    """
    lines: List[str] = []
    scan_root = normalize_dir(scan_root)

    # 1) Priority repo metadata (if present)
    priority_names = ["pyproject.toml", "Makefile", "setup.py", "setup.cfg", "requirements.txt"]
    for fname in priority_names:
        p = scan_root / fname
        if p.exists() and is_text_ext(p):
            content = read_text_file(p, max_file_bytes)
            if content is not None:
                lines.append(f"--- BEGIN FILE: {fname} ---")
                lines.extend(content)
                lines.append(f"--- END FILE: {fname} ---")
                lines.append("")

    # 2) Optional directory tree
    if include_tree:
        lines.append("==================")
        lines.append("DIRECTORY TREE")
        lines.append("==================")
        for tline in iter_filtered_tree(scan_root):
            lines.append(tline)
        lines.append("")

    # 3) Collect all files
    all_files = collect_files(scan_root, include_tests)

    # 4) Render each file
    for fpath in all_files:
        rel = safe_relpath(fpath, scan_root)
        content = read_text_file(fpath, max_file_bytes)
        if content is None:
            continue

        lines.append(f"--- BEGIN FILE: {rel} ---")
        if fpath.suffix == ".py":
            outline = python_one_line_outline(content)
            if outline:
                lines.append(f"# {outline}")
        lines.extend(content)
        lines.append(f"--- END FILE: {rel} ---")
        lines.append("")

    return lines


def make_preface_lines(
    scan_root: Path,
    chunk_count: int,
    project_root: Optional[Path],
    preface_text: str = DEFAULT_PREFACE_TEXT,
) -> List[str]:
    """
    Build the preface block (at the start of chunk 1).
    """
    proj_str = str(project_root) if project_root else "(unknown)"

    # Format the preface text with chunk_count
    formatted_preface = preface_text.format(chunk_count=chunk_count)

    lines = [
        "==================",
        "AI CONTEXT PREFACE",
        "==================",
        f"Generated at: {now_iso()}",
        f"Project root: {proj_str}",
        "",
    ]

    # Add the preface text (split into lines)
    lines.extend(formatted_preface.splitlines())

    lines.extend(
        [
            "",
            "--- END PREFACE ---",
            "",
            f"Scan root: {scan_root}",
            "",
        ]
    )

    return lines


def chunk_by_lines(lines: List[str], chunk_lines: int) -> List[List[str]]:
    """
    Split lines into chunks with a max of chunk_lines each.
    """
    if not lines:
        return [[]]
    chunks: List[List[str]] = []
    cur: List[str] = []
    for ln in lines:
        cur.append(ln)
        if len(cur) >= chunk_lines:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks if chunks else [[]]


def add_final_suffix(lines: List[str], suffix_text: str = DEFAULT_SUFFIX_TEXT) -> List[str]:
    """
    Append the required final line to the last chunk.
    """
    # Strip trailing blank lines for neatness
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append(suffix_text)
    return lines


def chunk_with_preface_and_suffix(
    body_lines: List[str],
    chunk_lines: int,
    scan_root: Path,
    project_root: Optional[Path],
    preface_text: str = DEFAULT_PREFACE_TEXT,
    suffix_text: str = DEFAULT_SUFFIX_TEXT,
) -> List[List[str]]:
    """
    Insert a dynamic preface at the start of chunk 1 and the required final suffix
    at the very end of the last chunk.
    """
    # First pass: count chunks without preface/suffix
    raw_chunks = chunk_by_lines(body_lines, chunk_lines)
    est_count = max(1, len(raw_chunks))  # avoid zero

    # Build with preface
    preface = make_preface_lines(scan_root, est_count, project_root, preface_text)
    chunks = chunk_by_lines(preface + body_lines, chunk_lines)
    final_count = len(chunks)
    if final_count != est_count:
        # Recreate preface with correct count if it changed
        preface = make_preface_lines(scan_root, final_count, project_root, preface_text)
        chunks = chunk_by_lines(preface + body_lines, chunk_lines)

    # Add final suffix to last chunk
    if chunks:
        chunks[-1] = add_final_suffix(chunks[-1], suffix_text)

    return chunks


# ============================================================
# Orchestration
# ============================================================


def write_chunks_and_manifest(
    scan_root: Path,
    output_base: Path,
    chunks: List[List[str]],
    chunk_lines: int,
    project_root: Optional[Path],
    module_root: Optional[Path],
) -> Manifest:
    out_dir = ensure_reports_dir(output_base)
    manifest_items: List[ManifestChunk] = []
    total = 0

    for idx, c in enumerate(chunks, start=1):
        fname = f"{CHUNK_PREFIX}{idx:04d}{CHUNK_SUFFIX}"
        data = ("\n".join(c) + "\n").encode("utf-8")
        (out_dir / fname).write_bytes(data)
        manifest_items.append(
            ManifestChunk(
                filename=fname,
                sha256=sha256_bytes(data),
                line_count=len(c),
                byte_count=len(data),
            )
        )
        total += len(c)

    manifest = Manifest(
        scan_root=str(scan_root),
        output_dir=str(out_dir),
        total_lines=total,
        chunk_lines=chunk_lines,
        chunks=manifest_items,
        generated_at=now_iso(),
        project_root=str(project_root) if project_root else None,
        module_root=str(module_root) if module_root else None,
    )
    (out_dir / MANIFEST_NAME).write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return manifest


# ============================================================
# CLI
# ============================================================


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="generate_context",
        description="Generate multi-chunk AI-readable context files for a source tree.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--chunk",
        type=int,
        default=DEFAULT_CHUNK_LINES,
        help="Maximum number of lines per output chunk.",
    )
    p.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help="Skip any single file larger than this size (bytes).",
    )
    p.add_argument(
        "--include-tests", action="store_true", help="Include tests/** and similar in the scan."
    )
    p.add_argument(
        "--no-tree", action="store_true", help="Do not include the directory tree section."
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Do not write files; print summary + previews."
    )

    # Text customization
    p.add_argument(
        "--preface-file",
        type=str,
        metavar="PATH",
        help="Path to file containing custom preface text (supports {chunk_count} placeholder).",
    )
    p.add_argument(
        "--suffix-file",
        type=str,
        metavar="PATH",
        help="Path to file containing custom suffix text.",
    )

    # Discovery: affects SCAN ROOT (not output base)
    p.add_argument(
        "--discover",
        choices=["project", "module"],
        default=None,
        help="Adjust the SCAN ROOT by discovering the project or module root. Default: scan current directory only.",
    )

    # Output location switches (mutually exclusive)
    out_group = p.add_mutually_exclusive_group()
    out_group.add_argument(
        "--to-project-root",
        action="store_true",
        help="Write outputs under <project-root>/{}/<timestamp>/".format(CONTEXT_DIRNAME),
    )
    out_group.add_argument(
        "--to-module-root",
        action="store_true",
        help="Write outputs under <module-root>/{}/<timestamp>/".format(CONTEXT_DIRNAME),
    )

    return p.parse_args(argv)


def pick_scan_root(
    args: argparse.Namespace, cwd: Path
) -> tuple[Path, Optional[Path], Optional[Path], List[str]]:
    """
    Decide the scan root based on discovery rules.

    Spec: "First evaluate the current directory; if it already qualifies, use it.
    Otherwise walk upward appropriately to select the scan root."

    When args.discover is None (default): use cwd exactly (no discovery).

    Returns (scan_root, project_root, module_root, warnings)
    """
    notes: List[str] = []

    # Always discover these for reference (and output location decisions)
    project_root = discover_project_root(cwd)
    module_root = discover_module_root(cwd)

    scan_root = cwd  # Default: current directory

    if args.discover == "project":
        # Check if cwd is already a project root
        if (cwd / "pyproject.toml").exists() or (cwd / ".git").exists():
            scan_root = cwd
        elif project_root:
            scan_root = project_root
        else:
            notes.append(
                "Warn: --discover project requested but no project root found; using current directory."
            )

    elif args.discover == "module":
        # Check if cwd is already a module root (has __init__.py)
        if (cwd / "__init__.py").exists():
            # cwd has __init__.py, but there might be a higher module root
            if module_root and module_root != cwd:
                # There's a higher package; use that
                scan_root = module_root
            else:
                # cwd is the module root
                scan_root = cwd
        elif module_root:
            # cwd doesn't have __init__.py, but we found a module root above
            scan_root = module_root
        else:
            notes.append(
                "Warn: --discover module requested but no module root found; using current directory."
            )

    # When args.discover is None, fall through with scan_root = cwd

    return (scan_root, project_root, module_root, notes)


def pick_output_base(
    args: argparse.Namespace,
    scan_root: Path,
    project_root: Optional[Path],
    module_root: Optional[Path],
) -> tuple[Path, List[str]]:
    """
    Decide where to WRITE outputs. Default: under the SCAN ROOT.
    Overrides: --to-project-root / --to-module-root.
    Returns (output_base, warnings)
    """
    notes: List[str] = []
    if args.to_project_root:
        if project_root:
            return (project_root, notes)
        else:
            notes.append(
                "Warn: --to-project-root requested but no project root found; writing under scan root."
            )
            return (scan_root, notes)
    if args.to_module_root:
        if module_root:
            return (module_root, notes)
        else:
            notes.append(
                "Warn: --to-module-root requested but no module root found; writing under scan root."
            )
            return (scan_root, notes)

    # Default: write under scan root
    return (scan_root, notes)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    cwd = normalize_dir(Path.cwd())

    # 1) Load custom preface and suffix text if provided
    preface_text = load_text_file_or_default(args.preface_file, DEFAULT_PREFACE_TEXT)
    suffix_text = load_text_file_or_default(args.suffix_file, DEFAULT_SUFFIX_TEXT)

    # 2) Determine scan root (and discovered roots)
    scan_root, project_root, module_root, discover_notes = pick_scan_root(args, cwd)

    # 3) Determine output base (where context_reports/ is created)
    output_base, out_notes = pick_output_base(args, scan_root, project_root, module_root)

    # 4) Build the body
    include_tree = not args.no_tree
    body_lines = build_body_lines(
        scan_root=scan_root,
        include_tests=args.include_tests,
        max_file_bytes=args.max_file_bytes,
        include_tree=include_tree,
        project_root=project_root,
    )

    # 5) Chunk with preface + final suffix
    chunks = chunk_with_preface_and_suffix(
        body_lines=body_lines,
        chunk_lines=args.chunk,
        scan_root=scan_root,
        project_root=project_root,
        preface_text=preface_text,
        suffix_text=suffix_text,
    )

    # DRY RUN MODE
    if args.dry_run:
        total_lines = sum(len(c) for c in chunks)
        print(
            f"[DRY RUN] total lines (with preface & suffix): {total_lines}; "
            f"chunk size: {args.chunk}; would write {len(chunks)} chunk(s).\n"
        )
        print(f"Scan root: {scan_root}")
        print(f"Output base (parent of '{CONTEXT_DIRNAME}'): {output_base}")
        if project_root:
            print(f"Project root: {project_root}")
        else:
            print("Project root: (not found)")
        if module_root:
            print(f"Module root:  {module_root}")
        else:
            print("Module root:  (not found)")
        for n in discover_notes + out_notes:
            print(n)
        print("")

        # Preview head/tail
        if chunks:
            head_preview = "\n".join(chunks[0][:25])
            print("--- Preview: start of chunk_0001.txt ---")
            print(head_preview)
            print("\n--- Preview: end of last chunk ---")
            tail = chunks[-1][-25:] if len(chunks[-1]) > 25 else chunks[-1]
            print("\n".join(tail))
        return 0

    # 5) Write outputs
    manifest = write_chunks_and_manifest(
        scan_root=scan_root,
        output_base=output_base,
        chunks=chunks,
        chunk_lines=args.chunk,
        project_root=project_root,
        module_root=module_root,
    )

    print(f"Context generated at: {manifest.output_dir}")
    print(f"Chunks: {len(manifest.chunks)} (chunk size: {manifest.chunk_lines} lines)")
    for c in manifest.chunks[:3]:
        print(f"  - {c.filename} ({c.line_count} lines, sha256={c.sha256[:12]}...)")
    if len(manifest.chunks) > 3:
        print(f"  ... and {len(manifest.chunks) - 3} more.")

    # Emit any warnings/notes post-run
    for n in discover_notes + out_notes:
        print(n)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
