"""lkden5 (owner KDEN 2026-11-18T01:11Z): a ROAD OVERPASS deck warps too —
held over the road it spans, its landing end graded (``deck_profile``)."""
from __future__ import annotations

from types import SimpleNamespace as NS

from auto_patch_v2.airport import deck_profile as DP

OVERPASS = ("airside deck on the road beneath the overpass 1627.91..1631.25 over 30 "
            "stations (its zero on the road, y +0.00; RULINGS 2026-10-30f (5)): flush "
            "at zero 1630.20 (RULINGS 2026-10-22n; was: low-side foot)")
AIRSIDE = ("airside deck on the solved airside surface at its end lines 101.20 / 101.30 "
           "(RULINGS 2026-10-22n)")


def _piece(reason, cls="deck", stations=((39.0, -104.0), (39.0001, -104.0)), zero=1630.2):
    body = NS(body_class=cls, anchor=NS(reason=reason), elevated=False, geom_pts=(),
              merged_into=None, band=None)
    return DP._Piece((0, 0), "unit:1", "deck.obj", zero, [], True, False, body,
                     NS(plate_stations=stations))


def test_an_overpass_deck_is_a_group_of_its_own():
    groups = DP._groups([_piece(OVERPASS)], walled_m=2.0)
    assert list(groups) == ["unit:1|overpass:deck.obj"]


def test_an_overpass_is_not_refused_as_an_airside_deck_but_class_a_still_is():
    assert DP._refusal([_piece(OVERPASS)], [0]) == ""
    assert DP._refusal([_piece(AIRSIDE)], [0]) == "airside_deck"


def test_no_stations_no_overpass_group():
    assert DP._groups([_piece(OVERPASS, stations=())], walled_m=2.0) == {}


def test_the_crossing_holds_the_zero_over_the_road_stations():
    xy = lambda la, lo: ((lo + 104.0) * 85000.0, (la - 39.0) * 111000.0)  # noqa: E731
    (node,) = DP._crossing_nodes([_piece(OVERPASS)], [0], xy)
    d, geom, c = node
    assert d == 0.0 and c == -1
    assert geom.contains(geom.centroid)
    assert geom.bounds[3] - geom.bounds[1] >= 11.0      # the two stations, 11 m apart
