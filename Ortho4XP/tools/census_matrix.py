"""THE CENSUS MATRIX — many census JSONs, one readable table, one gate.

    venv/bin/python tools/census_matrix.py CENSUS.json [CENSUS.json ...]
        [--gate ARM | --gate-json FILE | --no-gate] [--bands]

IT MEASURES NOTHING AND DERIVES NO NUMBER.  Every value printed is read
verbatim out of a ``tools/harness/census.py --json`` artifact (the one
census, the one law-true frame); this tool only lays several of them out
side by side and applies a stated per-cell CEILING to one column.  That
restriction is the whole design: a reporter that recomputes a defect count
is a census wrapper, and the two frame errors that made the harness
necessary were both produced by exactly that (CLAUDE.md, "The standard test
harness").

WHY IT EXISTS.  A multi-airport, multi-world round produces 8+ census JSONs
per arm, and the question asked of them is never "what is in this one file"
— it is "did any cell's AIRSIDE count rise against the arm we promised not
to regress" (the Q4 gate) and "where did the change land".  Read as separate
census tables that question cannot be answered without arithmetic by hand.

Promoted 2026-08-06 from ``tmp/c8fin/mx.py`` (lane c8fin) on its second use
(lane c9feed) — promote-on-reuse, RULINGS ``7e90032``.  The lane copy
hard-coded one round's frame of record as a module constant, which is
exactly what goes stale between rounds; the ceiling is an argument here.

CELLS.  A cell is the patch stem (``HECA_lo``, ``KCLT_hi``, …) with a
trailing rebuild suffix (``_lo2`` → ``_lo``) folded away, so a re-measured
world compares with its own baseline instead of appearing as a new cell.

THE GATE.  ``--gate ARM`` (default: arm 0, the leftmost census on the
command line) takes that arm's per-cell AIRSIDE adjudicated count as the
ceiling every later arm must stay at or under; ``--gate-json FILE`` reads a
recorded ``{cell: ceiling}`` frame instead (a frame of record from an
earlier round).  Equality PASSES — the gate is "may not RISE".  Cells absent
from the ceiling source are reported as ``no ceiling`` and counted in
neither the numerator nor the denominator, never silently passed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: The census JSON fields this tool reads.  Named here so a census schema
#: change breaks loudly in one place instead of printing zeros.
LAWTRUE_TOTAL = ("lawtrue", "total")
ADJ_TOTAL = ("adjudication", "adjudicated_total")
ADJ_BY_SIDE = ("adjudication", "adjudicated_by_side")


def _dig(entry: dict, path: Tuple[str, ...]):
    cur = entry
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            raise KeyError(
                f"census entry for {entry.get('patch', '?')!r} has no "
                f"{'.'.join(path)} — this is not a "
                f"tools/harness/census.py --json artifact, or the census "
                f"schema changed and this reporter must be updated with it")
        cur = cur[k]
    return cur


def cell_tag(patch_path: str) -> str:
    """``…/HECA_lo2.osm`` → ``HECA_lo`` — the rebuild suffix folded away."""
    tag = Path(patch_path).stem
    for n in ("2", "3", "4"):
        tag = tag.replace(f"_lo{n}", "_lo").replace(f"_hi{n}", "_hi")
    return tag


def read_cells(path) -> Dict[str, dict]:
    """One census JSON → ``{cell: {...verbatim census values...}}``."""
    out: Dict[str, dict] = {}
    for entry in json.loads(Path(path).read_text()):
        by = _dig(entry, ADJ_BY_SIDE)
        out[cell_tag(entry["patch"])] = {
            "lawtrue": _dig(entry, LAWTRUE_TOTAL),
            "adj": _dig(entry, ADJ_TOTAL),
            "air": by["airside"],
            "gs": by["groundside"],
            "mix": by["mixed"],
            # "airside for acceptance" — the census's own applied ruling
            # that a MIXED row counts against airside (airside is king).
            "a4a": by["airside"] + by["mixed"],
            "bands": entry.get("magnitude_bands"),
        }
    return out


def ceilings(arms: List[Dict[str, dict]], gate_arm: Optional[int],
             gate_json: Optional[str]) -> Dict[str, int]:
    """The per-cell AIRSIDE ceiling the gate judges against."""
    if gate_json:
        return {str(k): int(v) for (k, v) in
                json.loads(Path(gate_json).read_text()).items()}
    if gate_arm is None:
        return {}
    return {tag: c["air"] for (tag, c) in arms[gate_arm].items()}


def order_of(arms: List[Dict[str, dict]]) -> List[str]:
    """Stable cell order: airport groups in first-seen order, low world
    before high within each — the reading order of the battery."""
    seen: List[str] = []
    for arm in arms:
        for tag in arm:
            if tag not in seen:
                seen.append(tag)
    groups: List[str] = []
    for tag in seen:
        g = tag.rsplit("_", 1)[0]
        if g not in groups:
            groups.append(g)
    rank = {"_lo": 0, "_hi": 1}
    return sorted(seen, key=lambda t: (groups.index(t.rsplit("_", 1)[0]),
                                       rank.get("_" + t.rsplit("_", 1)[-1], 2),
                                       t))


def gate_rows(arms, names, cap, order) -> List[tuple]:
    """``(arm_name, cell, airside, ceiling|None, passed|None)`` — the gate
    verdict per cell, with no ceiling reported as ``None`` rather than a
    pass."""
    rows = []
    for (arm, nm) in zip(arms, names):
        for tag in order:
            c = arm.get(tag)
            if c is None:
                continue
            ceil = cap.get(tag)
            rows.append((nm, tag, c["air"], ceil,
                         None if ceil is None else c["air"] <= ceil))
    return rows


def _print_matrix(arms, names, order, cap):
    head = " | ".join(f"{n[:26]:>26}" for n in names)
    print(f"{'cell':9} | {'ceiling':>7} | " + head)
    print(f"{'':9} | {'':>7} | " + " | ".join(
        f"{'lawtrue   ADJ   air    gs':>26}" for _ in names))
    for tag in order:
        ceil = cap.get(tag)
        parts = []
        for arm in arms:
            c = arm.get(tag)
            parts.append("%26s" % ("-" if c is None else
                                   f"{c['lawtrue']:7} {c['adj']:5} "
                                   f"{c['air']:5} {c['gs']:5}"))
        print(f"{tag:9} | {('-' if ceil is None else ceil):>7} | "
              + " | ".join(parts))


def _print_gate(arms, names, order, cap):
    print("\nQ4 GATE (airside may not RISE vs the ceiling), per cell and arm:")
    rows = gate_rows(arms, names, cap, order)
    for nm in names:
        mine = [r for r in rows if r[0] == nm]
        n_pass = sum(1 for r in mine if r[4] is True)
        n = sum(1 for r in mine if r[4] is not None)
        for (_nm, tag, air, ceil, ok) in mine:
            if ok is None:
                print(f"  {nm[:12]:12} {tag:9} airside {air:6} "
                      f"vs      -  no ceiling (not gated)")
            else:
                print(f"  {nm[:12]:12} {tag:9} airside {air:6} vs {ceil:6}  "
                      f"{'PASS' if ok else 'FAIL'} ({air - ceil:+d})")
        print(f"  {nm[:12]:12} == {n_pass}/{n} PASS ==")


def _print_delta(arms, names, order):
    print("\nDELTA arm-vs-first (arm − arm 0):")
    base = arms[0]
    for (arm, nm) in zip(arms[1:], names[1:]):
        for tag in order:
            a, b = arm.get(tag), base.get(tag)
            if a is None or b is None:
                continue
            print(f"  {nm[:12]:12} {tag:9} ADJ {a['adj'] - b['adj']:+6} "
                  f"| air {a['air'] - b['air']:+5} "
                  f"| gs {a['gs'] - b['gs']:+6} "
                  f"| mix {a['mix'] - b['mix']:+4} "
                  f"| lawtrue {a['lawtrue'] - b['lawtrue']:+7}")

        def tot(A, k):
            return sum(A[t][k] for t in order if t in A)

        print(f"  {nm[:12]:12} BOTH-WORLDS ADJ {tot(base, 'adj')} -> "
              f"{tot(arm, 'adj')} ({tot(arm, 'adj') - tot(base, 'adj'):+d}); "
              f"airside {tot(base, 'air')} -> {tot(arm, 'air')} "
              f"({tot(arm, 'air') - tot(base, 'air'):+d}); groundside "
              f"{tot(base, 'gs')} -> {tot(arm, 'gs')} "
              f"({tot(arm, 'gs') - tot(base, 'gs'):+d})")


def _print_bands(arms, names, order):
    print("\nMAGNITUDE BANDS (census --magnitude-bands; verbatim):")
    for (arm, nm) in zip(arms, names):
        for tag in order:
            c = arm.get(tag)
            b = (c or {}).get("bands")
            if not b:
                continue
            print(f"  {nm[:12]:12} {tag:9} " + "  ".join(
                f"{x['label']}={x['n']}(adj {x['adjudicated']}, "
                f"air {x['airside']}/gs {x['groundside']})"
                for x in b["bands"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("census", nargs="+",
                    help="census JSON artifact(s) from "
                         "tools/harness/census.py --json — one per ARM")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--gate", type=int, default=0, metavar="ARM",
                   help="index of the arm whose per-cell AIRSIDE count is "
                        "the ceiling (default 0 = the first census listed)")
    g.add_argument("--gate-json", metavar="FILE",
                   help="a recorded {cell: airside_ceiling} frame instead")
    g.add_argument("--no-gate", action="store_true",
                   help="matrix only, no gate verdict")
    ap.add_argument("--bands", action="store_true",
                    help="also print the census's magnitude bands verbatim "
                         "(present only if the census ran "
                         "--magnitude-bands)")
    a = ap.parse_args(argv)

    arms = [read_cells(p) for p in a.census]
    names = [Path(p).stem for p in a.census]
    order = order_of(arms)
    cap = ceilings(arms, None if a.no_gate else a.gate, a.gate_json)
    _print_matrix(arms, names, order, cap)
    if not a.no_gate:
        _print_gate(arms, names, order, cap)
    if len(arms) >= 2:
        _print_delta(arms, names, order)
    if a.bands:
        _print_bands(arms, names, order)
    return 0


if __name__ == "__main__":                                # pragma: no cover
    sys.exit(main())
