"""The runway TRANSVERSE MAXIMUM twins (lane v2rwytransverse, RULINGS
2026-09-05o; spec ``runway-transverse-max-spec.md`` §4).

HECA 05C/23C on 1.0.285: half 14's outer edge sat 18 m under the ridge
across 31 m (a 58 % cross-fall) because the taxi family's longitudinal
law propagated the lower runway complex up the parallel taxiway into the
shared runway edge, and the runway's only cross-slope row was the SOFT
crown minimum.  ``rulesets.toml [*.runway] transverse_max`` existed and
nothing priced it.

* the accessor returns the table's letter value (ICAO A/B 2 %, C–F
  1.5 %; FAA likewise), read from the tables, never a Python literal;
* the generator states one two-sided HARD ``Linear`` per off-ridge
  ``runway`` ring vertex, in the runway tier (tier 0);
* a synthetic runway whose outer edge is pulled down by a hard pin on a
  vertex shared with a taxiway stub: WITHOUT the generator the edge
  falls (the crown floor is a preference) and the verify reader flags
  the drop as a ``runway_transverse`` DEFECT row (``reading =
  "transverse_max"``); WITH it the solve either holds the edge within
  ``transverse_max × d`` (the profile flexes, the taxiway conforms) or —
  pulled further than the profile can follow — the IIS names the pin.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.constraints import GENERATORS, generate, roads, runway_profile
from auto_patch_v2.constraints.precedence import view, row_tier
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import (REACH_GENERATOR, Band, ConstraintSet,
                                             Linear, Pin, Source)
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import Options, Status, solve_design
from auto_patch_v2.solve import solve_design
from auto_patch_v2.verify import census
from auto_patch_v2.verify.census import DEFECT_KEYS, FAMILY_TRANSVERSE
from tests.auto_patch_v2.test_crown import (HALF_WIDTH, Airport, Cell, Classification,
                                            CutLine, Frame, Runway, RunwayEnd,
                                            SceneryPack, _PlaneDem, _rect, _rot, build)

GEN = "runway_transverse"
PIN_SRC = Source("fixture_pin", "twin: a hard pin on a shared taxiway vertex", ("fixture:pin",))
RIDGE_SRC = Source("fixture_ridge", "twin: the profile held at its stations", ("fixture:ridge",))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def build_shared_edge(law):
    """The crown fixture's airport with the stub's centreline ending AT
    the runway edge (HECA's class: pav91/93/79 join 05C/23C's edge and
    the half stays ONE face whose ring runs the ridge and the edge — no
    cross chord couples the edge to the ridge at the stub)."""
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", r((600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _PlaneDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -600, -HALF_WIDTH, 600, HALF_WIDTH), (),
             3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", (r((-400.0, 91.5)), r((400.0, 91.5)))),
            CutLine("taxi_centerline", "stubB", (r((0.0, HALF_WIDTH)), r((0.0, 91.5)))))
    pm, stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm, stats


@pytest.fixture(scope="module")
def shared_edge(law):
    return build_shared_edge(law)


def test_accessor_returns_the_tables_letter_values(law):
    for key in ("icao", "faa"):
        lw = Law(tables=law.tables, ruleset_key=key)
        tbl = lw.ruleset.runway.transverse_max
        for letter in "ABCDEF":
            assert T.runway_transverse_max(lw, letter) == tbl.by_letter[letter]
        assert T.runway_transverse_max(lw, None) == tbl.default
        # the A/B classes are looser than C–F in both authorities
        assert T.runway_transverse_max(lw, "A") >= T.runway_transverse_max(lw, "D")
    # and it is the same number the within-shape cap carries for the family
    assert T.role_cap(law, "runway", 3, "D").transverse == \
        T.runway_transverse_max(law, "D", 3)


def _shared_edge_vertex(pm, law):
    """The runway-half face and its OUTER-edge ring vertex (the farthest
    off the ridge) shared with a stub's ring — HECA's class: the runway
    edge a taxi-family face owns a value on."""
    vw = view(pm, law)
    chains = runway_profile.ridge_chains(vw)
    best = None
    stubs = [set(vw.rings[f.id]) for f in vw.faces_of_role(("stub",))]
    for rw in vw.faces_of_role(("runway",)):
        chs = chains.get(rw.ref, [])
        ridge = {v for c in chs for v in c}
        for v in vw.rings[rw.id]:
            if v in ridge or not any(v in s for s in stubs):
                continue
            d = runway_profile._foot(vw, v, chs)[0]
            if best is None or d > best[0]:
                best = (d, rw, v)
    assert best is not None, "no stub shares an off-ridge runway edge vertex"
    return best[1], best[2], vw


def test_generator_states_a_two_sided_hard_band_in_the_runway_tier(shared_edge, law):
    airport, pm, _ = shared_edge
    rows = runway_profile.runway_transverse(pm, law, airport)
    rw, v, vw = _shared_edge_vertex(pm, law)
    assert rows and all(isinstance(r, Linear) and r.soft is None for r in rows)
    assert all(r.lo is not None and r.hi is not None and r.lo == -r.hi for r in rows)
    cap = T.runway_transverse_max(law, rw.code_letter, rw.code_number)
    chains = runway_profile.ridge_chains(vw)
    off: set[int] = set()
    for f in vw.faces_of_role(("runway",)):
        ridge = {c for ch in chains.get(f.ref, []) for c in ch}
        off.update(u for u in vw.rings[f.id] if u not in ridge)
    assert len(rows) == len(off)          # one row per off-ridge vertex, once
    by_v = {next(u for u, c in r.terms if c == -1.0): r for r in rows}
    assert v in by_v
    d = runway_profile._foot(vw, v, runway_profile.ridge_chains(vw)[rw.ref])[0]
    assert by_v[v].hi == pytest.approx(cap * d)
    tt = T.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    assert all(row_tier(pm, r, tier_of, len(tt) - 1) == 0 for r in rows)
    # registered beside the crown, in run order
    names = [n for n, _ in GENERATORS]
    assert names.index(GEN) == names.index("runway_crown") + 1


#: The pull on the shared edge vertex.  It stays INSIDE the route reach
#: band (``no_step.reach_bands``: the thresholds' envelope along taxi
#: routes — a deeper pin is refused by the band before any cross-slope
#: law is asked); the deep pull is diagnosed with the bands withdrawn,
#: as the last resort does (``relax.envelope_free``).
#: 1.0 m since RULINGS 2026-09-06b law 1 (the vertical curve is hard): the
#: profile of this 1,200 m code-3 fixture can dip at most ≈ 1.5 m under
#: K = 150 m per 1 % within the 1.5 % cap (h = ℓ²/K with ℓ ≤ 150 m), so
#: the 3.0 m pull the twin first used is now the refused class below.
PULL_M = 1.0
DEEP_PULL_M = 14.0


def _solve_with_pin(shared_edge, law, depth_m, *, with_generator, envelope=True,
                    hold_ridge=False):
    """The fixture solved with the shared edge vertex pinned ``depth_m``
    under its unpinned value; ``hold_ridge`` pins the two ridge stations
    bracketing its foot at THEIR unpinned values (HECA's class: the
    profile tracks the CIFP pins while the edge is pulled away)."""
    airport, pm, _ = shared_edge
    rw, v, vw = _shared_edge_vertex(pm, law)
    # without the generator the cliff must be BUILDABLE: under RULINGS
    # 2026-09-05aa the edge vertex's lateral hop to its ridge station is a
    # no_step ROUTE pair at transverse_max (66 ↔ 155, 23 m, measured), so
    # the no_step generator goes off with the transverse one — and so does
    # the chain (05ac), whose runway hop states the same edge once more
    only = None if with_generator else {n for n, _ in GENERATORS} - {GEN, "no_step_pairs", "taxi_chain"}
    cs, _c, _w = generate(pm, law, airport, only=only)
    base = solve_design(pm, cs, law)[0]
    assert base.status in (Status.OPTIMAL, Status.FEASIBLE), base.message
    extra = [Pin(v, float(base.z[v]) - depth_m, PIN_SRC)]
    if hold_ridge:
        _d, a, b, _t = runway_profile._foot(vw, v, runway_profile.ridge_chains(vw)[rw.ref])
        extra += [Pin(u, float(base.z[u]), RIDGE_SRC) for u in (a, b)]
    cs2 = ConstraintSet.from_rows(list(cs.rows()) + extra)
    if not envelope:
        cs2 = ConstraintSet.from_rows(
            [r for r in cs2.rows()
             if not (isinstance(r, Band) and r.source.generator == REACH_GENERATOR)])
    sol, rep = solve_design(pm, cs2, law)
    return airport, pm, rw, v, cs2, sol, rep


def _built_falls(pm, law, airport, z):
    """Vertex -> (built fall, cap × d) over the runway's off-ridge ring."""
    vw = view(pm, law)
    out = {}
    for f in vw.faces_of_role(("runway",)):
        chs = runway_profile.ridge_chains(vw).get(f.ref, [])
        cap = T.runway_transverse_max(law, f.code_letter, f.code_number)
        ridge = {c for ch in chs for c in ch}
        for u in vw.rings[f.id]:
            if u in ridge:
                continue
            d, a, b, t = runway_profile._foot(vw, u, chs)
            out[u] = ((1.0 - t) * z[a] + t * z[b] - z[u], cap * d)
    return out


def test_without_the_generator_the_edge_falls_and_verify_flags_it(shared_edge, law, tmp_path):
    airport, pm, rw, v, cs, sol, rep = _solve_with_pin(shared_edge, law, PULL_M, with_generator=False,
                                                  hold_ridge=True)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    falls = _built_falls(pm, law, airport, sol.z)
    fall, bound = falls[v]
    assert fall > bound + PULL_M - 0.5, (fall, bound)     # the cliff is built
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    assert FAMILY_TRANSVERSE in DEFECT_KEYS
    got = rows[FAMILY_TRANSVERSE]
    assert got and all(r["reading"] == "transverse_max" for r in got)
    # RE-SCOPED (owner RULINGS 2026-09-10av, lane v2grounddem): with the
    # transverse generator OFF nothing holds the runway's OTHER edge either,
    # and the adjacent ground's own DEM datum now gives the strip beside it a
    # level of its own — so the census's WORST transverse row is no longer
    # necessarily the pinned one (measured 1.88 m against the pinned 1.53 m).
    # What the twin holds: verify flags THE PINNED FALL, and nothing milder.
    assert any(r["magnitude_m"] == pytest.approx(fall, abs=0.05) for r in got), \
        (fall, sorted(r["magnitude_m"] for r in got))
    assert max(r["magnitude_m"] for r in got) >= fall - 0.05
    cap = T.runway_transverse_max(law, rw.code_letter, rw.code_number)
    assert all(r["direction"] == "fall" and r["cap_pct"] == pytest.approx(100 * cap)
               for r in got)


def test_with_the_generator_the_edge_holds_within_the_cap(shared_edge, law):
    airport, pm, rw, v, cs, sol, rep = _solve_with_pin(shared_edge, law, PULL_M, with_generator=True)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    # THE TRANSVERSE MAXIMUM IS A CONSTRAINT of the design surface (RULINGS
    # 2026-09-08v): held to the solve's own tolerance (``[design] hard_tol_m``,
    # inside the census's rounding envelope), not to the LP's exact bound
    tol_h = law.tables.emit.design.hard_tol_m
    falls = _built_falls(pm, law, airport, sol.z)
    assert all(abs(f) <= b + tol_h for f, b in falls.values()), \
        max((abs(f) - b, u) for u, (f, b) in falls.items())
    # the profile flexed to the pinned edge: the ridge foot moved with it
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))
    assert rows[FAMILY_TRANSVERSE] == []


def test_pulled_beyond_the_profile_the_iis_names_the_pin(shared_edge, law):
    airport, pm, rw, v, cs, sol, rep = _solve_with_pin(shared_edge, law, DEEP_PULL_M,
                                                  with_generator=True, envelope=False)
    # 08t/08v: there is no IIS.  The pull the fixture adds is a PIN the design
    # surface cannot honour beside the runway family's CONSTRAINTS, so what
    # names it is the residual: the pin is off by metres while the runway laws
    # — the transverse maximum and the vertical curve — are HELD.
    # 08t/08v: there is no IIS.  The fixture's pin is an EQUALITY the
    # reduction fixes, so the contradiction lands in the LAW rows around it:
    # the certificate's ``max_diff_m`` names it, and the design report books
    # it against the runway family whose rows the pull breaks.
    assert sol.residual is not None and sol.residual.max_diff_m > 0.1
    fam = rep.families.get("runway_profile")
    assert fam and fam["missed"] > 0 and fam["max_m"] > 0.1, rep.line()
