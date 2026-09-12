"""THE DOOR RAMPS AND SUNKEN ROADS AS STRUCTURES TO BUILD (RULINGS
2026-09-08b/c; spec ``docs/specs/auto-patch-v2/othh-terminal-ramps-
spec.md`` §2 / §3): the readings of ``airport/door_wells.py`` and
``airport/sunken_roads.py`` turned into the build groups
``planar/structures.py`` runs through its ONE ramp / void / rim
machinery (the 05n object-corridor path), so every consumer of a tunnel
structure is a consumer here (spec §4).

LAW A — the DOOR RAMP.  s = 0 stands ``cutout.floor_overlap_m`` inside
the building face (the well floor overlaps the face, as an object
corridor's floor overlaps its end wall); the well = the "walls" (its
reach ⊕ the overlaps), the floor there the SILL; the climb starts at
the well's outer edge at ``cutout.door.ramp_grade`` along the face's
outward normal (a straight axis) and tops where it meets the ground
within ``cutout.door.max_length_m``; the ramp is the sill's width; the
rim ``rim_standoff`` of the well's side walls inside the well (09-08a),
the OSM stand-off beyond it; the ramp STOPS at a pavement it would
enter (``Group.stop_at_pavement``).  A ``door_ramp`` face, never
``tunnel_ramp`` (spec §4: a different generation and a different
oracle law; since RULINGS 2026-09-12m the two FACE caps are both 8 %).

LAW B — the SUNKEN ROAD.  s = 0 at the deep-end cut (the plate at
``max_depth_m``), the axis the plate's own to the top, the floor the
plate's y per station (``Group.profile``, pinned by the generator), the
half widths the plate's, the rim ``rim_standoff`` of the measured side
walls; a plate steeper than ``tunnel.ramp_max_grade`` is refused here
(the ramp law prices every ring pair at that cap).  ``tunnel_ramp``
faces, as any ramp.

Both: ``seat = "none"`` — the groups carry ``plate_y`` 0 and are never
plate-seated (``pipeline/build._plate_seats`` reads ``source ==
"object"`` only).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..model.frame import XY
from .basins import shell_thickness_m
from .object_corridor import Group
from .structure_approach import unit
from .structure_geometry import rim_standoff

__all__ = ["RampCorridor", "door_groups", "sunken_groups"]


@_dc.dataclass(frozen=True)
class RampCorridor:
    """The corridor record a door / sunken-road group carries — the
    fields ``build_structures`` reads off an object corridor
    (``airport/tunnel_objects.Corridor``), no more: ``axis`` the trench
    inside the "walls" (the well / the plate), ``trench`` the floor
    plate (the 05n-2 assertion measures the emitted floor against it),
    ``footprint`` what the trench cuts as a hull (every cell, pads
    included — 08-26)."""

    id: str
    resource: str
    objects: tuple[str, ...]
    axis: tuple[XY, ...]
    length_m: float
    width_m: float
    mouth_thickness_m: float
    far_thickness_m: float
    mouth_kind: str
    mouth_dem_z: float
    floor_z: float
    walls: Polygon
    trench: Polygon
    footprint: Polygon
    anchor_xy: XY
    anchor_dem_z: float
    agl_m: float
    depth_m: float
    notes: tuple[str, ...] = ()
    plate_y: float = 0.0
    mouth_closed: bool = True
    far_closed: bool = False
    flat: bool = False
    edge_wall: bool = False

    @property
    def ends(self) -> str:
        return f"{'closed' if self.mouth_closed else 'open'}/{'closed' if self.far_closed else 'open'}"

    @property
    def ground_kind(self) -> str:
        return "open"


def door_groups(wells: _t.Sequence, law: Law) -> list[Group]:
    """Law A: one group per door well (module doc)."""
    tn = law.tables.structures.tunnel
    co = law.tables.structures.cutout
    dl = co.door
    grid = law.tables.emit.identity.min_distinct_spacing_m
    overlap = co.floor_overlap_m
    osm_rim = tn.wall_gap_m + tn.wall_band_width_m
    t_max = tn.object.wall_face_max_thickness_m
    out: list[Group] = []
    for w in wells:
        n = w.normal
        half = w.sill_width_m / 2.0
        hull_s = w.plate_out_m + 2.0 * overlap
        p0 = (w.sill_mid[0] - n[0] * overlap, w.sill_mid[1] - n[1] * overlap)
        reach = hull_s + dl.max_length_m + 3.0 * dl.station_m
        path = [p0, (p0[0] + n[0] * reach, p0[1] + n[1] * reach)]
        p_hull = (p0[0] + n[0] * hull_s, p0[1] + n[1] * hull_s)
        # the well's side walls (the rim's law, 09-08a): the plate-to-shell
        # distance off the sill line (``basins.shell_thickness_m``)
        t_side = shell_thickness_m(w.region, w.plate, grid, t_max, exclude=w.sill_line.buffer(grid))
        _inset, standoff = rim_standoff(t_side, co, grid)
        notes = tuple(w.notes) + (f"side walls {t_side:.2f} m thick: rim stand-off {standoff:.2f} m "
                                  f"off the floor ring (09-08a)",)

        def half_fn(s: float, _h=half, _ov=overlap, _L=hull_s) -> tuple[float, float]:
            return (_h + _ov, _h + _ov) if s <= _L + 1e-6 else (_h, _h)

        def rim_fn(s: float, _so=standoff, _L=hull_s, _b=osm_rim) -> tuple[float, float]:
            return (_so, _so) if s <= _L + 1e-6 else (_b, _b)

        c = RampCorridor(w.id, w.resource, tuple(w.objects), (p0, p_hull), hull_s,
                         w.sill_width_m, t_side, t_side, "door",
                         w.ground_z, w.sill_z, w.region, w.plate, w.region, w.anchor_xy,
                         w.anchor_dem_z, w.agl_m, w.depth_m, notes)
        out.append(Group([], p0, (-n[0], -n[1]), w.sill_width_m, path, c, w.id, hull_s, True,
                         True, False, half_fn, rim_fn, standoff, None, dl.ramp_grade,
                         kind="door", max_grade=dl.ramp_grade, max_length_m=dl.max_length_m,
                         spacing_m=dl.station_m, climb_from_s=hull_s, stop_at_pavement=True,
                         straight=True))
    return out


def _interp_station(sts, s: float) -> tuple[float, float]:
    if s <= sts[0].s + 1e-9:
        return sts[0].half_l, sts[0].half_r
    if s >= sts[-1].s - 1e-9:
        return sts[-1].half_l, sts[-1].half_r
    for a, b in zip(sts[:-1], sts[1:]):
        if a.s <= s <= b.s:
            f = (s - a.s) / max(b.s - a.s, 1e-9)
            return a.half_l + (b.half_l - a.half_l) * f, a.half_r + (b.half_r - a.half_r) * f
    return sts[-1].half_l, sts[-1].half_r


def sunken_groups(roads: _t.Sequence, law: Law, refused: list[str] | None = None
                  ) -> list[Group]:
    """Law B: one group per sunken road (module doc); a plate steeper than
    the ramp law is refused into ``refused``."""
    tn = law.tables.structures.tunnel
    co = law.tables.structures.cutout
    sr = co.sunken_road
    grid = law.tables.emit.identity.min_distinct_spacing_m
    overlap = co.floor_overlap_m
    osm_rim = tn.wall_gap_m + tn.wall_band_width_m
    t_max = tn.object.wall_face_max_thickness_m
    out: list[Group] = []
    for r in roads:
        sts = r.stations
        L = r.length_m
        steepest = max(abs(b.z - a.z) / max(b.s - a.s, 1e-9) for a, b in zip(sts[:-1], sts[1:]))
        if steepest > tn.ramp_max_grade + 1e-9:
            if refused is not None:
                refused.append(f"{r.id}: the plate descends at {100.0 * steepest:.2f} % between "
                               f"stations (> tunnel.ramp_max_grade {100.0 * tn.ramp_max_grade:.0f} %): "
                               f"the ramp law prices every ring pair at the cap")
            continue
        axis = list(r.axis)
        u0 = unit(axis[0], axis[1])
        # the side walls: the plate-to-footprint distance off the two ends
        ends = unary_union([Point(axis[0]).buffer(sr.station_m), Point(axis[-1]).buffer(sr.station_m)])
        t_side = shell_thickness_m(r.region, r.plate, grid, t_max, exclude=ends)
        _inset, standoff = rim_standoff(t_side, co, grid)
        notes = tuple(r.notes) + (f"side walls {t_side:.2f} m thick: rim stand-off {standoff:.2f} m "
                                  f"off the floor ring (09-08a)",)

        def half_fn(s: float, _sts=sts, _ov=overlap) -> tuple[float, float]:
            hl, hr = _interp_station(_sts, s)
            return hl + _ov, hr + _ov

        def rim_fn(s: float, _so=standoff, _L=L, _b=osm_rim) -> tuple[float, float]:
            return (_so, _so) if s <= _L + 1e-6 else (_b, _b)

        c = RampCorridor(r.id, r.resource, tuple(r.objects), tuple(axis), L, r.width_m,
                         t_side, t_side, "cut", r.mouth_dem_z, r.floor_z,
                         r.region, r.plate, r.region, r.anchor_xy, r.anchor_dem_z, r.agl_m,
                         r.depth_m, notes)
        out.append(Group([], axis[0], (-u0[0], -u0[1]), r.width_m, axis, c, r.id, L, True, True,
                         False, half_fn, rim_fn, standoff, None,
                         min(tn.ramp_max_grade, r.depth_m / max(L, 1e-9)), kind="sunken_road",
                         spacing_m=sr.station_m, profile=tuple(r.profile)))
    return out
