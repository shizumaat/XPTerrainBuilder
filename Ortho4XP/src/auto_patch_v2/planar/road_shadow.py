"""THE BAND HOLDS ITS GRADE BESIDE A ROAD THROUGH ZONE 2 — the DEM shadow
(owner RULINGS 2026-10-19ad, 2026-10-20c (39); issue #951).

A road cut out of a band's zone 2 (``planar/road_yield.BandYield``) follows
its own ground, and the DEM under and beside it carries the road's own cut:
the band's vertices at the cut's edge read the road's slope, and the band
graded over them sags into the road.  The band reads the ground the road did
not dig instead: a runway or taxi band vertex within ``probe`` of a yield's
axis takes the DEM at the point ``probe`` from the axis on its own side,
where

    probe = the road's half-width + the stand-off (``groundside_cutback_m``
            + ``snap_margin_m``) + ``adjacent_ground.road_shadow_dem_cells``
            DEM postings (the DEM's own ``posting_m``; none: no posting).

A probe point inside another yield's reach keeps the vertex's own DEM (two
roads side by side: there is no undug ground between them to read).  It is
a SUBSTITUTION, never a lift: the value written is the DEM there, above or
below.  Precedent: ``planar/covered_ground`` (#714) writes a substituted
ground into ``Vertex.dem_z`` at the same site of ``planar/build``.  The
caller hands in the band vertices off every road face: a welded kerb vertex
(zone 1) is the road's and keeps its own DEM."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..law import Law
from ..law.tables import snap_margin_m

__all__ = ["RoadShadow", "road_shadow"]


@_dc.dataclass
class RoadShadow:
    """What the shadow did (the build's report line)."""

    yields: int = 0
    vertices: int = 0
    max_shift_m: float = 0.0

    def line(self) -> str:
        return (f"road shadow (19ad, #951): {self.vertices} band vertices beside "
                f"{self.yields} zone-2 road cuts read the DEM past the cut "
                f"(max |shift| {self.max_shift_m:.2f} m)")


def road_shadow(dem, law: Law, yields: _t.Sequence, band_vertices: _t.Iterable[int],
                xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
                ) -> tuple[np.ndarray, RoadShadow]:
    """``zs`` with every vertex of ``band_vertices`` within a yield's probe
    substituted by the DEM at the probe (module docstring)."""
    rep = RoadShadow(yields=len(yields))
    band_vertices = sorted(band_vertices)
    if dem is None or not yields or not band_vertices:
        return zs, rep
    probe = _probes(dem, law, yields)
    picks = _probe_points(yields, probe, band_vertices, xs, ys)
    out = zs.copy()
    if not picks:
        return out, rep
    qz = _sample(dem, np.array([q[1] for q in picks]), np.array([q[2] for q in picks]))
    for (v, _x, _y), z in zip(picks, qz, strict=True):
        if not np.isfinite(z):
            continue
        rep.max_shift_m = max(rep.max_shift_m, abs(float(z) - float(out[v])))
        out[v] = float(z)
        rep.vertices += 1
    return out, rep


def _probes(dem, law: Law, yields) -> list[float]:
    """Each yield's probe distance from its axis (module docstring)."""
    ag = law.tables.zones.adjacent_ground
    cut = float(ag.groundside_cutback_m) + snap_margin_m(law)
    post = getattr(dem, "posting_m", None)
    cell = (post() if callable(post) else None) or 0.0
    return [float(y.half) + cut + float(ag.road_shadow_dem_cells) * float(cell)
            for y in yields]


def _probe_points(yields, probe, band_vertices, xs, ys
                  ) -> list[tuple[int, float, float]]:
    """``(vertex, x, y)`` of the probe point of every band vertex within a
    yield's probe — the nearest yield's, on the vertex's own side — unless
    that point lies within another yield's probe."""
    from shapely import Point
    from shapely.strtree import STRtree
    axes = [y.axis for y in yields]
    tree = STRtree(axes)
    reach = max(probe)
    picks: list[tuple[int, float, float]] = []
    for v in band_vertices:
        p = Point(float(xs[v]), float(ys[v]))
        best = None
        for k in tree.query(p, predicate="dwithin", distance=reach):
            k = int(k)
            d = axes[k].distance(p)
            if 1e-6 < d < probe[k] and (best is None or d < best[1]):
                best = (k, d)
        if best is None:
            continue
        k, d = best
        foot = axes[k].interpolate(axes[k].project(p))
        qx = foot.x + (p.x - foot.x) / d * probe[k]
        qy = foot.y + (p.y - foot.y) / d * probe[k]
        q = Point(qx, qy)
        if any(int(j) != k and axes[int(j)].distance(q) < probe[int(j)]
               for j in tree.query(q, predicate="dwithin", distance=reach)):
            continue
        picks.append((v, qx, qy))
    return picks


def _sample(dem, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    many = getattr(dem, "z_many", None)
    if callable(many):
        return np.asarray(many(xs, ys), dtype=float)
    return np.array([dem.z(float(x), float(y)) for x, y in zip(xs, ys, strict=True)])
