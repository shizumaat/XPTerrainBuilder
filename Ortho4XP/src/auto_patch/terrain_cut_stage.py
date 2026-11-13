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

Nothing here raises into the build: an unreadable plan or object is one
log line and that model is not cut.
"""
from __future__ import annotations

import glob
import json
import os
import traceback
import typing as _t

import numpy as np

from . import pack_choice as _PC

__all__ = ["cut_records", "bake", "apply"]

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
    record's zero and heading, eroded by its ``erode_m`` when it names one),
    or ``None`` where the file cannot be read."""
    from auto_patch_v2.airport import terrain_cut as _tc
    from auto_patch_v2.airport import terrain_model as _tm
    c = rec["cut"]
    grid = _tm.plan_grid(str(c["file"]))
    if grid is None:
        return None
    return _tc.cut_fit(grid, float(rec["elevation"]), float(c["heading"]),
                       float(c.get("erode_m", _tc.ERODE_M)))


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
