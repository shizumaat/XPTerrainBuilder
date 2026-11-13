"""The map's ONE key in both views and both apps (owner 2026-11-12T22:05Z,
#2031): a pill at the map's bottom-right, under the ZL pill, its items
laid out in a row — a swatch and a short word each, truncated with "…"
when the row runs out of room, the full sentence on hover.  The Build
view and the Fly view say the same eight items in the same words and
colours, in this one order; each lists only the items it shows now.

:data:`ITEMS` is the ONE place the key is defined (the owner may revise
it).  A built tile is drawn by its World state (#2031: "Built here",
"Other ortho" and "Other drive" are gone); the route is the magenta line,
with no item; the live preview's sharp squares are its "Sharp photo"
toggle, not an item.

The Mac mirror is ``Sources/SceneryKit/MapKeyText.swift`` (``MapKeyText``);
``tests/test_map_key.py`` requires the two to say the same.  Pure: no Qt.
"""
from __future__ import annotations

import math

import O4_World_State_Text as WORLD_TEXT

__all__ = ["ITEMS", "SHORT", "FULL", "FLY_KEY_ITEMS",
           "MAX_WIDTH_FRACTION", "BUILDING_PULSE_S", "BUILDING_LOW_ALPHA",
           "building_alpha",
           "ordered"]

#: (item, short word, the hover's sentence), in the key's order.
ITEMS = (
    ("full", "Full", WORLD_TEXT.LEGEND_FULL),
    ("mesh", "Mesh only", WORLD_TEXT.LEGEND_MESH),
    ("drape", "Drape", WORLD_TEXT.LEGEND_DRAPE),
    ("placeholder", "Placeholder", WORLD_TEXT.LEGEND_PLACEHOLDER),
    ("building", "Building", "Building: a mesh or a drape under way (pulsing)"),
    ("other_tool", "Other tool", WORLD_TEXT.LEGEND_OTHER_TOOL),
    ("stale", "Pack changed", "Airport pack changed since the build (dashed)"),
    ("custom", "Patch", WORLD_TEXT.LEGEND_CUSTOM_PATCH),
)
SHORT = {item: short for item, short, _full in ITEMS}
FULL = {item: full for item, _short, full in ITEMS}

#: The Fly view's cell keys (``O4_Fly_Text.LEGEND``) -> their item.
FLY_KEY_ITEMS = {
    "draping": "building", "meshing": "building", "draped": "drape",
    "built": "full", "mesh": "mesh", "placeholder": "placeholder",
    "custom": "custom",
}
#: The pill is at most this fraction of the map's width; its words
#: truncate to fit.
MAX_WIDTH_FRACTION = 0.7
#: "Building" pulses (#2031): its band's opacity runs from
#: ``BUILDING_LOW_ALPHA`` to 1 and back once in this many seconds.
BUILDING_PULSE_S = 1.2
BUILDING_LOW_ALPHA = 0.3


def building_alpha(seconds: float) -> float:
    """The "Building" band's opacity at ``seconds`` (any clock; Mac
    ``MapKeyText.buildingAlpha``)."""
    wave = 0.5 + 0.5 * math.cos(2 * math.pi * seconds / BUILDING_PULSE_S)
    return BUILDING_LOW_ALPHA + (1 - BUILDING_LOW_ALPHA) * wave


def ordered(items) -> list:
    """``items`` once each, in the key's order."""
    wanted = set(items)
    return [item for item, _s, _f in ITEMS if item in wanted]
