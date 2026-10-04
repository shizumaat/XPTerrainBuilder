"""Hermetic unit tests for the clean-room single grade graph
(``auto_patch.grade_graph``).  No build/fixtures — pure geometry."""
import pytest


def _square(side=20.0):
    """4-corner square apron/junction ring + keys."""
    ring = [(0.0, 0.0), (side, 0.0), (side, side), (0.0, side)]
    keys = [0, 1, 2, 3]
    return ring, keys


# ── ds_decompose: the anisotropic (Δs∥, Δs⊥) primitive (Phase 1) ──────────────


# ── cT transverse-cap table (Phase 2) ────────────────────────────────────────

def test_taxi_transverse_cap_per_letter():
    """ICAO Annex 14 §3.9.11 transverse caps: A/B → 2 %, C–F → = longitudinal
    (isotropic).  When width-grading is off, cT collapses to cL everywhere."""
    from auto_patch.config import (
        taxi_transverse_cap_for_letter as cT,
        taxi_grade_cap_for_letter as cL,
        TAXI_MAX_TRANSVERSE_NARROW)
    # C–F (and unknown) are isotropic: cT == cL
    for L in ("C", "D", "E", "F", None, ""):
        assert cT(L, enabled=True) == cL(L, enabled=True)
    # A/B earn the 2 % transverse cap when width-grading is on
    assert cT("A", enabled=True) == pytest.approx(0.02)
    assert cT("B", enabled=True) == pytest.approx(TAXI_MAX_TRANSVERSE_NARROW)
    # cT (2 %) is BELOW cL (3 %) for A/B — anisotropic, not looser
    assert cT("A", enabled=True) < cL("A", enabled=True)
    # gate OFF → cT collapses to cL (isotropic) for every letter
    for L in ("A", "B", "C", "F"):
        assert cT(L, enabled=False) == cL(L, enabled=False)


# ── spine-drop census (hygiene 2026-07-31) ───────────────────────────────────


# ── perf P3 lane D: the batched / prefiltered paths are TWINS of the
# per-item paths they stand in for.  Each optimisation below replaces a
# per-item shapely call with a vectorised one, or skips a call whose
# answer is already known; none of them may change a verdict, and none of
# them may be trusted on the comment alone.  Each test runs BOTH paths on
# the same input and asserts equality.


# ── the RUN-SCOPED law memo (perf P3 lane perfgraph) ─────────────────────


def _sig(sc):
    return ([(a, b, cap.cL, cap.cT, cap.budget) for (a, b, cap) in sc.edges],
            sc.spine_chains)


# ── centerline_specs: the input-keyed memo (perf P3 lane perfcenter) ────
#
# THE SINK.  ``centerline_specs`` is THE law's centerline enumeration and it
# had no memo: ``build_context`` walks it twice per graph build and
# ``verification``'s two sidecar exports walk it again, so a build reached it
# 9-11 times and the dupcensus measured ONE distinct input fingerprint behind
# all of them (HECA replay 11/1, full build 9/1).  The memo below serves the
# answer for exactly as long as its INPUTS are unchanged; these twins are the
# proof that "unchanged" means every input, not the ones that happened to
# move at HECA.


# ── the per-ctx CONTENT key (finalarch item 2, RULINGS 2026-08-14) ───


# ═══════════════════════════════════════════════════════════════════════
# R3 — TRANSVERSE CAP WITHOUT A SHARED ROUTE (service-road law spec
# 2026-08-15).  A service-family pair whose endpoints find no SHARED
# nearest route bakes against the nearest route of EITHER endpoint
# (tightest budget wins) instead of staying isotropic at the 8 % road
# cap; a pair genuinely off-network stays isotropic as before.
# ═══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# AN UNDECLARED CROWN ENDPOINT IS UNKNOWN, NOT ON THE RIDGE
# (wave-3 residual sweep; the R8 docket's two "diagonal" ws::runway rows).
#
# The crown field is exported per SOLVE-TIME node.  A ring vertex minted
# after the solve that ``crown.extend_field_to_new_ring_nodes`` did not
# reach is ABSENT from it — and ``crown_by_nid.get(nid, 0.0)`` used to
# read that absence as "sits on the crown ridge", manufacturing an
# expected step equal to its neighbour's whole drop.  Nothing in the
# SOLVER makes that claim: ``build_unified_graph`` constrains only
# SOFT_VISIBILITY_ROLES and ``plane_constraints`` — the runway ring's
# pair set — has no caller outside tools/check_grade.py.
# ══════════════════════════════════════════════════════════════════════


