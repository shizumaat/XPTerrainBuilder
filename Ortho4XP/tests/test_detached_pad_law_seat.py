"""DETACHED BUILDING PADS SEAT BY LAW — item 3(b), 2026-08-05.

OWNER LAW (RULINGS 2026-08-05, "DEM's role, and the constant-DEM
invariant"): *"DEM chooses WHERE in the lawful band a thing seats.  It
never shapes the band, never constrains, never blocks."*

A pad that touches no qualifying airside pavement used to be HARD-PINNED
at its raw-DEM footprint median for the whole solve
(``build_detached_pad_dem_pins`` + ``config.DETACHED_PAD_DEM_PIN``), and
excluded from every movable-pad relaxation.  Both are DELETED.  These
twins pin the replacement:

* the pad is a GROUNDSIDE object, so its datum is the SOLVED groundside
  pavement it abuts, resolved by the adjacent-ground foot rule
  (interpolate two solved host ring variables);
* buildings are FLAT, so the lawful levels are the INTERSECTION over the
  pad's contacts of ``[datum − cap·d, datum + cap·d]``;
* the DEM seed picks the point INSIDE that box and nothing else — which
  is the constant-DEM oracle in unit form: the same solved hosts give the
  SAME box in the plateau and canyon worlds, while the seat saturates at
  the FLOOR and the CEILING respectively;
* NO HOST ⇒ NO BOX and no write.  A missing datum never falls back to
  the DEM sample; that fallback is the defect this replaced.

No network, no DEM, no fixtures: a stub layout and arithmetic.
"""
from __future__ import annotations

import os
import sys

from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


CAP = 0.05                      # GROUNDSIDE_MAX_GRADE, the lot's own cap


class _CPS:
    """Exact-coordinate registry (the real one interns within 0.5 m;
    these twins place every point far enough apart that the two agree)."""

    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Shape:
    def __init__(self, role, ring):
        self.role = role
        self.polygon = Polygon(ring + [ring[0]])


class _Layout:
    def __init__(self, shapes):
        self.canonical_points = _CPS()
        self.shapes = list(shapes)


# ── the fixture geometry ─────────────────────────────────────────────
# A groundside LOT (y ≤ 10) solved at 100 m, and a building pad hovering
# 1 m clear of its edge.  The pad's two near vertices foot onto the lot's
# top edge at d = 1 m; its far vertices are 5 m away, past the contact
# radius, so they contribute nothing.
_LOT = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]


# ══════════════════════════════════════════════════════════════════════
# THE DEM PIN IS GONE
# ══════════════════════════════════════════════════════════════════════

class TestThePinIsDeleted:

    def test_the_gate_no_longer_exists(self):
        from auto_patch import config
        assert not hasattr(config, "DETACHED_PAD_DEM_PIN")


# ══════════════════════════════════════════════════════════════════════
# MEMBERSHIP + THE BAND WITHHOLDING (the attributed writer)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE LAW BOX — solved host variables only
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE SEAT — and the constant-DEM oracle in unit form
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# CYCLE-7 FIX 2 — FRONTAGE COUPLING ⇒ BAND SEATING (owner 2026-08-06)
# ══════════════════════════════════════════════════════════════════════
# Owner, verbatim intent: "A building close enough to have frontage and
# be coupled with the apron has to be seated based on the route graph
# that allows the apron to grade smoothly to its frontage within the
# apron's grade law."  Band-withholding keys on FRONTAGE COUPLING, not
# on touch; no DEM-datum value may bound a frontage-coupled node; a pad
# whose frontage band cannot be derived is a LOUD defect report, never a
# fallback to the datum pin.
#
# THE KNOWN ANSWER these twins are calibrated against (RULINGS 2026-08-06
# "Instrument truth is law", item 1) is the measured HECA carrier:
# building172, band WITHHELD, contact box [1.6576, 1.6576] at the
# groundside datum, an apron partner banded from 62.495 m across a
# 0.0646 m chord budget — a permanent clamp/sweep 2-cycle whose residual
# is 60.772738 m at sweep 1 and at sweep 49,600 alike.  Every case below
# is that arithmetic in eleven nodes.


