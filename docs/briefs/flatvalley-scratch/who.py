"""lane flatvalley scratch: WHO are the flat columns (roles, refs, clusters) — joins the QP dump to the solved pickle by key."""
import pickle, sys, collections
import numpy as np
sys.path.insert(0, "/Users/noah/XPTerrainBuilder/.claude/worktrees/flatvalley/Ortho4XP/src")


def main():
    qp, solved = sys.argv[1], sys.argv[2]
    q = pickle.load(open(qp, "rb"))
    part = np.load(qp + ".flatshare.npy")
    col, keys, xy = q["col"], q["keys"], q["xy"]
    sv = pickle.load(open(solved, "rb"))
    pm = sv["pm"]
    roles = collections.defaultdict(set); refs = collections.defaultdict(set)
    for f in pm.faces.values():
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                k = tuple(pm.vertices[v].key)
                roles[k].add(f.role); refs[k].add((f.role, str(f.ref)))
    own = [o[0] if o else "other" for o in q["owner"]]
    A0 = q["A0"].tocoo()
    has = collections.defaultdict(set)
    for r, c in zip(A0.row, A0.col):
        has[int(c)].add(own[r])
    U = q["U"]
    in_u = set(U.tocoo().col.tolist()) if U is not None else set()
    n = part.size
    vs_of = collections.defaultdict(list)
    for v, c in enumerate(col):
        if c >= 0:
            vs_of[int(c)].append(v)
    bend_only = [c for c in range(n) if has[c] <= {"bend"}]
    print(f"columns {n}; bend-only columns (no level term of their own) {len(bend_only)}; of them in a body-datum row {sum(1 for c in bend_only if c in in_u)}; "
          f"columns with NO always-on row at all {sum(1 for c in range(n) if not has[c])}")
    for name, sel in (("flat share>0.5", np.flatnonzero(part > 0.5)), ("flat share>0.1", np.flatnonzero(part > 0.1)),
                      ("bend-only", np.array(bend_only)), ("all", np.arange(n))):
        rc = collections.Counter(); tc = collections.Counter(); inu = 0
        for c in sel:
            rs = set()
            for v in vs_of[int(c)]:
                rs |= roles.get(tuple(keys[v]), {"?"})
            rc["+".join(sorted(rs))] += 1
            tc["+".join(sorted(has[int(c)])) or "-"] += 1
            inu += int(c) in in_u
        print(f"== {name}: {len(sel)} columns; in a datum row {inu}\n   roles {rc.most_common(8)}\n   terms {tc.most_common(6)}")
    # clusters of the flat columns (share>0.1), 60 m single linkage on a grid
    sel = np.flatnonzero(part > 0.1)
    pts = np.array([xy[vs_of[int(c)][0]] for c in sel])
    cell = collections.defaultdict(list)
    for i, p in enumerate(pts):
        cell[(int(p[0] // 80), int(p[1] // 80))].append(i)
    seen = set(); clusters = []
    for k0 in cell:
        if k0 in seen: continue
        stack = [k0]; seen.add(k0); mem = []
        while stack:
            a = stack.pop(); mem += cell[a]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    b = (a[0] + dx, a[1] + dy)
                    if b in cell and b not in seen: seen.add(b); stack.append(b)
        clusters.append(mem)
    clusters.sort(key=len, reverse=True)
    print(f"flat columns (share>0.1) in {len(clusters)} clusters; largest:")
    for mem in clusters[:8]:
        c0 = int(sel[mem[0]]); v0 = vs_of[c0][0]
        rr = collections.Counter(r for i in mem for v in vs_of[int(sel[i])] for r in refs.get(tuple(keys[v]), ()))
        print(f"   {len(mem)} cols near {keys[v0][0]:.8f},{keys[v0][1]:.8f}  refs {rr.most_common(4)}")


if __name__ == "__main__":
    main()
