"""Twin of ``tools/flight_schedule_replay.py`` (flight manager / World spec
2026-11-10 §15 "Flight replay", W2): the build-ahead job driven by the
CYYR World pack flight's recorded positions, a fake builder at the
measured times (light 397 s, drape 37 s) and a fake clock.

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
    """Light tiles at 397 s, as flown (157 m/s at 53°N): the 11 World
    tiles X-Plane opened in flight were all swapped in before their first
    open, and no tile was swapped after X-Plane had opened it."""
    result = R.replay(*flight, kind="light")
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


def test_where_light_tiles_stop_keeping_up_and_drapes_do_not(flight):
    """Twice as fast (~610 kt) the light job is late from the first
    column; drapes at 37 s keep up at 2x and 3x."""
    double = R.replay(*flight, kind="light", speed=2.0)
    assert not double["ok"] and "+53-063" in double["late"]
    assert not double["loaded_swaps"]
    for speed in (1.0, 2.0, 3.0):
        drape = R.replay(*flight, kind="drape", speed=speed)
        assert drape["ok"], (speed, drape["late"])


def test_the_cli_prints_and_exits_by_the_verdict(flight, capsys):
    assert R.main(["--speed", "1"]) == 0
    out = capsys.readouterr().out
    assert "as flown: +53-064" in out and "OK" in out
    assert R.main(["--speed", "3"]) == 1
