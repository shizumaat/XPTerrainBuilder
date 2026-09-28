"""Issue #81 (lane ``farfield``): a pad-outline change 2 km away must not
reach the airside stage-1 problem.

Measured on the KCLT courtyards capture (rule-2a arm against the
bridge-off arm, one variable): the runway moved at 755 of 1,616 nodes (max
0.42 m) and apron ``dsf:pol54`` 1.64 m.  THE FACE CLAIM carried it: a
polygonised face goes to the region with the largest overlap; a 59 m2 face
overlapped a parking lot and an apron by EXACTLY the same area, and the
strict ``>`` kept whichever the STRtree query returned first -- the tree's
packing, a function of every region at the airport.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.law import Law
from auto_patch_v2.planar.overlay import Region, _claiming_region


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _region(role, ref, poly):
    return Region(role, ref, poly, None, None, "airside", "cell")


# ── THE FACE CLAIM ───────────────────────────────────────────────────

def _kclt_tie():
    """The KCLT shape: a parking lot drawn OVER an apron, and a face whose
    overlap with each is the same area (the lot square lies inside both)."""
    apron = _region("apron", "dsf:pol10", box(0.0, 0.0, 100.0, 100.0))
    lot = _region("parking_lot", "dsf:pol52", box(10.0, 10.0, 17.0, 17.0))
    face = box(10.0, 10.0, 17.0, 17.0)
    return face, [apron, lot]


def test_a_tied_face_goes_to_the_senior_role_whatever_the_query_order(law):
    face, regions = _kclt_tie()
    for hits in ([0, 1], [1, 0]):
        r, a = _claiming_region(face, regions, hits, law)
        assert r.ref == "dsf:pol10" and r.role == "apron"
        assert a == pytest.approx(49.0)


def test_control_the_old_strict_first_wins_rule_flips_with_the_order(law):
    """The pre-#81 loop, verbatim in effect: the SAME face and regions give
    a different owner under the two query orders — the defect."""
    face, regions = _kclt_tie()

    def old(hits):
        best, best_a = None, 0.0
        for j in hits:
            a = face.intersection(regions[j].polygon).area
            if a > best_a:
                best, best_a = regions[j], a
        return best.role

    assert old([0, 1]) != old([1, 0])


def test_a_larger_overlap_still_wins_over_seniority(law):
    """The tie-break is a TIE-break: the largest overlap still decides."""
    apron = _region("apron", "a", box(0.0, 0.0, 5.0, 10.0))
    lot = _region("parking_lot", "p", box(5.0, 0.0, 10.0, 10.0))
    face = box(3.0, 0.0, 10.0, 10.0)             # 20 m2 apron, 50 m2 lot
    r, a = _claiming_region(face, [apron, lot], [0, 1], law)
    assert r.role == "parking_lot" and a == pytest.approx(50.0)


def test_equal_roles_tie_to_the_smaller_region_then_the_ref(law):
    big = _region("apron", "b", box(0.0, 0.0, 100.0, 100.0))
    small = _region("apron", "a", Polygon([(0, 0), (20, 0), (20, 20), (0, 20)]))
    face = box(0.0, 0.0, 10.0, 10.0)
    for hits in ([0, 1], [1, 0]):
        assert _claiming_region(face, [big, small], hits, law)[0].ref == "a"


def test_no_overlap_claims_nothing(law):
    apron = _region("apron", "a", box(0.0, 0.0, 1.0, 1.0))
    assert _claiming_region(box(5, 5, 6, 6), [apron], [0], law) == (None, 0.0)
