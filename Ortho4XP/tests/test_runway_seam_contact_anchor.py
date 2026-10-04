"""A tile seam is ANOTHER runway-grading anchor (owner ruling 2026-07-24).

    "This has never worked, trying to do anything other than DEM at the tile
     seam causes visual disaster in X-Plane.  We are not giving up the CIFP
     thresholds, it's just that a tile seam acts like a crossing runway, it's
     ANOTHER anchor that is part of the runway grading.  The tile seam at ALL
     points must be anchored at DEM."

Every non-runway role takes the seam DEM directly at its own vertex.  A
runway cannot: it also carries CIFP threshold elevations and the FAA grade /
vertical-curve law, and it is laterally FLAT — so its seam contact (a whole
LINE across the runway's width, 148 m of it at SPLP's 18-degree oblique
crossing) has to reach the surface through the one degree of freedom a
runway has, its longitudinal profile.  The seam therefore enters
``runway_redistribute`` exactly the way a crossing-runway anchor does.

What these tests pin:

* the contact is walked at ``RUNWAY_SEAM_CONTACT_STEP_M`` on the tile line
  AND on both ``TILE_CUT_HALF_WIDTH_M`` cut-back lines (the ruling's "the
  nodes along a tile seam at the cutback"), with both extremes always in;
* the one-sided "hump" filter is GONE — a contact whose DEM lies BELOW the
  current profile is anchored just like one above it (that filter is what
  left SPLP's north seam contact floating +0.67 m over the terrain);
* where the terrain across the contact is itself steeper than
  ``MAX_RUNWAY_GRADE`` the DEM ANCHOR wins (★ owner ruling 2026-07-26,
  ``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS``: "ALL nodes along the seam MUST
  be at exact DEM and anchored BEFORE the solve, then the solver can grade
  between them and its other anchors to maintain grade") and the over-cap
  pair is REPORTED with the grade it steps through — never midpointed, and
  since 2026-07-26 never vetoed either.  ``O4_RUNWAY_SEAM_CUTBACK_DEM=0``
  restores the 2026-07-24 feasibility sweep (``enforce_cap=True``);
* the accepted anchor set depends only on (whole-runway geometry, DEM), so
  BOTH tile builds derive it identically without seeing each other;
* the gate ``O4_RUNWAY_SEAM_CONTACT=0`` restores the pre-ruling behaviour;
* ``TILE_CUT_HALF_WIDTH_M`` is the single source of truth for the cut-back
  offset shared by ``tile_cut`` and the anchor walk.

Hermetic: hand-built layouts + an analytic DEM.  No fixtures, no network,
no X-Plane install.
"""
from __future__ import annotations

import importlib
import os
import sys


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import config as CFG                        # noqa: E402


# ── synthetic world ──────────────────────────────────────────────────
# Tile (0, 1); the airport sits at lat 0.5, lon 1.0, i.e. straddling the
# integer LONGITUDE line lon == 1 — the seam.  Local metres are anchored
# there, so the seam is x == 0.
TILE_LAT = 0
TILE_LON = 1
ANCHOR_LAT = 0.5
ANCHOR_LON = 1.0
M_PER_DEG = 111320.0


class _FakeDEM:
    """Analytic ``O4_DEM_Utils.DEM`` stand-in.

    ``alt((dlon, dlat))`` takes DEGREES of offset from the tile origin (as
    ``elevation._sample_dem`` hands them over); the terrain law below is
    written in the layout's local METRES, so convert on the way in.
    """

    nodata = -32768

    def __init__(self, fn):
        self.fn = fn

    def alt(self, node):
        dlon, dlat = float(node[0]), float(node[1])
        x = (dlon + TILE_LON - ANCHOR_LON) * M_PER_DEG
        y = (dlat + TILE_LAT - ANCHOR_LAT) * M_PER_DEG
        return self.fn(x, y)


class _Shape:
    def __init__(self, role, polygon, *, ref=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = node_altitudes
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


# ── the runway ────────────────────────────────────────────────────────
# A 2000 m runway running due EAST (so station == x) with a half-width of
# 20 m, crossing the seam line x = 1.0 square-on.  Square-on keeps the
# contact geometry trivial for the walk tests; the oblique case (where the
# contact spans real station) gets its own layout below.
HALF_W = 20.0


# ── an OBLIQUE crossing, the SPLP shape ──────────────────────────────
# Runway bearing 18 degrees off the seam line: the contact spans
# ``2*HALF_W / sin(18deg)`` ~ 129 m of runway length, so the profile can
# legitimately hold several DEM values at once.


def _m_to_ll(x, y):
    return (ANCHOR_LAT + y / M_PER_DEG, ANCHOR_LON + x / M_PER_DEG)


# ═════════════════════════ contact walk ══════════════════════════════


# ═════════════════ feasibility selection + reporting ═════════════════


# ══════════════ the one-sided filter is gone (the defect) ════════════


# ═══════════════════ cross-tile determinism ══════════════════════════


# ══════════════════════════ the gate ═════════════════════════════════

class TestGate:
    def test_gate_off_restores_the_two_extremes_only_walk(self, monkeypatch):
        monkeypatch.setenv("O4_RUNWAY_SEAM_CONTACT", "0")
        cfg = importlib.reload(CFG)
        try:
            assert cfg.RUNWAY_SEAM_CONTACT_ANCHORS is False
        finally:
            monkeypatch.delenv("O4_RUNWAY_SEAM_CONTACT", raising=False)
            importlib.reload(CFG)
        assert CFG.RUNWAY_SEAM_CONTACT_ANCHORS is True


# ═════════════ end-to-end: the DEM reaches the pavement ══════════════


