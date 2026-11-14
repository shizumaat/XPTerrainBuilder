"""THE SURVEYED UNDERPASS MOUTH (class K; #1939 round 2, spec
``docs/specs/1939-round2-spec.md`` R1 / R2 / R4; RULINGS 2026-11-13h N1).

CLASS K is a mapped group nothing pins -- no object corridor, portal, edge
bridge or hard deck -- whose every member bore is a §34 (5) underpass of ONE
aeroway deck (``structure_underpass.UNDERPASS_TAG``), not rail, and whose
credible survey reads the mouth KEPT (``lidar_road.survey_mouth``: the
survey already carries the road the owed depth under the cover).  Such a
mouth digs nothing; what decides it is WHERE the survey's covered extent
ends and what the survey's road is there.

R1 -- THE MOUTH LINE ON THE COVERED-EXTENT EDGE.  ``merge_duals`` puts one
SQUARE line (across the mean axis) at the outermost member end.  Under a
deck that crosses the roads at a skew (ESSA taxiway U's way -74 runs 31.4 deg
off square to the four carriageways, its kerb 32.2 deg, the survey's edge
32.7 deg) a square line through the outermost end slides 11 m out of the
taxiway's west part and stands 17 m beyond the bridge's edge on the far
side: the roads between are stubs held at deck level.  The covered extent
(kerb + graded strip, RULINGS 2026-09-15h) ends within ~0.5 m of the
survey's mid-face at both member ends placed, so the mouth line L runs
along the deck (direction ``e``) through the member end standing furthest
out of it (greatest ``m.xy . n_out``); the mouth moves to L's crossing of
the axis, and the ring is SHEARED onto it -- ``p -> p + u . sigma . ((p -
m0) . n)``, ``sigma = (e . u) / (e . n)`` -- so every lateral line of the
square ring becomes parallel to the deck.  The cap stands ``rim_off``
PERPENDICULAR behind the sheared mouth edge.  No shear (the square ring
stands) where the crossing is under ``structure_deck._DECK_MIN_ANGLE_DEG``
or where the shear moves the ring's far corner no more than ``wall_gap_m``.

R2 -- THE FLOOR IS THE SURVEY.  Each member's surveyed road is read on its
own line outward from L at its own width (``lidar_road.surveyed_road``) and
the floor along the mouth edge is the fit ``z0 + k . tau`` (``tau`` along
the edge from the axis): the cutting floor is a plane across the four
carriageways, not one level (ESSA south: 23.9-24.05 for the west lanes,
24.95 at the east, fit residual <= 0.27).

R4 -- NOTHING GROUNDSIDE AT GRADE UNDER THE DECK.  The band
:func:`under_deck_band` is the sheared corridor rim to rim from the cap line
inward for half the longest member bore: a groundside cell meeting both it
and the tunnel's ramp is cut by it (the road stubs the pavement's feet held
at deck level), a road along the deck never meets the ramp and is kept."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import substring

from ..law import Law
from ..model.frame import XY
from .lidar_road import KEPT, surveyed_road
from .structure_deck import _DECK_MIN_ANGLE_DEG
from .structure_geometry import RampGeometry, ring_for, snap_out
from .structure_underpass import UNDERPASS_TAG

__all__ = ["Skew", "k_deck_ref", "place_mouth", "ring_stations", "sheared_ring",
           "skewed_box", "member_roads", "survey_floor", "under_deck_band",
           "under_deck_blade"]

#: Plan step (m) a member's line is walked to find where it crosses L.
_WALK_M = 0.5
#: How far (m) a member's line is walked outward looking for L.
_WALK_MAX_M = 80.0


@_dc.dataclass(frozen=True)
class Skew:
    """R1's reading of a class-K mouth: ``m0`` the mouth on the axis (L's
    crossing), ``u`` outward along the axis, ``n`` its left normal, ``e`` the
    deck's direction along the mouth edge (``e . n > 0``), ``sigma`` the
    shear (0: the square ring stands), ``moved`` the metres the mouth moved
    OUT along the axis (negative: into the bore), ``deck`` the deck way's
    ref, ``anchor`` the member end L runs through."""

    m0: XY
    u: XY
    n: XY
    e: XY
    sigma: float
    moved: float
    deck: str
    anchor: XY

    @property
    def cos(self) -> float:
        """``|e . n|``: the perpendicular share of one metre along the axis."""
        return abs(self.e[0] * self.n[0] + self.e[1] * self.n[1])

    def back(self, d: float) -> float:
        """Metres along the axis that stand ``d`` PERPENDICULAR behind the
        sheared mouth edge."""
        return d if self.sigma == 0.0 else d / max(self.cos, 1e-6)

    def at(self, p: XY, origin: XY) -> XY:
        """``p`` sheared about ``origin`` (a point on the mouth edge)."""
        if self.sigma == 0.0:
            return (p[0], p[1])
        lat = (p[0] - origin[0]) * self.n[0] + (p[1] - origin[1]) * self.n[1]
        return (p[0] + self.u[0] * self.sigma * lat, p[1] + self.u[1] * self.sigma * lat)


def k_deck_ref(members: _t.Sequence, rail: bool, road_rd, *pins) -> str | None:
    """Class K's deck ref: the ONE ``UNDERPASS_TAG`` every member bore way
    carries, when nothing pins the group (``pins``: the corridor, portal,
    edge bridge and hard deck, all ``None``), it is not rail and the survey
    reads the mouth KEPT; else ``None``."""
    if rail or road_rd is None or road_rd.verdict != KEPT or not members \
            or any(p is not None for p in pins):
        return None
    ways = [w for m in members for w in (getattr(getattr(m, "bore", None), "ways", None) or ())]
    if not ways or any(not getattr(getattr(m, "bore", None), "ways", None) for m in members):
        return None
    refs = {(w.tags or {}).get(UNDERPASS_TAG) for w in ways}
    return None if None in refs or len(refs) != 1 else refs.pop()


def _unit(dx: float, dy: float) -> XY:
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _deck_dir(deck_pts: _t.Sequence[XY], mouth: XY, inward: XY) -> XY | None:
    """The deck way's unit direction where the bore's line crosses it (the
    point of the deck nearest the mouth where it does not)."""
    if len(deck_pts) < 2:
        return None
    deck = LineString(deck_pts)
    ray = LineString([mouth, (mouth[0] + inward[0] * 500.0, mouth[1] + inward[1] * 500.0)])
    x = deck.intersection(ray)
    pts = [g for g in getattr(x, "geoms", [x]) if not g.is_empty and g.geom_type == "Point"]
    at = min(pts, key=lambda g: g.distance(Point(mouth))) if pts else Point(mouth)
    s = deck.project(at)
    a = deck.interpolate(max(0.0, s - 1.0))
    b = deck.interpolate(min(deck.length, s + 1.0))
    if math.hypot(b.x - a.x, b.y - a.y) < 1e-6:
        return None
    return _unit(b.x - a.x, b.y - a.y)


def place_mouth(deck_pts: _t.Sequence[XY], deck_ref: str, members: _t.Sequence,
                axis: LineString, inward: XY, half: float, rim_off: float, law: Law
                ) -> tuple[Skew | None, LineString, str]:
    """R1: ``(skew, axis, note)`` -- the axis starting at the mouth on L's
    crossing (unchanged where the square ring stands); ``skew`` ``None``
    where the deck's direction cannot be read."""
    m = tuple(axis.coords[0])
    u = (-inward[0], -inward[1])
    n = (-u[1], u[0])
    e = _deck_dir(deck_pts, m, inward)
    if e is None:
        return None, axis, f"#1939 R1: deck {deck_ref} has no direction at the crossing"
    if e[0] * n[0] + e[1] * n[1] < 0.0:
        e = (-e[0], -e[1])
    en, eu = e[0] * n[0] + e[1] * n[1], e[0] * u[0] + e[1] * u[1]
    ang = math.degrees(math.asin(max(-1.0, min(1.0, en))))
    tn = law.tables.structures.tunnel
    sigma = eu / en if en > 1e-9 else math.inf
    width = 2.0 * (half + rim_off)
    if ang < _DECK_MIN_ANGLE_DEG or abs(sigma) * width <= tn.wall_gap_m:
        why = (f"crossing {ang:.1f} deg < {_DECK_MIN_ANGLE_DEG:.0f}" if ang < _DECK_MIN_ANGLE_DEG
               else f"skew {abs(sigma) * width:.2f} m over the ring <= wall_gap_m "
                    f"{tn.wall_gap_m}")
        return Skew((m[0], m[1]), u, n, e, 0.0, 0.0, deck_ref, (m[0], m[1])), axis, (
            f"#1939 R1: the square mouth stands under deck {deck_ref} ({why})")
    # n_out: the deck's normal out of the bore
    n_out = (-e[1], e[0])
    if n_out[0] * u[0] + n_out[1] * u[1] < 0.0:
        n_out = (-n_out[0], -n_out[1])
    anchor = max((tuple(mb.xy) for mb in members),
                 key=lambda p: p[0] * n_out[0] + p[1] * n_out[1])
    # L ∩ axis: m + t u with (m + t u - anchor) . n_out = 0
    t = ((anchor[0] - m[0]) * n_out[0] + (anchor[1] - m[1]) * n_out[1]) / (
        u[0] * n_out[0] + u[1] * n_out[1])
    new = _station_axis(axis, inward, t)
    m0 = tuple(new.coords[0])
    return Skew((m0[0], m0[1]), u, n, e, sigma, t, deck_ref, (anchor[0], anchor[1])), new, (
        f"#1939 R1: mouth on the covered-extent edge along deck {deck_ref} "
        f"({ang:.1f} deg crossing, shear {sigma:+.3f}), through the member end; "
        f"{'out' if t >= 0.0 else 'in'} {abs(t):.1f} m along the axis")


def _station_axis(axis: LineString, inward: XY, t: float) -> LineString:
    """``axis`` starting ``t`` m out along itself (``t < 0``: into the bore,
    along ``inward``)."""
    if t >= 0.0:
        return substring(axis, min(t, axis.length - 1e-3), axis.length)
    m = axis.coords[0]
    return LineString([(m[0] - inward[0] * t, m[1] - inward[1] * t)] + list(axis.coords))


def ring_stations(law: Law, dem, spacing: float) -> list[float]:
    """R1: the ring's two stations ``[0, R]``, ``R`` the larger of the
    station spacing and ``[bridge] ground_probe_dem_cells`` DEM postings
    rounded to the identity grid (12 m at ESSA)."""
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    post = getattr(dem, "posting_m", None)
    cell = post() if callable(post) else None
    probe = float(law.tables.structures.bridge.ground_probe_dem_cells) * float(cell or 0.0)
    return [0.0, max(float(spacing), round(probe / grid) * grid)]


def _perp(edge: LineString, p: XY) -> float:
    """The perpendicular distance of ``p`` from ``edge``'s infinite line."""
    (x0, y0), (x1, y1) = edge.coords[0], edge.coords[-1]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    return abs((p[0] - x0) * (y1 - y0) - (p[1] - y0) * (x1 - x0)) / L


def _shear_geometry(g: RampGeometry, sk: Skew, rim_off: float, grid: float
                   ) -> RampGeometry | None:
    """``g`` sheared onto the mouth edge (every field), snapped to the grid
    away from the axis, its cap pushed until it stands ``rim_off``
    perpendicular behind the mouth edge; ``None`` where the snap folds or
    thins the void (the stop, never retried)."""
    if sk.sigma == 0.0:
        return g
    o = g.axis[0]

    def sh(p: XY, base: XY) -> XY:
        return snap_out(sk.at(p, o), sk.at(base, o), grid)
    axis = [sk.at(p, o) for p in g.axis]
    left = [sh(p, a) for p, a in zip(g.left, g.axis, strict=False)]
    right = [sh(p, a) for p, a in zip(g.right, g.axis, strict=False)]
    left_rim = [sh(p, a) for p, a in zip(g.left_rim, g.left, strict=False)]
    right_rim = [sh(p, a) for p, a in zip(g.right_rim, g.right, strict=False)]
    edge = LineString([left[0], right[0]])
    inward = (-sk.u[0], -sk.u[1])

    def behind(p: XY) -> XY:
        q = p
        for _k in range(8):
            if _perp(edge, q) >= rim_off - 1e-6:
                return q
            q = snap_out((q[0] + inward[0] * grid, q[1] + inward[1] * grid), q, grid)
        return q
    cap_out = [behind(sh(p, axis[0])) for p in g.cap_out]
    far_out = [sh(p, axis[-1]) for p in g.far_out]
    nrm = []
    for v in g.normals:
        lat = v[0] * sk.n[0] + v[1] * sk.n[1]
        nrm.append(_unit(v[0] + sk.u[0] * sk.sigma * lat, v[1] + sk.u[1] * sk.sigma * lat))
    ramp = Polygon(left + list(reversed(right)))
    outer = Polygon(list(reversed(left_rim)) + cap_out + right_rim + far_out)
    if not ramp.is_valid or ramp.area < 1.0 or not outer.is_valid:
        return None
    wall = outer.difference(ramp)        # (``structure_geometry._geometry_at``'s test)
    if wall.geom_type == "MultiPolygon":
        parts = [w for w in wall.geoms if w.area > 1e-6]
        wall = parts[0] if len(parts) == 1 else MultiPolygon(parts)
    if wall.is_empty or not wall.is_valid:
        return None
    ex = ramp.exterior
    lines = [LineString(left_rim), LineString(right_rim)] + (
        [LineString(cap_out)] if len(cap_out) >= 2 else [])
    if any(ex.distance(ln) < rim_off - 1e-6 for ln in lines) or \
            any(_perp(edge, q) < rim_off - 1e-6 for q in cap_out):
        return None
    return _dc.replace(g, axis=axis, normals=nrm, left=left, right=right, ramp=ramp,
                       wall=wall, outer=outer, cap_in=[sk.at(p, o) for p in g.cap_in],
                       cap_out=cap_out, far_in=[sk.at(p, o) for p in g.far_in],
                       far_out=far_out, left_rim=left_rim, right_rim=right_rim)


def sheared_ring(sk: Skew | None, c, axis_fn, ss: list[float], half: float, rim_off: float,
                 inward: XY, grid: float, g, half_fn=None) -> RampGeometry | None:
    """``structure_geometry.ring_for`` with R1's shear: the square ring is
    built with its cap ``Skew.back(rim_off)`` behind the mouth line, then
    sheared (:func:`_shear_geometry`).  ``sk`` ``None`` (or no shear): the
    square ring, unchanged."""
    if sk is None or sk.sigma == 0.0:
        return ring_for(c, axis_fn, ss, half, rim_off, inward, grid, g, half_fn)
    gm = ring_for(c, axis_fn, ss, half, rim_off, inward, grid,
                  _dc.replace(g, cap_off=sk.back(rim_off)), half_fn)
    return None if gm is None else _shear_geometry(gm, sk, rim_off, grid)


def skewed_box(seg: LineString, s_pt: XY, half: float, rim_off: float, sk: Skew) -> Polygon:
    """``structure_mouth.clear_mouth``'s necessary-test rectangle for a
    sheared ring: ``seg`` (starting ``rim_off`` behind the mouth point
    ``s_pt``) pushed back to ``Skew.back(rim_off)`` behind it, buffered and
    sheared about ``s_pt``."""
    extra = sk.back(rim_off) - rim_off
    if extra > 0.0:
        (x0, y0), (x1, y1) = seg.coords[0], seg.coords[1]
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        seg = LineString([(x0 - (x1 - x0) / L * extra, y0 - (y1 - y0) / L * extra),
                          *seg.coords])
    box = seg.buffer(half + rim_off, cap_style="flat")
    return Polygon([sk.at(p, s_pt) for p in box.exterior.coords])


def member_roads(airport, sk: Skew, members: _t.Sequence) -> list[tuple[float, float]]:
    """R1 / R2's ALIGNED survey reading: ``(tau, z)`` per member -- its
    surveyed road (``lidar_road.surveyed_road``, the same 12 m reach) read on
    its OWN line outward from L at its own width, ``tau`` where that line
    crosses L, along ``Skew.e`` from ``Skew.m0``.  The square window from the
    axis point reads the smeared face on one side of a skewed mouth line
    (ESSA south: 24.27 against the members' 23.95-24.78)."""
    n_out = (-sk.e[1], sk.e[0])
    if n_out[0] * sk.u[0] + n_out[1] * sk.u[1] < 0.0:
        n_out = (-n_out[0], -n_out[1])
    pts: list[tuple[float, float]] = []
    for mb in members:
        path = [tuple(mb.xy)] + [tuple(p) for p in (getattr(mb, "approach", ()) or ())
                                 if math.dist(tuple(p), tuple(mb.xy)) > 1e-6]
        if len(path) < 2:
            continue
        ln = LineString(path)
        s_l = _crossing(ln, sk.anchor, n_out)
        if s_l is None:
            continue

        def fn(s: float, _ln=ln, _s0=s_l) -> XY:
            q = _ln.interpolate(min(_s0 + s, _ln.length))
            return (q.x, q.y)
        z = surveyed_road(airport, fn, float(getattr(mb, "width_m", 0.0) or 0.0))
        if math.isnan(z):
            continue
        q = fn(0.0)
        pts.append(((q[0] - sk.m0[0]) * sk.e[0] + (q[1] - sk.m0[1]) * sk.e[1], z))
    return pts


def survey_floor(pts: _t.Sequence[tuple[float, float]]) -> tuple[float, float, str] | None:
    """R2: ``(z0, k, note)`` -- the floor along the mouth edge ``z0 + k .
    tau``, the least-squares fit to :func:`member_roads`' ``(tau, z)``
    reads; ``None`` where there are none."""
    if not pts:
        return None
    ts = [t for t, _z in pts]
    if len(pts) == 1 or max(ts) - min(ts) < 1.0:
        z0, k = sum(z for _t, z in pts) / len(pts), 0.0
    else:
        mt = sum(ts) / len(pts)
        mz = sum(z for _t, z in pts) / len(pts)
        k = sum((t - mt) * (z - mz) for t, z in pts) / sum((t - mt) ** 2 for t in ts)
        z0 = mz - k * mt
    res = max(abs(z - (z0 + k * t)) for t, z in pts)
    return z0, k, (f"#1939 R2: floor = the survey along the mouth edge, {z0:.2f} "
                   f"{k:+.4f}/m from the axis, fitted to {len(pts)} member road(s) "
                   f"({', '.join(f'{z:.2f} at {t:+.1f} m' for t, z in sorted(pts))}; "
                   f"residual {res:.2f} m)")


def _crossing(ln: LineString, anchor: XY, n_out: XY) -> float | None:
    """The first station along ``ln`` standing on or beyond L (through
    ``anchor``, normal ``n_out``)."""
    s = 0.0
    while s <= min(ln.length, _WALK_MAX_M) + 1e-9:
        q = ln.interpolate(s)
        if (q.x - anchor[0]) * n_out[0] + (q.y - anchor[1]) * n_out[1] >= -1e-6:
            return s
        s += _WALK_M
    return None


def under_deck_band(cap_out: _t.Sequence[XY], inward: XY, members: _t.Sequence
                    ) -> Polygon | None:
    """R4's band B: the sheared cap line (the cap polyline, corner to
    corner) swept inward for half the longest member bore."""
    if len(cap_out) < 2:
        return None
    reach = 0.5 * max((LineString(m.bore.points).length for m in members
                       if len(getattr(getattr(m, "bore", None), "points", ()) or ()) >= 2),
                      default=0.0)
    if reach <= 0.0:
        return None
    # the cap polyline itself is B's edge (its centre need not be on the
    # corners' chord: a sliver of road would stand between them)
    back = [(p[0] + inward[0] * reach, p[1] + inward[1] * reach) for p in reversed(cap_out)]
    poly = Polygon(list(cap_out) + back)
    return poly if poly.is_valid and poly.area > 1.0 else None


def under_deck_blade(c, p: Polygon, law: Law, bands: _t.Sequence[tuple[Polygon, Polygon]]):
    """R4: the bands B (:func:`under_deck_band`, each with its tunnel's ramp)
    that cut cell ``c`` (polygon ``p``) -- a groundside value cell, never a
    building or a structure, meeting both B and that ramp; ``None`` when
    none does."""
    from shapely.ops import unary_union

    from ..law.tables import is_structure_role, is_value_role, role_side
    if not bands or c.role == "building" or role_side(law, c.role) == "airside" \
            or not is_value_role(law, c.role) or is_structure_role(law, c.role):
        return None
    hit = [b for b, ramp in bands if p.intersects(b) and p.intersects(ramp)]
    return unary_union(hit) if hit else None
