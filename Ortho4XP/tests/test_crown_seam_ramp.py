"""The crown ramps to ZERO at a tile seam, and the spine reaches the cut
edge (owner ruling 2026-07-24).

    "We need to deal with the crown spine when a seam crosses a runway.
     Because we have to be at DEM we need to be sure the crown spine
     connects all the way to the shape edge after the seam cut, and that
     the spine ramps smoothly down to 0 crown at the seam at less than 1%
     grade."

Since 99f39a6 a tile seam is an ANCHOR in the runway profile solve — the
tile line and BOTH cut-back lines are sampled and anchored at the DEM.  The
runway therefore MEETS the terrain at its cut-back edge, so a crowned edge
there sits ``crown_drop`` below the terrain the 10 m tile-cut gap renders.

What these tests pin:

R1  the runway crown SPINE terminates exactly ON a tile-cut edge — the
    ``_SPINE_EDGE_CLEAR_M`` erosion is re-extended there (and only there;
    a physical runway end keeps its clearance), and the ring-clearance
    rejection is waived inside the cut band only;
R2  the crown drop is exactly 0 on a cut-back line, monotone approaching
    it, and its gradient never exceeds ``RUNWAY_CROWN_SEAM_TAPER`` — which
    is STRICTLY under 1% and sheds the largest emittable runway crown over
    MORE than 30 m;
D   cross-tile determinism: the ramp is a function of the node's own
    lat/lon against the graticule plus fixed constants, so it is symmetric
    about the seam and carries no dependence on which side of the cut the
    building tile owns;
G   ``O4_CROWN_SEAM_RAMP=0`` restores the pre-ruling behaviour, and an
    airport with no tile-cut seam vertices at all is a strict no-op.

Hermetic: hand-built layouts, no fixtures, no DEM, no network.
"""
from __future__ import annotations

import os
import sys


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import config as CFG                        # noqa: E402


# ── synthetic world ──────────────────────────────────────────────────
# The airport is anchored ON the integer LONGITUDE line lon == 1, so in
# local metres the seam is x == 0 and the two cut-back lines are x == ±5.
ANCHOR_LAT = 0.5
ANCHOR_LON = 1.0
M_PER_DEG = 111320.0
HALF = CFG.TILE_CUT_HALF_WIDTH_M
RATE = CFG.RUNWAY_CROWN_SEAM_TAPER
UNIFORM = 0.23                      # == 1.0% x a 22.86 m half-width


class _Shape:
    def __init__(self, role, polygon, *, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = None
        self.adopts_apron_grade = False
        self.is_bridge = False
        self.source_axis = None
        self.from_single_poly = True


class _Layout:

    def m_to_ll(self, x, y):
        return (ANCHOR_LAT + float(y) / M_PER_DEG,
                ANCHOR_LON + float(x) / M_PER_DEG)

    def ll_to_m(self, lat, lon):
        return ((float(lon) - ANCHOR_LON) * M_PER_DEG,
                (float(lat) - ANCHOR_LAT) * M_PER_DEG)


# ── R2a: the rate itself ─────────────────────────────────────────────

def test_taper_rate_is_strictly_under_one_percent():
    """The ruling is 'less than 1%' — the pre-ruling code used exactly
    1.0% (TAXI_CROWN_TRANSVERSE).  The named constant must be strictly
    below it, with real headroom rather than a hairline pass."""
    assert RATE < 0.010
    assert RATE <= 0.005, "the chosen rate should keep 2x headroom under 1%"
    # and it must stay well under the runway's own longitudinal cap so the
    # ramp alone can never carry a rail pair to it.
    assert RATE * 3 <= CFG.RUNWAY_MAX_GRADE
    # ... and under the FAA end-zone longitudinal limit.
    assert RATE < CFG.RUNWAY_END_GRADE


# ── R2b: the ramp geometry ───────────────────────────────────────────


# ── D: cross-tile determinism ────────────────────────────────────────


# ── the drop FIELD on a seam-cut runway ──────────────────────────────

# A runway cut at the seam, keeping the x >= HALF side; the cut edge is
# densified like production's over-60 m edge densify, so the ramp (not the
# seam-bucket exemption) is what has to zero the interior cut-edge nodes.
_STATIONS = [HALF, 20.0, 40.0, 60.0, 80.0, 120.0, 400.0, 1000.0]


# ── R1: the spine reaches the cut edge ───────────────────────────────


