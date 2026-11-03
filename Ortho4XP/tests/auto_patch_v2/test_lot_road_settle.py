"""Issue #684: a LOT CANDIDATE (a mapped road's stretch along a lot,
``classify/lot_roads``) is settled ONCE inside ``road_ramp.with_road_ramp``
(``airport/lot_road_settle``): on its road's climb to a raised pad it stays
road (owner Q366 "A"), elsewhere it becomes its lot, its ramp target, route
frame and road-profile fit withdrawn."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.airport.road_profile import preferred_road_z
from auto_patch_v2.airport.road_ramp import with_road_ramp
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import is_late_ref, is_lot_road_ref, is_osm_ribbon_ref
from auto_patch_v2.planar.build import build
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
from tests.auto_patch_v2.test_v2roadramp import (
    PLATEAU_Z,
    ROAD_W,
    RUN_LEN,
    _airport,
    _Hill,
    _Shelf,
)

CAND = "small_roads:-3#2"


class _Plain(_Hill):
    """The apron on its plain: the road leaves its contact on its ground."""

    def z(self, x, y):
        return PLATEAU_Z


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells(r):
    """The runway, an apron, a road leaving its edge (route distance s from
    the mouth) with its stretch s = 40..100 along a lot split off as a lot
    candidate."""
    lo, hi = 200.0 - ROAD_W / 2.0, 200.0 + ROAD_W / 2.0

    def cell(i, role, ref, rect, side, ev=None):
        return Cell(i, role, ref, _rect(r, *rect), (), None, "D", side, role, ev or {})
    road = {"osm_ribbon": 1.0}
    return (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        cell(1, "apron", "apronA", (-220.0, 150.0, -20.0, 250.0), "airside"),
        cell(2, "service_road", "small_roads:-3", (-20.0, lo, 20.0, hi), "groundside", road),
        cell(3, "service_road", CAND, (20.0, lo, 80.0, hi), "groundside",
             {**road, "lot_candidate": "lot0"}),
        cell(4, "service_road", "small_roads:-3#1", (80.0, lo, 280.0, hi), "groundside", road),
        cell(5, "parking_lot", "lot0", (20.0, hi, 80.0, hi + 12.0), "groundside"),
    )


def _read(law, dem):
    airport, r = _airport(law, dem)
    pm, _st = build(airport, Classification(_cells(r), (), {}, ()), law)
    pref, _rep, _p = preferred_road_z(airport, pm, law)
    pm = _dc.replace(pm, preferred_z=pref)
    rep: dict = {}
    return pm, with_road_ramp(pm, law, airport, rep, service=load_rules().service), rep


def _only(pm, ref):
    """The vertices of the faces of ``ref`` that no other face carries."""
    fids = {fid for fid, f in pm.faces.items() if f.ref == ref}
    vs = {v for fid in fids for ring in (pm.faces[fid].ring, *pm.faces[fid].holes)
          for v in pm.ring_vertices(ring)}
    return {v for v in vs if set(pm.vertices[v].incident_faces) <= fids}


def test_a_candidate_on_the_climb_to_a_raised_apron_stays_road(law):
    """The apron stands on 12 m of fill: the road leaves it on its §37 (6)
    ramp, and the candidate lies on that climb — it stays the road (a
    ribbon ref, a late cell), the lot untouched."""
    pm, out, rep = _read(law, _Shelf())
    assert pm.lot_candidates == {CAND: "lot0"}
    assert rep["lot_candidates"] >= 1 and rep["lot_kept_road"] == rep["lot_candidates"], rep
    back = [f for f in out.faces.values() if f.ref == CAND]
    assert back and all(f.role == "service_road" for f in back)
    assert is_osm_ribbon_ref(CAND) and is_late_ref(CAND)
    assert [f.role for f in out.faces.values() if f.ref == "lot0"] == ["parking_lot"]
    assert out.lot_candidates == {CAND: "lot0"}


def test_a_candidate_where_the_road_is_on_its_ground_settles_as_the_lot(law):
    """The same road off an apron on its plain: no climb, the candidate
    is the lot — its role and a ref of the lot's own — and every vertex it
    alone carried leaves the ramp, the route frame and the road fit."""
    pm, out, rep = _read(law, _Plain())
    assert rep["lot_settled"] == rep["lot_candidates"] >= 1 and not rep["lot_kept_road"], rep
    settled = [f for f in out.faces.values() if is_lot_road_ref(f.ref)]
    assert settled and {(f.role, f.ref) for f in settled} == {("parking_lot", "lot0#road0")}
    assert not any(f.ref == CAND for f in out.faces.values()) and out.lot_candidates == {}
    alone = _only(pm, CAND)
    assert alone & set(pm.preferred_z)                      # it had the road's fit
    assert not alone & set(out.road_ramp_z) and not alone & set(out.road_route_frame)
    assert not alone & set(out.preferred_z)


def test_the_wall_flag_is_law(law):
    """Q-wall: one named boolean in the law tables, default the master's
    recommendation (a candidate on a declared wall terrace stays road)."""
    assert law.tables.emit.road_contact.lot_road_wall_keeps is True
