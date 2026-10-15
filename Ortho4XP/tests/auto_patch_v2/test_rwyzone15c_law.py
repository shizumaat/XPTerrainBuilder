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
    # ICAO: the strip's 60 m past the end + the RESA from the strip's end
    assert runway_safety_area_length_m(icao, 4, "C") == pytest.approx(60.0 + 240.0)
    assert runway_safety_area_length_m(icao, 1, "A") == pytest.approx(30.0 + 60.0)


def test_faa_runway_band_falls_at_five_percent_icao_at_three(faa, icao):
    lip = icao.tables.zones.adjacent_ground.lip_width_m
    d = 50.0
    lo_f, _ = zone_bounds(faa, "runway", d, 4, "D", half_m=60.0)
    lo_i, _ = zone_bounds(icao, "runway", d, 4, "D", half_m=60.0)
    fall_lip = icao.tables.zones.adjacent_ground.lip_max_down * lip
    assert -lo_f == pytest.approx(fall_lip + 0.05 * (d - lip))
    assert -lo_i == pytest.approx(fall_lip + 0.03 * (d - lip))


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
