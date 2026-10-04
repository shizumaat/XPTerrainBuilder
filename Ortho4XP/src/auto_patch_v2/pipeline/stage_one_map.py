"""STAGE 1 IS ASSEMBLED ON THE RIBBON-FREE MAP (issue #100, round 8; owner
RULINGS 2026-09-30z (1) "airside is king", 30aa rule 1; PM master decision
option (c), 2026-10-03).

THE RULE.  §20b's stage 1 — the airside problem, solved first — is built
from the planar map WITHOUT any mapped-road ribbon: the classification with
its ribbon cells removed goes through the caller's OWN prefix (the planar
build, the target channels, the shape stage, the constraint generators, the
jetway strips and the hold binding).  That is exactly the problem the build
had before ribbons existed, so every stage-1 row, column, triangle and sheet
face is the ribbon-free map's BY CONSTRUCTION, and a ribbon can reach no
stage-1 row however it displaces a groundside face along the airside rim.
The ribbons are minted onto the finished map (``planar/ribbons``, pass C)
and contribute ONLY stage-2 rows: stage 2 solves the full map with every
airside column stage 1 levelled substituted as a constant.

WHY NOT A VIEW.  Rounds 4-7 tried to keep one map and veto the ribbons'
effect per consumer (separators, shape labels, edge portions, then ghost
rings re-minting the displaced face's rows): every veto left a residue
(round 7, HECA: 82 one-sided stage-1 rows removed -> 8, but 22 -> 292
added).  Deriving stage 1 off its own map trims at the single derivation
site (owner RULINGS 2026-08-30l) — there is nothing to veto.

THE JOIN between the two maps is CANONICAL: by vertex coordinate, which
pass C keeps byte-identical for every airside and pad vertex (the round-6
bar ``ribbon_airside_added / _removed`` 0 / 0).  Stage 1's levels, its
released pins, its fronting set and its hold rows cross by that join; a
vertex the full map does not carry is COUNTED (``unmapped``), never guessed.

THE MODULE REGISTRIES (``pipeline/capture_state``) the planar stage fills
and the generators read are the ribbon-free map's while stage 1 is derived
and solved (:meth:`StageOne.scope`), and the caller's own everywhere else.
"""
from __future__ import annotations

import contextlib
import dataclasses as _dc
import typing as _t

from ..model.planar import face_vertex_set as _face_vertices
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear,
                                 Offset, Pin)

__all__ = ["StageOne", "ribbon_free", "stage_one_problem", "remap_row",
           "gap_free", "late_followers", "late_fixed", "late_constraints",
           "row_vertices", "late_rim_levels"]


def ribbon_free(cl):
    """``cl`` without its mapped-road ribbon cells, or ``None`` when it has
    none (then the map IS ribbon-free and stage 1 is assembled on it)."""
    from ..classify.roles import is_late_cell
    cells = tuple(c for c in cl.cells if not is_late_cell(c))
    if len(cells) == len(cl.cells):
        return None
    return _dc.replace(cl, cells=cells)


def _items(vertices):
    """``(id, vertex)`` of a map's vertex table (a dict, or a list)."""
    return vertices.items() if isinstance(vertices, dict) else enumerate(vertices)


def gap_free(cl):
    """``cl`` without its §53 gap pieces, or ``None`` when it has none —
    THE BASE MAP of the last stage (below)."""
    from ..model.planar import is_gap_ref
    cells = tuple(c for c in cl.cells if not is_gap_ref(getattr(c, "ref", "")))
    if len(cells) == len(cl.cells):
        return None
    return _dc.replace(cl, cells=cells)


def late_followers(pm_full, soft_roles: _t.AbstractSet[str] = frozenset()
                   ) -> tuple[set[int], dict]:
    """THE LAST STAGE'S UNKNOWNS (spec §53 (9); owner RULINGS 2026-10-04o/q,
    master 2026-10-04: "pieces follow, never lead"): the vertices of every
    §53 GAP PIECE, and of every mapped-road RIBBON
    (``model.planar.is_osm_ribbon_ref``) whose ring carries a vertex of a gap
    piece (``model.planar.gap_follower_faces``) — a road through or along a
    pavement is that pavement (the free-road ruling) — LESS every vertex a face that is neither carries:
    a pad, an airside face, an apt.dat road, an existing lot keeps the level
    the earlier stages gave it, and the follower grades up to it.  A face of
    a ``soft_roles`` role (the adjacent-ground bands, which adopt their
    value) does not hold a vertex.  ``(vertices, report)``."""
    from ..model.planar import gap_follower_faces
    gap, ribbons = gap_follower_faces(pm_full)
    follow = {f.id for f in gap} | {f.id for f in ribbons}
    free: set[int] = set()
    held: set[int] = set()
    for f in pm_full.faces.values():
        if f.id in follow:
            free |= _face_vertices(pm_full, f)
        elif f.role not in soft_roles:
            held |= _face_vertices(pm_full, f)
    rep = {"gap_faces": len(gap), "follower_ribbons": len(ribbons),
           "follower_ribbon_refs": sorted({str(f.ref) for f in ribbons}),
           "vertices": len(free - held), "held_on_a_leader": len(free & held)}
    return free - held, rep


#: metres of slack on the identity spacing: the emitter measures a pair in
#: its own local metres, the map in the airport frame
_IDENTITY_SLACK_M = 1e-3


def late_fixed(pm_base, z_base, pm_full, free: _t.AbstractSet[int],
               identity_m: float = 0.0) -> tuple[dict[int, float], dict]:
    """THE LAST STAGE'S CONSTANTS: the base map's solved level of every
    vertex the full map carries (the CANONICAL join, by coordinate — the
    one ``StageOne.bind`` makes) that is not ``free``.  A full-map vertex
    the base map lacks and no follower owns is COUNTED (``unjoined``) and
    left an unknown, never guessed.

    ONE EMITTED POINT WITH A STANDING VERTEX IS STANDING (spec §53 (18)):
    a follower the base map carries that lies within ``identity_m`` (the
    emitter's ``min_distinct_spacing_m``) of a constant is MERGED with it at
    emit (``emit/osm_adapter.merge_sub_spacing``), and the survivor may be
    the follower — its level is then the standing ring's emitted level.  It
    keeps the base's level (``held_at_identity``).  MEASURED at HECA: lot
    ``dsf:pol10``'s emitted ring carries ribbon ``big_roads:-1227``'s vertex
    0.5 m from its own, which moved 0.03 m as a follower."""
    at = {tuple(v.xy): i for i, v in _items(pm_full.vertices)}
    fixed: dict[int, float] = {}
    cand: dict[int, float] = {}
    miss = 0
    for i, v in _items(pm_base.vertices):
        j = at.get(tuple(v.xy))
        if j is None:
            miss += 1
        elif j not in free:
            fixed[j] = float(z_base[i])
        else:
            cand[j] = float(z_base[i])
    held = 0
    if identity_m > 0.0 and cand and fixed:
        from scipy.spatial import cKDTree
        fv = pm_full.vertices
        tree = cKDTree([fv[j].xy for j in fixed])
        near, _k = tree.query([fv[j].xy for j in cand],
                              distance_upper_bound=identity_m + _IDENTITY_SLACK_M)
        for (j, z), d in zip(list(cand.items()), near):
            if d != float("inf"):
                fixed[j] = z
                held += 1
    n_full = len(pm_full.vertices)
    return fixed, {"base_vertices": len(pm_base.vertices), "full_vertices": n_full,
                   "base_unmapped": miss, "fixed": len(fixed),
                   "held_at_identity": held,
                   "unjoined": n_full - len(fixed) - len(free) + held}


def late_rim_levels(pm_base, z_base, pm_full, fixed: dict[int, float],
                    free: _t.AbstractSet[int], tol_m: float) -> dict:
    """THE NEW NODE ON A STANDING EDGE STANDS ON THAT EDGE (spec §53 (11)).
    A follower's ring nodes the rim it shares with a standing cell, so the
    full map carries vertices the base map lacks that no follower owns.
    Each one lying within ``tol_m`` of a BASE edge is given that edge's own
    level at its foot — the linear interpolation of the edge's two solved
    ends — and joins ``fixed`` (in place): the standing cell's surface is
    the base's, with one more node on a straight edge.  A vertex on no base
    edge is counted (``off_edge``) and stays an unknown."""
    import shapely
    from shapely.strtree import STRtree
    todo = [j for j, _v in _items(pm_full.vertices) if j not in fixed and j not in free]
    rep = {"rim_nodes": len(todo), "on_a_base_edge": 0, "off_edge": 0}
    if not todo:
        return rep
    bv = pm_base.vertices
    edges = [e for e in pm_base.edges.values()] if isinstance(pm_base.edges, dict) \
        else list(pm_base.edges)
    lines = shapely.linestrings([[bv[e.a].xy, bv[e.b].xy] for e in edges])
    tree = STRtree(lines)
    pts = shapely.points([pm_full.vertices[j].xy for j in todo])
    near = tree.query_nearest(pts, max_distance=tol_m, all_matches=False)
    hit = {int(i): int(k) for i, k in zip(near[0], near[1])}
    for i, j in enumerate(todo):
        k = hit.get(i)
        if k is None:
            rep["off_edge"] += 1
            continue
        e = edges[k]
        length = float(shapely.length(lines[k]))
        t = float(shapely.line_locate_point(lines[k], pts[i])) / length if length else 0.0
        fixed[j] = (1.0 - t) * float(z_base[e.a]) + t * float(z_base[e.b])
        rep["on_a_base_edge"] += 1
    return rep


def row_vertices(row) -> tuple[int, ...]:
    """Every vertex ``row`` names (its ``follows`` leaders are not unknowns
    of the row and are not counted)."""
    if isinstance(row, (Pin, Band)):
        return (int(row.v),)
    if isinstance(row, (Diff, Offset)):
        return (int(row.a), int(row.b))
    if isinstance(row, Flat):
        return tuple(int(v) for v in row.group)
    if isinstance(row, Linear):
        return tuple(int(v) for v, _c in row.terms)
    raise TypeError(f"stage_one_map: unknown row type {type(row).__name__}")


def late_constraints(cs: ConstraintSet, fixed: _t.Mapping[int, float],
                     yield_heads: _t.AbstractSet[str] = frozenset()
                     ) -> tuple[ConstraintSet, dict]:
    """THE LAST STAGE'S OWN ROWS (spec §53 (10), master 2026-10-04): a row
    with NO unknown is not the last stage's.  Every row whose vertices are
    ALL constants of the earlier stages is dropped — so a PIN restated on
    the full map never moves an earlier stage's level (the reduction lets a
    pin outrank a substituted constant), and a law row between two fixed
    vertices is the earlier stage's residual, already published there, not
    a row this stage can answer for.  ``(set, {type: dropped})``."""
    kept, dropped = [], {}
    for r in cs.rows():
        if isinstance(r, Pin) and int(r.v) not in fixed \
                and str(r.source.ruling).split("(")[0].strip() in yield_heads:
            # A YIELDING PIN ON A FOLLOWER IS RELEASED (spec §53 (17)): a
            # follower ribbon's §37 (9) join pin is the core ribbon's level,
            # restated on the full map; the stage has no pin-yield pass, and
            # held hard it keeps the ribbon on its terrain against the fixed
            # ground beside it (MEASURED: ``small_roads:-18733`` pinned at
            # 87.51 beside an apron at 82.41)
            dropped["Pin (yielding, on a follower)"] = \
                dropped.get("Pin (yielding, on a follower)", 0) + 1
            continue
        if all(v in fixed for v in row_vertices(r)):
            k = type(r).__name__
            dropped[k] = dropped.get(k, 0) + 1
        else:
            kept.append(r)
    return ConstraintSet.from_rows(kept), dropped


def remap_row(row, vmap: _t.Mapping[int, int]):
    """``row`` with every vertex id read through ``vmap``; ``None`` when a
    vertex has no counterpart."""
    def m(v):
        return vmap.get(int(v))

    def mf(f):
        if f is None:
            return None
        if isinstance(f, tuple):
            out = tuple(m(v) for v in f)
            return None if None in out else out
        return m(f)
    if isinstance(row, Pin):
        v = m(row.v)
        return None if v is None else _dc.replace(row, v=v)
    if isinstance(row, Band):
        v = m(row.v)
        return None if v is None else _dc.replace(row, v=v)
    if isinstance(row, (Diff, Offset)):
        a, b = m(row.a), m(row.b)
        if a is None or b is None:
            return None
        if isinstance(row, Diff):
            fo = mf(row.follows)
            if row.follows is not None and fo is None:
                return None
            return _dc.replace(row, a=a, b=b, follows=fo)
        return _dc.replace(row, a=a, b=b)
    if isinstance(row, Flat):
        g = tuple(m(v) for v in row.group)
        return None if None in g else _dc.replace(row, group=g)
    if isinstance(row, Linear):
        ts = tuple((m(v), c) for v, c in row.terms)
        if any(v is None for v, _c in ts):
            return None
        fo = mf(row.follows)
        if row.follows is not None and fo is None:
            return None
        return _dc.replace(row, terms=ts, follows=fo)
    raise TypeError(f"stage_one_map: unknown row type {type(row).__name__}")


@_dc.dataclass
class StageOne:
    """The ribbon-free map's stage-1 problem, bound to the full map by
    coordinate.  ``solve.design.solve_design(stage1=...)`` reads it
    duck-typed (``solve`` may not import ``pipeline``)."""

    pm: _t.Any                 #: the ribbon-free PlanarMap
    cs: ConstraintSet          #: its constraint set
    strips: _t.Any             #: its jetway strips
    hold: _t.Any               #: its hold binding (``no_step.HoldPass``)
    state: dict                #: its capture-state record
    vmap: dict = _dc.field(default_factory=dict)   #: ribbon-free vid -> full vid
    unmapped: int = 0          #: ribbon-free vertices the full map lacks
    report: dict = _dc.field(default_factory=dict)

    def bind(self, pm_full) -> "StageOne":
        """The canonical join to the full map (vertex coordinate)."""
        at = {tuple(v.xy): i for i, v in _items(pm_full.vertices)}
        self.vmap = {}
        miss = 0
        for i, v in _items(self.pm.vertices):
            j = at.get(tuple(v.xy))
            if j is None:
                miss += 1
            else:
                self.vmap[i] = j
        self.unmapped = miss
        self.report.update(vertices=len(self.pm.vertices),
                           full_vertices=len(pm_full.vertices), unmapped=miss)
        return self

    @contextlib.contextmanager
    def scope(self):
        """The ribbon-free map's module registries, installed for the
        duration; the caller's restored after."""
        from . import capture_state as _cs
        saved = _cs.collect()
        _cs.install(self.state)
        try:
            yield self
        finally:
            self.state = _cs.collect()   # stage 1's own mutations stay its own
            _cs.install(saved)

    def to_full(self, vid: int) -> int | None:
        return self.vmap.get(int(vid))

    def rows_to_full(self, rows) -> tuple[list, int]:
        out, lost = [], 0
        for r in rows:
            q = remap_row(r, self.vmap)
            if q is None:
                lost += 1
            else:
                out.append(q)
        return out, lost

    def apply_full(self, cs_full: ConstraintSet) -> ConstraintSet:
        """``HoldPass.apply`` on the FULL map's set: the hold rows pass 1b
        derived on the ribbon-free map, carried by the join."""
        res = getattr(self.hold, "result", None)
        if self.hold is None or res is None:
            return cs_full
        base = self.hold.strip(cs_full) or cs_full
        rows, lost = self.rows_to_full(res.rows)
        self.report["hold_rows_unmapped"] = lost
        return ConstraintSet.from_rows([*base.rows(), *rows])

    def planar_of_full(self, pm_full):
        """``HoldPass.planar_of`` on the FULL map: the fronting set pass 1b
        published, carried by the join."""
        res = getattr(self.hold, "result", None)
        fr = getattr(res, "fronting", None)
        if not fr:
            return pm_full
        fv = frozenset(j for j in (self.to_full(v) for v in fr) if j is not None)
        fref = {j: z for v, z in dict(res.fronting_ref).items()
                if (j := self.to_full(v)) is not None}
        return _dc.replace(pm_full, fronting_vertices=fv, fronting_ref=fref)


def stage_one_problem(cl, derive: _t.Callable[[_t.Any], tuple]) -> StageOne | None:
    """THE RIBBON-FREE STAGE-1 PROBLEM: ``derive(cl0) -> (pm, cs, strips,
    hold)`` is the CALLER's own prefix (the build's, the replay's) run on
    the classification without ribbons.  ``None`` when ``cl`` carries no
    ribbon.  The registries the derivation fills are recorded as the
    problem's own and the caller's are restored."""
    cl0 = ribbon_free(cl)
    if cl0 is None:
        return None
    from . import capture_state as _cs
    saved = _cs.collect()
    try:
        pm0, cs0, strips0, hold0 = derive(cl0)
        state0 = _cs.collect()
    finally:
        _cs.install(saved)
    return StageOne(pm0, cs0, strips0, hold0, state0,
                    report={"ribbon_cells": len(cl.cells) - len(cl0.cells)})
