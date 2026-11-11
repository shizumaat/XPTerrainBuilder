"""RULINGS 2026-11-10m (#1900 HECA objpav447): a narrow strip of pavement
next to a taxiway, running parallel to its taxi route centreline, is the
taxiway's SHOULDER — one shape with it — and stops at every junction.

``classify/taxi_shoulder.join_taxi_shoulders`` over synthetic scorer rows
(``[role, ref, face, letter, evid, kind]``): a 20 m x 600 m corridor along
y=10, a 8 m strip along its north edge, a crossing road and a stand.
"""
from __future__ import annotations

from auto_patch_v2.classify.roles import TAXI_FAMILY
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.classify.taxi_shoulder import join_taxi_shoulders
from shapely.geometry import LineString, box

AXIS = LineString([(0.0, 10.0), (600.0, 10.0)])


def _taxi():
    return ["cross_connector", "pav1", box(0.0, 0.0, 600.0, 20.0), "E",
            {"kind": "corridor"}, "corridor"]


def _run(rows, startup=lambda f: False):
    stats = join_taxi_shoulders(rows, TAXI_FAMILY, [AXIS], load_rules(), startup)
    return rows, stats


def test_a_parallel_strip_joins_the_taxiway():
    strip = ["service_road", "pav2", box(0.0, 20.0, 600.0, 28.0), None,
             {"kind": "apron", "road_by_proportions": 1.0}, "apron"]
    rows, stats = _run([_taxi(), strip])
    assert stats["taxi_shoulders"] == 1
    sh = [r for r in rows if r[4].get("taxi_shoulder")]
    assert len(sh) == 1
    role, ref, face, letter, evid, _kind = sh[0]
    assert (role, ref, letter) == ("cross_connector", "pav1", "E")
    assert abs(face.area - 600.0 * 8.0) < 1.0
    assert evid["taxi_shoulder_source"] == "pav2"
    assert not [r for r in rows if r[0] == "service_road"]


def test_the_shoulder_stops_where_the_taxiway_ends():
    """The strip runs on 200 m past the corridor's end (a junction there):
    only the part beside the corridor joins it."""
    strip = ["apron", "pav2", box(0.0, 20.0, 800.0, 28.0), None, {}, "apron"]
    rows, _ = _run([_taxi(), strip])
    sh = [r for r in rows if r[4].get("taxi_shoulder")]
    tol = load_rules().cells.on_tol_m          # the contact tolerance
    assert len(sh) == 1 and sh[0][2].bounds[2] <= 600.0 + tol + 1e-6
    rest = [r for r in rows if r[0] == "apron"]
    assert len(rest) == 1 and abs(rest[0][2].area - 200.0 * 8.0) <= 8.0 * tol + 1.0


def test_a_crossing_road_and_mapped_roads_are_not_shoulders():
    cross = ["service_road", "pav3", box(290.0, 20.0, 310.0, 400.0), None, {}, "apron"]
    mapped = ["service_road", "pav4", box(0.0, -8.0, 600.0, 0.0), None,
              {"kind": "strip"}, "strip"]
    rows, stats = _run([_taxi(), cross, mapped])
    assert stats["taxi_shoulders"] == 0
    assert [r[0] for r in rows] == ["cross_connector", "service_road", "service_road"]


def test_a_10l_road_neck_is_the_shoulder_only_away_from_its_road():
    """#1900 (owner 2026-11-10T23:12Z, HECA dsf:objpav99): an L-shaped
    10 m neck — 600 m along the taxiway, then 200 m north beside a mapped
    road up x=600 — is the taxiway's shoulder along the taxiway and the
    road beside the road (``neck.road_arms``' "beside" reach: one road width
    plus its own)."""
    neck = box(0.0, 20.0, 600.0, 30.0).union(box(590.0, 30.0, 600.0, 230.0))
    arm = ["service_road", "pav5", neck, None,
           {"arm_road": 1.0, "neck_width_m": 10.0}, "junction"]
    road = LineString([(600.0, 30.0), (600.0, 400.0)])
    rows = [_taxi(), arm]
    stats = join_taxi_shoulders(rows, TAXI_FAMILY, [AXIS], load_rules(),
                                lambda f: False, [road])
    reach = load_rules().apron.arm_road_max_width_m + 10.0
    sh = [r for r in rows if r[4].get("taxi_shoulder")]
    assert stats["taxi_shoulders"] == 1 and sh[0][0] == "cross_connector"
    assert abs(sh[0][2].area - (600.0 - reach) * 10.0) < 20.0
    road_rows = [r for r in rows if r[0] == "service_road"]
    assert len(road_rows) == 1 and road_rows[0][2].bounds[3] == 230.0


def test_a_strip_beside_a_shoulder_joins_too():
    """#1900 (HECA dsf:objpav447 beside the dsf:objpav99 neck beside
    taxiway G): the join repeats until a round joins nothing."""
    inner = ["service_road", "pav2", box(0.0, 20.0, 600.0, 28.0), None, {}, "apron"]
    outer = ["service_road", "pav3", box(0.0, 28.0, 600.0, 34.0), None, {}, "apron"]
    rows, stats = _run([_taxi(), inner, outer])
    assert stats["taxi_shoulders"] == 2
    assert {r[4].get("taxi_shoulder_source") for r in rows
            if r[4].get("taxi_shoulder")} == {"pav2", "pav3"}
    assert not [r for r in rows if r[0] == "service_road"]


def test_a_deep_page_or_a_stand_is_not_a_shoulder():
    deep = ["apron", "pav6", box(0.0, 20.0, 600.0, 120.0), None, {}, "apron"]
    stand = ["apron", "pav7", box(0.0, -8.0, 600.0, 0.0), None, {}, "apron"]
    rows, stats = _run([_taxi(), deep, stand],
                       startup=lambda f: f.bounds[1] < 0.0)
    assert stats["taxi_shoulders"] == 0
