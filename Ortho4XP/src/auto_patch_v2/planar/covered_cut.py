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
MEASURED LFLL (capture replay at b8c456c9): ``building8/p1`` 53,943 m2 at
y -9.06 under t -0.06 (154 of 221 walled feet on the plane), 230.38 m flat
for the 450 m under the station where the fills stood at 239.3-239.8 m;
hard rows relaxed 280 -> 50, adjudicated census rows 415 -> 161, airside
families unchanged.

What no level takes -- a covered cutting under a pad whose unit has no
lower storey along it, a piece the level cut keeps off the airside -- is
trimmed out of every pad (:func:`trim_uncut`), as #1183 trims an open
cutting: a pad never fills a cut.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..model.planar import STRIP_SUFFIX
from .low_level import (_densest, _ground, _plane_band, _ring_poly, level_cut,
                        top_level, unit_share)

__all__ = ["WITNESS", "covered_corridors", "plan_covered", "trim_uncut"]

#: the ``witness`` a covered-cut lower level's record carries
WITNESS = "covered_cut"


def covered_corridors(airport, law, widen: float = 0.0):
    """The union of the mapped COVERED cutting corridors in the frame
    (``widen`` carriageway widths either side), or ``None``
    (``classify/pad_cut_corridor``, the one reading)."""
    from ..classify.pad_cut_corridor import cutting_corridors
    C = cutting_corridors(airport, law, covered=True, widen=widen)
    return None if C is None or C.is_empty else valid_area(C)


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
        return [y for (_xy, y), k in zip(got, inside) if k]

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
        ys = [y for y, k in zip(ys, off) if k]
    if len(ys) >= PLANE_MIN_FEET:
        return float(_densest(sorted(ys), _plane_band())[1])
    top = top_level(parts, air, airport, law, to_xy, near)
    return None if top is None else float(top[0])


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
    cut = level_cut(P, L0, air, others, law, grid, float(bp.min_area_m2))
    if cut is None:
        if refused is not None:
            refused.append(f"level cut refused ({L0.area:,.0f} m2 asked)")
        return None
    H, L, S = cut
    dem = getattr(airport, "dem", None)
    rec = {"witness": WITNESS, "top_y": round(t, 3), "y_lo": round(plane - t, 3),
           "y_hi": round(-step, 3), "low_parts": len(low), "feet_on_plane": n_on,
           "feet_read": n_feet, "area_m2": round(L.area, 1),
           "cut_m2": round(valid_area(C.intersection(L)).area, 1),
           "ground_z": _ground(L, dem, near), "ground_high_z": _ground(H, dem, near)}
    return H, L, S, rec


def trim_uncut(regions: list, airport, law, reg, counts: dict) -> list:
    """Every pad region less the covered cutting no covered-cut level took
    (module docstring).  The levels and their riser strips are kept whole."""
    cov = covered_corridors(airport, law) if airport is not None else None
    if cov is None:
        return regions
    mine = {ref for ref, rec in reg.landings.items() if rec.get("witness") == WITNESS}
    keep = mine | {ref + STRIP_SUFFIX for ref in mine}
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
