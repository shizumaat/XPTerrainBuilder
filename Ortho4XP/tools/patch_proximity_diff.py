#!/usr/bin/env python3
"""z_B − z_A between two emitted patches of DIFFERENT ENGINES, by proximity
(scout ``hecav1v2`` ``cmp2.py``, RULINGS 2026-09-08d; promoted on its second
use by lane ``v2chord`` — spec ``heca-v1-parity-spec.md`` §5).

    venv/bin/python tools/patch_proximity_diff.py ICAO B.osm A.osm [--json OUT.json]
        [--cells 16] [--near 5] [--tin 40]

THE QUESTION: how far does patch B's surface stand from patch A's, by role
and by place, when the two carry DIFFERENT node populations (a v1 patch
vs a v2 patch: 1 shared 7-dp key of 22,637 at HECA).  ``airside_value_
delta.py`` is the same-engine instrument — it joins by the canonical
identity and reports an unshared node as ADDED / REMOVED, which is right
within one engine and answers nothing across two.  This tool joins by
PROXIMITY: for every B node the A value is the nearest A node within
``--near`` metres, else the linear TIN interpolation of A's nodes when
one lies within ``--tin`` metres, else no comparison.  Reported: per B
role the mean / p10 / p90 / max / min of dz and the counts |dz| > 1 m and
> 3 m; the magnitude bands over all compared nodes; the ranked 200 m
cells of |dz| > 1 m with both patches' z − DEM there (the sites); the
ring-edge |grade| statistics of both.  The DEM is v2's production loader
(``airport.load.load_with_report``) — the frame both patches were built
in — sampled once per coordinate and memoised beside ``--json``.

It measures NO LAW and counts NO DEFECTS (``harness/census.py`` does).
Geometry comes from ``check_grade._parse_osm``; the role ranking is the
seniority order used to pick one role per node."""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

TIER = ["runway", "runway_crossing", "stub", "primary_parallel", "secondary_parallel",
        "cross_connector", "junction", "tunnel_ramp", "apron", "object_pad", "building_pad",
        "pad", "service_road", "service_junction", "groundside_pavement", "parking_lot",
        "graded_strip", "building", "adjacent_ground", "boundary", "tunnel_trench"]


def rank(r: str) -> int:
    return TIER.index(r) if r in TIER else len(TIER)


def pct(v, p):
    if not v:
        return float("nan")
    v = sorted(v)
    i = (len(v) - 1) * p
    lo = int(i)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def load_patch(path: Path):
    import check_grade as cg
    feats: dict = {}
    nodes, ways = cg._parse_osm(path, feature_out=feats)
    z: dict = {}
    roles: dict = collections.defaultdict(set)
    edges = []
    for w in ways:
        for n, e in zip(w.nids, w.elevs):
            if e is not None and n not in z:
                z[n] = e
            roles[n].add(w.role or "?")
        for a, b in zip(w.nids, w.nids[1:]):
            edges.append((a, b, w.role or "?"))
    return nodes, z, roles, edges, ways


def dem_sampler(icao: str, cache: Path | None):
    import pickle
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline.__main__ import default_inputs
    memo = pickle.load(cache.open("rb")) if cache is not None and cache.exists() else {}
    law = Law.for_airport(icao)
    airport, _ = load_with_report(icao, default_inputs(), law)
    to_xy, _ = airport.frame.transformers()

    def z(lat, lon):
        k = (round(lat, 7), round(lon, 7))
        if k not in memo:
            x, y = to_xy(lon, lat)
            try:
                memo[k] = float(airport.dem.z(x, y))
            except Exception:
                memo[k] = None
        return memo[k]

    def save():
        if cache is not None:
            pickle.dump(memo, cache.open("wb"))
    return z, save, airport


def ll_dist(a, b):
    la, lo = a
    lb, lob = b
    return math.hypot((la - lb) * 111320.0, (lo - lob) * 111320.0 * math.cos(math.radians(la)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("patch_b", type=Path, help="the patch under test (B)")
    ap.add_argument("patch_a", type=Path, help="the reference patch (A)")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--cells", type=int, default=16, help="ranked 200 m cells to list")
    ap.add_argument("--near", type=float, default=5.0)
    ap.add_argument("--tin", type=float, default=40.0)
    a = ap.parse_args()
    import numpy as np
    from scipy.interpolate import LinearNDInterpolator
    from scipy.spatial import cKDTree
    cache = (a.json.with_suffix(".demcache.pkl") if a.json else None)
    demz, save, airport = dem_sampler(a.icao.upper(), cache)
    to_xy, _ = airport.frame.transformers()
    N2, Z2, R2, E2, _W2 = load_patch(a.patch_b)
    N1, Z1, R1, E1, _W1 = load_patch(a.patch_a)
    ids1 = list(Z1)
    P1 = np.array([to_xy(N1[n][1], N1[n][0]) for n in ids1])
    z1 = np.array([Z1[n] for n in ids1])
    ids2 = list(Z2)
    P2 = np.array([to_xy(N2[n][1], N2[n][0]) for n in ids2])
    z2 = np.array([Z2[n] for n in ids2])
    d, j = cKDTree(P1).query(P2)
    zt = LinearNDInterpolator(P1, z1)(P2)
    print(f"B nodes {len(ids2)}; A nodes {len(ids1)}; B nodes with an A node within 1 m: "
          f"{(d < 1).sum()} ({100 * (d < 1).mean():.1f}%), within {a.near:g} m: {(d < a.near).sum()} "
          f"({100 * (d < a.near).mean():.1f}%); TIN-covered: {int(np.isfinite(zt).sum())}")
    zv1 = np.where(d < a.near, z1[j], np.where((d < a.tin) & np.isfinite(zt), zt, np.nan))
    dz = z2 - zv1
    role2 = [min(R2[n], key=rank) for n in ids2]
    role1n = [min(R1[ids1[k]], key=rank) for k in j]
    out: dict = {"icao": a.icao.upper(), "patch_b": str(a.patch_b), "patch_a": str(a.patch_a),
                 "by_role": {}, "sites": []}
    print(f"\n## z_B - z_A at B nodes (A = nearest node < {a.near:g} m, else TIN < {a.tin:g} m)")
    print("| B role | n | mean | p10 | p90 | max | min | n |dz|>1 m | n |dz|>3 m | A roles nearest (top 3) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    by = collections.defaultdict(list)
    for i, r in enumerate(role2):
        if np.isfinite(dz[i]):
            by[r].append((float(dz[i]), role1n[i]))
    tot: list[float] = []
    for r in sorted(by, key=rank):
        v = [t[0] for t in by[r]]
        tot += v
        rec = {"n": len(v), "mean": st.mean(v), "p10": pct(v, .1), "p90": pct(v, .9),
               "max": max(v), "min": min(v), "over_1m": sum(1 for x in v if abs(x) > 1),
               "over_3m": sum(1 for x in v if abs(x) > 3)}
        out["by_role"][r] = rec
        print("| %s | %d | %+.2f | %+.2f | %+.2f | %+.2f | %+.2f | %d | %d | %s |" % (
            r, rec["n"], rec["mean"], rec["p10"], rec["p90"], rec["max"], rec["min"],
            rec["over_1m"], rec["over_3m"], collections.Counter(t[1] for t in by[r]).most_common(3)))
    allrec = {"n": len(tot), "mean": st.mean(tot), "p10": pct(tot, .1), "p90": pct(tot, .9),
              "max": max(tot), "min": min(tot), "over_1m": sum(1 for x in tot if abs(x) > 1),
              "over_3m": sum(1 for x in tot if abs(x) > 3),
              "over_6m": sum(1 for x in tot if abs(x) > 6)}
    out["all"] = allrec
    print("| ALL | %d | %+.2f | %+.2f | %+.2f | %+.2f | %+.2f | %d | %d | |" % (
        allrec["n"], allrec["mean"], allrec["p10"], allrec["p90"], allrec["max"], allrec["min"],
        allrec["over_1m"], allrec["over_3m"]))
    cells = collections.defaultdict(list)
    for i in range(len(ids2)):
        if np.isfinite(dz[i]) and abs(dz[i]) > 1.0:
            x, y = P2[i]
            cells[(int(x // 200), int(y // 200))].append(i)
    ranked = sorted(cells.items(), key=lambda kv: -sum(abs(dz[i]) for i in kv[1]))
    print("\n## sites (200 m cells, |dz|>1 m), ranked by sum|dz|")
    print("| # | lat,lon | n | mean dz | max | min | B roles | A nearest roles | B z-DEM mean | A z-DEM mean |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for k, (_c, ii) in enumerate(ranked[:a.cells]):
        la = st.mean(N2[ids2[i]][0] for i in ii)
        lo = st.mean(N2[ids2[i]][1] for i in ii)
        ds = [float(dz[i]) for i in ii]
        dd2 = [float(z2[i]) - demz(*N2[ids2[i]]) for i in ii if demz(*N2[ids2[i]]) is not None]
        dd1 = [float(zv1[i]) - demz(*N2[ids2[i]]) for i in ii if demz(*N2[ids2[i]]) is not None]
        rec = {"rank": k + 1, "lat": la, "lon": lo, "n": len(ii), "mean_dz": st.mean(ds),
               "max": max(ds), "min": min(ds),
               "b_roles": dict(collections.Counter(role2[i] for i in ii).most_common(4)),
               "a_roles": dict(collections.Counter(role1n[i] for i in ii).most_common(3)),
               "b_z_dem_mean": st.mean(dd2) if dd2 else None,
               "a_z_dem_mean": st.mean(dd1) if dd1 else None}
        out["sites"].append(rec)
        print("| %d | %.6f,%.6f | %d | %+.2f | %+.2f | %+.2f | %s | %s | %s | %s |" % (
            k + 1, la, lo, len(ii), rec["mean_dz"], rec["max"], rec["min"], rec["b_roles"],
            rec["a_roles"], "n/a" if rec["b_z_dem_mean"] is None else "%+.2f" % rec["b_z_dem_mean"],
            "n/a" if rec["a_z_dem_mean"] is None else "%+.2f" % rec["a_z_dem_mean"]))
    aa = np.abs(dz[np.isfinite(dz)])
    bands = {"<0.5": int((aa < 0.5).sum()), "0.5-1": int(((aa >= 0.5) & (aa < 1)).sum()),
             "1-3": int(((aa >= 1) & (aa < 3)).sum()), "3-6": int(((aa >= 3) & (aa < 6)).sum()),
             ">6": int((aa >= 6).sum())}
    out["bands"] = bands
    print(f"\n|dz| bands over compared B nodes: {bands}  ({100 * allrec['over_1m'] / max(1, allrec['n']):.1f}% over 1 m, "
          f"{allrec['over_6m']} over 6 m)")

    def gstats(N, Z, E):
        eg = collections.defaultdict(list)
        for a_, b_, r in E:
            if a_ in Z and b_ in Z:
                L = ll_dist(N[a_], N[b_])
                if L >= 3:
                    eg[r].append(abs(Z[a_] - Z[b_]) / L * 100)
        return {r: (len(v), round(pct(v, .5), 2), round(pct(v, .9), 2), round(max(v), 1))
                for r, v in sorted(eg.items(), key=lambda kv: rank(kv[0]))}
    print("\n## ring-edge |grade| % (edges >= 3 m): n / median / p90 / max")
    out["grades"] = {"B": gstats(N2, Z2, E2), "A": gstats(N1, Z1, E1)}
    print("B", out["grades"]["B"])
    print("A", out["grades"]["A"])
    save()
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
