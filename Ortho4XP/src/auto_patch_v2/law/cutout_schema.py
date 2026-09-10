"""The ``structures.toml [cutout]`` schema — every below-grade OBJECT's
trench (RULINGS 2026-09-06b (1), 2026-09-08a) and the two ramp laws the
OTHH terminal read added (RULINGS 2026-09-08b/c; spec
``docs/specs/auto-patch-v2/othh-terminal-ramps-spec.md``): the DOOR RAMP
(``[cutout.door]``, §2) and the SUNKEN ROAD (``[cutout.sunken_road]``,
§3).  Kept beside ``model.py`` under the 1,000-line file law.  Values
live in the TOML; no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Cutout", "Door", "SunkenRoad", "WallCorridor", "check_cutout", "SEAT_NONE",
           "WALL_BOTTOM"]

#: The only seat law the two ramp families generate: the anchor family
#: is NEVER re-seated by the trench (spec §2 / §3 ``seat = "none"``).
SEAT_NONE = "none"
#: The only floor datum Law C generates: the walls' bottom edge per station.
WALL_BOTTOM = "wall_bottom"


@_dc.dataclass(frozen=True)
class Door:
    """Law A — the DOOR RAMP (spec §2): where a below-grade floor plate
    reaches the object's exterior face, a trench of the sill's width from
    the sill up to grade at ``ramp_grade``, outside the building along
    the face's outward normal."""

    sill_min_depth_m: float      # the door's own gate, separate from basin.admission_depth_m
    sill_min_width_m: float      # narrower is a drain, not a door
    sill_max_width_m: float      # wider is a service yard / a parking pit, not a door (spawner 2026-09-08j; the owner's doors are 3.7-5.7 m)
    exit_max_fraction: float     # the side opposite the face may run along the building over at most this share of its length (else enclosed)
    ramp_grade: float            # the climb beyond the well (the owner's "small ramp")
    max_length_m: float          # a climb longer than this is refused loudly
    station_m: float             # ramp station spacing (the climb's ring vertices)
    seat: str                    # "none": the door family never re-seats (spec §2)


@_dc.dataclass(frozen=True)
class SunkenRoad:
    """Law B — the SUNKEN ROAD under the building (spec §3): a roofed
    descending plate reaching grade at one end; the trench = the plate
    along its axis, the floor the plate's own y per station, cut only to
    ``max_depth_m``; the deck above untouched."""

    max_depth_m: float           # the cut ends where the plate reaches this depth (deeper = the underground road)
    top_depth_m: float           # the trench's top station: the plate within this of the ground
    min_descent_m: float         # the plate descends at least this from its grade end (a kerb dip is not a road)
    min_plate_m2: float          # a connected plate smaller than this is not a road
    roof_min_fraction: float     # the plate lies under the family's above-band solids over at least this share: ROOFED (spec §3)
    station_m: float             # station spacing along the plate's axis
    seat: str                    # "none": the family never re-seats (spec §3)


@_dc.dataclass(frozen=True)
class WallCorridor:
    """Law C — the WALL-BOTTOM FLOOR corridor (RULINGS 2026-09-08m/08n;
    spec §6): two parallel kerb-wall bands of one anchor family with no
    floor; the floor is the walls' bottom per station (level, or a
    descending garage ramp cut as authored); an open end ramps at
    ``ramp_grade``, steepening to ``max_ramp_grade`` where airside
    pavement stops it."""

    mouth_depth: str             # "wall_bottom": the only generated datum
    min_wall_depth_m: float      # a band reaches this far under the ground
    parallel_max_deg: float      # two bands pair when their axes agree within this
    min_width_m: float           # inner faces at least this apart
    max_width_m: float           # ...and at most this
    min_wall_length_m: float     # the bands overlap at least this along the axis
    merge_gap_m: float           # parallel bands within a wall's thickness laterally and this along the axis are one wall
    end_cap_cover_min: float     # a crossing family face covering this share of an end line closes it
    corridor_mouth_road_m: float    # RULINGS 2026-09-10z (b''): a road within this of a mouth, ANY heading, opens it onto groundside
    min_headroom_m: float        # the lowest near-horizontal face over the corridor above its floor
    ramp_grade: float            # the synthetic climb beyond a mouth
    max_ramp_grade: float        # ...steepened up to this at an airside stop (= the wall_corridor_ramp cap)
    max_authored_grade: float    # a descending wall bottom steeper than this is refused (= the garage_ramp cap)
    station_m: float             # ramp station spacing beyond the walls
    seat: str                    # "none": the family never re-seats


@_dc.dataclass(frozen=True)
class Cutout:
    """Below-grade object trench: floor ⊕ overlap, rim INSIDE the wall,
    no band (06b (1), 09-08a); the door and sunken-road ramp laws."""

    floor_overlap_m: float
    rim_inset_fraction: float
    emit_wall_band: bool
    door: Door
    sunken_road: SunkenRoad
    wall_corridor: WallCorridor


def check_cutout(co: Cutout, door_cap: float | None, err: type[Exception],
                 wall_corridor_cap: float | None = None, garage_cap: float | None = None
                 ) -> None:
    """The cross-file rules of the two ramp laws: the seat law is the only
    generated value; a door ramp's design grade never exceeds the
    ``door_ramp`` role's own longitudinal cap (``rulesets.toml
    [common.roles]`` — the cap both instruments price)."""
    if co.door.seat != SEAT_NONE:
        raise err(f"structures.cutout.door.seat {co.door.seat!r}: only {SEAT_NONE!r} is generated")
    if co.sunken_road.seat != SEAT_NONE:
        raise err(f"structures.cutout.sunken_road.seat {co.sunken_road.seat!r}: only "
                  f"{SEAT_NONE!r} is generated")
    if door_cap is None:
        raise err("rulesets.common.roles.door_ramp: the door ramp role carries no cap")
    if co.door.ramp_grade > door_cap:
        raise err(f"structures.cutout.door.ramp_grade {co.door.ramp_grade} exceeds the door_ramp "
                  f"role's longitudinal cap {door_cap}")
    if co.door.sill_min_depth_m <= 0.0 or co.door.max_length_m <= 0.0 or co.door.station_m <= 0.0:
        raise err("structures.cutout.door: sill_min_depth_m / max_length_m / station_m must be > 0")
    if co.sunken_road.max_depth_m <= 0.0 or co.sunken_road.station_m <= 0.0:
        raise err("structures.cutout.sunken_road: max_depth_m / station_m must be > 0")
    wc = co.wall_corridor
    if wc.seat != SEAT_NONE:
        raise err(f"structures.cutout.wall_corridor.seat {wc.seat!r}: only {SEAT_NONE!r} is generated")
    if wc.mouth_depth != WALL_BOTTOM:
        raise err(f"structures.cutout.wall_corridor.mouth_depth {wc.mouth_depth!r}: only "
                  f"{WALL_BOTTOM!r} is generated (RULINGS 2026-09-08m/08n)")
    if wall_corridor_cap is None or garage_cap is None:
        raise err("rulesets.common.roles: wall_corridor_ramp / garage_ramp carry no cap")
    if wc.max_ramp_grade != wall_corridor_cap:
        raise err(f"structures.cutout.wall_corridor.max_ramp_grade {wc.max_ramp_grade} is not the "
                  f"wall_corridor_ramp role's longitudinal cap {wall_corridor_cap}")
    if wc.max_authored_grade != garage_cap:
        raise err(f"structures.cutout.wall_corridor.max_authored_grade {wc.max_authored_grade} is "
                  f"not the garage_ramp role's longitudinal cap {garage_cap}")
    if not (0.0 < wc.ramp_grade <= wc.max_ramp_grade):
        raise err("structures.cutout.wall_corridor: 0 < ramp_grade <= max_ramp_grade")
    if not (0.0 < wc.min_width_m < wc.max_width_m) or wc.min_wall_depth_m <= 0.0 \
            or wc.min_wall_length_m <= 0.0 or wc.station_m <= 0.0 or wc.min_headroom_m <= 0.0 \
            or wc.merge_gap_m < 0.0:
        raise err("structures.cutout.wall_corridor: widths, depth, length, station and headroom "
                  "must be > 0 with min_width_m < max_width_m")
    if not (0.0 < wc.end_cap_cover_min <= 1.0):
        raise err("structures.cutout.wall_corridor.end_cap_cover_min must lie in (0, 1]")
    # RULINGS 2026-09-10z (b''): the groundside-mouth test's window
    if wc.corridor_mouth_road_m <= 0.0:
        raise err("structures.cutout.wall_corridor: corridor_mouth_road_m must be > 0")
