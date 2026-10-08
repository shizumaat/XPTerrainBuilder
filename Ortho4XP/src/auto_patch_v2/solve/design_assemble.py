"""§1-9 OF THE DESIGN ASSEMBLY — the problem ``solve/design`` solves.

:class:`Base` (the assembled problem before the active set runs),
:func:`assemble` that builds it, and the per-body datum record
:class:`_BodyDatum` it fills.  Split out of ``solve/design`` (issue #303:
that file passed the 1,500-line split point) along the seam the module
already splits on — ``design_ground``, ``design_roles``, ``design_stage``,
``design_report``, ``design_qp``.

No cycle, so no lazy import: assembly reads the LAW, the model and the row
library (``solve/rows``) and never reads the solve driver back.  Every name
keeps its import path — ``solve/design`` re-exports all three.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..law.design_schema import BEND_CLASSES
from ..law.tables import design as design_law, role_side
from ..model.constraints import ConstraintSet, Diff
from ..model.planar import PlanarMap
from .design_report import DesignReport
from .feasibility import _carries_a_column, apron_hard_rows
from .flex import _held_at_ref
from .rows import (_cotangent_laplacian, _face_triangles, _law_sides,
                   _plane_rows, _plane_targets, _reduce, _Reduction,
                   _role_bodies, _role_bodies_faced, _Rows, _shape_bodies,
                   _sheet_components, _Side, _zone_weights,
                   apply_level_belt)
from .design_ground import ground_datum_vertices, ground_rim_vertices
from .design_stage import _groundside_minter, _welded_faces
from .design_roles import (bend_class, bend_roles, conforming_rulings,
                           datum_roles, foot_row_rulings, hard_rulings,
                           is_hard, one_way_rulings, pad_flat_rulings,
                           pad_level_rulings, pavement_roles, ruling_head)

__all__ = ["Base", "assemble"]


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


def assemble(planar: PlanarMap, cs: ConstraintSet, law: Law,
             rep: DesignReport, *,
             drop: _t.AbstractSet[int] | None = None,
             fixed: _t.Mapping[int, float] | None = None,
             stage_roles: _t.AbstractSet[str] | None = None) -> Base:
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
    column is airside.  Both default empty: the single solve is unchanged.

    §20b (3) adds ``stage_roles``: the ROLES this stage's sheet is made of.
    "No vertex of it is foreign" is not the same test — a face every one of
    whose vertices is column-shared with airside (a pad welded to an apron
    rim, a lot, a service road) passed it and was triangulated INSIDE the
    airside stage whatever its role.  MEASURED (lane ``v2stagepop`` r1,
    HECA, every pad row dropped): the pads-OFF arm carried a 1 m²
    ``building`` face and a 16 m² ``groundside_pavement`` face in stage 1's
    sheet and the pads-ON arm neither, at LEMD 2 ``service_road`` faces
    against 1 ``building`` — a difference in stage 1's own problem made by
    groundside geometry, which is exactly what §20b (3) forbids.  ``None``
    (the single solve, stage 2) keeps the whole sheet."""
    d = design_law(law)
    n = len(planar.vertices)
    drop_f = frozenset(drop or ())

    # 1. the sheets and their triangulation
    roles = set(bend_roles(law))
    pav_roles = set(pavement_roles(law))
    # §20b (1c) THE SHEET IS THIS STAGE'S OWN.  The bending operator is
    # assembled over the triangulation of EVERY sheet face, so a pavement
    # vertex on the airside boundary carries a stencil reaching into the
    # strip beside it — one row, mixed columns, which the stage drop would
    # then refuse ENTIRELY, leaving the airside sheet with no bending at
    # its own edge (measured: the runway crown's built drop 0.146 -> 0.558
    # m on ``test_crown``'s fixture).  A stage therefore triangulates only
    # the faces it owns: the Laplacian's stencil never leaves the stage,
    # and every bending row it writes is in-stage by construction.
    sheet_faces = [f.id for f in planar.faces.values()
                   if f.role in roles
                   and (stage_roles is None or f.role in stage_roles)
                   and not (drop_f and any(
                       v in drop_f
                       for ring in (f.ring, *f.holes)
                       for v in planar.ring_vertices(ring)))]
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
    pl_heads = pad_level_rulings(law)
    #: the pad vertices a LEVEL row governs (owner RULINGS 2026-09-10l):
    #: they follow the pavement they front and carry no DEM datum (§9b)
    pad_follow: set[int] = set()
    hard: list[int] = []
    pad_flat_i: list[int] = []
    foot_i: list[int] = []   # the FOOT ROWS at ``pad_flat`` (11ab)
    one_way: dict[int, tuple[int, ...]] = {}
    #: the vertices a LAW EQUALITY GOVERNS (owner RULINGS 2026-09-10ba): a
    #: basin floor is no longer PINNED — it is tied to its rim by a relative
    #: equality — so §9 must read it as ANCHORED, or the floor sheet counts
    #: as detached and takes a DEM plane of its own beside that row.
    hard_follow: set[int] = set()
    stage_dropped = 0
    #: §20b (1b): the rows whose whole job is to FOLLOW — stage 1 refuses
    #: them even where every column is airside (a welded pad's skirt and
    #: flatness rows sit between two vertices the apron owns)
    conform = conforming_rulings(law) if drop_f else frozenset()
    # §5 THE FRONTING SET'S CAPS ARE HARD (flat-pad spec v2, RULINGS
    # 2026-09-30y (3)): the ONE filter — an airside pair cap whose every
    # foot is on the published fronting set joins the hard set; ``is_hard``
    # and every generator are unchanged
    front = frozenset(getattr(planar, "fronting_vertices", None) or ())
    front_heads = (frozenset(design_law(law).fronting_hard_rulings)
                   if front else frozenset())
    front_ref = getattr(planar, "fronting_ref", None) or {}
    tol_ref = float(design_law(law).hard_tol_m)
    rep.fronting_promoted, rep.fronting_promoted_by = 0, {}
    ap_hard = apron_hard_rows(planar, law)   # §5: the apron cap HARD (30be/30bf)
    # RULINGS 2026-09-30aa rule 1 (#100; owner 30z (1): a road never moves
    # the airside): a row MINTED by a WELDED road face (the mapped-road
    # ribbon) is stage 2's WHATEVER ITS COLUMNS — a ribbon ring pair footed
    # on two rim vertices has only airside columns, and stage 1 took it by
    # column (30aa (b)).  The minting face is the row's own ``face:N``.
    gs_minted = _groundside_minter(planar, law) if drop_f else None
    for side in one_t:
        terms, hi, row = side
        vs = {v for v, _c in terms}
        if vs & drop_f:               # §20b: not this stage's problem
            stage_dropped += 1
            continue
        if conform and (getattr(row, "follows", None) is not None
                        or ruling_head(row) in conform):
            stage_dropped += 1        # §20b (1b): a conforming row is stage 2's
            continue
        if gs_minted is not None and gs_minted(row):
            stage_dropped += 1        # 30aa rule 1: a groundside face's row
            continue
        if vs & red.dem_fixed and not vs <= red.dem_fixed:
            dropped_bank += 1
            continue
        # THE HARD ROWS (RULINGS 2026-09-08v): the runway family's transverse,
        # vertical curve and max grade are CONSTRAINTS.  A row whose every
        # foot is fixed carries no column and constrains nothing — it stays a
        # reported target.  A PREFERENCE among them is hard AT ITS CEILING and
        # keeps its preferred bound as the target: two sides, one row.
        #
        # "CARRIES NO COLUMN" IS THE TEST, NOT "IS DEM-FIXED" (lane
        # ``v2settle``, spec §20a; the first-ranked standing debt 13y (B) /
        # 13ab / 14as).  The sentence above states the law and the code
        # tested one WAY of being fixed: a foot held by a ``Pin`` — a road
        # profile pin, a threshold — is fixed and is NOT in ``dem_fixed``,
        # so its row entered the hard set carrying nothing the solve can
        # move.  MEASURED at HECA (staged, capture off b1b7704c): 142 of
        # stage 1's 161,780 hard rows carry no column at all, 9 of them
        # violated — INCLUDING THE WORST ROW OF THE WHOLE AIRSIDE SET
        # (0.1794 m, ``roads.groundside_road ramp ceiling`` on a pinned
        # service-road vertex at 30.13717041421,31.4124359031).  A constant
        # row cannot settle, and its cost is not only the report: phase C
        # keeps ``best_worst`` pinned at that constant, so ``worst <
        # best_worst`` never fires and the polish RETURNS ROUND 1's
        # iterate, discarding what the later rounds bought.  The row stays
        # a reported target exactly as the comment above says.
        # The test is the REDUCED row's, not the raw terms': two feet of one
        # rigid ``Flat`` group share a column and a ±1 pair cancels to
        # nothing, which is the same constant by another route.
        promoted = bool(front_heads) and ruling_head(row) in front_heads \
            and vs <= front and _held_at_ref(terms, hi, front_ref, tol_ref)
        if (is_hard(heads, row) or promoted or ap_hard(row)) and _carries_a_column(red, terms):
            if promoted and not is_hard(heads, row):
                rep.fronting_promoted += 1
                rep.fronting_promoted_by[ruling_head(row)] = rep.fronting_promoted_by.get(ruling_head(row), 0) + 1  # noqa: E501
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
         else foot_i if head in fr_heads else []).append(len(one))
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
        if conform and (getattr(side[2], "follows", None) is not None
                        or ruling_head(side[2]) in conform):
            stage_dropped += 1        # §20b (1b)
            continue
        if gs_minted is not None and gs_minted(side[2]):
            stage_dropped += 1        # 30aa rule 1
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
    # A collar's coverage-edge rim datum (issue #302) gives THAT VERTEX a
    # level inside its slack bank; it does not anchor the pad's sheet.
    # Counted as an anchor it withdrew the sheet's own body datum, and the
    # §20c single-solve locality twin (``test_v2qp``) read a 1.32 m far
    # response at ANY datum weight (measured down to 1e-6) — the anchor
    # test, not the pull, was the coupling.
    rim_only = ground_rim_vertices(planar)
    for vid in range(n):
        col = int(red.col[vid])
        if col < 0:                                   # a pin / the DEM beyond
            continue
        if (vid in pref or (vid in ground and vid not in rim_only)
                or ramp.get(vid, 0.0) > 0.0):
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
    #    RULINGS 2026-09-30aa rule 1: a WELDED road face's datum is a row
    #    that face MINTS — stage 2's, never stage 1's (in stage 1 its only
    #    columns are the rim vertices it shares: its plane would pull the
    #    apron toward the road's terrain), so stage 1 reads the bodies
    #    without the ribbons
    gs_roles = {r for r in pav_roles if role_side(law, r) == "groundside"}
    welded = _welded_faces(planar) if drop_f else set()
    for vs in _role_bodies(planar, gs_roles, red, welded):
        by_comp.setdefault(("groundside", vs[0]), vs)
    #    A RIGID GROUP (a pad, a plate, a wall band) is ONE column, so its
    #    own bending rows collapse to nothing: bending gives it no level at
    #    all and only its contact rows — one-sided — would.  Each such group
    #    that no pin fixes takes the same soft datum on its own DEM mean, so
    #    a pad with no frontage row sits on its ground instead of floating.
    #    A HELD PAD'S DATUM COLUMN IS ITS LEVEL, NOT A POINT ON THE GROUND
    #    OR ON THE APRON'S TREND (spec §56 (10) R4, step 4F; 10l read for
    #    the hold: "a pad following its frontage takes no trend row").  The
    #    column is one of the pad's rim vertices, so a DEM or trend target
    #    there is wherever that vertex happens to stand (MEASURED, HECA: a
    #    column that moved along the rim moved its trend target 99.97 ->
    #    92.90 m and ten pads' datums ~0.1 m); the hold rows give the level.
    from ..model.platform import datum_vertices as _datum_vertices
    datum_v = set(_datum_vertices(planar, law).values())
    datum_cols = {int(red.col[v]) for v in datum_v if red.col[v] >= 0}
    for f_ in cs.flats:
        col = int(red.col[f_.group[0]])
        if col < 0 or col in datum_cols:
            continue
        vs_f = [v for v in f_.group if planar.vertices[v].dem_z is not None]
        if not vs_f:
            continue
        mean = sum(float(planar.vertices[v].dem_z) for v in vs_f) / len(vs_f)
        rows.add(((f_.group[0], 1.0),), mean, d.detached_mean, ("detached", ("flat", col)))
    rep.detached = len(by_comp)
    for c, vs in by_comp.items():
        for vid, target in _plane_targets(planar, vs):
            if vid in datum_v:
                continue
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
        if vid in rwy_v or vid in pad_follow or vid in datum_v:
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
    # §42 (1b) (owner RULINGS 2026-09-27a (5)): a HARD GROUND PLANE is
    # graded LEVEL at its runway-edge frontage with NO DEM datum — X-Plane
    # sets the object level at its anchor, it cannot tilt after the ground
    # (``constraints/hard_plane``; the NLWF arm body_datum=0 was 92 -> 5
    # verify rows).  Its vertices leave every body's plane fit.  The vertex
    # set lives in ``model.hard_plane`` (issue #84: solve never imports
    # constraints).
    from ..model.hard_plane import hard_plane_vertices
    hard_v = hard_plane_vertices(planar)
    # THE COURTYARD (``model.islands``, lane islands #77): an apron island in
    # a pad hole takes the pad RIM's level — no DEM datum of its own
    from ..model.islands import courtyard_vertices
    court_v = courtyard_vertices(planar, law)
    for kind, roles_b in datum_roles(law):
        # THE BODY IS THIS STAGE'S OWN (issue #67; §20b (1c)'s rule for the
        # sheet, applied to the datum): stage 1's body is formed over the
        # airside faces alone.  Formed over every bending role, a pad face
        # JOINED two aprons into one body — so whether an apron carried its
        # own datum or none (a touched body takes the trend instead, below)
        # depended on a pad outline, which is the groundside deciding an
        # airside value.  The single solve and stage 2 keep every role.
        if stage_roles is not None:
            roles_b = frozenset(roles_b) & frozenset(stage_roles)
        for vs_b in _shape_bodies(planar, red,
                                  _role_bodies_faced(planar, roles_b, red)):
            # 10l: a pad that fronts pavement takes its frontage's level, not
            # the ground's — its vertices leave every body's datum fit
            vs_b = [v for v in vs_b if v not in pad_follow and v not in hard_v
                    and v not in court_v]
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
                chord_v, road_v, body, meta, foot_row_i=foot_i)
