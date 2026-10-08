"""pads60 scratch: taxi/runway/apron vertex movers between two graded.json arms (A -> B) over TOL, each with coordinates;
SW = inside the measured null-change region 30.1017-30.1066, 31.3967-31.3990 (spec 56 (10) F1)."""
import json, sys, collections
AIR = {"apron", "junction", "cross_connector", "primary_parallel", "secondary_parallel", "stub", "runway", "graded_strip"}
def load(f):
    d = json.load(open(f)); ids = {v[0]: (v[1], v[2]) for v in d["vertices"]}
    z = {(v[1], v[2]): v[3] for v in d["vertices"]}
    roles = collections.defaultdict(set); refs = collections.defaultdict(set)
    for f_ in d["faces"]:
        for i in list(f_["ring"]) + [j for h in f_.get("holes", []) for j in h]:
            roles[ids[i]].add(f_["role"]); refs[ids[i]].add(f_["ref"])
    return z, roles, refs
za, ra, fa = load(sys.argv[1]); zb, rb, fb = load(sys.argv[2]); tol = float(sys.argv[3]); top = int(sys.argv[4]) if len(sys.argv) > 4 else 12
sw = lambda k: 30.1017 <= k[0] <= 30.1066 and 31.3967 <= k[1] <= 31.3990
print("vertices", len(za), len(zb), "common", len(set(za) & set(zb)))
by = collections.defaultdict(list)
for k in set(za) & set(zb):
    d = zb[k] - za[k]
    if abs(d) > tol:
        for r in (ra[k] | rb[k]) & AIR: by[r].append((abs(d), d, k))
for r, L in sorted(by.items(), key=lambda t: -len(t[1])):
    L.sort(reverse=True); n_sw = sum(1 for x in L if sw(x[2]))
    print(f"{r:20s} movers {len(L):5d} (in SW region {n_sw}) worst {L[0][1]:+.3f}")
    for a_, d, k in L[:top]: print(f"     {d:+.3f} at {k[0]:.7f}, {k[1]:.7f} {'SW' if sw(k) else '  '} {sorted(fb[k])[:3]}")
