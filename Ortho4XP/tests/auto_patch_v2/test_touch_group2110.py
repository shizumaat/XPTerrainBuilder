"""RULINGS 2026-11-16k (#2110): touching buildings stay grouped — building
components of one frame that touch share one group zero; a fence or wall
between them does not chain them (14a (2) stands).  LOWS: Terminal_LOWS_41
b7 stood 0.74 m under Terminal_LOWS_46 b1, which it touches."""
from __future__ import annotations

import types

from auto_patch_v2.airport.open_frame_seat import body_root, group_key
from auto_patch_v2.airport.touch_group import touch_links
from auto_patch_v2.airport.touching_steps import census_touching_steps

_D = 1e-5                                   # ~1.1 m of lat per unit


def _sq(x0, s=10.0):
    return ((0.0, x0 * _D), (0.0, (x0 + s) * _D), (s * _D, (x0 + s) * _D), (s * _D, x0 * _D))


def _part(pid, x0, s=10.0, line=False, comp=None, rings=True):
    r = _sq(x0, s)
    box = (min(q[0] for q in r), min(q[1] for q in r), max(q[0] for q in r),
           max(q[1] for q in r))
    return types.SimpleNamespace(pid=pid, comp=pid if comp is None else comp,
                                 rings=(r,) if rings else (), box=box, line=line,
                                 height_m=1.0)


def _frame(*parts):
    return types.SimpleNamespace(id="f", anchor=(0.0, 0.0), members=[
        types.SimpleNamespace(id="dsf:obj1", resource="a.obj", origin=(0.0, 0.0),
                              parts=list(parts))])


def _staged(groups=(), parts=()):
    raw = [([p],) for p in parts]
    return [types.SimpleNamespace(raw=raw, groups=[list(g) for g in groups], carried=[],
                                  unit_carried=[], own_ground=[])]


def test_touching_units_take_one_group():
    """Two units whose parts come within ``touch_m``: one group, moving with
    the larger (no airside share)."""
    u = _frame(_part(1, 0.0), _part(2, 10.3), _part(3, 10.3, 2.0))
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:2", 0.0), 3: ("fu:1:2", 0.0)}
    assert touch_links(u, [], pw) == {"fu:1:1": "fu:1:2"}


def test_apart_units_stay_apart():
    u = _frame(_part(1, 0.0), _part(2, 12.0))
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:2", 0.0)}
    assert touch_links(u, [], pw) == {}


def test_a_fence_between_joins_nothing():
    """14a (2): a line part touching both is no link."""
    u = _frame(_part(1, 0.0), _part(2, 10.2, 2.0, line=True), _part(3, 12.4))
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:9", 0.0), 3: ("fu:1:3", 0.0)}
    assert touch_links(u, [], pw) == {}


def test_one_body_holding_two_units_joins_them():
    """A body is one rigid piece: the units its parts hold are one group,
    even where the parts themselves do not touch (LOWS Terminal_LOWS_59 b3:
    the terminal's parts and the north building's)."""
    p1, p2 = _part(1, 0.0), _part(2, 30.0)
    u = _frame(p1, p2)
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:2", 0.0)}
    assert touch_links(u, _staged([[0, 1]], [p1, p2]), pw) != {}


def test_airside_share_leads_the_group():
    u = _frame(_part(1, 0.0), _part(2, 10.3), _part(3, 10.3, 2.0))
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:2", 0.0), 3: ("fu:1:2", 0.0)}
    air = {group_key("fu:1:1", "f"): (1.0, 4)}
    assert touch_links(u, [], pw, airside=air) == {"fu:1:2": "fu:1:1"}


def test_a_body_takes_its_parts_unit_before_a_fallback_carrier_s():
    """22o (1): a body whose parts belong to a unit takes that unit, not the
    unit a NO-EVIDENCE carrier names (LOWS Terminal_LOWS_41 b7)."""
    fallback = types.SimpleNamespace(
        family="fu:1:9@one_building",
        reason="carried by x.obj (nearest footed body of the unit (29 m))")
    b = types.SimpleNamespace(anchor=fallback, pids=(1, 2, 3), merged_into="x.obj")
    pw = {1: ("fu:1:1/host", 0.0), 2: ("fu:1:1/host", 0.0), 3: ("fu:1:2", 0.0)}
    assert body_root(b, pw) == "fu:1:1"
    assert body_root(types.SimpleNamespace(anchor=fallback, pids=(7,)), pw) == "fu:1:9"
    # a carrier it RESTS on keeps it: the rider stays with its carrier
    rests = types.SimpleNamespace(family="fu:1:9@one_building",
                                  reason="carried by x.obj (rests on it)")
    assert body_root(types.SimpleNamespace(anchor=rests, pids=(1, 2)), pw) == "fu:1:9"


def test_census_lists_the_step_between_touching_bodies():
    p1, p2 = _part(1, 0.0, comp=0), _part(2, 10.3, comp=1)
    plan = types.SimpleNamespace(units=[_frame(p1, p2)])
    split = {"placement": {"index": 1, "resource": "a.obj", "lat": 0.0, "lon": 0.0},
             "bodies": [{"components": [0], "surface_z": 10.0, "y_zero": 0.0,
                         "new_resource": "a0"},
                        {"components": [1], "surface_z": 10.7, "y_zero": 0.0,
                         "new_resource": "a1"}]}
    got = census_touching_steps(plan, [split])
    assert len(got["pairs"]) == 1 and abs(got["pairs"][0][0] - 0.7) < 1e-9
