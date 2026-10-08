"""jetspec: do taxi centreline breaklines run INSIDE building (pad) faces today?
usage: python bl_check.py ICAO.graded.json ..."""
import json, sys, math
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree
for path in sys.argv[1:]:
    g = json.load(open(path)); lat0 = g['vertices'][0][1]
    mx = 111320.0 * math.cos(math.radians(lat0)); my = 110574.0
    V = {v[0]: ((v[2]) * mx, (v[1]) * my) for v in g['vertices']}
    pads = []
    for f in g['faces']:
        if f.get('role') == 'building':
            ring = [V[i] for i in f['ring']]
            p = Polygon(ring, [[V[i] for i in h] for h in f.get('holes', ())]); pads.append((f['ref'], p if p.is_valid else p.buffer(0)))
    tree = STRtree([p for _, p in pads])
    inside = 0; onrim = 0; total = 0; refs = {}
    for b in g['breaklines']:
        if b['kind'] != 'taxi_centerline':
            continue
        for vid in b['vertices']:
            total += 1; pt = Point(V[vid])
            for i in tree.query(pt):
                ref, p = pads[int(i)]
                if p.exterior.distance(pt) < 0.05 or any(h.distance(pt) < 0.05 for h in p.interiors):
                    onrim += 1
                elif p.contains(pt):
                    inside += 1; refs[ref] = refs.get(ref, 0) + 1
    print(f"{path}: taxi_centerline vertices {total}; on a pad rim {onrim}; strictly INSIDE a pad face {inside} {refs}")
