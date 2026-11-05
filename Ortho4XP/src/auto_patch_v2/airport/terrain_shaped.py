"""A TERRAIN-SHAPED HARD DECK IS ONE RIGID BODY ON ITS GROUND (issue #1730).

A pack may model a stretch of TERRAIN as one ``ATTR_hard_deck`` object: a
hill with a highway, its tunnel and its cloverleaf ramps, authored as a skin
that follows the ground (KBWI ``Buildings/Highway.obj``: 470 x 480 m, y
-25.9 ... +1.65).  It is not a bridge deck: nothing spans a gap, so it must
not be split into bodies, seated on one foot, nor read as a pit or a bridge
with a trench cut under it.  It is seated as ONE rigid unit, at the height
that best fits its deck to the DEM, and the patch under it is drawn to its
surface.

The rule reads GEOMETRY and the DEM only (RULINGS 05e -- no names).  The
deck's triangles are binned on a ``CELL_M`` grid in the object's own plan
frame; each cell carries the deck's lowest and highest surface there.  A
placement is terrain-shaped when all of these hold:

* a deck far beyond a bridge's -- at least ``MIN_AREA_M2`` of covered cells
  (the largest airport bridge deck measured, LFPG ``Hard_deck/H19``, is
  16,275 m2);
* RELIEF in its lowest surface beyond a plane -- the 5th to 95th
  percentile span of its departure from its least-squares plane at least
  ``MIN_RELIEF_M`` (a deck is a plane on a road's grade, however long:
  every hard deck of KBNA, KIAH and LFPG departs from its plane by under
  2 m; a terrain skin is the hill -- 15.8 m);
* it FOLLOWS the ground -- at the rigid best fit (:func:`fit`), more than
  ``MIN_FOLLOW`` of its covered cells hold the DEM inside the deck's own
  span there or within ``FOLLOW_BAND_M`` of it (a deck over a gap has the
  ground far under its span);
* it is ALONE in its frame -- no other placement shares its origin and
  heading.  A deck authored in a frame with other objects (a terminal's
  departure ramp at the terminal's origin) is the frame's to seat, and
  moving it alone would pull the author's model apart (``msl_feet``'s
  origin-set rule).

THE FIT is the height ``z0`` of the object's ``y = 0`` plane minimising the
summed distance of the DEM from each cell's deck span ``[z0 + bot, z0 +
top]`` (an L1 fit: a cell whose ground lies anywhere inside the span -- the
hill over a tunnel -- costs nothing).  The placement is written at ``z0`` as
an ``OBJECT_MSL`` row (``placement_write``), and every groundside patch
vertex under the deck takes a soft target at the deck's surface nearest its
ground (``geom/terrain_deck.target_at``,
``constraints/terrain_shaped``): cut where the ground pokes through, filled
where it falls short, left where it lies inside the span.
"""
from __future__ import annotations

import functools
import math
import os
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M, DeckGrid, TerrainFit
from . import dsf as _dsf

__all__ = ["MIN_AREA_M2", "MIN_RELIEF_M", "MIN_FOLLOW", "FOLLOW_BAND_M", "SEAT",
           "placement_fits", "fit", "grid_of_triangles", "dem_many_of",
           "grid_of_resource", "seat_records", "log_line", "row_seats",
           "PORTAL_SEAT", "ENTRANCE_SEAT", "portal_seat_records"]

MIN_AREA_M2 = 20_000.0
MIN_RELIEF_M = 5.0
MIN_FOLLOW = 0.5
FOLLOW_BAND_M = 1.5
#: the seat record's ``seat`` value (``RebakePlan.authored_seats``)
SEAT = "terrain fit"
#: a roofed portal's row seated at its pinned mouth floor (owner
#: 2026-11-04 ENTC: "the tunnel mouth objects are still not seated at the
#: bottom of the ramp"; ``Tunnel.portal_seat``)
PORTAL_SEAT = "portal floor"
#: #1747: an ENTRANCE object's face seated with its bottom on its portal's
#: floor -- a BODY's seat (the object stands at both ends, and carries more),
#: never the row's (``row_seats`` writes none)
ENTRANCE_SEAT = "entrance face"
_WHY = {SEAT: "terrain_fit", PORTAL_SEAT: "portal_floor"}


def _deck_grid(g: _t.Any) -> "DeckGrid | None":
    """The :class:`DeckGrid` of an ``obj8.ObjGeometry``'s hard deck, or
    ``None`` when it has none or it fails the area / relief gates (no DEM
    is needed for those, so most files stop here)."""
    tri = getattr(g, "hard_deck", None)
    if tri is None or not len(tri):
        return None
    p = g.vertices[np.asarray(tri)]
    if _extent_m2(p) < MIN_AREA_M2:
        return None
    grid = grid_of_triangles(p)
    if grid.area_m2 < MIN_AREA_M2 or grid.relief_m < MIN_RELIEF_M:
        return None
    return grid


def _extent_m2(p: np.ndarray) -> float:
    """The plan bounding-box area of the triangles ``p`` on the grid."""
    ni = int(math.ceil((float(p[:, :, 0].max()) - float(p[:, :, 0].min())) / CELL_M)) + 1
    nj = int(math.ceil((float(p[:, :, 2].max()) - float(p[:, :, 2].min())) / CELL_M)) + 1
    return ni * nj * CELL_M * CELL_M


def grid_of_triangles(p: np.ndarray) -> DeckGrid:
    """The :class:`DeckGrid` of the authored triangles ``p`` (``(n, 3, 3)``,
    ungated): each covered cell's lowest and highest surface."""
    x0, z0 = float(p[:, :, 0].min()), float(p[:, :, 2].min())
    ni = int(math.ceil((float(p[:, :, 0].max()) - x0) / CELL_M)) + 1
    nj = int(math.ceil((float(p[:, :, 2].max()) - z0) / CELL_M)) + 1
    bot = np.full((ni, nj), np.inf)
    top = np.full((ni, nj), -np.inf)
    for t in p:
        _bin(t, x0, z0, bot, top)
    bot[~np.isfinite(bot)] = np.nan
    top[~np.isfinite(top)] = np.nan
    return DeckGrid(x0, z0, bot, top)


def _bin(t: np.ndarray, x0: float, z0: float, bot: np.ndarray, top: np.ndarray) -> None:
    """Write one triangle's surface height into the cells whose centre it
    covers (barycentric; an edge-on triangle covers none)."""
    xs, zs = t[:, 0], t[:, 2]
    d = (zs[1] - zs[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (zs[0] - zs[2])
    if abs(d) < 1e-9:
        return
    i0 = max(0, int(math.ceil((xs.min() - x0) / CELL_M)))
    i1 = min(bot.shape[0] - 1, int(math.floor((xs.max() - x0) / CELL_M)))
    j0 = max(0, int(math.ceil((zs.min() - z0) / CELL_M)))
    j1 = min(bot.shape[1] - 1, int(math.floor((zs.max() - z0) / CELL_M)))
    if i1 < i0 or j1 < j0:
        return
    gx, gz = np.meshgrid(x0 + CELL_M * np.arange(i0, i1 + 1),
                         z0 + CELL_M * np.arange(j0, j1 + 1), indexing="ij")
    a = ((zs[1] - zs[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gz - zs[2])) / d
    b = ((zs[2] - zs[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gz - zs[2])) / d
    c = 1.0 - a - b
    m = (a >= -1e-9) & (b >= -1e-9) & (c >= -1e-9)
    if not m.any():
        return
    y = a * t[0, 1] + b * t[1, 1] + c * t[2, 1]
    sl = (slice(i0, i1 + 1), slice(j0, j1 + 1))
    bot[sl] = np.where(m, np.minimum(bot[sl], y), bot[sl])
    top[sl] = np.where(m, np.maximum(top[sl], y), top[sl])


@functools.lru_cache(maxsize=1024)
def _file_grid(path: str, mtime_ns: int, size: int) -> "DeckGrid | None":
    from .obj8 import parse_obj8
    try:
        with open(path, "rb") as fh:
            if b"ATTR_hard_deck" not in fh.read():
                return None
        return _deck_grid(parse_obj8(path))
    except (OSError, ValueError):
        return None


def _path_grid(path: str) -> "DeckGrid | None":
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _file_grid(path, st.st_mtime_ns, st.st_size)


def fit(grid: DeckGrid, xy: tuple[float, float], heading_deg: float,
        dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
        ) -> "tuple[float, float] | None":
    """``(z0, follow)`` -- THE RIGID FIT of one placement of ``grid`` (module
    doc), or ``None`` with no DEM under the deck."""
    ii, jj = np.nonzero(grid.covered)
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    x, z = grid.x0 + CELL_M * ii, grid.z0 + CELL_M * jj
    dem = np.asarray(dem_many(xy[0] + x * c - z * s, xy[1] - (x * s + z * c)), dtype=float)
    ok = np.isfinite(dem)
    if not ok.any():
        return None
    lo = dem[ok] - grid.top[ii[ok], jj[ok]]
    hi = dem[ok] - grid.bot[ii[ok], jj[ok]]
    # the L1 cost is convex and piecewise linear: its minimum sits at one
    # of the breakpoints
    cand = np.unique(np.round(np.r_[lo, hi], 3))
    if len(cand) > 512:
        cand = np.unique(np.percentile(cand, np.linspace(0.0, 100.0, 513)))
    cost = [float(np.sum(np.maximum(lo - q, 0.0) + np.maximum(q - hi, 0.0))) for q in cand]
    z0 = float(cand[int(np.argmin(cost))])
    gap = np.maximum(lo - z0, 0.0) + np.maximum(z0 - hi, 0.0)
    return z0, float(np.mean(gap <= FOLLOW_BAND_M))


def placement_fits(placements: _t.Iterable[tuple],
                   grid_of: _t.Callable[[str], "DeckGrid | None"],
                   dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
                   ) -> dict[str, TerrainFit]:
    """The terrain-shaped placements among ``placements`` -- ``(id, def
    path, xy, heading, ...)`` rows -- by id.  ``grid_of(def path)`` is the
    resource's :class:`DeckGrid` or ``None``."""
    from .msl_feet import origin_key
    from .obj8 import is_stock_library_resource
    rows = [(str(p[0]), str(p[1]), (float(p[2][0]), float(p[2][1])), float(p[3]))
            for p in placements]
    frames: dict[tuple, int] = {}
    for _i, _d, xy, hdg in rows:
        k = origin_key(xy, hdg)
        frames[k] = frames.get(k, 0) + 1
    out: dict[str, TerrainFit] = {}
    for oid, dpath, xy, hdg in rows:
        if is_stock_library_resource(dpath) or frames[origin_key(xy, hdg)] > 1:
            continue
        grid = grid_of(dpath)
        got = None if grid is None else fit(grid, xy, hdg, dem_many)
        if got is None or got[1] <= MIN_FOLLOW:
            continue
        out[oid] = TerrainFit(oid, dpath, xy, hdg, got[0], got[1], grid.area_m2,
                              grid.relief_m, grid)
    return out


def dem_many_of(dem: _t.Any) -> _t.Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """A batch DEM reader over a sampler (its ``z_many``) or over a plain
    ``z(x, y)`` callable."""
    many = getattr(dem, "z_many", None)
    if many is not None:
        return many
    one = dem if callable(dem) else dem.z
    return lambda xs, ys: np.array([one(float(a), float(b)) for a, b in zip(xs, ys, strict=True)])


def grid_of_resource(dpath: str, pack_root: "str | None",
                     index: "_t.Mapping[str, str] | None") -> "DeckGrid | None":
    """:func:`_deck_grid` of a placement's resource as ``obj8`` resolves it
    (one reading per file version)."""
    from .obj8 import resolve_resource
    phys = resolve_resource(dpath, pack_root, index)
    return None if phys is None else _path_grid(phys)


def seat_records(airport: _t.Any) -> list[dict[str, _t.Any]]:
    """One ``RebakePlan.authored_seats`` record per terrain-shaped deck the
    pack reading recognised (``Airport.terrain_decks``): ``seat``
    :data:`SEAT`, ``elevation`` its fitted ``z0`` -- the row the placement
    writer seats (:func:`row_seats`)."""
    decks = tuple(getattr(airport, "terrain_decks", ()) or ())
    return [{"id": f.id, "resource": f.path, "datum": "terrain", "seat": SEAT,
             "elevation": round(f.z0, 3), "follow": round(f.follow, 3),
             "area_m2": round(f.area_m2, 1), "relief_m": round(f.relief_m, 2)}
            for f in sorted(decks, key=lambda f: f.id)]


def log_line(icao: str, decks: _t.Sequence[TerrainFit]) -> str:
    """The build log's one line on the terrain-shaped decks."""
    if not decks:
        return f"[{icao}] terrain-shaped decks: none"
    return f"[{icao}] terrain-shaped decks: " + "; ".join(
        f"{f.path} ({f.id}) seated at {f.z0:.2f} m, follows {f.follow:.0%} of "
        f"{f.area_m2:,.0f} m2, relief {f.relief_m:.1f} m" for f in decks)


def portal_seat_records(structures: _t.Iterable[_t.Any], to_ll=None) -> list[dict[str, _t.Any]]:
    """One record per roofed portal seated at its mouth's pinned floor
    (``Tunnel.portal_seat``) -- the row :func:`row_seats` writes there --
    and per ENTRANCE face (#1747; ``to_ll`` the frame's xy -> (lat, lon)):
    seat :data:`ENTRANCE_SEAT`, its ``end`` ``[lat, lon]``, the elevation its
    zero, which ``airport/entrance_seat`` lays on the face's own body."""
    out = []
    for tn in structures:
        ps = getattr(tn, "portal_seat", ())
        if not ps or not tn.portal:
            continue
        rec = {"id": tn.portal, "resource": ps[0], "datum": "portal",
               "seat": PORTAL_SEAT, "elevation": round(float(ps[1]), 3)}
        if len(ps) > 2:
            if to_ll is None:
                continue
            lat, lon = to_ll(*ps[2])
            rec.update(seat=ENTRANCE_SEAT, end=[round(float(lat), 9), round(float(lon), 9)],
                       reach_m=float(ps[3]) if len(ps) > 3 else 0.0)
        out.append(rec)
    return out


def row_seats(dump: _t.Any, records: _t.Iterable[_t.Mapping[str, _t.Any]]) -> tuple:
    """The ``model.placement.MslSeat`` of every :func:`seat_records` and
    :func:`portal_seat_records` record
    naming a row of ``dump`` (``dsf:obj<i>`` is row ``i``): the placement
    written as ``OBJECT_MSL`` at its fitted ``z0``, whole."""
    from ..model.placement import MslSeat
    rows = list(getattr(dump, "placements", ()) or ())
    out = []
    for r in records or ():
        oid = str(r.get("id", ""))
        tile, i = _dsf.row_of(oid)
        if r.get("seat") not in _WHY or tile is not None or i is None:
            continue
        if not 0 <= i < len(rows) or str(rows[i].def_path) != str(r.get("resource")):
            continue
        row = rows[i]
        out.append(MslSeat(i, str(row.def_path), float(row.lon), float(row.lat),
                           float(getattr(row, "heading_deg", 0.0)),
                           float(r["elevation"]), _WHY[str(r.get("seat"))]))
    return tuple(out)
