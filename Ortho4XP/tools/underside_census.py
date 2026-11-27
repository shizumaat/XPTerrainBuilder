#!/usr/bin/env python3
"""THE UNDERSIDE CENSUS (owner RULINGS 2026-11-25m, 25n; spec
``docs/specs/underside-height-map-20261125.md`` §6, §7 step 1): every
footprint unit's underside map (``auto_patch_v2/airport/unit_underside``)
over capture pickles, or over an airport's pack (``--pack ICAO``: load and
the build's own ``pipeline/build.pack_stage``, no cache write), read
against TODAY's seat from the last object-stage plan
(``o4_v2_placement_<ICAO>.json``: each body's zero ``surface_z - y_zero``
and the pad level its anchor reason names, ``on pad X at Z``).

Per unit: rows, stations (airside), ``t``, ``base``, levels, relief,
interiors, composite; ``D`` and today's zero from the plan; ``z0 = D - t``;
the S3 verdict (``airport/underside_admission.admit``); 25n (2) the airside
contact stations still more than 0.5 m off ``t``; 25n (1) the no-pad units
and their perimeter gaps over 0.5 m (our DEM against today's zero).  Then
the S3 table per airport (coherent / mis-zeroed / composite / doubt /
exception, and no-pad) and the derivation seconds.  Reads only; builds
nothing; one capture at a time.

    venv/bin/python tools/underside_census.py CAP.pkl [...] [--plan P.json] [--json OUT]
    venv/bin/python tools/underside_census.py --registered [--icao ICAO ...]
    venv/bin/python tools/underside_census.py --pack ICAO [...]
    venv/bin/python tools/underside_census.py ... --unit firestation --unit pool_5

``--registered`` reads the newest capture per ICAO in ``docs/frames.jsonl``
(``tools/sunk_census.registered``); ``--unit`` prints every unit whose
members' resources contain the text.  Twin: ``tests/test_underside_census.py``.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pickle
import re
import statistics as _st
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

#: where the last object-stage plans stand
PATCHES = os.environ.get("O4_PATCHES_ROOT", "/Users/noah/XPTerrainBuilderData/Patches")
#: a station this far off is a gap (m; 25n)
GAP_M = 0.5
_PAD = re.compile(r"on pad (\S+) at (-?\d+(?:\.\d+)?)")
COLUMNS = ("coherent", "mis-zeroed", "composite", "doubt", "exception", "no-pad")


def plan_path(icao: str) -> "str | None":
    """The newest ``o4_v2_placement_<ICAO>.json`` under :data:`PATCHES`."""
    got = glob.glob(os.path.join(PATCHES, "*", "*", f"o4_v2_placement_{icao}.json"))
    return max(got, key=os.path.getmtime) if got else None


def today_of(plan: "str | None") -> dict[str, list[tuple[float, "float | None"]]]:
    """``{row id: [(body zero, pad level or None), ...]}`` from a placement
    plan (module doc); ``{}`` without one."""
    if not plan:
        return {}
    out: dict[str, list] = {}
    for s in json.loads(Path(plan).read_text()).get("splits", ()):
        rid = f"dsf:obj{s['placement']['index']}"
        for b in s.get("bodies", ()):
            if b.get("surface_z") is None:
                continue
            m = _PAD.search(str(b.get("anchor_reason", "")))
            out.setdefault(rid, []).append(
                (float(b["surface_z"]) - float(b.get("y_zero") or 0.0),
                 float(m.group(2)) if m else None))
    return out


def _mode(xs: list[float]) -> "float | None":
    return float(_st.mode(round(x, 2) for x in xs)) if xs else None


def row_of(m, today: dict, many, to_ll, rsc: dict) -> dict:
    """One unit's census row (module doc)."""
    import numpy as np
    from auto_patch_v2.airport.underside_admission import admit
    bodies = [b for r in m.key for b in today.get(r, ())]
    pads = [p for _z, p in bodies if p is not None]
    D = _mode(pads)
    z_today = _mode([z for z, p in bodies if p is not None] or [z for z, _p in bodies])
    g = np.asarray(many(m.e, m.n), dtype=float) if len(m.e) else np.zeros(0)
    verdict, det = admit(m, D, g)
    air = np.asarray(m.airside, dtype=bool)
    row = {"unit": m.unit, "rows": len([r for r in m.key if not str(r).startswith("@")]),
           "res": sorted({rsc.get(r, "") for r in m.key})[:3],
           "stations": int(len(m.e)), "airside": int(air.sum()),
           "t": None if m.t is None else round(m.t, 3), "t_from": m.t_from,
           "base": None if m.base is None else round(m.base, 3),
           "levels": list(m.levels), "relief": round(m.relief, 2),
           "interiors": [i.kind for i in m.interiors], "composite": m.composite,
           "D": D, "z_today": z_today, "verdict": verdict, **det,
           "z0": (det.get("z0") if m.t_from == "airside" or verdict == "mis-zeroed"
                  else z_today),
           "air_off": int(np.sum(np.abs(m.h[air] - m.t) > GAP_M)) if m.t is not None else 0}
    if len(m.e):
        c = to_ll(float(np.mean(m.e)), float(np.mean(m.n)))
        row["lat"], row["lon"] = round(c[0], 6), round(c[1], 6)
    if D is None and z_today is not None and len(g):
        row["no_pad_gaps"] = int(np.sum(np.abs(g - (z_today + m.h)) > GAP_M))
    return row


def step2_of(airport, law, objects, plan: "str | None") -> list[dict]:
    """STEP 2 (``airport/underside_seat.seat_records``, the seat the build
    writes): one row per unit S3 admits -- written whole at ``z0`` (with
    today's zero from the plan, ``z_today``, and the move) or refused and
    why -- read on the graded surface beside ``plan``
    (``<ICAO>.graded.json``) with the rows its rebake plan
    (``o4_v2_rebake_<ICAO>.json``) seats by another rule taken; ``[]``
    without a graded surface beside the plan."""
    from auto_patch_v2.airport import underside_seat as _us
    from auto_patch_v2.airport.open_frame_seat import TOUCH_M
    from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
    if not plan or objects is None:
        return []
    icao = airport.icao
    graded = Path(plan).with_name(f"{icao}.graded.json")
    if not graded.is_file():
        return []
    rb = Path(plan).with_name(f"o4_v2_rebake_{icao}.json")
    taken = set()
    if rb.is_file():
        taken = {str(r.get("id")) for r in json.loads(rb.read_text()).get("authored_seats", ())
                 if r.get("seat") != _us.SEAT}
    pads = pads_rims_from_graded_doc(json.loads(graded.read_text()))[0]
    _recs, rep = _us.seat_records(airport, pads, objects, taken, TOUCH_M, float(
        law.tables.structures.building_pad.low_level_min_step_m))
    today = today_of(plan)
    to_ll = airport.frame.transformers()[1]
    maps = {m.unit: m for m in airport.undersides.values()}
    for r in rep:
        zs = [z for z, _p in today.get(r["row"], ())]
        r["z_today"] = _mode(zs)
        if "refused" not in r and r["z_today"] is not None:
            r["move"] = round(r["z0"] - r["z_today"], 3)
        m = maps.get(r["unit"])
        if m is not None and len(m.e):
            c = to_ll(float(np.mean(m.e)), float(np.mean(m.n)))
            r["lat"], r["lon"] = round(c[0], 6), round(c[1], 6)
    return rep


def census_of(icao: str, airport, law, cache, plan: "str | None",
              objects=None) -> dict:
    """The rows of one airport (module doc) and the derivation seconds;
    with ``objects`` (the pack's placements) the step-2 rows
    (:func:`step2_of`) too."""
    import dataclasses as _dc

    from auto_patch_v2.airport.underside_composite import dem_many
    from auto_patch_v2.airport.unit_underside import attach_undersides
    if not any(getattr(c, "pids", None) for c in airport.clusters or ()):
        from auto_patch_v2.planar.cluster import clusters
        airport = _dc.replace(airport, clusters=tuple(clusters(airport, law)))
    t0 = time.perf_counter()
    airport, _w = attach_undersides(airport, law, cache, cached=False)
    cold = time.perf_counter() - t0          # the files parsed here too
    t0 = time.perf_counter()
    attach_undersides(airport, law, cache, cached=False)
    warm = time.perf_counter() - t0          # the MISS cost: files already read
    today = today_of(plan)
    rsc = {mm.id: mm.resource for u in airport.partition.units for mm in u.members}
    many, to_ll = dem_many(airport.dem), airport.frame.transformers()[1]
    rows = [row_of(m, today, many, to_ll, rsc) for m in airport.undersides.values()]
    return {"icao": icao, "plan": plan, "seconds": round(warm, 2),
            "seconds_with_parse": round(cold, 2), "rows": rows,
            "step2": step2_of(airport, law, objects, plan)}


def from_capture(path: str, plan: "str | None") -> dict:
    """:func:`census_of` over one capture pickle."""
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.law import Law
    with open(path, "rb") as fh:
        cap = pickle.load(fh)
    icao, airport = cap["icao"], cap["airport"]
    del cap
    law = Law.for_airport(icao)
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law))
    from auto_patch_v2.planar.basins import read_objects
    objects = read_objects(airport, law, cache)[0]
    return census_of(icao, airport, law, cache, plan or plan_path(icao), objects)


def from_pack(icao: str, plan: "str | None") -> dict:
    """:func:`census_of` over the airport's pack, read by the build's own
    pack stage (no cache written)."""
    from auto_patch_v2.airport.load import load_with_report
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline.build import pack_stage
    from auto_patch_v2.planar.__main__ import default_inputs
    law = Law.for_airport(icao)
    inputs = default_inputs()
    airport, lrep = load_with_report(icao, inputs, law)
    ps = pack_stage(icao, airport, law, inputs, lrep, out=lambda _m: None, write_cache=False)
    return census_of(icao, ps["airport"], law, ps["ocache"], plan or plan_path(icao),
                     ps["objects"])


def table(results: list[dict]) -> list[str]:
    """The S3 table: per airport the verdict counts, no-pad units with
    gaps, airside-off units and the derivation seconds."""
    out = [f"{'ICAO':5} {'units':>6} " + " ".join(f"{c:>10}" for c in COLUMNS)
           + f" {'gaps>0.5':>8} {'air_off':>7} {'sec':>6}"]
    for r in results:
        rows = r["rows"]
        n = {c: sum(1 for x in rows if x["verdict"] == c) for c in COLUMNS}
        n["no-pad"] = sum(1 for x in rows if x.get("D") is None and not x["stations"] == 0)
        gaps = sum(1 for x in rows if x.get("no_pad_gaps", 0) > 0)
        off = sum(1 for x in rows if x["air_off"] > 0)
        out.append(f"{r['icao']:5} {len(rows):>6} " + " ".join(f"{n[c]:>10}" for c in COLUMNS)
                   + f" {gaps:>8} {off:>7} {r['seconds']:>6.2f}")
    return out


def _fmt(x: dict) -> str:
    return (f"  {x['unit']:<22} {','.join(x['res'])[:48]:<48} rows {x['rows']:>3} "
            f"st {x['stations']:>5}/{x['airside']:<4} t {x['t']} base {x['base']} "
            f"D {x['D']} z0 {x.get('z0')} today {x['z_today']} {x['verdict']}"
            f"{' COMPOSITE' if x['composite'] else ''} air_off {x['air_off']}"
            f" levels {x['levels']} interiors {x['interiors']}")


def perimeter_of(path: str, plan: "str | None" = None) -> dict:
    """STEP 3 (spec §3 G4, ``tools/perimeter_judge``): one ``--solved-out``
    pickle's graded perimeters judged in the patch and on the free raster;
    ``plan``: a rebake plan whose ``perimeters`` are the build's own."""
    from auto_patch_v2.law import Law
    from perimeter_judge import judge_solved
    with open(path, "rb") as fh:
        solved = pickle.load(fh)
    law = Law.for_airport(solved.get("law_icao") or solved["icao"])
    records = (json.loads(Path(plan).read_text(encoding="utf-8")).get("perimeters") or []
               if plan else None)
    t = time.time()
    res = judge_solved(solved, law, float(
        law.tables.structures.building_pad.low_level_min_step_m), records)
    res.update(icao=solved["icao"], path=path, seconds=round(time.time() - t, 1))
    return res


def perimeter_lines(res: dict, units: "list[str]" = ()) -> list[str]:
    """The step-3 report of :func:`perimeter_of`: per graded unit (every one
    with an over; ``units`` the ones always printed) its free stations over
    0.5 m before and after the raster grade, its in-patch groundside over by
    role, and the totals."""
    out = [f"== {res['icao']} {res['path']}: {len(res['perimeters'])} graded perimeter(s) "
           f"({res['seconds']} s); raster grade {res.get('grade')}"]
    tot = {"free": 0, "before": 0, "after": 0, "ground": 0, "ground_over": 0, "uncut": 0}
    for pr, ip, fb, fa in zip(res["perimeters"], res["in_patch"], res["free_before"],
                              res["free_after"], strict=True):
        tot["free"] += fa.get("free", 0)
        tot["before"] += fb.get("over", 0)
        tot["after"] += fa.get("over", 0)
        tot["ground"] += ip["groundside"]
        tot["ground_over"] += ip["groundside_over"]
        tot["uncut"] += fa.get("uncut", 0)
        if not (fa.get("over") or ip["groundside_over"] or fb.get("over")
                or any(u in pr["unit"] or u in pr.get("res", "") for u in units)):
            continue
        roles = ", ".join(f"{r} {v[1]}/{v[0]} ({v[2]:+.2f})" for r, v in ip["by_role"].items())
        out.append(f"  {pr['unit'][:24]:<24} {pr.get('res', '')[:22]:<22} {pr['why']:<13} "
                   f"z0 {pr['z0']:.2f} st "
                   f"{pr['stations']} far {pr['far']} | free {fa.get('free', 0)} over "
                   f"{fb.get('over', 0)} -> {fa.get('over', 0)} boundary "
                   f"{fa.get('boundary', 0)} patch {fa.get('patch', 0)}"
                   + (f" interiors {fa.get('interior_cells')} postings: in patch "
                      f"{fa.get('in_patch', 0)} cut {fa.get('cut', 0)} uncut {fa['uncut']}, "
                      f"sub-posting cells {fa.get('subposting', 0)}" if "uncut" in fa else "")
                   + f" | in patch {roles}")
    out.append(f"  TOTAL free stations {tot['free']}: over 0.5 m {tot['before']} -> "
               f"{tot['after']}; in-patch groundside {tot['ground']}: over "
               f"{tot['ground_over']}; open-interior postings uncut {tot['uncut']}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("captures", nargs="*")
    ap.add_argument("--registered", action="store_true")
    ap.add_argument("--icao", action="append", default=None)
    ap.add_argument("--pack", action="append", default=[], metavar="ICAO")
    ap.add_argument("--plan", default=None, help="a placement plan (default: newest in Patches)")
    ap.add_argument("--unit", action="append", default=[],
                    help="print units whose resources contain this")
    ap.add_argument("--json", default=None)
    ap.add_argument("--perimeter", action="append", default=[], metavar="SOLVED.pkl",
                    help="STEP 3: judge the graded perimeters of a v2_solve_replay "
                         "--solved-out pickle (tools/perimeter_judge)")
    ap.add_argument("--perimeter-plan", default=None, metavar="REBAKE.json",
                    help="with --perimeter: the build's own perimeter records (the "
                         "replay's --emit --rebake-plan o4_v2_rebake_<ICAO>.json)")
    a = ap.parse_args(argv)
    if a.perimeter:
        results = []
        for path in a.perimeter:
            res = perimeter_of(path, a.perimeter_plan)
            print("\n".join(perimeter_lines(res, a.unit)), flush=True)
            results.append(res)
        if a.json:
            Path(a.json).write_text(json.dumps(results, indent=1, default=str))
        return 0
    from sunk_census import registered
    jobs = [("cap", p) for p in a.captures]
    if a.registered:
        jobs += [("cap", p) for p in registered(set(a.icao) if a.icao else None)]
    jobs += [("pack", i) for i in a.pack]
    results = []
    for kind, what in jobs:
        t = time.time()
        try:
            res = from_capture(what, a.plan) if kind == "cap" else from_pack(what, a.plan)
        except Exception as e:  # noqa: BLE001 -- a stale capture is reported, never fatal
            print(f"== {what}: UNREAD ({type(e).__name__}: {e})", flush=True)
            continue
        print(f"== {res['icao']} {what}: {len(res['rows'])} unit(s), derivation "
              f"{res['seconds']:.2f} s ({res['seconds_with_parse']:.2f} s with parse), "
              f"plan {res['plan']} ({time.time() - t:.0f} s)", flush=True)
        for x in res["rows"]:
            if x["composite"] or any(u in " ".join(x["res"]) for u in a.unit):
                print(_fmt(x))
        for r in res.get("step2", ()):
            print(f"  STEP2 {r['verdict']:<10} {str(r['unit'])[:28]:<28} {r['row']:<13} "
                  f"rows {r['rows']:>3} pad {r['pad']} D {r['D']} t {r['t']} base {r['base']} "
                  + (f"REFUSED ({r['refused']})" if "refused" in r else
                     f"z0 {r['z0']} today {r.get('z_today')} move {r.get('move')} "
                     f"riders {r.get('riders')}")
                  + f" @{r.get('lat')},{r.get('lon')}", flush=True)
        results.append(res)
        if a.json:
            Path(a.json).write_text(json.dumps(results, indent=1))
    print("\n".join(table(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
