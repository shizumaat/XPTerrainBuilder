"""pass2 scratch hook (candidate F1): the normal solve's Tikhonov floor CENTRED ON THE WARM START — with x0 given the
solve is for the INCREMENT, x = x0 + (N + eps I)^-1 A'(b - A x0) (same factorisation, one back-solve); cold start as
today plus P2_COLD refinement steps.  QP exits printed."""
import os


def install(ctx):
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    from auto_patch_v2.solve import design_qp as Q
    import auto_patch_v2.solve.design as D
    n_cold = int(os.environ.get('P2_COLD', '1'))

    def solve(A, b, x0, method, tol, maxiter, U=None, c=None, low_rank='bordered'):
        assert method == 'normal' and low_rank == 'bordered'
        At = A.T.tocsr()
        N = (At @ A).tocsc()
        n = N.shape[0]
        eps = 1e-12 * max(1.0, float(abs(N.diagonal()).max()))
        M = (N + eps * sp.identity(n, format='csc')).tocsc()
        k = 0 if U is None else int(U.shape[0])
        if k:
            lu = splu(sp.bmat([[M, U.T], [U, -sp.identity(k, format='csc')]], format='csc'))
            cc = np.asarray(c, float)

            def back(x):
                return np.asarray(lu.solve(np.concatenate([At @ (b - A @ x), cc - U @ x]))[:n], float)
        else:
            lu = splu(M)

            def back(x):
                return np.asarray(lu.solve(At @ (b - A @ x)), float)
        if x0 is not None:
            x0 = np.asarray(x0, float)
            return x0 + back(x0)
        x = back(np.zeros(n))
        for _ in range(n_cold):
            x = x + back(x)
        return x
    Q._linear_solve = solve
    D._linear_solve = solve
    orig = Q.solve_one_sided

    def traced(*a, **k):
        r = orig(*a, **k)
        print(f'    QP exit {r.status} rounds {r.rounds} solves {r.solves} F {r.objective:.6f} |g| {r.grad_norm:.3g} '
              f'wall {r.wall_s:.1f}s', flush=True)
        return r
    Q.solve_one_sided = traced
    D.solve_one_sided = traced
    print(f'  hook: centred floor (increment solve), cold refine {n_cold}', flush=True)
