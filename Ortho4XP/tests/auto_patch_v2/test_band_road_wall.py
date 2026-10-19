"""The band's wall against an in-band road, declared at the shared kerb
(owner RULINGS 2026-10-19a / 19i / 19l, #951; ``pipeline/band_road_wall``)."""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest

from auto_patch_v2.law import Law

from test_roadmint100 import _way, _with
from test_roadterrace100 import _solve
from test_wall_step715 import _StepDem

#: a tertiary road leaving the runway's strip southward, down the 8 m step
ROAD = ((750.0, -30.0), (750.0, -400.0))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def test_each_riser_off_a_kerb_below_the_band_is_a_declared_wall(law):
    """Every band ring edge from a shared kerb vertex to a band-only vertex
    standing above it is one ``wall_terrace`` record whose declared step is
    the emitted riser (plus the emit's rounding), its line crossing the
    edge; a kerb at or above its band neighbour declares nothing."""
    from auto_patch_v2.pipeline.band_road_wall import (
        LABEL, band_kerb_risers, band_road_wall_joints)
    a = _dc.replace(_with(_way(-3, ROAD, highway="tertiary")), dem=_StepDem())
    pm, sol, _rep = _solve(a, law)
    z = sol.z
    risers = band_kerb_risers(pm, law)
    assert len(risers) >= 2
    below = [(k, b) for k, b in risers if z[b] - z[k] > 0.01]
    recs = band_road_wall_joints(pm, law, z)
    assert len(recs) == len(below)
    assert band_road_wall_joints(pm, law, None) == []
    for (k, b), r in zip(below, recs, strict=True):
        assert r["kind"] == "wall_terrace" and r["shapes"] == [LABEL]
        assert r["step_m"] == pytest.approx(z[b] - z[k] + 0.01, abs=1e-3)
        (p0, p1) = r["points"]
        (lk, ok), (lb, ob) = pm.vertices[k].key, pm.vertices[b].key
        # the line's midpoint sits on the riser edge
        mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
        cross = (lb - lk) * (mid[1] - ok) - (ob - ok) * (mid[0] - lk)
        assert abs(cross) <= 1e-12 * max(1.0, math.hypot(lb - lk, ob - ok))


def test_the_census_reads_a_band_road_wall_as_lawful_in_the_strip():
    """19i: the wall stands in the safety area by law, so
    ``terrace_joint_strip`` does not read it; any other joint it does."""
    import sys
    from pathlib import Path
    tools = str(Path(__file__).resolve().parents[2] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import check_grade as cg
    wall = {"kind": "wall_terrace", "shapes": [cg.BAND_ROAD_WALL_LABEL],
            "points": [[0.0, 0.0], [0.0, 1e-5]]}
    pack = {"kind": "wall_terrace", "shapes": ["wall.obj#comp0"],
            "points": [[0.0, 0.0], [0.0, 1e-5]]}
    short = {"kind": "wall_terrace", "shapes": [cg.BAND_ROAD_WALL_LABEL],
             "points": [[0.0, 0.0]]}
    assert cg._terrace_joint_strip_exempt([wall, short, pack]) == [True, False]
