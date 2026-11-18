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
from shapely.geometry import LineString, Polygon, box

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


# #2170 (owner 1.0.560, KTUL +36-096; KBHM failed the same way): the real
# cells, both VALID; the host carries the classify snap grid (0.01 m) and
# GEOS's 1 m buffer of its ring comes back self-intersecting on that grid
KTUL_HOST = (
    "POLYGON ((417.86 1561.28, 419.44 1559.74, 420.84 1561.15, 421.42 "
    "1560.55, 424.52 1557.33, 427.31 1553.61, 429.35 1549.95, 430.8 1546.35, "
    "431.81 1542.8, 432.52 1539.27, 433.08 1535.76, 432.65 1527.94, 432.55 "
    "1527.95, 432.53 1527.46, 429.66 1475.29, 426.79 1423.12, 423.91 1370.96,"
    " 421.04 1318.8, 418.17 1266.63, 415.3 1214.47, 412.43 1162.31, 409.56 "
    "1110.15, 406.69 1057.98, 405.13 1029.59, 404.08 1028.62, 403.56 1005.77,"
    " 403.29 993.85, 403.15 990.68, 402.56 977.49, 402.37 975.04, 401.72 "
    "966.66, 401.22 960.67, 399.96 945.68, 399.02 934.49, 398.69 930.7, "
    "397.42 915.71, 396.8 908.3, 393.39 900.97, 393.34 900.85, 391.82 897.58,"
    " 391.66 897.35, 391.56 897.21, 391.18 896.84, 399.24 1049.23, 406.92 "
    "1194.55, 413.75 1323.58, 419.29 1428.18, 423.12 1500.22, 424.82 1531.58,"
    " 424.16 1538.21, 422.82 1543.55, 420.93 1547.88, 420.75 1548.15, 418.62 "
    "1551.43, 416.06 1554.43, 414.09 1556.44, 414.47 1556.8, 415.01 1557.31, "
    "415.54 1557.82, 416.07 1558.33, 417.26 1559.47, 416.65 1560.16, 417.48 "
    "1560.93, 417.86 1561.28))")
KTUL_FACE = (
    "POLYGON ((-104.55 930.64, -61.21 928.47, -18.59 926.35, 19.61 924.45, "
    "51.2 922.89, 73.95 921.77, 86.08 921.18, 86.56 920.27, 89.33 915.06, "
    "92.28 910.8, 95.13 907.73, 97.91 905.53, 100.67 903.88, 103.35 902.56, "
    "107.3 902.16, 115.74 901.28, 128.26 899.99, 140.78 898.7, 153.3 897.4, "
    "165.81 896.11, 178.36 894.81, 179.31 894.64, 180.23 894.47, 181.15 "
    "894.3, 182.07 894.13, 182.99 893.96, 183.87 893.8, 200.51 892.87, 217.2 "
    "891.93, 233.89 890.99, 250.58 890.06, 267.27 889.12, 283.95 888.19, "
    "284.68 888.18, 285.42 888.16, 286.17 888.15, 286.92 888.14, 287.66 "
    "888.13, 288.42 888.12, 299.51 887.68, 310.58 887.25, 321.66 886.82, "
    "332.74 886.39, 343.82 885.96, 347.61 885.81, 347.59 885.15, 348.92 "
    "885.08, 350.25 885.01, 351.57 884.94, 352.9 884.87, 354.23 884.81, "
    "355.55 884.74, 355.57 885.51, 356.59 885.48, 358.33 885.44, 360.13 "
    "885.39, 362.04 885.36, 364.07 885.34, 366.28 885.32, 368.45 885.39, "
    "370.72 885.61, 373.03 885.98, 375.32 886.54, 377.54 887.28, 379.62 "
    "888.22, 381.7 889.44, 383.56 890.73, 385.24 892.07, 386.78 893.46, "
    "388.25 894.88, 389.48 896.13, 397.5 1047.75, 390.17 895.85, 387.27 "
    "893.04, 387.21 891.61, 386.31 890.8, 384.55 889.39, 382.6 888.04, 381.29"
    " 887.27, 380.39 886.75, 378.14 885.73, 375.78 884.94, 373.35 884.36, "
    "370.93 883.96, 368.55 883.73, 366.27 883.66, 364.06 883.68, 362.01 "
    "883.7, 360.1 883.74, 358.29 883.78, 356.55 883.82, 354.83 883.87, 343.75"
    " 884.3, 332.67 884.73, 321.6 885.16, 310.52 885.59, 299.44 886.03, "
    "288.37 886.46, 287.64 886.47, 286.89 886.48, 286.14 886.49, 285.4 886.5,"
    " 284.65 886.52, 283.89 886.53, 267.18 887.47, 250.49 888.4, 233.8 "
    "889.34, 217.11 890.27, 200.42 891.21, 183.67 892.15, 182.69 892.33, "
    "181.77 892.5, 180.85 892.67, 179.93 892.84, 179.01 893.01, 178.12 "
    "893.17, 165.64 894.46, 153.12 895.75, 140.6 897.05, 128.09 898.34, "
    "115.57 899.63, 102.89 900.94, 99.9 902.42, 96.98 904.15, 94 906.51, "
    "90.98 909.77, 87.91 914.2, 85.02 919.59, 73.86 920.11, 51.11 921.23, "
    "19.53 922.8, -18.67 924.69, -61.3 926.82, -106.71 929.07, -107.39 930.7,"
    " -107.81 932.22, -108.14 934.46, -108.36 937.77, -108.43 942.53, -108.32"
    " 949.13, -108.05 957.71, -107.66 967.97, -107.17 979.57, -106.61 992.18,"
    " -106.06 1004.34, -104.4 1004.28, -104.95 992.11, -105.51 979.5, -106 "
    "967.9, -106.39 957.65, -106.66 949.08, -106.77 942.53, -106.7 937.83, "
    "-106.49 934.63, -106.18 932.57, -105.82 931.26, -105.59 930.69, -104.55 "
    "930.64))")


def test_a_self_intersecting_host_band_never_fails_the_join():
    """#2170: the join reads every operand it builds through ``valid_area``
    where GEOS calls it invalid — no TopologyException, the airport keeps
    its patch."""
    import shapely
    host = shapely.set_precision(shapely.from_wkt(KTUL_HOST), 0.01)
    face = shapely.from_wkt(KTUL_FACE)
    tol = load_rules().cells.on_tol_m
    assert host.is_valid and face.is_valid
    assert not host.boundary.buffer(tol).is_valid        # the GEOS defect
    rows = [["cross_connector", "pav238", host, "C", {"kind": "corridor"}, "corridor"],
            ["apron", "pav50", face, None, {}, "apron"]]
    axis = LineString(list(host.exterior.coords)[:2])
    join_taxi_shoulders(rows, TAXI_FAMILY, [axis], load_rules(), lambda f: False)
    assert all(r[2].is_valid for r in rows)


def test_an_invalid_strip_never_fails_the_join():
    """#2170: a self-touching (bow-tie) strip beside the corridor is read
    as its valid area; the join runs."""
    bowtie = Polygon([(0.0, 20.0), (600.0, 28.0), (600.0, 20.0), (0.0, 28.0)])
    assert not bowtie.is_valid
    rows, _stats = _run([_taxi(), ["apron", "pav2", bowtie, None, {}, "apron"]])
    assert all(r[2].is_valid for r in rows if r[4].get("taxi_shoulder"))
