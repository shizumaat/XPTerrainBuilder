"""Pavement classification v1 — airside apron vs landside pavement.

WHY THIS EXISTS.  ``apron`` is the FALLBACK bucket of the geometry phase
(``pavement/global_slice.classify_faces``: "everything else — no
centerlines, or open stand/terminal pavement beyond route reach").  That
is sound when the pavement SOURCE is an aerodrome's own apt.dat, but a
third-party pack that draws landside pavement — perimeter roads, car
parks, terminal frontage — as ordinary ``.pol`` pavement drops the whole
lot into the airside 1.5 % apron law, which then FLATTENS the real
terrain relief under it.  Measured at HECA (2026-07-26, Tai pack, 99 %
DSF-sourced): 251 of 318 apron shapes / 904,433 m² — 32.1 % of the apron
area — are landside, mean |offset vs DEM| 5.35 m, worst +21 m.

WHAT IT DOES.  Between the geometry-final apron reclassification
(``junction_repair._reclassify_apron_junctions``) and the runway
touch-chain classifier
(``junction_repair._reclassify_runway_disconnected_to_groundside``), it
votes on POSITIVE EVIDENCE for every apron-role shape:

* OSM ``aeroway`` backing (apron polygons, ``parking_position`` stands,
  taxiway/taxilane centerline territory) — the AIRSIDE evidence;
* road-corridor overlap from the airport-region ROAD FEED
  (``layout.airport_road_network``, buffered by the shared
  ``clearance.road_corridors_from_ways`` law) — the LANDSIDE evidence;
* the aircraft-opening morphology of
  ``object_footprints.is_vehicle_pavement_patch`` — can an aircraft fit
  anywhere on this shape at all;
* distance to the nearest taxi centerline / to the runway union.

The evidence is bimodal at HECA: every big misclassification has 0.0 %
aeroway backing and 45-95 % road overlap; every genuine apron has 26-89 %
aeroway backing and ≤27 % road.  See ``config.PAVEMENT_CLASS_V1`` for the
rule set (R1-R5) and every threshold.

THE TWO OWNER RULINGS (2026-07-26) THIS MODULE IMPLEMENTS.

R-VETO — positive OSM airside evidence keeps a shape apron, ABSOLUTELY:
"a road inside, or sharing an edge with a real apron must follow the
apron's grade".  A service road along or through an apron absorbs into
apron grading; it is never split out and never demoted.

R-SPLIT — "an airport author might … make a single piece of asphalt that
covers both a large apron, and 5km of thin roadway.  We have to be able
to identify where the road leaves the apron … so we can clearly separate
roads from aprons. … roads with empty terrain on both sides need to be
free to grade as roads and not be classified as aprons."  So a shape
carrying BOTH real apron evidence and long road-backed tails is cut at
the MOUTH where the thin corridor leaves the wide body — reusing the
existing mouth machinery, ``pavement/apron_necks`` (``neck_cuts`` /
``_cut_at_mouth``: a mouth is two near boundary vertices whose excursion
erodes to nothing, i.e. a thin arm).  The BODY keeps apron; each TAIL is
judged on its own and only leaves when it is road-backed AND has empty
terrain on both flanks.

The two rulings meet at the flank test: a road THROUGH an apron has
pavement on both sides, fails the flank test, and stays with the body
(R-VETO); a road that has LEFT the apron has open terrain on both sides
and is free to grade as a road (R-SPLIT).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

import O4_UI_Utils as UI
from .config import (
    DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M,
    DSF_OBJECT_PAVEMENT_OPENING_RATIO,
    PAVEMENT_CLASS_AEROWAY_LINE_BUFFER_M,
    PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC,
    PAVEMENT_CLASS_AIRSIDE_NONE_FRAC,
    PAVEMENT_CLASS_AIRSIDE_WEAK_FRAC,
    PAVEMENT_CLASS_FLANK_CLEAR_M,
    PAVEMENT_CLASS_MIN_AREA_M2,
    PAVEMENT_CLASS_MOUTH_SPLIT,
    PAVEMENT_CLASS_PARKING_FRAC,
    PAVEMENT_CLASS_ROAD_DOMINANT_FRAC,
    PAVEMENT_CLASS_ROAD_PARTIAL_FRAC,
    PAVEMENT_CLASS_RUNWAY_STANDOFF_M,
    PAVEMENT_CLASS_SPLIT_MAX_RING_VERTICES,
    PAVEMENT_CLASS_SPLIT_MIN_BODY_AREA_M2,
    PAVEMENT_CLASS_SPLIT_MIN_TAIL_AREA_M2,
    PAVEMENT_CLASS_STAND_BUFFER_M,
    PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC,
    PAVEMENT_CLASS_TAIL_MAX_FLANK_CONTACT,
    PAVEMENT_CLASS_TAIL_MAX_WIDTH_M,
    PAVEMENT_CLASS_TAIL_MIN_LENGTH_M,
    PAVEMENT_CLASS_TAIL_ROAD_FRAC,
    PAVEMENT_CLASS_TAXI_BUFFER_M,
    PAVEMENT_CLASS_V1,
)
from .layout import (
    ROLE_APRON,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_SERVICE_ROAD,
    BuiltShape,
)

__all__ = [
    "classify_pavement_v1",
    "PavementEvidence",
    "shape_evidence",
    "whole_shape_verdict",
    "split_body_and_tails",
    "evidence_sources",
]

_GEOM_EXC = (ValueError, ZeroDivisionError, AttributeError, TypeError,
             IndexError)

# Sentinel for "not built yet" where ``None`` is a legitimate value.
_UNSET = object()

# OSM ``aeroway`` values that are POSITIVE evidence of aircraft
# territory.  Deliberately a whitelist: ``aeroway=terminal`` /
# ``hangar`` / ``fuel`` are buildings, not movement surface, and would
# vote to keep the car park in front of the terminal.
_AIRSIDE_AEROWAY = frozenset({
    "apron", "taxiway", "taxilane", "runway", "parking_position",
    "stand", "gate", "holding_position", "jet_bridge", "helipad",
})
# The subset whose CENTERLINES carry taxi territory.
_TAXI_AEROWAY = frozenset({"taxiway", "taxilane"})
# The subset that marks an aircraft STAND.
_STAND_AEROWAY = frozenset({"parking_position", "stand", "gate"})
# Road-feed ``service=`` values that mark parking-lot circulation.
_PARKING_SERVICE = frozenset({"parking_aisle", "parking"})


# ═════════════════════════════════════════════════════════════════════
# Evidence sources — computed ONCE per layout, memoized on it
# ═════════════════════════════════════════════════════════════════════

class CoverIndex:
    """Area-coverage measurement against a scattered evidence layer.

    Every signal in this module is "what fraction of this shape is
    covered by layer X".  The layer is kept as its INDIVIDUAL PIECES —
    one per source way, overlaps and all — in an ``STRtree``; a shape
    unions only the pieces it genuinely intersects and measures against
    that.  Overlap between pieces is handled by that per-query union,
    so the layer is never pre-merged.

    BUILD-TIME DISCIPLINE (the HARD LAW).  This is not a micro-
    optimisation, it is the reason the feature fits its budget.  The
    obvious implementation — ``unary_union`` the whole layer once, then
    one ``polygon.intersection`` per shape against it — costs, for
    HECA's 4,648-way road-corridor layer over 318 apron shapes:

        build 0.674 s + query 0.519 s = 1.193 s

    against a 0.60 s ceiling for the entire feature.  The airport's
    roads union into ONE connected blob, so an ``STRtree`` over the
    merged layer does not help: every shape still intersects the whole
    thing.  Keeping the pieces separate and prefiltering the query with
    the tree's ``intersects`` predicate (which uses prepared geometry,
    so the 16-piece mean hit set never grows to the 288-piece bbox hit
    set) gives the identical fractions — verified to 5e-14 — for

        build 0.098 s + query 0.082 s = 0.180 s

    Measured 2026-07-26 on the HECA layout; ``scratchpad/pc_bench2.py``.
    """

    __slots__ = ("parts", "tree")

    def __init__(self, parts):
        from shapely.strtree import STRtree
        self.parts = [p for p in parts
                      if p is not None and not p.is_empty and p.area > 0.0]
        try:
            self.tree = STRtree(self.parts) if self.parts else None
        except _GEOM_EXC:
            self.tree = None

    def __bool__(self) -> bool:
        return bool(self.parts)

    def geometry(self):
        """The whole layer as one geometry (diagnostics / tests only)."""
        return _union(self.parts)

    def intersects(self, geometry) -> bool:
        """True when ``geometry`` touches ANY piece of this layer.

        The MEMBERSHIP question the area fractions cannot answer for a
        LINE: a cross-section chord has no area, so ``cover_fraction``
        reads 0.0 against every layer.  Same tree, same pieces, same
        prepared ``intersects`` predicate the fractions prefilter with —
        one index, two questions, no second layer to drift.
        """
        if self.tree is None or geometry is None:
            return False
        try:
            if geometry.is_empty:
                return False
            return len(self.tree.query(geometry,
                                       predicate="intersects")) > 0
        except _GEOM_EXC:
            return False

    def cover_fraction(self, polygon) -> float:
        """Fraction of ``polygon``'s area covered by this layer."""
        if self.tree is None:
            return 0.0
        try:
            area = polygon.area
            if area <= 0.0:
                return 0.0
            hits = [self.parts[int(i)]
                    for i in self.tree.query(polygon, predicate="intersects")]
            if not hits:
                return 0.0
            layer = hits[0] if len(hits) == 1 else unary_union(hits)
            return min(1.0, polygon.intersection(layer).area / area)
        except _GEOM_EXC:
            return 0.0

    def cover_fractions(self, polygons) -> list:
        """``cover_fraction`` over many polygons via ONE bulk tree query.

        Identical per-polygon math (single-hit shortcut, per-query
        union; equivalence discipline as above).  The bulk ``query``
        removes the per-call round trip, and zero-hit polygons — the
        common case against a sparse layer — cost nothing at all.
        """
        fractions = [0.0] * len(polygons)
        if self.tree is None or not polygons:
            return fractions
        try:
            import numpy as np
            arr = np.array(polygons, dtype=object)
            pairs = self.tree.query(arr, predicate="intersects")
            # A polygon lying fully inside ONE part is covered outright
            # (ratio 1.0 to within an ulp of the overlay's answer) —
            # the prepared predicate is far cheaper than the overlay.
            inside = {int(qi) for qi in
                      self.tree.query(arr, predicate="within")[0]}
        except _GEOM_EXC:
            return [self.cover_fraction(p) for p in polygons]
        hits_by: dict = {}
        for qi, gi in zip(pairs[0], pairs[1]):
            hits_by.setdefault(int(qi), []).append(self.parts[int(gi)])
        import shapely
        for qi, hits in hits_by.items():
            polygon = polygons[qi]
            try:
                area = polygon.area
                if area <= 0.0:
                    continue
                if qi in inside:
                    fractions[qi] = 1.0
                    continue
                if len(hits) == 1:
                    covered = polygon.intersection(hits[0]).area
                else:
                    # Clip each hit to the polygon FIRST, then union the
                    # small clipped pieces — same covered area as
                    # intersecting against the union of the full parts,
                    # without ever merging full-size layer geometry
                    # (equivalence discipline as above).
                    covered = shapely.union_all(shapely.intersection(
                        polygon, np.array(hits, dtype=object))).area
                fractions[qi] = min(1.0, covered / area)
            except _GEOM_EXC:
                fractions[qi] = 0.0
        return fractions


def _cover_index(pieces) -> CoverIndex:
    """A :class:`CoverIndex` over ``pieces`` (see there: NOT pre-merged)."""
    return CoverIndex(pieces)


@dataclass
class EvidenceSources:
    """The layers every per-shape signal is measured against.

    Built once per airport (``evidence_sources``), cached on the layout
    as ``_pavement_class_sources``.  An EMPTY layer means "no such
    evidence exists here" — every fraction against it reads 0.0, which
    is the correct answer, not a failure.
    """
    road_corridors: CoverIndex = field(
        default_factory=lambda: CoverIndex([]))
    road_lines: object | None = None          # feed centerlines (union)
    # BELOW-GRADE road corridors (``tunnel`` tagged / ``layer`` < 0) —
    # G-TUNNEL-ROAD evidence only (owner 2026-08-10), never surface-road
    # coverage.  Empty when the feed maps no bore.
    tunnel_corridors: CoverIndex = field(
        default_factory=lambda: CoverIndex([]))
    parking_corridors: CoverIndex = field(
        default_factory=lambda: CoverIndex([]))
    osm_apron: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    osm_stand: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    osm_taxi: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    osm_airside: CoverIndex = field(default_factory=lambda: CoverIndex([]))
    taxi_centerlines: object | None = None    # layout's own taxi network
    runway_union: object | None = None
    n_osm_ways: int = 0
    n_road_ways: int = 0


def _polygonal(geometry):
    """``geometry`` reduced to a valid polygonal union, or ``None``."""
    if geometry is None:
        return None
    try:
        if geometry.is_empty:
            return None
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        return None if geometry.is_empty else geometry
    except _GEOM_EXC:
        return None


def _union(pieces):
    pieces = [p for p in pieces if p is not None and not p.is_empty]
    if not pieces:
        return None
    try:
        return _polygonal(unary_union(pieces))
    except _GEOM_EXC:
        return None


def _osm_airside_unions(layout):
    """Airside-aeroway evidence unions from the airports OSM layer.

    The layer is already loaded by the pipeline (an Overpass
    ``way["aeroway"]`` query, cached per 1°×1° tile) and stashed on the
    layout as ``_osm_airport_features`` — this re-reads nothing.
    Returns ``(apron, stand, taxi, airside, n_ways)``.
    """
    features = getattr(layout, "_osm_airport_features", None)
    if not features:
        empty = CoverIndex([])
        return (empty, empty, empty, empty, 0)
    nodes, ways = features[0], features[1]
    if not nodes or not ways:
        empty = CoverIndex([])
        return (empty, empty, empty, empty, 0)
    ll_to_m = layout.ll_to_m
    apron_polys, stand_geoms, taxi_geoms, airside_geoms = [], [], [], []
    n_ways = 0
    for _way_id, node_refs, tags in ways:
        aeroway = tags.get("aeroway", "")
        if aeroway not in _AIRSIDE_AEROWAY:
            continue
        points = []
        for node_ref in node_refs:
            ll = nodes.get(node_ref)
            if ll is not None:
                points.append(ll_to_m(ll[0], ll[1]))
        if len(points) < 2:
            continue
        n_ways += 1
        closed = (len(points) >= 4
                  and abs(points[0][0] - points[-1][0]) < 0.5
                  and abs(points[0][1] - points[-1][1]) < 0.5)
        geometry = None
        if closed:
            try:
                geometry = _polygonal(Polygon(points))
            except _GEOM_EXC:
                geometry = None
        if geometry is None:
            try:
                geometry = LineString(points)
            except _GEOM_EXC:
                continue
            if geometry.length < 1.0:
                continue
        is_line = geometry.geom_type in ("LineString", "LinearRing")
        if aeroway == "apron" and not is_line:
            apron_polys.append(geometry)
        if aeroway in _STAND_AEROWAY:
            stand_geoms.append(geometry.buffer(PAVEMENT_CLASS_STAND_BUFFER_M))
        if aeroway in _TAXI_AEROWAY and is_line:
            taxi_geoms.append(geometry.buffer(PAVEMENT_CLASS_TAXI_BUFFER_M))
        airside_geoms.append(
            geometry.buffer(PAVEMENT_CLASS_AEROWAY_LINE_BUFFER_M)
            if is_line else geometry)
    return (_cover_index(apron_polys), _cover_index(stand_geoms),
            _cover_index(taxi_geoms), _cover_index(airside_geoms), n_ways)


def airside_evidence_layer(layout, taxi_lines=None) -> CoverIndex:
    """THE POSITIVE-AIRSIDE-EVIDENCE LAYER (owner ruling 2026-08-15,
    "roads carry spines … the free-road width test gains its missing
    landside term").

    R7a.  The free-road knife (``groundside.free_road_subsegments``)
    asks one question per station: is this wide pavement an APRON the
    road is inside of, or a LANDSIDE lot the road merely crosses?  The
    width test alone cannot tell them apart — a DSF ``.pol`` pack
    delivers apron and car park as one blob — and the measured cost was
    CYXY lot 377 swallowing a public road whole (82-93 % of its
    stations dropped; HECA 142 of 160 groundside shapes contain roads).

    A station is airside ONLY on evidence no landside pavement can
    supply:

    * **OSM ``aeroway`` backing** — the same whitelist, buffers and
      geometry ``_osm_airside_unions`` builds for the classifier
      (apron polygons, stand buffers, taxiway/taxilane territory);
    * **the airport's OWN name for it** — apt.dat row-110 pavement
      named apron or taxiway (``pavement_scoring.score_sources``);
    * **the runway union** and **the taxi centerline network** —
      airside by identity, never gated by anything here.

    The two classes the width test was BUILT for are preserved by
    construction, because both are airside on this evidence: the SPJC
    east-terminal frontage (apt.dat-named apron + OSM apron) and the
    HECA "svc junctions 4→76" carve (OSM apron backing).  What changes
    is only the pavement with NO airside evidence at all.

    ``taxi_lines`` — the effective taxi centerline set at the call site
    (the slice's own ``_cn_cls``); ``None`` falls back to
    ``layout.apt_taxi_centerlines``.  Memoized on the layout as
    ``_airside_evidence_layer``.
    """
    cached = getattr(layout, "_airside_evidence_layer", None)
    if cached is not None:
        return cached
    parts: list = []
    # (1) OSM aeroway backing — THE classifier's own layer, re-read here
    #     (the unions are memo-free but cheap; the ways are already in
    #     memory as ``_osm_airport_features``).
    apron_u, stand_u, taxi_u, airside_u, _n = _osm_airside_unions(layout)
    parts.extend(airside_u.parts)
    # (2) the airport's own apt.dat naming.
    try:
        from .pavement_scoring import score_sources
        ss = score_sources(layout)
        parts.extend(ss.name_apron.parts)
        parts.extend(ss.name_taxi.parts)
    except Exception:
        pass
    # (3) airside by identity — runways and the taxi centerline network.
    runway_u = getattr(layout, "runway_union", None)
    if runway_u is not None and not runway_u.is_empty:
        parts.append(runway_u)
    if taxi_lines is None:
        taxi_lines = [
            getattr(cl, "chained_line", None) or getattr(cl, "line", None)
            for cl in (getattr(layout, "apt_taxi_centerlines", None) or [])]
    for line in taxi_lines or []:
        if line is None or getattr(line, "is_empty", True):
            continue
        try:
            parts.append(line.buffer(PAVEMENT_CLASS_TAXI_BUFFER_M))
        except _GEOM_EXC:
            continue
    layer = CoverIndex(parts)
    layout._airside_evidence_layer = layer
    return layer


def _is_below_grade(tags) -> bool:
    """True when ``tags`` place the way BELOW grade — ``tunnel`` tagged
    (anything but the explicit no), or ``layer`` < 0.

    The R3.3 owner ruling's evidence test (2026-08-10, "tunneled roads
    are not surface roads"): the ``tunnel`` half is the standing corridor
    law's own test (``clearance.road_corridors_from_ways``); ``layer``
    < 0 joins it, because a way sunk under our pavement is no more a
    surface road for carrying no tunnel tag.
    """
    if tags.get("tunnel", "no") not in ("", "no"):
        return True
    layer = tags.get("layer")
    if layer is None:
        return False
    try:
        return float(str(layer).split(";")[0]) < 0.0
    except (TypeError, ValueError):
        return False


def _road_corridor_index(layout):
    """``(surface road corridors, BELOW-GRADE road corridors)`` for the
    airport-region ROAD FEED, both as :class:`CoverIndex` layers.

    THE LAW IS THE SHARED ONE.  Every corridor comes from
    ``clearance.road_corridors_from_ways`` — the same function
    ``clearance.airport_road_feed_corridors`` calls, over the same
    published ``layout.airport_road_network`` (ways + already-resolved
    carriageway widths), so a corridor measured here is byte-for-byte
    the buffer the clearance consumer would see.  Tunnels are dropped
    and railways get the rail corridor by that shared law, not by a
    second copy of it here.

    The BELOW-GRADE layer is the same law applied to the ways that law
    drops (``_is_below_grade``): the tags are stripped before the call
    so the shared buffer rule — not a second copy of it — produces the
    corridor.  It is evidence for ONE thing: G-TUNNEL-ROAD (owner
    2026-08-10), which takes SERVICE off the table for pavement painted
    over a bore.  It is never surface-road coverage.

    WHAT DIFFERS from ``airport_road_feed_corridors`` is ONLY the
    batching — it is called per way instead of once for all of them, so
    the layer arrives as pieces the :class:`CoverIndex` can prefilter
    instead of as one airport-wide blob.  That is a BUILD-BUDGET
    deviation, measured: the single-union form costs 1.193 s at HECA
    against a 0.60 s ceiling for the whole feature, this form 0.180 s,
    and the two produce identical coverage fractions to 5e-14.  See
    :class:`CoverIndex`.
    """
    network = getattr(layout, "airport_road_network", None)
    if network is None or not getattr(network, "ways", None):
        return CoverIndex([]), CoverIndex([])
    from .clearance import road_corridors_from_ways
    ll_to_m = layout.ll_to_m
    widths = getattr(network, "widths", None)
    nodes = network.nodes
    parts, below = [], []
    for way in network.ways:
        sink = parts
        if _is_below_grade(way[2]):
            sink = below
            _surface_tags = {k: v for k, v in way[2].items()
                             if k not in ("tunnel", "layer")}
            way = (way[0], way[1], _surface_tags)
        try:
            corridor = road_corridors_from_ways(nodes, [way], ll_to_m,
                                                widths=widths)
        except _GEOM_EXC:
            continue
        if corridor is None or corridor.is_empty:
            continue
        sink.extend(getattr(corridor, "geoms", [corridor]))
    return CoverIndex(parts), CoverIndex(below)


def _road_feed_lines(layout):
    """``(centerline union, parking-aisle corridor layer, n road ways)``
    from the airport-region road feed.

    What the corridor API does not expose is the raw CENTERLINES —
    needed to decide whether a demoted tail TRACKS a road
    (``service_road``, axial grading) or merely sits on one
    (``groundside_pavement``, DEM following) — and the parking-aisle
    subset.  Both are read off the same published
    ``layout.airport_road_network``; nothing is re-parsed.
    """
    network = getattr(layout, "airport_road_network", None)
    if network is None or not getattr(network, "ways", None):
        return (None, CoverIndex([]), 0)
    ll_to_m = layout.ll_to_m
    nodes = network.nodes
    widths = getattr(network, "widths", None) or {}
    lines, parking = [], []
    n_road_ways = 0
    for way_id, node_refs, tags in network.ways:
        if tags.get("highway") is None:
            continue                       # railways are not centerlines
        if _is_below_grade(tags):
            continue                       # matches the corridor law
        points = []
        for node_ref in node_refs:
            ll = nodes.get(node_ref)
            if ll is not None:
                points.append(ll_to_m(ll[0], ll[1]))
        if len(points) < 2:
            continue
        try:
            line = LineString(points)
        except _GEOM_EXC:
            continue
        if line.length < 1.0:
            continue
        n_road_ways += 1
        lines.append(line)
        if tags.get("service", "") in _PARKING_SERVICE:
            half_width = 0.5 * float(widths.get(way_id, 6.0))
            try:
                parking.append(line.buffer(
                    max(half_width, 0.5 * PAVEMENT_CLASS_TAIL_MAX_WIDTH_M)))
            except _GEOM_EXC:
                pass
    line_union = None
    if lines:
        try:
            line_union = unary_union(lines)
        except _GEOM_EXC:
            line_union = None
    return (line_union, _cover_index(parking), n_road_ways)


def evidence_sources(layout) -> EvidenceSources:
    """The layout's :class:`EvidenceSources`, built once and memoized."""
    cached = getattr(layout, "_pavement_class_sources", None)
    if cached is not None:
        return cached
    from .junction_repair import _aeroway_centerlines_union
    corridors, tunnel_corridors = _road_corridor_index(layout)
    road_lines, parking, n_road_ways = _road_feed_lines(layout)
    apron_u, stand_u, taxi_u, airside_u, n_osm = _osm_airside_unions(layout)
    try:
        centerlines = _aeroway_centerlines_union(layout)
    except _GEOM_EXC:
        centerlines = None
    sources = EvidenceSources(
        road_corridors=corridors,
        road_lines=road_lines,
        tunnel_corridors=tunnel_corridors,
        parking_corridors=parking,
        osm_apron=apron_u,
        osm_stand=stand_u,
        osm_taxi=taxi_u,
        osm_airside=airside_u,
        taxi_centerlines=centerlines,
        runway_union=getattr(layout, "runway_union", None),
        n_osm_ways=n_osm,
        n_road_ways=n_road_ways,
    )
    layout._pavement_class_sources = sources
    return sources


# ═════════════════════════════════════════════════════════════════════
# Per-shape evidence
# ═════════════════════════════════════════════════════════════════════

@dataclass
class PavementEvidence:
    """The vote inputs for ONE polygon.  Fractions are of its own area."""
    area: float = 0.0
    road: float = 0.0
    osm_apron: float = 0.0
    stand: float = 0.0
    taxi: float = 0.0
    parking: float = 0.0
    opening_vehicle: bool = False   # is_vehicle_pavement_patch verdict
    d_taxi_cl: float = -1.0
    d_runway: float = -1.0

    @property
    def airside(self) -> float:
        """R1's airside evidence: the STRONGEST of the three backings."""
        return max(self.osm_apron, self.stand, self.taxi)


def shape_evidence(polygon, sources: EvidenceSources) -> PavementEvidence:
    """Evidence for one polygon against the airport's shared layers."""
    evidence = PavementEvidence(area=float(getattr(polygon, "area", 0.0)))
    evidence.road = sources.road_corridors.cover_fraction(polygon)
    evidence.osm_apron = sources.osm_apron.cover_fraction(polygon)
    evidence.stand = sources.osm_stand.cover_fraction(polygon)
    evidence.taxi = sources.osm_taxi.cover_fraction(polygon)
    evidence.parking = sources.parking_corridors.cover_fraction(polygon)
    try:
        from .object_footprints import is_vehicle_pavement_patch
        evidence.opening_vehicle = bool(is_vehicle_pavement_patch(
            polygon,
            DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M,
            DSF_OBJECT_PAVEMENT_OPENING_RATIO))
    except _GEOM_EXC:
        evidence.opening_vehicle = False
    for name, source in (("d_taxi_cl", sources.taxi_centerlines),
                         ("d_runway", sources.runway_union)):
        if source is None:
            continue
        try:
            setattr(evidence, name, float(source.distance(polygon)))
        except _GEOM_EXC:
            pass
    return evidence


# ═════════════════════════════════════════════════════════════════════
# The vote (R1-R5)
# ═════════════════════════════════════════════════════════════════════

def whole_shape_verdict(evidence: PavementEvidence) -> tuple[str, str]:
    """``("airside" | "groundside", reason)`` for one polygon.

    R1 is the R-VETO: positive airside evidence wins outright, whole
    shape, no matter how much road overlaps it.  R2-R5 only ever fire
    when the airside evidence is at or near zero.
    """
    airside = evidence.airside
    # R1 — positive airside evidence wins outright (R-VETO).
    if airside >= PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC:
        return ("airside", f"OSM airside {100 * airside:.0f}%")
    # R2 — the road corridor dominates the polygon.
    if (evidence.road >= PAVEMENT_CLASS_ROAD_DOMINANT_FRAC
            and airside < PAVEMENT_CLASS_AIRSIDE_WEAK_FRAC):
        return ("groundside", f"road {100 * evidence.road:.0f}%")
    # R3 — nowhere wide enough for an aircraft.
    if evidence.opening_vehicle:
        return ("groundside", "opening < aircraft width")
    # R4 — parking lot.
    if (evidence.parking >= PAVEMENT_CLASS_PARKING_FRAC
            and airside < PAVEMENT_CLASS_AIRSIDE_WEAK_FRAC):
        return ("groundside", f"parking {100 * evidence.parking:.0f}%")
    # R5 — partial road, no airside evidence at all, away from a runway.
    if (evidence.road >= PAVEMENT_CLASS_ROAD_PARTIAL_FRAC
            and airside < PAVEMENT_CLASS_AIRSIDE_NONE_FRAC
            and evidence.d_runway > PAVEMENT_CLASS_RUNWAY_STANDOFF_M):
        return ("groundside",
                f"road {100 * evidence.road:.0f}% + no airside evidence "
                f"+ {evidence.d_runway:.0f} m from runway")
    return ("airside", "no groundside evidence")


# ═════════════════════════════════════════════════════════════════════
# R-SPLIT — the mouth split
# ═════════════════════════════════════════════════════════════════════

@dataclass
class SplitResult:
    """One shape's wide-body / thin-tail decomposition."""
    body: object | None = None            # Polygon or MultiPolygon
    tails: list = field(default_factory=list)   # [Polygon]
    n_cuts: int = 0


def _is_tail(piece, tail_half_width: float) -> bool:
    """A piece nowhere wider than ``2 * tail_half_width`` is a corridor."""
    try:
        # A bbox dimension under the erosion diameter proves the buffer
        # empty without computing it (an inscribed disk of radius r
        # needs 2r in both axes) — the erosion is a per-shape build-time
        # hotspot and most pieces fail this box test.
        minx, miny, maxx, maxy = piece.bounds
        if (maxx - minx < 2.0 * tail_half_width
                or maxy - miny < 2.0 * tail_half_width):
            return True
        return piece.buffer(-tail_half_width).is_empty
    except _GEOM_EXC:
        return False


def split_body_and_tails(
        polygon,
        tail_max_width_m: float = PAVEMENT_CLASS_TAIL_MAX_WIDTH_M,
        tail_min_length_m: float = PAVEMENT_CLASS_TAIL_MIN_LENGTH_M,
        min_body_area_m2: float = PAVEMENT_CLASS_SPLIT_MIN_BODY_AREA_M2,
        min_tail_area_m2: float = PAVEMENT_CLASS_SPLIT_MIN_TAIL_AREA_M2,
        max_ring_vertices: int = PAVEMENT_CLASS_SPLIT_MAX_RING_VERTICES,
        ) -> SplitResult:
    """Cut ``polygon`` at the MOUTHS where thin corridors leave the wide
    body, and return ``(body, tails)``.

    Straight reuse of the existing mouth machinery,
    ``pavement/apron_necks``: :func:`~.pavement.apron_necks.neck_cuts`
    finds the mouth chords (two near boundary vertices whose excursion
    erodes to nothing at the given half-width — exactly "a thin arm"),
    and :func:`~.pavement.apron_necks._cut_at_mouth` performs the ring
    split.  The only thing this function adds is the parameterisation
    (a ROAD half-width instead of a taxilane one) and the body/tail
    partition afterwards.

    The BODY is the union of every non-corridor piece — one geometry,
    never carved (R-VETO).  Pieces that are corridors but too small /
    too short to be a road are folded back into the body too, so a
    decomposition that finds no real tail returns the input unchanged.
    """
    result = SplitResult()
    if polygon is None or polygon.is_empty or polygon.geom_type != "Polygon":
        result.body = polygon
        return result
    try:
        n_ring = len(polygon.exterior.coords)
    except _GEOM_EXC:
        result.body = polygon
        return result
    if n_ring > max_ring_vertices:
        result.body = polygon
        return result
    half_width = 0.5 * tail_max_width_m
    from .pavement.apron_necks import _cut_at_mouth, neck_cuts
    try:
        cuts = neck_cuts(polygon,
                         taxi_hw=half_width,
                         max_mouth=tail_max_width_m,
                         min_excursion=tail_min_length_m,
                         min_neck_len=12.0)
    except _GEOM_EXC:
        cuts = []
    if not cuts:
        result.body = polygon
        return result
    pieces = [polygon]
    for a, b in cuts:
        mid = Point(0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
        nxt = []
        for piece in pieces:
            try:
                if piece.distance(mid) > 1.0:
                    nxt.append(piece)
                    continue
            except _GEOM_EXC:
                nxt.append(piece)
                continue
            sub = _cut_at_mouth(piece, a, b)
            if (sub and len(sub) >= 2
                    and max(p.area for p in sub) >= min_body_area_m2
                    and min(p.area for p in sub) >= min_tail_area_m2):
                nxt.extend(sub)
                result.n_cuts += 1
            else:
                nxt.append(piece)
        pieces = nxt
    if len(pieces) <= 1:
        result.body = polygon
        result.n_cuts = 0
        return result
    body_pieces, tails = [], []
    for piece in pieces:
        long_enough = False
        try:
            long_enough = (0.5 * piece.exterior.length
                           >= tail_min_length_m + 0.5 * tail_max_width_m)
        except _GEOM_EXC:
            long_enough = False
        if (piece.area >= min_tail_area_m2 and long_enough
                and _is_tail(piece, half_width)):
            tails.append(piece)
        else:
            body_pieces.append(piece)
    if not tails:
        result.body = polygon
        result.n_cuts = 0
        return result
    body = _union(body_pieces)
    if body is None or body.area < min_body_area_m2:
        # Nothing wide enough is left to be an apron — this is a pure
        # corridor network, which the whole-shape vote handles.
        result.body = polygon
        result.n_cuts = 0
        return result
    if body.geom_type != "Polygon":
        # Removing the tails DISCONNECTED the body, so at least one of
        # them is a BRIDGE between two pads rather than an arm leaving
        # one.  R-SPLIT is about "where the road LEAVES the apron"; a
        # corridor with apron at both ends has not left, so the shape
        # stays whole (and every downstream consumer keeps its
        # single-ring ``BuiltShape.polygon`` contract).
        result.body = polygon
        result.tails = []
        result.n_cuts = 0
        return result
    result.body = body
    result.tails = tails
    return result


def _pavement_adjacency_index(layout):
    """``(STRtree, polys, owner_ids)`` over every built pavement shape.

    Same idiom as ``adjacent_ground.apron_wall_pavement_adjacency_index``
    — built ONCE per airport, box-queried per test, ``owner_ids``
    carrying ``id(shape)`` so a shape is never counted as adjacent to
    itself (here: so a tail is never flanked by the very shape it was
    cut out of).
    """
    from shapely.strtree import STRtree
    polys, owners = [], []
    for shape in layout.shapes:
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty:
            continue
        polys.append(polygon)
        owners.append(id(shape))
    if not polys:
        return None
    try:
        return (STRtree(polys), polys, owners)
    except _GEOM_EXC:
        return None


def _flank_contact_fraction(tail, index, owner=None,
                            clear_m: float = PAVEMENT_CLASS_FLANK_CLEAR_M
                            ) -> float:
    """Fraction of ``tail``'s perimeter with OTHER pavement within
    ``clear_m`` — the "empty terrain on both sides" measurement.

    ``owner`` is the shape the tail was cut from; its own polygon (the
    body) is skipped, so the MOUTH chord — the one edge a tail always
    shares — never counts as a flank.

    ``index is None`` means the layout holds no other pavement at all,
    so the flanks really are empty (0.0).  A measurement that FAILS
    returns 1.0 (fully flanked): an unmeasurable flank must never
    license a demotion.
    """
    if index is None:
        return 0.0
    tree, polys, owners = index
    skip = None if owner is None else id(owner)
    try:
        boundary = tail.exterior
        total = boundary.length
        if total <= 0.0:
            return 1.0
        near = []
        for gi in tree.query(tail.buffer(clear_m)):
            gi = int(gi)
            if owners[gi] == skip:
                continue
            polygon = polys[gi]
            if polygon.distance(tail) <= clear_m:
                near.append(polygon)
        if not near:
            return 0.0
        halo = unary_union([p.buffer(clear_m) for p in near])
        return min(1.0, boundary.intersection(halo).length / total)
    except _GEOM_EXC:
        return 1.0


def _is_road_corridor(geometry, sources: EvidenceSources) -> bool:
    """True when ``geometry`` is a ROAD — a corridor with a centerline
    threaded down its long axis — rather than a landside AREA.

    This is what picks ``service_road`` (graded AXIALLY along the route,
    a DEM-following ramp at the road cap) over ``groundside_pavement``
    (re-levelled as a destination lot), i.e. the same distinction
    ``groundside.reclassify_groundside_route_corridors`` draws for
    apt.dat truck routes, applied to the OSM road feed.

    Two conditions, both necessary:

    * CORRIDOR SHAPE — nowhere wider than a carriageway.  A wide paved
      LOT with roads through it is one surface, not a road (the pipeline
      makes the same call in its service-junction re-role: "a service
      road is NARROW … a WIDE road-only residue is NOT road, it stays
      apron/junction so the lot is one surface, not a 4 % road plaza +
      DEM groundside cliff").
    * THREADED — a road centerline runs most of the long axis.
      ``0.5 * perimeter`` is that axis length to within the corridor's
      own width, so the ratio is the fraction of it the road threads;
      a shape that merely overlaps corridors sideways (a widened verge)
      fails and stays ``groundside_pavement``.
    """
    if sources.road_lines is None:
        return False
    try:
        if not _is_tail(geometry, 0.5 * PAVEMENT_CLASS_TAIL_MAX_WIDTH_M):
            return False
        run_m = sources.road_lines.intersection(geometry).length
        axis_m = 0.5 * geometry.exterior.length
        if axis_m <= 0.0:
            return False
        return (run_m >= PAVEMENT_CLASS_TAIL_MIN_LENGTH_M
                and run_m >= PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC * axis_m)
    except _GEOM_EXC:
        return False


# ═════════════════════════════════════════════════════════════════════
# The pass
# ═════════════════════════════════════════════════════════════════════

def _demote(shape, role, dem_at, law_anchors=None, anchor_key=None,
            stats=None):
    """Move ``shape`` to a landside ``role`` the way the established
    demotions do (``_reclassify_runway_disconnected_to_groundside`` for
    groundside, ``groundside.reclassify_groundside_route_corridors`` for
    service roads): a groundside piece is re-elevated onto the DEM, a
    service road drops its airside altitudes and is solved axially.
    Returns True when the shape actually moved.

    The DEM here is a PRE-SOLVE SEED (this runs in the classification
    slot, long before the one solve) — but it must not be the shape's
    only source: where the piece already carries a field, or welds to a
    surface that already carries one, those are law and the ladder in
    ``groundside._seat_ring_on_law_anchors`` takes them first.  A piece
    with neither is counted as a LAW ISLAND rather than shipped silently.
    """
    from .groundside import (_dem_follow_polygon, _shape_prior,
                             _LAW_SEATED_ATTR)
    if role == ROLE_GROUNDSIDE_PAVEMENT:
        if dem_at is not None:
            seat_out: dict = {}
            built = _dem_follow_polygon(shape.polygon, dem_at,
                                        simplify_tol=0.0,
                                        law_anchors=law_anchors,
                                        anchor_key=anchor_key,
                                        prior=_shape_prior(shape),
                                        stats=stats, seat_out=seat_out)
            if built is None:
                return False          # never half-convert real pavement
            shape.polygon, shape.node_altitudes = built
            setattr(shape, _LAW_SEATED_ATTR,
                    bool(seat_out.get("law_seated")))
        else:
            shape.node_altitudes = None
        shape.ref = "groundside"
    else:
        shape.node_altitudes = None
        shape.ref = ""
    shape.role = role
    shape.altitude = None
    shape.altitude_high = None
    shape.altitude_low = None
    return True


def _new_landside_shape(polygon, role, dem_at, law_anchors=None,
                        anchor_key=None, prior=None, stats=None):
    """A fresh landside ``BuiltShape`` for one split-off tail.

    ``prior`` is the PARENT shape's ring+values: a tail split off a
    valued pavement piece is the same surface, so it inherits the
    parent's field along the shared edge rather than re-following DEM.
    """
    from .groundside import _dem_follow_polygon, _LAW_SEATED_ATTR
    node_altitudes = None
    seat_out: dict = {}
    if role == ROLE_GROUNDSIDE_PAVEMENT and dem_at is not None:
        built = _dem_follow_polygon(polygon, dem_at, simplify_tol=0.0,
                                    law_anchors=law_anchors,
                                    anchor_key=anchor_key, prior=prior,
                                    stats=stats, seat_out=seat_out)
        if built is None:
            return None
        polygon, node_altitudes = built
    shape = BuiltShape(
        polygon=polygon, role=role,
        ref=("groundside" if role == ROLE_GROUNDSIDE_PAVEMENT else ""))
    shape.node_altitudes = node_altitudes
    setattr(shape, _LAW_SEATED_ATTR, bool(seat_out.get("law_seated")))
    return shape


def classify_pavement_v1(layout, icao: str = "", dem=None,
                         tile_lat: int = 0, tile_lon: int = 0) -> dict:
    """Vote every apron-role shape airside vs landside; split at mouths.

    Returns a summary dict (``flips``, ``flip_area_m2``, ``splits``,
    ``tails``, ``groundside``, ``service_road``, ``seconds``) — also
    stashed on the layout as ``pavement_class_summary`` so a probe or a
    test can read the decision without re-deriving it.

    NO-OP when ``config.PAVEMENT_CLASS_V1`` is off: the layout is not
    touched at all and the emitted patch is byte-identical to the
    pre-feature build.
    """
    summary = {"enabled": False, "flips": 0, "flip_area_m2": 0.0,
               "splits": 0, "tails": 0, "groundside": 0,
               "service_road": 0, "candidates": 0, "seconds": 0.0}
    if not PAVEMENT_CLASS_V1:
        layout.pavement_class_summary = summary
        return summary
    import time as _time
    started = _time.perf_counter()
    summary["enabled"] = True
    candidates = [s for s in layout.shapes
                  if s.role == ROLE_APRON
                  and s.polygon is not None and not s.polygon.is_empty
                  and s.polygon.area >= PAVEMENT_CLASS_MIN_AREA_M2]
    summary["candidates"] = len(candidates)
    if not candidates:
        layout.pavement_class_summary = summary
        return summary
    sources = evidence_sources(layout)
    if not (sources.road_corridors or sources.osm_airside
            or sources.parking_corridors):
        # No evidence of ANY kind reached this airport — the classifier
        # has nothing to vote on and must not guess (a silent absence of
        # evidence is exactly the hole the road feed was built to close).
        UI.vprint(1, f"  [pav-class] {icao}: no road-feed or OSM aeroway "
                     f"evidence available; classification skipped.")
        layout.pavement_class_summary = summary
        return summary

    from .groundside import (_dem_sampler, law_anchor_values,
                             law_anchor_key, _law_seat_stats, _shape_prior)
    dem_at = (_dem_sampler(layout, dem, tile_lat, tile_lon)
              if dem is not None else None)
    # ONCE per pass (single-pass principle) — the law datum and the
    # emitter's own vertex identity, so a demoted piece seats on the law
    # it welds to instead of on raw terrain.
    _law_anchors = law_anchor_values(layout)
    _anchor_key = law_anchor_key(layout, _law_anchors)
    _stats = _law_seat_stats(layout, "classify_pavement_v1")

    decisions: list[dict] = []
    new_shapes: list = []
    # Built lazily and ONCE, only if some shape actually reaches the
    # tail flank test (at HECA: 2 shapes of 151).
    adjacency = _UNSET
    n_groundside = n_service = n_splits = n_tails = 0
    flip_area = 0.0
    for shape in candidates:
        polygon = shape.polygon
        evidence = shape_evidence(polygon, sources)
        record = {"ref": shape.ref, "area": evidence.area,
                  "road": evidence.road, "osm_apron": evidence.osm_apron,
                  "stand": evidence.stand, "taxi": evidence.taxi,
                  "parking": evidence.parking,
                  "airside": evidence.airside,
                  "vehicle_opening": evidence.opening_vehicle,
                  "d_taxi_cl": evidence.d_taxi_cl,
                  "d_runway": evidence.d_runway}
        try:
            centroid = polygon.centroid
            record["lat"], record["lon"] = layout.m_to_ll(centroid.x,
                                                          centroid.y)
        except _GEOM_EXC:
            pass

        # ── R-SPLIT first: a shape with BOTH evidences is not a
        # whole-shape question at all.  The pre-filter is the cheap
        # NECESSARY condition for a split to be possible, so the
        # (quadratic) mouth search runs on a handful of shapes rather
        # than on every apron:
        #   * at least one TAIL's worth of road-covered area — a
        #     fraction test would be wrong here, since the owner's case
        #     is a big apron with a thin road arm and the arm's SHARE of
        #     the shape can be a few per cent;
        #   * some airside evidence — a shape with none anywhere cannot
        #     have a sub-region above the R1 threshold;
        #   * room for a body — below the minimum body area there is no
        #     apron left to keep.
        split_applied = False
        if (PAVEMENT_CLASS_MOUTH_SPLIT
                and (evidence.road * evidence.area
                     >= PAVEMENT_CLASS_SPLIT_MIN_TAIL_AREA_M2)
                and evidence.airside >= PAVEMENT_CLASS_AIRSIDE_NONE_FRAC
                and evidence.area >= PAVEMENT_CLASS_SPLIT_MIN_BODY_AREA_M2):
            split = split_body_and_tails(polygon)
            if split.tails:
                body_evidence = shape_evidence(split.body, sources)
                if (body_evidence.airside
                        >= PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC):
                    if adjacency is _UNSET:
                        adjacency = _pavement_adjacency_index(layout)
                    keep, demote = [], []
                    for tail in split.tails:
                        tail_evidence = shape_evidence(tail, sources)
                        flank = _flank_contact_fraction(tail, adjacency,
                                                        owner=shape)
                        if (tail_evidence.road >= PAVEMENT_CLASS_TAIL_ROAD_FRAC
                                and flank
                                <= PAVEMENT_CLASS_TAIL_MAX_FLANK_CONTACT):
                            demote.append(tail)
                        else:
                            keep.append(tail)
                    body = _union([split.body] + keep) or split.body
                    if body.geom_type != "Polygon":
                        # A KEPT tail was only attached through a
                        # demoted one, so the body would come back in
                        # pieces.  ``BuiltShape.polygon`` is a single
                        # ring by contract (a MultiPolygon here reaches
                        # ``groundside._verts_buckets`` as an
                        # ``exterior`` AttributeError); leave the shape
                        # whole rather than carve a real apron.
                        demote = []
                    if demote:
                        shape.polygon = body
                        for tail in demote:
                            role = (ROLE_SERVICE_ROAD
                                    if _is_road_corridor(tail, sources)
                                    else ROLE_GROUNDSIDE_PAVEMENT)
                            made = _new_landside_shape(
                                tail, role, dem_at,
                                law_anchors=_law_anchors,
                                anchor_key=_anchor_key,
                                prior=_shape_prior(shape), stats=_stats)
                            if made is None:
                                continue
                            new_shapes.append(made)
                            n_tails += 1
                            flip_area += tail.area
                            if role == ROLE_SERVICE_ROAD:
                                n_service += 1
                            else:
                                n_groundside += 1
                        n_splits += 1
                        split_applied = True
                        record["verdict"] = "split"
                        record["reason"] = (
                            f"body OSM airside "
                            f"{100 * body_evidence.airside:.0f}% + "
                            f"{len(demote)} road tail(s)")
                        record["tails_demoted"] = len(demote)
                        record["tails_kept"] = len(keep)
        if split_applied:
            decisions.append(record)
            continue

        verdict, reason = whole_shape_verdict(evidence)
        record["verdict"] = verdict
        record["reason"] = reason
        decisions.append(record)
        if verdict != "groundside":
            continue
        # A whole-shape demotion that a road CENTERLINE threads is a
        # road, not a lot — the ``reclassify_groundside_route_corridors``
        # semantics, applied at classification time.
        role = (ROLE_SERVICE_ROAD if _is_road_corridor(polygon, sources)
                else ROLE_GROUNDSIDE_PAVEMENT)
        if not _demote(shape, role, dem_at, law_anchors=_law_anchors,
                       anchor_key=_anchor_key, stats=_stats):
            record["verdict"] = "airside"
            record["reason"] = "DEM follow failed — kept"
            continue
        record["role"] = role
        flip_area += evidence.area
        if role == ROLE_SERVICE_ROAD:
            n_service += 1
        else:
            n_groundside += 1

    if new_shapes:
        layout.shapes.extend(new_shapes)
    n_flips = n_groundside + n_service
    summary.update({
        "flips": n_flips, "flip_area_m2": flip_area, "splits": n_splits,
        "tails": n_tails, "groundside": n_groundside,
        "service_road": n_service,
        "seconds": _time.perf_counter() - started,
    })
    layout.pavement_class_summary = summary
    layout.pavement_class_decisions = decisions

    # New groundside members must honour the no-shared-boundary
    # invariant vs terminals / airside — same clip the
    # runway-disconnected demotion runs (see there).
    if n_groundside and dem is not None:
        from .groundside import _separate_groundside_from_airside
        try:
            _separate_groundside_from_airside(layout, dem, tile_lat, tile_lon)
        except _GEOM_EXC:
            pass

    if n_flips or n_splits:
        UI.vprint(1,
            f"  [pav-class] {icao}: pavement classification v1 — "
            f"{n_flips} of {len(candidates)} apron shape(s) demoted "
            f"({flip_area:,.0f} m²: {n_groundside} groundside_pavement, "
            f"{n_service} service_road); {n_splits} mouth split(s) "
            f"yielding {n_tails} road tail(s); "
            f"{summary['seconds']:.2f} s.")
    else:
        UI.vprint(1,
            f"  [pav-class] {icao}: pavement classification v1 — no "
            f"demotion over {len(candidates)} apron shape(s) "
            f"({summary['seconds']:.2f} s).")
    return summary
