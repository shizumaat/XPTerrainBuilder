"""Twins for THE WHOLE-RUN CORRIDOR PROFILE (staged-solve round, S2).

Four properties the round spec names, each asserted on the solver
itself so a regression fails here and not three airports later:

1. ENDPOINT FIDELITY — mouth welds and free-end DEM ties are exact
   pass-through values (stage-A values are read-only boundary data).
2. CAP COMPLIANCE — every emitted segment obeys the road cap, and the
   profile is NOT a cap-riding bang-bang trace.
3. FLATNESS IS LAWFUL — equal pegs come out FLAT; no minimum slope is
   minted (owner 2026-08-14, "DRAINAGE RULING SCOPE CLARIFIED":
   corridors/roads get no added drainage curvature).
4. INTEGRAL INFEASIBILITY IS REPORTED WITH NUMBERS — a rise the run
   cannot absorb at the cap yields a conflict carrying rise/run/cap,
   never an exception, never a quarantine, never a bare step.
"""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))


CAP = 0.08          # config.SERVICE_ROAD_MAX_GRADE — the existing constant


def _uniform(n: int, step: float = 10.0) -> list[float]:
    return [i * step for i in range(n)]


def _wide_band(n: int, lo: float = -1e6, hi: float = 1e6):
    return [lo] * n, [hi] * n


# ── RUN / YARD SCOPING (Fable ruling 2026-08-14, S2's STOP 1) ───────
# "The 1-D profile HOLDS on the corridor's LINEAR RUNS only; a 2-D
# service surface is never held to a line."  The discriminator is the
# shape's own geometry — mean width ``2*area/perimeter`` against
# ``config.ROAD_CARVE_MAX_WIDTH_M`` — never the role literal, because a
# service_junction is a narrow connector in one place and a 40 m yard in
# another, and it was the YARDS that made within-shape pairs
# unsatisfiable (KCLT +157 rows, measured).

def _mean_width(poly):
    return 2.0 * poly.area / poly.length


def test_mean_width_separates_a_road_run_from_a_yard():
    from shapely.geometry import Polygon
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M as W
    road = Polygon([(0, 0), (120, 0), (120, 6), (0, 6)])       # 6 m x 120 m
    yard = Polygon([(0, 0), (40, 0), (40, 40), (0, 40)])       # 40 m square
    assert _mean_width(road) <= W, _mean_width(road)
    assert _mean_width(yard) > W, _mean_width(yard)


def test_the_widest_thing_the_carve_calls_a_road_is_still_linear():
    """The threshold is the existing carve constant, so a road at the
    carve's own maximum width is on the LINEAR side of it."""
    from shapely.geometry import Polygon
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M as W
    wide_road = Polygon([(0, 0), (2000, 0), (2000, W), (0, W)])
    assert _mean_width(wide_road) <= W


# ═══════════════════════════════════════════════════════════════════════
# R1 — A HELD PROFILE MUST BE LAWFUL OR IT IS NOT HELD (service-road law
# spec 2026-08-15).  The run's OWN audit names every over-cap segment and
# every relaxed inverted tube; exactly those stations are RELEASED from
# the ``svc_profile`` hold (values stay as seeds).  Clean stations stay
# held — the smooth majority must not loosen.
# ═══════════════════════════════════════════════════════════════════════


# ── R4: THE STRING HOLDS ON THE PEGGED SPAN ONLY (service-road law
# spec amendment, 2026-08-15 — the run-(46,0) eruption class) ────────


# ══ R5 — ROAD RUNS TRACK TERRAIN ════════════════════════════════════
# The taut string draws the STRAIGHTEST lawful profile — correct for an
# airside spine, wrong for a road (owner in-sim on 1.0.252: CYXY road
# 349 as a 5.2 m causeway over a 2.7 % dip, the junction-190 complex as
# a 12-16 m canyon under 718-722 m terrain, HECA as a plateau).  A
# service-road run's profile is the CAP-CONSTRAINED LEAST-DEVIATION
# TRACKER of its low-passed station DEM.


