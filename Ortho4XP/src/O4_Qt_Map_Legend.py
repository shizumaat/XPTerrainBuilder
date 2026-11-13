"""The Build map's key kinds (Qt half; the Mac app's ``MapKey.buildItems``,
same kinds and order — #1958, #2024, #2031): what the World pack draws on
each tile (``O4_Qt_Map_World``), another tool's tile (dotted), which
tile's airport pack changed since its build (``O4_Tile_Staleness``), and
the orange custom-patch band (#1229).  A built tile is drawn by its World
state (:func:`built_look`): where it built and on which drive are not key
items (#2031).  Only the kinds on the map now are listed; each kind IS
its ``O4_Map_Key_Text`` item, and ``O4_Qt_Map_Key`` paints the one key.
"""
from __future__ import annotations

import O4_Map_Key_Text as KEYTEXT
import O4_Tile_Info as TINFO
from PySide6.QtGui import QColor

__all__ = ["WORLD_FULL", "WORLD_MESH", "WORLD_DRAPE", "WORLD_PLACEHOLDER",
           "WORLD_OTHER_TOOL", "BUILDING", "STALE", "CUSTOM_PATCH",
           "STALE_COLOR", "CUSTOM_PATCH_COLOR", "BUILDING_COLOR",
           "built_elsewhere", "built_look", "legend_kinds", "stale_label"]

WORLD_FULL, WORLD_MESH, WORLD_DRAPE = "full", "mesh", "drape"
WORLD_PLACEHOLDER = "placeholder"
WORLD_OTHER_TOOL = "other_tool"
BUILDING, STALE, CUSTOM_PATCH = "building", "stale", "custom"

#: A tile whose airport pack changed (MapCanvasView.staleTile).
STALE_COLOR = "#BF5AF2"
#: The custom-patch band (O4_Qt_Map.CUSTOM_PATCH_COLOR).
CUSTOM_PATCH_COLOR = "#FF9F0A"
#: A mesh or a drape under way (#2031: one colour, pulsing; Mac
#: ``FlyMapOverlay.building``): a colour no other item uses.
BUILDING_COLOR = QColor(94, 92, 230)                    # #5E5CE6
_WORLD_KINDS = ((WORLD_FULL, "full"), (WORLD_MESH, "mesh_lowres"),
                (WORLD_DRAPE, "drape"), (WORLD_PLACEHOLDER, "placeholder"))
_DRAWN_STATES = frozenset(state for _kind, state in _WORLD_KINDS)


def built_elsewhere(info) -> bool:
    """Another tool built it (an engine before ``origin`` says nothing)."""
    return getattr(info, "origin", "") == TINFO.ORIGIN_OTHER


def built_look(info, world_row, stale: bool):
    """How a scanned built tile is drawn (#2031; Mac ``MapKey.builtLook``):
    ``(item, dotted)``, or ``None`` when its World state draws it alone.
    A stale tile is the dashed "Pack changed"; a built tile the World pack
    does not list is "Full", dotted when another tool built it."""
    if stale:
        return STALE, False
    if getattr(world_row, "state", "") in _DRAWN_STATES:
        return None
    return WORLD_FULL, built_elsewhere(info)


def legend_kinds(built: dict, stale: dict, world: dict | None = None,
                 custom_patch: bool = False) -> list:
    """The kinds present on the map now, in the legend's order."""
    world = world or {}
    # a stale built tile draws "Pack changed" in place of its World band
    rows = [row for key, row in world.items()
            if not (key in stale and key in built)]
    looks = [built_look(info, world.get(key), key in stale)
             for key, info in built.items()]
    looks = [look for look in looks if look is not None]
    present = {kind: any(row.state == state for row in rows)
               for kind, state in _WORLD_KINDS}
    present[WORLD_FULL] |= any(kind == WORLD_FULL for kind, _d in looks)
    present.update({
        WORLD_OTHER_TOOL: (any(row.origin == TINFO.ORIGIN_OTHER for row in rows)
                           or any(dotted for _k, dotted in looks)),
        STALE: any(kind == STALE for kind, _d in looks),
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
