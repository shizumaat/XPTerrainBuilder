"""Twins for R5c — GRADED-ROAD CHARACTER (service-road law spec, Fable
2026-08-15; owner in-sim on R5 at CYXY 60.7087015,-135.0746305).

R5's tracker follows the low-passed terrain faithfully — INCLUDING its
wiggles — where the owner wants ROAD character: "a smooth graded
surface".  And the visible road is a COMPOSITE (CYXY ``service_road``
349 + ``service_junction`` 63 on one corridor): each shape took station
values from ITS OWN chain projection, so the corridor could slope
LATERALLY across itself even though every single shape is
cross-section-flat.

Two mechanisms, one twin block each:

1. REVERSAL SUPPRESSION (longitudinal) — a grade reversal whose
   interior amplitude is below ``config.SVC_PROFILE_REVERSAL_MIN_M``
   is levelled through into a monotone bridge; a REAL terrain feature
   at any wavelength survives; the cap and the pegs still bind.
2. CORRIDOR CO-LEVEL (lateral) — a ``service_junction`` vertex within
   the seeder's station reach of an adjoining road's chain joins THAT
   chain's station cluster, so road and junction pieces at equal
   arclength take ONE value.  Multi-chain junctions: mouth welds win,
   then the through-chain of the widest road.
"""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from auto_patch.config import SVC_PROFILE_REVERSAL_MIN_M   # noqa: E402

CAP = 0.08          # config.SERVICE_ROAD_MAX_GRADE — the existing constant


def _uniform(n: int, step: float = 10.0) -> list[float]:
    return [i * step for i in range(n)]


def _wide_band(n: int, lo: float = -1e6, hi: float = 1e6):
    return [lo] * n, [hi] * n


# ══ 1. REVERSAL SUPPRESSION ═════════════════════════════════════════

def test_the_constant_is_the_spec_default():
    """ONE new constant, default 0.4 m (spec wording)."""
    assert SVC_PROFILE_REVERSAL_MIN_M == 0.4


# ── (a) A SYNTHETIC WIGGLE IS LEVELLED THROUGH ──────────────────────


# ══ 2. CORRIDOR CO-LEVEL ════════════════════════════════════════════

from shapely.geometry import LineString  # noqa: E402


#: The seeder's own station reach — ``ROAD_CARVE_MAX_WIDTH_M / 2 + 2``.
REACH_M = 13.0 / 2.0 + 2.0


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ONE CORRIDOR, TWO PIECES.  Road 349's analogue runs along y=0 and
# registers chain 0; junction 63's analogue sits beside it and registers
# its OWN chain 1, five metres off — near enough that both project onto
# either within the station reach, far enough that neither the 2 m XY
# station merge nor the (default-off) wide parallel merge can see them.
_LINES = [LineString([(0.0, 0.0), (40.0, 0.0)]),
          LineString([(0.0, 5.0), (40.0, 5.0)])]
# node 1 is the WELD — shared by both pieces, which is what makes them
# one corridor.
_NODE_POS = {0: (20.0, -2.0), 1: (20.0, 2.0),
             2: (20.0, 4.0), 3: (20.0, 6.0)}


def _raw(node_pos=None, lines=None):
    """The seeder's nearest-chain assignment, before co-level."""
    from shapely.geometry import Point
    node_pos = _NODE_POS if node_pos is None else node_pos
    lines = _LINES if lines is None else lines
    out = {}
    for i, p in node_pos.items():
        P = Point(p)
        best = min(((lines[li].distance(P), li) for li in range(len(lines))),
                   key=lambda t: t[0])
        if best[0] <= REACH_M:
            out[i] = (best[1], lines[best[1]].project(P))
    return out


def test_without_colevel_the_composite_splits_across_two_chains():
    """The premise: nearest-chain assignment puts the junction's
    vertices on a DIFFERENT chain from the road it welds to."""
    raw = _raw()
    assert raw[0][0] == 0 and raw[1][0] == 0
    assert raw[2][0] == 1 and raw[3][0] == 1


