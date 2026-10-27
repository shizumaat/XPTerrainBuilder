"""THE WALL TWO BAYS SHARE HIDES THE STEP BETWEEN THEM (owner RULINGS
2026-10-28l (2), #414).

Side-by-side Law C bays that share a wall are all built (2026-10-28h (3));
their floors need not agree (each is its own shallower wall's bottom,
28h (2)), so the two ramps meet under the wall they share at a step.
Where that wall reaches BELOW BOTH floors, the wall hides the step: it is
lawful.

THE DECLARATION is the existing one: one ``terrace_joints`` record
(``kind`` ``wall_terrace``, shape :data:`LABEL`) per shared wall, along the
wall band's own long axis within the two corridors, declared at the wall's
reach under the higher ground at the two mouths (plus the emit's
rounding) — so the census's ``DeclaredWallSteps`` / ``_terrace_step_allowance``
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
    walls = shared_walls(getattr(planar, "structures", ()) or ())
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


def shared_walls(tunnels: _t.Sequence) -> list[tuple[_t.Any, float, tuple[str, str]]]:
    """``(the wall's axis LineString within the two corridors, its reach
    under the higher mouth ground, (id, id))`` per wall two Law C corridors
    share whose bottom stands under BOTH their floors."""
    from shapely.geometry import LineString, Polygon

    bays = [t for t in tunnels if t.source == _WALL_KIND and t.wall_bands and t.footprint]
    out = []
    for a, b in itertools.combinations(bays, 2):
        fa, fb = Polygon(a.footprint), Polygon(b.footprint)
        if not fa.buffer(1e-6).intersects(fb):
            continue
        floor = min(_floor(a), _floor(b))
        for ra, za in a.wall_bands:
            pa = Polygon(ra)
            for rb, zb in b.wall_bands:
                pb = Polygon(rb)
                inter = pa.intersection(pb).area
                if inter < _SAME_WALL * min(pa.area, pb.area):
                    continue
                bottom = max(za, zb)            # the one wall, read twice
                if bottom > floor + _EMIT_Z_ROUND_M:
                    continue                    # shallower than a floor: it hides nothing
                axis = _long_axis(pa)
                if axis is None:
                    continue
                part = axis.intersection(fa.union(fb).buffer(1.0))
                if part.is_empty or part.geom_type != "LineString":
                    part = axis
                ground = max(float(a.mouth_dem_z), float(b.mouth_dem_z))
                out.append((LineString(part.coords), ground - bottom, (a.id, b.id)))
    return out


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
