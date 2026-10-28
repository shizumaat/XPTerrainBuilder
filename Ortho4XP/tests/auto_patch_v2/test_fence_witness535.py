"""Lane ``l535`` twins — issue #535, owner RULINGS 2026-10-27z: a mapped
``tunnel`` bore inside the airport fence with none of the five witnesses
(rise, road-level sign at a mouth, pack portal, anything over it, a lidar
cut on a credible inset) is NOT built (§34 (12) (5) (d) narrowed)."""
from __future__ import annotations

import types

import pytest
import test_tunnelwitness2 as TW  # noqa: E402
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.structure_fence import fence_witness
from shapely.geometry import LineString

BORE = ((300.0, -100.0), (335.0, -100.0))
ROAD = {"highway": "secondary", "lanes": "3"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ask(law, *more, bore_tags=TW.SPJC_TAGS, partition=None, prints=()):
    """``fence_witness`` asked of SPJC -5724's shape: the bore, its two
    approach roads (level, unless ``more`` replaces them) and ``more``."""
    bore = OsmWay(-5724, "big_roads", BORE, False, dict(bore_tags))
    approach = (OsmWay(-5708, "big_roads", ((150.0, -100.0), BORE[0]), False, ROAD),
                OsmWay(-5723, "big_roads", (BORE[1], (485.0, -100.0)), False, ROAD))
    ap = types.SimpleNamespace(dem=TW._Dem(lambda x, y: 21.97 - 0.015 * (x - 300.0)),
                               partition=partition,
                               frame=Frame("ZZZZ", origin=(-12.03, -77.11), identity_dp=11))
    on_field = types.SimpleNamespace(corridor_prints=prints, corridor_objects=())
    f = fence_witness(ap, law, on_field, (bore,) + approach + tuple(more))
    return f(types.SimpleNamespace(line=LineString(BORE), points=BORE, ways=(bore,)))


def test_a_fenced_bore_with_NO_witness_is_REFUSED_by_name(law):
    """SPJC -5724 / KDEN -6306: cover 0, rise +0.00, no layer, level
    approach roads, no pack portal, nothing over it, no lidar cut."""
    _cl, tunnels, st = TW._spjc(law)
    assert st.tunnels == 0 and not tunnels, st.mouths_off_field_nearest
    named = TW._refusals(st)
    assert len(named) == 1
    assert "-5724 IS TAGGED A TUNNEL INSIDE THE AIRPORT BOUNDARY WITH NO WITNESS" in named[0]
    assert "2026-10-27z" in named[0]
    assert _ask(law) is None


def test_a_RISE_is_a_witness(law):
    _cl, _t, st = TW._spjc(law, dem=TW._hill(0.7))
    assert st.tunnels == 2 and not TW._refusals(st)


@pytest.mark.parametrize("tags", [dict(ROAD, layer="-1"), dict(ROAD, bridge="yes"),
                                  dict(ROAD, tunnel="yes"), dict(ROAD, incline="down")])
def test_a_LEVEL_SIGN_on_a_road_joined_at_a_mouth_is_a_witness(law, tags):
    joined = OsmWay(-9001, "big_roads", (BORE[1], (335.0, -300.0)), False, tags)
    seen = _ask(law, joined)
    assert seen and "road level" in seen and "-9001" in seen


def test_a_level_road_joined_or_a_signed_road_AWAY_from_the_mouths_is_not(law):
    level = OsmWay(-9002, "big_roads", (BORE[1], (335.0, -300.0)), False, dict(ROAD, layer="0"))
    away = OsmWay(-9003, "big_roads", ((340.0, -100.0), (340.0, -300.0)), False,
                  dict(ROAD, layer="-1"))
    assert _ask(law, level, away) is None


def test_an_INCLINE_on_the_bore_is_a_witness(law):
    seen = _ask(law, bore_tags=dict(TW.SPJC_TAGS, incline="-5%"))
    assert seen and "incline" in seen


@pytest.mark.parametrize("tags", [dict(ROAD, bridge="yes", layer="1"),
                                  {"building": "yes"}, {"aeroway": "taxiway"},
                                  {"highway": "footway"}])
def test_ANYTHING_crossing_over_the_bore_is_a_witness_at_any_layer(law, tags):
    over = OsmWay(-9004, "x", ((317.0, -150.0), (317.0, -50.0)), False, tags)
    seen = _ask(law, over)
    assert seen and "crossed over" in seen and "-9004" in seen


def test_a_TUNNEL_or_the_AERODROME_over_it_or_a_way_at_a_mouth_is_not(law):
    tunnel = OsmWay(-9005, "x", ((317.0, -150.0), (317.0, -50.0)), False,
                    dict(ROAD, tunnel="yes"))
    aerodrome = OsmWay(-9006, "x", TW._rect(200, -200, 400, 0) + ((200, -200),), True,
                       {"aeroway": "aerodrome"})
    at_mouth = OsmWay(-9007, "x", ((335.5, -150.0), (335.5, -50.0)), False, ROAD)
    assert _ask(law, tunnel, aerodrome, at_mouth) is None


def test_a_PACK_PORTAL_at_a_mouth_is_a_witness_from_existing_law(law):
    """Below the ground-contact band (``[basin] contact_band_m``) within
    ``[tunnel.object] bore_end_tolerance_m`` of a mouth — HECA's
    ``concrete_3`` (base -1.84) at the east mouth; base -0.9 (inside the
    band) or 8 m off the mouth is no portal."""
    def part(base, x0):
        ring = TW._ll_ring(x0, -110, x0 + 20, -90)
        return TW._partition(("dsf:obj2", "concrete_3.obj", "", (TW._part(base, 2.66, ring),)))
    seen = _ask(law, partition=part(-1.84, 337.0))
    assert seen and "pack portal" in seen and "concrete_3.obj" in seen
    assert _ask(law, partition=part(-0.9, 337.0)) is None
    assert _ask(law, partition=part(-1.84, 343.0)) is None


def test_a_pack_TUNNEL_CORRIDOR_at_a_mouth_is_a_witness(law):
    from shapely.geometry import box
    assert "corridor" in (_ask(law, prints=(box(336.0, -110.0, 360.0, -90.0),)) or "")
    assert _ask(law, prints=(box(345.0, -110.0, 360.0, -90.0),)) is None


def test_a_pack_part_AT_GRADE_over_the_line_is_a_witness(law):
    over = TW._part(0.0, 6.0, TW._ll_ring(310, -110, 325, -90))
    _cl, _t, st = TW._spjc(law, partition=TW._link(over))
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest


def test_OUTSIDE_the_fence_nothing_changes(law):
    _cl, _t, st = TW._spjc(law, fence=None)
    assert st.tunnels == 0
    assert "-5724 PASSES UNDER NOTHING AT GRADE" in TW._refusals(st)[0]
