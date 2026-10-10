"""jetspec: per hull POCKET of one unit's rule-2 outline — what it holds (graded roles m2, gate
startups, riders, taxi-centreline m, other units), its mouth width/depth, and whether the BAY
rule (a gate startup in it) fills it.  usage: python <this> ICAO CAP.pkl GRADED.json UNIT [UNIT..]"""
from __future__ import annotations
import dataclasses as dc, json, pickle, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src")); sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pads56")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from auto_patch_v2.airport import riders as R
from auto_patch_v2.law import Law
from auto_patch_v2.planar.cluster import clusters as derive_clusters
from classify_probe import outlines
from jet_probe import read_graded, pockets, parts
icao, pkl, graded = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]); units = sys.argv[4:]
cap = pickle.load(pkl.open("rb")); airport = cap["airport"]; law = Law.for_airport(icao)
airport = dc.replace(airport, clusters=derive_clusters(airport, law)); to_xy, to_ll = airport.frame.transformers()
t, _c, _s = outlines(airport, law, None)
faces = read_graded(graded, to_xy); ftree = STRtree([f[2] for f in faces])
cand = R.rider_candidates(airport, law); objs = {o.id: o for o in airport.dsf_objects}
rpts = [Point(*objs[o].xy) for o in cand]; rtree = STRtree(rpts)
gates = [Point(*s.xy) for s in airport.startups if s.kind == "gate"]; gtree = STRtree(gates) if gates else None
taxi = [LineString([airport.taxi_nodes[e.a].xy, airport.taxi_nodes[e.b].xy]) for e in airport.taxi_edges if not e.is_runway and e.a in airport.taxi_nodes and e.b in airport.taxi_nodes]
ttree = STRtree(taxi)
for uid in units:
    u = t[uid]; hull, pk = pockets(u)
    print(f"== {uid} area {u.area:,.0f} hull-u {hull.area-u.area:,.0f} m2; pockets {len(pk)}")
    fill = []
    for p in sorted(pk, key=lambda p: -p["area"]):
        g = p["poly"]; gb = g.buffer(0.5)
        ng = sum(1 for i in (gtree.query(gb) if gtree else []) if gb.covers(gates[int(i)]))
        nr = sum(1 for i in rtree.query(gb) if gb.covers(rpts[int(i)]))
        roles = Counter()
        for i in ftree.query(g):
            f = faces[int(i)]; a = f[2].intersection(g).area
            if a > 0.5: roles[f[0]] += a
        tm = sum(taxi[int(i)].intersection(g).length for i in ttree.query(g))
        c = g.centroid; bay = ng > 0
        if bay: fill.append(g)
        if p["area"] > 100 or bay:
            print(f"   {'BAY ' if bay else '    '}{p['area']:9,.0f} m2 mouth {p['mouth_w']:6.1f} depth {p['depth']:6.1f} gates {ng:3d} riders {nr:3d} taxi {tm:5.0f} m at {to_ll(c.x,c.y)[0]:.5f},{to_ll(c.x,c.y)[1]:.5f} | {dict((k, round(v)) for k, v in roles.most_common(6))}")
    if fill:
        F = unary_union(fill); roles = Counter()
        for i in ftree.query(F):
            f = faces[int(i)]; a = f[2].intersection(F).area
            if a > 0.5: roles[f[0]] += a
        print(f"   BAYS total {F.area:,.0f} m2 in {len(fill)} pockets: {dict((k, round(v)) for k, v in roles.most_common(12))}")
