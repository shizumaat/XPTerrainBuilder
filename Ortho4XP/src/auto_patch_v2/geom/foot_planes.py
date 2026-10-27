"""THE FOOT PLANES of a group's feet (owner RULINGS 2026-10-22q/c, #1214
rounds 5-6; moved from ``airport/airside_group_seat`` in round 7 so a
constraint generator reads the same plane: ``constraints/group_level``).

Each foot of a group says where the group's zero must be for it to stand
on the surface under it (``z - y``); :func:`floor_plane` is the AIRSIDE
FLOOR among those candidates, :func:`ground_plane` the low side a share on
no airside stands on.
"""
from __future__ import annotations

import typing as _t

__all__ = ["PLANE_SHARE", "PLANE_BAND_M", "PLANE_MIN_FEET", "floor_plane", "ground_plane"]

#: a PLANE of the airside-contact feet holds at least this share of them,
#: within :data:`PLANE_BAND_M` ...
PLANE_SHARE = 0.1
PLANE_BAND_M = 1.0
#: ...and at least this many feet (or half of them, for a small share):
#: what rules out a STRAY PIECE — one wall strip of a building standing
#: in an uncut trench (LFPG 2A_1: 12 edge feet) is no airside floor
PLANE_MIN_FEET = 20


def floor_plane(zs: _t.Sequence[float], storey_m: float = 0.0) -> "float | None":
    """THE AIRSIDE FLOOR among a group's airside-contact feet (RULINGS
    2026-10-22q as read by #1214 round 5): each foot's zero candidate is
    ``airside z - y`` (where the group's zero must be for THAT foot to
    stand on the airside), and the floor that meets the apron is the
    FOUNDATION — the LOWEST substantial plane of feet, i.e. the HIGHEST
    plane of candidates holding :data:`PLANE_SHARE` of them and
    :data:`PLANE_MIN_FEET` (or half of them) within :data:`PLANE_BAND_M`;
    its median.  The feet above it are the building's upper storeys.
    Round 4 took the highest plane of feet: KMCI's concourse walls at
    y -1.1 stood on the apron and the complex sank a storey (owner,
    1.0.420); its curb plane at y -5.8 is the floor (zero 310.7).

    ONE LEVEL WITHIN A STOREY (#1344): the candidates less than
    ``storey_m`` (``[building_pad] low_level_min_step_m``) under that
    median are the SAME level, authored on ground that falls — the patch
    mints no second level for them either (``planar/low_level``).  Where
    their LOWEST substantial plane's median lies below the floor's band,
    it is the zero (:func:`ground_plane`'s reading: nothing floats; the
    feet of the higher plane may sink, owner RULINGS 2026-10-22c).  KBUF's
    terminal frame: 68 feet at y -0.10 and 39 at y -1.20 on one flat pad
    — the round-5 floor stood on the y -1.20 plane and floated the west
    half 0.9 m.  ``storey_m`` 0 keeps round 5's floor."""
    if not zs:
        return None
    v = sorted((float(z) for z in zs), reverse=True)
    need = max(1, int(PLANE_SHARE * len(v) + 0.999999),
               min(PLANE_MIN_FEET, int(0.5 * len(v) + 0.999999)))
    j = 0
    for i in range(len(v)):
        while v[j] > v[i] + PLANE_BAND_M:
            j += 1
        if i - j + 1 >= need:
            band = [x for x in v if v[j] - PLANE_BAND_M <= x <= v[j]]
            band.sort()
            floor = band[len(band) // 2]
            if storey_m <= 0.0:
                return floor
            low = _lowest_plane([x for x in v if x > floor - storey_m], need)
            return low if low < v[j] - PLANE_BAND_M else floor
    return sorted(v)[len(v) // 2]


def _lowest_plane(zs: _t.Sequence[float], need: int) -> float:
    """The median of the lowest :data:`PLANE_BAND_M` band of ``zs``
    holding ``need`` of them (else of all of them)."""
    v = sorted(zs)
    j = 0
    for i in range(len(v)):
        while v[i] - v[j] > PLANE_BAND_M:
            j += 1
        if i - j + 1 >= need:
            return v[(i + j) // 2]
    return v[len(v) // 2]


def ground_plane(zs: _t.Sequence[float]) -> "float | None":
    """THE GROUND A SHARE STANDS ON where it touches no airside (#1214
    round 6): over its feet's zero candidates ``ground z - y``, the LOWEST
    substantial plane -- the lowest :data:`PLANE_BAND_M` band holding
    :func:`floor_plane`'s share of them; its median.  Nothing of the share
    floats more than the band (owner, RULINGS 2026-10-22c: "no pillars are
    floating, it's ok if some are partly submerged"); the median of every
    foot (round 4) floated KMCI's tower 1.2 m on ground falling 1.5 m
    across its frame (owner, 1.0.421)."""
    if not zs:
        return None
    need = max(1, int(PLANE_SHARE * len(zs) + 0.999999),
               min(PLANE_MIN_FEET, int(0.5 * len(zs) + 0.999999)))
    return _lowest_plane(zs, need)
