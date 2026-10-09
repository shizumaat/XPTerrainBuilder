"""THE NULL-CHANGE CHECK of ``tools/v2_solve_replay.py`` (spec §61 (6); owner
RULINGS 2026-10-09e): solve the arm, solve it again with a handful of
ceilings the first answer ALREADY SATISFIES, and count what moved.

A convex problem handed a constraint its optimum satisfies has the same
optimum.  Before §61 it did not have the same ANSWER: ~1,800 of KCLT's
stage-1 columns carried bending only, the QP's tolerance exit landed them
by unrelated inputs, and 30 satisfied ceilings moved 506-615 vertices up to
0.81 m.  This is the standing instrument for that bar — at most 20 movers
at 0.02 m and none over 0.3 m on the solve-owned airside — and it reports
the two discrete choices that can still differ between the two solves: the
§5a LP's relaxed set and the rows promoted on a miss.

It MEASURES NO LAW AND COUNTS NO DEFECTS.  It reads each stage-1 PASS's own
answer where ``solve/flex.stage_one`` hands it on
(``flex.yield_stage_one``, wrapped for the two solves only and restored) —
pass 1a's levels are not kept anywhere else.

Twin: ``tests/test_replay_null.py``.
"""
from __future__ import annotations

import contextlib
import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["BAR_COUNT", "BAR_M", "BAR_STEP_M", "PassTrace", "ceilings",
           "movers", "null_change", "null_line", "with_bands"]

#: §61 (6) 5 THE STABILITY BAR: at most this many movers beyond ``BAR_M``,
#: none beyond ``BAR_STEP_M``
BAR_COUNT = 20
BAR_M = 0.02
BAR_STEP_M = 0.3
#: the ceilings stand this far above the first answer (satisfied, not tight)
MARGIN_M = 0.05
#: the FIXED seed the ceilings' vertices are drawn by (the lane's arm)
SEED = 3
PASS_NAMES = ("pass1a", "pass1b")


class PassTrace(contextlib.AbstractContextManager):
    """Records every stage-1 PASS's final answer while it is open: the
    pass's map, its ``z`` and the vertices it levelled, plus the §5a LP's
    relaxed count and the rows promoted on a miss."""

    def __init__(self) -> None:
        self.passes: list[dict[str, _t.Any]] = []
        self._orig: _t.Any = None

    def __enter__(self) -> "PassTrace":
        from auto_patch_v2.solve import flex
        self._orig = flex.yield_stage_one

        def traced(planar, cs, law, got, solve1):
            out = self._orig(planar, cs, law, got, solve1)
            sol, rep, _drop, _foreign, levels, _size = out[1]
            feas = getattr(rep, "hard_feasibility", None)
            self.passes.append({
                "pm": planar, "z": np.asarray(sol.z, float),
                "levelled": np.fromiter(sorted(levels), dtype=np.int64),
                "relaxed": int(getattr(feas, "relaxed", 0) or 0),
                "promoted": int(getattr(feas, "promoted_on_miss", 0) or 0)})
            return out
        flex.yield_stage_one = traced
        return self

    def __exit__(self, *exc: _t.Any) -> None:
        from auto_patch_v2.solve import flex
        flex.yield_stage_one = self._orig


def ceilings(pm: _t.Any, law: _t.Any, passes: _t.Sequence[dict], n: int,
             margin_m: float = MARGIN_M, seed: int = SEED) -> tuple:
    """``n`` ``Band`` ceilings ``margin_m`` above the HIGHEST of the passes'
    own levels, on apron / taxi-family ring vertices drawn by a fixed seed —
    constraints every pass of the first solve already satisfies."""
    from auto_patch_v2.model.constraints import Band, Source
    roles = set(law.tables.precedence.taxi_family.members) | {"apron"}
    vs = sorted({v for f in pm.faces.values() if f.role in roles
                 for v in pm.ring_vertices(f.ring)})
    if not vs or not passes:
        return ()
    pick = np.random.default_rng(seed).choice(len(vs), size=min(n, len(vs)),
                                              replace=False)
    src = Source("null_probe", "spec §61 (6) null-change ceiling", ())
    return tuple(Band(vs[i], None,
                      float(max(p["z"][vs[i]] for p in passes)) + margin_m, src)
                 for i in pick)


def movers(za: np.ndarray, zb: np.ndarray,
           among: np.ndarray | None = None) -> list:
    """``[movers > BAR_M, movers > BAR_STEP_M, worst m]`` between two
    answers of one map, over ``among`` (default: every vertex)."""
    d = np.abs(np.asarray(zb, float) - np.asarray(za, float))
    if among is not None:
        d = d[among]
    if not d.size:
        return [0, 0, 0.0]
    return [int((d > BAR_M).sum()), int((d > BAR_STEP_M).sum()),
            round(float(d.max()), 4)]


def null_change(run: _t.Callable[[tuple], tuple], pm_stage1: _t.Any,
                law: _t.Any, *, n: int = 30,
                first: tuple | None = None) -> dict[str, _t.Any]:
    """THE CHECK.  ``run(bands) -> (sol, rep)`` solves the arm with
    ``bands`` appended to the set STAGE 1 solves (``()`` = the arm as
    given); ``pm_stage1`` is the map that set's vertex ids are on.
    ``first`` is ``(trace, sol)`` of a solve of the arm already made under
    a :class:`PassTrace` (the replay's own), else the arm is solved here.
    """
    if first is None:
        with PassTrace() as ta:
            sol_a, _rep = run(())
    else:
        ta, sol_a = first
    bands = ceilings(pm_stage1, law, ta.passes, n)
    with PassTrace() as tb:
        sol_b, _rep = run(bands)
    out: dict[str, _t.Any] = {"ceilings": len(bands), "margin_m": MARGIN_M,
                              "bar": [BAR_COUNT, BAR_STEP_M],
                              "first_at": (list(pm_stage1.vertices[bands[0].v].key)
                                           if bands else None)}
    same = len(ta.passes) == len(tb.passes)
    out["passes"] = [len(ta.passes), len(tb.passes)]
    names = (PASS_NAMES if len(ta.passes) == 2 else
             tuple(f"pass{k + 1}" for k in range(len(ta.passes))))
    for name, pa, pb in zip(names, ta.passes, tb.passes if same else ()):
        out[name] = movers(pa["z"], pb["z"], pa["levelled"])
    out["promoted"] = [[p["promoted"] for p in t.passes] for t in (ta, tb)]
    out["lp_relaxed"] = [[p["relaxed"] for p in t.passes] for t in (ta, tb)]
    out["stage2"] = (movers(sol_a.z, sol_b.z)
                     if sol_a.z and sol_b.z and len(sol_a.z) == len(sol_b.z)
                     else None)
    worst = [m for k, m in out.items()
             if k.startswith("pass") and k != "passes" and m]
    out["met"] = bool(same and worst and all(
        m[0] <= BAR_COUNT and m[1] == 0 for m in worst))
    return out


def null_line(res: _t.Mapping[str, _t.Any]) -> str:
    """THE ONE LINE the sweep greps (spec §61 (6))."""
    def fmt(m: _t.Any) -> str:
        return "-" if not m else f"{m[0]}/{m[1]}/{m[2]:.3f}"
    parts = [f"{k} {fmt(v)}" for k, v in res.items()
             if k.startswith("pass") and k != "passes"]
    pa, pb = res["promoted"]
    la, lb = res["lp_relaxed"]
    return ("NULL-CHANGE " + " ".join(parts) + f" stage2 {fmt(res['stage2'])}"
            f" (movers > {BAR_M} / > {BAR_STEP_M} / worst m; bar {BAR_COUNT} / 0;"
            f" promoted {sum(pa)}={sum(pb)}, lp relaxed {sum(la)}={sum(lb)})"
            + ("" if res["met"] else "  BAR MISSED"))


def with_bands(cs: _t.Any, bands: tuple) -> _t.Any:
    """``cs`` with ``bands`` appended (the set itself when there are none)."""
    return cs if not bands else _dc.replace(cs, bands=tuple(cs.bands) + tuple(bands))
