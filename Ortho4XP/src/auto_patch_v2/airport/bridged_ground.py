"""A GROUND OBJECT IN THE WATER IS SEATED ON ITS BRIDGES' FAR ENDS (issue
#2053; owner RULINGS 2026-11-13i "we don't want any visible edge to be
floating").

A pack may model an ISLAND (a pier, a landfill) as one object: its ground,
its plinths, a skirt into the sea, and the road bridges that join it to the
shore, all in one frame.  Read like a building -- split, anchored on the
median ground of its footprint unit -- it stands where the island's own
ground puts it, and the bridges' far ends float over the shore road.  SBRJ's
``ILHAS/ColegioNaval/colegioNavalBase.obj`` (the naval school island beside
the runway, two road bridges to the mainland) was seated on the §16g unit's
median ground +0.90 m: both bridges' mainland ends stood 2.4-2.6 m over the
drawn shore (owner sim read 2026-11-13T15:06Z).

THE WITNESS (geometry, the DEM's water and the map only -- RULINGS 05e):

* PLAN -- its static solid spans at least :data:`MIN_PLAN_M` on its longer
  plan side (an island, not a bridge);
* IN THE WATER -- at least :data:`MIN_RIM_WATER` of the ring
  :data:`RING_M` wide outside its plan's outer edge lies over water: the object
  stands apart from the ground its bridges reach (a terminal with a viaduct
  stands on land, and its seat is §16g's and the deck law's);
* ARMS -- a mapped bridge (``deck_signature.is_bridge_way``, the one
  predicate) along which the object's own surface RUNS ON past one end of
  the way, into its body, for :data:`CONTINUE_M`, and STOPS within
  :data:`EXTEND_M` of the other end, the ground just beyond on land (not
  water): that stop is an ARM'S FAR END, where the deck meets the shore.

THE SEAT -- no visible edge floats: the object's ``y = 0`` plane is set at

    z0 = min over its arms' far ends of (ground - deck top)

``ground`` the DEM :data:`PROBE_M` beyond the end along the way, ``deck top``
the object's highest surface over the last :data:`TOP_SPAN_M` of the arm
(median).  Every far end then meets or sinks into the shore, none floats; the
spread of the per-end zeros is how far the other ends sink (logged).  The
object and every row sharing its origin are ONE rigid frame
(``terrain_model.set_members``) -- island and bridges move together -- and
take the terrain model's path from here (``terrain_model.TerrainModel``
with ``seat_by``): never split or re-anchored, written ``OBJECT_MSL`` at
``z0`` plus each row's lift (``terrain_model.seat_records``).

THE TRADE-OFF, AND ITS ANSWER: seated on its bridges the island's own top
lies under our ground where the DEM models the island higher than the pack
did (SBRJ, the owner's 1.0.50x mesh: 63 % of the island top under the drawn
ground at z0 -1.70).  The seat record carries ``cut`` like a terrain
model's, so the tile build cuts the ground under its plan to its surface
(owner RULINGS 2026-11-13k, ``auto_patch/terrain_cut_stage``), with the top
eroded over :data:`ERODE_M` only -- the island CARRIES riders (trees, cars,
lamps draped on the drawn ground), and the 30 m erosion a hill takes would
sink half of SBRJ's 180 more than 0.5 m under its top (5 m: 26) -- and to
its FLOOR per cell, the ground under a roof a storey or more over it,
never the roof (``terrain_cut`` THE FLOOR, #2053 round 2).  Never hideable.

The one-cell erosion alone does NOT keep the drawn ground under the object
(#2053 round 3): 13k's argument holds for triangles no wider than the
erosion, and the mesher draws a point from one triangle edge plus one
posting diagonal (about 30 + 15 m).  The guarantee comes from the MESH --
THE HOLD (``terrain_cut``): posting-sized triangles over the plan, every
free vertex lowered under the object's 1 m bound, and the patch under the
plan reading the cut ground (``object_ground``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M

__all__ = ["MIN_PLAN_M", "MIN_RIM_WATER", "EXTEND_M", "CONTINUE_M", "GAP_M",
           "PROBE_M", "TOP_SPAN_M", "STEP_M", "ERODE_M", "RING_M", "SEAT_BY",
           "mark", "log_line"]

#: the least longer plan side of the object's static solid (m)
MIN_PLAN_M = 100.0
#: the least share of the ring outside its edge over water
MIN_RIM_WATER = 0.5
#: the width of that ring (m)
RING_M = 10.0
#: how far past a way's end the object may carry its deck (m): a model's
#: abutment and the mapped end are drawn by different hands (SBRJ: 8 m
#: short of the map at one bridge, 7 m past it at the other)
EXTEND_M = 15.0
#: how far past the way's OTHER end the surface must run on (m): the arm
#: comes out of the object's body, it is no bridge of its own
CONTINUE_M = 10.0
#: an uncovered run this long ends the arm (m)
GAP_M = 3.0
#: the ground is read this far beyond the arm's end (m; ``drawn_site``'s
#: open-edge reading stands 1.5 m out too)
PROBE_M = 1.5
#: the deck top is the median over this last stretch of the arm (m)
TOP_SPAN_M = 1.0
#: the station step along a way (m)
STEP_M = 0.5
#: the cut's erosion for a ground object (module doc): one plan cell
ERODE_M = CELL_M
#: ``TerrainModel.seat_by`` of a seat made here
SEAT_BY = "bridge ends"


@_dc.dataclass(frozen=True)
class _ArmEnd:
    """One arm's far end: the way, where the deck stops (frame metres), the
    authored deck top there, the ground beyond it and the zero that puts
    the one on the other."""

    way: int
    xy: tuple[float, float]
    top_y: float
    ground: float

    @property
    def zero(self) -> float:
        return self.ground - self.top_y


def _static_tris(g: _t.Any) -> "np.ndarray | None":
    """``(n, 3, 3)`` authored points of the static solid, or ``None``."""
    tris = g.solid
    if g.animated.shape[0]:
        tris = tris[~g.animated]
    return g.vertices[tris] if tris.shape[0] else None


def _to_frame(x: np.ndarray, z: np.ndarray, xy: _t.Sequence[float],
              heading: float) -> tuple[np.ndarray, np.ndarray]:
    """Authored plan ``(x, z)`` -> frame ``(east, north)`` (the rotation
    ``terrain_model`` and ``pack_ground`` place by)."""
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    return xy[0] + x * c - z * s, xy[1] - (x * s + z * c)


def _to_authored(e: np.ndarray, n: np.ndarray, xy: _t.Sequence[float],
                 heading: float) -> tuple[np.ndarray, np.ndarray]:
    """The inverse of :func:`_to_frame`."""
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    de, dn = e - xy[0], n - xy[1]
    return de * c - dn * s, -de * s - dn * c


def _tops(tris: np.ndarray, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """The highest solid surface over each authored plan point (``nan``
    where none covers it)."""
    out = np.full(x.shape, np.nan)
    p0 = tris[:, 0]
    e1, e2 = tris[:, 1] - p0, tris[:, 2] - p0
    den = e1[:, 0] * e2[:, 2] - e2[:, 0] * e1[:, 2]
    live = np.abs(den) > 1e-9
    p0, e1, e2, den = p0[live], e1[live], e2[live], den[live]
    lo = tris[live].min(axis=1)
    hi = tris[live].max(axis=1)
    for k in range(x.shape[0]):
        px, pz = float(x[k]), float(z[k])
        m = (lo[:, 0] <= px) & (px <= hi[:, 0]) & (lo[:, 2] <= pz) & (pz <= hi[:, 2])
        if not m.any():
            continue
        qx, qz = px - p0[m, 0], pz - p0[m, 2]
        u = (qx * e2[m, 2] - e2[m, 0] * qz) / den[m]
        v = (e1[m, 0] * qz - qx * e1[m, 2]) / den[m]
        ins = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1.0 + 1e-6)
        if ins.any():
            y = p0[m, 1] + u * e1[m, 1] + v * e2[m, 1]
            out[k] = float(np.max(y[ins]))
    return out


def _stations(pts: np.ndarray, before: float, after: float
              ) -> tuple[np.ndarray, np.ndarray, float]:
    """Points every :data:`STEP_M` along the polyline ``pts`` (frame),
    extended ``before`` m behind its first point and ``after`` m past its
    last along the end segments: ``(points, s, length)`` with ``s`` metres
    from the first point."""
    seg = np.diff(pts, axis=0)
    ln = np.hypot(seg[:, 0], seg[:, 1])
    keep = ln > 1e-6
    pts = np.vstack([pts[:1], pts[1:][keep]])
    seg, ln = seg[keep], ln[keep]
    total = float(ln.sum())
    s = np.arange(-before, total + after + 1e-9, STEP_M)
    cum = np.concatenate([[0.0], np.cumsum(ln)])
    i = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(ln) - 1)
    t = (s - cum[i]) / ln[i]
    return pts[i] + seg[i] * t[:, None], s, total


def _far_end(cov: np.ndarray, s: np.ndarray, total: float) -> "int | None":
    """Index of the last covered station of an arm that runs from before
    the way's start (``s <= 0``, all covered) and stops within
    :data:`EXTEND_M` of its end, or ``None``."""
    back = s <= 0.0
    if not back.any() or not cov[back].all():
        return None
    gap = int(round(GAP_M / STEP_M))
    run = 0
    for k in np.flatnonzero(s > 0.0):
        if cov[k]:
            run = 0
            continue
        run += 1
        if run >= gap:
            e = int(k) - run
            return e if s[e] >= total - EXTEND_M else None
    return None


def _arm_ends(tris: np.ndarray, xy: _t.Sequence[float], heading: float,
             ways: _t.Sequence[tuple[int, _t.Any]],
             dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
             water_many: "_t.Callable[[np.ndarray, np.ndarray], np.ndarray] | None"
             ) -> list[_ArmEnd]:
    """Every ARM'S FAR END (module doc) of one placement of ``tris``
    (authored static solid) at ``xy`` / ``heading``, along the mapped
    bridges ``ways`` (``deck_signature.bridge_lines``, frame)."""
    lo, hi = tris.min(axis=(0, 1)), tris.max(axis=(0, 1))
    out: list[_ArmEnd] = []
    for wid, line in ways:
        pts = np.asarray(line.coords, dtype=float)[:, :2]
        if len(pts) < 2:
            continue
        ax, az = _to_authored(pts[:, 0], pts[:, 1], xy, heading)
        if (ax.max() < lo[0] - EXTEND_M or ax.min() > hi[0] + EXTEND_M
                or az.max() < lo[2] - EXTEND_M or az.min() > hi[2] + EXTEND_M):
            continue
        for p in (pts, pts[::-1]):
            st, s, total = _stations(p, CONTINUE_M, EXTEND_M + GAP_M + STEP_M)
            top = _tops(tris, *_to_authored(st[:, 0], st[:, 1], xy, heading))
            e = _far_end(np.isfinite(top), s, total)
            if e is None:
                continue
            span = (s >= s[e] - TOP_SPAN_M) & (s <= s[e]) & np.isfinite(top)
            d = st[min(e + 1, len(st) - 1)] - st[max(e - 1, 0)]
            probe = st[e] + d / max(float(np.hypot(*d)), 1e-9) * PROBE_M
            pe, pn = probe[:1], probe[1:]
            g = float(np.asarray(dem_many(pe, pn), dtype=float)[0])
            if not math.isfinite(g):
                continue
            if water_many is not None and bool(np.asarray(water_many(pe, pn))[0]):
                continue
            out.append(_ArmEnd(int(wid), (float(st[e][0]), float(st[e][1])),
                              float(np.median(top[span])), g))
    return out


def _rim_water_share(tris: np.ndarray, xy: _t.Sequence[float], heading: float,
                    water_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
                    ) -> float:
    """The share of the plan cells within :data:`RING_M` OUTSIDE the
    object's outer edge (its exterior, never a hole) that lie over water.
    Read outside, not on the edge cells: a skirt may stop at the shore on
    one side and run out into the sea on another (SBRJ: 34 % of the edge
    cells, 84 % of the ring outside them)."""
    from scipy import ndimage

    from .terrain_shaped import grid_of_triangles
    grid = grid_of_triangles(tris)
    k = max(1, int(round(RING_M / CELL_M)))
    cov = np.pad(grid.covered, k + 1, constant_values=False)
    lab, _n = ndimage.label(~cov)
    ring = ndimage.binary_dilation(cov, structure=np.ones((3, 3), dtype=bool),
                                   iterations=k) & (lab == lab[0, 0])
    ii, jj = np.nonzero(ring)
    if not len(ii):
        return 0.0
    e, n = _to_frame(grid.x0 + CELL_M * (ii - k - 1), grid.z0 + CELL_M * (jj - k - 1),
                     xy, heading)
    return float(np.mean(np.asarray(water_many(e, n), dtype=bool)))


def _candidate(o: _t.Any) -> bool:
    """A placement this module may read: pack-local, not an ``OBJECT_MSL``
    row (it states its datum), not already in another seat's frame."""
    from .obj8 import is_stock_library_resource
    return (o.resolved is not None and o.kind != "OBJECT_MSL"
            and not is_stock_library_resource(o.path)
            and getattr(o, "terrain_model", None) is None
            and getattr(o, "terrain_fit", None) is None
            and getattr(o, "walled_plate", None) is None
            and o.deck_kind not in ("flag", "signature"))


def _models(airport: _t.Any, objects: _t.Sequence[_t.Any], cache: _t.Any) -> dict:
    """``{placement id: TerrainModel}`` for every placement read here as a
    ground object on its bridges (module doc)."""
    from .deck_signature import bridge_lines
    from .terrain_model import TerrainModel
    from .terrain_shaped import dem_many_of
    ways = bridge_lines(getattr(airport, "osm_ways", ()) or ())
    water = getattr(airport.dem, "is_water_many", None)
    if not ways or water is None:
        return {}
    dem_many = dem_many_of(airport.dem)
    from ..law import Law
    from .airside_group_seat import storey_m
    storey = storey_m(Law.load())
    out = {}
    for o in objects:
        if not _candidate(o):
            continue
        g = cache.geometry(o.resolved)
        tris = None if g is None else _static_tris(g)
        if tris is None or float(np.ptp(tris[:, :, [0, 2]], axis=(0, 1)).max()) < MIN_PLAN_M:
            continue
        ends = _arm_ends(tris, o.xy, o.heading_deg, ways, dem_many, water)
        if not ends or _rim_water_share(tris, o.xy, o.heading_deg, water) < MIN_RIM_WATER:
            continue
        zeros = [a.zero for a in ends]
        out[str(o.id)] = TerrainModel(
            str(o.id), str(o.path), (float(o.xy[0]), float(o.xy[1])),
            float(o.heading_deg), float(min(zeros)), 0.0, 0.0, 0.0, 0.0, 0.0,
            file=str(o.resolved), seat_by=SEAT_BY, erode_m=ERODE_M, cut_floor_m=storey,
            spread_m=float(max(zeros) - min(zeros)))
    return out


def mark(airport: _t.Any, objects: _t.Sequence[_t.Any], cache: _t.Any) -> list:
    """``objects`` with every ground object seated on its bridges, and each
    row of its origin set, stamped as a terrain model's origin set is
    (``obj8.read_placed_objects``): ``terrain_model`` set, a terrain
    feature (never read), out of the deck verdict and the below-grade
    readings -- the 13i path carries it from here."""
    found = _models(airport, objects, cache)
    if not found:
        return list(objects)
    from .terrain_model import set_members
    rows = [(o.id, o.path, o.xy, o.heading_deg, o.agl_m, o.kind) for o in objects
            if o.kind != "OBJECT_MSL"]
    members = set_members(rows, found)
    return [o if str(o.id) not in members else _dc.replace(
        o, terrain_model=members[str(o.id)], terrain_feature=True, terrain_fit=None,
        origin_built=False, hard_deck=None, deck_top_z=None, deck_kind="",
        deck_evidence=(), deck_plate=None, below_grade=None, below_grade_comps=(),
        witnesses=(), buried=())
        for o in objects]


def log_line(icao: str, models: _t.Iterable[_t.Any]) -> str:
    """The build log's one line on the ground objects seated here."""
    got = sorted({m.id: m for m in models
                  if getattr(m, "seat_by", "") == SEAT_BY}.values(), key=lambda m: m.id)
    if not got:
        return f"[{icao}] ground objects on their bridges: none"
    return f"[{icao}] ground objects on their bridges: " + "; ".join(
        f"{m.path} ({m.id}) seated at {m.z0:.2f} m (its bridges' far ends meet the "
        f"shore; the other ends sink up to {m.spread_m:.2f} m), the ground under it "
        f"cut to it" for m in got)
