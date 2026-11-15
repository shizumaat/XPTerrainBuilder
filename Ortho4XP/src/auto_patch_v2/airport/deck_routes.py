"""THE ROUTES AROUND EVERY PACK DECK (#2090; owner RULINGS 2026-11-14f (1):
"All bridges in a scenery pack should be seated and graded regardless of
distance from the airport").

The load (``airport/load``) reads the OSM feeds' ways with a vertex inside
the ``radius_deg`` box about the airport's reference point.  A pack deck
standing at or past that box's edge had no mapped route: KDEN's
Outer_Train_Bridge viaduct (rail ways -4162 / -4165, ``bridge=viaduct``)
stands 0.06 degrees out, so the pack stage read "W1 route: no mapped route"
and nothing graded its ends.

Read once at the pack stage, before the deck stacks and the free bridges
(``pipeline/build``): for every pack deck (a placement with a deck top,
``PlacedObject.deck_top_z``) whose REACH box leaves the loaded box, the
feeds' ``highway`` / ``railway`` ways are read around it and the ones the
bridge readers walk are added to ``Airport.osm_ways``:

* every way of the route the deck CARRIES, W1's own reading
  (``bridge_witness.route_of`` over the feed) — a way passing under it is
  the bridge layer's and is not read;
* from each of its two ends, the straightest continuation through the
  feed's way joins (``bridge_end_state._pick``, the path rule 3 walks) for
  REACH metres: the deck's top over its anchor ground at the rail grade
  (``[tunnel] rail_ramp_grade``, the shallowest ramp a bridge end takes),
  plus one ``abutment_sample_step_m`` — the longest ramp its ends can need.

Nothing else of the feed is added: a road beside or under the deck that no
ramp follows stays out of the patch, as it was.  They go into
``Airport.osm_ways`` and, where a stack rewrote the ways, into
``osm_ways_mapped`` too (a replay re-derives every stack from it).  Nothing here names a pack, a
resource or an airport.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, box

__all__ = ["attach_deck_routes"]

XY = tuple[float, float]


class _Way:
    """A feed way in the frame: what ``bridge_end_state._Graph`` reads."""

    __slots__ = ("id", "points", "tags", "raw", "feed")

    def __init__(self, k: int, points, tags, raw, feed: str) -> None:
        self.id, self.points, self.tags, self.raw, self.feed = k, points, tags, raw, feed


def _decks(objects, law) -> list[tuple[_t.Any, float]]:
    """``(ring, reach m)`` of every pack deck (module doc)."""
    from shapely.geometry import Polygon

    from .rebake_plan import _deck_ring_xy
    st = law.tables.structures
    g = float(st.tunnel.rail_ramp_grade)
    step = float(st.bridge.abutment_sample_step_m)
    out = []
    for o in objects or ():
        top = getattr(o, "deck_top_z", None)
        if top is None or not getattr(o, "resolved", None):
            continue
        # the deck top over its anchor (``deck_top_z`` is rendered MSL)
        top = float(top) - float(getattr(o, "anchor_z", 0.0) or 0.0)
        try:
            ring = Polygon(_deck_ring_xy(o))
        except (AttributeError, TypeError, ValueError):
            continue
        if ring.is_empty or not ring.is_valid:
            ring = ring.buffer(0)
        if ring.is_empty:
            continue
        out.append((ring, max(float(top), 0.0) / g + step if g > 0.0 else step))
    return out


def _outside(decks, frame, radius_deg: float) -> list[tuple[_t.Any, float]]:
    """The decks whose reach box leaves the load's ``radius_deg`` box."""
    to_ll = frame.transformers()[1]
    lat0, lon0 = frame.origin
    out = []
    for ring, reach in decks:
        x0, y0, x1, y1 = ring.bounds
        corners = [to_ll(x, y) for x in (x0 - reach, x1 + reach)
                   for y in (y0 - reach, y1 + reach)]
        if any(abs(la - lat0) > radius_deg or abs(lo - lon0) > radius_deg
               for la, lo in corners):
            out.append((ring, reach))
    return out


def _feed_ways(osm_root: str, frame, region) -> list[_Way]:
    """Every route way of the road feeds with a vertex in ``region`` (frame
    metres), in the frame's entry projection (``load._vector_to_xy``)."""
    from . import osm as _osm
    from .bridge_end_state import _route
    to_xy = frame.entry()
    lat0, lon0 = frame.origin
    out: list[_Way] = []
    for feed in _osm.ROAD_FEEDS:
        doc = _osm.load_feed(osm_root, feed, lat0, lon0, 2.0)
        for w in doc.ways:
            if not _route(w):
                continue
            pts = tuple(to_xy(lo, la) for la, lo in w.points)
            if not region.intersects(LineString(pts)):
                continue
            out.append(_Way(len(out), pts, w.tags, w, feed))
    return out


def _walked(ways: list[_Way], decks, law) -> set[int]:
    """The ways the bridge readers walk from each deck (module doc)."""
    from .bridge_end_state import _Graph, _pick, _unit
    from .bridge_witness import route_of
    graph = _Graph(ways)
    take: set[int] = set()
    for ring, reach in decks:
        r = route_of(ring, graph.ways, law)
        if isinstance(r, str):
            continue
        for k in (graph.by_id[int(i)] for i in r.ways):
            take.add(k)
            pts = [tuple(map(float, p)) for p in graph.ways[k].points]
            for tip, prev in ((pts[-1], pts[-2]), (pts[0], pts[1])):
                h = _unit(tip[0] - prev[0], tip[1] - prev[1])
                used, run = list(take), 0.0
                while h is not None and run < reach:
                    pick = _pick(graph, tip, h, used)
                    if pick is None:
                        break
                    used.append(pick[1])
                    take.add(pick[1])
                    seg = [tip, *pick[2]]
                    run += LineString(seg).length
                    tip = seg[-1]
                    h = _unit(seg[-1][0] - seg[-2][0], seg[-1][1] - seg[-2][1])
    return {int(graph.ways[k].id) for k in take}


def attach_deck_routes(airport, objects, osm_root: str, law, radius_deg: float
                       ) -> tuple[_t.Any, list[str]]:
    """``(airport with the route ways around its far decks added to
    osm_ways, notes)`` (module doc); unchanged where every deck's reach lies
    inside the loaded box or no feed is to hand."""
    import dataclasses as _dc

    from ..model.airport import OsmWay
    from .load import _osm_id
    frame = getattr(airport, "frame", None)
    if not osm_root or frame is None or law is None:
        return airport, []
    far = _outside(_decks(objects, law), frame, float(radius_deg))
    if not far:
        return airport, []
    region = box(*far[0][0].buffer(far[0][1]).bounds)
    for ring, reach in far[1:]:
        region = region.union(box(*ring.buffer(reach).bounds))
    ways = _feed_ways(osm_root, frame, region)
    # the ways AS MAPPED (``osm_ways_mapped`` once a stack rewrote them): a
    # replay re-derives every stack from those
    mapped = getattr(airport, "osm_ways_mapped", None)
    have = {(w.kind, int(w.id)) for w in (mapped or airport.osm_ways)}
    add = []
    for k in sorted(_walked(ways, far, law)):
        w = ways[k]
        key = (w.feed, _osm_id(w.raw.id))
        if key in have:
            continue
        have.add(key)
        add.append(OsmWay(key[1], w.feed, w.points, w.raw.closed, w.raw.tags))
    if not add:
        return airport, [f"{len(far)} deck(s) reach past the feed box: no route way "
                         f"to add"]
    note = (f"{len(far)} deck(s) reach past the feed box: {len(add)} route way(s) "
            f"added ({', '.join(str(w.id) for w in add[:12])}"
            f"{', ...' if len(add) > 12 else ''}; RULINGS 2026-11-14f (1))")
    more = {"osm_ways": tuple(airport.osm_ways) + tuple(add)}
    if mapped is not None:
        more["osm_ways_mapped"] = tuple(mapped) + tuple(add)
    return _dc.replace(airport, **more), [note]
