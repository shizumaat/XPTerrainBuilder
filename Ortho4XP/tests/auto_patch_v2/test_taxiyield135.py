"""30ah (1) TAXIWAYS YIELD WITH THEIR RUNWAY (owner RULINGS 2026-09-30ah
(1), answering Q-133 of 30ad; issue #135).

When §50 yields a runway's longitudinal cap to its pins, every taxi-family
face on a route that touches that runway is priced at
``max(taxi table cap, the runway's effective cap)`` — never above the 29ac
pavement fallback — derived ONCE (``runway_yield.derive_taxi``, published
on ``PlanarMap.taxi_caps``) and read through ONE reader
(``precedence.taxi_cap_for``) by the generators, v2 verify and the census.

The fixture is ``test_routes``' loop (a runway, a stub up, a parallel west,
a stub down into an apron) with the runway's thresholds set apart so the
cap yields, plus one ISOLATED stub whose centreline touches nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints.precedence import face_cap, taxi_cap_for
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.runway_yield import TaxiYield, derive_taxi
from auto_patch_v2.constraints.stretches import stretches
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pavement_fallback_cap, role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.publication import (TAXI_YIELD_CAP_TAG,
                                                TAXI_YIELD_REF_TAG, face_tags)
from auto_patch_v2.planar.build import build

from test_routes import _RampDem, _rect

ROOT = Path(__file__).resolve().parents[2]
TAXI = ("primary_parallel", "secondary_parallel", "stub", "cross_connector",
        "junction")


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _loop(law, drop_m: float):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0,
                      "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0 + drop_m, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(488.5, 22.5, 511.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-120, 190, 520, 213), (),
             None, "D", "airside", "taxi", {}),
        Cell(3, "stub", "stubW", _rect(-111.5, 140, -88.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(4, "apron", "apron1", _rect(-200, 40, 0, 140), (), None, None,
             "airside", "apron", {}),
        # touches NOTHING: no route reaches the runway from it
        Cell(5, "stub", "stubX", _rect(-411.5, 400, -388.5, 520), (), None,
             "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubE", ((500.0, 0.0), (500.0, 201.5))),
            CutLine("taxi_centerline", "taxiA", ((-100.0, 201.5), (500.0, 201.5))),
            CutLine("taxi_centerline", "stubW", ((-100.0, 100.0), (-100.0, 201.5))),
            CutLine("taxi_centerline", "stubX", ((-400.0, 400.0), (-400.0, 520.0))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, with_runway_chord(pm, law, airport)


def _faces(pm, ref):
    return [f for f in pm.faces.values() if f.ref == ref]


@pytest.fixture(scope="module")
def yielded(law):
    return _loop(law, 30.0)          # 2.5 % pin to pin against 1.5 %


def test_tied_taxi_faces_take_the_runway_cap_and_the_untied_do_not(yielded, law):
    airport, pm = yielded
    rc = pm.runway_caps["09/27"]
    assert rc.yielded and rc.cap > 0.025
    assert pm.taxi_caps, "no taxi face yielded beside a yielded runway"
    for ref in ("stubE", "taxiA", "stubW"):
        for f in _faces(pm, ref):
            ty = pm.taxi_caps.get(f.id)
            assert isinstance(ty, TaxiYield), ref
            assert ty.ref == "09/27" and ty.table == 0.015
            assert ty.cap == pytest.approx(rc.cap)
            lon, tr = face_cap(law, f, pm)
            assert lon == pytest.approx(rc.cap)
            # the yield is LONGITUDINAL: the transverse cap never moves
            assert tr == role_cap(law, f.role, f.code_number, f.code_letter).transverse
    for f in _faces(pm, "stubX"):
        assert f.id not in pm.taxi_caps
        assert face_cap(law, f, pm)[0] == 0.015
    # only the taxi family yields
    assert all(pm.faces[fid].role in TAXI for fid in pm.taxi_caps)


def test_the_stretches_carry_the_yield_through_the_one_reader(yielded, law):
    airport, pm = yielded
    cap = pm.runway_caps["09/27"].cap
    st = stretches(pm, law)
    by_ref = {}
    for s in st.items:
        by_ref.setdefault(s.ref, set()).add(round(s.cap_l, 9))
    assert by_ref["taxiA"] == {round(cap, 9)}
    assert by_ref["stubX"] == {0.015}


def test_a_runway_that_fits_its_pins_yields_no_taxiway(law):
    airport, pm = _loop(law, 0.0)
    assert not pm.runway_caps["09/27"].yielded
    assert dict(pm.taxi_caps) == {}
    assert derive_taxi(pm, law, airport, pm.runway_caps) == {}


def test_nothing_exceeds_the_pavement_fallback(law):
    airport, pm = _loop(law, 150.0)  # 12.5 % pin to pin
    ceiling = pavement_fallback_cap(law)
    assert pm.runway_caps["09/27"].cap > ceiling
    assert pm.taxi_caps
    assert all(ty.cap == pytest.approx(ceiling) for ty in pm.taxi_caps.values())


def test_the_reader_is_max_of_table_and_yield():
    assert taxi_cap_for(0.015, None) == 0.015
    assert taxi_cap_for(0.015, 0.0202) == 0.0202
    assert taxi_cap_for(0.03, 0.0202) == 0.03


def test_published_record_tags_and_census_price_through_the_reader(yielded, law):
    airport, pm = yielded
    tags = face_tags(pm, law, airport)
    for fid, ty in pm.taxi_caps.items():
        assert float(tags[fid][TAXI_YIELD_CAP_TAG]) == pytest.approx(ty.cap)
        assert tags[fid][TAXI_YIELD_REF_TAG] == "09/27"
    for f in _faces(pm, "stubX"):
        assert TAXI_YIELD_CAP_TAG not in tags.get(f.id, {})

    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    assert cg.TAXI_YIELD_CAP_TAG == TAXI_YIELD_CAP_TAG

    class _W:
        def __init__(self, t):
            self.tags = t

    class _C:
        def __init__(self, cap, t, transverse=False):
            self.cap, self.way, self.transverse_road = cap, _W(t), transverse

    tag = {TAXI_YIELD_CAP_TAG: "0.0202"}
    assert cg._taxi_yield_pair_cap(_C(0.015, tag), 0.015) == 0.0202
    # a pair the law TIGHTENED (a pad endpoint) keeps its stricter law
    assert cg._taxi_yield_pair_cap(_C(0.005, tag), 0.015) is None
    assert cg._taxi_yield_pair_cap(_C(0.015, tag, True), 0.015) is None
    assert cg._taxi_yield_pair_cap(_C(0.015, {}), 0.015) is None
