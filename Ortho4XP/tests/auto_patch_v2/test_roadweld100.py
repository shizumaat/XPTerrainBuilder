"""#100 — A ROAD NEVER MOVES THE AIRSIDE (owner RULINGS 2026-09-30z (1);
spec-author review 2026-09-30aa, lane ``roadweld100``).

A mapped-road RIBBON is WELDED to the airside at its contacts: it shares
the rim vertex (no stand-off, no sliver — ``pad_cut.airside_clip`` at
pass B), every row a GROUNDSIDE face mints is stage 2's whatever its
columns (``solve/design.assemble``, rule 1), a pair with both feet
airside mints no row and a pair with one foot airside FOLLOWS the road
foot (``constraints/roads.road_pair_side``, rules 3-4).

Twins (the review's):

(i)  a ribbon between an APRON at 80 m and a JUNCTION at 84 m, 10 m
     apart: stage 1's rows and solution are IDENTICAL with the ribbon on
     and off; the ribbon's own pairs hold the road cap in stage 2 except
     at the higher contact, where the run is too short — a REPORTED
     ``road_contact_step`` (rule 7), never an airside move;
(ii) a ribbon touching a RUNWAY ring: the ring's node list is identical
     with the ribbon on and off;
(iii) no stage-1 row carries a ``roads`` / ``pavement_road_cap`` source
     from a groundside face.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap, rolled_on_roles
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import airside_stage_vertices

RIB_REF = "small_roads:-3"


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """The apron's ground at 80 m, the junction's at 84 m, and a ramp of
    DEM between them (the ribbon runs over it)."""

    provenance = {"synthetic": "roadweld100"}

    def z(self, x: float, y: float) -> float:
        if x <= 0.0:
            return 80.0
        if x >= 10.0:
            return 84.0
        return 80.0 + 0.4 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, runway=False):
    frame = Frame("ZZZZ", origin=(30.1, 31.4), identity_dp=11)
    rws = ()
    if runway:
        ends = (RunwayEnd("09", (-800.0, -300.0), (30.1, 31.4), 0.0, 0.0,
                          80.0, "fixture"),
                RunwayEnd("27", (800.0, -300.0), (30.1, 31.4), 0.0, 0.0,
                          80.0, "fixture"))
        rws = (Runway("09/27", 45.0, 1, ends, 3, "D"),)
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 80.0, rws, (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


def _cells(ribbon: bool, runway: bool = False):
    # each pavement page carries NODES at the road's mouth (y = ±4): the
    # contact a ribbon welds to is a rim node (rule 2); a mouth with none
    # retreats and is counted (``weld_refused_contacts``)
    out = [
        Cell(1, "apron", "apronA",
             ((-120.0, -40.0), (0.0, -40.0), (0.0, -4.0), (0.0, 4.0),
              (0.0, 40.0), (-120.0, 40.0)), (),
             None, None, "airside", "apron", {}),
        Cell(2, "junction", "twyJ",
             ((10.0, -40.0), (60.0, -40.0), (60.0, 40.0), (10.0, 40.0),
              (10.0, 4.0), (10.0, -4.0)), (),
             None, "C", "airside", "taxi", {}),
    ]
    if runway:
        out.append(Cell(0, "runway", "09/27",
                        _rect(-800.0, -322.5, 800.0, -277.5), (), 3, "D",
                        "airside", "runway", {}))
    if ribbon:
        # the mapped road: 8 m wide, from the apron edge (x = 0) to the
        # junction edge (x = 10); with ``runway`` it runs on south to touch
        # the runway ring at y = -277.5
        ring = (_rect(0.0, -4.0, 10.0, 4.0) if not runway else
                ((0.0, 4.0), (0.0, -277.5), (8.0, -277.5), (8.0, -4.0),
                 (10.0, -4.0), (10.0, 4.0)))
        out.append(Cell(3, "service_road", RIB_REF, ring, (), None, None,
                        "groundside", "road",
                        {"osm_ribbon": 1.0, "highway": "tertiary"}))
    return out


def _law_arm(law, **design):
    d0 = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit,
                                     design=_dc.replace(d0, **design))))


@pytest.fixture(scope="module")
def law():
    return _law_arm(Law.for_airport("ZZZZ"), staged_solve=True)


def _arm(law, ribbon: bool, runway: bool = False):
    airport = _airport(law, runway)
    pm, _st = build(airport, Classification(tuple(_cells(ribbon, runway)),
                                            (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    # the pipeline's own stage-2 rewrite (``pipeline/build.py``)
    from auto_patch_v2.constraints.road_ramp import reach_seed_rewrite
    sol, rep = solve_design(pm, cs, law,
                            stage2_rewrite=lambda lv: reach_seed_rewrite(pm, law, cs, lv))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return pm, cs, np.asarray(sol.z, float), rep


@pytest.fixture(scope="module")
def pair(law):
    return _arm(law, False), _arm(law, True)


def _air_values(pm, z, law):
    air = rolled_on_roles(law)
    out = {}
    for vid, v in pm.vertices.items():
        if any(r in air for r in pm.roles_at(vid)):
            out[v.key] = round(float(z[vid]), 9)
    return out


# ── (i) the ribbon between two levels ────────────────────────────────────

def test_stage_one_is_identical_with_the_ribbon_on_and_off(law, pair):
    (pm0, _cs0, z0, rep0), (pm1, _cs1, z1, rep1) = pair
    assert any(f.ref.startswith(RIB_REF) for f in pm1.faces.values())
    s0, s1 = rep0.stages.get("stage1") or {}, rep1.stages.get("stage1") or {}
    assert s0.get("unknowns") == s1.get("unknowns")
    assert s0.get("rows") == s1.get("rows")
    # THE AIRSIDE VERTEX SET AND ITS VALUES: identical (rules 9-10)
    a0, a1 = _air_values(pm0, z0, law), _air_values(pm1, z1, law)
    assert set(a0) == set(a1)
    assert max(abs(a0[k] - a1[k]) for k in a0) <= 1e-6


def test_the_ribbon_climbs_from_the_lower_contact_at_the_cap(law, pair):
    """Rules 5-7: the ribbon's own pairs hold 8 % / 2 % in stage 2 except
    the pairs AT THE HIGHER CONTACT — a 4 m rise in 10 m cannot be made at
    8 %, so the road arrives BELOW the junction and the step is reported
    (``road_contact_step``), never taken out of the junction."""
    _a0, (pm, _cs, z, rep) = pair
    cap = role_cap(law, "service_road")
    air = airside_stage_vertices(pm, law)
    rib = {v for f in pm.faces.values() if f.ref.startswith(RIB_REF)
           for v in pm.ring_vertices(f.ring)}
    # the ribbon's OWN vertices: neither an airside rim vertex (a weld,
    # stage 1's) nor a zone band's kerb (30e (4): the band leads there —
    # here the junction's zone-1 lip, 3 m wide, covers the ribbon's end)
    own = sorted(rib - air - pm.band_kerb_vertices())
    assert own, "the ribbon has vertices of its own"
    # nothing of the ribbon's own stands ABOVE the higher contact or
    # below the lower one
    assert all(80.0 - 0.05 <= z[v] <= 84.0 + 0.05 for v in own)
    # the ribbon's own pairs (neither foot airside) hold the road cap
    for f in pm.faces.values():
        if not f.ref.startswith(RIB_REF):
            continue
        ring = pm.ring_vertices(f.ring)
        for i, a in enumerate(ring):
            b = ring[(i + 1) % len(ring)]
            if a not in own or b not in own:
                continue
            (xa, ya), (xb, yb) = pm.vertices[a].xy, pm.vertices[b].xy
            d = ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5
            if d > 0.5:
                assert abs(z[a] - z[b]) <= cap.longitudinal * d + 0.02
    steps = [r for r in (rep.road_contact_steps or ())]
    assert steps, "the too-short run is REPORTED"
    assert max(s["step_m"] for s in steps) > float(law.tables.emit.cockpit.visual_m)


# ── (ii) a ribbon touching a runway ring ─────────────────────────────────

def test_a_ribbon_touching_a_runway_leaves_its_ring_node_list_identical(law):
    def ring_of(ribbon):
        airport = _airport(law, True)
        pm, _st = build(airport, Classification(
            tuple(_cells(ribbon, True)), (), {}, ()), law)
        rw = [f for f in pm.faces.values() if f.role == "runway"]
        assert rw
        return sorted(tuple(pm.vertices[v].key for v in pm.ring_vertices(f.ring))
                      for f in rw), pm
    r0, _pm0 = ring_of(False)
    r1, pm1 = ring_of(True)
    assert any(f.ref.startswith(RIB_REF) for f in pm1.faces.values())
    assert r0 == r1


# ── (iii) no stage-1 row from a groundside face ──────────────────────────

def test_no_stage_one_row_is_minted_by_a_groundside_face(law, pair):
    from auto_patch_v2.law.tables import role_side
    from auto_patch_v2.solve.design import DesignReport, assemble, stage_split
    _a0, (pm, cs, _z, _rep) = pair
    drop, foreign = stage_split(pm, cs, law)
    base = assemble(pm, cs, law, DesignReport(), drop=drop, fixed=foreign,
                    stage_roles=frozenset(rolled_on_roles(law)))
    gs = {f.id for f in pm.faces.values() if role_side(law, f.role) == "groundside"}
    bad = []
    for _terms, _hi, row in base.one:
        src = getattr(row, "source", None)
        if src is None or src.generator not in ("roads", "pavement_road_cap"):
            continue
        faces = {int(t[5:]) for t in src.inputs if str(t).startswith("face:")}
        if faces & gs:
            bad.append(src)
    assert bad == []
