import os, sys, pickle, time, math, numpy as np
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from auto_patch_v2.classify.evidence import polygon_parts
from auto_patch_v2.law import Law
import auto_patch_v2.planar.territories as T
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
bands = pickle.load(open(f"{SP}/HECA_t3_cut.pkl", "rb"))["bands"]; law = Law.for_airport("HECA")
to_xy, to_ll = airport.frame.transformers(); site = Point(to_xy(31.412022, 30.127729))
for roles in (("apron",), ("apron", "junction"), ("apron", "junction", "service_road", "service_junction")):
    polys = [Polygon(c.ring, [h for h in c.holes if len(h) >= 3]).buffer(0) for c in cl.cells if c.role in roles and c.kind != "service_road" and len(c.ring) >= 3]
    parts = [p for p in polygon_parts(unary_union(polys)) if p.area > 0]
    comp = next((p for p in parts if p.buffer(1).covers(site)), None)
    print(roles, "complexes", len(parts), "site complex", None if comp is None else (round(comp.area), len(comp.exterior.coords), len(comp.interiors)))
    if comp is not None:
        st = T.reached_stations(pm, bands); cov = comp.buffer(0.5)
        here = [v for v in st if cov.covers(Point(pm.vertices[v].xy))]
        ceils = sorted(round(bands[v][1]) for v in here)
        print("   contacts", len(here), "ceiling histogram", np.histogram(ceils, bins=[60,70,80,90,100,110,120,130,140])[0].tolist())
# the raw pav132 polygon
for p in airport.pavements:
    poly = Polygon(p.outer, [h for h in p.holes if len(h) >= 3]).buffer(0)
    if poly.buffer(1).covers(site): print("raw pavement", p.id, round(poly.area), "holes", len(p.holes), repr(p.description)[:60])
refs = {c.ref for c in cl.cells if Polygon(c.ring).buffer(1).covers(site)}; print("cells at site", refs)
print("cells with ref pav132 by role:", {r: sum(1 for c in cl.cells if c.ref.split('#')[0]=="pav132" and c.role==r) for r in set(c.role for c in cl.cells if c.ref.split('#')[0]=="pav132")})
