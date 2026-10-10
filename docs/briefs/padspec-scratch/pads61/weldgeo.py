"""pads61: where two arms' pad faces differ ON airside — per building ref, the ring vertices shared with a non-building face
(the welded candidates) present in one arm and not the other.  usage: weldgeo.py A.graded.json B.graded.json refA [refB]"""
import json, sys, collections
def load(p, ref):
    g = json.load(open(p)); V = {v[0]: (round(v[1], 7), round(v[2], 7)) for v in g["vertices"]}
    padv, other = set(), collections.defaultdict(set)
    for f in g["faces"]:
        ring = [V[i] for i in f["ring"] if i in V] + [V[i] for h in f.get("holes", ()) for i in h if i in V]
        base = str(f.get("ref", "")).split("#")[0]
        if f["role"] == "building" and base == ref: padv.update(ring)
        elif f["role"] != "building":
            for q in ring: other[q].add(f["role"])
    return padv, other
a, oa = load(sys.argv[1], sys.argv[3]); b, ob = load(sys.argv[2], sys.argv[4] if len(sys.argv) > 4 else sys.argv[3])
wa = {q for q in a if q in oa}; wb = {q for q in b if q in ob}
print(f"pad vertices A {len(a)} B {len(b)}; shared with another face A {len(wa)} B {len(wb)}; A-only {len(wa - wb)} B-only {len(wb - wa)}")
for name, s, o in (("A-only", wa - wb, oa), ("B-only", wb - wa, ob)):
    for q in sorted(s)[:40]: print(f"  {name} {q[0]},{q[1]} {sorted(o[q])}")
