"""THE LOWER LEVEL OF A STEPPED UNIT'S PAD (owner RULINGS 2026-10-19ai, #809;
``planar/low_level``): a held pad whose pack unit carries parts a storey
under its frontage level is split into its high block, a lower level
``<ref>/p1`` over those parts and the riser strip between."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import plane_of, plane_origin_ref
from auto_patch_v2.planar.low_level import plan_low
from shapely.geometry import box


def _part(x0, y0, x1, y1, base_y):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 rings=(ring,), feet=(), line=False)


def _stepped(x, y):
    """KATL's ground: a storey down landside (y < 85) of the apron's."""
    return 289.5 if y < 85.0 else 301.2


def _airport(parts, ground=_stepped):
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=parts)])
    return types.SimpleNamespace(
        partition=types.SimpleNamespace(units=[unit]),
        frame=types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat))),
        dem=types.SimpleNamespace(z=ground))


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="faa")


P = box(0.0, 0.0, 200.0, 100.0)          # the held pad; the apron north of it
AIR = box(0.0, 100.0, 200.0, 130.0)
FRONT = [_part(10.0 + 40.0 * i, 92.0, 40.0 + 40.0 * i, 100.0, 0.0) for i in range(4)]


def test_a_storey_down_is_a_lower_level_tied_by_its_band(law):
    low = [_part(0.0, 0.0, 100.0, 80.0, -13.0), _part(100.0, 0.0, 200.0, 80.0, -12.9)]
    got = plan_low(P, AIR, _airport(FRONT + low), law, 0.5)
    assert got is not None
    H, L, S, rec = got
    assert L.area == pytest.approx(200.0 * 80.0, rel=0.02)
    assert H.area > 0.0 and S.area > 0.0
    assert L.intersection(H).area == pytest.approx(0.0, abs=1e-6)
    assert L.distance(AIR) >= 3.0 - 1e-6                     # the frontage stays high
    assert rec["top_y"] == 0 and rec["y_lo"] == pytest.approx(-13.0)
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    assert rec["y_hi"] == pytest.approx(-step)


def test_no_storey_no_split(law):
    sill = [_part(0.0, 0.0, 100.0, 80.0, -1.0)]               # under one storey
    assert plan_low(P, AIR, _airport(FRONT + sill), law, 0.5) is None
    small = [_part(0.0, 0.0, 30.0, 30.0, -13.0)]              # under the unit-pad bar
    assert plan_low(P, AIR, _airport(FRONT + small), law, 0.5) is None


def test_parts_a_storey_down_over_level_ground_are_no_lower_level(law):
    """#1115 (EDDF Terminal 1, 50.0483, 8.5725): frontage parts authored a
    storey UP (piers, decks) made the ground-floor parts read "low" over
    ground level with the block's; the split forced a level 3 m into it
    and 1,092 pad rows relaxed.  The ground is the other half of the
    witness: no split where it does not drop a storey."""
    low = [_part(0.0, 0.0, 100.0, 80.0, -13.0), _part(100.0, 0.0, 200.0, 80.0, -12.9)]
    why: list = []
    assert plan_low(P, AIR, _airport(FRONT + low, lambda x, y: 110.4), law, 0.5,
                    refused=why) is None
    assert why and why[0].startswith("ground drop +0.00")
    def shallow(x, y):                                         # 2 m: under a storey
        return 108.4 if y < 85.0 else 110.4
    assert plan_low(P, AIR, _airport(FRONT + low, shallow), law, 0.5) is None
    got = plan_low(P, AIR, _airport(FRONT + low), law, 0.5)      # KATL's 11.7 m
    assert got is not None and got[3]["ground_z"] == pytest.approx(289.5)
    assert got[3]["ground_high_z"] == pytest.approx(301.2)


def test_the_object_stage_folds_the_lower_level_into_its_block():
    assert plane_of("building31/b0/p1") == ("building31/b0", 1)
    assert plane_origin_ref("building31/b0/p1") == "building31/b0"
    assert plane_origin_ref("building31/b0/p1#strip") == "building31/b0"
    assert plane_origin_ref("building31/b0") == "building31/b0"
    assert plane_origin_ref("unit/p1/b2") == "unit/p1/b2"     # a block inside a plane pad


def test_the_bending_skips_the_riser():
    """The riser between a block and its lower level is a declared step:
    ``solve/wall_cut`` cuts every triangle edge from a lower-level vertex
    to a strip vertex off that level, and nothing else."""
    from auto_patch_v2.solve.wall_cut import wall_cut_edges
    F = types.SimpleNamespace
    faces = {0: F(ref="b/b0", ring=(0, 1), holes=()),
             1: F(ref="b/b0/p1#strip", ring=(1, 2, 3, 4), holes=()),
             2: F(ref="b/b0/p1", ring=(3, 4, 5), holes=())}
    planar = F(faces=faces, ring_vertices=lambda r: tuple(r), road_terrace={})
    tris = [(1, 2, 3), (2, 3, 4), (3, 4, 5), (0, 1, 2)]
    assert wall_cut_edges(planar, tris) == frozenset({(1, 3), (2, 3), (2, 4)})


def test_a_self_touching_operand_never_costs_the_airport(law):
    """#1098 (EDDF): a held pad whose ring touches itself (a notch whose
    tip meets the shell) made ``plan_low``'s overlays raise ``side location
    conflict`` and the airport lost its whole patch.  Every operand is read
    as its valid area first (``geom/valid_area``); the split still lands."""
    from shapely.geometry import Polygon
    pad = Polygon([(0, 0), (200, 0), (200, 100), (0, 100), (0, 50),
                   (30, 40), (30, 60), (0, 50)])                  # touches itself at (0, 50)
    assert not pad.is_valid
    low = [_part(0.0, 0.0, 100.0, 80.0, -13.0), _part(100.0, 0.0, 200.0, 80.0, -12.9)]
    others = Polygon([(200, 0), (260, 0), (260, 40), (200, 20), (230, 20), (200, 40)])
    got = plan_low(pad, AIR, _airport(FRONT + low), law, 0.5, others)
    assert got is not None
    H, L, S, _rec = got
    assert H.is_valid and L.is_valid and S.is_valid
    assert L.area > 0.5 * 200.0 * 80.0


def test_valid_area_reads_the_area_and_drops_the_precision_model():
    import shapely
    from auto_patch_v2.geom.valid_area import valid_area
    from shapely.geometry import Polygon
    bow = Polygon([(0, 0), (10, 0), (10, 10), (5, 5), (8, 10), (0, 10), (0, 0)])
    pinch = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 5), (4, 4), (4, 6), (0, 5)])
    for g in (bow, pinch):
        v = valid_area(g)
        assert v.is_valid and v.geom_type in ("Polygon", "MultiPolygon")
        assert v.area > 0.0
    snapped = shapely.set_precision(box(0, 0, 3, 3), 0.5)
    assert shapely.get_precision(valid_area(snapped)) == 0.0
    ok = box(0, 0, 1, 1)
    assert valid_area(ok) is ok
    assert valid_area(None).is_empty


def test_the_lower_level_is_held_rigid_at_the_objects_lower_floor(monkeypatch, law):
    """#1141 (KATL east terminal): the lower level is a RIGID level tied
    to its block at the object's own lower floor, ``z = D + y_lo`` -- its
    own ground no longer chooses where in the storey it sits (it stood
    1.64 m over the floor and buried the roadway's towers)."""
    from auto_patch_v2.constraints import platform as CP
    from auto_patch_v2.model.registries import Registries
    monkeypatch.setattr(CP, "landing_vertices", lambda _p: {"b/p1": [1, 2, 3]})
    monkeypatch.setattr(CP, "datum_vertices", lambda _p, _l, **_k: {"b": 0})
    pm = types.SimpleNamespace(registries=Registries())
    pm.registries.landings["b/p1"] = {"kind": "low_level", "block": "b", "y_lo": -13.029,
                                      "y_hi": -3.0, "ground_z": 289.5}
    rows = CP.landing_rows(pm, law)
    assert len(rows) == 6                                   # two per vertex, no own-ground row
    for r in rows:
        (v, cv), (d, cd) = r.terms
        assert d == 0 and cv == -cd
        assert r.hi == pytest.approx(-13.029 * cv)          # z_v - D = y_lo, both ways


def _way(pts, **tags):
    return types.SimpleNamespace(points=tuple(pts), tags={"highway": "secondary", **tags})


def test_a_road_between_two_low_parts_is_on_the_lower_level(law):
    """#1291 (owner RULINGS 2026-10-24a): a 14 m road between two low parts
    stood on the block's level (a ridge over the lower level); it is on the
    lower level, and a road that runs on over the block carries the low
    level no further than one carriageway from it."""
    low = [_part(0.0, 0.0, 90.0, 80.0, -13.0), _part(110.0, 0.0, 200.0, 80.0, -13.0)]
    ap = _airport(FRONT + low)
    gap = box(92.0, 5.0, 108.0, 75.0)
    H0, L0, _S0, _r0 = plan_low(P, AIR, ap, law, 0.5)
    assert L0.intersection(gap).area < 0.1 * gap.area      # the ridge
    ap.osm_ways = (_way([(100.0, -10.0), (100.0, 80.0)], lanes="4"),
                   # a bore never lowers the ground it runs under
                   _way([(30.0, -10.0), (30.0, 99.0)], tunnel="yes"))
    H, L, _S, _r = plan_low(P, AIR, ap, law, 0.5)
    assert L.intersection(gap).area > 0.95 * gap.area
    assert L.distance(AIR) >= 3.0 - 1e-6                     # the frontage stays high
    assert H.area > 0.0
    # a road leaving the lower level north over the block: one carriageway
    ap.osm_ways = (_way([(150.0, 40.0), (150.0, 99.0)], lanes="2"),)
    _H, L2, _S2, _r2 = plan_low(P, AIR, ap, law, 0.5)
    assert L2.intersection(box(140.0, 80.0 + 7.0 + 3.5, 160.0, 100.0)).area < 1.0


def test_a_block_piece_the_lower_level_cuts_off_the_frontage_is_low(law):
    """#1291: a strip of the block between two low parts, fronting no
    airside, is the lower level; the frontage block stays high."""
    low = [_part(0.0, 0.0, 90.0, 80.0, -13.0), _part(110.0, 0.0, 200.0, 80.0, -13.0)]
    # the island between the low parts is cut off from the frontage by a
    # low part across its north end
    low.append(_part(85.0, 70.0, 115.0, 82.0, -13.0))
    H, L, _S, _r = plan_low(P, AIR, _airport(FRONT + low), law, 0.5)
    assert L.intersection(box(92.0, 5.0, 108.0, 65.0)).area > 0.95 * 16.0 * 60.0
    assert H.intersection(box(0.0, 95.0, 200.0, 100.0)).area > 0.9 * 200.0 * 5.0
