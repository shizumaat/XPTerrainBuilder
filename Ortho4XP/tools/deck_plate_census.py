#!/usr/bin/env python3
"""THE DECK-PLATE CENSUS (#2112): every installed airport pack's hard-deck
OBJ8 files, read by the engine's own plate reader
(``auto_patch_v2/airport/deck_plates``), for the decks authored as
DISJOINT PLATES the object stage cuts by plate.

    venv/bin/python tools/deck_plate_census.py SCENERY_DIR [--pack SUBSTR ...]
        [--reach M] [--json OUT] [--top N]

A file is read once: the pristine ``.anchor_bak`` where one stands beside
it, never a split body (``__b<k>``) or a copy of ours.  Per file: its
plates (hard-deck pieces chained within the rigid reach, default the
``[placement] rigid_reach_m`` law), whether they BAND (stand in order along
one axis, every gap wider than the reach — the frames the stage splits) and
the gaps.  One row per pack with a multi-plate deck, the files beneath it,
and the totals.  READ-ONLY.  Whether a file is PLACED (and so whether a
build moves anything) is the plan's question: run the object stage replay
on the airport (``v2_rebake_replay.py plan``) for the movers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))


def _law_reach() -> float:
    from auto_patch_v2.law import Law
    try:
        return float(Law.load().tables.structures.placement.rigid_reach_m)
    except (KeyError, TypeError, AttributeError):
        return 2.0


def _is_airport_pack(root: str) -> bool:
    return os.path.isfile(os.path.join(root, "Earth nav data", "apt.dat"))


def _deck_files(pack: str):
    """Every pristine OBJ8 under ``pack`` that declares ``ATTR_hard_deck``."""
    for dp, _dn, fn in os.walk(pack):
        names = set(fn)
        for f in fn:
            low = f.lower()
            if low.endswith(".obj"):
                if "__b" in low or f + ".anchor_bak" in names:
                    continue
            elif not low.endswith(".obj.anchor_bak"):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, "rb") as fh:
                    if b"ATTR_hard_deck" not in fh.read():
                        continue
            except OSError:
                continue
            yield p


def census(scenery: str, packs: "list[str] | None", reach_m: float) -> dict:
    from auto_patch_v2.airport import deck_plates as _dp
    rows = []
    tot = {"packs": 0, "deck_files": 0, "multi_plate": 0, "banded": 0}
    for name in sorted(os.listdir(scenery)):
        root = os.path.join(scenery, name)
        if not os.path.isdir(root) or not _is_airport_pack(root):
            continue
        if packs and not any(s.lower() in name.lower() for s in packs):
            continue
        tot["packs"] += 1
        files = []
        n = 0
        for p in _deck_files(root):
            n += 1
            r = _dp.census_file(p, reach_m)
            if r["plates"] >= 2:
                files.append({"file": os.path.relpath(p, root), **r})
        tot["deck_files"] += n
        tot["multi_plate"] += len(files)
        tot["banded"] += sum(1 for f in files if f["banded"])
        if files:
            rows.append({"pack": name, "deck_files": n, "files": files})
    return {"reach_m": reach_m, "totals": tot, "packs": rows}


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("scenery")
    ap.add_argument("--pack", nargs="*", default=None)
    ap.add_argument("--reach", type=float, default=None,
                    help="the plate reach (default: the law's rigid_reach_m)")
    ap.add_argument("--json", default="")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args(argv)
    reach = _law_reach() if a.reach is None else a.reach
    out = census(a.scenery, a.pack, reach)
    t = out["totals"]
    print(f"deck-plate census (reach {reach} m): {t['packs']} airport packs, "
          f"{t['deck_files']} hard-deck files, {t['multi_plate']} in plates, "
          f"{t['banded']} banded (split by the stage)")
    for r in out["packs"]:
        print(f"  {r['pack']}: {len(r['files'])} of {r['deck_files']} in plates")
        for f in r["files"][:a.top]:
            print(f"      {f['file']}: {f['plates']} plates, "
                  f"{'BANDED gaps ' + str(f['gaps_m']) if f['banded'] else 'not banded'}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
