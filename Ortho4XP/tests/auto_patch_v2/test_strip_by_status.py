"""THE STRIP BY INSTRUMENT STATUS (#811; audit
``docs/findings/law-table-audit-20261015.md`` rows 7 and 12; owner RULINGS
2026-10-15k): the two rows #776 left.

* ICAO Annex 14 §3.4.8: an INSTRUMENT runway's graded strip is 40 m from
  the centreline at code 1 (§3.4.9's non-instrument 30 m otherwise);
* FAA AC 150/5300-13B App. G Tables G-2 / G-4, "Lower than 3/4 mile": the
  RSA of an A/B-I or A/B-II runway with a PRECISION end is 300 ft wide
  (half 45.7 m) and runs 600 ft (182.9 m) beyond each end.

Synthetic runways only: every reader of the half-width — the planar band,
the strip keep-out, the ribbon extent, the end area, verify and the census
— reads the runway's status through ONE value
(``law.reference_code.runway_status``), from the runway, its ref or the
sidecar row.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from shapely.ops import unary_union

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.reference_code import (INSTRUMENT, NON_INSTRUMENT, PRECISION,
                                              ref_status, runway_status, status_by_ref,
                                              status_of_classes)
from auto_patch_v2.law.tables import (runway_safety_area_length_m, runway_zone_edge_offset_m,
                                      zone2_half_width_m, zone_bounds, zone_edge_offset_m)

FT = 0.3048


@pytest.fixture(scope="module")
def faa():
    return Law.load(ruleset="faa")


@pytest.fixture(scope="module")
def icao():
    return Law.load(ruleset="icao")


# ── the tables ──────────────────────────────────────────────────────────

def test_icao_code_1_instrument_strip_is_40_m(icao):
    """§3.4.8 instrument 75 / 75 / 40 / 40; §3.4.9 non-instrument 75 / 75 / 40 / 30."""
    for code, non, ins in ((1, 30.0, 40.0), (2, 40.0, 40.0), (3, 75.0, 75.0), (4, 75.0, 75.0)):
        assert zone2_half_width_m(icao, "runway", code, "A") == non
        assert zone2_half_width_m(icao, "runway", code, "A", INSTRUMENT) == ins
        assert zone2_half_width_m(icao, "runway", code, "A", PRECISION) == ins
    # the bool instrument flag is the same number
    assert zone2_half_width_m(icao, "runway", 1, "A", True) == 40.0
    # the taxi family states no status
    assert zone2_half_width_m(icao, "junction", None, "C", PRECISION) == \
        zone2_half_width_m(icao, "junction", None, "C")


def test_faa_ab_precision_rsa_is_300_by_600_ft(faa):
    """G-2 / G-4 "Lower than 3/4 mile": 300 ft wide, 600 ft beyond the end;
    C-E 500 x 1,000 ft at every visibility."""
    for letter, half, length in (("A", 120 / 2, 240), ("B", 150 / 2, 300)):
        for status in (NON_INSTRUMENT, INSTRUMENT):
            assert zone2_half_width_m(faa, "runway", 2, letter, status) == \
                pytest.approx(half * FT, abs=0.05)
            assert runway_safety_area_length_m(faa, 2, letter, status) == \
                pytest.approx(length * FT, abs=0.05)
        assert zone2_half_width_m(faa, "runway", 2, letter, PRECISION) == \
            pytest.approx(150 * FT, abs=0.05)
        assert runway_safety_area_length_m(faa, 2, letter, PRECISION) == \
            pytest.approx(600 * FT, abs=0.05)
    for letter in "CDEF":
        for status in (NON_INSTRUMENT, INSTRUMENT, PRECISION):
            assert zone2_half_width_m(faa, "runway", 4, letter, status) == 76.2
            assert runway_safety_area_length_m(faa, 4, letter, status) == \
                pytest.approx(1000 * FT, abs=0.05)


def test_precision_reads_icao_s_instrument_lengths(icao):
    """ICAO states its strip end and RESA by instrument status only: a
    precision runway reads the instrument figures."""
    for code in (1, 2, 3, 4):
        assert runway_safety_area_length_m(icao, code, "C", PRECISION) == \
            runway_safety_area_length_m(icao, code, "C", INSTRUMENT)


def test_the_edge_offset_and_the_corridor_read_the_status(faa, icao):
    assert runway_zone_edge_offset_m(icao, 1, "A", 9.0, INSTRUMENT) == pytest.approx(40.0 - 9.0)
    assert runway_zone_edge_offset_m(icao, 1, "A", 9.0) == pytest.approx(30.0 - 9.0)
    assert zone_edge_offset_m(faa, "runway", 2, "B", 11.5, status=PRECISION) == \
        pytest.approx(45.7 - 11.5)
    # zone 2 reaches the status's half-width, zone 3 (the DEM) beyond it
    assert zone_bounds(icao, "runway", 35.0, 1, "A") == (None, None)
    assert zone_bounds(icao, "runway", 35.0, 1, "A", status=INSTRUMENT) != (None, None)


# ── the status witness ─────────────────────────────────────────────────

def _rw(ref, classes, instrument=None):
    ends = tuple(SimpleNamespace(approach=c) for c in classes)
    ins = any(c != "visual" for c in classes) if instrument is None else instrument
    return SimpleNamespace(id=ref, ends=ends, instrument=ins)


def test_the_runway_status_is_its_strongest_end():
    assert status_of_classes(("visual", "visual")) == NON_INSTRUMENT
    assert status_of_classes(("visual", "npa")) == INSTRUMENT
    assert status_of_classes(("apv", "visual")) == INSTRUMENT
    assert status_of_classes(("visual", "pa")) == PRECISION
    assert status_of_classes((), True) == INSTRUMENT
    assert runway_status(_rw("09/27", ("pa", "visual"))) == PRECISION
    # a fixture stamping ``instrument`` with visual ends is instrument
    assert runway_status(_rw("09/27", ("visual", "visual"), True)) == INSTRUMENT
    of = status_by_ref([_rw("09/27", ("pa", "visual")), _rw("18/36", ("npa", "npa"))])
    assert ref_status(of, "09/27") == PRECISION
    assert ref_status(of, "18/36+09/27") == PRECISION     # a crossing: the stronger
    assert ref_status(of, "05/23") == NON_INSTRUMENT
    assert ref_status(None, "09/27") == NON_INSTRUMENT


def test_verify_and_the_census_read_the_published_status():
    """The sidecar row: slot 10 the instrument flag, 13 / 14 the end
    classes (``pipeline/publication``)."""
    from auto_patch_v2.verify.runway_witness import published_status

    def row(ref, ins, a, b):
        return [ref, 0, 0, 0, 0, 15.0, 0, 0, 0, 0, ins, 2, "B", a, b]

    rows = [row("09/27", 1, "pa", "visual"), row("18/36", 1, "npa", "visual"),
            row("05/23", 0, "visual", "visual"), ["old", 0, 0, 0, 0, 15.0]]
    assert published_status(rows, "09/27") == PRECISION
    assert published_status(rows, "18/36") == INSTRUMENT
    assert published_status(rows, "05/23") == NON_INSTRUMENT
    assert published_status(rows, "old") == NON_INSTRUMENT
    assert published_status(rows, "05/23+09/27") == PRECISION
    assert published_status(rows, None) == NON_INSTRUMENT
    # a row before the end classes: the flag alone
    assert published_status([["x"] + [0] * 9 + [1]], "x") == INSTRUMENT


def test_the_census_strip_half_width_is_the_engine_s(faa, icao):
    """``grade_law.runway_strip_half_width_m`` (the census's wall keep-out
    and end corridor) agrees with ``tables.zone2_half_width_m`` at every
    status."""
    from auto_patch.config import get_ruleset
    from tools.harness.law_support import grade_law as gl
    for law, key, cases in ((icao, "icao", [(c, "C") for c in (1, 2, 3, 4)]),
                            (faa, "faa", [(4, letter) for letter in "ABCDEF"])):
        rs = get_ruleset(key)
        for code, letter in cases:
            for status in (NON_INSTRUMENT, INSTRUMENT, PRECISION):
                assert gl.runway_strip_half_width_m(code, letter, rs, status) == \
                    pytest.approx(zone2_half_width_m(law, "runway", code, letter, status))


# ── the readers, on synthetic runways ──────────────────────────────────

def _cells(code, letter, half=9.0):
    ring = ((-400.0, -half), (400.0, -half), (400.0, half), (-400.0, half))
    return (Cell(0, "runway", "09/27", ring, (), code, letter, "airside", "runway", {}),)


@pytest.mark.parametrize("ruleset, code, letter, status, half, rsa", [
    ("icao", 1, "A", NON_INSTRUMENT, 30.0, 30.0 + 30.0),
    ("icao", 1, "A", INSTRUMENT, 40.0, 60.0 + 90.0),
    ("faa", 2, "B", INSTRUMENT, 22.9, 91.4),
    ("faa", 2, "B", PRECISION, 45.7, 182.9),
])
def test_the_planar_band_is_the_status_s_strip(ruleset, code, letter, status, half, rsa):
    """``planar/zones._runway_band``: the runway record's last slot is the
    status (``overlay._runway_records``)."""
    from auto_patch_v2.planar.zones import zone_regions
    law = Law.load(ruleset=ruleset)
    runways = (("09/27", (-400.0, 0.0), (400.0, 0.0), 18.0, None, None, status),)
    regs = zone_regions(_cells(code, letter), law, runways=runways)
    x0, y0, x1, y1 = unary_union([r.polygon for r in regs if r.zone == 2]).bounds
    assert (y0, y1) == pytest.approx((-half, half), abs=0.01)
    assert (x0, x1) == pytest.approx((-400.0 - rsa, 400.0 + rsa), abs=0.01)


def _runway(classes, code, letter):
    from auto_patch_v2.model.airport import Runway, RunwayEnd
    ends = tuple(RunwayEnd(n, xy, (0.0, 0.0), 0.0, 0.0, 100.0, "fixture", c)
                 for n, xy, c in (("09", (-400.0, 0.0), classes[0]),
                                  ("27", (400.0, 0.0), classes[1])))
    return Runway("09/27", 18.0, 1, ends, code, letter,
                  any(c != "visual" for c in classes))


@pytest.mark.parametrize("ruleset, code, letter, classes, half", [
    ("icao", 1, "A", ("visual", "visual"), 30.0),
    ("icao", 1, "A", ("npa", "visual"), 40.0),
    ("faa", 2, "B", ("npa", "npa"), 22.9),
    ("faa", 2, "B", ("visual", "pa"), 45.7),
])
def test_the_keep_outs_and_the_ribbon_extent_read_the_runway(ruleset, code, letter,
                                                              classes, half):
    """``planar/strip_keepout`` and ``classify/ribbon_mint.ribbon_extent``
    meet the runway by the cell's ref; ``classify.roles.shoulder_band``
    and ``model/end_area`` read it directly."""
    from auto_patch_v2.classify.ribbon_mint import ribbon_extent
    from auto_patch_v2.classify.roles import shoulder_band
    from auto_patch_v2.model.end_area import end_area_lengths
    from auto_patch_v2.planar.strip_keepout import strip_keepout
    from shapely.geometry import Polygon
    law = Law.load(ruleset=ruleset)
    rw = _runway(classes, code, letter)
    status = runway_status(rw)
    cells = _cells(code, letter)
    # both buffer the CELL by the centreline figure (an upper bound: the
    # keep-out may overshoot the band, never fall short)
    keep = strip_keepout(SimpleNamespace(cells=cells), law, (rw,))
    assert keep.bounds[3] == pytest.approx(9.0 + half, abs=0.01)
    pav = unary_union([Polygon(c.ring) for c in cells])
    ext = ribbon_extent(cells, law, pav, (rw,))
    assert ext.bounds[3] == pytest.approx(9.0 + half, abs=0.01)
    rsa = runway_safety_area_length_m(law, code, letter, status)
    assert ext.bounds[2] == pytest.approx(400.0 + rsa, abs=0.01)
    band = shoulder_band(rw, law)
    assert band.bounds[3] == pytest.approx(half, abs=0.01)
    lens = end_area_lengths(SimpleNamespace(runways=(rw,), dem=None), law)
    assert lens["09/27"] == pytest.approx((rsa, rsa))
