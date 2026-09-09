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

from ..law import Law
from ..law.cutout_schema import WALL_BOTTOM
from ..airport.wall_corridors import CLASS_GARAGE
from .object_corridor import Group
from .structure_approach import unit
from .structure_geometry import rim_standoff

__all__ = ["wall_corridor_groups", "RAMP_ROLE", "GARAGE_ROLE", "KIND"]

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
                         stop_side="airside", ramp_cuts_pads=True, mouth_strip=False,
                         sibling=r.sibling, ramp_role=GARAGE_ROLE if garage else RAMP_ROLE,
                         straight=True))
    return out
