"""A ROAD THAT MEETS A RETAINING WALL IS CUT BACK AT ITS FACES (issue
#1633 round 3, spec §1 (1)-(2); owner RULINGS 2026-10-28t Q269 (a): "the
wall is the step", each side keeps its own level).

ONE SITE, after every road-family cell is standing (``classify/roles``,
just before the :class:`~.roles.Classification` is built), for every
road family alike — the 1206 corridors with their §47 extension, the OSM
ribbons, the DSF road pages:

* :func:`cut_roads_at_walls` — every road-family cell loses each retaining
  wall's footprint AND the side band of the face it holds less of
  (``airport/wall_sides.far_side_cut``): a road is never on both sides of
  a wall.  MEASURED KATL (capture ``lkatl3``, solved l1633): face
  ``route10`` carried 11 vertices in ``muro_27R.obj``'s upper band and 7
  inside its footprint, held at the foot road's level 2-10 m beyond the
  wall's back — the "trench".
* :func:`cut_lines_at_walls` — every ``road_centerline`` cut line loses the
  footprints, so each remaining part is its own breakline (its own clamped
  way on its own side's DEM, ``airport/road_profile.core_profiles``); a
  part inside a footprint is dropped (the wall object stands there: route
  U's 58 m inside the 27R wall)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Polygon

from ..geom.parts import line_parts
from .evidence import polygon_parts

__all__ = ["cut_roads_at_walls", "cut_lines_at_walls"]

#: a centreline part shorter than this left by a footprint is noise
_MIN_LINE_M = 1.0


def cut_roads_at_walls(cells: _t.Sequence, roles: _t.Collection[str],
                       walls: _t.Sequence, min_area_m2: float, grow_m: float = 0.0
                       ) -> tuple[list, dict[str, float]]:
    """``cells`` with every cell of ``roles`` cut back at ``walls``
    (``Airport.retaining_walls``; the footprints grown by ``grow_m``, the
    identity snap's margin); parts under ``min_area_m2`` dropped, the ids
    re-numbered (they are positional).  Returns the cells and
    ``{wall_cut_cells, wall_cut_m2}``."""
    from ..airport.wall_sides import far_side_cut
    stats = {"wall_cut_cells": 0, "wall_cut_m2": 0.0}
    if not walls:
        return list(cells), stats
    reach = [w.poly.buffer(w.smear) for w in walls]
    out = []
    for c in cells:
        if c.role not in roles:
            out.append(c)
            continue
        poly = Polygon(c.ring, c.holes)
        poly = poly if poly.is_valid else poly.buffer(0.0)
        if not any(poly.intersects(r) for r in reach):
            out.append(c)
            continue
        kept = far_side_cut(poly, walls, grow_m=grow_m)
        lost = poly.area - kept.area
        if lost <= 1e-6:
            out.append(c)
            continue
        stats["wall_cut_cells"] += 1
        stats["wall_cut_m2"] += lost
        k = 0
        for part in polygon_parts(kept):
            if part.area < min_area_m2:
                continue
            out.append(_dc.replace(
                c, ref=c.ref if k == 0 else f"{c.ref}#w{k}",
                ring=tuple(part.exterior.coords)[:-1],
                holes=tuple(tuple(h.coords)[:-1] for h in part.interiors)))
            k += 1
    stats["wall_cut_m2"] = round(stats["wall_cut_m2"], 1)
    return [_dc.replace(c, id=i) for i, c in enumerate(out)], stats


def cut_lines_at_walls(cut: _t.Sequence, walls: _t.Sequence
                       ) -> tuple[list, dict[str, float]]:
    """``cut`` with every ``road_centerline`` line split at the walls'
    footprints (module doc).  Returns the lines and
    ``{wall_cut_lines, wall_cut_line_m}``."""
    stats = {"wall_cut_lines": 0, "wall_cut_line_m": 0.0}
    if not walls:
        return list(cut), stats
    out = []
    for cl in cut:
        if cl.kind != "road_centerline" or len(cl.points) < 2:
            out.append(cl)
            continue
        ln = LineString(cl.points)
        hit = [w.poly for w in walls if ln.intersects(w.poly)]
        if not hit:
            out.append(cl)
            continue
        rest = ln
        for g in hit:
            rest = rest.difference(g)
        stats["wall_cut_lines"] += 1
        stats["wall_cut_line_m"] += ln.length - rest.length
        out.extend(_dc.replace(cl, points=tuple(p.coords))
                   for p in line_parts(rest) if p.length >= _MIN_LINE_M)
    stats["wall_cut_line_m"] = round(stats["wall_cut_line_m"], 1)
    return out, stats
