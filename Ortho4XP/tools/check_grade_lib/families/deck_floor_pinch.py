"""A DECK'S FLOOR IS NEVER PINCHED TO ITS PAVEMENT family
``deck_floor_pinch`` (#2239 / #2241, spec cyyz-decks-r3 R5), SIDECAR-DECLARED.

The sidecar ``deck_floor_pinch`` names every trench-floor (``tunnel_ramp``)
vertex that is a stage-1 airside vertex or carries a pack deck's end-edge
weld row (``auto_patch_v2/verify/deck_pinch.pinch_records``: ``{"deck",
"v", "why", "lat", "lon"}``): the floor held up at the deck, a wedge across
the road under it.  Every record is one PRESENCE row.  A patch with no key
reports nothing, which is every patch built before the family."""
from __future__ import annotations

from typing import List, Tuple

from check_grade_lib.rows import Violation, Way

LAW_FAMILY_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("deck_floor_pinch",
     "TRENCH FLOOR vertex pinched to a DECK's pavement (airside or end-edge weld)",
     "within"),
)


def check_deck_floor_pinch(records) -> List[Violation]:
    """The family's rows (module doc)."""
    out: List[Violation] = []
    for rec in records or ():
        if rec.get("lat") is None:
            continue
        w = Way(str(rec.get("deck")), "tunnel_ramp", str(rec.get("why")), "", [], [], {})
        v = Violation(grade_pct=0.0, excess_pct=0.0, distance_m=0.0, de_m=0.0, way_a=w,
                      way_b=w, pt_a=(0.0, 0.0), pt_b=(0.0, 0.0), elev_a=0.0, elev_b=0.0)
        v.lat, v.lon = float(rec["lat"]), float(rec["lon"])
        out.append(v)
    return out
