"""A HELD PAD THE GROUP STANDS A STOREY ABOVE IS THE GROUP'S LOWER LEVEL
(#1214 round 7; owner RULINGS 2026-10-23b/e, implemented as 2026-10-23f).

Owner, LFPG app 1.0.424 (2026-10-24T00:29:21Z): "the central buildings and
roads at T2 are not getting a separate pad and not staying with the group";
00:33:07Z: "Check why it didn't get a second pad like KMCI, I would expect
the same pattern".  23b: "two pads, one at each of the two feet levels, and
the object group then stays connected and can seat correctly at both
levels".

``planar/low_level.plan_low`` cuts a lower level out of a held pad that
holds BOTH levels of its unit (KMCI ``building26/b1``: the apron walls at
y -5.8 and the lower storey at -8.2 on one block).  At LFPG T2 the levels
stand on DIFFERENT pads: the halls' stand-side walls read the group's
airside floor at y -0.04, while ``building34`` / ``building62`` /
``building35`` / ``building49`` carry only the trench storey's walls, at
y -7.47 -- a pad holding one level, which ``plan_low`` reads as no step.

THE GROUP IS THE WITNESS.  For a held pad whose pack unit (the plurality
of part centres inside it, ``low_level.unit_share``) reads a stand-side
airside floor ``t`` over the WHOLE unit (``low_level.stand_floor``, the
plane the object stage seats the group's one zero at,
``airside_group_seat.airside_zeros``), the pad's own share stands at the
densest ``PLANE_BAND_M`` plane ``y_p`` of its walled feet; where that
plane holds most of them and lies at least two bands (a storey, 23c) under
``t``, the pad is graded as the group's lower level: the pad itself,
closed and kept ``pad_frontage_m`` off the airside (``low_level.
level_cut``), is ``<pad>/p1`` with its riser strip, its high rim keeping
the pad's own datum where it welds to the airside.

THE LEVEL IS TIED TO THE GROUP'S ZERO, not to the pad's datum: the pad's
datum is the apron beside it (LFPG: 103.2-104.1 m), the group's zero is
the apron at the halls' stands (105.2 m).  The record carries the
witnesses -- the stand-side airside-contact feet in their floor's band
(:func:`_floor_band`; frame xy and authored y, at most
:data:`WITNESS_MAX`) -- and ``constraints/group_level`` holds the level at
their mean ``airside z - y`` on the design surface, plus ``y_p``.  The
airside never follows it: the level is not derived on STAGE 1'S MAP
(:func:`stage_one`, the door-pad pattern of ``constraints/door_pad``) --
stage 1 solves the airside with the pad whole
at its datum, and the level, its riser and the pad's rim are stage 2's,
against stage 1's constants.  MEASURED (LFPG replay, the level on stage
1's map): the pads' rims re-seated their datums and moved 1,033 airside
vertices up to 0.29 m, minting 7 airside_no_step rows.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import box

from ..airport.airside_group_seat import PLANE_BAND_M, PLANE_SHARE
from ..model.stage_one import deriving, stage_one
from .low_level import _densest, level_cut, stand_floor, unit_share, walled_feet

__all__ = ["GROUP_WITNESS", "WITNESS_MAX", "group_floor", "plan_group_low", "stage_one"]

#: the ``witness`` word of a group lower level's record
GROUP_WITNESS = "group"
#: at most this many stand-side feet tie the level (evenly sampled)
WITNESS_MAX = 256
#: a pad's share is read on at least this many walled feet
SHARE_MIN_FEET = 4
def group_floor(ui: int, airport, air_of: _t.Callable[[_t.Any], _t.Any],
                stands, law, to_xy, cache: dict) -> "tuple | None":
    """``(t, witness xy, witness y)`` of partition unit ``ui``: its
    stand-side airside floor plane over ALL its parts and the stand-side
    airside-contact feet that read it (``air_of(polygon)`` the airside
    about the unit), or ``None``; memoised in ``cache``."""
    if ui in cache:
        return cache[ui]
    u = airport.partition.units[ui]
    parts = [(p, to_xy(p.lon, p.lat)) for m in u.members for p in m.parts
             if not getattr(p, "line", False)]
    got = None
    if parts:
        xs = [xy[0] for _p, xy in parts]
        ys = [xy[1] for _p, xy in parts]
        air = air_of(box(min(xs), min(ys), max(xs), max(ys)).buffer(60.0))
        sf = stand_floor(parts, air, stands, law, to_xy)
        if sf is not None:
            t, X, Y, at = sf
            idx = _floor_band(airport, X, Y, [i for i in range(len(Y)) if at[i]])
            idx = idx[::max(1, -(-len(idx) // WITNESS_MAX))]
            got = (t, tuple((round(float(X[i, 0]), 3), round(float(X[i, 1]), 3)) for i in idx),
                   tuple(round(float(Y[i]), 3) for i in idx))
    cache[ui] = got
    return got


def _floor_band(airport, X, Y, idx: list) -> list:
    """The stand-side feet ``idx`` whose ground candidate ``DEM - y`` lies
    within half a ``PLANE_BAND_M`` of their ``floor_plane``: the feet the
    object stage's floor will be read on (the highest dense plane of
    ``airside z - y``; MEASURED LFPG T2 on the solved surface: the mean of
    every stand-side foot 104.2 m, the floor 105.2, the mean of this band
    105.0).  The DEM stands in for the airside, unsolved here; without a
    DEM every foot is kept."""
    from ..geom.foot_planes import floor_plane
    dem = getattr(airport, "dem", None)
    if dem is None or not idx:
        return idx
    c = {}
    for i in idx:
        try:
            z = float(dem.z(float(X[i, 0]), float(X[i, 1])))
        except Exception:  # noqa: BLE001 — off the raster
            continue
        if z == z:
            c[i] = z - float(Y[i])
    fp = floor_plane(list(c.values()))
    if fp is None:
        return idx
    return [i for i in idx if i in c and abs(c[i] - fp) <= 0.5 * PLANE_BAND_M]


def plan_group_low(P, air, airport, law, grid: float, others, floor_of,
                   refused: "list | None" = None
                   ) -> "tuple[_t.Any, _t.Any, _t.Any, dict] | None":
    """``(high, low, strip, record)`` grading the held pad ``P`` as its
    group's lower level (module docstring), or ``None`` (the reason, where
    one is read, appended to ``refused``).  ``floor_of(ui)`` is
    :func:`group_floor` bound to the airport."""
    if deriving():
        return None
    to_xy = airport.frame.entry()
    ui, parts = unit_share(P, airport, to_xy)
    floor = floor_of(ui) if ui is not None else None
    if floor is None or not floor[1]:
        return None
    t, wxy, wy = floor
    _xy, ys = walled_feet(parts, law, to_xy)
    if len(ys) < SHARE_MIN_FEET:
        return None
    n_top = sum(1 for y in ys if abs(y - t) <= PLANE_BAND_M)
    if n_top >= max(SHARE_MIN_FEET, PLANE_SHARE * len(ys)):
        # the pad carries the group's floor itself: its lower storey, if
        # any, is ``plan_low``'s (a hall's pad is never lowered)
        return None
    n, y_p = _densest(sorted(ys), PLANE_BAND_M)
    if 2 * n < len(ys) or y_p > t - 2.0 * PLANE_BAND_M:
        # the pad's share does not STAND a storey under the group's floor
        return None
    # the WHOLE pad is the level but for its frontage rim on the airside:
    # the pad IS the footprint, and its walls stand on its ring (MEASURED
    # LFPG replay, the level inset a riser's width: 219 of the trench
    # buildings' feet stood on the riser)
    cut = level_cut(P, P, air, others, law, grid, 0.0)
    if cut is None:
        if refused is not None:
            refused.append(f"group level y {y_p - t:+.2f}: no level left off the airside")
        return None
    H, L, S = cut
    rec = {"witness": GROUP_WITNESS, "top_y": round(t, 3), "y_lo": round(y_p - t, 3),
           "y_hi": round(-2.0 * PLANE_BAND_M, 3), "y_feet": round(y_p, 3),
           "low_parts": len(parts), "area_m2": round(L.area, 1),
           "ground_z": None, "ground_high_z": None,
           "air_xy": wxy, "air_y": wy}
    return H, L, S, rec
