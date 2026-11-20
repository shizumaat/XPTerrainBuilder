"""THE GENERATED ROAD BRIDGE IS A NARROW FLAT DECK (owner sim read
2026-11-19T14:31Z, #2183 item 5: "rather than inserting an x-plane road
bridge, use a narrower version of our flat taxiway bridge for the road";
14:32Z "Should apply to all bridges"; spec ``docs/specs/2123.md`` B2's
B-alt).

``planar/road_bridge_gen`` still decides WHERE a road bridge stands, its
span, its ends on their embankments (``levels``) and the lower roads cut
under it (``ground``).  The object stage no longer writes an X-Plane road
chain for it: each bridge is published as a deck record of the generated
taxiway deck's shape (``airport/generated_pack`` writes it with the same
writer), ``family`` ``road``:

* THE RING: the bridge's mapped axis, its carriageway half width plus
  ``[deck_gen] edge_margin_m`` each side (the taxiway deck's own margin
  over its pavement, Q3), flat at the mapped ends;
* THE END LINES: across the axis at the two mapped ends;
* THE TOP: straight from end A's level to end B's on their embankments
  (``road_bridge_clear.deck_at``), the zero at end A's;
* THE PIERS stand at the cut lower roads' edges (``roads``), the floor
  ``[bridge] clearance_minimum_m`` under the top -- the depth the lower
  roads are cut to under the span.

A road bridge riding a generated taxiway deck (``planar/deck_gen_pairs.
riders``, ``DeckBridge.riders``) is carried by that deck: no record.

A ROAD DECK SPANS THE WHOLE CUT (owner RULINGS 2026-11-19s (8) (d), KPHX
1.0.566: "The two road bridges to the east of the eastern most taxiway
bridge, done reach across their whole span, leaving floating ends ... the
bridges are the same length as the taxiway ones they are paralleling, just
narrower"): a road bridge whose axis crosses a generated taxiway deck's
cut (``DeckBridge.carve``) running along that deck runs on, straight past
its mapped ends, to the deck's two end lines -- the cut's crests -- and
each end then stands at the solved ground there (``z_at``): flush, no end
floats over the trench.

Nothing here names an airport.  Build-time impact: a few coordinate
conversions per road bridge.
"""
from __future__ import annotations

import hashlib
import math
import typing as _t

from shapely.geometry import LineString, Polygon

from .generated_publication import _ll

__all__ = ["road_deck_records"]


def _end(axis: LineString, end: int, w: float) -> list[tuple[float, float]]:
    """Three stations across the axis at its end ``end`` (0 / -1), ``w``
    either side."""
    a, b = (axis.coords[0], axis.coords[1]) if end == 0 else (axis.coords[-1], axis.coords[-2])
    d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
    return [(a[0] + nx * w, a[1] + ny * w), (a[0], a[1]), (a[0] - nx * w, a[1] - ny * w)]


#: a road bridge runs along a taxiway deck within this angle of its axis (deg)
_ALONG_DEG = 30.0


def _param(p, d, q, w) -> "float | None":
    """``s`` where the line ``p + s d`` meets the line through ``q`` along ``w``."""
    det = d[0] * w[1] - d[1] * w[0]
    if abs(det) < 1e-9:
        return None
    return ((q[0] - p[0]) * w[1] - (q[1] - p[1]) * w[0]) / det


def _to_cut(axis: LineString, decks) -> "tuple[LineString, str] | None":
    """``axis`` run on straight past its ends to the end lines of the
    generated deck whose cut it crosses running along it (module doc);
    ``None`` where it crosses none or already reaches both."""
    c = list(axis.coords)
    (ax, ay), (bx, by) = c[0], c[-1]
    L = math.hypot(bx - ax, by - ay)
    if L <= 1e-9:
        return None
    d = ((bx - ax) / L, (by - ay) / L)
    from ..constraints.deck_floor_follow import _deck_frame
    cos_t = math.cos(math.radians(_ALONG_DEG))
    best = None
    for db in decks:
        carve = getattr(db, "carve", None)
        fr = _deck_frame(db)
        if carve is None or fr is None or not any(
                len(p.coords) >= 2 and LineString(p.coords).intersects(axis)
                for p in carve.paths):
            continue
        o, u, w = fr
        lu = math.hypot(*u)
        if lu <= 1e-9 or abs(d[0] * u[0] + d[1] * u[1]) / lu < cos_t:
            continue
        # its end lines: end A through ``o`` along ``w``, end B through ``o + u``
        ts = [_param((ax, ay), d, q, w) for q in (o, (o[0] + u[0], o[1] + u[1]))]
        if None in ts:
            continue
        s0, s1 = min(0.0, *ts), max(L, *ts)
        if s0 < -1e-3 or s1 > L + 1e-3:
            # the deck it parallels: the nearest whose cut it crosses (two
            # decks over one road share a cut: KJFK -833 ran to the far one)
            near = Polygon(db.ring).distance(axis)
            if best is None or near < best[0]:
                best = (near, s0, s1, db.object_id)
    if best is None:
        return None
    _n, s0, s1, oid = best
    pts = [(ax + d[0] * s0, ay + d[1] * s0)] if s0 < -1e-3 else []
    pts += c
    pts += [(ax + d[0] * s1, ay + d[1] * s1)] if s1 > L + 1e-3 else []
    return LineString(pts).simplify(0.01), oid


def _record(b: _t.Mapping, law, to_ll, decks=(), z_at=None) -> "dict | None":
    from ..planar.deck_generated import GENERATED_DIR
    g = law.tables.structures.deck_gen
    axis = LineString(b.get("axis_xy") or ())
    levels = list(b.get("levels") or ())
    if axis.length <= 1.0 or len(levels) != 2:
        return None
    spans = _to_cut(axis, decks)
    if spans is not None:
        axis, _oid = spans
        ends = [z_at(axis.coords[k]) if z_at is not None else None for k in (0, -1)]
        levels = [lv if e is None else e for lv, e in zip(levels, ends, strict=True)]
    w = float(b.get("half_m") or 0.0) + float(g.edge_margin_m)
    ring = axis.buffer(w, cap_style="flat", join_style="mitre")
    if ring.geom_type != "Polygon":
        return None
    coords = list(ring.exterior.coords)[:-1]
    hid = hashlib.sha256(";".join(f"{x:.1f},{y:.1f}" for x, y in coords).encode()).hexdigest()[:8]
    roads = [{"line": _ll(to_ll, r["axis"]), "half_m": float(r["half"])}
             for r in b.get("ground") or () if len(r.get("axis") or ()) >= 2]
    return {"object_id": f"o4road_{hid}", "resource": f"{GENERATED_DIR}/road_{hid}.obj",
            "ring": _ll(to_ll, coords), "seats_a": _ll(to_ll, _end(axis, 0, w)),
            "seats_b": _ll(to_ll, _end(axis, -1, w)),
            "top_a": 0.0, "top_b": round(float(levels[1]) - float(levels[0]), 4),
            "zero_m": round(float(levels[0]), 4), "family": "road",
            "route": _ll(to_ll, axis.coords), "road": [], "approach": [], "hides": [],
            "thickness_m": float(g.thickness_m), "top_lift_m": float(g.top_lift_m),
            "floor_m": round(float(law.tables.structures.bridge.clearance_minimum_m), 4),
            "roads": roads, "road_bridge": str(b.get("id")),
            **({"spans_cut": spans[1]} if spans is not None else {})}


def road_deck_records(bridges: _t.Sequence[_t.Mapping], riding: _t.AbstractSet[str],
                      law, airport, decks=(), z_at=None) -> tuple[list[dict], list[dict]]:
    """``(deck records, bridge records)``: every generated road bridge not
    ``riding`` a taxiway deck as a narrow flat deck (module doc) -- across
    the whole cut of a generated taxiway deck ``decks`` it runs along, its
    ends at the solved ground ``z_at(xy)`` -- and every bridge's record
    without its X-Plane chain (its span still clips the pack's pages)."""
    _to_xy, to_ll = airport.frame.transformers()
    out = []
    for b in bridges:
        if str(b.get("id")) in riding:
            continue
        rec = _record(b, law, to_ll, decks, z_at)
        if rec is not None:
            out.append(rec)
    keep = [{k: v for k, v in dict(b).items()
             if k not in ("span_xy", "ground", "junctions", "subtype", "net")}
            for b in bridges]
    return out, keep
