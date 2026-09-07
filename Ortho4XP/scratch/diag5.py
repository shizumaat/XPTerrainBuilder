import os, sys, pickle, math, numpy as np, shapely
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import split
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m
import auto_patch_v2.planar.territories as T
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport("HECA"); tol = snap_margin_m(law)
seg = ((-61.628125, 1844.9212499999999), (-243.2140465116279, 1714.2348372093024))
line = T._extended(seg, tol); print("line", list(line.coords), "tol", tol)
for c in cl.cells:
    if len(c.ring) < 3: continue
    poly = Polygon(c.ring, [h for h in c.holes if len(h) >= 3])
    if not poly.intersects(line): continue
    inter = poly.intersection(line)
    parts = [g for g in split(poly, line).geoms if g.geom_type == "Polygon"]
    print("cell", c.id, c.role, c.ref, "valid", poly.is_valid, "area", round(poly.area), "inter len", round(inter.length, 2), "parts", len(parts), [round(p.area) for p in parts])
