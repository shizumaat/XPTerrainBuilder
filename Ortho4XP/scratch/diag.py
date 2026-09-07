"""Step-by-step diagnostics of the territory partition on the HECA complex holding the 07e site."""
import os, sys, pickle, time, math, numpy as np
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
cut = pickle.load(open(f"{SP}/HECA_t3_cut.pkl", "rb")); bands = cut["bands"]
law = Law.for_airport("HECA"); tt = law.tables.emit.terrace
to_xy, to_ll = airport.frame.transformers(); site = Point(to_xy(31.412022, 30.127729))
stations = T.reached_stations(pm, bands); cxy = {v: pm.vertices[v].xy for v in stations}
tol = snap_margin_m(law); min_d = law.tables.emit.identity.min_distinct_spacing_m; spacing = tt.simplify_factor * min_d
t = time.perf_counter(); comps = T._complexes(cl, law); print("complexes", len(comps), round(time.perf_counter()-t, 1), "s;", [(round(c.area), len(c.exterior.coords), len(c.interiors)) for c in comps])
comp = next(c for c in comps if c.buffer(1).covers(site)); print("site complex area", round(comp.area), "ring", len(comp.exterior.coords), "holes", len(comp.interiors))
here = {v: p for v, p in cxy.items() if comp.buffer(tol).covers(Point(p))}; print("contacts here", len(here))
P0, tags = T._boundary_nodes(comp, spacing); print("boundary nodes after simplify", len(P0))
t = time.perf_counter(); pt = T._partition(comp, here, spacing, tol); print("partition", round(time.perf_counter()-t, 1), "s; visible pairs", len(pt.I), "nodes", len(pt.P))
st = T.TerritoryStats(); cap_ = max(max(rc.longitudinal, rc.transverse) for rc in [role_cap(law, r) for r in tt.cell_roles] if rc)
t = time.perf_counter(); bad, dist = T._pairs(pt, bands, cap_, tt.min_step_m, st); print("pairs", round(time.perf_counter()-t, 1), "s; adjacent", len(st.pairs), "disagreeing", len(bad), "floor-only", st.floor_only_pairs)
sev, a, b, gap, d, hold = max(bad); print("severest", pt.contacts[a], pt.contacts[b], "gap", round(gap,2), "d", round(d,1), "hold", round(hold,2), "ll", to_ll(*pt.P[pt.n_boundary+a]), to_ll(*pt.P[pt.n_boundary+b]))
side = T._sides(pt, a, b); print("sides", int((side==0).sum()), int((side==1).sum()))
lines = T.reached_centrelines(pm, bands); ltree = STRtree(lines)
print("reached centrelines", len(lines), "crossing the complex", sum(1 for l in lines if l.intersects(comp)))
# candidate chords near the site
n_b = pt.n_boundary; bnd = (pt.I < n_b) & (pt.J < n_b); I, J = pt.I[bnd], pt.J[bnd]
L = np.hypot(pt.P[I,0]-pt.P[J,0], pt.P[I,1]-pt.P[J,1]); print("boundary chord candidates", len(I))
order = np.argsort(L)
cpts = [Point(pt.P[n_b+k]) for k in range(len(pt.contacts))]
near_site = [k for k in order if LineString([pt.P[I[k]], pt.P[J[k]]]).distance(site) < 80]
print("candidates within 80 m of site:", len(near_site), "shortest lengths", [round(float(L[k]),1) for k in near_site[:10]])
t = time.perf_counter()
for k in near_site[:12]:
    ch = LineString([pt.P[I[k]], pt.P[J[k]]])
    xl = [int(q) for q in ltree.query(ch, predicate="intersects") if lines[int(q)].intersects(ch)]
    parts = [g for g in split(comp, ch).geoms if g.geom_type == "Polygon"]
    piece = []
    for c in range(len(cpts)):
        piece.append(next((n for n, p in enumerate(parts) if p.buffer(tol).covers(cpts[c])), -1))
    piece = np.array(piece)
    s0 = set(piece[side==0].tolist()); s1 = set(piece[side==1].tolist())
    print(f"  chord {L[k]:.1f} m dist-to-site {ch.distance(site):.1f} crosses {len(xl)} lines; parts {len(parts)} sides->pieces {s0} | {s1}")
print("split tests", round(time.perf_counter()-t, 2), "s")
# global search stats
t = time.perf_counter(); found = T._find_chord(comp, pt, side, ltree, lines, tol, tt.joint_gap_m+min_d); print("find_chord", round(time.perf_counter()-t,1), "s ->", None if found is None else (round(found[0].length,1), found[1]))
