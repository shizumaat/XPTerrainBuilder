import os, sys, pickle, math, numpy as np, shapely
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree
from shapely.ops import split
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m, role_cap
import auto_patch_v2.planar.territories as T
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
bands = pickle.load(open(f"{SP}/HECA_t3_cut.pkl", "rb"))["bands"]; law = Law.for_airport("HECA"); tt = law.tables.emit.terrace
to_xy, to_ll = airport.frame.transformers(); site = Point(to_xy(31.412022, 30.127729))
stations = T.reached_stations(pm, bands); cxy = {v: pm.vertices[v].xy for v in stations}
tol = snap_margin_m(law); min_d = law.tables.emit.identity.min_distinct_spacing_m; spacing = tt.simplify_factor * min_d; clearance = tt.joint_gap_m + min_d
comps = T._complexes(cl, law); comp = next(c for c in comps if c.buffer(1).covers(site))
cover = comp.buffer(tol); shapely.prepare(cover)
here = {v: p for v, p in cxy.items() if cover.covers(Point(p))}
pt = T._partition(comp, here, spacing, tol)
st = T.TerritoryStats(); cap_ = max(max(rc.longitudinal, rc.transverse) for rc in [role_cap(law, r) for r in tt.cell_roles] if rc)
bad, dist = T._pairs(pt, bands, cap_, tt.min_step_m, st)
joint = {(min(a,b),max(a,b)) for _s,a,b,_g,_d,_h in bad}
arcs = T._change_arcs(pt, joint)
print("change arcs", len(arcs))
for k, (a, b) in enumerate(arcs):
    ta, tb = int(pt.terr[a]), int(pt.terr[b])
    print(f"  arc {k}: cycle {pt.tags[a][0]} nodes {a},{b} labels {pt.contacts[ta]}({bands[pt.contacts[ta]][1]:.1f}) | {pt.contacts[tb]}({bands[pt.contacts[tb]][1]:.1f}) len {math.dist(pt.P[a], pt.P[b]):.0f} m dist-to-site {LineString([pt.P[a], pt.P[b]]).distance(site):.0f} m")
lines = T.reached_centrelines(pm, bands); ltree = STRtree(lines)
simp = T._simplified(comp, spacing); ctree = STRtree(shapely.points(pt.P[pt.n_boundary:]))
for i in range(len(arcs)):
    for j in range(i+1, len(arcs)):
        f = T._cut_path(comp, simp, pt, arcs[i], arcs[j], ltree, cover, ctree, tol, clearance, spacing)
        if f is None: print(f"  pair {i},{j}: no path"); continue
        segs, L = f
        print(f"  pair {i},{j}: path {L:.0f} m, {len(segs)} segs; dist-to-site {min(s_.distance(site) for s_ in segs):.0f}")
print("---- path debug for arcs 0 and 4")
import auto_patch_v2.planar.territories as T2
arc_a, arc_b = arcs[0], arcs[4]
src = T._densify(tuple(pt.P[arc_a[0]]), tuple(pt.P[arc_a[1]]), spacing); dst = T._densify(tuple(pt.P[arc_b[0]]), tuple(pt.P[arc_b[1]]), spacing)
holes = [k for k, (ci, _p) in enumerate(pt.tags) if ci > 0]
print("src", len(src), "dst", len(dst), "holes", len(holes))
f = T._cut_path(comp, simp, pt, arc_a, arc_b, ltree, cover, ctree, tol, clearance, spacing)
segs, L = f
for sg in segs: print("   seg", [tuple(round(v,1) for v in c) for c in sg.coords], round(sg.length,1))
print("cost", L)
print("---- node-level path")
holes = [k for k, (ci, _p) in enumerate(pt.tags) if ci > 0]
hole_of = {k: pt.tags[k][0] for k in holes}
for k in holes:
    if math.dist(pt.P[k], (-223.1, 1829.6)) < 2 or math.dist(pt.P[k], (-355.8, 2171.2)) < 2 or math.dist(pt.P[k], (-380.9, 2164.1)) < 2:
        print("  node", k, "cycle", hole_of[k], tuple(round(v,1) for v in pt.P[k]))
for ci in sorted(set(hole_of.values())):
    ks = [k for k in holes if hole_of[k] == ci]
    xs = [pt.P[k] for k in ks]
    print("  hole", ci, "n", len(ks), "bbox", tuple(round(v) for v in (min(x for x,_ in xs), min(y for _,y in xs), max(x for x,_ in xs), max(y for _,y in xs))))
