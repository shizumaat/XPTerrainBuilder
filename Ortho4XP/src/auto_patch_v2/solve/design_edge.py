"""THE TAXIWAY EDGE's ROWS — the cross-section row and the membrane (owner
RULINGS 2026-10-09e; spec §61 (1)).

A taxi-family vertex off its centreline on a SHORT chain carried bending
only: no trend (§8.6.1 hands a face its chain's trend only where the chain
is long), no chord, no datum, no band.  Bending is eight orders softer than
the stiff rows, so those columns were a VALLEY of the objective and the QP's
tolerance exit landed them by unrelated inputs — a satisfied ceiling
somewhere else moved hundreds of them.  Two row families name them, both at
the taxi sheet's own bending price so the row NAMES the level and bending
still SHAPES the sheet:

* :func:`cross_section_rows` — ``z_v = (1 − t)·z_a + t·z_b`` at the foot of
  the vertex's perpendicular on its own face's chain
  (``PlanarMap.taxi_xsec``, derived in ``constraints/taxi_trend``: ``solve``
  imports ``law`` and ``model`` only).  The SOLVED centreline, so no DEM
  enters pavement (08t (1), 10v).  A runway contact enters as a constant.
* :func:`membrane_rows` — for a column still carrying no level row (a
  taxiway edge whose foot is past the reach or whose face no chain owns; in
  the airside stage, any pavement column no datum levels), one
  first-difference row to each bending neighbour: "level with what is
  beside it", because no centreline says more.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..law import Law
from ..model.planar import PlanarMap
from .rows import _Reduction, _Rows, _level_row_columns

__all__ = ["cross_section_rows", "membrane_rows"]

#: the breakline kind whose chains are the taxi centrelines (the kind
#: ``solve/design_assemble`` prices ``taxi_profile`` along)
TAXI_CENTERLINE = "taxi_centerline"


def cross_section_rows(planar: PlanarMap, rows: _Rows, red: _Reduction,
                       weight: float) -> set[int]:
    """One relational row per ``planar.taxi_xsec`` entry whose vertex is a
    free column and carries NO trend row (read here, at assembly, so a trend
    withdrawn after publication leaves the edge on its centreline).
    Returns the COLUMNS named — the membrane must not name them twice."""
    named: set[int] = set()
    if weight <= 0.0:
        return named
    trend = planar.taxi_trend_z
    for v, (a, b, t) in planar.taxi_xsec.items():
        col = int(red.col[v])
        if col < 0 or v in trend:
            continue
        terms: list[tuple[int, float]] = [(v, 1.0)]
        rhs = 0.0
        for end, coef in ((a, 1.0 - t), (b, t)):
            if coef <= 0.0:
                continue
            if isinstance(end, tuple):       # ("pin", the runway's value)
                rhs += coef * float(end[1])
            else:
                terms.append((int(end), -coef))
        if rows.add(terms, rhs, weight, ("taxi_xsec", v)):
            named.add(col)
    return named


def _bend_neighbours(rows: _Rows) -> dict[int, set[int]]:
    """Column -> the columns its BENDING rows couple it to (a bending row is
    centred on one column — its largest coefficient — and reaches that
    centre's mesh neighbours)."""
    nb: dict[int, set[int]] = {}
    if not rows.r:
        return nb
    R = np.asarray(rows.r, dtype=np.int64)
    C = np.asarray(rows.c, dtype=np.int64)
    V = np.abs(np.asarray(rows.v, dtype=float))
    cut = np.flatnonzero(np.diff(R)) + 1          # ``r`` is appended in order
    for rr, cc, vv in zip(np.split(R, cut), np.split(C, cut), np.split(V, cut)):
        own = rows.owner[int(rr[0])]
        if not own or own[0] != "bend" or cc.size < 2:
            continue
        ctr = int(cc[int(np.argmax(vv))])
        for u in cc.tolist():
            if u != ctr:
                nb.setdefault(ctr, set()).add(u)
                nb.setdefault(u, set()).add(ctr)
    return nb


def membrane_rows(planar: PlanarMap, law: Law, rows: _Rows,
                  body: _Rows | None, red: _Reduction,
                  named: _t.AbstractSet[int], weight: float,
                  airside_stage: bool = False) -> int:
    """§61 (1) THE MEMBRANE.  Every column that no row levels
    (:func:`rows._level_row_columns`) and that ``named`` (the cross-section
    rows) does not hold takes one first-difference row ``z_c − z_u = 0`` to
    each bending neighbour ``u``; a pair of two such columns is written
    once.  A vertex ON a taxi centreline is never in the class.  Returns
    the rows added.

    WHICH COLUMNS.  In the AIRSIDE STAGE (``airside_stage``: §20b stage 1,
    whose every column is airside pavement or its strip) it is EVERY such
    column — the reading every §61 number was probed under.  MEASURED at
    HECA (lane ``valley2``, one capture, the gap-free base, 30 satisfied
    ceilings): read for the taxi family alone, pass 1b moved 65 vertices,
    4 over 0.3 m, worst 0.39 m; read for every column, 4 / 0 / 0.26 — the
    115 rows between are an apron piece no datum levels.  Anywhere else
    (the single solve, stage 2) only a TAXI-FAMILY column takes it: the
    groundside is not this law's."""
    if weight <= 0.0 or red.n_cols == 0:
        return 0
    taxi = frozenset(law.tables.precedence.taxi_family.members)
    lev = _level_row_columns(rows, body, red.n_cols)
    if named:
        lev[sorted(named)] = True
    # A CENTRELINE VERTEX IS NOT IN THE CLASS (§61 (1): the membrane is for
    # the OFF-centreline leftovers).  A chain vertex with no trend row keeps
    # what it had — its ``taxi_profile`` curvature and the sheet — and still
    # stands as the NEIGHBOUR an edge beside it is levelled with.
    for bl in planar.breaklines.values():
        if bl.kind == TAXI_CENTERLINE:
            for v in bl.vertices(planar):
                if red.col[v] >= 0:
                    lev[int(red.col[v])] = True
    rep_v: dict[int, int] = {}
    free = np.zeros(red.n_cols, dtype=bool)
    for v in range(len(planar.vertices)):    # ids are dense: lowest id speaks
        vx = planar.vertices[v]
        col = int(red.col[v])
        if col < 0:
            continue
        rep_v.setdefault(col, v)
        if not lev[col] and (airside_stage or any(
                planar.faces[f].role in taxi for f in vx.incident_faces)):
            free[col] = True
    if not free.any():
        return 0
    nb = _bend_neighbours(rows)
    added = 0
    for c in np.flatnonzero(free).tolist():
        for u in sorted(nb.get(c, ())):
            if free[u] and u < c:
                continue                     # written from ``u``'s side
            added += bool(rows.add(((rep_v[c], 1.0), (rep_v[u], -1.0)), 0.0,
                                   weight, ("free_membrane", rep_v[c])))
    return added
