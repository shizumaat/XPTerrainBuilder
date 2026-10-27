"""Issue #1548 (LGAV ``dsf:pol171``): a pack pavement page a mapped
railway runs along, with no aircraft reach, is ground transport — never
``apron``.

The synthetic M1 airport (``test_classify._synthetic``) gains a 16 x 300 m
page meeting the apron END-ON at its north edge, no taxi centreline, no
startup, no mapped apron.  With no rail on it the page is AIRSIDE
pavement (LGAV's page reached ``apron`` through the §110 ribbon and §27's
end-on flip; here the touch-chain keeps it airside directly); with two
at-grade tracks along it the rail rung (``classify/sources.py``) reads it
a ``strip`` and it stays a groundside
``service_road``.  A railway in a tunnel or on a bridge is not what the
page carries and leaves the verdict alone.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.evidence import build_evidence  # noqa: E402
from auto_patch_v2.classify.sources import classify_sources  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import OsmWay, Pavement, Surface  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _rail_page_airport(**rail_tags):
    """The apron is x 300..700, y 300..500; the page runs north from its
    top edge.  ``rail_tags`` None-free: no tags -> no rail at all."""
    a = _synthetic(gate=True)
    page = Pavement("trackbed", Surface.ASPHALT, _rect(400.0, 500.0, 416.0, 800.0), ())
    ways = ()
    if rail_tags:
        ways = tuple(OsmWay(900 + k, "big_roads", ((x, 450.0), (x, 900.0)), False,
                            dict(rail_tags)) for k, x in enumerate((404.0, 412.0)))
    return _dc.replace(a, pavements=a.pavements + (page,),
                       osm_ways=a.osm_ways + ways)


def _page(cl):
    cells = [c for c in cl.cells if c.ref == "trackbed"]
    assert cells
    return cells


def _airside(cells) -> bool:
    return all(c.side == "airside" for c in cells)


def test_the_control_page_without_rail_is_airside(law):
    """The defect's shape: with nothing on it, the page is airside."""
    cells = _page(classify(_rail_page_airport(), law))
    assert _airside(cells), [(c.role, c.side) for c in cells]


def test_a_page_a_railway_runs_along_is_not_apron(law):
    a = _rail_page_airport(railway="rail")
    rules = load_rules()
    ev = build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2)
    rec = {r.id: r for r in classify_sources(a, ev, rules)[0]}["trackbed"]
    assert rec.cls == "strip" and rec.rail_m == pytest.approx(600.0), rec
    cells = _page(classify(a, law, rules))
    assert all(c.role == "service_road" and c.side == "groundside" for c in cells), \
        [(c.role, c.side, dict(c.evidence)) for c in cells]


@pytest.mark.parametrize("tags", [{"railway": "rail", "tunnel": "yes"},
                                  {"railway": "rail", "bridge": "yes"},
                                  {"railway": "abandoned"}])
def test_a_grade_separated_or_lifted_railway_is_no_evidence(law, tags):
    cells = _page(classify(_rail_page_airport(**tags), law))
    assert _airside(cells), [(c.role, c.side) for c in cells]


def test_a_taxi_centreline_on_the_page_outranks_the_rail(law):
    """Aircraft reach wins: a page a taxi centreline touches is never read
    by the rail rung."""
    from auto_patch_v2.model.airport import TaxiEdge, TaxiNode
    a = _rail_page_airport(railway="rail")
    nodes = dict(a.taxi_nodes)
    nodes[61] = TaxiNode(61, (408.0, 400.0), "both")
    nodes[62] = TaxiNode(62, (408.0, 780.0), "both")
    a = _dc.replace(a, taxi_nodes=nodes, taxi_edges=a.taxi_edges + (
        TaxiEdge(5, 61, "R", False, False, "C"), TaxiEdge(61, 62, "R", False, False, "C")))
    rules = load_rules()
    ev = build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2)
    rec = {r.id: r for r in classify_sources(a, ev, rules)[0]}["trackbed"]
    assert rec.cls == "open", rec
