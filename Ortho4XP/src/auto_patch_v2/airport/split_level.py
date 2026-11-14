"""A SPLIT-LEVEL BUILDING: a pack building cut into a slope (owner 2026-11-05,
"add split level buildings as they are very similar to tunnel mouths and
bridges: it's a building that is typically closed (walls on 4 sides) at the
upper level, and at least one open or untextured wall on the lower level(s)
that would be inside terrain.  It gets a pad at the lower level so the upper
level sits at the graded upper height").  Issues #1886, #1905.

THE WITNESS IS THE OBJECT'S OWN WALLS.  The placements sharing one frame
(one anchor, one heading: one authored building) are read together.  Their
plan's rotated rectangle gives four SIDES; each side's wall faces (the
vertical solid triangles within ``[building_pad] split_level_probe_m`` of
it and running along it) are binned by height, and the side's FOOT is the
lowest 1 m band they cover over at least ``split_level_wall_cover`` of its
length.  The building's LOWER FLOOR ``y_lo`` is the lowest foot (a closed
side), its UPPER FLOOR ``y_up`` the highest; a side whose foot stands at
least ``low_level_min_step_m`` (a storey) over ``y_lo`` is OPEN below it:
inside the terrain.

THE GROUND CONFIRMS IT (the open side faces the higher ground): the DEM
just outside the open sides stands at least half the step over the DEM
just outside the closed side across from them, and spans less than the
step along them (one upper level).  A hangar door on level ground is an open
side too; the ground refuses it.

OR THE MAP CONFIRMS IT (owner 2026-11-05/06, SBSP / KLAX / LFSB: "the
bottom of the upper floor's walls sits on airside ... the lower storeys
extend down to the terrain on the groundside"): where the DEM is too coarse
or too flat to show the step (an airport inset under a row of hangars on
an embankment), the open side FACES AIRSIDE -- at least half its stations
``_GROUND_OUT_M`` out lie on airside pavement -- and the low side across
from it does not, and the ground does not refute it (the low side's DEM
stands under half a step over the open side's), and the UPPER FLOOR is
built: an up-facing floor slab at the open side's foot covers at least
``_SLAB_SHARE`` of a ``_SLAB_DEPTH_M`` strip inside the open side.  A
hangar door opening onto the apron reads high on its door side (nothing
walls it below the lintel) but has no floor at the lintel: the slab
refuses it (owner 2026-11-06T02:40Z, SBSP's grouped row: Hangar2's 15 m
door is no storey).

THE STOREYS (#2062, RULINGS 2026-11-13w; spec ``2062-storey-shell-spec``
§1): a split-level building is a terrain-shaped object, and its record also
carries the reading the storey pads (``planar/storey_pad``) are minted from,
in FRAME coordinates (authored y plus each row's own AGL lift):
``runs`` -- the plan's outline cut at its vertices, each run carrying the
foot of the wall faces facing out of it (:func:`_run_feet`), or ``None``;
``levels`` -- the run feet clustered at ``BAND_M``, a level counting only
where its runs hold ``PLANE_SHARE`` of the walled outline (the others'
runs MINOR, on a neighbour's level: :func:`_run_levels`); ``level_plans``
-- per level its walls' frontage strips, then its floors, then the
unwitnessed remainder on the lowest level it meets (:func:`_level_plans`,
spec Amendment A1); ``air_level`` -- the level holding most run length
that faces airside pavement, else ``None``.

Pure reading: no law constant lives here; nothing names a pack, a resource
or an airport.  ``planar/split_level_pit`` turns a record into the pit,
``planar/storey_pad`` into storey pads."""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics as _st
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..geom.foot_planes import PLANE_SHARE
from . import obj8 as _obj8
from .object_cut import _face_normals_y

__all__ = ["SplitLevel", "corner_cut", "read_split_levels", "run_faces", "take_remainder"]

#: the height band a wall side is read in (metres of authored y)
BAND_M = 1.0
#: a wall face is VERTICAL under this |normal y|, and runs ALONG a side
#: within this many degrees
_VERTICAL_NY = 0.3
_ALONG_DEG = 30.0
#: the map witness's upper-floor slab: its share of a strip this deep
#: inside the open side
_SLAB_SHARE = 0.25
_SLAB_DEPTH_M = 10.0
#: the DEM is read this far outside a side, at this many stations along it
_GROUND_OUT_M = 3.0
_GROUND_STATIONS = 7


@_dc.dataclass(frozen=True)
class SplitLevel:
    """One split-level building, in the airport frame."""

    #: the family's first placement id (its witness: the lower floor's)
    id: str
    member_ids: tuple[str, ...]
    paths: tuple[str, ...]
    #: the plan rectangle of the building (frame metres)
    footprint: Polygon
    y_lo: float
    y_up: float
    #: the OPEN sides (frame segments, each running with the building on
    #: its RIGHT: the ground it meets lies on its left, #1903) and the
    #: closed ones
    open_sides: tuple[LineString, ...]
    closed_sides: tuple[LineString, ...]
    ground_open_m: float
    ground_closed_m: float
    #: the anchor of the family, frame xy
    anchor_xy: tuple[float, float]
    #: THE PLAN THE BUILDING COVERS (frame metres): its solids' plan,
    #: closed by ``[building_pad] split_level_probe_m`` -- the pit's plan,
    #: never the whole :attr:`footprint` box (``None``: the box).  A
    #: terminal's rotated box holds the apron between its piers (KLAX
    #: ``Terminal_2``: 14,342 of 33,694 m2 built), and a pit over the box
    #: sank that apron a storey (owner sim read 1.0.472)
    plan: "Polygon | None" = None
    #: THE STOREYS (module docstring; frame coordinates): ``(run, foot)``
    #: per run of the plan's outline (each run with the building on its
    #: RIGHT, ``foot`` ``None`` where no wall faces out of it) ...
    runs: tuple[tuple[LineString, "float | None"], ...] = ()
    #: ... the run feet clustered at ``BAND_M``, ascending (only the levels
    #: that count, spec A1 (2)) ...
    levels: tuple[float, ...] = ()
    #: ... each run's level (``None``: no foot) and the MINOR runs (their
    #: foot's level did not count; they take a neighbour's) ...
    run_levels: tuple["int | None", ...] = ()
    minor: tuple[int, ...] = ()
    #: ... one plan per level (wall feet, floors, then the remainder) ...
    level_plans: tuple[Polygon, ...] = ()
    #: ... and the level the airside meets (``None``: no run faces it)
    air_level: "int | None" = None
    #: which part of the covered plan this record reads (#2062 spec A2
    #: (5)): 0 the largest (the pit's), ``k`` the record ``<witness>#<k>``
    part: int = 0

    @property
    def pit_plan(self) -> Polygon:
        """The plan the pit is cut under: :attr:`plan`, else the box."""
        return self.footprint if self.plan is None else self.plan


def _families(objects: _t.Sequence[_obj8.PlacedObject]) -> list[list[_obj8.PlacedObject]]:
    """Placements sharing one anchor (1 cm) and heading (0.01 deg)."""
    fam: dict[tuple, list] = {}
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        k = (round(float(o.xy[0]), 2), round(float(o.xy[1]), 2),
             round(float(o.heading_deg) % 360.0, 2))
        fam.setdefault(k, []).append(o)
    return [sorted(v, key=lambda o: str(o.id)) for _k, v in sorted(fam.items())]


def _solids(members, cache, lifted: bool = False) -> "tuple[np.ndarray, np.ndarray] | None":
    """All static solid triangles of the family, authored ``(x, y, z)``
    (``lifted``: each member's y raised by its own AGL lift, the frame's
    coordinates)."""
    vs, ts, n = [], [], 0
    for o in members:
        g = cache.geometry(o.resolved)
        if g is None or g.solid is None or not len(g.solid):
            continue
        t = g.solid
        if g.animated.shape[0]:
            t = t[~g.animated]
        lift = float(getattr(o, "agl_m", 0.0) or 0.0) if lifted else 0.0
        vs.append(g.vertices + np.array([0.0, lift, 0.0]) if lift else g.vertices)
        ts.append(t + n)
        n += len(g.vertices)
    if not ts:
        return None
    return np.concatenate(vs), np.concatenate(ts)


def wall_box(v: np.ndarray, t: np.ndarray) -> "list[tuple[float, float]] | None":
    """The building's SIDES: the plan box of its solids aligned with its
    dominant wall direction (the area-weighted mode, mod 90 degrees, of its
    vertical faces' plan directions) -- four authored ``(x, z)`` corners in
    ring order, or ``None`` where it has no wall."""
    vert = _face_normals_y(v, t) < _VERTICAL_NY
    tv = t[vert]
    if not len(tv):
        return None
    a, b = v[tv[:, 0]][:, [0, 2]], v[tv[:, 1]][:, [0, 2]]
    c = v[tv[:, 2]][:, [0, 2]]
    d = np.where((np.linalg.norm(b - a, axis=1) >= np.linalg.norm(c - a, axis=1))[:, None],
                 b - a, c - a)
    w = np.linalg.norm(d, axis=1) * (v[tv][:, :, 1].max(axis=1) - v[tv][:, :, 1].min(axis=1))
    ang = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 90.0
    hist = np.bincount(np.floor(ang).astype(int) % 90, weights=w, minlength=90)
    th = math.radians(float(np.argmax(hist)) + 0.5)
    co, si = math.cos(th), math.sin(th)
    xz = v[:, [0, 2]]
    u = xz @ np.array([[co, -si], [si, co]])          # rotate by -th
    x0, z0 = u.min(axis=0)
    x1, z1 = u.max(axis=0)
    back = np.array([[co, si], [-si, co]])
    return [tuple((np.array(p) @ back).tolist()) for p in
            ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]


def _covered_plan(v: np.ndarray, t: np.ndarray, close_m: float, min_hole_m2: float
                 ) -> "Polygon | None":
    """The plan the solids ``(v, t)`` COVER (authored ``(x, z)``): the union
    of their non-vertical faces' plan triangles, closed by ``close_m``
    (walls a door apart are one building), holes under ``min_hole_m2``
    filled; the largest part, or ``None``."""
    parts = _covered_parts(v, t, close_m, min_hole_m2)
    return parts[0] if parts else None


def _covered_parts(v: np.ndarray, t: np.ndarray, close_m: float, min_hole_m2: float
                   ) -> list[Polygon]:
    """Every part of the covered plan (:func:`_covered_plan`), the largest
    first (#2062 spec A2 (5): each part of at least ``min_area_m2`` is read
    as its own storey record)."""
    ny = _face_normals_y(v, t)
    P = v[t[ny >= _VERTICAL_NY]][:, :, [0, 2]]
    if not len(P):
        return []
    tris = [g for g in shapely.polygons(P).tolist() if g is not None and g.area > 1e-6]
    if not tris:
        return []
    u = unary_union([g.buffer(0) for g in tris]).buffer(close_m, join_style="mitre")
    u = u.buffer(-close_m, join_style="mitre")
    parts = sorted((g for g in getattr(u, "geoms", [u])
                    if g.geom_type == "Polygon" and g.area > 0.0), key=lambda g: -g.area)
    return [Polygon(g.exterior, [h for h in g.interiors if Polygon(h).area >= min_hole_m2])
            for g in parts]


def _open_edges(plan: Polygon, closed: _t.Sequence[LineString], probe: float,
                back_m: float = 0.0) -> list[LineString]:
    """The OPEN boundary of a pit under ``plan``: the straight edges of its
    outline that face OUT of the building (away from its centroid) and lie
    more than ``probe`` off the TALL sides (``closed``, the box's sides
    walled down to the lower floor) -- the open side the upper ground meets.
    An edge facing back into the building (a notch between piers) is no
    side of it, nor is one FACING a tall side within ``back_m`` (the
    ``split_level_back_cut_m`` over which the pit cuts the back down to the
    lower floor: #1903 KLAX ``Terminal_8``'s east facade, 3.1-3.4 m inside
    its tall side's line, read open over the back cut).  Each edge runs
    CLOCKWISE: the building on its right, the ground it meets on its left."""
    ring = plan.exterior
    if ring.is_ccw:
        ring = LineString(list(ring.coords)[::-1])
    tall = unary_union(list(closed)).buffer(probe, cap_style="flat") if closed else None
    lines = unary_union(list(closed)) if closed and back_m > 0.0 else None
    cx, cy = plan.centroid.x, plan.centroid.y
    out = []
    pts = list(ring.coords)
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:], strict=True):
        seg = LineString([(x0, y0), (x1, y1)])
        if seg.length <= 0.0 or (tall is not None and seg.within(tall)):
            continue
        # clockwise ring: the outward normal is the edge turned left
        nx, ny = -(y1 - y0), (x1 - x0)
        mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        if (mx - cx) * nx + (my - cy) * ny <= 0.0:
            continue
        k = back_m / seg.length
        if lines is not None and LineString([(mx, my), (mx + nx * k, my + ny * k)]
                                            ).intersects(lines):
            continue
        out.append(seg)
    return out


def _outward_left(side: LineString, centre: tuple[float, float]) -> LineString:
    """``side`` running with ``centre`` on its RIGHT (the open sides'
    orientation, :attr:`SplitLevel.open_sides`)."""
    (x0, y0), (x1, y1) = side.coords[0], side.coords[-1]
    if (centre[0] - x0) * -(y1 - y0) + (centre[1] - y0) * (x1 - x0) > 0.0:
        return LineString(list(side.coords)[::-1])
    return side


def _side_feet(v: np.ndarray, t: np.ndarray, sides: _t.Sequence[tuple], probe: float,
              cover: float) -> list[float | None]:
    """Each side's FOOT (module docstring): the lowest ``BAND_M`` band over
    which the wall faces FACING OUT of that side (their outward normal --
    the OBJ8 winding's, ``-(p1 - p0) x (p2 - p0)`` -- within
    ``_ALONG_DEG`` of the side's outward normal) cover ``cover`` of its
    length, or ``None``.  A wall stands anywhere behind its side (a
    facade set back, a hangar's inset door frame); ``probe`` only reaches
    past the side's ends.  ``sides`` are authored plan segments ``((x0,
    z0), (x1, z1))`` in ring order."""
    vert = _face_normals_y(v, t) < _VERTICAL_NY
    tv = t[vert]
    if not len(tv):
        return [None] * len(sides)
    P = v[tv]                                        # (m, 3, 3)
    nrm = -np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    nxz = nrm[:, [0, 2]]
    nl = np.linalg.norm(nxz, axis=1)
    xz = P[:, :, [0, 2]]
    ln = np.stack([np.linalg.norm(xz[:, 0] - xz[:, 1], axis=1),
                   np.linalg.norm(xz[:, 0] - xz[:, 2], axis=1),
                   np.linalg.norm(xz[:, 1] - xz[:, 2], axis=1)], axis=1).max(axis=1)
    mid = xz.mean(axis=1)
    y0, y1 = P[:, :, 1].min(axis=1), P[:, :, 1].max(axis=1)
    lo = float(y0.min())
    nb = int(math.ceil((float(y1.max()) - lo) / BAND_M)) + 1
    ctr = np.mean(np.asarray([p for s in sides for p in s], float), axis=0)
    cos_along = math.cos(math.radians(_ALONG_DEG))
    out: list[float | None] = []
    for (p0, p1) in sides:
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        L = float(np.linalg.norm(p1 - p0))
        if L <= 0.0:
            out.append(None)
            continue
        u = (p1 - p0) / L
        n_out = np.array([u[1], -u[0]])
        if (ctr - p0) @ n_out > 0.0:
            n_out = -n_out
        s_ = (mid - p0) @ u
        facing = (nxz @ n_out) >= cos_along * np.maximum(nl, 1e-12)
        on = facing & (s_ >= -probe) & (s_ <= L + probe) & (ln > 0.05)
        cov = np.zeros(nb)
        for q in np.flatnonzero(on):
            b0 = int(math.floor((y0[q] - lo) / BAND_M))
            b1 = int(math.ceil((y1[q] - lo) / BAND_M))
            cov[b0:max(b1, b0 + 1)] += 0.5 * ln[q]
        full = np.flatnonzero(cov >= cover * L)
        out.append(None if not len(full) else lo + BAND_M * float(full[0]))
    return out


def _ground(dem_z, side: LineString, centre) -> "list[float]":
    """The DEM ``_GROUND_OUT_M`` outside ``side`` (away from the
    footprint's ``centre``) at ``_GROUND_STATIONS`` stations."""
    zs = []
    for x, y in _stations(side, centre):
        try:
            z = float(dem_z(x, y))
        except Exception:  # noqa: BLE001 -- off the raster
            continue
        if z == z:
            zs.append(z)
    return zs


def _stations(side: LineString, centre) -> "list[tuple[float, float]]":
    """The ``_GROUND_STATIONS`` points ``_GROUND_OUT_M`` outside ``side``
    (away from the footprint's ``centre``)."""
    (x0, y0), (x1, y1) = side.coords[0], side.coords[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L <= 0.0:
        return []
    nx, ny = dy / L, -dx / L
    mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    if (centre[0] - mx) * nx + (centre[1] - my) * ny > 0.0:
        nx, ny = -nx, -ny
    return [(x0 + f * dx + nx * _GROUND_OUT_M, y0 + f * dy + ny * _GROUND_OUT_M)
            for f in ((i + 0.5) / _GROUND_STATIONS for i in range(_GROUND_STATIONS))]


def _airside_share(airside, side: LineString, centre) -> float:
    """The share of :func:`_stations` outside ``side`` lying on
    ``airside`` (a prepared plan geometry)."""
    pts = _stations(side, centre)
    return sum(bool(airside.contains(Point(p))) for p in pts) / len(pts) if pts else 0.0


def run_faces(ground, run: LineString) -> bool:
    """A frame run (the building on its RIGHT) FACES ``ground`` (a prepared
    plan geometry: the airside pavement, a structure floor): half its
    :func:`_stations` outside it lie on it."""
    (x0, y0), (x1, y1) = run.coords[0], run.coords[-1]
    L = run.length or 1.0
    inside = (0.5 * (x0 + x1) + (y1 - y0) / L, 0.5 * (y0 + y1) - (x1 - x0) / L)
    return _airside_share(ground, run, inside) >= 0.5


def _slab_share(v: np.ndarray, t: np.ndarray, side: tuple, centre, y: float) -> float:
    """The share of a ``_SLAB_DEPTH_M`` strip inside the authored side
    ``side`` covered by up-facing horizontal solid faces at ``y`` (within
    ``BAND_M``)."""
    p0, p1 = np.asarray(side[0], float), np.asarray(side[1], float)
    L = float(np.linalg.norm(p1 - p0))
    if L <= 0.0:
        return 0.0
    u = (p1 - p0) / L
    n_in = np.array([-u[1], u[0]])
    if (np.asarray(centre, float) - p0) @ n_in < 0.0:
        n_in = -n_in
    P = v[t]
    n = -np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    area = 0.5 * np.linalg.norm(n, axis=1)
    up = n[:, 1] > 0.9 * np.maximum(2.0 * area, 1e-12)
    mid = P[:, :, [0, 2]].mean(axis=1)
    d, s_ = (mid - p0) @ n_in, (mid - p0) @ u
    on = up & (np.abs(P[:, :, 1].mean(axis=1) - y) < BAND_M) & (d >= 0.0) \
        & (d <= _SLAB_DEPTH_M) & (s_ >= 0.0) & (s_ <= L)
    return float(area[on].sum()) / (L * _SLAB_DEPTH_M)


def _wall_segments(v: np.ndarray, t: np.ndarray):
    """``(segments, outward normals, y0, y1)`` of the VERTICAL solid faces
    of ``(v, t)``: each face's plan segment (its two farthest corners,
    ``(m, 2, 2)`` authored ``(x, z)``), its OBJ8 outward normal in plan
    (unnormalised) and its height span -- or ``None``."""
    vert = _face_normals_y(v, t) < _VERTICAL_NY
    tv = t[vert]
    if not len(tv):
        return None
    P = v[tv]
    nxz = (-np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]))[:, [0, 2]]
    xz = P[:, :, [0, 2]]
    pairs = ((0, 1), (0, 2), (1, 2))
    d = np.stack([np.linalg.norm(xz[:, a] - xz[:, b], axis=1) for a, b in pairs], axis=1)
    k = np.argmax(d, axis=1)
    ia = np.array([pairs[j][0] for j in k])
    ib = np.array([pairs[j][1] for j in k])
    r = np.arange(len(tv))
    seg = np.stack([xz[r, ia], xz[r, ib]], axis=1)
    return seg, nxz, P[:, :, 1].min(axis=1), P[:, :, 1].max(axis=1)


def _run_feet(v: np.ndarray, t: np.ndarray, runs: _t.Sequence[tuple], normals: _t.Sequence,
             plan: Polygon, probe: float, cover: float, step: float = 1.0
             ) -> list["float | None"]:
    """Each RUN's foot (#2062, ``_side_feet`` per run of the plan's
    outline): stations ``step`` apart along the run look INTO the building
    (against its outward ``normals``) across the plan widened by ``probe``;
    the wall faces a station's line crosses that FACE OUT of the run (their
    outward normal within ``_ALONG_DEG`` of the run's) cover its height
    bands -- a facade set back under an overhang is the run's own, as a box
    side's is (:func:`_side_feet`).  The foot is the lowest ``BAND_M`` band
    covered at ``cover`` of the stations, or ``None``.  ``runs`` are
    authored plan segments ``((x0, z0), (x1, z1))``."""
    got = _wall_segments(v, t)
    if got is None or not runs:
        return [None] * len(runs)
    seg, nxz, y0, y1 = got
    ln = np.linalg.norm(seg[:, 1] - seg[:, 0], axis=1)
    keep = np.flatnonzero(ln > 0.05)
    if not len(keep):
        return [None] * len(runs)
    from shapely.strtree import STRtree
    tree = STRtree(shapely.linestrings(seg[keep]))
    nl = np.linalg.norm(nxz, axis=1)
    lo = float(y0.min())
    nb = int(math.ceil((float(y1.max()) - lo) / BAND_M)) + 1
    b0 = np.floor((y0 - lo) / BAND_M).astype(int)
    b1 = np.maximum(np.ceil((y1 - lo) / BAND_M).astype(int), b0 + 1)
    reach = plan.buffer(probe, join_style="mitre")
    x0, z0, x1, z1 = reach.bounds
    far = math.hypot(x1 - x0, z1 - z0) + probe
    cos_along = math.cos(math.radians(_ALONG_DEG))
    out: list[float | None] = []
    for (p0, p1), n_out in zip(runs, normals, strict=True):
        p0, p1, n_out = (np.asarray(q, float) for q in (p0, p1, n_out))
        L = float(np.linalg.norm(p1 - p0))
        if L <= 0.0:
            out.append(None)
            continue
        k = max(1, int(math.ceil(L / step)))
        rays = []
        for i in range(k):
            s = p0 + (i + 0.5) / k * (p1 - p0)
            a = s + n_out * probe * 0.999
            ray = LineString([a, s - n_out * far]).intersection(reach)
            parts = [g for g in getattr(ray, "geoms", [ray])
                     if g.geom_type == "LineString" and g.distance(Point(a)) < 1e-6]
            rays.append(parts[0] if parts else LineString([a, s]))
        ri, fi = tree.query(rays, predicate="intersects")
        f = keep[fi]
        ok = (nxz[f] @ n_out) >= cos_along * np.maximum(nl[f], 1e-12)
        cov = np.zeros((k, nb), bool)
        for r_, q in zip(ri[ok], f[ok], strict=True):
            cov[r_, b0[q]:b1[q]] = True
        full = np.flatnonzero(cov.mean(axis=0) >= cover)
        out.append(None if not len(full) else lo + BAND_M * float(full[0]))
    return out


def _storey_levels(feet: _t.Sequence[tuple["float | None", float]]) -> tuple[float, ...]:
    """The LEVELS of a building (#2062): its runs' ``(foot, length)``
    clustered at ``BAND_M`` (a foot more than a band over the last starts a
    level), each level its runs' length-weighted median foot, ascending."""
    known = sorted((float(f), float(L)) for f, L in feet if f is not None and L > 0.0)
    groups: list[list[tuple[float, float]]] = []
    for f, L in known:
        if groups and f - groups[-1][-1][0] <= BAND_M:
            groups[-1].append((f, L))
        else:
            groups.append([(f, L)])
    out = []
    for g in groups:
        half, acc = 0.5 * sum(L for _f, L in g), 0.0
        for f, L in g:
            acc += L
            if acc >= half:
                out.append(round(f, 3))
                break
    return tuple(out)


def _run_levels(feet: _t.Sequence[tuple["float | None", float]], step: float
                ) -> tuple[tuple[float, ...], list["int | None"], list[bool]]:
    """THE LEVELS AND EACH RUN'S LEVEL (#2062, spec A1 (2)): the runs'
    ``(foot, length)`` (ring order) clustered (:func:`_storey_levels`); a
    level COUNTS only where its runs hold ``PLANE_SHARE`` of the walled
    outline's length and it stands ``step`` from its neighbours (of two too
    close, the one holding less goes).  A run of a dropped level is MINOR:
    it takes the level of its neighbouring run along the outline (the
    nearest counted run each way; the longer of the two where they differ,
    the lower on a tie).  ``(levels, run level, minor)``; a run with no
    foot has no level."""
    raw = _storey_levels(feet)
    if not raw:
        return (), [None] * len(feet), [False] * len(feet)
    own = [None if f is None else min(range(len(raw)), key=lambda j: abs(raw[j] - f))
           for f, _L in feet]
    walled = sum(L for f, L in feet if f is not None) or 1.0
    held = [sum(L for (_f, L), k in zip(feet, own, strict=True) if k == j) / walled
            for j in range(len(raw))]
    keep = list(range(len(raw)))
    while True:
        bad = [j for j in keep if held[j] < PLANE_SHARE]
        bad += [min((a, b), key=lambda j: (held[j], -j))
                for a, b in zip(keep, keep[1:], strict=False)
                if raw[b] - raw[a] < step]
        if not bad or len(keep) == 1:
            break
        keep.remove(min(bad, key=lambda j: (held[j], j)))
    idx = {j: i for i, j in enumerate(keep)}
    level = [None if k is None or k not in idx else idx[k] for k in own]
    minor = [k is not None and k not in idx for k in own]
    n = len(feet)
    for i in [i for i in range(n) if minor[i]]:
        near = []
        for d in (-1, 1):
            for s in range(1, n):
                j = (i + d * s) % n
                if level[j] is not None and not minor[j]:
                    near.append(j)
                    break
        if not near:
            level[i] = 0
            continue
        best = max(near, key=lambda j: (feet[j][1], -level[j]))
        level[i] = level[best]
    return tuple(raw[j] for j in keep), level, minor


def _strip(p0, p1, n_out, depth: float) -> Polygon:
    """The strip ``depth`` deep INSIDE the authored run ``p0 -> p1`` (its
    outward normal ``n_out``)."""
    a, b, n = np.asarray(p0, float), np.asarray(p1, float), np.asarray(n_out, float)
    return Polygon([tuple(a), tuple(b), tuple(b - n * depth), tuple(a - n * depth)])


def _level_plans(plan: Polygon, levels: _t.Sequence[float], runs: _t.Sequence[tuple],
                 normals: _t.Sequence, run_level: _t.Sequence, probe: float,
                 frontage: float) -> tuple:
    """One plan per LEVEL (#2062, spec A1 (1) as amended by A2 (1)), taken
    in this order: (a) WALL FEET -- each run owns the strip ``frontage``
    deep inside it at its level; where the strips of two outline-adjacent
    runs of different levels overlap, the overlap is cut by the bisector
    through their common vertex (:func:`corner_cut`); any other overlap
    goes to the lower level (ground under the building may be too low --
    hidden in its walls -- never too high); (c) the UNWITNESSED REMAINDER
    -- open downward, it takes the LOWEST level it shares ``probe`` of
    boundary with, else the level it shares most with.  FLOORS ARE NO
    WITNESS OF GROUND (A2 (1)): an upper floor over lower ground is a deck.
    Authored ``(x, z)``."""
    if len(levels) < 2:
        return (plan,)
    strips = corner_cut([_strip(p0, p1, n, frontage) for (p0, p1), n
                          in zip(runs, normals, strict=True)], runs, normals, run_level)
    out: list = [Polygon() for _ in levels]
    taken = Polygon()
    for k in range(len(levels)):
        gs = [g for g, lv in zip(strips, run_level, strict=True) if lv == k]
        if gs:
            g = unary_union(gs).buffer(0).intersection(plan).difference(taken).buffer(0)
            out[k] = unary_union([out[k], g]).buffer(0)
            taken = unary_union([taken, g])
    return tuple(take_remainder(out, plan.difference(taken), probe))


def corner_cut(strips: list, runs: _t.Sequence[tuple], normals: _t.Sequence,
               run_level: _t.Sequence) -> list:
    """``strips`` (one per run, ring order) with the overlap of every two
    OUTLINE-ADJACENT runs of different levels (sharing an end vertex) split
    by the bisector of their corner: each keeps the overlap on its own
    side (spec A2 (1)).  ``normals`` point AWAY from the strips (the runs'
    outward normals for strips inside the plan, inward for strips outside
    it: ``planar/storey_pad``'s back cut)."""
    out = list(strips)
    n = len(runs)
    for i in range(n if n > 2 else n - 1):
        j = (i + 1) % n
        if run_level[i] is None or run_level[j] is None or run_level[i] == run_level[j]:
            continue
        p = _shared_end(runs[i], runs[j])
        if p is None:
            continue
        ov = out[i].intersection(out[j])
        if ov.is_empty or ov.area <= 1e-9:
            continue
        d = -(np.asarray(normals[i], float) + np.asarray(normals[j], float))
        if float(np.linalg.norm(d)) < 1e-9:
            continue
        d = d / np.linalg.norm(d)
        side = np.array([-d[1], d[0]])
        big = 1e3 * (1.0 + max(out[i].length, out[j].length))
        for a, b in ((i, j), (j, i)):
            mid = 0.5 * (np.asarray(runs[a][0], float) + np.asarray(runs[a][1], float))
            sg = 1.0 if float((mid - p) @ side) >= 0.0 else -1.0
            other = Polygon([tuple(p - d * big), tuple(p + d * big),
                             tuple(p + d * big - side * sg * big),
                             tuple(p - d * big - side * sg * big)])
            out[a] = out[a].difference(ov.intersection(other)).buffer(0)
    return out


def _shared_end(a: _t.Sequence, b: _t.Sequence) -> "np.ndarray | None":
    """The end vertex runs ``a`` and ``b`` share (either orientation)."""
    for p in (a[0], a[-1]):
        for q in (b[0], b[-1]):
            if math.dist(p, q) <= 1e-6:
                return np.asarray(p, float)
    return None


def take_remainder(plans: _t.Sequence, rest, probe: float) -> list:
    """``plans`` (one per level) with every piece of ``rest`` added to a
    level (spec A1 (1) (c)): a piece is open downward and takes the LOWEST
    level it shares ``probe`` of boundary with, else the level it shares
    most with (a piece meeting no level at all waits for the others, then
    takes the lowest)."""
    out = list(plans)
    pieces = sorted((g for g in getattr(rest, "geoms", [rest])
                     if g.geom_type == "Polygon" and g.area > 1e-6), key=lambda g: -g.area)
    for last in (False, True):
        later = []
        for piece in pieces:
            edge = piece.exterior
            share = [edge.intersection(g.buffer(1e-3)).length if not g.is_empty else 0.0
                     for g in out]
            if max(share) <= 0.0 and not last:
                later.append(piece)
                continue
            k = next((j for j, s in enumerate(share) if s >= probe), None)
            if k is None:
                k = max(range(len(out)), key=lambda j: (share[j], -j))
            out[k] = unary_union([out[k], piece]).buffer(0)
        pieces = later
    return out


def _storeys(fam, cache, cs, cov, aff, probe: float, cover: float, grid: float, airside,
             step: float, frontage: float) -> dict:
    """The record's STOREY fields (module docstring) in the frame: runs,
    levels, each run's level and minor flag, level plans and the airside's
    level."""
    lifted = any(float(getattr(o, "agl_m", 0.0) or 0.0) for o in fam)
    got = _solids(fam, cache, lifted=True) if lifted else _solids(fam, cache)
    if got is None:
        return {}
    v, t = got
    outline = cov if cov is not None else Polygon(cs)
    ring = list(outline.simplify(1e-6).exterior.coords)[:-1]
    if len(ring) < 3:
        return {}
    ccw = Polygon(ring).exterior.is_ccw

    def frame(p, a=aff):
        return (a[0] * p[0] + a[1] * p[1] + a[4], a[2] * p[0] + a[3] * p[1] + a[5])
    runs_a, normals = [], []
    for i, p0 in enumerate(ring):
        p1 = ring[(i + 1) % len(ring)]
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dz)
        if L <= 0.0:
            continue
        runs_a.append((p0, p1))
        normals.append((dz / L, -dx / L) if ccw else (-dz / L, dx / L))
    feet = _run_feet(v, t, runs_a, normals, outline, probe, cover)
    levels, run_level, minor = _run_levels(
        [(f, math.dist(p0, p1)) for (p0, p1), f in zip(runs_a, feet, strict=True)], step)
    # the frame runs with the building on their RIGHT (the open sides'
    # orientation): the frame ring clockwise
    cw = not Polygon([frame(p) for p in ring]).exterior.is_ccw
    runs = tuple((LineString([frame(p0), frame(p1)] if cw else [frame(p1), frame(p0)]), f)
                 for (p0, p1), f in zip(runs_a, feet, strict=True))
    from shapely import affinity
    m = [aff[0], aff[1], aff[2], aff[3], aff[4], aff[5]]
    plans = tuple(affinity.affine_transform(g, m) for g in _level_plans(
        outline, levels, runs_a, normals, run_level, probe, frontage))
    air = None
    if airside is not None and len(levels) >= 2:
        by = [0.0] * len(levels)
        for (r, _f), k in zip(runs, run_level, strict=True):
            if k is None:
                continue
            if run_faces(airside, r):
                by[k] += r.length
        if max(by) > 0.0:
            air = max(range(len(levels)), key=lambda j: (by[j], -j))
    return {"runs": runs, "levels": levels, "run_levels": tuple(run_level),
            "minor": tuple(i for i, f in enumerate(minor) if f), "level_plans": plans,
            "air_level": air}


def read_split_levels(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                      law, dem_z, airside=None) -> tuple[list[SplitLevel], list[str]]:
    """Every split-level building of ``objects`` (module docstring) and one
    note per family read with an open side.  ``airside`` (a prepared plan
    geometry of the airside pavement, frame metres) arms the map witness."""
    bp = law.tables.structures.building_pad
    cover = float(getattr(bp, "split_level_wall_cover", 0.0) or 0.0)
    step = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if cover <= 0.0 or step <= 0.0 or dem_z is None:
        return [], []
    probe = float(bp.split_level_probe_m)
    back = float(getattr(bp, "split_level_back_cut_m", 0.0) or 0.0)
    pmin = float(bp.min_area_m2)
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    frontage = float(law.tables.emit.design.pad_frontage_m)
    out: list[SplitLevel] = []
    notes: list[str] = []
    for fam in _families(objects):
        got = _solids(fam, cache)
        if got is None:
            continue
        v, t = got
        if float(np.ptp(v[:, 1])) < 2.0 * step:
            continue
        cs = wall_box(v, t)
        if cs is None or Polygon(cs).area < pmin:
            continue
        sides = [(cs[i], cs[(i + 1) % 4]) for i in range(4)]
        feet = _side_feet(v, t, sides, probe, cover)
        known = [f for f in feet if f is not None]
        if len(known) < 2:
            continue
        y_lo, y_up = min(known), max(known)
        # "closed (walls on 4 sides) at the upper level": a storey stands
        # over the open side's foot (an embankment block topping out at it
        # -- an arrestor bed -- is no building)
        if y_up - y_lo < step or float(v[:, 1].max()) - y_up < step:
            continue
        o = fam[0]
        aff = _obj8.placement_affine(o.xy, o.heading_deg)

        def frame(p, a=aff):
            return (a[0] * p[0] + a[1] * p[1] + a[4], a[2] * p[0] + a[3] * p[1] + a[5])
        segs = [LineString([frame(p0), frame(p1)]) for p0, p1 in sides]
        foot = [Polygon([frame(c) for c in cs])]
        centre = foot[0].centroid.coords[0]
        opened = [s for s, f in zip(segs, feet, strict=True) if f is None or f >= y_lo + step]
        closed = [s for s, f in zip(segs, feet, strict=True) if f is not None and f < y_lo + step]
        is_open = [f is None or f >= y_lo + step for f in feet]
        # the LOW side is the closed side across the building from an open
        # one (the sides running up the slope between them read both levels)
        across = [segs[(i + 2) % 4] for i in range(4)
                  if is_open[i] and not is_open[(i + 2) % 4]]
        g_open = [z for s in opened for z in _ground(dem_z, s, centre)]
        g_closed = [z for s in (across or closed) for z in _ground(dem_z, s, centre)]
        name = o.path.rsplit("/", 1)[-1]
        if not g_open or not g_closed:
            continue
        go, gc = _st.median(g_open), _st.median(g_closed)
        half = 0.5 * (y_up - y_lo)
        # the open side meets ONE upper ground: its relief along the open
        # walls stays under the step (a building whose "open" sides follow a
        # slope a storey high is a skirt on it, not two levels)
        spread = max(g_open) - min(g_open)
        by = "ground" if go - gc >= half else ""
        if not by and airside is not None and across and gc - go < half:
            a_open = _st.mean(_airside_share(airside, s, centre) for s in opened)
            a_low = _st.mean(_airside_share(airside, s, centre) for s in across)
            ctr_a = np.mean(np.asarray(cs, float), axis=0)
            slab = max((_slab_share(v, t, sides[i], ctr_a, feet[i]) for i in range(4)
                        if is_open[i] and feet[i] is not None and not is_open[(i + 2) % 4]),
                       default=0.0)
            by = "map" if a_open >= 0.5 > a_low and slab >= _SLAB_SHARE else ""
        why = "" if by else ": refused, the open side's ground is not the higher"
        why = why or ("" if spread <= 2.0 * half else f": refused, the open side's ground "
                      f"spans {spread:.1f} m (no one upper level)")
        verdict = not why
        notes.append(f"{o.id} {name} (+{len(fam) - 1}): feet "
                     + "/".join("-" if f is None else f"{f:.1f}" for f in feet)
                     + f", floors {y_lo:.1f} / {y_up:.1f}, ground open {go:.1f} (spans "
                     f"{spread:.1f}) closed {gc:.1f}"
                     + (f": SPLIT-LEVEL (by the {by})" if verdict else why))
        if not verdict:
            continue
        covs = _covered_parts(v, t, probe, pmin)
        cov = covs[0] if covs else None
        plan = None if cov is None else _framed(cov, frame)
        # the plan's open edges run clockwise already; the box's sides are
        # turned to (the box is convex: its centre lies inside every side)
        edges = _open_edges(plan, closed, probe, back) if plan is not None else []
        opened = edges or [_outward_left(s, centre) for s in opened]
        sl = SplitLevel(str(o.id), tuple(str(m.id) for m in fam),
                        tuple(sorted({m.path for m in fam})), foot[0],
                        round(y_lo, 3), round(y_up, 3), tuple(opened), tuple(closed),
                        round(go, 3), round(gc, 3), (float(o.xy[0]), float(o.xy[1])),
                        plan, **_storeys(fam, cache, cs, cov, aff, probe, cover, grid,
                                         airside, step, frontage))
        out.append(sl)
        # EVERY PART of the covered plan (#2062 spec A2 (5)): a part of
        # ``min_area_m2`` or more is its own storey record ``<witness>#<k>``
        # (the pit reads part 0 only)
        out.extend(_dc.replace(sl, id=f"{sl.id}#{k}", plan=_framed(c, frame), part=k,
                               **_storeys(fam, cache, cs, c, aff, probe, cover, grid,
                                          airside, step, frontage))
                   for k, c in enumerate(covs) if k and c.area >= pmin)
    return out, notes


def _framed(g: Polygon, frame) -> Polygon:
    """The authored plan polygon ``g`` in the airport frame."""
    return Polygon([frame(c) for c in g.exterior.coords],
                   [[frame(c) for c in h.coords] for h in g.interiors])
