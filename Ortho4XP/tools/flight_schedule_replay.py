#!/usr/bin/env python3
"""Replay a recorded flight through the build-ahead job (flight manager /
World spec 2026-11-10, §15 "Flight replay", W2): would every World-pack
tile the aircraft entered have been published before X-Plane opened it?

The job (``o4_engine.world_job.WorldJob``, track mode) is driven by the
recorded aircraft positions on a fake clock (the recording's own seconds,
divided by ``--speed`` to fly the same track faster), with a fake builder
that takes ``--build-s`` seconds a tile (default: the kind's measured
estimate, light 397 s / drape 37 s) and a fake publisher that swaps a
finished tile whenever rule S3 allows.  The witness of X-Plane's loads is
the recording's own ``.dsf`` opens of the World pack.

Pass: each World tile X-Plane opened was swapped in BEFORE its first open
(margin > 0), and no tile was swapped after X-Plane had opened it.  The
recording starts on a loaded flight, so the window starts at the flight
load rule (``WindowTracker.load``, B = round(lon), R = floor(lat)).

``--flight DEST_LAT,DEST_LON`` replays the FLIGHT MANAGER instead (lane
F1b, ``o4_engine.flight_manager.FlightManager``): a flight from the
recording's first position to that destination is created (corridor
``--corridor-km``, cruise ``--cruise-kt``), the pilot waits on the ground
until it is ready (10g: the readiness rows and the countdown, the staged
first-window tiles merged in with ONE ground reload, S6 (a)), then the
recording is flown from that moment.  A fake builder takes ``--build-s``
per intermediate tile and ``--full-s`` per ``full`` build (departure,
destination).  Pass: the countdown at creation covers the wait, it never
rose while waiting, every opened World tile of the flight was swapped
before its first open and no loaded tile was swapped.

``--divert T,LAT,LON[,IDENT]`` (lane F2, spec §8.6) diverts the flight at
the recording's second T to that airport (``FlightManager.divert``: its
tile built ``full`` first, the old destination's build stopped);
``--approach`` then flies on past the recording's end, straight to the
diversion airport at the last groundspeed, descending evenly to land
there (so rule S6 (b), the one reload near the ground, can be seen).
The result adds the notices posted (``FlightNotice`` codes), the reloads
in the air and the diversion tile's margin.

usage:
  flight_schedule_replay.py [FIXTURE] [--kit KIT] [--kind light|drape]
                            [--build-s S] [--speed K ...] [--capacity N]
                            [--cores N] [--json]
                            [--flight LAT,LON [--full-s S] [--cruise-kt K]
                             [--corridor-km KM] [--divert T,LAT,LON[,IDENT]
                             [--approach]]]

FIXTURE defaults to ``tests/fixtures/world/cyyr_world_flight.replay.json``
(positions + ``.dsf`` opens, cut by ``imagery_tier_replay.py extract
--aircraft``); KIT to ``cyyr_world_kit.json`` beside it (the World pack's
placeholder tiles, the user's own tile the kit skipped, and the as-flown
build of +53-064).  ``--capacity`` (the session's slots; parked builds
use two fewer) and ``--cores`` (in flight: ``clamp((cores - 6) // 3, 1,
3)``) default to this Mac (18 cores, 16 slots).  Twin:
``Ortho4XP/tests/test_flight_schedule_replay.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "src"))

import O4_World_Pack as WP  # noqa: E402
from o4_engine import world_job as JOB  # noqa: E402

FIXTURES = os.path.join(HERE, os.pardir, "tests", "fixtures", "world")
FIXTURE = os.path.join(FIXTURES, "cyyr_world_flight.replay.json")
KIT = os.path.join(FIXTURES, "cyyr_world_kit.json")


class FakeBuilder:
    """Each build takes ``seconds`` (a number, or ``{kind: seconds}``);
    any number may run (the job's slots bound them)."""

    def __init__(self, seconds) -> None:
        self.seconds = seconds
        self.now = 0.0
        self.running: dict = {}
        self.started: list = []
        self.cancelled: list = []

    def start(self, tile, kind, deadline_in_s, klass) -> bool:
        took = (self.seconds[kind] if isinstance(self.seconds, dict)
                else float(self.seconds))
        self.running[tuple(tile)] = self.now + took
        self.started.append((tuple(tile), self.now))
        return True

    def cancel(self, tile) -> None:
        """Stop a build (a diversion's old destination)."""
        self.running.pop(tuple(tile), None)
        self.cancelled.append((tuple(tile), self.now))

    def poll(self, now: float) -> list:
        done = [t for t, at in self.running.items() if at <= now]
        for tile in done:
            del self.running[tile]
        return [(tile, True) for tile in done]


class FakePublisher:
    """Stages a finished tile and swaps it as soon as S3 allows."""

    @staticmethod
    def settle(tile, kind, held: bool) -> str:
        return "staged" if held else "swapped"


def _opens(flight: dict, pack: str) -> dict:
    """``{tile: first time X-Plane opened its World-pack DSF}``."""
    first: dict = {}
    for t, name, where in flight["dsf"]:
        if where == pack:
            tile = WP.parse_tile(name)
            first[tile] = min(t, first.get(tile, t))
    return first


def replay(flight: dict, kit: dict, kind: str = "light",
           build_s: float | None = None, speed: float = 1.0,
           capacity: int = 16, cores: int = 18) -> dict:
    """Run the job over the flight; the per-tile outcome and the verdict."""
    wanted = {WP.parse_tile(n) for n in kit["placeholders"]}
    opens = {t: s / speed for t, s in _opens(flight, kit["pack"]).items()}
    seconds = JOB.ESTIMATE_S[kind] if build_s is None else float(build_s)
    builder = FakeBuilder(seconds)
    clock = {"now": 0.0}
    job = JOB.WorldJob(
        builder=builder, publisher=FakePublisher(),
        wanted=lambda tile: tile in wanted, kind=kind, capacity=capacity,
        cores=cores, estimate_s={kind: seconds},
        loads=lambda: {t for t, at in opens.items() if at <= clock["now"]})
    pos = flight["pos"]
    job.flight_loaded(pos[0][1], pos[0][2])
    loaded_swaps = []
    for t, lat, lon, alt, *_ in pos:
        now = clock["now"] = builder.now = t / speed
        before = len(job.swaps)
        job.tick(now, {"lat": lat, "lon": lon, "elev_m": alt})
        for tile, at in job.swaps[before:]:
            if tile in opens and opens[tile] <= at:
                loaded_swaps.append((WP.tile_name(*tile), at))
    tiles = []
    for tile, opened in sorted(opens.items(), key=lambda kv: kv[1]):
        if tile not in wanted:
            continue
        j = job.jobs.get(tile)
        swapped = j.swapped_at if j else None
        tiles.append({"tile": WP.tile_name(*tile), "opened_s": round(opened, 1),
                      "started_s": (round(j.started_at, 1)
                                    if j and j.started_at is not None
                                    else None),
                      "swapped_s": (round(swapped, 1)
                                    if swapped is not None else None),
                      "margin_s": (round(opened - swapped, 1)
                                   if swapped is not None else None)})
    late = [r["tile"] for r in tiles
            if r["margin_s"] is None or r["margin_s"] <= 0]
    return {"kind": kind, "build_s": seconds, "speed": speed,
            "flight_slots": job.flight_cap,
            "parked_slots": JOB.GOVERNOR.parked_slots(capacity),
            "built": len(builder.started), "tiles": tiles, "late": late,
            "loaded_swaps": loaded_swaps,
            "ok": not late and not loaded_swaps}


def _flight_plan(flight: dict, dest: tuple):
    import O4_Flight_Plan as FP
    lat, lon = flight["pos"][0][1:3]
    return FP.FlightPlan([FP.Waypoint("DEP", lat, lon),
                          FP.Waypoint("DEST", float(dest[0]), float(dest[1]))],
                         source="replay")


class _FlightClock:
    """The replay's two clocks: the manager's (seconds since the flight
    was created) and the recording's (its own seconds, the witness's)."""

    def __init__(self) -> None:
        self.now = 0.0
        self.rec_t = 0.0


def approach_positions(last: list, airport: tuple, ground: float,
                       step_s: float = 1.0) -> list:
    """Recorder rows ``[t, lat, lon, alt]`` flying straight on from
    ``last`` to ``airport`` ``(lat, lon)`` at ``last``'s groundspeed
    (``last[4]``), descending evenly to ``ground`` there; then 60 s
    standing on it."""
    t0, lat0, lon0, alt0 = last[:4]
    gs = max(30.0, float(last[4] if len(last) > 4 else 70.0))
    dist = JOB._M_PER_DEG * math.hypot(airport[0] - lat0, (airport[1] - lon0)
                                       * math.cos(math.radians(lat0)))
    steps = max(1, int(dist / gs / step_s))
    rows = []
    for i in range(1, steps + 1):
        f = i / steps
        rows.append([t0 + i * step_s, lat0 + f * (airport[0] - lat0),
                     lon0 + f * (airport[1] - lon0),
                     alt0 + f * (ground - alt0), gs * (1 - f)])
    end = rows[-1][0]
    rows += [[end + k, airport[0], airport[1], ground, 0.0]
             for k in range(1, 61)]
    return rows


def replay_flight(flight: dict, kit: dict, dest: tuple, kind: str = "light",
                  build_s: float | None = None, full_s: float = 900.0,
                  cruise_kt: float = 290.0, corridor_km: float = 20.0,
                  capacity: int = 16, cores: int = 18,
                  speed: float = 1.0, divert: dict | None = None,
                  approach: bool = False) -> dict:
    """The flight manager over the recording (see the module): the wait,
    the countdown, the ground reload, then the flight's swaps against
    X-Plane's opens.  ``speed`` flies the recording that many times faster
    (the plan's cruise with it)."""
    from datetime import datetime, timezone

    import O4_Flight_Plan as FP
    import O4_Flight_Schedule as SCHEDULE
    from o4_engine import flight_record as RECORD
    from o4_engine.flight_manager import FlightManager

    seconds = {kind: JOB.ESTIMATE_S[kind] if build_s is None else float(build_s),
               "full": float(full_s)}
    placeholders = {WP.parse_tile(n) for n in kit["placeholders"]}
    external = {WP.parse_tile(n) for n in kit.get("external", ())}
    opens = _opens(flight, kit["pack"])
    pos = flight["pos"]
    ground = pos[0][3]
    first = pos[0]
    clock = _FlightClock()
    builder = FakeBuilder(seconds)
    reloads: list = []

    def state_of(tile):
        return ("external" if tile in external
                else "placeholder" if tile in placeholders else None)

    def estimate(tile, k, role):
        return SCHEDULE.job_estimate(k, seconds[k], known=True)

    def facts():
        seen = {t for t, at in opens.items() if at <= clock.rec_t}
        return {"world_installed": True, "world_seen": True,
                "xplane_running": True, "budget_fits": True,
                "network_ok": True, "all_on_disk": True,
                "prefetch_done": True, "loads": seen}

    def ground_reload(tiles):
        names = [WP.tile_name(*t) for t in tiles]
        if manager.takeoff_at is None:
            reloads.append((clock.now, names))
        else:
            reloads_air.append((clock.now, names))
        return True

    plan = _flight_plan(flight, dest)
    reloads_air: list = []
    notices: list = []
    record = RECORD.from_plan(plan, "none", datetime.now(timezone.utc),
                              cruise_kt=cruise_kt * speed,
                              corridor_km=corridor_km)
    manager = FlightManager(
        record, plan, builder=builder, publisher=FakePublisher(), facts=facts,
        state_of=state_of, estimate=estimate, intermediate=kind,
        parked_slots=JOB.GOVERNOR.parked_slots(capacity),
        flight_slots=JOB.GOVERNOR.flight_slots(cores, 0, capacity),
        ground_reload=ground_reload)
    parked = {"lat": first[1], "lon": first[2], "agl_m": 0.0, "gs_ms": 0.0}
    manager.tracker.load(first[1], first[2])
    countdowns = []
    while record.state == "preparing" and clock.now < 6 * 3600:
        builder.now = clock.now
        manager.tick(clock.now, parked)
        countdowns.append((clock.now, manager.countdown_s))
        clock.now += 1.0
    wait = clock.now
    first_countdown = next((c for _t, c in countdowns if c is not None), None)
    rose = [(t, a, b) for (t, a), (_u, b) in zip(countdowns, countdowns[1:], strict=False)
            if a is not None and b is not None and b > a + 1.0]
    swapped_loaded = []
    prev = None
    diverted_tile = None
    if divert is not None and approach:
        pos = list(pos) + approach_positions(
            pos[-1], (divert["lat"], divert["lon"]), ground)
    for t, lat, lon, alt, *_ in pos:
        if divert is not None and diverted_tile is None and t >= divert["at_s"]:
            target = FP.Waypoint(divert.get("ident", "DIVERT"),
                                 float(divert["lat"]), float(divert["lon"]))
            manager.divert(wait + t / speed, target, False,
                           cancel=builder.cancel)
            diverted_tile = FP.tile_of(target.lat, target.lon)
        clock.rec_t, clock.now = t, wait + t / speed
        builder.now = clock.now
        gs = 0.0
        if prev is not None and t > prev[0]:
            gs = (JOB._M_PER_DEG * math.hypot(
                lat - prev[1], (lon - prev[2]) * math.cos(math.radians(lat)))
                / ((t - prev[0]) / speed))
        prev = (t, lat, lon)
        before = {j.tile: j.state for j in manager.jobs}
        manager.tick(clock.now, {"lat": lat, "lon": lon,
                                 "agl_m": max(0.0, alt - ground), "gs_ms": gs})
        notices += [(round(clock.now, 1), n["code"]) for n in manager.notices()]
        reloaded = {n for _at, names in reloads_air for n in names}
        for job in manager.jobs:
            if (job.state == "swapped" and before.get(job.tile) != "swapped"
                    and WP.tile_name(*job.tile) not in reloaded
                    and job.tile in opens and opens[job.tile] <= t):
                swapped_loaded.append(WP.tile_name(*job.tile))
    rows = []
    for job in manager.jobs:
        swapped = manager._runs.get(job.tile, {}).get("swapped_at")
        opened = opens.get(job.tile)
        rows.append({"tile": WP.tile_name(*job.tile), "role": job.role,
                     "kind": job.kind, "klass": "P%d" % job.klass,
                     "state": job.state,
                     "deadline_s": round(job.deadline_s, 1),
                     "swapped_s": None if swapped is None else round(swapped, 1),
                     "opened_s": (None if opened is None
                                  else round(wait + opened / speed, 1)),
                     "margin_s": (round(wait + opened / speed - swapped, 1)
                                  if swapped is not None and opened is not None
                                  else None)})
    late = [r["tile"] for r in rows if r["opened_s"] is not None
            and (diverted_tile is None
                 or r["tile"] != WP.tile_name(*diverted_tile))
            and (r["margin_s"] is None or r["margin_s"] <= 0)]
    diverted = next((r for r in rows if diverted_tile is not None
                     and r["tile"] == WP.tile_name(*diverted_tile)), None)
    covered = first_countdown is not None and first_countdown >= wait - 1.0
    return {"speed": speed, "wait_s": wait, "countdown_s": first_countdown,
            "countdown_rose": rose, "reloads": reloads,
            "state": record.state, "phase": record.phase,
            "reloads_air": reloads_air, "notices": notices,
            "diverted": diverted, "cancelled": [
                (WP.tile_name(*t), round(at, 1)) for t, at in builder.cancelled],
            "items": [list(i) for i in manager.items], "tiles": rows,
            "late": late, "loaded_swaps": swapped_loaded,
            "ok": covered and not rose and not late and not swapped_loaded}


def _print_flight(result: dict) -> None:
    print(f"flight at {result['speed']:g}x: waited {result['wait_s']:.0f} s "
          f"on the ground (countdown "
          f"at creation {result['countdown_s']}), reloads "
          f"{result['reloads']}, now {result['state']} / {result['phase']}: "
          + ("OK" if result["ok"] else f"LATE {result['late']}"))
    for row in result["tiles"]:
        print(f"  {row['tile']} {row['role']:<11} {row['kind']:<8} "
              f"{row['klass']} {row['state']:<8} deadline {row['deadline_s']}"
              f"  swapped {row['swapped_s']}  opened {row['opened_s']}  "
              f"margin {row['margin_s']}")
    for tile in result["loaded_swaps"]:
        print(f"  SWAPPED A LOADED TILE {tile}")
    if result.get("diverted"):
        print(f"  diverted to {result['diverted']}; reloads in the air "
              f"{result['reloads_air']}; cancelled {result['cancelled']}")
    if result.get("notices"):
        print(f"  notices {result['notices']}")


def as_flown(flight: dict, kit: dict) -> dict:
    """The one tile built in flight on the CYYR flight, as flown: its
    swap against its first open (spec §15: 397 s, swapped well before)."""
    row = kit["as_flown"]
    opened = _opens(flight, kit["pack"])[WP.parse_tile(row["tile"])]
    return {"tile": row["tile"], "build_start_s": row["build_start_s"],
            "swapped_s": row["swapped_s"], "opened_s": opened,
            "margin_s": round(opened - row["swapped_s"], 1)}


def _print(result: dict) -> None:
    print(f"{result['kind']} {result['build_s']:.0f} s a tile, speed "
          f"{result['speed']:g}x, slots {result['parked_slots']} parked / "
          f"{result['flight_slots']} flying, {result['built']} builds: "
          + ("OK" if result["ok"] else f"LATE {result['late']}"))
    for row in result["tiles"]:
        print(f"  {row['tile']}  opened {row['opened_s']:7.1f}  started "
              f"{row['started_s']}  swapped {row['swapped_s']}  "
              f"margin {row['margin_s']}")
    for tile, at in result["loaded_swaps"]:
        print(f"  SWAPPED A LOADED TILE {tile} at {at:.1f}")


def main(argv=None) -> int:
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("fixture", nargs="?", default=FIXTURE)
    ap.add_argument("--kit", default=KIT)
    ap.add_argument("--kind", choices=JOB.KINDS, default="light")
    ap.add_argument("--build-s", type=float, default=None)
    ap.add_argument("--speed", type=float, nargs="+", default=[1.0])
    ap.add_argument("--capacity", type=int, default=16)
    ap.add_argument("--cores", type=int, default=18)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--flight", default=None, metavar="LAT,LON")
    ap.add_argument("--full-s", type=float, default=900.0)
    ap.add_argument("--cruise-kt", type=float, default=290.0)
    ap.add_argument("--corridor-km", type=float, default=20.0)
    ap.add_argument("--divert", default=None, metavar="T,LAT,LON[,IDENT]")
    ap.add_argument("--approach", action="store_true")
    a = ap.parse_args(argv)
    with open(a.fixture, encoding="utf-8") as f:
        flight = json.load(f)
    with open(a.kit, encoding="utf-8") as f:
        kit = json.load(f)
    if a.flight:
        dest = tuple(float(v) for v in a.flight.split(","))
        divert = None
        if a.divert:
            parts = a.divert.split(",")
            divert = {"at_s": float(parts[0]), "lat": float(parts[1]),
                      "lon": float(parts[2]),
                      "ident": parts[3] if len(parts) > 3 else "DIVERT"}
        results = [replay_flight(flight, kit, dest, a.kind, a.build_s,
                                 a.full_s, a.cruise_kt, a.corridor_km,
                                 a.capacity, a.cores, k, divert, a.approach)
                   for k in a.speed]
        if a.json:
            print(json.dumps(results, indent=1))
        else:
            for result in results:
                _print_flight(result)
        return 0 if all(r["ok"] for r in results) else 1
    results = [replay(flight, kit, a.kind, a.build_s, s, a.capacity, a.cores)
               for s in a.speed]
    flown = as_flown(flight, kit)
    if a.json:
        print(json.dumps({"as_flown": flown, "runs": results}, indent=1))
    else:
        print(f"as flown: {flown['tile']} built from {flown['build_start_s']}"
              f" s, swapped {flown['swapped_s']} s, opened "
              f"{flown['opened_s']} s: margin {flown['margin_s']} s")
        for result in results:
            _print(result)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
