"""#1918, owner RULINGS 2026-11-06d (6): "trench depth should be based on other
objects like bridges and structures that extend below the surrounding grade".
A HIDDEN cut shell stays out of the solve; its VISIBLE frame members lying on
the cut state the depth, the floor's edge and the bank; a deck over the cut
and a buried foundation state nothing (``airport/visible_cut``).  Along a
channel the members' feet are a floor PROFILE and its edge, their plan the
crest, and the axis runs on along its way's continuation while the members do
(``planar/channel_depth``)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from auto_patch_v2.airport import visible_cut as VC
from auto_patch_v2.planar import channel_depth as CD
from shapely.geometry import LineString
from test_cut_shell1883 import _section, _shell
from test_hanging_objects1298 import LAW, THICK, _box, _placed, _write


def _frame(tmp_path):
    """A hidden shell (rim at the ground 100, floor 92) and its members: a
    bank LINER 0.8 m over the right bank, a pier standing on the floor, a
    deck plate 4 m over it and a foundation buried 3 m under it."""
    cache = O.ResourceCache(THICK)
    objs = [_placed(_shell(tmp_path), "dsf:obj1"),
            _placed(_write(tmp_path / "rail.obj", [_section([-1.0, 1.0], [-7.9, -7.9])]),
                    "dsf:obj3"),
            _placed(_write(tmp_path / "liner.obj", [_section([10.0, 13.0], [-7.2, 0.8])]),
                    "dsf:obj4"),
            _placed(_write(tmp_path / "pier.obj", [_box(-1.0, 50.0, 2.0, 2.0, 5.3, y0=-8.3)]),
                    "dsf:obj5"),
            _placed(_write(tmp_path / "deck.obj", [_box(-15.0, 40.0, 30.0, 20.0, 1.0, y0=-4.0)]),
                    "dsf:obj6"),
            _placed(_write(tmp_path / "pile.obj", [_box(5.0, 70.0, 1.0, 1.0, 6.0, y0=-11.0)]),
                    "dsf:obj7")]
    floors, notes = OF.read_object_floors(
        objs, cache, LAW, {}, shells={"dsf:obj1": ("dsf:obj3", None)},
        ground=lambda xs, ys: np.full(len(xs), 100.0))
    return objs, cache, floors, notes


def test_the_visible_members_state_the_cut_a_deck_and_a_pile_do_not(tmp_path):
    objs, cache, floors, notes = _frame(tmp_path)
    shell = next(f for f in floors if f.object_id == "dsf:obj1")
    assert shell.hidden and not OF.owns_ground(shell), notes
    (vc,) = VC.visible_cuts(floors, objs, cache, LAW)
    z, members = vc.points[:, 2], set(vc.points[:, 3].tolist())
    # the liner (from its toe 92.8 up to the rim less object_min_depth_m) and
    # the pier (its foot 91.7) — never the deck's soffit (96) nor the pile's
    # buried foot (89)
    assert len(members) == 2 and 91.6 < z.min() and z.max() <= 97.0 + 1e-9, z
    assert vc.covers == 1 and vc.buried == 1
    assert vc.bound is shell.footprint


def test_the_feet_are_the_floor_the_bank_runs_from_them_to_the_crest():
    axis = LineString([(0.0, 0.0), (1000.0, 0.0)])
    # member 0: a bank liner at station 100, toe 69.7 at 30 m off, top 77 at
    # 38 m; member 1: a footing 69.3 at 20 m; member 2: a tree on the bank
    # top (74.0 at 37 m); member 3: a wall foot 65.0 at station 600, 25 m off;
    # member 4 stands beyond the axis
    pts = np.array([[100.0, 30.0, 69.7, 0], [100.0, 38.0, 77.0, 0], [101.0, 34.0, 73.0, 0],
                    [100.0, 20.0, 69.3, 1], [100.0, 37.0, 74.0, 2],
                    [600.0, 25.0, 65.0, 3], [1200.0, 0.0, 10.0, 4]])
    cut = types.SimpleNamespace(points=pts, bound=None)
    p = CD.cut_points([cut], axis, 120.0)
    assert len(p) == 6                                     # beyond the axis: not its
    ss = [0.0, 100.0, 350.0, 600.0, 900.0]
    feet = CD.cut_feet(p, ss, 10.0)
    assert sorted(feet[1][:, 2].tolist()) == [69.3, 69.7, 74.0]   # one foot per member
    prof = dict(CD.cut_profile(feet, ss))
    assert abs(prof[100.0] - 69.7) < 1e-6                  # the median foot
    assert abs(prof[0.0] - 69.7) < 1e-6 and abs(prof[900.0] - 65.0) < 1e-6   # held
    assert abs(prof[350.0] - (69.7 + 65.0) / 2) < 1e-6     # linear between witnesses
    assert CD.cut_span(p) == (100.0, 600.0)
    edge, crest = CD.cut_halves(p, feet, ss, CD.cut_profile(feet, ss), 10.0, 1.0, 6.0,
                                120.0, 1.6, 10.0)
    # the floor ends at the liner's toe (30 m; the tree on the bank top is no
    # floor edge), the crest at its top (38 m)
    assert abs(edge[1] - 30.0) < 1e-6 and abs(crest[1] - 38.0) < 1e-6
    assert all(c >= e + 1.6 - 1e-9 for e, c in zip(edge, crest, strict=True))


def test_the_axis_runs_on_along_its_continuation_inside_the_cut():
    from shapely.geometry import box

    def way(i, pts, **tags):
        return types.SimpleNamespace(id=i, points=pts, tags=tags)

    def kind(w):
        return "rail" if w.tags.get("railway") else "road"

    lead = way(1, [(0.0, 0.0), (100.0, 0.0)], railway="rail")
    on = way(2, [(100.0, 0.0), (200.0, 10.0)], railway="rail")
    branch = way(3, [(100.0, 0.0), (100.0, 90.0)], railway="rail")
    road = way(4, [(200.0, 10.0), (300.0, 10.0)], highway="primary")
    pts = np.array([[150.0, 20.0, 70.0, 0], [250.0, 25.0, 70.0, 1]])
    cut = types.SimpleNamespace(points=pts, bound=box(-10, -40, 400, 40))
    ln, used = CD.extend_axis(LineString(lead.points), [lead, on, branch, road], [cut],
                              120.0, kind)
    assert used == [2] and abs(ln.length - (100.0 + np.hypot(100.0, 10.0))) < 1e-6
    same, none = CD.extend_axis(LineString(lead.points), [lead, on], [], 120.0, kind)
    assert none == [] and same.length == 100.0             # no visible cut: unchanged


def test_the_floor_rejoins_the_road_where_its_way_runs_on():
    prof = ((100.0, 75.0), (150.0, 70.0), (300.0, 70.0), (500.0, 70.0))
    out = dict(CD.rejoin(prof, 500.0, lambda s: 65.0, 0.10))
    # the way runs on past s 100 (the axis starts at 0): the floor there
    # hands over to the ground (65) at no more than 10 %
    assert abs(out[100.0] - 65.0) < 1e-9 and abs(out[150.0] - 70.0) < 1e-9
    # s 500 is the axis's own end: nothing to hand over to, left as stated
    assert out[500.0] == 70.0 and out[300.0] == 70.0
