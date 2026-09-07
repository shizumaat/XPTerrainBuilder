import os, sys, pickle, math, numpy as np, shapely
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
to_xy, to_ll = airport.frame.transformers(); site = Point(to_xy(31.412022, 30.127729))
stations = T.reached_stations(pm, bands); cxy = {v: pm.vertices[v].xy for v in stations}
tol = snap_margin_m(law); min_d = law.tables.emit.identity.min_distinct_spacing_m; spacing = tt.simplify_factor * min_d
comps = T._complexes(cl, law); comp = next(c for c in comps if c.buffer(1).covers(site))
cover = comp.buffer(tol); shapely.prepare(cover)
here = {v: p for v, p in cxy.items() if cover.covers(Point(p))}
pt = T._partition(comp, here, spacing, tol)
st = T.TerritoryStats(); cap_ = max(max(rc.longitudinal, rc.transverse) for rc in [role_cap(law, r) for r in tt.cell_roles] if rc)
bad, dist = T._pairs(pt, bands, cap_, tt.min_step_m, st); joint = {(min(a,b),max(a,b)) for _s,a,b,_g,_d,_h in bad}
arcs = T._change_arcs(pt, joint)
minx, miny, maxx, maxy = comp.bounds; W = 1400; R = max(maxx-minx, maxy-miny)/2; cx, cy = (minx+maxx)/2, (miny+maxy)/2; s = W/(2*R)
def px(p): return (int((p[0]-(cx-R))*s), int((cy+R-p[1])*s))
im = Image.new("RGB", (W, W), "white"); d = ImageDraw.Draw(im)
d.polygon([px(p) for p in comp.exterior.coords], fill=(235,240,255), outline=(0,0,255))
for h in comp.interiors: d.polygon([px(p) for p in h.coords], fill=(255,255,255), outline=(0,0,255))
for c in cl.cells:
    if c.role in ("primary_parallel","secondary_parallel","stub","cross_connector"): d.polygon([px(p) for p in c.ring], fill=(255,215,215), outline=(120,0,0))
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
for n, (a, b) in enumerate(arcs):
    d.line([px(pt.P[a]), px(pt.P[b])], fill=(255,0,255), width=4); x, y = px(pt.P[a]); d.text((x+5, y+5), f"arc{n} cyc{pt.tags[a][0]}", fill=(150,0,150))
x, y = px((site.x, site.y)); d.line([x-15,y,x+15,y], fill=(255,0,255), width=3); d.line([x,y-15,x,y+15], fill=(255,0,255), width=3)
for ci, ring in enumerate((comp.exterior, *comp.interiors)):
    x, y = px(ring.coords[0]); d.text((x, y), f"c{ci}", fill=(0,0,200))
d.text((10,10), f"site complex {comp.area:.0f} m2, {2*R:.0f} m window; nodes coloured by territory ceiling (blue 60 .. red 130); pink = taxi-family cells; magenta = change arcs", fill=(0,0,0))
im.save(f"{ROOT}/scratch/complex.png"); print("ok")
