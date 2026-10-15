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
from ..model.constraints import Band, ConstraintSet, Diff, Linear, Source
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


def _chord_rows(planar: PlanarMap, sides: _t.Mapping[bool, list], cap: float,
                xcap: float, src) -> list:
    """The strip's own CHORDS: along each side, consecutive vertices by
    station at the road cap; across, a vertex and the other side's vertex
    at its station (within one metre) at the cross-fall cap.  The level
    rows bound the strip against its landing; these bound it between its
    own vertices (MEASURED, HECA: a 19.6 % chord inside the bounds)."""
    import math
    xy = planar.vertices
    rows: list = []

    def d(a: int, b: int) -> float:
        (ax, ay), (bx, by) = xy[a].xy, xy[b].xy
        return math.hypot(ax - bx, ay - by)
    for pts in sides.values():
        pts = sorted(pts)
        rows.extend(Diff(a, b, cap, d(a, b), src) for (_s0, a), (_s1, b) in zip(pts, pts[1:])
                    if d(a, b) > 0.0)
    if xcap > 0.0 and len(sides) == 2:
        other = sorted(sides[False])
        for s0, a in sides[True]:
            near = min(other, key=lambda q: abs(q[0] - s0))
            if abs(near[0] - s0) <= 1.0 and d(a, near[1]) > 0.0:
                rows.append(Diff(a, near[1], xcap, d(a, near[1]), src))
    return rows


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
    the solve holds its block.  ONE ceiling (a ``Band``)::

        z_v  <=  max(dem_axis(s), z_hi + profile(s)) + visual_m

    — the same profile off the HIGHEST level the solve may hold the landing
    at (``z_hi``: the predicted datum + its widest reach band + ``y``,
    ``planar/landing_runout``), or the raw ground on the strip's AXIS at
    that station once that profile has met it: the strip comes down onto
    its DEM by its end (the ground objective alone held HECA's strip end
    1.5 m over it, MEASURED, no row binding).  And the strip's own CHORDS
    (:func:`_chord_rows`).  Like the landing's, a stage-2 row:
    ``D`` is stage 1's constant, nothing airside follows the strip.  A
    vertex of a rigid face other than a bank of its own (the landing's
    collar, the strip's side bank ``<run-out>#collar``) — the landing
    platform, another pad — is not the strip's."""
    from ..law.tables import is_rigid_role
    from ..model.platform import LANDING_RUNOUTS, datum_vertices
    from ..model.planar import COLLAR_SUFFIX
    STATS.pop("landing_runout_rows", None)
    if not LANDING_RUNOUTS:
        return []
    held = datum_vertices(planar, law)
    band = float(law.tables.emit.cockpit.visual_m)
    from ..law.tables import role_cap
    rc = role_cap(law, "service_road")
    xcap = float(rc.transverse) if rc is not None else 0.0
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
        banks = {rec["landing"] + COLLAR_SUFFIX, str(f.ref) + COLLAR_SUFFIX}
        (x0, y0), (dx, dy) = rec["lip"], rec["dir"]
        g, cap, y = float(rec["g"]), float(rec["cap"]), float(rec["y"])
        w = float(rec.get("width_m", 0.0))
        sides: dict[bool, list[tuple[float, int]]] = {}
        z_hi = float(rec["z0_pred"]) + float(rec.get("reach_m", 0.0))
        src = Source(GEN, LANDING_RUNOUT_RULING,
                     (f"face:{f.id}", str(f.ref), f"landing:{rec['landing']}"))
        for v in sorted(face_vertex_set(planar, f)):
            if v in seen or v == dv or any(
                    q in F and is_rigid_role(law, F[q].role) and str(F[q].ref) not in banks
                    for q in planar.vertices[v].incident_faces):
                continue
            seen.add(v)
            x, yy = planar.vertices[v].xy
            s = max(0.0, (x - x0) * dx + (yy - y0) * dy)
            dg = _dz_at(rec["ground"], s)
            prof = max(-cap * s, min(-g * s, dg - g * s))
            rows.append(Linear(((v, 1.0), (dv, -1.0)), y + prof, y, src))
            # the ceiling: the same profile off the HIGHEST level the solve
            # may hold the landing at, or the vertex's own ground where that
            # profile has met it — so the strip comes down onto its DEM by
            # its end however the solved datum falls inside its reach band
            # the ground the ceiling reads is the AXIS's at this station
            # (``ground``), never the vertex's own: the cross-fall cap holds
            # the two sides together and a ceiling off each side's DEM
            # contested it (MEASURED, HECA: 0.26-0.43 m cross rows relaxed)
            dem = rec.get("dem0")
            if dem is not None:
                hi = max(float(dem) + dg, z_hi + prof) + band
                rows.append(Band(v, None, hi, src))
            t = -(x - x0) * dy + (yy - y0) * dx
            if abs(t) >= 0.25 * w:
                sides.setdefault(t > 0.0, []).append((s, v))
        rows.extend(_chord_rows(planar, sides, cap, xcap, src))
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
