"""THE SUNKEN ROADS (RULINGS 2026-09-08b/c LAW B; spec ``docs/specs/
auto-patch-v2/othh-terminal-ramps-spec.md`` §3; law ``structures.toml
[cutout.sunken_road]``): a floor plate below the seat that is ROOFED
(the tunnel-object signature's "roofed along its axis" and the basin
pass's refusal) whose plate reaches within ``basin.contact_band_m`` of
the ground at one end is a sunken road — the terrain is cut to the
plate's OWN y per station, to ``max_depth_m`` at most (deeper is the
underground road, the terrain stays), the deck above untouched.

THE READING is per ANCHOR FAMILY over the geometry the basin pass parsed
(``obj8.ResourceCache``): OTHH's ``TerminalRoads_03_000`` carries the
descending carriageway, ``03_002`` the viaduct deck over it and other
members the deep continuation — one anchor, several resources — so the
class is not a per-resource wall signature (spec §4, the deviation
recorded there).  Per family:

1. FACES — every genuine component's near-horizontal solid faces
   (``basin.floor_plate_normal_y_min``) whose centroid lies at or under
   the local ground, in the frame with their rendered z; components
   buried under the ground (``shell_reaches_grade``) contribute none.
2. PLATES — the faces' union, connected parts of ``min_plate_m2`` or
   more; a part's AXIS is its minimum rotated rectangle's long axis.
3. PROFILE — stations ``station_m`` apart along the axis: the floor z is
   the area-weighted mean of the faces in the dominant depth bin
   (``tunnel.object.plate_bin_m``) across the station's slab, the half
   widths those faces' across-axis extents; the ground is the DEM at
   the axis point.
4. THE LAW — the shallow end within ``contact_band_m`` of the ground
   (else "does not reach grade"), the plate descending ``min_descent_m``
   or more (else a level plate: the basin pass's basement / pit reading
   stands, nothing here); s = 0 at the DEEP end = where the profile
   first reaches ``max_depth_m`` walking down from the grade end (the
   plate's own end when it never does), the TOP where the profile comes
   within ``top_depth_m`` of the ground; the trench between them.

Nothing numeric lives here; every value is a law-table argument.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8
from .deck_signature import family_key
from .tunnel_objects import _rect_axis

__all__ = ["RoadStation", "SunkenRoadRecord", "SunkenRoadStats", "read_sunken_roads",
           "ID_PREFIX"]

ID_PREFIX = "sunken-road"
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass(frozen=True)
class RoadStation:
    """One station of the trench: ``s`` from the deep end, the plate's
    floor ``z`` there, the plate's half widths left / right of the axis
    (direction of travel: deep end → top), the ground."""

    s: float
    z: float
    half_l: float
    half_r: float
    ground_z: float


@_dc.dataclass(frozen=True)
class SunkenRoadRecord:
    """One sunken road in the airport frame: the axis from the deep-end
    cut (s = 0, floor ``floor_z`` = the plate at ``max_depth_m``, or the
    plate's end) to the top (the plate within ``top_depth_m`` of the
    ground); ``stations`` the profile; ``plate`` the whole plate part;
    ``region`` the family's below-ground footprint round it (the walls'
    thickness — the rim's law, 09-08a — is the planar layer's
    measurement, ``planar/door_ramps.py``)."""

    id: str
    resource: str
    objects: tuple[str, ...]
    axis: tuple[XY, ...]
    stations: tuple[RoadStation, ...]
    length_m: float
    width_m: float
    floor_z: float
    mouth_dem_z: float
    top_z: float
    top_ground_z: float
    plate: Polygon
    region: Polygon
    cover: float
    anchor_xy: XY
    anchor_dem_z: float
    agl_m: float
    notes: tuple[str, ...] = ()

    @property
    def depth_m(self) -> float:
        return self.mouth_dem_z - self.floor_z

    @property
    def profile(self) -> tuple[tuple[float, float], ...]:
        return tuple((st.s, st.z) for st in self.stations)


@_dc.dataclass
class SunkenRoadStats:
    placements: int = 0
    families: int = 0
    plates: int = 0
    roads: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    read_s: float = 0.0


def _faces_below(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, dem_z, law: Law,
                 normal_min: float, top_m: float
                 ) -> tuple[list[tuple[Polygon, tuple, float]], list]:
    """Rule 1 for one placement: ``[(face polygon in the frame, its plane
    ``(a, b, c)`` — rendered z = a·E + b·N + c —, plan area)]`` for the road-flat faces (``|n_y| >= normal_min``)
    more than ``top_m`` under the local ground — the at-grade road
    surface is not a trench — and the below-ground footprints of the
    components carrying them."""
    bl = law.tables.structures.basin
    g = cache.geometry(o.resolved)
    if g is None:
        return [], []
    base = o.anchor_z + o.agl_m
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    v = g.vertices
    faces: list[tuple[Polygon, float, float]] = []
    belows = []
    for comp in cache.genuine(o.resolved):
        cx, cy = _obj8._to_frame(o.xy, o.heading_deg, comp.cx, comp.cz)
        local = float(dem_z(cx, cy))
        if math.isnan(local):
            local = o.anchor_z
        if bl.shell_reaches_grade and base + comp.max_y < local - bl.contact_band_m:
            continue
        plane_ground = local - base
        if comp.min_y > plane_ground - top_m:
            continue
        t = comp.tris
        p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        nrm = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(nrm, axis=1)
        ok = ln > 1e-12
        ny = np.zeros(t.shape[0])
        ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
        cyv = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
        sel = (ny >= normal_min) & (cyv <= plane_ground - top_m)
        if not sel.any():
            continue
        # the faces in bulk: authored (x, z) -> the frame by the placement
        # affine, shapely's vectorised constructors (a Python loop per
        # triangle cost 5 s per family on OTHH); each face carries its
        # PLANE (z = a·E + b·N + c in the frame) — a road triangle is 100 m
        # long, its centroid says nothing about the floor at a station
        a, b, d, e, xoff, yoff = mat
        pts = v[t[sel]][:, :, [0, 2]]
        xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
        ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
        hs = base + v[t[sel]][:, :, 1]
        polys = shapely.polygons(np.stack([xs, ys], axis=2))
        areas = shapely.area(polys)
        valid = shapely.is_valid(polys) & (areas > 1e-9)
        # the plane through the three frame points
        m = np.stack([xs, ys, np.ones_like(xs)], axis=2)          # (n, 3, 3)
        try:
            coef = np.linalg.solve(m, hs[:, :, None])[:, :, 0]     # (n, 3): a, b, c
        except np.linalg.LinAlgError:
            coef = np.stack([np.linalg.lstsq(m[i], hs[i], rcond=None)[0] for i in range(m.shape[0])])
        for poly, cf, ar, okp in zip(polys, coef.tolist(), areas.tolist(), valid.tolist()):
            if okp and all(math.isfinite(x) for x in cf):
                faces.append((poly, tuple(cf), ar))
        below = _obj8._clip_component(v, comp, plane_ground, True)
        if below is not None:
            # §51 (4) row 13 — ENTRY
            placed = _fe.enter([below], mat, cache.input_quantum_m)[0]
            if placed is not None:
                belows.append(placed)
    return faces, belows


def _profile(axis: LineString, faces: list[tuple[Polygon, float, float]], tree: STRtree,
             dem_z, step: float, bin_m: float, width: float
             ) -> list[tuple[float, float | None, float, float, float]]:
    """Rule 3: ``[(s, floor z | None, half left, half right, ground)]``
    every ``step`` along ``axis`` (the last station ON the end)."""
    L = axis.length
    ss = [step * k for k in range(int(L // step) + 1)]
    if L - ss[-1] > 1e-6:
        ss.append(L)
    out = []
    reach = width
    for s in ss:
        p = axis.interpolate(s)
        a0, a1 = axis.interpolate(max(0.0, s - 1.0)), axis.interpolate(min(L, s + 1.0))
        ux, uy = a1.x - a0.x, a1.y - a0.y
        n0 = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n0, uy / n0
        nx, ny = -uy, ux
        h = step / 2.0
        slab = Polygon([(p.x + ux * h + nx * reach, p.y + uy * h + ny * reach),
                        (p.x - ux * h + nx * reach, p.y - uy * h + ny * reach),
                        (p.x - ux * h - nx * reach, p.y - uy * h - ny * reach),
                        (p.x + ux * h - nx * reach, p.y + uy * h - ny * reach)])
        ground = float(dem_z(p.x, p.y))
        here = [(faces[int(j)], faces[int(j)][0].intersection(slab))
                for j in tree.query(slab, predicate="intersects")]
        here = [(f, x) for f, x in here if not x.is_empty and x.area > 1e-9]
        if not here:
            out.append((s, None, 0.0, 0.0, ground))
            continue
        # each face's floor AT the station: its plane at the axis point
        here = [((f, cf[0] * p.x + cf[1] * p.y + cf[2], a_), x) for (f, cf, a_), x in here]
        bins: dict[int, float] = {}
        for (f, z, _a), x in here:
            k = int(math.floor(z / bin_m))
            bins[k] = bins.get(k, 0.0) + x.area
        best = max(bins, key=lambda k: bins[k])
        sel = [((f, z, a), x) for (f, z, a), x in here
               if int(math.floor(z / bin_m)) in (best, best - 1, best + 1)]
        # the floor is the road's TOP surface: the highest face of the
        # dominant bin (a slab's underside sits one thickness lower)
        z_mean = max(z for (_f, z, _a), _x in sel)
        hl = hr = 0.0
        for _f, x in sel:
            for g in shapely.get_parts(x):
                for cx, cy in g.exterior.coords:
                    d = (cx - p.x) * nx + (cy - p.y) * ny
                    if d >= 0.0:
                        hl = max(hl, d)
                    else:
                        hr = max(hr, -d)
        out.append((s, float(z_mean), hl, hr, ground))
    return out


def _cross(prof, i: int, j: int, target: float) -> float:
    """The station s between profile rows ``i`` / ``j`` where the depth
    crosses ``target`` (linear)."""
    s0, d0 = prof[i][0], prof[i][4] - prof[i][1]
    s1, d1 = prof[j][0], prof[j][4] - prof[j][1]
    if abs(d1 - d0) < 1e-9:
        return s1
    f = (target - d0) / (d1 - d0)
    return s0 + (s1 - s0) * max(0.0, min(1.0, f))


def _interp(prof, s: float, k: int) -> float:
    """Linear interpolation of column ``k`` at ``s`` over the profile."""
    if s <= prof[0][0]:
        return float(prof[0][k])
    if s >= prof[-1][0]:
        return float(prof[-1][k])
    for a, b in zip(prof[:-1], prof[1:]):
        if a[0] <= s <= b[0]:
            f = (s - a[0]) / max(b[0] - a[0], 1e-9)
            return float(a[k] + (b[k] - a[k]) * f)
    return float(prof[-1][k])


def read_sunken_roads(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                      cache: _obj8.ResourceCache, law: Law
                      ) -> tuple[list[SunkenRoadRecord], SunkenRoadStats]:
    """Every sunken road the pack's object families state (module doc)."""
    t0 = time.perf_counter()
    stats = SunkenRoadStats()
    bl = law.tables.structures.basin
    sr = law.tables.structures.cutout.sunken_road
    tn = law.tables.structures.tunnel
    ob = tn.object
    dem_z = airport.dem.z
    to_ll = airport.frame.transformers()[1]
    fams: dict[tuple, list[_obj8.PlacedObject]] = {}
    boxed = [o for o in objects if o.plan_bbox is not None]
    bbox_tree = STRtree([o.plan_bbox for o in boxed]) if boxed else None
    cover_cache: dict[str, object] = {}
    # a ROAD surface is flatter than the ramp law: faces steeper than
    # tunnel.ramp_max_grade are banks and ramps' walls, never the floor
    # (measured OTHH: the drainage bowls' 20 % banks pass the 0.7 floor gate)
    normal_min = max(bl.floor_plate_normal_y_min, 1.0 / math.sqrt(1.0 + tn.ramp_max_grade ** 2))
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        stats.placements += 1
        vmin = cache.y_range(o.resolved)[0]
        # the pre-screen: a member with nothing min_descent_m under its own
        # seat plane cannot carry a plate that descends that far
        if vmin == math.inf or vmin > -sr.min_descent_m:
            continue
        fams.setdefault(family_key(o), []).append(o)
    out: list[SunkenRoadRecord] = []
    k_by_res: dict[str, int] = {}
    for fk, members in sorted(fams.items(), key=lambda kv: kv[0]):
        faces: list[tuple[Polygon, float, float]] = []
        belows = []
        owner_of: list[_obj8.PlacedObject] = []
        for o in members:
            f, b = _faces_below(o, cache, dem_z, law, normal_min, sr.top_depth_m)
            faces.extend(f)
            belows.extend(b)
            owner_of.extend([o] * len(f))
        if not faces:
            continue
        stats.families += 1
        u = unary_union([f for f, _z, _a in faces])
        parts = [g for g in shapely.get_parts(u) if g.geom_type == "Polygon"
                 and g.area >= sr.min_plate_m2]
        if not parts:
            continue
        tree = STRtree([f for f, _z, _a in faces])
        region_u = unary_union(belows) if belows else None
        if region_u is not None:
            region_u = region_u.buffer(bl.footprint_close_m, **_MITRE).buffer(
                -bl.footprint_close_m, **_MITRE)
        for part in sorted(parts, key=lambda g: -g.area):
            stats.plates += 1
            plate = Polygon(part.exterior.coords)
            la, lo = to_ll(*plate.centroid.coords[0])
            site = f"{la:.6f},{lo:.6f}"
            own = [o for o, (f, _z, _a) in zip(owner_of, faces) if f.intersects(plate)]
            o0 = max(own, key=lambda o: sum(1 for q in own if q is o)) if own else members[0]
            name = os.path.basename(o0.path)
            ra = _rect_axis(plate)
            if ra is None:
                continue
            length, width, a, b = ra
            axis = LineString([a, b])
            prof = _profile(axis, faces, tree, dem_z, sr.station_m, ob.plate_bin_m, width)
            rows = [r for r in prof if r[1] is not None]
            if len(rows) < 2:
                stats.refused.append(f"{name} at {site}: plate {plate.area:.0f} m2 leaves fewer "
                                     f"than two profile stations")
                continue
            depths = [(r[0], r[4] - r[1]) for r in rows]
            d_first, d_last = depths[0][1], depths[-1][1]
            deep_end = 1 if d_last >= d_first else 0
            shallow = min(d_first, d_last)
            deepest = max(d for _s, d in depths)
            if deepest - shallow < sr.min_descent_m:
                stats.refused.append(f"{name} at {site}: plate {plate.area:.0f} m2 is LEVEL "
                                     f"(descent {deepest - shallow:.2f} m < min_descent_m "
                                     f"{sr.min_descent_m}) — a basement or a pit, the basin pass's")
                continue
            if shallow > bl.contact_band_m:
                stats.refused.append(f"{name} at {site}: plate {plate.area:.0f} m2 ({length:.0f} x "
                                     f"{width:.0f} m) reaches no grade end: its shallow end lies "
                                     f"{shallow:.2f} m under the ground (> contact_band_m "
                                     f"{bl.contact_band_m}) — a basement or a pit, the basin pass's")
                continue
            # walk from the grade end down: the top, then the cut
            ordered = rows if deep_end == 1 else list(reversed(rows))
            dep = [r[4] - r[1] for r in ordered]
            i_top = next((i for i, d in enumerate(dep) if d > sr.top_depth_m), None)
            if i_top is None:
                stats.refused.append(f"{name} at {site}: the plate never leaves the top band")
                continue
            s_top = ordered[i_top][0] if i_top == 0 else _cross(ordered, i_top - 1, i_top, sr.top_depth_m)
            i_cut = next((i for i, d in enumerate(dep) if d >= sr.max_depth_m), None)
            if i_cut is None:
                s_cut = ordered[-1][0]
                cut_note = f"the plate ends {dep[-1]:.2f} m under the ground (< max_depth_m {sr.max_depth_m})"
            else:
                s_cut = _cross(ordered, i_cut - 1, i_cut, sr.max_depth_m) if i_cut > 0 else ordered[0][0]
                cut_note = f"cut ends where the plate reaches max_depth_m {sr.max_depth_m}"
            if abs(s_cut - s_top) < sr.station_m:
                stats.refused.append(f"{name} at {site}: the trench would be {abs(s_cut - s_top):.1f} m "
                                     f"long (< station_m {sr.station_m})")
                continue
            # re-sample s = 0 at the cut, growing toward the top
            sign = 1.0 if s_top > s_cut else -1.0
            total = abs(s_top - s_cut)
            ss = [sr.station_m * k for k in range(int(total // sr.station_m) + 1)]
            if total - ss[-1] > 1e-6:
                ss.append(total)
            sts: list[RoadStation] = []
            pts: list[XY] = []
            for s in ss:
                so = s_cut + sign * s
                p = axis.interpolate(so)
                pts.append((p.x, p.y))
                z = _interp(rows, so, 1)
                hl, hr = _interp(rows, so, 2), _interp(rows, so, 3)
                if sign < 0:
                    hl, hr = hr, hl
                sts.append(RoadStation(s, z, hl, hr, _interp(rows, so, 4)))
            region = None
            if region_u is not None:
                cands = [g for g in shapely.get_parts(region_u)
                         if g.geom_type == "Polygon" and g.intersects(plate)]
                region = max(cands, key=lambda g: g.area) if cands else None
            if region is None:
                region = plate
            cover = 0.0
            covering = []
            for j in (bbox_tree.query(plate, predicate="intersects") if bbox_tree is not None else ()):
                o = boxed[int(j)]
                if o.id not in cover_cache:
                    cover_cache[o.id] = _obj8.above_grade_footprint(o, cache, dem_z, bl.contact_band_m)
                if cover_cache[o.id] is not None:
                    covering.append(cover_cache[o.id])
            if covering:
                cover = unary_union(covering).intersection(plate).area / plate.area
            if cover < sr.roof_min_fraction:
                stats.refused.append(f"{name} at {site}: plate {plate.area:.0f} m2 ({length:.0f} x "
                                     f"{width:.0f} m, {shallow:.2f}..{deepest:.2f} m under) is roofed "
                                     f"over {cover:.0%} of its area (< roof_min_fraction "
                                     f"{sr.roof_min_fraction:.0%}) — an open ramp, not a sunken road "
                                     f"under a building (spec §3)")
                continue
            k = k_by_res.get(o0.path, 0)
            k_by_res[o0.path] = k + 1
            mean_w = 2.0 * sum((st.half_l + st.half_r) / 2.0 for st in sts) / len(sts)
            notes = (f"plate {plate.area:.0f} m2 ({length:.0f} x {width:.0f} m) from {len(own)} face(s) "
                     f"of {len({o.id for o in own})} placement(s); the family's cover over it {cover:.0%}",
                     f"profile: shallow end {shallow:.2f} m under the ground (<= contact_band_m "
                     f"{bl.contact_band_m}), deepest {deepest:.2f} m; {cut_note}",
                     f"trench {total:.1f} m from the cut (floor {sts[0].z:.2f}, ground "
                     f"{sts[0].ground_z:.2f}) to the top (floor {sts[-1].z:.2f}, ground "
                     f"{sts[-1].ground_z:.2f}); mean width {mean_w:.1f} m")
            out.append(SunkenRoadRecord(f"{ID_PREFIX}:{name}@{k}", o0.path,
                                        tuple(sorted({o.id for o in own})), tuple(pts), tuple(sts),
                                        float(total), float(mean_w), float(sts[0].z),
                                        float(sts[0].ground_z), float(sts[-1].z),
                                        float(sts[-1].ground_z), plate,
                                        Polygon(region.exterior.coords), float(cover),
                                        o0.xy, float(o0.anchor_z), float(o0.agl_m), notes))
            stats.roads += 1
    out.sort(key=lambda r: r.id)
    stats.read_s = time.perf_counter() - t0
    return out, stats
