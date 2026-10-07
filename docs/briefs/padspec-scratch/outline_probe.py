"""padspec scratch probe — the SIMPLIFIED BUILDING OUTLINE rule, pure geometry,
run on a v2_solve_replay capture.  Reads `airport.clusters` (the same rings
`classify/evidence._cluster_pads` reads), reproduces today's closed outline
(rule 2: dilate/erode at footprint_touch_m, simplify 0.05) through the engine's
own `geom.cluster_outlines`, then applies candidate outline rules and reports
per pad: vertices, area, area added / removed vs the true footprint union, and
what the added area lies on in the EMITTED graded.json (role census).

usage: outline_probe.py ICAO CAPTURE.pkl GRADED.json LAT LON [RADIUS_M] [--json OUT]
"""
from __future__ import annotations
import json, math, pickle, sys, time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path("/Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP")
sys.path.insert(0, str(ROOT / "src"))
from auto_patch_v2.geom.cluster_outline import (cluster_outlines, deck_shades,
                                                cluster_building_evidence, _parts)
from auto_patch_v2.classify.evidence import pad_admission
from auto_patch_v2.law import Law


def parts(g):
    return _parts(g)


def nverts(g):
    n = 0
    for p in parts(g):
        n += len(p.exterior.coords) - 1
        for h in p.interiors:
            n += len(h.coords) - 1
    return n


def nholes(g):
    return sum(len(p.interiors) for p in parts(g))


# ───────────── candidate outline rules (pure geometry) ─────────────
def rule_close(u, r_m, simplify_m, hole_min_m2=0.0, mitre=5.0):
    """Morphological CLOSE by r_m (fills every concavity narrower than 2r),
    then Douglas–Peucker at simplify_m (topology preserving), then drop
    holes under hole_min_m2.  Mitred joins keep corners square."""
    if r_m > 0:
        g = u.buffer(r_m, join_style=2, mitre_limit=mitre).buffer(-r_m, join_style=2, mitre_limit=mitre)
    else:
        g = u
    if not g.is_valid:
        g = g.buffer(0.0)
    if simplify_m > 0:
        g = g.simplify(simplify_m, preserve_topology=True)
    if hole_min_m2 > 0:
        out = []
        for p in parts(g):
            keep = [h for h in p.interiors if Polygon(h).area >= hole_min_m2]
            out.append(Polygon(p.exterior, keep))
        g = unary_union(out) if out else g
    if not g.is_valid:
        g = g.buffer(0.0)
    return g


def rule_close_round(u, r_m, simplify_m, hole_min_m2=0.0):
    """TRUE morphological close (round joins: result ⊇ input by construction),
    then DP simplify (removes the arc vertices), then small-hole fill."""
    g = u.buffer(r_m, join_style=1, quad_segs=8).buffer(-r_m, join_style=1, quad_segs=8)
    if not g.is_valid:
        g = g.buffer(0.0)
    return rule_close(g, 0.0, simplify_m, hole_min_m2)


def rule_hull(u):
    return unary_union([p.convex_hull for p in parts(u)])


def rule_close_open(u, r_close, r_open, simplify_m, hole_min_m2=0.0):
    """close then OPEN (drops protuberances thinner than 2*r_open) — the
    rule the owner did NOT ask for; kept as a reference arm."""
    g = rule_close(u, r_close, 0.0)
    g = g.buffer(-r_open, join_style=2).buffer(r_open, join_style=2)
    if not g.is_valid:
        g = g.buffer(0.0)
    return rule_close(g, 0.0, simplify_m, hole_min_m2)


VARIANTS = {
    "V0_today":        lambda u: u,
    "V1_dp1":          lambda u: rule_close(u, 0.0, 1.0),
    "V2_dp2":          lambda u: rule_close(u, 0.0, 2.0),
    "V3_c3_dp1":       lambda u: rule_close(u, 3.0, 1.0),
    "V4_c5_dp1":       lambda u: rule_close(u, 5.0, 1.0),
    "V5_c5_dp1_h200":  lambda u: rule_close(u, 5.0, 1.0, hole_min_m2=200.0),
    "V6_c8_dp1_h200":  lambda u: rule_close(u, 8.0, 1.0, hole_min_m2=200.0),
    "V7_c5_dp2_h200":  lambda u: rule_close(u, 5.0, 2.0, hole_min_m2=200.0),
    "V8_c5_o2_dp1":    lambda u: rule_close_open(u, 5.0, 2.0, 1.0, 200.0),
    "V9_hull":         rule_hull,
    "V10_rc5_dp1_h200": lambda u: rule_close_round(u, 5.0, 1.0, 200.0),
    "V11_rc3_dp1_h200": lambda u: rule_close_round(u, 3.0, 1.0, 200.0),
}


def main():
    icao, pkl, graded, lat, lon = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    radius = float(sys.argv[6]) if len(sys.argv) > 6 and not sys.argv[6].startswith("--") else 150.0
    out_json = None
    if "--json" in sys.argv:
        out_json = Path(sys.argv[sys.argv.index("--json") + 1])
    t0 = time.perf_counter()
    with pkl.open("rb") as fh:
        cap = pickle.load(fh)
    airport = cap["airport"]
    print(f"[{icao}] capture loaded {time.perf_counter()-t0:.0f} s; clusters {len(getattr(airport,'clusters',()) or ())}")
    law = Law.for_airport(icao)
    st = law.tables.structures.placement
    to_xy = airport.frame.entry()
    site = Point(to_xy(lon, lat))
    cl = list(airport.clusters)
    shades = deck_shades(getattr(airport, "partition", None), to_xy)
    refused = []
    # today's closed outlines — the engine's own derivation (airside clip is the arrangement's)
    got, counts = cluster_outlines(cl, to_xy, float(st.footprint_touch_m), airside=None,
                                   walled_only=True, min_m2=float(st.cluster_pad_min_m2),
                                   shades=shades, bridge_m=float(getattr(st, "post_bridge_gap_m", 0.0)),
                                   admission=pad_admission(law),
                                   osm_evidence=cluster_building_evidence(getattr(airport, "buildings", ()) or ()),
                                   refused=refused)
    print(f"[{icao}] cluster_outlines: {counts}")
    # the TRUE footprint union per pad (raw rings, no close) for area-added accounting
    raw_by_id = {}
    for pid, c, poly in got:
        ps = []
        for r in (getattr(c, "rings", ()) or ()):
            if len(r) >= 3:
                g = Polygon([to_xy(lo, la) for la, lo in r])
                if not g.is_valid:
                    g = g.buffer(0.0)
                ps.extend(parts(g))
        ru = unary_union(ps) if ps else poly
        # a split cluster's piece owns only the raw rings near it (close radius <= 8 m)
        raw_by_id[pid] = ru.intersection(poly.buffer(10.0, join_style=2)) if ru.area > 1.5 * poly.area else ru

    # emitted faces (graded.json) in the same frame, for the "what it swallows" census
    G = json.load(graded.open())
    V = {v[0]: to_xy(v[2], v[1]) for v in G["vertices"]}
    faces = []
    for f in G["faces"]:
        ring = [V[i] for i in f["ring"] if i in V]
        if len(ring) < 3:
            continue
        try:
            p = Polygon(ring, [[V[i] for i in h if i in V] for h in f.get("holes", [])])
            if not p.is_valid:
                p = p.buffer(0.0)
        except Exception:
            continue
        faces.append((f.get("role", "?"), f.get("ref", "?"), p, len(f["ring"]) + sum(len(h) for h in f.get("holes", []))))
    ftree = STRtree([p for _r, _f, p, _n in faces])
    print(f"[{icao}] graded faces {len(faces)}")

    def face_census(region):
        """m2 of `region` by emitted role, and the refs touched"""
        by_role = Counter(); refs = defaultdict(float)
        if region.is_empty:
            return by_role, refs
        for k in ftree.query(region, predicate="intersects"):
            role, ref, p, _n = faces[int(k)]
            a = p.intersection(region).area
            if a > 0.5:
                by_role[role] += a
                refs[f"{role}:{ref}"] += a
        return by_role, refs

    # emitted faces within radius of the site (the owner's "shapes around the terminal")
    near = [(r, f, p, n) for r, f, p, n in faces if p.distance(site) <= radius]
    nc = Counter(); nv = Counter()
    for r, f, p, n in near:
        base = f.split("#")[0]
        key = r if r != "building" else f"building:{base}" + ("#collar" if "#collar" in f else ("#blk" if "#" in f else ""))
        nc[key] += 1; nv[key] += n
    print(f"\n[{icao}] EMITTED within {radius:.0f} m of {lat},{lon}: {len(near)} faces / {sum(nv.values())} ring vertices")
    for k, c in sorted(nc.items(), key=lambda kv: -nv[kv[0]]):
        print(f"    {k:40s} faces {c:4d}  verts {nv[k]:5d}")

    # which pads are near the site
    near_pads = [(pid, c, poly) for pid, c, poly in got if poly.distance(site) <= radius]
    print(f"\n[{icao}] cluster pads within {radius:.0f} m: {[(pid, round(p.area)) for pid,_,p in near_pads]}")

    results = {}
    for vname, fn in VARIANTS.items():
        rows = []
        tot = Counter()
        for pid, c, poly in got:
            g = fn(poly)
            raw = raw_by_id[pid]
            added = g.difference(raw); removed = raw.difference(g)
            r = {"pad": pid, "near": poly.distance(site) <= radius,
                 "area_m2": round(g.area), "raw_m2": round(raw.area),
                 "verts": nverts(g), "verts0": nverts(poly), "holes": nholes(g), "holes0": nholes(poly),
                 "pieces": len(parts(g)), "piece_m2": sorted((round(p.area) for p in parts(g)), reverse=True)[:6],
                 "added_m2": round(added.area), "removed_m2": round(removed.area)}
            if r["near"] or vname == "V0_today":
                by_role, refs = face_census(added)
                r["added_on"] = {k: round(v) for k, v in by_role.most_common()}
                r["added_refs"] = {k: round(v) for k, v in sorted(refs.items(), key=lambda kv: -kv[1])[:8]}
            rows.append(r)
            tot["verts"] += r["verts"]; tot["verts0"] += r["verts0"]; tot["area"] += r["area_m2"]
            tot["added"] += r["added_m2"]; tot["removed"] += r["removed_m2"]; tot["holes"] += r["holes"]
            tot["pieces"] += r["pieces"]
        results[vname] = {"total": dict(tot), "rows": rows}
        nr = [r for r in rows if r["near"]]
        print(f"\n== {vname}: ALL pads {len(rows)}: verts {tot['verts0']} -> {tot['verts']}, area {tot['area']} m2 (+{tot['added']} / -{tot['removed']} vs raw), holes {tot['holes']}, pieces {tot['pieces']}")
        for r in nr:
            print(f"   {r['pad']:14s} verts {r['verts0']:5d} -> {r['verts']:5d}  area {r['raw_m2']:7d} -> {r['area_m2']:7d}  +{r['added_m2']:6d}/-{r['removed_m2']:5d}  holes {r['holes0']}->{r['holes']}  pieces {r['pieces']} {r['piece_m2']}  added_on {r.get('added_on')}")
        # worst cases airport-wide: most area added, most removed
        worst_add = sorted(rows, key=lambda r: -r["added_m2"])[:3]
        print("   worst added:", [(r["pad"], r["added_m2"], r.get("added_on")) for r in worst_add])
        worst_rem = sorted(rows, key=lambda r: -r["removed_m2"])[:3]
        print("   worst removed:", [(r["pad"], r["removed_m2"]) for r in worst_rem])
    if out_json:
        out_json.write_text(json.dumps({"icao": icao, "counts": counts, "variants": results}, indent=1))
        print("wrote", out_json)


if __name__ == "__main__":
    main()
