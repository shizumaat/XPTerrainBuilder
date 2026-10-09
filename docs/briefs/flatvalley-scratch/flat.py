"""lane flatvalley scratch: NAME THE FLAT DIRECTION of one dumped QP (nullarm FV_DUMPQP).
usage: flat.py QP.pkl [OTHER_ARM_DIR STAGE_K] [--tie W]"""
import pickle, sys, collections, time
import numpy as np, scipy.sparse as sp
sys.path.insert(0, "/Users/noah/XPTerrainBuilder/.claude/worktrees/flatvalley/Ortho4XP/src")
from auto_patch_v2.solve import design_qp
from auto_patch_v2.solve.linear import _objective


def main():
    q = pickle.load(open(sys.argv[1], "rb"))
    A0, b0, A1, b1, w, shift, U, c, x = (q[k] for k in ("A0", "b0", "A1", "b1", "w_row", "shift", "U", "c", "x"))
    kw = q["kw"]; col = q["col"]; n = A0.shape[1]
    F = lambda y: _objective(A0, b0, A1, b1, w, shift, y, U, c)
    print(f"columns {n}, always-on rows {A0.shape[0]}, one-sided {A1.shape[0]}, datum rows {0 if U is None else U.shape[0]}; F(exit) {F(x):.6f}")
    design_qp._REL_TOL = 1e-15; design_qp._ROUNDS_MAX = 5000
    t = time.perf_counter()
    r = design_qp.solve_one_sided(A0, b0, A1, b1, w, shift, x, U, c, **kw)
    xs = r.x
    d = np.abs(xs - x)
    print(f"tight continue: {r.status} {r.rounds} rounds {time.perf_counter()-t:.1f}s F* {r.objective:.6f}  F(exit)-F* {F(x)-r.objective:.3e} (rel {(F(x)-r.objective)/r.objective:.2e}); "
          f"|x_exit-x*| >0.02: {int((d>0.02).sum())} cols, >0.1: {int((d>0.1).sum())}, max {d.max():.4f}")
    rng = np.random.default_rng(5)
    r2 = design_qp.solve_one_sided(A0, b0, A1, b1, w, shift, xs + rng.normal(0, 0.3, n), U, c, **kw)
    d2 = np.abs(r2.x - xs)
    print(f"tight from x*+N(0,0.3): {r2.status} {r2.rounds} rounds F {r2.objective:.6f} dF {r2.objective-r.objective:+.3e}; |x**-x*| >0.02: {int((d2>0.02).sum())}, >0.1 {int((d2>0.1).sum())}, max {d2.max():.4f}")
    bb = b1 - shift
    act = np.flatnonzero(A1 @ xs - bb > 0)
    Aa = sp.diags(np.sqrt(w[act])) @ A1[act]
    H = (A0.T @ A0 + Aa.T @ Aa).toarray()
    if U is not None:
        Ud = U.toarray(); H += Ud.T @ Ud
    t = time.perf_counter()
    lam, V = np.linalg.eigh(H)
    print(f"Hessian/2 eigen ({time.perf_counter()-t:.0f}s): min {lam[0]:.3e} max {lam[-1]:.3e}; "
          + ", ".join(f"<{th:g}: {int((lam<th).sum())}" for th in (1e-6, 1e-4, 1e-3, 1e-2, 1e-1, 1.0)))
    # which always-on terms give the columns curvature
    own = [o[0] if o else "other" for o in q["owner"]]
    A0c = A0.tocsc()
    kinds = sorted(set(own)); ki = {k: i for i, k in enumerate(kinds)}
    oidx = np.array([ki[o] for o in own])
    D = np.zeros((n, len(kinds)))
    coo = A0.tocoo()
    np.add.at(D, (coo.col, oidx[coo.row]), coo.data ** 2)
    print("diag(A0'A0) by term, column medians: " + ", ".join(f"{k} {np.median(D[:, i][D[:, i] > 0]) if (D[:, i] > 0).any() else 0:.3g} ({int((D[:, i] > 0).sum())} cols)" for k, i in ki.items()))
    flat = lam < 1e-2
    part = (V[:, flat] ** 2).sum(axis=1)          # each column's share in the flat subspace
    fc = part > 0.5
    print(f"flat subspace (lam<1e-2): {int(flat.sum())} modes; columns mostly inside it (share>0.5): {int(fc.sum())}; share>0.1: {int((part>0.1).sum())}")
    for name, mask in (("flat columns", fc), ("all columns", np.ones(n, bool))):
        print(f"  {name}: terms present -> " + ", ".join(f"{k} {int((D[mask][:, i] > 0).sum())}" for k, i in ki.items()))
    gen = np.array(q["gen"])
    A1a = A1[act].tocsc()
    touched = np.diff(A1a.indptr)
    print(f"  active one-sided rows {act.size}; flat columns touched by an active row: {int((touched[fc] > 0).sum())}/{int(fc.sum())}; all: {int((touched > 0).sum())}/{n}")
    np.save(sys.argv[1] + ".flatshare.npy", part); np.save(sys.argv[1] + ".xstar.npy", xs)
    np.save(sys.argv[1] + ".lam.npy", lam)
    if len(sys.argv) > 3 and not sys.argv[2].startswith("--"):
        from pathlib import Path
        a = Path(sys.argv[1]).parent; o = Path(sys.argv[2]); k = sys.argv[3]
        za, zb = np.load(a / f"z_{k}.npy"), np.load(o / f"z_{k}.npy")
        dv = zb - za
        dx = np.zeros(n); cnt = np.zeros(n)
        ok = col >= 0
        np.add.at(dx, col[ok], dv[ok]); np.add.at(cnt, col[ok], 1); dx /= np.maximum(cnt, 1)
        coef = V.T @ dx
        e = coef ** 2
        tot = e.sum()
        print(f"mover vector (stage call {k}, {o.name} - control): |d|2 {tot:.3f}, cols>0.02 {int((np.abs(dx)>0.02).sum())}; share of |d|2 in modes "
              + ", ".join(f"lam<{th:g}: {e[lam<th].sum()/tot:.3f}" for th in (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0))
              + f"; d'Hd {float(coef**2 @ lam):.4e}")
        mv = np.abs(dx) > 0.02
        print(f"  movers inside the flat set (share>0.1): {int((mv & (part>0.1)).sum())}/{int(mv.sum())}")


if __name__ == "__main__":
    main()
