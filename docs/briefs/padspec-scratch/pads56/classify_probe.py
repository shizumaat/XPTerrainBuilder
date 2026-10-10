"""pads56 scratch probe — §56 steps 1 and 3 on a capture, CLASSIFY ONLY (no solve).

(a) the cluster outlines with rule 2b off / on: pads, lost / new / joined ids, MultiPolygons,
    the vertex count per id asked;
(b) classify with the near-road absorption off / on: absorbed and kept roads, and the proof that
    every cell which is not an absorbing pad, an absorbed road, a re-cut neighbour or a gap piece
    is IDENTICAL (ref, role, ring) between the arms.
usage (from Ortho4XP/): venv/bin/python <this> ICAO CAPTURE.pkl [LAT LON RADIUS] [unit-id ...]
"""
from __future__ import annotations
import dataclasses as dc, pickle, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from shapely.geometry import Point, Polygon
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify, load_rules, roles
from auto_patch_v2.classify import road_absorb as ra
from auto_patch_v2.geom import cluster_building_evidence, cluster_outlines, deck_shades
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_admission, pad_outline
from auto_patch_v2.planar.cluster import clusters as derive_clusters


def outlines(airport, law, outline):
    st = law.tables.structures.placement
    to_xy = airport.frame.entry()
    stats: dict = {}
    got, counts = cluster_outlines(
        list(airport.clusters), to_xy, float(st.footprint_touch_m), airside=None, walled_only=True,
        min_m2=float(st.cluster_pad_min_m2), shades=deck_shades(getattr(airport, "partition", None), to_xy),
        bridge_m=float(getattr(st, "post_bridge_gap_m", 0.0)), admission=pad_admission(law),
        osm_evidence=cluster_building_evidence(getattr(airport, "buildings", ()) or ()),
        outline=outline, stats=stats)
    return {i: g for i, _c, g in got}, counts, stats


def main():
    icao, pkl = sys.argv[1], Path(sys.argv[2])
    rest = sys.argv[3:]
    site = None
    if len(rest) >= 3:
        try:
            site = (float(rest[0]), float(rest[1]), float(rest[2])); rest = rest[3:]
        except ValueError:
            site = None
    cap = pickle.load(pkl.open("rb")); airport = cap["airport"]
    law = Law.for_airport(icao)
    airport = dc.replace(airport, clusters=derive_clusters(airport, law))
    # (a)
    t, c0, _ = outlines(airport, law, None)
    s, c1, st = outlines(airport, law, pad_outline(law))
    print(f"[{icao}] (a) cluster pads rule 2 {c0['pads']} -> rule 2b {c1['pads']}; "
          f"still_in_pieces {c0['still_in_pieces']} -> {c1['still_in_pieces']}; thin_dropped "
          f"{c0['thin_dropped']} -> {c1['thin_dropped']}; outline vertices {c1['outline_vertices_in']} -> "
          f"{c1['outline_vertices_out']} over {c1['outline_simplified']} outlines")
    print("  lost:", [(k, round(t[k].area)) for k in t if k not in s])
    print("  new :", [(k, round(s[k].area)) for k in s if k not in t])
    print("  joined_from:", {k: v["outline_joined_from"] for k, v in st.items() if v["outline_joined_from"]})
    print("  multipolygons:", [k for k in s if s[k].geom_type != "Polygon"])
    grow = [(k, round(100 * (s[k].area / t[k].area - 1), 1)) for k in s if k in t and s[k].area > 1.05 * t[k].area]
    print("  same-id pads growing > 5 %:", grow)
    for k in rest:
        if k in st:
            print(f"  {k}: {st[k]} holes {len(s[k].interiors)} area {s[k].area:,.0f}")
    # (b)
    rules = load_rules()
    cache = lambda: ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
    real = roles.pad_outline
    roles.pad_outline = lambda l: dc.replace(real(l), road_absorb_m=0.0)
    t0 = time.perf_counter(); base = classify(airport, law, rules, cache=cache())
    roles.pad_outline = real
    seen = {}
    real_abs = ra.absorb_near_roads
    def spy(cells, law_, outline, **kw):
        seen.update(kw, cells=list(cells)); return real_abs(cells, law_, outline, **kw)
    ra.absorb_near_roads = spy
    arm = classify(airport, law, rules, cache=cache())
    ra.absorb_near_roads = real_abs
    absorbed = {k: list(v) for k, v in ra.ROADS_ABSORBED.items()}; kept = list(ra.ROADS_KEPT)
    print(f"[{icao}] (b) classify x2 {time.perf_counter() - t0:.0f} s; cells {len(base.cells)} -> {len(arm.cells)}; "
          f"roads absorbed {sum(map(len, absorbed.values()))} into {len(absorbed)} pads; kept {len(kept)}; "
          f"recuts {arm.stats.get('mixed_pad_recuts', 0)}; gap pieces "
          f"{sum(1 for c in base.cells if roles.is_late_cell(c))} -> {sum(1 for c in arm.cells if roles.is_late_cell(c))}")
    bykey = {}
    for c in base.cells:
        bykey[(c.role, c.ref, c.ring, c.holes)] = c
    gone = {r for v in absorbed.values() for r in v}
    changed = [c for c in arm.cells if (c.role, c.ref, c.ring, c.holes) not in bykey]
    armkeys = {(c.role, c.ref, c.ring, c.holes) for c in arm.cells}
    missing = [c for c in base.cells if (c.role, c.ref, c.ring, c.holes) not in armkeys]
    kinds = {"absorbing_pad": 0, "recut_neighbour": 0, "gap_piece": 0, "OTHER": 0}
    other = []
    for c in changed:
        if c.role == "building" and c.ref in absorbed: kinds["absorbing_pad"] += 1
        elif roles.is_late_cell(c): kinds["gap_piece"] += 1
        elif c.side == "groundside" and c.evidence.get("mixed_pad_cutback"): kinds["recut_neighbour"] += 1
        else: kinds["OTHER"] += 1; other.append((c.role, c.ref))
    print(f"  changed cells in the arm: {len(changed)} {kinds}; OTHER: {other[:10]}")
    mk = {"absorbed_road": 0, "pad": 0, "gap_piece": 0, "recut": 0}
    for c in missing:
        if c.ref in gone: mk["absorbed_road"] += 1
        elif c.role == "building": mk["pad"] += 1
        elif roles.is_late_cell(c): mk["gap_piece"] += 1
        else: mk["recut"] += 1
    print(f"  base cells not in the arm: {len(missing)} {mk}")
    pads_same = sum(1 for c in arm.cells if c.role == "building" and c.ref not in absorbed
                    and (c.role, c.ref, c.ring, c.holes) in bykey)
    pads_all = sum(1 for c in arm.cells if c.role == "building")
    print(f"  pads: {pads_all}; absorbing {len(absorbed)}; non-absorbing pads byte-identical {pads_same} of {pads_all - len(absorbed)}")
    for p, v in absorbed.items():
        a0 = next(Polygon(c.ring, c.holes) for c in base.cells if c.ref == p and c.role == "building")
        a1 = next(Polygon(c.ring, c.holes) for c in arm.cells if c.ref == p and c.role == "building")
        nv = lambda g: len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)
        print(f"    {p}: {len(v)} roads {v}; area {a0.area:,.0f} -> {a1.area:,.0f} (+{100 * (a1.area / a0.area - 1):.1f} %); vertices {nv(a0)} -> {nv(a1)}")
    print("  kept:", kept)
    we = seen.get("wall_extended"); ko = seen.get("keep_out")
    print(f"  wall_extended area {0 if we is None else we.area:,.0f} m2; keep_out area {0 if ko is None else ko.area:,.0f} m2")
    byref = {c.ref: Polygon(c.ring, c.holes) for c in seen.get("cells", [])}
    for r, p, why in kept:
        g = byref.get(r)
        if g is None: continue
        ov = g.intersection(we).area if (we is not None and why == ra.KEPT_WALL) else (g.intersection(ko).area if ko is not None else 0.0)
        print(f"    kept {r} (pad {p}, {why}): road area {g.area:,.0f} m2, overlap with the reason's geometry {ov:,.1f} m2 ({100 * ov / max(g.area, 1e-9):.0f} %)")
    if site:
        to_xy = airport.frame.entry(); pt = Point(to_xy(site[1], site[0]))
        fam = {"service_road", "service_junction"}
        near0 = [c for c in base.cells if c.role in fam and Polygon(c.ring, c.holes).distance(pt) <= site[2]]
        near1 = [c for c in arm.cells if c.role in fam and Polygon(c.ring, c.holes).distance(pt) <= site[2]]
        print(f"  site {site}: road cells {len(near0)} -> {len(near1)}; absorbed there {sorted(c.ref for c in near0 if c.ref in gone)}; "
              f"left {sorted(c.ref for c in near1)}")
        for c in arm.cells:
            if c.role == "building" and Polygon(c.ring, c.holes).distance(pt) <= 1.0:
                print(f"  site pad {c.ref}: vertices {len(c.ring) + sum(map(len, c.holes))} holes {len(c.holes)}")


if __name__ == "__main__":
    main()
