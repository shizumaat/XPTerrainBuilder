"""padreview2 A: trace a ref's vertices between two graded.json arms (A -> B): per-vertex dz along the ref, and the
building faces within R m of it in B with their level in A and B — the chain pad rim -> welded road -> strip.
usage: roadtrace.py A.graded.json B.graded.json REF_SUBSTRING [R=60]"""
import json, sys, math, collections, statistics
def load(f):
    d = json.load(open(f)); V = {v[0]: (v[1], v[2], v[3]) for v in d["vertices"]}
    z = {(v[1], v[2]): v[3] for v in d["vertices"]}
    faces = collections.defaultdict(list)
    for fc in d["faces"]:
        faces[(fc["role"], fc["ref"])].append([V[i] for i in fc["ring"] if i in V])
    return z, faces
za, fa = load(sys.argv[1]); zb, fb = load(sys.argv[2]); sub = sys.argv[3]; R = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
hits = [k for k in fb if sub in k[1]]
print("refs matching", sub, ":", hits[:8])
pts = []
for k in hits:
    for ring in fb[k]:
        for la, lo, z in ring:
            pts.append((la, lo))
            d = z - za.get((la, lo), float("nan"))
            print(f"  {k[1]:28s} {la:.7f},{lo:.7f}  zA {za.get((la, lo), float('nan')):8.3f} zB {z:8.3f} dz {d:+.3f}")
if not pts:
    sys.exit()
la0 = pts[0][0]; mlat = 111_320.0; mlon = 111_320.0 * math.cos(math.radians(la0))
def near(ring):
    return any(math.hypot((la - p[0]) * mlat, (lo - p[1]) * mlon) <= R for la, lo, _z in ring for p in pts[::3])
print(f"-- building / pad faces within {R} m of it:")
for k, rings in fb.items():
    if k[0] != "building":
        continue
    for ring in rings:
        if near(ring):
            zsb = [z for _a, _b, z in ring]; zsa = [za[(a, b)] for a, b, _z in ring if (a, b) in za]
            print(f"   {k[1]:28s} n {len(ring):4d} level B med {statistics.median(zsb):8.3f} (min {min(zsb):.2f} max {max(zsb):.2f}) | same vertices in A: {len(zsa)} med {statistics.median(zsa) if zsa else float('nan'):8.3f}")
print("-- building faces in A near it (by A's own refs):")
for k, rings in fa.items():
    if k[0] != "building":
        continue
    for ring in rings:
        if near(ring):
            zs = [z for _a, _b, z in ring]
            print(f"   {k[1]:28s} n {len(ring):4d} level A med {statistics.median(zs):8.3f} (min {min(zs):.2f} max {max(zs):.2f})")
