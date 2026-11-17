#!/usr/bin/env python3
"""THE SUNK-WALL CENSUS (#2120 R2, spec ``docs/specs/2120-R2.md`` §2): every
pack wall the wall class admits by its FOURTH witness
(``auto_patch_v2/airport/sunk_frame.sunk_wall``: a block drawn down from its
author's ground, the ground stepping across it), over capture pickles.

For each ``v2_solve_replay --capture`` pickle it runs the ONE classifier,
``airport/wall_class.wall_class_components`` (the shipped ``[service]`` law),
and lists every retaining component the sunk witness read: unit, placement
id, resource, lift, rule (``upper`` R2 / ``plate`` R3), its class
(2120-W3 §2: ``A`` a retaining block, ``B`` a deck block -- only the strip
along its upper face retains, its plan a deck over the low ground), its upper
ground's authored ``y``, the height it retains, the plan's area and its
lat/lon.
Reads only; builds nothing.

    venv/bin/python tools/sunk_census.py CAP.pkl [CAP.pkl ...]
    venv/bin/python tools/sunk_census.py --registered [--icao ICAO ...]

``--registered`` reads every capture ``docs/frames.jsonl`` names (newest per
ICAO, missing files skipped).
"""
from __future__ import annotations

import argparse
import gzip
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()
from auto_patch_v2.airport.wall_class import wall_class_components  # noqa: E402
from auto_patch_v2.classify.rules import load_rules  # noqa: E402

LEDGER = ROOT.parent / "docs" / "frames.jsonl"


def sunk_rows(airport, cfg) -> list[dict]:
    """One row per wall-class component the sunk witness admitted
    (``WallComponent.sunk_rule``)."""
    from shapely.ops import unary_union
    lift = {str(m.id): float(u.agl_m) for u in airport.partition.units for m in u.members}
    unit = {str(m.id): str(u.id) for u in airport.partition.units for m in u.members}
    to_ll = airport.frame.transformers()[1]
    rows = []
    for c in wall_class_components(airport, cfg):
        if not c.retains or not c.sunk_rule:
            continue
        oid = str(c.member.id)
        g = unary_union(c.cover or c.pieces)
        lat, lon = to_ll(g.centroid.x, g.centroid.y)
        rows.append({"unit": unit.get(oid, ""), "id": oid,
                     "resource": str(c.resource).rsplit("/", 1)[-1],
                     "lift": round(lift.get(oid, 0.0), 2), "rule": c.sunk_rule,
                     "class": "B" if c.cover else "A",
                     "y_up": round(float(c.retained_top_y), 2),
                     "retained_m": round(c.retained_m, 2),
                     "top_y": None if c.top_y is None else round(c.top_y, 2),
                     "area_m2": int(round(g.area)), "lat": round(lat, 6), "lon": round(lon, 6)})
    return rows


def registered(icaos: set[str] | None = None) -> list[str]:
    """The newest registered capture per ICAO that is still on disk."""
    newest: dict = {}
    for line in LEDGER.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("kind") != "capture" or (icaos and row.get("icao") not in icaos):
            continue
        if Path(row["path"]).is_file() and row.get("at", "") >= newest.get(row["icao"], ("",))[0]:
            newest[row["icao"]] = (row.get("at", ""), row["path"])
    return [p for _a, p in sorted(newest.values(), key=lambda t: t[1])]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("captures", nargs="*")
    ap.add_argument("--registered", action="store_true")
    ap.add_argument("--icao", action="append", default=None)
    a = ap.parse_args(argv)
    paths = list(a.captures) + (registered(set(a.icao) if a.icao else None)
                                if a.registered else [])
    cfg = load_rules().service
    for path in paths:
        t = time.time()
        try:
            with (gzip.open if path.endswith(".gz") else open)(path, "rb") as fh:
                cap = pickle.load(fh)
            rows = sunk_rows(cap["airport"], cfg)
        except Exception as e:  # noqa: BLE001 -- a stale capture is reported, never fatal
            print(f"== {path}: UNREAD ({type(e).__name__}: {e})")
            continue
        print(f"== {cap.get('icao', '?')} {path}: {len(rows)} sunk wall(s) "
              f"({time.time() - t:.0f} s)")
        for r in rows:
            print(f"   {r['unit']:10s} {r['id']:14s} lift {r['lift']:+7.2f} "
                  f"{r['rule']:5s} {r['class']} "
                  f"y_up {r['y_up']:6.2f} top {r['top_y']} retained {r['retained_m']:5.2f} "
                  f"area {r['area_m2']:6d} @{r['lat']},{r['lon']} {r['resource']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
