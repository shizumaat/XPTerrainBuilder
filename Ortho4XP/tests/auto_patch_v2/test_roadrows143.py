"""Twins for lane ``roadrows143`` (issue #143 item 2, #100; owner 2026-09-30
Q-97/Q-100: "Why would a road EVER move airside? It should be welded to
airside and then grading DEM to maintain its cap"; free-road ruling;
airside-is-king; RULINGS 2026-09-30aa rules 3-4, 2026-10-01a).

MEASURED (HECA, capture ``frames/hardhold128/HECA.pkl``, main 52e2e2ae):
§20b stage 1 never treats a PINNED vertex as foreign, so every road row
footed on a §37 (9) join pin entered the airside problem — v28332
(30.11631421, 31.40976950, ``service_road#1312`` only, pinned at the core
ribbon's 100.755 m) carried ``road_cross_section`` AND its
``pavement_max_grade ceiling`` twin (0.294 m over 5.3 m) to apron ring
vertex v7898 (91.98 m).  Pass 1a had to yield the pin; the ribbon yielded
−8.49 m.  The population at HECA was 10 such rows (8 longitudinal, all on
join pins), at KCLT 21.

THE RULE (one helper, ``constraints/roads.road_pair_side``):

1. a road pair over AIRSIDE feet only stays the airside's own pair (two-way,
   in stage 1) — no road LEVEL enters it; dropping it (RULINGS 2026-09-30aa
   rule 3) was measured to leave airside pairs unpriced (SPJC apron|stub
   cliffs, CRITICAL motion 0 -> 8);
2. a road row welded to airside is ONE-WAY on its groundside feet, so no
   road row reaches stage 1 — pinned foot or not;
3. between the stages a join pin whose welded road row cannot hold against
   stage 1's constant is released (``road_ramp.welded_join_release``): the
   road's first groundside vertex carries the cap FROM the welded level.

EXTENDED by owner RULINGS 2026-10-02v (1) (lane ``roadsfree143``,
``test_roadsfree143.py``): rule 2 is stated at stage 1's OWN derivation site
— a pinned GROUNDSIDE vertex is foreign (``[design]
groundside_pin_rulings``, ``solve/design.stage_split``) — so it holds for
every generator and every road face, not the four this lane reached.  The
pair law above STAYS: it also decides who FOLLOWS in stage 2.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.road_ramp import (GEN as RAMP_GEN, JOIN_RULING,
                                                 reach_seed_rewrite,
                                                 welded_join_release)
from auto_patch_v2.constraints.roads import (PAIR_AIRSIDE, PAIR_GROUNDSIDE,
                                             PAIR_WELD, road_pair_side,
                                             stage_one_vertices)
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve import design as D
from auto_patch_v2.solve.pin_yield import row_vertices

RUN_LEN = 1200.0
HALF_W = 22.5
#: the apron's east edge, and the short service road welded to it there
APRON_E = 300.0
ROAD_LEN = 5.0
ROAD_Y0, ROAD_Y1 = 60.0, 66.0
#: how far above the apron the core ribbon's join stands (the HECA v28332
#: class: 8.7 m over an apron 5 m away)
RIBBON_ABOVE_M = 8.0

#: the generators whose rows are ROAD rows when they carry a road foot
_ROAD_GENS = ("roads", "transverse", "pavement_ceiling", "pavement_road_cap")


class _Dem:
    provenance = {"synthetic": "roadrows143"}

    def z(self, x: float, y: float) -> float:
        return 500.0 + 0.004 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _airport(law):
    frame = Frame("ZZZZ", origin=(45.5, -100.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (45.5, -100.5), 0.0, 0.0,
                      500.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (45.5, -100.5), 0.0, 0.0,
                      500.0, "fixture"))
    rw = Runway("09/27", 2 * HALF_W, 1, ends, 3, "C")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 500.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "C", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(-APRON_E, HALF_W, APRON_E, 150.0), (),
             None, None, "airside", "apron", {}),
        Cell(2, "service_road", "route3",
             _rect(APRON_E, ROAD_Y0, APRON_E + ROAD_LEN, ROAD_Y1), (),
             None, None, "groundside", "road", {}),
    ]


@pytest.fixture(scope="module")
def law():
    d0 = Law.for_airport("ZZZZ")
    return _dc.replace(d0, tables=_dc.replace(d0.tables, emit=_dc.replace(
        d0.tables.emit, design=_dc.replace(d0.tables.emit.design,
                                           staged_solve=True))))


@pytest.fixture(scope="module")
def built(law):
    airport = _airport(law)
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


def _road_faces(pm):
    return [f for f in pm.faces.values() if f.role == "service_road"]


def _road_vertices(pm):
    out: set[int] = set()
    for f in _road_faces(pm):
        for ring in (f.ring, *f.holes):
            out.update(pm.ring_vertices(ring))
    return out


def _first_groundside(pm, air):
    """The road vertices that are not airside — the road's first
    groundside vertices (the far kerb of the 5 m stub)."""
    return sorted(v for v in _road_vertices(pm) if v not in air)


def test_the_pair_law_reads_the_feet():
    air = frozenset({1, 2})
    assert road_pair_side(air, (1, 2)) == (PAIR_AIRSIDE, ())
    assert road_pair_side(air, (1, 7)) == (PAIR_WELD, (7,))
    assert road_pair_side(air, (7, 2, 8, 1)) == (PAIR_WELD, (7, 8))
    assert road_pair_side(air, (7, 8)) == (PAIR_GROUNDSIDE, ())


def test_the_fixture_welds_the_road_to_the_apron(law, built):
    pm, _cs = built
    air = stage_one_vertices(pm, law)
    rv = _road_vertices(pm)
    assert rv & air, "the road shares the apron's ring vertices (the weld)"
    assert _first_groundside(pm, air), "and has its own groundside kerb"


def test_a_road_row_on_an_airside_vertex_is_one_way_on_its_road_feet(law, built):
    pm, cs = built
    air = stage_one_vertices(pm, law)
    rv = _road_vertices(pm)
    gs_road = rv - air
    n_weld = 0
    for r in cs.rows():
        vs = set(row_vertices(r))
        if r.source.generator not in _ROAD_GENS or not vs & gs_road:
            continue
        if not vs & air:
            continue
        n_weld += 1
        fv = r.follows
        fvs = {fv} if isinstance(fv, int) else set(fv or ())
        assert fvs and fvs <= gs_road and fvs == vs - air, (r.source, vs, fv)
    assert n_weld > 0, "the fixture mints welded road rows"
    # 1. a road pair over the welded (airside) vertices alone is the
    # airside's own pair: minted two-way, never a follower
    both = [r for r in cs.rows() if r.source.generator == "roads"
            and set(row_vertices(r)) <= air]
    assert both, "the fixture's road ring carries two weld vertices"
    assert all(r.follows is None for r in both)


def _pinned(pm, cs, z_by_v):
    pins = [Pin(v, z, Source(RAMP_GEN, JOIN_RULING, (f"vertex:{v}",)))
            for v, z in z_by_v.items()]
    return ConstraintSet.from_rows([*cs.rows(), *pins])


def test_a_welded_road_contributes_no_stage_one_row_even_through_a_pin(law, built):
    pm, cs = built
    air = stage_one_vertices(pm, law)
    gs = _first_groundside(pm, air)
    pinned = _pinned(pm, cs, {v: 600.0 for v in gs})
    drop, fixed = D.stage_split(pm, pinned, law)
    # A PINNED GROUNDSIDE VERTEX IS FOREIGN (owner RULINGS 2026-10-02v (1),
    # lane ``roadsfree143``, ``tests/auto_patch_v2/test_roadsfree143.py``):
    # this lane shut the door one generator at a time and read "a pinned
    # vertex is never foreign" as stage 1's law; the ruling put the same law
    # at stage 1's own site, where it holds for every generator.  Both
    # statements are asserted here — the row outcome below is what the
    # one-way minting buys on its own, and it must still hold.
    assert set(gs) <= drop, "a pinned GROUNDSIDE vertex is foreign"
    rep = D.DesignReport()
    base = D.assemble(pm, pinned, law, rep, drop=drop, fixed=fixed,
                      stage_roles=D.airside_stage_roles(law))
    n = 0
    for _terms, _hi, row in base.one:
        vs = set(row_vertices(row))
        # a road foot beside an AIRSIDE foot is the defect; a road row
        # between two PINS was a constant that bound nothing, and since the
        # ruling it is not stage 1's row at all
        assert not (vs & set(gs) and vs & air), (row.source, vs)
        assert not vs & set(gs), (row.source, vs)
        n += bool(vs & air)
    assert n > 0, "stage 1 carries the airside's own rows"


def test_the_first_groundside_vertex_carries_the_cap_from_the_weld(law, built):
    pm, cs = built
    air = stage_one_vertices(pm, law)
    gs = _first_groundside(pm, air)
    sol0, _r0 = solve_design(pm, cs, law)
    assert sol0.status in (Status.OPTIMAL, Status.FEASIBLE)
    z0 = np.asarray(sol0.z, float)
    weld = sorted(_road_vertices(pm) & air)
    ribbon = float(max(z0[v] for v in weld)) + RIBBON_ABOVE_M
    pinned = _pinned(pm, cs, {v: ribbon for v in gs})
    sol, rep = solve_design(pm, pinned, law,
                            stage2_rewrite=lambda lv: reach_seed_rewrite(
                                pm, law, pinned, lv))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    z = np.asarray(sol.z, float)
    tol = float(law.tables.emit.design.hard_tol_m)
    # AIRSIDE IS KING: no airside vertex moves for the road's pin
    moved = max(abs(z[v] - z0[v]) for v in air)
    assert moved <= tol, moved
    # the road conforms: its first groundside vertex stands within the
    # road's own cap of the weld it touches (no 8 m spike)
    cap = role_cap(law, "service_road").longitudinal
    for v in gs:
        xv, yv = pm.vertices[v].xy
        near = min(weld, key=lambda w: np.hypot(*(np.subtract(pm.vertices[w].xy,
                                                              (xv, yv)))))
        d = float(np.hypot(*np.subtract(pm.vertices[near].xy, (xv, yv))))
        assert abs(z[v] - z[near]) <= cap * d + tol, (v, z[v], near, z[near], d)
    # the release is published as a yielded join (the ribbon follows)
    released = {r["v"] for r in rep.pin_yield if r.get("stage") == "2w"}
    assert released == set(gs)


def test_a_join_that_holds_against_the_weld_keeps_its_pin(law, built):
    pm, cs = built
    air = stage_one_vertices(pm, law)
    gs = _first_groundside(pm, air)
    sol0, _r0 = solve_design(pm, cs, law)
    z0 = np.asarray(sol0.z, float)
    pins = {v: float(z0[v]) for v in gs}
    pinned = _pinned(pm, cs, pins)
    levels = {v: float(z0[v]) for v in air}
    out, recs = welded_join_release(pm, law, pinned, levels)
    assert recs == []
    assert {p.v for p in out.pins} >= set(gs)
