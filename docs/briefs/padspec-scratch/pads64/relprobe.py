"""pads64 scratch: every RELEASED frontage contact of a --solved-out pickle read against its own rows: the hold row
(contact = datum column), the datum column's value, the rows naming the contact that are tight or violated at the solved
values, and whether the contact is an unknown of stage 1 / stage 2.
usage: (cd Ortho4XP &&) venv/bin/python ../docs/briefs/padspec-scratch/pads64/relprobe.py SOLVED.pkl SIDECAR.axes.json [REF...]"""
import pickle, json, sys, collections
sys.path.insert(0, "src")
from auto_patch_v2.model.constraints import Diff, Linear, Band, Pin
sv = pickle.load(open(sys.argv[1], "rb")); sc = json.load(open(sys.argv[2])); want = set(sys.argv[3:])
print("solved keys:", sorted(sv.keys()))
pm, cs, z = sv["pm"], sv["cs"], sv["z"]
k11 = lambda ll: (round(float(ll[0]), 11), round(float(ll[1]), 11))
key2v = {k11(v.key): i for i, v in pm.vertices.items()}
head = lambda r: r.source.ruling.split(" (")[0].strip()
roles = lambda v: "|".join(sorted({pm.faces[f].role for f in pm.vertices[v].incident_faces})) if v in pm.vertices and hasattr(pm.vertices[v], "incident_faces") else "?"
by_v = collections.defaultdict(list)
for r in cs.rows():
    if isinstance(r, Diff): vs = (int(r.a), int(r.b))
    elif isinstance(r, Linear): vs = tuple(int(v) for v, _c in r.terms)
    elif isinstance(r, (Band, Pin)): vs = (int(r.v),)
    else: continue
    for v in vs: by_v[v].append(r)
def viol(r):
    if isinstance(r, Diff):
        return abs(float(z[int(r.a)]) - float(z[int(r.b)]) - float(getattr(r, "rel", 0.0))) - r.cap * r.d
    if isinstance(r, Linear):
        s = sum(float(c) * float(z[int(v)]) for v, c in r.terms)
        return max((r.lo - s) if r.lo is not None else -1e9, (s - r.hi) if r.hi is not None else -1e9)
    if isinstance(r, Band):
        return max((r.lo - float(z[int(r.v)])) if r.lo is not None else -1e9, (float(z[int(r.v)]) - r.hi) if r.hi is not None else -1e9)
    if isinstance(r, Pin): return abs(float(z[int(r.v)]) - float(r.z))
for p in sc["platforms"]:
    if not p.get("released") or (want and p["ref"] not in want): continue
    print(f"== {p['ref']} datum {p['datum']} median {p.get('datum_median')} released {p['released']} max {p['released_max_m']} misfit {p.get('misfit_m')} band {p.get('reach_band')} isect {p.get('reach_isect')}")
    for ll in p["released_ll"]:
        v = key2v.get(k11(ll))
        if v is None: print("   contact", ll, "NOT IN MAP"); continue
        rows = by_v[v]
        print(f"   contact v{v} {ll} z {float(z[v]):.4f} (D{float(z[v]) - p['datum']:+.4f}) [{roles(v)}] rows {len(rows)}")
        vs = sorted(((viol(r), r) for r in rows), key=lambda t: -t[0])
        for x, r in vs[:6]:
            extra = (f"d {r.d:.1f} cap {100*r.cap:.2f}% other z {float(z[int(r.b) if int(r.a)==v else int(r.a)]):.4f}" if isinstance(r, Diff) else
                     f"terms {[(int(a), round(float(c),3), round(float(z[int(a)]),4)) for a, c in r.terms][:4]} lo {r.lo} hi {r.hi}" if isinstance(r, Linear) else
                     f"lo {r.lo} hi {r.hi}" if isinstance(r, Band) else f"z {r.z}")
            print(f"      {x:+.4f}  {type(r).__name__:6s} {r.source.generator} | {head(r)[:70]} | {extra}")
