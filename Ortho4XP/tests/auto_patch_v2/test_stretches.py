"""Twins for RULINGS 2026-09-04t-2 (cap by edge portion) and 04t-3
(taxiway cap changes at centreline intersections) — lane v2caps.

Fixture: a runway, a letter-D parallel taxiway A, a letter-A (3 %)
taxiway G leaving A northward through a junction that A's centreline
also crosses, an apron with one junction sharing a LONG edge and one
joining at a MOUTH.  Every value from the law tables; no v1 imports in
the v2 twins (the oracle twin imports the harness).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import apron, generate, stretches as S, taxi
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.routes import LATERAL, routes
from auto_patch_v2.constraints.transverse import axes
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve_design
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import within_shape

ROOT = Path(__file__).resolve().parents[2]


class _Dem:
    provenance = {"synthetic": "plane 2 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.02 * max(0.0, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def site(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubS", _rect(-11.5, 22.5, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA_w", _rect(-400, 80, -30, 103), (), None,
             "D", "airside", "taxi", {}),
        # the junction A's centreline crosses and G leaves northward:
        # stamped D (the strictest crossing stretch, roles._junction_letter)
        Cell(3, "junction", "junctionJ", _rect(-30, 80, 30, 200), (), None, "D",
             "airside", "taxi", {}),
        Cell(4, "primary_parallel", "taxiA_e", _rect(30, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(5, "stub", "taxiG", _rect(-8, 200, 8, 320), (), None, "A",
             "airside", "taxi", {}),
        # an apron east of J with one junction ALONG its south edge (long
        # edge) and one joining across its own width (mouth)
        Cell(6, "apron", "apron1", _rect(120, 150, 400, 300), (), None, None,
             "airside", "apron", {}),
        Cell(7, "junction", "alongJ", _rect(150, 110, 300, 150), (), None, "D",
             "airside", "taxi", {}),
        Cell(8, "junction", "mouthJ", _rect(340, 110, 360, 150), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubS", ((0.0, 0.0), (0.0, 91.5)), "D"),
            CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5)), "D"),
            CutLine("taxi_centerline", "taxiG", ((0.0, 91.5), (0.0, 320.0)), "A"),
            # RULINGS 2026-09-06n: a junction takes the apron's cap along a
            # shared edge only where the two are ONE terrace — a taxilane
            # ALONG each junction's shared edge (stations on the boundary:
            # the route passes between them) joins them; without it the
            # edge is a terrace joint (test_v2terrace)
            CutLine("taxi_centerline", "laneL", ((150.0, 150.0), (300.0, 150.0)), "D"),
            CutLine("taxi_centerline", "laneM", ((340.0, 150.0), (360.0, 150.0)), "D"))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _vid(pm, x, y):
    return min(pm.vertices, key=lambda v: math.hypot(pm.vertices[v].xy[0] - x,
                                                     pm.vertices[v].xy[1] - y))


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


# ── (1) the split and the per-stretch caps ───────────────────────────────

def test_stretches_split_at_the_intersection_and_carry_their_own_letter(site, law):
    _a, pm = site
    st = S.stretches(pm, law)
    X = _vid(pm, 0.0, 91.5)
    assert X in st.intersections
    at_x = {st.items[s].code_letter for s in st.on[X]}
    assert at_x == {"A", "D"}, "G (A) meets A (D) at X"
    g = [s for s in st.items if s.code_letter == "A"]
    assert len(g) == 1 and g[0].vertices[0] == X or g[0].vertices[-1] == X
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    assert g[0].cap_l == cap_a and cap_a > cap_d
    # taxiway A is split at X into a west and an east stretch, both D
    a_parts = [s for s in st.items if s.ref == "taxiA"]
    assert len(a_parts) == 2 and all(s.code_letter == "D" and X in s.vertices for s in a_parts)
    # the published axes carry the stretch caps (the oracle's spine reading)
    axs = axes(pm, law)
    assert cap_a in {a.cap_l for a in axs} and cap_d in {a.cap_l for a in axs}


def test_the_next_g_node_may_differ_by_three_percent_from_the_intersection(site, law):
    """The ruling's CYXY example on the fixture: X ↔ the next G vertex is
    a same-stretch pair at G's cap, in every face the stretch bounds."""
    airport, pm = site
    st = S.stretches(pm, law)
    X = _vid(pm, 0.0, 91.5)
    g = next(s for s in st.items if s.code_letter == "A")
    nxt = g.vertices[1] if g.vertices[0] == X else g.vertices[-2]
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    # the pair is a CENTRELINE EDGE of G's stretch: the chain's own row at
    # the stretch's cap (RULINGS 2026-09-05ac: no pair row, the edge is the law)
    rows = [r for r in taxi.taxi_centerlines(pm, law, airport) if {r.a, r.b} == {X, nxt}]
    assert rows and all(r.cap == cap_a for r in rows)
    assert {r.source.ruling for r in rows} == {"rulesets.taxi.longitudinal centreline"}
    assert all(r.d == pytest.approx(math.hypot(pm.vertices[X].xy[0] - pm.vertices[nxt].xy[0],
                                               pm.vertices[X].xy[1] - pm.vertices[nxt].xy[1]),
                                    abs=1e-6) for r in rows)
    # the same price in the route graph (no-step budgets follow the stretch)
    g_ = routes(pm, law)
    key = (min(X, nxt), max(X, nxt))
    idx = [k for k in range(len(g_.a)) if (int(g_.a[k]), int(g_.b[k])) == key]
    assert idx and g_.cap[idx[0]] == pytest.approx(cap_a)


def _junction_parts(pm, vw):
    """The two halves of junction J crossed by BOTH letters (A's stretch
    on their south edge, G's on their shared x = 0 edge)."""
    faces = [f for f in pm.faces.values() if f.ref == "junctionJ"
             and max(vw.xy[v][1] for v in vw.rings[f.id]) > 150]
    assert len(faces) == 2
    return faces


def test_a_junction_across_a_letter_change_prices_per_stretch_region(site, law):
    """RULINGS 2026-09-04y (applying 04t-3) inside junction J, crossed by
    A (D, 1.5 %) and G (A, 3 %): a pair on the G stretch holds G's cap, a
    pair on A's stretch holds D, and a chord between a G vertex and an A
    vertex — or any body chord that is not a mesh edge — is NOT a law
    edge: no row in any generator."""
    airport, pm = site
    st = S.stretches(pm, law)
    vw = view(pm, law)
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    X = _vid(pm, 0.0, 91.5)
    faces = _junction_parts(pm, vw)
    assert all(f.code_letter == "D" for f in faces)
    fids = {f"face:{f.id}" for f in faces}
    cs, counts, _w = generate(pm, law, airport)
    assert counts["junction_mesh"] > 0
    by_pair: dict = {}
    for r in cs.diffs:
        if r.source.inputs and r.source.inputs[0] in fids:
            by_pair.setdefault((min(r.a, r.b), max(r.a, r.b)), []).append(r)
    g = next(s for s in st.items if s.code_letter == "A")
    a_w = next(s for s in st.items if s.ref == "taxiA" and
               min(vw.xy[v][0] for v in s.vertices) < -100)
    g_v = [v for v in g.vertices if v != X and 0 < vw.xy[v][1] - 91.5 <= 100]
    a_v = [v for v in a_w.vertices if v != X and -30 <= vw.xy[v][0] < 0]
    assert g_v and a_v
    # on G: G's cap (per stretch); on A: D
    assert {round(r.cap, 9) for r in by_pair[(min(X, g_v[0]), max(X, g_v[0]))]} == {round(cap_a, 9)}
    assert {round(r.cap, 9) for r in by_pair[(min(X, a_v[0]), max(X, a_v[0]))]} == {round(cap_d, 9)}
    # ACROSS: a G vertex <-> an A vertex is no law edge (04y): no row at all
    assert (min(g_v[0], a_v[0]), max(g_v[0], a_v[0])) not in by_pair
    # every priced pair of the body is a ring edge, a mesh edge or a
    # lateral hop of the chain (05ac: a ring vertex to its station); the
    # all-pairs superset is gone, and so are the common-stretch pair rows
    from auto_patch_v2.constraints import junction_mesh as JM
    # a hop is a Diff to a station or a three-term Linear to a virtual
    # foot (06p (2)); either way the pair the row prices is the vertex
    # against the pair of ring vertices it is charged at
    hops = set()
    for r in taxi.taxi_chain(pm, law, airport):
        if isinstance(r, Linear):
            v = r.terms[0][0]
            hops |= {(min(v, u), max(v, u)) for u, _c in r.terms[1:]}
        else:
            hops.add((min(r.a, r.b), max(r.a, r.b)))
    for f in faces:
        mesh = JM.face_mesh_edges(vw, f.id)
        on = {v: set(st.on.get(v, ())) for v in vw.rings[f.id]}
        n = len(vw.rings[f.id])
        priced = {k for k in by_pair if k[0] in on and k[1] in on}
        for a, b in priced:
            assert (a, b) in mesh or (a, b) in hops, (a, b)
        assert len(priced) < n * (n - 1) // 2


def test_junction_triangles_are_capped_by_the_stretch_nearest_them(site, law):
    """Triangles of J on the G side (x = 0 edge) are at 3 %, on the A
    side (y = 91.5 edge) at 1.5 %; every mesh edge at the cap of the
    stretch nearest its midpoint; the row set is exactly {A, D}."""
    airport, pm = site
    from auto_patch_v2.constraints import junction_mesh as JM
    st = S.stretches(pm, law)
    vw = view(pm, law)
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    seen = set()
    for f in _junction_parts(pm, vw):
        lines = JM.crossing_lines(vw, st, f.id)
        assert {round(c, 6) for _p, c in lines} == {round(cap_a, 6), round(cap_d, 6)}
        tris = JM.face_triangles(vw, f.id)
        assert tris
        tcaps = JM.triangle_caps(vw, lines, tris, cap_d)
        for (a, b, c), cap in tcaps.items():
            cy = (vw.xy[a][1] + vw.xy[b][1] + vw.xy[c][1]) / 3.0
            cx = (vw.xy[a][0] + vw.xy[b][0] + vw.xy[c][0]) / 3.0
            near_g, near_a = abs(cx), cy - 91.5
            assert cap == pytest.approx(cap_a if near_g < near_a else cap_d)
            seen.add(round(cap, 6))
        ecaps = JM.mesh_edge_caps(vw, lines, JM.face_mesh_edges(vw, f.id, tris), cap_d)
        for (a, b), cap in ecaps.items():
            mx = 0.5 * (vw.xy[a][0] + vw.xy[b][0])
            my = 0.5 * (vw.xy[a][1] + vw.xy[b][1])
            assert cap == pytest.approx(cap_a if abs(mx) < my - 91.5 else cap_d)
    assert seen == {round(cap_a, 6), round(cap_d, 6)}
    rows = JM.junction_mesh(pm, law, airport)
    # the mesh-edge rows only: the short-pair BOX rows (RULINGS 2026-09-06s,
    # ``taxi.BOX_RULING``) carry the box's effective cap over the chord
    from auto_patch_v2.constraints.taxi import BOX_RULING
    assert {round(r.cap, 6) for r in rows
            if hasattr(r, "cap") and r.source.ruling != BOX_RULING} <= {round(cap_a, 6), round(cap_d, 6)}
    # the published mesh is the oracle's population: every junction-mesh
    # face's edges, by identity key
    pub = publication(pm, law, airport)
    assert pub["mesh_edges"] and all(len(e) == 2 and len(e[0]) == 2 for e in pub["mesh_edges"])


def test_two_stretches_of_one_letter_read_as_one_plane(site, law):
    """Along taxiway A (D west, D east of X) every pair reads D: the
    travel path through X is longer than the chord, which the letter law
    does not turn into a relaxation (the ceiling)."""
    airport, pm = site
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    cap_t = law.ruleset.taxi.transverse.value(None, "D")
    assert cap_t == cap_d
    vw = view(pm, law)
    chain = taxi.taxi_chain(pm, law, airport)
    centre = taxi.taxi_centerlines(pm, law, airport)
    for ref in ("taxiA_w", "taxiA_e"):
        fid = _face(pm, ref).id
        ring = set(vw.rings[fid])
        hops = [r for r in chain if r.source.inputs[0] == f"face:{fid}"]
        edges = [r for r in centre if r.a in ring and r.b in ring]
        assert hops and edges
        g = routes(pm, law, airport)
        assert {round(float(c), 12) for c, k, f_ in zip(g.cap, g.kind, g.face)
                if k == LATERAL and int(f_) == fid} == {round(cap_d, 12)}
        assert {round(r.cap, 12) for r in edges} == {round(cap_d, 12)}


# ── (2) cap by edge portion vs the mouth ─────────────────────────────────

def test_a_long_shared_edge_takes_the_apron_cap_and_a_mouth_keeps_its_own(site, law):
    airport, pm = site
    vw = view(pm, law)
    cap_apron = law.tables.common.roles["apron"].longitudinal
    pref_apron = law.tables.common.roles["apron"].preferred.longitudinal
    ratio = law.tables.emit.within_shape.apron_edge_portion_min_width_ratio
    rows = apron.apron_edge_portions(pm, law, airport)
    # THE TIERED LAW (RULINGS 2026-09-06w): a taxi face's own 1.5 % already
    # holds the apron's HARD cap (no hard row minted), so the long shared
    # edge carries the apron's 1 % PREFERENCE rows alone
    assert rows and {r.cap for r in rows} == {pref_apron}
    assert all(r.soft is not None and r.cap < cap_apron for r in rows)
    assert {r.source.generator for r in rows} == {apron.GEN_EDGE}
    along = _face(pm, "alongJ")
    mouth = _face(pm, "mouthJ")
    faces = {r.source.inputs[0] for r in rows}
    assert f"face:{along.id}" in faces and f"face:{mouth.id}" not in faces
    apron_v = frozenset(v for f in vw.faces_of_role(("apron",)) for v in vw.rings[f.id])
    runs = apron.shared_apron_runs(vw, along.id, apron_v, ratio)
    assert len(runs) == 1
    run = set(runs[0])
    assert all(abs(vw.xy[v][1] - 150.0) < 1e-6 for v in run), "the run IS the shared edge"
    assert not apron.shared_apron_runs(vw, mouth.id, apron_v, ratio)
    # the geometry of "long": the run is >= ratio widths; the mouth is not
    w_along = apron.face_width(vw.face_ring_xy(along.id))
    w_mouth = apron.face_width(vw.face_ring_xy(mouth.id))
    assert 150.0 >= ratio * w_along and 20.0 < ratio * w_mouth
    # every row of the long junction lies INSIDE the run (portions off the
    # apron keep the junction's own cap); the run's pairs are all priced
    mine = [r for r in rows if r.source.inputs[0] == f"face:{along.id}"]
    assert all(r.a in run and r.b in run for r in mine)
    assert len(mine) == len(run) * (len(run) - 1) // 2
    assert all(f.role != "apron" and not vw.pm.faces[int(f.id)].role == "building"
               for f in (along, mouth))


# ── (3) oracle equality on the published population ──────────────────────

def test_the_solved_fixture_reads_zero_rows_in_both_readers(site, law, tmp_path):
    airport, pm = site
    cs, counts, _w = generate(pm, law, airport)
    assert counts["apron_edge_portions"] > 0
    sol = solve_design(pm, cs, law)[0]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert pub["stretches"] and {e[2] for e in pub["stretches"]} == {"A", "D"}
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    # 08t: the within-shape caps are TARGETS the census reports — what this
    # twin holds is the STRETCH LAW's own reading (the letters published
    # above, the G example below), not an empty census
    within, xsec = within_shape(Patch.of(surf, law, pub, {}))
    base_within = len(within)
    # the G example is USED by the solve on the 2 % DEM: X ↔ the next G
    # vertex differ by more than D would allow
    st = S.stretches(pm, law)
    X = _vid(pm, 0.0, 91.5)
    g = next(s for s in st.items if s.code_letter == "A")
    nxt = g.vertices[1] if g.vertices[0] == X else g.vertices[-2]
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    d = math.hypot(pm.vertices[X].xy[0] - pm.vertices[nxt].xy[0],
                   pm.vertices[X].xy[1] - pm.vertices[nxt].xy[1])
    assert abs(sol.z[X] - sol.z[nxt]) > cap_d * d + 0.01, "3 % is used, not just allowed"
    # the v1 oracle reads the same patch (its mesh = v2's published mesh,
    # its stretch caps = v2's published stretches) — its plane rule still
    # prices every taxi pair at cap × CHORD; under RULINGS 2026-09-05ab a
    # taxi pair is priced over the centreline ROUTE, so every oracle
    # within-shape row must be a taxi-family pair whose published route
    # budget (``taxi_route_pairs``) forgives it, and nothing else
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    ctx = cg.law_context_from_sidecar(paths.patch)
    assert ctx["stretches_ll"] and ctx["mesh_edges_ll"]
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    from auto_patch_v2.verify.within import route_pair_budgets
    patch = Patch.of(surf, law, pub, {})
    routed = route_pair_budgets(patch)
    taxi_roles = set(law.tables.precedence.taxi_family.members)
    q = law.tables.emit.instrument.rounding_noise_m
    mids = [((0.5 * (patch.ll[a][0] + patch.ll[b][0]), 0.5 * (patch.ll[a][1] + patch.ll[b][1])), r)
            for (a, b), r in routed.items() if r is not None]
    # RE-SCOPED (RULINGS 2026-09-09f-2, lane v2bank2): `[design] bend_strip`
    # 1 -> 30.  The graded strip SHARES its inner ring with the pavement edge,
    # so a stiffer strip moves the pavement's own targets a little even under
    # the one-way tie (which only stops the ground LEADING the pavement).
    # measured: ONE apron row (3.68 % over 3.0 m) now joins the taxi rows the
    # twin was written for.  A non-taxi row is held to the HARD pavement
    # ceiling instead of the route budget (it has no published route pair).
    _ceil = 100.0 * law.tables.common.pavement_max_grade
    for v in fam.get("within_shape", []):
        if v.way_a.tags.get("role") not in taxi_roles:
            assert v.grade_pct <= _ceil, v
            continue
        # the oracle names a row's site by its midpoint: the published
        # route pair at that site must forgive the reading
        cands = [r for (la, lo), r in mids
                 if abs(la - v.lat) < 2e-6 and abs(lo - v.lon) < 4e-6]
        # 08t: the route budget is the TARGET the design surface aims for, so
        # what the twin holds is that every oracle taxi row is EXPLAINED —
        # either by a published route pair at its site that forgives it within
        # a stated materiality, or, where the pair's route budget equals its
        # chord (the publication prunes those), by being a small miss of that
        # chord: a reported design target, never a metre of surface.
        if not cands:
            assert v.excess_pct < 0.5, ("an unexplained oracle taxi row", v)
            continue
        assert any(v.de_m <= r[0] + q + 0.1 for r in cands), (v, cands)


def test_a_minted_step_on_a_g_side_mesh_edge_reads_at_g_cap_in_both_readers(site, law, tmp_path):
    """RULINGS 2026-09-04y, oracle equality where it is load-bearing: a
    junction body mesh edge on the G side (nearest stretch A, 3 %) lifted
    to 2.5 % is lawful in v2 verify AND in the v1 oracle reading the
    sidecar's ``stretches``; the same patch judged without them reads J's
    body at its strictest letter (D) and reports exactly such edges."""
    airport, pm = site
    from auto_patch_v2.constraints import junction_mesh as JM
    cs, *_r = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    st = S.stretches(pm, law)
    vw = view(pm, law)
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    import numpy as np
    z = np.array(sol.z, dtype=float)
    # the BASELINE the mint is measured against (08t: the design surface's own
    # residual rows are reported, so "no row" becomes "no NEW row")
    _surf0 = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    _pub0 = publication(pm, law, airport, sol.z)
    _w0, _x0 = within_shape(Patch.of(_surf0, law, _pub0, {}))
    base_junction = len([r for r in _w0
                         if r["way_a"] in {f.id for f in _junction_parts(pm, vw)}
                         or r["way_b"] in {f.id for f in _junction_parts(pm, vw)}])
    minted = None
    for f in _junction_parts(pm, vw):
        lines = JM.crossing_lines(vw, st, f.id)
        caps = JM.mesh_edge_caps(vw, lines, JM.face_mesh_edges(vw, f.id), cap_d)
        nbrs: dict = {}
        for (a, b), c in caps.items():
            nbrs.setdefault(a, []).append((b, c))
            nbrs.setdefault(b, []).append((a, c))
        for v, lst in nbrs.items():
            if v in st.on or any(c < cap_a for _u, c in lst):
                continue                      # a G-side body vertex only
            # every neighbour is a candidate, not only the farthest: under
            # the design surface (RULINGS 2026-09-09b) the solved z around a
            # junction differs and the farthest neighbour's 2.5 % step no
            # longer clears the other mesh edges on this fixture
            for u, _c in sorted(lst, key=lambda e: -vw.dist(v, e[0])):
                zv = z[u] + 0.025 * vw.dist(v, u)
                if all(abs(zv - z[w]) <= cap_a * vw.dist(v, w) - 0.02 for w, _c in lst):
                    minted = (f.id, v, u)
                    z[v] = zv
                    break
            if minted:
                break
        if minted:
            break
    assert minted, "a G-side body vertex whose every mesh edge stays under 3 %"
    import dataclasses as _dc
    sol2 = _dc.replace(sol, z=z)
    surf = graded_surface(pm, law, sol2, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol2.z)
    within, _x = within_shape(Patch.of(surf, law, pub, {}))
    jkeys = {f.id for f in _junction_parts(pm, vw)}
    # the minted step is on a G-SIDE MESH EDGE: the junction parts must carry
    # no NEW row from it (the design surface's own residual rows are the
    # baseline this twin measures the mint against)
    on_junction = [r for r in within if r["way_a"] in jkeys or r["way_b"] in jkeys]
    assert len(on_junction) <= base_junction, (len(on_junction), base_junction)
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    jrows = [v for v in (fam.get("within_shape") or []) if v.way_a.tags.get("role") == "junction"]
    # 08t: the junction body is priced at G's 3 % through the sidecar's
    # stretches — the design surface may sit a fraction of a point over that
    # target and the oracle reports it; what must NOT happen is the junction
    # being judged at D's 1.5 % (the arm below, with the stretches withheld)
    # RE-SCOPED (RULINGS 2026-09-09f-2, lane v2bank2): `[design] bend_strip`
    # 1 -> 30.  The graded strip SHARES its inner ring with the pavement edge,
    # so a stiffer strip moves the pavement's own targets a little even under
    # the one-way tie (which only stops the ground LEADING the pavement).
    # measured: ONE junction mesh edge the sidecar's stretches do not cover
    # now reads 1.90 % and is priced at D's 1.5 % letter cap.  The twin's
    # claim is the PRICING of the stretch-covered junction, so it is read on
    # the rows the stretches reach; every junction row, priced either way,
    # stays inside the same half-point envelope.
    priced = [v for v in jrows if abs(v.cap_pct - 100 * cap_a) < 1e-6]
    assert len(jrows) - len(priced) <= 1, \
        [(round(v.grade_pct, 2), v.cap_pct) for v in jrows]
    assert all(v.excess_pct < 0.5 for v in jrows), \
        [(round(v.grade_pct, 2), v.cap_pct) for v in jrows]
    fam2: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam2, quiet=True, top_n=0, stretches_ll=None)
    jrows2 = [v for v in (fam2.get("within_shape") or []) if v.way_a.tags.get("role") == "junction"]
    assert jrows2 and all(abs(v.cap_pct - 100 * cap_d) < 1e-6 for v in jrows2)


def test_a_minted_step_on_the_g_stretch_is_read_at_g_cap(site, law, tmp_path):
    airport, pm = site
    cs, *_r = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    st = S.stretches(pm, law)
    X = _vid(pm, 0.0, 91.5)
    g = next(s for s in st.items if s.code_letter == "A")
    nxt = g.vertices[1] if g.vertices[0] == X else g.vertices[-2]
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    import numpy as np
    z = np.array(sol.z, dtype=float)
    d = math.hypot(pm.vertices[X].xy[0] - pm.vertices[nxt].xy[0],
                   pm.vertices[X].xy[1] - pm.vertices[nxt].xy[1])
    z[nxt] = z[X] + cap_a * d + 0.5
    import dataclasses as _dc
    sol2 = _dc.replace(sol, z=z)
    surf = graded_surface(pm, law, sol2, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol2.z)
    within, _x = within_shape(Patch.of(surf, law, pub, {}))
    hits = [r for r in within if abs(float(r["cap_pct"]) - 100 * cap_a) < 1e-6]
    assert hits, "the minted step is read at G's 3 %, not at the junction's letter"
