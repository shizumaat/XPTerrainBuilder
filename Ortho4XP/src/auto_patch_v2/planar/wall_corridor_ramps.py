"""THE WALL CORRIDORS AS STRUCTURES TO BUILD (RULINGS 2026-09-08m / 08n
LAW C; spec ``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md`` §6):
the readings of ``airport/wall_corridors.py`` turned into the build
groups ``planar/structures.py`` runs through its ONE ramp / void / rim
machinery (the 05n object-corridor path, the 08b/c door path).

Per record: s = 0 at the MOUTH end (a closed end's floor overlapping the
end wall by ``cutout.floor_overlap_m``, or a level corridor half's
midpoint — capless, sharing the mouth line with its sibling half); the
"walls" are the two bands, their inner faces the ramp's
edges, the rim ``rim_standoff`` of each band's measured thickness
inside the wall (09-08a); the FLOOR is the wall bottom per station
(``Group.profile``, pinned by the generator — level or descending, cut
as authored); a LEVEL corridor / a BAY climbs beyond its open end at
``ramp_grade`` (``Group.climb_from_s`` = the wall end, moved back to the
COVERING PLATE's edge by §34 (9) (5) where the walls protrude past the
building — owner RULINGS 2026-09-14be) and STOPS at airside pavement,
steepening to ``max_ramp_grade`` (``stop_side``) or, at a road, at the
road's TRUE edge (§34 (9)/(10), :func:`road_true_edge`); a
GARAGE RAMP has no climb (its own floor meets the ground at the open
end).  Roles: ``wall_corridor_ramp`` (level / bay), ``garage_ramp``
(descending).  ``seat = "none"``: never plate-seated, the family excluded
from the re-seat.
"""
from __future__ import annotations

import typing as _t

import math

import os

import shapely
from shapely import affinity as _affinity
from shapely.geometry import LineString, Point

from ..law import Law
from ..airport import obj8
from ..law.cutout_schema import WALL_BOTTOM
from ..law.tables import role_side
from ..model.frame import XY
from ..model.structures import profile_z
from ..airport.wall_corridors import CLASS_GARAGE
from .object_corridor import Group
from .structure_approach import unit
from .structure_geometry import pad_hit as _pad_hit, rim_standoff

__all__ = ["wall_corridor_groups", "RAMP_ROLE", "GARAGE_ROLE", "KIND", "airside_stops",
           "locked_road_stops", "ROAD_ROLES", "road_edge_witness", "road_true_edge",
           "stop_and_steepen",
           "wall_corridor_profile", "wall_corridor_note"]

#: The groundside ROAD family §34 (9) can pinch a ramp against.  A parking
#: lot is not a road (it is a place, and §24's pad law governs it).
ROAD_ROLES = ("service_road", "service_junction", "groundside_pavement")

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

KIND = "wall_corridor"
RAMP_ROLE = "wall_corridor_ramp"
GARAGE_ROLE = "garage_ramp"


def _interp(sts, s: float, attr_l: str, attr_r: str) -> tuple[float, float]:
    if s <= sts[0].s + 1e-9:
        return getattr(sts[0], attr_l), getattr(sts[0], attr_r)
    if s >= sts[-1].s - 1e-9:
        return getattr(sts[-1], attr_l), getattr(sts[-1], attr_r)
    for a, b in zip(sts[:-1], sts[1:]):
        if a.s <= s <= b.s:
            f = (s - a.s) / max(b.s - a.s, 1e-9)
            return (getattr(a, attr_l) + (getattr(b, attr_l) - getattr(a, attr_l)) * f,
                    getattr(a, attr_r) + (getattr(b, attr_r) - getattr(a, attr_r)) * f)
    return getattr(sts[-1], attr_l), getattr(sts[-1], attr_r)


def wall_corridor_groups(records: _t.Sequence, law: Law) -> list[Group]:
    """Law C: one group per record (module doc)."""
    tn = law.tables.structures.tunnel
    co = law.tables.structures.cutout
    wc = co.wall_corridor
    if wc.mouth_depth != WALL_BOTTOM:
        raise ValueError(f"cutout.wall_corridor.mouth_depth {wc.mouth_depth!r}: only "
                         f"{WALL_BOTTOM!r} is generated")
    grid = law.tables.emit.identity.min_distinct_spacing_m
    osm_rim = tn.wall_gap_m + tn.wall_band_width_m

    def standoff(t: float) -> float:
        return rim_standoff(t, co)[1]
    out: list[Group] = []
    for r in records:
        axis = list(r.axis)
        sts = r.stations
        L = r.length_m
        u0 = unit(axis[0], axis[1])
        u_end = unit(axis[-2], axis[-1])
        inward = (-u0[0], -u0[1])
        garage = r.cls == CLASS_GARAGE

        def half_fn(s: float, _sts=sts) -> tuple[float, float]:
            # §47 (1): the floor ring IS the walls' inner faces exactly
            return _interp(_sts, s, "half_l", "half_r")

        def rim_fn(s: float, _sts=sts, _b=osm_rim) -> tuple[float, float]:
            if s > _sts[-1].s + 1e-6:
                return _b, _b
            tl, tr = _interp(_sts, s, "thick_l", "thick_r")
            return standoff(tl), standoff(tr)
        reach = tn.max_ramp_length_m + 2.0 * osm_rim
        path = axis if garage else axis + [(axis[-1][0] + u_end[0] * reach,
                                            axis[-1][1] + u_end[1] * reach)]
        out.append(Group([], axis[0], inward, r.width_m, path, r, r.id, L, not garage,
                         r.mouth_closed, False, half_fn, rim_fn,
                         standoff(r.mouth_thickness_m) if r.mouth_closed else None, None,
                         0.0 if garage else wc.ramp_grade, kind=KIND,
                         max_grade=wc.ramp_grade, spacing_m=wc.station_m, climb_from_s=L,
                         stop_at_pavement=not garage, profile=tuple(r.profile),
                         stop_side="airside", mouth_strip=False,
                         sibling=r.sibling, ramp_role=GARAGE_ROLE if garage else RAMP_ROLE))
    return out


# ── the build-time helpers ``planar/structures.build_structures`` calls ──

def airside_stops(cells, polys, law: Law, runway_family) -> list:
    """What a wall-corridor ramp STOPS at (RULINGS 2026-09-08m (a)/(b), spec
    §6a row 14): AIRSIDE cells and building pads, never a structure or
    the runway family; a groundside road across the ramp yields onto it."""
    return [(p, c.ref) for p, c in zip(polys, cells)
            if c.kind != "structure" and c.role not in runway_family
            and (role_side(law, c.role) == "airside" or c.role == "building")]


def locked_road_stops(cells, polys, law: Law, runway_family, airside_reach_m: float,
                      half_out: dict | None = None) -> list:
    """THE SERVICE ROADS LOCKED TO AIRSIDE (spec §34 (9), owner RULINGS
    2026-09-14ak) — ``[(polygon, ref)]``, the stops a corridor's climb-out
    may be PINCHED against.

    A groundside road is locked to airside when its level is not its own to
    give: it edge-shares with (or is absorbed into) airside pavement — the
    free-road ruling — or it stands within ``airside_reach_m``
    (``emit.roads.contact_reach_m``, §37 (10) (1)) of an airside face's
    edge, where §37 (10) gives its end THAT face's solved level.  Such a
    road cannot yield to a ramp: pulling it down would pull airside through
    the contact, and airside is king.  So the ramp ends at its edge instead
    (:func:`stop_and_steepen`).

    A road with no airside contact is NOT locked — it is free to follow the
    ramp, and nothing here stops the climb."""
    air = [p for p, c in zip(polys, cells)
           if c.kind != "structure" and c.role not in runway_family
           and role_side(law, c.role) == "airside"]
    if not air:
        return []
    tree = shapely.STRtree(air)
    roads = [(p, c) for p, c in zip(polys, cells)
             if c.kind != "structure" and c.role in ROAD_ROLES]
    out = []
    for p, c in roads:
        near = p.buffer(airside_reach_m)
        if not any(air[int(j)].distance(p) <= airside_reach_m + 1e-9
                   for j in tree.query(near, predicate="intersects")):
            continue
        # §34 (9) (6) (owner RULINGS 2026-09-14bb: "the ramps are coming to
        # the centerline of the road, so increase the road margin by a
        # half-width"): the edge a pinched ramp ends at is the road's TRUE
        # edge, so the stop geometry stands the road's HALF-WIDTH outside
        # its face.  Measured at OTHH: route7 and route9 each emit TWO
        # ribbons sharing their long edge — that shared edge IS the
        # centreline and each face is one half-carriageway (3.77 m / 3.15 m
        # wide), so the ramp stopping at a face edge stops a half-width
        # short of where the road really ends.
        half = _road_half_width_m(p, c, roads)
        if half_out is not None:
            half_out[c.ref] = half
        out.append((road_true_edge(p, c, roads), c.ref))
    return out


def road_true_edge(poly, cell, roads):
    """THE ROAD'S TRUE EDGE (spec §34 (10), owner RULINGS 2026-09-14bb /
    14bc / 14bd: "we should generalize this to allow this margin for ramps
    arriving at a road, not special case it for OTHH") — THE ONE
    DERIVATION every ramp emitter that arrives at a road reads.

    The road as a ramp must see it: its own emitted face grown to the
    carriageway the road actually carries — the centreline offset by
    :func:`_road_half_width_m` on EVERY side.  A ramp arriving from any
    side therefore ends at the true edge on ITS side and the road ribbon
    is never cut; the "side" of §34 (10) is where the ramp meets this
    region, not a parameter, so there is nothing per-consumer to get
    wrong and no per-airport key anywhere.

    THE CONSUMER CENSUS (owner RULINGS 2026-08-30l) that ruled this ONE
    site, over every ramp emitter §34 (10) names:

    * the PINCHED corridor climb (§34 (9), :func:`locked_road_stops` ->
      :func:`stop_and_steepen`) — reads road cells: HERE;
    * the §34 (8) mouth CLIMB-OUT and the tunnel-object / door ramp
      (``planar/object_corridor``'s ``stop_at_pavement``) — they consume
      the stop set ``planar/structures.build_structures`` assembles from
      every governed cell, ROAD_ROLES included: HERE, at that one list;
    * the Law C airside stop set (:func:`airside_stops`) — airside faces
      and building pads only; a road reaches it solely through
      :func:`locked_road_stops`, so it inherits this and needs nothing;
    * the BASIN ramp (§24 (8), ``planar/basin_geometry``) and
      ``planar/structure_approach`` — neither reads a role or a road: the
      first is the plan geometry of the object's OWN rim/floor/ramp
      corridors, the second computes mouths, chains and deck intervals
      off mapped WAYS.  Nothing to rule.

    So: one derivation, two call sites, both in ``planar/structures.py``.
    """
    half = _road_half_width_m(poly, cell, roads)
    return poly if half <= 0.0 else poly.buffer(half, **_MITRE)


def _road_half_width_m(poly, cell, roads) -> float:
    """THE ROAD'S HALF-WIDTH (spec §34 (9) (6)) from the geometry the road
    ACTUALLY carries: the emitted face's ribbon width — the short side of
    its minimum rotated rectangle.

    A carriageway emitted as TWO ribbons sharing their long edge (the
    centreline) gives each face one HALF of the road, so the face's own
    width is the half-width; a carriageway emitted whole gives the full
    width, and the half-width is half of it.  Which one this is, is read
    from the layout: a sibling face of the SAME road that shares a long
    edge with this one."""
    mrr = poly.minimum_rotated_rectangle
    cs = list(mrr.exterior.coords)[:-1]
    if len(cs) < 4:
        return 0.0
    w = min(math.dist(cs[i], cs[(i + 1) % 4]) for i in range(4))
    base = str(cell.ref).split("#")[0]
    halved = any(q is not poly and str(d.ref).split("#")[0] == base
                 and q.distance(poly) <= 1e-6
                 and q.intersection(poly.buffer(1e-3)).length > w
                 for q, d in roads)
    return w if halved else 0.5 * w


def road_edge_witness(airport, road_poly, at: XY, wc, cache: dict) -> tuple[object, str]:
    """THE ROAD EDGE IS THE PAINTED LINE (spec §34 (9) (4), owner RULINGS
    2026-09-14aq: "detect the white line marking from the scenery package
    that marks the road edge").

    ``(line geometry, name)`` for the pack's own road-edge marking beside
    ``at`` — a DRAPED object in the ``markings`` layer group (the class §42
    refuses as pavement, ``airport/object_pavement.py``: at HECA
    ``Airport/ground/asphalt_white.obj``) whose body lies within
    ``road_edge_line_reach_m`` of ``road_poly``'s edge and whose principal
    direction is within ``road_edge_line_parallel_deg`` of the road edge's
    there.  ``(None, "")`` when the pack paints no such line — then the
    FACE edge stands, which is §34 (9) (4)'s own provision.

    Read HERE, lazily, and only where a ramp is actually pinched: the
    markings are refused at load (they are not pavement) and a pack carries
    thousands of them (OTHH 5,906 placements over 20 resources).  The
    header screen is the whole pre-filter and each resource is parsed at
    most once, into ``cache``."""
    from ..airport import object_pavement as _objpav
    reach = wc.road_edge_line_reach_m
    edge = road_poly.exterior
    near = Point(at).buffer(reach + 20.0)
    best = None
    for o in getattr(airport, "dsf_objects", ()):
        path = getattr(o, "resolved_path", None)
        if not path or not near.contains(Point(o.xy)):
            continue
        if path not in cache:
            grp = _objpav.header_facts(path)[0]
            fp = None
            if grp and grp[0].lower() == "markings":
                geom = obj8.parse_obj8(path)
                fp = _objpav.draped_footprint(geom, 1.0)
            cache[path] = fp
        fp = cache[path]
        if fp is None:
            continue
        g = _affinity.affine_transform(fp, list(obj8.placement_affine(o.xy, o.heading_deg)))
        if g.is_empty or g.distance(edge) > reach:
            continue
        if _parallel_deg(g, edge, Point(at)) > wc.road_edge_line_parallel_deg:
            continue
        d = g.distance(Point(at))
        if best is None or d < best[0]:
            best = (d, g, os.path.basename(path))
    if best is None:
        return None, ""
    return best[1], best[2]


def _parallel_deg(line_body, edge, at: Point) -> float:
    """The angle between a marking body's principal direction and the road
    edge's direction at ``at``, in degrees (0..90)."""
    mrr = line_body.minimum_rotated_rectangle
    cs = list(mrr.exterior.coords)[:-1]
    if len(cs) < 4:
        return 90.0
    sides = sorted(((math.dist(cs[i], cs[(i + 1) % 4]), cs[i], cs[(i + 1) % 4])
                    for i in range(4)), key=lambda t: -t[0])
    (_L, a, b) = sides[0]
    p = edge.interpolate(edge.project(at))
    q = edge.interpolate(min(edge.length, edge.project(at) + 2.0))
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (q.x - p.x, q.y - p.y)
    n1 = math.hypot(*v1) or 1.0
    n2 = math.hypot(*v2) or 1.0
    c = abs(v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(0.0, min(1.0, c))))


def stop_and_steepen(airport, wc, axis_fn, axis_ln, ss, s_top, climb_from, mouth_z, clipped_by,
                     stop_list, stop_tree, host, beyond, grid, spacing, regeom,
                     locked_roads=(), mark_cache=None):
    """RULINGS 2026-09-08m (a): a climb STOPPED at airside pavement (or a
    pad) runs to the pavement EDGE — the exact station one grid step
    short of where the axis enters the cell (the stations' granularity
    gave up to a station of run) — and steepens to reach the ground there
    up to ``max_ramp_grade``.

    A CLIMB THAT CANNOT REACH AIRSIDE MOVES ITS MOUTH AWAY FROM AIRSIDE
    (spec §34 (8) as amended, owner RULINGS 2026-09-14u — which supersedes
    14p's portal).  Where the steepened climb still cannot reach the ground
    inside ``max_ramp_grade``, the corridor's MOUTH — where its flat trench
    floor ends and the climb begins — is moved AWAY from the airside edge,
    toward and if need be under the building, by the run the cap needs
    (``rise / max_ramp_grade`` minus the run available).  The ramp then runs
    at the cap from the moved mouth and reaches the ground at the pavement
    edge at full depth under the building; there is no step, and the airside
    cell is never pulled.  Measured at OTHH ``Terminal_Base_2_5.obj@0``:
    1.88 m of rise with 17.1 m of run = 11.0 % against the 10 % cap, so the
    mouth moves 1.7 m back under the terminal (recovering the grid step the
    stop is snapped short by leaves 10.7 %, so the move is the rule, not a
    rounding).  The corridor is refused only where the climb runs the WRONG
    WAY (the ground at the stop stands under the trench floor), or where
    moving the mouth would push it past the corridor's own far end.

    THE PINCHED RAMP (spec §34 (9), owner RULINGS 2026-09-14ak) takes
    PRECEDENCE over both.  Where the stop is a SERVICE ROAD LOCKED TO
    AIRSIDE (``locked_roads``, :func:`locked_road_stops`), the ramp ENDS AT
    THE ROAD EDGE: the road keeps its airside-locked level and is never
    pulled, the ramp runs from that edge down to its bottom at the BUILDING
    EDGE, and the cap is LIFTED for that pinched run — whatever grade the
    span requires is lawful, because the two things the ramp is pinched
    between (a road that may not move and the building it dives under) both
    stand where they stand.  The mouth does NOT move: shortening the run is
    the owner's complaint ("the ramps ... are coming out too far and
    pulling down the service road edge"), and the moved mouth of 14u is for
    an unpinched climb.

    ``(ss, geom, s_top, design_grade, refusal, climb_from, pinched,
    floor_lift)`` — ``climb_from`` is the MOVED mouth (unchanged when the
    ramp reaches the ground as it stands), ``pinched`` the ``(road ref,
    span m, grade)`` of a §34 (9) pinch or ``None``, and ``floor_lift``
    the metres §47 (7) RAISES the floor by so the cap holds and the
    residual stands at the covering plate's edge (0.0 otherwise)."""
    geom = regeom(ss)
    witness = ""
    stop_poly = next((p for p, ref in stop_list if ref == clipped_by), None)
    if stop_poly is not None and clipped_by in locked_roads and mark_cache is not None:
        # §34 (9) (4): the PAINTED line is the road edge where the pack
        # paints one; otherwise the face edge stands
        line, witness = road_edge_witness(airport, stop_poly, axis_fn(s_top), wc, mark_cache)
        if line is not None:
            stop_poly = stop_poly.union(line).convex_hull if line.disjoint(stop_poly) \
                else stop_poly.union(line)
    if stop_poly is not None and s_top + spacing <= axis_ln.length:
        tail = LineString([axis_fn(s_top), axis_fn(min(axis_ln.length, s_top + spacing * 2))])
        x = tail.intersection(stop_poly.boundary)
        s_edge = min((s_top + tail.project(pt) for pt in shapely.get_parts(x)
                      if pt.geom_type == "Point"), default=None)
        if s_edge is not None and s_edge - grid > s_top + grid / 2.0:
            ss_try = ss + [s_edge - grid]
            geom_try = regeom(ss_try)
            if geom_try is not None:
                probe = geom_try.ramp.intersection(beyond) if beyond is not None else geom_try.ramp
                if probe.is_empty or _pad_hit(probe, stop_list, stop_tree, grid, host) is None:
                    ss, geom, s_top = ss_try, geom_try, ss_try[-1]
    top_ground = float(airport.dem.z(*axis_fn(s_top)))
    run = s_top - climb_from
    rise = (top_ground - mouth_z) if not math.isnan(top_ground) else math.inf
    g2 = rise / run if run > 1e-6 else math.inf
    if clipped_by in locked_roads:
        # §47 (7) LAW C HOLDS THE CAP (owner RULINGS 2026-09-17h Q1:
        # "Maintain 10% cap, descend as far as that allows, stopping at the
        # building wall") — §34 (9)'s LIFTED cap is SUPERSEDED.  The ramp
        # still ENDS at the locked road's edge and the road still keeps its
        # airside level, but the run it has is run at ``max_ramp_grade``
        # and no steeper: the ramp arrives at the covering plate's edge at
        # ``cap x L`` and the RESIDUAL to the authored wall-bottom floor is
        # a step AT THE PLATE EDGE, reported per corridor (14bm's east
        # mouth read 17.17 % over 11.0 m; at the cap the same run reaches
        # 1.10 m of the 1.88 m rise and the 0.78 m residual stands at the
        # plate).  The floor is RAISED to put the residual there rather
        # than at the road: ``floor_lift`` is what the caller adds to
        # ``mouth_z``.  A climb the wrong way is still no corridor.
        if g2 < 0.0 or math.isinf(g2) or math.isnan(g2):
            return ss, geom, s_top, g2, (
                f"the climb pinched against the locked service road {clipped_by} at s "
                f"{s_top:.1f} runs the wrong way: {run:.1f} m of run for {rise:.2f} m of rise "
                f"to the road edge {top_ground:.2f} (§34 (9))"), climb_from, None, 0.0
        if g2 > wc.max_ramp_grade + 1e-9:
            lift = rise - wc.max_ramp_grade * run
            return ss, geom, s_top, wc.max_ramp_grade, None, climb_from, \
                (clipped_by, run, wc.max_ramp_grade, witness), lift
        return ss, geom, s_top, g2, None, climb_from, (clipped_by, run, g2, witness), 0.0
    if g2 < 0.0 or math.isinf(g2) or math.isnan(g2):
        return ss, geom, s_top, g2, (
            f"the climb stopped by {clipped_by} at s {s_top:.1f} runs the wrong way: "
            f"{run:.1f} m of run for {rise:.2f} m of rise to the ground {top_ground:.2f} — "
            f"a trench standing over its own ground is no corridor (§34 (8))"), climb_from, None, 0.0
    if g2 > wc.max_ramp_grade + 1e-9:
        # §34 (8) as amended (14u): MOVE THE MOUTH away from airside by the
        # run the cap needs, and run the ramp at the cap from there
        need = rise / wc.max_ramp_grade
        moved = s_top - need
        if moved < -1e-9:
            return ss, geom, s_top, g2, (
                f"the climb stopped by {clipped_by} at s {s_top:.1f} needs {need:.1f} m of run "
                f"at max_ramp_grade {100.0 * wc.max_ramp_grade:.0f} % for {rise:.2f} m of rise, "
                f"and the corridor is only {s_top:.1f} m long — the mouth cannot move that far "
                f"back (§34 (8), 14u)"), climb_from, None, 0.0
        moved = max(0.0, moved)
        ss = sorted(set([s for s in ss if abs(s - moved) > 1e-6] + [moved]))
        geom_m = regeom(ss)
        if geom_m is not None:
            geom = geom_m
        return ss, geom, s_top, rise / max(s_top - moved, 1e-9), None, moved, None, 0.0
    return ss, geom, s_top, g2, None, climb_from, None, 0.0


def wall_corridor_profile(airport, g: Group, ss, s_top, mouth_z, design_grade, axis_fn,
                          climb_from: float | None = None) -> tuple[tuple, float | None]:
    """The profile published to the generator (spec §6a row 19): the wall
    bottom inside the walls, then the design line from the wall end's
    floor to the ground at the top.  ``(profile, top ground)``.

    WITH A MOVED MOUTH (spec §34 (8) as amended, RULINGS 2026-09-14u) the
    climb starts at ``climb_from`` instead of the wall end — back under the
    building — so the wall bottom's own stations BEYOND that point give way
    to the ramp's line: the trench reaches full depth at the moved mouth and
    the ramp runs at the cap from there to the ground."""
    prof = list(g.profile)
    knee = g.hull_s if climb_from is None else min(float(climb_from), g.hull_s)
    top_ground = None
    if g.climbs and s_top > knee + 1e-6:
        z_end = profile_z(tuple(prof), knee) if prof else mouth_z
        top_ground = float(airport.dem.z(*axis_fn(s_top)))
        prof = [p for p in prof if p[0] <= knee + 1e-6]
        if not prof or abs(prof[-1][0] - knee) > 1e-6:
            prof.append((float(knee), z_end))
        for s in ss:
            if s > knee + 1e-6:
                prof.append((float(s), z_end + design_grade * (s - knee)))
        if not math.isnan(top_ground):
            prof[-1] = (prof[-1][0], top_ground)
    return tuple(prof), top_ground


def wall_corridor_note(c, g: Group, mouth_dem, s_top, climb_from, design_grade, top_ground,
                       clipped_by, moved_m: float = 0.0, pinched=None,
                       covered_from=None, witness: str = "") -> str:
    """The per-site line the report quotes."""
    tg = float("nan") if top_ground is None else top_ground
    return (f"wall corridor (2026-09-08m/n Law C, {c.cls}) of {c.resource}: floor = the wall "
            f"bottom per station {min(c.floors):.2f}..{max(c.floors):.2f} under ground "
            f"{mouth_dem:.2f} ({c.depth_m:.2f} m at most) over {g.hull_s:.1f} m, width "
            f"{c.width_m:.1f} m, ends {c.ends}"
            + (f"; climb {s_top - climb_from:.1f} m at {100.0 * design_grade:.2f} % to the ground "
               f"{tg:.2f}" if g.climbs else "; no climb: the authored ramp meets the ground")
            + (f" — STOPPED at {clipped_by} and steepened (08m (a))" if clipped_by else "")
            + (f"; THE MOUTH MOVED {moved_m:.2f} m AWAY FROM {clipped_by}, back under the "
               f"building, to s {climb_from:.1f}: the ramp runs at "
               f"{100.0 * design_grade:.1f} % (max_ramp_grade) from there and reaches the ground "
               f"at full depth — no step, and the airside cell is never pulled "
               f"(§34 (8) as amended, 14u)" if moved_m > 1e-9 else "")
            + (f"; pinched_ramp (§34 (9)): the climb ENDS AT THE EDGE of the airside-locked "
               f"service road {pinched[0]} — the road keeps its level and is never pulled — and "
               f"runs {pinched[1]:.1f} m from that edge down to the ramp bottom at the building "
               f"edge at {100.0 * pinched[2]:.1f} %, the cap LIFTED for the pinched run"
               + (f"; the road edge is {witness}" if witness else "")
               if pinched else "")
            + (f"; full depth at the BUILDING WALL (§34 (9) (5) as corrected by 14be): the "
               f"COVERING PLATE's edge is s {covered_from:.1f}, so the "
               f"{g.hull_s - covered_from:.1f} m of uncovered corridor — the retaining wall "
               f"protruding past the building included — is RAMP, not trench"
               if covered_from is not None and covered_from < g.hull_s - 1e-6 else ""))


def cap_held_note(clipped_by: str, lift_m: float, grade: float, run_m: float) -> str:
    """§47 (7): what the cap-holding Law C ramp reports — the floor raised
    by ``lift_m`` so the 10 % cap holds, and the residual to the authored
    wall-bottom floor standing at the COVERING PLATE's edge."""
    return (f"§47 (7) the 10 % cap holds against {clipped_by}: the floor is raised "
            f"{lift_m:.2f} m — the ramp arrives at the covering plate's edge at "
            f"{100.0 * grade:.1f} % over {run_m:.1f} m and the {lift_m:.2f} m residual to the "
            f"authored wall-bottom floor is a step there")
