"""TAXIWAY STRETCHES (RULINGS 2026-09-04t-3): a taxiway's letter — its
cap — applies per STRETCH, from its centreline intersection with another
taxiway onward.  At CYXY taxiway G's 3 % begins at its intersection with
E (60.7079446, −135.0697651); the next G node (60.7078279, −135.0704243)
may already differ from the intersection by 3 % × 38 m.  Junction faces
carry the cap of the stretch(es) they belong to; strictest-of-chains
(04q-2) is superseded.

* A STRETCH is a ``taxi_centerline`` breakline split at every planar
  vertex where two taxi centrelines meet (a vertex on >= 2 such
  breaklines); the intersection vertex belongs to BOTH stretches.  Each
  stretch carries ITS chain's letter (``Breakline.code_letter``, threaded
  from the classifier's chain) and the taxi family's cap for it.
* A FACE the stretch bounds (an edge of the stretch has the face on a
  side) is crossed by it.  Inside a taxi-family face every vertex is
  assigned to the stretch(es) it lies ON, else to the NEAREST crossing
  stretch (perpendicular distance to the stretch polyline).
* PAIR PRICING (:func:`pair_caps`) — the stated choice: a pair is priced
  by the stretch BOTH its vertices lie on — that stretch's cap over their
  distance (the plane rule per stretch; the looser of several common
  stretches, the oracle's "looser of the shared centerlines" through the
  published axes).  Every other pair of the face — one or both vertices
  off the common stretch — holds the FACE's cap, the strictest crossing
  letter the classifier stamps (``roles._junction_letter``).  It is not a
  chord across letters because a cross-stretch pair is never priced at
  the looser letter: the relaxation lives exactly on the stretch whose
  letter it is.  NOT chosen: partitioning the face at the intersection's
  perpendicular or by nearest stretch, and composing cross-letter pairs
  along the travel path (Σ cap·len through the intersection) — measured
  on the twin fixture 2026-09-04, the v1 oracle (one letter per way, the
  junction-mesh body rule) read four rows at 1.9-2.0 % / cap 1.5 % on
  exactly the composed pairs; a single-letter oracle cannot read a body
  region, and publishing v2's per-pair budgets (``pair_caps``) would put
  the oracle on v2's population (its baked path floors every published
  pair at the way cap, un-tightening the frontage reading).  Oracle
  equality on the published population is the twin.
* A CENTRELINE CHORD (:func:`edge_cap`) holds its stretch's cap, tightened
  by any governed NON-taxi, NON-apron face it bounds (a runway slab, a
  road, a structure).  A ROUTE THROUGH AN APRON KEEPS THE TAXIWAY LAW
  (owner, RULINGS 2026-09-06t; spec ``apron-route-cap`` §2): an apron-
  family face never tightens a stretch edge — 09-03j's "1202 edges inside
  an apron are APRON" stands for the ROLE and is withdrawn for the CAP.
  The apron beside the route is ANISOTROPIC (spec author, RULINGS
  2026-09-06v; owner question 06v-1): within an apron face CROSSED by a
  stretch (an edge of the stretch on one of the face's rings,
  :func:`crossing_axes`) every priced pair is the BOX against the
  crossing axis nearest its midpoint — ``|Δz| ≤ cL_stretch·|Δs| +
  cA·|Δt|`` with the APRON cap across (``apron.apron_within_shape``;
  06s's :class:`AxisIndex` with the apron cap as its ``cT``).  The round-1
  corridor (a taxiway-half-width band) was REFUTED by arithmetic and is
  deleted: any apron vertex with d(P,A) + d(P,B) < 1.5·d(A,B) re-capped
  the route through its 1 % chords.
* JUNCTION BODIES (RULINGS 2026-09-04y, ``constraints.junction_mesh``): a
  junction face's pairs are its common-stretch pairs ONLY
  (``compose_pairs(common_only=True)``); a chord whose endpoints lie on
  stretches of DIFFERENT letters is not a law edge and produces no row.
  The body is priced by its triangle mesh, each mesh edge at the cap of
  the crossing stretch NEAREST its midpoint (:func:`nearest_line_cap`).

Pure over the planar map and the law; read by ``taxi``, ``transverse``,
``routes`` and (through :func:`compose_pairs`) the verify reader.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.tables import role_cap, role_family
from ..model.planar import PlanarMap
from .geometry import project_to_chain

__all__ = ["Stretch", "Stretches", "stretches", "edge_cap", "pair_caps",
           "compose_pairs", "nearest_line_cap", "AxisIndex", "crossing_axes",
           "APRON_ROLE"]

#: THE APRON the route passes through (RULINGS 2026-09-06t): the emitted
#: ``apron`` role — the tables register it in the ``common`` family (the
#: spec's ``role_family == "apron"`` names no table family); a pad
#: (``building``) is rigid and no route passes through it.
APRON_ROLE = "apron"

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class Stretch:
    """One constant-letter run of a taxi centreline between intersections."""

    id: int
    breakline: int
    ref: str
    code_letter: str | None
    cap_l: float
    cap_t: float
    vertices: tuple[int, ...]
    edges: tuple[int, ...]


@_dc.dataclass(frozen=True)
class Stretches:
    """Every stretch of one planar map plus the joins the generators read."""

    items: tuple[Stretch, ...]
    on: dict[int, tuple[int, ...]]              # vertex -> stretches it lies on
    by_edge: dict[int, int]                     # centreline edge -> stretch
    face_stretches: dict[int, tuple[int, ...]]  # face -> stretches bounding it
    intersections: frozenset[int]               # vertices where stretches meet

    def cap(self, sid: int) -> float:
        return self.items[sid].cap_l


_CACHE: dict[int, tuple[PlanarMap, Law, Stretches]] = {}


def _taxi_cap(law: Law, letter: str | None) -> tuple[float, float]:
    """The taxi family's ``(longitudinal, transverse)`` cap for a letter
    (``rulesets.<authority>.taxi``; the default when unlettered)."""
    role = law.tables.precedence.taxi_family.members[0]
    rc = role_cap(law, role, None, letter)
    if rc is None:                          # a taxi family with no cap table
        raise ValueError("the taxi family carries no longitudinal cap")
    return rc.longitudinal, rc.transverse


def build_stretches(pm: PlanarMap, law: Law) -> Stretches:
    """Split every taxi centreline at the vertices it shares with another
    taxi centreline (module docstring)."""
    chains: dict[int, tuple[int, ...]] = {}
    count: dict[int, int] = {}
    for bid, b in pm.breaklines.items():
        if b.kind != "taxi_centerline":
            continue
        ch = b.vertices(pm)
        chains[bid] = ch
        for v in set(ch):
            count[v] = count.get(v, 0) + 1
    inter = frozenset(v for v, n in count.items() if n >= 2)
    items: list[Stretch] = []
    on: dict[int, list[int]] = {}
    by_edge: dict[int, int] = {}
    faces: dict[int, list[int]] = {}
    for bid, ch in chains.items():
        b = pm.breaklines[bid]
        cap_l, cap_t = _taxi_cap(law, b.code_letter)
        cuts = [0] + [k for k in range(1, len(ch) - 1) if ch[k] in inter] + [len(ch) - 1]
        for k0, k1 in zip(cuts, cuts[1:]):
            vs = ch[k0:k1 + 1]
            es = b.edges[k0:k1]
            if len(vs) < 2:
                continue
            sid = len(items)
            items.append(Stretch(sid, bid, b.ref, b.code_letter, cap_l, cap_t, vs, es))
            for v in vs:
                on.setdefault(v, []).append(sid)
            for eid in es:
                by_edge[eid] = sid
                e = pm.edges[eid]
                for f in (e.left_face, e.right_face):
                    if f is not None:
                        lst = faces.setdefault(f, [])
                        if sid not in lst:
                            lst.append(sid)
    return Stretches(tuple(items), {v: tuple(s) for v, s in on.items()}, by_edge,
                     {f: tuple(s) for f, s in faces.items()}, inter)


def stretches(pm: PlanarMap, law: Law) -> Stretches:
    """The (cached) stretches of ``pm`` under ``law``."""
    hit = _CACHE.get(id(pm))
    if hit is not None and hit[0] is pm and hit[1] is law:
        return hit[2]
    st = build_stretches(pm, law)
    _CACHE.clear()
    _CACHE[id(pm)] = (pm, law, st)
    return st


def edge_cap(pm: PlanarMap, law: Law, st: Stretches, eid: int,
             face_caps: _t.Mapping[int, tuple[float, float] | None]
             ) -> tuple[float, float] | None:
    """A centreline edge's ``(cL, cT)``: its stretch's cap, tightened by
    every governed non-taxi, NON-APRON face it bounds (a route through an
    apron keeps the taxiway law, RULINGS 2026-09-06t); an edge on no
    stretch (a road centreline, a plain edge) reads the strictest
    bounding face, apron included."""
    e = pm.edges[eid]
    sid = st.by_edge.get(eid)
    bounding = [(f, face_caps.get(f)) for f in (e.left_face, e.right_face)
                if f is not None and face_caps.get(f) is not None]
    if sid is None:
        if not bounding:
            return None
        return min((c for _f, c in bounding), key=lambda c: c[0])
    s = st.items[sid]
    cl, ct = s.cap_l, s.cap_t
    for f, c in bounding:
        role = pm.faces[f].role
        if role != APRON_ROLE and role_family(law, role) != "taxi":
            cl, ct = min(cl, c[0]), min(ct, c[1])
    return cl, ct


def compose_pairs(xy: _t.Mapping[int, XY], verts: _t.Sequence[int],
                  lines: _t.Sequence[tuple[_t.Sequence[int], float]],
                  base_cap: float, min_d: float, common_only: bool = False
                  ) -> list[tuple[int, int, float, float]]:
    """THE PER-STRETCH PAIR LAW over one face (module docstring), pure:
    ``verts`` the face's vertices, ``lines`` the stretches crossing it as
    ``(vertex chain, cap)``, ``base_cap`` the face's own cap.  Returns
    ``(a, b, cap, d)`` for every distinct pair: the looser common
    stretch's cap when both lie on one, else ``base_cap``.  With
    ``common_only`` (a JUNCTION body, RULINGS 2026-09-04y) only the pairs
    sharing a stretch are returned — every other chord is no law edge."""
    on: dict[int, list[float]] = {}
    for k, (ch, c) in enumerate(lines):
        for v in ch:
            on.setdefault(v, []).append((k, float(c)))  # type: ignore[arg-type]
    out: list[tuple[int, int, float, float]] = []
    n = len(verts)
    for i in range(n):
        a = verts[i]
        sa = on.get(a)
        for j in range(i + 1, n):
            b = verts[j]
            d = math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
            if d < min_d:
                continue
            cap = base_cap
            common: list[float] = []
            if sa:
                sb = on.get(b)
                if sb:
                    ks = {k for k, _c in sb}
                    common = [c for k, c in sa if k in ks]
                    if common:
                        cap = max(base_cap, max(common))
            if common_only and not common:
                continue
            out.append((a, b, cap, d))
    return out


def nearest_line_cap(p: XY, lines: _t.Sequence[tuple[_t.Sequence[XY], float]],
                     base_cap: float, tie_m: float = 1e-6) -> float:
    """THE NEAREST-STRETCH CAP (RULINGS 2026-09-04y): the cap of the line
    (a stretch's polyline in metres, with its cap) nearest to ``p`` by
    perpendicular distance; the STRICTEST cap among lines tied within
    ``tie_m``; ``base_cap`` when there is no line.  Pure — the verify
    reader and the v1 oracle apply the same rule to the same lines."""
    best_d = float("inf")
    best_cap = base_cap
    for pts, cap in lines:
        if len(pts) < 2:
            continue
        d = project_to_chain(p, pts)[0]
        if d < best_d - tie_m:
            best_d, best_cap = d, float(cap)
        elif abs(d - best_d) <= tie_m:
            best_cap = min(best_cap, float(cap))
    return best_cap


def pair_caps(pm: PlanarMap, law: Law, st: Stretches, fid: int,
              verts: _t.Sequence[int], base_cap: float, min_d: float,
              common_only: bool = False
              ) -> list[tuple[int, int, float, float]]:
    """:func:`compose_pairs` for face ``fid`` with its crossing stretches."""
    xy = {v: pm.vertices[v].xy for v in verts}
    lines: list[tuple[_t.Sequence[int], float]] = []
    for sid in st.face_stretches.get(fid, ()):
        s = st.items[sid]
        for v in s.vertices:
            xy.setdefault(v, pm.vertices[v].xy)
        lines.append((s.vertices, s.cap_l))
    return compose_pairs(xy, verts, lines, base_cap, min_d, common_only)


def crossing_axes(xy: _t.Mapping[int, XY], rings: _t.Iterable[_t.Sequence[int]],
                  chains: _t.Iterable[tuple[_t.Sequence[int], float, float]]
                  ) -> list[tuple[list[XY], float, float]]:
    """THE STRETCHES CROSSING ONE FACE (RULINGS 2026-09-06v; spec ``apron-
    route-cap`` §3 amended), pure: of ``chains`` — ``(vertex chain, cL,
    cap across)`` — those with an EDGE ON one of the face's ``rings``
    (two consecutive chain vertices both vertices of that ring: the
    stretch bounds the face there), as :class:`AxisIndex` axes ``(points,
    cL, cap across)``; empty when no stretch crosses.  The generator
    (``apron.apron_within_shape``), the verify reader
    (``verify/within.py``) and — on node ids — the v1 oracle
    (``check_grade._StretchBox``) share this one definition."""
    on: set[int] = set()
    for ring in rings:
        on.update(ring)
    out = []
    for chain, cl, ca in chains:
        if len(chain) >= 2 and any(u in on and w in on for u, w in zip(chain, chain[1:])):
            out.append(([xy[v] for v in chain], cl, ca))
    return out


class AxisIndex:
    """THE NEAREST STRETCH AXIS, grid-indexed (RULINGS 2026-09-06s; the
    generator's and the verify reader's one locator, the shape of the v1
    oracle's ``check_grade._StretchBox``): every stretch as
    ``(polyline m, cap_l, cap_t)``, its segments binned in ``cell``-sized
    squares; :meth:`nearest` returns the unit direction and the caps of
    the segment nearest a point, searching the point's cell and its
    neighbours first and, when they hold no segment, the WHOLE index —
    every point on a map with a stretch has a serving axis (the oracle
    tallied such pairs ``no_axis`` and read the chord; the ruling prices
    the nearest axis).  The strictest longitudinal cap wins a tie.  An
    apron face crossed by a stretch (RULINGS 2026-09-06v) builds one from
    its crossing stretches with the APRON cap as ``cT``
    (:func:`crossing_axes`)."""

    def __init__(self, axes: _t.Iterable[tuple[_t.Sequence[XY], float, float]],
                 cell: float, tie_m: float = 1e-6) -> None:
        self.cell = float(cell)
        self.tie_m = tie_m
        self.segs: list[tuple[float, float, float, float, float, float, float]] = []
        self.grid: dict[tuple[int, int], list[int]] = {}
        for pts, cap_l, cap_t in axes:
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                ln = math.hypot(bx - ax, by - ay)
                if ln <= 0.0:
                    continue
                k = len(self.segs)
                self.segs.append((ax, ay, (bx - ax) / ln, (by - ay) / ln, ln,
                                  float(cap_l), float(cap_t)))
                for gx in range(int(min(ax, bx) // self.cell), int(max(ax, bx) // self.cell) + 1):
                    for gy in range(int(min(ay, by) // self.cell), int(max(ay, by) // self.cell) + 1):
                        self.grid.setdefault((gx, gy), []).append(k)

    def __bool__(self) -> bool:
        return bool(self.segs)

    def _best(self, x: float, y: float, ks: _t.Iterable[int]
              ) -> tuple[float, float, float, float, float] | None:
        best = None
        for k in ks:
            ax, ay, ux, uy, ln, cl, ct = self.segs[k]
            t = max(0.0, min(ln, (x - ax) * ux + (y - ay) * uy))
            d = math.hypot(x - (ax + t * ux), y - (ay + t * uy))
            if best is None or d < best[0] - self.tie_m or \
                    (abs(d - best[0]) <= self.tie_m and cl < best[3]):
                best = (d, ux, uy, cl, ct)
        return best

    def _block(self, x: float, y: float) -> tuple[list[int], float]:
        """The 3x3 grid block's segments around ``(x, y)`` and the
        GUARANTEED RADIUS: a segment outside the block can be nearer than
        the block's best only beyond the point's distance to the block's
        edge (measured HECA pav129 2026-09-06: a 63 m segment binned into
        a neighbour cell by its bounding box beat the true nearest at
        44.7 m)."""
        cx, cy = int(x // self.cell), int(y // self.cell)
        ks: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                ks.extend(self.grid.get((cx + dx, cy + dy), ()))
        reach = min(x - (cx - 1) * self.cell, (cx + 2) * self.cell - x,
                    y - (cy - 1) * self.cell, (cy + 2) * self.cell - y)
        return ks, reach

    def _tied(self, x: float, y: float, d0: float) -> list[tuple[float, float, float, float]]:
        """Every segment at the nearest distance ``d0`` (within ``tie_m``):
        the point projects onto a polyline CORNER shared by two segments,
        or onto an intersection of two stretches — as ``(ux, uy, cl, ct)``."""
        out = []
        for ax, ay, ux, uy, ln, cl, ct in self.segs:
            t = max(0.0, min(ln, (x - ax) * ux + (y - ay) * uy))
            if abs(math.hypot(x - (ax + t * ux), y - (ay + t * uy)) - d0) <= self.tie_m:
                out.append((ux, uy, cl, ct))
        return out

    def nearest(self, x: float, y: float
                ) -> tuple[tuple[float, float], float, float] | None:
        """``((ux, uy), cap_l, cap_t)`` of the serving axis at ``(x, y)``,
        ``None`` only on an index with no segment."""
        hit = self._nearest(x, y)
        return None if hit is None else hit[1:]

    def _nearest(self, x: float, y: float
                 ) -> tuple[float, tuple[float, float], float, float] | None:
        if not self.segs:
            return None
        ks, reach = self._block(x, y)
        best = self._best(x, y, ks) if ks else None
        if best is None or best[0] > reach:
            best = self._best(x, y, range(len(self.segs)))
        if best is None:
            return None
        d, ux, uy, cl, ct = best
        return d, (ux, uy), cl, ct

    def box_bound(self, xa: float, ya: float, xb: float, yb: float
                  ) -> tuple[float, float, float] | None:
        """THE BOX of one pair (RULINGS 2026-09-06s): ``(bound_m, cap_l,
        cap_t)`` with ``bound = cap_l·|Δs| + cap_t·|Δt|`` against the axis
        serving the pair's midpoint; ``None`` with no axis.  A TIE — the
        midpoint projects onto a corner of the polyline (two segments at
        one distance) or onto two stretches' intersection — takes the
        STRICTEST bound among the tied axes: the tie set is the same in
        every frame, the winner of an exact tie is not (measured HECA
        pav129 2026-09-06: the generator's frame and the census's picked
        the two segments of taxi25 meeting at the corner 44.7 m away,
        and three built pairs read 0.03 m over the reader's box)."""
        x, y = 0.5 * (xa + xb), 0.5 * (ya + yb)
        hit = self._nearest(x, y)
        if hit is None:
            return None
        d0, (ux, uy), cl, ct = hit
        dx, dy = xb - xa, yb - ya
        best = (cl * abs(dx * ux + dy * uy) + ct * abs(dx * uy - dy * ux), cl, ct)
        for ux, uy, cl, ct in self._tied(x, y, d0):
            b = cl * abs(dx * ux + dy * uy) + ct * abs(dx * uy - dy * ux)
            if b < best[0]:
                best = (b, cl, ct)
        return best
