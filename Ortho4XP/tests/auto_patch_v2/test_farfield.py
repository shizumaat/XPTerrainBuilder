"""Issue #81 (lane ``farfield``): a pad-outline change 2 km away must not
reach the airside stage-1 problem.

Measured on the KCLT courtyards capture (rule-2a arm against the
bridge-off arm, one variable): the runway moved at 755 of 1,616 nodes (max
0.42 m) and apron ``dsf:pol54`` 1.64 m.  Two channels were attributed and
closed here, each with its pre-fix control:

* THE FACE CLAIM.  A polygonised face goes to the region with the largest
  overlap; a 59 m2 face overlapped a parking lot and an apron by EXACTLY the
  same area, and the strict ``>`` kept whichever the STRtree query returned
  first — the tree's packing, a function of every region at the airport.
* THE CEILING TWIN OF A PAD ROW.  ``pavement_ceiling`` twinned the pad's
  FLAT rows at 5 %; over two airside rim vertices such a twin is an
  all-airside HARD row, so stage 1 read the cluster's pair set.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.constraints.ceiling import pavement_ceiling  # noqa: E402
from auto_patch_v2.constraints.pads import FLAT_RULING  # noqa: E402
from auto_patch_v2.constraints.pads import GEN as PAD_GEN  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.constraints import Diff, Source  # noqa: E402
from auto_patch_v2.planar.overlay import Region, _claiming_region  # noqa: E402
from test_v2capyield import _one_runway  # noqa: E402


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


# ── THE CEILING TWIN OF A PAD ROW ────────────────────────────────────

def _pavement_pair(law):
    airport, pm = _one_runway(law)
    edge = [v for v in pm.vertices if abs(abs(pm.vertices[v].xy[1]) - 15.0) < 0.01]
    a, b = sorted(edge, key=lambda v: pm.vertices[v].xy[0])[:2]
    d = math.dist(pm.vertices[a].xy, pm.vertices[b].xy)
    assert 0.0 < d <= float(law.tables.emit.within_shape.withdrawn_chord_min_m)
    return pm, a, b, d


def test_a_pad_flat_row_mints_no_pavement_ceiling_twin(law):
    pm, a, b, d = _pavement_pair(law)
    src = Source(PAD_GEN, FLAT_RULING + " (2026-09-09c)", ("pad:x",))
    assert pavement_ceiling([Diff(a, b, 0.0, d, src)], pm, law) == []


def test_control_the_same_pair_from_an_airside_row_is_still_twinned(law):
    """The control: the pass itself still works — an airside family's row
    over the same two vertices mints its 5 % twin."""
    pm, a, b, d = _pavement_pair(law)
    src = Source("apron", "common.roles.apron preferred tier", ())
    twins = pavement_ceiling([Diff(a, b, 0.015, d, src)], pm, law)
    assert len(twins) == 1
    assert twins[0].cap == pytest.approx(float(law.tables.common.pavement_max_grade))
