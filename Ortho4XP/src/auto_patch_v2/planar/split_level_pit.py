"""THE SPLIT-LEVEL BUILDING'S PIT (owner 2026-11-05: "it gets a pad at the
lower level so the upper level sits at the graded upper height ... almost
the same logic as a tunnel mouth object"; #1886, #1905).

A building ``airport/split_level`` reads as split-level stands with its
lower floor ``y_lo`` on the low ground and its open side -- the lower
storeys' open wall, inside the terrain -- against the higher ground at its
upper floor ``y_up``.  It is minted as a BASIN (``planar/basins``: the cut
under an object is the object's): the RIM is the building's wall box, the
FLOOR is the rim less the ``[cutout] ring_floor_m`` wall band (the mesh's
wall, under the building's own wall), and

* the floor FOLLOWS THE OPEN SIDE'S RIM ``y_up - y_lo`` down
  (``constraints/structures.basins`` over :attr:`Basin.open_sides`): the
  upper floor sits at the graded upper ground, wherever the solve puts it;
* the rim is the ground's (the DEM where bare, the governed ground where
  shared): on the open side the terrain is held up to the wall, no gap;
* every member of the building is seated with its lower floor ON the
  floor (``pipeline/rebake_inputs``, ``Basin.kind`` ``split_level``: one
  frame, one seat), with no plate clearance (a floor, not a plate:
  ``Basin.clearance_m`` 0).

Refused, by name: a building over the runway family, over a structure, or
over another pit; and a box a mapped ROAD RUNS THROUGH (an OSM ``highway`` line
cuts the box in two or more pieces): the "open" sides of an underpass are a road's
way under it, and pitting it sank the bridge with its deck under the
ground (#1903 KBNA 1.0.470, the Murfreesboro Pike underpass).  Nothing
here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..airport.split_level import SplitLevel, read_split_levels
from ..geom.fixed_overlay import is_hairline
from ..geom.parts import polygon_parts_with_area
from ..model.structures import Basin
from .basin_geometry import _region_floor, _rim

__all__ = ["SPLIT_KIND", "split_level_pits"]

#: the ``Basin.kind`` of a split-level building's pit
SPLIT_KIND = "split_level"


def split_level_pits(airport, cells, polys, law, objects, cache, k0: int,
                     taken: _t.Sequence[Polygon], floor_role: str, wall_role: str,
                     runway_roles: _t.Collection[str]
                     ) -> tuple[list[Basin], list[tuple], list[Polygon], list[str], list[str]]:
    """``(basins, new cells, knives, notes, refusals)`` of every split-level
    building of ``objects`` (module docstring); refs numbered from ``k0``."""
    sls, notes = read_split_levels(objects, cache, law, getattr(airport.dem, "z", None))
    if not sls:
        return [], [], [], notes, []
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    band = float(law.tables.structures.cutout.ring_floor_m)
    hard = [p for p, c in zip(polys, cells, strict=True)
            if c.role in runway_roles or c.kind == "structure"]
    blocked = unary_union(list(hard) + list(taken)) if (hard or taken) else None
    roads = _roads(airport)
    basins: list[Basin] = []
    new_cells: list[tuple] = []
    knives: list[Polygon] = []
    refused: list[str] = []
    for sl in sls:
        k = k0 + len(basins)
        rim = _rim(sl.footprint, 0.0, grid)
        name = sl.paths[0].rsplit("/", 1)[-1]
        if rim is None:
            refused.append(f"{sl.id} {name}: the split-level box does not survive the grid")
            continue
        if blocked is not None and rim.intersects(blocked):
            refused.append(f"{sl.id} {name}: the split-level box meets the runway family, a "
                           "structure or another pit")
            continue
        if _road_through(rim, roads, grid):
            refused.append(f"{sl.id} {name}: a mapped road runs through the split-level box "
                           "(it cuts the box in two or more pieces) — a road's underpass, "
                           "not a building cut into a slope")
            continue
        floors = _region_floor(rim, band, [], grid)
        if not floors:
            refused.append(f"{sl.id} {name}: no floor inside the {band:.2f} m wall band")
            continue
        blocked = rim if blocked is None else blocked.union(rim)
        floor_ref, wall_ref = f"basin_floor:{k}", f"basin_wall:{k}"
        for j, f in enumerate(floors):
            new_cells.append((floor_role, floor_ref if j == 0 else f"{floor_ref}#{j}", f,
                              tuple(tuple(h.coords)[:-1] for h in f.interiors)))
        for part in polygon_parts_with_area(rim.difference(unary_union(floors))):
            new_cells.append((wall_role, wall_ref, part,
                              tuple(tuple(h.coords)[:-1] for h in part.interiors)))
        knives.append(rim)
        basins.append(_record(airport, sl, k, rim, floors, floor_ref, wall_ref))
    return basins, new_cells, knives, notes, refused


#: OSM ``highway`` values no vehicle runs on: a footpath may cross a
#: building in the map (an indoor corridor), a road never does
_ON_FOOT = frozenset({"footway", "path", "steps", "pedestrian", "cycleway", "corridor",
                      "bridleway", "elevator"})


def _roads(airport) -> list[LineString]:
    """The mapped roads: every OSM way whose ``highway`` a vehicle runs
    on, as built, bridged or tunnelled.  The OSM line, not the classified
    cell: a road under a pack structure is cut out of the cells there (the
    structure's own ramp, ``planar/structure_service``) but its way still
    runs on."""
    return [LineString(w.points) for w in getattr(airport, "osm_ways", ()) or ()
            if (w.tags or {}).get("highway", "") not in ("", *_ON_FOOT)
            and len(w.points) >= 2]


def _road_through(rim: Polygon, roads: _t.Sequence[LineString], grid: float) -> bool:
    """A road RUNS THROUGH ``rim``: the box less the roads crossing it
    (``grid`` wide) falls into two or more pieces wider than the grid."""
    hit = [ln.buffer(0.5 * grid, cap_style="flat") for ln in roads if ln.intersects(rim)]
    if not hit:
        return False
    rest = [q for q in polygon_parts_with_area(rim.difference(unary_union(hit)))
            if not is_hairline(q, grid)]
    return len(rest) >= 2


def _record(airport, sl: SplitLevel, k: int, rim: Polygon, floors, floor_ref: str,
            wall_ref: str) -> Basin:
    step = float(sl.y_up - sl.y_lo)
    floor_z = float(sl.ground_open_m) - step
    c = rim.representative_point()
    to_ll = airport.frame.transformers()[1]
    lat, lon = to_ll(c.x, c.y)
    return Basin(
        id=f"basin:{k}", objects=tuple(sl.paths), floor_z=floor_z, floor_ref=floor_ref,
        wall_ref=wall_ref, ring=tuple(floors[0].exterior.coords)[:-1],
        wall_path=tuple(rim.exterior.coords)[:-1], rim_estimate_m=float(sl.ground_open_m),
        solid_min_z=floor_z, solid_min_y_m=-step, covered_fraction=0.0,
        area_m2=float(sum(f.area for f in floors)), anchor_ll=(float(lat), float(lon)),
        notes=(SPLIT_KIND, f"lower floor y {sl.y_lo:+.2f}, upper floor y {sl.y_up:+.2f} on "
               f"the open side(s) ({len(sl.open_sides)}); ground open {sl.ground_open_m:.2f}"
               f" / closed {sl.ground_closed_m:.2f} (DEM)"),
        kind=SPLIT_KIND, region=tuple(rim.exterior.coords)[:-1],
        member_ids=tuple(sl.member_ids), plate_y_m=float(sl.y_lo), witness_id=sl.id,
        anchor_inside_floor=any(f.contains(Point(sl.anchor_xy)) for f in floors),
        open_sides=tuple(tuple(s.coords) for s in sl.open_sides),
        open_sides_ll=tuple(tuple(tuple(float(q) for q in to_ll(x, y)) for x, y in s.coords)
                            for s in sl.open_sides), clearance_m=0.0)
