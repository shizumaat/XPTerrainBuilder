"""emitspec probe 1 — THE PRIZE on an emitted v2 patch (RULINGS 2026-10-08e (B)).

Pure read over an existing ``<ICAO>_auto.patch.osm``.  Reports, per airport:
  (a) ways and nodes today, by role;
  (b) adjacent same-plane faces (flat at one level / one sloped plane, at a
      z tolerance) and what merging them saves, within role and across role;
  (c) nodes the mesh builder's interpolation makes redundant: ring nodes
      collinear in plan (perp. deviation <= xy_tol) whose z is the linear
      interpolation of their neighbours (|dz| <= z_tol), referenced by no
      other way; plus nodes that become INTERIOR to a merged flat shape;
  (d) a site window listing (faces, z range, merge verdict).

Never merges across: a structure_rim / crown_spine / terrain_edge edge, a
gap_interior_ring edge, a tile line, or a pair whose roles are in the
"never" set (runway stays its own shape: o4_single_poly).
"""
from __future__ import annotations
import argparse, json, math, re, sys
from collections import defaultdict
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

M_LAT = 111_320.0
NODE_RE = re.compile(r"<node id='(-?\d+)'[^>]*lat='([-\d.]+)' lon='([-\d.]+)'>\s*<tag k='alt_abs' v='([-\d.]+)' />", re.S)
WAY_RE = re.compile(r"<way id='(-?\d+)'[^>]*>(.*?)</way>", re.S)
ND_RE = re.compile(r"<nd ref='(-?\d+)' />")
TAG_RE = re.compile(r"<tag k='([^']*)' v='([^']*)' />")


def parse(path):
    txt = open(path, encoding="utf-8").read()
    nodes = {int(i): (float(la), float(lo), float(z)) for i, la, lo, z in NODE_RE.findall(txt)}
    ways = []
    for wid, body in WAY_RE.findall(txt):
        nds = [int(x) for x in ND_RE.findall(body)]
        tags = dict(TAG_RE.findall(body))
        closed = len(nds) > 1 and nds[0] == nds[-1]
        ways.append({"id": int(wid), "nds": nds[:-1] if closed else nds, "closed": closed, "tags": tags})
    return nodes, ways


def frame(nodes):
    lat0 = np.mean([v[0] for v in nodes.values()]); lon0 = np.mean([v[1] for v in nodes.values()])
    mlon = M_LAT * math.cos(math.radians(lat0))
    return {i: ((lo - lon0) * mlon, (la - lat0) * M_LAT, z) for i, (la, lo, z) in nodes.items()}


def plane_fit(pts):
    """max |residual| of a least-squares plane; (a,b,c)."""
    P = np.asarray(pts, float)
    if len(P) < 3:
        return 0.0, (0.0, 0.0, float(P[:, 2].mean()))
    A = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]
    sol, *_ = np.linalg.lstsq(A, P[:, 2], rcond=None)
    res = P[:, 2] - A @ sol
    return float(np.abs(res).max()), tuple(float(s) for s in sol)


def edges_of(ring):
    n = len(ring)
    return [(min(ring[i], ring[(i + 1) % n]), max(ring[i], ring[(i + 1) % n])) for i in range(n)]


def analyse(path, z_tol, xy_tol, across_role, site=None, radius=150.0, verbose_site=False, guard_m=3.0):
    nodes, ways = parse(path)
    xyz = frame(nodes)
    faces = [w for w in ways if w["closed"] and "role" in w["tags"]]
    feats = [w for w in ways if "o4_feature" in w["tags"]]
    # edges the merge may never cross
    barrier = set()
    for w in feats:
        if w["tags"]["o4_feature"] in ("structure_rim", "crown_spine", "terrain_edge", "gap_interior_ring"):
            e = edges_of(w["nds"]) if w["closed"] else [(min(a, b), max(a, b)) for a, b in zip(w["nds"], w["nds"][1:])]
            barrier.update(e)
    # (a) today
    by_role = defaultdict(lambda: [0, set()])
    for f in faces:
        r = f["tags"]["role"]; by_role[r][0] += 1; by_role[r][1].update(f["nds"])
    all_named = set(); [all_named.update(w["nds"]) for w in ways]
    # per-face planarity
    info = {}
    for f in faces:
        pts = [xyz[i] for i in f["nds"]]
        zs = [p[2] for p in pts]
        flat = (max(zs) - min(zs)) <= z_tol
        res, pl = plane_fit(pts)
        info[f["id"]] = {"flat": flat, "planar": res <= z_tol, "res": res, "plane": pl,
                         "z": float(np.mean(zs)), "role": f["tags"]["role"], "ref": f["tags"].get("ref", ""),
                         "n": len(f["nds"]), "shapeID": f["tags"].get("shapeID", "")}
    # adjacency by shared ring edge — exterior rings from the ways, HOLE
    # rings from the sidecar ``face_holes`` (the .osm way carries only the
    # exterior; the hole is the inner faces' own rings), joined on the
    # 11-dp identity coordinate exactly as the census joins them
    edge_owner = defaultdict(list)
    for f in faces:
        for e in edges_of(f["nds"]):
            edge_owner[e].append(f["id"])
    hole_edges = 0
    face_hole_ids = defaultdict(list)
    try:
        side = json.load(open(path + ".axes.json"))
        ll_id = {(f"{la:.11f}", f"{lo:.11f}"): i for i, (la, lo, z) in nodes.items()}
        by_shape = {f["tags"].get("shapeID"): f["id"] for f in faces}
        for sid, rings in side.get("face_holes", {}).items():
            host = by_shape.get(sid)
            if host is None:
                continue
            for ring in rings:
                ids = [ll_id.get((f"{la:.11f}", f"{lo:.11f}")) for la, lo in ring]
                ids = [i for i in ids if i is not None]
                if len(ids) >= 3:
                    face_hole_ids[host].append(ids)
                    for e in edges_of(ids):
                        edge_owner[e].append(host); hole_edges += 1
    except FileNotFoundError:
        pass
    # dedupe owners per edge (a hole edge may coincide with an exterior edge of the same host)
    edge_owner = {e: sorted(set(o)) for e, o in edge_owner.items()}
    way_by_id = {f["id"]: f for f in faces}
    node_ways = defaultdict(set)
    for w in ways:
        for i in w["nds"]:
            node_ways[i].add(w["id"])
    never = {"runway"}
    # union-find with refit check
    parent = {f["id"]: f["id"] for f in faces}
    comp_nodes = {f["id"]: set(f["nds"]) for f in faces}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    pairs = sorted((e, o) for e, o in edge_owner.items() if len(o) == 2 and e not in barrier)
    merged_pairs = 0; refused = defaultdict(int)
    for e, (a, b) in pairs:
        ia, ib = info[a], info[b]
        if ia["role"] in never or ib["role"] in never:
            refused["runway"] += 1; continue
        if not across_role and ia["role"] != ib["role"]:
            refused["role"] += 1; continue
        if not (ia["planar"] and ib["planar"]):
            refused["not_planar"] += 1; continue
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        pts = [xyz[i] for i in comp_nodes[ra] | comp_nodes[rb]]
        res, _ = plane_fit(pts)
        if res > z_tol:
            refused["different_plane"] += 1; continue
        parent[rb] = ra; comp_nodes[ra] |= comp_nodes[rb]; merged_pairs += 1
    comps = defaultdict(list)
    for f in faces:
        comps[find(f["id"])].append(f["id"])
    # (b)+(c): nodes after, per component
    ways_after = 0; nodes_after = set(); nodes_after_collinear = set()
    ways_before = len(faces); nodes_before = set(all_named)
    comp_rows = []
    for root, members in comps.items():
        mem = set(members)
        polys = []
        for m in members:
            pts = [(xyz[i][0], xyz[i][1]) for i in way_by_id[m]["nds"]]
            hs = [[(xyz[i][0], xyz[i][1]) for i in h] for h in face_hole_ids.get(m, [])]
            try:
                p = Polygon(pts, hs)
                if not p.is_valid: p = p.buffer(0)
                polys.append(p)
            except Exception:
                pass
        if len(members) == 1:
            ways_after += 1
            ring = way_by_id[members[0]]["nds"]
            keep = ring_keep(ring, xyz, node_ways, mem, xy_tol, z_tol, info[members[0]]["planar"])
            nodes_after.update(ring); nodes_after_collinear.update(keep)
            continue
        u = unary_union(polys)
        rings = []
        geoms = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
        for g in geoms:
            rings.append(g.exterior); rings.extend(g.interiors)
        ways_after += len(geoms)  # one way per outer ring; holes ride as interiors (counted below)
        hole_rings = sum(len(g.interiors) for g in geoms)
        # nodes on the union boundary: map boundary coords back to node ids
        coord_id = {(round(xyz[i][0], 4), round(xyz[i][1], 4)): i for m in members
                    for i in list(way_by_id[m]["nds"]) + [j for h in face_hole_ids.get(m, []) for j in h]}
        kept = set(); kept_col = set()
        for r in rings:
            ids = [coord_id.get((round(x, 4), round(y, 4))) for x, y in list(r.coords)[:-1]]
            ids = [i for i in ids if i is not None]
            kept.update(ids)
            kept_col.update(ring_keep(ids, xyz, node_ways, mem, xy_tol, z_tol, True))
        # a node any OTHER way references must stay even if interior/collinear
        for m in members:
            for i in way_by_id[m]["nds"]:
                if node_ways[i] - mem:
                    kept.add(i); kept_col.add(i)
        nodes_after.update(kept); nodes_after_collinear.update(kept_col)
        before_n = len({i for m in members for i in way_by_id[m]["nds"]})
        comp_rows.append((len(members), before_n, len(kept), len(kept_col), hole_rings,
                          sorted({info[m]["role"] for m in members}), info[members[0]]["z"], root))
    # (c) alone: collinear ring nodes without any merge
    col_only = set()
    for f in faces:
        col_only.update(ring_keep(f["nds"], xyz, node_ways, {f["id"]}, xy_tol, z_tol, info[f["id"]]["planar"]))
    # feature ways keep their nodes
    feat_nodes = set(); [feat_nodes.update(w["nds"]) for w in feats]
    # THE FENCE GUARD: a node within ``guard_m`` of a segment of any way
    # OUTSIDE its component stays.  In the real mesh a free vertex beside a
    # foreign ring at another level shares a triangle with that ring's
    # vertices and is averaged toward it (the R18-1b class); the authored
    # node is what holds the level there.  Measured: without it one dropped
    # node 1 m from an OTHH basin rim read 0.48 m off.
    if guard_m > 0:
        import shapely as _sh
        comp_of = {m: r for r, ms in comps.items() for m in ms}
        seg_way = []; seg_geom = []
        for w in ways:
            nd = w["nds"]; rng_ = range(len(nd)) if w["closed"] else range(len(nd) - 1)
            for k in rng_:
                a_, b_ = nd[k], nd[(k + 1) % len(nd)]
                seg_way.append(w["id"]); seg_geom.append([(xyz[a_][0], xyz[a_][1]), (xyz[b_][0], xyz[b_][1])])
        tree = _sh.STRtree(_sh.linestrings(seg_geom))
        guarded = 0
        for target in (nodes_after_collinear, nodes_after, col_only):
            dropped = [i for i in all_named if i not in target and i not in feat_nodes]
            if not dropped:
                continue
            pts = _sh.points([(xyz[i][0], xyz[i][1]) for i in dropped])
            hp, hs = tree.query(pts, predicate="dwithin", distance=guard_m)
            for k, sidx in zip(hp.tolist(), hs.tolist()):
                i = dropped[k]
                owners = {comp_of.get(wid) for wid in node_ways[i] if wid in comp_of}
                wid = seg_way[sidx]
                if comp_of.get(wid, None) not in owners or wid not in comp_of:
                    if i not in target:
                        target.add(i); guarded += 1
    out = {
        "patch": path, "z_tol": z_tol, "xy_tol": xy_tol, "across_role": across_role,
        "ways_before": ways_before, "feature_ways": len(feats),
        "nodes_before": len(nodes_before),
        "faces_flat": sum(1 for v in info.values() if v["flat"]),
        "faces_planar": sum(1 for v in info.values() if v["planar"]),
        "adjacent_pairs": len(pairs), "merged_pairs": merged_pairs, "refused": dict(refused),
        "components_multi": sum(1 for c in comps.values() if len(c) > 1),
        "ways_after_merge": ways_after,
        "nodes_after_merge": len(nodes_after | feat_nodes),
        "nodes_after_merge_and_collinear": len(nodes_after_collinear | feat_nodes),
        "nodes_after_collinear_only": len(col_only | feat_nodes),
        "guard_m": guard_m, "guarded_back": guarded if guard_m > 0 else 0,
        "by_role": {r: [c, len(s)] for r, (c, s) in sorted(by_role.items())},
        "largest_components": sorted(comp_rows, reverse=True)[:8],
    }
    out["_kept"] = nodes_after_collinear | feat_nodes
    out["_kept_merge_only"] = nodes_after | feat_nodes
    out["_comps"] = {r: m for r, m in comps.items()}
    out["_faces"] = faces
    out["_info"] = info
    if site is not None:
        la, lo = site
        lat0 = np.mean([v[0] for v in nodes.values()]); lon0 = np.mean([v[1] for v in nodes.values()])
        sx, sy = (lo - lon0) * M_LAT * math.cos(math.radians(lat0)), (la - lat0) * M_LAT
        rows = []
        for f in faces:
            pts = [xyz[i] for i in f["nds"]]
            d = min(math.hypot(p[0] - sx, p[1] - sy) for p in pts)
            if d <= radius:
                i = info[f["id"]]
                zs = [p[2] for p in pts]
                rows.append({"way": f["id"], "shapeID": i["shapeID"], "role": i["role"], "ref": i["ref"], "n": i["n"],
                             "zmin": round(min(zs), 2), "zmax": round(max(zs), 2), "planar_res": round(i["res"], 3),
                             "comp": find(f["id"]), "comp_size": len(comps[find(f["id"])])})
        out["site"] = {"faces": len(rows), "ring_vertices": sum(r["n"] for r in rows),
                       "components": len({r["comp"] for r in rows}),
                       "rows": rows if verbose_site else rows[:0]}
        by_comp = defaultdict(list)
        for r in rows: by_comp[r["comp"]].append(r)
        out["site"]["component_summary"] = sorted(
            [(len(v), sorted({r["role"] for r in v}), min(r["zmin"] for r in v), max(r["zmax"] for r in v),
              sum(r["n"] for r in v)) for v in by_comp.values()], reverse=True)
    return out


def ring_keep(ring, xyz, node_ways, members, xy_tol, z_tol, planar):
    """Nodes of a ring that must stay: a node goes only if it is referenced by
    no way outside ``members``, lies within xy_tol of the chord between its
    kept neighbours and its z is within z_tol of the linear value there."""
    n = len(ring)
    if n <= 3:
        return set(ring)
    keep = [True] * n
    changed = True
    while changed:
        changed = False
        idx = [k for k in range(n) if keep[k]]
        if len(idx) <= 3:
            break
        for j, k in enumerate(idx):
            i = ring[k]
            if node_ways[i] - members:
                continue
            a = ring[idx[j - 1]]; b = ring[idx[(j + 1) % len(idx)]]
            ax, ay, az = xyz[a]; bx, by, bz = xyz[b]; px, py, pz = xyz[i]
            dx, dy = bx - ax, by - ay
            L = math.hypot(dx, dy)
            if L <= 0:
                continue
            t = ((px - ax) * dx + (py - ay) * dy) / (L * L)
            if t < 0 or t > 1:
                continue
            off = abs((px - ax) * dy - (py - ay) * dx) / L
            dz = abs(pz - (az + t * (bz - az)))
            if off <= xy_tol and dz <= z_tol:
                keep[k] = False; changed = True
                break  # re-evaluate with the new neighbours (greedy, deterministic)
    return {ring[k] for k in range(n) if keep[k]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("patches", nargs="+")
    ap.add_argument("--z-tol", type=float, nargs="+", default=[0.01, 0.02])
    ap.add_argument("--xy-tol", type=float, default=0.05)
    ap.add_argument("--site", type=float, nargs=2)
    ap.add_argument("--radius", type=float, default=150.0)
    ap.add_argument("--verbose-site", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--guard", type=float, default=3.0)
    a = ap.parse_args()
    for p in a.patches:
        for zt in a.z_tol:
            for across in (False, True):
                o = analyse(p, zt, a.xy_tol, across, a.site, a.radius, a.verbose_site, a.guard)
                for k in [k for k in o if k.startswith("_")]:
                    o.pop(k)
                if a.json:
                    print(json.dumps(o, default=str)); continue
                print(f"\n== {p}  z_tol={zt} xy_tol={a.xy_tol} across_role={across}")
                print(f"  ways {o['ways_before']} (+{o['feature_ways']} feature ways)  nodes {o['nodes_before']}  "
                      f"flat faces {o['faces_flat']}  planar faces {o['faces_planar']}")
                print(f"  adjacent pairs {o['adjacent_pairs']}  merged {o['merged_pairs']}  refused {o['refused']}")
                print(f"  guard {o['guard_m']} m kept back {o['guarded_back']} nodes")
                print(f"  -> ways {o['ways_after_merge']}  nodes after merge {o['nodes_after_merge']}  "
                      f"+collinear {o['nodes_after_merge_and_collinear']}  (collinear only, no merge: {o['nodes_after_collinear_only']})")
                if not across:
                    print("  by role (ways, nodes):", o["by_role"])
                print("  largest comps (faces, nodes_before, after, after+col, holes, roles, z):")
                for r in o["largest_components"]:
                    print("    ", r[:7])
                if "site" in o:
                    s = o["site"]
                    print(f"  SITE faces {s['faces']} ring vertices {s['ring_vertices']} -> components {s['components']}")
                    for c in s["component_summary"]:
                        print("     comp", c)
                    for r in s["rows"]:
                        print("     ", r)


if __name__ == "__main__":
    main()
