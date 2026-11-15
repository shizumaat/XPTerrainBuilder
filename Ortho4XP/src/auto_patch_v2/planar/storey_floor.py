"""WHAT LEADS A STOREY SHELL'S BLOCK (#2062 spec R3b A; owner rulings
2026-11-13w / 13x (2), 2026-11-15T03:05Z "We should not have any airport
specific exceptions, or alternate code paths").

ONE DATUM RULE FOR EVERY SHELL (``planar/storey_pad._record`` reads it
once, ``StoreyShell.leader``):

* ``airside`` -- a run faces the airside (``SplitLevel.air_level``): the
  block is the airside's level and its datum the stage-1 weld column
  (``model/platform.datum_vertices``), as every held pad's;
* ``floor`` -- no run faces the airside, and half the lowest level's run
  length or more faces a RAMP-CLASS structure floor (a tunnel record's
  ramp, its front floor or its bank: a ``structure`` cell that is no wall
  and no basin or channel floor): the block is the lowest level, its datum
  that floor's mouth datum (``constraints/shell_datum``);
* ``ground`` -- neither: the block is the lowest level and its datum
  ``levels[0]`` plus the length-weighted median of (the DEM
  ``split_level._GROUND_OUT_M`` outside each judged groundside run, less
  that run's foot) -- the building's zero read where its walls meet the
  ground (``split_level._ground``, the reader's own witness).

A shell whose lowest level faces a BASIN or CHANNEL floor (half its run
length) is refused by name: no row makes a block follow one.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import statistics as _st
import typing as _t

from shapely.ops import unary_union
from shapely.prepared import prep

from ..airport.split_level import SplitLevel, _ground, run_faces
from .level_depth import _weighted_median

__all__ = ["FloorCells", "floor_scope", "ground_datum", "lowest_runs", "shell_level_s"]

#: refs of the structure floors no shell follows (a basin's, a channel's)
_NO_FOLLOW = ("basin_", "channel")


class FloorCells:
    """The structure floors of a classification a shell may stand on (its
    RAMP-CLASS floors) and those it may not (basin / channel floors), each
    a prepared plan union (or ``None``)."""

    def __init__(self, cells, polys) -> None:
        ramp, other = [], []
        for c, p in zip(cells, polys, strict=True):
            if c.kind != "structure" or "wall" in str(c.role):
                continue
            (other if str(c.ref).startswith(_NO_FOLLOW) else ramp).append(p)
        self.ramp = prep(unary_union(ramp)) if ramp else None
        self.other = prep(unary_union(other)) if other else None


def lowest_runs(sl: SplitLevel) -> list:
    """The judged runs (``LineString``) of the shell's lowest level."""
    lv = sl.run_levels or (None,) * len(sl.runs)
    return [r for i, ((r, _f), k) in enumerate(zip(sl.runs, lv, strict=True))
            if k == 0 and i not in sl.minor]


def floor_scope(sl: SplitLevel, floors: FloorCells) -> tuple[str, str]:
    """``(leader, why refused)`` of a shell with NO airside contact (module
    docstring): ``("floor", "")`` on a ramp-class floor, ``("ground", "")``
    otherwise, or a refusal on a basin / channel floor."""
    low = lowest_runs(sl)
    total = sum(r.length for r in low)
    if total <= 0.0:
        return "ground", ""
    on = sum(r.length for r in low if floors.ramp is not None and run_faces(floors.ramp, r))
    if on >= 0.5 * total:
        return "floor", ""
    off = sum(r.length for r in low if floors.other is not None and run_faces(floors.other, r))
    if off >= 0.5 * total:
        return "", (f"{off:.1f} of {total:.1f} m of its lowest level faces a basin or channel "
                    "floor (no row makes a block follow one)")
    return "ground", ""


def ground_datum(sl: SplitLevel, dem_z, air) -> "float | None":
    """The ``ground`` leader's datum (module docstring), or ``None`` where
    no judged groundside run reads the ground."""
    if dem_z is None or not sl.levels:
        return None
    centre = (sl.plan if sl.plan is not None else sl.footprint).centroid.coords[0]
    lv = sl.run_levels or (None,) * len(sl.runs)
    pairs = []
    for i, ((r, f), k) in enumerate(zip(sl.runs, lv, strict=True)):
        if f is None or k is None or i in sl.minor or r.length <= 0.0:
            continue
        if air is not None and run_faces(air, r):
            continue
        zs = _ground(dem_z, r, centre)
        if zs:
            pairs.append((_st.median(zs) - float(f), r.length))
    if not pairs:
        return None
    return round(float(sl.levels[0]) + _weighted_median(pairs), 3)


def shell_level_s(shells: _t.Sequence[SplitLevel], tid: str, axis, half: float,
                  climb_from: float, reach: float) -> tuple["float | None", list[str]]:
    """THE FLOOR IS LEVEL ALONG A SHELL THAT STANDS ON IT (#2062 R3b B,
    owner RULINGS 2026-11-13x (2): nothing along a shell's base stands
    above its wall foot): ``(the far station along the corridor's ``axis``
    of every floor-scope shell's lowest-level runs facing it, refusals)``.
    A shell with no airside contact FACES the corridor when half its lowest
    level's run length or more has its outside stations within ``half`` +
    ``split_level._GROUND_OUT_M`` of the axis; its far station counts when
    its near one lies within the LEVEL ZONE (``climb_from`` + ``reach``),
    else the shell is refused by name (the ramp would climb along it)."""
    from shapely.geometry import Point
    from ..airport.split_level import _GROUND_OUT_M, _stations
    far: "float | None" = None
    why: list[str] = []
    band = axis.buffer(half + _GROUND_OUT_M + 0.5)
    for sl in shells:
        if sl.air_level is not None or len(sl.levels) < 2:
            continue
        low = lowest_runs(sl)
        total = sum(r.length for r in low)
        if total <= 0.0:
            continue
        centre = (sl.plan if sl.plan is not None else sl.footprint).centroid.coords[0]
        on = [r for r in low if all(band.contains(Point(p)) for p in _stations(r, centre))]
        if sum(r.length for r in on) < 0.5 * total:
            continue
        ss = [axis.project(Point(p)) for r in on for p in r.coords]
        near, top = min(ss), max(ss)
        if near > climb_from + reach:
            why.append(f"{tid}: storey shell {sl.id} stands along the climb (its lowest "
                       f"level from s {near:.1f} m, the level zone to {climb_from + reach:.1f} m) "
                       "-- refused, the ramp would rise along its wall (R3b B)")
            continue
        far = top if far is None else max(far, top)
    return far, why
