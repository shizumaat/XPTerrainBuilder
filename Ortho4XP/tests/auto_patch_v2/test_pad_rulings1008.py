"""THE MASTER'S PROVISIONAL RULINGS OF 2026-10-08 ON SPEC §56 (R3: "landings
keep their collar machinery") — one twin per ruled reader, each landing
with its own commit so it can be reverted alone (pending spec-author
review; lane pads59, issue #452)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.airport import anchor_rule as _ar

SQ = ((30.0, 31.0), (30.0, 31.001), (30.001, 31.001), (30.001, 31.0))
IN = ((30.0002, 31.0002), (30.0002, 31.0008), (30.0008, 31.0008), (30.0008, 31.0002))


def _doc(flat_ref: str, bank_ref: str) -> dict:
    """A graded document: a flat face (``IN``, z 100) and the bank face
    around it (outer ring ``SQ``, z 97)."""
    vs = [[i, la, lo, 100.0] for i, (la, lo) in enumerate(IN)]
    vs += [[10 + i, la, lo, 97.0] for i, (la, lo) in enumerate(SQ)]
    return {"vertices": vs, "breaklines": [],
            "faces": [{"ref": flat_ref, "role": "building", "ring": [0, 1, 2, 3]},
                      {"ref": bank_ref, "role": "building", "ring": [10, 11, 12, 13]}]}


@pytest.mark.parametrize("flat,bank", [("u/landing0", "u/landing0#collar"),
                                       ("u/b0", "u/b0#strip")])
def test_r3_4_the_object_stage_folds_a_bank_under_its_flat_face(flat, bank):
    """R3 (4): the fold is NARROWED, not deleted — a BANK face (a landing's
    ``#collar``, a block's ``#strip``) is published under its flat face's
    ref with its OUTER ring and that face's plane heights, so containment
    is the whole footprint and every min / median is the plane's."""
    from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
    pads, _rims = pads_rims_from_graded_doc(_doc(flat, bank))
    assert [p.ref for p in pads] == [flat, flat]
    folded = _ar.fold_pad_ref(pads, flat)
    assert min(folded.z) == pytest.approx(100.0, abs=1e-6)
    assert _ar.pad_contains(folded, 30.00005, 31.00005)      # on the bank


def test_r3_3_a_blocks_polygons_are_every_ring_of_the_block():
    """R3 (3): with no unit collar the block face's ring IS the block's
    largest published ring — ``pad_block_seat`` keeps it (it used to drop
    the largest as "the collar's outer ring")."""
    from auto_patch_v2.airport.pad_block_seat import _platform_polys
    strip = ((30.0, 31.001), (30.0, 31.0011), (30.001, 31.0011), (30.001, 31.001))
    one = _platform_polys([_ar.PadRing("u/b0", SQ, (1.0,) * 4)])
    assert len(one[("u", 0)]) == 1 and one[("u", 0)][0].area > 1000.0
    two = _platform_polys([_ar.PadRing("u/b0", SQ, (1.0,) * 4),
                           _ar.PadRing("u/b0", strip, (1.0,) * 4)])
    assert sorted(round(g.area / one[("u", 0)][0].area, 2) for g in two[("u", 0)]) == [0.1, 1.0]


def test_r3_6_the_rim_relief_census_skips_a_record_with_no_rim_relief():
    """R3 (6): ``platform_rim_relief`` reads a record that CARRIES a bank's
    relief (a landing's welded bank) and skips one that does not (a unit
    pad has no collar); the families stay registered."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import check_grade as CG
    assert "platform_rim_relief" in dict((k, d) for k, d, _p in CG.LAW_FAMILIES)
    assert CG.SIDECAR_LAW_KEYS["platforms"] == "platforms_ll"
    recs = [{"ref": "u/landing0", "collar_m": 5.0, "level": 100.0,
             "rim_relief_max_m": 1.2, "worst_ll": [60.5, -135.5], "worst_z": 101.2},
            {"ref": "padU", "level": 100.0, "datum": 100.0, "released": 0},
            {"ref": "fac", "refused": "draped_facade", "pad_m2": 960.0}]
    rr = CG._check_platform_rim_relief(recs)
    assert [r.way_a.ref for r in rr] == ["platform_rim_relief:u/landing0"]
    assert rr[0].de_m == pytest.approx(1.2) and math.isfinite(rr[0].elev_b)
    assert len(CG._check_platform_refused(recs)) == 1
    for ref in ("padU#collar", "u/b0#strip"):
        assert CG._is_platform_collar(CG.Way("x", "building", ref, "", [], [],
                                             {"role": "building"}))
