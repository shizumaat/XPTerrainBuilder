"""#2099 R3 Part E twin (spec ``docs/specs/2099-R3.md`` §3, §7 T4): a wall
LINING the mouth's road joins its group (``airport/mouth_group._lining``)
-- within the separation of the mouth (E1), lining its road on one side (E2),
standing at the mouth's seat (E3); one hop, never through a lining wall."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_mouth_group2099 as MG  # noqa: E402
from auto_patch_v2.airport import mouth_group as M  # noqa: E402
from shapely.geometry import box as _box  # noqa: E402

LAW = MG.LAW
ROAD = ((0.0, -300.0), (0.0, 300.0))         # the road through the box, along y


def _placed(oid, path, xy, plan):
    o = MG._placed(oid, path, xy)
    o.plan_bbox = plan
    return o


def _groups(tmp_path, walls):
    """The box (deck top 0.5, floor -7.5: 8.0 over its floor) and ``walls``
    = ``[(id, OBJ path, anchor, plan box)]``; no piece touches the box."""
    bx = MG._cuboid(tmp_path / "box.obj", -10, 10, -7.5, 0.5, -10, 10, hard=True)
    objs = [_placed("box", bx, (0.0, 0.0), _box(-10, -10, 10, 10)),
            *(_placed(*w) for w in walls)]
    part = MG._partition([(o.id, o.path) for o in objs], [])
    cache = MG._cache()
    return M.mouth_groups(part, objs, [M.Mouth("box", -7.5, "test", road=ROAD)], cache, LAW)


def test_a_wall_lining_the_road_19_m_out_at_the_decks_top_joins(tmp_path):
    wall = MG._cuboid(tmp_path / "wall.obj", -0.3, 0.3, 0.0, 8.0, 0.0, 48.0)
    groups, notes = _groups(tmp_path, [("w", wall, (19.0, -12.0), _box(18.7, -60.0, 19.3, -12.0))])
    assert [(g.mouth.object_id, [w for w, _r in g.wings]) for g in groups] == [("box", ["w"])]
    assert any("lines mouth box's road" in n for n in notes)


def test_the_same_wall_a_coping_high_is_refused(tmp_path):
    low = MG._cuboid(tmp_path / "low.obj", -0.3, 0.3, 0.0, 0.6, 0.0, 48.0)
    groups, notes = _groups(tmp_path, [("w", low, (19.0, -12.0), _box(18.7, -60.0, 19.3, -12.0))])
    assert groups == [] and any("w " in n and "no lining wall" in n for n in notes)


def test_a_wall_on_both_sides_of_the_road_is_refused(tmp_path):
    """One placement standing a wall either side of the road (E2)."""
    path = tmp_path / "pair.obj"
    _two_walls(path)
    groups, notes = _groups(tmp_path, [("w", str(path), (0.0, -12.0),
                                        _box(-19.3, -60.0, 19.3, -12.0))])
    assert groups == [] and any("both sides" in n for n in notes)


def test_a_wall_reached_only_through_a_lining_wall_stays_out(tmp_path):
    wall = MG._cuboid(tmp_path / "wall.obj", -0.3, 0.3, 0.0, 8.0, 0.0, 48.0)
    far = MG._cuboid(tmp_path / "far.obj", -6.0, 6.0, 0.0, 8.0, -0.3, 0.3)
    groups, _n = _groups(tmp_path, [("w", wall, (19.0, -12.0), _box(18.7, -60.0, 19.3, -12.0)),
                                    ("x", far, (25.3, -55.0), _box(19.3, -55.3, 31.3, -54.7))])
    assert [w for w, _r in groups[0].wings] == ["w"]


def _two_walls(path):
    """Two wall cuboids at x = -19 and +19 along z 0..48, one OBJ."""
    vs, idx = [], []
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for cx in (-19.0, 19.0):
        base = len(vs)
        vs += [(x, y, z) for x in (cx - 0.3, cx + 0.3) for y in (0.0, 8.0) for z in (0.0, 48.0)]
        idx += [base + i for a, b, c, d in q for i in (a, b, c, a, c, d)]
    vt = "".join(f"VT {x} {y} {z} 0 1 0 0 0\n" for x, y, z in vs)
    ix = "".join(f"IDX {i}\n" for i in idx)
    path.write_text(f"I\n800\nOBJ\n\nTEXTURE x.png\nPOINT_COUNTS {len(vs)} 0 0 {len(idx)}\n"
                    f"{vt}{ix}TRIS 0 {len(idx)}\n", encoding="utf-8", newline="\n")
