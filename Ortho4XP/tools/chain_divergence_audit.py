"""Chain-divergence audit: measure how far a patch OSM is from a
CONFORMING PLANAR PARTITION — the property that any boundary shared by
two ways is the IDENTICAL vertex chain in both.

Divergence classes reported (each one is Ruppert-refinement food for
Triangle4XP — the CYXY weld bake exploded 26,727 -> 1,552,854
airport-region triangles on exactly these):

1. T-VERTEX: a node of way A lies ON (or near) the INTERIOR of a way-B
   edge without being a node of way B.  Binned by perpendicular offset:
     - exact  (< 0.1 mm): colinear overlap — Triangle4XP's colinear
       re-dicing usually survives these, but they still mint duplicate
       sub-segment constraints;
     - sub-mm / mm-cm / cm+ : NEAR-parallel non-colinear constrained
       pairs — the encroachment ping-pong class (the killers).
2. NEAR-PARALLEL PAIR: two edges from different ways, angle < 0.5 deg,
   with overlapping spans separated by 0 < d <= 15 cm (the sliver lens
   itself, independent of whether the ways share a node).
3. COINCIDENT NODES: distinct node ids at the same coordinates
   (deliberate wall node-splits are lawful; a high count on non-wall
   role pairs is a dedup failure).
4. INTERIOR EDGE CROSSING: two edges from DIFFERENT ways whose interiors
   properly cross — a single intersection point that lies strictly
   inside both edges (more than the endpoint tolerance away from every
   endpoint), NOT an endpoint touch and NOT a shared-vertex join.  Every
   such crossing forces Triangle4XP to insert a Steiner point at the
   intersection and re-dice both constrained edges, so it is the same
   refinement food as the T-vertex and near-parallel classes but arising
   from transversal geometry rather than from parallel slivers.  Not
   every crossing is a defect: at CYXY (2026-07-10 attribution) all 18
   are the crown-ridge crossing-continuity mechanism BY DESIGN — the
   crown_spine breakline crossing runway~runway_crossing internal seam
   edges (16) plus two intersecting runway ridges crossing without a
   shared node.  Attribute before treating a count as a violation.

5. TWIN-RING PAIR (round 16): two emitted rings SPELLING THE SAME
   BOUNDARY with differing vertex sets — a pad's exterior ring and its
   ``shape_interior_ring`` partner that differ by the vertices one of
   them lost to the sliver-corner repair.  The differing vertices sit ON
   the other ring's chord, so the pair is a ZERO-WIDTH CONSTRAINED LENS:
   Triangle4XP answers it with Steiner points (the +25+051 crash class,
   R15-2 ledger).
6. SUB-MICRON CLUSTER (round 16): two distinct node ids within
   ``--cluster-tol-deg`` (default 1e-9 deg, ~0.1 mm) of each other but
   NOT at identical coordinates — class 3's near-miss twin, and the
   population the r15 mesh work tracked.
7. NEEDLE TIP (round 16): a ring corner whose interior tip angle is at
   or below ``--needle-deg`` (default 25 deg), reported with its HEIGHT
   (perpendicular offset of the tip from the chord joining its
   neighbours).  Tips above the emitter's 0.09 m near-collinear floor
   are the ones the sliver repair spares.
8. UNOWNED WALL STRIP (round 16): a retaining-wall node standing
   ``wall_above_m`` or more above tunnel pavement within
   ``wall_reach_m`` of it, on a wall that reaches that pavement
   NOWHERE — no shape owns the strip between the two boundaries, so
   the mesh drapes it at DEM/Z0 under the crest.  Ownership is a
   property of the WALL, not of one node: a wall welded to the
   pavement (shared node ids, or vertices on its boundary) owns its
   whole face, crest included.

Usage:
    venv/bin/python tools/chain_divergence_audit.py PATCH.osm [PATCH2.osm ...]
        [--tol 0.15] [--top 12] [--cluster-tol-deg 1e-9]
        [--needle-deg 25] [--chord-tol 0.09]

Runs in seconds; prints per-class tables by way-role pair plus the worst
individual sites with lat/lon for probing.  Companion to
tools/wedge_audit.py (which only sees pairs sharing a node).
"""
import argparse
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

# Repo-RELATIVE and APPENDED (round-9 fix): the previous hardcoded
# main-checkout path at sys.path[0] hijacked ``auto_patch`` imports in
# any process that also runs worktree code (the known worktree
# isolation trap — importing this tool made test sessions resolve
# auto_patch from the MAIN repo).
import os as _os
sys.path.append(_os.path.join(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))), "src"))
from shapely import STRtree
from shapely.geometry import LineString, Point


def _load(path):
    """``(nodes, xy, ways, alts)``.

    ``ways`` rows are ``(way id, class, [node id...], ref tag)`` — the
    ``ref`` tag names the EMITTER (``tunnel_wall``, ``tunnel_ramp``, …)
    where ``o4_feature`` names the role, and the round-16 wall/ramp
    classes need both.  ``alts`` is ``{node id: alt_abs}`` for the nodes
    that carry one (an unvalued node — a hole-ring vertex — has none).
    """
    tree = ET.parse(path)
    root = tree.getroot()
    first_lat = None
    nodes = {}
    alts = {}
    for n in root.findall("node"):
        la, lo = float(n.get("lat")), float(n.get("lon"))
        if first_lat is None:
            first_lat = la
        nid = n.get("id")
        nodes[nid] = (la, lo)
        for t in n.findall("tag"):
            if t.get("k") == "alt_abs":
                try:
                    alts[nid] = float(t.get("v"))
                except (TypeError, ValueError):
                    pass
    mlat = 111320.0
    mlon = 111320.0 * math.cos(math.radians(first_lat or 0.0))
    xy = {nid: (lo * mlon, la * mlat) for nid, (la, lo) in nodes.items()}
    ways = []
    for w in root.findall("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        cls = tags.get("o4_feature") or tags.get("role") or "?"
        refs = [nd.get("ref") for nd in w.findall("nd")]
        ways.append((w.get("id"), cls, refs, tags.get("ref") or ""))
    return nodes, xy, ways, alts


#: Roles/refs the round-16 wall class reads (class 8).  The ramp side is
#: the tunnel PAVEMENT a wall stands beside; the wall side is every
#: emitted retaining wall.  Role literals live in ``auto_patch.layout``
#: and are matched here as strings for the same reason the census does.
_RAMP_ROLES = frozenset({"tunnel_ramp"})
_RAMP_REFS = frozenset({"tunnel_ramp", "tunnel_corridor",
                        "tunnel_low_connector", "tunnel_mouth"})
_WALL_ROLES = frozenset({"retaining_wall"})


def geometry_consistency(path, cluster_tol_deg=1e-9, needle_deg=25.0,
                         chord_tol_m=0.09, nodes=None, xy=None, ways=None,
                         alts=None, wall_reach_m=2.0, wall_above_m=1.0,
                         owned_tol_m=0.05):
    """The round-16 geometry-consistency classes (5, 6, 7, 8) as a dict.

    Separate from :func:`analyze` so the acceptance runs, the twins and
    the CLI all read ONE implementation — the census-wrapper precedent
    (a second, slightly-different counter) is what this avoids.  Pass the
    already-parsed ``nodes``/``xy``/``ways``/``alts`` to share one parse.
    """
    if nodes is None or xy is None or ways is None or alts is None:
        nodes, xy, ways, alts = _load(path)

    # ── 5. twin rings ────────────────────────────────────────────────
    rings = []                            # (way index, [nid...] open)
    for wi, (_wid, _cls, refs, _ref) in enumerate(ways):
        if len(refs) >= 4 and refs[0] == refs[-1]:
            rings.append((wi, refs[:-1]))
    ring_of_node = defaultdict(list)
    for ri, (_wi, open_refs) in enumerate(rings):
        for nid in set(open_refs):
            ring_of_node[nid].append(ri)
    shared = Counter()
    for _nid, owners in ring_of_node.items():
        for ia in range(len(owners)):
            for ib in range(ia + 1, len(owners)):
                shared[(owners[ia], owners[ib])] += 1
    twin_pairs = []
    for (ia, ib), n_shared in shared.items():
        if n_shared < 3:
            continue
        wa, ra = rings[ia]
        wb, rb = rings[ib]
        sa, sb = set(ra), set(rb)
        diff = (sa ^ sb)
        if not diff:
            continue                      # same vertex set: one spelling
        geom_a = LineString([xy[n] for n in ra] + [xy[ra[0]]])
        geom_b = LineString([xy[n] for n in rb] + [xy[rb[0]]])
        worst = 0.0
        on_chord = 0
        for nid in diff:
            other = geom_b if nid in sa else geom_a
            d = other.distance(Point(xy[nid]))
            worst = max(worst, d)
            if d <= 1e-6:
                on_chord += 1
        if worst > chord_tol_m:
            continue                      # different boundaries
        la, lo = nodes[next(iter(diff))]
        twin_pairs.append({
            "way_a": ways[wa][0], "way_b": ways[wb][0],
            "role_a": ways[wa][1], "role_b": ways[wb][1],
            "shared": n_shared, "missing": len(diff),
            "on_chord": on_chord, "worst_offset_m": worst,
            "lat": la, "lon": lo,
        })

    # ── 6. sub-micron clusters ───────────────────────────────────────
    cell = max(cluster_tol_deg, 1e-12)
    buckets = defaultdict(list)
    for nid, (la, lo) in nodes.items():
        buckets[(int(la / cell), int(lo / cell))].append(nid)
    clusters = 0
    cluster_sites = []
    seen_pair = set()
    for (ci, cj), _ids in buckets.items():
        near = []
        for oi in (-1, 0, 1):
            for oj in (-1, 0, 1):
                near.extend(buckets.get((ci + oi, cj + oj), ()))
        for ia in range(len(near)):
            for ib in range(ia + 1, len(near)):
                na, nb = near[ia], near[ib]
                key = (na, nb) if na < nb else (nb, na)
                if key in seen_pair:
                    continue
                la1, lo1 = nodes[na]
                la2, lo2 = nodes[nb]
                if (abs(la1 - la2) > cluster_tol_deg
                        or abs(lo1 - lo2) > cluster_tol_deg):
                    continue
                seen_pair.add(key)
                clusters += 1
                cluster_sites.append((la1, lo1, na, nb,
                                      la1 == la2 and lo1 == lo2))

    # ── 7. needle tips ───────────────────────────────────────────────
    cos_limit = math.cos(math.radians(needle_deg))
    needles = []
    for wi, open_refs in rings:
        m = len(open_refs)
        if m < 3:
            continue
        for k in range(m):
            a = xy[open_refs[(k - 1) % m]]
            b = xy[open_refs[k]]
            c = xy[open_refs[(k + 1) % m]]
            v1 = (a[0] - b[0], a[1] - b[1])
            v2 = (c[0] - b[0], c[1] - b[1])
            n1 = math.hypot(*v1)
            n2 = math.hypot(*v2)
            if n1 < 1e-9 or n2 < 1e-9:
                continue
            cosv = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
            if cosv < cos_limit:
                continue                  # tip angle wider than the cap
            dx, dy = c[0] - a[0], c[1] - a[1]
            chord = math.hypot(dx, dy)
            if chord < 1e-9:
                height = min(n1, n2)
            else:
                height = abs((b[0] - a[0]) * dy
                             - (b[1] - a[1]) * dx) / chord
            la, lo = nodes[open_refs[k]]
            needles.append({
                "way": ways[wi][0], "role": ways[wi][1],
                "angle_deg": math.degrees(math.acos(max(-1.0,
                                                        min(1.0, cosv)))),
                "height_m": height, "legs_m": (n1, n2),
                "lat": la, "lon": lo,
            })
    # ── 8. unowned wall strip (R16-2) ────────────────────────────────
    # A wall node standing ``wall_above_m`` or more above a ramp within
    # ``wall_reach_m`` of it, with a GAP between the two boundaries: no
    # shape owns that strip, so the mesh drapes it at DEM/Z0 and the
    # wall reads as a floating lip.  A node that lies ON the ramp
    # boundary is OWNED — the wall face carries the drop.
    ramp_edges = []
    ramp_nids: set = set()
    for wi, (_wid, cls, refs, ref_tag) in enumerate(ways):
        if cls not in _RAMP_ROLES and ref_tag not in _RAMP_REFS:
            continue
        ramp_nids.update(refs)
        for a, b in zip(refs, refs[1:]):
            if a == b:
                continue
            ramp_edges.append((xy[a], xy[b], alts.get(a), alts.get(b)))
    wall_nodes = []
    if ramp_edges:
        ramp_tree = STRtree([LineString([e[0], e[1]]) for e in ramp_edges])
        seen_wall = set()
        for wi, (_wid, cls, refs, ref_tag) in enumerate(ways):
            if cls not in _WALL_ROLES:
                continue
            # OWNERSHIP IS A PROPERTY OF THE WALL, NOT OF ONE NODE: a
            # wall whose inner edge IS the ramp's boundary (shared node
            # ids, or vertices sitting on it) owns the whole face, crest
            # included.  A wall that reaches the ramp NOWHERE leaves the
            # strip between them to the mesh, and every node of it
            # stands over unowned ground.
            welded = len(set(refs) & ramp_nids) >= 2
            if not welded:
                on_boundary = 0
                for nid in set(refs):
                    px, py = xy[nid]
                    pt = Point(px, py)
                    for gi in ramp_tree.query(pt.buffer(owned_tol_m)):
                        (ax, ay), (bx, by), _aa, _ab = ramp_edges[gi]
                        if LineString([(ax, ay), (bx, by)]).distance(
                                pt) <= owned_tol_m:
                            on_boundary += 1
                            break
                    if on_boundary >= 2:
                        welded = True
                        break
            for nid in refs:
                if (wi, nid) in seen_wall:
                    continue
                seen_wall.add((wi, nid))
                wall_alt = alts.get(nid)
                if wall_alt is None:
                    continue
                px, py = xy[nid]
                pt = Point(px, py)
                best = None
                for gi in ramp_tree.query(pt.buffer(wall_reach_m)):
                    (ax, ay), (bx, by), aa, ab = ramp_edges[gi]
                    dx, dy = bx - ax, by - ay
                    seg2 = dx * dx + dy * dy
                    if seg2 < 1e-18:
                        continue
                    t = max(0.0, min(1.0, ((px - ax) * dx
                                           + (py - ay) * dy) / seg2))
                    qx, qy = ax + t * dx, ay + t * dy
                    d = math.hypot(px - qx, py - qy)
                    if d > wall_reach_m:
                        continue
                    if aa is None or ab is None:
                        continue
                    ramp_alt = aa + (ab - aa) * t
                    if best is None or d < best[0]:
                        best = (d, ramp_alt)
                if best is None:
                    continue
                gap, ramp_alt = best
                if wall_alt - ramp_alt < wall_above_m:
                    continue
                la, lo = nodes[nid]
                wall_nodes.append({
                    "nid": nid, "way": _wid, "role": cls, "ref": ref_tag,
                    "gap_m": gap, "rise_m": wall_alt - ramp_alt,
                    "unowned": not welded, "lat": la, "lon": lo,
                })
    return {
        "twin_ring_pairs": twin_pairs,
        "twin_ring_missing": sum(p["missing"] for p in twin_pairs),
        "twin_ring_on_chord": sum(p["on_chord"] for p in twin_pairs),
        "submicron_clusters": clusters,
        "submicron_sites": cluster_sites,
        "wall_above_ramp": wall_nodes,
        "wall_unowned": sum(1 for w in wall_nodes if w["unowned"]),
        "needles": needles,
        "needle_tol": (needle_deg, chord_tol_m, cluster_tol_deg),
    }


def analyze(path, tol=0.15, top=12, cluster_tol_deg=1e-9, needle_deg=25.0,
            chord_tol_m=0.09):
    nodes, xy, ways, node_alts = _load(path)
    _first_lat = next(iter(nodes.values()))[0] if nodes else 0.0
    mlat = 111320.0
    mlon = 111320.0 * math.cos(math.radians(_first_lat))
    node_ways = defaultdict(set)          # nid -> set(way index)
    edges = []                            # (wi, ax, ay, bx, by)
    for wi, (_wid, _cls, refs, _ref) in enumerate(ways):
        for nid in refs:
            node_ways[nid].add(wi)
        for a, b in zip(refs, refs[1:]):
            ax, ay = xy[a]
            bx, by = xy[b]
            if (ax - bx) ** 2 + (ay - by) ** 2 < 1e-18:
                continue
            edges.append((wi, a, b, ax, ay, bx, by))
    edge_geoms = [LineString([(e[3], e[4]), (e[5], e[6])]) for e in edges]
    tree = STRtree(edge_geoms)

    # ── 1. T-vertices ────────────────────────────────────────────────
    BIN_EDGES = [(1e-4, "exact<0.1mm"), (1e-3, "0.1-1mm"),
                 (1e-2, "1mm-1cm"), (5e-2, "1-5cm"), (1e9, "5cm+")]

    def _bin(d):
        for lim, name in BIN_EDGES:
            if d < lim:
                return name
        return "5cm+"

    tv_by_bin = Counter()
    tv_by_pair = Counter()
    tv_worst = []
    for nid, owners in node_ways.items():
        px, py = xy[nid]
        pt = Point(px, py)
        for gi in tree.query(pt.buffer(tol)):
            wi, a, b, ax, ay, bx, by = edges[gi]
            if wi in owners:
                continue
            if a == nid or b == nid:
                continue
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = ((px - ax) * dx + (py - ay) * dy) / L2
            if t <= 0.0 or t >= 1.0:
                continue
            L = math.sqrt(L2)
            # skip projections that land near an endpoint: those are
            # near-coincident-node cases, class 3's territory
            if t * L < 1e-3 or (1.0 - t) * L < 1e-3:
                continue
            perp = abs((px - ax) * dy - (py - ay) * dx) / L
            if perp >= tol:
                continue
            # is there a node of way wi at the same spot? then the ways
            # DO share the chain here (two nids one coord — class 3)
            cls_owner = "+".join(sorted({ways[o][1] for o in owners}))
            cls_edge = ways[wi][1]
            key = tuple(sorted((cls_owner, cls_edge)))
            tv_by_bin[_bin(perp)] += 1
            tv_by_pair[(key, _bin(perp))] += 1
            la, lo = nodes[nid]
            tv_worst.append((perp, key, la, lo, nid))

    # ── 2. near-parallel pairs (angle < 0.5deg, separation <= tol) ──
    np_pairs = Counter()
    np_worst = []
    seen = set()
    COS_LIM = 0.9999619   # cos(0.5 deg)
    for gi, g in enumerate(edge_geoms):
        wi, a, b, ax, ay, bx, by = edges[gi]
        v1x, v1y = bx - ax, by - ay
        n1 = math.hypot(v1x, v1y)
        for gj in tree.query(g.buffer(tol)):
            if gj <= gi:
                continue
            wj, c, d, cx, cy, dx_, dy_ = edges[gj]
            if wj == wi:
                continue
            # shared node -> wedge_audit's domain; still count (it is
            # the same lens) but mark shared
            v2x, v2y = dx_ - cx, dy_ - cy
            n2 = math.hypot(v2x, v2y)
            cosv = abs(v1x * v2x + v1y * v2y) / (n1 * n2)
            if cosv < COS_LIM:
                continue
            # separation: max over the shorter edge's endpoints of
            # distance to the longer edge, requiring span overlap
            if n1 >= n2:
                lg, s0, s1 = g, (cx, cy), (dx_, dy_)
            else:
                lg = edge_geoms[gj]
                s0, s1 = (ax, ay), (bx, by)
            d0 = lg.distance(Point(s0))
            d1 = lg.distance(Point(s1))
            sep = max(d0, d1)
            if not (1e-9 < sep <= tol):
                continue
            # projection overlap of the shorter onto the longer
            key = tuple(sorted((ways[wi][1], ways[wj][1])))
            pk = (min(gi, gj), max(gi, gj))
            if pk in seen:
                continue
            seen.add(pk)
            np_pairs[key] += 1
            mx, my = (s0[0] + s1[0]) / 2, (s0[1] + s1[1]) / 2
            np_worst.append((sep, key, my / mlat, mx / mlon))

    # ── 4. interior edge crossings ───────────────────────────────────
    # Two edges from DIFFERENT ways whose interiors transversally cross
    # at a single point that sits strictly inside both edges.  Solved
    # analytically (segment-segment) for speed and to apply the same
    # endpoint tolerance the T-vertex class uses (1 mm): a crossing whose
    # intersection lands within that distance of any endpoint is really an
    # endpoint touch or a T-vertex and belongs to classes 1/3, not here.
    ENDPOINT_TOLERANCE = 1e-3   # metres
    xing_pairs = Counter()
    xing_worst = []
    for gi, g in enumerate(edge_geoms):
        wi, a, b, ax, ay, bx, by = edges[gi]
        rx, ry = bx - ax, by - ay
        for gj in tree.query(g):
            if gj <= gi:
                continue
            wj, c, d, cx, cy, ddx, ddy = edges[gj]
            if wj == wi:
                continue                     # same way: not a foreign cross
            sx, sy = ddx - cx, ddy - cy
            denom = rx * sy - ry * sx
            if abs(denom) < 1e-12:
                continue                     # parallel -> classes 1/2
            qx, qy = cx - ax, cy - ay
            t = (qx * sy - qy * sx) / denom  # param on edge gi
            u = (qx * ry - qy * rx) / denom  # param on edge gj
            if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
                continue                     # segments miss each other
            len_r = math.hypot(rx, ry)
            len_s = math.hypot(sx, sy)
            # intersection must sit in the interior of BOTH edges by more
            # than the endpoint tolerance, else it is an endpoint touch
            depth = min(t * len_r, (1.0 - t) * len_r,
                        u * len_s, (1.0 - u) * len_s)
            if depth < ENDPOINT_TOLERANCE:
                continue
            ix, iy = ax + t * rx, ay + t * ry
            key = tuple(sorted((ways[wi][1], ways[wj][1])))
            xing_pairs[key] += 1
            xing_worst.append((depth, key, iy / mlat, ix / mlon,
                               ways[wi][0], ways[wj][0], len_r, len_s))

    # ── 4b. SAME-WAY SELF-CROSSINGS (round-9 order, 2026-07-14) ──────
    # A way's own edges properly crossing — a self-intersecting loop.
    # The class-4 detector deliberately skips same-way pairs (foreign
    # crossings only), which let 9 self-crossing gap interior rings
    # through at CYXY.  Same analytic segment-segment test, same 1 mm
    # endpoint tolerance; ADJACENT edges (sharing a node id, including
    # a closed ring's first/last) are a shared endpoint, not a cross.
    self_x = Counter()
    self_x_worst = []
    for gi, g in enumerate(edge_geoms):
        wi, a, b, ax, ay, bx, by = edges[gi]
        rx, ry = bx - ax, by - ay
        for gj in tree.query(g):
            if gj <= gi:
                continue
            wj, c, d, cx, cy, ddx, ddy = edges[gj]
            if wj != wi:
                continue                     # foreign cross: class 4
            if len({a, b} & {c, d}):
                continue                     # adjacent edges share a node
            sx, sy = ddx - cx, ddy - cy
            denom = rx * sy - ry * sx
            if abs(denom) < 1e-12:
                continue
            qx, qy = cx - ax, cy - ay
            t = (qx * sy - qy * sx) / denom
            u = (qx * ry - qy * rx) / denom
            if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
                continue
            len_r = math.hypot(rx, ry)
            len_s = math.hypot(sx, sy)
            depth = min(t * len_r, (1.0 - t) * len_r,
                        u * len_s, (1.0 - u) * len_s)
            if depth < ENDPOINT_TOLERANCE:
                continue
            ix, iy = ax + t * rx, ay + t * ry
            self_x[ways[wi][1]] += 1
            self_x_worst.append((depth, ways[wi][1], iy / mlat,
                                 ix / mlon, ways[wi][0]))

    # ── 3. coincident node ids ───────────────────────────────────────
    by_coord = defaultdict(list)
    for nid, (la, lo) in nodes.items():
        by_coord[(la, lo)].append(nid)
    co = {c: ids for c, ids in by_coord.items() if len(ids) > 1}

    # ── report ───────────────────────────────────────────────────────
    print(f"== {path}")
    print(f"   nodes {len(nodes)}  ways {len(ways)}  edges {len(edges)}")
    total_tv = sum(tv_by_bin.values())
    print(f"   T-VERTICES (node on foreign edge interior, perp<{tol}m): "
          f"{total_tv}")
    for _lim, name in BIN_EDGES:
        if tv_by_bin.get(name):
            print(f"     {name:>12}: {tv_by_bin[name]}")
    pair_tot = Counter()
    for (key, _b), c in tv_by_pair.items():
        pair_tot[key] += c
    for key, c in pair_tot.most_common(top):
        bins = {b: n for (k, b), n in tv_by_pair.items() if k == key}
        print(f"     {key[0]} ~ {key[1]}: {c}   {bins}")
    print(f"   NEAR-PARALLEL PAIRS (angle<0.5deg, 0<sep<={tol}m): "
          f"{sum(np_pairs.values())}")
    for key, c in np_pairs.most_common(top):
        print(f"     {key[0]} ~ {key[1]}: {c}")
    print(f"   COINCIDENT-NODE coords (>=2 nids): {len(co)}")
    print(f"   INTERIOR EDGE CROSSINGS (foreign edges properly cross, "
          f"depth>={ENDPOINT_TOLERANCE * 1000:g}mm): "
          f"{sum(xing_pairs.values())}")
    for key, c in xing_pairs.most_common(top):
        print(f"     {key[0]} ~ {key[1]}: {c}")
    if xing_worst:
        print("   crossings (deepest interior first):")
        for depth, key, la, lo, wa, wb, lr, ls in sorted(
                xing_worst, reverse=True)[:max(top, len(xing_worst))]:
            print(f"     depth={depth * 1000:8.3f}mm {key[0]}~{key[1]} "
                  f"@ {la:.7f},{lo:.7f} ways={wa}/{wb} "
                  f"edgelen={lr:.2f}/{ls:.2f}m")
    print(f"   SAME-WAY SELF-CROSSINGS (a way's own edges properly "
          f"cross, depth>={ENDPOINT_TOLERANCE * 1000:g}mm): "
          f"{sum(self_x.values())}")
    for key, c in self_x.most_common(top):
        print(f"     {key}: {c}")
    if self_x_worst:
        print("   self-crossings (deepest interior first):")
        for depth, key, la, lo, wa in sorted(
                self_x_worst, reverse=True)[:max(top, len(self_x_worst))]:
            print(f"     depth={depth * 1000:8.3f}mm {key} "
                  f"@ {la:.7f},{lo:.7f} way={wa}")
    if np_worst:
        print("   worst near-parallel pairs:")
        for sep, key, la, lo in sorted(np_worst, reverse=True)[:top]:
            print(f"     sep={sep * 1000:8.3f}mm {key[0]}~{key[1]} "
                  f"@ {la:.7f},{lo:.7f}")
    print("   worst T-vertices:")
    for perp, key, la, lo, nid in sorted(tv_worst, reverse=True)[:top]:
        print(f"     perp={perp * 1000:8.3f}mm {key[0]}~{key[1]} "
              f"@ {la:.7f},{lo:.7f} nid={nid}")
    gc = geometry_consistency(
        path, cluster_tol_deg=cluster_tol_deg, needle_deg=needle_deg,
        chord_tol_m=chord_tol_m, nodes=nodes, xy=xy, ways=ways,
        alts=node_alts)
    print(f"   TWIN-RING PAIRS (one boundary spelled twice, differing "
          f"vertices within {chord_tol_m} m of the partner chord): "
          f"{len(gc['twin_ring_pairs'])} "
          f"({gc['twin_ring_missing']} differing vertex(es), "
          f"{gc['twin_ring_on_chord']} exactly on the chord)")
    tw_pairs = Counter(tuple(sorted((p["role_a"], p["role_b"])))
                       for p in gc["twin_ring_pairs"])
    for key, c in tw_pairs.most_common(top):
        print(f"     {key[0]} ~ {key[1]}: {c}")
    for p in sorted(gc["twin_ring_pairs"],
                    key=lambda r: -r["missing"])[:top]:
        print(f"     ways={p['way_a']}/{p['way_b']} "
              f"{p['role_a']}~{p['role_b']} shared={p['shared']} "
              f"missing={p['missing']} on_chord={p['on_chord']} "
              f"worst={p['worst_offset_m'] * 1000:.4f}mm "
              f"@ {p['lat']:.7f},{p['lon']:.7f}")
    print(f"   SUB-MICRON CLUSTERS (distinct nids within "
          f"{cluster_tol_deg:g} deg): {gc['submicron_clusters']}")
    for la, lo, na, nb, exact in sorted(gc["submicron_sites"])[:top]:
        print(f"     @ {la:.11f},{lo:.11f} nids={na}/{nb} "
              f"{'identical' if exact else 'near'}")
    print(f"   WALL NODES >=1 m ABOVE A RAMP WITHIN 2 m: "
          f"{len(gc['wall_above_ramp'])} "
          f"({gc['wall_unowned']} UNOWNED — a gap strip no shape covers)")
    for w in sorted(gc["wall_above_ramp"],
                    key=lambda r: -r["rise_m"])[:top]:
        print(f"     rise={w['rise_m']:6.2f}m gap={w['gap_m'] * 1000:8.2f}mm "
              f"{'UNOWNED' if w['unowned'] else 'owned'} "
              f"{w['ref'] or w['role']} way={w['way']} nid={w['nid']} "
              f"@ {w['lat']:.7f},{w['lon']:.7f}")
    print(f"   NEEDLE TIPS (tip angle <= {needle_deg} deg): "
          f"{len(gc['needles'])}")
    nd_role = Counter(n["role"] for n in gc["needles"])
    for role, c in nd_role.most_common(top):
        above = sum(1 for n in gc["needles"]
                    if n["role"] == role and n["height_m"] > chord_tol_m)
        print(f"     {role}: {c} ({above} above the {chord_tol_m} m "
              f"near-collinear floor)")
    for n in sorted(gc["needles"], key=lambda r: r["angle_deg"])[:top]:
        print(f"     angle={n['angle_deg']:6.2f}deg "
              f"height={n['height_m'] * 1000:9.3f}mm "
              f"legs={n['legs_m'][0]:.2f}/{n['legs_m'][1]:.2f}m "
              f"{n['role']} way={n['way']} "
              f"@ {n['lat']:.7f},{n['lon']:.7f}")
    print()
    return (total_tv, sum(np_pairs.values()), sum(xing_pairs.values()),
            sum(self_x.values()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--tol", type=float, default=0.15)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--cluster-tol-deg", type=float, default=1e-9,
                    help="sub-micron cluster tolerance in degrees")
    ap.add_argument("--needle-deg", type=float, default=25.0,
                    help="tip-angle cap for the needle class")
    ap.add_argument("--chord-tol", type=float, default=0.09,
                    help="how far a twin ring's differing vertex may sit "
                         "off the partner chord (metres)")
    args = ap.parse_args()
    for p in args.paths:
        analyze(p, tol=args.tol, top=args.top,
                cluster_tol_deg=args.cluster_tol_deg,
                needle_deg=args.needle_deg, chord_tol_m=args.chord_tol)
