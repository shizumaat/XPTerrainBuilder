"""THE WALL-CORRIDOR PROBES — the mouth ROADS (RULINGS 2026-09-10z) and
the round-4 discriminators (RULINGS 2026-09-10ab: the mouth road's LEVEL
against the corridor's floor; a FLOOR SLAB between the walls).  All three
are MEASUREMENTS: the ``--stage structures`` replay reads them, nothing
in law does (spec §12c refuted both round-4 clauses).  Split out of
``wall_corridors`` under the 1,000-line law.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from . import obj8 as _obj8
from .wall_geometry import (_MIN_SEG_M, _MITRE, _plan_polys, _rect_axis, _seat_base,
                            _tri_normals_y)

# ── the groundside mouth (RULINGS 2026-09-10z (b'')) ──────────────

#: The classification roles whose faces ARE patch road ribbons for the
#: mouth test: the road cross-section family and the groundside pavement
#: a kerb road runs over (``classify/roles.py``).
ROAD_ROLES = ("service_road", "service_junction", "groundside_pavement")
#: The OSM feeds a ``highway=*`` way is read from (``airport/osm.FEEDS``).
ROAD_FEEDS = ("airport_small_roads", "big_roads")


@_dc.dataclass(frozen=True)
class MouthRoad:
    """One road the mouth test reads: its plan geometry (an OSM way's
    line, a patch ribbon's face), the line whose bearing states its
    DIRECTION there, and the witness the refusal or admission names.
    ``centre`` is the centreline the LEVEL reader clamps (the way itself;
    a ribbon's own axis) and ``levelled`` says whether the core would
    level it (an asserted ``bridge`` / ``tunnel`` way it would not:
    RULINGS 2026-09-10ab reads the DEM there)."""

    geom: _t.Any
    axis: LineString
    witness: str
    centre: tuple[XY, ...] = ()
    levelled: bool = True


def mouth_roads(airport: Airport, classification: _t.Any = None) -> list[MouthRoad]:
    """Every road a Law C mouth may be entered by: the tile's OSM
    ``highway=*`` ways (the small-roads / big-roads feeds) and, when the
    classification is at hand, the patch's own road ribbons
    (:data:`ROAD_ROLES`).  Frame coordinates throughout."""
    out: list[MouthRoad] = []
    for w in airport.osm_ways:
        if w.kind not in ROAD_FEEDS or not w.tags.get("highway"):
            continue
        if len(w.points) < 2:
            continue
        ln = LineString(w.points)
        if ln.length < _MIN_SEG_M:
            continue
        levelled = all(not w.tags.get(k) or w.tags.get(k) == "no"
                       for k in ("bridge", "tunnel"))
        out.append(MouthRoad(ln, ln, f"osm way {w.id} ({w.tags.get('highway')})",
                             tuple((float(x), float(y)) for x, y in w.points), levelled))
    for c in getattr(classification, "cells", ()) or ():
        if c.role not in ROAD_ROLES or len(c.ring) < 3:
            continue
        poly = Polygon(c.ring, c.holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        ra = _rect_axis(poly)
        if ra is None:
            continue
        out.append(MouthRoad(poly, ra[0], f"patch {c.role} cell {c.id} ({c.ref})",
                             tuple((float(x), float(y)) for x, y in ra[0].coords), True))
    return out


# ── the round-4 discriminators (RULINGS 2026-09-10ab) ────────────────────

@_dc.dataclass(frozen=True)
class FloorRoad:
    """(i) FLOOR-vs-ROAD for one candidate: the nearest road within
    ``corridor_road_level_m`` of a MOUTH, its LEVEL at the point nearest
    that mouth (the core's own clamp on its centreline — a levelled road
    profile; the DEM where the core levels nothing) and the level minus
    the corridor's floor at that mouth."""

    distance_m: float
    level_z: float
    floor_z: float
    source: str
    witness: str
    mouth_k: int

    @property
    def delta_m(self) -> float:
        return self.level_z - self.floor_z


class _RoadLevels:
    """The LEVEL of a mouth road at a point: Ortho4XP's own longitudinal
    clamp (``airport/road_profile.clamp_way`` — the mid-envelope every
    v2 road-family vertex is fitted to) over the road's centreline, on
    the production DEM, clamped ways cached per road.  A road the core
    does not level (an asserted ``bridge`` / ``tunnel`` way) and a
    centreline the clamp cannot state (outside the warm tiles) fall back
    to the DEM at the point, which the source names."""

    def __init__(self, airport: Airport, law: Law) -> None:
        from ..law.tables import role_cap
        from . import road_profile as _rp
        self._rp = _rp
        self._sample = _rp._sample_fn(airport)
        self._inside = _rp._inside_fn(airport)
        rp = law.tables.emit.road_profile
        self._cap = float(role_cap(law, "service_road").longitudinal)
        self._station = float(rp.station_m)
        self._dem_z = airport.dem.z
        self._ways: dict[int, list] = {}

    def _centre(self, road: MouthRoad) -> list[XY]:
        if getattr(road.geom, "geom_type", "") == "Polygon":
            ring = list(road.geom.exterior.coords)[:-1]
            ax = self._rp.face_axis(ring, self._station / 2.0)
            if ax and len(ax) >= 2:
                return list(ax)
        return list(road.centre)

    def level(self, idx: int, road: MouthRoad, pt: XY) -> tuple[float, str]:
        z_dem = float(self._dem_z(pt[0], pt[1]))
        kind = "ribbon" if getattr(road.geom, "geom_type", "") == "Polygon" else "osm way"
        if not road.levelled:
            return z_dem, f"DEM at an unlevelled {kind}"
        if idx not in self._ways:
            pts = self._centre(road)
            self._ways[idx] = (self._rp.clamp_way("probe", str(idx), pts, self._sample,
                                                  self._cap, self._station, self._inside)
                               if len(pts) >= 2 else [])
        ways = self._ways[idx]
        if not ways:
            return z_dem, f"DEM ({kind}: the clamp states no profile there)"
        P = Point(pt)
        w = min(ways, key=lambda w_: w_.line.distance(P))
        return float(w.at(w.line.project(P))), f"levelled {kind} profile"


def _floor_road(mouths: _t.Sequence[tuple[int, XY, float]], roads: _t.Sequence[MouthRoad],
                tree: STRtree | None, max_m: float, levels: _RoadLevels) -> FloorRoad | None:
    """(i): over every MOUTH, the nearest road within ``max_m`` and its
    level there against that mouth's floor (``None`` = no road at all)."""
    if tree is None or not roads:
        return None
    best: tuple[float, int, XY, float, int] | None = None
    for k, pt, floor_z in mouths:
        P = Point(pt)
        for i in tree.query(P.buffer(max_m), predicate="intersects").tolist():
            d = float(roads[int(i)].geom.distance(P))
            if d > max_m:
                continue
            if best is None or d < best[0]:
                best = (d, int(i), pt, floor_z, k)
    if best is None:
        return None
    d, i, pt, floor_z, k = best
    r = roads[i]
    z, src = levels.level(i, r, pt)
    return FloorRoad(d, z, floor_z, src, r.witness, k)


def _floor_slab(members: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                trench: Polygon, axis_ln: LineString, orig_s: _t.Sequence[float],
                floors: _t.Sequence[float], max_thick: float, tol: float,
                normal_min: float, dem_z) -> tuple[float, str]:
    """(ii) FLOOR SLAB: the share of the corridor's length spanned by a
    HORIZONTAL PLATE of the family (a component thinner than
    ``max_thick``) lying within ``tol`` of the floor inside the trench —
    the fraction and the witness plate (``(0.0, "")`` = no slab)."""
    L = axis_ln.length
    if L <= 0.0 or trench.is_empty:
        return 0.0, ""
    minx, miny, maxx, maxy = trench.bounds
    s_arr = np.asarray(orig_s, dtype=float)
    f_arr = np.asarray(floors, dtype=float)
    ivals: list[tuple[float, float]] = []
    best_area = 0.0
    witness = ""
    for o in members:
        g = cache.geometry(o.resolved)
        if g is None:
            continue
        mat = _obj8.placement_affine(o.xy, o.heading_deg)
        v = g.vertices
        bounds = cache.component_bounds(o.resolved)
        comps = cache.components(o.resolved)
        for ci, comp in enumerate(comps):
            if ci >= bounds.shape[0]:
                break
            if comp.max_y - comp.min_y > max_thick:
                continue                     # a wall, a shell: not a slab
            x0, x1, z0, z1 = bounds[ci].tolist()
            corners = [_obj8._to_frame(o.xy, o.heading_deg, x, z)
                       for x in (x0, x1) for z in (z0, z1)]
            base = _seat_base(o, ((corners[0][0] + corners[3][0]) / 2.0,
                                  (corners[0][1] + corners[3][1]) / 2.0), dem_z)
            if max(c[0] for c in corners) < minx or min(c[0] for c in corners) > maxx \
                    or max(c[1] for c in corners) < miny or min(c[1] for c in corners) > maxy:
                continue
            ny = _tri_normals_y(v, comp.tris)
            horiz = ny >= normal_min
            if not horiz.any():
                continue
            t = comp.tris[horiz]
            a, b, d, e, xoff, yoff = mat
            pts = v[t][:, :, [0, 2]]
            xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
            ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
            zs = base + v[t][:, :, 1].mean(axis=1)
            polys = shapely.polygons(np.stack([xs, ys], axis=2))
            hit = shapely.intersects(polys, trench) & shapely.is_valid(polys)
            area = 0.0
            for kk in np.nonzero(hit)[0].tolist():
                inter = polys[kk].intersection(trench)
                if inter.is_empty:
                    continue
                ss = [axis_ln.project(Point(p)) for p in inter.envelope.exterior.coords] \
                    if inter.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection") else []
                if not ss:
                    continue
                lo, hi = max(0.0, min(ss)), min(L, max(ss))
                if hi <= lo:
                    continue
                fl = float(np.interp((lo + hi) / 2.0, s_arr, f_arr))
                if abs(float(zs[kk]) - fl) > tol:
                    continue
                ivals.append((lo, hi))
                area += float(inter.area)
            if area > best_area:
                best_area = area
                witness = f"plate comp {ci} of {os.path.basename(o.path)} ({o.id})"
    if not ivals:
        return 0.0, ""
    ivals.sort()
    covered = 0.0
    cur: tuple[float, float] | None = None
    for lo, hi in ivals:
        if cur is None or lo > cur[1]:
            if cur is not None:
                covered += cur[1] - cur[0]
            cur = (lo, hi)
        else:
            cur = (cur[0], max(cur[1], hi))
    if cur is not None:
        covered += cur[1] - cur[0]
    return covered / L, witness
