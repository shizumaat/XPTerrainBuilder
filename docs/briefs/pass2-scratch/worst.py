"""pass2 scratch: the WORST NEW airside rows of census B against census A, by EXCESS over the row's own limit,
with each pair's two end points' elevation in both surfaces.
usage: worst.py A.rows.json B.rows.json A.graded.json B.graded.json [--top N] [--skip FAMILY ...]"""
import json
import math
import sys
from collections import defaultdict

import numpy as np

if __name__ == '__main__':
    a = sys.argv[1:]
    ra, rb, ga, gb = a[:4]
    top = int(a[a.index('--top') + 1]) if '--top' in a else 10
    skip = {a[i + 1] for i, x in enumerate(a) if x == '--skip'} | {'drainage_minimum'}

    def key(r):
        s = r.get('site_m') or [[0, 0], [0, 0]]
        e = tuple(sorted((round(p[0] * 2) / 2, round(p[1] * 2) / 2) for p in s))
        return (r['family'], r['roles'], str(r.get('way_a')), str(r.get('way_b')), e)

    A = [r for r in json.load(open(ra))['rows'] if r.get('side') == 'airside']
    B = [r for r in json.load(open(rb))['rows'] if r.get('side') == 'airside']
    ka = {key(r) for r in A}
    # the same pair in A, whatever its magnitude: by family + end points
    new = [r for r in B if key(r) not in ka and r['family'] not in skip and r.get('site_m')]
    # affine site_m -> lat/lon from the rows' own mid-points
    M = np.array([[0.5 * (r['site_m'][0][0] + r['site_m'][1][0]), 0.5 * (r['site_m'][0][1] + r['site_m'][1][1]), 1.0]
                  for r in B if r.get('site_m') and r['family'] == 'within_shape'])
    L = np.array([[r['lat'], r['lon']] for r in B if r.get('site_m') and r['family'] == 'within_shape'])
    T, *_ = np.linalg.lstsq(M, L, rcond=None)

    def ll(p):
        return tuple(np.array([p[0], p[1], 1.0]) @ T)

    def verts(p):
        g = json.load(open(p))
        return [(v[1], v[2], v[3]) for v in g['vertices']]
    va, vb = verts(ga), verts(gb)
    la0 = va[0][0]
    kx, ky = 111320.0 * math.cos(math.radians(la0)), 110574.0

    def grid(vs):
        g = defaultdict(list)
        for la, lo, z in vs:
            g[(int(lo * kx // 5), int(la * ky // 5))].append((la, lo, z))
        return g
    gA, gB = grid(va), grid(vb)

    def z_at(g, la, lo):
        cx, cy = int(lo * kx // 5), int(la * ky // 5)
        best = None
        for i in range(cx - 1, cx + 2):
            for j in range(cy - 1, cy + 2):
                for p in g.get((i, j), ()):
                    d = math.hypot((p[1] - lo) * kx, (p[0] - la) * ky)
                    if best is None or d < best[0]:
                        best = (d, p[2], p[0], p[1])
        return best

    def excess(r):
        cap, d = r.get('cap_pct'), r.get('distance_m') or 0.0
        return r['magnitude_m'] - (cap / 100.0 * d if cap else 0.0)
    new.sort(key=lambda r: -excess(r))
    print(f'NEW airside rows (not deferred): {len(new)}; ranked by magnitude minus cap x distance (magnitude where the '
          f'family states no cap)')
    seen = set()
    n = 0
    for r in new:
        site = (r['family'], round(r['lat'], 4), round(r['lon'], 4))
        if site in seen:
            continue
        seen.add(site)
        ends = []
        for p in r['site_m']:
            la, lo = ll(p)
            za, zb = z_at(gA, la, lo), z_at(gB, la, lo)
            ends.append(f'{la:.8f}, {lo:.8f}: '
                        + (f'{za[1]:.2f}' if za and za[0] < 0.5 else 'n/a') + ' -> '
                        + (f'{zb[1]:.2f}' if zb and zb[0] < 0.5 else 'n/a'))
        cap = r.get('cap_pct')
        print(f'{n + 1}. {r["family"]} {r["roles"]} at {r["lat"]:.8f}, {r["lon"]:.8f}: {r["magnitude_m"]:.3f} m over '
              f'{r.get("distance_m")} m = {r.get("grade_pct")} %, limit {str(cap) + " %" if cap else "(family, no cap)"}'
              f', excess {excess(r):.3f} m | ends ' + ' ; '.join(ends))
        n += 1
        if n >= top:
            break
