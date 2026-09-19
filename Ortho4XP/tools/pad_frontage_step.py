#!/usr/bin/env python3
"""§28 (6)'s PAIR TABLE off a ``v2_solve_replay --capture`` pickle — the
read owner RULINGS 2026-09-13o/13p and 2026-09-18c (1) are taken on.

    cd Ortho4XP && venv/bin/python tools/pad_frontage_step.py CAP.pkl [--json OUT.json]

Per PAD-FACE PAIR of the §28 relation (a ``parking_lot`` /
``groundside_pavement`` / ``service_road`` / ``service_junction`` face and
a building pad it fronts): the face's frontage vertices, the pad's rim, the
pad's AIRSIDE-FRONTAGE vertices, each side's median ``dem_z``, and THREE
quantities —

* ``step``      — §28 (6)'s SHIPPED quantity, ``pad_frontage_gs.pair_dem_step_m``
  (frontage median − the pad's AIRSIDE-FRONTAGE median, owner 2026-09-18c (1));
* ``step_rim``  — the RETIRED pad-RIM-median quantity, kept as the control:
  the arrangement has been free to trim that rim since ``dba32406`` and it is
  what collapsed CYXY's two hillside pairs from 3.76/3.43 to 0.861/0.915
  (``docs/findings/beta2-CYXY-2-3-mechanism.md``);
* ``step_area`` — the FALLBACK quantity, an AREA-WEIGHTED DEM over the pad's
  own outline (``pad_frontage_gs.pad_area_weighted_dem``).

IT PRICES NO LAW AND COUNTS NO DEFECTS — defect counts come from
``harness/census.py`` and nowhere else.  Every predicate here is the
engine's own, imported and never re-spelled (the census-wrapper defect):
the population is ``pad_frontage_gs._groundside_geoms`` +
``constraints.pads._pad_polys`` / ``pad_fronts_airside`` /
``pad_frontage``, the quantities are ``pad_frontage_gs``'s own functions
and the bound is ``pad_frontage_gs.frontage_step_max_m``.

Promoted 2026-09-18 by lane ``b2frontagedatum`` from lane ``b2cyxyhill``'s
``scratchpad/probe28.py`` on its SECOND use (RULINGS ``7e90032``): its
first use bisected the CYXY-2/3 collapse to ``dba32406``, its second
measured the option-C population the new bound is centred on.
"""
from __future__ import annotations

import argparse
import json
import pickle
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def pair_rows(pm, law) -> list[dict]:
    """The §28 pair population with all three quantities, one dict per pair."""
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    from auto_patch_v2.constraints import pad_frontage_gs as G
    from auto_patch_v2.constraints.pads import (_pad_polys, pad_frontage,
                                                pad_fronts_airside)
    from auto_patch_v2.law.tables import role_side

    fronts = pad_fronts_airside(pm, law)
    rel = pad_frontage(pm, law)
    pads = [p for p in _pad_polys(pm, law) if p[0] in fronts]
    if not pads:
        return []
    tree = STRtree([p[3] for p in pads])
    xy = {v: vx.xy for v, vx in pm.vertices.items()}
    airside = G._airside_pavement_vertices(pm, law)
    r = G.frontage_radius_m(law)

    def med(vs):
        z = [float(pm.vertices[v].dem_z) for v in vs
             if pm.vertices[v].dem_z is not None]
        return statistics.median(z) if z else None

    out: list[dict] = []
    for gid, role, ref, gvs, gpoly in G._groundside_geoms(pm, law):
        cand = (tree.query(gpoly, predicate="dwithin", distance=r) if r > 0.0
                else tree.query(gpoly, predicate="intersects"))
        for pi in cand:
            pid, pref, pgroup, ppoly = pads[int(pi)]
            front = {v for v in gvs - set(pgroup) - airside
                     if ppoly.distance(Point(*xy[v])) <= r}
            if not front:
                continue
            air = G.pad_airside_frontage(pm, law, pid, rel=rel)
            fmed, rmed, amed = med(front), med(pgroup), med(air)
            aw = G.pad_area_weighted_dem(pm, ppoly, pgroup)
            out.append({
                "gs_face": gid, "gs_role": role, "gs_ref": ref,
                "pad_face": pid, "pad_ref": pref,
                "pad_rim_n": len(pgroup), "pad_area_m2": round(ppoly.area, 1),
                "front_n": len(front), "airside_front_n": len(air),
                "front_dem_med": fmed, "pad_rim_med": rmed,
                "pad_airside_med": amed, "pad_area_weighted_dem": aw,
                "step": G.pair_dem_step_m(pm, law, front, pid, ppoly, pgroup),
                "step_rim": None if (fmed is None or rmed is None) else fmed - rmed,
                "step_area": None if (fmed is None or aw is None) else fmed - aw,
                "airside_roles": sorted(
                    r_ for r_ in rel.get(pid, {}) if role_side(law, r_) == "airside"),
            })
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", type=Path, help="a v2_solve_replay --capture pickle")
    ap.add_argument("--icao", help="override the ICAO (default: the pickle's stem)")
    ap.add_argument("--json", type=Path, metavar="OUT.json")
    args = ap.parse_args(argv)

    from auto_patch_v2.constraints import pad_frontage_gs as G
    from auto_patch_v2.law import Law

    icao = args.icao or args.capture.stem.split(".")[0]
    with args.capture.open("rb") as fh:
        cap = pickle.load(fh)
    pm = cap["pm"]
    law = Law.for_airport(icao)
    bound = G.frontage_step_max_m(law)
    rows = pair_rows(pm, law)

    def f(x, n=3):
        return "-" if x is None else f"{x:.{n}f}"

    print(f"== {icao}  frontage_step_max_m {bound}  "
          f"pad_frontage_m {G.frontage_radius_m(law)}  pairs {len(rows)}")
    for row in sorted(rows, key=lambda t: -abs(t["step"] or 0.0)):
        held = row["step"] is not None and abs(row["step"]) > bound
        print(f"  {row['gs_ref']:>16} ({row['gs_role']:<20}) <- {row['pad_ref']:<14} "
              f"STEP {f(row['step']):>8} {'TERRACE' if held else 'armed  '}  "
              f"[rim {f(row['step_rim']):>8}  area {f(row['step_area']):>8}]  "
              f"front {row['front_n']:>3} med {f(row['front_dem_med'])} | "
              f"airside {row['airside_front_n']:>3} med {f(row['pad_airside_med'])} | "
              f"rim {row['pad_rim_n']:>3} med {f(row['pad_rim_med'])}")
    held = sum(1 for r in rows
               if r["step"] is not None and abs(r["step"]) > bound)
    print(f"  pairs_held_as_terrace {held}")
    if args.json:
        args.json.write_text(json.dumps(
            {"icao": icao, "frontage_step_max_m": bound,
             "pad_frontage_m": G.frontage_radius_m(law),
             "capture": str(args.capture), "pairs": rows,
             "pairs_held_as_terrace": held}, indent=1))
        print("WROTE", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
