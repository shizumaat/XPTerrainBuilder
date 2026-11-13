"""THE DECK STACK'S ROWS (#1971; spec ``interchange-levels-20261113.md``
§3.7, §3.8, amended by ``interchange-levels-v2-20261113.md`` §3.3).  The
floor itself is an object floor (``constraints/object_floor`` pins it, at
no clearance: v2 §3.1); this generator states the rest of a stack
(``Airport.deck_stacks``, ``model/deck_stack``) on the map's vertices and
on the stack's own ground (``planar/stack_ground``), every row under the
hard-deck bridge's ONE ruling head (``edge_deck.RIGID``: one zero, flush at
both end lines — RULINGS 2026-10-30a):

* R1 each END EDGE: the end-line road vertices (``airport/deck_ends.
  end_road_vertices``, the ONE selection the road ramp is seeded from) and
  every stack-ground vertex on a deck's end line or on its approach slab
  (``airport/deck_ends.ground_footprint``'s ``slabs``, one sample step
  beyond it) stand in ``[zero + top - deck_flush_m, zero + top]`` — the
  ground and the road never stand over the plate's end;
* R2 the WALLS' TOP and the CAPS: every cap vertex, every vertex of the
  floor's void band's outer ring along a wall line and every stack-ground
  vertex across the stand-off gap from it stand in ``[crest - visual_m /
  2, crest - deck_flush_m]`` (both sides of the gap at the top);
* R3 UNDER A DECK: a vertex inside a deck's ring (or on its own ground's
  rectangle) and off the floor stays under the plate there (``zero +
  plate y - deck_flush_m``) — no ground through a deck.

Where two rows cannot both hold the senior one stays: R3 over R1 of
another deck, R1 over R2, R3 over R2.  The toe (R4) is
``constraints/fill_bank``'s; the target (R5) the ground datum.  With no
stack the generator returns ``[]``.
"""
from __future__ import annotations

import numpy as np

from ..airport.deck_ends import end_road_vertices, ground_footprint
from ..geom.end_line import polyline_distance
from ..geom.lowest_face import floor_z_at
from ..law import Law
from ..law.tables import snap_margin_m
from ..model.airport import Airport
from ..model.constraints import Band, Row, Source
from ..model.planar import STACK_GROUND_PREFIX, PlanarMap
from .edge_deck import RIGID

__all__ = ["GEN", "deck_stack_rows"]

GEN = "deck_stack"


def _xy(planar: PlanarMap, ids) -> np.ndarray:
    return np.array([planar.vertices[v].xy for v in ids], float).reshape(-1, 2)


def _ref_vertices(planar: PlanarMap, pred) -> set[int]:
    out: set[int] = set()
    for f in planar.faces.values():
        if pred(f.ref):
            out.update(planar.ring_vertices(f.ring))
            for h in getattr(f, "holes", ()) or ():
                out.update(planar.ring_vertices(h))
    return out


def _ceilings(planar: PlanarMap, st, d, ids: list[int], flush: float) -> dict[int, float]:
    """R3's ceiling ``zero + plate y - flush`` on each vertex of ``ids``
    (off the plate: its lowest point)."""
    plate = np.asarray(d.plate, float).reshape(-1, 3, 3)
    if not ids:
        return {}
    xy = _xy(planar, ids)
    ys = floor_z_at(plate, xy[:, 0], xy[:, 1], edge_m=0.5)
    lo = float(plate[:, :, 2].min()) if len(plate) else min(d.top_a, d.top_b)
    return {v: float(st.zero_z) + (y if y == y else lo) - flush
            for v, y in zip(ids, ys.tolist(), strict=True)}


def deck_stack_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The stacks' R1-R3 rows (module doc)."""
    import shapely
    from shapely.geometry import Polygon
    stacks = tuple(getattr(airport, "deck_stacks", ()) or ())
    if not stacks:
        return []
    br = law.tables.structures.bridge
    flush = float(br.deck_flush_m)
    visual = float(law.tables.emit.cockpit.visual_m)
    thick = float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    #: how far from a wall line the stack ground's own edge stands: the void
    #: band, the groundside stand-off past it, the identity grid
    gap = (0.5 * thick + float(law.tables.zones.adjacent_ground.groundside_cutback_m)
           + snap_margin_m(law) + grid)
    roads = end_road_vertices(planar, law, airport)
    rows: list[Row] = []
    for st in stacks:
        floor_vs = _ref_vertices(planar, lambda r, st=st: r.split("#")[0] == st.floor_ref)
        if not floor_vs:
            continue                    # the floor never entered the map
        z0 = float(st.zero_z)
        mine = STACK_GROUND_PREFIX + st.id + ":"
        ground = sorted(_ref_vertices(planar, lambda r, m=mine: r.startswith(m)) - floor_vs)
        caps = _ref_vertices(planar, lambda r, m=mine + "cap#": r.startswith(m)) - floor_vs
        gxy = _xy(planar, ground)
        # R1: vertex -> (low, high, deck, part)
        r1: dict[int, tuple[float, float, str, str]] = {}
        refused: set[int] = set()
        for v, (z, sid, oid, part) in roads.items():
            if sid == st.id:
                r1[v] = (z - flush, z, oid, part)
        for d, side, top, slab in ground_footprint(st, law)["slabs"]:
            if slab.is_empty or not len(ground):
                continue
            z = z0 + float(top)
            on = shapely.contains_xy(slab.buffer(grid, join_style="mitre"), gxy[:, 0], gxy[:, 1])
            for k in np.flatnonzero(on).tolist():
                v = ground[k]
                if v in r1 and abs(r1[v][1] - z) > flush:
                    refused.add(v)              # two end lines meet in plan (v1 §4)
                r1.setdefault(v, (z - flush, z, d.object_id,
                                  f"{d.object_id}#{d.piece} end {side}"))
        # R3: vertex -> ceiling (the lowest over every deck above it)
        allv = [v for v in planar.vertices if v not in floor_vs]
        axy = _xy(planar, allv)
        gset = set(ground)
        r3: dict[int, tuple[float, str]] = {}
        for d in st.decks:
            ring = Polygon(d.ring)
            rect = ring.minimum_rotated_rectangle.buffer(grid, join_style="mitre")
            inside = shapely.contains_xy(ring, axy[:, 0], axy[:, 1]) if len(allv) else []
            on_rect = shapely.contains_xy(rect, axy[:, 0], axy[:, 1]) if len(allv) else []
            ks = [allv[k] for k in range(len(allv))
                  if (inside[k] or (on_rect[k] and allv[k] in gset))
                  and not (allv[k] in r1 and r1[allv[k]][2] == d.object_id)]
            for v, c in _ceilings(planar, st, d, ks, flush).items():
                if v not in r3 or c < r3[v][0]:
                    r3[v] = (c, f"{d.object_id}#{d.piece} under the deck")
        for v, (lo, hi, oid, part) in sorted(r1.items()):
            if v in refused or (v in r3 and lo > r3[v][0]):
                continue                        # R3 is senior; two ends: refused
            rows.append(Band(v, lo, hi, Source(GEN, RIGID, (st.id, oid, part))))
        # R2: the walls' top and the caps
        crest = z0 + float(st.crest_y)
        band = sorted(_ref_vertices(planar, lambda r, w=st.wall_ref: r.split("#")[0] == w)
                      - floor_vs)
        r2 = set(caps)
        if band and st.rim:
            bxy = _xy(planar, band)
            d_rim = np.min([polyline_distance(bxy, r) for r in st.rim], axis=0)
            r2.update(v for v, dd in zip(band, d_rim.tolist(), strict=True) if dd <= thick)
        if ground and st.rim:
            # the stack ground across the stand-off gap from the void band
            # (a bank where no cap stands): both sides of the gap at the top
            d_rim = np.min([polyline_distance(gxy, r) for r in st.rim], axis=0)
            r2.update(v for v, dd in zip(ground, d_rim.tolist(), strict=True) if dd <= gap)
        lo2, hi2 = crest - 0.5 * visual, crest - flush
        src2 = Source(GEN, RIGID, (st.id, st.walls_id, "the walls' top"))
        rows.extend(Band(v, lo2, hi2, src2) for v in sorted(r2)
                    if v not in r1 and not (v in r3 and lo2 > r3[v][0]))
        for v, (c, part) in sorted(r3.items()):
            rows.append(Band(v, None, c, Source(GEN, RIGID, (st.id, part.split("#")[0], part))))
    return rows
