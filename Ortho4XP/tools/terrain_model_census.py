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
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
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

    def read(xs, ys):
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
            q[i[np.isfinite(v)]] = px <= TM.QUALITY_PIXEL_M
        return q if fine else z
    return read


def candidates(pack_root: str) -> tuple[dict, dict]:
    """``(gate counts, {relative path: Shape})`` over the pack's OBJ8s; a
    ground shell's Shape is keyed ``("ground", path)``."""
    gates = {"objects": 0, "plan": 0, "photo": 0, "candidate": 0, "ground": 0}
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
        if TM._plan_m(g) < TM.SMALL_PLAN_M:
            continue
        gates["plan"] += 1
        tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
        spread = TM.photo_spread(g.vertices, TM._vt_rows(path), tris)
        if spread > TM.MAX_PHOTO_SPREAD:
            continue
        gates["photo"] += 1
        shape = TM.shape_of(path, g)
        if shape is not None:
            gates["candidate"] += 1
            shapes[rel] = shape
    return gates, shapes


def placements(dsf: str, dsftool: str) -> tuple[list[str], list[tuple]]:
    """``(OBJECT_DEF paths, [(def index, lon, lat, heading, kind,
    elevation)])`` of a DSF, dumped in a temporary folder (an ``OBJECT_AGL``
    / ``OBJECT_MSL`` row carries its elevation BEFORE its heading)."""
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
                    t = line.split()
                    elev = None if t[0] == "OBJECT" else float(t[4])
                    hdg = float(t[4] if t[0] == "OBJECT" else t[5])
                    rows.append((int(t[1]), float(t[2]), float(t[3]), hdg, t[0], elev))
    return defs, rows


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
            if shape is None or not TM.admits(shape, kind):
                continue
            rec = {"dsf": os.path.basename(dsf), "resource": defs[i], "lat": la, "lon": lo,
                   "heading": hdg, "kind": kind, "plan_m": round(shape.plan_m),
                   "relief_m": round(shape.relief_m, 1),
                   "photo_spread": round(shape.photo_spread, 3)}
            m = TM.match(shape, (0.0, 0.0), hdg, sampler(dems, lo, la),
                         sampler(dems, lo, la, fine=True))
            rec["verdict"] = "terrain model" if m else "no DEM match"
            if kind == "OBJECT_MSL":
                # #2064: an MSL row is read too; its author's height is kept
                rec["authored_msl"] = elev
            if m:
                rec.update({k: round(v, 3) for k, v in m.items()})
                rec["hideable"] = bool(m["quality_cover"] >= TM.MIN_QUALITY_COVER
                                       and m["corr"] >= TM.MIN_QUALITY_CORR)
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
            msl = (f" [MSL {row['authored_msl']:.2f}"
                   + (f", moves {row['z0'] - row['authored_msl']:+.2f}" if "z0" in row and
                      "corr" in row else "") + "]") if row.get("authored_msl") is not None else ""
            extra = msl + (f" z0 {row['z0']:.2f} m corr {row['corr']:.2f}"
                     f" peak_err {row['peak_err']:.2f}"
                     f" quality {row['quality_cover']:.0%}{' HIDEABLE' if row['hideable'] else ''}"
                     if "corr" in row else
                     f" z0 {row['z0']:.2f} m follow {row['follow']:.0%}" if "z0" in row else "")
            print(f"   {row['verdict']:<14} {row['resource']} @({row['lat']:.5f},{row['lon']:.5f})"
                  f" plan {row['plan_m']} relief {row['relief_m']}{extra}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(report, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
