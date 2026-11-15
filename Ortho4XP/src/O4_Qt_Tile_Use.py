"""The Qt app's "Use XPTerrainBuilder here" (#2100; Mac:
``BuildModel.setUseHere``): the engine's ``world_tile_use`` run in process
and the note to show.  No widget: the tile menu (``O4_Qt_Tile_Menu``)
offers it and the window (``O4_Qt_GUI``) shows the note and rescans.
"""
from __future__ import annotations

import O4_World_State_Text as TEXT

__all__ = ["set_use"]


def set_use(tile, use: bool, scenery_dir: str) -> str:
    """XPTerrainBuilder on or off on ``tile`` (lat, lon); the note to show
    (the refusal's sentence when the engine refuses)."""
    from o4_engine.world_tile_use import world_tile_use
    try:
        return TEXT.use_note(world_tile_use(tile[0], tile[1], use=use,
                                            scenery_dir=scenery_dir))
    except (OSError, ValueError) as error:
        return str(error)
