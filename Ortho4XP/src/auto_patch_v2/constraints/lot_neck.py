"""THE ROAD LEAVING A LOT CLIMBS WITH ITS GROUND (owner RULINGS 2026-11-25e
(2), #2283 EKVG: "we are not recognizing the neck I guess which would allow
it to climb more there") -- an assembly post-pass (``constraints/assembly``).

THE NECK.  Where a lot narrows to a road's width the pavement from there on
is a ROAD, not the lot: the §43 reading at the road's width over each
connected body of parking lots (``classify/neck.road_necks``: narrower than
the free-road width, a neck or an arm at least a neck long, its mean width
under anything a vehicle parks across).  MEASURED EKVG ``pav0#beyond1`` +
``dsf:pol17``: one 6.6 m x 662 m lane round the lot and up the north arm to
the primary road, every one of its rows a lot row at 5 %.

THE ROAD LAW FROM THE NECK ON (owner RULINGS 2026-11-25c: "Any section of
road should still be held to 2% laterally"; 2026-11-17 #2122 the steep
cap).  A grade row (a ``Diff``) between two vertices of one road is priced
as the road's BOX in its own LOCAL frame (the medial-axis direction nearest
the pair's midpoint, ``geom/centreline.medial_directions``: a ring road and
the arm leaving it branch):

    bound = g x |ds| + transverse x |dt|

``g`` the road cap ``[common] road_max_grade``, rising with the ground
under the pair to at most ``tables.road_terrain_cap``; ``transverse`` the
lot's own cross-fall cap (``rulesets.toml``: the road law's lateral 2 %).
A row from a road vertex to the rest of the lot, and a row whose chord runs
over the road between two of the lot's lobes, is widened to ``g`` over its
chord: the lot's law holds the lot, the road's the road.  Only the lot's
own within-shape rows are ever TIGHTENED (to the road's cross-fall); the
5 % ceiling's twin and the road-cap fallback only widen, as every release
does (``constraints/public_road_release``).

THE VERTICES are the lot's own (``model/lot_ground.lot_datum_vertices``:
carried by no other face, no level target) and never airside: a row with a
stage-1 foot is the airside's and is not touched.  They carry the lot's
weak DEM row (``solve/design_assemble`` 9'), so the road follows its ground
under its own law."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

from ..classify.evidence import polygon_parts
from ..classify.neck import road_necks
from ..classify.rules import load_rules
from ..geom.centreline import medial_directions
from ..law import Law
from ..law.tables import road_terrain_cap, role_cap
from ..model.constraints import Diff, Row
from ..model.lot_ground import LOT_DATUM_ROLE, is_datum_lot, lot_datum_vertices
from ..model.planar import PlanarMap, face_vertex_set
from . import roads
from .roads import stage_one_vertices

__all__ = ["neck_pair_bounds", "neck_release"]

#: the widened bound stands this far (relative) over the ground's own
#: difference, so the ground is strictly inside it (the public road's slack)
_SLACK = 1e-3

_Axis = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


@_dc.dataclass(frozen=True)
class _LotRoad:
    """One road a lot narrows into: its pavement, its own vertices and the
    local directions of its medial axis."""

    polygon: _t.Any
    vertices: frozenset[int]
    axes: tuple[_Axis, ...]
    tree: _t.Any = _dc.field(default=None, compare=False, repr=False)

    def direction(self, x: float, y: float) -> tuple[float, float] | None:
        """The road's unit direction nearest ``(x, y)``, or ``None``."""
        if self.tree is None:
            return None
        return self.axes[int(self.tree.nearest(Point(x, y)))][2]


def _lot_roads(planar: PlanarMap, law: Law) -> list[_LotRoad]:
    """Every road a lot of ``planar`` narrows into (module docstring)."""
    own = lot_datum_vertices(planar) - stage_one_vertices(planar, law)
    if not own:
        return []
    lots = [_polygon(planar, f) for f in planar.faces.values() if is_datum_lot(f)]
    rules = load_rules()
    tol = rules.cells.on_tol_m
    out: list[_LotRoad] = []
    for body in polygon_parts(unary_union(lots)):
        for neck in road_necks(body, rules):
            near = prep(neck.polygon.buffer(tol))
            vs = frozenset(v for v in own if near.contains(Point(planar.vertices[v].xy)))
            if not vs:
                continue
            axes = tuple(a for part in polygon_parts(neck.polygon)
                         for a in medial_directions(part))
            tree = STRtree([LineString([a, b]) for a, b, _u in axes]) if axes else None
            out.append(_LotRoad(neck.polygon, vs, axes, tree))
    return out


def _polygon(planar: PlanarMap, face: _t.Any) -> _t.Any:
    """``face`` as a valid shapely polygon (frame metres)."""
    def xy(ring):
        return [planar.vertices[v].xy for v in planar.ring_vertices(ring)]
    return Polygon(xy(face.ring), [xy(h) for h in face.holes]).buffer(0)


@_dc.dataclass(frozen=True)
class _LotNecks:
    """THE ONE READING of the roads the lots narrow into: which pair of
    vertices the road law prices, and at what bound.  The follower pass's
    rows (:func:`neck_release`) and the published pairs the in-build verify
    and the census price (:func:`neck_pair_bounds`) both read it, so the
    instrument and the solve cannot drift."""

    roads: tuple[_LotRoad, ...]
    road_of: _t.Mapping[int, int]
    lot_v: frozenset[int]
    air: frozenset[int]
    core: _t.Any
    caps: "_Caps"

    def bound(self, planar: PlanarMap, a: int, b: int, d: float
              ) -> tuple[float, bool] | None:
        """``(bound metres, box)`` the road law gives the pair ``a``-``b``
        ``d`` metres apart, or ``None`` where it is the lot's (or the
        airside's).  ``box``: both on one road, priced as its box (may
        tighten the lot's cap); otherwise the road's grade over the chord
        (only ever widens)."""
        if d <= 0.0 or a in self.air or b in self.air:
            return None
        ka, kb = self.road_of.get(a), self.road_of.get(b)
        if ka is not None and ka == kb:
            return self.caps.box(planar, a, b, d, self.roads[ka]), True
        if ka is not None or kb is not None or (
                a in self.lot_v and b in self.lot_v and _crosses(planar, a, b, self.core)):
            return self.caps.grade(planar, a, b, d) * d, False
        return None


def _lot_necks(planar: PlanarMap, law: Law) -> _LotNecks | None:
    """The :class:`_LotNecks` of ``planar``, or ``None`` where no lot
    narrows into a road."""
    found = _lot_roads(planar, law)
    if not found:
        return None
    lot_v = frozenset(v for f in planar.faces.values() if is_datum_lot(f)
                      for v in face_vertex_set(planar, f))
    core = prep(unary_union([r.polygon for r in found]).buffer(-load_rules().cells.on_tol_m))
    return _LotNecks(tuple(found), {v: k for k, r in enumerate(found) for v in r.vertices},
                    lot_v, frozenset(stage_one_vertices(planar, law)), core, _Caps(law))


def neck_release(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                 ) -> tuple[list[Row], int]:
    """``(rows, repriced)``: ``rows`` with every grade row of a lot's road
    priced under the road law (module docstring)."""
    necks = _lot_necks(planar, law)
    if necks is None:
        return list(rows), 0
    out: list[Row] = []
    n = 0
    for row in rows:
        new = row
        if isinstance(row, Diff):
            got = necks.bound(planar, row.a, row.b, row.d)
            if got is not None:
                bound, box = got
                new = _priced(row, bound / row.d,
                              tighten=box and row.source.generator == roads.GEN)
        n += new is not row
        out.append(new)
    return out, n


def neck_pair_bounds(planar: PlanarMap, law: Law) -> list[list[_t.Any]]:
    """THE PUBLISHED NECK PAIRS (sidecar ``lot_neck_pairs``): ``[[lat, lon],
    [lat, lon], bound m]`` for every pair of a lot face's own vertices the
    road law prices (:meth:`_LotNecks.bound`) -- LAW INPUT for the in-build
    verify (``verify/within``) and the census (``within_shape``), which
    price a lot pair there at this bound instead of the lot's chord cap.
    Empty where no lot narrows into a road."""
    necks = _lot_necks(planar, law)
    if necks is None:
        return []
    out: list[list[_t.Any]] = []
    for f in planar.faces.values():
        if not is_datum_lot(f):
            continue
        vs = sorted(face_vertex_set(planar, f))
        # a lot with no road vertex still has its chords over a road
        # repriced (``bound``'s crossing branch; MEASURED ESSA ``faclot:1``:
        # 3 chords at 5.07-5.09 % the release allowed, unpublished)
        if not any(v in necks.road_of for v in vs) and not necks.core.intersects(
                _polygon(planar, f)):
            continue
        for i, a in enumerate(vs):
            pa = planar.vertices[a]
            for b in vs[i + 1:]:
                pb = planar.vertices[b]
                d = ((pa.xy[0] - pb.xy[0]) ** 2 + (pa.xy[1] - pb.xy[1]) ** 2) ** 0.5
                got = necks.bound(planar, a, b, d)
                if got is not None:
                    out.append([[pa.key[0], pa.key[1]], [pb.key[0], pb.key[1]],
                                round(got[0], 4)])
    return out


class _Caps:
    """The road law's numbers, read once."""

    def __init__(self, law: Law) -> None:
        self.road = float(law.tables.common.road_max_grade)
        self.steep = max(self.road, float(road_terrain_cap(law)))
        cap = role_cap(law, LOT_DATUM_ROLE)
        self.transverse = float(cap.transverse) if cap is not None else 0.0

    def grade(self, planar: PlanarMap, a: int, b: int, run: float) -> float:
        """The road's longitudinal cap over ``run`` metres of the pair: the
        road cap, rising with the ground's own difference to the steep cap."""
        za, zb = planar.vertices[a].dem_z, planar.vertices[b].dem_z
        if za is None or zb is None or run <= 0.0:
            return self.road
        g = abs(float(za) - float(zb)) * (1.0 + _SLACK) / run
        return min(self.steep, max(self.road, g))

    def box(self, planar: PlanarMap, a: int, b: int, d: float, road: _LotRoad) -> float:
        """The pair's bound in metres: ``g x |ds| + transverse x |dt|`` in
        the road's local frame at the pair's midpoint."""
        (ax, ay), (bx, by) = planar.vertices[a].xy, planar.vertices[b].xy
        dx, dy = ax - bx, ay - by
        u = road.direction(0.5 * (ax + bx), 0.5 * (ay + by))
        if u is None:
            return self.grade(planar, a, b, d) * d
        ds = abs(dx * u[0] + dy * u[1])
        dt = abs(dy * u[0] - dx * u[1])
        return self.grade(planar, a, b, ds) * ds + self.transverse * dt


def _crosses(planar: PlanarMap, a: int, b: int, core: _t.Any) -> bool:
    """The pair's chord runs over a lot's road (``core``: the roads less
    their edge, so a chord ending on a road's kerb does not cross it)."""
    return core.intersects(LineString([planar.vertices[a].xy, planar.vertices[b].xy]))


def _priced(row: Diff, cap: float, *, tighten: bool) -> Diff:
    """``row`` at ``cap`` -- never under its own cap unless ``tighten``."""
    if cap == row.cap or (cap < row.cap and not tighten):
        return row
    ceil = row.ceiling if row.ceiling is None else max(row.ceiling, cap)
    return _dc.replace(row, cap=cap, ceiling=ceil)
