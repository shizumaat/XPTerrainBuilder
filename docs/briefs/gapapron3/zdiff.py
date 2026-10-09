"""true (unrounded) per-vertex z delta between two --solved-out pickles, by role family."""
import sys, pickle, collections, math
sys.path[:0] = ["src", ".", "tools"]
a, b = sys.argv[1], sys.argv[2]
roles = set(sys.argv[3].split(","))
out = sys.argv[4] if len(sys.argv) > 4 else None
def load(p):
    with open(p, "rb") as fh:
        sv = pickle.load(fh)
    pm, z = sv["pm"], sv["z"]
    d = {}
    for f in pm.faces.values():
        if f.role not in roles: continue
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                try: zz = float(z[v])
                except Exception: continue
                d[tuple(pm.vertices[v].key)] = (zz, f.ref, v)
    return d
A = load(a); B = load(b)
print(len(A), len(B), len(set(A) & set(B)))
rows = sorted(((B[k][0] - A[k][0], k, A[k][1], A[k][2], B[k][2]) for k in A if k in B), key=lambda t: -abs(t[0]))
by = collections.defaultdict(list)
for r in rows: by[r[2]].append(r)
for ref, rs in by.items():
    ds = [r[0] for r in rs]
    print(ref, "n", len(rs), "max|dz| %.4f" % max(abs(x) for x in ds), "mean %.4f" % (sum(ds)/len(ds)),
          ">0.01:", sum(abs(x) > 0.01 for x in ds), ">0.005:", sum(abs(x) > 0.005 for x in ds), ">0.001:", sum(abs(x) > 0.001 for x in ds))
for r in rows[:25]:
    print("%+.4f" % r[0], "%.8f,%.8f" % r[1][:2] if len(r[1])>=2 else r[1], r[2], "vA", r[3], "vB", r[4])
if out:
    import json; json.dump([[r[0], list(r[1]), r[2], r[3], r[4]] for r in rows], open(out, "w"))
