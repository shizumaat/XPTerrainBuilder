"""Twins of #2111 R2 (spec ``Ortho4XP/docs/specs/2111-R2.md``): A RUNWAY
END AREA ENDS AT THE FIRST BARRIER ACROSS IT (``planar/end_barriers``,
read by ``planar/zones.zone_regions``).

The test case was KBNA 31: the 304.8 m end area ran across the jet-blast
shield, both perimeter fences and the bank behind them, and the public
road there took the band's ceiling.  The twins hold the general rule: a
tall pack line across the extended centreline ends zones 1 and 2 at its
far face; a road behind it yields to no band; a short line beside the
centreline, or a low guardrail, ends nothing."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import EdgeLine, OsmWay
from auto_patch_v2.planar.end_barriers import end_barriers
from auto_patch_v2.planar.road_yield import road_carriageways, rsa_carriageways
from auto_patch_v2.planar.terrain_edge import EdgeReport
from auto_patch_v2.planar.zones import zone_regions
from shapely.ops import unary_union

RULES = load_rules()
RUNWAYS = (("09/27", (-1000.0, 0.0), (1000.0, 0.0), 30.0),)


@pytest.fixture(scope="module")
def faa():
    return Law.load(ruleset="faa")


def _cells():
    ring = ((-1000.0, -15.0), (1000.0, -15.0), (1000.0, 15.0), (-1000.0, 15.0))
    return (Cell(0, "runway", "09/27", ring, (), 4, "D", "airside", "runway", {}),)


def _line(pts, top=4.0, hw=0.3, lid="dsf:line0"):
    return EdgeLine(lid, "lib/jet_def.fac", tuple(pts), False, 0.0, top, top, 0.9, hw)


def _barriers(*lines):
    return end_barriers(lines, RULES.service, float(RULES.edge_lines.min_run_m))


def _zones(law, lines=(), ways=(), rep=None, yields=None):
    return zone_regions(_cells(), law, runways=RUNWAYS, edge_report=rep,
                        carriageways=road_carriageways(ways, law), yields=yields,
                        rsa_carriageways=rsa_carriageways(ways, law),
                        end_barriers=_barriers(*lines))


def _extent(regs, zone=2):
    return unary_union([r.polygon for r in regs if r.zone == zone]).bounds


WALL = ((1100.0, -100.0), (1100.0, 100.0))   # 100 m past the 27 end, across it


def test_a_wall_across_the_end_ends_the_band_at_its_far_face(faa):
    rep = EdgeReport()
    x0, _y0, x1, _y1 = _extent(_zones(faa, (_line(WALL),), rep=rep))
    assert x1 == pytest.approx(1100.3, abs=0.01)          # the far face
    assert x0 == pytest.approx(-1304.8, abs=0.01)         # the other end untouched
    assert rep.end_barriers == 1
    assert rep.end_barrier_cut_m2 == pytest.approx(204.5 * 152.4, rel=0.01)


def test_a_road_behind_the_barrier_yields_to_no_band(faa):
    road = OsmWay(1, "big_roads", ((1200.0, -300.0), (1200.0, 300.0)), False,
                  {"highway": "secondary"})
    open_, cut = [], []
    _zones(faa, (), (road,), yields=open_)
    _zones(faa, (_line(WALL),), (road,), yields=cut)
    assert any(y.through and y.runway_ref == "09/27" for y in open_)
    assert not any(y.through for y in cut)


def test_a_short_line_off_the_centreline_cuts_nothing(faa):
    beside = _line(((1100.0, 20.0), (1100.0, 60.0)))
    assert _extent(_zones(faa, (beside,))) == pytest.approx(_extent(_zones(faa)))


def test_a_low_guardrail_cuts_nothing(faa):
    rail = _line(WALL, top=0.8)
    assert _barriers(rail).lines == ()
    assert _extent(_zones(faa, (rail,))) == pytest.approx(_extent(_zones(faa)))
