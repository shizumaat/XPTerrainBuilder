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
* THE BACK IS CUT DOWN (owner sim read 2026-11-05T23:55Z, SBSP / KLAX
  #1909: "the apron should extend up to the building face on the
  airside, while the outside retaining wall and building floors should be
  exposed by cutting the terrain down around the back"): the pit reaches
  ``[building_pad] split_level_back_cut_m`` outside every TALL side (its
  walls run down to the lower floor), so the floor -- the lower floor --
  runs out past them and the rim climbs back to the ground beyond; the
  open side stays the rim, flush at the upper floor.  The reach yields to
  the runway family, structures, other pits and every airside pavement
  (the frontage roles: the cut is groundside only, no airside trench; it
  is clipped, never refused);
* every member of the building is seated with its lower floor ON the
  floor (``pipeline/rebake_inputs``, ``Basin.kind`` ``split_level``: one
  frame, one seat), with no plate clearance (a floor, not a plate:
  ``Basin.clearance_m`` 0).

Refused, by name: a building over the runway family, over a structure, or
over another pit.  Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.prepared import prep

from ..airport.split_level import SplitLevel, read_split_levels
from ..geom.parts import polygon_parts_with_area
from ..law.tables import frontage_roles
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
    fr = frontage_roles(law)
    air = unary_union([p for p, c in zip(polys, cells, strict=True) if c.role in fr]).buffer(0)
    sls, notes = read_split_levels(objects, cache, law, getattr(airport.dem, "z", None),
                                   None if air.is_empty else prep(air))
    if not sls:
        return [], [], [], notes, []
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    band = float(law.tables.structures.cutout.ring_floor_m)
    reach = float(getattr(law.tables.structures.building_pad, "split_level_back_cut_m", 0.0)
                  or 0.0)
    hard = [p for p, c in zip(polys, cells, strict=True)
            if c.role in runway_roles or c.kind == "structure"]
    blocked = unary_union(list(hard) + list(taken)) if (hard or taken) else None
    basins: list[Basin] = []
    new_cells: list[tuple] = []
    knives: list[Polygon] = []
    refused: list[str] = []
    boxes = [_rim(sl.footprint, 0.0, grid) for sl in sls]
    pits = None                      # the split-level pits cut so far
    for i, sl in enumerate(sls):
        k = k0 + len(basins)
        box = boxes[i]
        name = sl.paths[0].rsplit("/", 1)[-1]
        if box is None:
            refused.append(f"{sl.id} {name}: the split-level box does not survive the grid")
            continue
        if blocked is not None and box.intersects(blocked):
            refused.append(f"{sl.id} {name}: the split-level box meets the runway family, a "
                           "structure or another pit")
            continue
        # A ROW OF SPLIT-LEVEL BUILDINGS (SBSP's hangars on the embankment)
        # shares walls: a box yields what a neighbour's pit already took
        own = box if pits is None else _largest(box.difference(pits))
        if own is None or own.area < 0.5 * box.area:
            refused.append(f"{sl.id} {name}: the split-level box is taken by a neighbour's pit")
            continue
        # the back is cut on the groundside only: never into airside
        # pavement, a neighbour's box or its pit
        others = [b for j, b in enumerate(boxes) if j != i and b is not None]
        keep = unary_union([g for g in [blocked, None if air.is_empty else air, pits, *others]
                            if g is not None])
        rim = _rim(_cut_region(sl, reach, keep, own), 0.0, grid) or own
        if pits is not None:
            rim = _largest(rim.difference(pits)) or own
        floors = _region_floor(rim, band, [], grid)
        if not floors:
            refused.append(f"{sl.id} {name}: no floor inside the {band:.2f} m wall band")
            continue
        pits = rim if pits is None else pits.union(rim)
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


def _largest(geom) -> "Polygon | None":
    """The largest polygon part of ``geom``, or ``None``."""
    parts = polygon_parts_with_area(geom)
    return max(parts, key=lambda g: g.area) if parts else None


def _cut_region(sl: SplitLevel, reach: float, blocked, footprint=None) -> Polygon:
    """The pit's plan (module docstring): the building's box (``footprint``,
    default ``sl.footprint``) and, ``reach`` outside its TALL sides
    (``SplitLevel.closed_sides``, chained so two meeting sides take the
    corner between them), the strip the back is cut down in, less
    ``blocked``; the part holding the box."""
    foot = sl.footprint if footprint is None else footprint
    if reach <= 0.0 or not sl.closed_sides:
        return foot
    sides = unary_union(list(sl.closed_sides))
    # one tall side unions to a LineString, which linemerge refuses
    chain = sides if sides.geom_type == "LineString" else linemerge(sides)
    strip = chain.buffer(reach, cap_style="flat", join_style="mitre").difference(sl.footprint)
    if blocked is not None:
        strip = strip.difference(blocked)
    region = unary_union([foot, strip]).buffer(0)
    parts = [g for g in getattr(region, "geoms", [region]) if g.intersects(foot)]
    return max(parts, key=lambda g: g.area) if parts else foot


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
                            for s in sl.open_sides),
        closed_sides_ll=tuple(tuple(tuple(float(q) for q in to_ll(x, y)) for x, y in s.coords)
                              for s in sl.closed_sides), clearance_m=0.0)
