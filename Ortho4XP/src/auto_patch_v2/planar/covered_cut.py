"""THE CUT UNDER A BUILDING IS THE BUILDING'S LOWER LEVEL (#1333; owner
RULINGS 2026-10-23b two pads, 2026-10-27h depth from the objects; with
#1179's "a pad never fills a mapped cutting"; spec
``docs/specs/lfll-station-skybridge-spec.md``).

Owner, 2026-10-25 (LFLL): "the train station is connected to the terminal
by skybridge and should stay with that group, and receive a second lower
pad so the rail cut stays consistent as it passes the airport".

#1183 cut every mapped ``cutting=*`` corridor out of every pad, so a pad
no longer filled LFLL's TGV trench; but the station STANDS OVER the
trench (the tracks are mapped ``cutting=yes covered=yes
tunnel=building_passage`` under it), and the pad fills of 19ap
(``planar/pad_fill``) then filled the corridor back up under the
concourse's plates: MEASURED (main b8c456c9, capture replay) the ground
along the rail at 229.3-230.3 m north and south of the station and
239.3-239.8 m on 16 ``building8/landing*`` fills for the 450 m under it.

A COVERED CUTTING (``classify/pad_cut_corridor``: ``covered=yes`` or
``tunnel=building_passage``) stays in the pad, and HERE the pad's own unit
says how deep it runs.  The cut's REACH is its corridor and one carriageway
width either side (the platforms between and beside the tracks).  The
block's TOP level ``t`` is the densest ``PLANE_BAND_M`` plane of the walled
feet of the unit's share of the pad off the reach (:func:`_top`).  Its
LOWER PARTS are the parts standing at least two plane bands (a storey, 23c)
under ``t`` whose footprint meets the reach, each kept to it.  The corridor
and those footprints, cut out of the pad as a level
(``low_level.level_cut``: closed by ``pad_frontage_m``, kept that far off
the airside and a riser's width off the other pads, at least a unit pad's
worth), are ``<block>/p1``, a LOWER LEVEL (``low_level.LOW_KIND``, record
``witness`` :data:`WITNESS`) held rigid at the block's datum + the objects'
plane under ``t`` (27h; ``constraints/platform.landing_rows``): the densest
``PLANE_BAND_M`` plane of the lower parts' walled feet in the reach.  It
takes no road (24a): a road crossing over the cut inside the building is
the building's deck (28k 227a), and no road ribbon stands in a covered cut
(``planar/ribbons``).  It extends over nothing (``planar/low_extent``).
MEASURED LFLL (capture b8c456c9, replayed on main 28cd9b38 and this
tree): ``building8/p1`` at y -9.06 under t -0.06 (21,785 m2 since it
takes the cut alone, round 3; 54,130 m2 with the forecourt beyond the
trench grown in, 28r (1)), 230.38 m flat
for the 450 m under the station where the fills stood at 239.3-239.8 m;
hard rows relaxed 280 -> 50, adjudicated census rows 424 -> 176, airside
families unchanged.  Its ends grade to the open cut (``planar/cut_runout``,
RULINGS 2026-10-28r (3)).

What no level takes -- a covered cutting under a pad whose unit has no
lower storey along it, a piece the level cut keeps off the airside -- is
trimmed out of every pad (:func:`trim_uncut`), as #1183 trims an open
cutting: a pad never fills a cut.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..model.planar import STRIP_SUFFIX
from .low_level import _densest, _ground, _plane_band, _ring_poly, level_cut, top_level, unit_share

__all__ = ["WITNESS", "covered_corridors", "covered_cut_taken", "plan_covered", "trim_uncut"]

#: the ``witness`` a covered-cut lower level's record carries
WITNESS = "covered_cut"


def covered_corridors(airport, law, widen: float = 0.0):
    """The union of the mapped COVERED cutting corridors in the frame
    (``widen`` carriageway widths either side), or ``None``
    (``classify/pad_cut_corridor``, the one reading)."""
    from ..classify.pad_cut_corridor import cutting_corridors
    C = cutting_corridors(airport, law, covered=True, widen=widen)
    return None if C is None or C.is_empty else valid_area(C)


def _cut_refs(reg) -> "tuple[set, set]":
    """``(levels, levels and their strips)``: the covered-cut level refs."""
    mine = {ref for ref, rec in reg.landings.items() if rec.get("witness") == WITNESS}
    return mine, mine | {ref + STRIP_SUFFIX for ref in mine}


def covered_cut_taken(airport, law, regions, reg):
    """The covered corridors with every covered-cut level and its riser
    strip among ``regions`` (28r (2)): a road over the cut is the building's
    deck for the whole level and its riser, so no ribbon cell stands in
    them -- its cells end at the strip's outer edge, the block's rim.
    MEASURED LFLL: the ``-6364``/``-11343`` crossing's cell between the
    corridor's edge and the level's ring shared the level's ring node and
    held a level vertex at 239.37 m.  ``None`` where there is no cut."""
    C = covered_corridors(airport, law)
    _mine, keep = _cut_refs(reg)
    got = [r.polygon for r in regions if str(r.ref) in keep and r.polygon is not None]
    if not got:
        return C
    return valid_area(unary_union(got if C is None else [C, *got]))


def _lower_parts(parts, C, R, t: float, step: float, to_xy) -> list:
    """``[(part, footprint in R)]``: the parts standing at least ``step``
    under ``t`` whose footprint meets the corridor's REACH ``R`` (the
    corridor ``C`` and one carriageway width either side: the platforms
    between and beside the tracks), each footprint kept to ``R`` -- never
    the rest of a 5 km rail object or of the unit's ground plates."""
    out = []
    for p, _xy in parts:
        if getattr(p, "line", False) or float(p.base_y) > t - step:
            continue
        polys = [g for rg in p.rings if (g := _ring_poly(rg, to_xy)) is not None]
        if polys and any(g.intersects(R) for g in polys):
            g = valid_area(unary_union(polys).intersection(R))
            if not g.is_empty:
                out.append((p, g))
    return out


def _floor(low, R, law, t: float, step: float, to_xy) -> "tuple[float, int, int] | None":
    """``(plane, feet on it, feet read)``: the densest ``PLANE_BAND_M`` plane
    of the lower parts' WALLED feet in the reach ``R`` a storey under ``t``
    (27h); every such lower foot where none is walled."""
    import shapely
    wall_min = float(law.tables.structures.placement.chain_min_height_m)

    def feet(walled: bool) -> list:
        got = [(to_xy(float(f[1]), float(f[0])), float(f[2])) for p, _g in low
               if not walled or float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min
               for f in (getattr(p, "feet", ()) or ()) if float(f[2]) <= t - step]
        if not got:
            return []
        xs = [xy[0] for xy, _y in got]
        ys = [xy[1] for xy, _y in got]
        inside = shapely.contains_xy(R, xs, ys)
        return [y for (_xy, y), k in zip(got, inside, strict=True) if k]

    ys = feet(True) or feet(False)
    if not ys:
        return None
    n, med = _densest(sorted(ys), _plane_band())
    return med, n, len(ys)


def _top(parts, air, airport, law, to_xy, near: float, R) -> "float | None":
    """The block's TOP level in the objects' frame: the densest
    ``PLANE_BAND_M`` plane of the walled feet of the unit's share of the
    pad OFF the cut's reach ``R`` -- the floor the pad's own buildings
    stand on, which its datum carries (LFLL's station: 3,956 of 5,004
    walled feet at y -0.06; the stand-side floor of the WHOLE unit, the
    airport, read 241.06 m on the solved apron and stood the trench 2 m
    over its objects) -- else the frontage level (``low_level.top_level``)."""
    import shapely

    from ..airport.airside_group_seat import PLANE_MIN_FEET
    from .low_level import walled_feet
    xy, ys = walled_feet(parts, law, to_xy)
    if ys:
        off = ~shapely.contains_xy(R, [p[0] for p in xy], [p[1] for p in xy])
        ys = [y for y, k in zip(ys, off, strict=True) if k]
    if len(ys) >= PLANE_MIN_FEET:
        return float(_densest(sorted(ys), _plane_band())[1])
    top = top_level(parts, air, airport, law, to_xy, near)
    return None if top is None else float(top[0])


def _off_the_roads(P, H, L, S, C, airport, law, grid: float):
    """``(high, low, strip, n, m2)``: the level kept a riser's width ``w``
    off the carriageway of every mapped road within ``w`` of it that does
    not cross the cut ``C`` (24a: a road meets the pad at its edge, at the
    block's level; a road over the cut is the building's deck, 28r (2)),
    with the strip and the block re-cut from it; ``n`` roads kept off,
    ``m2`` taken from the level.  MEASURED LFLL closing build (main
    28cd9b38): the drop-off roads beside the station welded to the level's
    edge and were dragged 5-8 m down (road_cross_section +17)."""
    from ..airport.deck_signature import is_tunnel_way
    from ..airport.road_ways import mapped_width_m
    tn = law.tables.structures.tunnel
    admitted = tuple(tn.admitted_values)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    roads = []
    for way in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(way, "tags", None) or {}
        if not tags.get("highway") or len(way.points) < 2 or is_tunnel_way(tags, admitted):
            continue
        half = 0.5 * mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)
        c = LineString(way.points).buffer(half, cap_style="flat", join_style=2)
        if c.distance(L) <= w and not c.intersects(C):
            roads.append(c.buffer(w, join_style=2))
    if not roads:
        return H, L, S, 0, 0.0
    keep = valid_area(valid_area(unary_union(roads)).difference(C))
    if keep.is_empty or not keep.intersects(L):
        return H, L, S, len(roads), 0.0
    L2 = valid_area(L.difference(keep))
    Lw = valid_area(L2.buffer(w, join_style=2))
    S2 = valid_area(valid_area(P.intersection(Lw)).difference(L2))
    H2 = valid_area(P.difference(Lw))
    return H2, L2, S2, len(roads), round(L.area - L2.area, 1)


def plan_covered(P, air, airport, law, grid: float, cov, others=None, refused=None,
                 cov_reach=None) -> "tuple[_t.Any, _t.Any, _t.Any, dict] | None":
    """``(high, low, strip, record)`` for the held pad ``P`` over the covered
    cutting ``cov`` (module docstring; ``cov_reach`` the same corridors one
    carriageway width wider), or ``None`` -- the reason appended to
    ``refused`` where the corridor reaches the pad."""
    if cov is None or P.is_empty:
        return None
    C = valid_area(cov.intersection(P))
    bp = law.tables.structures.building_pad
    if C.is_empty or C.area < float(bp.min_area_m2):
        return None
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    to_xy = airport.frame.entry()
    parts = unit_share(P, airport, to_xy)[1]
    R = valid_area(valid_area(cov_reach.intersection(P)).union(C)) if cov_reach is not None else C
    t = _top(parts, air, airport, law, to_xy, near, R) if parts else None
    if t is None:
        if refused is not None:
            refused.append("no unit part fronts the airside")
        return None
    step = 2.0 * _plane_band()
    low = _lower_parts(parts, C, R, t, step, to_xy)
    fl = _floor(low, R, law, t, step, to_xy) if low else None
    if fl is None:
        if refused is not None:
            refused.append(f"no part a storey under y {t:+.2f} along the covered cut")
        return None
    plane, n_on, n_feet = fl
    L0 = valid_area(unary_union([C, *(g for _p, g in low)]))
    cut = level_cut(P, L0, air, others, law, grid, float(bp.min_area_m2), grow=False)
    if cut is None:
        if refused is not None:
            refused.append(f"level cut refused ({L0.area:,.0f} m2 asked)")
        return None
    H, L, S, n_roads, roads_m2 = _off_the_roads(P, *cut, C, airport, law, grid)
    if L.is_empty or L.area < float(law.tables.structures.placement.cluster_pad_min_m2):
        if refused is not None:
            refused.append("no level left off the roads")
        return None
    dem = getattr(airport, "dem", None)
    rec = {"witness": WITNESS, "top_y": round(t, 3), "y_lo": round(plane - t, 3),
           "y_hi": round(-step, 3), "low_parts": len(low), "feet_on_plane": n_on,
           "feet_read": n_feet, "area_m2": round(L.area, 1),
           "cut_m2": round(valid_area(C.intersection(L)).area, 1),
           "off_roads": n_roads, "off_roads_m2": roads_m2,
           "ground_z": _ground(L, dem, near), "ground_high_z": _ground(H, dem, near)}
    return H, L, S, rec


def trim_uncut(regions: list, airport, law, reg, counts: dict) -> list:
    """Every pad region less the covered cutting no covered-cut level took
    (module docstring).  The levels and their riser strips are kept whole."""
    cov = covered_corridors(airport, law) if airport is not None else None
    if cov is None:
        return regions
    mine, keep = _cut_refs(reg)
    taken = [r.polygon for r in regions if str(r.ref) in mine and r.polygon is not None]
    R = valid_area(cov.difference(unary_union(taken))) if taken else cov
    if R.is_empty:
        return regions
    import dataclasses as _dc
    out, n, area = [], 0, 0.0
    for r in regions:
        g = r.polygon
        if str(r.ref) in keep or g is None or g.is_empty or not g.intersects(R):
            out.append(r)
            continue
        q = valid_area(g.difference(R))
        n += 1
        area += g.area - q.area
        out.extend(_dc.replace(r, polygon=x) for x in nonempty_polygon_parts(q)
                   if isinstance(x, Polygon))
    if n:
        counts["covered_cut_trimmed"] = n
        counts["covered_cut_trimmed_m2"] = round(area, 1)
    return out
