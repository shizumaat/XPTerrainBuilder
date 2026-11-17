"""THE FOOT PLANES of a group's feet (owner RULINGS 2026-10-22q/c, #1214
rounds 5-6; moved from ``airport/airside_group_seat`` in round 7 so a
constraint generator reads the same plane: ``constraints/group_level``).

Each foot of a group says where the group's zero must be for it to stand
on the surface under it (``z - y``); :func:`floor_plane` is the AIRSIDE
FLOOR among those candidates, :func:`ground_plane` the low side a share on
no airside stands on.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["PLANE_SHARE", "PLANE_BAND_M", "PLANE_MIN_FEET", "floor_plane", "ground_plane",
           "is_support", "frame_floor", "carried_feet"]

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
    half 0.9 m.  ``storey_m`` 0 keeps round 5's floor.

    A candidate that is no number (a foot over no surface: a cold DEM's
    NaN) states no plane and is left out; with none left there is no
    floor (#2099: a NaN made every band comparison false and the band
    empty -- an IndexError, not an answer)."""
    v = sorted((float(z) for z in zs if not math.isnan(float(z))), reverse=True)
    if not v:
        return None
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
    across its frame (owner, 1.0.421).  A NaN candidate is left out, as
    in :func:`floor_plane`."""
    zs = [float(z) for z in zs if not math.isnan(float(z))]
    if not zs:
        return None
    need = max(1, int(PLANE_SHARE * len(zs) + 0.999999),
               min(PLANE_MIN_FEET, int(0.5 * len(zs) + 0.999999)))
    return _lowest_plane(zs, need)


# ── SUPPORT MEMBERS (#1726) ─────────────────────────────────────────
# A SUPPORT FOUNDS NO STOREY (owner, KBWI sim read 2026-11-03T05:25:51Z:
# "some of those columns should end up under ground, and don't appear to
# need a trench").  A SUPPORT is a WALLED part (``[placement]
# chain_min_height_m``) that is slender in plan: its plan box spans at most
# ``[building_pad] support_max_extent_m`` on both axes (MEASURED KBWI
# ``BWI_Terminal_new``: 275 poles 0.3 x 0.3 m down to y -6.15, 171 piers
# 1.9 x 1.9 m down to -3.46; walls and façades run tens of metres).  Poles
# and piers under a building may stand below the ground; the lower storey
# of a unit is witnessed by its other walls alone
# (``planar/low_level.feet_levels``).  The developer's own KBWI mesh keeps
# the ground level under the terminal (41.0-41.9 m against 41.0 at the
# gate doors), with the poles' feet 6 m into it.

_M_PER_DEG = 111_320.0


def is_support(part: _t.Any, law: _t.Any) -> bool:
    """A WALLED part whose lat/lon plan box (``part.box``: min lat, min
    lon, max lat, max lon) spans at most ``support_max_extent_m`` on both
    axes (module docstring)."""
    st = law.tables.structures
    if getattr(part, "line", False):
        return False
    if float(getattr(part, "height_m", 0.0) or 0.0) < float(st.placement.chain_min_height_m):
        return False
    box = getattr(part, "box", None)
    if not box:
        return False
    lim = float(getattr(st.building_pad, "support_max_extent_m", 0.0) or 0.0)
    dy = (float(box[2]) - float(box[0])) * _M_PER_DEG
    dx = (float(box[3]) - float(box[1])) * _M_PER_DEG * math.cos(math.radians(float(box[0])))
    return max(abs(dx), abs(dy)) <= lim


def frame_floor(unit: _t.Any, step_m: float, wall_min_m: float) -> "float | None":
    """THE LOWER FLOOR of a frame read at its airside floor (spec 2120-F R3,
    ``airport/airside_floor``'s ``y_l``), in its re-zeroed frame: the
    :func:`floor_plane` of its walled parts' (``wall_min_m`` tall) feet a
    storey (``step_m``, ``[building_pad] low_level_min_step_m``) or more
    under its zero; ``None`` for a unit with none."""
    ys = [-float(f[2]) for m in unit.members for p in m.parts
          if not getattr(p, "line", False)
          and float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min_m
          for f in (getattr(p, "feet", ()) or ()) if float(f[2]) <= -step_m]
    got = floor_plane(ys, step_m) if ys else None
    return None if got is None else round(-float(got), 3)


def _on_floor(y: float, y_floor: float) -> bool:
    """A foot at ``y`` (the frame's re-zeroed ``y``) TOUCHES GROUND (spec
    2120-WF2 F1): on the frame's lower floor ``y_floor`` or under it (a
    footing may sink, never float: 2120-F B2), or on its airside floor (its
    zero, the apron), each within :data:`PLANE_BAND_M`."""
    y = float(y)
    return y <= float(y_floor) + PLANE_BAND_M or abs(y) <= PLANE_BAND_M


def carried_feet(ys: _t.Sequence[float], y_floor: "float | None") -> bool:
    """A body of a ``floor_zero`` frame none of whose feet ``ys`` touches
    ground (:func:`_on_floor`) stands on the pack's own floors -- a curb, a
    mezzanine, a canopy: CARRIED, it takes no ground pad and no ground row
    (spec 2120-WF2 F1).  ``False`` without a lower floor or feet."""
    return y_floor is not None and bool(ys) and not any(_on_floor(y, y_floor) for y in ys)
