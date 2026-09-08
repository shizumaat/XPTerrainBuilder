"""Twins for RULINGS 2026-09-07g (lane v2terrace3, spec §2b): joints are
LABEL BOUNDARIES — every pavement node is served by the runway-connected
contact it reaches by the shortest visible in-shape path; two adjacent
nodes whose contacts disagree (07f's pairwise predicate) form a joint:
no row across it (dropped once at assembly), the boundary contour
declared in the sidecar, both censuses reading the step lawful and
pricing it when the declaration is withheld; agreeing contacts make no
joint; a dead-end lane through the boundary is still a joint; a
junction and a road spanning it lose their rows across it (the road's
step reported); one contact / no contact are 06n unchanged; the
feasibility fallback links two runways whose only connection is an
apron."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Flat, Linear, Offset
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.pipeline.territory import joint_steps, territory_constraints, territory_stage
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar import territories as T
from auto_patch_v2.planar.territories import NO_LABEL
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.verify.census import census_patch
from auto_patch_v2.verify.frame import Patch

ROOT = Path(__file__).resolve().parents[2]


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _StepDem:
    """700 west of x = 0, 715 east — each terrace has its own ground."""

    provenance = {"synthetic": "700 west of x=0, 715 east"}

    def z(self, x: float, y: float) -> float:
        return 715.0 if x > 0.0 and y > 60.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    """The 07g mechanics under a law WITHOUT the joint step cap: RULINGS
    2026-09-08d (3) makes a boundary predicted over ``terrace.max_step_m``
    (2 m) NOT a joint — these fixtures disagree by ≈ 23 m (a joint under
    07g alone).  The cap's own twins are ``test_v2chord.py``."""
    import dataclasses as _dc
    base = Law.for_airport("ZZZZ")
    emit = _dc.replace(base.tables.emit,
                       terrace=_dc.replace(base.tables.emit.terrace, max_step_m=float("inf")))
    return Law(tables=_dc.replace(base.tables, emit=emit), ruleset_key=base.ruleset_key)


def _airport(law, cells, cuts, runways=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    if runways is None:
        ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
                RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
        runways = (Runway("09/27", 45.0, 1, ends, 3, "D"),)
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, tuple(runways), (), (), {},
                      (), (), (), (), (), (), (), pack, _StepDem(), law.ruleset_key)
    cl = Classification(tuple(cells), tuple(cuts), {}, ())
    pm, pstats = build(airport, cl, law)
    stage = territory_stage(pm, law, airport, cl, out=lambda _m: None)
    return airport, stage.pm, stage, pstats, cl


#: the apron stands beyond the code-3 strip keep-out; the west stub is a
#: short route from the runway, the east route an L-shaped taxiway whose
#: length sets how far the two contacts' ceilings disagree
Y0, Y1 = 120.0, 180.0
RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {})
APRON = Cell(1, "apron", "apron", _rect(-150, Y0, 150, Y1), (), None, None, "airside", "apron", {})
STUB_W = Cell(2, "stub", "stubW", _rect(-161.5, 22.5, -138.5, Y0), (), None, "D", "airside", "taxi", {})
CUT_W = CutLine("taxi_centerline", "stubW", ((-150.0, 0.0), (-150.0, Y0 + 25.0)))


def _east(top: float):
    ring = ((588.5, 22.5), (611.5, 22.5), (611.5, top + 11.5), (138.5, top + 11.5),
            (138.5, Y1), (161.5, Y1), (161.5, top - 11.5), (588.5, top - 11.5))
    cell = Cell(3, "stub", "stubE", ring, (), None, "D", "airside", "taxi", {})
    cut = CutLine("taxi_centerline", "stubE", ((600.0, 0.0), (600.0, top), (150.0, top), (150.0, Y1 - 25.0)))
    return cell, cut


def _ids_of(row):
    if isinstance(row, (Diff, Offset)):
        return (row.a, row.b)
    if isinstance(row, Linear):
        return tuple(v for v, _c in row.terms)
    if isinstance(row, Flat):
        return tuple(row.group)
    return (row.v,)


def _faces(pm, ref):
    return [f for f in pm.faces.values() if f.ref == ref]


def _side_labels(pm, terr):
    """The label of the west and the east contact set (x < 0 / x > 0)."""
    west = {terr.label[v] for v in terr.label if terr.label[v] != NO_LABEL and pm.vertices[v].xy[0] < -100}
    east = {terr.label[v] for v in terr.label if terr.label[v] != NO_LABEL and pm.vertices[v].xy[0] > 100}
    return west, east


# ── 1. disagreeing contacts: a joint at the label boundary ───────────────

@pytest.fixture(scope="module")
def disagreeing(law):
    cell, cut = _east(900.0)           # ~1,700 m east route vs ~150 m west: ≈ 23 m apart by ceiling
    return _airport(law, [RUNWAY, APRON, STUB_W, cell], [CUT_W, cut])


def test_disagreeing_contacts_make_a_joint_at_the_label_boundary(disagreeing, law):
    airport, pm, stage, _ps, _cl = disagreeing
    terr, st = stage.terr, stage.terr.stats
    tt = law.tables.emit.terrace
    assert st.complexes_labelled == 1 and st.contacts >= 2
    assert st.joint_pairs >= 1 and st.joint_edges > 0 and st.contours >= 1, st
    # every apron vertex is served by a west or an east contact; the west
    # vertices by the west route, the east by the east route
    (apron,) = _faces(pm, "apron")
    ring = list(pm.ring_vertices(apron.ring))
    assert all(terr.label.get(v, NO_LABEL) != NO_LABEL for v in ring)
    assert st.unlabelled == 0          # labelling is TOTAL over a labelled complex
    west, east = _side_labels(pm, terr)
    assert west and east and not west & east
    for a, b in ((wa, ea) for wa in west for ea in east):
        assert terr.joint(a, b), (a, b, st.pairs)
    # the predicate's arithmetic on one disagreeing pair
    rec = next(p for p in st.pairs if p[6])
    _a, _b, gap, d, hold, _fg, _j = rec
    assert gap > 0.015 * d + tt.min_step_m and abs(hold - (0.015 * d + tt.min_step_m)) < 0.01
    # the label boundary crosses the apron between the two stubs: the
    # contour runs from the north edge to the south edge across the middle
    xs = [x for j in stage.joints for x, _y in j.points]
    ys = [y for j in stage.joints for _x, y in j.points]
    assert -100 < min(xs) and max(xs) < 100, (min(xs), max(xs))
    assert min(ys) <= Y0 + 1e-6 and max(ys) >= Y1 - 1e-6, (min(ys), max(ys))
    # no row of any generator joins a west-labelled vertex to an east one
    cs, counts, _w = territory_constraints(pm, law, airport, stage)
    assert counts["joint_filter"] > 0 and stage.flats_straddling == 0
    for r in cs.rows():
        ids = _ids_of(r)
        ls = {terr.label.get(v, NO_LABEL) for v in ids} - {NO_LABEL}
        assert not (ls & west and ls & east), (r.source.generator, ids)
    # no vertex was split: the map is the planar build's own
    assert len(pm.vertices) == _ps.vertices


def test_each_side_solves_to_its_contact_and_the_census_reads_the_step_lawful(disagreeing, law, tmp_path):
    airport, pm, stage, _ps, _cl = disagreeing
    terr = stage.terr
    cs, _c, _w = territory_constraints(pm, law, airport, stage)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    steps = [abs(sol.z[a] - sol.z[b]) for a, b, _ra, _rb in stage.edges]
    assert max(steps) > 1.0, steps                  # each terrace solves to its own contact
    js = joint_steps(pm, law, stage, sol.z)
    assert js["contours"] and max(c["step_m"] for c in js["contours"]) >= max(steps) - 1e-6
    west, east = _side_labels(pm, terr)
    zw = [sol.z[v] for v in terr.label if terr.label[v] in west]
    ze = [sol.z[v] for v in terr.label if terr.label[v] in east]
    assert min(ze) - max(zw) > 1.0 - 1e-6 or max(zw) - min(ze) > 1.0 - 1e-6
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z, label_joints=stage.joints,
                      straddles=terr.straddles)
    recs = [r for r in pub["terrace_joints"] if r.get("label_boundary")]
    assert recs and recs[0]["kind"] == "apron_terrace" and recs[0]["faced"] is False
    assert max(r["step_m"] for r in recs) >= max(steps) - 0.011
    # every published pair across the boundary was withheld
    for key in ("airside_no_step_edges", "pad_pavement_no_step_edges"):
        for e in pub[key]:
            assert not _crosses(pm, terr, e["a"], e["b"]), (key, e)
    # v2 verify: nothing fires across the declared boundary
    p = Patch.of(surf, law, pub)
    rows = census_patch(p)
    for fam in ("vertex_to_edge_step", "mid_edge_step", "cross_shape", "stacked_nodes",
                "within_shape", "airside_no_step", "transverse", "taxi_box"):
        assert not rows[fam], (fam, rows[fam][:2])
    # the same patch read with the declaration withheld prices the step
    p0 = Patch.of(surf, law, {k: v for k, v in pub.items() if k != "terrace_joints"})
    rows0 = census_patch(p0)
    assert rows0["within_shape"], "the ring edge across the boundary is a step the cap cannot hold"
    # the v1 oracle over the written patch: the boundary is a declared terrace
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    ctx = cg.law_context_from_sidecar(paths.patch)
    assert ctx["terrace_joints_ll"] and len(ctx["terrace_joints_ll"]) == len(recs)
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    for key in ("terrace_joint_route", "terrace_joint_strip",
                "vertex_to_edge_step", "mid_edge_step", "cross_shape", "stacked_nodes"):
        assert not fam.get(key), (key, fam.get(key)[:2])
    # the oracle's apron pairs across the boundary read the declared step
    # (its stub rows are the pre-existing chord-vs-route population of the
    # L-shaped east taxiway: the CONTROL without the territory stage
    # carries the same 1,974 rows, measured 2026-09-07)

    def apron_rows(f):
        return [v for v in f.get("within_shape", []) if getattr(v.way_a, "role", "") == "apron"]
    assert not apron_rows(fam), apron_rows(fam)[:2]
    fam0: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam0, quiet=True, top_n=0,
                           terrace_joints_ll=None)
    assert apron_rows(fam0)


def _crosses(pm, terr, a_ll, b_ll) -> bool:
    key_of = {(round(v.key[0], 7), round(v.key[1], 7)): vid for vid, v in pm.vertices.items()}
    ids = [key_of.get((round(float(q[0]), 7), round(float(q[1]), 7))) for q in (a_ll, b_ll)]
    return all(i is not None for i in ids) and terr.straddles(ids)


# ── 2. agreeing contacts: no joint ───────────────────────────────────────

def test_agreeing_contacts_make_no_joint(law):
    cell, cut = _east(200.0)           # ≈ 500 m east route: the cap holds the difference across 300 m
    airport, pm, stage, _ps, _cl = _airport(law, [RUNWAY, APRON, STUB_W, cell], [CUT_W, cut])
    st = stage.terr.stats
    assert st.contacts >= 2 and st.adjacent_pairs >= 1
    assert st.joint_pairs == 0 and st.joint_edges == 0 and not stage.joints, st.pairs
    cs, counts, _w = territory_constraints(pm, law, airport, stage)
    assert counts["joint_filter"] == 0


# ── 3. a dead-end lane through the boundary: still a joint ───────────────

def test_a_dead_end_lane_through_the_boundary_is_still_a_joint(law):
    cell, cut = _east(900.0)
    # a taxilane ACROSS the apron between the two routes, touching neither:
    # a dead-end lane — its stations are no contacts and serve nothing
    lane_cut = CutLine("taxi_centerline", "laneN", ((0.0, Y0), (0.0, Y1)))
    airport, pm, stage, _ps, _cl = _airport(law, [RUNWAY, APRON, STUB_W, cell], [CUT_W, cut, lane_cut])
    terr, st = stage.terr, stage.terr.stats
    assert st.complexes_labelled == 1, st
    assert st.joint_pairs >= 1 and st.joint_edges > 0
    station = {v for b in pm.breaklines.values() if b.kind == "taxi_centerline" and b.ref == "laneN"
               for v in b.vertices(pm)}
    assert station and not (station & terr.contacts), "a dead-end lane's stations are no contacts"
    # its stations are labelled like any node, by the west or the east contacts
    assert all(terr.label.get(v, NO_LABEL) != NO_LABEL for v in station)
    west, east = _side_labels(pm, terr)
    labels = {terr.label[v] for v in station}
    assert labels <= west | east
    cs, _c, _w = territory_constraints(pm, law, airport, stage)
    for r in cs.rows():
        ls = {terr.label.get(v, NO_LABEL) for v in _ids_of(r)} - {NO_LABEL}
        assert not (ls & west and ls & east), (r.source.generator, _ids_of(r))
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    assert max(abs(sol.z[a] - sol.z[b]) for a, b, _ra, _rb in stage.edges) > 1.0
    # the lane bridges nothing: its two ends solve to their own sides
    zs = sorted((pm.vertices[v].xy[1], sol.z[v]) for v in station)
    assert abs(zs[0][1] - zs[-1][1]) > 1.0 or len(labels) == 1


# ── 4. a junction and a road spanning the boundary: rows across dropped ──

def test_a_junction_and_a_road_spanning_the_boundary_lose_their_rows_across_it(law):
    cell, cut = _east(900.0)
    # a junction north of the apron, joined to it by a dead-end lane (06n:
    # a station on the shared boundary), and a service road welded north
    # of the junction — both span the label boundary
    jx = Cell(4, "junction", "jx", _rect(-40, Y1, 40, Y1 + 30), (), None, "D", "airside", "junction", {})
    road = Cell(5, "service_road", "svc", _rect(-60, Y1 + 30, 60, Y1 + 42), (), None, None,
                "airside", "pavement", {})
    lane_cut = CutLine("taxi_centerline", "laneN", ((0.0, Y0), (0.0, Y1 + 25.0)))
    airport, pm, stage, _ps, _cl = _airport(law, [RUNWAY, APRON, STUB_W, cell, jx, road],
                                            [CUT_W, cut, lane_cut])
    assert stage.terr.stats.complexes_labelled == 1, stage.terr.stats
    terr, st = stage.terr, stage.terr.stats
    assert st.joint_pairs >= 1
    roles = st.joint_edges_by_roles
    assert any("junction" in k for k in roles) and any("service_road" in k for k in roles), roles
    cs, counts, _w = territory_constraints(pm, law, airport, stage)
    dropped = stage.dropped
    assert dropped.get("junction_mesh", 0) > 0, dropped
    assert dropped.get("roads", 0) > 0 or dropped.get("road_within_shape", 0) > 0, dropped
    west, east = _side_labels(pm, terr)
    for r in cs.rows():
        ls = {terr.label.get(v, NO_LABEL) for v in _ids_of(r)} - {NO_LABEL}
        assert not (ls & west and ls & east), (r.source.generator, _ids_of(r))
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    js = joint_steps(pm, law, stage, sol.z)
    assert js["roads"] and js["roads"][0]["ref"] == "svc" and js["roads"][0]["step_m"] > 0.5, js["roads"]


# ── 5. one contact / no contact: 06n unchanged ───────────────────────────

def test_one_contact_is_no_partition(law):
    _airport_, pm, stage, _ps, _cl = _airport(law, [RUNWAY, APRON, STUB_W], [CUT_W])
    st = stage.terr.stats
    assert st.contacts >= 1 and st.joint_pairs == 0 and st.joint_edges == 0 and not stage.joints
    assert not pm.terrace_joints


def test_no_contact_is_an_island(law):
    _airport_, pm, stage, pstats, _cl = _airport(law, [RUNWAY, APRON], [])
    st = stage.terr.stats
    assert st.contacts == 0 and st.joint_pairs == 0 and not stage.joints
    assert pstats.terraces.islands == 1 and not pm.terrace_joints


# ── 6. the feasibility fallback: two runways joined only by an apron ─────

def test_the_fallback_links_two_runways_whose_only_connection_is_an_apron(law):
    ends2 = (RunwayEnd("09R", (-600.0, 400.0), (60.5, -135.5), 0.0, 0.0, 712.0, "fixture"),
             RunwayEnd("27L", (600.0, 400.0), (60.5, -135.5), 0.0, 0.0, 712.0, "fixture"))
    ends1 = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
             RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    runways = (Runway("09/27", 45.0, 1, ends1, 3, "D"), Runway("09R/27L", 45.0, 1, ends2, 3, "D"))
    rw2 = Cell(3, "runway", "09R/27L", _rect(-600, 377.5, 600, 422.5), (), 3, "D", "airside", "runway", {})
    apron = Cell(1, "apron", "apron", _rect(-150, Y0, 150, Y1 + 100), (), None, None, "airside", "apron", {})
    stub_n = Cell(4, "stub", "stubN", _rect(138.5, Y1 + 100, 161.5, 377.5), (), None, "D", "airside", "taxi", {})
    cut_n = CutLine("taxi_centerline", "stubN", ((150.0, 400.0), (150.0, Y1 + 100 - 25.0)))
    airport, pm, stage, _ps, _cl = _airport(law, [RUNWAY, apron, STUB_W, rw2, stub_n],
                                            [CUT_W, cut_n], runways=runways)
    st = stage.terr.stats
    assert st.links and pm.route_links, st
    (a, b, cap, d) = pm.route_links[0]
    assert cap > 0.0 and 100.0 < d < 400.0
    assert {pm.vertices[a].xy[0] < 0.0, pm.vertices[b].xy[0] < 0.0} == {True, False}
    # linked, the two systems agree through the apron: no joint
    assert st.joint_pairs == 0 and not stage.joints, st.pairs
    # both runways' pins reach every contact through the link
    assert all(v in stage.bands for v in stage.terr.contacts)
    cs, counts, _w = territory_constraints(pm, law, airport, stage)
    assert counts["route_links"] == 1
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message


# ── 7. labelling is TOTAL: the fallback takes the nearest CONNECTED node ─

def test_a_vertex_seeing_no_graph_node_takes_its_nearest_connected_node(law):
    """HECA 2026-09-07: 74 vertices stayed unlabelled because their
    Euclidean-nearest graph node was ISOLATED (no path to any contact)."""
    import numpy as np
    from shapely.geometry import Polygon
    poly = Polygon(_rect(0, 0, 200, 100))
    contacts = {1: (5.0, 50.0), 2: (195.0, 50.0)}
    g = T._graph(poly, contacts, 10.0, 0.5)
    assert g is not None and len(g.connected) == len(g.P)
    # isolate the node nearest the query (a notch node whose arcs failed)
    q = np.array([[100.0, 30.0]])
    _d, near = g.tree.query(q[0], k=1)
    D = g.D.copy(); D[:, near] = np.inf
    g = T._Graph(g.P, g.n_boundary, g.contacts, D, Polygon(), g.btree, g.tree,
                 np.flatnonzero(np.isfinite(D).any(axis=0)), None)
    g.ctree = type(g.tree)(g.P[g.connected])
    fb = [0, 0]
    out = T._vertex_distances(g, q, fb)     # the empty cover: nothing is visible
    assert fb == [1, 1] and np.isfinite(out).all(), (fb, out)
    _d2, k2 = g.ctree.query(q[0], k=1)
    node = g.connected[k2]
    gap = float(np.hypot(*(g.P[node] - q[0])))
    assert np.allclose(out[0], D[:, node] + gap)
    assert node != near


# ── 8. a chain row is read by its segments, never by its ends ───────────

def test_a_rate_triple_is_dropped_only_when_a_segment_straddles(law):
    """CYXY 2026-09-07: labels agree pairwise, not transitively — a §1.2
    rate row whose ends disagreed while both segments agreed was dropped,
    no contour crossed either segment, and the census priced the rate."""
    from auto_patch_v2.model.constraints import Source
    src = Source("no_step", "airside_no_step §1.2 rate")
    rate = Linear(((3, 1.0 / 12.5), (2, -(1.0 / 12.5 + 1.0 / 36.5)), (1, 1.0 / 36.5)), -1.0, 1.0, src)
    assert T.row_test_pairs(rate) == [(3, 2), (2, 1)]
    interp = Linear(((5, 1.0), (1, -0.4), (3, -0.6)), -1.0, 1.0, src)       # two negatives: not a chain
    assert T.row_test_pairs(interp) is None
    assert T.row_test_pairs(Diff(1, 3, 0.015, 1.0, src)) is None
    # non-transitive labels: ends 1 and 3 disagree, both segments agree
    terr = T.Territories({1: 10, 2: 20, 3: 30}, {}, frozenset({10, 20, 30}), T.TerritoryStats(),
                         verdict={(10, 20): False, (20, 30): False, (10, 30): True})
    assert terr.straddles((1, 2, 3))
    assert not terr.straddles_pairs(T.row_test_pairs(rate))
    assert terr.straddles_pairs([(1, 3)])


def test_the_law_table_carries_the_territory_keys(law):
    tt = law.tables.emit.terrace
    assert tt.min_step_m >= 0.0 and tt.simplify_factor > 0.0
    assert set(tt.cell_roles) <= set(tt.complex_roles)
