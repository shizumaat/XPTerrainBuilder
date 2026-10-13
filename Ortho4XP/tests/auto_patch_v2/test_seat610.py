"""Issues #610 / #625 (lane seat610): the bodies of ONE building that TOUCH are
ONE seat — walls, roof, posts, awning (owner RULINGS 2026-10-10n (1)/(3),
2026-09-11i).  The law lives in ``airport/placement_atom``:

* ``unit_rigid``'s ROOF WITNESS: a footed body 12ap's ground test refuses
  stays bound when an elevated body of the cluster stands over it AND over
  a kept body (one roof, one building); a roof over refused bodies only
  rides the body it stands on (two buildings that touch, each with its
  roof); a roof the SPAN bound tore off the walls it touches is released
  to the carrier search;
* ``follow_seniors``: a bound body follows its senior through the later
  §16g unit seat, and the unit seat LEADS the cluster.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.airport import anchor_rule as _ar
from auto_patch_v2.airport import placement_atom as ATOM
from auto_patch_v2.airport import placement_carrier as _pc


_BOX_A = (40.0, -3.0, 40.0005, -2.9995)            # ~55 x 43 m
_BOX_B = (40.0004, -3.0, 40.0009, -2.9995)         # touching A's north edge
_BOX_FAR = (40.0012, -3.0, 40.0017, -2.9995)       # beside, no overlap with A


def _footed(member, pid, box, zero, feet, area=100.0):
    return ATOM.RigidNode(member, frozenset([pid]), box, footprint_m2=area,
                          footed=True, bindable=True, zero=zero, feet=feet)


def _roof(member, pid, box):
    return ATOM.RigidNode(member, frozenset([pid]), box, footprint_m2=50.0,
                          footed=False, bindable=True, zero=None)


def test_two_touching_bodies_on_sloping_ground_under_one_roof_are_one_seat():
    """KASE Atlantic FBO: the posts (`FBO_3` b1) stand 0.78 m below the
    senior on ground that slopes under ONE building; the canopy
    (`FBO_5` b0) stands over the posts and the building.  12ap alone
    refused the posts; under the roof witness they are bound."""
    walls = _footed(0, 1, _BOX_A, 600.0, 30)
    posts = _footed(0, 2, _BOX_B, 599.22, 8, area=4.0)
    canopy = _roof(1, 3, (40.0, -3.0, 40.0009, -2.9995))   # over both
    cnt: dict = {}
    senior, _c = ATOM.unit_rigid([walls, posts, canopy], [(1, 2), (2, 3)],
                                 bind_ground_m=0.5, counts=cnt, roof_bind_m=1.0)
    assert senior == [-1, 0, 0], senior
    assert cnt.get("bind_kept_under_one_roof") == 1
    assert not cnt.get("bind_refused_for_ground")
    # without the roof the 12ap refusal stands (the GSE-box class)
    cnt2: dict = {}
    senior2, _c2 = ATOM.unit_rigid([walls, posts], [(1, 2)],
                                   bind_ground_m=0.5, counts=cnt2)
    assert senior2 == [-1, -1]
    assert cnt2["bind_refused_for_ground"] == 1
    # THE CAP ([terrace] pad_terrace_floor_m): a step the size of a terrace
    # is the terrain's to adapt — HECA T3's doors on the ground 10 m under
    # the pad's roof keep their own ground, and so does a 1.5 m one
    deep = _footed(0, 2, _BOX_B, 598.5, 8, area=4.0)
    cnt3: dict = {}
    senior3, _c3 = ATOM.unit_rigid([walls, deep, canopy], [(1, 2), (2, 3)],
                                   bind_ground_m=0.5, counts=cnt3, roof_bind_m=1.0)
    assert senior3 == [-1, -1, 0], senior3
    assert cnt3["bind_refused_for_ground"] == 1


def test_a_roof_over_two_wall_bodies_binds_both():
    """A roof authored as its own resource over two wall bodies of one
    building (KCLT `001_ALB` roofs over `00x_ALB` walls): the lower wall
    body is refused by ground alone and bound under the roof."""
    wall_a = _footed(0, 1, _BOX_A, 223.47, 48)
    wall_b = _footed(2, 2, _BOX_B, 222.70, 12)
    roof = _roof(1, 3, (40.0, -3.0, 40.0009, -2.9995))
    senior, _c = ATOM.unit_rigid([wall_a, wall_b, roof], [(1, 3), (2, 3)],
                                 bind_ground_m=0.5, roof_bind_m=1.0)
    assert senior == [-1, 0, 0], senior


def test_two_buildings_that_touch_at_a_corner_keep_two_seats_and_their_own_roofs():
    """Two separate buildings on two levels touching at a corner, each
    with its own roof: the lower one is refused (its own ground), and its
    roof rides IT — never the senior 0.78 m up — so no roof is written
    above its own walls; the senior's roof rides the senior."""
    big = _footed(0, 1, _BOX_A, 217.50, 28)
    small = _footed(0, 2, _BOX_FAR, 216.71, 4, area=10.0)
    roof_big = _roof(1, 3, _BOX_A)
    roof_small = _roof(1, 4, _BOX_FAR)
    cnt: dict = {}
    senior, _c = ATOM.unit_rigid(
        [big, small, roof_big, roof_small],
        [(1, 2), (1, 3), (2, 4), (3, 4)], bind_ground_m=0.5, counts=cnt,
        roof_bind_m=1.0)
    assert senior[0] == -1 and senior[1] == -1, senior
    assert senior[2] == 0 and senior[3] == 1, senior
    assert cnt["bind_refused_for_ground"] == 1
    assert cnt["roof_rides_its_own_walls"] == 1


class _St:
    """A staged member as ``_take_senior`` reads it."""

    def __init__(self, mi, anchor, feet):
        self.mi = mi
        self.raw = [((), "other", anchor, tuple(feet), False, None, (), None)]
        self.groups = [[0]]
        self.ground_off = [0.0]


def _cand(member, group, anchor, feet, box=_BOX_A):
    return _pc.Candidate(member, f"objects/m{member}__b{group}.obj", anchor,
                         frozenset([member * 10 + group]), len(feet), box,
                         part_boxes=(box,), ground_off=0.0, group=group,
                         body_class="other")


def test_a_bound_body_follows_its_senior_through_the_unit_seat():
    """KASE: the senior's anchor is COPIED at bind time; the §16g unit seat
    then lifts the senior 0.51 m and the bound leaf stays behind.  After
    the seat it follows — same zero, its own reason."""
    flat = lambda lat, lon: 2362.11                               # noqa: E731
    senior_anchor = _ar.Anchor("other", 40.0001, -2.9999, 0.01, "low-side foot",
                               surface_z=2362.12)
    leaf_anchor = _dc.replace(senior_anchor, reason=f"{ATOM._BOUND}x")
    cands = [_cand(0, 0, senior_anchor, [(40.0001, -2.9999, 0.0)]),
             _cand(1, 0, leaf_anchor, [(40.0004, -2.9999, 0.0)], _BOX_B)]
    staged = [_St(0, senior_anchor, cands[0].feet and [(40.0001, -2.9999, 0.0)]),
              _St(1, leaf_anchor, [(40.0004, -2.9999, 0.0)])]
    # the unit seat moves the senior (what footprint_unit._seat does)
    seated = _ar.Anchor("other", 40.0002, -2.9998, -0.08,
                        "§16g unit u@ground on its median ground at 2362.62",
                        surface_z=2362.54, unit_seat=True)
    cands[0] = _dc.replace(cands[0], anchor=seated)
    cnt: dict = {}
    n = ATOM.follow_seniors(cands, staged, flat, {0: 0, 1: 0}, cnt)
    assert n == 1 and cnt["bodies_followed_senior_seat"] == 1
    z = lambda a: a.surface_z - a.y_zero                           # noqa: E731
    assert z(cands[1].anchor) == pytest.approx(2362.62)
    assert cands[1].anchor.reason.startswith(ATOM._BOUND)
    assert staged[1].raw[0][2] is cands[1].anchor
    # a second pass has nothing to do
    assert ATOM.follow_seniors(cands, staged, flat, {0: 0, 1: 0}, {}) == 0


def test_the_unit_seat_leads_the_cluster_whichever_body_was_senior():
    """KCLT `003_ALB` b10: a unit HOST bound (by feet) to a 4-foot leaf
    senior — the host's §16g seat leads, the leaf follows UP; and two
    unit seats at two zeros in one cluster are two units touching, each
    kept."""
    flat = lambda lat, lon: 209.69                                  # noqa: E731
    leaf_anchor = _ar.Anchor("other", 40.0001, -2.9999, 0.0, "low-side foot",
                             surface_z=209.69)
    host_seated = _ar.Anchor("other", 40.0002, -2.9998, 0.0,
                             "§16g unit fu:3:368/host@ground at 210.14",
                             surface_z=210.14, unit_seat=True)
    other_seated = _ar.Anchor("other", 40.0003, -2.9997, 0.0,
                              "§16g unit fu:3:140@pad at 223.28",
                              surface_z=223.28, unit_seat=True)
    cands = [_cand(0, 0, leaf_anchor, [(40.0001, -2.9999, 0.0)] * 4),
             _cand(1, 0, host_seated, [(40.0002, -2.9998, 0.0)] * 2, _BOX_B),
             _cand(2, 0, other_seated, [(40.0003, -2.9997, 0.0)], _BOX_FAR)]
    staged = [_St(i, c.anchor, [(40.0, -3.0, 0.0)]) for i, c in enumerate(cands)]
    cnt: dict = {}
    n = ATOM.follow_seniors(cands, staged, flat, {0: 0, 1: 0, 2: 0}, cnt)
    z = lambda a: a.surface_z - a.y_zero                           # noqa: E731
    assert n == 1
    assert z(cands[0].anchor) == pytest.approx(210.14)             # followed up
    assert z(cands[1].anchor) == pytest.approx(210.14)             # the lead
    assert z(cands[2].anchor) == pytest.approx(223.28)             # its own unit
    assert cnt["bound_unit_seats_kept_apart"] == 1
