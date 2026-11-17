"""THE GENERATED STRUCTURES, PUBLISHED FOR THE OBJECT STAGE (spec
``docs/specs/2123.md`` A2 / B2; RULINGS 2026-11-16y).

The planar map carries the generated taxiway decks
(``planar/deck_generated``) and the generated road bridges
(``planar/road_bridge_gen``); the object stage, which writes them into the
airport's pack (``airport/generated_pack``), reads them off the graded
surface's provenance as ``generated`` -- in lon/lat, with each deck's
ZERO read off the SOLVED surface at its end lines (the stations the design
solve held flush, ``constraints/deck_lines``), so the object's top meets
the taxiway it carries.

Build-time impact: a few dozen coordinate conversions per airport.
"""
from __future__ import annotations

import statistics

__all__ = ["generated_records"]


def _ll(to_ll, pts) -> list[list[float]]:
    """``pts`` (frame xy) as ``[lon, lat]`` (``to_ll`` answers lat, lon)."""
    return [[round(float(lo), 9), round(float(la), 9)]
            for la, lo in (to_ll(float(x), float(y)) for x, y in pts)]


def _zero(planar, law, db, z) -> "float | None":
    """The deck's zero: the solved surface at its end-line stations less
    the top there (``rebake_inputs._deck_plate``'s reading)."""
    from ..constraints.deck_lines import end_lines
    zs = []
    for e in end_lines(planar, law).get(db.object_id, ()):
        w = sum(wt for _v, wt in e.terms)
        if w <= 0.0:
            continue
        at = sum(float(z[v]) * wt for v, wt in e.terms) / w
        zs.append(at - (float(db.bottom_y) + float(e.depth)))
    return statistics.median(zs) if zs else None


def _roads(db, law, to_ll) -> list[dict]:
    """The roads a deck covers (#2132: its piers stand at their floors'
    edges): ``{"line": [[lon, lat], ...], "half_m": carriageway half}``."""
    from ..planar.structure_approach import carriageway_width_m
    return [{"line": _ll(to_ll, coords),
             "half_m": round(carriageway_width_m(dict(tags), law) / 2.0, 3)}
            for _id, tags, coords in getattr(db, "covered", ()) or () if len(coords) >= 2]


def generated_records(planar, law, airport, z) -> dict[str, list[dict]]:
    """``{"decks": [...], "road_bridges": [...]}`` -- empty lists where
    the airport generated none (module doc)."""
    from ..planar.deck_generated import is_generated
    _to_xy, to_ll = airport.frame.transformers()
    g = law.tables.structures.deck_gen
    decks = []
    for db in getattr(planar, "decks", ()) or ():
        if not is_generated(db):
            continue
        zero = _zero(planar, law, db, z)
        if zero is None:
            continue
        decks.append({
            "object_id": db.object_id, "resource": db.resource,
            "ring": _ll(to_ll, db.ring), "seats_a": _ll(to_ll, db.seats_a),
            "seats_b": _ll(to_ll, db.seats_b),
            "top_a": round(float(db.top_a), 4), "top_b": round(float(db.top_b), 4),
            "zero_m": round(float(zero), 4), "family": db.family,
            "route": _ll(to_ll, db.route), "road": _ll(to_ll, db.road),
            "approach": [_ll(to_ll, q) for q in getattr(db, "approach", ()) or ()],
            "hides": [{"object_id": h[0], "resource": h[1], "lon": h[2][0], "lat": h[2][1]}
                      for h in getattr(db, "hides", ()) or ()],
            "thickness_m": float(g.thickness_m), "top_lift_m": float(g.top_lift_m),
            # #2132 the piers: the floor under the top and each covered road
            "floor_m": round(float(db.floor_min_m), 4),
            "roads": _roads(db, law, to_ll)})
    bridges = [{k: v for k, v in dict(b).items() if k != "span_xy"}
               for b in getattr(airport, "road_bridges", ()) or ()]
    return {"decks": decks, "road_bridges": bridges}
