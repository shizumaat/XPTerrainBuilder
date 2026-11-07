"""THE RUNWAY DESIGN LETTER from apt.dat witnesses (owner RULINGS
2026-11-07a; #1947; ``law/reference_code.runway_code_letter``,
``airport/approach.design_letter``).

* row-100 markings CAP it: no precision-marked end -> at most B;
* the airport's largest row-1301 ramp-start size class LIFTS it
  to the same letter (C -> C ... F -> F; master 2026-11-07);
* pavement width is the tie-breaker; a runway with markings 0 at an
  airport with no 1301 class carries no witness and reads its width;
* the wide-runway floor (law key, default on): 150 ft never reads below C;
* the census tool reads the engine's own classifier.
"""
from __future__ import annotations

import dataclasses as dc
import sys
from pathlib import Path

import pytest

from auto_patch_v2.airport import apt_dat as A
from auto_patch_v2.airport import approach as AP
from auto_patch_v2.law import Law
from auto_patch_v2.law import reference_code as RC
from auto_patch_v2.law.tables import zone2_half_width_m

FT = 0.3048
TOOLS = Path(__file__).resolve().parents[2] / "tools"


@pytest.fixture(scope="module")
def faa():
    return Law.for_airport("KSBS")


def _block(width_m: float, marks: tuple[int, int], ramp: tuple[str, ...]) -> list[str]:
    rows = ["1 10 0 0 XTST test field",
            f"100 {width_m:.2f} 1 0 0.25 0 2 0 "
            f"14 35.0 -80.0 0 0 {marks[0]} 0 0 0 "
            f"32 35.012 -79.99 0 0 {marks[1]} 0 0 0"]
    for k, cls in enumerate(ramp):
        rows += [f"1300 35.005 -79.995 90.0 gate jets|turboprops Ramp {k}",
                 f"1301 {cls} general_aviation"]
    return rows


def test_1301_size_class_rides_on_its_ramp_start():
    ap = A.parse_airport_block(_block(30.48, (2, 2), ("A", "C", "b")) +
                               ["1300 35.0 -80.0 0 tie_down props Tie no attrs"])
    assert [s.width_class for s in ap.startups] == ["A", "C", "B", ""]
    assert AP.airport_ramp_class(ap) == "C"
    assert A._startup_width_class("1301 Z airline".split()) == ""


@pytest.mark.parametrize("width_m, marks, ramp, want", [
    (100 * FT, (1, 2), ("A",) * 7, "B"),     # KSBS 14/32: NPI, ramp A -> B
    (100 * FT, (2, 3), ("A",), "C"),         # a precision end lifts the cap
    (75 * FT, (2, 2), ("C",), "C"),          # ramp C lifts a 75 ft runway
    (60 * FT, (1, 1), ("E",), "E"),          # the same letter (wingspan class)
    (60 * FT, (0, 0), ("F",), "F"),          # KLAX custom class: markings 0, ramp F
    (150 * FT, (3, 3), ("D",), "E"),         # width breaks the tie above the lift
    (150 * FT, (2, 2), ("B",), "C"),         # the wide-runway floor
    (40.0, (0, 0), (), "D"),                 # no witness: width, uncapped
    (40.0, (0, 0), ("A",), "B"),             # a ramp class is a witness
])
def test_design_letter_reads_markings_ramp_and_width(faa, width_m, marks, ramp, want):
    ap = A.parse_airport_block(_block(width_m, marks, ramp))
    assert AP.design_letter(faa, ap.runways[0], AP.airport_ramp_class(ap)) == want


def test_ksbs_zone2_is_b_ii_not_c(faa):
    ap = A.parse_airport_block(_block(100 * FT, (1, 2), ("A",) * 7))
    letter = AP.design_letter(faa, ap.runways[0], AP.airport_ramp_class(ap))
    assert zone2_half_width_m(faa, "runway", 3, letter, RC.INSTRUMENT) == 22.9
    assert zone2_half_width_m(faa, "runway", 3, RC.runway_code_letter(faa, 100 * FT),
                              RC.INSTRUMENT) == 76.2


def test_floor_is_a_law_key(faa):
    rc = faa.tables.common.reference_code
    off = dc.replace(faa, tables=dc.replace(faa.tables, common=dc.replace(
        faa.tables.common, reference_code=dc.replace(rc, wide_runway_floor=False))))
    assert RC.runway_code_letter(faa, 150 * FT, False, "B") == "C"
    assert RC.runway_code_letter(off, 150 * FT, False, "B") == "B"
    # never above the width letter: a 45 m floor reads the width's own D
    assert RC.runway_code_letter(faa, 45.0, False, None) == "C"
    assert RC.runway_code_letter(faa, 45.0, None, None) == "D"


def test_census_reads_the_engine_classifier(tmp_path):
    sys.path.insert(0, str(TOOLS))
    import design_letter_census as DLC
    xp = tmp_path / "XP"
    d = xp / "Global Scenery" / "Global Airports" / "Earth nav data"
    d.mkdir(parents=True)
    blk = _block(100 * FT, (1, 2), ("A",) * 3)
    blk[0] = "1 10 0 0 KSBS test field"
    (d / "apt.dat").write_text("I\n1200 test\n" + "\n".join(blk) + "\n99\n", encoding="utf-8",
                                   newline="\n")
    rows = DLC.census(str(xp), custom=False)
    assert [(r["icao"], r["old"], r["new"], r["zone2_old_m"], r["zone2_new_m"]) for r in rows] \
        == [("KSBS", "C", "B", 76.2, 22.9)]
    assert "letter changes 1" in DLC.summarise(rows)
