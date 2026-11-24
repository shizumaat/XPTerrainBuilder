"""THE TERRAIN-MODEL CENSUS, DRY (owner RULINGS 2026-11-13i, #2036 (c), #2040).

Which objects of an installed pack does ``auto_patch_v2/airport/
terrain_model`` read as MODELLING TERRAIN, and where would it seat them?
Per pack: every OBJ8 resource through the candidate gates (plan, height
span, photo-textured top, top relief -- the module's own ``shape_of``),
then every placement row of a candidate in the pack's PRISTINE tile DSF
(``.anchor_bak`` when the app has written the pack) through the module's
own ``match`` against the corpus rasters: the tile's ``.hgt`` under its
cached airport insets (finest first), with an inset of
``terrain_model.QUALITY_PIXEL_M`` or finer counted as quality elevation.

    venv/bin/python tools/terrain_model_census.py PACK_ROOT [PACK_ROOT ...]
        [--elevation-root DIR] [--json OUT]

It reads the RAW rasters, not the build's baked frame (no smoothing, no
water flattening), so a seat it prints can differ from a build's by the
bake; the verdicts (candidate / match / hideable) are the thresholds'
calibration.  Read-only: the DSF is copied and dumped in a temporary
folder, never in the pack or the mod cache.

GROUND SHELLS (issue #2056, ``auto_patch_v2/airport/ground_shell``): an
object past the plan and photo gates but too flat for a terrain model is
asked the ground shell's own candidate test (a lowest surface departing
from its plane by >= 5 m) and, per placement, its verdict at the no-float
seat: SEATED (lies on the ground) or HIDDEN.

TERRAIN COMPOSITES (#2077, spec ``docs/specs/2077-terrain-composites-spec.md``
5): every OBJ8 is also asked ``relief_skin``'s candidate (gate count
``skin``; per row ``relief skin`` with its seat, the raster under its
origin).  A terrain model's row carries both seats -- ``z0_rim`` (the
2026-11-13i rim minimum) and ``z0`` (#2077's L1 fit, capped over a wet
rim) -- with ``water_rim`` (the share of its outer rim over the tile's
cached water layers, ``O4_Vector_Map.cached_tile_water``; ``None`` where
none is cached) and the hide offer of the new quality test.  An
``OBJECT_MSL`` row is read like any other (llows), its datum beside it.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()  # utf-8 console before any print (#92)

from auto_patch_v2.airport import ground_shell as GS  # noqa: E402
from auto_patch_v2.airport import relief_skin as RS  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_shell as TS  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402

DEFAULT_ELEVATION = "/Users/noah/XPTerrainBuilderData/Elevation_data"


def _stem(lat: int, lon: int) -> tuple[str, str]:
    blk = f"{int(math.floor(lat / 10) * 10):+03d}{int(math.floor(lon / 10) * 10):+04d}"
    return blk, f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def rasters(root: str, lat: int, lon: int) -> list[tuple]:
    """``(geotransform, array, pixel_m, name)`` of the tile's cached
    insets (finest first) and its ``.hgt`` (last)."""
    from osgeo import gdal
    gdal.UseExceptions()
    blk, stem = _stem(lat, lon)
    found = []
    for path in sorted(glob.glob(os.path.join(root, blk, stem + "_airport_insets", "*.tif"))):
        try:
            with open(path[:-4] + ".json") as fh:
                meta = json.load(fh)
            px = float(meta.get("native_resolution_m") or meta.get("resolution_m") or 30.0)
        except (OSError, ValueError, TypeError):
            px = 30.0
        found.append((px, path))
    found.sort()
    hgt = os.path.join(root, blk, stem + ".hgt")
    if os.path.isfile(hgt):
        found.append((90.0, hgt))
    out = []
    for px, path in found:
        ds = gdal.Open(path)
        a = ds.GetRasterBand(1).ReadAsArray().astype(float)
        a[a < -1000.0] = np.nan
        out.append((ds.GetGeoTransform(), a, px, os.path.basename(path)))
    return out


def sampler(dems: list, lon0: float, lat0: float, *, fine: bool = False):
    """A ``(xs, ys) -> z`` (or ``-> quality``) reader in metres east /
    north of ``(lon0, lat0)``: the first raster holding a value, bilinear."""
    mlat = 111_320.0
    mlon = mlat * math.cos(math.radians(lat0))

    def read(xs, ys, pixel_m=TM.QUALITY_PIXEL_M):
        lo = lon0 + np.asarray(xs, dtype=float) / mlon
        la = lat0 + np.asarray(ys, dtype=float) / mlat
        z = np.full(lo.shape, np.nan)
        q = np.zeros(lo.shape, dtype=bool)
        for gt, a, px, _n in dems:
            c = (lo - gt[0]) / gt[1] - 0.5
            r = (la - gt[3]) / gt[5] - 0.5
            ok = np.isnan(z) & (c >= 0) & (r >= 0) & (c < a.shape[1] - 1) & (r < a.shape[0] - 1)
            i = np.flatnonzero(ok)
            c0, r0 = np.floor(c[ok]).astype(int), np.floor(r[ok]).astype(int)
            fc, fr = c[ok] - c0, r[ok] - r0
            v = (a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr)
                 + a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)
            z[i] = v
            q[i[np.isfinite(v)]] = px <= pixel_m
        return q if fine else z
    return read


def candidates(pack_root: str) -> tuple[dict, dict]:
    """``(gate counts, {relative path: Shape})`` over the pack's OBJ8s; a
    ground shell's Shape is keyed ``("ground", path)``."""
    gates = {"objects": 0, "plan": 0, "photo": 0, "candidate": 0, "ground": 0, "skin": 0,
             "shell": 0}
    shapes = {}
    for path in glob.glob(os.path.join(pack_root, "**", "*.[oO][bB][jJ]"), recursive=True):
        if "__b" in os.path.basename(path):          # the app's own split bodies
            continue
        gates["objects"] += 1
        try:
            g = parse_obj8(path)
        except (OSError, ValueError):
            continue
        rel = os.path.relpath(path, pack_root).replace(os.sep, "/").lower()
        shell = GS.shape_of(path, g)
        if shell is not None:
            gates["ground"] += 1
            shapes[("ground", rel)] = shell
        skin = RS.shape_of(path, g)
        if skin is not None and TM.shape_of(path, g) is None:
            gates["skin"] += 1
            shapes[("skin", rel)] = skin
        if TM._plan_m(g) < TM.MIN_PLAN_M:
            small = TS.small_shape(path, g)
            if small is not None:
                gates["shell"] += 1
                shapes[rel] = small
            continue
        gates["plan"] += 1
        tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
        if TM.photo_spread(g.vertices, TM._vt_rows(path), tris) > TM.MAX_PHOTO_SPREAD:
            continue
        gates["photo"] += 1
        shape = TM.shape_of(path, g)
        if shape is not None:
            gates["candidate"] += 1
            shapes[rel] = shape
    return gates, shapes


def placements(dsf: str, dsftool: str) -> tuple[list[str], list[tuple]]:
    """``(OBJECT_DEF paths, [(def index, lon, lat, heading, kind,
    elevation)])`` of a DSF (``elevation`` the AGL / MSL column, ``None``
    for a plain row), dumped in a temporary folder."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.dsf")
        shutil.copyfile(dsf, src)
        txt = os.path.join(tmp, "in.txt")
        subprocess.run([dsftool, "--dsf2text", src, txt], capture_output=True, check=False)
        defs, rows = [], []
        with open(txt, encoding="utf-8", errors="surrogateescape") as fh:
            for line in fh:
                if line.startswith("OBJECT_DEF "):
                    defs.append(line[11:].strip())
                elif line.startswith(("OBJECT ", "OBJECT_AGL ", "OBJECT_MSL ")):
                    # ``OBJECT_MSL`` / ``OBJECT_AGL`` carry their elevation
                    # BEFORE the heading (``airport/dsf``; #2272: read the
                    # other way round, every datum here was a heading)
                    t = line.split()
                    rows.append((int(t[1]), float(t[2]), float(t[3]), float(t[-1]), t[0],
                                 float(t[4]) if len(t) > 5 else None))
    return defs, rows


def water_reader(lat: int, lon: int, lon0: float, lat0: float):
    """``water(xs, ys) -> (wet, level)`` over the tile's CACHED water layers
    in metres east / north of ``(lon0, lat0)`` (the engine's own
    ``TileWater``), or ``None`` where none can be read."""
    try:
        import O4_Config_Utils as CFG
        import O4_Vector_Map as VMAP
        from auto_patch_v2.airport.dem_production import TileWater
        t = CFG.Tile(lat, lon, "")
        t.read_from_config()
        w = TileWater(lat, lon, *VMAP.cached_tile_water(t))
    except Exception:
        return None
    if not w.has_data:
        return None
    mlat = 111_320.0
    mlon = mlat * math.cos(math.radians(lat0))

    def read(xs, ys):
        la = lat0 + np.asarray(ys, float) / mlat
        lo = lon0 + np.asarray(xs, float) / mlon
        wet = w.index_of(la, lo) >= 0
        return wet, np.where(wet, 0.0, np.nan)
    return read


def _model_row(shape, hdg: float, dem, fine, water, datum=None) -> dict:
    """A terrain model row's both seats, its wet-rim share and its offer
    (a small shell, ``terrain_shell``, is matched at its ``datum``)."""
    m = TM.match(shape, (0.0, 0.0), hdg, dem, fine, water, datum)
    if m is None:
        return {"verdict": "no DEM match" if datum is not None or not shape.small
                else "not msl"}
    rec = {"verdict": "terrain shell" if shape.small else "terrain model", **{k: (round(v, 3) if isinstance(v, float) else v)
                                          for k, v in m.items()}}
    rec["z0_rim"] = round(TM.rim_seat(shape.grid, (0.0, 0.0), hdg, dem) or math.nan, 3)
    if water is not None:
        ri, rj = np.nonzero(TM.outer_rim(shape.grid.covered))
        rx, ry = TM._world(shape.grid, ri, rj, (0.0, 0.0), hdg)
        rec["water_rim"] = round(float(np.mean(water(rx, ry)[0])), 3) if len(rx) else 0.0
    else:
        rec["water_rim"] = None
    return rec


def census(pack_root: str, elevation_root: str, dsftool: str) -> dict:
    gates, shapes = candidates(pack_root)
    out = {"pack": os.path.basename(os.path.normpath(pack_root)), "gates": gates, "rows": []}
    for dsf in sorted(glob.glob(os.path.join(pack_root, "Earth nav data", "*", "*.dsf"))):
        src = dsf + ".anchor_bak" if os.path.isfile(dsf + ".anchor_bak") else dsf
        lat, lon = int(os.path.basename(dsf)[:3]), int(os.path.basename(dsf)[3:7])
        defs, rows = placements(src, dsftool)
        dems = rasters(elevation_root, lat, lon) if shapes else []
        for i, lo, la, hdg, kind, elev in rows:
            key = defs[i].replace("\\", "/").lower() if i < len(defs) else ""
            skin = shapes.get(("skin", key))
            if skin is not None and kind != "OBJECT_MSL":
                z = sampler(dems, lo, la)(np.array([0.0]), np.array([0.0]))[0]
                cover, hide = TM.quality(skin, (0.0, 0.0), hdg, sampler(dems, lo, la),
                                         sampler(dems, lo, la, fine=True))
                out["rows"].append({
                    "dsf": os.path.basename(dsf), "resource": defs[i], "lat": la, "lon": lo,
                    "heading": hdg, "kind": kind, "plan_m": round(skin.plan_m),
                    "relief_m": round(skin.relief_m, 1), "verdict": "relief skin",
                    "z0": round(float(z), 3), "quality_cover": round(cover, 3),
                    "hideable": bool(hide)})
            shell = shapes.get(("ground", key))
            if shell is not None and kind != "OBJECT_MSL":
                got = GS.verdict(shell.grid, (0.0, 0.0), hdg, sampler(dems, lo, la))
                out["rows"].append({
                    "dsf": os.path.basename(dsf), "resource": defs[i], "lat": la, "lon": lo,
                    "heading": hdg, "kind": kind, "plan_m": round(shell.plan_m),
                    "relief_m": round(shell.relief_m, 1),
                    "photo_spread": round(shell.photo_spread, 3),
                    "verdict": "ground shell " + (got[0] if got else "no DEM"),
                    **({"z0": round(got[1], 3), "follow": round(got[2], 3)} if got else {})})
            shape = shapes.get(key)
            if shape is None:
                continue
            rec = {"dsf": os.path.basename(dsf), "resource": defs[i], "lat": la, "lon": lo,
                   "heading": hdg, "kind": kind, "plan_m": round(shape.plan_m),
                   "relief_m": round(shape.relief_m, 1),
                   "photo_spread": round(shape.photo_spread, 3)}
            if kind == "OBJECT_MSL":
                rec["datum"] = elev
            rec.update(_model_row(shape, hdg, sampler(dems, lo, la),
                                  sampler(dems, lo, la, fine=True),
                                  water_reader(lat, lon, lo, la),
                                  elev if kind == "OBJECT_MSL" else None))
            out["rows"].append(rec)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("packs", nargs="+")
    ap.add_argument("--elevation-root", default=DEFAULT_ELEVATION)
    ap.add_argument("--dsftool", default=os.path.join(HERE, "..", "Utils", "mac", "DSFTool"))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    report = [census(p, a.elevation_root, a.dsftool) for p in a.packs]
    for r in report:
        print(f"== {r['pack']}: gates {r['gates']}")
        for row in r["rows"]:
            wet = row.get("water_rim")
            extra = (f" z0 {row['z0']:.2f} m (rim seat {row['z0_rim']:.2f}, wet rim "
                     f"{'-' if wet is None else f'{wet:.0%}'}) corr {row['corr']:.2f} "
                     f"peak_err {row['peak_err']:.2f} quality {row['quality_cover']:.0%}"
                     f"{' HIDEABLE' if row['hideable'] else ''}"
                     if "corr" in row else
                     f" z0 {row['z0']:.2f} m follow {row['follow']:.0%}" if "follow" in row else
                     f" z0 {row['z0']:.2f} m (its origin's ground) quality "
                     f"{row['quality_cover']:.0%}{' HIDEABLE' if row['hideable'] else ''}"
                     if "z0" in row else "")
            print(f"   {row['verdict']:<14} {row['resource']} @({row['lat']:.5f},{row['lon']:.5f})"
                  f" plan {row['plan_m']} relief {row['relief_m']}{extra}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(report, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
