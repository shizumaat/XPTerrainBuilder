#!/usr/bin/env python3
"""THE FREE-RIDER CENSUS (owner RULINGS 2026-11-13r, #2053): every footed
rider whose seat the 13r witness changes, over re-seat plans and captures.

For each input — a re-seat plan (``o4_v2_rebake_<ICAO>.json`` /
``<ICAO>.rebake.json``) or a ``v2_solve_replay --capture`` pickle (its
``airport.partition`` is the pack read the plan is made of) — the plan-wide
units are formed TWICE, with the witness and without it
(``footprint_unit.plan_units_and_connectors``, the shipped law values), and
every body that leaves its host is listed: pack, rider resource, host
resource, lat/lon, and its lowest foot's height over a FLAT ground of 0 m,
old -> new (the host unit's zero, then the rider unit's, by
``plan_unit_datums``).  It also checks that no HOST
unit's zero moved.  Reads only; builds nothing.

    venv/bin/python tools/rider_free_census.py PATH [PATH ...] [--newest-per-icao]

``--newest-per-icao`` keeps the newest input per ICAO (by file mtime).
"""
from __future__ import annotations

import argparse
import os
import pickle
import statistics
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()
from auto_patch_v2.airport import footprint_unit as fu  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402


def _plan_of(path: str):
    """``(plan-like, icao)`` from a re-seat plan or a capture pickle."""
    if path.endswith(".json"):
        from auto_patch_v2.airport.placement_read import read_plan
        plan, _ab = read_plan(path)
        return plan, plan.icao
    with open(path, "rb") as fh:
        cap = pickle.load(fh)
    a = cap["airport"]
    p = getattr(a, "partition", None)
    if p is None:
        return None, cap.get("icao", "?")
    return types.SimpleNamespace(
        units=p.units, contacts=p.contacts, abutments=p.abutments,
        connectors=getattr(p, "connectors", None), adapted_frame_pids=(),
        authored_seats=(), pack_name=p.pack_name, icao=a.icao), a.icao


def _units(plan, law, witness: bool):
    pl = law.tables.structures.placement
    real = fu._rider_witness
    if not witness:
        fu._rider_witness = lambda *a, **k: None
    try:
        counts: dict = {}
        units, _c = fu.plan_units_and_connectors(
            plan, float(pl.footprint_touch_m), float(pl.connector_span_m),
            counts, float(pl.chain_min_height_m),
            float(pl.contents_min_fraction),
            float(pl.sheet_chain_min_fraction))
    finally:
        fu._rider_witness = real
    return units, counts


def census(path: str, law) -> list[str]:
    plan, icao = _plan_of(path)
    if plan is None:
        return [f"{icao}\t{path}\tNO PARTITION"]
    flat = lambda la, lo: 0.0  # noqa: E731
    on, c_on = _units(plan, law, True)
    off, _c = _units(plan, law, False)
    pl = law.tables.structures.placement
    z_on = fu.plan_unit_datums(on, plan, flat, (), 0.0, 0.0,
                               float(pl.chain_min_height_m))
    z_off = fu.plan_unit_datums(off, plan, flat, (), 0.0, 0.0,
                                float(pl.chain_min_height_m))
    unit_on = {b: u.id for u in on for b in u.bodies}
    unit_off = {b: u.id for u in off for b in u.bodies}
    parts = {p.pid: p for u in plan.units for m in u.members for p in m.parts}
    no_origin = sum(1 for u in plan.units for m in u.members
                    if getattr(m, "origin", None) is None)
    out = [f"# {icao}\t{path}\tfree_riders={c_on.get('contents_free_riders', 0)}"
           f"\tmembers_without_origin={no_origin}"]
    pack = getattr(plan, "pack_name", "")
    for b, uid in sorted(unit_off.items()):
        nid = unit_on.get(b, "")
        if nid == uid or not nid.endswith("/rider"):
            continue
        m = plan.units[b[0]].members[b[1]]
        host = next(u for u in off if u.id == uid)
        hr = sorted({plan.units[k[0]].members[k[1]].resource for k in host.bodies
                     if k[:2] != b[:2]})
        low = min((f[2] for p in m.parts for f in p.feet), default=float("nan"))
        old = z_off[uid][0] + low if uid in z_off else float("nan")
        new = z_on[nid][0] + low if nid in z_on else float("nan")
        la = statistics.fmean(p.lat for p in m.parts)
        lo = statistics.fmean(p.lon for p in m.parts)
        out.append(f"{icao}\t{pack}\t{m.resource}\t{m.id}\tbody {b[2]}"
                   f"\thost={'|'.join(hr)}\t{la:.6f},{lo:.6f}"
                   f"\tfeet over ground {old:+.2f} -> {new:+.2f}")
    for uid, z in sorted(z_off.items()):
        if uid in z_on and abs(z_on[uid][0] - z[0]) > 1e-6:
            out.append(f"{icao}\tHOST ZERO MOVED\t{uid}\t{z[0]:+.3f} -> "
                       f"{z_on[uid][0]:+.3f}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--newest-per-icao", action="store_true")
    a = ap.parse_args(argv)
    paths = a.paths
    if a.newest_per_icao:
        best: dict[str, str] = {}
        for p in paths:
            k = Path(p).name.replace("o4_v2_rebake_", "").split(".")[0].split("_")[0]
            if k not in best or os.path.getmtime(p) > os.path.getmtime(best[k]):
                best[k] = p
        paths = sorted(best.values())
    law = Law.load()
    for p in paths:
        try:
            for line in census(p, law):
                print(line, flush=True)
        except Exception as e:  # noqa: BLE001 — one input never stops the census
            print(f"# ERROR\t{p}\t{type(e).__name__}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
