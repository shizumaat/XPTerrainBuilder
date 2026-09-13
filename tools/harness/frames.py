#!/usr/bin/env python3
"""frames — THE FRAMES REGISTRY: where the captures, rebake plans and
built products a lane can replay against actually are, and what base sha
they were taken on.

Owner 2026-09-13: lanes spent turns hunting earlier lanes' captures in
session scratchpads ("the KCLT 1.0.324 frame lane v2unboxed used — check
its base"). The registry is an append-only JSONL (merge-friendly across
lane branches) at `docs/frames.jsonl`; a path that no longer exists is
reported as MISSING, never silently served.

    tools/harness/frames.py register --icao KCLT --kind capture \\
        --path /…/KCLT.pkl --base 864e7577 --lane v2roadramp [--note '…']
    tools/harness/frames.py list [ICAO] [--kind capture|rebake|patch|graded|mesh]
    tools/harness/frames.py latest ICAO --kind capture   # newest EXISTING entry

Kinds: `capture` (v2_solve_replay --capture pickle), `rebake` (the
o4_v2_rebake_ICAO.json plan), `patch` (an emitted *.patch.osm with its
sidecar), `graded` (ICAO.graded.json), `mesh` (a built Data*.mesh).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = os.path.join(ROOT, "docs", "frames.jsonl")
KINDS = ("capture", "rebake", "patch", "graded", "mesh")


def _load() -> list[dict]:
    if not os.path.exists(REGISTRY):
        return []
    out = []
    with open(REGISTRY, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def register(icao: str, kind: str, path: str, base: str, lane: str, note: str = "") -> dict:
    if kind not in KINDS:
        raise SystemExit(f"frames: kind must be one of {KINDS}")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise SystemExit(f"frames: refusing to register a path that does not exist: {path}")
    rec = {"icao": icao.upper(), "kind": kind, "path": path, "base": base, "lane": lane,
           "note": note, "at": _dt.datetime.now().isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
    with open(REGISTRY, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _fmt(r: dict) -> str:
    exists = os.path.exists(r["path"])
    flag = "" if exists else "  [MISSING]"
    note = f"  — {r['note']}" if r.get("note") else ""
    return f"{r['icao']:5s} {r['kind']:8s} base {r['base']:10s} lane {r['lane']:16s} {r['at']}  {r['path']}{flag}{note}"


def list_frames(icao: str | None, kind: str | None) -> list[dict]:
    rows = _load()
    if icao:
        rows = [r for r in rows if r["icao"] == icao.upper()]
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    return rows


def latest(icao: str, kind: str) -> dict | None:
    rows = [r for r in list_frames(icao, kind) if os.path.exists(r["path"])]
    return rows[-1] if rows else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    for k in ("--icao", "--kind", "--path", "--base", "--lane"):
        r.add_argument(k, required=True)
    r.add_argument("--note", default="")
    l = sub.add_parser("list"); l.add_argument("icao", nargs="?"); l.add_argument("--kind")
    t = sub.add_parser("latest"); t.add_argument("icao"); t.add_argument("--kind", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "register":
        print(_fmt(register(a.icao, a.kind, a.path, a.base, a.lane, a.note))); return 0
    if a.cmd == "list":
        rows = list_frames(a.icao, a.kind)
        for rec in rows:
            print(_fmt(rec))
        return 0
    if a.cmd == "latest":
        rec = latest(a.icao, a.kind)
        if rec is None:
            print(f"frames: no existing {a.kind} registered for {a.icao.upper()}", file=sys.stderr)
            return 1
        print(rec["path"]); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
