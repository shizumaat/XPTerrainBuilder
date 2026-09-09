"""Owner 2026-09-04u (CYXY sim read, round 3; lane v2round3) as synthetic
twins over the M1 synthetic airport (``test_classify._synthetic``):

1. THE SLIVER WELD — two airside pavements whose boundaries run 0.47 m
   apart weld at planar build: one shared edge, no unowned sliver, zero
   T-vertices (``planar/weld.py``, ``emit.identity.weld_spacing_m``);
2. an OPEN page a 1206 route REACHES (ends at its boundary, 0 m inside)
   is a parking lot (``sources.road_reach``);
3. an OPEN page with NOTHING — no startup, no taxi centreline, no apron
   name, no road — is groundside pavement, never apron by default
   (``classify/open_default.py``, ``rules.groundside.default_open_role``);
4. a LOT beside a pad that touches no airside pavement keeps the
   set-back (every pad cuts, 09-01i / 04u) and its own level: no shared
   vertex, no pad flat group over a lot vertex, no frontage row on it.
"""
from __future__ import annotations

import dataclasses as _dc
import math
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
from auto_patch_v2.constraints import pads  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import (Building, GroundRoute, Pavement,  # noqa: E402
                                         Surface, TaxiNode)
from auto_patch_v2.planar.build import build as planar_build  # noqa: E402
from auto_patch_v2.planar.weld import weld_cells  # noqa: E402
from test_classify import _rect, _synthetic  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _face_poly(pm, f):
    return Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)])


def _with_law(law, **identity):
    ident = _dc.replace(law.tables.emit.identity, **identity)
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit, identity=ident)))


# ── 1. the sliver weld ────────────────────────────────────────────────────

def _sliver_airport():
    """No terminal (every island is aircraft parking, 06-11): a 60 x 35 m
    pavement whose south edge runs 0.47 m north of the parallel
    taxiway's north edge (y = 125) — the CYXY 101 / 211 class."""
    a = _synthetic(gate=False, island=False)
    gap = 0.47
    near = Pavement("near", Surface.ASPHALT,
                    _rect(320.0, 125.0 + gap, 380.0, 160.0 + gap), ())
    return _dc.replace(a, pavements=a.pavements + (near,)), gap


def test_pavements_a_sliver_apart_weld_with_no_t_vertex(law):
    a, gap = _sliver_airport()
    tol = law.tables.emit.identity.weld_spacing_m
    assert gap < law.tables.emit.identity.min_distinct_spacing_m <= tol
    cl = classify(a, law)
    near = [c for c in cl.cells if c.ref == "near"]
    assert near and near[0].side == "airside"
    # the cells as classified: 0.47 m from the nearest airside neighbour
    def others(cells):
        return [Polygon(c.ring, c.holes) for c in cells
                if c.ref != "near" and c.side == "airside"]
    npoly0 = Polygon(near[0].ring)
    assert min(p.distance(npoly0) for p in others(cl.cells)) == pytest.approx(gap, abs=1e-6)
    # the weld pass: the junior cell moves onto the senior boundary
    welded, st = weld_cells(cl.cells, law)
    wn = next(c for c in welded if c.ref == "near")
    assert st.cells_welded >= 1 and st.vertices_projected >= 2
    assert min(p.distance(Polygon(wn.ring)) for p in others(welded)) == 0.0
    # the planar map: a shared edge, no sliver face, no dropped gap there
    pm, stats = planar_build(a, cl, law)
    assert stats.t_vertices == 0 and stats.weld.cells_welded >= 1
    nf = next(f for f in pm.faces.values() if f.ref == "near")
    npoly = _face_poly(pm, nf)
    nb = [f for f in pm.faces.values() if f.ref != "near" and f.side == "airside"
          and f.role != "graded_strip" and _face_poly(pm, f).distance(npoly) < 1e-9]
    assert nb, "no welded neighbour"
    shared = set(pm.ring_vertices(nf.ring)) & {v for f in nb for v in pm.ring_vertices(f.ring)}
    assert len(shared) >= 2
    assert sum(_face_poly(pm, f).intersection(npoly).length for f in nb) >= 59.0
    # no face of any role sits in the old gap
    probe = Polygon([(330.0, 125.05), (370.0, 125.05), (370.0, 125.0 + gap - 0.05),
                     (330.0, 125.0 + gap - 0.05)])
    for f in pm.faces.values():
        if f.ref != "near" and f.id not in {g.id for g in nb}:
            assert _face_poly(pm, f).intersection(probe).area < 1e-6, f
    # the control arm: with the weld off the gap survives
    pm0, st0 = planar_build(a, cl, _with_law(law, weld_spacing_m=0.0))
    nf0 = _face_poly(pm0, next(f for f in pm0.faces.values() if f.ref == "near"))
    assert st0.weld.cells_welded == 0
    assert min(_face_poly(pm0, f).distance(nf0) for f in pm0.faces.values()
               if f.ref != "near" and f.side == "airside" and f.role != "graded_strip") > 0.3


# ── 2. an open page a route reaches is a lot ─────────────────────────────

def _reached_page_airport():
    """Landside: an 80 x 60 m open page (no startup, no taxi centreline, no
    road inside) with a 1206 route from the apron ENDING at its boundary."""
    a = _synthetic(gate=True, island=False)
    page = Pavement("page", Surface.ASPHALT, _rect(-300.0, 300.0, -220.0, 360.0), ())
    nodes = dict(a.taxi_nodes)
    nodes[30] = TaxiNode(30, (300.0, 320.0), "both")     # on the apron's west edge
    nodes[31] = TaxiNode(31, (-220.0, 320.0), "both")    # the page's east boundary
    routes = a.ground_routes + (GroundRoute(30, 31, "truck", False),)
    return _dc.replace(a, pavements=a.pavements + (page,), taxi_nodes=nodes,
                       ground_routes=routes)


def test_open_page_a_route_reaches_is_a_lot(law):
    a = _reached_page_airport()
    rules = load_rules()
    ev = build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2)
    recs = {r.id: r for r in classify_sources(a, ev, rules)[0]}
    page = recs["page"]
    assert page.road_m == pytest.approx(0.0) and page.road_reach == 1
    assert page.cls == "lot" and "reach" in page.reason
    cl = classify(a, law, rules)
    cells = [c for c in cl.cells if c.ref == "page"]
    assert [c.role for c in cells] == ["parking_lot"], cells
    assert cells[0].side == "groundside"
    assert cells[0].evidence["source_road_reach"] == 1.0
    # the route's corridor outside pavement is a service road
    assert any(c.role == "service_road" for c in cl.cells)


# ── 3. an open page with nothing is groundside, never apron ──────────────

def _bare_page_airport(reach: bool):
    """A 200 x 75 m open page on the RUNWAY's south edge (the chain seed:
    never demoted), touching no taxi centreline, no startup, no apron
    name, no road: within the runway's proximity band it is a junction
    (07-06), beyond it the slice scores APRON — the face the 04u default
    governs; optionally a route ending at its east boundary."""
    a = _synthetic(gate=True, island=False)
    page = Pavement("bare", Surface.ASPHALT, _rect(600.0, -90.0, 800.0, -15.0), ())
    a = _dc.replace(a, pavements=a.pavements + (page,))
    if reach:
        nodes = dict(a.taxi_nodes)
        nodes[40] = TaxiNode(40, (900.0, -50.0), "both")
        nodes[41] = TaxiNode(41, (800.0, -50.0), "both")
        a = _dc.replace(a, taxi_nodes=nodes,
                        ground_routes=a.ground_routes + (GroundRoute(40, 41, "truck", False),))
    return a


def test_open_page_with_nothing_is_groundside_by_default(law):
    rules = load_rules()
    assert rules.groundside.default_open_role == "groundside_pavement"
    a = _bare_page_airport(reach=False)
    cl = classify(a, law, rules)
    cells = [c for c in cl.cells if c.ref == "bare"]
    roles = {c.role for c in cells}
    assert "groundside_pavement" in roles and "apron" not in roles, cells
    gs = [c for c in cells if c.role == "groundside_pavement"]
    assert all(c.side == "groundside" and c.evidence.get("open_default") == 1.0
               and not c.evidence.get("demoted") for c in gs)
    assert cl.stats["open_defaulted"] >= 1
    # the strip within the runway's proximity band is maneuvering surface
    assert any(c.role == "junction" and c.evidence.get("near_route") == 1.0 for c in cells)
    # the apron itself (startup + taxi centreline) is still apron
    assert any(c.role == "apron" and c.ref == "apron" for c in cl.cells)
    # ...and the same page with a route reaching it is a lot
    cl2 = classify(_bare_page_airport(reach=True), law, rules)
    cells2 = [c for c in cl2.cells if c.ref == "bare"]
    assert cells2 and "parking_lot" in {c.role for c in cells2} and \
        "apron" not in {c.role for c in cells2}, cells2


# ── 4. a lot beside a pad keeps the set-back and its own level ───────────

def _lot_pad_airport():
    """The landside island (groundside) with a building whose ROTATED
    outline shares the island's north edge — a pad touching groundside
    only, on no lattice line (the CYXY building9 / lot 87 class)."""
    a = _synthetic(gate=True, island=True)         # island: 800..900 x 300..400
    ang = math.radians(20.0)
    c, s = math.cos(ang), math.sin(ang)
    x0, y0 = 830.0, 400.0                           # on the island's north edge
    pts = [(0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)]
    ring = tuple((x0 + x * c - y * s, y0 + x * s + y * c) for x, y in pts)
    b = Building("shed", ring, (), "osm", None, None)
    return _dc.replace(a, buildings=a.buildings + (b,))


def test_lot_beside_a_pad_keeps_the_setback_and_its_own_level(law):
    a = _lot_pad_airport()
    cl = classify(a, law)
    back = law.tables.structures.building_pad.groundside_cutback_m
    pad = [c for c in cl.cells if c.role == "building"
           and Polygon(c.ring).distance(Polygon([(830.0, 400.0)] * 3).buffer(1.0)) < 1.0]
    assert pad, "the shed became a pad"
    lots = [c for c in cl.cells if c.ref == "island"]
    assert lots and all(c.side == "groundside" for c in lots)
    assert all(c.evidence.get("mixed_pad_cutback") == 1.0 for c in lots)
    # the cells: cut back by at least the set-back
    d = min(Polygon(l.ring, l.holes).distance(Polygon(pad[0].ring)) for l in lots)
    assert d >= back - 1e-6
    # the planar map: no shared vertex after the identity snap
    pm, stats = planar_build(a, cl, law)
    assert stats.t_vertices == 0
    pf = next(f for f in pm.faces.values() if f.role == "building"
              and _face_poly(pm, f).distance(Polygon(pad[0].ring)) < 0.5)
    lf = [f for f in pm.faces.values() if f.ref == "island"]
    pv = set(pm.ring_vertices(pf.ring))
    lv = {v for f in lf for v in pm.ring_vertices(f.ring)}
    assert not (pv & lv)
    assert min(_face_poly(pm, f).distance(_face_poly(pm, pf)) for f in lf) >= back - 1e-6
    # its own level: the pad's flat group holds no lot vertex, and no
    # frontage row binds the lot to the pad (frontage is apron / junction)
    # the pad's flatness rows (09-09c: ``Diff`` pairs, not a merged ``Flat``)
    # hold no lot vertex
    for row in pads.pad_flats(pm, law, a):
        if f"face:{pf.id}" in row.source.inputs:
            assert not ({row.a, row.b} & lv)
    for row in pads.frontage_near_miss(pm, law, a):
        assert f"pad:{pf.id}" not in row.source.inputs or \
            not ({row.a, row.b} & lv)
