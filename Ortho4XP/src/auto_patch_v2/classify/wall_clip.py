"""PAVEMENT NEVER CROSSES A PACK RETAINING WALL (owner RULINGS
2026-10-20ak; 20ax; 20al; 20ba; issue #1158).

A pavement polygon that reaches over or past a pack retaining wall is cut
at the wall's outline: the wall's footprint is no pavement, and what the
wall separates are SEPARATE shapes — the pavement along the top stops at
the wall's upper face, the part past its lower face stands at the lower
level, and the change of level is hidden inside the wall.  MEASURED (the
#1139 lane): KATL ``pav14`` (Global Airports 110 asphalt) covered 937 m²
of ``muro_concreto``'s 1,563 m² footprint and ran up to 4.2 m past its
lower face (653 m² on the lower side); the cut then stood at the
pavement's edge, the sliver stayed at the upper level and an 8.13 m
``strip_seam_tear`` stood at the wall's south end.

WHICH WALLS: the wall-class components that RETAIN THEIR OWN HEIGHT
(``airport/wall_class``: slender, standing on the ground, the ground
stepping across them by their height) and retain more than
``[service] retaining_wall_clear_step_m`` — the owner's clear elevation
step, "more than 2 m of elevation change in less than 3 m" (20ba): the
wall itself is the change, a vertical one.  A wall-shaped part with no
step across it does not cut (20ax's same-elevation case: no witness in
the geometry tells a retaining wall standing on level ground from any
other wall-shaped part, and cutting every facade would split every
apron a building fronts).

WHICH PAVEMENT: every source polygon, the pack's own and the borrowed
alike (20ax supersedes the spec's "borrowed only" default).  Called from
the ONE site source pavement enters the classification
(``evidence.build_evidence``), before any union, slice or role, so every
consumer downstream reads the clipped pavement (consumer census:
``docs/findings/1158-lwalls.md``).

THE CUT, per polygon a cutting wall overlaps:

1. the wall's footprint leaves the polygon;
2. THE OVERHANG — the part of the polygon in the band beside the wall on
   ONE side (``airport/wall_class.retaining_sides``: the witness's ring,
   where the ground across the wall steps by the witness's own share of its
   height, ``retaining_wall_step_min_fraction``) that ENDS inside
   that band, the polygon reaching no further out on that side, is
   misplaced and leaves the polygon (20ak: "it can't physically be a
   taxiway at the bottom of the wall, only along the top, up to the
   edge").  Where the polygon ends inside both bands, the smaller part is
   the overhang;
3. a polygon that runs on past the band on BOTH sides keeps both: it is a
   TWO-LEVEL polygon (20ax), cut by the footprint only, and counted
   (``wall_clip_two_level``).

A polygon the cut splits keeps its id on its largest piece; the others
are ``<id>#wall<k>`` — ``sources`` reads the description of a ``#``-piece
off its base id, as it does for a remainder.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.parts import polygon_parts_with_area

__all__ = ["CuttingWall", "clip_at_walls", "cutting_walls"]

#: the last metre of a side band: pavement reaching into it runs on past
#: the band (it is not an overhang)
_OUTER_M = 1.0
_EPS_M2 = 1e-6


class CuttingWall(_t.NamedTuple):
    """One wall pavement stops at: its footprint, its two side bands and
    the bands' width (``airport/wall_class.retaining_sides``)."""

    poly: _t.Any
    upper: _t.Any
    lower: _t.Any
    ring: float


def cutting_walls(airport, walls: _t.Iterable, cfg) -> list[CuttingWall]:
    """Every wall that cuts pavement (module doc, WHICH WALLS) with its
    side bands; ``cfg`` is ``classify/rules.toml``'s ``[service]``."""
    from ..airport.wall_class import retaining_sides
    step = float(cfg.retaining_wall_clear_step_m)
    out = []
    for w in walls:
        held = float(getattr(w, "retained_m", 0.0) or w.height_m)
        if not getattr(w, "retains", False) or held <= step:
            continue
        # a side is where the wall RETAINS: the ground across it steps by
        # the witness's own share of the height it retains
        up, lo, ring = retaining_sides(
            airport, w, cfg, float(cfg.retaining_wall_step_min_fraction) * held)
        out.append(CuttingWall(unary_union(w.pieces), up, lo, ring))
    return out


def _overhang(g, cw: CuttingWall):
    """The part of ``g`` (the footprint already out) that is an overhang
    across ``cw`` (module doc, step 2), or ``None`` for a two-level
    polygon; an empty Polygon when nothing overhangs."""
    outer = cw.poly.buffer(cw.ring).difference(cw.poly.buffer(cw.ring - _OUTER_M))
    parts = []
    for band in (cw.upper, cw.lower):
        if band.is_empty or not g.intersects(band):
            parts.append((Polygon(), False))
            continue
        on = g.intersection(band)
        runs_on = g.intersection(band.intersection(outer)).area > _EPS_M2
        parts.append((on, runs_on))
    (up, up_on), (lo, lo_on) = parts
    if up_on and lo_on:
        return None
    if up_on:
        return lo
    if lo_on:
        return up
    return up if up.area < lo.area else lo


def clip_at_walls(polys: _t.Sequence[tuple[str, Polygon]],
                  walls: _t.Sequence[CuttingWall], min_area_m2: float = 0.0
                  ) -> tuple[list[tuple[str, Polygon]], dict]:
    """``polys`` cut at every wall of ``walls`` (module doc); a piece the
    cut leaves under ``min_area_m2`` (``[cells] min_area_m2``, noise) is
    dropped.  Returns the
    polygons and the stats: ``wall_clip_polygons`` (polygons a wall
    overlapped), ``wall_clip_m2`` (pavement area that left them: the
    footprints and the overhangs), ``wall_clip_overhang_m2`` (the
    overhangs alone), ``wall_clip_pieces`` (pieces beyond the first),
    ``wall_clip_two_level`` (step 3)."""
    stats = {"wall_clip_polygons": 0, "wall_clip_m2": 0.0,
             "wall_clip_overhang_m2": 0.0, "wall_clip_pieces": 0,
             "wall_clip_two_level": 0}
    out: list[tuple[str, Polygon]] = []
    for sid, g in polys:
        cut_g, hit = g, False
        for cw in walls:
            if not cut_g.intersects(cw.poly) or \
                    cut_g.intersection(cw.poly).area <= _EPS_M2:
                continue
            hit = True
            cut_g = cut_g.difference(cw.poly)
            over = _overhang(cut_g, cw)
            if over is None:
                stats["wall_clip_two_level"] += 1
            elif over.area > _EPS_M2:
                stats["wall_clip_overhang_m2"] += over.area
                cut_g = cut_g.difference(over)
        if not hit:
            out.append((sid, g))
            continue
        parts = sorted((p for p in polygon_parts_with_area(cut_g)
                        if p.area >= min_area_m2), key=lambda p: -p.area)
        stats["wall_clip_polygons"] += 1
        stats["wall_clip_m2"] += g.area - sum(p.area for p in parts)
        stats["wall_clip_pieces"] += max(0, len(parts) - 1)
        out.extend((sid if k == 0 else f"{sid}#wall{k}", p)
                   for k, p in enumerate(parts))
    for k in ("wall_clip_m2", "wall_clip_overhang_m2"):
        stats[k] = round(stats[k], 1)
    return out, stats
