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
(``model.planar.is_late_ref``).  It stands OFF every cell standing by the
§52 stand-off (``edge_line_mint.standing_keep_off``, the fence yard's):
it shares no vertex with a pad, a road or another lot.  Its outline is
built of 2-segment round buffers and simplified to the snap grid (#2114
round 2 P5: the 16-segment buffers put 35,536 ring nodes on KBNA's lots).

A CAR LOT IS A LAST-STAGE CELL (#2114 round 2 P1): absent from the base
map and the base solve (``pipeline/stage_one_map.gap_free``), cut against
the solved map's faces — the adjacent-ground bands included, which are
planar faces and no cell (P4, :func:`cut_car_lots`) — and solved alone
against them (``pipeline/late_stage``, ``constraints/car_lot_follow``).
MEASURED (round 1, the lot in the one map and the one solve): stood off,
229 standing nodes still moved > 0.1 m — a pad 0.33 m, a zone band 0.40 m,
road ends 4.6 m through the §37 (10) reach contact — and the owner's two
lots stood 1.9 / 2.9 m over the lidar, bound to their pad by §28.

The counted cars' anchors ride on the cell (:data:`ANCHORS_KEY`): the
lot's own ground is the DEM where its cars stand (P3).

Read once, after every other cell is minted (``classify/roles``)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..airport.facade import is_parked_car
from ..law import Law
from ..law.tables import LOT_ROLES, gap_standoff_m, road_family_roles
from ..model.planar import CAR_LOT_PREFIX
from .edge_line_mint import standing_keep_off
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["mint_car_lots", "cut_car_lots", "car_anchors", "LOT_ROLE", "CARS_KEY",
           "ANCHORS_KEY"]

LOT_ROLE = "parking_lot"
#: the cell evidence: how many counted cars stand in the lot
CARS_KEY = "car_lot_cars"
#: the cell evidence: the counted cars' anchors ``((x, y), ...)``, frame metres
ANCHORS_KEY = "car_lot_anchors"
#: round 2 P5: a car's ground grows with this many segments per quarter turn
_QUAD_SEGS = 2


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
    links = np.array([(free[i], free[j]) for i, j in pairs if i in keep],
                     dtype=float).reshape(-1, 2, 2)
    reach = cfg.car_half_m + cfg.margin_m
    # each car and each link buffered ALONE, then one union (#2206): one
    # buffer of the whole link set threw in GEOS's full-precision pass and
    # fell back to snap-rounding (MEASURED KATL, 21,019 links: 85 s -> 0.7 s;
    # the core moves < 1e-6 m, the simplified lot outline up to 0.8 m)
    core = shapely.union_all(np.concatenate([
        shapely.buffer(shapely.points(free[counted]), reach,
                       quad_segs=_QUAD_SEGS),
        shapely.buffer(shapely.linestrings(links), reach, quad_segs=_QUAD_SEGS)
        if len(links) else np.empty(0, dtype=object)]))
    # ground a group's cars ENCLOSE is the lot's (the aisle inside a ring)
    core = unary_union([Polygon(p.exterior) for p in polygon_parts(core)])
    # every PAD's set-back stands (the §52 facade lot's knife): a lot sharing a
    # pad's rim puts the pad's columns in the lot's rows, and the pad and the
    # apron it stands on move (MEASURED KBNA replay, welded by the touch
    # witness: 123 pad nodes up to 1.28 m, apron nodes 0.46 m)
    held = unary_union([standing_keep_off(cells, law), _structures(airport)])
    out = []
    for part, cars in _car_parts(core.difference(held), free[counted], rules, law, held):
        out.append((part, cars))
        stats["car_lots"] += 1
        stats["car_lot_m2"] += part.area
    return out, stats


def _car_parts(ground, cars: np.ndarray, rules: Rules, law: Law, held=None
               ) -> list[tuple[Polygon, np.ndarray]]:
    """The parts of ``ground`` that hold a car of ``cars`` and are at least
    ``cells.min_area_m2``, each with the cars in it, in a stable order.
    P5: the outline is simplified within the identity spacing (two emitted
    vertices are never closer: MEASURED KBNA, half of the lots' ring edges
    were under 1 m, 18,441 nodes -> 5,423 at this tolerance), cut by
    ``held`` again so the simplification never takes back the stand-off,
    and put on the snap grid."""
    grid = rules.cells.snap_grid_m
    ground = shapely.simplify(ground, float(law.tables.emit.identity.min_distinct_spacing_m))
    if held is not None and not held.is_empty:
        ground = ground.difference(held)
    ground = shapely.set_precision(ground, grid)
    pts = shapely.points(cars)
    out = []
    for part in sorted(polygon_parts(ground),
                       key=lambda q: (round(q.bounds[1]), round(q.bounds[0]))):
        inside = shapely.contains(part, pts)
        if inside.any() and part.area >= rules.cells.min_area_m2:
            out.append((part, cars[inside]))
    return out


def _evidence(cars: np.ndarray) -> dict:
    return {CARS_KEY: len(cars),
            ANCHORS_KEY: tuple((round(float(x), 2), round(float(y), 2)) for x, y in cars)}


def car_anchors(cell) -> np.ndarray:
    """The counted cars' anchors a car-lot cell carries, ``(n, 2)``."""
    got = (getattr(cell, "evidence", None) or {}).get(ANCHORS_KEY, ())
    return np.array(got, dtype=float).reshape(-1, 2)


def mint_car_lots(airport, cells: list, law: Law, rules: Rules, add) -> dict[str, float]:
    """Mint the car lots onto ``cells`` through ``add`` (the classifier's
    own cell constructor); returns the counts."""
    plan, stats = _lot_plan(airport, cells, law, rules)
    for k, (part, cars) in enumerate(plan):
        add(LOT_ROLE, f"{CAR_LOT_PREFIX}:{k}", part, "parking_lot", None, None,
            _evidence(cars))
    return stats


def _face_polygons(pm) -> list[Polygon]:
    """Every face of the map ``pm`` as a polygon (frame metres)."""
    from ..model.planar import face_cycles
    V, out = pm.vertices, []
    for f in sorted(pm.faces):
        ring, *holes = ([V[v].xy for v in cyc] for cyc in face_cycles(pm, pm.faces[f]))
        out.append(Polygon(ring, holes).buffer(0.0))
    return out


def cut_car_lots(lots: _t.Sequence, pm, law: Law, rules: Rules,
                 extra: _t.Sequence = ()) -> tuple[list, dict]:
    """#2114 round 2 P4/P5: each car-lot cell of ``lots`` CUT against every
    face of the solved map ``pm`` grown by the §52 stand-off — the
    adjacent-ground bands are faces of the map and no cell, so the mint's
    own stand-off could not see them (round 1: a band 0.5 m from
    ``carlot:225`` moved 0.40 m) — and the parts that keep a counted car
    and ``cells.min_area_m2`` after this LAST cut (round 1 emitted a lot way
    of area 0).  A lot cut in two is ``<ref>/<n>``.  ``extra``: polygons
    standing beside ``pm``'s faces (#2206: the gap parts and pad roads the
    one late map carries, cut before it is built).  ``(cells, report)``."""
    from shapely.strtree import STRtree
    rep = {"lots_in": len(lots), "lots_out": 0, "dropped": 0, "split": 0,
           "m2_in": 0.0, "m2_out": 0.0}
    if not lots:
        return [], rep
    faces = [*_face_polygons(pm), *(p for p in extra if p is not None and not p.is_empty)]
    tree = STRtree(faces)
    grow = gap_standoff_m(law)
    out = []
    for c in lots:
        lot = Polygon(c.ring, c.holes).buffer(0.0)
        rep["m2_in"] += lot.area
        near = tree.query(lot, predicate="dwithin", distance=grow)
        held = unary_union([faces[i] for i in near.tolist()]) if len(near) else Polygon()
        if not held.is_empty:
            held = held.buffer(grow, join_style="mitre", mitre_limit=2.0)
        parts = _car_parts(lot.difference(held), car_anchors(c), rules, law, held)
        rep["dropped"] += not parts
        rep["split"] += len(parts) > 1
        for n, (part, cars) in enumerate(parts):
            ref = c.ref if len(parts) == 1 else f"{c.ref}/{n}"
            out.append(_dc.replace(c, ref=ref, ring=tuple(part.exterior.coords)[:-1],
                                   holes=tuple(tuple(h.coords)[:-1] for h in part.interiors),
                                   evidence={**dict(c.evidence), **_evidence(cars)}))
            rep["m2_out"] += part.area
    rep["lots_out"] = len(out)
    rep["m2_in"], rep["m2_out"] = round(rep["m2_in"], 1), round(rep["m2_out"], 1)
    return out, rep
