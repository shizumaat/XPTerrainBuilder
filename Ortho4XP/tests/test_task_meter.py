"""Task meter: count-paced phase pricing and its integration into the
session ETA floor and the parallel scheduler's live-estimate harvest
(headless, no network)."""

import sys
import time

import pytest

sys.path.insert(0, "src")

from o4_engine import parallel, session, task_meter


@pytest.fixture(autouse=True)
def _clean_meter():
    task_meter._reset_for_tests()
    yield
    task_meter._reset_for_tests()


def test_no_active_phase_no_estimate():
    assert task_meter.active_remaining_seconds() is None


def test_unpaced_phase_without_prediction_offers_no_basis():
    task_meter.begin("insets", 10)
    assert task_meter.active_remaining_seconds() is None


def test_pace_prices_remaining_units():
    task_meter.begin("insets", 10)
    time.sleep(0.2)
    task_meter.advance("insets", 2)
    remaining = task_meter.active_remaining_seconds()
    # 2 units in ~0.2 s -> ~0.1 s/unit -> ~0.8 s for the other 8.
    assert remaining == pytest.approx(0.8, rel=0.5)
    task_meter.end("insets")
    assert task_meter.active_remaining_seconds() is None


def test_prediction_prices_phase_before_first_unit():
    task_meter.begin("insets", 4, predicted_seconds=100.0)
    remaining = task_meter.active_remaining_seconds()
    assert remaining == pytest.approx(100.0, abs=1.0)


def test_overrun_prediction_decays_not_expires():
    task_meter.begin("insets", 4, predicted_seconds=0.05)
    time.sleep(0.2)
    remaining = task_meter.active_remaining_seconds()
    # Past the prediction: half the overrun, never zero-forever.
    assert 0.0 < remaining < 0.2


def test_zero_total_units_stays_out():
    task_meter.begin("empty", 0)
    assert task_meter.active_remaining_seconds() is None


def test_advance_caps_at_total():
    task_meter.begin("insets", 3)
    task_meter.advance("insets", 7)
    # Fully complete -> zero remaining, not negative.
    assert task_meter.active_remaining_seconds() == pytest.approx(0.0)


def test_slowest_phase_wins():
    task_meter.begin("fast", 2)
    task_meter.begin("slow", 100)
    time.sleep(0.1)
    task_meter.advance("fast", 1)
    task_meter.advance("slow", 1)
    remaining = task_meter.active_remaining_seconds()
    # slow: ~0.1 s/unit * 99 left dominates fast's single unit.
    assert remaining > 5.0


def test_counted_phase_floors_current_step_remaining():
    tracker = session._EtaTracker(
        [(0, 0)], [("vector", 0.0, 1.0)], {(0, 0): {"vector": 1.0}})
    tracker.step_started((0, 0), "vector")
    task_meter.begin("insets", 10)
    time.sleep(0.2)
    task_meter.advance("insets", 1)
    remaining = tracker._current_step_remaining()
    # ~0.2 s/unit * 9 units left >> the 1 s model estimate.
    assert remaining > 1.0


def test_parallel_estimator_prefers_live_child_report():
    now = time.time()
    estimates = {(0, 0): {"vector": 100.0}}
    programs = {(0, 0): ("vector",)}
    live = {((0, 0), "vector"): (400.0, now)}
    with_live = parallel.estimate_remaining_wall_seconds(
        estimates, programs, [], {(0, 0): 0},
        {((0, 0), "vector"): now - 10.0}, now, 1, live)
    without = parallel.estimate_remaining_wall_seconds(
        estimates, programs, [], {(0, 0): 0},
        {((0, 0), "vector"): now - 10.0}, now, 1)
    assert with_live == pytest.approx(400.0, abs=1.0)
    assert without == pytest.approx(90.0, abs=1.0)


def test_parallel_estimator_distrusts_stale_live_report():
    now = time.time()
    estimates = {(0, 0): {"vector": 100.0}}
    programs = {(0, 0): ("vector",)}
    stale = {((0, 0), "vector"): (400.0, now - 60.0)}
    remaining = parallel.estimate_remaining_wall_seconds(
        estimates, programs, [], {(0, 0): 0},
        {((0, 0), "vector"): now - 10.0}, now, 1, stale)
    assert remaining == pytest.approx(90.0, abs=1.0)
