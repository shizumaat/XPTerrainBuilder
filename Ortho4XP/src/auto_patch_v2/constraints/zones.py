"""ADJACENT-GROUND ZONE generator (families ``adjacent_ground_tear`` /
``strip_seam_tear``; RULINGS 2026-08-01 zone law, memory
``adjacent-ground-zone-law``; ``law/zones.toml``).

Every ``graded_strip`` vertex lies at lateral distance ``d`` from the
pavement its zone serves — the PERPENDICULAR distance to the nearest
ring EDGE of the runway-family / taxi-family faces (a vertex distance
overstates ``d`` beside a long chord and turns the mandatory-down band
against the abeam-longitudinal law: measured CYXY 14L/32R, an IIS of
one band row and one strip row).  ``tables.zone_bounds`` — the ONE
derivation site of the corridor (2026-08-30l) — gives the signed
``(floor, ceiling)`` offset from the edge's elevation at the foot, so
the row is ``floor ≤ z_v − z_foot ≤ ceiling`` with ``z_foot`` the
interpolation along that edge (a three-term ``Linear``).  Beyond zone 2
no face exists — the DEM owns zone 3 and the terrace at the outer ring
is lawful (memory: "boundary steps are lawful terraces"); the objective
pulls every strip vertex toward its DEM sample.

THE POCKET RULE (08-01 clarification: "enclosed pockets between graded
zones fill"; 03i "takes its level from what it touches"): a strip vertex
gets ONE band, from the nearest pavement edge of EITHER family with that
edge's own class — a runway zone-2 vertex 3 m from a parallel taxiway is
bound to the taxiway's lip, not to a 2 m cut below the runway (measured
CYXY: an IIS of the two bands and the no-step pairs between the
pavements).  The drainage spine of a filled pocket is M3.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import is_value_role, role_side, zone2_half_width_m, zone_bounds
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import View, view
from .roads import road_family_roles
from .strips import runway_groups

__all__ = ["zone_bands"]

GEN = "zones"


def _pavement_edges(vw: View) -> list[tuple[int, int, str, int | None, str | None]]:
    """The ring EDGES of every runway-family / taxi-family face, each
    with the family and class the zone law keys by."""
    p = vw.law.tables.precedence
    fam_of: dict[str, str] = {}
    for r in p.runway_family.members:
        fam_of[r] = "runway"
    for r in p.taxi_family.members:
        fam_of[r] = "taxi"
    out: dict[tuple[int, int], tuple[int, int, str, int | None, str | None]] = {}
    for f in vw.faces_of_role(tuple(fam_of)):
        fam = fam_of[f.role]
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            n = len(ring)
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                key = (a, b) if a < b else (b, a)
                cur = out.get(key)
                # a shared edge keeps the senior family (runway first)
                if cur is None or (cur[2] == "taxi" and fam == "runway"):
                    out[key] = (key[0], key[1], fam, f.code_number, f.code_letter)
    return [out[k] for k in sorted(out)]


def _nearest_edge(vw: View, v: int, edges: list, grid: dict, cell: float,
                  half_of: _t.Callable[[tuple], float | None], reach_m: float,
                  admit: _t.Callable[[int], bool] | None = None
                  ) -> tuple[int, float, float] | None:
    """``(edge index, t, distance)`` of the nearest pavement edge WHOSE OWN
    CLASS CORRIDOR holds the vertex (``d ≤ half_of(edge)``) within
    ``reach_m`` — an edge of a narrower class beside the vertex does not
    shadow the wider-class edge whose zone the vertex lies in (measured
    CYXY: a taxi-D zone-2 vertex left bandless by a nearer letter-less
    edge, then a 3.9 m seam tear against its banded neighbour)."""
    x, y = vw.xy[v]
    cx, cy = int(x // cell), int(y // cell)
    span = int(math.ceil(reach_m / cell)) + 1
    best: tuple[int, float, float] | None = None
    for dx in range(-span, span + 1):
        for dy in range(-span, span + 1):
            for k in grid.get((cx + dx, cy + dy), ()):
                if admit is not None and not admit(k):
                    continue
                a, b = edges[k][0], edges[k][1]
                (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
                vx, vy = bx - ax, by - ay
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 < 1e-18 else max(0.0, min(
                    1.0, ((x - ax) * vx + (y - ay) * vy) / l2))
                d = math.hypot(x - (ax + t * vx), y - (ay + t * vy))
                half = half_of(edges[k])
                if half is None or d > half:
                    continue
                if best is None or d < best[2]:
                    best = (k, t, d)
    return best


def _face_class_of(e: tuple) -> tuple[str, int | None, str | None]:
    """The zone class an edge record keys (``_pavement_edges`` layout)."""
    return (e[2], e[3], e[4])


def _face_class(f) -> tuple[str, int | None, str | None] | None:
    parts = f.ref.split(":")
    if len(parts) < 2 or parts[1] not in ("runway", "taxi"):
        return None
    return parts[1], f.code_number, f.code_letter


def zone_bands(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The corridor rows per graded-strip vertex.

    MEMBERSHIP IS THE MAP'S: a vertex of a zone face of class ``C`` is
    in ``C``'s corridor (the planar zones are mitred buffers, so an
    outer-ring vertex can sit past the nominal half-width at a convex
    corner — ``d`` is clamped to the half-width there, never dropped:
    measured CYXY, 11 seam tears from bandless outer-ring vertices).

    THE POCKET RULE: of the vertex's own zone classes the NEAREST
    pavement contributes the full band (floor and mandatory-down
    ceiling); every other class / family whose corridor holds the vertex
    contributes its FLOOR only ("no deeper than") — between a runway and
    a parallel taxiway the ground fills toward the nearer surface instead
    of being cut to the farther one's band (08-01 clarification), and the
    ceiling reference changes continuously with the nearest edge so no
    seam tear is minted."""
    vw = view(planar, law)
    edges = _pavement_edges(vw)
    if not edges:
        return []
    # THE LATERAL LAW ONLY (v1 ``adjacent_ground_envelope``: "runway ENDS
    # are explicitly out of scope — the runway-end skirt law owns terrain
    # beyond a runway end"): a runway-family edge binds a strip vertex
    # only where the vertex lies abeam the runway's own extent; beyond an
    # end the end-corridor rows (``strips.py``) govern.
    groups = {g.ref: g for g in runway_groups(vw, airport)}
    face_of_edge: dict[int, int] = {}
    for e in planar.edges.values():
        for fid in (e.left_face, e.right_face):
            if fid is not None and planar.faces[fid].role in \
                    law.tables.precedence.runway_family.members:
                face_of_edge[e.id] = fid
    edge_index = {(e.a, e.b): e.id for e in planar.edges.values()}

    def abeam(v: int, k: int) -> bool:
        e = edges[k]
        if e[2] != "runway":
            return True
        eid = edge_index.get((e[0], e[1]))
        fid = face_of_edge.get(eid) if eid is not None else None
        if fid is None:
            return True
        ref = planar.faces[fid].ref.split("+")[0]
        g = groups.get(ref)
        if g is None:
            return True
        x, y = vw.xy[v]
        s_ = (x - g.axis_a[0]) * g.unit[0] + (y - g.axis_a[1]) * g.unit[1]
        return 0.0 <= s_ <= g.length_m

    cell = 50.0
    by_class: dict[tuple, dict[tuple[int, int], list[int]]] = {}
    by_family: dict[str, dict[tuple[int, int], list[int]]] = {"runway": {}, "taxi": {}}
    for k, e in enumerate(edges):
        (ax, ay), (bx, by) = vw.xy[e[0]], vw.xy[e[1]]
        x0, x1 = sorted((ax, bx))
        y0, y1 = sorted((ay, by))
        cls = (e[2], e[3], e[4])
        for gx in range(int(x0 // cell), int(x1 // cell) + 1):
            for gy in range(int(y0 // cell), int(y1 // cell) + 1):
                by_class.setdefault(cls, {}).setdefault((gx, gy), []).append(k)
                by_family[e[2]].setdefault((gx, gy), []).append(k)

    def half_of(e: tuple) -> float | None:
        return zone2_half_width_m(law, "runway" if e[2] == "runway" else "junction",
                                  e[3], e[4])

    reach = max((half_of(e) or 0.0) for e in edges)
    rows: list[Row] = []
    done: set[int] = set()
    # the zone classes each strip vertex is a member of (from its faces)
    member: dict[int, set[tuple]] = {}
    for f in vw.faces_of_role(("graded_strip",)):
        cls = _face_class(f)
        if cls is None:
            continue
        for v in vw.rings[f.id]:
            member.setdefault(v, set()).add(cls)
    # THE ZONES STOP AT THE WALL (M4, 08-30l row "adjacent-ground zones
    # stop at the wall"; 2026-09-03b L2 "the wall IS the discontinuity"):
    # a strip vertex on a retaining wall's edge carries the wall's crest
    # (the DEM) and no band toward a pavement lip binds it — measured
    # OTHH: an IIS of two crest pins and one mandatory-down band row
    wall_vertices = {v for f in vw.faces_of_role(("retaining_wall",))
                     for v in vw.rings[f.id]}
    # THE BAND BINDS REGARDLESS OF SHAPE OWNERSHIP (owner 2026-08-30,
    # "taxiway adjacent-ground band cuts groundside": zones 1-2 grade FROM
    # THE TAXIWAY and a groundside shape boundary is not an exemption).
    # Only a vertex an AIRSIDE value face touches carries that face's own
    # law instead of the band, and a ROAD-family vertex keeps the road's
    # (a road edge-sharing pavement IS that pavement, memory
    # ``free-road-ruling``; its 1.5 % cap cannot hold the lip's 3 %
    # mandatory-down — measured CYXY, an IIS of the two rows); a strip
    # vertex shared with any other groundside value face (a
    # ``groundside_pavement`` beside the lip) is banded like any other —
    # measured CYXY: unbanded, it sat on the DEM 2.16 m above the junction
    # lip 4.3 m away (the 2026-09-04e seam tear).
    roads = tuple(road_family_roles(law))
    own_law = {v for f in vw.faces_of_role(tuple(
        r for r, spec in law.tables.precedence.roles.items()
        if spec.value and (spec.side == "airside" or r in roads)))
        for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring}
    for v, classes in member.items():
        if v in own_law or v in wall_vertices:
            continue
        src = Source(GEN, "zones.adjacent_ground (2026-08-01)", (f"vertex:{v}",))
        found: list[tuple[float, int, float, float]] = []   # (d_eff, k, t, d)
        for cls in classes:
            g = by_class.get(cls)
            if not g:
                continue
            near = _nearest_edge(vw, v, edges, g, cell, lambda e: 1e9, reach * 2.0,
                                 lambda k: abeam(v, k))
            if near is None:
                continue
            k, t, d = near
            half = half_of(edges[k]) or 0.0
            found.append((min(d, half), k, t, d))
        # THE NEAREST PAVEMENT BY TRUE DISTANCE, its band clamped to its
        # own half-width — never "the nearest whose corridor holds the
        # vertex": at the taxi corridor's outer edge the ceiling reference
        # would otherwise jump from the taxiway's band to the runway's
        # mandatory-down (measured OTHH: a runway zone-2 vertex 23 m from
        # a code-F taxiway, 1 m below its neighbour 1.6 m away inside the
        # 22 m corridor — the 2026-09-04e seam tear).  The pocket rule
        # (08-01 "takes its level from what it touches") is continuous
        # only if the reference is the nearest edge, full stop.
        # ...but only for a vertex INSIDE some corridor: outside every
        # corridor the ground is zone 3, the DEM, and no pavement reaches
        # it — measured LEMD: a vertex 3 m off a runway END (no abeam
        # band) took a taxiway 19 m away as its reference, an IIS against
        # the end-skirt chord from the runway end.
        for fam, g in by_family.items():
            near = _nearest_edge(vw, v, edges, g, cell, half_of, reach,
                                 lambda k: abeam(v, k))
            if near is not None and all(near[0] != f_[1] for f_ in found):
                found.append((near[2], near[0], near[1], near[2]))
        if found:
            for fam, g in by_family.items():
                near = _nearest_edge(vw, v, edges, g, cell, lambda e: 1e9,
                                     reach * 2.0, lambda k: abeam(v, k))
                if near is not None and all(near[0] != f_[1] for f_ in found):
                    k, t, d = near
                    found.append((min(d, half_of(edges[k]) or 0.0), k, t, d))
        if not found:
            continue
        found = [f_ for f_ in found if abeam(v, f_[1])]
        found.sort(key=lambda f_: (f_[3], f_[1]))
        # a pavement beyond its own corridor contributes ONLY as the
        # nearest reference; as a farther candidate its floor is void
        # (measured CYXY: a taxiway 80 m off floored a runway zone-2
        # vertex above the runway's mandatory-down — an IIS of five rows)
        found = [f_ for rank, f_ in enumerate(found)
                 if rank == 0 or f_[3] <= (half_of(edges[f_[1]]) or 0.0)
                 or any(_face_class_of(edges[f_[1]]) == c for c in classes)]
        for rank, (d_eff, k, t, _d) in enumerate(found):
            a, b, fam, cn, cl = edges[k]
            role = "runway" if fam == "runway" else "junction"
            lo, hi = zone_bounds(law, role, d_eff, cn, cl)
            if lo is None and hi is None:
                continue
            if rank > 0:
                hi = None            # a farther pavement: floor only
            if t <= 0.0:
                terms: tuple[tuple[int, float], ...] = ((v, 1.0), (a, -1.0))
            elif t >= 1.0:
                terms = ((v, 1.0), (b, -1.0))
            else:
                terms = ((v, 1.0), (a, -(1.0 - t)), (b, -t))
            rows.append(Linear(terms, lo, hi, src))
    return rows
