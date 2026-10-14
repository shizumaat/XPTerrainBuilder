"""THE RUN-OUT'S PROFILE ROWS (issue #669; owner RULINGS 2026-10-14c (5)):
the strip ``classify/ramp_runout`` mints off an object ramp's graded foot is
graded at road grade from the ground's level there to the raw DEM.

Solved in the PAD ROADS' stage (``pipeline/late_stage``, ``roads_only``),
where everything the strip meets is a constant.  On every free vertex of a
run-out face ONE design row, ``s`` its distance along the direction of
travel from where the strip leaves the patch, ``z0`` the level there:

    z[v] = z0 + ramp_delta(dem[v], z0, dem0, g, s)

— the ramp ``constraints/pad_ramp`` lays off a pad's rim, here off the
patch's edge at the foot (``dem0`` the ground there): at the design grade
``[road_contact] ramp_grade`` toward the terrain never past it, or closing
the foot's offset over its ground where the ground falls away.  Absolute: the strip's start is a
constant of the stage, so the row can pull nothing standing.  The road's
own caps (the role's hard longitudinal cap, 10 %) stay; where a standing
face stops the strip short, they steepen it."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet, Linear, Source
from ..model.planar import PlanarMap, face_vertex_set
from .pad_ramp import ramp_delta

__all__ = ["RUNOUT_RULING", "runout_rows", "GEN"]

GEN = "ramp_runout"

#: The ruling head of the run-out's profile row.
RUNOUT_RULING = ("roads.ramp_runout ramp foot to raw DEM "
                 "(owner 2026-10-14c (5); issue #669)")


def runout_rows(planar: PlanarMap, law: Law, cs: ConstraintSet,
                levels: _t.Mapping[int, float] | None = None
                ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """``cs`` with the run-out profile rows added (module docstring)."""
    from ..law.tables import is_rigid_role
    runs = getattr(planar, "ramp_runouts", None) or {}
    rep = {"faces": 0, "rows": 0}
    if not runs:
        return cs, rep
    g = float(law.tables.emit.road_contact.ramp_grade)
    levels = levels or {}
    F = planar.faces
    seen: set[int] = set()
    rows = []
    for f in F.values():
        r = runs.get(str(f.ref))
        if r is None or f.role != "service_road":
            continue
        rep["faces"] += 1
        x0, y0, dx, dy, z0, d0 = r
        for v in sorted(face_vertex_set(planar, f)):
            if v in levels or v in seen or any(
                    q in F and is_rigid_role(law, F[q].role)
                    for q in planar.vertices[v].incident_faces):
                continue
            dv = planar.vertices[v].dem_z
            if dv is None:
                continue
            seen.add(v)
            x, y = planar.vertices[v].xy
            s = max(0.0, (x - x0) * dx + (y - y0) * dy)
            t = z0 + ramp_delta(float(dv), z0, d0, g, s)
            rows.append(Linear(((v, 1.0),), t, t,
                               Source(GEN, RUNOUT_RULING, (f"vertex:{v}", str(f.ref)))))
    rep["rows"] = len(rows)
    if not rows:
        return cs, rep
    return _dc.replace(cs, linears=tuple(cs.linears) + tuple(rows)), rep
