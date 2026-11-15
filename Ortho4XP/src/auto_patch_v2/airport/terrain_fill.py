"""THE GROUND IS FILLED UP TO A TERRAIN COMPOSITE (issue #2077 rule B, owner
2026-11-15T05:46Z: "where our ground stands below such a composite, fill the
ground up to it instead of sinking the composite to its lowest rim").

A terrain model is seated at its rigid fit to the ground
(``terrain_model.fit_seat``) and a relief skin at its origin's ground
(``relief_skin``); over a coarse DEM parts of their outer rim then stand over
our ground.  The tile build raises the ground to them, and conforms the
ground under a relief skin's town to its frame zero.  Pure numpy / scipy /
shapely on one raster: the glue that reads the plans and writes the
``.alt`` is ``auto_patch/terrain_cut_stage`` (step 1 and the mesh step's
refinement re-bake), which runs ALL CUTS (``airport/terrain_cut``), then the
PLANES, then the RIM FILLS.

THE RIM FILL (:func:`rim_fill`, a record whose ``cut`` carries ``"fill":
true``).  SUPPORTS: the outer-rim cells (``terrain_model.outer_rim``) whose
bottom ``z0 + bot`` stands over the raster ground, at ``z0 + bot - UNDER_M``.
Each posting within :data:`REACH_M` of a support is raised to

    max over supports of (z_s - max(0, d - W))

``d`` its distance to the support, ``W`` the SHOULDER (:func:`shoulder_m`:
:data:`SHOULDER_POSTS` posting diagonals, 15.5 m at LOWS): a flat shoulder
where the mesher's triangles may reach, then a 1:1 talus.  Only raised;
inside the plan never above the cut's bound (``terrain_cut``: the ground
stays under the object's surface).

THE PLANE (:func:`conform_plane`, a relief skin's ``cut["plane"]``): the
zero footprint (``relief_skin.zero_footprint``) is the ground at the frame
zero less ``UNDER_M``; every posting within :data:`REACH_M` of it is clipped
to ``[z - r, z + r]``, ``r = max(0, d - W)`` -- filled and cut, so the
walls stand on it and no street is pierced.  Inside a terrain member's plan
never above its cut bound.

NEVER CHANGED (both): postings within ``edge_posts`` of the tile's edge (the
neighbour's raster is not filled), postings inside an airport patch's
boundary (airside is king: the patch's own nodes carry its ground).  A RIM
FILL never raises a posting within ``W`` of ANOTHER composite's zero
footprint or terrain-member plan (that composite owns the ground: floors
win) -- LOWS's Festungsberg rim on its NW cut edge meets the old town's
cliff, which closes it; filled there it would raise 278 postings by up to
33.9 m against the town.  A support left more than :data:`SERVED_M` under
its bottom is UNSERVED, counted on the log line.

THE CONSUMER CENSUS (RULINGS 2026-08-30l) is the spec's table
(``docs/specs/2077-terrain-composites-spec.md`` 2): Triangle4XP reads the
filled raster; the plan-edge and footprint-edge rings are DUMMY constrained
lines; ``ProductionDem`` (the seat, the match, ``anchor_z``) reads the
corpus, never this raster; water vertices keep their datum; the object
stage reads the built mesh; the refinement re-bake re-applies all three.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..geom.terrain_deck import UNDER_M

__all__ = ["REACH_M", "SHOULDER_POSTS", "SERVED_M", "Raster", "shoulder_m",
           "posting_shoulder_m", "rim_fill", "conform_plane", "Owned"]

#: the reach of a fill or a plane from its supports (m)
REACH_M = 60.0
#: the shoulder, in posting diagonals (module doc)
SHOULDER_POSTS = 1.25
#: a support whose ground stays more than this under its bottom is unserved
SERVED_M = 0.5
_M_PER_DEG = 111_320.0


@_dc.dataclass
class Raster:
    """One elevation raster: ``alt[row, col]`` (changed in place), posting
    ``(row, col)`` at ``lon0 + col * dlon``, ``lat0 - row * dlat``
    (absolute degrees), and ``frozen(rows, cols, lons, lats)`` True at the
    postings never changed (the tile edge, an airport patch) or ``None``."""

    alt: np.ndarray
    lon0: float
    lat0: float
    dlon: float
    dlat: float
    frozen: "_t.Callable | None" = None

    def shoulder_m(self) -> float:
        """:func:`shoulder_m` of this raster's posting."""
        lat = self.lat0 - 0.5 * self.dlat * (self.alt.shape[0] - 1)
        return shoulder_m(self.dlon * _M_PER_DEG * math.cos(math.radians(lat)),
                          self.dlat * _M_PER_DEG)

    def window(self, w: float, s: float, e: float, n: float
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """``(rows, cols, lons, lats)`` of the free postings inside a
        degree box (flat arrays)."""
        ny, nx = self.alt.shape
        c0 = max(0, int(math.ceil((w - self.lon0) / self.dlon)))
        c1 = min(nx - 1, int(math.floor((e - self.lon0) / self.dlon)))
        r0 = max(0, int(math.ceil((self.lat0 - n) / self.dlat)))
        r1 = min(ny - 1, int(math.floor((self.lat0 - s) / self.dlat)))
        if c1 < c0 or r1 < r0:
            z = np.zeros(0, np.int64)
            return z, z, z.astype(float), z.astype(float)
        cols, rows = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
        rows, cols = rows.ravel(), cols.ravel()
        lons, lats = self.lon0 + cols * self.dlon, self.lat0 - rows * self.dlat
        if self.frozen is not None:
            keep = ~np.asarray(self.frozen(rows, cols, lons, lats), bool)
            rows, cols, lons, lats = rows[keep], cols[keep], lons[keep], lats[keep]
        return rows, cols, lons, lats

    def sample(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        """The bilinear raster at absolute ``(lons, lats)`` (``nan`` off it)."""
        ny, nx = self.alt.shape
        fx = (np.asarray(lons, float) - self.lon0) / self.dlon
        fy = (self.lat0 - np.asarray(lats, float)) / self.dlat
        ok = (fx >= 0) & (fy >= 0) & (fx <= nx - 1) & (fy <= ny - 1)
        out = np.full(fx.shape, np.nan)
        i = np.clip(np.floor(fx[ok]).astype(np.int64), 0, nx - 2)
        j = np.clip(np.floor(fy[ok]).astype(np.int64), 0, ny - 2)
        a, b = fx[ok] - i, fy[ok] - j
        z = self.alt
        out[ok] = (z[j, i] * (1 - a) * (1 - b) + z[j, i + 1] * a * (1 - b)
                   + z[j + 1, i] * (1 - a) * b + z[j + 1, i + 1] * a * b)
        return out


def shoulder_m(dx_m: float, dy_m: float) -> float:
    """THE SHOULDER ``W``: :data:`SHOULDER_POSTS` posting diagonals (m)."""
    return SHOULDER_POSTS * math.hypot(float(dx_m), float(dy_m))


def posting_shoulder_m(posting_m: "float | None", lat: float) -> float:
    """``W`` of a square-degree raster whose smaller posting (its east
    step) is ``posting_m`` at latitude ``lat`` (``ProductionDem.
    posting_m``); 0 without one."""
    if not posting_m:
        return 0.0
    c = max(math.cos(math.radians(lat)), 1e-6)
    return shoulder_m(posting_m, posting_m / c)


@_dc.dataclass(frozen=True)
class Owned:
    """The ground another composite owns, in lon/lat: its terrain-member
    plans' and zero footprints' rings (a rim fill stays ``W`` clear)."""

    rings: tuple = ()


def _polygon(rings_xy: _t.Sequence[np.ndarray]) -> _t.Any:
    """One shapely region of ``(k, 2)`` rings (outer rings and holes, by
    containment: even-odd)."""
    import shapely
    from shapely.geometry import Polygon
    polys = [Polygon(r) for r in rings_xy if len(r) >= 4]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    if not polys:
        return None
    region = polys[0]
    for p in polys[1:]:
        region = region.symmetric_difference(p)
    return shapely.make_valid(region)


def _distance(region: _t.Any, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Distance (m) of points to a shapely region, 0 inside; ``inf``
    without one."""
    import shapely
    if region is None or region.is_empty:
        return np.full(len(x), np.inf)
    return shapely.distance(region, shapely.points(np.c_[x, y]))


def _owned_mask(owned: _t.Iterable[Owned], to_xy: _t.Callable, x: np.ndarray,
                y: np.ndarray, w: float) -> np.ndarray:
    """Postings (frame ``x, y``) within ``w`` of another composite's ground."""
    near = np.zeros(len(x), bool)
    for o in owned:
        rings = [np.c_[to_xy(r[:, 0], r[:, 1])] for r in (np.asarray(q, float)
                                                           for q in o.rings) if len(r) >= 4]
        if rings:
            near |= _distance(_polygon(rings), x, y) <= w
    return near


def conform_plane(raster: Raster, to_xy: _t.Callable, rings_ll: _t.Sequence,
                  z: float, cap: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                  box: tuple[float, float, float, float]) -> int:
    """THE PLANE (module doc) on ``raster``: ``rings_ll`` the zero
    footprint's ``(lon, lat)`` rings, ``z`` its height, ``to_xy`` the
    composite's projector, ``cap(lons, lats)`` the cut bound at postings
    (``inf`` off every terrain member's plan), ``box`` the footprint's
    degree box grown by :data:`REACH_M`.  The postings changed."""
    rows, cols, lons, lats = raster.window(*box)
    if not len(rows):
        return 0
    x, y = to_xy(lons, lats)
    region = _polygon([np.c_[to_xy(r[:, 0], r[:, 1])]
                       for r in (np.asarray(q, float) for q in rings_ll) if len(r) >= 4])
    d = _distance(region, x, y)
    near = d <= REACH_M
    if not near.any():
        return 0
    rows, cols, lons, lats, d = rows[near], cols[near], lons[near], lats[near], d[near]
    r = np.maximum(0.0, d - raster.shoulder_m())
    old = raster.alt[rows, cols].astype(float)
    new = np.minimum(np.clip(old, z - r, z + r), np.maximum(old, cap(lons, lats)))
    moved = np.abs(new - old) > 1e-6
    raster.alt[rows[moved], cols[moved]] = new[moved]
    return int(moved.sum())


def rim_fill(raster: Raster, to_xy: _t.Callable, to_ll: _t.Callable,
             support_xy: np.ndarray, support_z: np.ndarray,
             cap: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
             owned: _t.Iterable[Owned] = ()) -> dict[str, int]:
    """THE RIM FILL (module doc) on ``raster``: ``support_xy`` / ``support_z``
    every outer-rim cell's frame point and bottom less ``UNDER_M`` (the
    supports are those standing over the raster), ``to_xy`` / ``to_ll`` the
    composite's projector, ``cap(lons, lats)`` its cut bound at postings
    (``inf`` off its plan), ``owned`` the other composites' ground.
    ``{"supports", "raised", "unserved"}``."""
    from scipy.spatial import cKDTree
    rep = {"supports": 0, "raised": 0, "unserved": 0}
    if not len(support_xy):
        return rep
    slon, slat = to_ll(support_xy[:, 0], support_xy[:, 1])
    over = np.asarray(support_z) > raster.sample(slon, slat)
    sxy, sz = support_xy[over], np.asarray(support_z, float)[over]
    rep["supports"] = int(len(sz))
    if not len(sz):
        return rep
    w = raster.shoulder_m()
    lo, la = to_ll(np.r_[sxy[:, 0].min() - REACH_M, sxy[:, 0].max() + REACH_M],
                   np.r_[sxy[:, 1].min() - REACH_M, sxy[:, 1].max() + REACH_M])
    rows, cols, lons, lats = raster.window(float(lo.min()), float(la.min()),
                                           float(lo.max()), float(la.max()))
    if len(rows):
        x, y = to_xy(lons, lats)
        pairs = cKDTree(np.c_[x, y]).sparse_distance_matrix(
            cKDTree(sxy), REACH_M, output_type="coo_matrix")
        lift = np.full(len(rows), -np.inf)
        np.maximum.at(lift, pairs.row, sz[pairs.col] - np.maximum(0.0, pairs.data - w))
        # a support at distance 0 is not a stored entry of the sparse matrix
        d0, k0 = cKDTree(sxy).query(np.c_[x, y], distance_upper_bound=1e-9)
        hit = np.isfinite(d0)
        lift[hit] = np.maximum(lift[hit], sz[k0[hit]])
        free = ~_owned_mask(owned, to_xy, x, y, w)
        old = raster.alt[rows, cols].astype(float)
        new = np.where(free, np.maximum(old, np.minimum(lift, cap(lons, lats))), old)
        up = new > old + 1e-6
        raster.alt[rows[up], cols[up]] = new[up]
        rep["raised"] = int(up.sum())
    after = raster.sample(*to_ll(sxy[:, 0], sxy[:, 1]))
    rep["unserved"] = int(np.sum(~(after >= sz + UNDER_M - SERVED_M)))
    return rep
