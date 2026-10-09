"""lane flatvalley scratch: movers of one stage call between two arms, by role, with clusters. mv.py A B K SOLVED.pkl"""
import pickle, sys, collections, json
import numpy as np
sys.path.insert(0, "/Users/noah/XPTerrainBuilder/.claude/worktrees/valleyspec/Ortho4XP/src")


def main():
    a, b, k, solved = sys.argv[1:5]
    za, zb, keys = np.load(f"{a}/z_{k}.npy"), np.load(f"{b}/z_{k}.npy"), np.load(f"{a}/k_{k}.npy")
    pm = pickle.load(open(solved, "rb"))["pm"]
    roles = collections.defaultdict(set); refs = collections.defaultdict(set)
    for f in pm.faces.values():
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                kk = tuple(pm.vertices[v].key); roles[kk].add(f.role); refs[kk].add(str(f.ref))
    d = zb - za
    mv = np.flatnonzero(np.abs(d) > 0.02)
    print(f"stage call {k}: movers>0.02 {mv.size}, >0.1 {int((np.abs(d)>0.1).sum())}, >0.3 {int((np.abs(d)>0.3).sum())}, worst {np.abs(d).max():.3f}")
    by = collections.defaultdict(list)
    for v in mv:
        for r in roles.get(tuple(keys[v]), {"?"}): by[r].append(v)
    for r, L in sorted(by.items(), key=lambda t: -len(t[1])):
        w = max(L, key=lambda v: abs(d[v]))
        print(f"   {r:20s} {len(L):5d} worst {d[w]:+.3f} at {keys[w][0]:.11f}, {keys[w][1]:.11f} {sorted(refs.get(tuple(keys[w]), []))[:3]}")
    # clusters (100 m grid linkage, degrees ~ 1e-3)
    cell = collections.defaultdict(list)
    for v in mv: cell[(int(keys[v][0] / 0.001), int(keys[v][1] / 0.001))].append(v)
    seen = set(); cl = []
    for c0 in cell:
        if c0 in seen: continue
        st = [c0]; seen.add(c0); mem = []
        while st:
            c = st.pop(); mem += cell[c]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dy)
                    if n in cell and n not in seen: seen.add(n); st.append(n)
        cl.append(mem)
    cl.sort(key=len, reverse=True)
    print(f"   {len(cl)} clusters; largest: " + "; ".join(f"{len(m)} near {keys[max(m, key=lambda v: abs(d[v]))][0]:.8f},{keys[max(m, key=lambda v: abs(d[v]))][1]:.8f} (worst {max(abs(d[v]) for v in m):.2f})" for m in cl[:6]))


if __name__ == "__main__":
    main()
