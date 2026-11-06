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

Pure reading: no law constant lives here; nothing names a pack, a resource
or an airport.  ``planar/split_level_pit`` turns a record into the pit."""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics as _st
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from . import obj8 as _obj8
from .object_cut import _face_normals_y

__all__ = ["SplitLevel", "read_split_levels"]

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
    #: the OPEN sides (frame segments) and the closed ones
    open_sides: tuple[LineString, ...]
    closed_sides: tuple[LineString, ...]
    ground_open_m: float
    ground_closed_m: float
    #: the anchor of the family, frame xy
    anchor_xy: tuple[float, float]


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


def _solids(members, cache) -> "tuple[np.ndarray, np.ndarray] | None":
    """All static solid triangles of the family, authored ``(x, y, z)``."""
    vs, ts, n = [], [], 0
    for o in members:
        g = cache.geometry(o.resolved)
        if g is None or g.solid is None or not len(g.solid):
            continue
        t = g.solid
        if g.animated.shape[0]:
            t = t[~g.animated]
        vs.append(g.vertices)
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
    pmin = float(bp.min_area_m2)
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
        out.append(SplitLevel(str(o.id), tuple(str(m.id) for m in fam),
                              tuple(sorted({m.path for m in fam})), foot[0],
                              round(y_lo, 3), round(y_up, 3), tuple(opened), tuple(closed),
                              round(go, 3), round(gc, 3), (float(o.xy[0]), float(o.xy[1]))))
    return out, notes
