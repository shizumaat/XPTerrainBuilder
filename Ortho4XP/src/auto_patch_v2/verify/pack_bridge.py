"""THE PACK'S BRIDGE OR OURS, NEVER BOTH -- v2 verify's reader of the census
family ``pack_bridge_under_deck`` (owner RULINGS 2026-11-20a (1), #2191).

The publication's ``pack_bridge_under_deck`` names every pack placement
the build left drawing a deck-level top under a GENERATED deck's footprint
after its one decision per crossing (``planar/deck_takeover.one_decision``:
a pack bridge body over a crossing we generated is hidden in the pack
copy).  Each record is one PRESENCE row, whatever its height; ``[]`` (or no
key, every patch built before it) reads none.  The census reads the same
record (``check_grade_lib/families/pack_bridge_under_deck``)."""
from __future__ import annotations

from .frame import Patch, Row, row

__all__ = ["FAMILY_PACK_BRIDGE_UNDER_DECK", "pack_bridge_under_deck"]

FAMILY_PACK_BRIDGE_UNDER_DECK = "pack_bridge_under_deck"


def pack_bridge_under_deck(p: Patch) -> list[Row]:
    """One row per published record (module doc)."""
    out: list[Row] = []
    for r in p.publication.get("pack_bridge_under_deck") or ():
        lat, lon = float(r.get("lat")), float(r.get("lon"))
        xy = p.to_m(lat, lon)
        out.append(row(FAMILY_PACK_BRIDGE_UNDER_DECK, ("all",), p.side("graded_strip"),
                       float(r.get("area_m2") or 0.0), None, None, None, xy, xy,
                       str(r.get("deck")), str(r.get("object")), lat=lat, lon=lon))
    return out
