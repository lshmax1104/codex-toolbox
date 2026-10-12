from __future__ import annotations

import difflib
import io
import json
import shutil
import stat
import zipfile
from pathlib import Path

from .core import (FS_LOCK, LIMIT, STATE, TEXT_LIMIT, backup, bounded, contained,
                   digest, input_file, resolve, tool, walk, write_bytes)


@tool("files")
def files_list(path: str = ".", recursive: bool = False, pattern: str = "*", limit: int = 200) -> dict:
    """List an allowed directory; recursive mode lists matching files, with a result cap."""
    bounded(limit)
    root = resolve(path, exists=True)
    if not root.is_dir():
        raise ValueError("Expected a directory")
    entries = walk(path, pattern) if recursive else sorted(root.iterdir())
    rows = []
    truncated = False
    for entry in entries:
        try:
            p = resolve(str(entry))
        except ValueError:
            continue
        if not p.match(pattern):
            continue
        if len(rows) == limit:
            truncated = True
            break
        rows.append({"path": str(p), "directory": p.is_dir(),
                     "bytes": p.stat().st_size if p.is_file() else None})
    return {"entries": rows, "truncated": truncated}


@tool("files")
def files_search(path: str, query: str, pattern: str = "*", case_sensitive: bool = False,
                 limit: int = 100) -> dict:
    """Find literal text in UTF-8 files; return matching lines and file paths."""
    bounded(limit)
    if not query:
        raise ValueError("query cannot be empty")
    needle = query if case_sensitive else query.casefold()
    matches = []
    for p in walk(path, pattern):
        if p.stat().st_size > LIMIT:
            continue
        try:
            text = p.read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            continue
        if "\0" in text:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if needle in (line if case_sensitive else line.casefold()):
                if len(matches) == limit:
                    return {"matches": matches, "truncated": True}
                matches.append({"path": str(p), "line": number, "text": line[:1000]})
    return {"matches": matches, "truncated": False}


@tool("files")
def files_read(path: str, start_line: int = 1, line_count: int = 200) -> dict:
    """Read a page of UTF-8 text with one-based line numbers."""
    bounded(start_line, high=10_000_000)
    bounded(line_count, high=5000)
    lines = input_file(path).read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines[start_line - 1:start_line - 1 + line_count])
    return {"path": str(resolve(path)), "start_line": start_line, "total_lines": len(lines),
            "text": text[:TEXT_LIMIT], "truncated": len(text) > TEXT_LIMIT or len(lines) >= start_line + line_count}


@tool("files", write=True)
def files_write(path: str, text: str, overwrite: bool = False) -> dict:
    """Create UTF-8 text; explicitly overwritten files get a restorable backup."""
    return write_bytes(path, text.encode("utf-8"), overwrite)


@tool("files", write=True)
def files_replace(path: str, old: str, new: str, expected_count: int = 1) -> dict:
    """Replace exact text only when its occurrence count matches; back up before writing."""
    bounded(expected_count, high=10000)
    if not old:
        raise ValueError("old cannot be empty")
    with FS_LOCK:
        text = input_file(path).read_text(encoding="utf-8")
        if text.count(old) != expected_count:
            raise ValueError(f"Found {text.count(old)} occurrences, expected {expected_count}")
        return write_bytes(path, text.replace(old, new).encode("utf-8"), True)


@tool("files", write=True)
def files_copy(source: str, destination: str, overwrite: bool = False) -> dict:
    """Copy one bounded file within allowed roots, backing up an overwritten destination."""
    return write_bytes(destination, input_file(source).read_bytes(), overwrite)


@tool("files", write=True, destructive=True)
def files_move(source: str, destination: str) -> dict:
    """Move one regular file to a new path; existing destinations are rejected."""
    with FS_LOCK:
        src, dst = input_file(source), resolve(destination)
        if dst.exists():
            raise FileExistsError(str(dst))
        dst.parent.mkdir(parents=True, exist_ok=True)
        saved = backup(src)
        shutil.move(str(src), str(dst))
        return {"source": str(src), "destination": str(dst), "backup_id": saved}


@tool("files", write=True)
def files_mkdir(path: str) -> dict:
    """Create an allowed directory and missing parents."""
    p = resolve(path)
    p.mkdir(parents=True, exist_ok=True)
    return {"path": str(p)}


@tool("files")
def files_info(path: str) -> dict:
    """Return size, modification time and file type."""
    p = resolve(path, exists=True)
    s = p.stat()
    return {"path": str(p), "directory": p.is_dir(), "bytes": s.st_size,
            "modified_epoch": s.st_mtime, "suffix": p.suffix}


@tool("files")
def files_hash(path: str) -> dict:
    """Calculate the SHA-256 of a bounded file."""
    p = input_file(path)
    return {"path": str(p), "sha256": digest(p)}


@tool("files")
def files_compare(first: str, second: str) -> dict:
    """Compare two UTF-8 files and return a unified diff."""
    a = input_file(first).read_text(encoding="utf-8-sig").splitlines(True)
    b = input_file(second).read_text(encoding="utf-8-sig").splitlines(True)
    diff = "".join(difflib.unified_diff(a, b, fromfile=first, tofile=second))
    return {"identical": a == b, "diff": diff[:TEXT_LIMIT], "truncated": len(diff) > TEXT_LIMIT}


@tool("files")
def files_duplicates(path: str, pattern: str = "*", limit: int = 100) -> dict:
    """Find duplicate bounded files by size and SHA-256; return paths without deleting."""
    bounded(limit)
    sizes = {}
    for p in walk(path, pattern):
        if p.stat().st_size <= LIMIT:
            sizes.setdefault(p.stat().st_size, []).append(p)
    groups = []
    for candidates in sizes.values():
        if len(candidates) < 2:
            continue
        hashes = {}
        for p in candidates:
            hashes.setdefault(digest(p), []).append(str(p))
        groups.extend({"sha256": key, "paths": paths} for key, paths in hashes.items() if len(paths) > 1)
    return {"groups": groups[:limit], "truncated": len(groups) > limit}


@tool("files")
def backups_list(limit: int = 50) -> dict:
    """List saved file backups with original paths and timestamps."""
    bounded(limit)
    folder = STATE / "backups"
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")]
    return {"backups": sorted(rows, key=lambda x: x["time"], reverse=True)[:limit]}


@tool("files", write=True)
def backups_restore(backup_id: str, destination: str, overwrite: bool = False) -> dict:
    """Restore a backup to an explicit allowed destination; preserve overwritten content."""
    if len(backup_id) != 32 or any(c not in "0123456789abcdef" for c in backup_id):
        raise ValueError("Invalid backup ID")
    p = STATE / "backups" / backup_id
    if not p.is_file():
        raise FileNotFoundError("Backup not found")
    return write_bytes(destination, p.read_bytes(), overwrite)


@tool("archives")
def zip_list(path: str, limit: int = 200) -> dict:
    """List ZIP member names, sizes and compressed sizes without extraction."""
    bounded(limit)
    with zipfile.ZipFile(input_file(path)) as z:
        items = z.infolist()
        return {"entries": [{"name": i.filename, "bytes": i.file_size,
                "compressed_bytes": i.compress_size} for i in items[:limit]], "truncated": len(items) > limit}


@tool("archives", write=True)
def zip_create(paths: list[str], destination: str, overwrite: bool = False) -> dict:
    """Create a ZIP from up to 200 explicit files; duplicate basenames are rejected."""
    bounded(len(paths), high=200)
    files = [input_file(p) for p in paths]
    if len({p.name.casefold() for p in files}) != len(files):
        raise ValueError("Duplicate basenames")
    if sum(p.stat().st_size for p in files) > LIMIT:
        raise ValueError("Combined input exceeds max_file_bytes")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.name)
    return write_bytes(destination, out.getvalue(), overwrite)


@tool("archives", write=True)
def zip_extract(path: str, destination: str) -> dict:
    """Extract a bounded ZIP into a new directory after validating all paths and sizes."""
    src = input_file(path)
    dst = resolve(destination)
    if dst.exists():
        raise FileExistsError("Extraction destination must be new")
    with zipfile.ZipFile(src) as z:
        entries = z.infolist()
        if len(entries) > 1000 or sum(i.file_size for i in entries) > LIMIT:
            raise ValueError("Archive exceeds extraction limits")
        targets = []
        keys = set()
        for entry in entries:
            name = entry.filename.replace("\\", "/")
            if name.startswith("/") or any(part in {"..", "."} or ":" in part for part in name.split("/")):
                raise ValueError("Unsafe archive member")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Archive symlinks are not supported")
            target = resolve(str(dst / name))
            if not contained(target, dst) or str(target).casefold() in keys:
                raise ValueError("Unsafe or duplicate archive target")
            keys.add(str(target).casefold())
            targets.append((entry, target))
        dst.mkdir(parents=True)
        try:
            for entry, target in targets:
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    write_bytes(str(target), z.read(entry))
        except Exception:
            # This directory was newly created by this call and was fully validated.
            shutil.rmtree(dst)
            raise
    return {"path": str(dst), "entries": len(entries)}
