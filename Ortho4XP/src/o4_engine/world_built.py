"""The built tiles of the World pack whose folders are not in the scanned
working folder (owner 2026-11-12T22:19Z: a tile a flight had just built
showed no patch view or editor when zoomed in).

The World and flight jobs build into the data folder's ``Tiles/``
(``O4_File_Names.build_dir(lat, lon, "")``) and Convert keeps a World
tile's records there (``world_records``).  A user whose build folder is
another one (a custom build folder, e.g. Custom Scenery itself) scanned
only that folder, so those tiles were never "built": no tile details, no
patch view or editor, nothing on the map after a flight built them.

:func:`iter_world_built` reads the data folder's ``Tiles/`` for the tiles
the World pack holds that the working folder did not list — the same
:class:`O4_Tile_Info.TileInfo` the working-folder pass reads, through the
same ``iter_scan_tiles``.  When the two folders are one, it reads nothing.
:func:`tile_info` is the same rule for one tile: the ONE "is it built"
answer the tile commands share (#2027: an adopted World tile's Favorite
said "not built" because ``imagery_pin`` read only the working folder).
No tile or airport is named here.
"""
from __future__ import annotations

import os
from typing import Collection, Iterator, Optional, Tuple

import O4_File_Names as FNAMES
import O4_Tile_Info as TINFO

__all__ = ["iter_world_built", "tile_info"]


def _world_tiles_dir() -> str:
    """The folder the World and flight jobs build into (no custom folder)."""
    return os.path.dirname(FNAMES.build_dir(0, 0, ""))


def _same_folder(a: str, b: str) -> bool:
    try:
        return os.path.realpath(a) == os.path.realpath(b)
    except (OSError, ValueError):
        return False


def iter_world_built(
    working_dir: str, world: Collection[Tuple[int, int]],
    found: Collection[Tuple[int, int]], tiles_dir: Optional[str] = None,
) -> "Iterator[tuple[int, int, Optional[tuple[int, int]], Optional[TINFO.TileInfo]]]":
    """``iter_scan_tiles`` of the World jobs' folder (*tiles_dir*, default
    :func:`_world_tiles_dir`), keeping only tiles in *world* and not in
    *found*; nothing when it is *working_dir*."""
    tiles_dir = tiles_dir or _world_tiles_dir()
    if not world or not os.path.isdir(tiles_dir) or _same_folder(tiles_dir, working_dir):
        return
    for done, total, key, info in TINFO.iter_scan_tiles(tiles_dir):
        if key is not None and (key not in world or key in found):
            key = info = None
        yield done, total, key, info


def tile_info(lat: int, lon: int, working_dir: str,
              scenery_dir: Optional[str] = None,
              tiles_dir: Optional[str] = None) -> Optional[TINFO.TileInfo]:
    """The tile's :class:`O4_Tile_Info.TileInfo` in *working_dir*; else,
    when the World pack in *scenery_dir* (default: the setting's) holds
    the tile, its folder in the World jobs' *tiles_dir* -- the tile the
    scan lists (:func:`iter_world_built`); None when neither has it."""
    info = TINFO.tile_info(int(lat), int(lon), working_dir) if working_dir else None
    if info is not None:
        return info
    tiles_dir = tiles_dir or _world_tiles_dir()
    if not os.path.isdir(tiles_dir) or _same_folder(tiles_dir, working_dir or ""):
        return None
    from . import storage_redundant
    from .world_state import read_tile
    if scenery_dir is None:
        scenery_dir = storage_redundant._custom_scenery_dir()
    if read_tile(scenery_dir, (lat, lon)) is None:
        return None
    return TINFO.tile_info(int(lat), int(lon), tiles_dir)
