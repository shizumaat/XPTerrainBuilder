"""M1 classifier twins: the rule table refuses bad values; a synthetic
airport exercises every verdict; the CYXY fixture's cells are registered
roles with the evidence recorded."""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport.dem import DemSampler
from auto_patch_v2.airport.load import load
from auto_patch_v2.classify import (Classification, RulesError, classify,
                                    load_rules)
from auto_patch_v2.classify.evidence import chains_from_edges
from auto_patch_v2.classify.roles import TAXI_FAMILY
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Building, GroundRoute,
                                         Pavement, Runway, RunwayEnd,
                                         SceneryPack, Startup, Surface,
                                         TaxiEdge, TaxiNode)
from auto_patch_v2.model.frame import Frame

from test_airport_load import fixture_inputs

RULES = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2" / "classify" / "rules.toml"


# ── the rule table ───────────────────────────────────────────────────────

def test_rules_load_and_refuse(tmp_path):
    r = load_rules()
    assert r.corridor.max_width_m == 50.0 and r.apron.route_proximity_m == 50.0
    assert r.surfaces.graded_codes == (1, 2, 3, 4, 5, 12, 14)
    text = RULES.read_text()
    bad = tmp_path / "r.toml"
    bad.write_text(text.replace("max_width_m = 50.0", "max_width_m = 50.0\nbogus = 1"))
    with pytest.raises(RulesError, match="unknown"):
        load_rules(bad)
    bad.write_text(text.replace("max_width_m = 50.0", "max_width_m = -1"))
    with pytest.raises(RulesError, match="negative"):
        load_rules(bad)
    bad.write_text(text.replace("[corridor]\nmax_width_m = 50.0", "[corridor]"))
    with pytest.raises(RulesError, match="missing"):
        load_rules(bad)
    bad.write_text(text.replace("requires_terminal = true", "requires_terminal = 1"))
    with pytest.raises(RulesError, match="bool"):
        load_rules(bad)


# ── a synthetic airport ──────────────────────────────────────────────────

class _FlatDem:
    provenance = {"base": "synthetic"}

    def z(self, x: float, y: float) -> float:
        return 100.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _synthetic(gate: bool, island: bool = True) -> Airport:
    """Runway along x from (0,0) to (1000,0), 30 m wide; a taxiway strip
    20 m wide from the runway edge north through a parallel taxiway
    (y = 100..125) to an apron 400 x 200 m at y = 300..500; a detached
    pavement island; a building on the apron; a truck route on open
    ground; a 60 m lead-in lane onto a stand."""
    frame = Frame("SYNT", (60.0, -135.0), 11)
    ends = (RunwayEnd("09", (0.0, 0.0), (60.0, -135.0), 0.0, 0.0, 100.0, "cifp"),
            RunwayEnd("27", (1000.0, 0.0), (60.0, -134.98), 0.0, 60.0, 100.0, "cifp"))
    rw = Runway("09/27", 30.0, Surface.ASPHALT, ends, 2, "C")
    pav = [Pavement("taxi", Surface.ASPHALT, _rect(490.0, 15.0, 510.0, 300.0), ()),
           Pavement("parallel", Surface.ASPHALT, _rect(100.0, 100.0, 900.0, 125.0), ()),
           Pavement("apron", Surface.ASPHALT, _rect(300.0, 300.0, 700.0, 500.0), ()),
           Pavement("water", Surface.WATER, _rect(700.0, 300.0, 750.0, 350.0), ())]
    if island:
        pav.append(Pavement("island", Surface.CONCRETE, _rect(800.0, 300.0, 900.0, 400.0), ()))
    nodes = {1: TaxiNode(1, (500.0, 0.0), "both"), 2: TaxiNode(2, (500.0, 15.0), "both"),
             7: TaxiNode(7, (500.0, 112.5), "both"),
             3: TaxiNode(3, (500.0, 300.0), "both"), 4: TaxiNode(4, (500.0, 330.0), "both"),
             5: TaxiNode(5, (500.0, 500.0), "both"), 6: TaxiNode(6, (560.0, 330.0), "both"),
             20: TaxiNode(20, (100.0, 112.5), "both"), 21: TaxiNode(21, (900.0, 112.5), "both"),
             10: TaxiNode(10, (300.0, -200.0), "both"), 11: TaxiNode(11, (300.0, 200.0), "both")}
    edges = (TaxiEdge(1, 2, "A", False, False, "C"), TaxiEdge(2, 7, "A", False, False, "C"),
             TaxiEdge(7, 3, "A", False, False, "C"), TaxiEdge(3, 4, "A", False, False, "C"),
             TaxiEdge(4, 5, "A", False, False, "C"),
             TaxiEdge(4, 6, "", False, False, "C"),        # a 60 m lead-in onto the stand
             TaxiEdge(20, 7, "P", False, False, "D"), TaxiEdge(7, 21, "P", False, False, "D"))
    routes = (GroundRoute(10, 11, "truck", False),)
    starts = (Startup("Stand 1", (565.0, 335.0), 0.0, "gate" if gate else "tie_down"),)
    bld = (Building("b1", _rect(320.0, 440.0, 380.0, 490.0), (), "osm", None, None),)
    pack = SceneryPack("synthetic", "", "", (), ())
    return Airport("SYNT", "Synthetic", frame, 100.0, (rw,), tuple(pav), (), nodes,
                   edges, routes, (), starts, (), bld, (), pack, _FlatDem(), "icao")


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _roles(cl: Classification):
    return {(c.role, c.ref): Polygon(c.ring, c.holes).area for c in cl.cells}


def test_synthetic_verdicts(law):
    cl = classify(_synthetic(gate=True), law)
    roles = _roles(cl)
    names = {r for r, _ in roles}
    assert "runway" in names and "runway_crossing" not in names
    # the parallel taxiway's halves are corridors named PRIMARY parallel
    # (112 m off the runway); the connector strips merge into them (one
    # pavement union, cut only by the routes) — the same slice model as v1
    assert "primary_parallel" in names
    # the apron body beyond 50 m of the route is apron; the band nearer is junction
    assert "apron" in names and "junction" in names
    assert roles[("apron", "apron")] > roles[("junction", "apron")] > 0
    # the detached island is landside at a gate airport
    assert ("groundside_pavement", "island") in roles
    # the lead-in onto the stand (4 -> 6, 60 m, leaf, near the startup) was
    # trimmed from the slice: no taxi cut inside the apron reaches x > 540
    assert not any(ln.kind == "taxi_centerline"
                   and any(x > 540 and y > 300 for x, y in ln.points)
                   for ln in cl.cut_lines)
    # corridor halves are half a strip wide (area / shared edge)
    assert all(e["width_m"] < 15 for e in
               (c.evidence for c in cl.cells if c.role == "primary_parallel"))
    assert all(c.code_letter == "D" for c in cl.cells if c.role == "primary_parallel")
    # the water pavement is not graded, the building is a pad, the truck route a road
    assert not any(ref == "water" for _r, ref in roles)
    assert ("building", "building1") in roles
    assert any(r == "service_road" for r, _ in roles)
    # every cell is a registered role with a census side
    for c in cl.cells:
        assert c.side in ("airside", "groundside")
        assert c.role in law.tables.precedence.roles
    assert cl.stats["terminal_present"] == 1.0


def test_synthetic_no_terminal_keeps_islands_airside(law):
    cl = classify(_synthetic(gate=False), law)
    roles = _roles(cl)
    assert ("apron", "island") in roles
    assert not any(r == "groundside_pavement" for r, _ in roles)
    assert cl.stats["terminal_present"] == 0.0


def test_chains_split_at_junctions_and_runway_contacts():
    nodes = {1: (0.0, 0.0), 2: (10.0, 0.0), 3: (20.0, 0.0), 4: (20.0, 10.0), 5: (30.0, 0.0)}
    edges = [(1, 2, "C", "A"), (2, 3, "C", "A"), (3, 4, "B", "B"), (3, 5, "C", "A")]
    chains = chains_from_edges(nodes, edges, {1}, False)
    assert len(chains) == 3                      # 1-2-3 | 3-4 | 3-5
    main = max(chains, key=lambda c: c.line.length)
    assert main.letter == "C" and main.runway_contact[0] and main.end_degree[1] == 3
    assert {c.letter for c in chains} == {"B", "C"}


# ── the CYXY fixture ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cyxy_cl():
    law = Law.for_airport("CYXY")
    a = load("CYXY", fixture_inputs(), law)
    return a, law, classify(a, law)


def test_cyxy_cells(cyxy_cl):
    a, law, cl = cyxy_cl
    refs = {(c.role, c.ref) for c in cl.cells}
    assert {r for r, ref in refs if r == "runway"} and \
        {ref for r, ref in refs if r == "runway"} == {"02/20", "14L/32R", "14R/32L"}
    assert {ref for r, ref in refs if r == "runway_crossing"} == \
        {"02/20+14L/32R", "02/20+14R/32L"}
    assert sum(1 for c in cl.cells if c.role in TAXI_FAMILY) >= 10
    assert all(c.code_letter in ("A", "B", "C", "D", "E", "F", None)
               for c in cl.cells)
    assert any(c.role in TAXI_FAMILY and c.code_letter for c in cl.cells)
    assert any(c.role == "building" for c in cl.cells)
    assert any(c.role == "groundside_pavement" for c in cl.cells)  # CYXY has a terminal
    assert {cl_.kind for cl_ in cl.cut_lines} >= {"taxi_centerline", "road_centerline"}
    for c in cl.cells:
        assert c.role in law.tables.precedence.roles, c.role
        assert c.side == law.tables.precedence.roles[c.role].side
        assert Polygon(c.ring, c.holes).is_valid
    total = sum(Polygon(c.ring, c.holes).area for c in cl.cells
                if c.role not in ("building", "service_road"))
    assert 700_000 < total < 850_000        # apt.dat + DSF pages less pads
    assert cl.stats["dsf_pavements_kept"] if "dsf_pavements_kept" in cl.stats else True
    evid = [c.evidence for c in cl.cells if c.kind == "corridor"]
    assert evid and all("width_m" in e for e in evid)
    assert math.isfinite(sum(e["width_m"] for e in evid))
