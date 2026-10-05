"""THE PLANAR STAGE'S PACK READS, ALONE — hashed and timed off a capture
(issue #362; promoted from lane ``parplanar``'s scratch ``planar_arm.py`` on
its second use).

    cd Ortho4XP && venv/bin/python tools/planar_read_arm.py CAPTURE.pkl \
        [--workers N] [--json OUT.json]

Off a ``v2_solve_replay --capture`` pickle it reads the pack's objects as the
replay's ``--from planar`` prelude does (one quantised ``ResourceCache``),
then makes the CLASSIFICATION-FREE reads exactly as ``planar/build`` asks
for them (``planar/pack_reads``: tunnel corridors, thin plates, door wells,
sunken roads, wall corridors) under a pinned work-pool budget, and prints

* a sha256 per reading — its records and its stats WITHOUT the clocks —
  and one over everything a later pass reads off the cache: the readings,
  ``frame_entry``'s fallback rungs, the at-grade stats (calls, unions,
  vertices, resources) and the memo sizes;
* the readers' own seconds, the pool's account and the load average.

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
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

__all__ = ["canon", "sha", "reading", "main"]

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


def reading(airport, objects, cache, law) -> dict:
    """The record of one arm (module doc) under the pool budget in force;
    ``timing`` is the only key that is not identity."""
    from auto_patch_v2.airport import frame_entry as fe
    from auto_patch_v2.planar import pack_reads as PR
    fe.reset_rung_counts()
    t = time.perf_counter()
    pr = PR.pack_reads(airport, objects, cache, law, walls=True)
    t_reads = time.perf_counter() - t
    walls, wstats = PR.wall_corridor_reads(airport, objects, cache, law)
    t_all = time.perf_counter() - t
    rec = {
        "tunnels": sha([pr.corridors, pr.tunnel_stats]),
        "plates": sha([pr.plates, pr.plate_stats]),
        "door_wells": sha([pr.wells, pr.door_stats]),
        "sunken_roads": sha([pr.roads, pr.road_stats]),
        "wall_corridors": sha([walls, wstats]),
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
                     "pool": PR.pool_report(cache), "loadavg": list(os.getloadavg())}
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture")
    ap.add_argument("--workers", type=int, default=None, metavar="N",
                    help="pin the work-pool budget (1 = one core; default: every core)")
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
    print(f"[{icao}] objects {len(objects)} read {time.perf_counter() - t:.1f} s; "
          f"work-pool budget {P.budget()} (cores {os.cpu_count()})", flush=True)
    rec = reading(airport, objects, cache, law)
    rec["timing"]["budget"] = P.budget()
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, default=str)
    for k in READINGS + ("all",):
        print(f"  {k:15s} {rec[k]}")
    g = rec["grade"]
    print(f"  rungs {rec['rungs']}  at-grade calls {g['calls']} unions {g['unions']} "
          f"vertices {g['vertices']} resources {len(g['resources'])}  memos {rec['memos']}")
    print(f"  counts {rec['counts']}")
    print(f"  timing {json.dumps(rec['timing'], default=str)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
