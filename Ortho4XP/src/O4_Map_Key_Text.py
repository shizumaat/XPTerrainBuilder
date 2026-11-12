"""The map's ONE key in both views and both apps (owner 2026-11-12T22:05Z):
a pill at the map's bottom-right, under the ZL pill, its items laid out
in a row — a swatch and a short word each, truncated with "…" when the
row runs out of room, the full sentence on hover.  The Build view lists
the kinds on the map now, the Fly view its corridor's keys; both in this
one order, each item in one colour wherever it shows.

The Mac mirror is ``Sources/SceneryKit/MapKeyText.swift`` (``MapKeyText``);
``tests/test_map_key.py`` requires the two to say the same.  Pure: no Qt.
"""
from __future__ import annotations

import O4_World_State_Text as WORLD_TEXT

__all__ = ["ITEMS", "SHORT", "FULL", "FLY_KEY_ITEMS",
           "MAX_WIDTH_FRACTION", "ordered"]

#: (item, short word, the hover's sentence), in the key's order.
ITEMS = (
    ("full", "Full", WORLD_TEXT.LEGEND_FULL),
    ("mesh", "Mesh", WORLD_TEXT.LEGEND_MESH),
    ("drape", "Drape", WORLD_TEXT.LEGEND_DRAPE),
    ("placeholder", "Placeholder", WORLD_TEXT.LEGEND_PLACEHOLDER),
    ("nothing", "Unmarked", WORLD_TEXT.LEGEND_NOTHING),
    ("other_tool", "Other tool", WORLD_TEXT.LEGEND_OTHER_TOOL),
    ("meshing", "Meshing", "Mesh being built"),
    ("draping", "Draping", "Photo being draped (dashed)"),
    ("route", "On route", "On the route, not built yet"),
    ("built", "Built here", "A tile XPTerrainBuilder built"),
    ("other", "Other ortho", "Ortho another tool built"),
    ("stale", "Pack changed", "Airport pack changed since the build (dashed)"),
    ("external", "Other drive", "Built on another drive"),
    ("custom", "Patch", WORLD_TEXT.LEGEND_CUSTOM_PATCH),
    ("sharp", "Full detail", "Full-detail photo (live flight preview)"),
)
SHORT = {item: short for item, short, _full in ITEMS}
FULL = {item: full for item, _short, full in ITEMS}

#: The Fly view's cell keys (``O4_Fly_Text.LEGEND``) -> their item.
FLY_KEY_ITEMS = {
    "draping": "draping", "meshing": "meshing", "draped": "drape",
    "built": "full", "mesh": "mesh", "placeholder": "placeholder",
    "own": "route", "custom": "custom", "sharp": "sharp",
}
#: The pill is at most this fraction of the map's width; its words
#: truncate to fit.
MAX_WIDTH_FRACTION = 0.7


def ordered(items) -> list:
    """``items`` once each, in the key's order."""
    wanted = set(items)
    return [item for item, _s, _f in ITEMS if item in wanted]
