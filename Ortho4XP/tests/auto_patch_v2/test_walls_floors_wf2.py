"""Spec 2120-WF2 (KATL #2120 combined round): the rules as general rules.

F1  a body of a frame read at its airside floor touches ground only on one
    of its two floors; one standing on the pack's own floors is CARRIED --
    no ground row (``constraints/foot_rows``).
F3  the frame's lower level is its own plan (no unwitnessed extension).
F5  no lower level under the frame's concourse.
W1  a wall terrace pairs a LOT vertex with the nearest pad on its own side:
    never a road vertex, never across a wall, never a strip / collar, never
    an upper pad.
W2  a foot on a retaining wall's fill takes no ground row (``wall_fill``).
W3  a retaining wall's footprint -- a deck block's cover too -- is no level.
"""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.geom import foot_planes as AF
from shapely.geometry import LineString, box

# ── F1: which feet touch ground ─────────────────────────────────────────

def test_a_foot_touches_ground_on_either_floor_or_under_the_lower():
    assert AF._on_floor(-15.0, -15.0) and AF._on_floor(-18.8, -15.0)     # a footing sinks
    assert AF._on_floor(0.4, -15.0)                                    # the apron
    assert not AF._on_floor(-11.0, -15.0) and not AF._on_floor(7.2, -15.0)


def test_a_body_on_neither_floor_is_carried():
    assert AF.carried_feet([-8.0, -7.6], -15.0)
    assert AF.carried_feet([10.6, 11.8], -15.0)
    assert not AF.carried_feet([-8.0, -15.0], -15.0)         # one foot on the floor
    assert not AF.carried_feet([-8.0], None)                 # no lower floor read
    assert not AF.carried_feet([], -15.0)


def test_the_foot_rows_read_a_carried_body_of_a_floor_zero_frame_only():
    from auto_patch_v2.constraints.foot_rows import _FrameFloors
    from auto_patch_v2.law import Law
    law = Law.for_airport("ZZZZ")
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    tall = float(law.tables.structures.placement.chain_min_height_m) + 1.0
    hall = types.SimpleNamespace(line=False, height_m=tall,
                                 feet=tuple((0.0, 0.1 * i, -15.0) for i in range(40)))
    mem = types.SimpleNamespace(parts=(hall,), floor_zero=True)
    plain = types.SimpleNamespace(parts=(hall,), floor_zero=False)
    a = types.SimpleNamespace(partition=types.SimpleNamespace(
        units=[types.SimpleNamespace(members=[mem, plain])]))
    ff = _FrameFloors(a, law)
    feet = (types.SimpleNamespace(y=-8.0), types.SimpleNamespace(y=-7.5))
    assert AF.frame_floor(a.partition.units[0], step, tall - 1.0) == pytest.approx(-15.0)
    assert -15.0 <= -step
    assert ff.carried(types.SimpleNamespace(senior=(0, 0, 0), feet=feet))
    assert not ff.carried(types.SimpleNamespace(senior=(0, 1, 0), feet=feet))
    on = (types.SimpleNamespace(y=-15.0),)
    assert not ff.carried(types.SimpleNamespace(senior=(0, 0, 0), feet=on))


# ── W1: the lot's own building ──────────────────────────────────────────

def _pm(verts, faces):
    """A stub planar map: ``verts`` {id: (xy, incident faces)}, ``faces``
    {id: (ref, role, ring)}."""
    V = {v: types.SimpleNamespace(xy=xy, incident_faces=inc) for v, (xy, inc) in verts.items()}
    F = {f: types.SimpleNamespace(ref=ref, role=role, ring=ring, road_by_proportions=False)
         for f, (ref, role, ring) in faces.items()}
    return types.SimpleNamespace(vertices=V, faces=F, ring_vertices=lambda r: list(r))


def _wall(poly, upper=None, lower=None):
    from auto_patch_v2.airport.road_ramp import WallPiece
    return WallPiece(poly, 5.0, "w.obj#comp0", True, upper_face=upper, lower_face=lower)


def test_a_road_vertex_never_pairs():
    from auto_patch_v2.airport import road_ramp as RR
    pm = _pm({1: ((0.0, 0.0), (10,)), 2: ((5.0, 0.0), (11,))},
             {10: ("small_roads:-1", "service_road", (1,)), 11: ("lot", "parking", (2,))})
    assert RR._on_road(pm, 1, frozenset({"service_road"}))
    assert not RR._on_road(pm, 2, frozenset({"service_road"}))


def test_the_lot_pairs_its_own_side_never_a_collar_an_upper_pad_or_across_a_wall():
    from auto_patch_v2.airport import road_ramp as RR
    wall = box(10.0, -50.0, 12.0, 50.0)                      # the lot west, pads east
    w = _wall(wall, upper=LineString([(12.0, -50), (12.0, 50)]),
              lower=LineString([(10.0, -50), (10.0, 50)]))
    verts = {1: ((0.0, 0.0), ()),
             2: ((-5.0, 0.0), ()), 3: ((-5.0, 8.0), ()),        # collar, west
             4: ((-20.0, 0.0), ()), 5: ((-20.0, 8.0), ()),      # the lot's building, west
             6: ((20.0, 0.0), ()), 7: ((20.0, 8.0), ())}        # across the wall, east
    faces = {20: ("b1/landing0#collar", "building", (2, 3)),
             21: ("b2", "building", (4, 5)),
             22: ("b3", "building", (6, 7))}
    pm = _pm(verts, faces)
    pad_f = {20: box(-6, 0, -5, 8), 21: box(-21, 0, -20, 8), 22: box(20, 0, 21, 8)}
    tree_polys = [wall]
    from shapely.strtree import STRtree
    tree = STRtree(tree_polys)
    # nearest first: the collar, the pad across the wall, then the lot's own
    got = RR._same_side_pad(pm, 1, [20, 22, 21], pad_f, w, tree, tree_polys)
    assert got == 4
    # across the wall only (no faces read): refused, never paired
    w0 = _wall(wall)
    assert RR._same_side_pad(pm, 1, [22], pad_f, w0, tree, tree_polys) is None
    # an UPPER pad on the lot's side of the line still is the wall's upper one
    up = _wall(wall, upper=LineString([(-21.0, -50), (-21.0, 50)]),
               lower=LineString([(10.0, -50), (10.0, 50)]))
    assert RR._same_side_pad(pm, 1, [21], pad_f, up, tree, tree_polys) is None


# ── F3 / F5 / W3: the frame's lower level ───────────────────────────────

@pytest.fixture(scope="module")
def law():
    from auto_patch_v2.law import Law
    return Law.for_airport("ZZZZ")


def _split(law, tmp_path, monkeypatch, extra=(), shade=None, halls=((0.0, 200.0),),
           beyond=()):
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.planar import low_level as LL
    from auto_patch_v2.planar import pad_blocks
    from auto_patch_v2.planar.low_extent import AirRegion
    from auto_patch_v2.planar.overlay import Region
    from test_two_pads1214 import _airport
    from test_two_pads1214 import _wall as _part
    monkeypatch.setattr(pad_blocks, "unit_base", lambda P, a: ("flat", "u"))
    air = box(0.0, 100.0, 200.0, 130.0)
    blk = box(0.0, 80.0, 200.0, 100.0)
    conc = [_part(10.0 + 20.0 * i, 99.5, 25.0 + 20.0 * i, 100.0, 0.0, 30) for i in range(8)]
    hall = [_part(x0, 0.0, x1, 60.0, -15.0, 300) for x0, x1 in halls]
    A = _airport(conc + hall + [_part(*e) for e in extra], tmp_path)
    A.partition.units[0].members[0].floor_zero = True
    A.wall_shade = shade
    reg = Registries()
    reg.held["blk"] = {"unit": "blk"}
    regions = [Region(role="building", ref="blk", polygon=blk, code_number=None,
                      code_letter=None, side="airside", source="cell")]
    out = LL.low_level_split(regions, [air], A, law, 0.5, {}, reg=reg,
                             air_all=[AirRegion(air, "cell")], beyond=beyond)
    ext = [r for r in out if reg.landings.get(str(r.ref), {}).get("extent_of")]
    return ext, reg


def test_the_frame_level_is_its_own_plan(law, tmp_path, monkeypatch):
    """F3: unreachable pavement beside the hall (``beyond``) is no part of
    a seeded frame's level -- the level is the frame's own plan."""
    far = box(0.0, -60.0, 200.0, -2.0)
    ext, _reg = _split(law, tmp_path, monkeypatch, beyond=(far,))
    assert ext
    assert all(r.polygon.intersection(far).area < 1.0 for r in ext)


def test_no_level_under_the_concourse(law, tmp_path, monkeypatch):
    """F5: the hall in two halves 4 m apart -- the frontage closes the gap
    into one level -- with a concourse part on the apron floor (feet at
    its zero) over the gap: no level under it."""
    halls = ((0.0, 98.0), (102.0, 200.0))
    gap = box(98.5, 5.0, 101.5, 55.0)
    ext, _r = _split(law, tmp_path, monkeypatch, halls=halls)
    assert sum(r.polygon.intersection(gap).area for r in ext) > 0.9 * gap.area
    ext, _r = _split(law, tmp_path, monkeypatch, halls=halls,
                     extra=[(98.0, 0.0, 102.0, 60.0, 0.0, 20)])
    assert ext and sum(r.polygon.intersection(gap).area for r in ext) < 1.0


def test_a_retaining_wall_is_never_a_level(law, tmp_path, monkeypatch):
    """W3: a wall's footprint (a deck block's cover too) keeps every piece
    off, as it keeps every pad."""
    cover = box(150.0, 0.0, 200.0, 60.0)
    ext, _r = _split(law, tmp_path, monkeypatch, shade=cover)
    assert ext and all(r.polygon.intersection(cover).area < 1.0 for r in ext)


# ── W2: a foot on a wall's fill ─────────────────────────────────────────

def test_a_foot_on_a_walls_fill_takes_no_ground_row(law):
    """The cut twin's colonnade (``test_v2cutfeet``) on a face that is a
    retaining wall's FILL (``model/wall_reach.WALL_FILL_MARK``): verdict
    ``wall_fill``, no row -- the fill is held by the wall's own law."""
    import dataclasses as dc

    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.constraints import foot_rows as FR
    from auto_patch_v2.model.wall_reach import WALL_FILL_MARK, WALL_SLOPE_REF_PREFIX
    from auto_patch_v2.planar.build import build
    from tests.auto_patch_v2.test_v2canopy6 import _FEET_X, _with_groups
    from tests.auto_patch_v2.test_v2cutfeet import _cells, _colonnade
    from tests.auto_patch_v2.test_v2grounddem import _LawfulDem
    from tests.auto_patch_v2.test_v2smooth import _airport
    airport, r = _airport(law, _LawfulDem(), ())
    airport = _with_groups(airport, [_colonnade("onfill", airport, r, _FEET_X)])
    pm, _st = build(airport, Classification(_cells(r, ramp_role="graded_strip"), (), {}, ()),
                    law)
    ref = f"{WALL_SLOPE_REF_PREFIX}w.obj{WALL_FILL_MARK}0"
    for fid, f in list(pm.faces.items()):
        if str(f.ref) == "rampA":
            pm.faces[fid] = dc.replace(f, ref=ref)
    rows, verdicts, counts = FR.foot_targets(pm, law, airport)
    assert counts["wall_fill"] == 1 and counts["rows"] == 0, counts
    assert [v.verdict for v in verdicts if v.gid == "onfill"] == ["wall_fill"]
