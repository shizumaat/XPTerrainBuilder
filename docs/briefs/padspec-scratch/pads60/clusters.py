"""pads60 scratch: taxi/runway/apron movers A -> B over TOL, clustered (single-link, 60 m); per cluster: n by role, worst, centroid, bbox, SW flag.
--list FILE writes every mover (lat lon dz roles refs)."""
import json, sys, collections, math
TAXI = {"junction", "cross_connector", "primary_parallel", "secondary_parallel", "stub", "runway"}; AIR = TAXI | {"apron"}
def load(f):
    d = json.load(open(f)); ids = {v[0]: (v[1], v[2]) for v in d["vertices"]}
    z = {(v[1], v[2]): v[3] for v in d["vertices"]}
    roles = collections.defaultdict(set); refs = collections.defaultdict(set)
    for f_ in d["faces"]:
        for i in list(f_["ring"]) + [j for h in f_.get("holes", []) for j in h]:
            roles[ids[i]].add(f_["role"]); refs[ids[i]].add(f_["ref"])
    return z, roles, refs
za, ra, fa = load(sys.argv[1]); zb, rb, fb = load(sys.argv[2]); tol = float(sys.argv[3])
mv = [(k, zb[k] - za[k]) for k in set(za) & set(zb) if abs(zb[k] - za[k]) > tol and (ra[k] | rb[k]) & AIR]
print("airside movers", len(mv), "taxi/runway-family", sum(1 for k, _ in mv if (ra[k] | rb[k]) & TAXI), "apron-only", sum(1 for k, _ in mv if not (ra[k] | rb[k]) & TAXI),
      "runway", sum(1 for k, _ in mv if "runway" in (ra[k] | rb[k])))
if "--list" in sys.argv:
    with open(sys.argv[sys.argv.index("--list") + 1], "w") as fh:
        for k, d in sorted(mv, key=lambda t: -abs(t[1])): fh.write(f"{k[0]:.9f} {k[1]:.9f} {d:+.3f} {','.join(sorted((ra[k]|rb[k]) & AIR))} {','.join(sorted(fb[k])[:3])}\n")
if not mv: sys.exit()
lat0 = mv[0][0][0]; mx = 111320 * math.cos(math.radians(lat0)); my = 110574
pts = [(k[1] * mx, k[0] * my) for k, _ in mv]; cell = collections.defaultdict(list)
for i, (x, y) in enumerate(pts): cell[(int(x // 60), int(y // 60))].append(i)
par = list(range(len(pts)))
def find(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for (cx, cy), L in cell.items():
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in cell.get((cx + dx, cy + dy), ()):
                for i in L:
                    if i < j and math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) <= 60: par[find(i)] = find(j)
cl = collections.defaultdict(list)
for i in range(len(pts)): cl[find(i)].append(i)
sw = lambda k: 30.1017 <= k[0] <= 30.1066 and 31.3967 <= k[1] <= 31.3990
print("clusters", len(cl))
for L in sorted(cl.values(), key=lambda L: -max(abs(mv[i][1]) for i in L))[:int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 20]:
    w = max(L, key=lambda i: abs(mv[i][1])); k = mv[w][0]
    rc = collections.Counter(r for i in L for r in (ra[mv[i][0]] | rb[mv[i][0]]) & AIR)
    la = [mv[i][0][0] for i in L]; lo = [mv[i][0][1] for i in L]
    print(f"  n {len(L):4d} worst {mv[w][1]:+.3f} at {k[0]:.7f}, {k[1]:.7f} | lat {min(la):.4f}..{max(la):.4f} lon {min(lo):.4f}..{max(lo):.4f} | SW-in {sum(1 for i in L if sw(mv[i][0]))} | {dict(rc)} | {sorted(fb[k])[:2]}")
