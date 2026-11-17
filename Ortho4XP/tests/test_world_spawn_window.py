"""Twin of ``src/o4_engine/world_spawn_window.py`` (#2142 part 1): the
spawn set of a point and of a tile, the plan's order and cores, and the
pre-drape run through fakes (no network, no pack)."""
from __future__ import annotations

import threading

from o4_engine import world_spawn_window as SPAWN
from o4_engine.build_share import BuildShare

#: A parked aircraft of the 2026-11-17 flight (fixture data, #2142).
POINT = ("APT", 59.65181, 17.91845)


def test_the_spawn_set_of_a_point_is_every_window_it_allows():
    """12 tiles away from the lines (columns 16..19, rows 58..60); 0.5
    deg into a tile two column boundaries are possible (5 columns); at
    lat x.95 two rows (4 rows)."""
    tiles = SPAWN.spawn_set(POINT[1], POINT[2])
    assert {t[1] for t in tiles} == {16, 17, 18, 19}
    assert {t[0] for t in tiles} == {58, 59, 60}
    assert len({t[1] for t in SPAWN.spawn_set(59.65, 17.5)}) == 5
    assert len({t[0] for t in SPAWN.spawn_set(59.95, 17.9)}) == 4


def test_a_tiles_set_is_the_union_over_its_airports_and_at_most_25():
    tile = (59, 17)
    one = SPAWN._tile_spawn_set(tile, [POINT])
    assert tile not in one and len(one) == 11
    corners = [("A", 59.02, 17.02), ("B", 59.98, 17.98), ("C", 59.5, 17.5)]
    many = SPAWN._tile_spawn_set(tile, corners)
    assert one <= SPAWN._tile_spawn_set(tile, [POINT] + corners)
    assert len(many) + 1 <= 25


def test_the_plan_takes_placeholders_nearest_first_with_the_airports_core():
    kinds = {t: "placeholder" for t in SPAWN.spawn_set(POINT[1], POINT[2])}
    kinds[(59, 17)] = "full"
    kinds[(60, 16)] = "full"
    plan = SPAWN._plan((59, 17), [POINT], kinds.get)
    tiles = [t for t, _core in plan]
    assert len(tiles) == 10 and (60, 16) not in tiles
    assert tiles[0] in {(60, 17), (59, 18)}            # touching the airport
    cores = dict(plan)
    assert cores[(59, 18)] == (POINT[1], POINT[2])     # 0.04 deg east of it
    assert cores[(60, 17)] is None                     # 0.35 deg: Quick only
    assert cores[(58, 19)] is None


def test_run_drapes_two_at_a_time_through_the_share_and_logs_each():
    kinds = {t: "placeholder" for t in SPAWN.spawn_set(POINT[1], POINT[2])}
    kinds[(59, 17)] = "full"
    lock, live, peak, published, lines = threading.Lock(), [0], [0], [], []

    def drape(tile, core):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        with lock:
            live[0] -= 1
        return tile != (58, 16)

    def publish(tile):
        published.append(tile)
        kinds[tile] = "drape"
        return "swapped"

    share = BuildShare()
    share.take("track", (58, 19), "drape")             # track mode has it
    counts = SPAWN._run((59, 17), [POINT], kind_of=kinds.get, drape=drape,
                       publish=publish, share=share, log=lines.append)
    assert counts["wanted"] == 11
    assert counts["draped"] == 9 and counts["failed"] == 1
    assert counts["skipped"] == 1 and (58, 19) not in published
    assert peak[0] <= SPAWN.AT_ONCE
    assert lines[-1]["done"] and len(lines) == 11     # the skipped: none


def test_nothing_is_draped_under_the_disk_floor():
    kinds = {t: "placeholder" for t in SPAWN.spawn_set(POINT[1], POINT[2])}
    counts = SPAWN._run((59, 17), [POINT], kind_of=kinds.get,
                       drape=lambda t, c: True, publish=lambda t: "swapped",
                       floor_ok=lambda: False)
    assert counts["draped"] == 0 and counts["skipped"] == counts["wanted"]
