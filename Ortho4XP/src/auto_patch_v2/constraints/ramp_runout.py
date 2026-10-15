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
from ..model.constraints import Band, ConstraintSet, Linear, Source
from ..model.planar import PlanarMap, face_vertex_set
from .pad_ramp import ramp_delta

__all__ = ["RUNOUT_RULING", "runout_rows", "landing_runout_rows", "runout_exempt", "GEN", "STATS"]

GEN = "ramp_runout"

#: a generator's own statistics (``constraints.generate`` publishes them)
STATS: dict[str, dict[str, int]] = {}

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


#: The ruling head of a LANDING run-out's level row (#711).
LANDING_RUNOUT_RULING = ("roads.ramp_runout landing run-out at road grade "
                         "(owner 2026-10-14c (5) at a 10-03e landing; issue #711)")


def _dz_at(profile: _t.Sequence[tuple[float, float]], s: float) -> float:
    """A long section's value at ``s``: linear between its samples, its
    last value beyond."""
    if s <= profile[0][0]:
        return float(profile[0][1])
    for (s0, z0), (s1, z1) in zip(profile, profile[1:]):
        if s <= s1:
            t = 0.0 if s1 <= s0 else (s - s0) / (s1 - s0)
            return float(z0 + t * (z1 - z0))
    return float(profile[-1][1])


def landing_runout_rows(planar: PlanarMap, law: Law, airport=None) -> list:
    """THE LANDING'S RUN-OUT COMES DOWN AT ROAD GRADE (issue #711; owner
    RULINGS 2026-10-14c (5) at a 10-03e landing).  Every vertex of a run-out
    strip (``planar/landing_runout``, ``model.platform.LANDING_RUNOUTS``),
    ``s`` its distance along the direction of travel from the foot's lip,
    takes ONE hard row against its block's DATUM COLUMN ``D`` (the
    landing's own row, ``constraints/platform.landing_rows``, is
    ``z_L - z_D = y``)::

        y + max(-cap * s, min(-g * s, dG(s) - g * s))  <=  z_v - z_D  <=  y

    — never above the landing; never below the design ramp off it (the
    shared ramp law's two profiles, ``geom/ramp_profile.ramp_delta``:
    toward the ground at ``g``, or closing the landing's offset over a
    ground ``dG`` falling away beside it), nor steeper than the road's own
    cap.  Linear in ``D``, so the strip follows the SOLVED landing wherever
    the solve holds its block; the ground objective lays it on its DEM
    once the bound has passed under it.  Like the landing's, a stage-2 row:
    ``D`` is stage 1's constant, nothing airside follows the strip.  A
    vertex of a rigid face other than the landing's own collar (the
    landing platform, another pad) is not the strip's."""
    from ..law.tables import is_rigid_role
    from ..model.platform import LANDING_RUNOUTS, datum_vertices
    from ..model.planar import COLLAR_SUFFIX
    STATS.pop("landing_runout_rows", None)
    if not LANDING_RUNOUTS:
        return []
    held = datum_vertices(planar, law)
    band = float(law.tables.emit.cockpit.visual_m)
    F = planar.faces
    rows: list = []
    seen: set[int] = set()
    n = n_none = 0
    for f in sorted(F.values(), key=lambda q: q.id):
        rec = LANDING_RUNOUTS.get(str(f.ref))
        if rec is None or f.role != "service_road":
            continue
        dv = held.get(rec["block"])
        if dv is None:
            n_none += 1
            continue
        n += 1
        bank = rec["landing"] + COLLAR_SUFFIX
        (x0, y0), (dx, dy) = rec["lip"], rec["dir"]
        g, cap, y = float(rec["g"]), float(rec["cap"]), float(rec["y"])
        z_hi = float(rec["z0_pred"]) + float(rec.get("reach_m", 0.0))
        src = Source(GEN, LANDING_RUNOUT_RULING,
                     (f"face:{f.id}", str(f.ref), f"landing:{rec['landing']}"))
        for v in sorted(face_vertex_set(planar, f)):
            if v in seen or v == dv or any(
                    q in F and is_rigid_role(law, F[q].role) and str(F[q].ref) != bank
                    for q in planar.vertices[v].incident_faces):
                continue
            seen.add(v)
            x, yy = planar.vertices[v].xy
            s = max(0.0, (x - x0) * dx + (yy - y0) * dy)
            prof = max(-cap * s, min(-g * s, _dz_at(rec["ground"], s) - g * s))
            rows.append(Linear(((v, 1.0), (dv, -1.0)), y + prof, y, src))
            # the ceiling: the same profile off the HIGHEST level the solve
            # may hold the landing at, or the vertex's own ground where that
            # profile has met it — so the strip comes down onto its DEM by
            # its end however the solved datum falls inside its reach band
            dem = planar.vertices[v].dem_z
            if dem is not None:
                hi = max(float(dem), z_hi + prof) + band
                rows.append(Band(v, None, hi, src))
    STATS["landing_runout_rows"] = {"runouts": n, "runouts_no_datum": n_none,
                                    "rows": len(rows)}
    return rows


def _row_vs(row) -> tuple[int, ...]:
    """Every vertex a row names (``Pin``/``Band``, ``Diff``/``Offset``,
    ``Linear``, ``Flat``)."""
    if hasattr(row, "v"):
        return (int(row.v),)
    if hasattr(row, "a") and hasattr(row, "b"):
        return (int(row.a), int(row.b))
    if hasattr(row, "terms"):
        return tuple(int(v) for v, _c in row.terms)
    return tuple(int(v) for v in getattr(row, "group", ()))


def runout_exempt(rows: list, planar: PlanarMap) -> tuple[list, int]:
    """A MAPPED ROAD ON A LANDING'S RUN-OUT RIDES IT (#711; RULINGS 14i "the
    road carries the run-out", option 3 "where a mapped road dead-ends at
    the landing the run-out starts there"): the §37 ramp rows
    (``constraints/road_ramp``: the target and the ceiling off the road's
    DEM-based profile) of every vertex the strip holds are withdrawn — the
    run-out's own rows (:func:`landing_runout_rows`) are that vertex's
    road-grade profile.  MEASURED (HECA, ``small_roads:-3964`` / ``-19455``
    inside ``runout:building4/landing3``): 8 ramp-ceiling rows relaxed by
    6.4-12.5 m against the strip.  ``(rows, withdrawn)``."""
    from ..model.platform import LANDING_RUNOUTS
    from .road_ramp import GEN as _ROAD_RAMP
    if not LANDING_RUNOUTS:
        return rows, 0
    held = {v for f in planar.faces.values() if str(f.ref) in LANDING_RUNOUTS
            for v in face_vertex_set(planar, f)}
    if not held:
        return rows, 0
    out = [r for r in rows if not (r.source.generator == _ROAD_RAMP
                                   and all(v in held for v in _row_vs(r)))]
    return out, len(rows) - len(out)
