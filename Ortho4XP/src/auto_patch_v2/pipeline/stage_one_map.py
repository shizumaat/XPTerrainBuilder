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

from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear,
                                 Offset, Pin)

__all__ = ["StageOne", "ribbon_free", "stage_one_problem", "remap_row"]


def ribbon_free(cl):
    """``cl`` without its mapped-road ribbon cells, or ``None`` when it has
    none (then the map IS ribbon-free and stage 1 is assembled on it)."""
    from ..classify.roles import is_osm_ribbon
    cells = tuple(c for c in cl.cells if not is_osm_ribbon(c))
    if len(cells) == len(cl.cells):
        return None
    return _dc.replace(cl, cells=cells)


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


def _items(vertices):
    """``(id, vertex)`` of a map's vertex table (a dict, or a list)."""
    return vertices.items() if isinstance(vertices, dict) else enumerate(vertices)


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
