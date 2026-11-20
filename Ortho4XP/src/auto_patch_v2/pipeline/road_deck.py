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

A ROAD DECK SPANS THE WHOLE CUT (owner RULINGS 2026-11-19s (8) (d);
``geom/road_span``): a road bridge over a generated taxiway deck's cut,
running along that deck, runs on to the deck's two end lines, and each end
stands at the solved ground there (``z_at``), which the carve landed at the
taxiway deck's end level (``constraints/deck_carve``): no end floats.

Nothing here names an airport.  Build-time impact: a few coordinate
conversions per road bridge.
"""
from __future__ import annotations

import hashlib
import math
import typing as _t

from shapely.geometry import LineString

from .generated_publication import _ll

__all__ = ["road_deck_records"]


def _end(axis: LineString, end: int, w: float) -> list[tuple[float, float]]:
    """Three stations across the axis at its end ``end`` (0 / -1), ``w``
    either side."""
    a, b = (axis.coords[0], axis.coords[1]) if end == 0 else (axis.coords[-1], axis.coords[-2])
    d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
    return [(a[0] + nx * w, a[1] + ny * w), (a[0], a[1]), (a[0] - nx * w, a[1] - ny * w)]


def _spans(decks) -> list:
    """Each generated deck with a cut as ``geom/road_span`` reads it."""
    from ..constraints.deck_floor_follow import _deck_frame
    from ..geom.road_span import DeckSpan
    out = []
    for db in decks:
        carve, fr = getattr(db, "carve", None), _deck_frame(db)
        if carve is not None and fr is not None:
            out.append(DeckSpan(db.object_id, tuple(db.ring),
                                [tuple(p.coords) for p in carve.paths], fr))
    return out


def _ground_min(ring, z_at, step: float = 2.0) -> "float | None":
    """The lowest solved ground under ``ring`` (frame), read by ``z_at``
    every ``step`` metres inside it; ``None`` with no reading."""
    from shapely.geometry import Point
    if z_at is None:
        return None
    x0, y0, x1, y1 = ring.bounds
    zs = []
    for i in range(int((x1 - x0) / step) + 1):
        for j in range(int((y1 - y0) / step) + 1):
            p = (x0 + i * step, y0 + j * step)
            if ring.contains(Point(p)) and (q := z_at(p)) is not None:
                zs.append(float(q))
    return min(zs) if zs else None


def _top_of(rec) -> "_t.Any | None":
    """The taxiway deck's published top (``deck_floor_follow``'s record:
    ``o``, ``u``, ``w`` and the four profiles) as a Coons patch."""
    if not rec:
        return None
    from ..geom.coons_patch import CoonsPatch
    return CoonsPatch(tuple(rec["o"]), tuple(rec["u"]), tuple(rec["w"]),
                      *(tuple((float(q), float(zz)) for q, zz in rec[k])
                        for k in ("a", "b", "s0", "s1")))


def _surface_from(top, axis: LineString, w: float, to_ll, step: float = 2.0) -> dict:
    """THE ROAD DECK TAKES ITS TAXIWAY DECK'S HEIGHT AND SLOPE (owner
    2026-11-20T15:20Z; lane lcross20): its own parallelogram (end A's left
    corner ``o``, ``u`` along its axis, ``w`` across it) with each edge's
    profile read off the taxiway deck's top ``top`` at the same stations
    (clamped onto it: beside the deck, its side's level), in the published
    surface form (``generated_publication._surface``: lon/lat corners,
    absolute levels)."""
    (ax, ay), (bx, by) = axis.coords[0], axis.coords[-1]
    L = math.hypot(bx - ax, by - ay) or 1.0
    nx, ny = -(by - ay) / L, (bx - ax) / L
    o = (ax - nx * w, ay - ny * w)
    u = (bx - ax, by - ay)
    ww = (2.0 * w * nx, 2.0 * w * ny)

    def z(sv: float, tv: float) -> float:
        x, y = o[0] + sv * u[0] + tv * ww[0], o[1] + sv * u[1] + tv * ww[1]
        sp, tp = top.st(x, y)
        return float(top.z_st(min(1.0, max(0.0, sp)), min(1.0, max(0.0, tp))))
    ns, nt = max(2, int(L / step) + 1), max(2, int(2.0 * w / step) + 1)
    ss = [k / (ns - 1) for k in range(ns)]
    ts = [k / (nt - 1) for k in range(nt)]
    corners = _ll(to_ll, [o, (o[0] + u[0], o[1] + u[1]), (o[0] + ww[0], o[1] + ww[1])])
    return {"o": corners[0], "ou": corners[1], "ow": corners[2],
            "a": [[round(t, 6), round(z(0.0, t), 4)] for t in ts],
            "b": [[round(t, 6), round(z(1.0, t), 4)] for t in ts],
            "s0": [[round(q, 6), round(z(q, 0.0), 4)] for q in ss],
            "s1": [[round(q, 6), round(z(q, 1.0), 4)] for q in ss]}


def _record(b: _t.Mapping, law, to_ll, decks=(), z_at=None, airport=None,
            tops=None) -> "dict | None":
    from ..planar.deck_generated import GENERATED_DIR
    g = law.tables.structures.deck_gen
    axis = LineString(b.get("axis_xy") or ())
    levels = list(b.get("levels") or ())
    if axis.length <= 1.0 or len(levels) != 2:
        return None
    from ..geom.road_span import span_to_cut
    spans = span_to_cut(axis, _spans(decks))
    top = None
    if spans is not None:
        axis, oid = spans
        # owner 2026-11-20T15:20Z: "assume they will have the same height
        # and slope as the taxiway bridges" -- its top is read off the
        # taxiway deck's (:func:`_surface_from`); with none published, its
        # ends at the solved ground there (lane lcross20)
        top = _top_of((tops or {}).get(oid))
        if top is None:
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
    # owner 2026-11-20T14:50Z: no pier on any mapped road or railway under
    # it; every pier down to the deepest ground under it (lane lcross20)
    from .generated_publication import mapped_under
    roads += mapped_under(coords, law, to_ll, airport) if airport is not None else []
    ground = _ground_min(ring, z_at)
    surface = _surface_from(top, axis, w, to_ll) if top is not None else None
    if surface is not None:
        zero = min(zz for k in ("a", "b", "s0", "s1") for _q, zz in surface[k])
        levels = [zero, zero]
    return {"object_id": f"o4road_{hid}", "resource": f"{GENERATED_DIR}/road_{hid}.obj",
            **({"surface": surface} if surface is not None else {}),
            "ring": _ll(to_ll, coords), "seats_a": _ll(to_ll, _end(axis, 0, w)),
            "seats_b": _ll(to_ll, _end(axis, -1, w)),
            "top_a": 0.0, "top_b": round(float(levels[1]) - float(levels[0]), 4),
            "zero_m": round(float(levels[0]), 4), "family": "road",
            "route": _ll(to_ll, axis.coords), "road": [], "approach": [], "hides": [],
            "thickness_m": float(g.thickness_m), "top_lift_m": float(g.top_lift_m),
            "floor_m": round(float(law.tables.structures.bridge.clearance_minimum_m), 4),
            "roads": roads, "road_bridge": str(b.get("id")),
            **({"ground_m": round(ground, 4)} if ground is not None else {}),
            **({"spans_cut": spans[1]} if spans is not None else {})}


def road_deck_records(bridges: _t.Sequence[_t.Mapping], riding: _t.AbstractSet[str],
                      law, airport, decks=(), z_at=None, tops=None
                      ) -> tuple[list[dict], list[dict]]:
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
        rec = _record(b, law, to_ll, decks, z_at, airport, tops)
        if rec is not None:
            out.append(rec)
    keep = [{k: v for k, v in dict(b).items()
             if k not in ("span_xy", "ground", "junctions", "subtype", "net")}
            for b in bridges]
    return out, keep
