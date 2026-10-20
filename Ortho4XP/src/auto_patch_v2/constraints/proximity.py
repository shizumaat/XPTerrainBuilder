"""CROSS-SHAPE PROXIMITY generator — family ``cross_shape`` (v1
``check_grade._check_cross_shape_proximity``; v2 ``verify/steps.
cross_shape``, the one reader): two DISTINCT vertices of DIFFERENT
governed faces within ``emit.identity.min_distinct_spacing_m`` of each
other hold the STRICTER of the two faces' caps over their distance —
the census's proximity law, read at the identity knob.  By the identity
law two distinct vertices are never closer than that spacing, so the
population is the stand-off class exactly AT it: a pad rim cut back
half a metre from its neighbour (CYXY building6 ↔ building7 across the
0.5 m sliver of apron pav17, measured 2026-09-05: 0.25 m over 0.5 m in
both readers).  A designed separation (a road-family face against a
non-road one; groundside against airside) is no pair, as the reader
skips it; an ungoverned face (no cap) contributes nothing.

WHY A GENERATOR (lane v2relaxfull6, RULINGS 2026-09-05ab): before the
centreline-only route graph (05aa) that pair was a no_step route pair
through the pad FRONTAGE hop the owner withdrew; under 05aa/05ab both
rim vertices are welded contacts whose only route to each other is
83.5 m out to taxilane station 3154 and back (167 m, outside the 150 m
no-step window), so no route family prices the 0.5 m sliver and the
census reads the step.  The law that governs it is this one, the
reader's own; stating it as a row is the exact twin of the reader.
The rows carry no ``face:`` input: their tier is the vertices' (the
stricter face's law is the row's, ``solve/tiers.row_tier``).

THE AIRSIDE SLIVER (owner RULINGS 2026-10-19an, #328: "two airside
pavements that lie within weld spacing of each other are one surface"):
:func:`airside_sliver_pairs` — a vertex of an airside pavement face
within ``emit.identity.weld_spacing_m`` of an EDGE of another airside
pavement face it is not a vertex of, across a strip of non-pavement (the
planar weld leaves one where the gap read over the tolerance before the
snap), holds the stricter of the two caps against the edge's level at
its perpendicular foot over the gap — the census's ``vertex_to_edge_step``
reading at its own contact tolerance (the same 1.0 m).  MEASURED (HECA
taxi E junction ``dsf:objpav112#2`` against apron ``route21``, 0.98 m
apart across ``adjacent_ground:taxi:E:zone1``): no other row ties them —
the airside pairs run along a pavement ROUTE only, and none crosses the
strip — so the step stood at 0.35-0.54 m.
"""
from __future__ import annotations

import math

from ..law import Law
from ..law.tables import is_rigid_role, is_value_role, role_side
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import view
from .roads import road_family_roles

__all__ = ["cross_shape_pairs", "airside_sliver_pairs"]

GEN = "proximity"


def _designed_separation(law: Law, roads: frozenset[str], ra: str, rb: str) -> bool:
    if (ra in roads) != (rb in roads):
        return True
    return (role_side(law, ra) == "groundside") != (role_side(law, rb) == "groundside")


def cross_shape_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One ``Diff`` per distinct-vertex pair of different governed faces
    within the identity spacing, at the stricter cap (module docstring)."""
    vw = view(planar, law)
    prox = law.tables.emit.identity.min_distinct_spacing_m
    roads = frozenset(road_family_roles(law))
    caps: dict[int, float] = {}
    for fid in planar.faces:
        # §50.2 Y10: the pair takes the STRICTER of the two faces' caps,
        # and each face's cap is the effective one ``vw.caps`` carries
        # (``precedence.face_cap`` with the map) — same rule, new number.
        rc = vw.caps[fid]
        if rc is not None:
            caps[fid] = rc[0]
    # every governed vertex with the faces it belongs to
    faces_of: dict[int, list[int]] = {}
    for fid in caps:
        for ring in [vw.rings[fid], *vw.holes[fid]]:
            for v in ring:
                faces_of.setdefault(v, []).append(fid)
    cell = prox
    grid: dict[tuple[int, int], list[int]] = {}
    for v in faces_of:
        x, y = vw.xy[v]
        grid.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(v)
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for v, fa in faces_of.items():
        x, y = vw.xy[v]
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for w in grid.get((cx + dx, cy + dy), ()):
                    if w <= v:
                        continue
                    key = (v, w)
                    if key in seen:
                        continue
                    seen.add(key)
                    d = math.hypot(x - vw.xy[w][0], y - vw.xy[w][1])
                    if d > prox or d <= 0.0:
                        continue
                    cap = None
                    pair: tuple[int, int] | None = None
                    for A in fa:
                        for B in faces_of[w]:
                            if A == B or _designed_separation(
                                    law, roads, planar.faces[A].role, planar.faces[B].role):
                                continue
                            c = min(caps[A], caps[B])
                            if cap is None or c < cap:
                                cap, pair = c, (A, B)
                    if cap is None or pair is None:
                        continue
                    A, B = pair
                    rows.append(Diff(v, w, cap, d, Source(
                        GEN, "emit.identity.min_distinct_spacing_m cross_shape proximity "
                        "(v1 _check_cross_shape_proximity; 2026-09-05ab)",
                        (planar.faces[A].ref, planar.faces[B].ref))))
    return rows


SLIVER_RULING = ("emit.identity.weld_spacing_m two airside pavements within weld "
                 "spacing are one surface (owner 2026-10-19an; #328)")


def _sliver_faces(planar: PlanarMap, law: Law, caps) -> list[int]:
    """The airside PAVEMENT faces: governed, value-carrying, not rigid
    (a pad is levelled by its own contact law), side ``airside`` — the
    weld's own partner class (``planar/weld``)."""
    return [fid for fid, f in planar.faces.items()
            if caps.get(fid) is not None and role_side(law, f.role) == "airside"
            and is_value_role(law, f.role) and not is_rigid_role(law, f.role)]


def airside_sliver_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One row per airside pavement vertex whose NEAREST edge of another
    airside pavement face lies within the weld spacing across a
    non-pavement gap: ``|z_v − z_foot| ≤ cap · d`` at the stricter cap,
    ``z_foot`` the edge's level at the perpendicular foot (module
    docstring, THE AIRSIDE SLIVER)."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.strtree import STRtree

    vw = view(planar, law)
    weld = float(law.tables.emit.identity.weld_spacing_m)
    min_d = float(law.tables.emit.identity.min_distinct_spacing_m)
    caps = {fid: (c[0] if c is not None else None) for fid, c in vw.caps.items()}
    faces = _sliver_faces(planar, law, caps)
    if len(faces) < 2 or weld <= 0.0:
        return []
    faces_of: dict[int, list[int]] = {}
    edges: list[tuple[int, int, int]] = []          # (face, a, b)
    polys: list[Polygon] = []
    for fid in faces:
        rings = [r for r in (vw.rings[fid], *vw.holes[fid]) if len(r) >= 3]
        if not rings:
            continue
        polys.append(Polygon([vw.xy[v] for v in rings[0]],
                             [[vw.xy[v] for v in r] for r in rings[1:]]))
        for r in rings:
            for i, v in enumerate(r):
                faces_of.setdefault(v, []).append(fid)
                edges.append((fid, v, r[(i + 1) % len(r)]))
    seg_tree = STRtree([LineString([vw.xy[a], vw.xy[b]]) for _f, a, b in edges])
    pave_tree = STRtree(polys)
    rows: list[Row] = []
    for v, fa in faces_of.items():
        x, y = vw.xy[v]
        best = None
        for i in seg_tree.query(Point(x, y).buffer(weld)):
            fb, a, b = edges[int(i)]
            if fb in fa or v in (a, b):
                continue
            (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            if seg2 <= 0.0:
                continue
            t = min(1.0, max(0.0, ((x - ax) * dx + (y - ay) * dy) / seg2))
            d = math.hypot(x - (ax + t * dx), y - (ay + t * dy))
            if best is None or d < best[0]:
                best = (d, t, fb, a, b)
        if best is None or best[0] > weld or best[0] <= 0.0:
            continue
        d, t, fb, a, b = best
        (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
        mid = Point((x + ax + t * (bx - ax)) / 2.0, (y + ay + t * (by - ay)) / 2.0)
        if any(polys[int(j)].contains(mid) for j in pave_tree.query(mid)):
            continue                     # pavement between them: one face already
        cap = min(min(caps[f] for f in fa), caps[fb])
        bound = cap * max(d, min_d)
        src = Source(GEN, SLIVER_RULING,
                     (planar.faces[fa[0]].ref, planar.faces[fb].ref))
        if t <= 1e-9 or t >= 1.0 - 1e-9:
            rows.append(Diff(v, a if t <= 0.5 else b, cap, max(d, min_d), src))
        else:
            rows.append(Linear(((v, 1.0), (a, -(1.0 - t)), (b, -t)),
                               -bound, bound, src))
    return rows
