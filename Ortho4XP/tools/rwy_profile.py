"""A RUNWAY PROFILE read on an emitted v2 patch (born lane v2routecap scratch, spec
`docs/specs/auto-patch-v2/apron-route-cap-spec.md` §5; promoted on its second use by lane v2lexi):
the crown spine's built z by station, the threshold line (apt.dat
threshold elevations, straight between the ends), the ridge MINIMUM and
its station, the bow (min of z − line), the z at the 05C/23C × 05L/23R
crossing, and the max grade change per 100 m along the spine.

    venv/bin/python tools/rwy_profile.py PATCH.osm [--icao HECA] [--rwy 05C/23C] [--cross 05L/23R]
    venv/bin/python tools/rwy_profile.py PATCH.osm --binned [--compare OTHER.osm] [--icao HECA]

The bow / ridge minimum / K figures every HECA round quotes (RULINGS 06l..06x)
come from here.  Twin owed (tools/INDEX.md).

``--binned`` (scout ``hecav1v2`` ``rwy.py``, RULINGS 2026-09-08d; promoted on
its second use by lane ``v2chord``) is the CROSS-ENGINE read: a v1 patch
carries no ``crown_spine`` way, so the ridge is read as the MAX z per 50 m
station bin over the runway-role nodes within 40 m of the axis, for EVERY
runway with two thresholds — bow, ridge minimum, max |grade|, max grade
change per 100 m, z − DEM (mean / min / max) — on this patch and, with
``--compare``, on the other, plus the station table of both ridges and
the DEM (v2's production loader, memoised beside the patch)."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
import check_grade as cg  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.airport.load import load_with_report  # noqa: E402
from auto_patch_v2.pipeline.__main__ import default_inputs  # noqa: E402


def _spine(patch: Path, ref: str):
    feats: dict = {}
    nodes, ways = cg._parse_osm(patch, feature_out=feats)
    ll_to_m = cg._ll_to_m_factory(nodes)
    best = None
    for w in feats.get("crown_spine", []):
        if ref and w.ref != ref and w.tags.get("ref") != ref:
            continue
        pts = [(nodes[n][0], nodes[n][1], *ll_to_m(*nodes[n]), z)
               for n, z in zip(w.nids, w.elevs) if z is not None]
        if best is None or len(pts) > len(best):
            best = pts
    return best, ll_to_m


def _binned(patches: dict[str, Path], airport, law) -> int:
    """The cross-engine read (module docstring)."""
    import collections
    import pickle
    import statistics as st
    to_xy, _ = airport.frame.transformers()
    cache = Path(str(next(iter(patches.values()))) + ".demcache.pkl")
    memo = pickle.load(cache.open("rb")) if cache.exists() else {}

    def demz(lat, lon):
        k = (round(lat, 7), round(lon, 7))
        if k not in memo:
            x, y = to_xy(lon, lat)
            try:
                memo[k] = float(airport.dem.z(x, y))
            except Exception:
                memo[k] = None
        return memo[k]
    loaded = {}
    for name, p in patches.items():
        feats: dict = {}
        nodes, ways = cg._parse_osm(p, feature_out=feats)
        loaded[name] = (nodes, ways)
    for rw in airport.runways:
        e0, e1 = rw.ends
        if e0.threshold_elev_m is None or e1.threshold_elev_m is None:
            continue
        (x0, y0), (x1, y1) = e0.xy, e1.xy
        L = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        z0, z1 = e0.threshold_elev_m, e1.threshold_elev_m
        print(f"\n### {rw.id}: {e0.name} {z0:.2f} -> {e1.name} {z1:.2f} over {L:.0f} m")
        prof: dict[str, dict] = {}
        for name, (nodes, ways) in loaded.items():
            bins = collections.defaultdict(list)
            for w in ways:
                if w.role != "runway" or (rw.id not in (w.ref or "") and (w.ref or "") not in rw.id):
                    continue
                for n, z in zip(w.nids, w.elevs):
                    if z is None:
                        continue
                    x, y = to_xy(nodes[n][1], nodes[n][0])
                    s = (x - x0) * ux + (y - y0) * uy
                    t = abs(-(x - x0) * uy + (y - y0) * ux)
                    if -5 <= s <= L + 5 and t < 40:
                        bins[int(s // 50)].append((z, demz(*nodes[n])))
            prof[name] = {b: (max(v, key=lambda q: q[0])[0],
                              st.mean(q[1] for q in v if q[1] is not None) if any(q[1] is not None for q in v) else None)
                          for b, v in bins.items()}
            rows = sorted((b * 50 + 25, zz, dd) for b, (zz, dd) in prof[name].items())
            if not rows:
                print(name, "no runway nodes")
                continue

            def line(s):
                return z0 + (z1 - z0) * s / L
            bow = min(rows, key=lambda r: r[1] - line(r[0]))
            zmin = min(rows, key=lambda r: r[1])
            g = [((rb[1] - ra[1]) / (rb[0] - ra[0]) * 100, ra[0]) for ra, rb in zip(rows, rows[1:])]
            gw = max(g, key=lambda q: abs(q[0])) if g else (0.0, 0)
            k = [(abs(g[i + 2][0] - g[i][0]) / (g[i + 2][1] - g[i][1]) * 100, g[i][1]) for i in range(len(g) - 2)]
            kw = max(k, key=lambda q: q[0]) if k else (float("nan"), 0)
            offs = [r[1] - r[2] for r in rows if r[2] is not None]
            print(f"{name}: bins {len(rows)}; ridge min z {zmin[1]:.2f} at s={zmin[0]:.0f}; "
                  f"BOW {bow[1] - line(bow[0]):+.2f} at s={bow[0]:.0f}; max |grade| {abs(gw[0]):.2f} % at "
                  f"s={gw[1]:.0f}; max grade change {kw[0]:.3f} %/100 m at s={kw[1]:.0f}; "
                  f"z-DEM mean {st.mean(offs):+.2f} min {min(offs):+.2f} max {max(offs):+.2f}; "
                  f"n nodes {sum(len(v) for v in bins.values())}")
        keys = sorted(set().union(*(set(p) for p in prof.values())))
        print("station(m): " + " ".join(f"{b * 50 + 25}" for b in keys if b % 4 == 0))
        dem_row = []
        for b in keys:
            if b % 4:
                continue
            d = next((p[b][1] for p in prof.values() if b in p and p[b][1] is not None), None)
            dem_row.append("  -  " if d is None else f"{d:.1f}")
        print("DEM       : " + " ".join(dem_row))
        for name, p in prof.items():
            print(f"{name:10s}: " + " ".join(f"{p[b][0]:.1f}" if b in p else "  -  " for b in keys if b % 4 == 0))
    pickle.dump(memo, cache.open("wb"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("--icao", default="HECA")
    ap.add_argument("--rwy", default="05C/23C")
    ap.add_argument("--cross", default="05L/23R")
    ap.add_argument("--binned", action="store_true", help="the cross-engine binned-ridge read of every runway")
    ap.add_argument("--compare", type=Path, help="with --binned: the other patch (v1 control) read alike")
    a = ap.parse_args()
    patch = Path(a.patch)
    law = Law.for_airport(a.icao)
    airport, _rep = load_with_report(a.icao, default_inputs(), law)
    if a.binned:
        patches = {"this": patch}
        if a.compare:
            patches["compare"] = a.compare
        return _binned(patches, airport, law)
    rw = next(r for r in airport.runways if r.id == a.rwy)
    xr = next(r for r in airport.runways if r.id == a.cross)
    pts, ll_to_m = _spine(patch, a.rwy)
    if not pts:
        print("no crown spine for", a.rwy)
        return 1
    e0, e1 = rw.ends
    (x0, y0), (x1, y1) = e0.xy, e1.xy
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    z0, z1 = e0.threshold_elev_m, e1.threshold_elev_m
    print(f"{a.rwy}: {e0.name} {z0:.2f} m -> {e1.name} {z1:.2f} m over {L:.0f} m; spine {len(pts)} stations")
    # the crossing: intersection of the two runway centrelines
    (cx0, cy0), (cx1, cy1) = xr.ends[0].xy, xr.ends[1].xy
    den = (x1 - x0) * (cy1 - cy0) - (y1 - y0) * (cx1 - cx0)
    t = ((cx0 - x0) * (cy1 - cy0) - (cy0 - y0) * (cx1 - cx0)) / den
    xs, ys = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
    s_cross = t * L
    rows = []
    for lat, lon, x, y, z in pts:
        s = (x - x0) * ux + (y - y0) * uy
        line = z0 + (z1 - z0) * s / L
        rows.append((s, z, line, lat, lon))
    rows.sort()
    zmin = min(rows, key=lambda r: r[1])
    bow = min(rows, key=lambda r: r[1] - r[2])
    near = min(rows, key=lambda r: abs(r[0] - s_cross))
    print(f"ridge MINIMUM z {zmin[1]:.2f} at station {zmin[0]:.0f} m ({zmin[3]:.6f},{zmin[4]:.6f}); line there {zmin[2]:.2f} -> {zmin[1]-zmin[2]:+.2f}")
    print(f"BOW (min z-line) {bow[1]-bow[2]:+.2f} m at station {bow[0]:.0f} m ({bow[3]:.6f},{bow[4]:.6f}), z {bow[1]:.2f} line {bow[2]:.2f}")
    print(f"{a.cross} crossing at station {s_cross:.0f} m: nearest spine station {near[0]:.0f} m z {near[1]:.2f} (line {near[2]:.2f}, {near[1]-near[2]:+.2f}); owner's 109 m point")
    # grades and grade change per 100 m along consecutive stations
    g = []
    for (s0, za, *_), (s1, zb, *_) in zip(rows, rows[1:]):
        if s1 - s0 > 0.5:
            g.append((s0, s1, (zb - za) / (s1 - s0)))
    worst = max(g, key=lambda r: abs(r[2]))
    print(f"max |grade| {100*abs(worst[2]):.3f} % at {worst[0]:.0f}-{worst[1]:.0f} m; stations {len(g)}")
    # grade change per 100 m: the grade over [s-100, s] vs [s, s+100]
    # (z interpolated along the spine), the owner's K reading
    S = [r[0] for r in rows]; Z = [r[1] for r in rows]
    def zat(s):
        import bisect
        i = bisect.bisect_left(S, s)
        if i <= 0: return Z[0]
        if i >= len(S): return Z[-1]
        f = (s - S[i-1]) / (S[i] - S[i-1]) if S[i] > S[i-1] else 0.0
        return Z[i-1] + f * (Z[i] - Z[i-1])
    k = []
    for s, *_ in rows:
        if s - 100.0 < S[0] or s + 100.0 > S[-1]:
            continue
        g0 = (zat(s) - zat(s - 100.0)) / 100.0
        g1 = (zat(s + 100.0) - zat(s)) / 100.0
        k.append((s, abs(g1 - g0) * 100.0))
    kw = max(k, key=lambda r: r[1])
    print(f"max grade change {kw[1]:.3f} % per 100 m at station {kw[0]:.0f} m "
          f"(law K: 1 % per 305 m = 0.328 %/100 m for C-F; verify family runway_vertical_curve is the instrument)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
