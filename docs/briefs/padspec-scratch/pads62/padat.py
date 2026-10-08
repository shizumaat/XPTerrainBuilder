"""pads62 scratch: for each site, the building-role face of a graded.json containing (or nearest to) the point, with its rim z spread.
usage: padat.py GRADED lat,lon ..."""
import json, sys, math
from shapely.geometry import Polygon, Point
g = json.load(open(sys.argv[1])); V = {v[0]: (v[1], v[2], v[3]) for v in g["vertices"]}
B = []
for f in g["faces"]:
    if f["role"] != "building": continue
    r = [V[i] for i in f["ring"] if i in V]
    if len(r) < 3: continue
    B.append((f, Polygon([(p[1], p[0]) for p in r]), [p[2] for p in r]))
for s in sys.argv[2:]:
    la, lo = map(float, s.split(",")); pt = Point(lo, la)
    hit = [b for b in B if b[1].is_valid and b[1].contains(pt)]
    how = "in"
    if not hit:
        hit = [min(B, key=lambda b: b[1].distance(pt))]; how = "near %.1fm" % (hit[0][1].distance(pt) * 111320 * math.cos(math.radians(la)) if True else 0)
    hit.sort(key=lambda b: -b[1].area)
    for f, poly, zs in hit[:2]:
        a = poly.area * 111320 * 110574 * math.cos(math.radians(la))
        print(f"{s:26s} {how:10s} {f['ref']:28s} area {a:9.0f} m2 ringv {len(zs):5d} z {min(zs):7.3f}..{max(zs):7.3f} spread {max(zs)-min(zs):.3f}")
