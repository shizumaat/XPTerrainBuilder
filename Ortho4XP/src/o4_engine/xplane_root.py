"""The X-Plane install a tile's build reads — light on purpose (#1989):
the session's build hooks resolve it without importing the pack-object
readers (``pack_objects`` re-exports it for its own callers) — and
whether X-Plane runs (:func:`xplane_running`, the converter's and the
World pack's one check)."""
from __future__ import annotations

import contextlib
import subprocess
import sys

__all__ = ["xplane_root_for", "xplane_root_of", "xplane_running"]


def xplane_running() -> bool:
    """Is an X-Plane process running on this machine (best effort: macOS
    and Linux process names; ``False`` where it cannot tell)?"""
    import O4_UI_Utils as UI
    if sys.platform == "win32":
        return False
    for name in ("X-Plane", "X-Plane-x86_64", "X-Plane-arm64"):
        with contextlib.suppress(OSError):
            done = subprocess.run(["pgrep", "-x", name], capture_output=True,
                                  check=False,
                                  **UI.external_tool_keyword_arguments())
            if done.returncode == 0:
                return True
    return False


def xplane_root_for(lat: int, lon: int) -> str | None:
    """The X-Plane install the tile's build reads (its CIFP folder's
    install — ``patch_commands`` and the tile driver resolve it so)."""
    import O4_Config_Utils as CFG
    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    return xplane_root_of(tile)


def xplane_root_of(tile) -> str | None:
    """:func:`xplane_root_for` of a tile already read (``tile_bundle.key``
    and ``tile_bundle.pack_dev`` read it so, the latter inside the object
    stage, whose code key must not reach the bundle-key code, #836)."""
    import O4_Vector_Map as VMAP
    from auto_patch_v2.airport.cifp import xplane_root_from_cifp_path
    cifp_dir = VMAP.resolve_cifp_dir_for_tile(tile)
    return xplane_root_from_cifp_path(cifp_dir) if cifp_dir else None
