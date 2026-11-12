"""The Build map's key kinds (Qt half; the Mac app's ``MapKey.buildItems``,
same kinds and order — #1958, #2024): what the World pack draws on each
tile (``O4_Qt_Map_World``), which border is a tile this app built, which
is "some ortho" another tool made (``TileInfo.origin``), which tile's
airport pack changed since its build (``O4_Tile_Staleness``), which lives
on another drive (#1987), and the orange custom-patch band (#1229).  Only
the kinds on the map now are listed; each kind IS its ``O4_Map_Key_Text``
item, and ``O4_Qt_Map_Key`` paints the one key.
"""
from __future__ import annotations

import O4_Map_Key_Text as KEYTEXT
import O4_Tile_Info as TINFO
from PySide6.QtGui import QColor

__all__ = ["WORLD_FULL", "WORLD_MESH", "WORLD_DRAPE", "WORLD_PLACEHOLDER",
           "WORLD_NOTHING", "WORLD_OTHER_TOOL", "BUILT", "OTHER", "STALE",
           "EXTERNAL", "CUSTOM_PATCH",
           "STALE_COLOR", "OTHER_ORTHO_COLOR", "CUSTOM_PATCH_COLOR",
           "built_elsewhere", "legend_kinds", "stale_label"]

WORLD_FULL, WORLD_MESH, WORLD_DRAPE = "full", "mesh", "drape"
WORLD_PLACEHOLDER, WORLD_NOTHING = "placeholder", "nothing"
WORLD_OTHER_TOOL = "other_tool"
BUILT, OTHER, STALE, EXTERNAL = "built", "other", "stale", "external"
CUSTOM_PATCH = "custom"

#: A tile whose airport pack changed (MapCanvasView.staleTile).
STALE_COLOR = "#BF5AF2"
#: A tile another tool built: the other packs' outline gray
#: (MapCanvasView.otherOrthoTile = regionOutline).
OTHER_ORTHO_COLOR = QColor(158, 158, 158, 217)
#: The custom-patch band (O4_Qt_Map.CUSTOM_PATCH_COLOR).
CUSTOM_PATCH_COLOR = "#FF9F0A"
_WORLD_KINDS = ((WORLD_FULL, "full"), (WORLD_MESH, "mesh_lowres"),
                (WORLD_DRAPE, "drape"), (WORLD_PLACEHOLDER, "placeholder"))


def built_elsewhere(info) -> bool:
    """Another tool built it (an engine before ``origin`` says nothing)."""
    return getattr(info, "origin", "") == TINFO.ORIGIN_OTHER


def legend_kinds(built: dict, stale: dict, world: dict | None = None,
                 custom_patch: bool = False) -> list:
    """The kinds present on the map now, in the legend's order."""
    world = world or {}
    states = {row.state for row in world.values()}
    infos = list(built.values())
    present = {kind: state in states for kind, state in _WORLD_KINDS}
    present.update({
        WORLD_NOTHING: bool(world),
        WORLD_OTHER_TOOL: any(row.origin == TINFO.ORIGIN_OTHER
                              for row in world.values()),
        BUILT: any(not built_elsewhere(i) for i in infos),
        OTHER: any(built_elsewhere(i) for i in infos),
        STALE: bool(infos) and bool(stale),
        EXTERNAL: any(getattr(i, "volume", "") for i in infos),
        CUSTOM_PATCH: bool(custom_patch),
    })
    return KEYTEXT.ordered(kind for kind, shown in present.items() if shown)


def stale_label(verdict: dict) -> str:
    """The map's pill: "Stale: EGKK", "Stale: EGKK +2" (O4StaleTile.label)."""
    airports = verdict.get("airports") or []
    if not airports:
        return ""
    first = airports[0]["icao"]
    return ("Stale: %s +%d" % (first, len(airports) - 1) if len(airports) > 1
            else "Stale: %s" % first)
