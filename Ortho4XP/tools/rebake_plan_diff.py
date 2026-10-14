"""THE REBAKE-PLAN DIFF — what the OBJECT stage would WRITE differently.

Two reads over ``obj8_split_report --json`` dumps (the dry run of one
``<ICAO>.rebake.json`` plan on an emitted ``<ICAO>.graded.json`` surface),
promoted from lane kclt608's scratch (``c2_osr_diff.py`` / ``a2_separations.py``)
on their second use (lane roads609; RULINGS ``7e90032``):

    venv/bin/python tools/rebake_plan_diff.py zeros BASE.json ARM.json [--top N]
    venv/bin/python tools/rebake_plan_diff.py separations OSR.json PLAN.json [--min-sep M] [--csv OUT]
    venv/bin/python tools/rebake_plan_diff.py samples BASE.json ARM.json [--mesh M.mesh] [--tol T] [--top N]

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

``samples`` (lane roofs610, #610): what MOVES ON SCREEN, keyed by the
written geometry, not by the body.  ``zeros`` keys a body by its component
set, and a body cut out of components the plan holds no part for has an
EMPTY set — every such piece of one placement collides on one key, and a
re-partitioned roof reads as a 21 m mover that does not exist.  Every
written sample (``geom_pts``) common to both dumps is keyed by
``(placement index, authored lat, lon, y)``; the samples whose world height
(zero + y) moved by more than ``--tol`` are grouped by the arm's body.
With ``--mesh`` (the app's own ``Data*.mesh``, read through
``engine_v2.mesh_placement_sampler``) each moved body also carries its
OWN-GROUND before and after — the median over its moved samples of
(zero − mesh ground under the sample) — and a verdict: ``better`` when
the after is smaller in magnitude by more than ``--tol``, ``worse`` when
larger, else ``same``.

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

__all__ = ["load_bodies", "zero_changes", "separations", "sample_moves",
           "main"]

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


def _samples(dump: _t.Mapping[str, _t.Any]) -> dict[tuple, tuple]:
    """``(placement index, lat, lon, y) -> (zero, resource, body id,
    reason)`` for every written geometry sample of a dump."""
    out: dict[tuple, tuple] = {}
    for s in dump.get("splits", ()):
        res = s["placement"]["resource"].split("/")[-1]
        ix = s["placement"].get("index")
        for b in s.get("bodies", ()):
            z = _zero(b)
            if z is None:
                continue
            for la, lo, y in b.get("geom_pts") or ():
                out[(ix, round(la, 6), round(lo, 6), round(y, 2))] = (
                    z, res, b.get("body_id"), b.get("anchor_reason") or "")
    return out


def sample_moves(base: _t.Mapping[str, _t.Any], arm: _t.Mapping[str, _t.Any],
                 tol: float = 0.05,
                 ground: "_t.Callable[[float, float], float | None] | None"
                 = None) -> list[dict[str, _t.Any]]:
    """The moved bodies of ``arm`` against ``base`` read on their common
    written samples (module doc), largest median move first."""
    import statistics
    A, B = _samples(base), _samples(arm)
    groups: dict[tuple, list] = collections.defaultdict(list)
    for k in set(A) & set(B):
        if abs(B[k][0] - A[k][0]) > tol:
            groups[(B[k][1], B[k][2])].append(k)
    rows = []
    for (res, bid), ks in groups.items():
        ks.sort()
        row = {"resource": res, "body_id": bid, "n": len(ks),
               "dz": statistics.median(B[k][0] - A[k][0] for k in ks),
               "lat": ks[0][1], "lon": ks[0][2],
               "base_reason": A[ks[0]][3], "arm_reason": B[ks[0]][3]}
        if ground is not None:
            g = [(k, ground(k[1], k[2])) for k in ks]
            g = [(k, z) for k, z in g if z is not None]
            if g:
                ob = statistics.median(A[k][0] - z for k, z in g)
                oa = statistics.median(B[k][0] - z for k, z in g)
                row.update(own_before=ob, own_after=oa,
                           verdict=("better" if abs(oa) < abs(ob) - tol else
                                    "worse" if abs(oa) > abs(ob) + tol else "same"))
        rows.append(row)
    rows.sort(key=lambda r: -abs(r["dz"]))
    return rows


def _mesh_ground(mesh: str, rows_of: _t.Sequence[_t.Mapping[str, _t.Any]]):
    """The app's own mesh adapter over the dumps' extent, as ``(lat, lon)
    -> z | None``."""
    las = [p[0] for d in rows_of for s in d.get("splits", ()) for b in s.get("bodies", ())
           for p in (b.get("geom_pts") or ())]
    los = [p[1] for d in rows_of for s in d.get("splits", ()) for b in s.get("bodies", ())
           for p in (b.get("geom_pts") or ())]
    _o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
        _o4os.path.abspath(__file__))), "src", "auto_patch"))
    from auto_patch.engine_v2 import mesh_placement_sampler
    sm = mesh_placement_sampler(mesh, (min(los) - .01, min(las) - .01,
                                       max(los) + .01, max(las) + .01))

    def _g(la: float, lo: float) -> "float | None":
        r = sm(la, lo)
        return None if r is None else float(r[0])
    return _g


def _print_samples(rows: list[dict[str, _t.Any]], top: int) -> None:
    v = collections.Counter(r.get("verdict", "-") for r in rows)
    print(f"{len(rows)} bodies moved on screen ({sum(r['n'] for r in rows)} samples); "
          f"verdicts {dict(v)}")
    for r in rows[:top]:
        own = (f"own-ground {r['own_before']:+6.2f} -> {r['own_after']:+6.2f} {r['verdict']:<6}"
               if "verdict" in r else "")
        print(f"{r['dz']:+7.2f} {r['resource'][:32]:<32} b{r['body_id']!s:<4} n={r['n']:<3} "
              f"at {r['lat']:.6f},{r['lon']:.6f} {own} | {r['base_reason'][:50]} -> "
              f"{r['arm_reason'][:50]}")


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
    m = sub.add_parser("samples", help="bodies whose written geometry moved, keyed by the "
                                       "geometry (with --mesh: own ground before/after)")
    m.add_argument("base"); m.add_argument("arm")
    m.add_argument("--mesh"); m.add_argument("--tol", type=float, default=0.05)
    m.add_argument("--top", type=int, default=60)
    a = ap.parse_args(argv)
    if a.cmd == "samples":
        base, arm = json.load(open(a.base)), json.load(open(a.arm))
        g = _mesh_ground(a.mesh, (base, arm)) if a.mesh else None
        _print_samples(sample_moves(base, arm, a.tol, g), a.top)
        return 0
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
