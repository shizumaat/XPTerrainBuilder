"""Per-tile clocks (TileClocks, protocol 1.3) — elapsed + own-work
remaining rows beside RunEta, for the activity views' per-tile display.

Pins:
  * the sequential ``_EtaTracker`` row math (queued 0.0 / active live /
    terminal frozen; remaining None without any basis — a dash, never a
    guess);
  * the parallel :func:`per_tile_clock_rows` (same step pricing as the
    wall estimator, summed per tile, never divided by slots);
  * the wire shape via ``serialize_event`` (tuples → lists, None → null).

Hermetic: fake clocks, no builds, no network.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import parallel as PARALLEL  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from o4_engine.events import TileClocks  # noqa: E402
from o4_engine.jsonl import serialize_event  # noqa: E402


def _tracker(monkeypatch, clock):
    monkeypatch.setattr(SESSION.time, "time", lambda: clock[0])
    plan = SESSION.plan_steps(True, True, False)
    return SESSION._EtaTracker(
        [(35, -81), (36, -81)], plan,
        {(35, -81): {"vector": 30.0, "mesh": 10.0, "masks": 5.0,
                     "imagery": 20.0},
         (36, -81): {"vector": 60.0, "mesh": 20.0, "masks": 10.0,
                     "imagery": 40.0}})


def test_sequential_rows_queued_active_and_frozen(monkeypatch):
    clock = [1000.0]
    eta = _tracker(monkeypatch, clock)
    # Both queued: zero elapsed, remaining = the full model estimate.
    rows = {(r[0], r[1]): r for r in eta.tile_rows()}
    assert rows[(35, -81)][2] == 0.0
    assert rows[(35, -81)][3] == 65.0
    assert rows[(36, -81)][3] == 130.0
    assert not rows[(35, -81)][4]

    # First tile runs its vector step for 40 s.
    eta.step_started((35, -81), "vector")
    clock[0] += 40.0
    rows = {(r[0], r[1]): r for r in eta.tile_rows()}
    assert rows[(35, -81)][2] == 40.0
    # Active tile: live current-step pricing + the future steps; the
    # queued sibling keeps its full-model figure untouched.
    assert rows[(35, -81)][3] > 0.0
    assert rows[(36, -81)][2] == 0.0
    assert rows[(36, -81)][3] == 130.0

    # Finish every planned step -> the clock freezes.
    for key in ("vector", "mesh", "masks", "imagery"):
        eta.step_started((35, -81), key)
        clock[0] += 5.0
        eta.step_finished((35, -81), key)
    frozen = {(r[0], r[1]): r for r in eta.tile_rows()}[(35, -81)]
    assert frozen[4] is True
    assert frozen[3] == 0.0
    final = frozen[2]
    clock[0] += 100.0
    assert {(r[0], r[1]): r
            for r in eta.tile_rows()}[(35, -81)][2] == final


def test_sequential_terminal_freezes_failed_tiles(monkeypatch):
    clock = [1000.0]
    eta = _tracker(monkeypatch, clock)
    eta.step_started((35, -81), "vector")
    clock[0] += 12.0
    eta.tile_terminal((35, -81))        # the BuildDone(ok=False) path
    row = {(r[0], r[1]): r for r in eta.tile_rows()}[(35, -81)]
    assert row[4] is True and row[2] == 12.0 and row[3] == 0.0
    # Idempotent — a later duplicate terminal must not restamp.
    clock[0] += 50.0
    eta.tile_terminal((35, -81))
    assert {(r[0], r[1]): r
            for r in eta.tile_rows()}[(35, -81)][2] == 12.0


def test_sequential_no_estimates_reports_dash(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(SESSION.time, "time", lambda: clock[0])
    eta = SESSION._EtaTracker(
        [(10, 10)], SESSION.plan_steps(True, True, False), {(10, 10): {}})
    row = eta.tile_rows()[0]
    assert row[3] is None, "no basis at all must be a dash, not a guess"


def test_requeued_tile_restarts_its_clock(monkeypatch):
    clock = [1000.0]
    eta = _tracker(monkeypatch, clock)
    eta.step_started((35, -81), "vector")
    clock[0] += 30.0
    eta.tile_terminal((35, -81))
    eta.add_tiles([(35, -81)], {(35, -81): {"vector": 30.0}}, ["vector"])
    row = {(r[0], r[1]): r for r in eta.tile_rows()}[(35, -81)]
    assert row[2] == 0.0 and row[4] is False


def test_parallel_rows_price_like_the_wall_estimator():
    now = 5000.0
    estimates = {(35, -81): {"vector": 100.0, "imagery": 50.0},
                 (36, -81): {"vector": 80.0, "imagery": 40.0},
                 (37, -81): {}}
    programs = {(35, -81): ["vector", "imagery"],
                (36, -81): ["vector", "imagery"],
                (37, -81): ["vector"]}
    rows = {(r[0], r[1]): r for r in PARALLEL.per_tile_clock_rows(
        estimates, programs,
        queued_tiles=[(36, -81), (37, -81)],
        next_step_index={(35, -81): 0},
        in_flight_steps={((35, -81), "vector"): now - 40.0},
        now=now,
        live_step_remaining={((35, -81), "vector"): (25.0, now - 2.0)},
        first_started={(35, -81): now - 40.0},
        final_elapsed={})}
    # Active tile: live child report (25 - 2 aged) + future imagery.
    assert rows[(35, -81)][2] == 40.0
    assert abs(rows[(35, -81)][3] - (23.0 + 50.0)) < 1e-6
    # Queued tile: its own full program, NOT divided by slots.
    assert rows[(36, -81)][2] == 0.0
    assert rows[(36, -81)][3] == 120.0
    # No estimates anywhere: the dash.
    assert rows[(37, -81)][3] is None


def test_parallel_final_elapsed_freezes_rows():
    rows = {(r[0], r[1]): r for r in PARALLEL.per_tile_clock_rows(
        {}, {(35, -81): ["vector"]}, [], {}, {}, 9000.0, {},
        {(35, -81): 8000.0}, {(35, -81): 123.4})}
    assert rows[(35, -81)] == (35, -81, 123.4, 0.0, True)


def test_tile_clocks_wire_shape():
    event = TileClocks(rows=((35, -81, 12.3, 45.6, False),
                             (36, -81, 0.0, None, False)))
    payload = serialize_event(event)
    assert payload["event"] == "TileClocks"
    assert payload["rows"] == [[35, -81, 12.3, 45.6, False],
                               [36, -81, 0.0, None, False]]
