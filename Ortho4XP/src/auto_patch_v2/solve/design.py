"""THE DESIGN SURFACE — ONE sparse least-squares solve (owner RULINGS
2026-09-08t; spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §1-§3).

Pavement is a DESIGNED surface: minimum curvature, unbounded cut and fill,
flush and tangent at every contact, the DEM a datum only, every law a
TARGET.  One convex quadratic program, no tiers, no IIS, no relaxation, no
yield groups — those are deleted.

    minimise  w_bend  ‖ L z ‖²          thin-plate bending over each connected
                                        pavement complex (the cotangent
                                        Laplacian of its faces' triangulation:
                                        bending is minimised in EVERY direction
                                        and tangency holds across shared edges)
            + w_chord ‖ z − chord ‖²    the runway's threshold chord per ridge
                                        station (``constraints/runway_chord.py``,
                                        published through ``preferred_z``)
            + w_law   ‖ max(0, viol) ‖² every law row of every generator as a
                                        ONE-SIDED quadratic penalty
            + w_dem   ‖ z − DEM ‖²      ONLY on zone vertices, ramped 0 at the
                                        pavement edge to 1 at the outer ring
            + w_road  ‖ L_chain z ‖²    road chains' own bending
            + w_det   ‖ z − DEM ‖²      a component with no datum at all
    subject to  Pin  → the vertex is FIXED (eliminated from the unknowns)
                Flat → the group is ONE unknown (merged)
                beyond the zone's outer ring the vertex IS the DEM (fixed)

The one-sided penalties are met by an ACTIVE SET iteration (a semismooth
Newton step): solve, take the rows the surface violates, re-solve with those
rows active, to a fixed point of the set.  Every weight and limit is a law
value (``law/emit.toml [design]``, ``law/design_schema.py``).

Joints (08k/08r-2) carry no bending term and no row: the shape stage split
their vertices and dropped their rows before the set reached here, so the
components below simply do not touch.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import cg, lsqr, splu

from ..law import Law
from ..law.tables import (design as design_law, is_structure_role, is_value_role,
                          role_side, zone2_half_width_m, zone_class)
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear, Offset,
                                 Pin, Row)
from ..model.planar import PlanarMap
from .api import Options, Residual, Solution, Status

__all__ = ["DesignReport", "Base", "assemble", "solve_design", "residual",
           "bend_roles", "pavement_roles",
           "METHODS", "DEFAULT_METHOD"]

#: The linear solvers the round may use.  ``normal`` factorises the normal
#: equations Aᵀ A once per active set (sparse LU); ``cg`` runs conjugate
#: gradients on them (Jacobi-preconditioned); ``lsqr`` runs on A itself.
#: The lane measured all three on CYXY and HECA captures (spec §5).
METHODS: tuple[str, ...] = ("normal", "cg", "lsqr")
DEFAULT_METHOD = "normal"

#: The backtracking line search's smallest step (a numeric floor of the
#: solver, not a law value): below it the Newton direction buys nothing and
#: the previous point IS the minimiser.
_ALPHA_FLOOR = 1.0e-6


def bend_roles(law: Law) -> tuple[str, ...]:
    """The roles whose faces form the SHEETS the bending term shapes: every
    role that is not a STRUCTURE's own surface — the pavement AND the
    graded strip / clearance ground around it, because the blend from the
    design level to the natural terrain happens INSIDE those zones (owner
    08t answer 3) and a blend with no bending term is not a blend."""
    return tuple(r for r in law.tables.precedence.roles
                 if not is_structure_role(law, r))


def pavement_roles(law: Law) -> tuple[str, ...]:
    """The DESIGNED surface itself — every VALUE role that is not a
    structure: the zone ramp measures its distance from here, and a vertex
    of one of these faces never takes a DEM fit (08t answer 1)."""
    return tuple(r for r in law.tables.precedence.roles
                 if is_value_role(law, r) and not is_structure_role(law, r))


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


# ── the report ──────────────────────────────────────────────────────────

@_dc.dataclass
class DesignReport:
    """The residual per family and per objective term — what ``law_tiers``
    used to be, read the design surface's way: a law is a TARGET, so a
    missed target is a residual, never a demotion."""

    rounds: int = 0
    converged: bool = False
    method: str = DEFAULT_METHOD
    unknowns: int = 0
    fixed: int = 0
    rows: int = 0
    triangles: int = 0
    components: int = 0
    detached: int = 0
    #: law rows whose one foot is the terrain beyond the zone's outer ring:
    #: the BANK (08t answers 2/3) — reported, never a design target
    bank_rows: int = 0
    solver_wall_s: float = 0.0
    families: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    terms: dict[str, float] = _dc.field(default_factory=dict)

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rounds": self.rounds, "converged": self.converged,
                "method": self.method, "unknowns": self.unknowns,
                "fixed": self.fixed, "rows": self.rows,
                "triangles": self.triangles, "components": self.components,
                "detached": self.detached, "bank_rows": self.bank_rows,
                "solver_wall_s": round(self.solver_wall_s, 3),
                "families": self.families, "terms": self.terms}

    def line(self) -> str:
        worst = sorted(self.families.items(), key=lambda kv: -kv[1]["max_m"])[:6]
        return (f"design (08t): {self.rounds} active-set round(s)"
                f"{'' if self.converged else ' (SET NOT SETTLED)'}, {self.method}, "
                f"{self.unknowns} unknowns / {self.fixed} fixed, {self.rows} rows, "
                f"{self.triangles} triangles in {self.components} complexes "
                f"({self.detached} detached), {self.bank_rows} bank rows off the "
                f"terrain edge, {self.solver_wall_s:.2f} s solver; "
                "worst targets " + ", ".join(
                    f"{k} {v['missed']}/{v['rows']} max {v['max_m']:.3f} m"
                    for k, v in worst if v["missed"]))


def residual(cs: ConstraintSet, z: np.ndarray, objective: float) -> Residual:
    """The certificate: the worst residual of each row kind at ``z`` — the
    same reading the LP's certificate carried, now of TARGETS."""
    mp = md = mf = mb = mo = 0.0
    for p in cs.pins:
        mp = max(mp, abs(float(z[p.v]) - p.z))
    for d in cs.diffs:
        md = max(md, abs(float(z[d.a]) - float(z[d.b])) - d.cap * d.d)
    for f in cs.flats:
        g = z[list(f.group)]
        mf = max(mf, float(g.max() - g.min()))
    for bd in cs.bands:
        if bd.lo is not None:
            mb = max(mb, bd.lo - float(z[bd.v]))
        if bd.hi is not None:
            mb = max(mb, float(z[bd.v]) - bd.hi)
    for o in cs.offsets:
        mo = max(mo, o.min_delta - (float(z[o.a]) - float(z[o.b])))
    ml = 0.0
    for ln in cs.linears:
        s = sum(c * float(z[v]) for v, c in ln.terms)
        if ln.hi is not None:
            ml = max(ml, s - ln.hi)
        if ln.lo is not None:
            ml = max(ml, ln.lo - s)
    return Residual(max_pin_m=mp, max_diff_m=max(md, ml), max_flat_m=mf,
                    max_band_m=mb, max_offset_m=mo, objective=objective)


# ── the linear solve ────────────────────────────────────────────────────

def _linear_solve(A: sp.csr_matrix, b: np.ndarray, x0: np.ndarray | None,
                  method: str, tol: float, maxiter: int) -> np.ndarray:
    """min ‖A x − b‖² by ``method`` (:data:`METHODS`)."""
    if method == "lsqr":
        out = lsqr(A, b, atol=tol, btol=tol, iter_lim=maxiter, x0=x0)
        return np.asarray(out[0], float)
    At = A.T.tocsr()
    N = (At @ A).tocsc()
    rhs = At @ b
    if method == "normal":
        # a tiny Tikhonov floor keeps the factorisation non-singular on a
        # column the active set left with only a bending row
        eps = 1e-9 * max(1.0, float(abs(N.diagonal()).max()))
        return np.asarray(splu((N + eps * sp.identity(N.shape[0], format="csc")).tocsc()
                               ).solve(rhs), float)
    diag = N.diagonal().copy()
    diag[diag <= 0.0] = 1.0
    M = sp.diags(1.0 / diag)
    x, _info = cg(N.tocsr(), rhs, x0=x0, rtol=tol, maxiter=maxiter, M=M)
    return np.asarray(x, float)


# ── THE SOLVE ───────────────────────────────────────────────────────────

@_dc.dataclass
class Base:
    """The assembled design problem before the active set runs: the ALWAYS-ON
    rows, the reduction, the one-sided law targets and the law's own
    equalities.  Public so a benchmark arm can solve the SAME problem another
    way (spec §5: the lane measured the normal equations against HiGHS QP)."""

    rows: "_Rows"
    red: _Reduction
    one: list["_Side"]
    eqs: list["_Side"]
    n: int
    chord_vertices: int = 0
    road_fit_vertices: int = 0
    dem_zone_vertices: int = 0


def assemble(planar: PlanarMap, cs: ConstraintSet, law: Law,
             rep: DesignReport) -> Base:
    """Sections 1-9 of the module docstring: the sheets and their
    triangulation, the zone ramp, the reduction, and every always-on row
    (bending, road chains, the chord, the zone DEM fit, the law's equalities,
    the bodies' own datums)."""
    d = design_law(law)
    n = len(planar.vertices)

    # 1. the sheets and their triangulation
    roles = set(bend_roles(law))
    pav_roles = set(pavement_roles(law))
    sheet_faces = [f.id for f in planar.faces.values() if f.role in roles]
    tris: list[tuple[int, int, int]] = []
    for fid in sheet_faces:
        tris.extend(_face_triangles(planar, fid))
    rep.triangles = len(tris)
    pav: set[int] = set()
    for fid in sheet_faces:
        if planar.faces[fid].role not in pav_roles:
            continue
        for ring in (planar.faces[fid].ring, *planar.faces[fid].holes):
            pav.update(planar.ring_vertices(ring))

    # 2. the zone ramp and what lies beyond it (the DEM, fixed).  A road's
    #    or a structure's vertex is never fixed: it carries its own law far
    #    from any pavement (08t answers 7 and 8)
    # the role sets straight from the LAW tables (M0 §1: ``solve`` imports
    # ``law`` and ``model`` only — never ``constraints``)
    road_roles = set(law.tables.families["road_cross_section"].roles)
    rwy_roles = set(law.tables.precedence.runway_family.members)
    free_roles = road_roles | {
        r for r in law.tables.precedence.roles if is_structure_role(law, r)}
    free = {v for v, vx in planar.vertices.items()
            if any(planar.faces[f].role in free_roles for f in vx.incident_faces)}
    ramp, beyond = _zone_weights(planar, law, pav, free)
    rwy_v = {v for v, vx in planar.vertices.items()
             if any(planar.faces[f].role in rwy_roles for f in vx.incident_faces)}

    # 3. the reduction: pins fix, flats merge, the outer ring is the DEM
    red = _reduce(planar, cs, beyond)
    rep.unknowns = red.n_cols
    rep.fixed = int((red.col < 0).sum())
    rows = _Rows(red)
    one: list[_Side] = []
    eqs: list[_Side] = []
    chord_v = road_v = dem_v = 0
    if red.n_cols == 0:
        return Base(rows, red, one, eqs, n)

    # 4. bending — the shaping term
    L, area = _cotangent_laplacian(planar, tris, n)
    L = L.tocsr()
    for i in range(n):
        s, e = L.indptr[i], L.indptr[i + 1]
        if e <= s or area[i] <= 0.0:
            continue
        scale = 1.0 / math.sqrt(area[i])
        rows.add([(int(L.indices[k]), float(L.data[k]) * scale) for k in range(s, e)],
                 0.0, d.bend, ("bend", i))

    # 5. the road chains' own bending (second difference along the chain)
    road_kinds = {"road_centerline"}
    for bl in planar.breaklines.values():
        if bl.kind not in road_kinds:
            continue
        ch = bl.vertices(planar)
        for k in range(1, len(ch) - 1):
            a, m, c = ch[k - 1], ch[k], ch[k + 1]
            if len({a, m, c}) < 3:
                continue
            (ax, ay), (mx, my), (cx, cy) = (planar.vertices[i].xy for i in (a, m, c))
            dp, dn = math.hypot(mx - ax, my - ay), math.hypot(cx - mx, cy - my)
            if dp <= 1e-6 or dn <= 1e-6:
                continue
            sc = 0.5 * (dp + dn)
            rows.add(((c, sc / dn), (m, -sc * (1.0 / dn + 1.0 / dp)), (a, sc / dp)),
                     0.0, d.road, ("road", bl.id))

    # 6. the runway chord (and the core's road profile) — ``preferred_z``
    #    (a runway-family vertex fits the CHORD; every other published
    #    target is the core's clamped road profile — the road's own term)
    pref = planar.preferred_z
    for vid, target in pref.items():
        if vid in rwy_v:
            if rows.add(((vid, 1.0),), float(target), d.chord, ("chord", vid)):
                chord_v += 1
        elif rows.add(((vid, 1.0),), float(target), d.road, ("road_fit", vid)):
            road_v += 1

    # 7. the DEM fit — ONLY on the zone vertices, ramped to the outer ring
    for vid, frac in ramp.items():
        if frac <= 0.0 or vid in pref or vid in pav:
            continue
        z_dem = planar.vertices[vid].dem_z
        if z_dem is None:
            continue
        if rows.add(((vid, 1.0),), float(z_dem), d.dem_zone * frac * frac,
                    ("dem_zone", vid)):
            dem_v += 1

    # 8. the law rows as ONE-SIDED penalties (plus the law's own equalities)
    one_t, eqs_t = _law_sides(cs)
    # THE BANK AT THE EDGE IS LAWFUL (owner 08t answers 2 and 3: cut and fill
    # are unbounded, the blend happens INSIDE the zone, beyond it the terrain).
    # A law row with one foot on a vertex that IS the terrain — fixed beyond
    # the zone's outer ring — and one on the design surface would pull the
    # DESIGN down to the terrain: it is the per-vertex DEM pull answer 1
    # removed, wearing a law row's clothes.  Such a row is not a design
    # target; the census still reports it, and the bank it names is the bank
    # the owner asked for.  A PIN's vertex is not terrain: those rows stay.
    dropped_bank = 0
    for side in one_t:
        vs = {v for v, _c in side[0]}
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        one.append(side)
    for side in eqs_t:
        vs = {v for v, _c in side[0]}
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        eqs.append(side)
    rep.bank_rows = dropped_bank
    for terms, hi, row in eqs:
        rows.add(terms, hi, d.law, ("law", row))
    # 9. THE BODY'S OWN DATUM (owner 08t answer 6).  A one-sided law row is
    #    no datum: it bounds a DIFFERENCE and starts inactive, so a sheet
    #    carrying neither a pin nor a chord nor a zone fit floats — level and
    #    tilt both free under bending alone.  Every such connected sheet
    #    takes ONE soft datum: the least-squares PLANE of its own DEM samples
    #    (its terrain mean AND its terrain tilt — a plane has zero bending, so
    #    this sets the body's level without undulating it), at
    #    ``detached_mean``.  A sheet a pin, a chord or the zone already
    #    anchors keeps its design level untouched.
    comp = _sheet_components(tris, red)
    rep.components = len(set(comp.values()))
    anchored: set[int] = set()
    for vid in range(n):
        col = int(red.col[vid])
        if col < 0:                                   # a pin / the DEM beyond
            continue
        if vid in pref or ramp.get(vid, 0.0) > 0.0:
            anchored.add(comp[col])
    for p_ in cs.pins:                                # a pin fixes its class
        col = int(red.col[p_.v])
        if col < 0:
            for vid in range(n):
                if red.find(vid) == red.find(p_.v) and red.col[vid] >= 0:
                    anchored.add(comp[int(red.col[vid])])
    for f_ in cs.flats:                               # a rigid group is one sheet
        cols = {int(red.col[v]) for v in f_.group if red.col[v] >= 0}
        if len(cols) < len(f_.group):                 # a member is fixed
            anchored.update(comp[c] for c in cols)
    by_comp: dict[int, list[int]] = {}
    for vid in range(n):
        col = int(red.col[vid])
        if col < 0 or comp[col] in anchored:
            continue
        if planar.vertices[vid].dem_z is not None:
            by_comp.setdefault(comp[col], []).append(vid)
    #    THE GROUNDSIDE BODIES (owner 08t answer 6 with the groundside
    #    terrace law): a lot, a groundside apron, a service road is reached by
    #    no route and pinned by nothing — its datum is ITS OWN TERRAIN PLANE
    #    too, even where a shared vertex ties it to the airside sheet.  The
    #    airside design surface is never given one.
    gs_roles = {r for r in pav_roles if role_side(law, r) == "groundside"}
    for vs in _role_bodies(planar, gs_roles, red):
        by_comp.setdefault(("groundside", vs[0]), vs)
    #    A RIGID GROUP (a pad, a plate, a wall band) is ONE column, so its
    #    own bending rows collapse to nothing: bending gives it no level at
    #    all and only its contact rows — one-sided — would.  Each such group
    #    that no pin fixes takes the same soft datum on its own DEM mean, so
    #    a pad with no frontage row sits on its ground instead of floating.
    for f_ in cs.flats:
        col = int(red.col[f_.group[0]])
        if col < 0:
            continue
        vs_f = [v for v in f_.group if planar.vertices[v].dem_z is not None]
        if not vs_f:
            continue
        mean = sum(float(planar.vertices[v].dem_z) for v in vs_f) / len(vs_f)
        rows.add(((f_.group[0], 1.0),), mean, d.detached_mean, ("detached", ("flat", col)))
    rep.detached = len(by_comp)
    for c, vs in by_comp.items():
        for vid, target in _plane_targets(planar, vs):
            rows.add(((vid, 1.0),), target, d.detached_mean, ("detached", c))
    return Base(rows, red, one, eqs, n, chord_v, road_v, dem_v)


def solve_design(planar: PlanarMap, cs: ConstraintSet, law: Law,
                 options: Options | None = None, *,
                 size_out: dict | None = None,
                 method: str = DEFAULT_METHOD) -> tuple[Solution, DesignReport]:
    """The whole design surface (module docstring).  Returns the solution
    and the residual report; the solve is never infeasible."""
    opt = options or Options()
    d = design_law(law)
    rep = DesignReport(method=method)
    t0 = time.perf_counter()
    n = len(planar.vertices)
    base_p = assemble(planar, cs, law, rep)
    rows, red, one, eqs = base_p.rows, base_p.red, base_p.one, base_p.eqs
    chord_v, road_v, dem_v = (base_p.chord_vertices, base_p.road_fit_vertices,
                              base_p.dem_zone_vertices)
    if red.n_cols == 0:
        z = np.array([float(red.value[v]) for v in range(n)])
        return (Solution(z=tuple(z), status=Status.OPTIMAL,
                         residual=residual(cs, z, 0.0),
                         wall_s=time.perf_counter() - t0,
                         message="every vertex fixed"), rep)

    # 10. THE ACTIVE SET: solve, take the violated one-sided rows, re-solve.
    #     The one-sided rows are stacked ONCE (``_one_matrix``) so a round is
    #     a row-slice and a matrix-vector product, never a Python re-assembly:
    #     at HECA that is 210k rows the loop would otherwise rebuild 60 times.
    A0f, b0f = rows.matrix(red.n_cols)      # the ALWAYS-ON rows (the base)
    A1, b1 = _one_matrix(one, red)
    w_law = math.sqrt(d.law)
    x = None
    x_prev: np.ndarray | None = None
    x_full: np.ndarray | None = None
    f_prev = math.inf
    f_last = math.inf
    active_i = np.zeros(0, dtype=np.int64)
    active: set[int] = set()
    z = np.zeros(n)
    t_solver = 0.0
    A, b = A0f, b0f
    for rnd in range(1, int(d.active_set_max_rounds) + 1):
        if active_i.size:
            A = sp.vstack([A0f, w_law * A1[active_i]], format="csr")
            b = np.concatenate([b0f, w_law * b1[active_i]])
        else:
            A, b = A0f, b0f
        rep.rows = int(A.shape[0])
        t1 = time.perf_counter()
        x = _linear_solve(A, b, x, method, float(d.solver_tol), int(d.solver_max_iter))
        x_full = x
        t_solver += time.perf_counter() - t1
        # DAMPING (a semismooth Newton step with a backtracking line search
        # on the TRUE objective): the plain fixed point can cycle between two
        # active sets, and a cycling set is not a solution.  ``F`` is convex
        # and C¹, so a step that does not decrease it is halved.
        if x_prev is not None:
            f_new = _objective(A0f, b0f, A1, b1, d, x)
            alpha = 1.0
            while f_new > f_prev and alpha > _ALPHA_FLOOR:
                alpha *= 0.5
                x = x_prev + alpha * (x_full - x_prev)
                f_new = _objective(A0f, b0f, A1, b1, d, x)
            if f_new > f_prev:
                # the step buys nothing: the previous point is the answer
                x = x_prev
                rep.converged = True
                rep.rounds = rnd
                break
            f_prev = f_new
        else:
            f_prev = _objective(A0f, b0f, A1, b1, d, x)
        x_prev = x.copy()
        z = np.where(red.col >= 0, x[np.clip(red.col, 0, None)], red.value)
        viol = A1 @ x - b1
        nxt_i = np.flatnonzero(viol > float(d.active_set_tol_m))
        nxt = set(nxt_i.tolist())
        rep.rounds = rnd
        # SETTLED: the same active set, or an objective that no longer moves
        # (a row hovering at its bound flips label without moving the surface)
        if nxt == active or (f_prev < math.inf and
                             abs(f_last - f_prev) <= 1e-6 * max(1.0, f_prev)):
            rep.converged = True
            break
        if opt.verbose:
            print(f"    [design] round {rnd}: F {f_prev:.6g}  active {len(nxt)} "
                  f"(was {len(active)}, changed {len(nxt ^ active)})")
        f_last = f_prev
        active, active_i = nxt, nxt_i
    if x is not None:
        z = np.where(red.col >= 0, x[np.clip(red.col, 0, None)], red.value)
    rep.solver_wall_s = t_solver

    # 11. the residual per family (a missed TARGET, not a demotion)
    fam: dict[str, dict[str, _t.Any]] = {}
    viol_all = (A1 @ x - b1) if x is not None else np.zeros(len(one))
    tol = float(d.active_set_tol_m)
    for k, (_terms, _hi, row) in enumerate(one):
        g = row.source.generator
        rec = fam.setdefault(g, {"rows": 0, "missed": 0, "max_m": 0.0, "energy": 0.0})
        rec["rows"] += 1
        v = float(viol_all[k])
        if v > tol:
            rec["missed"] += 1
            rec["max_m"] = max(rec["max_m"], v)
            rec["energy"] += d.law * v * v
    for terms, hi, row in eqs:
        g = row.source.generator
        rec = fam.setdefault(g, {"rows": 0, "missed": 0, "max_m": 0.0, "energy": 0.0})
        rec["rows"] += 1
        v = abs(sum(c * float(z[vid]) for vid, c in terms) - hi)
        if v > float(d.active_set_tol_m):
            rec["missed"] += 1
            rec["max_m"] = max(rec["max_m"], v)
            rec["energy"] += d.law * v * v
    for rec in fam.values():
        rec["max_m"] = round(rec["max_m"], 4)
        rec["energy"] = round(rec["energy"], 3)
    rep.families = dict(sorted(fam.items()))
    obj = float(np.sum((A @ x - b) ** 2)) if x is not None else 0.0
    rep.terms = _term_energies(rows, A, b, x)
    if size_out is not None:
        size_out.update({"columns": red.n_cols, "z": n, "rows": rep.rows,
                         "nnz": int(A.nnz), "triangles": rep.triangles,
                         "chord_vertices": chord_v, "road_fit_vertices": road_v,
                         "dem_zone_vertices": dem_v,
                         "active": len(active), "rounds": rep.rounds})
    cert = residual(cs, z, obj)
    wall = time.perf_counter() - t0
    return (Solution(z=tuple(float(v) for v in z),
                     status=Status.OPTIMAL if rep.converged else Status.FEASIBLE,
                     residual=cert, iterations=rep.rounds, wall_s=wall,
                     message=f"design surface: {rep.rounds} active-set round(s), "
                             f"{red.n_cols} unknowns, {rep.rows} rows, "
                             f"{method}"), rep)


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


def _objective(A0: sp.csr_matrix, b0: np.ndarray, A1: sp.csr_matrix,
               b1: np.ndarray, d, x: np.ndarray) -> float:
    """The TRUE objective at ``x``: the always-on rows' squared residual plus
    every one-sided row's ``w_law · max(0, violation)²``."""
    viol = np.maximum(A1 @ x - b1, 0.0)
    return float(np.sum((A0 @ x - b0) ** 2) + d.law * np.sum(viol ** 2))


def _term_energies(rows: _Rows, A: sp.csr_matrix, b: np.ndarray,
                   x: np.ndarray | None) -> dict[str, float]:
    """Σ of each objective term's squared weighted residual."""
    if x is None:
        return {}
    r = A @ x - b
    acc: dict[str, float] = {}
    for k, own in enumerate(rows.owner):
        key = own[0] if own else "other"
        acc[key] = acc.get(key, 0.0) + float(r[k]) ** 2
    return {k: round(v, 3) for k, v in sorted(acc.items())}


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
