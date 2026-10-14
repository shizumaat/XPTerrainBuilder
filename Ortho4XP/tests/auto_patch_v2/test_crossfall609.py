"""Issue #609 follow-up (lane crossfall609): THE PAD ROADS' STAGE LEAVES
NOTHING STANDING UNDER A ROAD ROW IT CANNOT HOLD.

* A pad road is junior to every standing level it meets (owner RULINGS
  2026-10-13a (1)): its ABSOLUTE §37 (6) ramp ceiling (a DEM profile from
  its airside contact) leaves EVERY unknown of it, not only the ones a pad
  rim reaches.  MEASURED HECA round 5: pad roads welded to a gap part 8 m
  over the DEM and reached from no rim kept the ceiling — 45 rows relaxed,
  worst 16.85 m.
* A standing cell's node the pad roads' arrangement NOTCHED off its edge is
  still that cell's and takes its edge's level (``late_rim_levels``
  ``notch_m``), a pad's at any distance (``rigid``).  MEASURED HECA round
  5: 301 such nodes stood as unknowns.
"""
from __future__ import annotations

import types

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.pipeline import stage_one_map as som

from tests.auto_patch_v2.test_late_stage import _pm
from tests.auto_patch_v2.test_pad_touch import _rect
from tests.auto_patch_v2.test_roads609 import _ribbon_cells
from tests.auto_patch_v2.test_roads609e import _map, _road


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_the_absolute_ramp_ceiling_leaves_every_pad_road_unknown(law):
    from auto_patch_v2.constraints.pad_ramp import pad_ramp_rewrite
    from auto_patch_v2.constraints.pads import pad_welded_vertices
    from auto_patch_v2.constraints.road_ramp import GEN, RULING_CEILING
    from auto_patch_v2.model.constraints import Band, ConstraintSet, Source
    from auto_patch_v2.model.planar import pad_road_faces
    # a pad road welded to padA's south edge, and a second one 100 m north
    # of the pad that no rim reaches (welded, in the build, to another
    # standing level)
    far = _road(2, "small_roads:-2", _rect(0.0, 300.0, 300.0, 308.0))
    cells = [*_ribbon_cells(), far]
    _a, pm = _map(law, cells, only=[2])
    rim = pad_welded_vertices(pm, law)
    road_vs = {v for f in pad_road_faces(pm) for v in pm.ring_vertices(f.ring)}
    far_vs = {v for f in pad_road_faces(pm) if f.ref == "small_roads:-2"
              for v in pm.ring_vertices(f.ring)}
    assert rim and far_vs
    cs = ConstraintSet.from_rows([
        Band(v, None, 690.0, Source(GEN, RULING_CEILING, (f"vertex:{v}", "x")))
        for v in sorted(road_vs - rim)])
    out, rep = pad_ramp_rewrite(pm, law, cs, {v: 705.0 for v in rim})
    left = [b.v for b in out.bands if b.source.ruling == RULING_CEILING]
    assert left == [], f"{len(left)} absolute ceilings kept, {len(set(left) & far_vs)} on the far road"


def test_a_notched_node_of_a_standing_cell_takes_its_edge_level():
    base = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], [("parking_lot", "dsf:pol10", (0, 1, 2))])
    base.edges = {k: types.SimpleNamespace(a=a, b=b)
                  for k, (a, b) in enumerate([(0, 1), (1, 2), (2, 0)])}
    # node 3 stands 0.8 m off the lot's south edge (pass C's notch), node 4
    # as far off but on ANOTHER ref, node 5 2 m off
    full = _pm([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (2.5, -0.8), (5.0, -0.8), (7.5, -2.0)], [])
    full.faces = {0: types.SimpleNamespace(ref="dsf:pol10"), 1: types.SimpleNamespace(ref="dsf:pol99")}
    for i, v in full.vertices.items():
        v.incident_faces = (1,) if i == 4 else (0,)
    z = {0: 100.0, 1: 104.0, 2: 90.0}
    fixed = dict(z)
    rep = som.late_rim_levels(base, z, full, fixed, set(), 0.01, notch_m=1.5)
    assert fixed[3] == pytest.approx(101.0) and 4 not in fixed and 5 not in fixed
    assert rep == {"rim_nodes": 3, "on_a_base_edge": 0, "off_edge": 2, "notched": 1}
    # without the notch the node stays an unknown (the gap stage's reading)
    fixed = dict(z)
    assert som.late_rim_levels(base, z, full, fixed, set(), 0.01)["off_edge"] == 3


def test_a_pad_node_beyond_the_notch_stands_on_its_pad():
    """A pad stands where it stands: a node the pad roads' arrangement left
    on a pad farther than the notch from its edges takes its pad's nearest
    base edge — never an unknown of the road's solve (MEASURED OTHH round 5:
    ``building9``'s sliver floated 5 cm over its rim)."""
    base = _pm([(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)],
               [("building", "padA", (0, 1, 2, 3))])
    base.edges = {k: types.SimpleNamespace(a=a, b=b)
                  for k, (a, b) in enumerate([(0, 1), (1, 2), (2, 3), (3, 0)])}
    full = _pm([(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0), (10.0, 5.0)], [])
    full.faces = {0: types.SimpleNamespace(ref="padA", role="building")}
    for v in full.vertices.values():
        v.incident_faces = (0,)
    z = {0: 100.0, 1: 100.2, 2: 100.2, 3: 100.0}        # 1 % along x
    fixed = dict(z)
    rep = som.late_rim_levels(base, z, full, fixed, set(), 0.01, notch_m=1.5,
                              rigid=frozenset({"building"}))
    assert fixed[4] == pytest.approx(100.1)
    assert rep["notched"] == 1 and rep["off_edge"] == 0
    # a cell of no rigid role keeps the notch's reach
    full.faces[0].role = "parking_lot"
    fixed = dict(z)
    assert som.late_rim_levels(base, z, full, fixed, set(), 0.01, notch_m=1.5,
                               rigid=frozenset({"building"}))["off_edge"] == 1
