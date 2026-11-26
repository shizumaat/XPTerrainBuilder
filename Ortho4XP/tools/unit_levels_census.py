#!/usr/bin/env python3
"""THE UNIT LEVELS CENSUS (RULINGS 2026-11-25g; spec
``docs/specs/terminal-frontage-split-level-20261125.md`` §4.2, step 1):
every terminal-sized pack unit's two floors as
``auto_patch_v2/airport/unit_storey.unit_levels`` reads them, over capture
pickles, beside what today's readers minted.

Per unit: plan m2, ``air_y``, ``land_y``, rise, rung, ``g_air``, ``g_land``,
verdict, face length, frontage-band vertex count -- and TODAY: the upward
storey parts (``upper_storeys``, R1: ``R1``), the levels the map minted on
the unit's pads (``Registries.landings`` level records ``<pad>/p<k>``, their
``y``) and its storey shells (``PlanarMap.storey_shells``).  Then the three
reports of §4.2: (1) ``held`` counts by sign and rung; (2) every unit whose
reading differs from today's; (3) the identity airports' rows.
Reads only; builds nothing; one capture at a time.

    venv/bin/python tools/unit_levels_census.py CAP.pkl [CAP.pkl ...] [--json OUT]
    venv/bin/python tools/unit_levels_census.py --registered [--icao ICAO ...]

``--registered`` reads the newest capture per ICAO ``docs/frames.jsonl``
names that is still on disk (``tools/sunk_census.registered``).
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import O4_Console_Encoding as _o4console  # noqa: E402

_o4console.configure_console_streams()

#: the airports whose rows report (3) lists (spec §4.2 (3), §5 step 1)
IDENTITY = ("HECA", "KATL", "KBUF", "KEGE", "BIKF", "OMDB", "LGAV")
#: a minted level this far off the record's rise is a differing reading
_AGREE_M = 0.5


def _today(pm, airport, law, air, plans: dict) -> dict:
    """``{unit index: {"r1": bool, "minted": [y, ...]}}`` -- today's
    readers (module docstring) for the units in ``plans``."""
    from auto_patch_v2.airport.unit_storey import upper_storeys
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    r1 = {s.unit for s in upper_storeys(airport, law, air)}
    pads: dict = {}
    for f in pm.faces.values():
        xy = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
        if len(xy) >= 3:
            pads.setdefault(str(f.ref), []).append(Polygon(xy).buffer(0.0))
    minted: dict = {}
    for ref, rec in (getattr(pm.registries, "landings", {}) or {}).items():
        if rec.get("deck") is None and "/p" in str(ref) and rec.get("y") is not None:
            minted.setdefault(str(rec.get("block")), []).append(float(rec["y"]))
    shells = {str(i): sh for sh in (getattr(pm, "storey_shells", ()) or ())
              for i in sh.member_ids}
    units = airport.partition.units
    out = {}
    for ui, plan in plans.items():
        ys = []
        for block, yl in minted.items():
            P = unary_union(pads.get(block, []))
            if not P.is_empty and P.intersection(plan).area >= 0.25 * plan.area:
                ys.extend(yl)
        for m in units[ui].members:
            sh = shells.get(str(m.id))
            if sh is not None:
                b = float(sh.levels[sh.block])
                ys.extend(round(float(y) - b, 3) for k, y in enumerate(sh.levels) if k != sh.block)
                break
        out[ui] = {"r1": ui in r1, "minted": sorted(set(round(y, 2) for y in ys))}
    return out


def low_refusal(pm, airport, law, air, plan) -> list[str]:
    """Why ``planar/low_level.plan_low`` minted no lower level on the held
    pads under ``plan`` (a unit read a storey DOWN), per pad: ``conforming``,
    the ``unit_base`` pre-gate of ``low_level_split`` (STEPPED only), then
    what ``plan_low`` itself answers -- its ``refused`` reason (the ground
    drop), no part fronting the airside, no part a storey under the top,
    the level cut refused, or the level it WOULD mint past the pre-gate."""
    from auto_patch_v2.airport.obj8_grade import STEPPED
    from auto_patch_v2.law.tables import design as design_law
    from auto_patch_v2.planar import low_level as ll
    from auto_patch_v2.planar.pad_blocks import unit_base
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    near = float(design_law(law).pad_frontage_m)
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    held = pm.registries.held
    pads: dict = {}
    for f in pm.faces.values():
        if str(f.ref) in held:
            pads.setdefault(str(f.ref), []).append(
                Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]).buffer(0.0))
    out = []
    to_xy = airport.frame.entry()
    for ref, gs in sorted(pads.items()):
        P = unary_union(gs)
        if P.intersection(plan).area < 0.25 * min(P.area, plan.area):
            continue
        h, why = held[ref], []
        if h.get("conforming"):
            why.append("conforming")
        base = unit_base(P, airport)[0]
        if base != STEPPED:
            why.append(f"unit_base {base!r} is not STEPPED (low_level_split pre-gate)")
        a = air.intersection(P.buffer(50.0))
        got = ll.plan_low(P, a, airport, law, grid, None, why) if not a.is_empty else None
        if got is not None:
            why.append(f"plan_low WOULD mint y_lo {got[3]['y_lo']:+.2f} "
                       f"({got[3]['area_m2']} m2, top {got[3]['top_y']:+.2f})")
        elif not any(w.startswith("ground drop") for w in why):
            parts = ll._unit_parts(P, airport, to_xy)
            top = ll.top_level(parts, a, airport, law, to_xy, near) if parts else None
            if not parts:
                why.append("no unit parts on the pad")
            elif top is None:
                why.append("no part fronts the airside (top_level)")
            else:
                sm = 2.0 * ll._plane_band() if top[1] is not None else step
                n = sum(1 for p, _xy in parts if p.base_y <= top[0] - sm)
                why.append(f"top {top[0]:+.2f}: " + (f"no part {sm:g} m under it" if not n
                                                     else f"{n} low parts, level cut refused"))
        out.append(f"{ref} ({P.area:.0f} m2, {h.get('verdict')}): " + "; ".join(why))
    return out


def census(path: str) -> dict:
    """One capture's rows (module docstring)."""
    with open(path, "rb") as fh:
        return census_of(pickle.load(fh), path)


def census_of(cap: dict, path: str) -> dict:
    """:func:`census` of an unpickled capture ``cap``."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline.frontage_publication import (
        frontage_levels,
        map_sides,
        terminal_frontage_records,
    )
    icao, airport, pm = cap["icao"], cap["airport"], cap["pm"]
    law = Law.for_airport(icao)
    if getattr(airport, "undersides", None) is None:
        # a capture older than the underside maps (RULINGS 2026-11-25m): rung
        # L0 reads them, derived as the build's pack stage derives them
        from auto_patch_v2.airport import frame_entry as _fe
        from auto_patch_v2.airport.obj8 import ResourceCache
        from auto_patch_v2.airport.unit_underside import attach_undersides
        if not any(getattr(c, "pids", None) for c in airport.clusters or ()):
            import dataclasses as _dc

            from auto_patch_v2.planar.cluster import clusters
            airport = _dc.replace(airport, clusters=tuple(clusters(airport, law)))
        airport, _w = attach_undersides(airport, law, ResourceCache(
            law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law)), cached=False)
    levels = frontage_levels(pm, law, airport)
    recs = terminal_frontage_records(pm, law, airport, levels)
    to_ll = airport.frame.transformers()[1]
    plans = {r.unit: r.plan for r in levels}
    air = map_sides(pm, law)[0]
    today = _today(pm, airport, law, air, plans)
    from auto_patch_v2.airport.unit_storey import carried_by, frontage_held
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    pads: dict = {}
    for f in pm.faces.values():
        pads.setdefault(str(f.ref), []).append(
            Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]).buffer(0.0))
    rows = []
    for r, rec in zip(levels, recs, strict=True):
        c = plans[r.unit].centroid
        lat, lon = to_ll(c.x, c.y)
        row = {**{k: v for k, v in rec.items() if k != "face_ll"},
               "lat": round(lat, 6), "lon": round(lon, 6), **today[r.unit],
               # step 2: whether the frontage law takes the record
               "frontage": bool(rec["block"] is not None and frontage_held(r, airport, law)
                                and carried_by(r, unary_union(pads[rec["block"]])))}
        if r.rise < 0.0 or any(a[0] > r.air_y for a in r.clues.get("air_planes", ())[:1]):
            # a storey DOWN, or the airside's own objects above the floor read
            row["low_refusal"] = low_refusal(pm, airport, law, air, plans[r.unit])
        rows.append(row)
    return {"icao": icao, "path": path, "rows": rows}


def differs(row: dict) -> bool:
    """Whether the record's reading differs from today's (report (2)):
    a second floor where today mints none, none where today mints one, or
    a minted level more than :data:`_AGREE_M` off the record's rise."""
    two = row["land_y"] is not None
    if not row["minted"]:
        return two and row["verdict"] == "held" or (two and not row["r1"] and row["rise"] > 0)
    if not two:
        return True
    return min(abs(y - row["rise"]) for y in row["minted"]) > _AGREE_M


def _clues(c: dict) -> str:
    return (f"air_planes {[a[0] for a in c.get('air_planes', [])][:4]} "
            f"span {c['face_span']} walls {len(c['retaining_walls'])} "
            f"fences {len(c['fences'])} upper_roads {len(c['upper_roads'])} "
            f"neighbours {len(c['neighbours'])}")


def _fmt(icao: str, r: dict) -> str:
    return (f"  {icao} {r['unit']:12s} {str(r['block']):11s} {r['plan_m2']:9.0f} m2  "
            f"air {r['air_y']:+6.2f} "
            f"land {'   -  ' if r['land_y'] is None else format(r['land_y'], '+6.2f')} "
            f"rise {r['rise']:+6.2f} {str(r['witness'] or '-'):12s} "
            f"L0 {r.get('l0')} g {r['g_air']}/{r['g_land']} {r['verdict']:11s} "
            f"face {r['face_m']:6.0f} m "
            f"band {r['band_vertices']:4d} lv {[lv['rise'] for lv in r['levels']]} "
            f"clues {_clues(r['clues'])}  today R1={'y' if r['r1'] else 'n'} "
            f"minted {r['minted']}  law {'TAKES' if r.get('frontage') else '-'}  "
            f"@{r['lat']},{r['lon']}")


def report(results: list[dict]) -> None:
    """The three §4.2 reports over ``results``."""
    print("\n(1) HELD by sign and rung")
    held: dict = {}
    for res in results:
        for r in res["rows"]:
            if r["verdict"] == "held":
                k = ("up" if r["rise"] > 0 else "down", r["witness"])
                held.setdefault(k, []).append(f"{res['icao']}:{r['unit']}")
    for k in sorted(held):
        print(f"  {k[0]:4s} {k[1]:12s} {len(held[k]):4d}  {' '.join(held[k])}")
    verdicts: dict = {}
    for res in results:
        for r in res["rows"]:
            verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    print(f"  all verdicts: {verdicts}")
    print("\n(2) DIFFERS from today's readers")
    for res in results:
        for r in res["rows"]:
            if differs(r):
                print(_fmt(res["icao"], r))
    print("\n(3) IDENTITY airports")
    for res in results:
        if res["icao"] in IDENTITY:
            for r in res["rows"]:
                print(_fmt(res["icao"], r))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("captures", nargs="*")
    ap.add_argument("--registered", action="store_true")
    ap.add_argument("--icao", action="append", default=None)
    ap.add_argument("--json", default=None, help="write every row here")
    a = ap.parse_args(argv)
    from sunk_census import registered
    paths = list(a.captures) + (registered(set(a.icao) if a.icao else None)
                                if a.registered else [])
    results = []
    for path in paths:
        t = time.time()
        try:
            res = census(path)
        except Exception as e:  # noqa: BLE001 -- a stale capture is reported, never fatal
            print(f"== {path}: UNREAD ({type(e).__name__}: {e})")
            continue
        print(f"== {res['icao']} {path}: {len(res['rows'])} unit(s) ({time.time() - t:.0f} s)")
        for r in res["rows"]:
            print(_fmt(res["icao"], r))
            for w in r.get("low_refusal", ()):
                print(f"      plan_low: {w}")
        results.append(res)
    report(results)
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
