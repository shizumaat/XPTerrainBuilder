import os, sys, pickle, time, math, numpy as np
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from shapely.geometry import Point, LineString
from PIL import Image, ImageDraw
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m, role_cap
import auto_patch_v2.planar.territories as T
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
bands = pickle.load(open(f"{SP}/HECA_t3_cut.pkl", "rb"))["bands"]; law = Law.for_airport("HECA"); tt = law.tables.emit.terrace
to_xy, to_ll = airport.frame.transformers(); site = Point(to_xy(31.412022, 30.127729)); sx, sy = site.x, site.y
stations = T.reached_stations(pm, bands); cxy = {v: pm.vertices[v].xy for v in stations}
tol = snap_margin_m(law); min_d = law.tables.emit.identity.min_distinct_spacing_m; spacing = tt.simplify_factor * min_d
comps = T._complexes(cl, law); comp = next(c for c in comps if c.buffer(1).covers(site))
here = {v: p for v, p in cxy.items() if comp.buffer(tol).covers(Point(p))}
pt = T._partition(comp, here, spacing, tol)
st = T.TerritoryStats(); cap_ = max(max(rc.longitudinal, rc.transverse) for rc in [role_cap(law, r) for r in tt.cell_roles] if rc)
bad, dist = T._pairs(pt, bands, cap_, tt.min_step_m, st)
joint = {(min(a,b),max(a,b)) for _s,a,b,_g,_d,_h in bad}
print("nodes", len(pt.P), "boundary", pt.n_boundary, "contacts", len(pt.contacts), "disagreeing", len(bad))
# walk the ring near the site: runs of labels
ring = [k for k, (c, _p) in enumerate(pt.tags) if c == 0]
runs = []
for k in ring:
    t = int(pt.terr[k]); c = pt.contacts[t] if t >= 0 else None
    if runs and runs[-1][0] == t: runs[-1][2] += 1; runs[-1][3] = min(runs[-1][3], math.dist(pt.P[k], (sx, sy)))
    else: runs.append([t, c, 1, math.dist(pt.P[k], (sx, sy)), k])
print("label runs on the exterior ring (territory contact, ceiling, nodes, min dist to site, start node):")
for r in runs:
    if r[3] < 400: print("   ", r[1], None if r[1] is None else round(bands[r[1]][1],1), r[2], round(r[3]), r[4], "DISAGREE-with-next" if False else "")
# consecutive run pairs near site: agree?
for a, b in zip(runs, runs[1:] + runs[:1]):
    if min(a[3], b[3]) < 400 and a[0] >= 0 and b[0] >= 0:
        key = (min(a[0],b[0]), max(a[0],b[0])); d = dist.get(key)
        print("   change", a[1], round(bands[a[1]][1],1), "->", b[1], round(bands[b[1]][1],1), "d_inshape", None if d is None else round(d), "JOINT" if key in joint else "agree")
# holes near the site
for ci in range(1, 1 + len(comp.interiors)):
    ks = [k for k, (c, _p) in enumerate(pt.tags) if c == ci]
    dmin = min(math.dist(pt.P[k], (sx, sy)) for k in ks)
    if dmin < 300:
        labs = [(pt.contacts[int(pt.terr[k])], round(bands[pt.contacts[int(pt.terr[k])]][1],1)) if pt.terr[k] >= 0 else None for k in ks]
        print("hole", ci, "nodes", len(ks), "dist", round(dmin), "labels", sorted(set(labs), key=lambda x: (x is None, x)))
# picture: boundary nodes coloured by territory ceiling
R = 500; W = 1200; s = W/(2*R)
def px(p): return (int((p[0]-(sx-R))*s), int((sy+R-p[1])*s))
im = Image.new("RGB", (W, W), "white"); d = ImageDraw.Draw(im)
for c in cl.cells:
    col = {"apron": (223,232,255), "junction": (255,232,192), "building": (220,220,220)}.get(c.role, (255,208,208) if c.role not in ("runway","runway_crossing") else (150,150,150))
    d.polygon([px(p) for p in c.ring], fill=col, outline=(0,0,0))
    for h in c.holes: d.polygon([px(p) for p in h], fill="white", outline=(0,0,0))
for l in T.reached_centrelines(pm, bands): d.line([px(p) for p in l.coords], fill=(0,160,0), width=2)
lo, hi = 60.0, 130.0
def colr(c):
    f = max(0.0, min(1.0, (c-lo)/(hi-lo))); return (int(255*f), 0, int(255*(1-f)))
for k in range(pt.n_boundary):
    t = int(pt.terr[k]); x, y = px(pt.P[k])
    if t >= 0: d.ellipse([x-4,y-4,x+4,y+4], fill=colr(bands[pt.contacts[t]][1]))
    else: d.ellipse([x-4,y-4,x+4,y+4], outline=(0,0,0))
for k, c in enumerate(pt.contacts):
    x, y = px(pt.P[pt.n_boundary+k]); d.rectangle([x-3,y-3,x+3,y+3], fill=colr(bands[c][1]), outline=(0,0,0))
x, y = px((sx, sy)); d.line([x-15,y,x+15,y], fill=(255,0,255), width=3); d.line([x,y-15,x,y+15], fill=(255,0,255), width=3)
xs = [px(p) for p in comp.exterior.coords]; d.line(xs, fill=(0,0,255), width=1)
im.save(f"{ROOT}/scratch/labels.png"); print("png ok")
