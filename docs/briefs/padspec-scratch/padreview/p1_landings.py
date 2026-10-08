"""padreview P1: every landing record in a sidecar + its face in graded.json (level vs the ground beside it)."""
import json, sys, statistics, collections
side, graded = sys.argv[1], sys.argv[2]
d = json.load(open(side)); g = json.load(open(graded))
V = {v[0]: (v[1], v[2], v[3]) for v in g["vertices"]}
faces = g["faces"]
byref = collections.defaultdict(list)
for f in faces: byref[f["ref"]].append(f)
L = [r for r in d.get("platforms", []) if "landing" in r["ref"]]
print("==", side, "landing records", len(L))
for r in L:
    keys = {k: r[k] for k in r if k not in ("released_ll", "reach_bands_contacts", "contacts_ll")}
    print(json.dumps(keys, default=str)[:900])
# landing faces and neighbours
landing_faces = [f for f in faces if "landing" in f["ref"]]
print("landing faces", len(landing_faces))
vert_owner = collections.defaultdict(set)
for f in faces:
    for i in f["ring"]: vert_owner[i].add((f["role"], f["ref"]))
for f in landing_faces:
    zs = [V[i][2] for i in f["ring"] if i in V]
    nb = collections.Counter()
    for i in f["ring"]:
        for o in vert_owner[i]:
            if o[1] != f["ref"]: nb[o] += 1
    print(f" {f['ref']:32s} role {f['role']:12s} n {len(zs)} z med {statistics.median(zs):.3f} min {min(zs):.3f} max {max(zs):.3f} | shares vertices with {dict(nb.most_common(6))}")
    # shared neighbour z
    for o, _ in nb.most_common(4):
        sh = [V[i][2] for i in f["ring"] if o in vert_owner[i] and i in V]
        nbz = [V[i][2] for ff in byref[o[1]] for i in ff["ring"] if i in V]
        print(f"     {o}: shared n {len(sh)} z med {statistics.median(sh):.3f}; that face z med {statistics.median(nbz):.3f} min {min(nbz):.3f} max {max(nbz):.3f}")
