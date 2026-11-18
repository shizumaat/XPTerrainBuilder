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


# ---------------------------------------------------- owner 2026-11-17 (a)/(b)

def test_backfill_queues_only_favourite_and_recent_airports(monkeypatch):
    """RULINGS 2026-11-17v (a): of the pack's full tiles beside a
    placeholder, only those of a favourite tile or a recent place are
    queued; every other built airport waits for the aircraft."""
    from o4_engine import world_commands as WORLD
    kinds = {(lat, lon): "placeholder" for lat in range(-46, 62)
             for lon in range(-72, 20)}
    full = [(59, 17), (-42, 147), (-41, -70), (47, 12), (10, 10)]
    kinds.update({t: "full" for t in full})
    queued = []
    monkeypatch.setattr(WORLD, "managed", lambda d: True)
    monkeypatch.setattr(WORLD, "pack_dir", lambda d: d)
    monkeypatch.setattr(WORLD, "write_log", lambda r: None)
    monkeypatch.setattr(SPAWN.WP, "world_tiles", lambda d: kinds)
    monkeypatch.setattr(SPAWN, "start",
                        lambda la, lo, d: queued.append((la, lo)) or True)
    recent = [("", POINT[1], POINT[2]), ("HECA", 30.11, 31.41)]
    out = SPAWN.backfill("pack", favourites={(47, 12)}, recent=recent)
    assert sorted(queued) == [(47, 12), (59, 17)]
    assert out == ["+47+012", "+59+017"]


def test_a_tiles_points_are_its_favourites_or_near_a_recent_place():
    from o4_engine import world_spawn_recent as RECENT
    points = [POINT, ("FAR", 59.2, 17.2), ("ESSA", 59.9, 17.9)]
    assert RECENT.allowed((59, 17), points, favourites={(59, 17)},
                          recent=[]) == points
    near = [("", POINT[1] + 0.02, POINT[2] - 0.03), ("essa", 0.0, 0.0)]
    assert RECENT.allowed((59, 17), points, favourites=set(),
                          recent=near) == [POINT, ("ESSA", 59.9, 17.9)]
    assert RECENT.allowed((59, 17), points, favourites=set(), recent=[]) == []


def test_recent_places_are_ground_notes_and_flight_ends_of_30_days(tmp_path):
    import json

    from o4_engine import world_spawn_recent as RECENT
    now = 1_800_000_000.0
    history = str(tmp_path / "spawns.json")
    assert RECENT.note(59.651, 17.918, now - 86400, path=history)
    assert not RECENT.note(59.652, 17.919, now - 86000, path=history)  # same
    assert RECENT.note(10.0, 10.0, now - 40 * 86400, path=history)   # old
    flights = tmp_path / "Flights"
    flights.mkdir()

    def flight(name, created, arrived=None):
        (flights / (name + ".json")).write_text(json.dumps({
            "id": name, "source": {}, "created_at": created,
            "arrived_at": arrived,
            "origin": {"ident": name[:4], "lat": 30.1, "lon": 31.4},
            "destination": {"ident": name[4:], "lat": 25.3, "lon": 51.6}}))
    flight("HECAOTHH", "2027-01-14T00:00:00Z", "2027-01-14T05:00:00Z")
    flight("KMRYKFAT", "2026-11-01T00:00:00Z")                      # old
    got = RECENT.places(now, history=history, flights=str(flights))
    assert sorted(p[0] for p in got) == ["", "HECA", "OTHH"]
    assert ("", 59.65, 17.92) in got


def test_the_work_waits_while_the_app_builds_or_xplane_runs():
    """RULINGS 2026-11-17v (b): paused while a reason holds, resumed
    after; one log line each; ``_run`` holds before every drape."""
    from o4_engine import world_yield as YIELD
    reasons = ["app build", "X-Plane", ""]
    slept, lines = [], []
    waited = YIELD.wait(lines.append, why=lambda: reasons.pop(0),
                        sleep=slept.append, poll_s=5.0)
    assert len(slept) == 2 and waited >= 0.0
    assert lines[0] == {"spawn_window": "paused", "reason": "app build"}
    assert lines[1]["spawn_window"] == "resumed"
    assert YIELD.wait(lines.append, why=lambda: "") == 0.0 and len(lines) == 2

    held = []
    kinds = {t: "placeholder" for t in SPAWN.spawn_set(POINT[1], POINT[2])}
    counts = SPAWN._run((59, 17), [POINT], kind_of=kinds.get,
                        drape=lambda t, c: True, publish=lambda t: "swapped",
                        hold=lambda: held.append(1))
    assert len(held) == counts["wanted"] == counts["draped"]


def test_an_app_build_session_and_xplane_are_the_reasons(monkeypatch):
    from o4_engine import world_yield as YIELD
    from o4_engine import xplane_root
    running = [False]
    monkeypatch.setattr(xplane_root, "xplane_running", lambda: running[0])
    monkeypatch.setattr(YIELD, "XPLANE_EVERY_S", 0.0)
    session = type("S", (), {"tiles": set(),
                             "building_tiles": lambda self: self.tiles})()
    YIELD.watch(session)
    try:
        assert YIELD.reason() == ""
        session.tiles = {"+47+012"}
        assert YIELD.reason() == "app build"
        session.tiles = set()
        running[0] = True
        assert YIELD.reason() == "X-Plane"
        running[0] = False
        assert YIELD.reason() == ""
    finally:
        YIELD.watch(None)


def test_another_sessions_app_reservation_is_an_app_build(monkeypatch):
    """The ledger's holders (O4_Machine_Memory): another session's app
    reservation pauses the work; this session's own does not."""
    import O4_Machine_Memory as MEMORY
    from o4_engine import world_yield as YIELD
    from o4_engine import xplane_root
    monkeypatch.setattr(xplane_root, "xplane_running", lambda: False)
    monkeypatch.setattr(YIELD, "XPLANE_EVERY_S", 0.0)
    mine = MEMORY.session_id()
    rows = {}
    snap = type("Snap", (), {"sessions": rows, "wants": []})()
    monkeypatch.setattr(MEMORY, "snapshot", lambda: snap)
    YIELD.watch(None)
    rows[mine] = {"role": "app"}
    assert YIELD.reason() == ""
    rows["other"] = {"role": "lane"}
    assert YIELD.reason() == ""
    rows["other"] = {"role": "app"}
    assert YIELD.reason() == "app build"
