"""THE SKIRT SEAT OF A SMALL TERRAIN SHELL (#2272 round 3).

Owner, 2026-11-25T04:29:28Z: "The shells were designed to work with
default terrain I believe, so they should be able to be seated with their
"skirts" below grade to hide any gaps..."  Rounds 1 and 2 kept a shell at
its author's ``OBJECT_MSL`` datum and reshaped OUR ground to it (a cut, a
rim tuck, a feather, a hold); both failed the drawn check.  Here our ground
is never touched: the SHELL moves, as one rigid body, by one vertical
offset ``dz`` from the frame zero ``z0`` its record carries
(``terrain_model.seat_records``: the author's datum, capped over a wet rim).

THE STATIONS.  The shell's static solid placed at its anchor and heading
(``terrain_model.plan_solid``), rasterised in plan at :data:`CELL_M`
(``geom.shape_class.rasterise``: per cell its top and LOWEST surface);
every outline cell and its outward direction
(``shape_class.boundary_cells``).  At each station: the skirt's lowest
surface there, and OUR GROUND -- the drawn mesh the placement write seats
on -- ``shape_class.OUTSIDE_M`` outside it, where the drawn instrument
reads a rim (``tools/drawn_cover`` RIM: one station, two readers).  Not
read: a station whose ground is at or under the sea datum (RULINGS
2026-11-25a (3): a shell at the water's edge runs under the water; water is
a datum, 2026-09-09m), one inside another kept shell's plan (that shell
covers it), one off the mesh.

THE SEAT.  ``need_k = ground_k - (z0 + low_k)``: at or over 0 the skirt's
bottom stands at or under our ground there and no gap shows under the rim.
``dz`` is the value closest to 0 with every ``need_k - dz >= 0``, i.e.
``min(0, min_k need_k)``: a shell whose whole land rim already stands at or
under our ground keeps its author's height (``dz = 0``; with fine matching
elevation that is the rule, not the exception), and the seat never rises
-- the author's height is the most a gap-free seat needs.  Bounded by the
SKIRT'S DEPTH: the median, over the land stations, of the shell's rise from
the station to the nearest cell ``terrain_cut.BAND_M`` inside its edge
(the deepest cell of a smaller shell).  Where the largest gap is deeper
than that, ``dz`` is minus the depth -- the seat in range whose largest
gap is least -- and the shell is REPORTED with the gap left.  Every row of
the shell's set (``model``) moves by ``dz``.

THE BODY may then stand under our ground -- that is what the skirt is for;
how much of our ground pokes through it is measured on the built tile
(``tools/drawn_cover --judge inner``) and judged by the owner in the sim.

Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..geom import shape_class as _sc
from ..geom.water_level import SEA_LEVEL_M

__all__ = ["CELL_M", "WATER_TOL_M", "placed", "place", "stations", "seat_one", "edge_depth",
           "rim_need", "seat_shells", "shells_box", "log_line"]

#: the plan grid of the stations (``terrain_cut.HOLD_CELL_M``, the drawn
#: instrument's)
CELL_M = 1.0
#: ground this near the sea datum is the water's (the mesh is a datum at
#: 0.00 over water)
WATER_TOL_M = 0.01


@_dc.dataclass(frozen=True)
class _Placed:
    """One kept shell placed in its own frame (metres east / north of its
    anchor; ``raster`` heights over its frame zero ``z0``)."""

    model: str
    resource: str
    z0: float
    raster: _sc.Raster
    to_xy: _t.Callable
    to_ll: _t.Callable

    def top_at(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        """The shell's top over its frame zero at ``(lon, lat)`` (``nan``
        off its plan)."""
        x, y = self.to_xy(lons, lats)
        r = self.raster
        j = np.floor((np.asarray(x, float) - r.e0) / r.step).astype(int)
        i = np.floor((np.asarray(y, float) - r.n0) / r.step).astype(int)
        ok = (i >= 0) & (j >= 0) & (i < r.top.shape[0]) & (j < r.top.shape[1])
        out = np.full(len(i), np.nan)
        out[ok] = r.top[i[ok], j[ok]]
        return out

    def covers(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        """True where the shell's plan covers ``(lon, lat)``."""
        return np.isfinite(self.top_at(lons, lats))


def placed(rec: _t.Mapping[str, _t.Any]) -> "_Placed | None":
    """A shell's own seat record (``shell``: file, anchor, heading;
    ``elevation`` its frame zero) placed, or ``None`` where its file
    cannot be read."""
    from . import terrain_cut as _tc
    c = rec["shell"]
    return place(str(c["file"]), float(c["heading"]),
                 *_tc.projector(float(c["lat"]), float(c["lon"])),
                 str(rec.get("model") or rec.get("id")), str(rec.get("resource", "")),
                 float(rec["elevation"]))


def place(file: str, heading: float, to_xy: _t.Callable, to_ll: _t.Callable,
          model: str = "", resource: str = "", z0: float = 0.0) -> "_Placed | None":
    """The shell of OBJ8 ``file`` at ``heading`` placed in the frame of
    ``to_xy`` / ``to_ll`` (``(lon, lat) <-> (east, north)`` of its anchor),
    its frame zero ``z0``; ``None`` where the file cannot be read."""
    from . import terrain_model as _tm
    tris = _tm.plan_solid(file)
    if tris is None or not len(tris):
        return None
    h = math.radians(heading)
    s, co = math.sin(h), math.cos(h)
    x, y, z = tris[..., 0], tris[..., 1], tris[..., 2]
    p = np.stack([x * co - z * s, -(x * s + z * co), y], axis=-1)
    a, b = p[:, 1, :2] - p[:, 0, :2], p[:, 2, :2] - p[:, 0, :2]
    p = p[0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) > 1e-3]
    r = _sc.rasterise(p, max_cells=10 ** 9, min_step=CELL_M)
    if r is None:
        return None
    return _Placed(model, resource, float(z0), r, to_xy, to_ll)


def stations(pl: _Placed) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(ij, lons, lats, low)``: every outline cell of the shell, where
    its ground is read (``OUTSIDE_M`` outside it) and the skirt's lowest
    surface there (over the frame zero)."""
    r = pl.raster
    ij, dirs = _sc.boundary_cells(r)
    e, n = r.centres(ij)
    lons, lats = pl.to_ll(e + _sc.OUTSIDE_M * dirs[:, 0], n + _sc.OUTSIDE_M * dirs[:, 1])
    return ij, np.asarray(lons, float), np.asarray(lats, float), r.low[ij[:, 0], ij[:, 1]]


def edge_depth(r: _sc.Raster) -> np.ndarray:
    """Per cell of ``r`` its distance (m) in from the plan's outer edge
    (-1 where uncovered)."""
    from scipy import ndimage
    cov = np.isfinite(r.top)
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    return np.where(cov, ndimage.distance_transform_edt(~rim) * r.step, -1.0)


def _skirt_depth(pl: _Placed, ij: np.ndarray, low: np.ndarray) -> float:
    """THE SKIRT'S DEPTH (module doc) over the stations ``ij`` (their
    lowest surfaces ``low``; none: 0)."""
    if not len(ij):
        return 0.0
    from scipy.spatial import cKDTree

    from .terrain_cut import BAND_M
    r = pl.raster
    inside = edge_depth(r)
    deep = np.argwhere(inside >= min(BAND_M, float(inside.max())))
    _d, k = cKDTree(np.c_[r.centres(deep)]).query(np.c_[r.centres(ij)])
    rise = r.top[deep[k, 0], deep[k, 1]] - low
    return max(0.0, float(np.median(rise)))


def _seat_offset(need: np.ndarray, depth: float) -> dict[str, _t.Any]:
    """THE SEAT (module doc) from the land stations' ``need`` and the
    skirt's ``depth``: ``dz``, the largest gap before (at ``dz = 0``) and
    after, the HEADROOM (how far the shell could rise with no gap: the
    owner's read of a body our ground buries) and ``fixed``."""
    need = np.asarray(need, float)
    if not len(need):
        return {"dz": 0.0, "gap_before_m": 0.0, "gap_after_m": 0.0, "headroom_m": None,
                "fixed": True}
    worst = float(need.min())
    dz = min(0.0, max(worst, -float(depth)))
    return {"dz": dz, "gap_before_m": max(0.0, -worst), "gap_after_m": max(0.0, dz - worst),
            "headroom_m": max(0.0, worst), "fixed": worst >= -float(depth)}


def _ground(surface: _t.Callable, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    many = getattr(surface, "many", None)
    got = (many([float(a) for a in lats], [float(o) for o in lons]) if many is not None
           else [surface(float(a), float(o)) for a, o in zip(lats, lons, strict=True)])
    return np.array([np.nan if z is None else float(z) for z in got], float)


def rim_need(pl: _Placed, others: _t.Sequence[_Placed], surface: _t.Callable
             ) -> dict[str, np.ndarray]:
    """THE STATIONS read (module doc): per station ``ij``, where its ground
    is read (``lons``, ``lats``), ``low``, our ground ``z`` (``nan`` off
    the mesh), ``need`` (``z - (z0 + low)``) and the masks ``wet``,
    ``shared`` and ``land`` (the stations the seat reads)."""
    ij, lons, lats, low = stations(pl)
    z = _ground(surface, lats, lons)
    wet = np.isfinite(z) & (z <= SEA_LEVEL_M + WATER_TOL_M)
    shared = np.zeros(len(z), bool)
    for o in others:
        shared |= o.covers(lons, lats)
    land = np.isfinite(z) & np.isfinite(low) & ~wet & ~shared
    return {"ij": ij, "lons": lons, "lats": lats, "low": low, "z": z,
            "need": z - (pl.z0 + low), "wet": wet, "shared": shared & ~wet, "land": land}


def seat_one(pl: _Placed, others: _t.Sequence[_Placed], surface: _t.Callable
             ) -> dict[str, _t.Any]:
    """THE SEAT (module doc) of one placed shell ``pl`` on ``surface``
    (``others``: the other kept shells): its report."""
    st = rim_need(pl, others, surface)
    land = st["land"]
    depth = _skirt_depth(pl, st["ij"][land], st["low"][land])
    return {"model": pl.model, "resource": pl.resource, "z0": pl.z0,
            "stations": int(len(land)), "land": int(land.sum()), "wet": int(st["wet"].sum()),
            "shared": int(st["shared"].sum()), "off_mesh": int((~np.isfinite(st["z"])).sum()),
            "depth_m": depth, **_seat_offset(st["need"][land], depth)}


def seat_shells(records: _t.Sequence[_t.Mapping[str, _t.Any]], surface: _t.Callable
                ) -> tuple[tuple, list[dict[str, _t.Any]]]:
    """``(records, reports)``: every kept shell of ``records`` (its own row
    carries ``shell``) seated by its skirt on ``surface`` (the drawn mesh;
    ``surface(lat, lon)`` / ``.many(lats, lons)``, ``None`` off it), each
    row of its set (``model``) moved by its ``dz``; one report per shell."""
    shells = [p for p in (placed(r) for r in records if isinstance(r, _t.Mapping)
                          and isinstance(r.get("shell"), _t.Mapping)) if p is not None]
    if not shells:
        return tuple(records), []
    reps = [seat_one(p, [o for o in shells if o is not p], surface) for p in shells]
    dz = {r["model"]: r["dz"] for r in reps if r["dz"]}
    out = tuple(dict(r, elevation=round(float(r["elevation"]) + dz[r["model"]], 3))
                if isinstance(r, _t.Mapping) and r.get("model") in dz else r for r in records)
    return out, reps


def shells_box(records: _t.Iterable[_t.Any]) -> "tuple[float, float, float, float] | None":
    """``(min_lon, min_lat, max_lon, max_lat)`` over every kept shell's
    anchor in ``records``, widened by the largest plan a small shell has
    (``terrain_model.MIN_PLAN_M``) -- the mesh its stations read -- or
    ``None`` with none."""
    from .terrain_model import MIN_PLAN_M
    pts = [(float(r["shell"]["lon"]), float(r["shell"]["lat"])) for r in records
           if isinstance(r, _t.Mapping) and isinstance(r.get("shell"), _t.Mapping)]
    if not pts:
        return None
    lons, lats = zip(*pts, strict=True)
    dlat = MIN_PLAN_M / 111320.0
    dlon = dlat / max(math.cos(math.radians(max(abs(v) for v in lats))), 1e-6)
    return min(lons) - dlon, min(lats) - dlat, max(lons) + dlon, max(lats) + dlat


def log_line(rep: _t.Mapping[str, _t.Any]) -> str:
    """The build log's line on one shell's seat."""
    line = (f"[shell] {rep['resource']} ({rep['model']}): seated by its skirt at "
            f"{rep['z0'] + rep['dz']:.2f} m (author {rep['z0']:.2f}, dz {rep['dz']:+.2f}); "
            f"largest rim gap {rep['gap_before_m']:.2f} -> {rep['gap_after_m']:.2f} m over "
            f"{rep['land']} land station(s) ({rep['wet']} on water, {rep['shared']} under "
            f"another shell, {rep['off_mesh']} off the mesh), skirt depth "
            f"{rep['depth_m']:.2f} m")
    if rep.get("headroom_m"):
        line += f", headroom {rep['headroom_m']:.2f} m"
    if not rep["fixed"]:
        line += " -- REPORTED: no seat within its skirt's depth closes every gap"
    return line
