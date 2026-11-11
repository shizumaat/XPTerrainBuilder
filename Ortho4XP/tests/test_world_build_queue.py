"""Twin of the build queue's class and deadline
(``src/o4_engine/build_order.py``; flight manager / World spec 2026-11-10
§8.4).  The ``light`` build profile is retired (spec §17, RULINGS
2026-11-11j): its old time records never predict a build."""
from __future__ import annotations

import os
import time
from collections import deque

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


def test_profile_is_no_build_override_any_more(tmp_path):
    import O4_Config_Utils as CFG

    assert "profile" not in CFG.BUILD_OVERRIDE_KEYS
    tile = CFG.Tile(47, -123, str(tmp_path) + os.sep)
    tile.auto_patch, tile.elevation_level = "ICAO", "auto"
    tile.apply_build_overrides({"profile": "light"})
    assert tile.auto_patch == "ICAO" and tile.elevation_level == "auto"


def test_a_light_record_never_predicts_a_full_build():
    """A record of the retired light profile never predicts a build (a
    record without a profile is a normal build)."""
    from o4_engine import tile_time_model as TTM

    light = {"features": {"zoomlevel": 16, "profile": "light"}}
    old = {"features": {"zoomlevel": 16}}
    for step in ("vector", "imagery"):
        assert not TTM._same_tile_compatible(light, {"zoomlevel": 16}, step)
        assert TTM._same_tile_compatible(old, {"zoomlevel": 16}, step)
