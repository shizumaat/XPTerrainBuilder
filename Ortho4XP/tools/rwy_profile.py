"""A RUNWAY PROFILE read on an emitted v2 patch (born lane v2routecap scratch, spec
`docs/specs/auto-patch-v2/apron-route-cap-spec.md` §5; promoted on its second use by lane v2lexi):
the crown spine's built z by station, the threshold line (apt.dat
threshold elevations, straight between the ends), the ridge MINIMUM and
its station, the bow (min of z − line), the z at the 05C/23C × 05L/23R
crossing, and the max grade change per 100 m along the spine.

    venv/bin/python tools/rwy_profile.py PATCH.osm [--icao HECA] [--rwy 05C/23C] [--cross 05L/23R]

The bow / ridge minimum / K figures every HECA round quotes (RULINGS 06l..06x)
come from here.  Twin owed (tools/INDEX.md)."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("--icao", default="HECA")
    ap.add_argument("--rwy", default="05C/23C")
    ap.add_argument("--cross", default="05L/23R")
    a = ap.parse_args()
    patch = Path(a.patch)
    law = Law.for_airport(a.icao)
    airport, _rep = load_with_report(a.icao, default_inputs(), law)
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
