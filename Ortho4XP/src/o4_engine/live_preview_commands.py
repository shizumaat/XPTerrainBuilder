"""The map's "Live flight preview" commands (#2001, capability
``live_preview``): the engine reads the installed textures, both apps
draw what it returns (``O4_Live_Preview`` holds the rule and the read).

* ``live_preview_squares {south, west, north, east, px_per_deg,
  scenery_dir?}`` -- sync: the squares to draw for the viewport
  (``O4_Live_Preview.squares``), each with its texture path, stamp and
  mip size.  An app asks again when the view moves and when the follow
  job lands a tier (``ImageryFollowStatus.landed`` grows); a square whose
  stamp changed is fetched again.
* ``live_preview_mip {path, px?}`` -- sync: one mip of one square,
  ``{width, height, format, data}`` (base64 JPEG/PNG, ~20 KB at 256 px).

A tile's textures are read where X-Plane reads them: the on-demand index
rows' folder (``O4_Imagery_OnDemand_Index.texture_path``; a tile
published into the World pack names the pack's folder there), the World
pack's ``textures/<tile>`` and the tile's ``zOrtho4XP_<tile>`` pack in
Custom Scenery (``scenery_dir``, else the app's ``custom_scenery_dir``
setting).  The index is read, never created.

A command module, not a session method (``imagery_commands`` gives the
reason): it stays out of the session's import closure.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any, Callable, Dict

__all__ = ["live_preview_handlers", "live_preview_squares",
           "live_preview_mip", "tile_folders"]


def _index_dirs(conn, tile: str) -> list:
    import O4_Imagery_OnDemand_Index as INDEX

    out = []
    for row in INDEX.rows(conn, tile=tile):
        path = INDEX.texture_path(row)
        folder = os.path.dirname(path) if path else ""
        if folder and folder not in out:
            out.append(folder)
    return out


def tile_folders(scenery_dir: str, conn=None) -> Callable[[int, int], list]:
    """``(lat, lon) -> [texture folder]`` for :func:`O4_Live_Preview.
    squares`, in the order the module docstring gives."""
    import O4_Live_Preview as LIVE
    import O4_World_Pack as WP

    from .storage_installed import PREFIX
    from .world_commands import pack_dir

    def folders(lat: int, lon: int) -> list:
        tile = WP.tile_name(lat, lon)
        candidates = _index_dirs(conn, tile) if conn is not None else []
        if scenery_dir:
            candidates += [os.path.join(pack_dir(scenery_dir), "textures", tile),
                           os.path.join(scenery_dir, PREFIX + tile, "textures")]
        return LIVE.existing_dirs(candidates)
    return folders


def live_preview_squares(south: float, west: float, north: float,
                         east: float, px_per_deg: float,
                         scenery_dir: str = "") -> Dict[str, Any]:
    """See the module docstring."""
    import O4_Imagery_OnDemand_Index as INDEX
    import O4_Live_Preview as LIVE

    from .world_commands import scenery_dir_or_default

    scenery = scenery_dir_or_default(scenery_dir)
    conn = None
    with contextlib.suppress(Exception):          # no index: none read
        if os.path.isfile(INDEX.index_path()):
            conn = INDEX.open_index()
    try:
        return LIVE.squares(float(south), float(west), float(north),
                            float(east), float(px_per_deg),
                            tile_folders(scenery, conn))
    finally:
        if conn is not None:
            conn.close()


def live_preview_mip(path: str, px: int = 256) -> Dict[str, Any]:
    """See the module docstring."""
    import O4_Live_Preview as LIVE

    return LIVE.mip_image(str(path), int(px))


def live_preview_handlers() -> Dict[str, Callable]:
    """This module's entries for the command table."""
    return {"live_preview_squares": live_preview_squares,
            "live_preview_mip": live_preview_mip}
