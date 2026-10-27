"""THE WALL TWO BAYS SHARE HIDES THE STEP BETWEEN THEM (owner RULINGS
2026-10-28l (2), #414).

Side-by-side Law C bays that share a wall are all built (2026-10-28h (3));
their floors need not agree (each is its own shallower wall's bottom,
28h (2)), so the two ramps meet under the wall they share at a step.
Where that wall reaches BELOW BOTH floors, the wall hides the step: it is
lawful.

THE DECLARATION is the existing one: one ``terrace_joints`` record
(``kind`` ``wall_terrace``, shape :data:`LABEL`) per shared wall, declared
at the wall's reach under the higher ground at the two mouths (plus the
emit's rounding).  Its LINE is the MIDLINE BETWEEN THE TWO RAMPS AS
EMITTED along the wall: the rings stand on the identity lattice, so a wall
thinner than the lattice spacing (OTHH's dock walls: 0.3 m on a 0.5 m
lattice) is not where the rings put it, and the authored band's axis can
lie beside both rings, where no chord between them crosses it.  Each
sample of the wall's axis moves to the midpoint of its nearest points on
the two ramps' faces (the axis itself where a corridor has none) — so the census's ``DeclaredWallSteps`` / ``_terrace_step_allowance``
and the engine's ``verify/steps`` forgive exactly a pair whose chord
crosses that wall, up to that depth; the excess, and every pair beside the
wall that does not cross it, still reports.  A shared wall standing
SHALLOWER than either floor declares nothing."""
from __future__ import annotations

import itertools
import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["shared_wall_joints", "shared_walls", "LABEL"]

#: the shape label the record carries
LABEL = "shared_bay_wall"
#: the patch writes elevations to the centimetre (``publication``'s own)
_EMIT_Z_ROUND_M = 0.01
#: two band rings are ONE wall when they overlap over this share of the smaller
_SAME_WALL = 0.5
_WALL_KIND = "wall_corridor"


def shared_wall_joints(planar: PlanarMap, law: Law,
                       z: _t.Sequence[float] | None = None) -> list[dict[str, _t.Any]]:
    """The ``wall_terrace`` records of the walls neighbouring bays share
    (module docstring)."""
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    walls = shared_walls(getattr(planar, "structures", ()) or (),
                         lambda t: _ramp_faces(planar, t), spacing)
    if not walls:
        return []
    from .ribbon_steps import _to_ll
    to_ll = _to_ll(planar)
    out: list[dict[str, _t.Any]] = []
    for line, depth, ids in walls:
        declared = round(depth + _EMIT_Z_ROUND_M, 4)
        out.append({
            "points": [list(to_ll(x, y)) for x, y in line.coords],
            "step_m": declared, "declared_step_m": declared, "faced": False,
            "kind": "wall_terrace", "faces": [], "shapes": [LABEL, *ids],
            "gap": False, "roles": [], "pairs": 0,
            "length_m": round(float(line.length), 2), "height_m": round(depth, 3)})
    return out


def shared_walls(tunnels: _t.Sequence, ramps=None, spacing: float = 0.5
                 ) -> list[tuple[_t.Any, float, tuple[str, str]]]:
    """``(the declared line, the wall's reach under the higher mouth
    ground, (id, id))`` per wall two Law C corridors share whose bottom
    stands under BOTH their floors.  ``ramps(tunnel)`` is the corridor's
    emitted ramp region (or ``None``); the line samples every ``spacing``.
    Two records sharing BOTH walls are the two halves of one corridor,
    never neighbours."""
    from shapely.geometry import LineString, Polygon

    bays = [t for t in tunnels if t.source == _WALL_KIND and t.wall_bands and t.footprint]
    out = []
    for a, b in itertools.combinations(bays, 2):
        fa, fb = Polygon(a.footprint), Polygon(b.footprint)
        if not fa.buffer(1e-6).intersects(fb):
            continue
        shared = [(Polygon(ra), max(za, zb)) for ra, za in a.wall_bands
                  for rb, zb in b.wall_bands if _same_wall(Polygon(ra), Polygon(rb))]
        if len(shared) != 1:
            continue                            # none, or the halves of one corridor
        pa, bottom = shared[0]
        if bottom > min(_floor(a), _floor(b)) + _EMIT_Z_ROUND_M:
            continue                            # shallower than a floor: it hides nothing
        axis = _long_axis(pa)
        if axis is None:
            continue
        part = axis.intersection(fa.union(fb).buffer(1.0))
        if part.is_empty or part.geom_type != "LineString":
            part = axis
        line = _between(LineString(part.coords), ramps(a) if ramps else None,
                        ramps(b) if ramps else None, spacing)
        ground = max(float(a.mouth_dem_z), float(b.mouth_dem_z))
        out.append((line, ground - bottom, (a.id, b.id)))
    return out


def _same_wall(pa, pb) -> bool:
    """Two band rings are ONE wall (read once by each corridor)."""
    return pa.intersection(pb).area >= _SAME_WALL * min(pa.area, pb.area)


def _between(axis, ra, rb, spacing: float):
    """The wall's axis moved, sample by sample, to the midpoint of its
    nearest points on the two ramp regions (module docstring)."""
    from shapely.geometry import LineString, Point
    from shapely.ops import nearest_points
    if ra is None or rb is None or ra.is_empty or rb.is_empty:
        return axis
    n = max(2, int(math.ceil(axis.length / max(spacing, 1e-6))) + 1)
    pts: list = []
    for k in range(n):
        c = axis.interpolate(axis.length * k / (n - 1))
        qa = nearest_points(ra.boundary, c)[0]
        qb = nearest_points(rb.boundary, c)[0]
        m = ((qa.x + qb.x) / 2.0, (qa.y + qb.y) / 2.0)
        if not pts or Point(m).distance(Point(pts[-1])) > 1e-6:
            pts.append(m)
    return LineString(pts) if len(pts) >= 2 else axis


def _ramp_faces(planar: PlanarMap, t):
    """The corridor's emitted ramp region: the faces carrying one of its
    ramp refs whose centre stands inside its footprint (``None`` if none)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from .band_road_wall import _poly
    foot = Polygon(t.footprint)
    refs = set(t.ramp_refs)
    got = []
    for f in planar.faces.values():
        if f.ref not in refs and f.role not in refs:
            continue
        g = _poly(planar, f)
        if not g.is_empty and foot.contains(g.representative_point()):
            got.append(g)
    return unary_union(got) if got else None


def _floor(t) -> float:
    """The corridor's lowest floor (its published profile; the mouth's
    when it carries none)."""
    zs = [float(zz) for _s, zz in (t.profile or ())]
    return min(zs) if zs else float(t.mouth_z)


def _long_axis(poly):
    """The long midline of a thin wall band's minimum rotated rectangle."""
    from shapely.geometry import LineString

    from ..model.frame import rotated_rectangle
    rect = rotated_rectangle(poly)
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    sides = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    k = max(range(4), key=lambda i: math.dist(*sides[i]))
    s1, s2 = sides[(k + 1) % 4], sides[(k + 3) % 4]
    m1 = ((s1[0][0] + s1[1][0]) / 2.0, (s1[0][1] + s1[1][1]) / 2.0)
    m2 = ((s2[0][0] + s2[1][0]) / 2.0, (s2[0][1] + s2[1][1]) / 2.0)
    return LineString([m1, m2]) if math.dist(m1, m2) > 0.0 else None
