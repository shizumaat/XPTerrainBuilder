"""ROUND 5 of issue #609 (lane roads609e) — the pad road's ramp INSIDE the
patch, 13e's release and 13f's shift, each on a synthetic map.

* B: the ramp row reads the rim's STANDING level and the run ALONG the
  road, a road end standing off a rim it could not be welded to is at that
  rim, the exit walk runs the ramp's own length off a pad road or a pad's
  edge and never mints a branch that leads nowhere;
* C: a stretch no cap-grade ramp fits on is released to the grade it needs
  and published as a lifted cap on its own faces;
* D: only a free-standing pad shifts, rigidly, inside the table's cap.
"""
from __future__ import annotations

import dataclasses as dc
import types

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.roles import Cell, Classification, _cut_back_groundside
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import build

from tests.auto_patch_v2.test_pad_touch import _Dem, _airport, _rect
from tests.auto_patch_v2.test_roads609 import _derive, _ribbon_cells


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _road(i, ref, ring):
    return Cell(i, "service_road", ref, ring, (), None, None, "groundside",
                "service_road", {"osm_ribbon": 1.0, "pad_road": 1.0})


def _map(law, cells, only, dem=None):
    airport = _airport(law, dem or _Dem())
    cells, _n = _cut_back_groundside(cells, law, load_rules(), airport, only=only, hold=False)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return airport, pm


def _ramp_rows(pm, law, levels):
    from auto_patch_v2.constraints.pad_ramp import PAD_RAMP_RULING, pad_ramp_rewrite
    from auto_patch_v2.model.constraints import ConstraintSet
    out, _rep = pad_ramp_rewrite(pm, law, ConstraintSet.from_rows([]), levels)
    return {r.terms[0][0]: (r.terms[1][0], r.lo) for r in out.linears
            if r.source.ruling == PAD_RAMP_RULING}


# ── B: the ramp row ──────────────────────────────────────────────────────

def test_the_ramp_row_descends_from_the_rims_standing_level(law):
    """KCLT ``-8190``: a pad standing 5 m over level ground.  The row is
    read off the pad's STANDING level — 5 % down from it, to the ground
    after 100 m — never off the rim's DEM (which said "level with the
    rim" all the way out: a road at the pad's height, a cliff at its end)."""
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    road = _road(1, "small_roads:-1", _rect(200.0, 146.0, 420.0, 154.0))
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [road]
    _airport_, pm = _map(law, cells, only=[2])
    rim = pad_welded_vertices(pm, law)
    assert rim
    rows = _ramp_rows(pm, law, {v: 705.0 for v in rim})
    g = float(law.tables.emit.road_contact.ramp_grade)
    far = [v for v in rows if pm.vertices[v].xy[0] >= 400.0]
    near = [v for v in rows if 200.0 < pm.vertices[v].xy[0] <= 240.0]
    assert far and all(rows[v][1] == pytest.approx(-5.0) for v in far)      # on the ground
    for v in near:                                                     # mid-ramp, at 5 %
        d = pm.vertices[v].xy[0] - 200.0
        assert -g * (d + 8.0) - 1e-6 <= rows[v][1] <= -g * d + 1e-6
    # the old read (no standing level given): the rim's own DEM — no descent
    assert all(lo == pytest.approx(0.0) for _r, lo in _ramp_rows(pm, law, None).values())


def test_on_ground_falling_away_the_ramp_comes_down_to_it(law):
    """KASE: the ground falls 8 % away from a pad standing on it.  The ramp
    takes the profile nearer the ground — the ground's own — and never
    floats at 5 % over a valley it cannot catch (which sent the exit walk
    1,000 m down the road)."""
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from tests.auto_patch_v2.test_roads609 import _FallingDem
    road = _road(1, "small_roads:-1", _rect(146.0, 0.0, 154.0, 100.0))
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [road]
    _a, pm = _map(law, cells, only=[2], dem=_FallingDem())
    rim = pad_welded_vertices(pm, law)
    rows = _ramp_rows(pm, law, {v: 700.0 for v in rim})
    far = [v for v in rows if pm.vertices[v].xy[1] <= 1.0]
    assert far and all(rows[v][1] == pytest.approx(pm.vertices[v].dem_z - 700.0)
                       for v in far)                         # on the ground, -8 m
    assert all(rows[v][1] < -0.05 * 100.0 for v in far)        # below a 5 % ramp


def test_the_run_is_measured_along_the_road(law):
    """An L-shaped road: the vertex round the corner is ramped by the run
    along the road's own edges, never the straight line across the bend."""
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.constraints.pad_ramp import _welded_ribbon_vertices
    ell = ((200.0, 146.0), (300.0, 146.0), (300.0, 40.0), (292.0, 40.0),
           (292.0, 138.0), (200.0, 138.0))
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] \
        + [_road(1, "small_roads:-1", ell)]
    _a, pm = _map(law, cells, only=[2])
    near, rim = _welded_ribbon_vertices(pm, law)
    assert rim == pad_welded_vertices(pm, law) and near
    tip = min(near, key=lambda v: pm.vertices[v].xy[1])            # the far end, y = 40
    r, d = near[tip]
    (x, y), (rx, ry) = pm.vertices[tip].xy, pm.vertices[r].xy
    straight = ((x - rx) ** 2 + (y - ry) ** 2) ** 0.5
    assert d >= 92.0 + 98.0 - 1e-6 and d > straight + 40.0


def test_a_road_end_standing_off_the_rim_is_at_the_rim(law):
    """KCLT ``-8198``: a road the arrangement could not weld to a rim node
    stands a metre off the pad and shares no vertex with it.  Its end is
    ramped from THAT rim (0.03 m under a pad 5 m up), not left without a
    row — or ramped from a rim round the block."""
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.constraints.pad_ramp import _stand_off_m, _welded_ribbon_vertices
    road = _road(1, "small_roads:-1", _rect(201.0, 146.0, 320.0, 154.0))   # 1.0 m off
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [road]
    _a, pm = _map(law, cells, only=[2])
    assert not pad_welded_vertices(pm, law)                     # no shared vertex
    near, _rim = _welded_ribbon_vertices(pm, law)
    ends = [v for v in near if pm.vertices[v].xy[0] <= 202.0]
    assert ends and all(near[v][1] <= _stand_off_m(law) for v in ends)
    pad_vs = {v for f in pm.faces.values() if f.role == "building"
              for v in pm.ring_vertices(f.ring)}
    assert all(near[v][0] in pad_vs for v in ends)
    rows = _ramp_rows(pm, law, {v: 705.0 for v in pad_vs})
    assert all(-0.1 <= rows[v][1] <= 0.0 for v in ends)


# ── B: the exit walk ─────────────────────────────────────────────────────

def _way(wid, pts):
    return OsmWay(wid, "airport_small_roads", tuple(pts), False, {"highway": "service"})


def _stations(x0, y0, x1, y1, step=20.0):
    n = int(max(abs(x1 - x0), abs(y1 - y0)) / step)
    return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]


def _exit(law, ways, level=705.0, road=True):
    from auto_patch_v2.classify.pad_road_exit import extend_pad_roads
    cells = [c for c in _ribbon_cells() if c.role != "service_road"]
    if road:
        cells.append(_road(1, "small_roads:-1", _rect(200.0, 146.0, 260.0, 154.0)))
    cells = [dc.replace(c, id=i) for i, c in enumerate(cells)]
    airport = types.SimpleNamespace(osm_ways=tuple(ways), dem=_Dem())
    rules = load_rules()
    cells, _n = _cut_back_groundside(cells, law, rules, airport,
                                     only=range(2, len(cells)), hold=False)
    if not road:        # the walk needs one pad road standing to be asked at all
        cells.append(_road(len(cells), "small_roads:-9", _rect(60.0, 146.0, 100.0, 154.0)))
    cl = Classification(tuple(cells), (), {}, ())
    return cl, extend_pad_roads(cl, airport, law, rules, {"padA": level})


def test_the_exit_runs_the_ramps_own_length(law):
    """A pad 5 m over its ground, its road leaving the patch at x = 260:
    the ribbon runs on 100 m (5 m at the 5 % design grade), to the next
    way vertex — and stops."""
    cl, (out, rep) = _exit(law, [_way(-1, [(150.0, 150.0)] + _stations(200.0, 150.0, 600.0, 150.0))])
    assert rep["exits"] == 1 and rep["run_complete"] == 1 and rep["dead_end_pieces"] == 0
    assert 100.0 <= rep["run_m"] <= 120.0
    new = [c for c in out.cells if c.evidence.get("pad_exit")]
    assert new and all(c.evidence.get("pad_road") for c in new)
    assert max(x for c in new for x, _y in c.ring) == pytest.approx(360.0, abs=20.0)
    assert len(out.cells) == len(cl.cells) + len(new)


def test_a_pad_already_at_grade_is_not_walked(law):
    cl, (out, rep) = _exit(law, [_way(-1, [(150.0, 150.0)] + _stations(200.0, 150.0, 600.0, 150.0))],
                           level=700.1)
    assert rep["at_grade"] == 1 and rep["exits"] == 0 and out is cl


def test_a_stub_that_leads_nowhere_is_not_made_a_ramp(law):
    """KCLT ``-24651``: a way leaving the pad road's side and ending 6 m
    on, the pad 5 m up — no run for a ramp and nowhere to go.  It is not
    minted (it was: an 8 x 6 m cell at the terrain under the road, 50 %)."""
    stub = _way(-2, [(230.0, 150.0), (230.0, 160.0)])
    cl, (out, rep) = _exit(law, [stub])
    assert rep["exits"] == 1 and rep["dead_end_pieces"] == 1 and rep["cells"] == 0
    assert out is cl


def test_a_road_leaving_straight_off_the_pads_edge_is_an_exit(law):
    """KCLT's garage entries: the way leaves the patch across the pad's own
    edge, no pad road beside it.  It is walked like any exit and the new
    cell is welded to the pad by the one touch witness."""
    from auto_patch_v2.classify.pad_touch import WELD_KEY
    entry = _way(-4, [(150.0, 180.0)] + _stations(150.0, 200.0, 150.0, 500.0))
    _cl, (out, rep) = _exit(law, [entry], road=False)
    new = [c for c in out.cells if c.evidence.get("pad_exit")]
    assert rep["exits"] == 1 and new and rep["welded"] >= 1
    assert any(c.evidence.get(WELD_KEY) for c in new)
    pad = Polygon(_rect(100.0, 100.0, 200.0, 200.0))
    assert min(Polygon(c.ring).distance(pad) for c in new) <= 2.0 * load_rules().cells.snap_grid_m
    assert 100.0 <= rep["run_m"] <= 120.0


# ── C, D: the road that cannot reach ─────────────────────────────────────

class _StepDem(_Dem):
    """700 m on and north of y = 80, ``drop`` lower south of it: the lot's
    ground stands under the pad's."""

    def __init__(self, drop: float):
        super().__init__()
        self.drop = drop

    def z(self, x: float, y: float) -> float:
        return 700.0 - (self.drop if y < 80.0 else 0.0)


def _short_road(law, lot: bool):
    """The pad, a 20 m road off its south edge and — ``lot`` — a lot the
    road ends on; else a second pad there, so that both pads stand free."""
    far = Cell(2, "parking_lot", "lot1", _rect(100.0, 40.0, 200.0, 80.0), (),
               None, None, "groundside", "pavement", {}) if lot else \
        Cell(2, "building", "padB", _rect(100.0, 0.0, 200.0, 80.0), (),
             None, None, "airside", "pad", {})
    road = _road(3, "small_roads:-1", _rect(140.0, 80.0, 160.0, 100.0))
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [far, road]
    return _map(law, cells, only=[3], dem=_StepDem(5.0))


def _face_vs(pm, ref):
    return {v for f in pm.faces.values() if str(f.ref).split("#")[0] == ref
            for v in pm.ring_vertices(f.ring)}


def test_only_a_free_standing_pad_shifts_and_rigidly(law):
    """13f.  Two pads 5 m apart in level, a 20 m road between them (25 %):
    both stand free, each moves the table's cap toward the other as ONE
    pad, and the grade the road still needs is what is left.  A pad with
    other pavement inside the frontage radius is not free-standing; two
    roads asking a pad opposite ways leave it where it is."""
    from auto_patch_v2.constraints.pad_road_reach import (free_standing_pads, pad_road_reach,
                                                         pad_shifts, shift_pads)
    most = float(law.tables.emit.road_contact.pad_shift_max_m)
    _a, pm = _short_road(law, lot=False)
    a, b = _face_vs(pm, "padA"), _face_vs(pm, "padB")
    fixed = {**{v: 700.0 for v in a}, **{v: 695.0 for v in b}}
    reach = pad_road_reach(pm, law, fixed)
    assert {r["pad"] for r in reach} == {"padA", "padB"}
    assert all(r["remainder_m"] for r in reach)
    free = free_standing_pads(pm, law)
    assert free == {"padA", "padB"}
    shifts = pad_shifts(reach, free)
    assert shifts == {"padA": -most, "padB": +most}
    moved = shift_pads(pm, law, fixed, shifts)
    assert moved == {"padA": len(a), "padB": len(b)}
    assert {fixed[v] for v in a} == {700.0 - most} and {fixed[v] for v in b} == {695.0 + most}
    after = pad_road_reach(pm, law, fixed)
    assert all(abs(r["rise_m"]) == pytest.approx(5.0 - 2.0 * most) for r in after)
    # two roads asking opposite ways leave the pad where it is
    assert pad_shifts([{"pad": "padA", "remainder_m": 1.0, "shift_m": 0.5},
                       {"pad": "padA", "remainder_m": -1.0, "shift_m": -0.5}], free) == {}
    # a pad with other pavement beside it is not free-standing
    side = Cell(4, "parking_lot", "lot9", _rect(202.0, 100.0, 260.0, 200.0), (),
                None, None, "groundside", "pavement", {})
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [
        Cell(2, "building", "padB", _rect(100.0, 0.0, 200.0, 80.0), (), None, None,
             "airside", "pad", {}),
        _road(3, "small_roads:-1", _rect(140.0, 80.0, 160.0, 100.0)), side]
    _a2, pm2 = _map(law, cells, only=[3], dem=_StepDem(5.0))
    assert free_standing_pads(pm2, law) == {"padB"}


def test_a_road_that_cannot_reach_is_released_and_published(law):
    """13e, end to end through the last stage: a pad with a lot against its
    east edge, and 20 m of road from it down to another lot 5 m below.  The
    pad is not free-standing and does not move (13f); the road joins both
    continuously — no longitudinal row is relaxed, no step — and its faces
    carry the lifted cap the census reads."""
    from auto_patch_v2.pipeline.late_stage import run_late_stage
    from auto_patch_v2.pipeline.publication import LIFTED_CAP_TAG, face_tags, lifted_caps
    from auto_patch_v2.pipeline.stage_one_map import gap_free
    from auto_patch_v2.solve import solve_design
    airport = _airport(law, _StepDem(5.0))
    far = Cell(2, "parking_lot", "lot1", _rect(100.0, 40.0, 200.0, 80.0), (),
               None, None, "groundside", "pavement", {})
    road = _road(3, "small_roads:-1", _rect(140.0, 80.0, 160.0, 100.0))
    side = Cell(4, "parking_lot", "lot9", _rect(202.0, 100.0, 260.0, 200.0), (),
                None, None, "groundside", "pavement", {})
    cells = [c for c in _ribbon_cells() if c.role != "service_road"] + [far, road, side]
    cells, _n = _cut_back_groundside(cells, law, load_rules(), airport, only=[3], hold=False)
    cl = Classification(tuple(cells), (), {}, ())
    derive = _derive(airport, law)
    pm0, cs0, _s, hold0 = derive(gap_free(cl))
    sol0, _r0 = solve_design(pm0, cs0, law, hold=hold0)
    # the lot STANDS 5 m under the pad (the base solve tilts this fixture's
    # lot up to the pad's ground; the standing levels are what is under test)
    z0 = {v: float(sol0.z[v]) for v in pm0.vertices}
    z0.update({v: 695.0 for v in _face_vs(pm0, "lot1")})
    lines: list[str] = []
    pm1, sol1, rep = run_late_stage(cl, airport, law, derive,
                                    {"pm": pm0, "z": z0, "pin_yield": []},
                                    out=lines.append, roads_only=True)
    ramp = rep["pad_ramp"]
    assert ramp["shifts"] == {} and len(ramp["released"]) >= 1
    rel = ramp["released"][0]
    assert rel["grade"] > 0.10 and rel["rows"] > 0 and rel["faces"]
    assert any("welded to other pavement: stays (13f)" in ln and "GRADE RELEASED" in ln
               for ln in lines)
    # no LONGITUDINAL row is relaxed: the release carried the grade
    assert not any("longitudinal" in ln or "max_grade" in ln
                   for ln in lines if "relaxed by head" in ln)
    # continuous at both ends: every road vertex on a standing ring is AT it
    road_vs = _face_vs(pm1, "small_roads:-1")
    for v in road_vs & set(rep["fixed"]):
        assert sol1.z[v] == pytest.approx(rep["fixed"][v], abs=1e-6)
    # published: the lifted cap on the released faces, and on no other
    caps = lifted_caps(pm1)
    assert set(caps) == set(rel["faces"]) and all(g == rel["grade"] for g in caps.values())
    tags = face_tags(pm1, law, airport)
    assert all(LIFTED_CAP_TAG in tags[f] for f in rel["faces"])
    assert not lifted_caps(pm0)
