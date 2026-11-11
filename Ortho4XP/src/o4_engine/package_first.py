"""PACKAGE FIRST (#2014 follow-up; owner 2026-11-11T16:45Z: "Yes, when
"clearing" or compressing a tile, we should create a package for it.").

Every path that clears a BUILT tile's rebuild data or its downloaded
inputs writes the tile's package (``tile_bundle.package.save_package``,
the whole tile, no imagery) into the package store
(``storage_packages.store_dir``, ``Tile_packages/<tile>.xptb``) first,
unless the package there already holds every input the tile has now
(:func:`_covered`: each input at its current time — so a package is
never replaced by one written after some of its inputs went).  The
paths:

* every storage sweep (``storage._Sweep.delete``): Free space by hand
  (``storage_clear``), the automatic cleanup and the cache caps, and
  the disk budget's tiers — the elevation and map tier and the rebuild
  data tier (whose older airport tiles ``storage_packages`` shrinks to
  their package, through the same :class:`Pass`).  A file of the
  rebuild, elevation or per-tile map store names the tiles it belongs to
  (:func:`_tiles_of`);
* Library ▸ Delete (``library.library_delete``) and Library ▸ Free
  cache (``library.free_cache``);
* Convert existing tiles ▸ Free space… (``world_retire.purge``).

A tile is packaged once per pass, before the first of its files goes.
A tile that cannot be packaged (no map data left, a held source) is
cleared as before and ``storage.log`` says why.  Each package is
recorded in ``storage_packages.packaged`` as not yet restored, so the
next build of the tile installs it first (``storage_packages.restore``).
Making a tile dynamic (``world_retire.retire_tile``) clears nothing —
its row is disabled and a link to another drive removed, its data stays
— so it packages nothing; its Free space… does.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import re
import time

import O4_File_Names as FNAMES

__all__ = ["STORE_KINDS", "built_tiles", "Pass"]

#: The storage stores whose files are a built tile's rebuild data or inputs.
STORE_KINDS = ("rebuild", "elevation", "osm")

_CELL = re.compile(r"^([NS])(\d{2})([EW])(\d{3})")


def _covered(path: str, lat: int, lon: int) -> bool:
    """Whether the package at ``path`` already holds every input tile
    (lat, lon) has now (``tile_bundle.inputs.files``), each at its
    current time: then a new package would hold nothing more, and one
    written after some inputs went would hold less."""
    from tile_bundle import BundleRefused
    from tile_bundle import inputs as INPUTS
    from tile_bundle.install import read_manifest
    if not os.path.isfile(path):
        return False
    try:
        held = read_manifest(path).get("files") or {}
    except BundleRefused:
        return False
    for name, local in INPUTS.files(lat, lon):
        try:
            mtime = os.stat(local).st_mtime_ns
        except OSError:
            continue
        if (held.get(name) or {}).get("mtime_ns") != mtime:
            return False
    return True


def _cell(name: str):
    m = _CELL.match(name)
    if not m:
        return None
    lat = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lon = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    return lat, lon


def _parts(path: str, root: str) -> list:
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    return [] if rel.startswith("..") else rel.replace(os.sep, "/").split("/")


def _tiles_of(kind: str, path: str) -> list:
    """The tile whose rebuild data or own input the file ``path`` of
    store ``kind`` is (:data:`STORE_KINDS`; ``[]`` for any other).  A
    base elevation raster is its own cell's: the eight neighbours whose
    packages also carry it read it as a neighbour, a few megabytes their
    next build downloads again, and packaging all of them because one
    tile is cleared is not what was asked."""
    if kind == "rebuild":
        parts = _parts(path, FNAMES.rebuild_root())
        tile = FNAMES.parse_tile_key(parts[0].rsplit("_", 1)[-1]) if parts else None
        return [tile] if tile else []
    if kind == "osm":
        parts = _parts(path, FNAMES.OSM_dir)
        tile = FNAMES.parse_tile_key(parts[1]) if len(parts) >= 3 else None
        return [tile] if tile else []
    if kind == "elevation":
        parts = _parts(path, FNAMES.Elevation_dir)
        cell = _cell(parts[1]) if len(parts) >= 2 else None
        return [cell] if cell else []
    return []


def built_tiles() -> dict:
    """``{(lat, lon): build folder}`` of the tiles this app built in the
    data folder's tiles folder."""
    import O4_Tile_Info as TINFO
    return {pair: info.build_dir
            for pair, info in TINFO.scan_tiles(FNAMES.Tile_dir).items()
            if TINFO.built_here(info.build_dir, *pair)}


def _ensure(lat: int, lon: int, custom_build_dir: str = "",
           dry_run: bool = False) -> dict:
    """Tile (lat, lon)'s package in the store (module doc): ``{"tile",
    "action": "kept" | "packaged" | "would_package" | "refused", "path",
    "bytes", "why"}``."""
    from tile_bundle import BundleRefused
    from tile_bundle import package as PACKAGE

    from . import storage as STORAGE
    from . import storage_packages as STORE
    from .storage_packages import remember
    key = FNAMES.short_latlon(int(lat), int(lon))
    out = {"tile": key, "action": "kept", "path": "", "bytes": 0, "why": ""}
    row = STORE.packaged().get(key) or {}
    target = row.get("path") or os.path.join(STORE.store_dir(), key + ".xptb")
    if _covered(target, lat, lon):
        out["path"] = target
        return out
    if dry_run:
        out["action"] = "would_package"
        return out
    try:
        done = PACKAGE.save_package([(int(lat), int(lon))], target, custom_build_dir)
    except (BundleRefused, OSError, ValueError) as error:
        STORAGE.write_log("not packaged %s before clearing: %s" % (key, error))
        out.update(action="refused", why=str(error))
        return out
    remember(key, path=done["path"], package_bytes=int(done["bytes"]),
                   freed_bytes=0, airports=row.get("airports") or [],
                   utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   restored=False)
    STORAGE.write_log("packaged %s before clearing: %d bytes" % (key, done["bytes"]))
    out.update(action="packaged", path=done["path"], bytes=int(done["bytes"]))
    return out


class Pass:
    """One clearing pass: each built tile it touches packaged once,
    before the first of its files goes."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.done: dict = {}
        self._built = None

    def tile(self, lat: int, lon: int, custom_build_dir: str = "",
             built: bool = False) -> "dict | None":
        """:func:`_ensure` once for a tile; ``built``: the caller already
        knows this app built it (else it is looked up)."""
        pair = (int(lat), int(lon))
        if pair not in self.done:
            if not built:
                if self._built is None:
                    self._built = built_tiles()
                if pair not in self._built:
                    self.done[pair] = None
                    return None
            self.done[pair] = _ensure(*pair, custom_build_dir, self.dry_run)
        return self.done[pair]

    def before_delete(self, kind: str, path: str) -> int:
        """Package the built tiles a file of store ``kind`` belongs to;
        the package bytes written."""
        written = 0
        for pair in _tiles_of(kind, path) if kind in STORE_KINDS else ():
            if pair in self.done:
                continue
            done = self.tile(*pair)
            if done and done["action"] == "packaged":
                written += done["bytes"]
        return written
