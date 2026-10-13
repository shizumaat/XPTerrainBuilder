"""THE PAD ROAD'S RAMP IS INSIDE THE PATCH (issue #609; owner RULINGS
2026-10-13a (1)/(3), 13d: "a road welded to a building pad takes the pad's
level at the weld and climbs to it at the least grade that fits").

A pad road is minted over the pad and the paths between pads
(``ribbon_mint.mint_pad_roads``); where its way then LEAVES the patch the
pad's level stands a few metres from the terrain and the road would step
down the patch edge (MEASURED KCLT, the three garages at 223 m over ground
at 218 m: 47-55 % over 10 m at seven exits).  The road-exit law (29y,
``ribbon_mint.exit_reach``) already says what to do — the ribbon runs on
until a profile from the patch's level meets the terrain — but it reads the
patch's level off the DEM, and a pad's level is not known before the solve.

It IS known in the last stage, where the pad roads are solved: this module
rewrites the classification there.  From every point where a mapped road
leaves the patch off a pad road, the road network is walked outward until a
profile falling (or climbing) from the pad's SOLVED level at the design
grade (``[road_contact] ramp_grade``) meets the terrain, or the road
re-enters the patch; what is walked is minted as more pad road.  Nothing
standing is overlapped.
"""
from __future__ import annotations

import dataclasses as _dc
import heapq
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from .ribbon_mint import (_arc_cuts, _mint_spans, _ribbon_ways, _way_intervals,
                          bridge_gaps)
from .rules import Rules

__all__ = ["extend_pad_roads", "MAX_REACH_M"]

#: the walk's bound — ``ribbon_mint.exit_reach``'s own ``max_reach_m``
MAX_REACH_M = 1000.0


def _key(x: float, y: float) -> tuple[float, float]:
    return (round(float(x), 3), round(float(y), 3))


def _cell_levels(roads: list, polys: list[Polygon], pad_levels: _t.Mapping[str, float],
                 law: Law) -> list[float | None]:
    """Each pad-road cell's pad level: its own welded pad's, else the level
    of the nearest cell that has one, through touching cells."""
    from .pad_touch import EVIDENCE_KEY, is_touching
    lv: list[float | None] = []
    for c in roads:
        refs = [r for r, d in (c.evidence.get(EVIDENCE_KEY) or {}).items()
                if r in pad_levels and is_touching(law, d)]
        lv.append(min(pad_levels[r] for r in refs) if refs else None)
    tree = STRtree(polys)
    queue = [i for i, z in enumerate(lv) if z is not None]
    while queue:
        i = queue.pop(0)
        for j in tree.query(polys[i].buffer(0.05), predicate="intersects").tolist():
            if lv[j] is None:
                lv[j] = lv[i]
                queue.append(j)
    return lv


def extend_pad_roads(cl, airport, law: Law, rules: Rules,
                     pad_levels: _t.Mapping[str, float]) -> tuple[_t.Any, dict]:
    """``cl`` with every pad road run on from its patch exits (module doc);
    ``pad_levels`` is ``{pad ref: its solved level}``.  ``(cl, report)`` —
    the report counts the exits walked, the cells added and their run."""
    from .roles import Cell
    from ..law.tables import role_side
    rep = {"exits": 0, "cells": 0, "run_m": 0.0, "met_terrain": 0, "re_entered": 0,
           "out_of_reach": 0}
    dem = getattr(airport, "dem", None)
    roads = [c for c in cl.cells if c.evidence.get("pad_road")]
    ways = _ribbon_ways(airport, rules)
    if not roads or not ways or dem is None or not pad_levels:
        return cl, rep
    g = float(law.tables.emit.road_contact.ramp_grade)
    hw = float(law.tables.emit.road_profile.lane_width_m)
    polys = [Polygon(c.ring, c.holes) for c in roads]
    levels = _cell_levels(roads, polys, pad_levels, law)
    occupied = unary_union([Polygon(c.ring, c.holes) for c in cl.cells])
    inside = occupied.buffer(rules.cells.snap_grid_m)
    rtree = STRtree(polys)

    def road_level(p: Point) -> float | None:
        js = rtree.query(p.buffer(hw), predicate="intersects").tolist()
        zs = [levels[j] for j in js if levels[j] is not None]
        return min(zs) if zs else None

    # the network outside the patch: each way cut at its own vertices and
    # where it crosses the patch edge (``ribbon_mint``'s own cuts), one edge
    # per piece off every cell
    adj: dict[tuple, list[tuple[int, float, float, tuple]]] = {}
    for i, (_w, ln) in enumerate(ways):
        cuts = _arc_cuts(ln, _way_intervals(ln, inside))
        for s0, s1 in zip(cuts, cuts[1:]):
            if s1 - s0 <= 1e-6 or inside.covers(ln.interpolate(0.5 * (s0 + s1))):
                continue
            p0, p1 = ln.interpolate(s0), ln.interpolate(s1)
            a, b = _key(p0.x, p0.y), _key(p1.x, p1.y)
            adj.setdefault(a, []).append((i, s0, s1, b))
            adj.setdefault(b, []).append((i, s0, s1, a))
    # the exits: a node of an outside edge that stands on a pad road
    heap: list[tuple[float, tuple, float]] = []
    best: dict[tuple, float] = {}
    for n in adj:
        z0 = road_level(Point(n))
        if z0 is not None:
            best[n] = 0.0
            heap.append((0.0, n, z0))
    rep["exits"] = len(heap)
    heapq.heapify(heap)
    walked: dict[int, list[tuple[float, float]]] = {}
    while heap:
        d, n, z0 = heapq.heappop(heap)
        if d > best.get(n, float("inf")):
            continue
        if d > 0.0:
            if inside.distance(Point(n)) <= 2e-3:
                rep["re_entered"] += 1
                continue
            if abs(float(dem.z(*n)) - z0) <= g * d:
                rep["met_terrain"] += 1
                continue
        for i, s0, s1, m in adj[n]:
            nd = d + (s1 - s0)
            if nd > MAX_REACH_M:
                rep["out_of_reach"] += 1
                continue
            # the piece is the road's whether or not its far node was
            # reached sooner from another exit (a stretch between two exits)
            walked.setdefault(i, []).append((s0, s1))
            if nd < best.get(m, float("inf")):
                best[m] = nd
                heapq.heappush(heap, (nd, m, z0))
    if not walked:
        return cl, rep
    serial: dict[str, int] = {}
    for c in cl.cells:
        base, _h, k = str(c.ref).partition("#")
        serial[base] = max(serial.get(base, 0), (int(k) if k.isdigit() else 0) + 1)
    cells = list(cl.cells)

    def add(role, ref, part, kind, cn, cl_, ev):
        cells.append(Cell(len(cells), role, ref, tuple(part.exterior.coords)[:-1],
                          tuple(tuple(h.coords)[:-1] for h in part.interiors), cn, cl_,
                          role_side(law, role), kind, dict(ev)))
    for i in sorted(walked):
        w, line = ways[i]
        spans = bridge_gaps(sorted(walked[i]), 1e-6)
        k, m2, rib = _mint_spans(w, line, spans, occupied, serial, Polygon(), law, rules,
                                 add, {"pad_road": 1.0, "pad_exit": 1.0}, min_len=0.0)
        rep["cells"] += k
        rep["run_m"] += sum(b - a for a, b in spans) if k else 0.0
        if rib is not None:
            occupied = unary_union([occupied, rib])
    rep["run_m"] = round(rep["run_m"], 1)
    cells = [_dc.replace(c, id=j) for j, c in enumerate(cells)]
    return _dc.replace(cl, cells=tuple(cells)), rep
