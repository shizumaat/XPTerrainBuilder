"""THE solver: scipy/HiGHS LP with the real objective (RULINGS
2026-09-03g: feasibility is answered by the real solve; a zero-objective
phase 1 is 9× slower).  Infeasible ⇒ the IIS names ``(row, source)``
(``iis.py``), run ONLY then.  The solver never invents a value.
"""
from __future__ import annotations

import time

import numpy as np
from scipy.optimize import linprog

from ..model.constraints import ConstraintSet, Diff, Flat, Linear, Offset, Pin
from ..model.planar import PlanarMap
from .api import Backend, Options, Residual, Solution, Status, Weights
from .assemble import Problem, assemble

__all__ = ["solve", "residual", "lp_size"]


def lp_size(p: Problem) -> dict[str, int]:
    return {"columns": int(p.c.shape[0]), "z": p.n,
            "rows_ub": int(p.A_ub.shape[0]), "rows_eq": int(p.A_eq.shape[0]),
            "nnz": int(p.A_ub.nnz + p.A_eq.nnz)}


def residual(planar: PlanarMap, cs: ConstraintSet, z: np.ndarray,
             objective: float) -> Residual:
    """The certificate: worst violation per row kind at ``z``."""
    mp = md = mf = mb = mo = 0.0
    for p in cs.pins:
        mp = max(mp, abs(z[p.v] - p.z))
    for d in cs.diffs:
        md = max(md, abs(z[d.a] - z[d.b]) - d.cap * d.d)
    for f in cs.flats:
        g = z[list(f.group)]
        mf = max(mf, float(g.max() - g.min()))
    for b in cs.bands:
        if b.lo is not None:
            mb = max(mb, b.lo - z[b.v])
        if b.hi is not None:
            mb = max(mb, z[b.v] - b.hi)
    for o in cs.offsets:
        mo = max(mo, o.min_delta - (z[o.a] - z[o.b]))
    ml = 0.0
    for ln in cs.linears:
        s = sum(c * z[v] for v, c in ln.terms)
        if ln.hi is not None:
            ml = max(ml, s - ln.hi)
        if ln.lo is not None:
            ml = max(ml, ln.lo - s)
    return Residual(max_pin_m=mp, max_diff_m=max(md, ml), max_flat_m=mf,
                    max_band_m=mb, max_offset_m=mo, objective=objective)


def solve(planar: PlanarMap, constraints: ConstraintSet, weights: Weights,
          options: Options | None = None, *,
          size_out: dict | None = None) -> Solution:
    """Assemble and solve; diagnose on infeasible.  ``size_out`` (a
    dict) receives :func:`lp_size` of the assembled problem."""
    opt = options or Options()
    if opt.backend != Backend.HIGHS:
        return Solution(z=(), status=Status.ERROR, residual=None,
                        message=f"backend {opt.backend} is not in the freeze "
                                "(RULINGS 2026-09-03g)")
    t0 = time.perf_counter()
    prob = assemble(planar, constraints, weights)
    if size_out is not None:
        size_out.update(lp_size(prob))
    lp_opts = {"disp": bool(opt.verbose), "presolve": True}
    if opt.time_limit_s is not None:
        lp_opts["time_limit"] = float(opt.time_limit_s)
    res = linprog(prob.c, A_ub=prob.A_ub, b_ub=prob.b_ub, A_eq=prob.A_eq,
                  b_eq=prob.b_eq, bounds=prob.bounds, method="highs",
                  options=lp_opts)
    wall = time.perf_counter() - t0
    if res.status == 2:
        iis_rows: tuple = ()
        msg = f"infeasible: {res.message}"
        if opt.diagnose_iis:
            from .iis import diagnose
            t1 = time.perf_counter()
            iis_rows = diagnose(planar, constraints, weights, opt)
            msg += f"; IIS {len(iis_rows)} row(s) in {time.perf_counter() - t1:.2f} s"
        return Solution(z=(), status=Status.INFEASIBLE, residual=None,
                        iis=iis_rows, backend=Backend.HIGHS,
                        iterations=int(getattr(res, "nit", 0) or 0),
                        wall_s=wall, message=msg)
    if res.status != 0 or res.x is None:
        return Solution(z=(), status=Status.ERROR, residual=None,
                        backend=Backend.HIGHS, wall_s=wall,
                        message=f"status {res.status}: {res.message}")
    z = np.asarray(res.x[:prob.n], float)
    cert = residual(planar, constraints, z, float(res.fun))
    status = Status.OPTIMAL if cert.max_m <= opt.feasibility_tol_m * 100 \
        else Status.FEASIBLE
    return Solution(z=tuple(float(v) for v in z), status=status, residual=cert,
                    backend=Backend.HIGHS, iterations=int(getattr(res, "nit", 0) or 0),
                    wall_s=wall, message=f"{res.message}; "
                    f"rows {lp_size(prob)['rows_ub']}+{lp_size(prob)['rows_eq']}")
