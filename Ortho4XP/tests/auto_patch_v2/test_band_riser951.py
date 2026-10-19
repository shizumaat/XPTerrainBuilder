"""Owner RULINGS 2026-10-19a / 19i / 19k / 19l (#951, #949): a road inside a
runway's safety-area band, BELOW the band's grade, follows its own ground
and meets the band at a retaining wall — the band's RISER, one weld spacing
wide (``planar/band_riser``), across which the design energy is cut
(``solve/wall_cut.riser_cut_edges``) and the pair rows released
(``constraints/band_riser``); the wall is declared
(``pipeline/band_road_wall``).

Synthetic: the #715 twin's runway 09/27 along y = 0 on ground at 100 m and
a tertiary road along y = -30 inside its strip on ground at 92 m — with NO
pack wall."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.law import Law
from test_roadmint100 import _way, _with
from test_roadterrace100 import _solve
from test_wall_step715 import ROAD, _road, _StepDem


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


@pytest.fixture(scope="module")
def arm(law):
    a = _dc.replace(_with(_way(-3, ROAD, highway="tertiary")), dem=_StepDem())
    return _solve(a, law)


def test_the_band_yields_a_riser_one_weld_spacing_wide(arm, law):
    from auto_patch_v2.model.planar import band_risers
    pm, _sol, _rep = arm
    rs = band_risers(pm)
    assert rs, "no riser beside the road in the strip"
    w = law.tables.emit.identity.weld_spacing_m
    road = _road(pm)
    for _fid, lower, upper in rs:
        assert lower and upper and lower & road
        # the band line stands one weld spacing off the kerbs (y -26 / -34)
        for v in upper:
            y = pm.vertices[v].xy[1]
            assert min(abs(y + 26.0), abs(y + 34.0)) == pytest.approx(w, abs=0.05)


def test_the_road_keeps_its_ground_and_the_riser_is_the_wall(arm, law):
    from auto_patch_v2.model.planar import band_risers
    from auto_patch_v2.pipeline.band_road_wall import LABEL, band_road_wall_joints
    pm, sol, _rep = arm
    road = _road(pm)
    assert max(abs(sol.z[v] - 92.0) for v in road) <= 0.5
    w = law.tables.emit.identity.weld_spacing_m
    for _fid, lower, upper in band_risers(pm):
        # the band side stands metres above the kerb across one weld spacing
        assert min(sol.z[v] for v in upper) - max(sol.z[v] for v in lower) > 5.0 * w
    js = band_road_wall_joints(pm, law, sol.z)
    assert js and all(j["kind"] == "wall_terrace" and j["shapes"] == [LABEL]
                      for j in js)
    assert all(j["step_m"] > 5.0 for j in js)


def test_the_bending_is_cut_across_the_riser(arm):
    """``solve/wall_cut.riser_cut_edges``: every cut edge joins a ribbon
    vertex to a band vertex; none joins two ribbon vertices (the road keeps
    its own bending)."""
    from auto_patch_v2.model.planar import band_risers
    from auto_patch_v2.solve.rows import _face_triangles
    from auto_patch_v2.solve.wall_cut import riser_cut_edges
    pm, _sol, _rep = arm
    tris = [t for f in pm.faces for t in _face_triangles(pm, f)]
    cut = riser_cut_edges(pm, tris)
    assert cut
    lower = set().union(*(lo for _f, lo, _u in band_risers(pm)))
    upper = set().union(*(up for _f, _l, up in band_risers(pm)))
    assert all((a in lower) != (b in lower) for a, b in cut)
    assert any(a in upper or b in upper for a, b in cut)
