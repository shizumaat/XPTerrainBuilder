"""Issue #609, owner RULINGS 2026-10-13a (1)/(3): THE ROAD YIELDS TO THE PAD.

A mapped-road ribbon admitted for a pad is a FOLLOWER of the last stage
(round 4), keeps no absolute road row
off the rim (its §37 (6) target and ceiling leave, its §37 (9) join pin is
released so the core ribbon yields), and carries ONE design row relative
to its nearest rim vertex; the ribbon pass of the touch witness never
holds a road off a pad as a hillside terrace.  The fixtures are
``test_pad_touch``'s (one pad, one road along its south edge)."""
from __future__ import annotations

import dataclasses as dc

import pytest

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.pad_touch import HELD_KEY, WELD_KEY
from auto_patch_v2.classify.roles import Cell, Classification, _cut_back_groundside
from auto_patch_v2.law import Law
from auto_patch_v2.planar import build

from tests.auto_patch_v2.test_pad_touch import _Dem, _airport, _rect


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ribbon_cells(y0: float = 92.0, y1: float = 100.0):
    """``test_pad_touch._road_cells`` with the road carrying a MAPPED-ROAD
    ribbon ref (``small_roads:-1``), along the pad's south edge by default
    (``y0, y1`` = 200, 208 puts it along the north edge, on the hillside)."""
    return [Cell(9, "runway", "09/27", _rect(-800.0, -422.5, 800.0, -377.5), (),
                 3, "D", "airside", "runway", {}),
            Cell(0, "building", "padA", _rect(100.0, 100.0, 200.0, 200.0), (),
                 None, None, "airside", "pad", {}),
            Cell(1, "service_road", "small_roads:-1", _rect(0.0, y0, 300.0, y1), (),
                 None, None, "groundside", "service_road",
                 {"osm_ribbon": 1.0, "pad_road": 1.0})]


def test_the_ribbon_pass_never_holds_a_road_off_a_pad(law):
    """13a (3) "Ramp it": across a 5 m hillside step the first pass HOLDS a
    lot (the §28 (6) knife); the ribbon pass (``hold=False``) welds."""
    airport = _airport(law, _Dem(north=5.0))
    held, n_held = _cut_back_groundside(_ribbon_cells(200.0, 208.0), law, load_rules(), airport)
    road = [c for c in held if c.role == "service_road"]
    assert n_held == 1 and any(c.evidence.get(HELD_KEY) for c in road)
    welded, n_cut = _cut_back_groundside(_ribbon_cells(200.0, 208.0), law, load_rules(),
                                         airport, only=[2], hold=False)
    road = [c for c in welded if c.role == "service_road"]
    assert n_cut == 0 and all(not c.evidence.get(HELD_KEY) for c in road)
    assert any(c.evidence.get(WELD_KEY) for c in road)


def test_a_welded_ribbon_keeps_no_absolute_road_row_off_the_rim(law):
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.constraints.road_ramp import (JOIN_RULING, PAD_RAMP_RULING,
                                                     RULING, RULING_CEILING,
                                                     pad_ramp_rewrite,
                                                     pad_weld_release,
                                                     road_join_rows,
                                                     road_ramp_rows)
    from auto_patch_v2.model.constraints import ConstraintSet
    airport = _airport(law, _Dem())
    cells, _n = _cut_back_groundside(_ribbon_cells(), law, load_rules(), airport,
                                     only=[2], hold=False)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    rim = pad_welded_vertices(pm, law)
    road = {v for f in pm.faces.values() if f.ref == "small_roads:-1"
            for v in pm.ring_vertices(f.ring)}
    assert rim and rim < road
    off = sorted(road - rim)
    pm = dc.replace(pm, road_ramp_z={v: 700.0 for v in road},
                    road_coverage_join={off[0]: 702.0})
    cs = ConstraintSet.from_rows(road_ramp_rows(pm, law, airport)
                                 + road_join_rows(pm, law, airport))
    cs, _rep = pad_weld_release(pm, law, cs)
    out, rep = pad_ramp_rewrite(pm, law, cs)
    assert rep["ribbon_vertices"] == len(off)
    assert rep["targets"] == rep["ceilings"] == len(off)
    assert [j["v"] for j in rep["joins"]] == [off[0]] and rep["joins"][0]["stage"] == "2p"
    assert not out.pins
    assert not any(r.source.ruling == RULING_CEILING for r in out.bands)
    assert not any(r.source.ruling == RULING for r in out.linears)
    # the released join leaves no row behind: the core yields to the patch
    assert not any(r.source.ruling == JOIN_RULING for r in out.linears)
    rel = [r for r in out.linears if r.source.ruling == PAD_RAMP_RULING]
    assert rep["rows"] == len(rel) == len(off)
    g = float(law.tables.emit.road_contact.ramp_grade)
    for r in rel:
        (v, cv), (q, cq) = r.terms
        assert cv == 1.0 and cq == -1.0 and q in rim and v in off
        d = ((pm.vertices[v].xy[0] - pm.vertices[q].xy[0]) ** 2
             + (pm.vertices[v].xy[1] - pm.vertices[q].xy[1]) ** 2) ** 0.5
        assert r.lo == r.hi and abs(r.lo) <= g * d + 1e-9     # flat DEM: 0, never past g·d


class _FallingDem(_Dem):
    """Flat at 700 m on and north of the pad, falling 8 % south of its
    south edge (y < 100): the road's ground stands below the pad."""

    def z(self, x: float, y: float) -> float:
        return 700.0 + (0.0 if y >= 100.0 else 0.08 * (y - 100.0))


def _derive(airport, law):
    """The caller's prefix the last stage runs (``pipeline/build``'s shape)."""
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.no_step import hold_pass

    def run(cl0):
        pm0, _st = build(airport, cl0, law)
        cs0, _c, _w = generate(pm0, law, airport)
        return pm0, cs0, None, hold_pass(pm0, law)
    return run


def _pad_levels(pm, z) -> dict[tuple[float, float], float]:
    return {tuple(round(c, 3) for c in pm.vertices[v].xy): float(z[v])
            for f in pm.faces.values() if f.role == "building"
            for v in pm.ring_vertices(f.ring)}


def test_the_pad_road_is_a_follower_of_the_last_stage(law):
    """ROUND 4 — SENIORITY AS AN ORDER (13b (5), 13d): the base map is the
    classification WITHOUT its pad roads (``gap_free``), solved as an
    airport with no such road is; the last stage solves the pad road
    against those levels.  The pad's level is the base's EXACTLY, and the
    road descends from the rim toward its own ground."""
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.pipeline.late_stage import run_late_stage
    from auto_patch_v2.pipeline.stage_one_map import gap_free, late_followers
    from auto_patch_v2.solve import solve_design
    airport = _airport(law, _FallingDem())
    cells, _n = _cut_back_groundside(_ribbon_cells(), law, load_rules(), airport,
                                     only=[2], hold=False)
    cl = Classification(tuple(cells), (), {}, ())
    base = gap_free(cl)
    assert base is not None and not any(c.role == "service_road" for c in base.cells)
    derive = _derive(airport, law)
    pm0, cs0, _s, hold0 = derive(base)
    sol0, _rep0 = solve_design(pm0, cs0, law, hold=hold0)
    pm1, sol1, rep = run_late_stage(cl, airport, law, derive,
                                    {"pm": pm0, "z": sol0.z, "pin_yield": []},
                                    out=lambda m: None)
    assert rep["followers"]["pad_roads"] >= 1 and rep["followers"]["gap_faces"] == 0
    free, _f = late_followers(pm1)
    assert free and rep["pad_ramp"]["rows"] > 0
    p1, p0 = _pad_levels(pm1, sol1.z), _pad_levels(pm0, sol0.z)
    assert set(p0) <= set(p1)
    assert max(abs(p1[k] - p0[k]) for k in p0) < 1e-6
    rim = pad_welded_vertices(pm1, law)
    road = {v for f in pm1.faces.values() if f.ref == "small_roads:-1"
            for v in pm1.ring_vertices(f.ring)}
    assert rim and all(abs(sol1.z[v] - 700.0) < 1e-6 for v in rim)
    outer = [v for v in road - rim if pm1.vertices[v].xy[1] < 100.0]
    assert outer and all(sol1.z[v] <= 700.0 + 1e-6 for v in outer)
    assert min(sol1.z[v] for v in outer) < 700.0 - 0.1


def test_the_reach_read_names_the_remainder_where_no_cap_ramp_fits(law):
    """13d: between the pad's rim and the road's other standing end the
    least grade is |rise| / run; over the road cap the remainder is
    ``|rise| - cap x run``, signed toward the far end."""
    from auto_patch_v2.constraints.pad_road_reach import pad_road_reach
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.law.tables import role_cap
    airport = _airport(law, _Dem())
    lot = Cell(2, "parking_lot", "lot1", _rect(100.0, 60.0, 200.0, 80.0), (),
               None, None, "groundside", "pavement", {})
    road = Cell(3, "service_road", "small_roads:-1", _rect(100.0, 80.0, 200.0, 104.0), (),
                None, None, "groundside", "service_road",
                {"osm_ribbon": 1.0, "pad_road": 1.0})
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [lot, road]
    cells, _n = _cut_back_groundside(cells, law, load_rules(), airport, only=[3], hold=False)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    assert pm.pad_roads == frozenset({"small_roads:-1"})
    rim = pad_welded_vertices(pm, law)
    rv = {v for f in pm.faces.values() if f.ref == "small_roads:-1"
          for v in pm.ring_vertices(f.ring)}
    lot_v = {v for f in pm.faces.values() if f.ref == "lot1" for v in pm.ring_vertices(f.ring)}
    assert rv & rim and rv & lot_v
    cap = float(role_cap(law, "service_road").longitudinal)

    def read(drop):
        fixed = {v: 700.0 for f in pm.faces.values() if f.ref != "small_roads:-1"
                 for v in pm.ring_vertices(f.ring)}
        fixed.update({v: 700.0 - drop for v in lot_v})
        return pad_road_reach(pm, law, fixed)
    fits, = read(1.0)                     # 1 m over ~20 m: ~5 %
    assert fits["pad"] == "padA" and fits["remainder_m"] == 0.0
    assert 19.0 <= fits["run_m"] <= 24.0             # the road is 20 m long
    short, = read(5.0)                    # 5 m over 20 m: 25 %
    assert short["rise_m"] == pytest.approx(-5.0)
    assert short["remainder_m"] == pytest.approx(-(5.0 - cap * short["run_m"]), abs=1e-3)
    most = float(law.tables.emit.road_contact.pad_shift_max_m)
    assert short["shift_m"] == -most                      # the pad takes no more than the cap
    assert short["step_m"] == pytest.approx(abs(short["remainder_m"]) - most, abs=1e-3)
