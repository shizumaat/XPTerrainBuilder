"""noown.py GRADED.json SIDECAR.json — the pads (building faces by ref) with NO vertex of their own (every vertex is
also on a non-pad face), their relief, what carries their rim, and whether the sidecar holds them (a read)."""
import collections, json, math, sys


def main(gp, sp):
    G = json.load(open(gp)); X = json.load(open(sp))
    V = {v[0]: v for v in G["vertices"]}
    held = {p["ref"]: p for p in X.get("platforms", [])}
    use = collections.defaultdict(set)          # vertex -> {(role, ref, 'ring'|'hole')}
    for f in G["faces"]:
        for i in f["ring"]:
            use[i].add((f["role"], f["ref"], "ring"))
        for h in f.get("holes", []):
            for i in h:
                use[i].add((f["role"], f["ref"], "hole"))
    pads = collections.defaultdict(set)
    for f in G["faces"]:
        if f["role"] == "building":
            pads[f["ref"].split("#")[0]].update(f["ring"])
    rows = []
    for ref, vs in pads.items():
        own = [i for i in vs if all(r == "building" for r, _q, _k in use[i])]
        zs = [V[i][3] for i in vs]
        carriers = collections.Counter((r, q, k) for i in vs for r, q, k in use[i] if r != "building")
        hp = held.get(ref)
        rows.append((ref, len(vs), len(own), round(max(zs) - min(zs), 2), hp.get("hold_verdict") if hp else "NO RECORD",
                     hp.get("datum") if hp else None, carriers.most_common(2), f"{V[next(iter(vs))][1]:.8f}, {V[next(iter(vs))][2]:.8f}"))
    no = [r for r in rows if r[2] == 0]
    print(f"pads {len(rows)}; with NO own vertex {len(no)}; of those with relief > 0.05 m: {sum(1 for r in no if r[3] > 0.05)}; "
          f"pads WITH an own vertex and relief > 0.05 m: {sum(1 for r in rows if r[2] and r[3] > 0.05)}")
    for r in sorted(no, key=lambda r: -r[3])[:14]:
        print("  ", r)
    print(" tilted WITH own vertex:", sorted([(r[0], r[1], r[2], r[3], r[4]) for r in rows if r[2] and r[3] > 0.05], key=lambda r: -r[3])[:10])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
