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

__all__ = ['_hole_region', '_field_region', '_runs', '_in_hole', '_across', '_spread_m', '_span', '_deck_ring', '_sides', '_lidar_floor', '_bank_width', '_walls_half', '_bank_toe_half', '_poly', '_parts', '_ends', '_witness_along', '_lidar_cut']

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _dem(airport: Airport, p: XY) -> float:
    return float(airport.dem.z(p[0], p[1]))


def _hole_region(union, field=None):
    """THE UNPAVED CORRIDOR OF §45 (1) (b) — the complement of the
    AIRSIDE PAVEMENT UNION **inside the field** (spec §45 (14), owner
    RULINGS 2026-09-15bk).

    A NOTCH AND A HOLE ARE ONE CLASS.  The first reading was the union's
    own INTERIORS (the filled outline less the pavement), which sees a
    corridor only where the airfield closes around it.  KDFW's does
    (``ring69`` of the 339-node outer, 2,518 x ~1,150 m).  KPHX's does
    NOT: E Sky Harbor Blvd runs in from the edge, so the corridor is an
    INDENTATION of the outer boundary, ``holes`` was empty and every
    candidate read ``necks = 0`` — no channel at a site with two taxiway
    decks over it (round 6 measurement).  So the region is the field
    MINUS the pavement, and ``field`` is:

    * the apt.dat row-130 boundary where one exists (``Airport.
      boundaries``, §44 (3)'s own borrow rule already applied at load —
      never re-derived here), else
    * the union's convex hull grown by ``[tunnel] mouth_standoff_m``, the
      same "how far off the pavement is still the field" length §29 (1)
      uses.

    The interiors are a SUBSET of this (a hole is complement-inside-field
    too), so KDFW, LGAV and LEMD read exactly what they read before.
    ``field = None`` falls back to the interiors alone — the fixtures
    that state no boundary and no hull."""
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
    region = filled if field is None else unary_union([filled, field])
    holes = region.difference(union)
    return None if holes.is_empty else holes


def _field_region(airport, union, law):
    """§45 (14)'s FIELD: the row-130 boundary, else the pavement union's
    convex hull ⊕ ``[tunnel] mouth_standoff_m``.  ``None`` when there is
    no union to grow and no boundary to read."""
    rings = []
    for b in (getattr(airport, "boundaries", ()) or ()):
        try:
            poly = Polygon(b.outer, [h for h in (b.holes or ()) if len(h) >= 3])
        except Exception:                      # pragma: no cover - fixture rings
            continue
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty:
            rings.append(poly)
    if rings:
        return unary_union(rings)
    if union is None or getattr(union, "is_empty", True):
        return None
    grow = float(law.tables.structures.tunnel.mouth_standoff_m)
    return union.convex_hull.buffer(grow, **_MITRE)


def _runs(flags: _t.Sequence[bool]) -> list[tuple[bool, int, int]]:
    """``[(value, i0, i1)]`` — maximal runs of equal flags, i1 inclusive."""
    out: list[tuple[bool, int, int]] = []
    for i, f in enumerate(flags):
        if out and out[-1][0] == f:
            out[-1] = (f, out[-1][1], i)
        else:
            out.append((f, i, i))
    return out


def _in_hole(ln: LineString, ss: list[float], run, holes, notch=None,
             union=None, cap: float = 0.0, near_s: float | None = None) -> bool:
    """Whether an UNPAVED run of a way lies inside the CORRIDOR of §45
    (1) (b) — tested at the run's midpoint, which is the deepest point of
    the corridor beside the neck.

    TWO READINGS, ONE CLASS (§45 (14), owner RULINGS 2026-09-15bk).
    ``holes`` is the pavement union's own INTERIOR rings, a corridor the
    airfield closes around (KDFW's ``ring69``); ``notch`` is the
    complement INSIDE THE FIELD, which also carries the INDENTATIONS of
    the outer boundary (KPHX's E Sky Harbor Blvd, which runs in from the
    edge, leaves ``holes`` empty and read ``necks = 0``).

    A NOTCH IS A CORRIDOR ONLY WHERE IT IS ONE.  The field complement is
    everything unpaved, so on its own it reads every road that crosses a
    taxiway as a channel: measured on the round-8 arm (the seven dry
    replays), LEMD 3 -> 6, HECA 0 -> 3, CYXY 0 -> 1, LGAV 1 -> 4, all of
    them 7.0 m half-width roads with two decks, over open field.  The
    word §45 (1) (b) uses is CORRIDOR, so a notch run qualifies only
    where the pavement stands ON BOTH SIDES of it across the way within
    ``corridor_max_half_width_m`` — which is what an indentation IS, and
    what KPHX's corridor between Terminals 3 and 4 measures.  An interior
    hole is flanked by construction and takes this test as read, so every
    site that had a hole reads exactly what it read before (14)."""
    _v, i0, i1 = run
    s_mid = (ss[i0] + ss[i1]) / 2.0
    p = ln.interpolate(s_mid)
    if holes is not None and holes.contains(Point(p.x, p.y)):
        return True
    # THE FLANK IS READ BESIDE THE NECK (§45 (14): "an unpaved flank of
    # ``corridor_min_length_m`` on both sides of a paved neck, ALONG THE
    # WAY").  The interior-hole reading above keeps its midpoint — every
    # site that has a hole must read what it read before — but a NOTCH
    # flank is often the rest of the road: at KPHX the west flank of the
    # first neck is 1,300 m long and its midpoint stands 700 m off the
    # field, where no pavement is within the cap and the corridor test
    # answers "not a corridor" about a place the neck never touches.
    s_at = s_mid if near_s is None else min(max(near_s, ss[i0]), ss[i1])
    q = ln.interpolate(s_at)
    if notch is None or union is None or not notch.contains(Point(q.x, q.y)):
        return False

    def _at(s: float) -> XY:
        r = ln.interpolate(min(max(s, 0.0), ln.length))
        return (r.x, r.y)

    return _span(union, _at, s_at, cap) is not None


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


def _lidar_cut(airport: Airport, law: Law, axis_fn, ss, cap: float) -> bool:
    """§45 (3) (ii)/(7): whether a CREDIBLE lidar inset actually READS THE
    CUT along this corridor — the ground rising ``[channel]
    object_min_depth_m`` above the DTM floor on BOTH SIDES of the axis
    within ``corridor_max_half_width_m``, at a majority of the stations.

    A credible inset is not by itself a depth witness.  §45 (7) states it
    the other way round — "Where the DEM DOES see the cut (KDFW) it is the
    floor witness (3) (ii)" — and the round-8 arm measured what dropping
    the condition costs: at CYXY, KCLT and KPHX, whose insets are credible
    lidar over ordinary sloping or flat ground, ``_bank_toe_half`` walked
    out to the cap (120 m) and the floor took the DTM's own surface, so a
    road crossing a taxiway became a 120 m channel on a "depth witness"
    that §45 (12)'s ``min_decks_without_depth`` then never got to test.

    BOTH SIDES is what separates a cut from a hillside: on a slope the
    uphill side rises and the downhill side falls, and only a channel has
    ground standing above its floor to left AND right."""
    ch = law.tables.structures.channel
    depth = float(ch.object_min_depth_m)
    window = float(ch.lidar_floor_window_m)
    step = max(2.0, float(ch.station_m) / 2.0)
    seen = cut = 0
    for s in ss:
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        flr = _lidar_floor(airport, axis_fn, s, window)
        if math.isnan(flr):
            continue
        rises = []
        for sgn in (1.0, -1.0):
            top = float("nan")
            t = step
            while t <= cap:
                z = _dem(airport, (p[0] + nv[0] * sgn * t, p[1] + nv[1] * sgn * t))
                if not math.isnan(z):
                    top = z if math.isnan(top) else max(top, z)
                t += step
            rises.append(-1.0 if math.isnan(top) else top - flr)
        seen += 1
        if min(rises) >= depth:
            cut += 1
    return bool(seen) and cut * 2 >= seen


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


def _witness_along(axis_ln: LineString, objects: _t.Sequence,
                   ids: _t.Sequence[str]) -> tuple[float, float] | None:
    """How far the witnessing pack walls' BELOW-GRADE footprints reach
    ALONG the axis — ``(s_min, s_max)``, or ``None`` where none states
    one.  §45 (16)'s "extended by a depth witness" for (1) (c)."""
    want = set(ids or ())
    lo: float | None = None
    hi: float | None = None
    for o in objects or ():
        if str(getattr(o, "id", "")) not in want:
            continue
        bg = getattr(o, "below_grade", None)
        if bg is None or getattr(bg, "is_empty", True):
            continue
        for g in getattr(bg, "geoms", [bg]):
            if g.geom_type != "Polygon":
                continue
            for p in g.exterior.coords:
                s = axis_ln.project(Point(p))
                lo = s if lo is None else min(lo, s)
                hi = s if hi is None else max(hi, s)
    return None if lo is None else (float(lo), float(hi))


def _ends(airport: Airport, law: Law, decks, axis_ln: LineString, axis_fn,
          half_at: float, objects: _t.Sequence, packs: _t.Sequence[str],
          lidar: bool) -> tuple[float, float]:
    """§45 (16) A CHANNEL ENDS AT ITS OUTERMOST CROSSINGS (Fable
    2026-09-16; owner RULINGS 2026-09-15bo).

    §45 (2)'s ends — "where the corridor leaves the airside pavement
    union ⊕ ``mouth_standoff_m``" — were written for a HOLE, whose road
    leaves the pavement at the hole's own two edges.  A NOTCH has no such
    exit, and (14) wired with those ends ran corridors to the field
    boundary: KPHX 5,750 m, HECA 14,562 m, CYXY 5,646 m (round 7).

    So the ends are the corridor's OUTERMOST CROSSINGS — the decks of
    (1) (a)/(b) — each extended by ONE DECK WIDTH along the axis, and
    where a DEPTH WITNESS reaches further along the way, to the end of
    that witness: the pack walls' below-grade footprints (1) (c), or the
    stations a credible lidar still reads as cut (3) (ii).  Beyond them
    §37 governs as before."""
    ch = law.tables.structures.channel
    first = min(decks, key=lambda d: d.s0)
    last = max(decks, key=lambda d: d.s1)
    lo = first.s0 - (first.s1 - first.s0)
    hi = last.s1 + (last.s1 - last.s0)
    span = _witness_along(axis_ln, objects, packs)
    if span is not None:
        lo, hi = min(lo, span[0]), max(hi, span[1])
    elif lidar:
        # the lidar's own reach: walk outward while the DTM still reads a
        # cut of ``object_min_depth_m`` under the ground at the corridor
        # edge (the same "is this a real wall" depth (1) (c) uses)
        step = float(ch.station_m)
        depth = float(ch.object_min_depth_m)
        window = float(ch.lidar_floor_window_m)
        for sgn, start in ((-1.0, lo), (1.0, hi)):
            s = start
            while 0.0 <= s + sgn * step <= axis_ln.length:
                t = s + sgn * step
                p = axis_fn(t)
                a, b = axis_fn(max(0.0, t - 1.0)), axis_fn(t + 1.0)
                u = unit(a, b)
                nv = (-u[1], u[0])
                rim = max(_dem(airport, (p[0] + nv[0] * half_at, p[1] + nv[1] * half_at)),
                          _dem(airport, (p[0] - nv[0] * half_at, p[1] - nv[1] * half_at)))
                flr = _lidar_floor(airport, axis_fn, t, window)
                if math.isnan(rim) or math.isnan(flr) or (rim - flr) < depth:
                    break
                s = t
            if sgn < 0.0:
                lo = min(lo, s)
            else:
                hi = max(hi, s)
    return (max(0.0, float(lo)), min(axis_ln.length, float(hi)))


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


