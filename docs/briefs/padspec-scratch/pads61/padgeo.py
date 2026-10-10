"""pads61: the emitted pad of one building ref in two arms — area, faces, and where the symmetric difference stands
(parts over MIN m2, with the roles of the OTHER arm's faces there).  usage: padgeo.py A.graded.json B.graded.json REF [MIN]"""
import json, sys, math
from shapely.geometry import Polygon
from shapely.ops import unary_union
ref = sys.argv[3]; mn = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
def load(p):
    g = json.load(open(p)); V = {v[0]: (v[1], v[2]) for v in g["vertices"]}
    return g, V
(ga, Va), (gb, Vb) = load(sys.argv[1]), load(sys.argv[2])
la0, lo0 = next(iter(Va.values())); kx = 111320.0 * math.cos(math.radians(la0)); ky = 111320.0
def poly(f, V):
    xy = lambda i: ((V[i][1] - lo0) * kx, (V[i][0] - la0) * ky)
    p = Polygon([xy(i) for i in f["ring"] if i in V], [[xy(i) for i in h if i in V] for h in f.get("holes", ()) if len(h) >= 3])
    return p if p.is_valid else p.buffer(0)
def pad(g, V):
    fs = [f for f in g["faces"] if f["role"] == "building" and str(f.get("ref", "")).split("#")[0] == ref]
    return unary_union([poly(f, V) for f in fs]), len(fs)
pa, na = pad(ga, Va); pb, nb = pad(gb, Vb)
print(f"{ref}: A {pa.area:,.1f} m2 in {na} faces; B {pb.area:,.1f} m2 in {nb} faces")
def what(g, V, q):
    out = {}
    for f in g["faces"]:
        p = poly(f, V)
        if p.intersects(q):
            a = p.intersection(q).area
            if a > 0.05: out[f"{f['role']}:{f.get('ref')}"] = round(a, 1)
    return out
for name, d, og, oV in (("A-only", pa.difference(pb), gb, Vb), ("B-only", pb.difference(pa), ga, Va)):
    parts = sorted([q for q in getattr(d, "geoms", [d]) if q.area >= mn], key=lambda q: -q.area)
    print(f" {name}: {d.area:,.1f} m2 total; {len(parts)} parts over {mn} m2")
    for q in parts[:14]:
        c = q.representative_point()
        print(f"   {q.area:8.1f} m2 at {la0 + c.y / ky:.7f}, {lo0 + c.x / kx:.7f}  there in the other arm: {what(og, oV, q)}")
