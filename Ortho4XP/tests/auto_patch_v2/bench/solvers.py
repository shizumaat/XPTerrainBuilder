"""Solver arms over the canonical form (qpform.build).  Each returns a dict
with z (or None), status, and any solver-specific extras.  Timing is done
by the caller (run_one.py) around the whole function, so format conversion
counts -- a real implementation pays it too.
"""
import time
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.optimize import linprog
import scipy.optimize._highspy._core as _h

INF = 1e20


# --------------------------------------------------------------------------
# HiGHS LP via scipy.optimize.linprog(method="highs")
# --------------------------------------------------------------------------
def _lp_parts(f):
    """split rows: single-variable rows -> column bounds; equality pairs -> A_eq;
    ranged pairs -> +-A_ub; one-sided -> A_ub."""
    A, l, u, fam = f["A"].tocsr(), f["l"], f["u"], f["fam"]
    n = f["n"]
    lb, ub = np.full(n, -np.inf), np.full(n, np.inf)
    single = (fam == "pin") | (fam == "band")
    Asing = A[single]
    col = Asing.indices  # one entry per row
    lb[col] = np.maximum(lb[col], l[single]); ub[col] = np.minimum(ub[col], u[single])
    eq = fam == "flat"
    rng = (fam == "edge")
    ge = fam == "offset"
    A_eq, b_eq = A[eq], l[eq]
    A_ub = sp.vstack([A[rng], -A[rng], -A[ge]]).tocsr()
    b_ub = np.r_[u[rng], -l[rng], -l[ge]]
    return lb, ub, A_eq, b_eq, A_ub, b_ub


def highs_lp_phase1(f, inst):
    lb, ub, A_eq, b_eq, A_ub, b_ub = _lp_parts(f)
    res = linprog(np.zeros(f["n"]), A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=np.c_[lb, ub], method="highs")
    return dict(z=res.x if res.status == 0 else None, status=int(res.status), msg=res.message,
                nit=int(res.nit))


def highs_lp_l1(f, inst):
    """L1 proxy: min sum w_i |z_i - dem_i|  (second differences not included)."""
    n = f["n"]
    lb, ub, A_eq, b_eq, A_ub, b_ub = _lp_parts(f)
    w, dem = inst["w"], inst["dem"]
    I = sp.identity(n, format="csr")
    Z = sp.csr_matrix((A_ub.shape[0], n))
    A_ub2 = sp.vstack([sp.hstack([A_ub, Z]), sp.hstack([I, -I]), sp.hstack([-I, -I])]).tocsr()
    b_ub2 = np.r_[b_ub, dem, -dem]
    A_eq2 = sp.hstack([A_eq, sp.csr_matrix((A_eq.shape[0], n))]).tocsr()
    c = np.r_[np.zeros(n), w]
    bounds = np.r_[np.c_[lb, ub], np.c_[np.zeros(n), np.full(n, np.inf)]]
    res = linprog(c, A_ub=A_ub2, b_ub=b_ub2, A_eq=A_eq2, b_eq=b_eq, bounds=bounds, method="highs")
    return dict(z=res.x[:n] if res.status == 0 else None, status=int(res.status), msg=res.message,
                nit=int(res.nit), lp_obj=float(res.fun) if res.status == 0 else None)


# --------------------------------------------------------------------------
# HiGHS raw API (scipy's bundled binding): ranged rows, dual ray, IIS, QP
# --------------------------------------------------------------------------
def _highs_model(f, with_hessian):
    A = f["A"].tocsc()
    n, m = f["n"], f["m"]
    lp = _h.HighsLp()
    lp.num_col_ = n; lp.num_row_ = m
    lp.a_matrix_.num_col_ = n; lp.a_matrix_.num_row_ = m
    lp.a_matrix_.format_ = _h.MatrixFormat.kColwise
    lp.a_matrix_.start_ = A.indptr.astype(np.int32)
    lp.a_matrix_.index_ = A.indices.astype(np.int32)
    lp.a_matrix_.value_ = A.data
    lp.col_cost_ = f["q"] if with_hessian else np.zeros(n)
    lp.col_lower_ = np.full(n, -_h.kHighsInf); lp.col_upper_ = np.full(n, _h.kHighsInf)
    lo = np.where(f["l"] <= -INF, -_h.kHighsInf, f["l"]); up = np.where(f["u"] >= INF, _h.kHighsInf, f["u"])
    lp.row_lower_ = lo; lp.row_upper_ = up
    lp.offset_ = f["const"] if with_hessian else 0.0
    h = _h._Highs()
    h.setOptionValue("output_flag", False)
    h.passModel(lp)
    if with_hessian:
        P = sp.tril(f["P"]).tocsc()
        hs = _h.HighsHessian()
        hs.dim_ = n; hs.format_ = _h.HessianFormat.kTriangular
        hs.start_ = P.indptr.astype(np.int32); hs.index_ = P.indices.astype(np.int32); hs.value_ = P.data
        h.passHessian(hs)
    return h


def highs_raw_phase1(f, inst, diagnose=True):
    h = _highs_model(f, False)
    h.run()
    st = h.getModelStatus()
    out = dict(status=str(st), z=None)
    if st == _h.HighsModelStatus.kOptimal:
        out["z"] = np.array(h.getSolution().col_value)
        return out
    if st == _h.HighsModelStatus.kInfeasible and diagnose:
        t0 = time.perf_counter()
        rs, has, ray = h.getDualRay()
        out["dual_ray_status"] = str(rs); out["dual_ray_exists"] = bool(has)
        if has:
            ray = np.asarray(ray)
            nz = np.where(np.abs(ray) > 1e-9 * max(1, np.abs(ray).max()))[0]
            out["dual_ray_rows"] = [str(f["names"][i]) for i in nz[:50]]
            out["dual_ray_nnz"] = int(len(nz))
        out["t_dual_ray"] = time.perf_counter() - t0
        # dual ray often needs presolve off; retry if missing
        if not has:
            t0 = time.perf_counter()
            h2 = _highs_model(f, False)
            h2.setOptionValue("presolve", "off")
            h2.run()
            rs, has, ray = h2.getDualRay()
            out["dual_ray_nopresolve_exists"] = bool(has)
            if has:
                ray = np.asarray(ray)
                nz = np.where(np.abs(ray) > 1e-9 * max(1, np.abs(ray).max()))[0]
                out["dual_ray_rows"] = [str(f["names"][i]) for i in nz[:50]]
                out["dual_ray_nnz"] = int(len(nz))
            out["t_dual_ray_nopresolve"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        iis = _h.HighsIis()
        try:
            h.setOptionValue("iis_strategy", 1)   # kIisStrategyFromLpRowPriority (deletion filter)
            rs = h.getIis(iis)
            out["iis_status"] = str(rs); out["iis_valid"] = bool(iis.valid)
            rows = list(iis.row_index); cols = list(iis.col_index)
            out["iis_rows"] = [str(f["names"][i]) for i in rows[:50]]
            out["iis_nrows"] = len(rows); out["iis_ncols"] = len(cols)
        except Exception as ex:  # noqa
            out["iis_error"] = repr(ex)
        out["t_iis"] = time.perf_counter() - t0
    return out


def highs_qp(f, inst, time_limit=900.0):
    h = _highs_model(f, True)
    h.setOptionValue("time_limit", float(time_limit))
    h.run()
    st = h.getModelStatus()
    out = dict(status=str(st), z=None)
    if st in (_h.HighsModelStatus.kOptimal, _h.HighsModelStatus.kTimeLimit):
        out["z"] = np.array(h.getSolution().col_value)
    info = h.getInfo()
    out["qp_iters"] = int(info.qp_iteration_count)
    return out


# --------------------------------------------------------------------------
# Hand-rolled ADMM (OSQP algorithm) on the sparse quasi-definite KKT system,
# factorised with SuperLU (scipy.sparse.linalg.splu); adaptive rho.
# --------------------------------------------------------------------------
def admm(f, inst, eps_abs=1e-4, eps_rel=1e-4, max_iter=4000, sigma=1e-6, alpha=1.6, rho0=0.1):
    P, q, A, l, u = f["P"], f["q"], f["A"].tocsc(), f["l"].copy(), f["u"].copy()
    n, m = f["n"], f["m"]
    l = np.where(l <= -INF, -np.inf, l); u = np.where(u >= INF, np.inf, u)
    eq = np.abs(u - l) < 1e-9

    def rho_vec(rho):
        r = np.full(m, rho); r[eq] = 1e3 * rho; return r

    def factor(rho):
        rv = rho_vec(rho)
        K = sp.bmat([[P + sigma * sp.identity(n), A.T], [A, -sp.diags(1.0 / rv)]], format="csc")
        return spla.splu(K, permc_spec="COLAMD"), rv

    rho = rho0
    lu, rv = factor(rho)
    x = np.zeros(n); z = np.clip(np.zeros(m), l, u); y = np.zeros(m)
    nfact = 1
    Ax = A @ x
    for it in range(1, max_iter + 1):
        rhs = np.r_[sigma * x - q, z - y / rv]
        sol = lu.solve(rhs)
        xt = sol[:n]; nu = sol[n:]
        zt = z + (nu - y) / rv
        x_new = alpha * xt + (1 - alpha) * x
        z_new = np.clip(alpha * zt + (1 - alpha) * z + y / rv, l, u)
        y = y + rv * (alpha * zt + (1 - alpha) * z - z_new)
        x, z = x_new, z_new
        if it % 25 == 0:
            Ax = A @ x; Px = P @ x; ATy = A.T @ y
            r_p = np.abs(Ax - z).max(); r_d = np.abs(Px + q + ATy).max()
            e_p = eps_abs + eps_rel * max(np.abs(Ax).max(), np.abs(z).max())
            e_d = eps_abs + eps_rel * max(np.abs(Px).max(), np.abs(ATy).max(), np.abs(q).max())
            if r_p <= e_p and r_d <= e_d:
                return dict(z=x, status="solved", iters=it, refactors=nfact, r_prim=float(r_p), r_dual=float(r_d))
            # adaptive rho (OSQP rule)
            num = r_p / max(np.abs(Ax).max(), np.abs(z).max(), 1e-12)
            den = r_d / max(np.abs(Px).max(), np.abs(ATy).max(), np.abs(q).max(), 1e-12)
            new = rho * np.sqrt(num / den)
            if new > 5 * rho or new < rho / 5:
                rho = float(np.clip(new, 1e-6, 1e6)); lu, rv = factor(rho); nfact += 1
    return dict(z=x, status="max_iter", iters=max_iter, refactors=nfact)


# --------------------------------------------------------------------------
# OSQP
# --------------------------------------------------------------------------
def osqp_solve(f, inst, **settings):
    import osqp
    P, q, A, l, u = f["P"], f["q"], f["A"].tocsc(), f["l"].copy(), f["u"].copy()
    l = np.where(l <= -INF, -np.inf, l); u = np.where(u >= INF, np.inf, u)
    prob = osqp.OSQP()
    st = dict(verbose=False); st.update(settings)
    prob.setup(P=sp.triu(P, format="csc"), q=q, A=A, l=l, u=u, **st)
    res = prob.solve()
    out = dict(status=res.info.status, z=res.x if res.info.status.startswith("solved") else None,
               iters=int(res.info.iter), run_time=float(res.info.run_time), setup_time=float(res.info.setup_time),
               solve_time=float(res.info.solve_time), polish_time=float(res.info.polish_time),
               status_val=int(res.info.status_val), status_polish=int(res.info.status_polish),
               rho_updates=int(res.info.rho_updates))
    if "infeasible" in res.info.status:
        cert = np.asarray(getattr(res, "prim_inf_cert", np.zeros(0)))
        if cert.size:
            nz = np.where(np.abs(cert) > 1e-6 * np.abs(cert).max())[0]
            out["cert_rows"] = [str(f["names"][i]) for i in nz[:50]]
            out["cert_nnz"] = int(len(nz))
    return out


# --------------------------------------------------------------------------
# scipy trust-constr (small n only; documented as a reference, not a candidate)
# --------------------------------------------------------------------------
def trust_constr(f, inst):
    from scipy.optimize import minimize, LinearConstraint
    P, q, A, l, u = f["P"], f["q"], f["A"], f["l"].copy(), f["u"].copy()
    l = np.where(l <= -INF, -np.inf, l); u = np.where(u >= INF, np.inf, u)
    fun = lambda z: 0.5 * z @ (P @ z) + q @ z
    jac = lambda z: P @ z + q
    res = minimize(fun, inst["dem"].copy(), jac=jac, hess=lambda z: P, method="trust-constr",
                   constraints=[LinearConstraint(A, l, u)], options=dict(maxiter=500, verbose=0, gtol=1e-6, xtol=1e-6))
    return dict(z=res.x, status=str(res.status) + ":" + res.message, iters=int(res.nit))


# --------------------------------------------------------------------------
# deletion-filter IIS over the LP (fallback / cross-check of HiGHS getIis)
# --------------------------------------------------------------------------
def deletion_filter_iis(f, candidate_rows=None):
    """Start from candidate rows (e.g. dual-ray support); drop rows one at a
    time, keep those whose removal makes the LP feasible.  Each probe is a
    phase-1 LP over the whole model with those rows relaxed."""
    A, l, u = f["A"], f["l"], f["u"]
    keep = list(candidate_rows if candidate_rows is not None else range(f["m"]))
    active = set(keep)

    def feasible(relaxed):
        lo = l.copy(); up = u.copy()
        idx = np.fromiter(relaxed, int) if relaxed else np.zeros(0, int)
        lo[idx] = -INF; up[idx] = INF
        g = dict(f); g["l"] = lo; g["u"] = up
        h = _highs_model(g, False); h.run()
        return h.getModelStatus() == _h.HighsModelStatus.kOptimal

    outside = set(range(f["m"])) - active
    probes = 0
    for r in keep:
        probes += 1
        if not feasible(outside | {r}):
            outside.add(r)     # r is not needed for infeasibility
    iis = sorted(set(range(f["m"])) - outside)
    return iis, probes


def iis_deletion_seeded(f, inst):
    h = _highs_model(f, False); h.run()
    rs, has, ray = h.getDualRay()
    ray = np.asarray(ray); nz = np.where(np.abs(ray) > 1e-9 * max(1, np.abs(ray).max()))[0]
    t0 = time.perf_counter()
    iis, probes = deletion_filter_iis(f, list(nz))
    return dict(z=None, status="iis", seed_rows=int(len(nz)), probes=probes, iis_rows=[str(f["names"][i]) for i in iis],
                t_filter=time.perf_counter() - t0)


def iis_deletion_full(f, inst):
    t0 = time.perf_counter()
    iis, probes = deletion_filter_iis(f, None)
    return dict(z=None, status="iis", probes=probes, iis_rows=[str(f["names"][i]) for i in iis],
                t_filter=time.perf_counter() - t0)


ARMS = {
    "iis_deletion_seeded": iis_deletion_seeded,
    "iis_deletion_full": iis_deletion_full,
    "highs_lp_phase1": highs_lp_phase1,
    "highs_lp_l1": highs_lp_l1,
    "highs_raw_phase1": highs_raw_phase1,
    "highs_qp": highs_qp,
    "admm_1e-4": lambda f, i: admm(f, i, 1e-4, 1e-4),
    "admm_1e-6": lambda f, i: admm(f, i, 1e-6, 1e-6, max_iter=20000),
    "osqp_default": lambda f, i: osqp_solve(f, i),
    "osqp_polish": lambda f, i: osqp_solve(f, i, polish=True),
    "osqp_1e-4_polish": lambda f, i: osqp_solve(f, i, polish=True, eps_abs=1e-4, eps_rel=1e-4),
    "osqp_1e-6_polish": lambda f, i: osqp_solve(f, i, polish=True, eps_abs=1e-6, eps_rel=1e-6, max_iter=100000),
    "trust_constr": trust_constr,
}
