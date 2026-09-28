"""§37 (11) (7) TWINS — A NATURAL SHORE SLOPES TO THE WATER LINE (owner
RULINGS 2026-09-27a (7), issue #19): a runway end on a natural shore slopes
to the water line (zone 2 at 1:3, no vertical face); §37 (11)'s quay wall
applies only where OSM / the pack DECLARES a quay or wall.

Measured at NLWF (lane ``nlwfends``, harness ``nlwfends_c0`` against
``nlwfends_s3``): the five §37 (11) sea walls 4.75 / 3.65 / 3.60 / 3.30 /
3.18 m on the south shore — the "excavated block" the owner read at both
ends — became a strip falling to 0.00 at the coastline; census 9 → 4
(sea_wall 5 → 0, strip_transverse 0), ADJUDICATED 0.
Headless: synthetic zones and a synthetic tie, law values from the tables.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import zone_bounds
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.zones import (shore_declarations, shore_wedge_m,
                                        zone_regions)
from auto_patch_v2.verify.strips import runway_edge_tie

from test_v2vmmcshore import _SeaDem, _zone_cells


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_an_undeclared_shore_is_natural_not_a_quay(law):
    """The coast 10 m off the pavement, nothing declared: the zone that
    reaches it is a NATURAL shore — no quay, no sea wall."""
    wet = zone_regions(_zone_cells(), law, (), _SeaDem(), ())
    reach = [r for r in wet if r.natural_shore or r.quay]
    assert reach, [r.ref for r in wet]
    assert not any(r.quay for r in wet)
    assert all(r.natural_shore for r in reach)


def test_a_declared_quay_or_wall_keeps_the_wall(law):
    for tags in ({"man_made": "quay"}, {"man_made": "breakwater"},
                 {"barrier": "wall"}, {"man_made": "seawall"}):
        line = OsmWay(-1, "fixture", ((-300.0, -30.0), (300.0, -30.0)),
                      False, tags)
        wet = zone_regions(_zone_cells(), law, (), _SeaDem(), (), None,
                           shore_declarations((line,)))
        assert any(r.quay for r in wet), tags
        assert not any(r.natural_shore for r in wet), tags
    # a declaration elsewhere declares nothing here
    far = OsmWay(-2, "fixture", ((-300.0, -900.0), (300.0, -900.0)), False,
                 {"man_made": "quay"})
    wet = zone_regions(_zone_cells(), law, (), _SeaDem(), (), None,
                       shore_declarations((far,)))
    assert not any(r.quay for r in wet)
    # and a road is not a declaration
    assert shore_declarations((OsmWay(-3, "f", ((0.0, 0.0), (1.0, 0.0)), False,
                                      {"highway": "service"}),)) == ()


def test_a_pavement_edge_on_the_coastline_is_the_wall(law):
    """§37 (11) (2)'s second clause stands: the coast within the lip of the
    pavement leaves no land to slope on — the pavement edge is the wall."""
    wet = zone_regions(_zone_cells(), law, (), _SeaDem(-22.0), ())
    lip = [r for r in wet if r.zone == 1]
    assert lip and all(r.quay and not r.natural_shore for r in lip)


def test_the_slope_lives_in_the_wedge_only(law):
    """The band falls at the bank slope only within the wedge a 1:3 bank
    needs from the field to the sea — a zone far from the water keeps its
    class's band (NLWF: the north strip is 62 m from the sea)."""
    w = shore_wedge_m(law, 3.96)
    bank = float(law.tables.emit.design.bank_slope)
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    assert w == pytest.approx(lip + (3.96 + 1.0) / bank)
    wet = zone_regions(_zone_cells(), law, (), _SeaDem(), (), None, (), w)
    nat = [r for r in wet if r.natural_shore]
    assert nat and all(r.shore_wedge is not None for r in nat)
    for r in nat:
        assert r.shore_wedge.area <= r.polygon.area + 1e-6
        # nothing in the wedge stands farther from the sea than its width
        sea = _SeaDem().sea_geometry()
        assert max(sea.distance(__import__("shapely").geometry.Point(c))
                   for c in r.shore_wedge.exterior.coords) <= w + 1e-6


def test_zone_bounds_takes_the_bank_slope_fall_only(law):
    bank = float(law.tables.emit.design.bank_slope)
    lo, hi = zone_bounds(law, "runway", 30.0, 2, None)
    lo_n, hi_n = zone_bounds(law, "runway", 30.0, 2, None, band_max_down=bank)
    assert hi_n == hi                       # the mandatory-down ceiling stands
    lip = law.tables.zones.adjacent_ground
    assert lo_n == pytest.approx(-lip.lip_max_down * lip.lip_width_m
                                 - bank * (30.0 - lip.lip_width_m))
    assert lo_n < lo


def test_the_tie_reads_the_bank_slope_fall_inside_the_wedge(law):
    """One core for verify and census: a strip vertex 30 m off a code-2
    runway edge standing 8 m below it is a strip_transverse defect on an
    ordinary strip and lawful inside a natural-shore wedge."""
    edge = ((0.0, 0.0, 5.0), (200.0, 0.0, 5.0), "07/25", 2, None)
    pt = [(1, 100.0, -30.0, -3.0, True, "graded_strip")]
    q, tol = 0.01, 0.5
    assert runway_edge_tie(pt, [edge], {}, law, q, tol)
    wedge = Polygon(((0, -50), (200, -50), (200, -20), (0, -20)))
    assert not runway_edge_tie(pt, [edge], {}, law, q, tol, natural_shore=wedge)
    # the RISE side is unchanged inside the wedge
    up = [(2, 100.0, -30.0, 13.0, True, "graded_strip")]
    assert runway_edge_tie(up, [edge], {}, law, q, tol, natural_shore=wedge)
