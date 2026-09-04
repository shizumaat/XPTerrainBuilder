"""The scenery pack that serves an airport, and its SIGNATURE — apt.dat +
DSF ONLY (owner ruling, RULINGS :75; memory ``scenery-signature-apt-dsf-
only``): deep walks of a pack stay out.

Pack precedence is v1's (``find_airport_apt_dat``): a Custom Scenery
pack carrying the airport with row-110 pavement wins over Global
Airports (which lives under ``Global Scenery`` on XP12 and under
``Custom Scenery`` on XP11) — the 09-02 CYXY arm was built from the
``CYXY Whitehorse`` custom pack, and v2 must read the same authored
geometry to be compared with it.

RESTORE BEFORE READ (RULINGS 2026-09-04i 04f-1; ``structures.toml
[rebake] restore_before_read``): a pack a previous build re-baked
carries, beside every rewritten ``.obj``, the AUTHORED file as
``<name>.anchor_bak`` (v1 ``object_rebake.BACKUP_SUFFIX``, created once
from the authored bytes and never overwritten with a bake).  v2 reads
THAT file — the pack as its author shipped it — never the previously
re-baked state on disk (m4b-report §9 Q1: LEMD's T4S read +3.42 m off
because the live file was the bake).  This is a READ-side restore: the
pack is not written during the patch build; the re-bake after the mesh
(``emit/rebake.py``) is what writes, through the same backup discipline.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import os

from ..model.airport import SceneryPack
from .apt_dat import block_sha256, find_apt_dat

__all__ = ["PackSelection", "select_pack", "tile_dsf_path", "signature",
           "sha256_file", "AUTHORED_BACKUP_SUFFIX", "authored_source",
           "is_authored_backup", "live_path_of"]

#: v1's backup suffix (``object_rebake.BACKUP_SUFFIX``) — the one file
#: format both engines share; spelled here so v2 imports nothing of v1.
AUTHORED_BACKUP_SUFFIX = ".anchor_bak"


def authored_source(path: str | None) -> tuple[str | None, bool]:
    """``(path_to_read, restored)``: the ``.anchor_bak`` beside ``path``
    when one exists (the authored geometry; ``restored`` True), else
    ``path`` itself.  A path that already names a backup is returned
    unchanged.  ``None`` passes through (an unresolved placement)."""
    if not path or path.endswith(AUTHORED_BACKUP_SUFFIX):
        return path, False
    bak = path + AUTHORED_BACKUP_SUFFIX
    if os.path.isfile(bak):
        return bak, True
    return path, False


def is_authored_backup(path: str) -> bool:
    return path.endswith(AUTHORED_BACKUP_SUFFIX)


def live_path_of(path: str) -> str:
    """The pack file a bake WRITES for a path the loader read: the live
    ``.obj`` beside an ``.anchor_bak``, else the path itself."""
    return path[:-len(AUTHORED_BACKUP_SUFFIX)] if is_authored_backup(path) else path


@_dc.dataclass(frozen=True)
class PackSelection:
    """``root`` is the pack directory (the one holding ``Earth nav
    data``); ``name`` its folder name (also the ``Airport_mod_cache``
    sub-directory); ``custom`` whether it is a Custom Scenery pack."""

    name: str
    root: str
    apt_dat_path: str
    custom: bool


def select_pack(xplane_root: str, icao: str) -> PackSelection | None:
    """The pack whose apt.dat serves ``icao`` (see module docstring)."""
    apt = find_apt_dat(xplane_root, icao)
    if apt is None:
        return None
    root = os.path.dirname(os.path.dirname(apt))
    name = os.path.basename(root)
    custom = os.path.basename(os.path.dirname(root)) == "Custom Scenery" \
        and name != "Global Airports"
    return PackSelection(name, root, apt, custom)


def tile_dsf_path(pack_root: str, lat: int, lon: int) -> str | None:
    """``<pack>/Earth nav data/+60-140/+60-136.dsf`` when present."""
    p = os.path.join(pack_root, "Earth nav data",
                     f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}",
                     f"{lat:+03d}{lon:+04d}.dsf")
    return p if os.path.isfile(p) else None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def signature(sel: PackSelection, block: list[str], lat: int,
              lon: int) -> SceneryPack:
    """The pack signature: the airport's own apt.dat block hash (the
    whole Global file is hundreds of MB; the block is what is read) and
    the tile DSF's file hash."""
    dsf = tile_dsf_path(sel.root, lat, lon)
    paths = (dsf,) if dsf else ()
    return SceneryPack(sel.name, sel.apt_dat_path, block_sha256(block),
                       paths, tuple(sha256_file(p) for p in paths))
