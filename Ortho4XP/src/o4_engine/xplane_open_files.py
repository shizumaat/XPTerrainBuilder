"""Is X-Plane loading a World-pack tile right now (#2175, RULINGS
2026-11-19e)?

The owner (2026-11-19T01:06Z): a new tile may go into the World folder
while X-Plane runs "unless x-plane is in the middle of loading that
specific dsf".  X-Plane reads a DSF, its ``.ter`` files and textures and
closes them (an X-Plane 12 session with the World pack loaded held none
open, measured 2026-11-18 with ``lsof``), so a tile is being loaded
exactly while an X-Plane process holds one of its files open:

* :func:`open_paths` -- the files the X-Plane processes hold open: macOS
  ``lsof -p`` (one call for every process), Linux ``/proc/<pid>/fd``.
  Windows has no handle listing in the standard library and
  ``xplane_root.xplane_pids`` finds no process there: nothing counts as
  loading (the swap goes in at once).
* :func:`loading` -- the predicate ``O4_World_Pack.publish`` /
  ``swap_staged`` keep a tile staged by: its DSF, or a file under its
  ``terrain/<tile>`` or ``textures/<tile>`` folder, is open now.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Callable, Iterable, Optional

import O4_World_Pack as WP

__all__ = ["loading"]


def _lsof(pids: Iterable[int]) -> set:
    import O4_UI_Utils as UI
    try:
        command = ["lsof", "-n", "-P", "-Fn", "-p",
                   ",".join(str(p) for p in pids)]
        done = subprocess.run(
            command,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=20,
            **UI.external_tool_keyword_arguments(command))
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line[1:] for line in done.stdout.splitlines()
            if line.startswith("n/")}


def _proc_fds(pids: Iterable[int]) -> set:
    out = set()
    for pid in pids:
        folder = f"/proc/{pid}/fd"
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            try:
                out.add(os.readlink(os.path.join(folder, name)))
            except OSError:
                continue
    return out


def open_paths(pids: Optional[Iterable[int]] = None) -> set:
    """The real paths of the files X-Plane holds open now (``pids``:
    default the running X-Plane processes); empty when none runs."""
    if pids is None:
        from . import xplane_root as XROOT
        pids = XROOT.xplane_pids()
    pids = [int(p) for p in pids]
    if not pids:
        return set()
    paths = _proc_fds(pids) if sys.platform.startswith("linux") else _lsof(pids)
    return {os.path.realpath(p) for p in paths}


def _tile_roots(pack: str, lat: int, lon: int) -> tuple:
    tile = WP.tile_name(lat, lon)
    pack = os.path.realpath(pack)
    return (os.path.join(pack, WP.dsf_relpath(lat, lon)),
            os.path.join(pack, "terrain", tile) + os.sep,
            os.path.join(pack, "textures", tile) + os.sep)


def loading(pack: str, paths: Optional[Callable[[], set]] = None
            ) -> Callable[[int, int], bool]:
    """The predicate of RULINGS 2026-11-19e for one moment: is X-Plane
    loading tile ``(lat, lon)`` of ``pack`` (one of its files open)?
    ``paths`` (default :func:`open_paths`) is read once, on the first
    question."""
    held: list = []

    def answer(lat: int, lon: int) -> bool:
        if not held:
            held.append((paths or open_paths)())
        dsf, terrain, textures = _tile_roots(pack, lat, lon)
        return any(p == dsf or p.startswith(terrain) or p.startswith(textures)
                   for p in held[0])
    return answer
