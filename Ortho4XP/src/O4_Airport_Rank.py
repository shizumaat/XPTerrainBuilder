"""How big an airport is, and which airports a tile is named by.

One rule, read by both front ends (issues #815 and #817):

* :func:`size_class` turns what ``apt.dat`` says about an airport -- its
  type (land / seaplane base / heliport) and its runways -- into a class
  from 0 (the largest) to 4.  The airport index (:mod:`O4_Airport_Index`)
  computes it once, at build time, and writes it into the cache with the
  longest runway's length, so neither app parses runways.
* :func:`rank_key` orders airports largest first: class, then longest
  runway, then code (a total order, so both apps agree on ties).
* :func:`largest_by_tile` and :func:`title_codes` give a build-progress
  row its title codes: the tile's four largest airports, the searched
  one first when it is not among them.

The macOS app's half of the last two is
``Sources/SceneryKit/AirportRank.swift``; both read the vectors in
``tests/fixtures/airport_rank_cases.json``.

No airport is named here (owner standing 2026-10-05): the classes are
thresholds on runway length, surface and type only.
"""

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import O4_Airport_Batch as APTBATCH

__all__ = [
    "SIZE_CLASSES",
    "UNKNOWN_SIZE_CLASS",
    "TITLE_CODE_LIMIT",
    "size_class",
    "runway_length_m",
    "is_paved",
    "rank_key",
    "largest_by_tile",
    "title_codes",
]

# Class -> what it holds.  Lower is larger.
SIZE_CLASSES = (
    "major",       # 0: a paved runway of 3000 m or more
    "large",       # 1: a paved runway of 2000 m or more
    "medium",      # 2: a paved runway of 1200 m or more
    "small",       # 3: shorter or unpaved runways, seaplane bases
    "minor",       # 4: heliports, and airports with no runway at all
)
# The class an index row without size columns (a pre-v6 cache) reads as.
UNKNOWN_SIZE_CLASS = 3

# Paved-runway length thresholds (metres) for classes 0, 1 and 2.
_PAVED_THRESHOLDS_M = (3000.0, 2000.0, 1200.0)

# apt.dat row 100 surface codes that are hard (asphalt / concrete):
# 1 asphalt, 2 concrete, and X-Plane 12's asphalt (20-38) and concrete
# (50-57) variants.  Everything else (turf, dirt, gravel, lakebed, water,
# snow, transparent) is soft.
_PAVED_SURFACES = frozenset([1, 2] + list(range(20, 39)) + list(range(50, 58)))

# A progress row's title lists at most this many codes (#815).
TITLE_CODE_LIMIT = 4

_EARTH_RADIUS_M = 6371008.8


def runway_length_m(lat1: float, lon1: float, lat2: float,
                    lon2: float) -> float:
    """Distance between a runway's two ends, metres (equirectangular:
    exact enough over a few kilometres, and cheap over 40 000 airports)."""
    mean_lat = math.radians((lat1 + lat2) / 2.0)
    dx = math.radians(lon2 - lon1) * math.cos(mean_lat)
    dy = math.radians(lat2 - lat1)
    return _EARTH_RADIUS_M * math.hypot(dx, dy)


def is_paved(surface_code: str) -> bool:
    """True for an apt.dat row-100 surface code that is asphalt or
    concrete."""
    try:
        return int(float(surface_code)) in _PAVED_SURFACES
    except (TypeError, ValueError):
        return False


def size_class(category: str, longest_m: float, longest_paved_m: float) -> int:
    """The airport's size class (0 = largest, see :data:`SIZE_CLASSES`).

    ``category`` is an :data:`O4_Airport_Index.AIRPORT_CATEGORIES` value;
    ``longest_m`` its longest runway of any surface (water included) and
    ``longest_paved_m`` its longest hard runway, both in metres (0 when
    it has none).
    """
    if category == "heliport":
        return 4
    if category == "seaplane_base":
        return 3
    for cls, threshold in enumerate(_PAVED_THRESHOLDS_M):
        if longest_paved_m >= threshold:
            return cls
    return 3 if longest_m > 0 else 4


def rank_key(code: str, cls: int, runway_m: int) -> Tuple[int, int, str]:
    """Sort key, largest airport first: class, longest runway, code."""
    return (int(cls), -int(runway_m), str(code))


def largest_by_tile(entries: Iterable, limit: int = TITLE_CODE_LIMIT
                    ) -> Dict[Tuple[int, int], List[str]]:
    """Each tile -> the codes of its ``limit`` largest airports, largest
    first.

    ``entries`` are :class:`O4_Airport_Index.AirportEntry` rows (anything
    with ``code lat lon extent size_class runway_m``).  An airport belongs
    to every tile its extent touches -- the #542 rule a code search
    selects by (:func:`O4_Airport_Batch.airport_tiles`).
    """
    by_tile: Dict[Tuple[int, int], List[Tuple[Tuple[int, int, str], str]]] = {}
    for entry in entries:
        key = rank_key(entry.code, entry.size_class, entry.runway_m)
        for tile in APTBATCH.airport_tiles(entry.lat, entry.lon, entry.extent):
            by_tile.setdefault(tile, []).append((key, entry.code))
    result = {}
    for tile, ranked in by_tile.items():
        ranked.sort()
        result[tile] = [code for _, code in ranked[:max(0, limit)]]
    return result


def title_codes(largest: Sequence[str], searched: Optional[Sequence[str]] = (),
                limit: int = TITLE_CODE_LIMIT) -> List[str]:
    """The codes a tile's progress row names (#815), at most ``limit``.

    ``largest`` is the tile's largest airports, largest first; ``searched``
    the codes a search picked the tile by.  A searched code that is not
    among the largest goes FIRST (the user asked for it by name); the
    largest fill the rest.  Case is folded to upper; no code repeats.
    """
    wanted = [str(c).upper() for c in (searched or ())]
    top = [str(c).upper() for c in largest]
    shown = top[:max(0, limit)]
    codes: List[str] = []
    for code in [c for c in wanted if c not in shown] + top:
        if code not in codes:
            codes.append(code)
    return codes[:max(0, limit)]
