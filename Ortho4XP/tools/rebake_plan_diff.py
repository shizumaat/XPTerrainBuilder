"""THE REBAKE-PLAN DIFF — what the OBJECT stage would WRITE differently.

Two reads over ``obj8_split_report --json`` dumps (the dry run of one
``<ICAO>.rebake.json`` plan on an emitted ``<ICAO>.graded.json`` surface),
promoted from lane kclt608's scratch (``c2_osr_diff.py`` / ``a2_separations.py``)
on their second use (lane roads609; RULINGS ``7e90032``):

    venv/bin/python tools/rebake_plan_diff.py zeros BASE.json ARM.json [--top N]
    venv/bin/python tools/rebake_plan_diff.py separations OSR.json PLAN.json [--min-sep M] [--csv OUT]

``zeros``: two dumps of the SAME plan (one per arm, or one per surface): the
bodies whose FOOTPRINT UNIT or ZERO (``surface_z - y_zero``) changed, the
re-partition (body keys only in one arm), and the units that changed.  A
body is keyed by ``(resource, placement index, component set)`` — the
placement index MUST be in the key: single-component bodies of two
placements of one resource collide without it, which minted a −34.96 m
``sign_T2`` mover that did not exist (kclt608 notes, CORRECTION).

``separations``: the ε-contact pairs of the plan whose two parts are
WRITTEN into bodies with DIFFERENT zeros — the step between touching parts
of one building (a roof plane over its walls, a canopy over its posts) —
at or above ``--min-sep`` (0.3 m, the seat materiality), worst first.

Instrument only: it measures no law and counts no defects (that is
``harness/census.py``); it reads the dry run's own records.
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``, ahead of every other import (the
# ``--help`` carries ``ε`` / ``−``).  Twin: ``tests/test_console_encoding.py``.
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import collections
import json
import re
import sys
import typing as _t

__all__ = ["load_bodies", "zero_changes", "separations", "main"]

_UNIT = re.compile(r"unit (\S+?)(?:'s|@| )")


def _unit_of(reason: str | None) -> str:
    m = _UNIT.search(reason or "")
    return m.group(1) if m else ""


def _zero(b: _t.Mapping[str, _t.Any]) -> float | None:
    if b.get("surface_z") is None or b.get("y_zero") is None:
        return None
    return float(b["surface_z"]) - float(b["y_zero"])


def load_bodies(dump: _t.Mapping[str, _t.Any]) -> dict[tuple, dict[str, _t.Any]]:
    """``{(resource, placement index, components): body record}`` of one
    ``obj8_split_report --json`` dump; the record carries ``unit``,
    ``zero``, ``reason``, ``lat``/``lon`` (plan-box centre) and ``ground_off``."""
    out: dict[tuple, dict[str, _t.Any]] = {}
    for s in dump["splits"]:
        res = s["placement"]["resource"].split("/")[-1]
        idx = s["placement"].get("index")
        for b in s["bodies"]:
            bx = b["plan_box"]
            out[(res, idx, tuple(b["components"]))] = {
                "unit": _unit_of(b.get("anchor_reason")), "zero": _zero(b),
                "reason": (b.get("anchor_reason") or "")[:90],
                "lat": (bx[0] + bx[2]) / 2, "lon": (bx[1] + bx[3]) / 2,
                "ground_off": b.get("ground_off"), "body_id": b.get("body_id"),
                "cls": b.get("class"), "carrier": b.get("merged_into")}
    return out


def zero_changes(base: _t.Mapping[str, _t.Any], arm: _t.Mapping[str, _t.Any],
                 tol_m: float = 0.05) -> dict[str, _t.Any]:
    """The bodies whose unit or zero changed by more than ``tol_m``, the
    re-partition counts and the changed units, as data."""
    B, A = load_bodies(base), load_bodies(arm)
    changed = []
    for k in B:
        if k not in A:
            continue
        b, a = B[k], A[k]
        zb, za = b["zero"], a["zero"]
        moved = (zb is None) != (za is None) or (
            zb is not None and za is not None and abs(zb - za) > tol_m)
        if b["unit"] != a["unit"] or moved:
            changed.append({"key": k, "base": b, "arm": a,
                            "dz": (za - zb) if zb is not None and za is not None else None})
    changed.sort(key=lambda c: -(abs(c["dz"]) if c["dz"] is not None else 0.0))
    return {"changed": changed,
            "movers": [c for c in changed if c["dz"] is not None and abs(c["dz"]) > tol_m],
            "base_only": len(set(B) - set(A)), "arm_only": len(set(A) - set(B)),
            "units_changed": sorted({c["arm"]["unit"] for c in changed
                                     if c["arm"]["unit"] != c["base"]["unit"]}),
            "counts": {k: v for k, v in arm.get("counts", {}).items()
                       if "off_pad" in k or "level" in k}}


def separations(osr: _t.Mapping[str, _t.Any], plan: _t.Mapping[str, _t.Any],
                min_sep: float = 0.3) -> list[dict[str, _t.Any]]:
    """The touching body pairs (the plan's ε-contacts) written at zeros
    ``min_sep`` or more apart, worst first."""
    parts: dict[int, tuple] = {}
    member_parts: dict[str, dict] = {}
    for u in plan["units"]:
        for m in u["members"]:
            member_parts[m["id"]] = {p[1]: p for p in m["parts"]}
            for p in m["parts"]:
                parts[p[0]] = (m["id"], m["resource"].split("/")[-1], p[1], p[2], p[3], p[4])
    body_of: dict[int, tuple] = {}
    bodies: dict[tuple, dict[str, _t.Any]] = {}
    for s in osr["splits"]:
        mid = s["placement"].get("id") or "dsf:obj%d" % s["placement"]["index"]
        comp = member_parts.get(mid, {})
        for b in s["bodies"]:
            key = (mid, b["body_id"])
            bodies[key] = {"res": s["placement"]["resource"].split("/")[-1],
                           "unit": _unit_of(b.get("anchor_reason")), "zero": _zero(b),
                           "cls": b.get("class")}
            for c in b["components"]:
                p = comp.get(c)
                if p is not None:
                    body_of[p[0]] = key
    pairs: dict[tuple, list] = collections.defaultdict(list)
    for a, b in plan["contacts"]:
        ka, kb = body_of.get(a), body_of.get(b)
        if ka is None or kb is None or ka == kb:
            continue
        za, zb = bodies[ka]["zero"], bodies[kb]["zero"]
        if za is None or zb is None or abs(za - zb) < min_sep:
            continue
        if ka > kb:
            ka, kb, a, b = kb, ka, b, a
        pairs[(ka, kb)].append((a, b))
    rows = []
    for (ka, kb), ps in pairs.items():
        A, Bd = bodies[ka], bodies[kb]
        pa = parts[ps[0][0]]
        rows.append({"sep": abs(A["zero"] - Bd["zero"]), "A": A, "B": Bd, "pairs": len(ps),
                     "keyA": ka, "keyB": kb, "lat": pa[3], "lon": pa[4],
                     "base_y_max": max(parts[q][5] for q, _ in ps)})
    rows.sort(key=lambda r: -r["sep"])
    return rows


def _print_zeros(d: dict[str, _t.Any], top: int) -> None:
    print("counts arm", d["counts"])
    print(f"{len(d['changed'])} bodies changed unit or zero ({len(d['movers'])} with a zero "
          f"move > 0.05 m); {d['base_only']} base-only, {d['arm_only']} arm-only (re-partitioned)")
    for c in d["movers"][:top]:
        k, b, a = c["key"], c["base"], c["arm"]
        print(f"{c['dz']:+6.2f} {k[0]:<34} {b['unit']:<22} z {b['zero']:.2f} -> {a['unit']:<24} "
              f"z {a['zero']:.2f} at {b['lat']:.7f},{b['lon']:.7f}  {a['reason'][:70]}")
    print("units changed:", len(d["units_changed"]), d["units_changed"][:40])


def _print_separations(rows: list[dict[str, _t.Any]], min_sep: float,
                       csv: str | None) -> None:
    print(f"{len(rows)} touching body pairs with zeros >= {min_sep} m apart "
          f"({len({k for r in rows for k in (r['keyA'], r['keyB'])})} bodies)")
    for r in rows:
        A, B = r["A"], r["B"]
        print(f"{r['sep']:5.2f} m  {A['res']} b{r['keyA'][1]} [{A['unit']}] z {A['zero']:.2f} ({A['cls']})"
              f"  <->  {B['res']} b{r['keyB'][1]} [{B['unit']}] z {B['zero']:.2f} ({B['cls']})"
              f"  pairs {r['pairs']}  at {r['lat']:.7f},{r['lon']:.7f}  base_y A-side max {r['base_y_max']:.2f}")
    if csv:
        with open(csv, "w", encoding="utf-8") as f:
            f.write("sep_m,resA,bodyA,unitA,zeroA,resB,bodyB,unitB,zeroB,pairs,lat,lon\n")
            for r in rows:
                A, B = r["A"], r["B"]
                f.write(f"{r['sep']:.2f},{A['res']},{r['keyA'][1]},{A['unit']},{A['zero']:.2f},"
                        f"{B['res']},{r['keyB'][1]},{B['unit']},{B['zero']:.2f},{r['pairs']},"
                        f"{r['lat']:.7f},{r['lon']:.7f}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zeros", help="bodies whose unit or zero changed between two dumps of one plan")
    z.add_argument("base"); z.add_argument("arm")
    z.add_argument("--top", type=int, default=40)
    z.add_argument("--tol", type=float, default=0.05)
    z.add_argument("--json")
    s = sub.add_parser("separations", help="touching body pairs written at two zeros")
    s.add_argument("osr"); s.add_argument("plan")
    s.add_argument("--min-sep", type=float, default=0.3)
    s.add_argument("--csv")
    a = ap.parse_args(argv)
    if a.cmd == "zeros":
        d = zero_changes(json.load(open(a.base)), json.load(open(a.arm)), a.tol)
        _print_zeros(d, a.top)
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump({"movers": [{"key": list(c["key"]), "dz": c["dz"], "base": c["base"],
                                       "arm": c["arm"]} for c in d["movers"]],
                           "base_only": d["base_only"], "arm_only": d["arm_only"],
                           "units_changed": d["units_changed"]}, f, indent=1)
        return 0
    rows = separations(json.load(open(a.osr)), json.load(open(a.plan)), a.min_sep)
    _print_separations(rows, a.min_sep, a.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
