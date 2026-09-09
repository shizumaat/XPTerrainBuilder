"""THE DESIGN SURFACE's ROWS — the pieces ``solve/design.py`` assembles its
one least-squares problem from (owner RULINGS 2026-09-08t; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §1): the REDUCTION (pins
fix a vertex, a rigid ``Flat`` group is one column, the terrain beyond the
zone's outer ring is the DEM), the pavement TRIANGULATION and its cotangent
Laplacian (the bending operator), the weighted ROW accumulator, the law rows
as ONE-SIDED targets, the ZONE RAMP, and the connected-sheet / body / plane
readings the body datums need.

Split from ``design.py`` under the 1,000-line file law (M0 §1); it imports
``law`` and ``model`` only, never a generator.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import scipy.sparse as sp

from ..law import Law
from ..law.tables import zone2_half_width_m
from ..model.constraints import ConstraintSet, Row
from ..model.planar import PlanarMap

__all__ = ["_Reduction", "_reduce", "_face_triangles", "_cotangent_laplacian",
           "_Rows", "_Side", "_law_sides", "_violation", "_zone_weights",
           "_one_matrix", "_sheet_components", "_role_bodies", "_plane_targets"]


# ── the reduction: pins fix, flats merge ────────────────────────────────

class _Reduction:
    """Vertex -> column, or a fixed value.  A ``Flat`` group is ONE column
    (the group is one rigid value, 09-01c); a ``Pin`` fixes it."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.fixed: dict[int, float] = {}
        #: the vertices fixed because they lie BEYOND the zone's outer ring —
        #: they ARE the terrain (08t answer 3), not a law's own value
        self.dem_fixed: set[int] = set()
        self.col = np.full(n, -1, dtype=np.int64)
        self.value = np.zeros(n)
        self.n_cols = 0

    def find(self, v: int) -> int:
        p = self.parent
        while p[v] != v:
            p[v] = p[p[v]]
            v = p[v]
        return v

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def finish(self) -> None:
        """Roots first: a root carrying a fixed value fixes its class."""
        n = len(self.parent)
        root_fixed: dict[int, float] = {}
        for v, z in self.fixed.items():
            root_fixed.setdefault(self.find(v), z)
        root_col: dict[int, int] = {}
        for v in range(n):
            r = self.find(v)
            if r in root_fixed:
                self.value[v] = root_fixed[r]
                continue
            c = root_col.get(r)
            if c is None:
                c = root_col[r] = self.n_cols
                self.n_cols += 1
            self.col[v] = c


def _reduce(pm: PlanarMap, cs: ConstraintSet, fixed_dem: _t.Mapping[int, float]
            ) -> _Reduction:
    red = _Reduction(len(pm.vertices))
    for f in cs.flats:
        g = f.group
        for v in g[1:]:
            red.union(g[0], v)
    for v, z in fixed_dem.items():
        red.fixed[v] = float(z)
        red.dem_fixed.add(v)
    for p in cs.pins:                       # a pin outranks a DEM fixing
        red.fixed[p.v] = float(p.z)
        red.dem_fixed.discard(p.v)
    red.finish()
    return red


# ── the geometry: triangulation and the cotangent Laplacian ─────────────

def _face_triangles(pm: PlanarMap, fid: int) -> list[tuple[int, int, int]]:
    """A triangulation of one face: the Delaunay triangulation of its ring
    and hole vertices, keeping the triangles whose centroid lies inside the
    face (so a concave face and a face with holes triangulate correctly)."""
    from scipy.spatial import Delaunay, QhullError
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    f = pm.faces[fid]
    ring = pm.ring_vertices(f.ring)
    holes = [pm.ring_vertices(h) for h in f.holes]
    ids = list(dict.fromkeys([*ring, *(v for h in holes for v in h)]))
    if len(ids) < 3:
        return []
    pts = np.array([pm.vertices[v].xy for v in ids], float)
    try:
        poly = Polygon([pm.vertices[v].xy for v in ring],
                       [[pm.vertices[v].xy for v in h] for h in holes if len(h) >= 3])
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return []
        tri = Delaunay(pts)
    except (QhullError, ValueError):
        return []
    inside = prep(poly)
    from shapely.geometry import Point
    out: list[tuple[int, int, int]] = []
    for s in tri.simplices:
        c = pts[s].mean(axis=0)
        if inside.contains(Point(c[0], c[1])):
            out.append((ids[s[0]], ids[s[1]], ids[s[2]]))
    return out


def _cotangent_laplacian(pm: PlanarMap, tris: _t.Sequence[tuple[int, int, int]],
                         n: int) -> tuple[sp.csr_matrix, np.ndarray]:
    """The assembled cotangent Laplacian over ``tris`` and the barycentric
    vertex areas.  A row is ``Σ_j w_ij (z_i − z_j)`` — metres of integrated
    curvature; the caller scales it by ``1/√area`` so the energy is the
    thin-plate one and mesh-density independent."""
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    area = np.zeros(n)
    for a, b, c in tris:
        pa, pb, pc = (np.asarray(pm.vertices[v].xy, float) for v in (a, b, c))
        ab, bc, ca = pb - pa, pc - pb, pa - pc
        cross = abs(ab[0] * (-ca[1]) - ab[1] * (-ca[0])) * 0.5
        if cross <= 0.0:
            continue
        area[[a, b, c]] += cross / 3.0
        # cot of the angle OPPOSITE each edge = (u·v) / (2 * area)
        for (i, j, u, v) in ((a, b, -ca, bc), (b, c, ab, -ca), (c, a, bc, ab)):
            w = float(u @ v) / (4.0 * cross)
            if w <= 0.0:
                continue                    # obtuse: clamp (keeps the operator PSD)
            rows += [i, i, j, j]
            cols += [i, j, j, i]
            vals += [w, -w, w, -w]
    L = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    return L, area


# ── the objective's rows ────────────────────────────────────────────────

@_dc.dataclass
class _Rows:
    """Accumulates weighted rows ``√w · (Σ c z − b)`` over the REDUCED
    columns; a fixed vertex's contribution moves to the right-hand side."""

    red: _Reduction
    r: list[int] = _dc.field(default_factory=list)
    c: list[int] = _dc.field(default_factory=list)
    v: list[float] = _dc.field(default_factory=list)
    b: list[float] = _dc.field(default_factory=list)
    owner: list[_t.Any] = _dc.field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.b)

    def add(self, terms: _t.Sequence[tuple[int, float]], rhs: float, w: float,
            owner: _t.Any = None) -> bool:
        """One row; ``False`` when every term is fixed (nothing to solve)."""
        s = math.sqrt(w)
        k = self.n
        acc: dict[int, float] = {}
        for vid, coef in terms:
            col = int(self.red.col[vid])
            if col < 0:
                rhs -= coef * float(self.red.value[vid])
            else:
                acc[col] = acc.get(col, 0.0) + coef
        acc = {k2: v2 for k2, v2 in acc.items() if v2 != 0.0}
        if not acc:
            return False
        for col, coef in acc.items():
            self.r.append(k)
            self.c.append(col)
            self.v.append(s * coef)
        self.b.append(s * rhs)
        self.owner.append(owner)
        return True

    def matrix(self, ncol: int) -> tuple[sp.csr_matrix, np.ndarray]:
        A = sp.csr_matrix((self.v, (self.r, self.c)), shape=(self.n, ncol))
        return A, np.asarray(self.b, float)


#: One law row's one-sided target: ``Σ c z ≤ hi`` (a violation is positive).
_Side = tuple[tuple[tuple[int, float], ...], float, Row]


def _law_sides(cs: ConstraintSet) -> tuple[list[_Side], list[_Side]]:
    """Every law row as ONE-SIDED targets ``Σ c z ≤ hi``, plus the rows the
    law states as equalities (``lo == hi``), which are two-sided targets."""
    one: list[_Side] = []
    eq: list[_Side] = []
    for d in cs.diffs:
        bound = d.cap * d.d
        one.append((((d.a, 1.0), (d.b, -1.0)), bound, d))
        one.append((((d.b, 1.0), (d.a, -1.0)), bound, d))
    for o in cs.offsets:
        one.append((((o.b, 1.0), (o.a, -1.0)), -o.min_delta, o))
    for ln in cs.linears:
        if ln.lo is not None and ln.hi is not None and ln.lo == ln.hi:
            eq.append((tuple(ln.terms), float(ln.hi), ln))
            continue
        if ln.hi is not None:
            one.append((tuple(ln.terms), float(ln.hi), ln))
        if ln.lo is not None:
            one.append((tuple((v, -c) for v, c in ln.terms), -float(ln.lo), ln))
    for bd in cs.bands:
        if bd.hi is not None:
            one.append((((bd.v, 1.0),), float(bd.hi), bd))
        if bd.lo is not None:
            one.append((((bd.v, -1.0),), -float(bd.lo), bd))
    return one, eq


def _violation(side: _Side, z: np.ndarray) -> float:
    terms, hi, _row = side
    return sum(c * float(z[v]) for v, c in terms) - hi


# ── the zone ramp ───────────────────────────────────────────────────────

def _zone_weights(pm: PlanarMap, law: Law, pav: _t.AbstractSet[int],
                  free: _t.AbstractSet[int]
                  ) -> tuple[dict[int, float], dict[int, float]]:
    """``(ramp, beyond)``: for every vertex OUTSIDE the pavement, its DEM-fit
    ramp factor — 0 at the pavement edge, 1 at the zone's outer ring — by
    graph distance (metres) along the planar map from the pavement,
    normalised by the zone-2 half width THAT pavement's own class states
    (``law.tables.zone2_half_width_m``: a runway's strip is wide, a
    taxiway's narrow, and each blends over its own width — 08t answer 3);
    ``beyond`` holds the vertices past the outer ring, which ARE the DEM
    (fixed, never unknowns) — ``free`` (the road chains and the structures,
    which carry their own law far from any pavement) is never fixed."""
    import heapq
    width_of: dict[int, float] = {}
    for f in pm.faces.values():
        w = zone2_half_width_m(law, f.role, f.code_number, f.code_letter)
        if not w:
            continue
        for ring in (f.ring, *f.holes):
            for v in pm.ring_vertices(ring):
                if v in pav:
                    width_of[v] = max(width_of.get(v, 0.0), float(w))
    if not width_of:
        return {}, {}
    widest = max(width_of.values())
    adj: dict[int, list[tuple[int, float]]] = {}
    for e in pm.edges.values():
        (ax, ay), (bx, by) = pm.vertices[e.a].xy, pm.vertices[e.b].xy
        d = math.hypot(bx - ax, by - ay)
        adj.setdefault(e.a, []).append((e.b, d))
        adj.setdefault(e.b, []).append((e.a, d))
    # the state a vertex reaches is (distance, the source's own zone width):
    # the SMALLEST fraction wins — a vertex 20 m from a taxiway and 20 m from
    # a runway blends over the runway's wider zone (the pocket rule's spirit)
    best: dict[int, tuple[float, float]] = {}
    heap: list[tuple[float, int, float]] = []
    for v, w in width_of.items():
        best[v] = (0.0, w)
        heap.append((0.0, v, w))
    heapq.heapify(heap)
    while heap:
        frac, v, w = heapq.heappop(heap)
        cur = best.get(v)
        if cur is None or frac > cur[0] / cur[1] + 1e-12:
            continue
        d0 = frac * w
        for nb, step in adj.get(v, ()):
            nd = d0 + step
            if nd > w:
                continue
            nf = nd / w
            prev = best.get(nb)
            if prev is None or nf < prev[0] / prev[1] - 1e-12:
                best[nb] = (nd, w)
                heapq.heappush(heap, (nf, nb, w))
    ramp: dict[int, float] = {}
    beyond: dict[int, float] = {}
    for vid, vx in pm.vertices.items():
        if vid in pav:
            continue
        rec = best.get(vid)
        if rec is None:
            if vid not in free and vx.dem_z is not None:
                beyond[vid] = float(vx.dem_z)
        else:
            ramp[vid] = min(1.0, rec[0] / rec[1])
    del widest
    return ramp, beyond



def _one_matrix(one: _t.Sequence[_Side], red: _Reduction
                ) -> tuple[sp.csr_matrix, np.ndarray]:
    """Every one-sided law target as ONE sparse matrix over the REDUCED
    columns, with the fixed vertices' contribution folded into the
    right-hand side: a row's violation is ``(A1 x − b1)_k``.  Stacked once
    so the active set costs a row slice, not a re-assembly."""
    r: list[int] = []
    c: list[int] = []
    v: list[float] = []
    b = np.zeros(len(one))
    for k, (terms, hi, _row) in enumerate(one):
        rhs = float(hi)
        acc: dict[int, float] = {}
        for vid, coef in terms:
            col = int(red.col[vid])
            if col < 0:
                rhs -= coef * float(red.value[vid])
            else:
                acc[col] = acc.get(col, 0.0) + coef
        for col, coef in acc.items():
            if coef == 0.0:
                continue
            r.append(k)
            c.append(col)
            v.append(coef)
        b[k] = rhs
    return sp.csr_matrix((v, (r, c)), shape=(len(one), red.n_cols)), b



def _sheet_components(tris: _t.Sequence[tuple[int, int, int]],
                      red: _Reduction) -> dict[int, int]:
    """Column -> its CONNECTED SHEET (triangles sharing a vertex, over the
    reduced columns).  A column no triangle reaches is its own sheet: a
    structure's ring, a lone road station."""
    parent: dict[int, int] = {c: c for c in range(red.n_cols)}

    def find(v: int) -> int:
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b, c in tris:
        cols = [int(red.col[v]) for v in (a, b, c) if red.col[v] >= 0]
        if len(cols) < 2:
            continue
        ra = find(cols[0])
        for other in cols[1:]:
            parent[find(other)] = ra
    return {c: find(c) for c in range(red.n_cols)}


def _role_bodies(pm: PlanarMap, roles: _t.AbstractSet[str], red: _Reduction
                 ) -> list[list[int]]:
    """The connected BODIES of the faces of ``roles`` (faces sharing a
    vertex), each as its unknown vertices carrying a DEM sample."""
    parent: dict[int, int] = {}

    def find(v: int) -> int:
        parent.setdefault(v, v)
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    members: dict[int, list[int]] = {}
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        vs = [v for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)]
        if not vs:
            continue
        r0 = find(vs[0])
        for v in vs[1:]:
            parent[find(v)] = r0
        members.setdefault(f.id, []).extend(vs)
    acc: dict[int, set[int]] = {}
    for vs in members.values():
        for v in vs:
            acc.setdefault(find(v), set()).add(v)
    out: list[list[int]] = []
    for group in acc.values():
        keep = sorted(v for v in group
                      if red.col[v] >= 0 and pm.vertices[v].dem_z is not None)
        if keep:
            out.append(keep)
    return out


def _plane_targets(pm: PlanarMap, vs: _t.Sequence[int]
                   ) -> list[tuple[int, float]]:
    """``(vertex, target)`` for a detached sheet's OWN TERRAIN PLANE: the
    least-squares plane through its DEM samples, evaluated at each vertex.
    Mean and tilt, no undulation — a plane's bending energy is zero, so this
    datum never fights the design (owner 08t answer 6)."""
    if not vs:
        return []
    P = np.array([[*pm.vertices[v].xy, 1.0] for v in vs], float)
    y = np.array([float(pm.vertices[v].dem_z) for v in vs], float)
    if len(vs) < 3:
        return [(v, float(y.mean())) for v in vs]
    try:
        coef, *_ = np.linalg.lstsq(P, y, rcond=None)
    except np.linalg.LinAlgError:
        return [(v, float(y.mean())) for v in vs]
    fit = P @ coef
    return [(v, float(fit[k])) for k, v in enumerate(vs)]
