"""OUR OWN BRIDGES: A LEVEL THE SOLVE CHOOSES, A GRADE THE TAXIWAY TAKES, A
CLEARANCE FLOOR (owner 2026-11-19T16:59Z / 17:02Z, relayed by the master:
"Since we set the bridge heights for our own bridges, shouldn't they be set
so the taxiway can meet the ends within grade?"; "The bridges just need
minimum clearances, they are allowed to have more, and they are allowed to
slope at the same grade as the taxiway").

A GENERATED deck (``planar/deck_generated``) is ours: no authored object
fixes its level or its rise.  Until this module it took the pack hard
deck's rigid row (``edge_deck._rigid_rows``: one zero, the A->B rise read
off the DEM at planar time), and a taxiway whose grade could not reach that
rise relaxed a row (MEASURED KRDU capture: the rigid row relaxed 0.98 m).
Now:

1. its end lines take the GRADED rows a span cut out of a pack deck takes
   (``edge_deck._graded_rows``: each end line flush across itself, the
   rise between them free within the carried family's longitudinal cap) --
   :func:`graded`;
2. each end line's seat mean stands at least the minimum clearance
   (``[bridge] clearance_minimum_m``) plus the slab (``[deck_gen]
   thickness_m``) over the HIGHEST lidar point of the roads it covers under
   its ring -- a one-sided row, no upper bound (:func:`clearance_rows`) --
   but never higher than the deck's own pre-solve level at that end (the
   ground beside its end lines, ``deck_generated._ends_ground``): where that
   level clears less, the floor is cut under the deck (the ladder,
   ``planar/survey_deck_cut``) and clears it by construction.  MEASURED on
   the KRDU capture: a bound past the pre-solve level lifted the deck off
   its taxiway (3.28 m relaxed); no bound at all let the free level sink
   into the bare-earth cut (KRDU NTH 6.0 m, KORD 6.2 m under it, the road
   1-2 m under the slab).

The object stage builds the deck to the solved levels at both end lines
(``pipeline/generated_publication``).  Nothing here names an airport.
Build-time impact: a few DEM reads per generated deck.
"""
from __future__ import annotations

import math
import typing as _t

from ..model.constraints import Linear, Row, Source
from ..model.structures import is_generated

__all__ = ["graded", "clearance_rows"]

_RUNWAY = ("runway", "runway_crossing")
#: the step (m) the covered road is read at under the ring
_STEP_M = 2.0


def graded(deck) -> bool:
    """``deck`` is ours and carries a taxiway (a runway deck keeps the
    runway's own anchor, ``constraints/deck_anchor``)."""
    return is_generated(deck) and str(getattr(deck, "family", "")) not in _RUNWAY


def _road_top(deck, dem) -> "float | None":
    """The highest lidar point of the roads ``deck`` covers, under its ring."""
    from shapely.geometry import LineString, Polygon
    ring = Polygon(deck.ring)
    ring = ring if ring.is_valid else ring.buffer(0.0)
    zs: list[float] = []
    for _id, _tags, coords in getattr(deck, "covered", ()) or ():
        if len(coords) < 2:
            continue
        x = LineString(coords).intersection(ring)
        for g in getattr(x, "geoms", [x]):
            if g.geom_type != "LineString" or g.length <= 0.0:
                continue
            n = max(1, int(g.length / _STEP_M))
            for k in range(n + 1):
                p = g.interpolate(g.length * k / n)
                z = float(dem.z(p.x, p.y))
                if math.isfinite(z):
                    zs.append(z)
    return max(zs) if zs else None


def clearance_rows(oid: str, es: _t.Sequence, airport, law, head: str, gen: str) -> list[Row]:
    """Rule 2 (module doc): per end line of generated deck ``oid`` (its
    ``deck_lines.EndLine``s ``es``), ``mean z[S] >= min(road top +
    clearance + slab, the pre-solve level there)``, under ``head`` (a
    ``[design] hard_rulings`` head)."""
    dem = getattr(airport, "dem", None)
    if not es or dem is None or not graded(es[0].deck):
        return []
    deck = es[0].deck
    road = _road_top(deck, dem)
    if road is None:
        return []
    need = road + float(law.tables.structures.bridge.clearance_minimum_m) \
        + float(law.tables.structures.deck_gen.thickness_m)
    mid = 0.5 * (float(deck.top_a) + float(deck.top_b))
    rows: list[Row] = []
    for k, e in enumerate(es):
        w = sum(wt for _v, wt in e.terms)
        if w <= 0.0:
            continue
        # never more than the deck's own pre-solve level at this end asks
        at_a = tuple(map(tuple, e.line)) == tuple(map(tuple, deck.seats_a))
        top = float(deck.top_a) if at_a else float(deck.top_b)
        lo = min(need, float(deck.deck_z) + top - mid)
        rows.append(Linear(tuple((v, wt / w) for v, wt in e.terms), lo, None,
                           Source(gen, head, (oid, f"clearance end {k}"))))
    return rows
