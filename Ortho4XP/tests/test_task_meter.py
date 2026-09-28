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
    """The pace arithmetic, priced against THIS run's clock (#76).

    This asserted ``remaining == approx(0.8, rel=0.5)`` — a band derived
    from the 0.2 s the sleep ASKS for, times four.  A loaded runner gives
    the sleep back late: macOS CI measured 1.2678 s against a 0.4-1.2 s
    band, so a correctness twin went red for the machine, which is the
    class RULINGS 2026-09-12z names (a wall-clock bar in a correctness
    suite fails under load while every correctness assertion passes).

    The subject is the ARITHMETIC, not the wall time:
    ``active_remaining_seconds`` computes ``(elapsed / done) * (total -
    done)``, so with 2 of 10 units done the answer is exactly ``elapsed *
    4`` whatever the sleep really took.  Measuring the elapsed time this
    run actually saw makes the assertion load-independent AND tighter
    than the old one — 15 % of the real value, not 50 % of a guessed one.
    """
    t0 = time.time()                      # the clock the meter itself uses
    task_meter.begin("insets", 10)
    time.sleep(0.2)
    task_meter.advance("insets", 2)
    remaining = task_meter.active_remaining_seconds()
    elapsed = time.time() - t0
    assert remaining == pytest.approx(elapsed * 4.0, rel=0.15), (
        f"remaining {remaining} is not the pace price of {elapsed} s "
        f"elapsed over 2 of 10 units")
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
