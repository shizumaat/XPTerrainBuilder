"""THE END-AREA LENGTH CENSUS — every runway END's end-area length
(``auto_patch_v2.model.end_area.end_area_lengths``) over a set of
registered captures, under the CURRENT tree and under a BASE ref's copy of
``model/end_area.py``, so a change to the end-area rule (RULINGS
2026-10-15g (C) drop, #1332 deep tier, #2276 rise) lists every airport
where it fires before a single replay is paid for.

    venv/bin/python tools/end_area_census.py --base origin/main A.pkl B.pkl ...
    venv/bin/python tools/end_area_census.py --registered [--base REF]

``--registered`` reads every capture ``tools/harness/frames.py`` lists
that exists on disk (the newest per ICAO).  Prints one row per end whose
length differs (``--all``: every end) and a JSON summary with ``--json``.
Read-only; loads each pickle once (they are ~1 GB: allow ~10 s each).
Promoted on its second use (#1332's 57-capture census, #2276)."""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E401,E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REL = "Ortho4XP/src/auto_patch_v2/model/end_area.py"


def base_module(ref: str):
    """``model/end_area.py`` at ``ref``, imported as a sibling module of
    the package (its relative imports resolve against the current tree)."""
    text = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{REL}"],
                          check=True, capture_output=True, text=True).stdout
    path = Path(ROOT / "tmp" / "end_area_base.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    name = "auto_patch_v2.model._end_area_base"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def registered_captures() -> list[Path]:
    """The newest existing capture per ICAO in the frames registry."""
    out = subprocess.run([sys.executable, str(ROOT.parent / "tools" / "harness" / "frames.py"),
                          "list", "--kind", "capture"], capture_output=True, text=True).stdout
    best: dict[str, tuple[str, Path]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 7 or "[MISSING]" in line:
            continue
        icao, stamp = parts[0], parts[5]
        pkl = next((Path(p) for p in parts if p.endswith(".pkl")), None)
        if pkl is None or not pkl.exists():
            continue
        if icao not in best or stamp > best[icao][0]:
            best[icao] = (stamp, pkl)
    return [p for _s, p in sorted(best.values(), key=lambda t: t[1].name)]


def census(pkls: list[Path], base_ref: str | None, show_all: bool) -> list[dict]:
    sys.path.insert(0, str(SRC))
    from auto_patch_v2.law import Law
    from auto_patch_v2.model import end_area as lane
    base = base_module(base_ref) if base_ref else None
    rows: list[dict] = []
    for pkl in pkls:
        with pkl.open("rb") as fh:
            cap = pickle.load(fh)
        icao, airport = cap["icao"], cap["airport"]
        law = Law.for_airport(icao)
        now = lane.end_area_lengths(airport, law)
        was = base.end_area_lengths(airport, law) if base else now
        for rid, lens in sorted(now.items()):
            for end, (a, b) in enumerate(zip(was.get(rid, lens), lens, strict=True)):
                row = {"icao": icao, "runway": rid, "end": end,
                       "base_m": round(a, 1), "lane_m": round(b, 1)}
                rows.append(row)
                if show_all or abs(a - b) > 1e-6:
                    print(f"{icao:5s} {rid:10s} end{end} {a:7.1f} -> {b:7.1f}"
                          + ("" if abs(a - b) <= 1e-6 else "   CHANGED"), flush=True)
        print(f"[{icao}] {len(now)} runway(s) read ({pkl})", flush=True)
        del cap
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pkls", nargs="*", type=Path)
    ap.add_argument("--registered", action="store_true")
    ap.add_argument("--base", default=None, help="git ref whose end_area.py is the base arm")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    # owner 2026-11-25: the census takes its memory on the machine ledger
    # before it loads anything (O4_Machine_Jobs; released at exit)
    import O4_Machine_Jobs as _jobs
    _jobs.admit_process("end_area_census")
    pkls = list(a.pkls) + (registered_captures() if a.registered else [])
    if not pkls:
        ap.error("no captures (name pickles or pass --registered)")
    rows = census(pkls, a.base, a.all)
    changed = [r for r in rows if abs(r["base_m"] - r["lane_m"]) > 1e-6]
    print(f"{len(rows)} end(s), {len(changed)} changed")
    if a.json:
        a.json.write_text(json.dumps({"rows": rows, "changed": changed}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
