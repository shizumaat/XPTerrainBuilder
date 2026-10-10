"""pads61 probe — the R-W pin on the REAL classify: the building cells of the rule-2 arm (outline + absorb keys 0) against
the lane's (pin on), read inside the FRONTAGE ZONE of the true airside cells (side == airside, buffer pin_m) and of the
evidence-time airside the mint pins against (runway + pavement pages).  Per pad: symmetric-difference area inside each zone,
vertices, and where the largest differences stand.
usage (from Ortho4XP/): venv/bin/python pinprobe.py ICAO CAPTURE.pkl [--absorb0] [--top N]"""
from __future__ import annotations
import dataclasses as dc, pickle, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify, load_rules, roles
from auto_patch_v2.classify import evidence as ev
from auto_patch_v2.classify import road_absorb as ra
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline
from auto_patch_v2.planar.cluster import clusters as derive_clusters

icao, pkl = sys.argv[1], Path(sys.argv[2])
absorb0 = "--absorb0" in sys.argv
top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 12
cap = pickle.load(pkl.open("rb")); airport = cap["airport"]
law = Law.for_airport(icao)
airport = dc.replace(airport, clusters=derive_clusters(airport, law))
rules = load_rules()
cache = lambda: ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
real_r, real_e = roles.pad_outline, ev.pad_outline
poly = lambda c: Polygon(c.ring, c.holes)
nv = lambda g: len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)

def run(mod):
    roles.pad_outline = lambda l: mod(real_r(l)); ev.pad_outline = lambda l: mod(real_e(l))
    t0 = time.perf_counter(); arm = classify(airport, law, rules, cache=cache())
    roles.pad_outline, ev.pad_outline = real_r, real_e
    front = ev.minted_frontage(airport)
    return arm, dict(ev.CLUSTER_PADS), {k: list(v) for k, v in ra.ROADS_ABSORBED.items()}, list(ra.ROADS_KEPT), front, time.perf_counter() - t0

base, c0, _a, _k, front, t = run(lambda o: dc.replace(o, close_m=0.0, chord_m=0.0, hole_min_m2=0.0, road_absorb_m=0.0))
print(f"[{icao}] rule-2 arm: classify {t:.0f} s, pads {sum(1 for c in base.cells if c.role == 'building')}")
lane, c1, absorbed, kept, front, t = run((lambda o: dc.replace(o, road_absorb_m=0.0)) if absorb0 else (lambda o: o))
print(f"[{icao}] lane arm{' (absorb 0)' if absorb0 else ''}: classify {t:.0f} s, pads {sum(1 for c in lane.cells if c.role == 'building')}; "
      f"outline vertices {c1.get('outline_vertices_in')} -> {c1.get('outline_vertices_out')} over {c1.get('outline_simplified')}; "
      f"frontage clusters {c1.get('outline_frontage')}, fills refused {c1.get('outline_fills_refused')}, pinned {c1.get('outline_vertices_pinned')}; "
      f"roads absorbed {sum(map(len, absorbed.values()))} into {len(absorbed)}; kept {len(kept)}")
import collections
print("   kept reasons:", dict(collections.Counter(w for _r, _p, w in kept)))
pin = pad_outline(law).pin_m
air_cells = [poly(c) for c in base.cells if c.side == "airside" and c.role != "building"]
air_tree = STRtree(air_cells)
def zone_of(g, src_tree, src):
    hit = [src[int(k)] for k in src_tree.query(g.buffer(5.0), predicate="intersects")]
    return unary_union(hit).buffer(pin) if hit else None
bpads = [(c.ref, poly(c)) for c in base.cells if c.role == "building"]
lpads = [(c.ref, poly(c)) for c in lane.cells if c.role == "building"]
bu = unary_union([g for _r, g in bpads]); lu = unary_union([g for _r, g in lpads])
ltree = STRtree([g for _r, g in lpads])
rows = []
sd = bu.symmetric_difference(lu)
to_ll = airport.frame.transformers()[1]
for ref, g in bpads:
    near = [lpads[int(k)][1] for k in ltree.query(g.buffer(8.0), predicate="intersects")]
    lg = unary_union(near) if near else Polygon()
    z = zone_of(g.union(lg), air_tree, air_cells)
    if z is None:
        continue
    loc = sd.intersection(g.buffer(8.0))
    d = loc.intersection(z)
    zf = front.buffer(pin).intersection(g.buffer(12.0)) if front is not None else None
    df = loc.intersection(zf) if zf is not None else Polygon()
    if d.area > 0.05:
        p = max(getattr(d, "geoms", [d]), key=lambda q: q.area).representative_point()
        lon, lat = to_ll(p.x, p.y)
        rows.append((d.area, ref, df.area, nv(g), lat, lon, (d.difference(zf).area if zf is not None else d.area)))
print(f"[{icao}] pads whose ground differs inside the TRUE airside frontage zone (pin {pin} m): {len(rows)} of {len(bpads)}; total {sum(r[0] for r in rows):.1f} m2")
print("   ref: m2 in the true zone / m2 in the mint's zone / m2 in the true zone OUTSIDE the mint's zone; rule-2 vertices; at")
for a_, ref, dfa, n, lat, lon, out in sorted(rows, reverse=True)[:top]:
    print(f"   {ref:12s} {a_:8.2f} / {dfa:8.2f} / {out:8.2f}; v {n:4d}; {lat:.7f}, {lon:.7f}")
