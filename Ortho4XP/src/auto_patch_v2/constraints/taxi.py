"""TAXI-FAMILY generator (family ``within_shape`` on the taxi family,
``plane_gradient`` on triangles; ICAO Annex 14 §3.9.10 / FAA AC
150/5300-13B §4 through ``rulesets.<authority>.taxi``).

THE TAXI GRADE LAW IS EXPRESSED BY THE CHAIN (RULINGS 2026-09-05ac,
stating 05aa/05ab compactly; spec ``relaxation-without-certificate-
spec.md`` §8/§9): the route graph's own edges are the rows, and there
are NO PAIR ROWS for taxi faces at all —

* one hard ``Diff`` per CENTRELINE EDGE of every stretch, every polyline
  vertex, at the stretch's cap (:func:`taxi_centerlines`; the runway
  ridge edges are ``runway_profile``'s rows);
* one hard row per LATERAL HOP — a ring vertex to its PERPENDICULAR FOOT
  on the centreline at the face's TRANSVERSE cap over the perpendicular
  distance only (RULINGS 2026-09-06p (2); ``routes``' LATERAL edges): a
  three-term ``Linear`` ``|z_v − (1−t)·z_a − t·z_b| ≤ cap·d`` where the
  foot is a virtual station ``(a, b, t)`` inside a segment, a two-vertex
  ``Diff`` where the foot is a station — and one ``Diff`` per runway
  CROSSING (05z b) (:func:`taxi_chain`);
* the pad CONTACTS are ``pads.frontage_near_miss``'s own rows (a welded
  rim IS the pavement vertex, 05ab).

Every pair's route budget is IMPLIED by the chain (triangle inequality:
``|z_a − z_b| ≤ Σ cap·len`` along any route joining them), so the
within-shape route reading of 05ab holds for every pair without a row
per pair — measured HECA 2026-09-05: the pairwise formulation (160k
route rows) stalled HiGHS dual simplex past 34 min; a row per leaving
chord only where "stricter" (38k) under-constrained 393 pairs past 2 %
along their routes; the chain is ~8k rows.  A vertex no centreline
attaches (no hop) has no taxi row: the transverse law, the junction
mesh (inside the bounded junction territory only, 05x) and no_step
govern it — PLUS the SHORT-PAIR BOX below.

THE SHORT-PAIR BOX (RULINGS 2026-09-06s, generator law): the chain
prices a rim pair through its feet there-and-back (hop + along + hop:
HECA stub pav78's two rim neighbours 4.04 m apart carried Δz 2.16 m
under a 21.4 m budget over 1,427 route-metres; pav73 27 m across carried
6.9 m), so every taxi-family pair of ONE RING (the outer ring, or a hole
ring — the oracle's population: a hole is its own way judged at its
host's role) closer than ``emit.within_shape.withdrawn_chord_min_m``
(30 m) carries a hard ``Diff`` ``|Δz| ≤ cL·|Δs| + cT·|Δt|`` against the
NEAREST stretch axis of the map at the pair's midpoint (``Δs`` along
it, ``Δt`` across; ``cL`` that stretch's longitudinal cap, ``cT`` its
letter's transverse cap — ``junction_mesh.box_rows``'s anisotropic
form on a pair; ``stretches.AxisIndex``), taxi tier, never relaxable
(:func:`taxi_box`; a junction-mesh face's population — its mesh edges
and common-stretch pairs, 04y — is boxed inside ``junction_mesh``).  A
pair of ``withdrawn_chord_min_m`` or longer stays route-priced (05ac).
The v2 verify (``verify/within.py::taxi_box``) and the v1 oracle
(``check_grade._StretchBox``, family ``taxi_box``) read the same
population against the same bound.  The verify reader keeps its 05ab pair-over-route reading
from the published ``taxi_route_pairs`` (:func:`taxi_pair_routes`: every
pair of every taxi-family ring with its route distance and budget) —
the taxi family's instrument; the v1 oracle's chord rows are the
withdrawn law (05aa), reported apart by the harness census.

* a THREE-vertex face is a rendered triangle whose PLANE gradient the
  census reads (user 2026-07-05): its gradient vector is linear in z, so
  ``|∇z| ≤ cap`` is bound by 16 half-planes at ``cap · cos(π/16)`` — a
  linearisation of the disc (1.9 % inside the law's own bound; the
  tightening is a linearisation artefact, not a law value).
"""
from __future__ import annotations

import math
import typing as _t

import dataclasses as _dc

from ..law import Law
from ..law.tables import is_rigid_role, role_cap, role_family
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import View, view
from .routes import CENTRELINE, CONTACT, CROSSING, LATERAL, route_pairs, routes
from .stretches import AxisIndex, Stretches, edge_cap, pair_caps, stretches

__all__ = ["taxi_chain", "taxi_centerlines", "triangle_planes",
           "all_pairs", "pad_vertices", "plane_rows", "box_rows",
           "plane_gradient_terms", "PricedPair",
           "taxi_pair_routes", "chain_ruling",
           "taxi_box", "short_pairs", "box_pair_rows", "axis_index",
           "BOX_RULING", "STATS"]

GEN = "taxi"
#: ``runway_profile.GEN`` (stated here: ``runway_profile`` imports this module)
RUNWAY_GEN = "runway_profile"
_GRADIENT_DIRECTIONS = 16
#: The short-pair box row's citation (module docstring); ``solve.why``
#: keys the ``taxi_box`` family on it.
BOX_RULING = "short-pair box |dz| <= cL*|ds| + cT*|dt| vs the nearest stretch axis (2026-09-06s)"
#: Per-generator statistics ``generate`` publishes as ``<name>.<stat>``:
#: ``taxi_box``: ``pairs`` (short pairs boxed), ``no_axis`` (a map with
#: no stretch: no row).
STATS: dict[str, dict[str, int]] = {}


def all_pairs(vw: View, ring: list[int], cap_l: float, src: Source,
              min_d: float) -> list[Row]:
    """Every distinct vertex pair of ``ring`` at ``cap_l``."""
    rows: list[Row] = []
    n = len(ring)
    for i in range(n):
        a = ring[i]
        for j in range(i + 1, n):
            b = ring[j]
            d = vw.dist(a, b)
            if d < min_d:
                continue
            rows.append(Diff(a, b, cap_l, d, src))
    return rows


def pad_vertices(vw: View) -> frozenset[int]:
    """Every vertex a rigid (pad) face carries — a pair to one is a
    FRONTAGE pair at the pad's cap."""
    law = vw.law
    out: set[int] = set()
    for f in vw.pm.faces.values():
        if is_rigid_role(law, f.role):
            out.update(vw.rings[f.id])
            for h in vw.holes[f.id]:
                out.update(h)
    return frozenset(out)


@_dc.dataclass(frozen=True)
class PricedPair:
    """One taxi-family within-shape pair for the PUBLICATION (the verify
    reader's population, RULINGS 2026-09-05ab): the face, the pair, the
    CHORD reading (``cap_chord × d_chord``, the census's plane rule) and
    the ROUTE reading (``dist`` / ``budget``; ``None`` when no route joins
    the two — no law edge).  ``pad``: a pad endpoint.  No row is minted
    from it (05ac: the chain is the law)."""

    face: int
    a: int
    b: int
    cap_chord: float            # the plane reading's cap (a pad endpoint: the pad's)
    d_chord: float
    dist: float | None
    budget: float | None
    pad: bool

    @property
    def routed(self) -> bool:
        return self.dist is not None

    @property
    def chord_bound_m(self) -> float:
        return self.cap_chord * self.d_chord


_PAIR_CACHE: dict[int, tuple[PlanarMap, Law, list[PricedPair]]] = {}


def taxi_pair_routes(planar: PlanarMap, law: Law, airport: Airport | None
                     ) -> list[PricedPair]:
    """Every taxi-family within-shape pair (``stretches.pair_caps``: every
    distinct pair at its stretch cap, RULINGS 2026-09-04t-3; a JUNCTION
    BODY's common-stretch pairs only, 04y; a pad endpoint at the pad's
    cap, 09-01g) with its chord and route readings (module docstring;
    cached per map)."""
    hit = _PAIR_CACHE.get(id(planar))
    if hit is not None and hit[0] is planar and hit[1] is law:
        return hit[2]
    vw = view(planar, law)
    st = stretches(planar, law)
    members = law.tables.precedence.taxi_family.members
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    pads = pad_vertices(vw)
    pad_cap = law.tables.common.roles["building"].longitudinal
    mesh_roles = frozenset(law.tables.emit.within_shape.junction_mesh_roles)
    chord: list[tuple[int, int, int, float, float, bool]] = []
    groups: list[list[int]] = []
    for f in vw.faces_of_role(members):
        cap = role_cap(law, f.role, f.code_number, f.code_letter)
        if cap is None:
            continue
        common_only = f.role in mesh_roles
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            groups.append(list(ring))
            for a, b, c, d in pair_caps(planar, law, st, f.id, ring,
                                        cap.longitudinal, min_d, common_only):
                pad = a in pads or b in pads
                chord.append((f.id, a, b, min(c, pad_cap) if pad else c, d, pad))
    table = route_pairs(routes(planar, law, airport), groups)
    out: list[PricedPair] = []
    for fid, a, b, c, d, pad in chord:
        key = (a, b) if a < b else (b, a)
        hit_r = table.get(key)
        out.append(PricedPair(fid, a, b, c, d,
                              None if hit_r is None else hit_r[0],
                              None if hit_r is None else hit_r[1], pad))
    _PAIR_CACHE.clear()
    _PAIR_CACHE[id(planar)] = (planar, law, out)
    return out


def chain_ruling(law: Law, role: str | None, kind: int) -> tuple[str, str]:
    """``(generator, citation)`` of one chain row: the law the edge STATES
    — a LATERAL hop at its face's transverse cap, named for the face's
    law family (``taxi`` on a taxi-family face; ``runway_profile`` on a
    runway-family face; the role itself — ``apron`` — for a common-table
    role, cited ``common.roles.<role>`` so the relaxation reads the
    apron's tier through ``relax.stated_role``); a runway CROSSING at the
    runway longitudinal cap.  A hop is the ATTACHMENT of its own face's
    vertex, so its family is that face's, never the taxi family's by
    default (measured on the M5 / relax twins: apron hops named ``taxi``
    read as taxi rows relaxed)."""
    if kind == CROSSING:
        return GEN, "rulesets.runway.longitudinal crossing, chain (2026-09-05z b / 05ac)"
    if role is not None and role in law.tables.common.roles:
        return role, f"common.roles.{role} lateral hop, chain (2026-09-05aa / 05ac)"
    fam = role_family(law, role) if role is not None else None
    gen = RUNWAY_GEN if fam == "runway" else GEN
    return gen, f"rulesets.{fam or 'taxi'}.transverse lateral hop, chain (2026-09-05aa / 05ac)"


def taxi_chain(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE CHAIN (module docstring; RULINGS 2026-09-05ac): every LATERAL
    hop and every runway CROSSING of the route graph as one hard
    ``Diff`` at the edge's own budget (``cap × length``).  The
    CENTRELINE edges are :func:`taxi_centerlines` / ``runway_profile``'s
    rows and the CONTACT edges ``pads.frontage_near_miss``'s — stated
    once each, never twice.  A hop cites the face it hangs off
    (``face:<id>``) and is named for that face's law family
    (:func:`chain_ruling`) so the relaxation reads that face's tier: an
    apron vertex's hop is an apron row (relaxable under 04t(1)); a
    taxiway's or a runway's is not."""
    g = routes(planar, law, airport)
    faces = planar.faces
    src_of: dict[tuple[int, int], Source] = {}
    rows: list[Row] = []
    for a, b, cap, ln, kind, fid in zip(g.a, g.b, g.cap, g.length, g.kind, g.face):
        kind = int(kind)
        if kind in (CENTRELINE, CONTACT) or ln <= 0.0:
            continue
        fid = int(fid)
        src = src_of.get((fid, kind))
        if src is None:
            f = faces.get(fid)
            role = None if f is None else f.role
            inputs = () if f is None else (f"face:{f.id}", f.ref)
            gen, ruling = chain_ruling(law, role, kind)
            src = Source(gen, ruling, inputs)
            src_of[(fid, kind)] = src
        a, b = int(a), int(b)
        if g.is_foot(b) or g.is_foot(a):
            # THE FOOT ROW (06p (2)): the vertex against the interpolated
            # foot ``(fa, fb, t)`` over the perpendicular distance
            v, ft = (a, b) if g.is_foot(b) else (b, a)
            fa, fb, t = g.foot[ft]
            bound = float(cap) * float(ln)
            rows.append(Linear(((v, 1.0), (fa, -(1.0 - t)), (fb, -t)),
                               -bound, bound, src))
            continue
        rows.append(Diff(a, b, float(cap), float(ln), src))
    return rows


def taxi_centerlines(planar: PlanarMap, law: Law, airport: Airport
                     ) -> list[Row]:
    """Longitudinal cap along every taxi centreline chord: its stretch's
    cap (04t-3), tightened by a governed non-taxi face it bounds (an apron
    lane is apron, RULINGS 2026-09-03j)."""
    vw = view(planar, law)
    st = stretches(planar, law)
    rows: list[Row] = []
    for bid, b in planar.breaklines.items():
        if b.kind != "taxi_centerline":
            continue
        src = Source(GEN, "rulesets.taxi.longitudinal centreline",
                     (f"breakline:{bid}", b.ref))
        for eid in b.edges:
            e = planar.edges[eid]
            cap = edge_cap(planar, law, st, eid, vw.caps)
            if cap is None:
                continue
            d = vw.dist(e.a, e.b)
            if d <= 0.0:
                continue
            rows.append(Diff(e.a, e.b, cap[0], d, src))
    return rows


def triangle_planes(planar: PlanarMap, law: Law, airport: Airport
                    ) -> list[Row]:
    """``|∇z| ≤ cap`` on every governed three-vertex face (the census's
    ``plane_gradient`` family reads triangles only)."""
    vw = view(planar, law)
    from .roads import road_law_caps
    law_caps = road_law_caps(planar, law, airport)
    rows: list[Row] = []
    for fid, ring in vw.rings.items():
        if len(ring) != 3 or vw.holes[fid]:
            continue
        cap = vw.caps[fid]
        if cap is None:
            continue
        cap = (min(cap[0], law_caps.get(fid, cap[0])), cap[1])
        f = planar.faces[fid]
        src = Source(GEN, "plane_gradient (user 2026-07-05)",
                     (f"face:{fid}", f.ref))
        rows.extend(plane_rows(ring, vw.xy, cap[0], src))
    return rows


def plane_gradient_terms(tri: _t.Sequence[int], xy: _t.Mapping[int, tuple[float, float]]
                         ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """The plane gradient of a triangle as LINEAR forms in its corner
    elevations: ``∇z = (Σ gx_i·z_i, Σ gy_i·z_i)`` (barycentric); ``None``
    for a degenerate triangle."""
    (x1, y1), (x2, y2), (x3, y3) = (xy[v] for v in tri)
    det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
    if abs(det) < 1e-9:
        return None
    gx = ((y2 - y3) / det, (y3 - y1) / det, (y1 - y2) / det)
    gy = ((x3 - x2) / det, (x1 - x3) / det, (x2 - x1) / det)
    return gx, gy


def plane_rows(tri: _t.Sequence[int], xy: _t.Mapping[int, tuple[float, float]],
               cap: float, src: Source) -> list[Row]:
    """``|∇z| ≤ cap`` over one triangle as 16 half-plane ``Linear`` rows
    (module docstring); none for a degenerate triangle."""
    g = plane_gradient_terms(tri, xy)
    if g is None:
        return []
    gx, gy = g
    bound = cap * math.cos(math.pi / _GRADIENT_DIRECTIONS)
    rows: list[Row] = []
    for k in range(_GRADIENT_DIRECTIONS):
        th = 2.0 * math.pi * k / _GRADIENT_DIRECTIONS
        c, s = math.cos(th), math.sin(th)
        terms = tuple((tri[i], c * gx[i] + s * gy[i]) for i in range(3))
        rows.append(Linear(terms, None, bound, src))
    return rows


def box_rows(tri: _t.Sequence[int], xy: _t.Mapping[int, tuple[float, float]],
             axis: tuple[float, float], cap_along: float, cap_across: float,
             src: Source) -> list[Row]:
    """THE ANISOTROPIC plane bound (RULINGS 2026-09-06k (2)): over one
    triangle, the gradient component ALONG the unit ``axis`` (the serving
    centreline's direction) within ``±cap_along`` and the component
    ACROSS it within ``±cap_across`` — TWO two-sided ``Linear`` rows, a
    box, never the isotropic cone (which bounds any two points of the
    body by the cap × their STRAIGHT distance: the withdrawn chord law
    05aa).  None for a degenerate triangle or a zero axis."""
    g = plane_gradient_terms(tri, xy)
    n = math.hypot(axis[0], axis[1])
    if g is None or n < 1e-12:
        return []
    gx, gy = g
    ux, uy = axis[0] / n, axis[1] / n
    along = tuple((tri[i], ux * gx[i] + uy * gy[i]) for i in range(3))
    across = tuple((tri[i], -uy * gx[i] + ux * gy[i]) for i in range(3))
    return [Linear(along, -cap_along, cap_along, src),
            Linear(across, -cap_across, cap_across, src)]


def short_pairs(xy: _t.Mapping[int, tuple[float, float]], ring: _t.Sequence[int],
                min_d: float, max_d: float) -> list[tuple[int, int, float]]:
    """Every distinct pair ``(a, b, d)`` of ``ring`` with ``min_d <= d <
    max_d`` — the box's population over one ring (vectorised: a HECA
    junction ring runs to thousands of vertices)."""
    n = len(ring)
    if n < 2:
        return []
    import numpy as np
    ids = np.asarray(ring, dtype=np.int64)
    pts = np.array([xy[v] for v in ring], dtype=float)
    out: list[tuple[int, int, float]] = []
    for i in range(n - 1):
        dd = np.hypot(pts[i + 1:, 0] - pts[i, 0], pts[i + 1:, 1] - pts[i, 1])
        hit = np.nonzero((dd >= min_d) & (dd < max_d))[0]
        a = int(ids[i])
        for j in hit:
            out.append((a, int(ids[i + 1 + j]), float(dd[j])))
    return out


def axis_index(vw: View, st: Stretches) -> AxisIndex:
    """The map's stretches as one :class:`AxisIndex`, cells of the box's
    own floor (``withdrawn_chord_min_m``)."""
    return AxisIndex((([vw.xy[v] for v in s.vertices], s.cap_l, s.cap_t) for s in st.items),
                     vw.law.tables.emit.within_shape.withdrawn_chord_min_m)


def box_pair_rows(vw: View, index: AxisIndex,
                  pairs: _t.Iterable[tuple[int, int, float]], src: Source) -> list[Row]:
    """One hard ``Diff`` per pair at the BOX's bound over the pair's
    distance (module docstring): ``cap = (cL·|Δs| + cT·|Δt|) / d``."""
    rows: list[Row] = []
    for a, b, d in pairs:
        if d <= 0.0:
            continue
        (xa, ya), (xb, yb) = vw.xy[a], vw.xy[b]
        bb = index.box_bound(xa, ya, xb, yb)
        if bb is None:
            continue
        rows.append(Diff(a, b, bb[0] / d, d, src))
    return rows


def taxi_box(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE SHORT-PAIR BOX (module docstring; RULINGS 2026-09-06s) on every
    taxi-family PLANE face (a junction-mesh face is boxed in
    ``junction_mesh`` over its mesh population): every pair of each of
    its rings under ``withdrawn_chord_min_m``."""
    vw = view(planar, law)
    st = stretches(planar, law)
    stats = STATS.setdefault("taxi_box", {"pairs": 0, "no_axis": 0})
    stats["pairs"] = stats["no_axis"] = 0
    index = axis_index(vw, st)
    members = law.tables.precedence.taxi_family.members
    mesh_roles = frozenset(law.tables.emit.within_shape.junction_mesh_roles)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    max_d = law.tables.emit.within_shape.withdrawn_chord_min_m
    rows: list[Row] = []
    for f in vw.faces_of_role(members):
        if f.role in mesh_roles or vw.caps[f.id] is None:
            continue
        src = Source(GEN, BOX_RULING, (f"face:{f.id}", f.ref))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            pairs = short_pairs(vw.xy, ring, min_d, max_d)
            if not index:
                stats["no_axis"] += len(pairs)
                continue
            got = box_pair_rows(vw, index, pairs, src)
            stats["pairs"] += len(got)
            rows.extend(got)
    return rows
