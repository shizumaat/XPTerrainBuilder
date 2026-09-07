"""THE APRON TERRACE JOINTS (RULINGS 2026-09-06n — the owner's KML verdict
on the HECA 05C/23C sag chain: "not a valid route — only taxiway
centreline routes count; no apron except a route through it; the red hop
crosses two separate aprons with a lawful step"; ``emit.toml [terrace]``).

THE LAW.  (1) Feasibility is the ROUTE's: a runway's or taxiway's
elevation is chained only through taxi-centreline rows and the runway's
own rows — apron rows (within-shape chords, edge portions, frontage, pad
welds) never carry reach between two taxi routes.  (2) Two apron cells
that no taxi route joins are SEPARATE TERRACES: their shared boundary is
a lawful step — a terrace joint.  (3) Within one cell the apron law
stands.  (4) A taxi route through an apron couples the apron along that
route, never the whole cell to another route.

"JOINED BY A TAXI ROUTE", precisely.  The cells are the faces of
``terrace.cell_roles`` ∪ ``terrace.neighbour_roles`` (apron, and the
junction the 05w classification gives a hangar apron).  Two cells sharing
a boundary are JOINED when a taxi-centreline STATION — a vertex of a
``taxi_centerline`` breakline, the 1202 network the route graph walks
(05aa) — lies on that shared boundary: a route passes from the one into
the other (the arrangement nodes every crossing, so a route crossing or
touching the boundary always leaves a station on it).  The TERRACE
GROUPS are the connected components of this relation (A joined to J and
J to B: one terrace of three cells — the "common junction cell" case).
Every boundary between two groups with an apron on at least one side is
a JOINT.  A cell no route reaches at all (HECA pav132 #363: 46,000 m² of
hangar apron, 1,193 m against junction #40, no station anywhere) is an
island: every boundary of it is a joint, and it floats to its own DEM
under its own 1 % law — the groundside terrace law's ground between the
graded features.

THE SPLIT.  Along a joint the terrace groups are ranked (total area,
largest first); at every joint vertex the top group keeps the vertex and
every other group present gets a COPY of it ``joint_gap_m`` inside its
own territory (the inward bisector of that group's boundary at the
vertex) — coincident in identity to the eye, a distinct planar vertex
with its own DEM sample, so no row shares a variable across the joint,
the identity law holds (the gap exceeds the identity spacing: v1's
``STACKED_WALL_RETREAT_M`` reason) and the mesh makes the wall in the
band between the two rings exactly as it makes the trench wall inside a
structure rim (2026-09-06b).  The joint tapers to zero where a vertex
must stay shared: a vertex on any breakline (a road centreline, a runway
station) or on a tile seam, a copy that would come within the identity
spacing of another vertex, a face whose retreated ring is no longer a
valid polygon (one retry without those copies — the attempt cap), and
every joint inside a RUNWAY STRIP (walls at runway edges are never
lawful, owner 2026-08-01: the strip footprint ⊕ its end corridors,
``zone2_half_width_m`` / ``end_skirt.corridor_length_m``).  A pad (rigid
face) belongs to the group of the cell it shares most vertices with and
retreats with it.

THE DECLARATION.  ``PlanarMap.terrace_joints`` carries every joint (the
original run, the split pairs); the sidecar ``terrace_joints`` publishes
it in v1's record shape (``points`` / ``step_m`` — the emitted step) so
the v1 oracle prices ``terrace_joint_route`` / ``terrace_joint_strip`` /
``terrace_actual_step`` and forgives the declared step in its step
readers, and v2 verify's step readers do the same.  ``terrace.max_step_m``
is v1's ``APRON_TERRACE_MAX_STEP_M``, REPORTED against the emitted steps
(a joint has no grade law of its own).

Consumers ruled at spec time (owner 2026-08-30l, the consumer census):
``apron_edge_portions`` — a junction's run along a terraced apron is no
longer an apron run (the apron's vertices are its copies); ``routes`` —
a terraced cell's copies attach to no centreline (no reach band, no
no_step pair; a cell with a station keeps its own attachment);
``pads.frontage_contacts`` — a near-miss pair across a joint is refused
(``terrace_group``); ``proximity`` — the gap exceeds the identity
spacing; ``seams`` / breaklines — never split; strips / zones — the
strip keep-out refuses the joint; ``verify/steps`` — the declared step is
the allowance; the v1 oracle — the sidecar key.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..classify.roles import Classification
from ..law import Law
from ..law.tables import is_rigid_role, is_structure_role, zone2_half_width_m
from ..model.airport import Airport
from ..model.frame import XY, Key
from ..model.planar import (Breakline, EdgeKind, Face, PlanarError, PlanarMap,
                            TerraceJoint, Vertex, validate)
from .edges import EdgeTable

__all__ = ["TerraceStats", "split_terraces", "strip_keepout", "terrace_groups"]

#: Which breakline kind is the 1202 network (the route graph's stations).
STATION_KIND = "taxi_centerline"
#: The adjacent-ground zone faces (``planar/zones.py``): corridor cover.
ZONE_ROLE = "graded_strip"
#: Retry bound of the validity pass (owner 2026-08-02 attempt cap), never a law value.
MAX_PASSES = 2


@_dc.dataclass
class TerraceStats:
    """What the split did and what it refused (one line in the build log)."""

    cells: int = 0                 # apron-like faces
    groups: int = 0                # terrace groups (connected components)
    islands: int = 0               # apron cells no route reaches at all
    joints: int = 0
    joint_length_m: float = 0.0
    split_vertices: int = 0        # copies made
    faces_retreated: int = 0
    refused_strip: int = 0         # joint edges inside a runway strip (kept welded)
    refused_breakline: int = 0     # joint vertices on a breakline / seam / structure rim (kept shared)
    refused_spacing: int = 0       # copies inside the identity spacing of another vertex
    refused_invalid: int = 0       # copies withdrawn for an invalid retreated ring
    refused_pinch: int = 0         # a group meeting a joint vertex in two wedges
    refused_map: int = 0           # the re-assembled map failed validation (whole split refused)
    joints_by_pair: list[list] = _dc.field(default_factory=list)   # [a, b, split pairs, length m]


def strip_keepout(classification: Classification, law: Law):
    """The RUNWAY STRIP keep-out: every runway-family cell's long axis,
    extended by the end-skirt corridor at both ends, buffered to the
    zone-2 (strip) half width — a joint touching it is never split."""
    polys = []
    rw_roles = set(law.tables.precedence.runway_family.members)
    cl = law.ruleset.end_skirt.corridor_length_m
    for c in classification.cells:
        if c.role not in rw_roles or len(c.ring) < 3:
            continue
        poly = Polygon(c.ring)
        if poly.is_empty or poly.area <= 0.0:
            continue
        half = zone2_half_width_m(law, "runway", c.code_number, c.code_letter) or 0.0
        end = (cl.value(c.code_number, c.code_letter) if cl is not None else 0.0) or 0.0
        rect = poly.minimum_rotated_rectangle
        pts = list(rect.exterior.coords)[:4]
        if len(pts) < 4:
            polys.append(poly.buffer(half))
            continue
        sides = [(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]), k)
                 for k in range(3)] + [(math.hypot(pts[0][0] - pts[3][0], pts[0][1] - pts[3][1]), 3)]
        _l, k = max(sides)
        p, q = pts[k], pts[(k + 1) % 4]
        r, s = pts[(k + 3) % 4], pts[(k + 2) % 4]
        a = ((p[0] + r[0]) / 2.0, (p[1] + r[1]) / 2.0)
        b = ((q[0] + s[0]) / 2.0, (q[1] + s[1]) / 2.0)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            polys.append(poly.buffer(half))
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        axis = LineString([(a[0] - ux * end, a[1] - uy * end), (b[0] + ux * end, b[1] + uy * end)])
        width = max(half, poly.area / max(L, 1.0) / 2.0)
        polys.append(axis.buffer(width, cap_style="flat").union(poly.buffer(half)))
    return unary_union(polys) if polys else None


def terrace_groups(pm: PlanarMap, law: Law) -> tuple[dict[int, int], set[int], set[int]]:
    """``(group of face, apron-like faces, station vertices)`` — the
    connected components of "joined by a taxi route" (module docstring);
    pads assigned to the cell they share most vertices with."""
    tt = law.tables.emit.terrace
    roles = set(tt.cell_roles) | set(tt.neighbour_roles)
    soft = {fid for fid, f in pm.faces.items() if f.role in roles}
    station: set[int] = set()
    for b in pm.breaklines.values():
        if b.kind == STATION_KIND:
            station.update(b.vertices(pm))
    parent = {fid: fid for fid in soft}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in pm.edges.values():
        a, b = e.left_face, e.right_face
        if a is None or b is None or a not in soft or b not in soft:
            continue
        if e.a in station or e.b in station:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    group = {fid: find(fid) for fid in soft}
    # pads: the group of the cell they share most vertices with
    for fid, f in pm.faces.items():
        if fid in soft or not is_rigid_role(law, f.role):
            continue
        count: dict[int, int] = {}
        for cyc in (f.ring, *f.holes):
            for v in pm.ring_vertices(cyc):
                for g in pm.vertices[v].incident_faces:
                    if g in soft:
                        count[group[g]] = count.get(group[g], 0) + 1
        if count:
            group[fid] = max(count, key=lambda k: (count[k], -k))
    return group, soft, station


def _face_cycles(pm: PlanarMap, fid: int) -> list[list[int]]:
    f = pm.faces[fid]
    return [list(pm.ring_vertices(f.ring))] + [list(pm.ring_vertices(h)) for h in f.holes]


def _chains(edges: list[tuple[int, int]]) -> list[list[int]]:
    """Vertex chains from an unordered edge list (a run may be several)."""
    adj: dict[int, list[int]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen: set[tuple[int, int]] = set()
    out: list[list[int]] = []
    ends = [v for v, nb in adj.items() if len(nb) != 2] or list(adj)
    for start in sorted(ends):
        for nxt in adj[start]:
            key = (min(start, nxt), max(start, nxt))
            if key in seen:
                continue
            chain = [start, nxt]
            seen.add(key)
            cur, prev = nxt, start
            while True:
                cands = [w for w in adj[cur] if w != prev and
                         (min(cur, w), max(cur, w)) not in seen]
                if len(adj[cur]) != 2 or not cands:
                    break
                w = cands[0]
                seen.add((min(cur, w), max(cur, w)))
                chain.append(w)
                prev, cur = cur, w
                if cur == start:
                    break
            if len(chain) > 2 and chain[-1] == chain[0]:
                chain.pop()
            out.append(chain)
    return out


def split_terraces(pm: PlanarMap, law: Law, airport: Airport,
                   classification: Classification) -> tuple[PlanarMap, TerraceStats]:
    """``pm`` with the terrace joints split (module docstring), validated;
    the unchanged map when there is nothing to split."""
    stats = TerraceStats()
    tt = law.tables.emit.terrace
    group, soft, station = terrace_groups(pm, law)
    stats.cells = len(soft)
    if not soft:
        return pm, stats
    pm = _dc.replace(pm, terrace_group=dict(group))   # the groups are the record even unsplit
    cell_roles = set(tt.cell_roles)
    xy = {vid: v.xy for vid, v in pm.vertices.items()}
    area: dict[int, float] = {}
    for fid in soft:
        poly = Polygon([xy[v] for v in pm.ring_vertices(pm.faces[fid].ring)])
        area[group[fid]] = area.get(group[fid], 0.0) + (poly.area if poly.is_valid else 0.0)
    stats.groups = len(area)
    for fid in soft:
        f = pm.faces[fid]
        if f.role in cell_roles and not any(v in station for cyc in (f.ring, *f.holes)
                                            for v in pm.ring_vertices(cyc)):
            stats.islands += 1
    rank = {g: k for k, g in enumerate(sorted(area, key=lambda g: (-area[g], g)))}
    # ── the joints: shared edges between two groups, an apron on one side;
    #    and an apron cell's edges against a ZONE FACE owned by another
    #    group (the corridor cover of a taxiway the cell is not joined to —
    #    the zone reads its band from ITS corridor's pavement only,
    #    ``constraints.zones._pavement_edges``, so the cell retreats from it
    #    exactly as from that pavement; measured HECA 2026-09-06: with the
    #    zone vertices left shared, taxi-E zone #362 between junction #40
    #    and island #363 carried a 6.37 m tear over 3.4 m — 11
    #    ``strip_seam_tear`` rows in both readers)
    zone_owner: dict[int, int] = {}
    for e in pm.edges.values():
        a, b = e.left_face, e.right_face
        if a is None or b is None:
            continue
        for z_, f_ in ((a, b), (b, a)):
            if pm.faces[z_].role == ZONE_ROLE and f_ in group:
                cur = zone_owner.get(z_)
                if cur is None or rank[group[f_]] < rank[cur]:
                    zone_owner[z_] = group[f_]
    joint_edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for e in pm.edges.values():
        a, b = e.left_face, e.right_face
        if a is None or b is None:
            continue
        ra, rb = pm.faces[a].role, pm.faces[b].role
        if a in soft and b in soft:
            if group[a] == group[b] or (ra not in cell_roles and rb not in cell_roles):
                continue
        elif ra == ZONE_ROLE and b in soft and rb in cell_roles:
            if zone_owner.get(a) in (None, group[b]):
                continue
        elif rb == ZONE_ROLE and a in soft and ra in cell_roles:
            if zone_owner.get(b) in (None, group[a]):
                continue
        else:
            continue
        joint_edges.setdefault((min(a, b), max(a, b)), []).append((e.a, e.b))
    if not joint_edges:
        return pm, stats
    # the terrace line MINUS the runway strip (v1's structural guarantee):
    # a joint edge inside the keep-out is no joint, its vertices stay shared
    blocked: set[int] = set(pm.seam_vertices)
    keep = strip_keepout(classification, law)
    if keep is not None and not keep.is_empty:
        for pair, es in list(joint_edges.items()):
            kept = []
            for a, b in es:
                if keep.intersects(LineString([xy[a], xy[b]])):
                    stats.refused_strip += 1
                    blocked.update((a, b))
                else:
                    kept.append((a, b))
            if kept:
                joint_edges[pair] = kept
            else:
                del joint_edges[pair]
        if not joint_edges:
            return pm, stats
    for b in pm.breaklines.values():
        blocked.update(b.vertices(pm))
    # a structure's rim / floor vertex is level with the ground it touches
    # (09-03b): never split from it
    for v, vert in pm.vertices.items():
        if any(is_structure_role(law, pm.faces[f].role) for f in vert.incident_faces):
            blocked.add(v)
    joint_vertices: set[int] = set()
    for es in joint_edges.values():
        for a, b in es:
            joint_vertices.update((a, b))
    # ── copies: at each joint vertex, every non-top group present ─────
    cycles = {fid: _face_cycles(pm, fid) for fid in pm.faces}
    other_face: dict[tuple[int, int], dict[int, int | None]] = {}
    for e in pm.edges.values():
        other_face[(min(e.a, e.b), max(e.a, e.b))] = {
            e.left_face: e.right_face, e.right_face: e.left_face}  # type: ignore[index]

    def boundary_normal(v: int, g: int) -> XY | None:
        """The inward unit bisector of group ``g``'s boundary at ``v``."""
        normals: list[XY] = []
        for fid in pm.vertices[v].incident_faces:
            if group.get(fid) != g:
                continue
            for cyc in cycles[fid]:
                n = len(cyc)
                for i, u in enumerate(cyc):
                    if u != v:
                        continue
                    for p, q in ((cyc[i - 1], v), (v, cyc[(i + 1) % n])):
                        of = other_face[(min(p, q), max(p, q))].get(fid)
                        if of is not None and group.get(of) == g:
                            continue
                        dx, dy = xy[q][0] - xy[p][0], xy[q][1] - xy[p][1]
                        L = math.hypot(dx, dy)
                        if L > 0.0:
                            normals.append((-dy / L, dx / L))
        if len(normals) != 2:
            return None
        sx, sy = normals[0][0] + normals[1][0], normals[0][1] + normals[1][1]
        L = math.hypot(sx, sy)
        return None if L <= 1e-9 else (sx / L, sy / L)

    copies: dict[tuple[int, int], XY] = {}          # (vertex, group) -> xy
    for v in sorted(joint_vertices):
        if v in blocked:
            stats.refused_breakline += 1
            continue
        fs = pm.vertices[v].incident_faces
        present = sorted({group[f] for f in fs if f in group}, key=lambda g: rank[g])
        owners = {zone_owner.get(f) for f in fs if pm.faces[f].role == ZONE_ROLE} - {None}
        need = list(present[1:])
        if present and any(o != present[0] for o in owners):
            need.insert(0, present[0])             # a zone's corridor outranks it here
        for g in need:
            n = boundary_normal(v, g)
            if n is None:
                stats.refused_pinch += 1
                continue
            copies[(v, g)] = (xy[v][0] + tt.joint_gap_m * n[0], xy[v][1] + tt.joint_gap_m * n[1])
    if not copies:
        return pm, stats
    # the identity spacing: a copy within it of any vertex or other copy is refused
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    pts = [Point(p) for p in xy.values()]
    tree = STRtree(pts)
    keys = list(copies)
    cpts = [Point(copies[k]) for k in keys]
    ctree = STRtree(cpts)
    for i, k in enumerate(keys):
        p = cpts[i]
        near = [int(j) for j in tree.query(p.buffer(min_d)) if pts[int(j)].distance(p) < min_d]
        nearc = [int(j) for j in ctree.query(p.buffer(min_d))
                 if int(j) != i and cpts[int(j)].distance(p) < min_d]
        if near or nearc:
            stats.refused_spacing += 1
            copies.pop(k, None)
    # ── substitute, with one retry for faces whose ring goes invalid ───
    def substituted() -> dict[int, list[list[int]]]:
        out: dict[int, list[list[int]]] = {}
        for fid, cycs in cycles.items():
            g = group.get(fid)
            if g is None:
                out[fid] = cycs
                continue
            out[fid] = [[new_id.get((v, g), v) for v in cyc] for cyc in cycs]
        return out

    n0 = len(pm.vertices)
    for _pass in range(MAX_PASSES):
        new_id: dict[tuple[int, int], int] = {}
        new_xy: list[XY] = []
        for k in sorted(copies):
            new_id[k] = n0 + len(new_xy)
            new_xy.append(copies[k])
        allxy = dict(xy)
        for k, vid in new_id.items():
            allxy[vid] = copies[k]
        subs = substituted()
        bad: set[tuple[int, int]] = set()
        for fid, cycs in subs.items():
            if cycs == cycles[fid]:
                continue
            poly = Polygon([allxy[v] for v in cycs[0]],
                           [[allxy[v] for v in h] for h in cycs[1:] if len(h) >= 3])
            if not poly.is_valid or poly.area <= 0.0:
                g = group[fid]
                bad.update((v, g) for cyc in cycles[fid] for v in cyc if (v, g) in copies)
        if not bad:
            break
        stats.refused_invalid += len(bad)
        for k in bad:
            copies.pop(k, None)
    else:
        return pm, stats
    if not copies:
        return pm, stats
    # ── re-assemble the map ────────────────────────────────────────────
    table = EdgeTable()
    for vid in allxy:
        table.incident.setdefault(vid, set())
    faces: dict[int, Face] = {}
    for fid, f in pm.faces.items():
        cycs = subs[fid]
        ring = table.walk(cycs[0], fid)
        holes = tuple(table.walk(h, fid) for h in cycs[1:])
        faces[fid] = _dc.replace(f, ring=ring, holes=holes)
        if cycs != cycles[fid]:
            stats.faces_retreated += 1
    breaklines: dict[int, Breakline] = {}
    kinds: dict[int, EdgeKind] = {}
    old_kind = {(min(e.a, e.b), max(e.a, e.b)): e.kind for e in pm.edges.values()}
    for bid, b in pm.breaklines.items():
        eids = []
        for old in b.edges:
            u, w = pm.edges[old].a, pm.edges[old].b
            eid = table.edge_id(u, w)         # never substituted: breakline vertices stay
            if eid is None:
                raise PlanarError(f"terraces: breakline {bid} lost edge {u}-{w}")
            eids.append(eid)
            kinds[eid] = old_kind.get((min(u, w), max(u, w)), EdgeKind.BREAKLINE)
        breaklines[bid] = _dc.replace(b, edges=tuple(eids))
    edges = {}
    for e in table.edges:
        k = kinds.get(e.id)
        if k is None:
            roles = {faces[f].role for f in (e.left_face, e.right_face) if f is not None}
            k = EdgeKind.ZONE if roles and roles <= {"graded_strip"} else EdgeKind.BOUNDARY
        edges[e.id] = _dc.replace(e, kind=k)
    # the copies' identity and DEM
    _to_xy, to_ll = airport.frame.transformers()
    dp = airport.frame.identity_dp
    dem = airport.dem
    vertices: dict[int, Vertex] = {}
    for vid, v in pm.vertices.items():
        vertices[vid] = _dc.replace(v, incident_faces=tuple(sorted(table.incident.get(vid, ()))))
    for k, vid in new_id.items():
        x, y = copies[k]
        la, lo = to_ll(x, y)
        key: Key = (round(float(la), dp), round(float(lo), dp))
        z = float(dem.z(x, y))
        if math.isnan(z):
            z = pm.vertices[k[0]].dem_z if pm.vertices[k[0]].dem_z is not None else float("nan")
        vertices[vid] = Vertex(vid, (x, y), key, None if math.isnan(z) else z,
                               tuple(sorted(table.incident.get(vid, ()))))
    # ── the joint records ──────────────────────────────────────────────
    joints: list[TerraceJoint] = []
    for (a, b), es in sorted(joint_edges.items()):
        ga, gb = group.get(a), group.get(b)          # a zone side has no group: it keeps the original
        for chain in _chains(es):
            pairs = []
            for v in chain:
                ia = new_id.get((v, ga), v) if ga is not None else v
                ib = new_id.get((v, gb), v) if gb is not None else v
                if ia != ib:
                    pairs.append((ia, ib))
            length = sum(math.hypot(xy[q][0] - xy[p][0], xy[q][1] - xy[p][1])
                         for p, q in zip(chain, chain[1:]))
            joints.append(TerraceJoint(a, b, tuple(chain), tuple(pairs), length))
            stats.joint_length_m += length
            stats.joints_by_pair.append([a, b, len(pairs), round(length, 1)])
    stats.joints = len(joints)
    stats.split_vertices = len(new_id)
    pm2 = PlanarMap(pm.icao, vertices, edges, faces, breaklines, pm.seam_vertices,
                    pm.structures, pm.basins, dict(pm.preferred_z), tuple(joints),
                    dict(group))
    try:
        validate(pm2)
    except PlanarError:
        stats.refused_map += 1
        stats.joints, stats.split_vertices, stats.faces_retreated = 0, 0, 0
        stats.joint_length_m, stats.joints_by_pair = 0.0, []
        return pm, stats
    return pm2, stats
