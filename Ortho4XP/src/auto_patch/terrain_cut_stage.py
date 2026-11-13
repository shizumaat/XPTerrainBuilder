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

from . import pack_choice as _PC

__all__ = ["cut_records", "bake", "apply", "held_boxes", "hold"]

#: the raster postings left uncut at the tile's edge (the neighbour's
#: raster is not cut, and the two must meet)
_EDGE_POSTS = 2


def _hidden(rec: _t.Mapping[str, _t.Any], pack_root: str) -> bool:
    """The user hides this model: it is offered (``hideable``) and the
    pack's "Hide terrain objects" answer is ``update``."""
    return bool(rec.get("hideable")) and \
        _PC.Store(_PC.TERRAIN_CHOICES).choice(pack_root) == "update"


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


def _fit(rec):
    """One record's cut as a ``TerrainFit`` (its file's plan grid at the
    record's zero and heading, eroded by its ``erode_m`` when it names one,
    to its floor when it names ``floor_m``), or ``None`` where the
    file cannot be read."""
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_model as _tm
    c = rec["cut"]
    grid = _tm.plan_grid(str(c["file"]))
    if grid is None:
        return None
    return _tc.cut_fit(grid, float(rec["elevation"]), float(c["heading"]),
                       float(c.get("erode_m", _tc.ERODE_M)), float(c.get("floor_m", 0.0)))


def _cut_one(dem, tile, rec) -> int:
    """Cut ``tile.dem.alt_dem`` under one record's plan; the postings cut."""
    from auto_patch_v2.airport import terrain_cut as _tc
    fit = _fit(rec)
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


def bake(tile, records: _t.Sequence[_t.Mapping[str, _t.Any]] | None = None) -> int:
    """Cut ``tile.dem``'s raster under every record (:func:`cut_records`
    of the tile's patch folder when ``None``); the postings cut."""
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
    return total


def _outline(rec) -> list:
    """The plan's edge of one record, tile-relative ``(lon, lat)`` rings."""
    from auto_patch_v2.airport import terrain_cut as _tc
    fit = _fit(rec)
    if fit is None:
        return []
    c = rec["cut"]
    return _tc.outline_rings(fit, _tc.projector(float(c["lat"]), float(c["lon"]))[1])


def apply(tile, vector_map, icaos: _t.Iterable[str]) -> int:
    """STEP 1 (module doc): cut the raster under the included airports'
    terrain models, rewrite the ``.alt`` and draw each plan's edge as a
    constrained line.  The postings cut."""
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI
    from shapely.geometry import LineString, MultiLineString
    records = cut_records(FNAMES.patch_dir(tile.lat, tile.lon), icaos)
    if not records:
        return 0
    UI.vprint(0, "-> Cutting the ground under the airports' terrain objects")
    total = bake(tile, records)
    if not total:
        return 0
    tile.dem.write_to_file(FNAMES.alt_file(tile))
    lines = []
    for rec in records:
        try:
            lines += [LineString(r - np.array([tile.lon, tile.lat])) for r in _outline(rec)
                      if len(r) >= 2]
        except Exception as exc:
            UI.vprint(1, f"   terrain model {rec.get('resource')}: no edge line ({exc})")
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
    in the tile's patch folder (the mesh step's weight boxes)."""
    from auto_patch_v2.airport import terrain_cut as _tc
    out = []
    for rec in _held_records(tile):
        fit = _fit(rec)
        if fit is not None:
            c = rec["cut"]
            out.append(_tc.plan_box(fit, _tc.projector(float(c["lat"]), float(c["lon"]))[1]))
    return out


def _hold_one(tile, vertices, corners, fixed: np.ndarray, rec) -> dict:
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
        float(rec["elevation"]) + bound[ii, jj] - UNDER_M)
    moved = vids[z_new < z_old]
    if len(moved):
        drop = (z_old - z_new)[z_new < z_old]
        vertices[6 * moved + 2] = z_new[z_new < z_old]
        vertices[6 * moved + 3] = 0
        vertices[6 * moved + 4] = 0
        rep["lowered"], rep["worst_m"] = int(len(moved)), float(drop.max())
    return rep


def hold(tile, vertices, corners, fixed) -> dict:
    """THE HOLD (module doc) on the post-processed mesh: ``vertices`` the
    flat six-per-vertex node array (tile-relative x, y, altitude, normal
    x, normal y, carried altitude; changed in place: a lowered vertex's
    normal is zeroed, the ``O4_Mesh_Pins`` convention), ``corners`` the
    ``(m, 3)`` triangles, ``fixed`` the vertices it never moves (the
    INTERP_ALT corners, the water-valued ones, the patch pins).  One log
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
    out = {}
    for rec in records:
        try:
            r = _hold_one(tile, vertices, corners, fixed, rec)
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
