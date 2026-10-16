"""THE RUNWAY'S OUTER ZONE AND ITS END (owner RULINGS 2026-10-15c (1)-(4);
spec ``docs/specs/runway-zone-15c-spec.md``).

(1) "From the centreline": the zone-2 half-width is measured from the
    runway centreline; the band reaches max(lip, half-width − runway
    half-width) past the edge;
(2) "Full safety-area length": the end band runs the RSA length from the
    runway END (FAA by letter 240 / 300 / 1,000 ft, ICAO strip 60 m + RESA);
(3) WITHDRAWN (RULINGS 2026-10-15g (B)): no bank — the zone goes straight
    to raw DEM at its outer edge;
(4) "5% for FAA": the runway band's max fall under the FAA ruleset.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import (runway_safety_area_length_m, runway_zone_edge_offset_m,
                                      zone_bounds)
from auto_patch_v2.planar.zones import zone_regions

FT = 0.3048


@pytest.fixture(scope="module")
def faa():
    return Law.load(ruleset="faa")


@pytest.fixture(scope="module")
def icao():
    return Law.load(ruleset="icao")


def test_the_band_is_measured_from_the_centreline(faa, icao):
    # FAA C/D/E RSA 500 ft wide: a 30.5 m runway's band reaches 60.95 m past the edge
    assert runway_zone_edge_offset_m(faa, 4, "D", 15.25) == pytest.approx(76.2 - 15.25)
    assert runway_zone_edge_offset_m(faa, 4, "B", 11.5) == pytest.approx(22.9 - 11.5)
    assert runway_zone_edge_offset_m(icao, 4, "C", 22.5) == pytest.approx(75.0 - 22.5)
    # never less than the lip
    lip = icao.tables.zones.adjacent_ground.lip_width_m
    assert runway_zone_edge_offset_m(icao, 1, "A", 40.0) == pytest.approx(lip)


def test_the_rsa_length_is_the_authority_s_own(faa, icao):
    assert runway_safety_area_length_m(faa, 4, "A") == pytest.approx(240 * FT, abs=0.05)
    assert runway_safety_area_length_m(faa, 4, "B") == pytest.approx(300 * FT, abs=0.05)
    for letter in "CDEF":
        assert runway_safety_area_length_m(faa, 4, letter) == pytest.approx(1000 * FT, abs=0.05)
    # ICAO: the strip's end + the RESA from the strip's end, BY CODE AND
    # INSTRUMENT STATUS (RULINGS 2026-10-15k (1), Annex 14 §3.4.2 / §3.5.2-4)
    assert runway_safety_area_length_m(icao, 4, "C") == pytest.approx(60.0 + 240.0)
    assert runway_safety_area_length_m(icao, 4, "C", True) == pytest.approx(60.0 + 240.0)
    assert runway_safety_area_length_m(icao, 3, "C") == pytest.approx(60.0 + 90.0)
    # code 1/2 NON-instrument: the strip's 30 / 60 m + the recommended 30 m
    assert runway_safety_area_length_m(icao, 1, "A") == pytest.approx(30.0 + 30.0)
    assert runway_safety_area_length_m(icao, 2, "B") == pytest.approx(60.0 + 30.0)
    # code 1/2 INSTRUMENT: the strip's 60 m + the mandatory 90 m
    assert runway_safety_area_length_m(icao, 1, "A", True) == pytest.approx(60.0 + 90.0)
    assert runway_safety_area_length_m(icao, 2, "B", True) == pytest.approx(60.0 + 90.0)
    # FAA's RSA is by design group, never by instrument status here
    assert runway_safety_area_length_m(faa, 4, "B", True) == pytest.approx(300 * FT, abs=0.05)


def test_the_take_off_climb_surface_is_read_by_code(icao):
    """RULINGS 2026-10-15k (2), Annex 14 Table 4-2: code 1 5 % from 30 m,
    code 2 4 % from 60 m, code 3/4 2 % from 60 m."""
    from auto_patch_v2.law.tables import runway_end_profile
    for code, slope, setback in ((1, 0.05, 30.0), (2, 0.04, 60.0), (3, 0.02, 60.0),
                                 (4, 0.02, 60.0)):
        prof = runway_end_profile(icao, code, "B")
        assert (prof.climb_slope, prof.climb_setback_m) == pytest.approx((slope, setback))
    # the strip's end length by status: code 1 30 m, instrument 60 m
    assert runway_end_profile(icao, 1, "B").break_m == pytest.approx(30.0)
    assert runway_end_profile(icao, 1, "B", True).break_m == pytest.approx(60.0)


def test_the_instrument_witness_is_a_cifp_approach_to_the_runway(tmp_path):
    """RULINGS 2026-10-15k (3): an ``APPCH:`` procedure flown TO a runway
    makes it instrument; a circling procedure names no runway."""
    from auto_patch_v2.airport.cifp import read_cifp_approach_runways
    f = tmp_path / "ZZZZ.dat"
    f.write_text("RWY:RW14L,+0432,      ,02277, ,    , ,   ;N60431814,W135043590,0000;\n"
                 "APPCH:010,A,I32LY,RETEV,RETEV,CY,P,C,E  A, ,   ,IF;\n"
                 "APPCH:010,A,R14L,OBSIS,OBSIS,CY,P,C,E  A, ,   ,IF;\n"
                 "APPCH:010,N,N25,,WF,NL,P,C,E  A, ,   ,IF;\n"
                 "APPCH:010,A,VDM-A,ABC,ABC,CY,P,C,E  A, ,   ,IF;\n",
                 encoding="utf-8", newline="\n")
    assert read_cifp_approach_runways(str(f)) == {"32L", "14L", "25"}
    assert read_cifp_approach_runways(str(tmp_path / "none.dat")) == frozenset()


def test_the_runway_band_is_the_regulation_s_transverse_law(faa, icao):
    """RULINGS 2026-10-15l (2) / (4).  FAA (AC 150/5300-13B Table 3-6 S-3):
    falls 1.5 % to 3 % at AAC C-E, to 5 % at A/B (the width-letter proxy).
    ICAO (Annex 14 §3.4.15): beyond the lip the slope is bounded in
    MAGNITUDE only, 2.5 % at code 3/4, 3 % at code 1/2 — no minimum fall."""
    ag = icao.tables.zones.adjacent_ground
    lip = ag.lip_width_m
    d = 50.0
    band = d - lip
    for letter, fall in (("D", 0.03), ("B", 0.05)):
        lo, hi = zone_bounds(faa, "runway", d, 4, letter, half_m=60.0)
        assert -lo == pytest.approx(ag.lip_max_down * lip + fall * band)
        assert -hi == pytest.approx(ag.lip_min_down * lip + 0.015 * band)
    for code, mag in ((4, 0.025), (3, 0.025), (2, 0.03), (1, 0.03)):
        lo, hi = zone_bounds(icao, "runway", d, code, "D", half_m=60.0)
        assert -lo == pytest.approx(ag.lip_max_down * lip + mag * band)
        assert hi == pytest.approx(-ag.lip_min_down * lip + mag * band)
    # the lip itself is unchanged under both
    assert zone_bounds(icao, "runway", 2.0, 4, "D") == zone_bounds(faa, "runway", 2.0, 4, "D")


class _Falling:
    """Flat at 100 m over the runway, falling 10 % south of y = -20."""
    provenance = {"synthetic": "falling south"}

    def z(self, x: float, y: float) -> float:
        return 100.0 - 0.10 * max(0.0, -20.0 - y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Flat:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 100.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _runway_cells():
    ring = ((-1000.0, -15.0), (1000.0, -15.0), (1000.0, 15.0), (-1000.0, 15.0))
    return (Cell(0, "runway", "09/27", ring, (), 4, "D", "airside", "runway", {}),)


RUNWAYS = (("09/27", (-1000.0, 0.0), (1000.0, 0.0), 30.0),)


def test_the_planar_band_is_the_rsa_rectangle(faa):
    regs = zone_regions(_runway_cells(), faa, runways=RUNWAYS)
    from shapely.ops import unary_union
    x0, y0, x1, y1 = unary_union([r.polygon for r in regs if r.zone == 2]).bounds
    # 76.2 m from the CENTRELINE, 304.8 m past each runway END
    assert (y0, y1) == pytest.approx((-76.2, 76.2), abs=0.01)
    assert (x0, x1) == pytest.approx((-1000.0 - 304.8, 1000.0 + 304.8), abs=0.01)




# ── RULINGS 2026-10-15g (C): the end area stops at the top of a drop ──────

class _Profile:
    """Level to ``x = 1000 + top`` beyond the 27 end, then falling ``grade``."""
    provenance = {"synthetic": "end profile"}

    def __init__(self, top: float, grade: float):
        self.top, self.grade = top, grade

    def z(self, x: float, y: float) -> float:
        return 100.0 - self.grade * max(0.0, x - 1000.0 - self.top)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def test_an_escarpment_ends_the_end_area_at_its_top(faa):
    from auto_patch_v2.model.end_area import end_area_length
    rsa = runway_safety_area_length_m(faa, 4, "D")
    # level ground: the full RSA
    assert end_area_length(_Profile(1e9, 0.0), (1000.0, 0.0), (1.0, 0.0), faa, 4, "D") \
        == pytest.approx(rsa)
    # ordinary down-slope ground under the fill (KBJC's steepest end ground
    # is 10.5 %): the full RSA, filled to the profile
    assert end_area_length(_Profile(0.0, 0.08), (1000.0, 0.0), (1.0, 0.0), faa, 4, "D") \
        == pytest.approx(rsa)
    # an escarpment (CYXY's: 25-52 %) 150 m out: the end area stops at its top
    got = end_area_length(_Profile(150.0, 0.45), (1000.0, 0.0), (1.0, 0.0), faa, 4, "D")
    step = faa.tables.emit.design.edge_grid_m
    assert 150.0 - step <= got <= 150.0 + step


def test_a_crossing_piece_mints_no_band_of_its_own(icao):
    """A runway_crossing cell (ref ``a+b``) belongs to both runways' bands —
    alone it carried an RSA rectangle off its own few-metre axis (CYXY)."""
    ring_a = ((-1000.0, -15.0), (-15.0, -15.0), (-15.0, 15.0), (-1000.0, 15.0))
    ring_x = ((-15.0, -15.0), (15.0, -15.0), (15.0, 15.0), (-15.0, 15.0))
    ring_b = ((15.0, -15.0), (1000.0, -15.0), (1000.0, 15.0), (15.0, 15.0))
    ring_c = ((-15.0, 15.0), (15.0, 15.0), (15.0, 800.0), (-15.0, 800.0))
    cells = (Cell(0, "runway", "09/27", ring_a, (), 4, "D", "airside", "runway", {}),
             Cell(1, "runway_crossing", "09/27+18/36", ring_x, (), 4, "D", "airside",
                  "runway", {}),
             Cell(2, "runway", "09/27", ring_b, (), 4, "D", "airside", "runway", {}),
             Cell(3, "runway", "18/36", ring_c, (), 4, "D", "airside", "runway", {}))
    runways = (("09/27", (-1000.0, 0.0), (1000.0, 0.0), 30.0),
               ("18/36", (0.0, -15.0), (0.0, 800.0), 30.0))
    from shapely.ops import unary_union
    regs = zone_regions(cells, icao, runways=runways)
    x0, y0, x1, y1 = unary_union([r.polygon for r in regs]).bounds
    rsa = runway_safety_area_length_m(icao, 4, "D")
    assert x0 >= -1000.0 - rsa - 1.0 and x1 <= 1000.0 + rsa + 1.0
    assert y0 >= -15.0 - rsa - 1.0 and y1 <= 800.0 + rsa + 1.0


def test_the_instrument_witness_reads_the_apt_dat_markings_too():
    """RULINGS 2026-10-15n (amending 15m (2)): an end is INSTRUMENT when
    CIFP lists an approach to it OR apt.dat row 100 gives it PRECISION
    markings (3 or 5); non-precision markings (2, 4) alone do not count.
    The markings come off the row the loader already parses."""
    from auto_patch_v2.airport.apt_dat import _runway
    from auto_patch_v2.airport.load import instrument_markings
    row = ("100 30.00 1 0 0.25 1 2 1 "
           "02 60.71195640 -135.07178769 0 0 2 0 0 0 "
           "20 60.71513697 -135.06737621 0 0 1 0 0 0").split()
    rw = _runway(row)
    assert rw is not None and rw.markings == (2, 1)
    assert [instrument_markings(c) for c in range(7)] == [False, False, False, True,
                                                          False, True, False]


def test_a_strip_pair_on_non_runway_pavement_is_the_pavement_edge_s(icao):
    """#763 phase 8 (under RULINGS 2026-10-15l): a strip pair touching a
    taxiway / junction / apron vertex is a pavement-edge junction — the
    strip's longitudinal and arc laws skip it through ONE predicate
    (``constraints.end_lip.pavement_edge_junction``) that the generators and
    both readers share.  ``tables.generator_slack_m`` is the one slack
    helper (the end profile's; not the strip families', RULINGS 09-12y)."""
    from auto_patch_v2.constraints.end_lip import (nonrunway_pavement_roles,
                                                   pavement_edge_junction)
    from auto_patch_v2.constraints.strips import strip_longitudinal_pairs
    from auto_patch_v2.law.tables import end_profile_noise_m, generator_slack_m
    roles = nonrunway_pavement_roles(icao)
    assert {"primary_parallel", "junction", "apron"} <= roles and "runway" not in roles
    ids = [1, 2, 3, 4]
    xy = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    rect = [(-1.0, -5.0), (31.0, -5.0), (31.0, 5.0), (-1.0, 5.0), (-1.0, -5.0)]
    every = strip_longitudinal_pairs(ids, xy, (1.0, 0.0), rect, frozenset())
    kept = strip_longitudinal_pairs(ids, xy, (1.0, 0.0), rect, frozenset(), {3})
    assert len(every) == 3 and [(ids[i], ids[j]) for i, j, _d in kept] == [(1, 2)]
    assert pavement_edge_junction((1, 3), {3}) and not pavement_edge_junction((1, 2), {3})
    ins = icao.tables.emit.instrument
    assert generator_slack_m(icao, ins.coarse_noise_m) == pytest.approx(
        ins.coarse_noise_m - ins.rounding_noise_m)
    assert end_profile_noise_m(icao) == pytest.approx(generator_slack_m(icao, ins.strip_edge_noise_m))
