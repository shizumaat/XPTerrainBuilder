"""§2 AUTHORITY RETREAT — a sub-tolerance vertex pair must not withdraw it.

REGRESSION (KCLT tunnel_ramp #1658, 2026-08-05).  The ramp at the taxiway
bridge portal abuts junction #650 in plan and sits 12 m below it.  The
retreat pass detected the conflict at three consecutive ring vertices
(spread 12.02 / 12.00 / 12.00 m) and built three faces — then
``_retreat_run_walls`` withdrew the whole retreat because the rebuilt ring
had 5 vertices where the input had 6.

The lost vertex was not a degeneration: two of the ring's vertices sat
0.10 m apart, far inside ``SHARED_VERTEX_TOL_M`` (0.5 m), so the EMITTER
interns them to one node either way.  Retreating both welded them and the
count-equality test read that as the ring collapsing.

Consequence of the withdrawal: the ramp fell back on the emit consensus,
adopted the deck's 215.00 m at those nodes, and shipped an 80.5 % / 12.02 m
within-shape row (plus five siblings and the vertex/midpoint step rows) —
the largest single grade defect in the composed KCLT census.

The law this pins: a retreat may weld together only vertices the emitter
would already have welded; any OTHER vertex loss is a real degeneration and
still withdraws the retreat.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_patch import adjacent_ground as AG              # noqa: E402
from auto_patch.layout import (                           # noqa: E402
    BuiltShape, ROLE_TUNNEL_RAMP, SHARED_VERTEX_TOL_M)

# The production ring, verbatim from the O4_RETREAT_DIAG build (metre
# frame).  Vertices 3 and 4 are 0.10 m apart — one node at emit.
RING = [(-471.44, -1293.29),    # 0 SE corner
        (-470.47, -1274.49),    # 1 NE corner
        (-485.36, -1273.52),    # 2 junction vertex
        (-487.87, -1273.59),    # 3 ramp NW corner   \\ 0.10 m apart
        (-487.88, -1273.69),    # 4 junction vertex  /
        (-488.87, -1293.04)]    # 5 SW corner
OWN = [203.62, 202.98, 202.98, 202.98, 202.98, 203.62]
DECK = {2: 215.00, 3: 214.98, 4: 214.98}


def _shape():
    return BuiltShape(polygon=Polygon(RING + [RING[0]]),
                      role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                      node_altitudes=list(OWN) + [OWN[0]])


def _run(conflict):
    shape = _shape()
    n = len(RING)
    top = [None] * n
    spread = [0.0] * n
    for i, v in conflict.items():
        top[i] = v
        spread[i] = abs(v - OWN[i])
    walls = AG._retreat_run_walls(shape, list(RING), list(OWN),
                                  top, spread, None)
    return shape, walls


def test_the_ring_really_does_carry_a_sub_tolerance_pair():
    """Frame check: the regression only means something if 3-4 are inside
    the emitter's own weld tolerance."""
    (ax, ay), (bx, by) = RING[3], RING[4]
    d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    assert d < SHARED_VERTEX_TOL_M, (
        f"vertices 3-4 are {d:.3f} m apart — not a sub-tolerance pair, so "
        f"this fixture no longer reproduces the KCLT #1658 geometry")


def test_subtolerance_weld_does_not_withdraw_the_retreat():
    shape, walls = _run(DECK)
    assert walls, (
        "the 12 m authority conflict produced no retaining face — the "
        "shape will adopt the winner's value and ship the step "
        "(KCLT #1658: 80.5 %, 12.02 m)")
    # the run retreated: the conflicting vertices no longer sit on the
    # deck edge, and the ring lost exactly the one welded duplicate
    assert len(shape.polygon.exterior.coords) - 1 == len(RING) - 1
    assert shape.node_altitudes is not None
    assert len(shape.node_altitudes) == len(
        shape.polygon.exterior.coords)
    # the shape keeps its OWN values; nothing adopted the deck
    assert max(shape.node_altitudes) < 205.0, (
        f"retreated ring adopted an authority value: "
        f"{shape.node_altitudes}")


@pytest.mark.parametrize("conflict", [
    {2: 215.00},
    {2: 215.00, 3: 214.98},
    {3: 214.98, 4: 214.98},
])
def test_shorter_conflict_runs_still_retreat(conflict):
    _shape_after, walls = _run(conflict)
    assert walls, f"no face for conflict run {sorted(conflict)}"


def test_a_real_degeneration_still_withdraws():
    """The guard must still fire when the retreat genuinely collapses the
    shape — a band far narrower than ``STACKED_WALL_RETREAT_M``."""
    thin = [(0.0, 0.0), (40.0, 0.0), (40.0, 0.2), (0.0, 0.2)]
    shape = BuiltShape(polygon=Polygon(thin + [thin[0]]),
                       role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
                       node_altitudes=[100.0] * 4 + [100.0])
    top = [None, None, 115.0, 115.0]
    spread = [0.0, 0.0, 15.0, 15.0]
    walls = AG._retreat_run_walls(shape, list(thin), [100.0] * 4,
                                  top, spread, None)
    assert not walls
    assert len(shape.polygon.exterior.coords) - 1 == len(thin)
