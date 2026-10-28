"""THE LOWER LEVEL OF A STEPPED UNIT'S PAD (owner RULINGS 2026-10-19ai, #809;
amends the flat-pad cut of 2026-09-30r; follows 2026-10-19y; spec
``docs/specs/low-level-pad-spec.md``).

"Where an object carries its own one-storey step, its rigid pad gets a
second, lower level along that step, tied to the airside level, and
landside roads meet the lower level."  Measured KATL east terminal
(33.641271, −84.416453): the terminal unit ``terminal_F`` stands on ONE
held block (``building31/b0``, 79,176 m²) flat at the apron's 300.76 m
while 71,302 m² of the unit's parts are authored a storey down (base
y −13 against 0 at the apron) over ground whose DEM median is 289.5 m —
the landside roads welded to the block's rim rode up 10 m with it.

THE WITNESS IS THE OBJECT.  For each HELD block (or whole held unit) the
pack unit standing on it (the plurality of part centres inside the pad)
gives a TOP level ``t`` — the median authored base ``y`` of its parts at
the welded frontage — and its LOW parts: base ``y <= t −
[building_pad] low_level_min_step_m``.  Their plan footprints, inside the
pad, closed by ``pad_frontage_m`` and kept off the airside by the same
distance, are the LOW REGION.  Only a unit whose composed base reads
STEPPED is read (``pad_blocks.unit_base``; RULINGS 2026-10-02aj (2)).
The GROUND confirms it (#1115): the DEM median over the low region must lie
at least ``low_level_min_step_m`` under the median over the high block —
parts a storey under the frontage over level ground are a frontage raised
a storey (EDDF Terminal 1's piers), not a stepped base.

THE LEVEL IS TIED TO THE BLOCK.  The low region is minted as
``<block>/p1`` (the plane-pad grammar, ``model.planar.plane_ref``) and
registered in ``Registries.landings`` with ``kind = "low_level"``: it is an
ordinary pad (flat), and ``constraints/platform.landing_rows`` HOLDS every
vertex of it RIGID against the block's DATUM COLUMN at the object's own
lower floor, ``z = D + y_lo`` (hard, after stage 1 -- the airside never
follows it): ``y_lo`` the lowest low part, the floor the object's lower
storey stands on (#1141: "the bottom road deck sits at ground level").
``y_hi`` (= −``low_level_min_step_m``) and ``ground_z`` stay on the record
as the mint's witnesses; the ground no longer places the level (KATL: it
stood at the DEM median 289.45 m, 1.64 m over the object's floor at
287.78, and buried the roadway's towers).  Between the two levels a
RISER STRIP ``<block>/p1#strip`` (the block strip's spelling: a bank,
skipped by every pad reader) of ``max(identity spacing, 2 x grid)`` — the base-profile spec's riser
(§2 (3), Q2: the steepest cell, never a 1:3 bank under a building).

The object stage never sees a second level: ``airport/placement_read``
publishes the low pad and its strip under the BLOCK's ref at the block's
plane (``model.planar.plane_origin_ref``), so the unit is seated as one
body at the airside datum — the anchor of 19y.

THE UPPER LEVEL, ITS MIRROR (owner answer 47, 2026-10-20, #1101: "the pad
gets a second, UPPER rigid level, a storey above the airside level and
tied to it; landside lots and roads meet it").  A lot §27 read as meeting
the apron ACROSS a unit's storey (``classify.storey_edge``; it carries the
storey's authored rise, and the classifier welded it to the pad) meets the
held pad it touches at that storey: the pad's strip along the lot, of
``pad_frontage_m``, kept the same distance off the airside, is minted
``<block>/p<k>`` (``kind = "upper_level"``) with its riser strip, and
registered with ``y`` = the rise — the LANDING's rigid row, ``z = D + y``
(``constraints/platform.landing_rows``), so it stands a storey above the
block and the lot comes to it.  MEASURED LPHR (38.521557, −28.716632): the
terminal's floor at y 0 on the apron, its forecourt parapet, kerb columns
and landside hall at +6.0; the forecourt sat at the pad's 28.6 m with the
DEM at 34."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.errors import GEOSException
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.deck_signature import is_tunnel_way
from ..airport.road_ways import mapped_width_m
from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area
from ..model.planar import STRIP_SUFFIX, plane_ref
from ..model.registries import Registries

__all__ = ["LOW_KIND", "UP_KIND", "level_cut", "low_level_split", "plan_low", "plan_up",
           "stand_floor", "unit_share", "walled_feet"]

#: the ``Registries.landings`` record kind of a lower level (a ramp
#: landing's record carries no kind)
LOW_KIND = "low_level"
#: the record kind of an upper level: held like a landing (``z = D + y``)
UP_KIND = "upper_level"


def _unit_parts(P: Polygon, airport, to_xy) -> list:
    """``[(part, (x, y))]`` of the pack unit holding the plurality of part
    centres inside ``P`` (one unit, one authored frame)."""
    return unit_share(P, airport, to_xy)[1]


def unit_share(P: Polygon, airport, to_xy) -> "tuple[int | None, list]":
    """``(unit index, [(part, (x, y))])``: :func:`_unit_parts` with the
    partition unit it read (``None`` and ``[]`` where no part stands in
    ``P``)."""
    part = getattr(airport, "partition", None)
    if part is None:
        return None, []
    by: dict[int, list] = {}
    for ui, u in enumerate(part.units):
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False):
                    continue
                xy = to_xy(p.lon, p.lat)
                if P.contains(Point(xy)):
                    by.setdefault(ui, []).append((p, xy))
    if not by:
        return None, []
    return max(by.items(), key=lambda kv: (len(kv[1]), -kv[0]))


def _ring_poly(rg, to_xy) -> "Polygon | None":
    if len(rg) < 3:
        return None
    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
    g = g if g.is_valid else g.buffer(0.0)
    return None if g.is_empty else g


def _stands_xy(airport, to_xy) -> list:
    """The aircraft stands and jetways (``airside_group_seat.stands_in``)
    in the frame, read off the apt.dat the airport was loaded from."""
    from ..airport.airside_group_seat import stands_in
    pack = getattr(airport, "pack", None)
    got = stands_in(str(getattr(pack, "apt_dat_path", "") or ""),
                    str(getattr(airport, "icao", "") or ""))
    return [to_xy(lo, la) for la, lo in got]


def _densest(ys: _t.Sequence[float], band: float) -> "tuple[int, float]":
    """``(count, median)`` of the ``band``-wide window holding most of
    ``ys`` (sorted ascending)."""
    best, med, j = 0, 0.0, 0
    for i in range(len(ys)):
        while ys[i] - ys[j] > band:
            j += 1
        if i - j + 1 > best:
            best, med = i - j + 1, ys[(i + j) // 2]
    return best, med


def walled_feet(parts, law, to_xy) -> "tuple[list, list]":
    """``(frame xy, y)`` of the ground-contact feet of the WALLED parts of
    ``parts`` (``[(part, xy)]``; ``[placement] chain_min_height_m``)."""
    wall_min = float(law.tables.structures.placement.chain_min_height_m)
    xy, ys = [], []
    for p, _xy in parts:
        if getattr(p, "line", False) or float(getattr(p, "height_m", 0.0) or 0.0) < wall_min:
            continue
        for f in getattr(p, "feet", ()) or ():
            xy.append(to_xy(float(f[1]), float(f[0])))
            ys.append(float(f[2]))
    return xy, ys


def stand_floor(parts, air, stands, law, to_xy) -> "tuple[float, _t.Any, _t.Any, _t.Any] | None":
    """``(t, X, Y, at)``: the stand-side airside floor plane ``t`` of the
    walled feet of ``parts`` (``airside_group_seat.floor_plane`` over the
    feet touching ``air`` within ``STAND_M`` of a stand, RULINGS
    2026-10-23b), the feet's frame xy ``X``, their ``Y`` and the mask
    ``at`` of the feet that read it -- or ``None`` where too few do."""
    import numpy as np
    import shapely

    from ..airport import airside_group_seat as ag
    if not stands or air is None or air.is_empty:
        return None
    xy, ys = walled_feet(parts, law, to_xy)
    if len(ys) < ag.PLANE_MIN_FEET:
        return None
    X = np.asarray(xy, dtype=float)
    Y = np.asarray(ys, dtype=float)
    touch = shapely.contains_xy(air.buffer(ag.TOUCH_M), X[:, 0], X[:, 1])
    near = np.zeros(len(ys), dtype=bool)
    hit = STRtree(shapely.points(np.asarray(stands, dtype=float))).query(
        shapely.points(X), predicate="dwithin", distance=ag.STAND_M)
    near[hit[0]] = True
    at = touch & near
    if int(at.sum()) < ag.PLANE_MIN_FEET:
        return None
    return -float(ag.floor_plane([-float(y) for y in Y[at]], ag.storey_m(law))), X, Y, at


def feet_levels(parts, air, stands, law, to_xy) -> "tuple[float, float | None] | None":
    """THE TWO FOOT LEVELS (module docstring, RULINGS 2026-10-23b):
    ``(t, y_low)`` of the unit ``parts`` (``[(part, xy)]``) -- ``t`` the
    stand-side airside floor plane of its walled feet (:func:`stand_floor`),
    ``y_low`` the lower storey's plane or ``None`` (one level) -- or
    ``None`` where too few walled feet touch the airside near a stand to
    read one (``stands``: frame xy; ``to_xy(lon, lat)`` the frame's
    entry)."""
    from ..airport import airside_group_seat as ag
    got = stand_floor(parts, air, stands, law, to_xy)
    if got is None:
        return None
    t, _X, Y, _at = got
    ys = Y.tolist()
    low = sorted(float(y) for y in Y if y <= t - 2.0 * ag.PLANE_BAND_M)
    need = max(ag.PLANE_MIN_FEET, int(ag.PLANE_SHARE * len(ys) + 0.999999))
    n, med = _densest(low, ag.PLANE_BAND_M) if low else (0, 0.0)
    return t, (med if n >= need else None)


def plan_low(P, air, airport, law, grid: float, others=None, refused=None
             ) -> "tuple[_t.Any, _t.Any, _t.Any, dict] | None":
    """``(high, low, strip, record)`` for one held pad ``P`` (module
    docstring), or ``None`` where its unit carries no lower storey — or
    where the ground under the low region does not lie at least that
    storey under the ground of the high block (#1115; the reason is
    appended to ``refused``).

    EVERY OPERAND IS A VALID AREA (#1098): a held pad, the apron or a
    neighbour pad may arrive self-touching or on a fixed precision model,
    and an overlay of the low region against it then raised ``side
    location conflict`` and cost the airport its whole patch (EDDF).
    ``geom/valid_area`` reads each one's area before it is cut."""
    P, air = valid_area(P), valid_area(air)
    bp = law.tables.structures.building_pad
    step_min = float(getattr(bp, "low_level_min_step_m", 0.0) or 0.0)
    if step_min <= 0.0:
        return None
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    pmin = float(bp.min_area_m2)
    to_xy = airport.frame.entry()
    parts = _unit_parts(P, airport, to_xy)
    if not parts:
        return None
    # THE SEAT'S TWO FOOT LEVELS where the airport names its stands (module
    # docstring, RULINGS 2026-10-23b); else the round-3 frontage reading
    lv = feet_levels(parts, air, _stands_xy(airport, to_xy), law, to_xy)
    if lv is not None and lv[1] is not None:
        t, y_feet = lv
        step_min = 2.0 * _plane_band()
    else:
        y_feet = None
        front = air.buffer(near)
        top_ys = [p.base_y for p, _xy in parts
                  if any((g := _ring_poly(rg, to_xy)) is not None and g.intersects(front)
                         for rg in p.rings)]
        if not top_ys:
            return None
        # THE FRONTAGE LEVEL: the base most of the frontage parts stand at (a
        # canopy edge or a roof trim at the frontage stands ABOVE it, a buried
        # sill below — neither is the floor the apron meets)
        t = min(_st.multimode(round(y) for y in top_ys))
    low_parts = [p for p, _xy in parts if p.base_y <= t - step_min]
    if not low_parts:
        return None
    polys = [g for p in low_parts for rg in p.rings
             if (g := _ring_poly(rg, to_xy)) is not None]
    if not polys:
        return None
    cut = level_cut(P, unary_union(polys), air, others, law, grid, pmin, airport)
    if cut is None:
        return None
    H, L, S = cut
    dem = getattr(airport, "dem", None)
    g_lo, g_hi = _ground(L, dem, near), _ground(H, dem, near)
    if y_feet is None and (g_lo is None or g_hi is None or g_hi - g_lo < step_min):
        # THE GROUND IS THE OTHER HALF OF THE WITNESS (#1115): a storey of
        # the object stands a storey down only where its own ground does.
        # MEASURED EDDF Terminal 1: frontage parts at y 6-17 (piers, decks)
        # made the unit's ground-floor parts "low", over ground 0.1 m and
        # -5.9 m from the block's — a lower level 3 m into level ground
        # that relaxed 1,092 pad rows.  KATL ``terminal_F``: 11.7 m down.
        if refused is not None:
            refused.append(f"ground drop {_fmt(g_hi, g_lo)} < {step_min:g} m")
        return None
    # the lower storey's FLOOR: its walls' plane where the feet read it,
    # else the lowest low part (KATL: both -13)
    y_floor = (y_feet if y_feet is not None else min(p.base_y for p in low_parts)) - t
    rec = {"witness": "feet" if y_feet is not None else "frontage", "top_y": round(t, 3),
           "y_lo": round(y_floor, 3), "y_hi": round(-step_min, 3),
           "low_parts": len(low_parts), "area_m2": round(L.area, 1),
           "ground_z": g_lo, "ground_high_z": g_hi}
    return H, L, S, rec


def level_cut(P, L0, air, others, law, grid: float, hmin: float, airport=None
              ) -> "tuple[_t.Any, _t.Any, _t.Any] | None":
    """``(high, low, strip)``: the low region ``L0`` cut out of the held pad
    ``P`` as a level -- closed by ``pad_frontage_m``, kept that distance off
    the airside ``air`` and a riser's width off the pads ``others``, at
    least a unit pad's worth of ground -- with its riser strip and the high
    block left (of at least ``hmin`` m2), or ``None``."""
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    L = L0.buffer(near, join_style=2).buffer(-near, join_style=2)
    if airport is not None:
        L = _with_roads(L, P, airport, law, near)
    L = valid_area(valid_area(L.intersection(P)).difference(air.buffer(near, join_style=2)))
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    if others is not None and not others.is_empty:
        # ANOTHER PAD the low level touches keeps its own floor (two pads
        # may sit at different floors, ``step_exemption_pad_to_pad``): the
        # riser runs along it too, never one vertex at two levels
        # (MEASURED KATL: ``building34`` / ``building36`` at the apron's level
        # shared 10 vertices with the low level and held it up)
        L = valid_area(L.difference(valid_area(others).buffer(w, join_style=2)))
    keep = [q for q in nonempty_polygon_parts(L) if q.area >= pmin]
    # A STOREY OF THE UNIT, not a sill: the low level is a unit pad's worth
    # of ground (``[placement] cluster_pad_min_m2``, the §30 (4) bar) —
    # MEASURED KATL ``building11``: two parts 7 m down over 571 m² asked a
    # 3 m drop of ground the apron holds, and the band was relaxed
    if sum(q.area for q in keep) < float(law.tables.structures.placement.cluster_pad_min_m2):
        return None
    L = valid_area(unary_union(keep))
    # a MITRE buffer can come back self-crossing (MEASURED KMCI
    # ``building26/b1``, #1214 round 6: the riser's cut raised ``Ring edge
    # missing`` and cost the block its lower level) -- its valid area
    L = _with_orphans(L, P, air, others, w, near, grid)
    Lw = valid_area(L.buffer(w, join_style=2))
    S = valid_area(_overlay(valid_area(_overlay(P, Lw, "intersection", grid)), L,
                            "difference", grid))
    H = valid_area(_overlay(P, Lw, "difference", grid))
    if H.is_empty or H.area < hmin:
        return None                  # the frontage block must stay a block
    return H, L, S


def _with_roads(L, P, airport, law, near: float):
    """A ROAD OVER THE LOWER LEVEL IS ON IT (#1291; owner RULINGS
    2026-10-24a): the low region ``L`` plus every mapped road's carriageway
    over the pad ``P`` that meets it, closed again by ``near``.

    The low parts' footprints leave the roads between them out -- a road
    is no part of the object -- so the block kept the corridor at its own
    level and the roads rode it: MEASURED KMCI ``building26/b1``, the
    covered road and the passages between the terminal and the garage's
    lower floor stood on two 8 m block strips 2.4 m over the lower level
    (the owner's "twin 2m tall road ridges ... that should be flat at the
    lower level"), with the road ribbons spanning the riser.  The corridor
    is the way's mapped carriageway (``airport/road_ways.mapped_width_m``
    at the ``[tunnel]`` lane law); a bridge's corridor counts too (the
    ground under a bridge is the ground the road beneath runs on), a bore
    never (it runs under the pad).  Each corridor joins only within one
    carriageway width of ``L``: a road that merely touches the lower level
    and runs on over the block never carries the low level with it."""
    if L.is_empty:
        return L
    tn = law.tables.structures.tunnel
    admitted = tuple(tn.admitted_values)
    add = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if not tags.get("highway") or len(w.points) < 2 or is_tunnel_way(tags, admitted):
            continue
        width = mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)
        c = LineString(w.points).buffer(0.5 * width, cap_style="flat")
        if not c.intersects(P) or c.distance(L) > near:
            continue
        add.append(valid_area(_overlay(valid_area(c), P, "intersection", 0.01))
                   .intersection(L.buffer(width, join_style=2)))
    if not add:
        return L
    return (valid_area(unary_union([L, *add]))
            .buffer(near, join_style=2).buffer(-near, join_style=2))


def _with_orphans(L, P, air, others, w: float, near: float, grid: float):
    """THE BLOCK IS ITS AIRSIDE FRONTAGE (#1291; owner RULINGS 2026-10-24a):
    a piece of the high block the lower level (with its roads) cuts off from
    the frontage -- one that comes no nearer the airside than ``near`` plus
    the riser ``w`` -- has no airside to stand level with, so it is the lower
    level too.  MEASURED KMCI ``building26/b1``: a 5.7 m block island
    between the covered road and the garage, and the bands along the
    garage's far walls the roads cross into its ground-level floor, each
    2.4 m over the lower level beside it.

    The grown level is read by SUBTRACTION -- the pad less the kept block
    and its riser, the airside frontage and the other pads -- so it keeps
    the pad's own edge vertex for vertex (a re-buffered edge minted a
    0.25 m2 tunnel-ramp sliver against the pad's rim and spiked the ramp)."""
    H = valid_area(_overlay(P, valid_area(L.buffer(w, join_style=2)), "difference", grid))
    parts = nonempty_polygon_parts(H)
    keep = [q for q in parts if q.distance(air) <= near + w]
    if not keep or len(keep) == len(parts):
        return L
    cut = [valid_area(unary_union(keep).buffer(w, join_style=2)),
           valid_area(air.buffer(near, join_style=2))]
    if others is not None and not others.is_empty:
        cut.append(valid_area(valid_area(others).buffer(w, join_style=2)))
    return valid_area(_overlay(P, valid_area(unary_union(cut)), "difference", grid))


def _plane_band() -> float:
    from ..airport.airside_group_seat import PLANE_BAND_M
    return float(PLANE_BAND_M)


def _overlay(a, b, op: str, grid: float):
    """``a.<op>(b)`` -- retried on the arrangement's precision grid where
    GEOS still refuses two valid floating operands."""
    import shapely
    try:
        return getattr(a, op)(b)
    except GEOSException:
        g = max(float(grid), 0.01)
        return getattr(shapely, op)(shapely.set_precision(a, g),
                                    shapely.set_precision(b, g), grid_size=g)


def _fmt(g_hi, g_lo) -> str:
    return "n/a" if g_hi is None or g_lo is None else f"{g_hi - g_lo:+.2f}"


def plan_up(P, air, lots, rise: float, law, grid: float, others=None
            ) -> "tuple[_t.Any, _t.Any, _t.Any, dict] | None":
    """``(high, upper, strip, record)`` for one held pad ``P`` touching the
    storey lots ``lots`` (one geometry) whose storey stands ``rise`` above
    the pad's floor (module docstring), or ``None``."""
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    w = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    U = (P.intersection(lots.buffer(near, join_style=2))
         .difference(air.buffer(near + w, join_style=2)))
    if others is not None and not others.is_empty:
        U = U.difference(others.buffer(w, join_style=2))
    # a piece the riser could not stand beside is no level
    keep = [q for q in nonempty_polygon_parts(U) if q.area >= near * 2.0 * w]
    if not keep:
        return None
    U = unary_union(keep)
    S = P.intersection(U.buffer(w, join_style=2)).difference(U)
    H = P.difference(U.buffer(w, join_style=2))
    if H.is_empty or H.area < pmin:
        return None
    return H, U, S, {"y": round(float(rise), 3), "area_m2": round(U.area, 1)}


def _ground(L, dem, step: float) -> "float | None":
    """THE LOWER LEVEL'S OWN GROUND: the median DEM over its AREA (a grid
    of ``step`` metres, at least 400 samples' worth) — never its ring's
    mean, whose riser side stands on the slope up to the block (MEASURED
    KATL: the ring read 292.9 m, the area 289.5)."""
    import math
    if dem is None or L.is_empty:
        return None
    x0, y0, x1, y1 = L.bounds
    h = max(step, math.sqrt(L.area / 400.0))
    zs = []
    y = y0 + 0.5 * h
    while y < y1:
        x = x0 + 0.5 * h
        while x < x1:
            if L.contains(Point(x, y)):
                try:
                    z = float(dem.z(x, y))
                except Exception:  # noqa: BLE001 — off the raster
                    z = float("nan")
                if z == z:
                    zs.append(z)
            x += h
        y += h
    return round(_st.median(zs), 3) if zs else None


def low_level_split(out: list, air_polys: _t.Sequence[Polygon], airport,
                    law, grid: float, counts: dict, *, reg: Registries,
                    storey_lots: _t.Sequence = (),
                    air_all: _t.Sequence | None = None,
                    beyond: _t.Sequence = (),
                    lots: _t.Sequence = ()) -> list:
    """The pad regions ``out`` with every held block whose unit carries a
    lower storey split into its high block, its low level ``<ref>/p1`` and
    the riser strip (module docstring); each low level registered in
    ``reg.landings``.  ``storey_lots`` — ``(polygon, rise)`` of the lots
    met across a storey — give the held pads they touch an UPPER level.
    Each lower level then extends over its group's lower footprint
    (``planar/low_extent``, #1306/#1302), kept off ``air_all`` -- every
    airside or structure REGION, the zones among them (default: ``air_polys`` as
    pavement); ``beyond`` the apron pieces no aircraft reaches once the
    pads stand (``planar/reach_after_pads``), which it takes in; ``lots``
    the parking lots a level's fill band is cut along (``planar/low_fill``)."""
    from ..airport.obj8_grade import STEPPED
    from .group_low import plan_group_low
    from .pad_blocks import unit_base
    if (airport is None or getattr(airport, "frame", None) is None
            or not air_polys):
        return out
    held = reg.held
    tree = STRtree(list(air_polys))
    groups: dict[str, list] = {}
    for r in out:
        ref = str(r.ref)
        h = held.get(ref)
        if h is not None and r.polygon is not None:
            groups.setdefault(ref, []).append(r)
    done: dict[str, list | None] = {}
    floor_of = _group_floors(airport, air_polys, tree, law)
    for ref, regs in sorted(groups.items()):
        if held[ref].get("conforming"):
            continue
        P = unary_union([r.polygon for r in regs])
        if P.is_empty:
            continue
        air = unary_union([air_polys[int(j)] for j in
                           tree.query(P.buffer(50.0), predicate="intersects")])
        if air.is_empty:
            continue
        others = unary_union([r.polygon for r in out if str(r.ref) != ref
                              and r.polygon is not None and r.polygon.intersects(P.buffer(1.0))])
        try:
            why: list = []
            got = (plan_low(P, air, airport, law, grid, others, why)
                   if unit_base(P, airport)[0] == STEPPED else None)
            if got is None:
                # a pad holding ONE level a storey under its group's floor
                # is the group's lower level (``planar/group_low``, #1214
                # round 7: LFPG T2's trench pads)
                gwhy: list = []
                got = plan_group_low(P, air, airport, law, grid, others, floor_of, gwhy)
                if gwhy:
                    k = "low_level_group_refused"
                    counts[k] = counts.get(k, 0) + 1
                    counts.setdefault(k + "_list", []).append(f"{ref}: {gwhy[0]}")
                if got is not None:
                    why = []
                    counts["low_level_group"] = counts.get("low_level_group", 0) + 1
        except GEOSException as exc:
            # an overlay GEOS still refuses on valid areas: the block stays
            # ONE level (the pre-#809 pad) and the refusal is counted, never
            # a lost airport (#1098)
            counts["low_level_refused"] = counts.get("low_level_refused", 0) + 1
            counts.setdefault("low_level_refused_list", []).append(f"{ref}: {exc}")
            continue
        if got is None:
            if why:
                counts["low_level_no_ground_step"] = counts.get("low_level_no_ground_step", 0) + 1
                counts.setdefault("low_level_no_ground_step_list", []).append(f"{ref}: {why[0]}")
            continue
        H, L, S, rec = got
        tmpl = regs[0]
        low = plane_ref(ref, 1)
        done[ref] = ([_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(H)]
                     + [_dc.replace(tmpl, ref=low, polygon=q) for q in nonempty_polygon_parts(L)]
                     + [_dc.replace(tmpl, ref=low + STRIP_SUFFIX, polygon=q)
                        for q in nonempty_polygon_parts(S)])
        reg.landings[low] = {"block": ref, "y": rec["y_lo"], "deck": None,
                             "kind": LOW_KIND, **rec}
    _upper_split(groups, done, out, tree, air_polys, storey_lots, law, grid, reg)
    if not done:
        return out
    from .low_extent import AirRegion, extend_levels
    res: list = []
    for r in out:
        ref = str(r.ref)
        if ref in done:
            if done[ref] is not None:
                res.extend(done[ref])
                done[ref] = None
            continue
        res.append(r)
    res = extend_levels(res, reg, air_all if air_all is not None
                        else [AirRegion(g, "cell") for g in air_polys],
                        airport, law, grid, counts, beyond)
    # 28s (3) (#1572): a lower level's fill along a lot is cut off
    from .low_fill import cut_fill_bands
    res = cut_fill_bands(res, reg, lots, airport, law, grid, counts, LOW_KIND)
    counts["low_levels"] = sum(1 for v in reg.landings.values() if v.get("kind") == LOW_KIND)
    counts["low_level_list"] = "; ".join(
        f"{k} on {v['block']} band [{v['y_lo']:+.2f}, {v['y_hi']:+.2f}] {v['area_m2']:g} m2"
        for k, v in sorted(reg.landings.items()) if v.get("kind") == LOW_KIND)
    counts["upper_levels"] = "; ".join(
        f"{k} on {v['block']} +{v['y']:.2f} {v['area_m2']:g} m2"
        for k, v in sorted(reg.landings.items()) if v.get("kind") == UP_KIND)
    return res


def _group_floors(airport, air_polys, tree, law) -> _t.Callable[[int], _t.Any]:
    """``ui -> group_low.group_floor`` of the partition unit, memoised per
    split (one stand read, the airside about each unit)."""
    from .group_low import group_floor
    to_xy = airport.frame.entry()
    stands = _stands_xy(airport, to_xy)
    cache: dict = {}

    def air_of(poly):
        return unary_union([air_polys[int(j)] for j in tree.query(poly, predicate="intersects")])
    return lambda ui: group_floor(ui, airport, air_of, stands, law, to_xy, cache)


def _upper_split(groups, done, out, tree, air_polys, storey_lots, law,
                 grid: float, reg: Registries) -> None:
    """THE UPPER LEVELS (module docstring): every held pad in ``groups``
    touching a storey lot -- a block a lower level split keeps it, as
    ``<block>/p2`` on its high remainder (RULINGS 2026-10-23b: a two-level
    group's pads at both levels, the upper one where the lots meet it)."""
    if not storey_lots:
        return
    lots = [g for g, _y in storey_lots]
    ltree = STRtree(lots)
    for ref, regs in sorted(groups.items()):
        lower = done.get(ref) or []
        high = [r for r in lower if str(r.ref) == ref] if lower else regs
        rest = [r for r in lower if str(r.ref) != ref]
        P = unary_union([r.polygon for r in high])
        hit = [int(j) for j in ltree.query(P, predicate="dwithin", distance=max(grid, 0.01))]
        if P.is_empty or not hit:
            continue
        air = unary_union([air_polys[int(j)] for j in
                           tree.query(P.buffer(50.0), predicate="intersects")])
        others = unary_union([r.polygon for r in out if str(r.ref) != ref
                              and r.polygon is not None and r.polygon.intersects(P.buffer(1.0))]
                             + [r.polygon for r in rest if r.polygon is not None])
        got = plan_up(P, air, unary_union([lots[j] for j in hit]),
                      min(storey_lots[j][1] for j in hit), law, grid, others)
        if got is None:
            continue
        H, U, S, rec = got
        tmpl = regs[0]
        up = plane_ref(ref, 2 if rest else 1)
        done[ref] = ([_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(H)]
                     + rest
                     + [_dc.replace(tmpl, ref=up, polygon=q) for q in nonempty_polygon_parts(U)]
                     + [_dc.replace(tmpl, ref=up + STRIP_SUFFIX, polygon=q)
                        for q in nonempty_polygon_parts(S)])
        reg.landings[up] = {"block": ref, "deck": None, "kind": UP_KIND, **rec}
