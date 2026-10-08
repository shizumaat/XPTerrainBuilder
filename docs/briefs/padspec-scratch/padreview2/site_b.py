"""padreview2 B: the OTHH within_shape site — every vertex within R m of a site in a graded.json, with z, the
roles/refs that own it, and (for the building faces there) how many ring vertices stand over the pad's datum."""
import json, sys, math, collections
g = json.load(open(sys.argv[1])); lat0, lon0 = map(float, sys.argv[2].split(",")); R = float(sys.argv[3])
mlat = 111_320.0; mlon = 111_320.0 * math.cos(math.radians(lat0))
V = {v[0]: (v[1], v[2], v[3]) for v in g["vertices"]}
own = collections.defaultdict(set)
for f in g["faces"]:
    for i in list(f["ring"]) + [j for h in f.get("holes", []) for j in h]:
        own[i].add((f["role"], f["ref"]))
near = [(i, V[i]) for i in V if math.hypot((V[i][0] - lat0) * mlat, (V[i][1] - lon0) * mlon) <= R]
print(sys.argv[1], "vertices within", R, "m:", len(near))
for i, (la, lo, z) in sorted(near, key=lambda t: -t[1][2])[:int(sys.argv[4]) if len(sys.argv) > 4 else 25]:
    print(f"  z {z:8.3f} at {la:.7f},{lo:.7f}  {sorted(own[i])}")
# the building faces touching the site: z histogram of their rings
for f in g["faces"]:
    if f["role"] != "building":
        continue
    ids = list(f["ring"])
    if not any(i in dict(near) for i in ids):
        continue
    zs = sorted(V[i][2] for i in ids)
    med = zs[len(zs) // 2]
    hi = [(V[i][2], sorted(own[i] - {(f["role"], f["ref"])})) for i in ids if V[i][2] > med + 0.5]
    roles = collections.Counter(r for z_, o in hi for r, _ in o)
    print(f"face {f['ref']:28s} n {len(ids):5d} z med {med:.3f} min {zs[0]:.3f} max {zs[-1]:.3f}  over med+0.5: {len(hi)}  co-owned by {dict(roles.most_common(6))}")
