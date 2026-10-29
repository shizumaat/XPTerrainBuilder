"""A RETAINING WALL SPLITS THE ADJACENT GROUND (owner, issue #1139, KATL
east terminal 33.638963, -84.417003: "a retaining wall ... would override
any adjacent ground ... low level up to the bottom of the wall, high level
flat at the top of the wall"; RULINGS 2026-10-15a (2) "the wall is the
step", 2026-10-15g (B) "the zone goes straight to DEM").

A zone-law row (``constraints/zones`` / ``strips``) ties a ground vertex
``g`` to its pavement FOOT.  At a declared wall that RETAINS ITS HEIGHT
(``PlanarMap.road_terrace['wall']`` with ``retains``; a tunnel mouth's
piece excluded — it bounds the open cut, ``airport/road_ramp``):

* BEYOND THE WALL — the segment ``g`` -> foot crosses the wall (already
  ``wall_release``'s), OR the wall stands just BEHIND the foot, inside the
  pavement (the pavement OVERHANGS the wall's outer face, so the whole zone
  strip lies on the far side and no segment of it crosses): the row is
  released and the ground goes to its own level.  MEASURED KATL (capture on
  901f2f587): ``muro_concreto.obj`` comp 0 (12.01 m) stands 3.1 m inside
  taxiway ``pav14``'s edge; zone-2 vertex v23164, 1 m from the owner's
  lower site, held 299.88 m over a 290.34 m DEM by its row to the edge.
* BEFORE THE WALL — the wall stands on the ray from the foot through ``g``
  within ``reach`` past ``g``: ``g`` is between the pavement and the wall,
  and that ground is ONE PLANE at the edge's level (the band at exactly
  zero, §37 (11) (2)'s quay): flat over to the wall, whichever level the
  pavement is.

Geometry only, read off the published wall records; the rows' own
generators are untouched."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..model.constraints import Linear
from ..model.wall_reach import BEHIND_SHARE, wall_reach_m, wall_smear_m

__all__ = ["RetainingLine", "retaining_lines", "split", "flat", "foot_ground",
           "BEHIND_SHARE"]


class RetainingLine(_t.NamedTuple):
    """One pack retaining wall as the adjacent ground reads it."""

    poly: _t.Any
    #: how far it reads ground and pavement: ``max(4 h, 20 m)``
    reach: float
    #: how far a lidar DEM smears its step on either side: the witness's
    #: ring (``airport/wall_class._retains_its_height``, at least 3 m, the
    #: wall's height out)
    smear: float
    #: the record's labelled sides: vertex -> ``"upper"`` / ``"lower"``
    side: dict


def retaining_lines(walls: _t.Mapping[int, _t.Mapping]) -> list[RetainingLine]:
    """One :class:`RetainingLine` per pack retaining wall (no mouth)."""
    from shapely.geometry import Polygon
    out = []
    for _k, r in sorted(walls.items()):
        if not r.get("retains") or r.get("mouth") or len(r.get("line") or ()) < 4:
            continue
        g = Polygon(r["line"])
        h = float(r["height_m"])
        side = {int(v): "upper" for v in r.get("upper") or ()}
        side.update({int(v): "lower" for v in r.get("lower") or ()})
        out.append(RetainingLine(g if g.is_valid else g.buffer(0.0),
                                 wall_reach_m(h), wall_smear_m(h), side))
    return out


def _foot_xy(r: Linear, xy: _t.Mapping[int, tuple[float, float]], g: int
             ) -> tuple[float, float] | None:
    """The row's pavement foot: its other terms' weighted point."""
    w = [(xy[v], abs(c)) for v, c in r.terms if v != g and v in xy]
    s = sum(c for _p, c in w)
    if not w or s <= 0.0:
        return None
    return (sum(p[0] * c for p, c in w) / s, sum(p[1] * c for p, c in w) / s)


def _on_lower_side(w: RetainingLine, g: int,
                   xy: _t.Mapping[int, tuple[float, float]]) -> bool:
    """``g`` sees the wall's LOWER side: the nearest of the record's labelled
    vertices it reaches without crossing the wall is a lower one (the
    reading ``solve/wall_cut._side_of`` makes)."""
    from shapely.geometry import LineString
    for _d, q in sorted((math.dist(xy[g], xy[q]), q) for q in w.side if q in xy):
        if not LineString([xy[g], xy[q]]).intersects(w.poly):
            return w.side[q] == "lower"
    return False


def _behind(w: RetainingLine, f: tuple[float, float], g: int,
            xy: _t.Mapping[int, tuple[float, float]], under: _t.Any) -> bool:
    """The pavement OVERHANGS the wall's outer face and ``g`` is past it:
    the wall's nearest point within ``BEHIND_SHARE x reach`` of the foot
    ``f``, on the far side of ``f`` from ``g`` and inside the foot's own
    pavement (``under``, less half a metre), and ``g`` on the wall's lower
    side (:func:`_on_lower_side`).  MEASURED KATL: ``pav14`` runs over
    ``muro_concreto5`` too, 8 m in from its WEST edge, with its west zone
    on the upper side — read without the side, that zone fell 4 m to its
    DEM."""
    from shapely.geometry import Point
    from shapely.ops import nearest_points
    p = Point(f)
    if under is None or w.poly.distance(p) > BEHIND_SHARE * w.reach:
        return False
    q = nearest_points(w.poly, p)[0]
    gx, gy = xy[g]
    if (q.x - f[0]) * (gx - f[0]) + (q.y - f[1]) * (gy - f[1]) >= 0.0:
        return False
    return bool(under.buffer(-0.5).contains(q)) and _on_lower_side(w, g, xy)


def _ahead(poly, f: tuple[float, float], g: tuple[float, float], reach: float) -> bool:
    """The wall stands on the ray from the foot through ``g``, within
    ``reach`` past ``g``: ``g`` is between the pavement and the wall."""
    from shapely.geometry import LineString
    dx, dy = g[0] - f[0], g[1] - f[1]
    n = math.hypot(dx, dy)
    if n <= 1e-9:
        return False
    return LineString([g, (g[0] + dx / n * reach, g[1] + dy / n * reach)]).intersects(poly)


def _near_side(r: Linear, xy: _t.Mapping[int, tuple[float, float]], g: int,
               lines: _t.Sequence[RetainingLine],
               paved: _t.Callable[[int], frozenset]) -> Linear | None:
    """The row with its feet ACROSS a retaining wall from ``g`` dropped and
    the rest renormalised, or ``None`` when ``g`` is beyond the wall: every
    foot across it, or a foot across it on the SAME pavement as a foot on
    ``g``'s side (the pavement straddles the wall; ``g`` is past it).  A
    zone row's foot can BLEND two pavement edges (``zones._blend_partner``):
    measured KATL, zone-2 v10114 above ``muro_ladrillo`` blended taxiway
    ``pav14``'s edge (302.5 m) with ``building57``'s rim below the wall
    (293.0 m) — that foot is another level's and is dropped."""
    from shapely.geometry import LineString
    near, far = [], []
    for v, c in r.terms:
        if v == g:
            continue
        seg = LineString([xy[g], xy[v]])
        (far if any(seg.intersects(w.poly) for w in lines) else near).append((v, c))
    if not far:
        return r
    s = sum(-c for _v, c in near)
    if not near or s <= 0.0:
        return None
    if {p_ for v, _c in far for p_ in paved(v)} & {p_ for v, _c in near for p_ in paved(v)}:
        return None
    own = next(c for v, c in r.terms if v == g)
    return _dc.replace(r, terms=((g, own), *((v, c / s * own) for v, c in near)))


def split(r: Linear, xy: _t.Mapping[int, tuple[float, float]],
          lines: _t.Sequence[RetainingLine],
          paved: _t.Callable[[int], frozenset],
          paved_area: _t.Callable[[Linear], _t.Any]) -> tuple[str | None, Linear]:
    """``("beyond", r)`` (release the row), ``("before", flat row)`` (one
    plane at the edge) or ``(None, r)`` — the row kept, its feet across a
    wall dropped — for one zone-law row against the retaining walls.
    ``paved(v)`` is the set of pavement refs a foot vertex stands on,
    ``paved_area(row)`` the area of the pavements its feet stand on."""
    g = r.follows if isinstance(r.follows, int) else None
    if g is None or g not in xy:
        return None, r
    kept = _near_side(r, xy, g, lines, paved)
    if kept is None:
        return "beyond", r
    f = _foot_xy(kept, xy, g)
    if f is None:
        return None, kept
    under = paved_area(kept)
    if any(_behind(w, f, g, xy, under) for w in lines):
        return "beyond", r
    # a floor-only or ceiling-only row (a farther pavement's floor, a road
    # kerb's cap) is not the band and never becomes the plane
    # ...and, on the wall's UPPER side, only for a wall AT the pavement edge
    # (#1139: within ``BEHIND_SHARE x reach`` of the foot).  An upper band
    # whose pavement stands farther back is met by the band's own law and
    # stops ``smear`` short of the upper face (``planar/zones``, #1633
    # round 3 spec §3 (2)): held flat to the wall, the 27R safety area stood
    # a 17 m mesh cliff over the road band.  On the LOWER side the ground
    # runs flat to the wall's foot whatever the distance (#1600's "front":
    # the whole face exposed, no bumps — KATL ``muro_concreto5``)
    from shapely.geometry import Point
    if kept.lo is not None and kept.hi is not None and \
            any(_ahead(w.poly, f, xy[g], w.reach)
                and (w.poly.distance(Point(f)) <= BEHIND_SHARE * w.reach
                     or _on_lower_side(w, g, xy))
                for w in lines):
        return "before", flat(kept)
    return None, kept


def flat(r: Linear) -> Linear:
    """The row as ONE PLANE at its foot's level (the band at exactly zero)."""
    return _dc.replace(r, lo=0.0, hi=0.0)


def foot_ground(dem: _t.Mapping[int, float], xy: _t.Mapping[int, tuple[float, float]],
                lines: _t.Sequence[RetainingLine]) -> dict[int, float]:
    """THE LOWER LEVEL RUNS FLAT TO THE WALL'S FOOT (#1139): the level of
    each released ground vertex (``dem``: vertex -> its DEM sample) — its
    own DEM, except within a wall's ``smear`` of its footprint, where the
    lidar still reads part of the step: there the lower of its own DEM and
    that of the nearest released vertex on its side of the wall past the
    smear.  MEASURED KATL (capture on 901f2f587): zone-1 v23472, 3 m off
    ``muro_concreto``'s foot, DEM 300.47 m against 289.7-290.3 m on the
    ground 12 m out; held at its own DEM it lifted the service road beside
    it 6 m."""
    from shapely.geometry import LineString, Point
    out = dict(dem)
    for w in lines:
        dist = {v: w.poly.distance(Point(xy[v])) for v in dem}
        near = [v for v, d in dist.items() if d < w.smear]
        past = [v for v, d in dist.items() if w.smear <= d <= w.reach]
        for v in near:
            side = [q for q in past
                    if not LineString([xy[v], xy[q]]).intersects(w.poly)]
            if side:
                q = min(side, key=lambda q: (math.dist(xy[v], xy[q]), q))
                out[v] = min(out[v], float(dem[q]))
    return out
