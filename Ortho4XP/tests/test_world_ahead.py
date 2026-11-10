"""Twin of build-ahead's planning without a route and of the CPU share
(``src/O4_World_Ahead.py``, ``src/O4_World_Governor.py``; flight manager /
World spec 2026-11-10 §8.5, §7.5 S3, §10)."""
from __future__ import annotations

import O4_World_Ahead as AHEAD
import O4_World_Governor as GOV
import O4_World_Window as W
import pytest


def test_the_s3_margin_is_005_degrees_or_60_s_whichever_is_more():
    assert AHEAD.margin_km(0.0) == pytest.approx(5.566, abs=1e-3)
    assert AHEAD.margin_km(50.0) == pytest.approx(5.566, abs=1e-3)
    assert AHEAD.margin_km(157.6) == pytest.approx(9.456, abs=1e-3)
    assert AHEAD._margin_s(157.6) == pytest.approx(60.0)
    assert AHEAD.deadline_s(700.0, 157.6) == pytest.approx(
        700.0 - 60.0 - AHEAD.SWAP_S)


def test_entries_along_a_straight_track_match_the_tracker_flown_there():
    """Westbound at 53°N from the CYYR start: the projection names the
    column -063 first, then -064, at the times the same tracker flown
    point by point names them."""
    live = W.WindowTracker()
    live.load(53.30, -60.45)
    entries = AHEAD._track_entries(live, 53.30, -60.45, 270.0, 150.0, 1500.0)
    assert live.cols == {-60}                       # the live one never moves
    first = {t: s for t, s in entries.items() if t[1] == -63}
    assert set(first) == {(52, -63), (53, -63), (54, -63)}
    # 0.20° of longitude at 53°N is 13.4 km: 89 s at 150 m/s.
    assert min(first.values()) == pytest.approx(90.0, abs=AHEAD.STEP_S)
    later = {t for t, s in entries.items() if t[1] == -64}
    assert later and min(entries[t] for t in later) > max(first.values())


def test_a_turn_adds_the_tiles_toward_it():
    tracker = W.WindowTracker()
    tracker.load(53.5, -60.5)
    straight = AHEAD.ahead(tracker, 53.5, -60.5, 270.0, 150.0, 1200.0)
    turning = AHEAD.ahead(tracker, 53.5, -60.5, 270.0, 150.0, 1200.0,
                          turn_deg_s=-2.0)            # turning left: south
    assert set(straight) < set(turning)
    assert all(lat <= 52 for lat, _ in set(turning) - set(straight))
    assert AHEAD.ahead(tracker, 53.5, -60.5, 270.0, 150.0, 1200.0,
                       turn_deg_s=0.2) == straight


def test_parked_the_ring_is_the_next_move_in_every_direction():
    tracker = W.WindowTracker()
    tracker.load(53.30427, -60.447077)              # columns -62..-59
    ring = AHEAD.ring(tracker, 53.30427, -60.447077)
    assert not set(ring) & tracker.window()
    assert {(53, -63), (53, -58), (51, -60), (55, -60)} <= set(ring)
    assert len(ring) == 6 * 5 - 4 * 3
    nearest = min(ring, key=ring.get)
    assert nearest[1] == -63 and ring[nearest] == pytest.approx(13.6, abs=0.2)


def test_flight_and_parked_slots():
    assert GOV.flight_slots(18) == 3                # this Mac: (18-6)//3 -> 3
    assert GOV.flight_slots(8) == 1
    assert GOV.flight_slots(12) == 2
    assert GOV.flight_slots(18, setting=1) == 1
    assert GOV.flight_slots(18, memory_slots=2) == 2
    assert GOV.parked_slots(16) == 14 and GOV.parked_slots(2) == 1


def _feed(gov, start, end, frame_s, building, step=1.0):
    t = start
    while t < end:
        gov.observe(t, frame_s, building)
        t += step


def test_the_guard_gives_a_slot_back_and_returns_it():
    gov = GOV.FrameGovernor("balanced")
    _feed(gov, 0, 60, 0.020, building=False)         # baseline p90 20 ms
    assert gov.baseline == pytest.approx(0.020) and gov.allowed(3) == 3
    _feed(gov, 60, 70, 0.022, building=True)         # +10 %: under 25 %
    assert gov.allowed(3) == 3 and gov.state == "ok"
    _feed(gov, 70, 110, 0.030, building=True)        # +50 %
    assert gov.allowed(3) <= 2 and gov.state == "reduced"
    assert gov.frame_ms() == pytest.approx(30.0)
    _feed(gov, 110, 300, 0.021, building=True)       # back under for long
    assert gov.allowed(3) == 3 and gov.state == "ok"


def test_the_guard_keeps_one_slot_and_fast_never_reduces():
    gov = GOV.FrameGovernor("smooth")
    _feed(gov, 0, 60, 0.020, building=False)
    _feed(gov, 60, 400, 0.040, building=True)
    assert gov.allowed(3) == 1
    fast = GOV.FrameGovernor("fast")
    _feed(fast, 0, 60, 0.020, building=False)
    _feed(fast, 60, 400, 0.040, building=True)
    assert fast.allowed(3) == 3
    with pytest.raises(ValueError):
        GOV.FrameGovernor("turbo")
