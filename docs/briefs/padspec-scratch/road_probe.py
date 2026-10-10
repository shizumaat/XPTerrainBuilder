"""padspec scratch probe 2 — THE ROAD ABSORPTION rule (spec (b)).
For every emitted groundside road face near the site: its area, the share
of it within D m of the simplified outline (rc3/dp1/h200), and the verdict
absorbed (share >= 1 - eps) / split (part) / passes by.
usage: road_probe.py ICAO CAPTURE.pkl GRADED.json LAT LON RADIUS D
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
from outline_probe import rule_close_round, parts, ROOT, nverts
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from auto_patch_v2.geom.cluster_outline import cluster_outlines, deck_shades, cluster_building_evidence
from auto_patch_v2.classify.evidence import pad_admission
from auto_patch_v2.law import Law

ROAD_ROLES = {"service_road", "road", "groundside_road", "small_road"}

def main():
    icao, pkl, graded, lat, lon, radius, D = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7])
    cap = pickle.load(pkl.open("rb")); airport = cap["airport"]
    law = Law.for_airport(icao); st = law.tables.structures.placement
    to_xy = airport.frame.entry(); site = Point(to_xy(lon, lat))
    got, counts = cluster_outlines(list(airport.clusters), to_xy, float(st.footprint_touch_m), airside=None,
                                   walled_only=True, min_m2=float(st.cluster_pad_min_m2),
                                   shades=deck_shades(getattr(airport, "partition", None), to_xy),
                                   bridge_m=float(getattr(st, "post_bridge_gap_m", 0.0)),
                                   admission=pad_admission(law),
                                   osm_evidence=cluster_building_evidence(getattr(airport, "buildings", ()) or ()))
    pads = {pid: rule_close_round(poly, 3.0, 1.0, 200.0) for pid, c, poly in got}
    G = json.load(graded.open()); V = {v[0]: to_xy(v[2], v[1]) for v in G["vertices"]}
    roads = []
    for f in G["faces"]:
        role, ref = f.get("role", "?"), str(f.get("ref", "?"))
        if not (role in ROAD_ROLES or ref.startswith("route") or ref.startswith("small_roads")):
            continue
        ring = [V[i] for i in f["ring"] if i in V]
        if len(ring) < 3: continue
        p = Polygon(ring); p = p if p.is_valid else p.buffer(0)
        if p.distance(site) <= radius:
            roads.append((role, ref, p, len(f["ring"])))
    near_pads = {pid: g for pid, g in pads.items() if g.distance(site) <= radius}
    U = unary_union(list(near_pads.values()))
    band = U.buffer(D, join_style=1)
    print(f"[{icao}] pads near: {list(near_pads)}; road faces near: {len(roads)}; D={D}")
    verdict = Counter(); vabs = 0; fabs = 0; m2abs = 0.0
    for role, ref, p, n in roads:
        inside = p.intersection(band).area / max(p.area, 1e-9)
        touch = p.distance(U) <= 1.0
        v = "ABSORBED" if inside >= 0.98 else ("SPLIT" if inside >= 0.02 else "PASSES")
        verdict[v] += 1
        if v == "ABSORBED": vabs += n; fabs += 1; m2abs += p.area
        print(f"  {role:14s} {ref:22s} area {p.area:8.0f} verts {n:4d} within-{D:.0f}m {inside:5.2f} touches {touch} -> {v}")
    print(f"  VERDICTS {dict(verdict)}; absorbed faces {fabs} / verts {vabs} / {m2abs:.0f} m2")
    # the outline after absorbing: union + re-close, vertex count
    absorbed = [p for role, ref, p, n in roads if p.intersection(band).area / max(p.area,1e-9) >= 0.98]
    for pid, g in near_pads.items():
        g2 = rule_close_round(unary_union([g] + [p for p in absorbed if p.distance(g) <= D]), 3.0, 1.0, 200.0)
        print(f"  pad {pid}: verts {nverts(g)} -> {nverts(g2)} with roads absorbed; area {g.area:.0f} -> {g2.area:.0f}; pieces {len(parts(g2))}")

if __name__ == "__main__":
    main()
