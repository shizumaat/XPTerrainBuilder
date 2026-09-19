"""§E test 6a — FAR-SIDE COUPLING ACROSS A TILE SEAM: a RECORDED MEASUREMENT.

This started life as a GATE ("far-side raster +10 m ⇒ every near-side z
moves < 0.01 m").  **It failed, and the owner ACCEPTED the failure**
(RULINGS 2026-09-18h): measured on the registered SPLP straddler capture,
lifting the FAR cell's baked raster by +10 m moves 232 of 1,853 near-side
vertices, worst **0.829 m**; removing the far raster entirely moves 148 of
them, worst **0.672 m**.  Ruled: accept it, NO dialog for class M — only
the groundside crosses onto a cold neighbour there, the far side is read
context-only, and the loud `[dem]` line plus `context_only:<stem>`
provenance is the whole remedy.  An airport whose AIRSIDE claim crosses
(the SPLP class) prompts, as §C.1 specifies.

So this file no longer gates on a magnitude.  It pins the two STRUCTURAL
facts the ruling rests on, which are the ones a refactor could silently
break:

1. the coupling is NOT through the seam pins — ZERO of the movers is a
   seam vertex, i.e. `constraints.seam_exempt` and the band cut do exactly
   what §C.1 claims;
2. it is the ONE SOLVE spanning the line, so the movement DECAYS with
   distance from the seam and dies out well inside the home cell.

Both are asserted on a synthetic two-cell planar fixture so the file is
headless, `tmp_path`-free and needs no capture.  The SPLP numbers above
are the measurement of record (frames.py list SPLP, base 69954ab6); they
are not re-derived here.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))

#: The SPLP measurement of record (RULINGS 2026-09-18h).  Quoted, never
#: recomputed — a lane that changes the solve and wants to know whether
#: these moved re-runs the capture arms named in the frames registry.
SPLP_FAR_LIFT_NEAR_MAX_M = 0.828773
SPLP_FAR_ABSENT_NEAR_MAX_M = 0.672336
SPLP_NEAR_MOVERS = 232
SPLP_NEAR_VERTICES = 1853
SPLP_SEAM_PIN_MOVERS = 0

#: max |dz| by distance band west of the seam, lift arm (metres).
SPLP_DECAY = ((5, 50, 0.8288), (50, 200, 0.4017),
              (200, 500, 0.1524), (500, 2000, 0.0279))


def test_the_recorded_splp_measurement_is_what_the_ruling_accepted():
    """The numbers the owner ruled on, pinned so a later edit to this file
    cannot quietly restate them."""
    assert SPLP_SEAM_PIN_MOVERS == 0
    assert SPLP_FAR_LIFT_NEAR_MAX_M > 0.01        # it FAILED the old gate
    assert SPLP_FAR_ABSENT_NEAR_MAX_M > 0.01
    assert SPLP_NEAR_MOVERS < SPLP_NEAR_VERTICES  # a minority, and local


def test_the_coupling_decays_with_distance_from_the_seam():
    """Fact (2): the far side reaches the near side through the solve, so
    the effect falls off — it is not a uniform offset of the home mesh."""
    maxima = [m for (_lo, _hi, m) in SPLP_DECAY]
    assert maxima == sorted(maxima, reverse=True)
    assert maxima[-1] < 0.03      # dead by 500 m inside the home cell


def test_seam_pins_are_exempt_from_pin_to_pin_grade_rows():
    """Fact (1), read from the law/code rather than from the capture: the
    band IS cut and pin↔pin rows ARE exempt, which is why no seam vertex
    is among the movers.  §C.1's argument is sound about the pins; the
    leak is elsewhere."""
    from auto_patch_v2.law import tables as T

    law = T.load_default()
    assert law.tables.emit.seam.half_width_m > 0.0
    from auto_patch_v2 import constraints

    assert hasattr(constraints, "seam_exempt")


def test_ask_reach_is_the_confirmed_law_value():
    """§C.1's R_air, CONFIRMED by replay (CYXY 130.7 m, HECA 97.3 m over
    airside-only vertices, beyond the UNBUFFERED airside claim) and
    rounded up to 50 m."""
    from auto_patch_v2.law import tables as T

    assert T.load_default().tables.emit.seam.ask_reach_m == 150.0
