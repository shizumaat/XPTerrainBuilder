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
as authored); a LEVEL corridor / a BAY's ramp RUNS THE WALLS' LENGTH
(owner RULINGS 2026-10-07b (2), :func:`full_wall_ramp`): at grade at the
walls' outer end, falling toward the building to full depth at the
COVERING PLATE's edge (§34 (9) (5), 14be), never steeper than
``max_ramp_grade`` save a SERVICE BAY too short for it (07c (1): exempt) —
nothing is built beyond the walls, so nothing stops it; a GARAGE RAMP has no climb (its own floor meets the ground at the
open end).  Roles: ``wall_corridor_ramp`` (level / bay), ``garage_ramp``
(descending).  ``seat = "none"``: never plate-seated, the family excluded
from the re-seat.
"""
from __future__ import annotations

import typing as _t

import math

from ..law import Law
from ..law.cutout_schema import WALL_BOTTOM
from ..model.frame import rotated_rectangle
from ..model.structures import profile_z
from ..airport.wall_corridors import CLASS_GARAGE
from .object_corridor import Group
from .structure_approach import unit
from .structure_geometry import rim_standoff

__all__ = ["wall_corridor_groups", "RAMP_ROLE", "GARAGE_ROLE", "KIND", "ROAD_ROLES",
           "road_true_edge", "full_wall_ramp", "BAY_EXEMPT",
           "wall_corridor_profile", "wall_corridor_note"]

#: The groundside ROAD family §34 (9) can pinch a ramp against.  A parking
#: lot is not a road (it is a place, and §24's pad law governs it).
ROAD_ROLES = ("service_road", "service_junction", "groundside_pavement")

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

KIND = "wall_corridor"
RAMP_ROLE = "wall_corridor_ramp"
#: the ``Tunnel.pinched`` road slot of a service bay whose ramp is exempt
#: from the cap (owner RULINGS 2026-10-07c (1)) — the §34 (9) lifted-cap
#: record, so ``pipeline/publication.lifted_caps`` tags its faces and both
#: census readers judge them at the designed grade
BAY_EXEMPT = "service bay, exempt from the cap (RULINGS 2026-10-07c (1))"
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
                         0.0 if garage else wc.max_ramp_grade, kind=KIND,
                         max_grade=wc.max_ramp_grade, spacing_m=wc.station_m, climb_from_s=L,
                         profile=tuple(r.profile), mouth_strip=False,
                         sibling=r.sibling, ramp_role=GARAGE_ROLE if garage else RAMP_ROLE))
    return out


# ── the build-time helpers ``planar/structures.build_structures`` calls ──

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

    * the PINCHED corridor climb of §34 (9) — RETIRED with owner RULINGS
      2026-10-07b (2): a Law C ramp runs its walls' length and reaches no
      road (:func:`full_wall_ramp`);
    * the §34 (8) mouth CLIMB-OUT and the tunnel-object / door ramp
      (``planar/object_corridor``'s ``stop_at_pavement``) — they consume
      the stop set ``planar/structures.build_structures`` assembles from
      every governed cell, ROAD_ROLES included: HERE, at that one list;
    * the BASIN ramp (§24 (8), ``planar/basin_geometry``) and
      ``planar/structure_approach`` — neither reads a role or a road: the
      first is the plan geometry of the object's OWN rim/floor/ramp
      corridors, the second computes mouths, chains and deck intervals
      off mapped WAYS.  Nothing to rule.

    So: one derivation, one call site, in ``planar/structures.py``.
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
    mrr = rotated_rectangle(poly)
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


def full_wall_ramp(top_ground: float, profile, floor_z: float, wall_end_s: float,
                   covered_from: float | None, cap: float, closed: bool):
    """THE RAMP RUNS THE FULL WALL LENGTH (owner RULINGS 2026-10-07b (2):
    "Ramps should use full wall length, at grade at the outer extent of
    the two retaining walls, grading down toward building"; 07a (2) "they
    should only be the size of the walls", (3) "about half as long, they
    extend out too far").

    The top is the ground at the walls' OUTER END (``wall_end_s`` — the
    last station at which BOTH walls stand, so two walls of unequal length
    end the ramp at the SHORTER one's end).  From there it falls toward
    the building and is at full depth where the corridor becomes COVERED
    (``covered_from``, §34 (9) (5) / 14be; where nothing protrudes — no
    cover, or a cover reaching the wall end — at the corridor's own start
    s = 0, so the ramp still runs the walls' full length) at the grade that
    span needs — but never steeper
    than ``cap`` (``max_ramp_grade``, the 10 % of the same ruling): where
    the uncovered span is too short the knee moves back UNDER the building
    by the run the cap needs (§34 (8), 14u).  Where even the walls' whole
    length is too short, a CLOSED corridor (a SERVICE BAY) is EXEMPT from
    the cap (owner RULINGS 2026-10-07c (1), superseding §47 (7)'s raised
    floor and 17h Q1's step): the ramp runs the walls' whole length at the
    grade that span needs — no raised floor, no step at the door; an open
    half is refused (its floor is a through road's).

    ``(climb_from, grade, moved_m, exempt)`` or the refusal; ``exempt`` is
    True where the grade stands over ``cap`` by 07c (1)."""
    floors = [z for _s, z in profile] or [floor_z]
    rise = top_ground - min(floors)
    if math.isnan(rise) or rise < 0.0:
        return (f"the ground at the walls' outer end ({top_ground:.2f}) stands under the "
                f"corridor floor ({min(floors):.2f}) — a trench standing over its own ground "
                f"is no corridor (§34 (8))")
    # no cover protruding (none, or it reaches the wall end): the ramp is
    # the walls' WHOLE length — never a run beyond them (07b (2))
    knee = 0.0 if covered_from is None else float(covered_from)
    if rise <= cap * (wall_end_s - knee) + 1e-9:
        run = wall_end_s - knee
        return knee, (rise / run if run > 1e-9 else 0.0), 0.0, False
    moved = wall_end_s - rise / cap
    if moved >= -1e-9:
        return max(0.0, moved), cap, knee - max(0.0, moved), False
    if closed and wall_end_s > 1e-9:
        return 0.0, rise / wall_end_s, knee, True
    return (f"the walls are {wall_end_s:.1f} m long and {rise:.2f} m of rise needs "
            f"{rise / cap:.1f} m at max_ramp_grade {100.0 * cap:.0f} % — the ramp cannot run "
            f"inside its walls (RULINGS 2026-10-07b (2); §34 (8))")


def wall_corridor_profile(airport, g: Group, ss, s_top, mouth_z, design_grade, axis_fn,
                          climb_from: float | None = None) -> tuple[tuple, float | None]:
    """The profile published to the generator (spec §6a row 19): the wall
    bottom up to the knee ``climb_from`` (the covering plate's edge, or
    the point under the building the cap moved it to), then the design
    line from the floor there to the ground at the walls' outer end
    (RULINGS 2026-10-07b (2)); the wall bottom's own stations beyond the
    knee give way to the ramp's line.  ``(profile, top ground)``."""
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
                       moved_m: float = 0.0, covered_from=None, exempt: bool = False) -> str:
    """The per-site line the report quotes."""
    tg = float("nan") if top_ground is None else top_ground
    return (f"wall corridor (2026-09-08m/n Law C, {c.cls}) of {c.resource}: floor = the wall "
            f"bottom per station {min(c.floors):.2f}..{max(c.floors):.2f} under ground "
            f"{mouth_dem:.2f} ({c.depth_m:.2f} m at most) over {g.hull_s:.1f} m, width "
            f"{c.width_m:.1f} m, ends {c.ends}"
            + (f"; ramp {s_top - climb_from:.1f} m of the walls' {g.hull_s:.1f} m at "
               f"{100.0 * design_grade:.2f} %: at grade ({tg:.2f}) at the walls' outer end, "
               f"falling toward the building (RULINGS 2026-10-07b (2))"
               + (f", over max_ramp_grade: {BAY_EXEMPT}" if exempt else "")
               if g.climbs else "; no climb: the authored ramp meets the ground")
            + (f"; full depth at the COVERING PLATE's edge, s {covered_from:.1f} (§34 (9) (5), "
               f"14be)" if covered_from is not None and moved_m <= 1e-9 else "")
            + (f"; the knee moved {moved_m:.2f} m back UNDER the building to s "
               f"{climb_from:.1f}: the span needs more than max_ramp_grade (§34 (8), 14u)"
               if moved_m > 1e-9 else ""))
