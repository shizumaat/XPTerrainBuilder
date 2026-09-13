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
    """The lot page keeps ITS OWN FACE, cut at its own boundary — no
    apron cell reaches into it (owner 2026-09-04j).

    Its ROLE moved on 2026-09-12: this page shares its whole 80 m west
    edge with the apron, so §27 (RULINGS 2026-09-12c) makes that face
    `apron`.  What the cut guarantees is unchanged and is what this twin
    pins: the face is the LOT PAGE's own, at the lot page's own extent,
    never a lobe of the apron's cell."""
    a = _apron_lot_airport()
    cl = classify(a, law)
    cells = _cells(cl)
    page = [c for c in cells if c[1] == "lotpage"]
    assert len(page) == 1 and abs(page[0][2] - 60.0 * 80.0) < 1.0
    assert page[0][0] == "apron"                     # §27: the airside edge
    ev = page[0][3].evidence
    assert ev.get("airside_edge_flip") == 1.0 and ev.get("airside_edge_was") == "parking_lot"
    # no OTHER apron face reaches into the lot page's rectangle
    for _r, _ref, _a, c in cells:
        if _ref == "lotpage" or _r != "apron":
            continue
        assert not Polygon(c.ring, c.holes).intersection(
            Polygon(_rect(240.0, 320.0, 300.0, 400.0))).area > 1.0
    # ...and a lot page that touches NO airside pavement is still a lot
    far = _dc.replace(a, pavements=a.pavements[:-1] + (
        Pavement("lotfar", Surface.ASPHALT, _rect(-400.0, 320.0, -340.0, 400.0), ()),))
    roles = {c.ref: c.role for c in classify(far, law).cells}
    assert roles.get("lotfar") in ("parking_lot", "groundside_pavement"), roles


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


# ── 5. a MAPPED APRON refuses the lot verdict (owner RULINGS 2026-09-11ac
#      item 6: LEMD shapeID 83 / pav126) ─────────────────────────────────

def _mapped_apron_lot_airport(apron_fraction: float):
    """The §2 lot page again — an OSM service road inside, no taxi
    centreline, no startup — with an OSM ``aeroway=apron`` polygon over
    ``apron_fraction`` of its area.  LEMD's ``pav126`` is this page at
    25 %: a real apron the pack draws as one 43,000 m2 concrete page that
    a service road crosses, shipped ``parking_lot`` because 25 % missed
    the old 50 % majority test."""
    a = _apron_lot_airport()                     # lotpage = _rect(240, 320, 300, 400)
    y1 = 320.0 + 80.0 * apron_fraction
    apron = OsmWay(3, "airports", _rect(240.0, 320.0, 300.0, y1) + ((240.0, 320.0),),
                   True, {"aeroway": "apron"})
    return _dc.replace(a, osm_ways=a.osm_ways + (apron,))


def test_a_mapped_apron_refuses_the_lot_verdict(law):
    rules = load_rules()
    pad_min = law.tables.structures.building_pad.min_area_m2
    # 25 % apron: under the veto's own floor the page is no longer a lot
    a = _mapped_apron_lot_airport(0.25)
    ev = build_evidence(a, rules, pad_min)
    rec = {r.id: r for r in classify_sources(a, ev, rules)[0]}["lotpage"]
    assert rec.apron_cover == pytest.approx(0.25, abs=0.02), rec.apron_cover
    assert rec.cls == "open", rec
    assert not any(c.role == "parking_lot" and c.ref == "lotpage"
                   for c in classify(a, law, rules).cells)
    # ...and with NO mapped apron the very same page is still the lot it was
    b = _apron_lot_airport()
    evb = build_evidence(b, rules, pad_min)
    recb = {r.id: r for r in classify_sources(b, evb, rules)[0]}["lotpage"]
    assert recb.apron_cover == 0.0 and recb.cls == "lot", recb


def test_one_apron_cover_key_serves_both_readings(law):
    """ONE physical fact, ONE threshold: the mapped apron that refuses the
    lot verdict is the same evidence that names the open face apron.  The
    PARKING knob is its own key again and is not consulted here."""
    rules = load_rules()
    assert rules.lot.apron_cover_fraction == pytest.approx(0.1)
    assert rules.lot.parking_cover_fraction == pytest.approx(0.5)
    a = _mapped_apron_lot_airport(0.25)
    src = {r.id: r for r in classify_sources(
        a, build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2),
        rules)[0]}["lotpage"]
    from auto_patch_v2.classify.open_default import apron_evidence
    why = apron_evidence(Polygon(_rect(240.0, 320.0, 300.0, 400.0)), src,
                         {"n_taxi": 0}, None, rules)
    assert why is not None and "aeroway=apron" in why, why
    # ...and the page is no longer cut out as a lot: the pavement over it
    # is airside (here it merges into the apron beside it, which is what
    # "the apron never absorbs a lot" stops happening the other way round)
    page = Polygon(_rect(240.0, 320.0, 300.0, 400.0))
    over = [c for c in classify(a, law, rules).cells
            if Polygon(c.ring, c.holes).intersection(page).area > 1.0]
    assert over and all(c.side == "airside" for c in over), \
        [(c.role, c.side, c.ref) for c in over]


# ── 6. the landside demotion yields to APRON EVIDENCE (owner RULINGS
#      2026-09-11ac item 7: LEMD shapeID 75 / pav171, five 1300 startups)

def _detached_stands_airport(startups: bool, road: bool = False):
    """A 100 x 85 m page west of the apron, 50 m clear of every other
    pavement and outside every route-proximity band: the slice scores it
    APRON and the touch-chain law demotes it, exactly as at LEMD.  With
    ``startups`` it carries three 1300 stands — ``pav171`` carries five
    (70-74) on 30,174 m2 and shipped ``parking_lot``, groundside."""
    a = _synthetic(gate=True)
    page = Pavement("stands", Surface.ASPHALT, _rect(150.0, 300.0, 250.0, 385.0), ())
    starts = a.startups + tuple(
        Startup(f"Stand {k}", (170.0 + 25.0 * k, 340.0), 0.0, "gate")
        for k in range(3)) if startups else a.startups
    ways = a.osm_ways + ((_way(4, [(150.0, 320.0), (250.0, 320.0)],
                               highway="service"),) if road else ())
    return _dc.replace(a, pavements=a.pavements + (page,), startups=starts,
                       osm_ways=ways)


def test_startups_keep_a_demoted_page_airside(law):
    # the SAME geometry with no evidence on it: demoted, as the M1 law says
    bare = [c for c in classify(_detached_stands_airport(False), law).cells
            if c.ref == "stands"]
    assert bare and all(c.side == "groundside" for c in bare), bare
    assert all(c.evidence.get("demoted") == 1.0 for c in bare), \
        "the twin no longer exercises the demotion"
    # ...and with the stands on it the demotion yields
    page = [c for c in classify(_detached_stands_airport(True), law).cells
            if c.ref == "stands"]
    assert page and all(c.side == "airside" for c in page), \
        [(c.role, c.side) for c in page]
    assert any(c.evidence.get("apron_evidence") == "startup on the face"
               for c in page), [dict(c.evidence) for c in page]


def test_a_road_on_a_stand_page_does_not_make_it_a_lot(law):
    """pav171's own shape: stands AND an OSM service road across it.  The
    road is road evidence and would have made the demoted face a
    ``parking_lot``; the stands outrank it."""
    page = [c for c in classify(_detached_stands_airport(True, road=True), law).cells
            if c.ref == "stands"]
    assert page
    assert not any(c.role in ("parking_lot", "groundside_pavement") for c in page), \
        [(c.role, c.side) for c in page]


# ── §37 (5): A PAGE TOO NARROW TO PARK ON IS NOT A CAR PARK ────────────
# (owner RULINGS 2026-09-13j item 7 / 13ab, lane ``v2roadcap2``).  The
# KCLT site in miniature: an 8.4 m ribbon 600 m long, five OSM roads
# reaching it and only a fraction of one mapped INSIDE it, no taxi
# centreline, no startup.  ``narrow_road_width_m``'s own words are "a
# page at most this wide that carries ANY road centreline IS the road",
# but its branch is gated on ``min_road_fraction`` x HALF-PERIMETER —
# 120 m on a 601 m ribbon — so the page fell to the LOT ladder's weakest
# rung (04u ``reach > 0``) and §27 then flipped the ``parking_lot`` to
# ``apron`` on 20.8 m of lateral contact, the LOT rule, §37 (2)'s share
# test not applying to a face not born a road.

def _ribbon(x0: float, y0: float, length: float, width: float) -> Polygon:
    return _rect(x0, y0, x0 + length, y0 + width)


def _ribbon_airport(road_m: float, width: float = 8.4):
    """A landside ribbon page with ``road_m`` of OSM service road mapped
    inside it, well clear of the runway and of every apron."""
    a = _synthetic(gate=True)
    page = Pavement("ribbon", Surface.ASPHALT,
                    _ribbon(-400.0, 200.0, 600.0, width), ())
    ways = ()
    if road_m > 0.0:
        y = 200.0 + width / 2.0
        ways = (_way(41, [(-380.0, y), (-380.0 + road_m, y)], highway="service"),)
    return _dc.replace(a, pavements=a.pavements + (page,),
                       osm_ways=a.osm_ways + ways)


def _ribbon_source(law, road_m: float, width: float = 8.4):
    a = _ribbon_airport(road_m, width)
    rules = load_rules()
    recs, _polys = classify_sources(
        a, build_evidence(a, rules,
                          law.tables.structures.building_pad.min_area_m2, law),
        rules)
    srcs = {s.id: s for s in recs}
    return srcs["ribbon"], rules


def test_a_sub_module_ribbon_carrying_any_road_is_a_STRIP(law):
    """71 m of mapped centreline in a 601 m ribbon — a tenth of the
    half-perimeter, so ``carries`` is False and the 12 m narrow-road
    branch never fires.  Below the parking floor the gate is the rule's
    own words: ANY road centreline inside."""
    src, rules = _ribbon_source(law, road_m=71.0)
    assert src.width_m <= rules.lot.min_lot_width_m, src.width_m
    assert src.road_m < rules.lot.min_road_fraction * (src.area_m2 / src.width_m), (
        "the twin must exercise the branch ``carries`` does NOT cover")
    assert src.cls == "strip", (src.cls, src.reason)
    assert "too narrow to park on" in src.reason, src.reason


def test_a_sub_module_ribbon_with_no_road_stays_open_never_a_lot(law):
    """The veto's other half: the 04u rung reads only that roads REACH
    the page.  With none inside, a page too narrow to hold a parking
    module is ``open`` — it is never minted a car park."""
    src, _ = _ribbon_source(law, road_m=0.0)
    assert src.cls == "open", (src.cls, src.reason)


def test_a_page_wide_enough_for_a_parking_module_is_untouched(law):
    """CYXY ``pav4``'s own reading (11.5 m, 41 m of road on a 464 m
    half-perimeter — the case ``min_road_fraction`` was written for):
    ABOVE the floor, so the lot ladder still owns it and 09-04j stands."""
    src, rules = _ribbon_source(law, road_m=41.0, width=11.5)
    assert src.width_m > rules.lot.min_lot_width_m, src.width_m
    assert src.cls == "lot", (src.cls, src.reason)
    assert "reach it (04u)" in src.reason, src.reason


def test_the_ribbon_keeps_its_road_role_through_the_airside_edge_pass(law):
    """END TO END: born a road, §37 (2)'s SHARE test now applies to it,
    and a graze does not flip it.  This is the owner's item 7 —
    ``dsf:pol82`` a ``service_road`` on its own ground, not ``apron``."""
    cl = classify(_ribbon_airport(71.0), law)
    cells = [c for c in cl.cells if c.ref == "ribbon"]
    assert cells
    assert all(c.role == "service_road" for c in cells), \
        [(c.role, c.side) for c in cells]
    assert all(c.side == "groundside" for c in cells)


def test_an_emit_sliver_clipping_a_road_is_never_a_road(law):
    """LEMD's own defect, caught before it shipped: 34 emit slivers
    0.1-0.3 m across clip a metre of road each, and every one of them
    became a ``service_road`` on the first arm of this rule.  A page
    narrower than one service-road corridor is an artefact, and a road
    shorter than the feed's own noise floor is noise."""
    src, rules = _ribbon_source(law, road_m=71.0, width=0.3)
    assert src.width_m < rules.service.road_width_m, src.width_m
    assert src.cls != "strip", (src.cls, src.reason)


def test_a_metre_of_road_is_noise_not_evidence(law):
    """The other floor: a sub-module page a road merely clips."""
    src, rules = _ribbon_source(law, road_m=4.0)
    assert src.road_m < rules.osm_roads.min_len_m, src.road_m
    assert src.cls != "strip", (src.cls, src.reason)
