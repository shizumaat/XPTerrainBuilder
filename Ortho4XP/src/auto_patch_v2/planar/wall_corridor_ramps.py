"""THE WALL CORRIDORS AS STRUCTURES TO BUILD (RULINGS 2026-09-08m / 08n
LAW C; spec ``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md`` §6):
the readings of ``airport/wall_corridors.py`` turned into the build
groups ``planar/structures.py`` runs through its ONE ramp / void / rim
machinery (the 05n object-corridor path, the 08b/c door path).

Per record: s = 0 at the MOUTH end (a closed end's floor overlapping the
end wall by ``cutout.floor_overlap_m``, or a level corridor half's
midpoint — capless, sharing the mouth line with its sibling half); the
"walls" are the two bands, their inner faces ⊕ the overlap the ramp's
edges, the rim ``rim_standoff`` of each band's measured thickness
inside the wall (09-08a); the FLOOR is the wall bottom per station
(``Group.profile``, pinned by the generator — level or descending, cut
as authored); a LEVEL corridor / a BAY climbs beyond its open end at
``ramp_grade`` (``Group.climb_from_s`` = the wall end) and STOPS at
airside pavement, steepening to ``max_ramp_grade`` (``stop_side``); a
GARAGE RAMP has no climb (its own floor meets the ground at the open
end).  Roles: ``wall_corridor_ramp`` (level / bay), ``garage_ramp``
(descending).  ``seat = "none"``: never plate-seated, the family excluded
from the re-seat.
"""
from __future__ import annotations

import typing as _t

import math

import shapely
from shapely.geometry import LineString

from ..law import Law
from ..law.cutout_schema import WALL_BOTTOM
from ..law.tables import role_side
from ..airport.wall_corridors import CLASS_GARAGE
from .object_corridor import Group
from .structure_approach import unit
from .structure_geometry import pad_hit as _pad_hit, rim_standoff

__all__ = ["wall_corridor_groups", "RAMP_ROLE", "GARAGE_ROLE", "KIND", "airside_stops",
           "stop_and_steepen", "wall_corridor_profile", "wall_corridor_note"]

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
    overlap = co.floor_overlap_m
    osm_rim = tn.wall_gap_m + tn.wall_band_width_m

    def standoff(t: float) -> float:
        return rim_standoff(t, co, grid)[1]
    out: list[Group] = []
    for r in records:
        axis = list(r.axis)
        sts = r.stations
        L = r.length_m
        u0 = unit(axis[0], axis[1])
        u_end = unit(axis[-2], axis[-1])
        inward = (-u0[0], -u0[1])
        garage = r.cls == CLASS_GARAGE

        def half_fn(s: float, _sts=sts, _ov=overlap) -> tuple[float, float]:
            hl, hr = _interp(_sts, s, "half_l", "half_r")
            return hl + _ov, hr + _ov

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
                         sibling=r.sibling, ramp_role=GARAGE_ROLE if garage else RAMP_ROLE,
                         straight=True))
    return out


# ── the build-time helpers ``planar/structures.build_structures`` calls ──

def airside_stops(cells, polys, law: Law, runway_family) -> list:
    """What a wall-corridor ramp STOPS at (RULINGS 2026-09-08m (a)/(b), spec
    §6a row 14): AIRSIDE cells and building pads, never a structure or
    the runway family; a groundside road across the ramp yields onto it."""
    return [(p, c.ref) for p, c in zip(polys, cells)
            if c.kind != "structure" and c.role not in runway_family
            and (role_side(law, c.role) == "airside" or c.role == "building")]


def stop_and_steepen(airport, wc, axis_fn, axis_ln, ss, s_top, climb_from, mouth_z, clipped_by,
                     stop_list, stop_tree, host, beyond, grid, spacing, regeom):
    """RULINGS 2026-09-08m (a): a climb STOPPED at airside pavement (or a
    pad) runs to the pavement EDGE — the exact station one grid step
    short of where the axis enters the cell (the stations' granularity
    gave up to a station of run) — and steepens to reach the ground there
    up to ``max_ramp_grade``; above it the corridor is refused loudly,
    never a portal face.  ``(ss, geom, s_top, design_grade, refusal)``."""
    geom = regeom(ss)
    stop_poly = next((p for p, ref in stop_list if ref == clipped_by), None)
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
    if not (0.0 <= g2 <= wc.max_ramp_grade + 1e-9):
        return ss, geom, s_top, g2, (
            f"the climb stopped by {clipped_by} at s {s_top:.1f} would need {100.0 * g2:.1f} % "
            f"over {run:.1f} m to reach the ground {top_ground:.2f} (> max_ramp_grade "
            f"{100.0 * wc.max_ramp_grade:.0f} %; 2026-09-08m (a))")
    return ss, geom, s_top, g2, None


def wall_corridor_profile(airport, g: Group, ss, s_top, mouth_z, design_grade, axis_fn
                          ) -> tuple[tuple, float | None]:
    """The profile published to the generator (spec §6a row 19): the wall
    bottom inside the walls, then the design line from the wall end's
    floor to the ground at the top.  ``(profile, top ground)``."""
    prof = list(g.profile)
    top_ground = None
    if g.climbs and s_top > g.hull_s + 1e-6:
        z_end = prof[-1][1] if prof else mouth_z
        top_ground = float(airport.dem.z(*axis_fn(s_top)))
        for s in ss:
            if s > g.hull_s + 1e-6:
                prof.append((float(s), z_end + design_grade * (s - g.hull_s)))
        if not math.isnan(top_ground):
            prof[-1] = (prof[-1][0], top_ground)
    return tuple(prof), top_ground


def wall_corridor_note(c, g: Group, mouth_dem, s_top, climb_from, design_grade, top_ground,
                       clipped_by) -> str:
    """The per-site line the report quotes."""
    tg = float("nan") if top_ground is None else top_ground
    return (f"wall corridor (2026-09-08m/n Law C, {c.cls}) of {c.resource}: floor = the wall "
            f"bottom per station {min(c.floors):.2f}..{max(c.floors):.2f} under ground "
            f"{mouth_dem:.2f} ({c.depth_m:.2f} m at most) over {g.hull_s:.1f} m, width "
            f"{c.width_m:.1f} m, ends {c.ends}"
            + (f"; climb {s_top - climb_from:.1f} m at {100.0 * design_grade:.2f} % to the ground "
               f"{tg:.2f}" if g.climbs else "; no climb: the authored ramp meets the ground")
            + (f" — STOPPED at {clipped_by} and steepened (08m (a))" if clipped_by else ""))
