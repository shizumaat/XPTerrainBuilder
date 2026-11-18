"""A PACK DECK LYING AT GRADE ON THE AIRPORT'S PAVEMENT IS CUT TO ITS SPANS
(owner RULINGS 2026-11-18i; #2157 KRDU 2026-11-18T19:04Z: "drop that long
straight object for taxiway E between the two bridges and use real terrain
and taxiway grading instead").

A hard-deck piece (``planar/deck_bridge.deck_bridges``) whose axis holds a
SPAN over lower ground (``geom/deck_spans``: a road, a void or ground more
than a storey, ``[building_pad] low_level_min_step_m``, under the
profile's fill level) AND an AT-GRADE stretch longer than the piece is wide
that lies on the airport's mapped paved airside (a runway, taxiway or apron
cell along most of it) is cut to its spans: each span, abutment to
abutment, is a deck of its own -- seated flat on its own end lines, the
airside graded to weld to them (RULINGS 2026-10-30a, #2112's one zero per
plate) -- and the at-grade parts are no deck at all: the airport's graded
pavement draws there and the object stage drops those bands of the frame
(``airport/deck_plates``).  The abutment is where the bare-earth bank of
the span turns no steeper than twice the taxiway longitudinal cap.

A deck that is all bridge (no such at-grade stretch: KBNA's taxiway-L
plates) is unchanged.  Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

from ..geom.deck_spans import SpanCut, span_cut, span_pieces
from ..law.tables import role_family

__all__ = ["span_split"]

#: the station step along a piece's axis, metres
STEP_M = 2.0
_PAVED_FAMILIES = ("runway", "taxi")
_PAVED_COMMON = ("apron",)


def span_split(piece: _t.Any, airport: _t.Any, law: _t.Any, roles: _t.Any
               ) -> "tuple[SpanCut, list] | None":
    """``(cut, span pieces)`` of a deck piece the rule cuts (module doc),
    else ``None``."""
    dem = getattr(airport, "dem", None)
    storey = float(getattr(law.tables.structures.building_pad, "low_level_min_step_m", 0.0)
                   or 0.0)
    cap = law.ruleset.taxi.longitudinal.value(None, None)
    if dem is None or storey <= 0.0 or cap is None:
        return None

    def z_of(x: float, y: float) -> "float | None":
        z = dem.z(x, y)
        return None if z is None else float(z)
    cut = span_cut(piece, z_of, drop_m=storey, rise_grade=2.0 * float(cap), step_m=STEP_M)
    if cut is None or cut.length <= 0.0:
        return None
    width = piece.area / cut.length
    if not any(s1 - s0 > width and _paved(cut, s0, s1, roles, law)
               for s0, s1 in cut.at_grade()):
        return None
    parts = span_pieces(piece, cut)
    return (cut, parts) if parts else None


def _paved(cut: SpanCut, s0: float, s1: float, roles: _t.Any, law: _t.Any) -> bool:
    """Does most of the axis stretch ``s0..s1`` stand on paved airside?"""
    ux, uy = cut.unit
    n = max(int((s1 - s0) / STEP_M), 1)
    hits = 0
    for k in range(n + 1):
        s = s0 + (s1 - s0) * k / n
        r = roles.at_xy((cut.a[0] + s * ux, cut.a[1] + s * uy))
        hits += bool(r) and _paved_role(r, law)
    return hits * 2 > n + 1


def _paved_role(role: str, law: _t.Any) -> bool:
    try:
        fam = role_family(law, role)
    except KeyError:
        return False
    return fam in _PAVED_FAMILIES or role in _PAVED_COMMON
