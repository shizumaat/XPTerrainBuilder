"""The 23 HECA census airside_no_step rows vs the declared label joints."""
import os, sys, json, math, pickle
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src"); sys.path.insert(0, ROOT + "/tools"); sys.path.insert(0, ROOT + "/tools/harness")
import numpy as np
from pathlib import Path
from shapely.geometry import LineString, Point
import check_grade as cg
PATCH = Path("/tmp/harness/HECA_20260907T124610.osm")
nodes, ways = cg._parse_osm(PATCH)
side = json.load(open(str(PATCH) + ".axes.json"))
anchor = side.get("projection_anchor") or side.get("anchor")
print("anchor key", anchor, [k for k in side if "anchor" in k or "origin" in k or "frame" in k][:6])
rows = json.load(open(f"{SP}/heca_rows.json"))
items = rows if isinstance(rows, list) else next(iter(rows.values())) if not isinstance(rows.get("rows"), list) else rows["rows"]
ns = [r for r in items if r["family"] == "airside_no_step"]
ids = list(nodes); LL = np.array([nodes[i] for i in ids])
frames = {"mean": cg._ll_to_m_factory(nodes)}
if anchor: frames["anchor"] = cg._ll_to_m_factory(nodes, anchor)
best = None
for name, f in frames.items():
    XY = np.array([f(la, lo) for la, lo in LL])
    a = ns[0]["site_m"][0]; d = np.hypot(XY[:,0]-a[0], XY[:,1]-a[1]).min()
    print("frame", name, "nearest node to site a:", round(d, 3), "m")
    if best is None or d < best[0]: best = (d, name, f, XY)
_d, fname, ll_to_m, XY = best
joints_all = cg._terrace_joints_to_m(side.get("terrace_joints"), ll_to_m)
joints_lab = cg._terrace_joints_to_m([r for r in side.get("terrace_joints") if r.get("label_boundary")], ll_to_m)
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.territory import territory_stage
from auto_patch_v2.planar.territories import NO_LABEL
law = Law.for_airport("HECA")
stage = territory_stage(pm, law, airport, cl, out=lambda m: None); terr = stage.terr
to_xy, to_ll = airport.frame.transformers()
vids = list(pm.vertices); VP = np.array([pm.vertices[v].xy for v in vids])
edge_set = {(min(e.a, e.b), max(e.a, e.b)) for e in pm.edges.values()}
contours = [LineString(j.points) for j in stage.joints]
def pmv(lat, lon):
    x, y = to_xy(lon, lat); k = int(np.argmin(np.hypot(VP[:,0]-x, VP[:,1]-y))); return vids[k], float(np.hypot(VP[k,0]-x, VP[k,1]-y))
print(f"{'step':>6} {'d':>6} {'va':>6} {'vb':>6} {'la':>6} {'lb':>6} joint edge allow_all allow_lab  d_contour  faces")
for r in ns:
    (ax, ay), (bx, by) = r["site_m"]
    ka = int(np.argmin(np.hypot(XY[:,0]-ax, XY[:,1]-ay))); kb = int(np.argmin(np.hypot(XY[:,0]-bx, XY[:,1]-by)))
    va, da = pmv(*LL[ka]); vb, db = pmv(*LL[kb])
    la, lb = terr.label.get(va, NO_LABEL), terr.label.get(vb, NO_LABEL)
    j = terr.joint(la, lb)
    pa, pb = pm.vertices[va].xy, pm.vertices[vb].xy
    seg = LineString([pa, pb]); dc = min((c.distance(seg) for c in contours), default=float("nan"))
    fa = set(pm.vertices[va].incident_faces) & set(pm.vertices[vb].incident_faces)
    print(f"{r['magnitude_m']:6.2f} {r['distance_m']:6.1f} {va:6d} {vb:6d} {la:6d} {lb:6d} {str(j):5s} {str((min(va,vb),max(va,vb)) in edge_set):5s} {cg._terrace_step_allowance(joints_all, ax, ay, bx, by):8.2f} {cg._terrace_step_allowance(joints_lab, ax, ay, bx, by):8.2f} {dc:9.1f}  {[pm.faces[f].role+'#'+str(f) for f in fa]} snap {da:.2f}/{db:.2f}")
print("---- rows in the filtered set for the 23 pairs")
from auto_patch_v2.pipeline.territory import territory_constraints
from auto_patch_v2.model.constraints import Diff
cs, counts, walls = territory_constraints(pm, law, airport, stage)
byp = {}
for rw in cs.rows():
    if isinstance(rw, Diff): byp.setdefault((min(rw.a, rw.b), max(rw.a, rw.b)), []).append(rw)
pairs = [(10498,10500),(10499,10501),(10220,10222),(10216,10218),(10206,10208),(10208,10210),(10214,10216),(10215,10217),(10207,10209),(10209,10211),(10205,10207),(10307,10309),(10202,10204),(10971,10973)]
for p in pairs:
    rs = byp.get(p, [])
    print(p, "labels", terr.label.get(p[0]), terr.label.get(p[1]), "joint", terr.joint(terr.label.get(p[0], -1), terr.label.get(p[1], -1)), "rows", [(r.source.generator, round(r.cap, 4), round(r.d, 1), round(r.cap * r.d, 3)) for r in rs])
print("dropped", stage.dropped)
