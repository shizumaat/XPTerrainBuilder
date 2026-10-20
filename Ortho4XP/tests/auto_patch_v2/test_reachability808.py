"""PAVEMENT AIRCRAFT CANNOT REACH IS GROUNDSIDE (owner RULINGS 2026-10-19ag,
issue #808, ``classify/reachability``).

The KCLT shape, in the abstract: a taxiway, an apron along it, and a long
building standing on the apron's far edge; pavement wraps the building's
ends and far side and joins the apron only through gaps narrower than the
serving taxiway.  That pavement is groundside; the apron stays apron.  A
small hangar with taxiable apron all round divides nothing.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.reachability import unreachable_aprons
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from shapely.geometry import box

TAXI = box(0.0, 0.0, 400.0, 25.0)                 # a letter-F taxiway
APRON = box(0.0, 25.0, 400.0, 125.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _final(*faces):
    return [["primary_parallel", "twy", TAXI, "F", {}, "taxi"],
            ["apron", "apronA", APRON, None, {}, "apron"],
            *[["apron", ref, g, None, {}, "apron"] for ref, g in faces]]


def test_pavement_behind_a_building_through_narrow_gaps_is_groundside(law):
    # the building stands on the apron's far edge, x 100..300, y 125..155;
    # the lot wraps it from x 90..310 out to y 205, joined to the apron only
    # by the two 10 m gaps at its ends (x 90..100 and 300..310)
    lot = box(90.0, 125.0, 310.0, 205.0).difference(box(100.0, 125.0, 300.0, 155.0))
    final = _final(("lotB", lot))
    rep = unreachable_aprons(final, [], law, load_rules())
    roles = {f[1]: f[0] for f in final}
    assert roles["apronA"] == "apron"
    assert role_side(law, roles["lotB"]) == "groundside"
    assert rep["reach_demoted"] == 1


def test_a_hangar_with_apron_all_round_divides_nothing(law):
    # a 40 x 30 m hangar in a 200 x 120 m apron pocket: 30 m and more of
    # pavement on every side
    pocket = box(100.0, 125.0, 300.0, 245.0).difference(box(180.0, 170.0, 220.0, 200.0))
    final = _final(("pocket", pocket))
    rep = unreachable_aprons(final, [], law, load_rules())
    assert {f[1]: f[0] for f in final}["pocket"] == "apron"
    assert rep["reach_demoted"] == 0


def test_a_stand_beyond_the_gap_keeps_the_apron(law):
    lot = box(90.0, 125.0, 310.0, 205.0).difference(box(100.0, 125.0, 300.0, 155.0))
    final = _final(("lotB", lot))
    unreachable_aprons(final, [], law, load_rules(), [(200.0, 180.0)])
    assert {f[1]: f[0] for f in final}["lotB"] == "apron"
