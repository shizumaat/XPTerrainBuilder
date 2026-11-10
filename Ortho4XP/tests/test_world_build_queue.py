"""Twin of the build queue's class and deadline and of the ``profile``
override (``src/o4_engine/build_order.py``, ``src/O4_Build_Profile.py``;
flight manager / World spec 2026-11-10 §8.4, §2.1)."""
from __future__ import annotations

import os
import time
from collections import deque

import O4_Build_Profile as PROFILE
import pytest
from o4_engine import build_order as ORDER
from o4_engine.parallel import ParallelBuildRun
from o4_engine.session import EngineSession


def test_rank_is_class_then_deadline_and_a_plain_press_is_p2():
    assert ORDER.rank("P0", 50.0) < ORDER.rank("P1", 10.0)
    assert ORDER.rank("P1", 10.0) < ORDER.rank("P1", 20.0) < ORDER.rank("P1")
    assert ORDER.rank() == ORDER.rank("P2") < ORDER.rank("P3", 0.0)
    with pytest.raises(ValueError):
        ORDER.rank("P9")


def test_place_keeps_equals_first_in_first_out():
    ranks = {"a": ORDER.rank(), "b": ORDER.rank(), "c": ORDER.rank("P1", 5.0),
             "d": ORDER.rank("P1", 2.0), "e": ORDER.rank("P4")}
    queue: deque = deque()
    for item in "abcde":
        ORDER.place(queue, item, ranks[item], ranks.get)
    assert list(queue) == ["d", "c", "a", "b", "e"]


def test_the_laxity_guard_takes_the_least_slack_under_one_build():
    now = 1000.0
    entries = [("far", now + 5000, 400), ("tight", now + 700, 400),
               ("tighter", now + 500, 400), ("no_deadline", None, 400),
               ("no_estimate", now + 10, 0)]
    assert ORDER.urgent(entries, now) == "tighter"
    assert ORDER.urgent([("far", now + 5000, 400)], now) is None


def test_the_parallel_queue_orders_by_rank_and_lets_the_urgent_jump():
    run = ParallelBuildRun.__new__(ParallelBuildRun)
    run._queue, run._estimates = deque(), {}
    for tile in [(1, 1), (2, 2)]:
        run._queue_tile_locked(tile)                 # the user's presses
    now = time.time()
    run._queue_tile_locked((3, 3), ORDER.rank("P4"))
    run._queue_tile_locked((4, 4), ORDER.rank("P1", now + 9000))
    run._queue_tile_locked((5, 5), ORDER.rank("P1", now + 3000))
    assert list(run._queue) == [(5, 5), (4, 4), (1, 1), (2, 2), (3, 3)]
    # The alternate-class tile now has under one build of slack: next.
    run._priority[(3, 3)] = ORDER.rank("P4", now + 500)
    run._estimates[(3, 3)] = {"vector": 200.0, "mesh": 100.0}   # 450 s high
    run._laxity_first_locked()
    assert run._queue[0] == (3, 3)


def test_the_in_process_queue_orders_by_rank():
    session = EngineSession.__new__(EngineSession)
    session._work_queue = deque()
    items = {}
    for tile, priority in [((1, 1), None), ((2, 2), ORDER.rank("P1", 50.0)),
                           ((3, 3), None), ((4, 4), ORDER.rank("P0", 99.0))]:
        session._note_priority([tile], priority)
        items[tile] = (tile, "BI", 16, "", [])
        session._queue_item_locked(items[tile])
    assert [item[0] for item in session._work_queue] == [
        (4, 4), (2, 2), (1, 1), (3, 3)]


def test_the_light_profile_is_the_cyyr_flights_settings():
    light = PROFILE.profile_settings("light")
    assert light["elevation_level"] == "90" and light["auto_patch"] == "None"
    assert light["airport_elevation_insets"] == "None"
    assert light["imagery_on_demand"] is True
    assert light["placeholder_zl_drop"] == 3
    assert PROFILE.profile_settings("full") == {}
    assert PROFILE.profile_of({"profile": "light"}) == "light"
    assert PROFILE.profile_of({}) == PROFILE.profile_of(None) == "full"
    with pytest.raises(ValueError):
        PROFILE.profile_settings("heavy")


def test_a_profile_lands_on_the_tile_never_in_its_cfg(tmp_path, monkeypatch):
    import O4_Config_Utils as CFG
    import O4_Settings_Model as SM

    tile = CFG.Tile(47, -123, str(tmp_path) + os.sep)
    tile.auto_patch, tile.elevation_level = "ICAO", "auto"
    tile.apply_build_overrides({"profile": "light"})
    assert tile.auto_patch == "None" and tile.elevation_level == "90"
    assert tile.cover_airports_with_highres == "False"
    written = {}
    monkeypatch.setattr(SM, "sparse_tile_values",
                        lambda values, **kw: written.update(values) or {})
    monkeypatch.setattr(SM, "write_tile_cfg", lambda path, out: None)
    tile.write_to_config(str(tmp_path / "t.cfg"))
    assert written["auto_patch"] == "ICAO"
    assert written["elevation_level"] == "auto"


def test_the_session_remembers_a_batchs_overrides_per_tile():
    session = EngineSession.__new__(EngineSession)
    session._tile_overrides = {}
    session._note_overrides([(53, -64)], {"profile": "light"})
    assert session.tile_overrides(53, -64) == {"profile": "light"}
    assert session.tile_overrides(53, -65) == {}


def test_a_light_record_never_predicts_a_full_build():
    """World spec §9: the time model never mixes profiles (a record
    without one is a full build)."""
    from o4_engine import tile_time_model as TTM

    light = {"features": {"zoomlevel": 16, "profile": "light"}}
    old = {"features": {"zoomlevel": 16}}
    for step in ("vector", "imagery"):
        assert not TTM._same_tile_compatible(light, {"zoomlevel": 16}, step)
        assert TTM._same_tile_compatible(
            light, {"zoomlevel": 16, "profile": "light"}, step)
        assert TTM._same_tile_compatible(
            old, {"zoomlevel": 16, "profile": "full"}, step)
