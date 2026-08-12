"""FLAT-SITE FAST PATH (phase 3) — the SOLVE PARTITION.

Spec: ``docs/specs/flat-site-fast-path-spec.md`` (2026-08-10, FROZEN).
Phase 1 (``flat_site.py``) is the report-only detector, phase 2
(``flat_site_mode.py``) is the DEM SOURCE SUBSTITUTION that puts a
synthetic constant raster at ``Z0`` under a flat airport.  This module is
phase 3: given that constant raster, THE ANSWER IS KNOWN BEFORE THE
SOLVE STARTS for most of the field, so the solve PARTITIONS.

  1. ELIGIBLE shapes are BORN at Z0, not solved.  They take the existing
     fixed-value membership idiom (``bridges.born_flat_solver_plate`` /
     the deck-pin registry): every ring vertex is a HARD PIN at exactly
     Z0, protected like a seam pin.  They contribute BOUNDARY VALUES and
     no free variables — no grade-graph rows, no reach bands, no route
     profile membership.  A CONSTANT field satisfies every within-shape
     and step law by construction.
  2. INELIGIBLE shapes solve fully, verbatim, against those fixed
     boundary values.

CONSERVATIVE BY LAW (spec §1): any shape the predicate cannot PROVE
eligible solves fully.  Partition, never approximate.  Every refusal
below is counted and reported, so a predicate that admits nothing is
visible in the console rather than silent.

WHAT MAKES THE PARTITION PROVABLE.  The gate is not the detector's
verdict — it is the DEM PROVENANCE STAMP that phase 2 writes on the DEM
object the solve actually samples
(``provenance.dem_provenance_from_dem(...)["synthetic_flat_site"]``,
captured onto ``layout.dem_inset_provenance`` at the pipeline's
DEM-in-hand point).  A verdict says "this site is flat"; the stamp says
"the raster you are grading against IS the constant Z0, over THIS
extent, feathered over THIS width".  Only the second statement licenses
"a soft node's closest-to-DEM-within-grade solution is exactly Z0", and
only inside the extent ERODED BY THE FEATHER, where the raster is
constant rather than ramping.  With ``FLAT_SITE_MODE`` off there is no
stamp and this module admits nothing — which is correct: a merely
flat-ISH real DEM does not converge to a constant.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shapely.geometry import box
from shapely.errors import GEOSException
from shapely.errors import TopologicalError
from shapely.ops import unary_union

__all__ = [
    "fast_path_enabled",
    "quantum_m",
    "eligible_roles",
    "solver_eligible_roles",
    "transition_roles",
    "published_plan",
    "z0_residual_report",
    "substitution_entry",
    "constant_core",
    "runway_envelope",
    "below_grade_present",
    "below_grade_keepout",
    "build_plan",
    "plan_for",
    "apply_seed_pins",
    "skip_shape_ids",
    "band_skip_idx",
    "certificate_exempt_idx",
    "format_log_line",
    "FastPathPlan",
    "PLAN_ATTRIBUTE",
]

_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

#: Where the plan is published on the layout.  Written once per solve by
#: :func:`plan_for`; read by the constraint builder, the unified-graph
#: build and the reach-band skip.
PLAN_ATTRIBUTE = "_flat_fast_path"


def fast_path_enabled() -> bool:
    """The gate.  ``O4_FLAT_SITE_FAST_PATH=0`` kills the partition."""
    from . import config as _config

    return bool(getattr(_config, "FLAT_SITE_FAST_PATH", False))


def quantum_m() -> float:
    """The solver quantum equivalence is proven to (spec, Tests §1)."""
    from . import config as _config

    return float(getattr(_config, "FLAT_SITE_FAST_PATH_QUANTUM_M", 0.01))


# ──────────────────────────────────────────────────────────────────────
# (a) THE ROLE FAMILIES
# ──────────────────────────────────────────────────────────────────────
def eligible_roles() -> frozenset:
    """The pavement / groundside / building role families (spec §1a).

    ENUMERATED FROM ``config.ROLE_GRADE_LIMITS``, never from a fresh list
    of role literals — role strings are wire-adjacent (they name the
    emitted way's tag and the validator's law family), and a second
    hand-written list is how a role silently falls out of a law
    (``object_pads`` carries the same note for the same reason).

    The rule reads off that table directly:

    * a ``None`` cap means the role is NOT pavement — it is a law
      surface or a feature emission (boundary, retaining wall,
      clearance cuts, graded strips, OLS cuts, the bridge trench /
      causeway plates, object pads).  The spec excludes every one of
      them: "never a tunnel/bridge/basin feature role, never
      boundary/adjacent-ground feature emission".
    * ``runway`` and ``runway_crossing`` are excluded by name — the
      runway keeps the CIFP-absolute profile + crown machinery verbatim.
    * ``tunnel_ramp`` is excluded by name — a below-grade feature role.
    * ``terminal`` is the pre-rename READ ALIAS of ``building`` (see
      ``ROLE_GRADE_LIMITS``'s own comment); no live build mints it, and
      admitting an alias would double-count the family.

    A role absent from the table (``tunnel_trench``, and anything a
    future feature adds) is NOT eligible: ``_role_grade`` falls back to
    the taxi cap for unknown roles, and inheriting an eligibility from a
    fallback is exactly the "unprovable" case the spec sends to the full
    solve.
    """
    from .config import ROLE_GRADE_LIMITS
    from .layout import (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
                         ROLE_TUNNEL_RAMP)

    excluded = {ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_TUNNEL_RAMP,
                "terminal"}
    return frozenset(
        role for role, cap in ROLE_GRADE_LIMITS.items()
        if cap is not None and role not in excluded)


def solver_eligible_roles() -> frozenset:
    """:func:`eligible_roles` ∩ the solver's own membership set.

    A shape whose role is not in ``PAVEMENT_ROLES`` owns no solve
    variable, so partitioning it is meaningless — it is emitted
    post-solve from its own law.  ``groundside_pavement`` is the whole of
    that difference today: it is a pavement family member by
    ``ROLE_GRADE_LIMITS`` and IS born at Z0 on a substituted site, but by
    the per-vertex DEM sample its own emitter already takes, not by
    anything here.
    """
    from .elevation_per_surface.solver_primitives import PAVEMENT_ROLES

    return eligible_roles() & frozenset(PAVEMENT_ROLES)


#: The role family the R5 below-grade transition law may re-profile
#: post-solve (``groundside.TRANSITION_ROLES``), projected onto the roles
#: this module can admit.  Read at call time — the source of truth is
#: ``groundside``.
def transition_roles() -> frozenset:
    from .groundside import TRANSITION_ROLES

    return frozenset(TRANSITION_ROLES)


# ──────────────────────────────────────────────────────────────────────
# THE CONSTANT-FIELD LICENCE
# ──────────────────────────────────────────────────────────────────────
def substitution_entry(layout) -> dict | None:
    """The ``synthetic_flat_site`` provenance entry for THIS build's DEM.

    ``None`` when phase 2 substituted nothing (gate off, non-flat
    verdict, no X-Plane root, a bake failure) — in which case this module
    admits nothing at all.  The entry is written by
    ``O4_Airport_Elevation_Insets.overlay_flat_site_insets`` and ONLY
    there, so it can never claim a substitution the solve did not see.
    """
    provenance = getattr(layout, "dem_inset_provenance", None)
    if not isinstance(provenance, dict):
        return None
    entry = provenance.get("synthetic_flat_site")
    return entry if isinstance(entry, dict) else None


def constant_core(layout, entry: dict):
    """The footprint over which the substituted raster is EXACTLY Z0.

    The synthetic inset is a RECTANGLE handed to the same bake the real
    airport insets take, and that bake FEATHERS from the rectangular data
    edge inward over ``feather_m``.  Inside the feather ring the raster
    ramps from Z0 to the base surface, so it is NOT constant there; the
    provable core is the extent bounding box ERODED by the feather.

    Returns a layout-metre polygon, or ``None`` when the entry carries no
    usable extent (the conservative answer — no core, no candidate).
    """
    extent = entry.get("extent_wgs84")
    if not extent or len(extent) != 4:
        return None
    try:
        lon0, lat0, lon1, lat1 = (float(v) for v in extent)
        feather_m = float(entry.get("feather_m") or 0.0)
    except (TypeError, ValueError):                    # pragma: no cover
        return None
    try:
        x0, y0 = layout.ll_to_m(lat0, lon0)
        x1, y1 = layout.ll_to_m(lat1, lon1)
    except (AttributeError, TypeError, ValueError):    # pragma: no cover
        return None
    try:
        rect = box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        core = rect if feather_m <= 0.0 else rect.buffer(-feather_m)
    except _GEOM_EXC:                                  # pragma: no cover
        return None
    if core is None or core.is_empty:
        return None
    return core


# ──────────────────────────────────────────────────────────────────────
# (b) THE RUNWAY ENVELOPE
# ──────────────────────────────────────────────────────────────────────
def runway_envelope(layout, z0_m: float):
    """``(geometry | None, extra_buffer_m)`` — the ground a shape must lie
    entirely outside of (spec §1b).

    The base footprint is THE STRIP LAW's own geometry —
    ``adjacent_ground.runway_strip_wall_keepout(layout,
    require_gate=False)``, the union of every runway's strip footprint
    built from ``grade_law.runway_strip_wall_keepout_rings`` (the lateral
    graded rectangle at ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` plus the two
    end corridors).  Same law function, same runway grouping by ``ref``,
    so the envelope here and the strip the law enforces are one geometry.

    THE EXTRA BUFFER (conservatism closure, reported as a deviation).
    The spec's seam claim is that a fast-pathed neighbour presents "the
    same Z0 the full solve would have converged to".  That is true while
    the runway itself sits at Z0 — which is the flat site's own premise,
    Z0 BEING the CIFP threshold consensus.  Where a runway vertex sits
    ``|dz|`` off Z0, the full solve may legitimately carry that
    difference outward at the taxi cap for ``|dz| / cap`` metres, and a
    Z0 plate inside that reach would be a value the full solve never
    produced.  The buffer is exactly that distance, taken over the
    layout's runway vertices, so on the site the spec is written for it
    is ZERO and the envelope is the strip footprint verbatim.
    """
    from . import adjacent_ground as _adjacent_ground
    from .config import TAXI_MAX_GRADE

    try:
        strip = _adjacent_ground.runway_strip_wall_keepout(
            layout, require_gate=False)
    except _GEOM_EXC:                                  # pragma: no cover
        strip = None

    from .layout import ROLE_RUNWAY, ROLE_RUNWAY_CROSSING

    worst_dz = 0.0
    runway_polys = []
    for shape in getattr(layout, "shapes", ()) or ():
        if shape.role not in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING):
            continue
        if shape.polygon is None or shape.polygon.is_empty:
            continue
        runway_polys.append(shape.polygon)
        values = []
        if shape.node_altitudes:
            values.extend(a for a in shape.node_altitudes if a is not None)
        if shape.altitude is not None:
            values.append(shape.altitude)
        if shape.altitude_high is not None:
            values.append(shape.altitude_high)
        if shape.altitude_low is not None:
            values.append(shape.altitude_low)
        for value in values:
            try:
                worst_dz = max(worst_dz, abs(float(value) - float(z0_m)))
            except (TypeError, ValueError):            # pragma: no cover
                continue

    parts = [p for p in ([strip] if strip is not None else []) if p is not None]
    parts.extend(runway_polys)
    if not parts:
        return None, 0.0
    try:
        envelope = unary_union(parts)
    except _GEOM_EXC:                                  # pragma: no cover
        return None, 0.0
    if envelope is None or envelope.is_empty:
        return None, 0.0
    cap = float(TAXI_MAX_GRADE)
    extra = 0.0 if cap <= 0.0 else worst_dz / cap
    return envelope, extra


# ──────────────────────────────────────────────────────────────────────
# (c) THE BELOW-GRADE TRANSITION REACH
# ──────────────────────────────────────────────────────────────────────
def below_grade_present(layout) -> bool:
    """Cheap "does this layout hold ANY below-grade surface yet?".

    The same family test :func:`below_grade_keepout` uses, without the
    unions — for the re-application check, which runs after the emitters
    that create most of them.  The families themselves come from
    ``groundside.below_grade_family_shapes``, the ONE enumeration (this
    site used to spell it out a second time)."""
    from .groundside import below_grade_family_shapes

    return bool(below_grade_family_shapes(layout))


def below_grade_keepout(layout, z0_m: float):
    """``(geometry | None, reach_m, transition_family_veto)`` — spec §1c.

    THE R5 REACH, EXACTLY.  For the below-grade surfaces that EXIST at
    solve time (object tunnel trench floors and rim collars, any ramp
    already born) the reach is ``groundside.transition_reach_m`` fed with
    the constant surface ``[Z0]`` and the layout's own
    ``_BelowGradeIndex`` — the R5 formula verbatim, not a re-derivation.

    THE PART THE SPEC COULD NOT ANSWER (reported as a deviation).  Most
    below-grade geometry — tunnel ramps, portal walls, depressed-road
    trenches — is emitted POST-solve by ``bridges`` inside
    ``finalize.emit_terrain_transition_features``, so at solve time the
    below-grade union is largely EMPTY and the literal reading of §1c
    would admit every shape: not conservative, which the spec's own
    override forbids.  The pre-solve evidence of where that geometry WILL
    be born already exists and is already THE published keep-out every
    other consumer reads —
    ``crossing_terrain.crossing_influence_zone_union`` (bridge deck
    boxes, tunnel portal-pair footprints + collars, the mapped
    depressed-road corridor).  It carries geometry but no altitudes, so
    no reach can be computed from it; the conservative closure is:

    * for the R5 TRANSITION ROLE family — the only family
      ``apply_below_grade_transition`` can re-profile — an unknown reach
      is an UNBOUNDED reach: the family is vetoed wholesale whenever any
      below-grade source or any crossing zone exists.
    * for every other role the R5 law never touches such a shape, so the
      only reach a crossing has is its own footprint (plus the measured
      reach of the real sources).
    """
    from . import crossing_terrain as _crossing
    from . import groundside as _groundside
    from .config import GROUNDSIDE_MAX_GRADE
    # The below-grade FAMILIES are gap_fill's blocker set — that module
    # already had to enumerate "a law-cut hole in the ground with its own
    # profile" (R6, spec round4-othh-fixes) and it is the source of
    # truth.  R5's own ``below_grade_sources`` keys on the REF, which
    # catches the bridges.py ramp/trench quads but not the object-derived
    # trench plates (they carry ``<prefix>_trench``); both families are
    # below grade and both belong in this keep-out.
    from .gap_fill import _TUNNEL_BLOCKER_REFS, _TUNNEL_BLOCKER_ROLES

    sources = list(_groundside.below_grade_sources(layout))
    claimed = {id(polygon) for polygon, _r, _a in sources}
    footprints = [polygon for polygon, _r, _a in sources
                  if polygon is not None and not polygon.is_empty]
    for shape in getattr(layout, "shapes", ()) or ():
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty or id(polygon) in claimed:
            continue
        if (shape.role not in _TUNNEL_BLOCKER_ROLES
                and getattr(shape, "ref", "") not in _TUNNEL_BLOCKER_REFS):
            continue
        footprints.append(polygon)
        ring, alts = _groundside._ring_and_altitudes(shape)
        if ring is not None:
            sources.append((polygon, ring, alts))

    index = _groundside._BelowGradeIndex(sources)
    reach_m = 0.0
    if index:
        reach_m = float(_groundside.transition_reach_m(
            [float(z0_m)], index, GROUNDSIDE_MAX_GRADE))

    parts = list(footprints)
    zone = _crossing.crossing_influence_zone_union(layout)
    if zone is not None and not zone.is_empty:
        parts.append(zone)
    veto = bool(parts)
    if not parts:
        return None, 0.0, False
    try:
        keepout = unary_union(parts)
    except _GEOM_EXC:                                  # pragma: no cover
        return None, 0.0, True
    if keepout is None or keepout.is_empty:            # pragma: no cover
        return None, 0.0, veto
    return keepout, reach_m, veto


# ──────────────────────────────────────────────────────────────────────
# THE PLAN
# ──────────────────────────────────────────────────────────────────────
@dataclass
class FastPathPlan:
    """The partition for one solve.

    ``candidates`` is the GEOMETRIC verdict (roles, constant core, runway
    envelope, below-grade reach); ``eligible`` is what survives the
    SEED-TIME demotion (:func:`apply_seed_pins`), which is where a
    candidate carrying a senior hard pin away from Z0 falls back to the
    full solve.  Every consumer reads ``eligible``.

    ``candidates`` is a ``{id(shape): shape}`` MAP and not a bare id set
    on purpose: the plan outlives the solve (``final_grade_projection``
    re-seeds through it), the emitters delete and mint shapes in between,
    and CPython recycles ``id()`` the moment an object is freed.  Holding
    the reference is what makes the identity join sound.
    """

    z0_m: float
    verdict: str = ""
    feather_m: float = 0.0
    candidates: dict = field(default_factory=dict)
    eligible: set = field(default_factory=set)
    node_idx: set = field(default_factory=set)
    pinned_idx: set = field(default_factory=set)
    exclusive_node_idx: set = field(default_factory=set)
    counts: dict = field(default_factory=dict)
    applied: bool = False

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def clone(self) -> "FastPathPlan":
        """A private copy for a READONLY probe re-read of the seeding.

        ``_seed_elevations(readonly=True)`` exists so a measurement
        instrument can reproduce the production seeding without moving
        the emitted surface; it must therefore run the same demotion and
        the same pins, but on state of its own — publishing a probe's
        node sets would rebind the solve's partition to a foreign node
        space (the round-6 SPJC lesson, in the plan's own terms)."""
        return FastPathPlan(
            z0_m=self.z0_m, verdict=self.verdict, feather_m=self.feather_m,
            candidates=dict(self.candidates),
            eligible=set(self.candidates),
            node_idx=set(), pinned_idx=set(), exclusive_node_idx=set(),
            counts=dict(self.counts), applied=False)


def build_plan(layout) -> "FastPathPlan | None":
    """The geometric partition, or ``None`` when the fast path is inert.

    ``None`` means "solve exactly as today" and is returned for every
    reason the partition cannot be PROVEN: gate off, no synthetic
    substitution stamped on this build's DEM, no usable constant core.
    """
    if not fast_path_enabled():
        return None
    entry = substitution_entry(layout)
    if entry is None:
        return None
    try:
        z0_m = float(entry["z0_m"])
    except (KeyError, TypeError, ValueError):          # pragma: no cover
        return None
    core = constant_core(layout, entry)
    if core is None:
        return None

    plan = FastPathPlan(
        z0_m=z0_m,
        verdict=str(entry.get("verdict") or ""),
        feather_m=float(entry.get("feather_m") or 0.0),
    )
    roles = solver_eligible_roles()
    trans_roles = transition_roles()
    envelope, envelope_extra = runway_envelope(layout, z0_m)
    keepout, reach_m, transition_veto = below_grade_keepout(layout, z0_m)
    plan.counts["reach_m"] = round(reach_m, 2)
    plan.counts["runway_extra_m"] = round(envelope_extra, 2)

    # The three test geometries are built and PREPARED once — a buffer of
    # a complex union inside the per-shape loop is O(shapes) copies of the
    # same dilation, and this predicate runs on every build of a
    # substituted airport.
    from shapely.prepared import prep

    core_test = prep(core)
    envelope_test = None
    if envelope is not None:
        envelope_test = prep(envelope.buffer(envelope_extra)
                             if envelope_extra > 0.0 else envelope)
    keepout_test = None
    if keepout is not None:
        keepout_test = prep(keepout.buffer(reach_m)
                            if reach_m > 0.0 else keepout)

    for shape in getattr(layout, "shapes", ()) or ():
        role = getattr(shape, "role", None)
        if role not in roles:
            plan.bump("refused_role")
            continue
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty:
            plan.bump("refused_geometry")
            continue
        plan.bump("candidate")
        try:
            if not core_test.contains(polygon):
                plan.bump("refused_outside_core")
                continue
            if envelope_test is not None and envelope_test.intersects(polygon):
                plan.bump("refused_runway_envelope")
                continue
            if keepout_test is not None:
                if transition_veto and role in trans_roles:
                    plan.bump("refused_transition_family")
                    continue
                if keepout_test.intersects(polygon):
                    plan.bump("refused_below_grade_reach")
                    continue
        except _GEOM_EXC:                              # pragma: no cover
            plan.bump("refused_geometry")
            continue
        plan.candidates[id(shape)] = shape

    plan.eligible = set(plan.candidates)
    return plan


def plan_for(layout) -> "FastPathPlan | None":
    """Build the plan once per solve and publish it on the layout."""
    plan = build_plan(layout)
    try:
        setattr(layout, PLAN_ATTRIBUTE, plan)
    except AttributeError:                             # pragma: no cover
        pass
    return plan


def published_plan(layout) -> "FastPathPlan | None":
    """The plan :func:`plan_for` published, if the partition is live.

    ``None`` (the inert answer) whenever the gate is off, nothing was
    published, or the seed pass never applied it — so every consumer's
    off-path is the pre-change code path exactly.
    """
    plan = getattr(layout, PLAN_ATTRIBUTE, None)
    if plan is None or not getattr(plan, "applied", False):
        return None
    return plan if plan.eligible else None


def skip_shape_ids(layout) -> frozenset:
    """``id(shape)`` of every BORN-AT-Z0 shape — the set the grade-graph
    builders skip.  Empty frozenset when the partition is inert."""
    plan = published_plan(layout)
    return frozenset(plan.eligible) if plan is not None else frozenset()


def certificate_exempt_idx(layout) -> frozenset:
    """Node indices the FLATNESS CERTIFICATE must NOT treat as hard
    (lead ruling 2026-08-10, approving this lane's open question).

    ``_build_shape_constraints`` refuses the certificate to any shape
    touching a ``hard_nodes`` member, and it states its own reason:
    those nodes "sit at profile values, NOT the DEM seed", so a shape
    touching one starts already off the seed the certificate is taken
    at.  A BORN-AT-Z0 pin is the exact opposite case — the substituted
    raster IS Z0, so the pin sits precisely AT its own DEM sample, and
    that identity is what the equivalence twin proves.  Leaving it in the
    hard set therefore refuses the certificate for a reason that is false
    of it, and the cost lands on the shape's INELIGIBLE neighbours: every
    junction or apron sharing one vertex with a born-at-Z0 shape falls
    back to eager O(n²) pair generation (OTHH, measured: 118 of the 160
    surviving junction candidates refused).

    SCOPED TO THIS FAMILY'S OWN PINS, never to a hard node generally: a
    vertex of an eligible shape that a SENIOR family (runway, tile seam,
    bridge deck, runway-end skirt, EAT) had already hardened is NOT in
    ``pinned_idx`` — that family owns the value, may hold it at a profile
    value, and keeps its certificate-refusing power untouched.
    """
    plan = published_plan(layout)
    return (frozenset(plan.pinned_idx) if plan is not None
            else frozenset())


def band_skip_idx(layout) -> frozenset:
    """Node indices the reach band may skip (spec §3).

    ONLY nodes used EXCLUSIVELY by born-at-Z0 shapes: a node shared with
    an ineligible shape keeps its band, because that shape's own law
    reads it.  An exclusive node is a hard pin no pass may move, so its
    band is never consumed — the same argument
    ``node_bands(skip_from=…)`` already makes for adjacent-ground zone
    vertices.
    """
    plan = published_plan(layout)
    return (frozenset(plan.exclusive_node_idx) if plan is not None
            else frozenset())


# ──────────────────────────────────────────────────────────────────────
# THE FIXED-VALUE MEMBERSHIP (the born-flat plate, seed side)
# ──────────────────────────────────────────────────────────────────────
def apply_seed_pins(layout, plan, nodes, bucket_to_idx, elev, is_hard,
                    have_initial, intern, *, readonly: bool = False) -> None:
    """Pin every eligible shape's ring vertices at exactly Z0.

    THE PIN IDIOM IS THE EXISTING ONE.  This is the object-bridge deck
    pin / runway-end skirt pin block mirrored once more: ``elev`` takes
    the fixed value, ``is_hard`` and ``have_initial`` are set, and the
    indices join ``layout._seam_pin_idx`` so no downstream re-stamp or
    yield relaxation may move them.  It runs LAST of the pin families, so
    a senior pin (runway, tile seam, bridge deck, runway-end skirt, EAT
    anchor rect) is never overwritten.

    THE DEMOTION IS THE CONSERVATISM.  A candidate shape holding a senior
    pin whose value differs from Z0 by more than the quantum is NOT
    provably constant — the full solve would have graded away from that
    pin — so the WHOLE shape falls back to the full solve and none of its
    vertices are pinned here.  Demotion runs as a first pass over every
    candidate before any pin is written, so the verdict cannot depend on
    shape order.
    """
    if plan is None:
        return
    roles = solver_eligible_roles()
    tol = quantum_m()
    z0 = float(plan.z0_m)

    # EVERY APPLICATION IS ONE NODE SPACE.  ``_seed_elevations`` runs
    # again in ``final_grade_projection`` (and in the projection
    # snapshot) on a REBUILT node list, and an index means nothing across
    # a rebuild — the rod-key lesson.  So the index sets are cleared and
    # the eligibility is re-derived from the geometric candidates each
    # time, rather than accumulated across two spaces.
    plan.node_idx = set()
    plan.pinned_idx = set()
    plan.exclusive_node_idx = set()
    plan.eligible = set(plan.candidates)

    # POST-SOLVE BELOW-GRADE EMERGENCE.  The plan's §1c test ran
    # pre-solve, when almost no below-grade shape existed yet.  By the
    # time the projection re-seeds, ``bridges`` has emitted the ramps,
    # trenches and portal walls the R5 transition law grades away from —
    # and that law rewrites exactly ``groundside.TRANSITION_ROLES``.
    # Re-check the cheap half here so a re-application can never pin a
    # surface R5 has since taken authority over.
    if below_grade_present(layout):
        trans = transition_roles()
        for shape in getattr(layout, "shapes", ()) or ():
            if shape.role in trans and id(shape) in plan.eligible:
                plan.eligible.discard(id(shape))
                plan.bump("demoted_below_grade_emergence")

    # Ring vertices per candidate shape, resolved once.
    from .elevation_per_surface.solver_primitives import _open_ring

    rings: dict = {}
    for shape in getattr(layout, "shapes", ()) or ():
        key = id(shape)
        if key not in plan.candidates or shape.role not in roles:
            continue
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty:        # pragma: no cover
            continue
        try:
            coords = _open_ring(list(polygon.exterior.coords))
        except _GEOM_EXC:                              # pragma: no cover
            continue
        idx = []
        for x, y in coords:
            k = intern(float(x), float(y))
            if k is None:                              # readonly probe
                continue
            i = bucket_to_idx.get(k)
            if i is not None:
                idx.append(i)
        if idx:
            rings.setdefault(key, []).extend(idx)

    # Pass 1 — demotion against the SENIOR pin state.
    for key, idx in list(rings.items()):
        for i in idx:
            if is_hard[i] and abs(float(elev[i]) - z0) > tol:
                plan.eligible.discard(key)
                plan.bump("demoted_senior_pin")
                break

    # Pass 2 — pin.  A senior pin already AT Z0 (within the quantum) is
    # left exactly as it is: the senior family owns the value, and
    # rewriting it would mint a difference the quantum says is not there.
    pinned: set = set()
    for key, idx in rings.items():
        if key not in plan.eligible:
            continue
        for i in idx:
            plan.node_idx.add(i)
            if is_hard[i]:
                continue
            elev[i] = z0
            is_hard[i] = True
            have_initial[i] = True
            pinned.add(i)
    plan.pinned_idx = set(pinned)
    plan.counts["pinned_nodes"] = len(pinned)
    plan.counts["eligible_shapes"] = len(plan.eligible)

    # EXCLUSIVE nodes — used by no shape outside the eligible set.  Only
    # these may skip the reach band; a shared node is a boundary value an
    # ineligible shape's law still reads.
    foreign: set = set()
    from .elevation_per_surface.solver_primitives import PAVEMENT_ROLES

    for shape in getattr(layout, "shapes", ()) or ():
        if id(shape) in plan.eligible:
            continue
        if shape.role not in PAVEMENT_ROLES:
            continue
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty:
            continue
        try:
            coords = _open_ring(list(polygon.exterior.coords))
        except _GEOM_EXC:                              # pragma: no cover
            continue
        for x, y in coords:
            k = intern(float(x), float(y))
            if k is None:                              # pragma: no cover
                continue
            i = bucket_to_idx.get(k)
            if i is not None:
                foreign.add(i)
    plan.exclusive_node_idx = plan.node_idx - foreign

    if pinned and not readonly:
        existing = getattr(layout, "_seam_pin_idx", None)
        layout._seam_pin_idx = (           # type: ignore[attr-defined]
            set(existing) if existing else set()) | pinned
    plan.applied = not readonly


def format_log_line(plan, icao: str = "") -> str:
    """The one verbosity-0 line the partition prints per airport."""
    if plan is None:
        return f"  [flat-fast-path] {icao}: inert (no partition)."
    counts = plan.counts
    return (
        f"  [flat-fast-path] {icao}: {counts.get('eligible_shapes', 0)} of "
        f"{counts.get('candidate', 0)} candidate shape(s) BORN at Z0 "
        f"{plan.z0_m:.2f} m ({counts.get('pinned_nodes', 0)} node(s) "
        f"pinned, {len(plan.exclusive_node_idx)} band-skippable) | "
        f"refused: core {counts.get('refused_outside_core', 0)}, "
        f"runway-envelope {counts.get('refused_runway_envelope', 0)} "
        f"(+{counts.get('runway_extra_m', 0)} m), "
        f"transition-family {counts.get('refused_transition_family', 0)}, "
        f"below-grade-reach {counts.get('refused_below_grade_reach', 0)} "
        f"(reach {counts.get('reach_m', 0)} m), "
        f"senior-pin {counts.get('demoted_senior_pin', 0)}")


def z0_residual_report(plan, elev) -> dict:
    """``{n, worst_m}`` over the born-at-Z0 nodes after the solve.

    The build's own equivalence evidence: every eligible node must still
    read exactly Z0 when the solve returns (they are hard pins, so any
    drift is a pass that moved a protected node).  Report-only.
    """
    if plan is None or not plan.node_idx:
        return {"n": 0, "worst_m": None}
    worst = 0.0
    for i in plan.node_idx:
        if i < len(elev):
            worst = max(worst, abs(float(elev[i]) - float(plan.z0_m)))
    return {"n": len(plan.node_idx), "worst_m": round(worst, 6)}
