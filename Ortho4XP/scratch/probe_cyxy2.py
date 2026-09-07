import os, sys, json, math
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
import numpy as np
from shapely.geometry import LineString, Point
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.__main__ import shared_repo_guard
from auto_patch_v2.planar.__main__ import default_inputs
from auto_patch_v2.airport.load import load_with_report
from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.planar.build import build as build_planar
from auto_patch_v2.pipeline.territory import territory_stage
from auto_patch_v2.planar.territories import NO_LABEL
law = Law.for_airport("CYXY")
with shared_repo_guard():
    airport, _ = load_with_report("CYXY", default_inputs(), law); cl = classify(airport, law, load_rules()); pm, _ = build_planar(airport, cl, law)
stage = territory_stage(pm, law, airport, cl, out=print)
terr = stage.terr
site = [(-6.16, -302.26), (42.71, -304.76)]
ids = list(pm.vertices)
P = np.array([pm.vertices[v].xy for v in ids])
def near(x, y): k = int(np.argmin(np.hypot(P[:,0]-x, P[:,1]-y))); return ids[k], float(np.hypot(P[k,0]-x, P[k,1]-y))
a, da = near(*site[0]); c, dc = near(*site[1])
print("triple ends", a, round(da,2), c, round(dc,2), "labels", terr.label.get(a, NO_LABEL), terr.label.get(c, NO_LABEL), "faces", [pm.faces[f].role+"#"+str(f) for f in pm.vertices[a].incident_faces], [pm.faces[f].role+"#"+str(f) for f in pm.vertices[c].incident_faces])
# the junction ring between them
for fid in set(pm.vertices[a].incident_faces) & set(pm.vertices[c].incident_faces):
    f = pm.faces[fid]; ring = list(pm.ring_vertices(f.ring))
    ia, ic = ring.index(a), ring.index(c)
    seg = ring[min(ia,ic):max(ia,ic)+1]
    print(f"face #{fid} {f.role} {f.ref}: ring {len(ring)} between a..c: {[ (v, terr.label.get(v, NO_LABEL)) for v in seg]}")
mid = ((site[0][0]+site[1][0])/2, (site[0][1]+site[1][1])/2)
print("joint edges within 80 m of site:")
for (u, w, ra, rb) in stage.edges:
    m = ((pm.vertices[u].xy[0]+pm.vertices[w].xy[0])/2, (pm.vertices[u].xy[1]+pm.vertices[w].xy[1])/2)
    if math.dist(m, mid) < 80: print("  ", u, w, ra, rb, "labels", terr.label[u], terr.label[w], "xy", [tuple(round(t,1) for t in pm.vertices[u].xy), tuple(round(t,1) for t in pm.vertices[w].xy)])
print("contours near site:")
for j in stage.joints:
    d = LineString(j.points).distance(Point(mid))
    if d < 80: print("  contour", j.id, round(j.length_m,1), j.roles, "pairs", j.pairs, "d", round(d,1), "pts", [tuple(round(t,1) for t in p) for p in j.points])
print("dropped", stage.dropped, "pairs", terr.stats.pairs)
