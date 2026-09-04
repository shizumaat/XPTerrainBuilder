"""The scenery pack that serves an airport, and its SIGNATURE — apt.dat +
DSF ONLY (owner ruling, RULINGS :75; memory ``scenery-signature-apt-dsf-
only``): deep walks of a pack stay out.

Pack precedence is v1's (``find_airport_apt_dat``): a Custom Scenery
pack carrying the airport with row-110 pavement wins over Global
Airports (which lives under ``Global Scenery`` on XP12 and under
``Custom Scenery`` on XP11) — the 09-02 CYXY arm was built from the
``CYXY Whitehorse`` custom pack, and v2 must read the same authored
geometry to be compared with it.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import os

from ..model.airport import SceneryPack
from .apt_dat import block_sha256, find_apt_dat

__all__ = ["PackSelection", "select_pack", "tile_dsf_path", "signature",
           "sha256_file"]


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
