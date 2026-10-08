"""Spec §56 (3) / owner RULINGS 2026-10-07c (6): THE FRONTAGE WARNING — the
fixed copy, byte for byte (the owner reads it), the bar, and the record's
carry across the build's maps."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.constraints.pad_warning import (  # noqa: E402
    frontage_warning, missing_slots, stamp_warning, warnings_of)
from auto_patch_v2.model import platform as mp  # noqa: E402

MARGIN = 0.3


def _rec(**kw):
    rec = {"ref": "building7", "centroid_ll": [30.1222, 31.40732], "pad_m2": 12345.6,
           "datum": 82.464, "released": 3, "welded": 13, "released_max_m": 0.45,
           "released_ll": [[30.1223, 31.40766], [30.12239, 31.40799]],
           "reach_isect": [82.1, 82.9], "reach_isect_empty": False,
           "needs_split": False, "blocks": 1}
    rec.update(kw)
    return rec


def test_the_copy_where_a_common_level_exists():
    assert frontage_warning(_rec(), MARGIN) == (
        "Building pad building7 at 30.12220, 31.40732 (12,346 m²): the apron cannot "
        "be welded to it along its whole frontage within the grade caps. The pad is "
        "seated flat at 82.46 m, the apron's own level there; 3 of 16 frontage "
        "contacts are released, the worst by 0.45 m at 30.12230, 31.40766. Why: a "
        "common level within reach exists (82.10–82.90 m), but the apron around "
        "those contacts cannot blend to it under its caps and the fixed airside. "
        "The apron keeps its caps; the pad's rim steps there; the building is not "
        "moved.")


def test_the_copy_where_no_single_level_is_in_reach():
    text = frontage_warning(_rec(reach_isect=[83.4, 82.2], reach_isect_empty=True),
                            MARGIN)
    assert text == (
        "Building pad building7 at 30.12220, 31.40732 (12,346 m²): the apron cannot "
        "be welded to it along its whole frontage within the grade caps. The pad is "
        "seated flat at 82.46 m, the apron's own level there; 3 of 16 frontage "
        "contacts are released, the worst by 0.45 m at 30.12230, 31.40766. Why: no "
        "single level is within the apron's reach of every frontage contact from "
        "the fixed taxiways and runways: the lowest contact can be reached only up "
        "to 82.20 m and the highest only down to 83.40 m. The apron keeps its caps; "
        "the pad's rim steps there; the building is not moved.")


def test_the_one_block_suffix():
    text = frontage_warning(_rec(needs_split=True), MARGIN)
    assert ("the fixed airside; the unit reads one level, so it is not split into "
            "blocks. The apron keeps its caps;") in text
    # a unit already cut into blocks is not told it reads one level
    assert "not split into blocks" not in frontage_warning(
        _rec(needs_split=True, blocks=2), MARGIN)


def test_under_the_bar_nothing_is_said():
    rec = stamp_warning(_rec(released_max_m=0.25), MARGIN)
    assert rec["warned"] is False and rec["warning"] is None
    assert "warning_unsaid" not in rec
    assert warnings_of([rec]) == []
    # no released weld: nothing either, whatever the number
    assert frontage_warning(_rec(released=0, released_max_m=0.0), MARGIN) is None


def test_over_the_bar_is_stamped_and_listed():
    rec = stamp_warning(_rec(), MARGIN)
    assert rec["warned"] is True and rec["warning"].startswith("Building pad building7")
    assert warnings_of([rec, {"ref": "x", "refused": "draped_facade"}]) == [rec["warning"]]


def test_a_record_lacking_a_slot_says_which_and_no_sentence():
    rec = stamp_warning(_rec(reach_isect=[None, 82.9]), MARGIN)
    assert rec["warned"] is False and rec["warning"] is None
    assert rec["warning_unsaid"] == ["reach_isect"]
    assert missing_slots(_rec(pad_m2=None, reach_isect=None)) == ("pad_m2", "reach_isect")


def test_the_hold_report_is_carried_by_ref_and_only_its_keys():
    saved = dict(mp.HELD)
    try:
        mp.HELD.clear()
        mp.HELD["a"] = {"unit": "a", "k": 0}
        mp.HELD["b"] = {"unit": "b", "k": 0}
        stage1 = {"a": {"unit": "a", "reach_isect": [1.0, 2.0], "reach_isect_empty": False,
                        "datum_chosen": 1.5, "hold_contacts": [(7, None)]},
                  "gone": {"reach_isect": [0.0, 0.0]}}
        rep = mp.hold_report(stage1)
        assert set(rep) == {"a", "gone"} and "hold_contacts" not in rep["a"]
        assert mp.install_hold_report(rep) == 1
        assert mp.HELD["a"]["reach_isect"] == [1.0, 2.0] and mp.HELD["a"]["datum_chosen"] == 1.5
        assert "hold_contacts" not in mp.HELD["a"] and "reach_isect" not in mp.HELD["b"]
        rep["a"]["reach_isect"][0] = 9.0           # a deep copy, not a view
        assert mp.HELD["a"]["reach_isect"] == [1.0, 2.0]
    finally:
        mp.HELD.clear()
        mp.HELD.update(saved)


def test_the_census_rows_are_the_released_blocks_each_with_warned():
    spec = importlib.util.spec_from_file_location("check_grade_w", ROOT / "tools" / "check_grade.py")
    cg = importlib.util.module_from_spec(spec)
    sys.modules["check_grade_w"] = cg
    spec.loader.exec_module(cg)
    recs = [stamp_warning(_rec(), MARGIN),
            stamp_warning(_rec(ref="building8", released_max_m=0.25, released=1), MARGIN),
            stamp_warning(_rec(ref="building9", released=0, released_max_m=0.0), MARGIN),
            {"ref": "building10", "refused": "draped_facade"},
            stamp_warning(_rec(ref="building11", reach_isect=[None, None]), MARGIN)]
    rows = cg._check_pad_frontage(recs, False)
    assert [(r.way_a.ref, r.reading, r.de_m, r.distance_m) for r in rows] == [
        ("pad_frontage_infeasible:building7", "warned", 0.45, 3.0),
        ("pad_frontage_infeasible:building8", "not_warned", 0.25, 1.0),
        ("pad_frontage_infeasible:building11", "unsaid", 0.45, 3.0)]
    assert (rows[0].lat, rows[0].lon) == (30.1223, 31.40766)
