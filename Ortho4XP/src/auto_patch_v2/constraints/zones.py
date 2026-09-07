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

THE STRIP TIE (RULINGS 2026-09-06b law 2, family ``strip_transverse``;
:func:`strip_transverse`): the corridor rows are "no deeper than" the
DEM corridor and, for the NEAREST pavement only, "no higher than" its
mandatory-down — nothing bound a strip vertex ABOVE a runway edge that
was not its nearest pavement (HECA 05C/23C on 1.0.288: the graded strip
stood 5.6 m above the ridge within 60 m).  Every graded-strip vertex
abeam a runway-family edge, inside the runway zone (``d ≤ zone-2 half
width``), is TIED to that edge's foot: ``|z_v − z_foot| ≤
strip_transverse_bound(d)`` — the runway zone class's own transverse cap
accumulated over the corridor (``adjacent_ground.lip_max_down``,
``adjacent_ground.runway.band_max_down``), both ways: the fall side is
the corridor floor :func:`zone_bands` states for the same edge, the rise
side is :func:`strip_transverse`'s own row.

THE RUNWAY-EDGE TIE (RULINGS 2026-09-06p (1), the same family and the
same row): the rise side binds EVERY vertex of ANY role — ring or hole,
any owner except the runway family's own faces and a retaining wall's
crest — lying abeam a runway-family ring edge within that runway's
zone-2 half width: ``z_v − z_foot ≤ strip_transverse_bound(d)``.
THE FALL SIDE (RULINGS 2026-09-06q (2)) is the SAME row's other bound,
``z_foot − z_v ≤ strip_transverse_bound(d)``: the tie is TWO-WAY against
the runway for every vertex it covers (HECA 05C/23C after 06p: 15
strip-hole vertices 0.35–1.25 m BELOW the edge within 3 m — cliffs the
rise-only row let stand as the stub's "own law"); where :func:`zone_bands`
already states that edge's floor the row carries the rise side alone.
The pocket rule's nearest-pavement floor STAYS beside a runway (06q (2)'s
second clause measured and not applied: see :func:`zone_bands`).
``own_law`` exempts NOTHING from this row: the 06b
population was the strip-only vertices, and HECA's 05C/23C ridges
(owner sim read 1.0.291, 06o) were 207 vertices over the bound — stub
170, primary_parallel 35, junction 2 — every one a ring vertex of an
airside value face that ``own_law`` left to its own rows, none of which
reached the runway edge 7 m away (v2921: one hop 482 m to a crossing
station, no no_step pair inside the 150 m route window, the ridge IS the
DEM while the runway is cut 3.4–5.8 m below it).  A rigid pad is ONE
level and carries the tie on its rim vertex nearest the edge only (the
``Flat`` carries the level; per-vertex rows on one plane against a
sloping edge are the v2padflat contradiction).  The row cites the
graded-strip face the vertex touches (``face:<id>``) so the tier
machinery holds it in the STRIP's tier — the strip law's row, junior to
the runway (whose profile never flexes to it), senior to the DEM pull
in the objective; a vertex touching no strip face reads its own tier.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.tables import (is_value_role, role_side, strip_transverse_bound,
                          zone2_half_width_m, zone_bounds)
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import View, view
from .roads import road_family_roles
from .strips import runway_groups

__all__ = ["zone_bands", "strip_transverse"]

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


@_dc.dataclass
class _Context:
    """The zone law's reading of one map, shared by :func:`zone_bands`
    and :func:`strip_transverse` (one derivation of membership, feet
    and exemptions — never two)."""

    vw: View
    edges: list
    by_family: dict
    cell: float
    reach: float
    half_of: _t.Callable
    abeam: _t.Callable[[int, int], bool]
    member: dict[int, set[tuple]]
    own_law: set[int]
    wall_vertices: set[int]
    pad_rim: dict[int, int]
    found: _t.Callable[[int, set], list]
    #: THE TIE POPULATION (06p (1)): every vertex of every non-runway-family
    #: face (ring and holes), the runway family's own vertices and the wall
    #: crests excluded -> the graded-strip face it touches (or -1)
    tie_pop: dict[int, int] = _dc.field(default_factory=dict)
    #: rigid face id -> its rim vertices (attached pads included)
    rigid_rims: dict[int, list[int]] = _dc.field(default_factory=dict)


def _context(planar: PlanarMap, law: Law, airport: Airport) -> _Context | None:
    """The shared setup (module docstring); ``None`` with no pavement."""
    vw = view(planar, law)
    edges = _pavement_edges(vw)
    if not edges:
        return None
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
        # outer ring AND holes: a pad inside the strip is a hole of the
        # zone face, and its rim vertices are strip vertices (KCLT
        # building26, 2026-09-05 — see the rigid-pad note below)
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
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
    # A RIGID PAD HAS NO OWN LEVEL (09-01g: "levelled by its contact";
    # 03i: "takes its level from what it touches"): its rim vertices that
    # are strip vertices stay banded like any other, and the FLAT row lifts
    # the whole pad to the band — measured KCLT building26 (2026-09-05):
    # a pad inside taxiway F's zone 2, touching no airside pavement, was
    # held at the lip only by an accidental weld to a groundside road;
    # round 3 cut the road back (04u) and the unbanded pad settled 2.14 m
    # onto its DEM, tearing the strip 2.17 m in 2.5–3.9 m (24 rows).
    roads = tuple(road_family_roles(law))
    own_law = {v for f in vw.faces_of_role(tuple(
        r for r, spec in law.tables.precedence.roles.items()
        if spec.value and not getattr(spec, "rigid", False)
        and (spec.side == "airside" or r in roads)))
        for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring}
    # A RIGID PAD IS ONE LEVEL, SO IT CARRIES ONE BAND: its rim vertices
    # span different ``d`` and different feet, and the zone-1 band beside
    # the lip cannot meet the zone-2 mandatory-down at the far rim on one
    # flat plane (measured KCLT 2026-09-05: the hard set went infeasible
    # on exactly that, and the tier machinery demoted every zone row).
    # The pad takes its level from the NEAREST pavement (the pocket rule):
    # its rim vertex nearest a lip carries the full band and NO other rim
    # vertex carries any zone row — the ``Flat`` group carries that level
    # to them.  A per-vertex floor on the far rim ("no deeper than" its own
    # foot) is the same contradiction one lip-slope later: along a 1.5 %
    # lip the far foot rises faster than the band is wide (0.28 m at
    # d = 17.5 beside a code-3 runway), so a 100 m pad's floor at one end
    # sat above its ceiling at the other — measured 2026-09-05 (lane
    # v2padflat): the hard set INFEASIBLE on the pad's Flat + two zone
    # rows (the m5g §6-2 KCLT class).  Bands on a detached pad apply to
    # the group's single level, never per vertex.
    # ONLY A DETACHED PAD is levelled by the strip: a pad with a rim vertex
    # on airside pavement (or a road) takes THAT level (03h weld, 04r
    # contact), and a strip band on its other rim vertices would demand
    # the mandatory-down below the very lip it sits on — measured
    # 2026-09-05: CYXY / SPLP / SPJC / OTHH went hard-infeasible on it.
    pad_rim: dict[int, int] = {}          # vertex -> rigid face id (detached pads)
    attached_rim: set[int] = set()        # rim vertices of pads touching pavement
    rigid_rims: dict[int, list[int]] = {}
    for f in vw.faces_of_role(tuple(
            r for r, spec in law.tables.precedence.roles.items()
            if getattr(spec, "rigid", False))):
        rim = [v for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring]
        rigid_rims[f.id] = rim
        if any(v in own_law for v in rim):
            attached_rim.update(rim)
            continue
        for v in rim:
            pad_rim.setdefault(v, f.id)
    own_law = own_law | attached_rim
    # THE TIE POPULATION (06p (1), module docstring): every vertex of every
    # face outside the runway family, the runway family's own vertices and
    # the wall crests excluded, with the strip face it touches
    rw_roles = set(law.tables.precedence.runway_family.members)
    runway_v = {v for f in vw.faces_of_role(tuple(rw_roles))
                for ring in [vw.rings[f.id], *vw.holes[f.id]] for v in ring}
    tie_pop: dict[int, int] = {}
    for f in vw.faces_of_role(tuple(r for r in law.tables.precedence.roles
                                    if r not in rw_roles and r != "retaining_wall")):
        strip = f.role == "graded_strip" and _face_class(f) is not None
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                if v in runway_v or v in wall_vertices:
                    continue
                if strip or v not in tie_pop:
                    tie_pop[v] = f.id if strip else tie_pop.get(v, -1)

    def _found(v: int, classes: set) -> list:
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
            return []
        found = [f_ for f_ in found if abeam(v, f_[1])]
        found.sort(key=lambda f_: (f_[3], f_[1]))
        # a pavement beyond its own corridor contributes ONLY as the
        # nearest reference; as a farther candidate its floor is void
        # (measured CYXY: a taxiway 80 m off floored a runway zone-2
        # vertex above the runway's mandatory-down — an IIS of five rows)
        found = [f_ for rank, f_ in enumerate(found)
                 if rank == 0 or f_[3] <= (half_of(edges[f_[1]]) or 0.0)
                 or any(_face_class_of(edges[f_[1]]) == c for c in classes)]
        return found

    return _Context(vw, edges, by_family, cell, reach, half_of, abeam, member, own_law,
                    wall_vertices, pad_rim, _found, tie_pop, rigid_rims)


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
    ctx = _context(planar, law, airport)
    if ctx is None:
        return []
    vw, edges, member, own_law = ctx.vw, ctx.edges, ctx.member, ctx.own_law
    wall_vertices, pad_rim, _found = ctx.wall_vertices, ctx.pad_rim, ctx.found
    rows: list[Row] = []
    pad_nearest: dict[int, int] = {}      # rigid face id -> its nearest rim vertex
    pad_d: dict[int, float] = {}
    for v, fid in pad_rim.items():
        if v not in member or v in own_law or v in wall_vertices:
            continue
        fv = _found(v, member[v])
        if not fv:
            continue
        if fid not in pad_nearest or fv[0][3] < pad_d[fid]:
            pad_nearest[fid], pad_d[fid] = v, fv[0][3]

    for v, classes in member.items():
        if v in own_law or v in wall_vertices:
            continue
        src = Source(GEN, "zones.adjacent_ground (2026-08-01)", (f"vertex:{v}",))
        found = _found(v, classes)
        if not found:
            continue
        # THE POCKET FLOOR STAYS BESIDE A RUNWAY (RULINGS 2026-09-06q (2)
        # second clause, measured and NOT applied — lane v2ridge2): voiding
        # a taxi edge's nearest-pavement floor wherever a runway edge is
        # within its zone-2 half width tore HECA's strip 3.1–3.3 m in 3 m
        # at the runway corridor's OUTER ring (05L/23R zone-2 ring vertex
        # -9844 at d 74.9, nearest pavement taxiway E's lip 3 m away:
        # floor 65.15 with the lip, 62.0 with the runway's corridor floor
        # alone — it fell to its DEM, 12 strip_seam_tear rows, the CYXY
        # 2026-09-04e class).  The 15 cliffs the clause named were
        # own-law hole vertices with NO taxi floor: the tie's FALL side
        # (:func:`strip_transverse`) is what binds them.  Where a taxi
        # floor and the runway tie truly conflict the strip tier relaxes.
        for rank, (d_eff, k, t, _d) in enumerate(found):
            a, b, fam, cn, cl = edges[k]
            role = "runway" if fam == "runway" else "junction"
            lo, hi = zone_bounds(law, role, d_eff, cn, cl)
            if lo is None and hi is None:
                continue
            if rank > 0:
                hi = None            # a farther pavement: floor only
            if v in pad_rim and pad_nearest.get(pad_rim[v]) != v:
                continue             # a pad's far rim: no row (the Flat carries the level)
            if t <= 0.0:
                terms: tuple[tuple[int, float], ...] = ((v, 1.0), (a, -1.0))
            elif t >= 1.0:
                terms = ((v, 1.0), (b, -1.0))
            else:
                terms = ((v, 1.0), (a, -(1.0 - t)), (b, -t))
            rows.append(Linear(terms, lo, hi, src))
    return rows


def strip_transverse(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE STRIP TIE / RUNWAY-EDGE TIE rows (module docstring): for every
    vertex ``v`` of the tie population (``_Context.tie_pop`` — any role
    but the runway family's own faces and the wall crests, 06p (1))
    whose nearest ABEAM runway-family edge holds it in the runway zone
    (``_nearest_edge`` over the runway family, ``d ≤`` the class's zone-2
    half width), with foot ``(a, b, t)`` at lateral distance ``d``:

        z_v − ((1 − t)·z_a + t·z_b) ≤ bound,
        bound = strip_transverse_bound(law, d, code)

    — the RISE side.  The FALL side is the vertex's own law: for a
    graded-strip vertex the corridor FLOOR :func:`zone_bands` already
    states for that very edge (``zone_bounds`` is the one derivation: the
    floor's magnitude IS ``strip_transverse_bound``), so it is not minted
    twice — a duplicate row is what HiGHS's QP factorisation refused on
    the relax twin (kNotset over 66 duplicate pairs, measured 2026-09-06);
    for every other vertex its zone floor, reach band or pad level.  A
    rigid pad carries the tie on its rim vertex nearest the edge only
    (the ``Flat`` carries the level; per-vertex rows on one plane are the
    v2padflat contradiction).  The row cites the strip face the vertex
    touches, so it sits in the strip's tier."""
    ctx = _context(planar, law, airport)
    if ctx is None:
        return []
    vw, edges = ctx.vw, ctx.edges
    grid = ctx.by_family.get("runway")
    if not grid:
        return []
    src = Source(GEN, "zones.adjacent_ground.runway.band_max_down strip tie "
                 "(2026-09-06b law 2; every vertex 2026-09-06p; two-way 2026-09-06q)", ())

    def nearest(v: int):
        return _nearest_edge(vw, v, edges, grid, ctx.cell, ctx.half_of, ctx.reach,
                             lambda k: ctx.abeam(v, k))

    # a rigid pad: ONE tie, on the rim vertex nearest a runway edge
    pad_pick: dict[int, int] = {}
    for fid, rim in ctx.rigid_rims.items():
        best: tuple[float, int] | None = None
        for v in rim:
            if v not in ctx.tie_pop:
                continue
            near = nearest(v)
            if near is not None and (best is None or near[2] < best[0]):
                best = (near[2], v)
        if best is not None:
            pad_pick[fid] = best[1]
    rim_of: dict[int, int] = {v: fid for fid, rim in ctx.rigid_rims.items() for v in rim}
    rows: list[Row] = []
    for v in sorted(ctx.tie_pop):
        fid_rigid = rim_of.get(v)
        if fid_rigid is not None and pad_pick.get(fid_rigid) != v:
            continue
        near = nearest(v)
        if near is None:
            continue
        k, t, d = near
        # NOT MINTED WHERE THE CORRIDOR ALREADY HOLDS IT: when this runway
        # edge is a strip vertex's NEAREST pavement, ``zone_bands`` states
        # its mandatory-down ceiling (the vertex must sit BELOW the edge),
        # which dominates the tie; the tie binds exactly where the nearest
        # pavement is another surface and the runway contributes a floor
        # only (the pocket rule) — HECA's strip between 05C/23C and the
        # parallel stub pav101.  A dominated duplicate beside the ceiling
        # is also what tipped HiGHS's QP into its approximation on the
        # relax twin (measured 2026-09-06: 1,080 candidates, kNotset).
        # THE FALL SIDE (RULINGS 2026-09-06q (2)): the tie is TWO-WAY — a
        # vertex within the half width may neither rise above nor fall
        # below the edge foot faster than the strip bound.  Where
        # ``zone_bands`` already states this very edge's FLOOR (the runway
        # is a farther pavement of a strip vertex: floor only, the pocket
        # rule) the row here carries the rise side alone — never the same
        # floor twice (the duplicate HiGHS's QP factorisation refused).
        floor_stated = False
        classes = ctx.member.get(v)
        if classes and v not in ctx.own_law and v not in ctx.wall_vertices:
            if v in ctx.pad_rim:
                continue                  # zone_bands' pad rule owns it
            found = ctx.found(v, classes)
            if found and found[0][1] == k and found[0][0] <= (ctx.half_of(edges[k]) or 0.0):
                continue
            floor_stated = any(f_[1] == k for f_ in found)
        a, b, _fam, cn, cl = edges[k]
        bound = strip_transverse_bound(law, d, cn, cl)
        if bound is None or d <= 0.0:
            continue
        if t <= 0.0:
            terms: tuple[tuple[int, float], ...] = ((v, 1.0), (a, -1.0))
        elif t >= 1.0:
            terms = ((v, 1.0), (b, -1.0))
        else:
            terms = ((v, 1.0), (a, -(1.0 - t)), (b, -t))
        strip_fid = ctx.tie_pop[v]
        inputs = ((f"face:{strip_fid}", f"vertex:{v}") if strip_fid >= 0
                  else (f"vertex:{v}",))
        rows.append(Linear(terms, None if floor_stated else -bound, bound,
                           Source(src.generator, src.ruling, inputs)))
    return rows
