"""Twins for #2037: the follow job beside a World drape run.

Observed on 2026-11-13 (CYEG, 1.0.506, 2,300 m above Edmonton at 160 m/s,
twelve Bing drape tiles fetching in the engine beside an Arc follower):
the follower landed ~4 squares per 75-163 s, and each batch was counted
44-176 s after it landed.  The tick reread every index row (215,209, one
``sqlite3`` step each: every step releases and re-takes the GIL) and
measured the storage floor (a ``stat`` per placeholder) on its own
thread; beside threads that hold the GIL each re-take waits its turn
(measured on that index: 5,000 rows 0.02 s idle, 15 s beside two busy
Python threads).

The rules these twins hold:

* the camera's requests go FIRST in a server's session budget
  (``O4_Machine_Slots.net_priority``): while one waits, no other request
  takes a slot of that class, and the class limit is unchanged;
* the async fetcher's budget carries its caller's priority onto the loop
  thread; a worker thread started under it carries it too;
* the house (``imagery_follow_house``) rereads, measures and writes near
  rows on its own thread: a slow reread never holds the tick; the rows
  the job landed after a snapshot's read began stay the job's;
* ``INDEX.all_rows`` reads exactly what ``INDEX.rows`` reads;
* the replay (``tools/follow_contention_replay.py``) of a drape run and
  the follower on one server: the follower's share with its priority.
"""
from __future__ import annotations

import os
import threading
import time
import types

import O4_Imagery_OnDemand_Index as INDEX
import O4_Machine_Slots as S
import pytest
from o4_engine import imagery_follow as FOLLOW
from o4_engine import imagery_follow_house as HOUSE
from test_imagery_follow import REPLAY, Clock, FakeLander, _index_rows, _settle

TOOLS = os.path.join(os.path.dirname(__file__), "..", "tools")


@pytest.fixture()
def session(tmp_path, monkeypatch):
    """A slot session of the test's own."""
    monkeypatch.delenv(S.ENV_DIR, raising=False)
    monkeypatch.setenv(S.ENV_CAPACITY, "4")
    monkeypatch.setenv(S.ENV_UNGATED, "1")
    yield
    monkeypatch.delenv(S.ENV_DIR, raising=False)


# --- the camera's requests go first --------------------------------------


def test_a_waiting_priority_request_takes_the_next_free_slot(session):
    name = "net:priority.test"
    other = S.try_take_class(name, 1, 1)              # a drape holds it
    assert other.count == 1
    assert S.try_take_class(name, 1, 1, priority=True).count == 0
    other.release()                                   # the slot comes free
    assert S.try_take_class(name, 1, 1).count == 0    # the drape waits
    mine = S.try_take_class(name, 1, 1, priority=True)
    assert mine.count == 1
    mine.release()
    time.sleep(S.DEMAND_TTL_S + 0.1)                  # no camera demand now
    again = S.try_take_class(name, 1, 1)
    assert again.count == 1
    again.release()


def test_the_flag_follows_the_thread_and_its_workers(session):
    seen = []
    with S.net_priority():
        assert S.has_net_priority()
        task = S.carry_net_priority(lambda: seen.append(S.has_net_priority()))
        worker = threading.Thread(target=task)
        worker.start()
        worker.join()
        bare = threading.Thread(target=lambda: seen.append(S.has_net_priority()))
        bare.start()
        bare.join()
    assert not S.has_net_priority()
    assert seen == [True, False]
    assert S.carry_net_priority(len) is len           # no flag: no wrapper


def test_the_async_budget_carries_the_callers_priority(session):
    import O4_Imagery_Async as FETCH_ASYNC
    request = types.SimpleNamespace(url="http://async.test:81/1/2/3.jpg")
    name = S.net_class(request.url)
    held = S.try_take_class(name, 1, 1)
    low, high = FETCH_ASYNC._server_budget(1), FETCH_ASYNC._server_budget(1, True)
    assert high(request) is None                      # refused: marks demand
    held.release()
    assert low(request) is None                       # the camera's turn
    slot = high(request)
    assert slot is not None and slot.count == 1
    slot.release()


def test_a_drape_run_yields_to_the_camera_and_the_limit_holds(session):
    """Six drape threads keep a 4-slot class full; the camera's thread asks
    for 20 requests: with its priority it waits for none of theirs, and the
    class never has more than 4 requests in flight."""
    name, limit = "net:share.test", 4
    flight, peak, guard = [0], [0], threading.Lock()
    stop = threading.Event()

    def request(seconds):
        with S.hold_class(name, limit, poll_s=0.005) as held:
            assert held.count == 1
            with guard:
                flight[0] += 1
                peak[0] = max(peak[0], flight[0])
            time.sleep(seconds)
            with guard:
                flight[0] -= 1

    def drape():
        while not stop.is_set():
            request(0.02)

    def camera(out, priority):
        t0 = time.monotonic()
        for _ in range(20):
            if priority:
                with S.net_priority():
                    request(0.02)
            else:
                request(0.02)
        out.append(time.monotonic() - t0)

    drapes = [threading.Thread(target=drape, daemon=True) for _ in range(6)]
    for thread in drapes:
        thread.start()
    time.sleep(0.2)
    timed = {}
    for priority in (False, True):
        out = []
        cam = threading.Thread(target=camera, args=(out, priority))
        cam.start()
        cam.join(60)
        timed[priority] = out[0]
    stop.set()
    for thread in drapes:
        thread.join(5)
    assert peak[0] <= limit
    assert timed[True] < timed[False]


# --- the house: the index work off the tick --------------------------------


def test_all_rows_reads_what_rows_reads(tmp_path):
    index_path, _ = _index_rows(tmp_path)
    conn = INDEX.open_index(index_path)
    INDEX.upsert(conn, {"tile": "+61-136", "name": "1_2_Arc16.dds",
                        "centre_lat": 61.5, "centre_lon": -135.5,
                        "load_size_m": 4900.0, "fetched_at": 1794541700.0991})
    assert INDEX.all_rows(conn) == INDEX.rows(conn)
    conn.close()


class _Reader:
    """Flight 2's positions at the test clock's time."""
    resets, loading = 0, False

    def __init__(self, clock):
        self.clock = clock

    def read(self):
        pos = [p for p in REPLAY["pos"] if p[0] <= self.clock.t] or REPLAY["pos"][:1]
        _t, lat, lon, alt, _gs = pos[-1]
        return {"lat": lat, "lon": lon, "elev_m": alt, "agl_m": 300.0}


def _times(n, start=0):
    return [p[0] for p in REPLAY["pos"][start:start + n]]


def test_a_slow_reread_never_holds_the_tick(tmp_path, monkeypatch):
    """The house's reread takes 3 s (beside a drape run it took minutes):
    the job ticks on, lands, and takes the rows when they come, keeping
    what it landed after the read began."""
    index_path, _ = _index_rows(tmp_path)
    clock = Clock()
    job = FOLLOW.FollowJob(lambda e: None, reader=_Reader(clock),
                           lander=FakeLander(), index_path=index_path,
                           clock=clock, cap_bytes=0, log_path=None)
    job.open()
    real, gate = HOUSE._read_rows, threading.Event()

    def slow(conn):
        rows = real(conn)
        gate.wait(10)
        return rows
    monkeypatch.setattr(HOUSE, "_read_rows", slow)
    job.house.start()
    try:
        times = _times(41)
        clock.t = times[0]
        job.tick()
        job.house.want_rows()                # the reread starts and waits
        time.sleep(0.3)
        longest = 0.0
        for t in times[1:]:
            clock.t = t
            t0 = time.monotonic()
            job.tick()
            longest = max(longest, time.monotonic() - t0)
            time.sleep(0.01)
        landed = {lnd["square"] for lnd in job.landings}
        assert landed and longest < 1.0
        gate.set()                           # the stale read lands now
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and job.house._snapshot is None:
            time.sleep(0.05)
        job.tick()
        for key in landed:                   # the job's rows, not the read's
            assert job._rows[key]["state"] == "upgraded"
    finally:
        gate.set()
        job.close()


def _commits(conn) -> list:
    """Every commit on ``conn`` from now on: a ``COMMIT``, or a write made
    outside a transaction (autocommit: its own commit)."""
    seen = []

    def trace(sql):
        verb = sql.split(None, 1)[0].upper()
        if verb == "COMMIT" or (verb in ("UPDATE", "INSERT", "DELETE",
                                         "REPLACE") and not conn.in_transaction):
            seen.append(verb)
    conn.set_trace_callback(trace)
    return seen


def test_a_tick_commits_its_index_writes_once(tmp_path):
    """#2037, the windows-latest red: a tick's 0-12 index writes (the
    landings harvested, the fetches dispatched, the late marks) were each
    an autocommit -- a disk flush apiece.  They go in ONE transaction: at
    most one commit a tick, whatever it wrote, and the index holds every
    landing the job counted."""
    index_path, _ = _index_rows(tmp_path)
    clock = Clock()
    job = FOLLOW.FollowJob(lambda e: None, reader=_Reader(clock),
                           lander=FakeLander(), index_path=index_path,
                           clock=clock, cap_bytes=0, log_path=None)
    job.open()
    job.house.start()                   # its writes on its own connection
    writes, commits = [], _commits(job._conn)
    real = job._commit

    def counted():
        writes.append(len(job._writes))
        real()
    job._commit = counted
    most = 0
    try:
        for t in _times(40):
            clock.t = t
            before = len(commits)
            writes.clear()
            job.tick()
            assert len(commits) - before <= 1, (writes, commits[before:])
            most = max(most, sum(writes))
            _settle(job)                    # the landings harvested next
        assert most >= 2 and job.counts["landed"] >= 2
    finally:
        job.close()
    conn = INDEX.open_index(index_path)
    landed = {lnd["square"] for lnd in job.landings}
    for key in landed:
        tile, name = key.split("/", 1)
        assert INDEX.get(conn, tile, name)["state"] == "upgraded"
    conn.close()


class _HeldLander(FakeLander):
    """Lands when ``gate`` opens; ``from_source``: every row lands from
    a mounted source (or none)."""

    def __init__(self, sourced):
        super().__init__()
        self.gate, self.sourced = threading.Event(), sourced

    def __call__(self, row, tier):
        self.gate.wait(10)
        return super().__call__(row, tier)

    def from_source(self, row):
        return self.sourced


@pytest.mark.parametrize("sourced", [False, True])
def test_a_landing_from_a_source_takes_no_fetch_slot(tmp_path, sourced):
    """#2037: ThunderBlade landings (a built tile's full DDS on a mounted
    volume) queued behind the network's slots.  One download slot: a
    downloaded square holds it; squares landing from their source start
    beside it, up to the workers."""
    import O4_Imagery_Fetch_Slots as SLOTS
    index_path, _ = _index_rows(tmp_path)
    clock = Clock()
    slots = SLOTS.FetchSlots(max_slots=4)
    slots.update = lambda buffer, now: slots.slots      # pinned at 1
    lander = _HeldLander(sourced)
    job = FOLLOW.FollowJob(lambda e: None, reader=_Reader(clock),
                           lander=lander, index_path=index_path, clock=clock,
                           cap_bytes=0, log_path=None, slots=slots)
    job.open()
    try:
        most = 0
        for t in _times(12):
            clock.t = t
            job.tick()
            most = max(most, len(job._inflight))
        assert most == (4 if sourced else 1)
    finally:
        lander.gate.set()
        job.close()


def test_a_landing_starts_when_it_is_submitted(tmp_path):
    """#2037 attribution: on the owner's CYEG flight (1.0.506) source
    landings read 29-163 s, every square of a batch landing within 0.1 s
    of the others whatever its tier -- the tick's work BEFORE its dispatch
    (the reread, then on the tick) was counted in them: ``started`` was
    the tick's start.  It is the submit."""
    index_path, _ = _index_rows(tmp_path)
    clock = Clock()
    lander = _HeldLander(False)
    job = FOLLOW.FollowJob(lambda e: None, reader=_Reader(clock),
                           lander=lander, index_path=index_path, clock=clock,
                           cap_bytes=0, log_path=None)
    job.open()
    real = job._plan

    def slow(now, planner=True):
        clock.t += 50.0                     # the tick's work before dispatch
        return real(now, planner)
    job._plan = slow
    try:
        for t in _times(12):
            clock.t = t
            tick_start = t
            job.tick()
            if job._inflight:
                break
        assert job._inflight
        for item in job._inflight.values():
            assert item.started == tick_start + 50.0
    finally:
        lander.gate.set()
        job.close()


def test_the_sweep_holds_the_dispatch(tmp_path, monkeypatch):
    """While the house's sweep downgrades, the tick starts no fetch."""
    index_path, _ = _index_rows(tmp_path)
    clock = Clock()
    lander = FakeLander()
    job = FOLLOW.FollowJob(lambda e: None, reader=_Reader(clock),
                           lander=lander, index_path=index_path, clock=clock,
                           cap_bytes=0, log_path=None)
    job.open()
    times = _times(7)
    with job.house.dispatch_guard:
        for t in times[:6]:
            clock.t = t
            job.tick()
        assert not lander.calls and not job.last_dispatched
    clock.t = times[6]
    job.tick()
    assert job.last_dispatched
    job.close()


# --- the replay: a drape run and the follower on one server ---------------


def test_the_replay_gives_the_camera_its_share(tmp_path, monkeypatch):
    pytest.importorskip("curl_cffi")
    import O4_Imagery_Utils as IMG
    import O4_UI_Utils as UI
    for module, name in ((IMG, "textures_in_parallel"),
                         (IMG, "shared_tile_cache_dir"), (UI, "red_flag")):
        monkeypatch.setattr(module, name, getattr(module, name))   # restored
    monkeypatch.delenv(S.ENV_DIR, raising=False)
    monkeypatch.setenv("O4_IMAGERY_FETCHER", "async")      # loopback only
    monkeypatch.syspath_prepend(TOOLS)
    import follow_contention_replay as REPLAY_TOOL
    index_path, _ = _index_rows(tmp_path)
    lat, lon = REPLAY["pos"][0][1:3]
    records = {}
    for arm in ("--no-priority", ""):
        args = REPLAY_TOOL.build_parser().parse_args(
            ["--index", index_path, "--lat", str(lat), "--lon", str(lon),
             "--seconds", "8", "--warmup", "2", "--drapes", "8",
             "--same-host", "--latency", "0.2", "--speed", "80",
             "--agl", "300", "--tmp", str(tmp_path)] + ([arm] if arm else []))
        records[arm or "priority"] = REPLAY_TOOL.run(args)
    base, mine = records["--no-priority"], records["priority"]
    assert mine["follow_req_s"] > base["follow_req_s"]
    assert mine["tick_gap_s"]["max"] < 3.0


def test_a_spawns_core_reads_only_the_tiles_in_reach():
    """The core of a spawn over the tiles in reach is the core over the
    whole index (#2037: the whole index was read at every flight load)."""
    import random

    import O4_Imagery_Follow_Reach as REACH
    import O4_Imagery_Spawn as SPAWN
    from test_imagery_follow_reach import _world
    rows = _world()
    tiles = REACH.by_tile(rows)
    rng = random.Random(2037)
    for _ in range(30):
        lat, lon = 59.0 + 3 * rng.random(), -137.0 + 3 * rng.random()
        agl = rng.choice([0.0, 300.0, 2300.0, 11000.0])
        assert (SPAWN.core_wants(rows, lat, lon, agl, tiles)
                == SPAWN.core_wants(rows, lat, lon, agl))
