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
        --path /…/KCLT.pkl --base 864e7577 --lane v2roadramp [--note '…'] [--copy]
    tools/harness/frames.py list [ICAO] [--kind capture|rebake|patch|graded|mesh]
    tools/harness/frames.py latest ICAO --kind capture   # newest EXISTING entry

Kinds: `capture` (v2_solve_replay --capture pickle), `rebake` (the
o4_v2_rebake_ICAO.json plan), `patch` (an emitted *.patch.osm with its
sidecar), `graded` (ICAO.graded.json), `mesh` (a built Data*.mesh).

DURABLE PATHS ONLY (issue #37, 2026-09-21): 279 of 282 registered frames
were MISSING after one reboot, because lanes registered products under
`/tmp` and session scratchpads, which a reboot purges.  `register` now
REFUSES a path outside the durable root — the shared data repo's
`.harness/frames/<lane>/` (`shared_repo_guard.HARNESS_STATE`, the same
always-allowed state directory the refresh ledger and the locks live in;
`O4_DATA_REPO` re-points it) — unless `--copy` is given, in which case the
file (or directory, e.g. a capture dir) is COPIED there, a `patch` brings
its `.axes.json` sidecar along, and the row points at the DURABLE copy
(`copied_from` keeps the original).  An existing destination is reused
only when it is byte-identical; otherwise it is refused, never overwritten.
Rows registered before this law are untouched; `list` marks any row whose
path is gone `[MISSING]`.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = os.path.join(ROOT, "docs", "frames.jsonl")
KINDS = ("capture", "rebake", "patch", "graded", "mesh")
SIDECAR_SUFFIX = ".axes.json"     # census.py: Path(str(osm) + ".axes.json")


def _harness_state() -> str:
    """The shared repo's ``.harness/`` — ONE resolution, the guard's own
    (``shared_repo_guard.HARNESS_STATE``, honouring ``O4_DATA_REPO``), so
    the durable root can never drift from the directory the guard always
    allows writes to."""
    spec = importlib.util.spec_from_file_location(
        "shared_repo_guard",
        os.path.join(ROOT, "Ortho4XP", "tools", "harness", "shared_repo_guard.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return str(mod.HARNESS_STATE)


#: Where a registered product must live to survive a reboot:
#: ``<data repo>/.harness/frames/<lane>/…``.  Monkeypatchable (tests).
DURABLE_ROOT = os.path.join(_harness_state(), "frames")


def durable_root() -> str:
    return DURABLE_ROOT


def is_durable(path: str) -> bool:
    """True iff ``path`` (symlinks resolved) lies under :func:`durable_root`."""
    root = os.path.realpath(durable_root())
    real = os.path.realpath(path)
    return real == root or real.startswith(root + os.sep)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_durable(path: str, lane: str, kind: str) -> tuple[str, list[str]]:
    """Copy ``path`` (file or directory) into ``<durable root>/<lane>/`` and
    return ``(durable_path, extra_files_copied)``.  A ``patch`` brings its
    ``.axes.json`` sidecar (without it every census degrades to the
    context-free frame that overcounts).  Never overwrites: an existing
    destination is reused only when byte-identical, otherwise REFUSED."""
    if not lane or os.sep in lane or lane in (".", "..") or lane.startswith("."):
        raise SystemExit(f"frames: --lane must be a bare name to copy under: {lane!r}")
    dest_dir = os.path.join(durable_root(), lane)
    dest = os.path.join(dest_dir, os.path.basename(path.rstrip(os.sep)))
    os.makedirs(dest_dir, exist_ok=True)
    extras: list[str] = []
    if os.path.isdir(path):
        if os.path.exists(dest):
            raise SystemExit(
                f"frames: refusing to overwrite an existing durable directory: {dest}\n"
                f"  (rename the source, or register {dest} as-is if it is the same frame)")
        shutil.copytree(path, dest, symlinks=False)
    else:
        if os.path.exists(dest):
            if not (os.path.isfile(dest) and _sha256(dest) == _sha256(path)):
                raise SystemExit(
                    f"frames: refusing to overwrite an existing durable file that "
                    f"differs: {dest}\n  (rename the source; a frame is never replaced in place)")
            # byte-identical: reuse
        else:
            shutil.copy2(path, dest)
        if kind == "patch":
            side = path + SIDECAR_SUFFIX
            if os.path.isfile(side):
                side_dest = dest + SIDECAR_SUFFIX
                if not os.path.exists(side_dest):
                    shutil.copy2(side, side_dest)
                extras.append(side_dest)
    return dest, extras


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


def register(icao: str, kind: str, path: str, base: str, lane: str, note: str = "",
             copy: bool = False) -> dict:
    if kind not in KINDS:
        raise SystemExit(f"frames: kind must be one of {KINDS}")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise SystemExit(f"frames: refusing to register a path that does not exist: {path}")
    copied_from = None
    if not is_durable(path):
        if not copy:
            raise SystemExit(
                f"frames: REFUSING to register a NON-DURABLE path: {path}\n"
                f"  A reboot purges /tmp and session scratchpads (279 of 282 registered "
                f"frames were MISSING after one, issue #37).  Register products under "
                f"the durable root {durable_root()}/<lane>/ — or pass --copy to copy "
                f"this one there and register the copy.")
        copied_from = path
        path, extras = _copy_durable(path, lane, kind)
        print(f"frames: copied {copied_from} -> {path}"
              + (f" (+ {', '.join(os.path.basename(e) for e in extras)})" if extras else ""),
              file=sys.stderr)
    rec = {"icao": icao.upper(), "kind": kind, "path": path, "base": base, "lane": lane,
           "note": note, "at": _dt.datetime.now().isoformat(timespec="seconds")}
    if copied_from:
        rec["copied_from"] = copied_from
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
    r.add_argument("--copy", action="store_true",
                   help="copy a non-durable path (/tmp, scratchpad, lane tree) into "
                        "<data repo>/.harness/frames/<lane>/ and register the copy")
    l = sub.add_parser("list"); l.add_argument("icao", nargs="?"); l.add_argument("--kind")
    t = sub.add_parser("latest"); t.add_argument("icao"); t.add_argument("--kind", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "register":
        print(_fmt(register(a.icao, a.kind, a.path, a.base, a.lane, a.note, copy=a.copy))); return 0
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
