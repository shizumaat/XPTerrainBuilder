#!/usr/bin/env python3
"""THE TERRAIN SHELLS' RASTER, REPLAYED (#2272 round 2, spec
``docs/specs/terrain-shells-2272-round2.md`` sections 4 and 7).

Which ground does the tile build leave under and around a pack's kept small
terrain shells (``auto_patch_v2.airport.terrain_cut`` THE SHELL)?  Offline,
on a CONTROL ``.alt`` (a tile build's ``Rebuild_cache`` raster: the ground
before any shell cut): the pack's shells from ``tools/terrain_model_census``
(or its ``--census`` JSON), their seat records as ``terrain_model.
seat_records`` writes them, then the production step-1 pass
(``auto_patch.terrain_cut_stage.bake``) on a copy of the raster.  Per arm:

* BODY: 3 m samples of each shell's true footprint deeper than ``BAND_M``
  (the shell's surface seated at or over the sea datum), over 0.05 m;
* BAND: the samples within ``BAND_M``, the share over 0.05 m;
* RIM: 1 m points on each footprint's boundary at its lowest surface --
  the ground there lowered over 0.5 m (share, median, max, against the
  control), and FLOATING more than 0.5 m over the ground on land (control
  ground over :data:`DRY_M` m, the rim seated over the datum) outside
  every other kept plan;
* FEATHER: the postings outside every plan the arm lowers;
* ROADS (``--site NAME=LAT,LON[,R]``): the road-ribbon proxy -- each
  levelled way's stations read on the arm's raster, linear between, the
  worst 1 m step outside every kept plan within ``R`` (150 m) of the site;
* WATER (RULINGS 2026-11-25a (3)): per shell the share of its plan and rim
  seated under the sea datum and its rim over the control's sea.

Arms: ``control`` (no shell), ``S2-S4`` (the cut and the feather, the rim
fill off), ``lane`` (S2-S5, the production pass).  ``--hold`` also replays
THE HOLD (S6) on a mesh of the lane raster's postings round each shell plus
its outline and body rings (unrefined: the counts are a lower bound of the
mesh step's density; the wall time is its order).  Read-only.

    venv/bin/python tools/terrain_shell_replay.py ICAO --tile LAT LON
        [--pack DIR] [--census JSON] [--cache DIR] [--patch P.osm]
        [--site NAME=LAT,LON[,R] ...] [--hold] [--json OUT]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import sys
import time
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

__all__ = ["shell_records", "Shells", "measure", "water_report", "run", "main"]

DATA = "/Users/noah/XPTerrainBuilderData"
#: the control ground over this is land (m)
DRY_M = 0.3
#: judged over the shell / floating under the rim (m)
OVER_M, FLOAT_M = 0.05, 0.5
#: the edge band (``terrain_cut.BAND_M``)
BAND_M = 10.0
#: sample spacing in the footprint, along the rim (m)
SAMPLE_M, RIM_STEP_M = 3.0, 1.0


def _tile_name(lat: int, lon: int) -> str:
    return f"{lat:+03d}{lon:+04d}"


def shell_records(rows: list[dict], pack_root: str, icao: str) -> list[dict]:
    """The seat records ``terrain_model.seat_records`` writes for the
    census rows a kept shell reads as (``verdict`` ``terrain shell``)."""
    from auto_patch_v2.airport import terrain_model as TM
    out = []
    for k, r in enumerate(rows):
        if r.get("verdict") != "terrain shell":
            continue
        out.append({"id": f"shell{k}", "resource": r["resource"], "seat": TM.SEAT,
                    "elevation": float(r["z0"]), "icao": icao,
                    "cut": {"file": os.path.join(pack_root, r["resource"]), "lat": r["lat"],
                            "lon": r["lon"], "heading": float(r["heading"]), "fill": True,
                            "shell": True}})
    return out


class Shells:
    """The shells' true footprints (the union of their plan triangles) in
    one transverse-Mercator frame, their surfaces and their rims."""

    def __init__(self, records: list[dict]):
        import shapely
        from auto_patch_v2.airport import terrain_cut as TC
        from auto_patch_v2.airport import terrain_model as TM
        lat0 = float(np.mean([r["cut"]["lat"] for r in records]))
        lon0 = float(np.mean([r["cut"]["lon"] for r in records]))
        self.to_xy, self.to_ll = TC.projector(lat0, lon0)
        self.items = []
        for rec in records:
            tris = TM.plan_solid(rec["cut"]["file"])
            if tris is None:
                continue
            ax, ay = (float(v) for v in self.to_xy(rec["cut"]["lon"], rec["cut"]["lat"]))
            h = math.radians(rec["cut"]["heading"])
            s, c = math.sin(h), math.cos(h)
            x, z = tris[:, :, 0], tris[:, :, 2]
            e, n = ax + x * c - z * s, ay - (x * s + z * c)
            ps = shapely.polygons(np.stack([e, n], -1))
            ps = ps[shapely.area(ps) > 1e-6]
            plan = shapely.union_all(shapely.make_valid(ps))
            name = os.path.splitext(os.path.basename(rec["resource"]))[0].split("_")[-1]
            self.items.append({"name": name, "rec": rec, "plan": plan,
                               "tri": np.stack([e, n, tris[:, :, 1]], -1)})
        self.union = shapely.union_all([i["plan"] for i in self.items])

    @staticmethod
    def surface(tri: np.ndarray, x: np.ndarray, y: np.ndarray, highest: bool = True,
                tol: float = 1e-6) -> np.ndarray:
        """The solid's highest (lowest) authored ``y`` at frame points."""
        a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        ok = np.abs(d) > 1e-9
        a, b, c, d = a[ok], b[ok], c[ok], d[ok]
        out = np.full(len(x), np.nan)
        for s in range(0, len(x), 300):
            xx, yy = x[s:s + 300, None], y[s:s + 300, None]
            l0 = ((b[:, 1] - c[:, 1]) * (xx - c[:, 0]) + (c[:, 0] - b[:, 0]) * (yy - c[:, 1])) / d
            l1 = ((c[:, 1] - a[:, 1]) * (xx - c[:, 0]) + (a[:, 0] - c[:, 0]) * (yy - c[:, 1])) / d
            l2 = 1 - l0 - l1
            ins = (l0 >= -tol) & (l1 >= -tol) & (l2 >= -tol)
            w = np.clip(np.stack([l0, l1, l2]), 0, 1)
            v = (w[0] * a[:, 2] + w[1] * b[:, 2] + w[2] * c[:, 2]) / np.maximum(w.sum(0), 1e-12)
            v = np.where(ins, v, -np.inf if highest else np.inf)
            v = v.max(1) if highest else v.min(1)
            out[s:s + 300] = np.where(np.isfinite(v), v, np.nan)
        return out

    def samples(self) -> None:
        """Body / band samples and rim points of every shell."""
        import shapely
        for it in self.items:
            z0 = it["rec"]["elevation"]
            u = it["plan"]
            w, s, e, n = u.bounds
            gx, gy = np.meshgrid(np.arange(w, e, SAMPLE_M), np.arange(s, n, SAMPLE_M))
            pts = shapely.points(np.c_[gx.ravel(), gy.ravel()])
            m = shapely.contains(u, pts)
            gx, gy = gx.ravel()[m], gy.ravel()[m]
            depth = shapely.distance(u.boundary, shapely.points(np.c_[gx, gy]))
            top = z0 + self.surface(it["tri"], gx, gy)
            ok = np.isfinite(top) & (top >= 0.0)
            it["s"] = (gx[ok], gy[ok], top[ok], depth[ok])
            rings = [r for g in getattr(u, "geoms", [u]) for r in (g.exterior, *g.interiors)]
            p = np.concatenate([np.array([r.interpolate(t).coords[0] for t in
                                          np.arange(0.0, r.length, RIM_STEP_M)]) for r in rings])
            it["rim"] = (p, z0 + self.surface(it["tri"], p[:, 0], p[:, 1], False, 0.02))


class Raster:
    """A control ``.alt`` (or any array ``base`` in its frame ``f``);
    bilinear reads at frame points."""

    def __init__(self, base: np.ndarray, f: dict, to_ll):
        self.base, self.f, self.to_ll = base, f, to_ll
        self.dx = (f["x1"] - f["x0"]) / (f["nxdem"] - 1)
        self.dy = (f["y1"] - f["y0"]) / (f["nydem"] - 1)

    @classmethod
    def read(cls, cache: str, tile: str, to_ll) -> "Raster":
        with open(os.path.join(cache, f"Data{tile}.alt.frame.json"), encoding="utf-8") as fh:
            f = json.load(fh)
        base = np.memmap(os.path.join(cache, f"Data{tile}.alt"), np.float32, "r").reshape(
            int(f["nydem"]), int(f["nxdem"]))
        return cls(base, f, to_ll)

    def at(self, a, x, y):
        lo, la = self.to_ll(x, y)
        f = self.f
        fx = (lo - f["tile_lon"] - f["x0"]) / self.dx
        fy = (f["tile_lat"] + f["y1"] - la) / self.dy
        c, r = np.floor(fx).astype(int), np.floor(fy).astype(int)
        tx, ty = fx - c, fy - r
        return (a[r, c] * (1 - tx) * (1 - ty) + a[r, c + 1] * tx * (1 - ty)
                + a[r + 1, c] * (1 - tx) * ty + a[r + 1, c + 1] * tx * ty)

    def tile(self, a):
        f = self.f
        return types.SimpleNamespace(lat=int(f["tile_lat"]), lon=int(f["tile_lon"]), iterate=0,
                                     build_dir="", dem=types.SimpleNamespace(
                                         x0=f["x0"], x1=f["x1"], y0=f["y0"], y1=f["y1"],
                                         alt_dem=a))


def _patch_area(patch: str | None, lat: int, lon: int):
    """The patch's concave hull, tile-relative degrees (a proxy of the
    vector step's ``patches_area``)."""
    import re

    import shapely
    if not patch or not os.path.isfile(patch):
        return None
    with open(patch, encoding="utf-8") as fh:
        txt = fh.read()
    pn = np.array([(float(a), float(b)) for a, b in
                   re.findall(r"lat='([-\d.]+)' lon='([-\d.]+)'", txt)])
    if not len(pn):
        return None
    return shapely.concave_hull(shapely.multipoints(np.c_[pn[:, 1] - lon, pn[:, 0] - lat]),
                                ratio=0.15)


def _bake(ras: Raster, records, patch_area, fill: bool) -> tuple[np.ndarray, float, str]:
    """One arm: the production step-1 pass on a copy of the control."""
    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.airport import terrain_fill as TF
    a = np.array(ras.base)
    tile = ras.tile(a)
    orig = TF.rim_fill
    if not fill:
        TF.rim_fill = lambda *a_, **k: {"supports": 0, "raised": 0, "unserved": 0}
    buf = io.StringIO()
    t = time.perf_counter()
    try:
        with contextlib.redirect_stdout(buf):
            TCS.bake(tile, [dict(r, cut=dict(r["cut"])) for r in records], patch_area)
    finally:
        TF.rim_fill = orig
    return tile.dem.alt_dem, time.perf_counter() - t, buf.getvalue()


def _roads(path: str, sites: dict, sh: Shells) -> dict:
    """The levelled ways within each site's radius (frame metres)."""
    import shapely
    with open(path, encoding="utf-8") as fh:
        ways = json.load(fh)["ways"]
    out = {}
    for name, (la, lo, rad) in sites.items():
        cx, cy = (float(v) for v in sh.to_xy(lo, la))
        circ = shapely.Point(cx, cy).buffer(rad)
        got = []
        for w in ways:
            wl, wo = np.asarray(w["lat"]), np.asarray(w["lon"])
            if len(wl) < 2 or abs(wl.mean() - la) > 0.01 or abs(wo.mean() - lo) > 0.01:
                continue
            st = np.c_[sh.to_xy(wo, wl)]
            part = shapely.LineString(st).intersection(circ)
            for g in getattr(part, "geoms", [part]):
                if g.geom_type == "LineString" and g.length > 2:
                    got.append((g, st))
        out[name] = got
    return out


def _profile(ras: Raster, a, g, st):
    """The ribbon proxy along ``g``: ``st``'s stations read on ``a``,
    linear between, every metre."""
    import shapely
    line = shapely.LineString(st)
    sz = ras.at(a, st[:, 0], st[:, 1])
    ss = shapely.line_locate_point(line, shapely.points(st))
    p = np.array([g.interpolate(v).coords[0] for v in np.arange(0, g.length, 1.0)])
    s = shapely.line_locate_point(line, shapely.points(p))
    o = np.argsort(ss)
    return p, np.interp(s, ss[o], sz[o])


def measure(ras: Raster, sh: Shells, a, roads: dict | None = None) -> dict:
    """The section-4 row of one arm's raster ``a`` (module doc)."""
    import shapely
    n_in = o_in = n_b = o_b = 0
    worst = 0.0
    per = {}
    for it in sh.items:
        gx, gy, top, depth = it["s"]
        d = ras.at(a, gx, gy) - top
        inner = depth > BAND_M
        n_in += int(inner.sum())
        o_in += int((d[inner] > OVER_M).sum())
        n_b += int((~inner).sum())
        o_b += int((d[~inner] > OVER_M).sum())
        if inner.any():
            worst = max(worst, float(d[inner].max()))
        per[it["name"]] = {"body_over": int((d[inner] > OVER_M).sum()),
                           "band_over_pct": round(100.0 * float(np.mean(d[~inner] > OVER_M)), 1)
                           if (~inner).any() else None}
    lowered, floating, rim_n = [np.zeros(0)], 0, 0
    for it in sh.items:
        p, z = it["rim"]
        g0 = ras.at(ras.base, p[:, 0], p[:, 1])
        g = ras.at(a, p[:, 0], p[:, 1])
        others = shapely.union_all([o["plan"] for o in sh.items if o is not it])
        inside = (shapely.contains(others, shapely.points(p)) if not others.is_empty
                  else np.zeros(len(p), bool))
        land = np.isfinite(z) & (z >= 0.0) & (g0 > DRY_M) & ~inside
        rim_n += int(land.sum())
        fl = int((land & (g - z < -FLOAT_M)).sum())
        floating += fl
        lowered.append((g - g0)[land])
        per[it["name"]]["rim_float_m"] = fl
    low = np.concatenate(lowered)
    down = low < -FLOAT_M
    out = {"body_over": o_in, "body_n": n_in, "body_worst_m": round(worst, 2),
           "band_over_pct": round(100.0 * o_b / max(n_b, 1), 1),
           "rim_land_m": rim_n, "rim_float_m": floating,
           "rim_lowered_pct": round(100.0 * float(down.mean()), 1) if len(low) else 0.0,
           "rim_lowered_median_m": round(float(-np.median(low[down])), 2) if down.any() else 0.0,
           "rim_lowered_max_m": round(float(max(-low.min(), 0.0)), 2) if len(low) else 0.0,
           "per_shell": per}
    if roads:
        out["roads"] = {}
        for name, ways in roads.items():
            w = 0.0
            for g, st in ways:
                p, zz = _profile(ras, a, g, st)
                vis = ~shapely.contains(sh.union, shapely.points(p))
                both = vis[1:] & vis[:-1]
                if both.any():
                    w = max(w, float(np.abs(np.diff(zz))[both].max()))
            out["roads"][name] = round(w, 2)
    return out


def _feather_stats(ras: Raster, sh: Shells, a) -> dict:
    """The postings outside every plan the arm lowers (``a`` vs control)."""
    import shapely
    d = a - ras.base
    rr, cc = np.nonzero(d < -0.05)
    if not len(rr):
        return {"postings": 0}
    f = ras.f
    lon = f["tile_lon"] + f["x0"] + cc * ras.dx
    lat = f["tile_lat"] + f["y1"] - rr * ras.dy
    x, y = sh.to_xy(lon, lat)
    out = ~shapely.contains(sh.union, shapely.points(np.c_[x, y]))
    v = -d[rr[out], cc[out]]
    cell_m2 = (ras.dx * 111_320.0 * math.cos(math.radians(f["tile_lat"] + 0.5))
               * ras.dy * 111_320.0)
    if not len(v):
        return {"postings": 0}
    return {"postings": int(out.sum()), "ha": round(float(out.sum()) * cell_m2 / 1e4, 1),
            "median_m": round(float(np.median(v)), 2),
            "p95_m": round(float(np.percentile(v, 95)), 2), "max_m": round(float(v.max()), 2)}


def water_report(ras: Raster, sh: Shells) -> dict:
    """RULINGS 2026-11-25a (3): per shell, what part is seated under the
    sea datum (plan share, rim metres) and how much rim lies over the
    control's sea (ground at or under :data:`DRY_M`)."""
    import shapely
    out = {}
    for it in sh.items:
        u, z0 = it["plan"], it["rec"]["elevation"]
        w, s, e, n = u.bounds
        gx, gy = np.meshgrid(np.arange(w, e, 2.0), np.arange(s, n, 2.0))
        m = shapely.contains(u, shapely.points(np.c_[gx.ravel(), gy.ravel()]))
        top = z0 + sh.surface(it["tri"], gx.ravel()[m], gy.ravel()[m])
        p, z = it["rim"]
        g0 = ras.at(ras.base, p[:, 0], p[:, 1])
        out[it["name"]] = {"plan_under_datum_pct": round(100.0 * float(np.mean(top < 0.0)), 1),
                           "rim_m": int(len(p)), "rim_under_datum_m": int(np.sum(z < 0.0)),
                           "rim_over_sea_m": int(np.sum(g0 <= DRY_M))}
    return out


def _hold_replay(ras: Raster, records, a) -> dict:
    """THE HOLD (S6) on a Delaunay mesh of the lane raster's postings in
    each plan box plus the outline and body rings (module doc)."""
    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.airport import terrain_cut as TC
    from scipy.spatial import Delaunay
    f = ras.f
    pts = []
    for rec in records:
        fit = TCS._fit(rec)
        w, s, e, n = TC.plan_box(fit, TC.projector(rec["cut"]["lat"], rec["cut"]["lon"])[1])
        c0 = int((w - f["tile_lon"] - f["x0"]) / ras.dx)
        c1 = int((e - f["tile_lon"] - f["x0"]) / ras.dx) + 1
        r0 = int((f["tile_lat"] + f["y1"] - n) / ras.dy)
        r1 = int((f["tile_lat"] + f["y1"] - s) / ras.dy) + 1
        cc, rr = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
        pts.append(np.c_[f["x0"] + cc.ravel() * ras.dx, f["y1"] - rr.ravel() * ras.dy])
        for ring in TCS._outline(rec):
            pts.append(np.asarray(ring, float) - np.array([f["tile_lon"], f["tile_lat"]]))
    xy = np.unique(np.round(np.concatenate(pts), 10), axis=0)
    fx, fy = (xy[:, 0] - f["x0"]) / ras.dx, (f["y1"] - xy[:, 1]) / ras.dy
    c, r = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = fx - c, fy - r
    z = (a[r, c] * (1 - tx) * (1 - ty) + a[r, c + 1] * tx * (1 - ty)
         + a[r + 1, c] * (1 - tx) * ty + a[r + 1, c + 1] * tx * ty)
    v = np.zeros((len(xy), 6))
    v[:, 0], v[:, 1], v[:, 2], v[:, 5] = xy[:, 0], xy[:, 1], z, z
    v = v.ravel()
    tris = Delaunay(xy * np.array([math.cos(math.radians(f["tile_lat"] + 0.5)), 1.0])).simplices
    tile = types.SimpleNamespace(lat=int(f["tile_lat"]), lon=int(f["tile_lon"]))
    orig = TCS._held_records
    TCS._held_records = lambda t: TCS._held(records)
    t = time.perf_counter()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            got = TCS.hold(tile, v, tris, (), ())
    finally:
        TCS._held_records = orig
    return {"seconds": round(time.perf_counter() - t, 2), "vertices": int(len(xy)),
            "triangles": int(len(tris)),
            "samples": int(sum(g["samples"] for g in got.values())),
            "unresolved": int(sum(g["unresolved"] for g in got.values())),
            "lowered": int(sum(g["lowered"] for g in got.values())),
            "worst_m": round(max([g["worst_m"] for g in got.values()] or [0.0]), 2)}


def _sites(specs) -> dict:
    out = {}
    for s in specs or ():
        name, vals = s.split("=", 1)
        q = [float(v) for v in vals.split(",")]
        out[name] = (q[0], q[1], q[2] if len(q) > 2 else 150.0)
    return out


def run(args) -> dict:
    lat, lon = args.tile
    tile = _tile_name(lat, lon)
    blk = _tile_name(int(math.floor(lat / 10) * 10), int(math.floor(lon / 10) * 10))
    patch_dir = os.path.join(DATA, "Patches", blk, tile)
    pack = args.pack
    if pack is None:
        with open(os.path.join(patch_dir, f"o4_v2_rebake_{args.icao}.json"),
                  encoding="utf-8") as fh:
            pack = json.load(fh)["pack_root"]
    if args.census and os.path.isfile(args.census):
        with open(args.census, encoding="utf-8") as fh:
            rows = json.load(fh)[0]["rows"]
    else:
        import terrain_model_census as TMC
        rows = TMC.census(pack, TMC.DEFAULT_ELEVATION,
                          os.path.join(HERE, "..", "Utils", "mac", "DSFTool"))["rows"]
    records = shell_records(rows, pack, args.icao)
    if not records:
        raise SystemExit(f"NOT MEASURED: no terrain shell in {pack}")
    sh = Shells(records)
    sh.samples()
    ras = Raster.read(args.cache or os.path.join(DATA, "Rebuild_cache", f"zOrtho4XP_{tile}"),
                      tile, sh.to_ll)
    area = _patch_area(args.patch or os.path.join(patch_dir, f"{args.icao}_auto.patch.osm"),
                       lat, lon)
    sites = _sites(args.site)
    cache = args.cache or os.path.join(DATA, "Rebuild_cache", f"zOrtho4XP_{tile}")
    roads = _roads(os.path.join(cache, "o4_levelled_roads.json"), sites, sh) if sites else None
    rep = {"icao": args.icao, "tile": tile, "shells": [i["name"] for i in sh.items],
           "water": water_report(ras, sh), "arms": {"control": measure(ras, sh, ras.base, roads)}}
    for arm, fill in (("S2-S4", False), ("lane", True)):
        a, secs, log = _bake(ras, records, area, fill)
        rep["arms"][arm] = dict(measure(ras, sh, a, roads), step1_s=round(secs, 2),
                                feather=_feather_stats(ras, sh, a))
        if arm == "lane":
            rep["log"] = [ln.strip() for ln in log.splitlines()
                          if "feathered" in ln or "filled" in ln]
            if args.hold:
                rep["hold"] = _hold_replay(ras, records, a)
    return rep


def print_report(rep: dict) -> None:
    print(f"TERRAIN SHELL REPLAY {rep['icao']} {rep['tile']}: {len(rep['shells'])} shells")
    print("arm | body over (of n), worst | band over | rim lowered >0.5 (median, max) | "
          "rim float >0.5 m on land (of m) | roads")
    for arm, m in rep["arms"].items():
        roads = " / ".join(f"{k} {v:.2f}" for k, v in (m.get("roads") or {}).items())
        print(f"{arm:8s} | {m['body_over']} ({m['body_n']}), {m['body_worst_m']} m | "
              f"{m['band_over_pct']} % | {m['rim_lowered_pct']} % ({m['rim_lowered_median_m']}, "
              f"{m['rim_lowered_max_m']} m) | {m['rim_float_m']} ({m['rim_land_m']}) | {roads}"
              + (f" | step1 {m['step1_s']} s; feather {m['feather']}" if "step1_s" in m else ""))
    print("per shell (lane): body over / band over % / rim float m")
    for k, v in rep["arms"]["lane"]["per_shell"].items():
        print(f"   {k:18s} {v['body_over']:5d} {v['band_over_pct']} {v['rim_float_m']}")
    print("water (RULINGS 2026-11-25a (3)): plan under datum % / rim under datum m / "
          "rim over sea m (of rim m)")
    for k, v in rep["water"].items():
        print(f"   {k:18s} {v['plan_under_datum_pct']:5.1f} {v['rim_under_datum_m']:5d} "
              f"{v['rim_over_sea_m']:5d} ({v['rim_m']})")
    if "hold" in rep:
        print(f"hold (S6, unrefined posting mesh): {rep['hold']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("--tile", nargs=2, type=int, required=True, metavar=("LAT", "LON"))
    ap.add_argument("--pack", default=None, help="pack root (default: the rebake plan's)")
    ap.add_argument("--census", default=None, help="a terrain_model_census --json")
    ap.add_argument("--cache", default=None, help="the control Rebuild_cache tile folder")
    ap.add_argument("--patch", default=None, help="the patch (default: the data repo's)")
    ap.add_argument("--site", action="append", help="NAME=LAT,LON[,R] (road proxy)")
    ap.add_argument("--hold", action="store_true", help="also replay the hold (S6)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    rep = run(args)
    print_report(rep)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
