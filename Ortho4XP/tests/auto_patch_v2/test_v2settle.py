"""The v2settle twins (owner RULINGS 2026-09-09y; lane ``v2settle``): THE
FINAL PROJECTION — after the design solve, every non-runway vertex is FIXED
at its solved z and the runway family's vertices are re-solved as a QP
holding every runway-family hard row EXACTLY
(``auto_patch_v2/solve/project.py``).

The design solve's augmented Lagrangian cannot certify the hard set (09r
(3) / 09v (3): the multiplier sequence oscillates on a real airport at every
weight measured), and on 09y its residual landed on RUNWAY rows at HECA —
``runway_transverse`` 1 at 0.50 m and ``runway_vertical_curve`` 4 at
0.24-0.33 m, DEFECTs the app's gate refuses.

The twins state the projection's contract on the ``ridge`` fixture
(``test_v2ridge.build_ridge``: a 1,200 m runway, a parallel taxiway and two
stubs), with the violation INJECTED into the solved surface rather than
hoped for from the solve — the contract is "whatever the solve leaves, the
projection settles", so the twin hands it a surface that violates:

1. a KINK on the ridge puts K rows far over their bound; the projection
   settles every runway-family hard row to the law's own HELD bar
   (``[design] hard_tol_m``, :func:`held_m` — reported deviation 1 of
   ``solve/project.py``) and both DEFECT readers read 0 on the emitted
   patch, where they read the kink without it;
2. the rest of the surface is UNTOUCHED — every vertex outside the runway
   family keeps the value the design solve gave it, to the bit;
3. the threshold pins hold EXACTLY (they are fixed vertices: the projection
   never has a column for them);
4. a surface with no violation is returned unchanged — max move 0;
5. ``[design] runway_projection = false`` is the DIAGNOSTIC ARM: the solve
   returns its own surface and the report says so.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import numpy as np
import pytest

from auto_patch_v2.constraints import generate, roads
from auto_patch_v2.constraints.runway_profile import ridge_chains, threshold_pins
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import solve_design
from auto_patch_v2.solve.design import DesignReport, assemble
from auto_patch_v2.solve.project import (free_columns, project_runway,
                                         runway_family_vertices)
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS
from tests.auto_patch_v2.test_v2ridge import build_ridge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

#: the injected kink: three consecutive ridge stations pushed off the
#: profile, which puts the vertical-curve K rows around them far over bound
KINK_M = 0.6
KINK_STATIONS = (40, 41, 42)

#: the QP's own feasibility tolerance
EXACT_M = 1.0e-4


def held_m(law) -> float:
    """The law's own definition of a HELD row (``[design] hard_tol_m``): the
    bar the projection settles every runway-family hard row to.  It is under
    the census's per-node rounding envelope (0.03 m) and far under the rate
    readers' quantum (0.1 m), so a row held here mints no DEFECT row —
    which is what "0 by construction" means on the readers' own instrument.
    Projecting to EXACT zero instead buys no reading and costs surface
    (measured CYXY, lane ``v2settle``: a 0.027 m residual already inside the
    envelope pulled the runway 2.16 m and took the census 428 -> 464)."""
    return float(law.tables.emit.design.hard_tol_m)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def ridge(law):
    return build_ridge(law)


@pytest.fixture(scope="module")
def solved(ridge, law):
    """The design surface of the ridge fixture, with the assembled problem
    the projection reads (``Base``) beside it."""
    airport, pm, _ = ridge
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    base = assemble(pm, cs, law, DesignReport())
    return airport, pm, cs, sol, rep, base


def _columns(base, z) -> np.ndarray:
    """The reduced column vector of a full ``z`` (a column's value is any of
    its vertices' — a ``Flat`` group is one rigid value)."""
    red = base.red
    x = np.zeros(red.n_cols)
    for v in range(len(red.col)):
        c = int(red.col[v])
        if c >= 0:
            x[c] = float(z[v])
    return x


def _full(base, x, n) -> np.ndarray:
    red = base.red
    return np.where(red.col >= 0, x[np.clip(red.col, 0, None)], red.value)[:n]


def _kinked(ridge, law, solved):
    """The solved surface with three ridge stations pushed off the profile:
    a K violation no census envelope can absorb."""
    airport, pm, _cs, sol, _rep, base = solved
    z = np.asarray(sol.z, float).copy()
    ch = ridge_chains(view(pm, law))["09/27"][0]
    for k, st in enumerate(KINK_STATIONS):
        z[ch[st]] += KINK_M * (1.0 if k % 2 == 0 else -1.0)
    return z


def _readers(ridge, law, z, tmp_path):
    """The DEFECT families read on the patch this ``z`` emits."""
    airport, pm, _ = ridge
    sol = _dc.replace(_SOL[0], z=tuple(float(v) for v in z))
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    return {k: len(rows[k]) for k in DEFECT_KEYS}


#: the Solution the readers re-dress with each z (module-level so ``_readers``
#: keeps one signature); set by the first test that needs it
_SOL: list = [None]


# ── 1. the kink is settled, and the DEFECT readers read 0 ────────────────

def test_a_k_row_over_its_bound_is_projected_to_zero_violation(ridge, law, solved,
                                                               tmp_path):
    airport, pm, cs, sol, _rep, base = solved
    _SOL[0] = sol
    z_kink = _kinked(ridge, law, solved)
    x_kink = _columns(base, z_kink)
    x_out, prep = project_runway(pm, law, base, x_kink)
    assert prep.ran, prep.status
    # the kink IS a violation the projection had to remove...
    assert prep.before_m > 0.1, prep.as_dict()
    # ...and every row whose feet are all inside the runway family is held
    # to the solver's own tolerance afterwards
    assert prep.after_family_m <= held_m(law) + EXACT_M, prep.as_dict()
    assert prep.after_m <= max(held_m(law) + EXACT_M,
                               prep.elastic_slack_m), prep.as_dict()
    # the DEFECT readers: the kinked surface is a defect, the projected one
    # reads 0 in BOTH families
    n = len(pm.vertices)
    before = _readers(ridge, law, z_kink, tmp_path)
    after = _readers(ridge, law, _full(base, x_out, n), tmp_path)
    assert sum(before.values()) > 0, before
    assert after == {k: 0 for k in DEFECT_KEYS}, after


# ── 2. the rest of the surface is untouched ──────────────────────────────

def test_every_vertex_outside_the_runway_family_keeps_its_design_value(
        ridge, law, solved):
    airport, pm, cs, sol, _rep, base = solved
    _SOL[0] = sol
    n = len(pm.vertices)
    z_kink = _kinked(ridge, law, solved)
    x_out, prep = project_runway(pm, law, base, _columns(base, z_kink))
    assert prep.ran
    z_out = _full(base, x_out, n)
    family = runway_family_vertices(pm, law)
    free = free_columns(base.red, family)
    outside = [v for v in range(n) if int(base.red.col[v]) < 0
               or not free[int(base.red.col[v])]]
    assert outside, "the fixture has ground outside the runway family"
    assert np.array_equal(z_out[outside], z_kink[outside])
    # ...and the projection DID move the family (it had a kink to settle)
    assert prep.max_move_m > 0.0


# ── 3. the threshold pins hold exactly ───────────────────────────────────

def test_the_threshold_pins_hold_exactly(ridge, law, solved):
    airport, pm, cs, sol, _rep, base = solved
    n = len(pm.vertices)
    pins = threshold_pins(pm, law, airport)
    assert pins, "the fixture pins both thresholds"
    z_kink = _kinked(ridge, law, solved)
    x_out, prep = project_runway(pm, law, base, _columns(base, z_kink))
    z_out = _full(base, x_out, n)
    for v, elev in pins.items():
        assert z_out[v] == pytest.approx(elev, abs=0.0), (v, elev, z_out[v])


# ── 4. a surface with no violation is unchanged ──────────────────────────

def test_a_surface_with_no_violation_is_returned_unchanged(ridge, law, solved):
    airport, pm, cs, sol, _rep, base = solved
    n = len(pm.vertices)
    x0 = _columns(base, np.asarray(sol.z, float))
    # the shipped surface has ALREADY been projected inside ``solve_design``,
    # so projecting it again is the identity: nothing left to settle
    x1, prep = project_runway(pm, law, base, x0)
    assert prep.before_m <= held_m(law) + EXACT_M, prep.as_dict()
    # MOVE ZERO, to the QP's own feasibility tolerance: a projected surface
    # has many rows sitting exactly ON their bound, and HiGHS re-lands them
    # within 1e-7 of it, so the re-solve reports a few hundredths of a
    # MILLIMETRE (measured 3.5e-5 m) — four orders under the elevation
    # materiality (0.01 m), a PASS-with-residual and never a surface change.
    assert prep.max_move_m < 1.0e-4, prep.as_dict()
    assert np.allclose(_full(base, x1, n), np.asarray(sol.z, float), atol=1.0e-4)


# ── 5. the diagnostic arm ────────────────────────────────────────────────

def test_the_law_key_off_is_the_diagnostic_arm(ridge, law, solved):
    airport, pm, cs, sol, _rep, base = solved
    d = law.tables.emit.design
    off = _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit,
                                     design=_dc.replace(d, runway_projection=False))))
    z_kink = _kinked(ridge, law, solved)
    x_kink = _columns(base, z_kink)
    x_out, prep = project_runway(pm, off, base, x_kink)
    assert not prep.ran
    assert "runway_projection" in prep.status
    assert np.array_equal(x_out, x_kink)


# ── the solve ships the projection ON ────────────────────────────────────

def test_the_shipped_solve_runs_the_projection_and_settles_the_family(solved, law):
    _a, _pm, _cs, _sol, rep, _base = solved
    prep = rep.runway_projection
    assert prep.ran, prep.as_dict()
    assert prep.after_family_m <= held_m(law) + EXACT_M, prep.as_dict()
    assert prep.vertices > 0 and prep.columns > 0 and prep.rows > 0
    assert "runway_projection" in rep.as_dict()


# ── EVERY OPTIONAL FIELD OF ``Member`` IS PASSED BY NAME ────────────────
# (lane ``v2settle`` 2026-09-13, measured on the LEMD capture)
#
# ``airport/pack_partition._member_of`` builds every pack member.  It used
# to pass the tail POSITIONALLY, and twice a field inserted into
# ``model.rebake.Member`` slid that tail by one:
#
#   * 2026-09-11t inserted ``plate_clearance_m`` — the viaduct's
#     ``elevated_deck`` read False and ``skirted`` read the clearance;
#   * 5fc707eb (§16e (2)) inserted ``deck_end_stations`` — ``plate_y``
#     landed on the ``()`` meant for ``plate_stations``.  ``plate_y is not
#     None`` is ``planar.group._eligible``'s FIRST test, so at LEMD every
#     one of 14,256 bodies came out ineligible and the pad group law
#     derived groups 0, relief 0, infeasible 0 (it derives 9,820 / 5,036 /
#     3,163).  The whole pad law was silently off, and the build still
#     exited 0.
#
# Neither shift is visible at the call site and neither breaks a type.  The
# only spelling a future insertion cannot break is the keyword, so that is
# what this asserts — on the SOURCE, because a value twin only catches the
# fields it happens to name.

def test_pack_partition_builds_its_Member_entirely_by_keyword():
    import ast
    import pathlib

    src = pathlib.Path(
        __import__("auto_patch_v2.airport.pack_partition", fromlist=["x"]).__file__)
    tree = ast.parse(src.read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "Member"]
    assert calls, "pack_partition no longer builds a Member — retarget this twin"
    for c in calls:
        assert not c.args, (
            f"{src.name}:{c.lineno} passes {len(c.args)} POSITIONAL argument(s) to "
            "Member(); a field inserted into model.rebake.Member silently shifts "
            "them (plate_y -> plate_stations killed the pad group law at LEMD, "
            "2026-09-13). Pass every field by name.")


def test_a_plain_pack_member_carries_no_plate_and_is_group_eligible():
    """The value half: what the shift produced was ``plate_y = ()``, which
    is not None, so ``_eligible`` refused it.  A member with parts and no
    plate is eligible."""
    from auto_patch_v2.model.rebake import Member, Part
    from auto_patch_v2.planar.group import _eligible

    part = Part(pid=1, comp=0, lat=40.0, lon=-3.0, base_y=0.0, area_m2=10.0,
                box=(0.0, 0.0, 1.0, 1.0))
    m = Member(id="dsf:obj1", resource="a.obj", authored_path="/a.obj",
               live_path="/a.obj", heading_deg=0.0, parts=(part,))
    assert m.plate_y is None and m.deck_stations == ()
    assert _eligible(m)
    assert not _eligible(_dc.replace(m, plate_y=0.0))
