"""The automatic photo source of a tile (#2018, spec
``docs/specs/auto-imagery-provider-spec-20261113.md`` §1; owner
2026-11-13T02:00Z).

A World or flight drape, and a flight's full build, under the Fly pane's
"Automatic" photo source takes the national orthophoto service whose
extent covers the whole 1° tile, else Bing:

* :func:`candidates` -- the national layers of the combined sources
  (``Providers/*.comb``), in file order (the order the combined build
  paints them, top first), each with its extent; global layers are not
  candidates (the fallback is :data:`FALLBACK`).
* :func:`covered_fraction` -- how much of the tile an extent's mask sets
  (``O4_Imagery_Utils.has_data``).  A layer covers a tile at
  :data:`COVER_FRACTION`: a border or open-sea tile is drawn by Bing,
  since a national service is blank outside its country.
* :func:`choose` -- ``(provider, zoom level)``: the first covering
  candidate, else :data:`FALLBACK`, at the user's zoom raised to the
  provider's ``min_source_zl`` (#2017).

A pure function of the shipped provider and extent files: a tile always
gets the same answer, so its neighbours agree on where providers change.
The registries must be loaded (the engine loads them at start,
``o4_engine.jsonl``).  No tile, airport or country is named here.
"""
from __future__ import annotations

import functools
from typing import List, Tuple

import numpy
import O4_Imagery_Placeholder as PLACEHOLDER
import O4_Imagery_Utils as IMG

__all__ = ["AUTO", "FALLBACK", "COVER_FRACTION", "choose", "at_zoom"]

#: The ``fly_photo_source`` value meaning "choose per tile".
AUTO = "auto"
#: The provider of a tile no national layer covers (owner: "else Bing").
FALLBACK = "BI"
#: The share of the tile an extent's mask must set (the rest is the
#: mask's anti-aliased edge).
COVER_FRACTION = 0.99
#: Mask pixels per tile edge read for the fraction.
_MASK_PX = 64
_GLOBAL = ("global", "default")


def candidates() -> List[Tuple[str, str]]:
    """``[(layer code, extent code)]`` of every national layer of the
    combined sources, top first, each once."""
    out, seen = [], set()
    for comb in sorted(IMG.combined_providers_dict, key=str.lower):
        for layer in IMG.combined_providers_dict[comb]:
            code, extent = layer.get("layer_code"), str(layer.get("extent_code") or "")
            if (not extent or extent in _GLOBAL or extent.startswith("!")
                    or code not in IMG.providers_dict or code in seen
                    or extent not in IMG.extents_dict):
                continue
            seen.add(code)
            out.append((code, extent))
    return out


def covered_fraction(extent_code: str, lat: int, lon: int) -> float:
    """The fraction of tile (``lat``, ``lon``) the extent's mask sets."""
    try:
        mask = IMG.has_data((lon, lat + 1, lon + 1, lat), extent_code,
                            return_mask=True, mask_size=(_MASK_PX, _MASK_PX))
    except Exception:                   # a missing or unreadable mask
        return 0.0
    if mask is True:
        return 1.0
    if mask is False or mask is None:
        return 0.0
    return float((numpy.asarray(mask) >= 128).mean())


@functools.lru_cache(maxsize=4096)
def provider_for(lat: int, lon: int) -> str:
    """The provider code that draws tile (``lat``, ``lon``) under
    Automatic: the first candidate covering it, else :data:`FALLBACK`."""
    for code, extent in candidates():
        if covered_fraction(extent, int(lat), int(lon)) >= COVER_FRACTION:
            return code
    return FALLBACK


def choose(lat: int, lon: int, zoomlevel: int) -> Tuple[str, int]:
    """``(provider, zoom level)`` of tile (``lat``, ``lon``) under
    Automatic: :func:`provider_for`, at ``zoomlevel`` raised to the
    provider's ``min_source_zl`` (#2017)."""
    return at_zoom(provider_for(int(lat), int(lon)), zoomlevel)


def at_zoom(code: str, zoomlevel: int) -> Tuple[str, int]:
    """``(code, zoom level)``: ``zoomlevel`` raised to provider ``code``'s
    ``min_source_zl`` (#2017)."""
    floor = PLACEHOLDER.min_source_zl(IMG.providers_dict.get(code))
    return code, max(int(zoomlevel), floor or 0)


def forget() -> None:
    """Drop the cached answers (the registries were reloaded)."""
    provider_for.cache_clear()
