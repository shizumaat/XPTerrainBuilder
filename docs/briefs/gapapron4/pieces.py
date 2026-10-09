"""per apron part: level A (late gap:<k> parts) -> B (gapapron:<j>), and the worst
standing apron / taxi move B0 -> BBASE within R m of the part (proximity, not causation)."""
import sys, pickle, json, collections
sys.path[:0] = ["src", ".", "tools"]
import numpy as np
from shapely.geometry import Polygon, Point
from auto_patch_v2.law import Law
b0, bb, a, b, clp, out = sys.argv[1:7]
R = 150.0
cl = pickle.load(open(clp, "rb"))["cl"]
jk = {c.ref: c.evidence["gap_ref"] for c in cl.cells if str(c.ref).startswith("gapapron:")}
poly = {c.ref: Polygon(c.ring, c.holes) for c in cl.cells if str(c.ref).startswith("gapapron:")}
def load(p):
    sv = pickle.load(open(p, "rb")); return sv["pm"], sv["z"], sv["airport"]
def face_levels(pm, z, pred):
    d = collections.defaultdict(list)
    for f in pm.faces.values():
        if pred(str(f.ref)):
            for ring in (f.ring, *f.holes):
                for v in pm.ring_vertices(ring):
                    d[str(f.ref).split("/")[0].split("#")[0]].append(float(z[v]))
    return d
pmA, zA, ap = load(a); LA = face_levels(pmA, zA, lambda r: r.startswith("gap:")); del pmA, zA
pmB, zB, _ = load(b); LB = face_levels(pmB, zB, lambda r: r.startswith("gapapron:")); del pmB, zB
law = Law.for_airport("HECA"); p = law.tables.precedence
taxi = set(p.taxi_family.members); rw = set(p.runway_family.members)
def verts(pm, z):
    d = {}
    for f in pm.faces.values():
        fam = "apron" if f.role == "apron" else "taxi" if f.role in taxi else "runway" if f.role in rw else None
        if fam is None or str(f.ref).startswith("gapapron:"): continue
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                vx = pm.vertices[v]
                d.setdefault((tuple(vx.key), fam), (float(z[v]), f.ref, f.role, tuple(vx.xy)))
    return d
pm0, z0, _ = load(b0); V0 = verts(pm0, z0); del pm0, z0
pm1, z1, _ = load(bb); V1 = verts(pm1, z1); del pm1, z1
to_ll = ap.frame.transformers()[1]
mv = [(V1[k][0] - V0[k][0], k[1], V0[k][1], V0[k][2], V0[k][3], V0[k][0], V1[k][0]) for k in V0 if k in V1]
print("joined", len(mv), "of", len(V0), len(V1))
for fam in ("apron", "taxi", "runway"):
    m = [x for x in mv if x[1] == fam]
    w = max(m, key=lambda x: abs(x[0]))
    print(f"{fam}: nodes {len(m)}, >0.01 m {sum(abs(x[0])>0.01 for x in m)}, >0.1 {sum(abs(x[0])>0.1 for x in m)}, >1.0 {sum(abs(x[0])>1.0 for x in m)}; worst {w[0]:+.4f} m {w[2]} ({w[3]}) at %.7f, %.7f  {w[5]:.2f} -> {w[6]:.2f}" % to_ll(*w[4]))
rows = []
for j, k in sorted(jk.items(), key=lambda t: int(t[0].split(":")[1])):
    q = poly[j]; rp = q.representative_point(); lat, lon = to_ll(rp.x, rp.y)
    la, lb = LA.get(k, []), LB.get(j, [])
    row = {"ref": j, "gap_ref": k, "m2": round(q.area), "at": f"{lat:.7f}, {lon:.7f}",
           "A": [round(min(la), 2), round(float(np.mean(la)), 2), round(max(la), 2)] if la else None,
           "B": [round(min(lb), 2), round(float(np.mean(lb)), 2), round(max(lb), 2)] if lb else None}
    for fam in ("apron", "taxi", "runway"):
        near = [x for x in mv if x[1] == fam and q.distance(Point(*x[4])) <= R]
        if near:
            w = max(near, key=lambda x: abs(x[0]))
            row[fam] = {"dz": round(w[0], 3), "ref": w[2], "role": w[3], "at": "%.7f, %.7f" % to_ll(*w[4]), "z": [round(w[5], 2), round(w[6], 2)], "n>0.01": sum(abs(x[0]) > 0.01 for x in near)}
    rows.append(row)
    print(j, k, row["m2"], row["at"], "A", row["A"], "B", row["B"], "| apron", row.get("apron"), "| taxi", row.get("taxi"), "| runway", row.get("runway"))
json.dump(rows, open(out, "w"), indent=1)
