"""#1952 KMCI round 4 (S2): A ROAD LEAVES A FOOT LOT FROM THE FOOT.

A road vertex on the ring of a lot at a wall's foot (``airport/foot_lot.
foot_vertices``) takes the lot's foot: its §37 (6) ramp target and ceiling
are withdrawn (as a mouth's), and the road's ramp is seeded there -- a cut
(``road_descent.climb``) where the foot stands under the road's floor --
so beyond the lot the road climbs out at the design grade.  MEASURED KMCI:
``small_roads:-12627`` carried "ramp to the DEM" targets 303.29-303.43 m on
five ring vertices of lot ``dsf:objpav660`` (foot 299.82 m)."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport import road_ramp as rr
from auto_patch_v2.airport.road_ramp import WallPiece, with_road_ramp
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build
from shapely.geometry import LineString, box
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
from tests.auto_patch_v2.test_v2roadramp import (
    PLATEAU_Z,
    ROAD_W,
    RUN_LEN,
    _airport,
    _Hill,
    _road_vertices,
)

FOOT = PLATEAU_Z - 3.5


class _Flat(_Hill):
    def z(self, x, y):
        return PLATEAU_Z


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _arm(law, monkeypatch, low_side):
    """The lot (map y -220..-20) with a road leaving its edge (y = -20) for
    300 m; ``low_side`` None: no wall, else a wall along the lot's far
    side (y = -220) whose lower band covers the lot's last 10 m."""
    airport, r = _airport(law, _Flat())
    cells = (Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                              HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
             Cell(1, "parking_lot", "lotA", _rect(r, -220.0, 150.0, -20.0, 250.0), (),
                  None, "D", "groundside", "parking_lot", {}),
             Cell(2, "service_road", "roadA", _rect(r, -20.0, 200.0 - ROAD_W / 2.0, 280.0,
                                                    200.0 + ROAD_W / 2.0), (),
                  None, "D", "groundside", "service_road", {}))
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    lot = next(f for f in pm.faces.values() if f.role == "parking_lot")
    xs = [pm.vertices[v].xy[0] for v in pm.ring_vertices(lot.ring)]
    ys = [pm.vertices[v].xy[1] for v in pm.ring_vertices(lot.ring)]
    x0, x1, y0 = min(xs), max(xs), min(ys)
    walls = () if low_side is None else (WallPiece(
        box(x0, y0 - 1.0, x1, y0), 3.5, "skirt.obj#comp0", False, False, None, None,
        LineString([(x0, y0), (x1, y0)]), ((0.0, FOOT), (x1 - x0, FOOT)),
        box(x0, y0, x1, y0 + 10.0), low_side),)
    monkeypatch.setattr(rr, "wall_pieces", lambda _ap, _cfg=None: walls)
    rep: dict = {}
    pm = with_road_ramp(pm, law, airport, rep, service=load_rules().service)
    ring = {v for v in pm.ring_vertices(lot.ring)}
    return pm, rep, ring


def test_a_road_leaves_a_foot_lot_from_the_foot(law, monkeypatch):
    pm, rep, ring = _arm(law, monkeypatch, "sheets")
    tg = pm.road_ramp_z
    on_ring = [v for v in _road_vertices(pm) if v in ring]
    assert on_ring and not any(v in tg for v in on_ring)      # no ramp row there
    assert rep["foot_withdrawn"] == len(on_ring) and rep["foot_cuts"] > 0, rep
    design = rep["design"]
    seen = 0
    for v in _road_vertices(pm):
        if v in ring or v not in tg:
            continue
        s = max(0.0, pm.vertices[v].xy[1] + 20.0)
        want = min(PLATEAU_Z, FOOT + design * s)
        assert tg[v] == pytest.approx(want, abs=0.6), (v, s, tg[v], want)
        seen += want < PLATEAU_Z - 0.6
    assert seen          # the road climbs out of the foot over a run


def test_no_foot_lot_leaves_the_targets_as_they_were(law, monkeypatch):
    """A DEM-witnessed wall names no foot: the targets are byte-identical
    to the map with no wall."""
    pm0, _r0, _ = _arm(law, monkeypatch, None)
    pm1, rep, _ = _arm(law, monkeypatch, "dem")
    assert pm1.road_ramp_z == pm0.road_ramp_z and rep["foot_withdrawn"] == 0


# ── #1971 v2 §3.4 (T23): a road leaves a pack deck's end as it leaves a foot ──

def _deck_end_arm(law, top_over):
    """A lone road (y 200, x -20..280) on flat ground; its x = -20 end pair
    is a deck's end line at ``PLATEAU_Z + top_over``."""
    airport, r = _airport(law, _Flat())
    cells = (Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                              HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
             Cell(1, "service_road", "roadA", _rect(r, -20.0, 200.0 - ROAD_W / 2.0, 280.0,
                                                    200.0 + ROAD_W / 2.0), (),
                  None, "D", "groundside", "service_road", {}))
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    roads = _road_vertices(pm)
    x0 = min(pm.vertices[v].xy[0] for v in roads)
    end = {v: (PLATEAU_Z + top_over, pm.vertices[v].xy[0] - x0) for v in roads
           if pm.vertices[v].xy[0] < x0 + 0.5}
    base = rr.road_ramp_targets(pm, law, airport)
    got = rr.road_ramp_targets(pm, law, airport, deck_ends=end)
    return pm, end, base, got, x0


@pytest.mark.parametrize("top_over", (1.5, -0.8))
def test_t23_a_deck_end_seeds_the_ramp_with_the_hold(law, top_over):
    pm, end, base, got, x0 = _deck_end_arm(law, top_over)
    assert end and got.report["_foot"] >= frozenset(end)
    g = float(law.tables.emit.road_contact.ramp_grade)
    H = float(law.tables.structures.bridge.abutment_sample_step_m)
    top = PLATEAU_Z + top_over
    seen = 0
    for v, z in got.targets.items():
        if v in end:
            continue
        s = pm.vertices[v].xy[0] - x0
        want = top - g * max(0.0, s - H) if top_over > 0 else top + g * max(0.0, s - H)
        if top_over > 0:
            assert z >= min(want, PLATEAU_Z) - 0.6, (s, z, want)
        else:
            assert z <= max(want, PLATEAU_Z) + 0.6, (s, z, want)
        seen += abs(z - PLATEAU_Z) > 0.05
    assert seen                       # the ramp reaches past the seed
    assert got.report["deck_end_seeds" if top_over > 0 else "deck_end_cuts"] == len(end)
    assert rr.road_ramp_targets(pm, law, _airport(law, _Flat())[0]).targets == base.targets
