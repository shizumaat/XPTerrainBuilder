"""THE TWO SIDES OF A RETAINING WALL (issue #1633 round 3; owner RULINGS
2026-10-28t Q268 / Q269 (a), 2026-10-15a (2) "the wall is the step").

A pack wall that retains its own height (``airport/wall_class``,
``retains``) is the step between two levels, and nothing on one level is
ever answered, merged or graded from the other.  This module is the ONE
reading of a retaining wall's two sides that every reader shares:

* :func:`wall_faces` — the wall's two long faces: its footprint ring split
  at its two END edges (the pair of short edges that halves the ring);
* :class:`WallSides` — per retaining piece: the footprint, the band
  ``smear`` wide beside each face (single-sided, so a bent wall's inside
  is the face's own, never both), which face is the UPPER one (the
  median ground ``smear`` out on it stands over the other's), the lidar
  ``smear`` (``max(3 m, h)``, the witness's ring: ``constraints/
  wall_zone``) and the object's extent above its own zero (``top_y``);
* :func:`far_side_cut` — a road-family face cut back at the wall: the
  footprint out, and the band of the face the road is NOT on (the side
  holding less of it) out — a road is never on both sides of a wall
  (KATL ``muro_27R.obj``: the §47 extension and the corridor's slivers put
  a ``service_road`` face 2-10 m beyond the wall's back, answered by the
  foot road 13 m below);
* :func:`crosses_wall` — a segment touches a footprint (a way never answers
  a vertex across the wall; two ways across it are never one carriageway);
* :func:`smear_sampler` — the DEM read past the smear beside a wall: the
  lidar reads part of the step within ``smear`` of the footprint, so a
  station there reads the ground ``smear`` out along its own perpendicular,
  on its own side (the lower of the two on the lower side, the higher on
  the upper — ``constraints/wall_zone.foot_ground``'s rule, mirrored);
* :func:`top_z` — the wall's TOP as seated (owner option (a), #1633 spec
  §3 (1)): the lower level plus the object's extent above its zero, never
  over the upper ground past the smear.

Derived once beside :attr:`Airport.wall_shade` (``airport/wall_shade``)
and carried as :attr:`Airport.retaining_walls`."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union

from ..model.wall_reach import BEHIND_SHARE, wall_reach_m, wall_smear_m

__all__ = ["WallSides", "wall_faces", "wall_sides", "far_side_cut",
           "crosses_wall", "smear_sampler", "top_z", "band_setbacks"]


@_dc.dataclass(frozen=True)
class WallSides:
    """One retaining piece read as two levels (module doc)."""

    poly: Polygon
    #: the height it retains (``WallComponent.retained_m``)
    height_m: float
    #: how far the lidar smears its step on either side: ``max(3 m, h)``
    smear: float
    #: the band ``smear`` wide beside the upper / the lower face
    upper: _t.Any
    lower: _t.Any
    #: the object's extent above its own zero, ``None`` when not read
    top_y: float | None = None
    resource: str = ""
    #: the footprint shrunk by the identity grid's half metre (at most a
    #: quarter of its width): a segment ACROSS the wall reaches it, a kerb
    #: vertex standing on the face (snapped a little in) does not
    core: _t.Any = None
    #: the UPPER face line (``wall_faces``), outward on its right
    upper_face: _t.Any = None

    def side_of(self, xy) -> str | None:
        """``"upper"`` / ``"lower"`` for a point in one of the bands, else
        ``None`` (in the footprint, past an end, or farther out)."""
        p = Point(xy)
        if self.upper is not None and self.upper.covers(p):
            return "upper"
        if self.lower is not None and self.lower.covers(p):
            return "lower"
        return None


def wall_faces(poly: Polygon) -> tuple[LineString, LineString] | None:
    """The two long faces of a thin footprint: its ring split at the pair
    of edges no longer than a few widths that halves it best (the ends),
    each face oriented with the footprint on its LEFT.  ``None`` for a
    footprint with no such pair (not thin)."""
    if poly is None or poly.is_empty or poly.geom_type != "Polygon" or poly.length <= 0:
        return None
    g = orient(poly, 1.0)
    cs = list(g.exterior.coords)[:-1]
    n = len(cs)
    if n < 4:
        return None
    wide = 2.0 * g.area / g.length
    lens = [math.dist(cs[i], cs[(i + 1) % n]) for i in range(n)]
    short = [i for i in range(n) if lens[i] <= max(3.0 * wide, wide + 2.0)]
    total = sum(lens)
    best = None
    for a in range(len(short)):
        for b in range(a + 1, len(short)):
            i, j = short[a], short[b]
            if j - i < 2 or (i + n) - j < 2:
                continue
            c1 = sum(lens[i + 1:j])
            c2 = total - c1 - lens[i] - lens[j]
            score = abs(c1 - c2) + lens[i] + lens[j]
            if best is None or score < best[0]:
                best = (score, i, j)
    if best is None:
        return None
    _s, i, j = best
    one = [cs[k % n] for k in range(i + 1, j + 1)]
    two = [cs[k % n] for k in range(j + 1, i + n + 1)]
    if len(one) < 2 or len(two) < 2:
        return None
    return LineString(one), LineString(two)


def _face_band(face: LineString, poly: Polygon, width: float):
    """The band ``width`` wide on the OUTER side of ``face`` (the footprint
    lies on its left, so outward is its right)."""
    band = face.buffer(-width, single_sided=True, join_style="mitre", mitre_limit=2.0)
    band = band if band.is_valid else band.buffer(0.0)
    return band.difference(poly)


def _median_ground(dem, face: LineString, out_m: float) -> float:
    """The median DEM ``out_m`` outside ``face`` (every 2 m along it)."""
    from .dem import dem_z_many
    off = face.offset_curve(-out_m, join_style="mitre", mitre_limit=2.0)
    lines = [ln for ln in getattr(off, "geoms", [off]) if ln.length > 0.0]
    pts = [ln.interpolate(float(t)).coords[0] for ln in lines
           for t in np.arange(0.0, ln.length + 1e-9, 2.0)]
    if not pts:
        return math.nan
    a = np.asarray(pts, float)
    z = dem_z_many(dem, a[:, 0], a[:, 1])
    z = z[np.isfinite(z)]
    return float(np.median(z)) if z.size else math.nan


def wall_sides(airport, cfg, comps=None) -> tuple[WallSides, ...]:
    """Every retaining piece of ``airport``'s pack walls (``wall_class``,
    ``retains``, its retained step over ``[service] retaining_wall_clear_
    step_m``) read as two levels.  ``cfg`` is ``classify/rules.toml``'s
    ``[service]`` record, supplied by the caller; ``comps`` the wall-class
    components when the caller has them."""
    dem = getattr(airport, "dem", None)
    if cfg is None or dem is None or getattr(airport, "partition", None) is None:
        return ()
    if comps is None:
        from .wall_class import wall_class_components
        comps = wall_class_components(airport, cfg)
    clear = float(getattr(cfg, "retaining_wall_clear_step_m", 0.0) or 0.0)
    out = []
    for w in comps:
        h = float(w.retained_m or w.height_m)
        if not w.retains or h <= clear:
            continue
        smear = wall_smear_m(h)
        for g in w.pieces:
            faces = wall_faces(g)
            if faces is None:
                continue
            a, b = (_face_band(f, g, smear) for f in faces)
            za, zb = (_median_ground(dem, f, smear) for f in faces)
            if not (math.isfinite(za) and math.isfinite(zb)):
                continue
            both = a.intersection(b)
            if not both.is_empty:
                a, b = a.difference(both), b.difference(both)
            up, lo = (a, b) if za >= zb else (b, a)
            wide = 2.0 * g.area / g.length
            core = g.buffer(-min(0.5, wide / 4.0))
            out.append(WallSides(g, h, smear, up, lo, w.top_y, w.resource,
                                 None if core.is_empty else core,
                                 faces[0] if za >= zb else faces[1]))
    return tuple(out)


def far_side_cut(geom, walls: _t.Sequence[WallSides], judge=None, grow_m: float = 0.0):
    """``geom`` cut back at every wall it reaches: the footprint (grown by
    ``grow_m``, the identity snap's margin, so no snapped vertex lands in
    it) out and the band of the face ``judge`` (default ``geom`` itself)
    holds LESS of out — the road is on one side of a wall.  ``geom``
    itself when no wall reaches it."""
    if geom is None or geom.is_empty or not walls:
        return geom
    judge = geom if judge is None else judge
    for w in walls:
        if not geom.intersects(w.poly.buffer(w.smear)):
            continue
        up = judge.intersection(w.upper).area if w.upper is not None else 0.0
        lo = judge.intersection(w.lower).area if w.lower is not None else 0.0
        cut = [w.poly.buffer(grow_m, join_style="mitre") if grow_m > 0.0 else w.poly]
        if up > 0.0 or lo > 0.0:
            cut.append(w.upper if up < lo else w.lower)
        geom = geom.difference(unary_union(cut))
    return geom


def crosses_wall(a, b, walls: _t.Sequence[WallSides]) -> bool:
    """The segment ``a``-``b`` runs ACROSS (or into) a wall: it reaches the
    footprint's core (:attr:`WallSides.core`) — a vertex on the wall's face
    and its own side's way never do."""
    if not walls:
        return False
    seg = LineString([tuple(a), tuple(b)]) if math.dist(a, b) > 1e-9 else Point(a)
    x0, y0, x1, y1 = seg.bounds
    for w in walls:
        if w.core is None:
            continue
        bx0, by0, bx1, by1 = w.core.bounds
        if x0 > bx1 or x1 < bx0 or y0 > by1 or y1 < by0:
            continue
        if seg.intersects(w.core):
            return True
    return False


def smear_sampler(sample: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                  walls: _t.Sequence[WallSides]):
    """``sample`` read past the smear (module doc): a point within a wall's
    ``smear`` of its footprint, in one of its side bands, reads also the
    ground ``smear`` out along its own perpendicular from the wall and
    takes the lower of the two on the lower side, the higher on the upper.
    ``sample`` itself where no wall stands."""
    if not walls:
        return sample
    boxes = np.array([w.poly.buffer(w.smear).bounds for w in walls], float)

    def _sample(xs, ys):
        xs = np.asarray(xs, float)
        ys = np.asarray(ys, float)
        z = np.array(sample(xs, ys), dtype=float)
        for k, w in enumerate(walls):
            x0, y0, x1, y1 = boxes[k]
            idx = np.flatnonzero((xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1))
            fix, at = [], []
            for i in idx:
                p = Point(float(xs[i]), float(ys[i]))
                side = w.side_of((p.x, p.y))
                if side is None:
                    continue
                q = nearest_points(w.poly, p)[0]
                d = math.hypot(p.x - q.x, p.y - q.y)
                if d <= 1e-6 or d >= w.smear:
                    continue
                f = w.smear / d
                fix.append((int(i), side))
                at.append((q.x + (p.x - q.x) * f, q.y + (p.y - q.y) * f))
            if not fix:
                continue
            a = np.asarray(at, float)
            past = np.asarray(sample(a[:, 0], a[:, 1]), dtype=float)
            for (i, side), zp in zip(fix, past):
                if np.isfinite(zp):
                    z[i] = min(z[i], zp) if side == "lower" else max(z[i], zp)
        return z
    return _sample


def top_z(w: WallSides, lower_z: float, upper_z: float) -> float:
    """THE WALL'S TOP AS SEATED (owner option (a), spec §3 (1)): the lower
    level ``lower_z`` plus the object's extent above its zero, never over
    the upper ground past the smear ``upper_z``; the upper ground where the
    extent is not read."""
    if w.top_y is None:
        return float(upper_z)
    return float(min(upper_z, lower_z + w.top_y))


def band_setbacks(walls: _t.Sequence[WallSides]) -> tuple[tuple, ...]:
    """THE BAND STOPS SHORT OF THE WALL (#1633 round 3, spec §3 (2)):
    ``(cut, footprint, near_m)`` per wall — a graded band (runway zones,
    the end box, a taxi zone) whose pavement stands farther than ``near_m``
    (``BEHIND_SHARE x reach``) from the footprint loses ``cut``, the
    footprint and its upper band (``smear`` wide): the hill between the
    band's new edge and the wall's back is released ground and grades
    down to the wall's top.  A wall AT the pavement edge keeps #1139's
    plane (``constraints/wall_zone.split``)."""
    return tuple((unary_union([w.poly, w.upper]), w.poly,
                  BEHIND_SHARE * wall_reach_m(w.height_m)) for w in walls
                 if w.upper is not None and not w.upper.is_empty)
