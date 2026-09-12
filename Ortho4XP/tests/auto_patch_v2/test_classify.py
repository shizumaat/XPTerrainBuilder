"""M1 classifier twins: the rule table refuses bad values; a synthetic
airport exercises every verdict; the CYXY fixture's cells are registered
roles with the evidence recorded."""
from __future__ import annotations

import math
from pathlib import Path

import pytest
import shapely
from shapely.geometry import LineString, Polygon

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


# ── the bounded route territory (RULINGS 2026-09-05x, spec §6) ───────────

def _crossed_apron() -> Airport:
    """A 600 x 400 m apron crossed by two through taxi centrelines (x = 300
    and y = 200, each far longer than ``apron.through_min_len_m``), the
    runway 300 m away (its own proximity band never reaches the apron)."""
    frame = Frame("SYNT", (60.0, -135.0), 11)
    ends = (RunwayEnd("09", (0.0, -300.0), (60.0, -135.0), 0.0, 0.0, 100.0, "cifp"),
            RunwayEnd("27", (1000.0, -300.0), (60.0, -134.98), 0.0, 60.0, 100.0, "cifp"))
    rw = Runway("09/27", 30.0, Surface.ASPHALT, ends, 2, "C")
    pav = [Pavement("apron", Surface.ASPHALT, _rect(0.0, 0.0, 600.0, 400.0), ())]
    nodes = {1: TaxiNode(1, (0.0, 200.0), "both"), 2: TaxiNode(2, (300.0, 200.0), "both"),
             3: TaxiNode(3, (600.0, 200.0), "both"), 4: TaxiNode(4, (300.0, 0.0), "both"),
             5: TaxiNode(5, (300.0, 400.0), "both")}
    edges = (TaxiEdge(1, 2, "A", False, False, "C"), TaxiEdge(2, 3, "A", False, False, "C"),
             TaxiEdge(4, 2, "B", False, False, "C"), TaxiEdge(2, 5, "B", False, False, "C"))
    pack = SceneryPack("synthetic", "", "", (), ())
    return Airport("SYNT", "Synthetic", frame, 100.0, (rw,), tuple(pav), (), nodes,
                   edges, (), (), (), (), (), (), pack, _FlatDem(), "icao")


def test_crossed_apron_junction_is_the_bounded_route_territory(law):
    """The proximity contour (50 m of each centreline) would make 90,000 m²
    of the apron junction; the ruling bounds it to the routes' 25 m
    corridors — two 50 m corridors crossing, 47,500 m² — and the rest of
    every face is APRON, with the evidence recorded."""
    rules = load_rules()
    half = rules.junction.route_territory_half_width_m
    cl = classify(_crossed_apron(), law, rules)
    cells = [c for c in cl.cells if c.ref == "apron"]
    assert {c.role for c in cells} == {"apron", "junction"}
    axes = shapely.union_all([LineString([(0, 200), (600, 200)]),
                              LineString([(300, 0), (300, 400)])])
    corridor = axes.buffer(half, cap_style="flat")
    junction_area = sum(Polygon(c.ring, c.holes).area for c in cells if c.role == "junction")
    apron_area = sum(Polygon(c.ring, c.holes).area for c in cells if c.role == "apron")
    assert junction_area == pytest.approx(corridor.area, rel=0.01)          # 47,500 m²
    assert apron_area == pytest.approx(240_000.0 - corridor.area, rel=0.01)  # 192,500 m²
    for c in cells:
        poly = Polygon(c.ring, c.holes)
        if c.role == "junction":       # nothing beyond the corridor's edge
            assert poly.difference(corridor.buffer(0.05)).area < 1.0
            assert c.evidence["near_route"] == 1.0
            assert c.code_letter == "C"
        else:                          # nothing inside it
            assert poly.intersection(corridor.buffer(-0.05)).area < 1.0
            assert c.evidence["near_route"] == 0.0
        # the explain record: the territory's share of the contour on this
        # face, and the contour's apron remainder (a face's L-shaped 50 m band
        # is 22,500 m², its 25 m corridors 11,875 m²)
        assert c.evidence["territory_frac"] == pytest.approx(11_875 / 22_500, abs=0.02)
        assert c.evidence["apron_remainder_m2"] == pytest.approx(10_625.0, rel=0.02)


def test_route_territory_keeps_tight_pockets_and_returns_the_rest():
    """The helper on plain geometry: a corridor band through a face is
    territory; a remainder piece up to ``junction.max_area_m2`` (a pocket
    at an intersection) joins it; a bigger piece is apron remainder."""
    from shapely.geometry import box
    from auto_patch_v2.classify.roles import _route_territory
    rules = load_rules()
    band = box(0, 80, 1000, 120)                          # a 40 m corridor band
    wide = box(0, 0, 200, 200)                            # remainders 16,000 m² each
    terr, near, rem = _route_territory(wide, wide, band, rules)
    assert near == pytest.approx(40_000.0) and terr.area == pytest.approx(8_000.0)
    assert rem == pytest.approx(32_000.0)
    narrow = box(0, 0, 30, 200)                           # remainders 2,400 m² each: pockets
    assert 2_400.0 <= rules.junction.max_area_m2
    terr, near, rem = _route_territory(narrow, narrow, band, rules)
    assert terr.area == pytest.approx(6_000.0) and rem == 0.0
    # no contour on the face: no territory, nothing to report
    terr, near, rem = _route_territory(wide, box(500, 500, 600, 600), band, rules)
    assert terr.is_empty and near == 0.0 and rem == 0.0


# ── §27 an airside edge makes a lot airside (RULINGS 2026-09-12c/12e,
# ── roads and the mouth 2026-09-12f) ─────────────────────────────────────

def _lot_flip_case(final_extra, law=None, rules=None):
    """Run ``_airside_edge_flip`` over ``final_extra`` and give the roles
    back.  Entries are ``(role, ref, polygon, letter, evidence)`` exactly
    as ``classify``'s own final list."""
    from auto_patch_v2.classify.airside_edge import airside_edge_flip as _airside_edge_flip
    law = law or Law.for_airport("SYNT")
    rules = rules or load_rules()
    final = [list(t) + [str(t[4].get("kind", ""))] for t in final_extra]
    n, rounds = _airside_edge_flip(final, [], law, rules)
    return n, rounds, [f[0] for f in final], final


def test_airside_edge_flips_a_lot_with_a_long_apron_edge():
    """§27 (1): a lot running at least ``lot.airside_edge_min_m``
    laterally along airside pavement IS an apron, and its evidence
    records the metres."""
    from shapely.geometry import box
    rules = load_rules()
    assert rules.lot.airside_edge_min_m == 10.0
    apron = box(0, 0, 100, 100)
    lot = box(100, 0, 200, 100)               # 100 m of lateral shared edge
    far = box(400, 400, 500, 500)             # touches nothing
    n, rounds, roles, final = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("parking_lot", "pav2", lot, None, {"kind": "lot"}),
        ("parking_lot", "pav3", far, None, {"kind": "lot"}),
    ])
    assert n == 1 and rounds == 2 and roles == ["apron", "apron", "parking_lot"]
    assert final[1][4]["airside_edge_m"] >= 100.0
    assert final[1][4]["airside_edge_flip"] == 1.0
    assert final[1][4]["airside_edge_was"] == "parking_lot"
    # side is a pure function of role — no consumer edit (§27 (2))
    from auto_patch_v2.law.tables import role_side
    law = Law.for_airport("SYNT")
    assert role_side(law, final[1][0]) == "airside"
    assert role_side(law, final[2][0]) == "groundside"


def test_a_road_alongside_an_apron_flips_and_carries_the_lot_with_it():
    """§27 (5) (owner RULINGS 2026-09-12f): a service road running
    LATERALLY along an apron IS the apron (the free-road ruling), and the
    flip PROPAGATES — the lot on its far side is then beside apron.  The
    pass iterates to the fixpoint and says how many rounds it took."""
    from shapely.geometry import box
    road = box(0, 0, 10, 200)                 # a 10 m strip, 200 m long
    apron = box(10, 0, 110, 200)              # 200 m LATERAL along the road
    lot = box(-60, 0, 0, 200)                 # 200 m along the road's far side
    n, rounds, roles, final = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("service_road", "r1", road, None, {}),
        ("parking_lot", "pav2", lot, None, {"kind": "lot"}),
    ])
    assert roles == ["apron", "apron", "apron"] and n == 2
    # round 1 flips the road, round 2 the lot it exposed, round 3 stops
    assert rounds == 3
    assert final[1][4]["airside_edge_round"] == 1.0
    assert final[1][4]["airside_edge_was"] == "service_road"
    assert final[2][4]["airside_edge_round"] == 2.0


def test_a_mouth_keeps_a_shape_groundside():
    """§27 (5): the exemption is the SHAPE OF THE CONTACT, not the
    neighbour's role — a free road meeting the apron END-ON at its own
    mouth (the strip's end cap, transverse, at most
    ``lot.mouth_width_factor`` strip-widths) stays groundside, and so
    does the lot at the road's other mouth."""
    from shapely.geometry import box
    rules = load_rules()
    assert rules.lot.mouth_width_factor == 1.5
    road = box(0, 0, 10, 200)                 # 10 m wide, axis north
    apron = box(-100, -100, 100, 0)           # meets the road's SOUTH cap
    lot = box(-40, 200, 10, 300)              # meets the road's NORTH cap
    n, rounds, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("service_road", "r1", road, None, {}),
        ("parking_lot", "pav2", lot, None, {"kind": "lot"}),
    ])
    assert n == 0 and rounds == 1 and roles == ["apron", "service_road", "parking_lot"]
    # the SAME 10 m of contact laid LATERALLY is never a mouth: widen the
    # cap beyond the factor and the road flips
    wide = box(0, 0, 10, 200)
    apron2 = box(-100, -100, 100, 0)
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron2.union(box(10, 0, 100, 30)), None, {}),
        ("service_road", "r1", wide, None, {}),
    ])
    assert n == 1 and roles[1] == "apron"


def test_airside_edge_never_flips_a_sliver():
    """§27 (1): area / perimeter < 1 m is an emit artefact, never a face
    that flips — LEMD's `dsf:pol255#2` rings share 100+ m each."""
    from shapely.geometry import box
    from auto_patch_v2.classify.airside_edge import _LOT_SLIVER_RADIUS_M
    assert _LOT_SLIVER_RADIUS_M == 1.0
    apron = box(0, 0, 200, 100)
    sliver = box(0, 100, 200, 100.8)          # 200 m long, 0.8 m wide -> r ~ 0.4
    assert sliver.area / sliver.length < 1.0
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("parking_lot", "pav2", sliver, None, {"kind": "lot"}),
    ])
    assert n == 0 and roles[-1] == "parking_lot"
    fat = box(0, 100, 200, 103)               # r = 1.48: a real strip, flips
    assert fat.area / fat.length > 1.0
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("parking_lot", "pav2", fat, None, {"kind": "lot"}),
    ])
    assert n == 1 and roles[-1] == "apron"


def test_airside_edge_is_weld_tolerant():
    """§27 (1): the cells are PRE-WELD, so exact coincidence under-reads
    the edge the owner sees.  Measured at LEMD `pav137` (shapeID 81):
    95.0 m exact, 140.2 m in the emitted patch — the buffered measure at
    ``emit.identity.weld_spacing_m`` recovers it."""
    from shapely.geometry import box
    from shapely.strtree import STRtree
    from auto_patch_v2.classify.airside_edge import _lateral_airside_m
    law = Law.for_airport("SYNT")
    rules = load_rules()
    weld = float(law.tables.emit.identity.weld_spacing_m)
    f = float(rules.lot.mouth_width_factor)
    assert weld == 1.0
    apron = box(0, 0, 100, 100)
    gapped = box(100.6, 0, 200, 100)          # a 0.6 m gap the weld closes
    assert gapped.boundary.intersection(apron.boundary).length == 0.0
    tree = STRtree([apron])
    assert _lateral_airside_m(gapped, False, tree, [(apron, False)], weld,
                              f) == pytest.approx(100.0, abs=1.0)
    # ...and the same lot 3 m away — beyond the weld — reads nothing
    far = box(103.0, 0, 200, 100)
    assert _lateral_airside_m(far, False, tree, [(apron, False)], weld, f) == 0.0
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("parking_lot", "pav2", gapped, None, {"kind": "lot"}),
        ("parking_lot", "pav3", box(103.0, 200, 200, 300), None, {"kind": "lot"}),
    ])
    assert n == 1 and roles == ["apron", "apron", "parking_lot"]


def test_only_a_road_offers_a_mouth():
    """§27 (5): the exemption is "a FREE ROAD meeting it end-on".  Where
    neither face in contact is a road there is no mouth: a lot meeting an
    apron head-on across a short edge is a lateral contact and flips.
    And a road that ALREADY flipped still offers its mouth — the
    exemption follows the road's ORIGINAL role, not its current one."""
    from shapely.geometry import box
    # 20 m of contact, transverse to the lot's own axis, no road anywhere
    apron = box(0, 0, 200, 100)
    lot = box(0, 100, 20, 300)                # a 20 m wide finger, end-on
    n, _r, roles, final = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("parking_lot", "pav2", lot, None, {"kind": "lot"}),
    ])
    assert n == 1 and roles[-1] == "apron"
    assert final[1][4]["airside_edge_m"] == pytest.approx(21.0, abs=1.5)   # the weld band adds ~1 m at each corner
    # the same finger reaching the apron through a road's mouth stays
    road = box(0, 100, 20, 140)               # 20 m wide, 40 m long strip
    lot2 = box(0, 140, 20, 300)
    n, _r, roles, _ = _lot_flip_case([
        ("apron", "pav1", apron, None, {}),
        ("service_road", "r1", road, None, {}),
        ("parking_lot", "pav2", lot2, None, {"kind": "lot"}),
    ])
    assert n == 0 and roles == ["apron", "service_road", "parking_lot"]
