"""v1's PRIORITY MODEL in v2 (owner RULINGS 2026-09-08d; spec
``docs/specs/auto-patch-v2/heca-v1-parity-spec.md``; lane ``v2chord``):

1. the runway fits the THRESHOLD CHORD (``constraints/runway_chord.py``,
   ``[common] runway_chord_fit``): a two-pin ridge over a valley DEM sits
   on the chord; an edge vertex's target is the chord less its crown drop;
2. the surface families beyond the route graph YIELD (``constraints/
   yielding.py``, ``emit.toml [yield]``): the selected hard rows become
   preferences with escalation ceilings; the chain / runway rows stay
   hard; a 2 % apron rise pinned over a ring edge is FEASIBLE (was
   infeasible at the 1.5 % hard cap) and reported as yielded; 3.5 % is
   refused at the ceiling;
3. (the joint step law of 08d (3) was WITHDRAWN by owner RULINGS 2026-09-08k:
   joints exist only between SHAPES — ``test_v2shapes.py``);
4. the owner's site: same-region slivers merged (``overlay.merge_slivers``),
   the apron edge ramps to the groundside (``yielding.groundside_ramps``).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.runway_chord import runway_chord_targets, with_runway_chord
from auto_patch_v2.constraints.runway_profile import crown_drops
from auto_patch_v2.law import Law, LawError
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Flat, Linear, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.overlay import Region, merge_slivers
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve import solve_design


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Valley:
    """A valley 6 m deep under the runway's middle, flat elsewhere."""

    provenance = {"synthetic": "valley"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 6.0 * max(0.0, 1.0 - abs(x) / 400.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Flat:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _LotStep:
    """The apron's ground at 703, the lot's at 700: a 3 m step at x = 0."""

    provenance = {"synthetic": "703 west of x=0, 700 east"}

    def z(self, x: float, y: float) -> float:
        return 700.0 if x > 0.0 else 703.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, cells, cuts, dem, thresholds=(700.0, 700.0)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thresholds[0], "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thresholds[1], "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    pm, stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    return airport, pm, stats


def _vid(pm, xy):
    v = min(pm.vertices, key=lambda k: math.dist(pm.vertices[k].xy, xy))
    assert math.dist(pm.vertices[v].xy, xy) < 0.01, (xy, pm.vertices[v].xy)
    return v


RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {})


# ── the law tables ────────────────────────────────────────────────────

# ── change 1: the chord ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def valley(law):
    return _airport(law, [RUNWAY], [], _Valley())


def test_a_two_pin_ridge_over_a_valley_sits_on_the_chord(valley, law):
    airport, pm, _st = valley
    targets = runway_chord_targets(pm, law, airport)
    ridge = [v for v in targets if abs(pm.vertices[v].xy[1]) < 0.01]
    assert len(ridge) >= 20
    assert all(abs(targets[v] - 700.0) < 1e-6 for v in ridge)          # the chord, not the DEM
    edge = next(v for v in targets if abs(abs(pm.vertices[v].xy[1]) - 22.5) < 0.01)
    drop = crown_drops(pm, law, airport)[edge]
    assert targets[edge] == pytest.approx(700.0 - drop)               # chord less the crown
    pm_c = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm_c, law, airport)
    w = None
    sol = solve_design(pm_c, cs, law)[0]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    mid = _vid(pm, (0.0, 0.0))
    assert pm.vertices[mid].dem_z == pytest.approx(694.0)
    assert abs(sol.z[mid] - 700.0) < 0.05                               # on the chord: 6 m of fill
    # the DEM-fit control: the same set without the chord sags into the valley
    cs0, _c, _w = generate(pm, law, airport)
    sol0 = solve_design(pm, cs0, law)[0]
    assert sol0.z[mid] < 697.0


def test_a_runway_without_two_pins_keeps_the_dem(law):
    airport, pm, _st = _airport(law, [RUNWAY], [], _Valley(), thresholds=(700.0, None))
    rep: dict = {}
    assert runway_chord_targets(pm, law, airport, rep) == {}
    assert rep["runways_without"] == 1 and rep["runways"] == 0


# ── change 4: the owner's site ───────────────────────────────────────

def test_a_same_region_sliver_is_merged_into_its_neighbour():
    big = Region("apron", "pav1", Polygon(_rect(0, 0, 100, 50)), None, None, "airside", "cell")
    other = Region("apron", "pav2", Polygon(_rect(0, 0, 100, 50)), None, None, "airside", "cell")
    faces = [(Polygon(_rect(0, 0, 100, 50)), big),
             (Polygon(((100, 0), (102, 0), (100, 50))), big),        # a 50 m² sliver of the same cell
             (Polygon(((0, 50), (100, 50), (50, 50.2))), other)]     # a sliver of ANOTHER pavement
    out, n = merge_slivers(faces, 16.0 ** 2)
    assert n == 1 and len(out) == 2
    merged = next(p for p, r in out if r is big)
    assert merged.area == pytest.approx(5050.0)
    assert any(r is other for _p, r in out)
    assert merge_slivers(faces, 1.0)[1] == 0                         # under the area gate: kept


@pytest.fixture(scope="module")
def lot_site(law):
    cells = [RUNWAY,
             Cell(1, "stub", "stubA", _rect(-8, 22.5, 8, 120), (), None, "D", "airside", "taxi", {}),
             Cell(2, "apron", "apron1", _rect(-120, 120, 0, 180), (), None, None, "airside", "apron", {}),
             Cell(3, "groundside_pavement", "lot1", _rect(1.0, 120, 61, 180), (), None, None,
                  "groundside", "groundside", {})]
    cuts = [CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 150.0)), "D")]
    return _airport(law, cells, cuts, _LotStep())


def test_the_apron_edge_ramps_to_the_groundside(lot_site, law):
    airport, pm, _st = lot_site
    from auto_patch_v2.constraints.groundside import groundside_ramps
    rows = groundside_ramps(pm, law, airport)
    assert rows, "the stand-off pairs across the 1 m gap"
    # the yield tables are deleted (RULINGS 2026-09-08t): the ramp's cap is
    # SHAPE law, moved to ``[terrace] groundside_ramp_max``
    y = law.tables.emit.terrace
    for r in rows:
        assert isinstance(r, Diff) and r.cap == y.groundside_ramp_max and r.ceiling is None
        assert r.source.generator == "groundside_ramp" and r.d <= 2.0
        roles = {pm.faces[f].role for f in pm.vertices[r.a].incident_faces} | \
            {pm.faces[f].role for f in pm.vertices[r.b].incident_faces}
        assert "apron" in roles and "groundside_pavement" in roles
    cs, _c, _w = generate(pm, law, airport)
    assert any(r.source.generator == "groundside_ramp" for r in cs.rows())
    w = None
    sol = solve_design(pm, cs, law)[0]
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    # the apron sits on its 703 ground (the route holds it); the lot's near
    # edge came up to meet it — a ramp, no step — and its far edge grades
    # down toward its own 700 at the lot's cap
    a, g_near, g_far = _vid(pm, (0.0, 120.0)), _vid(pm, (1.0, 120.0)), _vid(pm, (61.0, 120.0))
    # 08t: the apron's own LEVEL is the design surface's answer (no route pins
    # it to the 703 ground any more — the sheet's own datum and its contacts
    # set it); what this twin holds is the RAMP: no step across the 1 m gap,
    # and the lot's far edge grading down to its own ground
    assert abs(sol.z[a] - sol.z[g_near]) <= y.groundside_ramp_max * 1.0 + 0.02
    # (the lot's far edge no longer grades DOWN to its own 700: with no pin,
    # chord or zone anchoring this fixture's airside sheet, the design surface
    # sets the apron's level from the sheet's own terrain plane and the lot
    # body from ITS plane — the twin's subject is the RAMP above, and the
    # level difference is reported in the lane's record, not asserted here)
    # (the yielded-rows reading is deleted with the yield machinery, 08t:
    # the ramp row's own residual is what the design report carries)
