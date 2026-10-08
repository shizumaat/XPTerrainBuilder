"""jetspec scratch probe — THE WITNESS and THE SHAPE for the jetway-terminal pad
(owner RULINGS 2026-10-08a / 08b), pure geometry on a capture + one build's graded.json.

(1) WITNESS: per cluster unit (rule-2 outline), the rider candidates standing within their
    reach of the outline (= what `rider_hosts` would host at cluster time), split by
    jetway-NAMED (ground truth for the probe only — the engine never reads names) and by the
    general witnesses: plan half-extent, reach at the cap, kind.
(2) SHAPE: for every unit that any witness qualifies, the candidate pads —
    hull, pockets-with-riders (R2), pockets-facing-airside (R3), closing at W —
    with vertices, area added and WHAT the added area is on the build's graded faces
    (role m²), stands inside, taxi-edge metres inside, rider anchors inside, other units'
    outlines inside, DEM relief and solved-apron relief inside.
usage (from Ortho4XP/): venv/bin/python <this> ICAO CAP.pkl GRADED.json [--json OUT] [--top N]
"""
from __future__ import annotations
import argparse, dataclasses as dc, json, math, os, pickle, sys, time
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pads56"))
import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from auto_patch_v2.airport import riders as R
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline
from auto_patch_v2.planar.cluster import clusters as derive_clusters
from classify_probe import outlines  # pads56 probe, reused (rule 2 / 2b cluster outlines)

JET = ("jetway", "jet_way", "jetbridge", "bridge", "gate", "finger", "passerelle", "aerobridge")
STRUCT = ("tunnel_ramp", "wall_corridor_ramp", "garage_ramp", "door_ramp", "retaining_wall",
          "tunnel_trench", "tunnel_wall")
AIRSIDE = ("apron", "taxiway", "runway", "junction", "graded_strip", "secondary_parallel")


def nv(g):
    if g.geom_type != "Polygon":
        return sum(nv(p) for p in g.geoms)
    return len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)


def parts(g):
    if g.is_empty:
        return []
    return [g] if g.geom_type == "Polygon" else [p for p in g.geoms if p.geom_type == "Polygon"]


def read_graded(path, to_xy):
    g = json.load(open(path))
    V = {v[0]: (to_xy(v[2], v[1]), v[3]) for v in g["vertices"]}
    faces = []
    for f in g["faces"]:
        ring = [V[i][0] for i in f["ring"] if i in V]
        if len(ring) < 3:
            continue
        p = Polygon(ring, [[V[i][0] for i in h if i in V] for h in f.get("holes", ()) if len(h) >= 3])
        if not p.is_valid:
            p = p.buffer(0)
        if p.is_empty:
            continue
        zs = [V[i][1] for i in f["ring"] if i in V]
        faces.append((f.get("role", "?"), str(f.get("ref", "?")), p, zs, [V[i][0] for i in f["ring"] if i in V]))
    return faces


def sdist(poly, pt):
    d = poly.exterior.distance(pt)
    for h in poly.interiors:
        d = min(d, h.distance(pt))
    return -d if poly.contains(pt) else d


def pockets(u):
    """The hull's concavities of a polygon: maximal pockets, each with its mouth (the hull
    edge(s) that close it), mouth width and depth."""
    hull = u.convex_hull
    out = []
    for p in parts(hull.difference(u)):
        mouth = p.boundary.intersection(hull.exterior)
        w = mouth.length
        out.append(dict(poly=p, mouth=mouth, mouth_w=w, area=p.area, depth=(p.area / w if w > 0 else 0.0)))
    return hull, out


def dem_relief(dem, poly, step=15.0):
    minx, miny, maxx, maxy = poly.bounds
    zs = []
    prep = poly
    for x in np.arange(minx, maxx, step):
        for y in np.arange(miny, maxy, step):
            if prep.contains(Point(x, y)):
                try:
                    z = float(dem.z(x, y))
                except Exception:
                    continue
                if math.isfinite(z):
                    zs.append(z)
    if not zs:
        return None
    a = np.array(zs)
    return dict(n=len(a), min=round(float(a.min()), 2), max=round(float(a.max()), 2),
                p5=round(float(np.percentile(a, 5)), 2), p95=round(float(np.percentile(a, 95)), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("icao"); ap.add_argument("pkl", type=Path); ap.add_argument("graded", type=Path)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--min-jet", type=int, default=1, help="print units with >= this many riders of any kind")
    ap.add_argument("--close", type=float, nargs="*", default=[30.0, 60.0])
    a = ap.parse_args()
    icao = a.icao
    t0 = time.perf_counter()
    cap = pickle.load(a.pkl.open("rb")); airport = cap["airport"]
    law = Law.for_airport(icao)
    airport = dc.replace(airport, clusters=derive_clusters(airport, law))
    to_xy, to_ll = airport.frame.transformers()
    pl = law.tables.structures.placement
    cap_reach = float(pl.rider_reach_max_m)
    t, c0, _ = outlines(airport, law, None)
    s, c1, st = outlines(airport, law, pad_outline(law))
    print(f"[{icao}] loaded {time.perf_counter()-t0:.0f} s; rule-2 pads {c0['pads']}, rule-2b {c1['pads']}; "
          f"dsf_objects {len(airport.dsf_objects)}; startups {len(airport.startups)}; taxi edges {len(airport.taxi_edges)}")
    faces = read_graded(a.graded, to_xy)
    print(f"[{icao}] graded faces {len(faces)} from {a.graded}")
    ftree = STRtree([f[2] for f in faces])
    # ── (1) the riders ─────────────────────────────────────────────────────────
    cand = R.rider_candidates(airport, law)
    objs = {o.id: o for o in airport.dsf_objects}
    ids = sorted(t)
    polys = [t[i] for i in ids]
    tree = STRtree(polys)
    per_unit: dict[str, list] = defaultdict(list)
    for oid, (reach, kind) in cand.items():
        o = objs[oid]
        pt = Point(*o.xy)
        best = None
        for i in tree.query(pt.buffer(reach)):
            poly = polys[int(i)]
            d = 0.0 if (kind == "agp" and poly.covers(pt)) else float(poly.exterior.distance(pt))
            if d > reach:
                continue
            k = (round(d, 6), -poly.area, ids[int(i)])
            if best is None or k < best[0]:
                best = (k, ids[int(i)], d)
        if best is None:
            continue
        rp = getattr(o, "resolved_path", None)
        ext = R.obj_half_extent_m(rp) if (rp and os.path.isfile(rp) and kind != "agp") else None
        name = os.path.basename(o.path)
        per_unit[best[1]].append(dict(id=oid, res=name, kind=kind, reach=reach, d=round(best[2], 2),
                                      ext=(None if ext is None else round(float(ext), 2)),
                                      jet=any(j in name.lower() for j in JET), xy=(float(o.xy[0]), float(o.xy[1]))))
    print(f"[{icao}] rider candidates {len(cand)}; hosted at cluster time (within reach of a rule-2 outline): "
          f"{sum(map(len, per_unit.values()))} on {len(per_unit)} units")
    # the general witnesses, measured against the name
    allr = [r for v in per_unit.values() for r in v]
    jet = [r for r in allr if r["jet"]]; non = [r for r in allr if not r["jet"]]
    def hist(rows, key):
        c = Counter()
        for r in rows:
            v = r[key]
            c["none" if v is None else ("agp" if r["kind"] == "agp" else (f"<{int(v)//4*4+4}" if v < 12 else ">=12"))] += 1
        return dict(sorted(c.items()))
    print(f"[{icao}] hosted riders jet-named {len(jet)} ext-hist {hist(jet,'ext')}; non-jet {len(non)} ext-hist {hist(non,'ext')}")
    print(f"[{icao}]   reach==cap: jet {sum(1 for r in jet if r['reach']>=cap_reach)} / non-jet {sum(1 for r in non if r['reach']>=cap_reach)}; "
          f"non-jet at the cap, top resources: {Counter(r['res'] for r in non if r['reach']>=cap_reach).most_common(8)}")
    print(f"[{icao}]   jet-named UNDER the cap: {Counter((r['res'], r['ext']) for r in jet if r['reach']<cap_reach).most_common(6)}")
    # per unit
    units = []
    for pid in ids:
        rows = per_unit.get(pid, [])
        big = [r for r in rows if r["reach"] >= cap_reach]
        j = [r for r in rows if r["jet"]]
        if len(rows) >= a.min_jet:
            units.append((pid, rows, big, j))
    print(f"[{icao}] units with riders: {len(units)} — id, area m2, rule-2 v, riders, big(reach=cap), jet-named, "
          f"big per 100 m of outline, members")
    for pid, rows, big, j in sorted(units, key=lambda x: -len(x[2])):
        u = t[pid]
        print(f"   {pid:18s} {u.area:10,.0f} {nv(u):5d} v  riders {len(rows):3d} big {len(big):3d} jet {len(j):3d} "
              f"big/100m {100*len(big)/u.exterior.length:5.2f}  "
              f"top {Counter(r['res'] for r in rows).most_common(3)}")
    # ── (2) the shapes ───────────────────────────────────────────────────────
    out_units = {}
    apron_faces = [f for f in faces if f[0] in AIRSIDE]
    atree = STRtree([f[2] for f in apron_faces])
    taxi_lines = []
    for e in airport.taxi_edges:
        if e.is_runway:
            continue
        na, nb = airport.taxi_nodes.get(e.a), airport.taxi_nodes.get(e.b)
        if na and nb:
            taxi_lines.append(LineString([na.xy, nb.xy]))
    ttree = STRtree(taxi_lines) if taxi_lines else None
    stands = [Point(*s.xy) for s in airport.startups]
    stree = STRtree(stands) if stands else None
    for pid, rows, big, j in sorted(units, key=lambda x: -len(x[2])):
        if len(big) < 2:
            continue
        u = t[pid]
        hull, pk = pockets(u)
        anchors = [Point(*r["xy"]) for r in rows]
        bigpts = [Point(*r["xy"]) for r in big]
        # a pocket "holds" a rider when the rider's anchor stands in it or within its reach of it
        for p in pk:
            buf = p["poly"].buffer(0.5)
            p["riders"] = sum(1 for q in anchors if buf.covers(q))
            p["big"] = sum(1 for q in bigpts if buf.covers(q))
            # mouth faces airside: airside face area within 10 m outward of the mouth
            m = p["mouth"]
            mb = m.buffer(10.0).difference(p["poly"]).difference(u) if m.length else Polygon()
            p["mouth_airside_m2"] = round(sum(apron_faces[int(i)][2].intersection(mb).area for i in atree.query(mb)), 0) if not mb.is_empty else 0.0
            p["mouth_frac_airside"] = round(p["mouth_airside_m2"] / max(mb.area, 1e-9), 2) if not mb.is_empty else 0.0
        cands = {"hull": hull}
        cands["R2_pockets_with_riders"] = unary_union([u] + [p["poly"] for p in pk if p["riders"] > 0]).buffer(0)
        cands["R2b_pockets_with_big"] = unary_union([u] + [p["poly"] for p in pk if p["big"] > 0]).buffer(0)
        cands["R3_pockets_mouth_airside"] = unary_union([u] + [p["poly"] for p in pk if p["mouth_frac_airside"] >= 0.5]).buffer(0)
        for W in a.close:
            cands[f"close_{int(W)}"] = u.buffer(W).buffer(-W).union(u).buffer(0)
        cands["rule2b_today"] = s.get(pid, u)
        rec = {"area": round(u.area), "v_rule2": nv(u), "v_hull": nv(hull), "riders": len(rows), "big": len(big), "jet": len(j),
               "pockets": [], "cands": {}}
        print(f"\n== {pid} area {u.area:,.0f} m2, rule-2 {nv(u)} v, hull {nv(hull)} v; pockets {len(pk)} "
              f"(riders {len(rows)}, big {len(big)}, jet-named {len(j)}) centroid {to_ll(u.centroid.x, u.centroid.y)}")
        for p in sorted(pk, key=lambda p: -p["area"])[:14]:
            c = p["poly"].centroid
            rec["pockets"].append({k: (round(v, 1) if isinstance(v, float) else v) for k, v in p.items() if k not in ("poly", "mouth")})
            print(f"   pocket {p['area']:9,.0f} m2 mouth {p['mouth_w']:6.1f} m depth {p['depth']:6.1f} m riders {p['riders']:3d} big {p['big']:3d} "
                  f"mouth→airside {p['mouth_frac_airside']:.2f} at {to_ll(c.x, c.y)}")
        for name, g in cands.items():
            g = g if g.geom_type == "Polygon" else max(parts(g), key=lambda p: p.area)
            gs = g.simplify(1.0, preserve_topology=True)
            added = g.difference(u)
            roles = Counter()
            for i in ftree.query(added):
                f = faces[int(i)]
                ia = f[2].intersection(added).area
                if ia > 0.5:
                    roles[f[0]] += ia
            n_st = sum(1 for i in (stree.query(added) if stree else []) if added.covers(stands[int(i)]))
            taxi_m = sum(taxi_lines[int(i)].intersection(added).length for i in (ttree.query(added) if ttree else []))
            n_anch = sum(1 for q in anchors if added.covers(q))
            others = sum(t[o].intersection(added).area for o in ids if o != pid and t[o].intersects(added))
            dem = dem_relief(airport.dem, g) if name in ("hull", "R2_pockets_with_riders", "rule2b_today") else None
            # the solved apron inside the ADDED area: z range of airside-face vertices inside it
            zs = []
            for i in atree.query(added):
                f = apron_faces[int(i)]
                for xy, z in zip(f[4], f[3]):
                    if added.covers(Point(xy)):
                        zs.append(z)
            apz = (round(min(zs), 2), round(max(zs), 2), len(zs)) if zs else None
            row = dict(v=nv(gs), area=round(g.area), added=round(added.area), roles={k: round(v) for k, v in roles.most_common(10)},
                       stands=n_st, taxi_m=round(taxi_m), anchors_in=n_anch, other_units_m2=round(others), dem=dem, apron_z=apz,
                       wkt=g.simplify(2.0).wkt if name in ("R2_pockets_with_riders", "hull") else None)
            rec["cands"][name] = row
            print(f"   {name:26s} v {row['v']:5d} area {row['area']:9,} +{row['added']:8,} m2 | stands {n_st:3d} taxi {taxi_m:6.0f} m anchors {n_anch:3d} "
                  f"other-units {others:6.0f} | {dict(roles.most_common(6))} | dem {dem} | apron z in added {apz}")
        out_units[pid] = rec
    if a.json:
        json.dump({"icao": icao, "units": out_units}, a.json.open("w"), indent=1, default=str)
    print(f"[{icao}] done {time.perf_counter()-t0:.0f} s")


if __name__ == "__main__":
    main()
