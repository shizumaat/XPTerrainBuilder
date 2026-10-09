"""Twins for flat-pad spec v2 §1 / §2 / §5 (owner RULINGS 2026-09-30y,
30as; lane ``flatpad128v3``, issue #128): THE RUNWAY FLEXES 20 % OF THE
PULL INSIDE A HARD BUDGET, THE DATUM IS CERTIFIED BY A PAIR-GRAPH
INTERVAL, THE FRONTING SET'S CAPS ARE HARD.

1. ``reach_anchored`` IS ``reach`` at zero width, widens by exactly the
   anchor's width, and without transit equals the transit read whenever
   the anchors are consistent (the triangle inequality) — and is NOT
   collapsed by an inconsistent anchor pair behind it.
2. THE INTERVAL on a synthetic pair graph: a frontage whose two ends are
   anchored 5.99 m apart over 344 m (1.74 % > 1.5 %) is EMPTY at share 0
   and non-empty once the runway term is widened enough.
3. THE FLEX BUDGET on a synthetic airport (a runway, an apron touching it,
   a held pad): with the hold the runway moves by at most ``beta_R`` (+
   ``hard_tol_m``); at ``runway_flex_share = 0`` by at most
   ``hard_tol_m``; with no held block pass 1b never runs and the solve is
   the hold-less solve exactly.
4. THE FRONTING PROMOTION is the one filter: an airside pair cap whose
   every foot is on ``PlanarMap.fronting_vertices`` joins the hard set.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, routes as R
from auto_patch_v2.constraints.no_step import (FLEX_RULING, hold_pass,
                                               pair_graph)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design

RUN_LEN = 1600.0
HALF_W = 22.5


# ── 1. the anchored reach ────────────────────────────────────────────────

def _graph(n: int, seed: int) -> R.RouteGraph:
    rng = np.random.default_rng(seed)
    a, b = [], []
    for v in range(1, n):
        a.append(int(rng.integers(0, v)))
        b.append(v)
    for _ in range(n):
        x, y = sorted(int(t) for t in rng.integers(0, n, 2))
        if x != y:
            a.append(x)
            b.append(y)
    a, b = np.array(a), np.array(b)
    return R.RouteGraph(n=n, nodes=frozenset(range(n)), a=a, b=b,
                        length=rng.uniform(5, 80, len(a)),
                        cap=rng.choice([0.015, 0.03, 0.05], len(a)),
                        kind=np.full(len(a), R.CENTRELINE),
                        station=np.ones(n, bool))


def test_anchored_reach_at_zero_width_is_the_reach():
    g = _graph(200, 11)
    rng = np.random.default_rng(5)
    pins = {int(v): float(rng.uniform(10, 40)) for v in rng.choice(200, 90, replace=False)}
    ref = R.reach(g, pins)
    ar = R.reach_anchored(g, {v: (z, 0.0) for v, z in pins.items()})
    for v, (lo, hi) in ref.items():
        assert abs(ar.lo[v] - lo) < 1e-9 and abs(ar.hi[v] - hi) < 1e-9


def test_anchored_reach_widens_by_the_width():
    g = _graph(120, 3)
    anchors = {0: (20.0, 0.0)}
    a0 = R.reach_anchored(g, anchors)
    a1 = R.reach_anchored(g, {0: (20.0, 0.7)})
    fin = np.isfinite(a0.hi[:g.n])
    assert np.allclose(a1.hi[fin] - a0.hi[fin], 0.7)
    assert np.allclose(a0.lo[fin] - a1.lo[fin], 0.7)


def test_no_transit_equals_transit_on_consistent_anchors():
    g = _graph(150, 9)
    # anchors from ONE Lipschitz surface: consistent by construction
    base = R.reach_anchored(g, {0: (50.0, 0.0)})
    picks = [5, 17, 33, 80, 101]
    anchors = {0: (50.0, 0.0), **{v: (float(base.lo[v]) + 0.5 * (float(base.hi[v])
                                                                  - float(base.lo[v])), 0.0)
                                  for v in picks}}
    t = R.reach_anchored(g, anchors)
    nt = R.reach_anchored(g, anchors, transit=False)
    others = [v for v in range(g.n) if v not in anchors and np.isfinite(t.hi[v])]
    assert np.allclose(t.lo[others], nt.lo[others]) and np.allclose(t.hi[others], nt.hi[others])


def test_no_transit_is_not_collapsed_behind_an_inconsistent_pair():
    # a chain 0 - 1 - 2 - 3, 100 m at 1 %: anchors 1 and 2 stand 10 m apart
    # over a 1 m budget (inconsistent); vertex 0 hangs off anchor 1 alone
    g = R.RouteGraph(n=4, nodes=frozenset(range(4)), a=np.array([0, 1, 2]),
                     b=np.array([1, 2, 3]), length=np.full(3, 100.0),
                     cap=np.full(3, 0.01), kind=np.full(3, R.CENTRELINE),
                     station=np.ones(4, bool))
    anchors = {1: (0.0, 0.0), 2: (10.0, 0.0)}
    t = R.reach_anchored(g, anchors)
    nt = R.reach_anchored(g, anchors, transit=False)
    assert t.lo[0] > t.hi[0]                          # the contradiction reaches 0
    assert nt.lo[0] <= nt.hi[0]                       # first-hit: it does not
    assert abs(nt.lo[0] + 1.0) < 1e-9 and abs(nt.hi[0] - 1.0) < 1e-9


# ── 2. the interval on a pair graph ──────────────────────────────────────

class _PM:
    """The pair graph reads ``planar.vertices`` for its size only."""

    def __init__(self, n: int):
        self.vertices = {i: None for i in range(n)}


def _frontage(beta: float) -> tuple[float, float]:
    """Two runway anchors 0 and 5 (5.99 m apart) each 10 m of 1.5 % taxi
    from a frontage 344 m long (contacts 2 and 3, one datum): the interval
    of the frontage's datum."""
    src = Source("taxi", "rulesets.taxi.longitudinal centreline", ())
    cs = ConstraintSet(diffs=(
        Diff(0, 1, 0.015, 10.0, src), Diff(1, 2, 0.015, 1e-3, src),
        Diff(2, 3, 0.015, 344.0, src),               # the frontage itself
        Diff(3, 4, 0.015, 1e-3, src), Diff(4, 5, 0.015, 10.0, src)))
    g = pair_graph(_PM(6), cs, frozenset(range(6)),
                   frozenset({"rulesets.taxi.longitudinal centreline"}))
    anchors = {0: (0.0, beta), 5: (5.99 + 344.0 * 0.0, beta)}
    ar = R.reach_anchored(g, anchors, transit=False)
    # one datum for both contacts: they are HELD equal, so the frontage
    # row is not in the hold set's metric (the hold overrides it)
    lo = max(float(ar.lo[2]), float(ar.lo[3]))
    hi = min(float(ar.hi[2]), float(ar.hi[3]))
    return lo, hi


def test_a_174_percent_frontage_is_empty_until_the_runway_term_widens():
    # without the frontage row: contact 2 bound by anchor 0 only (the
    # no-transit read), contact 3 by anchor 5 — B = 0.15 m each side
    lo, hi = _frontage(0.0)
    assert lo > hi, (lo, hi)                          # EMPTY at share 0
    gap = lo - hi
    lo2, hi2 = _frontage(0.5 * gap + 1e-6)
    assert lo2 <= hi2                                 # widened enough: NOT empty


# ── 3. the flex budget on a synthetic airport ────────────────────────────

class _Dem:
    """The ground rises 1 % west to east under the apron and the pad, so
    the pad's frontage is not level in pass 1a and the hold must lift."""

    provenance = {"synthetic": "flatpad128v3"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + (0.01 * x if y > HALF_W else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _airport(law, startups=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 2 * HALF_W, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), tuple(startups), (), (), (), pack, _Dem(), law.ruleset_key)


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(-300.0, HALF_W, 300.0, 180.0), (),
             None, None, "airside", "apron", {}),
        Cell(2, "building", "padA", _rect(-150.0, 180.0, 150.0, 260.0), (),
             None, None, "airside", "pad", {}),
    ]


def _arm(law, **design):
    d0 = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit,
                                     design=_dc.replace(d0, **design))))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def built(law):
    airport = _airport(law)
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


def _runway_v(pm):
    return sorted({v for f in pm.faces.values() if f.role in ("runway", "runway_crossing")
                   for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)})


def _strip(cs):
    from auto_patch_v2.constraints.platform import HOLD_RULING
    return ConstraintSet.from_rows([r for r in cs.rows()
                                    if r.source.ruling.split(" (")[0].strip() != HOLD_RULING])


def _solve(pm, cs, lw, hold: bool):
    kw = {"hold": hold_pass(pm, lw)} if hold else {}
    sol, rep = solve_design(pm, cs, lw, **kw)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return np.asarray(sol.z, float), rep


def test_the_fixture_holds_a_block(law, built):
    from auto_patch_v2.model.platform import datum_vertices
    pm, _cs = built
    assert datum_vertices(pm, law), "the fixture's pad is a held block"


def test_the_runway_is_never_pulled_by_a_pad(law, built):
    """Owner RULINGS 2026-10-02ag (1) ("pad stays flat, apron twists to weld
    to it ... the pad area just has to be blended into the rest of the
    apron"): no pad earns a runway budget — beta_R = 0, ``runway_flex``
    reports no pulled runway, and every runway column sits at its pass-1a
    value under the hold (the 30as 20 % share is withdrawn with the pull)."""
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    tol = float(lw.tables.emit.design.hard_tol_m)
    z0, _r0 = _solve(pm, _strip(cs), lw, hold=False)      # pass 1a's runway
    hp = hold_pass(pm, lw)
    sol, rep = solve_design(pm, cs, lw, hold=hp)
    z1 = np.asarray(sol.z, float)
    assert "stage1a" in rep.stages                     # pass 1a ran
    rw = _runway_v(pm)
    moved = max(abs(z1[v] - z0[v]) for v in rw)
    assert not rep.runway_flex                         # nothing pulls
    assert moved <= tol, moved
    assert FLEX_RULING in lw.tables.emit.design.hard_rulings
    assert hp.result.stats["runway_bands_unpulled"] == hp.result.stats["runway_bands"]


def test_share_zero_holds_the_runway(law, built):
    pm, cs = built
    lw = _arm(law, staged_solve=True, runway_flex_share=0.0)
    tol = float(lw.tables.emit.design.hard_tol_m)
    z0, _ = _solve(pm, _strip(cs), lw, hold=False)
    z1, rep = _solve(pm, cs, lw, hold=True)
    rw = _runway_v(pm)
    assert max(abs(z1[v] - z0[v]) for v in rw) <= tol
    assert all(r["budget_m"] == 0.0 for r in rep.runway_flex)


def test_no_held_block_is_the_holdless_solve(law, built, monkeypatch):
    """No hold row -> ``HoldPass.strip`` is None -> pass 1a IS stage 1 and
    nothing else runs: the SAME surface as ``hold=None``, bit for bit."""
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    cs0 = _strip(cs)
    za, ra = _solve(pm, cs0, lw, hold=False)
    zb, rb = _solve(pm, cs0, lw, hold=True)
    assert "stage1a" not in rb.stages and not rb.runway_flex
    assert np.array_equal(za, zb)


def test_evaluation_ii_runs_at_most_once(law, built, monkeypatch):
    from auto_patch_v2.constraints import no_step, routes
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    calls: list[int] = []
    real = routes.reach_anchored

    def spy(g, anchors, transit=True):
        calls.append(1)
        return real(g, anchors, transit)
    monkeypatch.setattr(routes, "reach_anchored", spy)
    _solve(pm, cs, lw, hold=True)
    # I0, R(c), the precondition read, the fronting read, and at most ONE
    # widened evaluation (ii)
    assert len(calls) <= 5, len(calls)


# ── 4. the fronting promotion ────────────────────────────────────────────

def test_the_fronting_set_promotes_its_caps(law, built):
    from auto_patch_v2.solve.design import assemble, stage_split
    from auto_patch_v2.solve.design_report import DesignReport
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    drop, fixed = stage_split(pm, cs, lw)
    r0 = DesignReport()
    assemble(pm, cs, lw, r0, drop=drop, fixed=fixed)
    assert r0.fronting_promoted == 0                   # nothing published
    apron = {v for f in pm.faces.values() if f.role == "apron"
             for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)}
    # the promotion reads pass 1a's values (RULINGS 2026-09-30bb F2): a
    # cap is promoted only where the reference already holds it
    z1a, _ = _solve(pm, _strip(cs), lw, hold=False)
    pm1 = _dc.replace(pm, fronting_vertices=frozenset(apron),
                      fronting_ref={v: float(z1a[v]) for v in apron})
    pm_none = _dc.replace(pm, fronting_vertices=frozenset(apron))
    rn = DesignReport()
    assemble(pm_none, cs, lw, rn, drop=drop, fixed=fixed)
    assert rn.fronting_promoted == 0          # no reference: nothing promoted
    r1 = DesignReport()
    b1 = assemble(pm1, cs, lw, r1, drop=drop, fixed=fixed)
    assert r1.fronting_promoted > 0
    r0b = DesignReport()
    b0 = assemble(pm, cs, lw, r0b, drop=drop, fixed=fixed)
    assert len(b1.hard) - len(b0.hard) >= r1.fronting_promoted


# ── 5. the stand-line plateau (§3) and the §20 pad (§4) ─────────────────

def _cells_full():
    """The base fixture plus a §20 CONFORMING pad (800 m², under
    ``cluster_pad_min_m2``) fronting the same apron."""
    return _cells() + [
        Cell(3, "building", "padB", _rect(200.0, 180.0, 240.0, 200.0), (),
             None, None, "airside", "pad", {}),
    ]


@pytest.fixture(scope="module")
def built_full(law):
    from auto_patch_v2.model.airport import Startup
    gate = Startup("G1", (0.0, 140.0), 180.0, "gate")
    airport = _airport(law, startups=(gate,))
    pm, _st = build(airport, Classification(tuple(_cells_full()), (), {}, ()), law)
    from auto_patch_v2.model.platform import HELD, PLATEAUS
    held, plateaus = {k: dict(v) for k, v in HELD.items()}, dict(PLATEAUS)
    cs, _c, _w = generate(pm, law, airport)
    pm0, _st0 = build(_airport(law), Classification(tuple(_cells_full()), (), {}, ()), law)
    # the registries are the LAST arrangement's: restore the stand arm's
    HELD.clear()
    HELD.update(held)
    PLATEAUS.clear()
    PLATEAUS.update(plateaus)
    return pm, cs, pm0, plateaus


def test_the_stand_cuts_a_plateau_and_renodes_nothing_else(law, built_full):
    from auto_patch_v2.model.planar import PLATEAU_MARK
    pm, _cs, pm0, plateaus = built_full
    assert "padA" in plateaus and plateaus["padA"]["source"] == "startups"
    faces = [f for f in pm.faces.values() if PLATEAU_MARK in str(f.ref)]
    assert faces and all(f.role == "apron" for f in faces)
    key = lambda pmx: {vx.key for vx in pmx.vertices.values()}
    k1, k0 = key(pm), key(pm0)
    ring = {pm.vertices[v].key for f in faces for r in (f.ring, *f.holes)
            for v in pm.ring_vertices(r)}
    assert not (k0 - k1), "the cut deleted a vertex"
    assert (k1 - k0) <= ring, "the cut minted a vertex off the plateau ring"


def test_the_plateau_is_not_pulled_to_the_datum(law, built_full):
    """Owner RULINGS 2026-10-02ag (1): the only airside vertices a pad may
    move are its welded CONTACTS (to D); a plateau vertex is an apron
    INTERIOR vertex and takes no hold row — the apron around the contacts
    blends under its own caps instead (flat-pad spec v2 §3's stand line is
    withdrawn with the pull)."""
    from auto_patch_v2.constraints.platform import HOLD_RULING
    from auto_patch_v2.model.platform import plateau_vertices
    pm, cs, _pm0, _p = built_full
    lw = _arm(law, staged_solve=True)
    hp = hold_pass(pm, lw)
    _sol, _rep = solve_design(pm, cs, lw, hold=hp)
    pv = set(plateau_vertices(pm, lw)["padA"])
    assert pv
    contacts = {o for o, _z in hp.result.blocks["padA"]["weld"] and
                [(o, None) for o in hp.result.blocks["padA"]["weld"]]}
    touched = set()
    for r in hp.result.rows:
        if r.source.ruling.split(" (")[0].strip() != HOLD_RULING:
            continue
        for term in getattr(r, "terms", ()):
            touched.add(int(term[0]))
    assert not (touched & (pv - contacts)), "a plateau vertex carries a hold row"


def test_a_conforming_pad_is_held_flat(law, built_full):
    """Owner RULINGS 2026-10-02ag (1): the pad STAYS FLAT at the apron's own
    frontage level — the datum column holds exactly the level
    ``hold_interval`` chose (the median of the contacts' pass-1a value; the
    apron-tier ``frontage_hold datum`` row is never the relaxed one) — and
    the apron twists to weld to it.  A contact the airside's own anchors
    cannot bring to D (this fixture's apron shares RUNWAY ring vertices,
    held at pass 1a by the zero-budget flex Bands) keeps its own level with
    its hold relaxed in the pad tier and is REPORTED, never a lift of the
    runway; the pad's interior stays on D."""
    from auto_patch_v2.model.platform import HELD, datum_vertices
    pm, cs, _pm0, _p = built_full
    assert HELD.get("padB", {}).get("conforming")
    lw = _arm(law, staged_solve=True)
    z, _rep = _solve(pm, cs, lw, hold=True)
    tol = float(lw.tables.emit.design.hard_tol_m)
    dv = datum_vertices(pm, lw)["padB"]
    D = z[dv]
    # round 5 (owner 2026-10-02): the datum is a FREE column — the record's
    # datum IS the solved column (no pin to disagree with); the median is
    # only the soft preference's target
    from auto_patch_v2.constraints.platform import _conforming_records
    rec = {r["ref"]: r for r in _conforming_records(pm, lw, z)}["padB"]
    assert abs(rec["datum"] - D) <= 1e-3
    assert rec["datum_median"] == HELD["padB"]["datum_chosen"]
    # spec §56 (3): the record carries the pad's area (the warning's slot)
    # and the warning's verdict — the faces' own area, holes out
    from auto_patch_v2.planar.index import face_polygon
    assert rec["pad_m2"] == round(sum(face_polygon(pm, q).area for q, f in pm.faces.items()
                                      if f.ref == "padB"), 1) > 0.0
    assert rec["warned"] is False and rec["warning"] is None
    assert rec["welded"] + rec["released"] == rec["held_contacts"]
    assert rec["released"] == 0 or rec["needs_split"]
    contacts = {o for o, _z in HELD["padB"].get("hold_contacts", [])}
    vs = {v for f in pm.faces.values() if f.ref == "padB"
          for r in (f.ring, *f.holes) for v in pm.ring_vertices(r)}
    off = {v for v in contacts if abs(z[v] - D) > tol + 1e-6}
    # an own vertex not welded beside a relaxed contact is on the datum
    import itertools
    nbr = set()
    for f in pm.faces.values():
        if f.ref != "padB":
            continue
        for ring in (f.ring, *f.holes):
            rv = list(pm.ring_vertices(ring))
            for a, b in zip(rv, rv[1:] + rv[:1]):
                if a in off:
                    nbr.add(b)
                if b in off:
                    nbr.add(a)
    interior = vs - contacts - nbr
    # this 4-vertex fixture pad has both own vertices beside a runway-shared
    # contact, so the interior claim is empty here; the datum line above
    # carries the ruling (and the SPJC build: every held pad's own ring on
    # its datum)
    if interior:
        assert max(abs(z[v] - D) for v in interior) <= tol + 1e-6
    assert off <= contacts
    assert bool(off) == bool(rec["needs_split"])

def test_a_weld_left_off_its_datum_by_the_solve_is_sealed_and_recorded(law, built):
    """Owner RULINGS 2026-10-08c (4) / 08d (2) (``constraints/weld_floor``):
    after the solve every hard weld stands on its datum within the
    tolerance; a contact the solve left 0.05 m off is put ON it by the weld
    projection (``HoldPass.seal``) and recorded in its block's
    ``weld_widened`` with the move; a runway-family contact is never moved."""
    from auto_patch_v2.model.platform import HELD
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    tol = float(lw.tables.emit.design.hard_tol_m)
    hp = hold_pass(pm, lw)
    sol, rep = solve_design(pm, cs, lw, hold=hp)
    z = np.asarray(sol.z, float)
    welds = hp.result.welds
    assert welds and "weld_seal" in rep.stages["stage1a"]
    assert max(abs(z[c] - z[dv]) for c, dv, _p in welds) <= tol + 1e-9
    levels = {int(v): float(z[v]) for v in range(len(z))}
    c, dv, pref = welds[0]
    levels[c] = levels[dv] + 0.05
    got = hp.seal(levels)
    assert got["contacts"] == 1 and abs(got["max_m"] - 0.05) < 1e-9
    assert levels[c] == levels[dv]
    w = HELD[pref]["weld_widened"]
    assert w["sealed"] == 1 and [*pm.vertices[c].key, 0.05] in w["contacts"]
    assert hp.seal(levels)["contacts"] == 0                       # idempotent
    hp.result = _dc.replace(hp.result, never=frozenset({c}))
    levels[c] = levels[dv] + 0.05
    assert hp.seal(levels)["contacts"] == 0 and levels[c] != levels[dv]


def test_a_weld_the_lp_relaxed_is_widened_and_resolved_never_sealed(law, built, monkeypatch):
    """Spec §57 (3) (ii-c) (seat review D2): a weld pass 1b leaves 0.3 m off
    its datum — the feasibility LP relaxed it; over ``[design] seal_max_m``,
    under the terrace floor — is NOT assigned its datum.  It is a misfit the
    pair graph did not see: the contact joins the block's gives with what it
    is off, the pavement rows naming it are widened and pass 1b is solved
    ONCE more; the weld then stands (released 0) and nothing is sealed."""
    from auto_patch_v2.model.platform import HELD
    from auto_patch_v2.solve import flex
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    assert float(lw.tables.emit.design.seal_max_m) == 0.05
    hp = hold_pass(pm, lw)
    solve_design(pm, cs, lw, hold=hp)
    c, dv, pref = next(w for w in hp.result.welds
                       if w[0] not in hp.result.never and w[0] not in hp.result.pinned)
    # the unit: 0.3 m off is the pavement's to give, never the seal's
    z = np.asarray(solve_design(pm, cs, lw, hold=hp)[0].z, float)
    levels = {int(v): float(z[v]) for v in range(len(z))}
    levels[c] = levels[dv] - 0.30
    assert hp.seal(dict(levels))["contacts"] == 0
    assert hp.rewiden(levels) == 1 and abs(hp.result.widen[c] - 0.32) < 1e-9
    assert HELD[pref]["weld_widened"]["relaxed"] == 1
    # the pass: stage 1 re-solves ONCE with the widened rows
    hp2 = hold_pass(pm, lw)
    calls = {"n": 0}
    real = type(hp2).rewiden

    def once(self, lv):
        calls["n"] += 1
        if calls["n"] == 1:
            lv = dict(lv)
            lv[c] = lv[dv] - 0.30               # the LP's relaxation, stood in
        return real(self, lv)
    monkeypatch.setattr(type(hp2), "rewiden", once)
    sol, rep = solve_design(pm, cs, lw, hold=hp2)
    z2 = np.asarray(sol.z, float)
    s1 = rep.stages["stage1a"]
    assert s1["weld_rewidened"] == 1 and calls["n"] == 1
    assert s1["weld_seal"]["contacts"] == 0                       # sealed 0
    tol = float(lw.tables.emit.design.hard_tol_m)
    assert abs(z2[c] - z2[dv]) <= tol + 1e-9                      # released 0
    assert HELD[pref]["weld_widened"]["rows"] > 0


def test_the_hold_pass_widens_only_the_pavement_rows_naming_a_closing_contact(law, built):
    """Owner RULINGS 2026-10-08d (2) (``constraints/weld_floor``): pass 1b and
    stage 2 state the pavement-tier rows naming a contact that closes a
    misfit block's set widened by that contact's give — and no other row:
    the same count of rows, every hold row and every row naming no such
    contact byte-identical, and the block's record carries the count."""
    from auto_patch_v2.constraints.weld_floor import pavement_heads, ruling_note
    from auto_patch_v2.model.platform import HELD
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    hp = hold_pass(pm, lw)
    solve_design(pm, cs, lw, hold=hp)
    assert not hp.result.widen                      # the fixture's frontage meets
    c, _dv, pref = hp.result.welds[0]
    heads = pavement_heads(lw)
    hp.result = _dc.replace(hp.result, widen={c: 0.4})
    hp.result.blocks[pref].update(widened=True, gives={c: 0.4})
    HELD[pref]["weld_widened"] = {"floor_m": 1.0, "contacts": [[*pm.vertices[c].key, 0.4]]}
    out = hp.widened(cs)
    a, b = list(cs.rows()), list(out.rows())
    assert len(a) == len(b)
    changed = [(x, y) for x, y in zip(a, b) if x != y]
    assert changed and HELD[pref]["weld_widened"]["rows"] == len(changed)
    for x, y in changed:
        vs = ({int(x.a), int(x.b)} if hasattr(x, "a") else {int(v) for v, _k in x.terms})
        assert c in vs and x.source.ruling.split(" (")[0].strip() in heads
        assert y.source.ruling == x.source.ruling + ruling_note
        if hasattr(x, "cap"):
            assert abs(y.bound_m - (x.bound_m + 0.4)) < 1e-9
    assert hp.widened(out) is out                   # idempotent
