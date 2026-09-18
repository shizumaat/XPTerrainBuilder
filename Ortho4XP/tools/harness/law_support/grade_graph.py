"""The CONSTRAINT GENERATOR (shape / plane constraints, route and spine metrics) the census prices within-shape and cross-shape pairs with.

COPIED from ``grade_graph.py`` on 2026-09-17 (lane ``v1retire`` round 1, ruling (d)
of the stage-B brief: "the census stays engine-neutral BY IMPLEMENTATION").
`tools/check_grade.py` priced v2 patches with law machinery that lived in
modules the v1 deletion takes; what it USES is copied here ONCE, verbatim, and
the census reads it from the harness.  Values that are law live in
``auto_patch/config.py`` (KEEP) or ``auto_patch_v2/law/*.toml`` and are
IMPORTED, never re-spelled.

Do not edit to change behaviour: this is a transcription, and the acceptance
was a census A/B on the same HECA patch bytes reading IDENTICAL.
"""

from __future__ import annotations

from . import grade_law as GL
from .contiguity import SERVICE_AXIS_PRICED_ROLES
from .contiguity import cap_at as _cap_at
from .corridor import spine_corridor_cover
from .roles import GROUNDSIDE_ROLES
from .roles import SHARED_VERTEX_TOL_M
from array import array
from auto_patch.config import ANISO_EDGES
from auto_patch.config import APRON_BACK_EDGE_GRADE
from auto_patch.config import APRON_MAX_GRADE
from auto_patch.config import APRON_TAXI_BLEND
from auto_patch.config import APRON_TAXI_TRANSITION_M
from auto_patch.config import BUILDING_REACH_CORRIDOR_M as _BUILDING_REACH_CORRIDOR_M
from auto_patch.config import FAN_RAMP_CAP
from auto_patch.config import GRADE_VISIBILITY_BUFFER_M as _VIS_BUF
from auto_patch.config import JUNCTION_MESH_CONSTRAINTS
from auto_patch.config import ROAD_PATH_METRIC
from auto_patch.config import SERVICE_ROAD_MAX_GRADE
from auto_patch.config import SERVICE_ROAD_MAX_GRADE as _SVC_CAP_BL
from auto_patch.config import SERVICE_ROAD_WIDTH_M
from auto_patch.config import SVC_SPINE_FIRST
from auto_patch.config import TAXI_MAX_GRADE
from auto_patch.config import taxi_grade_cap_for_letter
from auto_patch.config import transverse_cap_for_longitudinal_cap as _transverse_cap_for_longitudinal_cap
from dataclasses import dataclass, field
from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString
from shapely.geometry import LineString as _CLs
from shapely.geometry import LineString as _IzLine
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as _CoPt
from shapely.geometry import Point as _IzPt
from shapely.geometry import Point as _P
from shapely.geometry import Point as _Pt
from shapely.geometry import Point as _RPt
from shapely.geometry import Point as _RPt2
from shapely.geometry import Polygon as _IzPoly
from shapely.geometry import Polygon as _Poly
from shapely.ops import triangulate as _tri
from shapely.prepared import prep
from shapely.prepared import prep as _cc_prep
from shapely.prepared import prep as _iz_prep
from shapely.strtree import STRtree
from typing import Callable, Hashable, Optional, Sequence
import copy as _copy
import heapq
import math
import math as _m
import numpy as _np
import os
import shapely as _shapely


_GEOM_EXC = (ValueError, GEOSException, TopologicalError)


APRON_ROLE = "apron"


JUNCTION_ROLES = GL.JUNCTION_ROLES


SOFT_VISIBILITY_ROLES = ((APRON_ROLE,) + JUNCTION_ROLES
                         + (("service_road",) if SVC_SPINE_FIRST else ()))


SPINE_PERP_TOL_M = 1.0


SERVICE_SPINE_PERP_TOL_M = SERVICE_ROAD_WIDTH_M / 2.0 + SPINE_PERP_TOL_M


APRON_ROUTE_CONTACT = os.environ.get("O4_APRON_ROUTE_CONTACT", "1") == "1"


_ROUTE_CONTACT_TOL_M = 0.5


ROUTE_METRIC_PAIRS = os.environ.get("O4_ROUTE_METRIC_PAIRS", "1") == "1"


PAIR_CHORD_LOCAL_M = float(os.environ.get("O4_PAIR_CHORD_LOCAL_M", "120"))


ROUTE_LEG_EXACT = os.environ.get("O4_ROUTE_LEG_EXACT", "1") == "1"


PAIR_BUDGET_PRUNE_M = float(os.environ.get("O4_PAIR_BUDGET_PRUNE_M", "150"))


SPINE_FRAME_PAIRS = os.environ.get("O4_SPINE_FRAME_PAIRS", "1") == "1"


APRON_CHORD_ANCHOR_TARGET = (
    os.environ.get("O4_APRON_CHORD_ANCHOR_TARGET", "1") != "0")


ANCHOR_KIND_SPINE = "spine"


ANCHOR_KIND_PAD = "pad"


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
    # APRON SPINE (owner ruling RULINGS 2026-08-25h): this piece runs
    # INSIDE or ALONG an apron, so the ruling makes it THE APRON'S SPINE
    # at the apron's cap.  It stays ``is_service`` — the reachability
    # band must still refuse to justify a ceiling through a truck route
    # (§2.2, REACH_NO_SERVICE_SPINES) — but the GRADING scaffold reads it
    # like a taxi centerline, which is the whole of §2.1.
    #
    # TWO FLAGS BECAUSE THERE ARE TWO GUARDS, and they were never the
    # same question: ``is_service`` gates the BAND (reachability), and
    # ``_reads_service_spines`` gates SPINE MEMBERSHIP (grading).  The
    # ruling moves the second for this population and leaves the first
    # exactly where it is.
    is_apron_spine: bool = False

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
    #: THE FACE'S HOLES (RULINGS 2026-09-05ae(1), lane v2fix288): open rings
    #: in the same frame; a non-adjacent chord crossing one is not a
    #: surface path (``_visibility_predicate``).  The v1 engine leaves it
    #: empty (its layout carries no hole geometry here — a stricter
    #: superset); the census fills it from the v2 sidecar ``face_holes``.
    holes: list = field(default_factory=list)
    fan_ramp_zone: bool = False
    adopts_taxi_grade: bool = False
    adopted_taxi_letter: str | None = None
    lateral_cap: float | None = None
    #: Amendment 2 clause 1 — the PER-STATION cap vector, carried from
    #: ``BuiltShape.station_cap_vector`` so a pair prices at the cap of
    #: the stations its OWN endpoints stand in, not at one ring-wide
    #: scalar.  Empty ⇒ the scalar path, byte-identical.
    station_cap_vector: list = field(default_factory=list)
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
    #: INDEX-PARALLEL to :attr:`edges`: True where the pair is a PAD
    #: FRONTAGE CHORD (``grade_law.is_frontage_chord`` on the very
    #: ``PairContext`` ``classify_pair`` judged) — the 2026-08-25
    #: chord-anchor law's own population.  Recorded at MINT for the third
    #: time and the same reason the three flags above are: the UNIFIED
    #: LAW BAND (owner ruling RULINGS 2026-08-27, spec
    #: ``docs/specs/unified-law-band-spec.md`` §1.1a) needs exactly this
    #: population in its edge iterator, and re-deriving "which apron
    #: pairs are frontage chords" from cap values downstream would be a
    #: guess — the 1 % stand cap is reached by several other routes.
    #: This is the population, from its own builder, with its own caps.
    edge_frontage_chord: list[bool] = field(default_factory=list)
    #: APRON ring keys inside the RUNWAY STRIP footprint (spec AMENDMENT
    #: A4.2).  Those pairs are SKIPPED by the law, so the node never
    #: appears on an edge and the seniority partition — whose domain is
    #: built from edges — could not see it at all.  Recording it HERE, at
    #: the same place the flags are computed for the law, is what lets
    #: ``grade_law.apron_node_seniority`` report ``excluded`` instead of
    #: silently dropping the node (owner ruling RULINGS 2026-08-21d,
    #: wired 2026-08-24).
    strip_excluded: set = field(default_factory=set)


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
    from auto_patch.config import BUILDING_REACH_CORRIDOR_M as _BUILDING_REACH_CORRIDOR_M
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
        from .corridor import (
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


def _visibility_predicate(ring: list[tuple[float, float]], holes=()):
    """Return ``vis(xa,ya,xb,yb)->bool``: True iff the chord stays inside the
    ring grown by ``_VIS_BUF``.  ``None`` if shapely is unavailable / the polygon
    is degenerate (caller falls back to plain all-pair).

    ``holes`` (RULINGS 2026-09-05ae(1)): the face's holes as open rings —
    a chord crossing a hole (a road, a building standing inside the
    apron) leaves the pavement and is not a pair; the ring edges and the
    inside chords carry the apron law around the obstacle.  Measured HECA
    43d50a53: apron pav132's 585–770 m frontage chords through the hole
    where a road and a building stand carried 21 km of the relaxation's
    26.5 km of relief.  A hole narrower than ``2 × _VIS_BUF`` closes
    under the buffer — a sliver, never a road.

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
        poly = Polygon(ring, [list(h) for h in (holes or ()) if len(h) >= 3])
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
    from .roles import GROUNDSIDE_ROLES
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
        _cl_m = ctx.centerlines[ci]
        if (not svc_ok and _cl_m.is_service
                and not getattr(_cl_m, "is_apron_spine", False)):
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
            if (not _svc_ok and cl.is_service
                    and not getattr(cl, "is_apron_spine", False)):
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


def _station_cap_at(shape, x, y, fallback):
    """The PER-STATION cap governing ``(x, y)`` on ``shape`` (Amendment 2
    clause 1), or ``fallback`` when the shape carries no vector.

    ONE derivation, read through THE law's own accessor
    (``lateral_contiguity.cap_at``) — never a second nearest-station
    convention here.
    """
    vec = getattr(shape, "station_cap_vector", None)
    if not vec:
        return fallback
    from .contiguity import cap_at as _cap_at
    c = _cap_at(vec, float(x), float(y), None)
    return fallback if c is None else min(float(fallback), float(c))


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
        from .roles import SHARED_VERTEX_TOL_M
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


def shape_constraints(shape: GradeShape, ctx: GradeContext,
                      ring_only: bool = False,
                      road_path_metric: bool = False) -> ShapeConstraints:
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
    # Amendment 2 clause 1's vector, read once per shape.
    station_vec = (list(getattr(shape, "station_cap_vector", None) or ())
                   if shape.role in GL.ROAD_ROLES else [])
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
    vis = None if ring_only else _visibility_predicate(ring, shape.holes)
    # ── THE ROAD'S OWN PATH METRIC (owner ruling 2026-08-28, round-5b
    # spec Amendment 1 clause 1) ─────────────────────────────────────
    # A road-family ring's pairs are priced along the RING WALK, not the
    # straight line across the loop.  Computed ONCE per shape here, in
    # THE function both readers of the within-shape pair set call —
    # ``check_grade.iter_shape_grade_constraints`` (the census) and
    # ``solver_primitives._build_shape_constraints`` (the solve) — so a
    # road pair cannot be priced at two distances by two instruments.
    # ``O4_ROAD_PATH_METRIC=0`` restores the euclidean chord exactly.
    # SCOPED TO THE TWO READERS THE RULING NAMES — the CENSUS and the
    # emitter's chord LIMITER — and NOT to the solve graph, which is a
    # THIRD reader of this function.  That scope is MEASURED (this lane,
    # HECA): with the metric in the solve as well, the road's own law
    # change travelled through the ONE solve and moved 1,756 SOLVE-OWNED
    # airside nodes by up to 2.07 m — 1,516 of them apron nodes with no
    # road contact at all.  Airside is king: the solve keeps the
    # euclidean chord, which is the STRICTER of the two (a walk is never
    # shorter), so it can never mint a census row the walk would forgive.
    _road_cum = _road_total = None
    if (road_path_metric and ROAD_PATH_METRIC
            and shape.role in GL.ROAD_ROLES):
        _road_cum, _road_total = GL.ring_path_cumulative(ring)
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
        from auto_patch.config import SERVICE_ROAD_MAX_GRADE as _SVC_CAP_BL
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
            _xsec_pair = (road_axis is not None
                          and GL.pair_is_transverse(road_axis,
                                                    xj - xi, yj - yi))
            # Amendment 2 clause 1 — THE PER-STATION CAP.  A road pair
            # prices at the STRICTER of the caps governing its own two
            # endpoints, so a stretch alongside an apron carries the
            # apron's 1 % over exactly its own stations while the same
            # ring's free stretch keeps SERVICE_ROAD_MAX_GRADE.  One
            # ring, two caps, which is what "the cap lives at the
            # station" means.  Empty vector ⇒ the ring-wide scalar,
            # byte-identical.
            _st_cap = None
            if station_vec:
                _st_cap = min(
                    _station_cap_at(shape, xi, yi, body_cap),
                    _station_cap_at(shape, xj, yj, body_cap))
            if _road_cum is not None and not _xsec_pair:
                # Amendment 1 clause 1 — never TIGHTER than the chord
                # (a ring walk is >= the chord by construction), so this
                # only ever relaxes, exactly as the airside route metric
                # does in ``_route_leg_floor``.
                #
                # SCOPED TO THE LONGITUDINAL PAIRS, and that scope is
                # MEASURED (this lane, CYXY): applied to the whole ring it
                # also relaxed the DIAGONAL cross-section pairs, whose
                # walk is long, and the road CROSS-SECTION law (RULINGS
                # 2026-08-25g) rides on exactly those — CYXY gained 46
                # road_cross_section and 102 transverse rows.  A
                # cross-section is measured ACROSS the road by
                # definition, so its distance is the chord; the walk is
                # the metric of travel ALONG the road, which is what the
                # profile solves in.  ONE predicate decides which is
                # which — ``GL.pair_is_transverse`` against THE ring axis
                # the cross-section law itself uses.
                d = GL.road_pair_distance(ring, _road_cum, _road_total,
                                          i, j, d)
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
                spine_caps=spine_caps,
                body_cap=(body_cap if _st_cap is None else _st_cap),
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
                transverse_road=_xsec_pair)
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
            # THE SAME PairContext, a third time (unified law band §1.1a).
            sc.edge_frontage_chord.append(GL.is_frontage_chord(_pc))

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
            # Same construction rule as the two lists above: this path is
            # the PLANE (runway) one and its pairs carry no building
            # endpoint, so the answer is always False — but the lists stay
            # the same length BY CONSTRUCTION rather than by luck.
            sc.edge_frontage_chord.append(GL.is_frontage_chord(_pc))
    return sc

