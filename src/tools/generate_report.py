#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Optional, Iterator

# ---------- Defaults / knobs ----------
DEFAULT_CHUNK_LINES = 1500
DEFAULT_MAX_FILE_BYTES = 300_000  # skip unusually large text files

REPORTS_DIRNAME = "project_reports"
TIMESTAMP_FMT = "%Y%m%d_%H%M%S"
CHUNK_PREFIX = "chunk_"
CHUNK_SUFFIX = ".txt"
MANIFEST_NAME = "MANIFEST.json"
LATEST_SYMLINK = "latest"

# What to show in the lean report
INCLUDE_DIRS_ALWAYS = ["src", "scripts"]  # tree + content scan roots
INCLUDE_TOPLEVEL_CORE = ["pyproject.toml", "Makefile"]
INCLUDE_SCRIPT_GLOBS = ["scripts/*.sh"]          # small helper scripts
ALSO_INCLUDE_CODE_CONFIG = ["paths.py"]          # any src/**/paths.py

# Exclude noisy/transient stuff
TREE_EXCLUDES = {
    ".git", REPORTS_DIRNAME, "__pycache__", ".venv", "venv", "env",
    "build", "dist", ".tox", ".nox", "node_modules", ".ruff_cache",
    ".mypy_cache", ".pytest_cache", ".cache", ".idea", ".vscode"
}
TEXT_EXTS = {
    ".py", ".md", ".toml", ".txt", ".ini", ".cfg", ".yml", ".yaml",
    ".json", ".sh", ".rst", ".desktop", ".service"
}

# ---------- Utilities ----------

def find_project_root(start: Optional[Path] = None) -> Path:
    start = Path(start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    return start

def call_git(args: List[str], cwd: Path) -> Tuple[int, str]:
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=str(cwd),
            stderr=subprocess.STDOUT, text=True
        )
        return (0, out.strip())
    except Exception as e:
        return (1, f"(unavailable: {e})")

def sanitize_git_remotes(text: str) -> str:
    return re.sub(r"(https://)([^/@]+)@", r"\1<redacted>@", text)

def gather_git_info(project_root: Path) -> List[str]:
    lines = []
    code, head = call_git(["rev-parse", "HEAD"], project_root)
    if code == 0:
        lines += ["[GIT] HEAD:", head]
    code, status = call_git(["status", "--porcelain"], project_root)
    if code == 0:
        lines += ["[GIT] Status (porcelain):", status if status else "(clean)"]
    return lines or ["[GIT] info unavailable"]

def safe_relpath(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)

def section_header(title: str) -> List[str]:
    bar = "=" * len(title)
    return [bar, title, bar]

@dataclass
class Section:
    title: str
    body_lines: List[str]

# ---------- Tree (filtered) ----------

def _skip_name(name: str) -> bool:
    return name in TREE_EXCLUDES or name.startswith(".")

def iter_filtered_tree(project_root: Path, include_dirs: List[str], include_top_files: List[str]) -> Iterator[str]:
    """ASCII tree of selected roots + top-level core files."""
    roots = [project_root / d for d in include_dirs if (project_root / d).exists()]
    roots.sort()
    yield "."
    # top-level core files
    for rel in include_top_files:
        p = project_root / rel
        if p.exists() and p.is_file():
            yield f"├── {rel}"
    # then roots
    for ridx, root in enumerate(roots):
        last_root = (ridx == len(roots) - 1)
        branch = "└──" if last_root else "├──"
        yield f"{branch} {root.relative_to(project_root)}"
        yield from _walk_dir(root, prefix=("    " if last_root else "│   "))

def _walk_dir(dirpath: Path, prefix: str) -> Iterator[str]:
    entries = [e for e in dirpath.iterdir() if not _skip_name(e.name)]
    entries.sort(key=lambda p: (p.is_file(), p.name.lower()))
    for i, e in enumerate(entries):
        is_last = (i == len(entries) - 1)
        branch = "└── " if is_last else "├── "
        yield f"{prefix}{branch}{e.name}"
        if e.is_dir():
            child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
            yield from _walk_dir(e, child_prefix)

# ---------- File collection ----------

def read_text_file(path: Path, max_bytes: int) -> Optional[List[str]]:
    try:
        if path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        return text.splitlines()
    except Exception:
        return None

def gather_core_files(project_root: Path, max_bytes: int) -> List[str]:
    out: List[str] = []
    # top-level core
    for rel in INCLUDE_TOPLEVEL_CORE:
        p = project_root / rel
        if p.exists() and p.is_file():
            lines = read_text_file(p, max_bytes)
            if lines is None:
                continue
            out += [f"--- BEGIN FILE: {rel} ---"]
            out.extend(lines)
            out += [f"--- END FILE: {rel} ---", ""]
    # scripts/*.sh
    for pat in INCLUDE_SCRIPT_GLOBS:
        for p in sorted(project_root.glob(pat)):
            if not p.is_file():
                continue
            lines = read_text_file(p, max_bytes)
            if lines is None:
                continue
            rel = safe_relpath(p, project_root)
            out += [f"--- BEGIN FILE: {rel} ---"]
            out.extend(lines)
            out += [f"--- END FILE: {rel} ---", ""]
    # any src/**/paths.py
    src_dir = project_root / "src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("paths.py")):
            if not p.is_file():
                continue
            lines = read_text_file(p, max_bytes)
            if lines is None:
                continue
            rel = safe_relpath(p, project_root)
            out += [f"--- BEGIN FILE: {rel} ---"]
            out.extend(lines)
            out += [f"--- END FILE: {rel} ---", ""]
    return out

def gather_code(project_root: Path, include_tests: bool, max_bytes: int) -> List[str]:
    out: List[str] = []
    # src/**/*.py
    src_dir = project_root / "src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("*.py")):
            if any(part in TREE_EXCLUDES for part in p.parts):
                continue
            lines = read_text_file(p, max_bytes)
            if lines is None:
                continue
            rel = safe_relpath(p, project_root)
            out += [f"--- BEGIN FILE: {rel} ---"]
            out.extend(lines)
            out += [f"--- END FILE: {rel} ---", ""]
    # optional tests/**/*.py
    if include_tests:
        tests_dir = project_root / "tests"
        if tests_dir.exists():
            for p in sorted(tests_dir.rglob("*.py")):
                if any(part in TREE_EXCLUDES for part in p.parts):
                    continue
                lines = read_text_file(p, max_bytes)
                if lines is None:
                    continue
                rel = safe_relpath(p, project_root)
                out += [f"--- BEGIN FILE: {rel} ---"]
                out.extend(lines)
                out += [f"--- END FILE: {rel} ---", ""]
    return out

# ---------- Chunking / manifest ----------

def chunk_by_lines(lines: List[str], max_lines: int) -> List[List[str]]:
    chunks: List[List[str]] = []
    buf: List[str] = []
    for ln in lines:
        buf.append(ln)
        if len(buf) >= max_lines:
            chunks.append(buf)
            buf = []
    if buf:
        chunks.append(buf)
    return chunks

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

@dataclass
class ManifestChunk:
    filename: str
    sha256: str
    line_count: int
    byte_count: int

@dataclass
class Manifest:
    project_root: str
    output_dir: str
    total_lines: int
    chunk_lines: int
    chunks: List[ManifestChunk]
    generated_at: str
    git_head: Optional[str]

def ensure_reports_dir(project_root: Path) -> Path:
    out_root = project_root / REPORTS_DIRNAME
    out_root.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime(TIMESTAMP_FMT)
    out_dir = out_root / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    # Update latest symlink (best-effort)
    latest = out_root / LATEST_SYMLINK
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(out_dir.name)
    except Exception:
        pass
    return out_dir

# ---------- Preface injection (first chunk only) ----------

def make_preface_lines(project_root: Path, total_chunks: int) -> List[str]:
    now = dt.datetime.now().astimezone().isoformat()
    title = "AI PROJECT REPORT PREFACE"
    bar = "=" * len(title)
    return [
        bar,
        title,
        bar,
        f"Generated at: {now}",
        f"Project root: {project_root}",
        "",
        "You are an AI assistant. You are receiving a multi-part, plain-text report that serves as the single",
        "source of truth for this project so you can help with code navigation, analysis, refactoring,",
        "bug fixing, packaging, and related development tasks.",
        "",
        f"Delivery: This report is split into {total_chunks} chunk(s) named {CHUNK_PREFIX}0001{CHUNK_SUFFIX} ...",
        f"up to {CHUNK_PREFIX}{total_chunks:04d}{CHUNK_SUFFIX}. You are reading chunk 1 of {total_chunks}.",
        "",
        "Instructions:",
        "  1) Use only the information in this report unless explicitly provided with more context.",
        f"  2) When the last chunk ({CHUNK_PREFIX}{total_chunks:04d}{CHUNK_SUFFIX}) arrives, WAIT for further",
        "     instructions before taking any action.",
        "  3) Respect file boundaries marked as:",
        "         --- BEGIN FILE: <path> ---",
        "         --- END FILE: <path> ---",
        "  4) Use the DIRECTORY TREE and METADATA sections to orient yourself quickly.",
        "",
        "--- END PREFACE ---",
        ""
    ]

def chunk_with_preface(lines: List[str], chunk_lines: int, project_root: Path) -> List[List[str]]:
    """
    Insert a dynamic preface at the start of chunk 1 that references the final chunk count.
    We do this in two passes to make the count accurate even if the preface affects chunking.
    """
    # First pass: estimate count without preface
    initial_chunks = chunk_by_lines(lines, chunk_lines)
    est_count = len(initial_chunks)

    # Build with preface using estimate, then re-flow once with final count if needed
    preface = make_preface_lines(project_root, est_count)
    chunks = chunk_by_lines(preface + lines, chunk_lines)
    final_count = len(chunks)

    if final_count != est_count:
        preface = make_preface_lines(project_root, final_count)
        chunks = chunk_by_lines(preface + lines, chunk_lines)

    return chunks

# ---------- Orchestration ----------

def build_lines(project_root: Path, include_tests: bool, max_file_bytes: int) -> List[str]:
    lines: List[str] = []
    # METADATA
    lines += section_header("PROJECT METADATA")
    lines += [
        f"timestamp: {dt.datetime.now().astimezone().isoformat()}",
        f"project_root: {project_root}",
        f"python: {sys.version.split()[0]}",
        "",
    ]
    # GIT
    lines += section_header("GIT")
    lines += gather_git_info(project_root) + [""]

    # DIRECTORY TREE (filtered)
    lines += section_header("DIRECTORY TREE (filtered)")
    lines += list(iter_filtered_tree(project_root, INCLUDE_DIRS_ALWAYS, INCLUDE_TOPLEVEL_CORE)) + [""]

    # CORE FILES
    core = gather_core_files(project_root, max_file_bytes)
    if core:
        lines += section_header("CORE FILES")
        lines += core

    # CODE (+ optional TESTS)
    code = gather_code(project_root, include_tests, max_file_bytes)
    if code:
        title = "CODE" if not include_tests else "CODE & TESTS"
        lines += section_header(title)
        lines += code

    # Trim trailing empties
    while lines and lines[-1] == "":
        lines.pop()
    return lines

# ---------- CLI ----------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="generate_report",
        description="Generate a lean, AI-readable project report (split into .txt chunks).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--chunk", type=int, default=DEFAULT_CHUNK_LINES, metavar="N",
                   help="Maximum number of lines per output chunk.")
    p.add_argument("--include-tests", action="store_true",
                   help="Include tests/** in the report.")
    p.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES, metavar="N",
                   help="Skip any single file larger than this size (bytes).")
    p.add_argument("--output-dir", type=Path, default=None, metavar="DIR",
                   help=f"Override output directory (default: {REPORTS_DIRNAME}/<timestamp>).")
    p.add_argument("--project-root", type=Path, default=None, metavar="DIR",
                   help="Explicit project root (auto-detected if omitted).")
    p.add_argument("--dry-run", action="store_true",
                   help="Do everything except write files; prints summary to stdout.")
    return p.parse_args(argv)

def write_chunks_and_manifest(project_root: Path, out_dir: Path, chunks: List[List[str]], chunk_lines: int) -> Manifest:
    manifest_items: List[ManifestChunk] = []
    total = 0
    for idx, c in enumerate(chunks, start=1):
        fname = f"{CHUNK_PREFIX}{idx:04d}{CHUNK_SUFFIX}"
        data = ("\n".join(c) + "\n").encode("utf-8")
        (out_dir / fname).write_bytes(data)
        manifest_items.append(ManifestChunk(
            filename=fname,
            sha256=sha256_bytes(data),
            line_count=len(c),
            byte_count=len(data),
        ))
        total += len(c)
    code, head = call_git(["rev-parse", "HEAD"], project_root)
    head_val = head if code == 0 else None
    manifest = Manifest(
        project_root=str(project_root),
        output_dir=str(out_dir),
        total_lines=total,
        chunk_lines=chunk_lines,
        chunks=manifest_items,
        generated_at=dt.datetime.now().astimezone().isoformat(),
        git_head=head_val,
    )
    (out_dir / MANIFEST_NAME).write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return manifest

def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root) if args.project_root else find_project_root()
    if not project_root.exists():
        print(f"Error: project root does not exist: {project_root}", file=sys.stderr)
        return 2

    # Build the lean report body (without preface)
    body_lines = build_lines(project_root, include_tests=args.include_tests, max_file_bytes=args.max_file_bytes)

    # Chunk with dynamic preface injected into chunk 1
    chunks = chunk_with_preface(body_lines, args.chunk, project_root)

    if args.dry_run:
        print(f"[DRY RUN] total lines (with preface): {sum(len(c) for c in chunks)}; "
              f"chunk size: {args.chunk}; would write {len(chunks)} chunk(s).")
        # Show first 25 lines of the first chunk (to see the preface), and a small peek into the last chunk
        preview_first = "\n".join(chunks[0][:25])
        print("\n--- Preview: start of chunk_0001.txt ---\n" + preview_first)
        if len(chunks) > 1:
            last = chunks[-1]
            tail = "\n".join(last[-10:])
            print("\n--- Preview: end of last chunk ---\n" + tail)
        return 0

    out_dir = Path(args.output_dir) if args.output_dir else ensure_reports_dir(project_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = write_chunks_and_manifest(project_root, out_dir, chunks, args.chunk)

    print(f"Report generated at: {manifest.output_dir}")
    print(f"Chunks: {len(manifest.chunks)} (chunk size: {manifest.chunk_lines} lines)")
    for c in manifest.chunks[:3]:
        print(f"  - {c.filename} ({c.line_count} lines, sha256={c.sha256[:12]}...)")
    if len(manifest.chunks) > 3:
        print(f"  ... and {len(manifest.chunks)-3} more.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

