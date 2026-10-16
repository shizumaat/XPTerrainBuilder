"""THE RUNWAY WITNESSES and the RAOA end filter (regulation-conformance
spec ``docs/specs/regulation-conformance-20261015.md`` §3, §2.B; owner
RULINGS 2026-10-15k/l/m/n; lane regL1).

* ONE code-number and ONE code-letter classifier (``law.reference_code``),
  stamped by the loader, published in ``runway_axes`` and read back by
  verify and the census (``verify.runway_witness``);
* the approach class of each END: CIFP ident class (``cifp``) joined to the
  end (designator or #119 threshold fallback), strengthened by apt.dat
  precision markings; Cat II/III by lighting + TDZ (``airport.approach``);
* the RAOA only before a precision end (Annex 14 §3.8.1) — one predicate
  for the generator, verify and the census.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from auto_patch_v2.airport import approach as AP
from auto_patch_v2.airport import cifp as C
from auto_patch_v2.airport.apt_dat import _runway
from auto_patch_v2.airport.load import Inputs, load_with_report
from auto_patch_v2.law import Law
from auto_patch_v2.law import reference_code as RC
from auto_patch_v2.verify import runway_witness as RW

FIX = Path(__file__).resolve().parent / "fixtures" / "CYXY"
FT = 0.3048


@pytest.fixture(scope="module")
def law():
    return Law.load()


# ── §3.1 the letter, §3.2 the number ─────────────────────────────────────

@pytest.mark.parametrize("width_m, letter", [
    (60 * FT, "A"), (18.8, "A"), (18.81, "B"),     # 60 ft: AAC/ADG A/B-I
    (75 * FT, "B"), (23.4, "B"),                   # 75 ft: A/B-II
    (100 * FT, "C"), (31.0, "C"), (31.01, "D"),    # 100 ft: C, not D
    (45.0, "D"),                                   # ICAO 45 m
    (150 * FT, "E"), (46.3, "E"),                  # 150 ft: the ADG-V tail
    (60.0, "F"), (200 * FT, "F"),                  # Annex 14 F at 60 m
])
def test_one_letter_classifier_with_a_half_metre_tolerance(law, width_m, letter):
    assert RC.runway_code_letter(law, width_m) == letter


@pytest.mark.parametrize("length_m, code", [
    (0.0, 1), (799.9, 1), (800.0, 2), (1199.9, 2), (1200.0, 3), (1800.0, 4), (4000.0, 4)])
def test_one_code_number_classifier(law, length_m, code):
    assert RC.runway_code_number(law, length_m) == code


# ── §3.4 the approach class per end ──────────────────────────────────────

def test_cifp_ident_route_type_gives_the_class_and_the_strongest_wins(tmp_path):
    f = tmp_path / "ZZZZ.dat"
    f.write_text("".join(f"APPCH:010,A,{ident},X,X,ZZ,P,C,E  A, ,   ,IF;\n" for ident in (
        "N05", "R05", "L23", "J23", "R14Y", "H14", "V32", "I32LZ", "M09", "D27", "VDM-A")),
        encoding="utf-8", newline="\n")
    assert C.read_cifp_approach_runways(str(f)) == {
        "05": "apv", "23": "pa", "14": "apv", "32": "npa", "32L": "pa", "09": "pa",
        "27": "npa"}


@pytest.mark.parametrize("cifp, marks, lights, tdz, want", [
    (None, 0, 0, 0, ("visual", False)),
    (None, 2, 0, 0, ("visual", False)),       # 15n: non-precision paint alone
    (None, 4, 2, 1, ("visual", False)),
    (None, 3, 0, 0, ("pa", False)),           # 15m (2): precision markings
    (None, 5, 0, 0, ("pa", False)),
    ("npa", 2, 0, 0, ("npa", False)),
    ("apv", 1, 0, 0, ("apv", False)),
    ("npa", 3, 0, 0, ("pa", False)),          # either source
    ("pa", 2, 0, 0, ("pa", False)),
    ("pa", 3, 2, 1, ("pa", True)),            # ALSF-II + TDZ
    ("pa", 3, 4, 1, ("pa", True)),            # Calvert II/III + TDZ
    ("pa", 3, 2, 0, ("pa", False)),           # no TDZ lights
    ("pa", 3, 1, 1, ("pa", False)),           # ALSF-I is not Cat II/III
    ("apv", 2, 2, 1, ("apv", False)),         # Cat II/III only at a precision end
])
def test_end_approach_reads_either_source(cifp, marks, lights, tdz, want):
    assert AP.end_approach(cifp, marks, lights, tdz) == want


def test_row_100_carries_lights_and_tdz_per_end():
    row = ("100 45.72 1 0 0.25 0 3 0 "
           "18C 35.0 -80.0 0 0 3 2 1 1 "
           "36C 35.1 -80.0 0 0 2 8 0 0").split()
    rw = _runway(row)
    assert rw.markings == (3, 2) and rw.approach_lights == (2, 8) and rw.tdz_lights == (1, 0)


def _cifp_with_approaches(tmp_path: Path, rename: dict[str, str], idents) -> str:
    d = tmp_path / "CIFP"
    d.mkdir()
    lines = []
    for raw in (FIX / "CIFP" / "CYXY.dat").read_text(encoding="utf-8", errors="replace").splitlines():
        for old, new in rename.items():
            raw = raw.replace(f"RWY:RW{old:<3s}", f"RWY:RW{new:<3s}")
        lines.append(raw)
    lines += [f"APPCH:010,A,{i},X,X,CY,P,C,E  A, ,   ,IF;" for i in idents]
    (d / "CYXY.dat").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(d)


def _load(cifp_dir: str):
    return load_with_report("CYXY", Inputs(
        xplane_root=str(FIX), cifp_dir=cifp_dir, osm_root=str(FIX / "OSM_data"),
        elevation_root=str(FIX / "Elevation_data"), dem_frame="authored",
        mod_cache_root=str(FIX / "Airport_mod_cache")), Law.for_airport("CYXY"))[0]


def test_the_loader_stamps_each_end_through_the_threshold_join(tmp_path):
    """14R/32L RENAMED 15R/33L in the CIFP (the KCLT class, #119): the ILS
    to 33L reaches apt.dat's 32L through the threshold join; 14L's RNAV is
    APV; 14R and 32R have non-precision paint (2) and no approach: visual.
    02/20 likewise — non-instrument (15n)."""
    a = _load(_cifp_with_approaches(tmp_path, {"14R": "15R", "32L": "33L"},
                                    ("I33LY", "R14L")))
    got = {e.name: (e.approach, e.cat_ii_iii) for r in a.runways for e in r.ends}
    assert got == {"14R": ("visual", False), "32L": ("pa", False), "14L": ("apv", False),
                   "32R": ("visual", False), "02": ("visual", False),
                   "20": ("visual", False)}
    assert [r.instrument for r in a.runways] == [True, True, False]
    # the stamp: 45.72 m E, 100 ft C (the letter fix), 75 ft B
    assert [(r.code_number, r.code_letter) for r in a.runways] == [(4, "E"), (4, "C"), (1, "B")]


# ── §2.B the RAOA end filter, and the published read ─────────────────────

def test_raoa_binds_before_a_precision_end_only(law):
    icao = Law.for_airport("CYXY")
    assert [RC.raoa_applies(icao, c) for c in RC.APPROACH_CLASSES] == [False, False, False, True]
    assert not RC.raoa_applies(Law.for_airport("KCLT"), "pa")      # FAA states no RAOA
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from harness.law_support import grade_law
    assert [grade_law.raoa_applies(c, "icao") for c in RC.APPROACH_CLASSES] == \
        [RC.raoa_class(c) for c in RC.APPROACH_CLASSES]
    assert not grade_law.raoa_applies("pa", "faa")


def test_the_published_witness_is_read_back_by_the_end_it_belongs_to(law):
    row = ["14R/32L", 60.0, -135.0, 60.02, -135.0, 22.86, 0.0, 0.0, 240.0, 240.0, 1,
           4, "E", "npa", "pa", 0, 0]
    to_m = lambda la, lo: (lo * 55_000.0, la * 111_000.0)   # noqa: E731
    a, b = to_m(60.0, -135.0), to_m(60.02, -135.0)
    assert RW.published_end_classes([row], "14R/32L", a, b, to_m) == ("npa", "pa")
    assert RW.published_end_classes([row], "14R/32L", b, a, to_m) == ("pa", "npa")
    assert RW.published_code_number([row], "14R/32L", 10.0, law) == 4
    assert RW.published_code_letter([row], "14R/32L", "A") == "E"
    old = row[:11]                                   # a patch predating the slots
    assert RW.published_end_classes([old], "14R/32L", a, b, to_m) is None
    assert RW.published_code_number([old], "14R/32L", 1500.0, law) == 3
    assert RW.published_code_letter([old], "14R/32L", "D") == "D"
