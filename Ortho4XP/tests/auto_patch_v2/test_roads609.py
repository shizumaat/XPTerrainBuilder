"""Issue #609, owner RULINGS 2026-10-13a (1)/(3): THE ROAD YIELDS TO THE PAD.

A mapped-road ribbon welded to a building pad keeps no absolute road row
off the rim (its §37 (6) target and ceiling leave, its §37 (9) join pin is
released so the core ribbon yields), and carries ONE design row relative
to its nearest rim vertex; the ribbon pass of the touch witness never
holds a road off a pad as a hillside terrace.  The fixtures are
``test_pad_touch``'s (one pad, one road along its south edge)."""
from __future__ import annotations

import dataclasses as dc

import pytest

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.pad_touch import HELD_KEY, WELD_KEY
from auto_patch_v2.classify.roles import Cell, Classification, _cut_back_groundside
from auto_patch_v2.law import Law
from auto_patch_v2.planar import build

from tests.auto_patch_v2.test_pad_touch import _Dem, _airport, _rect


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ribbon_cells(y0: float = 92.0, y1: float = 100.0):
    """``test_pad_touch._road_cells`` with the road carrying a MAPPED-ROAD
    ribbon ref (``small_roads:-1``), along the pad's south edge by default
    (``y0, y1`` = 200, 208 puts it along the north edge, on the hillside)."""
    return [Cell(9, "runway", "09/27", _rect(-800.0, -422.5, 800.0, -377.5), (),
                 3, "D", "airside", "runway", {}),
            Cell(0, "building", "padA", _rect(100.0, 100.0, 200.0, 200.0), (),
                 None, None, "airside", "pad", {}),
            Cell(1, "service_road", "small_roads:-1", _rect(0.0, y0, 300.0, y1), (),
                 None, None, "groundside", "service_road", {"osm_ribbon": 1.0})]


def test_the_ribbon_pass_never_holds_a_road_off_a_pad(law):
    """13a (3) "Ramp it": across a 5 m hillside step the first pass HOLDS a
    lot (the §28 (6) knife); the ribbon pass (``hold=False``) welds."""
    airport = _airport(law, _Dem(north=5.0))
    held, n_held = _cut_back_groundside(_ribbon_cells(200.0, 208.0), law, load_rules(), airport)
    road = [c for c in held if c.role == "service_road"]
    assert n_held == 1 and any(c.evidence.get(HELD_KEY) for c in road)
    welded, n_cut = _cut_back_groundside(_ribbon_cells(200.0, 208.0), law, load_rules(),
                                         airport, only=[2], hold=False)
    road = [c for c in welded if c.role == "service_road"]
    assert n_cut == 0 and all(not c.evidence.get(HELD_KEY) for c in road)
    assert any(c.evidence.get(WELD_KEY) for c in road)


def test_a_welded_ribbon_keeps_no_absolute_road_row_off_the_rim(law):
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.constraints.road_ramp import (JOIN_RULING, PAD_RAMP_RULING,
                                                     RULING, RULING_CEILING,
                                                     pad_ramp_rewrite,
                                                     pad_weld_release,
                                                     road_join_rows,
                                                     road_ramp_rows)
    from auto_patch_v2.model.constraints import ConstraintSet
    airport = _airport(law, _Dem())
    cells, _n = _cut_back_groundside(_ribbon_cells(), law, load_rules(), airport,
                                     only=[2], hold=False)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    rim = pad_welded_vertices(pm, law)
    road = {v for f in pm.faces.values() if f.ref == "small_roads:-1"
            for v in pm.ring_vertices(f.ring)}
    assert rim and rim < road
    off = sorted(road - rim)
    pm = dc.replace(pm, road_ramp_z={v: 700.0 for v in road},
                    road_coverage_join={off[0]: 702.0})
    cs = ConstraintSet.from_rows(road_ramp_rows(pm, law, airport)
                                 + road_join_rows(pm, law, airport))
    cs, _rep = pad_weld_release(pm, law, cs)
    out, rep = pad_ramp_rewrite(pm, law, cs)
    assert rep["ribbon_vertices"] == len(off)
    assert rep["targets"] == rep["ceilings"] == len(off)
    assert [j["v"] for j in rep["joins"]] == [off[0]] and rep["joins"][0]["stage"] == "2p"
    assert not out.pins
    assert not any(r.source.ruling == RULING_CEILING for r in out.bands)
    assert not any(r.source.ruling == RULING for r in out.linears)
    # the released join leaves no row behind: the core yields to the patch
    assert not any(r.source.ruling == JOIN_RULING for r in out.linears)
    rel = [r for r in out.linears if r.source.ruling == PAD_RAMP_RULING]
    assert rep["rows"] == len(rel) == len(off)
    g = float(law.tables.emit.road_contact.ramp_grade)
    for r in rel:
        (v, cv), (q, cq) = r.terms
        assert cv == 1.0 and cq == -1.0 and q in rim and v in off
        d = ((pm.vertices[v].xy[0] - pm.vertices[q].xy[0]) ** 2
             + (pm.vertices[v].xy[1] - pm.vertices[q].xy[1]) ** 2) ** 0.5
        assert r.lo == r.hi and abs(r.lo) <= g * d + 1e-9     # flat DEM: 0, never past g·d
