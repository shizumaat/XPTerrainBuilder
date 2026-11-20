"""THE PACK-CHOICES READING, HELD PER TILE (issue #2200).

Owner (2026-11-20): "Same as our other pack reads, e.g. at startup,
these should be cached and updated as things change, not re-read in
their entirety on every action" -- and only the selected tile's packs
are read.  ``overlap_stage._detect`` reads a tile's packs once; this
holds its rows under the tile's :func:`_signature` and answers every
later ask on the unchanged tile with no pack file opened.

The signature is ``O4_Custom_Scenery.folder_state`` (a pack installed,
removed, renamed, enabled or disabled) and, for each enabled pack with a
DSF on the tile (``O4_Custom_Scenery.tile_pack_names``), the stat
identity of its tile DSF, of that DSF's backup and of its apt.dat (a
pack updated in place).  Stats only: nothing is opened.  A write this
app makes itself (an answer rewriting a pack's DSF) re-signs the tile
(:func:`resign`): the reading of the pack as installed did not change.

Not seen until the folder changes: a pack already installed that GAINS
a DSF for the tile, or an off-tile pack's apt.dat edited in place (the
same-airport rows read every pack's idents once per folder state).
"""
from __future__ import annotations

import os
import threading
import typing as _t

from .apt_dat import _file_identity as _stat  # (mtime_ns, size) or None

__all__ = ["held", "keep", "resign"]

#: the backup ``dsf_write`` keeps beside a pack DSF it wrote
_BACKUP = ".anchor_bak"

#: ``{(folder, lat, lon): (signature, rows)}``
_MEMO: dict = {}
_LOCK = threading.Lock()


def _signature(scenery_dir: str, lat: int, lon: int) -> tuple:
    """The tile's packs as they stand (module doc): stats, no read."""
    import O4_Custom_Scenery as _CS
    import O4_Scenery_Packs as _SP

    from . import dsf as _dsf2
    packs = []
    for name in _CS.tile_pack_names(scenery_dir, lat, lon):
        root = os.path.join(scenery_dir, name)
        dsf = _dsf2.dsf_path_in_pack(root, lat, lon)
        packs.append((name, _stat(dsf), _stat(dsf + _BACKUP),
                      _stat(os.path.join(_SP.earth_nav_data(root), "apt.dat"))))
    return (_CS.folder_state(scenery_dir), tuple(packs))


def _key(scenery_dir: str, lat: int, lon: int) -> tuple:
    return (os.path.realpath(scenery_dir), int(lat), int(lon))


def held(scenery_dir: str, lat: int, lon: int) -> list[dict] | None:
    """The tile's rows when its signature has not moved, else ``None``."""
    with _LOCK:
        hit = _MEMO.get(_key(scenery_dir, lat, lon))
    if hit is None or hit[0] != _signature(scenery_dir, lat, lon):
        return None
    return [dict(r) for r in hit[1]]


def keep(scenery_dir: str, lat: int, lon: int, rows: _t.Sequence[dict]) -> None:
    """Hold the tile's fresh reading under its signature now."""
    sig = _signature(scenery_dir, lat, lon)
    with _LOCK:
        _MEMO[_key(scenery_dir, lat, lon)] = (sig, [dict(r) for r in rows])


def _without(sig: tuple, names: _t.Collection[str]) -> tuple:
    return (sig[0], tuple(p for p in sig[1] if p[0] not in names))


def resign(scenery_dir: str, lat: int, lon: int, names: _t.Collection[str]) -> None:
    """After this app's own write to the tile's packs ``names``: the held
    rows stand under the new signature when nothing else on the tile
    moved; otherwise they are dropped (the next ask reads the tile)."""
    key = _key(scenery_dir, lat, lon)
    sig = _signature(scenery_dir, lat, lon)
    with _LOCK:
        hit = _MEMO.get(key)
        if hit is None:
            return
        if _without(hit[0], names) == _without(sig, names):
            _MEMO[key] = (sig, hit[1])
        else:
            _MEMO.pop(key, None)
