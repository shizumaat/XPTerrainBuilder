"""padspec2 scratch probe — §56 step 2: WHERE DO THE JETWAY RIDERS STAND
relative to the building outline, today (rule 2) and after step 1 (rule 2b)?

Reads a v2_solve_replay capture: `airport.dsf_objects`, `airport.partition`,
`airport.clusters`; runs `riders.rider_candidates` (the one site every
rider's reach is born) and the engine's own `geom.cluster_outlines` twice
(outline=None = today; outline=pad_outline(law) = step 1 as landed on
claude/cloudpadspec).  Per rider within 12 m of any unit outline: kind,
resource, nearest unit, signed distance to the rule-2 outline and to the
2b outline (negative = inside), and for an .agp the footprint's area
outside the 2b outline.  Also censuses every DSF object whose resource
name says jetway/bridge/gate: rider or body (partition member)?

usage: rider_probe.py ICAO CAPTURE.pkl [--json OUT]
"""
from __future__ import annotations
import json, math, os, pickle, sys, time
from collections import Counter
from pathlib import Path

from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP")
sys.path.insert(0, str(ROOT / "src"))
from auto_patch_v2.geom.cluster_outline import (cluster_outlines, deck_shades,
                                                cluster_building_evidence, _parts)
from auto_patch_v2.classify.evidence import pad_admission
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline
from auto_patch_v2.airport import riders as R

JET = ("jetway", "jet_way", "jetbridge", "bridge", "gate", "finger", "passerelle", "aerobridge")


def outlines(icao, airport, law, to_xy, outline):
    st = law.tables.structures.placement
    cl = list(airport.clusters)
    shades = deck_shades(getattr(airport, "partition", None), to_xy)
    got, counts = cluster_outlines(cl, to_xy, float(st.footprint_touch_m), airside=None,
                                   walled_only=True, min_m2=float(st.cluster_pad_min_m2),
                                   shades=shades, bridge_m=float(getattr(st, "post_bridge_gap_m", 0.0)),
                                   admission=pad_admission(law),
                                   osm_evidence=cluster_building_evidence(getattr(airport, "buildings", ()) or ()),
                                   refused=[], outline=outline)
    return {pid: poly for pid, c, poly in got}, counts


def sdist(poly, pt):
    d = poly.exterior.distance(pt)
    for h in poly.interiors:
        d = min(d, h.distance(pt))
    return -d if poly.contains(pt) else d


def main():
    icao, pkl = sys.argv[1], Path(sys.argv[2])
    out_json = Path(sys.argv[sys.argv.index("--json") + 1]) if "--json" in sys.argv else None
    t0 = time.perf_counter()
    cap = pickle.load(pkl.open("rb"))
    airport = cap["airport"]
    law = Law.for_airport(icao)
    to_xy = airport.frame.entry()
    print(f"[{icao}] loaded {time.perf_counter()-t0:.0f} s; dsf_objects {len(getattr(airport,'dsf_objects',()) or ())}")
    cand = R.rider_candidates(airport, law)
    kinds = Counter(k for _r, k in cand.values())
    print(f"[{icao}] rider candidates {len(cand)} by kind {dict(kinds)}")
    objs = {o.id: o for o in airport.dsf_objects}
    skipped, members = R._no_geometry_paths(airport)
    # the jetway-named resources: rider or body?
    jet_objs = [o for o in airport.dsf_objects if any(j in os.path.basename(o.path).lower() for j in JET)]
    jc = Counter()
    for o in jet_objs:
        jc[("rider:" + cand[o.id][1]) if o.id in cand else ("body" if o.path in members else "other")] += 1
    print(f"[{icao}] jetway-named placements {len(jet_objs)}: {dict(jc)}; distinct resources "
          f"{sorted(set(os.path.basename(o.path) for o in jet_objs))[:12]}")
    today, c0 = outlines(icao, airport, law, to_xy, None)
    step1, c1 = outlines(icao, airport, law, to_xy, pad_outline(law))
    print(f"[{icao}] pads today {c0['pads']} step1 {c1['pads']}")
    ids = sorted(today)
    tree0 = STRtree([today[i] for i in ids])
    reach_max = float(law.tables.structures.placement.rider_reach_max_m)
    rows = []
    for oid, (reach, kind) in cand.items():
        o = objs[oid]
        pt = Point(*o.xy)
        near = [int(i) for i in tree0.query(pt.buffer(reach_max + 15.0))]
        if not near:
            continue
        best = min(near, key=lambda i: sdist(today[ids[i]], pt))
        pid = ids[best]
        d0 = sdist(today[pid], pt)
        d1 = sdist(step1[pid], pt) if pid in step1 else math.nan
        if d0 > reach_max + 15.0:
            continue
        rec = {"id": oid, "res": os.path.basename(o.path), "kind": kind, "reach": reach,
               "unit": pid, "d_today": round(d0, 2), "d_step1": round(d1, 2),
               "hosted_today": d0 <= reach or (kind == "agp" and d0 <= 0),
               "ll": [round(float(o.lat), 7), round(float(o.lon), 7)] if hasattr(o, "lat") else None}
        if kind == "agp":
            rp = getattr(o, "resolved_path", None) or o.path
            fp = R.agp_footprint_xy(rp, (float(o.xy[0]), float(o.xy[1])), float(getattr(o, "heading", 0.0) or 0.0)) if rp and os.path.isfile(rp) else None
            if fp and len(fp) >= 3:
                fpoly = Polygon(fp)
                if not fpoly.is_valid:
                    fpoly = fpoly.buffer(0)
                rec["fp_m2"] = round(fpoly.area, 1)
                rec["fp_outside_step1_m2"] = round(fpoly.difference(step1[pid]).area, 1) if pid in step1 else None
                rec["fp_outside_today_m2"] = round(fpoly.difference(today[pid]).area, 1)
        rows.append(rec)
    rows.sort(key=lambda r: (r["unit"], r["d_today"]))
    by_kind = Counter(r["kind"] for r in rows)
    print(f"[{icao}] riders within {reach_max+15:.0f} m of a unit outline: {len(rows)} {dict(by_kind)}")
    ins0 = sum(1 for r in rows if r["d_today"] <= 0)
    ins1 = sum(1 for r in rows if r["d_step1"] <= 0)
    hosted = sum(1 for r in rows if r["hosted_today"])
    print(f"[{icao}]   inside the rule-2 outline today: {ins0}; inside the 2b outline: {ins1}; hosted today (within reach): {hosted}")
    moved = [r for r in rows if r["d_today"] > 0 and r["d_step1"] <= 0]
    print(f"[{icao}]   anchors the close moved INSIDE: {len(moved)}")
    for r in rows:
        print("   ", {k: r[k] for k in r if k != "ll"})
    if out_json:
        out_json.write_text(json.dumps({"icao": icao, "candidates": len(cand), "kinds": dict(kinds),
                                        "jetway_named": dict(jc), "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
