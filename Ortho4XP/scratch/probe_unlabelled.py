"""Why are complex vertices still unlabelled after the notch fallback?"""
import os, sys, pickle, time, json, collections
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
import numpy as np
from shapely.geometry import Point
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m
from auto_patch_v2.planar import territories as T
from auto_patch_v2.constraints.no_step import reach_band_values
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport("HECA")
bands = reach_band_values(pm, law, airport)
terr = T.label_territories(pm, law, bands, cl)
st = terr.stats
print("labelled", st.labelled, "unlabelled", st.unlabelled, "fallback", st.notch_fallback, "wall", round(st.wall_s,1))
# rebuild the complexes to attribute each unlabelled vertex
stations = terr.contacts
outside = {c.ref for c in cl.cells if c.kind == T.OUTSIDE_ROAD_KIND}
fids = T._complex_faces(pm, law, stations, outside)
tol = snap_margin_m(law); min_d = law.tables.emit.identity.min_distinct_spacing_m
complexes = T._complexes(pm, fids, min_d/2.0)
spacing = law.tables.emit.terrace.simplify_factor * min_d
unl = [v for v, l in terr.label.items() if l == T.NO_LABEL]
print("unlabelled ids sample", unl[:40])
reasons = collections.Counter()
for ci, (comp, members) in enumerate(complexes):
    verts = sorted({v for fid in members for cyc in (pm.faces[fid].ring, *pm.faces[fid].holes) for v in pm.ring_vertices(cyc)})
    mine = [v for v in verts if terr.label.get(v) == T.NO_LABEL]
    if not mine: continue
    cover = comp.buffer(tol)
    here = {v: pm.vertices[v].xy for v in stations if cover.covers(Point(pm.vertices[v].xy))}
    g = T._graph(comp, here, spacing, tol)
    print(f"complex {ci}: faces {len(members)} verts {len(verts)} contacts {len(here)} unlabelled {len(mine)} graph {None if g is None else len(g.P)}")
    for v in mine[:60]:
        x, y = pm.vertices[v].xy
        inside = comp.covers(Point(x, y)); dist = comp.distance(Point(x, y))
        if g is None:
            reasons["no graph"] += 1; continue
        d, k = g.tree.query([x, y], k=1)
        Dk = g.D[:, k]
        fin = np.isfinite(Dk).any()
        reasons[("inside" if inside else f"outside"), "nearest-node-connected" if fin else "nearest-node-DISCONNECTED"] += 1
        roles = [pm.faces[f].role + "#" + str(f) for f in pm.vertices[v].incident_faces]
        print(f"  v{v} inside={inside} dist={dist:.1f} nearest node {k} at {d:.1f} m connected={fin} roles={roles}")
print(reasons)
for v in (10228, 10159):
    print(v, "label", terr.label.get(v), "contact", v in stations, "band", bands.get(v), [pm.faces[f].role + "#" + str(f) for f in pm.vertices[v].incident_faces])
# graph connectivity: how many boundary nodes have no finite D to any contact
for ci, (comp, members) in enumerate(complexes):
    cover = comp.buffer(tol)
    here = {v: pm.vertices[v].xy for v in stations if cover.covers(Point(pm.vertices[v].xy))}
    if len(here) < 2: continue
    g = T._graph(comp, here, spacing, tol)
    if g is None: continue
    dis = int((~np.isfinite(g.D).any(axis=0)).sum())
    print(f"complex {ci}: graph nodes {len(g.P)} boundary {g.n_boundary} contacts {len(g.contacts)} disconnected nodes {dis} holes {len(comp.interiors)}")
print("JOINT(10774,10159)?", terr.joint(10774, 10159), "pair", [p for p in st.pairs if set(p[:2]) == {10774, 10159}])
wa, wb = terr._where.get(10774), terr._where.get(10159); print("where", wa, wb, "d_inshape", None if wa is None or wb is None or wa[0]!=wb[0] else terr._dcc[wa[0]][wa[1], wb[1]], "bands", bands.get(10774), bands.get(10159), "cap", terr._cap, "min_step", terr._min_step)
print("pairs joint:", [p for p in st.pairs if p[6]])
