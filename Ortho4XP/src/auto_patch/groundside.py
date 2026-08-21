"""Groundside (curbside / drop-off / parking) pavement emit.

Pulls roads tagged as airport-access or service highway out of the
OSM cache, lifts them off the DEM, and emits matching curbside
ribbon polygons.  Then prunes orphan junction polygons that are
fully contained inside (or touch only) the groundside ribbon —
those are road-island fragments that don't belong with airside
pavement.

Public API (leading-underscore preserved for backward compatibility
with internal callers in ``O4_Airport_Pavement_Builder``):

    _emit_groundside_pavement_dem
    _reclassify_groundside_orphan_junctions
"""
from __future__ import annotations

import json
import math
import os as _os
from typing import Dict, List, Optional, Sequence, Set, Tuple

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import (
    LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon,
    box)
from shapely.ops import linemerge, nearest_points, snap, unary_union

from .layout import (
    AEROWAY_FOR_ROLE,
    BuiltShape,
    PavementLayout,
    R_EARTH,
    ROLE_APRON,
    ROLE_BOUNDARY,
    ROLE_CROSS_CONNECTOR,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_SECONDARY_PARALLEL,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_STUB,
    ROLE_BUILDING,
    ROLE_RETAINING_WALL,
    ROLE_TUNNEL_RAMP,
    SHARED_VERTEX_TOL_M,
    authority_rank,
)
from .pavement.vertices import _snap_polygon_vertices_to_rect_corners
from .elevation import _sample_dem, _resample_node_altitudes_nn
# Groundside ramp-grade cap (rise/run, user 2026-05-22) — single source of
# truth in ``config``; groundside follows the DEM but is graded to this
# cap so steep terrain becomes a navigable car/parking surface.
#
# THE LAW AND THE SHAPING ARE TWO NUMBERS, DELIBERATELY (owner
# 2026-08-12 + lead ruling on the measurement).  The LAW — what the
# validator adjudicates a lot against — is the ROAD LIMIT, and it lives
# in ``config.ROLE_GRADE_LIMITS["groundside_pavement"]``
# (= ``GROUNDSIDE_PAVEMENT_MAX_GRADE``, an alias of the road cap).  The
# SHAPING every limiter in this module applies stays at
# ``GROUNDSIDE_MAX_GRADE`` (5 %), BY MEASUREMENT: pointing the limiters
# at the cap made lots ride exactly ON it, and the emitted 2-decimal
# quantization over short chords then tipped whole families of pairs
# 0.08-2.36 pp past it — CYXY within_shape 4 → 62 on ONE lot (way
# -10268), KMCI 420 → 490, +58/+75 adjudicated, while the road-stub
# class it was meant to clear did not move (transverse Δ0 both
# airports).  Shaping BELOW the law is the margin that makes the law
# reachable; it is not a second law, and a limiter re-pointed at the
# cap without a margin re-opens that class (twin:
# tests/test_owner_constants_round.TestTheLimitersRideTheRoadCap).
from .config import GROUNDSIDE_MAX_GRADE

# Narrow exception tuple for shapely / numeric-geometry failure
# modes.  Programming errors propagate so they surface immediately.
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)


__all__ = [
    "_absorb_apron_enclosed_groundside",
    "merge_small_apron_fragments",
    "_reclassify_groundside_orphan_junctions",
    "_emit_groundside_pavement_dem",
    "_separate_groundside_from_airside",
    "_merge_touching_groundside",
    "consolidate_full_width_service_corridors",
]


def dem_world_label(dem) -> str:
    """The WORLD stamp for a DEM object: class + its own ``source_path``.

    The instruments in this module are ENTIRELY about whether a value is
    DEM-derived, which makes the DEM world their most load-bearing frame
    (RULINGS 2026-08-06 binding point 3).  ``provenance.dem_label`` cannot
    supply it on its own — a ``ConstantDEM`` oracle world and a real
    inset-less DEM both render ``base RAW (no inset baked)``; the class
    name plus ``<constant-dem 10000 m>`` tells them apart."""
    if dem is None:
        return "None (no DEM object)"
    src = getattr(dem, "source_path", None)
    return f"{type(dem).__name__}:{src if src else '?'}"


def _dem_sampler(layout, dem, tile_lat, tile_lon):
    """Return ``_dem_at(x, y) -> Optional[float]`` sampling ``dem`` in
    layout-metre space (anchored at ``layout.anchor``).

    THE ONE SEAM every groundside DEM read goes through, so it is also
    where the world gets stamped for ``report_groundside_law_seat`` —
    report-only, a ``set`` so a build that sampled two different DEMs says
    so instead of quietly reporting the last one."""
    try:
        seen = getattr(layout, "_gs_dem_worlds", None)
        if seen is None:
            seen = set()
            layout._gs_dem_worlds = seen
        seen.add(dem_world_label(dem))
    except (AttributeError, TypeError):                # pragma: no cover
        pass
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    R = R_EARTH

    def _dem_at(x: float, y: float) -> Optional[float]:
        try:
            lat = lat0 + math.degrees(y / R)
            lon = lon0 + math.degrees(x / (R * cos0))
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None
    return _dem_at


# Douglas-Peucker tolerance for the groundside simplify pass (user
# 2026-05-22): drop over-resolved boundary detail (sub-meter apt.dat /
# DSF curve steps) before the densify+per-vertex-DEM emit, so groundside
# polygons don't carry needless node density into the patch.
GROUNDSIDE_SIMPLIFY_TOL_M = 2.0

# Width (m) of the corridor cut that opens an enclosed hole to the polygon
# exterior (see ``_open_polygon_holes``).  Wide enough to survive the 2 m
# groundside simplify without collapsing (which would re-close the hole),
# narrow enough that the driveway-like notch loses negligible lot area.
_HOLE_OPEN_CUT_WIDTH_M = 3.0


def _open_polygon_holes(p, _depth: int = 0):
    """Return ``p`` re-expressed with NO interior ring, as a list of
    hole-free ``Polygon`` pieces.

    The OSM emitter (``layout.to_osm``) writes only a shape's EXTERIOR
    ring — interior rings are dropped for X-Plane patch compatibility.  A
    groundside polygon that ENCLOSES a building (or any airside shape the
    separation pass subtracted out) therefore re-covers that footprint
    once emitted, producing a 100 %-contained self-overlap (SPJC: building
    #31 inside groundside #455).  Opening the hole here — cutting a thin
    mitre corridor from the hole to the nearest exterior edge so the
    enclosed void becomes an open notch (a simply-connected C-shape) —
    keeps the void real in BOTH the shapely geometry and the emitted
    exterior ring.

    ``[p]`` unchanged when ``p`` already has no holes; ``[]`` if ``p`` is
    unusable.  Usually one piece — the nearest-edge cut reaches only just
    past the exterior on the near side, so the far-side material keeps the
    ring connected.
    """
    if p is None or p.is_empty or p.geom_type != "Polygon":
        return []
    if not p.interiors or _depth > 4:
        return [p]
    cutters = []
    ext = p.exterior
    for interior in p.interiors:
        try:
            hole_ring = LineString(interior)
            a, b = nearest_points(hole_ring, ext)   # a on hole, b on ext
        except _GEOM_EXC:
            continue
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        if d < 1e-9:
            # Hole boundary touches the exterior — push the corridor
            # radially outward from the hole centroid instead.
            try:
                cx, cy = Polygon(interior).representative_point().coords[0]
            except _GEOM_EXC:
                continue
            dx, dy = a.x - cx, a.y - cy
            d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        start = (a.x - ux * 0.5, a.y - uy * 0.5)     # inside the hole
        end = (b.x + ux * 0.5, b.y + uy * 0.5)       # just past exterior
        try:
            cutters.append(LineString([start, end]).buffer(
                _HOLE_OPEN_CUT_WIDTH_M / 2.0,
                cap_style=2, join_style=2))
        except _GEOM_EXC:
            continue
    if not cutters:
        return [p]
    try:
        opened = p.difference(unary_union(cutters))
    except _GEOM_EXC:
        return [p]
    if opened is None or opened.is_empty:
        return [p]
    pieces: List[Polygon] = []
    parts = ([opened] if opened.geom_type == "Polygon"
             else list(getattr(opened, "geoms", [])))
    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        if part.interiors:
            pieces.extend(_open_polygon_holes(part, _depth + 1))
        else:
            pieces.append(part)
    return pieces or [p]


def _grade_limit_ring(coords, alts, max_grade, iters=None, pinned=None):
    """Relax per-vertex altitudes so no adjacent ring edge exceeds
    ``max_grade`` (rise/run).  Each pass pulls the steeper end of a
    violating edge toward the other by half the excess; iterates to a
    ≤max_grade profile (ramp-like).  Modifies and returns ``alts``.

    A perturbation propagates ~one vertex per pass in each direction, so
    convergence needs O(n) passes — iters defaults to ``4*n`` so large
    curbside rings fully flatten to the cap.

    ``pinned`` — indices whose value is LAW and may not move (a weld to a
    higher-authority surface, see :func:`law_anchor_values`).  A violating
    edge with one pinned end moves the FREE end by the whole excess
    instead of splitting it; an edge with BOTH ends pinned cannot be
    relaxed here at all and is left standing — two law values that
    disagree across a short chord is a law/anchor defect to attribute, not
    something a groundside relaxation may quietly average away (RULINGS:
    emitters emit, never grade).
    """
    n = len(coords)
    if n < 2 or len(alts) != n:
        return alts
    if iters is None:
        iters = max(300, 4 * n)
    pinned = pinned or frozenset()
    for _ in range(iters):
        worst = 0.0
        for i in range(n):
            j = (i + 1) % n
            d = math.hypot(coords[j][0] - coords[i][0],
                           coords[j][1] - coords[i][1])
            if d < 1e-6:
                continue
            maxd = max_grade * d
            diff = alts[j] - alts[i]
            if abs(diff) <= maxd:
                continue
            excess = abs(diff) - maxd
            i_fixed, j_fixed = i in pinned, j in pinned
            if i_fixed and j_fixed:
                continue                    # law vs law — report, never mix
            worst = max(worst, excess)
            if i_fixed:
                alts[j] += -excess if diff > 0 else excess
            elif j_fixed:
                alts[i] += excess if diff > 0 else -excess
            else:
                half = excess / 2.0
                if diff > 0:
                    alts[j] -= half
                    alts[i] += half
                else:
                    alts[j] += half
                    alts[i] -= half
        if worst < 1e-3:
            break
    return alts


# ──────────────────────────────────────────────────────────────────────
# THE TRANSITION LAW beside BELOW-GRADE geometry (round-4 spec R5)
# ──────────────────────────────────────────────────────────────────────

#: Shape ``ref``s whose emitted surface is CUT BELOW the surrounding
#: ground — the transition law's sources.  A ramp dives by law; whatever
#: stands beside it may not answer with a raw DEM sample.
# ``tunnel_road`` (R14-1/A-1) is mapped road pavement the tunnel
# system CLAIMED and re-profiled to the bore profile: it is below
# grade and it is what the surrounding surface must grade toward, so
# it belongs in this set exactly like an emitted ramp.  The claimed
# shape keeps its own ROLE — and therefore its authority rank — so
# nothing here is a new authority class.
BELOW_GRADE_REFS = ("tunnel_ramp", "tunnel_trench", "tunnel_road")

#: Roles whose plates take the transition law where they fall inside a
#: below-grade surface's reach.  Retaining-wall crest bands are in here
#: because the band IS the first ring of the transition, not a cliff top.
TRANSITION_ROLES = (
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_SERVICE_ROAD,
    ROLE_SERVICE_JUNCTION,
    ROLE_RETAINING_WALL,
)


def _ring_and_altitudes(shape):
    """``(ring, alts)`` for a shape carrying per-vertex or flat values —
    ``(None, None)`` for one that carries neither (an end-pair rect: the
    transition law never invents a per-vertex profile from a pair)."""
    polygon = getattr(shape, "polygon", None)
    if polygon is None or polygon.is_empty or polygon.geom_type != "Polygon":
        return None, None
    try:
        ring = list(polygon.exterior.coords)
    except _GEOM_EXC:                                  # pragma: no cover
        return None, None
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return None, None
    alts = getattr(shape, "node_altitudes", None)
    if alts:
        values = [a for a in alts[:len(ring)] if a is not None]
        if not values:
            return None, None
        fill = sum(values) / len(values)
        return ring, [
            float(a) if a is not None else fill
            for a in list(alts[:len(ring)])
            + [None] * max(0, len(ring) - len(alts))
        ]
    flat = getattr(shape, "altitude", None)
    if flat is None:
        return None, None
    return ring, [float(flat)] * len(ring)


def below_grade_sources(layout, refs=BELOW_GRADE_REFS) -> list:
    """``[(polygon, ring, alts)]`` for every BELOW-GRADE surface in the
    layout — the profiles the transition law grades away from."""
    sources = []
    for shape in getattr(layout, "shapes", ()) or ():
        if getattr(shape, "ref", "") not in refs:
            continue
        ring, alts = _ring_and_altitudes(shape)
        if ring is None:
            continue
        sources.append((shape.polygon, ring, alts))
    return sources


def below_grade_family_shapes(layout) -> list:
    """Every shape that IS below-grade geometry — THE ONE family test.

    The families were enumerated in three places that had to agree and
    were not one authority: :data:`BELOW_GRADE_REFS` here (the ramp /
    trench / claimed-road profiles the transition law grades away from)
    and ``gap_fill._TUNNEL_BLOCKER_ROLES`` / ``_TUNNEL_BLOCKER_REFS``
    (the law-cut hole R6 already had to enumerate: the tunnel roles and
    the wall ref).  ``flat_fast_path`` composed both by hand at two
    sites.  This is that composition, once, so a fourth reader
    (R17b-1's below-grade ANCHOR law) extends it rather than forking it
    (`consult-before-create`).

    Returns the shapes in ``layout.shapes`` order; a shape with no
    usable polygon is skipped, because every consumer is geometric.
    """
    from .gap_fill import _TUNNEL_BLOCKER_REFS, _TUNNEL_BLOCKER_ROLES

    out = []
    for shape in getattr(layout, "shapes", ()) or ():
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty:
            continue
        ref = getattr(shape, "ref", "")
        if (ref in BELOW_GRADE_REFS
                or ref in _TUNNEL_BLOCKER_REFS
                or getattr(shape, "role", None) in _TUNNEL_BLOCKER_ROLES):
            out.append(shape)
    return out


class _BelowGradeIndex:
    """The below-grade surfaces plus an R-tree over them.

    Built ONCE per layout: the law asks "what is under my feet and how
    far away" for every vertex of every candidate plate, and at OTHH
    that is O(10^5) vertices against O(10^2) ramps — a linear scan is
    the whole build-time cost of this law, and the index removes it.
    """

    __slots__ = ("sources", "tree", "bounds", "component_of",
                 "deepest_station")

    def __init__(self, sources):
        self.sources = list(sources)
        self.bounds = None
        self.tree = None
        # ONE PORTAL PER BELOW-GRADE BODY.  A tunnel cluster is emitted
        # as a chain of ramp quads and a Y-fork as two arms of one union:
        # anchoring per QUAD would pin the transition surface to the
        # ramp along its whole length (the collapse in mirror form), so
        # the sources are grouped into connected bodies and each body
        # contributes exactly one anchor — its deepest station, which is
        # where it meets grade under the pavement: the portal.
        self.component_of = [0] * len(self.sources)
        #: ``{component: ((x, y), altitude)}`` — THE PORTAL of each
        #: below-grade body: its DEEPEST station, the minimum profile
        #: altitude over that body's source rings (R16-2a).  Filled
        #: after ``component_of`` resolves.
        self.deepest_station = {}
        if not self.sources:
            return
        polygons = [polygon for polygon, _ring, _alts in self.sources]
        try:
            from shapely.strtree import STRtree

            self.tree = STRtree(polygons)
        except Exception:                              # pragma: no cover
            self.tree = None
        try:
            merged = unary_union(polygons)
            bodies = [
                geometry for geometry in getattr(merged, "geoms", [merged])
                if geometry is not None and not geometry.is_empty
            ]
            if len(bodies) > 1:
                body_tree = STRtree(bodies)
                for index, polygon in enumerate(polygons):
                    hit = body_tree.query(polygon.representative_point())
                    self.component_of[index] = (
                        int(hit[0]) if len(hit) else index)
        except Exception:                              # pragma: no cover
            self.component_of = list(range(len(self.sources)))
        _deepest: dict = {}
        for index, (_polygon, ring, alts) in enumerate(self.sources):
            component = self.component_of[index]
            for position, vertex in enumerate(ring):
                if position >= len(alts):              # pragma: no cover
                    break
                value = float(alts[position])
                point = (float(vertex[0]), float(vertex[1]))
                current = _deepest.get(component)
                if current is None or value < current[0] - 1e-9:
                    _deepest[component] = (value, [point])
                elif abs(value - current[0]) <= 1e-9:
                    current[1].append(point)
        # A STATION is a CROSS-SECTION, not one vertex: a ramp quad
        # reaches its portal depth on BOTH its edges, and measuring the
        # gap to whichever of the two the ring scan met first would put
        # the whole ramp WIDTH into the anchor's ``cap * gap`` (10.6 m
        # instead of 0.6 m on the R5 band twin).  Every vertex at the
        # body's minimum altitude is the same station.
        for component, (value, points) in _deepest.items():
            self.deepest_station[component] = (MultiPoint(points), value)
        xs0, ys0, xs1, ys1 = zip(*(p.bounds for p in polygons))
        self.bounds = (min(xs0), min(ys0), max(xs1), max(ys1))

    def __bool__(self) -> bool:
        return bool(self.sources)

    def candidates(self, point, reach_m: float):
        if self.tree is None:
            return range(len(self.sources))
        px, py = point
        try:
            return self.tree.query(
                box(px - reach_m, py - reach_m, px + reach_m, py + reach_m))
        except Exception:                              # pragma: no cover
            return range(len(self.sources))

    def in_reach_of(self, polygon, reach_m: float) -> bool:
        """Cheap bbox test: can this shape possibly be governed at all?"""
        if self.bounds is None or polygon is None:
            return False
        try:
            x0, y0, x1, y1 = polygon.bounds
        except (AttributeError, ValueError):           # pragma: no cover
            return False
        bx0, by0, bx1, by1 = self.bounds
        return not (x1 + reach_m < bx0 or x0 - reach_m > bx1
                    or y1 + reach_m < by0 or y0 - reach_m > by1)


def _nearest_source_profile(point, index, reach_m: float):
    """``(altitude, distance, source_index)`` of the nearest below-grade
    profile within ``reach_m`` of ``point`` — ``(None, None, None)`` when
    nothing is in reach.

    The altitude is interpolated along the source ring's nearest EDGE, so
    a ramp quad answers with its own dive at that station rather than
    with a corner value.
    """
    best = None
    px, py = point
    for source_index in index.candidates(point, reach_m):
        polygon, ring, alts = index.sources[int(source_index)]
        try:
            distance = polygon.distance(Point(px, py))
        except _GEOM_EXC:                              # pragma: no cover
            continue
        if distance > reach_m or (best is not None and distance >= best[1]):
            continue
        n = len(ring)
        best_edge = None
        for i in range(n):
            ax, ay = ring[i]
            bx, by = ring[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            length_squared = dx * dx + dy * dy
            if length_squared < 1e-12:
                t = 0.0
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / length_squared
                t = max(0.0, min(1.0, t))
            qx, qy = ax + dx * t, ay + dy * t
            edge_distance = math.hypot(px - qx, py - qy)
            if best_edge is None or edge_distance < best_edge[0]:
                best_edge = (
                    edge_distance,
                    alts[i] + (alts[(i + 1) % n] - alts[i]) * t,
                )
        if best_edge is None:                          # pragma: no cover
            continue
        best = (best_edge[1], distance, int(source_index))
    return best if best is not None else (None, None, None)


def transition_law_altitudes(ring, surface_alts, sources,
                             max_grade: float = GROUNDSIDE_MAX_GRADE,
                             reach_m: float | None = None):
    """THE TRANSITION LAW (round-4 spec R5, lead ruling 2026-08-10).

    A surface adjoining below-grade geometry does not get to answer with
    a raw DEM sample.  But the run it grades over is measured ALONG ITS
    OWN EXTENT — the band's ring, the plate's span — anchored where the
    below-grade surface meets grade under the pavement (the PORTAL, its
    deepest station), never across the horizontal gap to the ramp.

      * the surrounding surface is the AUTHORITY along the ramp's whole
        length: a retaining wall's crest stands at grade and the wall
        FACE spans the drop;
      * the crest descends only within the cap-limited run of the
        portal, converging on the ramp there.

    Measuring the run across the horizontal gap instead recreates the
    very collapse this law exists to remove, in mirror form — terrain
    hugging the ramp rather than standing beside it.  The witness is the
    pre-regression Aug-8 state: a crest graded 2.90–5.00 m at
    surrounding grade against a ramp already diving beneath it.

    Mechanism: one ANCHOR per below-grade body (``index.component_of``),
    placed at the ring vertex whose lawful floor ``ramp + cap * gap`` is
    lowest — the vertex closest to that body's deepest station — pinned
    at that floor; then the ring is relaxed to the cap around the pinned
    anchors, which IS the along-the-ring run.  Vertices further along the
    ring than ``|dz| / cap`` keep the surrounding surface exactly.

    Under FLAT-SITE mode the DEM sample is a constant, which is how the
    defect surfaced (a flat 4.00 crest against a −4.02 ramp; a
    groundside plate meeting its ramp with a 5.62 m step at 2.6 m
    spacing — the invalid-triangle source).  But the DEM sample was
    always the wrong witness beside a law-cut ramp; flat mode only
    removed the terrain variation that hid it.

    Returns ``(alts, touched)`` — the new per-vertex values and how many
    vertices the law moved.  ``sources`` empty ⇒ the input, untouched.
    """
    index = (sources if isinstance(sources, _BelowGradeIndex)
             else _BelowGradeIndex(sources))
    if not index or not ring:
        return list(surface_alts), 0
    if reach_m is None:
        reach_m = transition_reach_m(surface_alts, index, max_grade)
    alts = [float(a) for a in surface_alts]

    # THE PORTAL ANCHORS (R16-2a).  Per below-grade body the portal is
    # the body's DEEPEST STATION — the minimum profile altitude over its
    # source rings — and the anchor is the governed ring vertex NEAREST
    # THAT STATION, pinned at ``deepest_alt + cap * gap`` measured to
    # that station.  ``cap * gap`` is the only role the horizontal gap
    # keeps: what the anchor may stand above the ramp, never a run any
    # other vertex grades over.
    #
    # The pre-round-16 mechanism minimised ``nearest_profile + cap * d``
    # PER VERTEX, and ``_nearest_source_profile`` answers with the
    # NEAREST edge of the NEAREST quad — so the winner was whichever
    # station happened to lie closest to the ring, i.e. the SHALLOWEST
    # one, and the docstring's own prose (this law's text) measured out
    # false.  Which BODIES govern the ring is unchanged: still the
    # bodies a ring vertex finds in reach.
    governed: set = set()
    for position, vertex in enumerate(ring):
        source_alt, distance, source_index = _nearest_source_profile(
            vertex, index, reach_m)
        if source_alt is None:
            continue
        governed.add(index.component_of[source_index])
    floor_by_component: dict[int, tuple[float, int]] = {}
    for component in governed:
        station = index.deepest_station.get(component)
        if station is None:                            # pragma: no cover
            continue
        station_geom, deepest_alt = station
        best = None
        for position, vertex in enumerate(ring):
            try:
                gap = station_geom.distance(
                    Point(float(vertex[0]), float(vertex[1])))
            except _GEOM_EXC:                          # pragma: no cover
                continue
            if best is None or gap < best[0]:
                best = (gap, position)
        if best is None:                               # pragma: no cover
            continue
        gap, position = best
        floor = float(deepest_alt) + max_grade * float(gap)
        if floor >= alts[position] - 1e-3:
            continue                   # nothing below grade to grade to
        floor_by_component[component] = (floor, position)
    if not floor_by_component:
        return alts, 0

    pinned = set()
    for floor, position in floor_by_component.values():
        # Two bodies can name the SAME nearest vertex; the deeper floor
        # is the one that governs it (a vertex has one lawful value).
        if position in pinned:
            alts[position] = min(alts[position], floor)
        else:
            alts[position] = floor
        pinned.add(position)
    # The relaxation IS the along-the-ring run, so it must actually
    # converge: the primitive's default budget (max(300, 4n)) is sized
    # for a nudge, and a pinned portal 8 m below a 60-vertex ring needs
    # an order of magnitude more passes to spread at the cap (measured:
    # 300 passes leave 0.011 m of excess, convergence to the primitive's
    # own 5e-4 floor costs 5-21 ms on 62-302 vertex rings).  It still
    # breaks early the moment it converges.
    alts = _grade_limit_ring(
        list(ring), alts, max_grade,
        iters=max(4000, 64 * len(ring)), pinned=pinned)
    touched = sum(
        1 for position, value in enumerate(alts)
        if abs(value - float(surface_alts[position])) > 1e-9
    )
    return alts, touched


def transition_reach_m(surface_alts, index,
                       max_grade: float = GROUNDSIDE_MAX_GRADE) -> float:
    """How far the law can reach: the largest rise the cap has to climb,
    divided by the cap.  Beyond it the surrounding surface stands."""
    if not index or not surface_alts:
        return 0.0
    source_low = min(min(alts) for _p, _r, alts in index.sources)
    source_high = max(max(alts) for _p, _r, alts in index.sources)
    span = max(
        abs(float(max(surface_alts)) - source_low),
        abs(float(min(surface_alts)) - source_high),
    )
    return span / max(max_grade, 1e-6)


def apply_below_grade_transition(layout,
                                 roles=TRANSITION_ROLES,
                                 max_grade: float = GROUNDSIDE_MAX_GRADE
                                 ) -> int:
    """Re-profile every transition surface standing in a below-grade
    surface's reach (round-4 spec R5).  Returns the number of shapes the
    law moved.

    Runs AFTER the tunnel emitters, because the ramps it grades away
    from are what those emitters create.  A shape carrying neither
    per-vertex nor flat altitudes is left alone: inventing a profile out
    of an end pair would be minting, not grading.
    """
    index = _BelowGradeIndex(below_grade_sources(layout))
    if not index:
        return 0
    source_ids = {id(polygon) for polygon, _ring, _alts in index.sources}
    changed = 0
    for shape in list(getattr(layout, "shapes", ()) or ()):
        if getattr(shape, "role", "") not in roles:
            continue
        if id(getattr(shape, "polygon", None)) in source_ids:
            continue
        ring, alts = _ring_and_altitudes(shape)
        if ring is None:
            continue
        reach_m = transition_reach_m(alts, index, max_grade)
        if not index.in_reach_of(shape.polygon, reach_m):
            continue
        new_alts, touched = transition_law_altitudes(
            ring, alts, index, max_grade, reach_m=reach_m)
        if not touched:
            continue
        shape.node_altitudes = list(new_alts) + [new_alts[0]]
        shape.altitude = None
        changed += 1
    return changed


def law_anchor_values(layout, for_role=None) -> dict:
    """``{(x, y) rounded to mm: elevation}`` — the LAW values this role's
    surfaces must grade to, taken from every shape that OUTRANKS it.

    THE SAME ORDER THE EMITTER USES.  ``layout.authority_rank`` is the
    total precedence order ``to_osm`` resolves a shared node with (airside
    first; groundside_pavement last among the named roles).  Reading it
    here is what makes the groundside SURFACE and the emitted NODE agree:
    the lot grades to exactly the value the emit consensus is going to
    write at that weld, so the two cannot disagree.  Soft receivers
    (graded_strip, runway_clearance, retaining_wall, …) are unnamed in the
    order and therefore tail — correctly, since they ADOPT values rather
    than carry them, and anchoring a lot to an adopter would be circular.

    Only shapes carrying an explicit per-vertex ``node_altitudes`` or a
    single ``altitude`` contribute.  A rect that carries only
    ``altitude_high``/``altitude_low`` is skipped rather than guessed at:
    inventing a per-vertex value from an end pair is minting, and the
    measured weld population here (HEAZ way -10281: 17 service_junction
    nodes) carries explicit node altitudes.

    R7b — A ROAD NEVER WELDS TO A BUILDING (owner ruling 2026-08-15, the
    sink ruling): "a building pad datum is legitimate for its own
    footprint and must not propagate into the road network".
    ``ROLE_BUILDING`` outranks every road-family and groundside role in
    ``AUTHORITY_PRECEDENCE``, so before this clause every pad vertex
    within the weld tolerance of a road, junction or lot ring was a
    PINNED law anchor for it.  That is the measured CYXY sink: building
    25's 697.13 pad datum reached lot 377 through frontage junctions
    352/364/365 and carved 40,000 m³ against a 702.2 terrain median.
    Buildings are therefore skipped for every asking role in
    ``GROUNDSIDE_ROLES``; they remain law for everything senior to them
    (the apron↔building frontage weld, owner 2026-08-08, is untouched —
    an apron outranks a building and reads it through its own path).
    """
    from .layout import (GROUNDSIDE_ROLES, ROLE_BUILDING,
                         ROLE_GROUNDSIDE_PAVEMENT, authority_rank)
    asking = for_role or ROLE_GROUNDSIDE_PAVEMENT
    my_rank = authority_rank(asking)
    no_pads = asking in GROUNDSIDE_ROLES
    best: dict = {}
    for idx, s in enumerate(getattr(layout, "shapes", ()) or ()):
        role = getattr(s, "role", "") or ""
        if no_pads and role == ROLE_BUILDING:
            continue                    # R7b: pads stay on their footprints
        rank = authority_rank(role)
        if rank >= my_rank:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        try:
            ring = list(poly.exterior.coords)
        except _GEOM_EXC:
            continue
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        alts = getattr(s, "node_altitudes", None)
        if alts is not None:
            vals = [None if a is None else float(a) for a in alts]
        elif getattr(s, "altitude", None) is not None:
            vals = [float(s.altitude)] * len(ring)
        else:
            continue
        for (x, y), v in zip(ring, vals):
            if v is None:
                continue
            key = (round(float(x), 3), round(float(y), 3))
            prior = best.get(key)
            if prior is None or (rank, idx) < (prior[0], prior[1]):
                best[key] = (rank, idx, float(v))
    return {k: v for k, (_r, _i, v) in best.items()}


def law_anchor_key(layout, anchors=None):
    """The KEY FUNCTION that decides "this ring vertex IS that weld".

    ONE IDENTITY, the emitter's.  ``law_anchor_values`` used to key on the
    millimetre-rounded coordinate while ``to_osm`` interns shared nodes
    through ``layout.canonical_points`` at ``SHARED_VERTEX_TOL_M`` (0.5 m)
    — so a lot vertex 3 mm from the service-junction node it welds to
    found NO anchor at seat time, kept its raw DEM seed, and then had that
    same vertex OVERWRITTEN at emit by the higher authority's value.  The
    result is one ring carrying its welds on the law and its interior on
    the terrain: measured at HECA (way shapeID 525) as two nodes at
    99.06/99.07 m against four at 1.13-1.22 m on the 1 m plateau — the
    98.07 m ``within_shape`` row that headed the census.

    IDENTITY IS NEAREST-WITHIN-TOLERANCE, not key equality.  The emitter
    resolves a node through ``CanonicalPointRegistry`` (``tol_m =
    SHARED_VERTEX_TOL_M``), which returns the NEAREST registered point
    within the radius — so this builds the same structure over the
    ANCHOR coordinates and asks it the same question.  Keying on the
    layout's global registry was not enough on its own: post-solve
    geometry passes move an authority ring after its vertices were
    interned, so neither side need resolve to a canonical point at all
    (measured at HEAZ shape 279 — fourteen weld vertices shared with
    ``service_junction`` shape 28 at 57.9-59.9 m, none of them found, the
    interior left at 1-17 m and 748 ``within_shape`` rows minted).

    The layout registry is still consulted FIRST and READ-ONLY (``get``,
    never ``get_or_add``): interning a point here would change which
    LATER points intern together and so move the emitted surface from
    inside a lookup.  With neither registry nor anchors the key degrades
    to the historical millimetre rule.

    ``anchors`` — the dict ``law_anchor_values`` returned.  Its KEYS are
    the coordinates the index is built over, so a hit always names a key
    that dict actually holds.
    """
    reg = getattr(layout, "canonical_points", None)
    index = None
    if anchors:
        from .canonical_points import CanonicalPointRegistry
        index = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
        for (ax, ay) in anchors:
            index.add_exact(float(ax), float(ay))

    def _key(x, y):
        x, y = float(x), float(y)
        exact = (round(x, 3), round(y, 3))
        if anchors is not None and exact in anchors:
            return exact
        if reg is not None:
            try:
                c = reg.get(x, y)
            except Exception:                          # pragma: no cover
                c = None
            if c is not None:
                ck = (round(float(c[0]), 3), round(float(c[1]), 3))
                if anchors is None or ck in anchors:
                    return ck
        if index is not None:
            near = index.find_nearest(x, y, SHARED_VERTEX_TOL_M)
            if near is not None:
                return (round(float(near[0]), 3), round(float(near[1]), 3))
        return exact

    return _key


def _mm_key(x, y):
    """The historical millimetre key — the fallback identity."""
    return (round(float(x), 3), round(float(y), 3))


def _ring_arcs(coords):
    """Edge lengths of the CLOSED ring, index i = edge i→i+1."""
    n = len(coords)
    return [math.hypot(coords[(i + 1) % n][0] - coords[i][0],
                       coords[(i + 1) % n][1] - coords[i][1])
            for i in range(n)]


def _flanking_law(coords, seg, have, k):
    """Walk the ring both ways from ``k`` to the nearest index in
    ``have``.  Returns ``(j, db, k2, df)`` or ``None`` if ``have`` is
    empty.  ``j == k2`` when the ring carries exactly one law datum.

    THE ARC, not the straight line: the within-shape grade law pairs
    ADJACENT RING VERTICES, so the distance a lot vertex is allowed to
    deviate from its law datum is measured along the ring it lives on.
    """
    n = len(coords)
    if not have:
        return None
    db = 0.0
    j = k
    for _ in range(n):
        j = (j - 1) % n
        db += seg[j]
        if j in have:
            break
    else:                                              # pragma: no cover
        return None
    df = 0.0
    k2 = k
    for _ in range(n):
        df += seg[k2]
        k2 = (k2 + 1) % n
        if k2 in have:
            break
    else:                                              # pragma: no cover
        return None
    return j, db, k2, df


def _seat_ring_on_law_anchors(coords, dem_alts, anchors, max_grade,
                              key_fn=None, prior_at=None, stats=None,
                              seat_out=None, band_at=None):
    """Seat a groundside ring on the LAW datum its welds carry, keeping
    only the DEM's RELIEF — the owner's "DEM is a SEED, nothing more".

    Returns ``(alts, pinned_indices)``.  With no anchor on the ring the
    DEM values are returned unchanged and ``pinned`` is empty: an island
    with nothing to grade to is a LAW-ISLAND defect to attribute, not a
    licence to invent a datum.

    THE DEFECT THIS REPLACES (fix cycle 2 item 2, measured).  The lot
    emitter sampled the DEM at every vertex and ring-limited the result —
    a DEM DRAPE with a smoother, in which the terrain is the authority and
    the law is a post-filter.  The welds were then overwritten at emit by
    the higher-authority claimant, so a single lot shipped with its weld
    vertices on the law and its interior on the terrain.  Measured at HEAZ
    in the canyon world (way -10281): 17 weld nodes at 85.56-91.70 m and
    47 interior nodes at 10 000.00 m — one shape, 9 914.44 m of step, and
    the campaign's worst within_shape row in both flat worlds.

    A ring limiter alone CANNOT fix that, and the arithmetic says why: at
    the 5 % lot cap over a 15 m densify step an edge may fall 0.75 m, so
    closing 9 914 m would need ~13 000 edges and the ring has 63.  Capping
    the SLOPE of a surface whose DATUM is wrong just distributes the error.
    The datum has to come from the law:

        z(v) = z_law(nearest anchor) + clamp(dem(v) - dem(anchor), ±cap·d)

    Under a constant DEM the relief term is exactly zero, so the lot lands
    flat on its weld datum and emits zero rows — which is the oracle's
    whole point.  Under real terrain the lot still FOLLOWS the ground, but
    only as far from its welds as the lot's own grade law allows.

    THE VALUE LADDER (cycle-6 ingestion, spec Part D).  A ring vertex
    never takes the raw DEM while ANY law source reaches it:

    1. an exact WELD anchor — the value the higher-authority surface
       carries, pinned (identity via ``key_fn``, the emitter's);
    2. the shape's OWN PRIOR FIELD (``prior_at``) — a clipped, merged or
       de-conflicted piece is the same surface it was a moment ago, and
       that surface was already law-seated.  Interpolated along the
       ORIGINAL ring's edge, so it is the host-edge insert value the
       ingestion spec names.  A law datum, not pinned;
    3. the ROUTE-GRAPH BAND (``band_at``, RULINGS 2026-08-06 "ONE graph")
       — the vertex is coupled to the solved network through service-road
       routes and/or the pavement it welds to, so the law reaches it even
       with no weld of its own: the band says WHICH VALUES ARE LAWFUL
       there and the DEM SEED chooses where inside that interval the
       vertex seats (``clamp(seed, floor, ceiling)``).  A law datum, not
       pinned.  This is the rung that retires the LAW-ISLAND branch for
       every CONNECTED ring — the D′ class, 4,607 census rows in the
       c8base frame of record, 97 % of HECA's groundside rings;
    4. LAW INTERPOLATION between the two FLANKING law datums along the
       ring, with the DEM contributing RELIEF ONLY about that chord,
       clamped to ``cap × arc`` — the nearest-anchor rule this replaces
       could only offer one datum and so stair-stepped between two welds;
    5. nothing above reaches this ring — a genuinely DISCONNECTED ring,
       which the owner ruled is NOT SOLVED: *"Anything truly
       disconnected, we don't really have to do anything at all — it just
       gets left at DEM and doesn't need to be solved."*  The DEM seed
       stands, the ring is COUNTED in ``stats``, and the census
       adjudicates its rows out of scope through the SAME predicate (the
       sidecar carries this answer — coupling law and census land
       together).

    Under a constant DEM steps 2 and 3 return the law value exactly (the
    relief term and the DEM chord both vanish), which is why the oracle
    worlds read zero here.
    """
    n = len(coords)
    out = [float(a) for a in dem_alts]
    key_fn = key_fn or _mm_key
    law_at: dict = {}
    anchor_idx: list = []
    if anchors:
        for k in range(n):
            v = anchors.get(key_fn(coords[k][0], coords[k][1]))
            if v is not None:
                law_at[k] = float(v)
                anchor_idx.append(k)
    # (2) the shape's own prior field, where the welds do not reach.
    prior_idx: list = []
    if prior_at is not None:
        for k in range(n):
            if k in law_at:
                continue
            v = prior_at(coords[k][0], coords[k][1])
            if v is not None:
                law_at[k] = float(v)
                prior_idx.append(k)
    # (4) THE ROUTE-GRAPH BAND — the law source for a ring NO weld and no
    # prior field reaches.  It is asked AFTER the two datum rungs on
    # purpose: where the ring carries a law datum, the flanking
    # interpolation below is the TIGHTER law (a weld value is a point, the
    # band is an interval), and the tighter law wins.  The band is the
    # LAWFUL INTERVAL and the DEM SEED picks the value inside it — the
    # owner's "DEM chooses where things get seated within their feasible
    # bands" verbatim.  In the ruled synthetic worlds the seed is outside
    # the interval at every vertex, so the clamp lands on the near edge —
    # floor at −500, ceiling at 10 000 — which is exactly the
    # extreme-seating saturation the constant-DEM oracle asserts.
    band_idx: list = []
    if band_at is not None and not law_at:
        ivs = {}
        for k in range(n):
            iv = band_at(coords[k][0], coords[k][1])
            if iv is None:
                continue
            lo_v, hi_v = float(iv[0]), float(iv[1])
            if hi_v < lo_v:                                # pragma: no cover
                lo_v, hi_v = hi_v, lo_v
            ivs[k] = (lo_v, hi_v)
        for k, (lo_v, hi_v) in ivs.items():
            # THE NEAR EDGE, PER VERTEX — the DEM seed clamped into the
            # vertex's own interval ("DEM chooses where within the band").
            #
            # A LEVEL-RING VARIANT WAS TRIED AND IS NOT HERE (cycle 8,
            # measured): seating the whole ring at one value inside the
            # INTERSECTION of its vertices' intervals is trivially
            # within-cap, but it measured WORSE — HEAZ canyon groundside
            # adjudicated 131 -> 153 rows — because a level lot then
            # steps against everything it welds to.  Kept as a note
            # rather than a flag: one seat, the measured one.
            seed = dem_alts[k]
            seed = lo_v if seed is None else float(seed)
            law_at[k] = min(max(seed, lo_v), hi_v)
            band_idx.append(k)
    if stats is not None:
        stats["rings"] = stats.get("rings", 0) + 1
        stats["anchored"] = stats.get("anchored", 0) + len(anchor_idx)
        stats["from_prior"] = stats.get("from_prior", 0) + len(prior_idx)
        stats["from_band"] = stats.get("from_band", 0) + len(band_idx)
    if seat_out is not None:
        seat_out["n_band"] = len(band_idx)
        seat_out["law_seated"] = bool(law_at)
        seat_out["n_law"] = len(law_at)
        seat_out["n_anchor"] = len(anchor_idx)
    if not law_at:
        # (5) TRULY DISCONNECTED — no weld, no prior field, and the route
        # graph's band does not reach it either.  Report, don't invent:
        # the owner ruled this geometry is not solved at all.
        if stats is not None:
            stats["islands"] = stats.get("islands", 0) + 1
            stats["island_vertices"] = (stats.get("island_vertices", 0) + n)
            # VERTEX IDENTITY (RULINGS 2026-08-06 binding point 3): a bare
            # total cannot be attributed, which defeats the report's own
            # "a nonzero count is a defect to attribute" claim.  One
            # locator per island ring — its first vertex in layout-local
            # metres — capped so a pathological build cannot grow the
            # book without bound.
            where = stats.setdefault("island_xy", [])
            if len(where) < _ISLAND_XY_CAP:
                where.append((round(float(coords[0][0]), 2),
                              round(float(coords[0][1]), 2)))
        return out, frozenset()
    for k, v in law_at.items():
        out[k] = v
    # (3) interpolate between flanking law datums; DEM = relief only.
    seg = _ring_arcs(coords)
    have = set(law_at)
    for k in range(n):
        if k in have:
            continue
        flank = _flanking_law(coords, seg, have, k)
        if flank is None:                              # pragma: no cover
            continue
        j, db, k2, df = flank
        span = db + df
        if k2 == j or span <= 0.0:
            base = law_at[j]
            dem_ref = float(dem_alts[j])
            reach = db
        else:
            t = db / span
            base = law_at[j] + t * (law_at[k2] - law_at[j])
            dem_ref = (float(dem_alts[j])
                       + t * (float(dem_alts[k2]) - float(dem_alts[j])))
            reach = min(db, df)
        allowed = max_grade * reach
        relief = float(dem_alts[k]) - dem_ref
        out[k] = base + max(-allowed, min(allowed, relief))
    if stats is not None:
        stats["interpolated"] = (stats.get("interpolated", 0)
                                 + n - len(have))
    return out, frozenset(anchor_idx)


def _prior_field_reader(prior, tol_m=None):
    """``f(x, y) -> value | None`` over the ring(s) a rebuilt piece came
    FROM — the shape's own law field, interpolated along the original
    ring's edge.

    ``prior`` is an iterable of ``(coords, alts)`` (open or closed; the
    ``len(alts) == len(coords) + 1`` convention is trimmed here, the one
    the OSM emitter uses).  Reuses
    ``adjacent_ground._interp_on_ring_law`` — THE authority for "value at
    an arbitrary point on a ring" — rather than re-deriving the
    projection a third time.  Returns ``None`` when nothing is in range,
    which is what lets the caller fall through the ladder instead of
    inventing a datum.
    """
    from .adjacent_ground import _interp_on_ring_law
    rings = []
    for entry in (prior or ()):
        if not entry:
            continue
        coords, alts = entry
        if not coords or not alts:
            continue
        c = list(coords)
        a = [None if v is None else float(v) for v in alts]
        if len(c) > 1 and c[0] == c[-1]:
            c = c[:-1]
        if len(a) == len(c) + 1:
            a = a[:-1]
        if len(a) != len(c) or len(c) < 2 or any(v is None for v in a):
            continue
        rings.append((c, a))
    if not rings:
        return None
    reach = float(tol_m if tol_m is not None else GROUNDSIDE_CLEARANCE_M)

    def _read(x, y):
        best = None
        for (c, a) in rings:
            v = _interp_on_ring_law(c, a, float(x), float(y), reach)
            if v is not None:
                # Two source rings can both cover a merge seam; the
                # HIGHER value wins, matching the emitter's authority
                # order (a lot never adopts the lower of two claims it
                # already carried).
                best = v if best is None else max(best, v)
        return best

    return _read


#: Per-pass cap on the island LOCATORS kept for attribution.  The counts
#: are never capped; only the coordinate list is.
_ISLAND_XY_CAP = 20


def _law_seat_stats(layout, where):
    """The per-pass accumulator behind ``[groundside-law-seat]``."""
    if layout is None:
        return None
    book = getattr(layout, "_gs_law_seat", None)
    if book is None:
        book = {}
        layout._gs_law_seat = book
    return book.setdefault(where, {"where": where})


#: Set on a groundside shape whose field came from the LAW (a weld
#: anchor, or interpolation between welds).  Absent/False means the ring
#: is still carrying its DEM SEED, and such a field must never be
#: inherited as law by the next rebuild — that is how one pre-solve DEM
#: drape propagated through clip → merge → de-conflict and shipped.
_LAW_SEATED_ATTR = "_gs_law_seated"

#: Set on a groundside shape the ONE route graph does not reach — no weld,
#: no prior field, no band (RULINGS 2026-08-06: "TRULY DISCONNECTED
#: geometry … is NOT SOLVED: it stays at raw DEM by construction and mints
#: nothing").  The emitted sidecar carries these rings so the census
#: adjudicates them with the SOLVE'S OWN answer instead of a second
#: reachability opinion.
_DISCONNECTED_ATTR = "_gs_disconnected"

#: A vertex whose value equals the DEM sample within this tolerance is
#: still on its SEED — nothing ever wrote law there.  It is the emitted
#: altitude's rounding step (2 dp), not a law tolerance, and at the
#: constant-DEM worlds the test is exact.
_SEED_MATCH_TOL_M = 0.011



def _shape_prior(*shapes):
    """``[(ring, values)]`` for every shape that carries a per-vertex or
    flat field — the prior half of the value ladder.  Shapes with no
    value contribute nothing (inventing one from an end pair is minting,
    the same rule ``law_anchor_values`` states).

    A groundside piece still on its DEM SEED contributes nothing either:
    its field is not law, and passing it on as a prior would launder a
    DEM drape into an apparently-lawful inheritance.
    """
    out = []
    for s in shapes:
        if s is None:
            continue
        if (getattr(s, "role", "") == ROLE_GROUNDSIDE_PAVEMENT
                and not getattr(s, _LAW_SEATED_ATTR, False)):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        try:
            ring = list(poly.exterior.coords)
        except _GEOM_EXC:
            continue
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) < 2:
            continue
        na = getattr(s, "node_altitudes", None)
        if na is not None:
            vals = list(na)
        elif getattr(s, "altitude", None) is not None:
            vals = [float(s.altitude)] * len(ring)
        else:
            continue
        out.append((ring, vals))
    return out


def _service_edge_counterfactual(layout, G, band):
    """REPORT-ONLY, DEFAULT OFF — ``O4_DUMP_SERVICE_BAND=<path>``.

    THE IN-PROCESS INTERVENTION behind "do the service EDGES carry reach":
    the SAME band construction is run a second time on the same graph with
    the service spine pairs dropped from ``G.spine_adj`` (mouths kept —
    they are the boundary arbiter, RULINGS 2026-08-07), and the two source
    tables are diffed node by node.  It answers with NUMBERS only: how many
    nodes lose their band entirely, how many keep one with a different
    interval, and the worst floor/ceiling movement, plus a sample carrying
    both frames (local metres and 11-decimal lat/lon canonical identity).

    It is a counterfactual, not a second implementation: both arms call
    ``building_feasibility.groundside_reach_band``, so there is one code
    path and no private copy of the band (tools/INDEX.md, the
    census-wrapper precedent).  The graph is restored before returning.
    """
    path = _os.environ.get("O4_DUMP_SERVICE_BAND")
    if not path or band is None:
        return
    import O4_UI_Utils as UI
    try:
        from .elevation_per_surface.building_feasibility import (
            groundside_reach_band)
        from .elevation_per_surface.route_profile.solve import (
            adj_without_pairs)
        pairs = getattr(G, "service_spine_pairs", None) or set()
        full_src = dict(getattr(band, "src", None) or {})
        saved_adj = G.spine_adj
        try:
            G.spine_adj = adj_without_pairs(saved_adj, pairs)
            band_ko = groundside_reach_band(layout, G)
        finally:
            G.spine_adj = saved_adj
        ko_src = dict(getattr(band_ko, "src", None) or {}) if band_ko else {}
        pos = getattr(G, "pos", None) or {}
        lost, moved, same = [], [], 0
        for i, (f, c) in full_src.items():
            other = ko_src.get(i)
            if other is None:
                lost.append(i)
            elif abs(other[0] - f) > 1e-6 or abs(other[1] - c) > 1e-6:
                moved.append((i, f, c, other[0], other[1]))
            else:
                same += 1
        moved.sort(key=lambda t: max(abs(t[3] - t[1]), abs(t[4] - t[2])),
                   reverse=True)
        to_ll = getattr(layout, "m_to_ll", None)

        def _row(i, f=None, c=None, f2=None, c2=None):
            x, y = pos.get(i, (None, None))
            ll = None
            if to_ll is not None and x is not None:
                try:
                    la, lo = to_ll(float(x), float(y))
                    ll = [f"{la:.11f}", f"{lo:.11f}"]
                except Exception:                      # pragma: no cover
                    ll = None
            return {"node": int(i), "x": x, "y": y, "ll": ll,
                    "floor": f, "ceiling": c,
                    "floor_no_edges": f2, "ceiling_no_edges": c2}

        rec = {
            "icao": getattr(layout, "icao", ""),
            "service_spine_pairs": len(pairs),
            "mouths": int(getattr(band, "mouths", 0)),
            "sources_full": len(full_src),
            "sources_no_service_edges": len(ko_src),
            "lost_band_entirely": len(lost),
            "band_interval_moved": len(moved),
            "band_unchanged": same,
            "worst_move_m": (round(max(max(abs(t[3] - t[1]),
                                          abs(t[4] - t[2]))
                                      for t in moved), 4)
                             if moved else 0.0),
            "sample_lost": [_row(i) for i in lost[:20]],
            "sample_moved": [_row(i, f, c, f2, c2)
                             for (i, f, c, f2, c2) in moved[:20]],
        }
        with open(path, "w") as fh:
            json.dump(rec, fh)
        UI.vprint(1,
            f"  [svc-band-diag] service-edge counterfactual: sources "
            f"{rec['sources_full']} -> {rec['sources_no_service_edges']} "
            f"without the {len(pairs)} service pair(s); {rec['lost_band_entirely']} "
            f"node(s) lose their band, {rec['band_interval_moved']} keep one "
            f"with a different interval (worst {rec['worst_move_m']:.4f} m) "
            f"-> {path}")
    except Exception as exc:                           # pragma: no cover
        UI.vprint(1, f"  [svc-band-diag] WARN: counterfactual FAILED "
                     f"({exc!r}) — no number reported rather than a wrong one")


def groundside_route_band(layout):
    """THE route-graph band for groundside seating, or ``None``.

    Builds the node list, the unified graph and
    ``building_feasibility.groundside_reach_band`` — the SAME construction
    ``adjacent_ground._construct_reach_band`` uses for the pre-solve
    march, so there is one way to get a band from a layout.  Read-only:
    the node list is taken ``readonly`` (measurement contract) and nothing
    on the layout is written.

    A failure DEGRADES LOUDLY to ``None`` (the ladder then has only its
    welds and priors, which is the pre-cycle-8 behaviour) rather than
    killing a build in the emit tail.
    """
    import O4_UI_Utils as UI
    # SIDE-EFFECT FREE, and MEASURED THAT WAY.  ``spine_value_fields`` —
    # which this build necessarily runs — publishes three WRITE-ONLY,
    # LAST-CALL-WINS stashes on the layout: the band-anchor provenance and
    # the final-band inversion record (plus its node count), which
    # ``assert_no_final_band_inversion`` reads as THE post-solve law.
    # Letting a groundside band build overwrite them replaces the solve's
    # own record with one taken in a different context — measured here as
    # a HEAZ build failing on 5 "inversions" the solve never saw.  The
    # values are snapshotted and restored, exactly as an instrument
    # restores the node-space indices it perturbs.
    # The two NODE-SPACE INDICES ``_build_node_list`` publishes are in the
    # stash for the same reason: they are IN ITS OWN node space, and a
    # later pass reading them against a different one is the node-space
    # trap this repo has paid for repeatedly.  ``_analytic_band`` in the
    # harness oracle restores exactly these two; a probe that reads a
    # layout must leave it as it found it.
    _STASH = ("_final_band_inversions", "_final_band_node_count",
              "_band_anchor_provenance",
              "_terrain_host_yield_first_index",
              "_adjacent_ground_first_zone_index",
              "_pav_vis_cache")
    saved = {a: getattr(layout, a, None) for a in _STASH}
    try:
        from .elevation_per_surface.solver_primitives import _build_node_list
        from . import grade_graph as _GG
        from .elevation_per_surface.building_feasibility import (
            groundside_reach_band)
        nodes, b2i = _build_node_list(layout, readonly=True)
        if not nodes:
            return None
        ctx = _GG.build_context(layout, b2i)
        # WITHIN-SHAPE EDGES ARE DEAD WORK FOR THIS PROBE, and the proof
        # ``build_unified_graph`` demands for ``skip_edge_shape_ids``
        # ("never as an optimisation on faith") is a READING one, not a
        # numerical one — nothing downstream of this call ever looks at the
        # set being skipped:
        #   1. the graph's only consumers here are ``groundside_reach_band``
        #      and ``_service_edge_counterfactual``, and neither reads
        #      ``G.edges`` / ``G.edge_family``: the whole band path
        #      (building_feasibility, raster_reach_band) reads ``G.pos``,
        #      ``G.spine_adj``, ``G.runway_anchor`` and
        #      ``G.service_spine_pairs`` and nothing else;
        #   2. POSITIONS STAY REGISTERED — the skip is tested AFTER
        #      ``G.pos[i] = ring[p]`` — so the global spine still strings
        #      across every shape and the band keeps its connectivity, which
        #      is the guarantee the parameter's own docstring makes;
        #   3. the spine and runway-anchor stages (``_build_global_spine``,
        #      ``_runway_anchors``) read ``G.pos`` only, so ``spine_adj``
        #      and the anchors are the full graph's;
        #   4. the one side effect skipped is the per-shape
        #      ``layout._lockstep_shape_bake`` export, whose ONLY consumers
        #      (``verification.lockstep_pair_caps_ll`` via solve.py, and
        #      ``grade_graph_validate.within_violations`` via
        #      ``elevation._report_within_shape_violations``, pipeline.py
        #      step [5]'s last statement) have both run by the time this
        #      phase-[6] probe is reached — so the store this probe used to
        #      overwrite with post-solve bakes is never read again.
        # Measured at HECA: the skipped pair generation is ~9 s of this
        # probe's ~20 s, and the emitted patch is byte-identical.
        G = _GG.build_unified_graph(
            layout, b2i, ctx=ctx,
            skip_edge_shape_ids={id(s) for s in layout.shapes})
        band = groundside_reach_band(layout, G)
        if band is not None:
            UI.vprint(1, f"  [groundside-band] route-graph band: "
                         f"{getattr(band, 'mouths', 0)} mouth(s), "
                         f"{getattr(band, 'sources', 0)} banded node(s), "
                         f"off-route radius "
                         f"{getattr(band, 'offnet_radius_m', 0.0):.0f} m "
                         f"at the lot cap")
            _service_edge_counterfactual(layout, G, band)
        return band
    except Exception as exc:                               # pragma: no cover
        UI.vprint(1, f"  [groundside-band] WARN: route-graph band build "
                     f"FAILED ({exc!r}) — the seat ladder keeps its welds "
                     f"and priors only (coverage degrade).")
        return None
    finally:
        for a, v in saved.items():
            if v is None:
                if hasattr(layout, a):
                    try:
                        delattr(layout, a)
                    except AttributeError:                 # pragma: no cover
                        pass
            else:
                setattr(layout, a, v)


def seat_groundside_on_law(layout, dem, tile_lat: int = 0,
                           tile_lon: int = 0, band_at=None) -> int:
    """POST-SOLVE: seat every groundside ring still on its DEM seed.

    WHY THIS EXISTS (measured, HEAZ ``--dem 1``).  The classification
    slot demotes pavement to groundside LONG BEFORE the one solve, so at
    that moment no higher-authority surface carries a value and
    ``law_anchor_values`` is empty: the piece is necessarily born on a
    DEM SEED.  The build then had no pass that ever came back for it —
    only pieces that happened to be clipped, merged or de-conflicted were
    re-seated — so the seed shipped.  16 of HEAZ's 20 law-island rings
    were minted in exactly that slot.

    This is the "come back for it" pass, and it is the ingestion the
    single-solve ruling asks for (RULINGS 2026-08-03): groundside lots
    are NOT in the solve's node space (``PAVEMENT_ROLES`` excludes
    ``groundside_pavement``), so nothing here overwrites a solved value —
    it replaces a raw-DEM seed with the law the lot welds to, using the
    same ladder and the same emitter identity as every other seat.

    VALUES ONLY.  The ring is not re-simplified, re-densified or moved:
    its vertices are shared with the neighbours it welds to, and a
    geometry change here would desync them (the ``_regrade_merged_host``
    rule).  Returns the number of shapes re-seated.
    """
    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    if _dem_at is None:
        return 0
    anchors = law_anchor_values(layout)
    key = law_anchor_key(layout, anchors)
    stats = _law_seat_stats(layout, "post_solve_groundside_law_seat")
    n = 0
    # Between-ring weld (finalarch item 1, see ``_SeatedWeldBook``):
    # groundside lots sharing a node weld to the FIRST-seated value and
    # absorb the level change over their own run.  Cross-pass welds
    # (lot↔service) already ride ``law_anchor_values`` — the service
    # pass runs first and its shipped values outrank a lot — so this
    # book carries only the lot↔lot debt.
    _weld_book = _SeatedWeldBook()
    _n_weld_pins = 0
    # SKIP BUCKETS, one per BRANCH, named by the CONDITION the branch
    # tests (cycle-7.5 instrument sweep, RULINGS 2026-08-06 binding point
    # 2).  Every one of these rings keeps whatever field it arrived with —
    # which for most of them is the pre-solve DEM seed — but they leave by
    # DIFFERENT doors, and a single count labelled "had no law source" is
    # the catch-all-bucket-with-a-cause pattern: a ring skipped at the
    # seed reader never reached the law ladder at all, so nothing was
    # learned about whether law reaches it.  Counted where the condition
    # is known, never inferred later.
    skips = stats.setdefault("skipped", {})

    def _skip(bucket):
        skips[bucket] = skips.get(bucket, 0) + 1

    for s in layout.shapes:
        if s.role != ROLE_GROUNDSIDE_PAVEMENT:
            continue
        stats["candidates"] = stats.get("candidates", 0) + 1
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            _skip("no_usable_polygon")
            continue
        try:
            ring = list(poly.exterior.coords)
        except _GEOM_EXC:
            _skip("ring_coords_raised")
            continue
        closed = len(ring) > 1 and ring[0] == ring[-1]
        if closed:
            ring = ring[:-1]
        if len(ring) < 3:
            _skip("ring_under_3_vertices")
            continue
        dem_alts = []
        for (x, y) in ring:
            d = _dem_at(x, y)
            dem_alts.append(None if d is None else float(d))
        if any(d is None for d in dem_alts):
            # Fall back to the ring's own current values as the seed
            # shape, so an off-tile vertex cannot inject a None.
            cur = list(getattr(s, "node_altitudes", None) or ())
            if len(cur) == len(ring) + 1:
                cur = cur[:-1]
            if len(cur) != len(ring) or any(v is None for v in cur):
                # SEED UNREADABLE — the DEM returned None somewhere AND
                # the ring's own field is the wrong length or carries a
                # None.  This ring never reaches the law ladder, so it is
                # NOT an observation about law reach; the old report
                # counted it nowhere and described it as an island.
                _skip("seed_altitudes_unreadable")
                continue
            dem_alts = [float(v) for v in cur]
        # EVERY RING, EVERY PASS — the ``already_law_seated`` skip is
        # RETIRED (cycle 8, measured at HEAZ).  ``_LAW_SEATED_ATTR`` says
        # a ring's field CAME FROM the law at least once; it never said
        # every VERTEX of the ring did.  A weld insert, a clip or a merge
        # adds vertices after the seat and those arrive on the DEM seed —
        # the STRANDED class, and the only class that mints a within-shape
        # row at all (a whole ring on the seed is FLAT and mints nothing).
        # The skip is what left HEAZ way -10280 shipping welds at ~59.8 m
        # beside vertices at −500.00: 559.84 m of step inside one shape,
        # the worst groundside row in that world, on a ring the pass
        # looked at and declined to touch.
        #
        # Re-seating is from the LAW ANCHORS and the BAND, never from the
        # ring's own current field: post-solve, ``law_anchor_values`` is
        # complete (every higher-authority surface carries its solved
        # value), so the welds ARE the best law available, while the
        # ring's own field is either those same welds or a seed that a
        # ring limiter has since smeared across the shape — and adopting a
        # smeared seed as a datum is exactly the laundering
        # ``_shape_prior`` refuses.
        ring_anchors = dict(anchors)
        _n_weld_pins += _weld_book.pin_ring(ring, ring_anchors, key)
        seat_out: dict = {}
        alts, pinned = _seat_ring_on_law_anchors(
            ring, dem_alts, ring_anchors, GROUNDSIDE_MAX_GRADE, key_fn=key,
            stats=stats, seat_out=seat_out, band_at=band_at)
        if not seat_out.get("law_seated"):
            # The ladder ran and found NO law source — no weld, no prior
            # field, and the ROUTE-GRAPH BAND does not reach this ring
            # either.  Under RULINGS 2026-08-06 ("ONE graph") that is the
            # TRULY DISCONNECTED class: not solved, left at its DEM seed,
            # minting nothing.  The shape is MARKED so the emitted sidecar
            # can carry this exact answer to the census — the coupling law
            # and the census adjudication land together, which is the
            # frontage-gap lesson written into a mechanism.
            setattr(s, _DISCONNECTED_ATTR, True)
            _skip("no_law_source_at_ladder")
            continue                    # not solved — counted, not moved
        if getattr(s, _DISCONNECTED_ATTR, False):
            # It reached the law this pass (a band arrived): the mark is a
            # statement about the CURRENT layout, never a sticky label.
            setattr(s, _DISCONNECTED_ATTR, False)
        alts = _grade_limit_ring(ring, alts, GROUNDSIDE_MAX_GRADE,
                                 pinned=pinned)
        alts = [round(float(a), 2) for a in alts]
        s.node_altitudes = alts + [alts[0]]
        s.altitude = None
        setattr(s, _LAW_SEATED_ATTR, True)
        n += 1
        for k, (x, y) in enumerate(ring):
            _weld_book.add(x, y, alts[k])
    stats["reseated"] = stats.get("reseated", 0) + n
    stats["between_ring_weld_pins"] = (
        stats.get("between_ring_weld_pins", 0) + _n_weld_pins)
    return n


def disconnected_rings_sidecar(layout) -> list:
    """``[[lat, lon], …]`` — one representative vertex per groundside ring
    the ONE route graph does not reach (``_DISCONNECTED_ATTR``).

    THE CENSUS'S HALF OF THE LOCKSTEP (RULINGS 2026-08-06, ONE graph
    binding point 3).  The solve's reachability answer is EXPORTED, never
    re-derived: a census that recomputed "is this ring connected" would be
    a second predicate, and the frontage-gap lesson (a coupling law
    landing without its seating authority) is precisely what that costs.
    Rows the census finds inside one of these rings are adjudicated
    OUT-OF-SCOPE — reported, never dropped, never counted as violations.

    Written unconditionally, so a reader can tell "no disconnected rings"
    from "this patch predates the law".
    """
    from .layout import ROLE_GROUNDSIDE_PAVEMENT
    out: list = []
    if getattr(layout, "anchor", None) is None:
        return out
    for s in (getattr(layout, "shapes", ()) or ()):
        if getattr(s, "role", "") != ROLE_GROUNDSIDE_PAVEMENT:
            continue
        if not getattr(s, _DISCONNECTED_ATTR, False):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        try:
            ring = list(poly.exterior.coords)
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        if len(ring) < 3:                                  # pragma: no cover
            continue
        try:
            pts = [[round(float(la), 11), round(float(lo), 11)]
                   for (la, lo) in (layout.m_to_ll(float(x), float(y))
                                    for (x, y) in ring)]
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        out.append(pts)
    return out


class _SeatedWeldBook:
    """Values this seating pass has already authored, by node identity.

    THE BETWEEN-RING DEBT (finalarch item 1; S1f dossier item 2,
    measured at HECA: 894 ``service_junction`` seatings at seam 14,
    worst step 3.260 m).  Each seat pass grades its ring WITHIN itself
    (``_grade_limit_ring`` closes the ring), but two seated rings
    sharing a node were seated in ISOLATION — the anchor map is built
    once, before the loop, so ring B never saw the value ring A had
    just written at their shared node.  Under weld-or-gap (RULINGS
    2026-08-13) a shared-node disagreement is ALWAYS a defect, and the
    seating minted exactly the between-shape census families
    (``mid_edge_step`` 42/45 new sites service_junction,
    ``vertex_to_edge_step`` 9/9, ``transverse`` 41/49).

    This book is the weld: every value a ring ships is recorded here,
    and a later ring PINS its shared vertices to the recorded value
    (rung-1 law anchor), then absorbs the level change over its own run
    under its cap — the S6 routing's "a losing lot adopting the
    winner's value must absorb the level change over its own run",
    implemented with the pass's own machinery and no new constant.

    Identity is the emitter's: nearest-within-``SHARED_VERTEX_TOL_M``
    (the ``law_anchor_key`` rule), so a vertex 3 mm off the node it
    welds to still finds it.  First writer wins — entries are never
    overwritten — so the winner is deterministic (layout order) and a
    solve-authored value pre-seeded ahead of the pass outranks any
    post-solve seat.
    """

    def __init__(self):
        from .canonical_points import CanonicalPointRegistry
        self._index = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
        self._values: dict = {}

    def add(self, x, y, value) -> None:
        k = _mm_key(x, y)
        if k in self._values:
            return                          # first writer wins
        self._index.add_exact(float(x), float(y))
        self._values[k] = float(value)

    def get(self, x, y):
        k = _mm_key(x, y)
        v = self._values.get(k)
        if v is not None:
            return v
        near = self._index.find_nearest(float(x), float(y),
                                        SHARED_VERTEX_TOL_M)
        if near is None:
            return None
        return self._values.get(_mm_key(near[0], near[1]))

    def pin_ring(self, ring, ring_anchors: dict, key_fn) -> int:
        """Pin ``ring``'s vertices to already-seated shared-node values.

        Adds entries to ``ring_anchors`` under each vertex's own
        ``key_fn`` key (the spelling ``_seat_ring_on_law_anchors`` looks
        up).  Existing entries — outranking law welds, the ring's own
        solved vertices — are never displaced.  Returns how many
        vertices were pinned by the book.
        """
        n = 0
        for (x, y) in ring:
            kk = key_fn(x, y)
            if kk in ring_anchors:
                continue
            v = self.get(x, y)
            if v is not None:
                ring_anchors[kk] = v
                n += 1
        return n


def seat_service_pavement_on_law(layout, dem, tile_lat: int = 0,
                                 tile_lon: int = 0, band_at=None) -> int:
    """POST-SOLVE: seat every SERVICE road / junction vertex the one solve
    never reached — the far ends of the service network.

    THE MECHANISM THIS CLOSES (RULINGS 2026-08-06, "ONE graph", measured
    at HEAZ).  Airside reachability never rides service spines
    (``REACH_NO_SERVICE_SPINES``, standing law), so a service junction
    whose ONLY connection to the network is a service road gets no band —
    and a node with no band keeps its DEM seed.  It then ships at raw DEM
    while the pavement it welds to sits at law: HEAZ emitted 12 service
    junctions with a way-level altitude ON the −500 m constant, and the
    lots welded to them graded down to meet them, which is where the
    worst groundside rows in the census came from.  The lot was obeying
    the law; the law source was wrong.

    THE SEAT IS THE MOUTH'S, PROPAGATED (the ruling verbatim): the band
    comes from :func:`building_feasibility.groundside_reach_band`, whose
    interval at a service node is the AIRSIDE value at the mouth the road
    leaves from, widened by the road's own 8 % budget along the route.
    The DEM seed then picks the value inside that interval.

    ONLY THE UNREACHED VERTICES MOVE.  A service vertex the solve DID
    seat carries a solved value, and overwriting it here would be exactly
    the second authority the single-solve architecture forbids.  The
    predicate is "the vertex is still sitting on its DEM seed"; every
    other vertex of the ring is kept and, better, is used as a LAW ANCHOR
    for the ones that move, so a partly-solved ring grades to its own
    solved half.

    Returns the number of shapes re-seated.
    """
    from .config import ROLE_GRADE_LIMITS, SERVICE_ROAD_MAX_GRADE
    from .layout import ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD
    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    if _dem_at is None:
        return 0
    stats = _law_seat_stats(layout, "post_solve_service_law_seat")
    skips = stats.setdefault("skipped", {})
    n = 0
    # ── THE BETWEEN-RING WELD (finalarch item 1; weld-or-gap) ────────
    # ONE book across both roles.  Pre-seeded with every SOLVE-authored
    # service vertex (a vertex not on its DEM seed) so a seat can never
    # step against a solved value it shares a node with — the solve is
    # the winner by authority, not by loop order.  Ring outputs join the
    # book as they ship; later rings pin shared nodes and absorb the
    # level change over their own run (see ``_SeatedWeldBook``).
    _weld_book = _SeatedWeldBook()
    for role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
        for s in layout.shapes:
            if getattr(s, "role", "") != role:
                continue
            poly = getattr(s, "polygon", None)
            if poly is None or poly.is_empty or poly.geom_type != "Polygon":
                continue
            try:
                ring = list(poly.exterior.coords)
            except _GEOM_EXC:                          # pragma: no cover
                continue
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            cur = list(getattr(s, "node_altitudes", None) or ())
            if len(cur) == len(ring) + 1:
                cur = cur[:-1]
            if len(cur) != len(ring):
                continue
            for k, (x, y) in enumerate(ring):
                if cur[k] is None:
                    continue
                d = _dem_at(x, y)
                if d is None or abs(float(cur[k]) - float(d)) \
                        > _SEED_MATCH_TOL_M:
                    _weld_book.add(x, y, float(cur[k]))
    _n_weld_pins = 0
    for role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
        # THE STRICTEST CAP OF THE CONTIGUOUS CROSS-SECTION, not the
        # road's own (RULINGS 2026-08-02, lateral-contiguity grade law,
        # FINAL: "the laterally-contiguous paved CROSS-SECTION takes the
        # STRICTEST cap of any class present in it").  These shapes weld
        # to groundside lots — that is the whole reason they matter here —
        # and a seat written at the road's 8 % hands the lot a datum field
        # its own 5 % law cannot follow: measured at HEAZ canyon, one lot
        # (way -10284, 17 vertices shared with service junctions) minted
        # 136 within-shape rows at up to 42 % doing exactly that.  A
        # STRICTER seat can never violate the looser law, so this is
        # conservative in the only direction that matters.
        cap = min(float(ROLE_GRADE_LIMITS.get(role)
                        or SERVICE_ROAD_MAX_GRADE),
                  float(GROUNDSIDE_MAX_GRADE))
        anchors = law_anchor_values(layout, for_role=role)
        key = law_anchor_key(layout, anchors)
        for s in layout.shapes:
            if getattr(s, "role", "") != role:
                continue
            stats["candidates"] = stats.get("candidates", 0) + 1
            poly = getattr(s, "polygon", None)
            if poly is None or poly.is_empty or poly.geom_type != "Polygon":
                skips["no_usable_polygon"] = skips.get(
                    "no_usable_polygon", 0) + 1
                continue
            try:
                ring = list(poly.exterior.coords)
            except _GEOM_EXC:                              # pragma: no cover
                skips["ring_coords_raised"] = skips.get(
                    "ring_coords_raised", 0) + 1
                continue
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) < 3:
                skips["ring_under_3_vertices"] = skips.get(
                    "ring_under_3_vertices", 0) + 1
                continue
            dem_alts = [(_dem_at(x, y)) for (x, y) in ring]
            if any(d is None for d in dem_alts):
                skips["seed_altitudes_unreadable"] = skips.get(
                    "seed_altitudes_unreadable", 0) + 1
                continue
            dem_alts = [float(d) for d in dem_alts]
            cur = list(getattr(s, "node_altitudes", None) or ())
            if len(cur) == len(ring) + 1:
                cur = cur[:-1]
            if len(cur) != len(ring):
                flat = getattr(s, "altitude", None)
                cur = ([float(flat)] * len(ring) if flat is not None
                       else [None] * len(ring))
            on_seed = [k for k in range(len(ring))
                       if cur[k] is None
                       or abs(float(cur[k]) - dem_alts[k]) <= _SEED_MATCH_TOL_M]
            if not on_seed:
                skips["solve_seated_every_vertex"] = skips.get(
                    "solve_seated_every_vertex", 0) + 1
                continue
            ring_anchors = dict(anchors)
            for k in range(len(ring)):
                if k in on_seed or cur[k] is None:
                    continue
                ring_anchors.setdefault(key(ring[k][0], ring[k][1]),
                                        float(cur[k]))
            # Between-ring weld: pin shared nodes an earlier ring (or
            # the solve) already valued.  Outranking law anchors and the
            # ring's own solved vertices, added above, are never
            # displaced.
            _n_weld_pins += _weld_book.pin_ring(ring, ring_anchors, key)
            seat_out: dict = {}
            alts, pinned = _seat_ring_on_law_anchors(
                ring, dem_alts, ring_anchors, cap, key_fn=key,
                stats=stats, seat_out=seat_out, band_at=band_at)
            if not seat_out.get("law_seated"):
                skips["no_law_source_at_ladder"] = skips.get(
                    "no_law_source_at_ladder", 0) + 1
                continue
            alts = _grade_limit_ring(ring, alts, cap, pinned=pinned)
            alts = [round(float(a), 2) for a in alts]
            s.node_altitudes = alts + [alts[0]]
            s.altitude = None
            n += 1
            # The ring's SHIPPED values join the book (first writer
            # wins), so every later ring welds to what actually emitted.
            for k, (x, y) in enumerate(ring):
                _weld_book.add(x, y, alts[k])
    stats["reseated"] = stats.get("reseated", 0) + n
    stats["between_ring_weld_pins"] = (
        stats.get("between_ring_weld_pins", 0) + _n_weld_pins)
    return n


def report_groundside_law_seat(layout, icao: str = "") -> dict:
    """Print (and return) what every groundside ring was seated ON.

    LOUD BY DEFAULT.  The ingestion requirement is that a ring vertex
    never takes raw DEM, so the number that matters is ``islands`` — the
    rings that reached the seat with no weld and no prior field.  A
    nonzero count is a defect to attribute under RULINGS 2026-08-05
    (a)-(d), not a tolerated residue, and it is printed even when zero so
    an absent line means the pass did not run.

    WHAT CHANGED IN THE CYCLE-7.5 SWEEP (RULINGS 2026-08-06):

    * the island line said the rings *"had no law source and kept their
      DEM seed"* — one causal label over several distinct exit
      conditions.  ``islands`` counts exactly one of them (the ladder ran
      and ``law_at`` came back empty); a ring whose seed altitudes could
      not be READ leaves ``seat_groundside_on_law`` before the ladder and
      was described by that sentence while being counted by nothing.
      Each condition is now counted at its own branch and printed under
      its own NAME, and the line states the ladder condition instead of
      inferring a cause;
    * the line carried ``icao`` and no frame at all, on an instrument
      whose entire subject is whether a value is DEM-derived.  The DEM
      world, the tree sha and the node space are stamped;
    * ``island_vertices`` was a bare total with no way to locate a single
      one of them, which defeats this docstring's own "attribute it"
      claim.  Up to ``_ISLAND_XY_CAP`` per-ring locators are reported.
    """
    import O4_UI_Utils as UI
    book = getattr(layout, "_gs_law_seat", None) or {}
    tot = {"rings": 0, "anchored": 0, "from_prior": 0, "interpolated": 0,
           "islands": 0, "island_vertices": 0, "candidates": 0,
           "reseated": 0}
    skipped: dict = {}
    island_xy: list = []
    for st in book.values():
        for k in tot:
            tot[k] += int(st.get(k, 0) or 0)
        for bucket, cnt in (st.get("skipped") or {}).items():
            skipped[bucket] = skipped.get(bucket, 0) + int(cnt or 0)
        for xy in (st.get("island_xy") or ()):
            if len(island_xy) < _ISLAND_XY_CAP:
                island_xy.append(tuple(xy))
    tot["skipped"] = skipped
    tot["island_xy"] = island_xy
    # FRAME STAMP.  The world comes from the DEM objects this module
    # actually sampled (``_dem_sampler``), not from a second reading.
    worlds = sorted(getattr(layout, "_gs_dem_worlds", None) or ())
    tot["dem_worlds"] = list(worlds)
    try:
        from .elevation_per_surface.building_feasibility import (
            instrument_tree_sha)
        _tree = instrument_tree_sha()
    except Exception:                                  # pragma: no cover
        _tree = "?"
    frame = (f"[frame tree={_tree} "
             f"dem_world={'+'.join(worlds) if worlds else '?'} "
             f"nodes=groundside ring vertices, layout-local metres about "
             f"layout.anchor (NOT solver node ids) "
             f"values=emitted groundside altitudes (uncrowned; groundside "
             f"carries no crown drop)]")
    tot["frame"] = frame
    UI.vprint(1, f"  [groundside-law-seat] {icao}: {tot['rings']} ring(s) "
                 f"seated — {tot['anchored']} weld anchor(s), "
                 f"{tot['from_prior']} vertex(es) from the piece's own "
                 f"prior field, {tot['interpolated']} law-interpolated "
                 f"along the ring; {tot['islands']} ring(s) "
                 f"({tot['island_vertices']} vertex(es)) reached the law "
                 f"ladder with NO weld anchor and NO prior field "
                 f"(condition: law_at empty) and kept the field they "
                 f"arrived with.  {frame}")
    if island_xy:
        UI.vprint(1, f"  [groundside-law-seat]   island ring locator(s), "
                     f"first vertex, up to {_ISLAND_XY_CAP}: "
                     + ", ".join(f"({x:.2f},{y:.2f})" for (x, y) in island_xy))
    # THE DISCONNECTED COUNT, from the MARKS the census will read — not
    # from the skip counter, which counts LADDER EXITS across passes.  If
    # these two disagree, the sidecar and the report are describing
    # different populations, and this line is where that shows.
    marked = sum(1 for s in (getattr(layout, "shapes", ()) or ())
                 if getattr(s, _DISCONNECTED_ATTR, False))
    tot["disconnected_marked"] = marked
    UI.vprint(1, f"  [groundside-law-seat]   {marked} groundside ring(s) "
                 f"MARKED disconnected (no weld, no prior, no band) — the "
                 f"sidecar carries them and the census adjudicates their "
                 f"rows OUT OF SCOPE")
    if skipped:
        # NAMED CONDITIONS, not a cause.  Each bucket is the branch that
        # returned the ring, spelled as the test that branch performs.
        UI.vprint(1, f"  [groundside-law-seat]   post-solve seat pass: "
                     f"{tot['reseated']} of {tot['candidates']} groundside "
                     f"ring(s) re-seated; skipped by condition — "
                     + ", ".join(f"{k}={v}" for k, v in
                                 sorted(skipped.items(),
                                        key=lambda kv: -kv[1])))
    for where, st in sorted(book.items(),
                            key=lambda kv: -int(kv[1].get("islands", 0) or 0)):
        if st.get("islands"):
            UI.vprint(1, f"  [groundside-law-seat]   {st['islands']:5d} "
                         f"island ring(s) at {where}")
    return tot


def _dem_follow_polygon(p, _dem_at, densify_step_m: float = 15.0,
                        simplify_tol: float = GROUNDSIDE_SIMPLIFY_TOL_M,
                        law_anchors=None, anchor_key=None, prior=None,
                        stats=None, seat_out=None):
    """Densify ``p``, SEED it from the DEM, and grade it to the groundside
    law — returning ``(densified_polygon, node_altitudes)`` (node_altitudes
    closed with a repeated first value, matching the OSM emitter's
    convention) or ``None`` if it can't be built.

    Shared by ``_emit_groundside_pavement_dem`` and the groundside-orphan
    reclassify so both grade identically — a polygon that abuts graded
    groundside stays flush with it (no cliff).

    ``law_anchors`` — ``{(x, y): elevation}`` from :func:`law_anchor_values`:
    the values the higher-authority surfaces this shape WELDS TO already
    carry.  With them the ring is seated on its law datum and the DEM
    supplies relief only (:func:`_seat_ring_on_law_anchors`); without them
    (a legacy caller, or a genuine law island with no weld) the behaviour
    is the historical DEM follow, and the shape is a law-island to
    attribute rather than a surface to invent a datum for.
    """
    if p is None or p.is_empty or p.geom_type != "Polygon":
        return None
    # Open any interior ring (hole) to the exterior before emitting: the
    # OSM emitter writes only the exterior ring, so an enclosed hole (a
    # building the separation pass subtracted out) would silently re-cover
    # its footprint (SPJC building #31 ⊂ groundside #455).  The nearest-
    # edge corridor keeps the polygon a single connected piece; if it ever
    # splits, follow the largest piece (this function returns one shape).
    if p.interiors:
        opened = _open_polygon_holes(p)
        if not opened:
            return None
        p = max(opened, key=lambda g: g.area)
    # Simplify pass: drop over-resolved boundary detail before densifying
    # so the per-vertex-DEM emit carries fewer nodes.  Densify below
    # re-establishes uniform altitude sampling on the simplified ring.
    # The separation pass passes a SMALL tol (< its clearance) so this
    # only removes the sub-metre clip-boundary edges that would otherwise
    # inflate the per-vertex grade after 0.1 m altitude rounding — without
    # moving the boundary back across the clearance gap it just cut.
    if simplify_tol > 0:
        try:
            s = p.simplify(simplify_tol, preserve_topology=True)
            if s.geom_type == "Polygon" and not s.is_empty and s.is_valid:
                p = s
        except _GEOM_EXC:
            pass
    try:
        ring = list(p.exterior.coords)
    except _GEOM_EXC:
        return None
    if not ring:
        return None
    if ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return None
    # Truncate needle-tip corners (interior angle below the Triangle4XP
    # sliver threshold) at SOURCE: the OSM emitter drops any polygon that
    # still carries one, and dropping a whole groundside shape uncovers
    # its entire source footprint (HECA: a 30-vertex strip lost to one
    # 1.62° tip → two interior coverage gaps).  Truncation loses only the
    # sub-50 m² wedge beyond the chord.
    from .pavement.junctions import _drop_sliver_corners
    ring = _drop_sliver_corners(ring)
    if len(ring) < 3:
        return None
    # Densify so per-vertex altitudes resolve well across long edges.
    densified: List[Tuple[float, float]] = []
    n_r = len(ring)
    for i in range(n_r):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n_r]
        densified.append((ax, ay))
        edge_len = math.hypot(bx - ax, by - ay)
        if edge_len <= densify_step_m:
            continue
        n_intermediate = int(edge_len // densify_step_m)
        for k in range(1, n_intermediate + 1):
            t = (k * densify_step_m) / edge_len
            if t >= 1.0:
                break
            densified.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    if len(densified) < 3:
        return None
    # Sample DEM at every densified vertex; walk outward to the nearest
    # valid sample for any point that lands outside the DEM tile.
    alts: List[Optional[float]] = [_dem_at(x, y) for x, y in densified]
    if all(a is None for a in alts):
        return None
    for k, a in enumerate(alts):
        if a is not None:
            continue
        found: Optional[float] = None
        for off in range(1, len(alts)):
            left = (k - off) % len(alts)
            right = (k + off) % len(alts)
            if alts[left] is not None:
                found = alts[left]
                break
            if alts[right] is not None:
                found = alts[right]
                break
        assert found is not None, (
            "groundside: walk-outward DEM neighbour search failed despite "
            "precondition ensuring at least one valid sample")
        alts[k] = found
    # Rebuild from densified coords so the polygon and node_altitudes
    # stay 1-for-1; re-sample if buffer(0) validity repair changed the
    # vertex count.
    try:
        new_poly = Polygon(densified)
        if not new_poly.is_valid:
            new_poly = new_poly.buffer(0)
        if new_poly.geom_type != "Polygon" or new_poly.is_empty:
            return None
    except _GEOM_EXC:
        return None
    rebuilt = list(new_poly.exterior.coords)
    if rebuilt and rebuilt[0] == rebuilt[-1]:
        rebuilt = rebuilt[:-1]
    if len(rebuilt) != len(densified):
        alts = [(_dem_at(x, y) or 0.0) for x, y in rebuilt]
    else:
        alts = [float(a) for a in alts]
    # ── SEAT ON THE LAW, THEN GRADE-LIMIT ────────────────────────────
    # The DEM values above are the SEED.  Where this ring welds to a
    # higher-authority surface, that surface's value is the DATUM and the
    # seed contributes only relief within the lot cap; the ring limiter
    # then closes any residual adjacent-pair excess, holding the welds
    # fixed.  (Previously the DEM values went straight into the limiter,
    # so the terrain was the authority and the welds were overwritten at
    # emit — the 9 914 m HEAZ canyon row.)
    alts, _pinned = _seat_ring_on_law_anchors(
        rebuilt, alts, law_anchors, GROUNDSIDE_MAX_GRADE,
        key_fn=anchor_key, prior_at=_prior_field_reader(prior),
        stats=stats, seat_out=seat_out)
    # Grade-limit to the SHAPING cap (ramp-graded, user 2026-05-22)
    # before rounding.  2 decimals, matching the emit resolution — 0.1 m
    # quantization on sub-metre groundside chords reads as 10-15 % stairs
    # (the V15 waviness class).
    alts = _grade_limit_ring(rebuilt, alts, GROUNDSIDE_MAX_GRADE,
                             pinned=_pinned)
    alts = [round(float(a), 2) for a in alts]
    return new_poly, alts + [alts[0]]


def _regrade_merged_host(host, _dem_at) -> Optional[float]:
    """Re-run the LOT EMITTER'S ramp-limited DEM follow over a groundside
    host whose ring has just absorbed one or more road stretches.

    Ruling (2026-08-03, on the kill-prep round's measured absorbed-surface
    defect): the merged lot+road polygon is ONE surface and gets graded as
    ONE.  Moving the host's PRE-EXISTING vertices is lawful — the host is
    groundside and this is groundside's own law.

    Only the ALTITUDE half of :func:`_dem_follow_polygon` is re-run.  The
    ring itself is left exactly as the merge built it, because its
    vertices are shared with the neighbours the absorbed stretch was
    welded to; a re-simplify / re-densify here would desync those shared
    nodes and tear the arrangement.  "Sample the DEM at every vertex, then
    ramp-limit the ring at ``GROUNDSIDE_MAX_GRADE``" IS the lot law —
    densify and simplify are emit-resolution choices, not law.

    Why the whole ring and not just the new vertices: FIX ATTEMPT 1
    (2026-08-03) gave the NEW vertices raw DEM and left the host's own
    alone, and measured WORSE (CYXY within-shape 189 → 275) because the
    old/new boundary then carried the full DEM-vs-interpolated step at
    sub-metre spacing.  The step exists precisely BECAUSE the two halves
    were graded by different authorities; one authority over the whole
    merged ring removes it at source, and the ring limiter bounds every
    adjacent pair including the sub-metre ones.

    Returns the worst adjacent ring grade after the regrade (for the
    round's log line), or ``None`` when it could not run — no DEM
    sampler (every legacy caller), or a degenerate ring — in which case
    the host keeps exactly what the merge left it.
    """
    if _dem_at is None or host is None:
        return None
    poly = getattr(host, "polygon", None)
    if poly is None or poly.is_empty or poly.geom_type != "Polygon":
        return None
    try:
        ring = list(poly.exterior.coords)
    except _GEOM_EXC:
        return None
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return None
    alts: List[Optional[float]] = [_dem_at(x, y) for x, y in ring]
    if all(a is None for a in alts):
        return None
    # Walk outward to the nearest valid sample for any vertex outside the
    # DEM tile — the same rule ``_dem_follow_polygon`` uses, so a merged
    # ring and a freshly-emitted one treat tile edges identically.
    for k, a in enumerate(alts):
        if a is not None:
            continue
        found: Optional[float] = None
        for off in range(1, len(alts)):
            if alts[(k - off) % len(alts)] is not None:
                found = alts[(k - off) % len(alts)]
                break
            if alts[(k + off) % len(alts)] is not None:
                found = alts[(k + off) % len(alts)]
                break
        assert found is not None, (
            "groundside: walk-outward DEM neighbour search failed despite "
            "precondition ensuring at least one valid sample")
        alts[k] = found
    vals = _grade_limit_ring(ring, [float(a) for a in alts],
                             GROUNDSIDE_MAX_GRADE)
    vals = [round(float(v), 2) for v in vals]
    host.node_altitudes = vals + [vals[0]]      # the CLOSED convention
    host.altitude = None
    host.altitude_high = None
    host.altitude_low = None
    worst = 0.0
    n = len(ring)
    for k in range(n):
        (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % n]
        d = math.hypot(x1 - x0, y1 - y0)
        if d > 1e-6:
            worst = max(worst, abs(vals[(k + 1) % n] - vals[k]) / d)
    return worst


# MEASURED AND REJECTED (perf P3 lane F, HECA 2026-08-13).  A component
# BBOX PREFILTER over ``pav_union`` — STRtree over its own disjoint
# components, only the ones whose envelope meets the 120 m probe's handed
# to ``intersection`` — was built, twinned output-inert and proved
# byte-identical at HECA, and it bought **0.5 s of 26.2 s across 39,663
# stations**.  It is not the union's COMPONENT COUNT that costs here, so
# splitting the union by component buys nothing; the cost is one overlay
# per station against a pavement body the probe mostly does not touch.
# The next lever at this site is therefore a per-line (or per-run) CLIP
# of the union to the band the probe can reach — which inserts vertices
# on the clip boundary and so is NOT float-free, and must be gated on the
# frozen body hash rather than argued.  Recorded rather than left for the
# next lane to rediscover.
def _svc_contiguous_cross_section(line, arc, pav_union,
                                  probe: float = 60.0):
    """The contiguous pavement CROSS-SECTION chord at arc-length ``arc``
    of a service centerline — THE measurement, of which
    :func:`_svc_contiguous_width` is the length.

    Returns the chord as a ``LineString``; an EMPTY ``LineString`` when
    the road crosses open terrain there (the old ``0.0``); ``None`` on
    geometry failure (callers treat that as NOT road-width —
    conservative, never carve on a broken measurement).

    The chord itself — not just its length — is what R7a's landside term
    needs (owner ruling 2026-08-15): the question "is this wide pavement
    an apron or a landside lot" is answered by asking the airside
    evidence layer whether it touches THIS chord.  Splitting the width
    out of the geometry would have been a second cross-section
    measurement, and the free-road filter and the narrow-strip carve
    exist in lockstep precisely because there is only one.
    """
    p = line.interpolate(arc)
    q = line.interpolate(min(arc + 1.0, line.length))
    dx, dy = q.x - p.x, q.y - p.y
    dn = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / dn, dx / dn
    cross = LineString([(p.x - nx * probe, p.y - ny * probe),
                        (p.x + nx * probe, p.y + ny * probe)])
    try:
        inter = cross.intersection(pav_union)
    except _GEOM_EXC:
        return None
    parts = ([inter] if inter.geom_type == "LineString"
             else list(getattr(inter, "geoms", ())))
    for part in parts:
        if part.geom_type == "LineString" and part.distance(p) < 2.0:
            return part
    return LineString()


def _svc_contiguous_width(line, arc, pav_union, probe: float = 60.0):
    """Contiguous pavement cross-section (m) at arc-length ``arc`` of a
    service centerline — the ONE measurement both the narrow-strip carve
    and the free-road slice filter key on, so they cannot drift.  ``None``
    on geometry failure (callers treat that as NOT road-width —
    conservative, never carve on a broken measurement)."""
    part = _svc_contiguous_cross_section(line, arc, pav_union, probe=probe)
    return None if part is None else part.length


def free_road_subsegments(lines, pav_union, *,
                          landside_evidence=None,
                          narrow_width_m: float = 25.0,
                          sample_step_m: float = 5.0,
                          min_run_m: float = 12.0):
    """The sub-segments of ``lines`` along which a road is COMPLETELY
    FREE — owner ruling 2026-07-27 (canonical text):

        "Any road inside, or sharing an edge with an apron must be
        graded the same as the apron, so essentially just becomes part
        of the apron and never needs to be carved in the first place.
        We only want completely free roads, with no pavement on either
        side of road-width pavement, to be graded as roads."

    A station is FREE when the contiguous pavement cross-section there
    is at most ``narrow_width_m`` (the pavement IS the road — the same
    standing 25 m rule ``carve_narrow_service_strips`` carves by) or
    zero (the road runs over open terrain).  A station inside or along
    WIDER pavement is part of the apron: feeding it to the slice would
    cut a face the classifiers then mis-role — the SPJC east-terminal
    frontage (109 k m² of phantom ``service_junction``) and HECA's
    "svc junctions 4→76" carve were exactly this.  Consecutive free
    stations group into intervals; intervals shorter than ``min_run_m``
    are dropped (a road momentarily narrow inside an apron is still the
    apron's road).

    R7a — THE LANDSIDE TERM (owner ruling 2026-08-15, "roads carry
    spines like taxiways … the free-road width test gains its missing
    landside term").  The ruling above says APRON, and the width test
    read only WIDTH.  A DSF ``.pol`` pack delivers apron and car park as
    one undifferentiated pavement blob, so every wide LANDSIDE lot read
    as "an apron the road is inside of" and swallowed the public road
    whole: measured at CYXY, lot 377 dropped 82-93 % of the road's
    stations and then valued the strip it had taken by its own
    lot law, 3.2 m away from the road faces either side of it; at HECA
    142 of 160 groundside shapes contain a road on these terms.

    THE TERM IS POSITIVE (Fable AMENDMENT A1, 2026-08-15 late).  The
    first arm asked for positive AIRSIDE evidence and read its ABSENCE
    as landside; that is refuted at exactly the airports this feature
    exists for, because at a DSF-pack airport genuine apron routinely
    carries no OSM ``aeroway`` and no apt.dat row-110 name, so "no
    airside evidence" is the normal reading of real aircraft pavement.
    A wide station therefore stays APRON — dropped, as the 2026-07-27
    ruling says — unless there is POSITIVE LANDSIDE EVIDENCE for the
    cross-section it actually stands in: ``landside_evidence`` (a
    ``pavement_classification.CoverIndex``:
    ``pavement_classification.landside_evidence_layer`` — the
    parking-aisle corridor layer, and pavement outside the runway-touch
    connectivity chain).  Wide pavement WITH landside evidence keeps the
    knife: the road cuts its own face through the lot and scores as a
    road.

    The two classes the width test was built for are preserved BY
    CONSTRUCTION — SPJC's east terminal and HECA's svc-junction aprons
    are aircraft pavement chained to a runway and carry no parking
    aisles, so neither landside term fires and their wide stations are
    still dropped.

    ``landside_evidence=None`` is the WIDTH-ONLY fallback (synthetic
    callers and the pre-R7a law): with no evidence layer to ask, every
    wide station is treated as apron, exactly as before.  Production
    passes the layer — see ``pipeline`` at the free-road scoping site.

    Pure function over LineStrings — the slice feeds the result in
    place of the raw service set; the narrow-strip carve keeps its own
    identical per-station test.

    Interval ends SNAP to the nearest ORIGINAL vertex within one sample
    step; interior vertices are carried over exactly, and a cut that
    genuinely falls mid-segment interpolates only there — at least a
    full sample step from any original vertex.  A blind ``substring()``
    minted endpoints ~mm off source vertices, and the solver/validator
    budget lockstep test caught exactly that (CYXY: one shared edge,
    7.7e-5 budget drift on near-duplicate vertices).
    """
    if pav_union is None or pav_union.is_empty:
        return list(lines)
    out = []
    for line in lines:
        if line is None or line.is_empty or line.length < min_run_m:
            continue
        n_st = max(2, int(line.length / sample_step_m) + 1)
        arcs = [line.length * k / (n_st - 1) for k in range(n_st)]
        free = []
        for arc in arcs:
            part = _svc_contiguous_cross_section(line, arc, pav_union)
            if part is None:                    # broken measurement
                free.append(False)
                continue
            if part.length <= narrow_width_m:   # the pavement IS the road
                free.append(True)
                continue
            # WIDE.  Apron — unless there is POSITIVE LANDSIDE evidence
            # for THIS cross-section (R7a, amendment A1), in which case
            # the station stays a knife.
            free.append(landside_evidence is not None
                        and landside_evidence.intersects(part))
        coords = list(line.coords)
        vertex_arcs = [0.0]
        for (xa, ya), (xb, yb) in zip(coords, coords[1:]):
            vertex_arcs.append(vertex_arcs[-1]
                               + math.hypot(xb - xa, yb - ya))

        def _snap(a):
            best = min(range(len(vertex_arcs)),
                       key=lambda i: abs(vertex_arcs[i] - a))
            if abs(vertex_arcs[best] - a) <= sample_step_m:
                return vertex_arcs[best]
            return a

        k = 0
        while k < len(arcs):
            if not free[k]:
                k += 1
                continue
            k2 = k
            while k2 + 1 < len(arcs) and free[k2 + 1]:
                k2 += 1
            a1, a2 = _snap(arcs[k]), _snap(arcs[k2])
            k = k2 + 1
            if a2 - a1 < min_run_m:
                continue
            pts = []
            if a1 not in vertex_arcs:
                p = line.interpolate(a1)
                pts.append((p.x, p.y))
            pts.extend(coords[i] for i, va in enumerate(vertex_arcs)
                       if a1 - 1e-9 <= va <= a2 + 1e-9)
            if a2 not in vertex_arcs:
                p = line.interpolate(a2)
                pts.append((p.x, p.y))
            if len(pts) < 2:
                continue
            try:
                seg = LineString(pts)
            except _GEOM_EXC:
                continue
            if not seg.is_empty and seg.length >= min_run_m:
                out.append(seg)
    return out


# ═════════════════════════════════════════════════════════════════════════
# LATERAL-CONTIGUITY GRADE LAW — clauses (2)-(5)
# (owner-confirmed FINAL 2026-08-02; the law itself is
#  ``grade_law.lateral_contiguity_cap`` / ``…_segments``)
# ═════════════════════════════════════════════════════════════════════════
# Clause (1) — the FREE road — is ``free_road_subsegments`` above: only the
# sub-segments with nothing paved beside them ever reach the slice, so a road
# inside an apron is absorbed by NEVER BEING CARVED.  This pass is the same
# ruling for the roads that DO exist as their own faces: at every station of a
# road-family shape it takes the laterally-contiguous paved cross-section,
# reads the strictest cap present, and either ABSORBS the stretch into the
# adjacent surface (clause 4, the preferred form) or, where the surface that
# owns the cap is not the piece's own neighbour, carries the cap on the piece
# (``BuiltShape.lateral_cap`` — solver + validator lockstep).

# The station walk itself is ``auto_patch.lateral_contiguity`` — ONE
# instrument, shared verbatim with ``tools/check_grade``'s twin, so the two
# readers cannot census different station sets (they did, once: a road the
# validator flagged had never been walked by the emitter's own axis
# convention — SPLP way -10009).
from .lateral_contiguity import (          # noqa: E402
    GAP_TOL_M as _LATERAL_GAP_TOL_M,
    MIN_MEMBER_M as _LATERAL_MIN_MEMBER_M,
    PROBE_M as _LATERAL_PROBE_M,
    station_caps as _lateral_station_caps,
    station_normal as _lateral_station_normal,
)


def apply_lateral_contiguity_law(layout, icao: str = "", *,
                                 rebind_only: bool = False,
                                 dem_at=None) -> dict:
    """Clauses (2)-(5) of the lateral-contiguity grade law, per SEGMENT.

    ``rebind_only`` re-evaluates the CAP against the final pre-solve
    arrangement and changes NO geometry.  The law has to bind what actually
    ships: the geometric half (absorb / cut) must run early, while the
    conformance and planarize passes can still weld the rings it makes,
    but many passes move roles and split shapes between there and the
    solve — measured at HECA, 255 of 281 residual stations sat on shapes
    that carried no cap at all because they did not exist, or were not
    roads, when the geometric pass ran.  So the pass runs twice with ONE
    law and ONE walker: geometry early, the number late.

    For every road-family shape: walk its axis, read the laterally-contiguous
    paved cross-section at each 5 m station, and take the STRICTEST cap of the
    classes present (``grade_law.lateral_contiguity_cap``).  Consecutive
    stations of equal cap form a SEGMENT
    (``grade_law.lateral_contiguity_segments``); the shape is cut at the
    segment boundaries with the existing mouth machinery
    (``pavement.apron_necks._cut_at_mouth``, the transverse chord across the
    road at the boundary station), and each segment is then either:

      * ABSORBED into the adjacent surface that owns its cap (clause 4 —
        merged, so the road stops being a separate shape at all), when that
        surface is a LITERAL neighbour of the piece and neither side carries
        per-vertex altitudes (a DEM-followed groundside lot's
        ``node_altitudes`` align 1:1 with its ring, and a merge would
        silently misalign them); or
      * kept, carrying ``lateral_cap`` — the strictest cap, read by the
        solver (``grade_graph._body_cap``) and stamped for the validator.

    Stations inside a RUNWAY STRIP footprint get no verdict (clause 5: the
    strip footprint law supersedes there).

    ``dem_at`` (``f(x, y) -> Optional[float]``) is the groundside DEM
    sampler used to RE-GRADE a merged host as one surface
    (:func:`_regrade_merged_host`, ruling 2026-08-03: the merged lot+road
    polygon is ONE surface and gets graded as ONE).  ``None`` — synthetic
    callers and tests — leaves the merge's own field in place.

    History, so the reverted attempt is not re-tried: passing this sampler
    to ``_merge_piece_into_apron``'s ``alt_for_new`` instead, i.e. raw DEM
    for the NEW vertices only with the host's own left alone, was MEASURED
    WORSE (CYXY within-shape 189 → 275 rows) — the old/new boundary then
    carries the full DEM-vs-interpolated step at sub-metre spacing.  The
    merge is therefore still done with the interpolated field and the
    WHOLE ring is re-followed and ramp-limited afterwards.

    Returns a summary dict; ``layout.shapes`` is rebuilt in place.
    """
    from .config import (LATERAL_CONTIGUITY_LAW_ENABLED,
                         SERVICE_LOT_ABSORPTION as _CLASS_UNIVERSAL)
    summary = {"roads": 0, "segments": 0, "absorbed": 0, "capped": 0,
               "cut": 0, "strip_skipped": 0, "rebound": 0, "released": 0,
               # class-universal absorption (owner 2026-08-03) bookkeeping:
               # stretches merged into a host that carries per-vertex
               # altitudes, pieces the mouth cut could NOT separate (never
               # absorbed — the owner's uncut-road defect), and merges that
               # failed and fell back to carrying the cap.
               "absorbed_dem_host": 0, "cut_failed": 0, "merge_failed": 0,
               "absorbed_caps": {},
               # merged-surface lawfulness (ruling 2026-08-03): hosts whose
               # whole ring was re-followed and ramp-limited as ONE surface,
               # and the worst adjacent ring grade left behind.
               "host_regraded": 0, "host_regrade_worst": 0.0,
               # CONTEXT-CONSERVATIVE ABSORPTION (membership round V2,
               # spec §V2.A): absorbed stretches whose FOOTPRINT was
               # retained for the solve's context sets, split by whether
               # the host was a DEM-followed (groundside) one.
               "context_retained": 0, "context_retained_dem_host": 0}
    if not LATERAL_CONTIGUITY_LAW_ENABLED:
        return summary
    from shapely.strtree import STRtree
    from .config import ROLE_GRADE_LIMITS
    from .grade_law import (LATERAL_CONTIGUITY_ROAD_ROLES,
                            lateral_contiguity_segments)
    from .pavement.apron_necks import _cut_at_mouth

    def _pav(s):
        return (s.polygon is not None and not s.polygon.is_empty
                and s.polygon.geom_type == "Polygon"
                and ROLE_GRADE_LIMITS.get(s.role) is not None)

    shapes = list(layout.shapes)
    idx = [i for i, s in enumerate(shapes) if _pav(s)]
    if not idx:
        return summary
    polys = [shapes[i].polygon for i in idx]
    roles = [shapes[i].role for i in idx]
    pos = {i: k for k, i in enumerate(idx)}
    tree = STRtree(polys)
    strip = None
    try:
        from .adjacent_ground import runway_strip_wall_keepout
        strip = runway_strip_wall_keepout(layout, require_gate=False)
    except Exception:
        strip = None

    absorbed_into: dict = {}        # shape index -> [pieces to merge]
    drop: set = set()
    add: list = []
    for i, s in enumerate(shapes):
        if s.role not in LATERAL_CONTIGUITY_ROAD_ROLES or not _pav(s):
            continue
        own_cap = ROLE_GRADE_LIMITS.get(s.role)
        summary["roads"] += 1
        normal = _lateral_station_normal(s.polygon)
        if normal is None:
            continue
        nx, ny = normal
        # THE census — the same call ``tools/check_grade`` makes.
        stations, caps = _lateral_station_caps(
            s.polygon, tree, polys, roles, pos.get(i), keepout=strip)
        if not stations:
            continue
        summary["strip_skipped"] += sum(
            1 for st, cap in zip(stations, caps)
            if st is not None and cap is None and strip is not None
            and strip.covers(Point(st)))
        runs = lateral_contiguity_segments(caps)
        if not runs:
            if rebind_only and s.lateral_cap is not None:
                s.lateral_cap = None
                summary["released"] += 1
            continue
        summary["segments"] += len(runs)
        binding = [r for r in runs if r[2] < own_cap - 1e-12]
        if rebind_only:
            # LATE BINDING: the number only, against the arrangement that
            # ships.  A road whose neighbours moved out from beside it
            # RELEASES its cap — the law tightens where it applies and
            # nowhere else.
            new_cap = min((r[2] for r in binding), default=None)
            if new_cap != s.lateral_cap:
                s.lateral_cap = new_cap
                summary["rebound"] += 1
            if new_cap is not None:
                summary["capped"] += 1
            continue
        if not binding:
            continue
        # A road that carries PER-VERTEX altitudes (a DEM-followed piece) is
        # never cut or rebuilt — its ``node_altitudes`` align 1:1 with the
        # ring it has.  It still takes the law: the STRICTEST cap any of its
        # stations saw, carried in place.
        if s.node_altitudes is not None:
            s.lateral_cap = min(r[2] for r in binding)
            summary["capped"] += 1
            continue
        pieces = _lateral_split(s.polygon, stations, caps, runs, nx, ny,
                                _cut_at_mouth)
        if pieces is None:
            continue
        if len(pieces) > 1:
            summary["cut"] += 1
        for piece, cap, uniform in pieces:
            if cap is None or cap >= own_cap - 1e-12:
                add.append(_lateral_piece_shape(s, piece, None,
                                                split=len(pieces) > 1))
                continue
            # PORTION-ONLY (owner 2026-08-03): a piece the mouth cut could
            # not separate still holds stations of DIFFERENT caps — its free
            # stretch is in there.  Absorbing it would absorb the free road
            # end-to-end, which is the defect; it carries the strictest cap
            # instead and the failure is counted, never hidden.
            if _CLASS_UNIVERSAL and not uniform:
                summary["cut_failed"] += 1
                add.append(_lateral_piece_shape(s, piece, cap,
                                                split=len(pieces) > 1))
                summary["capped"] += 1
                continue
            target = _lateral_absorb_target(piece, cap, shapes, idx, polys,
                                            roles, tree, s)
            if target is not None:
                absorbed_into.setdefault(target, []).append((piece, cap, s))
                summary["absorbed"] += 1
                summary["absorbed_caps"][round(cap, 6)] = (
                    summary["absorbed_caps"].get(round(cap, 6), 0) + 1)
            else:
                add.append(_lateral_piece_shape(s, piece, cap,
                                                split=len(pieces) > 1))
                summary["capped"] += 1
        drop.add(i)

    if rebind_only:
        import O4_UI_Utils as UI
        UI.vprint(1,
            f"  [pav-builder] {icao}: lateral-contiguity law (late "
            f"re-bind) — {summary['capped']} road shape(s) carry the "
            f"strictest cap of their cross-section "
            f"({summary['rebound']} changed, {summary['released']} "
            f"released) over {summary['roads']} walked.")
        return summary
    if not drop and not absorbed_into:
        return summary

    def _retain_context(piece, src_role, dem_host: bool) -> None:
        """Keep the absorbed stretch's FOOTPRINT in the solve's context sets.

        CONTEXT-CONSERVATIVE ABSORPTION (membership round V2, spec §V2.A;
        the owner's spine-remains amendment generalized).  The merge
        deletes a shape whose polygon is an INPUT to two buffered
        point-membership sets the grade law reads — the road-carve zone
        (``grade_graph.build_context``) and the airside chord-visibility
        union (``solver_primitives._build_shape_constraints``) — so the
        deletion moves the solve GLOBALLY (measured: 21 HECA runway
        vertices 4.2-4.6 km from any absorption, an airside-is-king
        violation).  Retaining the footprint makes both sets absorption-
        INVARIANT: they are then computed over the same total pavement
        area either way.  Unconditional on ``SERVICE_LOT_ABSORPTION``
        deliberately — the gate only widens WHICH stretches absorb, and a
        conservation that applied to one arm and not the other would
        itself be a context difference between them.  Nothing here is a
        shape: the polygon is never emitted, solved, or mutated.
        """
        try:
            if piece is None or piece.is_empty:
                return
        except _GEOM_EXC:
            return
        ctx = getattr(layout, "absorbed_road_context", None)
        if ctx is None:
            ctx = []
            layout.absorbed_road_context = ctx
        ctx.append((piece, src_role, bool(dem_host)))
        # The merged-surface index caches on the list length.
        if hasattr(layout, "_absorbed_merged_index_cache"):
            layout._absorbed_merged_index_cache = None
        summary["context_retained"] += 1
        if dem_host:
            summary["context_retained_dem_host"] += 1

    for ti, extra in absorbed_into.items():
        host = shapes[ti]
        # CLASS-UNIVERSAL ABSORPTION (owner 2026-08-03): a DEM-followed host
        # (a groundside lot) carries ``node_altitudes`` aligned 1:1 with its
        # ring, so the plain union below would misalign them.  Merge through
        # the existing helper that REBUILDS them (old vertices keep theirs,
        # new ones sample the host's pre-merge surface) — the same operator
        # the apron absorb has always used.  A merge that fails does not
        # lose the road: the piece comes back as a shape carrying its cap.
        if _CLASS_UNIVERSAL and getattr(host, "node_altitudes", None):
            n_merged = 0
            for (piece, cap, src) in extra:
                # ``alt_for_new`` stays None deliberately — see the
                # ``dem_at`` note in this function's docstring (attempt 1,
                # measured worse, reverted).  The merged ring is re-graded
                # as ONE surface below instead.
                if _merge_piece_into_apron(piece, host, 0.0,
                                           alt_for_new=None):
                    # ``_merge_piece_into_apron`` writes the OPEN ring's
                    # altitudes; a DEM-followed lot carries the CLOSED
                    # convention (``_dem_follow_polygon``, len == len of
                    # exterior.coords with the repeat), which every reader
                    # alignment test uses.  Re-close so the merged host
                    # stays in its own convention.
                    _na = host.node_altitudes
                    _nc = len(host.polygon.exterior.coords)
                    if _na is not None and len(_na) == _nc - 1:
                        host.node_altitudes = list(_na) + [_na[0]]
                    summary["absorbed_dem_host"] += 1
                    n_merged += 1
                    _retain_context(piece, src.role, True)
                    continue
                summary["absorbed"] -= 1
                summary["merge_failed"] += 1
                summary["capped"] += 1
                add.append(_lateral_piece_shape(src, piece, cap, split=True))
            # THE MERGED SURFACE IS ONE SURFACE — grade it as one (ruling
            # 2026-08-03).  Runs once per host, after every piece has been
            # welded in, so the ring the lot law sees is the final one.
            if n_merged:
                _w = _regrade_merged_host(host, dem_at)
                if _w is not None:
                    summary["host_regraded"] += 1
                    summary["host_regrade_worst"] = max(
                        summary["host_regrade_worst"], _w)
            continue
        merged = None
        try:
            merged = unary_union([host.polygon] + [p for (p, _c, _s) in extra])
        except _GEOM_EXC:
            merged = None
        if merged is not None and merged.geom_type == "MultiPolygon":
            merged = max(merged.geoms, key=lambda g: g.area)
        if merged is not None and (merged.geom_type != "Polygon"
                                   or merged.is_empty):
            merged = None
        if merged is not None and not merged.is_valid:
            merged = merged.buffer(0)
            if merged.geom_type != "Polygon" or merged.is_empty:
                merged = None
        if merged is None:
            # The union did not close.  Gate ON, the pieces come BACK as
            # capped shapes — a failed merge must never delete pavement
            # (the source-coverage law); gate OFF this keeps its historical
            # silent-drop behaviour so the arms stay byte-identical.
            if _CLASS_UNIVERSAL:
                for (piece, cap, src) in extra:
                    summary["absorbed"] -= 1
                    summary["merge_failed"] += 1
                    summary["capped"] += 1
                    add.append(_lateral_piece_shape(src, piece, cap,
                                                    split=True))
            continue
        host.polygon = merged
        for (piece, _c, src) in extra:
            _retain_context(piece, src.role, False)
    layout.shapes = [s for i, s in enumerate(shapes) if i not in drop] + add
    import O4_UI_Utils as UI
    UI.vprint(1,
        f"  [pav-builder] {icao}: lateral-contiguity law — "
        f"{summary['roads']} road shape(s) walked, {summary['cut']} cut at "
        f"segment boundaries, {summary['absorbed']} stretch(es) ABSORBED "
        f"into the adjacent surface, {summary['capped']} carrying the "
        f"strictest cap.")
    if summary["context_retained"]:
        UI.vprint(1,
            f"  [pav-builder] {icao}: context-conservative absorption — "
            f"{summary['context_retained']} absorbed footprint(s) RETAINED "
            f"for the solve's context sets "
            f"({summary['context_retained_dem_host']} into a DEM-followed "
            f"host); the road-carve zone and the airside visibility union "
            f"are absorption-invariant.")
    if _CLASS_UNIVERSAL:
        UI.vprint(1,
            f"  [pav-builder] {icao}: class-universal absorption — "
            f"{summary['absorbed_dem_host']} stretch(es) merged into a "
            f"DEM-followed host, caps "
            f"{sorted(summary['absorbed_caps'].items())}, "
            f"{summary['cut_failed']} piece(s) NOT absorbed (mouth cut did "
            f"not separate the free stretch), {summary['merge_failed']} "
            f"merge failure(s) returned as capped shapes; "
            f"{summary['host_regraded']} merged host(s) RE-GRADED as one "
            f"surface (worst adjacent ring grade after "
            f"{100.0 * summary['host_regrade_worst']:.2f} %).")
    return summary


def _lateral_piece_shape(src, poly, cap, *, split: bool):
    """One output shape for a road segment.

    An UNCUT road keeps its own shape object (every field the rest of the
    build set on it survives — only the cap is added); a CUT road yields
    dataclass copies, which is safe because a shape carrying per-vertex
    altitudes is never cut (its ``node_altitudes`` could not follow the
    new ring)."""
    if not split:
        src.polygon = poly
        src.lateral_cap = cap
        return src
    import dataclasses as _dc
    return _dc.replace(src, polygon=poly, lateral_cap=cap,
                       node_altitudes=None,
                       from_route_proximity_cut=True)


def _lateral_absorb_target(piece, cap, shapes, idx, polys, roles, tree, src):
    """The shape index this segment ABSORBS into (clause 4), or ``None``.

    A legal target is a LITERAL neighbour of the piece (shared boundary, not
    proximity) whose own cap IS the segment's cap.  Ties go to the longest
    shared boundary (the surface the road most belongs to).

    A host carrying per-vertex altitudes (a DEM-followed lot) is legal only
    under ``config.SERVICE_LOT_ABSORPTION`` (owner 2026-08-03, absorption is
    CLASS-UNIVERSAL): there the merge goes through ``_merge_piece_into_apron``,
    which rebuilds ``node_altitudes`` for the merged ring instead of leaving
    them misaligned.  With that gate off those segments carry the cap."""
    from .config import SERVICE_LOT_ABSORPTION as _CLASS_UNIVERSAL
    best, best_share = None, 0.0
    try:
        boundary = piece.exterior
    except _GEOM_EXC:
        return None
    for k in tree.query(piece.buffer(_LATERAL_GAP_TOL_M)):
        k = int(k)
        si = idx[k]
        host = shapes[si]
        if host is src or host.polygon is piece:
            continue
        if roles[k] in LATERAL_ABSORB_EXCLUDED_ROLES:
            continue
        from .config import ROLE_GRADE_LIMITS as _RGL
        if _RGL.get(roles[k]) != cap:
            continue
        if (getattr(host, "node_altitudes", None) is not None
                and not _CLASS_UNIVERSAL):
            continue
        try:
            if piece.distance(polys[k]) > _LATERAL_GAP_TOL_M:
                continue
            share = boundary.intersection(
                polys[k].buffer(_LATERAL_GAP_TOL_M)).length
        except _GEOM_EXC:
            continue
        if share > best_share:
            best, best_share = si, share
    return best if best_share >= _LATERAL_MIN_MEMBER_M else None


# Roles a road may never be merged INTO even when their cap matches: the
# runway family owns its own footprint law (clause 5) and a building pad is
# not a surface a road becomes.
LATERAL_ABSORB_EXCLUDED_ROLES = frozenset({
    "runway", "runway_crossing", "building", "terminal"})


def _lateral_split(poly, stations, caps, runs, nx, ny, cut_at_mouth):
    """Cut ``poly`` transversely where the segment cap CHANGES and return
    ``[(piece, cap, uniform), …]``.

    ``uniform`` is ``True`` when every station the piece covers agrees on
    that one cap — i.e. the mouth cut DID separate this segment from its
    neighbours.  ``False`` means the cut did not fire (``cut_at_mouth``
    fell back to the uncut piece) and the piece still holds stations of
    another class: absorbing it would absorb a free road stretch end to end,
    which the owner ruled a defect (2026-08-03), so the caller keeps it.

    The cut chord is the station's own cross-section through the road: the
    two points where the perpendicular leaves the road's ring.  That is a
    MOUTH chord in exactly the sense ``_cut_at_mouth`` takes (its non-vertex
    fallbacks handle a chord whose ends are not ring vertices), so the
    segmentation reuses the existing machinery rather than inventing one.

    Returns ``None`` when the shape has a single segment and needs no cut
    (the caller then treats the whole shape as that segment) — except that a
    single BINDING segment still returns the whole shape with its cap.
    """
    if len(runs) == 1:
        return [(poly, runs[0][2], True)]
    cut_stations = [runs[j][0] for j in range(1, len(runs))]
    pieces = [poly]
    for si in cut_stations:
        st = stations[si] if si < len(stations) else None
        if st is None:
            continue
        px, py = st
        nxt = []
        for piece in pieces:
            chord = _lateral_chord(piece, px, py, nx, ny)
            if chord is None:
                nxt.append(piece)
                continue
            sub = cut_at_mouth(piece, chord[0], chord[1])
            if sub and len(sub) >= 2 and all(g.area > 1.0 for g in sub):
                nxt.extend(sub)
            else:
                nxt.append(piece)
        pieces = nxt
    out = []
    for piece in pieces:
        own = [caps[k] for k, st in enumerate(stations)
               if st is not None and caps[k] is not None
               and piece.covers(Point(st))]
        cap = min(own) if own else None
        # UNIFORMITY is judged on the piece's INTERIOR stations only: the
        # boundary station IS the cut chord (the cut is drawn through it),
        # so both pieces of a successful cut cover it and it would read as
        # a disagreement on every cut ever made.
        interior = [caps[k] for k, st in enumerate(stations)
                    if st is not None and caps[k] is not None
                    and piece.covers(Point(st))
                    and piece.exterior.distance(Point(st)) > 1e-6]
        uniform = (cap is not None
                   and all(abs(c - cap) <= 1e-12 for c in interior))
        out.append((piece, cap, uniform))
    return out


def _lateral_chord(poly, px, py, nx, ny):
    """The two points where the perpendicular at ``(px, py)`` leaves
    ``poly``'s ring — the transverse mouth chord across the road."""
    line = LineString([(px - nx * _LATERAL_PROBE_M, py - ny * _LATERAL_PROBE_M),
                       (px + nx * _LATERAL_PROBE_M, py + ny * _LATERAL_PROBE_M)])
    try:
        inter = line.intersection(poly)
    except _GEOM_EXC:
        return None
    parts = ([inter] if inter.geom_type == "LineString"
             else [g for g in getattr(inter, "geoms", ())
                   if g.geom_type == "LineString"])
    for g in parts:
        cs = list(g.coords)
        if len(cs) < 2:
            continue
        if g.distance(Point(px, py)) <= _LATERAL_GAP_TOL_M:
            return cs[0], cs[-1]
    return None


def carve_narrow_service_strips(
        layout: "PavementLayout",
        pav_union,
        terminal_union=None,
        *,
        narrow_width_m: float = 25.0,
        sample_step_m: float = 5.0,
        min_run_m: float = 12.0,
        mouth_extension_m: float = 2.5,
        min_piece_m2: float = 25.0,
        ) -> int:
    """Carve NARROW ground-truck-route strips out of apron/junction faces
    as ``ROLE_SERVICE_JUNCTION`` corridors CENTERED on the truck spine
    (user 2026-07-04, CYXY): where the CONTIGUOUS pavement cross-section
    at a service centerline is ≤ ``narrow_width_m``, the WHOLE strip is
    service-road pavement.  The global slice cuts pavement ALONG the
    route line, so each half of a narrow strip merges into whatever big
    face it touches at its ends and no "narrow face" ever exists for
    ``classify_faces`` — one side (or neither) read as road while the
    strip physically IS the road.

    Downstream this cascades through the existing classifiers: the
    service corridor severs the aircraft touch-chain, so lots and pads
    beyond it (reachable only via the road) demote to DEM-following
    groundside in ``_reclassify_runway_disconnected_to_groundside``.
    Wide pavement crossed by a truck route stays apron (standing user
    ruling 2026-07-02) — the carve happens only where the contiguous
    cross-section is narrow.

    Corridor intervals that reach a route END are extended by
    ``mouth_extension_m`` so a road that stops at a groundside lot's
    edge (the pre-slice groundside subtraction leaves a ~1 m gap)
    touches the lot again — the groundside mouth-anchor machinery then
    grades the road to CLIMB to the lot (user ruling 4).

    Supersedes the retired ``O4_SVC_CURVED_JUNCTION`` experiment
    (2026-06-29, net-negative): its corridors graded all-pair 4 %,
    while these faces ride the v14.1 service SPINES (longitudinal 5 %
    along the route).

    Returns the number of carved service pieces added.
    """
    from shapely.ops import substring
    service_lines = getattr(layout, "apt_service_centerlines", None) or []
    if not service_lines or pav_union is None or pav_union.is_empty:
        return 0

    def _contiguous_width(line, arc, probe=60.0):
        return _svc_contiguous_width(line, arc, pav_union, probe=probe)

    corridors = []
    for centerline in service_lines:
        line = getattr(centerline, "line", None)
        if line is None or line.is_empty or line.length < min_run_m:
            continue
        n_stations = max(2, int(line.length / sample_step_m) + 1)
        arcs = [line.length * k / (n_stations - 1)
                for k in range(n_stations)]
        narrow = []
        for arc in arcs:
            w = _contiguous_width(line, arc)
            narrow.append(w is not None and 0.0 < w <= narrow_width_m)
        # group consecutive narrow stations into intervals
        k = 0
        while k < len(arcs):
            if not narrow[k]:
                k += 1
                continue
            k2 = k
            while k2 + 1 < len(arcs) and narrow[k2 + 1]:
                k2 += 1
            a1, a2 = arcs[k], arcs[k2]
            k = k2 + 1
            if a2 - a1 < min_run_m:
                continue
            try:
                seg = substring(line, a1, a2)
                coords = list(seg.coords)
                # extend intervals that reach a route END so the road
                # mouth re-touches the groundside lot it feeds
                if a1 <= sample_step_m and len(coords) >= 2:
                    (x1, y1), (x2, y2) = coords[0], coords[1]
                    d = math.hypot(x2 - x1, y2 - y1) or 1.0
                    coords[0] = (x1 - (x2 - x1) / d * mouth_extension_m,
                                 y1 - (y2 - y1) / d * mouth_extension_m)
                if a2 >= line.length - sample_step_m and len(coords) >= 2:
                    (x1, y1), (x2, y2) = coords[-2], coords[-1]
                    d = math.hypot(x2 - x1, y2 - y1) or 1.0
                    coords[-1] = (x2 + (x2 - x1) / d * mouth_extension_m,
                                  y2 + (y2 - y1) / d * mouth_extension_m)
                # mitre joins: arc-free carve edges, so the pre-solve
                # conformance passes can stitch neighbours cleanly
                corridors.append(LineString(coords).buffer(
                    narrow_width_m / 2.0 + 1.0, cap_style=2,
                    join_style=2))
            except _GEOM_EXC:
                continue
    if not corridors:
        return 0
    try:
        corridor_union = unary_union(corridors)
        if terminal_union is not None and not terminal_union.is_empty:
            corridor_union = corridor_union.difference(terminal_union)
    except _GEOM_EXC:
        return 0
    if corridor_union.is_empty:
        return 0

    n_carved = 0
    new_shapes = []
    # Post-slice faces can still OVERLAP each other slightly (the
    # overlap-clip pass runs later) — an overlap region inside the
    # corridor must be emitted as service ONCE, and EVERY face loses
    # its full corridor intersection (else face B keeps pavement face
    # A already emitted as road: cross-role overlap, zero-tolerance
    # test).  ``emitted_corridor`` accumulates the pieces emitted so
    # far; each face's carve dedupes against it.
    emitted_corridor = []
    for shape in layout.shapes:
        if shape.role not in (ROLE_APRON, ROLE_JUNCTION) \
                or shape.polygon is None or shape.polygon.is_empty:
            new_shapes.append(shape)
            continue
        try:
            carved = shape.polygon.intersection(corridor_union)
            if emitted_corridor and not carved.is_empty:
                carved = carved.difference(unary_union(emitted_corridor))
        except _GEOM_EXC:
            new_shapes.append(shape)
            continue
        carved_parts = [g for g in
                        ([carved] if carved.geom_type == "Polygon"
                         else list(getattr(carved, "geoms", ())))
                        if g.geom_type == "Polygon"
                        and g.area >= min_piece_m2]
        try:
            remainder = shape.polygon.difference(corridor_union)
        except _GEOM_EXC:
            new_shapes.append(shape)
            continue
        rem_parts = [g for g in
                     ([remainder] if remainder.geom_type == "Polygon"
                      else list(getattr(remainder, "geoms", ())))
                     if g.geom_type == "Polygon" and g.area >= 1.0]
        if not carved_parts and remainder.area \
                >= shape.polygon.area - min_piece_m2:
            # corridor barely grazes this face — leave it whole
            new_shapes.append(shape)
            continue
        if not rem_parts and carved_parts:
            # whole face is road territory
            shape.role = ROLE_SERVICE_JUNCTION
            new_shapes.append(shape)
            emitted_corridor.append(shape.polygon)
            n_carved += 1
            continue
        if not rem_parts:
            new_shapes.append(shape)
            continue
        rem_parts.sort(key=lambda g: -g.area)
        shape.polygon = rem_parts[0]
        new_shapes.append(shape)
        for extra in rem_parts[1:]:
            new_shapes.append(BuiltShape(
                polygon=extra, role=shape.role, ref=shape.ref,
                source_axis=shape.source_axis))
        for piece in carved_parts:
            new_shapes.append(BuiltShape(
                polygon=piece, role=ROLE_SERVICE_JUNCTION, ref="",
                source_axis=None))
            emitted_corridor.append(piece)
            n_carved += 1
    if n_carved:
        layout.shapes = new_shapes
    return n_carved


def consolidate_full_width_service_corridors(
        layout: "PavementLayout",
        *,
        touch_tol_m: float = 0.5,
        min_shared_m: float = 1.0,
        max_corridor_halfwidth_m: float = 15.0,
        route_through_min_m: float = 2.0,
        absorb_fragment_area_m2: float = 60.0,
        ) -> int:
    """Merge the shattered pieces of ONE service-road corridor into
    full-width corridor shapes (user 2026-07-05 full-width corridor):
    a service road is ONE corridor — its spine (the apt.dat truck-route
    centerline) has pavement on BOTH sides, and the two half-strips are
    the same surface.  The global slice cuts pavement by every
    centerline INCLUDING the road's own spine, so each road is born as
    two half-strips flanking the spine, and the carve / re-role /
    conversion passes add along-route fragment chains on top (CYXY
    around (60.70588, -135.07070): five sub-100 m² pieces for one
    ~30 m corridor run).  Solved independently they cannot grade as
    one surface.

    A shape is a corridor MEMBER when it is service pavement ridden by
    exactly ONE truck route (≥ ``route_through_min_m`` of the route
    inside/along it — a piece carrying two routes' interiors is a
    genuine road↔road intersection and is left alone) and its whole
    ring lies within ``max_corridor_halfwidth_m`` of that route (a wide
    lot only meets its route at the mouth and never qualifies).
    Members of the SAME route whose rings share a ≥ ``min_shared_m``
    boundary run merge — this joins both opposite-side half-strips
    (they share the spine seam itself) and along-route fragment chains.
    Small junction / service_junction slivers (≤
    ``absorb_fragment_area_m2``) that sit ON the route inside the
    corridor width DERIVED FROM THE MEMBERS BEING MERGED (never a
    constant — the road's actual pavement extent) are absorbed too
    (CYXY: the 8 m² full-width junction sliver at the corridor mouth).

    The merged shapes carry ``ROLE_SERVICE_ROAD`` (a corridor with one
    route through it grades AXIALLY along that route) and no altitudes
    — this runs PRE-solve so the corridor grades as one surface.

    Gate ``O4_FULL_WIDTH_SERVICE_CORRIDOR`` (default ON); off restores
    the old shattered-pieces behaviour byte-identically.  Returns the
    net number of shapes eliminated by merging.
    """
    if _os.environ.get("O4_FULL_WIDTH_SERVICE_CORRIDOR", "1") != "1":
        return 0
    routes = [centerline.line for centerline in
              (getattr(layout, "apt_service_centerlines", None) or [])
              if centerline.line is not None
              and not centerline.line.is_empty]
    if not routes:
        return 0

    def _max_lateral_extent_m(polygon, route_line):
        """Farthest ring vertex from the route spine — the half-width
        this piece actually spans (user 2026-07-05 full-width corridor:
        corridor width is derived from the faces, never a constant)."""
        try:
            return max(route_line.distance(Point(x, y))
                       for (x, y) in polygon.exterior.coords)
        except _GEOM_EXC:
            return float("inf")

    _debug_at = None
    _debug_spec = _os.environ.get("O4_FW_DEBUG_LL", "")
    if _debug_spec and layout.anchor is not None:
        try:
            _dbg_lat, _dbg_lon = (float(v) for v in _debug_spec.split(","))
            _lat0, _lon0 = layout.anchor
            _debug_at = (
                math.radians(_dbg_lon - _lon0) * R_EARTH
                * math.cos(math.radians(_lat0)),
                math.radians(_dbg_lat - _lat0) * R_EARTH)
        except ValueError:
            _debug_at = None

    def _debug_near(polygon):
        return (_debug_at is not None
                and polygon.distance(Point(*_debug_at)) <= 60.0)

    # ── corridor members: service pavement riding exactly ONE route ──
    member_indices: List[int] = []
    member_route: Dict[int, int] = {}
    member_lateral: Dict[int, float] = {}
    for index, shape in enumerate(layout.shapes):
        if shape.role not in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            continue
        if shape.polygon is None or shape.polygon.is_empty \
                or shape.polygon.geom_type != "Polygon":
            continue
        if getattr(shape, "is_bridge", False):
            continue
        # Measure each route's run along the piece against the piece
        # BUFFERED by the touch tolerance: a half-strip's spine seam IS
        # the route line, running exactly ON the ring — the unbuffered
        # polygon∩line length reads ~0 there whenever a weld/snap moved
        # a seam vertex by millimetres, and the flanking half never
        # qualified (user 2026-07-05 full-width corridor: pavement on
        # BOTH sides of the spine is the same surface, so both flanks
        # must ride the route).
        try:
            reach_polygon = shape.polygon.buffer(touch_tol_m)
        except _GEOM_EXC:
            continue
        riding_routes = []
        for route_index, route_line in enumerate(routes):
            try:
                run_m = route_line.intersection(reach_polygon).length
            except _GEOM_EXC:
                run_m = 0.0
            if run_m >= route_through_min_m:
                riding_routes.append((route_index, run_m))
        if _debug_near(shape.polygon):
            print(f"[fw-debug] shape#{index} role={shape.role} "
                  f"area={shape.polygon.area:.1f} riding={riding_routes}")
        if not riding_routes:
            continue          # routeless piece — not corridor pavement
        riding_routes.sort(key=lambda entry: -entry[1])
        primary_route, primary_run_m = riding_routes[0]
        # A piece is a genuine road↔road INTERSECTION — left alone —
        # only when a SECOND route runs through it comparably to the
        # first.  A side-route MOUTH poking a few metres into a long
        # corridor to meet the spine must not disqualify the corridor
        # (CYXY: an 81 m route-7 corridor touched by 4.7 m of route 2).
        if len(riding_routes) > 1 and riding_routes[1][1] \
                >= max(route_through_min_m, 0.25 * primary_run_m):
            continue          # comparable second route → intersection
        lateral = _max_lateral_extent_m(shape.polygon,
                                        routes[primary_route])
        if _debug_near(shape.polygon):
            print(f"[fw-debug]   lateral={lateral:.1f}")
        if lateral > max_corridor_halfwidth_m:
            continue          # lot-like piece, not a corridor flank
        member_indices.append(index)
        member_route[index] = primary_route
        member_lateral[index] = lateral
    if len(member_indices) < 2:
        return 0

    def _shared_boundary_run_m(polygon_a, polygon_b):
        """Length of ring A running within ``touch_tol_m`` of ring B
        (identity on exactly-shared boundaries; 0 for point touches)."""
        try:
            shared = polygon_a.exterior.intersection(
                polygon_b.exterior.buffer(touch_tol_m))
            return getattr(shared, "length", 0.0)
        except _GEOM_EXC:
            return 0.0

    # ── union-find: same-route members sharing a real boundary run ──
    parent = {index: index for index in member_indices}

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for position, index_a in enumerate(member_indices):
        polygon_a = layout.shapes[index_a].polygon
        for index_b in member_indices[position + 1:]:
            if member_route[index_a] != member_route[index_b]:
                continue      # only pieces flanking the SAME spine merge
            polygon_b = layout.shapes[index_b].polygon
            try:
                if polygon_a.distance(polygon_b) > touch_tol_m:
                    continue
            except _GEOM_EXC:
                continue
            if _shared_boundary_run_m(polygon_a, polygon_b) \
                    < min_shared_m:
                continue      # point / sliver touch — not one corridor
            root_a, root_b = _find(index_a), _find(index_b)
            if root_a != root_b:
                parent[root_a] = root_b

    groups: Dict[int, List[int]] = {}
    for index in member_indices:
        groups.setdefault(_find(index), []).append(index)

    # ── absorb tiny on-route slivers into the corridor they shatter ──
    # (junction / service_junction fragments spanning the corridor —
    # CYXY's 8 m² mouth sliver.)  The lateral cap comes from the GROUP
    # being merged: the corridor's own measured half-width, +1 m slack.
    absorbed: Dict[int, List[int]] = {}
    claimed: Set[int] = set(member_indices)
    for index, shape in enumerate(layout.shapes):
        if index in claimed:
            continue
        if shape.role not in (ROLE_JUNCTION, ROLE_SERVICE_JUNCTION):
            continue
        if shape.polygon is None or shape.polygon.is_empty \
                or shape.polygon.geom_type != "Polygon":
            continue
        if getattr(shape, "is_bridge", False) \
                or shape.polygon.area > absorb_fragment_area_m2:
            continue
        for root, group in groups.items():
            route_line = routes[member_route[group[0]]]
            try:
                if route_line.distance(shape.polygon) > touch_tol_m:
                    continue          # not on this corridor's spine
            except _GEOM_EXC:
                continue
            group_halfwidth = max(member_lateral[member]
                                  for member in group)
            if _max_lateral_extent_m(shape.polygon, route_line) \
                    > group_halfwidth + 1.0:
                continue              # pokes past the corridor width
            if not any(_shared_boundary_run_m(
                        shape.polygon, layout.shapes[member].polygon)
                       >= min_shared_m for member in group):
                continue              # doesn't actually abut the group
            absorbed.setdefault(root, []).append(index)
            claimed.add(index)
            break

    # ── merge each group into full-width corridor shape(s) ──────────
    removed_indices: Set[int] = set()
    merged_shapes: List[BuiltShape] = []
    n_eliminated = 0
    for root, group in groups.items():
        piece_indices = group + absorbed.get(root, [])
        if len(piece_indices) < 2:
            continue
        try:
            union = unary_union([layout.shapes[index].polygon
                                 for index in piece_indices])
        except _GEOM_EXC:
            continue
        union_pieces = ([union] if union.geom_type == "Polygon"
                        else [g for g in getattr(union, "geoms", ())
                              if g.geom_type == "Polygon"])
        union_pieces = [g for g in union_pieces if not g.is_empty]
        if not union_pieces or len(union_pieces) >= len(piece_indices):
            continue                  # nothing actually merged
        if any(any(Polygon(ring).area > 0.05 for ring in g.interiors)
               for g in union_pieces):
            continue    # a real hole appeared — keep the pieces as-is
        for g in union_pieces:
            if g.interiors:           # drop numeric-noise micro holes
                g = Polygon(g.exterior)
            merged_shapes.append(BuiltShape(
                polygon=g, role=ROLE_SERVICE_ROAD, ref="",
                source_axis=None))
        removed_indices.update(piece_indices)
        n_eliminated += len(piece_indices) - len(union_pieces)
    if not removed_indices:
        return 0
    layout.shapes = [shape for index, shape in enumerate(layout.shapes)
                     if index not in removed_indices] + merged_shapes
    return n_eliminated


def reclassify_groundside_route_corridors(
        layout: "PavementLayout",
        *,
        corridor_halfwidth_m: float = 13.5,
        min_cover_frac: float = 0.70,
        min_run_m: float = 30.0,
        ) -> int:
    """Re-role a groundside piece that IS a truck-route road corridor to
    ``ROLE_SERVICE_ROAD`` (user 2026-07-04, CYXY #206): OSM-captured
    groundside pavement (curbside / parking capture) can coincide with an
    apt.dat ground-truck route end-to-end — an 835 m road emitted as a
    DEM "lot", which ``apply_groundside_reach`` then rigid-shifted 9 m
    below terrain to satisfy its apron connector.  A piece whose area
    lies ≥``min_cover_frac`` within ``corridor_halfwidth_m`` of the
    service centerlines AND that carries ≥``min_run_m`` of route is ROAD
    pavement: as ``service_road`` it grades AXIALLY along the route
    (DEM-following ramp at the road cap) instead of being re-levelled as
    a destination lot.  A genuine lot only meets its route at the mouth
    (coverage ≪ ``min_cover_frac``), so it never converts.  Short mouth
    pieces DO convert (measured: leaving CYXY's three 100-250 m² mouth
    pieces groundside re-opens the 40-80 % road-weld cliffs — the
    original 414-count disease).

    Returns the number of shapes re-roled."""
    if _os.environ.get("O4_GROUNDSIDE_ROUTE_CORRIDOR", "1") != "1":
        return 0
    service_lines = [c.line for c in
                     (getattr(layout, "apt_service_centerlines", None) or [])
                     if c.line is not None and not c.line.is_empty]
    if not service_lines:
        return 0
    try:
        line_union = unary_union(service_lines)
        corridor = line_union.buffer(corridor_halfwidth_m)
    except _GEOM_EXC:
        return 0
    # Existing pavement union (any non-groundside, non-feature role):
    # groundside was allowed to OVERLAP service pavement until the
    # separation pass trimmed it — a converted piece leaves that regime,
    # so trim the overlap NOW or it emits as service∩service
    # (zero-tolerance test_no_self_overlap, CYXY 0.4 m²).
    _FEATURE_ROLES = {ROLE_BOUNDARY, ROLE_GROUNDSIDE_PAVEMENT}
    try:
        pav_union = unary_union(
            [t.polygon for t in layout.shapes
             if t.polygon is not None and not t.polygon.is_empty
             and t.role not in _FEATURE_ROLES
             and not str(t.role).endswith("clearance")])
    except _GEOM_EXC:
        pav_union = None
    n_reroled = 0
    extra_shapes: list = []
    for s in layout.shapes:
        if s.role != ROLE_GROUNDSIDE_PAVEMENT or s.polygon is None \
                or s.polygon.is_empty:
            continue
        try:
            run_m = line_union.intersection(s.polygon).length
            cover = s.polygon.intersection(corridor).area / s.polygon.area
        except _GEOM_EXC:
            continue
        # A piece ENTIRELY inside the truck corridor with the route
        # genuinely through it is road pavement no matter how short the
        # run — a loop's turnaround pad (CYXY #56: 98 m², cover 1.00,
        # 14 m of 'Crew cars' through it) sat as groundside one
        # clearance-gap cliff off its own road.
        _full_corridor = cover >= 0.95 and run_m >= 5.0
        if (run_m < min_run_m and not _full_corridor) \
                or cover < min_cover_frac:
            continue
        parts = [s.polygon]
        if pav_union is not None:
            try:
                trimmed = s.polygon.difference(pav_union)
            except _GEOM_EXC:
                trimmed = None
            parts = ([] if trimmed is None or trimmed.is_empty
                     else [trimmed] if trimmed.geom_type == "Polygon"
                     else [g for g in getattr(trimmed, "geoms", ())
                           if g.geom_type == "Polygon"])
            parts = [g for g in parts if g.area >= _GROUNDSIDE_MIN_AREA_M2]
            if not parts:
                continue                  # fully covered — nothing to convert
            parts.sort(key=lambda g: -g.area)
        s.polygon = parts[0]
        s.role = ROLE_SERVICE_ROAD
        s.ref = ""
        s.node_altitudes = None
        s.altitude = None
        s.altitude_high = None
        s.altitude_low = None
        for extra in parts[1:]:
            extra_shapes.append(BuiltShape(
                polygon=extra, role=ROLE_SERVICE_ROAD, ref=""))
        n_reroled += 1
    if extra_shapes:
        layout.shapes.extend(extra_shapes)
    return n_reroled


def conform_service_mouths_to_groundside(
        layout: "PavementLayout",
        touch_tol_m: float = 0.5,
        ) -> int:
    """Insert shared vertices into groundside lot rings where a SERVICE
    shape's ring vertex lies on the lot boundary — the road↔lot
    connection is identified EARLY and becomes first-class shared
    geometry (user 2026-07-04, CYXY P4): the lot is served BY the road,
    so the two must emit welded nodes there, and the groundside
    mouth-anchor machinery can bind by canonical key instead of failing
    on a mouth that lands mid-edge (the road then CLIMBS to the lot).

    The inserted vertex takes the lot edge's interpolated DEM altitude,
    so the lot's surface is unchanged — only its ring gains a node.
    Returns the number of vertices inserted.
    """
    service_shapes = [s for s in layout.shapes
                      if s.role in (ROLE_SERVICE_ROAD,
                                    ROLE_SERVICE_JUNCTION)
                      and s.polygon is not None
                      and not s.polygon.is_empty]
    if not service_shapes:
        return 0
    n_inserted = 0
    for lot in layout.shapes:
        if lot.role != ROLE_GROUNDSIDE_PAVEMENT or lot.polygon is None \
                or lot.polygon.is_empty or not lot.node_altitudes:
            continue
        near = [s for s in service_shapes
                if s.polygon.distance(lot.polygon) <= touch_tol_m]
        if not near:
            continue
        ring = list(lot.polygon.exterior.coords)
        closed = len(ring) > 1 and ring[0] == ring[-1]
        if closed:
            ring = ring[:-1]
        alts = list(lot.node_altitudes[:len(ring)])
        if len(alts) < len(ring):
            alts += [alts[-1] if alts else None] * (len(ring) - len(alts))
        changed = False
        for s in near:
            s_ring = list(s.polygon.exterior.coords)
            if len(s_ring) > 1 and s_ring[0] == s_ring[-1]:
                s_ring = s_ring[:-1]
            boundary = lot.polygon.exterior
            for (vx, vy) in s_ring:
                p = Point(vx, vy)
                if boundary.distance(p) > touch_tol_m:
                    continue
                if any(math.hypot(vx - rx, vy - ry) <= touch_tol_m
                       for (rx, ry) in ring):
                    continue          # a lot vertex is already there
                # insert into the lot edge nearest the mouth vertex
                best = None
                for k in range(len(ring)):
                    ax, ay = ring[k]
                    bx, by = ring[(k + 1) % len(ring)]
                    dx, dy = bx - ax, by - ay
                    seg2 = dx * dx + dy * dy
                    if seg2 < 1e-9:
                        continue
                    t = ((vx - ax) * dx + (vy - ay) * dy) / seg2
                    t = min(1.0, max(0.0, t))
                    px, py = ax + t * dx, ay + t * dy
                    d = math.hypot(vx - px, vy - py)
                    if best is None or d < best[0]:
                        best = (d, k, t, px, py)
                if best is None or best[0] > touch_tol_m:
                    continue
                _d, k, t, px, py = best
                a0 = alts[k]
                a1 = alts[(k + 1) % len(ring)]
                new_alt = (round(a0 + t * (a1 - a0), 2)
                           if a0 is not None and a1 is not None else a0)
                ring.insert(k + 1, (px, py))
                alts.insert(k + 1, new_alt)
                changed = True
                n_inserted += 1
        if changed:
            try:
                lot.polygon = Polygon(ring)
            except _GEOM_EXC:
                continue
            lot.node_altitudes = alts + [alts[0]]
    return n_inserted


def conform_parallel_service_edges(layout, window_m: float = 2.0,
                                   min_gap_m: float = 0.05,
                                   dedup_m: float = 0.75) -> int:
    """Insert projected vertices where two SERVICE shapes run parallel
    within ``window_m`` of each other (user 2026-07-06, HECA #578↔#64).

    Two near-parallel roads carry no shared geometry, and their ring
    nodes are offset along-track — the service DEM-follow's node↔node
    proximity coupling then has nothing to bind (a 1 m gap emitted a
    0.9 m mid-edge wall between a flat road and a climbing one).  For
    every vertex of shape A within the window of shape B's boundary,
    insert the projection foot into B's ring (skipped when a B vertex
    already sits within ``dedup_m``), so matching nodes exist for the
    coupling.  Runs PRE-SOLVE (no altitudes exist yet on service rings).
    Returns the number of inserted vertices."""
    import os as _os
    if _os.environ.get("O4_SVC_PARALLEL_CONFORM", "1") != "1":
        return 0
    svc = [s for s in layout.shapes
           if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
           and s.polygon is not None and not s.polygon.is_empty
           and s.polygon.geom_type == "Polygon"]
    n_inserted = 0
    for receiver in svc:
        try:
            ring = list(receiver.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        closed = len(ring) > 1 and ring[0] == ring[-1]
        if closed:
            ring = ring[:-1]
        changed = False
        for donor in svc:
            if donor is receiver:
                continue
            try:
                if donor.polygon.distance(receiver.polygon) > window_m:
                    continue
            except _GEOM_EXC:
                continue
            try:
                donor_ring = list(donor.polygon.exterior.coords)[:-1]
            except _GEOM_EXC:
                continue
            for (vx, vy) in donor_ring:
                # nearest point on the receiver ring
                best = None
                for k in range(len(ring)):
                    ax, ay = ring[k]
                    bx, by = ring[(k + 1) % len(ring)]
                    dx, dy = bx - ax, by - ay
                    seg2 = dx * dx + dy * dy
                    if seg2 < 1e-9:
                        continue
                    t = ((vx - ax) * dx + (vy - ay) * dy) / seg2
                    t = min(1.0, max(0.0, t))
                    px, py = ax + t * dx, ay + t * dy
                    d = math.hypot(vx - px, vy - py)
                    if best is None or d < best[0]:
                        best = (d, k, px, py)
                if (best is None or best[0] > window_m
                        or best[0] < min_gap_m):
                    continue
                _d, k, px, py = best
                if any(math.hypot(px - rx, py - ry) <= dedup_m
                       for (rx, ry) in ring):
                    continue          # a receiver vertex is already there
                ring.insert(k + 1, (px, py))
                changed = True
                n_inserted += 1
        if changed:
            try:
                receiver.polygon = Polygon(ring)
            except _GEOM_EXC:
                continue
    return n_inserted


# R7c — the CUT-AND-FILL kernel, shared verbatim by the single-ring
# limiter and the layout-wide one, so the two cannot drift into two lot
# laws (the census-wrapper lesson, applied to the surface law itself).
#
# THE EXCESS IS SPLIT, exactly as ``_grade_limit_ring`` splits it between
# two free ring neighbours — the same law, now over CHORD pairs.  A
# GAUSS-SEIDEL walk cannot do that: whichever end the sweep reaches first
# absorbs the whole excess, so the pre-R7c order made every pair yield
# DOWNWARD and a pit pulled its whole ring into itself instead of being
# filled.  So the walk is a DAMPED JACOBI: every free vertex reads the
# band the CURRENT field gives it, and they all move half-way to it
# together, which is order-independent and shares the correction.  A
# short cut-only finisher then guarantees the field is lawful (after
# convergence it is a no-op; where two PINNED welds are mutually
# infeasible it is what still yields, downward, as before).
_CHORD_JACOBI_SWEEPS = 16
_CHORD_JACOBI_DAMPING = 0.5
_CHORD_JACOBI_TOL_M = 1e-4


def _chord_band(coords, vals, live, a, cap, caps=None):
    """``(lo, hi)`` — the ``cap``-reachable band vertex ``a`` may sit in,
    generated by every other live vertex of the ring.

    ``caps`` — OPTIONAL per-vertex caps, for the ONE unified pass that now
    carries roles whose limits differ (the road chord limiter, spec
    ``docs/specs/road-chord-limiter-spec.md`` §2).  A pair is then
    budgeted at the STRICTER of its two endpoints' caps — the spec's
    pre-delegated shared-node rule, and the direction the
    lateral-contiguity ruling (owner FINAL 2026-08-02) takes everywhere
    else: a node carried by two classes takes the stricter class's law.
    ``None`` = one cap for the whole ring, arithmetic identical to the
    pre-road pass (its callers stay on that path by construction —
    see ``_grade_limit_groundside_chords``)."""
    xa, ya = coords[a]
    hi = float("inf")
    lo = float("-inf")
    cap_a = cap if caps is None else caps[a]
    for b in live:
        if b == a:
            continue
        xb, yb = coords[b]
        pair_cap = cap if caps is None else min(cap_a, caps[b])
        reach = pair_cap * math.hypot(xa - xb, ya - yb)
        up = vals[b] + reach
        if up < hi:
            hi = up
        dn = vals[b] - reach
        if dn > lo:
            lo = dn
    return lo, hi


def _chord_cut_and_fill(coords, vals, live, free, cap, sweeps: int = 4,
                        caps=None):
    """R7c in place: clamp ``vals`` into the two-sided ``cap`` band over
    CHORD pairs, leaving every vertex not in ``free`` (the welds) alone.

    ``caps`` — per-vertex caps (see :func:`_chord_band`); ``None`` keeps
    the single-cap arithmetic unchanged."""
    if not free:
        return
    for _sweep in range(_CHORD_JACOBI_SWEEPS):
        worst = 0.0
        moves = []
        for a in free:
            lo, hi = _chord_band(coords, vals, live, a, cap, caps)
            v = vals[a]
            target = hi if lo > hi else min(max(v, lo), hi)
            d = (target - v) * _CHORD_JACOBI_DAMPING
            if d:
                moves.append((a, v + d))
                worst = max(worst, abs(d))
        for a, nv in moves:
            vals[a] = nv
        if worst <= _CHORD_JACOBI_TOL_M:
            break
    # THE GUARANTEE: whatever the damped walk left over cap comes down.
    for _sweep in range(max(1, sweeps)):
        changed = False
        for a in free:
            _lo, hi = _chord_band(coords, vals, live, a, cap, caps)
            if hi < vals[a] - 1e-6:
                vals[a] = hi
                changed = True
        if not changed:
            break


def chord_limit_ring_altitudes(coords, alts,
                               cap: float = GROUNDSIDE_MAX_GRADE,
                               sweeps: int = 4,
                               pinned=None):
    """The ``cap``-Lipschitz field CLOSEST to ``alts`` over straight-line
    CHORD pairs of ONE ring (the within-shape validator metric) — the
    single-ring core of ``_grade_limit_groundside_chords``, callable at
    SOLVE time.

    ``apply_groundside_reach`` welds service-road nodes to the groundside
    ring values it computes, but the post-solve chord limiter used to
    rewrite the LOT ring only — two writers for the same physical nodes
    (CYXY road #41: pinned 698.15/699.66 at solve time while the emitted
    lot said 699.5/699.4 → 15 % road chords after emit consensus).
    Limiting the ring BEFORE the weld reads it makes the solve-time field
    identical to the post-solve one (the late limiter is idempotent on an
    already-limited ring).

    R7c — CUT **AND** FILL (owner ruling 2026-08-15, "groundside lots cut
    and fill"): this pass used to be the largest Lipschitz field ≤
    ``alts`` — CUT-ONLY, and therefore the last writer that UNDID every
    fill the seat/reach passes had lawfully made.  The lot law is now the
    TWO-SIDED band: each vertex is clamped into
    ``[v_b − cap·d, v_b + cap·d]`` of every other vertex, so a vertex the
    law must RAISE to reach its weld is raised, and one it must lower is
    lowered.  The one-sided law was the measured mechanism of the CYXY
    40,000 m³ lot-377 hollow's persistence and of the apron-42 mirror
    (99.6 % fill refused).

    ``pinned`` — indices (into ``coords``) whose value is LAW and may not
    move: the ring's welds.  The band the ruling names is generated by
    those, so they are held while everything else clamps into it.  Where
    two pinned welds are mutually infeasible the free vertex takes the
    CEILING (the pre-R7c side), never a value above a weld it must reach
    down to.

    ``coords`` may be closed (last == first); ``alts`` may carry ``None``
    (skipped).  Returns a new list shaped like ``alts``."""
    m = min(len(coords), len(alts))
    vals = [None if alts[k] is None else float(alts[k]) for k in range(m)]
    live = [k for k in range(m) if vals[k] is not None]
    held = set(pinned or ())
    free = [k for k in live if k not in held]
    _chord_cut_and_fill(coords, vals, live, free, cap, sweeps=sweeps)
    out = list(alts)
    for k in range(m):
        if vals[k] is not None:
            out[k] = round(vals[k], 2)
    # keep a closed ring closed
    if len(out) == len(coords) and len(coords) > 1 \
            and tuple(coords[0]) == tuple(coords[-1]) and out[0] is not None:
        out[-1] = out[0]
    return out


# ── THE CHORD-LIMITED FAMILY (road chord limiter, wave-3 step 1) ────
# ONE unified pass, ONE shared-node key space (spec
# ``docs/specs/road-chord-limiter-spec.md`` §1): the lot AND the road
# family — ``service_road`` + ``service_junction`` — are clamped
# together, so a road↔lot weld stays flush and a corridor chain
# rect↔junction↔rect is ONE law object (§3: the unification is the node
# book below, EXTENDED to the road roles, never a second mechanism).
# ``tunnel_ramp`` is EXCLUDED BY LAW (§1) — its law is the portal walk.
_CHORD_LIMIT_ROLES = (ROLE_GROUNDSIDE_PAVEMENT,
                      ROLE_SERVICE_ROAD,
                      ROLE_SERVICE_JUNCTION)


def _chord_limit_cap_for_role(role: str) -> float:
    """The cap :func:`_grade_limit_groundside_chords` shapes ``role`` to.

    * the LOT keeps ``GROUNDSIDE_MAX_GRADE`` — the SHAPING margin below
      its law (owner 2026-08-12 + the measurement behind it; twin
      ``test_owner_constants_round.TestTheLimitersRideTheRoadCap``), so
      every pre-road caller is unchanged;
    * the ROAD FAMILY takes its own law from ``ROLE_GRADE_LIMITS`` (spec
      §2, "the road limit, one constant, per the standing ruling") —
      read from the one table, never a second number invented here.
    """
    if role == ROLE_GROUNDSIDE_PAVEMENT:
        return GROUNDSIDE_MAX_GRADE
    from .config import ROLE_GRADE_LIMITS, SERVICE_ROAD_MAX_GRADE
    lim = ROLE_GRADE_LIMITS.get(role)
    return float(lim) if lim else float(SERVICE_ROAD_MAX_GRADE)


def _airside_claimed_keys(layout):
    """The chord limiter's PINNED set: every node an AIRSIDE ring claims,
    in BOTH identities the pass can be asked in — ``(xy_keys,
    canonical_keys)``.

    THE PARTITION IS THE REGISTRY'S, NOT A LIST HERE.
    ``layout.GROUNDSIDE_ROLES`` is the single source the census's
    ``check_grade.row_side`` and the projection's
    ``solve._receiver_nodes_from_roles`` both read; airside is its
    complement, and — exactly as the receiver rule states it — a node is
    groundside only when EVERY role it carries is groundside, so one
    airside ring claiming a node makes it airside.  A role added to the
    registry therefore lands here with no edit (the blast.py
    role-literal hazard, closed by construction).

    THE 2-DECIMAL KEY IS NOT THE EMITTER'S IDENTITY, and the difference
    is measured: with the xy key alone ONE HECA apron node welded to a
    service junction still moved 0.12 m (way-level: the apron vertex and
    the road vertex are millimetres apart, so they hash to different
    2-dp buckets while ``to_osm`` merges them into one node).  So the
    CANONICAL POINT is carried too — ``layout.canonical_points``, the
    registry the emitter, ``_node_role_sets`` and the weld book all
    resolve identity through — and a vertex is pinned if EITHER identity
    says an airside ring claims it.  A layout without the registry (unit
    scenes) simply gets the xy set, unchanged.
    """
    from .layout import GROUNDSIDE_ROLES
    keys: set = set()
    canon: set = set()
    cps = getattr(layout, "canonical_points", None)
    tol = getattr(cps, "tol_m", None) if cps is not None else None
    for s in (getattr(layout, "shapes", None) or ()):
        role = getattr(s, "role", None)
        if role is None or role in GROUNDSIDE_ROLES:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            rings = ([poly.exterior] if poly.geom_type == "Polygon"
                     else [g.exterior for g in poly.geoms])
        except _GEOM_EXC:                              # pragma: no cover
            continue
        for ring in rings:
            try:
                coords = list(ring.coords)
            except _GEOM_EXC:                          # pragma: no cover
                continue
            for (x, y) in coords:
                keys.add((round(float(x), 2), round(float(y), 2)))
                if tol is None:
                    continue
                k = cps.find_nearest(float(x), float(y), tol)
                if k is not None:
                    canon.add(k)
    return keys, canon


def _chord_limit_shared_node_census(stats, node_roles, node_cap,
                                    node_cap_max, node_road_shapes) -> None:
    """Fill ``stats`` with what the ONE node book actually unified.

    Every number is read off the book the clamp itself uses — nothing
    here re-derives geometry:

    * ``shared_road_lot_nodes`` — road↔lot welds inside the pass;
    * ``shared_rect_junction_nodes`` — the CORRIDOR CHAIN's own joints
      (spec §3: rect↔junction↔rect is one law object only if its segment
      boundaries are shared nodes here);
    * ``stricter_cap_nodes`` — nodes where two roles' caps disagreed and
      the stricter one won (spec §2, "flag the count");
    * ``road_nodes_near_miss`` — the honest other half: road-family nodes
      that are NOT shared with another road shape yet sit within the
      EMITTER's node-identity tolerance of one.  Counted, never repaired
      here; a second identity rule inside this pass would be the second
      implementation the spec forbids.
    """
    for kxy, roles_here in node_roles.items():
        if node_cap[kxy] < node_cap_max[kxy]:
            stats["stricter_cap_nodes"] += 1
        road_here = (ROLE_SERVICE_ROAD in roles_here
                     or ROLE_SERVICE_JUNCTION in roles_here)
        if road_here and ROLE_GROUNDSIDE_PAVEMENT in roles_here:
            stats["shared_road_lot_nodes"] += 1
        if (ROLE_SERVICE_ROAD in roles_here
                and ROLE_SERVICE_JUNCTION in roles_here):
            stats["shared_rect_junction_nodes"] += 1
    if not node_road_shapes:
        return
    cell = float(SHARED_VERTEX_TOL_M)
    grid: dict = {}
    for kxy in node_road_shapes:
        grid.setdefault((int(kxy[0] // cell), int(kxy[1] // cell)),
                        []).append(kxy)
    near = 0
    for kxy, owners in node_road_shapes.items():
        if len(owners) > 1:
            continue
        cx, cy = int(kxy[0] // cell), int(kxy[1] // cell)
        hit = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid.get((cx + dx, cy + dy), ()):
                    if other == kxy or not (node_road_shapes[other]
                                            - owners):
                        continue
                    if ((kxy[0] - other[0]) ** 2
                            + (kxy[1] - other[1]) ** 2) <= cell * cell:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            near += 1
    stats["road_nodes_near_miss"] = near


def _grade_limit_groundside_chords(layout) -> int:
    """Clamp every groundside AND road-family shape's altitude field into
    the Lipschitz band of its own vertices at its role's cap, measured
    over straight-line CHORD pairs — the within-shape validator metric.
    ``_dem_follow_polygon``'s ring-ramp limit only bounds CONSECUTIVE
    ring vertices; a ring-compliant hillside piece still reads >4 %
    across its interior (HECA #230: 4.7-5.5 %).  Shared boundary nodes
    are UNIFIED across shapes (keyed by rounded coords) so abutting
    groundside pieces stay flush.  Runs ONCE, late, over ALL groundside
    shapes regardless of which pass created them.  Returns the number of
    shapes whose altitudes changed.

    R7c — CUT **AND** FILL (owner ruling 2026-08-15).  This is the LAST
    groundside-altitude writer, and while it was one-sided ("the largest
    Lipschitz field ≤ the current values") it undid every lawful FILL the
    seat and reach passes made: the emitted lot read as
    ``min(terrain, cone)`` no matter what the welds asked for.  It is now
    the two-sided clamp the ruling names, with the ring's WELDS held —
    ``law_anchor_values`` is the same weld set ``_seat_ring_on_law_anchors``
    pins, so the band a lot is clamped into is generated by exactly the
    law datums that seated it.

    THE ROAD FAMILY JOINS (wave-3 step 1, spec
    ``docs/specs/road-chord-limiter-spec.md``; owner ruling ROADS CARRY
    SPINES LIKE TAXIWAYS, 2026-08-15 evening).  Road faces had NO chord
    limiter at all, so the frontage round's honest exposure moved lot
    area onto UNLIMITED road chords (+892 HECA groundside in the
    2026-08-16 battery).  ``service_road`` and ``service_junction`` are
    now clamped in THIS pass — the same node book, so road↔lot welds and
    the rect↔junction↔rect corridor chain share one value per node and
    the clamp cannot mint a step at a segment boundary.  Two rules the
    unified key space needs and a single-role pass never did:

    * the node book seeds by AUTHORITY PRECEDENCE, not ``min`` — a lot
      may not hand a road its value (``layout.AUTHORITY_PRECEDENCE`` is a
      total order, airside-first, and the deleted weld re-adoption at the
      foot of this function is what the other direction cost);
    * a node carried by two roles takes the STRICTER of their caps, and
      the count is reported (spec §2).

    ``tunnel_ramp`` is untouched: its law is the portal walk.
    """
    node_alt: dict = {}
    node_cap: dict = {}
    node_cap_max: dict = {}
    node_rank: dict = {}
    node_roles: dict = {}
    node_road_shapes: dict = {}
    rings: dict = {}
    ring_role: dict = {}
    ring_cap: dict = {}
    stats: dict = {
        "rings": {}, "changed": {}, "caps": {}, "nodes": 0,
        "shared_road_lot_nodes": 0,
        "shared_rect_junction_nodes": 0,
        "stricter_cap_nodes": 0,
        "road_nodes_near_miss": 0,
    }
    # THE WELDS ARE NOT PINNED HERE, and that is MEASURED, not assumed.
    # Holding them (``law_anchor_values`` keyed to this pass's 2-decimal
    # node key) is the literal reading of R7c's "[weld − cap·d,
    # weld + cap·d]" — but a lot ring commonly carries MANY welds whose
    # law values are not mutually lawful across the ring's own chords,
    # and freezing them converts every such pair from a cut into a
    # standing violation: CYXY way -10126 went to 6.17 m at 16-26 %
    # where the same site had read 4.79 m at 8.1 % (the shaping cap is
    # 5 %, so a >8 % pair is a pair no limiter touched).  The weld nodes
    # are OVERWRITTEN AT EMIT by the higher-authority claimant anyway
    # (``to_osm``'s precedence resolution — the lot's own field at a weld
    # is not what ships), so moving them inside the lot's field costs
    # nothing and is the pre-R7c behaviour.  The kernel keeps the ``pinned``
    # capability for the single-ring API, where the caller knows its
    # welds are one consistent datum.
    #
    # THE ONE EXCEPTION IS AIRSIDE (lead ruling 2026-08-20, this lane's
    # attempt 2).  A node an AIRSIDE ring also claims is not a groundside
    # weld at all — it is airside DATA: ``layout.GROUNDSIDE_ROLES`` is the
    # partition (the registry ``check_grade.row_side`` and
    # ``solve._receiver_nodes_from_roles`` both read — never a hand list),
    # and a node is a receiver only when EVERY role it carries is in it.
    # Moving one is a second author on an airside value, and the carrier
    # is measured: the final projection's airside pass RE-PROJECTS FROM
    # THE SEED, so a groundside rewrite of a shared node changes the
    # airside output even though the partition keeps every groundside
    # PAIR out of the airside constraint set (HECA: 175 junction ways
    # ≤0.05 m, 82 apron ways ≤0.15 m, 46 building ways ≤0.10 m).  Pinning
    # costs the lot/road nothing it keeps: the emit ships the airside
    # claimant's value at that node anyway (``to_osm`` precedence), so
    # this makes the clamp agree with what actually emits.  The pinned
    # values still GENERATE the band — the groundside side conforms to
    # airside, which is the mouth ruling in clamp form.
    pinned_keys, _airside_canon = _airside_claimed_keys(layout)
    _cps_pin = getattr(layout, "canonical_points", None)
    _pin_tol = (getattr(_cps_pin, "tol_m", None)
                if (_cps_pin is not None and _airside_canon) else None)
    for i, s in enumerate(layout.shapes):
        role = getattr(s, "role", "")
        if role not in _CHORD_LIMIT_ROLES:
            continue
        if (s.polygon is None or s.polygon.is_empty
                or s.polygon.geom_type != "Polygon"):
            continue
        if not s.node_altitudes:
            continue
        try:
            ring = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        alts = list(s.node_altitudes)
        if len(alts) == len(ring) + 1:
            alts = alts[:-1]
        if len(alts) != len(ring) or len(ring) < 3:
            continue
        if any(a is None for a in alts):
            continue
        keys = [(round(x, 2), round(y, 2)) for x, y in ring]
        # THE CANONICAL SECOND READING of the airside pin (see
        # ``_airside_claimed_keys``): a vertex the emitter will merge into
        # an airside node is airside DATA even when its 2-dp bucket
        # differs by millimetres.
        if _pin_tol is not None:
            for _k, (_vx, _vy) in enumerate(ring):
                if keys[_k] in pinned_keys:
                    continue
                _ck = _cps_pin.find_nearest(float(_vx), float(_vy),
                                            _pin_tol)
                if _ck is not None and _ck in _airside_canon:
                    pinned_keys.add(keys[_k])
        rings[i] = keys
        ring_role[i] = role
        cap = _chord_limit_cap_for_role(role)
        ring_cap[i] = cap
        stats["rings"][role] = stats["rings"].get(role, 0) + 1
        stats["caps"][role] = cap
        rank = authority_rank(role)
        is_road = role != ROLE_GROUNDSIDE_PAVEMENT
        for kxy, a in zip(keys, alts):
            v = float(a)
            prev = node_rank.get(kxy)
            if prev is None or rank < prev:
                # PRECEDENCE ACROSS ROLES, min WITHIN one.
                # ``layout.AUTHORITY_PRECEDENCE`` is a TOTAL order and it
                # is airside-first: ``service_road`` and
                # ``service_junction`` OUTRANK ``groundside_pavement``, so
                # a lot may not dictate a road's value — the emit
                # resolution ships the road's number at that node anyway,
                # and seeding this book with the lot's would clamp the
                # road against a value nothing emits.  A layout with no
                # road shapes never leaves the ``rank == prev`` branch, so
                # it keys exactly as it did before the family grew.
                node_alt[kxy] = v
                node_rank[kxy] = rank
            elif rank == prev:
                node_alt[kxy] = min(node_alt[kxy], v)
            prev_cap = node_cap.get(kxy)
            if prev_cap is None:
                node_cap[kxy] = cap
                node_cap_max[kxy] = cap
            else:
                node_cap[kxy] = min(prev_cap, cap)
                node_cap_max[kxy] = max(node_cap_max[kxy], cap)
            node_roles.setdefault(kxy, set()).add(role)
            if is_road:
                node_road_shapes.setdefault(kxy, set()).add(i)
    if not rings:
        return 0
    _chord_limit_shared_node_census(stats, node_roles, node_cap,
                                    node_cap_max, node_road_shapes)
    stats["nodes"] = len(node_alt)
    stats["airside_pinned_nodes"] = sum(1 for k in node_alt
                                        if k in pinned_keys)
    # R7c: CUT **AND** FILL, through the ONE kernel the single-ring
    # limiter uses (``_chord_cut_and_fill``) — per ring, over the SHARED
    # node values, so abutting pieces stay flush exactly as before.  The
    # welds are held: they are the band the lot is clamped into.
    for _round in range(4):
        moved = False
        for i, keys in rings.items():
            m = len(keys)
            vals = [node_alt[k] for k in keys]
            before = list(vals)
            live = list(range(m))
            free = [k for k in live if keys[k] not in pinned_keys]
            cap = ring_cap[i]
            caps = [node_cap[k] for k in keys]
            if any(c != cap for c in caps):
                # A node this ring shares with a STRICTER role: the pair
                # budget drops to the stricter cap at that endpoint.
                _chord_cut_and_fill(keys, vals, live, free, cap, caps=caps)
            else:
                # Every node at the ring's own cap — the scalar path, bit
                # for bit the pre-road arithmetic.
                _chord_cut_and_fill(keys, vals, live, free, cap)
            for k in range(m):
                if abs(vals[k] - before[k]) > 1e-6:
                    node_alt[keys[k]] = vals[k]
                    moved = True
        if not moved:
            break
    n_changed = 0
    for i, keys in rings.items():
        s = layout.shapes[i]
        # 2 decimals, matching the emit resolution end-to-end — 0.1 m
        # quantization on sub-metre groundside chords reads as 10-15 %
        # stairs (the V15 waviness class).
        alts = [round(node_alt[k], 2) for k in keys]
        closed = alts + [alts[0]]
        if closed != list(s.node_altitudes):
            s.node_altitudes = closed
            n_changed += 1
            _r = ring_role[i]
            stats["changed"][_r] = stats["changed"].get(_r, 0) + 1
    layout._chord_limit_stats = stats
    # THE SERVICE-NODE WELD RE-ADOPTION — DELETED 2026-08-05 (constant-DEM
    # oracle, fix lane 2 item 2).  It ADOPTED this pass's limited GROUNDSIDE
    # values onto coincident ``service_road`` / ``service_junction`` nodes at
    # ``layout._groundside_weld_keys``, on the reasoning that "the lot is
    # senior at its own ring" and that leaving the two writers split would
    # let the emit consensus AVERAGE them (CYXY #207).
    #
    # Both halves of that reasoning are dead law now:
    #   * SENIORITY runs the other way.  ``layout.AUTHORITY_PRECEDENCE`` is a
    #     TOTAL order and it is AIRSIDE-FIRST (airside-is-king, standing):
    #     ``service_road`` and ``service_junction`` both outrank
    #     ``groundside_pavement``.  A lot may not dictate a road's value.
    #   * The emit consensus no longer averages anything.  Single-authority
    #     emission is STANDING and ungated since 2026-08-05 ("EMITTERS EMIT,
    #     NEVER GRADE"): at a shared node the precedence winner's value is
    #     emitted verbatim and the losing claimant retreats behind a
    #     retaining wall (``adjacent_ground.emit_authority_retreat_walls``)
    #     instead of being blended away.
    #
    # MEASURED (HEAZ, constant-DEM oracle, both worlds).  This loop was the
    # author of 24 of service_junction #28's 167 vertices, writing the raw
    # DEM constant onto a face the solve had graded 0/167 on-DEM: a 50.47 m
    # internal cliff, the worst within-shape row in the plateau census
    # (1410.89 %), and a 450.56 m step in the canyon world.  Deleting it
    # took the airport's law-true rows from 836/4040 (plateau/canyon) to
    # 1258/894 — service_junction within-shape rows 113→13 and 361→0,
    # junction 169→160 and 2152→35, strip-seam tears 143→0.  That is DEM
    # used as a hard authority over a law-solved surface, which RULINGS
    # 5578b6a ("DEM is a SEED, never an authority") forbids outright.
    #
    # The lot keeps the limited values written above on its OWN ring; the
    # shared node emits the road's law value.  ``_groundside_weld_keys``
    # (anchors.py) and ``_weld_relimit_moved_xy`` (pipeline.py) both survive
    # as bookkeeping with no reader here.
    return n_changed


def _perimeter_frac_near(poly, region, radius_m: float = 1.5,
                         step_m: float = 1.5) -> float:
    """Fraction of ``poly``'s exterior perimeter lying within ``radius_m``
    of ``region`` (a Polygon/MultiPolygon, or None → 0.0).

    A genuine curbside strip faces a road / open terrain on its outer
    side (that perimeter is NOT near any apron), so its apron-bounded
    fraction is low.  An apron island wrongly carved out by a groundside
    strip is bounded by apron almost all the way around."""
    if region is None or getattr(region, "is_empty", True):
        return 0.0
    try:
        ring = list(poly.exterior.coords)
    except _GEOM_EXC:
        return 0.0
    near = 0.0
    total = 0.0
    for i in range(len(ring) - 1):
        ax, ay = ring[i]
        bx, by = ring[i + 1]
        seg = math.hypot(bx - ax, by - ay)
        if seg < 1e-6:
            continue
        n = max(1, int(seg // step_m))
        sub = seg / n
        for k in range(n):
            t = (k + 0.5) / n
            try:
                if region.distance(Point(ax + (bx - ax) * t,
                                         ay + (by - ay) * t)) <= radius_m:
                    near += sub
            except _GEOM_EXC:
                pass
            total += sub
    return (near / total) if total else 0.0


def _shape_repr_alt(s: "BuiltShape") -> Optional[float]:
    """One representative elevation for a shape, whichever altitude
    convention it carries (flat / sloped / per-vertex)."""
    if s.altitude is not None:
        return float(s.altitude)
    if s.altitude_high is not None and s.altitude_low is not None:
        return 0.5 * (float(s.altitude_high) + float(s.altitude_low))
    if s.node_altitudes:
        vals = [float(a) for a in s.node_altitudes if a is not None]
        if vals:
            return sum(vals) / len(vals)
    return None


# Apron-island / airside-wedged absorption (user 2026-06-03).  A piece is
# reclassified from groundside to flush ``apron`` when it has essentially
# NO open-terrain / road frontage (it is wedged inside the airside: an
# apron island, an apron-hugging clip residue, or a sliver between apron
# and the terminal) AND it touches at least some apron.  Genuine curbside
# faces a road / open terrain on its outer side, so its open fraction is
# well above the gate and it stays groundside.
#
# Measured on the EMITTED groundside shapes, AFTER ``_emit_..._dem`` has
# subtracted apron/terminal (so the perimeter reflects true adjacency) but
# BEFORE ``_separate_..._airside`` opens the 1 m clearance gap (so an
# absorbed piece is still flush with the apron, not 1 m off it).
_APRON_ISLAND_OPEN_MAX = 0.15    # max road/open frontage to still absorb
_APRON_ISLAND_APRON_MIN = 0.15   # must touch at least this much apron
# A qualifying piece whose perimeter is more than this fraction terminal-
# bordered is absorbed into the TERMINAL (flat building pad), not the apron
# (user 2026-06-03: "merge any apron inside a terminal with the terminal").
_APRON_ISLAND_TERM_MAJORITY = 0.5


def _best_bordering_shape(piece: "Polygon", shapes, radius_m: float):
    """The shape in ``shapes`` sharing the most boundary length with ``piece``
    (``None`` if none shares more than 1 m)."""
    pb = piece.buffer(radius_m)
    best = None
    best_share = 1.0
    for a in shapes:
        if a.polygon is None or a.polygon.is_empty:
            continue
        try:
            share = a.polygon.boundary.intersection(pb).length
        except _GEOM_EXC:
            continue
        if share > best_share:
            best_share = share
            best = a
    return best


def _clean_merge(merged):
    """Clean a merged polygon for emit: ``buffer(0)``, keep the largest part,
    and DROP needle/sliver corners — the thin-gap bridge can leave a near-zero-
    angle spike at the seam, and a sliver corner makes the X-Plane emit DROP the
    WHOLE shape (it dropped terminal1 / terminal9 at HECA).  Returns a valid
    ``Polygon`` whose corners clear ``SLIVER_ANGLE_THRESHOLD_DEG``, or ``None``
    (caller bails and the piece falls back) if it can't be made clean."""
    from .pavement.junctions import _drop_sliver_corners
    if merged is None or merged.is_empty:
        return None
    try:
        if not merged.is_valid:
            merged = merged.buffer(0)
        if merged.geom_type == "MultiPolygon":
            merged = max(merged.geoms, key=lambda g: g.area)
        if merged.geom_type != "Polygon" or merged.is_empty:
            return None
        base = merged        # exact intended coverage of the kept part
        ring = list(merged.exterior.coords)
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        ring = _drop_sliver_corners(ring)
        if len(ring) < 3:
            return None
        # Keep the merged polygon's interior rings — a bare
        # Polygon(ring) FILLED them, re-covering a terminal pad the
        # overlap-clip had carved out of the apron (KPHL terminal11,
        # 6,352 m² overlap; no clip pass runs after this absorb).
        from .junction_rules import _rebuild_ring_with_holes
        cleaned = _rebuild_ring_with_holes(ring, merged,
                                           normalize=False)
        if cleaned is None:
            return None
        if not cleaned.is_valid:
            cleaned = cleaned.buffer(0)
        if cleaned.geom_type != "Polygon" or cleaned.is_empty:
            return None
        # The sliver-corner drop may CHORD the ring across a DEEP concave
        # notch and pave ground that was in NEITHER input (CYXY item B: at
        # a 24 m spine step the wedge-absorb chorded ~1.5 k m² of yard into
        # junction #91 → the emitted apron rested 27 % on source).  Needle
        # cleanup only ever changes sliver-scale area, so subtract any
        # ADDED part big enough to be real ground.
        from shapely.ops import unary_union as _uu
        added = cleaned.difference(base)
        big = [g for g in getattr(added, "geoms", [added])
               if g.geom_type == "Polygon" and g.area > 5.0]
        if big:
            reclipped = cleaned.difference(_uu(big))
            if not reclipped.is_valid:
                reclipped = reclipped.buffer(0)
            if reclipped.geom_type == "MultiPolygon":
                reclipped = max(reclipped.geoms, key=lambda g: g.area)
            if reclipped.geom_type != "Polygon" or reclipped.is_empty:
                return None
            cleaned = reclipped
        return cleaned
    except _GEOM_EXC:
        return None



def _has_interior(g) -> bool:
    """True if ``g`` (Polygon / MultiPolygon) has any interior ring (hole)."""
    if g is None or g.is_empty:
        return False
    if g.geom_type == "Polygon":
        return len(list(g.interiors)) > 0
    if g.geom_type == "MultiPolygon":
        return any(len(list(p.interiors)) > 0 for p in g.geoms)
    return False


def merge_small_apron_fragments(layout: "PavementLayout",
                                radius_m: float = 1.5,
                                max_area_m2: float = 600.0) -> int:
    """PRE-SOLVE: fold a SMALL apron piece fully enclosed by apron/terminal into
    its larger neighbour (PURE GEOMETRY — runs before the elevation solver, so
    the merged shape's edges/elevation simply disappear and the solver grades
    the one unified apron; no post-solve step to reconcile).

    Only genuine slivers (< ``max_area_m2``) with NO taxi/runway/open frontage
    qualify, so real aprons (incl. neck-split pads) are left alone.  HOLE-SLICE
    SAFE: never fuses a union that would enclose a void, so the hole-router's
    intentional hole-opening cuts are preserved.  Returns the count merged."""
    aprons = [s for s in layout.shapes if s.role == ROLE_APRON
              and s.polygon is not None and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"]
    if len(aprons) < 2:
        return 0
    try:
        other_union = unary_union([
            s.polygon for s in layout.shapes
            if s.role not in (ROLE_APRON, ROLE_BUILDING)
            and s.polygon is not None and not s.polygon.is_empty
            and s.polygon.geom_type in ("Polygon", "MultiPolygon")])
    except _GEOM_EXC:
        other_union = None
    try:
        road_union = unary_union([
            s.polygon for s in layout.shapes
            if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
            and s.polygon is not None and not s.polygon.is_empty])
    except _GEOM_EXC:
        road_union = None
    n = 0
    for s in sorted(aprons, key=lambda a: a.polygon.area):   # smallest first
        p = s.polygon
        if p is None or p.is_empty or p.area >= max_area_m2:
            continue
        if other_union is not None and \
                _perimeter_frac_near(p, other_union, radius_m) > 0.05:
            continue                       # touches taxi/runway -> real apron
        hosts = [a for a in aprons if a is not s and a.polygon is not None
                 and not a.polygon.is_empty and a.polygon.area > p.area]
        host = _best_bordering_shape(p, hosts, radius_m)
        if host is None:
            continue
        try:
            merged = unary_union([host.polygon, p])
        except _GEOM_EXC:
            continue
        if _has_interior(merged):
            continue                       # would re-bury a void (hole slice)
        cleaned = _clean_merge(merged)
        if cleaned is None:
            continue
        # (s79) the sliver-corner drop can chord the merged ring ACROSS
        # a carved ROAD corridor (the KPHL terminal-incursion class with
        # a road instead of a pad — CYXY pav[1] ramp, 13.5 m² onto
        # SVC11): clip the merge result back off the road rects.
        if road_union is not None and not road_union.is_empty:
            try:
                clipped = cleaned.difference(road_union)
            except _GEOM_EXC:
                clipped = None
            if clipped is not None and clipped.geom_type == "Polygon" \
                    and not clipped.is_empty:
                cleaned = clipped
            elif clipped is not None \
                    and clipped.geom_type == "MultiPolygon":
                cleaned = max(clipped.geoms, key=lambda g: g.area)
        host.polygon = cleaned             # solver assigns node_altitudes later
        s.polygon = None
        n += 1
    if n:
        layout.shapes = [s for s in layout.shapes if s.polygon is not None]
    return n


def _merge_piece_into_apron(piece: "Polygon", apron, radius_m: float,
                            clip_against=None, alt_for_new=None) -> bool:
    """Union ``piece`` into ``apron`` as ONE continuous, node-shared polygon and
    rebuild the apron's per-vertex altitudes: old vertices keep theirs, new
    (piece) vertices sample the apron's PRE-merge surface (``_edge_interp_alt``).
    Returns ``False`` (caller falls back) if the union isn't a clean single
    polygon.  ``clip_against`` (e.g. the terminal-pad union) is subtracted
    from the cleaned merge — ``_clean_merge``'s sliver-corner drop can chord
    a notch ACROSS a terminal edge (KPHL terminal22: a 0.4 m × 2.5 m
    incursion pocket), and no overlap-clip pass runs after this absorb.

    ``alt_for_new`` (owner 2026-08-03, the lateral-contiguity absorption):
    ``f(x, y) -> Optional[float]`` for the NEW vertices instead of the
    pre-merge-surface interpolation.  A DEM-followed LOT is not a plane —
    extrapolating its edge field over an absorbed road stretch imprinted
    steps of 17 % on the merged ring (measured at CYXY before this
    parameter existed); the lot's own emitter samples the DEM at every
    vertex, so an absorbed stretch must too.  ``None`` (every legacy
    caller) keeps the interpolation, byte for byte."""
    from types import SimpleNamespace
    from .clearance import _edge_interp_alt
    before = apron.polygon
    before_na = list(apron.node_altitudes) if apron.node_altitudes else None
    try:
        merged = unary_union([before, piece])
        if merged is not None and merged.geom_type != "Polygon":
            # The piece touches the apron only at a POINT / is offset by a
            # sub-metre gap (near-coincident boundaries, not edge-shared), so
            # the plain union can't fuse them into one polygon (e.g. HECA
            # #2169 ↔ #305).  Bridge ONLY the thin gap between them — the
            # region within ``d`` of BOTH, in NEITHER — so the host apron's
            # other boundaries are left untouched (no morphological close that
            # would round corners / fill notches and desync shared edges).
            d = 0.6
            gap = (before.buffer(d).intersection(piece.buffer(d))
                   .difference(before).difference(piece))
            merged = unary_union([before, piece, gap])
    except _GEOM_EXC:
        return False
    merged = _clean_merge(merged)
    if merged is None:
        return False
    if clip_against is not None and not clip_against.is_empty:
        try:
            if merged.intersects(clip_against):
                clipped = merged.difference(clip_against)
                if clipped.geom_type == "MultiPolygon":
                    clipped = max(clipped.geoms, key=lambda g: g.area)
                if (clipped.geom_type == "Polygon"
                        and not clipped.is_empty):
                    merged = clipped
        except _GEOM_EXC:
            pass
    if before_na is None:
        # Flat apron: the union stays flat at the same altitude, nothing to
        # rebuild per-vertex.
        apron.polygon = merged
        return True
    old = list(before.exterior.coords)
    if old and old[0] == old[-1]:
        old = old[:-1]
    oldmap = {(round(x, 2), round(y, 2)): before_na[k]
              for k, (x, y) in enumerate(old) if k < len(before_na)}
    src = SimpleNamespace(node_altitudes=before_na, polygon=before)
    mean = sum(before_na) / len(before_na)
    new_ring = list(merged.exterior.coords)
    if new_ring and new_ring[0] == new_ring[-1]:
        new_ring = new_ring[:-1]
    new_na = []
    for (x, y) in new_ring:
        z = oldmap.get((round(x, 2), round(y, 2)))
        if z is None and alt_for_new is not None:
            try:
                z = alt_for_new(x, y)
            except _GEOM_EXC:
                z = None
        if z is None:
            try:
                z = _edge_interp_alt(src, x, y)
            except _GEOM_EXC:
                z = None
        new_na.append(z if z is not None else mean)
    apron.polygon = merged
    apron.node_altitudes = new_na
    apron.altitude = None
    apron.altitude_high = None
    apron.altitude_low = None
    return True


def _merge_piece_into_terminal(piece: "Polygon", terminal, radius_m: float,
                               clip_against=None) -> bool:
    """Union ``piece`` into ``terminal`` as one continuous polygon, kept FLAT at
    the terminal's level (building pads are flat).  Same thin-gap bridge as the
    apron merge for point-touching pieces.  ``False`` if the union isn't a clean
    single polygon.  ``clip_against`` (the apron union) is subtracted from the
    cleaned merge: the 0.6 m gap-bridge can lap onto an adjacent apron's
    footprint, and the apron-side absorb bridges the SAME thin gap from the
    other side — the two independently-bridged rings overlapped by a ~0.1 m²
    sliver at KPHL terminal22, with no overlap-clip pass running after."""
    before = terminal.polygon
    try:
        merged = unary_union([before, piece])
        if merged is not None and merged.geom_type != "Polygon":
            d = 0.6
            gap = (before.buffer(d).intersection(piece.buffer(d))
                   .difference(before).difference(piece))
            merged = unary_union([before, piece, gap])
    except _GEOM_EXC:
        return False
    merged = _clean_merge(merged)
    if merged is None:
        return False
    if clip_against is not None and not clip_against.is_empty:
        try:
            if merged.intersects(clip_against):
                clipped = merged.difference(clip_against)
                if clipped.geom_type == "MultiPolygon":
                    clipped = max(clipped.geoms, key=lambda g: g.area)
                if (clipped.geom_type == "Polygon"
                        and not clipped.is_empty):
                    merged = clipped
        except _GEOM_EXC:
            pass
    lvl = _shape_repr_alt(terminal)
    terminal.polygon = merged
    if lvl is not None:
        terminal.altitude = round(lvl, 1)
        terminal.node_altitudes = None
        terminal.altitude_high = None
        terminal.altitude_low = None
    return True


def _absorb_apron_enclosed_groundside(
        layout: "PavementLayout",
        radius_m: float = 1.5) -> int:
    """Reclassify emitted groundside shapes that sit wedged inside the
    airside — apron islands, apron-hugging clip residue, apron/terminal
    sandwich slivers — back into flush ``apron`` pavement at the
    neighbouring aprons' elevation, instead of leaving them as
    DEM-following groundside that would otherwise become a 1 m-gapped
    sliver after the separation pass.

    A piece qualifies when its perimeter has at most ``_APRON_ISLAND_
    OPEN_MAX`` open (road / terrain) frontage and touches at least
    ``_APRON_ISLAND_APRON_MIN`` apron.  Genuine curbside — which faces a
    road on its outer side — keeps a high open fraction and is left alone.

    Runs AFTER ``_emit_groundside_pavement_dem`` and BEFORE
    ``_separate_groundside_from_airside``.  Returns the number absorbed.
    """
    gs_shapes = [s for s in layout.shapes
                 if s.role == ROLE_GROUNDSIDE_PAVEMENT
                 and s.polygon is not None and not s.polygon.is_empty]
    if not gs_shapes:
        return 0
    apron_shapes = [s for s in layout.shapes
                    if s.role == ROLE_APRON
                    and s.polygon is not None and not s.polygon.is_empty]
    if not apron_shapes:
        return 0
    try:
        apron_union = unary_union([s.polygon for s in apron_shapes])
    except _GEOM_EXC:
        return 0
    terminal_shapes = [s for s in layout.shapes
                       if s.role == ROLE_BUILDING
                       and s.polygon is not None and not s.polygon.is_empty]
    term_union = None
    try:
        if terminal_shapes:
            term_union = unary_union([t.polygon for t in terminal_shapes])
    except _GEOM_EXC:
        term_union = None
    absorbed = 0
    # Running clip unions: a piece absorbed into the APRON earlier in
    # this loop is apron footprint the next TERMINAL merge must not lap
    # onto (and vice versa) — the start-of-pass unions don't contain
    # it, and both sides' 0.6 m gap-bridges can otherwise claim the
    # same thin gap (KPHL terminal22 ∩ apron, ~0.1 m² sliver).
    apron_clip = apron_union
    term_clip = term_union
    for s in gs_shapes:
        p = s.polygon
        apron_f = _perimeter_frac_near(p, apron_union, radius_m)
        term_f = _perimeter_frac_near(p, term_union, radius_m)
        open_f = max(0.0, 1.0 - apron_f - term_f)
        # Enclosed (no open road/terrain frontage) AND touches apron OR is
        # mostly terminal-surrounded.
        if not (open_f <= _APRON_ISLAND_OPEN_MAX
                and (apron_f >= _APRON_ISLAND_APRON_MIN
                     or term_f >= _APRON_ISLAND_TERM_MAJORITY)):
            continue
        # Majority-terminal perimeter -> absorb into the TERMINAL (flat pad).
        if term_f >= _APRON_ISLAND_TERM_MAJORITY and terminal_shapes:
            host_t = _best_bordering_shape(p, terminal_shapes, radius_m)
            if host_t is not None and _merge_piece_into_terminal(
                    p, host_t, radius_m, clip_against=apron_clip):
                s.polygon = None
                absorbed += 1
                try:
                    term_clip = unary_union(
                        [g for g in (term_clip, host_t.polygon)
                         if g is not None])
                except _GEOM_EXC:
                    pass
                continue
        # Clip to the terminal footprint so aircraft apron never intrudes
        # under the building; keep the largest surviving piece.
        q = p
        if term_union is not None:
            try:
                d = p.difference(term_union)
            except _GEOM_EXC:
                d = p
            if d is None or d.is_empty:
                q = None
            elif d.geom_type == "Polygon":
                q = d
            elif d.geom_type == "MultiPolygon":
                parts = [g for g in d.geoms
                         if g.geom_type == "Polygon" and not g.is_empty]
                q = max(parts, key=lambda g: g.area) if parts else None
        if q is None or q.area < _GROUNDSIDE_MIN_AREA_M2:
            # Entirely under the terminal / too small once clipped — drop
            # it (mark the source shape empty; it is removed below).
            s.polygon = None
            absorbed += 1
            continue
        # Double-source coverage (s70 Phoenix triage): when the emitted
        # aprons ALREADY cover essentially the whole piece — apt.dat
        # apron and OSM groundside both map the same pocket — merging or
        # re-tagging emits a duplicate on top of pavement that is
        # already there (KLUF apron#74∩island#106 5 752 m², KSDL
        # #72∩#152 104 m²).  The piece is fully redundant: drop it.
        # Terminal-wedged islands (HECA) keep >1 % outside the aprons
        # and are unaffected.
        try:
            if q.difference(apron_union).area <= max(1.0, 0.01 * q.area):
                s.polygon = None
                absorbed += 1
                continue
        except _GEOM_EXC:
            pass
        # (user 2026-06-03) Genuinely MERGE the piece into the apron it borders
        # most — one continuous, node-shared polygon — instead of leaving a
        # standalone flat "apron-island" whose coincident-but-unshared vertices
        # tear into cliffs when the apron surface moves.  This MERGE is
        # geometry-only (no altitude needed) and is the PRE-solve path: the
        # solver grades the unified apron, so the cliff is gone at the source.
        # The flush standalone re-tag below is the fallback when there is no
        # apron to merge into.
        host = _best_bordering_shape(q, apron_shapes, radius_m)
        if host is not None and _merge_piece_into_apron(
                q, host, radius_m, clip_against=term_clip):
            s.polygon = None
            absorbed += 1
            try:
                apron_clip = unary_union(
                    [g for g in (apron_clip, host.polygon)
                     if g is not None])
            except _GEOM_EXC:
                pass
            continue
        # Standalone re-tag fallback (no bordering apron to merge into): the
        # piece becomes a flush apron-island at the mean representative
        # altitude of the neighbouring aprons.  PRE-solve the aprons have no
        # altitude yet → leave the piece as groundside (it gets a DEM altitude
        # + the separation gap) rather than guessing a flat level.
        try:
            halo = p.buffer(radius_m + 0.5)
            neigh = [_shape_repr_alt(a) for a in apron_shapes
                     if a.polygon.intersects(halo)]
        except _GEOM_EXC:
            neigh = []
        neigh = [a for a in neigh if a is not None]
        if not neigh:
            neigh = [a for a in (_shape_repr_alt(a) for a in apron_shapes)
                     if a is not None]
        if not neigh:
            continue                # no usable altitude — leave as gs
        alt = round(sum(neigh) / len(neigh), 1)
        s.polygon = q
        s.role = ROLE_APRON
        s.ref = "apron-island"
        s.altitude = alt
        s.node_altitudes = None
        s.altitude_high = None
        s.altitude_low = None
        absorbed += 1
    if absorbed:
        layout.shapes = [s for s in layout.shapes if s.polygon is not None]
    return absorbed



def _emit_groundside_pavement_dem(
        layout: "PavementLayout",
        dem,
        tile_lat: int,
        tile_lon: int,
        densify_step_m: float = 15.0,
        terminal_gap_m: float = 0.1,
        ) -> int:
    """Emit each saved groundside pavement polygon as a DEM-following
    shape with per-vertex altitudes.

    Per user 2026-04-29: pavement that wraps around the GROUNDSIDE
    of a terminal building (curbside, drop-off, parking) sits at a
    different elevation than the airside apron — at CYXY the
    terminal is cut into the hill so the airside apron is several
    metres lower than the road frontage.  The earlier subtraction
    pass (see ``_terminal_groundside_zone``) keeps the airside
    pavement clean of these strips, but they still belong in the
    output: they should render at local DEM elevation and should
    NOT touch the terminal building footprint (a 0.1 m gap is
    already applied during capture).

    Implementation:
      1. Iterate ``layout._groundside_polys`` (captured during
         ``build_airport_pavement`` immediately before the
         groundside subtraction).
      2. Densify each polygon's exterior to ``densify_step_m`` so
         per-vertex altitudes resolve at the same spatial
         frequency as the boundary ribbon (15 m step → typical
         curbside has 5–10 vertices per side).
      3. Sample DEM at every vertex; emit as ``BuiltShape`` with
         role ``ROLE_GROUNDSIDE_PAVEMENT``, ``node_altitudes`` set,
         and ``altitude``/``altitude_high``/``altitude_low`` left
         None so the OSM emitter writes per-vertex altitude tags.

    Returns the number of polygons emitted.
    """
    from .pipeline import _load_osm_big_roads
    polys = list(getattr(layout, "_groundside_polys", []) or [])
    if not polys:
        return 0
    # Build a buffered union of every emitted terminal shape — we
    # subtract this from each groundside polygon so the result
    # leaves a ``terminal_gap_m`` clearance to every actual
    # terminal polygon in the final layout.  Using layout shapes
    # (not OSM source) handles cases where apt.dat row-110 /
    # DSF residue absorption produced a slightly different ring.
    _term_buf = None
    try:
        _t_polys = [s.polygon for s in layout.shapes
                    if s.role == ROLE_BUILDING
                    and s.polygon is not None
                    and not s.polygon.is_empty]
        if _t_polys:
            _term_buf = unary_union(
                [tp.buffer(terminal_gap_m) for tp in _t_polys])
            if _term_buf.is_empty:
                _term_buf = None
    except _GEOM_EXC:
        _term_buf = None
    # Also subtract every other pavement-bearing layout shape so
    # the groundside pavement never overlaps a rect / junction /
    # apron / runway / terminal / wall / ramp.  The boundary
    # ribbon is excluded — by design it traces over everything.
    NON_OVERLAP_ROLES = {
        ROLE_RUNWAY, ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
        ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_APRON, ROLE_JUNCTION,
        ROLE_TUNNEL_RAMP, ROLE_RETAINING_WALL,
    }
    _other_buf = None
    try:
        _other_polys = [s.polygon for s in layout.shapes
                        if s.role in NON_OVERLAP_ROLES
                        and s.polygon is not None
                        and not s.polygon.is_empty]
        if _other_polys:
            _other_buf = unary_union(_other_polys)
            if _other_buf.is_empty:
                _other_buf = None
    except _GEOM_EXC:
        _other_buf = None
    cuts = []
    if _term_buf is not None:
        cuts.append(_term_buf)
    if _other_buf is not None:
        cuts.append(_other_buf)
    if cuts:
        try:
            cut_union = unary_union(cuts) if len(cuts) > 1 else cuts[0]
        except _GEOM_EXC:
            cut_union = None
        if cut_union is not None and not cut_union.is_empty:
            clipped: List[Polygon] = []
            for p in polys:
                try:
                    q = p.difference(cut_union)
                except _GEOM_EXC:
                    continue
                if q is None or q.is_empty:
                    continue
                if q.geom_type == "Polygon":
                    if q.area >= 5.0:
                        clipped.append(q)
                elif q.geom_type == "MultiPolygon":
                    for g in q.geoms:
                        if (g.geom_type == "Polygon"
                                and not g.is_empty
                                and g.area >= 5.0):
                            clipped.append(g)
            polys = clipped
    if not polys:
        return 0
    # Two captured groundside polygons can themselves overlap (the cut
    # above only subtracts terminals / airside, not other groundside) —
    # leaving a self-overlap (HECA #2222 ∩ #2223, 0.1 m²).  Clip each
    # against the union of already-accepted polygons (largest first, so
    # the smaller piece yields) so groundside never overlaps groundside.
    polys.sort(key=lambda g: -g.area)
    _emitted_union = None
    deconflicted: List[Polygon] = []
    for p in polys:
        if _emitted_union is not None:
            try:
                q = p.difference(_emitted_union)
            except _GEOM_EXC:
                q = p
            if q is None or q.is_empty:
                continue
            if q.geom_type == "Polygon":
                p = q if q.area >= 5.0 else None
            elif q.geom_type == "MultiPolygon":
                pieces = [g for g in q.geoms
                          if g.geom_type == "Polygon" and g.area >= 5.0]
                p = max(pieces, key=lambda g: g.area) if pieces else None
            else:
                p = None
            if p is None:
                continue
        deconflicted.append(p)
        try:
            _emitted_union = (p if _emitted_union is None
                              else unary_union([_emitted_union, p]))
        except _GEOM_EXC:
            _emitted_union = p
    polys = deconflicted
    if not polys:
        return 0
    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    # THE LAW DATUM this pass grades to — computed ONCE per pass
    # (single-pass principle), read from the SAME authority order
    # the emitter resolves a shared node with.
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _stats = _law_seat_stats(layout, "emit_groundside_pavement_dem")
    n_emitted = 0
    for p in polys:
        _seat_out: dict = {}
        built = _dem_follow_polygon(p, _dem_at, densify_step_m,
                                    law_anchors=_law_anchors,
                                    anchor_key=_anchor_key, stats=_stats,
                                    seat_out=_seat_out)
        if built is None:
            continue
        new_poly, node_alts = built
        _new = BuiltShape(
            polygon=new_poly,
            role=ROLE_GROUNDSIDE_PAVEMENT,
            ref="groundside",
            node_altitudes=node_alts)
        setattr(_new, _LAW_SEATED_ATTR, bool(_seat_out.get("law_seated")))
        layout.shapes.append(_new)
        n_emitted += 1
    return n_emitted


def _reclassify_groundside_orphan_junctions(
        layout: "PavementLayout",
        dem,
        tile_lat: int,
        tile_lon: int,
        vertex_match_tol_m: float = 0.5,
        ) -> int:
    """RECLASSIFY junction polygons that connect ONLY to groundside
    pavement (no path through shared vertices to any airside rect /
    runway / terminal) into DEM-following groundside pavement.

    Per user 2026-04-29 (CYXY -10111 + -10115): the rect/junction
    tessellator can leave junction polygons sitting next to a groundside
    polygon when the apt.dat row-110 / DSF union has pavement outside the
    groundside-zone subtraction's perpendicular extent.  Those junctions
    get the airside-flat altitude during the solver (they were classified
    airside even though they don't touch any airside pavement), then they
    share an edge with the DEM-following groundside polygon at an altitude
    mismatch — X-Plane renders that as a cliff.

    Earlier versions DROPPED these junctions.  That was wrong (user
    2026-05-21): pav_union is the source of truth and these junctions
    cover REAL pavement — at HECA the DSF adds large terminal aprons with
    no taxi centerline that are vertex-disconnected from the airside
    network, and dropping them erased ~44k m² of genuine apron.  Instead
    we KEEP the pavement and re-elevate it to follow the DEM (like the
    groundside ribbon it abuts), which both preserves coverage AND removes
    the cliff — the original goal.

    Detection rule (a junction is reclassified if BOTH):
        1. It shares ≥1 vertex with a ``ROLE_GROUNDSIDE_PAVEMENT``
           polygon.
        2. It does NOT share any vertex with an airside seed shape
           (runway / primary_parallel / secondary_parallel / stub /
           cross_connector / terminal), directly or transitively through
           other junction polygons (BFS over junction-junction shared
           vertices) — so genuine apron→runway/terminal connectors are
           left airside (SPJC primary_parallels U and M relied on this).

    Returns the number of junctions reclassified.
    """
    # APRON is airside (aircraft pavement), user 2026-05-22: a junction
    # abutting an apron is airside-connected, so it must NOT be
    # reclassified to groundside (groundside = cars/buildings).  Without
    # APRON here, large no-centerline terminal *aircraft* aprons were
    # reclassified to groundside and ended up sharing nodes/edges (and
    # overlapping) airside aprons — violating the no-shared-boundary
    # invariant.  With it, they stay airside (kept as junction → apron),
    # and only junctions touching ONLY groundside become groundside.
    AIRSIDE_SEED_ROLES = {
        ROLE_RUNWAY, ROLE_PRIMARY_PARALLEL,
        ROLE_SECONDARY_PARALLEL, ROLE_STUB,
        ROLE_CROSS_CONNECTOR, ROLE_BUILDING, ROLE_APRON,
    }
    bucket_size = vertex_match_tol_m

    def _verts_buckets(s: "BuiltShape") -> List[Tuple[int, int]]:
        if s.polygon is None or s.polygon.is_empty:
            return []
        try:
            coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            return []
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        out = []
        for x, y in coords:
            out.append((int(round(x / bucket_size)),
                        int(round(y / bucket_size))))
        return out
    # Index every junction's vertex buckets (1-bucket halo so
    # near-misses still match neighbours).
    junction_idxs = [i for i, s in enumerate(layout.shapes)
                      if s.role == ROLE_JUNCTION
                      and s.polygon is not None
                      and not s.polygon.is_empty]
    if not junction_idxs:
        return 0
    junction_buckets: Dict[int, set] = {}
    bucket_to_jidx: Dict[Tuple[int, int], List[int]] = {}
    for ji in junction_idxs:
        bs = _verts_buckets(layout.shapes[ji])
        halo: set = set()
        for bx, by in bs:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    halo.add((bx + dx, by + dy))
        junction_buckets[ji] = halo
        for b in bs:
            bucket_to_jidx.setdefault(b, []).append(ji)
    # Airside seeds (rect / runway / terminal vertex buckets).
    seed_buckets: set = set()
    for s in layout.shapes:
        if s.role not in AIRSIDE_SEED_ROLES:
            continue
        for b in _verts_buckets(s):
            seed_buckets.add(b)
    # Build airside connectivity component over junctions: BFS
    # starting from junctions that share a bucket with any
    # airside seed, propagating through junction-junction
    # shared buckets.
    airside_set: set = set()
    for ji in junction_idxs:
        if junction_buckets[ji] & seed_buckets:
            airside_set.add(ji)
    queue = list(airside_set)
    while queue:
        ji = queue.pop()
        for b in junction_buckets[ji]:
            for kj in bucket_to_jidx.get(b, []):
                if kj in airside_set:
                    continue
                airside_set.add(kj)
                queue.append(kj)
    # Groundside vertex buckets (1-bucket halo).
    gs_buckets: set = set()
    for s in layout.shapes:
        if s.role != ROLE_GROUNDSIDE_PAVEMENT:
            continue
        for bx, by in _verts_buckets(s):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    gs_buckets.add((bx + dx, by + dy))
    if not gs_buckets:
        return 0
    orphan_set: set = set()
    for ji in junction_idxs:
        if ji in airside_set:
            continue
        if junction_buckets[ji] & gs_buckets:
            orphan_set.add(ji)
    if not orphan_set:
        return 0
    # Building union (buffered to the groundside clearance): an orphan
    # junction can fully enclose a building footprint, and re-roling it to
    # groundside verbatim would cover that building — a 100 %-contained
    # self-overlap once emitted (the OSM emitter drops interior rings, so
    # the hole a later ``_separate`` cut would leave does not survive).
    # Subtract buildings HERE so the re-roled groundside honours the gap at
    # its source, like every other groundside rebuild path.
    _bldg_buf = None
    try:
        _bpolys = [b.polygon for b in layout.shapes
                   if b.role == ROLE_BUILDING
                   and b.polygon is not None and not b.polygon.is_empty]
        if _bpolys:
            _bldg_buf = unary_union(
                [bp.buffer(GROUNDSIDE_CLEARANCE_M) for bp in _bpolys])
            if _bldg_buf.is_empty:
                _bldg_buf = None
    except _GEOM_EXC:
        _bldg_buf = None
    # Re-elevate each orphan junction to follow the DEM and reclassify it
    # as groundside pavement — keep the pavement, lose the cliff.  If the
    # DEM-follow can't be built, LEAVE the shape unchanged (never erase
    # real pavement).
    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    # THE LAW DATUM this pass grades to — computed ONCE per pass
    # (single-pass principle), read from the SAME authority order
    # the emitter resolves a shared node with.
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _stats = _law_seat_stats(layout, "reclassify_groundside_orphan_junctions")
    n = 0
    new_shapes: List["BuiltShape"] = []
    for ji in orphan_set:
        s = layout.shapes[ji]
        # Cut buildings out first — the result may be a polygon with a hole
        # (opened by ``_dem_follow_polygon``) or split into several pieces.
        src_polys: List[Polygon] = [s.polygon]
        if _bldg_buf is not None:
            try:
                diff = s.polygon.difference(_bldg_buf)
            except _GEOM_EXC:
                diff = s.polygon
            if diff is not None and not diff.is_empty:
                src_polys = ([diff] if diff.geom_type == "Polygon"
                             else [g for g in getattr(diff, "geoms", [])
                                   if g.geom_type == "Polygon"
                                   and not g.is_empty
                                   and g.area >= _GROUNDSIDE_MIN_AREA_M2])
        builts = []
        # The orphan junction is SOLVED airside a moment ago: its own
        # ring values are the law this re-role must carry across, not a
        # field to re-derive from terrain.
        _prior = _shape_prior(s)
        _seat_out = {}
        for sp in src_polys:
            b = _dem_follow_polygon(sp, _dem_at,
                                    law_anchors=_law_anchors,
                                    anchor_key=_anchor_key,
                                    prior=_prior, stats=_stats,
                                    seat_out=_seat_out)
            if b is not None:
                builts.append(b)
        if not builts:
            continue          # never erase real pavement — leave unchanged
        # Largest piece keeps the shape's identity; extras are appended.
        builts.sort(key=lambda t: -t[0].area)
        new_poly, node_alts = builts[0]
        s.polygon = new_poly
        s.role = ROLE_GROUNDSIDE_PAVEMENT
        s.ref = "groundside"
        s.node_altitudes = node_alts
        setattr(s, _LAW_SEATED_ATTR, bool(_seat_out.get("law_seated")))
        for extra_poly, extra_alts in builts[1:]:
            _extra = BuiltShape(
                polygon=extra_poly, role=ROLE_GROUNDSIDE_PAVEMENT,
                ref="groundside", node_altitudes=extra_alts)
            setattr(_extra, _LAW_SEATED_ATTR,
                    bool(_seat_out.get("law_seated")))
            new_shapes.append(_extra)
        n += 1
    layout.shapes.extend(new_shapes)
    return n


# Clearance (m) groundside pavement must keep from any terminal / airside
# polygon (user 2026-05-22): groundside is for cars/buildings and follows
# the DEM, so it sits at a different elevation than the graded airside and
# must NOT share a node or edge with it.  A clearance just over the
# shared-vertex snap tolerance guarantees separation (no shared node after
# snapping, no degenerate seam slivers in Triangle4XP).
GROUNDSIDE_CLEARANCE_M = SHARED_VERTEX_TOL_M + 0.5  # 1.0 m
_GROUNDSIDE_MIN_AREA_M2 = 5.0

# ── R7b CLAUSE 3 — PARALLEL FRONTAGE CUTS BACK TO DEM ────────────────
# Owner ruling 2026-08-15 late (the sink ruling): "a road running
# PARALLEL to an apron for more than 1.5x the road's width takes the
# STANDARD GROUNDSIDE CUTBACK and stays AT DEM — roads commonly run up
# to and along terminals at DIFFERENT LEVELS (at CYXY the landside
# frontage road is a second-story level several metres above the airside
# apron; that separation is real and must be preserved, not welded
# away)."  Fable amendment A2 rules the mechanism GEOMETRIC and names
# this machinery: the cutback IS ``_separate_groundside_from_airside``'s
# clearance buffer, its mouth windows and its DEM re-follow, applied to
# the ROAD face instead of to a lot.  Nothing new is invented — a road
# that no longer shares a node with the apron cannot be welded to it,
# and the level separation survives by construction.
ROAD_FRONTAGE_SPAN_WIDTH_FACTOR = 1.5


def _face_carriageway_width(polygon) -> float:
    """A road face's OWN carriageway width: ``2·area / perimeter``.

    For an L×W strip that is ``LW/(L+W)`` → W as L grows, and a road
    face IS that shape.  Deliberately measured off the face's own
    geometry: an axis-based or centerline-based width would be a SECOND
    measurement of the same quantity, free to drift from the one the
    free-road knife already keys on.
    """
    try:
        perimeter = polygon.length
        if perimeter <= 0.0:
            return 0.0
        return 2.0 * polygon.area / perimeter
    except _GEOM_EXC:
        return 0.0


def _longest_contact_run_m(ring, clip_geom) -> float:
    """The longest CONTIGUOUS run of ``ring`` inside ``clip_geom`` — the
    edge-contact span R7b measures its 1.5× against.

    Contiguity is the whole point of the ruling's word PARALLEL: a road
    that touches an apron at two separate MOUTHS is not a road running
    along it, and summing the two runs would say it was.
    """
    try:
        inter = ring.intersection(clip_geom)
    except _GEOM_EXC:
        return 0.0
    if inter is None or inter.is_empty:
        return 0.0
    parts = ([inter] if inter.geom_type == "LineString"
             else list(getattr(inter, "geoms", ())))
    return max((p.length for p in parts if p.geom_type == "LineString"),
               default=0.0)


def _cut_back_road_frontage(layout, frontage_clips, _dem_at,
                            span_factor: float
                            = ROAD_FRONTAGE_SPAN_WIDTH_FACTOR,
                            stats=None) -> int:
    """R7b clause 3 in place: every road face that runs along an apron
    for more than ``span_factor`` × its own carriageway width is CUT
    BACK off it and DEM-re-follows.  Returns the number of faces cut.

    ``frontage_clips`` — the apron/junction clearance buffers ALREADY
    built by :func:`_separate_groundside_from_airside`, with the mouth
    windows subtracted.  That is what makes mouths exempt in both
    directions at once: a mouth is outside the clip, so it neither
    counts toward the parallel span nor gets cut, and the road keeps its
    shared edge — and therefore its weld — exactly there.  R7b clause 1
    ("a road welds to an apron ONLY at a mouth") is the same geometry
    read from the other side.

    A cut that would ERASE the road or FRAGMENT it into several pieces
    is refused: a cutback opens a 1 m gap along a flank, and anything
    else is a severance this clause never authorised.
    """
    if not frontage_clips:
        return 0
    from shapely.strtree import STRtree
    try:
        tree = STRtree(frontage_clips)
    except _GEOM_EXC:
        return 0
    anchors_by_role: dict = {}
    n_cut = 0
    for s in layout.shapes:
        if s.role not in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        width = _face_carriageway_width(poly)
        if width <= 0.0:
            continue
        need = span_factor * width
        ring = poly.exterior
        try:
            hits = [frontage_clips[int(i)] for i in tree.query(poly)]
        except _GEOM_EXC:
            continue
        qualifying = [g for g in hits
                      if _longest_contact_run_m(ring, g) > need]
        if not qualifying:
            continue
        try:
            cut = (qualifying[0] if len(qualifying) == 1
                   else unary_union(qualifying))
            diff = poly.difference(cut)
        except _GEOM_EXC:
            continue
        parts = [p for p in ([diff] if diff.geom_type == "Polygon"
                             else list(getattr(diff, "geoms", ())))
                 if p.geom_type == "Polygon" and not p.is_empty
                 and p.area >= _GROUNDSIDE_MIN_AREA_M2]
        if len(parts) != 1 or parts[0].equals(poly):
            continue        # erased or fragmented — not a cutback
        if len(parts[0].interiors) > len(poly.interiors):
            # A HOLE is not a cutback either, and this one is measured:
            # where an apron pokes into a road's bay the difference
            # returns an ANNULUS, and ``_dem_follow_polygon`` then opens
            # the hole with a corridor — rewriting the road's footprint
            # instead of trimming its flank (SPJC 2026-08-16: 4 → 9
            # ``shape_interior_ring`` ways, and the road at
            # -12.0313,-77.1071 went from a 10-node face spanning 1.89 m
            # to a 12-node face + interior ring spanning 2.87 m).
            continue
        if s.role not in anchors_by_role:
            _a = law_anchor_values(layout, for_role=s.role)
            anchors_by_role[s.role] = (_a, law_anchor_key(layout, _a))
        _law_anchors, _anchor_key = anchors_by_role[s.role]
        _seat_out: dict = {}
        built = _dem_follow_polygon(parts[0], _dem_at, simplify_tol=0.0,
                                    law_anchors=_law_anchors,
                                    anchor_key=_anchor_key, stats=stats,
                                    seat_out=_seat_out)
        if built is None:
            continue
        # MUTATED IN PLACE, never rebuilt: the face carries slice state
        # (``source_axis``, ``ref``, centerline provenance) that a fresh
        # ``BuiltShape`` would silently drop.
        s.polygon, s.node_altitudes = built
        setattr(s, _LAW_SEATED_ATTR, bool(_seat_out.get("law_seated")))
        n_cut += 1
    return n_cut


def _merge_touching_groundside(
        layout: "PavementLayout", dem, tile_lat: int, tile_lon: int,
        touch_tol: float = 0.5, min_shared_m: float = 2.0) -> int:
    """Merge groundside pavement pieces that share a real boundary into ONE
    shape (user 2026-06-26).  Groundside is DEM-following pavement with no spine
    or internal structure, so two pieces sharing a ≥``min_shared_m`` boundary were
    SPLIT upstream (junction-emit ``pav_union.difference(rects)`` / overlap-clip on
    a multi-polygon source union) — they should be a single surface (CYXY parking
    lot @(-465,408): two pieces 899+1276 m² touching along a 55 m seam).  Pieces
    that merely touch at a point are left alone (no ``min_shared_m`` seam).
    """
    if _os.environ.get("O4_MERGE_GROUNDSIDE", "1") != "1":
        return 0
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    gs = [s for s in layout.shapes
          if s.role == ROLE_GROUNDSIDE_PAVEMENT and s.polygon is not None
          and not s.polygon.is_empty and s.polygon.geom_type == "Polygon"]
    if len(gs) < 2:
        return 0
    polys = [s.polygon for s in gs]
    n = len(gs)
    parent = list(range(n))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tree = STRtree(polys)
    for i in range(n):
        try:
            cand = tree.query(polys[i].buffer(touch_tol))
        except _GEOM_EXC:
            continue
        for qj in cand:
            j = int(qj)
            if j <= i:
                continue
            try:
                if polys[i].distance(polys[j]) > touch_tol:
                    continue
                # NEAR-coincident flush runs count as shared boundary
                # (user 2026-07-04, CYXY P4): a demoted connector meets
                # the lot it serves within millimetres but rarely
                # EXACTLY, so the exact ring∩ring length reads 0 while
                # the pieces are physically one surface — left unmerged,
                # their independent DEM-follow/shift left coincident
                # nodes 2.6 m apart.  Measure the run of ring i within
                # ``touch_tol`` of ring j instead (identity on exactly-
                # shared boundaries).
                shared = polys[i].exterior.intersection(
                    polys[j].exterior.buffer(touch_tol))
                if getattr(shared, "length", 0.0) < min_shared_m:
                    continue            # point/sliver touch — not a split seam
            except _GEOM_EXC:
                continue
            ri, rj = _find(i), _find(j)
            if ri != rj:
                parent[ri] = rj

    groups: dict = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)

    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    # THE LAW DATUM this pass grades to — computed ONCE per pass
    # (single-pass principle), read from the SAME authority order
    # the emitter resolves a shared node with.
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _stats = _law_seat_stats(layout, "merge_touching_groundside")
    merged_objs: set = set()
    new_shapes: list = []
    n_merged = 0
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        try:
            # Snap each piece onto the accumulated union before
            # unioning: near-coincident flush pairs (see above) stay
            # TWO polygons under a plain union — the sub-tolerance
            # hairline between them never dissolves.  ``snap`` moves
            # only vertices already within ``touch_tol`` of the other
            # ring; exactly-shared boundaries are untouched.
            u = polys[idxs[0]]
            for k in idxs[1:]:
                u = unary_union([u, snap(polys[k], u, touch_tol)])
        except _GEOM_EXC:
            continue
        if u.is_empty:
            continue
        pieces = ([u] if u.geom_type == "Polygon"
                  else [g for g in getattr(u, "geoms", []) if g.geom_type == "Polygon"])
        if not pieces:
            continue
        # The merged pieces ARE the prior surface: the union is one
        # shape now, but its field was already law-seated piece by piece
        # and a DEM re-follow from scratch would throw that away (the
        # merge is a geometry operation, not a re-grading event).
        _prior = _shape_prior(*[gs[k] for k in idxs])
        for k in idxs:
            merged_objs.add(id(gs[k]))
        for p in pieces:
            _seat_out = {}
            built = _dem_follow_polygon(p, _dem_at, simplify_tol=0.0,
                                        law_anchors=_law_anchors,
                                        anchor_key=_anchor_key,
                                        prior=_prior, stats=_stats,
                                        seat_out=_seat_out)
            if built is None:
                continue
            np_, na = built
            _new = BuiltShape(
                polygon=np_, role=ROLE_GROUNDSIDE_PAVEMENT,
                ref="groundside", node_altitudes=na)
            setattr(_new, _LAW_SEATED_ATTR,
                    bool(_seat_out.get("law_seated")))
            new_shapes.append(_new)
        n_merged += len(idxs) - 1
    if not merged_objs:
        return 0
    layout.shapes = [s for s in layout.shapes
                     if id(s) not in merged_objs] + new_shapes
    return n_merged


def _separate_groundside_from_airside(
        layout: "PavementLayout", dem, tile_lat: int, tile_lon: int,
        clearance: float = GROUNDSIDE_CLEARANCE_M,
        preserve_field: bool = False,
        road_frontage_cutback: bool = False,
        groundside_clip: bool = True) -> int:
    """Clip every groundside polygon so it keeps ``clearance`` from all
    terminal / airside pavement — enforcing the invariant that groundside
    shares no node or edge with terminal or airside (it is separate
    car/building pavement at DEM elevation).  Re-derives DEM + grade-
    limited altitudes for the clipped result.  Returns shapes clipped.

    Robust to the non-conformance case the apron-seed rule can't catch:
    a groundside polygon that *overlaps* airside without sharing a vertex
    is still cut back to the clearance gap.

    ``preserve_field=True`` (the POST-solve call sites): a clipped piece
    keeps its existing altitude FIELD — each rebuilt vertex takes
    ``DEM + deviation-of-nearest-original-vertex`` instead of a raw
    DEM re-follow.  Post-solve, groundside carries the reach re-level /
    chord-limit / weld field; resetting a clipped piece to raw DEM
    detached it from every road welded to it at solve time (CYXY: a
    mouth lot reset 695.8 → 700.6 = 5 m road↔lot yanks).

    ``road_frontage_cutback=True`` additionally runs R7b clause 3
    (:func:`_cut_back_road_frontage`) over the SAME clearance buffers
    and mouth windows built here.  ``groundside_clip=False`` runs ONLY
    that clause.  Both default to the pre-R7b behaviour, so every
    existing call site is byte-identical; production reaches the clause
    through ONE explicit pre-solve call in ``pipeline`` (a road cut back
    post-solve would throw away the solved road field, which is the
    opposite of "stays at DEM").
    """
    AIRSIDE_ROLES = {
        ROLE_RUNWAY, ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
        ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_APRON, ROLE_JUNCTION,
        ROLE_BUILDING, ROLE_TUNNEL_RAMP, ROLE_RETAINING_WALL,
    }
    # Groundside MAY share an edge with a SERVICE ROAD / junction (user
    # 2026-06-26, STANDING LAW): a parking lot is SERVED by its service road,
    # so they touch — opening the 1 m clearance gap there DISCONNECTS the road
    # from the lot it feeds (CYXY SVC1 ↔ lot @(-472,404): a cliff across the
    # gap).  ``ROLE_SERVICE_ROAD`` / ``ROLE_SERVICE_JUNCTION`` are therefore
    # deliberately absent from ``AIRSIDE_ROLES`` above.  Groundside is still
    # cut back from BUILDINGS and aircraft pavement.
    # Truck-route END mouths (user ruling 2026-07-04, CYXY P4): a lot is
    # groundside BECAUSE its connection is a service road — the connection
    # is identified EARLY and the clearance gap is never cut across it.
    # Apron/junction pavement carrying a truck-route END abuts the lot
    # that route serves; the demotion sweeps later re-role that connector
    # to groundside, but a gap cut now is never re-closed, leaving the
    # connector and its lot two disjoint DEM-followed surfaces (CYXY
    # route N: 165 m² connector 1.00 m from its 6.8 k m² lot).  Such a
    # shape keeps the shared edge inside a mouth window around the route
    # end: its clearance buffer is subtracted there and the RAW polygon
    # joins the clip instead (overlap still trimmed, touching edge
    # survives — the same treatment service shapes get below).
    _keep_route_end_edge = _os.environ.get(
        "O4_GROUNDSIDE_ROUTE_END_EDGE", "1") == "1"
    _MOUTH_END_ON_PAVEMENT_TOL_M = 1.0
    _MOUTH_WINDOW_RADIUS_M = 15.0
    _DEMOTABLE_ROLES = {ROLE_APRON, ROLE_JUNCTION}
    route_end_points: list = []
    if _keep_route_end_edge:
        for centerline in (getattr(layout, "apt_service_centerlines", None)
                           or []):
            line = getattr(centerline, "line", None)
            if line is None or line.is_empty:
                continue
            try:
                route_end_points.append(Point(*line.coords[0]))
                route_end_points.append(Point(*line.coords[-1]))
            except (ValueError, IndexError):
                continue
    clip_polys = []
    # R7b clause 3's frontage partners: the AIRCRAFT pavement a road can
    # run along.  Their clearance buffers are collected as the clause
    # sees them — mouth windows already subtracted.
    frontage_clips: list = []
    for s in layout.shapes:
        if s.role in AIRSIDE_ROLES and s.polygon is not None \
                and not s.polygon.is_empty:
            try:
                # Mitre join: the buffered boundary is straight-edged
                # (no rounded-corner arc segments), so the clip cut
                # doesn't introduce sub-metre edges that would inflate the
                # per-vertex grade after altitude rounding.
                buffered = s.polygon.buffer(clearance, join_style=2)
                mouth_ends = ([ep for ep in route_end_points
                               if s.polygon.distance(ep)
                               <= _MOUTH_END_ON_PAVEMENT_TOL_M]
                              if s.role in _DEMOTABLE_ROLES else [])
                if mouth_ends:
                    # Square windows (shapely ``box``), not point buffers:
                    # the window edge is part of the clip boundary and
                    # must stay arc-free for the same reason as the mitre
                    # join above.
                    windows = unary_union([
                        box(ep.x - _MOUTH_WINDOW_RADIUS_M,
                            ep.y - _MOUTH_WINDOW_RADIUS_M,
                            ep.x + _MOUTH_WINDOW_RADIUS_M,
                            ep.y + _MOUTH_WINDOW_RADIUS_M)
                        for ep in mouth_ends])
                    buffered = buffered.difference(windows)
                    clip_polys.append(s.polygon)
                clip_polys.append(buffered)
                if s.role in _DEMOTABLE_ROLES and not buffered.is_empty:
                    frontage_clips.append(buffered)
            except _GEOM_EXC:
                continue
    # ── R7b clause 3, over the buffers just built (see
    #    ``_cut_back_road_frontage``).  Runs BEFORE the groundside clip
    #    so a lot clipped below sees the road's FINAL geometry.
    n_road_cut = 0
    if road_frontage_cutback:
        _dem_at_rf = _dem_sampler(layout, dem, tile_lat, tile_lon)
        n_road_cut = _cut_back_road_frontage(
            layout, frontage_clips, _dem_at_rf,
            stats=_law_seat_stats(layout, "cut_back_road_frontage"))
        if n_road_cut:
            import O4_UI_Utils as UI
            UI.vprint(1,
                f"  [pav-builder] R7b: cut {n_road_cut} road face(s) back "
                f"from the apron they front (parallel run > "
                f"{ROAD_FRONTAGE_SPAN_WIDTH_FACTOR}x their own width); "
                f"they DEM-refollow at their own level "
                f"(owner ruling 2026-08-15).")
    if not groundside_clip:
        return n_road_cut
    # Groundside may TOUCH a service road (shared edge, kept above) but must not
    # OVERLAP it (area overlap = self-overlap, not a shared edge — e.g. a curved
    # SVC connector emitted as service_junction that straddles the lot it feeds).
    # Add the service polys at ZERO clearance so an overlap is trimmed while the
    # touching edge survives (no disconnecting gap).
    for s in layout.shapes:
        if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION) \
                and s.polygon is not None and not s.polygon.is_empty:
            clip_polys.append(s.polygon)
    if not clip_polys:
        return 0
    try:
        clip = unary_union(clip_polys)
    except _GEOM_EXC:
        return 0
    if clip is None or clip.is_empty:
        return 0
    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    # THE LAW DATUM this pass grades to — computed ONCE per pass
    # (single-pass principle), read from the SAME authority order
    # the emitter resolves a shared node with.
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _stats = _law_seat_stats(layout, "separate_groundside_from_airside")
    out_shapes = []
    n_clipped = 0
    for s in layout.shapes:
        if s.role != ROLE_GROUNDSIDE_PAVEMENT or s.polygon is None \
                or s.polygon.is_empty:
            out_shapes.append(s)
            continue
        try:
            diff = s.polygon.difference(clip)
        except _GEOM_EXC:
            out_shapes.append(s)
            continue
        if diff.is_empty:
            n_clipped += 1            # entirely inside the gap → drop
            continue
        parts = ([diff] if diff.geom_type == "Polygon"
                 else list(getattr(diff, "geoms", [])))
        # THE PIECE'S OWN PRIOR FIELD — one authority, consumed INSIDE
        # the law seat (cycle-6 ingestion).  What stood here was a
        # post-seat rewrite: every rebuilt vertex took ``DEM + deviation
        # of the NEAREST original vertex``, which (a) overwrote the weld
        # anchors the seat had just pinned, and (b) reduced to the raw
        # DEM wherever the original piece was itself DEM-seeded — the
        # carrier of the emitted ``within_shape groundside_pavement``
        # class.  As a ladder rung it is now the edge-INTERPOLATED value
        # along the original ring (``_prior_field_reader``), ranked
        # BELOW the welds instead of above them.
        _prior = _shape_prior(s) if preserve_field else None
        changed = False
        kept = []
        for part in parts:
            if part.geom_type != "Polygon" or part.is_empty \
                    or part.area < _GROUNDSIDE_MIN_AREA_M2:
                changed = True
                continue
            if part.equals(s.polygon):
                kept.append(s)        # untouched
                continue
            # No re-simplify: the source groundside was already 2 m-
            # simplified at emit, and re-simplifying would move the
            # boundary back across the clearance gap.  The mitre-buffered
            # clip above already yields clean straight edges.
            _seat_out = {}
            built = _dem_follow_polygon(part, _dem_at, simplify_tol=0.0,
                                        law_anchors=_law_anchors,
                                        anchor_key=_anchor_key,
                                        prior=_prior, stats=_stats,
                                        seat_out=_seat_out)
            if built is None:
                continue
            np_, na = built
            _new = BuiltShape(
                polygon=np_, role=ROLE_GROUNDSIDE_PAVEMENT,
                ref="groundside", node_altitudes=na)
            setattr(_new, _LAW_SEATED_ATTR,
                    bool(_seat_out.get("law_seated")))
            kept.append(_new)
            changed = True
        out_shapes.extend(kept)
        if changed:
            n_clipped += 1
    layout.shapes = out_shapes
    return n_clipped


def _clip_shape_yielding_to(ys, kept_polygon, snap_tol: float = 0.25):
    """Clip shape ``ys`` so it yields its overlap with ``kept_polygon``:
    snap-then-difference (the contact chain passes exactly through the
    kept vertices), largest surviving part, kept-vertex projections
    inserted on the new ring (no residual T-junction), and
    ``node_altitudes`` carried from the nearest original vertex.

    ``snap_tol=0`` disables the pre-difference snap: the result then
    only ever SHRINKS ``ys``, so the clip cannot sweep an edge across a
    third shape — the non-converging-rounds fallback in
    ``_deconflict_service_overlaps``.

    Returns the new ``Polygon`` (``ys`` already mutated), or ``None``
    when nothing survives — the yielder lies (essentially) wholly
    inside the kept geometry and the caller should drop it.
    Extracted verbatim from the service↔service loop so the
    senior-pavement stage shares one clip semantics."""
    try:
        base = (snap(ys.polygon, kept_polygon, snap_tol) if snap_tol
                else ys.polygon)
        diff = base.difference(kept_polygon)
    except _GEOM_EXC:
        return ys.polygon
    parts = ([diff] if diff.geom_type == "Polygon"
             else [g for g in getattr(diff, "geoms", ())
                   if g.geom_type == "Polygon"])
    parts = [g for g in parts if g.area >= 1.0]
    if not parts:
        return None
    new_poly = max(parts, key=lambda g: g.area)
    new_ring = list(new_poly.exterior.coords)
    if new_ring and new_ring[0] == new_ring[-1]:
        new_ring = new_ring[:-1]
    kept_ring = list(kept_polygon.exterior.coords)
    inserts = []          # (segment index, u along segment, point)
    for (kx, ky) in kept_ring:
        if any(math.hypot(kx - nx, ky - ny) <= 0.02
               for (nx, ny) in new_ring):
            continue
        best = None
        for t in range(len(new_ring)):
            ax, ay = new_ring[t]
            bx, by = new_ring[(t + 1) % len(new_ring)]
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            if seg2 < 1e-9:
                continue
            u = ((kx - ax) * dx + (ky - ay) * dy) / seg2
            u = min(1.0, max(0.0, u))
            px, py = ax + u * dx, ay + u * dy
            d = math.hypot(kx - px, ky - py)
            if best is None or d < best[0]:
                best = (d, t, u, (px, py))
        if best is not None and best[0] <= 0.25:
            inserts.append(best[1:])
    for (t, u, pt) in sorted(inserts, key=lambda e: (-e[0], -e[1])):
        new_ring.insert(t + 1, pt)
    try:
        new_poly = Polygon(new_ring)
    except _GEOM_EXC:
        pass
    old_ring = list(ys.polygon.exterior.coords)
    old_alts = list(ys.node_altitudes or [])
    ys.polygon = new_poly
    if old_alts and len(old_alts) >= len(old_ring) - 1:
        out_ring = list(new_poly.exterior.coords)
        new_alts = []
        for (nx, ny) in out_ring:
            best_k = min(
                range(min(len(old_ring), len(old_alts))),
                key=lambda t: (old_ring[t][0] - nx) ** 2
                + (old_ring[t][1] - ny) ** 2)
            new_alts.append(old_alts[best_k])
        ys.node_altitudes = new_alts
    return new_poly


def _clip_pavement_against_building_pads(
        layout: "PavementLayout", min_overlap_m2: float = 1e-3) -> int:
    """LAST-WORD building-pad re-clip (owner CYXY building1, 12.3 →
    36.9 m² apron∩building — the standing zero-tolerance-overlap red).

    The slice builds pavement from ``pav_union − terminal_union``, so
    shapes are BORN clear of building pads — but the post-solve
    conformance weld (0.5 m tolerance) can bow a pavement ring back
    ACROSS a pad edge (the exact overlap class the final T-weld's
    tight-tolerance comment predicts), and no later pass owned the
    pavement∩building pair.  Pavement always yields to the pad (the
    slice's own invariant).  Pure difference (``snap_tol=0`` — only
    ever shrinks the yielder, cannot mint overlap elsewhere) with the
    shared clip's altitude carry-over; runs BEFORE the final T-weld so
    the clip's new on-edge vertices get welded.  Returns shapes
    clipped/dropped.
    """
    from shapely.strtree import STRtree
    pads = [s.polygon for s in layout.shapes
            if s.role in (ROLE_BUILDING, "terminal")
            and s.polygon is not None and not s.polygon.is_empty
            and s.polygon.geom_type == "Polygon"]
    if not pads:
        return 0
    clip_roles = (ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_ROAD,
                  ROLE_SERVICE_JUNCTION, ROLE_GROUNDSIDE_PAVEMENT)
    tree = STRtree(pads)
    n_clipped = 0
    drop_ids: set = set()
    for s in layout.shapes:
        if (s.role not in clip_roles or s.polygon is None
                or s.polygon.is_empty
                or s.polygon.geom_type != "Polygon"):
            continue
        try:
            candidates = tree.query(s.polygon)
        except _GEOM_EXC:
            continue
        for qk in candidates:
            pad = pads[int(qk)]
            try:
                overlap = s.polygon.intersection(pad).area
            except _GEOM_EXC:
                continue
            if overlap <= min_overlap_m2:
                continue
            new_poly = _clip_shape_yielding_to(s, pad, snap_tol=0.0)
            if new_poly is None:
                # wholly inside the pad — the building owns the
                # footprint; drop the redundant pavement.
                drop_ids.add(id(s))
                n_clipped += 1
                break
            n_clipped += 1
    if drop_ids:
        layout.shapes = [s for s in layout.shapes
                         if id(s) not in drop_ids]
    return n_clipped


def _deconflict_service_overlaps(
        layout: "PavementLayout", min_overlap_m2: float = 1e-3) -> int:
    """Clip lens-scale service-shape overlaps to CONVERGENCE.

    One round is not always enough: a round's own snap-clips can sweep
    a rebuilt edge across a THIRD shape and mint a fresh lens (SPJC
    severed piece 2026-07-28: the senior-pavement clip re-crossed a
    neighbouring service_junction by 1.27 m²; snap-clip rounds then
    OSCILLATE — each stage's 0.25 m snap re-minting the other's
    overlap — and nothing later owns service↔service).  Repeat until a
    full round clips nothing; if the rounds cap out without
    converging, run one last round with the snap DISABLED — a pure
    difference only ever shrinks the yielder, so it cannot mint
    overlap anywhere and the pass ends overlap-free (the cost is a
    possible T-vertex on the contact, which the final T-weld inserts
    handle).  Returns total shapes clipped."""
    total = 0
    converged = False
    for _ in range(3):
        n = _deconflict_service_overlaps_once(layout, min_overlap_m2)
        total += n
        if not n:
            converged = True
            break
    if not converged:
        total += _deconflict_service_overlaps_once(layout, min_overlap_m2,
                                                   snap_tol=0.0)
    return total


def _deconflict_service_overlaps_once(
        layout: "PavementLayout", min_overlap_m2: float = 1e-3,
        snap_tol: float = 0.25) -> int:
    """Clip lens-scale overlaps between SERVICE shapes (last word, before
    emit).  The canonical vertex weld can cross two near-coincident
    service boundaries whose contact chains carry different vertex
    sequences (CYXY: a corridor-converted road hugging the strip-carved
    junction it was trimmed against — 0.38 m² lens after welding), and no
    earlier pass owns service↔service overlap.  Larger piece is
    canonical; the smaller piece yields the overlap.  Altitudes for the
    rebuilt ring carry over from the nearest original vertex (the
    surfaces are welded along the contact, so the values agree there).
    Returns the number of shapes clipped."""
    svc = [(i, s) for i, s in enumerate(layout.shapes)
           if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
           and s.polygon is not None and not s.polygon.is_empty
           and s.polygon.geom_type == "Polygon"]
    if len(svc) < 2:
        return 0
    from shapely.strtree import STRtree
    polys = [s.polygon for _i, s in svc]
    tree = STRtree(polys)
    n_clipped = 0
    drop_ids: set = set()   # yielders wholly inside a kept shape → removed
    for a in range(len(svc)):
        ia, sa = svc[a]
        if id(sa) in drop_ids:
            continue
        try:
            cand = tree.query(sa.polygon)
        except _GEOM_EXC:
            continue
        for qb in cand:
            b = int(qb)
            if b <= a:
                continue
            ib, sb = svc[b]
            if id(sb) in drop_ids:
                continue
            try:
                overlap = sa.polygon.intersection(sb.polygon).area
            except _GEOM_EXC:
                continue
            if overlap <= min_overlap_m2:
                continue
            # smaller yields
            yi, ys = (ia, sa) if sa.polygon.area < sb.polygon.area \
                else (ib, sb)
            ki, ks = (ib, sb) if ys is sa else (ia, sa)
            new_poly = _clip_shape_yielding_to(ys, ks.polygon,
                                               snap_tol=snap_tol)
            if new_poly is None:
                # Nothing survives the difference → the yielder lies
                # (essentially) WHOLLY inside the kept shape.  A plain
                # ``continue`` here left the fully-covered yielder in place
                # (KEQY: service_junction #23, 109 m², entirely inside #21) —
                # a 100 %-area self-overlap.  Drop the redundant yielder: the
                # kept shape already covers its footprint at the same role, so
                # removing it loses no coverage and kills the overlap.
                drop_ids.add(id(ys))
                n_clipped += 1
                continue
            # (Snap-difference, largest part, kept-vertex conformance
            # inserts and altitude carry-over all happen inside
            # ``_clip_shape_yielding_to`` — one clip semantics shared
            # with the senior-pavement stage below.)
            # keep the STRtree list coherent for later pairs
            polys[a if ys is sa else b] = new_poly
            n_clipped += 1

    # SENIOR-PAVEMENT SENIORITY (2026-07-17, SPJC apron #89 ∩
    # service_junction #96, 9.4 m²): a service shape overlapping APRON
    # or JUNCTION pavement YIELDS its overlap — the apron-edge-service
    # ruling grades service portions inside an apron as apron anyway,
    # and no earlier pass owns the cross-role pair (the fixed-shape
    # overlap ladder has no service tier; the groundside separation
    # cuts only groundside).  Same clip semantics as service↔service.
    from .layout import ROLE_APRON as _R_AP, ROLE_JUNCTION as _R_JN
    senior_polys = [s.polygon for s in layout.shapes
                    if s.role in (_R_AP, _R_JN)
                    and s.polygon is not None and not s.polygon.is_empty
                    and s.polygon.geom_type == "Polygon"]
    if senior_polys:
        senior_tree = STRtree(senior_polys)
        for s in layout.shapes:
            if (s.role not in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
                    or id(s) in drop_ids or s.polygon is None
                    or s.polygon.is_empty
                    or s.polygon.geom_type != "Polygon"):
                continue
            try:
                candidates = senior_tree.query(s.polygon)
            except _GEOM_EXC:
                continue
            for qk in candidates:
                kept_polygon = senior_polys[int(qk)]
                try:
                    overlap = s.polygon.intersection(kept_polygon).area
                except _GEOM_EXC:
                    continue
                if overlap <= min_overlap_m2:
                    continue
                new_poly = _clip_shape_yielding_to(s, kept_polygon,
                                                   snap_tol=snap_tol)
                if new_poly is None:
                    drop_ids.add(id(s))
                    n_clipped += 1
                    break
                n_clipped += 1

    if drop_ids:
        layout.shapes = [s for s in layout.shapes if id(s) not in drop_ids]
    return n_clipped


def _deconflict_groundside_overlaps(
        layout: "PavementLayout", dem, tile_lat: int, tile_lon: int,
        min_overlap_m2: float = 0.5) -> int:
    """Clip overlapping groundside-vs-groundside pavement so no two
    groundside polygons share interior area.

    ``_separate_groundside_from_airside`` removes groundside↔airside
    overlap but never groundside↔groundside — an orphan junction
    reclassified to groundside, or two independently DEM-followed
    pieces, can overlap each other (LMML: piece #238 covered #185 by
    32.7 m² and #182 by 3.0 m²).  Larger pieces are canonical; each
    smaller piece YIELDS the overlap (subtract the running union of the
    already-kept larger pieces), is rebuilt with DEM altitudes, and
    sub-minimum remnants are dropped.  Pieces that merely ABUT a larger
    one are untouched (difference of a touching polygon is a no-op).

    Returns the number of groundside shapes modified or dropped."""
    gs = [(i, s) for i, s in enumerate(layout.shapes)
          if s.role == ROLE_GROUNDSIDE_PAVEMENT
          and s.polygon is not None and not s.polygon.is_empty]
    if len(gs) < 2:
        return 0
    # Largest-first, deterministic index tie-break.
    order = sorted(gs, key=lambda t: (-t[1].polygon.area, t[0]))
    _dem_at = _dem_sampler(layout, dem, tile_lat, tile_lon)
    # THE LAW DATUM this pass grades to — computed ONCE per pass
    # (single-pass principle), read from the SAME authority order
    # the emitter resolves a shared node with.
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _stats = _law_seat_stats(layout, "deconflict_groundside_overlaps")
    kept_union = None
    replace: Dict[int, list] = {}   # original idx → [BuiltShape, …] ([] = drop)
    n_mod = 0
    for i, s in order:
        poly = s.polygon
        if kept_union is not None and not kept_union.is_empty:
            try:
                overlap = poly.intersection(kept_union).area
            except _GEOM_EXC:
                overlap = 0.0
            if overlap > min_overlap_m2:
                try:
                    diff = poly.difference(kept_union)
                except _GEOM_EXC:
                    diff = None
                parts = ([] if diff is None or diff.is_empty
                         else [diff] if diff.geom_type == "Polygon"
                         else list(getattr(diff, "geoms", [])))
                new_pieces = []
                for part in parts:
                    if (part.geom_type != "Polygon" or part.is_empty
                            or part.area < _GROUNDSIDE_MIN_AREA_M2):
                        continue
                    _seat_out = {}
                    built = _dem_follow_polygon(
                        part, _dem_at, simplify_tol=0.0,
                        law_anchors=_law_anchors, anchor_key=_anchor_key,
                        # The YIELDING shape still carries its own field:
                        # subtracting an overlap is geometry, not a
                        # re-grading event.
                        prior=_shape_prior(s), stats=_stats,
                        seat_out=_seat_out)
                    if built is None:
                        continue
                    np_, na = built
                    _new = BuiltShape(
                        polygon=np_, role=ROLE_GROUNDSIDE_PAVEMENT,
                        ref="groundside", node_altitudes=na)
                    setattr(_new, _LAW_SEATED_ATTR,
                            bool(_seat_out.get("law_seated")))
                    new_pieces.append(_new)
                replace[i] = new_pieces
                n_mod += 1
                try:
                    poly = (unary_union([p.polygon for p in new_pieces])
                            if new_pieces else None)
                except _GEOM_EXC:
                    poly = None
        if poly is not None and not poly.is_empty:
            try:
                kept_union = (poly if kept_union is None
                              else unary_union([kept_union, poly]))
            except _GEOM_EXC:
                pass
    if not replace:
        return 0
    out = []
    for i, s in enumerate(layout.shapes):
        if i in replace:
            out.extend(replace[i])
        else:
            out.append(s)
    layout.shapes = out
    return n_mod




def service_end_cap_lines(lines, pav_union, *, max_half_width_m=40.0,
                          edge_tol_m=1.0):
    """Perpendicular CUT chords at service-line ends that die
    mid-pavement.

    Owner report 2026-07-28 (CYXY 60.7131204,-135.0753622): a free-road
    interval end cut the pavement only up to the SPINE — the far half of
    the road stayed fused to the neighbouring shape ("one half of a road
    or taxiway correct, the other half lumped in with a larger shape").
    A cap chord across the full local cross-section makes the slice
    sever both halves at the same station.  Returns bare cut GEOMETRY —
    the caller must keep cap ids out of face classification.

    ``max_half_width_m`` must exceed any real corridor cross-section:
    a cap that stops SHORT of the pavement boundary leaves the face
    unpartitioned and the polygonizer silently ignores the cut (CYXY
    shape 64/69, caps 1.4-2.3 m short at 15 m — the owner's round-4
    "widen-cut" chords never fired).  The contiguous-piece filter below
    keeps a long chord local, so a generous reach is safe.
    """
    import math as _math
    from shapely.geometry import LineString as _LS, Point as _P
    caps = []
    if pav_union is None or pav_union.is_empty:
        return caps
    boundary = pav_union.boundary
    for line in lines:
        try:
            coords = list(line.coords)
        except _GEOM_EXC:
            continue
        if len(coords) < 2:
            continue
        for end, prev in ((coords[0], coords[1]),
                          (coords[-1], coords[-2])):
            dx, dy = end[0] - prev[0], end[1] - prev[1]
            run = _math.hypot(dx, dy)
            if run < 1e-6:
                continue
            point = _P(end)
            try:
                if not pav_union.contains(point):
                    continue
                if boundary.distance(point) < edge_tol_m:
                    continue      # dies at the pavement edge: no cap
                px, py = -dy / run, dx / run
                chord = _LS([
                    (end[0] - px * max_half_width_m,
                     end[1] - py * max_half_width_m),
                    (end[0] + px * max_half_width_m,
                     end[1] + py * max_half_width_m)])
                cut = chord.intersection(pav_union)
            except _GEOM_EXC:
                continue
            best = None
            for piece in getattr(cut, "geoms", [cut]):
                if piece.geom_type != "LineString":
                    continue
                if piece.distance(point) > 0.5:
                    continue      # a disjoint sliver across a gap
                if best is None or piece.length > best.length:
                    best = piece
            if best is not None and best.length >= 2.0:
                caps.append(best)
    return caps
