"""20g (3): A ROAD OR RAIL UNDER A PACK SOFFIT IS AN OPEN TRENCH (owner
RULINGS 2026-11-20g / 20k / 20s; spec ``docs/specs/elevated-clearance-20g-
round3-spec.md`` §B.5).

Every crossing still short at its group's planned seat (``airport/
crossing_seat``: the anchor's ground vote less the O1 cap ``dz``) is
lowered by the R6 open-trench family (``planar/viaduct_road``: the route
walk, the covered runs, the two halves, ``object_corridor.Group`` kind
``sunken_road``), which the structure pass carves out of whatever cell lies
there -- a pad, a lot, a ribbon, the ground:

* the COVERED RUN is the crossing's spanning cells grown by ``max(5 m, one
  carriageway width)``, read along the way's ROUTE (``viaduct_road._route``);
  parallel carriageways or tracks within ``dual_carriageway_max_
  separation_m`` are one trench; the floor is FLAT over the run;
* its PLANNED FLOOR is the planned seat + the least soffit ``y`` - the class
  minimum (``design_clearance_m``) - ``[elevated] clearance_margin_m``: the
  geometry only -- ``constraints/soffit_floor`` ties the floor to the SOLVED
  surface under the group's witness, so the clearance holds whatever the
  seat solves to.  Overlapping runs take the LOWEST floor (another group's
  crossing in the run is listed when its planned clearance falls under the
  need plus the margin);
* the CLIMBS: a road at ``[tunnel] ramp_grade`` / ``ramp_max_grade``, a
  rail at ``rail_ramp_grade`` / ``rail_ramp_max_grade`` (20s O4: the rail's
  graded corridor is the trench floor at rail grades); a way that ENDS in
  the group's own plan stays level at the floor to its end (the terminus,
  Law B's end wall).

REFUSED BY CLASS (``stats.refused`` and ``crossing_seat.VERDICTS``): ``airside_held``
(G1: the trench and its rim within ``[design] pad_frontage_m`` of an
airside-role cell; G3: inside an airside band's zone-2 envelope or on an
apt.dat 1206 truck route -- airside is king), ``level_seed`` (the run stands
in a two-level region's passage, ``viaduct_road._in_passage``),
``depth_cap`` (deeper than ``[cutout.sunken_road] max_depth_m`` under the
ground, 20s O5), ``no_route`` (no climb fits).  Nothing names an airport.
"""
from __future__ import annotations

import math
import statistics
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.ops import substring, unary_union

from ..airport.crossing_seat import VERDICTS, ground_reader, margin_m, seat_plan, short_crossings
from ..airport.dem import dem_z_at
from ..airport.elevated_crossing import crossable
from ..law import Law
from .structure_approach import carriageway_width_m
from .viaduct_road import _half, _in_passage, _outward, _runs, _side, _straight_m

__all__ = ["soffit_road_groups", "ID_PREFIX"]

ID_PREFIX = "soffit-road"
#: the least a run's ends stand off its crossing's cells (m)
_PAD_M = 5.0
_STEP_M = 5.0


def _key(rec, c) -> tuple:
    return (rec["unit"], c["member"], int(c["comp"]), c["way"])


def _cell_ground(cells, polys, law: Law, dem):
    """``crossing_seat.ground_reader`` on the cells (a pad keyed by its ref)."""
    return ground_reader([(p, c.role, c.ref) for p, c in zip(polys, cells, strict=True)],
                         law, dem)


def _airside_zone(airport, law: Law, cells, polys):
    """``(G1 pavement, G3 zone)``: the airside-role cells, and the airside
    bands' zone-2 envelope with the 1206 truck routes."""
    from ..airport.ground_route_ways import ground_route_ways
    from ..classify.ribbon_mint import ribbon_extent
    from .structure_service import airside_cut_roles
    cut = set(airside_cut_roles(law))
    g1 = unary_union([p for p, c in zip(polys, cells, strict=True) if c.role in cut])
    bands = ribbon_extent(cells, law, Polygon(), getattr(airport, "runways", ()))
    routes = [LineString(w.points) for w in ground_route_ways(airport)]
    return g1, unary_union([bands, *routes])


def _ways(airport, rail: bool) -> list:
    """The network's crossable ways, one per geometry (the feeds carry
    duplicates)."""
    out, seen = [], set()
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = w.tags or {}
        if len(w.points) < 2 or not crossable(tags) or bool(tags.get("railway")) != rail \
                or (not rail and not tags.get("highway")):
            continue
        k = tuple((round(x, 2), round(y, 2)) for x, y in w.points)
        if k in seen or k[::-1] in seen:
            continue
        seen.add(k)
        out.append(w)
    return out


def _cover(sel, law: Law, ways_by_id) -> "Polygon":
    """The crossings' spanning cells, grown by ``max(5 m, a carriageway)``."""
    parts = []
    for _rec, _plan, c in sel:
        w = ways_by_id.get(c["way"])
        pad = max(_PAD_M, carriageway_width_m(w.tags, law) if w is not None else 0.0)
        cells = np.asarray(c["cells"])
        h = 0.5
        g = unary_union([box(x - h, y - h, x + h, y + h) for x, y, _z in cells])
        parts.append(g.buffer(pad))
    return unary_union(parts)


def _inside(sel, zone) -> list:
    """The crossings of ``sel`` with a cell in ``zone``."""
    out = []
    for item in sel:
        cells = np.asarray(item[2]["cells"])
        if shapely.contains_xy(zone, cells[:, 0], cells[:, 1]).any():
            out.append(item)
    return out


def _terminus(route: LineString, end: float, fwd: bool, plan, pad: float
              ) -> "LineString | None":
    """The route beyond ``end`` to the way's END when it runs under the
    group's own ``plan`` all the way to that end (the station a rail ends
    in: level to it, O4) -- a way that leaves the group first climbs."""
    out = _outward(route, end, fwd)
    if plan is None or out is None or not out.within(plan.buffer(pad)):
        return None
    return out


def _level_side(route, mid, end, fwd, out, width: float):
    """A half level to the way's end, cut back where it curls tighter than
    the trench and its rim are wide (``viaduct_road._straight_m``: a tighter
    curl folds the ring); ``None`` where that is short of the run's end."""
    run = substring(route, mid, end) if fwd else \
        LineString(list(substring(route, end, mid).coords)[::-1])
    axis = run if out is None else LineString(list(run.coords) + list(out.coords)[1:])
    ok = _straight_m(axis, width)
    if ok < run.length - 1e-6:
        return None
    return axis if ok >= axis.length - 1e-6 else substring(axis, 0.0, ok)


def soffit_road_groups(airport, law: Law, cells, polys, seeds: _t.Sequence = ()
                       ) -> tuple[list, list[str], list[str]]:
    """``(groups, notes, refused)`` -- the trench halves (module doc);
    ``crossing_seat.VERDICTS`` refilled."""
    VERDICTS.clear()
    recs = tuple(getattr(airport, "elevated_crossings", ()) or ())
    if not recs:
        return [], [], []
    ground, near = _cell_ground(cells, polys, law, airport.dem)
    margin = margin_m(law)
    wanted: list[tuple] = []
    for rec in recs:
        plan = None if rec["class"] else seat_plan(rec, law, ground, near)
        for c in rec["crossings"]:
            if c["class"] or plan is None:
                VERDICTS[_key(rec, c)] = c["class"] or rec["class"]
        if plan is not None:
            wanted += [(rec, plan, c) for c in short_crossings(rec, plan, margin, ground)]
    groups: list = []
    notes: list[str] = []
    refused: list[str] = []
    zones = _airside_zone(airport, law, cells, polys) if wanted else None
    for rail in (False, True):
        sel = [t for t in wanted if t[2]["kind"].startswith("railway=") == rail]
        if sel:
            _network(airport, law, sel, rail, seeds, zones, groups, notes, refused)
    for rec, _plan, c in wanted:
        VERDICTS.setdefault(_key(rec, c), "no_route")
    return groups, notes, refused


def _network(airport, law: Law, sel, rail: bool, seeds, zones, groups, notes, refused):
    """The trenches of one network (roads, or rails)."""
    from ..law.tables import design as design_law
    tn = law.tables.structures.tunnel
    ways = _ways(airport, rail)
    by_id = {str(w.id): w for w in ways}
    cover = _cover(sel, law, by_id)
    ids = {c["way"] for _r, _p, c in sel}
    near = float(design_law(law).pad_frontage_m)
    grade, cap = ((tn.rail_ramp_grade, tn.rail_ramp_max_grade) if rail
                  else (tn.ramp_grade, tn.ramp_max_grade))
    runs = _runs(ways, cover, cover.buffer(1.0), law, 0.0, lambda w: str(w.id) in ids)
    for k, (route, s0, s1, half_w, wids) in enumerate(runs):
        rid = f"{ID_PREFIX}:{'rail' if rail else 'road'}{k}"
        run = substring(route, s0, s1)
        inside = _inside(sel, run.buffer(half_w + 1.0))
        if not inside:
            continue
        rec, plan, gov = min(inside, key=lambda t: t[2]["floor"])
        floor = float(gov["floor"])
        why = _refusal(airport, law, run, floor, seeds, near)
        # the floor face holds the whole carriageway: the wall's gap beyond it
        # (the void slopes from the ramp's edge, never over the road)
        built = None if why else _halves(airport, law, route, s0, s1, floor,
                                         half_w + tn.wall_gap_m, rec, rid, grade, cap)
        if built is None and not why:
            why = ("no_route", f"no {100 * grade:.2f} % climb from {floor:.2f} fits "
                   f"within {100 * cap:.1f} % on the mapped route or inside the run, "
                   f"or the route curls tighter than the trench and its rim are wide")
        if built is not None:
            why = _guard(built[2], zones, near)
        cls = "trench" if why is None else why[0]
        for r_, _p, c in inside:
            if VERDICTS.get(_key(r_, c)) != "trench":
                VERDICTS[_key(r_, c)] = cls
        head = (f"{rid} ({wids}): {len(inside)} crossing(s) under {rec['unit']} "
                f"({gov['member']}#{gov['comp']} soffit {gov['soffit_y']:.2f}, need "
                f"{gov['need']:.1f}, short {gov['short']:.2f})")
        if why is not None:
            refused.append(f"{head}: {why[0]} -- {why[1]}")
            continue
        a, b, _foot, depth, ramps = built
        note = (f"{head}: floor {floor:.2f} (planned seat {plan['seat']:.2f}, dz "
                f"{plan['dz']:+.2f}), depth {depth:.2f} m, trench {2 * half_w:.1f} m wide, "
                f"ramps {ramps[0]:.0f} m / {ramps[1]:.0f} m at {100 * grade:.2f} % "
                f"(RULINGS 2026-11-20g (3) / 20s)")
        groups += [a, b]
        notes.append(note)


def _refusal(airport, law: Law, run: LineString, floor: float, seeds, near: float):
    """``(class, why)`` refusing the run before its halves, or ``None``."""
    s = _in_passage(run, seeds, near)
    if s is not None:
        return ("level_seed", f"stands in unit {s.unit}'s passage level (§19 S1)")
    n = max(2, int(run.length // _STEP_M) + 1)
    zs = [dem_z_at(airport, (p.x, p.y)) for p in
          (run.interpolate(run.length * k / (n - 1)) for k in range(n))]
    zs = [z for z in zs if not math.isnan(z)]
    cap = float(law.tables.structures.cutout.sunken_road.max_depth_m)
    if zs and max(zs) - floor > cap + 1e-9:
        return ("depth_cap", f"{max(zs) - floor:.2f} m under the ground > "
                f"[cutout.sunken_road] max_depth_m {cap:.1f} (RULINGS 2026-11-20s O5)")
    return None


#: a half's axis is eased by this (m) where its offset rims fold (a kink
#: in the mapped route a trench this wide cannot follow)
_EASE_M = 1.0


def _rims_fold(axis: LineString, off: float) -> bool:
    """Whether either rim (the axis offset by ``off``, the structure pass's
    ring) folds onto itself."""
    for d in (off, -off):
        oc = axis.offset_curve(d)
        if oc.is_empty or oc.geom_type != "LineString" or not oc.is_simple:
            return True
    return False


def _eased(side, off: float):
    """``side`` ``(axis, flat_m, top_z)`` whose rims do not fold, the axis
    eased by :data:`_EASE_M` where they would (the level end scaled with
    it); ``None`` where even the eased axis folds."""
    axis, flat_m, top_z = side
    if not _rims_fold(axis, off):
        return side
    eased = axis.simplify(_EASE_M, preserve_topology=True)
    if eased.length <= 0.0 or _rims_fold(eased, off):
        return None
    return eased, flat_m * eased.length / axis.length, top_z


def _halves(airport, law: Law, route, s0, s1, floor, half_w, rec, rid, grade, cap):
    """``(half a, half b, footprint, depth, (ramp a, ramp b))`` or ``None``."""
    tn = law.tables.structures.tunnel
    rim = tn.wall_gap_m + tn.wall_band_width_m
    mid = 0.5 * (s0 + s1)
    run = substring(route, s0, s1)
    zs = [dem_z_at(airport, (p.x, p.y)) for p in
          (run.interpolate(f * run.length) for f in (0.0, 0.25, 0.5, 0.75, 1.0))]
    zs = [z for z in zs if not math.isnan(z)]
    if not zs:
        return None
    sides = []
    pad = max(_PAD_M, 2.0 * half_w)
    width = 2.0 * (half_w + rim)
    for end, fwd in ((s1, True), (s0, False)):
        out = _terminus(route, end, fwd, rec.get("plan"), pad)
        if out is not None or (fwd and end >= route.length - 1e-6) or \
                (not fwd and end <= 1e-6):
            axis = _level_side(route, mid, end, fwd, out, width)
            if axis is None:
                return None
            sides.append((axis, axis.length, floor))
            continue
        got = _side(route, mid, end, floor, half_w, airport, law, grade, cap)
        if got is None or _straight_m(got[0], width) < got[0].length - 1e-6:
            return None
        sides.append(got)
    sides = [_eased(sd, half_w + rim) for sd in sides]
    if any(sd is None for sd in sides):
        return None
    g_mid = statistics.median(zs)
    label = f"{ID_PREFIX} (20g, {rec['unit']})"
    note = (f"{ID_PREFIX}: {rec['unit']} floor {floor:.2f}",)
    a, b = f"{rid}/a", f"{rid}/b"
    ha = _half(sides[0][0], sides[0][1], sides[0][2], floor, a, b, half_w, law, g_mid,
               note, grade, label, True)
    hb = _half(sides[1][0], sides[1][1], sides[1][2], floor, b, a, half_w, law, g_mid,
               note, grade, label, True)
    foot = unary_union([s[0].buffer(half_w + rim, cap_style="flat") for s in sides])
    ramps = tuple(s[0].length - s[1] for s in sides)
    return ha, hb, foot, max(zs) - floor, ramps


def _guard(foot, zones, near: float):
    """``("airside_held", why)`` when the trench reaches airside (G1/G3)."""
    g1, g3 = zones
    if not g1.is_empty and foot.distance(g1) <= near:
        return ("airside_held", f"the trench and its rim stand within {near:.1f} m of "
                f"airside pavement (G1: airside is king)")
    if not g3.is_empty and foot.intersects(g3):
        return ("airside_held", "the trench reaches an airside band's zone-2 envelope or "
                "a 1206 truck route (G3)")
    return None
