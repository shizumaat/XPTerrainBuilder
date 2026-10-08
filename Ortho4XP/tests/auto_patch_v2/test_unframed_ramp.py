"""Twins for owner RULINGS 2026-10-08c (1) / 08d (1) — THE 10 % CAP IS A CEILING,
NEVER THE GRADE A RAMP IS BUILT AT (``planar/unframed_ramp.unframed_top``;
law ``[tunnel] ramp_grade`` / ``ramp_max_grade``).

A ramp no object frames is built at its design grade (5 %, 08d (1)) and
steepens toward the cap only where that grade cannot top out in the run it
has — then at the smallest grade that fits.  Found by
the sweep of lane ``sweepwalls``: raising the cap 8 -> 10 % shortened every
mapped tunnel approach on five airports (the cap was read as the climb)."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_m4b as M4B                                         # noqa: E402
from auto_patch_v2.classify.roles import Cell, Classification  # noqa: E402
from auto_patch_v2.law import Law                              # noqa: E402
from auto_patch_v2.planar.basins import read_objects           # noqa: E402
from auto_patch_v2.planar.structure_approach import ramp_top   # noqa: E402
from auto_patch_v2.planar.structures import build_structures   # noqa: E402
from auto_patch_v2.planar.unframed_ramp import unframed_top    # noqa: E402

SPACING = 12.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ground(fn):
    """An airport whose DEM is ``fn(x)`` and an axis running along +x."""
    airport = types.SimpleNamespace(dem=types.SimpleNamespace(z=lambda x, y: fn(x)))
    return airport, (lambda s: (s, 0.0))


def test_the_law_keeps_the_design_grade_under_the_cap(law):
    tn = law.tables.structures.tunnel
    assert 0.0 < tn.ramp_grade <= tn.ramp_max_grade
    # two numbers: the design (08d (1)) and the ceiling (07d)
    assert tn.ramp_grade == pytest.approx(0.05) and tn.ramp_max_grade == pytest.approx(0.10)


def test_ample_run_builds_at_the_design_grade_not_at_the_cap(law):
    """Flat ground 5.1 m over the mouth and nothing in the way: the ramp
    is the design-grade ramp ``ramp_top`` gives — LONGER than the cap's."""
    tn = law.tables.structures.tunnel
    airport, axis = _ground(lambda x: 0.0)
    grade, s_top, ss = unframed_top(airport, law, axis, -5.1, 0.0, SPACING)
    want_top, want_ss = ramp_top(airport, law, axis, -5.1, 0.0, SPACING, grade=tn.ramp_grade)
    assert grade == tn.ramp_grade
    # 5.1 m at 5 % is 102 m: met at the 108 m station, one station of slack
    assert (s_top, ss) == (want_top, want_ss) == (120.0, [SPACING * k for k in range(11)])
    at_cap, _ss = ramp_top(airport, law, axis, -5.1, 0.0, SPACING, grade=tn.ramp_max_grade)
    assert at_cap < s_top


def test_a_run_that_fits_only_at_7_3_percent_is_built_at_7_3_percent(law):
    """A stop at 72 m leaves the climb 60 m (one station of slack is the
    top's): 4.38 m over 60 m is 7.3 % — the LEAST grade that tops out,
    neither the 5 % design (it would run to 108 m) nor the 10 % cap."""
    airport, axis = _ground(lambda x: 0.0)
    grade, s_top, ss = unframed_top(airport, law, axis, -4.38, 0.0, SPACING, within=72.0)
    assert grade == pytest.approx(0.073)
    assert s_top == 72.0 and ss[-1] == 72.0
    assert grade < law.tables.structures.tunnel.ramp_max_grade


def test_a_run_that_needs_more_than_the_cap_is_refused(law):
    """48 m of climb for 5.4 m is 11.25 %: no grade up to the cap tops
    out — nothing is returned (the caller keeps the ramp it had, or
    refuses with its own reason)."""
    airport, axis = _ground(lambda x: 0.0)
    assert unframed_top(airport, law, axis, -5.4, 0.0, SPACING, within=60.0)[:2] == (None, None)


def test_ground_the_design_grade_never_meets_takes_the_least_steeper_grade(law):
    """Ground climbing at 8.5 % from 1 m over the mouth: the design grade
    never meets it in 600 m (the refusal of old); the least grade that does is
    ``0.085 + 1 / 600`` at the last station — under the cap, so the ramp
    is ADMITTED at that grade.  Ground climbing at 12 % is over the cap:
    refused, with the cap's own walk for the caller's line."""
    tn = law.tables.structures.tunnel
    airport, axis = _ground(lambda x: 0.085 * x)
    assert ramp_top(airport, law, axis, -1.0, 0.0, SPACING, grade=tn.ramp_grade)[0] is None
    grade, s_top, _ss = unframed_top(airport, law, axis, -1.0, 0.0, SPACING)
    assert tn.ramp_grade < grade == pytest.approx(0.085 + 1.0 / 600.0, abs=1e-6)
    assert s_top == pytest.approx(600.0 + SPACING)
    steep, axis2 = _ground(lambda x: 0.12 * x)
    grade2, s2, ss2 = unframed_top(steep, law, axis2, -1.0, 0.0, SPACING)
    assert (grade2, s2) == (None, None) and len(ss2) > 2


def test_a_mapped_bore_is_built_and_priced_at_the_design_grade(law, tmp_path_factory):
    """Through ``build_structures``: the synthetic mapped bore's ramp
    carries the design grade (it had the cap's), so the solve's descent
    rows (``constraints/structures``) price it there and its top stands
    where the design-grade climb meets the ground."""
    tn = law.tables.structures.tunnel
    pack = M4B.objs.__wrapped__(tmp_path_factory)
    airport = M4B._airport(pack, law, [], M4B._tunnel_ways()[:3])
    cells = [Cell(0, "runway", "09/27", M4B._rect(-600, 500, 600, 545), (), 3, "D", "airside",
                  "runway", {}),
             Cell(1, "apron", "apron1", M4B._rect(-80, -60, 80, 60), (), None, None, "airside",
                  "apron", {})]
    objects, _rep = read_objects(airport, law)
    _cl, tunnels, _st = build_structures(airport, Classification(tuple(cells), (), {}, ()), law,
                                         objects)
    bores = [t for t in tunnels if t.source == "osm"]
    assert bores
    for t in bores:
        assert t.design_grade == tn.ramp_grade < tn.ramp_max_grade
        assert not any("steepened" in n for n in t.notes)
        if not t.clipped_by:
            rise = abs(t.mouth_dem_z - t.mouth_z)
            # the climb (less the top's one station of slack) covers the rise at the design grade
            assert (t.top_s - t.climb_from_s) * tn.ramp_grade >= rise - 1e-6


def test_two_overlapping_unframed_ramps_the_longer_yields_its_run(law):
    """Another structure's corridor ends the run (08d (1)): of two mapped
    ramps whose design-grade corridors cross, the LONGER climb is given
    the station where it enters the other, less the gap; once that end
    could not be met (the ramp came back as long as before) the other
    yields; two ramps already at the cap leave the refusal as it was."""
    from shapely.geometry import box
    from auto_patch_v2.planar.unframed_ramp import overlap_run_end
    tn = law.tables.structures.tunnel
    gap = tn.wall_gap_m

    def ramp(tid, axis, top, grade=tn.ramp_grade):
        return types.SimpleNamespace(id=tid, source="osm", axis=axis, top_s=top,
                                     climb_from_s=0.0, design_grade=grade)
    a = ramp("tunnel:a@0", ((0.0, 0.0), (120.0, 0.0)), 120.0)
    b = ramp("tunnel:b@0", ((90.0, -50.0), (90.0, 50.0)), 100.0)
    fa, fb = box(0, -5, 120, 5), box(85, -50, 95, 50)
    tid, (end, why) = overlap_run_end((a, b), (fa, fb), {}, law, gap)
    assert tid == "tunnel:a@0" and end == pytest.approx(85.0 - gap) and "tunnel:b@0" in why
    # a's run end of the last pass was not met: b yields where it enters a
    tid2, (end2, _why) = overlap_run_end((a, b), (fa, fb), {"tunnel:a@0": (end, why)}, law, gap)
    assert tid2 == "tunnel:b@0" and end2 == pytest.approx(45.0 - gap)
    at_cap = [ramp(t.id, t.axis, t.top_s, tn.ramp_max_grade) for t in (a, b)]
    assert overlap_run_end(at_cap, (fa, fb), {}, law, gap) is None
    # a ramp an object frames never yields
    framed = types.SimpleNamespace(**{**vars(a), "source": "wall_corridor"})
    assert overlap_run_end((framed, at_cap[1]), (fa, fb), {}, law, gap) is None
