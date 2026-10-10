"""padspec2 — what EMITTED face lies under a jetway rider's anchor, and 4 m / 8 m
further out along the outward normal of the nearest unit outline?  If apron:
the root stands on airside (airside is king: the outline cannot take it);
if service_road / groundside: the strip between face and apron the near-road
absorption (§56 (2)) turns into pad.  usage: anchor_role_probe.py ICAO CAP.pkl GRADED.json RIDERS.json"""
import json, pickle, sys, math, collections
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
from shapely.ops import nearest_points
sys.path.insert(0, "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padspec2")
from rider_probe import outlines
from auto_patch_v2.law import Law
icao, pkl, graded, rj = sys.argv[1:5]
cap = pickle.load(open(pkl, "rb")); airport = cap["airport"]; law = Law.for_airport(icao); to_xy = airport.frame.entry()
today, _ = outlines(icao, airport, law, to_xy, None)
G = json.load(open(graded)); V = {v[0]: to_xy(v[2], v[1]) for v in G["vertices"]}
faces = []
for f in G["faces"]:
    ring = [V[i] for i in f["ring"] if i in V]
    if len(ring) < 3: continue
    p = Polygon(ring, [[V[i] for i in h if i in V] for h in f.get("holes", [])]); p = p if p.is_valid else p.buffer(0)
    faces.append((f.get("role"), str(f.get("ref")), p))
tree = STRtree([p for _r, _f, p in faces])
def role_at(pt):
    for k in tree.query(pt, predicate="within"):
        r, f, p = faces[int(k)]
        return r + ("" if r != "building" else ("#collar" if "#collar" in f else ""))
    return "ground"
rows = json.load(open(rj))["rows"]
objs = {o.id: o for o in airport.dsf_objects}
jet = [r for r in rows if any(j in r["res"].lower() for j in ("jetway", "jet_way", "no_glass")) and "tug" not in r["res"].lower()]
c = collections.Counter(); c4 = collections.Counter(); c8 = collections.Counter(); cin = collections.Counter()
for r in jet:
    o = objs[r["id"]]; pt = Point(*o.xy); poly = today[r["unit"]]
    q = nearest_points(poly.exterior, pt)[0]
    dx, dy = pt.x - q.x, pt.y - q.y; L = math.hypot(dx, dy) or 1.0
    if poly.contains(pt): dx, dy = -dx, -dy
    out4 = Point(q.x + 4 * dx / L, q.y + 4 * dy / L); out8 = Point(q.x + 8 * dx / L, q.y + 8 * dy / L); in2 = Point(q.x - 2 * dx / L, q.y - 2 * dy / L)
    c[role_at(pt)] += 1; c4[role_at(out4)] += 1; c8[role_at(out8)] += 1; cin[role_at(in2)] += 1
print(f"{icao} jetway riders {len(jet)}")
print("  under the ANCHOR:", dict(c)); print("  4 m out from the face:", dict(c4)); print("  8 m out:", dict(c8)); print("  2 m INSIDE the face:", dict(cin))
