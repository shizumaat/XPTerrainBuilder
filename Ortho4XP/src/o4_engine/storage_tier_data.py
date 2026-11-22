"""Rebuild data on a storage tier (owner 2026-11-14T17:01Z, #2087, on
RULINGS 2026-11-12g's optional tiered storage):

    "external drives can be used to store things needed to rebuild tiles
    as well, priority being keeping the ability to fly without the
    external drive and not see a difference in the sim."

* :func:`keep` -- a cache file the disk budget clears (``storage._Sweep.
  delete``: rebuild data, orthophotos, texture-cache entries, elevation
  and map data, masks) MOVES to the first mounted tier with room instead
  of being deleted.  It lands at ``<mount>/XPTerrainBuilder Tier/<store
  folder>/<path in the store>`` -- the texture cache's entries at the
  very place ``storage_tiers.find`` already reads them (one store).  The
  tier's own size is its budget: when it is full, its files used longest
  ago go first (:func:`_make_room`), never one used more recently than
  the file coming in (that file is deleted instead, as without a tier).
  The clearing reaches files in tile priority order
  (``storage_priority``), so the tier keeps the most wanted tiles.
* :func:`recall_tile` -- a build step of a tile lays back, from a
  mounted tier, whatever of its map data, elevation (its cell, and the
  base rasters of its eight neighbours), masks, orthophotos and rebuild
  data is missing locally (``session._run_step``), so it downloads only
  what no tier holds.  An absent tier is no source: the build downloads.

FLYING NEVER NEEDS THE TIER (RULINGS 2026-11-12a (1)): only a CACHE
store's file under the data folder moves (:func:`_movable`) -- never a
built tile, a DSF, a placeholder or a texture the sim draws, never the
on-demand store and never anything in Custom Scenery or the World pack;
nothing on a tier is linked anywhere.  Unplugging the drive changes
nothing X-Plane loads.

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import os
import shutil

import O4_File_Names as FNAMES

from . import storage_tiers as TIERS
from .storage import _last_used

__all__ = ["MOVABLE_KINDS", "keep", "recall_tile"]

#: The cache stores whose files may move to a tier (``storage.STORES``
#: kinds): what rebuilds a tile, never what X-Plane reads.
MOVABLE_KINDS = ("imagery", "dds", "elevation", "osm", "masks", "rebuild")


def _root(mount: str) -> str:
    return os.path.join(mount, TIERS.TIER_DIR)


def _target(mount: str, store_root: str, path: str) -> str:
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(store_root))
    return os.path.normpath(os.path.join(_root(mount), os.path.basename(
        os.path.normpath(store_root)), rel))


def _under(path: str, root: str) -> bool:
    if not root:
        return False
    root = os.path.join(os.path.normcase(os.path.abspath(root)), "")
    return os.path.normcase(os.path.abspath(path)).startswith(root)


def _movable(kind: str, store_root: str, path: str) -> bool:
    """A file of a movable cache store, inside it, and never inside the
    tiles folder, the World home or Custom Scenery (the flyable side)."""
    if kind not in MOVABLE_KINDS or not _under(path, store_root):
        return False
    flyable = [FNAMES.Tile_dir, FNAMES.world_home()]
    with contextlib.suppress(Exception):
        from .storage_redundant import _custom_scenery_dir
        flyable.append(_custom_scenery_dir())
    return not any(_under(path, root) for root in flyable if root)


def _tier_files(mount: str) -> list:
    """``(last used, size, path)`` of every file a tier holds, used
    longest ago first."""
    rows = []
    for folder, _dirs, names in os.walk(_root(mount)):
        for name in names:
            path = os.path.join(folder, name)
            with contextlib.suppress(OSError):
                st = os.lstat(path)
                rows.append((_last_used(st), st.st_size, path))
    rows.sort()
    return rows


def _make_room(mount: str, size: int, cap: float, used_at: float) -> bool:
    """Free the tier until ``size`` more bytes fit under ``cap``, its
    files used longest ago first and none used at or after ``used_at``;
    whether they fit."""
    room = cap - TIERS._used(mount)
    if size <= room:
        return True
    for last, nbytes, path in _tier_files(mount):
        if last >= used_at or size <= room:
            break
        with contextlib.suppress(OSError):
            os.remove(path)
            TIERS._add_used(mount, -nbytes)
            room += nbytes
    return size <= room


def _copy(source: str, target: str) -> bool:
    """``source`` copied to ``target`` (times kept) under a partial
    name, checked, then renamed; whether it is there."""
    partial = target + ".part"
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, partial)
        if os.path.getsize(partial) != os.path.getsize(source):
            raise OSError("short copy")
        os.replace(partial, target)
        return True
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(partial)
        return False


def keep(kind: str, store_root: str, path: str, st: os.stat_result) -> str:
    """Move the file ``path`` of store ``kind`` (rooted at
    ``store_root``) to the first mounted tier with room; where it is now,
    or ``""`` (no tier took it: the caller deletes it as before)."""
    if not _movable(kind, store_root, path):
        return ""
    for mount, gigabytes in TIERS._configured().items():
        if not TIERS._mounted(mount):
            continue                        # absent: deleted as before
        if not _make_room(mount, st.st_size, gigabytes * TIERS._GB,
                          _last_used(st)):
            continue
        target = _target(mount, store_root, path)
        if not _copy(path, target):
            continue
        try:
            os.remove(path)
        except OSError:
            with contextlib.suppress(OSError):
                os.remove(target)
            return ""
        TIERS._add_used(mount, st.st_size)
        return target
    return ""


def _recall_tree(store_root: str, local: str, accept=None) -> int:
    """Copy back every file a mounted tier holds under ``local`` (a
    folder of ``store_root``) that is missing locally -- only those whose
    path relative to ``local`` ``accept`` takes, when given; the files
    laid back."""
    count = 0
    for mount in TIERS._configured():
        if not TIERS._mounted(mount):
            continue
        source_root = _target(mount, store_root, local)
        for folder, _dirs, names in os.walk(source_root):
            for name in names:
                source = os.path.join(folder, name)
                rel = os.path.relpath(source, source_root)
                if name.endswith(".part") or (accept and not accept(rel)):
                    continue
                dest = os.path.join(local, rel)
                if not os.path.exists(dest) and _copy(source, dest):
                    count += 1
    return count


def _elevation(lat: int, lon: int) -> int:
    """The tile's own cell entries (every file or folder named for it)
    and its neighbours' base rasters (files at the block's top level)."""
    count = 0
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            cell_lat, cell_lon = lat + dlat, (lon + dlon + 180) % 360 - 180
            if not -90 <= cell_lat < 90:
                continue
            stem = FNAMES.hem_latlon(cell_lat, cell_lon)
            own = (dlat, dlon) == (0, 0)

            def accept(rel, stem=stem, own=own):
                named = rel == stem or rel.startswith((stem + "_", stem + "."))
                return named and (own or os.sep not in rel)
            count += _recall_tree(FNAMES.Elevation_dir, os.path.dirname(
                FNAMES.base_file_name(cell_lat, cell_lon)), accept)
    return count


def recall_tile(lat: int, lon: int) -> int:
    """Lay back from the mounted tiers what tile (lat, lon) is missing
    of its map data, elevation, masks, orthophotos and rebuild data; the
    files laid back (0 at once when no tier is set)."""
    if not TIERS._configured():
        return 0
    lat, lon = int(lat), int(lon)
    key = FNAMES.short_latlon(lat, lon)
    count = _recall_tree(FNAMES.OSM_dir, FNAMES.osm_dir(lat, lon))
    count += _recall_tree(FNAMES.masks_root(), FNAMES.mask_dir(lat, lon))
    count += _recall_tree(FNAMES.Imagery_dir, os.path.join(
        FNAMES.Imagery_dir, FNAMES.long_latlon(lat, lon)))
    count += _elevation(lat, lon)
    rebuild = FNAMES.rebuild_root()
    for mount in TIERS._configured():
        with contextlib.suppress(OSError):
            for name in os.listdir(_target(mount, rebuild, rebuild)):
                if name == key or name.endswith("_" + key):
                    count += _recall_tree(rebuild, os.path.join(rebuild, name))
    return count
