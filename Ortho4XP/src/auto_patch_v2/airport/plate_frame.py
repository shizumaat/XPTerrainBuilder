"""THE WALLS FRAME A PLATE THE OTHER WAY (owner RULINGS 2026-10-28h (1),
#414; amends Law B, RULINGS 2026-09-08b/c, for this case only).

A sunken-road plate (``sunken_roads``) is read as the pack's own floor:
deep where the plate is deep.  A pack can author that plate OPPOSITE to
the lane its walls frame — at grade against the face that closes the lane,
deepest at the open end.  There the WALLS win: the lane is a BAY (Law C),
deep at the closed end and rising over the walls' length to grade at the
open end, exactly as a wall corridor closed at one end is read.

The witnesses, all the FAMILY's own vertical faces reaching Law C's
``min_wall_depth_m`` under the object's zero (the faces a wall band is
made of, ``wall_geometry._FamilyFaces``):

1. the plate's GRADE end is CLOSED — those faces cover at least
   ``end_cap_cover_min`` of the plate's end line within
   ``tunnel.object.end_cap_open_m`` (Law C rule 4's test);
2. its DEEP end is OPEN — no family vertical face covers that share of it;
3. the lane is WALLED — a run of those faces parallel to the plate's axis
   (``parallel_max_deg``) stands at the plate's side, within a wall's
   plan thickness (``wall_face_max_thickness_m``), along at least
   ``min_wall_length_m``.

The walls' LENGTH is where the shortest side wall stops, measured from the
closed end (2026-10-26s: a corridor ends where its shorter wall stops).

:func:`walls_frame` is the ONE test; ``planar/plate_bays`` turns a framed
plate into the bay record.  Nothing numeric lives here.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString

from ..law import Law
from ..model.frame import XY
from . import obj8 as _obj8
from .deck_signature import family_key
from .wall_corridors import _bands_of, _end_cover
from .wall_geometry import _FamilyFaces, _angle_diff, _union_length

__all__ = ["PlateFrame", "walls_frame"]


@_dc.dataclass(frozen=True)
class PlateFrame:
    """The bay the walls frame round a plate: ``closed_xy`` the plate's
    grade end (now the CLOSED end, s = 0), ``u`` the unit axis toward the
    open end, ``half_m`` the plate's half width, ``wall_length_m`` the
    walls' length from the closed end, the two end covers, the family key
    as Law C names it, the side walls' count and the thinnest side wall
    band's measured plan thickness (Law C rule 1's ``WallBand``; 0 when no
    band reads there)."""

    closed_xy: XY
    u: XY
    half_m: float
    wall_length_m: float
    closed_cover: float
    open_cover: float
    family: str
    sides: int
    thick_m: float = 0.0


def _end(p: XY, u: XY, half: float) -> tuple[XY, XY]:
    n = (-u[1], u[0])
    return ((p[0] + n[0] * half, p[1] + n[1] * half), (p[0] - n[0] * half, p[1] - n[1] * half))


def _side_walls(faces: _t.Sequence[LineString], tree, p0: XY, u: XY, half: float,
                length: float, law: Law, bands: _t.Sequence = ()) -> tuple[list[float], float]:
    """Per side of the plate that a wall stands at: where that wall stops,
    measured from ``p0`` along ``u`` (the faces' far extent); a side with
    less than ``min_wall_length_m`` of wall along the plate has none.  With
    them, the thinnest of ``bands`` standing on a walled side (0 if none)."""
    wc = law.tables.structures.cutout.wall_corridor
    t_max = law.tables.structures.tunnel.object.wall_face_max_thickness_m
    n = (-u[1], u[0])
    brg = math.degrees(math.atan2(u[0], u[1])) % 180.0
    ends: list[float] = []
    thick: list[float] = []
    for side in (1.0, -1.0):
        c = (p0[0] + n[0] * side * half, p0[1] + n[1] * side * half)
        strip = LineString([c, (c[0] + u[0] * length, c[1] + u[1] * length)]).buffer(
            t_max, cap_style="flat")
        ivals: list[tuple[float, float]] = []
        far = 0.0
        for j in (tree.query(strip, predicate="intersects") if tree is not None else ()):
            seg = faces[int(j)]
            (ax, ay), (bx, by) = seg.coords[0], seg.coords[-1]
            if math.hypot(bx - ax, by - ay) < 1e-9:
                continue
            if _angle_diff(math.degrees(math.atan2(bx - ax, by - ay)) % 180.0, brg) \
                    > wc.parallel_max_deg:
                continue
            ts = [(x - p0[0]) * u[0] + (y - p0[1]) * u[1] for x, y in seg.coords]
            lo, hi = max(0.0, min(ts)), max(ts)
            if hi > lo:
                ivals.append((lo, min(hi, length)))
                far = max(far, hi)
        if _union_length(ivals) >= wc.min_wall_length_m:
            ends.append(far)
            thick.extend(bd.thickness_m for bd in bands if bd.poly.intersects(strip)
                         and _angle_diff(bd.bearing_deg, brg) <= wc.parallel_max_deg)
    return ends, min(thick, default=0.0)


def walls_frame(members: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                dem_z, law: Law, a: XY, b: XY, width: float, deep_end: int
                ) -> PlateFrame | None:
    """The bay the family's walls frame round the plate whose minimum
    rotated rectangle runs ``a`` -> ``b`` (``width`` across), deep at
    ``b`` when ``deep_end`` is 1 — or ``None`` when any witness of the
    module doc is missing (the plate is read as Law B reads it)."""
    wc = law.tables.structures.cutout.wall_corridor
    ob = law.tables.structures.tunnel.object
    grade, deep = (a, b) if deep_end == 1 else (b, a)
    L = math.dist(grade, deep)
    if L <= 1e-9:
        return None
    u = ((deep[0] - grade[0]) / L, (deep[1] - grade[1]) / L)
    half = width / 2.0
    verticals = []
    bands = []
    for o in members:
        bs, verts = _bands_of(o, cache, dem_z, law)
        bands.extend(bs)
        if verts:
            verticals.append((o, verts))
    if not verticals:
        return None
    fam = _FamilyFaces(verticals, cache, wc.min_wall_depth_m, True)
    closed = _end_cover(_end(grade, u, half), fam.faces_low, fam.low_tree, ob.end_cap_open_m)
    if closed < wc.end_cap_cover_min:
        return None
    opened = _end_cover(_end(deep, u, half), fam.faces, fam.tree, ob.end_cap_open_m)
    if opened >= wc.end_cap_cover_min:
        return None
    sides, thick = _side_walls(fam.faces_low, fam.low_tree, grade, u, half, L, law, bands)
    if not sides:
        return None
    fk = family_key(members[0])
    return PlateFrame(grade, u, half, float(min(sides)), float(closed), float(opened),
                      f"{fk[0]:.3f},{fk[1]:.3f},{fk[2]:.3f}", len(sides), float(thick))
