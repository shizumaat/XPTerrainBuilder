"""A RETAINING WALL THE PACK BUILT FROM SHEETS (issues #1952 / #1950; owner
RULINGS 2026-11-09a (14) "a retaining wall's height is what it retains
above the ground on its low side", 2026-11-07b (1) "the author's ground is
the pack's own, never our terrain").

A pack wall is often several co-linear OBJ sheets placed at one origin: a
deep skirt hung from the upper ground down to a footing (it hides the old
mesh), and a face sheet whose bottom edge is where the author put the low
side's ground.  Where the lidar predates the wall (no step across it), the
DEM is no witness of what it retains; the pack's own sheets are.

GATE G (:func:`hung_wall`): a candidate is the ONE part of its member,
hung from its zero (``wall_class._hangs_from_zero``), solid authored below
that zero and standing on the ground — plus the SIDE WITNESS S
(:func:`paved_faces`): apt.dat airside pavement along one long face within
``[service] retaining_wall_reach_m``, along at least
``retaining_wall_along_fraction`` of it, and along no more than the rest
of the other face.

THE COMPOSITE (:func:`sheets_of`): the tall, long parts of the same
placement unit whose footprints overlap the candidate's, transitively, are
ONE wall carried by it; every sheet's footprint is the wall's
(``airport/wall_shade``: no pad from any of them).

THE LOW SIDE FROM THE PACK (:func:`low_side_y`): the length-weighted
median ``base_y`` of the sheets standing at least :data:`FOOTING_CLEAR_M`
over the composite's lowest base — the face's bottom edge, never the
footing.  The wall retains its OBJ top (:func:`obj_top_y`) less that.

Geometry only, read off the pack partition and apt.dat; no airport is
named (RULINGS 2026-10-05e).  MEASURED KMCI (capture l1952): the border
unit's ``KCMO-Trimsheet-16`` (y -13.98 .. -0.93) with ``stoneblock``,
``KCMO-Trimsheet-22`` and ``KCMO-Trimsheet-17`` (face bottom y -4.74,
777 m) retains 3.81 m; the lidar reads 297.8 / 298.1 either side."""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

__all__ = ["FOOTING_CLEAR_M", "hung_wall", "paved_faces",
           "airside_union", "sheets_of", "low_side_y", "obj_top_y"]

#: a sheet whose base stands less than this over the composite's lowest
#: base is FOOTING (the skirt down to it), never the low side's ground: a
#: deep skirt's footing strip is authored within a metre of its bottom
#: (KMCI: ``KCMO-Trimsheet-16`` base -13.98 with its flat plate at -12.18,
#: ``stoneblock`` -14.06, ``KCMO-Trimsheet-22`` comp 3 -13.97)
FOOTING_CLEAR_M = 1.0

#: positive-area overlap (m2) that makes two sheets one wall: footprints
#: that only touch share none
_OVERLAP_M2 = 1e-6
#: the side witness's ray spacing along a face, and its start off the face
_RAY_STEP_M = 2.0
_RAY_START_M = 0.2


class _SheetPart(_t.NamedTuple):
    """One part of a placement unit as a candidate sheet."""

    key: tuple          # ``(member id, part comp)``
    poly: _t.Any        # its footprint, planar frame
    base_y: float
    length_m: float


def hung_wall(part, one: bool, top_y: float | None, seat: float | None, cfg) -> bool:
    """GATE G without its side witness: the one part of its member, hung
    from its zero, solid authored below it, standing on the ground."""
    from .wall_class import _hangs_from_zero, _stands_on_ground
    by = getattr(part, "base_y", None)
    return one and by is not None and float(by) < 0.0 \
        and _hangs_from_zero(top_y, seat, cfg) and _stands_on_ground(part)


def airside_union(airport):
    """THE APT.DAT AIRSIDE PAVEMENT: every ``Airport.pavements`` polygon
    that is not a DSF page (a ``dsf:`` page carries no side here;
    ``classify/evidence`` splits them the same way); ``None`` without one."""
    polys = []
    for pv in getattr(airport, "pavements", ()) or ():
        if str(pv.id).startswith("dsf:") or len(pv.outer) < 3:
            continue
        g = Polygon(list(pv.outer), [list(h) for h in pv.holes if len(h) >= 3])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty:
            polys.append(g)
    if not polys:
        return None
    u = unary_union(polys)
    return None if u.is_empty else u


def _ray_hits(face: LineString, paved, reach: float) -> tuple[int, int]:
    """``(hits, stations)``: rays every :data:`_RAY_STEP_M` along ``face``,
    out on its right (the footprint lies on its left), ``reach`` long —
    how many reach the airside pavement ``paved``."""
    hits = n = 0
    for t in np.arange(1.0, face.length - 1.0, _RAY_STEP_M):
        a = face.interpolate(float(t))
        b = face.interpolate(min(face.length, float(t) + 0.5))
        dx, dy = b.x - a.x, b.y - a.y
        ln = math.hypot(dx, dy)
        if ln <= 1e-9:
            continue
        nx, ny = dy / ln, -dx / ln
        ray = LineString([(a.x + nx * _RAY_START_M, a.y + ny * _RAY_START_M),
                          (a.x + nx * reach, a.y + ny * reach)])
        n += 1
        hits += bool(ray.intersects(paved))
    return hits, n


def paved_faces(pieces: _t.Sequence, paved, cfg) -> tuple | None:
    """THE SIDE WITNESS S: per piece of a wall, the index (0 / 1) of its
    long face (``wall_sides._wall_faces``) with the airside pavement
    ``paved`` beside it — its UPPER face — or ``None`` for a piece with no
    faces or with pavement on neither; ``None`` for the whole wall unless
    the paved faces have pavement along at least ``[service]
    retaining_wall_along_fraction`` of their stations and the other faces
    along no more than the rest."""
    from .wall_sides import _wall_faces
    if paved is None:
        return None
    reach = float(cfg.retaining_wall_reach_m)
    along = float(cfg.retaining_wall_along_fraction)
    out, up_h, up_n, lo_h, lo_n = [], 0, 0, 0, 0
    for g in pieces:
        faces = _wall_faces(g)
        if faces is None:
            out.append(None)
            continue
        (ha, na), (hb, nb) = (_ray_hits(f, paved, reach) for f in faces)
        if ha == hb:
            out.append(None)
            continue
        k = 0 if ha > hb else 1
        out.append(k)
        up_h, up_n = up_h + (ha, hb)[k], up_n + (na, nb)[k]
        lo_h, lo_n = lo_h + (ha, hb)[1 - k], lo_n + (na, nb)[1 - k]
    if not up_n or up_h < along * up_n or lo_h > (1.0 - along) * lo_n:
        return None
    return tuple(out)


def _part_poly(part, to_xy):
    polys = []
    for rg in getattr(part, "rings", None) or ():
        if len(rg) < 3:
            continue
        g = Polygon([to_xy(lon, lat) for lat, lon in rg])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty:
            polys.append(g)
    return unary_union(polys) if polys else None


def sheets_of(unit, key: tuple, to_xy, cfg) -> list[_SheetPart]:
    """THE COMPOSITE: the parts of ``unit`` (fences excluded; at least
    ``[service] retaining_wall_min_height_m`` tall and ``_min_length_m``
    long) whose footprints overlap the part ``key`` (``(member id,
    comp)``), transitively — itself included; empty when ``key`` is not
    among them."""
    from .wall_class import _not_a_wall
    lo_h = float(cfg.retaining_wall_min_height_m)
    lo_l = float(cfg.retaining_wall_min_length_m)
    cand: list[_SheetPart] = []
    for m in unit.members:
        if _not_a_wall(m.resource):
            continue
        for p in m.parts:
            if float(p.height_m) < lo_h or getattr(p, "base_y", None) is None:
                continue
            g = _part_poly(p, to_xy)
            if g is None or g.length / 2.0 < lo_l:
                continue
            cand.append(_SheetPart((m.id, int(p.comp)), g, float(p.base_y), g.length / 2.0))
    seed = [i for i, c in enumerate(cand) if c.key == key]
    if not seed:
        return []
    got, todo = set(seed), list(seed)
    while todo:
        a = cand[todo.pop()]
        for j, b in enumerate(cand):
            if j not in got and a.poly.intersection(b.poly).area > _OVERLAP_M2:
                got.add(j)
                todo.append(j)
    return [cand[i] for i in sorted(got)]


def low_side_y(sheets: _t.Sequence[_SheetPart]) -> float | None:
    """THE LOW SIDE'S GROUND AS AUTHORED: the length-weighted median
    ``base_y`` of the sheets standing at least :data:`FOOTING_CLEAR_M`
    over the lowest base; ``None`` when none does."""
    if not sheets:
        return None
    floor = min(s.base_y for s in sheets) + FOOTING_CLEAR_M
    up = sorted((s.base_y, s.length_m) for s in sheets if s.base_y >= floor)
    if not up:
        return None
    half, run = 0.5 * sum(w for _b, w in up), 0.0
    for b, w in up:
        run += w
        if run >= half:
            return float(b)
    return float(up[-1][0])


def obj_top_y(member, origin, to_xy, cache=None) -> float | None:
    """The highest authored ``y`` of ``member``'s solid triangles (its OBJ
    top edge); ``None`` where unread."""
    from .sunken_ramp import _member_tris
    if origin is None:
        return None
    tris = _member_tris(member, origin, to_xy, cache)
    if tris is None or not len(tris):
        return None
    return float(np.max(np.asarray(tris, float)[:, :, 2]))
