"""THE OPEN CHANNEL'S MEASUREMENTS (spec §45; owner RULINGS 2026-09-15i,
amended 2026-09-15s) — lane ``v2channel``.

Its own module beside ``planar/channel.py`` for that file's own
1,000-line budget, and for the same reason ``planar/structure_geometry``
stands beside ``planar/structures``: these are pure geometry readings
over a line, a DEM and a pavement union.  They decide nothing — the
record's law lives next door.

Two of them carry a measurement the round-1 arm paid for and the ruling
then wrote down.  :func:`_across` exists because ``LineString.project``
CLAMPS a point past either end, so a way that merely overhangs the axis
longitudinally reads its overhang as width: ``channel:2`` read a 404.7 m
half-corridor off two rail ways 17-24 m apart.  :func:`_span` returns
``None`` rather than the search radius, because returning the radius read
a 480 m half-corridor wherever the ray found no pavement edge.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from .structure_approach import unit

__all__ = ['_hole_region', '_runs', '_in_hole', '_across', '_spread_m', '_span', '_deck_ring', '_sides', '_lidar_floor', '_bank_width', '_walls_half', '_bank_toe_half', '_poly', '_parts']

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _dem(airport: Airport, p: XY) -> float:
    return float(airport.dem.z(p[0], p[1]))


def _hole_region(union):
    """THE HOLE IN THE AIRSIDE PAVEMENT (§45 (1) (b)) — the pavement
    union's own interiors: the filled outline LESS the pavement.

    This is what separates a CHANNEL from a service road that merely
    crosses a taxiway spur.  KDFW's corridor IS a hole — ``ring69`` of
    the single 339-node outer pavement, 2,518 m x ~1,150 m, with the four
    taxiway necks bridging it (scout `channelscout` §4a).  A road running
    OUTSIDE the field and crossing one taxiway leaves the pavement into
    open ground, not into a hole the airfield cut for it.  Measured at
    LGAV on the first arm: without this clause the neck test read five
    channels, four of them service roads."""
    if union is None:
        return None
    shells = []
    for g in getattr(union, "geoms", [union]):
        if g.geom_type != "Polygon":
            continue
        shells.append(Polygon(g.exterior))
    if not shells:
        return None
    filled = unary_union(shells)
    holes = filled.difference(union)
    return None if holes.is_empty else holes


def _runs(flags: _t.Sequence[bool]) -> list[tuple[bool, int, int]]:
    """``[(value, i0, i1)]`` — maximal runs of equal flags, i1 inclusive."""
    out: list[tuple[bool, int, int]] = []
    for i, f in enumerate(flags):
        if out and out[-1][0] == f:
            out[-1] = (f, out[-1][1], i)
        else:
            out.append((f, i, i))
    return out


def _in_hole(ln: LineString, ss: list[float], run, holes) -> bool:
    """Whether an UNPAVED run of a way lies inside the pavement's own
    hole (:func:`_hole_region`) — tested at the run's midpoint, which is
    the deepest point of the corridor beside the neck."""
    if holes is None:
        return False
    _v, i0, i1 = run
    p = ln.interpolate((ss[i0] + ss[i1]) / 2.0)
    return bool(holes.contains(Point(p.x, p.y)))


def _across(line: LineString, pts) -> float:
    """How far ``pts`` reach ACROSS ``line`` — the perpendicular offset of
    every point whose projection lands STRICTLY INSIDE the line, and 0.0
    where none does.

    The end clamp is the whole point.  ``LineString.project`` pins a point
    beyond either end to that end, so a way that merely OVERHANGS the axis
    longitudinally reads its overhang as lateral distance: round 1's
    ``channel:2`` read a **404.7 m** half-corridor that way, off two rail
    ways 17–24 m apart whose ends stick out past each other.  Only the
    OVERLAP measures a corridor's width."""
    out = 0.0
    L = line.length
    for p in pts:
        s = line.project(Point(p))
        if s <= 1e-6 or s >= L - 1e-6:
            continue
        q = line.interpolate(s)
        out = max(out, math.hypot(p[0] - q.x, p[1] - q.y))
    return out


def _spread_m(grp: list[_Cand], extra: _Cand | None = None) -> float:
    """§45 (11): how far the group's ways reach ACROSS its own axis — the
    longest member's line — counting ``extra`` if given."""
    members = list(grp) + ([extra] if extra is not None else [])
    lead = max(members, key=lambda c: c.line.length).line
    return max((_across(lead, c.line.coords) for c in members), default=0.0)


def _span(union, axis_fn, s: float, reach: float) -> float | None:
    """How far the pavement reaches ACROSS the axis at ``s``, on the
    NARROWER side — the neck's own across-axis extent, which §45 (1) (b)
    calls the deck's span.  ``None`` where the ray finds no pavement edge
    within ``reach``: the caller then keeps the carriageway width and
    never invents a span out of the search radius (the first arm returned
    ``reach`` and read a 480 m half-corridor at LGAV)."""
    if union is None:
        return None
    p = axis_fn(s)
    a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
    u = unit(a, b)
    nv = (-u[1], u[0])
    best: float | None = None
    for sgn in (1.0, -1.0):
        ray = LineString([p, (p[0] + nv[0] * sgn * reach, p[1] + nv[1] * sgn * reach)])
        x = ray.intersection(union.boundary)
        pts = [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]
        if not pts:
            return None
        d = min(math.hypot(g.x - p[0], g.y - p[1]) for g in pts)
        best = d if best is None else min(best, d)
    return None if best is None else max(1.0, best)


def _deck_ring(axis_fn, s0: float, s1: float, half: float) -> tuple[XY, ...]:
    left, right = _sides(axis_fn, [s0, s1], half)
    return tuple(left) + tuple(reversed(right))


def _sides(axis_fn, ss: _t.Sequence[float], half: float) -> tuple[list[XY], list[XY]]:
    left: list[XY] = []
    right: list[XY] = []
    for s in ss:
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        left.append((p[0] + nv[0] * half, p[1] + nv[1] * half))
        right.append((p[0] - nv[0] * half, p[1] - nv[1] * half))
    return left, right


def _lidar_floor(airport: Airport, axis_fn, s: float, window_m: float) -> float:
    """§45 (3) (ii): the DTM floor at one station — the MINIMUM across
    ``lidar_floor_window_m`` on the axis normal.  The bank toes stand
    inside the corridor (KDFW's run 1:4 over 35–45 m) and the floor is
    what lies between them, so a single centreline sample would read a
    bank wherever the carriageway is not the deepest line."""
    p = axis_fn(s)
    a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
    u = unit(a, b)
    nv = (-u[1], u[0])
    best = float("nan")
    k = max(2, int(window_m // 2.0))
    for i in range(-k, k + 1):
        t = i * (window_m / (2.0 * k))
        z = _dem(airport, (p[0] + nv[0] * t, p[1] + nv[1] * t))
        if math.isnan(z):
            continue
        best = z if math.isnan(best) else min(best, z)
    return best


def _bank_width(airport: Airport, axis_fn, ss, profile, slope: float, shape: str,
                grid: float) -> float:
    """The bank's PLAN run, one value for the channel (§45 (5)).

    ``"face"`` — a pack wall stands here and the bank hides behind it at
    the identity spacing (near-vertical AT the face, §24 (1)); ``"lidar"``
    / ``"bank"`` — ``(crest − floor) / bank_slope``, sized off the DEM so
    the mesh has room.  The crest's VALUE is never the DEM (§45 (5)); this
    is plan geometry only."""
    if shape == "face":
        return max(grid, 1.0)
    from ..model.structures import profile_z
    drops = []
    for s in ss:
        z = _dem(airport, axis_fn(s))
        if math.isnan(z):
            continue
        drops.append(max(0.0, z - profile_z(profile, s)))
    drop = max(drops) if drops else 0.0
    return max(grid, drop / max(slope, 1e-6))


def _walls_half(axis_ln: LineString, objects: _t.Sequence, ids: _t.Sequence[str]) -> float:
    """§45 (10) (i): how far the witnessing WALL OBJECTS' outer faces
    reach across the axis — their below-grade footprints' own extent, by
    the OVERLAP rule of :func:`_across`.  ``0.0`` where none states one."""
    want = set(ids or ())
    out = 0.0
    for o in objects or ():
        if str(getattr(o, "id", "")) not in want:
            continue
        bg = getattr(o, "below_grade", None)
        if bg is None or getattr(bg, "is_empty", True):
            continue
        for g in getattr(bg, "geoms", [bg]):
            if g.geom_type != "Polygon":
                continue
            out = max(out, _across(axis_ln, g.exterior.coords))
    return out


def _bank_toe_half(airport: Airport, law: Law, axis_fn, ss, cap: float) -> float:
    """§45 (10) (ii): the BANK TOES on the axis normal, where the inset is
    credible lidar — walk outward from the axis until the DTM comes back
    within the materiality floor of the crest (the toe), and take the
    MEDIAN station's toe so one bridge abutment does not set the width.

    KDFW is the site this exists for: 8.64-9.94 m of cut with banks at
    roughly 1:4, i.e. a toe 35-45 m out, against an apt.dat hole
    1,150 m wide."""
    tol = float(law.tables.emit.materiality.elevation_m)
    step = max(2.0, float(law.tables.structures.channel.station_m) / 5.0)
    toes: list[float] = []
    for s in ss:
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        z0 = _dem(airport, p)
        if math.isnan(z0):
            continue
        here = 0.0
        for sgn in (1.0, -1.0):
            t = step
            top = z0
            while t <= cap:
                z = _dem(airport, (p[0] + nv[0] * sgn * t, p[1] + nv[1] * sgn * t))
                if math.isnan(z):
                    break
                if z <= top + tol:
                    top = max(top, z)
                    t += step
                    continue
                top = z
                t += step
            here = max(here, min(t, cap))
        if here > 0.0:
            toes.append(here)
    if not toes:
        return 0.0
    toes.sort()
    return toes[len(toes) // 2]


def _poly(ring) -> Polygon | None:
    if not ring or len(ring) < 3:
        return None
    p = Polygon(list(ring))
    if not p.is_valid:
        p = p.buffer(0)
    if p.is_empty:
        return None
    if p.geom_type != "Polygon":
        parts = [g for g in p.geoms if g.geom_type == "Polygon"]
        if not parts:
            return None
        p = max(parts, key=lambda g: g.area)
    return p


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    import shapely
    return [g for g in shapely.get_parts(geom)
            if g.geom_type == "Polygon" and g.area > 1e-6]


