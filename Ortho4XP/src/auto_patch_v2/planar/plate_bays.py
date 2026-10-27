"""THE BAY A PLATE'S WALLS FRAME (owner RULINGS 2026-10-28h (1), #414):
a sunken-road plate the family's walls frame the other way
(``airport/plate_frame.walls_frame``) is built as the BAY those walls
frame — one Law C wall-corridor record, so it is read by exactly the path
an owner-approved dock bay is: closed at the plate's grade end (s = 0),
its floor the plate's own deepest level there, open at the far end of the
walls, the ramp running the walls' length at the grade the walls give
(``wall_corridor_ramps.full_wall_ramp``, RULINGS 2026-10-07b (2) / 07e),
standing inside its own walls and never clipped by a building pad (a Law C
ramp's walls are senior to a pad, 05k-1 / 08-26).

:func:`plate_bays` is the one site; nothing numeric lives here.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..airport.tunnel_walls import Station
from ..airport.wall_corridors import CLASS_BAY, ID_PREFIX, WallCorridorRecord, _trench
from ..law import Law
from ..model.frame import XY

__all__ = ["plate_bays"]


def plate_bays(roads: _t.Sequence, walls: _t.Sequence, law: Law, dem_z
               ) -> tuple[list, list[WallCorridorRecord]]:
    """``(the roads Law B still reads, the bays the framed ones are)``.  A
    framed plate standing for the most part (``end_cap_cover_min`` of its
    area) inside a corridor Law C already read from its walls (``walls``)
    IS that bay: it is not built twice."""
    share = law.tables.structures.cutout.wall_corridor.end_cap_cover_min
    kept: list = []
    bays: list[WallCorridorRecord] = []
    for r in roads:
        if getattr(r, "framed", None) is None:
            kept.append(r)
        elif not any(w.trench.intersection(r.plate).area >= share * r.plate.area for w in walls):
            bays.append(_bay(r, law, dem_z))
    return kept, bays


def _bay(r, law: Law, dem_z) -> WallCorridorRecord:
    """The bay record of one framed plate (module doc)."""
    f = r.framed
    co = law.tables.structures.cutout
    ob = law.tables.structures.tunnel.object
    grid = law.tables.emit.identity.min_distinct_spacing_m
    u = f.u
    # the closed end's floor overlap behind the mouth, as a bay's (Law C)
    start = (f.closed_xy[0] - u[0] * co.floor_overlap_m, f.closed_xy[1] - u[1] * co.floor_overlap_m)
    total = f.wall_length_m + co.floor_overlap_m
    ss = [ob.wall_sample_m * k for k in range(int(total // ob.wall_sample_m) + 1)]
    if total - ss[-1] > 1e-6:
        ss.append(total)
    axis: list[XY] = [(start[0] + u[0] * s, start[1] + u[1] * s) for s in ss]
    # the side walls' plan thickness, at least the lattice spacing — as a
    # Law C station reads it (``tunnel_walls.stations_along``)
    t = max(grid, f.thick_m)
    sts = tuple(Station(s, f.half_m, f.half_m, t, t) for s in ss)
    floor = min(st.z for st in r.stations)
    grounds = tuple(float(dem_z(*p)) for p in axis)
    trench = _trench(axis, sts)
    walls = r.region.difference(trench)
    if walls.is_empty:
        walls = trench.buffer(t, join_style="mitre").difference(trench)
    footprint = _as_polygon(unary_union([walls, trench]))
    name, k = r.id.split(":", 1)[1].rsplit("@", 1)
    note = (f"walls frame the plate the other way (2026-10-28h (1)): the plate of {name} is at "
            f"grade against the family face that closes the lane ({f.closed_cover:.0%} covered) "
            f"and deepest at the open end ({f.open_cover:.0%}); read as a closed bay, floor "
            f"{floor:.2f} at the closed end, walls {f.wall_length_m:.1f} m ({f.sides} side "
            f"wall(s)), a ramp beyond the open end")
    return WallCorridorRecord(
        f"{ID_PREFIX}:{name}@plate{k}", r.resource, tuple(r.objects), f.family, CLASS_BAY,
        tuple(axis), sts, tuple(floor for _ in ss), grounds, float(total), 2.0 * f.half_m,
        True, False, t, 0.0, walls, trench, footprint, r.anchor_xy,
        r.anchor_dem_z, r.agl_m, None, 0.0, "", tuple(r.notes) + (note,))


def _as_polygon(g) -> Polygon:
    return g if g.geom_type == "Polygon" else Polygon(g.convex_hull.exterior.coords)
