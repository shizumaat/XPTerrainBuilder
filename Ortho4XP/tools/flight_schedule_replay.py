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

usage:
  flight_schedule_replay.py [FIXTURE] [--kit KIT] [--kind light|drape]
                            [--build-s S] [--speed K ...] [--capacity N]
                            [--cores N] [--json]

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
    """Each build takes ``seconds``; any number may run (the job's slots
    bound them)."""

    def __init__(self, seconds: float) -> None:
        self.seconds = float(seconds)
        self.now = 0.0
        self.running: dict = {}
        self.started: list = []

    def start(self, tile, kind, deadline_in_s, klass) -> bool:
        self.running[tuple(tile)] = self.now + self.seconds
        self.started.append((tuple(tile), self.now))
        return True

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
    a = ap.parse_args(argv)
    with open(a.fixture, encoding="utf-8") as f:
        flight = json.load(f)
    with open(a.kit, encoding="utf-8") as f:
        kit = json.load(f)
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
