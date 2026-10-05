"""THE PLANAR STAGE'S PACK READS, ALONE — hashed and timed off a capture
(issue #362; promoted from lane ``parplanar``'s scratch ``planar_arm.py`` on
its second use).

    cd Ortho4XP && venv/bin/python tools/planar_read_arm.py CAPTURE.pkl \
        [--workers N] [--reader-cap M] [--no-field] [--json OUT.json]

Off a ``v2_solve_replay --capture`` pickle it reads the pack's objects as the
replay's ``--from planar`` prelude does (one quantised ``ResourceCache``),
then makes the CLASSIFICATION-FREE reads exactly as ``planar/build`` asks
for them (``planar/pack_reads``: tunnel corridors, thin plates, door wells,
sunken roads, wall corridors) under a pinned work-pool budget, and prints

* a sha256 per reading — its records and its stats WITHOUT the clocks —
  and one over everything a later pass reads off the cache: the readings,
  ``frame_entry``'s fallback rungs, the at-grade stats (calls, unions,
  vertices, resources) and the memo sizes;
* the readers' own seconds, the pool's account, the load average and the
  peak resident memory of this process + its workers (sampled once a
  second through ``ps``).

The wall corridors are read under THE FIELD (ramps spec §12h (4)): the
cover of the capture's own classification, derived as ``planar/build``
derives it and handed to the pool and the one-core read alike.
``--no-field`` leaves FIELD not read.  ``wall_records`` is the sha of the
corridor RECORDS alone (what a build consumes); ``wall_corridors`` hashes
them with their stats, whose admission lines change with a clause's wording.

``--reader-cap M`` replaces ``reader_work.MAX_WORKERS`` for the arm — the
worker-count sweep that number is set from (1 / 2 / 4 / 8 / N).

Two runs at two ``--workers`` are the serial / pooled identity arm of a
change to the readers; it is seconds against a 9-minute replay.  NOT a
build and NOT a census: it prices no law and counts no defects.

Twin: ``tests/auto_patch_v2/test_parplanar.py``.
"""
from __future__ import annotations

import argparse
import dataclasses as dc
import hashlib
import json
import os
import pickle
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

__all__ = ["canon", "sha", "reading", "PeakRss", "main"]

READINGS = ("tunnels", "plates", "door_wells", "sunken_roads", "wall_corridors")


def canon(v):
    """``v`` as JSON-able data that is the same in every process: geometry
    as WKB hex, floats by ``repr``, sets sorted, clocks (``*_s``,
    ``seconds``) dropped from dataclasses."""
    if hasattr(v, "wkb_hex"):
        return v.wkb_hex
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (tuple, list)):
        return [canon(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted(canon(x) for x in v)
    if isinstance(v, dict):
        return {str(k): canon(x) for k, x in v.items()}
    if dc.is_dataclass(v) and not isinstance(v, type):
        return {f.name: canon(getattr(v, f.name)) for f in dc.fields(v)
                if not f.name.endswith("_s") and f.name != "seconds"}
    if hasattr(v, "tolist"):
        return canon(v.tolist())
    return v


def sha(v) -> str:
    return hashlib.sha256(json.dumps(canon(v), sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


#: the process table per platform: one ``pid ppid resident-KiB`` line each
_PROCESS_TABLE = {
    "posix": ["ps", "-axo", "pid=,ppid=,rss="],
    "nt": ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "Get-CimInstance Win32_Process | ForEach-Object { '{0} {1} {2}' -f "
           "$_.ProcessId, $_.ParentProcessId, [long]($_.WorkingSetSize / 1024) }"],
}


def process_rows() -> list[tuple[int, int, int]]:
    """``[(pid, ppid, resident KiB)]`` of every process on this machine —
    ``ps`` on POSIX, CIM on Windows (which has no ``ps``; Git bash's is
    another program) — or nothing where the table cannot be read."""
    cmd = _PROCESS_TABLE.get(os.name)
    if cmd is None:
        return []
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows = (ln.split() for ln in out.splitlines())
    return [(int(r[0]), int(r[1]), int(r[2])) for r in rows
            if len(r) == 3 and all(f.isdigit() for f in r)]


def load_average() -> list[float] | None:
    """The system load averages, or ``None`` where the platform keeps none
    (``os.getloadavg`` does not exist on Windows)."""
    try:
        return list(os.getloadavg())
    except (AttributeError, OSError):
        return None


class PeakRss:
    """The peak of (this process + its descendants) resident memory while
    the block runs, sampled once a second: ``gb`` — ``{"sum", "parent",
    "worker_max", "workers"}`` at the peak of the sum (a clock-like
    reading: never identity)."""

    def __init__(self, every_s: float = 1.0) -> None:
        self.gb = {"sum": 0.0, "parent": 0.0, "worker_max": 0.0, "workers": 0}
        self._every, self._stop = every_s, threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "PeakRss":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(5.0)

    def sample(self) -> None:
        rows = process_rows()
        if not rows:
            return                                   # no table here: no reading
        kids: dict[int, list] = {}
        rss = {}
        for pid, ppid, kb in rows:
            kids.setdefault(ppid, []).append(pid)
            rss[pid] = kb / 1048576.0
        me = os.getpid()
        workers = []
        stack = list(kids.get(me, ()))
        while stack:
            pid = stack.pop()
            stack += kids.get(pid, ())
            if rss[pid] >= 0.05:                     # not the ps, not the tracker
                workers.append(rss[pid])
        total = rss.get(me, 0.0) + sum(workers)
        if total > self.gb["sum"]:
            self.gb = {"sum": round(total, 2), "parent": round(rss.get(me, 0.0), 2),
                       "worker_max": round(max(workers, default=0.0), 2),
                       "workers": len(workers)}

    def _run(self) -> None:
        while not self._stop.wait(self._every):
            self.sample()


def reading(airport, objects, cache, law, field=None) -> dict:
    """The record of one arm (module doc) under the pool budget in force;
    ``timing`` is the only key that is not identity.  ``field`` is the wall
    corridors' FIELD cover (``wall_mouth.WallField``, ramps spec §12h (4));
    ``None`` leaves FIELD not read, which the record says (``field``)."""
    from auto_patch_v2.airport import frame_entry as fe
    from auto_patch_v2.planar import pack_reads as PR
    fe.reset_rung_counts()
    t = time.perf_counter()
    with PeakRss() as peak:
        pr = PR.pack_reads(airport, objects, cache, law, walls=True, field=field)
        t_reads = time.perf_counter() - t
        walls, wstats = PR.wall_corridor_reads(airport, objects, cache, law, field)
        t_all = time.perf_counter() - t
    rec = {
        "tunnels": sha([pr.corridors, pr.tunnel_stats]),
        "plates": sha([pr.plates, pr.plate_stats]),
        "door_wells": sha([pr.wells, pr.door_stats]),
        "sunken_roads": sha([pr.roads, pr.road_stats]),
        "wall_corridors": sha([walls, wstats]),
        # the RECORDS alone: what a build consumes — the stats beside them
        # carry the admission lines, which change when a clause is reworded
        "wall_records": sha(walls),
        "field": {"read": wstats.field_read, "cells": wstats.field_cells},
        "rungs": {k: list(v) for k, v in sorted(fe.rung_counts().items())},
        "grade": canon(cache.grade),
        "memos": {"grade": len(cache.grade_memo), "cover": len(cache.cover_memo),
                  "clip": len(cache.clip_memo)},
        "counts": {"corridors": len(pr.corridors), "plates": len(pr.plates),
                   "wells": len(pr.wells), "roads": len(pr.roads), "walls": len(walls)},
    }
    rec["all"] = sha(rec)
    rec["timing"] = {"pack_reads_s": round(t_reads, 2), "with_walls_s": round(t_all, 2),
                     "reader_clock_s": {"tunnels_signature": pr.tunnel_stats.signature_s,
                                        "plates": pr.plate_stats.read_s,
                                        "door": pr.door_stats.read_s,
                                        "sunken": pr.road_stats.read_s,
                                        "walls": wstats.read_s},
                     "pool": PR.pool_report(cache), "loadavg": load_average(),
                     "peak_rss_gb": peak.gb}
    return rec


def main() -> int:
    # the console is UTF-8 before anything prints (#171; ONE derivation site)
    import O4_Console_Encoding as _o4console
    _o4console.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture")
    ap.add_argument("--workers", type=int, default=None, metavar="N",
                    help="pin the work-pool budget (1 = one core; default: every core)")
    ap.add_argument("--reader-cap", type=int, default=None, metavar="M",
                    help="replace reader_work.MAX_WORKERS for this arm (the sweep it is set from)")
    ap.add_argument("--no-field", action="store_true",
                    help="read the wall corridors WITHOUT the capture's classified cover "
                         "(FIELD not read, ramps spec §12h (4)); default: the capture's own")
    ap.add_argument("--json", default=None, metavar="OUT")
    a = ap.parse_args()
    from auto_patch_v2.airport import frame_entry as fe
    from auto_patch_v2.airport import pool as P
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.basins import read_objects
    with open(a.capture, "rb") as fh:
        cap = pickle.load(fh)
    icao, airport = cap["icao"], cap["airport"]
    law = Law.for_airport(icao)
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
    t = time.perf_counter()
    objects, _rep = read_objects(airport, law, cache)
    if a.workers is not None:
        P.configure(a.workers)
    if a.reader_cap is not None:
        from auto_patch_v2.airport import reader_work
        reader_work.MAX_WORKERS = max(1, a.reader_cap)
    print(f"[{icao}] objects {len(objects)} read {time.perf_counter() - t:.1f} s; "
          f"work-pool budget {P.budget()} (cores {os.cpu_count()})", flush=True)
    field = None
    if not a.no_field and cap.get("cl") is not None:
        from auto_patch_v2.planar.structure_approach import wall_field
        field = wall_field(cap["cl"], law)
    print(f"[{icao}] wall-corridor field: "
          + ("NOT READ" if field is None else f"{len(field.polys)} cells of the capture's "
             f"classification, standoff {field.standoff_m:g} m"), flush=True)
    rec = reading(airport, objects, cache, law, field)
    rec["timing"]["budget"] = P.budget()
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, default=str)
    for k in READINGS + ("wall_records", "all"):
        print(f"  {k:15s} {rec[k]}")
    g = rec["grade"]
    print(f"  rungs {rec['rungs']}  at-grade calls {g['calls']} unions {g['unions']} "
          f"vertices {g['vertices']} resources {len(g['resources'])}  memos {rec['memos']}")
    print(f"  counts {rec['counts']}")
    print(f"  timing {json.dumps(rec['timing'], default=str)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
