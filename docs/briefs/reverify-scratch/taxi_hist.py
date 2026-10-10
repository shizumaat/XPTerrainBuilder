"""reverify scratch: TAXI-family vertices BASE -> ARM binned by plan distance to the nearest pad-rim vertex
(sheetlevel movers_hist.py's read with the taxi roles).  usage: taxi_hist.py BASE_DIR ARM_DIR ICAO"""
import collections
import json
import math
import sys

import numpy as np
from scipy.spatial import cKDTree

TAXI = {'primary_parallel', 'secondary_parallel', 'cross_connector', 'stub', 'junction', 'runway_crossing'}


def main():
    B, A, icao = sys.argv[1:4]
    gb = json.load(open(f'{B}/emit/{icao}.graded.json'))
    ga = json.load(open(f'{A}/emit/{icao}.graded.json'))
    mx = 111320 * math.cos(math.radians(ga['frame']['origin'][0]))
    roles, pad = collections.defaultdict(set), set()
    for f in ga['faces']:
        vs = set(f['ring']) | {u for h in f['holes'] for u in h}
        for u in vs:
            roles[u].add(f['role'])
        if f['role'] == 'building':
            pad |= vs
    va = {r[0]: r for r in ga['vertices']}
    tree = cKDTree(np.array([(va[u][2] * mx, va[u][1] * 111320) for u in pad]))
    zb = {(round(r[1], 11), round(r[2], 11)): r[3] for r in gb['vertices']}
    bins = collections.defaultdict(list)
    for r in ga['vertices']:
        if not roles[r[0]] & TAXI or 'runway' in roles[r[0]]:
            continue
        z0 = zb.get((round(r[1], 11), round(r[2], 11)))
        if z0 is None:
            continue
        d = float(tree.query((r[2] * mx, r[1] * 111320))[0])
        k = '<30' if d < 30 else '30-60' if d < 60 else '60-200' if d < 200 else '200-500' if d < 500 else '>500'
        bins[k].append(r[3] - z0)
    print('TAXI vertices by distance to a pad rim: n / movers>0.02 / >0.1 / >0.3 / worst dz')
    for k in ('<30', '30-60', '60-200', '200-500', '>500'):
        L = bins.get(k, [])
        M = sorted((abs(x), x) for x in L if abs(x) > 0.02)
        print(f'  {k:8s} {len(L):6d} {len(M):6d} {sum(1 for a, _ in M if a > 0.1):6d} {sum(1 for a, _ in M if a > 0.3):6d}  '
              + (f'{M[-1][1]:+.2f}' if M else ''))


if __name__ == '__main__':
    main()
