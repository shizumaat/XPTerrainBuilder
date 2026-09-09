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
                THE RUNWAY FAMILY'S LAW ROWS (``[design] hard_generators``)
                → CONSTRAINTS, enforced EXACTLY as a KKT block, never a
                  penalty (owner 05s/06b within 08t, RULINGS 2026-09-08v)

``w_bend`` is PER CLASS (``bend_runway`` / ``bend_taxi`` / ``bend_apron`` /
``bend_road`` / ``bend_strip``, RULINGS 2026-09-08v): one weight for the
whole sheet traded the pavement against the strip, so a bending row is
priced by the class of its own vertex (:func:`bend_class`).

The one-sided penalties are met by an ACTIVE SET iteration (a semismooth
Newton step): solve, take the rows the surface violates, re-solve with those
rows active, to a fixed point of the set.  The HARD rows run their own active
set inside the same loop — a violated one enters the KKT block, one whose
multiplier turns negative leaves it — and a bounded polish after it, so the
returned surface satisfies every runway law to the solver's tolerance.  Every
weight and limit is a law value (``law/emit.toml [design]``,
``law/design_schema.py``).

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
from ..law.design_schema import BEND_CLASSES
from ..law.tables import (design as design_law, is_structure_role, is_value_role,
                          role_side, zone2_half_width_m, zone_class)
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear, Offset,
                                 Pin, Row)
from ..model.planar import PlanarMap
from .api import Options, Residual, Solution, Status
from .rows import (_cotangent_laplacian, _face_triangles, _law_sides, _one_matrix,
                   _plane_targets, _reduce, _Reduction, _role_bodies, _Rows,
                   _sheet_components, _Side, _violation, _zone_weights)

__all__ = ["DesignReport", "Base", "assemble", "solve_design", "residual",
           "bend_roles", "pavement_roles", "bend_class", "hard_rulings",
           "is_hard", "METHODS", "DEFAULT_METHOD"]

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


def bend_class(law: Law, role: str) -> str:
    """The BENDING CLASS of ``role`` (``design_schema.BEND_CLASSES``, RULINGS
    2026-09-08v): ``runway`` / ``taxi`` for the two named families,
    ``road`` for the road cross-section's roles, ``apron`` for every other
    role that carries its own value, ``strip`` for the rest (the graded
    strip, the clearances, the cuts — the ground the blend happens in)."""
    if role in law.tables.precedence.runway_family.members:
        return "runway"
    if role in law.tables.precedence.taxi_family.members:
        return "taxi"
    if role in law.tables.families["road_cross_section"].roles:
        return "road"
    return "apron" if is_value_role(law, role) else "strip"


def hard_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are HARD CONSTRAINTS of the active set —
    ``[design] hard_rulings`` (RULINGS 2026-09-08v: the runway family's
    transverse, vertical curve K and max grade; the threshold pins are
    already equalities)."""
    return frozenset(design_law(law).hard_rulings)


def is_hard(law_heads: _t.AbstractSet[str], row: Row) -> bool:
    """Whether ``row`` states one of the HARD laws: the head of its ruling
    (everything before the first parenthesis) is one of ``law_heads``."""
    return row.source.ruling.split(" (")[0].strip() in law_heads


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
    #: THE HARD ROWS (RULINGS 2026-09-08v): the runway family's law rows as
    #: constraints — how many exist, how many the settled active set holds,
    #: how many polish rounds it took and the worst violation left (a
    #: constraint held exactly reads 0 to the solver's tolerance)
    hard_rows: int = 0
    hard_active: int = 0
    hard_rounds: int = 0
    hard_max_violation_m: float = 0.0
    hard_settled: bool = True
    #: the ruling of the worst-held hard row (empty where every row is held)
    hard_worst: str = ""
    bend_rows_by_class: dict[str, int] = _dc.field(default_factory=dict)
    #: THE MISSED TARGETS (sidecar ``design_target``, RULINGS 2026-09-08t/v):
    #: one record per law row the design surface did not reach — its family,
    #: the metres it is out by and the lat/lon identities of its vertices, so
    #: the census can report the rows it counts under one heading
    targets: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    solver_wall_s: float = 0.0
    families: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    terms: dict[str, float] = _dc.field(default_factory=dict)

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rounds": self.rounds, "converged": self.converged,
                "method": self.method, "unknowns": self.unknowns,
                "fixed": self.fixed, "rows": self.rows,
                "triangles": self.triangles, "components": self.components,
                "detached": self.detached, "bank_rows": self.bank_rows,
                "hard_rows": self.hard_rows, "hard_active": self.hard_active,
                "hard_rounds": self.hard_rounds, "hard_settled": self.hard_settled,
                "hard_max_violation_m": round(self.hard_max_violation_m, 6),
                "hard_worst": self.hard_worst,
                "bend_rows_by_class": self.bend_rows_by_class,
                "targets": len(self.targets),
                "solver_wall_s": round(self.solver_wall_s, 3),
                "families": self.families, "terms": self.terms}

    def line(self) -> str:
        worst = sorted(self.families.items(), key=lambda kv: -kv[1]["max_m"])[:6]
        return (f"design (08t): {self.rounds} active-set round(s)"
                f"{'' if self.converged else ' (SET NOT SETTLED)'}, {self.method}, "
                f"{self.unknowns} unknowns / {self.fixed} fixed, {self.rows} rows, "
                f"{self.triangles} triangles in {self.components} complexes "
                f"({self.detached} detached), {self.bank_rows} bank rows off the "
                f"terrain edge, {self.hard_active}/{self.hard_rows} hard rows active "
                f"(max violation {self.hard_max_violation_m:.4f} m in "
                f"{self.hard_rounds} polish round(s)"
                f"{'' if self.hard_settled else ', HARD SET NOT SETTLED'}), "
                f"{self.solver_wall_s:.2f} s solver; "
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
        eps = 1e-12 * max(1.0, float(abs(N.diagonal()).max()))
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
    #: indices into ``one`` of the HARD rows (``[design] hard_generators``):
    #: constraints of the active set, never penalties (RULINGS 2026-09-08v)
    hard: list[int] = _dc.field(default_factory=list)
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
        return Base(rows, red, one, eqs, n)      # nothing to solve

    # 4. bending — the shaping term, PER CLASS (RULINGS 2026-09-08v).  A
    #    bending row is centred on ONE vertex, so it is priced by that
    #    vertex's own class: the SENIOR class of the faces that touch it
    #    (``BEND_CLASSES`` order), so a runway edge shared with its strip
    #    bends at the runway's weight and the strip beside it at the strip's.
    rank = {c: k for k, c in enumerate(BEND_CLASSES)}
    v_class: dict[int, str] = {}
    for f in planar.faces.values():
        if f.role not in roles:
            continue
        cls = bend_class(law, f.role)
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                cur = v_class.get(v)
                if cur is None or rank[cls] < rank[cur]:
                    v_class[v] = cls
    rep.bend_rows_by_class = {c: 0 for c in BEND_CLASSES}
    L, area = _cotangent_laplacian(planar, tris, n)
    L = L.tocsr()
    for i in range(n):
        s, e = L.indptr[i], L.indptr[i + 1]
        if e <= s or area[i] <= 0.0:
            continue
        cls = v_class.get(i, "strip")
        scale = 1.0 / math.sqrt(area[i])
        if rows.add([(int(L.indices[k]), float(L.data[k]) * scale) for k in range(s, e)],
                    0.0, d.bend(cls), ("bend", i)):
            rep.bend_rows_by_class[cls] += 1

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
    heads = hard_rulings(law)
    hard: list[int] = []
    for side in one_t:
        terms, hi, row = side
        vs = {v for v, _c in terms}
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        # THE HARD ROWS (RULINGS 2026-09-08v): the runway family's transverse,
        # vertical curve and max grade are CONSTRAINTS.  A row whose every
        # foot is fixed carries no column and constrains nothing — it stays a
        # reported target.  A PREFERENCE among them is hard AT ITS CEILING and
        # keeps its preferred bound as the target: two sides, one row.
        if is_hard(heads, row) and not vs <= red.dem_fixed:
            hi_hard = hi
            ceil = getattr(row, "ceiling", None)
            if getattr(row, "soft", None) is not None and ceil is not None:
                hi_hard = (float(ceil) * row.d if isinstance(row, Diff)
                           else hi + float(ceil))
            if hi_hard > hi:
                one.append(side)
                hard.append(len(one))
                one.append((terms, hi_hard, row))
                continue
            hard.append(len(one))
        one.append(side)
    for side in eqs_t:
        vs = {v for v, _c in side[0]}
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        eqs.append(side)
    rep.bank_rows = dropped_bank
    rep.hard_rows = len(hard)
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
    return Base(rows, red, one, eqs, n, hard, chord_v, road_v, dem_v)


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
    #
    #     THE HARD ROWS (the runway family's transverse, vertical curve K and
    #     max grade — ``[design] hard_rulings``, RULINGS 2026-09-08v) ride the
    #     same stack at the CONSTRAINT weight ``ρ = hard_weight`` and are made
    #     EXACT by an outer AUGMENTED-LAGRANGIAN loop: the inner active set
    #     runs to its damped fixed point with the multipliers held, then each
    #     violated runway row's multiplier rises by ``ρ · violation`` and
    #     tightens that row's target by ``μ/ρ``.  The multipliers converge, so
    #     the runway laws end HELD, not traded — which a weight alone cannot
    #     do (RULINGS 2026-09-08v: "a weight cannot buy a law").
    A0f, b0f = rows.matrix(red.n_cols)      # the ALWAYS-ON rows (the base)
    A1, b1 = _one_matrix(one, red)
    hard_i = np.asarray(base_p.hard, dtype=np.int64)
    rep.hard_rows = int(hard_i.size)
    # THE HARD ROWS ARE SCALED TO METRES.  A law row is stated in its own
    # units: a grade cap's row is a Δz (metres), but a VERTICAL CURVE row is a
    # difference of grades (dimensionless), and a rate row a curvature.  One
    # constraint weight and one tolerance can only price them together if the
    # residual means the same thing, so each hard row (and its target) is
    # divided by ``Σ|c| / 2`` — 1 for a two-vertex Δz row, ``≈ d/2`` for a K
    # row, so every hard violation the report and the multipliers see is
    # METRES of surface.  Measured: without it a K row's penalty was ~1/d²
    # weaker than a transverse row's and the K law never closed (CYXY 0.0093
    # left at ρ = 3e6; spec §6 deviation 9).
    if hard_i.size:
        rowsum = np.asarray(abs(A1).sum(axis=1)).ravel()
        sc = np.ones(A1.shape[0])
        good = rowsum[hard_i] > 0.0
        sc[hard_i[good]] = 2.0 / rowsum[hard_i[good]]
        A1 = sp.diags(sc) @ A1
        b1 = sc * b1
        A1 = A1.tocsr()
    rho = float(d.hard_weight)
    w_row = np.full(len(one), float(d.law))
    w_row[hard_i] = rho
    sw = np.sqrt(w_row)
    #: ``μ/ρ`` per one-sided row — zero everywhere but the hard rows, where it
    #: tightens the target by the multiplier the constraint has earned
    shift = np.zeros(len(one))
    tol = float(d.active_set_tol_m)
    x: np.ndarray | None = None
    z = np.zeros(n)
    t_solver = 0.0
    A, b = A0f, b0f
    active_i = np.zeros(0, dtype=np.int64)
    active: set[int] = set()

    def _stack(sel: np.ndarray) -> tuple[sp.csr_matrix, np.ndarray]:
        """The base rows plus the ACTIVE one-sided rows at their own weights
        (the law's for a target, ``ρ`` for a runway constraint) against their
        shifted targets."""
        if not sel.size:
            return A0f, b0f
        W = sp.diags(sw[sel])
        return (sp.vstack([A0f, W @ A1[sel]], format="csr"),
                np.concatenate([b0f, sw[sel] * (b1[sel] - shift[sel])]))

    def _inner(x0: np.ndarray | None) -> np.ndarray:
        """One damped active-set solve at the CURRENT multipliers."""
        nonlocal A, b, active, active_i, t_solver
        x_ = x0
        x_prev: np.ndarray | None = None
        f_prev = math.inf
        f_last = math.inf
        for rnd in range(1, int(d.active_set_max_rounds) + 1):
            A, b = _stack(active_i)
            rep.rows = int(A.shape[0])
            t1 = time.perf_counter()
            x_full = _linear_solve(A, b, x_, method, float(d.solver_tol),
                                   int(d.solver_max_iter))
            x_ = x_full
            t_solver += time.perf_counter() - t1
            # DAMPING (a semismooth Newton step with a backtracking line search
            # on the TRUE objective): the plain fixed point can cycle between
            # two active sets, and a cycling set is not a solution.  ``F`` is
            # convex and C¹, so a step that does not decrease it is halved.
            if x_prev is not None:
                f_new = _objective(A0f, b0f, A1, b1, w_row, shift, x_)
                alpha = 1.0
                while f_new > f_prev and alpha > _ALPHA_FLOOR:
                    alpha *= 0.5
                    x_ = x_prev + alpha * (x_full - x_prev)
                    f_new = _objective(A0f, b0f, A1, b1, w_row, shift, x_)
                if f_new > f_prev:
                    x_ = x_prev          # the step buys nothing: this is it
                    rep.converged = True
                    rep.rounds += rnd
                    return x_
                f_prev = f_new
            else:
                f_prev = _objective(A0f, b0f, A1, b1, w_row, shift, x_)
            x_prev = x_.copy()
            viol = A1 @ x_ - (b1 - shift)
            nxt_i = np.flatnonzero(viol > tol)
            nxt = set(nxt_i.tolist())
            # SETTLED: the same active set, or an objective that no longer
            # moves (a row hovering at its bound flips label without moving
            # the surface)
            if nxt == active or (f_prev < math.inf and
                                 abs(f_last - f_prev) <= 1e-6 * max(1.0, f_prev)):
                rep.converged = True
                rep.rounds += rnd
                return x_
            if opt.verbose:
                print(f"    [design] round {rnd}: F {f_prev:.6g}  active {len(nxt)} "
                      f"(was {len(active)}, changed {len(nxt ^ active)})")
            f_last = f_prev
            active, active_i = nxt, nxt_i
        rep.converged = False
        rep.rounds += int(d.active_set_max_rounds)
        return x_ if x_ is not None else np.zeros(red.n_cols)

    x = _inner(None)
    if hard_i.size:
        Ah, bh = A1[hard_i], b1[hard_i]
        mu = np.zeros(hard_i.size)
        tol_h = float(d.hard_tol_m)
        worst = float(np.max(np.maximum(Ah @ x - bh, 0.0)))
        best_x, best_worst = x, worst
        for pr in range(1, int(d.hard_max_rounds) + 1):
            if worst <= tol_h:
                break
            rep.hard_rounds = pr
            mu = np.maximum(0.0, mu + rho * (Ah @ x - bh))
            shift[hard_i] = mu / rho
            x = _inner(x)
            worst = float(np.max(np.maximum(Ah @ x - bh, 0.0)))
            if worst < best_worst:
                best_x, best_worst = x, worst
            if opt.verbose:
                print(f"    [design/hard] multiplier round {pr}: "
                      f"{int(np.count_nonzero(mu > 0.0))} runway rows carry a "
                      f"multiplier, max runway violation {worst:.5f} m")
        if best_worst < worst:
            x, worst = best_x, best_worst      # never return a worse surface
        rep.hard_active = int(np.count_nonzero(mu > 0.0))
        rep.hard_max_violation_m = worst
        rep.hard_settled = worst <= tol_h
        if worst > tol_h:
            k = int(np.argmax(Ah @ x - bh))
            rep.hard_worst = one[int(hard_i[k])][2].source.ruling[:70]
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
    # THE PUBLISHED TARGETS: every row missed beyond the elevation
    # materiality, with its vertices' canonical identities (RULINGS
    # 2026-09-08t: "a target missed is a row, the census counts it")
    mat = float(law.tables.emit.materiality.elevation_m)
    tgt: list[dict[str, _t.Any]] = []
    for k, (terms, _hi, row) in enumerate(one):
        v = float(viol_all[k])
        if v <= mat:
            continue
        tgt.append({"family": row.source.generator, "miss_m": round(v, 4),
                    "ll": [[planar.vertices[vid].key[0], planar.vertices[vid].key[1]]
                           for vid, _c in terms]})
    rep.targets = tgt
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


def _objective(A0: sp.csr_matrix, b0: np.ndarray, A1: sp.csr_matrix,
               b1: np.ndarray, w_row: np.ndarray, shift: np.ndarray,
               x: np.ndarray) -> float:
    """The TRUE objective at ``x``: the always-on rows' squared residual plus
    every one-sided row's ``w · max(0, violation)²`` at ITS OWN weight (the
    law's for a target, ``hard_weight`` for a runway constraint) against its
    shifted target (the augmented Lagrangian's ``b − μ/ρ``)."""
    viol = np.maximum(A1 @ x - (b1 - shift), 0.0)
    return float(np.sum((A0 @ x - b0) ** 2) + float(np.sum(w_row * viol ** 2)))


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

