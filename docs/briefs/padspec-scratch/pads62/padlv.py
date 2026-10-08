"""pads62 scratch: building-role faces within R m of a site (graded.json): ref, area, ring vertices, z min/max; plus sidecar platform record.
usage: padlv.py TAG ICAO lat lon R"""
import json, sys, math
from shapely.geometry import Polygon, Point
t, a = sys.argv[1:3]; la, lo, R = map(float, sys.argv[3:6])
g = json.load(open(f"/tmp/harness/{t}.v2/{a}.graded.json")); sc = json.load(open(f"/tmp/harness/{t}.osm.axes.json"))
V = {v[0]: (v[1], v[2], v[3]) for v in g["vertices"]}
mx = 111320 * math.cos(math.radians(la)); my = 110574
P = {p["ref"]: p for p in sc.get("platforms") or []}
print("==", t, la, lo, "r", R)
for f in g["faces"]:
    if f["role"] != "building": continue
    r = [((V[i][1] - lo) * mx, (V[i][0] - la) * my) for i in f["ring"] if i in V]
    if len(r) < 3: continue
    p = Polygon(r); p = p if p.is_valid else p.buffer(0)
    if p.distance(Point(0, 0)) > R: continue
    ids = list(f["ring"]) + [j for h in f.get("holes", []) or [] for j in h]
    zs = [V[i][2] for i in ids]
    pr = P.get(f["ref"]) or {}
    print(f"  {f['ref']:30s} {p.area:9.0f} m2 v {len(ids):4d} z {min(zs):7.2f}..{max(zs):7.2f} spread {max(zs)-min(zs):5.2f}  datum {pr.get('datum')} welded {pr.get('welded')} released {pr.get('released')}/{pr.get('released_max_m')}")
