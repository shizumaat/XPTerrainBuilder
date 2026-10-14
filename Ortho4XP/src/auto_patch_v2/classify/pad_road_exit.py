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
leaves the patch off a pad road — or straight off a pad's own edge (a
garage entry) — the road network is walked outward for THE RAMP'S RUN: the
pad's height over the ground at that exit, at the design grade
(``[road_contact] ramp_grade``), or until the road re-enters the patch.
What is walked is minted as more pad road and read by the one touch
witness (``roles._cut_back_groundside``), so an exit that reaches another
pad is welded to it.  Nothing standing is overlapped.

THE RUN IS THE PAD'S OFFSET, NOT A SEARCH OF THE TERRAIN (round 5).  The
walk used to run on "until a profile from the pad's level at the design
grade meets the terrain" (the road-exit law's own test, 29y).  MEASURED
KASE, 3 exits: where the valley falls away along the road faster than the
design grade that profile never meets the ground — 2,295 m of ribbon, four
branches stopped by the 1,000 m bound alone.  A ramp closes the pad's
OFFSET from its ground; the ground's own slope is the road's
(``constraints/pad_ramp.pad_ramp_rewrite`` lays the same profile).

TWO THINGS ARE NOT WALKED.  An exit whose pad already stands within one
lane width of design grade of the terrain there (the join law's own
allowance, ``constraints/road_ramp._run_grade``: "an end inside one lane
width asks nothing").  And A BRANCH THAT LEADS NOWHERE: a walked stretch
ending at a dead end of the mapped network before its run is complete
is no ramp — MEASURED KCLT, way ``-24651``: a 17 m stub through a
garage's lip ending 1 m beyond it was minted as an 8 x 1 m cell 5 m under
the pad, 38-51 % over 10 m.  It stays what it is on the map: a road that
ends at the pad.
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
                 law: Law) -> list[tuple[float, float] | None]:
    """Each pad-road cell's pad levels, ``(lowest, highest)``, over THE
    NETWORK it belongs to (the cells reached through touching cells): the
    level a road leaves the patch at is its nearest pad's along the road,
    which is known only once the roads are solved — any pad of the network
    may be that one, so the run is sized for the farthest from the ground
    (MEASURED KCLT way ``-13743``: sized for a small pad at 220.7 m, the
    exit stood at the terminal's 222.6 m and left the patch 2.6 m up)."""
    from .pad_touch import EVIDENCE_KEY, is_touching
    own = [[pad_levels[r] for r, d in (c.evidence.get(EVIDENCE_KEY) or {}).items()
            if r in pad_levels and is_touching(law, d)] for c in roads]
    tree = STRtree(polys)
    out: list[tuple[float, float] | None] = [None] * len(roads)
    seen: set[int] = set()
    for i in range(len(roads)):
        if i in seen:
            continue
        seen.add(i)
        comp, queue, zs = [], [i], []
        while queue:
            k = queue.pop()
            comp.append(k)
            zs.extend(own[k])
            for j in tree.query(polys[k].buffer(0.05), predicate="intersects").tolist():
                if j not in seen:
                    seen.add(j)
                    queue.append(j)
        if zs:
            for k in comp:
                out[k] = (min(zs), max(zs))
    return out


def _prune_dead_ends(pieces: set[tuple[int, float, float, tuple, tuple]],
                     ends_ok: set[tuple]) -> set:
    """``pieces`` (``way index, s0, s1, node a, node b``) less every branch
    that ends at a node no other piece continues from and that is not in
    ``ends_ok`` (an exit, a completed run, a re-entry, the reach bound)."""
    live = set(pieces)
    while True:
        deg: dict[tuple, int] = {}
        for _i, _s0, _s1, a, b in live:
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
        dead = {p for p in live
                if any(deg[n] == 1 and n not in ends_ok for n in (p[3], p[4]))}
        if not dead:
            return live
        live -= dead


def extend_pad_roads(cl, airport, law: Law, rules: Rules,
                     pad_levels: _t.Mapping[str, float]) -> tuple[_t.Any, dict]:
    """``cl`` with every pad road run on from its patch exits (module doc);
    ``pad_levels`` is ``{pad ref: its solved level}``.  ``(cl, report)`` —
    the report counts the exits walked, the cells added and their run."""
    from .roles import Cell, _cut_back_groundside
    from ..law.tables import role_side
    rep = {"exits": 0, "cells": 0, "run_m": 0.0, "run_complete": 0, "re_entered": 0,
           "out_of_reach": 0, "at_grade": 0, "dead_end_pieces": 0, "welded": 0}
    dem = getattr(airport, "dem", None)
    roads = [c for c in cl.cells if c.evidence.get("pad_road")]
    ways = _ribbon_ways(airport, rules)
    if not roads or not ways or dem is None or not pad_levels:
        return cl, rep
    g = float(law.tables.emit.road_contact.ramp_grade)
    hw = float(law.tables.emit.road_profile.lane_width_m)
    snap = float(rules.cells.snap_grid_m)
    polys = [Polygon(c.ring, c.holes) for c in roads]
    levels = _cell_levels(roads, polys, pad_levels, law)
    pads = [(Polygon(c.ring, c.holes), float(pad_levels[c.ref])) for c in cl.cells
            if c.role == "building" and c.ref in pad_levels]
    occupied = unary_union([Polygon(c.ring, c.holes) for c in cl.cells])
    inside = occupied.buffer(snap)
    rtree = STRtree(polys)
    ptree = STRtree([q for q, _z in pads]) if pads else None

    def road_levels(p: Point) -> list[float]:
        """The pad levels a road leaving the patch at ``p`` may carry: its
        pad road's network's there, else that of the pad whose own edge it
        leaves.  ``p`` must stand ON that cell's edge (the way's own
        crossing of the patch edge): a way that only passes beside a pad
        road leaves nothing (MEASURED KCLT way ``-13743``, a road 1 m
        beside a pad road and 2.3 m under it: its vertices within a lane
        of the pad road were read as exits and 28 m of it minted at the
        pad road's level, a cliff at both ends)."""
        js = rtree.query(p, predicate="dwithin", distance=2.0 * snap).tolist()
        zs = [z for j in js if levels[j] is not None for z in levels[j]]
        if not zs and ptree is not None:
            zs = [pads[j][1] for j in
                  ptree.query(p, predicate="dwithin", distance=2.0 * snap).tolist()]
        return zs

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
    # the exits: a node of an outside edge that stands on a pad road or on
    # a pad's edge, the pad more than a lane of design grade off the ground
    heap: list[tuple[float, tuple, float]] = []
    best: dict[tuple, float] = {}
    ends_ok: set[tuple] = set()
    for n in sorted(adj):
        zs = road_levels(Point(n))
        if not zs:
            continue
        ground = float(dem.z(*n))
        off = max(abs(ground - z) for z in zs)
        if off <= g * hw:
            rep["at_grade"] += 1
            continue
        best[n] = 0.0
        heap.append((0.0, n, off / g))       # the run this exit's ramp needs
        ends_ok.add(n)
    rep["exits"] = len(heap)
    heapq.heapify(heap)
    pieces: set[tuple[int, float, float, tuple, tuple]] = set()
    while heap:
        d, n, need = heapq.heappop(heap)
        if d > best.get(n, float("inf")):
            continue
        if d > 0.0:
            if inside.distance(Point(n)) <= 2e-3:
                rep["re_entered"] += 1
                ends_ok.add(n)
                continue
            if d >= need:
                rep["run_complete"] += 1
                ends_ok.add(n)
                continue
        for i, s0, s1, m in adj[n]:
            nd = d + (s1 - s0)
            if nd > MAX_REACH_M:
                rep["out_of_reach"] += 1
                ends_ok.add(n)
                continue
            # the piece is the road's whether or not its far node was
            # reached sooner from another exit (a stretch between two exits)
            pieces.add((i, s0, s1, *sorted((n, m))))
            if nd < best.get(m, float("inf")):
                best[m] = nd
                heapq.heappush(heap, (nd, m, need))
    kept = _prune_dead_ends(pieces, ends_ok)
    rep["dead_end_pieces"] = len(pieces) - len(kept)
    walked: dict[int, list[tuple[float, float]]] = {}
    for i, s0, s1, _a, _b in sorted(kept):
        walked.setdefault(i, []).append((s0, s1))
    if not walked:
        return cl, rep
    serial: dict[str, int] = {}
    for c in cl.cells:
        base, _h, k = str(c.ref).partition("#")
        serial[base] = max(serial.get(base, 0), (int(k) if k.isdigit() else 0) + 1)
    cells = list(cl.cells)
    n_before = len(cells)

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
    # THE ONE TOUCH WITNESS (09j (2)), read on the new cells only and never
    # holding a hillside terrace (13a (3)), as ``roles`` reads the pad roads
    cells, _n = _cut_back_groundside(cells, law, rules, airport, hold=False,
                                     only=range(n_before, len(cells)))
    from .pad_touch import WELD_KEY
    rep["welded"] = sum(1 for c in cells[n_before:] if c.evidence.get(WELD_KEY))
    return _dc.replace(cl, cells=tuple(cells)), rep
