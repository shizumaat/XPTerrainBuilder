"""Twin of ``tools/flight_schedule_replay.py`` (flight manager / World spec
2026-11-10 §15 "Flight replay", W2): the build-ahead job driven by the
CYYR World pack flight's recorded positions, a fake builder at the
measured drape times (and a 397 s tile, the retired light build's) and a
fake clock.

Fixtures: ``tests/fixtures/world/cyyr_world_flight.replay.json`` (W0's
extract: positions + every ``.dsf`` X-Plane opened) and
``cyyr_world_kit.json`` (the kit's World pack: its 30 placeholder tiles,
the user's own +53-061 it skipped, and the as-flown build of +53-064,
from the kit's ``world_log.jsonl``)."""
from __future__ import annotations

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))

import flight_schedule_replay as R  # noqa: E402


@pytest.fixture(scope="module")
def flight():
    with open(R.FIXTURE, encoding="utf-8") as f:
        flight = json.load(f)
    with open(R.KIT, encoding="utf-8") as f:
        kit = json.load(f)
    return flight, kit


def test_every_world_tile_entered_was_published_before_it_loaded(flight):
    """Slow tiles (397 s, the retired light build's time) as flown (157
    m/s at 53°N): the 11 World tiles X-Plane opened in flight were all
    swapped in before their first open, and no tile was swapped after
    X-Plane had opened it."""
    result = R.replay(*flight, build_s=397.0)
    assert result["ok"], result
    assert len(result["tiles"]) == 11
    assert all(row["margin_s"] > 0 for row in result["tiles"])
    assert not result["loaded_swaps"]
    assert result["flight_slots"] == 3 and result["parked_slots"] == 14
    margins = {row["tile"]: row["margin_s"] for row in result["tiles"]}
    # The tightest: the first column, built from the parked start.
    assert min(margins.values()) == margins["+54-063"] > 30


def test_as_flown_the_on_the_fly_tile_had_four_minutes_to_spare(flight):
    flown = R.as_flown(*flight)
    assert flown["tile"] == "+53-064"
    assert flown["swapped_s"] - flown["build_start_s"] == pytest.approx(397)
    assert flown["margin_s"] == pytest.approx(250, abs=1)


def test_where_slow_tiles_stop_keeping_up_and_drapes_do_not(flight):
    """Twice as fast (~610 kt) a 397 s tile is late from the first
    column; drapes keep up at 1x, 2x and 3x: the measured 512 px drape
    and one held to the water wait (``WATER_WAIT_S``, RULINGS
    2026-11-11j)."""
    from o4_engine import world_job_run as RUN
    double = R.replay(*flight, build_s=397.0, speed=2.0)
    assert not double["ok"] and "+53-063" in double["late"]
    assert not double["loaded_swaps"]
    for speed in (1.0, 2.0, 3.0):
        for build_s in (None, RUN.WATER_WAIT_S + 10.0):
            drape = R.replay(*flight, build_s=build_s, speed=speed)
            assert not drape["loaded_swaps"]
            if speed == 3.0 and build_s is not None:
                # #2142: the window's held placeholders now take parked
                # slots the ring had; at 3x (under a minute parked) with
                # the water wait the first column after takeoff is late
                assert len(drape["late"]) <= 3, drape["late"]
                continue
            assert drape["ok"], (speed, build_s, drape["late"])


def test_the_cli_prints_and_exits_by_the_verdict(flight, capsys):
    assert R.main(["--speed", "1"]) == 0
    out = capsys.readouterr().out
    assert "as flown: +53-064" in out and "OK" in out
    assert R.main(["--speed", "3", "--build-s", "397"]) == 1


ESSA = os.path.join(R.FIXTURES, "essa_20261117.replay.json")


@pytest.fixture(scope="module")
def held_fixture():
    with open(ESSA, encoding="utf-8") as f:
        return json.load(f)


def test_held_placeholders_are_draped_and_offered_once_on_the_ground(
        held_fixture):
    """#2142 bar 1: the 2026-11-17 follow-log flight (16:08:31-16:30:46Z,
    the aircraft never left its first window, 10 of its 12 tiles
    placeholders).  All 10 dispatched at the first (on-ground) position,
    all swapped; exactly one reload offer, on the ground; none in the
    air; no swap of a held tile holding real files."""
    result = R.replay_held(held_fixture)
    assert result["held_placeholders"] == 10
    assert all(r["dispatched_s"] == 0.0 for r in result["tiles"])
    assert result["swapped"] == 10
    assert result["offers_ground"] == 1 and result["offers_air"] == 0
    assert not result["real_swaps"]
    assert R.held_ok(result)


def test_with_the_spawn_window_predraped_nothing_is_built_or_offered(
        held_fixture):
    """#2142 bar 2: part 1 ran when the airport tile was built: no
    in-window build, no offer."""
    result = R.replay_held(held_fixture, predrape=True)
    assert result["held_placeholders"] == 0
    assert not result["window_builds"]
    assert result["offers_ground"] == result["offers_air"] == 0
    assert R.held_ok(result)


def test_the_cli_replays_a_held_fixture(capsys):
    assert R.main([ESSA, "--held"]) == 0
    assert "reload offers on the ground 1, in the air 0" in (
        capsys.readouterr().out)
