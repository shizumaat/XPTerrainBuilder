"""THE FRONTAGE ROAD AND ITS KERBSIDE (issue #2057, ``classify/frontage_road``;
the cross-section clip in ``constraints/pad_ramp``).

A mapped road running along a building pad within ``[road_contact]
contact_reach_m`` serves its frontage: the stretch along the pad is a pad
road and the gap between them its kerbside, welded to the pad; a road
farther off stays free, a road already patch is never re-minted.  The
levels (the frontage at the pad's level within the road's cross-section,
the ramps along the road at its ends) are read on the KASE replays of the
lane (issue #2057), not here."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.classify.frontage_road import KERBSIDE_KEY, mint_frontage_roads
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from shapely.geometry import Polygon


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


#: a 150 x 60 m terminal pad, its landside facade along y = 0
PAD = Cell(0, "building", "padA", _rect(0.0, -60.0, 150.0, 0.0), (), None, None,
           "airside", "pad", {})


def _mint(law, y: float, extra=()):
    """Mint for one tertiary way along the facade at ``y`` (its centreline)."""
    way = OsmWay(-7, "airport_small_roads", ((-100.0, y), (250.0, y)), False,
                 {"highway": "tertiary"})
    cells = [PAD, *extra]
    added = []

    def add(role, ref, poly, kind, cn=None, cl=None, ev=None):
        added.append((role, ref, poly, dict(ev or {})))
    stats = mint_frontage_roads(types.SimpleNamespace(osm_ways=(way,)), cells, law,
                                load_rules(), add)
    return stats, added


def test_a_road_along_the_facade_is_a_pad_road_with_its_kerbside(law):
    reach = float(law.tables.emit.road_contact.contact_reach_m)
    stats, added = _mint(law, 15.0)        # ribbon 4 m half-width: an 11 m kerbside
    assert 15.0 - 4.0 <= reach
    roads = [a for a in added if not a[3].get(KERBSIDE_KEY)]
    kerbs = [a for a in added if a[3].get(KERBSIDE_KEY)]
    assert roads and kerbs
    assert all(a[0] == "service_road" and a[3]["pad_road"] and a[3]["frontage_road"]
               for a in added)
    pad = Polygon(PAD.ring)
    rib = roads[0][2]
    for _r, _ref, k, _ev in kerbs:
        assert k.distance(pad) <= 1e-6 and k.distance(rib) <= 1e-3   # pad to road
        assert not k.intersection(pad).area > 1e-6                  # never on the pad
    # the stretch runs along the frontage (+ reach past each end), not the whole way
    length = rib.area / 8.0
    assert 150.0 <= length <= 150.0 + 2 * (reach + 4.0) + 1.0
    assert stats["kerbsides"] == len(kerbs)


def test_a_road_beyond_the_reach_stays_free(law):
    reach = float(law.tables.emit.road_contact.contact_reach_m)
    _stats, added = _mint(law, 4.0 + reach + 5.0)
    assert added == []


def test_a_road_already_patch_is_never_reminted(law):
    rib = Cell(1, "service_road", "small_roads:-7", _rect(-100.0, 11.0, 250.0, 19.0), (),
               None, None, "groundside", "service_road", {"osm_ribbon": 1.0})
    _stats, added = _mint(law, 15.0, extra=(rib,))
    assert added == []

