"""pads62 scratch: gap_pieces count (sidecar) and the face containing each pavement-gap owner site (graded.json).
usage: gapsite.py TAG ICAO"""
import json, sys
from shapely.geometry import Polygon, Point
t, a = sys.argv[1:3]
sc = json.load(open(f"/tmp/harness/{t}.osm.axes.json")); g = json.load(open(f"/tmp/harness/{t}.v2/{a}.graded.json"))
gp = sc.get("gap_pieces")
print(t, "gap_pieces:", (len(gp) if isinstance(gp, list) else gp if not isinstance(gp, dict) else {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in gp.items()}))
V = {v[0]: (v[1], v[2], v[3]) for v in g["vertices"]}
print("  faces with ref gap:*", sum(1 for f in g["faces"] if str(f["ref"]).startswith("gap:")), "distinct refs", len({f["ref"] for f in g["faces"] if str(f["ref"]).startswith("gap:")}))
for la, lo in ((30.1154841, 31.4105884), (30.1159784, 31.4106264), (30.1193169, 31.4085087)):
    hit = []
    for f in g["faces"]:
        r = [(V[i][1], V[i][0]) for i in f["ring"] if i in V]
        if len(r) >= 3:
            p = Polygon(r)
            if p.is_valid and p.contains(Point(lo, la)):
                zs = [V[i][2] for i in f["ring"]]; hit.append((f["ref"], f["role"], round(min(zs), 2), round(max(zs), 2)))
    print(f"  {la},{lo}: {hit}")
