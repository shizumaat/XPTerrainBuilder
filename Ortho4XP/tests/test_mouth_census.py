"""The census reads a declared walled tunnel MOUTH as CARRIED GROUND (owner
RULINGS 2026-10-15b, census option 1; the mouth is RULINGS 15a (1)(2)) and
reads a declared wall's riser once (``check_grade.DeclaredWallSteps``).

* the emitter's mouth label is the literal the census keys on;
* a mouth joint is carried along its whole run, a pack wall is not;
* a carried mouth point inside a runway strip is no wall at the edge,
  while the same point of a pack wall still reports (2026-08-01);
* the zone-strip within-face step across a declared wall line is forgiven
  up to the LARGEST declared step crossed — never their sum.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_ROOT, "tools"), os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade as cg  # noqa: E402


def _xy(lat, lon):
    return (lon, lat)


def _joint(label, step=10.0, x=0.0):
    return {"kind": "wall_terrace", "step_m": step, "shapes": [label],
            "points": [[-5.0, x], [0.0, x], [5.0, x]]}


MOUTH = "New Buildings/tunnel.obj" + cg.MOUTH_WALL_LABEL_SUFFIX
WALL = "objects/wall.obj#comp0"


def test_emitter_mouth_label_is_the_census_literal():
    from auto_patch_v2.airport.road_ramp import mouth_wall_pieces
    pm = SimpleNamespace(mouth_walls=[(((0, 0), (10, 0), (10, 2), (0, 2)),
                                       8.0, "New Buildings/tunnel.obj")])
    (piece,) = mouth_wall_pieces(pm)
    assert piece.mouth and piece.label.endswith(cg.MOUTH_WALL_LABEL_SUFFIX)
    assert cg._is_mouth_wall_joint({"kind": cg.WALL_TERRACE_JOINT_KIND,
                                    "shapes": [piece.label]})


def test_mouth_is_carried_wall_is_not():
    flags = cg._terrace_joint_carried_flags([_joint(MOUTH), _joint(WALL)])
    assert flags == [[True] * 3, [False] * 3]
    # the label alone is not enough: the kind is the declaration
    assert cg._terrace_joint_carried_flags(
        [dict(_joint(MOUTH), kind="apron_terrace")]) == [[False] * 3]


def test_carried_mouth_in_runway_strip_is_not_a_wall_at_the_edge(monkeypatch):
    ring = [(-50.0, -50.0), (50.0, -50.0), (50.0, 50.0), (-50.0, 50.0),
            (-50.0, -50.0)]
    monkeypatch.setattr(cg, "_runway_strip_keepout_rings",
                        lambda ways, nodes, ll_to_m: [ring])
    rows = [_joint(MOUTH), _joint(WALL)]
    jm = cg._terrace_joints_to_m(rows, _xy)
    carried = cg._terrace_joint_carried_flags(rows)
    out = cg._check_terrace_joint_in_runway_strip(jm, [], {}, _xy,
                                                  carried_flags=carried)
    assert len(out) == 1                      # the pack wall alone


def test_declared_wall_allowance_is_the_largest_step_crossed():
    walls = cg.DeclaredWallSteps(
        [_joint(MOUTH, 12.0), _joint(MOUTH, 9.0, x=0.5),
         dict(_joint(WALL, 30.0, x=0.2), kind="apron_terrace")], _xy)
    assert walls.allowance(-1.0, 0.0, 1.0, 0.0) == 12.0    # max, not 21
    assert walls.allowance(2.0, 0.0, 3.0, 0.0) == 0.0      # beside the line
    assert cg.DeclaredWallSteps([], _xy).allowance(-1, 0, 1, 0) == 0.0


def _ag_way(elevs):
    nids = ["a", "b", "a"]
    return cg.Way("-1", "graded_strip", cg.V2_ADJACENT_GROUND_REF_PREFIX + "x",
                  "", nids, elevs, {})


def test_adjacent_ground_step_across_a_wall_reads_the_wall_once():
    nodes = {"a": (0.0, -1.0), "b": (0.0, 1.0)}             # 2 m apart
    walls = cg.DeclaredWallSteps([_joint(MOUTH, 12.0)], _xy)
    under = cg._check_adjacent_ground_steps(
        [_ag_way([110.0, 100.0, 110.0])], nodes, _xy, 0.5, 0.5, walls)
    over = cg._check_adjacent_ground_steps(
        [_ag_way([115.0, 100.0, 115.0])], nodes, _xy, 0.5, 0.5, walls)
    bare = cg._check_adjacent_ground_steps(
        [_ag_way([110.0, 100.0, 110.0])], nodes, _xy, 0.5, 0.5)
    assert under == [] and len(over) == 2 and len(bare) == 2


def test_pack_wall_declares_its_height_along_its_outline():
    """owner RULINGS 2026-10-19ao (#507): a pack wall's declared step is its
    HEIGHT, read along the whole outline — never the step at its one lot
    pairing the emitter published; a mouth keeps the step it carries."""
    wall = dict(_joint(WALL, 1.6049), height_m=3.102)
    mouth = dict(_joint(MOUTH, 1.0), height_m=8.0)
    tall_step = dict(_joint(WALL, 4.0), height_m=3.102)
    jm = cg._terrace_joints_to_m([wall, mouth, tall_step], _xy)
    assert [s for _p, s in jm] == [3.112, 1.0, 4.0]
    walls = cg.DeclaredWallSteps([wall], _xy)
    assert walls.allowance(-1.0, 0.0, 1.0, 0.0) == 3.112
    # a row without a height (an older sidecar) reads as published
    assert cg._declared_joint_step(_joint(WALL, 1.6)) == 1.6
