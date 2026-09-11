"""THE APRON BODY'S TARGET SURFACE — the ground's 2-D long-wave trend at
every vertex of a body larger than the fit window (owner RULINGS
2026-09-10ar; spec §8.7).

§8.6 (2) gave every APRON BODY three affine rows: its mean and its two
first moments against the same moments of the production DEM under it, so
the body's least-squares PLANE follows the ground's — level AND tilt.
10ar measured what that still leaves open.  LEMD's T4S apron is a single
439 x 1,242 m body; its plane was satisfied while the body's pit CORNER
sat 1.2 m under its own DEM, and the sheet fell 0.79 m over the last
23.8 m into the basin rim.  A plane has no LOCAL REACH: it is the chain's
"right mean, no tilt" defect (10t) one order up — the right tilt, no
curvature.

THE RULE (10ar).  An apron body targets the ground's 2-D LONG-WAVE TREND
at EVERY vertex: a moving quadratic SURFACE fit of the production DEM,
tricube-weighted over radius ``[design] runway_profile_window_m``
(``constraints/surface_trend.py``, the 2-D sibling of ``trend.py``),
priced at the weak ``[design] apron_trend``.  For a body whose plan
DIAMETER exceeds the window this REPLACES its three affine rows; a body
at or under the window keeps them, because inside one window the trend
IS its plane to the fit's own precision and three rows are cheaper than N.

THE GROUND ENTERS PAVEMENT ONLY THROUGH LONG-WAVE TRENDS (08t (1)): the
window is longer than any DEM artefact the owner has read as "unrealistic
undulation", and the fit's degree is bounded by what its in-window samples
resolve — the same statement §21.2 (5) makes for the runway and §8.6 for
the taxi chain.

WHAT TAKES NO ROW HERE.  A vertex the apron shares with the RUNWAY family
(the runway owns its value, its contact is hard and flush) and a vertex
already carrying a ``taxi_trend`` row: two authorities on one vertex is
the ``emit consensus mints violations`` class.  A ``pad_level`` vertex is
dropped at the ROW SITE (``solve/design.py``), where the pad register is
known, exactly as it is dropped from the plane rows (10l).

THE BODIES ARE THE DATUM'S BODIES.  Connected faces of ``apron_roles``
sharing a vertex — the same construction ``solve/rows._role_bodies_faced``
makes, from the same law reader (``law.tables.apron_roles``, moved down a
layer so both packages read one derivation site).  The solve's own
partition additionally drops fixed columns, DEM-less vertices and foreign
shape members, so a solve body is a SUBSET of exactly one body here:
``design.py`` therefore drops the plane rows of any body a published
target touches, and ONE gate decides both.
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import time as _time
import typing as _t

import numpy as np

from .runway_chord import dem_degraded
from .surface_trend import cell_samples, surface_trend_of
from ..law import Law
from ..law.tables import apron_roles
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["ApronTrendReport", "apron_trend_targets", "with_apron_trend",
           "apron_trend_block"]


class ApronTrendReport(_t.TypedDict, total=False):
    """What the apron trend fit covered."""

    bodies: int                # apron bodies given a 2-D trend target
    bodies_plane: int          # bodies at or under the window (affine rows kept)
    vertices: int              # vertices carrying a trend target
    skipped_runway: int        # apron vertices the runway family owns
    skipped_taxi: int          # vertices already carrying a taxi trend row
    window_m: float
    max_diameter_m: float
    samples: int               # DEM cells the fits were made over
    fit_wall_s: float          # the fit's own wall clock
    max_above_dem_m: float     # the largest target − DEM (the fill it asks)
    max_below_dem_m: float     # the largest DEM − target (the cut)
    fallback: str              # why nothing was fitted, where nothing was
    by_body: list              # [{"ll", "vertices", "diameter_m", ...}]


def _apron_bodies(pm: PlanarMap, law: Law) -> list[list[int]]:
    """The connected BODIES of the apron-role faces (faces sharing a
    vertex), each as its vertices carrying a DEM sample — the same
    construction the per-body datum uses (module docstring)."""
    roles = apron_roles(law)
    parent: dict[int, int] = {}

    def find(v: int) -> int:
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    members: list[list[int]] = []
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        vs = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
        if not vs:
            continue
        r0 = find(vs[0])
        for v in vs[1:]:
            parent[find(v)] = r0
        members.append(vs)
    acc: dict[int, set[int]] = {}
    for vs in members:
        for v in vs:
            acc.setdefault(find(v), set()).add(v)
    out = []
    for group in acc.values():
        keep = sorted(v for v in group if pm.vertices[v].dem_z is not None)
        if keep:
            out.append(keep)
    return out


def _diameter_m(xy: np.ndarray) -> float:
    """The body's plan DIAMETER — the largest distance between two of its
    vertices.  Taken over the CONVEX HULL where scipy can build one (the
    diameter is always a hull pair), else over the vertices themselves; a
    body of thousands of vertices then costs a hull, not N squared."""
    if xy.shape[0] < 2:
        return 0.0
    pts = xy
    if xy.shape[0] > 3:
        try:
            from scipy.spatial import ConvexHull
            pts = xy[ConvexHull(xy).vertices]
        except Exception:                     # degenerate (collinear) input
            pts = xy
    if pts.shape[0] > 4096:                   # never quadratic in N
        pts = pts[:: 1 + pts.shape[0] // 4096]
    d = pts[:, None, :] - pts[None, :, :]
    return float(np.sqrt(np.einsum("ijk,ijk->ij", d, d)).max())


def _dem_many(airport: Airport, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """The production DEM at many points — its vectorised reader where it
    has one (``airport/dem_production.ProductionDem.z_many``), else point
    by point.  The same shape ``planar/build._sample`` uses."""
    dem = airport.dem
    many = getattr(dem, "z_many", None)
    if callable(many):
        return np.asarray(many(xs, ys), dtype=float)
    return np.array([dem.z(float(a), float(b)) for a, b in zip(xs, ys)], float)


def apron_trend_targets(pm: PlanarMap, law: Law, airport: Airport,
                        report: ApronTrendReport | None = None
                        ) -> dict[int, float]:
    """Vertex id -> the ground's 2-D trend under it, for every apron body
    whose plan diameter exceeds the fit window (module docstring)."""
    window = float(law.tables.emit.design.runway_profile_window_m)
    degraded = dem_degraded(airport)
    bodies = _apron_bodies(pm, law)
    if report is not None:
        report.update(window_m=window, bodies=0, bodies_plane=0, vertices=0,
                      skipped_runway=0, skipped_taxi=0, max_diameter_m=0.0,
                      samples=0, fit_wall_s=0.0, max_above_dem_m=0.0,
                      max_below_dem_m=0.0, by_body=[])
    if degraded:
        if report is not None:
            report["fallback"] = degraded
            report["bodies_plane"] = len(bodies)
        return {}
    rwy = frozenset(law.tables.precedence.runway_family.members)
    taxi_held = set(pm.taxi_trend_z)
    t0 = _time.perf_counter()
    out: dict[int, float] = {}
    n_big = n_small = n_rwy = n_taxi = n_samples = 0
    worst_d = above = below = 0.0
    by_body: list[dict[str, _t.Any]] = []
    for vs in bodies:
        xy = np.asarray([pm.vertices[v].xy for v in vs], dtype=float)
        diam = _diameter_m(xy)
        worst_d = max(worst_d, diam)
        if diam <= window:
            # inside one window the trend IS the plane: the three affine
            # rows stand, unchanged (spec §8.7 (2))
            n_small += 1
            continue
        z = np.asarray([float(pm.vertices[v].dem_z) for v in vs], dtype=float)
        # THE CELL'S VALUE IS THE DEM AVERAGED OVER IT, never one sample:
        # an apron's vertices sit on a lattice its own edges make, and one
        # sample per cell ALIASES ground noise into the trend (measured,
        # ``surface_trend``'s docstring).  Where the frame cannot be
        # re-read the body's own vertex samples stand — never an invented
        # value (plan §2).
        try:
            cells = cell_samples(xy, window, lambda a, b: _dem_many(airport, a, b))
        except Exception:
            cells = list(zip(xy[:, 0], xy[:, 1], z))
        tr = surface_trend_of(cells or zip(xy[:, 0], xy[:, 1], z), window)
        if tr is None:
            n_small += 1
            continue
        n_samples += tr.samples
        vals = tr.at(xy[:, 0], xy[:, 1])
        n = 0
        for v, t, dem in zip(vs, vals, z):
            if not _math.isfinite(float(t)):
                continue
            # THE RUNWAY OWNS ITS OWN VERTICES, and a vertex already held by
            # the taxi chain's trend takes no second authority
            if any(r in rwy for r in pm.roles_at(v)):
                n_rwy += 1
                continue
            if v in taxi_held:
                n_taxi += 1
                continue
            out[v] = float(t)
            n += 1
            above = max(above, float(t) - float(dem))
            below = max(below, float(dem) - float(t))
        if n:
            n_big += 1
            by_body.append({"ll": [pm.vertices[vs[0]].key[0],
                                   pm.vertices[vs[0]].key[1]],
                            "vertices": n, "diameter_m": round(diam, 1),
                            "samples": tr.samples})
        else:
            n_small += 1
    if report is not None:
        report.update(bodies=n_big, bodies_plane=n_small, vertices=len(out),
                      skipped_runway=n_rwy, skipped_taxi=n_taxi,
                      max_diameter_m=round(worst_d, 1), samples=n_samples,
                      fit_wall_s=round(_time.perf_counter() - t0, 3),
                      max_above_dem_m=round(above, 3),
                      max_below_dem_m=round(below, 3),
                      by_body=sorted(by_body,
                                     key=lambda r: -r["diameter_m"])[:12])
    return out


def with_apron_trend(pm: PlanarMap, law: Law, airport: Airport,
                     report: ApronTrendReport | None = None) -> PlanarMap:
    """``pm`` with the apron bodies' target surfaces published in
    ``apron_trend_z`` (its own channel — see the module docstring)."""
    targets = apron_trend_targets(pm, law, airport, report)
    if not targets:
        return pm
    return _dc.replace(pm, apron_trend_z=dict(targets))


def apron_trend_block(pm: PlanarMap, law: Law,
                      z: _t.Sequence[float]) -> dict[str, _t.Any]:
    """THE REPORT the round owes (spec §8.7): per apron body carrying a 2-D
    trend, the BUILT surface against the published target (RMS and max) and
    the body's own mean z − DEM.  Read after the solve and the projection,
    from the SAME channel the rows were priced from, so the number is the
    residual of the row that exists."""
    at = pm.apron_trend_z
    if not at:
        return {}
    rows: list[dict[str, _t.Any]] = []
    worst = 0.0
    for vs in _apron_bodies(pm, law):
        d2 = []
        dem2 = []
        for v in vs:
            t = at.get(v)
            if t is None:
                continue
            d2.append(float(z[v]) - float(t))
            dem = pm.vertices[v].dem_z
            if dem is not None:
                dem2.append(float(z[v]) - float(dem))
        if not d2:
            continue
        rms = _math.sqrt(sum(x * x for x in d2) / len(d2))
        mx = max(abs(x) for x in d2)
        worst = max(worst, mx)
        xy = np.asarray([pm.vertices[v].xy for v in vs], dtype=float)
        rows.append({"ll": [pm.vertices[vs[0]].key[0], pm.vertices[vs[0]].key[1]],
                     "diameter_m": round(_diameter_m(xy), 1),
                     "vertices": len(d2),
                     "rms_m": round(rms, 3), "max_m": round(mx, 3),
                     "mean_off_dem_m": round(sum(dem2) / len(dem2), 3)
                     if dem2 else None})
    rows.sort(key=lambda r: -r["max_m"])
    n = max(1, sum(r["vertices"] for r in rows))
    return {"bodies": len(rows), "vertices": len(at),
            "worst_residual_m": round(worst, 3),
            "rms_m": round(_math.sqrt(sum(r["rms_m"] ** 2 * r["vertices"]
                                          for r in rows) / n), 3),
            "by_body": rows[:12]}
