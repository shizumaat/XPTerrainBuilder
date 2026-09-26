#!/usr/bin/env python3
"""THE PACK STAGE, TIMED — ``load -> read_objects -> partition_pack ->
groups -> clusters`` for one airport, through the BUILD'S OWN
``pipeline/build.pack_stage`` (never a second spelling of the drive site),
N times, each run in a FRESH interpreter so every run is cold in-process
and reports its own max RSS.

Spec ``pack-read-once-fast-spec.md`` §C (MEANWHILE-CAPTURE NOTE): the
throwaway ``instr_groups.py`` arm of lane ``packreadprofile`` was on its
SECOND use, so slice S2 promotes it here (issue #27).

    venv/bin/python tools/pack_stage_profile.py TNCM [--runs 3]
        [--cache off|on] [--json OUT] [--site LAT,LON]

``--cache off`` (default) hands the stage NO mod-cache root, so every run
reads and partitions the pack (the COLD stage); ``--cache on`` uses the
lane's mod-cache overlay (``O4_AIRPORT_MOD_CACHE_DIR``, armed here by the
harness redirect): the first run MISSES and WRITES, the rest HIT — the
REBUILD stage.  Timing law (CLAUDE.md): a single run swings ±25 %; quote
the MEDIAN of ``--runs`` >= 3, never one run per side, and never through
the run ledger.

Every run arms the harness's shared-repo protection (the ONE arming
composition, ``build_airport.arm_shared_repo_protection``) and fails if
the shared repo was written.  It builds no patch, prices no law and counts
no defects.  Twin: ``tests/auto_patch_v2/test_v2packcache.py``.
"""
from __future__ import annotations

import argparse
import dataclasses as _dc
import json
import os
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if os.environ.get("O4_PACK_STAGE_TREE"):      # --tree, re-read in the child
    ROOT = Path(os.environ["O4_PACK_STAGE_TREE"]).resolve()

#: The per-run fields the report carries, in print order.
WALL_KEYS = ("load", "read", "partition", "groups", "clusters", "stage")
COUNT_KEYS = ("placements", "members", "parts", "contacts", "pairs_tested",
              "abutments", "scatter_members", "scatter_parts")
GROUP_KEYS = ("bodies", "groups", "infeasible")


def site_report(clusters, lat: float, lon: float, min_m2: float = 0.0,
                pads=None, site_xy=None) -> dict:
    """THE CLUSTER AT A SITE (issue #69): the cluster whose outline (the
    union of its ``rings``, ``(lat, lon)``) contains ``(lat, lon)`` — else
    the nearest one — with its outline area (m², local equirectangular
    metres about the site), member / body counts, and the airport's
    cluster count and how many clear ``min_m2`` (the cluster pad plane).
    ``pads`` (``geom.cluster_outlines``'s ``[(pad id, cluster, polygon)]``
    in the planar metres, ``site_xy`` the site there) adds the PAD reading
    the classify mint starts from: the pad count and the LARGEST pad
    within 1 m of the site — the #69 terminal piece.
    Prices nothing; a read of the partition the stage returned."""
    import math
    import shapely
    from shapely.geometry import Point, Polygon
    kx = 111_320.0 * math.cos(math.radians(lat))
    ky = 110_574.0

    def poly(r):
        pts = [((lo - lon) * kx, (la - lat) * ky) for la, lo in r]
        if len(pts) < 3:
            return None
        g = Polygon(pts)
        return g if g.is_valid else g.buffer(0)

    site = Point(0.0, 0.0)
    best = None
    for c in clusters:
        ps = [g for g in (poly(r) for r in (getattr(c, "rings", ()) or ())) if g is not None and not g.is_empty]
        if not ps:
            continue
        u = shapely.union_all(ps)
        d = 0.0 if u.contains(site) else float(u.distance(site))
        if best is None or d < best[0]:
            best = (d, c, u)
    out = {"clusters": len(clusters),
           "clusters_over_min": sum(1 for c in clusters if c.area_m2 >= min_m2),
           "min_m2": min_m2}
    if best is not None:
        d, c, u = best
        out.update(site_cluster=c.id, site_unit=c.unit, site_dist_m=round(d, 1),
                   site_outline_m2=round(float(u.area), 0),
                   site_area_m2=round(float(c.area_m2), 0),
                   site_members=len(c.members), site_bodies=int(c.bodies),
                   site_walled=int(c.walled))
    if pads is not None and site_xy is not None:
        sp = Point(*site_xy)
        near = [(float(g.area), i, c) for i, c, g in pads if g.distance(sp) <= 1.0]
        out["pads"] = len(pads)
        if near:
            a, i, c = max(near, key=lambda r: r[0])
            out.update(pad_at_site=i, pad_at_site_m2=round(a, 0),
                       pad_members=len(c.members), pad_bodies=int(c.bodies))
    return out


def run_once(icao: str, cache_on: bool, out_dir: Path,
             site: tuple[float, float] | None = None) -> dict:
    """ONE pack stage, in this process.  Returns the run record."""
    for p in (ROOT / "tools", ROOT / "tools" / "harness"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from build_airport import (arm_shared_repo_protection, report_guard_churn,
                               resolve_tile_for)
    guard, _redir = arm_shared_repo_protection(ROOT, out_dir, f"packstage_{icao}")
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.law import Law
    try:
        from auto_patch_v2.pipeline.build import pack_stage
    except ImportError:                  # a BASE tree predating pack_stage
        pack_stage = _legacy_pack_stage
        if cache_on:
            raise SystemExit("--cache on needs a tree with pipeline/build.pack_stage")
    from auto_patch_v2.planar.__main__ import default_inputs
    law = Law.for_airport(icao)
    inputs = default_inputs()
    try:
        from auto_patch.engine_v2 import fresh_pack_dump
        tl = resolve_tile_for(icao, ROOT)
        d = fresh_pack_dump(inputs.xplane_root, icao, *tl) if tl else None
        if d:
            inputs = _dc.replace(inputs, dsf_dump_path=d)
    except Exception as exc:                       # the loader refuses loudly
        print(f"[{icao}] pack dump not refreshed: {exc}", flush=True)
    if not cache_on:
        inputs = _dc.replace(inputs, mod_cache_root=None)
    lines: list[str] = []
    with guard:
        t = time.perf_counter()
        airport, lrep = load_with_report(icao, inputs, law)
        t_load = time.perf_counter() - t
        ps = pack_stage(icao, airport, law, inputs, lrep, out=lines.append)
    report_guard_churn(guard)
    if guard.blocked:
        raise SystemExit(f"[{icao}] REFUSED: the shared repo was written: {guard.blocked}")
    part, grp = ps["partition"], ps["groups"]
    w = dict(ps["wall"])
    rec = {
        "icao": icao, "cache": ps["cache"],
        "wall": {"load": round(t_load, 2), "read": round(w.get("read", 0.0), 2),
                 "partition": round(w.get("partition", 0.0), 2),
                 "groups": round(w.get("groups", 0.0), 2),
                 "clusters": round(w.get("clusters", 0.0), 2),
                 "stage": round(w["total"], 2)},
        "counts": {k: int(part.counts.get(k, 0)) for k in COUNT_KEYS},
        "groups": {k: int(grp.counts.get(k, 0)) for k in GROUP_KEYS},
        "clusters": len(ps["clusters"]),
        "max_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2),
        "cache_lines": [ln.strip() for ln in lines if "[partition] cache" in ln],
    }
    if site is not None:
        try:
            from auto_patch_v2.planar.cluster import cluster_min_m2
            mn = float(cluster_min_m2(law))
        except Exception:
            mn = 0.0
        pads = sxy = None
        try:
            from auto_patch_v2.geom import cluster_outlines
            st = law.tables.structures.placement
            to_xy = ps["airport"].frame.entry()
            pads, _c = cluster_outlines(ps["clusters"], to_xy, float(st.footprint_touch_m),
                                        walled_only=True, min_m2=mn)
            sxy = to_xy(site[1], site[0])
        except Exception as exc:                  # an older tree: clusters only
            print(f"[{icao}] pad reading skipped: {exc}", flush=True)
        rec["site"] = site_report(ps["clusters"], site[0], site[1], mn, pads, sxy)
    return rec


def _legacy_pack_stage(icao, airport, law, inputs, lrep, out=print):
    """``--tree`` pointed at a BASE tree that predates ``pack_stage``
    (main before #27): that tree's drive site with the cache OFF is
    exactly this sequence — read, partition, groups, clusters — so the
    base arm times the same four calls.  Never used on a tree that has
    ``pack_stage``."""
    import dataclasses as _d
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.airport.pack_partition import partition_pack
    from auto_patch_v2.law.tables import group_span_max_m
    from auto_patch_v2.planar.basins import read_objects
    from auto_patch_v2.planar.cluster import clusters as derive_clusters
    from auto_patch_v2.planar.group import derive
    sub = {}
    t0 = t = time.perf_counter()
    oc = ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objs, rep = read_objects(airport, law, oc)
    sub["read"] = time.perf_counter() - t
    t = time.perf_counter()
    part = partition_pack(airport, objs, oc, law)
    sub["partition"] = time.perf_counter() - t
    to_xy = airport.frame.entry() if hasattr(airport.frame, "entry") else airport.frame.transformers()[0]

    def dem_at(lat, lon):
        x, y = to_xy(lon, lat)
        try:
            z = airport.dem.z(x, y)
        except Exception:
            return None
        return None if z is None or float(z) != float(z) else float(z)

    bank = float(law.tables.emit.design.bank_slope)
    t = time.perf_counter()
    grp = derive(part, group_span_max_m(law), bank, dem_at=dem_at, bank_slope=bank)
    sub["groups"] = time.perf_counter() - t
    t = time.perf_counter()
    cl = derive_clusters(_d.replace(airport, partition=part), law)
    sub["clusters"] = time.perf_counter() - t
    sub["total"] = time.perf_counter() - t0
    return {"airport": airport, "partition": part, "groups": grp, "clusters": cl, "cache": "OFF(legacy)",
            "wall": sub}


def summarise(runs: list[dict]) -> dict:
    """Median per wall key over the runs, and whether the counts agree."""
    med = {k: round(statistics.median(r["wall"][k] for r in runs), 2) for k in WALL_KEYS}
    same = all(r["counts"] == runs[0]["counts"] and r["groups"] == runs[0]["groups"]
               for r in runs)
    return {"median_wall": med, "runs": len(runs), "counts_agree": same,
            "max_rss_gb_max": max(r["max_rss_gb"] for r in runs)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--cache", choices=("off", "on"), default="off")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "tmp" / "pack_stage_profile")
    ap.add_argument("--tree", type=Path, help="time ANOTHER worktree's Ortho4XP/ "
                    "(a base arm at clean main); its own src/ is imported")
    ap.add_argument("--site", help="LAT,LON: report the cluster whose outline "
                    "contains (or is nearest) the site — outline m², members, "
                    "bodies — and the cluster counts (issue #69)")
    ap.add_argument("--one", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    if a.one:
        st = tuple(float(v) for v in a.site.split(",")) if a.site else None
        print("RECORD " + json.dumps(run_once(a.icao, a.cache == "on", a.out_dir, st)), flush=True)
        return 0
    runs: list[dict] = []
    for k in range(a.runs):
        cmd = [sys.executable, __file__, a.icao, "--one", "--cache", a.cache,
               "--out-dir", str(a.out_dir)] + (["--site", a.site] if a.site else [])
        env = dict(os.environ)
        if a.tree:
            env["O4_PACK_STAGE_TREE"] = str(a.tree.resolve())
        p = subprocess.run(cmd, cwd=str(a.tree.resolve() if a.tree else ROOT),
                           capture_output=True, text=True, env=env)
        rec = next((json.loads(ln[7:]) for ln in p.stdout.splitlines()
                    if ln.startswith("RECORD ")), None)
        if p.returncode != 0 or rec is None:
            sys.stderr.write(p.stdout[-4000:] + p.stderr[-4000:])
            print(f"[{a.icao}] run {k + 1} FAILED rc {p.returncode}")
            return 1
        runs.append(rec)
        print(f"[{a.icao}] run {k + 1}/{a.runs} cache {rec['cache']}  "
              + "  ".join(f"{kk} {rec['wall'][kk]:.1f}" for kk in WALL_KEYS)
              + f"  RSS {rec['max_rss_gb']:.2f} GB  parts {rec['counts']['parts']}  "
              f"pairs {rec['counts']['pairs_tested']}  groups {rec['groups']['groups']}",
              flush=True)
        for ln in rec["cache_lines"]:
            print(f"    {ln}")
        if rec.get("site"):
            print("    [site] " + "  ".join(f"{k} {v}" for k, v in rec["site"].items()))
    s = summarise(runs)
    print(f"[{a.icao}] MEDIAN of {s['runs']}: "
          + "  ".join(f"{k} {v:.1f}" for k, v in s["median_wall"].items())
          + f"  max RSS {s['max_rss_gb_max']:.2f} GB  counts agree {s['counts_agree']}")
    if a.json:
        a.json.write_text(json.dumps({"summary": s, "runs": runs}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
