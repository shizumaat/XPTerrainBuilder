"""Twins for #2037: the follow job sharpens the ground the aircraft flies
over, not only the places X-Plane reloaded at.

Observed on 2026-11-13 (flight 20261113T0352Z, 1.0.506, 2,300 m above the
ground at 160 m/s north across a city): three scenery reloads opened
three spawn episodes; each one's core (55, then 18 squares, 1024-4096 px)
took every fetch slot until ALL of it had landed, at ~4 squares per
75-163 s from a provider shared with a World drape run, so for twelve
minutes every landing was a core square of a place already behind the
aircraft and the planner's squares ahead got none.  The job also planned
the whole index (215,200 rows) every tick: 1.3 s of Python per tick.

The rules these twins hold:

* an episode's core follows the camera (``Episode.follow``): a square the
  camera has left is dropped, a square it still wants keeps only the tier
  it wants from where it is now -- so the episode closes once the camera
  has flown on;
* after the flight-start window a core file shows only at a reload: the
  planner's fetches for a crossing still ahead go first;
* the core is read at the eye (slant distance, RULINGS 2026-11-12f): no
  full file far below a high camera;
* the planner reads only the tiles in reach (``O4_Imagery_Follow_Reach``),
  and plans exactly what it planned over the whole index.

Network-free: a stub reader and the clock-driven lander of
``test_imagery_spawn`` on the test's clock.
"""
from __future__ import annotations

import concurrent.futures as futures
import math
import random
import time

import O4_Imagery_Follow_Reach as REACH
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_Spawn as SPAWN
import O4_Imagery_Tier_Plan as PLAN
from o4_engine import imagery_follow as FOLLOW
from test_imagery_follow import TILE, Clock, _index_rows
from test_imagery_spawn import CoreLander

#: A ZL16 square's S at 60.5 N (16 x 611 m x cos lat).
SIZE_M = 4_900.0
_M_PER_DEG = 111_320.0
LAT0, LON0 = 60.0, -136.0           # the tile's corner (TILE = +60-136)


def _squares():
    """A ZL16-like grid filling the 1-degree tile: (name, lat, lon, S)."""
    dlat = SIZE_M / _M_PER_DEG
    dlon = SIZE_M / (_M_PER_DEG * math.cos(math.radians(LAT0 + 0.5)))
    rows, cols = int(1 / dlat), int(1 / dlon)
    return [(f"{20000 + 16 * r}_{8000 + 16 * c}_Arc16.dds",
             LAT0 + (r + 0.5) * dlat, LON0 + (c + 0.5) * dlon, SIZE_M)
            for r in range(rows) for c in range(cols)]


def _rows(squares, tile=TILE):
    return {f"{tile}/{name}": {
        "tile": tile, "name": name, "centre_lat": lat, "centre_lon": lon,
        "load_size_m": size, "state": "low", "tier_px": 512}
        for name, lat, lon, size in squares}


# --- the planner reads only the tiles in reach ---------------------------


def _world():
    """Nine tiles of squares around +60-136 (an index of many tiles)."""
    rows = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            tile = f"+{60 + dy:02d}-{136 - dx:03d}"
            rows.update(_rows([(name, lat + dy, lon + dx, size)
                               for name, lat, lon, size in _squares()], tile))
    return rows


def test_reach_keeps_every_square_the_planner_plans():
    rows = _world()
    tiles = REACH.by_tile(rows)
    squares = {key: PLAN.Square(key, r["centre_lat"], r["centre_lon"],
                                r["load_size_m"]) for key, r in rows.items()}
    rng = random.Random(2037)
    read = []
    for _ in range(40):
        motion = PLAN.Motion(
            60.0 + rng.random(), -136.0 + rng.random(), 0.0,
            rng.uniform(0, 360), rng.choice([0.0, 8.0, 80.0, 160.0, 250.0]),
            rng.choice([0.0, 300.0, 2300.0, 11000.0]),
            rng.choice([0.0, -10.0]))
        keys = REACH.keys_within(tiles, motion.lat, motion.lon,
                                 REACH.plan_reach(motion))
        whole = PLAN.plan(motion, squares.values(), {})
        near = PLAN.plan(motion, [squares[k] for k in keys], {})
        assert near == whole
        read.append(len(keys) / len(rows))
    assert min(read) < 0.5 and max(read) <= 1.0     # far tiles left out


def test_a_parked_camera_reads_its_own_tile_only():
    rows = _world()
    tiles = REACH.by_tile(rows)
    motion = PLAN.Motion(60.5, -135.5, 0.0, 0.0, 0.0)   # parked mid-tile
    keys = REACH.keys_within(tiles, 60.5, -135.5, REACH.plan_reach(motion))
    assert {rows[k]["tile"] for k in keys} == {TILE}
    near = REACH.keys_within(tiles, 60.5, -135.5, REACH.near_reach())
    assert len(near) >= len(keys)                   # tier 0's 10 S


# --- the core is read at the eye ------------------------------------------


def test_the_core_is_read_at_the_eye():
    rows = _rows(_squares())
    here = (60.5, -135.5)
    ground = SPAWN.core_wants(rows, *here)
    assert ground == {key: CORES.core_tier(row, [("", *here)])
                      for key, row in rows.items()
                      if CORES.core_tier(row, [("", *here)])}
    low = SPAWN.core_wants(rows, *here, agl_m=2300.0)
    assert set(low) <= set(ground)
    assert all(low[k] <= ground[k] for k in low)
    high = SPAWN.core_wants(rows, *here, agl_m=11_000.0)
    assert 3 not in high.values()           # never the full file far below
    assert 1 in high.values()               # the 1024 ring still wanted


def test_a_core_the_camera_left_behind_is_dropped():
    rows = _rows(_squares())
    watch = SPAWN.SpawnWatch()
    episode = watch.witness("flight_load", 0.0, 60.2, -135.5, rows,
                            agl_m=2300.0)
    wanted = dict(episode.wants)
    assert 3 in wanted.values()
    on = 60.2 + 160.0 * 120 / _M_PER_DEG    # 160 m/s north for 120 s
    dropped = episode.follow(rows, on, -135.5, 2300.0)
    assert dropped > 0 and set(episode.wants) < set(wanted)
    for key, tier in episode.wants.items():     # what it wants from here
        assert tier == min(wanted[key],
                           SPAWN._eye_tier(rows[key], on, -135.5, 2300.0))
    episode.follow(rows, 60.95, -135.5, 2300.0)     # far on: nothing left
    assert not episode.pending(rows)
    assert watch.settle(rows, 60.95, -135.5) == []
    # a plan's departure is wherever the camera is: kept whole
    plan = watch.witness("plan", 0.0, 60.2, -135.5, rows)
    whole = dict(plan.wants)
    assert plan.follow(rows, 60.95, -135.5) == 0 and plan.wants == whole


# --- the observed sequence: reloads over a city while flying on ----------


class Reader:
    """X-Plane's Web API as the follow job reads it: the camera on a
    straight track, ``down`` while a scenery reload stalls it."""

    def __init__(self, clock, start, track_deg, speed_ms, agl_m):
        self.clock, self.start = clock, start
        self.track, self.speed, self.agl = track_deg, speed_ms, agl_m
        self.down = False
        self.resets = 0
        self.loading = False
        self._was_down = False

    def at(self, t):
        lat0, lon0 = self.start
        d, trk = self.speed * t, math.radians(self.track)
        return (lat0 + d * math.cos(trk) / _M_PER_DEG,
                lon0 + d * math.sin(trk)
                / (_M_PER_DEG * math.cos(math.radians(lat0))))

    def read(self):
        if self.down:
            self._was_down = True
            return None
        if self._was_down:
            self._was_down = False
            self.resets += 1
        lat, lon = self.at(self.clock.t)
        return {"lat": lat, "lon": lon, "elev_m": self.agl,
                "agl_m": self.agl, "paused": 0}


class Flight:
    """The job, the stub reader and the clock-driven lander."""

    def __init__(self, tmp_path, reader_kw, download_s):
        self.clock = Clock()
        index_path, _ = _index_rows(tmp_path, _squares())
        self.reader = Reader(self.clock, **reader_kw)
        self.lander = CoreLander(self.clock, download_s=download_s)
        self.job = FOLLOW.FollowJob(
            lambda _e: None, reader=self.reader, lander=self.lander,
            index_path=index_path, clock=self.clock,
            log_path=str(tmp_path / "od.log"))
        self.job.open()
        self.submitted = 0
        self.dispatched = []            # (t, fetch, an episode's core?)

    def tick(self, t):
        self.clock.t = t
        due = self.lander.release(t)
        wait = [self.job._inflight[f"{TILE}/{n}"].future for n in due
                if f"{TILE}/{n}" in self.job._inflight]
        assert not futures.wait(wait, timeout=20).not_done, "TIMED_OUT"
        self.job.tick()
        episode = self.job.spawn.episode
        core = set(episode.wants) if episode is not None else set()
        for f in self.job.last_dispatched:
            self.dispatched.append((t, f, f.square in core))
        self.submitted += len(self.job.last_dispatched)
        deadline = time.time() + 20
        while self.lander.entered < self.submitted:
            assert time.time() < deadline, "TIMED_OUT"
            time.sleep(0.001)

    def close(self):
        self.lander.release(float("inf"))
        self.job.close()


def test_reloads_over_a_city_do_not_hold_the_slots_from_the_ground_ahead(
        tmp_path):
    """The sequence of #2037: in flight at 2,300 m and 160 m/s, X-Plane
    reloads its scenery twice (each a 15 s Web API drop: a flight-load
    witness), every download takes 100 s, four slots.  Each reload's core
    is more than the slots can land before the aircraft has left it
    (landing it whole took 8-20 min of every slot on the flight).  Now
    each core closes as the aircraft leaves it, and squares whose
    crossing is still ahead take slots while a core is open."""
    flight = Flight(tmp_path, dict(start=(60.08, -135.5), track_deg=10.0,
                                   speed_ms=160.0, agl_m=2300.0),
                    download_s=100.0)
    reloads = [(30, 45), (400, 415)]
    spans = []                              # [episode, opened, closed]
    try:
        for t in range(0, 800):
            flight.reader.down = any(a <= t < b for a, b in reloads)
            flight.tick(float(t))
            episode = flight.job.spawn.episode
            for span in spans:
                if span[0] is not episode and span[2] is None:
                    span[2] = t
            if episode is not None and not any(s[0] is episode for s in spans):
                spans.append([episode, t, None])
    finally:
        flight.close()
    log = (tmp_path / "od.log").read_text(encoding="utf-8")
    loads = [s for s in spans if s[0].witness == "flight_load"]
    assert len(loads) == 2
    assert log.count("spawn_done=flight_load") == 2     # closed, not replaced
    for episode, opened, closed in loads:
        whole = len(episode.had) * 100.0 / flight.job.slots.max_slots
        assert closed is not None and closed - opened < whole
    # the ground ahead got slots while a core was open
    open_at = {t for _e, opened, closed in loads
               for t in range(opened, closed)}
    ahead = [(t, f) for t, f, in_core in flight.dispatched
             if not in_core and f.deadline_s > 0.0 and t in open_at]
    assert len(ahead) >= 4
    for t, f in ahead:                      # ahead of the camera then
        row = flight.job._rows[f.square]
        assert row["centre_lat"] > flight.reader.at(t)[0] - SIZE_M / _M_PER_DEG
