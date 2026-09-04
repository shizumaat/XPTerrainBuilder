"""THE TAXI-NAME RULE (RULINGS 2026-09-04z(1); ``rules.taxi_name``): an
apt.dat 110 description naming a taxiway is taxi evidence — the page is
``junction`` even without a 1202 centreline, never a lot; a page with a
centreline keeps its corridor role; a startup on the face keeps apron;
the editor's default "New Taxiway N" names nothing; an apron name is
senior ("Taxiway E apron"); "Aeronaval" is not a taxiway name.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.evidence import build_evidence, taxi_name_match  # noqa: E402
from auto_patch_v2.classify.explain import explain_polygon  # noqa: E402
from auto_patch_v2.classify.sources import classify_sources  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import GroundRoute, Pavement, Surface, TaxiNode  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _page_airport(description: str, reach: bool = True):
    """A 200 x 75 m page on the runway's south edge (chain seed) with no
    centreline and no startup, a route ending at its east boundary (the
    04u lot reading), described as ``description``."""
    a = _synthetic(gate=True, island=False)
    page = Pavement("page", Surface.ASPHALT, _rect(600.0, -90.0, 800.0, -15.0), (),
                    description)
    a = _dc.replace(a, pavements=a.pavements + (page,))
    if reach:
        nodes = dict(a.taxi_nodes)
        nodes[40] = TaxiNode(40, (900.0, -50.0), "both")
        nodes[41] = TaxiNode(41, (800.0, -50.0), "both")
        a = _dc.replace(a, taxi_nodes=nodes,
                        ground_routes=a.ground_routes + (GroundRoute(40, 41, "truck", False),))
    return a


def _page_roles(cl):
    return {c.role: round(Polygon(c.ring, c.holes).area)
            for c in cl.cells if c.ref.split("#")[0] == "page"}


def test_matcher(rules):
    assert rules.taxi_name.tokens and rules.taxi_name.unauthored_names
    assert taxi_name_match("Taxiway B", rules) == ("taxiway", "B")
    assert taxi_name_match("TWY A1", rules) == ("twy", "A1")
    assert taxi_name_match("Taxiway V / U / Q", rules) == ("taxiway", "V")
    # the editor's default names nothing; a suffix beyond a number is authored
    assert taxi_name_match("New Taxiway 2", rules) is None
    assert taxi_name_match("New Taxiway", rules) is None
    # the apron name is senior (03j: a "Taxiway E apron" is an apron)
    assert taxi_name_match("Taxiway E apron", rules) is None
    # not a taxiway name: SPJC's naval-aviation pavement, a ramp, a plural
    assert taxi_name_match("Aeronaval", rules) is None
    assert taxi_name_match("Naval Aviation Ramp", rules) is None
    assert taxi_name_match("taxiways", rules) is None


def test_named_page_without_centreline_is_a_junction(law, rules):
    a = _page_airport("Taxiway K")
    ev = build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2)
    rec = {r.id: r for r in classify_sources(a, ev, rules)[0]}["page"]
    assert rec.taxi_name == "taxiway" and rec.taxi_designator == "K"
    assert rec.cls == "open" and "taxi by name" in rec.reason and rec.road_reach == 1
    cl = classify(a, law, rules)
    roles = _page_roles(cl)
    assert set(roles) == {"junction"}, roles
    cells = [c for c in cl.cells if c.ref == "page"]
    assert all(c.side == "airside" and c.evidence["taxi_name"] == "taxiway"
               and c.evidence["taxi_name_designator"] == "K" for c in cells)
    assert cl.stats["taxi_named"] >= 1
    # explain shows the token match
    text = "\n".join(explain_polygon(Polygon(_rect(600.0, -90.0, 800.0, -15.0)), cl, ev, a))
    assert "TAXI NAME 'taxiway' designator K (04z-1)" in text and "taxi_name=taxiway" in text


def test_default_name_and_aeronaval_stay_lots(law, rules):
    for desc in ("New Taxiway 7", "Aeronaval"):
        cl = classify(_page_airport(desc), law, rules)
        roles = _page_roles(cl)
        assert "parking_lot" in roles and "junction" not in roles, (desc, roles)
        assert not cl.stats.get("taxi_named")


def test_named_page_with_centreline_keeps_the_corridor_role(law, rules):
    """The synthetic parallel taxiway named "Taxiway P": still the
    primary parallel corridor at the chain's letter."""
    a = _synthetic(gate=True)
    pav = tuple(_dc.replace(p, description="Taxiway P") if p.id == "parallel" else p
                for p in a.pavements)
    a = _dc.replace(a, pavements=pav)
    cl = classify(a, law, rules)
    base = classify(_synthetic(gate=True), law, rules)
    roles = lambda c: sorted((x.role, x.ref, round(Polygon(x.ring, x.holes).area)) for x in c.cells)
    assert roles(cl) == roles(base)
    par = [c for c in cl.cells if c.ref == "parallel"]
    assert par and all(c.role == "primary_parallel" and c.code_letter == "D" for c in par)
    assert not cl.stats.get("taxi_named")


def test_named_page_with_a_startup_keeps_apron(law, rules):
    """A named page holding a stand is apron (the startup is face evidence
    above the name); the apron-named page is untouched."""
    from auto_patch_v2.model.airport import Startup
    a = _page_airport("Taxiway K", reach=False)
    a = _dc.replace(a, startups=a.startups + (Startup("S9", (700.0, -70.0), 0.0, "gate"),))
    cl = classify(a, law, rules)
    roles = _page_roles(cl)
    assert "apron" in roles and "junction" in roles, roles      # band + body
    body = [c for c in cl.cells if c.ref == "page" and c.role == "apron"]
    assert body and all("taxi_name" not in c.evidence for c in body)
