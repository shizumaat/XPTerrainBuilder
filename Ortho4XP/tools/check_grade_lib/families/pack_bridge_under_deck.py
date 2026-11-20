"""THE PACK'S BRIDGE OR OURS, NEVER BOTH family ``pack_bridge_under_deck``
(owner RULINGS 2026-11-20a (1); issue #2191), SIDECAR-DECLARED.

The build makes ONE decision per crossing (``planar/deck_takeover.
one_decision``): where it generates a deck, every pack bridge body over
the crossing is hidden in the pack copy.  The sidecar
``pack_bridge_under_deck`` names each pack placement still drawing a
deck-level top under a generated deck's footprint after it
(``{"deck", "object", "resource", "lat", "lon", "area_m2"}``); every
record is one PRESENCE row.  A patch with no key reports nothing, which is
every patch built before the decision (KMCO 1.0.567: ``puente.obj`` under
our decks, no row)."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("pack_bridge_under_deck",
     "PACK BRIDGE left under a GENERATED deck (the pack's bridge or ours, never both)",
     "within"),
)


def check_pack_bridge_under_deck(records) -> List[Violation]:
    """The family's rows (module doc)."""
    out: List[Violation] = []
    for rec in records or ():
        w = Way(str(rec.get("object")), "pack_bridge", str(rec.get("deck")), "", [], [], {})
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0,
                      de_m=float(rec.get("area_m2") or 0.0), way_a=w, way_b=w,
                      pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=0.0, elev_b=0.0)
        v.lat, v.lon = float(rec.get("lat") or 0.0), float(rec.get("lon") or 0.0)
        out.append(v)
    return out
