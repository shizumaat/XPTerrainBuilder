"""#2099 R2 / R3 (specs ``docs/specs/2099-R2-wing-cut.md``, ``docs/specs/
2099-R3.md`` Part D): a grouped mouth's wing walls are a ramp witness --
the ground on the road side of each wall line stands on its feet, the strip
behind it meets its top, and a deck mouth's ramp is planned on them.

* ``planar/wing_cut.wall_line_feet`` (D1, T5): wall lines per placement,
  feet per line, a coping-only station dropped;
* ``planar/wing_cut.wing_cuts`` (D2 / D3 / D5, T6): the region on the road
  side only, carved out of the ground it meets, never on pavement;
* ``model/wing_cut.wing_floor_y`` (D4): the foot along the facing line;
* ``constraints/wing_cut``: one held pair per vertex, hard and one-way;
* ``planar/deck_bridge.deck_pin`` and the structure pass (D6, T7).
"""
from __future__ import annotations

import dataclasses as _dc
import sys
import types
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_mouth_group2099 as MG  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402

LAW = Law.for_airport("")


def _walls_obj(path, walls):
    """One OBJ8 holding a cuboid wall per ``(x0, z0, x1, z1, foot0, foot1,
    top, thick)``: along authored (x, z) from ``(x0, z0)`` to ``(x1, z1)``,
    its bottom rising ``foot0`` -> ``foot1``, its top level."""
    vs, idx = [], []
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4), (1, 5, 7, 3), (2, 3, 7, 6), (0, 4, 5, 1)]
    for x0, z0, x1, z1, f0, f1, top, th in walls:
        L = ((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5
        nx, nz = -(z1 - z0) / L * th / 2.0, (x1 - x0) / L * th / 2.0
        b = len(vs)
        vs += [(x0 - nx, f0, z0 - nz), (x0 + nx, f0, z0 + nz), (x0 - nx, top, z0 - nz),
               (x0 + nx, top, z0 + nz), (x1 - nx, f1, z1 - nz), (x1 + nx, f1, z1 + nz),
               (x1 - nx, top, z1 - nz), (x1 + nx, top, z1 + nz)]
        idx += [b + i for a, c, d, e in q for i in (a, c, d, a, d, e)]
    vt = "".join(f"VT {x} {y} {z} 0 1 0 0 0\n" for x, y, z in vs)
    ix = "".join(f"IDX {i}\n" for i in idx)
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS {len(vs)} 0 0 {len(idx)}\n"
                    f"{vt}{ix}TRIS 0 {len(idx)}\n", encoding="utf-8", newline="\n")
    return str(path)


def test_two_splayed_walls_are_two_lines_and_a_coping_station_is_dropped(tmp_path):
    """T5: one placement, two walls splayed from the mouth; the second's
    bottom rises to its top (a coping) at its far end."""
    from auto_patch_v2.airport.wall_lines import wall_line_feet
    from shapely.geometry import box
    p = _walls_obj(tmp_path / "w.obj", [(5.0, 0.0, 15.0, 40.0, 0.0, 4.0, 7.2, 0.6),
                                        (-5.0, 0.0, -15.0, 40.0, 0.0, 7.0, 7.2, 0.6)])
    o = MG._placed("w", p, (0.0, 0.0))
    lines = wall_line_feet(o, MG._cache(), LAW, box(-10.0, 0.0, 10.0, 20.0))
    assert len(lines) == 2
    for _ln, st in lines:
        feet = [s[6] for s in st]
        assert feet[0] == pytest.approx(0.0, abs=0.5)          # from the end nearest the mouth
        assert feet[0] == feet[1]                              # R3b D1b: an end is no section
        assert all(b >= a - 1e-6 for a, b in zip(feet, feet[1:], strict=False))
    a, b = sorted(lines, key=lambda ln: ln[1][-1][6])
    assert a[1][-1][6] == pytest.approx(4.0, abs=0.35)
    assert max(s[7] - s[6] for s in b[1][-2:]) > float(LAW.tables.structures.tunnel.object
                                                       .plate_bin_m)   # the coping end dropped
    assert len(b[1]) < len(a[1])


def test_an_end_station_takes_its_neighbours_section():
    """T9 (R3b D1b): end sections 0.3 m thick with foot 5 over an interior
    1.4 m thick with foot 0: the end stations read 1.4 m and 0, their own
    tops standing."""
    from auto_patch_v2.airport.wall_lines import _ends_from_inside
    end = lambda y, top: (0.0, y, 1.0, 0.0, -0.15, 0.15, 5.0, top)      # noqa: E731
    mid = lambda y: (0.0, y, 1.0, 0.0, -0.7, 0.7, 0.0, 7.0)              # noqa: E731
    st = _ends_from_inside([end(0.0, 7.1), mid(2.0), mid(4.0), end(6.0, 7.3)])
    for s, top in ((st[0], 7.1), (st[-1], 7.3)):
        assert s[5] - s[4] == pytest.approx(1.4) and s[6] == 0.0 and s[7] == top
    assert _ends_from_inside([end(0.0, 7.1), end(2.0, 7.2)])[0][6] == 5.0   # too short: as read


def test_the_foot_is_read_along_the_facing_line_and_linear_across():
    from auto_patch_v2.model.wing_cut import WallLine, WingCut, wing_floor_y, wing_top_y
    east = WallLine("e", ((5.0, 0.0), (5.0, 10.0)), ((5.6, 0.0), (5.6, 10.0)), (0.0, 2.0),
                    (7.0, 7.0))
    west = WallLine("w", ((-5.0, 0.0), (-5.0, 10.0)), ((-5.6, 0.0), (-5.6, 10.0)), (0.0, 4.0),
                    (7.0, 8.0))
    one = WingCut("m", "wing_cut:m", (), (east,))
    assert wing_floor_y(one, (0.0, 5.0)) == pytest.approx(1.0)       # half way up the line
    both = WingCut("m", "wing_cut:m", (), (east, west))
    assert wing_floor_y(both, (0.0, 10.0)) == pytest.approx(3.0)     # 2 and 4, equidistant
    assert wing_floor_y(both, (2.5, 10.0)) == pytest.approx(2.5)     # nearer the east line
    assert wing_top_y(both, (-7.0, 10.0)) == pytest.approx(8.0)      # behind the west line
    assert wing_floor_y(WingCut("m", "r", ()), (0.0, 0.0)) == 0.0


def test_a_vertex_behind_its_face_reads_its_own_wall_within_reach():
    """T10 (R3b D4b): a vertex 0.2 m behind its wall's face, a second wall of
    foot 0 turned toward it 60 m away: it reads its own wall's foot.  The
    same second wall 30 m away, facing it across a road: linear across."""
    from auto_patch_v2.model.wing_cut import WallLine, WingCut, wing_floor_y
    own = WallLine("a", ((0.0, 0.0), (0.0, 10.0)), ((-0.6, 0.0), (-0.6, 10.0)), (2.0, 2.0),
                   (7.0, 7.0))

    def far(x):
        return WallLine("b", ((x, 0.0), (x, 10.0)), ((x + 0.6, 0.0), (x + 0.6, 10.0)),
                        (0.0, 0.0), (7.0, 7.0))
    xy = (-0.2, 5.0)
    assert wing_floor_y(WingCut("m", "r", (), (own, far(60.0)), reach=40.0), xy) == \
        pytest.approx(2.0)
    assert wing_floor_y(WingCut("m", "r", (), (own, far(30.0)), reach=40.0), xy) == \
        pytest.approx(2.0 * 30.2 / 30.4)


def _deck(oid="box"):
    from auto_patch_v2.model.structures import DeckBridge
    ring = ((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))
    return DeckBridge(oid, "box.obj", (oid,), ring,
                      ((-10.0, -10.0), (-10.0, 10.0)), ((10.0, 10.0), (10.0, -10.0)),
                      0.5, 0.5, -7.5, 170.0)


@_dc.dataclass(frozen=True)
class _Cl:
    cells: tuple


def test_the_region_is_the_road_side_carved_out_of_the_ground_and_off_pavement(tmp_path):
    """T6: a deck box over a road along y and a wall at x = 8 lining it 50 m
    south; a zone strip over the road side, an apron west of the road: the
    region lies on the road side only, is cut out of the strip, keeps clear of
    the apron, holds vertices on both long edges, and a back strip stands
    behind the wall."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.wing_cut import wing_cuts
    box = MG._cuboid(tmp_path / "box.obj", -10, 10, -7.5, 0.5, -10, 10, hard=True)
    wall = _walls_obj(tmp_path / "wall.obj", [(0.0, 0.0, 0.0, 50.0, 0.0, 4.0, 8.0, 0.6)])
    objs = [MG._placed("box", box, (0.0, 0.0)), MG._placed("w1", wall, (8.0, -10.2))]
    part = MG._partition([(o.id, o.path) for o in objs], [(0, 1)])
    airport = types.SimpleNamespace(partition=part, osm_ways=())

    def cell(i, role, ref, ring, side="groundside"):
        return Cell(i, role, ref, ring, (), None, None, side, "x", {})
    strip = cell(0, "graded_strip", "zone", ((-4.0, -70.0), (30.0, -70.0), (30.0, -12.0),
                                             (-4.0, -12.0)), "airside")    # ground, airside side
    apron = cell(1, "apron", "pav", ((-40.0, -70.0), (-6.0, -70.0), (-6.0, -12.0),
                                     (-40.0, -12.0)), "airside")
    tun = types.SimpleNamespace(deck_bridge="box", portal="", half_width_m=3.5, axis=())
    deck = _dc.replace(_deck(), road=((0.0, -300.0), (0.0, 300.0)))
    cl, cuts, notes = wing_cuts(airport, objs, MG._cache(), (deck,), (tun,),
                                _Cl((strip, apron)), LAW)
    assert len(cuts) == 1 and len(cuts[0].lines) == 1
    region = Polygon(cuts[0].region[0])
    assert region.contains(Point(0.0, -30.0))                      # the road side, across it
    assert not region.contains(Point(9.5, -30.0))                  # never behind the wall
    gap = float(LAW.tables.structures.tunnel.wall_gap_m)
    assert region.distance(Polygon(apron.ring)) >= gap - 1e-6      # off the pavement
    zone = [c for c in cl.cells if c.ref.startswith("zone")]
    assert zone and all(Polygon(c.ring).intersection(region).area < 0.3 for c in zone)
    minted = [c for c in cl.cells if c.ref.startswith("wing_cut:box")]
    assert minted and all(c.role == "graded_strip" for c in minted)
    xs = [x for x, _y in cuts[0].region[0]]
    face = sum(abs(x - 7.7) < 0.05 for x in xs)
    assert face >= 3 and sum(x < 0.0 for x in xs) >= 3            # both long edges
    assert cuts[0].back and any(c.ref.startswith("wing_back:box") for c in cl.cells)


def _planar(cut, faces, xy):
    vs = {v: types.SimpleNamespace(xy=p, incident_faces=tuple(
        fid for fid, f in faces.items() if v in f.ring)) for v, p in xy.items()}
    return types.SimpleNamespace(wing_cuts=(cut,), faces=faces, vertices=vs,
                                 ring_vertices=lambda ring: tuple(ring))


def test_the_rows_hold_ground_road_and_back_never_airside_or_floor():
    from auto_patch_v2.constraints import wing_cut as W
    from auto_patch_v2.model.constraints import Linear
    from auto_patch_v2.model.wing_cut import WallLine, WingCut
    line = WallLine("w", ((0.0, 0.0), (0.0, 20.0)), ((-0.6, 0.0), (-0.6, 20.0)), (1.0, 1.0),
                    (6.0, 6.0))
    cut = WingCut("p", "wing_cut:p", (((0, 0), (20, 0), (20, 20), (0, 20)),), (line,),
                  floor_z=100.0)
    F = types.SimpleNamespace
    faces = {1: F(role="graded_strip", ref="wing_cut:p", ring=(1, 2, 3), holes=()),
             2: F(role="service_road", ref="road", ring=(3, 4, 5), holes=()),
             3: F(role="apron", ref="pav", ring=(2, 6, 7), holes=()),
             4: F(role="tunnel_ramp", ref="tunnel_ramp", ring=(5, 8, 9), holes=()),
             5: F(role="graded_strip", ref="wing_back:p", ring=(10, 11, 12), holes=())}
    xy = {1: (1, 1), 2: (2, 2), 3: (3, 3), 4: (4, 4), 5: (5, 5), 6: (30, 30),
          7: (31, 31), 8: (6, 6), 9: (7, 7), 10: (-2, 5), 11: (-3, 6), 12: (-2, 7)}
    rows = W.wing_cut_rows(_planar(cut, faces, xy), LAW, None)
    held = {r.terms[0][0]: r.hi for r in rows if r.terms[0][1] > 0}
    assert sorted(held) == [1, 3, 4, 10, 11, 12]   # 2 the apron's, 5, 8, 9 the ramp floor's
    assert {held[v] for v in (1, 3, 4)} == {101.0} and {held[v] for v in (10, 11, 12)} == {106.0}
    assert all(isinstance(r, Linear) and r.source.generator == W.GEN for r in rows)
    head = W.RULING.split("(")[0].strip()          # hard, and one-way: it follows the deck
    assert head in LAW.tables.emit.design.hard_rulings
    assert head in LAW.tables.emit.design.one_way_rulings


def test_a_vertex_on_the_cut_and_the_back_is_held_at_the_top():
    """T11 (R3b D5b): a vertex a wing_cut face and a wing_back face of one
    cut both carry: one pair, at the wall's top."""
    from auto_patch_v2.constraints import wing_cut as W
    from auto_patch_v2.model.wing_cut import WallLine, WingCut
    line = WallLine("w", ((0.0, 0.0), (0.0, 20.0)), ((-0.6, 0.0), (-0.6, 20.0)), (1.0, 1.0),
                    (6.0, 6.0))
    cut = WingCut("p", "wing_cut:p", (((0, 0), (20, 0), (20, 20), (0, 20)),), (line,),
                  floor_z=100.0)
    F = types.SimpleNamespace
    faces = {1: F(role="graded_strip", ref="wing_cut:p", ring=(1, 2, 3), holes=()),
             2: F(role="graded_strip", ref="wing_back:p#1", ring=(3, 4, 5), holes=())}
    xy = {1: (1, 1), 2: (2, 2), 3: (-0.3, 3), 4: (-2, 4), 5: (-2, 6)}
    rows = W.wing_cut_rows(_planar(cut, faces, xy), LAW, None)
    mine = [r for r in rows if r.terms[0][0] == 3]
    assert len(mine) == 2
    assert {r.hi for r in mine if r.terms[0][1] > 0} == {106.0}


def test_a_held_vertex_sheds_its_dem_pin():
    from auto_patch_v2.constraints import edge_deck
    from auto_patch_v2.model.constraints import Linear, Pin, Source
    held = Linear(((7, 1.0),), None, 101.0, Source("wing_cut", "r", ()))
    dem = Pin(7, 104.0, Source("structures", "rim", ()))
    other = Pin(8, 104.0, Source("structures", "rim", ()))
    counts: dict = {}
    out = edge_deck.release_governed([held, dem, other], counts, gen="wing_cut")
    assert out == [held, other] and counts == {"wing_cut.released": 1}


# ── D6: a deck mouth's group walls plan its ramp (T7) ──────────────────

def _site(group_feet):
    """The #2072 deck (``test_deck_trench2072``) over a north-south road,
    no apron north of it: the structure pass's tunnels."""
    import tempfile

    import test_deck_trench2072 as T
    import test_m4b as M4B
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.model.airport import OsmWay
    from auto_patch_v2.planar.structures import build_structures
    db = _dc.replace(T._deck(), group_feet=tuple(group_feet))
    d = Path(tempfile.mkdtemp()) / "objects"
    d.mkdir()
    road = OsmWay(-1, "big_roads", ((0.0, -400.0), (0.0, 400.0)), False,
                  {"highway": "primary", "lanes": "2"})
    airport = M4B._airport({"dir": d}, T.LAW, [], (road,))
    _cl, tunnels, _st = build_structures(airport, Classification(tuple(T._cells()[:2]), (), {}, ()),
                                         T.LAW, deck_bridges=(db,))
    return T._north(tunnels), next(t for t in tunnels if t.axis[-1][1] < 0.0)


def _feet(grade):
    return [(x, y, grade * (y - 15.0)) for x in (-6.0, 6.0) for y in range(15, 77, 2)]


def test_group_walls_set_the_ramp_grade_on_their_side():
    """T7: walls with a 3.5 % foot north of the deck: the north ramp's grade
    is 3.5 %, the south one's the design grade; a 0.2 % foot is no witness."""
    from auto_patch_v2.planar.deck_bridge import group_reach
    tn = LAW.tables.structures.tunnel
    north, south = _site(_feet(0.035))
    assert north.design_grade == pytest.approx(0.035, abs=1e-3)
    assert south.design_grade == pytest.approx(tn.ramp_grade, abs=1e-6)
    flat_n, _s = _site(_feet(0.002))
    assert flat_n.design_grade == pytest.approx(tn.ramp_grade, abs=1e-6)
    import test_deck_trench2072 as T
    reach, g = group_reach(_dc.replace(T._deck(), group_feet=tuple(_feet(0.035))),
                            (0.0, 15.0), LAW)
    assert reach == pytest.approx(60.0, abs=0.5) and g == pytest.approx(0.035, abs=1e-6)
