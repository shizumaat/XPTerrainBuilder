"""pass2 scratch hook: the QP's linear solve with P2_REFINE steps of CORRECTED SEMI-NORMAL refinement (the residual
taken on A itself, b - A x, never on the normal matrix) on one factorisation; every QP exit printed."""
import os


STAT = {}


def install(ctx):
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    from auto_patch_v2.solve import design_qp as Q
    Q._ROUNDS_MAX = int(os.environ.get('P2_ROUNDS', '400'))
    n_ref = int(os.environ.get('P2_REFINE', '2'))

    def solve(A, b, x0, method, tol, maxiter, U=None, c=None, low_rank='bordered'):
        assert method == 'normal' and low_rank == 'bordered'
        At = A.T.tocsr()
        N = (At @ A).tocsc()
        n = N.shape[0]
        eps = float(os.environ.get('P2_EPS', '1e-12')) * max(1.0, float(abs(N.diagonal()).max()))
        STAT['eps'] = eps; STAT['dmax'] = float(abs(N.diagonal()).max()); STAT['dmin'] = float(abs(N.diagonal()).min())
        M = (N + eps * sp.identity(n, format='csc')).tocsc()
        k = 0 if U is None else int(U.shape[0])
        if k:
            K = sp.bmat([[M, U.T], [U, -sp.identity(k, format='csc')]], format='csc')
            lu = splu(K)
            cc = np.asarray(c, float)

            def back(r, rc):
                return np.asarray(lu.solve(np.concatenate([r, rc]))[:n], float)
            x = back(At @ b, cc)
            for _ in range(n_ref):
                x = x + back(At @ (b - A @ x), cc - U @ x)
            return x
        lu = splu(M)
        x = np.asarray(lu.solve(At @ b), float)
        for _ in range(n_ref):
            x = x + np.asarray(lu.solve(At @ (b - A @ x)), float)
        return x
    Q._linear_solve = solve
    orig = Q.solve_one_sided

    def traced(*a, **k):
        r = orig(*a, **k)
        print(f'    linear: eps {STAT.get("eps"):.3g} diag max {STAT.get("dmax"):.3g} min {STAT.get("dmin"):.3g}')
        print(f'    QP exit {r.status} rounds {r.rounds} solves {r.solves} F {r.objective:.6f} |g| {r.grad_norm:.3g} '
              f'wall {r.wall_s:.1f}s', flush=True)
        return r
    Q.solve_one_sided = traced
    import auto_patch_v2.solve.design as D
    D.solve_one_sided = traced
    print(f'  hook: refine {n_ref}, _ROUNDS_MAX = {Q._ROUNDS_MAX}', flush=True)
