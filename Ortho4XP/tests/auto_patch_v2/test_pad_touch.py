"""Spec §63 twins (owner RULINGS 2026-10-09j: a groundside cell TOUCHING a
pad in the source geometry is welded to it; a GAPPED one is free).  Rule T
— the touch witness at the one site, ``classify/roles._cut_back_groundside``
— on a pad with four lots drawn round it: one OVERLAPPING it, one 0.3 m off
(a gap the identity grid cannot hold), one 0.8 m off and one 2 m off.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.pad_touch import (EVIDENCE_KEY, is_touching,
                                              touch_records)
from auto_patch_v2.classify.roles import Cell, _cut_back_groundside
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.publication import pad_touch


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _lot(i, ref, ring):
    return Cell(i, "parking_lot", ref, ring, (), None, None, "groundside",
                "parking_lot", {})


def _cells():
    """The pad is 100..200 x 100..200; every coordinate is on the 0.5 m
    identity grid except the stand-offs under test."""
    return [Cell(0, "building", "padA", _rect(100.0, 100.0, 200.0, 200.0), (),
                 None, None, "airside", "pad", {}),
            _lot(1, "over", _rect(150.0, 190.0, 180.0, 260.0)),      # overlaps 10 m
            _lot(2, "hair", _rect(200.3, 110.0, 260.0, 150.0)),      # 0.3 m off
            _lot(3, "gap08", _rect(40.0, 110.0, 99.2, 150.0)),       # 0.8 m off
            _lot(4, "gap2", _rect(110.0, 40.0, 150.0, 98.0)),        # 2 m off
            _lot(5, "far", _rect(110.0, 0.0, 150.0, 30.0))]          # 70 m off


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def cut(law):
    cells, _n = _cut_back_groundside(_cells(), law, load_rules())
    return cells


def _witness(cells, ref):
    got = [c.evidence.get(EVIDENCE_KEY) for c in cells
           if c.ref.split("#")[0] == ref]
    assert got, ref
    return got[0]


def test_an_overlapping_cell_reads_touching(cut, law):
    w = _witness(cut, "over")
    assert w == {"padA": 0.0} and is_touching(law, w["padA"])


def test_a_gap_the_identity_grid_cannot_hold_reads_touching(cut, law):
    """0.3 m off the pad as drawn; on the 0.5 m identity grid the lot's
    edge lands on the pad's or one cell off it — either way no gap that
    can stand in the planar map (RULINGS 2026-09-04u)."""
    w = _witness(cut, "hair")
    assert set(w) == {"padA"} and is_touching(law, w["padA"])


def test_a_real_gap_reads_gapped_with_its_distance(cut, law):
    """0.8 m as drawn reads on the grid as 1.0 m (99.2 -> 99.0): gapped,
    and the gap is the published number."""
    w = _witness(cut, "gap08")
    assert not is_touching(law, w["padA"])
    assert w["padA"] == pytest.approx(0.8, abs=law.tables.emit.identity.min_distinct_spacing_m / 2 + 1e-9)
    assert _witness(cut, "gap2") == {"padA": 2.0}


def test_a_cell_beyond_the_frontage_radius_has_no_relation(cut):
    assert _witness(cut, "far") is None


def test_the_sidecar_names_every_neighbour_of_a_pad_by_class(cut, law):
    recs = pad_touch(cut, law)
    assert recs == touch_records(cut, law)
    (rec,) = recs
    assert rec["pad"] == "padA"
    assert {n.split("#")[0] for n in rec["touching"]} == {"parking_lot:over",
                                                          "parking_lot:hair"}
    assert [g["cell"].split("#")[0] for g in rec["gapped"]] == [
        "parking_lot:gap08", "parking_lot:gap2"]
    assert [g["gap_m"] for g in rec["gapped"]][1] == 2.0
