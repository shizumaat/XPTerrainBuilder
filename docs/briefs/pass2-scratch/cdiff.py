"""pass2 scratch: ROW-LEVEL diff of two harness censuses (--rows-json), joined to the two graded surfaces.
usage: cdiff.py A.rows.json B.rows.json A.graded.json B.graded.json [--fam F ...] [--top N] [--side airside]
A row's key: (family, roles, way_a, way_b, its two site_m endpoints rounded to 0.5 m, unordered).
NEW = in B only; GONE = in A only.  For each NEW row: the endpoints' z in A and B (nearest graded vertex in the
row's own frame is not available -> joined by the row's lat/lon mid-point: the two nearest graded vertices' moves)."""
import json
import math
import sys
from collections import Counter, defaultdict

if __name__ == '__main__':
    a = sys.argv[1:]
    ra, rb, ga, gb = a[:4]
    fams = [a[i + 1] for i, x in enumerate(a) if x == '--fam']
    top = int(a[a.index('--top') + 1]) if '--top' in a else 10
    side = a[a.index('--side') + 1] if '--side' in a else 'airside'

    def key(r):
        s = r.get('site_m') or [[0, 0], [0, 0]]
        e = tuple(sorted((round(p[0] * 2) / 2, round(p[1] * 2) / 2) for p in s))
        return (r['family'], r['roles'], str(r.get('way_a')), str(r.get('way_b')), e)

    def load(p):
        rows = [r for r in json.load(open(p))['rows'] if r.get('side') == side or side == 'all']
        d = defaultdict(list)
        for r in rows:
            d[key(r)].append(r)
        return rows, d
    rows_a, da = load(ra)
    rows_b, db = load(rb)
    ca, cb = Counter(r['family'] for r in rows_a), Counter(r['family'] for r in rows_b)

    def verts(p):
        g = json.load(open(p))
        return {(round(v[1], 9), round(v[2], 9)): v[3] for v in g['vertices']}, g
    za, _ = verts(ga)
    zb, gB = verts(gb)
    common = [k for k in za if k in zb]
    la0, lo0 = gB['frame']['origin']
    kx, ky = 111320.0 * math.cos(math.radians(la0)), 110574.0
    pts = [((k[1] - lo0) * kx, (k[0] - la0) * ky, za[k], zb[k], k) for k in common]
    grid = defaultdict(list)
    for p in pts:
        grid[(int(p[0] // 25), int(p[1] // 25))].append(p)

    def near(x, y, n=1):
        best = []
        cx, cy = int(x // 25), int(y // 25)
        for i in range(cx - 1, cx + 2):
            for j in range(cy - 1, cy + 2):
                for p in grid.get((i, j), ()):
                    best.append((math.hypot(p[0] - x, p[1] - y), p))
        best.sort(key=lambda t: t[0])
        return best[:n]

    print(f'rows ({side}) A {len(rows_a)} B {len(rows_b)}; nodes common {len(common)} of {len(za)} / {len(zb)}')
    print('family: A -> B | NEW (B only) / GONE (A only) / kept | NEW rows whose pair MOVED (|d(dz)| > 0.02) / did not move')
    for f in sorted(set(ca) | set(cb)):
        if fams and f not in fams:
            continue
        if ca[f] == cb[f] and not fams:
            continue
        new = [r for k, v in db.items() if k[0] == f and k not in da for r in v]
        gone = [r for k, v in da.items() if k[0] == f and k not in db for r in v]
        kept = sum(len(v) for k, v in db.items() if k[0] == f and k in da)
        mv = nm = 0
        det = []
        for r in new:
            s = r.get('site_m')
            if not s:
                continue
            # the row's frame is the census's own metre frame; join by lat/lon mid-point instead
            x, y = (r['lon'] - lo0) * kx, (r['lat'] - la0) * ky
            half = 0.5 * (r.get('distance_m') or 0.0)
            nb = near(x, y, 6)
            # the pair's own endpoints: the two graded vertices nearest the mid-point +- half the span
            cand = [p for d, p in nb]
            d_move = max((abs(p[3] - p[2]) for p in cand), default=0.0)
            dd = (max(p[3] - p[2] for p in cand) - min(p[3] - p[2] for p in cand)) if cand else 0.0
            if dd > 0.02 or d_move > 0.02:
                mv += 1
            else:
                nm += 1
            det.append((r['magnitude_m'], r, d_move, dd, cand[:2]))
        print(f'{f}: {ca[f]} -> {cb[f]} | NEW {len(new)} / GONE {len(gone)} / kept {kept} | moved {mv} / unmoved {nm}')
        if fams or abs(cb[f] - ca[f]) > 0:
            det.sort(key=lambda t: -t[0])
            for mag, r, d_move, dd, cand in det[:top]:
                zz = '; '.join(f'{p[4][0]:.8f},{p[4][1]:.8f} {p[2]:.2f}->{p[3]:.2f}' for p in cand)
                print(f'    NEW {r["roles"]} {mag:.3f} m ({r.get("grade_pct")} % vs cap {r.get("cap_pct")} %, d {r.get("distance_m")}) '
                      f'at {r["lat"]:.8f}, {r["lon"]:.8f} ways {r.get("way_a")}/{r.get("way_b")} | nearest vertices moved '
                      f'<= {d_move:.2f} m, relative {dd:.2f} m: {zz}')
