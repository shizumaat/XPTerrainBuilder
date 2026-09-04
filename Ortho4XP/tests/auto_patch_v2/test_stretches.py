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
from auto_patch_v2.constraints.routes import routes
from auto_patch_v2.constraints.transverse import axes
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.highs import Options, Status, solve
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
            CutLine("taxi_centerline", "taxiG", ((0.0, 91.5), (0.0, 320.0)), "A"))
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
    rows = [r for r in taxi.taxi_within_shape(pm, law, airport) if {r.a, r.b} == {X, nxt}]
    assert rows and all(r.cap == cap_a for r in rows)
    assert {r.source.ruling for r in rows} == {"rulesets.taxi.longitudinal per stretch (04t-3)"}
    # the same price in the route graph (no-step budgets follow the stretch)
    g_ = routes(pm, law)
    key = (min(X, nxt), max(X, nxt))
    idx = [k for k in range(len(g_.a)) if (int(g_.a[k]), int(g_.b[k])) == key]
    assert idx and g_.cap[idx[0]] == pytest.approx(cap_a)


def test_a_junction_across_a_letter_change_prices_per_stretch_region(site, law):
    """Inside junction J (crossed by A at D and G at A): a pair on the G
    stretch holds G's cap, a pair on A's stretch holds D, a pair across
    the two — and every pair with a body vertex off the stretches — holds
    J's own D cap: the relaxation lives on the stretch whose letter it is,
    never on a chord across letters."""
    airport, pm = site
    st = S.stretches(pm, law)
    vw = view(pm, law)
    cap_a = law.ruleset.taxi.longitudinal.value(None, "A")
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    X = _vid(pm, 0.0, 91.5)
    faces = [f for f in pm.faces.values() if f.ref == "junctionJ"]
    assert faces and all(f.code_letter == "D" for f in faces)
    rows = [r for r in taxi.taxi_within_shape(pm, law, airport)
            if r.source.inputs[0] in {f"face:{f.id}" for f in faces}]
    by_pair = {}
    for r in rows:
        by_pair.setdefault((min(r.a, r.b), max(r.a, r.b)), r)
    g = next(s for s in st.items if s.code_letter == "A")
    a_w = next(s for s in st.items if s.ref == "taxiA" and
               min(vw.xy[v][0] for v in s.vertices) < -100)
    g_v = [v for v in g.vertices if v != X and 0 < vw.xy[v][1] - 91.5 <= 100]
    a_v = [v for v in a_w.vertices if v != X and -30 <= vw.xy[v][0] < 0]
    assert g_v and a_v
    # on G: G's cap; on A: D; across: J's own cap; body: J's own cap
    assert by_pair[(min(X, g_v[0]), max(X, g_v[0]))].cap == pytest.approx(cap_a)
    assert by_pair[(min(X, a_v[0]), max(X, a_v[0]))].cap == pytest.approx(cap_d)
    assert by_pair[(min(g_v[0], a_v[0]), max(g_v[0], a_v[0]))].cap == pytest.approx(cap_d)
    on_any = set(st.on)
    body = [v for f in faces for v in vw.rings[f.id] if v not in on_any]
    assert body, "J has rim vertices off every stretch"
    for r in rows:
        if r.a in body or r.b in body:
            assert r.cap == pytest.approx(cap_d)
    assert {round(r.cap, 12) for r in rows} == {round(cap_a, 12), round(cap_d, 12)}


def test_two_stretches_of_one_letter_read_as_one_plane(site, law):
    """Along taxiway A (D west, D east of X) every pair reads D: the
    travel path through X is longer than the chord, which the letter law
    does not turn into a relaxation (the ceiling)."""
    airport, pm = site
    cap_d = law.ruleset.taxi.longitudinal.value(None, "D")
    for ref in ("taxiA_w", "taxiA_e"):
        fid = _face(pm, ref).id
        rows = [r for r in taxi.taxi_within_shape(pm, law, airport)
                if r.source.inputs[0] == f"face:{fid}"]
        assert rows and {round(r.cap, 12) for r in rows} == {round(cap_d, 12)}


# ── (2) cap by edge portion vs the mouth ─────────────────────────────────

def test_a_long_shared_edge_takes_the_apron_cap_and_a_mouth_keeps_its_own(site, law):
    airport, pm = site
    vw = view(pm, law)
    cap_apron = law.tables.common.roles["apron"].longitudinal
    ratio = law.tables.emit.within_shape.apron_edge_portion_min_width_ratio
    rows = apron.apron_edge_portions(pm, law, airport)
    assert rows and {r.cap for r in rows} == {cap_apron}
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
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert pub["stretches"] and {e[2] for e in pub["stretches"]} == {"A", "D"}
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    within, xsec = within_shape(Patch.of(surf, law, pub, {}))
    assert within == [] and xsec == []
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
    # the v1 oracle reads the same patch: zero within-shape rows
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    assert not fam.get("within_shape"), [
        (v.way_a.tags.get("role"), round(v.grade_pct, 2), v.cap_pct) for v in fam["within_shape"]]


def test_a_minted_step_on_the_g_stretch_is_read_at_g_cap(site, law, tmp_path):
    airport, pm = site
    cs, *_r = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
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
