"""A list of airport codes typed into the search field (issue #542).

``KCLT, kase OTHH`` selects the tiles of all three airports in one step.
This module is the Python half of that rule; the macOS app's half is
``Sources/SceneryKit/AirportCodeList.swift``.  The two read ONE set of
test vectors (``tests/fixtures/airport_code_list_cases.json``), so they
cannot drift without a twin going red.

The rule (owner decisions on #542, 2026-10-10):

* commas, semicolons and whitespace all separate codes, in any mix;
* case does not matter, and a repeated code counts once;
* a code that is not in the index is reported, and the rest are still
  selected;
* an airport selects every tile its extent (boundary, runways, datum)
  touches.

A query is a LIST only when it could not be an ordinary search: it holds
a comma or semicolon, or it holds two or more words of which at least one
is an exact airport code.  Anything else -- one word, or a free-text name
such as ``Charlotte Douglas`` -- returns ``None`` and the caller runs its
single-airport search exactly as before.  Tile-key queries (``+48-006``)
are the caller's to recognise first.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "AirportBatch",
    "split_codes",
    "airport_tiles",
    "resolve_codes",
    "code_lookup",
    "UNKNOWN_CODES_TITLE",
    "unknown_codes_message",
]

# The alert shown when a code was not found (owner decision on #542).
# Same wording as SceneryKit's AirportBatch.unknownCodesTitle/Message.
UNKNOWN_CODES_TITLE = "Some airport codes were not found"

# Separators: any run of commas, semicolons and whitespace.
_SEPARATORS = re.compile(r"[,;\s]+")
# Characters that make a query an explicit list even with one code.
_LIST_MARKS = (",", ";")
# An extent wider than this (degrees) is a data error, not an airport --
# an antimeridian wrap or a stray node -- and the airport falls back to
# its datum tile.
_MAX_EXTENT_DEG = 1.0

Tile = Tuple[int, int]


@dataclass
class AirportBatch:
    """What a code list resolved to.

    Attributes:
        codes: The codes found, upper-cased, in the order typed.
        unknown: The codes not in the index, in the order typed.
        tiles: Every tile the found airports touch, sorted, no repeats.
    """

    codes: List[str] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    tiles: List[Tile] = field(default_factory=list)


def split_codes(query: str) -> List[str]:
    """The query's codes: split on commas, semicolons and whitespace,
    upper-cased, first occurrence kept."""
    codes: List[str] = []
    for token in _SEPARATORS.split(query or ""):
        code = token.upper()
        if code and code not in codes:
            codes.append(code)
    return codes


def airport_tiles(lat: float, lon: float,
                  extent: Optional[Sequence[float]] = None) -> List[Tile]:
    """Every 1x1 tile ``(lat, lon)`` an airport touches.

    ``extent`` is ``(min_lat, min_lon, max_lat, max_lon)``; without one
    (or with an implausibly wide one) the airport is its datum point.
    """
    if extent is not None:
        min_lat, min_lon, max_lat, max_lon = extent
        if (0 <= max_lat - min_lat <= _MAX_EXTENT_DEG
                and 0 <= max_lon - min_lon <= _MAX_EXTENT_DEG):
            return [
                (la, lo)
                for la in range(math.floor(min_lat), math.floor(max_lat) + 1)
                for lo in range(math.floor(min_lon), math.floor(max_lon) + 1)
            ]
    return [(math.floor(lat), math.floor(lon))]


def resolve_codes(query: str,
                  lookup: Callable[[str], Optional[List[Tile]]]
                  ) -> Optional[AirportBatch]:
    """Resolve a typed list through ``lookup`` (code -> its tiles, or
    ``None`` when unknown).

    Returns ``None`` when the query is not a list (see the module
    docstring): the caller's ordinary search handles it.
    """
    codes = split_codes(query)
    explicit = any(mark in (query or "") for mark in _LIST_MARKS)
    if not codes or (len(codes) < 2 and not explicit):
        return None
    batch = AirportBatch()
    tiles = set()
    for code in codes:
        found = lookup(code)
        if found is None:
            batch.unknown.append(code)
        else:
            batch.codes.append(code)
            tiles.update(found)
    if not explicit and not batch.codes:
        return None
    batch.tiles = sorted(tiles)
    return batch


def unknown_codes_message(batch: AirportBatch) -> Optional[str]:
    """The alert's message, or ``None`` when every code resolved (no
    alert)."""
    if not batch.unknown:
        return None
    selected = ("The tiles of %s are selected." % ", ".join(batch.codes)
                if batch.codes else "No tiles were selected.")
    return "Not identified: %s. %s" % (", ".join(batch.unknown), selected)


def code_lookup(entries: Iterable) -> Callable[[str], Optional[List[Tile]]]:
    """A ``resolve_codes`` lookup over index entries (anything with
    ``code``/``lat``/``lon`` and an optional ``extent``, i.e.
    :class:`O4_Airport_Index.AirportEntry`).  Codes match case-blind; the
    first entry carrying a code wins, as in the index itself."""
    by_code = {}
    for entry in entries:
        by_code.setdefault(entry.code.upper(), entry)

    def lookup(code: str) -> Optional[List[Tile]]:
        entry = by_code.get(code.upper())
        if entry is None:
            return None
        return airport_tiles(entry.lat, entry.lon,
                             getattr(entry, "extent", None))

    return lookup
