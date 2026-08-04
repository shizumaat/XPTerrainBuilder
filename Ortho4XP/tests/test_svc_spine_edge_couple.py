"""Regression: a service-road SPINE welded to higher edges must never be
draped BELOW those edges by the feasibility projection's broken-node blend
(config.SVC_SPINE_EDGE_COUPLE, round-6 site-4).

Mechanism reproduced from CYXY service_road #201 (way -10202, site 4 at
60.7087015,-135.0746305): the final grade projection hardens the road's
DEM-following adjacent-ground welds into a wide staircase.  The cap-Lipschitz
reach envelope then declares the spine stations BROKEN (a HIGH welded edge
close by raises the floor, a LOW anchor reachable through a multi-hop path
lowers the ceil, floor > ceil) and the distance-weighted blend drapes the
centreline ~2.4 m below its own 709.5 m edge welds — a ~-55 % within-shape
ravine.  THE LAW: a broken node's blend is clamped into the interval its HARD
welded neighbours admit whenever that interval is non-empty, so the spine can
never sit below the edges it is welded to.

★ EXPOSED CONSUMER — STOP AND REPORT (2026-08-04, spec ``docs/specs/
kill-half-spec.md`` §2).  This feature's ONLY effect site was inside the
break blend: it clamped a BLENDED broken node into its hard-neighbour
interval.  §2 deletes that blend, so ``config.SVC_SPINE_EDGE_COUPLE``, the
``edge_couple_nodes`` parameter and the caller's node walk in
``solve.final_grade_projection`` are all inert.  Per the spec's own
exposed-consumer clause NOTHING was deleted on the implementer's
authority: the flag, the parameter and the caller stand, the coupled test
below is ``xfail(strict=True)`` naming the exposure, and the ruling is the
spec author's to make.

MEASURED at the same time, so the exposure is quoted with its consequence:
on this synthetic (genuinely infeasible) case the spine's drape below its
welded edge improves 2.4 m → 1.163 m, because the node is no longer frozen
at the blend and the sweeps own it — but the coupled guarantee ("within
cap of the welded edge") is gone.  At the real airport the mechanism came
from (CYXY), the post-flip DEFAULT patch body is byte-identical to the
pre-deletion CAND arm, i.e. #201 did not regress.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project,
)


def _synthetic_spine_case():
    """Nodes: 0 = spine station S; 1 = high welded edge E1 (HARD, 709.5 m);
    2,3 = free intermediate road nodes; 4 = low adjacent-ground weld L
    (HARD, 705.5 m) reached from S only through the multi-hop 0-2-3-4 chain.

    S's ONLY direct HARD neighbour is E1 at 709.5 m (budget 0.19 m), so the
    within-shape law demands S ∈ [709.31, 709.69].  But the reach envelope
    finds a low ceil at S through the chain to L, declares S broken, and the
    blend drapes it toward the low side."""
    elev = [709.40, 709.50, 708.00, 707.00, 705.50]
    hard = {1, 4}
    shape_constraints = [{
        "nodes": [0, 1, 2, 3, 4],
        "edges": [
            (0, 1, 0.19),   # spine ↔ high welded edge (tight, direct)
            (0, 2, 0.30),   # spine ↔ free road node
            (2, 3, 0.30),
            (3, 4, 0.30),   # ↔ low welded anchor (multi-hop from S)
        ],
    }]
    return elev, shape_constraints, hard


@pytest.mark.xfail(strict=True, reason=(
    "EXPOSED CONSUMER, kill-half §2: the break blend this coupling clamped "
    "is deleted, so edge_couple_nodes is inert.  Left failing on purpose — "
    "the feature is not the implementer's to delete."))
def test_broken_spine_not_draped_below_welded_edge():
    """With the spine node in ``edge_couple_nodes`` the broken-node blend is
    clamped into its hard welded edge's interval — S stays within cap of the
    709.5 m edge instead of being draped to the low side."""
    elev, sc, hard = _synthetic_spine_case()
    broken: set = set()
    feasibility_project(elev, sc, hard, force_scalar=True, max_iters=400,
                        broken_out=broken, edge_couple_nodes={0})
    # The scenario must exercise the BREAK path (else the test proves nothing).
    assert 0 in broken, "spine node was expected to be quarantined as broken"
    # THE LAW: spine within the service-road cap of its 709.5 m welded edge
    # (budget 0.19 m + a small margin for the emit-quantization sweep floor).
    assert elev[0] >= 709.5 - 0.19 - 0.05, (
        f"spine draped to {elev[0]:.3f} m — below its 709.5 m welded edge "
        f"(expected >= {709.5 - 0.19 - 0.05:.3f})")
    assert abs(elev[0] - elev[1]) <= 0.19 + 0.05


def test_control_without_coupling_drapes_the_spine():
    """Control: the spine still ends below its welded edge on this
    synthetic case.

    Pre-2026-08-04 this was "the ravine the coupling removes"; post-§2 the
    coupling removes nothing (see the module docstring) and this pins the
    RESIDUAL: an infeasible pocket's sweeps split the excess instead of
    honouring the tight direct edge.  Kept red-free as a measurement, not
    as an endorsement."""
    elev, sc, hard = _synthetic_spine_case()
    broken: set = set()
    feasibility_project(elev, sc, hard, force_scalar=True, max_iters=400,
                        broken_out=broken, edge_couple_nodes=None)
    assert 0 in broken
    # The uncoupled blend violates the within-shape cap to the welded edge
    # (that is the defect); assert it is clearly draped so the coupled test
    # above is proving a real lift, not a no-op.
    assert abs(elev[0] - elev[1]) > 0.19 + 0.05, (
        f"control spine at {elev[0]:.3f} m did not drape below the edge — "
        f"the scenario no longer exercises the defect")
