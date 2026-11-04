"""#1332 (owner 2026-11-04): pavement past a runway end with no declared
overrun is a blast pad that follows the DEM (``classify/blast_pad``).

The fixture is a 1200 m runway 09/27 with a 60 m x 80 m page past the 27
end (the GCLA 36 shape: wider than the runway, touching the end edge)."""
from __future__ import annotations

import dataclasses as _dc

from auto_patch_v2.classify.blast_pad import blast_pad_end
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Runway, RunwayEnd
from shapely.geometry import box

LAW = Law.for_airport("ZZZZ")
TOL = 1.0


def _runway(overrun: float = 0.0) -> Runway:
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, overrun, 700.0, "fixture"))
    return Runway("09/27", 45.0, 1, ends, 4, "E")


def test_a_page_past_the_end_is_a_blast_pad():
    assert blast_pad_end(box(600.0, -30.0, 680.0, 30.0), [_runway()], LAW, TOL) == ("09/27", "27")


def test_a_declared_overrun_keeps_the_runway_s_own_slab():
    assert blast_pad_end(box(600.0, -30.0, 680.0, 30.0), [_runway(80.0)], LAW, TOL) is None


def test_a_page_beside_the_runway_or_off_the_end_edge_is_not():
    rw = [_runway()]
    assert blast_pad_end(box(300.0, 30.0, 380.0, 90.0), rw, LAW, TOL) is None   # beside it
    assert blast_pad_end(box(640.0, -30.0, 700.0, 30.0), rw, LAW, TOL) is None   # 40 m out
    # an apron mostly outside the end's box
    assert blast_pad_end(box(600.0, -30.0, 680.0, 400.0), rw, LAW, TOL) is None


def test_the_fixture_end_has_no_overrun():
    assert _dc.asdict(_runway().ends[1])["overrun_m"] == 0.0
