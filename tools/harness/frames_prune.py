"""frames_prune — age out the durable frames store (owner 2026-11-16).

A lane dir ``<frames root>/<lane>`` older than ``--days`` (mtime) is:

* KEPT when cited — by a repo file (docs/specs/tools/tests/scripts/.claude;
  ``docs/frames.jsonl`` itself does not count), by a live lane worktree's
  ``docs/tmp``, or as the latest registered row of any (icao, kind);
  a cited dir is MOVED to the storage tier (``<tier>/<lane>``) with a
  symlink left behind, or stays local when the tier is not mounted;
* DELETED otherwise.

Every frames root is handled (the shared data repo and its APFS clone,
#2093): deleting in one frees nothing while the clone holds the blocks.
Dry run by default; ``lane_worktree.sh down`` runs it with ``--apply``.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time

#: The storage tier frames move to (env ``O4_FRAMES_TIER`` overrides).
DEFAULT_TIER = "/Volumes/ThunderBlade/XPTerrainBuilderFrames"
#: The #2093 clone of the data repo sits beside it under this name.
CLONE_NAME = "XPTerrainBuilderDevData"
_CITE = re.compile(r"\.harness/frames/([0-9A-Za-z_.+-]+)")
_REPO_DIRS = ("docs", "tools", "scripts", ".claude", "Ortho4XP/docs",
              "Ortho4XP/tools", "Ortho4XP/tests", "Ortho4XP/src")


def frames_roots(durable: str) -> list[str]:
    """The durable root plus the clone's, when the clone exists."""
    env = os.environ.get("O4_FRAMES_ROOTS")
    if env:
        return [p for p in env.split(os.pathsep) if p]
    clone = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(durable))),
                         CLONE_NAME, ".harness", "frames")
    return [durable] + ([clone] if os.path.isdir(clone) and
                        os.path.realpath(clone) != os.path.realpath(durable) else [])


def _cites_in(text: str) -> set[str]:
    return set(_CITE.findall(text))


def cited_lanes(repo: str, registry: str, worktrees: str) -> set[str]:
    """Lane names cited by repo files and by live worktrees' docs/tmp."""
    out: set[str] = set()
    reg = os.path.realpath(registry)
    trees = [(repo, _REPO_DIRS)]
    if os.path.isdir(worktrees):
        trees += [(os.path.join(worktrees, w), ("docs/tmp",))
                  for w in sorted(os.listdir(worktrees))]
    for base, subs in trees:
        for sub in subs:
            top = os.path.join(base, sub)
            for dirpath, dirs, files in os.walk(top):
                dirs[:] = [d for d in dirs if d not in (".git", "venv", "__pycache__")]
                for f in files:
                    p = os.path.join(dirpath, f)
                    if os.path.realpath(p) == reg or os.path.islink(p):
                        continue
                    try:
                        if os.path.getsize(p) > 20_000_000:
                            continue
                        with open(p, encoding="utf-8", errors="ignore") as fh:
                            out |= _cites_in(fh.read())
                    except OSError:
                        continue
    return out


def latest_lanes(rows: list[dict]) -> set[str]:
    """Lanes holding the latest registered row of any (icao, kind)."""
    last: dict[tuple, dict] = {}
    for r in rows:
        last[(r.get("icao"), r.get("kind"))] = r
    return set().union(*(_cites_in(r.get("path", "")) for r in last.values())) if last else set()


def _bytes(path: str) -> int:
    total = 0
    for dirpath, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def plan(roots: list[str], days: float, keep: set[str], now: float | None = None):
    """[(action, path, bytes)] with action 'delete' or 'move'."""
    cutoff = (now or time.time()) - days * 86400
    out = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if os.path.islink(p) or not os.path.isdir(p) or os.stat(p).st_mtime > cutoff:
                continue
            out.append(("move" if name in keep else "delete", p, _bytes(p)))
    return out


def _rmtree(path: str) -> None:
    for _ in range(3):  # a Finder .DS_Store can land mid-delete
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return
    shutil.rmtree(path)


def apply(items, tier: str) -> list[str]:
    """Carry out ``plan``; a move with the tier unmounted stays local."""
    mounted = os.path.isdir(os.path.dirname(tier.rstrip("/"))) or os.path.isdir(tier)
    log = []
    for action, path, _n in items:
        if action == "delete":
            _rmtree(path)
            log.append(f"deleted {path}")
            continue
        if not mounted:
            log.append(f"kept {path} (tier {tier} not mounted)")
            continue
        dest = os.path.join(tier, os.path.basename(path))
        os.makedirs(tier, exist_ok=True)
        if os.path.exists(dest):   # the other root already moved it
            _rmtree(path)
        else:
            subprocess.run(["mv", path, dest], check=True)
        os.symlink(dest, path)
        log.append(f"moved {path} -> {dest}")
    return log


def report(items) -> str:
    lines = []
    for act in ("delete", "move"):
        sel = [i for i in items if i[0] == act]
        gb = sum(i[2] for i in sel) / 1e9
        lines.append(f"{act}: {len(sel)} dirs, {gb:.2f} GB")
        lines += [f"  {p}  {n / 1e9:.2f} GB" for _a, p, n in sel]
    return "\n".join(lines)
