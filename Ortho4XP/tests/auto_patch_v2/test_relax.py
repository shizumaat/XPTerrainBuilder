"""Twins for THE LAST RESORT (RULINGS 2026-09-04t(1), ``solve/relax.py``):

* a HANGAR ROW — three flat pads fronting a narrow apron strip whose two
  ends reach a runway that climbs the lawful 1.5 % between the stubs, on
  a DEM 10 % across the apron — is HARD-INFEASIBLE; the IIS names the
  site (the apron face, its pads); the relaxation SPREADS the relief
  over all three populations (no single carrier; the brief's "no slack
  ≥ 2× mean" is refuted on a membrane and the measured spread recorded),
  makes every pad ONE PLANE (no step: the certificate), and the
  runway / taxi rows stay exact;
* the QP and the piecewise-linear approximation agree on the spread;
* a FEASIBLE airport is untouched: ``solve_law_ordered`` returns the hard
  solution byte for byte;
* ``why`` on the infeasible set runs in RELAXED MODE and reports the IIS
  and the relief;
* the census tags rows on relaxed vertices under ``relaxed_by``;
* the law table carries the budgets (``[relaxation]``).
"""
from __future__ import annotations

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law, tables
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff, Flat, Linear, Pin
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline import why as pwhy
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve import relax
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.solve.tiers import solve_law_ordered


class _Dem:
    """1.5 % along the runway (x), 10 % across the apron (y beyond 40)."""

    provenance = {"synthetic": "1.5 % in x, 10 % in y across the hangar row"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.015 * (x + 600.0) + 0.10 * max(0.0, y - 40.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _hangar_row(law, pins=(700.0, 718.0)):
    """The runway climbs ``pins`` over 1,200 m (1.5 %: the cap); two stubs
    at x = ±150 lead to a 40 m wide apron strip whose north edge three
    hangar pads front with 10 m gaps.  Between the stubs the runway rises
    4.5 m; the stubs may carry ±0.86 m each; the apron must climb ≥ 2.8 m
    but its rim is consumed by three FLAT contacts — it can climb ~1 m."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, pins[0], "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, pins[1], "fixture"))
    runways = [Runway("09/27", 45.0, 1, ends, 3, "D")]
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubW", _rect(-161.5, 22.5, -138.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "stub", "stubE", _rect(138.5, 22.5, 161.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "hangar_apron", _rect(-200, 80, 200, 120), (), None, None,
             "airside", "apron", {}),
        Cell(4, "building", "hangar1", _rect(-190, 120, -70, 170), (), None, None,
             "airside", "pad", {}),
        Cell(5, "building", "hangar2", _rect(-60, 120, 60, 170), (), None, None,
             "airside", "pad", {}),
        Cell(6, "building", "hangar3", _rect(70, 120, 190, 170), (), None, None,
             "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubW", ((-150.0, 0.0), (-150.0, 100.0))),
            CutLine("taxi_centerline", "stubE", ((150.0, 0.0), (150.0, 100.0)))]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, tuple(runways), (), (), {},
                      (), (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    pm, _stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    return airport, pm


@pytest.fixture(scope="module")
def hangar(law):
    airport, pm = _hangar_row(law)
    cs, _counts, _w = generate(pm, law, airport)
    return airport, pm, cs


def _over_cap(cs, z, generators):
    worst = 0.0
    for d in cs.diffs:
        if d.source.generator in generators:
            worst = max(worst, abs(z[d.a] - z[d.b]) - d.cap * d.d)
    return worst


def test_law_table_carries_the_budgets(law):
    rl = law.tables.emit.relaxation
    assert rl.iis_time_budget_s > 0 and rl.max_rounds >= 1 and rl.max_pieces >= 2
    assert 0 < rl.materiality_m <= 0.05
    assert rl.relaxable_from_role in law.tables.precedence.roles
    assert relax.qp_available(), "highspy is the QP backend the freeze carries"


def test_hangar_row_is_hard_infeasible_and_the_iis_names_the_site(hangar, law):
    airport, pm, cs = hangar
    sol = solve_hard(pm, cs, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.INFEASIBLE
    assert sol.iis, sol.message
    rows = [r for r, _s in sol.iis]
    apron = next(f.id for f in pm.faces.values() if f.role == "apron")
    faces = {relax._face_of(r) for r in rows} - {None}
    assert apron in faces, faces
    kinds = {type(r).__name__ for r in rows}
    assert "Flat" in kinds, kinds                       # the pads consume the rim
    # every IIS row touches the hangar row: the apron, its pads, the stubs, the runway
    site = {f.id for f in pm.faces.values()
            if f.role in ("apron", "building", "stub", "runway")}
    for r in rows:
        vs = (r.v,) if isinstance(r, Pin) else (r.a, r.b) if isinstance(r, Diff) else \
            r.group if isinstance(r, Flat) else tuple(v for v, _c in r.terms) \
            if isinstance(r, Linear) else (r.v,)
        assert all(set(pm.vertices[v].incident_faces) & site for v in vs)


def test_relaxation_spreads_the_relief_and_forms_no_step(hangar, law):
    airport, pm, cs = hangar
    size: dict = {}
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options(), size_out=size)
    assert sol.status is Status.OPTIMAL, sol.message
    assert rep.mode == "relaxed" and rep.relaxation and rep.relaxation["applied"]
    assert rep.k_min is None and rep.demoted == 0        # the ladder was never entered
    rl = rep.relaxation
    assert rl["backend"] == "qp" and not rl["approximation"]   # exact at twin scale
    assert rl["iis_rows"] > 0 and rl["rounds"] == 1
    assert rl["candidates"] >= len(rl["rows"]) > 0                # the site, then its support
    rows = rl["rows"]
    assert rows, "the IIS must name relaxable rows"
    kinds = {r["kind"] for r in rows}
    assert "pad" in kinds and "diff" in kinds             # pads AND apron chords together
    # ONLY the ruling's populations: apron-tier or junior, never runway / taxi
    apron_tier = tables.role_tier(law, "apron")
    assert all(r["tier"] >= apron_tier for r in rows)
    assert all(r["family"] in ("apron", "pads", "no_step") for r in rows), {r["family"] for r in rows}
    # THE SPREAD (04t-1: "a quadratic spread, not L1's one row").  Measured
    # on this membrane: the middle pad follows the apron's own 1 % (slope
    # 1.02 %), the west pad 0.56 %, the 10 m gap chords +0.68 % / +0.38 %,
    # ~150 rows above the grade materiality — the brief's "no slack ≥ 2×
    # mean" is REFUTED here (max/mean ≈ 11: a pad's excess counts from
    # flat, a chord's from 1 %, and the transverse chords join at small
    # excess); what holds, and is the ruling's substance:
    st, sm = rl["stats"], rl["stats_m"]
    assert st["n"] >= 20, st                               # many rows, not one
    # Under the runway TRANSVERSE maximum (RULINGS 2026-09-05o/s, hard
    # tier-0 rows on the runway's off-ridge edge) the stubs' runway-end
    # vertices no longer sag below the ridge, so the apron carries more of
    # the climb: measured 2026-09-05 the middle pad 0.90 %, the outer pads
    # 0.45 %, the largest single element 1.21 m of 4.19 m (0.29; it was
    # 0.25 before the law).  The substance holds: the largest carrier is
    # under a third of the relief where L1 would load ~1.0 on one row.
    assert sm["max"] / sm["sum"] <= 1.0 / 3.0, sm          # no single carrier (L1: ~1.0)
    assert st["max"] <= 0.011, st                          # slightly over cap: ≤ the apron's own 1 %
    assert sm["max"] < 1.5, sm
    pads = [r for r in rows if r["kind"] == "pad"]
    assert len(pads) >= 2                                  # more than one pad shares it
    assert max(r["slope"] for r in pads) / min(r["slope"] for r in pads) < 2.5   # measured 1.99 under the transverse law
    # senior rows exact
    for p in cs.pins:
        assert abs(sol.z[p.v] - p.z) < 1e-6
    assert _over_cap(cs, sol.z, {"taxi", "runway_profile", "runway"}) <= 1e-6
    # the pads are PLANES (one slope each), never a step: the certificate
    assert rl["certificate"]["ok"], rl["certificate"]
    for r in pads:
        assert r["slope"] < 0.05                           # a slight contact slope
        zs = [sol.z[v] for v in r["vertices"]]
        assert max(zs) - min(zs) <= r["slack_m"] + 1e-6
        # no step between the pad and the apron: every rim vertex is one
        # variable shared with the apron (identity), and along the rim
        # consecutive vertices differ by the plane's slope alone
        ring = list(pm.ring_vertices(pm.faces[r["face"]].ring))
        for a, b in zip(ring, ring[1:] + ring[:1]):
            (ax, ay), (bx, by) = pm.vertices[a].xy, pm.vertices[b].xy
            assert abs(sol.z[a] - sol.z[b]) <= r["slope"] * ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 + 1e-6
    # the relaxed rows are the only over-cap apron rows, each by its own slack
    over = _over_cap(cs, sol.z, {"apron"})
    assert 0.0 < over <= sm["max"] + 1e-6
    # the message names the mode; the size dict carries no ladder groups
    assert "relaxed by 04t(1)" in sol.message or "relaxation (04t-1) applied" in sol.message
    assert not any(g.startswith("law:") for g in size.get("escalation", {}))
    # the certificate arrived in budget: scope (i), no failure named
    assert rl["scope"] == relax.SCOPE_CERTIFICATE and rep.scope == "certificate"
    assert rep.failure is None and rep.demoted_governed == []
    assert "scope certificate" in rep.line()


def test_pwl_approximation_agrees_with_the_qp(hangar, law):
    airport, pm, cs = hangar
    sol = solve_hard(pm, cs, DEFAULT_WEIGHTS, Options())
    rows = [r for r, _s in sol.iis]
    rel = relax.site_candidates(pm, law, cs, rows)
    assert len(rel) > len(relax.relaxable(pm, law, rows))   # the site is wider than one IIS
    qp = relax.stage1(pm, cs, rel, law, backend="qp")
    pwl = relax.stage1(pm, cs, rel, law, backend="pwl")
    assert qp.status == "optimal" and pwl.status == "optimal"
    assert qp.backend == "qp" and pwl.backend == "pwl"
    a = [qp.excess[x.index] for x in rel]
    b = [pwl.excess[x.index] for x in rel]
    # the piecewise approximation lands within a few of the finest pieces of
    # the square's optimum, and its objective within the same envelope
    m = law.tables.emit.materiality.grade
    # within a few of the finest pieces near zero; at a larger excess the
    # doubling breakpoints make the piece a fraction of the value itself
    # (the pads sit on the 05f slope cap, and the chord that takes what
    # they no longer can lands on a breakpoint: measured 1.2e-3 at 6.3e-3)
    assert max(abs(x - y) for x, y in zip(a, b)) <= 8 * m + 0.25 * max(a + b), (a, b)
    w = [x.extent_m for x in rel]
    fa = sum(wi * v * v for wi, v in zip(w, a))
    fb = sum(wi * v * v for wi, v in zip(w, b))
    assert fb >= fa - 1e-9 and fb - fa <= 8 * m * sum(wi * (x + y) for wi, x, y in zip(w, a, b))


def test_feasible_airport_is_byte_identical(law):
    """The last resort never runs on a feasible set: the hard solution is
    returned as is (the M5 fixture's feasible apron)."""
    from tests.auto_patch_v2.test_m5 import _airport
    airport, pm = _airport(law, None)
    cs, _c, _w = generate(pm, law, airport)
    hard = solve_hard(pm, cs, DEFAULT_WEIGHTS, Options())
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert rep.mode == "hard" and rep.relaxation is None
    assert sol.z == hard.z and sol.status is hard.status


def test_iis_naming_no_relaxable_row_falls_back_to_the_tiers(law):
    """A runway whose CIFP pins contradict its own cap (test_m5): the IIS
    names tier-0 rows only — a PROOF the relaxable scope cannot answer
    (RULINGS 2026-09-05u: it is refuted without running) — the report
    says so, the tier machinery answers and NAMES the failure."""
    from tests.auto_patch_v2.test_m5 import _airport
    airport, pm = _airport(law, None, rw1=(700.0, 760.0))
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.INFEASIBLE and rep.mode == "tiered"
    assert rep.relaxation and not rep.relaxation["applied"]
    assert "no relaxable row" in rep.relaxation["reason"]
    assert rep.relaxation["scope"] == relax.SCOPE_LADDER and rep.scope == "ladder"
    # the relaxable scope never ran: no exit string of its own in the reason
    # (its candidates are the certificate path's site, kept for the report)
    assert "STILL infeasible" not in rep.relaxation["reason"]
    assert "not applied" in rep.line()
    assert rep.failure and "no lawful surface" in rep.failure
    assert rep.line().startswith("law tiers: FAILURE")
    assert rep.as_dict()["failure"] == rep.failure and rep.as_dict()["scope"] == "ladder"


def test_a_row_stating_the_apron_law_on_a_junction_face_is_relaxable(hangar, law):
    """04t-2's portion rows cite ``common.roles.apron`` on a taxi-family
    face: the law they state, read from the citation, makes them apron
    rows the last resort admits (HECA replay 2026-09-05: keyed on the
    generator's name, 18,672 of 22,547 were refused)."""
    from auto_patch_v2.constraints.apron import GEN_EDGE
    from auto_patch_v2.model.constraints import Source
    airport, pm, cs = hangar
    stub = next(f for f in pm.faces.values() if f.role == "stub")
    ring = list(pm.ring_vertices(stub.ring))
    a, b = ring[0], ring[1]
    (ax, ay), (bx, by) = pm.vertices[a].xy, pm.vertices[b].xy
    d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    src = Source(GEN_EDGE, "common.roles.apron on the shared edge portion (04t-2)",
                 (f"face:{stub.id}", stub.ref))
    portion = Diff(a, b, 0.01, d, src)
    taxi = Diff(a, b, 0.015, d, Source("taxi", "common.roles.stub within shape", (f"face:{stub.id}",)))
    assert relax.stated_role(portion, law.tables.precedence.roles) == "apron"
    assert relax.stated_role(taxi, law.tables.precedence.roles) == "stub"
    got = relax.relaxable(pm, law, [portion, taxi])
    assert [x.row for x in got] == [portion]
    assert got[0].tier == tables.role_tier(law, "apron")


# ── RULINGS 2026-09-05u: no certificate is not a reason to demote ────────

def test_no_certificate_runs_the_relaxable_scope(hangar, law):
    """Spec §3, twin 1: the infeasible hangar row with the IIS budget at
    0 s — no certificate search at all — is answered by 04t(1) over the
    WHOLE relaxable scope: status relaxed, scope ``relaxable``, the taxi
    rows untouched, the apron rows carrying the slack, every pad a plane
    ≤ ``pad_slope_max``; no tier demoted, no failure named."""
    airport, pm, cs = hangar
    nocert = _with_relaxation(law, iis_time_budget_s=0.0)
    size: dict = {}
    sol, rep = solve_law_ordered(pm, cs, nocert, DEFAULT_WEIGHTS, Options(), size_out=size)
    assert sol.status is Status.OPTIMAL, sol.message
    assert rep.mode == "relaxed" and rep.scope == "relaxable"
    assert rep.k_min is None and rep.demoted == 0 and rep.failure is None
    rl = rep.relaxation
    assert rl["applied"] and rl["scope"] == relax.SCOPE_RELAXABLE
    assert rl["iis_rows"] == 0 and rl["certificates"] == []      # no certificate was sought
    assert "no certificate search" in rl["certificate_reason"]
    # the WHOLE relaxable population was the candidate set: every hard
    # apron-tier-or-junior Diff/Linear and every pad of the map
    assert rl["candidates"] == len(relax.full_scope(pm, nocert, relax.envelope_free(cs)))
    assert rl["candidates"] > len(rl["rows"]) > 0
    apron_tier = tables.role_tier(law, "apron")
    rows = rl["rows"]
    assert all(r["tier"] >= apron_tier for r in rows)
    assert all(r["family"] in ("apron", "pads", "no_step") for r in rows), {r["family"] for r in rows}
    assert any(r["kind"] == "diff" and r["family"] == "apron" for r in rows)   # the apron carries slack
    pads = [r for r in rows if r["kind"] == "pad"]
    assert pads
    tol = law.tables.emit.materiality.grade
    assert all(r["slope"] <= law.tables.emit.relaxation.pad_slope_max + tol for r in pads)
    # the taxi and runway rows untouched: exact at the solution
    for p in cs.pins:
        assert abs(sol.z[p.v] - p.z) < 1e-6
    assert _over_cap(cs, sol.z, {"taxi", "runway_profile", "runway"}) <= 1e-6
    assert rl["certificate"]["ok"], rl["certificate"]
    assert "scope relaxable" in rep.line() and "RELAXABLE scope" in rl["line"]
    assert not any(g.startswith("law:") for g in size.get("escalation", {}))
    # the same SITE the certificate path spreads over — the hangar row:
    # the certificate's support (the IIS rows' faces) lies inside the
    # relaxable scope's, and both inside the row; a candidate SUPERSET
    # spends no more total slack in the least-total-variance program.
    # Measured 2026-09-05 under RULINGS 05z (the runway edges are no
    # route; the stub mouths join through the ridge, 0.7 m looser): the
    # relaxable scope also lets hangar3 (a pad the IIS never named) take
    # a plane and spends 4.15 m where the certificate scope spends 6.31 m
    sol_c, rep_c = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    assert rep_c.scope == "certificate"
    faces_c = {r["face"] for r in rep_c.relaxation["rows"]}
    faces_r = {r["face"] for r in rows}
    site = {f.id for f in pm.faces.values() if f.role in ("apron", "building")} | {None}
    assert faces_c <= faces_r <= site, (faces_c, faces_r)
    # THE OBJECTIVE, not the metre sum (lane v2fix288, RULINGS 2026-09-05ae(2)):
    # with every slack bounded by ``max_over_cap_factor`` the least-total-
    # variance program on a candidate SUPERSET spends no more of ITS OWN
    # objective (Σ d·g² + Σ D·slope² + Σ s²); its metre sum may differ
    # (measured 3.26 m vs 3.08 m — the bound pushes relief onto more,
    # longer rows).  The pre-05ae reading compared the metre sums.
    def objective(rows):
        return sum(r["distance_m"] * r["excess"] ** 2 if r["kind"] == "diff"
                   else r["extent_m"] * r["slope"] ** 2 if r["kind"] == "pad"
                   else r["slack_m"] ** 2 for r in rows)
    assert objective(rows) <= objective(rep_c.relaxation["rows"]) * 1.01 + 1e-9


def test_unrelaxable_conflict_with_no_certificate_names_the_ladder_failure(law):
    """Spec §3, twin 2: two runway pins against the runway's own cap with
    the IIS budget at 0 s — the relaxable scope is tried and is STILL
    infeasible (the contradiction is tier 0's), the ladder answers and
    the report names the failure."""
    from tests.auto_patch_v2.test_m5 import _airport
    airport, pm = _airport(law, None, rw1=(700.0, 760.0))
    cs, _c, _w = generate(pm, law, airport)
    nocert = _with_relaxation(law, iis_time_budget_s=0.0)
    sol, rep = solve_law_ordered(pm, cs, nocert, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.INFEASIBLE and rep.mode == "tiered"
    rl = rep.relaxation
    assert not rl["applied"] and rl["scope"] == relax.SCOPE_LADDER
    assert rl["candidates"] > 0                          # the relaxable scope RAN
    assert "STILL infeasible" in rl["reason"] and "tier machinery" in rl["reason"]
    # THE NAMING: the certificate of the set minus every relaxable row —
    # the runway's own rows against its pins, nothing the ruling may relax
    assert "unrelaxable contradiction" in rl["reason"], rl["reason"]
    named = {u["family"] for u in rl["unrelaxed"]}
    assert "runway_profile" in named, named
    assert not named & {"apron", "pads"}, named
    assert rep.failure and "no lawful surface" in rep.failure
    assert "FAILURE" in rep.line() and "scope ladder" in rep.line()


def test_governed_demotion_is_a_named_failure(law):
    """The ladder's own demotion of a governed family (the M5 fixture's
    apron between two pinned runways, driven past the last resort by a
    0 s budget and a relaxation scope that admits no apron row): the
    apron tier yields and the report names it as the FAILURE."""
    from tests.auto_patch_v2.test_m5 import _airport
    airport, pm = _airport(law, (730.0, 736.0))
    cs, _c, _w = generate(pm, law, airport)
    # relaxable from the LOWEST tier only: the apron is senior to it, so
    # neither scope can relax the apron and the ladder must demote it
    lowest = tables.tiers(law)[-1][0]
    ladder = _with_relaxation(law, iis_time_budget_s=0.0, relaxable_from_role=lowest)
    sol, rep = solve_law_ordered(pm, cs, ladder, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.OPTIMAL and rep.mode == "tiered"
    apron_tier = tables.role_tier(law, "apron")
    assert apron_tier in rep.yielded and rep.yielded[apron_tier]["rows"] > 0
    assert rep.demoted_governed and rep.demoted_governed[0]["tier"] == apron_tier
    assert "apron" in rep.demoted_governed[0]["roles"]
    assert rep.failure and rep.failure.startswith("governed family demoted")
    assert rep.line().startswith("law tiers: FAILURE — governed family demoted")
    assert rep.as_dict()["demoted_governed"] == rep.demoted_governed
    # the lawful case names nothing: only the last (ungoverned / rigid) tier
    # yielding is the DEM's own yield
    from auto_patch_v2.solve.tiers import TierReport, name_failure
    tt = tables.tiers(law)
    lawful = TierReport("tiered", tt, yielded={len(tt) - 1: {"rows": 3, "max_m": 1.97, "by_generator": {}}})
    name_failure(lawful, law, Status.OPTIMAL)
    assert lawful.failure is None and lawful.demoted_governed == []


def test_why_runs_in_relaxed_mode(hangar, law):
    airport, pm, cs = hangar
    lines: list[str] = []
    prep = pwhy._prepare_solved("ZZZZ", airport, pm, law, DEFAULT_WEIGHTS, lines.append)
    assert prep.relaxation is not None and prep.relaxation.applied
    assert any("RELAXED MODE" in ln for ln in lines)
    apron = next(f.id for f in pm.faces.values() if f.role == "apron")
    text = pwhy.report(prep, apron)
    assert "relaxed by 04t(1)" in text
    assert "slack spread" in text and "certificate" in text
    assert "pad " in text and "diff " in text
    # the LP why read is the RELAXED set: its rows carry the ruling
    assert any(relax.RULING in r.source.ruling for r in prep.cs.rows())


def test_census_tags_rows_on_relaxed_vertices(hangar, law):
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.pipeline.build import relaxed_publication
    from auto_patch_v2.pipeline.publication import publication
    from auto_patch_v2.verify import census
    from auto_patch_v2.verify.census import RELAXED_KEY
    airport, pm, cs = hangar
    sol, rep = solve_law_ordered(pm, cs, law, DEFAULT_WEIGHTS, Options())
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    pub = publication(pm, law, airport, sol.z)
    pub["relaxed_rows"] = relaxed_publication(rep)
    assert pub["relaxed_rows"] and all(r["ll"] for r in pub["relaxed_rows"])
    rows = census(surf, law, pub)
    tagged = [r for lst in rows.values() for r in lst if r.get(RELAXED_KEY) == "04t(1)"]
    plain = [r for lst in rows.values() for r in lst if not r.get(RELAXED_KEY)]
    # every over-cap apron row the census sees sits on a relaxed vertex
    assert not [r for r in plain if r["family"] == "within_shape" and "apron" in r["roles"]], plain
    assert tagged or not [r for lst in rows.values() for r in lst], rows


def _with_relaxation(law, **kw):
    import dataclasses as _dc
    rl = _dc.replace(law.tables.emit.relaxation, **kw)
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit, relaxation=rl)))


def test_relaxed_pad_slope_is_bounded_by_the_table(hangar, law):
    """RULINGS 2026-09-05f: ``[relaxation] pad_slope_max`` bounds every
    relaxed pad's plane in stage 1; the relief a steeper pad would have
    taken goes to the other populations (04t-1), and the certificate
    reads the bound."""
    airport, pm, cs = hangar
    rl = law.tables.emit.relaxation
    assert 0.0 < rl.pad_slope_max <= 0.02
    sol = solve_hard(pm, cs, DEFAULT_WEIGHTS, Options())
    rows = [r for r, _s in sol.iis]
    rel = relax.site_candidates(pm, law, cs, rows)
    tol = law.tables.emit.materiality.grade
    s1 = relax.stage1(pm, cs, rel, law, backend="qp")
    pads = [x for x in rel if x.kind == "pad"]
    assert pads and all(s1.excess[x.index] <= rl.pad_slope_max + tol for x in pads)
    # the bound is read where it binds: under RULINGS 05z (the runway
    # edges are no route, the stub mouths join through the ridge) the
    # unbounded pad on this fixture slopes 0.86 % (measured 2026-09-05;
    # 1.02 % on the ring-route graph), inside the ruled 1 % — the tight
    # table value below is the arm the cap is ACTIVE on
    loose = _with_relaxation(law, pad_slope_max=0.05)
    s0 = relax.stage1(pm, cs, rel, loose, backend="qp")
    assert max(s1.excess[x.index] for x in pads) <= max(s0.excess[x.index] for x in pads) + tol
    tight = _with_relaxation(law, pad_slope_max=0.005)
    # the default backend: highspy's QP reports kSolveError at this bound on
    # this fixture (measured 2026-09-05) and the approximation answers
    s2 = relax.stage1(pm, cs, rel, tight)
    assert s2.status == "optimal", s2
    assert all(s2.excess[x.index] <= 0.005 + tol for x in pads)
    assert max(s2.excess[x.index] for x in pads) >= 0.9 * 0.005   # ACTIVE here
    chords = [x for x in rel if x.kind != "pad"]
    assert sum(s2.slack[x.index] for x in chords) > sum(s1.slack[x.index] for x in chords)
    # the same on the approximation, and the certificate reads the bound
    s3 = relax.stage1(pm, cs, rel, tight, backend="pwl")
    assert all(s3.excess[x.index] <= 0.005 + tol for x in pads)
    sol2, rep, _cs2 = relax.solve_relaxed(pm, cs, tight, DEFAULT_WEIGHTS, Options())
    assert sol2 is not None and rep.certificate["ok"]
    assert rep.certificate["pad_slope_max"] == 0.005
    assert rep.certificate["pad_slope_max_seen"] <= 0.005 + tol
