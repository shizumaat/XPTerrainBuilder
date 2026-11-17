"""LIBRARY of ``tools/deck_probe.py --cut-cover`` (owner 2026-11-17 18:30Z:
"Be sure the cut goes all the way under anywhere we add a bridge"): THE
CUT UNDER EVERY GENERATED DECK AND ROAD BRIDGE, off a ``--solved-out``
pickle.

* A GENERATED DECK (``PlanarMap.decks``, witness ``generated``): under its
  ring (``INSET_M`` inside the edge) the solved ground stands no higher than
  the bank the cut builds -- the end line's solved seat level less
  ``slope`` x the distance from that end line, at most the end's depth (the
  floor) -- plus ``tol``.  The bank slope is the generated deck's
  (``planar/deck_generated.generated_bank_slope``).
* A GENERATED ROAD BRIDGE (``Airport.road_bridges``): under its span, each
  lower road's carriageway stands at least ``[bridge] clearance_minimum_m``
  under the deck line (straight between the ends' levels on their
  embankments, ``planar/road_bridge_clear.deck_at``) less ``tol`` -- the
  cut (``airport/road_bridge_ground``) reached all the way under.

The surface is read at the map's vertices AND along its edges (every
``STEP_M``, linear between the two solved ends): a long edge from a crest
across the floor -- the cut not reaching all the way under -- stands over
the floor between vertices that each pass.  The emitted triangulation adds
diagonals inside faces that this read does not see.  Pure: reads the
pickle's map, ``z`` and airport; writes nothing.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["INSET_M", "STEP_M", "deck_cover", "road_bridge_cover", "cut_cover"]

#: the ring is read this far inside its edge (the seat line and rim stand on it)
INSET_M = 0.5
#: an edge is sampled this often (m)
STEP_M = 2.0


def _samples(pm, z, region) -> _t.Iterator[tuple[float, float, float, str]]:
    """``(x, y, z, where)`` of the map's surface inside ``region``: every
    vertex, then every edge every :data:`STEP_M`."""
    from shapely.geometry import LineString, Point
    from shapely.prepared import prep
    pr = prep(region)
    for v, vx in pm.vertices.items():
        if pr.contains(Point(vx.xy)):
            yield vx.xy[0], vx.xy[1], float(z[v]), f"v{v}"
    x0, y0, x1, y1 = region.bounds
    for e in pm.edges.values():
        (ax, ay), (bx, by) = pm.vertices[e.a].xy, pm.vertices[e.b].xy
        if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1:
            continue
        if not pr.intersects(LineString([(ax, ay), (bx, by)])):
            continue
        n = max(1, int(math.hypot(bx - ax, by - ay) / STEP_M))
        za, zb = float(z[e.a]), float(z[e.b])
        for k in range(1, n):
            f = k / n
            p = (ax + f * (bx - ax), ay + f * (by - ay))
            if pr.contains(Point(p)):
                yield p[0], p[1], za + f * (zb - za), f"e{e.id}@{f:.2f}"


def _end_level(pm, z, deck, end: str) -> "float | None":
    """The end line's solved seat level: its anchor's stations, else the
    map's vertices within :data:`INSET_M` of the seat line (a generated
    deck's end lines carry no anchor)."""
    import numpy as np
    from shapely.geometry import LineString, Point
    for x in getattr(pm, "deck_anchors", ()) or ():
        if x.object_id == deck.object_id and x.end == end and x.stations:
            return float(np.median([z[v] for v in x.stations]))
    seats = deck.seats_a if end == "a" else deck.seats_b
    if len(seats) < 2:
        return None
    line = LineString(seats)
    on = [float(z[v]) for v, vx in pm.vertices.items()
          if line.distance(Point(vx.xy)) <= INSET_M]
    return float(np.median(on)) if on else None


def deck_cover(pm, z, deck, slope: float, tol: float) -> dict:
    """One generated deck's read (module doc): the worst sample over the
    bank-or-floor ceiling and how many stand over ``tol``."""
    from shapely.geometry import LineString, Point, Polygon
    ring = Polygon(deck.ring).buffer(-INSET_M)
    ends = [(LineString(st), lv, float(dp)) for st, lv, dp in
            ((deck.seats_a, _end_level(pm, z, deck, "a"), deck.depth_a),
             (deck.seats_b, _end_level(pm, z, deck, "b"), deck.depth_b))
            if len(st) >= 2 and lv is not None]
    out = {"object": deck.object_id, "kind": "deck", "over": 0, "samples": 0,
           "worst_m": None, "worst_at": None}
    if ring.is_empty or not ends:
        out["note"] = "no ring or no solved end line"
        return out
    for x, y, zz, where in _samples(pm, z, ring):
        p = Point(x, y)
        line, lv, dp = min(ends, key=lambda t: t[0].distance(p))
        ceil = lv - min(dp, slope * line.distance(p))
        d = zz - ceil
        out["samples"] += 1
        out["over"] += d > tol
        if out["worst_m"] is None or d > out["worst_m"]:
            out["worst_m"], out["worst_at"] = round(d, 3), (round(x, 2), round(y, 2), where)
    return out


def road_bridge_cover(pm, z, airport, bridge: _t.Mapping, law, tol: float) -> list[dict]:
    """One generated road bridge's read (module doc), per lower road: under
    the span, its carriageway's solved ground stands at least ``clear`` under
    the deck line (``road_bridge_clear.deck_at`` between the ends' levels)."""
    from auto_patch_v2.planar.structure_approach import carriageway_width_m
    from shapely.geometry import LineString, Point, Polygon
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    axis = LineString(bridge["axis_xy"])
    lv = bridge["levels"]
    span = Polygon(bridge["span_xy"])
    res = []
    lower = set(bridge.get("over") or ())
    for w in getattr(airport, "osm_ways", ()) or ():
        if str(w.id) not in lower or len(w.points) < 2:
            continue
        half = carriageway_width_m(w.tags, law) / 2.0
        region = LineString(w.points).buffer(half, cap_style="flat").intersection(span)
        if region.is_empty:
            continue
        out = {"object": f"road bridge {bridge['id']}", "kind": "road_bridge",
               "lower": str(w.id), "over": 0, "samples": 0, "worst_m": None,
               "worst_at": None}
        for x, y, zz, where in _samples(pm, z, region):
            t = min(1.0, max(0.0, axis.project(Point(x, y)) / max(axis.length, 1e-9)))
            d = zz - (lv[0] + t * (lv[1] - lv[0]) - clear)
            out["samples"] += 1
            out["over"] += d > tol
            if out["worst_m"] is None or d > out["worst_m"]:
                out["worst_m"], out["worst_at"] = round(d, 3), (round(x, 2), round(y, 2), where)
        res.append(out)
        lower.discard(str(w.id))
    return res


def cut_cover(pm, z, airport, law, tol: float) -> list[dict]:
    """Every generated deck's and road bridge's read; ``ll`` on each worst
    sample (``(lat, lon)``)."""
    from auto_patch_v2.planar.deck_generated import GENERATED_WITNESS, generated_bank_slope
    slope = generated_bank_slope(law)
    out = [deck_cover(pm, z, d, slope, tol) for d in getattr(pm, "decks", ()) or ()
           if getattr(d, "witness", "") == GENERATED_WITNESS]
    for b in getattr(airport, "road_bridges", ()) or ():
        if b.get("axis_xy") and b.get("levels"):
            out += road_bridge_cover(pm, z, airport, b, law, tol)
    if airport is not None and getattr(airport, "frame", None) is not None:
        _xy, to_ll = airport.frame.transformers()
        for q in out:
            if q.get("worst_at"):
                la, lo = to_ll(q["worst_at"][0], q["worst_at"][1])
                q["ll"] = (round(la, 7), round(lo, 7))
    return out
