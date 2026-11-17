"""PARKED CARS MARK A LOT (owner RULINGS 2026-11-16p, #2114 KBNA:
"Agreed with the rule to use cars to identify lots").

A pack draws a car park as rows of parked cars on its ortho photo and
often maps nothing under them — no pavement page, no OSM parking, no lot
facade — so the ground stays raw DEM and reads too steep (KBNA, the lots
round the building at 36.118458, -86.671064).  The cars are the pack's
own statement that the ground is a lot.

THE RULE.  A placed object :func:`airport.facade.is_parked_car` names is a
CAR.  A car counts only SEATED ON THE GROUND (a plain ``OBJECT``, or an
``OBJECT_AGL`` / ``OBJECT_MSL`` within ``[car_lots] ground_m`` of it: a car
on a garage storey or a deck marks no ground), on ground no classified cell
and no building footprint holds (a car on an apron is a ground vehicle; one
inside a lot, a road or a pad is already graded) and not ALONG A ROAD
(its anchor within ``[car_lots] road_side_m`` of a road-cross-section
cell).  Cars within ``link_m`` of each other are
one group (single linkage); a group of at least ``min_cars`` marks a lot.
THE LOT is the ground under the group — every car and every link between
two linked cars, grown by ``car_half_m`` (the car) plus ``margin_m`` (16p
"+ ~3 m"), the ground its cars enclose included — minus every cell
standing and every building; the parts that hold a counted car.
Role ``parking_lot`` (the lot law, 5 %), ref ``carlot:<k>``; a LATE cell
(``model.planar.is_late_ref``) like the §52 facade lot, so the cells
standing are what they were.  It stands OFF every cell standing by the
§52 stand-off (``edge_line_mint.standing_keep_off``, the fence yard's):
it shares no vertex with a pad, a road or another lot.  MEASURED (KBNA
replay vs the test-550 control): welded by the touch witness, 716 nodes
of existing cells moved > 0.1 m (pads 1.28 m, apron 0.46 m); off the
pads' set-back only, 698 (apron 0.34 m); stood off, 198 and no airside
node (roads still move through the §37 (10) reach contact, whose
``[road_contact] extra_roles`` reads a lot within 15 m of a road end).

Read once, after every other cell is minted (``classify/roles``)."""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import MultiLineString, MultiPoint, Polygon
from shapely.ops import unary_union

from ..airport.facade import is_parked_car
from ..law import Law
from ..law.tables import LOT_ROLES, road_family_roles
from ..model.planar import CAR_LOT_PREFIX
from .edge_line_mint import standing_keep_off
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["mint_car_lots", "LOT_ROLE", "CARS_KEY"]

LOT_ROLE = "parking_lot"
#: the cell evidence: how many counted cars stand in the lot
CARS_KEY = "car_lot_cars"


def _groups(xy: np.ndarray, link_m: float) -> tuple[list[list[int]], list[tuple[int, int]]]:
    """Single-linkage groups of the points ``xy`` at ``link_m``, and the
    linking pairs."""
    pairs = sorted(cKDTree(xy).query_pairs(link_m)) if len(xy) > 1 else []
    parent = list(range(len(xy)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in pairs:
        parent[find(i)] = find(j)
    out: dict[int, list[int]] = {}
    for i in range(len(xy)):
        out.setdefault(find(i), []).append(i)
    return list(out.values()), pairs


def _on_ground(o, dem, cfg) -> bool:
    """Whether the pack seats car ``o`` ON THE GROUND: a plain ``OBJECT``
    (X-Plane drapes it), an ``OBJECT_AGL`` at most ``ground_m`` up, or an
    ``OBJECT_MSL`` within ``ground_m`` of the DEM — never a car on a deck or
    a garage storey (KBNA's multi-storey garage, 36.13386, -86.66671:
    1,091 cars at MSL storeys over ground no cell holds)."""
    kind = getattr(o, "kind", "OBJECT")
    if kind == "OBJECT_MSL":
        z = dem.z(*o.xy) if dem is not None else float("nan")
        return bool(abs(o.y_offset_m - z) <= cfg.ground_m)
    return kind != "OBJECT_AGL" or abs(o.y_offset_m) <= cfg.ground_m


def _structures(airport) -> Polygon:
    """Every building footprint the airport reads (a pad or not): a car
    inside one is in a garage or a showroom, and no lot covers one."""
    rings = []
    for b in getattr(airport, "buildings", ()) or ():
        try:
            rings.append(Polygon(b.outer, b.holes).buffer(0.0))
        except (ValueError, TypeError):
            continue
    return unary_union(rings) if rings else Polygon()


def _counted_cars(airport, polys, law: Law, cfg, stats) -> np.ndarray:
    """The car anchors that count: seated on the ground, on no held cell
    or building, not along a road."""
    dem = getattr(airport, "dem", None)
    objs = [o for o in getattr(airport, "dsf_objects", ()) or () if is_parked_car(o.path)]
    stats["cars"] = len(objs)
    cars = np.array([o.xy for o in objs if _on_ground(o, dem, cfg)],
                    dtype=float).reshape(-1, 2)
    stats["cars_raised"] = len(objs) - len(cars)
    if len(cars) < cfg.min_cars:
        return cars[:0]
    held = unary_union([p for _c, p in polys] + [_structures(airport)])
    road_roles = set(road_family_roles(law)) - set(LOT_ROLES)
    roads = unary_union([p for c, p in polys if c.role in road_roles] or [Polygon()])
    on_held = shapely.contains_xy(held, cars[:, 0], cars[:, 1]) if not held.is_empty \
        else np.zeros(len(cars), bool)
    by_road = shapely.dwithin(roads, shapely.points(cars), cfg.road_side_m) \
        if not roads.is_empty else np.zeros(len(cars), bool)
    stats["cars_held"] = int(on_held.sum())
    stats["cars_along_road"] = int((by_road & ~on_held).sum())
    return cars[~on_held & ~by_road]


def _lot_plan(airport, cells: _t.Sequence, law: Law, rules: Rules
                 ) -> tuple[list[tuple[Polygon, int]], dict[str, float]]:
    """The lots the parked cars mark: ``[(part, cars in it)]`` over the
    ground no cell of ``cells`` holds, and the counts."""
    cfg = rules.car_lots
    stats = {"cars": 0, "cars_raised": 0, "cars_held": 0, "cars_along_road": 0, "car_groups": 0,
             "car_lots": 0, "car_lot_m2": 0.0}
    polys = [(c, Polygon(c.ring, c.holes).buffer(0.0)) for c in cells]
    free = _counted_cars(airport, polys, law, cfg, stats)
    groups, pairs = _groups(free, cfg.link_m)
    counted = sorted(i for g in groups if len(g) >= cfg.min_cars for i in g)
    stats["car_groups"] = sum(1 for g in groups if len(g) >= cfg.min_cars)
    if not counted:
        return [], stats
    keep = set(counted)
    links = [(free[i], free[j]) for i, j in pairs if i in keep]
    reach = cfg.car_half_m + cfg.margin_m
    core = unary_union([MultiPoint(free[counted]).buffer(reach),
                        MultiLineString(links).buffer(reach) if links else Polygon()])
    # ground a group's cars ENCLOSE is the lot's (the aisle inside a ring)
    core = unary_union([Polygon(p.exterior) for p in polygon_parts(core)])
    # every PAD's set-back stands (the §52 facade lot's knife): a lot sharing a
    # pad's rim puts the pad's columns in the lot's rows, and the pad and the
    # apron it stands on move (MEASURED KBNA replay, welded by the touch
    # witness: 123 pad nodes up to 1.28 m, apron nodes 0.46 m)
    held = unary_union([standing_keep_off(cells, law), _structures(airport)])
    ground = shapely.set_precision(core.difference(held), rules.cells.snap_grid_m)
    pts = shapely.points(free[counted])
    out = []
    for part in sorted(polygon_parts(ground),
                       key=lambda q: (round(q.bounds[1]), round(q.bounds[0]))):
        n = int(shapely.contains(part, pts).sum())
        if n == 0 or part.area < rules.cells.min_area_m2:
            continue
        out.append((part, n))
        stats["car_lots"] += 1
        stats["car_lot_m2"] += part.area
    return out, stats


def mint_car_lots(airport, cells: list, law: Law, rules: Rules, add) -> dict[str, float]:
    """Mint the car lots onto ``cells`` through ``add`` (the classifier's
    own cell constructor); returns the counts."""
    plan, stats = _lot_plan(airport, cells, law, rules)
    for k, (part, n) in enumerate(plan):
        add(LOT_ROLE, f"{CAR_LOT_PREFIX}:{k}", part, "parking_lot", None, None, {CARS_KEY: n})
    return stats
