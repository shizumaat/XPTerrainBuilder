"""#2090 amendment C: the ground at an AGP follower's ground floor — its
plates (``airport/agp_plates``), their pieces (``planar/agp_ground``) and
rows (``constraints/agp_plate``), the bank's toe (``constraints/
fill_bank``), no ground datum on a plate (``solve/design_ground``), a road
on a bank is no mouth (``airport/road_ramp``) and the road under a joined
deck keeps its floor (C3c)."""
from __future__ import annotations

import types

import pytest
import shapely
from auto_patch_v2.law import Law
from auto_patch_v2.model.agp_group import AgpGroup, AgpMember, AgpPlate

LAW = Law.for_airport("")
GID = "agp:dsf:obj1"
L = 1629.82
RING = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))


def _group(built=True):
    gov = AgpMember("dsf:obj2", 2, "A.agp", (500.0, 0.0), (0.0, 0.0), 0.0, 0.0)
    fol = AgpMember("dsf:obj1", 1, "J.agp", (50.0, 50.0), (0.0, 0.0), 400.0, -9.0)
    plate = AgpPlate(GID, "dsf:obj1", 0, RING, (), 0.15, L, 10000.0, 2.0, built)
    return AgpGroup(GID, (fol, gov), (), "dsf:obj2", 1638.71, "", frozenset({"dsf:obj2"}),
                    plates=(plate,))


def _pm(verts, faces, edges=(), groups=None, stacks=()):
    """``verts`` ``{v: (xy, dem, (face ids))}``, ``faces`` ``{f: (role, ref, ring)}``."""
    vs = {v: types.SimpleNamespace(xy=xy, dem_z=dz, incident_faces=tuple(fs))
          for v, (xy, dz, fs) in verts.items()}
    fs = {f: types.SimpleNamespace(id=f, role=r, ref=ref, ring=tuple(ring), holes=())
          for f, (r, ref, ring) in faces.items()}
    es = {k: types.SimpleNamespace(a=a, b=b, left_face=lf, right_face=rf)
          for k, (a, b, lf, rf) in enumerate(edges)}
    return types.SimpleNamespace(vertices=vs, faces=fs, edges=es,
                                 agp_groups=(groups or (_group(),)), bridge_stacks=stacks,
                                 ring_vertices=lambda ring: list(ring))


def _rows_by_v(rows):
    return {r.v: r for r in rows}


def test_p1_p2_p3_bands():
    from auto_patch_v2.constraints.agp_plate import LOT_GRADE, agp_plate_rows
    vis = float(LAW.tables.emit.cockpit.visual_m)
    flush = float(LAW.tables.structures.bridge.deck_flush_m)
    pm = _pm({1: ((50.0, 50.0), 1627.8, (10,)),        # plate ground
              2: ((60.0, 50.0), 1627.8, (11,)),        # a road inside
              3: ((120.0, 50.0), 1627.5, (12,)),       # a lot 20 m out
              4: ((400.0, 50.0), 1627.5, (12,))},      # a lot out of reach
             {10: ("graded_strip", f"agp_ground:{GID}:dsf:obj1:plate#0", (1,)),
              11: ("service_road", "small_roads:-7", (2,)),
              12: ("parking_lot", "lot:1", (3, 4))})
    ap = types.SimpleNamespace(agp_groups=(_group(),), deck_stacks=(), osm_ways=())
    b = _rows_by_v(agp_plate_rows(pm, LAW, ap))
    assert (b[1].lo, b[1].hi) == pytest.approx((L - 0.5 * vis, L))
    assert (b[2].lo, b[2].hi) == pytest.approx((L - flush, L))
    assert (b[3].lo, b[3].hi) == pytest.approx((L - 0.5 * vis - LOT_GRADE * 20.0,
                                                L + LOT_GRADE * 20.0))
    assert 4 not in b
    assert all(GID in r.source.inputs for r in b.values())     # the datum moves them


def test_an_under_deck_road_vertex_keeps_its_floor():
    """C3c: a road vertex under a joined or riding deck's ring takes no P
    row and seeds no plate ramp (owner Q1 (a))."""
    from auto_patch_v2.constraints.agp_plate import agp_plate_rows
    from auto_patch_v2.model.agp_plate import plate_road_levels
    from auto_patch_v2.model.deck_stack import KEPT
    deck = types.SimpleNamespace(ring=((55.0, 40.0), (70.0, 40.0), (70.0, 60.0), (55.0, 60.0)))
    st = types.SimpleNamespace(kind=KEPT, datum_group=GID, decks=(deck,))
    pm = _pm({2: ((60.0, 50.0), 1627.8, (11,)), 5: ((80.0, 50.0), 1627.8, (11,))},
             {11: ("service_road", "small_roads:-7", (2, 5))}, stacks=(st,))
    ap = types.SimpleNamespace(agp_groups=(_group(),), deck_stacks=(st,), osm_ways=())
    assert set(plate_road_levels(pm, LAW, ap)) == {5}
    assert set(_rows_by_v(agp_plate_rows(pm, LAW, ap))) == {5}


def test_the_bank_toe_is_pinned_on_the_dem():
    from auto_patch_v2.constraints.fill_bank import AGP_RULING, fill_toe_pins
    pm = _pm({1: ((100.0, 50.0), 1628.0, (20,)), 2: ((106.0, 50.0), 1627.1, (20,)),
              3: ((106.0, 60.0), 1627.2, (20,))},
             {20: ("graded_strip", f"agp_ground:{GID}:dsf:obj1:bank#0", (1, 2, 3))},
             edges=((1, 2, 20, None), (2, 3, 20, None)))
    ap = types.SimpleNamespace(agp_groups=(_group(),), deck_stacks=())
    pins = {p.v: p for p in fill_toe_pins(pm, LAW, ap) if p.source.ruling == AGP_RULING}
    assert set(pins) == {2, 3} and pins[2].z == pytest.approx(1627.1)  # plate edge: no toe


def test_a_plate_on_a_pad_is_not_built():
    from auto_patch_v2.planar.agp_ground import agp_ground_pieces
    dem = types.SimpleNamespace(z_many=lambda xs, ys: [1627.8] * len(xs))
    ap = types.SimpleNamespace(agp_groups=(_group(),), dem=dem)
    pad = shapely.Polygon(RING).buffer(1.0)
    notes: list = []
    got = agp_ground_pieces(ap, [], [pad], 1.0, 0.5, 20.0, law=LAW, pads=[("building22", pad)],
                            notes=notes)
    assert not [r for r, _g in got if ":plate#" in r]
    assert any(n.startswith("agp_plate_on_pad") for n in notes)
    free = agp_ground_pieces(ap, [], [], 1.0, 0.5, 20.0, law=LAW)
    assert [r for r, _g in free if ":plate#" in r] and [r for r, _g in free if ":bank#" in r]


def test_a_plate_vertex_carries_no_ground_datum():
    from auto_patch_v2.solve.design_ground import _agp_plate_vertices
    pm = _pm({1: ((50.0, 50.0), 1627.8, (10,)), 2: ((104.0, 50.0), 1627.5, (20,))},
             {10: ("graded_strip", f"agp_ground:{GID}:dsf:obj1:plate#0", (1,)),
              20: ("graded_strip", f"agp_ground:{GID}:dsf:obj1:bank#0", (2,))})
    assert _agp_plate_vertices(pm) == {1}


def test_a_road_vertex_on_a_bank_is_no_mouth():
    from auto_patch_v2.airport.road_ramp import _only_agp_ground
    pm = types.SimpleNamespace(
        vertices={1: types.SimpleNamespace(incident_faces=(20, 11)),
                  2: types.SimpleNamespace(incident_faces=(30, 11))},
        faces={20: types.SimpleNamespace(role="graded_strip",
                                         ref=f"agp_ground:{GID}:dsf:obj1:bank#0"),
               30: types.SimpleNamespace(role="graded_strip", ref="zone2:taxi:F"),
               11: types.SimpleNamespace(role="service_road", ref="small_roads:-7")})
    assert _only_agp_ground(pm, LAW, 1) and not _only_agp_ground(pm, LAW, 2)


def test_plates_are_the_followers_ground_floors(tmp_path):
    """C1: one connected part of a follower's ground floors is one plate at
    ``zero_pred + y - deck_flush_m``; a small part is listed, not built."""
    import numpy as np
    from auto_patch_v2.airport.agp_plates import _member_plates
    flush = float(LAW.tables.structures.bridge.deck_flush_m)
    big = [[(0, 0, 0.15), (60, 0, 0.15), (60, 60, 0.15)], [(0, 0, 0.15), (60, 60, 0.15),
                                                          (0, 60, 0.15)]]
    small = [[(200, 0, 0.15), (205, 0, 0.15), (205, 5, 0.15)]]
    tris = np.array(big + small, float)
    dem = types.SimpleNamespace(z_many=lambda xs, ys: np.full(len(xs), 1628.0))
    got = _member_plates(_group(), "dsf:obj1", tris, dem, LAW.tables.structures.agp, flush)
    built = [p for p in got if p.built]
    assert len(built) == 1 and built[0].level == pytest.approx(1638.71 - 9.0 + 0.15 - flush)
    assert built[0].area_m2 == pytest.approx(3600.0)
    assert [p.why.split(":")[0] for p in got if not p.built] == ["agp_plate_small"]
