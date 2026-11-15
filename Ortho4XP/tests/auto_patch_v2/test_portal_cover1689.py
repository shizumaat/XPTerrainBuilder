"""#1689 / #1718: a headwall portal holds the survey's cover BEHIND its
roof, and the road under a hard-deck bridge is the deck's.

* ``portal_objects._ground_covers_roof`` reads the cover over the bore
  inward from the end (as far as the roof reaches along it, plus
  ``bore_end_tolerance_m``) against the lowest of the end and the road the
  tolerance out of it: a survey cell straddling the mouth blends the cut's
  two sides, and the roof plan alone reads no cover.
* ``walled_pit.hard_deck_share``: the share of a floor under a ``flag`` /
  ``signature`` hard deck of its frame -- a walled pit or a portal floor
  read under it would give the bridge's frame a second zero.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.airport.walled_pit import hard_deck_share
from auto_patch_v2.law import Law
from shapely.geometry import box

LAW = Law.for_airport("")


def _cut_dem(x: float, y: float) -> float:
    """A road at 169 m for x < 0 rising through a blended cell to cover at
    177 m by x = 10 (the bore runs along +x from its end at the origin)."""
    if x <= -5.0:
        return 169.0
    if x >= 10.0:
        return 177.0
    return 169.0 + (x + 5.0) / 15.0 * 8.0


def test_cover_behind_the_roof_is_read_along_the_bore():
    roof = box(-12.0, -15.0, 2.0, 15.0)   # the headwall's top, mostly out over the road
    assert P._ground_covers_roof(roof, (0.0, 0.0), _cut_dem, LAW) is None
    cover = P._ground_covers_roof(roof, (0.0, 0.0), _cut_dem, LAW, (1.0, 0.0))
    assert cover is not None and cover >= 169.0 + LAW.tables.structures.channel.object_min_depth_m


def test_no_cover_where_the_ground_is_flat():
    flat = lambda x, y: 170.0  # noqa: E731
    roof = box(-12.0, -15.0, 2.0, 15.0)
    assert P._ground_covers_roof(roof, (0.0, 0.0), flat, LAW, (1.0, 0.0)) is None


def _placed(deck, kind="flag"):
    return types.SimpleNamespace(xy=(0.0, 0.0), hard_deck=deck, deck_kind=kind)


def test_hard_deck_share_of_a_floor():
    floor = box(0.0, 0.0, 10.0, 10.0)
    assert hard_deck_share(floor, [_placed(box(0.0, 0.0, 10.0, 6.0))]) == 0.6
    assert hard_deck_share(floor, [_placed(box(0.0, 0.0, 10.0, 6.0), kind="candidate")]) == 0.0
    assert hard_deck_share(floor, [types.SimpleNamespace(xy=(0.0, 0.0))]) == 0.0


def _obj(i, xy=(0.0, 0.0), hdg=10.0, path=None):
    return types.SimpleNamespace(id=f"dsf:obj{i}", path=path or f"Objects/p{i}.obj", xy=xy,
                                 heading_deg=hdg)


def test_a_roofed_portal_leads_its_frame():
    from auto_patch_v2.airport.terrain_shaped import PORTAL_SEAT, portal_frame_records
    objs = [_obj(1), _obj(2), _obj(3, xy=(0.5, 0.0)), _obj(4, xy=(40.0, 0.0)),
            _obj(5, hdg=95.0), _obj(6)]
    recs = [{"id": "dsf:obj1", "resource": "Objects/p1.obj", "datum": "portal",
             "seat": PORTAL_SEAT, "elevation": 168.7},
            {"id": "dsf:obj6", "resource": "Objects/p6.obj", "seat": "object floor",
             "elevation": 160.0}]
    got = portal_frame_records(recs, objs, 2.0)
    assert {r["id"] for r in got} == {"dsf:obj2", "dsf:obj3"}
    assert all(r["elevation"] == 168.7 and r["led_by"] == "dsf:obj1" for r in got)
