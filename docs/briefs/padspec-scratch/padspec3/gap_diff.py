"""padspec3 scratch: the LATE cells (gap pieces, ribbons, facade cells) one classify arm
has and another has not, near a site, and what stands on their ground in the other arm.
usage: venv/bin/python <this> BASE.cells.pkl ARM.cells.pkl LAT LON R ICAO"""
import pickle, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from shapely.geometry import Polygon, Point
from auto_patch_v2.model.planar import is_late_ref
from auto_patch_v2.law import Law
import dataclasses as dc

base = pickle.load(open(sys.argv[1], "rb")); arm = pickle.load(open(sys.argv[2], "rb"))
lat, lon, R = map(float, sys.argv[3:6]); icao = sys.argv[6]
# the frame: metres per degree at the site is enough for a radius test
import math
mx = 111320.0 * math.cos(math.radians(lat)); my = 110574.0
def key(c): return (c[0], c[1], c[2], c[3])
bl = {key(c): c for c in base if is_late_ref(c[1])}
al = {key(c): c for c in arm if is_late_ref(c[1])}
print(f"late cells {len(bl)} -> {len(al)}; gap-prefixed {sum(1 for k in bl if str(k[1]).startswith('gap'))} -> {sum(1 for k in al if str(k[1]).startswith('gap'))}")
lost = [bl[k] for k in bl if k not in al]; new = [al[k] for k in al if k not in bl]
print(f"lost {len(lost)}, new {len(new)}; lost refs {sorted(set(c[1] for c in lost))[:40]}")
print(f"new refs {sorted(set(c[1] for c in new))[:40]}")
apads = [(c[1], Polygon(c[2], c[3])) for c in arm if c[0] == "building"]
bpads = {c[1]: Polygon(c[2], c[3]) for c in base if c[0] == "building"}
for c in lost:
    g = Polygon(c[2], c[3])
    cover = [(ref, round(g.intersection(p).area, 1)) for ref, p in apads if p.intersects(g)]
    same = [k for k in al if k[1] == c[1]]
    print(f"  lost {c[0]} {c[1]} {g.area:,.0f} m2: on arm pads {cover}; a cell of the same ref in the arm: {len(same)}")
