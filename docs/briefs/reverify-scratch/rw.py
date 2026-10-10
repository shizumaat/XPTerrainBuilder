"""reverify scratch: runway read BASE_DIR -> ARM_DIR (graded.json joined on the 11-dp lat/lon key; z is cm-rounded,
so dz is quantised at 0.01 m = 0.033 pp over 30 m).   usage: rw.py BASE_DIR ARM_DIR ICAO [TOP]
Per runway (RULINGS 2026-10-10a (1): worst <= 0.5 m AND gentle): movers, worst, and the SHAPE of dz = arm - base
along the runway's own axis (PCA of its vertices): cross-sections (vertices within 2 m of station) -> mean dz ->
piecewise-linear dz(s) sampled at 1 m -> largest change over any 30 m and any 60 m as a longitudinal grade change
(percentage points); every run of 30 m windows over 0.1 pp listed by site (a KINK); the largest change of dz across
one face edge, transverse and longitudinal (a step / cliff)."""
import collections
import json
import math
import sys

import numpy as np

KINK_PP = 0.1


def main():
    B, A, icao = sys.argv[1:4]
    top = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    gb = json.load(open(f'{B}/emit/{icao}.graded.json'))
    ga = json.load(open(f'{A}/emit/{icao}.graded.json'))
    zb = {(round(r[1], 11), round(r[2], 11)): r[3] for r in gb['vertices']}
    va = {r[0]: r for r in ga['vertices']}
    lat0 = ga['frame']['origin'][0]
    mx = 111320 * math.cos(math.radians(lat0))
    byref = collections.defaultdict(set)
    edges = collections.defaultdict(set)
    for f in ga['faces']:
        if f['role'] != 'runway':
            continue
        ref = f['ref'].split('#')[0]
        for ring in [f['ring'], *f['holes']]:
            byref[ref] |= set(ring)
            for a, b in zip(ring, ring[1:] + ring[:1]):
                edges[ref].add((min(a, b), max(a, b)))
    allmv, seen = [], set()
    for ref, vs in sorted(byref.items()):
        d = {}
        for u in vs:
            r = va[u]
            z0 = zb.get((round(r[1], 11), round(r[2], 11)))
            if z0 is not None:
                d[u] = (r[2] * mx, r[1] * 111320, r[3] - z0, r[1], r[2], z0, r[3])
                if u not in seen:
                    seen.add(u)
                    allmv.append((abs(r[3] - z0), r[1], r[2], z0, r[3], ref))
        if len(d) < 8:
            continue
        us = sorted(d)
        P = np.array([d[u][:2] for u in us])
        dz = np.array([d[u][2] for u in us])
        c = P.mean(0)
        vt = np.linalg.svd(P - c)[2]
        s = (P - c) @ vt[0]
        off = (P - c) @ vt[1]
        s0 = s.min()
        s -= s0
        sd = dict(zip(us, s))
        n02, n10, n50 = (int((abs(dz) > t).sum()) for t in (0.02, 0.1, 0.5))
        w = int(np.argmax(abs(dz)))
        print(f'RUNWAY {ref}: {len(us)} vertices (unmatched {len(vs) - len(us)}), length {s.max():.0f} m; movers > 0.02: {n02}, '
              f'> 0.1: {n10}, > 0.5: {n50}, worst {dz[w]:+.3f} m @ {d[us[w]][3]:.8f},{d[us[w]][4]:.8f} (s {s[w]:.0f} m)')
        # cross-sections -> dz(s)
        order = np.argsort(s)
        secs, cur = [], [order[0]]
        for i in order[1:]:
            if s[i] - s[cur[0]] <= 2.0:
                cur.append(i)
            else:
                secs.append(cur)
                cur = [i]
        secs.append(cur)
        ss = np.array([s[k].mean() for k in secs])
        sz = np.array([dz[k].mean() for k in secs])
        grid = np.arange(0.0, math.floor(s.max()) + 1.0)
        prof = np.interp(grid, ss, sz)
        gaps = np.diff(ss)
        print(f'  {len(secs)} cross-sections, spacing median {np.median(gaps):.0f} m, max {gaps.max():.0f} m; dz of sections '
              f'min {sz.min():+.3f} max {sz.max():+.3f}')

        def at(st):
            k = int(np.argmin(abs(s - st) + abs(off) * 0.01))
            return f'{d[us[k]][3]:.8f},{d[us[k]][4]:.8f}'
        for L in (30, 60):
            dd = prof[L:] - prof[:-L]
            k = int(np.argmax(abs(dd)))
            print(f'  SHAPE over {L} m: largest change of dz {dd[k]:+.3f} m = longitudinal grade change '
                  f'{100 * dd[k] / L:+.3f} pp at s {k}..{k + L} m ({at(k + L / 2)})')
        dd = 100 * (prof[30:] - prof[:-30]) / 30
        hot = np.where(abs(dd) > KINK_PP)[0]
        runs = []
        for k in hot:
            if runs and k - runs[-1][-1] <= 30:
                runs[-1].append(k)
            else:
                runs.append([k])
        print(f'  KINKS (> {KINK_PP} pp over 30 m): {len(runs)}')
        for r in runs:
            k = max(r, key=lambda k: abs(dd[k]))
            print(f'    s {r[0]}..{r[-1] + 30} m  peak {dd[k]:+.3f} pp at s {k}..{k + 30} ({at(k + 15)})  dz {prof[k]:+.3f} -> {prof[k + 30]:+.3f}')
        best = {'transverse': (0, None), 'longitudinal': (0, None)}
        for a, b in edges[ref]:
            if a not in d or b not in d:
                continue
            ex, ey = d[b][0] - d[a][0], d[b][1] - d[a][1]
            ln = math.hypot(ex, ey)
            if ln < 0.5:
                continue
            kind = 'transverse' if abs(ex * vt[0][0] + ey * vt[0][1]) / ln < 0.5 else 'longitudinal'
            t = abs(d[b][2] - d[a][2])
            if t > best[kind][0]:
                best[kind] = (t, (a, b, ln))
        for kind, (t, e) in best.items():
            if e:
                a, b, ln = e
                print(f'  EDGE {kind}: largest change of dz across one runway face edge {t:.3f} m over {ln:.1f} m '
                      f'({100 * t / ln:.3f} pp) at {d[a][3]:.8f},{d[a][4]:.8f} (s {sd[a]:.0f} m)')
        print('  dz by station (200 m, mean of sections): ' + ' '.join(
            f'{sz[(ss >= a0) & (ss < a0 + 200)].mean():+.2f}' for a0 in range(0, int(s.max()), 200)
            if ((ss >= a0) & (ss < a0 + 200)).any()))
    allmv.sort(reverse=True)
    print(f'ALL RUNWAY VERTICES {len(allmv)}: movers > 0.02: {sum(1 for t in allmv if t[0] > 0.02)}, > 0.1: '
          f'{sum(1 for t in allmv if t[0] > 0.1)}, > 0.5: {sum(1 for t in allmv if t[0] > 0.5)}, worst {allmv[0][4] - allmv[0][3]:+.3f} m')
    print(f'TOP {top} runway movers (lat, lon, base -> arm, dz, runway):')
    for a, la, lo, z0, z1, ref in allmv[:top]:
        print(f'  {la:.11f}, {lo:.11f}  {z0:.3f} -> {z1:.3f}  {z1 - z0:+.3f}  {ref}')


if __name__ == '__main__':
    main()
