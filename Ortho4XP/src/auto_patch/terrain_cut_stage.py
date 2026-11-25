"""THE TERRAIN MODELS' CUT IN THE TILE BUILD (owner RULINGS 2026-11-13k,
#2036 (c) / #2040): "Yes to cutting terrain under a terrain object if
it's not being hidden".

WHERE.  Step 1, right after the airport patches are built and loaded
(``O4_Vector_Map.include_airports``): every included airport's object
plan (``o4_v2_rebake_<ICAO>.json``) names its terrain models -- the
model's own seat record carries ``cut`` (file, anchor, heading;
``auto_patch_v2.airport.terrain_model.seat_records``) and its written
elevation.  For each one the user has not hidden (``Hide terrain
objects``, :data:`pack_choice.TERRAIN_CHOICES`), the tile's ``.alt``
raster under the plan is cut to the object's surface
(``auto_patch_v2.airport.terrain_cut``, which carries the consumer
census) and the plan's edge goes into the vector map as a constrained
line.  The mesh step's refinement re-bake (``tile.iterate``) calls
:func:`bake` again on the raster it rewrites.

THE HOLD (#2053 round 3, ``auto_patch_v2.airport.terrain_cut`` THE
HOLD): a record whose ``cut`` names ``erode_m`` (an object carrying
riders) is also held by the MESH -- :func:`held_boxes` gives the mesh
step's curvature weight map its plan boxes (``O4_Mesh_Utils.
build_curv_tol_weight_map``), and :func:`hold` lowers the free vertices
of the drawn mesh under the object's bound after the altitudes are post
processed (``O4_Mesh_Utils.post_process_nodes_altitudes``).  A terrain
model's record (no ``erode_m``) is not held.

THE FILL (#2077 rule B, ``auto_patch_v2.airport.terrain_fill``): after
every cut, a relief skin's ZERO PLANE (``cut["plane"]``) conforms the
ground under its town to its frame zero, then every record whose ``cut``
carries ``"tuck": true`` (a small terrain shell, #2272) has the ground
near its rim conformed to its nearest edge (``terrain_fill.rim_tuck``:
raised to a floating skirt, lowered to a buried top), and every other
record whose ``cut`` carries ``"fill": true`` has the ground raised to its
outer rim.  Neither
touches the tile's edge postings nor an airport patch's boundary
(``patch_area``: the vector step's ``patches_area``, the mesh step's
``O4_Mesh_Utils.patch_coverage_polygon``), and a rim fill stays clear of
another composite's ground.  The footprint's edge is drawn as a DUMMY
constrained line, like the plan's.

ROUND 2 (#2077 spec 9.2): a fill record's cut holds its rim's level to
``W + s`` inside the plan (:func:`_fill_band`, R1); the planes' and fills'
change is recorded beside the ``.alt`` (:func:`write_unfill`) and taken
off every water vertex by the mesh step (:func:`unfill_water`): the water
is levelled from the raster as it stood before them (R2); the footprint's
ring is drawn ``terrain_fill.QUAY_M`` off mapped water (R3); inside the
footprint grown by ``W`` only the composite's own members' bound holds the
plane (R4, ``terrain_fill.conform_plane``).

ROUND 3 (#2077, master rulings R2'/R3' 2026-11-15): the ``.alt`` the
mesher reads keeps the planes and fills ``terrain_fill.DRY_M`` off mapped
water (:func:`write_alt`; the raster in memory -- the roads' -- keeps
them), the fill records' weight boxes leave the water's cells at their
weight (:func:`wet_weight_cells`), and the sidecar gives every land vertex
the conformed ground back (:func:`refill_land`): the water's triangles are
the control's, its vertices read the cut raster, the land reads the
plane.  Every quay piece is drawn (``terrain_fill.quay_rings``).

Nothing here raises into the build: an unreadable plan or object is one
log line and that model is not cut (or not held).
"""
from __future__ import annotations

import glob
import json
import os
import traceback
import typing as _t

import numpy as np
from auto_patch_v2.airport import pack_choice as _PC

__all__ = ["cut_records", "bake", "apply", "held_boxes", "wet_weight_cells", "hold",
           "write_alt", "unfill_water", "refill_land"]

#: the raster postings left uncut at the tile's edge (the neighbour's
#: raster is not cut, and the two must meet)
_EDGE_POSTS = 2


def _hidden(rec: _t.Mapping[str, _t.Any], pack_root: str) -> bool:
    """The user hides this model: the pack's "Hide terrain objects" answer
    is ``update`` and it is offered (``hideable``) -- as the user's
    per-object answers move it (#2272, ``pack_terrain.offered``)."""
    if _PC.Store(_PC.TERRAIN_CHOICES).choice(pack_root) != "update":
        return False
    from auto_patch_v2.airport import pack_terrain as _pt
    res = str(rec.get("resource", ""))
    return res in _pt.offered([res] if rec.get("hideable") else [],
                              _PC.terrain_answers(pack_root))


def cut_records(patch_dir: str, icaos: _t.Iterable[str] | None = None
                ) -> list[dict[str, _t.Any]]:
    """The seat records to cut: every terrain model's own record with a
    ``cut`` in the object plans of ``icaos`` (``None``: every plan in
    ``patch_dir``), less the hidden ones."""
    from auto_patch_v2.airport import terrain_model as _tm
    from auto_patch_v2.model.rebake import PLAN_FILENAME
    want = None if icaos is None else {str(i).upper() for i in icaos}
    out = []
    for path in sorted(glob.glob(os.path.join(patch_dir, PLAN_FILENAME.format(icao="*")))):
        try:
            with open(path, encoding="utf-8") as fh:
                plan = json.load(fh)
        except (OSError, ValueError):
            continue
        if want is not None and str(plan.get("icao", "")).upper() not in want:
            continue
        root = str(plan.get("pack_root") or "")
        for rec in plan.get("authored_seats") or ():
            if (isinstance(rec, dict) and rec.get("seat") == _tm.SEAT
                    and isinstance(rec.get("cut"), dict) and not _hidden(rec, root)):
                out.append(dict(rec, icao=plan.get("icao", "")))
    return out


def _fill_band(raster) -> tuple[float, float]:
    """``(W + s, d)`` of a ``terrain_fill.Raster`` (#2077 round 2 R1): ``W``
    the fill's shoulder, ``s`` the larger posting step, ``d`` one posting
    diagonal (metres) -- a fill record's cut holds its rim's level that far
    inside the plan (``terrain_cut._bound``)."""
    dx, dy = raster.posting_m()
    return raster.shoulder_m() + max(dx, dy), float(np.hypot(dx, dy))


def _fit(rec, band: tuple[float, float] | None = None):
    """One record's cut as a ``TerrainFit`` (its file's plan grid at the
    record's zero and heading, eroded by its ``erode_m`` when it names one,
    to its floor when it names ``floor_m``; a FILL record's edge band
    reaching ``band`` = :func:`_fill_band` when given), or ``None`` where
    the file cannot be read."""
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_model as _tm
    c = rec["cut"]
    grid = _tm.plan_grid(str(c["file"]))
    if grid is None:
        return None
    reach = band if band is not None and c.get("fill") else (_tc.BAND_M, None)
    return _tc.cut_fit(grid, float(rec["elevation"]), float(c["heading"]),
                       float(c.get("erode_m", _tc.ERODE_M)), float(c.get("floor_m", 0.0)),
                       float(reach[0]), reach[1])


def _cut_one(dem, tile, rec) -> int:
    """Cut ``tile.dem.alt_dem`` under one record's plan; the postings cut."""
    from auto_patch_v2.airport import terrain_cut as _tc
    fit = _fit(rec, _fill_band(_raster(dem, tile, None)))
    if fit is None:
        return 0
    c = rec["cut"]
    to_xy, to_ll = _tc.projector(float(c["lat"]), float(c["lon"]))
    w, s, e, n = _tc.plan_box(fit, to_ll)
    a = dem.alt_dem
    ny, nx = a.shape
    dx, dy = (dem.x1 - dem.x0) / (nx - 1), (dem.y1 - dem.y0) / (ny - 1)
    lo = max(dem.x0, _EDGE_POSTS * dx)
    hi = min(dem.x1, 1.0 - _EDGE_POSTS * dx)
    c0 = max(0, int(np.ceil((max(w - tile.lon, lo) - dem.x0) / dx)))
    c1 = min(nx - 1, int(np.floor((min(e - tile.lon, hi) - dem.x0) / dx)))
    lo = max(dem.y0, _EDGE_POSTS * dy)
    hi = min(dem.y1, 1.0 - _EDGE_POSTS * dy)
    r0 = max(0, int(np.ceil((dem.y1 - min(n - tile.lat, hi)) / dy)))
    r1 = min(ny - 1, int(np.floor((dem.y1 - max(s - tile.lat, lo)) / dy)))
    if c1 < c0 or r1 < r0:
        return 0
    cols, rows = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
    lons = tile.lon + dem.x0 + cols.ravel() * dx
    lats = tile.lat + dem.y1 - rows.ravel() * dy
    ground = a[rows.ravel(), cols.ravel()].astype(float)
    z, inside = _tc.cut_heights(fit, to_xy, lons, lats, ground)
    cut = inside & np.isfinite(z) & (z < ground)
    a[rows.ravel()[cut], cols.ravel()[cut]] = z[cut]
    return int(cut.sum())


def bake(tile, records: _t.Sequence[_t.Mapping[str, _t.Any]] | None = None,
         patch_area=None) -> int:
    """Cut ``tile.dem``'s raster under every record (:func:`cut_records`
    of the tile's patch folder when ``None``), then conform its planes and
    fill its rims (module doc, THE FILL; ``patch_area`` the tile-relative
    patch coverage, ``None`` for none); the postings changed."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    dem = getattr(tile, "dem", None)
    if dem is None or getattr(dem, "alt_dem", None) is None:
        return 0
    if records is None:
        records = cut_records(FNAMES.patch_dir(tile.lat, tile.lon))
    total = 0
    for rec in records:
        try:
            k = _cut_one(dem, tile, rec)
        except Exception as exc:
            UI.vprint(1, f"   terrain model {rec.get('resource')} not cut ({exc})")
            UI.vprint(2, traceback.format_exc())
            continue
        total += k
        UI.vprint(1, f"   [{rec.get('icao', '')}] terrain model {rec.get('resource')} "
                     f"({rec.get('id')}): the ground under it cut at {k} posting(s)")
    dem.terrain_fill_delta = None
    if any(r["cut"].get("fill") or r["cut"].get("plane") for r in records):
        try:
            k, dem.terrain_fill_delta = _fill_all(dem, tile, records, patch_area)
            total += k
        except Exception as exc:
            UI.vprint(1, f"   terrain composites not filled ({exc})")
            UI.vprint(2, traceback.format_exc())
    return total


class _Composite(_t.NamedTuple):
    """One record's fill inputs: its cut, projector and rim supports."""

    rec: _t.Mapping[str, _t.Any]
    fit: _t.Any
    to_xy: _t.Callable
    to_ll: _t.Callable
    support_xy: np.ndarray
    support_z: np.ndarray
    owned: _t.Any                  # its ground (``terrain_fill.Owned``)
    floor: _t.Any                  # its zero footprint alone (``Owned``)
    #: the rim's TOP less ``UNDER_M`` (the rim tuck's supports, #2272)
    support_top: np.ndarray


def _composite(rec, band: tuple[float, float] | None = None) -> "_Composite | None":
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_fill as _tf
    from auto_patch_v2.airport import terrain_model as _tm
    from auto_patch_v2.geom.terrain_deck import UNDER_M
    fit = _fit(rec, band)
    grid = _tm.plan_grid(str(rec["cut"]["file"]))
    if fit is None or grid is None:
        return None
    c = rec["cut"]
    to_xy, to_ll = _tc.projector(float(c["lat"]), float(c["lon"]))
    ri, rj = np.nonzero(_tm.outer_rim(grid.covered))
    sx, sy = _tm._world(grid, ri, rj, (0.0, 0.0), float(c["heading"]))
    plane = (c.get("plane") or {}).get("rings") or ()
    rings = tuple(np.asarray(r, float) for r in [*_tc.outline_rings(fit, to_ll), *plane])
    return _Composite(rec, fit, to_xy, to_ll, np.c_[sx, sy],
                      float(rec["elevation"]) + grid.bot[ri, rj] - UNDER_M,
                      _tf.Owned(rings), _tf.Owned(tuple(np.asarray(r, float) for r in plane)),
                      float(rec["elevation"]) + grid.top[ri, rj] - UNDER_M)


def _raster(dem, tile, patch_area):
    """The tile's raster as a ``terrain_fill.Raster``: its edge postings
    and the airport patches frozen."""
    from auto_patch_v2.airport import terrain_fill as _tf
    a = dem.alt_dem
    ny, nx = a.shape
    dx, dy = (dem.x1 - dem.x0) / (nx - 1), (dem.y1 - dem.y0) / (ny - 1)
    if patch_area is not None and getattr(patch_area, "is_empty", True):
        patch_area = None

    def frozen(rows, cols, lons, lats):
        out = ((rows < _EDGE_POSTS) | (cols < _EDGE_POSTS)
               | (rows > ny - 1 - _EDGE_POSTS) | (cols > nx - 1 - _EDGE_POSTS))
        if patch_area is not None and len(rows):
            import shapely
            out |= shapely.contains_xy(patch_area, lons - tile.lon, lats - tile.lat)
        return out
    return _tf.Raster(a, tile.lon + dem.x0, tile.lat + dem.y1, dx, dy, frozen)


def _fill_window(dem, tile, comps) -> tuple[int, int, int, int] | None:
    """``(r0, r1, c0, c1)``: the raster window every plane and rim fill of
    ``comps`` can change (their plan boxes and zero footprints grown by
    the reach and a posting), ``None`` off the raster."""
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_fill as _tf
    boxes = []
    for c in comps:
        boxes.append(_tc.plan_box(c.fit, c.to_ll))
        for r in (c.rec["cut"].get("plane") or {}).get("rings") or ():
            a = np.asarray(r, float)
            boxes.append((a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()))
    if not boxes:
        return None
    b = np.asarray(boxes, float)
    ny, nx = dem.alt_dem.shape
    dx, dy = (dem.x1 - dem.x0) / (nx - 1), (dem.y1 - dem.y0) / (ny - 1)
    pad = _tf.REACH_M / _tf._M_PER_DEG
    padx = pad / max(np.cos(np.radians(float(b[:, 1].mean()))), 1e-6) + dx
    pad += dy
    c0 = max(0, int(np.floor((b[:, 0].min() - padx - tile.lon - dem.x0) / dx)))
    c1 = min(nx - 1, int(np.ceil((b[:, 2].max() + padx - tile.lon - dem.x0) / dx)))
    r0 = max(0, int(np.floor((dem.y1 - (b[:, 3].max() + pad - tile.lat)) / dy)))
    r1 = min(ny - 1, int(np.ceil((dem.y1 - (b[:, 1].min() - pad - tile.lat)) / dy)))
    return None if c1 < c0 or r1 < r0 else (r0, r1, c0, c1)


def _fill_all(dem, tile, records, patch_area) -> tuple[int, "dict | None"]:
    """THE FILL (module doc): every plane, every rim tuck, every rim fill;
    the postings changed and the change (:func:`write_unfill`'s
    record, their ``alt - before`` at the postings they moved)."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_fill as _tf
    raster = _raster(dem, tile, patch_area)
    band = _fill_band(raster)
    comps = [c for c in (_composite(r, band) for r in records) if c is not None]
    win = _fill_window(dem, tile, comps)
    if win is None:
        return 0, None
    r0, r1, c0, c1 = win
    before = dem.alt_dem[r0:r1 + 1, c0:c1 + 1].astype(np.float32, copy=True)

    def bound(members):
        def cap(lons, lats):
            out = np.full(len(lons), np.inf)
            for c in members:
                out = np.minimum(out, _tc.cut_heights(c.fit, c.to_xy, lons, lats,
                                                      np.full(len(lons), np.inf))[0])
            return out
        return cap
    total = 0
    for c in comps:
        plane = c.rec["cut"].get("plane")
        if not plane or not plane.get("rings"):
            continue
        ll = np.concatenate([np.asarray(r, float) for r in plane["rings"]])
        pad = _tf.REACH_M / _tf._M_PER_DEG
        padx = pad / max(np.cos(np.radians(float(ll[:, 1].mean()))), 1e-6)
        # floors win in the owned zone (R4): its own members' bound holds
        # everywhere, another composite's only beyond W of the footprint
        k = _tf.conform_plane(raster, c.to_xy, plane["rings"], float(plane["z"]), bound([c]),
                              (ll[:, 0].min() - padx, ll[:, 1].min() - pad,
                               ll[:, 0].max() + padx, ll[:, 1].max() + pad),
                              bound([o for o in comps if o is not c]))
        total += k
        UI.vprint(1, f"   [{c.rec.get('icao', '')}] terrain composite {c.rec.get('resource')} "
                     f"({c.rec.get('id')}): the ground of its zero footprint conformed to "
                     f"{float(plane['z']):.2f} m at {k} posting(s)")
    for c in comps:
        if not c.rec["cut"].get("tuck"):
            continue
        # #2272: a small shell at its author's height -- the ground near its
        # rim conformed to its nearest edge, raised or lowered (its fill)
        rep = _tf.rim_tuck(raster, c.to_xy, c.to_ll, c.support_xy, c.support_z,
                           c.support_top, bound([c]),
                           [o.owned for o in comps if o is not c] + [c.floor])
        total += rep["raised"] + rep["lowered"]
        UI.vprint(1, f"   [{c.rec.get('icao', '')}] terrain shell {c.rec.get('resource')} "
                     f"({c.rec.get('id')}): the ground tucked under its rim, "
                     f"{rep['raised']} posting(s) raised and {rep['lowered']} lowered "
                     f"from {rep['supports']} support(s)")
    for c in comps:
        if not c.rec["cut"].get("fill") or c.rec["cut"].get("tuck"):
            continue
        # floors win -- its own town's floor too: a cliff's crest never
        # raises the zero footprint at its foot through the cliff
        rep = _tf.rim_fill(raster, c.to_xy, c.to_ll, c.support_xy, c.support_z, bound([c]),
                           [o.owned for o in comps if o is not c] + [c.floor])
        total += rep["raised"]
        UI.vprint(1, f"   [{c.rec.get('icao', '')}] terrain model {c.rec.get('resource')} "
                     f"({c.rec.get('id')}): the ground filled to its rim at "
                     f"{rep['raised']} posting(s) from {rep['supports']} support(s), "
                     f"{rep['unserved']} unserved")
    d = dem.alt_dem[r0:r1 + 1, c0:c1 + 1] - before
    ii, jj = np.nonzero(d != 0)
    if not len(ii):
        return total, None
    ny, nx = dem.alt_dem.shape
    change = d[ii, jj].astype(np.float32)
    wet = _wet(tile, dem, ii + r0, jj + c0)
    if wet.any():
        UI.vprint(1, f"   terrain composites (#2077 R2'): {int(wet.sum())} of {len(ii)} "
                     f"planed or filled posting(s) kept off the mesher's raster within "
                     f"{_tf.DRY_M:.0f} m of mapped water")
    return total, {"rows": (ii + r0).astype(np.int32), "cols": (jj + c0).astype(np.int32),
                   "delta": np.where(wet, 0.0, change).astype(np.float32),
                   "held": np.where(wet, change, 0.0).astype(np.float32),
                   "nx": int(nx), "ny": int(ny),
                   "frame": np.array([dem.x0, dem.y0, dem.x1, dem.y1], float)}


def _metric(tile):
    """``(x, y) -> metres`` of tile-relative degrees (east, north) about the
    tile's middle latitude: the frame the water's distances are read in."""
    kx = 111_320.0 * float(np.cos(np.radians(tile.lat + 0.5)))
    return lambda q: np.c_[q[:, 0] * kx, q[:, 1] * 111_320.0]


def _wet(tile, dem, rows, cols) -> np.ndarray:
    """THE DRY RASTER (R2'): the postings ``(rows, cols)`` within
    ``terrain_fill.DRY_M`` of the tile's mapped water (none without it)."""
    import shapely
    from auto_patch_v2.airport import terrain_fill as _tf
    from shapely.geometry import box as _box
    out = np.zeros(len(rows), bool)
    try:
        water = _tile_water(tile)
    except Exception:
        water = None
    if water is None or not len(rows):
        return out
    ny, nx = dem.alt_dem.shape
    dx, dy = (dem.x1 - dem.x0) / (nx - 1), (dem.y1 - dem.y0) / (ny - 1)
    x, y = dem.x0 + cols * dx, dem.y1 - rows * dy
    pad = 2.0 * _tf.DRY_M / 111_320.0 / max(float(np.cos(np.radians(tile.lat + 1.0))), 1e-6)
    near = water.intersection(_box(x.min() - pad, y.min() - pad, x.max() + pad, y.max() + pad))
    if near.is_empty:
        return out
    to_m = _metric(tile)
    near = shapely.transform(near, to_m)
    shapely.prepare(near)
    return shapely.dwithin(near, shapely.points(to_m(np.c_[x, y])), _tf.DRY_M)


def _outline(rec) -> list:
    """The plan's edge of one record, tile-relative ``(lon, lat)`` rings."""
    from auto_patch_v2.airport import terrain_cut as _tc
    fit = _fit(rec)
    if fit is None:
        return []
    c = rec["cut"]
    return _tc.outline_rings(fit, _tc.projector(float(c["lat"]), float(c["lon"]))[1])


def _tile_water(tile):
    """The tile's mapped water (sea and inland, tile-relative degrees: the
    mesh's own derivation, ``O4_Vector_Map.cached_tile_water``) or
    ``None`` when none is cached."""
    import O4_Vector_Map as VMAP
    from shapely import union_all
    parts = [g for g in VMAP.cached_tile_water(tile) if g is not None and not g.is_empty]
    return union_all(parts) if parts else None


def _quay(tile, rec, rings, water, report: dict) -> list:
    """THE QUAY (R3, R3'): one zero footprint's rings less mapped water
    grown by ``terrain_fill.QUAY_M`` (``terrain_fill.quay_rings``, every
    piece drawn; the hairline pre-flight's gaps from ``O4_Hairline``);
    ``water`` the tile's (:func:`_tile_water`); ``report`` its counts."""
    import O4_Hairline as MESH
    import shapely
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_fill as _tf
    from shapely.geometry import box as _box
    c = rec["cut"]
    to_xy, to_ll = _tc.projector(float(c["lat"]), float(c["lon"]))
    a = np.concatenate([np.asarray(r, float) for r in rings])
    pad = 0.002
    near = water.intersection(_box(a[:, 0].min() - tile.lon - pad, a[:, 1].min() - tile.lat - pad,
                                   a[:, 0].max() - tile.lon + pad, a[:, 1].max() - tile.lat + pad))
    near = shapely.transform(near, lambda q: np.c_[to_xy(q[:, 0] + tile.lon, q[:, 1] + tile.lat)])
    return _tf.quay_rings(rings, to_xy, to_ll, near, degenerate_m=MESH.HAIRLINE_DEGENERATE_M,
                          spacing_m=MESH.HAIRLINE_SPACING_M, report=report)


def _edge_lines(tile, records) -> list:
    """Every record's plan edge and zero-footprint edge (THE QUAY), as
    tile-relative ``LineString`` s for the DUMMY constrained lines."""
    import O4_UI_Utils as UI
    from shapely.geometry import LineString
    water, untrimmed = None, 0
    if any((r["cut"].get("plane") or {}).get("rings") for r in records):
        try:
            water = _tile_water(tile)
        except Exception as exc:
            UI.vprint(2, f"   the tile's water unread ({exc})")
    lines = []
    for rec in records:
        try:
            plane = (rec["cut"].get("plane") or {}).get("rings") or ()
            if plane and water is not None:
                rep = {}
                plane = _quay(tile, rec, plane, water, rep)
                UI.vprint(1, f"   [{rec.get('icao', '')}] terrain composite {rec.get('resource')}: "
                             f"its quay drawn as {rep.get('pieces', 0)} piece(s) "
                             f"({rep.get('merged', 0)} merged, {rep.get('cleaned', 0)} cleaned "
                             f"of a hairline, {rep.get('dropped', 0)} left out)")
            elif plane:
                untrimmed += 1
            lines += [LineString(np.asarray(r, float) - np.array([tile.lon, tile.lat]))
                      for r in [*_outline(rec), *plane] if len(r) >= 2]
        except Exception as exc:
            UI.vprint(1, f"   terrain model {rec.get('resource')}: no edge line ({exc})")
    if untrimmed:
        UI.vprint(1, f"   {untrimmed} zero footprint(s) drawn untrimmed: no mapped water cached")
    return lines


def write_alt(tile) -> None:
    """Write ``tile.dem`` to the ``.alt`` the mesher reads, and its
    :func:`write_unfill` sidecar: THE DRY RASTER (R2') -- the postings the
    last :func:`bake` kept off it (``terrain_fill_delta["held"]``) are
    written at their cut ground; the raster in memory keeps them."""
    import O4_File_Names as FNAMES
    dem = tile.dem
    d = getattr(dem, "terrain_fill_delta", None)
    held = None if not d else d.get("held")
    if held is None or not np.any(held):
        dem.write_to_file(FNAMES.alt_file(tile))
    else:
        r, c = d["rows"], d["cols"]
        full = dem.alt_dem[r, c].copy()
        dem.alt_dem[r, c] = full - held
        try:
            dem.write_to_file(FNAMES.alt_file(tile))
        finally:
            dem.alt_dem[r, c] = full
    write_unfill(tile)


def write_unfill(tile) -> None:
    """THE WATER IS NEVER FILLED (#2077 round 2 R2): write the change the
    last :func:`bake` made with its planes and fills (``tile.dem.
    terrain_fill_delta``: ``delta`` in the ``.alt``, ``held`` kept off it
    by :func:`write_alt`) beside the ``.alt`` -- the mesh step takes
    ``delta`` off every water vertex (:func:`unfill_water`) and gives
    ``held`` to every land vertex (:func:`refill_land`) -- or remove a stale
    one when it made none."""
    import O4_File_Names as FNAMES
    path = FNAMES.alt_unfill_file(tile)
    d = getattr(getattr(tile, "dem", None), "terrain_fill_delta", None)
    if not d:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "wb") as fh:
        np.savez(fh, **d)


def _sidecar_dz(tile, vertices, v: np.ndarray, key: str) -> tuple[np.ndarray, np.ndarray]:
    """``(v, dz)``: the vertices of ``v`` inside the box of the sidecar's
    change and the bilinear ``key`` (``delta`` / ``held``) at their
    positions (Triangle4XP's ``altitude()`` indexing); empty without one."""
    import O4_File_Names as FNAMES
    none = (np.zeros(0, np.int64), np.zeros(0))
    path = FNAMES.alt_unfill_file(tile)
    if not len(v) or not os.path.exists(path):
        return none
    with np.load(path) as f:
        if key not in f.files:
            return none
        rows, cols, delta = f["rows"], f["cols"], f[key].astype(float)
        nx, ny, (x0, y0, x1, y1) = int(f["nx"]), int(f["ny"]), f["frame"]
    if not len(rows) or not np.any(delta):
        return none
    px = (vertices[6 * v] - x0) / (x1 - x0) * (nx - 1)
    py = (y1 - vertices[6 * v + 1]) / (y1 - y0) * (ny - 1)
    r0, c0 = int(rows.min()), int(cols.min())
    grid = np.zeros((int(rows.max()) - r0 + 3, int(cols.max()) - c0 + 3))
    grid[rows - r0 + 1, cols - c0 + 1] = delta
    i, j = np.floor(px).astype(np.int64), np.floor(py).astype(np.int64)
    inside = (i >= c0 - 1) & (i <= cols.max() + 1) & (j >= r0 - 1) & (j <= rows.max() + 1)
    if not inside.any():
        return none
    v, px, py, i, j = (a[inside] for a in (v, px, py, i, j))
    ip, jp = np.minimum(i + 1, nx - 1), np.minimum(j + 1, ny - 1)

    def at(jj, ii):
        gi, gj = ii - c0 + 1, jj - r0 + 1
        ok = (gi >= 0) & (gj >= 0) & (gi < grid.shape[1]) & (gj < grid.shape[0])
        out = np.zeros(len(ii))
        out[ok] = grid[gj[ok], gi[ok]]
        return out
    rx, ry = px - i, py - j
    dz = (at(j, i) * (1 - rx) * (1 - ry) + at(j, ip) * rx * (1 - ry)
          + at(jp, i) * (1 - rx) * ry + at(jp, ip) * rx * ry)
    moved = np.abs(dz) > 1e-9
    return v[moved], dz[moved]


def _level(tile, vertices, v, key: str, sign: float, what: str) -> dict:
    """:func:`unfill_water` / :func:`refill_land`: ``sign`` times the
    sidecar's ``key`` added to the vertices ``v``; one log line; never
    raises."""
    import O4_UI_Utils as UI
    rep = {"vertices": 0, "worst_m": 0.0}
    try:
        v, dz = _sidecar_dz(tile, vertices, v, key)
        if not len(v):
            return rep
        vertices[6 * v + 2] += sign * dz
        if sign > 0:            # a land vertex on the conformed ground: its
            vertices[6 * v + 3] = 0     # normal is the plane's, not the dry
            vertices[6 * v + 4] = 0     # raster's (the O4_Mesh_Pins convention)
        rep = {"vertices": int(len(v)), "worst_m": float(np.abs(dz).max())}
    except Exception as exc:
        UI.vprint(1, f"   terrain composites: {what} not levelled ({exc})")
        UI.vprint(2, traceback.format_exc())
        return rep
    UI.vprint(1, f"   terrain composites (#2077 R2): {rep['vertices']} {what} vertex(es) "
                 f"levelled from the {'conformed' if sign > 0 else 'unfilled'} raster, "
                 f"worst {rep['worst_m']:.2f} m")
    return rep


def unfill_water(tile, vertices, water_valued) -> dict:
    """R2 on the mesh (``O4_Mesh_Utils.post_process_nodes_altitudes``,
    before the water smoothing): every water-valued vertex in the box of
    :func:`write_unfill`'s change has the bilinear ``delta`` (the planes'
    and fills' change the ``.alt`` carries) taken off its altitude, so the
    water is levelled from the raster as it stood before the planes and
    fills.  ``vertices`` flat, six per vertex, changed in place.  One log
    line; never raises."""
    if not water_valued:
        return {"vertices": 0, "worst_m": 0.0}
    v = np.fromiter((int(k) for k in water_valued), np.int64)
    return _level(tile, vertices, v, "delta", -1.0, "water")


def refill_land(tile, vertices, water_valued) -> dict:
    """R2' on the mesh (beside :func:`unfill_water`): every vertex that is
    not water-valued has the bilinear ``held`` (the change :func:`write_alt`
    kept off the ``.alt``) added, so the land reads the conformed raster
    the vector step made; its normal is zeroed.  One log line; never
    raises."""
    n = len(vertices) // 6
    wet = np.zeros(n, bool)
    if water_valued:
        wet[np.fromiter((int(k) for k in water_valued), np.int64)] = True
    return _level(tile, vertices, np.flatnonzero(~wet), "held", 1.0, "land")


def apply(tile, vector_map, icaos: _t.Iterable[str], patch_area=None) -> int:
    """STEP 1 (module doc): cut the raster under the included airports'
    terrain models, rewrite the ``.alt`` (:func:`write_alt`, with its
    sidecar) and draw each plan's edge and each zero footprint's quay as
    a constrained line.  The postings cut."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from shapely.geometry import MultiLineString
    records = cut_records(FNAMES.patch_dir(tile.lat, tile.lon), icaos)
    if not records:
        write_unfill(tile)
        return 0
    UI.vprint(0, "-> Cutting the ground under the airports' terrain objects")
    total = bake(tile, records, patch_area)
    if not total:
        write_unfill(tile)
        return 0
    write_alt(tile)
    lines = _edge_lines(tile, records)
    if lines:
        vector_map.encode_MultiLineString(MultiLineString(lines), tile.dem.alt_vec,
                                          "DUMMY", check=True)
    return total


def _held(records) -> list:
    """The records THE HOLD applies to: their ``cut`` names ``erode_m``."""
    return [r for r in records if "erode_m" in r["cut"]]


def _held_records(tile) -> list:
    import O4_File_Names as FNAMES
    return _held(cut_records(FNAMES.patch_dir(tile.lat, tile.lon)))


def held_boxes(tile) -> list[tuple[float, float, float, float]]:
    """``(west, south, east, north)`` degrees of every held record's plan
    in the tile's patch folder (the mesh step's weight boxes) -- and of
    every FILL record's plan and zero footprint grown by the fill's reach
    (#2077: the mesh draws the filled and conformed ground at one posting;
    weights only, never the hold)."""
    import O4_File_Names as FNAMES
    return [b for _, b in _weight_boxes(cut_records(FNAMES.patch_dir(tile.lat, tile.lon)))]


def _weight_boxes(records) -> list[tuple[bool, tuple[float, float, float, float]]]:
    """``(held, box)`` of every record :func:`held_boxes` names: ``held``
    for THE HOLD's (``erode_m``), else a fill record's box."""
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_fill as _tf
    out = []
    for rec in records:
        c = rec["cut"]
        if "erode_m" not in c and not c.get("fill"):
            continue
        fit = _fit(rec)
        if fit is None:
            continue
        w, s, e, n = _tc.plan_box(fit, _tc.projector(float(c["lat"]), float(c["lon"]))[1])
        if "erode_m" not in c:
            for r in (c.get("plane") or {}).get("rings") or ():
                a = np.asarray(r, float)
                w, s = min(w, float(a[:, 0].min())), min(s, float(a[:, 1].min()))
                e, n = max(e, float(a[:, 0].max())), max(n, float(a[:, 1].max()))
            dy = _tf.REACH_M / 111_320.0
            dx = dy / max(np.cos(np.radians(0.5 * (s + n))), 1e-6)
            w, s, e, n = w - dx, s - dy, e + dx, n + dy
        out.append(("erode_m" in c, (w, s, e, n)))
    return out


def _cells(tile, box) -> tuple[int, int, int, int]:
    """``(rowmin, rowmax, colmin, colmax)`` of a degree box on the mesh
    step's 1001 x 1001 weight grid (``O4_Mesh_Utils._raise_box_curv_weight``)."""
    w, s, e, n = box
    return (max(round((tile.lat + 1 - n) * 1000), 0), min(round((tile.lat + 1 - s) * 1000), 1000),
            max(round((w - tile.lon) * 1000), 0), min(round((e - tile.lon) * 1000), 1000))


def wet_weight_cells(tile, records=None) -> tuple[np.ndarray, np.ndarray]:
    """THE DRY RASTER's weights (R2'): ``(rows, cols)`` of the weight-grid
    cells a FILL record's box raises that meet mapped water and lie in no
    held box -- the mesh step leaves them at the weight they had, so the
    water's own triangles are refined as the control's.  ``records``
    :func:`cut_records` of the tile's patch folder when ``None``."""
    import shapely
    if records is None:
        import O4_File_Names as FNAMES
        records = cut_records(FNAMES.patch_dir(tile.lat, tile.lon))
    boxes = _weight_boxes(records)
    empty = (np.zeros(0, np.int64), np.zeros(0, np.int64))
    fill = [_cells(tile, b) for held, b in boxes if not held]
    if not fill:
        return empty
    water = _tile_water(tile)
    if water is None:
        return empty
    mark = np.zeros((1001, 1001), np.int8)
    for r0, r1, c0, c1 in fill:
        mark[r0:r1 + 1, c0:c1 + 1] = 1
    for r0, r1, c0, c1 in (_cells(tile, b) for held, b in boxes if held):
        mark[r0:r1 + 1, c0:c1 + 1] = 0
    ll, kk = np.nonzero(mark)
    x, y = kk / 1000.0, 1.0 - ll / 1000.0
    cells = shapely.box(x - 5e-4, y - 5e-4, x + 5e-4, y + 5e-4)
    shapely.prepare(water)
    hit = shapely.intersects(water, cells)
    return ll[hit].astype(np.int64), kk[hit].astype(np.int64)


def _hold_one(tile, vertices, corners, fixed: np.ndarray, rec,
              floor: np.ndarray | None = None) -> dict:
    """THE HOLD of one record on the mesh (``vertices`` flat, six per
    vertex, changed in place); the counts for its log line."""
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_model as _tm
    from auto_patch_v2.geom.terrain_deck import UNDER_M
    c = rec["cut"]
    fit, tris = _fit(rec), _tm.plan_solid(str(c["file"]))
    if fit is None or tris is None:
        raise ValueError("its object cannot be read")
    to_xy, to_ll = _tc.projector(float(c["lat"]), float(c["lon"]))
    w, s, e, n = _tc.plan_box(fit, to_ll)
    lon = tile.lon + vertices[0::6]
    lat = tile.lat + vertices[1::6]
    cl, ca = lon[corners], lat[corners]
    meet = (cl.max(1) >= w) & (cl.min(1) <= e) & (ca.max(1) >= s) & (ca.min(1) <= n)
    vids, inv = np.unique(corners[meet], return_inverse=True)
    x0, z0, bound = _tc.hold_bound(tris, float(c["erode_m"]), float(c.get("floor_m", 0.0)))
    ii, jj = np.nonzero(np.isfinite(bound))
    rep = {"triangles": int(meet.sum()), "samples": int(len(ii)), "lowered": 0,
           "worst_m": 0.0, "unresolved": 0}
    if not len(vids) or not len(ii):
        return rep
    lx, lz = fit.local(*to_xy(lon[vids], lat[vids]))
    z_old = vertices[6 * vids + 2].astype(float)
    z_new, rep["unresolved"] = _tc.hold_heights(
        np.c_[lx, lz], z_old, inv.reshape(-1, 3), ~np.isin(vids, fixed),
        np.c_[x0 + _tc.HOLD_CELL_M * ii, z0 + _tc.HOLD_CELL_M * jj],
        float(rec["elevation"]) + bound[ii, jj] - UNDER_M,
        None if floor is None else floor[vids])
    moved = vids[z_new < z_old]
    if len(moved):
        drop = (z_old - z_new)[z_new < z_old]
        vertices[6 * moved + 2] = z_new[z_new < z_old]
        vertices[6 * moved + 3] = 0
        vertices[6 * moved + 4] = 0
        rep["lowered"], rep["worst_m"] = int(len(moved)), float(drop.max())
    return rep


def water_floor(vertices, corners, water) -> np.ndarray | None:
    """Per vertex, the highest water datum (the altitude the mesh post-
    process gave a water-valued vertex) of any water vertex it shares a
    triangle with; ``-inf`` elsewhere; None when there is no water.  The
    hold never lowers a land vertex under it (#2053, owner 2026-11-13)."""
    water = np.fromiter((int(v) for v in water), np.int64)
    if not len(water):
        return None
    z = np.asarray(vertices[2::6], float)
    is_w = np.zeros(len(z), bool)
    is_w[water] = True
    tri_w = np.where(is_w, z, -np.inf)[corners].max(1)
    floor = np.full(len(z), -np.inf)
    hit = np.isfinite(tri_w)
    for k in range(3):
        np.maximum.at(floor, corners[hit, k], tri_w[hit])
    return floor


def hold(tile, vertices, corners, fixed, water=()) -> dict:
    """THE HOLD (module doc) on the post-processed mesh: ``vertices`` the
    flat six-per-vertex node array (tile-relative x, y, altitude, normal
    x, normal y, carried altitude; changed in place: a lowered vertex's
    normal is zeroed, the ``O4_Mesh_Pins`` convention), ``corners`` the
    ``(m, 3)`` triangles, ``fixed`` the vertices it never moves (the
    INTERP_ALT corners, the water-valued ones, the patch pins), ``water``
    the water-valued vertices (their altitude floors the land beside them,
    ``water_floor``).  One log
    line per held record; ``{id: counts}``.  Never raises."""
    import O4_UI_Utils as UI
    try:
        records = _held_records(tile)
    except Exception as exc:
        UI.vprint(1, f"   the hold: no records read ({exc})")
        return {}
    if not records:
        return {}
    fixed = np.fromiter((int(v) for v in fixed), np.int64)
    corners = np.asarray(corners, np.int64)
    floor = water_floor(vertices, corners, water)
    out = {}
    for rec in records:
        try:
            r = _hold_one(tile, vertices, corners, fixed, rec, floor)
        except Exception as exc:
            UI.vprint(1, f"   terrain object {rec.get('resource')} not held ({exc})")
            UI.vprint(2, traceback.format_exc())
            continue
        out[str(rec.get("id"))] = r
        UI.vprint(1, f"   [{rec.get('icao', '')}] the hold (#2053) {rec.get('resource')} "
                     f"({rec.get('id')}): {r['lowered']} vertex(es) lowered under the "
                     f"object, worst {r['worst_m']:.2f} m; {r['unresolved']} of "
                     f"{r['samples']} sample(s) unresolved")
    return out
