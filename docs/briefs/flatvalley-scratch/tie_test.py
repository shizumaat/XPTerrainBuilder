"""lane flatvalley scratch: QP-level arm test on one dumped stage QP.
For each candidate tie: (cost) distance of its optimum from today's exit; (stability) distance between
two solves of the SAME tied problem from two starts (today's exit vs exit + N(0, 0.3 m))."""
import pickle, sys, time, collections
import numpy as np, scipy.sparse as sp
sys.path.insert(0, "/Users/noah/XPTerrainBuilder/.claude/worktrees/flatvalley/Ortho4XP/src")
from auto_patch_v2.solve import design_qp


def main():
    q = pickle.load(open(sys.argv[1], "rb"))
    A0, b0, A1, b1, w, shift, U, c, x = (q[k] for k in ("A0", "b0", "A1", "b1", "w_row", "shift", "U", "c", "x"))
    kw = q["kw"]; col = q["col"]; n = A0.shape[1]
    own = [o[0] if o else "other" for o in q["owner"]]
    coo = A0.tocoo()
    has = collections.defaultdict(set)
    for r, cc in zip(coo.row, coo.col):
        has[int(cc)].add(own[r])
    free = np.array([cc for cc in range(n) if has[cc] <= {"bend"}])
    isfree = np.zeros(n, bool); isfree[free] = True
    # mesh adjacency from the bending rows (a Laplacian row = a vertex and its ring)
    bend_rows = np.flatnonzero(np.array(own) == "bend")
    A0r = A0.tocsr()
    nb = collections.defaultdict(set)
    for r in bend_rows:
        idx = A0r.indices[A0r.indptr[r]:A0r.indptr[r + 1]]; dat = A0r.data[A0r.indptr[r]:A0r.indptr[r + 1]]
        if idx.size < 2: continue
        ctr = int(idx[np.argmax(np.abs(dat))])
        for u in idx:
            if int(u) != ctr: nb[ctr].add(int(u)); nb[int(u)].add(ctr)
    dem = None
    if len(sys.argv) > 2:
        dem = np.load(sys.argv[2])       # per-column DEM (see mkdem)
    rng = np.random.default_rng(5)
    noise = rng.normal(0, 0.3, n)

    def run(name, T, t, rel):
        design_qp._REL_TOL = rel; design_qp._ROUNDS_MAX = 3000
        A = A0 if T is None else sp.vstack([A0, T], format="csr")
        b = b0 if T is None else np.concatenate([b0, t])
        t0 = time.perf_counter()
        r1 = design_qp.solve_one_sided(A, b, A1, b1, w, shift, x, U, c, **kw); t1 = time.perf_counter() - t0
        r2 = design_qp.solve_one_sided(A, b, A1, b1, w, shift, x + noise, U, c, **kw)
        r3 = design_qp.solve_one_sided(A, b, A1, b1, w, shift, None, U, c, **kw)
        d12 = np.abs(r1.x - r2.x); d13 = np.abs(r1.x - r3.x); dc = np.abs(r1.x - x)
        f = lambda d: f">0.02 {int((d>0.02).sum()):5d} >0.1 {int((d>0.1).sum()):4d} >0.3 {int((d>0.3).sum()):3d} max {d.max():.3f}"
        print(f"{name:26s} rel {rel:g}: [{r1.status} {r1.rounds}r {t1:.1f}s | {r2.status} {r2.rounds}r | cold {r3.status} {r3.rounds}r]\n"
              f"      stability warm-vs-noisy  {f(d12)}\n      stability warm-vs-cold   {f(d13)}\n      cost vs today's exit     {f(dc)}  (free cols only: {f(dc[free])})", flush=True)
        return r1.x

    print(f"columns {n}; free (bend-only) {free.size}; mesh edges at free columns {sum(len(nb[int(cc)]) for cc in free)}")
    for rel in (1e-9, 1e-12):
        run("no tie", None, None, rel)
    for eps in (0.03, 0.3, 3.0):
        rows, cols, vals = [], [], []
        k = 0
        for cc in free:
            for u in nb[int(cc)]:
                if isfree[u] and u < cc: continue      # a free-free edge once
                rows += [k, k]; cols += [int(cc), u]; vals += [np.sqrt(eps), -np.sqrt(eps)]; k += 1
        T = sp.csr_matrix((vals, (rows, cols)), shape=(k, n))
        for rel in (1e-9, 1e-12):
            run(f"membrane eps {eps:g} ({k} rows)", T, np.zeros(k), rel)
    if dem is not None:
        for eps in (0.03, 0.3, 3.0):
            T = sp.csr_matrix((np.full(free.size, np.sqrt(eps)), (np.arange(free.size), free)), shape=(free.size, n))
            for rel in (1e-9, 1e-12):
                run(f"DEM tie eps {eps:g}", T, np.sqrt(eps) * dem[free], rel)


if __name__ == "__main__":
    main()
