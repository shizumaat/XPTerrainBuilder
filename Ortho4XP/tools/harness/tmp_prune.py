#!/usr/bin/env python3
"""THE AGE PRUNE of a tree's ``tmp/`` — harness outputs and the lane cache (#1723).

    venv/bin/python tools/harness/tmp_prune.py ENGINE [--days N] [--apply]
        [--data-repo DIR] [--frames FILE]

WHY.  A lane worktree drops its ``tmp/`` on ``down``; the main checkout
never does, and its ``tmp/engine_caches/Airport_mod_cache`` (the
lane-persistent overlay, ``build_airport.lane_cache_root``) grew to 32 GB,
with ~3 GB of stale lane output beside it.  This lists every entry no
file of which was touched for ``--days`` days: each top-level child of
``tmp/`` except ``engine_caches``, and each child of every
``engine_caches/<cache>/``.  The default is the dry-run listing with the
PRIVATE bytes each entry would free (``cow_audit.private_bytes``: an APFS
clone of the shared corpus frees ~0, whatever ``du`` says); ``--apply``
deletes.

NEVER deleted: a symlink, or anything that resolves into the shared data
repo; an entry a registered frame (``docs/frames.jsonl``) lies in or
holds; an entry a running process holds open (one ``lsof +D``, refused
outright when ``lsof`` is missing and ``--apply`` is given).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corpus_snapshot import SHARED_DATA_REPO_DEFAULT  # noqa: E402
from cow_audit import private_bytes  # noqa: E402

__all__ = ["candidates", "prune", "frame_paths", "open_paths",
           "prune_cache_after_run"]

CACHE_DIR = "engine_caches"


def _newest(path: str) -> float:
    """The newest mtime/atime of ``path`` and everything under it."""
    st = os.lstat(path)
    newest = max(st.st_mtime, st.st_atime)
    if os.path.isdir(path) and not os.path.islink(path):
        for dirpath, dirs, names in os.walk(path):
            for name in dirs + names:
                try:
                    s = os.lstat(os.path.join(dirpath, name))
                except OSError:
                    continue
                newest = max(newest, s.st_mtime, s.st_atime)
    return newest


def _freed(path: str) -> int:
    """Private bytes under ``path`` (allocated bytes where APFS cannot say)."""
    files = [path] if not os.path.isdir(path) else [
        os.path.join(d, n) for d, _s, ns in os.walk(path) for n in ns]
    total = 0
    for f in files:
        if os.path.islink(f):
            continue
        size = private_bytes(f)
        if size is None:
            try:
                st = os.lstat(f)
                blocks = getattr(st, "st_blocks", None)   # none on Windows
                size = blocks * 512 if blocks is not None else st.st_size
            except OSError:
                size = 0
        total += size
    return total


def frame_paths(registry) -> list:
    """Real paths of every registered frame."""
    out = []
    if registry and os.path.isfile(registry):
        with open(registry, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    path = json.loads(line).get("path")
                    if path:
                        out.append(os.path.realpath(path))
    return out


def open_paths(tmp) -> list | None:
    """Real paths open under ``tmp`` by a BUILD (a python or engine
    process, the rule ``lane_worktree.sh reclaim`` uses: a system daemon
    indexing a file is no writer); None without lsof."""
    if not shutil.which("lsof"):
        return None
    run = subprocess.run(["lsof", "-a", "-c", "python", "-c", "Python",
                          "-c", "Ortho4XP", "-Fn", "+D", str(tmp)], capture_output=True,
                         text=True, check=False)
    return [os.path.realpath(ln[1:]) for ln in run.stdout.splitlines()
            if ln.startswith("n")]


def _entries(tmp: Path):
    for child in sorted(tmp.iterdir()):
        if child.name != CACHE_DIR:
            yield child
            continue
        for cache in sorted(p for p in child.iterdir() if p.is_dir()):
            yield from sorted(cache.iterdir())


def _within(path: str, roots) -> bool:
    return any(path == r or path.startswith(r + os.sep) or
               r.startswith(path + os.sep) for r in roots)


def candidates(engine, days: float, data_repo=None, frames=(), held=(),
               now=None) -> list:
    """``[(path, private bytes, age days, why-kept or "")]`` for ``engine``'s
    ``tmp/`` entries older than ``days``; a kept entry names its reason."""
    tmp = Path(engine) / "tmp"
    if not tmp.is_dir():
        return []
    now = time.time() if now is None else now
    data = os.path.realpath(data_repo) if data_repo else None
    rows = []
    for entry in _entries(tmp):
        path = str(entry)
        age = (now - _newest(path)) / 86400.0
        if age < days:
            continue
        real = os.path.realpath(path)
        why = ""
        if os.path.islink(path):
            why = "symlink"
        elif data and _within(real, [data]):
            why = "shared data repo"
        elif _within(real, frames):
            why = "registered frame"
        elif any(h == real or h.startswith(real + os.sep) for h in held):
            why = "held open by a process"
        rows.append((path, 0 if why else _freed(path), age, why))
    return rows


def prune(rows) -> int:
    """Delete the unkept ``rows``; the bytes freed."""
    freed = 0
    for path, size, _age, why in rows:
        if why:
            continue
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        freed += size
    return freed


def prune_cache_after_run(engine, data_repo=None, frames=None,
                          days=None) -> tuple:
    """``build_airport``'s closing step: delete the ``engine_caches``
    entries (only those) unused for ``days`` (``O4_LANE_CACHE_PRUNE_DAYS``,
    default 7; 0 disables).  ``(entries, bytes)``; nothing without lsof."""
    if days is None:
        days = float(os.environ.get("O4_LANE_CACHE_PRUNE_DAYS", "7"))
    tmp = Path(engine) / "tmp"
    held = open_paths(tmp) if days > 0 and tmp.is_dir() else None
    if held is None:
        return 0, 0
    cache = str(tmp / CACHE_DIR) + os.sep
    rows = [r for r in candidates(engine, days, data_repo,
                                  frame_paths(frames), held)
            if r[0].startswith(cache) and not r[3]]
    return len(rows), prune(rows)


def main(argv=None) -> int:
    # The console is UTF-8 before the parser can print (#171, #125).
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    here = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("engine", help="an Ortho4XP tree (holds tmp/)")
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--data-repo", default=os.environ.get(
        "O4_DATA_REPO", str(SHARED_DATA_REPO_DEFAULT)))
    ap.add_argument("--frames", default=str(here / "docs" / "frames.jsonl"))
    args = ap.parse_args(argv)
    held = open_paths(Path(args.engine) / "tmp")
    if held is None and args.apply:
        print("REFUSING: --apply needs lsof to prove no build holds a file",
              file=sys.stderr)
        return 2
    rows = candidates(args.engine, args.days, args.data_repo,
                      frame_paths(args.frames), held or ())
    total = 0
    for path, size, age, why in rows:
        total += size
        print(f"  {'KEEP ' + why if why else 'prune'}  {size / 1e6:10.1f} MB"
              f"  {age:6.1f} d  {path}")
    print(f"  [prune] {sum(1 for r in rows if not r[3])} entries older than "
          f"{args.days:g} d, {total / 1e9:.2f} GB private "
          f"{'freed' if args.apply else 'would be freed (dry run)'}")
    if args.apply:
        prune(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
