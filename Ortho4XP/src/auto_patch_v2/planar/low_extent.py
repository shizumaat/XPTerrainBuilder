"""THE LOWER LEVEL SPANS ITS GROUP'S LOWER FOOTPRINT (#1306, #1302; owner
RULINGS 2026-10-27h).

Owner, KATL 1.0.425: "that lower level should follow the retaining wall that
extends around the apron for that terminal all the way to the ends of the
walls"; LFPG: "that lower level should extend across the whole central
corridor".  27h: "The lower levels depth is determined by the objects, so
the bottom of the retaining wall at KATL, and the bottom of the lower
central buildings at LFPG".

``planar/low_level`` cuts every lower level out of ONE held pad
(``level_cut``: ``L ∩ P``), so a level stopped at its pad's ring: KATL's
``building47/p1`` at the terminal's west tip, 170 m and 376 m short of the
two apron walls' ends; LFPG's four trench levels either side of a corridor
no pad covers.  HERE, after the levels are minted, each level's GROUP
(its pack unit and the units whose footprints come within
``open_frame_seat.TOUCH_M`` of it, 22o) gives its LOWER PARTS: the walled
parts (``[placement] chain_min_height_m``) whose foot plane stands at least
the level's own step (``y_hi``) under its top floor.  Their footprint,
closed by ``pad_frontage_m``, with the mapped roads over it
(``low_level._with_roads``, 24a) and the pavement no aircraft reaches once
the pads stand (``planar/reach_after_pads``) that it meets -- and, read
apart, a RETAINING WALL's lower side: the ground within its own reach
``max(4 h, 20 m)`` (``constraints/wall_zone``) that stands nearer its
foot than its top (the apron it retains never does) -- less every pad
region and a riser's width, less the airside (cells and zones) and
``pad_frontage_m``, is the EXTENSION.  Each connected piece of at least ``[building_pad]
min_area_m2`` is minted ``<block>/p<k>`` (kind ``low_level``, the nearest
level's witness and block) at THE OBJECTS' BOTTOM: the densest
``PLANE_BAND_M`` plane of the lower parts' feet on it (27h), with its riser
strip ``#strip`` along the pads it faces.  The KATL control tower and brick
wall stand in no unit of the terminal's group and are not taken in (27h).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..model.planar import STRIP_SUFFIX, plane_of, plane_ref
from ..model.registries import Registries
from .low_level import LOW_KIND, _densest, _overlay, _with_roads, unit_share

__all__ = ["AirRegion", "extend_levels"]


class AirRegion(_t.NamedTuple):
    """A region the extension keeps off, as it reads it: its polygon, its
    source (``"cell"`` pavement, ``"zone"`` adjacent ground) and its role."""

    polygon: _t.Any
    source: str
    role: str = "apron"


class _Lower(_t.NamedTuple):
    """One lower part of a group: its plan footprint, its feet's ``y``,
    its wall reach (0 for a body) and its foot plane."""

    poly: _t.Any
    ys: tuple
    reach: float
    y: float


def extend_levels(regs: list, reg: Registries, air_all: _t.Sequence, airport, law,
                  grid: float, counts: dict, beyond: _t.Sequence = ()) -> list:
    """``regs`` (the pad regions, levels minted) with every lower level's
    extension over its group's lower footprint minted beside it (module
    docstring); each piece registered in ``reg.landings``.  ``beyond``: the
    pavement no aircraft reaches once the pads stand -- a piece of it the
    lower footprint meets is the footprint too (19ag, #1302)."""
    from ..model.stage_one import deriving
    lows = {r: v for r, v in reg.landings.items() if v.get("kind") == LOW_KIND}
    if not lows or getattr(airport, "partition", None) is None or not air_all:
        return regs
    to_xy = airport.frame.entry()
    by_ref: dict[str, list] = {}
    for r in regs:
        if r.polygon is not None and not r.polygon.is_empty:
            by_ref.setdefault(str(r.ref), []).append(r)
    units: dict[int, list[str]] = {}
    for ref in sorted(lows):
        if ref not in by_ref or (deriving() and lows[ref].get("air_xy")):
            continue          # a group level is not on stage 1's map (``group_low``)
        ui, _p = unit_share(unary_union([r.polygon for r in by_ref[ref]]), airport, to_xy)
        if ui is not None:
            units.setdefault(ui, []).append(ref)
    if not units:
        return regs
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    pads = valid_area(unary_union([r.polygon for rs in by_ref.values() for r in rs]))
    # every piece keeps off every airside region, the zones among them (a
    # zone past a retaining wall is already released to its own ground,
    # ``constraints/wall_zone``; one the extension cut into tore 5-9 m at
    # the walls' ends, MEASURED KATL replay), and off every STRUCTURE, which
    # its own law grades (MEASURED LFPG replay: a piece over a tunnel ramp
    # lifted its walls 2.75 m); a wall's TOP is read on the airside
    # pavement it retains
    from ..law.tables import is_structure_role
    air = valid_area(unary_union([r.polygon for r in air_all]))
    pave = valid_area(unary_union([r.polygon for r in air_all if r.source != "zone"
                                   and not is_structure_role(law, getattr(r, "role", ""))]))
    feet = _Feet(airport, law, to_xy)
    made: list = []
    n_k: dict[str, int] = {}
    for ref in lows:
        po = plane_of(ref)
        if po is not None:
            n_k[po[0]] = max(n_k.get(po[0], 0), po[1])
    for r in regs:
        po = plane_of(str(r.ref))
        if po is not None:
            n_k[po[0]] = max(n_k.get(po[0], 0), po[1])
    for ui, refs in sorted(units.items()):
        rec0 = lows[refs[0]]
        t = float(rec0["top_y"])
        lower = feet.lower(ui, t + float(rec0["y_hi"]))
        if not lower:
            continue
        bodies, walls = _footprint(lower, pave, near, w, airport, law, t)
        if beyond and not bodies.is_empty:
            reach = bodies.buffer(near, join_style=2)
            bodies = valid_area(unary_union([bodies, *(g for g in beyond if g.intersects(reach))]))
        levels = {ref: unary_union([r.polygon for r in by_ref[ref]]) for ref in refs}
        qs = []
        keep_off = valid_area(unary_union([pads.buffer(w, join_style=2),
                                           air.buffer(near, join_style=2)]))
        for A in (bodies, walls):
            if not A.is_empty:
                A = valid_area(_overlay(A, keep_off, "difference", grid))
                qs.extend(nonempty_polygon_parts(A))
        for q in qs:
            if q.area < pmin:
                continue
            y = _bottom(q, lower, w)
            if y is None:
                continue
            host = min(refs, key=lambda r: levels[r].distance(q))
            rec = lows[host]
            block = str(rec["block"])
            n_k[block] = n_k.get(block, 1) + 1
            ext = plane_ref(block, n_k[block])
            S = valid_area(q.buffer(w, join_style=2).intersection(pads.buffer(w + 0.5 * w))
                           .difference(q).difference(pads).difference(air))
            tmpl = by_ref[host][0]
            made.append(_dc.replace(tmpl, ref=ext, polygon=q))
            made.extend(_dc.replace(tmpl, ref=ext + STRIP_SUFFIX, polygon=s)
                        for s in nonempty_polygon_parts(S))
            reg.landings[ext] = {**rec, "y": round(y - t, 3), "y_lo": round(y - t, 3),
                                 "y_feet": round(y, 3), "area_m2": round(q.area, 1),
                                 "low_parts": 0, "extent_of": host}
            pads = unary_union([pads, q.buffer(w, join_style=2)])
    if made:
        counts["low_level_extents"] = sum(1 for v in reg.landings.values()
                                          if v.get("extent_of"))
        counts["low_level_extent_list"] = "; ".join(
            f"{k} of {v['extent_of']} y {v['y_feet']:+.2f} {v['area_m2']:g} m2"
            for k, v in sorted(reg.landings.items()) if v.get("extent_of"))
    return regs + made


class _Feet:
    """The pack read the extension needs: unit footprints, the group of a
    unit, its lower parts (wall-class pieces marked)."""

    def __init__(self, airport, law, to_xy):
        from ..airport.open_frame_seat import TOUCH_M
        self.airport, self.law, self.to_xy = airport, law, to_xy
        self.touch = float(TOUCH_M)
        self.wall_min = float(law.tables.structures.placement.chain_min_height_m)
        self._foot: dict[int, _t.Any] = {}
        self._walls = None
        units = airport.partition.units
        polys = [self.footprint(i) for i in range(len(units))]
        self.ids = [i for i, g in enumerate(polys) if not g.is_empty]
        self.tree = STRtree([polys[i] for i in self.ids]) if self.ids else None

    def footprint(self, ui: int):
        if ui not in self._foot:
            gs = [g for m in self.airport.partition.units[ui].members for p in m.parts
                  if not getattr(p, "line", False) for g in self._rings(p)]
            self._foot[ui] = valid_area(unary_union(gs)) if gs else Polygon()
        return self._foot[ui]

    def _rings(self, p) -> list:
        out = []
        for rg in getattr(p, "rings", ()) or ():
            if len(rg) >= 3:
                g = Polygon([self.to_xy(lon, lat) for lat, lon in rg])
                g = g if g.is_valid else g.buffer(0.0)
                if not g.is_empty:
                    out.append(g)
        return out

    def group(self, ui: int) -> list[int]:
        """``ui`` and the units whose footprints come within ``TOUCH_M``
        (22o, one hop)."""
        f = self.footprint(ui)
        if self.tree is None or f.is_empty:
            return [ui]
        hit = self.tree.query(f, predicate="dwithin", distance=self.touch)
        return sorted({ui, *(self.ids[int(j)] for j in hit)})

    def walls(self) -> "tuple[list, _t.Any]":
        """``(reaches, tree)`` of the pack's wall-class pieces
        (``airport/wall_class``, the one classifier): each piece's reach
        ``max(4 h, 20 m)``, and an index over the pieces."""
        if self._walls is None:
            from ..classify.retaining_wall import wall_class_components
            from ..classify.rules import load_rules
            polys, reach = [], []
            for c in wall_class_components(self.airport, load_rules().service):
                for g in c.pieces:
                    polys.append(g)
                    reach.append(max(4.0 * float(c.height_m), 20.0))
            self._walls = (list(zip(polys, reach, strict=True)), STRtree(polys) if polys else None)
        return self._walls

    def reach(self, g) -> float:
        """The wall reach of a part footprint ``g`` (0 for a body): the
        reach of the wall-class piece covering most of it."""
        pieces, tree = self.walls()
        if tree is None:
            return 0.0
        for j in tree.query(g, predicate="intersects"):
            q, r = pieces[int(j)]
            if q.intersection(g).area >= 0.5 * g.area:
                return r
        return 0.0

    def lower(self, ui: int, y_max: float) -> list[_Lower]:
        """The group's lower parts: walled parts whose foot plane stands at
        or under ``y_max``."""
        from ..airport.airside_group_seat import PLANE_BAND_M
        out = []
        for u in self.group(ui):
            for m in self.airport.partition.units[u].members:
                for p in m.parts:
                    if (getattr(p, "line", False)
                            or float(getattr(p, "height_m", 0.0) or 0.0) < self.wall_min):
                        continue
                    ys = tuple(sorted(float(f[2]) for f in (getattr(p, "feet", ()) or ())))
                    if not ys:
                        continue
                    _n, y = _densest(ys, PLANE_BAND_M)
                    if y > y_max:
                        continue
                    g = unary_union(self._rings(p))
                    if g.is_empty:
                        continue
                    out.append(_Lower(g, ys, self.reach(g), y))
        return out


def _footprint(lower: list[_Lower], air, near: float, w: float, airport, law, t: float):
    """``(bodies, walls)``: the closed lower footprint of a group's lower
    bodies with the roads over it, and the lower side of its retaining
    walls beyond it a riser off (module docstring) -- two floors, read
    apart."""
    bodies = [p.poly for p in lower if p.reach <= 0.0]
    B = unary_union(bodies).buffer(near, join_style=2).buffer(-near, join_style=2) \
        if bodies else Polygon()
    if not B.is_empty:
        B = _with_roads(valid_area(B), B.buffer(near), airport, law, near)
    dem = getattr(airport, "dem", None)
    sides = [_low_side(p, air, dem, t) for p in lower if p.reach > 0.0 and dem is not None]
    W = valid_area(unary_union(sides)) if sides else Polygon()
    if not W.is_empty and not B.is_empty:
        W = valid_area(W.difference(B.buffer(w, join_style=2)))
    return valid_area(B), W


def _low_side(p: _Lower, air, dem, t: float):
    """The ground within a wall's reach that stands at its LOWER side: the
    DEM nearer the wall's foot than its top, the top read as the airside
    pavement's ground beside it (the wall retains the apron)."""
    band = p.poly.buffer(p.reach, join_style=2).difference(p.poly)
    near_air = air.intersection(p.poly.buffer(p.reach)) if air is not None else None
    z_top = _median_dem(near_air, dem) if near_air is not None and not near_air.is_empty else None
    if z_top is None:
        return Polygon()
    cut = z_top - 0.5 * (t - p.y)
    x0, y0, x1, y1 = band.bounds
    h = max(2.0, math.sqrt(max(band.area, 1.0) / 4000.0))
    cells = []
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            c = Point(x + 0.5 * h, y + 0.5 * h)
            if band.contains(c):
                try:
                    z = float(dem.z(c.x, c.y))
                except Exception:  # noqa: BLE001 — off the raster
                    z = float("nan")
                if z == z and z <= cut:
                    cells.append(box(x, y, x + h, y + h))
            x += h
        y += h
    if not cells:
        return Polygon()
    return valid_area(unary_union(cells).intersection(band))


def _median_dem(g, dem) -> "float | None":
    from .low_level import _ground
    return _ground(g, dem, 2.0)


def _bottom(q, lower: list[_Lower], w: float) -> "float | None":
    """THE OBJECTS' BOTTOM on piece ``q`` (27h): the densest
    ``PLANE_BAND_M`` plane of the feet of the lower bodies standing on it,
    each body weighed by the area it covers there (a terminal's lower hall
    over a road deck's columns: "the bottom of the lower central buildings
    at LFPG") -- where none does, of
    the NEAREST retaining wall whose lower side it is (the wall beside its
    lower ground: "the bottom of the retaining wall at KATL")."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    pairs = []
    for p in lower:
        if p.reach <= 0.0:
            a = p.poly.intersection(q).area
            if a > 1.0:
                pairs.extend((y, a / len(p.ys)) for y in p.ys)
    if not pairs:
        # the walls whose lower side this piece is (within their reach: the
        # apron may overhang the wall's face, 20aj, and the piece stands
        # ``pad_frontage_m`` off it)
        near = sorted((p.poly.distance(q), i) for i, p in enumerate(lower) if p.reach > 0.0
                      and p.poly.distance(q) <= p.reach)
        if near:
            d0 = near[0][0]
            pairs = [(y, 1.0) for d, i in near if d <= d0 + w for y in lower[i].ys]
    if not pairs:
        return None
    return _densest_weighted(sorted(pairs), float(PLANE_BAND_M))


def _densest_weighted(pairs: list, band: float) -> float:
    """The weighted median of the ``band``-wide window of ``(y, weight)``
    (sorted by ``y``) holding the most weight."""
    best, lo, hi = -1.0, 0, 0
    acc, j = 0.0, 0
    for i, (y, wt) in enumerate(pairs):
        acc += wt
        while y - pairs[j][0] > band:
            acc -= pairs[j][1]
            j += 1
        if acc > best:
            best, lo, hi = acc, j, i
    half, run = 0.5 * best, 0.0
    for y, wt in pairs[lo:hi + 1]:
        run += wt
        if run >= half:
            return float(y)
    return float(pairs[hi][0])
