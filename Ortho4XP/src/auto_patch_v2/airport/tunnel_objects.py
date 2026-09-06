"""TUNNEL WALL OBJECTS AS THE TUNNEL AUTHORITY (RULINGS 2026-09-05k-1;
round 2 2026-09-05n; specs ``docs/specs/auto-patch-v2/tunnel-wall-
objects-spec.md`` §3.1 and ``…-round2-spec.md``; law ``structures.toml
[tunnel.object]``).

The owner's five laws (05n), all of them read here or in
``planar/object_corridor.py``: (1) the ramp's MOUTH is at the full depth
of the wall object and the other end reaches GROUND at the end of the
wall — or beyond where ``ramp_max_grade`` needs the length; (2) the
trench never extends beyond the outside of the walls and follows their
CURVES; (3) an OSM tunnel ramp is still built wherever OSM says there is
one, objects or not (precedence PER MOUTH); (4) the top of the wall
object is FLUSH with the ground (the object is re-seated to it).

THE SIGNATURE (round-1 §3.1, unchanged), per resource, over the geometry
the basin pass already parsed (``obj8.ResourceCache`` — never a second
parse): a WALL SKIRT (genuine solids ``skirt_min_depth_m`` or more
below the seat plane), a CREST PLATE (near-horizontal faces at the
largest-area ``plate_bin_m`` bin at or above the seat, ``plate_min_
area_m2``, ``plate_min_height_m`` above the seat), NO FLOOR PLATE below
the seat and NO ROOF along the axis, and per placement a seat
``basin.admission_depth_m`` or more under the ground.

THE WALLS (round 2 §3.1; ``tunnel_walls.py``): the crest plate's plan
union IS the walls' footprint — a U / an O / two bands (measured OTHH:
one welded component per object, the plate ring the only thin band per
wall) — read into the two side walls' inner faces, the end walls and
the free ends; the corridor AXIS is the midline between the inner
faces; the wall band is each wall's own footprint.  NO rectangle.

THE ENDS (§3.2, ``mouth_end = "bore"``): the MOUTH is the end an OSM
tunnel way continues into — a bore END standing inside the corridor
nearer that end, or the bore LINE crossing that end's line; else the
end facing the other placement of the same resource; else the closed
end.  Two bore ends (a box on the bore: OTHH ``tunnel west 1``) are two
mouths and the trench is FLAT at the mouth depth.

THE DATUMS (§3.3, ``mouth_depth = "plate"``): floor at the mouth =
ground(mouth) − plate height; the ramp climbs inside the walls
(``planar/object_corridor.py``).

Every number is a law-table value; nothing here reads the environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
from shapely import affinity as _affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY, rotated_rectangle
from . import obj8 as _obj8
from .deck_signature import is_tunnel_way
from .tunnel_walls import Station, WallLines, midline, read_wall_lines, stations_along

__all__ = ["WallSignature", "Corridor", "TunnelObjectStats", "signature",
           "read_corridors", "ID_PREFIX"]

ID_PREFIX = "tunnel-object"
#: Facing test for the family rule: the other placement lies within this
#: half-angle of the end's outward direction.
_FACING_COS = math.cos(math.radians(45.0))


@_dc.dataclass(frozen=True)
class WallSignature:
    """One resource's reading in the AUTHORED frame (x east, z south,
    y up; the seat plane is y = 0): the crest plate height and area, the
    skirt depth, the plate's plan polygon (the walls' footprint) and the
    plan rectangle's sides (a reading, never a footprint)."""

    path: str
    plate_y: float
    plate_area_m2: float
    skirt_depth_m: float
    plate: Polygon
    length_m: float
    width_m: float


@_dc.dataclass(frozen=True)
class Corridor:
    """One tunnel corridor in the AIRPORT frame (round 2).  ``axis`` runs
    from the MOUTH (s = 0; ``cutout.floor_overlap_m`` OUTSIDE a closed
    end's inner face — the floor overlaps the end wall's footprint,
    2026-09-06b) to the far end; ``stations`` give the inner faces left / right
    of it and the walls' thickness by station; ``trench`` is the region
    between the inner faces, ``walls`` the walls' plan footprint,
    ``footprint`` their union (what a bore mouth is INSIDE of)."""

    id: str
    resource: str
    objects: tuple[str, ...]
    plate_y: float
    axis: tuple[XY, ...]
    stations: tuple[Station, ...]
    length_m: float
    width_m: float
    mouth_closed: bool
    far_closed: bool
    mouth_thickness_m: float
    far_thickness_m: float
    mouth_kind: str
    flat: bool
    mouth_dem_z: float
    floor_z: float
    walls: Polygon
    trench: Polygon
    footprint: Polygon
    anchor_xy: XY
    anchor_dem_z: float
    agl_m: float
    notes: tuple[str, ...] = ()

    @property
    def ends(self) -> str:
        a = "closed" if self.mouth_closed else "open"
        b = "closed" if self.far_closed else "open"
        return f"{a}/{b}"

    @property
    def ground_kind(self) -> str:
        return "bore" if self.flat else ("closed" if self.far_closed else "open")

    @property
    def depth_m(self) -> float:
        return self.plate_y


@_dc.dataclass
class TunnelObjectStats:
    """What the reader saw, admitted and refused (every refusal names
    its reason and the resource)."""

    placements: int = 0
    resources: int = 0
    signatures: int = 0
    corridors: int = 0
    merged: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    signature_s: float = 0.0


# ── the signature ────────────────────────────────────────────────────────

def _faces(v: np.ndarray, tris: np.ndarray):
    """``(|n_y|, plan area, centroid y, max y)`` per triangle."""
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    nrm = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(nrm, axis=1)
    ok = ln > 1e-12
    ny = np.zeros(tris.shape[0])
    ny[ok] = np.abs(nrm[ok, 1] / ln[ok])
    area = 0.5 * np.abs((p1[:, 0] - p0[:, 0]) * (p2[:, 2] - p0[:, 2])
                        - (p2[:, 0] - p0[:, 0]) * (p1[:, 2] - p0[:, 2]))
    cy = (p0[:, 1] + p1[:, 1] + p2[:, 1]) / 3.0
    ymax = np.maximum(np.maximum(p0[:, 1], p1[:, 1]), p2[:, 1])
    return ny, area, cy, ymax


def _rect_axis(poly: Polygon) -> tuple[float, float, XY, XY] | None:
    """``(length, width, a, b)`` of the minimum rotated rectangle — a
    READING of the hull's sides for the stub gate and the roof / floor
    axis tests, never a footprint (05n-2)."""
    rect = rotated_rectangle(poly)
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    if len(c) < 4:
        return None
    edges = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    lens = [math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in edges]
    li = max(range(4), key=lambda i: lens[i])
    length, width = lens[li], min(lens)
    if length <= 0.0:
        return None
    shorts = [edges[(li + 1) % 4], edges[(li + 3) % 4]]
    mids = [((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0) for p, q in shorts]
    a, b = mids
    return float(length), float(width), (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


def _axis_crossing_area(v: np.ndarray, tris: np.ndarray, area: np.ndarray, a: XY, b: XY,
                        wall_m: float) -> float:
    """The plan area of the faces whose plan RUNS ALONG the axis segment
    ``a``–``b`` (authored x, z) for more than ``wall_m``: a floor does,
    an end wall's underside (a slab ``end_cap_open_m`` thick at most)
    does not."""
    if tris.shape[0] == 0:
        return 0.0
    axis = LineString([a, b])
    total = 0.0
    for t, ar in zip(tris.tolist(), area.tolist()):
        pts = [(float(v[i][0]), float(v[i][2])) for i in t]
        tri = Polygon(pts)
        if tri.area > 1e-9 and tri.intersection(axis).length > wall_m:
            total += ar
    return float(total)


def signature(geom: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component], law: Law
              ) -> WallSignature | str:
    """The resource's wall signature, or the REASON it is not a tunnel
    wall object (a string; every refusal names its numbers)."""
    ob = law.tables.structures.tunnel.object
    if not genuine:
        return "no genuine solid component"
    tris = np.concatenate([c.tris for c in genuine])
    v = geom.vertices
    ny, area, cy, ymax = _faces(v, tris)
    skirt = -min(c.min_y for c in genuine)
    if skirt < ob.skirt_min_depth_m:
        return (f"no wall skirt: genuine solids reach only {skirt:.2f} m under the seat "
                f"(< skirt_min_depth_m {ob.skirt_min_depth_m})")
    horiz = ny >= ob.plate_normal_y_min
    pts = v[np.unique(tris.reshape(-1))]
    hull = Polygon([(float(x), float(z)) for x, z in zip(pts[:, 0], pts[:, 2])]).convex_hull
    if hull.geom_type != "Polygon":
        return "the solids' plan hull is degenerate (a line)"
    ra = _rect_axis(hull)
    if ra is None:
        return "the solids' plan hull has no rectangle"
    length, width, a, b = ra
    if length < ob.hull_min_length_m:
        return (f"a stub: the hull's long side is {length:.1f} m "
                f"(< hull_min_length_m {ob.hull_min_length_m})")
    above = horiz & (cy >= 0.0)
    if not above.any():
        return "no crest plate: no near-horizontal solid face at or above the seat"
    bins: dict[int, float] = {}
    for y, ar in zip(cy[above].tolist(), area[above].tolist()):
        k = int(math.floor(y / ob.plate_bin_m))
        bins[k] = bins.get(k, 0.0) + ar
    best = max(bins, key=lambda k: bins[k])
    plate_area = bins[best]
    in_bin = above & (np.floor(cy / ob.plate_bin_m).astype(int) == best)
    plate_y = float(ymax[in_bin].max())
    if plate_area < ob.plate_min_area_m2:
        return (f"not a wall: crest plate {plate_area:.0f} m2 at {plate_y:.2f} m "
                f"(< plate_min_area_m2 {ob.plate_min_area_m2:.0f})")
    if plate_y < ob.plate_min_height_m:
        return (f"a kerb, not a tunnel wall: crest plate at {plate_y:.2f} m above the seat "
                f"(< plate_min_height_m {ob.plate_min_height_m})")
    # NO FLOOR PLATE (``floor_plate_max_m2``): a near-horizontal face
    # below the seat that runs ALONG the corridor's axis is a floor
    below = horiz & (ymax < 0.0)
    floor_area = _axis_crossing_area(v, tris[below], area[below], a, b, ob.end_cap_open_m)
    if floor_area > ob.floor_plate_max_m2:
        return (f"a floor plate below the seat ({floor_area:.0f} m2 along the axis > "
                f"floor_plate_max_m2 {ob.floor_plate_max_m2:.0f}): a basin, basins.py owns it")
    # ...and OPEN ALONG ITS AXIS at every height: a near-horizontal face
    # running along the axis above the seat is a roof or a deck (measured
    # OTHH: the skirt + plate + hull signature alone admitted the Emiri
    # terminal, a fuel building and three terminal road slabs)
    roof_area = _axis_crossing_area(v, tris[horiz], area[horiz], a, b, ob.end_cap_open_m)
    if roof_area >= ob.plate_min_area_m2:
        return (f"roofed along its axis ({roof_area:.0f} m2 of near-horizontal faces run "
                f"along the corridor axis, a plate's worth: >= plate_min_area_m2 "
                f"{ob.plate_min_area_m2:.0f}): a building or a deck, not a wall skirt")
    # THE PLATE IN PLAN (round 2 §3.1): the walls' footprint
    faces = [Polygon([(float(v[i][0]), float(v[i][2])) for i in t])
             for t in tris[in_bin].tolist()]
    plate = unary_union([f for f in faces if f.area > 1e-9]).buffer(0)
    if plate.is_empty:
        return "the crest plate has no plan area"
    return WallSignature(geom.path, plate_y, float(plate_area), float(skirt), plate, length, width)


# ── placements → corridors ───────────────────────────────────────────────

def _seat(o: _obj8.PlacedObject, msl: _t.Mapping[str, float]) -> float:
    """The rendered seat plane: MSL absolute, else DEM(placement) + the
    AGL elevation (``PlacedObject.agl_m`` is 0 for a plain ``OBJECT``)."""
    if o.kind == "OBJECT_MSL":
        return float(msl.get(o.id, o.anchor_z))
    return float(o.anchor_z + o.agl_m)


def _bore_ends_at(walls: WallLines, axis: list[XY], tunnel_ways, tol: float
                  ) -> tuple[list[int], list[int]]:
    """Per end ``(0, 1)``: the ids of the OSM tunnel ways whose mapped END
    stands inside the corridor nearer that end (the bore dips under the
    ground there: OTHH's bores end 3–20 m inside the closed end), or —
    for a bore with NO end inside, one passing through — whose LINE
    crosses that end's line (a box on the bore)."""
    region = unary_union([walls.plate, Polygon(list(walls.inner_a) + list(reversed(walls.inner_b)))
                          ]).buffer(tol)
    ln = LineString(axis)
    out: tuple[list[int], list[int]] = ([], [])
    for w in tunnel_ways:
        line = LineString(w.points)
        inside = [e for e in (w.points[0], w.points[-1]) if region.contains(Point(e))]
        for e in inside:
            k = 0 if ln.project(Point(e)) < ln.length / 2.0 else 1
            if w.id not in out[k]:
                out[k].append(w.id)
        if inside:
            continue
        for k in (0, 1):
            a, b = walls.end_line(k)
            if line.intersects(LineString([a, b]).buffer(tol)) and w.id not in out[k]:
                out[k].append(w.id)
    return out


def _rotated_box(w: WallLines) -> WallLines:
    """The O read the other way round: the end walls become the side
    walls (``inner_a`` = the wall at end 0, from ``inner_b``'s start to
    ``inner_a``'s start; ``inner_b`` = the wall at end 1, in the same
    direction) and the side walls the end walls."""
    a = [w.inner_b[0], w.inner_a[0]]
    b = [w.inner_b[-1], w.inner_a[-1]]
    # the former side walls' thickness at their middles
    la, lb = LineString(w.inner_a), LineString(w.inner_b)
    pa, pb = la.interpolate(0.5, normalized=True), lb.interpolate(0.5, normalized=True)
    mid_ab = ((pa.x + pb.x) / 2.0, (pa.y + pb.y) / 2.0)
    from .tunnel_walls import _dir, _thickness_at
    ua = _dir(mid_ab, (pa.x, pa.y))
    ub = _dir(mid_ab, (pb.x, pb.y))
    ta = _thickness_at((pa.x, pa.y), ua, w.plate, 3.0 * max(w.thickness_m, 0.5))
    tb = _thickness_at((pb.x, pb.y), ub, w.plate, 3.0 * max(w.thickness_m, 0.5))
    return WallLines(w.plate, a, b, (True, True), (ta or w.thickness_m, tb or w.thickness_m),
                     w.thickness_m, "O")


def _faces_other(axis: list[XY], k: int, others: _t.Sequence[Polygon]) -> bool:
    """End ``k``'s outward direction points at another placement of the
    same resource (within ``_FACING_COS``)."""
    e = axis[0] if k == 0 else axis[-1]
    nxt = axis[1] if k == 0 else axis[-2]
    u = (e[0] - nxt[0], e[1] - nxt[1])
    L = math.hypot(*u) or 1.0
    u = (u[0] / L, u[1] / L)
    for p in others:
        c = p.centroid
        d = (c.x - e[0], c.y - e[1])
        D = math.hypot(*d) or 1.0
        if (d[0] * u[0] + d[1] * u[1]) / D >= _FACING_COS:
            return True
    return False


def _oriented(walls: WallLines, axis: list[XY], sts: list[Station], mouth: int,
              overlap: float, sample: float) -> tuple[list[XY], list[Station]]:
    """The axis and stations re-based with s = 0 at the MOUTH end, the
    stations resampled every ``sample`` (the last ON the far end), a
    closed end's station standing ``overlap`` OUTSIDE its inner face
    (the trench floor overlaps the end wall, ``cutout.floor_overlap_m``)."""
    ln = LineString(axis)
    s0, s1 = sts[0].s, sts[-1].s
    if mouth == 1:
        s0, s1 = s1, s0
    closed_m, closed_f = walls.closed[mouth], walls.closed[1 - mouth]
    sign = 1.0 if mouth == 0 else -1.0
    start = s0 - sign * (overlap if closed_m else 0.0)
    end = s1 + sign * (overlap if closed_f else 0.0)
    total = abs(end - start)
    ss = [sample * k for k in range(int(total // sample) + 1)]
    if total - ss[-1] > 1e-6:
        ss.append(total)
    by_s = [(st.s, st) for st in sts]

    def interp(s_orig: float) -> Station:
        lo = max((t for t in by_s if t[0] <= s_orig + 1e-9), key=lambda t: t[0], default=by_s[0])
        hi = min((t for t in by_s if t[0] >= s_orig - 1e-9), key=lambda t: t[0], default=by_s[-1])
        if hi[0] - lo[0] < 1e-9:
            return lo[1]
        f = (s_orig - lo[0]) / (hi[0] - lo[0])
        g = lambda a, b: a + (b - a) * f     # noqa: E731
        return Station(s_orig, g(lo[1].half_l, hi[1].half_l), g(lo[1].half_r, hi[1].half_r),
                       g(lo[1].thick_l, hi[1].thick_l), g(lo[1].thick_r, hi[1].thick_r))

    out_axis: list[XY] = []
    out_st: list[Station] = []
    for s in ss:
        so = start + sign * s
        # beyond the midline's ends (the overlap into an end wall) the
        # axis continues straight along its end direction
        if so < 0.0 or so > ln.length:
            e = ln.interpolate(0.0 if so < 0.0 else ln.length)
            q = ln.interpolate(min(ln.length, 1.0) if so < 0.0 else max(0.0, ln.length - 1.0))
            ux, uy = e.x - q.x, e.y - q.y
            L = math.hypot(ux, uy) or 1.0
            d = (-so) if so < 0.0 else (so - ln.length)
            out_axis.append((e.x + ux / L * d, e.y + uy / L * d))
        else:
            p = ln.interpolate(so)
            out_axis.append((p.x, p.y))
        st = interp(so)
        if mouth == 1:          # travelling the other way: left and right swap
            st = Station(s, st.half_r, st.half_l, st.thick_r, st.thick_l)
        else:
            st = Station(s, st.half_l, st.half_r, st.thick_l, st.thick_r)
        out_st.append(st)
    return out_axis, out_st


def _corridor(sig: WallSignature, o: _obj8.PlacedObject, k: int, airport: Airport,
              tunnel_ways, others: _t.Sequence[Polygon], law: Law) -> Corridor | str:
    """The placement's corridor, or the reason it has none."""
    ob = law.tables.structures.tunnel.object
    tn = law.tables.structures.tunnel
    grid = law.tables.emit.identity.min_distinct_spacing_m
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    plate = _affinity.affine_transform(sig.plate, mat)
    walls = read_wall_lines(plate, law)
    if isinstance(walls, str):
        return walls
    axis = midline(walls, ob.wall_sample_m)
    bores = _bore_ends_at(walls, axis, tunnel_ways, ob.end_cap_open_m)
    notes: list[str] = []
    if walls.kind == "O" and not (bores[0] or bores[1]):
        # A BOX reads its long sides as the side walls; a near-square box
        # on a bore (OTHH tunnel west 1: 35 × 40 m inside) orients itself
        # ALONG the bore — the walls the bore crosses are its end walls
        alt = _rotated_box(walls)
        axis_alt = midline(alt, ob.wall_sample_m)
        bores_alt = _bore_ends_at(alt, axis_alt, tunnel_ways, ob.end_cap_open_m)
        if bores_alt[0] or bores_alt[1]:
            walls, axis, bores = alt, axis_alt, bores_alt
            notes.append("box oriented along the bore that passes through it")
    sts = stations_along(axis, walls, ob.wall_sample_m, grid)
    if len(sts) < 2:
        return "the inner faces leave no station (the walls do not face each other)"
    if bores[0] and bores[1]:
        mouth, flat, kind = 0, True, "bore"
        notes.append(f"bores at both ends ({bores[0]} / {bores[1]}): two mouths, the trench "
                     f"flat at the mouth depth")
    elif bores[0] or bores[1]:
        mouth, flat, kind = (0 if bores[0] else 1), False, "bore"
        notes.append(f"mouth = the bore end (ways {bores[mouth]})")
    elif _faces_other(axis, 0, others) != _faces_other(axis, 1, others):
        mouth, flat, kind = (0 if _faces_other(axis, 0, others) else 1), False, "family"
        notes.append("mouth = the end facing the other placement of the resource")
    elif walls.closed[0] != walls.closed[1]:
        mouth, flat, kind = (0 if walls.closed[0] else 1), False, "closed"
        notes.append("mouth = the closed end")
    else:
        return (f"the mouth is undetermined: no bore at either end, no facing placement, "
                f"ends {walls.kind} {'closed' if walls.closed[0] else 'open'}/"
                f"{'closed' if walls.closed[1] else 'open'}")
    axis2, sts2 = _oriented(walls, axis, sts, mouth,
                            law.tables.structures.cutout.floor_overlap_m, ob.wall_sample_m)
    if len(axis2) < 2:
        return "the corridor is shorter than one station"
    far = 1 - mouth
    mouth_dem = float(airport.dem.z(*axis2[0]))
    if math.isnan(mouth_dem):
        return "no DEM at the mouth"
    floor = mouth_dem - sig.plate_y
    trench = Polygon(list(walls.inner_a) + list(reversed(walls.inner_b)))
    if not trench.is_valid:
        trench = trench.buffer(0)
    footprint = unary_union([walls.plate, trench])
    if footprint.geom_type != "Polygon":
        footprint = footprint.convex_hull
    width = 2.0 * sum((s.half_l + s.half_r) / 2.0 for s in sts2) / len(sts2)
    name = os.path.basename(o.path)
    notes.append(f"walls {walls.kind}: {len(walls.inner_a)} + {len(walls.inner_b)} inner-face "
                 f"vertices, band {walls.thickness_m:.2f} m thick")
    return Corridor(f"{ID_PREFIX}:{name}@{k}", o.path, (o.id,), sig.plate_y, tuple(axis2),
                    tuple(sts2), float(sts2[-1].s), width, walls.closed[mouth], walls.closed[far],
                    walls.end_thickness_m[mouth], walls.end_thickness_m[far], kind, flat,
                    mouth_dem, floor, walls.plate, trench, footprint, o.xy, float(o.anchor_z),
                    float(o.agl_m), tuple(notes))


def read_corridors(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                   cache: _obj8.ResourceCache, law: Law
                   ) -> tuple[list[Corridor], TunnelObjectStats]:
    """Every tunnel corridor the pack's wall objects state, in the
    airport frame; the stats name every refusal by resource."""
    t0 = time.perf_counter()
    stats = TunnelObjectStats()
    msl = {o.id: o.y_offset_m for o in airport.dsf_objects if o.kind == "OBJECT_MSL"}
    admission = law.tables.structures.basin.admission_depth_m
    skirt = law.tables.structures.tunnel.object.skirt_min_depth_m
    tunnel_ways = [w for w in airport.osm_ways if is_tunnel_way(w.tags) and len(w.points) >= 2]
    sigs: dict[str, WallSignature | str] = {}
    counts: dict[str, int] = {}
    admitted: list[tuple[WallSignature, _obj8.PlacedObject]] = []
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        stats.placements += 1
        counts[o.path] = counts.get(o.path, 0) + 1
        if o.witnesses:
            sigs.setdefault(o.path, "the basin pass witnessed a floor in it (basins.py owns it)")
            continue
        if o.path not in sigs:
            stats.resources += 1
            # THE PRE-SCREEN (the basin reader's O(n) step): a skirt reaches
            # skirt_min_depth_m under the seat, so a resource whose lowest
            # authored vertex does not is refused before its components
            # are built (OTHH: 1,350 resources, 7 tunnels)
            vmin = cache.y_range(o.resolved)[0]
            if vmin > -skirt:
                sigs[o.path] = (f"no wall skirt: the lowest vertex is {-vmin:.2f} m under the "
                                f"seat (< skirt_min_depth_m {skirt})")
                continue
            g = cache.geometry(o.resolved)
            sigs[o.path] = signature(g, cache.genuine(o.resolved), law) if g is not None \
                else "unreadable OBJ8"
        sig = sigs[o.path]
        if isinstance(sig, str):
            continue
        seat = _seat(o, msl)
        # THE SEAT IS BELOW GRADE (the basin family's admission depth): a
        # wall object seated AT grade is a fence or a compound wall
        # (measured OTHH: a fuel-farm wall and a terminal kerb wall)
        if seat > o.anchor_z - admission:
            stats.refused.append(f"{o.id} {os.path.basename(o.path)}: seat {seat:.2f} is not "
                                 f"{admission:.1f} m (basin.admission_depth_m) under the ground "
                                 f"at the placement ({o.anchor_z:.2f}) — a wall at grade, not a "
                                 f"tunnel floor")
            continue
        admitted.append((sig, o))
    stats.signatures = sum(1 for s in sigs.values() if not isinstance(s, str))
    for path, sig in sigs.items():
        if isinstance(sig, str) and not sig.startswith("no wall skirt") \
                and not sig.startswith("no genuine") and not sig.startswith("no crest plate"):
            stats.refused.append(f"{os.path.basename(path)} x{counts[path]}: {sig}")
    # the other placements of each resource (the family rule reads them)
    plates: dict[str, list[tuple[str, Polygon]]] = {}
    for sig, o in admitted:
        plates.setdefault(o.path, []).append(
            (o.id, _affinity.affine_transform(sig.plate, _obj8.placement_affine(o.xy, o.heading_deg))))
    out: list[Corridor] = []
    k_by_res: dict[str, int] = {}
    for sig, o in admitted:
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        others = [p for oid, p in plates[o.path] if oid != o.id]
        c = _corridor(sig, o, k, airport, tunnel_ways, others, law)
        if isinstance(c, str):
            stats.refused.append(f"{o.id} {os.path.basename(o.path)}: {c}")
            continue
        out.append(c)
    out.sort(key=lambda c: c.id)
    stats.corridors = len(out)
    stats.signature_s = time.perf_counter() - t0
    return out, stats
