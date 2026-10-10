"""pads61: why a fallback pad joins a cluster pad under rule 2b — the cluster outlines of the two arms around one site."""
from __future__ import annotations
import dataclasses as dc, pickle, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from auto_patch_v2.classify import evidence as ev
from auto_patch_v2.classify import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline
from auto_patch_v2.planar.cluster import clusters as derive_clusters
icao, pkl, lat, lon = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
cap = pickle.load(pkl.open("rb")); airport = cap["airport"]
law = Law.for_airport(icao)
airport = dc.replace(airport, clusters=derive_clusters(airport, law))
to_xy = airport.frame.entry(); to_ll = airport.frame.transformers()[1]
site = Point(to_xy(lon, lat))
real = ev.pad_outline
seen = {}
orig = ev._cluster_pads
def spy(ap, lw, airside=None):
    got = orig(ap, lw, airside); seen["pads"] = list(got); seen["air"] = airside; return got
ev._cluster_pads = spy
rules = load_rules()
def run(mod):
    ev.pad_outline = lambda l: mod(real(l))
    e = ev.build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2, law, None)
    ev.pad_outline = real
    return list(seen["pads"]), e
b_cl, eb = run(lambda o: dc.replace(o, close_m=0.0, chord_m=0.0, hole_min_m2=0.0))
l_cl, el = run(lambda o: o)
def at(pads):
    return [(r, g) for r, g in pads if g.distance(site) < 1.0]
print("evidence pads at site: base", [(r, round(g.area)) for r, g in at(eb.pads)], " lane", [(r, round(g.area)) for r, g in at(el.pads)])
fb = at(eb.pads)[0][1]
for name, cl in (("base", b_cl), ("lane", l_cl)):
    near = [g for g in cl if g.distance(fb) < 10.0]
    for g in near:
        sh = Polygon(g.exterior)
        print(f" {name} cluster pad {g.area:,.0f} m2, {len(g.interiors)} holes, shell covers the fallback pad: {sh.covers(fb)}; "
              f"fallback inside shell {fb.intersection(sh).area:,.0f} of {fb.area:,.0f}; outside {fb.difference(sh).area:,.1f}; "
              f"pad covers {fb.intersection(g).area:,.0f}")
        out = fb.difference(sh)
        for q in sorted(getattr(out, "geoms", [out]), key=lambda q: -q.area)[:4]:
            if q.area > 0.01:
                c = q.representative_point(); lo, la = to_ll(c.x, c.y)
                print(f"     outside part {q.area:.1f} m2 at {la:.7f}, {lo:.7f}; to airside {q.distance(seen['air']):.2f} m")
lg = [g for g in l_cl if g.distance(fb) < 10.0]; bg = [g for g in b_cl if g.distance(fb) < 10.0]
d = unary_union(lg).difference(unary_union(bg)).intersection(fb.buffer(15.0))
print(" lane-only cluster ground within 15 m of the fallback pad:", round(d.area, 1), "m2 in", len(getattr(d, "geoms", [d])), "parts")
for q in sorted(getattr(d, "geoms", [d]), key=lambda q: -q.area)[:8]:
    c = q.representative_point(); lo, la = to_ll(c.x, c.y)
    print(f"     {q.area:8.1f} m2 at {la:.7f}, {lo:.7f}; to airside {q.distance(seen['air']):.2f} m; touches fallback {q.distance(fb) < 0.01}")
