"""Twins for lane ``rwyband139`` (issue #139, owner RULINGS 2026-10-02v (6)):
A TAXI-FAMILY REACH BAND NEVER CAPS A RUNWAY-FAMILY VERTEX — the runway's
edge level is the band's SOURCE, never its subject.

The reach band (04o, ``no_step.reach_band_values``) propagates the CIFP
threshold values along the route graph at the path caps and gives every
vertex it reaches a floor and a ceiling.  Where a runway edge vertex is
SHARED with a taxi-family face — HECA v1703's ``runway|stub`` class, the
same geometry the 05o transverse maximum was ruled on — the cheapest
route from a THRESHOLD to that vertex can run up the stub at the TAXI
cap, and the ceiling it delivers sits under where the runway's own law
puts the edge.  Since 05o the transverse maximum is HARD, so a ceiling
on the edge is a ceiling on the crowned RIDGE: the runway comes down to
meet a bound derived from the taxi network.

The fix is at the band's ONE derivation site: a vertex whose role set
carries a runway-family role takes the band its OWN family's routes
imply (``no_step.runway_family_routes``) and never the raw metric's.
The routes are untouched — they still TRANSIT the runway, the
thresholds are still the band's pins, and the taxi-side vertices BEYOND
the shared edge keep the full metric's band and still obey it.

WHY THE RUNWAY'S OWN BAND IS KEPT (round 2, and the whole of this
lane's red CI): the ruling's subject is a TAXI-FAMILY band.  Round 1
withdrew EVERY band on a runway-family vertex, which also withdraws the
band a runway derives from its OWN thresholds along its OWN ridge at
its own longitudinal cap — the envelope its own hard path rows already
imply, and a row the ruling does not name.  Measured: on
``test_v2smooth.valley`` and ``test_v2ground.taxi_map`` — fixtures with
no taxi centreline at all, so every one of their 202 route edges is
runway-only — all 163 bands are the runway's own, and withdrawing them
moved the graded strip's smallest fill 0.70 m -> 0.4276 m and the
``runway_profile`` family's worst miss 0.5706 m -> 0.6556 m.  Dropping
routes can only RAISE the least budget, so the runway-only band is
never tighter than the raw metric's: the narrowing only ever loosens,
and only on runway-family vertices.

THE FIXTURE is two runways joined only through the taxi network: 09/27
with both thresholds at 700 m, and a lower 09L/27R at 689.5 m reachable
from it only along ``stubC → taxiA → stubB``, whose far end is the
shared ``runway|stub`` edge vertex of 09/27.  The ceiling 689.5 delivers
there is ~3.6 m under 09/27's own thresholds — a LOW TAXI BAND CEILING,
and the fixture's whole point.

THE PRE-FIX SET is reconstructed, not re-run: the old derivation is
exactly today's plus a ``Band`` at every runway-family vertex of the raw
metric, so the two arms differ by those rows and nothing else — which is
also how the twin states "the runway rows are otherwise byte-identical".
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.constraints import generate, no_step, runway_profile
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.routes import reach, reach_anchored, routes
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import (REACH_GENERATOR, Band,
                                             ConstraintSet, Source)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.shapes import shape_stage
from auto_patch_v2.planar.build import build
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.solve import Status, solve_design
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot

#: 09/27's two thresholds (flat: its own law puts the whole ridge here).
HIGH_M = 700.0
#: 09L/27R's two thresholds — the LOW complex the band's ceiling comes from.
LOW_M = 689.5
#: The fixture's terrain, flat and above both runways (they are cut into
#: it), so nothing in the DEM pulls the ridge down.
DEM_M = 706.0


class _FlatDem:
    provenance = {"synthetic": f"flat {DEM_M} m"}

    def z(self, x: float, y: float) -> float:
        return DEM_M

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def two_runways(law):
    """09/27 at 700 m with a stub on its north edge, a parallel taxiway,
    a second stub, and 09L/27R at 689.5 m — the ONLY route between the
    two runways runs through the taxi network."""
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    hi = (RunwayEnd("09", r((-300.0, 0.0)), (60.5, -135.5), 0.0, 0.0, HIGH_M, "fixture"),
          RunwayEnd("27", r((300.0, 0.0)), (60.5, -135.5), 0.0, 0.0, HIGH_M, "fixture"))
    lo = (RunwayEnd("09L", r((-300.0, 172.5)), (60.5, -135.5), 0.0, 0.0, LOW_M, "fixture"),
          RunwayEnd("27R", r((300.0, 172.5)), (60.5, -135.5), 0.0, 0.0, LOW_M, "fixture"))
    rw_hi = Runway("09/27", 45.0, 1, hi, 3, "D")
    rw_lo = Runway("09L/27R", 45.0, 1, lo, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, HIGH_M, (rw_hi, rw_lo), (), (),
                      {}, (), (), (), (), (), (), (), pack, _FlatDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -300, -HALF_WIDTH, 300, HALF_WIDTH), (),
             3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -250, 80, 250, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 80), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "stub", "stubC", _rect(r, -11.5, 103, 11.5, 150), (), None,
             "D", "airside", "taxi", {}),
        Cell(4, "runway", "09L/27R", _rect(r, -300, 150, 300, 195), (), 3, "D",
             "airside", "runway", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", (r((-250.0, 91.5)), r((250.0, 91.5)))),
            CutLine("taxi_centerline", "stubB", (r((0.0, HALF_WIDTH)), r((0.0, 91.5)))),
            CutLine("taxi_centerline", "stubC", (r((0.0, 91.5)), r((0.0, 150.0)))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _raw_band(pm, law, airport):
    """The route metric itself — the band's values BEFORE the subject set
    is narrowed (what ``reach_band_values`` returned before 10-02v (6))."""
    return reach(routes(pm, law, airport), runway_profile.threshold_pins(pm, law, airport))


def _runway_verts(pm, law, verts):
    return set(no_step.runway_membership(pm, law, set(verts)))


def _shared_edge(pm, law):
    """09/27's off-ridge ring vertex farthest from its ridge that a stub
    also owns — the ``runway|stub`` vertex of HECA's class."""
    vw = view(pm, law)
    chains = runway_profile.ridge_chains(vw)
    stubs = [set(vw.rings[f.id]) for f in vw.faces_of_role(("stub",))]
    best = None
    for f in vw.faces_of_role(("runway",)):
        if f.ref != "09/27":
            continue
        chs = chains.get(f.ref, [])
        ridge = {v for c in chs for v in c}
        for v in vw.rings[f.id]:
            if v in ridge or not any(v in s for s in stubs):
                continue
            d = runway_profile._foot(vw, v, chs)[0]
            if best is None or d > best[0]:
                best = (d, f, v)
    assert best is not None, "no stub shares an off-ridge 09/27 edge vertex"
    return best[1], best[2], vw


def _ridge(pm, law, ref="09/27"):
    chs = runway_profile.ridge_chains(view(pm, law)).get(ref, [])
    return [v for ch in chs for v in ch]


def _arms(two_runways, law):
    """``(airport, pm, cs_post, cs_pre, raw, runway_verts)`` — the shipped
    set and the reconstructed pre-10-02v set."""
    airport, pm = two_runways
    raw = _raw_band(pm, law, airport)
    rwv = _runway_verts(pm, law, raw)
    cs, _c, _w = generate(pm, law, airport)
    src = Source(REACH_GENERATOR, "reach band: threshold values along taxi routes "
                 "at the path caps (2026-09-04o)", ())
    pre = [Band(v, raw[v][0], raw[v][1], src) for v in sorted(rwv)
           if raw[v][0] <= raw[v][1]]
    assert pre, "the fixture must reach the runway family at all"
    return airport, pm, cs, ConstraintSet.from_rows([*cs.rows(), *pre]), raw, rwv


# ── the derivation site ──────────────────────────────────────────────────

def test_the_runway_family_is_the_bands_source_never_its_subject(two_runways, law):
    airport, pm = two_runways
    raw = _raw_band(pm, law, airport)
    rwv = _runway_verts(pm, law, raw)
    assert rwv, "the fixture must reach runway-family vertices"
    vals = no_step.reach_band_values(pm, law, airport)
    pins = runway_profile.threshold_pins(pm, law, airport)
    g = routes(pm, law, airport)
    own = reach(no_step.runway_family_routes(g, pm, law), pins)
    # OUTSIDE the runway family nothing moved: the metric is untouched
    assert set(vals) - rwv == set(raw) - rwv
    assert all(vals[v] == raw[v] for v in set(vals) - rwv)
    # INSIDE it every vertex takes its OWN family's routes' band — and the
    # population is the metric's, less only what no runway-only route reaches
    assert rwv & set(vals), "the runway family keeps its own band"
    assert all(vals[v] == own[v] for v in rwv & set(vals))
    assert (rwv - set(vals)) == (rwv - set(own))
    # ... and that band is never TIGHTER than the raw metric's: dropping
    # routes can only raise the least budget (10-02v (6) only ever loosens)
    assert all(vals[v][0] <= raw[v][0] + 1e-9 and vals[v][1] >= raw[v][1] - 1e-9
               for v in rwv & set(vals))
    # and on the shared edge it is STRICTLY looser — that is the whole fix
    _rw, shared, _vw = _shared_edge(pm, law)
    assert vals[shared][1] > raw[shared][1] + 0.05, (raw[shared], vals[shared])
    # the generator mints exactly the feasible subjects
    rows = no_step.reach_bands(pm, law, airport)
    assert rows and all(r.source.generator == REACH_GENERATOR for r in rows)
    assert {r.v for r in rows} == {v for v, (lo, hi) in vals.items() if lo <= hi}


def test_the_shape_stage_reads_the_narrowed_band_not_the_raw_metric(two_runways, law, capsys):
    """The second reader (``pipeline/shapes.shape_stage``) inherits the
    narrowed VALUES from the derivation site — no veto of its own."""
    airport, pm = two_runways
    stage = shape_stage(pm, law, airport, out=lambda _s: None)
    raw = _raw_band(pm, law, airport)
    rwv = _runway_verts(pm, law, stage.bands)
    assert stage.bands and rwv
    assert stage.bands == no_step.reach_band_values(pm, law, airport)
    _rw, shared, _vw = _shared_edge(pm, law)
    assert stage.bands[shared][1] > raw[shared][1] + 0.05
    # the withdraw set is band_roles-driven and is NOT how the runway family
    # loses its band (no apron/junction/service face in this fixture at all)
    assert not set(law.tables.emit.terrace.band_roles) & {f.role for f in pm.faces.values()}


def test_the_shared_edge_ceiling_came_up_the_stub_at_the_taxi_cap(two_runways, law):
    """The ceiling the OLD derivation put on the ``runway|stub`` vertex is
    a TAXI band ceiling: it is delivered by the low runway's threshold and
    its binding walk runs through the stub."""
    airport, pm = two_runways
    raw = _raw_band(pm, law, airport)
    _rw, v, _vw = _shared_edge(pm, law)
    lo, hi = raw[v]
    assert lo <= hi                              # the old band existed here
    assert hi < HIGH_M - 3.0, (lo, hi)           # ... and it capped the edge LOW
    pins = runway_profile.threshold_pins(pm, law, airport)
    g = routes(pm, law, airport)
    ar = reach_anchored(g, {u: (z, 0.0) for u, z in pins.items()})
    walk = ar.binding(v, "hi")
    assert walk, "the ceiling must have a binding anchor"
    assert pins.get(walk[0]) == pytest.approx(LOW_M)   # the LOW runway's threshold
    taxi = set(law.tables.precedence.taxi_family.members)
    on_taxi = {u for u in walk
               if any(pm.faces[f].role in taxi for f in pm.vertices[u].incident_faces)}
    assert on_taxi, (walk, "the binding walk must run over the taxi family")
    stubs = {u for f in pm.faces.values() if f.role == "stub"
             for cyc in (f.ring, *f.holes) for u in pm.ring_vertices(cyc)}
    assert set(walk) & stubs, walk


# ── the constraint set ───────────────────────────────────────────────────

def test_runway_rows_are_otherwise_byte_identical(two_runways, law):
    _airport, _pm, cs, cs_pre, _raw, rwv = _arms(two_runways, law)
    post, pre = set(cs.rows()), set(cs_pre.rows())
    gone = pre - post
    assert not post - pre                       # nothing was ADDED by the fix
    assert gone and all(isinstance(r, Band) and r.source.generator == REACH_GENERATOR
                        and r.v in rwv for r in gone)
    # every other row of the set — the runway's pins, longitudinal caps,
    # vertical curve, crown, transverse maximum — stands unchanged
    assert {r for r in pre if r not in gone} == post


def test_the_shared_edge_carries_the_transverse_row_and_its_own_band(two_runways, law):
    airport, pm, cs, _pre, raw, _rwv = _arms(two_runways, law)
    rw, v, vw = _shared_edge(pm, law)
    # the band it carries is its OWN runway's reach, not the taxi ceiling
    mine = [r for r in cs.rows() if isinstance(r, Band)
            and r.source.generator == REACH_GENERATOR and r.v == v]
    assert len(mine) == 1
    assert mine[0].hi > HIGH_M - 3.0 > raw[v][1], (raw[v], mine[0].hi)
    trans = runway_profile.runway_transverse(pm, law, airport)
    on_v = [r for r in trans if any(u == v for u, _c in r.terms)]
    assert on_v and all(r.soft is None for r in on_v)       # HARD (05o)
    d = runway_profile._foot(vw, v, runway_profile.ridge_chains(vw)[rw.ref])[0]
    cap = T.runway_transverse_max(law, rw.code_letter, rw.code_number)
    assert on_v[0].hi == pytest.approx(cap * d)


# ── the solve ────────────────────────────────────────────────────────────

def test_the_ridge_does_not_come_down(two_runways, law):
    """Both arms solved: with the pre-10-02v bands the taxi-derived
    ceiling holds 09/27 down; without them the ridge rises and stays up,
    and the edge is bounded by the transverse row."""
    airport, pm, cs, cs_pre, raw, _rwv = _arms(two_runways, law)
    rw, v, vw = _shared_edge(pm, law)
    pre_sol, _p = solve_design(pm, cs_pre, law)
    post_sol, _q = solve_design(pm, cs, law)
    assert pre_sol.status in (Status.OPTIMAL, Status.FEASIBLE), pre_sol.message
    assert post_sol.status in (Status.OPTIMAL, Status.FEASIBLE), post_sol.message
    zp, zq = np.asarray(pre_sol.z, float), np.asarray(post_sol.z, float)
    ridge = _ridge(pm, law)
    assert ridge
    # THE RIDGE DOES NOT COME DOWN: no station of 09/27 is lower without the
    # bands than with them, and the station over the stub is strictly higher
    tol = law.tables.emit.design.hard_tol_m
    assert all(zq[u] >= zp[u] - tol for u in ridge), \
        min((zq[u] - zp[u], u) for u in ridge)
    foot = runway_profile._foot(vw, v, runway_profile.ridge_chains(vw)[rw.ref])
    _d, a, b, _t = foot
    assert max(zq[a] - zp[a], zq[b] - zp[b]) > 0.05, (zq[a] - zp[a], zq[b] - zp[b])
    # THE SHARED EDGE IS NO LONGER PULLED AT THE TAXI CEILING.  A reach
    # band is a priced TARGET, not a hard bound (it is in no
    # ``hard_rulings`` tier; "a TARGET met to the ELEVATION MATERIALITY",
    # test_routes), so the arms differ by what the target was worth — not
    # by a cliff: both arms stand above the ceiling, the PRE arm nearer it
    assert zq[v] > zp[v] + 0.05, (zp[v], zq[v], raw[v][1])
    assert zp[v] - raw[v][1] < zq[v] - raw[v][1]
    # ... and what bounds it now is the runway's own transverse row
    d, a, b, t = foot
    cap = T.runway_transverse_max(law, rw.code_letter, rw.code_number)
    fall = (1.0 - t) * zq[a] + t * zq[b] - zq[v]
    assert abs(fall) <= cap * d + tol + 1e-9, (fall, cap * d)


def test_the_taxi_side_vertices_beyond_the_edge_still_obey_the_band(two_runways, law):
    """The stub's own vertices — the ones no runway face owns — still
    CARRY the band and the solve still honours it."""
    airport, pm, cs, _pre, raw, rwv = _arms(two_runways, law)
    stub = {u for f in pm.faces.values() if f.role == "stub"
            for cyc in (f.ring, *f.holes) for u in pm.ring_vertices(cyc)}
    beyond = {u for u in stub - rwv if u in raw and raw[u][0] <= raw[u][1]}
    assert len(beyond) >= 3, len(beyond)
    banded = {r.v: (r.lo, r.hi) for r in cs.bands
              if r.source.generator == REACH_GENERATOR}
    assert beyond <= set(banded)
    assert all(banded[u] == pytest.approx(raw[u]) for u in beyond)
    # and the band STILL GOVERNS them: against an arm with every reach
    # band dropped (``why._ENVELOPE``'s own transform) each of them is held
    # at or under where it stands band-free, strictly under for some.  The
    # comparative form is the honest one — the band is a priced TARGET, so
    # a vertex sits a residual above its ceiling in either arm
    sol, _rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    free = ConstraintSet.from_rows(
        r for r in cs.rows()
        if not (isinstance(r, Band) and r.source.generator == REACH_GENERATOR))
    sol_free, _r2 = solve_design(pm, free, law)
    assert sol_free.status in (Status.OPTIMAL, Status.FEASIBLE), sol_free.message
    z, zf = np.asarray(sol.z, float), np.asarray(sol_free.z, float)
    tol = law.tables.emit.design.hard_tol_m
    assert all(z[u] <= zf[u] + tol for u in beyond), \
        max((z[u] - zf[u], u) for u in beyond)
    assert any(z[u] < zf[u] - 0.01 for u in beyond), \
        sorted(round(float(zf[u] - z[u]), 4) for u in beyond)
