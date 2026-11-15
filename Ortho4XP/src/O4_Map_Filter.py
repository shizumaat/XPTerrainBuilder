"""The map's Filter menu (#2097; Mac: ``MapFilter.swift``, same keys,
words and order): two sections of independent toggles, each item on or
off with a check mark, kept per user.

Airports -- ICAO, Small, Custom Scenery, Global.  ICAO / Small is the
airport's KIND: the engine index's ``icao_airport`` category (an apt.dat
airport with an ``icao_code`` row) is ICAO, every other row (local IDs,
seaplane bases, heliports) Small; a custom pack's airport takes its kind
from the index by code, and one the index lacks is Small.  Custom
Scenery / Global is its SOURCE (a custom pack's mark, X-Plane's Global
Airports).  A mark draws when its kind AND its source are on.

Ortho Tiles -- Favorites, Full, Drape.  A tile is Full when the World
pack draws it full, as a mesh whose imagery streams, or as a
placeholder, when it is one of our built tiles the World pack does not
list (#2031), and for other installed ortho packages' outlines; Drape
when the World pack drapes it; Favorites when it is a built tile marked
Favorite (``TileInfo.pinned``, #2033).  A tile draws when ANY of its
items is on.

Only the items turned OFF are stored, so an item a later version adds
starts on.
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, Optional

from o4_engine import world_state as WS

__all__ = [
    "SECTIONS", "KEYS", "ICAO_CATEGORY",
    "parse_hidden", "dump_hidden", "is_filtering",
    "shows_airport", "shows_tile", "shows_other_ortho", "shows_any_tile",
]

#: (section header, ((key, label), ...)) top to bottom; the headers are
#: not selectable.
SECTIONS = (
    ("Airports", (("icao", "ICAO"), ("small", "Small"),
                  ("custom", "Custom Scenery"), ("global", "Global"))),
    ("Ortho Tiles", (("favorites", "Favorites"), ("full", "Full"),
                     ("drape", "Drape"))),
)
KEYS = tuple(key for _header, items in SECTIONS for key, _label in items)

#: The engine index's category of an airport with an ICAO code
#: (``O4_Airport_Index.AIRPORT_CATEGORIES[0]``).
ICAO_CATEGORY = "icao_airport"

_ORTHO_KEYS = frozenset(key for key, _label in SECTIONS[1][1])
_FULL_STATES = (WS.FULL, WS.MESH_LOWRES, WS.PLACEHOLDER)


def parse_hidden(value) -> FrozenSet[str]:
    """The items turned off, from a stored list (or comma string);
    unknown keys are dropped."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(str(key) for key in value if str(key) in KEYS)


def dump_hidden(hidden: Iterable[str]) -> list:
    """The stored form: the off keys in menu order."""
    hidden = set(hidden)
    return [key for key in KEYS if key in hidden]


def is_filtering(hidden: Iterable[str]) -> bool:
    """Any item off (the toolbar's filled filter icon)."""
    return bool(set(hidden) & set(KEYS))


def shows_airport(hidden: FrozenSet[str], icao_coded: bool,
                  custom: bool) -> bool:
    """A mark draws when its kind and its source are both on."""
    kind = "icao" if icao_coded else "small"
    source = "custom" if custom else "global"
    return kind not in hidden and source not in hidden


def _tile_item(state: Optional[str]) -> Optional[str]:
    """The Ortho item a World state reads as; None (a built tile the World
    pack does not list) is Full, ``nothing`` no item."""
    if state is None or state in _FULL_STATES:
        return "full"
    if state == WS.DRAPE:
        return "drape"
    return None


def shows_tile(hidden: FrozenSet[str], state: Optional[str],
               pinned: bool = False) -> bool:
    """A tile of World ``state`` (None: a built tile the World pack does
    not list) draws when its item is on, or it is a Favorite and
    Favorites is on."""
    if pinned and "favorites" not in hidden:
        return True
    item = _tile_item(state)
    return item is not None and item not in hidden


def shows_other_ortho(hidden: FrozenSet[str]) -> bool:
    """Other installed ortho / mesh packages' outlines are Full ortho."""
    return "full" not in hidden


def shows_any_tile(hidden: FrozenSet[str]) -> bool:
    """Any Ortho item on (the map key's build kinds, the built labels)."""
    return not _ORTHO_KEYS <= set(hidden)
