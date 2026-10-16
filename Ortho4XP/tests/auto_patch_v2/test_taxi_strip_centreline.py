"""THE TAXIWAY GRADED STRIP FROM THE CENTRELINE (RULINGS 2026-10-15l (1),
audit ``docs/findings/law-table-audit-20261015.md`` row 3; spec
``docs/specs/regulation-conformance-20261015.md`` §2.A).

ICAO Annex 14 §3.11.4 states the graded portion of a taxiway strip from the
CENTRELINE (A 10.25 … F 22 m); FAA AC 150/5300-13B §4.5.3 states the
taxiway safety area as the ADG wingspan, so its half-width is half of it
(7.5 / 12.0 / 18.0 / 26.0 / 32.6 / 39.9 m).  The zone band reaches
``max(lip, half-width − the letter's pavement half-width)`` past the edge,
through ONE accessor (``tables.zone_edge_offset_m``) that the planar
derivation site, the generator and both census readers share.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import zone2_half_width_m, zone_edge_offset_m

#: (letter, centreline half-width, reach past the edge) per authority
ICAO = {"A": (10.25, 6.5), "B": (11.0, 5.75), "C": (12.5, 5.0),
        "D": (18.5, 9.5), "E": (19.0, 7.5), "F": (22.0, 9.5)}
FAA = {"A": (7.5, 3.75), "B": (12.0, 6.75), "C": (18.0, 10.5),
       "D": (26.0, 14.5), "E": (32.6, 21.1), "F": (39.9, 24.9)}


@pytest.fixture(scope="module")
def laws():
    return {"icao": Law.load(ruleset="icao"), "faa": Law.load(ruleset="faa")}


@pytest.mark.parametrize("key,table", [("icao", ICAO), ("faa", FAA)])
def test_the_strip_is_a_centreline_figure_reached_past_the_pavement(laws, key, table):
    law = laws[key]
    for letter, (half, reach) in table.items():
        assert zone2_half_width_m(law, "junction", None, letter) == pytest.approx(half)
        assert zone_edge_offset_m(law, "junction", None, letter) == pytest.approx(reach)


def test_the_default_letter_reads_one_letter_in_both_tables(laws):
    # no letter witnessed: the zone and the pavement width defaults are the
    # same letter (C), so the reach is C's
    assert zone_edge_offset_m(laws["icao"], "junction") == pytest.approx(5.0)
    assert zone_edge_offset_m(laws["faa"], "junction") == pytest.approx(10.5)


def test_the_runway_branch_is_the_15c_reading(laws):
    from auto_patch_v2.law.tables import runway_zone_edge_offset_m
    for law in laws.values():
        assert zone_edge_offset_m(law, "runway", 4, "D", 22.5) == pytest.approx(
            runway_zone_edge_offset_m(law, 4, "D", 22.5))
        # no runway width known: the centreline figure, an upper bound
        assert zone_edge_offset_m(law, "runway", 4, "D") == pytest.approx(
            zone2_half_width_m(law, "runway", 4, "D"))
    assert zone_edge_offset_m(laws["icao"], "apron") is None


def test_the_census_reads_the_engine_s_accessor_under_its_own_ruleset(laws):
    from tools.harness.law_support import grade_law
    from auto_patch import config as cfg
    for key, table in (("icao", ICAO), ("faa", FAA)):
        rs = cfg.get_ruleset(key)
        for letter, (_half, reach) in table.items():
            assert grade_law.taxiway_strip_edge_offset_m(letter, rs) == pytest.approx(reach)
            # the envelope's zone 2 ends exactly there (zone 3 beyond)
            inside = grade_law.adjacent_ground_envelope("junction", None, letter,
                                                        reach - 0.01, ruleset=key)
            beyond = grade_law.adjacent_ground_envelope("junction", None, letter,
                                                        reach + 1.0, ruleset=key)
            assert inside[0] is not None and beyond[0] is None, (key, letter, inside, beyond)


def test_the_planar_band_is_drawn_at_the_reach(laws):
    """THE DERIVATION SITE (A-1): a lone code-E taxiway's zone-2 ring stands
    the reach past its pavement, ICAO 7.5 m (19.0 m before) and FAA 21.1 m."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.zones import zone_regions
    ring = ((0.0, 0.0), (400.0, 0.0), (400.0, 23.0), (0.0, 23.0))
    cell = Cell(0, "primary_parallel", "pav1", ring, (), None, "E", "airside", "pav", {})
    for key, reach in (("icao", 7.5), ("faa", 21.1)):
        out = zone_regions([cell], laws[key])
        z2 = [r for r in out if r.zone == 2]
        assert z2, key
        ys = [y for r in z2 for g in getattr(r.polygon, "geoms", [r.polygon])
              for _x, y in g.exterior.coords]
        assert max(ys) == pytest.approx(23.0 + reach, abs=0.05), key
        assert min(ys) == pytest.approx(-reach, abs=0.05), key
