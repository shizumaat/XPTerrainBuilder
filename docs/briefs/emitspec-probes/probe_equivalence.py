"""emitspec probe 2 — THE EQUIVALENCE INSTRUMENT (RULINGS 2026-10-08e (B)).

"Same terrain" made testable with the mesh builder's OWN interpolation rule
(``O4_Mesh_Utils.interpolate_free_interior_altitudes``: graph-harmonic
extension of the patch-valued vertices over the INTERP_ALT sub-mesh; a
mesher-inserted vertex ON a ring segment takes the segment's linear value,
``patch_segment_split_values``).

For a window of the patch: ONE triangulation over (every node of the fine
patch A) ∪ (a Steiner lattice at ``--spacing`` m inside the coverage).  Arm
A: every ring node is Dirichlet.  Arm B: only the nodes the simplified patch
keeps are Dirichlet; the dropped nodes become free and are interpolated like
any mesher-inserted vertex.  The instrument reads |zA − zB| at EVERY vertex
of the window (dropped nodes and lattice points alike) and reports the max,
the count over the 0.01 m materiality floor, and where the worst is.

This is a PROXY for Triangle4XP (unconstrained scipy Delaunay, no quality
refinement): it tests the interpolation law, not the exact triangle set.
The closing build reads the real mesh.
"""
from __future__ import annotations
import argparse, math, sys, os
import numpy as np
from scipy.spatial import Delaunay
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from shapely import prepared

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SRC = "/Users/noah/XPTerrainBuilder/.claude/worktrees/emitspec/Ortho4XP/src"
sys.path.insert(0, SRC)
import probe_simplify as PS


def window(o, xyz, centre_xy, radius):
    faces = [f for f in o["_faces"]
             if min(math.hypot(xyz[i][0] - centre_xy[0], xyz[i][1] - centre_xy[1]) for i in f["nds"]) <= radius]
    return faces


def run(path, z_tol, xy_tol, across, site, radius, spacing, comp_rank=None):
    o = PS.analyse(path, z_tol, xy_tol, across, site, radius)
    nodes, ways = PS.parse(path)
    xyz = PS.frame(nodes)
    lat0 = np.mean([v[0] for v in nodes.values()]); lon0 = np.mean([v[1] for v in nodes.values()])
    if comp_rank is not None:
        comps = sorted(o["_comps"].values(), key=len, reverse=True)
        faces = [f for f in o["_faces"] if f["id"] in set(comps[comp_rank])]
        label = f"component#{comp_rank} ({len(faces)} faces)"
    else:
        cx = (site[1] - lon0) * PS.M_LAT * math.cos(math.radians(lat0)); cy = (site[0] - lat0) * PS.M_LAT
        faces = window(o, xyz, (cx, cy), radius)
        label = f"site r={radius} ({len(faces)} faces)"
    kept = o["_kept"]
    face_ids = {i for f in faces for i in f["nds"]}
    # FEATURE ways (structure rims, crown spines, hole rings) are constrained
    # rings/lines with Dirichlet values in the real mesh too: every feature
    # way with a node inside the window's face set joins the window, as the
    # fine arm's data and as constraint segments
    fset = {f["id"] for f in faces}
    fx = np.array([[xyz[i][0], xyz[i][1]] for i in face_ids]); lo_, hi_ = fx.min(0) - 5, fx.max(0) + 5
    feat_ids = set()
    for w in ways:
        if w["id"] in fset or "role" in w["tags"]:
            continue
        if any(lo_[0] <= xyz[i][0] <= hi_[0] and lo_[1] <= xyz[i][1] <= hi_[1] for i in w["nds"]):
            feat_ids.update(w["nds"]); fset.add(w["id"])
    ids = sorted(face_ids | feat_ids)
    # neighbours' nodes that bound the window faces are already in ids (shared rings)
    P = np.array([[xyz[i][0], xyz[i][1]] for i in ids]); Z = np.array([xyz[i][2] for i in ids])
    polys = []
    for f in faces:
        try:
            p = Polygon([(xyz[i][0], xyz[i][1]) for i in f["nds"]])
            polys.append(p if p.is_valid else p.buffer(0))
        except Exception:
            pass
    cov = unary_union(polys); pc = prepared.prep(cov)
    minx, miny, maxx, maxy = cov.bounds
    gx = np.arange(minx + spacing / 2, maxx, spacing); gy = np.arange(miny + spacing / 2, maxy, spacing)
    lattice = [(x, y) for x in gx for y in gy if pc.contains(Point(x, y))]
    # jitter the lattice slightly so no lattice point is collinear with ring chords (Delaunay degeneracy)
    rng = np.random.default_rng(0)
    L = np.array(lattice) + rng.uniform(-0.05, 0.05, (len(lattice), 2)) if lattice else np.zeros((0, 2))
    allP = np.vstack([P, L]); n_ring = len(P)
    tri = Delaunay(allP)
    cent = allP[tri.simplices].mean(axis=1)
    inside = np.array([pc.contains(Point(x, y)) for x, y in cent])
    tris = [tuple(int(v) for v in s) for s in tri.simplices[inside]]
    # THE CONSTRAINT PROXY: Triangle4XP never triangulates across a
    # constrained segment, so a graph edge that properly CROSSES a ring or
    # feature edge of the fine patch cannot exist in the real mesh.  Drop
    # every triangle carrying one (its remaining edges stay in the graph
    # through its neighbours) — the harmonic solve then never averages a
    # freed vertex across a structure rim or a step.
    import shapely as _sh
    pos = {i: k for k, i in enumerate(ids)}
    T0 = np.array(tris)

    def tris_for(keep_ids):
        """Triangles whose edges cross no constrained segment of THIS arm —
        the arm's segments are the chords between consecutive KEPT nodes of
        every way (a dropped node's two chords become one)."""
        segs = set()
        for w in ways:
            nd = [i for i in w["nds"] if i in pos and i in keep_ids]
            if len(nd) < 2:
                continue
            rng_ = range(len(nd)) if w["closed"] else range(len(nd) - 1)
            for k in rng_:
                a_, b_ = pos[nd[k]], pos[nd[(k + 1) % len(nd)]]
                if a_ != b_:
                    segs.add((min(a_, b_), max(a_, b_)))
        if not segs:
            return [tuple(t) for t in T0.tolist()]
        stree = _sh.STRtree(_sh.linestrings([[allP[a_], allP[b_]] for a_, b_ in segs]))
        E = np.vstack([T0[:, [0, 1]], T0[:, [1, 2]], T0[:, [2, 0]]])
        hit_e, _ = stree.query(_sh.linestrings(allP[E]), predicate="crosses")
        bad = np.zeros(len(E), bool); bad[np.unique(hit_e)] = True
        n = len(T0)
        bad_tri = bad[:n] | bad[n:2 * n] | bad[2 * n:]
        return [tuple(t) for t in T0[~bad_tri].tolist()]
    import O4_Mesh_Utils as MU
    def arm(dirichlet):
        tris = tris_for({ids[k] for k in dirichlet})
        verts = np.zeros(6 * len(allP))
        verts[0::6] = allP[:, 0]; verts[1::6] = allP[:, 1]
        verts[5::6] = 0.0
        verts[5::6][:n_ring] = Z          # ring values; free ones get overwritten
        rep = {}
        MU.interpolate_free_interior_altitudes(verts, tris, set(dirichlet), report=rep)
        return verts[5::6].copy(), rep
    zA, rA = arm(range(n_ring))
    # the window is a CUT through the patch: a node any face outside the
    # window references is held in both arms (it is the window's boundary
    # datum, not a node the simplification decides)
    outside = {i for w in ways if w["id"] not in fset for i in w["nds"]} | feat_ids
    keptB = [k for k, i in enumerate(ids) if i in kept or i in outside]
    zB, rB = arm(keptB)
    # SCORED SET: every vertex the proxy solved in BOTH arms, plus the
    # vertices Dirichlet in both.  A vertex stranded in either arm (the
    # proxy's whole-triangle removal leaves a sliver with no datum; the
    # real mesh has a constrained triangle there) is counted, not scored.
    solvedA = set(np.asarray(rA.get("changed_indices", [])).tolist())
    solvedB = set(np.asarray(rB.get("changed_indices", [])).tolist())
    both_d = set(range(n_ring)) & set(keptB)
    touched = np.unique(T0)
    scored = np.array(sorted((solvedA & solvedB) | both_d), int)
    stranded = int(len(set(touched.tolist()) - set(scored.tolist())))
    d = np.abs(zA - zB)[scored]
    worst = int(scored[int(np.argmax(d))]) if scored.size else -1
    dropped = n_ring - len(keptB)
    print("  isolated A/B:", rA.get("isolated"), rB.get("isolated"), "components", rB.get("isolated_components"))
    wx, wy = allP[worst] if worst >= 0 else (0, 0)
    wlat = lat0 + wy / PS.M_LAT; wlon = lon0 + wx / (PS.M_LAT * math.cos(math.radians(lat0)))
    return {"label": label, "ring_nodes": n_ring, "dropped": dropped, "lattice": len(L), "triangles": len(tris),
            "freeA": rA.get("free"), "freeB": rB.get("free"),
            "max_dz": float(d.max()) if d.size else 0.0, "n_over_0.01": int((d > 0.01).sum()),
            "n_over_0.001": int((d > 0.001).sum()), "stranded": stranded, "scored": int(scored.size),
            "worst_at": (round(float(wlat), 7), round(float(wlon), 7))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("--site", type=float, nargs=2)
    ap.add_argument("--radius", type=float, default=150.0)
    ap.add_argument("--z-tol", type=float, default=0.01)
    ap.add_argument("--xy-tol", type=float, default=0.01)
    ap.add_argument("--across", action="store_true")
    ap.add_argument("--spacing", type=float, default=6.0)
    ap.add_argument("--components", type=int, default=0, help="also run the N largest merged components")
    a = ap.parse_args()
    if a.site:
        print(run(a.patch, a.z_tol, a.xy_tol, a.across, a.site, a.radius, a.spacing))
    for k in range(a.components):
        print(run(a.patch, a.z_tol, a.xy_tol, a.across, a.site or (0, 0), a.radius, a.spacing, comp_rank=k))


if __name__ == "__main__":
    main()
