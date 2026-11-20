"""LIBRARY of ``tools/drawn_site.py`` (owner RULINGS 2026-11-20g; spec
``Ortho4XP/docs/specs/elevated-clearance-20g-spec.md``): ``drawn_site
--crossings`` -- THE ELEVATED CROSSINGS X-PLANE DRAWS at each ``--site``.

Every placement of the given pack(s) whose solids reach a site (the WRITTEN
DSF rows, placed as X-Plane places them: ``drawn_site.select`` /
``row_base``) is read over every mapped road and rail of the site's OSM
feeds (``big_roads``, ``airport_small_roads``) through the engine's ONE
crossing read (``auto_patch_v2.airport.elevated_crossing``): each
carriageway cell (1 m) a row's lowest static solid face stands over, at
least ``OVER_GROUND_M`` over the DRAWN mesh, is a crossing cell; per row
and way the LEAST clearance (soffit - drawn mesh), its median, the cells,
the class minimum (4.2 m over a small road, 5.0 m over every other road and
rail) and the shortfall.  A row whose lowest face stands on the road is a
building the road enters, never a crossing.  Read-only (temp dumps).

    venv/bin/python tools/drawn_site.py --crossings --pack PACK \\
        --site NAME=LAT,LON,RADIUS_M [--tile-dir DIR] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import tempfile

import numpy as np

__all__ = ["site_ways", "site_crossings", "print_crossings", "main"]

#: the OSM feeds a mapped road or rail is read from
FEEDS = ("big_roads", "airport_small_roads")


def site_ways(osm_root: str, site) -> list:
    """The mapped ways of the site's tile neighbourhood within its radius,
    each once: a way two tiles' extracts both carry (their ids are
    namespaced per tile) is read by its geometry."""
    from auto_patch_v2.airport import osm
    from auto_patch_v2.airport.elevated_crossing import crossable
    r_deg = site.radius_m / 111320.0 + 0.005
    seen: dict = {}
    for feed in FEEDS:
        for w in osm.load_feed(osm_root, feed, site.lat, site.lon, radius_deg=r_deg).ways:
            key = tuple((round(a, 7), round(b, 7)) for a, b in w.points)
            if crossable(w.tags) and key not in seen:
                seen[key] = w
    return list(seen.values())


def origin_of(q: dict) -> str:
    """``pack`` (the pack's own file), ``generated`` (this engine's deck or
    road object, written into the pack) or ``library`` (a resource the
    pack does not hold)."""
    phys = os.path.abspath(q["phys"])
    if not phys.startswith(os.path.abspath(q["root"]) + os.sep):
        return "library"
    return "generated" if "o4_generated" in phys.replace(os.sep, "/") else "pack"


def site_crossings(site, picked, mesh, ways, law, step: float) -> list[dict]:
    """Every crossing of the ``picked`` rows over ``ways`` at ``site``."""
    from auto_patch_v2.airport.elevated_crossing import carriageways, read_crossings
    from drawn_site import Frame, placed_vertices, row_base
    fr = Frame(site.lat, site.lon)

    def xy_of(w):
        e, n = fr.enter([p[0] for p in w.points], [p[1] for p in w.points])
        return list(zip(np.asarray(e).tolist(), np.asarray(n).tolist(), strict=True))
    cways = carriageways(ways, xy_of, law)

    def ground(xs, ys):
        la, lo = fr.leave(xs, ys)
        return mesh.z(la, lo)

    def owners():
        for q in picked:
            p, g = q["p"], q["g"]
            e0, n0 = fr.enter(p.lat, p.lon)
            base = row_base(p, float(mesh.z([p.lat], [p.lon])[0]))
            if not math.isfinite(base):
                continue
            V = placed_vertices(g, float(e0), float(n0), p.heading_deg, base)
            T = np.asarray(g.solid)
            if g.animated.shape[0]:
                T = T[~np.asarray(g.animated, dtype=bool)]
            yield (q["tile"], q["row"], p.def_path, origin_of(q)), V[T], None
    out = []
    for c in read_crossings(owners(), cways, ground, step=step):
        la, lo = fr.leave(*c.at)
        tile, row, res, origin = c.owner
        out.append({"tile": tile, "row": row, "resource": res, "origin": origin,
                    "way": c.way, "kind": c.kind,
                    "need_m": c.need_m, "cells": c.cells, "least_m": c.least_m,
                    "p50_m": c.p50_m, "short_m": round(c.short_m, 3),
                    "soffit_z": c.soffit_z, "ground_z": c.ground_z,
                    "lat": round(float(la), 7), "lon": round(float(lo), 7)})
    return sorted(out, key=lambda r: (-r["short_m"], r["resource"], r["way"]))


def print_crossings(site_rec: dict, top: int) -> None:
    """One line per crossing, worst shortfall first, and the site's count."""
    rows = site_rec.get("crossings") or []
    pack = [r for r in rows if r.get("origin", "pack") == "pack"]
    short = [r for r in pack if r["short_m"] > 0.0]
    print(f"CROSSINGS {site_rec['name']}: {len(pack)} pack structure~way crossing(s), "
          f"{len(short)} short of the class minimum ({len(rows) - len(pack)} generated / "
          f"library rows listed apart)")
    for r in rows[:top]:
        tag = "" if r.get("origin", "pack") == "pack" else f"[{r['origin']}] "
        print(f"  {tag}{r['resource']} (obj{r['row']}) over {r['kind']} {r['way']}: least "
              f"{r['least_m']:+.2f} m (p50 {r['p50_m']:+.2f}, {r['cells']} cells) need "
              f"{r['need_m']:.1f} -> {'SHORT %.2f' % r['short_m'] if r['short_m'] else 'ok'}"
              f" @{r['lat']:.6f},{r['lon']:.6f} soffit {r['soffit_z']:.2f} ground "
              f"{r['ground_z']:.2f}")


def main(argv) -> int:
    from auto_patch_v2.law import Law
    from drawn_site import (DrawnMesh, Frame, Resources, dsftool, mesh_box, pack_rows,
                            parse_site, select, tile_of)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--crossings", action="store_true")
    ap.add_argument("--pack", action="append", default=[])
    ap.add_argument("--site", action="append", default=[], help="NAME=LAT,LON[,RADIUS_M]")
    ap.add_argument("--radius", type=float, default=600.0)
    ap.add_argument("--search-m", type=float, default=3000.0)
    ap.add_argument("--custom-scenery", default=None)
    ap.add_argument("--mod-cache", default=None)
    ap.add_argument("--tile-dsf", default=None)
    ap.add_argument("--tile-dir", action="append", default=[])
    ap.add_argument("--osm-root", default=None, help="default: the engine's OSM_data")
    ap.add_argument("--step", type=float, default=1.0, help="carriageway grid, m")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    import O4_Config_Utils  # noqa: F401
    import O4_File_Names as FNAMES
    if args.custom_scenery is None:
        from auto_patch_v2.planar.__main__ import _cfg_value
        args.custom_scenery = _cfg_value("custom_scenery_dir") \
            or os.path.expanduser("~/X-Plane 12/Custom Scenery")
    args.mod_cache = args.mod_cache or FNAMES.airport_mod_cache_root()
    osm_root = args.osm_root or FNAMES.OSM_dir
    from drawn_site_agp import pack_dir
    packs = [pack_dir(p, args.custom_scenery) for p in args.pack]
    sites = [parse_site(s, args.radius) for s in args.site]
    if not sites or not packs:
        ap.error("--crossings wants --pack and --site")
    law = Law.load()
    tool = dsftool()
    work = tempfile.mkdtemp(prefix="drawn_crossings_")
    try:
        res = Resources(os.path.dirname(args.custom_scenery.rstrip("/")), args.mod_cache)
        tiles = {tile_of(s.lat + a, s.lon + b) for s in sites
                 for a in (-0.03, 0.0, 0.03) for b in (-0.04, 0.0, 0.04)}
        rows = [r for pk in packs for r in pack_rows(pk, tiles, work, tool)]
        frames = {s: Frame(s.lat, s.lon) for s in sites}
        picked = select(rows, sites, [], frames, res, args.search_m)
        mesh = DrawnMesh(mesh_box(sites, picked), args.custom_scenery, tool, args.tile_dsf,
                         args.cache, args.tile_dir)
        rep = {"mesh": mesh.sources, "packs": packs, "sites": []}
        for s in sites:
            ways = site_ways(osm_root, s)
            rec = {"name": s.name, "lat": s.lat, "lon": s.lon, "radius_m": s.radius_m,
                   "ways": len(ways),
                   "crossings": site_crossings(s, [q for q in picked if s in q["sites"]],
                                               mesh, ways, law, args.step)}
            rep["sites"].append(rec)
            print_crossings(rec, args.top)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0
