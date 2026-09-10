"""THE NEAREST-THRESHOLD CROSSING PIN (owner RULINGS 2026-09-09z (1),
superseding 09r (2); spec ``docs/specs/auto-patch-v2/design-surface-
spec.md`` §17; lane ``v2crossing``).

The owner, verbatim: "V1 takes the closest threshold to the crossing,
solves that runway, then sets the crossing node as an anchor for the other
runway(s) to grade to, same logic as a tile seam boundary or the CIFP
threshold."  V1's own site is ``src/auto_patch/pavement/runway_segments.py``
"Runway-runway centerline-crossing reconciliation" — "whichever runway has
the threshold geometrically closer to the crossing point gets its
CIFP-linear-interp value used as the agreed altitude".

The fixture is the CYXY shape (``test_v2cyxy._crossing_airport``): 09/27
1,200 m, 700 -> 706, crossing at its midpoint (600 m from either
threshold); 18/36 1,000 m, 701 -> 701, crossing at ITS midpoint (500 m
from either threshold).  18/36's threshold is the nearer, so 18/36
GOVERNS both, hands the node 701.0 m, and 09/27 — which wants 703.0 there
on its straight chord — grades to it inside its own hard laws.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.runway_chord import (ChordReport, PIN_GEN,
                                                    crossing_governor,
                                                    runway_chord_targets,
                                                    runway_crossing_pins,
                                                    runway_crossings)
from auto_patch_v2.constraints.runway_profile import ridge_chains, threshold_pins
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import design as design_law
from auto_patch_v2.law.tables import role_cap, runway_vertical_curve_bound
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS
from auto_patch_v2.constraints import roads
from tests.auto_patch_v2.test_v2cyxy import (RUN_LEN, _PlaneDem, _airport,
                                             _crossing_airport)
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect

GOV = "18/36"          # the governing runway: its threshold is 500 m away
OTHER = "09/27"        # 600 m away — it grades to the node
Z_NODE = 701.0         # the governing runway's own chord at the crossing


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def crossing(law):
    airport, r, cells = _crossing_airport(law, _PlaneDem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return airport, pm


@pytest.fixture(scope="module")
def solved(law):
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.solve import Status, solve_design
    airport, _r, cells = _crossing_airport(law, _PlaneDem())
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    return airport, pm, np.asarray(sol.z, float), rep, sol


def _profile(pm, law, z, rid):
    """``[(station, z)]`` along a runway's ridge, in axis order."""
    axis = 1 if rid == GOV else 0
    pts = [(pm.vertices[v].xy[axis], float(z[v]))
           for ch in ridge_chains(view(pm, law)).get(rid) or [] for v in ch]
    pts.sort()
    return pts


# ── 1. THE REGISTER: the nearest threshold governs ───────────────────────

def test_the_runway_with_the_nearest_threshold_governs_the_crossing(crossing, law):
    """09z (1)'s register, and v1's: NOT the longer runway (09r (2)'s
    refuted seniority would have picked 09/27, 1,200 m against 1,000 m) —
    the one whose THRESHOLD is nearest the node.  The answer never depends
    on the order the two ids arrive in."""
    airport, pm = crossing
    xings = runway_crossings(pm, law, airport)
    assert len(xings) == 1, xings
    x = xings[0]
    assert (x.governing, x.other) == (GOV, OTHER)
    assert x.d_gov < x.d_other, "the governing runway's threshold is the nearer"
    assert abs(x.z_pin - Z_NODE) <= 0.01, x.z_pin
    from auto_patch_v2.constraints.runway_chord import _chords
    chords, _ = _chords(pm, law, airport)
    assert crossing_governor(airport, chords, x.xy, OTHER, GOV) == (GOV, OTHER)
    assert crossing_governor(airport, chords, x.xy, GOV, OTHER) == (GOV, OTHER)


# ── 2. THE GOVERNING RUNWAY'S CHORD IS UNCHANGED ─────────────────────────

def test_the_governing_runways_chord_passes_through_the_crossing_unchanged(crossing, law):
    """"the runway ... solves that node": its chord target is the straight
    line between its own two CIFP thresholds across the crossing, exactly
    as it is for a runway with no crossing at all."""
    airport, pm = crossing
    rep: ChordReport = {}
    targets = runway_chord_targets(pm, law, airport, rep)
    assert rep["crossings"][0]["governing"] == GOV
    crown = law.tables.common.runway_crown_transverse
    ridge = {v for ch in ridge_chains(view(pm, law)).get(GOV) or [] for v in ch}
    got = 0
    for v in ridge:
        if v not in targets:
            continue
        got += 1
        assert abs(targets[v] - Z_NODE) <= 0.02 + crown * 1.0, \
            f"the governing runway's ridge target {targets[v]:.3f} left its chord"
    assert got > 4, "the governing runway must carry ridge targets"


# ── 3. THE OTHER RUNWAY GRADES TO THE PIN ────────────────────────────────

def test_the_crossing_node_is_a_hard_pin_on_the_other_runway(crossing, law):
    """"sets the crossing node as an anchor ... same logic as a tile seam
    boundary or the CIFP threshold": ONE hard ``Pin``, on the graded
    runway's ridge vertex at the node, at the governing chord's value —
    and NONE on the governing runway, which solves the node itself."""
    airport, pm = crossing
    rows = runway_crossing_pins(pm, law, airport)
    assert len(rows) == 1, rows
    row = rows[0]
    assert isinstance(row, Pin) and row.source.generator == PIN_GEN
    assert abs(row.z - Z_NODE) <= 0.05, row.z
    assert row.v not in threshold_pins(pm, law, airport), \
        "a CIFP threshold vertex is never re-pinned"
    ridge_other = {v for ch in ridge_chains(view(pm, law)).get(OTHER) or [] for v in ch}
    ridge_gov = {v for ch in ridge_chains(view(pm, law)).get(GOV) or [] for v in ch}
    # the noding WELDS the two ridges at the intersection, so the node is
    # one shared vertex — pinning it holds both runways at the agreed
    # elevation, which is exactly v1's ``auto_extra_anchors`` for BOTH
    assert row.v in ridge_other
    assert row.v in ridge_gov or len(ridge_other & ridge_gov) == 0
    x, y = pm.vertices[row.v].xy
    assert abs(x) <= HALF_WIDTH + 1.0 and abs(y) <= HALF_WIDTH + 1.0, \
        "the pinned vertex is the node's own ridge station"


def test_the_pin_reaches_the_solve_and_the_other_runway_passes_through_it(solved, law):
    """The pin is an EQUALITY: ``solve/rows._reduce`` eliminates its vertex,
    so the graded runway's profile passes through the node's elevation
    exactly, instead of the two conflicting chords splitting the ~2 m
    difference and dipping (spec §13.2)."""
    airport, pm, z, _rep, _sol = solved
    row = runway_crossing_pins(pm, law, airport)[0]
    assert abs(float(z[row.v]) - row.z) <= 1e-6, \
        f"the crossing pin did not hold: {float(z[row.v]):.4f} vs {row.z:.4f}"
    pts = _profile(pm, law, z, OTHER)
    mid = [zz for s, zz in pts if abs(s) <= HALF_WIDTH + 1.0]
    assert mid, "the graded runway must carry ridge stations at the node"
    assert abs(float(np.mean(mid)) - Z_NODE) <= 0.2, \
        f"the graded runway sits at {np.mean(mid):.3f} at the node, not {Z_NODE}"


def test_the_graded_runway_holds_its_own_hard_laws_through_the_pin(solved, law):
    """"all crossing runways must stay within the runway grade laws": the
    graded runway keeps its CIFP thresholds, its longitudinal cap and its
    vertical-curve K while carrying the node's elevation."""
    airport, pm, z, _rep, _sol = solved
    pts = _profile(pm, law, z, OTHER)
    assert len(pts) > 4
    assert abs(pts[0][1] - 700.0) <= 0.05 and abs(pts[-1][1] - 706.0) <= 0.05, \
        "a re-fit chord never releases the CIFP threshold pins"
    cap = role_cap(law, "runway", 3, "D").longitudinal
    tol = float(design_law(law).hard_tol_m)
    for (s0, z0), (s1, z1) in zip(pts, pts[1:]):
        d = abs(s1 - s0)
        if d < 1e-6:
            continue
        assert abs(z1 - z0) <= cap * d + tol, \
            f"grade {(z1 - z0) / d:.5f} over its cap {cap} at s {s0:.0f}"
    sp = float(np.mean([abs(b[0] - a[0]) for a, b in zip(pts, pts[1:])]))
    bound = runway_vertical_curve_bound(law, sp, 3, "D")
    if bound is not None:
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            d0, d1 = b[0] - a[0], c[0] - b[0]
            if d0 < 1e-6 or d1 < 1e-6:
                continue
            g = (c[1] - b[1]) / d1 - (b[1] - a[1]) / d0
            assert abs(g) <= bound + 0.02, \
                f"grade change {g:.5f} over K's {bound:.5f} at s {b[0]:.0f}"


def test_both_defect_readers_read_zero_at_the_crossing(solved, law):
    """The bar: the surface the crossing pin produces mints NO runway
    DEFECT row — §16's projection spreads the node into a vertical curve
    rather than a V."""
    airport, pm, _z, _rep, sol = solved
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    got = {k: len(rows[k]) for k in DEFECT_KEYS}
    assert got == {k: 0 for k in DEFECT_KEYS}, got


# ── 4. A SINGLE RUNWAY IS UNCHANGED ──────────────────────────────────────

def test_a_single_runway_mints_no_crossing_pin_and_keeps_its_chord(law):
    """The inertness proof: with no ``runway_crossing`` face there is no
    node, no pin, and the chord targets are the straight line between the
    thresholds — the shape every non-crossing airport already had."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.constraints.precedence import view as _view
    airport, r = _airport(law, _PlaneDem(), thresholds=(700.0, 706.0))
    cells = (Cell(0, "runway", "09/27",
                  _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2, HALF_WIDTH),
                  (), 3, "D", "airside", "runway", {}),)
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    assert runway_crossings(pm, law, airport) == []
    assert runway_crossing_pins(pm, law, airport) == []
    rep: ChordReport = {}
    targets = runway_chord_targets(pm, law, airport, rep)
    assert rep["crossings"] == [] and rep["crossing_pins"] == 0
    crown = law.tables.common.runway_crown_transverse
    for v in {v for ch in ridge_chains(_view(pm, law)).get("09/27") or [] for v in ch}:
        if v not in targets:
            continue
        s = pm.vertices[v].xy[0]
        want = 700.0 + 6.0 * (s + RUN_LEN / 2) / RUN_LEN
        assert abs(targets[v] - want) <= 0.05 + crown * 1.0, \
            f"a single runway's chord moved: {targets[v]:.3f} vs {want:.3f}"
