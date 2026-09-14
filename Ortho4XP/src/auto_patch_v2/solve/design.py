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
from ..law.tables import (design as design_law, is_value_role,
                          pavement_roles as _pavement_roles,
                          role_side, zone2_half_width_m, zone_class)
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear, Offset,
                                 Pin, Row)
from ..model.planar import PlanarMap
from .api import Options, Solution, Status
from .linear import (DEFAULT_LOW_RANK, DEFAULT_METHOD, LOW_RANK_MODES,
                     METHODS, _linear_solve, _objective, _term_energies)
from .design_report import DesignReport, foot_row_diagnostic, residual, settled_flip
from .project import ProjectionReport, ZoneClampReport, project_after_solve
from .rows import (_cotangent_laplacian, _face_triangles, _law_sides, _level_free_columns,
                   _one_matrix,
                   apply_level_belt, _plane_rows, _plane_targets, _reduce, _Reduction, _role_bodies,
                   _role_bodies_faced, _Rows, _shape_bodies,
                   _sheet_components, _Side, _violation, _zone_weights)

__all__ = ["DesignReport", "Base", "assemble", "solve_design", "residual",
           "stage_split", "airside_stage_roles", "airside_stage_vertices",
           "bend_roles", "pavement_roles", "bend_class", "apron_roles",
           "taxi_body_roles", "datum_roles", "hard_rulings",
           "one_way_rulings", "pad_flat_rulings", "pad_level_rulings",
           "ground_roles", "ground_datum_vertices", "foot_row_rulings",
           "cluster_reach_rulings",
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


# ── role / ruling readers: ``solve/design_roles`` (the 1,000-line file law) ──
from .design_ground import ground_datum_vertices, ground_roles  # noqa: E402
from .design_roles import (  # noqa: E402  (re-export)
    airside_stage_roles, airside_stage_vertices, bend_roles, pavement_roles, bend_class, apron_roles, taxi_body_roles, datum_roles, one_way_rulings, foot_row_rulings, pad_flat_rulings, pad_level_rulings, cluster_reach_rulings, hard_rulings, ruling_head, is_hard)

@_dc.dataclass(frozen=True)
class _BodyDatum:
    """One body of the PER-BODY DATUM: which family formed it (``apron``,
    :func:`datum_roles`), the vertices its PLANE is fitted over, the MEAN
    PRODUCTION DEM under them and how many of the three plane rows its
    geometry carried (a collinear body carries fewer — RULINGS
    2026-09-10v (2))."""

    kind: str
    vertices: tuple[int, ...]
    dem_mean: float
    rows: int = 1


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
    #: one_way_rulings``): only those COLUMNS keep their place, the leaders
    #: enter the right-hand side lagged (RULINGS 2026-09-09b (2)/(3))
    one_way: dict[int, tuple[int, ...]] = _dc.field(default_factory=dict)
    chord_vertices: int = 0
    road_fit_vertices: int = 0
    #: THE PER-BODY DATUM rows, kept OUT of ``rows`` (RULINGS 2026-09-09r
    #: (1)): each is dense in ``AᵀA``, so they reach the linear solve as
    #: the low-rank term ``U`` (:data:`LOW_RANK_MODES`), never factorised.
    body: "_Rows | None" = None
    #: one record per datum row, in the row order of ``body`` — what the
    #: report reads its residual and its DEM mean from (RULINGS 2026-09-10p)
    body_meta: list["_BodyDatum"] = _dc.field(default_factory=list)
    #: ``one`` indices of the FOOT ROWS (``[design] foot_row_rulings``,
    #: 11ab): priced at ``pad_flat``, the pad law's own target
    foot_row_i: list[int] = _dc.field(default_factory=list)
    #: ``one`` indices of §30 (4)'s CLUSTER APRON REACH (``[design]
    #: cluster_reach_rulings``, owner RULINGS 2026-09-13cc (ii)): priced
    #: at ``apron_trend``, so the taxi family's law rows outrank them
    cluster_reach_i: list[int] = _dc.field(default_factory=list)


def stage_split(planar: PlanarMap, cs: ConstraintSet, law: Law
                ) -> tuple[frozenset[int], dict[int, float]]:
    """§20b STAGE 1's SPLIT: the vertices whose columns are FOREIGN to the
    airside problem, and the dummy values they are fixed at.

    A column is AIRSIDE when any vertex mapped to it is a vertex of an
    airside-pavement face (:func:`airside_stage_vertices`) — the test is on
    the COLUMN, because a rigid ``Flat`` group welded to an apron vertex is
    ONE unknown and the airside's own weld decides it.  Every other FREE
    vertex is foreign: it is fixed (so it carries no column) and every row
    touching it is dropped (``_Rows.drop``), which is the brief's "every row
    whose every column is airside".  A vertex already FIXED — a ``Pin``, a
    threshold, a seam pin (§38) — is never foreign: a constant is not a
    column, and the rows footed on it belong to stage 1 exactly as the law
    states them."""
    red0 = _reduce(planar, cs, {})
    air_v = airside_stage_vertices(planar, law)
    air_cols = {int(red0.col[v]) for v in air_v if red0.col[v] >= 0}
    foreign: dict[int, float] = {}
    for vid in range(len(planar.vertices)):
        col = int(red0.col[vid])
        if col < 0 or col in air_cols:
            continue
        dz = planar.vertices[vid].dem_z
        foreign[vid] = float(dz) if dz is not None else 0.0
    return frozenset(foreign), foreign


def assemble(planar: PlanarMap, cs: ConstraintSet, law: Law,
             rep: DesignReport, *,
             drop: _t.AbstractSet[int] | None = None,
             fixed: _t.Mapping[int, float] | None = None) -> Base:
    """Sections 1-9 of the module docstring: the sheets and their
    triangulation, the zone ramp, the reduction, and every always-on row
    (bending, road chains, the chord, the zone DEM fit, the law's equalities,
    the bodies' own datums).

    §20b THE STAGED SOLVE adds two arguments and nothing else.  ``fixed``
    SUBSTITUTES a vertex's value as a constant — stage 1's foreign vertices
    in stage 1, and every airside vertex stage 1 levelled in stage 2 — by
    the reduction, exactly as a ``Pin`` is substituted, so a row coupling to
    it is one-way BY CONSTRUCTION.  ``drop`` removes every row that touches
    one of its vertices, which is how stage 1 keeps only the rows whose every
    column is airside.  Both default empty: the single solve is unchanged."""
    d = design_law(law)
    n = len(planar.vertices)
    drop_f = frozenset(drop or ())

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

    # 2. the zone ramp.  NOTHING beyond the ring is fixed (09-09b (3)); a
    #    road's or a structure's vertex was never fixed either — it carries
    #    its own law far from any pavement (08t answers 7 and 8).  The
    #    "free" set that computed and DELETED that answer is gone with it
    #    (RULINGS 2026-09-13: a refuted mechanism is deleted, not kept).
    #    The role set is the LAW's own (M0 §1: ``solve`` imports ``law``
    #    and ``model`` only — never ``constraints``).
    rwy_roles = set(law.tables.precedence.runway_family.members)
    ramp = _zone_weights(planar, law, pav)
    rwy_v = {v for v, vx in planar.vertices.items()
             if any(planar.faces[f].role in rwy_roles for f in vx.incident_faces)}

    # 3. the reduction: pins fix, flats merge, the outer ring is the DEM
    #    (§20b: plus the other stage's substituted values)
    red = _reduce(planar, cs, {}, fixed)
    rep.unknowns = red.n_cols
    rep.fixed = int((red.col < 0).sum())
    rows = _Rows(red, drop=drop_f)
    one: list[_Side] = []
    eqs: list[_Side] = []
    chord_v = road_v = trend_v = apron_trend_v = 0
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

    # 5c. THE TAXI CHAIN'S TARGET PROFILE (owner RULINGS 2026-09-10v (1);
    #     spec §8.6).  The second-difference rows above are CURVATURE and
    #     have no level: 10o measured CYXY's 1,664 m parallel extrapolating
    #     its level from its far contact while the ground rose under it, and
    #     10t measured SPJC's `pav49` with the right mean and no TILT.
    #     Every taxi centreline chain therefore carries a TARGET PROFILE —
    #     the ground's LONG-WAVE TREND along that chain, the SAME §21 fit at
    #     the SAME window key, shifted linearly through the chain's runway
    #     contacts — derived in ``constraints/taxi_trend.py`` and published
    #     through ``PlanarMap.taxi_trend_z`` (``solve`` imports ``law`` and
    #     ``model`` only, M0 §1: the derivation cannot live here).  WEAK, at
    #     ``[design] taxi_trend``, below ``body_datum``: it says WHERE the
    #     chain runs, never how smoothly (that is the row above), and every
    #     law outranks it.  A runway-contact vertex carries no target — the
    #     runway owns its value and its contact stays hard.
    for vid, target in planar.taxi_trend_z.items():
        if vid in rwy_v:
            continue
        if rows.add(((vid, 1.0),), float(target), d.taxi_trend,
                    ("taxi_trend", vid)):
            trend_v += 1

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

    # 7. THE GROUND'S OWN DATUM (owner RULINGS 2026-09-10av; spec §23),
    #    re-scoping 09-09b (3)'s "no DEM term" to PAVEMENT.  09b (3) deleted
    #    the DEM from the patch entirely, and a surface built only from
    #    ONE-SIDED rows has no LEVEL: CYXY's 14R/32L end corridor cut 1.9 m
    #    into lawful natural ground (strip 700.1 where the DEM is 701.96) and
    #    a 45 % cut bank climbed back to a foot correctly on the DEM.
    #    Every ADJACENT-GROUND vertex — the ``graded_strip`` family, never a
    #    pavement vertex, never an interior pocket enclosed by pavement
    #    (09g (1)) — carries ONE WEAK row ``z = DEM(v)`` at ``[design]
    #    ground_datum``.  Its law rows are UNCHANGED: one-sided and ONE-WAY
    #    (``follows = v``, §8 above), so the ground follows its pavement and
    #    never pulls it, and the pavement keeps no DEM pull of its own
    #    (08t (1)).  Where the ground already satisfies the zone law no row
    #    is active and the datum is the only term with a level, so the strip
    #    EQUALS the natural ground; where a law row binds, ``law`` (300)
    #    outprices the datum (3) and the strip is cut or filled TO THE LAW
    #    LINE and no further.  The bank then starts from a ring already on
    #    the DEM and vanishes there (``daylight_feet`` resolves at
    #    ``bank_min_width_m``, zero drop, by the walk it already runs).
    #    THE ONE-WAY GUARANTEE (spec §23.3): the row carries exactly ONE
    #    column — v's — and v is never a pavement vertex, so the pavement's
    #    normal equations gain no row and no right-hand side; the coupling
    #    rows are stripped of their leader columns by the one-way lag; and
    #    the only channel left, the shared bending stencil, is a SECOND
    #    DIFFERENCE that annihilates any affine field, so a rigid level or
    #    tilt the datum gives a strip transmits exactly zero.
    #    THE VERTEX SET IS DERIVED ONCE (``solve/design_ground``): ``why``
    #    names the terminal from the same function.
    ground = ground_datum_vertices(planar, law)
    ground_v = 0
    for vid in sorted(ground):
        dz = planar.vertices[vid].dem_z
        if dz is None:
            continue
        if rows.add(((vid, 1.0),), float(dz), d.ground_datum,
                    ("ground_datum", vid)):
            ground_v += 1
    rep.ground_datum_rows = ground_v

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
    pf_heads, fr_heads = pad_flat_rulings(law), foot_row_rulings(law)
    cr_heads = cluster_reach_rulings(law)
    pl_heads = pad_level_rulings(law)
    #: the pad vertices a LEVEL row governs (owner RULINGS 2026-09-10l):
    #: they follow the pavement they front and carry no DEM datum (§9b)
    pad_follow: set[int] = set()
    hard: list[int] = []
    pad_flat_i: list[int] = []
    foot_i: list[int] = []   # the FOOT ROWS at ``pad_flat`` (11ab)
    reach_i: list[int] = []  # §30 (4)'s reach at ``apron_trend`` (13cc)
    one_way: dict[int, tuple[int, ...]] = {}
    #: the vertices a LAW EQUALITY GOVERNS (owner RULINGS 2026-09-10ba): a
    #: basin floor is no longer PINNED — it is tied to its rim by a relative
    #: equality — so §9 must read it as ANCHORED, or the floor sheet counts
    #: as detached and takes a DEM plane of its own beside that row.
    hard_follow: set[int] = set()
    stage_dropped = 0
    for side in one_t:
        terms, hi, row = side
        vs = {v for v, _c in terms}
        if vs & drop_f:               # §20b: not this stage's problem
            stage_dropped += 1
            continue
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
        fvs = ((int(fv),) if isinstance(fv, int)
               else tuple(int(v) for v in fv) if fv is not None else ())
        if fvs and ruling_head(row) in ow_heads:
            # THE FOLLOWER MAY BE A SET (owner RULINGS 2026-09-10y): a pad
            # PLANE has three degrees of freedom, so the row that levels it
            # keeps three columns.  A follower with no column of its own is
            # fixed and simply keeps none.
            cols = tuple(sorted({int(red.col[v]) for v in fvs
                                 if red.col[v] >= 0}))
            if cols:
                one_way[len(one)] = cols
        head = ruling_head(row)
        (pad_flat_i if head in pf_heads
         else foot_i if head in fr_heads
         else reach_i if head in cr_heads else []).append(len(one))
        # A PAD THAT FRONTS PAVEMENT HAS NO DEM DATUM OF ITS OWN (owner
        # RULINGS 2026-09-10l): every vertex a LEVEL row governs — the whole
        # pad plane (10y), not just the feet the row mentions — follows the
        # pavement's edge, so §9b drops it from every body's mean.  The
        # register (``pad_level_rulings``) is what makes that a LAW read and
        # not a second derivation of "which pad fronts what".
        if fvs and ruling_head(row) in pl_heads:
            pad_follow.update(fvs)
        one.append(side)
    for side in eqs_t:
        vs = {v for v, _c in side[0]}
        if vs & drop_f:               # §20b: not this stage's problem
            stage_dropped += 1
            continue
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        fv_e = getattr(side[2], "follows", None)
        if fv_e is not None:
            hard_follow.update((int(fv_e),) if isinstance(fv_e, int)
                               else (int(v) for v in fv_e))
        eqs.append(side)
    rep.bank_rows = dropped_bank
    rep.stage_dropped_rows = stage_dropped
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
    #    (This graph OVERSTATES the objective's — ``rows._sheet_components``.)
    comp = _sheet_components(tris, red)
    rep.components = len(set(comp.values()))
    anchored: set[int] = set()
    for vid in range(n):
        col = int(red.col[vid])
        if col < 0:                                   # a pin / the DEM beyond
            continue
        if vid in pref or vid in ground or ramp.get(vid, 0.0) > 0.0:
            anchored.add(comp[col])
    for vid in hard_follow:                           # a HARD row anchors too
        col = int(red.col[vid])
        if col >= 0:
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

    # 9a.  THE APRON BODY'S TARGET SURFACE (owner RULINGS 2026-09-10ar; spec
    #     §8.7).  9b below gives an apron body three AFFINE rows, so its
    #     least-squares PLANE follows the ground's — but over a body larger
    #     than the fit window a plane has no LOCAL reach: LEMD's T4S apron
    #     is one 439 x 1,242 m body whose plane was satisfied while its pit
    #     CORNER sat 1.2 m under its own DEM.  Such a body takes ONE row per
    #     vertex against the ground's 2-D LONG-WAVE TREND under it, derived
    #     in ``constraints/apron_trend.py`` and published through
    #     ``PlanarMap.apron_trend_z`` (``solve`` imports ``law`` and
    #     ``model`` only, M0 §1), and NO affine rows (9b reads the same
    #     channel, so ONE gate decides both).  WEAK, at ``[design]
    #     apron_trend``: it says WHERE the apron sits, and every law row is
    #     senior.  A PAD FOLLOWING ITS FRONTAGE takes no trend row, exactly
    #     as it takes no datum row (10l) — the register is known here, so
    #     the drop happens here.
    for vid, target in planar.apron_trend_z.items():
        if vid in rwy_v or vid in pad_follow:
            continue
        if rows.add(((vid, 1.0),), float(target), d.apron_trend,
                    ("apron_trend", vid)):
            apron_trend_v += 1

    # 9b. THE PER-BODY DATUM IS THE GROUND'S PLANE (owner RULINGS
    #     2026-09-09p (3), refining 08t answer 6; the AFFINE fit ruled in
    #     2026-09-10t (1) and 2026-09-10v (2)).  Bending alone has an
    #     AFFINE null space: it shapes a body but says nothing about where
    #     the body SITS or which way it TILTS.  09p closed the level — one
    #     mean row per apron body — and 10t measured what the level alone
    #     leaves open at SPJC: over `pav49`'s 2,010 vertices mean z − mean
    #     DEM was −0.39 m while the profile ran +0.99 → −6.65 → −4.71 m
    #     against the ground, a straight ramp under a rising hill.  The
    #     error is a missing TILT — the first moments, second order, not
    #     the level.
    #     Every APRON BODY therefore takes THREE weak rows at
    #     ``body_datum``: its MEAN, and its two FIRST MOMENTS against the
    #     same moments of the production DEM under its own vertices — i.e.
    #     the body's own least-squares PLANE follows the plane fitted to
    #     the ground beneath it, level AND tilt.  THREE rows, never per
    #     vertex (08t (1)): a plane has zero bending energy, so this datum
    #     never fights the designed shape within the body — only where the
    #     body sits and how it leans.
    #     THE MOMENT ROWS ARE ORTHOGONALISED (Gram-Schmidt on the centred
    #     plan coordinates) so the three functionals are independent and
    #     matching them IS matching the least-squares plane exactly; each
    #     is scaled by the body's own RMS half-extent so its residual reads
    #     in METRES — the rise of the plane over that radius — and the
    #     three rows are commensurate with each other and with the weight.
    #     A body whose vertices are collinear (or fewer than three) carries
    #     only the rows its geometry supports: a degenerate moment row is
    #     dropped, never given an invented value.
    #     TAXI BODIES CARRY NO DATUM ROW (owner RULINGS 2026-09-10v,
    #     replacing 10p): the taxi family's level and tilt come from its
    #     CHAIN'S TREND (step 5c) — along the route, where the ground
    #     actually varies — because a taxi body is the whole connected taxi
    #     network and one plane over an airport is no better than one mean.
    #     The RUNWAY family stays excluded (its profile and pins are its
    #     datum), and a runway contact stays hard: the final projection
    #     (``solve/project.py``) absorbs any conflict into non-runway
    #     vertices.
    #     ``detached_mean`` is SUBSUMED in effect for an apron body (the
    #     same plane under the same vertices); it is not deleted, because
    #     it is also what anchors a component nothing else holds.
    #     THE ROWS ARE DENSE IN ``AᵀA`` (RULINGS 2026-09-09r (1)): each is a
    #     rank-1 ``N × N`` block, so they are accumulated SEPARATELY and
    #     handed to the linear solve as the low-rank term ``U`` — the same
    #     algebra, never the block (:data:`LOW_RANK_MODES`).  Three rows per
    #     body instead of one triples that term's RANK, not the solve's
    #     size.
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
    body = _Rows(red, drop=drop_f)
    meta: list[_BodyDatum] = []
    for kind, roles_b in datum_roles(law):
        for vs_b in _shape_bodies(planar, red,
                                  _role_bodies_faced(planar, roles_b, red)):
            # 10l: a pad that fronts pavement takes its frontage's level, not
            # the ground's — its vertices leave every body's datum fit
            vs_b = [v for v in vs_b if v not in pad_follow]
            zs = [float(planar.vertices[v].dem_z) for v in vs_b]
            if not zs:
                continue
            # THE BODY'S EXTENT DECIDES (spec §8.7 (2)): a body larger than
            # the fit window carries the 2-D TREND at every vertex (5d) and
            # NO plane.  The gate itself lives at the one derivation site
            # (``constraints/apron_trend``); here the published channel IS
            # the decision, so the two can never disagree.  The solve's own
            # body is a SUBSET of that module's (it also drops fixed
            # columns, DEM-less vertices and foreign shape members), so one
            # touched vertex identifies the body.
            if any(v in planar.apron_trend_z for v in vs_b):
                continue
            mean_dem = sum(zs) / len(zs)
            added = 0
            for name, coefs, rhs in _plane_rows(planar, vs_b, zs):
                if body.add(coefs, rhs, d.body_datum,
                            ("body_datum", (vs_b[0], name))):
                    added += 1
            if added:
                meta.append(_BodyDatum(kind=kind, vertices=tuple(vs_b),
                                       dem_mean=mean_dem, rows=added))
    # 9c. THE LEVEL BELT (RULINGS 2026-09-13, ``v2zerocrater``; spec §23.4):
    #     a column with no LEVEL solves to the sentinel 0 — KCLT's crater.
    rep.level_belt_rows = apply_level_belt(planar, rows, body, red, one, d.detached_mean)
    rep.taxi_trend_rows = trend_v
    rep.apron_trend_rows = apron_trend_v
    rep.body_datum_rows = body.n
    rep.body_datum_bodies = len(meta)
    rep.foot_rows = len(foot_i)
    return Base(rows, red, one, eqs, n, hard, pad_flat_i, one_way,
                chord_v, road_v, body, meta, foot_row_i=foot_i,
                cluster_reach_i=reach_i)


def solve_design(planar: PlanarMap, cs: ConstraintSet, law: Law,
                 options: Options | None = None, *,
                 size_out: dict | None = None,
                 method: str = DEFAULT_METHOD,
                 low_rank: str = DEFAULT_LOW_RANK) -> tuple[Solution, DesignReport]:
    """THE DESIGN SURFACE, in ONE stage or TWO (§20b).

    ``[design] staged_solve`` false is the single solve this module has
    always been: one problem, one report.  True is §20b THE STAGED SOLVE
    (owner RULINGS 2026-09-13dh, ordered 14an) — "airside solves first,
    everything else conforms" as an ARCHITECTURE and not a price:

      stage 1  the AIRSIDE PAVEMENT problem alone (:func:`stage_split`):
               its columns, every row whose every column is one of them,
               its own polish and BOTH projections.  What it returns is the
               certified airside surface.
      stage 2  the WHOLE problem with every airside column stage 1 LEVELLED
               substituted as a constant (the reduction eliminates it,
               exactly as a ``Pin``).  A pad / road / ground row coupling to
               airside then has a CONSTANT on its airside side: one-way by
               construction, no lag, no skirt, and airside moved between the
               stages is zero BY CONSTRUCTION.

    The returned ``z`` is stage 2's (airside values ARE stage 1's), the
    status the worse of the two, the report stage 2's with stage 1's
    counters in ``stages`` and the hard set COMBINED (§20b's census table).
    """
    if not bool(design_law(law).staged_solve):
        return _solve_stage(planar, cs, law, options, size_out=size_out,
                            method=method, low_rank=low_rank)
    t_all = time.perf_counter()
    rep1 = DesignReport(method=method)
    size1: dict = {}
    drop, foreign = stage_split(planar, cs, law)
    levels: dict[int, float] = {}
    t1 = time.perf_counter()
    sol1, rep1 = _solve_stage(planar, cs, law, options, size_out=size1,
                              method=method, low_rank=low_rank,
                              drop=drop, fixed=foreign, levelled_out=levels)
    w1 = time.perf_counter() - t1
    t2 = time.perf_counter()
    sol2, rep2 = _solve_stage(planar, cs, law, options, size_out=size_out,
                              method=method, low_rank=low_rank, fixed=levels)
    w2 = time.perf_counter() - t2
    rep2.staged = True
    rep2.stage1_wall_s, rep2.stage2_wall_s = w1, w2
    rep2.stage1_fixed = len(levels)
    rep2.stage1_unlevelled = rep1.stage1_unlevelled
    rep2.stage_dropped_rows = rep1.stage_dropped_rows
    rep2.stages = {"stage1": dict(rep1.as_dict(), wall_s=round(w1, 3),
                                  projection_line=rep1.runway_projection.line(),
                                  lag_line=(rep1.lag_failure_line()
                                            if not rep1.one_way_settled else "")),
                   "stage2": {"unknowns": rep2.unknowns, "rows": rep2.rows,
                              "hard_rows": rep2.hard_rows,
                              "hard_active": rep2.hard_active,
                              "hard_max_violation_m": round(rep2.hard_max_violation_m, 6),
                              "hard_settled": rep2.hard_settled,
                              "rounds": rep2.rounds, "wall_s": round(w2, 3)}}
    # THE HARD SET IS THE COMBINATION (§20b's census table): an airside hard
    # row carries no column in stage 2 — it was enforced and read in stage 1,
    # where it is scaled to metres — so the shipped surface's hard set is
    # stage 1's plus stage 2's, and SETTLED is the conjunction.
    rep2.hard_rows += rep1.hard_rows
    rep2.hard_active += rep1.hard_active
    rep2.hard_rounds += rep1.hard_rounds
    if rep1.hard_max_violation_m > rep2.hard_max_violation_m:
        rep2.hard_max_violation_m = rep1.hard_max_violation_m
        rep2.hard_worst = rep1.hard_worst
    rep2.hard_settled = bool(rep1.hard_settled and rep2.hard_settled)
    if size_out is not None:
        size_out.update({"stage1_columns": size1.get("columns", 0),
                         "stage1_rows": size1.get("rows", 0),
                         "stage1_fixed_into_stage2": len(levels)})
    status = (Status.ERROR if Status.ERROR in (sol1.status, sol2.status)
              else Status.FEASIBLE if Status.FEASIBLE in (sol1.status, sol2.status)
              else sol2.status)
    sol = _dc.replace(sol2, status=status,
                      iterations=sol1.iterations + sol2.iterations,
                      wall_s=time.perf_counter() - t_all,
                      message=f"staged design surface (20b): stage 1 {sol1.message}; "
                              f"stage 2 {sol2.message}")
    return sol, rep2


def _solve_stage(planar: PlanarMap, cs: ConstraintSet, law: Law,
                 options: Options | None = None, *,
                 size_out: dict | None = None,
                 method: str = DEFAULT_METHOD,
                 low_rank: str = DEFAULT_LOW_RANK,
                 drop: _t.AbstractSet[int] | None = None,
                 fixed: _t.Mapping[int, float] | None = None,
                 levelled_out: dict[int, float] | None = None
                 ) -> tuple[Solution, DesignReport]:
    """ONE solve of the design surface (module docstring) — the whole thing
    when ``staged_solve`` is off, one stage of §20b when it is not.

    ``drop`` / ``fixed`` are :func:`assemble`'s.  ``levelled_out`` collects
    §20b (4)'s answer for the next stage: the solved value of every vertex
    whose column carried an ALWAYS-ON row (bending, chord, trend, datum,
    level belt) — a column with none has no level here and is left free.
    """
    opt = options or Options()
    d = design_law(law)
    rep = DesignReport(method=method)
    t0 = time.perf_counter()
    n = len(planar.vertices)
    base_p = assemble(planar, cs, law, rep, drop=drop, fixed=fixed)
    rows, red, one, eqs = base_p.rows, base_p.red, base_p.one, base_p.eqs
    # §20b (4): a column with NO LEVEL is not this stage's answer.  The level
    # belt (§23.4) normally leaves none — it gives every level-free piece its
    # own terrain plane or refuses by name — so this reads 0 and is the guard
    # that keeps a sentinel 0.0 m from being SUBSTITUTED into the next stage.
    unlevelled: set[int] = set()
    if levelled_out is not None:
        unlevelled = set(_level_free_columns(rows, base_p.body, red, one))
        rep.stage1_unlevelled = len(unlevelled)
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
        # THE FOLLOWER IS A COLUMN SET (owner RULINGS 2026-09-10y): a pad
        # plane's three degrees of freedom cannot be one column, so the
        # split is by (row, column) MEMBERSHIP, not by a single column id.
        is_ow = np.zeros(len(one), dtype=bool)
        is_ow[ow_i] = True
        ncol = int(red.n_cols)
        keep_keys = np.array(sorted({int(k) * ncol + int(c)
                                     for k, cs in base_p.one_way.items()
                                     for c in cs}), dtype=np.int64)
        coo = A1.tocoo()
        key = coo.row.astype(np.int64) * ncol + coo.col.astype(np.int64)
        lead = is_ow[coo.row] & ~np.isin(key, keep_keys)
        A1_lead = sp.csr_matrix((coo.data[lead], (coo.row[lead], coo.col[lead])),
                                shape=A1.shape)
        keep = ~lead
        A1 = sp.csr_matrix((coo.data[keep], (coo.row[keep], coo.col[keep])),
                           shape=A1.shape)
    hard_i = np.asarray(base_p.hard, dtype=np.int64)
    if fixed and drop is None and hard_i.size:
        # §20b STAGE 2's HARD SET (the census table): an AIRSIDE hard row
        # now carries no column — stage 1 enforced it and read it there, in
        # its own metre scaling — and its reduced row sum is 0, which the
        # scaling below cannot divide by.  Reading it here would report a
        # vertical-curve row in RAW units against ``hard_tol_m``.  Stage 2's
        # hard set is the rows that still carry a column; the report
        # COMBINES the two stages.
        rowsum0 = np.asarray(abs(A1).sum(axis=1)).ravel()
        hard_i = hard_i[rowsum0[hard_i] > 0.0]
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
    # THE FOOT ROWS ARE THE PAD LAW'S TARGET (owner RULINGS 2026-09-11ab,
    # spec §11b (2)): a body with no pad polygon states its placement
    # through its feet, so those rows pay the PAD's price, not the ADJACENT
    # GROUND's (round 7 at 3.0: 715 of 1,434 missed, 5.70 m; pair bar kept).
    fr_i = np.asarray(base_p.foot_row_i, dtype=np.int64)
    if fr_i.size:
        w_row[fr_i] = float(d.pad_flat)
    # §30 (4) THE CLUSTER PAD'S APRON REACH (owner RULINGS 2026-09-13cc
    # (ii)): the APRON TREND's own design-target weight, an order BELOW
    # the law's, so the taxi family's law rows always outrank it and the
    # reach yields exactly where the owner said it must.
    cr_i = np.asarray(base_p.cluster_reach_i, dtype=np.int64)
    if cr_i.size:
        w_row[cr_i] = float(d.apron_trend)
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

    def _settled(x_):    # §30 (3c): ONE derivation, ``design_report.settled_flip``
        return settled_flip(A1 @ x_ - (b1 - shift), tol, active)

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
                    rep.converged = rep.record_flip(_settled(x_))
                    rep.rounds += rnd
                    return x_
                f_prev = f_new
            else:
                f_prev = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
            x_prev = x_.copy()
            viol = A1 @ x_ - (b1 - shift)
            nxt_i = np.flatnonzero(viol > tol)
            nxt = set(nxt_i.tolist())
            # SETTLED (§30 (3c), ONE derivation in ``_settled``): the same set,
            # or a flip every row of which hovers at its own bound.  The
            # objective STALLING is an exit, NOT settlement — it fires with
            # thousands of rows still crossing their bounds by metres.
            if nxt == active or (f_prev < math.inf and
                                 abs(f_last - f_prev) <= 1e-6 * max(1.0, f_prev)):
                rep.converged = rep.record_flip(_settled(x_))
                rep.rounds += rnd
                return x_
            if opt.verbose:
                print(f"    [design] round {rnd}: F {f_prev:.6g}  active {len(nxt)} "
                      f"(was {len(active)}, changed {len(nxt ^ active)})")
            f_last = f_prev
            active, active_i = nxt, nxt_i
        rep.converged = False            # the round cap: NEVER settlement
        rep.record_flip(_settled(x_) if x_ is not None else (False, 0, 0.0))
        rep.rounds += int(d.active_set_max_rounds)
        return x_ if x_ is not None else np.zeros(red.n_cols)

    # THE WARM-UP: the one-way rows are OFF for the first solve (their
    # leaders have no value yet), then lagged from the surface it gives.
    if ow_i.size:
        shift[ow_i] = -_LAG_OFF
        rep.one_way_settled = False
    x = _inner(None)

    # PHASE B — THE LAG IS A CONVERGENCE CONDITION (09-09b (2)/(3); §20a,
    # RULINGS 2026-09-13ac).  The one-way leaders are re-read from the
    # surface, UNDER-RELAXED by ``one_way_relax`` (the plain fixed point
    # does not contract), and the set re-solved — to ``one_way_tol_m`` or
    # to a NAMED failure, always BEFORE the multipliers (interleaved, each
    # lag round undid the previous one and the runway laws drifted OUT:
    # HECA, a 0.52 m ``runway_transverse`` DEFECT).  ``one_way_max_rounds``
    # is a SAFETY CEILING, and its hit is that named failure: the polish
    # ran inside an unconverged lag at LEMD and the wobble crossed
    # ``hard_tol_m`` (13ac).
    theta = float(d.one_way_relax)
    dmove = np.zeros(0)
    for outer in range(1, (int(d.one_way_max_rounds) if ow_i.size else 0) + 1):
        target = np.asarray(A1_lead @ x).ravel()[ow_i]
        cur = shift[ow_i]
        new_shift = target if outer == 1 else cur + theta * (target - cur)
        dmove = (np.abs(new_shift - cur) if outer > 1
                 else np.full(ow_i.size, math.inf))
        move = float(np.max(dmove)) if dmove.size else 0.0
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
    if ow_i.size and not rep.one_way_settled:       # §20a: NAME the failure
        rep.read_lag_failure(ow_i, dmove, float(d.one_way_tol_m),
                             int(d.one_way_max_rounds), one, base_p.one_way,
                             planar)

    # PHASE C — THE HARD ROWS' MULTIPLIERS, the lag now FROZEN (spec §6
    # deviation 7; owner RULINGS 2026-09-09r (3)).  Runs to ``hard_tol_m``
    # or ``polish_rounds_max``; the sequence is NOT monotone (it oscillates
    # while the one-sided set re-forms), so a flat round ends nothing, the
    # BEST iterate is returned, and the cap's hit is a NAMED failure.
    # ``law/emit.toml`` [design] carries the measurements.
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
    # 09v (3)).  The Lagrangian above cannot CERTIFY the hard set, so every
    # non-runway vertex is FIXED and the runway family re-solved as a small
    # QP holding its hard rows exactly (``solve/project.py``, which carries
    # the rationale and §32 (4)'s purity test).
    if x is not None:
        # ... then PHASE E, the ZONE projection (12ag, §32): one entry,
        x, rep.runway_projection, rep.zone_projection = project_after_solve(
            planar, law, base_p, x, stacked=(A1, b1), verbose=opt.verbose)
        # RE-READ AFTER THE PROJECTION (§30 (3b), ``rep.read_hard_set``): its
        # own rows are held exactly now; what is left is what it does not own.
        if hard_i.size:
            worst = rep.read_hard_set(
                np.maximum(A1[hard_i] @ x - b1[hard_i], 0.0), float(d.hard_tol_m),
                lambda k: one[int(hard_i[k])][2].source.ruling[:70])
    if x is not None:
        z = np.where(red.col >= 0, x[np.clip(red.col, 0, None)], red.value)
    if levelled_out is not None and x is not None:
        for vid in range(n):
            col = int(red.col[vid])
            if col >= 0 and col not in unlevelled:
                levelled_out[vid] = float(z[vid])
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
    rep.foot_row_diag = foot_row_diagnostic(one, viol_all, base_p.foot_row_i, red.col)
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
    # EACH BODY'S DATUM RESIDUAL (owner RULINGS 2026-09-10p): the solved
    # mean of the body's own vertices against the mean production DEM
    # under them — the number the owner's CYXY read is about.
    rep.body_datums = [
        {"kind": m.kind,
         "ll": [planar.vertices[m.vertices[0]].key[0],
                planar.vertices[m.vertices[0]].key[1]],
         "vertices": len(m.vertices),
         "rows": m.rows,
         "dem_mean_m": round(m.dem_mean, 3),
         "residual_m": round(
             sum(float(z[v]) for v in m.vertices) / len(m.vertices)
             - m.dem_mean, 3),
         "tilt_m": round(max((abs(sum(w * float(z[v]) for v, w in coefs) - rhs)
                              for name, coefs, rhs in _plane_rows(
                                  planar, m.vertices,
                                  [float(planar.vertices[v].dem_z)
                                   for v in m.vertices])
                              if name != "mean"), default=0.0), 3)}
        for m in base_p.body_meta]
    if size_out is not None:
        size_out.update({"columns": red.n_cols, "z": n, "rows": rep.rows,
                         "nnz": int(A.nnz), "triangles": rep.triangles,
                         "chord_vertices": chord_v, "road_fit_vertices": road_v,
                         "one_way_rows": rep.one_way_rows,
                         "ground_datum_rows": rep.ground_datum_rows,
                         "foot_rows": rep.foot_rows,
                         "active": len(active), "rounds": rep.rounds})
    cert = residual(cs, z, obj)
    wall = time.perf_counter() - t0
    return (Solution(z=tuple(float(v) for v in z),
                     status=Status.OPTIMAL if rep.converged else Status.FEASIBLE,
                     residual=cert, iterations=rep.rounds, wall_s=wall,
                     message=f"design surface: {rep.rounds} active-set round(s), "
                             f"{red.n_cols} unknowns, {rep.rows} rows, "
                             f"{method}"), rep)
