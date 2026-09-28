"""§37 (11) THE SHORE DECISION — twins per witness (owner RULINGS
2026-09-29a, issue #72).

Wherever water lies inside a pavement's zone 1 or 2 the contact is decided
by precedence: (1) DECLARED OSM tag → wall; (2) a PACK wall-class object
along the shore within one identity spacing → wall; (3) the pavement edge
on the coastline within the lip → wall; (4) the TERRAIN PROFILE across the
last 10 m before the water line — a >= 2 m drop taken steeper than 1:3 is a
built edge → wall at that height, a profile at or gentler than 1:3 →
natural; (5) default natural, a ``shore_undeclared`` row.

Headless: the synthetic junction of ``test_v2vmmcshore`` (its south edge
10 m from a straight coast at y = -30), synthetic DEMs in the frame.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.shore import (SHORE_WITNESSES, PackWall,
                                        shore_contact, shore_declarations,
                                        shore_profile, shore_verdict)
from auto_patch_v2.planar.zones import zone_regions

from test_v2vmmcshore import _SeaDem, _zone_cells

Y_SHORE = -30.0


class _ProfileDem(_SeaDem):
    """The sea south of ``y = -30``; the land's height a function of the
    distance inland from the water line."""

    def __init__(self, fn) -> None:
        super().__init__(Y_SHORE)
        self.fn = fn

    def z(self, x: float, y: float) -> float:
        return float(self.fn(max(0.0, y - Y_SHORE)))


def _step(h: float, at: float = 4.5):
    return lambda d: 0.0 if d < at else h


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _reach(regions):
    return [r for r in regions if r.shore is not None]


def _decide(law, dem, declared=(), walls=()):
    reach = _reach(zone_regions(_zone_cells(), law, (), dem, (), None,
                                declared, None, walls))
    assert reach
    return reach


def test_the_witnesses_are_the_rulings_five_in_order():
    assert SHORE_WITNESSES == ("declared", "pack_wall", "pavement", "profile",
                               "default")


def test_the_law_keys(law):
    ag = law.tables.zones.adjacent_ground
    assert ag.shore_profile_drop_m == 2.0
    assert ag.shore_profile_run_m == 10.0


# ── (1) DECLARED ─────────────────────────────────────────────────────────

def test_declared_tags_of_29a_are_walls(law):
    gentle = _ProfileDem(lambda d: 0.1 * d)
    for tags in ({"man_made": "embankment"}, {"man_made": "dyke"},
                 {"barrier": "retaining_wall"}):
        line = OsmWay(-1, "f", ((-300.0, -30.0), (300.0, -30.0)), False, tags)
        for r in _decide(law, gentle, shore_declarations((line,))):
            assert r.quay and r.shore.witness == "declared", tags


def test_reclaimed_land_is_a_declared_area(law):
    """``landuse=reclaimed`` is an AREA: the contact lies inside it."""
    ring = ((-400.0, -60.0), (400.0, -60.0), (400.0, 200.0), (-400.0, 200.0),
            (-400.0, -60.0))
    way = OsmWay(-4, "f", ring, True, {"landuse": "reclaimed"})
    decl = shore_declarations((way,))
    assert len(decl) == 1 and decl[0].geom_type == "Polygon"
    for r in _decide(law, _ProfileDem(lambda d: 0.0), decl):
        assert r.quay and r.shore.witness == "declared"


def test_declared_takes_precedence_over_a_natural_profile(law):
    line = OsmWay(-1, "f", ((-300.0, -30.0), (300.0, -30.0)), False,
                  {"man_made": "quay"})
    reach = _decide(law, _ProfileDem(lambda d: 0.25 * d),
                    shore_declarations((line,)))
    assert all(r.shore.witness == "declared" for r in reach)


# ── (2) A PACK WALL ──────────────────────────────────────────────────────

def _wall(y0: float, h: float = 3.1):
    return PackWall(Polygon(((-250.0, y0), (250.0, y0), (250.0, y0 + 0.6),
                             (-250.0, y0 + 0.6))), h, "fixture/wall.obj")


def test_a_pack_wall_along_the_shore_is_a_wall_at_its_height(law):
    # the wall's seaward face 0.3 m inland of the water line: within one
    # identity spacing (0.5 m)
    reach = _decide(law, _ProfileDem(lambda d: 0.1 * d),
                    walls=(_wall(Y_SHORE + 0.3),))
    for r in reach:
        assert r.quay and r.shore.witness == "pack_wall"
        assert r.shore.height_m == pytest.approx(3.1)


def test_a_pack_wall_away_from_the_shore_is_no_witness(law):
    reach = _decide(law, _ProfileDem(lambda d: 0.1 * d),
                    walls=(_wall(Y_SHORE + 5.0),))
    assert all(r.shore.witness == "profile" and r.natural_shore for r in reach)


# ── (3) THE PAVEMENT EDGE ON THE COASTLINE ───────────────────────────────

def test_the_pavement_edge_on_the_coast_is_a_wall(law):
    class _Near(_SeaDem):
        def z(self, x, y):
            return 0.0
    lip = [r for r in zone_regions(_zone_cells(), law, (), _Near(-22.0), ())
           if r.shore is not None and r.zone == 1]
    assert lip and all(r.quay and r.shore.witness == "pavement" for r in lip)


# ── (4) THE TERRAIN PROFILE ──────────────────────────────────────────────

def test_a_2m_step_within_10m_is_a_built_edge_at_that_height(law):
    for r in _decide(law, _ProfileDem(_step(2.0))):
        assert r.quay and r.shore.witness == "profile", r.shore
        assert r.shore.height_m == pytest.approx(2.0)


def test_a_1_in_4_fall_is_natural(law):
    """2.5 m over the 10 m run, but a bank would stand at it: natural."""
    for r in _decide(law, _ProfileDem(lambda d: 0.25 * d)):
        assert r.natural_shore and not r.quay
        assert r.shore.witness == "profile" and r.shore.gentle > 0


def test_a_profile_at_1_in_3_is_natural(law):
    for r in _decide(law, _ProfileDem(lambda d: d / 3.0)):
        assert r.natural_shore and r.shore.witness == "profile"


def test_a_steep_step_under_2m_is_no_witness(law):
    """Steeper than 1:3 but only 1.5 m: neither built nor gentle — the
    contact falls through to the default (a ``shore_undeclared`` row)."""
    for r in _decide(law, _ProfileDem(_step(1.5))):
        assert r.natural_shore and r.shore.witness == "default"
        assert r.shore.undeclared


def test_the_profile_reads_inland_not_seaward(law):
    """The stations read the LAND side of the water line: a step on the
    sea side is not a built edge."""
    water = _SeaDem().sea_geometry()
    contact = LineString(((-100.0, Y_SHORE), (100.0, Y_SHORE)))

    class _SeaStep(_SeaDem):
        def z(self, x, y):
            return 5.0 if y < Y_SHORE - 3.0 else 0.0
    n, built, gentle, _h = shore_profile(contact, water, _SeaStep(), law)
    assert n > 0 and built == 0 and gentle == n


# ── (5) DEFAULT ──────────────────────────────────────────────────────────

def test_no_dem_no_witness_is_natural_by_default(law):
    water = _SeaDem().sea_geometry()
    pav = Polygon(((-200, -20), (200, -20), (200, 120), (-200, 120)))
    part = Polygon(((-200, -30), (200, -30), (200, -20), (-200, -20)))
    v = shore_verdict(shore_contact(part, water, law), pavement=pav,
                      water=water, law=law)
    assert (v.kind, v.witness, v.undeclared) == ("natural", "default", True)


def test_a_level_platform_at_the_water_line_is_a_built_edge(law):
    """VMMC's class (measured, lane shoredecide): the flat-site inset holds
    the land at Z0 6.10 m right to the coastline, so the profile's drop is
    the fall from the platform TO THE WATER at the line — 6.1 m in the
    first metre — a wall at that height."""
    for r in _decide(law, _ProfileDem(lambda d: 6.1)):
        assert r.quay and r.shore.witness == "profile"
        assert r.shore.height_m == pytest.approx(6.1)
