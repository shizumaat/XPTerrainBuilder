"""Issue #684, owner Q366 "A" (2026-11-03): a road along a lot that CLIMBS to
a raised pad or structure stays road and keeps its climb; the rest of the
road along the lot joins the lot (``airport/lot_road_climb``)."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.airport.lot_road_climb import with_lot_road_climbs
from auto_patch_v2.airport.road_profile import preferred_road_z
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import is_late_ref, is_osm_ribbon_ref
from auto_patch_v2.planar.build import build
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
from tests.auto_patch_v2.test_v2roadramp import ROAD_W, RUN_LEN, _airport, _Hill, _Shelf


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells(r):
    """The runway, an apron, a road leaving its edge (route distance s from
    the mouth) with its stretch s = 40..100 along a lot cut as a lot strip."""
    lo, hi = 200.0 - ROAD_W / 2.0, 200.0 + ROAD_W / 2.0

    def cell(i, role, ref, rect, side, ev=None):
        return Cell(i, role, ref, _rect(r, *rect), (), None, "D", side, role, ev or {})
    return (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        cell(1, "apron", "apronA", (-220.0, 150.0, -20.0, 250.0), "airside"),
        cell(2, "service_road", "small_roads:-3", (-20.0, lo, 20.0, hi), "groundside",
             {"osm_ribbon": 1.0}),
        cell(3, "parking_lot", "lot0#road0", (20.0, lo, 80.0, hi), "groundside",
             {"lot_road": 1.0, "lot_of": "lot0", "lot_road_way": "small_roads:-3"}),
        cell(4, "service_road", "small_roads:-3#1", (80.0, lo, 280.0, hi), "groundside",
             {"osm_ribbon": 1.0}),
        cell(5, "parking_lot", "lot0", (20.0, hi, 80.0, hi + 12.0), "groundside"),
    )


def _read(law, dem):
    airport, r = _airport(law, dem)
    pm, _st = build(airport, Classification(_cells(r), (), {}, ()), law)
    pref, _rep, _p = preferred_road_z(airport, pm, law)
    pm = _dc.replace(pm, preferred_z=pref)
    rep: dict = {}
    out = with_lot_road_climbs(pm, law, airport, rep, service=load_rules().service)
    return pm, out, rep


def test_a_strip_on_the_climb_to_a_raised_apron_is_road_again(law):
    """The apron stands on 12 m of fill: the road leaves it on its §37 (6)
    ramp, and the strip along the lot lies on that climb — it is the road's
    again (a ribbon ref, still a late cell), the lot itself untouched."""
    pm, out, rep = _read(law, _Shelf())
    assert pm.lot_road_ways == {"lot0#road0": "small_roads:-3"}
    assert rep["lot_strips"] == rep["lot_strips_on_climb"] >= 1, rep
    back = [f for f in out.faces.values() if f.ref.startswith("small_roads:-3#lot")]
    assert back and all(f.role == "service_road" for f in back)
    assert is_osm_ribbon_ref(back[0].ref) and is_late_ref(back[0].ref)
    assert not any(f.ref == "lot0#road0" for f in out.faces.values())
    assert [f.role for f in out.faces.values() if f.ref == "lot0"] == \
        [f.role for f in pm.faces.values() if f.ref == "lot0"]
    assert out.lot_road_ways == {}


def test_a_strip_where_the_road_is_on_its_ground_stays_the_lot(law):
    """The same road off an apron on its own ground: no climb, the strip is
    the lot and the map is the one it was."""
    pm, out, rep = _read(law, _Hill())
    assert rep["lot_strips"] >= 1 and rep["lot_strips_on_climb"] == 0, rep
    assert out is pm
