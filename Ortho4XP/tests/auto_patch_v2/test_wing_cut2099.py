"""#2099 R2 (spec ``docs/specs/2099-R2-wing-cut.md``): a grouped mouth's
wing walls are a ramp witness -- the ground beside and between them stands
on their foot line.

* ``model/wing_cut.wing_floor_y``: the wings' feet, inverse-square weighted;
* ``planar/wing_cut``: the feet off a wall's solids (an exact cross-section),
  the region across the opening, the free ground minted as cells;
* ``constraints/wing_cut``: one held pair per vertex inside the region, hard and
  one-way (it follows the deck), airside and ramp floors never held; ``edge_deck.release_governed`` sheds the DEM pins of a held
  vertex.
"""
from __future__ import annotations

import dataclasses as _dc
import types

import pytest
from shapely.geometry import Point, Polygon

from auto_patch_v2.law import Law

LAW = Law.for_airport("")


def _wall(path, length, foot0, foot1, top, thick=0.6):
    """An OBJ8 wall along +z from 0 to ``length``: its bottom rises from
    ``foot0`` to ``foot1``, its top level at ``top`` (12 solid triangles)."""
    h = thick / 2.0
    vs = [(-h, foot0, 0.0), (h, foot0, 0.0), (-h, top, 0.0), (h, top, 0.0),
          (-h, foot1, length), (h, foot1, length), (-h, top, length), (h, top, length)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4), (1, 5, 7, 3), (2, 3, 7, 6), (0, 4, 5, 1)]
    idx = [i for a, b, c, d in quads for i in (a, b, c, a, c, d)]
    vt = "".join(f"VT {x} {y} {z} 0 1 0 0 0\n" for x, y, z in vs)
    ix = "".join(f"IDX {i}\n" for i in idx)
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS {len(vs)} 0 0 {len(idx)}\n"
                    f"{vt}{ix}TRIS 0 {len(idx)}\n", encoding="utf-8", newline="\n")
    return str(path)


def _cache():
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    return ResourceCache(LAW.tables.structures.basin.min_solid_thickness_m, _fe.quantum(LAW))


def _placed(oid, path, xy, hdg=0.0):
    return types.SimpleNamespace(id=oid, path=path, resolved=path, xy=xy, heading_deg=hdg)


def test_the_floor_under_a_point_is_the_wings_feet_weighted():
    from auto_patch_v2.model.wing_cut import WingCut, wing_floor_y
    cut = WingCut("m", "wing_cut:m", (), ((0.0, 0.0, 0.0, "a"), (0.0, 10.0, 2.0, "a"),
                                           (10.0, 0.0, 4.0, "b")))
    assert wing_floor_y(cut, (0.0, 9.9)) == pytest.approx(2.0, abs=0.02)   # a's sample
    mid = wing_floor_y(cut, (5.0, 0.0))                  # a's foot 0 and b's 4, equidistant
    assert mid == pytest.approx(2.0)
    assert wing_floor_y(WingCut("m", "r", (), ()), (0.0, 0.0)) == 0.0


def test_the_road_runs_along_the_end_lines():
    from auto_patch_v2.planar.wing_cut import _end_line_dir
    db = types.SimpleNamespace(seats_a=((0.0, 0.0), (0.0, 10.0)),
                               seats_b=((20.0, 10.0), (20.0, 0.0)))
    assert _end_line_dir(db) == pytest.approx((0.0, 1.0))
    assert _end_line_dir(types.SimpleNamespace(seats_a=((0.0, 0.0),), seats_b=())) is None


def test_a_wing_lining_one_side_cuts_across_the_whole_opening():
    from auto_patch_v2.planar.wing_cut import _ribbon
    feet = [(6.0, y, 0.0) for y in (0.0, 10.0, 20.0)]      # the wall at u = +6
    rib = _ribbon(feet, (0.0, 0.0), (0.0, 1.0), 8.0)       # axis along +y, half 8
    # the axis is along +y, so u is -x: the wall stands at u = -6, the far edge at +8
    xs = sorted({round(x, 6) for x, _y in rib.exterior.coords})
    assert xs == [-8.0, 6.0]
    assert rib.area == pytest.approx(14.0 * 20.0)


def _deck(oid="box"):
    from auto_patch_v2.model.structures import DeckBridge
    ring = ((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))
    return DeckBridge(oid, "box.obj", (oid,), ring,
                      ((-10.0, -10.0), (-10.0, 10.0)), ((10.0, 10.0), (10.0, -10.0)),
                      0.5, 0.5, -7.5, 170.0)


@_dc.dataclass(frozen=True)
class _Cl:
    cells: tuple


def test_wing_cuts_read_the_foot_and_mint_only_free_ground(tmp_path):
    """A deck box over a road along +y (end lines on x = -10 / +10) and a wing
    wall at x = 8 running 40 m out of it to y = -50, its foot rising 0 -> 4 m:
    the feet rise with it, the region spans the opening beside it, and a
    road cell already standing there keeps its ground."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.wing_cut import wing_cuts
    wall = _wall(tmp_path / "wall.obj", 40.0, 0.0, 4.0, 7.2)
    # heading 0: the wall's +z runs to -y
    objs = [_placed("box", str(tmp_path / "box.obj"), (0.0, 0.0)),
            _placed("w1", wall, (8.0, -10.2))]
    part = types.SimpleNamespace(
        units=tuple(types.SimpleNamespace(members=(types.SimpleNamespace(
            id=o.id, resource=o.path, parts=(types.SimpleNamespace(pid=i, line=False),)),))
            for i, o in enumerate(objs)),
        member_object={(i, 0): (o.id, o.path) for i, o in enumerate(objs)}, contacts=((0, 1),))
    box = tmp_path / "box.obj"
    from tests.auto_patch_v2.test_mouth_group2099 import _cuboid   # the group's own fixture
    _cuboid(box, -10, 10, -7.5, 0.5, -10, 10, hard=True)
    airport = types.SimpleNamespace(partition=part)
    road = Cell(0, "service_road", "road", ((-3.0, -60.0), (3.0, -60.0), (3.0, -11.0),
                                            (-3.0, -11.0)), (), None, None, "groundside",
                "road", {})
    cl, cuts, notes = wing_cuts(airport, objs, _cache(), (_deck(),), (), _Cl((road,)), LAW)
    assert len(cuts) == 1 and cuts[0].mouth == "box" and cuts[0].floor_y == -7.5
    feet = sorted(cuts[0].feet, key=lambda f: -f[1])
    assert feet[0][2] == pytest.approx(0.0, abs=0.3) and feet[-1][2] == pytest.approx(4.0, abs=0.3)
    assert all(abs(x - 7.7) < 0.05 for x, _y, _f, _w in feet)   # the face toward the axis
    region = Polygon(cuts[0].region[0])
    assert region.contains(Point(0.0, -30.0)) and region.contains(Point(-9.0, -30.0))
    assert not region.contains(Point(0.0, -5.0))                 # the deck keeps its ground
    minted = [c for c in cl.cells if c.ref.startswith("wing_cut:box")]
    assert minted and all(c.role == "graded_strip" for c in minted)
    assert all(Polygon(c.ring).intersection(Polygon(road.ring)).area < 1e-6 for c in minted)
    assert any("wing cut over 1 wing(s)" in n for n in notes)


def _planar(cut, faces, xy):
    vs = {v: types.SimpleNamespace(xy=p, incident_faces=tuple(
        fid for fid, f in faces.items() if v in f.ring)) for v, p in xy.items()}
    return types.SimpleNamespace(wing_cuts=(cut,), faces=faces, vertices=vs,
                                 ring_vertices=lambda ring: tuple(ring))


def test_the_rows_hold_ground_and_road_never_airside_or_floor():
    from auto_patch_v2.constraints import wing_cut as W
    from auto_patch_v2.model.constraints import Linear
    from auto_patch_v2.model.wing_cut import WingCut
    cut = WingCut("p", "wing_cut:p", (((0, 0), (20, 0), (20, 20), (0, 20)),),
                  ((0.0, 0.0, 1.0, "w"),), floor_z=100.0)
    F = types.SimpleNamespace
    faces = {1: F(role="graded_strip", ref="wing_cut:p", ring=(1, 2, 3), holes=()),
             2: F(role="service_road", ref="road", ring=(3, 4, 5), holes=()),
             3: F(role="apron", ref="pav", ring=(2, 6, 7), holes=()),
             4: F(role="tunnel_ramp", ref="tunnel_ramp", ring=(5, 8, 9), holes=())}
    xy = {1: (1, 1), 2: (2, 2), 3: (3, 3), 4: (4, 4), 5: (5, 5), 6: (30, 30),
          7: (31, 31), 8: (6, 6), 9: (7, 7)}
    rows = W.wing_cut_rows(_planar(cut, faces, xy), LAW, None)
    held = sorted({r.terms[0][0] for r in rows if r.terms[0][1] > 0})
    assert held == [1, 3, 4]             # 2 is the apron's, 5, 8, 9 the ramp floor's
    assert all(isinstance(r, Linear) and r.source.generator == W.GEN for r in rows)
    assert {r.hi for r in rows if r.terms[0][1] > 0} == {101.0}
    assert all(r.follows == r.terms[0][0] or r.follows in dict(r.terms) for r in rows)
    head = W.RULING.split("(")[0].strip()          # hard, and one-way: it follows the deck
    assert head in LAW.tables.emit.design.hard_rulings
    assert head in LAW.tables.emit.design.one_way_rulings


def test_a_held_vertex_sheds_its_dem_pin():
    from auto_patch_v2.constraints import edge_deck
    from auto_patch_v2.model.constraints import Linear, Pin, Source
    held = Linear(((7, 1.0),), None, 101.0, Source("wing_cut", "r", ()))
    dem = Pin(7, 104.0, Source("structures", "rim", ()))
    other = Pin(8, 104.0, Source("structures", "rim", ()))
    counts: dict = {}
    out = edge_deck.release_governed([held, dem, other], counts, gen="wing_cut")
    assert out == [held, other] and counts == {"wing_cut.released": 1}
