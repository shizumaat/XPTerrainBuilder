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
    p = CD._cut_points([cut], axis, 120.0)
    assert len(p) == 6                                     # beyond the axis: not its
    ss = [0.0, 100.0, 350.0, 600.0, 900.0]
    feet = CD._cut_feet(p, ss, 10.0)
    assert sorted(feet[1][:, 2].tolist()) == [69.3, 69.7, 74.0]   # one foot per member
    prof = dict(CD._cut_profile(feet, ss))
    # the HIGHEST floor foot (owner Q2); the tree on the bank top is a ledge
    assert abs(prof[100.0] - 69.7) < 1e-6
    assert abs(prof[0.0] - 69.7) < 1e-6 and abs(prof[900.0] - 65.0) < 1e-6   # held
    assert abs(prof[350.0] - (69.7 + 65.0) / 2) < 1e-6     # linear between witnesses
    assert CD._cut_span(p) == (100.0, 600.0)


def _trench(ledge_only_at=500.0):
    """The spec's twin (object-gate-member-floors §8): a shell with a 60 m
    floor at 69.7 (its floor plates, ``extent``), a LEDGE liner on the left
    bank (foot 72.5 at 33.5 m, top 77.4 at 45 m), a WALL on the right (foot
    69.5 at 35 m), a floor footing on the left (69.7 at 20 m) and a pile
    buried under the floor (66.0 at 10 m); at ``ledge_only_at`` only the
    liner stands."""
    rows, ext = [], []
    for s in np.arange(100.0, 901.0, 5.0):
        rows += [(s, 33.5, 72.5, 0), (s, 45.0, 77.4, 0)]
        if abs(s - ledge_only_at) > 15.0:
            rows += [(s, -35.0, 69.5, 1), (s, -35.0, 77.0, 1), (s, 20.0, 69.7, 2),
                     (s, 10.0, 66.0, 3)]
    for s in np.arange(0.0, 1001.0, 2.5):
        ext += [(s, o, 69.7) for o in np.arange(-30.0, 30.1, 5.0)]
    return types.SimpleNamespace(
        points=np.array(rows, float), bound=None, extent=np.array(ext, float),
        members=(("dsf:obj10", 70.0), ("dsf:obj11", 70.0), ("dsf:obj12", 70.0),
                 ("dsf:obj13", 70.0)))


def _axis_fn(s):
    return (float(s), 0.0)


def test_a_ledge_states_no_floor_and_the_floor_stops_short_of_it():
    """spec object-gate-member-floors §4: signed sides; a ledge foot never
    sets the floor (the ledge-only station interpolates, no bump); the left
    floor edge is the shell's floor edge, never under the ledge; the right
    is the wall foot plus the margin; the left crest is the ledge line,
    pinned at the foot's height; every foot published with its kind."""
    axis = LineString([(0.0, 0.0), (1000.0, 0.0)])
    vis = CD.VisibleFloor([_trench()], axis, 120.0)
    assert (vis.points[vis.points[:, 3] == 0, 1] > 0).all()      # left: positive
    assert (vis.points[vis.points[:, 3] == 1, 1] < 0).all()      # right: negative
    ss = [float(s) for s in np.arange(0.0, 1001.0, 10.0)]
    prof = dict(vis.profile(ss, 10.0, 1.0))
    k100 = ss.index(100.0)
    kinds = dict(zip(vis.feet[k100][:, 3].astype(int).tolist(), vis.kinds[k100].tolist(),
                     strict=True))
    assert kinds == {0: CD.LEDGE, 1: CD.FLOOR, 2: CD.FLOOR, 3: CD.BELOW}
    assert abs(prof[100.0] - 69.7) < 1e-6                 # max(69.5, 69.7)
    assert abs(prof[500.0] - 69.7) < 1e-6                 # the ledge-only station
    (hl, hr), (cl, cr), pins, feet = vis.sides(tuple(sorted(prof.items())), _axis_fn,
                                               6.0, 120.0, 1.6, 50.0, 1.0)
    i = ss.index(300.0)
    assert 29.9 <= hl[i] <= 33.5 - 1.6 + 1e-9             # the shell's floor edge
    assert abs(hr[i] - 36.0) < 1e-6                       # the wall's foot + 1.0
    assert abs(cl[i] - 33.5) < 1e-6 and cr[i] >= hr[i] + 1.6
    on = [p for p in pins if abs(p[0] - 300.0) < 1e-6]
    assert on == [(300.0, 33.5, 72.5)]
    got = {(pid, kind) for _x, _y, _yy, pid, kind in feet}
    assert ("dsf:obj10", CD.LEDGE) in got and ("dsf:obj11", CD.FLOOR) in got
    assert ("dsf:obj13", CD.UNMET) in got                 # buried: states nothing
    led = next(f for f in feet if f[3] == "dsf:obj10" and f[4] == CD.LEDGE)
    assert abs(led[2] - 2.5) < 1e-6                       # authored y: 72.5 - 70.0


def test_the_median_floor_is_one_switch(monkeypatch):
    """Owner Q2 is one switch: off, the station's floor is its median foot."""
    axis = LineString([(0.0, 0.0), (1000.0, 0.0)])
    monkeypatch.setattr(CD, "FLOOR_AT_HIGHEST_FOOT", False)
    vis = CD.VisibleFloor([_trench()], axis, 120.0)
    prof = dict(vis.profile([0.0, 100.0, 200.0], 10.0, 1.0))
    assert abs(prof[100.0] - 69.6) < 1e-6


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
    out = dict(CD.rejoin(prof, 530.0, lambda s: 65.0, 0.10, 50.0))
    # the way runs on past s 100 (the axis starts at 0): the floor there
    # hands over to the ground (65) at no more than 10 %
    assert abs(out[100.0] - 65.0) < 1e-9 and abs(out[150.0] - 70.0) < 1e-9
    # 30 m of axis past s 500 is no road running on: left as stated
    assert out[500.0] == 70.0 and out[300.0] == 70.0


def test_a_bench_wider_than_the_floor_never_sets_the_floor_level():
    """MEASURED LGAV Trench_06 (lobjgate3): from s 290 m a 71.08 m bench
    outweighs the 69.71 m floor; the floor level is the LOWEST plate cluster,
    weighted by plan area (a thin strip's many points weigh little)."""
    ext = np.array([(0.0, o, 69.71, 1.0) for o in range(-20, 21, 5)]
                   + [(0.0, o, 71.08, 3.0) for o in range(-60, 61, 5)]
                   + [(0.0, 40.0, 72.5, 0.01)] * 200)
    lv = CD._shell_floor(ext, [0.0], 10.0, 1.0)
    assert abs(lv[0] - 69.71) < 1e-9
