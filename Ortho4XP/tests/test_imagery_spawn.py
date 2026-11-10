"""Twins for spawn and jump (#1992 local-imagery-cache spec §4.5, §8,
§11 U9, phase P5): ``O4_Imagery_Spawn``, the scenery reload of
``O4_XPlane_WebAPI`` and the follow job's use of both
(``o4_engine.imagery_follow``).

The acceptance of spec §14 P5, offline, on a replay of recorder flight
1's flight start (``tests/fixtures/imagery_spawn/flight1_start.replay.json``;
cut with ``tools/imagery_tier_replay.py extract <kit>/flight1.jsonl
<analyse_reads --csv> <pack> --window 0 160``): X-Plane's Web API answers
at the field for 80 s, drops while the flight loads, all 308 textures are
opened at mip 4 at 128 s and 174 of them again, finer, at 152-153 s.  The
replay puts the first position after the drop at the mip 4 opens (the v1
recorder never resumed; spec §11 U11 measures the real offset).

* cache hits land inside the flight-start window: X-Plane's finer opens
  find them, and no reload follows;
* a job that first reads X-Plane already standing at the field counts on
  no window: one reload once its core is down;
* downloads miss the window: ONE reload, after the core has landed; the
  reload's own stall is not a new witness;
* nothing missed (a built airport's kept core): no reload;
* no network: no reload; what the caches hold still lands in the window;
* a map jump is a witness; a jump back to a sharp core costs nothing.

Network-free: the fake X-Plane of ``test_imagery_follow`` on 127.0.0.1,
a stub lander on the test's clock.
"""
from __future__ import annotations

import concurrent.futures as futures
import json
import threading
import time
from pathlib import Path

import O4_Imagery_Spawn as SPAWN
import O4_Imagery_Tier_Plan as PLAN
import O4_XPlane_WebAPI as WEBAPI
import pytest
import test_imagery_follow as P3B
from o4_engine import imagery_follow as FOLLOW
from o4_engine.events import CAPABILITIES, ImageryFollowStatus
from O4_Imagery_Follow_Motion import MotionTracker
from test_imagery_follow import TILE, Clock, FakeLander, _index_rows

xplane = P3B.xplane                         # the fake X-Plane, a fixture

FX = Path(__file__).resolve().parent / "fixtures" / "imagery_spawn"
FLIGHT1 = json.loads((FX / "flight1_start.replay.json").read_text(
    encoding="utf-8"))
FIELD = tuple(FLIGHT1["pos"][-1][1:3])      # the camera when the API dropped
MIP4_AT = min(t for t, _name, mip in FLIGHT1["loads"] if mip == 4)
FINER = [(t, name, mip) for t, name, mip in FLIGHT1["loads"]
         if t > MIP4_AT + 1.0]              # the opens ~24 s later
#: A place in the tile no aircraft flies to from the field in a second.
FAR = (60.95, -135.95)
#: A place with no on-demand square in sight (the previous flight's).
ELSEWHERE = (62.6, -135.06)


def _rows(tiers=None):
    """Index rows (``{key: row}``) of flight 1's squares, in memory."""
    return {f"{TILE}/{name}": {
        "tile": TILE, "name": name, "centre_lat": lat, "centre_lon": lon,
        "load_size_m": size, "state": "low",
        "tier_px": PLAN.TIER_WIDTH[(tiers or {}).get(name, 0)]}
        for name, lat, lon, size in FLIGHT1["squares"]}


def _core(at=FIELD) -> dict:
    """name -> the tier a camera standing ``at`` wants."""
    return {key.split("/", 1)[1]: tier
            for key, tier in SPAWN.core_wants(_rows(), *at).items()}


# --- the fixture is flight 1's start --------------------------------------


def test_flight_1_opens_all_at_mip_4_then_finer_24_s_later():
    first = [x for x in FLIGHT1["loads"] if abs(x[0] - MIP4_AT) < 1.0]
    assert len(first) == len(FLIGHT1["squares"]) == 308
    assert {mip for _t, _n, mip in first} == {4}
    assert FLIGHT1["pos"][-1][0] < MIP4_AT          # no position at the load
    gaps = [t - MIP4_AT for t, _n, _m in FINER]
    assert sum(1 for _t, _n, mip in FINER if mip < 4) == 174
    assert 23.0 < min(gaps) and max(gaps) < 26.0
    assert min(gaps) > SPAWN.FLIGHT_START_WINDOW_S - SPAWN.WINDOW_MARGIN_S


def test_the_core_rule_names_what_x_plane_opened_finer():
    """The squares a camera at the field wants (the kept-core rule) are
    the ones flight 1 opened finer than the placeholder, at that tier."""
    core = _core()
    assert sorted(core.values()).count(3) == 14 and len(core) == 71
    loaded = {}
    for _t, name, mip in FINER:
        loaded[name] = max(loaded.get(name, 0), PLAN.tier_for_mip(mip))
    finer = {n: k for n, k in loaded.items() if k > 0}
    same = sum(1 for n, k in finer.items() if core.get(n) == k)
    assert same / len(finer) >= 0.85                # 63 of 70; the rest
    assert all(abs(core.get(n, 0) - k) <= 1 for n, k in finer.items())


# --- O4_Imagery_Spawn: witnesses and the reload verdict --------------------


def test_a_witness_plans_the_core_first_and_cached_files_before_downloads():
    rows = _rows()
    watch = SPAWN.SpawnWatch()
    cached = {n for n, k in _core().items() if k == 1}     # the 1024 ring
    assert watch.witness("spawn", 100.0, *FIELD, rows).window_end == 100.0
    episode = watch.witness("flight_load", 100.0, *FIELD, rows,
                            is_local=lambda row, tier: row["name"] in cached)
    assert episode.window_end == 100.0 + 20.0
    fetches = episode.fetches(rows, 105.0)
    assert len(fetches) == 71 and all(f.due and not f.late for f in fetches)
    assert all(f.tier == f.crossing == episode.wants[f.square]
               and f.deadline_s == 15.0 for f in fetches)
    names = [f.square.split("/", 1)[1] for f in fetches]
    assert set(names[:len(cached)]) == cached       # no download: first
    tiers = [f.tier for f in fetches[len(cached):]]
    assert tiers == sorted(tiers, reverse=True)     # then the core, its rings
    full = [f.distance_m for f in fetches if f.tier == 3]
    assert full == sorted(full)                     # nearest first


def test_the_reload_verdict_follows_the_read_model():
    rows = _rows()
    watch = SPAWN.SpawnWatch()
    episode = watch.witness("flight_load", 0.0, *FIELD, rows)
    key = next(k for k, tier in episode.wants.items() if tier == 3)
    other = next(k for k, tier in episode.wants.items() if tier == 1)
    episode.wants = {key: 3, other: 1}
    assert watch.settle(rows, *FIELD) is None       # still to land
    rows[key]["tier_px"] = 4096
    episode.note_landed(key, 2, 5.0)                # not the tier wanted
    episode.note_landed(key, 3, 5.0)                # inside the window
    assert watch.settle(rows, *FIELD) is None       # one in flight
    rows[other]["tier_px"] = 1024
    episode.note_landed(other, 1, 60.0)             # after it
    episode.note_landed(key, 3, 70.0)               # counted once
    assert episode.landed == {key, other} and episode.missed == {other}
    assert watch.settle(rows, *FIELD) == [other] and watch.episode is None
    # ... but not once the camera has left where X-Plane wants that tier:
    # the step-up open on the way back reads the new file
    again = SPAWN.SpawnWatch()
    episode = again.witness("jump", 0.0, *FIELD, _rows())
    episode.wants, episode.missed = {other: 1}, {other}
    assert again.settle(rows, *FAR) == []


def test_one_event_is_one_episode():
    rows = _rows()
    watch = SPAWN.SpawnWatch()
    first = watch.witness("jump", 0.0, *FIELD, rows)
    # a stutter (a short drop, the camera where it was): the window stands
    assert watch.witness("flight_load", 8.0, *FIELD, rows, moved_m=900.0,
                         down_s=3.0) is None
    assert watch.episode is first
    # a load (a long drop): X-Plane read everything again, a new window
    second = watch.witness("flight_load", 60.0, *FIELD, rows, moved_m=0.0,
                           down_s=40.0)
    assert second is not first and second.window_end == 80.0
    # this job's reload stalls X-Plane: its recovery is not a witness
    second.wants = {}
    assert watch.settle(rows, *FIELD) == []
    watch.reloaded(100.0)
    assert watch.witness("flight_load", 130.0, *FIELD, rows, moved_m=5.0,
                         down_s=25.0) is None
    # ... but a jump is, and so is a load somewhere else or much later
    assert watch.witness("jump", 131.0, *FAR, rows) is not None
    assert watch.witness("flight_load", 140.0, *FIELD, rows,
                         moved_m=50_000.0, down_s=5.0) is not None
    watch.episode = None
    late = 100.0 + SPAWN.RELOAD_QUIET_S + 1
    assert watch.witness("flight_load", late, *FIELD, rows, moved_m=0.0,
                         down_s=5.0) is None        # a stutter in flight
    assert watch.witness("flight_load", late, *FIELD, rows, moved_m=0.0,
                         down_s=30.0) is not None
    assert watch.episodes == 5 and watch.reloads == 1


def test_the_tracker_restarts_and_measures_a_move():
    tracker = MotionTracker()
    assert tracker.moved_m(*FIELD) == float("inf")
    tracker.add(0.0, *FIELD)
    tracker.add(1.0, FIELD[0] + 0.001, FIELD[1])
    assert tracker.motion().groundspeed_ms > 100
    assert 100 < tracker.moved_m(FIELD[0] + 0.002, FIELD[1]) < 120
    tracker.restart()
    assert tracker.add(50.0, *FAR).groundspeed_ms == 0.0 and not tracker.jumps


# --- O4_XPlane_WebAPI: the reload command (spec §11 U9) --------------------


def test_reload_scenery_is_the_web_api_command(xplane):
    ident = xplane.commands[WEBAPI.RELOAD_SCENERY]
    assert WEBAPI.RELOAD_SCENERY == "sim/operation/reload_scenery"
    assert WEBAPI.command_id(WEBAPI.RELOAD_SCENERY, xplane.base) == ident
    assert WEBAPI.reload_scenery(xplane.base) is True
    assert xplane.activations == [(ident, {"duration": 0.0})]


def test_no_command_no_reload(xplane):
    xplane.commands = {}                # the main menu: no flight loaded
    assert WEBAPI.command_id(WEBAPI.RELOAD_SCENERY, xplane.base) is None
    assert WEBAPI.reload_scenery(xplane.base) is False
    assert xplane.activations == []
    xplane.close()                      # X-Plane gone: the caller hears it
    with pytest.raises(OSError):
        WEBAPI.reload_scenery(xplane.base)


def test_a_reload_x_plane_is_busy_doing_counts_as_taken(xplane):
    xplane.stall_s = 0.6                # it reloads before it answers
    assert WEBAPI.activate_command(WEBAPI.RELOAD_SCENERY, xplane.base,
                                   timeout=0.15) is True
    assert len(xplane.activations) == 1


# --- the follow job over flight 1's start ----------------------------------


class CoreLander(FakeLander):
    """``cached`` names need no download and land at once; a download
    takes ``download_s`` seconds of the test's clock, or fails when
    ``offline``."""

    def __init__(self, clock, cached=(), download_s=0.0, offline=False):
        super().__init__()
        self.clock, self.cached = clock, set(cached)
        self.download_s, self.offline = download_s, offline
        self.entered = 0
        self.waiting = []               # (lands at, name, gate)

    def local(self, row, tier):
        return row["name"] in self.cached

    def __call__(self, row, tier):
        gate = None
        with self.guard:
            self.entered += 1
            if row["name"] not in self.cached and not self.offline:
                gate = threading.Event()
                self.waiting.append((self.clock.t + self.download_s,
                                     row["name"], gate))
        if row["name"] not in self.cached and self.offline:
            raise RuntimeError("no network")
        if gate is not None:
            assert gate.wait(20), "TIMED_OUT"
        return super().__call__(row, tier)

    def release(self, now) -> list:
        """Let the downloads due by ``now`` land; their names."""
        with self.guard:
            due = [w for w in self.waiting if w[0] <= now]
            self.waiting = [w for w in self.waiting if w[0] > now]
        for _at, _name, gate in due:
            gate.set()
        return [name for _at, name, _gate in due]


class Flight:
    """The job, the fake X-Plane and the stub lander on one clock."""

    def __init__(self, xplane, tmp_path, *, tiers=None, **lander):
        self.xplane, self.clock = xplane, Clock()
        index_path, _textures = _index_rows(tmp_path, FLIGHT1["squares"],
                                            tiers)
        self.index_path = index_path
        self.lander = CoreLander(self.clock, **lander)
        self.reloads = []               # when the job asked for one
        self.events = []
        self.submitted = 0
        self.job = FOLLOW.FollowJob(
            self.events.append, reader=WEBAPI.PositionReader(xplane.base),
            lander=self.lander, index_path=index_path, clock=self.clock,
            log_path=str(tmp_path / "od.log"), reloader=self.reload)
        self.job.open()

        self.max_slots = 1

    def reload(self) -> bool:
        self.reloads.append(self.clock.t)
        return True

    def core_landings(self, core) -> list:
        """The first landing of each ``core`` square, in landing order
        (the planner's turn margin fetches a little beyond the core, and
        finer, once the core is down)."""
        seen, out = set(), []
        for lnd in self.job.landings:
            name = lnd["square"].split("/", 1)[1]
            if name in core and name not in seen:
                seen.add(name)
                out.append(dict(lnd, name=name))
        return out

    def _done(self, names) -> None:
        wait = [self.job._inflight[f"{TILE}/{n}"].future for n in names
                if f"{TILE}/{n}" in self.job._inflight]
        assert not futures.wait(wait, timeout=20).not_done, "TIMED_OUT"

    def tick(self, t, at=None, down=False) -> None:
        """One second of the replay: downloads due land, then the job
        reads the camera ``at`` (the API refuses while ``down``)."""
        self.clock.t = t
        self._done(self.lander.release(t))
        self.xplane.down = down
        if at is not None:
            self.xplane.values.update(lat=at[0], lon=at[1])
        self.job.tick()
        self.max_slots = max(self.max_slots, self.job.slots.slots)
        self.submitted += len(self.job.last_dispatched)
        deadline = time.time() + 20
        while self.lander.entered < self.submitted:
            assert time.time() < deadline, "TIMED_OUT"
            time.sleep(0.001)
        self._done([f.square.split("/", 1)[1]
                    for f in self.job.last_dispatched
                    if f.square.split("/", 1)[1] in self.lander.cached
                    or self.lander.offline])

    def fly(self, start, stop, at=None, down=False) -> None:
        for t in range(int(start), int(stop)):
            self.tick(float(t), at, down)

    def load_flight_1(self, before="here") -> None:
        """Flight 1 to the mip 4 opens: positions at the field (``here``),
        at another place (``elsewhere``: the load brings the camera to the
        field), or none (``loading``: the job started during the load)."""
        if before != "loading":
            for t, lat, lon, _alt, _gs in FLIGHT1["pos"]:
                self.tick(t, (lat, lon) if before == "here" else ELSEWHERE)
        self.fly(FLIGHT1["pos"][-1][0] + 1, MIP4_AT, down=True)
        self.xplane.generation += 1

    def tier_at(self, name, t) -> int:
        """The tier on disk for ``name`` at time ``t``."""
        return max([lnd["tier"] for lnd in self.job.landings
                    if lnd["square"] == f"{TILE}/{name}"
                    and lnd["landed"] <= t], default=0)

    def served(self) -> tuple[int, int]:
        """Of flight 1's finer opens above the placeholder: how many found
        a file at least as fine on disk, and how many there were."""
        wanted = [(t, name, PLAN.tier_for_mip(mip)) for t, name, mip in FINER
                  if PLAN.tier_for_mip(mip) > 0]
        return (sum(1 for t, name, tier in wanted
                    if self.tier_at(name, t) >= tier), len(wanted))

    def close(self) -> ImageryFollowStatus:
        self.lander.release(float("inf"))
        self.job.close()
        return self.events[-1]


def test_cache_hits_land_inside_the_flight_start_window(xplane, tmp_path):
    """The previous flight was elsewhere; flight 1's load brings the
    camera to the field.  No network at all: only the caches serve."""
    core = _core()
    assert not _core(ELSEWHERE)
    flight = Flight(xplane, tmp_path, cached=core, offline=True)
    flight.load_flight_1("elsewhere")
    job = flight.job
    flight.tick(MIP4_AT // 1, FIELD)                # the witness
    # files that need no download take no fetch slot: four at once
    assert len(job.last_dispatched) == job.slots.max_slots == 4
    assert job.slots.slots < 4
    flight.fly(MIP4_AT + 1, 160, at=FIELD)
    window_end = MIP4_AT // 1 + 20.0
    landed = flight.core_landings(core)
    assert {lnd["name"]: lnd["tier"] for lnd in landed} == core
    assert all(lnd["landed"] <= window_end and not lnd["late"]
               for lnd in landed)
    # core first: the full squares landed before the rings
    order = [lnd["tier"] for lnd in landed]
    assert order == sorted(order, reverse=True)
    # X-Plane's own finer opens read them: every open the core rule
    # covers (3 boundary squares it opened one tier finer than the rule)
    assert flight.served() == (67, 70)
    assert flight.reloads == [] and job.counts["landed"] == len(core)
    last = flight.close()
    assert last.reloads == 0 and last.flight_loads == 1
    log = (tmp_path / "od.log").read_text(encoding="utf-8")
    assert "spawn=flight_load core=71 local=71 window_s=20.0" in log
    assert "spawn_done=flight_load landed=71 missed=0 stale=0 reload=no" in log


@pytest.mark.parametrize("before", ["here", "loading"])
def test_a_job_that_first_reads_the_field_counts_on_no_window(
        xplane, tmp_path, before):
    """Flight 1 as flown (the job reads the field for 80 s before the
    load), and a job started while it loads: X-Plane may have stood there
    for an hour, so the core that lands is taken as missed: one reload
    when it is down, none for the flight load that follows."""
    core = _core()
    flight = Flight(xplane, tmp_path, cached=core, offline=True)
    flight.load_flight_1(before)
    start = FLIGHT1["pos"][0][0] if before == "here" else MIP4_AT // 1
    flight.fly(MIP4_AT, 160, at=FIELD)
    landed = flight.core_landings(core)
    assert len(landed) == 71
    down = max(lnd["landed"] for lnd in landed)
    assert down < start + 20 and len(flight.reloads) == 1
    assert down < flight.reloads[0] <= down + 1.5   # the next tick
    if before == "here":                # on disk long before X-Plane's opens
        assert flight.served() == (67, 70)
    last = flight.close()
    assert last.reloads == 1
    assert "spawn=spawn core=71 local=71 window_s=0.0" in (
        tmp_path / "od.log").read_text(encoding="utf-8")


def test_downloads_miss_the_window_one_reload_after_the_core(xplane,
                                                             tmp_path):
    core = _core()
    full = {n for n, k in core.items() if k == 3}
    flight = Flight(xplane, tmp_path, cached=full, download_s=3.0)
    flight.load_flight_1("elsewhere")
    t = int(MIP4_AT)
    while not flight.reloads:
        assert t < MIP4_AT + 400, "TIMED_OUT"
        flight.tick(float(t), FIELD)
        t += 1
    job = flight.job
    window_end = MIP4_AT // 1 + 20.0
    landed = {lnd["name"]: lnd for lnd in flight.core_landings(core)}
    assert {n: lnd["tier"] for n, lnd in landed.items()} == core
    assert all(landed[n]["landed"] <= window_end for n in full)
    missed = [n for n, lnd in landed.items() if lnd["landed"] > window_end]
    assert missed and all(landed[n]["late"] for n in missed)
    # the reload came once, when the last core file was down
    assert flight.reloads == [max(lnd["landed"] for lnd in landed.values())]
    assert flight.max_slots > 1                    # the buffer was empty
    # X-Plane stalls while it reloads; positions resume: not a new witness
    stall = t + 15
    flight.fly(t, stall, down=True)
    flight.fly(stall, stall + 90, at=FIELD)
    assert job.reader.resets == 2 and flight.reloads[1:] == []
    last = flight.close()
    assert last.reloads == 1 and last.flight_loads == 2
    assert f"missed={len(missed)} stale={len(missed)} reload=sent" in (
        tmp_path / "od.log").read_text(encoding="utf-8")


def test_a_kept_core_needs_nothing(xplane, tmp_path):
    """A built airport: its core is kept sharp (spec §6.1)."""
    core = _core()
    flight = Flight(xplane, tmp_path, tiers=core, download_s=3.0)
    flight.load_flight_1("elsewhere")
    flight.fly(MIP4_AT, MIP4_AT + 90, at=FIELD)
    assert flight.job.spawn.episodes == 2 and flight.job.spawn.episode is None
    assert flight.reloads == []
    assert flight.close().reloads == 0
    assert "spawn=flight_load core=0 local=0" in (
        tmp_path / "od.log").read_text(encoding="utf-8")


def test_no_network_no_reload(xplane, tmp_path):
    core = _core()
    full = {n for n, k in core.items() if k == 3}
    flight = Flight(xplane, tmp_path, cached=full, offline=True)
    flight.load_flight_1("elsewhere")
    flight.fly(MIP4_AT, MIP4_AT + 200, at=FIELD)
    job = flight.job
    assert {lnd["square"].split("/", 1)[1] for lnd in job.landings} == full
    assert all(lnd["landed"] <= MIP4_AT // 1 + 20.0 for lnd in job.landings)
    assert job.counts["failed"] >= FOLLOW.OFFLINE_AFTER
    assert any(e.reason.startswith("Offline") for e in flight.events)
    assert flight.reloads == []
    assert flight.close().reloads == 0


def test_a_map_jump_is_a_witness_and_a_sharp_core_costs_nothing(xplane,
                                                                tmp_path):
    here, there = _core(FIELD), _core(FAR)
    assert there and not set(here) & set(there)
    flight = Flight(xplane, tmp_path, cached=here, download_s=5.0)
    flight.fly(0, 30, at=FIELD)                    # the field's core lands
    assert len(flight.core_landings(here)) == len(here)
    assert len(flight.reloads) == 1                # the session's first place
    t = 30
    while len(flight.reloads) < 2:                 # the map jump away
        assert t < 400, "TIMED_OUT"
        flight.tick(float(t), FAR)
        t += 1
    job = flight.job
    assert job.tracker.jumps == 1 and job.reader.resets == 0
    away = flight.core_landings(there)
    assert {lnd["name"]: lnd["tier"] for lnd in away} == there
    assert flight.reloads[1] == max(lnd["landed"] for lnd in away)
    flight.fly(t, t + 90, at=FIELD)                # ... and back
    assert job.tracker.jumps == 2 and job.spawn.episodes == 3
    assert len(flight.reloads) == 2
    last = flight.close()
    assert (last.jumps, last.reloads) == (2, 2)


def test_the_job_reloads_through_the_web_api_and_survives_its_refusal(
        xplane, tmp_path):
    index_path, _textures = _index_rows(tmp_path, FLIGHT1["squares"])
    clock = Clock()
    job = FOLLOW.FollowJob(
        lambda event: None, reader=WEBAPI.PositionReader(xplane.base),
        lander=FakeLander(), index_path=index_path, clock=clock,
        log_path=str(tmp_path / "od.log"),
        reloader=lambda: WEBAPI.reload_scenery(xplane.base))
    job.open()
    xplane.values.update(lat=FIELD[0], lon=FIELD[1])

    def run(start):
        for t in range(start, start + 60):
            clock.t = float(t)
            job.tick()
            futures.wait([f.future for f in job._inflight.values()],
                         timeout=10)
            if job.spawn.episode is None:
                return t
        raise AssertionError("TIMED_OUT")

    done = run(0)                                  # 71 files, 1 a second
    assert job.counts["reloads"] == 1
    assert xplane.activations == [
        (xplane.commands[WEBAPI.RELOAD_SCENERY], {"duration": 0.0})]
    # a jump whose reload X-Plane cannot take (no such command): no count
    xplane.commands = {}
    xplane.values.update(lat=FAR[0], lon=FAR[1])
    run(done + 1)
    assert job.tracker.jumps == 1 and job.counts["reloads"] == 1
    job.close()
    assert "reload=no" in (tmp_path / "od.log").read_text(encoding="utf-8")


def test_the_wire_names_the_reload():
    assert "imagery_spawn_reload" in CAPABILITIES
    assert ImageryFollowStatus(reloads=2).reloads == 2
    import inspect

    from o4_engine import imagery_commands as CMDS
    assert "reload" in inspect.signature(CMDS.start_imagery_follow).parameters


def test_the_real_lander_knows_what_needs_no_download(tmp_path, monkeypatch):
    import O4_DDS_Cache as DDSCACHE
    import O4_Imagery_Utils as IMG
    from o4_engine import imagery_follow_land as LAND
    entry, jpeg = tmp_path / "entry.dds", tmp_path / "tier.jpg"
    monkeypatch.setattr(DDSCACHE, "entry_path", lambda key: str(entry))
    monkeypatch.setitem(IMG.providers_dict, "FAKE", {"code": "FAKE"})
    monkeypatch.setattr(IMG, "_source_jpeg_location",
                        lambda tile, *attrs, drop=None: (str(tmp_path),
                                                         "tier.jpg"))
    lander = LAND.TierLander()
    monkeypatch.setattr(lander, "_tile", lambda row: object())
    row = {"tile": TILE, "name": "18752_35552_FAKE16.dds", "zl": 16,
           "provider": "FAKE", "build_dir": str(tmp_path),
           "dds_cache_key": "k"}
    assert not lander.local(row, 3) and not lander.local(row, 1)
    entry.write_bytes(b"x")
    assert lander.local(row, 3) and not lander.local(row, 2)
    jpeg.write_bytes(b"x")
    assert lander.local(row, 2)
    assert not lander.local(dict(row, name="not a texture"), 2)
    assert not lander.local(dict(row, provider="COMBINED",
                                 dds_cache_key=None), 3)
