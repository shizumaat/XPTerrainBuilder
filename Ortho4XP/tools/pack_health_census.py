#!/usr/bin/env python3
"""THE PACK HEALTH CENSUS (issue #1978): every installed scenery pack,
counted for the vendor defects the pack health check repairs — the
engine's own detectors (``auto_patch_v2.airport.pack_health``), so it
prints what a build would find.

    venv/bin/python tools/pack_health_census.py SCENERY_DIR
        [--pack SUBSTRING ...] [--top 20] [--workers 6] [--json OUT]
        [--no-dsf] [--no-objects]

* OBJECTS — every ``.obj`` of every pack (the PRISTINE file: its
  ``.anchor_bak`` when one exists; never a split body or a copy of
  ours): the malformed ``LIGHT_*`` records (``light_records``), each
  "completed" or "dropped".  The engine repairs those its airport packs'
  DSFs place by a pack path; a library pack's are counted here only.
* DSFs — every tile DSF of every AIRPORT pack (one with
  ``Earth nav data/apt.dat``; the standard ``Earth nav data/<bucket>/``
  layout only), pristine likewise, dumped with DSFTool to a temp folder:
  the duplicate and stacked line / draped-polygon placements
  (``stacked_polygons``) and the busiest spot.

READ-ONLY on the install: nothing is written there; the dumps go to a
temp folder removed afterwards.  Prints one row per pack, worst first,
and the totals.  Twin: ``tests/test_pack_health.py``.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

from auto_patch_v2.airport.pack_health import light_records as LR  # noqa: E402
from auto_patch_v2.airport.pack_health import objects as OB  # noqa: E402
from auto_patch_v2.airport.pack_health import stacked_polygons as SP  # noqa: E402

BAK = ".anchor_bak"
_SKIP_DIRS = {"Earth nav data", "terrain", "textures", "Textures"}


def _pristine(path: str) -> str:
    return path + BAK if os.path.isfile(path + BAK) else path


def objects_of(pack_root: str) -> dict:
    """``{pack-relative obj: {"completed": n, "dropped": n}}``."""
    out: dict = {}
    for d, subs, files in os.walk(pack_root):
        subs[:] = [s for s in subs if s not in _SKIP_DIRS]
        for f in files:
            if not f.lower().endswith(".obj") or OB._ours(f):
                continue
            phys = os.path.join(d, f)
            try:
                with open(_pristine(phys), "rb") as fh:
                    raw = fh.read().decode("latin-1")
            except OSError:
                continue
            if "LIGHT" not in raw:
                continue
            found = LR.check_lines(raw.replace("\r\n", "\n").split("\n"))
            if found:
                out[os.path.relpath(phys, pack_root)] = {
                    a: sum(x.action == a for x in found)
                    for a in ("completed", "dropped")}
    return out


def dsfs_of(pack_root: str, tool: str, work: str) -> dict:
    """``{pack-relative dsf: report}`` for an airport pack's tile DSFs."""
    nav = os.path.join(pack_root, "Earth nav data")
    if not os.path.isfile(os.path.join(nav, "apt.dat")):
        return {}
    out: dict = {}
    for bucket in sorted(os.listdir(nav)):
        bdir = os.path.join(nav, bucket)
        if not os.path.isdir(bdir):
            continue
        for f in sorted(os.listdir(bdir)):
            if not f.endswith(".dsf"):
                continue
            dump = os.path.join(work, f"{os.getpid()}_{f}.txt")
            try:
                subprocess.run([tool, "--dsf2text", _pristine(os.path.join(bdir, f)),
                                dump], capture_output=True, timeout=900, check=False)
                with open(dump, encoding="utf-8", errors="surrogateescape") as fh:
                    rep = SP.scan(fh.read().splitlines())
            except (OSError, subprocess.SubprocessError) as exc:
                out[f"{bucket}/{f}"] = {"error": str(exc)}
                continue
            finally:
                if os.path.exists(dump):
                    os.remove(dump)
            if rep.dropped:
                out[f"{bucket}/{f}"] = {
                    "dropped": rep.dropped, "duplicates": rep.duplicates,
                    "stacked": rep.stacked, "site": list(rep.site),
                    "by_def": dict(sorted(rep.by_def.items(),
                                          key=lambda kv: -kv[1])[:3])}
    return out


def _one(args: tuple) -> tuple[str, dict]:
    pack_root, tool, work, do_obj, do_dsf = args
    row: dict = {}
    if do_obj:
        row["objects"] = objects_of(pack_root)
    if do_dsf and tool:
        row["dsfs"] = dsfs_of(pack_root, tool, work)
    return os.path.basename(pack_root), row


def _totals(row: dict) -> tuple[int, int, int]:
    lights = sum(v["completed"] + v["dropped"] for v in row.get("objects", {}).values())
    dsfs = [v for v in row.get("dsfs", {}).values() if "dropped" in v]
    return (lights, sum(v["duplicates"] for v in dsfs),
            sum(v["stacked"] for v in dsfs))


def main(argv: list[str] | None = None) -> int:
    import O4_Console_Encoding as CE  # UTF-8 before anything prints (#171)
    CE.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scenery_dir")
    ap.add_argument("--pack", action="append", default=[],
                    help="only packs whose name contains this (repeatable)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--json", default="")
    ap.add_argument("--no-dsf", action="store_true")
    ap.add_argument("--no-objects", action="store_true")
    a = ap.parse_args(argv)
    from auto_patch import dsf_reader as _DSFR
    tool = "" if a.no_dsf else (_DSFR._dsftool_path() or "")
    packs = sorted(os.path.join(a.scenery_dir, p) for p in os.listdir(a.scenery_dir)
                   if os.path.isdir(os.path.join(a.scenery_dir, p))
                   and (not a.pack or any(s in p for s in a.pack)))
    work = tempfile.mkdtemp(prefix="o4_health_census_")
    try:
        jobs = [(p, tool, work, not a.no_objects, bool(tool)) for p in packs]
        with mp.Pool(max(1, a.workers)) as pool:
            rows = dict(pool.imap_unordered(_one, jobs, chunksize=8))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ranked = sorted(((sum(_totals(r)), n) for n, r in rows.items() if sum(_totals(r))),
                    reverse=True)
    lights = dup = stk = 0
    for r in rows.values():
        t = _totals(r)
        lights, dup, stk = lights + t[0], dup + t[1], stk + t[2]
    print(f"packs {len(rows)}; with a defect {len(ranked)}; light records "
          f"{lights:,}; duplicate placements {dup:,}; stacked slivers {stk:,}")
    print(f"{'total':>9} {'lights':>7} {'dups':>9} {'stacked':>8}  pack (worst DSF / object)")
    for total, name in ranked[:a.top]:
        r = rows[name]
        t = _totals(r)
        dsfs = [(v.get("dropped", 0), k, v) for k, v in r.get("dsfs", {}).items()]
        worst = max(dsfs)[1:] if dsfs else None
        objs = sorted(r.get("objects", {}).items(),
                      key=lambda kv: -(kv[1]["completed"] + kv[1]["dropped"]))
        where = (f"{worst[0]} site {worst[1].get('site')}" if worst
                 else (objs[0][0] if objs else ""))
        print(f"{total:>9,} {t[0]:>7,} {t[1]:>9,} {t[2]:>8,}  {name}  [{where}]")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
