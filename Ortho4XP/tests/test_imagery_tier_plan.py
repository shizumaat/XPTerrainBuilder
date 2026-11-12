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


# -- altitude (RULINGS 2026-11-12f + 17:56Z, spec §4.3 "Altitude") --------
FT = 0.3048


def _at(agl_m: float, v=V, vz=0.0) -> TP.Motion:
    return TP.Motion(LAT0, 0.0, 1000.0 + agl_m, 0.0, v, agl_m, vz)


def _field(n=13, step=0.75 * S):
    """A field of squares around and ahead of a northbound camera."""
    return [_square_at(i * step, j * step, f"{i},{j}")
            for i in range(-n // 2, n // 2 + 1) for j in range(-4, 2 * n)]


def _key(fl):
    return [(f.square, f.tier, f.crossing, f.late) for f in fl]


def _best(fl) -> dict:
    out = {}
    for f in fl:
        out[f.square] = max(out.get(f.square, 0), f.tier)
    return out


def test_the_eye_angles_are_the_crossings_read_at_the_eye():
    """EYE_RAD[k] = 1 / (c_k W_{k-1}): about one minute of arc."""
    for k in (1, 2, 3):
        assert TP.texel_angle(k - 1, S, TP.CROSSING_S[k] * S) == \
            pytest.approx(TP.EYE_RAD[k])
        assert math.degrees(TP.EYE_RAD[k]) * 60 == pytest.approx(1.15, abs=0.15)


def test_on_the_ground_the_plan_is_the_horizontal_plan():
    """h = 0 is the ground plan exactly (also with a vertical speed: no
    height, no vertical term); a cockpit 3 m up changes no tier."""
    field = _field()
    ground = TP.plan(_at(0.0), field, {})
    assert ground == TP.plan(_north(), field, {})       # default agl = 0
    assert ground == TP.plan(_at(0.0, vz=8.0), field, {})
    cockpit = TP.plan(_at(3.0), field, {})
    assert _key(cockpit) == _key(ground)
    for x, y in zip(cockpit, ground, strict=True):
        assert x.deadline_s == pytest.approx(y.deadline_s, abs=0.01)


def test_1000_ft_and_35000_ft_want_different_tiers_and_radii():
    """Low: finest tiers over a small area; high: coarser tiers, never the
    full file far below the aircraft."""
    field = _field()
    low = _best(TP.plan(_at(1_000 * FT), field, {}))
    high = _best(TP.plan(_at(35_000 * FT), field, {}))
    assert max(low.values()) == 3 and max(high.values()) == 2
    assert all(high.get(k, 0) <= t for k, t in low.items())
    assert sum(1 for t in high.values() if t == 2) < \
        sum(1 for t in low.values() if t >= 2)
    # a square 2 S ahead of a hovering camera: the full file low, at
    # FL350 (slant 14.3 km, past 1.65 S + the 0.5 S margin) 2048 at most
    ahead = [_square_at(0.0, 2.0 * S, "ahead")]
    assert sorted(f.tier for f in TP.plan(_at(1_000 * FT, 0.0), ahead,
                                          {})) == [1, 3]
    assert sorted(f.tier for f in TP.plan(_at(35_000 * FT, 0.0), ahead,
                                          {})) == [1, 2]


def test_a_higher_level_camera_never_plans_more_files_or_bytes():
    """The budget: every circle shrinks with height, so on the same track
    a higher camera plans no more files and no more bytes."""
    field = _field()
    prev_n = prev_bytes = math.inf
    for feet in (0, 1_000, 5_000, 10_000, 20_000, 35_000, 45_000):
        fl = TP.plan(_at(feet * FT), field, {})
        n, b = len(fl), sum(TP.TIER_BYTES[f.tier] for f in fl)
        assert n <= prev_n and b <= prev_bytes
        prev_n, prev_bytes = n, b
    assert prev_bytes < sum(TP.TIER_BYTES[f.tier]
                            for f in TP.plan(_at(0.0), field, {}))


def test_a_descent_schedules_the_finer_tier_before_its_height():
    """A camera descending at 10 m/s over a ZL18 square (S = 1.2 km): the
    full file's deadline is the height 1.65 S, reached in ~103 s; level
    at the same height it would never be wanted."""
    sq = TP.Square("zl18", LAT0, 0.0, 1195.0)
    level = TP.plan(_at(3_000.0, 0.0), [sq], {"zl18": 2})
    assert level == []
    down = TP.plan(_at(3_000.0, 0.0, -10.0), [sq], {"zl18": 2})
    assert [(f.tier, f.crossing) for f in down] == [(3, 3)]
    assert down[0].deadline_s == pytest.approx((3_000 - 1.65 * 1195) / 10,
                                               rel=1e-3)
    assert down[0].start_in_s == pytest.approx(down[0].deadline_s
                                               - TP.DEFAULT_LEAD_S)
    # a descent that meets the ground goes on level: a square 3 S ahead
    # is reached on the ground after the touchdown
    far = TP.Square("far", LAT0 + 4 * 1195 / 111_320.0, 0.0, 1195.0)
    fl = TP.plan(_at(300.0, 50.0, -10.0), [far], {})
    assert sorted(f.tier for f in fl) == [1, 3]
    # a climb is planned level (a level-off never finds the camera lower)
    assert TP.plan(_at(3_000.0, 0.0, 10.0), [sq], {}) == \
        TP.plan(_at(3_000.0, 0.0), [sq], {})


def _profile():
    """(t, agl_m, groundspeed, vertical) every 5 s: climb to FL350,
    cruise, descend to the ground (speeds ramp over a minute)."""
    out, h, t, v = [], 0.0, 0.0, 80.0
    for v_to, vz, span in ((150.0, 12.0, 900.0), (230.0, 0.0, 300.0),
                           (150.0, -12.0, 900.0), (70.0, 0.0, 60.0)):
        for _ in range(int(span / 5.0)):
            if h <= 0.0 and vz < 0.0:
                vz = 0.0
            out.append((t, h, v, vz))
            v += max(-5.0, min(5.0, v_to - v))
            h = max(0.0, min(10_668.0, h + vz * 5.0))
            t += 5.0
    return out


LAND_S = 25.0                    # a fetch lands 25 s after it falls due


def _fly_profile(vertical=True):
    """Fly :func:`_profile` northbound over a ZL16 field, landing each due
    fetch ``LAND_S`` later (``vertical``: the plan sees the descent).
    Returns (misses, worst texel angle, samples checked, exempt, on_disk):
    a miss is a sample where a square's file is coarser than the tier the
    eye wants at its slant distance; exempt are squares first listed
    already inside or with less than ``LAND_S`` left."""
    prof = _profile()
    dist = [0.0]
    for (t0, _h, v, _vz), (t1, *_r) in zip(prof, prof[1:], strict=False):
        dist.append(dist[-1] + v * (t1 - t0))
    rows = range(-2, int(dist[-1] / (0.8 * S)) + 4)
    squares = [_square_at(e, i * 0.8 * S, f"{e:.0f},{i}")
               for i in rows for e in (0.0, 1.0 * S, -2.5 * S)]
    on_disk, landing, exempt, listed = {}, {}, set(), set()
    worst, misses, checked = 0.0, [], 0
    for (t, h, v, vz), d in zip(prof, dist, strict=True):
        here = TP.Motion(LAT0 + d / 111_320.0, 0.0, h, 0.0, v, h,
                         vz if vertical else 0.0)
        for key, (at, tier) in list(landing.items()):
            if at <= t:
                on_disk[key] = max(on_disk.get(key, 0), tier)
                del landing[key]
        fetches = TP.plan(here, squares, on_disk)
        exempt.update(f.square for f in fetches if f.square not in listed
                      and (f.late or f.deadline_s < LAND_S))
        listed.update(f.square for f in fetches)
        for f in fetches:
            if (f.due or f.late) and f.square not in landing:
                landing[f.square] = (t + LAND_S, f.tier)
        for sq in squares:
            if sq.name in exempt:
                continue
            east, north = TP._offset_m(here, sq)
            slant = math.sqrt(east * east + north * north + h * h)
            tier = on_disk.get(sq.name, 0)
            want = max([k for k in range(1, 4)
                        if slant < TP.CROSSING_S[k] * S] or [0])
            if want > tier:
                misses.append((t, sq.name, want, tier))
            if 0 < want < 3:             # the full file is the finest
                worst = max(worst, TP.texel_angle(tier, S, slant))
                checked += 1
    return misses, worst, checked, exempt, on_disk, len(squares)


def test_clarity_holds_across_climb_cruise_and_descent():
    """The owner's 17:56Z refinement: the same clarity the whole flight.
    At every sample of a climb / cruise / descent every square's file is
    at least the tier the eye wants at its slant distance, so below the
    full file's distance no texel on disk subtends more than the eye
    angle; without the descent in the plan the descent misses."""
    misses, worst, checked, exempt, on_disk, n = _fly_profile()
    assert not misses, misses[:5]
    assert checked > 1000 and len(exempt) < n // 4
    assert {1, 2, 3} <= set(on_disk.values())
    assert worst <= max(TP.EYE_RAD[1:]) * 1.0001
    assert _fly_profile(vertical=False)[0]       # level planning is late


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
