"""TAXI-FAMILY generator (family ``within_shape`` on the taxi family,
``plane_gradient`` on triangles; ICAO Annex 14 §3.9.10 / FAA AC
150/5300-13B §4 through ``rulesets.<authority>.taxi``).

* every taxi-family face (``precedence.taxi_family.members``) is a PLANE
  shape in the census (all vertex pairs) — the same PAIR POPULATION here
  (``stretches.pair_caps``: every distinct pair; a JUNCTION BODY's
  common-stretch pairs only, RULINGS 2026-09-04y, its body priced by the
  triangle mesh in ``junction_mesh``), each pair PRICED OVER THE
  CENTRELINE ROUTE (RULINGS 2026-09-05ab, spec §9): the row is
  ``|z_a − z_b| ≤ Σ cap·len`` along the route graph's shortest path
  between the two vertices — a's lateral hop, the centreline stretches at
  their own caps, b's hop (``routes.route_pairs``) — never ``cap × chord``
  (HECA pav101 v2632↔v2831: a 1,463 m chord at 1.5 % where the route is
  3,326 m; the chord was the last shortcut across open pavement).  A
  pair on one straight stretch is unchanged (chord = route); a pair no
  route joins gets NO row (the transverse law, the junction mesh and
  no_step govern adjacency); a pad endpoint reaches the route through
  its contact (05ab: welded rim = the pavement vertex) and is priced the
  same way — the pad-cap chord (09-01g's frontage reading) was the
  1,175 m hangar-rim shortcut measured 2026-09-05.  The verify reader
  prices exactly the published budgets (``taxi_route_pairs``);
* every ``taxi_centerline`` breakline chord at ITS STRETCH's cap, tightened
  by a governed non-taxi face it bounds (an apron lane is apron, RULINGS
  2026-09-03j; "reach follows centrelines": the profile an aircraft
  actually travels);
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
from ..law.tables import is_rigid_role, role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import View, view
from .routes import route_pairs, routes
from .stretches import edge_cap, pair_caps, stretches

__all__ = ["taxi_within_shape", "taxi_centerlines", "triangle_planes",
           "all_pairs", "pad_vertices", "plane_rows", "PricedPair",
           "taxi_pair_routes"]

GEN = "taxi"
_GRADIENT_DIRECTIONS = 16


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
    """One taxi-family within-shape pair: the face, the pair, the CHORD
    reading (``cap_chord × d_chord``, the census's plane rule) and the
    ROUTE reading (``dist`` / ``budget``, ``None`` when no route joins
    the two — the pair then has no row).  ``pad``: a pad endpoint."""

    face: int
    a: int
    b: int
    cap_chord: float
    d_chord: float
    dist: float | None
    budget: float | None
    pad: bool

    @property
    def routed(self) -> bool:
        return self.dist is not None


_PAIR_CACHE: dict[int, tuple[PlanarMap, Law, list[PricedPair]]] = {}


def taxi_pair_routes(planar: PlanarMap, law: Law, airport: Airport | None
                     ) -> list[PricedPair]:
    """Every taxi-family within-shape pair with its chord and route
    readings (module docstring; cached per map — the generator and the
    publication read one computation)."""
    hit = _PAIR_CACHE.get(id(planar))
    if hit is not None and hit[0] is planar and hit[1] is law:
        return hit[2]
    vw = view(planar, law)
    st = stretches(planar, law)
    members = law.tables.precedence.taxi_family.members
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    pads = pad_vertices(vw)
    mesh_roles = frozenset(law.tables.emit.within_shape.junction_mesh_roles)
    chord: list[tuple[int, int, int, float, float]] = []
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
                chord.append((f.id, a, b, c, d))
    table = route_pairs(routes(planar, law, airport), groups)
    out: list[PricedPair] = []
    for fid, a, b, c, d in chord:
        key = (a, b) if a < b else (b, a)
        hit_r = table.get(key)
        out.append(PricedPair(fid, a, b, c, d,
                              None if hit_r is None else hit_r[0],
                              None if hit_r is None else hit_r[1],
                              a in pads or b in pads))
    _PAIR_CACHE.clear()
    _PAIR_CACHE[id(planar)] = (planar, law, out)
    return out


def taxi_within_shape(planar: PlanarMap, law: Law, airport: Airport
                      ) -> list[Row]:
    """All pairs of every taxi-family ring, each priced over the centreline
    route (05ab); a pair no route joins has no row."""
    rows: list[Row] = []
    faces = planar.faces
    src_of: dict[tuple[int, bool], Source] = {}
    for pp in taxi_pair_routes(planar, law, airport):
        if not pp.routed:
            continue
        key = (pp.face, pp.pad)
        src = src_of.get(key)
        if src is None:
            f = faces[pp.face]
            src = Source(GEN, "rulesets.taxi.longitudinal within_shape over the "
                         "centreline route" + (" from the pad's contact" if pp.pad else "")
                         + " (2026-09-05ab)", (f"face:{f.id}", f.ref))
            src_of[key] = src
        rows.append(Diff(pp.a, pp.b, pp.budget / pp.dist, pp.dist, src))
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


def plane_rows(tri: _t.Sequence[int], xy: _t.Mapping[int, tuple[float, float]],
               cap: float, src: Source) -> list[Row]:
    """``|∇z| ≤ cap`` over one triangle as 16 half-plane ``Linear`` rows
    (module docstring); none for a degenerate triangle."""
    (x1, y1), (x2, y2), (x3, y3) = (xy[v] for v in tri)
    det = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
    if abs(det) < 1e-9:
        return []
    # ∇z = M · (z1, z2, z3): gx = Σ gi·zi, gy = Σ hi·zi (barycentric)
    gx = ((y2 - y3) / det, (y3 - y1) / det, (y1 - y2) / det)
    gy = ((x3 - x2) / det, (x1 - x3) / det, (x2 - x1) / det)
    bound = cap * math.cos(math.pi / _GRADIENT_DIRECTIONS)
    rows: list[Row] = []
    for k in range(_GRADIENT_DIRECTIONS):
        th = 2.0 * math.pi * k / _GRADIENT_DIRECTIONS
        c, s = math.cos(th), math.sin(th)
        terms = tuple((tri[i], c * gx[i] + s * gy[i]) for i in range(3))
        rows.append(Linear(terms, None, bound, src))
    return rows
