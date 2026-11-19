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

Nothing here names an airport.  Build-time impact: a few coordinate
conversions per road bridge.
"""
from __future__ import annotations

import hashlib
import math
import typing as _t

from shapely.geometry import LineString

__all__ = ["road_deck_records"]


def _ll(to_ll, pts) -> list[list[float]]:
    return [[round(float(lo), 9), round(float(la), 9)]
            for la, lo in (to_ll(float(x), float(y)) for x, y in pts)]


def _end(axis: LineString, end: int, w: float) -> list[tuple[float, float]]:
    """Three stations across the axis at its end ``end`` (0 / -1), ``w``
    either side."""
    a, b = (axis.coords[0], axis.coords[1]) if end == 0 else (axis.coords[-1], axis.coords[-2])
    d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
    return [(a[0] + nx * w, a[1] + ny * w), (a[0], a[1]), (a[0] - nx * w, a[1] - ny * w)]


def _record(b: _t.Mapping, law, to_ll) -> "dict | None":
    from ..planar.deck_generated import GENERATED_DIR
    g = law.tables.structures.deck_gen
    axis = LineString(b.get("axis_xy") or ())
    levels = list(b.get("levels") or ())
    if axis.length <= 1.0 or len(levels) != 2:
        return None
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
            "roads": roads, "road_bridge": str(b.get("id"))}


def road_deck_records(bridges: _t.Sequence[_t.Mapping], riding: _t.AbstractSet[str],
                      law, airport) -> tuple[list[dict], list[dict]]:
    """``(deck records, bridge records)``: every generated road bridge not
    ``riding`` a taxiway deck as a narrow flat deck (module doc), and every
    bridge's record without its X-Plane chain (its span still clips the
    pack's pages)."""
    _to_xy, to_ll = airport.frame.transformers()
    decks = []
    for b in bridges:
        if str(b.get("id")) in riding:
            continue
        rec = _record(b, law, to_ll)
        if rec is not None:
            decks.append(rec)
    keep = [{k: v for k, v in dict(b).items()
             if k not in ("span_xy", "ground", "junctions", "subtype", "net")}
            for b in bridges]
    return decks, keep
