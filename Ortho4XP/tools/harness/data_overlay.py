"""THE LANE-LOCAL ELEVATION VIEW (issue #156): a declared overlay that the
engine can actually read.

``tools/v2_solve_replay.py --capture ICAO --data-overlay DIR`` declares a
lane-local data root whose ``Elevation_data`` / ``OSM_data`` take
precedence over the shared corpus's.  ``OSM_data`` is read through
``Inputs.osm_root`` and took effect from the start.  ``Elevation_data``
did not: the capture composes its DEM in the PRODUCTION frame through the
core, the core reads ``FNAMES.Elevation_dir``, and
``airport/dem_production._check_corpus`` refuses an ``elevation_root``
that is not that directory (RULINGS ``e9daef5`` — one corpus per read).
So the provider-inset case the issue was filed for refused, and lanes
kept swapping the worktree's ``Elevation_data`` symlink by hand.

This module builds ONE directory both sides can name: a lane-local VIEW
of the shared ``Elevation_data`` in which every entry is a SYMLINK — to
the overlay where the overlay carries that path, to the shared corpus
everywhere else — and a real directory only where both carry the same
directory and their children must be merged.  The capture points the
core's ``Elevation_dir`` and ``Inputs.elevation_root`` at the view, so the
engine's own one-corpus check still holds (and still refuses if anything
re-points the core afterwards).  No engine code changes, no symlink of
the worktree is touched, nothing in the shared repo is written: the view
lives under the lane's own ``tmp/`` and holds directories and links (and
whatever ``.lock`` the engine drops into its merged directories).

Granularity is the FILE: an overlay's ``index.json`` replaces the shared
one for that tile directory — the overlay is what the lane declares it
to be, whole.  The overlay's files are hashed into the frame
(:func:`overlay_manifest`) so a replay can tell an overlay that changed
or vanished since the capture (:func:`stale_reason`) and refuse by name.

Pure standard library; no engine import (the capture's cache redirects
must precede that import, lane ``v2padqp``).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

__all__ = ["VIEW_MARKER", "SIDECAR_SUFFIX", "overlay_manifest", "view_conflicts",
           "compose_view", "stale_reason", "write_sidecar", "read_sidecar"]

#: written at the view root so :func:`compose_view` only ever clears a
#: directory it built itself
VIEW_MARKER = ".o4_overlay_view.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def overlay_manifest(overlay_dir, subdirs) -> dict[str, str]:
    """``{relative posix path: sha256}`` of every FILE under the named
    ``subdirs`` of ``overlay_dir`` (symlinks followed — a lane may link a
    provider's output in).  Only the named subdirs: a provided directory
    that IS the shared corpus under another name is never walked."""
    root = Path(overlay_dir)
    out: dict[str, str] = {}
    for sub in subdirs:
        for dirpath, _dirs, files in os.walk(root / sub, followlinks=True):
            for name in files:
                p = Path(dirpath) / name
                out[p.relative_to(root).as_posix()] = _sha256(p)
    return dict(sorted(out.items()))


def view_conflicts(shared_dir, overlay_dir) -> str | None:
    """Why ``overlay_dir`` cannot be laid over ``shared_dir``, or ``None``.

    The one refusal: a path that is a directory on one side and a file on
    the other — the overlay would hide a whole subtree, or a subtree
    would hide the overlay's file, and neither is an overlay."""
    shared, over = Path(shared_dir), Path(overlay_dir)
    for dirpath, dirs, files in os.walk(over, followlinks=True):
        rel = Path(dirpath).relative_to(over)
        for name in dirs:
            s = shared / rel / name
            if s.exists() and not s.is_dir():
                return (f"{(rel / name).as_posix()} is a directory in the overlay "
                        f"and a file in the shared corpus ({s})")
        for name in files:
            if (shared / rel / name).is_dir():
                return (f"{(rel / name).as_posix()} is a file in the overlay and "
                        f"a directory in the shared corpus ({shared / rel / name})")
    return None


def _clear_view(view_root: Path) -> None:
    """Remove a view this module built.  Only a directory carrying the
    marker is touched, and the walk NEVER descends a link: a link is
    unlinked (its target — shared corpus or overlay — is untouched), a
    real file is one the engine wrote INTO the view's own merged
    directories during a capture (a ``.lock``), lane-local by
    construction."""
    if not (view_root / VIEW_MARKER).is_file():
        raise SystemExit(f"REFUSING: {view_root} exists and is not an overlay view "
                         f"(no {VIEW_MARKER}); not clearing it")
    for dirpath, dirs, files in os.walk(view_root, topdown=False):
        d = Path(dirpath)
        for name in files + dirs:
            p = d / name
            if p.is_symlink() or not p.is_dir():
                p.unlink()
            else:
                p.rmdir()
    view_root.rmdir()


def _merge(shared: Path, over: Path, view: Path) -> None:
    """Lay ``over`` onto ``shared`` at ``view`` (a fresh directory)."""
    names = set(os.listdir(over))
    if shared.is_dir():
        names |= set(os.listdir(shared))
    for name in sorted(names):
        o, s, v = over / name, shared / name, view / name
        if o.exists() and s.is_dir() and o.is_dir():
            v.mkdir()
            _merge(s, o, v)
        elif o.exists():
            v.symlink_to(o.resolve(), target_is_directory=o.is_dir())
        else:
            v.symlink_to(s, target_is_directory=s.is_dir())


def compose_view(shared_dir, overlay_dir, view_parent) -> Path:
    """Build the view of ``shared_dir`` with ``overlay_dir`` laid over it,
    at ``<view_parent>/<hash of the overlay path>/<basename of shared_dir>``,
    and return that path.  Rebuilt on every call (a view is links only,
    cheap), so whatever the shared corpus gained since the last capture
    shows, and one overlay always has one view path."""
    shared, over = Path(shared_dir).resolve(), Path(overlay_dir).resolve()
    why = view_conflicts(shared, over)
    if why:
        raise SystemExit(f"REFUSING the data overlay {over}: {why}")
    root = Path(view_parent) / hashlib.sha256(str(over).encode()).hexdigest()[:16]
    if root.exists():
        _clear_view(root)
    root.mkdir(parents=True)
    (root / VIEW_MARKER).write_text(
        json.dumps({"shared": str(shared), "overlay": str(over)},
                   indent=1, sort_keys=True) + "\n", encoding="utf-8")
    view = root / shared.name
    view.mkdir()
    _merge(shared, over, view)
    return view


def stale_reason(overlay_dir, files: dict[str, str], subdirs) -> str | None:
    """Why the overlay a capture recorded (``files`` from
    :func:`overlay_manifest` over ``subdirs`` at capture time) is no longer
    that overlay — the FIRST file missing, changed or added, by name — or
    ``None``."""
    d = Path(overlay_dir)
    if not d.is_dir():
        return f"the overlay directory {d} no longer exists"
    now = overlay_manifest(d, subdirs)
    for rel, sha in files.items():
        if rel not in now:
            return f"{rel} is missing from the overlay {d}"
        if now[rel] != sha:
            return f"{rel} changed in the overlay {d} (sha {sha[:12]} -> {now[rel][:12]})"
    extra = sorted(set(now) - set(files))
    if extra:
        return f"{extra[0]} was added to the overlay {d} after the capture"
    return None


#: the capture's overlay record, beside the pickle, so ``frames.py
#: register`` can carry it without unpickling engine objects
SIDECAR_SUFFIX = ".overlay.json"


def write_sidecar(capture_path, frame: dict | None) -> Path:
    """Write ``<capture>.overlay.json`` — the overlay frame, or ``null``
    for a capture on the shared corpus alone."""
    side = Path(str(capture_path) + SIDECAR_SUFFIX)
    side.write_text(json.dumps({"data_overlay": frame}, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    return side


def read_sidecar(capture_path) -> dict | None:
    """``{"data_overlay": frame-or-None}``, or ``None`` when the capture has
    no sidecar (it predates issue #156's record: corpus unknown)."""
    side = Path(str(capture_path) + SIDECAR_SUFFIX)
    if not side.is_file():
        return None
    return json.loads(side.read_text(encoding="utf-8"))
