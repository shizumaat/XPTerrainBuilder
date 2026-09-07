"""PIL plot of the site: cells by role, reached (green) / unreached (red) centrelines, contacts coloured by ceiling, the 07e site, named vertices."""
import os, sys, pickle, numpy as np
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from PIL import Image, ImageDraw
from auto_patch_v2.law import Law
import auto_patch_v2.planar.territories as T
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
bands = pickle.load(open(f"{SP}/HECA_t3_cut.pkl", "rb"))["bands"]; law = Law.for_airport("HECA")
to_xy, to_ll = airport.frame.transformers(); sx, sy = to_xy(31.412022, 30.127729)
R = float(sys.argv[1]) if len(sys.argv) > 1 else 700; W = 1400; s = W / (2 * R)
extra = sys.argv[2:]   # optional: chord "x1,y1,x2,y2"
def px(p): return (int((p[0] - (sx - R)) * s), int((sy + R - p[1]) * s))
im = Image.new("RGB", (W, W), "white"); d = ImageDraw.Draw(im)
COL = {"runway": (150,150,150), "runway_crossing": (120,120,120), "building": (220,220,220), "apron": (223,232,255), "junction": (255,232,192), "service_road": (224,255,224), "service_junction": (200,255,200)}
for c in cl.cells:
    col = COL.get(c.role, (255,208,208))
    d.polygon([px(p) for p in c.ring], fill=col, outline=(0,0,0))
    for h in c.holes: d.polygon([px(p) for p in h], fill="white", outline=(0,0,0))
for b in pm.breaklines.values():
    if b.kind != "taxi_centerline": continue
    pts = [px(pm.vertices[v].xy) for v in b.vertices(pm)]
    reached = any(v in bands for v in b.vertices(pm))
    d.line(pts, fill=(0,160,0) if reached else (220,0,0), width=3 if reached else 2)
st = T.reached_stations(pm, bands); lo, hi = 60.0, 130.0
for v in st:
    c = bands[v][1]; f = max(0.0, min(1.0, (c - lo) / (hi - lo)))
    col = (int(255*f), 0, int(255*(1-f))); x, y = px(pm.vertices[v].xy); d.ellipse([x-3,y-3,x+3,y+3], fill=col)
for v in (10159, 10286, 10228, 10564, 10541, 10763):
    if v in pm.vertices:
        x, y = px(pm.vertices[v].xy); d.ellipse([x-7,y-7,x+7,y+7], outline=(255,0,255), width=3); d.text((x+8, y-8), f"v{v} {bands.get(v,(0,0))[1]:.1f}", fill=(120,0,120))
x, y = px((sx, sy)); d.line([x-15,y,x+15,y], fill=(255,0,255), width=3); d.line([x,y-15,x,y+15], fill=(255,0,255), width=3)
for e in extra:
    x1,y1,x2,y2 = map(float, e.split(",")); d.line([px((x1,y1)), px((x2,y2))], fill=(0,0,0), width=4)
d.text((10,10), f"{2*R:.0f} m window; contacts blue=60 m .. red=130 m ceiling; green=reached centreline, red=unreached", fill=(0,0,0))
im.save(f"{ROOT}/scratch/site.png"); print("ok")
