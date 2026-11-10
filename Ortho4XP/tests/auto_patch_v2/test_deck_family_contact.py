"""#1969: A DECK FAMILY IS A ROW; A DECK GOVERNS ONLY WHAT IT TOUCHES.

KBZN's shared-datum ``T1`` row places 122 files at one anchor, three of
them carpets flagged ``ATTR_hard_deck``.  The anchor-identity deck family
(``deck_signature.family_key``) took the whole row out of the line class
(14.1 rule 4), so the 5.3 km perimeter fence chained the airport into one
footprint unit and floated its buildings 15-20 m.  A family member that no
deck footprint of its family touches keeps the line class; a railing on
the deck stays governed by it.
"""
from __future__ import annotations

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import rebake_plan as RP
from auto_patch_v2.airport.deck_family_contact import ungoverned_members
from auto_patch_v2.law import Law
from shapely.geometry import box
from test_v2fence import _obj, _sheet, _slab

LAW = Law.for_airport("")


def _placed(oid, path, deck=None, kind=""):
    return O.PlacedObject(id=oid, path=path, resolved=path, xy=(0.0, 0.0),
                          heading_deg=0.0, agl_m=0.0, kind="OBJECT", anchor_z=100.0,
                          below_grade=None, plan_bbox=None, solid_min_z=None,
                          solid_min_depth_m=None, hard_deck=deck, deck_top_z=None,
                          deck_kind=kind)


def _row(tmp_path):
    """One anchor: a flagged deck (authored x -10..10, z -5..5 -> frame
    east -10..10, north -5..5), a railing along its edge, and a perimeter
    fence 200 m away."""
    deck = _obj(tmp_path / "carpet.obj", _slab(-10.0, 10.0, -5.0, 5.0, 3.0, 3.3))
    rail = _obj(tmp_path / "rail.obj", _sheet(-10.0, 10.0, 4.5, 3.3, 4.3))
    fence = _obj(tmp_path / "fence.obj", _sheet(-400.0, 400.0, -200.0, 0.0, 2.5))
    return [_placed("dsf:obj0", deck, box(-10.0, -5.0, 10.0, 5.0), "flag"),
            _placed("dsf:obj1", rail), _placed("dsf:obj2", fence)]


def test_only_the_member_no_deck_touches_is_ungoverned(tmp_path):
    objs = _row(tmp_path)
    fam = {o.id: "row" for o in objs}
    cache = O.ResourceCache(0.05)
    got = ungoverned_members(objs, fam, {o.id for o in objs}, cache, 0.5, 0.5,
                             LAW.tables.structures.rebake)
    assert got == {"dsf:obj2"}


def test_one_post_on_the_deck_does_not_govern_a_fence(tmp_path):
    """KBZN: the perimeter fence meets the terminal (and a carpet in it) at
    one post, 0.29 m away — 0.4 % of its vertices.  Contact is not standing
    on the deck."""
    objs = _row(tmp_path)
    fence = _obj(tmp_path / "fence2.obj", _sheet(-400.0, -9.8, -4.0, 0.0, 2.5))
    objs.append(_placed("dsf:obj3", fence))
    fam = {o.id: "row" for o in objs}
    got = ungoverned_members(objs, fam, {o.id for o in objs}, O.ResourceCache(0.05), 0.5, 0.5,
                             LAW.tables.structures.rebake)
    assert "dsf:obj3" in got


def test_the_far_fence_keeps_the_line_class(tmp_path):
    """The screen: the railing is structure-seated (it rides the deck),
    the perimeter fence is not, so 10bb's line class reaches it."""
    objs = _row(tmp_path)
    cache = O.ResourceCache(0.05)
    screen, _objs = RP.screen_of(objs, cache, LAW)
    assert screen.deck_family == {"dsf:obj0", "dsf:obj1", "dsf:obj2"}
    assert "dsf:obj1" in screen.structure_seated
    assert "dsf:obj2" not in screen.structure_seated
