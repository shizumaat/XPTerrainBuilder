#!/usr/bin/env python3
"""Command reply latency and per-process CPU of the engine while N tiles
build (lane lscale, owner 2026-11-20T18:33-18:40Z: "an active dialog
should take precedence over any builds which should be in the
background").

Starts this checkout's engine over its JSON-lines pipe (``Ortho4XP.py
--engine-jsonl``, the app's transport), sends one ``build`` of the given
tiles, and until ``RunDone`` (or ``--seconds``) every ``--every`` seconds:

* sends a dialog answer (``slow_step_choice`` "continue" for the first
  tile: the command a SlowStep card's button sends) and a synchronous
  read (``tile_customizations``), and records each reply's round trip;
* samples ``ps`` for the engine's process tree: the command process and
  every descendant (build workers, their pools), %CPU and nice.

Prints one JSON record: reply latency p50/p95/max per command, the
command process's mean %CPU and CPU seconds, the descendants' summed
%CPU, the nice values, the descendant count, the run's wall seconds.
Writes nothing but what the build writes (the checkout's own Tiles
folder).  Time it in the foreground with ``O4_DEV_NICE=0`` (the dev venv
runs every process at nice 15 otherwise, which flattens the priorities).

    cd Ortho4XP && O4_DEV_NICE=0 venv/bin/python tools/engine_build_latency.py \\
        --tile 21 -160 --tile 22 -160 [--imagery] [--seconds 900] [--every 0.5]
"""
from __future__ import annotations

import argparse
import json
import os

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py`` (twin: ``tests/test_console_encoding.py``).
import os as _o4os  # noqa: E401,E402
import statistics
import subprocess
import sys
import sys as _o4sys
import threading
import time

_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tree(root_pid: int) -> dict:
    """``{pid: (ppid, pcpu, nice, cpu_seconds)}`` of ``root_pid``'s tree."""
    text = subprocess.run(["ps", "-axo", "pid=,ppid=,pcpu=,nice=,time="],
                          capture_output=True, text=True).stdout
    rows = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        seconds = 0.0
        for piece in parts[4].replace("-", ":").split(":"):
            seconds = seconds * 60 + float(piece)
        rows[int(parts[0])] = (int(parts[1]), float(parts[2]),
                               int(parts[3]), seconds)
    keep, frontier = {}, [root_pid]
    while frontier:
        pid = frontier.pop()
        if pid in rows and pid not in keep:
            keep[pid] = rows[pid]
            frontier.extend(p for p, r in rows.items() if r[0] == pid)
    return keep


def _quantiles(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(ordered),
            "p50_ms": round(1000 * statistics.median(ordered), 1),
            "p95_ms": round(1000 * ordered[int(0.95 * (len(ordered) - 1))], 1),
            "max_ms": round(1000 * ordered[-1], 1)}


class _Engine:
    """The engine over its pipe: replies matched to their sends."""

    def __init__(self):
        self.process = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "Ortho4XP.py"),
             "--engine-jsonl"],
            cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
            # A lane's run on the machine memory ledger: it yields to the
            # owner's app builds (O4_Machine_Memory.claim stands).
            env=dict(os.environ, O4_MEMORY_ROLE="lane",
                     O4_MEMORY_LABEL="lane engine_build_latency"))
        self.latency, self.sent_at = {}, {}
        self.done, self.hello = threading.Event(), threading.Event()
        self._sent, self._lock, self._id = {}, threading.Lock(), 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            event = message.get("event")
            if event == "EngineHello":
                self.hello.set()
            elif event == "RunDone":
                self.done.set()
            if "reply" in message:
                with self._lock:
                    entry = self._sent.pop(message["reply"], None)
                if entry is not None:
                    self.latency.setdefault(entry[0], []).append(
                        time.time() - entry[1])
                    self.sent_at.setdefault(entry[0], []).append(entry[1])
        self.done.set()

    def send(self, command, **fields):
        with self._lock:
            self._id += 1
            self._sent[self._id] = (command, time.time())
            line = json.dumps(dict(fields, cmd=command, id=self._id))
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def close(self):
        try:
            self.send("shutdown")
            self.process.wait(30)
        except Exception:
            self.process.kill()


def _sample(engine, tiles, seconds, every):
    """Probe and sample until RunDone or ``seconds``; the raw series."""
    pid = engine.process.pid
    series = {"command": [], "children": [], "pids": set(), "nice": {},
              "cpu": {}}
    started = time.time()
    while not engine.done.is_set() and time.time() - started < seconds:
        engine.send("slow_step_choice", lat=tiles[0][0], lon=tiles[0][1],
                    choice="continue")
        engine.send("tile_customizations", lat=tiles[0][0],
                    lon=tiles[0][1])
        tree = _tree(pid)
        if pid in tree:
            series["command"].append(tree[pid][1])
            series["nice"]["command"] = tree[pid][2]
        children = {p: r for p, r in tree.items() if p != pid}
        series["children"].append(sum(r[1] for r in children.values()))
        series["pids"].update(children)
        series["nice"].setdefault("children", set()).update(
            r[2] for r in children.values())
        series["cpu"].update({p: r[3] for p, r in tree.items()})
        time.sleep(every)
    series["wall"] = time.time() - started
    series["run_done"] = engine.done.is_set()
    series["started"] = started
    return series


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tile", nargs=2, type=int, action="append",
                        required=True, metavar=("LAT", "LON"))
    parser.add_argument("--imagery", action="store_true",
                        help="build imagery too (downloads)")
    parser.add_argument("--provider", default="BI")
    parser.add_argument("--zoomlevel", type=int, default=16)
    parser.add_argument("--seconds", type=float, default=900.0)
    parser.add_argument("--every", type=float, default=0.5)
    args = parser.parse_args(argv)
    engine = _Engine()
    if not engine.hello.wait(120):
        print(json.dumps({"error": "engine did not say hello"}))
        engine.process.kill()
        return 1
    tiles = [list(tile) for tile in args.tile]
    engine.send("build", tiles=tiles, provider=args.provider,
                zoomlevel=args.zoomlevel, custom_build_dir="",
                do_vector=True, do_imagery=args.imagery, do_overlays=False,
                missing_art="leave")
    series = _sample(engine, tiles, args.seconds, args.every)
    engine.close()
    pid = engine.process.pid
    probes = [(round(at - series["started"], 1), round(1000 * lag, 1))
              for at, lag in zip(engine.sent_at.get("slow_step_choice", ()),
                                 engine.latency.get("slow_step_choice", ()), strict=False)]
    print(json.dumps({
        "tiles": tiles, "wall_s": round(series["wall"], 1),
        "run_done": series["run_done"],
        "build_reply_ms": round(1000 * engine.latency["build"][0], 1)
        if engine.latency.get("build") else None,
        "latency": {k: _quantiles(v) for k, v in engine.latency.items()
                    if k in ("slow_step_choice", "tile_customizations")},
        # the dialog answers slower than 100 ms: (seconds into the run, ms)
        "slow_dialog_answers": [p for p in probes if p[1] > 100.0][:20],
        "command_process": {
            "mean_pcpu": round(statistics.mean(series["command"]), 1)
            if series["command"] else None,
            "cpu_s": round(series["cpu"].get(pid, 0.0), 1)},
        "descendants": {
            "count": len(series["pids"]),
            "mean_pcpu_sum": round(statistics.mean(series["children"]), 1)
            if series["children"] else None,
            "cpu_s_last_seen": round(sum(
                s for p, s in series["cpu"].items() if p != pid), 1)},
        "nice": {"command": series["nice"].get("command"),
                 "children": sorted(series["nice"].get("children", ()))},
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
