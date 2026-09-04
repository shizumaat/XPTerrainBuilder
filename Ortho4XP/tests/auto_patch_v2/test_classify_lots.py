"""Owner 2026-09-04j (CYXY sim read, lane v2class) as four synthetic
twins over the M1 synthetic airport (``test_classify._synthetic``):

1. a road strip entering a parking lot -> TWO faces (service_road at
   the road law, parking_lot at 5 %), cut at the mouth (the lot's
   boundary), the planar map still T-vertex free;
2. an apron with an adjacent lot page -> apron and parking_lot, never
   one face;
3. apron mis-evidence (a corridor-shaped, apron-NAMED pavement with a
   taxi lane along it) -> apron, not a corridor;
4. taxiway mis-evidence (a detached page a NETWORK taxiway runs onto,
   no pavement touch-chain) -> the taxi family, not groundside.

Plus the register: ``parking_lot`` in both law tables and its oracle
alias in the emitted way tags.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.classify import classify, load_rules  # noqa: E402
from auto_patch_v2.classify.evidence import build_evidence  # noqa: E402
from auto_patch_v2.classify.sources import classify_sources  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.law.tables import role_cap, role_side  # noqa: E402
from auto_patch_v2.model.airport import (OsmWay, Pavement, Startup, Surface,  # noqa: E402
                                         TaxiEdge, TaxiNode)
from auto_patch_v2.planar.build import build as planar_build  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cells(cl):
    return [(c.role, c.ref, Polygon(c.ring, c.holes).area, c) for c in cl.cells]


def _way(wid: int, pts, **tags) -> OsmWay:
    return OsmWay(wid, "airport_small_roads", tuple(pts), False, dict(tags))


# ── 1. road strip into a lot: two faces, cut at the mouth ───────────────

def _lot_airport():
    """Landside, west of the runway: a 60 x 80 m lot page with three
    dead-end aisles, entered from the south by an 8 m x 120 m road strip
    carrying an OSM service road that runs on into the lot."""
    a = _synthetic(gate=True)
    lot = Pavement("lot", Surface.ASPHALT, _rect(-400.0, 200.0, -340.0, 280.0), ())
    strip = Pavement("strip", Surface.ASPHALT, _rect(-374.0, 80.0, -366.0, 200.0), ())
    road = _way(1, [(-370.0, 60.0), (-370.0, 200.0), (-370.0, 270.0)], highway="service")
    aisles = [_way(10 + k, [(-370.0, y), (-345.0, y)], highway="service")
              for k, y in enumerate((220.0, 240.0, 260.0))]
    return _dc.replace(a, pavements=a.pavements + (lot, strip),
                       osm_ways=a.osm_ways + (road, *aisles))


def test_road_strip_and_lot_are_two_faces_cut_at_the_mouth(law):
    a = _lot_airport()
    rules = load_rules()
    ev = build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2)
    recs = {r.id: r for r in classify_sources(a, ev, rules)[0]}
    assert recs["strip"].cls == "strip", recs["strip"]
    assert recs["lot"].cls == "lot", recs["lot"]
    assert recs["lot"].road_pieces >= 3            # the aisle grid, not one road
    cl = classify(a, law, rules)
    cells = _cells(cl)
    roads = [c for c in cells if c[1] == "strip"]
    lots = [c for c in cells if c[1] == "lot"]
    assert [c[0] for c in roads] == ["service_road"], roads
    assert [c[0] for c in lots] == ["parking_lot"], lots
    assert abs(roads[0][2] - 8.0 * 120.0) < 1.0 and abs(lots[0][2] - 60.0 * 80.0) < 1.0
    # the mouth: the road face ends at the lot's boundary (y = 200)
    assert max(y for _x, y in roads[0][3].ring) <= 200.0 + 1e-6
    assert min(y for _x, y in lots[0][3].ring) >= 200.0 - 1e-6
    # the aisles inside the lot did not cut it: one lot face
    assert len(lots) == 1
    # sides and caps from the register
    assert roads[0][3].side == "groundside" and lots[0][3].side == "groundside"
    assert role_cap(law, "parking_lot").longitudinal == pytest.approx(0.05)
    assert role_cap(law, "service_road").longitudinal == pytest.approx(0.08)
    # evidence is recorded per face
    assert lots[0][3].evidence["source_class"] == "lot"
    assert roads[0][3].evidence["source_class"] == "strip"
    # the planar map stays a partition with no T-vertex
    _pm, stats = planar_build(a, cl, law)
    assert stats.t_vertices == 0


# ── 2. apron + adjacent lot page: two faces ───────────────────────────────

def _apron_lot_airport():
    """A lot page (OSM service road inside, no taxi centreline, no
    startup) touching the apron's west edge."""
    a = _synthetic(gate=True)
    lot = Pavement("lotpage", Surface.ASPHALT, _rect(240.0, 320.0, 300.0, 400.0), ())
    road = _way(2, [(250.0, 330.0), (290.0, 330.0), (290.0, 390.0)], highway="service")
    return _dc.replace(a, pavements=a.pavements + (lot,), osm_ways=a.osm_ways + (road,))


def test_apron_never_absorbs_an_adjacent_lot(law):
    a = _apron_lot_airport()
    cl = classify(a, law)
    cells = _cells(cl)
    lots = [c for c in cells if c[0] == "parking_lot"]
    assert [c[1] for c in lots] == ["lotpage"], lots
    assert abs(lots[0][2] - 60.0 * 80.0) < 1.0
    # the apron kept its own face(s) and none of them reaches into the lot
    aprons = [c for c in cells if c[0] == "apron"]
    assert aprons
    for _r, _ref, _a, c in aprons:
        assert not Polygon(c.ring, c.holes).intersection(
            Polygon(_rect(240.0, 320.0, 300.0, 400.0))).area > 1.0


# ── 3. apron mis-evidence: an apron by name is never a corridor ──────────

def _named_apron_airport(name: str):
    """A 30 m x 300 m pavement east of the parallel taxiway with a
    network taxi lane along its axis — corridor-shaped; ``name`` is the
    apt.dat description."""
    a = _synthetic(gate=True)
    pav = Pavement("named", Surface.ASPHALT, _rect(600.0, 140.0, 900.0, 170.0), (), name)
    nodes = dict(a.taxi_nodes)
    nodes[30] = TaxiNode(30, (610.0, 155.0), "both")
    nodes[31] = TaxiNode(31, (890.0, 155.0), "both")
    # joined to the NETWORK at node 21 (the parallel's east end)
    edges = a.taxi_edges + (TaxiEdge(21, 31, "S", False, False, "C"),
                            TaxiEdge(31, 30, "S", False, False, "C"))
    starts = a.startups + (Startup("Stand 9", (750.0, 160.0), 0.0, "tie_down"),)
    return _dc.replace(a, pavements=a.pavements + (pav,), taxi_nodes=nodes,
                       taxi_edges=edges, startups=starts)


def test_apron_by_name_is_apron_not_corridor(law):
    named = classify(_named_apron_airport("GA Apron"), law)
    roles = {c.role for c in named.cells if c.ref == "named"}
    assert roles and roles <= {"apron", "junction"}, roles      # junction = the proximity band
    assert any(c.evidence.get("apron_named") == 1.0 for c in named.cells if c.ref == "named")
    # the same geometry named a taxiway reads as the corridor it is shaped like
    taxi = classify(_named_apron_airport("Taxiway S"), law)
    roles = {c.role for c in taxi.cells if c.ref == "named"}
    assert roles & {"primary_parallel", "secondary_parallel", "cross_connector", "stub"}, roles


# ── 4. taxiway mis-evidence: a network taxiway makes its page airside ────

def _detached_page_airport():
    """A page 20 m clear of every other pavement (no touch-chain) that a
    network taxiway (joined to the parallel) runs onto."""
    a = _synthetic(gate=True)
    page = Pavement("page", Surface.ASPHALT, _rect(700.0, 145.0, 800.0, 200.0), ())
    nodes = dict(a.taxi_nodes)
    nodes[41] = TaxiNode(41, (750.0, 145.0), "both")      # the page's south edge
    nodes[42] = TaxiNode(42, (750.0, 195.0), "both")
    # joined to the NETWORK at node 21 (the parallel's east end), across the gap
    edges = a.taxi_edges + (TaxiEdge(21, 41, "T", False, False, "C"),
                            TaxiEdge(41, 42, "T", False, False, "C"))
    return _dc.replace(a, pavements=a.pavements + (page,), taxi_nodes=nodes,
                       taxi_edges=edges)


def test_network_taxiway_makes_a_detached_page_airside(law):
    cl = classify(_detached_page_airport(), law)
    page = [c for c in cl.cells if c.ref == "page"]
    assert page
    assert all(c.side == "airside" for c in page), [(c.role, c.side) for c in page]
    assert all(c.role != "groundside_pavement" and c.role != "parking_lot" for c in page)
    # the detached island with NO taxiway on it is still landside (M1 law)
    assert any(c.role == "groundside_pavement" and c.ref == "island" for c in cl.cells)


# ── the register and the oracle alias ───────────────────────────────────

def test_parking_lot_registered_and_aliased(law):
    spec = law.tables.precedence.roles["parking_lot"]
    assert spec.side == "groundside" and spec.family == "common" and spec.value
    assert spec.oracle_role == "groundside_pavement"
    assert role_side(law, "parking_lot") == "groundside"
    assert law.tables.precedence.order[-1] == "parking_lot"
    cap = law.tables.common.roles["parking_lot"]
    assert cap.longitudinal == pytest.approx(0.05) and cap.transverse == pytest.approx(0.02)


def test_emitted_way_carries_the_oracle_alias(law, tmp_path):
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.emit.osm_adapter import render_patch
    a = _lot_airport()
    cl = classify(a, law)
    pm, _stats = planar_build(a, cl, law)
    from auto_patch_v2.solve.api import Solution, Status
    n = max(pm.vertices) + 1
    sol = Solution(z=tuple([100.0] * n), status=Status.OPTIMAL, residual=None)
    surface = graded_surface(pm, law, sol, a.frame.origin)
    text, _n_ways, _n_nodes = render_patch(surface, law)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text)
    lots = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if tags.get("class") == "parking_lot":
            lots.append(tags)
    assert lots, "no aliased parking_lot way emitted"
    for tags in lots:
        assert tags["role"] == "groundside_pavement"       # the oracle's partition + 8 % base
        assert float(tags["o4_grade_law_cap"]) == pytest.approx(0.05)  # composed as a minimum: 5 %
    assert not any(t.get("v") == "parking_lot" for w in root.iter("way")
                   for t in w.findall("tag") if t.get("k") == "role")
