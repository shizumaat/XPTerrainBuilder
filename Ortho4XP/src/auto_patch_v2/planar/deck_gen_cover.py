"""WHAT A GENERATED DECK SPANS (spec ``docs/specs/2123.md`` A1-A2; issues
#2181 KPHX, #2183 KIAH; owner RULINGS 2026-11-19m (2): with the pack's own
bridge object hidden, our generated bridges take over).

``planar/deck_generated`` reads a deck where a covered road runs under the
airport's taxi / runway pavement ``P``.  Three readings of the map decide
which pavement and which road that is; each is a general rule, measured at
the sites named:

1. THE ROAD'S COVER ENDS WHERE OSM MAPS IT OPEN (:func:`covered_state`).
   The cover of an underpass road is its mapped road grown end to end
   through OSM's splits (spec 2123 deviation 2) -- but only through the
   pieces mapped in the same state as the piece under the deck: a road
   mapped covered (``tunnel`` / ``covered`` / ``layer`` < 0) under the
   bridge and open beside it is open there.  MEASURED KPHX (33.4354,
   -112.0047): Sky Harbor Blvd ``-3936`` (``building_passage``, 65 m under
   the west taxiway bridge) grew through the open ``-3934`` (16 m between
   the two bridges) into ``-3935`` under the east one: 126 m, read as a
   tunnel, and no deck stood over the north half of the span.
2. A ROAD IS COUNTED ONCE (:func:`distinct_ways`): an airport over two
   tiles reads a way once per tile's extract (two ids, one line, #2169).
   MEASURED KPHX: tunnel ``-2221`` and its twin ``-4366`` summed to 129.9 m
   of a 65 m tunnel.
3. THE DECK CARRIES THE TAXIWAY ACROSS THE PACK'S HOLE
   (:func:`bridge_ribbons`): a pack that models its bridge as an object
   leaves the pavement out under it; with the object hidden (19m (2)) or
   never there, the mapped aeroway bridge (``structure_underpass.
   aeroway_decks``) between pavement at both ends is pavement for the deck
   -- its ribbon at the width of the pavement it joins.  MEASURED KIAH
   (29.9831, -95.3430 and three more): taxiway bridges over two primary
   roads stood over no pavement, so no road read as covered and no deck
   was tried; KRDU north (``-334`` over tunnel ``-1744``) and KORD I-190
   (``-25`` / ``-26``) with the pack's frame hidden the same.

Nothing here names an airport.  Build-time impact: one pass over the
aeroway bridges (a handful) and a few line-polygon reads each.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

__all__ = ["covered_state", "distinct_ways", "bridge_ribbons", "union_with"]


def _layer(tags) -> float:
    try:
        return float(str((tags or {}).get("layer", "0")).strip() or 0)
    except ValueError:
        return 0.0


def covered_state(tags: "_t.Mapping[str, str] | None") -> bool:
    """OSM maps this road COVERED: any ``tunnel`` value but ``no`` (a
    ``building_passage`` too), ``covered`` other than ``no``, or a layer
    under the ground's (rule 1)."""
    t = tags or {}
    return (str(t.get("tunnel", "no")).strip() not in ("", "no")
            or str(t.get("covered", "no")).strip() not in ("", "no")
            or _layer(t) < 0.0)


def _key(points) -> tuple:
    pts = [(round(float(x), 1), round(float(y), 1)) for x, y in points]
    return tuple(min(pts, pts[::-1]))


def distinct_ways(ways: _t.Iterable) -> list:
    """``ways`` with every line kept once, whichever way it runs (rule 2)."""
    seen: set = set()
    out = []
    for w in ways:
        k = _key(w.points)
        if k in seen:
            continue
        seen.add(k)
        out.append(w)
    return out


#: the pavement's width is read from this far past each end of the bridge,
#: stepping out by the same (m) ...
_PROBE_M = 3.0


def _half_at(P, line: LineString, end: int, reach: float = 30.0
             ) -> "tuple[float, tuple[float, float]] | None":
    """``(half width, station)`` of the pavement across ``line`` at the
    first station from ``_PROBE_M`` past its end ``end`` (0 / -1), out to
    ``reach``, standing on it -- an OSM bridge way may end short of the
    pavement it joins -- or ``None``."""
    a, b = (line.coords[1], line.coords[0]) if end == 0 else (line.coords[-2], line.coords[-1])
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    if d <= 1e-9:
        return None
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    t = _PROBE_M
    while t <= reach and not P.contains(Point(b[0] + ux * t, b[1] + uy * t)):
        t += _PROBE_M
    if t > reach:
        return None
    p = Point(b[0] + ux * t, b[1] + uy * t)
    far = 200.0
    cross = LineString([(p.x - uy * far, p.y + ux * far), (p.x + uy * far, p.y - ux * far)])
    x = cross.intersection(P)
    piece = next((g for g in getattr(x, "geoms", [x])
                  if g.geom_type == "LineString" and g.distance(p) < 1e-6), None)
    return None if piece is None else (0.5 * piece.length, (p.x, p.y))


def _widest_taxi_half(law) -> float:
    """Half the widest taxiway the authority states (``taxi.width_m``,
    its widest letter): a pavement read wider at a bridge's end is the
    apron it joins, never the taxiway it carries."""
    from ..law.tables import taxi_half_width_m
    hs = [taxi_half_width_m(law, c) for c in "ABCDEF"]
    hs = [h for h in hs if h is not None]
    return max(hs) if hs else float("inf")


def bridge_ribbons(P, airport, law) -> tuple[list, list[str]]:
    """``(ribbons, notes)``: per mapped aeroway bridge
    (``structure_underpass.aeroway_decks``) whose line runs over no taxi /
    runway pavement ``P`` somewhere and meets ``P`` beyond BOTH its ends
    (within ``[deck_gen] level_probe_m``: an OSM bridge way may end short
    of the pavement), its line from that pavement to that pavement at the
    half width of the pavement it joins (the narrower end, never wider than
    the widest taxiway the authority states) -- the hole the pack leaves
    under its own bridge object (rule 3).  A bridge paved across gives
    nothing."""
    from .structure_underpass import aeroway_decks
    if P is None or P.is_empty:
        return [], []
    out, notes = [], []
    cap = _widest_taxi_half(law)
    for w in aeroway_decks(airport, law):
        line = LineString(w.points)
        if line.length <= 1.0 or line.difference(P).length <= 1.0:
            continue
        reach = float(law.tables.structures.deck_gen.level_probe_m)
        ends = [_half_at(P, line, e, reach) for e in (0, -1)]
        if ends[0] is None or ends[1] is None:
            continue
        half = min(cap, ends[0][0], ends[1][0])
        # from the pavement at one end to the pavement at the other
        ribbon = LineString([ends[0][1], *line.coords, ends[1][1]]).buffer(half, cap_style="flat")
        hole = ribbon.difference(P)
        if hole.area <= 1.0:
            continue
        out.append(ribbon)
        notes.append(f"aeroway bridge {w.id}: {hole.area:,.0f} m2 of its {line.length:.0f} m "
                     f"span stand over no pavement -- the pack's hole under its own bridge "
                     f"object; the generated deck carries the taxiway across at "
                     f"{2.0 * half:.1f} m (#2183 item 4)")
    return out, notes


def union_with(P, ribbons):
    """``P`` with the ribbons (:func:`bridge_ribbons`)."""
    return unary_union([P, *ribbons]) if ribbons else P
