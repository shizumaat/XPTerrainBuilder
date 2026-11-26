#!/usr/bin/env python3
"""THE TERRAIN MODELS' CUT AND RIM FILL, REPLAYED ON THE RAW DEM (#2217,
owner RULINGS 2026-11-26b (2)/(4)).

What would the tile build's terrain step (``auto_patch.terrain_cut_stage.
bake``: every cut, then the planes, then the rim fills) do to our ground
under and around an airport's terrain models?  Offline, no tile build:
the airport's OWN rebake plans (``terrain_cut_stage.cut_records`` of a
patch folder -- the records the build reads, hidden models left out), a
window of the tile's raw rasters (``terrain_model_census.rasters``: the
``.hgt`` under its cached insets, finest first) sampled at ``--posting-m``
(default: the ``.hgt``'s own posting) around the plans, the patch
folder's ``*.osm`` closed ways frozen (airside is king), then ``bake``
itself on that window.  Per record, on its plan grid (5 m cells), land
cells only (the cached water layers, ``terrain_model_census.
water_reader``; a wet rim is a modelled under-water cliff, RULINGS
2026-11-25a (3)):

* RIM GAP -- each outer-rim cell's bottom over the ground after the step
  (the edge floats where it is > 0): p50 / p90 / max and the share over
  ``terrain_fill.SERVED_M``;
* RING -- the ground the step LOWERED at the outer rim (the moat, #2217):
  p50 / p90 / max and the share over 0.5 m;
* GAPS IN THE BOX -- the postings inside the plan's box its plan does not
  cover (a notch, a hole), within ``terrain_fill.REACH_M`` of a rim cell
  standing over our ground: how many the step raised;
* THROUGH -- the share of the land cells deeper than ``terrain_cut.
  BAND_M`` from the edge where the ground after the step stands more than
  ``terrain_cut.BURIED_M`` over the top (13k's measure: the cost of a
  skirt left buried);
* SKIRT -- the share of the plan the stage leaves buried (``terrain_cut.
  buried_skirt`` on the raw raster, RULINGS 2026-11-26b (4)), the share
  merely buried, and the skirt's depth from the edge.

``--json OUT`` writes the report with the raster's change; ``--against
BASE.json`` prints the postings that moved against a base run (count,
max) and each record's numbers beside the base's.  Read-only.

    venv/bin/python tools/terrain_cut_replay.py PATCH_DIR [--icao ICAO]
        [--posting-m M] [--elevation-root DIR] [--json OUT] [--against BASE]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "..", "src"), HERE, os.path.join(HERE, "harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

__all__ = ["records", "window", "rim_stats", "run", "print_report", "main"]

#: the window's margin around the plans (m): beyond the fill's reach
_PAD_M = 200.0
_K_LAT = 111_320.0


def records(patch_dir: str, icao: str | None) -> list[dict]:
    """The build's cut records of ``patch_dir`` (one per model)."""
    from auto_patch import terrain_cut_stage as TCS
    out: dict = {}
    for r in TCS.cut_records(patch_dir, [icao] if icao else None):
        out.setdefault((r.get("icao"), r.get("id"), r.get("resource")), r)
    return list(out.values())


def window(recs: list[dict], root: str, posting_m: float | None):
    """``(tile, before)``: a stand-in tile whose ``dem`` is a raw-raster
    window around every record's plan (tile-relative degrees, the build's
    DEM frame) and a copy of its raster."""
    import terrain_model_census as TMC
    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.airport import terrain_cut as TC
    lat0, lon0 = float(recs[0]["cut"]["lat"]), float(recs[0]["cut"]["lon"])
    tlat, tlon = math.floor(lat0), math.floor(lon0)
    dems = TMC.rasters(root, tlat, tlon)
    if not dems:
        raise SystemExit(f"NOT MEASURED: no raster for {tlat:+d}{tlon:+d} under {root}")
    step = float(posting_m or dems[-1][2])
    boxes = []
    for r in recs:
        fit = TCS._fit(r)
        if fit is not None:
            boxes.append(TC.plan_box(fit, TC.projector(r["cut"]["lat"], r["cut"]["lon"])[1]))
    b = np.asarray(boxes, float)
    kx = _K_LAT * math.cos(math.radians(lat0))
    w, e = b[:, 0].min() - _PAD_M / kx, b[:, 2].max() + _PAD_M / kx
    s, n = b[:, 1].min() - _PAD_M / _K_LAT, b[:, 3].max() + _PAD_M / _K_LAT
    dy, dx = step / _K_LAT, step / kx
    nx, ny = int(math.ceil((e - w) / dx)) + 1, int(math.ceil((n - s) / dy)) + 1
    lons, lats = w + dx * np.arange(nx), n - dy * np.arange(ny)
    glon, glat = np.meshgrid(lons, lats)
    read = TMC.sampler(dems, lon0, lat0)
    alt = np.asarray(read((glon.ravel() - lon0) * kx, (glat.ravel() - lat0) * _K_LAT),
                     float).reshape(glon.shape)
    alt = np.where(np.isfinite(alt), alt, np.nanmedian(alt)).astype(np.float32)
    dem = types.SimpleNamespace(alt_dem=alt, x0=w - tlon, x1=float(lons[-1]) - tlon,
                                y0=float(lats[-1]) - tlat, y1=n - tlat)
    return types.SimpleNamespace(lat=tlat, lon=tlon, dem=dem, step_m=step), alt.copy()


def _patch_area(patch_dir: str, tile):
    """The patch folder's closed ways, tile-relative (the build's frozen
    ``patches_area``), or ``None``."""
    import shapely
    import shapely.affinity
    import shell_seat_replay as SSR
    polys = [a for a in (SSR.patch_area(p) for p in
                         sorted(glob.glob(os.path.join(patch_dir, "*.osm")))) if a is not None]
    if not polys:
        return None
    return shapely.affinity.translate(shapely.union_all(polys), -tile.lon, -tile.lat)


def _raster(tile, a: np.ndarray):
    from auto_patch_v2.airport import terrain_fill as TF
    d = tile.dem
    ny, nx = a.shape
    return TF.Raster(a, tile.lon + d.x0, tile.lat + d.y1, (d.x1 - d.x0) / (nx - 1),
                     (d.y1 - d.y0) / (ny - 1))


def _pct(v: np.ndarray, over: float) -> dict:
    if not len(v):
        return {"n": 0}
    return {"n": int(len(v)), "p50": round(float(np.percentile(v, 50)), 2),
            "p90": round(float(np.percentile(v, 90)), 2), "max": round(float(v.max()), 2),
            "over": round(float(np.mean(v > over)), 3)}


def _wet(tile, rec, lons, lats) -> np.ndarray:
    import terrain_model_census as TMC
    c = rec["cut"]
    water = TMC.water_reader(tile.lat, tile.lon, float(c["lon"]), float(c["lat"]))
    if water is None:
        return np.zeros(len(lons), bool)
    kx = _K_LAT * math.cos(math.radians(float(c["lat"])))
    return np.asarray(water((lons - float(c["lon"])) * kx,
                            (lats - float(c["lat"])) * _K_LAT)[0], bool)


def rim_stats(tile, rec: dict, before: np.ndarray, after: np.ndarray) -> dict:
    """RIM GAP, RING, GAPS IN THE BOX, THROUGH and SKIRT (module doc) of
    one record."""
    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.airport import terrain_cut as TC
    from auto_patch_v2.airport import terrain_fill as TF
    from auto_patch_v2.airport import terrain_model as TM
    from auto_patch_v2.geom.terrain_deck import CELL_M
    grid = TM.plan_grid(str(rec["cut"]["file"]))
    if grid is None:
        return {"resource": rec.get("resource"), "error": "unreadable"}
    c = rec["cut"]
    hdg, z0 = float(c["heading"]), float(rec["elevation"])
    to_xy, to_ll = TC.projector(float(c["lat"]), float(c["lon"]))
    b0, b1 = _raster(tile, before), _raster(tile, after)
    ri, rj = np.nonzero(TM.outer_rim(grid.covered))
    lo, la = to_ll(*TM._world(grid, ri, rj, (0.0, 0.0), hdg))
    g0, g1 = b0.sample(lo, la), b1.sample(lo, la)
    ok = ~_wet(tile, rec, lo, la) & np.isfinite(g0) & np.isfinite(g1)
    gap = (z0 + grid.bot[ri, rj] - g1)[ok]
    # the postings in the plan's box the plan does not cover, near a rim
    # cell standing over our ground
    fit = TCS._fit(rec)
    rows, cols, plo, pla = b0.window(*TC.plan_box(fit, to_ll))
    px, py = to_xy(plo, pla)
    _i, _j, inside = fit.grid.cell_of(*fit.local(px, py))
    from scipy.spatial import cKDTree
    rx, ry = TM._world(grid, ri, rj, (0.0, 0.0), hdg)
    hang = (z0 + grid.bot[ri, rj]) > g0 + 1e-6
    near = np.zeros(len(px), bool)
    if hang.any():
        d, _k = cKDTree(np.c_[rx[hang], ry[hang]]).query(np.c_[px, py])
        near = d <= TF.REACH_M
    box = ~inside & near & ~_wet(tile, rec, plo, pla)
    raised = after[rows, cols] > before[rows, cols] + 1e-3
    ii, jj = np.nonzero(grid.covered)
    alo, ala = to_ll(*TM._world(grid, ii, jj, (0.0, 0.0), hdg))
    dem = np.full(grid.bot.shape, np.nan)
    dem[ii, jj] = b0.sample(alo, ala) - z0
    skirt = TC.buried_skirt(grid, dem)
    edge = _edge_depth(grid)
    depth = edge[skirt]
    # THROUGH: the ground after the step over the top by more than the
    # pavement bar, deeper than the edge band, on land (the 13k measure)
    deep = grid.covered[ii, jj] & (edge[ii, jj] > TC.BAND_M) & ~_wet(tile, rec, alo, ala)
    over = (b1.sample(alo, ala) - z0 - grid.top[ii, jj]) > TC.BURIED_M
    return {"resource": rec.get("resource"), "id": rec.get("id"), "z0": z0,
            "rim_cells": int(len(ri)), "rim_land": int(ok.sum()),
            "rim_gap": _pct(gap, TF.SERVED_M), "ring": _pct((g0 - g1)[ok], 0.5),
            "box_gaps": {"postings": int(box.sum()), "raised": int((box & raised).sum())},
            "through": {"deep_cells": int(deep.sum()),
                        "share": round(float(np.mean(over[deep])), 3) if deep.any() else 0.0},
            "plan_m2": round(float(grid.covered.sum()) * CELL_M * CELL_M),
            "skirt": {"share": round(float(skirt.sum()) / max(int(grid.covered.sum()), 1), 3),
                      "buried_share": round(float(np.sum(grid.covered & (np.nan_to_num(
                          dem - grid.top, nan=-1.0) > TC.BURIED_M))) /
                          max(int(grid.covered.sum()), 1), 3),
                      **({"depth_p50_m": round(float(np.percentile(depth, 50)), 1),
                          "depth_p90_m": round(float(np.percentile(depth, 90)), 1),
                          "depth_max_m": round(float(depth.max()), 1)} if len(depth) else {})}}


def _edge_depth(grid) -> np.ndarray:
    """Each cell's distance (m) to the plan's edge cells (0 on them)."""
    from scipy import ndimage

    from auto_patch_v2.geom.terrain_deck import CELL_M
    cov = grid.covered
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    return ndimage.distance_transform_edt(~rim) * CELL_M


def run(args) -> dict:
    from auto_patch import terrain_cut_stage as TCS
    recs = records(args.patch_dir, args.icao)
    if not recs:
        raise SystemExit(f"NOT MEASURED: no terrain-model cut record in {args.patch_dir}")
    tile, before = window(recs, args.elevation_root, args.posting_m)
    changed = TCS.bake(tile, recs, _patch_area(args.patch_dir, tile))
    after = tile.dem.alt_dem
    return {"patch_dir": args.patch_dir, "posting_m": round(tile.step_m, 2),
            "changed": int(changed), "shape": list(after.shape),
            "delta": (after.astype(float) - before).round(3).tolist(),
            "records": [rim_stats(tile, r, before, after) for r in recs]}


def print_report(rep: dict, base: dict | None = None) -> None:
    print(f"{rep['patch_dir']}: posting {rep['posting_m']} m, raster {rep['shape']}, "
          f"{rep['changed']} posting change(s) by the step")
    old = {(r.get("resource"), r.get("id")): r for r in (base or {}).get("records", [])}
    for r in rep["records"]:
        key = (r.get("resource"), r.get("id"))
        print(f"  {r.get('resource')} ({r.get('id')}) z0 {r.get('z0')}  rim land "
              f"{r.get('rim_land')}/{r.get('rim_cells')}  plan {r.get('plan_m2')} m2")
        for k in ("rim_gap", "ring", "box_gaps", "through", "skirt"):
            print(f"    {k:<9} {r.get(k)}" + (f"   base {old[key].get(k)}" if key in old else ""))
    if base is not None and base.get("shape") == rep["shape"]:
        mv = np.asarray(rep["delta"]) - np.asarray(base["delta"])
        a = np.abs(mv)
        print(f"  MOVERS against base: {int((a > 0.01).sum())} posting(s) > 0.01 m "
              f"(raised {int((mv > 0.01).sum())} max {float(max(mv.max(), 0.0)):.2f} m, "
              f"lowered {int((mv < -0.01).sum())} max {float(max(-mv.min(), 0.0)):.2f} m)")


def main(argv=None) -> int:
    import terrain_model_census as TMC
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("patch_dir", help="the airport's patch folder (its rebake plans)")
    ap.add_argument("--icao")
    ap.add_argument("--posting-m", type=float, help="the raster posting (default: the .hgt's)")
    ap.add_argument("--elevation-root", default=TMC.DEFAULT_ELEVATION)
    ap.add_argument("--json", help="write the report here")
    ap.add_argument("--against", help="a base --json report: print the movers")
    args = ap.parse_args(argv)
    rep = run(args)
    base = None
    if args.against:
        with open(args.against, encoding="utf-8") as fh:
            base = json.load(fh)
    print_report(rep, base)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
