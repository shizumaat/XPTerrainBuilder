"""Twins of the imagery tier planner (#1992 P3a, spec §4.3) and its
flight-2 replay (``tools/imagery_tier_replay.py``)."""
from __future__ import annotations

import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "src"))
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))

import imagery_tier_replay as R  # noqa: E402
import O4_Imagery_Tier_Plan as TP  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "imagery_tier",
                       "flight2_outbound.replay.json")
S = 4744.0                       # a ZL16 square at 61 N (LOAD_CENTER)
LAT0 = 60.0
V = 129.0                        # 250 kt


def _square_at(east_m: float, north_m: float, name="sq") -> TP.Square:
    lat = LAT0 + north_m / 111_320.0
    lon = east_m / (111_320.0 * math.cos(math.radians(LAT0)))
    return TP.Square(name, lat, lon, S)


def _north(v=V) -> TP.Motion:
    return TP.Motion(LAT0, 0.0, 1000.0, 0.0, v)


def test_on_track_square_gets_1024_then_full_never_2048():
    sq = _square_at(0.0, 30_000.0)
    fl = TP.plan(_north(), [sq], {})
    assert [(f.tier, f.crossing) for f in fl] == [(1, 1), (3, 2)]
    t1 = (30_000.0 - 5.2 * S) / V
    t2 = (30_000.0 - 2.8 * S) / V
    assert fl[0].deadline_s == pytest.approx(t1, rel=1e-3)
    assert fl[1].deadline_s == pytest.approx(t2, rel=1e-3)
    assert fl[0].start_in_s == pytest.approx(t1 - TP.DEFAULT_LEAD_S, rel=1e-3)
    assert not any(f.late for f in fl)


def test_abeam_beyond_2_8_S_gets_1024_only():
    sq = _square_at(3.5 * S, 30_000.0)        # beyond 2.8 S + 0.5 S margin
    assert [f.tier for f in TP.plan(_north(), [sq], {})] == [1]


def test_abeam_between_1_65_and_2_8_S_gets_1024_then_2048():
    sq = _square_at(2.2 * S, 30_000.0)        # beyond 1.65 S + margin
    assert [f.tier for f in TP.plan(_north(), [sq], {})] == [1, 2]


def test_turn_margin_wants_the_full_at_the_closest_approach():
    sq = _square_at(1.9 * S, 30_000.0)        # inside 1.65 S + 0.5 S
    fl = TP.plan(_north(), [sq], {})
    assert [f.tier for f in fl] == [1, 3]
    assert fl[1].deadline_s < 30_000.0 / V


def test_slow_full_fetch_falls_back_to_the_crossing_tier():
    sq = _square_at(0.0, 30_000.0)
    fl = TP.plan(_north(), [sq], {}, fetch_s={1: 1, 2: 2, 3: 1000})
    assert [f.tier for f in fl] == [1, 2, 3]


def test_tiers_on_disk_need_nothing():
    sq = _square_at(0.0, 30_000.0)
    assert TP.plan(_north(), [sq], {"sq": 3}) == []
    assert [f.tier for f in TP.plan(_north(), [sq], {"sq": 1})] == [3]


def test_receding_and_far_squares_are_not_listed():
    behind = _square_at(0.0, -30_000.0, "behind")
    far = _square_at(0.0, 200_000.0, "far")     # beyond the 300 s horizon
    assert TP.plan(_north(), [behind, far], {}) == []


def test_passed_crossings_are_late_and_last():
    near = _square_at(0.0, 1.0 * S, "near")       # inside every crossing
    ahead = _square_at(0.0, 40_000.0, "ahead")
    fl = TP.plan(_north(), [near, ahead], {})
    assert [f.square for f in fl if not f.late] == ["ahead", "ahead"]
    assert [f.square for f in fl[-2:]] == ["near", "near"]
    assert all(f.late and f.due for f in fl[-2:])


def test_earliest_deadline_first_across_squares():
    a = _square_at(0.0, 50_000.0, "a")
    b = _square_at(300.0, 35_000.0, "b")
    fl = TP.plan(_north(), [a, b], {})
    assert [f.deadline_s for f in fl] == sorted(f.deadline_s for f in fl)
    assert fl[0].square == "b"


def test_stationary_camera_plans_only_what_is_inside_now():
    inside = _square_at(0.0, 2.5 * S, "in")    # beyond 1.65 S + margin
    outside = _square_at(0.0, 6.0 * S, "out")
    fl = TP.plan(_north(0.0), [inside, outside], {})
    assert {f.square for f in fl} == {"in"}
    assert [f.tier for f in fl] == [1, 2]


@pytest.mark.parametrize("mip,tier", [(0, 3), (1, 2), (2, 1), (3, 0), (4, 0)])
def test_tier_for_mip(mip, tier):
    assert TP.tier_for_mip(mip) == tier


# -- the flight-2 fixture (outbound leg, 0-380 s of the recording) ---------
@pytest.fixture(scope="module")
def flight():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_fixture_step_up_population(flight):
    ups = R.step_ups(flight["loads"])
    assert len(flight["squares"]) == 308
    assert len(ups) == 265 and sum(1 for *_, k in ups if k) == 202


def test_flight2_outbound_served_at_true_speed(flight):
    """Spec §14 P3a acceptance on the cut: >= 98 % of the step-up opens
    after the start window find a file at least as fine, at 85 req/s with
    one file in flight, the airport core kept (§6.1)."""
    data = R.at_true_speed(flight)
    j = R.judge(data, R.simulate(data, req_rate=85.0, slots=1, core=True))
    served, total = j["flight"]
    assert total == 187 and served / total >= 0.98


def test_flight2_outbound_request_rate_near_the_spec_estimate(flight):
    """Cold start, outbound leg: requests per km flown within 20 % of
    §4.3's 60 N 250 kt figure (32 req/s at 129 m/s)."""
    data = R.at_true_speed(flight)
    sim = R.simulate(data, req_rate=85.0, slots=1)
    req = sum(TP.TIER_REQUESTS[k] * n for k, n in sim["fetched"].items())
    per_km = req / R.flown_km(data["pos"])
    assert per_km == pytest.approx(32 * 1000 / 129.0, rel=0.20)


def test_true_speed_undoes_the_ground_speed_multiplier(flight):
    data = R.at_true_speed(flight)
    span = data["pos"][-1][0] - data["pos"][0][0]
    raw = flight["pos"][-1][0] - flight["pos"][0][0]
    assert span > 2.0 * raw
    assert [x[1:] for x in data["loads"]] == [x[1:] for x in flight["loads"]]
