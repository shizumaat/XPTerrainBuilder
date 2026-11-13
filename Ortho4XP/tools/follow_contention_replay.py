#!/usr/bin/env python3
"""follow_contention_replay.py: the imagery follow job against a World
drape run, offline, on the engine's real fetch path (#2037).

The real ``imagery_follow.FollowJob`` (its own thread and its house
thread) follows a straight camera over a COPY of an on-demand index while
``--drapes`` drape tiles fetch beside it, in one process as the engine
runs them.  Every texture of both goes through the real
``O4_Imagery_Utils.build_texture_from_tilbox`` (the async fetcher on the
engine's one event loop, the session's ``net:<host>`` budget of
``O4_Machine_Slots``, the JPEG decode and paste) against loopback servers
in a CHILD process (so their threads take no GIL here) that answer each
request after ``--latency`` s (x 0.5-1.5); each texture is then encoded
(``O4_DDS_Encode.encode_dds``).  The follower's tier takes 16/64/256
requests (1024/2048/4096 px), a drape square 4 (512 px).  The drapes use
a server of their own (the CYEG flight: Bing drapes, Arc follower) unless
``--same-host``.  No network, no X-Plane, no texture written: a landing
changes only the index copy.

    cd Ortho4XP && venv/bin/python tools/follow_contention_replay.py \\
        --index COPY.sqlite --lat 53.31 --lon -113.58 --seconds 120 \\
        [--drapes 12] [--same-host] [--no-priority] [--base] \\
        [--slots 4] [--json OUT.jsonl]

``--base`` is the tick before #2037's house: the house's work on the tick,
the rows read one ``sqlite3`` step per row (``INDEX.rows``), the storage
floor measured at every check, a spawn's core and the status's sharp
count read over every row; ``--no-priority`` gives the follower no
precedence in the server's budget.  Together: the base behaviour.  Prints
one JSON record: requests per second of the follower and the drapes,
squares landed, the harvest lag (a landing to the tick that counts it)
and the gaps between ticks.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import O4_Machine_Slots as MACHINE_SLOTS  # noqa: E402
from O4_Imagery_Tier_Plan import TIER_WIDTH  # noqa: E402

#: map tiles per side of a follower tier (16, 64, 256 requests)
SIDE = {1: 4, 2: 8, 3: 16}
#: a drape square at 512 px: a 2 x 2 fetch
DRAPE_SIDE = 2
FOLLOW_ZL, DRAPE_ZL = 18, 13


def _serve(ports, latency_s: float, counts) -> None:
    """Child process: two loopback tile servers; ``counts`` the requests
    of the follower's provider (0) and the drapes' (1), by path; each
    answer waits ``latency_s`` x 0.5-1.5."""
    import io
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from PIL import Image
    jpegs = []
    for k in range(16):
        buf = io.BytesIO()
        Image.new("RGB", (256, 256), (k * 15, 120, 255 - k * 15)).save(
            buf, format="JPEG", quality=85)
        jpegs.append(buf.getvalue())

    def handler():
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                time.sleep(latency_s * random.uniform(0.5, 1.5))
                body = jpegs[hash(self.path) % len(jpegs)]
                which = 0 if self.path.startswith("/TWA/") else 1
                with counts.get_lock():
                    counts[which] += 1
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass
        return Handler

    ThreadingHTTPServer.request_queue_size = 512
    servers = [ThreadingHTTPServer(("127.0.0.1", 0), handler())
               for _ in range(2)]
    for server in servers:
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
    ports.put([server.server_address[1] for server in servers])
    while True:
        time.sleep(3600)


def _provider(code: str, port: int) -> dict:
    return {"code": code, "request_type": "tms", "grid_type": "webmercator",
            "tile_size": 256, "max_threads": 16,
            "resolutions": {z: 1.0 for z in range(25)},
            "top_left_corner": {z: [0.0, 0.0] for z in range(25)},
            "url_template": "http://127.0.0.1:%d/%s/{zoom}/{x}/{y}.jpg"
                            % (port, code)}


def texture(provider: dict, zl: int, x0: int, y0: int, side: int) -> None:
    """One texture through the engine's fetch path, then encoded."""
    import numpy
    import O4_DDS_Encode as ENCODE
    import O4_Imagery_Utils as IMG
    _ok, image = IMG.build_texture_from_tilbox(
        (x0, y0, x0 + side, y0 + side), zl, provider)
    ENCODE.encode_dds(numpy.asarray(image.convert("RGB")), "bc1")


class Lander:
    """The follower's lander: the tier's square, fetched and encoded."""

    def __init__(self, provider):
        self.provider, self.count = provider, 0
        self.guard = threading.Lock()

    def __call__(self, row, tier):
        with self.guard:
            self.count += 1
            k = self.count
        side = SIDE[int(tier)]
        texture(self.provider, FOLLOW_ZL, 1000 + 16 * k, 2000, side)
        return {"tier_px": TIER_WIDTH[int(tier)], "full_bytes": 1,
                "network": True}


def drape_worker(provider, stop, seed: int) -> None:
    """One of a drape tile's two texture workers: squares in turn."""
    k = 0
    while not stop.is_set():
        k += 1
        texture(provider, DRAPE_ZL, 4 * k, 8 * seed, DRAPE_SIDE)


def burn(seconds: float) -> None:
    """Python and numpy work holding the GIL (``--cpu-threads``)."""
    import numpy as np
    end = time.perf_counter() + seconds
    image = np.random.rand(256, 256).astype(np.float32)
    while time.perf_counter() < end:
        (image ** 2.2).clip(0, 1).reshape(64, 4, 64, 4).mean(axis=(1, 3))
        total = 0
        for value in range(2000):
            total += value


def cpu_worker(stop) -> None:
    while not stop.is_set():
        burn(0.5)


def py_worker(stop) -> None:
    """Pure Python that never waits: a drape's water-mask polygons, a
    rescan's parsing (``--py-threads``)."""
    while not stop.is_set():
        total = 0
        for value in range(200_000):
            total += value * value


class Reader:
    """A camera on a straight line (track ``track_deg``) at ``speed``."""

    resets, loading = 0, False

    def __init__(self, lat, lon, track_deg, speed_ms, agl_m):
        self.t0, self.lat, self.lon = time.time(), lat, lon
        self.track, self.speed, self.agl = math.radians(track_deg), speed_ms, agl_m

    def read(self):
        dist = self.speed * (time.time() - self.t0)
        north, east = dist * math.cos(self.track), dist * math.sin(self.track)
        lat = self.lat + north / 111_320.0
        lon = self.lon + east / (111_320.0 * math.cos(math.radians(lat)))
        return {"lat": lat, "lon": lon, "elev_m": self.agl + 700.0,
                "agl_m": self.agl, "paused": False}


def _copy(src: str, dst: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(src + suffix):
            if sys.platform == "darwin":
                subprocess.run(["cp", "-c", src + suffix, dst + suffix],
                               check=True)
            else:
                shutil.copy2(src + suffix, dst + suffix)


def _pct(values, q):
    if not values:
        return 0.0
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * len(values)))], 2)


def run(args) -> dict:
    """One arm; returns its record."""
    import multiprocessing

    import O4_Imagery_Utils as IMG
    import O4_UI_Utils as UI
    from o4_engine import imagery_follow as FOLLOW
    os.environ.pop(MACHINE_SLOTS.ENV_DIR, None)     # a session of its own
    UI.red_flag = False
    IMG.shared_tile_cache_dir = None
    IMG.textures_in_parallel = 2                    # the budget: 16 x 2
    context = multiprocessing.get_context("spawn")
    ports, counts = context.Queue(), context.Array("i", 2)
    child = context.Process(target=_serve, args=(ports, args.latency, counts),
                            daemon=True)
    child.start()
    port_a, port_b = ports.get(timeout=60)
    follow_p = _provider("TWA", port_a)
    drape_p = _provider("TWB", port_a if args.same_host else port_b)
    work = tempfile.mkdtemp(prefix="o4-follow-replay-", dir=args.tmp)
    index = os.path.join(work, "index.sqlite")
    _copy(args.index, index)
    stop = threading.Event()
    lags, ticks = [], []

    class Job(FOLLOW.FollowJob):
        def tick(self):
            ticks.append(time.monotonic())
            super().tick()

        def _landed(self, key, item, facts, now):
            if not self._stop.is_set():     # not the stop's last harvest
                lags.append(time.time() - now)
            super()._landed(key, item, facts, now)

    reader = Reader(args.lat, args.lon, args.track, args.speed, args.agl)
    lander = Lander(follow_p)
    job = Job(lambda event: None, reader=reader, lander=lander,
              index_path=index, max_slots=args.slots, cap_bytes=10 ** 15,
              log_path=None)     # a cap never reached: measured, no sweep
    threads = [threading.Thread(target=drape_worker, daemon=True,
                                args=(drape_p, stop, k))
               for k in range(args.drapes * 2)]
    threads += [threading.Thread(target=cpu_worker, daemon=True, args=(stop,))
                for _ in range(args.cpu_threads)]
    threads += [threading.Thread(target=py_worker, daemon=True, args=(stop,))
                for _ in range(args.py_threads)]
    kept = MACHINE_SLOTS.net_priority
    if args.no_priority:                        # the base: no precedence
        MACHINE_SLOTS.net_priority = _null
    import O4_Imagery_OnDemand_Index as INDEX
    import O4_Imagery_Spawn as SPAWN
    from o4_engine import imagery_follow_house as HOUSE
    kept_reads = (INDEX.all_rows, HOUSE.FLOOR_EVERY_S, SPAWN.core_wants,
                  Job.status)
    if args.base:       # the base tick's reads: every row, every time
        whole = SPAWN.core_wants
        INDEX.all_rows, HOUSE.FLOOR_EVERY_S = INDEX.rows, 0.0
        SPAWN.core_wants = (lambda rows, lat, lon, agl_m=0.0, tiles=None:
                            whole(rows, lat, lon, agl_m))
        Job.status = _base_status
    for thread in threads:
        thread.start()
    time.sleep(args.warmup)                     # the drapes under way first
    with counts.get_lock():
        start_counts = list(counts)
    if args.base:                               # the tick does the house's work
        job._thread = threading.Thread(target=_loop, args=(job,), daemon=True)
        job._thread.start()
    else:
        job.start()
    t0 = time.monotonic()
    time.sleep(args.seconds)
    elapsed = time.monotonic() - t0
    ticks.append(time.monotonic())              # the gap still open
    with counts.get_lock():
        done = [c - s for c, s in zip(counts, start_counts, strict=True)]
    stop.set()
    job.stop(timeout=30)
    MACHINE_SLOTS.net_priority = kept
    (INDEX.all_rows, HOUSE.FLOOR_EVERY_S, SPAWN.core_wants,
     Job.status) = kept_reads
    child.terminate()
    shutil.rmtree(work, ignore_errors=True)
    follow_req, drape_req = done
    gaps = [b - a for a, b in zip(ticks, ticks[1:], strict=False)]
    return {
        "arm": {"priority": not args.no_priority,
                "house": "base" if args.base else "thread",
                "slots": args.slots, "drapes": args.drapes,
                "same_host": args.same_host, "cpu_threads": args.cpu_threads,
                "py_threads": args.py_threads,
                "latency_s": args.latency},
        "seconds": round(elapsed, 1),
        "follow_req_s": round(follow_req / elapsed, 1),
        "drape_req_s": round(drape_req / elapsed, 1),
        "landed": job.counts["landed"], "late": job.counts["late"],
        "landed_per_min": round(60 * job.counts["landed"] / elapsed, 1),
        "harvest_lag_s": {"p50": _pct(lags, 0.5), "p95": _pct(lags, 0.95),
                          "max": round(max(lags), 2) if lags else 0.0},
        "tick_gap_s": {"p50": _pct(gaps, 0.5), "p95": _pct(gaps, 0.95),
                       "max": round(max(gaps), 2) if gaps else 0.0},
        "ticks": len(ticks) - 1,
    }


def _base_status(job) -> dict:
    """The status as the base built it: the sharp rows counted over the
    whole index at every tick."""
    import O4_Imagery_Tier_Plan as PLAN
    from o4_engine import imagery_follow as FOLLOW
    finest = len(PLAN.TIER_WIDTH) - 1
    job._sharp = sum(1 for r in job._rows.values()
                     if PLAN.tier_of_width(r["tier_px"]) == finest)
    return FOLLOW.FollowJob.status(job)


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _loop(job) -> None:
    """``FollowJob.run`` without starting the house thread."""
    job.open()
    while not job._stop.is_set():
        t0 = time.monotonic()
        try:
            job.tick()
        except Exception as error:      # as run() does
            print("tick_error", repr(error), file=sys.stderr)
        job._stop.wait(max(0.02, job.period_s - (time.monotonic() - t0)))
    job.close()


def build_parser() -> argparse.ArgumentParser:
    """The tool's arguments."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--index", required=True,
                        help="an on-demand index (copied; never written)")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--track", type=float, default=0.0)
    parser.add_argument("--speed", type=float, default=160.0)
    parser.add_argument("--agl", type=float, default=2300.0)
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--drapes", type=int, default=12)
    parser.add_argument("--same-host", action="store_true",
                        help="the drapes fetch from the follower's server")
    parser.add_argument("--cpu-threads", type=int, default=0,
                        help="threads of numpy and Python work")
    parser.add_argument("--py-threads", type=int, default=0,
                        help="threads of pure Python that never waits")
    parser.add_argument("--latency", type=float, default=0.67,
                        help="seconds per request (CYEG drapes: ~0.67)")
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--slots", type=int, default=4)
    parser.add_argument("--no-priority", action="store_true")
    parser.add_argument("--base", action="store_true",
                        help="the tick before the house (see above)")
    parser.add_argument("--tmp", default=None)
    parser.add_argument("--json", default=None)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    record = run(args)
    text = json.dumps(record)
    print(text)
    if args.json:
        with open(args.json, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
