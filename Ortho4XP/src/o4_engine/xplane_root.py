"""The X-Plane install a tile's build reads — light on purpose (#1989):
the session's build hooks resolve it without importing the pack-object
readers (``pack_objects`` re-exports it for its own callers)."""
from __future__ import annotations

__all__ = ["xplane_root_for"]


def xplane_root_for(lat: int, lon: int) -> str | None:
    """The X-Plane install the tile's build reads (its CIFP folder's
    install — ``patch_commands`` and the tile driver resolve it so)."""
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    from auto_patch_v2.airport.cifp import xplane_root_from_cifp_path
    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    cifp_dir = VMAP.resolve_cifp_dir_for_tile(tile)
    return xplane_root_from_cifp_path(cifp_dir) if cifp_dir else None
