#!/usr/bin/env python3
"""BASE-VS-BRANCH DIFF OF DRY STRUCTURE REPLAYS (``--stage structures``).

The bar a structure lane is held to is "the existing records are
BYTE-IDENTICAL": a lane that adds a new structure class must show that
every ``Tunnel`` and ``Basin`` record the engine already built is
unchanged, ``replaced_ways`` and all, and that the only refusals that
appeared are its own pass's.  This compares the ``structures.json`` two
arms wrote for the same airports and says so per airport.

    venv/bin/python tools/structure_replay_diff.py \\
        --base /tmp/lane/base --branch /tmp/lane/br \\
        --icao OTHH LEMD HECA KCLT CYXY SPJC \\
        [--keys tunnels basins] [--own-marks '§45' 'channel:'] [--json]

``--base`` / ``--branch`` are the directories holding one
``<ICAO>/structures.json`` each (the ``--out`` of ``python -m
auto_patch_v2.planar ICAO --stage structures``), or, with
``--prefix``, one directory holding ``base_<ICAO>/`` and ``br_<ICAO>/``.

``--own-marks`` names the substrings that identify the LANE'S OWN
refusal lines; any refusal the branch added that carries none of them is
a foreign refusal and fails the run, as does any refusal that
disappeared.  Exit status is 0 only when every airport is identical in
every compared key.

Promoted 2026-09-15 from lane ``v2channel``'s scratchpad copy, which ran
in rounds 3, 4, 5 and 6 (tool discipline, RULINGS ``7e90032``: the
second use is the signal).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

DEFAULT_KEYS = ("tunnels", "basins")
REFUSAL_KEYS = ("corridor_refused", "basin_refused", "sunken_refused",
                "door_refused", "plate_refused", "tunnel_refused")


def load(d: pathlib.Path) -> dict | None:
    f = d / "structures.json"
    return json.loads(f.read_text()) if f.is_file() else None


def canon(rec: dict, key: str) -> str:
    return json.dumps(rec.get(key) or [], sort_keys=True, separators=(",", ":"))


def compare(base: dict, branch: dict, keys, own_marks) -> dict:
    """One airport's verdict as a plain dict (the JSON the CLI prints)."""
    out: dict = {"identical": True, "keys": {}, "refusals": {}}
    for key in keys:
        same = canon(base, key) == canon(branch, key)
        out["keys"][key] = {"base": len(base.get(key) or []),
                            "branch": len(branch.get(key) or []),
                            "identical": same}
        out["identical"] &= same
    for key in REFUSAL_KEYS:
        b, a = set(base.get(key) or []), set(branch.get(key) or [])
        added, gone = sorted(a - b), sorted(b - a)
        if not added and not gone:
            continue
        foreign = [r for r in added if not any(m in r for m in own_marks)]
        out["refusals"][key] = {"added": len(added), "gone": len(gone),
                                "foreign": foreign[:5], "lost": gone[:5]}
        if foreign or gone:
            out["identical"] = False
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="structure_replay_diff.py")
    ap.add_argument("--base", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--icao", nargs="+", required=True)
    ap.add_argument("--keys", nargs="+", default=list(DEFAULT_KEYS))
    ap.add_argument("--own-marks", nargs="*", default=[],
                    help="substrings identifying the lane's OWN refusal lines; "
                         "any other added refusal fails the run")
    ap.add_argument("--prefix", action="store_true",
                    help="--base/--branch name ONE directory holding "
                         "base_<ICAO>/ and br_<ICAO>/")
    args = ap.parse_args(argv)
    ok = True
    rows = {}
    for icao in args.icao:
        bd = (pathlib.Path(args.base) / f"base_{icao}") if args.prefix else \
            pathlib.Path(args.base) / icao
        ad = (pathlib.Path(args.branch) / f"br_{icao}") if args.prefix else \
            pathlib.Path(args.branch) / icao
        b, a = load(bd), load(ad)
        if b is None or a is None:
            print(f"{icao:5}  MISSING  base={b is not None} branch={a is not None}")
            rows[icao] = {"identical": False, "missing": True}
            ok = False
            continue
        v = compare(b, a, args.keys, args.own_marks)
        rows[icao] = v
        ok &= v["identical"]
        cells = [f"{icao:5}"]
        for key, r in v["keys"].items():
            cells.append(f"{key} {r['base']}->{r['branch']} "
                         f"{'IDENTICAL' if r['identical'] else '*** DIFFERS ***'}")
        for key, r in v["refusals"].items():
            cells.append(f"{key}: +{r['added']} -{r['gone']} "
                         f"(foreign {len(r['foreign'])})")
            for line in r["foreign"] + r["lost"]:
                cells.append(f"      ! {line[:150]}")
        print("  ".join(cells))
    print("\nVERDICT:", "ALL IDENTICAL" if ok else "DIFFERENCES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":                      # pragma: no cover
    sys.exit(main())
