"""THE single within-shape grade-constraint graph (solver AND validator).

This module is the ONE place that decides *which* vertex pairs of a soft airside
shape are grade-constrained and *at what cap*.  Both the elevation solver
(pre-emit, from ``layout.shapes``) and the grade validator (post-emit, from the
OSM ways) build the same representation-agnostic input and call
:func:`build_grade_constraints` — so the surface we *build* and the surface we
*check* can never drift again (see ``docs/single_grade_graph.md``).

It is deliberately self-contained and clean-room: it does NOT import the legacy
``check_grade.iter_shape_grade_constraints`` / per-axis machinery.

Model (user, authoritative 2026-06-23) — a soft airside shape is **spine + body**:

* **spine**  = taxi centerline(s) through the shape (after ``junction_spine``
  slicing the centerline is a real shared edge with nodes ON it).  A pair of
  spine nodes on a COMMON centerline is graded at the **taxiway per-letter cap**
  (A/B 3 %, C–F 1.5 %) — the centerline is a taxiway even inside an apron/junction.
* **body**  = every other mutually-visible pair, graded at the shape's **body
  cap**:
    - apron   → ``APRON_MAX_GRADE`` (1 %),
    - junction → the taxiway per-letter cap of its spine (so a junction is uniform
      at the taxiway cap; a junction with NO spine inherits the cap from the
      nearest connected taxiway-sized shape),
    - service_junction → ``SERVICE_ROAD_MAX_GRADE`` (config's ONE road
      number; do not restate it here — the "4 %"/"5 %" copies this file and
      pavement/service_roads.py used to carry were both stale).

Rects (4-corner sloping planes), terminals (flat pads), runways (FAA profile) and
groundside (DEM) are NOT handled here — the solver keeps their plane/flat/profile
models (a correct planar rect already satisfies the convex all-pair check, so
they are not a lockstep gap) and the validator keeps its own per-role handling for
them.  This module owns the apron/junction visibility graph only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from typing import Callable, Hashable, Optional, Sequence

from shapely.errors import GEOSException, TopologicalError

from . import fabric_flags as _FF
from . import grade_law as GL
# R3 (service-road law spec, 2026-08-15): the road family whose
# unshared-route pairs migrate to the nearest-route bake in
# ``_bake_edge`` — the service lateral pass's own target set, one list,
# so the family this rule prices is the family that pass plants on.
from .lateral_spine_nodes import SERVICE_AXIS_PRICED_ROLES
# THE STAGE TAG (staged-solve S1b) — stamped per unified-graph edge from
# the minting shape's lawful role.
from .solve_stage import stage_of_shape as _stage_of_shape

# Shapely-domain failures a triangulation / geometry op may raise (never catch
# built-ins broadly — a KeyError etc. is a real bug, not a bad polygon).
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)
from .config import (
    ANISO_EDGES,
    APRON_BACK_EDGE_GRADE,
    APRON_MAX_GRADE,
    APRON_TAXI_BLEND,
    APRON_TAXI_TRANSITION_M,
    FAN_RAMP_CAP,
    GRADE_VISIBILITY_BUFFER_M as _VIS_BUF,
    JUNCTION_MESH_CONSTRAINTS,
    SERVICE_ROAD_MAX_GRADE,
    SERVICE_ROAD_MAX_TRANSVERSE,
    SERVICE_ROAD_WIDTH_M,
    SVC_SPINE_FIRST,
    TAXI_MAX_GRADE,
    TAXI_MAX_GRADE_NARROW,
    TAXI_MAX_TRANSVERSE_NARROW,
    taxi_grade_cap_for_letter,
    transverse_cap_for_longitudinal_cap as _transverse_cap_for_longitudinal_cap,
)

# Roles this module owns (the visibility-graph soft airside shapes).
# ``JUNCTION_ROLES`` is defined by THE LAW (``grade_law`` — the junction mesh
# rule applies to these roles) and re-exported here for the readers.
# SPINE-FIRST service roads (config.SVC_SPINE_FIRST, part 30m):
# ``service_road`` joins the soft set so the road body gets within-shape LAW
# edges on BOTH readers (this graph and the validator, which import the same
# tuple) — previously a service_road emitted ZERO within-shape edges (not
# soft, not a rect-era sloping rect since it carries
# per-node altitudes), so its two long edges could bind to different anchor
# regimes with no law between them (the CYXY 2.49 m cross-road tear).  Its
# pairs resolve through the SAME ``classify_pair``/``_bake_edge`` path as
# service_junction: body cap SERVICE_ROAD_MAX_GRADE longitudinally,
# SERVICE_ROAD_MAX_TRANSVERSE across the route — the cross-road tear becomes
# unrepresentable, not merely illegal.
APRON_ROLE = "apron"
JUNCTION_ROLES = GL.JUNCTION_ROLES
SOFT_VISIBILITY_ROLES = ((APRON_ROLE,) + JUNCTION_ROLES
                         + (("service_road",) if SVC_SPINE_FIRST else ()))

# A ring vertex counts as a SPINE node of a centerline when it lies within this
# perpendicular distance of it.  Post-slice the spine nodes sit exactly on the
# line, so this is tight (it only has to absorb float/round noise, not width).
SPINE_PERP_TOL_M = 1.0

# SERVICE-ROAD STRINGING (cycle 8, the D′ finisher — spec
# ``docs/specs/cycle8-one-graph-spec.md`` ADDENDUM).  The tolerance above
# assumes TAXI-style node placement: the global slice cuts pavement ALONG
# a taxi centerline, so its spine nodes land ON the line.  A service road
# is sliced as a CORRIDOR — its nodes sit at the road's two EDGES, half a
# corridor width away — so at 1.0 m a road strings almost nothing and the
# ONE graph never receives the road network.  Measured at the cycle-8
# baseline, both worlds: SPJC 4 service centerline(s) strung (of 389
# apt.dat row-1206 segments), KCLT 10, HECA 0, HEAZ 0 — and ZERO MOUTHS
# at every airport, so ``building_feasibility.groundside_reach_band`` was
# fed by airside-valued nodes alone and every lot beyond its off-net
# radius kept its DEM seed (the D′ class).
# DERIVED, never a fresh magic number: half the corridor width the road
# rects are built at, plus the base tolerance for float/round noise.
SERVICE_SPINE_PERP_TOL_M = SERVICE_ROAD_WIDTH_M / 2.0 + SPINE_PERP_TOL_M

# DIAGNOSTIC-ONLY window margin (``O4_DUMP_SERVICE_STRINGING``): how far
# PAST the tolerance the instrument looks for nodes, so a "just missed"
# node is distinguishable from "no node at all".  Never consulted by the
# stringing decision itself.
_DIAG_MARGIN_M = 25.0

# Apron↔taxi-route CONTACT allowance (user 2026-06-30): an apron ring edge welded
# to a taxi-route pavement earns the taxi cap in its own direction (the contact
# ramp from the apron body down/up to the route), instead of the flat apron cap
# that false-flags it.  ``_ROUTE_CONTACT_TOL_M`` buffers the route union so a
# node ON the shared boundary reads as inside.  Gate off ⇒ prior blend behaviour.
APRON_ROUTE_CONTACT = os.environ.get("O4_APRON_ROUTE_CONTACT", "1") == "1"
_ROUTE_CONTACT_TOL_M = 0.5

# ROUTE-METRIC FAR PAIRS (owner ruling 2026-07-29, HECA south-terminal
# burial): a within-shape pair's budget is priced by the distance a vehicle
# actually travels, not the straight chord.  Near pairs (chord ≤
# ``PAIR_CHORD_LOCAL_M``) keep the chord — local apron planarity is the law
# there, and the deep-set-building case (a pad 200 m back from its taxiway)
# prices as a straight off-graph leg, byte-identical to the chord.  Far
# pairs price at ``cap × max(chord, d_route)`` where ``d_route`` is
# measured on the NON-SERVICE centerline graph (off-graph leg + graph
# distance + off-graph leg — the same airside-only metric the reach band
# seats buildings with).  Without this the all-pair web composes across
# welded shapes into a straight-line Lipschitz bound (HECA: 28 m of budget
# over 2,940 m of chords vs the 5,500 m taxi route) and the movable-pads
# yield lawfully drags route-seated pads ~15 m off their seats.
# BUILDING-endpoint pairs are excluded exactly like the route-arc bake
# (2026-07-03 ruling: buildings are the heaviest constraint).
# ``PAIR_BUDGET_PRUNE_M``: a far pair whose priced budget exceeds any
# plausible airport relief span can never bind and is dropped outright.
ROUTE_METRIC_PAIRS = os.environ.get("O4_ROUTE_METRIC_PAIRS", "1") == "1"
PAIR_CHORD_LOCAL_M = float(os.environ.get("O4_PAIR_CHORD_LOCAL_M", "120"))
# EXACT ROUTE LEGS (owner field report 2026-08-02).  Two defects in the
# route-leg pricing above, measured at HECA, which compose into one
# over-allowance and are therefore gated together:
#   (1) ``_RouteDistanceOracle._nearest`` attaches a point to the nearest
#       graph VERTEX, but the law's "off-spine offset" means the distance
#       to the CENTRELINE.  440 of HECA's 692 axes are 2-point polylines,
#       so a point beside a long straight taxiway attaches to a vertex up
#       to half a segment away: measured off-leg overstatement p90 77.5 m,
#       max 454.5 m, and the owner's ON-CENTRELINE vertex was charged a
#       190 m off-leg.  With this ON the attachment is the nearest POINT
#       ON the polyline and the graph leg is measured from the attachment
#       SEGMENT's two endpoints.
#   (2) ``_route_leg_floor`` lost the chord gate its predecessor
#       ``_route_metric_far_pair`` still applies: it floors EVERY interior
#       pair, including a 38 m one, at a route-travel budget.  With this
#       ON the floor applies only beyond ``PAIR_CHORD_LOCAL_M``, restoring
#       the block comment above ("Near pairs keep the chord — local apron
#       planarity is the law there") and the ``ds_decompose`` principle:
#       the pavement between two nearby points is CONTINUOUS, so the
#       surface gradient between them is what the standards regulate.
# Gate OFF ⇒ the vertex attachment and the ungated floor, byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the field-report fix batch ``0b9efaf``, which built the
# exact attachment + chord-gated floor from the owner's flown lateral
# pricing report — the ungated floor priced 38 m interior apron pairs at a
# route-travel budget, which is the mispricing, not a stricter law).
ROUTE_LEG_EXACT = os.environ.get("O4_ROUTE_LEG_EXACT", "1") == "1"
PAIR_BUDGET_PRUNE_M = float(os.environ.get("O4_PAIR_BUDGET_PRUNE_M", "150"))

# SPINE-FRAME PAIR LAW (owner model, 2026-07-29 burial session: "taxi
# spines, even through aprons, should get the 1.5 % grade, then aprons
# grade out from the spines").  Two deltas over the §3c decomposition:
# (1) apron/junction pairs decompose against their shared/nearest route
# WITHOUT the blend-zone distance gate (the decomposition is a pure
# rotation of the pair separation — see ds_decompose — so this grants
# no arc credit; a far interior chord with no route keeps isotropic
# 1 %), and (2) the LONGITUDINAL cap upgrades to the route's per-letter
# taxi cap (never a service road's own cap — the free-road ruling makes
# in-apron road pavement apron) while the TRANSVERSE cap stays the
# pair's own (apron 1 % across).  Without this the apron's isotropic
# 1 % all-pair web overrides the spine's 1.5 % — the composed
# short-hop chain over HECA's slice-born mega-apron capped the south
# terminals ~15 m under their route-lawful seats no matter how far
# pairs were priced.  Building-endpoint pairs remain excluded
# (2026-07-03: buildings are the heaviest constraint).
SPINE_FRAME_PAIRS = os.environ.get("O4_SPINE_FRAME_PAIRS", "1") == "1"

# ── THE CHORD-TARGET LAW (owner ruling RULINGS 2026-08-25, spec
# ``docs/specs/apron-chord-anchor-target-spec.md`` §1) ────────────────────
# "An apron ring vertex's strict chord is measured to the NEAREST VISIBLE
# anchor across APRON-ONLY pavement, where the anchor set is BOTH the
# building pads and the taxiway centerline nodes — whichever is closer
# wins."  The enumeration below (``nearest_spine_pairs``) therefore searches
# a UNION candidate set and carries the target KIND per pair; the kind
# selects the cap class in ``grade_law.apron_pair_class``.
#
# ``O4_APRON_CHORD_ANCHOR_TARGET=0`` restores the pre-ruling enumeration
# BYTE-FOR-BYTE: spine-coincident candidates only, today's visibility
# population, and the 2026-08-21f pad INTERCEPTION the ruling supersedes.
APRON_CHORD_ANCHOR_TARGET = (
    os.environ.get("O4_APRON_CHORD_ANCHOR_TARGET", "1") != "0")

#: The two anchor kinds carried per chord (spec §1.5).  ONE spelling: the
#: enumeration mints them, ``ShapeConstraints.edge_anchor_kind`` reports
#: them and ``grade_law.PairContext.nearest_anchor_pad`` is set from them.
ANCHOR_KIND_SPINE = "spine"
ANCHOR_KIND_PAD = "pad"

# The per-pair eligibility/cap decision (min-pair-dist, apron body-chord max,
# seam/building/spine/visibility skips, cap selection) is THE LAW — it lives in
# ``grade_law`` so the solver and the grade test share one source.  This module
# is the solver-side reader: it builds a ``grade_law.PairContext`` per pair and
# calls ``grade_law.classify_pair``.


@dataclass
class Centerline:
    """One taxi route centerline through the airport, in the SAME meter frame as
    the shape rings the caller passes.  ``seg_caps`` is the PER-SEGMENT taxiway
    longitudinal grade cap (one per ``pts`` segment, from the route's per-segment
    ICAO size); a route may change width along its length, so the cap is resolved
    locally via :meth:`cap_at`.  ``cap`` is the tightest cap on the route, for the
    scalar within-shape-body consumers."""
    pts: Sequence[tuple[float, float]]
    seg_caps: list = field(default_factory=list)
    # cumulative arc length at each pt (filled lazily)
    _arc: Optional[list[float]] = None
    # Index into ``GradeContext.routes`` of the WHOLE route this bend-split piece
    # belongs to (the chained-route spine-arc frame, see :class:`RouteChain`).
    # ``-1`` ⇒ no chained route attached (legacy / piece is its own route).
    route_idx: int = -1
    # SERVICE-ROAD spine (owner ruling 2026-07-29: "reachability for all
    # airside should never use any groundside or service road paths").
    # Service centerlines still WEAVE into ``G.spine_adj`` (the solve
    # grades roads along their own spine), but edges woven from a
    # flagged centerline are recorded in
    # ``UnifiedGraph.service_spine_pairs`` so the airside reach band can
    # refuse to justify a ceiling/floor through them
    # (``building_feasibility.reach_band_unified``).
    is_service: bool = False

    @property
    def cap(self) -> float:
        return min(self.seg_caps) if self.seg_caps else TAXI_MAX_GRADE

    def cap_at(self, s: float) -> float:
        """Per-segment cap at arc-length ``s`` along the centerline."""
        if not self.seg_caps:
            return TAXI_MAX_GRADE
        a = self.arc()
        for i in range(len(a) - 1):
            if s <= a[i + 1] + 1e-9:
                return self.seg_caps[min(i, len(self.seg_caps) - 1)]
        return self.seg_caps[-1]

    def arc(self) -> list[float]:
        if self._arc is None:
            a = [0.0]
            for i in range(1, len(self.pts)):
                a.append(a[-1] + math.hypot(self.pts[i][0] - self.pts[i - 1][0],
                                            self.pts[i][1] - self.pts[i - 1][1]))
            self._arc = a
        return self._arc


@dataclass
class RouteChain:
    """A WHOLE taxi route (the continuous parent polyline of a set of bend-split
    :class:`Centerline` pieces), in LOCAL meters.

    It exists to give an off-spine pair a single continuous spine-ARC frame: a
    climbing route that curves through a junction is bend-split into short pieces,
    so projecting a body vertex onto one piece resets the arc at every bend and the
    curve never earns its full Δs∥.  Projecting onto the chained route instead
    credits the route's true arc length (``docs/anisotropic_edge_handling_plan.md``
    §3d).  Geometry only — per-letter caps still travel on the ``Centerline``
    pieces; the route supplies the (Δs∥, Δs⊥) decomposition frame, not the cap."""
    pts: Sequence[tuple[float, float]]
    _arc: Optional[list[float]] = None

    def arc(self) -> list[float]:
        if self._arc is None:
            a = [0.0]
            for i in range(1, len(self.pts)):
                a.append(a[-1] + math.hypot(self.pts[i][0] - self.pts[i - 1][0],
                                            self.pts[i][1] - self.pts[i - 1][1]))
            self._arc = a
        return self._arc

    def project(self, x: float, y: float) -> tuple[float, float]:
        """``(arc_pos, perp_dist)`` of ``(x, y)`` onto this chained route."""
        a, d, _ = _project(self, x, y)
        return a, d


@dataclass
class GradeShape:
    """One soft airside shape, representation-agnostic.

    ``ring``  open ring (no repeated closing vertex), LOCAL meter coords.
    ``keys``  stable per-vertex key parallel to ``ring`` (OSM nid | solver idx).
    ``role``  apron | junction | service_junction.
    ``adopts_apron_grade``  USER RULING 2026-07-06: a service road /
    service junction sharing an edge with an apron follows the APRON
    grading rules.  Layout reader: from ``BuiltShape.adopts_apron_grade``;
    OSM reader: from the ``o4_grade_law='apron'`` way tag.

    ``adopts_taxi_grade`` / ``adopted_taxi_letter``  USER RULING 2026-07-07
    (STATUS part 29 item 4): a service-road portion inside/alongside a
    TAXIWAY follows the taxiway grade law (1.5 %, letter-aware via the
    adjacent taxiway's code letter).  Layout reader: from
    ``BuiltShape.adopts_taxi_grade`` / ``.adopted_taxi_letter``; OSM reader:
    from the ``o4_grade_law='taxi'`` way tag (+ ``code_letter``).  Apron
    (1 %) is more limiting than taxi (1.5 %); when both are set apron wins.

    ``lateral_cap``  LATERAL-CONTIGUITY LAW (owner FINAL 2026-08-02, clause
    2): the STRICTEST cap of any pavement class in this piece's laterally-
    contiguous cross-section, when the owning surface could not absorb the
    piece.  Generalises the two adoption flags to the cap itself.  Layout
    reader: ``BuiltShape.lateral_cap``; OSM reader: the ``o4_grade_law_cap``
    way tag.  It is a MINIMUM over the other resolutions — never a
    relaxation.

    ``fan_ramp_zone``  THE FAN-RAMP LAW (owner RULINGS 21f0980): this
    piece IS a declared fan-ramp zone — apron ground between two adjacent
    building frontages, clear of every aircraft-movement surface — and
    holds ``FAN_RAMP_CAP`` (5 %) instead of the apron's 1 %.  Layout
    reader: ``BuiltShape.fan_ramp_zone``; OSM reader: the
    ``o4_grade_law='fan_ramp'`` way tag, both resolved through the ONE
    function ``config.fan_ramp_law_cap``.  The piece is cut out pre-solve
    (``apron_terrace.split_aprons_at_fan_zones``), so this is a whole
    shape's law and not a region-inside-a-shape predicate.
    """
    role: str
    ring: list[tuple[float, float]]
    keys: list[Hashable]
    adopts_apron_grade: bool = False
    fan_ramp_zone: bool = False
    adopts_taxi_grade: bool = False
    adopted_taxi_letter: str | None = None
    lateral_cap: float | None = None
    # Runway DE-SEGMENTATION (O4_RUNWAY_SINGLE_POLY): this is the ONE ring
    # per runway ref whose FAA profile stations are interior long-edge
    # vertices.  ``plane_constraints`` scopes such a ring's within-shape
    # pair domain to LATERAL + same/adjacent-station (user ruling
    # 2026-07-08); a segmented sub-rect leaves this False and keeps its full
    # all-pair check (its short/wide axis would over-segment).  Layout
    # reader: ``BuiltShape.from_single_poly``; OSM reader: the
    # ``o4_single_poly='1'`` way tag.
    single_poly: bool = False


@dataclass
class GradeContext:
    """Shared context every caller builds once from its own representation."""
    centerlines: list[Centerline]
    # The WHOLE routes (chained parent polylines); ``Centerline.route_idx`` indexes
    # this list.  An off-spine pair decomposes against its centerline's route here
    # so a curving route earns its full spine ARC as Δs∥ (anisotropic edge law).
    routes: list[RouteChain] = field(default_factory=list)
    seam_keys: frozenset = frozenset()
    # cap to use for a junction that has NO spine of its own — the caller resolves
    # the nearest connected taxiway-sized shape's cap and passes a lookup keyed by
    # the shape's identity (id(shape) for the solver, way id for the validator).
    inherited_junction_cap: Callable[[GradeShape], float] = (
        lambda s: TAXI_MAX_GRADE)
    # node keys that sit on a BUILDING pad.  An apron/junction edge with BOTH
    # endpoints on a building is the inter-pad FRONTAGE = a building↔building
    # step (allowed by the model — adjacent pads may sit at different levels with
    # a facade/step between them), NOT an apron grade path, so it is not graded.
    # Mirrors the validator's building↔building step exemption.
    building_keys: frozenset = frozenset()
    # ── THE APRON MOVEMENT-SURFACE POPULATION (RULINGS 2026-08-21b) ──────
    # FRONTAGE VERTICES: node keys on a BUILDING ring EDGE whose two endpoints
    # are both soft-pavement ring vertices — production's own predicate, via
    # the ONE function ``grade_law.frontage_vertex_keys`` (anchors._frontage_
    # box).  SAME KEY SPACE as ``building_keys`` (the caller's), and a subset
    # of it by construction.  An APRON pair is within-shape LAW only if it is
    # a FRONTAGE CHORD: one endpoint here, the other in the corridor cover.
    frontage_keys: frozenset = frozenset()
    # ── AMENDMENT A4 ────────────────────────────────────────────────────
    # ``strip_keepout``: the prepared union of every runway's STRIP footprint
    # (``grade_law.runway_strip_wall_keepout_rings`` via
    # ``adjacent_ground.runway_strip_wall_keepout``), or None.  A vertex
    # inside it carries NO apron law (A4.2).  Both context builders fill it
    # from the same function, so the two readers exclude the same ground.
    strip_keepout: object = None
    # ── AMENDMENT A5 ────────────────────────────────────────────────────
    # ``building_polys``: the BUILDING PAD rings as (x, y) tuples, for the
    # pad-interception half of A5.  Geometry, not keys — the keys already
    # live in ``building_keys``/``frontage_keys``, but a chord's INTERSECTION
    # with a pad is a geometric question.  Filled by both context builders
    # from the same shapes, beside ``corridor_lines``.
    building_polys: tuple = ()
    # The centerline GEOMETRY the spine corridor cover is built from — set by
    # the context builders alongside ``centerlines`` so BOTH readers cover the
    # same spines.  The cover itself is built LAZILY and cached (see
    # ``corridor_cover_prepared``): a layout with no building frontage never
    # pays for it, and ``build_context`` is called several times per solve.
    corridor_lines: tuple = ()
    # ── THE BACK-EDGE ZONES (owner ruling RULINGS 2026-08-24) ───────────
    # ``interior_zones``: the fan-ramp BACK-EDGE zone polygons, as OPEN
    # ``((x, y), ...)`` rings in this context's metre frame.  Geometry, not
    # keys — "is this chord wholly inside one zone" is a geometric
    # question, exactly like ``building_polys``.  The SOLVER fills it from
    # ``apron_terrace.plan_fan_ramp_zones`` (the ruling's own predicate,
    # computed live — the zones need not be DECLARED); the CENSUS fills it
    # from the sidecar's ``interior_zones`` export of those same polygons,
    # so both readers price the identical ground.  Empty ⇒ no pair is a
    # back-edge pair and the apron body is strict throughout, which is the
    # conservative direction.
    interior_zones: tuple = ()
    _interior_zones_prep: object = None
    _interior_zones_built: bool = False
    _corridor_cover_prep: object = None
    _corridor_cover_built: bool = False
    _spine_nodes_built: bool = False
    _spine_nodes_m: list = field(default_factory=list)
    # PREPARED geometry of the service-road carve zone (road shapes unioned and
    # buffered by ``ROAD_FRONTAGE_TOL_M``), in the caller's meter frame.  A
    # soft-shape pair with BOTH endpoints inside it descends at the road cap (the
    # carve corners lie on the host ring).  ``None`` ⇒ no road carves.
    road_zone: object = None
    # PREPARED union of the taxi-ROUTE pavements (junction / parallels / stub /
    # cross-connector), buffered a hair.  An apron ring node inside it is welded to
    # a taxi route it abuts — so its ring edges are the apron's CONTACT with that
    # route and earn the taxi cap in their own climbing direction (they must drop
    # from the apron body to the lower/higher route), not the flat apron cap.  Keys
    # off the route PAVEMENT, so it fires even at a wide junction whose painted
    # centerline is far from the contact.  ``None`` ⇒ off.
    route_zone: object = None
    # EXACT-MESH sidecar (user 2026-07-05): the SOLVER's junction triangle-mesh
    # edge set (a ``MeshEdgesExact``), consumed 1:1 by the emitted-OSM reader so
    # emit-time ring repairs (buffer(0), needle-vertex removal, canonical-point
    # interning) cannot mint a DIFFERENT Delaunay than the one the solver graded
    # to (the SPJC cm-noise junction class).  ``None`` ⇒ the reader triangulates
    # its own ring (the solver path, and legacy sidecars).
    mesh_edges_exact: object = None
    # FRAME STAMP for the spine census (cycle 9): which road set the SERVICE
    # centerlines came from (``grade_graph.service_spine_source`` — "sliced"
    # = the slice's own scoped set, road feed included; "apt1206" = no slice
    # ran) and their total length in metres.  Reported, never read as law:
    # "0 service centerlines strung" and "no roads at this airport" have
    # different fix loci and the census could not tell them apart.
    service_source: str = ""
    service_length_m: float = 0.0


@dataclass
class ShapeConstraints:
    """The grade constraints of ONE shape: undirected edges ``(key_a, key_b,
    allowance)`` — where ``allowance`` is a :class:`grade_law.Allowance`
    (anisotropic ``cL·Δs∥ + cT·Δs⊥``; evaluate with ``allowance.at(Δs∥, Δs⊥)``,
    today flat) — plus the spine chains (ordered spine node keys) for the
    connecting solve's smooth-profile handling."""
    role: str
    edges: list[tuple[Hashable, Hashable, "GL.Allowance"]] = field(
        default_factory=list)
    spine_chains: list[list[Hashable]] = field(default_factory=list)
    #: INDEX-PARALLEL to :attr:`edges`: True where the pair is an APRON
    #: INTERIOR pair (``grade_law.is_apron_interior`` on the very
    #: ``PairContext`` ``classify_pair`` judged).  The apron staged solve
    #: (spec ``docs/specs/apron-staged-solve-spec.md``) withholds exactly
    #: these from its senior pass; recording it at MINT is what keeps the
    #: partition the LAW's answer rather than a cap-value guess (a blended
    #: pair can sit at 5 % without being interior).
    edge_interior: list[bool] = field(default_factory=list)
    #: INDEX-PARALLEL to :attr:`edges`: the ANCHOR KIND of the pair when it
    #: is a vertex's nearest-anchor chord (``grade_graph.ANCHOR_KIND_SPINE``
    #: / ``ANCHOR_KIND_PAD``, owner ruling RULINGS 2026-08-25), ``""``
    #: otherwise.  Recorded at MINT for the same reason
    #: :attr:`edge_interior` is: the STAND class now has two sub-populations
    #: (pad-target and spine-target chords) and a report that re-derives
    #: which is which from a cap value would be guessing — a 1 % row is a
    #: stand row whatever its target.
    edge_anchor_kind: list[str] = field(default_factory=list)
    #: INDEX-PARALLEL to :attr:`edges`: True where the pair is a ROAD
    #: ring's CROSS-SECTION (owner ruling RULINGS 2026-08-25g — the pair
    #: axis stands ≥ 45 ° to the ring's long axis, ``grade_law.
    #: pair_is_transverse`` on the very ``PairContext`` ``classify_pair``
    #: judged).  Recorded at MINT for the same reason
    #: :attr:`edge_interior` is: the census reports the cross-section as
    #: its OWN law family, and re-deriving which rows those are from a
    #: 2 %-looking cap value would be a guess — the road cap chain can
    #: reach 2 % by other routes (a narrow-taxi blend, a tightened
    #: frontage), and a guess would mint or lose rows either way.
    edge_transverse_road: list[bool] = field(default_factory=list)
    #: APRON ring keys inside the RUNWAY STRIP footprint (spec AMENDMENT
    #: A4.2).  Those pairs are SKIPPED by the law, so the node never
    #: appears on an edge and the seniority partition — whose domain is
    #: built from edges — could not see it at all.  Recording it HERE, at
    #: the same place the flags are computed for the law, is what lets
    #: ``grade_law.apron_node_seniority`` report ``excluded`` instead of
    #: silently dropping the node (owner ruling RULINGS 2026-08-21d,
    #: wired 2026-08-24).
    strip_excluded: set = field(default_factory=set)


def _open_ring(coords):
    """Open ring (drop the repeated closing vertex)."""
    c = list(coords)
    return c[:-1] if c and c[0] == c[-1] else c


def edge_family_name(role: str, is_spine: bool) -> str:
    """THE within-shape edge-family literal — ``UnifiedGraph.edge_family``'s
    mint-time provenance AND the sidecar ``pair_caps`` family tag
    (``verification.lockstep_pair_caps_ll``).  ONE speller, so the
    certificate's families and the sidecar's cannot drift apart."""
    return f"unified:{role}:spine" if is_spine else f"unified:{role}"


def spine_nodes_m(ctx: "GradeContext") -> list:
    """THE SPINE NODE SET, in the context's metre frame — every vertex of
    every centerline (spec AMENDMENT A4.1(i)).

    ``ctx.centerlines`` is built from ``centerline_specs``, THE one
    enumeration that also produces the sidecar's ``axes_exact``
    (``verification.taxi_axes_exact_ll`` walks the same function), so the
    solver's nearest-spine assignment and the census's are made over the
    IDENTICAL node set by construction — not by two hand-kept copies.  That
    is the lockstep the whole sidecar exists to guarantee, applied to this
    population.
    """
    if ctx._spine_nodes_built:
        return ctx._spine_nodes_m
    ctx._spine_nodes_built = True
    out: list = []
    seen = set()
    for cl in (ctx.centerlines or ()):
        for p in (getattr(cl, "pts", None) or ()):
            k = (round(float(p[0]), 6), round(float(p[1]), 6))
            if k in seen:
                continue
            seen.add(k)
            out.append((float(p[0]), float(p[1])))
    ctx._spine_nodes_m = out
    return out


def _pad_intercept(ring, i, j, ctx):
    """The BUILDING PAD a vertex's centerline chord runs into, or ``None``
    (spec AMENDMENT A5).  Returns the index of a ring vertex ON that pad, so
    the replacement chord stays inside the ring x ring enumeration and mints
    no vertex.

    FRONTAGE AUTHORITY (owner ruling RULINGS 2026-08-21f): a pad standing in
    the path IS what that vertex grades to — the centerline behind it is not
    the surface an aircraft or an apron edge reaches.  So the chord is
    REPLACED, not added: one chord per vertex, still.
    """
    pads = getattr(ctx, "building_polys", None)
    if not pads:
        return None
    try:
        from shapely.geometry import LineString, Polygon
    except ImportError:                                    # pragma: no cover
        return None
    ax, ay = ring[i]
    bx, by = ring[j]
    chord = LineString([(ax, ay), (bx, by)])
    best = None
    bestd = None
    import math as _m
    for pad in pads:
        if len(pad) < 3:
            continue
        try:
            poly = Polygon(pad)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not chord.intersects(poly):
                continue
        except Exception:                                  # pragma: no cover
            continue
        # the pad is in the way — price to the ring vertex ON it that is
        # nearest this one (deterministic: shortest, then lowest index).
        padset = {(round(px, 6), round(py, 6)) for (px, py) in pad}
        for k2, (qx, qy) in enumerate(ring):
            if k2 == i or (round(qx, 6), round(qy, 6)) not in padset:
                continue
            d = _m.hypot(qx - ax, qy - ay)
            if bestd is None or d < bestd - 1e-9 or (
                    abs(d - bestd) <= 1e-9 and k2 < best):
                best, bestd = k2, d
    return best


def nearest_spine_pairs(ring, keys, ctx, vis=None) -> dict:
    """``{(key_a, key_b): kind}`` — ONE chord per ring vertex, to its NEAREST
    VISIBLE ANCHOR, with the anchor's KIND (``ANCHOR_KIND_SPINE`` /
    ``ANCHOR_KIND_PAD``) carried per pair.

    THE ANCHOR SET (owner ruling RULINGS 2026-08-25, spec §1.1) is the UNION
    of two ring-vertex populations:

      (a) vertices lying ON a taxiway centerline — the existing
          ``SPINE_PERP_TOL_M`` notion, unchanged;
      (b) vertices lying on a BUILDING PAD boundary — the enumeration's
          existing ``ctx.building_keys`` membership, the same set the pair
          loop reads as ``bld``/``ki_bld``.  Keys, not geometry, and for a
          load-bearing reason: the CENSUS context fills ``building_keys``
          and does NOT fill ``building_polys``, so a geometric pad test here
          would enumerate a different anchor set in the two readers.

    WHICHEVER IS CLOSER WINS.  This is A4.1(i) as the 2026-08-25 ruling
    amends it: "the pad is a first-class chord target, not merely an
    interceptor when it happens to lie in the path" — so with the ruling
    armed the 2026-08-21f INTERCEPTION step is superseded and does not run;
    a pad standing between a vertex and a centerline is now reached as the
    nearer anchor, and a centerline BEHIND a pad is refused by the very
    visibility gate below (the pad footprint is a re-entrant notch of the
    apron ring, not pavement the chord may cross).

    The far end is always a RING VERTEX — a centerline node welded into the
    ring, or a pad-boundary node welded into it — so the chord stays inside
    the ring x ring enumeration and NO NEW VERTEX is minted (the standing
    "no new vertices" rule).  A vertex with no visible anchor within
    ``BUILDING_REACH_CORRIDOR_M`` contributes nothing (spec §1.4, unchanged
    reach) — the seat does not reach an anchor, and inventing a chord for it
    would be the very long-pair class A4 exists to remove.

    DETERMINISTIC (A4.3(a)): candidates are walked NEAREST-FIRST with ties on
    the lower ring index, so the mapping does not depend on iteration order
    in either reader.  Walking in that order and stopping at the first
    VISIBLE candidate is the same selection the pre-ruling linear scan made
    (it, too, only ever compared visible candidates) and it is what keeps the
    widened candidate set off the build budget: the visibility predicate is
    shapely-priced per chord, so it is asked ~once per vertex instead of once
    per candidate.

    ``O4_APRON_CHORD_ANCHOR_TARGET=0`` (``APRON_CHORD_ANCHOR_TARGET``)
    restores the pre-ruling enumeration exactly: spine candidates only, and
    the 2026-08-21f pad interception back in place.  Every returned pair is
    then ``ANCHOR_KIND_SPINE``, which is today's cap assignment.
    """
    from .config import BUILDING_REACH_CORRIDOR_M as _BUILDING_REACH_CORRIDOR_M
    sp = spine_nodes_m(ctx)
    if not sp or not ring:
        return {}
    import math as _m
    # THE SPINE NODES OF THIS RING are the vertices that LIE ON a centerline,
    # not the ones that coincide with a centerline VERTEX.  Measured: on the
    # A3 HECA patch not one emitted apron ring vertex equals an ``axes_exact``
    # vertex, while the node the owner named sits 0.002 m off the line — the
    # engine welds route geometry onto rings by projection, not by identity.
    # Coordinate identity therefore yields an EMPTY set and makes A4.1(i)
    # inert; ``SPINE_PERP_TOL_M`` is the engine's own on-the-spine tolerance
    # (the same one ``_spine_membership`` uses), so this is that notion, not
    # a new one.
    cand = []
    for i, (x, y) in enumerate(ring):
        for (sx, sy) in sp:
            if _m.hypot(sx - x, sy - y) <= SPINE_PERP_TOL_M:
                cand.append(i)
                break
    spine_cand = set(cand)
    # ── (b) THE PAD-BOUNDARY ANCHORS (RULINGS 2026-08-25) ────────────────
    # ``ctx.building_keys`` is the enumeration's OWN pad membership — the
    # very set the pair loop reads as ``bld`` — so this adds no geometric
    # notion and no vertex.  Both context builders fill it.
    if APRON_CHORD_ANCHOR_TARGET:
        _bld = getattr(ctx, "building_keys", None) or frozenset()
        if _bld:
            for i, k in enumerate(keys):
                if k in _bld and i not in spine_cand:
                    cand.append(i)
    if not cand:
        return {}
    out = {}
    for i, (x, y) in enumerate(ring):
        # Candidates IN REACH, walked NEAREST-FIRST (ties: lower ring index).
        near = []
        for j in cand:
            if j == i:
                continue
            d = _m.hypot(ring[j][0] - x, ring[j][1] - y)
            if d > _BUILDING_REACH_CORRIDOR_M:
                continue
            # Distances are bucketed at 1 nm — the same 1e-9 window the
            # pre-ruling scan compared in, so a tie is still decided by the
            # lower ring index and not by floating-point dust.
            near.append((round(d, 9), j))
        if not near:
            continue
        near.sort()
        best = None
        for _d, j in near:
            # THE SHORTEST *VISIBLE* CHORD (spec AMENDMENT A5; owner rulings
            # RULINGS 2026-08-21f and 2026-08-25 §1.2).  Visibility is the
            # engine's OWN pavement predicate — the same ``vis`` thunk
            # ``classify_pair``'s visibility gate consumes, over this apron
            # ring's own polygon — so no third notion of "can this vertex
            # reach that one" is minted, and the population it is priced
            # over is apron-only by construction.  A nearer anchor behind a
            # re-entrant edge (or across a gap) is not the chord this vertex
            # grades on.
            if vis is not None and not vis(x, y, ring[j][0], ring[j][1]):
                continue
            best = j
            break
        if best is None:
            continue
        if not APRON_CHORD_ANCHOR_TARGET:
            # PAD INTERCEPTION (A5, owner ruling RULINGS 2026-08-21f) — the
            # pre-2026-08-25 law, kept whole behind the flag: a pad standing
            # in the chord's path IS what this vertex grades to; the
            # centerline chord behind it is NOT priced for this vertex.
            # Replacement, not addition — one chord per vertex either way.
            _pad = _pad_intercept(ring, i, best, ctx)
            if _pad is not None:
                best = _pad
        # THE TARGET KIND (spec §1.5).  With the ruling disarmed the
        # pre-2026-08-25 law knows ONE kind — every chord is a chord to a
        # centerline node (an intercepting pad only moved its far end) — so
        # the flag-off enumeration reports ``spine`` throughout and the cap
        # assignment below it is byte-identically today's.
        kind = (ANCHOR_KIND_SPINE
                if (best in spine_cand or not APRON_CHORD_ANCHOR_TARGET)
                else ANCHOR_KIND_PAD)
        ka, kb = keys[i], keys[best]
        pair = (ka, kb) if str(ka) <= str(kb) else (kb, ka)
        # A pair may be selected from BOTH ends (each vertex is the other's
        # nearest anchor).  SPINE WINS the kind — the spine reading is
        # today's assignment and the ruling changes it only where the
        # nearer anchor is a pad.
        if out.get(pair) != ANCHOR_KIND_SPINE:
            out[pair] = kind
    return out


def strip_excluded_flags(ring, ctx) -> list:
    """Per-ring-vertex "inside the runway strip footprint" (A4.2), from
    ``ctx.strip_keepout`` — the SAME prepared union ``adjacent_ground`` and
    ``groundside`` already read.  ``None`` keep-out ⇒ all False."""
    ko = getattr(ctx, "strip_keepout", None)
    if ko is None or not ring:
        return [False] * len(ring)
    from shapely.geometry import Point as _P
    return [bool(ko.intersects(_P(x, y))) for (x, y) in ring]


def interior_zones_prepared(ctx: "GradeContext"):
    """THE BACK-EDGE ZONE INDEX of this context, built once: a list of
    ``(bounds, prepared_polygon)`` over ``ctx.interior_zones``.

    Same shape (and same reason) as ``FanRampPlan._index``: the pair
    predicate is asked tens of thousands of times per airport and a raw
    shapely predicate is ~10 us, so the bbox prefilter plus a PREPARED
    geometry is what keeps the rescope off the build budget.  Empty /
    absent zones ⇒ ``[]``, and the predicate below then answers False
    without touching shapely at all."""
    if ctx._interior_zones_built:
        return ctx._interior_zones_prep
    ctx._interior_zones_built = True
    ctx._interior_zones_prep = []
    if not ctx.interior_zones:
        return ctx._interior_zones_prep
    try:
        from shapely.geometry import Polygon as _IzPoly
        from shapely.prepared import prep as _iz_prep
        idx = []
        for ring in ctx.interior_zones:
            pts = [(float(x), float(y)) for (x, y) in ring]
            if len(pts) < 3:
                continue
            poly = _IzPoly(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly is None or poly.is_empty or poly.geom_type != "Polygon":
                continue
            idx.append((poly.bounds, _iz_prep(poly)))
        ctx._interior_zones_prep = idx
    except Exception:                                     # pragma: no cover
        ctx._interior_zones_prep = []
    return ctx._interior_zones_prep


def interior_zone_of(ctx: "GradeContext", x, y) -> int:
    """The index of the back-edge zone containing ``(x, y)``, or ``-1``.

    ``FanRampPlan.zone_of``'s predicate, over the context's own copy of the
    polygons — ONE spelling for both readers because both readers reach
    THIS function through ``shape_constraints``."""
    for k, (bb, pre) in enumerate(interior_zones_prepared(ctx)):
        if not (bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]):
            continue
        try:
            from shapely.geometry import Point as _IzPt
            if pre.intersects(_IzPt(x, y)):
                return k
        except Exception:                                 # pragma: no cover
            continue
    return -1


def interior_zone_flags(ring, ctx) -> list:
    """Per-ring-vertex back-edge ZONE INDEX (``-1`` outside every zone).

    Computed ONCE per shape and handed to the law as the cheap half of
    ``in_interior_zone`` — the same "membership is the reader's, the
    verdict is the law's" split as ``strip_excluded_flags``."""
    if not ring or not interior_zones_prepared(ctx):
        return [-1] * len(ring)
    return [interior_zone_of(ctx, x, y) for (x, y) in ring]


def interior_zone_pair(ctx, zi: int, zj: int, xa, ya, xb, yb) -> bool:
    """Is this pair WHOLLY inside ONE back-edge zone (RULINGS 2026-08-24)?

    ``FanRampPlan.pair_cap``'s predicate verbatim: both ends in the SAME
    zone (the cheap test, already answered by ``interior_zone_flags``) AND
    the CHORD between them covered by it.  A chord that leaves the zone
    crosses ground the zone does not own, and that ground holds the strict
    apron cap always."""
    if zi < 0 or zi != zj:
        return False
    idx = interior_zones_prepared(ctx)
    if zi >= len(idx):                                    # pragma: no cover
        return False
    try:
        from shapely.geometry import LineString as _IzLine
        return bool(idx[zi][1].covers(_IzLine([(xa, ya), (xb, yb)])))
    except Exception:                                     # pragma: no cover
        return False


def corridor_cover_prepared(ctx: "GradeContext"):
    """The PREPARED spine corridor cover of this context, built once.

    THE APRON WITHIN-SHAPE POPULATION's second half (RULINGS 2026-08-21b): a
    frontage chord's far endpoint must lie ON the spine the seat grades to.
    Geometry and radius come from ``apron_terrace.spine_corridor_cover`` — the
    engine's ONE corridor-cover function and its ONE radius — over
    ``ctx.corridor_lines``, which both readers fill from the SAME spine
    enumeration.  ``None`` ⇒ the airport has no corridor at all."""
    if ctx._corridor_cover_built:
        return ctx._corridor_cover_prep
    ctx._corridor_cover_built = True
    ctx._corridor_cover_prep = None
    if not ctx.corridor_lines:
        return None
    try:
        from .elevation_per_surface.route_profile.apron_terrace import (
            spine_corridor_cover)
        from shapely.prepared import prep as _cc_prep
        cover = spine_corridor_cover(ctx.corridor_lines)
        if cover is not None:
            ctx._corridor_cover_prep = _cc_prep(cover)
    except Exception:                                     # pragma: no cover
        ctx._corridor_cover_prep = None
    return ctx._corridor_cover_prep


def centerline_geometries(centerlines) -> tuple:
    """The shapely geometry of a ``GradeContext.centerlines`` list — the
    ``corridor_lines`` both context builders publish.  ONE conversion, so the
    solver's spine cover and the validator's are the same object shape."""
    from shapely.geometry import LineString as _CLs
    out = []
    for cl in (centerlines or ()):
        pts = list(getattr(cl, "pts", ()) or ())
        if len(pts) < 2:
            continue
        try:
            out.append(_CLs(pts))
        except Exception:                                 # pragma: no cover
            continue
    return tuple(out)


def service_spine_source(layout) -> str:
    """Which road set this layout's SERVICE spine comes from — the frame
    stamp for the spine census (RULINGS 2026-08-06, "Instrument truth is
    law": every reported number carries its frame).

    ``"corridor"`` — the CORRIDOR COURSES (owner 2026-08-12b, one law object
    per corridor): ``layout._service_corridor_lines``, registered whole, with
    the scoped pieces they cover replaced rather than duplicated.
    ``"sliced"`` — the global slice's own scoped road set
    (``layout._slice_service_subsegments``), i.e. every road the slice
    actually cut: apt.dat row-1206 routes AND the per-airport ROAD FEED,
    after free-road scoping.  ``"apt1206"`` — no slice ran (unit fixtures),
    so the row-1206 entries of ``apt_taxi_centerlines`` are the source.
    """
    from .config import SERVICE_CORRIDOR_CHAINS
    if SERVICE_CORRIDOR_CHAINS and (
            getattr(layout, "_service_corridor_lines", None) or []):
        return "corridor"
    return ("sliced"
            if getattr(layout, "_slice_service_subsegments", None) is not None
            else "apt1206")


def centerline_specs(layout) -> list:
    """THE law's centerline membership — aircraft spine AND service roads —
    as ``[(pts, seg_caps, is_service, route_key, route_pts), …]`` in LOCAL
    metres, in one enumeration.

    BOTH readers of the law consume this and only this: :func:`build_context`
    (the solver's and the validator's shared context) and
    ``verification.taxi_axes_exact_ll`` (the sidecar mirror, which the census
    reads back as ``axes_exact``).  They used to be two hand-kept copies of
    the same walk, so a membership change in one was invisible to the other
    and the census would then judge a patch under a spine the build never
    graded to — the half-landed law the RULINGS forbid.  One list, one order,
    so the route ordinals agree by construction rather than by inspection.

    THE SERVICE SOURCE (cycle 9; RULINGS 2026-08-06 "ONE graph: groundside
    joins the route graph" and "Service-road mouths seat like apron-edge
    buildings").  ``apt_taxi_centerlines`` only ever carries the apt.dat
    row-1206 ground-vehicle routes — measured at this lane's baseline: HECA
    5, KCLT 15, SPJC 15, HEAZ 0 — while the roads that actually CARVE the
    slice, and that the emitter ships as ``service_road`` /
    ``service_junction`` shapes, come from the per-airport ROAD FEED (HECA
    705 lines / 97.9 km, KCLT 320, SPJC 84 after free-road scoping).  Those
    roads cut groundside geometry and then never became route edges, so
    nothing downstream of them could reach a band: the mouths fired and the
    band propagated, but only over the row-1206 skeleton, and every lot the
    feed roads serve kept its DEM seed.  That is the D′ population.

    So the service half reads the slice's OWN scoped set
    (``layout._slice_service_subsegments``) wherever the slice ran.  That
    list is the road network as sliced — row-1206 routes and feed ways
    alike, after FREE-ROAD scoping (owner 2026-07-27: a road inside or
    edge-sharing an apron IS the apron, is never carved, and therefore is
    never its own spine either).  The unscoped row-1206 originals are NOT
    also registered: their scoped remains are already in that list, and
    adding the originals would give one physical road two spines at two
    different extents and put a road spine back through the apron portion
    the free-road ruling scoped away.

    Layouts built without the global slice (unit fixtures) have no such
    attribute and keep the pre-cycle-9 source — presence of the attribute is
    the switch, not its truthiness, so a slice that legitimately scoped every
    road away is not silently re-fed from apt.dat.

    ONE LAW OBJECT PER CORRIDOR (owner ruling 2026-08-12b; gate
    ``config.SERVICE_CORRIDOR_CHAINS``).  The scoped subsegments are the
    SLICE's frame, not the corridor's: free-road scoping cuts a corridor
    wherever it runs along wide pavement, so registering the pieces gives one
    physical corridor several disjoint 2-node axes with axis-free gaps
    between them (measured at HECA: corridor A as FOUR axes, gaps s97-254 and
    s269-593; corridor B with no axis at all).  With the gate on, the
    corridor COURSES stashed by the pipeline
    (``layout._service_corridor_lines`` — apt.dat 1206 routes whole, feed
    ways linemerged, deduped between the two sources) are registered as ONE
    chain each and REPLACE the scoped pieces they cover: never both, so no
    road gets two spines (the invariant the cycle-9 note above states).  A
    scoped piece no corridor covers still registers on its own — a piece is
    never silently dropped.

    This does not touch airside law: a service centerline is a spine only for
    a GROUNDSIDE-family shape (:func:`_reads_service_spines`), so a corridor
    crossing an apron is not that apron's spine, and inside the groundside
    family the road cap and the groundside-pavement cap are THE SAME constant
    (``config.GROUNDSIDE_PAVEMENT_MAX_GRADE`` is an alias of
    ``SERVICE_ROAD_MAX_GRADE``), so the composition loosens nothing.

    INPUT-KEYED MEMO (perf P3 lane perfcenter).  Nine to eleven calls per
    build reach this — ``build_context`` twice per graph build, plus the two
    sidecar exports in ``verification`` — and the dupcensus measured EVERY
    one of them after the first reproducing the first's inputs (HECA replay
    11 calls / 1 distinct fingerprint, full build 9 / 1), so the whole set
    of shapely halo buffers and cover intersections below ran ~10 times for
    one answer.  :func:`_cls_specs_key` digests the WHOLE read set and the
    answer is served only while that digest is unchanged; see it for the
    read set and why identity is not the key.
    """
    key = _cls_specs_key(layout) if CENTERLINE_SPECS_MEMO else None
    if key is not None:
        memo = getattr(layout, "_cls_specs_memo", None)
        if memo is not None and memo[0] == key:
            return _cls_specs_fresh(memo[1])
    specs = _centerline_specs_uncached(layout)
    if key is not None:
        try:
            # The memo holds a PRIVATE copy and this call returns the list it
            # just built, so the miss path is byte-for-byte the pre-memo
            # function and no caller ever holds the stored answer.
            layout._cls_specs_memo = (key, _cls_specs_fresh(specs))
        except Exception:                                 # pragma: no cover
            pass
    return specs


#: MEMO KILL SWITCH (perf P3 lane perfcenter).  Module level so the twin can
#: turn the memo OFF and compare the SAME layout's specs with it on — an
#: equality, not an argument.  With it ``False`` this module is exactly what
#: it was before the memo landed.  It is not an env flag and not a law
#: constant: no law reads it and no build changes behaviour under it.
CENTERLINE_SPECS_MEMO = True


def _cls_geom_bytes(g):
    """The EXACT coordinate identity of one geometry, BY VALUE.

    Shapely geometries are immutable (2.x), so a WKB digest is the whole of
    what :func:`centerline_specs` can read out of one — ``is_empty``,
    ``coords`` and ``length`` are all functions of it.  Anything without a
    ``wkb`` raises here and :func:`_cls_specs_key` then declines to memo,
    rather than keying on an input it cannot see.
    """
    return b"\x00none\x00" if g is None else b"\x00g\x00" + g.wkb


def _cls_specs_fresh(specs):
    """A private copy of a spec list.

    The memo must hand every caller the same FRESH ``pts`` / ``seg_caps``
    lists an uncached computation would: ``build_context`` stores them
    directly on its ``Centerline`` / ``RouteChain`` objects, so a shared list
    would put one graph build's answer inside another's.  (No consumer
    mutates them today — audited across ``src/`` and ``tools/`` — which is
    why this is cheap insurance rather than a fix.)  The ``rpts is pts``
    ALIASING is preserved exactly: the corridor and sliced branches, and any
    piece with no ``route_line``, hand back the same object twice.
    """
    out = []
    for (pts, caps, is_svc, rkey, rpts) in specs:
        p = list(pts)
        out.append((p, list(caps), is_svc, rkey,
                    p if rpts is pts else list(rpts)))
    return out


def _cls_specs_key(layout):
    """The memo key for :func:`centerline_specs` — a digest of EVERY input
    that computation reads.  ``None`` ⇒ an input this cannot see, so the
    answer is not memoed at all.

    THE READ SET, walked rather than assumed, through ``centerline_specs``
    and everything it calls (``taxi_grade_cap_for_letter``,
    ``_corridor_cover``, ``_covered_by_corridor``) — it reads nothing else:

      layout   ``apt_taxi_centerlines`` (per entry: ``line``, ``is_service``,
               ``seg_sizes``, ``route_line``), ``_slice_service_subsegments``
               and ``_service_corridor_lines``.  The first is last written in
               phase 1 (``pipeline`` 2585 / 3233, ``centerline_recognition``
               232, ``pavement/route_arcs`` 481), the other two by the global
               slice (``pipeline`` 3489 / 3552) — all before the solve.  The
               key does not RELY on that ordering, it MEASURES it: a write
               after any call simply misses.
      config   ``SERVICE_ROAD_MAX_GRADE`` (the cap written into every service
               ``seg_caps``), ``SERVICE_CORRIDOR_CHAINS`` (the gate),
               ``SERVICE_ROAD_WIDTH_M`` (``_corridor_cover``'s halo width),
               and the four globals ``taxi_grade_cap_for_letter`` reads —
               ``TAXI_GRADE_BY_WIDTH``, ``TAXI_MAX_GRADE``,
               ``TAXI_MAX_GRADE_NARROW``, ``NARROW_TAXI_CODE_LETTERS``.  It
               is called here with no ``ruleset``, so its ruleset branch is
               unreachable from this function.  Read off the config MODULE,
               never this module's import-time aliases: ``centerline_specs``
               and ``_corridor_cover`` both re-import inside the call, so a
               monkeypatched ``config`` value is live for them and must be
               live for the key too.
      module   ``_CORRIDOR_COVER_FRAC``.

    PRESENCE, NOT TRUTHINESS, for ``_slice_service_subsegments``: an absent
    attribute and an empty list select different sources (the docstring's
    "presence of the attribute is the switch"), so they key differently.

    GEOMETRY IS KEYED BY VALUE (WKB), NEVER BY ``id()``.  CPython reuses a
    freed object's address, so an identity key can only be trusted while
    something holds a reference to every object in it — the trap the
    dupcensus had to close to quote its own identity column.  A value key
    has no such precondition.  ROUTE SHARING is keyed structurally beside
    the values, because ``route_line`` binds pieces into routes by OBJECT
    IDENTITY (``rkey = id(rline)``): two equal-but-distinct route lines are
    two routes, and a pure value digest could not tell them from one.  The
    ordinal of first appearance is exactly that pattern expressed as a
    value; each route's own WKB is digested once, when it first appears.
    """
    from . import config as _cfg
    h = hashlib.sha256()
    try:
        h.update(repr((
            float(_cfg.SERVICE_ROAD_MAX_GRADE),
            bool(_cfg.SERVICE_CORRIDOR_CHAINS),
            float(_cfg.SERVICE_ROAD_WIDTH_M),
            float(_CORRIDOR_COVER_FRAC),
            bool(_cfg.TAXI_GRADE_BY_WIDTH),
            float(_cfg.TAXI_MAX_GRADE),
            float(_cfg.TAXI_MAX_GRADE_NARROW),
            tuple(sorted(str(x) for x in _cfg.NARROW_TAXI_CODE_LETTERS)),
        )).encode())
        route_ord: dict = {}
        h.update(b"\x00apt\x00")
        for tcl in (getattr(layout, "apt_taxi_centerlines", []) or []):
            h.update(_cls_geom_bytes(getattr(tcl, "line", tcl)))
            h.update(repr((bool(getattr(tcl, "is_service", False)),
                           tuple(getattr(tcl, "seg_sizes", []) or []))
                          ).encode())
            rline = getattr(tcl, "route_line", None)
            if rline is None:
                h.update(b"\x00r-\x00")
                continue
            # Every ``rline`` is reachable from the list being walked, so no
            # address in ``route_ord`` can be recycled mid-walk; the ordinal
            # that leaves this function is a position, not an address.
            ordinal = route_ord.get(id(rline))
            if ordinal is None:
                ordinal = len(route_ord)
                route_ord[id(rline)] = ordinal
                h.update(b"\x00r%d\x00" % ordinal + _cls_geom_bytes(rline))
            else:
                h.update(b"\x00r%d\x00" % ordinal)
        h.update(b"\x00sliced\x00")
        sliced = getattr(layout, "_slice_service_subsegments", None)
        if sliced is None:
            h.update(b"absent")
        else:
            h.update(b"present")
            for ln in sliced:
                h.update(_cls_geom_bytes(ln))
        h.update(b"\x00corridor\x00")
        for ln in (getattr(layout, "_service_corridor_lines", None) or []):
            h.update(_cls_geom_bytes(ln))
    except Exception:
        return None
    return h.hexdigest()


def _centerline_specs_uncached(layout) -> list:
    """:func:`centerline_specs` with no memo — THE computation.  Split out so
    the memo wrapper is the only thing between a caller and this, and so the
    twin can run both paths on one layout."""
    from .config import (SERVICE_ROAD_MAX_GRADE as _SVC_CAP,
                         SERVICE_CORRIDOR_CHAINS as _CORRIDOR_CHAINS)
    specs: list = []
    sliced = getattr(layout, "_slice_service_subsegments", None)
    use_sliced = sliced is not None
    corridors = [ln for ln in (getattr(layout, "_service_corridor_lines",
                                       None) or [])
                 if ln is not None and not getattr(ln, "is_empty", True)
                 and len(getattr(ln, "coords", ())) >= 2]
    use_corridors = bool(_CORRIDOR_CHAINS and corridors)
    for tcl in (getattr(layout, "apt_taxi_centerlines", []) or []):
        ln = getattr(tcl, "line", tcl)
        if ln is None or getattr(ln, "is_empty", True):
            continue
        is_svc = bool(getattr(tcl, "is_service", False))
        if is_svc and use_sliced:
            continue                    # the sliced set is the service source
        try:
            pts = list(ln.coords)
        except Exception:                                 # pragma: no cover
            continue
        if len(pts) < 2:
            continue
        if is_svc:
            # road spine: own cap, no per-letter table.
            seg_caps = [_SVC_CAP] * (len(pts) - 1)
        else:
            # Per-segment cap from the route's per-segment ICAO size (no
            # name→letter table); padded to one cap per segment.
            sizes = list(getattr(tcl, "seg_sizes", []) or [])
            seg_caps = [taxi_grade_cap_for_letter(sizes[i]) if i < len(sizes)
                        else taxi_grade_cap_for_letter(
                            sizes[-1] if sizes else None)
                        for i in range(len(pts) - 1)]
        # Chain this piece to its WHOLE route.  Pieces bend-split from the
        # same parent share the SAME ``route_line`` object (or fall back to
        # their own ``line``) — key by identity so each distinct route is
        # minted once and every piece points at it.
        rline = getattr(tcl, "route_line", None)
        rkey = id(rline) if rline is not None else ("self", id(ln))
        try:
            rpts = list(rline.coords) if rline is not None else pts
        except Exception:                                 # pragma: no cover
            rpts = pts
        specs.append((pts, seg_caps, is_svc, rkey, rpts))
    covered = None
    if use_corridors:
        # ONE chain per corridor course, registered whole.
        for ln in corridors:
            try:
                pts = list(ln.coords)
            except Exception:                             # pragma: no cover
                continue
            if len(pts) < 2:
                continue
            specs.append((pts, [_SVC_CAP] * (len(pts) - 1), True,
                          ("corridor", id(ln)), pts))
        covered = _corridor_cover(corridors)
    if use_sliced:
        for ln in sliced:
            if ln is None or getattr(ln, "is_empty", True):
                continue
            try:
                pts = list(ln.coords)
            except Exception:                             # pragma: no cover
                continue
            if len(pts) < 2:
                continue
            if covered is not None and _covered_by_corridor(ln, covered):
                continue    # its corridor chain carries it — never both
            # A sliced subsegment IS its own route: free-road scoping cut it
            # at the stations where the road stops being a free road, and the
            # law downstream of that cut is the apron's, not this road's.
            specs.append((pts, [_SVC_CAP] * (len(pts) - 1), True,
                          ("svc", id(ln)), pts))
    # ── APRON SPINES (owner ruling RULINGS 2026-08-25h, spec
    # ``service-road-apron-spine-spec.md`` §2) ────────────────────────────
    # "A truck route along/through an apron is a SPINE at the apron's cap —
    # like a taxiway, but 1 %."  These are the stretches free-road scoping
    # REMOVED (``groundside.apron_spine_subsegments``, its own complement):
    # until now they reached the grade graph with no centerline at all, so
    # nothing anchored the apron chain and the road family at the same
    # welded stations.
    #
    # THEY ARE CENTERLINES, so they enter phase A / the scaffold anchor set
    # and the chord-anchor law's CENTERLINE targets for free — the target
    # set grows, the mechanics do not change (§2.1).
    #
    # ``is_service`` STAYS TRUE, and that is the load-bearing half of §2.2:
    # ``REACH_NO_SERVICE_SPINES`` gates the reachability BAND off these
    # edges, and a spine that joined the band's route graph would be the
    # airside-contamination regression class.  The cap changes; the band
    # membership does not.
    from .config import (APRON_MAX_GRADE as _APRON_CAP,
                         SERVICE_APRON_SPINE as _APRON_SPINE_ON)
    if _APRON_SPINE_ON:
        for ln in (getattr(layout, "_apron_spine_subsegments", None) or []):
            if ln is None or getattr(ln, "is_empty", True):
                continue
            try:
                pts = list(ln.coords)
            except Exception:                             # pragma: no cover
                continue
            if len(pts) < 2:
                continue
            specs.append((pts, [_APRON_CAP] * (len(pts) - 1), True,
                          ("apron_spine", id(ln)), pts))
    return specs


# A corridor chain REPLACES a scoped subsegment when the subsegment lies
# inside the corridor's own road-width halo over more than this fraction of
# its length — the same "is this the same physical road" question the
# centerline-level source dedupe asks, at the same width.
_CORRIDOR_COVER_FRAC = 0.5


def _corridor_cover(corridors):
    """Road-width halo of the corridor courses (or ``None``)."""
    from .config import SERVICE_ROAD_WIDTH_M
    try:
        from shapely.geometry import LineString  # noqa: F401
        from shapely.ops import unary_union
        return unary_union([
            ln.buffer(SERVICE_ROAD_WIDTH_M / 2.0, cap_style=2, join_style=2)
            for ln in corridors])
    except Exception:                                     # pragma: no cover
        return None


def _covered_by_corridor(line, cover) -> bool:
    if cover is None or cover.is_empty:
        return False
    try:
        if line.length <= 0.0:
            return False
        return (line.intersection(cover).length / line.length
                > _CORRIDOR_COVER_FRAC)
    except Exception:                                     # pragma: no cover
        return False


def service_chain_lines(layout) -> list:
    """THE service centerline set, as ``LineString``s — one source.

    Exactly the SERVICE half of :func:`centerline_specs` (corridor chains
    where the corridor gate registers them, the free-road-scoped
    subsegments elsewhere, the row-1206 originals in unit fixtures), for
    consumers that need the GEOMETRY rather than the specs.

    Added by the corridor-joins round (ruling 3): the DEM-follow spine
    seeder used to walk ``apt_taxi_centerlines`` filtered on ``is_service``
    — the row-1206 set alone — so a FEED-sourced corridor chain was
    invisible to it and its road fell through to the per-vertex fallback
    (measured at KCLT 35.2077054,-80.9290667: 2.9 % descent against an 8 %
    cap, ending 6.31 m proud of DEM).  A second enumeration of "which roads
    are roads" is exactly the drift this module's ``centerline_specs``
    docstring exists to prevent, so the seeder reads this and nothing else.
    """
    from shapely.geometry import LineString
    out: list = []
    for (pts, _caps, is_svc, _rkey, _rpts) in centerline_specs(layout):
        if not is_svc or len(pts) < 2:
            continue
        try:
            out.append(LineString(pts))
        except Exception:                                 # pragma: no cover
            continue
    return out



# ══════════════════════════════════════════════════════════════════════
# THE BUILDING-PAD CLAIM — one rule, every identity space
# ══════════════════════════════════════════════════════════════════════
# ``ctx.building_keys`` is what makes ``grade_law.classify_pair`` price a
# pair at ``BUILDING_FRONTAGE_MAX_GRADE`` ("buildings are the HEAVIEST
# constraint", user 2026-07-03).  It has TWO populations, and BOTH are
# the claim:
#   (1) a BUILDING RING VERTEX;
#   (2) an ON-EDGE node — one lying within ``SHARED_VERTEX_TOL_M`` of a
#       pad BOUNDARY without being one of its ring vertices, because the
#       pad only acquires the shared vertex later at the nid-level weld.
#
# WHY THIS IS A SHARED OBJECT AND NOT A SECOND WALK (measured, this
# lane).  The late chord limiter re-derived the claim from ring vertices
# alone — population (1) — and its frontage exemption was therefore a
# no-op exactly where the regression was: HECA site B's frontage pairs
# come from population (2), road nodes NEAR a pad boundary.  15 rows
# stayed at 6.04 m / 37.6 % across a whole verification build.  THE LAW'S
# CLAIM SET IS THE PIN SET (owner ruling), so the rule lives here once
# and every reader supplies its own key function — the same shape
# ``grade_law.frontage_vertex_keys`` documents ("expressed on KEYS so
# every reader can supply its own identity space").
class BuildingClaim:
    """Does a BUILDING PAD claim this point?  Both populations.

    ``contains(x, y)`` answers in PLAN COORDINATES, so a caller keys the
    answer however it likes (solver node indices, rounded layout metres,
    emitted node ids).  Cheap by construction: a coarse bounding-box cell
    prefilter, then the prepared boundary test only for points that land
    in one — the same prefilter ``build_context`` measured at ~0.01 s per
    call against 0.34 s for a dense perimeter walk at HECA.
    """

    _GCELL = 8.0

    def __init__(self, polys, tol):
        self.tol = float(tol)
        self._zone = None
        self._cells = set()
        polys = [p for p in polys if p is not None and not p.is_empty]
        if not polys:
            return
        for poly in polys:
            x0, y0, x1, y1 = poly.bounds
            for cx in range(int(math.floor((x0 - self.tol) / self._GCELL)),
                            int(math.floor((x1 + self.tol) / self._GCELL)) + 1):
                for cy in range(int(math.floor((y0 - self.tol) / self._GCELL)),
                                int(math.floor((y1 + self.tol) / self._GCELL)) + 1):
                    self._cells.add((cx, cy))
        try:
            from shapely.ops import unary_union as _uu
            from shapely.prepared import prep as _prep
            self._zone = _prep(_uu([p.boundary for p in polys])
                               .buffer(self.tol))
        except Exception:                                  # pragma: no cover
            self._zone = None

    def __bool__(self):
        return self._zone is not None

    def contains(self, x, y) -> bool:
        """Population (2): within ``tol`` of some pad's BOUNDARY."""
        if self._zone is None:
            return False
        if (int(math.floor(x / self._GCELL)),
                int(math.floor(y / self._GCELL))) not in self._cells:
            return False
        try:
            from shapely.geometry import Point as _Pt
            return bool(self._zone.contains(_Pt(x, y)))
        except Exception:                                  # pragma: no cover
            return False


def building_pad_polygons(layout):
    """The BUILDING pads of ``layout`` — the one enumeration behind both
    ``ctx.building_keys`` and the late limiter's pin."""
    from .layout import ROLE_BUILDING
    return [s.polygon for s in layout.shapes
            if s.role == ROLE_BUILDING and s.polygon is not None
            and not s.polygon.is_empty]


def building_claim(layout):
    """THE building-pad claim for ``layout`` (:class:`BuildingClaim`)."""
    from .layout import SHARED_VERTEX_TOL_M
    return BuildingClaim(building_pad_polygons(layout), SHARED_VERTEX_TOL_M)


def build_context(layout, bucket_to_idx=None) -> "GradeContext":
    """THE single shared grade-graph context (solver + spine + validator).

    Builds the taxi centerlines (LOCAL meters, per-letter caps), the spine-less
    junction cap-inheritance lookup (nearest connected taxiway-sized rect), and
    the building-pad key set.  The route-profile solver (via
    ``build_unified_graph``) and the validator
    (``grade_graph_validate.within_violations``) both call this, so the
    centerlines, caps and inheritance can never drift (docs/single_grade_graph.md).

    ``bucket_to_idx`` selects the BUILDING-KEY space (the one place the two
    representations diverge):

      * given (solver / spine, pre-emit) → SOLVER NODE INDICES
        (``bucket_to_idx[canonical_points.get_or_add(x, y)]``), matching the
        node-idx ``keys`` those callers put on their ``GradeShape``s;
      * ``None`` (validator, post-emit) → ROUNDED-COORD tuples
        ``(round(x, 3), round(y, 3))`` — the validator keys its shapes by ring
        index and matches buildings by coordinate.
    """
    from .elevation_per_surface.solver_primitives import (
        ADJACENT_CAP_ROLES, _shape_grade)
    from .layout import ROLE_BUILDING

    cls: list[Centerline] = []
    routes: list[RouteChain] = []
    route_key_to_idx: dict = {}
    # GLOBAL-SLICE spine (user 2026-07-02): service ROADS are spines too —
    # narrow truck routes are sliced like taxiways and their faces grade
    # LONGITUDINALLY along the road at the road cap ("two roughly parallel
    # spines with the right grade cap").  Membership, per-segment caps and
    # route binding all come from ``centerline_specs`` — the ONE enumeration
    # this context and the sidecar mirror share, so the solver, the
    # validator and the census cannot drift on which roads are roads
    # (cycle 9; the road feed reaches the graph through it).
    _svc_len_m = 0.0
    for (pts, seg_caps, _is_svc, rkey, rpts) in centerline_specs(layout):
        ridx = route_key_to_idx.get(rkey)
        if ridx is None:
            ridx = len(routes)
            routes.append(RouteChain(pts=rpts))
            route_key_to_idx[rkey] = ridx
        cls.append(Centerline(pts=pts, seg_caps=seg_caps, route_idx=ridx,
                              is_service=_is_svc))
        if _is_svc:
            _svc_len_m += sum(math.hypot(b[0] - a[0], b[1] - a[1])
                              for (a, b) in zip(pts, pts[1:]))

    # Adjacent-cap node coords -> cap: a shape with NO spine inherits the
    # cap of an ADJACENT_CAP_ROLES shape it shares a ring node with (live
    # via service roads — a junction sharing ring nodes with a road
    # inherits the 4 % cap; the surviving slice of the rect-era
    # inheritance, owner 2026-07-29).
    rect_cap_at: dict = {}
    for s in layout.shapes:
        if (s.role not in ADJACENT_CAP_ROLES or s.polygon is None
                or s.polygon.is_empty):
            continue
        cap = _shape_grade(layout, s)
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            k = (round(x, 3), round(y, 3))
            if rect_cap_at.get(k, -1.0) < cap:
                rect_cap_at[k] = cap

    def _inherited(shape):
        best = None
        for (x, y) in shape.ring:
            c = rect_cap_at.get((round(x, 3), round(y, 3)))
            if c is not None and (best is None or c > best):
                best = c
        return best if best is not None else TAXI_MAX_GRADE

    cps = getattr(layout, "canonical_points", None)

    def _law_key(x, y):
        """This context's node key for a layout coordinate — the ONE key
        function ``building_keys`` and ``frontage_keys`` share (they are the
        same identity space by construction: a frontage vertex IS a building
        ring vertex)."""
        if bucket_to_idx is not None and cps is not None:
            return bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
        return (round(x, 3), round(y, 3))

    bld_keys: set = set()
    bld_polys: list = []
    bld_key_rings: list = []
    for s in layout.shapes:
        if (s.role == ROLE_BUILDING and s.polygon is not None
                and not s.polygon.is_empty):
            bld_polys.append(s.polygon)
            ring_keys = []
            for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
                k = _law_key(x, y)
                ring_keys.append(k)
                if k is not None:
                    bld_keys.add(k)
            bld_key_rings.append(ring_keys)
    # ON-EDGE PAD MEMBERSHIP (2026-07-28).  A solve node can lie EXACTLY on a
    # pad boundary without being one of that pad's ring vertices: the pad only
    # acquires the shared vertex later, at the nid-level final weld.  Keying
    # building membership off ring-vertex identity alone therefore read the
    # SAME PHYSICAL VERTEX two ways in one build — SPJC apron/-10191 node
    # (915.482, -1130.138) sits 0.00000 m from ``building81``'s boundary, yet
    # the solve context held 627 building keys and the final projection's 683,
    # differing by exactly the 56 on-edge nodes.  That is not cosmetic:
    # ``grade_law.classify_pair``'s apron body-chord cap
    # (``APRON_BODY_CHORD_MAX_M``) EXEMPTS building-endpoint pairs, so the
    # divergence silently dropped every long building-frontage chord from the
    # body yield's graph (fp#8 never enforced them, the free endpoint drifted)
    # while ``final_grade_projection`` DID bake them — and the validator,
    # consuming that bake in lockstep, graded pairs the solve had never
    # constrained.  Register on-boundary nodes here so both readings agree BY
    # CONSTRUCTION.  Solver key space only: the validator's post-emit rings
    # already carry the welded vertex, so its coordinate keying sees it.
    if bucket_to_idx and bld_polys:
        from .layout import SHARED_VERTEX_TOL_M
        # ONE RULE, delegated (see :class:`BuildingClaim` above).  This
        # used to be an inline prefilter + prepared-boundary test; it is
        # the SAME test, now shared with the late chord limiter so the
        # law's claim set and the limiter's pin set cannot be two
        # different populations (measured: they were, and the limiter's
        # frontage exemption no-op'd on HECA site B because of it).
        _claim = BuildingClaim(bld_polys, SHARED_VERTEX_TOL_M)
        if _claim:
            for (c, i) in bucket_to_idx.items():
                if i in bld_keys:
                    continue
                if _claim.contains(c[0], c[1]):
                    bld_keys.add(i)
    # Service-road carve zone — a soft-shape pair on a road carve descends at the
    # road cap (the carve corners lie on the host ring).  Built ONCE here so the
    # solver and the validator regulate it identically (the law, not a fudge).
    road_zone = None
    road_polys = [s.polygon for s in layout.shapes
                  if s.role in ("service_road", "service_junction")
                  and s.polygon is not None and not s.polygon.is_empty]
    # CONTEXT-CONSERVATIVE ABSORPTION (membership round V2, spec §V2.A).
    # Clause-4 absorption deletes a road SHAPE; the carve zone is keyed on
    # the road FOOTPRINT, and dropping it silently re-prices every soft
    # pair whose endpoints sat on that carve.  The retained footprint goes
    # back in, so this zone is the same geometry whether the stretch was
    # absorbed or not — absorption moves surface identity and cap, never
    # the law's context geometry.  Both the solver and the validator reach
    # this code, so they stay in lockstep.  Empty off the lateral law.
    from .layout import absorbed_road_context_polys as _abs_ctx
    road_polys += _abs_ctx(layout, roles=("service_road",
                                          "service_junction"))
    if road_polys:
        try:
            from shapely.ops import unary_union as _uu
            from shapely.prepared import prep as _prep
            from .config import ROAD_FRONTAGE_TOL_M
            road_zone = _prep(_uu(road_polys).buffer(ROAD_FRONTAGE_TOL_M))
        except Exception:                                     # pragma: no cover
            road_zone = None

    # Taxi-ROUTE pavement zone — apron edges that contact it are contact ramps and
    # earn the taxi cap (user 2026-06-30).  Keyed off the pavement (not the far
    # centerline) so it fires at wide-junction contacts.  Gate O4_APRON_ROUTE_CONTACT.
    route_zone = None
    if APRON_ROUTE_CONTACT:
        route_polys = [s.polygon for s in layout.shapes
                       if s.role in ("junction", "primary_parallel",
                                     "secondary_parallel", "stub", "cross_connector")
                       and s.polygon is not None and not s.polygon.is_empty]
        if route_polys:
            try:
                from shapely.ops import unary_union as _uu
                from shapely.prepared import prep as _prep
                route_zone = _prep(_uu(route_polys).buffer(_ROUTE_CONTACT_TOL_M))
            except Exception:                                 # pragma: no cover
                route_zone = None

    # Tile-seam pin keys (user 2026-07-04, "treat the seam like a runway
    # edge or building"): the solver-side law was running with NO seam
    # concept (empty default) while the validator zone-flagged 400 m —
    # the one place the two readers disagreed on the LAW itself.  The
    # solver's key space is node indices, so the pin set published by
    # ``solver_primitives._seed_elevations`` (which runs before every
    # ``build_context`` call in the solve) is used verbatim; callers
    # without a solve in flight (no attribute) get an empty set = the old
    # behaviour.  The validator builds its own nid-space set from the
    # sidecar's ``seam_pins`` export.
    seam_pin_idx = getattr(layout, "_seam_pin_idx", None) or ()

    # ── FRONTAGE VERTICES (owner ruling RULINGS 2026-08-21b) ─────────────
    # The soft ring vertices a building pad shares a whole EDGE with — the
    # apron within-shape population's first half.  Roles and predicate are
    # the LAW's (``grade_law.FRONTAGE_SOFT_ROLES`` /
    # ``frontage_vertex_keys``), keyed by ``_law_key`` so this set is a
    # SUBSET of ``building_keys`` in whichever space this caller uses.
    soft_front_keys: set = set()
    if bld_key_rings:
        for s in layout.shapes:
            if (s.role not in GL.FRONTAGE_SOFT_ROLES or s.polygon is None
                    or s.polygon.is_empty):
                continue
            for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
                k = _law_key(x, y)
                if k is not None:
                    soft_front_keys.add(k)
    frontage_keys = (GL.frontage_vertex_keys(bld_key_rings, soft_front_keys)
                     if soft_front_keys else set())

    # ── THE RUNWAY-STRIP KEEP-OUT (spec AMENDMENT A4.2; owner ruling
    # RULINGS 2026-08-21d, WIRED 2026-08-24) ─────────────────────────────
    # ``GradeContext.strip_keepout`` existed and was documented from the
    # day A4.2 landed, but NOTHING EVER ASSIGNED IT — so
    # ``strip_excluded_flags`` read ``None`` on every production build,
    # ``is_apron_in_strip`` answered False for every pair, and the ruling's
    # acceptance counts came from a re-derivation rather than from the
    # law.  One geometry, one function: the SAME prepared union
    # ``adjacent_ground`` and ``groundside`` read.  ``require_gate=False``
    # because A4.2 is not the retaining-wall gate's clause — the footprint
    # is a law function regardless of whether walls are enabled.
    strip_keepout = None
    try:
        from .adjacent_ground import runway_strip_wall_keepout as _rswk
        strip_keepout = _rswk(layout, require_gate=False)
    except Exception:                                         # pragma: no cover
        strip_keepout = None
    # ── THE BACK-EDGE ZONES (owner ruling RULINGS 2026-08-24) ────────────
    # Computed LIVE from ``plan_fan_ramp_zones``' predicate — the ruling is
    # explicit that the zones need NOT be declared, so nothing here splits
    # an apron, mints a shape or touches the terrace pass (fan ZONES stay
    # retired under W2).  This is a pure read of the pad-adjacency geometry
    # for the LAW's use, cached on the LAYOUT because ``build_context`` is
    # called several times per solve and the answer is a function of the
    # geometry alone.
    interior_zones = getattr(layout, "_interior_zone_rings", None)
    if interior_zones is None:
        interior_zones = ()
        try:
            from .elevation_per_surface.route_profile.apron_terrace import (
                plan_fan_ramp_zones as _pfrz)
            _plan = _pfrz(layout, icao=getattr(layout, "icao", "") or "")
            interior_zones = tuple(
                tuple(_open_ring(list(z["polygon"].exterior.coords)))
                for z in _plan.zones
                if z.get("polygon") is not None
                and not z["polygon"].is_empty
                and z["polygon"].geom_type == "Polygon")
        except Exception:                                     # pragma: no cover
            interior_zones = ()
        setattr(layout, "_interior_zone_rings", interior_zones)
    ctx = GradeContext(centerlines=cls, routes=routes,
                       inherited_junction_cap=_inherited,
                       building_keys=frozenset(bld_keys), road_zone=road_zone,
                       route_zone=route_zone,
                       strip_keepout=strip_keepout,
                       interior_zones=interior_zones,
                       frontage_keys=frozenset(frontage_keys),
                       corridor_lines=centerline_geometries(cls),
                       building_polys=tuple(
                           tuple(_open_ring(list(s.polygon.exterior.coords)))
                           for s in layout.shapes
                           if (s.role == ROLE_BUILDING and s.polygon is not None
                               and not s.polygon.is_empty
                               and s.polygon.geom_type == "Polygon")),
                       seam_keys=frozenset(seam_pin_idx),
                       service_source=service_spine_source(layout),
                       service_length_m=_svc_len_m)
    # RUN-SCOPED LAW MEMO (perf P3 lane perfgraph) — see
    # :func:`shape_constraints_cached`.  It hangs off the LAYOUT, not this
    # module: one solve run is one layout, so the memo cannot outlive the
    # geometry it was derived from, and a process that builds several
    # airports (a tile) never carries one airport's answers into the next.
    #
    # SOLVER KEY SPACE ONLY (``bucket_to_idx is not None``).  The other
    # space is the VALIDATOR's, and it is not merely different, it is
    # COLLIDABLE: its shapes are keyed by RING INDEX (0, 1, 2, …) and its
    # building membership by rounded coordinate, so a validator shape and
    # a solver shape whose node indices happen to be 0..n-1 can present
    # the same ring, the same keys and the same all-False membership
    # vector — one key, two different laws.  The validator builds its
    # graph once per run, so excluding it costs nothing measurable and
    # removes the whole class.
    if SC_RUN_MEMO and bucket_to_idx is not None:
        try:
            run = getattr(layout, "_sc_run_memo", None)
            if run is None:
                run = {}
                layout._sc_run_memo = run
            ctx._sc_run_memo = run
        except Exception:                                 # pragma: no cover
            pass
    return ctx


# ── visibility ──────────────────────────────────────────────────────────────

def _visibility_predicate(ring: list[tuple[float, float]]):
    """Return ``vis(xa,ya,xb,yb)->bool``: True iff the chord stays inside the
    ring grown by ``_VIS_BUF``.  ``None`` if shapely is unavailable / the polygon
    is degenerate (caller falls back to plain all-pair).

    THE POLYGON POPULATION IS THIS SHAPE'S OWN RING — which is what makes
    this predicate already answer the RULINGS 2026-08-25 / spec §1.2
    question ("visibility is priced across APRON-ONLY pavement; the chord
    may not cross non-apron pavement or gaps") for the apron chord
    enumeration: the ring IS one apron's pavement, a chord that leaves it
    (a gap, a re-entrant edge, ground beyond the apron) is not visible, and
    a pad-boundary anchor is a vertex OF this ring, so the pad's own
    footprint at the target end is walkable by construction.  No pad or
    route GEOMETRY may enter this population: the census context carries no
    ``building_polys`` at all, so a pad-augmented population here would
    make the two readers price different chords — the census-wrapper defect
    in its structural form.
    """
    try:
        import shapely as _shapely
        from shapely.geometry import LineString, Polygon
        from shapely.prepared import prep
    except ImportError:  # pragma: no cover
        return None
    try:
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        poly = poly.buffer(_VIS_BUF)
        if poly.is_empty:
            return None
        pg = prep(poly)
    except Exception:
        return None

    def _vis(xa, ya, xb, yb):
        try:
            return pg.contains(LineString(((xa, ya), (xb, yb))))
        except Exception:
            return True

    # ROW BATCH (perf P3 lane D).  ``pg`` is a prepared wrapper around
    # ``poly``, and ``prep()`` prepares ``poly`` ITSELF, so the vectorized
    # ``shapely.contains(poly, chords)`` runs the SAME prepared GEOS
    # predicate on the SAME chord coordinates — one Python-level dispatch
    # for a whole row of chords instead of one per chord.  Same predicate,
    # same inputs, same verdicts; only the dispatch count changes.
    def _vis_batch(chords):
        return _shapely.contains(poly, chords)

    _vis.batch = _vis_batch
    return _vis


# ── spine membership ────────────────────────────────────────────────────────

def _project(cl, x: float, y: float):
    """Return ``(arc_pos, perp_dist, (foot_x, foot_y))`` of ``(x, y)`` onto the
    polyline ``cl`` (any object exposing ``.pts`` + ``.arc()`` — a
    :class:`Centerline` piece or a whole :class:`RouteChain`)."""
    best_d = float("inf")
    best_a = 0.0
    best_foot = (x, y)
    arc = cl.arc()
    for i in range(len(cl.pts) - 1):
        ax, ay = cl.pts[i]
        bx, by = cl.pts[i + 1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-12:
            continue
        t = ((x - ax) * dx + (y - ay) * dy) / seg2
        t = max(0.0, min(1.0, t))
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(x - px, y - py)
        if d < best_d:
            best_d = d
            best_a = arc[i] + t * math.sqrt(seg2)
            best_foot = (px, py)
    return best_a, best_d, best_foot


def _polyline_tree(ctx: "GradeContext", which: str):
    """Lazy STRtree over ``ctx.centerlines`` (`which='cl'`) or ``ctx.routes``
    (`which='routes'`), cached ON the ctx object and invalidated when the
    list length changes (the blend builds a filtered shallow copy).

    The linear nearest-scan was O(vertices x lines x line_pts): with the
    route-arc global slice there are ~500 UNCHAINED lines, and profiling
    showed 25M ``_project`` calls / ~90 s per SPJC build in these lookups.
    Returns ``(tree, idx_list, geom_list)`` (tree None when no geometry)."""
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    items = ctx.centerlines if which == "cl" else ctx.routes
    cache_attr = "_tree_" + which
    n_attr = cache_attr + "_n"
    cached = getattr(ctx, cache_attr, None)
    if cached is not None and getattr(ctx, n_attr, -1) == len(items):
        return cached
    geoms, idxs = [], []
    for i, it in enumerate(items):
        if len(it.pts) >= 2:
            try:
                geoms.append(LineString(it.pts))
                idxs.append(i)
            except Exception:
                continue
    cached = (STRtree(geoms) if geoms else None, idxs, geoms)
    try:
        setattr(ctx, cache_attr, cached)
        setattr(ctx, n_attr, len(items))
    except Exception:
        pass
    return cached


def ds_decompose(pa: tuple[float, float], pb: tuple[float, float],
                 route) -> tuple[float, float]:
    """Decompose the separation of two points into ``(Δs∥, Δs⊥)`` w.r.t. a route
    (a :class:`RouteChain` or :class:`Centerline`):

    * ``Δs∥`` = the CHORD between the two projection foot points — the pair's
      along-route component measured on the SURFACE;
    * ``Δs⊥`` = the residual transverse offset, ``√(max(0, sep² − long_chord²))``
      — so ``Δs∥² + Δs⊥² = sep²`` exactly: the decomposition is a rotation of
      the direct pair separation, never an inflation.

    ⚠ Δs∥ was originally the along-route ARC (``|arc_a − arc_b|``, "a climbing
    turn earns its full longitudinal budget").  MEASURED WRONG (user JOSM/sim
    review 2026-07-03): near curves two physically-CLOSE points project far
    apart along the route, so the arc form granted budgets far beyond any
    surface cap — 7,040 SPJC pairs steeper than 1.5 % were "legal" (worst
    12.5 % over 5.2 m ruled legal at a nominal 1.5 % cap): visible cliffs
    perpendicular to the spine and >1 % terminal-frontage ramps at ZERO
    reported violations.  The pavement between two nearby points is
    continuous — the surface gradient between them is what the standards
    regulate, so the budget must be built from the direct separation, only
    ROTATED into (∥, ⊥) so ``cL``/``cT`` anisotropy still applies.

    THE single decomposition primitive — the anisotropic allowance is then
    ``Allowance.at(Δs∥, Δs⊥) = cL·Δs∥ + cT·Δs⊥`` (``grade_law``); the solver and
    validator both call it, so the built and checked surfaces use identical math.
    For a STRAIGHT route this returns ``(sep, 0)`` (the isotropic ``cap·dist``
    case), so straight taxiways/aprons are unaffected."""
    # Per-route projection memo: under the spine-frame law every
    # same-cell pair decomposes, so a big shape re-projects each ring
    # vertex O(n) times — cache the foot point per (rounded) vertex.
    memo = getattr(route, "_proj_memo", None)
    if memo is None:
        memo = {}
        try:
            route._proj_memo = memo
        except Exception:
            memo = None
    if memo is not None:
        ka = (round(pa[0], 3), round(pa[1], 3))
        kb = (round(pb[0], 3), round(pb[1], 3))
        ra = memo.get(ka)
        if ra is None:
            ra = _project(route, pa[0], pa[1])
            memo[ka] = ra
        rb = memo.get(kb)
        if rb is None:
            rb = _project(route, pb[0], pb[1])
            memo[kb] = rb
        _arc_a, _da, qa = ra
        _arc_b, _db, qb = rb
    else:
        _arc_a, _da, qa = _project(route, pa[0], pa[1])
        _arc_b, _db, qb = _project(route, pb[0], pb[1])
    sep = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    long_chord = math.hypot(qa[0] - qb[0], qa[1] - qb[1])
    ds_par = min(long_chord, sep)
    ds_perp = math.sqrt(max(0.0, sep * sep - ds_par * ds_par))
    return ds_par, ds_perp


def _reads_service_spines(shape: GradeShape) -> bool:
    """May THIS shape's own law read a SERVICE centerline as its spine?

    Only a groundside-family shape may (``layout.GROUNDSIDE_ROLES`` — the
    road itself, the lot it serves).  A TRUCK ROUTE IS NOT AN AIRCRAFT
    SPINE: the same principle the apron↔taxi blend already applies ("a
    truck route's cap belongs to its own strip faces, not to the apron
    around it", 2026-07-02) — stated once here, on the law's own role
    partition, instead of by cap comparison.

    It became load-bearing when the ROAD FEED joined the ONE graph (cycle
    9): the feed multiplies service centerlines by 10-140x (HECA 5 → 705),
    and every one of them was then a spine for whatever airside pavement it
    passed — an apron chord CROSSING a truck road was dropped as
    "carried by the spine", and the apron's own spine cap could be read off
    a road.  That is a groundside object changing AIRSIDE law, which
    airside-is-king forbids however the roads got there.  MEASURED, arm 1
    of this lane: airside rose at 7 of 8 battery cells, carried by
    ``transverse::apron|apron`` (HECA 10 000 +176) and
    ``transverse::junction|junction`` (+132) — families that only exist
    relative to a spine.
    """
    from .layout import GROUNDSIDE_ROLES
    return shape.role in GROUNDSIDE_ROLES


def _spine_membership(shape: GradeShape, ctx: GradeContext
                      ) -> dict[int, list[tuple[int, float]]]:
    """For each ring index, the list of (centerline-index, arc_pos) it lies on
    (within ``SPINE_PERP_TOL_M``).

    SERVICE centerlines are members only of a groundside-family shape
    (:func:`_reads_service_spines`); indices still index
    ``ctx.centerlines``, so every downstream consumer of this map
    (``_spine_cap``, ``_body_cap``, the crossing predicate) inherits the
    restriction from one place."""
    out: dict[int, list[tuple[int, float]]] = {}
    tree, idxs, _geoms = _polyline_tree(ctx, "cl")
    if tree is None:
        return out
    ring = shape.ring
    if not ring:
        return out
    svc_ok = _reads_service_spines(shape)
    # CANDIDATE QUERY, ONE CALL FOR THE WHOLE RING (perf P3 lane D).  This
    # used to build a 33-vertex ``Point(x, y).buffer(TOL)`` per ring vertex
    # and query the tree with it, one Python-level shapely round trip per
    # vertex.  The tree query is an ENVELOPE test, and the buffer's envelope
    # is exactly ``box(x-TOL, y-TOL, x+TOL, y+TOL)`` — every point within
    # TOL of (x, y) lies in that box — so the box returns the same candidate
    # set (a superset in general, which is equally safe: EVERY candidate is
    # then put through the unchanged exact ``_project`` distance test, and
    # ``hits.sort()`` makes the result order-independent, so extra
    # candidates that fail the test change nothing).  Building the boxes and
    # querying them are both vectorized, so the whole ring costs two calls
    # instead of 2n.
    import numpy as _np
    import shapely as _shapely
    xy = _np.asarray(ring, dtype=float)
    tol = SPINE_PERP_TOL_M
    boxes = _shapely.box(xy[:, 0] - tol, xy[:, 1] - tol,
                         xy[:, 0] + tol, xy[:, 1] + tol)
    q_ri, q_k = tree.query(boxes)
    for ri, k in zip(q_ri.tolist(), q_k.tolist()):
        ci = idxs[k]
        if not svc_ok and ctx.centerlines[ci].is_service:
            continue
        x, y = ring[ri]
        a, d, _ = _project(ctx.centerlines[ci], x, y)
        if d <= SPINE_PERP_TOL_M:
            out.setdefault(ri, []).append((ci, a))
    for hits in out.values():
        hits.sort()
    # Ring-ascending KEY order, as the per-vertex loop produced: downstream
    # (``_build_spine_chains``) iterates this mapping and the chain list it
    # builds inherits its order.
    return {ri: out[ri] for ri in sorted(out)}


# How many chords one vectorised predicate call covers (perf P3 lane D).
# A BUFFER SIZE, not a law value: it changes only how many chords share one
# shapely dispatch and how many geometries exist at once, never a verdict —
# the same predicate runs on the same chords whatever it is set to.
_PRED_BLOCK_CHORDS = 65536


def _predicate_true():
    """Constant thunk for a predicate already decided True (see the
    batched visibility table in :func:`shape_constraints`)."""
    return True


def _predicate_false():
    """Constant thunk for a predicate already decided False."""
    return False


def _crossing_hit_points(inter):
    """The intersection points a crossing verdict is measured at.

    Hoisted UNCHANGED out of ``_spine_crossing_predicate._crosses`` (perf
    P3 lane D): it was a nested generator function, so a fresh function
    object was built on every chord the predicate was asked about."""
    stack = [inter]
    while stack:
        q = stack.pop()
        if q.is_empty:
            continue
        gt = q.geom_type
        if gt == "Point":
            yield (q.x, q.y)
        elif gt in ("LineString", "LinearRing"):
            # collinear overlap: its midpoint stands in for the run
            m = q.interpolate(0.5, normalized=True)
            yield (m.x, m.y)
        elif hasattr(q, "geoms"):
            stack.extend(q.geoms)


# An intersection point within this distance of a chord endpoint is
# CONTACT, not a crossing (see _crosses): far enough from the mm-scale
# solver-frame vs emitted-lat/lon differences that both readers give the
# same verdict, small enough that a genuine crossing a metre into the
# chord still skips it.
_CROSS_ENDPOINT_CLEARANCE_M = 0.5


def _spine_crossing_predicate(shape: GradeShape, ctx: GradeContext,
                              membership: dict):
    """Return ``crosses(xa,ya,xb,yb)->bool``: True iff the chord crosses a
    spine centerline (so the real grade path between the two sides is via the
    spine, not the direct diagonal).  ``None`` if shapely is unavailable or
    the context has no centerlines.

    Tested against ALL context centerlines, not only the shape's MEMBER ones
    (user 2026-07-03): the two law readers carry the same spine geometry
    SPLIT DIFFERENTLY (the solver has whole polylines; the validator's
    sidecar axes are split per segment-cap letter), so membership-gated geoms
    diverged — a chord crossing a non-member PIECE of a line whose other
    piece held the members was skipped by one reader and flagged by the
    other (the SPJC ≥1% residual tail).  The union of all centerlines is
    identical on both sides regardless of splitting, and the rule's physics
    ("the climb between the two sides is carried by the spine") holds for
    any spine the chord crosses, member or not."""
    if not ctx.centerlines:
        return None
    _ = membership          # kept in the signature for call-site stability
    try:
        from shapely.geometry import LineString
    except ImportError:  # pragma: no cover
        return None
    # ALL-centerline geoms + STRtree, built once per CONTEXT (cached): the
    # per-shape member subset used to keep this list short; the full set
    # needs the tree to stay cheap.
    # TWO trees, cached side by side: with the SERVICE centerlines (the
    # groundside family's own law) and without them (everything else — a
    # truck route is not an aircraft spine; see
    # :func:`_reads_service_spines`).  Selected by the shape's role, so an
    # apron chord is never dropped as "carried by the spine" because a road
    # happens to run across it.
    _attr = ("_crossing_tree" if _reads_service_spines(shape)
             else "_crossing_tree_nosvc")
    cached = getattr(ctx, _attr, None)
    if cached is None:
        _svc_ok = _reads_service_spines(shape)
        geoms = []
        for cl in ctx.centerlines:
            if not _svc_ok and cl.is_service:
                continue
            if len(cl.pts) >= 2:
                try:
                    geoms.append(LineString(cl.pts))
                except Exception:
                    pass
        tree = None
        if geoms:
            try:
                from shapely.strtree import STRtree
                tree = STRtree(geoms)
            except Exception:               # pragma: no cover
                tree = None
        cached = (geoms, tree)
        try:
            setattr(ctx, _attr, cached)
        except Exception:                   # pragma: no cover
            pass
    geoms, tree = cached
    if not geoms:
        return None

    def _crosses(xa, ya, xb, yb):
        # ⚠ MEASURED DEAD END (2026-07-03, do not retry as-is): trimming ~1 m
        # off the chord ends (with either ``crosses`` or ``intersects``) to fix
        # the endpoint-contact instability made SPJC WORSE (178→325): the trim
        # flips verdicts for the common chords that START next to a spine cut
        # node, and the two readers' mm-different inputs then diverge on MORE
        # pairs, not fewer.  The real fix is upstream: give both readers
        # IDENTICAL inputs (sidecar carries the solver's exact spine geometry /
        # frame), not a more forgiving predicate.
        try:
            ch = LineString(((xa, ya), (xb, yb)))
        except Exception:
            return False
        # INTERIOR-CLEARANCE crossing (2026-07-03, replaces both the bare
        # ``crosses`` parity AND the short-lived endpoint-on-spine skip):
        # the chord crosses a spine iff SOME intersection point lies at
        # least ``_CROSS_ENDPOINT_CLEARANCE_M`` from BOTH chord endpoints.
        #   * endpoint CONTACT is not a crossing — a chord touching the
        #     spine at its own endpoint (a spine cut/junction node on the
        #     ring) stays IN the law, so side-to-spine and pad-frontage
        #     differentials remain regulated (the blanket endpoint skip
        #     let faces tilt steeply perpendicular to the spine and waived
        #     terminal-frontage chords — user-visible violations at 0
        #     reported).  The verdict is DISTANCE-thresholded, so the two
        #     readers' mm-different frames agree (bare ``crosses`` flipped
        #     on epsilon endpoint contact — the SPJC 122 m pad-chord class).
        #   * ANY hit point counts, including one AT a centerline endpoint
        #     — split-agnostic (``crosses`` needed an interior hit on the
        #     line side too, so a chord passing exactly through a sidecar
        #     split node was invisible to one reader).
        _hit_points = _crossing_hit_points

        def _crosses_one(g, known_intersecting=False):
            if not (known_intersecting or ch.intersects(g)):
                return False
            try:
                inter = ch.intersection(g)
            except Exception:
                return False
            for (px, py) in _hit_points(inter):
                da = math.hypot(px - xa, py - ya)
                db = math.hypot(px - xb, py - yb)
                if min(da, db) > _CROSS_ENDPOINT_CLEARANCE_M:
                    return True
            return False

        if tree is not None:
            try:
                # PREDICATE PUSHED INTO THE QUERY (perf P3 lane D): the tree
                # runs ``intersects`` against each candidate in C and returns
                # only the hits, instead of returning bbox candidates for a
                # Python-level ``ch.intersects(g)`` each.  Same predicate,
                # same pairs — ``query(g, predicate=...)`` is defined as the
                # bbox candidates filtered by exactly that predicate — so
                # this only removes per-candidate dispatch.  The verdict is
                # an OR over the hits, so evaluation order is immaterial.
                for k in tree.query(ch, predicate="intersects"):
                    if _crosses_one(geoms[int(k)], known_intersecting=True):
                        return True
                return False
            except Exception:               # pragma: no cover
                pass
        for g in geoms:
            if _crosses_one(g):
                return True
        return False

    # NOT VECTORISED, AND THAT IS A MEASUREMENT, NOT AN OVERSIGHT (perf P3
    # lane D).  TWO vectorised forms of this predicate were built and
    # measured, both byte-identical to the baseline, both SLOWER:
    #   * a full whole-shape batch (verdict for every pair at once) —
    #     ``shape_constraints`` 83.3 s -> 100.3 s at HECA, 7.4 -> 8.6 s at
    #     CYXY;
    #   * a cheap "does this chord meet ANY spine" prefilter in front of the
    #     per-chord path, leaving the intersection and endpoint-clearance
    #     walk where it was — CYXY 5.6 s -> 6.4 s.
    # The cause is the same for both, and it is the law's own precedence:
    # ``classify_pair`` reaches the crossing rule only AFTER the visibility
    # skip, so anything computed for EVERY pair (which a reader must do — it
    # may not re-spell the law's order to predict which pairs will be asked)
    # pays for pairs the law never asks about, and here that overhead
    # cancels the dispatch it saves.  Visibility, which the law reaches
    # FIRST for nearly every body pair, vectorises profitably and does (see
    # ``_visibility_predicate``).  Do not "finish the job" here without
    # re-measuring both airports.
    return _crosses


# ── caps ────────────────────────────────────────────────────────────────────

def _spine_cap(membership: dict, ctx: GradeContext) -> float:
    """The taxiway cap to use for this shape's spine (max per-letter cap over the
    centerlines crossing it — the steeper code governs the corridor here)."""
    caps = [ctx.centerlines[c].cap
            for hits in membership.values() for (c, _a) in hits]
    return max(caps) if caps else TAXI_MAX_GRADE


def _body_cap(shape: GradeShape, ctx: GradeContext, membership: dict) -> float:
    cap = _body_cap_unbounded(shape, ctx, membership)
    # LATERAL-CONTIGUITY LAW (owner FINAL 2026-08-02, clause 2): the piece's
    # laterally-contiguous cross-section holds a STRICTER class — that cap
    # governs the whole cross-section.  Applied as a MINIMUM (the law only
    # ever tightens; a looser lateral answer never relaxes the shape's own
    # law) and to every role, so the same statement covers a road pulled to
    # an apron's 1 %, a taxiway's 1.5 % or a groundside lot's 4 %.
    lat = getattr(shape, "lateral_cap", None)
    return cap if lat is None else min(cap, float(lat))


def _body_cap_unbounded(shape: GradeShape, ctx: GradeContext,
                        membership: dict) -> float:
    # THE FAN-RAMP LAW (owner RULINGS 21f0980), FIRST because a fan-ramp
    # piece keeps ``role == apron`` — every apron machine still owns it,
    # only its CAP is the zone's.  The piece was cut out of its apron
    # before the solve, so this cap governs its OWN all-pairs: the ramp
    # fanning between two building seat levels is the surface the ONE
    # solve is now free to reach, and no movement surface is inside it
    # (the zone is ``apron − corridor_cover`` by construction).
    if getattr(shape, "fan_ramp_zone", False):
        return FAN_RAMP_CAP
    if shape.role == APRON_ROLE:
        return APRON_MAX_GRADE
    # USER RULING 2026-07-06: a service road / junction sharing an edge
    # with an apron follows the apron grading rules.
    if shape.adopts_apron_grade:
        return APRON_MAX_GRADE
    # USER RULING 2026-07-07: a service road / junction inside or alongside
    # a taxiway follows the taxiway cap (1.5 %, letter-aware).  Apron (1 %)
    # is more limiting, so the apron branch above wins if both are set.
    if getattr(shape, "adopts_taxi_grade", False):
        return float(taxi_grade_cap_for_letter(
            getattr(shape, "adopted_taxi_letter", None)))
    # ``service_road`` reaches here only under SVC_SPINE_FIRST (it joins
    # SOFT_VISIBILITY_ROLES there) — same road cap as service_junction.
    # Without the explicit branch it would fall through to the junction
    # spine/inheritance logic and could inherit a TAXI cap from a welded
    # neighbour, which is not the road's law.
    if shape.role in ("service_junction", "service_road"):
        return SERVICE_ROAD_MAX_GRADE
    # junction: taxiway cap of its spine, else inherited from the nearest
    # connected taxiway-sized shape.
    if membership:
        return _spine_cap(membership, ctx)
    return ctx.inherited_junction_cap(shape)


def _nearest_centerline(x: float, y: float, ctx: GradeContext):
    """``(dist, cap, (tx, ty))`` — the nearest taxi centerline to ``(x, y)``: its
    perpendicular distance, per-letter cap, and unit tangent at the foot point."""
    best_d, best_cap, best_t = float("inf"), APRON_MAX_GRADE, (1.0, 0.0)
    tree, idxs, geoms = _polyline_tree(ctx, "cl")
    if tree is None:
        return best_d, best_cap, best_t
    from shapely.geometry import Point as _Pt
    k = tree.nearest(_Pt(x, y))
    cands = [ctx.centerlines[idxs[int(k)]]] if k is not None else []
    for cl in cands:
        pts = cl.pts
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            if seg2 <= 1e-12:
                continue
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / seg2))
            px, py = ax + t * dx, ay + t * dy
            d = math.hypot(x - px, y - py)
            if d < best_d:
                L = math.sqrt(seg2)
                best_d, best_cap, best_t = d, cl.cap, (dx / L, dy / L)
    return best_d, best_cap, best_t


def _apron_edge_cap(xi, yi, xj, yj, ni, nj, body_cap, twist, boundary=False,
                    contact=False):
    """Apron cap near a taxi route (user 2026-06-25): an apron edge earns the
    route's (looser) cap as it nears the route, decaying to ``body_cap`` past
    ``APRON_TAXI_TRANSITION_M``.  ``ni``/``nj`` = ``_nearest_centerline`` at each
    endpoint.

    ``twist`` (the edge touches a building frontage): the apron WARPS to blend the
    flat pad into the climbing route — its corners slope ± to meet the route — so
    the looser cap applies in ALL directions (isotropic).

    ``boundary`` (user 2026-06-30): a RING-ADJACENT apron edge that runs along a
    taxi route is the apron's CONTACT with the route — it must drop from the apron
    body down to the (lower/higher) route it abuts, so like a frontage warp it
    grades the route cap in its OWN direction (isotropic), not only parallel to the
    centerline.  This is what lets an apron↔taxiway contact ramp exceed the flat
    apron cap instead of being false-flagged as an apron body violation.

    ``contact`` (an endpoint is welded to a taxi-route pavement, via ``route_zone``)
    forces the FULL route cap regardless of centerline distance — the corner of a
    wide junction is metres from its own painted centerline, but it is still the
    apron's contact with that route, so the along-centerline decay must not shrink
    the allowance to nothing there.

    Otherwise only the ALONG-route component earns it (the apron still grades
    ``body_cap`` perpendicular, from its edges to the spine)."""
    d, route_cap, tan = (ni if ni[0] <= nj[0] else nj)
    # The frontage warp needs MORE than the route cap (the route's climb along the
    # pad is compressed into the apron depth), so the twist target is the
    # back-edge ramp grade; elsewhere the apron blends toward the route cap.
    target = max(route_cap, APRON_BACK_EDGE_GRADE) if twist else route_cap
    if target <= body_cap or (d >= APRON_TAXI_TRANSITION_M and not contact):
        return body_cap
    dist_factor = 1.0 if contact else 1.0 - d / APRON_TAXI_TRANSITION_M
    if twist or boundary or contact:
        infl = dist_factor                               # isotropic (warp/contact)
    else:
        ex, ey = xj - xi, yj - yi
        el = math.hypot(ex, ey) or 1e-9
        along = abs(ex * tan[0] + ey * tan[1]) / el      # 0 (perp) .. 1 (along)
        infl = along * dist_factor
    return body_cap + (target - body_cap) * infl


# ── anisotropic edge decomposition (O4_ANISO_EDGES) ──────────────────────────

def _nearest_route(x: float, y: float, ctx: GradeContext):
    """``(route_idx, perp)`` — the nearest chained route to ``(x, y)`` and its
    perpendicular distance.  ``(-1, inf)`` if there are no routes."""
    tree, idxs, geoms = _polyline_tree(ctx, "routes")
    if tree is None:
        return -1, float("inf")
    from shapely.geometry import Point as _Pt
    pt = _Pt(x, y)
    k = tree.nearest(pt)
    if k is None:
        return -1, float("inf")
    k = int(k)
    return idxs[k], geoms[k].distance(pt)


def _edge_route(role, shared, ctx, vr_i, vr_j, di_perp, dj_perp):
    """The route a pair decomposes against (§3c), or ``None`` to stay isotropic.

    * SPINE pair (shares a centerline) → that route (the looser-cap centerline's
      chained route) — the climbing curve earns its full arc as Δs∥.
    * JUNCTION body pair → the NEAREST route, but only when BOTH endpoints share
      the same nearest route (same Voronoi crotch cell); spanning the convergence
      (different nearest routes) stays isotropic / is already skipped.
    * APRON pair → only in the BLEND zone (both endpoints within
      ``APRON_TAXI_TRANSITION_M`` of the one shared route); apron body far from any
      route keeps its isotropic 1 % (no arc credit for a far interior chord)."""
    if shared:
        c_star = max(shared, key=lambda c: ctx.centerlines[c].cap)
        ridx = ctx.centerlines[c_star].route_idx
        if 0 <= ridx < len(ctx.routes):
            return ctx.routes[ridx]
        return ctx.centerlines[c_star]
    ri, rj = vr_i, vr_j
    if ri < 0 or ri != rj:
        return None
    if (role == APRON_ROLE and not SPINE_FRAME_PAIRS
            and (di_perp > APRON_TAXI_TRANSITION_M
                 or dj_perp > APRON_TAXI_TRANSITION_M)):
        # Legacy blend-zone scoping.  Under the SPINE-FRAME law the
        # whole apron decomposes against its route (pure rotation, no
        # arc credit) so the spine can carry its cap through it.
        return None
    return ctx.routes[ri]


class _RouteDistanceOracle:
    """Airside route-graph distance for the far-pair metric (see the
    ``ROUTE_METRIC_PAIRS`` block).  Graph = the NON-SERVICE centerline
    polylines, vertices fused by coordinate bucket so crossing lines join;
    ``distance(a, b) = |a−att(a)| + graph(att(a), att(b)) + |att(b)−b|``
    with straight off-graph legs (a pad deep in an apron reaches its
    serving route across the apron, exactly what the reach band measures).
    Distance fields are memoized per attachment vertex as float arrays and
    evicted FIFO — the bake walks shapes sequentially, so attachments
    cluster and locality is high."""

    _CELL = 50.0
    _MAX_FIELDS = 512

    def __init__(self, centerlines):
        verts: list = []
        vid: dict = {}
        adj: list = []

        def _vert(p):
            k = (round(p[0], 1), round(p[1], 1))
            i = vid.get(k)
            if i is None:
                i = len(verts)
                vid[k] = i
                verts.append((p[0], p[1]))
                adj.append([])
            return i

        for cl in centerlines or ():
            if getattr(cl, "is_service", False):
                continue
            pts = list(cl.pts)
            for a, b in zip(pts, pts[1:]):
                ia, ib = _vert(a), _vert(b)
                if ia == ib:
                    continue
                w = math.hypot(a[0] - b[0], a[1] - b[1])
                adj[ia].append((ib, w))
                adj[ib].append((ia, w))
        self.verts = verts
        self.adj = adj
        self.grid: dict = {}
        for i, (x, y) in enumerate(verts):
            self.grid.setdefault(
                (int(x // self._CELL), int(y // self._CELL)), []).append(i)
        self._fields: dict = {}
        self._field_order: list = []
        self._nearest_memo: dict = {}
        # EXACT ATTACHMENT index (``ROUTE_LEG_EXACT``): the graph's
        # SEGMENTS, bucketed over every cell their bbox touches, so a
        # point can be attached to the nearest POINT ON a centreline
        # instead of the nearest vertex.  Built only under the gate —
        # gate-off construction is untouched.
        self.segs: list = []
        self.seg_grid: dict = {}
        if ROUTE_LEG_EXACT:
            seen_seg: set = set()
            for i, nbrs in enumerate(adj):
                for (j, w) in nbrs:
                    if i >= j or (i, j) in seen_seg:
                        continue
                    seen_seg.add((i, j))
                    self.segs.append((verts[i], verts[j], i, j, w))
            c = self._CELL
            for si, (a, b, _i, _j, _w) in enumerate(self.segs):
                x0, x1 = sorted((a[0], b[0]))
                y0, y1 = sorted((a[1], b[1]))
                for gx in range(int(x0 // c), int(x1 // c) + 1):
                    for gy in range(int(y0 // c), int(y1 // c) + 1):
                        self.seg_grid.setdefault((gx, gy), []).append(si)
        self._attach_memo: dict = {}

    def _attach(self, p):
        """``(off, seg_index, d_to_i, d_to_j)`` — the nearest POINT ON the
        centreline graph: the perpendicular offset to it, the segment it
        lies on, and the along-segment distance from it to each of that
        segment's two graph vertices.  ``None`` when the graph is empty.

        This is what the law means by "off-spine offset" (see the
        ``ROUTE_LEG_EXACT`` block): the distance to the CENTRELINE, not to
        whichever polyline vertex happens to be nearest.  Memoized on the
        centimetre-rounded point exactly as ``_nearest`` is."""
        if not self.segs:
            return None
        key = (round(p[0], 2), round(p[1], 2))
        hit = self._attach_memo.get(key)
        if hit is not None:
            return hit
        c = self._CELL
        cx, cy = int(p[0] // c), int(p[1] // c)
        best = None
        r = 0
        while r < 4096:
            cand = []
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    cand.extend(self.seg_grid.get((cx + dx, cy + dy), ()))
            for si in cand:
                (ax, ay), (bx, by), _i, _j, w = self.segs[si]
                vx, vy = bx - ax, by - ay
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 < 1e-12 else max(0.0, min(
                    1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / l2))
                qx, qy = ax + t * vx, ay + t * vy
                d = math.hypot(p[0] - qx, p[1] - qy)
                if best is None or d < best[0]:
                    best = (d, si, t * w, (1.0 - t) * w)
            # A hit found at ring r can still be beaten from ring r+1
            # onward only while the ring's inner boundary is nearer than
            # the incumbent — the same soundness argument ``_nearest``
            # makes with its "one extra ring", stated as a distance.
            if best is not None and best[0] <= r * c:
                break
            r += 1
        if best is not None:
            self._attach_memo[key] = best
        return best

    def _nearest(self, p):
        if not self.verts:
            return None
        memo_key = (round(p[0], 2), round(p[1], 2))
        cached = self._nearest_memo.get(memo_key)
        if cached is not None:
            return cached
        cx, cy = int(p[0] // self._CELL), int(p[1] // self._CELL)
        best, bd = None, float("inf")
        found_at = None
        # expand square rings until a hit, then one extra ring (a nearer
        # vertex can hide in the next ring at corner geometries).
        for r in range(4096):
            if found_at is not None and r > found_at + 1:
                break
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    for i in self.grid.get((cx + dx, cy + dy), ()):
                        x, y = self.verts[i]
                        d = (x - p[0]) ** 2 + (y - p[1]) ** 2
                        if d < bd:
                            bd = d
                            best = i
            if best is not None and found_at is None:
                found_at = r
        if best is not None:
            self._nearest_memo[memo_key] = best
        return best

    def _field(self, src):
        f = self._fields.get(src)
        if f is None:
            import heapq
            from array import array
            f = array("d", [float("inf")] * len(self.verts))
            f[src] = 0.0
            pq = [(0.0, src)]
            while pq:
                dcur, i = heapq.heappop(pq)
                if dcur > f[i]:
                    continue
                for (j, w) in self.adj[i]:
                    nd = dcur + w
                    if nd < f[j]:
                        f[j] = nd
                        heapq.heappush(pq, (nd, j))
            if len(self._field_order) >= self._MAX_FIELDS:
                old = self._field_order.pop(0)
                self._fields.pop(old, None)
            self._fields[src] = f
            self._field_order.append(src)
        return f

    def legs(self, pa, pb):
        """``(off_a, graph_d, off_b)`` — straight off-graph legs plus the
        route-graph distance between the attachments; ``None`` when no
        graph exists / the attachments are disconnected."""
        if ROUTE_LEG_EXACT and self.segs:
            aa = self._attach(pa)
            ab = self._attach(pb)
            if aa is None or ab is None:
                return None
            off_a, sa, a_i, a_j = aa
            off_b, sb, b_i, b_j = ab
            if sa == sb:
                # SAME SEGMENT: the route between the two attachments IS
                # that segment, so the graph leg is their separation along
                # it — no detour through either endpoint.
                return off_a, abs(a_i - b_i), off_b
            ia, ja = self.segs[sa][2], self.segs[sa][3]
            ib, jb = self.segs[sb][2], self.segs[sb][3]
            best = None
            for (va, da) in ((ia, a_i), (ja, a_j)):
                f = self._field(va)
                for (vb, db) in ((ib, b_i), (jb, b_j)):
                    g = f[vb]
                    if g == float("inf"):
                        continue
                    tot = da + g + db
                    if best is None or tot < best:
                        best = tot
            if best is None:
                return None
            return off_a, best, off_b
        ia = self._nearest(pa)
        ib = self._nearest(pb)
        if ia is None or ib is None:
            return None
        va, vb = self.verts[ia], self.verts[ib]
        off_a = math.hypot(pa[0] - va[0], pa[1] - va[1])
        off_b = math.hypot(pb[0] - vb[0], pb[1] - vb[1])
        g = self._field(ia)[ib]
        if g == float("inf"):
            return None
        return off_a, g, off_b

    def distance(self, pa, pb):
        """Airside route-metric distance, or ``None`` when no graph exists /
        the attachments are disconnected (caller keeps the chord law)."""
        legs = self.legs(pa, pb)
        if legs is None:
            return None
        return legs[0] + legs[1] + legs[2]


def _route_oracle(ctx) -> "_RouteDistanceOracle | None":
    """The context's memoized :class:`_RouteDistanceOracle` (None when the
    airport has no non-service centerlines)."""
    oracle = getattr(ctx, "_route_metric_oracle", "unset")
    if oracle == "unset":
        try:
            oracle = _RouteDistanceOracle(ctx.centerlines)
            if not oracle.verts:
                oracle = None
        except Exception:
            oracle = None
        try:
            ctx._route_metric_oracle = oracle
        except Exception:
            pass
    return oracle


def _route_leg_floor(allow, pa, pb, d, ctx):
    """The SPINE-FRAME model's route-leg budget floor for one pair (owner
    2026-07-29: spine carries the taxi cap, apron grades out at its own
    rate).  ``budget ≥ cT·(off_a + off_b) + taxi_cap·graph_distance`` —
    the pair's lawful rise along the airside travel path: transverse rate
    on the off-spine legs (the deep-set-building 1 % law byte-exact),
    taxi rate along the route graph.  Applied as a FLOOR (max with the
    pair's chord-priced budget — never tightens); cross-cell and
    off-frame pairs, which stay isotropic under the frame decomposition,
    get their route-lawful budget this way, so the short-hop 1 %
    composition across a slice-born mega-apron can no longer form the
    binding path.  Returns ``None`` when the floored budget exceeds
    ``PAIR_BUDGET_PRUNE_M`` (unbindable — pair dropped)."""
    oracle = _route_oracle(ctx)
    if oracle is None:
        return allow
    legs = oracle.legs(pa, pb)
    if legs is None:
        return allow
    off_a, g, off_b = legs
    base = allow.budget if allow.budget is not None else allow.at(d, 0.0)
    floor = allow.cT * (off_a + off_b) + TAXI_MAX_GRADE * g
    budget = max(base, floor)
    if budget > PAIR_BUDGET_PRUNE_M:
        return None
    if budget <= base + 1e-12:
        return allow
    return GL.Allowance.baked(allow.cL, allow.cT, budget)


def _route_metric_far_pair(allow, pa, pb, d, ctx):
    """Re-price a FAR pair (chord ``d`` > ``PAIR_CHORD_LOCAL_M``) on the
    airside route metric: budget = allowance at ``max(chord, d_route)``.
    Returns the (possibly re-baked) allowance, or ``None`` when the priced
    budget exceeds ``PAIR_BUDGET_PRUNE_M`` (unbindable — pair dropped).
    (Superseded by :func:`_route_leg_floor` when the SPINE-FRAME law is
    on; kept as the fallback pricing under ``O4_SPINE_FRAME_PAIRS=0``.)"""
    oracle = _route_oracle(ctx)
    if oracle is None:
        return allow
    dr = oracle.distance(pa, pb)
    if dr is None or dr <= d:
        return allow
    if allow.budget is not None:
        # already-baked (route-arc) budget: scale by the metric inflation.
        budget = allow.budget * (dr / d)
    else:
        budget = allow.at(dr, 0.0)
    if budget > PAIR_BUDGET_PRUNE_M:
        return None
    return GL.Allowance.baked(allow.cL, allow.cT, budget)


def _bake_one_route(allow, pa, pb, shared, ctx, vr, route):
    """Bake one pair's anisotropic budget against ONE route — the
    decomposition body of :func:`_bake_edge`, factored so the R3
    unshared-route path below can price candidate routes with the same
    law.  ``vr`` is the route index used for the spine-frame taxi-cap
    lookup (ignored when ``shared`` is non-empty)."""
    dp, dt = ds_decompose(pa, pb, route)
    cL = allow.cL
    # Transverse cap: A/B taxiways (cL == narrow 3 %) earn the tighter 2 %
    # transverse (ICAO Annex 14 §3.9.11), and SERVICE-ROAD-rate pairs
    # (cL == 5 %) earn the AASHTO 2 % normal-crown transverse (user crown
    # ruling 2026-07-07 — laterally a road may not tilt at its
    # longitudinal cap: 25 cm across a 5 m road was the visible
    # ridge/valley budget).  Every other cap (C–F 1.5 %, apron 1 %,
    # apron-blend gradients) stays isotropic cT == cL.
    # (cT resolves from the PAIR's own cap BEFORE the spine-frame
    # upgrade below — "aprons grade out from the spines" at their own
    # transverse rate.)
    # ONE LAW SOURCE (2026-08-08): the three branches are
    # ``config.transverse_cap_for_longitudinal_cap``; this reader, the
    # emitter's cross-section pair budget and
    # ``check_grade._transverse_cap_for_seg_cap`` all delegate to it.
    cT = _transverse_cap_for_longitudinal_cap(cL)
    if SPINE_FRAME_PAIRS:
        # SPINE-FRAME upgrade (owner model 2026-07-29): the route's
        # per-letter TAXI cap carries longitudinally through the shape
        # it threads — never a service road's rate (free-road ruling).
        rcap = _route_taxi_cap(shared, vr, ctx)
        if rcap is not None and rcap > cL:
            cL = rcap
    return GL.Allowance.baked(
        cL, cT, math.hypot(cL * dp, cT * dt))


def _bake_edge(allow, role, pa, pb, shared, ctx, vr_i, vr_j):
    """Replace a live ``Allowance`` with its route-decomposed BAKED budget (when
    the pair has a route, §3c); otherwise return it unchanged (isotropic).

    The budget is the anisotropic ``√((cL·Δs∥)² + (cT·Δs⊥)²)`` against the
    pair's route — the max |Δz| in an oblique direction on a surface with
    principal gradient limits ``cL`` along the route and ``cT`` across it.
    (Two former inflations, both measured wrong 2026-07-03: Δs∥ used to be
    the along-route ARC — near curves physically-close pairs earned budgets
    far beyond any surface cap — and the L1 sum ``cL·Δs∥ + cT·Δs⊥``
    over-allowed diagonals by up to √2.)

    R3 (service-road law spec, 2026-08-15) — TRANSVERSE CAP WITHOUT A
    SHARED ROUTE: a SERVICE-family pair whose endpoints find no shared
    nearest route (:func:`_edge_route` → ``None``) used to stay isotropic
    at the 8 % road cap — the 2 % transverse cap never applied (measured
    at HECA: 2,151 of 15,892 ring-adjacent service pairs, 13.5 %).  Such
    a pair now bakes against the nearest route of EITHER endpoint
    (endpoints within ``SERVICE_SPINE_PERP_TOL_M`` of their route — the
    module's own service node-on-spine tolerance, no new number), and
    the TIGHTEST resulting budget wins.  A pair genuinely off-network
    (neither endpoint within the tolerance of any route) stays isotropic
    as before.  Migrated pairs are counted on
    ``ctx._svc_pair_route_migrated`` and reported by
    :func:`build_unified_graph`."""
    route = _edge_route(role, shared, ctx, vr_i[0], vr_j[0], vr_i[1], vr_j[1])
    if route is not None:
        return _bake_one_route(allow, pa, pb, shared, ctx, vr_i[0], route)
    if role not in SERVICE_AXIS_PRICED_ROLES:
        return allow
    cand: list = []
    for (ridx, perp) in (vr_i, vr_j):
        if (ridx is not None and 0 <= ridx < len(ctx.routes)
                and perp <= SERVICE_SPINE_PERP_TOL_M
                and all(ridx != c0 for (c0, _r) in cand)):
            cand.append((ridx, ctx.routes[ridx]))
    if not cand:
        return allow            # genuinely off-network — isotropic, as today
    best = None
    for (ridx, r) in cand:
        baked = _bake_one_route(allow, pa, pb, shared, ctx, ridx, r)
        if best is None or baked.budget < best.budget:
            best = baked
    try:
        ctx._svc_pair_route_migrated = getattr(
            ctx, "_svc_pair_route_migrated", 0) + 1
    except Exception:                                    # pragma: no cover
        pass
    return best


def _route_taxi_cap(shared, vr, ctx):
    """The per-letter taxi cap of the route a pair decomposes against, or
    ``None`` when the route is service-only (its cap must not carry)."""
    if shared:
        c_star = max(shared, key=lambda c: ctx.centerlines[c].cap)
        cl = ctx.centerlines[c_star]
        return None if getattr(cl, "is_service", False) else cl.cap
    if vr is None or vr < 0:
        return None
    memo = getattr(ctx, "_route_taxi_cap_memo", None)
    if memo is None:
        memo = {}
        try:
            ctx._route_taxi_cap_memo = memo
        except Exception:
            pass
    cap = memo.get(vr, "unset")
    if cap == "unset":
        caps = [cl.cap for cl in ctx.centerlines
                if cl.route_idx == vr and not getattr(cl, "is_service",
                                                     False)]
        cap = max(caps) if caps else None
        memo[vr] = cap
    return cap


# ── junction mesh edges (O4_JUNCTION_MESH_CONSTRAINTS) ───────────────────────

def mesh_edge_keys(ring: Sequence[tuple[float, float]],
                   keys: Sequence[Hashable]) -> set:
    """The triangle-mesh EDGE set of a shape, as ``frozenset({key_a, key_b})``
    pairs — the edges a constrained-Delaunay triangulation of the ring facets
    (what X-Plane's mesh approximates).  Includes the perimeter (ring-adjacent)
    edges and the interior/cross-slope edges; excludes long chords across the
    shape.  A junction's real grade paths are these edges plus its spine; the
    remaining ``O(n²)`` chords are phantom (see ``config.JUNCTION_MESH_CONSTRAINTS``).

    SINGLE SOURCE both the solver (``shape_constraints``) and the validator use,
    so they cannot drift.  Deterministic (GEOS Delaunay is order-stable).  Falls
    back to ring-adjacent-only if the polygon is degenerate / triangulation fails
    (never raises — a bad triangulation must not abort a build)."""
    from shapely.geometry import Polygon as _Poly
    n = len(ring)
    # ring-adjacent perimeter edges are always mesh edges (the polygon boundary).
    out = {frozenset((keys[i], keys[(i + 1) % n])) for i in range(n)}
    if n < 4:
        return out
    idx = {(round(x, 3), round(y, 3)): keys[i] for i, (x, y) in enumerate(ring)}
    try:
        poly = _Poly(ring)
        if (not poly.is_valid) or poly.is_empty or poly.area <= 0.0:
            return out
        from shapely.ops import triangulate as _tri
        for t in _tri(poly):
            # keep only triangles inside the (possibly concave) polygon.
            if not poly.contains(t.centroid):
                continue
            corners = list(t.exterior.coords)[:-1]
            tk = [idx.get((round(x, 3), round(y, 3))) for (x, y) in corners]
            for a in range(3):
                u, v = tk[a], tk[(a + 1) % 3]
                if u is not None and v is not None and u != v:
                    out.add(frozenset((u, v)))
    except _GEOM_EXC:
        return out
    return out


class MeshEdgesExact:
    """The SOLVER's junction triangle-mesh edge set (sidecar ``mesh_edges``),
    indexed so an emitted-OSM reader can consume the solver's mesh 1:1 instead
    of re-triangulating the EMITTED ring.

    Why: ``layout.to_osm`` repairs rings at emit (buffer(0), needle-vertex
    removal, ~0.5 m canonical-point interning), so the emitted junction ring
    can differ from the ring the solver triangulated — GEOS Delaunay then
    facets it DIFFERENTLY, and the validator checks mesh chords the solver
    never constrained (SPJC 2026-07-05: 44 genuine mesh/ring pairs a median
    1.8 cm over allowance).  With this structure the validator asks "was this
    pair a SOLVER mesh edge" by matching each emitted ring vertex to the
    nearest exported mesh vertex within ``SHARED_VERTEX_TOL_M`` (the one
    canonical node identity, 2026-06-30).

    An emitted vertex with NO solver counterpart within tolerance (e.g. a
    buffer(0) self-touch vertex minted at emit) matches nothing, so its body
    chords skip as phantom — the solver never constrained them, and checking
    them against a mesh the solver never built is exactly the noise class this
    removes.  Ring-adjacent pairs are unaffected (the law never consults the
    mesh for them).

    Vertex identity is the exact meter-coordinate tuple: both endpoints of a
    shared solver vertex serialize to the same rounded lat/lon, so they
    convert to bit-identical meters."""

    def __init__(self, edge_endpoints_m):
        from .layout import SHARED_VERTEX_TOL_M
        self._match_tolerance_m = float(SHARED_VERTEX_TOL_M)
        self._vertex_ordinal: dict = {}      # exact (x, y) → ordinal
        self._grid_cells: dict = {}          # grid cell → [(x, y, ordinal)]
        self.edge_pairs: set = set()         # frozenset({ordinal_a, ordinal_b})
        for (point_a, point_b) in edge_endpoints_m:
            ordinal_a = self._intern(point_a)
            ordinal_b = self._intern(point_b)
            if ordinal_a != ordinal_b:
                self.edge_pairs.add(frozenset((ordinal_a, ordinal_b)))

    def _intern(self, point) -> int:
        key = (float(point[0]), float(point[1]))
        ordinal = self._vertex_ordinal.get(key)
        if ordinal is None:
            ordinal = len(self._vertex_ordinal)
            self._vertex_ordinal[key] = ordinal
            cell = (int(math.floor(key[0] / self._match_tolerance_m)),
                    int(math.floor(key[1] / self._match_tolerance_m)))
            self._grid_cells.setdefault(cell, []).append(
                (key[0], key[1], ordinal))
        return ordinal

    def _nearest_vertex(self, x: float, y: float):
        """Nearest exported mesh vertex within the match tolerance, or None.
        Deterministic: ties break to the lowest ordinal."""
        cell_x = int(math.floor(x / self._match_tolerance_m))
        cell_y = int(math.floor(y / self._match_tolerance_m))
        best_ordinal = None
        best_distance = self._match_tolerance_m
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (vx, vy, ordinal) in self._grid_cells.get(
                        (cell_x + dx, cell_y + dy), ()):
                    distance = math.hypot(x - vx, y - vy)
                    if (distance < best_distance
                            or (distance == best_distance
                                and best_ordinal is not None
                                and ordinal < best_ordinal)):
                        best_distance = distance
                        best_ordinal = ordinal
        return best_ordinal

    def mesh_keys_for_ring(self, ring, keys) -> set:
        """The solver-mesh membership set for one emitted ring, in the ring's
        own key space — same contract as :func:`mesh_edge_keys`."""
        matched = [self._nearest_vertex(x, y) for (x, y) in ring]
        out: set = set()
        n = len(ring)
        for i in range(n):
            ordinal_i = matched[i]
            if ordinal_i is None:
                continue
            for j in range(i + 1, n):
                ordinal_j = matched[j]
                if ordinal_j is None or ordinal_j == ordinal_i:
                    continue
                if frozenset((ordinal_i, ordinal_j)) in self.edge_pairs:
                    out.add(frozenset((keys[i], keys[j])))
        return out


# ── main ────────────────────────────────────────────────────────────────────

def shape_constraints(shape: GradeShape, ctx: GradeContext,
                      ring_only: bool = False) -> ShapeConstraints:
    """The grade constraints of ONE soft airside shape (apron / junction).

    ``ring_only`` (user 2026-07-05 flatness tier): generate ONLY the
    ring-adjacent pairs — the O(n) physical boundary edges — through the SAME
    ``classify_pair`` path, so ring budgets are identical to the full run's.
    Used exclusively by ``solver_primitives._build_shape_constraints`` for
    shapes holding a flatness certificate (their O(n²) body pairs are
    satisfied at the DEM seed and are generated lazily the first time any of
    the shape's nodes moves off it — see ``one_solve.feasibility_project``).
    The mesh / visibility / spine-crossing predicates only ever gate
    NON-ring pairs (``grade_law.classify_pair`` never consults them for a
    ring-adjacent pair), so skipping their setup here cannot change a ring
    budget."""
    sc = ShapeConstraints(role=shape.role)
    ring = shape.ring
    keys = shape.keys
    n = len(ring)
    if n < 3:
        return sc
    membership = _spine_membership(shape, ctx)
    body_cap = _body_cap(shape, ctx, membership)
    # ── THE APRON MOVEMENT-SURFACE POPULATION (RULINGS 2026-08-21b) ──────
    # Per-vertex frontage / corridor membership, computed ONCE per shape and
    # handed to THE LAW (``grade_law.classify_pair``) as ``a_frontage`` /
    # ``a_corridor``; the PREDICATE lives only there.  Both readers reach
    # this one function, so census and bake cannot enumerate different apron
    # pair sets.
    # AMENDED BY RULINGS 2026-08-21c / spec A1: the membership is now what
    # tells a STRICT movement surface from a 5 %-capped INTERIOR pair, not
    # what tells law from not-law.  The frontage-less early return that used
    # to live here is GONE with the skip it served: a zero-building apron
    # still yields a full interior pair set, now at ``APRON_INTERIOR_CAP``.
    apron_pop = (GL.APRON_INTERIOR_RAMP_CAP
                 and shape.role == APRON_ROLE)
    front_vert = None
    cover_vert = None
    # ── AMENDMENT A4: the nearest-spine chord set and the strip exclusion,
    # both computed ONCE per shape and handed to the law as per-pair facts.
    # ``near_spine`` is now ``{pair: anchor kind}`` — THE ONE nearest-ANCHOR
    # enumeration (owner ruling RULINGS 2026-08-25, spec §1.5).  Membership
    # is still the strict-population flag (both kinds are strict); the KIND
    # selects the cap class in ``grade_law.apron_pair_class``.
    near_spine = {}
    strip_vert = None
    # ONE VISIBILITY THUNK for this ring, built once and used by BOTH the
    # A5 chord selection and the pair loop's own visibility gate — the same
    # predicate, so "can this vertex reach that one" has one answer here.
    vis = None if ring_only else _visibility_predicate(ring)
    # ── THE BACK-EDGE ZONES (RULINGS 2026-08-24): per-vertex zone index,
    # computed ONCE per shape.  Only the 5 % class needs it, so it is
    # built only for aprons and only when the context carries zones.
    zone_vert = None
    if shape.role == APRON_ROLE:
        strip_vert = strip_excluded_flags(ring, ctx)
        # A4.2's excluded nodes, published for the seniority partition:
        # the law SKIPS their pairs, so nothing downstream would ever see
        # them if they were not recorded at the flag.
        if any(strip_vert):
            sc.strip_excluded.update(
                k for k, f in zip(keys, strip_vert) if f)
        near_spine = nearest_spine_pairs(ring, keys, ctx, vis=vis)
        if ctx.interior_zones:
            zone_vert = interior_zone_flags(ring, ctx)
            if not any(z >= 0 for z in zone_vert):
                zone_vert = None
    if apron_pop:
        front_vert = ([k in ctx.frontage_keys for k in keys]
                      if ctx.frontage_keys else [False] * n)
        # The cover is needed EVEN WITH NO FRONTAGE VERTEX (spec AMENDMENT
        # A2): a ring edge inside the spine corridor cover at both ends is a
        # CORRIDOR-CROSSING edge and keeps the strict cap, whether or not
        # anything on this ring fronts a building.  (The A1-era short-circuit
        # that skipped the containment test on frontage-less rings was
        # correct only while ring edges were unconditionally strict.)
        cover = corridor_cover_prepared(ctx)
        if cover is not None:
            from shapely.geometry import Point as _CoPt
            cover_vert = [cover.intersects(_CoPt(x, y)) for (x, y) in ring]
    # ── NO PLATEAUS (owner ruling RULINGS 2026-08-24b) ───────────────────
    # IS THIS APRON JOINED TO THE CORRIDOR NETWORK?  A SHAPE-level fact, and
    # the ruling's reason is shape-level: "an apron spanning between two
    # lawful 1.5 % taxiways lawfully runs ~1.5 % itself".
    #
    # TWO EXISTING NOTIONS, BOTH ALREADY COMPUTED FOR THIS SHAPE — no new
    # geometry, no new radius, nothing that can drift from the cover the
    # frontage chords and the back-edge zones are cut against:
    #   * ``membership``  — a ring vertex lies ON a spine centerline
    #     (``_spine_membership``, the engine's own ``SPINE_PERP_TOL_M``
    #     notion).  This is the load-bearing half, and it works on a WIDE
    #     apron that a taxiway crosses through the middle BECAUSE THE
    #     ENGINE WELDS route geometry into the apron ring pre-emit — the
    #     same fact ``nearest_spine_pairs`` is built on.  ``near_spine`` is
    #     therefore not asked here: it is strictly narrower than
    #     ``membership`` (same on-the-spine test, plus visibility and
    #     reach), so it would add nothing.
    #   * ``cover_vert``  — a ring vertex lies inside the corridor cover;
    #     the apron abuts a corridor it has no welded vertex on.
    corridor_connected = (bool(membership)
                          or bool(cover_vert and any(cover_vert)))
    # JUNCTION MESH CONSTRAINTS (O4_JUNCTION_MESH_CONSTRAINTS): the RULE — a
    # junction's only real grade paths are the spine + the triangle-mesh edges,
    # the remaining body chords are phantom — lives in ``grade_law.classify_pair``
    # (the JUNCTION MESH RULE skip).  This reader only computes the mesh-edge key
    # set and supplies the per-pair lazy membership thunk (``mesh_member_fn``),
    # mirroring the visibility / spine-crossing predicates.  APRONS keep their
    # full visibility graph (the geodesic flatness model catches aggregate slope a
    # mesh edge misses), so this is junction/service_junction only.
    # ``ctx.mesh_edges_exact`` (exact-mesh sidecar) supplies the SOLVER's mesh
    # 1:1; without it the reader triangulates its own ring (the solver path).
    mesh_keys = None
    if (JUNCTION_MESH_CONSTRAINTS and not ring_only
            and shape.role in JUNCTION_ROLES):
        mesh_keys = (ctx.mesh_edges_exact.mesh_keys_for_ring(ring, keys)
                     if ctx.mesh_edges_exact is not None
                     else mesh_edge_keys(ring, keys))
    # The shape's spine centerline geometries (those it has nodes on) — a body
    # chord that CROSSES one is NOT a real grade path: the climb between the two
    # sides is carried by the SPINE at the taxiway cap (the apron grades 1% to
    # its local spine, plan §2), so the straight 1%-diagonal across the spine
    # would falsely declare a wide apron infeasible.  Drop it; the constraint
    # holds transitively through the spine.
    crosses_spine = (None if ring_only
                     else _spine_crossing_predicate(shape, ctx, membership))
    seam = ctx.seam_keys
    bld = ctx.building_keys

    # APRON↔taxi blend: per-ring-node nearest centerline (dist, cap, tangent), so
    # an apron body edge's ALONG-route component earns the route's looser cap as
    # it nears a taxiway running through the apron (user 2026-06-25).
    near = None
    if (APRON_TAXI_BLEND and shape.role == APRON_ROLE
            and ctx.centerlines and body_cap < TAXI_MAX_GRADE):
        # SERVICE roads never blend an apron: a truck route's road cap
        # belongs to its own strip faces, not to the apron around it
        # (service lines entered ctx.centerlines as road-cap spines with
        # the global slice, 2026-07-02).
        from .config import SERVICE_ROAD_MAX_GRADE as _SVC_CAP_BL
        _blend_ctx = ctx
        if any(c.cap >= _SVC_CAP_BL - 1e-9 for c in ctx.centerlines):
            import copy as _copy
            _blend_ctx = _copy.copy(ctx)
            _blend_ctx.centerlines = [
                c for c in ctx.centerlines if c.cap < _SVC_CAP_BL - 1e-9]
        near = [_nearest_centerline(x, y, _blend_ctx) for (x, y) in ring]

    # ── THE ROAD CROSS-SECTION (owner ruling RULINGS 2026-08-25g) ────────
    # THIS RING'S OWN AXIS, computed ONCE per shape (O(n) over the ring
    # edges) and handed to THE LAW as a per-pair fact, exactly like the
    # frontage / strip / zone memberships above.  The verdict is the
    # law's (``grade_law.pair_is_transverse``); the axis is the reader's,
    # and it is THE axis — ``grade_law.long_axis_of_points`` is the same
    # function the lateral-contiguity station walk reads a road's
    # direction with, so the law cannot price a cross-section the walk
    # would call longitudinal.
    #
    # Scoped to the ROAD FAMILY: the ruling names the road, and a taxiway
    # or apron ring's long axis is not a cross-section notion (their
    # transverse law is the ROUTE-frame one ``_bake_one_route`` already
    # applies).  Gate off ⇒ ``None`` ⇒ every pair keeps its longitudinal
    # cap, byte-identical to the pre-ruling build.
    road_axis = None
    if GL.ROAD_CROSS_SECTION_LAW and shape.role in GL.ROAD_ROLES:
        _ax = GL.long_axis_of_points(ring)
        road_axis = _ax[0] if _ax else None
    # Per-vertex service-road-carve membership (O(n) once; the pair rule is then
    # ``both endpoints on a carve`` → road cap, via grade_law.classify_pair).
    road_vert = None
    if ctx.road_zone is not None:
        from shapely.geometry import Point as _RPt
        road_vert = [ctx.road_zone.contains(_RPt(x, y)) for (x, y) in ring]

    # Per-vertex taxi-route-pavement contact (apron only): a ring node welded to a
    # junction/parallel/stub pavement makes its ring edges contact ramps → taxi cap.
    route_vert = None
    if ctx.route_zone is not None and shape.role == APRON_ROLE and near is not None:
        from shapely.geometry import Point as _RPt2
        route_vert = [ctx.route_zone.contains(_RPt2(x, y)) for (x, y) in ring]

    # ANISOTROPIC EDGES (O4_ANISO_EDGES): per-vertex nearest chained route, so a
    # surviving spine / junction-body / apron-blend pair can be decomposed against
    # its route (Δs∥ = spine arc) and its budget BAKED into the Allowance.  Off ⇒
    # ``vert_route`` is None and every edge stays the legacy isotropic cap·dist.
    aniso = ANISO_EDGES and bool(ctx.routes)
    vert_route = ([_nearest_route(x, y, ctx) for (x, y) in ring]
                  if aniso else None)

    # Build the representation-agnostic PairContext for each pair and apply THE
    # LAW (``grade_law.classify_pair``).  The expensive visibility / spine-cross
    # predicates and the apron blend cap are passed as thunks so the law evaluates
    # them lazily (only for pairs surviving the cheap skips) — the same
    # short-circuiting the legacy in-line loop had.  ``classify_pair`` returns an
    # ``Allowance``; every current rule is isotropic, so ``flat_cap()`` recovers
    # the legacy scalar ``(key_a, key_b, cap)`` edge exactly.  The per-edge spine
    # cap (a taxi route keeps its own per-letter cap inside a junction) and the
    # per-letter blend are encoded as the ``spine_caps`` / ``blend_cap_fn`` inputs.
    # ── BATCHED VISIBILITY (perf P3 lane D) ───────────────────────────────
    # ``vis`` is a pure predicate of the CHORD.  Asked one chord at a time
    # it pays shapely's Python-level dispatch per pair — measured at HECA,
    # 27.0 s inside this function.  Asked in BLOCKS it pays it once per
    # block (measured 10.4 s), and the verdicts are identical: the same
    # prepared GEOS predicate on the same chord coordinates (see
    # ``_visibility_predicate``'s batch comment).
    #
    # The table covers a SUPERSET of the pairs the law asks about, because
    # the law short-circuits on its cheap skips first.  That is sound and
    # not merely convenient: the predicate is pure and side-effect free, so
    # a verdict computed for a pair the law never consults is discarded, and
    # a discarded verdict cannot change an outcome.  (It is also what makes
    # the CROSSING predicate a bad batch candidate — see
    # ``_spine_crossing_predicate``, where the same superset was measured
    # and rejected.)
    #
    # The law's own call sequence is untouched: it still receives a thunk
    # and still decides WHEN to consult it — the thunk just answers from the
    # table instead of calling into shapely.  Any failure in the batch (a
    # degenerate chord, an older shapely) drops the whole shape back to the
    # original per-pair thunk, which is still here.
    #
    # Blocks are sized in CHORDS, not shapes: batching a whole small ring at
    # once is what makes the amortisation work there (measured: per-ROW
    # batching was a LOSS at CYXY, whose rings are short — the vectorised
    # call's own setup outweighed the handful of chords in a row), while the
    # cap keeps a large ring's peak geometry count bounded.  Pairs are
    # generated in the loop's own order, so the k-th table entry is the
    # k-th pair the loop visits.
    vis_all = None
    if not ring_only and vis is not None:
        try:
            import numpy as _np
            import shapely as _shapely
            xy = _np.asarray(ring, dtype=float)
            iu, ju = _np.triu_indices(n, 1)      # row-major = loop order
            n_pairs = len(iu)
            vis_all = _np.zeros(n_pairs, dtype=bool)
            for start in range(0, n_pairs, _PRED_BLOCK_CHORDS):
                stop = min(start + _PRED_BLOCK_CHORDS, n_pairs)
                m = stop - start
                pts = _np.empty((2 * m, 2), dtype=float)
                pts[0::2] = xy[iu[start:stop]]
                pts[1::2] = xy[ju[start:stop]]
                chords = _shapely.linestrings(
                    pts, indices=_np.repeat(_np.arange(m), 2))
                vis_all[start:stop] = vis.batch(chords)
        except Exception:                   # pragma: no cover
            vis_all = None

    # Per-vertex spine-centerline sets, built ONCE (perf P3 lane D).  The
    # pair loop used to rebuild BOTH endpoints' sets inside the O(n²) body,
    # so a vertex on a spine had its set rebuilt n times.  Same sets, same
    # intersection.
    mem_sets = {ri: {c for (c, _a) in hits}
                for ri, hits in membership.items()}

    pair_ord = -1
    for i in range(n):
        xi, yi = ring[i]
        ki = keys[i]
        mi = membership.get(i)
        mset_i = mem_sets.get(i)
        ki_bld = ki in bld
        ki_front = bool(front_vert) and front_vert[i]
        ki_cover = bool(cover_vert) and cover_vert[i]
        for j in range(i + 1, n):
            pair_ord += 1
            ring_adjacent = (j == i + 1) or (i == 0 and j == n - 1)
            if ring_only and not ring_adjacent:
                continue
            kj = keys[j]
            if ki == kj:
                continue
            xj, yj = ring[j]
            d = math.hypot(xi - xj, yi - yj)
            mj = membership.get(j)
            shared = ((mset_i & mem_sets[j])
                      if (mi is not None and mj is not None) else set())
            spine_caps = tuple(ctx.centerlines[c].cap for c in shared)
            kj_bld = kj in bld

            # Junction mesh membership thunk for THE LAW's JUNCTION MESH RULE
            # (``grade_law.classify_pair`` skips a non-spine, non-ring,
            # non-mesh junction body chord as a phantom).  Supplied only where
            # the rule can apply, like ``crosses_fn`` below.
            mesh_fn = None
            if mesh_keys is not None and not spine_caps and not ring_adjacent:
                mesh_fn = (lambda _k=frozenset((ki, kj)), _m=mesh_keys:
                           _k in _m)

            if vis is None:
                visible_fn = None
            elif vis_all is not None:
                visible_fn = (_predicate_true if vis_all[pair_ord]
                              else _predicate_false)
            else:
                visible_fn = (lambda _a=xi, _b=yi, _c=xj, _d=yj:
                              vis(_a, _b, _c, _d))
            crosses_fn = None
            if (crosses_spine is not None and not spine_caps
                    and not ring_adjacent):
                crosses_fn = (lambda _a=xi, _b=yi, _c=xj, _d=yj:
                              crosses_spine(_a, _b, _c, _d))
            blend_fn = None
            if near is not None:
                _ct = bool(route_vert and ring_adjacent
                           and (route_vert[i] or route_vert[j]))
                blend_fn = (lambda _a=xi, _b=yi, _c=xj, _d=yj, _ni=near[i],
                            _nj=near[j], _kb=(ki_bld or kj_bld),
                            _ra=(ring_adjacent and APRON_ROUTE_CONTACT), _cn=_ct:
                            _apron_edge_cap(_a, _b, _c, _d, _ni, _nj,
                                            body_cap, _kb, boundary=_ra, contact=_cn))

            both_road = bool(road_vert and road_vert[i] and road_vert[j])
            # THE ONE nearest-ANCHOR enumeration's verdict for this pair:
            # ``None`` (not a chord), ``ANCHOR_KIND_SPINE`` or
            # ``ANCHOR_KIND_PAD`` (RULINGS 2026-08-25).
            _anchor_kind = near_spine.get(
                (ki, kj) if str(ki) <= str(kj) else (kj, ki))
            _pc = GL.PairContext(
                role=shape.role, dist=d, ring_adjacent=ring_adjacent,
                a_seam=ki in seam, b_seam=kj in seam,
                a_building=ki_bld, b_building=kj_bld,
                spine_caps=spine_caps, body_cap=body_cap,
                visible_fn=visible_fn, crosses_spine_fn=crosses_fn,
                mesh_member_fn=mesh_fn,
                blend_cap_fn=blend_fn, both_road=both_road,
                a_frontage=ki_front,
                b_frontage=bool(front_vert) and front_vert[j],
                a_corridor=ki_cover,
                b_corridor=bool(cover_vert) and cover_vert[j],
                nearest_spine=_anchor_kind is not None,
                # THE TARGET KIND (RULINGS 2026-08-25): a chord whose
                # nearest visible anchor is a PAD prices in the STAND
                # class; a chord to a CENTERLINE keeps today's assignment.
                nearest_anchor_pad=(_anchor_kind == ANCHOR_KIND_PAD),
                a_in_strip=bool(strip_vert) and strip_vert[i],
                b_in_strip=bool(strip_vert) and strip_vert[j],
                # THE BACK-EDGE PREDICATE (RULINGS 2026-08-24).  Both
                # endpoints in the SAME zone is the cheap half and is
                # tested FIRST, so the chord containment (a shapely
                # ``covers``) is only ever paid by the handful of pairs
                # that could pass it — ``FanRampPlan.pair_cap``'s own
                # ordering, for its own reason.
                in_interior_zone=(
                    zone_vert is not None
                    and zone_vert[i] >= 0
                    and zone_vert[i] == zone_vert[j]
                    and interior_zone_pair(ctx, zone_vert[i], zone_vert[j],
                                           xi, yi, xj, yj)),
                corridor_connected=corridor_connected,
                # THE ROAD CROSS-SECTION (RULINGS 2026-08-25g).
                transverse_road=(
                    road_axis is not None
                    and GL.pair_is_transverse(road_axis,
                                              xj - xi, yj - yi)))
            allow = GL.classify_pair(_pc)
            if allow is None:
                continue
            # THE SAME PairContext answers the seniority question, so the
            # staged solve's partition is the law's own verdict and cannot
            # drift from the cap it just returned (spec §3, ONE predicate).
            _is_interior = GL.is_apron_interior(_pc)
            # NEVER bake a route-arc budget into a BUILDING-endpoint pair
            # (user 2026-07-03, extending the 2026-07-02 ruling that already
            # excludes building pairs from the blend and the road carve:
            # buildings are the HEAVIEST constraint).  The arc credit
            # (Δs∥ = route arc ≫ chord) legalised pad-frontage chords at
            # 2-3× the flat 1 %·d — the SPJC residual-178 class: the solver
            # graph was satisfied at the baked budgets while the validator's
            # flat reading (correctly) flagged the same chords.
            # A CROSS-SECTION IS NOT A TRAVEL PATH (RULINGS 2026-08-25g).
            # Every pricing below this line converts a pair's budget from
            # its chord to a ROUTE measure: the anisotropic bake spends
            # the along-route component at ``cL``, and the route-leg /
            # route-metric floors spend the airside TRAVEL distance
            # between the endpoints, which on a road cross-section is the
            # whole way round the block.  Applied to the pair that runs
            # ACROSS a road, each of them re-opens exactly the budget the
            # ruling closes.  The law already priced this pair at the
            # cross-section cap; it exits the chain holding it.
            #
            # This is a TIGHTENING and only that: the bake's own verdict
            # for a transverse pair is ``hypot(cL·Δs∥, cT·Δs⊥)`` with
            # Δs∥ ≈ 0, i.e. ≈ ``cT·d`` — the same number the flat
            # allowance carries — so on the pairs that HAD a route
            # nothing measurable changes, and the pairs that had none
            # (``_bake_edge``'s off-network branch, isotropic at the 8 %
            # road cap) are the population the ruling is about.
            _road_xsec = _pc.transverse_road
            if (vert_route is not None and not (ki_bld or kj_bld)
                    and not _road_xsec):
                allow = _bake_edge(allow, shape.role, (xi, yi), (xj, yj),
                                   shared, ctx, vert_route[i], vert_route[j])
            # ROUTE-LEG FLOOR / ROUTE-METRIC FAR PAIRS (owner rulings
            # 2026-07-29): price interior pairs by the airside travel
            # path, not the chord.  Building-endpoint pairs keep the
            # chord law (2026-07-03: buildings are the heaviest
            # constraint); ring-adjacent pairs are the surface
            # smoothness law and stay tight.
            if (SPINE_FRAME_PAIRS
                    and not ring_adjacent and not (ki_bld or kj_bld)
                    and not _road_xsec
                    # CHORD GATE (``ROUTE_LEG_EXACT``, owner field report
                    # 2026-08-02): a LOCAL pair is priced on its chord,
                    # exactly as ``_route_metric_far_pair`` still is and as
                    # the ROUTE-METRIC block comment above already states.
                    # The pavement between two nearby points is continuous
                    # (``ds_decompose``), so the surface gradient between
                    # them is what the standards regulate — a route-travel
                    # budget over a 38 m chord is not a grade law.
                    and (not ROUTE_LEG_EXACT or d > PAIR_CHORD_LOCAL_M)):
                allow = _route_leg_floor(
                    allow, (xi, yi), (xj, yj), d, ctx)
                if allow is None:
                    continue
            elif (ROUTE_METRIC_PAIRS and d > PAIR_CHORD_LOCAL_M
                    and not ring_adjacent and not (ki_bld or kj_bld)
                    and not _road_xsec):
                allow = _route_metric_far_pair(
                    allow, (xi, yi), (xj, yj), d, ctx)
                if allow is None:
                    continue
            sc.edges.append((ki, kj, allow))
            sc.edge_interior.append(_is_interior)
            sc.edge_anchor_kind.append(_anchor_kind or "")
            sc.edge_transverse_road.append(_road_xsec)

    sc.spine_chains = _build_spine_chains(shape, ctx, membership)
    return sc


def _build_spine_chains(shape: GradeShape, ctx: GradeContext,
                        membership: dict) -> list[list[Hashable]]:
    """Ordered spine node-key chains (one per centerline crossing the shape),
    sorted by arc position — the smooth-profile handle for the connecting
    solve."""
    by_cl: dict[int, list[tuple[float, Hashable]]] = {}
    for ri, hits in membership.items():
        for (ci, a) in hits:
            by_cl.setdefault(ci, []).append((a, shape.keys[ri]))
    chains = []
    for ci, lst in by_cl.items():
        lst.sort(key=lambda t: t[0])
        chain = [k for (_a, k) in lst]
        if len(chain) >= 2:
            chains.append(chain)
    return chains


def plane_constraints(shape: GradeShape, ctx: GradeContext,
                      cap: float) -> ShapeConstraints:
    """Within-shape constraints for a PLANE shape — a sloping taxi rect, a runway
    segment, or a flat terminal pad — via the SAME law as the soft shapes
    (:func:`grade_law.classify_pair`).

    A plane's pairwise grade IS the plane's slope along that chord, so the rule is
    simply ALL vertex pairs at the shape's ``cap`` (no spine / blend / visibility
    gating — these shapes are convex 4-corner; terminals are checked all-pair as
    before).  The seam and road-carve rules still apply (a plane vertex on a road
    carve descends at the road cap).  ``cap`` is the shape's within-shape cap the
    caller resolves (per-letter for a taxi rect, the runway/terminal cap
    otherwise).  This is the single rule source for plane shapes: both the
    in-memory validator and the OSM grade test build a ``GradeShape`` and call it,
    so they cannot drift from each other or from the law."""
    sc = ShapeConstraints(role=shape.role)
    ring = shape.ring
    keys = shape.keys
    n = len(ring)
    if n < 3:
        return sc
    seam = ctx.seam_keys
    road_vert = None
    if ctx.road_zone is not None:
        from shapely.geometry import Point as _RPt
        road_vert = [ctx.road_zone.contains(_RPt(x, y)) for (x, y) in ring]
    # RUNWAY within-shape LATERAL scoping (user 2026-07-08): a de-segmented
    # runway emits ONE ring whose FAA profile stations live as interior long-edge
    # vertices, so its all-pair within-shape check conflates the LATERAL law
    # (this check's real domain) with the LONGITUDINAL profile law
    # (``check_runway_profile`` + the spine-profile check).  Scope the runway
    # ring's pairs to SAME-/ADJACENT-station (``grade_law.runway_within_pair_in_
    # domain``); a pair spanning 2+ stations leaves this domain to the profile
    # law.  ONE predicate in ``grade_law``, applied HERE — ``plane_constraints``
    # is the single plane-rule source both the OSM grade test (``check_grade``'s
    # runway path) and any solver plane-edge build call —
    # so BUILD and CHECK scope in lockstep.  ONLY the de-segmented single-poly
    # ring (``shape.single_poly``) is scoped: its length ≫ width so the
    # longest-pair ref axis IS the runway axis and same-cross-end vertices
    # cluster to one station.  A legacy segmented sub-rect is left alone — it
    # keeps its full all-pair check (a short/wide rect's longest pair is a
    # DIAGONAL, which would spuriously split its two cross-ends into >2
    # stations and drop real pairs), so gate-off stays byte-identical.
    station_of = (GL.runway_axis_station_indices(ring)
                  if (shape.role == "runway" and shape.single_poly)
                  else None)
    for i in range(n):
        xi, yi = ring[i]
        ki = keys[i]
        for j in range(i + 1, n):
            kj = keys[j]
            if ki == kj:
                continue
            if (station_of is not None
                    and not GL.runway_within_pair_in_domain(
                        station_of[i], station_of[j])):
                continue
            xj, yj = ring[j]
            d = math.hypot(xi - xj, yi - yj)
            both_road = bool(road_vert and road_vert[i] and road_vert[j])
            _pc = GL.PairContext(
                role=shape.role, dist=d,
                ring_adjacent=(j == i + 1) or (i == 0 and j == n - 1),
                a_seam=ki in seam, b_seam=kj in seam,
                a_building=False, b_building=False,
                spine_caps=(), body_cap=cap, both_road=both_road)
            allow = GL.classify_pair(_pc)
            if allow is None:
                continue
            sc.edges.append((ki, kj, allow))
            # Index-parallel, from the same law call — this path is the
            # PLANE (runway) one and answers False for every real shape,
            # but keeping the two lists the same length by CONSTRUCTION is
            # what stops a silent misalignment if it ever carries an apron.
            sc.edge_interior.append(GL.is_apron_interior(_pc))
            sc.edge_anchor_kind.append("")
    return sc


# ── THE ONE GRAPH (solver sets on it, validator checks it) ───────────────────

@dataclass
class UnifiedGraph:
    """THE single grade graph on GEOMETRY NODES (node indices via
    ``bucket_to_idx``) — the SAME nodes the solver sets elevations on and the
    validator checks (docs/goal_merge_one_graph.md).

    * ``pos``           — ``{node_idx: (x, y)}`` local-meter position.
    * ``edges``         — every undirected grade edge ``(a, b, cap, is_spine)``:
      apron/junction within-shape (body + spine) + sloping-rect/cap all-pair.
      ``is_spine`` marks the taxi-spine pairs (apron/junction spine chains + the
      rect/cap pairs) the strict spine gate covers.
    * ``spine_adj``     — ``{i: [(j, budget), ...]}`` over the SMOOTH-PROFILE
      spine subgraph (centerline-consecutive apron/junction pairs + rect axis +
      rect-cap continuation), ``budget = cap·dist``.  This is what the spine
      solve smooths; a 1-D feasible chain.
    * ``runway_anchor`` — ``{node_idx: local_runway_elev}`` for every geometry
      node a taxi spine joins the runway at (the single hard anchor; the building
      floor yields to it).
    * ``runway_anchor_sample`` — ``{node_idx: (sample_x, sample_y, shape)}``
      the exact point (and owning runway/crossing SHAPE) the anchor value was
      sampled at.  The crown writeback (user ruling 2026-07-16: taxi joins
      anchor to the RUNWAY EDGE value — the crowned edge, never the
      centerline/crown profile) re-samples that shape's EMITTED edge at THIS
      point and assigns the join node the drop that lands it exactly there.
    """
    pos: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    spine_adj: dict = field(default_factory=dict)
    runway_anchor: dict = field(default_factory=dict)
    runway_anchor_sample: dict = field(default_factory=dict)
    # Canonical ``(min, max)`` node pairs of spine edges woven from a
    # SERVICE-ROAD centerline (owner ruling 2026-07-29): the solve still
    # grades roads along these, but airside REACHABILITY must never ride
    # them — ``reach_band_unified`` skips these pairs in its value-field
    # Dijkstras (gate ``O4_REACH_NO_SERVICE_SPINES``).
    service_spine_pairs: set = field(default_factory=set)
    # ── R-a · THE ROUTE-TRANSPARENT NODES (lead ruling 2026-08-08) ─────
    # The cross-section feet ``lateral_spine_nodes`` planted, resolved into
    # THIS graph's node space by ``_build_global_spine`` (see its docstring
    # for the law and the HECA measurement).  They are excluded from every
    # centerline chain, so no ``spine_adj`` budget has one as an endpoint —
    # this set is the RECORD of that, published for instruments, and read
    # by nothing in the solve.  Empty when the flag is off or the layout
    # planted no laterals, which is when the graph is byte-identical to
    # the pre-R-a one.
    route_transparent_nodes: set = field(default_factory=set)
    # ── CENTERLINE AUTHORSHIP of the spine (S1 Stage 0 level 1, Fable
    # ruling 2026-07-31) ───────────────────────────────────────────────
    # ``_build_global_spine`` already orders each centerline's on-line
    # nodes by arc position before linking them; recording that ordered
    # list is the AUTHORED truth of "which taxiway is this", exported
    # from the same walk at zero extra cost.  S1 assembles its string
    # domains from these instead of from heading heuristics, which were
    # MEASURED to fail on real geometry (terminal segments of the
    # ``_build_spine_corridors`` pieces peel perpendicular onto crossers
    # and fillets, so a piece-scale heading is jitter, not signal).
    # Plain graph attributes ON PURPOSE: this never crosses node spaces,
    # so it is deliberately NOT a U1 node-space artifact.
    centerline_chains: dict = field(default_factory=dict)   # ci -> [node]
    centerline_service: set = field(default_factory=set)    # service ci's
    # ── SPINE-DROP CENSUS (hygiene 2026-07-31) ─────────────────────────
    # ``_build_global_spine`` can only link a centerline into ``spine_adj``
    # once it has found at least TWO geometry nodes within
    # ``SPINE_PERP_TOL_M`` of it; a centerline with 0 or 1 contributes NO
    # string and used to vanish without a counter or a log line (P7 2026-
    # 07-31: the route-arc stage hands this walk 653 ways at HECA and
    # nothing in the build log said how many died here).  Counted apart
    # because they are DIFFERENT findings with different fix loci — zero
    # nodes means no geometry under the way at all, one node means a
    # THINNED region (P7's density-is-not-a-binary lesson).
    spine_centerlines: int = 0        # centerlines walked
    spine_no_string: int = 0          # ... that yielded < 2 on-line nodes
    spine_no_string_zero: int = 0     # ... of those, with NO on-line node
    # ── THE SERVICE HALF (cycle 8) ─────────────────────────────────────
    # ``spine_service_centerlines`` is the DENOMINATOR the service line
    # never carried: "0 strung" reads as "no roads here" and as "the roads
    # did not string", and those are different findings with different fix
    # loci.  ``spine_service_attachments`` counts the service-strung nodes
    # the AIRCRAFT pass had already strung — the MOUTH candidates, i.e.
    # exactly the seeds ``building_feasibility.service_mouths`` can find.
    spine_service_centerlines: int = 0
    spine_service_attachments: int = 0

    # ── EDGE PROVENANCE (cycle-5 certificate family axis, spec fix 4) ───
    # Parallel to ``edges``: the CONSTRUCTOR that minted each edge, as
    # ``"unified:<role>"`` / ``"unified:<role>:spine"``.  The shipped
    # ``[proj-law-certificate]`` dumped 80.6 % of its mass into one
    # ``unified_graph`` catch-all because this graph's whole ``edges``
    # list entered the joint as ONE entry with a single literal tag — a
    # construction site, not a law.  Recorded at mint time (the only
    # place the owning shape's role is in hand) and read ONLY by the
    # certificate: nothing in the solve consumes it, the edge tuples are
    # unchanged, and the edge ORDER is untouched — the certificate splits
    # the bucket by LOOKUP, never by regrouping the constraint set.
    edge_family: list = field(default_factory=list)
    #: MINT-TIME STAGE per edge (staged-solve S1b), index-parallel to
    #: :attr:`edges`: the lawful-airside partition of the SHAPE that
    #: minted the edge.  See :mod:`auto_patch.solve_stage`.
    edge_stage: list = field(default_factory=list)
    #: Index-parallel to :attr:`edges`: True for an APRON INTERIOR pair
    #: (the apron staged solve's partition input, spec §§1-3).
    edge_interior: list = field(default_factory=list)
    #: THE §1 ANCHOR NEIGHBOURHOOD, published for the DEM-LAST SEAT BIAS
    #: (owner ruling RULINGS 2026-08-25 second ruling; spec
    #: ``apron-chord-anchor-target-spec.md`` §2): ``(node_a, node_b,
    #: budget_m, kind)`` for every pair the ONE nearest-anchor enumeration
    #: selected, where ``budget_m`` is that chord's own ``cap x dist`` and
    #: ``kind`` is ``ANCHOR_KIND_SPINE`` / ``ANCHOR_KIND_PAD``.
    #:
    #: NOT a second enumeration and not a re-derivation: it is
    #: ``ShapeConstraints.edge_anchor_kind`` carried into the solve's node
    #: index space at MINT, so the level a pad seats at is chosen against
    #: exactly the chords its ring vertices are priced on.  Deriving the
    #: neighbourhood later — from the emitted ring, or from a second
    #: nearest search — is the census-wrapper defect in seat form.
    anchor_chords: list = field(default_factory=list)
    #: APRON NODES INSIDE THE RUNWAY STRIP (spec AMENDMENT A4.2; owner
    #: ruling RULINGS 2026-08-21d, wired 2026-08-24).  Their pairs are
    #: SKIPPED by ``grade_law.classify_pair``, so they carry no edge and
    #: the seniority partition's edge-derived domain cannot see them.
    #: Accumulated at mint from ``ShapeConstraints.strip_excluded`` and
    #: handed to ``grade_law.apron_node_seniority`` as ``excluded_nodes``,
    #: which is what makes the sidecar's third value (``excluded``) real
    #: rather than merely declared.
    apron_excluded_nodes: set = field(default_factory=set)
    #: MINT-TIME STAGE per NODE (staged-solve S1b): ``{node_idx: stage}``,
    #: stamped as each shape registers its ring positions.  AIRSIDE WINS a
    #: shared node — a service-road mouth vertex on an apron ring is
    #: airside data (RULINGS 2026-08-06, the mouth seat).
    node_stage: dict = field(default_factory=dict)

    def stage_by_pair(self) -> dict:
        """``{(min(a,b), max(a,b)): stage}`` from :attr:`edge_stage`.

        Keyed by NODE PAIR, never by list position, so it survives the
        budget rewrites the callers apply to their ``u_edges`` copy —
        the same reason :meth:`family_by_pair` is.  A pair two shapes
        both mint keeps the AIRSIDE stage when either claimant is
        airside: airside is king, and a shared law pair the apron also
        owns is the apron's to enforce in its own pass.
        """
        out: dict = {}
        for (a, b, _c, _sp), st in zip(self.edges, self.edge_stage):
            key = (a, b) if a <= b else (b, a)
            prev = out.get(key)
            if prev is None or (prev != "A" and st == "A"):
                out[key] = st
        return out

    def spine_edge_set(self):
        """The undirected spine pairs ``{(min(a,b), max(a,b))}`` (is_spine)."""
        return {(min(a, b), max(a, b))
                for (a, b, _c, sp) in self.edges if sp}

    def interior_pairs(self) -> set:
        """``{(min(a,b), max(a,b))}`` for every APRON INTERIOR pair.

        The apron staged solve's own partition input (spec
        ``docs/specs/apron-staged-solve-spec.md`` §2): the senior pass
        withholds exactly this set, the interior pass projects exactly it.
        Keyed by NODE PAIR for the same reason :meth:`family_by_pair` is —
        callers rewrite their ``u_edges`` copy freely.

        A pair minted INTERIOR by one shape and STRICT by another resolves
        to STRICT: seniority is a claim about a movement surface, and a
        surface that any shape calls a movement surface is one.
        """
        out, strict = set(), set()
        for (a, b, _c, _sp), it in zip(self.edges, self.edge_interior):
            if not isinstance(a, int) or not isinstance(b, int):
                continue
            k = (min(a, b), max(a, b))
            (out if it else strict).add(k)
        return out - strict

    def family_by_pair(self) -> dict:
        """``{(min(a,b), max(a,b)): family}`` from :attr:`edge_family`.

        The certificate's per-edge family resolver.  Keyed by NODE PAIR,
        not by list position, so it survives every rewrite the callers
        apply to their ``u_edges`` copy (the terrace and fan-ramp
        appliers rewrite BUDGETS on the same pairs; the near-miss
        frontage law APPENDS pairs this graph never minted — those
        resolve to no entry and keep their caller's own family).
        Duplicate pairs from two shapes keep the FIRST minted family;
        the certificate is a report, and a pair that two constructors
        both claim is named by one of them either way.
        """
        out: dict = {}
        for (a, b, _c, _sp), fam in zip(self.edges, self.edge_family):
            key = (a, b) if a <= b else (b, a)
            if key not in out:
                out[key] = fam
        return out

    def airside_spine_nodes(self):
        """The stage-A subset of ``spine_adj``'s node set (S1b).

        The three airside authorities that iterate ``spine_adj`` whole —
        the apron-terrace anchor resolver, the building hard-truth seeds
        and the runway-contact anchor membership test (couplings 17-19 of
        ``tmp/s1_attribution.md``) — predate the standing
        ``REACH_NO_SERVICE_SPINES`` law that the reach band and phase A
        already obey.  A node with no minted stage is airside: the
        conservative side under airside-is-king.
        """
        return {i for i in (self.spine_adj or {})
                if self.node_stage.get(i, "A") == "A"}

    def spine_nodes(self):
        s = set()
        for (a, b, _c, sp) in self.edges:
            if sp:
                s.add(a)
                s.add(b)
        return s


#: RUN-SCOPED MEMO KILL SWITCH (perf P3 lane perfgraph).  Module level so
#: the twin can turn the second memo OFF and compare the SAME solve's
#: constraint sets with it on — an equality, not an argument.  Never read
#: as law and never a gate: with it False the code is exactly what it was
#: before the memo landed (the per-ctx memo still runs).
SC_RUN_MEMO = True


def _ctx_law_digest(ctx: GradeContext):
    """Digest of the ctx inputs :func:`shape_constraints` reads GLOBALLY —
    the ones whose influence on a shape cannot be projected onto that shape
    in O(n).  Cached on the ctx (computed once per graph build).

    The transitive read set of ``shape_constraints`` is exactly ten
    ``GradeContext`` fields — the eight below plus the apron
    movement-surface pair added 2026-08-21b, ``frontage_keys`` (projected
    per shape by :func:`_sc_run_key`, like ``building_keys``) and
    ``corridor_lines`` (DERIVED from ``centerlines`` by the one function
    ``centerline_geometries``, so this digest already covers it) (verified by walking every function reachable
    from it: ``centerlines`` via ``_spine_membership`` / ``_spine_cap`` /
    ``_spine_crossing_predicate`` / ``_nearest_centerline`` / ``_edge_route``
    / ``_polyline_tree`` / ``_route_oracle`` / ``_route_taxi_cap``,
    ``routes`` via ``_edge_route`` / ``_polyline_tree``, and ``seam_keys``,
    ``building_keys``, ``road_zone``, ``route_zone``, ``mesh_edges_exact``,
    ``inherited_junction_cap`` read in ``shape_constraints`` /
    ``_body_cap_unbounded`` themselves).  ``_route_metric_oracle`` and
    ``_route_taxi_cap_memo`` are memos the ctx derives from ``centerlines``
    / ``routes``, not inputs.

    THIS digest covers five of them — ``centerlines``, ``routes``,
    ``road_zone``, ``route_zone``, ``mesh_edges_exact``.  The other three
    are projected per shape by :func:`_sc_run_key`, which is what makes a
    cross-build hit possible at all: at HECA ``building_keys`` moves
    between EVERY pair of graph builds (measured), so a whole-ctx digest
    keyed 0 hits out of 12,078 computations while the per-shape projection
    keyed 1,275.

    ``None`` ⇒ this ctx carries an input this function cannot digest, and
    the run memo stays OFF for it (a key that cannot see an input is a
    wrong-answer machine — the ruling's spirit: key on inputs, never on
    live mutable state).  ``mesh_edges_exact`` is that case: it is the
    validator's sidecar structure, never set on a solve ctx.
    """
    d = getattr(ctx, "_law_digest", "?")
    if d != "?":
        return d
    d = None
    try:
        if ctx.mesh_edges_exact is not None:
            raise ValueError("mesh_edges_exact is not digestible")
        h = hashlib.sha256()
        for c in ctx.centerlines:
            h.update(repr((tuple(c.pts), tuple(c.seg_caps), c.route_idx,
                           bool(c.is_service))).encode())
        h.update(b"\x00routes\x00")
        for r in (ctx.routes or []):
            h.update(repr(tuple(r.pts)).encode())
        for name in ("road_zone", "route_zone"):
            z = getattr(ctx, name)
            h.update(b"\x00" + name.encode() + b"\x00")
            if z is not None:
                # A prepared geometry's own geometry is what the predicate
                # answers from; WKB is its exact coordinate identity.
                h.update(getattr(z, "context", z).wkb)
        d = h.hexdigest()
    except Exception:                                     # pragma: no cover
        d = None
    ctx._law_digest = d
    return d


def _sc_run_key(gs: GradeShape, ctx: GradeContext, ring_only: bool):
    """The RUN-scoped memo key: every input the computation reads.

    Shape side — the whole ``GradeShape`` the law consults: ``role``, the
    exact ring coordinates (never rounded: a rounded ring is an under-keyed
    ring), the node ``keys`` (they label the answer AND gate it, via the
    ``ki == kj`` skip), and the five per-shape law flags.

    Ctx side — :func:`_ctx_law_digest` for the global five, plus the three
    that are projected onto THIS shape in O(n), which is what a cross-build
    hit needs:

      * ``building_keys`` / ``seam_keys`` / ``frontage_keys`` are read ONLY
        as ``key in set`` for this shape's own keys, so the membership
        vector IS their whole influence.  ``frontage_keys`` (RULINGS
        2026-08-21b) moves between builds exactly as ``building_keys`` does
        — it is a subset of it — so it is projected here, never digested
        globally.  The apron rule's OTHER input, corridor membership, is a
        pure function of this shape's ring and ``ctx.centerlines``, both of
        which the key already carries (``gs.ring`` and the law digest);

      * ``inherited_junction_cap`` is read ONLY as
        ``ctx.inherited_junction_cap(shape)`` (``_body_cap_unbounded``'s
        last line), so its RETURN VALUE for this shape is its whole
        influence.  ``build_context``'s closure is pure — it reads a
        rounded-coordinate dict built before the ctx was returned — so
        calling it here is a read, never a side effect.

    ``None`` ⇒ do not memo (undigestible ctx)."""
    d = _ctx_law_digest(ctx)
    if d is None:
        return None
    keys = tuple(gs.keys)
    bld = ctx.building_keys
    seam = ctx.seam_keys
    return (d, gs.role, bool(ring_only),
            tuple(gs.ring), keys,
            tuple(k in bld for k in keys),
            tuple(k in seam for k in keys),
            tuple(k in ctx.frontage_keys for k in keys),
            float(ctx.inherited_junction_cap(gs)),
            bool(getattr(gs, "fan_ramp_zone", False)),
            bool(getattr(gs, "adopts_apron_grade", False)),
            bool(getattr(gs, "adopts_taxi_grade", False)),
            getattr(gs, "adopted_taxi_letter", None),
            getattr(gs, "lateral_cap", None))


def _sc_ctx_key(gs: GradeShape, ring_only: bool):
    """The PER-CTX memo key — CONTENT, never ``id()`` (finalarch item 2,
    RULINGS 2026-08-14 "THE DOUBLE PROJECTION RETIRES" / the repetition
    charter; the perfgraph/perfcenter key discipline: value keys).

    The historical key was ``(id(s.polygon), role, ring_only)``.  Within
    one build that is safe — every keyed polygon is alive for its whole
    lifetime — but a ctx carried ACROSS the freeze→solve gap is not:
    ``construct_adjacent_ground_presolve`` mints and drops thousands of
    temporary polygons in between and CPython reuses ``id()`` freely, so
    a recycled id served one shape another shape's constraint pairs
    (measured at HECA: within_shape 3,764 → 5,629, worst 431 % — the
    refusal that kept the freeze-published graph unreused).  This key
    spells the SAME identity by value: everything ``shape_constraints``
    reads off the ``GradeShape`` itself.  The ctx-side inputs (law
    digest, building/seam membership, inherited junction cap) are NOT
    here because a per-ctx memo's scope holds them constant — the
    RUN-scoped tier below keys on them (:func:`_sc_run_key`) exactly
    because it crosses ctxs.

    A ctx may therefore be REUSED across the freeze→solve gap iff the
    layout's solve-consumed geometry is unchanged (the geometry-freeze
    rail proves it) — which is what makes the freeze-published graph
    build-once-read-many.

    Note the flag triple is IN the key: the two consumers construct
    GradeShapes that differ only in the gate-off ``adopts_*`` flags
    (``solver_primitives._grade_graph_edges`` omits them), and the old
    id key let whichever consumer ran FIRST fix the answer for both.
    Under the lateral-contiguity law (standing, ungated) the flags are
    never set, so the flavors are identical in production; keying on
    them closes the reported first-writer-wins gap structurally instead
    of preserving it.
    """
    return ("scmemo", gs.role, bool(ring_only),
            tuple(gs.ring), tuple(gs.keys),
            bool(getattr(gs, "fan_ramp_zone", False)),
            bool(getattr(gs, "adopts_apron_grade", False)),
            bool(getattr(gs, "adopts_taxi_grade", False)),
            getattr(gs, "adopted_taxi_letter", None),
            getattr(gs, "lateral_cap", None))


def shape_constraints_cached(polygon_key, gs: GradeShape,
                             ctx: GradeContext,
                             ring_only: bool = False) -> "ShapeConstraints":
    """Memoised :func:`shape_constraints` — keyed BY CONTENT
    (:func:`_sc_ctx_key`) on the CONTEXT, so the two per-solve law
    consumers (``solver_primitives._build_shape_constraints`` and
    :func:`build_unified_graph`, which construct identical ``GradeShape``s
    from the same polygons) run the expensive pair generation ONCE when they
    share a ctx (measured ~11 s/solve of duplicate work at SPJC).  Results
    are shared, never mutated by either consumer.  ``polygon_key`` (the
    callers' ``id(s.polygon)``) is retired from the key — see
    :func:`_sc_ctx_key` for the recycled-id defect that forced it — and
    kept in the signature only so the call sites need not churn.

    ``ring_only`` is part of the key (user 2026-07-05 flatness tier): the
    certified-lazy branch's ring-only result and ``build_unified_graph``'s
    FULL result (which feeds the validator-parity ``u_edges`` projection and
    the reach fields, so it must never be thinned) coexist without either
    consumer seeing the other's set.

    ── SECOND TIER: THE RUN-SCOPED MEMO (perf P3 lane perfgraph) ──────────
    One solve builds the unified graph SIX times at HECA (apron-terrace
    presolve, adjacent-ground presolve, the solve itself, two final
    projections, the validator), each from a fresh ctx and therefore a
    fresh per-ctx memo, and re-derives every shape.  The measured
    cross-build redundancy is real but partial: at HECA 1,275 of 12,078
    computations (10.6 %) reproduce an earlier build's answer EXACTLY, at
    CYXY 310 of 1,522 (20.4 %), and in both cases the whole set is the
    second presolve repeating the first.  A hit is served from
    ``layout._sc_run_memo``, which lives for exactly one solve run.

    The key (:func:`_sc_run_key`) covers every input the computation reads
    — that is the whole design, not a precaution: the OBVIOUS key
    (geometry + node keys) hits the same 1,275 at HECA and has never
    produced a different answer in 13,600 measured computations, and it is
    still forbidden, because nothing in it would NOTICE a moved
    ``building_keys``.  The soundness is in the key, never in the
    coincidence.  ``sc`` objects are shared, exactly as the per-ctx memo
    already shares them between its two consumers, and no consumer mutates
    one (both only read ``sc.edges`` / ``sc.spine_chains``).

    MEASURED AND REJECTED — a FLOAT-ORDER win, so out of scope by the perf
    charter, and recorded here so the next lane does not rebuild it.  Keying
    in RING-INDEX space (cache the pair set by ring index, RELABEL to node
    keys on a hit) has a measured ceiling of 58.5 % at HECA / 54.6 % at CYXY:
    the node numbering moves between builds far more often than the law does
    (3,266 of HECA's 4,857 distinct shape-states appear under more than one
    key spelling).  It is unreachable.  In 114 of those HECA computations
    (7 at CYXY) two builds agree on the ring, the key-equality pattern and
    EVERY projected ctx input, produce the SAME pair set with the same caps,
    and still differ — in the last ULP of the route-metric BAKED budget
    (measured at CYXY: pair (7,8) of an 18-vertex junction,
    0.021270521763298956 vs ...52, identical ``_spine_membership`` and
    ``body_cap``).  The route decomposition is not bit-stable across graph
    builds, so serving one build's answer to another would move emitted
    bytes.  This tier therefore keys in NODE-KEY space, where those pairs
    never collide, and takes the 10.6 %."""
    memo = getattr(ctx, "_sc_memo", None)
    if memo is None:
        memo = {}
        ctx._sc_memo = memo
    key = _sc_ctx_key(gs, ring_only)
    sc = memo.get(key)
    if sc is not None:
        return sc
    run = getattr(ctx, "_sc_run_memo", None) if SC_RUN_MEMO else None
    run_key = None
    if run is not None:
        run_key = _sc_run_key(gs, ctx, ring_only)
        if run_key is not None:
            sc = run.get(run_key)
    if sc is None:
        sc = shape_constraints(gs, ctx, ring_only=ring_only)
        if run is not None and run_key is not None:
            run[run_key] = sc
    memo[key] = sc
    return sc


def build_unified_graph(layout, bucket_to_idx, ctx=None, *,
                        skip_edge_shape_ids=None,
                        include_spine=True) -> "UnifiedGraph":
    """Assemble THE one graph on geometry node indices.

    This is the SINGLE graph the route-profile solver sets elevations on and the
    validator (``grade_graph_validate.within_violations``) checks — the same
    nodes, edges, per-letter caps and runway anchors, so build and validate can
    never drift (the whole point of docs/goal_merge_one_graph.md).

    ``ctx``: optionally a prebuilt :func:`build_context` — pass the SAME one
    ``solver_primitives._build_shape_constraints`` used so the per-shape law
    memo (:func:`shape_constraints_cached`) is shared instead of recomputed.

    SCOPED FINAL PROJECTION (user 2026-07-05, ``O4_SCOPED_FINAL_PROJECTION``):
    ``skip_edge_shape_ids`` — apron/junction shapes (by ``id(s)``) whose
    within-shape ``G.edges`` contribution is SKIPPED (their positions are
    still registered).  TWO callers pass it, both with a PROOF that the
    skipped pairs are already satisfied — never as an optimisation on faith:
    ``final_grade_projection`` for shapes it proved unchanged since the solve
    (their identical pair set is carried by that caller's lazy entries), and
    the FLAT-SITE FAST PATH (docs/specs/flat-site-fast-path-spec.md §1) for
    shapes born at a single constant Z0, where every within-shape pair reads
    grade 0 and no cap can be exceeded.  Because positions stay registered,
    the global spine still strings across a skipped shape and the reach band
    keeps its connectivity in both cases.
    ``include_spine=False`` additionally skips the global spine /
    runway-anchor stages (``spine_adj`` and
    ``runway_anchor`` consumers), which that caller never reads — it uses
    ``G.edges`` only.  Defaults reproduce the full graph exactly.
    """
    cps = layout.canonical_points
    if ctx is None:
        ctx = build_context(layout, bucket_to_idx)
    G = UnifiedGraph()

    def _idx(x, y):
        return bucket_to_idx.get(cps.get_or_add(float(x), float(y)))

    # ── apron / junction within-shape edges (body + spine), node-index keyed ──
    for s in layout.shapes:
        if (s.role not in SOFT_VISIBILITY_ROLES or s.polygon is None
                or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        if len(ring) < 3:
            continue
        idx = [_idx(x, y) for (x, y) in ring]
        keys = [i if i is not None else ("_n", p) for p, i in enumerate(idx)]
        _s_stage = _stage_of_shape(s)
        for p, i in enumerate(idx):
            if i is not None:
                G.pos[i] = ring[p]
                # MINT-TIME NODE STAGE (S1b).  Airside wins a shared node.
                if G.node_stage.get(i) != "A":
                    G.node_stage[i] = _s_stage
        if skip_edge_shape_ids is not None and id(s) in skip_edge_shape_ids:
            continue    # scoped projection: pairs live in the caller's lazy entry
        gs = GradeShape(role=s.role, ring=list(ring), keys=keys,
                        fan_ramp_zone=getattr(s, "fan_ramp_zone", False),
                        adopts_apron_grade=getattr(
                            s, "adopts_apron_grade", False),
                        adopts_taxi_grade=getattr(
                            s, "adopts_taxi_grade", False),
                        adopted_taxi_letter=getattr(
                            s, "adopted_taxi_letter", None),
                        lateral_cap=getattr(s, "lateral_cap", None))
        sc = shape_constraints_cached(id(s.polygon), gs, ctx)
        # A4.2 EXCLUDED APRON NODES, accumulated as the shapes are walked
        # (their pairs never reach ``G.edges``, so this is the only place
        # the graph can learn about them).
        if sc.strip_excluded:
            G.apron_excluded_nodes.update(
                int(k) for k in sc.strip_excluded if isinstance(k, int))
        # Ring position of each key — needed by the anchor-chord publish
        # inside the edge loop AND by the lockstep bake export below, so it
        # is built ONCE here rather than twice.
        position_of_key = {key: p for p, key in enumerate(keys)}
        spine_pairs = set()
        for chain in sc.spine_chains:
            for u, v in zip(chain, chain[1:]):
                if isinstance(u, int) and isinstance(v, int):
                    spine_pairs.add((min(u, v), max(u, v)))
        for _ei, (a, b, cap) in enumerate(sc.edges):
            if not isinstance(a, int) or not isinstance(b, int):
                continue
            is_spine = (min(a, b), max(a, b)) in spine_pairs
            G.edges.append((a, b, cap, is_spine))
            # Mint-time provenance for the certificate (see ``edge_family``).
            # ONE speller, shared with the sidecar's ``pair_caps`` family tag
            # (spec §7) — ``edge_family_name``.
            G.edge_family.append(edge_family_name(s.role, is_spine))
            # THE STAGED-SOLVE PARTITION, minted where the law answered it.
            G.edge_interior.append(
                bool(sc.edge_interior[_ei]) if _ei < len(sc.edge_interior)
                else False)
            # MINT-TIME STAGE (staged-solve S1b).  The unified graph
            # reaches every projection as ONE bare ``{"edges": u_edges}``
            # entry with no role key, so a service_road / groundside lot
            # law pair inside it was enforced in the AIRSIDE pass
            # (couplings 3 and 6 of tmp/s1_attribution.md).  The shape
            # that mints the edge is the only place its stage is known;
            # ``edge_stage`` is index-parallel to ``edges`` and
            # ``edge_family``, and ``stage_by_pair()`` is the readers'
            # pair-keyed view.
            G.edge_stage.append(_stage_of_shape(s))
            # THE §1 ANCHOR NEIGHBOURHOOD (RULINGS 2026-08-25 §2).  The
            # kind the ONE enumeration minted for this pair, carried into
            # the solve's node space with the chord's OWN budget
            # (cap x dist) — the quantity the seat bias measures its
            # residuals in.  Only anchor chords are published; everything
            # else carries ``""`` and is skipped here.
            _ak = (sc.edge_anchor_kind[_ei]
                   if _ei < len(sc.edge_anchor_kind) else "")
            if _ak:
                _pa = position_of_key.get(a)
                _pb = position_of_key.get(b)
                if _pa is not None and _pb is not None:
                    _d = math.hypot(ring[_pa][0] - ring[_pb][0],
                                    ring[_pa][1] - ring[_pb][1])
                    G.anchor_chords.append(
                        (a, b, float(cap.flat_cap()) * _d, _ak))
        # LOCKSTEP BAKE EXPORT (2026-07-17): persist THIS shape's baked
        # decomposition in RING-POSITION space so the validator
        # (``grade_graph_validate._iter_checked_pairs``) consumes the
        # identical allowances instead of re-baking with a context it
        # cannot reconstruct (its ``build_context(layout)`` has no
        # ``bucket_to_idx``; measured CYXY: 29 of 9,915 shared edges
        # resolved a marginally different route-arc allowance on
        # re-bake).  Keyed by ``id(s)`` and guarded by (role, ring
        # signature): a post-solve-mutated ring misses the guard and
        # the validator re-bakes fresh — correct, its geometry changed.
        # Repeat builds (the scoped final projection) re-bake only the
        # shapes they re-run; skipped shapes keep the solve-time entry,
        # whose ring is unchanged by definition of the skip.
        ring_signature = tuple(
            (round(x, 6), round(y, 6)) for (x, y) in ring)
        baked_edges = []
        for (a, b, cap) in sc.edges:
            pa = position_of_key.get(a)
            pb = position_of_key.get(b)
            if pa is not None and pb is not None:
                baked_edges.append((pa, pb, cap))
        baked_spine = set()
        for chain in sc.spine_chains:
            for u, v in zip(chain, chain[1:]):
                pu = position_of_key.get(u)
                pv = position_of_key.get(v)
                if pu is not None and pv is not None:
                    baked_spine.add((min(pu, pv), max(pu, pv)))
        bake_store = getattr(layout, "_lockstep_shape_bake", None)
        if bake_store is None:
            bake_store = {}
            layout._lockstep_shape_bake = bake_store
        bake_store[id(s)] = (
            s.role, ring_signature, baked_edges, baked_spine)

    if include_spine:
        # ── GLOBAL spine chains: per centerline, all on-line geometry nodes
        # ordered by arc and linked consecutive (budget = cap·arc-gap).  This
        # connects the spine ACROSS shape boundaries (junction→apron→junction)
        # — one connected, ≤cap profile, exactly what the route graph gave
        # but on the geometry nodes themselves.
        # SERVICE STRINGING (cycle 8): the road-family node set the service
        # pass may string over, resolved in THIS call's node space (never
        # cached across node spaces — the rod-key lesson).
        _build_global_spine(G, ctx, icao=getattr(layout, "icao", ""),
                            road_nodes=_road_family_nodes(layout,
                                                          bucket_to_idx),
                            layout=layout)
        _write_service_stringing_diag(layout, G)
        _withhold_service_edges_probe(G, icao=getattr(layout, "icao", ""))

        # ── runway anchors: every geometry node a taxi spine joins the runway
        # at ──
        _runway_anchors(layout, G, bucket_to_idx)
    # R3 (service-road law spec): report the service-family pairs whose
    # unshared-route bake migrated to a nearest-endpoint route (cumulative
    # on this shared ctx — the per-shape law memo means a pair is baked,
    # and therefore counted, once).
    _n_mig = getattr(ctx, "_svc_pair_route_migrated", 0)
    if _n_mig:
        import O4_UI_Utils as _UI_r3
        _UI_r3.vprint(1,
            f"  [pav-builder] R3 unshared-route service pairs migrated to "
            f"the nearest-endpoint route bake (transverse cap applies): "
            f"{_n_mig} pair(s).")
    return G


def _withhold_service_edges_probe(G, icao: str = ""):
    """PROBE GATE, DEFAULT OFF — ``O4_PROBE_NO_SERVICE_EDGES=1`` withholds
    the service/road route EDGES from ``G.spine_adj`` ITSELF.

    IT HAS TO ACT ON THE GRAPH, not on a caller's alias.  The gate used to
    live in ``solve.py``, where it rebound the LOCAL name ``u_spine_adj``
    — and ``groundside.groundside_route_band`` builds its OWN
    ``build_unified_graph`` and rides ``G.spine_adj``, so the groundside
    band, which is the one consumer the service edges exist for, never saw
    the knife.  Its "withheld from the ONE graph (every consumer)" line was
    FALSE, and the byte-identical patch it produced was an instrument
    artifact rather than evidence about the edges (RULINGS 2026-08-06,
    instrument truth: a lying instrument misroutes more work than a lying
    emitter).  Acting here, at the single site every consumer's graph comes
    out of, is what makes the sentence true.

    ``G.service_spine_pairs`` is KEPT: the MOUTHS are read off that set and
    mouths are the airside/groundside boundary arbiter (RULINGS 2026-08-07)
    — the knife withholds the road's EDGES, never its mouth seats, so what
    it measures is exactly "do the edges bind".
    """
    if os.environ.get("O4_PROBE_NO_SERVICE_EDGES") != "1":
        return
    pairs = getattr(G, "service_spine_pairs", None) or set()
    if not pairs:
        return
    # ONE filter, no second copy (the census-wrapper defect class): the same
    # ``adj_without_pairs`` the airside view uses.  Imported LATE and only
    # under the gate — ``solve`` imports this module at load time.
    from .elevation_per_surface.route_profile.solve import adj_without_pairs
    before = sum(len(v) for v in G.spine_adj.values())
    G.spine_adj = adj_without_pairs(G.spine_adj, pairs)
    after = sum(len(v) for v in G.spine_adj.values())
    import O4_UI_Utils as _UI
    _UI.vprint(1,
        f"  [probe] O4_PROBE_NO_SERVICE_EDGES=1: {icao}: {len(pairs)} "
        f"service pair(s) withheld from G.spine_adj — every consumer, the "
        f"groundside band included ({before} -> {after} directed spine "
        f"edge(s)); the mouths themselves are KEPT.")


def _write_service_stringing_diag(layout, G):
    """REPORT-ONLY, DEFAULT OFF — ``O4_DUMP_SERVICE_STRINGING=<path>``
    writes the per-service-centerline stringing record collected by
    :func:`_build_global_spine`.

    It answers ONE question with numbers and no verdict (RULINGS
    2026-08-06 binding point 2): for every service centerline that
    contributed NO string, WHICH condition failed — no candidate node
    within the tolerance at all (`no_candidate_in_tol`), candidates within
    the tolerance that the eligibility restriction excluded
    (`ineligible_in_tol`), or exactly one on-line node (`one_node`).  The
    three are different mechanisms and only the first is the recorded
    tolerance suspect.

    Positions are emitted in BOTH frames: local metres (the node space
    this was measured in) and 11-decimal lat/lon, which is this repo's
    canonical identity spelling (memory: canonical identity join — never
    proximity).
    """
    path = os.environ.get("O4_DUMP_SERVICE_STRINGING")
    rec = getattr(G, "_service_stringing_diag", None)
    if not path or rec is None:
        return
    to_ll = getattr(layout, "m_to_ll", None)

    def _ll(x, y):
        if to_ll is None:
            return None
        try:
            lat, lon = to_ll(float(x), float(y))
            return [f"{lat:.11f}", f"{lon:.11f}"]
        except Exception:                              # pragma: no cover
            return None

    for row in rec["centerlines"]:
        for n in row.get("nearest", ()):
            n["ll"] = _ll(n["x"], n["y"])
    rec["icao"] = getattr(layout, "icao", "")
    rec["service_perp_tol_m"] = SERVICE_SPINE_PERP_TOL_M
    rec["aircraft_perp_tol_m"] = SPINE_PERP_TOL_M
    rec["service_road_width_m"] = SERVICE_ROAD_WIDTH_M
    try:
        with open(path, "w") as fh:
            json.dump(rec, fh)
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [svc-string-diag] wrote {len(rec['centerlines'])} service "
            f"centerline record(s) -> {path}")
    except Exception as exc:                           # pragma: no cover
        import O4_UI_Utils as _UI
        _UI.vprint(1, f"  [svc-string-diag] WARN: dump failed ({exc!r})")


def _road_family_nodes(layout, bucket_to_idx):
    """Node indices lying on a ROAD-FAMILY / groundside ring.

    The only nodes a SERVICE centerline may string beyond the aircraft
    tolerance (see :data:`SERVICE_SPINE_PERP_TOL_M`).  Role membership comes
    from the layout's OWN registry — ``layout.GROUNDSIDE_ROLES``, the same
    partition the projection partition and ``check_grade.row_side`` use — so
    there is no second role literal to drift (blast.py role-literal hazard).

    READ-ONLY on the canonical-point registry (``find_nearest``, never
    ``get_or_add``): a membership scan must not mint canonical points."""
    from .layout import GROUNDSIDE_ROLES
    out: set = set()
    cps = getattr(layout, "canonical_points", None)
    if cps is None or not bucket_to_idx:
        return out
    tol = cps.tol_m
    for s in (getattr(layout, "shapes", None) or ()):
        if getattr(s, "role", None) not in GROUNDSIDE_ROLES:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            rings = ([poly.exterior] if poly.geom_type == "Polygon"
                     else [g.exterior for g in poly.geoms])
        except Exception:                              # pragma: no cover
            continue
        for ring in rings:
            for (x, y) in ring.coords:
                k = cps.find_nearest(float(x), float(y), tol)
                if k is None:
                    continue
                i = bucket_to_idx.get(k)
                if i is not None:
                    out.add(i)
    return out


def _build_global_spine(G, ctx, icao: str = "", road_nodes=None,
                        layout=None):
    """Order every on-line geometry node along each centerline by arc position and
    link consecutive ones into ``G.spine_adj`` at the centerline's per-letter cap.
    A node may lie on several centerlines (a junction crossing) — it is linked on
    each, so the chains fuse into one connected spine network.

    A centerline with fewer than two on-line nodes contributes NO string.  That
    is counted (``G.spine_no_string`` / ``…_zero``) and summarised in one log
    line — it used to be a silent ``continue`` (hygiene 2026-07-31).

    TWO PASSES, ONE GRAPH (cycle 8, the D′ finisher).  The AIRCRAFT spine is
    strung first, at the tolerance it has always used, over every node — the
    airside membership is exactly what the single-pass walk produced.  SERVICE
    centerlines are strung AFTER, at ``SERVICE_SPINE_PERP_TOL_M`` (their own
    sliced geometry's half-width), over a RESTRICTED node set: ``road_nodes``
    (road-family / groundside ring vertices) plus the nodes the aircraft pass
    just strung.

    The restriction is what makes this receiver-only.  A road may never sweep
    an unrelated apron vertex into a spine chain at its 8 % cap — but it MAY
    adopt the one airside node it genuinely meets, and that node is the MOUTH:
    "the mouth of the service road has to function like an apron edge
    building, seated where it's feasible for the airside apron to meet it,
    then the road and everything else is graded per its law" (RULINGS
    2026-08-06).  ``building_feasibility.service_mouths`` reads exactly those
    attachments, and the pairs stay in ``service_spine_pairs`` so airside
    reachability still refuses to ride them (``REACH_NO_SERVICE_SPINES`` —
    direction, not deletion).

    ``road_nodes`` empty/None ⇒ a service centerline can only string nodes the
    aircraft spine already carries, i.e. the pre-cycle-8 behaviour for every
    airport whose roads carry no groundside geometry.

    R-a — LATERAL NODES ARE ROUTE-TRANSPARENT (lead ruling 2026-08-08, the
    direct application of the owner's 2026-07-30 "Reach follows centerlines":
    feasibility/reach follows TAXI CENTERLINES only).  A cross-section foot
    planted by ``lateral_spine_nodes`` is a sample of the TRANSVERSE law, not
    a route.  It is skipped here — never on-line, so never a chain member and
    never an endpoint of a ``spine_adj`` budget — which makes the arc-ordered
    on-line list, and therefore every route length this graph prices,
    IDENTICAL to the list the same layout without laterals would produce.
    That identity is the ruling stated as an invariant, and
    ``tests/test_route_transparent_laterals.py`` is its known-answer twin.

    THE MEASUREMENT THAT MADE IT LAW: ``SPINE_PERP_TOL_M`` is 1.0 m, and the
    wide-corridor class the lateral pass exists for is precisely an axis
    running ALONG a pavement edge — so its feet land within the tolerance,
    become spine nodes, and a corridor fed from both sides interleaves left
    and right feet in arc order into CROSS EDGES.  At HECA the
    station-densified restoration therefore shortened routes and shrank the
    reach band's route budgets until the build refused
    (``assert_no_final_band_inversion``: 1,655 of 10,220 band-covered nodes
    inverted, 49.400 m of anchor spread over a 47.723 m budget).  The
    transverse law and the route metric were sharing one graph; this is the
    line between them, drawn where the owner drew it."""
    items = list(G.pos.items())
    # R-a: the recorded cross-section feet, resolved into THIS call's node
    # space (never cached across node spaces — the rod-key lesson).  A
    # layout that planted none, or the flag OFF, leaves ``_lateral_nodes``
    # empty and every walk below is byte-identical to before.
    _lateral_nodes: set = set()
    if _FF.on("O4_FABRIC_RA_ROUTE_TRANSPARENT_LATERALS") and layout is not None:
        from .lateral_spine_nodes import lateral_foot_predicate
        _is_lat = lateral_foot_predicate(layout)
        if _is_lat is not None:
            _lateral_nodes = {i for (i, (x, y)) in items if _is_lat(x, y)}
            if _lateral_nodes:
                import O4_UI_Utils as _UI
                _UI.vprint(1,
                    f"  [global-spine] {icao}: R-a route-transparent "
                    f"laterals — {len(_lateral_nodes)} of {len(items)} "
                    f"geometry node(s) are cross-section feet "
                    f"({getattr(_is_lat, 'n_feet', 0)} foot(s) recorded, "
                    f"match radius {getattr(_is_lat, 'tol_m', 0):.2f} m); "
                    f"they mint no route-graph edge.")
    G.route_transparent_nodes = _lateral_nodes
    # Spatial prefilter (CYUL: the naive centerlines × nodes double loop was
    # 52 M ``_project`` calls / 140 s — 2,473 fragmented route pieces × 21 k
    # nodes).  Only nodes inside the centerline's tolerance-inflated bbox can
    # be on it; everything else skips the exact projection.
    node_tree = None
    try:
        from shapely.geometry import Point as _NPt, box as _nbox
        from shapely.strtree import STRtree as _NTree
        node_tree = _NTree([_NPt(x, y) for (_i, (x, y)) in items])
    except Exception:                                  # pragma: no cover
        node_tree = None
    _taxi_woven_pairs: set = set()
    # AMENDMENT 2: the road-family node set as a SET (the walk asks it per
    # pair), and the counter the census line reports.
    from .config import (
        SERVICE_BAND_AIRSIDE_EXCLUSION as _BAND_AIRSIDE_EXCLUSION)
    _road_node_set = set(road_nodes or ())
    _n_svc_airside_skipped = [0]
    _n_no_node = 0            # centerlines with NO node within the tolerance
    _n_one_node = 0           # ... with exactly one (a thinned region)
    _taxi_strung: set = set()  # every node the AIRCRAFT pass strung
    _svc_walked = 0            # service centerlines seen (the denominator)
    _svc_attach: set = set()   # service-strung nodes that are aircraft spine

    # REPORT-ONLY collector, DEFAULT OFF (``O4_DUMP_SERVICE_STRINGING``).
    # Nothing is computed for it on a default build — the flag is read once,
    # here, and every extra projection below sits inside ``if _diag``.
    # ``_DIAG_MARGIN_M`` widens the diagnostic's own node window past the
    # tolerance so NEAR-MISSES are visible (see ``_walk``).
    _diag = (({"centerlines": []}
              if os.environ.get("O4_DUMP_SERVICE_STRINGING") else None))

    def _walk(_ci, cl, tol, eligible, diag=False):
        """String ONE centerline; return its arc-ordered node list (``[]``
        when it contributed no string)."""
        nonlocal _n_no_node, _n_one_node
        if node_tree is not None:
            xs = [p[0] for p in cl.pts]
            ys = [p[1] for p in cl.pts]
            q = _nbox(min(xs) - tol, min(ys) - tol,
                      max(xs) + tol, max(ys) + tol)
            cand = [items[int(k)] for k in node_tree.query(q)]
        else:                                          # pragma: no cover
            cand = items
        on_line = []
        for (i, (x, y)) in cand:
            if eligible is not None and i not in eligible:
                continue
            if i in _lateral_nodes:
                continue          # R-a: a cross-section foot is not a route
            a, d, _ = _project(cl, x, y)
            if d <= tol:
                on_line.append((a, i))
        if diag:
            # THE NEAR-MISS WINDOW.  The production prefilter above inflates
            # the bbox by ``tol`` exactly, so a node just OUTSIDE the
            # tolerance is never even a candidate — and "a sliced-road node
            # sitting just past the tolerance" is precisely the recorded
            # suspect this instrument exists to test.  The diagnostic
            # therefore re-queries at ``tol + _DIAG_MARGIN_M`` and measures
            # every node in that window, eligible or not.  Separate loop, so
            # the production path above is untouched, not merely equivalent.
            _d_all = []
            if node_tree is not None:
                _wt = tol + _DIAG_MARGIN_M
                _wq = _nbox(min(xs) - _wt, min(ys) - _wt,
                            max(xs) + _wt, max(ys) + _wt)
                _wcand = [items[int(k)] for k in node_tree.query(_wq)]
            else:                                      # pragma: no cover
                _wcand = items
            for (i, (x, y)) in _wcand:
                _a, _d, _ = _project(cl, x, y)
                _d_all.append((_d, i, x, y,
                               (eligible is None or i in eligible)))
            _d_all.sort(key=lambda t: t[0])
            _in_tol = [t for t in _d_all if t[0] <= tol]
            _elig_in_tol = [t for t in _in_tol if t[4]]
            if len(on_line) >= 2:
                _cls = "strung"
            elif len(_elig_in_tol) == 1:
                _cls = "one_node"
            elif _in_tol and not _elig_in_tol:
                _cls = "ineligible_in_tol"
            elif not _d_all:
                _cls = "no_node_in_window"
            else:
                _cls = "no_candidate_in_tol"
            _diag["centerlines"].append({
                "ci": int(_ci),
                "is_service": bool(getattr(cl, "is_service", False)),
                "n_pts": len(cl.pts),
                "plan_len_m": round(sum(
                    math.hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(cl.pts, cl.pts[1:])), 3),
                "tol_m": float(tol),
                "n_candidates": len(_d_all),
                "n_in_tol": len(_in_tol),
                "n_eligible_in_tol": len(_elig_in_tol),
                "n_on_line": len(on_line),
                "min_d_any_m": (round(_d_all[0][0], 4) if _d_all else None),
                "min_d_eligible_m": (
                    round(min((t[0] for t in _d_all if t[4]), default=-1), 4)
                    if any(t[4] for t in _d_all) else None),
                "class": _cls,
                "nearest": [{"node": int(i), "d_m": round(d, 4),
                             "x": round(x, 3), "y": round(y, 3),
                             "eligible": bool(el)}
                            for (d, i, x, y, el) in _d_all[:5]],
            })
        if len(on_line) < 2:
            # No string from this way — counted, and said out loud in the
            # census line at the end of the walk.
            if on_line:
                _n_one_node += 1
            else:
                _n_no_node += 1
            return []
        on_line.sort(key=lambda t: t[0])
        # S1 level-1 authorship export (see ``centerline_chains``): the
        # arc-ordered on-line node list IS this centerline's authored
        # string.  Recorded here, inside the existing walk — no extra
        # pass, no extra projection.
        G.centerline_chains[_ci] = [i for (_a, i) in on_line]
        if cl.is_service:
            G.centerline_service.add(_ci)
        for (a0, i0), (a1, i1) in zip(on_line, on_line[1:]):
            if i0 == i1:
                continue
            if (cl.is_service and _BAND_AIRSIDE_EXCLUSION
                    and i0 not in _road_node_set and i1 not in _road_node_set):
                # AIRSIDE EXCLUSION AT THE POPULATION SOURCE (AMENDMENT 2,
                # Fable lead 2026-08-12b; the law this docstring already
                # states: "a road may never sweep an unrelated apron vertex
                # into a spine chain at its 8 % cap — but it MAY adopt the
                # one airside node it genuinely meets, and that node is the
                # MOUTH").
                #
                # A corridor registered END-TO-END (the 2026-08-12b
                # one-law-object ruling) runs across apron pavement, so its
                # walk strings MANY airside nodes, not one, and linked
                # CONSECUTIVE PAIRS OF THEM into ``spine_adj`` at the road
                # cap.  Every consumer of the one graph then saw them: the
                # reach band as pairs to exclude (measured −65 airside rows
                # when the exclusion was lifted) and the profile solve as
                # law edges priced at 8 % between two apron nodes.  A
                # groundside corridor may not alter airside feasibility
                # inputs, so the pair is never woven — once, here, at the
                # single population source, rather than in each consumer.
                # The MOUTH survives by construction: one end of a mouth
                # pair is a road-family node.
                _n_svc_airside_skipped[0] += 1
                continue
            gap = abs(a1 - a0)
            d = _dist(G.pos.get(i0), G.pos.get(i1))
            # Per-segment cap at the midpoint between the two on-line nodes (a
            # route may change width along its length).
            budget = cl.cap_at(0.5 * (a0 + a1)) * max(gap, d, 1e-3)
            _spine_link(G.spine_adj, i0, i1, budget)
            # Reachability exclusion bookkeeping (owner ruling 2026-07-29)
            # — see ``UnifiedGraph.service_spine_pairs``.
            _pair = (i0, i1) if i0 < i1 else (i1, i0)
            if cl.is_service:
                G.service_spine_pairs.add(_pair)
            else:
                _taxi_woven_pairs.add(_pair)
        return [i for (_a, i) in on_line]

    # ── PASS 1: THE AIRCRAFT SPINE (unchanged rule, every node) ──────────
    for _ci, cl in enumerate(ctx.centerlines):
        if not cl.is_service:
            _taxi_strung.update(_walk(_ci, cl, SPINE_PERP_TOL_M, None))
    # ── PASS 2: THE SERVICE SPINE (its own tolerance, road-family nodes
    # plus the aircraft spine it attaches to — the MOUTH) ────────────────
    _svc_eligible = set(road_nodes or ()) | _taxi_strung
    for _ci, cl in enumerate(ctx.centerlines):
        if not cl.is_service:
            continue
        _svc_walked += 1
        _svc_attach.update(
            i for i in _walk(_ci, cl, SERVICE_SPINE_PERP_TOL_M, _svc_eligible,
                             diag=(_diag is not None))
            if i in _taxi_strung)
    # A pair ALSO woven by a taxi centerline (a road crossing a taxi
    # route's nodes) is a genuine taxi edge — the service tag must not
    # remove it from reachability.
    _n_svc_woven_out = len(G.service_spine_pairs & _taxi_woven_pairs)
    G.service_spine_pairs -= _taxi_woven_pairs
    if _diag is not None:
        _diag["service_centerlines_walked"] = _svc_walked
        _diag["service_centerlines_strung"] = len(G.centerline_service)
        _diag["service_spine_pairs"] = len(G.service_spine_pairs)
        _diag["aircraft_spine_attachments"] = len(_svc_attach)
        _diag["eligible_nodes"] = len(_svc_eligible)
        _diag["road_family_nodes"] = len(set(road_nodes or ()))
        _diag["taxi_strung_nodes"] = len(_taxi_strung)
        _diag["graph_nodes"] = len(items)
        G._service_stringing_diag = _diag
    # ── spine-drop census (hygiene 2026-07-31) ──────────────────────────
    G.spine_centerlines = len(ctx.centerlines)
    G.spine_no_string = _n_no_node + _n_one_node
    G.spine_no_string_zero = _n_no_node
    if G.spine_centerlines:
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [global-spine] {icao}: {G.spine_no_string} of "
            f"{G.spine_centerlines} centerline(s) contributed no string "
            f"({_n_no_node} with no geometry node within "
            f"{SPINE_PERP_TOL_M:.1f} m, {_n_one_node} with one).")
        # THE SERVICE HALF, counted where it is decided (cycle 8).  The
        # ONE-graph round's mouths are the endpoints of these pairs, so
        # "how many service pairs are there" is a load-bearing number and
        # it was never reported: a build with zero of them has no mouths
        # at all, and the groundside band is then fed only by the airside
        # nodes it can see.  ``woven_out`` is the taxi-woven subtraction
        # (a road crossing a taxi route's nodes is a genuine taxi edge).
        _svc_cl = len(G.centerline_service)
        G.spine_service_centerlines = _svc_walked
        G.spine_service_attachments = len(_svc_attach)
        _UI.vprint(1,
            f"  [global-spine] {icao}: {_svc_cl} of {_svc_walked} service "
            f"centerline(s) strung at the {SERVICE_SPINE_PERP_TOL_M:.1f} m "
            f"service tolerance, {len(G.service_spine_pairs)} service spine "
            f"pair(s) after the taxi-woven subtraction ({_n_svc_woven_out} "
            f"pair(s) removed as taxi-woven), {len(_svc_attach)} "
            f"attachment(s) to the aircraft spine — the MOUTH candidates "
            f"(eligible nodes: {len(_svc_eligible)}; source "
            f"{getattr(ctx, 'service_source', '?')}, "
            f"{getattr(ctx, 'service_length_m', 0.0):,.0f} m of road; "
            f"{_n_svc_airside_skipped[0]} airside-to-airside service pair(s) "
            f"NOT woven — a groundside corridor may not alter airside "
            f"feasibility inputs)")


def _dist(pa, pb):
    if pa is None or pb is None:
        return 1e-3
    return math.hypot(pa[0] - pb[0], pa[1] - pb[1])


def _spine_link(spine_adj, a, b, budget):
    spine_adj.setdefault(a, [])
    spine_adj.setdefault(b, [])
    if all(j != b for (j, _w) in spine_adj[a]):
        spine_adj[a].append((b, budget))
    if all(j != a for (j, _w) in spine_adj[b]):
        spine_adj[b].append((a, budget))


def _runway_anchors(layout, G, bucket_to_idx):
    """Record ``{geometry_node_idx: local_runway_elev}`` for every node where a
    taxi centerline joins a runway (mirrors the validator's runway-join check).
    The runway is the single hard anchor; this is what the spine solve pins to."""
    from shapely.geometry import Point
    from .layout import ROLE_RUNWAY, ROLE_RUNWAY_CROSSING
    from .pavement.runways import _sample_runway_segment_elev
    from .config import taxi_grade_cap_for_letter

    import os
    cps = layout.canonical_points
    # (``RUNWAY_CONTACT_M`` is applied inside ``GL.runway_join_contacts``.)
    _NEAR_M = GL.RUNWAY_JOIN_NEAR_M
    _spine_edge_anchor = (
        os.environ.get("O4_RUNWAY_CONTACT_ANCHOR", "1") == "1")
    # (``O4_RUNWAY_EDGE_CONTACT`` is read inside ``GL.runway_join_contacts``,
    # so every consumer of the join set — this one and the runway profile
    # seeder — agrees on where the contact is.)
    # ANCHOR TARGET SET (user 2026-07-16, KBNA 13/31 defect H): include the
    # ROLE_RUNWAY_CROSSING slab pieces alongside the true runways.  A taxi /
    # junction join that TERMINATES on the crossing slab (which replaced the
    # runway surface where two runways intersect) finds no ROLE_RUNWAY within
    # RUNWAY_CONTACT_M, so it got no runway anchor and stepped off the slab
    # edge (KBNA 13/31: junction 376 stepped 0.31 m vs the crossing slab
    # edge).  The slab is runway-derived surface carrying per-vertex node
    # altitudes, so ``_sample_runway_segment_elev`` reads its edge value at
    # the contact exactly as for a runway.  Gate O4_RUNWAY_CROSSING_ANCHOR=0
    # reverts to true-runway-only targets.
    _crossing_anchor = (
        os.environ.get("O4_RUNWAY_CROSSING_ANCHOR", "1") == "1")
    _anchor_roles = ((ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)
                     if _crossing_anchor else (ROLE_RUNWAY,))
    runways = [s for s in layout.shapes
               if s.role in _anchor_roles and s.polygon is not None
               and not s.polygon.is_empty]
    if not runways:
        return
    # Candidate nodes = EVERY emitted non-runway vertex (the SAME set the
    # validator's runway-join picks its nearest node from — including
    # runway_crossing nodes), so we anchor the exact node it checks.  Each is
    # mapped to its geometry index; a node off the solve graph is skipped.
    nx = []
    seen = set()
    for s in layout.shapes:
        if (s.role == ROLE_RUNWAY or s.polygon is None or s.polygon.is_empty):
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is None or i in seen:
                continue
            seen.add(i)
            nx.append((i, (x, y)))
            G.pos.setdefault(i, (x, y))
    if not nx:
        return
    contact_endpoints = []   # centerline endpoints that TERMINATE at a runway
    # WHERE A JOIN IS — resolved by the ONE shared authority
    # (``grade_law.runway_join_contacts``), which the runway PROFILE SEEDER also
    # calls so the station it anchors at the law line and the node anchored here
    # are the same join (docs/specs/cycle4-anchor-law-spec.md).  The contact NODE
    # sits where the centerline meets the runway EDGE, not at the deep-interior
    # centerline endpoint (a taxi route joins the runway CENTERLINE, ~half-width
    # inside on a wide runway), so the nearest-node search reaches the emitted
    # taxiway↔runway node.  O4_RUNWAY_EDGE_CONTACT=0 reverts to the endpoint.
    for (rwy, (cx, cy), _endpoint) in GL.runway_join_contacts(
            getattr(layout, "apt_taxi_centerlines", []) or [], runways):
        re = _sample_runway_segment_elev(rwy, cx, cy)
        if re is None:
            continue
        sample_x, sample_y = cx, cy
        contact_endpoints.append((cx, cy))
        # nearest graph node to the contact = the spine node that anchors
        best_i, best_d2 = None, _NEAR_M * _NEAR_M
        for (i, (x, y)) in nx:
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 < best_d2:
                best_d2, best_i = d2, i
        if best_i is not None:
            # Runway DE-SEGMENTATION (O4_RUNWAY_SINGLE_POLY): on a
            # single-poly ring, sample the runway surface at the
            # ANCHORED NODE's own boundary projection instead of the
            # contact's station.  The legacy per-piece sampler
            # effectively quantised the anchor onto the local piece's
            # corner values, keeping a near-edge anchor consistent
            # with the welded edge vertex beside it; the ring's
            # whole-profile interpolation returns the value 5-15 m
            # up-axis at the contact, and pinning THAT on a node
            # 2.5 m from the weld is unlawful over the junction's
            # within-shape budget (HECA 05R: 9 cm over 2.51 m =
            # 3.57 %).  The node-projection value satisfies both
            # readers by construction: it differs from the contact
            # sample by ≤ profile-grade × d(contact, node) — inside
            # the validator's join budget — and from any welded edge
            # vertex by ≤ profile-grade × their separation.
            if getattr(rwy, "from_single_poly", False):
                node_x, node_y = G.pos.get(best_i, (cx, cy))
                try:
                    boundary = rwy.polygon.exterior
                    q = boundary.interpolate(
                        boundary.project(Point(node_x, node_y)))
                    re_node = _sample_runway_segment_elev(
                        rwy, q.x, q.y)
                except _GEOM_EXC:
                    re_node = None
                if re_node is not None:
                    re = re_node
                    sample_x, sample_y = q.x, q.y
            if os.environ.get("O4_DESEG_DEBUG") == "1":
                _la, _lo = layout.m_to_ll(*G.pos.get(best_i, (cx, cy)))
                print(f"  [deseg-dbg] runway_anchor node@{_la:.7f},"
                      f"{_lo:.7f} = {float(re):.3f} "
                      f"(contact {cx:.1f},{cy:.1f})")
            G.runway_anchor[best_i] = float(re)
            G.runway_anchor_sample[best_i] = (
                float(sample_x), float(sample_y), rwy)

    # ── SPINE nodes ON a runway edge where a route TERMINATES (user 2026-06-28) ─
    # A taxiway that ENDS at the runway already has its contact materialised as a
    # SHARED node: the runway sub-rect corner, the abutting junction vertex and
    # the taxi SPINE node are welded to ONE canonical point on the runway edge
    # (the segmenter cut it; ``_unify_airside_geometry`` welded it).  That node IS
    # the taxiway↔runway contact and must sit at the runway surface — yet the
    # endpoint search above misses it when the taxiway's rect ends short of the
    # centerline's runway-edge endpoint (CYXY taxiway A: the centerline endpoint
    # is the runway-edge MIDLINE at (-345,914), but the welded spine/runway nodes
    # are its two SIDE contacts 22.6 m away — past _NEAR_M=18 — so A was left
    # reach-detoured ~700 m and its served building over-credited 706 vs ~699).
    # So anchor every spine node that coincides with a runway vertex AND sits near
    # a TERMINATING contact endpoint (within _EDGE_REACH_M) — the route ends at the
    # runway there, exactly like a junction pavement edge.  The endpoint gate
    # excludes a taxiway that merely CROSSES / runs ALONG a runway mid-centerline
    # (SPJC taxiway F at (2136,-1677), 36 m from F's nearest endpoint) — those are
    # handled by the runway-crossing reconciliation, and hard-anchoring them
    # over-constrains the adjacent junction (a 0.16 m floor flag).  ``setdefault``
    # keeps any centerline-based anchor set above.  Gate O4_RUNWAY_CONTACT_ANCHOR=0.
    _EDGE_REACH_M = 30.0
    if _spine_edge_anchor and contact_endpoints:
        er2 = _EDGE_REACH_M * _EDGE_REACH_M
        for s in runways:
            for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
                i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                if i is None or i not in G.spine_adj or i in G.runway_anchor:
                    continue
                if all((x - ex) ** 2 + (y - ey) ** 2 > er2
                       for (ex, ey) in contact_endpoints):
                    continue
                re = _sample_runway_segment_elev(s, x, y)
                if re is not None:
                    if os.environ.get("O4_DESEG_DEBUG") == "1":
                        _la, _lo = layout.m_to_ll(x, y)
                        print(f"  [deseg-dbg] spine-edge anchor "
                              f"node@{_la:.7f},{_lo:.7f} = {float(re):.3f}")
                    G.runway_anchor[i] = float(re)
                    G.runway_anchor_sample[i] = (
                        float(x), float(y), s)
