"""A PROJECTED VERTEX IS NOT AN UNKNOWN OF THE SOLVE (spec
``2068-fence-grade-spec-A3.md`` R3; makes A2's G7 "the yard is a late
cell, projected after the solve, never a row" true).

A fence yard (``classify/fence_yard``) stands on the fence-foot plane: its
vertices take their height AFTER the whole solve (``solve/project_yard``),
so no row may price them against the airport.  A PROJECTED vertex is a
vertex of a ``fenceyard:`` face that no other face carries, and a FREE
vertex of a yard's road run (R5, ``model/yard_run.yard_runs``).  At the one
site every generator's rows pass (``constraints.assembly``, beside the
riser's exemption and before the 5 % ceiling and the pavement fallback)
this withdraws

* (i) every row naming a projected vertex and any other vertex — the
  apron-to-groundside ramp across the yard's stand-off and its ceiling
  twin (MEASURED LPPI replay: row 102123, yard v2120 36.67 vs apron v604
  33.50 over 1.80 m, the 66th hard row);
* (ii) every ``road_ramp`` row naming a projected vertex (the
  ``ramp_runout.runout_exempt`` precedent).

A single-vertex row of any other family stays.  The pavement fallback
(``constraints/pavement_cap``) skips a pair holding a projected vertex
through :func:`projected_vertices`.  The yard's edge stays a declared
joint for the census (``pipeline/upper_pad_publication``).

THE YARD'S ROAD RUN (R5) and its lot grade are read in the model
(``model/yard_run``: :func:`~auto_patch_v2.model.yard_run.yard_runs`,
``run_grade``), which the solve's projection reads too."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import Row, row_vertices
from ..model.planar import PlanarMap, face_vertex_set, fence_yard_pad
from ..model.yard_run import yard_runs

__all__ = ["projected_vertices", "yard_exempt"]


def projected_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """The vertices of the fence yards no other face carries, and the free
    vertices of their road runs (module doc); empty with no yard."""
    own: set[int] = set()
    other: set[int] = set()
    for f in planar.faces.values():
        (own if fence_yard_pad(f.ref) is not None else other).update(
            face_vertex_set(planar, f))
    if not own:
        return frozenset()
    run = {v for r in yard_runs(planar, law) for v in r.free}
    return frozenset((own - other) | run)


def yard_exempt(rows: list[Row], planar: PlanarMap, law: Law,
                counts: dict[str, _t.Any]) -> list[Row]:
    """``rows`` less every row R3 withdraws (module doc); the count goes
    into ``counts['yard_rows_withdrawn']`` where a yard stands (none is
    written without one, as ``riser.riser_exempt``)."""
    from .road_ramp import GEN as _ROAD_RAMP
    held = projected_vertices(planar, law)
    if not held:
        return rows
    out: list[Row] = []
    for r in rows:
        vs = set(row_vertices(r))
        if vs & held and (len(vs) > 1 or r.source.generator == _ROAD_RAMP):
            continue
        out.append(r)
    counts["yard_rows_withdrawn"] = len(rows) - len(out)
    return out
