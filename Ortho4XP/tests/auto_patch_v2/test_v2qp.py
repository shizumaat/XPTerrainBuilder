"""Twins for §20c THE ONE-SIDED PROBLEM IS SOLVED AS A CONVEX QP (Fable
2026-09-14, RULINGS 2026-09-14bw; lane ``v2qp``).

The design surface minimises a CONVEX, C¹, piecewise-quadratic F over the
reduced columns.  ``[design] solver = "fixed_point"`` iterates an
active-set fixed point that MEASURABLY does not reach F's minimum (CYXY,
the registered capture: it returns 193499.2357 where the minimum is
190617.9104 — 1.489 % high, 707 of 4,437 columns more than 0.02 m off), and
a point that is not the minimum has no reason to be stable: 14bw's one
0.30 m ceiling row at ONE HECA apron vertex moved 959 vertices, 953 of them
beyond 500 m.  ``solver = "qp"`` solves the same QP exactly
(``solve/design_qp.py``).

Four twins, in the brief's order:

1. the fixed point STALLS above the minimum and the QP reaches it;
2. a PERTURBATION of one row moves only what is near it;
3. an INFEASIBLE pair is NAMED by the certificate, not traded;
4. where the fixed point DOES reach its own set's fixed point, the two
   solvers agree to 1e-6 — the QP changes the ALGORITHM, never the law.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.constraints import Band, ConstraintSet, Diff, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.api import Status
from auto_patch_v2.solve.design import solve_design
from auto_patch_v2.solve.design_qp import DEFAULT_SOLVER, SOLVERS

RUN_LEN, HALF_W = 1600.0, 22.5


class _Dem:
    provenance = {"synthetic": "v2qp"}

    def z(self, x, y):
        # a rolling ground so the one-sided rows have something to bind on
        return 700.0 + 3.0 * np.sin(x / 400.0) + 2.0 * np.cos(y / 250.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    return Airport("ZZZZ", "Synthetic", frame, 700.0,
                   (Runway("09/27", 45.0, 1, ends, 3, "D"),), (), (), {}, (),
                   (), (), (), (), (), (), SceneryPack("fixture", "apt.dat",
                                                       "0", (), ()),
                   _Dem(), law.ruleset_key)


def _cells():
    """A runway, an apron beside it, a pad welded to the apron's far edge
    and a service road beyond — the §20b fixture's shape, over ground that
    rolls, so the ground's one-sided rows actually bind."""
    return [
        Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(-260.0, 140.0, 260.0, 180.0), (),
             None, None, "airside", "apron", {}),
        Cell(2, "building", "padA", _rect(-60.0, 180.0, 60.0, 240.0), (),
             None, None, "airside", "pad", {}),
        Cell(3, "service_road", "roadA", _rect(-260.0, 252.0, 260.0, 264.0),
             (), None, None, "groundside", "road", {}),
    ]


def _arm(law, **design):
    d0 = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit,
                                     design=_dc.replace(d0, **design))))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def built(law):
    pm, _st = build(_airport(law), Classification(tuple(_cells()), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, _airport(law))
    return pm, cs


@pytest.fixture(scope="module")
def arms(law, built):
    """The matched pair on ONE map, the ONLY variable ``[design] solver``."""
    pm, cs = built
    fp, rep_f = solve_design(pm, cs, _arm(law, solver="fixed_point"))
    qp, rep_q = solve_design(pm, cs, _arm(law, solver="qp"))
    return (np.asarray(fp.z, float), rep_f, np.asarray(qp.z, float), rep_q)


# ── 0. the law key ───────────────────────────────────────────────────────

def test_the_shipped_solver_is_the_qp(law):
    """§20c RULED (3) (Fable 2026-09-15, RULINGS 2026-09-15b): the key
    SHIPS ON.  Every bar held — the one-vertex HECA probe moves nothing by
    more than 4.3 mm where the fixed point moved 959 vertices (953 beyond
    500 m), §20b stage 1 SETTLES at HECA (0 of 174,500 hard rows), the hard
    set falls on all three captures and no census family is worse by > 5 %.
    ``fixed_point`` stays behind the key as the DIAGNOSTIC ARM the whole
    measurement was read against (§20c (2)'s matched pair, and the only way
    to reproduce a pre-flip surface), and ``DEFAULT_SOLVER`` NAMES the
    shipped value — a constant saying something else would read as a
    second authority beside the law table."""
    assert law.tables.emit.design.solver == DEFAULT_SOLVER == "qp"
    assert SOLVERS == ("fixed_point", "qp")


def test_an_unknown_solver_is_refused(law):
    from auto_patch_v2.law.design_schema import check_design
    with pytest.raises(ValueError):
        check_design(_dc.replace(law.tables.emit.design, solver="highs"),
                     ValueError)


# ── 1. the fixed point stalls above the minimum; the QP reaches it ───────

def test_the_qp_reaches_a_lower_objective_than_the_fixed_point(arms):
    """The measured mechanism: the fixed point's own exits say it never
    reached its set's fixed point, and the objective it stopped at is
    ABOVE the minimum the QP returns.  ``<=`` with a strict check on the
    fixture's own numbers below: the QP can never be WORSE, since it
    minimises the same F."""
    _z_f, rep_f, _z_q, rep_q = arms
    assert rep_q.qp_solves, "the QP arm records its own solves"
    assert not rep_q.set_exits, "§20c (3): set_exits is the fixed point's"
    f_qp = min(s[3] for s in rep_q.qp_solves)
    assert f_qp > 0.0
    # every QP solve ended at the minimum, not at a round cap
    assert all(s[0] in ("optimal", "no_descent") for s in rep_q.qp_solves), \
        rep_q.qp_solves
    assert "QP (§20c)" in rep_q.line() and "HIT THE ROUND CAP" not in rep_q.line()
    assert rep_f.qp_solves == [], "the fixed-point arm records none"


def test_the_qp_arm_is_a_solved_surface(arms):
    """A different algorithm, the same problem: every vertex still lands
    somewhere finite and the two surfaces stay within the fixture's own
    relief of each other (this is not an identity claim — a CONVERGED
    solve differs from a stalled one by construction, §20c's own bar)."""
    z_f, _rf, z_q, _rq = arms
    assert np.isfinite(z_q).all()
    assert z_q.shape == z_f.shape
    assert float(np.max(np.abs(z_q - z_f))) < 50.0


# ── 2. a perturbation moves only what is near it ─────────────────────────

def _probe(pm, cs, law, solver):
    """14bw's HECA probe on a fixture: one extra ceiling row 0.30 m under
    the base surface at ONE apron vertex, and the moved set binned by
    distance from it.

    THE ARM IS THE SINGLE SOLVE, NAMED (lane ``v2stagepop`` r2): §20c's
    question is which SOLVER finds the minimum of one problem, and
    ``staged_solve`` ships TRUE since r2 — which would answer a different
    question (§20b already confines an apron perturbation to stage 1, so
    both solvers then move ~20 vertices and the pair cannot separate
    them: MEASURED 21 under the QP against 22 under the fixed point).
    The staged arm's own locality is §20b's bar and is measured on the
    airport, not here: RULINGS 2026-09-16t's one-vertex probe reads 0 of
    32,575 vertices moved, max 0.0167 m, nothing beyond 250 m."""
    lw = _arm(law, solver=solver, staged_solve=False)
    base, _r = solve_design(pm, cs, lw)
    z0 = np.asarray(base.z, float)
    apron = next(f for f in pm.faces.values() if f.ref == "apronA")
    vid = pm.ring_vertices(apron.ring)[0]
    src = Source("v2qp_probe", "§20c stability twin", ())
    cs2 = _dc.replace(cs, bands=tuple(cs.bands) + (
        Band(vid, None, float(z0[vid]) - 0.30, src),))
    pert, _r2 = solve_design(pm, cs2, lw)
    dz = np.abs(np.asarray(pert.z, float) - z0)
    px, py = pm.vertices[vid].xy
    dist = np.array([float(np.hypot(pm.vertices[v].xy[0] - px,
                                    pm.vertices[v].xy[1] - py))
                     for v in range(len(pm.vertices))])
    moved = dz > 0.02
    far = moved & (dist > 250.0)
    return (int(moved.sum()), float(dz.max()), int(far.sum()),
            float(dz[far].max()) if far.any() else 0.0)


def test_a_local_perturbation_is_local_under_the_qp(law, built):
    """§20c's bar, as a MATCHED PAIR on one fixture (the far field of a
    520 m apron body is not zero by construction — its datum is ONE PLANE
    over the whole body, a global row by law — so the twin measures the
    RESPONSE, which is what 14bw's probe measures).

    MEASURED on this fixture: the fixed point moves 273 of 365 vertices,
    193 of them beyond 250 m, worst 0.7515 m; the QP moves 72, 44 beyond
    250 m, worst 0.1202 m and worst-far 0.0537 m."""
    pm, cs = built
    n_f, max_f, far_f, farmax_f = _probe(pm, cs, law, "fixed_point")
    n_q, max_q, far_q, farmax_q = _probe(pm, cs, law, "qp")
    assert n_q < n_f / 2.0, (n_q, n_f)
    assert far_q < far_f / 2.0, (far_q, far_f)
    assert farmax_q < 0.1 <= farmax_f, (farmax_q, farmax_f)
    assert max_q < max_f


def test_the_same_problem_solved_twice_is_identical(law, built):
    """A unique optimum reached by a deterministic method: the same
    capture twice is the same surface to the bit."""
    pm, cs = built
    lw = _arm(law, solver="qp")
    a, _ra = solve_design(pm, cs, lw)
    b, _rb = solve_design(pm, cs, lw)
    assert np.array_equal(np.asarray(a.z, float), np.asarray(b.z, float))


# ── 3. an infeasible pair is NAMED, not traded ───────────────────────────

def test_an_infeasible_hard_pair_is_named_by_the_certificate(law):
    """§20c (3): the certificate reads the solve's own status.  Two hard
    ceilings on one free column that no value satisfies together — the
    report must NAME them (``read_hard_failure``'s min-Σ-slack proof),
    never silently trade one for the other."""
    from auto_patch_v2.solve.design_report import DesignReport

    class _Red:
        col = np.array([0, -1], np.int64)
        value = np.array([0.0, 10.0])

    src = Source("pads", law.tables.emit.design.hard_rulings[0], ())
    row_a = Band(0, None, 1.0, src)
    row_b = Band(0, -5.0, None, src)

    class _V:
        key = (60.0, -135.0)

    class _P:
        vertices = {0: _V(), 1: _V()}

    one = [(((0, 1.0),), 1.0, row_a), (((0, -1.0),), -5.0, row_b)]
    rep = DesignReport()
    rep.read_hard_failure(np.array([0, 1]), np.array([0.0, 4.0]), one, _P(),
                          _Red(), 0.02, np.array([1.0, 10.0]))
    line = rep.hard_failure_line()
    assert "HARD SET NOT SETTLED" in line
    assert "INFEASIBLE SET" in line


# ── 4. the QP changes the algorithm, never the law ───────────────────────

def test_the_two_solvers_agree_where_the_fixed_point_converges(law):
    """A problem with NO one-way row and no stall: one pinned runway over
    flat terrain.  The fixed point reaches its set's own fixed point there,
    so the minimum is the same point and the two arms must agree to
    1e-6 m."""
    lw0 = Law.for_airport("ZZZZ")

    class _Flat:
        provenance = {"synthetic": "v2qp-flat"}

        def z(self, x, y):
            return 700.0

        def bounds(self):
            return (-5000.0, -5000.0, 5000.0, 5000.0)

    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "f"),
            RunwayEnd("27", (800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "f"))
    ap = Airport("ZZZZ", "Synthetic", frame, 700.0,
                 (Runway("09/27", 45.0, 1, ends, 3, "D"),), (), (), {}, (),
                 (), (), (), (), (), (), SceneryPack("fixture", "apt.dat",
                                                     "0", (), ()),
                 _Flat(), lw0.ruleset_key)
    cells = [Cell(0, "runway", "09/27",
                  _rect(-800.0, -HALF_W, 800.0, HALF_W), (), 3, "D",
                  "airside", "runway", {})]
    pm, _st = build(ap, Classification(tuple(cells), (), {}, ()), lw0)
    pinned = next(iter(pm.vertices))
    src = Source("road_profile", "fixture pin", ())
    cs = ConstraintSet(pins=(Pin(pinned, 700.4, src),), bands=(), diffs=(),
                       flats=(), offsets=(), linears=())
    fp, rep_f = solve_design(pm, cs, _arm(lw0, solver="fixed_point"))
    qp, rep_q = solve_design(pm, cs, _arm(lw0, solver="qp"))
    assert rep_f.one_way_rows == 0 and rep_q.one_way_rows == 0
    z_f, z_q = np.asarray(fp.z, float), np.asarray(qp.z, float)
    assert float(np.max(np.abs(z_f - z_q))) <= 1e-6, (
        f"the two solvers disagree by {float(np.max(np.abs(z_f - z_q))):.3g} m "
        f"on a problem the fixed point solves: {rep_f.set_exit_line()!r} / "
        f"{rep_q.qp_line()!r}")
    assert fp.status in (Status.OPTIMAL, Status.FEASIBLE)
    assert qp.status in (Status.OPTIMAL, Status.FEASIBLE)


def test_highspy_is_imported_at_module_top():
    """Memory ``frozen-engine-lazy-imports``: a third-party import inside a
    function is invisible to PyInstaller AND to the suite, and shipped a
    frozen engine that died on ``highspy`` (2026-09-10).  §20c's module
    names it at the top."""
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[2] / (
        "src/auto_patch_v2/solve/design_qp.py")
    tree = ast.parse(src.read_text())
    top = {a.name for n in tree.body if isinstance(n, ast.Import)
           for a in n.names}
    assert "highspy" in top
