"""jetspec: THE GATE WITNESS — per cluster unit (rule-2 outline), the apt.dat 1300 startups by
kind within R of the outline, the riders within reach (any kind), and the hull pockets that hold
a gate or a rider; prints the units a name-free witness would call 'a terminal with jetways'.
usage (from Ortho4XP/): venv/bin/python <this> ICAO CAP.pkl [--reach 60]"""
from __future__ import annotations
import argparse, dataclasses as dc, pickle, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pads56"))
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree
from auto_patch_v2.airport import riders as R
from auto_patch_v2.law import Law
from auto_patch_v2.planar.cluster import clusters as derive_clusters
from classify_probe import outlines

ap = argparse.ArgumentParser(); ap.add_argument("icao"); ap.add_argument("pkl", type=Path); ap.add_argument("--reach", type=float, default=60.0)
a = ap.parse_args()
cap = pickle.load(a.pkl.open("rb")); airport = cap["airport"]; law = Law.for_airport(a.icao)
airport = dc.replace(airport, clusters=derive_clusters(airport, law))
from auto_patch_v2.law.tables import design as _design; d = _design(law)
print(f"[{a.icao}] law stand_zone_startup_kinds={list(d.stand_zone_startup_kinds)} reach={d.stand_zone_startup_reach_m} radius={d.stand_zone_radius_m} D={d.jetway_strip_m}")
t, c0, _ = outlines(airport, law, None)
print(f"[{a.icao}] startups {len(airport.startups)} by kind {dict(Counter(s.kind for s in airport.startups))}; units {len(t)}")
ids = sorted(t); polys = [t[i] for i in ids]; tree = STRtree(polys)
cand = R.rider_candidates(airport, law); objs = {o.id: o for o in airport.dsf_objects}
riders = Counter()
for oid, (reach, kind) in cand.items():
    o = objs[oid]; pt = Point(*o.xy)
    for i in tree.query(pt.buffer(reach)):
        p = polys[int(i)]
        if (kind == "agp" and p.covers(pt)) or p.exterior.distance(pt) <= reach:
            riders[ids[int(i)]] += 1; break
rows = []
for pid, u in t.items():
    near = Counter()
    for s in airport.startups:
        pt = Point(*s.xy)
        if u.exterior.distance(pt) <= a.reach and not u.contains(pt):
            near[s.kind] += 1
    hull = u.convex_hull
    pk = [g for g in getattr(hull.difference(u), "geoms", [hull.difference(u)]) if not g.is_empty and g.area > 1]
    pk_gate = sum(1 for g in pk if any(g.buffer(a.reach).covers(Point(*s.xy)) and s.kind == "gate" for s in airport.startups))
    rows.append((pid, round(u.area), near.get("gate", 0), near.get("tie_down", 0), sum(near.values()), riders.get(pid, 0), len(pk), pk_gate, round(hull.area - u.area)))
rows.sort(key=lambda r: (-r[2], -r[5]))
print(f"[{a.icao}] unit, area, gates<={a.reach:.0f}m, tie_downs, all starts, riders, pockets, pockets holding a gate, hull-u m2")
for r in rows:
    if r[2] or r[5] or r[3]:
        print("   ", r)
