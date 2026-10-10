"""pads61: what the R-W pin holds, and how much of it is the evidence-time airside being a SUPERSET of the true airside —
on the rule-2 arm's classify, per building cell over MIN m2: ring vertices, vertices pinned against the mint's frontage
(runway + every pavement page) and against the true airside CELLS (side == airside).
usage (from Ortho4XP/): venv/bin/python pincost.py ICAO CAPTURE.pkl [MIN_M2] [N]"""
from __future__ import annotations
import dataclasses as dc, pickle, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify, load_rules, roles
from auto_patch_v2.classify import evidence as ev
from auto_patch_v2.geom.outline_pin import Frontage
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline
from auto_patch_v2.planar.cluster import clusters as derive_clusters
icao, pkl = sys.argv[1], Path(sys.argv[2])
mn = float(sys.argv[3]) if len(sys.argv) > 3 else 5000.0
top = int(sys.argv[4]) if len(sys.argv) > 4 else 8
cap = pickle.load(pkl.open("rb")); airport = cap["airport"]
law = Law.for_airport(icao)
airport = dc.replace(airport, clusters=derive_clusters(airport, law))
rules = load_rules()
real_r, real_e = roles.pad_outline, ev.pad_outline
off = lambda o: dc.replace(o, close_m=0.0, chord_m=0.0, hole_min_m2=0.0, road_absorb_m=0.0)
roles.pad_outline = lambda l: off(real_r(l)); ev.pad_outline = lambda l: off(real_e(l))
arm = classify(airport, law, rules, cache=ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law)))
roles.pad_outline, ev.pad_outline = real_r, real_e
front = ev.minted_frontage(airport); pin = pad_outline(law).pin_m
poly = lambda c: Polygon(c.ring, c.holes)
air = [poly(c) for c in arm.cells if c.side == "airside" and c.role != "building"]
gnd_pav = [poly(c) for c in arm.cells if c.side != "airside" and c.role != "building"]
tree = STRtree(air)
to_ll = airport.frame.transformers()[1]
rows = []
for c in arm.cells:
    if c.role != "building":
        continue
    g = poly(c)
    if g.area < mn:
        continue
    def pinned(src):
        f = Frontage.near(g, src, pin, 4.0)
        if f is None:
            return 0
        return int(sum(f._pins(np.asarray(r.coords)[:, :2]).sum() for r in (g.exterior, *g.interiors)))
    hit = [air[int(k)] for k in tree.query(g.buffer(6.0), predicate="intersects")]
    nv = len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)
    p = g.representative_point(); lon, lat = to_ll(p.x, p.y)
    rows.append((g.area, c.ref, nv, pinned(front), pinned(unary_union(hit)) if hit else 0, lat, lon))
tot = [sum(r[i] for r in rows) for i in (2, 3, 4)]
print(f"[{icao}] building cells over {mn:.0f} m2: {len(rows)}; ring vertices {tot[0]}; pinned against the mint's frontage {tot[1]}; against the true airside cells {tot[2]}")
for a, ref, nv, pf, pt, lat, lon in sorted(rows, reverse=True)[:top]:
    print(f"   {ref:12s} {a:10,.0f} m2  vertices {nv:5d}  pinned (mint's union) {pf:5d}  pinned (true airside) {pt:5d}   {lat:.6f}, {lon:.6f}")
