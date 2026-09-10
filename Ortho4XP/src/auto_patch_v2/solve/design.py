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
from scipy.sparse.linalg import LinearOperator, cg, lsqr, splu

from ..law import Law
from ..law.design_schema import BEND_CLASSES
from ..law.tables import (design as design_law, is_structure_role, is_value_role,
                          pavement_roles as _pavement_roles,
                          role_side, zone2_half_width_m, zone_class)
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear, Offset,
                                 Pin, Row)
from ..model.planar import PlanarMap
from .api import Options, Residual, Solution, Status
from .linear import (DEFAULT_LOW_RANK, DEFAULT_METHOD, LOW_RANK_MODES,
                     METHODS, _linear_solve, _objective, _term_energies)
from .project import ProjectionReport, project_runway
from .rows import (_cotangent_laplacian, _face_triangles, _law_sides, _one_matrix,
                   _plane_targets, _reduce, _Reduction, _role_bodies,
                   _role_bodies_faced, _Rows, _shape_bodies,
                   _sheet_components, _Side, _violation, _zone_weights)

__all__ = ["DesignReport", "Base", "assemble", "solve_design", "residual",
           "bend_roles", "pavement_roles", "bend_class", "apron_roles", "hard_rulings",
           "one_way_rulings", "pad_flat_rulings", "pad_level_rulings",
           "is_hard", "ruling_head",
           "METHODS", "DEFAULT_METHOD", "LOW_RANK_MODES", "DEFAULT_LOW_RANK"]

#: The backtracking line search's smallest step (a numeric floor of the
#: solver, not a law value): below it the Newton direction buys nothing and
#: the previous point IS the minimiser.
_ALPHA_FLOOR = 1.0e-6

#: The shift that switches a ONE-WAY row OFF for the warm-up solve (its
#: leaders have no value before the first solve): a target so far away
#: that the row can never be violated.  A solver constant, not a law value.
_LAG_OFF = 1.0e9


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
    of one of these faces never takes a DEM fit (08t answer 1).  ONE
    derivation site, ``law.tables.pavement_roles`` (``constraints.pads``
    reads the same predicate to tell a pad's fronting pavement apart from
    the pad)."""
    return _pavement_roles(law)


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


def apron_roles(law: Law) -> frozenset[str]:
    """The roles of an APRON BODY — every role the bending term prices at
    ``bend_apron`` (a value role that is not the runway family, the taxi
    family or the road cross-section).  These are the bodies the PER-BODY
    DATUM sits (RULINGS 2026-09-09p (3)); the runway and taxi families are
    excluded because the threshold chord and the taxi design profile ARE
    their datums, and a structure's own surface is not a body at all."""
    return frozenset(r for r in pavement_roles(law)
                     if bend_class(law, r) == "apron")


def one_way_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are priced ONE-WAY — ``[design]
    one_way_rulings`` (RULINGS 2026-09-09b (2)/(3): the adjacent ground
    follows the pavement edge and never pulls it)."""
    return frozenset(design_law(law).one_way_rulings)


def pad_flat_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are priced at ``[design] pad_flat`` —
    the pad's flatness TARGET (owner RULINGS 2026-09-09c): a weight an
    order above the law's, so a pad comes out flat wherever the geometry
    admits a flat solution, and tilts (to at most 1 %, hard) where not."""
    return frozenset(design_law(law).pad_flat_rulings)


def pad_level_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS of a pad's frontage LEVEL rows — ``[design]
    pad_level_rulings`` (owner RULINGS 2026-09-10l, 10k-1 = (A): "Pad
    takes the apron edge level").  A vertex one of these rows GOVERNS
    follows its pavement, so §9b takes it out of every per-body DEM datum
    mean: a pad's own datum (09p (3)) is for a pad that fronts NO
    pavement."""
    return frozenset(design_law(law).pad_level_rulings)


def hard_rulings(law: Law) -> frozenset[str]:
    """The ruling HEADS whose rows are HARD CONSTRAINTS of the active set —
    ``[design] hard_rulings`` (RULINGS 2026-09-08v: the runway family's
    transverse, vertical curve K and max grade; the threshold pins are
    already equalities)."""
    return frozenset(design_law(law).hard_rulings)


def ruling_head(row: Row) -> str:
    """The HEAD of a row's ruling — everything before the first
    parenthesis, the key ``[design] hard_rulings`` / ``one_way_rulings``
    name a law by."""
    return row.source.ruling.split(" (")[0].strip()


def is_hard(law_heads: _t.AbstractSet[str], row: Row) -> bool:
    """Whether ``row`` states one of the HARD laws: the head of its ruling
    (everything before the first parenthesis) is one of ``law_heads``."""
    return ruling_head(row) in law_heads


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
    #: THE PER-BODY DATUM (RULINGS 2026-09-09p (3)): one row per APRON
    #: BODY, its mean z against the mean DEM under its own vertices
    body_datum_rows: int = 0
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
    #: THE FINAL PROJECTION (owner RULINGS 2026-09-09y): the runway family's
    #: hard rows held EXACTLY by a QP after the solve (``solve/project.py``)
    runway_projection: ProjectionReport = _dc.field(default_factory=ProjectionReport)
    #: THE ONE-WAY ROWS (RULINGS 2026-09-09b (2)/(3)): the adjacent-ground
    #: corridor and strip-tie rows whose pavement feet are LAGGED — how
    #: many, how many lag rounds the outer loop paid, whether the lag
    #: settled and how far the worst leader foot moved in the last round
    one_way_rows: int = 0
    one_way_rounds: int = 0
    one_way_settled: bool = True
    one_way_move_m: float = 0.0
    bend_rows_by_class: dict[str, int] = _dc.field(default_factory=dict)
    #: THE MISSED TARGETS (sidecar ``design_target``, RULINGS 2026-09-08t/v):
    #: one record per law row the design surface did not reach — its family,
    #: the metres it is out by and the lat/lon identities of its vertices, so
    #: the census can report the rows it counts under one heading
    targets: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    solver_wall_s: float = 0.0
    #: THE RUNWAY PROFILE (spec §21.2 (4)): per runway the target kind and
    #: window, the built ridge's residual against its target, its mean
    #: |z - DEM| and the law row that holds it — filled by the pipeline
    #: after the projection (``pipeline/runway_report.runway_profile_block``), and
    #: carried into the sidecar's ``design`` block so the census and the
    #: owner read WHICH target the runway was designed to.
    runway_profile: dict[str, _t.Any] = _dc.field(default_factory=dict)
    families: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    terms: dict[str, float] = _dc.field(default_factory=dict)

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rounds": self.rounds, "converged": self.converged,
                "method": self.method, "unknowns": self.unknowns,
                "fixed": self.fixed, "rows": self.rows,
                "triangles": self.triangles, "components": self.components,
                "detached": self.detached,
                "body_datum_rows": self.body_datum_rows,
                "bank_rows": self.bank_rows,
                "hard_rows": self.hard_rows, "hard_active": self.hard_active,
                "hard_rounds": self.hard_rounds, "hard_settled": self.hard_settled,
                "hard_max_violation_m": round(self.hard_max_violation_m, 6),
                "hard_worst": self.hard_worst,
                "runway_projection": self.runway_projection.as_dict(),
                "one_way_rows": self.one_way_rows,
                "one_way_rounds": self.one_way_rounds,
                "one_way_settled": self.one_way_settled,
                "one_way_move_m": round(self.one_way_move_m, 6),
                "bend_rows_by_class": self.bend_rows_by_class,
                "targets": len(self.targets),
                "solver_wall_s": round(self.solver_wall_s, 3),
                "runway_profile": self.runway_profile,
                "families": self.families, "terms": self.terms}

    def line(self) -> str:
        worst = sorted(self.families.items(), key=lambda kv: -kv[1]["max_m"])[:6]
        return (f"design (08t): {self.rounds} active-set round(s)"
                f"{'' if self.converged else ' (SET NOT SETTLED)'}, {self.method}, "
                f"{self.unknowns} unknowns / {self.fixed} fixed, {self.rows} rows, "
                f"{self.triangles} triangles in {self.components} complexes "
                f"({self.detached} detached), {self.body_datum_rows} apron "
                f"bodies on their own DEM mean, {self.bank_rows} bank rows off the "
                f"terrain edge, {self.hard_active}/{self.hard_rows} hard rows active "
                f"(max violation {self.hard_max_violation_m:.4f} m in "
                f"{self.hard_rounds} polish round(s)"
                f"{', HARD SET SETTLED' if self.hard_settled else ', HARD SET NOT SETTLED'}), "
                f"{self.one_way_rows} one-way rows in {self.one_way_rounds} lag "
                f"round(s) (worst leader move {self.one_way_move_m:.3f} m"
                f"{'' if self.one_way_settled else ', LAG NOT SETTLED'}), "
                f"{self.solver_wall_s:.2f} s solver; "
                + self.runway_projection.line() + "; "
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
    #: indices into ``one`` of the PAD FLATNESS rows (``[design]
    #: pad_flat_rulings``): targets priced at ``pad_flat`` instead of ``law``
    #: (owner RULINGS 2026-09-09c — a pad TARGETS flat, hard only at 1 %)
    pad_flat: list[int] = _dc.field(default_factory=list)
    #: ``one`` index -> the FOLLOWER vertex of a ONE-WAY row (``[design]
    #: one_way_rulings``): only that vertex keeps its column, the leaders
    #: enter the right-hand side lagged (RULINGS 2026-09-09b (2)/(3))
    one_way: dict[int, int] = _dc.field(default_factory=dict)
    chord_vertices: int = 0
    road_fit_vertices: int = 0
    #: THE PER-BODY DATUM rows, kept OUT of ``rows`` (RULINGS 2026-09-09r
    #: (1)): each is dense in ``AᵀA``, so they reach the linear solve as
    #: the low-rank term ``U`` (:data:`LOW_RANK_MODES`), never factorised.
    body: "_Rows | None" = None


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
    del free                       # 09-09b (3): nothing beyond the ring is fixed
    ramp = _zone_weights(planar, law, pav)
    rwy_v = {v for v, vx in planar.vertices.items()
             if any(planar.faces[f].role in rwy_roles for f in vx.incident_faces)}

    # 3. the reduction: pins fix, flats merge, the outer ring is the DEM
    red = _reduce(planar, cs, {})
    rep.unknowns = red.n_cols
    rep.fixed = int((red.col < 0).sum())
    rows = _Rows(red)
    one: list[_Side] = []
    eqs: list[_Side] = []
    chord_v = road_v = 0
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

    # 5b. THE TAXI DESIGN PROFILE (owner RULINGS 2026-09-09b (2): taxiways
    #     "should follow terrain less and be more like runways").  A runway
    #     is designed along its axis — the threshold chord plus the vertical
    #     curve K — so its profile is smooth by construction.  A taxiway had
    #     only its grade CAPS, which are silent inside themselves, so it
    #     draped.  Every taxi CENTRELINE chain now carries the runway's K
    #     pattern as an objective term: the second difference of z at each
    #     interior station, at ``[design] taxi_profile``.
    for bl in planar.breaklines.values():
        if bl.kind != "taxi_centerline":
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
                     0.0, d.taxi_profile, ("taxi_profile", bl.id))

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

    # 7. THE DEM FIT IS DELETED (owner RULINGS 2026-09-09b (3)): "adjacent
    #    ground should not go directly from airside to the DEM ... not even
    #    try to match DEM — the engine should automatically smooth between
    #    whatever elevation we set and the DEM".  Zone 1 is the lip draining
    #    down from the pavement edge, zone 2 the graded strip continuing at
    #    the strip transverse law, the runway ends the end-skirt corridor —
    #    all of them LAW rows of ``constraints/zones.py`` and
    #    ``constraints/strips.py``, priced ONE-WAY (§8) — and the outer
    #    ring's elevation is whatever those laws give.  The mesh engine
    #    drapes from the patch boundary to the DEM outside it.

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
    ow_heads = one_way_rulings(law)
    pf_heads = pad_flat_rulings(law)
    pl_heads = pad_level_rulings(law)
    #: the pad vertices a LEVEL row governs (owner RULINGS 2026-09-10l):
    #: they follow the pavement they front and carry no DEM datum (§9b)
    pad_follow: set[int] = set()
    hard: list[int] = []
    pad_flat_i: list[int] = []
    one_way: dict[int, int] = {}
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
        # ONE-WAY (RULINGS 2026-09-09b (2)/(3)): the row governs its
        # ``follows`` vertex and treats its other feet — the PAVEMENT — as
        # given.  A row whose follower is itself fixed governs nothing and
        # stays two-way.
        fv = getattr(row, "follows", None)
        if fv is not None and ruling_head(row) in ow_heads and red.col[fv] >= 0:
            one_way[len(one)] = int(fv)
        if ruling_head(row) in pf_heads:
            pad_flat_i.append(len(one))
        # A PAD THAT FRONTS PAVEMENT HAS NO DEM DATUM OF ITS OWN (owner
        # RULINGS 2026-09-10l): the vertex a LEVEL row governs follows the
        # pavement's edge, so §9b drops it from every body's mean.
        if fv is not None and ruling_head(row) in pl_heads:
            pad_follow.add(int(fv))
        one.append(side)
    for side in eqs_t:
        vs = {v for v, _c in side[0]}
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        eqs.append(side)
    rep.bank_rows = dropped_bank
    rep.hard_rows = len(hard)
    rep.one_way_rows = len(one_way)
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

    # 9b. THE PER-BODY DATUM (owner RULINGS 2026-09-09p (3), refining 08t
    #     answer 6).  Bending alone has an AFFINE null space: it shapes a
    #     body but says nothing about where the body SITS, so an apron up
    #     the hill was levelled toward the runway through its contacts and
    #     the taxiway serving it flattened — the whole complex cut into the
    #     hill (the owner's CYXY read: taxiway G "not sloping up enough").
    #     Every APRON BODY takes ONE row — the MEAN of its own vertices
    #     against the MEAN production DEM under them, at ``body_datum``.
    #     ONE row, NEVER per vertex: the datum fixes the body's LEVEL and
    #     leaves its designed shape (and its tilt) to the bending term, so
    #     bodies sit where the ground is and the taxiways climb between
    #     them at their own caps.  The runway and taxi families are
    #     excluded — they carry the threshold chord and the taxi design
    #     profile, which ARE their datums.
    #     ``detached_mean`` is SUBSUMED in effect for an apron body (the
    #     same DEM under the same vertices); it is not deleted, because it
    #     is also what anchors the TILT of a component nothing else holds,
    #     which one mean row cannot do.
    #     THE ROW IS DENSE IN ``AᵀA`` (RULINGS 2026-09-09r (1)): a mean over
    #     ``N`` vertices is a rank-1 ``N × N`` block, ``O(Σ N_body²)`` to
    #     factorise (HECA: +76 s).  These rows are therefore accumulated
    #     SEPARATELY and handed to the linear solve as the low-rank term
    #     ``U`` — the same algebra, never the block (:data:`LOW_RANK_MODES`).
    #     THE VERTEX SET IS SHAPE MEMBERSHIP (RULINGS 2026-09-09v), never
    #     the ring vertices of the body's faces: a road along a boundary
    #     belongs to the shape it is welded to (08r-2), so its far-edge
    #     vertices — which ARE ring vertices of the NEIGHBOUR's faces —
    #     are dropped from the neighbour's mean, and the neighbour's datum
    #     no longer pulls the road off its level (:func:`_shape_bodies`,
    #     which also records what taking the BODIES from the partition
    #     measured at CYXY).
    #     A PAD THAT FRONTS PAVEMENT HAS NO DEM DATUM OF ITS OWN (owner
    #     RULINGS 2026-09-10l, 10k-1 = (A) "Pad takes the apron edge
    #     level"): a rigid role is a value role, so a pad IS an apron body
    #     (or, welded to one, part of it) and its vertices used to pull the
    #     body's mean toward the BUILDING's terrain.  Every vertex a
    #     ``pad_level_rulings`` row governs is dropped here: its level is
    #     its frontage's, not the ground's.  A pad that fronts NO pavement
    #     mints no such row and keeps its datum, exactly as ruled.
    body = _Rows(red)
    for vs_b in _shape_bodies(planar, red,
                              _role_bodies_faced(planar, apron_roles(law), red)):
        vs_b = [v for v in vs_b if v not in pad_follow]
        zs = [float(planar.vertices[v].dem_z) for v in vs_b]
        if not zs:
            continue
        w = 1.0 / len(vs_b)
        body.add([(v, w) for v in vs_b], sum(zs) / len(zs), d.body_datum,
                 ("body_datum", vs_b[0]))
    rep.body_datum_rows = body.n
    return Base(rows, red, one, eqs, n, hard, pad_flat_i, one_way,
                chord_v, road_v, body)


def solve_design(planar: PlanarMap, cs: ConstraintSet, law: Law,
                 options: Options | None = None, *,
                 size_out: dict | None = None,
                 method: str = DEFAULT_METHOD,
                 low_rank: str = DEFAULT_LOW_RANK) -> tuple[Solution, DesignReport]:
    """The whole design surface (module docstring).  Returns the solution
    and the residual report; the solve is never infeasible."""
    opt = options or Options()
    d = design_law(law)
    rep = DesignReport(method=method)
    t0 = time.perf_counter()
    n = len(planar.vertices)
    base_p = assemble(planar, cs, law, rep)
    rows, red, one, eqs = base_p.rows, base_p.red, base_p.one, base_p.eqs
    chord_v, road_v = base_p.chord_vertices, base_p.road_fit_vertices
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
    # THE PER-BODY DATUM as the LOW-RANK term (RULINGS 2026-09-09r (1)): one
    # row per body, never factorised — ``_linear_solve`` applies it by the
    # Woodbury identity (:data:`LOW_RANK_MODES`).
    Ub, cb = ((base_p.body.matrix(red.n_cols)) if base_p.body is not None
              and base_p.body.n else (None, None))
    A1, b1 = _one_matrix(one, red)
    # THE ONE-WAY SPLIT (RULINGS 2026-09-09b (2)/(3)).  A corridor row
    # ``z_ground − z_foot ≤ bound`` priced two-way pulls the PAVEMENT down
    # toward the ground it is meant to shape.  For a one-way row only the
    # FOLLOWER's column stays in ``A1``; its leader coefficients move to
    # ``A1_lead``, whose product with the previous outer round's ``x``
    # enters the right-hand side through ``shift`` — the ground follows,
    # the pavement never feels it.  The lag is iterated to a fixed point
    # (``one_way_max_rounds`` / ``one_way_tol_m``), exactly as the hard
    # rows' multipliers are.
    ow_i = np.asarray(sorted(base_p.one_way), dtype=np.int64)
    A1_lead: sp.csr_matrix | None = None
    if ow_i.size:
        fcol = np.full(len(one), -2, dtype=np.int64)
        for k, v in base_p.one_way.items():
            fcol[k] = int(red.col[v])
        coo = A1.tocoo()
        lead = (fcol[coo.row] != -2) & (coo.col != fcol[coo.row])
        A1_lead = sp.csr_matrix((coo.data[lead], (coo.row[lead], coo.col[lead])),
                                shape=A1.shape)
        keep = ~lead
        A1 = sp.csr_matrix((coo.data[keep], (coo.row[keep], coo.col[keep])),
                           shape=A1.shape)
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
    # THE PAD TARGETS FLAT (owner RULINGS 2026-09-09c): its flatness rows are
    # priced at ``pad_flat``, above the law's target weight and far below the
    # hard constraint weight — flat wherever a flat solution exists, tilting
    # (to at most the 1 % hard ceiling) where the contacts leave none.
    pad_i = np.asarray(base_p.pad_flat, dtype=np.int64)
    if pad_i.size:
        w_row[pad_i] = float(d.pad_flat)
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
            rep.rows = int(A.shape[0]) + (0 if Ub is None else int(Ub.shape[0]))
            t1 = time.perf_counter()
            x_full = _linear_solve(A, b, x_, method, float(d.solver_tol),
                                   int(d.solver_max_iter), Ub, cb, low_rank)
            x_ = x_full
            t_solver += time.perf_counter() - t1
            # DAMPING (a semismooth Newton step with a backtracking line search
            # on the TRUE objective): the plain fixed point can cycle between
            # two active sets, and a cycling set is not a solution.  ``F`` is
            # convex and C¹, so a step that does not decrease it is halved.
            if x_prev is not None:
                f_new = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
                alpha = 1.0
                while f_new > f_prev and alpha > _ALPHA_FLOOR:
                    alpha *= 0.5
                    x_ = x_prev + alpha * (x_full - x_prev)
                    f_new = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
                if f_new > f_prev:
                    x_ = x_prev          # the step buys nothing: this is it
                    rep.converged = True
                    rep.rounds += rnd
                    return x_
                f_prev = f_new
            else:
                f_prev = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
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

    # THE WARM-UP: the one-way rows are OFF for the first solve (their
    # leaders have no value yet), then lagged from the surface it gives.
    if ow_i.size:
        shift[ow_i] = -_LAG_OFF
        rep.one_way_settled = False
    x = _inner(None)

    # PHASE B — THE LAG (RULINGS 2026-09-09b (2)/(3)).  The one-way rows'
    # leader feet are re-read from the current surface, UNDER-RELAXED by
    # ``one_way_relax`` (the plain fixed point does not contract: measured
    # HECA, the worst leader move sat at 0.25-0.29 m over six rounds), and
    # the inner set is re-solved.  It runs to settlement BEFORE the hard
    # rows' multipliers, so the augmented Lagrangian sees a problem that
    # stops moving under it — interleaved, each lag round undid the
    # previous multiplier round and the runway laws drifted OUT (measured
    # HECA: a 0.52 m ``runway_transverse`` DEFECT).
    theta = float(d.one_way_relax)
    for outer in range(1, (int(d.one_way_max_rounds) if ow_i.size else 0) + 1):
        target = np.asarray(A1_lead @ x).ravel()[ow_i]
        cur = shift[ow_i]
        new_shift = target if outer == 1 else cur + theta * (target - cur)
        move = math.inf if outer == 1 else float(np.max(np.abs(new_shift - cur)))
        shift[ow_i] = new_shift
        rep.one_way_rounds = outer
        rep.one_way_move_m = 0.0 if move == math.inf else move
        x = _inner(x)                  # always solve AT the shift just set
        if opt.verbose:
            print(f"    [design/lag] round {outer}: worst leader move "
                  f"{rep.one_way_move_m:.4f} m")
        if move <= float(d.one_way_tol_m):
            rep.one_way_settled = True
            break

    # PHASE C — THE HARD ROWS' MULTIPLIERS, the lag now FROZEN (spec §6
    # deviation 7).  THE HARD SET MUST SETTLE (owner RULINGS 2026-09-09r
    # (3)): the loop runs until every hard row is within ``hard_tol_m`` or
    # until ``polish_rounds_max`` rounds are spent.  A round that buys less
    # than one tolerance of violation NO LONGER ENDS IT (round 1's rule):
    # measured, the multiplier sequence is not monotone — it oscillates
    # while the one-sided active set around it re-forms (m3c road fixture:
    # 0.050, 0.039, 0.058, 0.040, 0.019 m) — so the first flat round is
    # nowhere near the answer.  The BEST iterate is kept and returned.
    # Exhausting the cap is a NAMED FAILURE in the report, never a silent
    # "not settled" in a shipped patch.
    if hard_i.size:
        Ah, bh = A1[hard_i], b1[hard_i]
        mu = np.zeros(hard_i.size)
        tol_h = float(d.hard_tol_m)
        worst = float(np.max(np.maximum(Ah @ x - bh, 0.0)))
        best_x, best_worst = x, worst
        for pr in range(1, int(d.polish_rounds_max) + 1):
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
                      f"{int(np.count_nonzero(mu > 0.0))} hard rows carry a "
                      f"multiplier, max hard violation {worst:.5f} m")
            if worst <= tol_h:
                break
        if best_worst < worst:
            x, worst = best_x, best_worst      # never return a worse surface
        rep.hard_active = int(np.count_nonzero(mu > 0.0))
        rep.hard_max_violation_m = worst
        rep.hard_settled = worst <= tol_h
        if worst > tol_h:
            k = int(np.argmax(Ah @ x - bh))
            rep.hard_worst = one[int(hard_i[k])][2].source.ruling[:70]
    # PHASE D — THE FINAL PROJECTION (owner RULINGS 2026-09-09y, closing
    # 09v (3)).  The augmented Lagrangian above cannot CERTIFY the hard set,
    # and at HECA its residual landed on runway rows the DEFECT gate refuses.
    # Every non-runway vertex is now FIXED at its solved z and the runway
    # family's vertices are re-solved as a small QP holding every
    # runway-family hard row exactly (``solve/project.py``); the rows the
    # surrounding sheet states on runway vertices are re-read below as
    # REPORT FIGURES, which is exactly what the ruling asks of them.
    if x is not None:
        x, rep.runway_projection = project_runway(planar, law, base_p, x,
                                                  stacked=(A1, b1),
                                                  verbose=opt.verbose)
        # the HARD SET's reading is of the SHIPPED surface, so it is re-read
        # after the projection: the rows it owns are now held exactly, and
        # what is left is what it does not own (a pad plane, a hard row with
        # no runway vertex on it).
        if hard_i.size:
            v_h = np.maximum(A1[hard_i] @ x - b1[hard_i], 0.0)
            worst = float(np.max(v_h))
            rep.hard_max_violation_m = worst
            rep.hard_settled = worst <= float(d.hard_tol_m)
            rep.hard_worst = ("" if rep.hard_settled else
                              one[int(hard_i[int(np.argmax(v_h))])][2].source.ruling[:70])
    if x is not None:
        z = np.where(red.col >= 0, x[np.clip(red.col, 0, None)], red.value)
    rep.solver_wall_s = t_solver

    # 11. the residual per family (a missed TARGET, not a demotion)
    fam: dict[str, dict[str, _t.Any]] = {}
    # the REPORTED violation is the row's TRUE one — the one-way rows'
    # leader columns are back for the reading (they are lagged only in the
    # matrix the solve factorises)
    viol_all = (A1 @ x - b1) if x is not None else np.zeros(len(one))
    if x is not None and A1_lead is not None:
        viol_all = viol_all + np.asarray(A1_lead @ x).ravel()
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
    if Ub is not None and x is not None:
        rep.terms["body_datum"] = round(float(np.sum((Ub @ x - cb) ** 2)), 3)
        rep.terms = dict(sorted(rep.terms.items()))
    if size_out is not None:
        size_out.update({"columns": red.n_cols, "z": n, "rows": rep.rows,
                         "nnz": int(A.nnz), "triangles": rep.triangles,
                         "chord_vertices": chord_v, "road_fit_vertices": road_v,
                         "one_way_rows": rep.one_way_rows,
                         "active": len(active), "rounds": rep.rounds})
    cert = residual(cs, z, obj)
    wall = time.perf_counter() - t0
    return (Solution(z=tuple(float(v) for v in z),
                     status=Status.OPTIMAL if rep.converged else Status.FEASIBLE,
                     residual=cert, iterations=rep.rounds, wall_s=wall,
                     message=f"design surface: {rep.rounds} active-set round(s), "
                             f"{red.n_cols} unknowns, {rep.rows} rows, "
                             f"{method}"), rep)
