"""THE FOLLOWER PASS AFTER STAGE 2 (issue #359): faces that FOLLOW a
stage-2 face are solved once more against stage 2's answer held constant.

A lot beside a building pad couples to the pad's level.  Solved together in
stage 2 the coupling is two-way — the pad bends toward the lot as much as
the lot toward the pad, and a pull over the whole lot made a loop with no
leader (MEASURED HECA: ``building8`` sank 100.37 -> 99.24 m).  Here the
caller's rewrite (``constraints/lot_follow.lot_follow_rewrite``, bound by
the caller: this layer may not import ``constraints``, M0 §1) names the
followers' rows and every other vertex's stage-2 level as a constant; the
pass is ONE solve on those constants (``fixed``, as the last stage's,
``design.solve_late_stage``), so nothing but a follower can move — the pad
stays at its stage-2 level by construction and no loop can form.

The pass is KEPT only when its hard set is no worse than stage 2's own;
otherwise stage 2's answer stands and the refusal is reported."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .api import Solution, Status

__all__ = ["solve_follow"]


def solve_follow(cs, sol2: Solution, rewrite: _t.Callable, solve: _t.Callable
                 ) -> tuple[Solution, dict]:
    """``sol2`` with the follower pass applied, and the pass's report.
    ``rewrite(cs, z)`` is the caller's (``None``: no follower);
    ``solve(cs_f, fixed)`` one design solve with ``fixed`` substituted."""
    got = rewrite(cs, sol2.z)
    if got is None:
        return sol2, {}
    cs_f, fixed, rep = got
    rep = dict(rep)
    sol_f, rep_f = solve(cs_f, fixed)
    rep.update(rows=rep_f.rows, unknowns=rep_f.unknowns,
               hard_settled=bool(rep_f.hard_settled),
               hard_max_violation_m=round(float(rep_f.hard_max_violation_m), 6))
    if sol_f.status is Status.ERROR or not sol_f.z or not rep_f.hard_settled:
        rep["kept"] = False
        return sol2, rep
    z = list(sol2.z)
    moved = 0.0
    for v in range(len(z)):
        if v not in fixed:
            moved = max(moved, abs(float(sol_f.z[v]) - z[v]))
            z[v] = float(sol_f.z[v])
    rep.update(kept=True, max_move_m=round(moved, 4))
    return _dc.replace(sol2, z=tuple(z)), rep
