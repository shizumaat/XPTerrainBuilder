"""Taxi/road bridges + tunnel portals + depressed-road segments.

Five emitters:

* ``_emit_tunnel_portals`` — short ramp polygons at tunnel-OSM
  entrance / exit so the road dives under airport pavement.
* ``_scenery_has_bridge_objects`` — DSF-pavement check that gates
  bridge emission (no point emitting bridge polygons if the
  underlying scenery already provides bridge meshes).
* ``_emit_taxi_bridges`` — taxi-over-road bridges.
* ``_emit_underpass_road_approaches`` — road approaches sloping
  down toward an underpass.
* ``_emit_through_airport_depressed_roads`` — road segments
  depressed below airport surface where they cut through.

**All five are gated by ``EMIT_BRIDGES_AND_TUNNELS`` in
``O4_Pavement_Config`` (currently True).**  Each emitter carves
its footprint out of overlapping airside / groundside pavement
before emitting so ``test_no_self_overlap`` stays green.

Public API (leading-underscore preserved for backward compatibility
with internal callers in ``O4_Airport_Pavement_Builder``):

    _emit_tunnel_portals
    _scenery_has_bridge_objects
    _emit_taxi_bridges
    _emit_underpass_road_approaches
    _emit_through_airport_depressed_roads
"""
from __future__ import annotations

import math
import os
import re

import O4_UI_Utils as UI

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.affinity import translate as shapely_translate
from shapely.ops import linemerge, nearest_points, substring, unary_union
from shapely.strtree import STRtree

# Narrow exception tuple for shapely / numeric-geometry failure
# modes + file I/O.  Programming errors propagate so they surface
# immediately rather than being silently masked at runtime.
_GEOM_EXC = (OSError, ValueError,
             GEOSException, TopologicalError)

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
    ROLE_STUB,
    ROLE_BUILDING,
    ROLE_RETAINING_WALL,
    ROLE_RUNWAY_CLEARANCE,
    ROLE_RUNWAY_CROSSING,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_TUNNEL_RAMP,
    ROLE_TUNNEL_TRENCH,
    SHARED_VERTEX_TOL_M,
)
from .pavement.vertices import _snap_polygon_vertices_to_rect_corners
from .pavement.runways import _sample_runway_segment_elev
from .elevation import _resample_node_altitudes_nn, _sample_dem
from .geom_safe import min_rotated_rect
from . import config as _CFG
from . import dsf_road_network
from .config import (
    IMPLIED_CROSSING_TUNNELS,
    IMPLIED_TUNNEL_TAG_EVIDENCE,
    IMPLIED_TUNNEL_TAG_EVIDENCE_M,
    SKIP_TUNNEL_RAMPS_NEAR_ROADS,
    TUNNEL_ADJACENT_ROAD_DIST_M,
    TUNNEL_DEM_CUT_MIN_DROP_M,
    TUNNEL_DEM_CUT_WINDOW_M,
    TUNNEL_FORK_THROAT,
    TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M,
    TUNNEL_MOUTH_PLATE_LENGTH_M,
    TUNNEL_MOUTH_WINDOW_M,
    TUNNEL_ROOF_PLATE_MAX_LENGTH_M,
)

# Feature B (object-derived bridge terrain, docs/object_terrain_features_
# spec.md).  The two layout attributes the assembler
# (``object_terrain_assembly``) caches the classifier output under; read
# here at emission time.  Read the live ``_CFG.OBJECT_BRIDGE_TERRAIN`` /
# ``_CFG.BRIDGE_ROAD_CLEARANCE_M`` (never a bound copy) so the gate and
# the clearance constant honour env + monkeypatch at call time.
_OBJECT_BRIDGE_CLASSIFICATION_ATTRIBUTE = "_object_bridge_classification"
_TUNNEL_PORTAL_PAIRS_ATTRIBUTE = "_object_tunnel_portal_pairs"
_OBJECT_BRIDGE_ROAD_NETWORKS_ATTRIBUTE = "_object_bridge_road_networks"
_OBJECT_BRIDGE_ROUTE_LINES_ATTRIBUTE = "_object_bridge_route_lines"


__all__ = [
    "_emit_taxi_bridges",
    "_emit_through_airport_depressed_roads",
    "_emit_tunnel_portals",
    "_emit_underpass_road_approaches",
    "_scenery_has_bridge_objects",
]


# Per-OSM-highway-type carriageway width (user 2026-05-03).
# Was a single 22 m default, which made every tunnel look like a
# 6-lane motorway.  Real-world widths vary by classification; the
# numbers below match typical FAA-relevant standards (single
# carriageway including shoulders).
HIGHWAY_CARRIAGEWAY_WIDTH_M = {
    "motorway":         25.0,  # 25 m corridor per user 2026-07-04 (KDFW)
    "motorway_link":     8.0,
    "trunk":            22.0,
    "trunk_link":        8.0,
    "primary":          18.0,
    "primary_link":      7.0,
    "secondary":        15.0,  # 15 m corridor per user 2026-07-04 (KDFW)
    "secondary_link":    7.0,
    "tertiary":          9.0,
    "tertiary_link":     6.0,
    "residential":       7.0,
    "service":           6.0,
    # Pseudo-type for railway tunnel bores.  Single-track right-of-way
    # (one ``railway=rail`` line, no ``tracks=2``): a rail bore is
    # NARROWER than the road carriageway it forks from — user 2026-06-13,
    # "roads are supposed to be wider (double I think) than rail".  Was
    # 10 m (double-track, user 2026-06-12); a 9 m tertiary road is now
    # ~2× this.
    "railway":          5.0,
    # TWIN parallel rails emitted as ONE bore (user 2026-07-04, KCLT):
    # OSM maps each track as its own ``railway=rail`` line; two lines
    # side by side are one double-track corridor — ~5 m per rail plus
    # margin, "12 m to 15 m for two rails".
    "railway_twin":    14.0,
}

# Two rail tunnel lines closer than this run in ONE corridor — the pair
# emits a single ``railway_twin`` bore (the other line's portals are
# suppressed).
TWIN_RAIL_NEAR_M = 10.0

# Every tunnel break (portal split point) lands this far OUTSIDE the
# taxiway pavement edge (user 2026-07-04, KDFW): the portal's 1 m-thick
# retaining-wall cap then occupies exactly [pavement edge, edge + 1 m],
# with the ramp's low end right behind it.
TAXI_EDGE_BREAK_MARGIN_M = 1.0

# OSM ways less than this far apart group into a SINGLE underpass
# corridor (user 2026-07-04, KDFW): a motorway + its frontage road +
# a rail line running together get one combined ramp, never
# overlapping per-way ramps.  KDFW's two motorway carriageways run
# ~113 m apart and correctly stay separate corridors.
UNDERPASS_GROUP_DIST_M = 35.0


def _carriageway_width_for(highway_type: str | None,
                            default_m: float) -> float:
    """Return the carriageway width in metres for an OSM highway
    type, falling back to ``default_m`` for unknown types.
    """
    if highway_type is None:
        return default_m
    return HIGHWAY_CARRIAGEWAY_WIDTH_M.get(highway_type, default_m)


# Per-lane width for ``lanes=``-derived carriageway sizing (typical
# rural/urban lane, between the 3.0 m urban minimum and the 3.65 m
# trunk standard).
LANE_WIDTH_M = 3.5

#: The carriageway width a bore falls back to when its way carries
#: neither ``width=`` nor ``lanes=``.  ONE home: ``_emit_tunnel_portals``
#: takes it as its parameter default and the §T7 covered-span mask reads
#: it, so the mask's width and the bore's width can never be two numbers
#: (this module "states no second number" — the service-road docstring's
#: rule, and the reason that one is written down).
TUNNEL_DEFAULT_CARRIAGEWAY_WIDTH_M = 22.0


def _carriageway_width_from_tags(highway_type: str | None,
                                 tags: dict | None,
                                 default_m: float) -> float:
    """Carriageway width in metres for a road way, preferring the way's
    own OSM measurements over the per-type table (user 2026-07-16,
    EGPB: the table's 18 m ``primary`` entry sized the A970's ramps at
    ~3× the mapped ~6.5 m single carriageway):

      1. ``width=`` — metres (bare number, ``6.5 m``, or a comma
         decimal), sanity-clamped to [2.5, 40] m;
      2. ``lanes=`` × ``LANE_WIDTH_M``;
      3. the ``HIGHWAY_CARRIAGEWAY_WIDTH_M`` table via
         :func:`_carriageway_width_for` (which also serves the
         ``railway`` / ``railway_twin`` pseudo-types).

    Road caches written before the 2026-07-16 tag-schema bump carry
    neither tag, so they fall through to the table unchanged.
    """
    if tags:
        raw_width = tags.get("width")
        if raw_width:
            text = str(raw_width).strip().lower()
            if text.endswith("m"):
                text = text[:-1].strip()
            try:
                width_value = float(text.replace(",", "."))
            except ValueError:
                width_value = None
            if width_value is not None and 2.5 <= width_value <= 40.0:
                return width_value
        raw_lanes = tags.get("lanes")
        if raw_lanes:
            try:
                lane_count = int(str(raw_lanes).strip())
            except ValueError:
                lane_count = None
            if lane_count is not None and 1 <= lane_count <= 10:
                return max(4.0, lane_count * LANE_WIDTH_M)
    return _carriageway_width_for(highway_type, default_m)


# ── Portal OUTWARD ramp width (user ruling 2026-07-15, KBNA runway-02C,
# supersedes the 2026-07-14c "as wide as the MOUTH FACE" rule) ────────
# A tunnel-portal object whose sides slant up into retaining walls has a
# footprint far wider than the DRIVABLE road that emerges from it (KBNA
# portal 1: an 84 m footprint over a 6-lane, 21 m carriageway).  The
# outward approach ramp must match the drivable road, never the full
# footprint, resolved as the first available of:
#   1. the mapped OSM carriageway width of the road crossing the
#      footprint (``_carriageway_width_from_tags``) PLUS a small shoulder
#      margin;
#   2. else the classified deck cross-section width
#      (``BridgeStructure.deck_width_m`` — the narrower rotated-rectangle
#      dimension of the drivable deck surface);
#   3. else the mouth-face width as a last resort.
# The result is ALWAYS capped at the mouth-face width (never wider than
# the object it emerges from).
PORTAL_RAMP_SHOULDER_MARGIN_M = 2.0
# Planning-grade headroom under TUNNEL_RAMP_MAX_GRADE for the legacy
# tunnel ramp chains: absorbs the 0.1 m altitude rounding on short
# quads (a 9 m segment could otherwise round up to ~4.4 % when the
# design grade is exactly 4 %).  Shared by the walk-truncation sizing
# and the effective-space grade clamp in ``_emit_chain``.
TUNNEL_RAMP_GRADE_SAFETY_MARGIN = 0.005
# Elevation difference across a ramp quad below which ``_emit_chain``
# ships it FLAT (one ``altitude``) instead of the sloped high/low pair.
# The flat form offers the AVERAGE at both cross-edges, so it disagrees
# with each neighbour quad about their SHARED nodes by half this number;
# the value is the spec's 0.01 m materiality floor doubled, so the
# disagreement can never exceed the floor (spec
# ``tunnel-ramp-cut-boundaries-spec.md`` §2, ramp-internal corner
# agreement).  It was 0.1 m — up to 0.05 m of disagreement.
_TUNNEL_RAMP_FLAT_QUAD_M = 0.02
# ── R20-1: THE SURFACE WALK'S PLAN FILTER ─────────────────────────────
# The grid ``layout.to_osm`` writes ``alt_abs`` on, and the grid the ramp
# quads' own ``altitude_high``/``altitude_low`` round to.  Both are
# 0.01 m; the 0.1 m the walk filter's old comment sized itself against
# has not been the emitted precision for a long time.
_TUNNEL_ALT_EMIT_STEP_M = 0.01
# Plan tolerance of the walk's deviation filter: a surface-walk vertex is
# dropped only when the retained chain passes within this distance of it,
# so the emitted ramp centreline is within it of the OSM way at EVERY
# node — whatever the node spacing.  0.25 m is a quarter of the campaign's
# worst measured deletion (KCLT node -75937, 1.86 m off the chord the old
# 15 m SPACING merge left behind) and comfortably under the round's 0.3 m
# claim; it is well below a lane width, so no vertex a driver could see
# the road turn at survives it.
_TUNNEL_WALK_DEVIATION_TOL_M = 0.25
# The rounding-safe segment floor, DERIVED rather than guessed.  One
# segment's Δe carries at most one emit grid step of rounding error, so
# the error it adds to that segment's grade is
# ``_TUNNEL_ALT_EMIT_STEP_M / length``.  Keeping that inside the ramp's
# existing planning headroom needs ``step / margin`` = 0.01 / 0.005 = 2 m
# — which is the whole of what the 15 m spacing merge was buying, at the
# real emitted precision.  (``layout``'s law-aware emit snap picks each
# pair's rounding DIRECTION against that pair's own raw cap, so this
# floor is the second line of defence, not the first.)
_TUNNEL_WALK_MIN_SEGMENT_M = (
    _TUNNEL_ALT_EMIT_STEP_M / TUNNEL_RAMP_GRADE_SAFETY_MARGIN)
# FORK SUSTAIN (spec ``docs/specs/tunnel-fork-sustain-spec.md`` §2, owner
# 2026-08-07).  Fraction of the probe stations FROM the divergence
# crossing to the end of the probe window at which the member spread must
# still exceed the divergence threshold for the cluster to fork.  1.0 =
# the spec's literal "remains above it through the end of the probe
# window": a genuine Y-split's arms keep separating, so every remaining
# station holds; twin carriageways come back together and none of the
# later ones do.  Lives here rather than in ``config.py`` because it is
# an emitter invariant, not a user knob (spec: "no config-file knob").
# The measured case it exists for: OTHH A-site, separation 9.52 m at the
# portal → threshold crossing at s ≈ 157.5 m on a 1.2 m relative splay →
# 0.00 m at the far end, where the two carriageways share an end node.
TUNNEL_FORK_SUSTAIN_FRACTION = 1.0
# A big-road highway way within this distance of the portal footprint is
# the road the outward ramp follows; the draped/OSM centrelines the
# corridor walks carry no tags, so the mapped width is re-associated to
# the tagged big-road ways by geometry (the plumbing chosen 2026-07-15).
PORTAL_ROAD_ASSOCIATION_M = 15.0


#: §F2 gate (LEMD ramp/road fidelity spec, law 2).  DEFAULT ON.  OFF
#: restores the big-roads-only width resolution byte for byte.
_ROAD_WIDTH_FROM_FEED_ENV = "O4_ROAD_WIDTH_FROM_FEED"


def road_width_from_feed_enabled() -> bool:
    """§F2: does the width resolver also read the per-airport ROAD FEED?

    THE DEFECT IT CLOSES (owner sim read of 1.0.265, LEMD).  The resolver
    below reads ONE source, the tile's ``big_roads`` cache.  At LEMD that
    cache is EMPTY at both tunnel sites and the tile has no small-roads
    extract at all, so it resolved ``None`` and the ramp fell back to the
    portal object's own face — "about half the width" of the real
    carriageway, and off its centre.  The per-airport ROAD FEED, which
    ``_load_tunnel_road_network`` already merges for the tunnel walk,
    carries those very ways WITH their measurements: measured
    2026-08-28, way -2096 at the item-3 probe is
    ``highway=service lanes=4`` (14.0 m) and way -2070 at the item-1
    portal is ``highway=service lanes=2 tunnel=yes`` (7.0 m).  The source
    STATES a width; nothing read it.  (The KCLT precedent is the same
    shape — owner 2026-07-26, the minter reading an empty small-roads
    cache while the feed held the road.)
    """
    return os.environ.get(_ROAD_WIDTH_FROM_FEED_ENV, "1") == "1"


def _mapped_osm_carriageway_width_m(layout, footprint, to_meters):
    """Widest mapped OSM carriageway (via ``_carriageway_width_from_tags``)
    of a highway way crossing — within :data:`PORTAL_ROAD_ASSOCIATION_M`
    of — the portal ``footprint``, in metres.  ``None`` when no highway
    way is near the footprint or no tagged road source resolves.

    The draped road centrelines the corridor already walks
    (``_draped_road_centerlines_meters``) come from the sibling DSF road
    network and carry NO OSM tags, and the OSM fallback
    (``_load_underpass_osm_road_lines``) drops the tags too — so the
    mapped width cannot be read off the walked lines.  It is instead
    re-associated by geometry to the tagged ways of the two sources this
    module already loads: the tile's big-roads cache
    (``_load_osm_big_roads``, the same cache the level-crossing veto and
    the underpass fallback read) and — §F2 — the per-airport ROAD FEED
    (``layout.airport_road_network``, the source
    ``_load_tunnel_road_network`` merges for the tunnel walk).  Neither
    is a new parser and neither is a second opinion: the WIDEST way near
    the footprint wins across both, exactly as it did across one.
    """
    sources: list = []
    try:
        from .pipeline import _load_osm_big_roads
        nodes_raw, ways_raw = _load_osm_big_roads(
            layout.anchor[0], layout.anchor[1]
        )
        if ways_raw:
            sources.append((nodes_raw, ways_raw))
    except Exception:
        pass
    if road_width_from_feed_enabled():
        network = getattr(layout, "airport_road_network", None)
        if (network is not None
                and getattr(network, "source", "none") != "none"
                and getattr(network, "ways", None)):
            sources.append((network.nodes, network.ways))
    if not sources:
        return None
    best = None
    for nodes_raw, ways_raw in sources:
        nodes_meters: dict[str, tuple[float, float]] = {}
        for node_id, (latitude, longitude) in nodes_raw.items():
            nodes_meters[node_id] = to_meters(longitude, latitude)
        for _way_id, node_refs, tags in ways_raw:
            if tags.get("highway") is None:
                continue  # railway ways carry no carriageway width
            points = [nodes_meters[n] for n in node_refs
                      if n in nodes_meters]
            if len(points) < 2:
                continue
            try:
                line = LineString(points)
                if (line.is_empty
                        or line.distance(footprint)
                        > PORTAL_ROAD_ASSOCIATION_M):
                    continue
            except _GEOM_EXC:
                continue
            # default 0.0 → an unknown highway type resolves to 0 and is
            # skipped; width= / lanes= / a known type table entry all
            # resolve to a positive carriageway width.
            width = _carriageway_width_from_tags(
                tags.get("highway"), tags, 0.0)
            if width > 0.0 and (best is None or width > best):
                best = width
    return best


def _portal_outward_ramp_width_m(
        layout, portal, footprint, to_meters, mouth_face_width_m):
    """Resolve the portal OUTWARD ramp width (user ruling 2026-07-15):
    mapped OSM carriageway + shoulder → classified deck-face width →
    mouth-face width, always capped at the mouth-face width.  Returns
    ``(width_m, provenance)``; ``width_m`` is ``None`` only when no source
    resolves (no OSM road, no deck width, no mouth face)."""
    cap = mouth_face_width_m
    mapped = _mapped_osm_carriageway_width_m(layout, footprint, to_meters)
    if mapped is not None and mapped > 0.0:
        width = mapped + PORTAL_RAMP_SHOULDER_MARGIN_M
        provenance = (
            f"mapped OSM {mapped:.1f} m + "
            f"{PORTAL_RAMP_SHOULDER_MARGIN_M:.0f} m shoulder")
    else:
        deck_face = getattr(portal["bridge"], "deck_width_m", None)
        if deck_face is not None and deck_face > 0.0:
            width = float(deck_face)
            provenance = f"deck-face {deck_face:.1f} m"
        elif cap is not None and cap > 0.0:
            width = float(cap)
            provenance = "mouth-face (last resort)"
        else:
            return None, "unresolved"
    if cap is not None and cap > 0.0 and width > cap:
        width = float(cap)
        provenance += f" (capped at mouth face {cap:.1f} m)"
    return width, provenance


# ── At-grade level-crossing veto for IMPLIED bores (user 2026-07-16,
# EGPB / Gibraltar) ──────────────────────────────────────────────────
# A public through-road crossing runway pavement is normally assumed to
# tunnel under it (``IMPLIED_CROSSING_TUNNELS``) — but a handful of
# airports have a genuine GATED LEVEL CROSSING (Sumburgh's A970 across
# runway 09/27, Gibraltar's Winston Churchill Avenue).  OSM maps these
# with positive at-grade evidence on the crossing way's own nodes:
# ``aeroway=aircraft_crossing`` (usually with ``crossing:aircraft=*``)
# at the intersection, plus ``barrier`` gates / lift gates where the
# road is closed for aircraft movements.  Evidence within the radii
# below of a crossing segment vetoes the synthetic bore — the road
# stays at grade.  Mapped ``tunnel=yes`` ways are never vetoed (the
# mapper's word beats the heuristic in both directions).
AIRCRAFT_CROSSING_VETO_DIST_M = 60.0    # tag sits ON the crossing
LEVEL_CROSSING_GATE_VETO_DIST_M = 120.0  # gates flank the runway strip
LEVEL_CROSSING_BARRIER_VALUES = frozenset((
    "gate", "lift_gate", "swing_gate", "sliding_gate",
))


def _local_meter_projections(anchor: tuple[float, float]):
    """Return ``(to_meters, meters_to_lat_lon)`` closures converting
    between (lon, lat) degrees and the local-meter frame anchored at
    ``anchor`` — the one equirectangular projection every emitter in
    this module shares.
    """
    anchor_lat, anchor_lon = anchor
    cos_anchor = math.cos(math.radians(anchor_lat))

    def to_meters(lon: float, lat: float) -> tuple[float, float]:
        return (math.radians(lon - anchor_lon) * R_EARTH * cos_anchor,
                math.radians(lat - anchor_lat) * R_EARTH)

    def meters_to_lat_lon(x: float, y: float) -> tuple[float, float]:
        return (anchor_lat + math.degrees(y / R_EARTH),
                anchor_lon + math.degrees(x / (R_EARTH * cos_anchor)))

    return to_meters, meters_to_lat_lon


HW_TUNNEL_TYPES = {
    "motorway", "trunk", "primary", "secondary",
    "tertiary", "motorway_link", "trunk_link",
    "primary_link", "residential", "service",
    # ``unclassified`` is the standard OSM class for minor public
    # roads (user 2026-07-17, EGGW: the airside service-road tunnel
    # under the taxiway is ``highway=unclassified tunnel=yes`` and
    # was invisible while ``service``/``residential`` qualified).
    "unclassified",
}
# Rail tunnels qualify too (user 2026-06-12, KPHL: a combined
# road+rail tunnel passes under the hill past the RWY 26
# threshold — the rail bore is railway=rail tunnel=yes and has
# no highway tag at all, so the highway-only filter dropped it).
RAIL_TUNNEL_TYPES = {
    "rail", "light_rail", "subway", "narrow_gauge", "tram",
}

def _tunnelable(tags9: dict) -> bool:
    return (tags9.get("highway") in HW_TUNNEL_TYPES
            or tags9.get("railway") in RAIL_TUNNEL_TYPES)
TUNNEL_VALUES = {"yes", "building_passage"}


def _has_tunnel_tag_evidence(tags9: dict) -> bool:
    """True when ``tags9`` is OSM evidence of a BELOW-GRADE way.

    The R4 evidence test (owner spec round4-othh-fixes, 2026-08-10):
    ``tunnel`` in :data:`TUNNEL_VALUES`, or ``layer`` < 0.  ``layer`` is
    carried by the airport ROAD FEED's tag whitelist
    (``osm_load._ROAD_FEED_WAY_TAGS``); the tile road caches
    (``O4_Vector_Map.ROADS_TAGS_OF_INTEREST``) do not retain it, so on a
    tile-cache way the ``tunnel`` half is the whole test — absence of the
    key is never read as evidence either way.
    """
    if tags9.get("tunnel") in TUNNEL_VALUES:
        return True
    layer = tags9.get("layer")
    if layer is None:
        return False
    try:
        return float(str(layer).split(";")[0]) < 0.0
    except (TypeError, ValueError):
        return False


def _way_signature(tags: dict):
    """The ROAD IDENTITY signature ``(highway, railway, name)``.

    ONE predicate, two consumers: the implied-crossing chain merge
    (:func:`_merge_eligible_chains`) and the R6-2 evidence walk
    (:func:`_chain_tunnel_evidence`).  Two pieces share a signature when
    they are the same road — a class change or a name change makes them
    different roads, whatever the junction geometry says.
    """
    return (tags.get("highway"), tags.get("railway"), tags.get("name"))


def _tunnel_evidence_chain_index(ways, nodes_m):
    """``(endpoint key → way indices, per-way tag-evidence flags)`` for
    the R4 chain walk, under the R6-2 same-road law.

    Keyed on node POSITION (centimetre-rounded), not node id: the merged
    tunnel road network carries three namespaced id spaces (``big_roads``
    plain ids, ``S|`` small_roads, ``F|`` the airport road feed — see
    ``_load_tunnel_road_network``), so the SAME real junction holds three
    different ids.  Coincident positions are the same OSM node's lat/lon
    projected once, i.e. an identity join, never a proximity join.

    **ENDPOINTS ONLY (R6-2, round-6 spec).**  The index used to hold
    every node of every way, which made "connected" mean "shares any
    vertex with anything" — at OTHH the two S1 bores were admitted by
    ``S|-8342`` (tunnel=yes, service) FOUR network hops away through a
    class change and a real junction, exactly the bore R4 meant to
    refuse.  A road CONTINUES at an endpoint join and only there, so the
    index carries a way's first and last node and nothing else; the
    per-position list length is then the join's DEGREE, which the walk
    uses to refuse junctions.  A closed way contributes its shared
    endpoint twice on purpose — the walk's ``wids[0] == wids[1]`` test
    reads that as "no continuation", the same posture
    :func:`_merge_eligible_chains` takes.
    """
    index: dict = {}
    flags: list[bool] = []
    for _i, (_wid, _nrefs, _tags) in enumerate(ways):
        flags.append(_has_tunnel_tag_evidence(_tags))
        if not _nrefs:
            continue
        for _n in (_nrefs[0], _nrefs[-1]):
            _p = nodes_m.get(_n)
            if _p is None:
                continue
            index.setdefault((round(_p[0], 2), round(_p[1], 2)),
                             []).append(_i)
    return index, flags


def _chain_tunnel_evidence(start, index, flags, ways, nodes_m,
                           near, radius_m) -> bool:
    """True when way ``start`` — or a way its SAME-ROAD chain continues
    into within ``radius_m`` of ``near`` — carries below-grade tag
    evidence.

    Breadth-first over the endpoint index, hopping ONLY through nodes
    within ``radius_m`` of the crossing geometry ``near``, so the walk
    stays local (the build-budget argument) and "connects to within
    100 m" is measured from the crossing itself.

    **THE R6-2 LAW (round-6 spec, OTHH S1).**  A hop is admitted only at
    a DEGREE-2 ENDPOINT JOIN of IDENTICAL :func:`_way_signature` — the
    same predicate the chain merge uses.  A junction node (three or more
    way ends), a mid-way T (the other way's endpoint is not ours), a
    class change or a name change ENDS the walk.  "Network-connected
    within 100 m" admitted a bore four hops away through a class change
    and a real junction; evidence must ride the SAME ROAD.
    """
    if flags[start]:
        return True
    seen = {start}
    frontier = [start]
    while frontier:
        nxt: list[int] = []
        for _i in frontier:
            _nrefs = ways[_i][1]
            if not _nrefs:
                continue
            _signature = _way_signature(ways[_i][2])
            for _n in (_nrefs[0], _nrefs[-1]):
                _p = nodes_m.get(_n)
                if _p is None:
                    continue
                try:
                    if near.distance(Point(_p)) > radius_m:
                        continue
                except _GEOM_EXC:
                    continue
                _at_node = index.get((round(_p[0], 2), round(_p[1], 2)),
                                     ())
                # DEGREE-2 ONLY: exactly two DISTINCT way ends meet here.
                # Anything else is a junction (or a closed way's own
                # seam) and the road does not continue through it.
                if len(_at_node) != 2 or _at_node[0] == _at_node[1]:
                    continue
                for _j in _at_node:
                    if _j == _i or _j in seen:
                        continue
                    if _way_signature(ways[_j][2]) != _signature:
                        continue        # class / name change — not us
                    if flags[_j]:
                        return True
                    seen.add(_j)
                    nxt.append(_j)
        frontier = nxt
    return False
# Portal EMISSION qualifies only real excavated tunnels (user
# 2026-06-12): ``building_passage`` is a BUILDING built over an
# at-grade road — no trench, no ramps, nothing for the patch to
# model (KPHL's terminal-complex service passages).  The broader
# TUNNEL_VALUES set stays for the surface-walk exclusions — a
# ramp should not continue INTO a passage either way.
PORTAL_TUNNEL_VALUES = {"yes"}

# R10-1/A6 — THE COVER IS THE DECK (lead ruling 2026-08-11).  A bare-earth
# DEM cannot see a man-made bore under pavement, so "no cut" alone cannot
# tell a real tunnel from flat ground: it refused KCLT's four
# building-passthroughs (right) and all 8 of OTHH's mapped bores (wrong).
# What separates them is WHAT COVERS THE BORE.  Measured over both
# airports, the two populations do not overlap and are not close:
#
#   KCLT passthroughs (F|-600/-601/-873/-1119)
#       building cover 0.98-1.00   airside-pavement cover 0.00-0.02
#   real bores (KCLT F|-255/F|-251, OTHH -68/-69/-96/-97/-114/-115/
#       -613/-614)
#       building cover 0.00        airside-pavement cover 0.18-0.90
#
# The thresholds sit in those gaps with room either side: 0.5 is half a
# way-length under a building (the passthroughs measure ~1.0, every bore
# 0.00), and 0.10 is well under the thinnest real bore's 0.18 while well
# over the fattest passthrough's 0.02.  Deterministic from the layout —
# no env knob, because a gate here decides whether a tunnel exists.
TUNNEL_PASSTHROUGH_BUILDING_COVER_FRAC = 0.5
TUNNEL_BORE_PAVEMENT_COVER_FRAC = 0.10

# R14-3 — THE RAMP RUN IS DEPTH OVER GRADE.  A mouth's open cut climbs
# to ambient in ``bore_depth / TUNNEL_APPROACH_GRADE`` and stops there;
# it is NOT the mapped way's remaining extent.
#
# OWNER RULING 2026-08-11, verbatim: "Ramps should be at up to 5% grade."
# This is a CAP, and the distinction is load-bearing: ``bore_depth /
# TUNNEL_APPROACH_GRADE`` is therefore the MINIMUM lawful run.  A LONGER
# run at a shallower grade is lawful where the geometry demands it; a
# STEEPER one never is, which is what the ``max_drop`` cap below the
# walk enforces on the emitted top edge.  It reads back exactly to the
# owner's own worked example — climb to ambient "in ~100 m" from the
# 5.1 m clearance depth a service-road bore takes, 5.1 / 100 = 0.051.
# The 3.5 % it replaces is a HIGHWAY planning grade, and spending it on
# a service road bought 43 % more roadway for the same climb.
TUNNEL_APPROACH_GRADE = 0.05

# R14-1/A-1 — the ref a CLAIMED road surface takes.  A claimed shape
# keeps its role (and therefore its authority rank); the ref is what
# registers it in ``groundside.BELOW_GRADE_REFS`` so the unchanged R5
# transition law grades the surrounding surface toward it, and what puts
# it in this module's tunnel-pavement union so no wall may cover it.
# ``TUNNEL_ROAD_REF`` now lives in ``layout`` (one home, so the
# groundside passes can recognise a claimed corridor without a
# circular import); re-exported here for every existing reader.
from .layout import TUNNEL_ROAD_REF  # noqa: E402,F401

# R14-2/A-3 — AIRCRAFT-TRANSIT PAVEMENT A CUT NEVER INTERRUPTS.  The
# runway family was already never cut; A-3 adds the taxiway family.
# Owner: "nothing may cut a taxiway" — an aircraft cannot detour round a
# trench.  ``apron`` / ``service_road`` / ``service_junction`` /
# ``groundside_pavement`` stay cuttable: owner ruling 4's beheading
# precedent lives exactly there (OTHH's mapped portals open within apron
# and service pavement), so this supersedes ruling 4 for the taxiway
# family ONLY.
_TUNNEL_PROTECTED_TRANSIT_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_RUNWAY_CLEARANCE,
    ROLE_JUNCTION, ROLE_CROSS_CONNECTOR, ROLE_PRIMARY_PARALLEL,
    ROLE_SECONDARY_PARALLEL, ROLE_STUB,
})

# §T3 (tunnel-integrity-round-spec, RULINGS 2026-08-28 items 6/7): THE
# AIRPORT'S OWN PAVEMENT — the runway / taxiway / apron family whose deck
# a bore passes under.  A bore roofed by this, or opening inside the
# airside gate union, IS the thing the tunnel machinery exists to model,
# so the urban-interchange veto (LMML, 2026-06-12) never reaches it.
# Derived from the transit set plus ``apron`` — never a second hand
# written role list.
_TUNNEL_OWN_BORE_COVER_ROLES = frozenset(
    _TUNNEL_PROTECTED_TRANSIT_ROLES | {ROLE_APRON})


#: §T2.1: the DEM source classes that can actually CARRY an approach
#: profile.  ``flat_site.class_for_resolution_m`` names ``lidar`` for a
#: declared native resolution ≤ 2 m — the metre-credible / sub-metre
#: tier.  ``sub10m`` NEVER qualifies (spec §T2.1, explicit): a 10 m
#: posting smooths a road cut into a broad dish, so "the DEM already
#: carries the descending approach" is false there however deep the
#: measured relief is.
_DEM_CUT_LIDAR_CLASSES = frozenset({"lidar"})


def _dem_cut_provenance(layout, dem) -> tuple[bool, str | None]:
    """§T2.1: may the DEM-CUT LIGHT-TOUCH MODE fire on this build's DEM?

    Returns ``(ok, source_class)``.  EVIDENCE and MODE are separate
    questions (the comment at ``_cut_measured``'s definition): measured
    relief still ADMITS the bore, and this gate decides only whether the
    admitted bore gets the light-touch cap/mouth/roof construction or
    the full synthetic ramp.  The EGGW ruling (2026-07-17) is preserved
    exactly where lidar earned it; a COARSE-DEM "cut" emits the full
    synthetic ramp+mouth as if no cut existed, which is what LEMD's
    eight ramp-less clusters were missing.

    THE REGISTER is the sidecar's own: ``layout.site_class`` (written by
    the flat-site detector at the pipeline's DEM-in-hand point, well
    before this pass) and, failing that, ``layout.dem_inset_provenance``
    read through the SAME classifier the detector uses.  No second
    resolution table lives here.
    """
    _klass = None
    _rec = getattr(layout, "site_class", None)
    if isinstance(_rec, dict):
        _klass = _rec.get("s2_source_class")
    if _klass is None:
        try:
            from . import flat_site as _flat_site
            _klass = _flat_site.source_class_for_dem(
                dem, icao=getattr(layout, "icao", None),
                dem_meta=getattr(layout, "dem_inset_provenance", None),
            ).get("class")
        except Exception:                                # pragma: no cover
            _klass = None
    return (_klass in _DEM_CUT_LIDAR_CLASSES), _klass


def _demcut_provenance_gate_on() -> bool:
    """``O4_DEMCUT_PROVENANCE_GATE`` — §T2's gate, default ON.  ONE gate
    covers both halves of §T2 (they are one ruling about the DEM-cut
    construction): the provenance requirement above, the mouth-beats-cap
    resolution of R16-2b vs R10-2, and the withdrawal of the light-touch
    mouths' unwalled-finding exemption.  OFF restores the pre-round emit
    byte-identically."""
    return os.environ.get("O4_DEMCUT_PROVENANCE_GATE", "1") == "1"


def _obj_tunnel_compose_on() -> bool:
    """``O4_OBJ_TUNNEL_COMPOSE`` — §T1's gate, default ON.  OFF keeps the
    tunnel-only object-trench union, the pre-round retreat-wall scope and
    the unsuppressed deck-clearance corridor, byte-identically."""
    return os.environ.get("O4_OBJ_TUNNEL_COMPOSE", "1") == "1"


#: §T1.1 (Fable ruling 2026-08-28, option (c)): how far beyond a mapped
#: bore's own carriageway its GROUND reaches for the deck-clearance
#: suppression.  The bore's portals and their immediate approach are the
#: ground the OSM tunnel machinery emits its mouth and walls on; a
#: deck-clearance corridor stamped over it is the second authority.
_MAPPED_BORE_GROUND_MARGIN_M = 8.0
_MAPPED_BORE_GROUND_ATTRIBUTE = "_mapped_bore_ground_union"


def _mapped_bore_ground_union(layout):
    """§T1.1: the GROUND every mapped bore at this airport owns, in
    layout metres — its covered span AND its portal ground — or ``None``.

    Each ``tunnel=yes``-class way in the road feed is buffered by half
    its own carriageway width (the way's ``width=``/``lanes=`` tags beat
    the per-type table, exactly as the portal walk sizes it) plus
    :data:`_MAPPED_BORE_GROUND_MARGIN_M`.  A way's ENDS are its portals,
    so the same buffer covers the portal ground without a second notion
    of "near a portal" — one geometry, one definition.

    Cached on the layout: ``build_bridge_layout_shapes`` runs pre-solve
    and ``_emit_tunnel_portals`` in finalize, and re-reading the road
    caches per consumer is both slow and a chance for the two to
    disagree about what the bores are.
    """
    cached = getattr(layout, _MAPPED_BORE_GROUND_ATTRIBUTE, "unset")
    if cached != "unset":
        return cached
    union = None
    try:
        nodes_r, ways_r, _big, _tags = _load_tunnel_road_network(layout)
        to_m, _m_to_ll = _local_meter_projections(layout.anchor)
        nodes_m = {nid: to_m(lon, lat)
                   for nid, (lat, lon) in nodes_r.items()}
        parts: list = []
        for wid, refs, tags in ways_r:
            if tags.get("tunnel") not in PORTAL_TUNNEL_VALUES:
                continue
            if not _tunnelable(tags):
                continue
            pts = [nodes_m[n] for n in refs if n in nodes_m]
            if len(pts) < 2:
                continue
            width = _carriageway_width_from_tags(
                tags.get("highway"), tags, 22.0)
            try:
                parts.append(LineString(pts).buffer(
                    0.5 * float(width) + _MAPPED_BORE_GROUND_MARGIN_M))
            except _GEOM_EXC:                            # pragma: no cover
                continue
        if parts:
            union = unary_union(parts)
            if union.is_empty:
                union = None
        # NAMED, because an EMPTY union silently restores the pre-round
        # treatment: the feed merge that carries most airports' bores
        # ("F|" namespace) needs ``layout.airport_road_network`` to be
        # attached already, and a reader must be able to tell "no mapped
        # bores here" from "the bores were not loaded yet".
        UI.vprint(
            1,
            f"   [object-bridge] §T1.1 mapped-bore ground: "
            f"{len(parts)} bore(s), "
            f"{0.0 if union is None else union.area:,.0f} m2 — the "
            f"ground a deck-clearance corridor may not be stamped over")
    except Exception:                                    # pragma: no cover
        # A missing road cache is "no mapped bores here", never a build
        # failure: the suppression is a NARROWING of an existing
        # treatment, so absent evidence leaves that treatment intact.
        union = None
    try:
        setattr(layout, _MAPPED_BORE_GROUND_ATTRIBUTE, union)
    except (AttributeError, TypeError):                  # pragma: no cover
        pass
    return union


#: §T1.1: the classifier CONTRACTS whose deck-clearance corridor yields
#: to a mapped bore.  The deck-clearance law is for structures over OPEN
#: GROUND; a DECK_CARRIED span (a genuine hard-deck overpass whose deck
#: carries the pavement) keeps its treatment over a mapped road tunnel
#: like any other bridge — the ruling narrows the ambiguous cases only.
_CORRIDOR_YIELDS_TO_BORE_CONTRACTS = ("AMBIGUOUS", "TERRAIN_CARRIED")


def _corridor_yields_to_mapped_bore(bridge, layout):
    """§T1.1: the mapped-bore ground this bridge's corridor must NOT be
    stamped over, or ``None`` when its corridor stands (spec
    tunnel-integrity-round §T1.1 as ruled by Fable 2026-08-28, option
    (c)).

    THE DEFECT, measured at LEMD: mapped bore ``F|-2070`` (tunnel=yes,
    service, layer=-1, 224 m) is ADMITTED and emits BOTH portals — the
    OSM tunnel machinery already owns that ground — and the pack's
    ``Bridges/Bridge2/Bridge3.obj`` (contract TERRAIN_CARRIED) stamps a
    deck-clearance trench at 606.96 m over the north portal anyway.  No
    ``tunnel_ramp`` then lands within 141.8 m of the owner's item-4
    entrance.  The corridor is the second authority, and it is the one
    that yields: the object's pins and its causeway seating OUTSIDE the
    overlap keep their existing treatment.
    """
    if not _obj_tunnel_compose_on():
        return None
    if str(getattr(bridge, "contract", "") or "") not in \
            _CORRIDOR_YIELDS_TO_BORE_CONTRACTS:
        return None
    return _mapped_bore_ground_union(layout)


def _record_corridor_suppression(layout, bridge, ref, polygon,
                                 removed_area_m2, whole: bool) -> None:
    """§T1.1's named line + sidecar note for ONE suppressed piece.

    The named line is the portal-corridor-claim §1 form (one line PER
    PIECE, with the coordinate a reviewer flies to); the sidecar note is
    ``object_corridor_suppressions``, so "why is there no deck-clearance
    trench here?" is answerable from the artifacts and not only from a
    live build's log.
    """
    try:
        from .layout import ROLE_BRIDGE_TRENCH as _ROLE
        _shape = BuiltShape(polygon=polygon, role=_ROLE, ref=ref)
        log_tunnel_piece_removal(
            layout, _shape,
            "object deck-clearance corridor over a MAPPED BORE "
            "(§T1.1: the bore's own machinery owns that ground)",
            verdict=("whole" if whole else "clipped")
            + f", {removed_area_m2:.1f} m2 suppressed")
        _lat = _lon = None
        if polygon is not None and not polygon.is_empty:
            _to_m, _to_ll = _local_meter_projections(layout.anchor)
            _c = polygon.centroid
            _lat, _lon = _to_ll(_c.x, _c.y)
        _existing = list(
            getattr(layout, "object_corridor_suppressions", None) or [])
        _existing.append({
            "object_resources": list(
                getattr(bridge, "object_resources", None) or []),
            "contract": str(getattr(bridge, "contract", "") or ""),
            "ref": ref,
            "suppressed": "whole" if whole else "clipped",
            "suppressed_area_m2": round(float(removed_area_m2), 1),
            "lat": None if _lat is None else round(_lat, 7),
            "lon": None if _lon is None else round(_lon, 7),
        })
        layout.object_corridor_suppressions = _existing
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        # An instrument may never take a build down.
        return


def _tunnel_veto_scoped_on() -> bool:
    """``O4_TUNNEL_VETO_SCOPED`` — §T3's gate, default ON.  OFF restores
    the unscoped adjacent-road veto byte-identically."""
    return os.environ.get("O4_TUNNEL_VETO_SCOPED", "1") == "1"


def _bore_floor_elevation(apt_elev, deck_reference, mouth_min,
                          cut_measured, tunnel_depth_m):
    """A-2: the elevation a bore's floor sits at.

    ``deck_reference − BRIDGE_ROAD_CLEARANCE_M`` — what the crossing
    structurally requires and no more.  A bore whose DEM cut was
    MEASURED keeps R10-3's deeper-of-the-two, so a real trench is never
    filled back in.  The 8 m ``tunnel_depth_m`` is the last resort for a
    portal with no deck reference at all (``layer < 0``, no usable DEM,
    no crossing): there, nothing has been measured to reason from.
    """
    if deck_reference is None:
        return float(apt_elev) - float(tunnel_depth_m)
    _clearance_floor = (float(deck_reference)
                        - float(_CFG.BRIDGE_ROAD_CLEARANCE_M))
    if cut_measured and mouth_min is not None:
        return min(float(mouth_min), _clearance_floor)
    return _clearance_floor


def _load_tunnel_road_network(layout: "PavementLayout"):
    """Load the big-roads + small-roads OSM caches for the tile
    and merge them under namespaced ids.  Returns ``(nodes_r,
    ways_r, big_way_ids, node_tags_r)`` where ``big_way_ids`` is the
    id set of the big-roads ways (pre-2026-06-12 candidate class) and
    ``node_tags_r`` maps node id → tag dict for the (few) nodes whose
    tags the road-layer download whitelist retained (level-crossing
    evidence: ``aeroway=aircraft_crossing``, ``barrier`` gates —
    empty for caches written before the tag-schema bump).
    """
    # MEMOISED ON THE LAYOUT (§T7): the covered-span mask is published at
    # the service-road mint in phase 4 and the tunnel pass runs in phase
    # 6; both need this network, and loading the road caches twice would
    # be two costs AND two populations.  One load, one answer, per build.
    _memo = getattr(layout, "_tunnel_road_network_memo", None)
    if _memo is not None:
        return _memo
    from .osm_load import _load_osm_road_layer
    # Load big-roads OSM cache for this tile — AND small_roads (user
    # 2026-06-12, KPHL): the big/small highway split puts tertiary /
    # residential / service ways in small_roads, so a minor-road
    # tunnel bore (KPHL's road+rail tunnel under the RWY 26 hill:
    # highway=tertiary, 151 m past the threshold) was invisible to
    # this emitter even though its type is in HW_TUNNEL_TYPES.
    nodes_r, ways_r, node_tags_r = _load_osm_road_layer(
        "big_roads", layout.anchor[0], layout.anchor[1])
    _big_way_ids = {w[0] for w in ways_r}
    nodes_s, ways_s, node_tags_s = _load_osm_road_layer(
        "small_roads", layout.anchor[0], layout.anchor[1])
    if nodes_s:
        # ⚠ The road caches use SYNTHETIC per-layer negative ids:
        # ``r-13-078:-202`` in big_roads and in small_roads are
        # DIFFERENT real-world features.  A raw dict merge overwrote
        # big-road node coordinates with unrelated small-road points
        # and displaced whole tunnel ways by kilometres (SPJC's 4
        # user-approved tunnels measured 5-12 km from the boundary
        # and vanished).  Namespace every small-cache id instead.
        merged_n = dict(nodes_r)
        for nid, ll in nodes_s.items():
            merged_n["S|" + nid] = ll
        nodes_r = merged_n
        node_tags_r = dict(node_tags_r)
        for nid, tags in node_tags_s.items():
            node_tags_r["S|" + nid] = tags
        ways_r = list(ways_r) + [
            ("S|" + wid, ["S|" + n for n in nrefs], tags)
            for wid, nrefs, tags in ways_s]
    # AIRPORT ROAD FEED (owner ruling 2026-07-26, KCLT Yorkmont Road).
    # ``small_roads`` exists only at ``road_level >= 2`` (default 1), so
    # the minor-road classes — tertiary, the *_link ramps, mapped
    # service/unclassified tunnels — were simply ABSENT from this
    # emitter at default config: a tertiary road under KCLT's south
    # apron got no bore because the road was never loaded.  The
    # per-airport road feed (``layout.airport_road_network``,
    # ``osm_load._ensure_airport_road_feed``) already carries every
    # ``highway=`` way for the region, so merge its NON-big classes
    # here under a third namespace ("F|" — the feed uses its own id
    # space, see the ⚠ above) exactly as a small_roads cache would
    # have.  Skipped when a real small_roads cache loaded (tile cache
    # stays authoritative — same precedence the feed itself applies)
    # and when the feed is absent/empty.  Rail stays big_roads-only.
    _BIG_HW = {"motorway", "trunk", "primary", "secondary"}
    net = getattr(layout, "airport_road_network", None)
    if (not nodes_s and net is not None
            and getattr(net, "source", "none") != "none"
            and getattr(net, "ways", None)):
        feed_ways = [
            (wid, nrefs, tags) for wid, nrefs, tags in net.ways
            if tags.get("highway") and tags.get("highway") not in _BIG_HW
            and not tags.get("railway")]
        if feed_ways:
            merged_n = dict(nodes_r)
            for nid, ll in net.nodes.items():
                merged_n["F|" + nid] = ll
            nodes_r = merged_n
            node_tags_r = dict(node_tags_r)
            for nid, tags in (net.node_tags or {}).items():
                node_tags_r["F|" + nid] = tags
            ways_r = list(ways_r) + [
                ("F|" + wid, ["F|" + n for n in nrefs], tags)
                for wid, nrefs, tags in feed_ways]
    _memo = (nodes_r, ways_r, _big_way_ids, node_tags_r)
    try:
        layout._tunnel_road_network_memo = _memo
    except (AttributeError, TypeError):                  # pragma: no cover
        pass
    return _memo


def _merge_eligible_chains(ways_r, hw_types, excluded_ids):
    """Merge consecutive same-road OSM pieces into single chain ways for
    the implied-crossing walk (owner ruling 2026-07-26, KCLT Yorkmont
    Road).  OSM splits a road wherever any attribute changes: Yorkmont
    Road crosses ~61 m under KCLT's south apron as SIX 9-69 m pieces, so
    every candidate interval ended within the end-margin of a way end
    and the must-CROSS test vetoed all of them — the walk saw the
    mapper's segmentation, not the road.

    Only plain surface pieces merge (no tunnel/bridge tag, not excluded,
    implied-eligible class), and only at a DEGREE-2 join: a node hosting
    exactly two eligible endpoints with the same
    ``(highway, railway, name)`` signature.  Junctions (degree ≥ 3),
    class changes and name changes all break the chain, so unrelated
    roads never merge.  Chain ways take the id ``C|<first member id>``
    and the tags of their longest member; member pieces are REPLACED by
    the chain (their geometry lives on inside it).

    The signature predicate is module-level :func:`_way_signature`: the
    R6-2 evidence walk applies the SAME same-road test, and a second
    copy would be a silent drift hazard."""
    _sig = _way_signature

    idx_of: dict = {}
    for i, (wid, nrefs, tags) in enumerate(ways_r):
        if (tags.get("tunnel") in TUNNEL_VALUES or tags.get("bridge")
                or wid in excluded_ids or len(nrefs) < 2
                or nrefs[0] == nrefs[-1]
                or not (tags.get("highway") in hw_types
                        or tags.get("railway") in RAIL_TUNNEL_TYPES)):
            continue
        idx_of[wid] = i
    if len(idx_of) < 2:
        return ways_r
    ends: dict = {}
    for wid, i in idx_of.items():
        nrefs = ways_r[i][1]
        ends.setdefault(nrefs[0], []).append(wid)
        ends.setdefault(nrefs[-1], []).append(wid)
    # Pairwise links at clean degree-2 joins.
    link: dict = {}          # (wid, node) -> other wid
    for node, wids in ends.items():
        if len(wids) != 2 or wids[0] == wids[1]:
            continue
        a, b = wids
        if _sig(ways_r[idx_of[a]][2]) != _sig(ways_r[idx_of[b]][2]):
            continue
        link[(a, node)] = b
        link[(b, node)] = a
    if not link:
        return ways_r
    merged_members: set = set()
    chains: list = []
    for wid in idx_of:
        if wid in merged_members:
            continue
        nrefs = ways_r[idx_of[wid]][1]
        # Walk to the chain's start (no link at the entry node), then
        # forward — loops bail out via the visited set.
        start_wid, entry = wid, nrefs[0]
        seen = {wid}
        while (start_wid, entry) in link:
            prev = link[(start_wid, entry)]
            if prev in seen:
                break                       # closed loop — leave as-is
            seen.add(prev)
            p_refs = ways_r[idx_of[prev]][1]
            entry = p_refs[0] if p_refs[-1] == entry else p_refs[-1]
            start_wid = prev
        if (start_wid, entry) in link:      # closed loop — leave as-is
            continue
        # Forward walk building the merged node list.
        members = []
        cur, cur_entry = start_wid, entry
        chain_refs: list = []
        visited = set()
        while True:
            if cur in visited:
                break
            visited.add(cur)
            members.append(cur)
            c_refs = list(ways_r[idx_of[cur]][1])
            if c_refs[0] != cur_entry:
                c_refs.reverse()
            if chain_refs:
                chain_refs.extend(c_refs[1:])
            else:
                chain_refs.extend(c_refs)
            exit_node = c_refs[-1]
            nxt = link.get((cur, exit_node))
            if nxt is None or nxt in visited:
                break
            cur, cur_entry = nxt, exit_node
        if len(members) < 2:
            continue
        longest = max(members,
                      key=lambda w: len(ways_r[idx_of[w]][1]))
        chains.append((members, chain_refs,
                       dict(ways_r[idx_of[longest]][2])))
        merged_members.update(members)
    if not chains:
        return ways_r
    out = [wt for wt in ways_r if wt[0] not in merged_members]
    for members, chain_refs, tags in chains:
        out.append(("C|" + str(members[0]), chain_refs, tags))
    return out


def _synthesize_implied_crossing_bores(
        layout: "PavementLayout",
        nodes_m: dict,
        ways_r: list,
        excluded_way_ids: set | None,
        low_connector_max_gap_m: float = 0.0,
        node_tags: dict | None = None) -> tuple:
    """Split public through-roads / railways that cross taxi/runway
    pavement into approach + synthetic ``tunnel=yes`` bore pieces.
    Mutates ``nodes_m`` (synthetic split nodes) and returns
    ``(ways_r, low_connector_gaps)``.

    ``node_tags`` (node id → tag dict, from the road-layer caches)
    carries the at-grade level-crossing evidence: a crossing with an
    ``aeroway=aircraft_crossing`` node or nearby ``barrier`` gates is a
    real gated level crossing (EGPB, Gibraltar — user 2026-07-16) and
    gets NO implied bore.

    User 2026-07-04 (KDFW wide underpasses), three behaviours on top
    of the original implied-bore split:

    * MAPPED ``tunnel=yes`` ways of the same public classes are
      RE-SPLIT by the same pavement intersections (gate
      ``O4_TUNNEL_TAXI_BREAKS``): the OSM mapper's tunnel-segment
      endpoints land wherever they were drawn, so breaks came at the
      taxiway edge for implied bores but at arbitrary spots for
      mapped ones ("some seem to be doing that, and others not").
      Deriving every break from OUR pavement makes them uniform.  A
      mapped tunnel that crosses NO taxi/runway pavement is a road
      built over (terminal buildings, aprons) — retagged
      ``building_passage``: no trench, no ramps, but ramp walks
      still refuse to route through it.
    * Every break lands ``TAXI_EDGE_BREAK_MARGIN_M`` (1 m) OUTSIDE
      the pavement edge, so the portal's 1 m retaining-wall cap
      occupies exactly [edge, edge+1 m] — wall at the taxiway edge,
      ramp low end right behind it.
    * Consecutive bores along one way whose surface gap is shorter
      than ``low_connector_max_gap_m`` (too short to ramp up to DEM
      and back — the double-parallel-taxiway case) MERGE into one
      long bore and the gap is recorded in ``low_connector_gaps``
      as ``(gap_line, corridor_width_m)``: the caller emits it as a
      single flat rect at the low elevation with retaining walls,
      instead of two facing overlapping ramps.  Gate
      ``O4_TUNNEL_LOW_CONNECTORS``.
    """
    # ── IMPLIED CROSSING TUNNELS (user 2026-07-04) ────────────────────
    # A PUBLIC through-road or railway that crosses taxiway/runway
    # pavement cannot do so at grade — assume a tunnel under the
    # pavement even when OSM carries no tunnel tag.  The way is SPLIT at
    # the pavement-edge crossing points into approach + synthetic
    # ``tunnel=yes`` bore + approach pieces; everything downstream
    # (portal walks, ramps, retaining walls, twin-bore clustering, the
    # adjacent-road system veto) then treats the bore exactly like a
    # mapped tunnel, so ramps emit on either side of the pavement.
    # Service/residential roads are excluded — airport service roads
    # legitimately cross taxi routes at grade.
    low_connector_gaps: list = []
    if IMPLIED_CROSSING_TUNNELS:
        _IMPLIED_HW_TYPES = {
            "motorway", "trunk", "primary", "secondary", "tertiary",
            "motorway_link", "trunk_link", "primary_link",
        }
        # "apron" joined 2026-07-26 (owner ruling, KCLT Yorkmont Road):
        # an apron is load-bearing aircraft pavement — a public
        # tertiary+ road can no more run at grade beneath it than under
        # a taxiway.  ``_built_over_u`` below narrowed to buildings
        # accordingly: an apron-only mapped tunnel now bores + ramps
        # instead of silently degrading to ``building_passage``.
        _IMPLIED_CROSS_ROLES = (
            "runway", "runway_crossing", "primary_parallel",
            "secondary_parallel", "stub", "cross_connector", "junction",
            "apron")
        _IMPLIED_MIN_BORE_M = 6.0      # narrower = a sliver graze
        _IMPLIED_MAX_BORE_M = 500.0    # longer = through-airport road
        _IMPLIED_END_MARGIN_M = 2.0    # way must CROSS, not END inside
        # Only a near-COINCIDENT mapped tunnel suppresses an implied
        # bore (a duplicate line of the same physical feature).  Was
        # 40 m — but parallel carriageways/frontage roads within 35 m
        # now GROUP into one corridor (user 2026-07-04), so a mapped
        # motorway tunnel must not silently swallow the frontage
        # road's own crossing.
        _IMPLIED_MAPPED_NEAR_M = 6.0
        # Gate: derive mapped-tunnel breaks from OUR pavement too.
        _taxi_breaks = os.environ.get(
            "O4_TUNNEL_TAXI_BREAKS", "1") == "1"
        _low_connectors = (low_connector_max_gap_m > 0.0
                           and os.environ.get(
                               "O4_TUNNEL_LOW_CONNECTORS", "1") == "1")
        try:
            _cross_pav_u = unary_union(
                [s.polygon for s in layout.shapes
                 if s.polygon is not None and not s.polygon.is_empty
                 and s.role in _IMPLIED_CROSS_ROLES])
            if _cross_pav_u.is_empty:
                _cross_pav_u = None
        except _GEOM_EXC:
            _cross_pav_u = None
        # Built-over cover (buildings ONLY since 2026-07-26 — aprons
        # moved to ``_IMPLIED_CROSS_ROLES`` above): a mapped tunnel
        # under a BUILDING is a road built up and over — no trench, no
        # ramps (KDFW/KPHL terminal passages, which run under the
        # terminal buildings themselves).  A mapped tunnel under mere
        # grass/RESA (CYUL's runway-24-end underpass, KPHL's hill
        # bore) is a REAL trench and keeps its mapped portals when it
        # crosses no taxiway.
        try:
            _built_over_u = unary_union(
                [s.polygon for s in layout.shapes
                 if s.polygon is not None and not s.polygon.is_empty
                 and s.role in ("building",)])
            if _built_over_u.is_empty:
                _built_over_u = None
        except _GEOM_EXC:
            _built_over_u = None

        def _resplittable(_tags) -> bool:
            # A mapped ``tunnel=yes`` way of the public classes gets its
            # breaks re-derived from pavement like an unmarked way.
            return (_taxi_breaks
                    and _tags.get("tunnel") == "yes"
                    and (_tags.get("highway") in _IMPLIED_HW_TYPES
                         or _tags.get("railway") in RAIL_TUNNEL_TYPES))
        _mapped_tunnel_lines = []
        if _cross_pav_u is not None:
            for _wid, _nrefs, _tags in ways_r:
                if _tags.get("tunnel") not in TUNNEL_VALUES:
                    continue
                if _resplittable(_tags):
                    continue    # re-split below — must not self-suppress
                _pts = [nodes_m[n] for n in _nrefs if n in nodes_m]
                if len(_pts) >= 2:
                    try:
                        _mapped_tunnel_lines.append(LineString(_pts))
                    except _GEOM_EXC:
                        continue
        _excluded_early = excluded_way_ids or set()
        # CHAIN MERGE (owner ruling 2026-07-26): let the walk see roads,
        # not the mapper's segmentation — see _merge_eligible_chains.
        if (os.environ.get("O4_IMPLIED_TUNNEL_CHAINS", "1") == "1"
                and _cross_pav_u is not None):
            ways_r = _merge_eligible_chains(
                ways_r, _IMPLIED_HW_TYPES, _excluded_early)
        _n_implied = 0
        _n_level_crossings = 0
        _n_no_tag_evidence = 0
        # ── R4 TAG EVIDENCE (owner spec round4-othh-fixes 2026-08-10) ──
        # "Synthesis requires TAG EVIDENCE — the crossing way, or a way
        # its chain connects to within 100 m, carries ``tunnel=yes`` or
        # ``layer`` < 0.  A purely geometric crossing is never a
        # tunnel."  Measured at OTHH on 1.0.229: the S1 ramps
        # (25.2531, 51.6209) are engine-FABRICATED — untagged tertiary
        # ways crossing our pavement, with no OSM tunnel on their chain
        # (the nearest mapped bore is 73 m away and unconnected).  S4's
        # pair — untagged CONTINUATIONS of a mapped bore that share its
        # portal junction — still qualifies through the chain walk.
        # The index is built ONCE per airport, after the chain merge so
        # it indexes the ways the split loop actually walks.
        # Built LAZILY: an airport whose ways raise no candidate bore
        # never pays for the index at all.
        _ev_ways = ways_r
        _ev_state: list = []

        def _tag_evidence_ok(_wi9, _part9) -> bool:
            if not IMPLIED_TUNNEL_TAG_EVIDENCE:
                return True
            if not _ev_state:
                _ev_state.extend(
                    _tunnel_evidence_chain_index(_ev_ways, nodes_m))
            return _chain_tunnel_evidence(
                _wi9, _ev_state[0], _ev_state[1], _ev_ways, nodes_m,
                _part9, IMPLIED_TUNNEL_TAG_EVIDENCE_M)

        if _cross_pav_u is not None:
            _split_ways: list = []
            for _wi, (_wid, _nrefs, _tags) in enumerate(ways_r):
                _had_tunnel = _resplittable(_tags)
                _eligible = (
                    (_tags.get("tunnel") not in TUNNEL_VALUES
                     or _had_tunnel)
                    and not _tags.get("bridge")
                    and _wid not in _excluded_early
                    and (_tags.get("highway") in _IMPLIED_HW_TYPES
                         or _tags.get("railway") in RAIL_TUNNEL_TYPES))
                _present = ([(n, nodes_m[n]) for n in _nrefs
                             if n in nodes_m] if _eligible else [])
                if not _eligible or len(_present) < 2:
                    _split_ways.append((_wid, _nrefs, _tags))
                    continue
                try:
                    _line = LineString([p for (_n, p) in _present])
                    if not _line.intersects(_cross_pav_u):
                        if (_had_tunnel and _built_over_u is not None
                                and _line.intersects(_built_over_u)):
                            # Mapped tunnel crossing NO taxi/runway
                            # pavement but running under a BUILDING /
                            # apron pad = a road built up and over
                            # (KDFW terminals): no trench, no ramps —
                            # but ramp walks still must not route
                            # through it (user 2026-07-04).  A mapped
                            # tunnel under mere grass keeps its mapped
                            # portals (CYUL runway-24 end).
                            _ptags = dict(_tags)
                            _ptags["tunnel"] = "building_passage"
                            _split_ways.append((_wid, _nrefs, _ptags))
                        else:
                            _split_ways.append((_wid, _nrefs, _tags))
                        continue
                    _inter = _line.intersection(_cross_pav_u)
                except _GEOM_EXC:
                    _split_ways.append((_wid, _nrefs, _tags))
                    continue
                _parts = ([_inter] if _inter.geom_type == "LineString"
                          else [g for g in getattr(_inter, "geoms", ())
                                if g.geom_type == "LineString"])
                # At-grade level-crossing evidence on THIS way's nodes
                # (user 2026-07-16, EGPB/Gibraltar): the crossing node
                # itself (``aeroway=aircraft_crossing`` /
                # ``crossing:aircraft``) or the barrier gates that close
                # the road for aircraft movements.  Collected once per
                # way, tested per crossing segment below.
                _level_evidence: list = []   # (Point, is_crossing_tag)
                if node_tags and not _had_tunnel:
                    for _en, _ep in _present:
                        _ent = node_tags.get(_en)
                        if not _ent:
                            continue
                        if (_ent.get("aeroway") == "aircraft_crossing"
                                or "crossing:aircraft" in _ent):
                            _level_evidence.append((Point(_ep), True))
                        elif (_ent.get("barrier")
                                in LEVEL_CROSSING_BARRIER_VALUES):
                            _level_evidence.append((Point(_ep), False))
                _intervals: list = []
                for _part in _parts:
                    if not (_IMPLIED_MIN_BORE_M <= _part.length
                            <= _IMPLIED_MAX_BORE_M):
                        continue
                    if _level_evidence and not _had_tunnel:
                        _veto = False
                        for _epoint, _is_crossing_tag in _level_evidence:
                            _radius = (AIRCRAFT_CROSSING_VETO_DIST_M
                                       if _is_crossing_tag
                                       else LEVEL_CROSSING_GATE_VETO_DIST_M)
                            try:
                                if _part.distance(_epoint) <= _radius:
                                    _veto = True
                                    break
                            except _GEOM_EXC:
                                continue
                        if _veto:
                            _n_level_crossings += 1
                            continue
                    try:
                        _s1 = _line.project(Point(*_part.coords[0]))
                        _s2 = _line.project(Point(*_part.coords[-1]))
                    except _GEOM_EXC:
                        continue
                    if _s2 < _s1:
                        _s1, _s2 = _s2, _s1
                    # must CROSS the pavement (extend beyond both
                    # sides).  A previously-MAPPED tunnel is a KNOWN
                    # underpass — it may legitimately start/end right
                    # at (or under) the pavement, so it skips this.
                    if not _had_tunnel and (
                            _s1 < _IMPLIED_END_MARGIN_M
                            or _s2 > _line.length - _IMPLIED_END_MARGIN_M):
                        continue
                    # a mapped tunnel already models this underpass
                    if not _had_tunnel and any(
                            _part.distance(_tl) < _IMPLIED_MAPPED_NEAR_M
                            for _tl in _mapped_tunnel_lines):
                        continue
                    # R4 (owner 2026-08-10): a purely GEOMETRIC crossing
                    # is never a tunnel — the way, or a way its chain
                    # connects to within 100 m, must carry the tag.
                    if not _had_tunnel and not _tag_evidence_ok(
                            _wi, _part):
                        _n_no_tag_evidence += 1
                        continue
                    _intervals.append((_s1, _s2))
                if not _intervals:
                    if (_had_tunnel and _built_over_u is not None
                            and _line.intersects(_built_over_u)):
                        # Its only pavement contacts were slivers /
                        # over-long grazes and it runs under a
                        # building/apron — treat as built-over.
                        _ptags = dict(_tags)
                        _ptags["tunnel"] = "building_passage"
                        _split_ways.append((_wid, _nrefs, _ptags))
                    else:
                        _split_ways.append((_wid, _nrefs, _tags))
                    continue
                _intervals.sort()
                # The break lands TAXI_EDGE_BREAK_MARGIN_M outside the
                # pavement edge (user 2026-07-04): the portal's 1 m wall
                # cap then occupies exactly [edge, edge+1 m].
                _intervals = [
                    (max(0.05, _s1 - TAXI_EDGE_BREAK_MARGIN_M),
                     min(_line.length - 0.05,
                         _s2 + TAXI_EDGE_BREAK_MARGIN_M),
                     _s1, _s2)
                    for (_s1, _s2) in _intervals]
                # Merge overlapping bores, and — when the surface gap
                # between consecutive bores is too short for a ramp
                # pair to reach DEM and come back — merge ACROSS the
                # gap into one long bore, recording the gap for the
                # flat low-connector emit (user 2026-07-04: the area
                # between double parallel taxiways is all at the low
                # elevation).
                _merged: list = [list(_intervals[0])]
                for _iv in _intervals[1:]:
                    _prev = _merged[-1]
                    _gap = _iv[0] - _prev[1]
                    if _gap <= 0.0:
                        _prev[1] = max(_prev[1], _iv[1])
                        _prev[3] = max(_prev[3], _iv[3])
                    elif _low_connectors and _gap < low_connector_max_gap_m:
                        # The road cannot surface and return within this
                        # gap, so the bores merge either way.  The gap's
                        # VISIBLE form depends on its width (user
                        # 2026-07-10, SPJC big NW crossing): a narrow gap
                        # (KDFW double-parallel-taxiway median, 30-70 m)
                        # is dug open as a flat low connector; anything
                        # wider stays COVERED — no trench recorded, no
                        # mid-gap portals, ground bridged over the bore.
                        #
                        # RULING 2 (owner 2026-08-07, OTHH): a MAPPED
                        # bore's interior is roofed BY DEFINITION — the
                        # mapper drew one continuous tunnel, so a gap
                        # between two of OUR pavement crossings inside it
                        # is covered roof whatever its length, never an
                        # open cut.  (OTHH: 86.5 m and 39 m interior gaps
                        # of a mapped 810 m bore were dug open, ways
                        # -11724/-11728.)  The gap still MERGES below,
                        # exactly like a gap ≥ the open-cut cap; only the
                        # implied-bore path (KDFW) records it for
                        # excavation.
                        if (not _had_tunnel
                                and _gap
                                < TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M):
                            try:
                                _gline = substring(_line, _prev[3], _iv[2])
                            except _GEOM_EXC:
                                _gline = None
                            if (_gline is not None
                                    and _gline.geom_type == "LineString"
                                    and _gline.length > 1.0):
                                _gw = _carriageway_width_from_tags(
                                    _tags.get("highway") or "railway",
                                    _tags, 22.0)
                                low_connector_gaps.append((_gline, _gw))
                        _prev[1] = _iv[1]
                        _prev[3] = _iv[3]
                    else:
                        _merged.append(list(_iv))
                _intervals = [(_a, _b) for (_a, _b, _r1, _r2) in _merged]
                # MAPPED-END PRESERVATION (user 2026-07-10, SPJC big NW
                # tunnel): the re-split derives a mapped tunnel's breaks
                # from OUR pavement (KDFW mapper-break cleanup), which
                # plants portals at the pavement edges INSIDE the real
                # bore when the mapped tunnel extends far beyond the
                # crossing (SPJC: 1.27 km mapped trunk bores with the
                # crossings mid-way — ramps emitted inside the tunnel).
                # A mapped end stretch is genuine covered tunnel, not
                # mapper sloppiness: keep it BORE by clamping the
                # outermost interval to the way end, so the portal (and
                # the approach ramps walked beyond it) sit at the TRUE
                # mapped mouth.
                #
                # RULING 1 (owner 2026-08-07, OTHH): the clamp is
                # UNCONDITIONAL for a mapped way — the old length test
                # (only end stretches longer than the open-gap design cap
                # were preserved) let OTHH's 62 m mouth stretch fall
                # through, planting the portal 61 m INSIDE the bore and
                # stripping ``tunnel=yes`` off the covered mouth stretch,
                # which the ramp then excavated.  The portal now always
                # sits at s=0 / s=L of the mapped extent; the approach
                # ramp is walked on the SURFACE side of it (the portal
                # node is shared with the untagged continuation ways).
                # IMPLIED (un-tagged) ways keep the re-split cleanup
                # unchanged (KDFW-validated: portal cap at [pavement
                # edge, edge + 1 m]).
                if _had_tunnel and _intervals:
                    _intervals[0] = (0.05, _intervals[0][1])
                    _intervals[-1] = (_intervals[-1][0],
                                      _line.length - 0.05)
                # split the way: approach | bore | approach | bore | ...
                _arcs = [0.0]
                for _k in range(1, len(_present)):
                    _arcs.append(_arcs[-1] + math.hypot(
                        _present[_k][1][0] - _present[_k - 1][1][0],
                        _present[_k][1][1] - _present[_k - 1][1][1]))
                _pieces: list = []      # (nref list, is_bore)
                _cur: list = []
                _idx = 0
                _syn = 0
                for (_s1, _s2) in _intervals:
                    while _idx < len(_present) and _arcs[_idx] <= _s1 - 0.01:
                        _cur.append(_present[_idx][0])
                        _idx += 1
                    _pin = _line.interpolate(_s1)
                    _sid_in = f"IMP|{_wid}|{_syn}"
                    _syn += 1
                    nodes_m[_sid_in] = (_pin.x, _pin.y)
                    _cur.append(_sid_in)
                    if len(_cur) >= 2:
                        _pieces.append((_cur, False))
                    _bore = [_sid_in]
                    while _idx < len(_present) and _arcs[_idx] < _s2 - 0.01:
                        _bore.append(_present[_idx][0])
                        _idx += 1
                    _pout = _line.interpolate(_s2)
                    _sid_out = f"IMP|{_wid}|{_syn}"
                    _syn += 1
                    nodes_m[_sid_out] = (_pout.x, _pout.y)
                    _bore.append(_sid_out)
                    _pieces.append((_bore, True))
                    _cur = [_sid_out]
                while _idx < len(_present):
                    _cur.append(_present[_idx][0])
                    _idx += 1
                if len(_cur) >= 2:
                    _pieces.append((_cur, False))
                for _j, (_refs, _is_bore) in enumerate(_pieces):
                    _ptags = dict(_tags)
                    if _is_bore:
                        _ptags["tunnel"] = "yes"
                        _ptags["o4_implied_tunnel"] = "1"
                        _n_implied += 1
                    elif _had_tunnel:
                        # A re-split mapped tunnel's leftover pieces
                        # are surface approaches — drop the tunnel tag
                        # so portal walks can route along them.
                        _ptags.pop("tunnel", None)
                    _split_ways.append((f"{_wid}|IMP{_j}", _refs, _ptags))
            ways_r = _split_ways
        if _n_implied:
            try:
                UI.vprint(1,
                    f"  [pav-builder] implied {_n_implied} tunnel bore(s) "
                    f"under taxi/runway pavement (unmarked road/rail "
                    f"crossings).")
            except _GEOM_EXC:
                pass
        if _n_no_tag_evidence:
            try:
                UI.vprint(1,
                    f"  [pav-builder] declined {_n_no_tag_evidence} "
                    f"implied bore(s) — no tunnel/layer tag evidence on "
                    f"the crossing way or its chain within "
                    f"{IMPLIED_TUNNEL_TAG_EVIDENCE_M:.0f} m (R4).")
            except _GEOM_EXC:
                pass
        if _n_level_crossings:
            try:
                UI.vprint(1,
                    f"  [pav-builder] kept {_n_level_crossings} road/rail "
                    f"crossing(s) AT GRADE — OSM level-crossing evidence "
                    f"(aircraft-crossing node / barrier gates), no "
                    f"implied tunnel.")
            except _GEOM_EXC:
                pass
    return ways_r, low_connector_gaps


def _build_surface_way_indices(ways_r: list):
    """Index the road ways for surface-road walking.  Returns
    ``(way_by_id, node_to_ways)``.
    """
    # Build node-to-way and way-by-id indices for surface-road walking.
    way_by_id: dict[str, tuple[list[str], dict[str, str]]] = {}
    node_to_ways: dict[str, list[str]] = {}
    for wid, nrefs, tags in ways_r:
        way_by_id[wid] = (nrefs, tags)
        for n in nrefs:
            node_to_ways.setdefault(n, []).append(wid)
    return way_by_id, node_to_ways


# Helper: orient ``o_nrefs`` so it starts at ``anchor_nid`` and
# walks AWAY from ``anchor_nid``.  When the anchor is mid-way,
# picks the longer side.  Returns None if anchor isn't on the way.
def _orient_away(o_nrefs: list[str],
                 anchor_nid: str,
                 nodes_m: dict) -> list[str] | None:
    try:
        idx = o_nrefs.index(anchor_nid)
    except ValueError:
        return None
    forward = o_nrefs[idx:]
    backward = list(reversed(o_nrefs[:idx + 1]))
    if idx == 0:
        return forward
    if idx == len(o_nrefs) - 1:
        return backward
    # Mid-way: pick the longer leg.
    def _leg_len(refs: list[str]) -> float:
        return sum(
            math.hypot(
                nodes_m[refs[i + 1]][0] - nodes_m[refs[i]][0],
                nodes_m[refs[i + 1]][1] - nodes_m[refs[i]][1])
            for i in range(len(refs) - 1)
            if (refs[i] in nodes_m
                and refs[i + 1] in nodes_m))
    return forward if _leg_len(forward) >= _leg_len(backward) \
        else backward


def _deviation_filter(pts: list, tol_m: float,
                      min_segment_m: float) -> list:
    """R20-1: thin a plan polyline by DEVIATION, never by spacing.

    Douglas-Peucker at ``tol_m``: a vertex survives unless the retained
    chain already passes within ``tol_m`` of it, so the returned chain
    is within ``tol_m`` of EVERY input vertex by construction — which is
    the round's claim metric (max lateral offset emitted-vs-OSM).  The
    endpoints always survive.

    ``min_segment_m`` is the rounding-safe floor
    (``_TUNNEL_WALK_MIN_SEGMENT_M``): survivors closer together than it
    would carry a grade whose emit-rounding error eats the ramp's
    planning headroom, so they merge — the LATER one is dropped, except
    at the far end, where the endpoint is kept and its predecessor goes
    (the endpoint is the walk's grade-reach station and must stay
    exact).  A merge here moves the chain by less than ``min_segment_m``
    laterally in the worst case and by far less in practice: two
    vertices that close together on a road cannot subtend a turn.
    """
    if len(pts) < 3:
        return list(pts)

    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        ax, ay = pts[i0]
        bx, by = pts[i1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        worst_d = -1.0
        worst_k = -1
        for k in range(i0 + 1, i1):
            px, py = pts[k]
            if seg2 <= 1e-18:
                d = math.hypot(px - ax, py - ay)
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / seg2
                t = max(0.0, min(1.0, t))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > worst_d:
                worst_d, worst_k = d, k
        if worst_d > tol_m and worst_k > i0:
            keep[worst_k] = True
            stack.append((i0, worst_k))
            stack.append((worst_k, i1))
    out = [pts[k] for k in range(len(pts)) if keep[k]]

    if min_segment_m <= 0.0 or len(out) < 3:
        return out
    merged = [out[0]]
    for k in range(1, len(out) - 1):
        if math.hypot(out[k][0] - merged[-1][0],
                      out[k][1] - merged[-1][1]) >= min_segment_m:
            merged.append(out[k])
    last = out[-1]
    while (len(merged) >= 2
           and math.hypot(last[0] - merged[-1][0],
                          last[1] - merged[-1][1]) < min_segment_m):
        merged.pop()
    merged.append(last)
    return merged


# Helper: from a portal node, walk a chain of connecting non-
# tunnel surface roads OUTWARD for ``length_m`` metres.  When
# the current OSM way ends, follow the connected highway way
# whose first segment best continues the current direction
# (smallest turn angle) — keeps us on the main road through
# OSM-imposed splits at intersections instead of bailing into
# a side street.  Returns the walked path as a list of (x, y)
# points starting at the portal, or None if no valid surface
# way connects.
def _walk_surface(portal_nid: str,
                  tunnel_wid: str,
                  length_m: float,
                  nodes_m: dict,
                  way_by_id: dict,
                  node_to_ways: dict,
                  carriageway_width_m: float
                  ) -> list[tuple[float, float]] | None:
    if portal_nid not in nodes_m:
        return None
    # Pick the FIRST surface highway way leaving the portal.
    # When several candidates connect, prefer the one whose
    # first segment is most-aligned with the tunnel direction
    # (so divided-highway crossings don't turn into a service
    # road off the main carriageway).
    if tunnel_wid in way_by_id:
        tw_nrefs = way_by_id[tunnel_wid][0]
        t_oriented = _orient_away(tw_nrefs, portal_nid,
                                      nodes_m)
        if t_oriented and len(t_oriented) >= 2 \
                and t_oriented[1] in nodes_m:
            tp = nodes_m[portal_nid]
            tn = nodes_m[t_oriented[1]]
            tdx, tdy = tn[0] - tp[0], tn[1] - tp[1]
            tlen = math.hypot(tdx, tdy) or 1.0
            # Tunnel direction points INTO the tunnel; the
            # surface walk goes the OPPOSITE way.
            tunnel_outward_dir: tuple[float, float] | None = (
                -tdx / tlen, -tdy / tlen)
        else:
            tunnel_outward_dir = None
    else:
        tunnel_outward_dir = None

    first_way: str | None = None
    first_refs: list[str] | None = None
    best_align: float = -2.0
    for other_wid in node_to_ways.get(portal_nid, []):
        if other_wid == tunnel_wid:
            continue
        if other_wid not in way_by_id:
            continue
        o_nrefs, o_tags = way_by_id[other_wid]
        if o_tags.get("tunnel") in TUNNEL_VALUES:
            continue
        if not _tunnelable(o_tags):
            continue
        refs = _orient_away(o_nrefs, portal_nid, nodes_m)
        if refs is None or len(refs) < 2 \
                or refs[1] not in nodes_m:
            continue
        if tunnel_outward_dir is None:
            first_way, first_refs = other_wid, refs
            break
        cp = nodes_m[portal_nid]
        cn = nodes_m[refs[1]]
        cdx, cdy = cn[0] - cp[0], cn[1] - cp[1]
        clen = math.hypot(cdx, cdy) or 1.0
        align = (cdx * tunnel_outward_dir[0]
                 + cdy * tunnel_outward_dir[1]) / clen
        if align > best_align:
            best_align = align
            first_way, first_refs = other_wid, refs
    if first_refs is None or first_way is None:
        return None

    pts: list[tuple[float, float]] = []
    cums: list[float] = []
    cum = 0.0
    visited_ways = {tunnel_wid, first_way}
    current_refs = first_refs
    current_hw = way_by_id[first_way][1].get("highway")
    # Loop detection: a surface road that folds back on itself
    # (roundabout, hairpin) brings the walk back into the corridor
    # of an EARLIER segment.  Continuing would emit ramp polygons
    # overlapping the ramps already laid down (LMML SW Kirkop:
    # the walk looped a roundabout and the returning tail overlapped
    # its own start by 104 m² with a 3.8 m elevation step).  Stop
    # the walk when a new node lands within one corridor width of an
    # earlier node that is more than ``_loop_ignore_m`` back along
    # the path (the back-distance gate keeps gentle curves and
    # normal forward progress from tripping it).
    _loop_hit_m = carriageway_width_m
    _loop_ignore_m = max(2.0 * carriageway_width_m, 40.0)

    def _append_node(p: tuple[float, float]) -> bool:
        """Append ``p`` to ``pts``; truncate at ``length_m`` or
        where the path loops back on itself.  Returns True if the
        walk should stop."""
        nonlocal cum
        if not pts:
            pts.append(p)
            cums.append(0.0)
            return False
        seg_len = math.hypot(
            p[0] - pts[-1][0], p[1] - pts[-1][1])
        new_cum = cum + seg_len
        # Self-intersection (loop) check against non-recent points.
        # ``cums`` is monotonically increasing, so once the back-
        # distance drops below the ignore band the remaining points
        # are all recent — stop scanning.
        for i in range(len(pts)):
            if new_cum - cums[i] < _loop_ignore_m:
                break
            if math.hypot(p[0] - pts[i][0],
                          p[1] - pts[i][1]) < _loop_hit_m:
                return True
        if new_cum >= length_m:
            if seg_len > 0:
                t = (length_m - cum) / seg_len
                tx = pts[-1][0] + t * (p[0] - pts[-1][0])
                ty = pts[-1][1] + t * (p[1] - pts[-1][1])
                pts.append((tx, ty))
                cums.append(length_m)
            cum = length_m
            return True
        cum = new_cum
        pts.append(p)
        cums.append(cum)
        return False

    while True:
        stopped = False
        for n in current_refs:
            if n not in nodes_m:
                stopped = True
                break
            if _append_node(nodes_m[n]):
                return pts
        if stopped:
            break
        # Try to chain to a connected highway way at the end
        # of ``current_refs``.  Skip tunnels and ways already
        # visited; prefer same highway type, then most-straight
        # continuation (smallest turn angle).
        last_nid = current_refs[-1]
        if len(pts) < 2:
            break
        end_dir_x = pts[-1][0] - pts[-2][0]
        end_dir_y = pts[-1][1] - pts[-2][1]
        ed_len = math.hypot(end_dir_x, end_dir_y) or 1.0
        end_dir = (end_dir_x / ed_len, end_dir_y / ed_len)
        best_score = -2.0
        best_wid: str | None = None
        best_refs: list[str] | None = None
        for cand_wid in node_to_ways.get(last_nid, []):
            if cand_wid in visited_ways:
                continue
            if cand_wid not in way_by_id:
                continue
            c_nrefs, c_tags = way_by_id[cand_wid]
            if c_tags.get("tunnel") in TUNNEL_VALUES:
                continue
            if c_tags.get("highway") not in HW_TUNNEL_TYPES:
                continue
            refs = _orient_away(c_nrefs, last_nid, nodes_m)
            if refs is None or len(refs) < 2 \
                    or refs[1] not in nodes_m:
                continue
            first_p = nodes_m[refs[1]]
            last_p = nodes_m[last_nid]
            fdx = first_p[0] - last_p[0]
            fdy = first_p[1] - last_p[1]
            fl = math.hypot(fdx, fdy) or 1.0
            align = (fdx * end_dir[0] + fdy * end_dir[1]) / fl
            same_hw = 1 if c_tags.get("highway") == current_hw else 0
            # Tie-break: same highway type beats alignment by
            # ~0.1 (~25° turn), so we follow trunk → trunk over
            # trunk → service even when both are similar angle.
            score = align + 0.1 * same_hw
            if score > best_score:
                best_score = score
                best_wid = cand_wid
                best_refs = refs
        if best_refs is None or best_wid is None:
            break
        visited_ways.add(best_wid)
        current_hw = way_by_id[best_wid][1].get("highway")
        # Skip refs[0]; it's the connecting node already in pts.
        current_refs = best_refs[1:]

    if len(pts) >= 2:
        return pts
    return None


def _build_adjacent_road_index(ways_r: list, nodes_m: dict,
                               skip_if_adjacent_road: bool):
    """Build the other-road line index + STRtree and the
    all-tunnel node set for the adjacent-road veto.  Returns
    ``(other_road_lines, other_road_tree, tunnel_all_nodes)``.
    """
    # Adjacent-road skip (user 2026-06-12, LMML): tunnels that run
    # under / alongside OTHER roads sit in a dense interchange where the
    # surface walk traces a tangle of parallel carriageways, slip roads
    # and roundabouts, and the ramps overlap.  Rather than model that,
    # skip ramp emission for a tunnel whose line is CROSSED by — or runs
    # within ``adjacent_road_dist_m`` of — another road.  The "other
    # road" set excludes ``highway=service`` (minor aisles/driveways),
    # other tunnels (a divided highway's own clustered carriageway), and
    # — per tunnel, below — any way sharing a node with it (the surface
    # continuation the ramp is meant to follow).  This skips all 6 LMML
    # tunnels and keeps SPJC's user-approved tunnels (crossed only by
    # service roads; parallel carriageway > dist away).
    _other_road_lines: list = []   # (LineString, frozenset(nodes), wid)
    _other_road_tree = None
    # Every node of ANY tunnel-tagged way (any tunnel value): a bore's
    # covered middle sections may carry different tags than the portal
    # candidates, and the twin continuation shares nodes with THOSE —
    # a per-candidate node set misses them (CYUL).
    _tunnel_all_nodes: set = set()
    if skip_if_adjacent_road:
        for _w2, _n2, _t2 in ways_r:
            if _t2.get("tunnel") in TUNNEL_VALUES:
                _tunnel_all_nodes.update(_n2)
        try:
            for _w2, _n2, _t2 in ways_r:
                if _t2.get("highway") is None:
                    continue
                if _t2.get("highway") == "service":
                    continue
                if _t2.get("tunnel") in TUNNEL_VALUES:
                    continue
                _pts2 = [nodes_m[n] for n in _n2 if n in nodes_m]
                if len(_pts2) < 2:
                    continue
                try:
                    _other_road_lines.append(
                        (LineString(_pts2), frozenset(_n2), _w2))
                except _GEOM_EXC:
                    continue
            if _other_road_lines:
                _other_road_tree = STRtree(
                    [ln for ln, _, _ in _other_road_lines])
        except _GEOM_EXC:
            _other_road_tree = None
    return _other_road_lines, _other_road_tree, _tunnel_all_nodes


def _tunnel_has_adjacent_road(tw_id2, t_nrefs2, system_nodes,
                              nodes_m: dict,
                              adjacent_road_dist_m: float,
                              other_road_lines: list,
                              other_road_tree,
                              parent_nodes: set | None = None,
                              detail_out: dict | None = None) -> bool:
    """True when the tunnel way is crossed by — or runs within
    ``adjacent_road_dist_m`` of — a foreign (non-service) road;
    see the adjacent-road skip comment in
    ``_build_adjacent_road_index``.

    ``parent_nodes``: every node of the candidate's ORIGINAL
    (pre-re-split) way.  The share-a-node exemption must evaluate at
    that scope — the re-split moves a way's original end nodes into
    its approach pieces, so a bore clamped to the mapped tunnel end
    no longer shares a node with the surface continuation it hands
    off to, and the veto read the continuation as a foreign road at
    0 m (SPJC true-mouth clamp, 2026-07-10).

    ``detail_out`` (§T3.1) receives the blocking neighbour's
    ``{"blocked_by", "crosses", "distance_m"}`` — the discriminator the
    system propagation now reads.  A CROSSING neighbour always wins the
    record (the scan does not stop at the first mere neighbour), because
    a NON-crossing veto stands for the candidate itself but never
    propagates: "a road merely near a candidate" is not an interchange
    tangle.
    """
    if other_road_tree is None:
        return False
    _pts = [nodes_m[n] for n in t_nrefs2 if n in nodes_m]
    if len(_pts) < 2:
        return False
    try:
        _tline = LineString(_pts)
        _buf = _tline.buffer(adjacent_road_dist_m)
    except _GEOM_EXC:
        return False
    _tnodes = set(t_nrefs2) | (parent_nodes or set())
    _hit = False
    for _qi in other_road_tree.query(_buf):
        _oline, _onodes, _owid = other_road_lines[int(_qi)]
        if _owid == tw_id2 or (_tnodes & _onodes):
            continue
        try:
            _crosses = _tline.crosses(_oline)
            if not _crosses and _tline.distance(_oline) \
                    >= adjacent_road_dist_m:
                continue
            # Parallel continuation of a twin bore in THIS way's own
            # underpass system: not a veto (crossing roads always
            # veto; a continuation of a FOREIGN tunnel still vetoes —
            # exempting those half-emitted the LMML tangle).
            if (not _crosses and system_nodes is not None
                    and (_onodes & system_nodes)):
                continue
            if detail_out is not None and not (
                    _hit and not _crosses):
                detail_out.update({
                    "blocked_by": _owid,
                    "crosses": bool(_crosses),
                    "distance_m": round(
                        float(_tline.distance(_oline)), 2),
                })
            if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                _mx, _my = _pts[len(_pts) // 2]
                print(f"    [tunnel-skip] way {tw_id2} blocked by "
                      f"road {_owid} (crosses={_crosses}, "
                      f"d={_tline.distance(_oline):.0f}m) "
                      f"mid local ({_mx:.0f},{_my:.0f})")
            _hit = True
            # A CROSSING verdict is final; a mere neighbour keeps
            # scanning in case a crossing road follows it (the record
            # decides system propagation, so it may not be first-wins).
            if _crosses or detail_out is None:
                return True
        except _GEOM_EXC:
            continue
    return _hit


def _compute_tunnel_system_veto(
        ways_r: list, nodes_m: dict, excluded: set,
        adjacent_road_dist_m: float, skip_if_adjacent_road: bool,
        other_road_lines: list, other_road_tree,
        tunnel_all_nodes: set,
        airside_gate_union=None, own_bore_cover_union=None,
        veto_detail: dict | None = None) -> dict:
    """Group tunnel candidates into systems by proximity and
    propagate the adjacent-road veto across each system.
    Returns the per-way veto map.

    §T3.1 SCOPES the veto (``O4_TUNNEL_VETO_SCOPED``, default ON).  Two
    changes, both narrowings of a rule written for URBAN INTERCHANGES:

    * AN AIRPORT'S OWN BORE IS NEVER VETOED BY ITS OWN SERVICE ROADS.
      A candidate whose portal (either end) lies inside
      ``airside_gate_union``, or whose span passes under
      ``own_bore_cover_union`` (runway / apron / taxiway pavement —
      :data:`_TUNNEL_OWN_BORE_COVER_ROLES`), is EXEMPT: it is the very
      thing this machinery exists to model.  Its raw verdict is forced
      to False, so it neither skips nor drags its system down.
    * SYSTEM PROPAGATION IS FOR CROSSINGS.  Only a raw veto raised by a
      road that actually CROSSES the candidate spreads to the system;
      a merely-near neighbour (``crosses=False``, ``d>0``) vetoes its
      own way and no other.  The LMML tangle is crossings, so it stays
      out whole; a lone service road running past one LEMD bore no
      longer kills 37 ways.

    ``veto_detail`` receives one record per candidate (way id → the
    blocking neighbour, whether it crossed, the distance, whether the
    way was exempt and which evidence exempted it) — §T3.2's recorded
    refusal, published to the sidecar by the caller.
    """
    # ── SYSTEM-LEVEL veto propagation (user 2026-07-04) ──────────────
    # The per-way twin-bore exemption alone half-emits an interchange:
    # at LMML the parallel bores of a tangle were exempted while their
    # CROSSING mates stayed vetoed, and the emitted ramps overlapped the
    # vetoed roads (baseline 0 → 8 vertex + 25 mid-edge steps,
    # measured).  Group tunnel candidates into SYSTEMS by geometric
    # proximity (twin carriageways never share nodes) and veto ALL
    # members when ANY member is vetoed — a clean divided-highway
    # underpass (CYUL runway-24 end: parallel twins only, no crossing
    # road) emits whole, an interchange tangle stays out whole.
    _system_veto: dict = {}      # tw_id -> True (skip) / False (emit)
    if skip_if_adjacent_road:
        _cands = []              # (tw_id, t_nrefs, LineString)
        for _tw, _tn, _tt in ways_r:
            if _tt.get("tunnel") not in PORTAL_TUNNEL_VALUES:
                continue
            if not _tunnelable(_tt):
                continue
            if _tw in excluded or len(_tn) < 2:
                continue
            _p = [nodes_m[nn] for nn in _tn if nn in nodes_m]
            if len(_p) < 2:
                continue
            try:
                _cands.append((_tw, _tn, LineString(_p)))
            except _GEOM_EXC:
                continue
        parent = list(range(len(_cands)))

        def _find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for a in range(len(_cands)):
            for b in range(a + 1, len(_cands)):
                try:
                    if _cands[a][2].distance(_cands[b][2]) \
                            < adjacent_road_dist_m * 1.5:
                        ra, rb = _find(a), _find(b)
                        if ra != rb:
                            parent[rb] = ra
                except _GEOM_EXC:
                    continue
        _sys_bad: dict = {}
        # Node sets of the candidates' ORIGINAL ways (the re-split
        # appends pieces as ``<parent>|IMP<j>``) — the share-a-node
        # exemption evaluates at whole-original-way scope, see
        # ``_tunnel_has_adjacent_road``.
        _parent_nodes: dict = {}
        for _tw9, _tn9, _tt9 in ways_r:
            _pid9 = _tw9.split("|IMP", 1)[0]
            _parent_nodes.setdefault(_pid9, set()).update(_tn9)
        _scoped = _tunnel_veto_scoped_on()
        _details: list[dict] = []
        _raw: list[bool] = []
        for k in range(len(_cands)):
            _d: dict = {}
            _rk = _tunnel_has_adjacent_road(
                _cands[k][0], _cands[k][1], tunnel_all_nodes,
                nodes_m, adjacent_road_dist_m,
                other_road_lines, other_road_tree,
                parent_nodes=_parent_nodes.get(
                    _cands[k][0].split("|IMP", 1)[0]),
                detail_out=_d if _scoped else None)
            _details.append(_d)
            _raw.append(bool(_rk))
        # ── §T3.1 (a): THE AIRPORT'S OWN BORES ────────────────────────
        _exempt = [False] * len(_cands)
        if _scoped:
            for k, (_tw, _tn, _ln) in enumerate(_cands):
                _why = _own_bore_exemption(
                    _ln, airside_gate_union, own_bore_cover_union)
                if _why is None:
                    continue
                _exempt[k] = True
                _details[k]["exempt"] = _why
                if _raw[k]:
                    _details[k]["exempted_veto"] = True
                _raw[k] = False
        for k in range(len(_cands)):
            r = _find(k)
            # ── §T3.1 (b): ONLY CROSSINGS PROPAGATE ───────────────────
            _propagates = _raw[k] and (
                not _scoped
                or bool(_details[k].get("crosses")))
            _sys_bad[r] = _sys_bad.get(r, False) or _propagates
        for k, (_tw, _tn, _ln) in enumerate(_cands):
            _vetoed = bool(_sys_bad[_find(k)] or _raw[k])
            _system_veto[_tw] = _vetoed
            if veto_detail is not None:
                _rec = dict(_details[k])
                _rec["raw_veto"] = _raw[k]
                _rec["system_veto"] = bool(_sys_bad[_find(k)])
                _rec["vetoed"] = _vetoed
                veto_detail[_tw] = _rec
            if (not _vetoed
                    and os.environ.get("O4_TUNNEL_DEBUG") == "1"):
                _mx, _my = list(_ln.coords)[len(list(_ln.coords)) // 2]
                print(f"    [tunnel-emit] way {_tw} len={_ln.length:.0f}m "
                      f"raw_veto={_raw[k]} exempt={_exempt[k]} "
                      f"mid local ({_mx:.0f},{_my:.0f})")
    return _system_veto


def _own_bore_exemption(line, airside_gate_union,
                        own_bore_cover_union) -> str | None:
    """§T3.1: WHY this candidate is the airport's own bore, or ``None``.

    ``"portal_in_airside_gate"`` when either end lies inside the airside
    gate union; ``"covered_by_airside_pavement"`` when the span passes
    under runway / apron / taxiway pavement.  The order is the ruling's:
    a portal inside the gate is the stronger evidence, so it is named
    first when both hold.
    """
    if line is None:
        return None
    try:
        _coords = list(line.coords)
    except _GEOM_EXC:                                    # pragma: no cover
        return None
    if airside_gate_union is not None and _coords:
        try:
            for _end in (_coords[0], _coords[-1]):
                if airside_gate_union.intersects(Point(_end)):
                    return "portal_in_airside_gate"
        except _GEOM_EXC:                                # pragma: no cover
            pass
    if own_bore_cover_union is not None:
        try:
            if line.intersects(own_bore_cover_union):
                return "covered_by_airside_pavement"
        except _GEOM_EXC:                                # pragma: no cover
            pass
    return None


def _gather_portal_walks(
        ways_r: list, nodes_m: dict, way_by_id: dict,
        node_to_ways: dict, excluded: set, system_veto: dict,
        big_way_ids: set, airside_gate_union,
        max_boundary_dist_m: float, arm_walk_max_m: float,
        carriageway_width_m: float, airport_elevation_at,
        meters_to_lat_lon, dem, tile_lat: int, tile_lon: int,
        tunnel_depth_m: float, plan_grade: float,
        ramp_min_length_m: float,
        building_union=None, pavement_union=None,
        transit_union=None,
        passthrough_findings: list | None = None,
        veto_detail: dict | None = None,
        dem_cut_provenance: tuple | None = None) -> list:
    """Walk every qualifying tunnel portal's surface approach
    and collect the per-portal ramp data (twin-rail merge, the
    per-portal gates, walk merge / densify / grade truncation).

    ``building_union`` / ``pavement_union`` are the ``ROLE_BUILDING``
    footprint union and the airside-pavement union; under R10-1/A6 they
    are the COVER EVIDENCE the admission predicate reads (A1 recorded
    them but forbade reading them, which cost OTHH all 8 of its bores).
    ``transit_union`` is the AIRCRAFT-TRANSIT pavement union
    (``_TUNNEL_PROTECTED_TRANSIT_ROLES`` — the taxiway family R14-2/A-3
    protects outright).  R20-2b stops every run at it: a ramp may not be
    laid across pavement an aircraft cannot detour around, and the run
    that could reach one is exactly the run R20-2 made possible.

    ``passthrough_findings`` collects the refusal records the caller
    publishes on the layout.
    """
    # Collect portal data: (portal_node_id, tunnel_wid, walk_pts,
    # hw_type, apt_elev_at_portal, dem_at_far_end, is_new_candidate,
    # carriageway_width_m — from the way's own ``width=`` / ``lanes=``
    # tags when mapped, else the per-type table, dem_cut_detected,
    # mouth_grade_m, bore_inward_pts, deck_reference_m — the last four
    # feed the DEM-cut light-touch mode, see TUNNEL_DEM_CUT_MIN_DROP_M;
    # then inner_deck_m and, at index 13, bore_floor_m — the floor the
    # run was SIZED against, which R20-2b makes the floor the chain is
    # EMITTED from too).
    portal_data: list[tuple] = []
    # Rail tunnel lines, for the TWIN-corridor pairing below (user
    # 2026-07-04, KCLT: two parallel ``railway=rail`` tracks are one
    # double-track corridor — one wide bore, not two overlapping ones).
    _rail_tunnel_lines: dict = {}
    for _rw_id, _rw_refs, _rw_tags in ways_r:
        if (_rw_tags.get("tunnel") in PORTAL_TUNNEL_VALUES
                and _rw_tags.get("highway") is None
                and _rw_tags.get("railway") in RAIL_TUNNEL_TYPES):
            _rw_pts = [nodes_m[nn] for nn in _rw_refs if nn in nodes_m]
            if len(_rw_pts) >= 2:
                try:
                    _rail_tunnel_lines[_rw_id] = LineString(_rw_pts)
                except _GEOM_EXC:
                    continue

    _n_adj_skip = 0
    _cover_fraction: dict = {}

    def _cover_fractions(way_id, way_refs) -> tuple:
        """``(f_building, f_airside_pavement)`` for the way's covered
        stretch — R10-1/A6's admission evidence.

        WHAT COVERS THE BORE is the question a bare-earth DEM cannot
        answer: it carries no cut under either a terminal or an apron,
        but a road under a BUILDING is at grade (the building is the
        deck) while a road under APRON is a bore (the pavement is the
        deck).  Measured per unit of way length, cached per way — both
        portals of a way read the same cover.
        """
        if way_id in _cover_fraction:
            return _cover_fraction[way_id]
        _fb = _fp = None
        try:
            _pts = [nodes_m[_n] for _n in way_refs if _n in nodes_m]
            if len(_pts) >= 2:
                _line = LineString(_pts)
                if _line.length > 0.0:
                    # An ABSENT union is zero cover, not unknown cover:
                    # an airport with no mapped buildings covers nothing
                    # with buildings.  Returning None there would make
                    # the A6 disjunct unreachable on exactly those
                    # airports.
                    _fb = (0.0 if building_union is None else round(
                        _line.intersection(building_union).length
                        / _line.length, 3))
                    _fp = (0.0 if pavement_union is None else round(
                        _line.intersection(pavement_union).length
                        / _line.length, 3))
        except _GEOM_EXC:
            _fb = _fp = None
        _cover_fraction[way_id] = (_fb, _fp)
        return (_fb, _fp)

    for tw_id, t_nrefs, t_tags in ways_r:
        if t_tags.get("tunnel") not in PORTAL_TUNNEL_VALUES:
            continue
        hw = t_tags.get("highway")
        if not _tunnelable(t_tags):
            continue
        if hw is None and t_tags.get("railway") in RAIL_TUNNEL_TYPES:
            # Pseudo-type so the width table can size rail bores
            # (10 m double-track vs the 22 m road default).  Never in
            # HW_TUNNEL_TYPES, so rail stays NEW-class for the gates.
            hw = "railway"
            _my_rail = _rail_tunnel_lines.get(tw_id)
            if _my_rail is not None:
                _twins = sorted(
                    _oid for _oid, _ol in _rail_tunnel_lines.items()
                    if _oid != tw_id
                    and _ol.distance(_my_rail) < TWIN_RAIL_NEAR_M)
                if _twins:
                    # Canonical member (smallest id) carries the ONE
                    # wide corridor bore; the twin's portals are
                    # suppressed entirely.
                    if str(tw_id) > min(str(tw_id),
                                        *[str(t) for t in _twins]):
                        if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                            print(f"    [tunnel-drop] way {tw_id}: "
                                  f"rail twin of {min(_twins)}")
                        continue
                    hw = "railway_twin"
        # OLD candidates (big_roads + highway type — the only ways the
        # emitter saw before 2026-06-12) keep the original behaviour
        # verbatim: no new gates (SPJC's user-approved tunnels emit
        # bit-identically).  NEW candidates (small_roads bores, rail)
        # carry the gates below — they widened the input enough to
        # surface the dead-boundary-gate strays at KPHL.
        _is_new_cand = not (tw_id in big_way_ids
                            and hw in HW_TUNNEL_TYPES)
        # Effective carriageway width: the way's own ``width=`` /
        # ``lanes=`` measurements beat the per-type table (user
        # 2026-07-16, EGPB).  Computed HERE — the only place the way's
        # tags are in hand — and carried through ``portal_data`` for
        # the cluster emit.
        way_carriage_w = _carriageway_width_from_tags(
            hw, t_tags, carriageway_width_m)
        if len(t_nrefs) < 2:
            continue
        # Skip OSM way IDs already handled by the through-
        # airport depressed-road emit (which produces a single
        # uniform depression instead of per-bridge ramps).
        if tw_id in excluded:
            continue
        # Skip tunnels running under / alongside other roads — their
        # surface walk traces a dense interchange whose ramps overlap
        # (user 2026-06-12, LMML).  Both portals are skipped.  The
        # verdict is SYSTEM-level (``_system_veto`` above): a clean
        # divided-highway underpass emits whole, a tangle stays out
        # whole (user 2026-07-04, CYUL runway-24 end).
        if system_veto.get(tw_id, False):
            _n_adj_skip += 1
            # NAME THE VETOED WAY (plan item W4a, owner 2026-07-31: the
            # 8th OTHH tunnel "should be one cutout that exposes the
            # whole below grade area").  The aggregate count below says
            # only THAT something was skipped — it cannot be flown to,
            # measured, or matched against the pack, so the ruling had
            # nowhere to land.  Verbosity 1 because a silent skip is
            # this project's classic failure mode.  Reports the way's
            # own centroid and end-to-end extent in metres.
            #
            # §T3.2: VERBOSITY 0, AND RECORDED.  A refusal recorded and
            # thrown away is the class this campaign exists to kill — so
            # the line prints at the default verbosity and the finding
            # joins ``layout.tunnel_passthrough_findings``, which the
            # caller publishes to the sidecar as ``tunnel_vetoes``.
            _vd = dict((veto_detail or {}).get(tw_id) or {})
            try:
                _veto_pts = [nodes_m[_nid] for _nid in t_nrefs
                             if _nid in nodes_m]
                if _veto_pts:
                    _veto_x = sum(p[0] for p in _veto_pts) / len(_veto_pts)
                    _veto_y = sum(p[1] for p in _veto_pts) / len(_veto_pts)
                    _veto_span = math.hypot(
                        _veto_pts[-1][0] - _veto_pts[0][0],
                        _veto_pts[-1][1] - _veto_pts[0][1])
                    _veto_lat, _veto_lon = meters_to_lat_lon(
                        _veto_x, _veto_y)
                    UI.vprint(
                        0,
                        f"  [pav-builder] tunnel way {tw_id} "
                        f"({hw or t_tags.get('railway') or '?'}) VETOED — "
                        f"adjacent/crossing road; {len(t_nrefs)} node(s), "
                        f"{_veto_span:.0f} m end-to-end, centre "
                        f"{_veto_lat:.6f},{_veto_lon:.6f}")
                    if passthrough_findings is not None:
                        passthrough_findings.append({
                            "way_id": tw_id,
                            "lat": round(_veto_lat, 7),
                            "lon": round(_veto_lon, 7),
                            "x_m": round(_veto_x, 1),
                            "y_m": round(_veto_y, 1),
                            "highway": hw or t_tags.get("railway"),
                            "tunnel": t_tags.get("tunnel"),
                            "node_count": len(t_nrefs),
                            "span_m": round(_veto_span, 1),
                            "admitted_by": None,
                            "refused_because": "adjacent_road_veto",
                            "veto": _vd,
                        })
            except (KeyError, IndexError, ZeroDivisionError, _GEOM_EXC):
                pass
            continue
        for portal_idx in (0, len(t_nrefs) - 1):
            portal_nid = t_nrefs[portal_idx]
            if portal_nid not in nodes_m:
                if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                    print(f"    [tunnel-drop] way {tw_id}: portal node "
                          f"{portal_nid} not in nodes_m")
                continue
            # Airport-proximity gate against the AIRSIDE PAVEMENT
            # union (user 2026-06-12, KPHL; ALL candidate classes
            # 2026-07-04): distant urban strays are skipped by their
            # distance to the airport's PAVEMENT.  The old
            # ROLE_BOUNDARY-distance gate is RETIRED: since the at-DEM
            # ribbon skip (2026-07-03) only a few ribbon scraps
            # survive, and at KDFW the 3 leftovers sat >1 km from the
            # central underpass corridor — the gate silently dropped
            # every portal of a 5x7 km airport's main tunnels.  The
            # pavement union always exists here and scales with the
            # airport.
            if airside_gate_union is not None:
                _ppx, _ppy = nodes_m[portal_nid]
                try:
                    if airside_gate_union.distance(
                            Point(_ppx, _ppy)) > max_boundary_dist_m:
                        if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                            print(f"    [tunnel-drop] way {tw_id} portal "
                                  f"({_ppx:.0f},{_ppy:.0f}): "
                                  f"{airside_gate_union.distance(Point(_ppx, _ppy)):.0f} m "
                                  f"from airside pavement")
                        continue
                except _GEOM_EXC:
                    pass
            walk = _walk_surface(portal_nid, tw_id, arm_walk_max_m,
                                 nodes_m, way_by_id, node_to_ways,
                                 way_carriage_w)
            if walk is None or len(walk) < 2:
                if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                    _px, _py = nodes_m[portal_nid]
                    print(f"    [tunnel-drop] way {tw_id} portal "
                          f"({_px:.0f},{_py:.0f}): no surface walk")
                continue
            # ── R20-1: CURVATURE SURVIVES THE WALK ────────────────
            # What stood here was a 15 m SPACING merge: it deleted a
            # vertex for being CLOSE to its neighbour, with no reference
            # to whether the road TURNED there.  At the owner's KCLT
            # portal it deleted three of the surface walk's seven OSM
            # nodes — node -75937 among them, 1.86 m off the chord the
            # merge left behind — and the densify below only subdivides
            # the SURVIVORS' chords, so nothing came back: the road's
            # bend was gone from the plan geometry before ``_emit_chain``
            # (faithful, miters every vertex it is given) ever saw it.
            #
            # The filter is now a DEVIATION filter: a vertex is dropped
            # only where the retained chain already passes within
            # ``_TUNNEL_WALK_DEVIATION_TOL_M`` of it, so the emitted
            # centreline is within that tolerance of the OSM way at
            # EVERY node, however tightly the nodes are spaced.
            #
            # THE ALTITUDE-ROUNDING RATIONALE THE SPACING MERGE CARRIED
            # IS KEPT — and is now derived from the two constants that
            # actually set it (see ``_TUNNEL_WALK_MIN_SEGMENT_M``): the
            # emitted grid is 0.01 m, not the 0.1 m the old comment
            # sized 15 m against, so 2 m of segment already holds the
            # worst-case rounding error inside
            # ``TUNNEL_RAMP_GRADE_SAFETY_MARGIN``.  The filter enforces
            # that floor on its survivors, so no ramp quad is emitted
            # shorter than the rounding budget allows.
            walk = _deviation_filter(walk, _TUNNEL_WALK_DEVIATION_TOL_M,
                                     _TUNNEL_WALK_MIN_SEGMENT_M)
            if len(walk) < 2:
                continue
            # Densify long segments so the visible ramp tracks the
            # road with multiple sloped pieces — user 2026-05-03
            # ("SW tunnel only has one ramp segment, should be
            # multiple following the road up to DEM elevation").
            # Sparse OSM ways often have ~150-200 m gaps between
            # nodes; without densification a 200 m approach renders
            # as a single straight ramp.  Target ~50 m segments.
            # Use ceil so segments never exceed ``target_seg_m``;
            # ``round`` would leave a 72 m gap as a single segment
            # (round(72/50) == 1) and the user noticed those single-
            # segment ramps don't track the road's grade closely.
            target_seg_m = 50.0
            densified: list[tuple[float, float]] = [walk[0]]
            for k in range(1, len(walk)):
                px, py = densified[-1]
                qx, qy = walk[k]
                d = math.hypot(qx - px, qy - py)
                n_sub = max(1, math.ceil(d / target_seg_m))
                for s in range(1, n_sub + 1):
                    t = s / n_sub
                    densified.append(
                        (px + t * (qx - px), py + t * (qy - py)))
            walk = densified
            portal_xy = walk[0]
            apt_elev = airport_elevation_at(*portal_xy)
            if apt_elev is None:
                if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                    print(f"    [tunnel-drop] way {tw_id} portal "
                          f"({portal_xy[0]:.0f},{portal_xy[1]:.0f}): "
                          f"no airport elevation")
                continue
            # ── DEM-CUT DETECTION (user 2026-07-17, EGGW) ─────────
            # With a lidar elevation inset the bare-earth DEM already
            # carries the descending approach cut; when it does, the
            # cluster emit switches to the light-touch mode (face cap
            # + short mouth plate + roof cover, NO synthetic ramps or
            # wall chains — user: "we don't want a tunnel ramp
            # running around the entire parking garage").
            #
            # The signal is LOCAL RELIEF ACROSS THE ROAD — the trench
            # floor on the walk versus the deck BESIDE it at the same
            # station — never an absolute drop against ``apt_elev``:
            # ★``_airport_elevation_at`` falls back to the DEM at the
            # portal point when no boundary node is near (mid-field
            # tunnels), which samples the trench floor itself and
            # reads "no drop"; ★an absolute test against surrounding
            # ground also false-fires on any hillside bore whose DEM
            # legitimately has NO cut (KPHL class) and which still
            # needs the synthetic ramp.  ``mouth_grade`` = the DEM's
            # own road grade near the face (minimum inside the mouth
            # window — minimum, not first-sample, because smoothing
            # mixes the face pixels with the deck above).
            # ``deck_reference`` = the highest cross-road sample near
            # the portal: the grade the face cap and roof cover hold.
            # Fields ride at the END of the portal tuple (indices
            # 8-11) so every existing positional consumer (≤ 7) is
            # untouched.
            def _dem_at_local(px: float, py: float) -> float | None:
                try:
                    _plat, _plon = meters_to_lat_lon(px, py)
                    _value = _sample_dem(
                        dem, tile_lat, tile_lon, _plat, _plon)
                except _GEOM_EXC:
                    return None
                return None if _value is None else float(_value)

            _half_road = 0.5 * way_carriage_w
            _mouth_min: float | None = None
            _deck_reference: float | None = None
            _trench_depths: list[float] = []
            _cum2 = 0.0
            for i in range(len(walk)):
                if i > 0:
                    _cum2 += math.hypot(
                        walk[i][0] - walk[i - 1][0],
                        walk[i][1] - walk[i - 1][1])
                if _cum2 > TUNNEL_DEM_CUT_WINDOW_M:
                    break
                if i + 1 < len(walk):
                    _sdx = walk[i + 1][0] - walk[i][0]
                    _sdy = walk[i + 1][1] - walk[i][1]
                else:
                    _sdx = walk[i][0] - walk[i - 1][0]
                    _sdy = walk[i][1] - walk[i - 1][1]
                _slen = math.hypot(_sdx, _sdy) or 1.0
                _perp = (-_sdy / _slen, _sdx / _slen)
                _centre = _dem_at_local(*walk[i])
                if _centre is None:
                    continue
                _side_best: float | None = None
                for _offset in (_half_road + 6.0, _half_road + 15.0):
                    for _sign in (+1.0, -1.0):
                        _side = _dem_at_local(
                            walk[i][0] + _perp[0] * _offset * _sign,
                            walk[i][1] + _perp[1] * _offset * _sign)
                        if _side is not None and (
                                _side_best is None
                                or _side > _side_best):
                            _side_best = _side
                if _side_best is not None:
                    _trench_depths.append(_side_best - _centre)
                    if _cum2 <= TUNNEL_MOUTH_WINDOW_M and (
                            _deck_reference is None
                            or _side_best > _deck_reference):
                        _deck_reference = _side_best
                if _cum2 <= TUNNEL_MOUTH_WINDOW_M and (
                        _mouth_min is None or _centre < _mouth_min):
                    _mouth_min = _centre
            _median_depth: float | None = None
            if _trench_depths:
                _sorted_depths = sorted(_trench_depths)
                _median_depth = _sorted_depths[
                    len(_sorted_depths) // 2]
            # EVIDENCE and MODE are separate questions.  ``_cut_measured``
            # is the physical finding — R10-1 admits on it, because an
            # env flag is not physical evidence and an operator choosing
            # the synthetic construction must not thereby delete every
            # tunnel on the field.  ``cut_detected`` stays what it always
            # was: the switch to the light-touch construction, which
            # ``O4_TUNNEL_DEM_CUT=0`` still turns off.
            _cut_measured = (
                _median_depth is not None
                and len(_trench_depths) >= 2
                and _median_depth >= TUNNEL_DEM_CUT_MIN_DROP_M)
            # §T2.1: THE MODE ALSO NEEDS A DEM THAT CAN CARRY AN APPROACH
            # PROFILE.  Measured relief admits the bore; a source class
            # coarser than lidar cannot be trusted to have carved the
            # approach, so a coarse-DEM "cut" emits the full synthetic
            # ramp+mouth exactly as if no cut existed (LEMD: 8 of 8
            # clusters emitted no ramp at all).  ``_cut_measured`` — the
            # EVIDENCE — is untouched.
            _prov_ok, _prov_class = (
                dem_cut_provenance if dem_cut_provenance is not None
                else (True, None))
            cut_detected = (
                os.environ.get("O4_TUNNEL_DEM_CUT", "1") == "1"
                and _cut_measured
                and (_prov_ok or not _demcut_provenance_gate_on()))
            if (_cut_measured and not cut_detected and _prov_ok is False
                    and _demcut_provenance_gate_on()
                    and os.environ.get("O4_TUNNEL_DEM_CUT", "1") == "1"):
                UI.vprint(
                    1,
                    f"  [pav-builder] tunnel way {tw_id}: DEM cut measured "
                    f"({_median_depth:.2f} m) but the DEM source class is "
                    f"{_prov_class!r} — not lidar-class, so the light-touch "
                    f"mode stands down and the full synthetic ramp+mouth "
                    f"is emitted (spec tunnel-integrity-round §T2.1).")
            if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                print(f"    [tunnel-dem-probe] way {tw_id} portal "
                      f"({walk[0][0]:.0f},{walk[0][1]:.0f}): "
                      f"apt_elev={apt_elev:.2f} "
                      f"median_cross_road_depth={_median_depth} "
                      f"deck_reference={_deck_reference} "
                      f"mouth_min={_mouth_min} "
                      f"cut_detected={cut_detected}")
            # ── R10-1 / A1: NO PHYSICAL EVIDENCE, NO DEPTH ────────────
            # The DEM is the physical authority; OSM ``layer=-1`` is a
            # RELATIVE stacking statement (order against the crossing
            # feature — at a building passthrough, the building), never
            # absolute depth.  Per portal:
            #
            #     emit below grade ⇔ cut_detected
            #                        OR (layer < 0 AND the DEM is unusable)
            #
            # "Unusable" is the probe's OWN failure condition, so a
            # refusal never rests on a measurement the probe did not
            # make.  ``tunnel=building_passage`` is covered-at-grade by
            # definition and never seeds SYNTHETIC depth whatever the
            # tag says (a real cut still admits it — the DEM-cut mode
            # emits no synthetic ramps anyway).  KCLT area 1: four
            # ``layer=-1`` service ways under a terminal, cross-road
            # relief 0.016-0.222 m, emitting ramps at −8 m through an
            # apron.  A refusal is RECORDED, never silent: a wrongly
            # refused real bore has to be visible evidence.
            _dem_unusable = (_median_depth is None
                             or len(_trench_depths) < 2)
            _layer_below = False
            _layer_raw = t_tags.get("layer")
            if _layer_raw is not None:
                try:
                    _layer_below = float(
                        str(_layer_raw).split(";")[0]) < 0.0
                except (TypeError, ValueError):
                    _layer_below = False
            _covered_at_grade = (
                t_tags.get("tunnel") == "building_passage")
            # A6's third disjunct: no cut, but the COVER says bore.  A
            # ``building_passage`` is covered-at-grade by definition and
            # stays barred from it (R10-1 bullet 2, untouched by A6) —
            # every OTHH passthrough measures 0.00 pavement cover and
            # would fail the test anyway, so the bar costs nothing and
            # keeps the tag meaning what it says.
            _f_building, _f_pavement = _cover_fractions(tw_id, t_nrefs)
            _cover_says_bore = (
                _has_tunnel_tag_evidence(t_tags)
                and not _covered_at_grade
                and _f_building is not None
                and _f_pavement is not None
                and _f_building < TUNNEL_PASSTHROUGH_BUILDING_COVER_FRAC
                and _f_pavement >= TUNNEL_BORE_PAVEMENT_COVER_FRAC)
            if _cut_measured:
                _admitted_by = "dem_cut"
            elif (_layer_below and _dem_unusable
                    and not _covered_at_grade):
                _admitted_by = "layer_below_dem_unusable"
            elif _cover_says_bore:
                _admitted_by = "pavement_cover"
            else:
                _admitted_by = None
            if _admitted_by is None:
                if passthrough_findings is not None:
                    _f_lat, _f_lon = meters_to_lat_lon(*walk[0])
                    passthrough_findings.append({
                        "way_id": tw_id,
                        "lat": round(_f_lat, 7),
                        "lon": round(_f_lon, 7),
                        "x_m": round(walk[0][0], 1),
                        "y_m": round(walk[0][1], 1),
                        "median_cross_road_depth_m": _median_depth,
                        "building_cover_fraction": _f_building,
                        "airside_pavement_cover_fraction": _f_pavement,
                        "layer": _layer_raw,
                        "tunnel": t_tags.get("tunnel"),
                        "admitted_by": None,
                        "refused_because": (
                            "covered_at_grade" if _covered_at_grade
                            else "building_cover"
                            if (_f_building is not None
                                and _f_building
                                >= TUNNEL_PASSTHROUGH_BUILDING_COVER_FRAC)
                            else "no_cover_no_cut"),
                    })
                if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                    print(f"    [tunnel-passthrough] way {tw_id} portal "
                          f"({walk[0][0]:.0f},{walk[0][1]:.0f}): no cut "
                          f"(median={_median_depth}), layer={_layer_raw}, "
                          f"cover building={_f_building} "
                          f"pavement={_f_pavement} — nothing below grade "
                          f"emitted here")
                continue
            if (_admitted_by == "pavement_cover"
                    and os.environ.get("O4_TUNNEL_DEBUG") == "1"):
                print(f"    [tunnel-cover-bore] way {tw_id} portal "
                      f"({walk[0][0]:.0f},{walk[0][1]:.0f}): no DEM cut, "
                      f"admitted on cover (building={_f_building}, "
                      f"pavement={_f_pavement}) — the pavement is the deck")
            # ── A-2 / R14-3: THE BORE FLOOR, THEN THE RUN ────────
            # The floor is the road CLEARANCE below the MEASURED deck,
            # not a fixed 8 m.  A service road passing under a crossing
            # needs road clearance and no more; the 8 m synthetic sank
            # KCLT's SE bore 11.46 m, and a climb out of that hole then
            # demanded 361 m of roadway.  A cut bore keeps R10-3's
            # deeper-of-the-two.  ``tunnel_depth_m`` survives only where
            # there is no deck reference at all.
            elev_low = _bore_floor_elevation(
                apt_elev, _deck_reference, _mouth_min, _cut_measured,
                tunnel_depth_m)
            # THE RUN IS DEPTH OVER GRADE, never the way's extent.
            # Three mechanisms used to outlive grade-reach here, and all
            # three are gone: the 8 m synthetic floor (above), the 3.5 %
            # planning grade, and ``ramp_min_length_m``'s 200 m MINIMUM,
            # which kept walking after the grade requirement was already
            # met.  A minimum that outlives grade-reach is not a floor,
            # it is a canyon: it carried KCLT's SE chain 173 m into a
            # taxiway junction.  ``ramp_min_length_m`` is retired from
            # this walk (the parameter stays for the callers).  R20-2
            # leaves all three retired: the 5 % cap below is still what
            # sizes the MINIMUM lawful run, and the DEM-reach extension
            # after it is a per-station measurement of the ground, not a
            # length anyone declared.
            _ambient = (float(_deck_reference) if _deck_reference is not None
                        else float(apt_elev))
            # The MINIMUM lawful run at the owner's 5 % cap.  Walking
            # further would be lawful (shallower); walking less would
            # not (steeper), and the ``max_drop`` cap below holds the
            # emitted top edge to the cap either way.
            _bore_depth = max(0.0, _ambient - elev_low)
            _run_floor = max(_bore_depth / TUNNEL_APPROACH_GRADE, 1.0)
            # ── R20-2: THE RUN REACHES GRADE ──────────────────────
            # The minimum above is PORTAL-LOCAL: it measures depth
            # against the ambient AT THE MOUTH and assumes the ground
            # stays there.  Where the road climbs away from the portal
            # it does not, and the run stops with the ramp still buried:
            # at the owner's KCLT portal the deck reference is 211.44
            # while the DEM on the walk reaches 216.71, so a run sized
            # on 211.44 − 206.36 ended 101 m out and the ramp topped
            # 4.26 m under the ground beside it — a 4.4 m cliff, with
            # ~97 m of corridor to the taxiway carrying no shape at all.
            #
            # The run is sized against the GROUND ALONG THE WALK, and
            # against the grade this module actually EMITS.  Those were
            # two different constants: the sizing used
            # ``TUNNEL_APPROACH_GRADE`` (5 %) and the emit uses
            # ``plan_grade`` (the ramp cap less its safety margin,
            # 3.5 %), so even on flat ground the run was 30 % short of
            # what its own ramp needed.  ONE constant now runs the whole
            # path — sizing here, the ``max_drop`` cap below, and
            # ``_emit_chain``'s effective-space clamp all read the
            # emitted grade.
            #
            # The run therefore extends while
            # ``dem_along_walk(s) − elev_low > emit_grade · s`` and ends
            # where the ramp MEETS the ground, so the top edge lands on
            # the DEM instead of under it.  Nothing that R14 removed
            # comes back: this is a floor-and-extend, never a minimum —
            # it cannot make a run SHORTER than the R14 minimum above,
            # and it stops the moment the ramp is at grade, so neither
            # the 200 m minimum nor the 8 m synthetic floor is
            # reachable from here.  Past the meeting station the walk's
            # surface is ordinary road: the R14-1 claim machinery
            # re-profiles the mapped pavement it covers (the approach
            # zone is this same run-limited walk), and where nothing is
            # mapped the road law owns it.
            #
            # SCOPE: the portals that HAVE a synthetic ramp.  A
            # ``cut_detected`` portal emits the light-touch
            # cap/mouth/roof construction instead — the bare-earth DEM
            # already carries the descending approach — so there is no
            # ramp there to bring up to ground and nothing to reach for;
            # extending its walk would only widen the R14-1 claim's
            # approach zone over ground the trench already models.  Those
            # portals keep the R14 run exactly.
            _emit_grade = max(float(plan_grade), 1e-3)

            def _walk_ground(_pt):
                """DEM on the walk, ``None`` when it cannot answer."""
                try:
                    _g_lat, _g_lon = meters_to_lat_lon(*_pt)
                    _g_raw = _sample_dem(
                        dem, tile_lat, tile_lon, _g_lat, _g_lon)
                except _GEOM_EXC:
                    return None
                return None if _g_raw is None else float(_g_raw)

            _meet_at = 0.0
            if not cut_detected:
                _stations: list[float] = [0.0]
                for _i in range(1, len(walk)):
                    _stations.append(_stations[-1] + math.hypot(
                        walk[_i][0] - walk[_i - 1][0],
                        walk[_i][1] - walk[_i - 1][1]))
                # Deficit = how far the emitted ramp is still BELOW the
                # ground at that station.  Sampled at the walk's own
                # vertices — the stations the ramp quads are cut at — so
                # the crossing this finds is the crossing the emitted
                # profile has.  The LAST station still below ground is
                # what sizes the run, not the first crossing: a dip in
                # the road must not end a run the ground beyond it still
                # demands.
                _deficits: list[float] = []
                for _i, _pt in enumerate(walk):
                    _g = _walk_ground(_pt)
                    if _g is None:
                        _g = _ambient
                    _deficits.append(
                        _g - elev_low - _emit_grade * _stations[_i])
                _last_below = -1
                for _i in range(len(_deficits) - 1, -1, -1):
                    if _deficits[_i] > 0.0:
                        _last_below = _i
                        break
                if _last_below < 0:
                    # The ramp is at or above ground from the mouth out —
                    # nothing to reach.  R14's minimum governs.
                    _meet_at = 0.0
                elif _last_below >= len(walk) - 1:
                    # The ground outruns the ramp for the whole walk: no
                    # meeting station exists on this road.  Surface all
                    # of it; the ``max_drop`` cap below keeps the top
                    # lawful and the residual gap is the road's, not the
                    # ramp's.
                    _meet_at = _stations[-1]
                else:
                    _d0 = _deficits[_last_below]
                    _d1 = _deficits[_last_below + 1]
                    _t = (_d0 / (_d0 - _d1)
                          if (_d0 - _d1) > 1e-9 else 1.0)
                    _t = min(1.0, max(0.0, _t))
                    _meet_at = (_stations[_last_below]
                                + _t * (_stations[_last_below + 1]
                                        - _stations[_last_below]))
            _run_limit = max(_run_floor, _meet_at)
            # ── R20-2b: THE TAXIWAY STOP ─────────────────────────────
            # A run that never meets ground walks the WHOLE walk, and
            # the walk follows a road that can cross aircraft-transit
            # pavement.  A ramp there is neither cut (R14-2/A-3 forbids
            # cutting a taxiway) nor yielded, so it would simply lie on
            # the taxiway at ramp elevation — the R14 canyon in a new
            # costume.  The run therefore ENDS at the first transit
            # pavement it reaches.  The safety floor in
            # ``_tunnel_ramp_pavement_cut`` is the second half of this
            # (a piece that still lands mostly on transit pavement is
            # dropped); this half keeps the chain from being built into
            # it at all, so the drop never has to remove a mid-chain
            # piece and leave a hole.
            #
            # An INITIAL run already on transit pavement is skipped:
            # a portal at the face of the very pavement its bore passes
            # under starts there by construction, and stopping at
            # station 0 would delete every such ramp (the AIRSIDE /
            # DOUBLE-EMIT GATE is what judges those, on whether the ramp
            # LEADS AWAY from pavement).  It is the first RE-ENTRY that
            # stops the run.
            if transit_union is not None:
                _left_transit = False
                _stop_at: float | None = None
                _s_t = 0.0
                for _i in range(len(walk)):
                    if _i:
                        _s_t += math.hypot(
                            walk[_i][0] - walk[_i - 1][0],
                            walk[_i][1] - walk[_i - 1][1])
                    try:
                        _inside = transit_union.intersects(
                            Point(walk[_i]))
                    except _GEOM_EXC:
                        _inside = False
                    if not _inside:
                        _left_transit = True
                        continue
                    if _left_transit:
                        _stop_at = _s_t
                        break
                if _stop_at is not None and _stop_at < _run_limit:
                    _run_limit = max(_stop_at, 1.0)
                    if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                        print(f"    [tunnel-transit-stop] way {tw_id}: "
                              f"run cut to {_run_limit:.1f} m at the "
                              f"first aircraft-transit pavement")
            cum = 0.0
            kept_pts: list[tuple[float, float]] = [walk[0]]
            for i in range(1, len(walk)):
                seg_len = math.hypot(
                    walk[i][0] - walk[i - 1][0],
                    walk[i][1] - walk[i - 1][1])
                if cum + seg_len >= _run_limit:
                    _t = ((_run_limit - cum) / seg_len
                          if seg_len > 1e-9 else 1.0)
                    _t = min(1.0, max(0.0, _t))
                    _cx = walk[i - 1][0] + _t * (walk[i][0] - walk[i - 1][0])
                    _cy = walk[i - 1][1] + _t * (walk[i][1] - walk[i - 1][1])
                    if math.hypot(_cx - kept_pts[-1][0],
                                  _cy - kept_pts[-1][1]) > 0.5:
                        kept_pts.append((_cx, _cy))
                    cum = _run_limit
                    break
                cum += seg_len
                kept_pts.append(walk[i])
            if len(kept_pts) < 2:
                kept_pts = list(walk[:2])
                cum = math.hypot(walk[1][0] - walk[0][0],
                                 walk[1][1] - walk[0][1])
            grade_ok_at = cum
            walk = kept_pts
            far_xy = walk[-1]
            try:
                far_lat, far_lon = meters_to_lat_lon(*far_xy)
                far_dem = _sample_dem(
                    dem, tile_lat, tile_lon, far_lat, far_lon)
            except _GEOM_EXC:
                far_dem = None
            if far_dem is None:
                far_dem = _ambient
            # The visible top edge never outruns the grade the chain is
            # emitted at (R20-2: ONE constant on the whole path — the
            # cap that judges the top must be the cap the run was sized
            # on, or the run buys reach the cap then refuses to spend).
            max_drop = _emit_grade * grade_ok_at
            if (far_dem - elev_low) > max_drop:
                far_dem = elev_low + max_drop
            mouth_grade = (_mouth_min if _mouth_min is not None
                           else apt_elev - tunnel_depth_m)
            # Bore polyline INWARD from this portal (for the roof
            # plates over the covered body), truncated at the bore
            # MIDPOINT — each end covers its own half with its own
            # local deck reference (★a full-bore plate from one end
            # lands the PARTNER cluster's head inside this cluster's
            # exclusion zone and silently drops it — measured EGGW
            # v4: "inside an emitted portal's exclusion zone" at the
            # south-west mouth) — and at the roof plate cap.
            _inward_refs = (t_nrefs if portal_idx == 0
                            else list(reversed(t_nrefs)))
            _bore_pts = [nodes_m[_nref] for _nref in _inward_refs
                         if _nref in nodes_m]
            _bore_length = sum(
                math.hypot(_bore_pts[i + 1][0] - _bore_pts[i][0],
                           _bore_pts[i + 1][1] - _bore_pts[i][1])
                for i in range(len(_bore_pts) - 1))
            _roof_limit = min(TUNNEL_ROOF_PLATE_MAX_LENGTH_M,
                              0.5 * _bore_length + 0.5)
            inward_pts: list[tuple[float, float]] = []
            _cum3 = 0.0
            for _pt in _bore_pts:
                if inward_pts:
                    _segment = math.hypot(
                        _pt[0] - inward_pts[-1][0],
                        _pt[1] - inward_pts[-1][1])
                    if _cum3 + _segment > _roof_limit:
                        _fraction = ((_roof_limit - _cum3) / _segment
                                     if _segment > 1e-9 else 0.0)
                        inward_pts.append((
                            inward_pts[-1][0]
                            + (_pt[0] - inward_pts[-1][0]) * _fraction,
                            inward_pts[-1][1]
                            + (_pt[1] - inward_pts[-1][1]) * _fraction))
                        break
                    _cum3 += _segment
                inward_pts.append(_pt)
            # Deck grade at the INNER (pavement-side) end of the roof
            # cover — the highest cross-bore sample there.  The roof
            # plate GRADES from this at its inner end down to the
            # face-local ``deck_reference`` at the mouth (user
            # 2026-07-17: "a clean wall that grades the terrain from
            # the taxiway flat over to the tunnel portal") — a flat
            # plate at the face grade left a ~3 m scarp against the
            # taxiway edge (measured EGGW v5: 154.8 plate against
            # 157.6 pavement).
            _inner_deck: float | None = None
            if len(inward_pts) >= 2:
                _idx = inward_pts[-1][0] - inward_pts[-2][0]
                _idy = inward_pts[-1][1] - inward_pts[-2][1]
                _ilen = math.hypot(_idx, _idy) or 1.0
                _iperp = (-_idy / _ilen, _idx / _ilen)
                for _offset in (_half_road + 6.0, _half_road + 15.0):
                    for _sign in (+1.0, -1.0):
                        _side = _dem_at_local(
                            inward_pts[-1][0]
                            + _iperp[0] * _offset * _sign,
                            inward_pts[-1][1]
                            + _iperp[1] * _offset * _sign)
                        if _side is not None and (
                                _inner_deck is None
                                or _side > _inner_deck):
                            _inner_deck = _side
            portal_data.append(
                (portal_nid, tw_id, walk, hw,
                 float(apt_elev), float(far_dem), _is_new_cand,
                 float(way_carriage_w), bool(cut_detected),
                 float(mouth_grade), inward_pts,
                 (float(_deck_reference)
                  if _deck_reference is not None else None),
                 (float(_inner_deck)
                  if _inner_deck is not None else None),
                 # R20-2b (AMENDMENT 1) — index 13, THE BORE FLOOR THIS
                 # WALK WAS SIZED AGAINST.  It used to die here: the run
                 # was sized on ``_bore_floor_elevation`` while
                 # ``_emit_portal_cluster`` emitted the chain from
                 # ``apt_elev − tunnel_depth_m``, and at the owner's KCLT
                 # portal those are 210.5 and 206.36 — the 4.5 m between
                 # them WAS the 4.26 m cliff, not the run length.  One
                 # number now leaves this function and is gathered, sized
                 # and emitted against.
                 float(elev_low)))
    if _n_adj_skip:
        try:
            UI.vprint(1,
                f"  [pav-builder] skipped {_n_adj_skip} tunnel(s) with "
                f"an adjacent/crossing road (ramps not modelled).")
        except _GEOM_EXC:
            pass
    # The R10-1 summary counts ITS OWN population, not the whole
    # register: §T3.2 put the adjacent-road veto records into the same
    # list (one place a refusal is recorded, one sidecar key), and a
    # summary that counted the list would report vetoes as
    # covered-at-grade passthroughs.  The veto has its own count above.
    _n_passthrough = sum(
        1 for _f in (passthrough_findings or ())
        if isinstance(_f, dict)
        and _f.get("refused_because") != "adjacent_road_veto")
    if _n_passthrough:
        try:
            UI.vprint(1,
                f"  [pav-builder] R10-1: {_n_passthrough} "
                f"tunnel portal(s) emitted NOTHING below grade — the DEM "
                f"probe found no cut there and the way's layer tag is not "
                f"corroborated by any measurement (covered-at-grade "
                f"passthrough).")
        except _GEOM_EXC:
            pass
    if os.environ.get("O4_TUNNEL_DEBUG") == "1":
        print(f"    [tunnel-portals] {len(portal_data)} portal walk(s) "
              f"built")
    return portal_data


def _facing_same_road_portals(portal_data: list, way_by_id: dict,
                              max_gap_m: float,
                              min_gap_m: float = 0.0) -> tuple[set, list]:
    """FACING same-road portal pairs — ``(facing indices, pairs)``.

    Two portals FACE each other when they belong to different ways of
    the SAME ROAD (``_way_signature``, the R6-2 same-road law), their
    stations lie between ``min_gap_m`` and ``max_gap_m``, and each one's
    outward approach heads at the other.  The mutual test is what keeps
    a merely NEARBY bore — a parallel service road, the far end of the
    same system — out of the set.

    ``min_gap_m`` is A8's first case read here: portals within
    ``portal_cluster_dist_m`` are COMBINED-ENTRANCE SIBLINGS, one
    entrance that ``_cluster_portals`` merges — there is no gap between
    them to lower, and treating them as facing minted a degenerate
    corridor sliver (measured KCLT: 3.6 m² between two stations ~2 m
    apart).  A gap has to be a gap.

    A3 (owner ruling 2026-08-11): such a pair is not two tunnels with an
    approach between them, it is ONE lowered stretch of road — "the two
    close together tunnel mouths indicate the whole area is lowered …
    and flat between the two mouths".  The gap therefore emits an open
    CUT (:func:`_emit_facing_corridors`) and neither portal emits
    ramp-to-grade geometry into it; ramps to grade remain the job of the
    system's OUTER approaches.
    """
    _stations: list = []
    for _pd in portal_data:
        _walk = _pd[2]
        if len(_walk) < 2:
            _stations.append(None)
            continue
        _dx, _dy = _walk[1][0] - _walk[0][0], _walk[1][1] - _walk[0][1]
        _dl = math.hypot(_dx, _dy)
        _stations.append(None if _dl < 1e-6
                         else (_walk[0], (_dx / _dl, _dy / _dl)))
    _facing: set = set()
    _pairs: list = []
    for i in range(len(portal_data)):
        if _stations[i] is None:
            continue
        _wi = way_by_id.get(portal_data[i][1])
        if _wi is None:
            continue
        _pi, _di = _stations[i]
        for j in range(i + 1, len(portal_data)):
            if _stations[j] is None:
                continue
            if portal_data[j][1] == portal_data[i][1]:
                # A way's own two ends are the OPPOSITE mouths of one
                # bore; the ground between them is the bore itself.
                continue
            _wj = way_by_id.get(portal_data[j][1])
            if _wj is None:
                continue
            if _way_signature(_wi[1]) != _way_signature(_wj[1]):
                continue
            _pj, _dj = _stations[j]
            _vx, _vy = _pj[0] - _pi[0], _pj[1] - _pi[1]
            _vl = math.hypot(_vx, _vy)
            if _vl < 1e-6 or _vl > max_gap_m or _vl <= min_gap_m:
                continue
            _ux, _uy = _vx / _vl, _vy / _vl
            if (_di[0] * _ux + _di[1] * _uy) < 0.5:
                continue
            if (_dj[0] * -_ux + _dj[1] * -_uy) < 0.5:
                continue
            _facing.add(i)
            _facing.add(j)
            _pairs.append((i, j))
            if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                print(f"    [tunnel-facing] ways {portal_data[i][1]} / "
                      f"{portal_data[j][1]} face across {_vl:.0f} m — "
                      f"the gap is an OPEN CUT, not two ramps")
    return _facing, _pairs


def _mouth_grade_with_clearance(mouth_grade, deck_reference):
    """R10-3 depth floor: a mouth never sits shallower than
    ``BRIDGE_ROAD_CLEARANCE_M`` below the MEASURED deck.

    A 1-arcsec DEM under-resolves a narrow cut — the smoothed trench
    floor mixes face pixels with the deck above — so the probe can read
    a bore shallower than the crossing structurally requires (KCLT:
    215.83 under a 219.01 deck).  The DEM may say DEEPER; it may not say
    shallower.  ``deck_reference`` of ``None`` is the mid-field fallback
    that samples the trench floor itself, and clamping to it would sink
    the mouth a clearance below its own road.
    """
    if mouth_grade is None or deck_reference is None:
        return mouth_grade
    return min(float(mouth_grade),
               float(deck_reference) - float(_CFG.BRIDGE_ROAD_CLEARANCE_M))


def _emit_facing_corridors(layout: "PavementLayout", portal_data: list,
                           pairs: list, exclusion_zones: list,
                           wall_gap_m: float,
                           retaining_wall_width_m: float,
                           dem_at) -> int:
    """A3's OPEN CUT: one depressed corridor per facing pair.

    The surface spans station to station at the linear interpolation of
    the two portals' (clearance-floored) mouth grades — flat when they
    agree — at the pair's shared carriageway width, with a retaining
    wall down BOTH sides following the DEM the cut is made in.  It is
    ROOFLESS: the gap is open sky, not tunnel, and nothing here is
    tagged ``tunnel``.

    The corridor is tunnel PAVEMENT (``ROLE_TUNNEL_RAMP``): R10-2's cuts
    treat it exactly as a ramp, and like a ramp it CUTS the pavement it
    lowers — the gap's service junctions cannot be left standing at
    grade over a road the ruling puts a bore-depth below them.
    """
    _n = 0
    for (i, j) in pairs:
        _a, _b = portal_data[i], portal_data[j]
        _pa, _pb = _a[2][0], _b[2][0]
        _dx, _dy = _pb[0] - _pa[0], _pb[1] - _pa[1]
        _len = math.hypot(_dx, _dy)
        if _len < 2.0:
            continue
        _ux, _uy = _dx / _len, _dy / _len
        _px, _py = -_uy, _ux
        _half = 0.5 * max(float(_a[7]), float(_b[7]))
        _ga = _mouth_grade_with_clearance(
            _a[9], _a[11] if len(_a) > 11 else None)
        _gb = _mouth_grade_with_clearance(
            _b[9], _b[11] if len(_b) > 11 else None)
        if _ga is None or _gb is None:
            continue
        _ga, _gb = round(float(_ga), 2), round(float(_gb), 2)
        # 4-corner high/low encoding (ring order 0,3 = high / 1,2 = low),
        # the encoding that demonstrably reaches the mesh; a flat pair
        # ships as one altitude so no rounding tilts a level cut.
        _corners = [
            (_pb[0] + _px * _half, _pb[1] + _py * _half),
            (_pa[0] + _px * _half, _pa[1] + _py * _half),
            (_pa[0] - _px * _half, _pa[1] - _py * _half),
            (_pb[0] - _px * _half, _pb[1] - _py * _half),
        ]
        try:
            _floor = Polygon(_corners)
            if not _floor.is_valid:
                _floor = _floor.buffer(0)
            if _floor.geom_type != "Polygon" or _floor.is_empty:
                continue
        except _GEOM_EXC:
            continue
        if abs(_gb - _ga) >= 0.1:
            _shape = BuiltShape(
                polygon=_floor, role=ROLE_TUNNEL_RAMP,
                ref="tunnel_corridor",
                altitude_high=_gb, altitude_low=_ga)
        else:
            _shape = BuiltShape(
                polygon=_floor, role=ROLE_TUNNEL_RAMP,
                ref="tunnel_corridor",
                altitude=round(0.5 * (_ga + _gb), 2))
        layout.shapes.append(_shape)
        exclusion_zones.append(_floor)
        _n += 1
        # Retaining wall down both sides, DEM-following like every other
        # tunnel wall (the crest is the ground the cut is made in).
        for _sign in (+1.0, -1.0):
            # R16-2b: the band's inner edge IS the cut floor's edge
            # (``_half``), so the two share their vertices and nothing
            # between them is unowned; the crest stays where it was,
            # ``wall_gap + width`` out.
            #
            # §T5 (RULINGS 2026-08-28c item 1) splits that band in two at
            # ``wall_gap`` — the owner's "small gap" between the road
            # surface and the wall, without giving the gap back to
            # nobody.  The FOOT is the ``wall_gap`` shelf, FLAT at the
            # floor's own profile (``_ga``/``_gb``: no rise across its
            # width), and the FACE rises from the foot's outer edge to
            # the crest.  The floor welds to the FOOT; it shares no
            # vertex with the rising ``tunnel_wall``.
            # §T5 REACHES THIS EMITTER (the follow-up docket Amendment 1
            # ruling 1 named, closed 2026-08-29).  Amendment 1 scoped the
            # foot to the perimeter band because 3 SPJC foot∩face pairs
            # (2.99 m²) were not root-caused; Amendment 2 attributed them
            # to the PERIMETER band, and the mechanism is now measured —
            # the post-solve conformance weld bows a welded face inboard
            # — and closed for EVERY emitter by
            # :func:`reclip_wall_feet_against_faces`.  So the residual
            # population this emitter was reported as owning is fixed
            # here: MEASURED at OTHH (baseline td_base_othh),
            # ``ramp_wall_gap`` 32 shared node ids and
            # ``ramp_wall_annulus_owned`` 56/56 are this emitter's — its
            # single band starts AT the corridor edge (``_half``), so
            # every wall shares the corridor's own nodes, and its inner
            # pair carries the cut FLOOR while its outer pair carries the
            # crest, which is the 5.14 m ``wall_top_flat`` reading on way
            # -12281 (4.00 vs -1.14) and the crumpled ribbon in the sim.
            #
            # WITH THE FOOT: the FLOOR is the foot's (a flat shelf out to
            # ``wall_gap_m``, welded to the corridor as the structure's
            # own), and the FACE stands off it carrying the CREST on BOTH
            # edges — §F1's "the top is flat across its width", here by
            # construction: the two vertices at one station read one DEM
            # sample.  OFF is the single band, byte for byte.
            _crest = _half + wall_gap_m + retaining_wall_width_m
            if ramp_wall_foot_enabled():
                _bands = (
                    (_half, _half + wall_gap_m, TUNNEL_WALL_FOOT_REF,
                     True),
                    (_half + wall_gap_m, _crest, "tunnel_wall", False),
                )
            else:
                _bands = ((_half, _crest, "tunnel_wall", False),)
            for _inner, _outer, _wall_ref, _flat in _bands:
                _ring = [
                    (_pa[0] + _px * _inner * _sign,
                     _pa[1] + _py * _inner * _sign),
                    (_pb[0] + _px * _inner * _sign,
                     _pb[1] + _py * _inner * _sign),
                    (_pb[0] + _px * _outer * _sign,
                     _pb[1] + _py * _outer * _sign),
                    (_pa[0] + _px * _outer * _sign,
                     _pa[1] + _py * _outer * _sign),
                ]
                try:
                    _wall = Polygon(_ring)
                    if not _wall.is_valid:
                        _wall = _wall.buffer(0)
                    if _wall.geom_type != "Polygon" or _wall.is_empty:
                        continue
                except _GEOM_EXC:
                    continue
                # The ring is ``[inner@_pa, inner@_pb, outer@_pb,
                # outer@_pa]``: the first two vertices carry the cut
                # floor's profile (``_ga`` at ``_pa``, ``_gb`` at
                # ``_pb``).  A FOOT is flat, so its outer pair carries
                # the SAME profile; a FACE's outer pair is the crest and
                # keeps the DEM (R16-2b).
                if _flat:
                    _alts = [round(float(_ga), 2), round(float(_gb), 2),
                             round(float(_gb), 2), round(float(_ga), 2)]
                elif ramp_wall_foot_enabled():
                    # §F1 HERE: ONE VALUE PER STATION ACROSS THE BAND.
                    # ``_ring`` is [inner@_pa, inner@_pb, outer@_pb,
                    # outer@_pa], so indices 0/3 stand at station _pa and
                    # 1/2 at _pb.  The crest is sampled ONCE per station
                    # (at the outer vertex, the ambient the wall grades
                    # to) and both vertices of that station carry it —
                    # the wall top cannot twist, by construction.  The
                    # FLOOR is the foot's now, not this band's.
                    def _crest_at(_xy):
                        _g = dem_at(_xy[0], _xy[1])
                        return round(float(_g) if _g is not None
                                     else max(_ga, _gb), 1)
                    _ca = _crest_at(_ring[3])
                    _cb = _crest_at(_ring[2])
                    _alts = [_ca, _cb, _cb, _ca]
                else:
                    _alts = [round(float(_ga), 2), round(float(_gb), 2)]
                    for (_vx, _vy) in _ring[2:]:
                        _ground = dem_at(_vx, _vy)
                        _alts.append(round(
                            float(_ground) if _ground is not None
                            else max(_ga, _gb), 1))
                _alts.append(_alts[0])
                _append_tunnel_cover(
                    layout, exclusion_zones,
                    _tunnel_pavement_union(layout),
                    BuiltShape(polygon=_wall, role=ROLE_RETAINING_WALL,
                               ref=_wall_ref, node_altitudes=_alts))
        if os.environ.get("O4_TUNNEL_DEBUG") == "1":
            print(f"    [tunnel-corridor] ways {_a[1]}/{_b[1]}: "
                  f"{_len:.0f} m open cut at {_ga:.2f}..{_gb:.2f}, "
                  f"width {2 * _half:.0f} m, walled both sides")
    if _n:
        try:
            UI.vprint(1,
                f"  [pav-builder] A3: {_n} facing-portal gap(s) emitted "
                f"as ONE depressed open corridor — the road between two "
                f"close mouths of the same road is lowered whole, not "
                f"ramped up and back down.")
        except _GEOM_EXC:
            pass
    return _n


def _dedup_portal_walks(portal_data: list, nodes_m: dict,
                        portal_cluster_dist_m: float) -> list:
    """Drop portals of the LMML MERGE CLASS only (see WALK DEDUP below).
    """
    # WALK DEDUP (user 2026-07-04): twin carriageways that MERGE beyond
    # their portals give two portals the SAME surface walk — two ramps
    # emitted on one stretch of road, one per bore profile (LMML:
    # coincident tunnel_ramp pieces 4.3 m apart in z).
    #
    # A8 (lead ruling 2026-08-11, final form).  Overlap ALONE was the
    # wrong key and station distance alone was too: three populations
    # share "two portals whose walks coincide", and only ONE is
    # duplicate.  They separate by station distance and OUTWARD WALK
    # DIRECTION:
    #
    #   COMBINED-ENTRANCE SIBLINGS — divided carriageways of one
    #     crossing, stations within ``portal_cluster_dist_m`` (OTHH's
    #     twin bores measure 7.3-17.8 m apart).  NEVER dropped:
    #     ``_cluster_portals`` merges them into the one combined-WIDTH
    #     entrance it exists to build, and dropping one instead left
    #     each bore spanning a single carriageway.
    #   FACING ENTRANCES — opposite ends across an open gap, outward
    #     directions OPPOSING.  NEVER dropped: they are two distinct
    #     mouths and the A3 open-cut corridor owns the road between
    #     them (KCLT F|-255 / F|-251, 55.5 m apart).  Their walks DO
    #     coincide, which is exactly why overlap alone deleted one.
    #   THE LMML MERGE CLASS — carriageways merging into one roadway
    #     beyond portals that are far apart, so two ramps land on one
    #     stretch of road at two profiles (coincident pieces 4.3 m
    #     apart in z, user 2026-07-04).  Aligned, far apart, and
    #     overlapping: this, and only this, is dropped.
    #
    # A way's own two portals never dedup (opposite tunnel mouths, user
    # 2026-05-03).  The 4 m buffer is the original overlap geometry.
    _kept_portals: list = []
    _kept_meta: list = []      # (walk line, tw_id, station, outward dir)
    for _pd in portal_data:
        _walk_pts = _pd[2]
        _wline = (LineString(_walk_pts) if len(_walk_pts) >= 2 else None)
        _station = nodes_m.get(_pd[0])
        _dir = None
        if len(_walk_pts) >= 2:
            _dx = _walk_pts[1][0] - _walk_pts[0][0]
            _dy = _walk_pts[1][1] - _walk_pts[0][1]
            _dl = math.hypot(_dx, _dy)
            if _dl > 1e-6:
                _dir = (_dx / _dl, _dy / _dl)
        _dup = False
        if _wline is not None and _station is not None and _dir is not None:
            for (_kl, _kw, _kstation, _kdir) in _kept_meta:
                if _kw == _pd[1] or _kstation is None or _kdir is None:
                    continue
                if (math.hypot(_station[0] - _kstation[0],
                               _station[1] - _kstation[1])
                        < portal_cluster_dist_m):
                    continue                  # sibling — clustering owns it
                if (_dir[0] * _kdir[0] + _dir[1] * _kdir[1]) <= 0.0:
                    continue                  # facing — the corridor owns it
                try:
                    _ov = _wline.buffer(4.0).intersection(_kl).length
                except _GEOM_EXC:
                    continue
                if _ov > 0.5 * min(_wline.length, _kl.length):
                    _dup = True
                    break
        if _dup:
            if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                print(f"    [tunnel-walk-dedup] dropped portal of way "
                      f"{_pd[1]} (merges into a kept ramp's roadway)")
            continue
        _kept_portals.append(_pd)
        if _wline is not None:
            _kept_meta.append((_wline, _pd[1], _station, _dir))
    return _kept_portals


def _cluster_portals(portal_data: list, nodes_m: dict,
                     portal_cluster_dist_m: float
                     ) -> list[list[int]]:
    """Group portals into combined-entrance clusters by portal-
    node proximity.  Returns index lists into ``portal_data``.
    """
    # Cluster portals by node-coord proximity (divided highways
    # with two parallel carriageways have a portal per carriageway
    # at each tunnel end; cluster them so we emit one combined
    # entrance per end).
    #
    # Per user 2026-05-03: do NOT cluster the two portals of the
    # SAME tunnel way (a short tunnel ≤ ``portal_cluster_dist_m``
    # long has both ends within cluster distance, but they're the
    # OPPOSITE ends of the same tunnel — emitting only one cluster
    # would skip one tunnel mouth, which is what was happening on
    # the small 33 m secondary tunnel south of Terminal 2).
    clusters: list[list[int]] = []
    used: set = set()
    for i in range(len(portal_data)):
        if i in used:
            continue
        wid_i = portal_data[i][1]
        nid_i = portal_data[i][0]
        cl = [i]
        used.add(i)
        pi = nodes_m[nid_i]
        for j in range(i + 1, len(portal_data)):
            if j in used:
                continue
            wid_j = portal_data[j][1]
            if wid_j == wid_i:
                # Same tunnel way — two ends, do not cluster.
                continue
            pj = nodes_m[portal_data[j][0]]
            if (math.hypot(pi[0] - pj[0], pi[1] - pj[1])
                    < portal_cluster_dist_m):
                cl.append(j)
                used.add(j)
        clusters.append(cl)
    return clusters


# R10-2: the tunnel PAVEMENT refs a cover piece may never sit on, and
# the smallest surviving arc worth keeping.  ``tunnel_mouth`` carries
# ROLE_TUNNEL_RAMP and is road surface exactly like ``tunnel_ramp`` —
# leaving it out of the cutting union is what let a cap cover the mouth
# it was supposed to face.
_TUNNEL_PAVEMENT_REFS = ("tunnel_ramp", "tunnel_mouth", "tunnel_corridor",
                         TUNNEL_ROAD_REF)
#: §T5 — the wall's FOOT: the ``_g0`` annulus between the ramp edge and
#: the wall face's inner boundary, flat at RAMP-EDGE elevation and owned
#: by the wall structure.  Its own ref (not ``tunnel_wall``) is what makes
#: the owner's law measurable: the RAMP welds to the FOOT, at one shared
#: elevation, and shares NO node with the rising ``tunnel_wall`` face —
#: which is the "small gap" RULINGS 2026-08-28c item 1 asks for, without
#: reopening R16-2b's unowned annulus (the foot owns it).
TUNNEL_WALL_FOOT_REF = "tunnel_wall_foot"
_TUNNEL_COVER_REFS = ("tunnel_wall", TUNNEL_WALL_FOOT_REF,
                      "tunnel_roof", "tunnel_cap")

#: §T5 gate.  DEFAULT ON since the face-inflation was ATTRIBUTED
#: (2026-08-29, lane/tunneldockets).  The partition is disjoint AT EMIT
#: (measured 0.0000 m² for all 6 SPJC pieces); what inflated each wall
#: FACE by ~1.4 m² (343.2→344.6, 116.4→117.8, 315.7→317.3) back over its
#: foot is ``conformance.enforce_conformance`` — the post-solve T-vertex
#: weld, whose inserts take the DONOR's coordinate (never the projection
#: onto the receiving edge), so an insert bows the receiving ring by up
#: to ``CONFORMANCE_TOL_M`` (0.5 m).  Measured: exactly 2 inserts per
#: SPJC face, every donor a vertex carried by the band's own
#: ``tunnel_wall``/``tunnel_wall_foot`` pieces.  That weld is not a
#: defect — it is what keeps Triangle4XP from tearing — so the FOOT
#: yields to the welded face afterwards
#: (:func:`reclip_wall_feet_against_faces`), exactly as pavement yields
#: to a building pad in the LAST-WORD re-clip that closes the identical
#: class (``groundside._clip_pavement_against_building_pads``, owner
#: CYXY building1: "the post-solve conformance weld's 0.5 m tolerance
#: can bow a ring back ACROSS an edge and nothing later owned the
#: pair").  OFF is the plain ``_g0`` standoff, byte-identical to the
#: pre-round fallback.
_RAMP_WALL_FOOT_ENV = "O4_RAMP_WALL_FOOT"


def ramp_wall_foot_enabled() -> bool:
    return os.environ.get(_RAMP_WALL_FOOT_ENV, "1") == "1"


def reclip_wall_feet_against_faces(layout: "PavementLayout",
                                   min_overlap_m2: float = 1e-3) -> int:
    """LAST-WORD wall-foot re-clip — THE FOOT IS WHAT THE FACE LEAVES.

    §T5 makes the foot and the face ONE PARTITION of one band polygon,
    and at emit they are disjoint by construction.  The post-solve
    T-vertex weld then bows the face's inner edge inboard: its inserts
    carry the DONOR's coordinate, not the projection onto the receiving
    edge, so a welded ring moves by up to ``CONFORMANCE_TOL_M``.  The
    weld is doing its job (an unwelded on-edge node Ruppert-explodes the
    tile mesh) — so the PARTITION is what re-establishes itself: the
    annulus is *what the face does not occupy*, and the foot yields.

    This is the same last-word shape, and the same reasoning, as
    ``groundside._clip_pavement_against_building_pads``; it shares that
    clip's semantics rather than spelling a second one
    (``_clip_shape_yielding_to`` with ``snap_tol=0`` — a pure difference
    only ever shrinks the yielder, so it cannot mint an overlap
    elsewhere).  Runs BEFORE the final tight-tolerance T-weld so the
    clip's new on-edge vertices are themselves welded.

    Returns the number of foot pieces clipped or dropped.
    """
    if not ramp_wall_foot_enabled():
        return 0
    _faces = [s.polygon for s in layout.shapes
              if getattr(s, "ref", "") == "tunnel_wall"
              and getattr(s, "polygon", None) is not None
              and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"]
    if not _faces:
        return 0
    from .groundside import _clip_shape_yielding_to
    _tree = STRtree(_faces)
    _n = 0
    _dropped: set = set()
    for _s in layout.shapes:
        if getattr(_s, "ref", "") != TUNNEL_WALL_FOOT_REF:
            continue
        if (getattr(_s, "polygon", None) is None or _s.polygon.is_empty
                or _s.polygon.geom_type != "Polygon"):
            continue
        for _qk in _tree.query(_s.polygon):
            _face = _faces[int(_qk)]
            try:
                _ov = _s.polygon.intersection(_face).area
            except _GEOM_EXC:                          # pragma: no cover
                continue
            if _ov <= min_overlap_m2:
                continue
            _new = _clip_shape_yielding_to(_s, _face, snap_tol=0.0)
            _n += 1
            if _new is None:
                # The welded face covers the whole shelf here — the face
                # owns that ground; a foot with nothing left is not a
                # sliver worth shipping.
                log_tunnel_piece_removal(
                    layout, _s, "wall-foot re-clip: face covers the shelf")
                _dropped.add(id(_s))
                break
    if _dropped:
        layout.shapes = [s for s in layout.shapes if id(s) not in _dropped]
    return _n


#: §F1 gate (LEMD ramp/road fidelity spec, law 1).  DEFAULT ON.  OFF
#: restores the per-vertex DEM sample the band used before, byte for
#: byte — the control arm every claim about this law is measured
#: against.
_WALL_TOP_STATION_ENV = "O4_WALL_TOP_STATION"


def wall_top_station_law_enabled() -> bool:
    """§F1: is the wall top a function of STATION rather than of each
    node's own DEM sample?

    THE DEFECT IT CLOSES (owner sim read of 1.0.265, LEMD portal at
    40.4984622,-3.5850476).  ``tunnel_wall`` ships as ONE thin band
    ``retaining_wall_width_m`` across, and every one of its ring vertices
    used to take ``dem_at`` AT ITS OWN POSITION.  The two vertices facing
    each other across the band are ~1-1.5 m apart in plan and arbitrarily
    far apart ALONG the ring, so nothing tied their values together: the
    owner measured pairs differing 0.5-1.6 m (610.6/610.1, 608.3/607.7,
    606.2/605.4) and the wall top rendered as a twisted, crumpled ribbon.

    THE LAW: the crest is a function of STATION on the body being walled.
    It is sampled and grade-limited ONCE per ramp body, on that body's own
    exterior ring, and every band vertex reads it at the station of its
    nearest point on that ring — so a cross-band pair, which projects to
    ONE point, carries ONE value by construction rather than by tolerance.
    """
    return os.environ.get(_WALL_TOP_STATION_ENV, "1") == "1"


class _CrestProfile:
    """The wall crest as a function of STATION on one walled body (§F1).

    ``body`` is the ramp polygon the band surrounds.  Its exterior ring
    is the station curve: the DEM is sampled at each of its vertices, the
    TRANSITION LAW is applied ALONG IT (so the crest still stands at
    surrounding grade and descends only within the cap-limited run of the
    portal — the same law the band ring used to run, on the curve that
    actually has a run), and a lookup interpolates that profile at any
    point's station.

    Why the BODY's ring and not the band's: the band ring traverses the
    outer boundary one way and the inner boundary back, so two vertices
    facing each other across the band sit at opposite ends of it.  Every
    point of the band projects onto the body ring, and a cross-band pair
    projects onto the SAME point of it — on a straight run because both
    offsets lie on one normal, at a mitred corner because both offsets lie
    on one ray from that corner.  One station, one value, exactly.
    """

    __slots__ = ("line", "stations", "values", "length")

    def __init__(self, body, dem_at, apt_elev: float, index, max_grade):
        ring = list(body.exterior.coords)
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        self.line = None
        self.stations: list[float] = []
        self.values: list[float] = []
        self.length = 0.0
        if len(ring) < 3:
            return
        surface = []
        for vertex_x, vertex_y in ring:
            sample = dem_at(vertex_x, vertex_y)
            surface.append(
                float(sample if sample is not None else apt_elev))
        values = surface
        if index is not None:
            try:
                # The engine's own transition law — imported here for the
                # same reason ``emit_wall_band`` imports it lazily
                # (``groundside`` is a heavier module than this one needs
                # at import time), never re-spelled.
                from .groundside import transition_law_altitudes
                values, _moved = transition_law_altitudes(
                    ring, surface, index, max_grade)
            except (_GEOM_EXC, ImportError):           # pragma: no cover
                values = surface
        try:
            self.line = LineString(list(ring) + [ring[0]])
        except _GEOM_EXC:                              # pragma: no cover
            self.line = None
            return
        cumulative = 0.0
        self.stations = [0.0]
        for position in range(len(ring)):
            nxt = ring[(position + 1) % len(ring)]
            cumulative += math.hypot(nxt[0] - ring[position][0],
                                     nxt[1] - ring[position][1])
            self.stations.append(cumulative)
        self.length = cumulative
        # The closed profile: the first vertex's value repeats at the end.
        self.values = list(values) + [values[0]]

    def __bool__(self) -> bool:
        return self.line is not None and len(self.values) >= 2

    def at(self, point_xy) -> float | None:
        """The crest value at ``point_xy``'s station, or ``None`` when the
        profile could not be built."""
        if not self:
            return None
        try:
            station = float(self.line.project(Point(point_xy[0],
                                                    point_xy[1])))
        except _GEOM_EXC:                              # pragma: no cover
            return None
        stations = self.stations
        if station <= stations[0]:
            return float(self.values[0])
        if station >= stations[-1]:
            return float(self.values[-1])
        low, high = 0, len(stations) - 1
        while high - low > 1:
            middle = (low + high) // 2
            if stations[middle] <= station:
                low = middle
            else:
                high = middle
        span = stations[high] - stations[low]
        if span <= 1e-12:                              # pragma: no cover
            return float(self.values[low])
        fraction = (station - stations[low]) / span
        return float(self.values[low]
                     + (self.values[high] - self.values[low]) * fraction)


#: The two refs the perimeter band emits: the rising FACE and its FOOT.
#: Every pass that reclips or gates "the wall" reads THIS, so the foot can
#: never be treated as a stranger to the structure it belongs to.
_WALL_BAND_REFS = ("tunnel_wall", TUNNEL_WALL_FOOT_REF)
_TUNNEL_COVER_MIN_PIECE_M2 = 0.5
# Ruling 4's "the tunnel road wins over the pavement it surfaces
# through" applies to the two RAMP-LIKE surfaces: the approach ramp and
# A3's open corridor, whose whole purpose is to lower the ground the
# gap's junctions stand on.  A mouth PLATE keeps its pre-R10 behaviour.
_TUNNEL_PAVEMENT_CUT_REFS = ("tunnel_ramp", "tunnel_corridor")


def _tunnel_pavement_union(layout: "PavementLayout"):
    """Union of every ``tunnel_ramp``/``tunnel_mouth`` polygon emitted so
    far, or ``None`` — the surface R10-2 forbids any cover piece to
    occupy."""
    _polys = [s.polygon for s in layout.shapes
              if getattr(s, "ref", "") in _TUNNEL_PAVEMENT_REFS
              and s.polygon is not None and not s.polygon.is_empty]
    if not _polys:
        return None
    try:
        _u = unary_union(_polys)
    except _GEOM_EXC:
        return None
    return None if _u.is_empty else _u


def _piece_span_m(polygon) -> float | None:
    """The LONGER side of a polygon's minimum rotated rectangle — how far
    the piece REACHES ACROSS, in metres.

    §T2.2 asks whether a post-cut cap fragment still SPANS the portal
    face.  The span of a bar is its long dimension: a cap bar's short
    side is its ``wall_gap_m``-class reach, which is under a metre by
    construction and would condemn every intact cap.
    """
    if polygon is None or polygon.is_empty:
        return None
    try:
        _rect = polygon.minimum_rotated_rectangle
        _c = list(getattr(_rect, "exterior", _rect).coords)
    except (AttributeError, *_GEOM_EXC):                 # pragma: no cover
        return None
    if len(_c) < 4:
        return None
    _sides = [math.hypot(_c[i + 1][0] - _c[i][0], _c[i + 1][1] - _c[i][1])
              for i in range(min(3, len(_c) - 1))]
    return max(_sides) if _sides else None


def _tunnel_cover_pieces(shape, pavement_union, *,
                         min_span_m: float | None = None,
                         layout=None, cluster=None) -> list:
    """``shape`` cut against ``pavement_union`` as a list of BuiltShape.

    R10-2: a wall / roof / cap NEVER covers tunnel pavement, and ALL
    surviving pieces ≥ ``_TUNNEL_COVER_MIN_PIECE_M2`` are kept.  Keeping
    only the largest is a DELETION: a perimeter ring cut by the roadway
    it crosses is three arcs, and dropping two of them left a mouth
    walled on one side (the ``parts9[0]`` rule this replaces).  Altitude
    carries by the existing clip conversions — a piece whose profile
    cannot be answered is dropped rather than shipped with ring-order
    slope semantics its new ring does not have.

    ``min_span_m`` (§T2.2, CAPS ONLY) adds the second survivor gate the
    area floor could never be: a cap is a BAR ACROSS THE PORTAL FACE, so
    a post-cut fragment whose span has fallen below the bore's
    carriageway width is no longer a face — it is a free-standing
    sliver, and the eight LEMD caps measured at 0.5–11 m² are exactly
    that.  ``_TUNNEL_COVER_MIN_PIECE_M2`` admitted every one of them.
    Each drop takes its portal-corridor-claim §1 named line.
    """
    if (pavement_union is None or shape.polygon is None
            or shape.polygon.is_empty):
        return [shape]
    try:
        if not shape.polygon.intersects(pavement_union):
            return [shape]
        _cut = shape.polygon.difference(pavement_union)
    except _GEOM_EXC:
        return [shape]
    if _cut.is_empty:
        return []
    try:
        _old_ring = list(shape.polygon.exterior.coords)
    except _GEOM_EXC:
        _old_ring = []
    if _old_ring and _old_ring[0] == _old_ring[-1]:
        _old_ring = _old_ring[:-1]
    _out: list = []
    for _part in getattr(_cut, "geoms", [_cut]):
        if (_part.geom_type != "Polygon" or _part.is_empty
                or _part.area < _TUNNEL_COVER_MIN_PIECE_M2):
            continue
        _alt = shape.altitude
        _hi, _lo = shape.altitude_high, shape.altitude_low
        _na = None
        if shape.node_altitudes:
            _na = _resample_node_altitudes_nn(
                _part, _old_ring, list(shape.node_altitudes),
                interior_edge_project=True)
            if _na is None:
                continue
        elif _hi is not None and _lo is not None:
            _na = _sloped_rect_clipped_altitudes(
                shape.polygon, _hi, _lo, _part)
            if _na is None:
                continue
            _hi = _lo = None
        _kept = BuiltShape(
            polygon=_part, role=shape.role, ref=shape.ref,
            altitude=_alt, altitude_high=_hi, altitude_low=_lo,
            node_altitudes=_na)
        if min_span_m is not None and _demcut_provenance_gate_on():
            _span = _piece_span_m(_part)
            if _span is not None and _span < float(min_span_m):
                log_tunnel_piece_removal(
                    layout, _kept,
                    "cap fragment no longer spans the portal face",
                    coverage=None, cluster=cluster,
                    verdict=f"span={_span:.2f}m < carriageway "
                            f"{float(min_span_m):.2f}m")
                continue
        _out.append(_kept)
    return _out


def _append_tunnel_cover(layout: "PavementLayout", exclusion_zones: list,
                         pavement_union, shape, *,
                         min_span_m: float | None = None,
                         cluster=None) -> int:
    """Append ``shape``'s R10-2 surviving cover pieces; return how many."""
    _pieces = _tunnel_cover_pieces(shape, pavement_union,
                                   min_span_m=min_span_m,
                                   layout=layout, cluster=cluster)
    for _piece in _pieces:
        layout.shapes.append(_piece)
        exclusion_zones.append(_piece.polygon)
    return len(_pieces)


#: §F4 gate (LEMD ramp/road fidelity spec Amendment 1, ruling 1).
#: DEFAULT ON.  OFF restores the OSM-spelling-only envelope byte for byte.
_SPELLING_ENVELOPE_ENV = "O4_PORTAL_SPELLING_ENVELOPE"

#: How near a DSF chain must pass the portal to be THE SAME ROAD.  One
#: road spelled twice stands a lane or two apart (2.75 m measured at
#: LEMD); a genuinely different road is further off, and
#: ``PORTAL_ROAD_ASSOCIATION_M`` is already this module's answer to
#: "which tagged road is this portal's road" — stated once, not twice.
_SPELLING_MATCH_M = PORTAL_ROAD_ASSOCIATION_M


def portal_spelling_envelope_enabled() -> bool:
    """§F4: does a portal's corridor cover EVERY spelling of its road?

    THE DEFECT IT CLOSES (owner sim read of 1.0.265, LEMD portal at
    40.4984622,-3.5850476).  The corridor's width was already right —
    7.03 m, exactly the ``lanes=2`` the source states — and its centre
    sat 0.3 m off the OSM/feed line it was derived from.  But X-Plane
    draws the DSF VECTOR ROAD NETWORK's spelling of that same road, and
    the two spellings stand 2.75 m apart: inside a 7 m cut the rendered
    ribbon therefore hugged the west wall, which is the owner's "not
    centered on the road".  One spelling's centre is never authority
    over the other's ribbon.
    """
    return os.environ.get(_SPELLING_ENVELOPE_ENV, "1") == "1"


def _spelling_edges(layout, origin, perp, half_carriage: float,
                    known_edges: list) -> list:
    """§F4: the ``(outer_left, outer_right)`` pairs the DSF spellings of
    this portal's road add to the cluster envelope.

    Every draped chain of the sibling DSF road networks passing within
    :data:`_SPELLING_MATCH_M` of ``origin`` is projected onto ``perp``
    and contributes its own half-width — the SAME half the OSM spelling
    carries, because it is the same physical road and the DSF network
    states no width of its own (its columns are a subtype and a draping
    LEVEL FLAG, never metres).

    A spelling already inside the known envelope adds nothing, so a
    tile whose two sources agree emits byte-identically.  Returns ``[]``
    when the law is off, no network is cached, or nothing is in reach —
    the networks are the ones ``object_terrain_assembly`` already
    published on the layout, so this costs no load and no second parser.
    """
    if not portal_spelling_envelope_enabled():
        return []
    networks = _object_bridge_road_networks(layout)
    if not networks:
        return []
    to_meters, _back = _local_meter_projections(layout.anchor)
    origin_point = Point(origin[0], origin[1])
    lo_known = min((e[0] for e in known_edges), default=None)
    hi_known = max((e[1] for e in known_edges), default=None)
    out: list = []
    for network in networks:
        for segment in getattr(network, "segments", ()):  # noqa: B007
            if not segment.is_fully_draped:
                continue          # an elevated ramp flies over the cut
            points = [to_meters(p.longitude, p.latitude)
                      for p in segment.shape_points]
            if len(points) < 2:
                continue
            try:
                line = LineString(points)
                if line.is_empty or line.distance(origin_point) > \
                        _SPELLING_MATCH_M:
                    continue
                near = line.interpolate(line.project(origin_point))
            except _GEOM_EXC:                          # pragma: no cover
                continue
            proj = ((near.x - origin[0]) * perp[0]
                    + (near.y - origin[1]) * perp[1])
            low, high = proj - half_carriage, proj + half_carriage
            if (lo_known is not None and hi_known is not None
                    and low >= lo_known - 1e-9
                    and high <= hi_known + 1e-9):
                continue          # the sources agree — nothing to widen
            out.append((low, high))
    return out


def _emit_portal_cluster(
        cl: list[int], portal_data: list, nodes_m: dict,
        layout: "PavementLayout", exclusion_zones: list,
        carriageway_width_m: float, tunnel_depth_m: float,
        wall_gap_m: float, retaining_wall_width_m: float,
        half_wall_w: float, dem_at,
        airside_gate_union=None,
        object_trench_union=None,
        object_trench_yield_stats=None) -> int:
    """Emit one portal cluster's cap + arm walls + ramp chain
    (plus fork throat / perimeter wall band when gated on).
    Appends the emitted footprints to ``exclusion_zones``.
    Returns 1 when the cluster emitted, 0 when skipped.

    ``object_trench_union`` is the R8-3 yield region
    (:func:`_object_trench_body_union`): where a classified object tunnel
    owns ground AND cut a trench there, this chain's ramp and wall pieces
    yield to it — the object trench is the rendered truth.  ``None``
    (OSM-only tunnels, gate off, no trench emitted) emits as today.
    """
    # All portals in cluster share approximately the same
    # location.  Use the first portal's walk as the canonical
    # arm path; combine widths for divided highways.
    head = portal_data[cl[0]]
    # Slice, never destructure whole: the portal tuple grew DEM-cut
    # fields at indices 8-10 (2026-07-17) and may grow again.
    (portal_nid, _wid_unused, walk_pts, hw_type, apt_elev,
     far_dem, _head_new, head_carriage_w) = head[:8]
    _cl_all_new = all(portal_data[k][6] for k in cl)
    if len(walk_pts) < 2:
        return 0
    # Carriageway width from the way's own ``width=`` / ``lanes=``
    # tags when mapped, else the per-OSM-highway-type table (user
    # 2026-05-03 / 2026-07-16) — computed in ``_gather_portal_walks``
    # and carried per portal.
    carriage_w = head_carriage_w
    half_carriage = 0.5 * carriage_w
    # ── R20-2b (AMENDMENT 1): ONE DATUM ON THE WHOLE PATH ────────────
    # This was ``apt_elev − tunnel_depth_m`` — the 8 m synthetic floor —
    # while ``_gather_portal_walks`` sized the very same chain's run
    # against ``_bore_floor_elevation`` (the R14-3/A-2 clearance floor,
    # ``deck_reference − BRIDGE_ROAD_CLEARANCE_M``).  Two floors for one
    # ramp: at the owner's KCLT portal the sizing floor is ~210.5 and
    # this one was 206.36, so a run correctly sized for a 5.1 m climb
    # was spent on a 9.3 m one and the chain topped 4.26 m under the
    # ground beside it.  The measurement is in the round-20 report; the
    # cliff was the DATUM SPLIT, not the run length.  R14-3/A-2 already
    # ruled what the floor is — this is that ruling reaching the emitter.
    #
    # The cluster takes the DEEPEST member floor, the same "one depth per
    # system" rule the facing pairs take for their mouths, so a cluster's
    # two carriageways cannot sit at two depths.  ``tunnel_depth_m``
    # survives as the fallback for a portal that recorded no floor at all
    # (the pre-R20 tuple shape, and the mid-field portal with no deck
    # reference — where ``_bore_floor_elevation`` itself returns exactly
    # this expression, so the fallback is the same number by
    # construction).  SCOPE: the SIZED path only.  The light-touch and
    # facing branches above return before this line and keep their own
    # mouth-grade datum untouched — whether the legacy datum should
    # retire there too is a separate ruling this round does not take.
    _cl_floors = [portal_data[k][13] for k in cl
                  if len(portal_data[k]) > 13
                  and portal_data[k][13] is not None]
    elev_low = (min(float(_f) for _f in _cl_floors) if _cl_floors
                else apt_elev - tunnel_depth_m)
    elev_high = far_dem
    # Compute the walk's cumulative distance for elevation
    # interpolation.
    cum_dists = [0.0]
    for i in range(1, len(walk_pts)):
        cum_dists.append(cum_dists[-1] + math.hypot(
            walk_pts[i][0] - walk_pts[i - 1][0],
            walk_pts[i][1] - walk_pts[i - 1][1]))
    total_walk = cum_dists[-1]
    if total_walk < 5.0:
        if os.environ.get("O4_TUNNEL_DEBUG") == "1":
            print(f"    [tunnel-drop] cluster at "
                  f"({walk_pts[0][0]:.0f},{walk_pts[0][1]:.0f}): "
                  f"walk only {total_walk:.1f} m")
        return 0
    # Cluster spread for combined width: project each cluster
    # member's portal node onto the perpendicular at the head
    # portal.  Cap, arms and ramps are all centred on the
    # cluster centroid (midpoint between carriageway portals),
    # not on the head portal — user 2026-05-03 ("trunk highway
    # tunnels not centered on OSM ways, offset with one edge on
    # one of the ways").  We apply a constant translation to
    # ``walk_pts`` so every downstream geometry inherits the
    # centring; this keeps the cap and ramps coplanar across
    # both carriageways of a divided highway.  Constant shift
    # is exact at the portal and stays close-to-correct for the
    # length of the walk because parallel carriageways follow
    # parallel curves.
    first_seg = (walk_pts[1][0] - walk_pts[0][0],
                 walk_pts[1][1] - walk_pts[0][1])
    first_len = math.hypot(*first_seg)
    if first_len < 0.1:
        return 0
    first_dir = (first_seg[0] / first_len,
                 first_seg[1] / first_len)
    first_perp = (-first_dir[1], first_dir[0])
    # Project each member's portal node onto the perpendicular AND
    # carry its own carriageway half-width, so the combined bore spans
    # from the leftmost member's OUTER edge to the rightmost member's
    # OUTER edge — covering the whole tunnel mouth even when the
    # members differ in width (e.g. a 9 m road + a 5 m rail).  Using
    # only the head member's half-width left the bore short on the
    # wider member's side (user 2026-06-13).
    spans = []          # centre-projection per member (for divergence)
    _edges = []         # (outer_left, outer_right) per member
    for k in cl:
        ni = portal_data[k][0]
        if ni not in nodes_m:
            continue
        p = nodes_m[ni]
        proj = ((p[0] - walk_pts[0][0]) * first_perp[0]
                + (p[1] - walk_pts[0][1]) * first_perp[1])
        half_k = 0.5 * portal_data[k][7]
        spans.append(proj)
        _edges.append((proj - half_k, proj + half_k))
    cluster_span = max(spans) - min(spans) if spans else 0.0
    # ── §F4: THE ENVELOPE OF EVERY SPELLING OF THE CROSSING ROAD ─────
    # (LEMD ramp/road fidelity spec Amendment 1 ruling 1.)  The members
    # above are the OSM/feed spelling of the road.  X-Plane draws the DSF
    # VECTOR NETWORK's spelling, and at LEMD the two stand 2.75 m apart:
    # a cut centred on ours put the rendered ribbon hard against a wall.
    # The cut exists to cover what the sim RENDERS as well as what we
    # emit, so every spelling within reach contributes its own outer
    # edges to the envelope and the centre is the envelope's midpoint.
    # ``cluster_span`` — the DIVERGENCE frame the fork test reads — is
    # deliberately NOT touched: two spellings of one road are not two
    # diverging arms, and feeding this into that test would fork a road
    # that never splits.
    _edges += _spelling_edges(
        layout, walk_pts[0], first_perp, half_carriage, _edges)
    if _edges:
        _ml = min(e[0] for e in _edges)
        _mr = max(e[1] for e in _edges)
        cluster_perp_offset = 0.5 * (_ml + _mr)
        combined_half = 0.5 * (_mr - _ml)
    else:
        cluster_perp_offset = 0.0
        combined_half = half_carriage
    if abs(cluster_perp_offset) > 1e-6:
        shift_x = first_perp[0] * cluster_perp_offset
        shift_y = first_perp[1] * cluster_perp_offset
        walk_pts = [(p[0] + shift_x, p[1] + shift_y)
                    for p in walk_pts]

    def _build_wall_segment(p_a: tuple[float, float],
                             p_b: tuple[float, float],
                             perp_off: float
                             ) -> Polygon | None:
        """4-corner wall polygon parallel to segment ``a-b``,
        offset by ``perp_off`` from the segment's centre line,
        ``retaining_wall_width_m`` thick."""
        seg = (p_b[0] - p_a[0], p_b[1] - p_a[1])
        slen = math.hypot(*seg)
        if slen < 0.1:
            return None
        ux, uy = seg[0] / slen, seg[1] / slen
        nx, ny = -uy, ux
        # Sign of perp_off picks which side.  Inner edge of
        # wall is at perp_off, outer edge at perp_off ± width.
        inner = perp_off
        outer = (perp_off + half_wall_w * 2.0
                 if perp_off >= 0
                 else perp_off - half_wall_w * 2.0)
        corners = [
            (p_a[0] + nx * inner, p_a[1] + ny * inner),
            (p_b[0] + nx * inner, p_b[1] + ny * inner),
            (p_b[0] + nx * outer, p_b[1] + ny * outer),
            (p_a[0] + nx * outer, p_a[1] + ny * outer),
        ]
        try:
            p = Polygon(corners)
            if not p.is_valid:
                p = p.buffer(0)
            if p.geom_type == "Polygon" and not p.is_empty:
                return p
        except _GEOM_EXC:
            return None
        return None
    # AIRSIDE / DOUBLE-EMIT GATE (user 2026-06-12, KPHL): with
    # small_roads + railways feeding this emitter, service-tunnel
    # bores UNDER the apron/terminal complex now qualify — but a
    # tunnel under solid pavement has no visible ramp to model
    # (the surface above it is the graded apron).  The
    # discriminator is the RAMP, not the portal: a legitimate
    # portal's ramp leads AWAY from pavement (SPJC's runway
    # tunnels: portals at the pavement FACE, ramps off-airport),
    # a buried bore's ramp stays ON it (KPHL terminal-area
    # service tunnels).  Skip when more than half the ramp walk
    # runs over airside pavement; also skip a cap landing inside
    # an already-emitted portal's footprint (road and rail bores
    # of one tunnel cluster emitting twice).
    try:
        if _cl_all_new and exclusion_zones:
            if unary_union(exclusion_zones).buffer(2.0).contains(
                    Point(walk_pts[0])):
                if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                    print(f"    [tunnel-drop] cluster at "
                          f"({walk_pts[0][0]:.0f},"
                          f"{walk_pts[0][1]:.0f}): inside an "
                          f"emitted portal's exclusion zone")
                return 0
    except _GEOM_EXC:
        pass
    # 1) Cap wall AT the portal cluster's centroid, perpendicular
    #    to the first segment.  The cap's centre line passes
    #    through the cluster centroid (so divided-highway
    #    tunnels are centered between the carriageways, user
    #    2026-05-03), its width spans the combined carriageways
    #    + 2 × wall_gap, its thickness is
    #    retaining_wall_width_m.
    # Index of the first shape THIS cluster emits — the gate-on
    # perimeter wall band (emitted at cluster end) unions every
    # tunnel_ramp from here on.
    _cl_start_idx = len(layout.shapes)
    # Far (surface) end of every ramp arm this cluster emits —
    # the perimeter wall band must be cut OPEN there (the road
    # continues at grade; a band crossing it walls off the live
    # roadway).  (endpoint, previous point, half width) per arm.
    _cl_arm_ends: list = []
    cap_half_len = combined_half + wall_gap_m
    cap_centre = walk_pts[0]
    c0 = (cap_centre[0] + first_perp[0] * cap_half_len,
          cap_centre[1] + first_perp[1] * cap_half_len)
    c1 = (cap_centre[0] - first_perp[0] * cap_half_len,
          cap_centre[1] - first_perp[1] * cap_half_len)
    # Move cap thickness INTO the tunnel direction (negative
    # first_dir) — cap occupies the strip from portal back
    # by retaining_wall_width_m.
    c0_back = (c0[0] - first_dir[0] * retaining_wall_width_m,
               c0[1] - first_dir[1] * retaining_wall_width_m)
    c1_back = (c1[0] - first_dir[0] * retaining_wall_width_m,
               c1[1] - first_dir[1] * retaining_wall_width_m)
    # ── DEM-CUT MODE (user 2026-07-17, EGGW): the mesh already has
    # the ramps.  When every member's walk found the approach cut
    # already carved in the DEM (lidar bare-earth inset), synthetic
    # ramps/walls/throat would fight the real — often steeper —
    # lidar profile, so emit only the pieces the bare-earth model
    # CANNOT supply: the portal face cap at airport grade (seats a
    # portal object whose anchor sits on the face at DECK grade), a
    # short mouth plate at the DEM's own road grade (keeps the face
    # wall crisp instead of a Triangle smear), and flat roof plates
    # at airport grade over the covered bore between the face and
    # the airside pavement (a bare-earth model strips the structure
    # above the bore, leaving an open trench that pavement grading
    # alone does not fill).
    #
    # A3 (owner ruling 2026-08-11) routes FACING same-road portals here
    # too, whatever the probe said: the gap between two close mouths of
    # one road is an OPEN CUT that :func:`_emit_facing_corridors` lays
    # whole, so a ramp climbing to grade inside it would be geometry
    # arguing with the corridor beneath it.  What such a portal still
    # owes is exactly this mode's list — a face at its mapped station at
    # bore depth, and the roof over its own covered bore.
    _cl_facing = all(len(portal_data[k]) > 14 and portal_data[k][14]
                     for k in cl)
    if _cl_facing or all(len(portal_data[k]) > 11 and portal_data[k][8]
                         for k in cl):
        emitted_any = False
        # The grade the face cap holds: the measured cross-road deck
        # beside the trench (index 11) — never ``apt_elev``, whose
        # mid-field fallback samples the trench floor itself.
        deck_grade = max(
            (portal_data[k][11] for k in cl
             if portal_data[k][11] is not None),
            default=apt_elev)
        # The clearance floor below is only lawful against a MEASURED
        # deck; ``apt_elev`` is the mid-field fallback that samples the
        # trench floor itself, and clamping to it would sink the mouth
        # a clearance below its own road.
        _deck_ref_measured = any(portal_data[k][11] is not None
                                 for k in cl)
        mouth_grade = min(
            (portal_data[k][9] for k in cl
             if portal_data[k][9] is not None),
            default=apt_elev - tunnel_depth_m)
        # R10-3 depth floor, the same helper the A3 corridor uses so a
        # mouth and the corridor it stands in cannot disagree.
        if _deck_ref_measured:
            mouth_grade = _mouth_grade_with_clearance(
                mouth_grade, deck_grade)
        # R10-2: the cover pieces below are cut against the tunnel
        # pavement already on the layout (earlier clusters); this
        # cluster's own mouth is cut into them by the finalize pass,
        # which sees the whole build.
        _pavement_u = _tunnel_pavement_union(layout)
        # 1) GRADED roof cover per member, emitted FIRST: a chain of
        #    quads along each carriageway's own bore from ITS mapped
        #    face to the airside pavement edge (upstream truncation at
        #    the bore midpoint keeps it off the partner's half), every
        #    corner carrying its own ABSOLUTE altitude (user
        #    2026-07-17: per-corner values — the sloped high/low rect
        #    encoding is 4-corner-fragile).  Corner altitudes lerp
        #    from face-top grade to the pavement-seam deck.  Quads
        #    share corners only with each other at equal values, so
        #    node-bucket sharing stays value-consistent (★arbitrary
        #    difference polygons instead LOSE per-node values to
        #    foreign ways' buckets — measured EGGW v6).
        roof_polygons: list = []
        for k in cl:
            bore_pts = portal_data[k][10]
            if not bore_pts or len(bore_pts) < 2:
                continue
            face_deck = (portal_data[k][11]
                         if portal_data[k][11] is not None
                         else deck_grade)
            inner_deck = (portal_data[k][12]
                          if len(portal_data[k]) > 12
                          and portal_data[k][12] is not None
                          else face_deck)
            try:
                bore_line = LineString(bore_pts)
                clear_line = bore_line
                if airside_gate_union is not None:
                    clipped = bore_line.difference(airside_gate_union)
                    pieces = [g for g in getattr(
                        clipped, "geoms", [clipped])
                        if g.geom_type == "LineString"
                        and g.length > 1.0]
                    # Only the piece CONTAINING the face end is the
                    # roof strip; when the pavement reaches (almost)
                    # to the face there is nothing to cover — never
                    # fall back to a beyond-pavement piece (★measured
                    # EGGW v9: nearest-piece selection wandered to a
                    # mid-body segment INSIDE the crossing and graded
                    # quads over the taxiway).
                    face_point = Point(bore_pts[0])
                    containing = [g for g in pieces
                                  if g.distance(face_point) < 1.0]
                    if containing:
                        clear_line = containing[0]
                    else:
                        continue
            except _GEOM_EXC:
                continue
            clear_length = clear_line.length
            if clear_length < 2.0:
                continue
            # Refine the inner deck at the strip's actual far end
            # (the pavement seam) when the DEM offers a sample there.
            try:
                far_point = clear_line.interpolate(clear_length)
                near_point = clear_line.interpolate(
                    max(0.0, clear_length - 5.0))
                _fdx = far_point.x - near_point.x
                _fdy = far_point.y - near_point.y
                _flen = math.hypot(_fdx, _fdy) or 1.0
                _fperp = (-_fdy / _flen, _fdx / _flen)
                half_member = 0.5 * portal_data[k][7]
                for _offset in (half_member + 6.0, half_member + 15.0):
                    for _sign in (+1.0, -1.0):
                        _side = dem_at(
                            far_point.x + _fperp[0] * _offset * _sign,
                            far_point.y + _fperp[1] * _offset * _sign)
                        if _side is not None and _side > inner_deck:
                            inner_deck = float(_side)
            except _GEOM_EXC:
                pass
            half_roof = 0.5 * portal_data[k][7] + wall_gap_m
            target_quad_m = 12.0
            quad_count = max(1, math.ceil(clear_length / target_quad_m))
            for quad_index in range(quad_count):
                s_low = clear_length * quad_index / quad_count
                s_high = clear_length * (quad_index + 1) / quad_count
                try:
                    p_low = clear_line.interpolate(s_low)
                    p_high = clear_line.interpolate(s_high)
                except _GEOM_EXC:
                    continue
                _qdx = p_high.x - p_low.x
                _qdy = p_high.y - p_low.y
                _qlen = math.hypot(_qdx, _qdy)
                if _qlen < 0.5:
                    continue
                _qperp = (-_qdy / _qlen, _qdx / _qlen)
                elevation_low = round(
                    face_deck + (inner_deck - face_deck)
                    * (s_low / clear_length), 2)
                elevation_high = round(
                    face_deck + (inner_deck - face_deck)
                    * (s_high / clear_length), 2)
                corners = [
                    (p_high.x + _qperp[0] * half_roof,
                     p_high.y + _qperp[1] * half_roof),
                    (p_low.x + _qperp[0] * half_roof,
                     p_low.y + _qperp[1] * half_roof),
                    (p_low.x - _qperp[0] * half_roof,
                     p_low.y - _qperp[1] * half_roof),
                    (p_high.x - _qperp[0] * half_roof,
                     p_high.y - _qperp[1] * half_roof),
                ]
                try:
                    quad = Polygon(corners)
                    if not quad.is_valid or quad.is_empty \
                            or quad.area < 2.0:
                        continue
                except _GEOM_EXC:
                    continue
                # 4-corner high/low encoding (corners 0,3 = high /
                # 1,2 = low).  ★Per-corner ``node_altitudes`` on
                # these post-solve quads measurably LOSES most values
                # between emission and the written patch (EGGW v9:
                # ways shipped with alt_abs on 2 of 6 nodes and the
                # strip collapsed toward the trench) — mechanism not
                # yet root-caused; until it is, the high/low pair is
                # the encoding that demonstrably reaches the mesh.
                if abs(elevation_high - elevation_low) >= 0.1:
                    _roof_shape = BuiltShape(
                        polygon=quad,
                        role=ROLE_RETAINING_WALL,
                        ref="tunnel_roof",
                        altitude_high=elevation_high,
                        altitude_low=elevation_low)
                else:
                    _roof_shape = BuiltShape(
                        polygon=quad,
                        role=ROLE_RETAINING_WALL,
                        ref="tunnel_roof",
                        altitude=round(0.5 * (
                            elevation_high + elevation_low), 2))
                for _piece in _tunnel_cover_pieces(
                        _roof_shape, _pavement_u):
                    layout.shapes.append(_piece)
                    roof_polygons.append(_piece.polygon)
                    exclusion_zones.append(_piece.polygon)
                    emitted_any = True
        try:
            roof_union = (unary_union(roof_polygons)
                          if roof_polygons else None)
        except _GEOM_EXC:
            roof_union = None
        # 2) Face cap: a flat bar at the deck grade across the
        #    combined carriageways at the cluster face line.  Overlap
        #    with the roof cover is at the SAME grade — benign.
        try:
            # R16-2b (round-16 amendment 1): THE CAP FACE IS OWNED
            # GEOMETRY TOO.  The cap used to stop at the portal station
            # while the mouth plate starts ``wall_gap_m`` further out,
            # leaving the same unowned strip the wall bands had —
            # measured at KCLT: 3 cap nodes 1.16/5.10 m above the
            # pavement across a 0.60-1.71 m gap no shape owned.  The cap
            # now reaches the mouth plate's NEAR EDGE, carries the
            # mouth's grade on the two vertices it shares with it (the
            # plate's own near corners, coincident by construction and
            # welded by the canonical point registry), and keeps the
            # deck grade on its crest.  Its outboard half-width and its
            # back face are unchanged, so nothing outside the cap moved.
            # HOW FAR THE FACE REACHES (attempt 2): to the tunnel
            # pavement it actually faces, not a fixed ``wall_gap_m``.
            # Measured at KCLT after attempt 1: 2 of 3 unowned cap nodes
            # closed, and the third stood 1.04 m from CLAIMED ROAD
            # pavement (the R14 claim) rather than 0.6 m from a mouth
            # plate — a 0.6 m reach could not span it, and R10-2 then
            # cut the overhang back off.  Reaching exactly the nearest
            # tunnel pavement leaves zero-area contact, so the cover cut
            # is a no-op and no strip is left unowned.  Bounded by the
            # cap's own footprint so a cap far from any pavement is
            # unchanged.
            _cap_reach = wall_gap_m
            try:
                if _pavement_u is not None:
                    _face_line = LineString([c0, c1])
                    _d_face = float(_pavement_u.distance(_face_line))
                    if _d_face > 0.0:
                        _cap_reach = min(max(_d_face, wall_gap_m),
                                         wall_gap_m
                                         + retaining_wall_width_m)
            except _GEOM_EXC:
                _cap_reach = wall_gap_m
            # ── §T2.2: THE MOUTH WINS (R16-2b vs R10-2) ──────────────
            # Attempt 2's pavement-seeking reach above can run
            # ``retaining_wall_width_m`` PAST the mouth plate's near edge
            # (``_mouth_near`` below is ``wall_gap_m`` from this same
            # origin), and R10-2 then cuts the overhang back off against
            # the mouth — which is how all eight LEMD caps came out as
            # 0.5–11 m² slivers.  The cap face therefore stops AT the
            # mouth plate's near edge and never reaches into it: the two
            # surfaces share that boundary, so R16-2b's annulus stays
            # OWNED (zero-width, nothing unowned between them) and the
            # cap is never cut by the mouth it faces.
            if _demcut_provenance_gate_on():
                _cap_reach = min(_cap_reach, wall_gap_m)
            _cap_f = (cap_centre[0] + first_dir[0] * _cap_reach,
                      cap_centre[1] + first_dir[1] * _cap_reach)
            _cap_ring = [
                (_cap_f[0] + first_perp[0] * cap_half_len,
                 _cap_f[1] + first_perp[1] * cap_half_len),
                (_cap_f[0] + first_perp[0] * combined_half,
                 _cap_f[1] + first_perp[1] * combined_half),
                (_cap_f[0] - first_perp[0] * combined_half,
                 _cap_f[1] - first_perp[1] * combined_half),
                (_cap_f[0] - first_perp[0] * cap_half_len,
                 _cap_f[1] - first_perp[1] * cap_half_len),
                c1_back, c0_back,
            ]
            _cap_alts = [round(deck_grade, 2),
                         round(mouth_grade, 2), round(mouth_grade, 2),
                         round(deck_grade, 2),
                         round(deck_grade, 2), round(deck_grade, 2)]
            cap_poly = Polygon(_cap_ring)
            if not cap_poly.is_valid:
                cap_poly = cap_poly.buffer(0)
                _cap_alts = None          # ring order no longer aligned
            if (cap_poly.geom_type == "Polygon"
                    and not cap_poly.is_empty):
                if _append_tunnel_cover(
                        layout, exclusion_zones, _pavement_u,
                        BuiltShape(
                            polygon=cap_poly,
                            role=ROLE_RETAINING_WALL,
                            ref="tunnel_cap",
                            altitude=(round(deck_grade, 1)
                                      if _cap_alts is None else None),
                            node_altitudes=(
                                None if _cap_alts is None
                                else _cap_alts + [_cap_alts[0]])),
                        min_span_m=carriage_w,
                        cluster=cap_centre):
                    emitted_any = True
        except _GEOM_EXC:
            pass
        # 3) Mouth plate at the DEM's own road grade, MINUS the roof
        #    cover: with staggered twin-carriageway mapped ends the
        #    cluster-wide rect crosses the more-recessed member's
        #    bore, where the roof (real structure at deck grade) must
        #    win (measured EGGW v7: 28.7 m² of road-grade plate under
        #    the partner's roof).  A flat plate tolerates any ring
        #    shape, so the difference result ships as-is.
        try:
            _mouth_near = wall_gap_m
            _mouth_far = wall_gap_m + TUNNEL_MOUTH_PLATE_LENGTH_M
            _mc = cap_centre
            _m0 = (_mc[0] + first_dir[0] * _mouth_near,
                   _mc[1] + first_dir[1] * _mouth_near)
            _m1 = (_mc[0] + first_dir[0] * _mouth_far,
                   _mc[1] + first_dir[1] * _mouth_far)
            mouth_geometry = Polygon([
                (_m0[0] + first_perp[0] * combined_half,
                 _m0[1] + first_perp[1] * combined_half),
                (_m1[0] + first_perp[0] * combined_half,
                 _m1[1] + first_perp[1] * combined_half),
                (_m1[0] - first_perp[0] * combined_half,
                 _m1[1] - first_perp[1] * combined_half),
                (_m0[0] - first_perp[0] * combined_half,
                 _m0[1] - first_perp[1] * combined_half),
            ])
            if not mouth_geometry.is_valid:
                mouth_geometry = mouth_geometry.buffer(0)
            if roof_union is not None and not mouth_geometry.is_empty:
                mouth_geometry = mouth_geometry.difference(roof_union)
            for part in getattr(
                    mouth_geometry, "geoms", [mouth_geometry]):
                if part.geom_type != "Polygon" or part.is_empty:
                    continue
                if part.area < 1.0:
                    # §T8.3 / portal-corridor-claim §1: NAME IT.  This is
                    # one of the item-4 removal sites — a mouth plate the
                    # roof difference has cut below the area floor used to
                    # vanish with no record, and "the mouth is missing" is
                    # then indistinguishable from "the mouth was never
                    # admitted".
                    log_tunnel_piece_removal(
                        layout,
                        BuiltShape(polygon=part, role=ROLE_TUNNEL_RAMP,
                                   ref="tunnel_mouth",
                                   altitude=round(mouth_grade, 2)),
                        "mouth plate below the 1 m2 area floor after the "
                        "roof difference",
                        cluster=cap_centre)
                    continue
                _mouth_shape = BuiltShape(
                    polygon=part,
                    role=ROLE_TUNNEL_RAMP,
                    ref="tunnel_mouth",
                    altitude=round(mouth_grade, 2))
                layout.shapes.append(_mouth_shape)
                # A7(c): this mode emits cap + roof and NO side walls, by
                # owner ruling (2026-07-17, "no tunnel ramp running around
                # the entire parking garage").  Its mouths are therefore
                # exempt from the R10-2 unwalled-mouth finding — reporting
                # a by-design shape as a defect trains reviewers to ignore
                # the check.
                try:
                    _lt = getattr(layout, "_tunnel_light_touch_mouths",
                                  None)
                    if _lt is None:
                        _lt = set()
                        layout._tunnel_light_touch_mouths = _lt
                    _lt.add(id(_mouth_shape))
                except (AttributeError, TypeError):
                    pass
                exclusion_zones.append(part)
                emitted_any = True
        except _GEOM_EXC:
            pass
        if os.environ.get("O4_TUNNEL_DEBUG") == "1":
            print(f"    [tunnel-dem-cut] cluster at "
                  f"({walk_pts[0][0]:.0f},{walk_pts[0][1]:.0f}): "
                  f"cap+roof@{deck_grade:.1f}, mouth@{mouth_grade:.1f}, "
                  f"no synthetic ramps (DEM cut present)")
        return 1 if emitted_any else 0
    # Gate ON folds the cap into the continuous perimeter wall band
    # (which wraps the portal end too); gate OFF keeps the separate
    # flat cap.
    if not TUNNEL_FORK_THROAT:
        try:
            cap_poly = Polygon([c0, c1, c1_back, c0_back])
            if not cap_poly.is_valid:
                cap_poly = cap_poly.buffer(0)
            if (cap_poly.geom_type == "Polygon"
                    and not cap_poly.is_empty):
                # R10-2: never over tunnel pavement already emitted.
                _append_tunnel_cover(
                    layout, exclusion_zones,
                    _tunnel_pavement_union(layout),
                    BuiltShape(
                        polygon=cap_poly,
                        role=ROLE_RETAINING_WALL,
                        ref="tunnel_cap",
                        altitude=round(apt_elev, 1)),
                    min_span_m=carriage_w,
                    cluster=cap_centre)
        except _GEOM_EXC:
            pass
    # Per user 2026-05-04: the cap + arm walls form a continuous
    # "U" — arms touch the cap on both sides (their inner-front
    # corner sits exactly at the cap's outer-front corner, since
    # ``cap_half_len`` and ``arm_off - half_wall_w`` both equal
    # ``combined_half + wall_gap_m``).  Only the RAMP starts
    # ``wall_gap_m`` further into the tunnel so its near edge
    # (lowest elevation) leaves the same clearance from the cap
    # as it already does from the side walls.  We achieve that
    # by offsetting the FIRST ramp segment's near corners
    # individually below; ``walk_pts`` itself stays at the portal.

    # Y-split throat polygons emitted for THIS cluster: a branch ramp
    # segment mostly covered by the throat is redundant pavement at
    # the same elevation — skip it rather than emit an overlapping
    # sloped rect (user 2026-07-04: ramps must not overlap; a sloped
    # ``altitude_high/low`` rect cannot be clipped without breaking
    # its two-corner elevation semantics).
    cluster_throat_polys: list = []

    def _emit_chain(chain_pts, chain_half, e_lo_c, e_hi_c,
                    cap_gap):
        """Emit arm walls + ramp chain along ``chain_pts`` at
        half-width ``chain_half``, elevations linear from
        ``e_lo_c`` (start) to ``e_hi_c`` (end).  ``cap_gap``
        applies the first-segment wall_gap offset (the chain
        abuts the portal cap).  Extracted verbatim from the
        single-ramp emit so the parallel-bores path is
        unchanged; the Y-split calls it once for the shared
        throat and once per diverging branch (user 2026-06-12,
        KPHL RWY 26 north portal: road+rail share the tunnel,
        then fork right outside — the ramp must fork too).

        RAMP-INTERNAL CORNER AGREEMENT (spec
        ``tunnel-ramp-cut-boundaries-spec.md`` §2): returns the
        REALIZED top elevation — ``e_hi_c`` after the effective-space
        grade clamp below.  The clamp is what made the bore's far edge
        and the throat's flat landing disagree by 0.96 m at the shared
        cross-edge nodes (OTHH ways -11758/-11759): the caller planned
        ``e_div``, the bore realized something lower, and the throat
        (and the arms hanging off it) kept the plan.  The whole profile
        is piecewise-linear, so the correct shared value is simply the
        one the bore actually reached — the caller re-seats the throat
        and the arms on it."""
        n_c = len(chain_pts)
        if n_c < 2:
            return e_hi_c
        c_cums = [0.0]
        for i in range(1, n_c):
            c_cums.append(c_cums[-1] + math.hypot(
                chain_pts[i][0] - chain_pts[i - 1][0],
                chain_pts[i][1] - chain_pts[i - 1][1]))
        c_total = c_cums[-1]
        if c_total < 1.0:
            return e_hi_c
        c_first = (chain_pts[1][0] - chain_pts[0][0],
                   chain_pts[1][1] - chain_pts[0][1])
        c_first_len = math.hypot(*c_first)
        if c_first_len < 0.1:
            return e_hi_c
        c_first_dir = (c_first[0] / c_first_len,
                       c_first[1] / c_first_len)
        arm_off = chain_half + wall_gap_m + half_wall_w
        verts_perp = []
        verts_scale = []
        for i in range(n_c):
            if i == 0:
                s = (chain_pts[1][0] - chain_pts[0][0],
                     chain_pts[1][1] - chain_pts[0][1])
                sl = math.hypot(*s)
                verts_perp.append((-s[1] / sl, s[0] / sl))
                verts_scale.append(1.0)
            elif i == n_c - 1:
                s = (chain_pts[i][0] - chain_pts[i - 1][0],
                     chain_pts[i][1] - chain_pts[i - 1][1])
                sl = math.hypot(*s)
                verts_perp.append((-s[1] / sl, s[0] / sl))
                verts_scale.append(1.0)
            else:
                s1 = (chain_pts[i][0] - chain_pts[i - 1][0],
                      chain_pts[i][1] - chain_pts[i - 1][1])
                s2 = (chain_pts[i + 1][0] - chain_pts[i][0],
                      chain_pts[i + 1][1] - chain_pts[i][1])
                l1 = math.hypot(*s1)
                l2 = math.hypot(*s2)
                u1 = (s1[0] / l1, s1[1] / l1)
                u2 = (s2[0] / l2, s2[1] / l2)
                avg = ((u1[0] + u2[0]) / 2.0,
                       (u1[1] + u2[1]) / 2.0)
                al = math.hypot(*avg)
                if al < 1e-6:
                    verts_perp.append((-u1[1], u1[0]))
                    verts_scale.append(1.0)
                    continue
                tangent = (avg[0] / al, avg[1] / al)
                perp = (-tangent[1], tangent[0])
                dot = u1[0] * u2[0] + u1[1] * u2[1]
                cos_half = max(0.1, math.sqrt(
                    max(0.0, (1.0 + dot) / 2.0)))
                verts_perp.append(perp)
                verts_scale.append(1.0 / cos_half)

        def _vertex_offset(idx, off):
            px, py = chain_pts[idx]
            nx, ny = verts_perp[idx]
            scaled = off * verts_scale[idx]
            return (px + nx * scaled, py + ny * scaled)

        # Station elevations lerp over EFFECTIVE cumulative length: each
        # segment weighs min(centerline, both road-edge lengths).  On a
        # bend the miter join shortens the INNER quad edge below the
        # centerline arc, so a centerline-proportional Δe read as an
        # over-cap grade along that edge (SPJC 2026-07-06: 0.70 m over a
        # 15.25 m inner edge on a ~20 m segment = 4.59 % vs the 4 % ramp
        # law).  Weighting by the shortest edge caps every quad-edge
        # grade at ~total_de/Σeffective, which the walk sizing keeps at
        # the plan grade (the safety margin absorbs the tiny Σ shrink).
        effective_cums = [0.0]
        for i in range(n_c - 1):
            seg_len = c_cums[i + 1] - c_cums[i]
            edge_plus = math.dist(_vertex_offset(i, +chain_half),
                                  _vertex_offset(i + 1, +chain_half))
            edge_minus = math.dist(_vertex_offset(i, -chain_half),
                                   _vertex_offset(i + 1, -chain_half))
            effective_cums.append(
                effective_cums[-1]
                + min(seg_len, edge_plus, edge_minus))
        effective_total = effective_cums[-1]
        if effective_total < 1.0:
            return e_hi_c
        # ── THE DECK REQUIRES STANDARD DEPTH (RULINGS 2026-08-30f) ───
        # "The tunnel cut stays AT FULL BORE DATUM from the tunnel mouth
        # all the way to the bridge, passes under the deck at that depth
        # (covered stretch), and the ramp up to DEM begins on the OTHER
        # side of the bridge deck."
        #
        # So the climb does not start at the mouth: it starts where the
        # chain LEAVES the last deck it passes under.  Everything before
        # that station holds ``e_lo_c`` — the bore floor — which is what
        # gives the deck its ``BRIDGE_ROAD_CLEARANCE_M`` by construction
        # instead of by moving the deck up.  MEASURED at LEMD (round 1):
        # the walk surfaced to 600.17-600.95 m under the owner's span
        # against a 598.45 m bore, leaving 0.73-0.91 m of cover where the
        # law requires 5.1 m; that is the defect this closes.
        #
        # ``climb_start_eff`` is 0.0 wherever no deck lies on the chain,
        # which makes every other airport's walk byte-identical.
        climb_start_eff = 0.0
        try:
            from .road_bridge_deck import (
                terrain_deck_union as _deck_union_of)
            _deck_u = _deck_union_of(layout)
        except Exception:                                # pragma: no cover
            _deck_u = None
        if _deck_u is not None:
            from shapely.geometry import LineString as _LS
            for _i in range(n_c - 1):
                try:
                    if _LS([chain_pts[_i],
                            chain_pts[_i + 1]]).intersects(_deck_u):
                        climb_start_eff = max(climb_start_eff,
                                              effective_cums[_i + 1])
                except _GEOM_EXC:                        # pragma: no cover
                    continue
            if climb_start_eff > 0.0:
                UI.vprint(1,
                    f"  [bridge-deck] §4/2026-08-30f: this portal walk "
                    f"passes under a road bridge deck — the cut holds "
                    f"bore datum {e_lo_c:.2f} m for the first "
                    f"{climb_start_eff:.1f} m (the covered stretch) and "
                    f"the climb to DEM starts BEYOND the deck, over the "
                    f"remaining {effective_total - climb_start_eff:.1f} m.")
        climb_total = effective_total - climb_start_eff
        if climb_total < 1.0:
            # The deck covers the whole walk: the cut stays at bore datum
            # for all of it and there is no climb left to grade.
            return e_lo_c
        # EFFECTIVE-SPACE GRADE CLAMP (2026-07-17, SPJC #499/#500/#502):
        # the walk TRUNCATION sizes the chain on CENTERLINE length
        # (drop / plan_grade), but elevations lerp over the EFFECTIVE
        # (min-edge) length — on a curving chain the miter-shortened
        # edges shrink Σeffective 15-20 % below the centerline sum, so
        # every quad edge realized drop/Σeffective = plan × (Σcenter /
        # Σeffective) = 4.13-4.21 % against the 4 % ramp law (the
        # 0.5 pp safety margin only covers rounding).  Clamp the
        # chain-top elevation so the effective-space grade never
        # exceeds the plan grade; the ramp top then sits slightly
        # below the outside DEM — the same accepted "subtle terrain
        # dip" trade the walk gatherer already makes when the roadway
        # is too short (its far_dem cap).
        if e_hi_c > e_lo_c:
            plan_grade_local = max(
                float(_CFG.TUNNEL_RAMP_MAX_GRADE)
                - TUNNEL_RAMP_GRADE_SAFETY_MARGIN, 1e-3)
            # ...over the CLIMB run, not the whole walk: with a deck on
            # the chain the first ``climb_start_eff`` metres are level at
            # bore datum, so pricing the drop against ``effective_total``
            # would let the post-deck stretch run over the ramp cap.
            # Identical wherever there is no deck (climb_total ==
            # effective_total).
            maximum_effective_drop = plan_grade_local * climb_total
            if (e_hi_c - e_lo_c) > maximum_effective_drop:
                e_hi_c = e_lo_c + maximum_effective_drop

        for i in range(n_c - 1):
            p_a = chain_pts[i]
            p_b = chain_pts[i + 1]
            d_a = c_cums[i]
            d_b = c_cums[i + 1]
            seg_len = d_b - d_a
            if seg_len < 0.5:
                continue
            # THE COVERED STRETCH IS LEVEL, THE CLIMB IS BEYOND IT
            # (RULINGS 2026-08-30f).  Both fractions are measured from
            # ``climb_start_eff``, so every station under and inshore of
            # the deck sits at ``e_lo_c`` and the grade beyond it is
            # (e_hi_c - e_lo_c) / climb_total.
            frac_a = max(0.0, effective_cums[i]
                         - climb_start_eff) / climb_total
            frac_b = max(0.0, effective_cums[i + 1]
                         - climb_start_eff) / climb_total
            e_a = (1 - frac_a) * e_lo_c + frac_a * e_hi_c
            e_b = (1 - frac_b) * e_lo_c + frac_b * e_hi_c
            # Legacy per-segment flat walls (gate OFF only — byte-
            # identical to the pre-2026-06-13 behaviour).  Gate ON
            # traces ONE continuous DEM-following wall band around the
            # whole cluster ramp union after all ramps are emitted
            # (see ``_emit_perimeter_wall``), so per-segment walls are
            # skipped here.
            wall_top = apt_elev
            wall_thresh = wall_top - 0.05
            seg_e_lo = min(e_a, e_b)
            seg_e_hi = max(e_a, e_b)
            if TUNNEL_FORK_THROAT or seg_e_lo >= wall_thresh:
                pass
            else:
                if seg_e_hi > wall_thresh \
                        and abs(e_b - e_a) > 1e-3:
                    frac_cross = (
                        (wall_thresh - e_a) / (e_b - e_a))
                    frac_cross = max(0.0, min(1.0, frac_cross))
                else:
                    frac_cross = 1.0
                pa = chain_pts[i]
                pb = chain_pts[i + 1]
                cross = (
                    pa[0] + frac_cross * (pb[0] - pa[0]),
                    pa[1] + frac_cross * (pb[1] - pa[1]))
                for sign in (+1, -1):
                    inner = sign * (arm_off - half_wall_w)
                    outer = sign * (arm_off + half_wall_w)
                    ai = _vertex_offset(i, inner)
                    ao = _vertex_offset(i, outer)
                    if frac_cross >= 0.999:
                        bi = _vertex_offset(i + 1, inner)
                        bo = _vertex_offset(i + 1, outer)
                    else:
                        sx, sy = (pb[0] - pa[0], pb[1] - pa[1])
                        sl = math.hypot(sx, sy) or 1.0
                        nx, ny = -sy / sl, sx / sl
                        bi = (cross[0] + nx * inner,
                              cross[1] + ny * inner)
                        bo = (cross[0] + nx * outer,
                              cross[1] + ny * outer)
                    try:
                        wp = Polygon([ai, bi, bo, ao])
                        if not wp.is_valid:
                            wp = wp.buffer(0)
                        if (wp.geom_type == "Polygon"
                                and not wp.is_empty
                                and wp.area > 0.5):
                            # R8-3: the object trench owns this ground.
                            # A wall band is FLAT at one altitude and
                            # shares no value with its neighbours, so it
                            # clips rather than drops whole.
                            wp = _yield_piece_to_object_trench(
                                wp, object_trench_union,
                                corner_shared=False,
                                stats=object_trench_yield_stats)
                            if wp is None:
                                continue
                            # R10-2: never over tunnel pavement.
                            _append_tunnel_cover(
                                layout, exclusion_zones,
                                _tunnel_pavement_union(layout),
                                BuiltShape(
                                    polygon=wp,
                                    role=ROLE_RETAINING_WALL,
                                    ref="tunnel_wall",
                                    altitude=round(apt_elev, 1)))
                    except _GEOM_EXC:
                        continue
            if cap_gap and i == 0 \
                    and c_first_len > wall_gap_m + 0.5:
                near_xy = (
                    chain_pts[0][0] + c_first_dir[0] * wall_gap_m,
                    chain_pts[0][1] + c_first_dir[1] * wall_gap_m)
                npx, npy = verts_perp[0]
                ra = (near_xy[0] + npx * chain_half,
                      near_xy[1] + npy * chain_half)
                rd = (near_xy[0] - npx * chain_half,
                      near_xy[1] - npy * chain_half)
                if c_cums[1] > 0:
                    e_a = (
                        e_a + (e_b - e_a)
                        * (wall_gap_m / c_cums[1]))
            else:
                ra = _vertex_offset(i, +chain_half)
                rd = _vertex_offset(i, -chain_half)
            rb = _vertex_offset(i + 1, +chain_half)
            rc = _vertex_offset(i + 1, -chain_half)
            if e_b >= e_a:
                ramp_corners = [rb, ra, rd, rc]
                eh, el = e_b, e_a
            else:
                ramp_corners = [ra, rb, rc, rd]
                eh, el = e_a, e_b
            try:
                rp = Polygon(ramp_corners)
                if not rp.is_valid:
                    rp = rp.buffer(0)
                if (rp.geom_type == "Polygon"
                        and not rp.is_empty
                        and rp.area > 0.5):
                    covered = 0.0
                    for tp in cluster_throat_polys:
                        try:
                            covered += rp.intersection(tp).area
                        except _GEOM_EXC:
                            continue
                    if covered > 0.5 * rp.area:
                        continue    # throat already paves this spot
                    # R8-3: a classified object tunnel with a cut trench
                    # owns this ground — the ramp chain yields.  A ramp
                    # quad SHARES its cross-edge corners with its
                    # neighbours (see the corner-agreement note below),
                    # so it drops whole or survives whole; clipping it
                    # would mint a third value on those shared nodes.
                    if _yield_piece_to_object_trench(
                            rp, object_trench_union, corner_shared=True,
                            stats=object_trench_yield_stats) is None:
                        continue
                    # RAMP-INTERNAL CORNER AGREEMENT (spec §2): the
                    # FLAT fallback averages the two edges, so each of
                    # the quad's two cross-edges is offered a value
                    # |eh-el|/2 away from what its NEIGHBOUR quad
                    # offers the same shared nodes.  At the old 0.1 m
                    # threshold that is up to 0.05 m of disagreement —
                    # five times the spec's 0.01 m materiality floor —
                    # decided by which of the two ways ``to_osm``'s
                    # shape-order precedence happens to write last.
                    # ``_TUNNEL_RAMP_FLAT_QUAD_M`` keeps the flat
                    # encoding only where the averaging error is AT the
                    # floor.
                    if abs(eh - el) >= _TUNNEL_RAMP_FLAT_QUAD_M:
                        layout.shapes.append(BuiltShape(
                            polygon=rp,
                            role=ROLE_TUNNEL_RAMP,
                            ref="tunnel_ramp",
                            altitude_high=round(eh, 2),
                            altitude_low=round(el, 2)))
                    else:
                        layout.shapes.append(BuiltShape(
                            polygon=rp,
                            role=ROLE_TUNNEL_RAMP,
                            ref="tunnel_ramp",
                            altitude=round(
                                0.5 * (eh + el), 2)))
                    exclusion_zones.append(rp)
            except _GEOM_EXC:
                pass
        return e_hi_c

    def _emit_fork_throat(throat_pts, throat_half, e_throat,
                          arms):
        """Bridge the shared bore (ending at the fork point ``F``)
        to the per-arm sloping rects with ONE ``node_altitudes``
        "throat" polygon carrying a V-notch, then trace the whole Y
        with retaining walls (outer fan edges + the inner V between
        the arms).  No pavement is graded between the arms — each
        crotch wedge is carved out by an apex vertex.  Modelled on
        the taxiway sloping-rect + junction pattern (user
        2026-06-12, KPHL RWY 26 north portal).  Generalises to N
        arms (N-1 crotches, a star-shaped fan about ``F``).

        ``arms`` = list of ``(branch_pts, half_k, far_k)``; each
        branch starts at the arm's (advanced) fork-side end, so its
        near-edge corners intern 1:1 with the arm ramp's near edge.
        Returns True when a throat polygon was emitted."""
        if len(throat_pts) < 2 or len(arms) < 2:
            return False
        F = throat_pts[-1]
        # Perp of the throat's FAR edge — matches _emit_chain's
        # last-vertex offset so NL/NR intern with the bore's far
        # corners (continuity at the bore→throat seam).
        tdx = throat_pts[-1][0] - throat_pts[-2][0]
        tdy = throat_pts[-1][1] - throat_pts[-2][1]
        tl = math.hypot(tdx, tdy)
        if tl < 1e-6:
            return False
        t_dir = (tdx / tl, tdy / tl)
        t_perp = (-t_dir[1], t_dir[0])
        NL = (F[0] + t_perp[0] * throat_half,
              F[1] + t_perp[1] * throat_half)
        NR = (F[0] - t_perp[0] * throat_half,
              F[1] - t_perp[1] * throat_half)
        # Per-arm fork-side geometry.  Near corners are computed
        # exactly as _emit_chain's vertex-0 offset (±half along the
        # branch's first-segment perp) so they share arm-ramp nodes.
        arm_info = []
        for branch, half_k, _far_k in arms:
            if len(branch) < 2:
                continue
            E = branch[0]
            adx = branch[1][0] - branch[0][0]
            ady = branch[1][1] - branch[0][1]
            al = math.hypot(adx, ady)
            if al < 1e-6:
                continue
            a_dir = (adx / al, ady / al)
            a_perp = (-a_dir[1], a_dir[0])
            cP = (E[0] + a_perp[0] * half_k, E[1] + a_perp[1] * half_k)
            cM = (E[0] - a_perp[0] * half_k, E[1] - a_perp[1] * half_k)
            adv = math.hypot(E[0] - F[0], E[1] - F[1])
            arm_info.append({"E": E, "dir": a_dir, "half": half_k,
                             "cP": cP, "cM": cM, "adv": adv})
        if len(arm_info) < 2:
            return False
        # Nothing to fill if no arm advanced past the fork.
        if max(a["adv"] for a in arm_info) < 2.0:
            return False

        def _ang_about_F(p):
            vx, vy = p[0] - F[0], p[1] - F[1]
            return math.atan2(vx * t_perp[0] + vy * t_perp[1],
                              vx * t_dir[0] + vy * t_dir[1])
        # Order arms left→right (decreasing angle about the bore
        # forward axis) so the fan ring stays simple.
        arm_info.sort(key=lambda a: _ang_about_F(a["E"]),
                      reverse=True)
        # Classify each arm's two near corners as more-left (cL) and
        # more-right (cR) about F.
        for a in arm_info:
            if _ang_about_F(a["cP"]) >= _ang_about_F(a["cM"]):
                a["cL"], a["cR"] = a["cP"], a["cM"]
            else:
                a["cL"], a["cR"] = a["cM"], a["cP"]

        def _fwd(p):
            return (p[0] - F[0]) * t_dir[0] + (p[1] - F[1]) * t_dir[1]

        def _apex(a_left, a_right):
            # Crotch apex = where the two facing inner edges (left
            # arm's right edge, right arm's left edge), extended back
            # toward F, meet — the natural fork point.  Fall back to
            # a pulled-back midpoint when near-parallel or the meet
            # lands behind F / past the inner corners.
            p1, d1 = a_left["cR"], a_left["dir"]
            p2, d2 = a_right["cL"], a_right["dir"]
            denom = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
            if abs(denom) > 1e-9:
                rx, ry = p2[0] - p1[0], p2[1] - p1[1]
                t1 = (rx * (-d2[1]) - ry * (-d2[0])) / denom
                mx, my = p1[0] + t1 * d1[0], p1[1] + t1 * d1[1]
                fwd = (mx - F[0]) * t_dir[0] + (my - F[1]) * t_dir[1]
                cap = max(_fwd(p1), _fwd(p2))
                if 0.0 < fwd <= cap + 0.5:
                    return (mx, my)
            mid = (0.5 * (p1[0] + p2[0]), 0.5 * (p1[1] + p2[1]))
            return (F[0] + 0.6 * (mid[0] - F[0]),
                    F[1] + 0.6 * (mid[1] - F[1]))

        # Build the fan ring (CCW from NL).  Edge i→i+1 carries a
        # wall unless it abuts a ramp: arm near edges (cL→cR) and the
        # bore near edge (NR→NL) do, everything else is a wall.
        ring, wall_edge = [], []

        def _push(p, wall):
            ring.append(p)
            wall_edge.append(wall)
        _push(NL, True)                      # NL → first arm: outer wall
        for idx, a in enumerate(arm_info):
            _push(a["cL"], False)            # arm near edge: no wall
            _push(a["cR"], True)             # cR → apex / NR: wall
            if idx != len(arm_info) - 1:
                _push(_apex(a, arm_info[idx + 1]), True)
        _push(NR, False)                     # NR → NL (bore): no wall

        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.geom_type == "MultiPolygon":
                poly = max(poly.geoms, key=lambda g: g.area)
            if (poly.geom_type != "Polygon" or poly.is_empty
                    or poly.area < 1.0):
                return False
        except _GEOM_EXC:
            return False
        # Flat landing at the bore-handoff elevation, carried as
        # node_altitudes (the junction representation) so a future
        # change with differing per-arm start elevations bridges
        # them per-vertex with no further work.
        #
        # RAMP-INTERNAL CORNER AGREEMENT (spec §2): rounded to the
        # SAME 2 decimals ``_emit_chain`` rounds its quad corners to.
        # At 1 decimal the throat offered NL/NR (shared with the bore's
        # far corners) and cL/cR (shared with each arm's near corners) a
        # value up to 0.05 m from what the chain offered the same nodes
        # — a disagreement decided by ``to_osm`` shape order, not by the
        # plan.
        #
        # R8-3: the throat shares NL/NR with the bore and cL/cR with each
        # arm, so it too drops whole or survives whole where a classified
        # object tunnel owns the ground.
        if _yield_piece_to_object_trench(
                poly, object_trench_union, corner_shared=True,
                stats=object_trench_yield_stats) is None:
            return False
        _np = len(poly.exterior.coords) - 1
        na = [round(e_throat, 2)] * (_np + 1)
        layout.shapes.append(BuiltShape(
            polygon=poly, role=ROLE_TUNNEL_RAMP,
            ref="tunnel_ramp", node_altitudes=na))
        exclusion_zones.append(poly)
        cluster_throat_polys.append(poly)

        # No walls here — the continuous perimeter wall band is traced
        # around the whole cluster ramp union after all ramps emit
        # (``_emit_perimeter_wall``); the throat is just one more ramp
        # piece in that union.
        return True

    # ── Y-SPLIT (user 2026-06-12): when cluster members share the
    # portal but their ways DIVERGE just outside (KPHL RWY 26
    # north: road and rail fork right after the tunnel), emit a
    # shared throat to the fork station, then per-member branch
    # ramps following each way separately as they grade to DEM.
    # Parallel members (south side, SPJC divided highways) keep
    # the single combined ramp unchanged.
    def _point_at(pts, cums, s):
        for i in range(1, len(pts)):
            if cums[i] >= s:
                seg = cums[i] - cums[i - 1]
                t = ((s - cums[i - 1]) / seg) if seg > 0 else 0.0
                return (pts[i - 1][0]
                        + t * (pts[i][0] - pts[i - 1][0]),
                        pts[i - 1][1]
                        + t * (pts[i][1] - pts[i - 1][1]))
        return pts[-1]

    s_div = None
    member_chains = []
    if len(cl) > 1:
        for k in cl:
            w_k = portal_data[k][2]
            if w_k and len(w_k) >= 2:
                c_k = [0.0]
                for i in range(1, len(w_k)):
                    c_k.append(c_k[-1] + math.hypot(
                        w_k[i][0] - w_k[i - 1][0],
                        w_k[i][1] - w_k[i - 1][1]))
                member_chains.append((k, w_k, c_k))
        if len(member_chains) > 1:
            probe_max = min(c[2][-1] for c in member_chains)
            # Gate-on ends the shared bore as soon as the ways START
            # to diverge (small margin, fine probe) so the bore is
            # short enough for the throat to widen smoothly into the
            # arms (user 2026-06-13).  The legacy bare-crotch path
            # keeps the wider 8 m margin.
            _div_margin = 2.0 if TUNNEL_FORK_THROAT else 8.0
            _div_step = 2.5 if TUNNEL_FORK_THROAT else 5.0
            s = 5.0 if TUNNEL_FORK_THROAT else 10.0
            # SUSTAINED DIVERGENCE (spec
            # ``docs/specs/tunnel-fork-sustain-spec.md`` §2, owner
            # 2026-08-07).  The probe used to fork on the FIRST station
            # whose spread crossed the threshold and stop looking.  That
            # reads a momentary wobble as a Y-split: OTHH's A-site
            # cluster is twin one-way service carriageways whose measured
            # separation runs 9.52 m at the portal, drifts 8.3-9.8 m for
            # 150 m, crosses the 11.50 m threshold at s ≈ 157.5 m on a
            # 1.2 m relative splay — and then falls to 0.00 m, because
            # the two carriageways MERGE into one road at a shared end
            # node.  The emitted "fork" was two arms overlapping by
            # 93.89 m² that interned into each other and minted 16
            # cross-arm adoption rows.  So scan the WHOLE window and
            # require the divergence to HOLD: a real Y-split keeps
            # separating, twin carriageways come back together.
            _div_thresh = cluster_span + _div_margin
            _spreads: list = []          # (station, spread)
            while s < probe_max:
                pts_at = [_point_at(w, c, s)
                          for (_k, w, c) in member_chains]
                spread = max(
                    math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                    for x1, p1 in enumerate(pts_at)
                    for p2 in pts_at[x1 + 1:])
                _spreads.append((s, spread))
                if s_div is None and spread > _div_thresh:
                    s_div = s
                s += _div_step
            if s_div is not None:
                _after = [_sp for (_st, _sp) in _spreads if _st >= s_div]
                _held = sum(1 for _sp in _after if _sp > _div_thresh)
                if (not _after
                        or (_held / len(_after))
                        < TUNNEL_FORK_SUSTAIN_FRACTION):
                    if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                        print(f"    [tunnel-fork] cluster at "
                              f"({walk_pts[0][0]:.0f},{walk_pts[0][1]:.0f})"
                              f": divergence at s={s_div:.1f} NOT sustained "
                              f"({_held}/{len(_after)} stations above "
                              f"{_div_thresh:.2f} m; spread falls to "
                              f"{min(_after):.2f} m) — twin carriageways, "
                              f"emitting ONE combined ramp")
                    s_div = None
            # FORK-THRESHOLD FRAME AUDIT (debug only, spec
            # ``tunnel-fork-sustain-spec.md`` §2b step 0): the threshold
            # references ``cluster_span`` — a 1-D PERPENDICULAR projection
            # of the portal nodes onto the head walk's first-segment
            # perpendicular — while ``spread`` is a 2-D same-station
            # euclidean distance.  Print both frames beside the members'
            # true euclidean separation so the mismatch is a measurement,
            # not an inference.
            if os.environ.get("O4_TUNNEL_DEBUG") == "1" and _spreads:
                _pnodes = [nodes_m[portal_data[k][0]] for k in cl
                           if portal_data[k][0] in nodes_m]
                _eucl = max((math.hypot(a[0] - b[0], a[1] - b[1])
                             for i9, a in enumerate(_pnodes)
                             for b in _pnodes[i9 + 1:]), default=0.0)
                _sp0 = _spreads[0][1]
                _spmin = min(sp for _st, sp in _spreads)
                _spmax = max(sp for _st, sp in _spreads)
                print(f"    [tunnel-fork-frame] cluster at "
                      f"({walk_pts[0][0]:.0f},{walk_pts[0][1]:.0f}) "
                      f"members={len(member_chains)} "
                      f"cluster_span(1-D perp)={cluster_span:.2f} "
                      f"portal_euclid(2-D)={_eucl:.2f} "
                      f"thresh={_div_thresh:.2f} "
                      f"spread0={_sp0:.2f} min={_spmin:.2f} "
                      f"max={_spmax:.2f} growth={_spmax - _sp0:+.2f} "
                      f"probe_max={probe_max:.1f} "
                      f"s_div={'None' if s_div is None else f'{s_div:.1f}'}")
            if s_div is not None and (probe_max - s_div) < 10.0:
                s_div = None     # fork too close to the end

    if s_div is None:
        _emit_chain(walk_pts, combined_half,
                    elev_low, elev_high, True)
        if len(walk_pts) >= 2:
            _cl_arm_ends.append((walk_pts[-1], walk_pts[-2],
                                 combined_half))
    else:
        # Per-member branches (widest first).
        ordered = []
        for k, w_k, c_k in member_chains:
            half_k = 0.5 * portal_data[k][7]
            ordered.append((half_k, k, w_k, c_k))
        ordered.sort(key=lambda t: -t[0])
        # Gate-on: arms start at the common station where every pair has
        # separated by their combined half-widths + a gap (they start
        # CLOSE together), and the bore (a sloping rect) ends EARLY
        # enough to leave at least a ``_throat_min`` junction that
        # cleanly widens from the bore to the arms — no jog (user
        # 2026-06-13).  The legacy path keeps s_div + per-arm advance.
        _throat_min = 10.0
        s_arm = s_div
        s_bore_end = s_div
        if TUNNEL_FORK_THROAT and len(ordered) >= 2:
            _half_of = {k: hk for hk, k, _w, _c in ordered}
            _chain_of = {k: (w, c) for _h, k, w, c in ordered}
            d_adv = 0.0
            while s_div + d_adv < probe_max - 4.0:
                _pa = {k: _point_at(_chain_of[k][0], _chain_of[k][1],
                                    s_div + d_adv) for k in _half_of}
                _clear = True
                _ks = list(_half_of)
                for _i9 in range(len(_ks)):
                    for _j9 in range(_i9 + 1, len(_ks)):
                        _ka, _kb = _ks[_i9], _ks[_j9]
                        _need = (_half_of[_ka] + _half_of[_kb]
                                 + 2.0 * wall_gap_m + 2.0)
                        if math.hypot(
                                _pa[_ka][0] - _pa[_kb][0],
                                _pa[_ka][1] - _pa[_kb][1]) < _need:
                            _clear = False
                            break
                    if not _clear:
                        break
                if _clear:
                    break
                d_adv += 1.0
            s_arm = s_div + d_adv
            # Shorten the bore so the junction spans ≥ _throat_min; the
            # bore never extends past the fork (s_div).
            s_bore_end = max(1.0, min(s_div, s_arm - _throat_min))
        # Shared bore (sloping rect) on the centred canonical walk,
        # ending at s_bore_end.
        throat = [walk_pts[0]]
        for i in range(1, len(walk_pts)):
            if cum_dists[i] < s_bore_end:
                throat.append(walk_pts[i])
            else:
                break
        throat.append(_point_at(walk_pts, cum_dists, s_bore_end))
        e_div = (elev_low + (elev_high - elev_low)
                 * (s_bore_end / total_walk if total_walk > 0
                    else 0.0))
        # RAMP-INTERNAL CORNER AGREEMENT (spec
        # ``tunnel-ramp-cut-boundaries-spec.md`` §2): the bore's
        # effective-space grade clamp may land its far edge BELOW the
        # planned ``e_div`` (it fires on every bend — the miter-
        # shortened inner edges shrink Σeffective 15-20 % below the
        # centreline sum).  The throat's flat landing and the arms'
        # near edges intern with that far edge, so they must be seated
        # on the elevation the bore REALIZED, not on the plan; OTHH
        # ways -11758/-11759 disagreed by 0.96 m at exactly these
        # nodes.  The handoff stays piecewise-linear either way — only
        # the shared value changes.
        _e_bore_top = _emit_chain(throat, combined_half,
                                  elev_low, e_div, True)
        if _e_bore_top is not None:
            e_div = _e_bore_top
        prior: list = []          # (LineString, half)
        try:
            prior.append((LineString(throat), combined_half))
        except _GEOM_EXC:
            pass
        # Collect the arm chains.  Gate ON: every arm starts at the
        # common ``s_arm`` station (mutually clear by construction, so
        # no per-arm advance).  Gate OFF: legacy per-arm advance past
        # the throat + prior siblings (byte-identical to before).
        arm_specs: list = []      # (branch_pts, half_k, far_k)
        for half_k, k, w_k, c_k in ordered:
            _start_s = s_arm if TUNNEL_FORK_THROAT else s_div
            branch = [_point_at(w_k, c_k, _start_s)]
            for i in range(1, len(w_k)):
                if c_k[i] > _start_s:
                    branch.append(w_k[i])
            if len(branch) < 2:
                continue
            if not TUNNEL_FORK_THROAT and prior:
                # advance the start until clear of the throat +
                # every prior sibling corridor (sample 2 m).
                bl = LineString(branch)
                s9 = 0.0
                while s9 < bl.length - 4.0:
                    pt9 = bl.interpolate(s9)
                    if all(pt9.distance(pl) >= half_k + ph + 0.5
                           for pl, ph in prior):
                        break
                    s9 += 2.0
                if s9 > 0.0:
                    if bl.length - s9 < 6.0:
                        continue
                    head9 = bl.interpolate(s9)
                    branch = ([(head9.x, head9.y)]
                              + [pp for i9, pp in enumerate(branch)
                                 if bl.project(Point(pp)) > s9])
                    if len(branch) < 2:
                        continue
            far_k = portal_data[k][5]
            arm_specs.append((branch, half_k, far_k))
            try:
                prior.append((LineString(branch), half_k))
            except _GEOM_EXC:
                pass
        # Throat bridges bore→arms; emitted before the arms so it abuts
        # the bore's far edge.
        if TUNNEL_FORK_THROAT and len(arm_specs) >= 2:
            _emit_fork_throat(throat, combined_half, e_div,
                              arm_specs)
        for branch, half_k, far_k in arm_specs:
            _emit_chain(branch, half_k, e_div, far_k, False)
            if len(branch) >= 2:
                _cl_arm_ends.append((branch[-1], branch[-2], half_k))
        # WALL OPENINGS: a diverging branch must cross the
        # throat's (or a sibling's) side wall — clip every wall
        # piece of THIS cluster against the cluster's ramp
        # polygons (walls are flat; clipping is safe).
        try:
            ramps9 = [s9.polygon for s9 in
                      layout.shapes[_cl_start_idx:]
                      if getattr(s9, 'ref', '') == 'tunnel_ramp'
                      and s9.polygon is not None]
            if ramps9:
                ramp_u9 = unary_union(ramps9).buffer(0.3)
                # R10-2: ALL surviving arcs are kept.  A throat ring cut
                # by the roadways crossing it is three arcs; keeping only
                # the largest was a silent DELETION of the other two —
                # the mouth then faced open ground on the sides the
                # deleted arcs walled.  Extra pieces are appended as
                # their own shapes (a wall carries no cross-piece
                # identity).
                _extra9: list = []
                for s9 in layout.shapes[_cl_start_idx:]:
                    # §T5: the wall's FOOT is reclipped with its face.
                    if getattr(s9, 'ref', '') not in _WALL_BAND_REFS \
                            or s9.polygon is None:
                        continue
                    if not s9.polygon.intersects(ramp_u9):
                        continue
                    _pieces9 = _tunnel_cover_pieces(s9, ramp_u9)
                    if not _pieces9:
                        s9.polygon = None
                        continue
                    _head9 = _pieces9[0]
                    s9.polygon = _head9.polygon
                    s9.altitude = _head9.altitude
                    s9.altitude_high = _head9.altitude_high
                    s9.altitude_low = _head9.altitude_low
                    s9.node_altitudes = _head9.node_altitudes
                    _extra9.extend(_pieces9[1:])
                layout.shapes = [
                    s9 for s9 in layout.shapes
                    if not (getattr(s9, 'ref', '') in _WALL_BAND_REFS
                            and s9.polygon is None)]
                for _e9 in _extra9:
                    layout.shapes.append(_e9)
                    exclusion_zones.append(_e9.polygon)
        except _GEOM_EXC:
            pass
    # ── B-1: A RAMP NEVER CROSSES A BUILDING PAD EDGE (owner ruling
    # 2026-08-07, spec ``tunnel-ramp-cut-boundaries-spec.md`` §4).
    # Owner, verbatim: "A ramp should never cross a building pad edge.
    # Either the tunnel is under the building and the ramp stops at the
    # building edge, or the building is mis-identified and shouldn't be
    # there in the first place."  So a building pad is neither CUT
    # (``ROLE_BUILDING`` is absent from ``_tunnel_ramp_cut_roles`` — it
    # was never in ``pavement_cut_roles``) nor BURIED (that is what
    # ruling 4's un-gated ramp did: OTHH's ``building1`` pad ring
    # dragged to −3.74).  The visible ramp CLIPS at the pad edge, with
    # the same 0.6 m vertex-bucket clearance every other tunnel piece
    # keeps; the continuation under the pad is covered bore and is not
    # emitted.  Runs BEFORE the perimeter band below, so the ramp's new
    # end face at the pad edge is walled by the band exactly like the
    # portal face (§4 last bullet).  A mis-identified building is a
    # data-quality case, never an emitter workaround.
    _cl_ramps = [(_i9, layout.shapes[_i9])
                 for _i9 in range(_cl_start_idx, len(layout.shapes))
                 if getattr(layout.shapes[_i9], "ref", "") == "tunnel_ramp"
                 and layout.shapes[_i9].polygon is not None
                 and not layout.shapes[_i9].polygon.is_empty]
    if _cl_ramps:
        _pads = [(_i9, _s9) for _i9, _s9 in enumerate(layout.shapes)
                 if _s9.role == ROLE_BUILDING and _s9.polygon is not None
                 and not _s9.polygon.is_empty]
        _cl_wid = head[1]
        _dropped9: set = set()
        _ez_replace: dict = {}
        _n_bclip = 0
        # TRIGGER GEOMETRY: each pad BUFFERED by the graze clearance, so a
        # TANGENT ramp is clipped exactly like an overlapping one (spec v3
        # amendment, 2026-08-09).  The bare ``overlap area > 0`` test let a
        # ramp whose corner sits EXACTLY on the pad ring (zero-area
        # tangency) escape the 0.6 m standoff; it then landed inside that
        # ring vertex's SHARED_VERTEX_TOL_M intern bucket and to_osm's
        # authority precedence welded its below-grade profile onto the
        # building — measured at OTHH: ramp -11489 dragging building1's
        # node -24372 to −4.29 (the ruling-4 specimen was the same pad at
        # −3.74).  Buffered ONCE per pad, not per (ramp, pad) pair.
        _pads_trigger = []
        for _pi, _pad in _pads:
            try:
                _pads_trigger.append(
                    (_pi, _pad,
                     _pad.polygon.buffer(_TUNNEL_GRAZE_CLEARANCE_M)))
            except _GEOM_EXC:
                _pads_trigger.append((_pi, _pad, _pad.polygon))
        for _i9, _s9 in (_cl_ramps if _pads else ()):
            _hit = []
            for _pi, _pad, _pad_trig in _pads_trigger:
                try:
                    _ov9 = _s9.polygon.intersection(_pad_trig).area
                except _GEOM_EXC:
                    continue
                if _ov9 > 0.0:
                    _hit.append((_ov9, _pi, _pad))
            if not _hit:
                continue
            _hit.sort(key=lambda t: -t[0])
            _pad_id = _hit[0][1]
            try:
                _pad_u = unary_union([p.polygon for _o, _i, p in _hit]).buffer(
                    _TUNNEL_GRAZE_CLEARANCE_M)
                _keep9 = _s9.polygon.difference(_pad_u)
            except _GEOM_EXC:
                continue
            if _keep9.geom_type == "MultiPolygon":
                _keep9 = max(_keep9.geoms, key=lambda g: g.area)
            if (_keep9.is_empty or _keep9.geom_type != "Polygon"
                    or _keep9.area < 1.0):
                _dropped9.add(_i9)
                _ez_replace[id(_s9.polygon)] = None
                try:
                    UI.vprint(1,
                        f"  [pav-builder] tunnel ramp piece of way "
                        f"{_cl_wid} DROPPED whole — it lies under "
                        f"building pad shapeID {_pad_id}; the tunnel "
                        f"runs UNDER the building (covered bore), so "
                        f"the open ramp stops at the pad edge.")
                except _GEOM_EXC:
                    pass
                continue
            # Altitude semantics: the EXISTING graze-clip conversion —
            # a clipped ramp keeps the profile it already planned and
            # never stretches it (``_sloped_rect_clipped_altitudes``
            # clamps the projection parameter to [0, 1];
            # ``_resample_node_altitudes_nn`` interpolates along the
            # OLD edges).  A conversion that cannot answer drops the
            # piece rather than shipping a ring with the wrong
            # ring-order slope semantics.
            if _s9.node_altitudes:
                try:
                    _or9 = list(_s9.polygon.exterior.coords)
                except _GEOM_EXC:
                    _or9 = []
                if _or9 and _or9[0] == _or9[-1]:
                    _or9 = _or9[:-1]
                _res9 = _resample_node_altitudes_nn(
                    _keep9, _or9, list(_s9.node_altitudes),
                    interior_edge_project=True)
                if _res9 is None:
                    _dropped9.add(_i9)
                    _ez_replace[id(_s9.polygon)] = None
                    continue
                _s9.node_altitudes = _res9
            elif (_s9.altitude_high is not None
                    and _s9.altitude_low is not None):
                _res9 = _sloped_rect_clipped_altitudes(
                    _s9.polygon, _s9.altitude_high, _s9.altitude_low,
                    _keep9)
                if _res9 is None:
                    _dropped9.add(_i9)
                    _ez_replace[id(_s9.polygon)] = None
                    continue
                _s9.altitude_high = None
                _s9.altitude_low = None
                _s9.node_altitudes = _res9
            # (flat ``altitude`` pieces keep their altitude verbatim)
            _ez_replace[id(_s9.polygon)] = _keep9
            _s9.polygon = _keep9
            _n_bclip += 1
        if _ez_replace:
            # The ramp polygons are also in ``exclusion_zones`` (the
            # boundary-ribbon subtraction and the double-emit gate read
            # it); leaving the PRE-clip footprint there would carve the
            # ribbon out over pavement the ramp no longer occupies.
            _ez_new = []
            for _z9 in exclusion_zones:
                _r9 = _ez_replace.get(id(_z9), _z9)
                if _r9 is not None:
                    _ez_new.append(_r9)
            exclusion_zones[:] = _ez_new
        if _dropped9:
            layout.shapes = [_s9 for _i9, _s9 in enumerate(layout.shapes)
                             if _i9 not in _dropped9]
        if _n_bclip:
            try:
                UI.vprint(1,
                    f"  [pav-builder] clipped {_n_bclip} tunnel ramp "
                    f"piece(s) of way {_cl_wid} at a building pad edge "
                    f"(the bore runs under the building).")
            except _GEOM_EXC:
                pass
    # ── CONTINUOUS PERIMETER WALL (gate ON, user 2026-06-13): ONE
    # wall traced around the WHOLE cluster ramp-union perimeter,
    # regardless of whether the tunnel forks.  The band is the ramp
    # union's outward offset annulus (shapely buffer → clean corners,
    # no self-overlap on curves/sharp ends), node_altitudes FOLLOWING
    # THE DEM like the airport boundary ribbon.  The annulus is "slit"
    # into a single hole-free ring (to_osm drops interior rings, which
    # would otherwise emit a filled disc over the ramp).  Replaces the
    # per-segment / cap / throat walls entirely.
    if TUNNEL_FORK_THROAT:
        try:
            _ramps_b = [
                s.polygon for s in layout.shapes[_cl_start_idx:]
                if getattr(s, 'ref', '') == 'tunnel_ramp'
                and s.polygon is not None
                and not s.polygon.is_empty]
            _ru = unary_union(_ramps_b) if _ramps_b else None
            _ru_polys = [g for g in getattr(_ru, 'geoms', [_ru] if _ru
                                            else [])
                         if g.geom_type == 'Polygon'
                         and not g.is_empty]
            emit_wall_band(
                layout, exclusion_zones, _ru_polys,
                [s for s in layout.shapes[_cl_start_idx:]
                 if getattr(s, 'ref', '') == 'tunnel_ramp'],
                _cl_arm_ends, wall_gap_m, retaining_wall_width_m,
                dem_at, apt_elev)
        except _GEOM_EXC:
            pass
    return 1



def emit_wall_band(layout: "PavementLayout", exclusion_zones: list,
                   bodies: list, sources: list, arm_ends: list,
                   wall_gap_m: float, retaining_wall_width_m: float,
                   dem_at, apt_elev: float) -> None:
    """THE PERIMETER WALL BAND — one construction, every caller.

    ``bodies`` are the below-grade surfaces to wall (a cluster's ramp
    union, or a CLAIMED corridor's footprint — §T6/portal-corridor-claim
    §2.3: "a claimed corridor walls itself exactly as the synthetic path
    does").  ``sources`` are the shapes whose ring altitudes the band's
    inner edge takes its values from — the road surface the wall retains.
    ``arm_ends`` are ``(end_xy, prev_xy, half_width)`` triples at which
    the band is cut OPEN; pass ``[]`` to WRAP the ends instead, which is
    what a claimed corridor's mouths need.

    Extracted from ``_emit_portal_cluster`` unchanged in behaviour when
    called with that function's own arguments — the alternative was a
    second wall emitter, and a slightly-different duplicate is the defect
    this repo has already paid for (RULINGS ``7e90032``).
    """
    _ru_polys = [g for g in bodies
                 if g is not None and not g.is_empty
                 and g.geom_type == "Polygon"]
    if not _ru_polys:
        return
    _sources_in = [s for s in sources
                   if s is not None and s.polygon is not None
                   and not s.polygon.is_empty
                   and s.polygon.geom_type == "Polygon"]
    _cl_arm_ends = list(arm_ends or ())
    # HOISTED, and it is invariant: this loop appends only ``tunnel_wall``
    # / ``tunnel_wall_foot`` pieces, neither of which is in
    # ``_TUNNEL_PAVEMENT_REFS``, so the union it cuts against cannot
    # change while it runs.  Recomputing it per emitted piece is a union
    # over the whole layout inside the innermost loop — affordable for a
    # cluster's few ramp bodies, not for a claimed corridor set (§T6.1).
    _pav_u_band = _tunnel_pavement_union(layout)
    _g0 = wall_gap_m
    _g1 = wall_gap_m + retaining_wall_width_m
    # Openings at every arm's FAR (surface) end: the annulus
    # crosses the roadway at BOTH ends, but only the PORTAL
    # crossing is the cap — at the far end the road continues
    # at grade and the crossing walls it off (user 2026-07-04,
    # CYUL east: the slit knife then severed the true cap at
    # the narrow portal, leaving the wall "flipped" with the
    # cap at the high end).  Cutting the far ends open also
    # makes the band simply connected, so the portal cap
    # survives the hole-slitting untouched.
    _openings = []
    for (_ep, _pp, _hk) in _cl_arm_ends:
        _odx, _ody = _ep[0] - _pp[0], _ep[1] - _pp[1]
        _odl = math.hypot(_odx, _ody) or 1.0
        _oux, _ouy = _odx / _odl, _ody / _odl
        _open_line = LineString([
            (_ep[0] - _oux * 1.0, _ep[1] - _ouy * 1.0),
            (_ep[0] + _oux * (_g1 + 2.0),
             _ep[1] + _ouy * (_g1 + 2.0))])
        try:
            _openings.append(_open_line.buffer(
                max(_hk + _g0 - 0.05, 0.5), cap_style=2))
        except _GEOM_EXC:
            continue
    _open_u = unary_union(_openings) if _openings else None
    _foot_law = ramp_wall_foot_enabled()

    # ── THE ALTITUDE SOURCES, BUILT ONCE ─────────────────────────────
    # Ring-independent, and the partition below asks for altitudes twice
    # per band piece instead of once — rebuilding this per ring was
    # affordable when there was one ring and is not now.
    try:
        from .groundside import (
            GROUNDSIDE_MAX_GRADE as _GS_CAP,
            _BelowGradeIndex,
            _nearest_source_profile as _nsp,
            transition_law_altitudes,
        )
        _sources = []
        for _sr in _sources_in:
            if (_sr.polygon is None or _sr.polygon.is_empty
                    or _sr.polygon.geom_type != 'Polygon'):
                continue
            _rr = list(_sr.polygon.exterior.coords)
            if len(_rr) > 1 and _rr[0] == _rr[-1]:
                _rr = _rr[:-1]
            _ra = getattr(_sr, 'node_altitudes', None)
            if _ra and len(_ra) >= len(_rr):
                _rv = [a for a in _ra[:len(_rr)] if a is not None]
                if not _rv:
                    continue
                _fill = sum(_rv) / len(_rv)
                _sources.append((
                    _sr.polygon, _rr,
                    [float(a) if a is not None else _fill
                     for a in _ra[:len(_rr)]]))
            elif getattr(_sr, 'altitude', None) is not None:
                _sources.append((
                    _sr.polygon, _rr,
                    [float(_sr.altitude)] * len(_rr)))
        _idx = _BelowGradeIndex(_sources)
    except _GEOM_EXC:                                  # pragma: no cover
        _idx = None
    #: The ramp-value lookup must reach the ramp from anywhere in the
    #: structure, and the face's inner ring stands ``_g0`` off it.
    _reach = _WALL_FACE_ON_PAVEMENT_TOL_M + 0.5 + wall_gap_m
    #: THE PARTITION IS STRUCTURE-WIDE, not per body.  ``_ru_polys`` is
    #: one band PER RAMP BODY and the R10-2 note below says each band
    #: crosses its siblings' — so foot(A) ∩ face(B) is reachable even
    #: though foot(A) ∩ face(A) is not.  Measured at SPJC: 3 pairs,
    #: 2.9933 m², whose AREAS did not move across three within-body
    #: fixes, which is what identified them as cross-body.  Each piece
    #: subtracts what the structure already occupies, and — this is the
    #: ordering Amendment 2 names — the ring and the node_altitudes are
    #: derived AFTER that subtraction, from the final geometry.
    _emitted_band: list = []
    #: §F1 (LEMD fidelity spec law 1): the crest profile of the body this
    #: band is currently walling.  Rebound once per ``_ru_polys`` entry
    #: below; ``None`` when the law is OFF or the profile degenerates, and
    #: the per-vertex DEM sample then stands exactly as it did before.
    _crest_law = wall_top_station_law_enabled()
    _crest: "_CrestProfile | None" = None

    def _band_altitudes(ring, inner_boundary, is_foot):
        """Node altitudes for ONE ring of the FINAL partitioned geometry.

        THE CREST BAND TAKES THE TRANSITION LAW (round-4 spec R5, lead
        ruling 2026-08-10), not a DEM sample: the crest stays the
        surrounding-surface authority along the ramp's whole length — the
        wall FACE spans the drop — and descends only within the
        cap-limited run of the PORTAL.  The DEM value is the surface it
        grades TO, never the profile itself (sampling it alone gave a
        flat 4.00 m crest against a −4.02 m ramp).

        R16-2b: the structure's INNER edge carries the RAMP's value, so
        nothing between it and the crest is unowned.  A FOOT is FLAT —
        every vertex takes the ramp-edge value, so the shelf has no rise
        across its own width and the face rises from the shelf's outer
        edge alone.
        """
        # ── §F1: THE CREST IS A FUNCTION OF STATION ──────────────────
        # (LEMD ramp/road fidelity spec law 1, owner sim read of 1.0.265.)
        # Reading ``dem_at`` per vertex gave the two vertices facing each
        # other across a 1-1.5 m band values 0.5-1.6 m apart — nothing
        # tied them together, because along the RING they stand at
        # opposite ends.  With the law on, every vertex reads the profile
        # already sampled and grade-limited along the WALLED BODY's own
        # ring, at the station of its nearest point on it: a cross-band
        # pair projects to ONE station and so carries ONE value.  The
        # ramp-value overwrite below is untouched — it is the FACE's inner
        # edge law (R16-2b), a different edge from the crest.
        if _crest_law and _crest is not None and _crest:
            _station_vals = [_crest.at(_v) for _v in ring]
            if all(_sv is not None for _sv in _station_vals):
                _vals = [float(_sv) for _sv in _station_vals]
                if _idx is not None:
                    for _vi, (_vx, _vy) in enumerate(ring):
                        if not is_foot:
                            if inner_boundary is None:
                                continue
                            try:
                                if (inner_boundary.distance(Point(_vx, _vy))
                                        > _WALL_FACE_ON_PAVEMENT_TOL_M):
                                    continue
                            except _GEOM_EXC:          # pragma: no cover
                                continue
                        _ra, _rd, _rsi = _nsp((_vx, _vy), _idx, _reach)
                        if _ra is not None:
                            _vals[_vi] = float(_ra)
                return _vals
        _surface = []
        for _vx, _vy in ring:
            _d = dem_at(_vx, _vy)
            _surface.append(float(_d if _d is not None else apt_elev))
        if _idx is None:                               # pragma: no cover
            return _surface
        try:
            _vals, _n_moved = transition_law_altitudes(
                ring, _surface, _idx, _GS_CAP)
            for _vi, (_vx, _vy) in enumerate(ring):
                if not is_foot:
                    if inner_boundary is None:
                        continue
                    try:
                        if (inner_boundary.distance(Point(_vx, _vy))
                                > _WALL_FACE_ON_PAVEMENT_TOL_M):
                            continue
                    except _GEOM_EXC:                  # pragma: no cover
                        continue
                _ra, _rd, _rsi = _nsp((_vx, _vy), _idx, _reach)
                if _ra is not None:
                    _vals[_vi] = float(_ra)
            return _vals
        except _GEOM_EXC:                              # pragma: no cover
            return _surface

    for _rp in _ru_polys:
        # §F1: ONE crest profile per WALLED BODY, built before its band
        # pieces so every piece of the same body reads one law.  The
        # transition law runs here instead of per band ring, so this
        # replaces work rather than adding it (a body's ring is smaller
        # than the band rings it produces, and a body may produce
        # several).
        # ``_idx is None`` means the groundside import above failed, and
        # with it ``_GS_CAP``; the pre-§F1 path returns the raw surface
        # there, so the law stands down with it rather than inventing one.
        if _crest_law and _idx is not None:
            try:
                _crest = _CrestProfile(_rp, dem_at, apt_elev, _idx, _GS_CAP)
                if not _crest:
                    _crest = None
            except _GEOM_EXC:                          # pragma: no cover
                _crest = None
        try:
            _outer = _rp.buffer(_g1, join_style=2, mitre_limit=2.0)
            # R16-2b: THE WALL FACE IS OWNED GEOMETRY.  The band used to
            # start ``_g0`` (0.6 m) outboard of the ramp, leaving an
            # annulus NO shape owned — the mesh draped it at DEM/Z0 under
            # a crest standing 6.5-8 m above the ramp (measured OTHH: 17
            # wall nodes over a 0.6-1.6 m unowned gap).
            #
            # §T5 (RULINGS 2026-08-28c item 1) reconciles that with the
            # owner's "the ramp must have a small gap from the wall": the
            # FACE stands off ``_g0`` again and the annulus it vacates is
            # OWNED BY THE WALL STRUCTURE as its FOOT — a flat shelf at
            # ramp-edge elevation from which the face rises.
            #
            # ONE BAND, ONE SLIT, THEN A BOOLEAN PARTITION (spec
            # Amendment 2, ruling 1).  Building the foot and the face as
            # two INDEPENDENTLY buffered bands and slitting each of them
            # produced 3 overlapping foot∩face pairs totalling 2.99 m² at
            # SPJC, against ``test_no_self_overlap``'s zero tolerance:
            # mitre-joined buffers do not nest exactly at a sharp corner,
            # and the knife moves each ring separately.  A partition of
            # ONE post-slit polygon cannot overlap itself.
            # The inner-offset region, built ONCE per body: the FOOT's
            # outer edge when the foot ships, and the band's own inner
            # edge when it does not.
            _inner_region = _rp.buffer(_g0, join_style=2, mitre_limit=2.0)
            if _foot_law:
                # The whole annulus, partitioned below into foot + face.
                _band = _outer.difference(_rp)
                _region = _inner_region
            else:
                # ── THE DEFINED FALLBACK (Amendment 2 ruling 2) ──────
                # The plain ``_g0`` STANDOFF ships alone: the face stands
                # off the ramp, so the owner's measured sim breakage
                # (item 9 — ramp welded to wall, 84 shared node ids at
                # 0.0000 m) is fixed, and the older unowned-annulus
                # defect (R16-2b) RETURNS as the accepted lesser defect
                # pre-ship.  The owner's ruling outranks it: a broken
                # ramp is visible in the sim, and the annulus is a
                # draping artefact under a crest.
                _band = _outer.difference(_inner_region)
                _region = None
            if _open_u is not None:
                _band = _band.difference(_open_u)
        except _GEOM_EXC:
            continue
        for _bp in getattr(_band, 'geoms', [_band]):
            if (_bp.geom_type != 'Polygon' or _bp.is_empty
                    or _bp.area < 0.5):
                continue
            # Slit EVERY interior hole, not just the first.  A Y-fork
            # band has TWO holes — the central hole AND the crotch wedge
            # between the diverging arms — so the old single-hole slit
            # left the second hole, the ring filled into a solid disc
            # over the ramps, and the wall-vs-ramp clip then dropped it
            # (the fork lost its wall).  Cut a thin radial knife from
            # each hole out to the band exterior, collapsing the
            # multiply-connected annulus into one simply-connected
            # hole-free ring (to_osm drops interior rings, which would
            # fill the ramp with a disc).
            _slit = _bp
            _guard = 0
            while (_slit is not None and _slit.geom_type == 'Polygon'
                   and _slit.interiors and _guard < 8):
                _guard += 1
                try:
                    _pa, _pb = nearest_points(
                        _slit.interiors[0], _slit.exterior)
                except _GEOM_EXC:
                    _slit = None
                    break
                _kdx, _kdy = _pb.x - _pa.x, _pb.y - _pa.y
                _kl = math.hypot(_kdx, _kdy) or 1.0
                _kux, _kuy = _kdx / _kl, _kdy / _kl
                _knife = LineString([
                    (_pa.x - _kux * 0.1, _pa.y - _kuy * 0.1),
                    (_pb.x + _kux * 0.1, _pb.y + _kuy * 0.1),
                ]).buffer(0.02, cap_style=2, join_style=2)
                try:
                    _cut = _slit.difference(_knife)
                except _GEOM_EXC:
                    _slit = None
                    break
                if _cut.geom_type == 'MultiPolygon':
                    _cut = max(_cut.geoms, key=lambda g: g.area)
                _slit = (_cut if _cut.geom_type == 'Polygon'
                         and not _cut.is_empty else None)
            if (_slit is None or _slit.geom_type != 'Polygon'
                    or _slit.is_empty or _slit.interiors):
                continue
            _ring0 = list(_slit.exterior.coords)
            if _ring0 and _ring0[0] == _ring0[-1]:
                _ring0 = _ring0[:-1]
            if len(_ring0) < 4:
                continue
            try:
                _wp0 = Polygon(_ring0)
            except _GEOM_EXC:                          # pragma: no cover
                continue
            # THE SLIT RING MAY SELF-TOUCH — repaired BEFORE the
            # partition (Amendment 2).  On a thin band the traversal of
            # outer boundary, 0.02 m knife and inner boundary can close
            # on itself, and ``Polygon`` of a self-touching ring is
            # INVALID: its ``area`` and ``intersection`` are then
            # unreliable, so a partition of it would be too.
            if not _wp0.is_valid:
                _wp0 = _wp0.buffer(0)
                if _wp0.geom_type == 'MultiPolygon':
                    _wp0 = max(_wp0.geoms, key=lambda g: g.area)
            if (_wp0 is None or _wp0.is_empty
                    or _wp0.geom_type != 'Polygon'):
                continue
            # ── THE PARTITION ────────────────────────────────────────
            # foot = band ∩ region, face = band − region.  Disjoint by
            # construction; both rings AND both altitude vectors come
            # from the FINAL geometry, never from ``_ring0`` (deriving
            # values before the split is the ordering that desynchronised
            # the rings from their node_altitudes).
            _parts: list = []
            if _region is None:
                _parts.append((_wp0, "tunnel_wall", False, None))
            else:
                try:
                    _foot_g = _wp0.intersection(_region)
                    _face_g = _wp0.difference(_region)
                except _GEOM_EXC:                      # pragma: no cover
                    continue
                _inner_b = None
                try:
                    _inner_b = _region.boundary
                except _GEOM_EXC:                      # pragma: no cover
                    _inner_b = None
                for _g in getattr(_foot_g, 'geoms', [_foot_g]):
                    if (_g is not None and not _g.is_empty
                            and _g.geom_type == 'Polygon'
                            and _g.area >= 0.05):
                        _parts.append(
                            (_g, TUNNEL_WALL_FOOT_REF, True, None))
                for _g in getattr(_face_g, 'geoms', [_face_g]):
                    if (_g is not None and not _g.is_empty
                            and _g.geom_type == 'Polygon'
                            and _g.area >= 0.05):
                        _parts.append(
                            (_g, "tunnel_wall", False, _inner_b))
            for _wp, _wall_ref, _is_foot, _inner_b in _parts:
                try:
                    if _emitted_band:
                        _wp = _wp.difference(unary_union(_emitted_band))
                        if _wp.geom_type == 'MultiPolygon':
                            _wp = max(_wp.geoms, key=lambda g: g.area)
                        if (_wp is None or _wp.is_empty
                                or _wp.geom_type != 'Polygon'
                                or _wp.area < 0.05):
                            continue
                    if not _wp.is_valid:
                        _wp = _wp.buffer(0)
                        if _wp.geom_type == 'MultiPolygon':
                            _wp = max(_wp.geoms, key=lambda g: g.area)
                    if (_wp is None or _wp.is_empty
                            or _wp.geom_type != 'Polygon'
                            or _wp.interiors):
                        continue
                    _emitted_band.append(_wp)
                    _ring = list(_wp.exterior.coords)
                    if _ring and _ring[0] == _ring[-1]:
                        _ring = _ring[:-1]
                    if len(_ring) < 4:
                        continue
                    _vals = _band_altitudes(_ring, _inner_b, _is_foot)
                    _na = [round(_v, 1) for _v in _vals]
                    _na.append(_na[0])
                    # R10-2: the band is buffered per ramp-union POLYGON,
                    # so it crosses sibling ramps and every earlier
                    # cluster's; cut it against the whole tunnel pavement
                    # and keep EVERY surviving arc.
                    for _piece in _tunnel_cover_pieces(
                            BuiltShape(
                                polygon=_wp,
                                role=ROLE_RETAINING_WALL,
                                ref=_wall_ref,
                                node_altitudes=_na),
                            _pav_u_band):
                        layout.shapes.append(_piece)
                except _GEOM_EXC:
                    continue
            # The exclusion zone stays the ANNULUS ``_bp`` (the ring
            # fills its own hole — carrying that into the zones would
            # over-carve the boundary ribbon over ground the band never
            # occupies), and it is the WHOLE band, once, not once per
            # partition part.
            exclusion_zones.append(_bp)


def _low_connector_corridors(low_connector_gaps: list) -> list:
    """Dissolve the recorded per-way gap rects into corridor polygons.

    Each gap is ``(gap_line, corridor_width_m)``; gaps of grouped
    parallel ways (< ``UNDERPASS_GROUP_DIST_M`` apart) dissolve into
    ONE corridor via a morphological closing, so the group renders as
    a single depressed trench spanning its combined width.
    """
    if not low_connector_gaps:
        return []
    rects = []
    for (gap_line, corridor_width_m) in low_connector_gaps:
        try:
            r = gap_line.buffer(corridor_width_m / 2.0,
                                cap_style=2, join_style=2)
            if not r.is_empty:
                rects.append(r)
        except _GEOM_EXC:
            continue
    if not rects:
        return []
    try:
        merged = unary_union(rects)
        close_r = UNDERPASS_GROUP_DIST_M / 2.0
        merged = (merged.buffer(close_r, join_style=2)
                        .buffer(-close_r, join_style=2))
    except _GEOM_EXC:
        merged = unary_union(rects)
    return ([merged] if merged.geom_type == "Polygon"
            else [g for g in getattr(merged, "geoms", ())
                  if g.geom_type == "Polygon"])


def _suppress_portals_in_low_corridors(
        portal_data: list, corridors: list) -> list:
    """Drop portals whose mouth sits INSIDE a low-connector corridor.

    OSM splits ways at intersections, so a frontage road's crossings
    of taxiway A and taxiway B often live on DIFFERENT ways — the
    per-way gap merge cannot see across them, and both leftover
    portals would ramp INTO the flat low corridor (overlapping it and
    each other).  The corridor covers the whole grouped surface, so
    any portal starting inside it is superseded by the flat rect.
    """
    if not corridors or not portal_data:
        return portal_data
    kept = []
    for pd in portal_data:
        walk_pts = pd[2]
        px, py = walk_pts[0]
        inside = False
        for corridor in corridors:
            try:
                if corridor.buffer(2.0).contains(Point(px, py)):
                    inside = True
                    break
            except _GEOM_EXC:
                continue
        if inside:
            if os.environ.get("O4_TUNNEL_DEBUG") == "1":
                print(f"    [tunnel-drop] way {pd[1]} portal "
                      f"({px:.0f},{py:.0f}): inside a flat "
                      f"low-connector corridor")
            continue
        kept.append(pd)
    return kept


def _emit_low_corridor_connectors(
        layout: "PavementLayout",
        corridors: list,
        exclusion_zones: list,
        airside_gate_union,
        airport_elevation_at,
        dem_at,
        tunnel_depth_m: float,
        wall_gap_m: float,
        retaining_wall_width_m: float) -> int:
    """Emit the depressed surface BETWEEN two merged bores.

    User 2026-07-04 (KDFW double parallel taxiways): when the surface
    gap between two taxiway underpasses is too short for a ramp pair
    to climb to DEM and come back, the whole area between them stays
    at the LOW elevation — a single corridor-width flat
    ``ROLE_TUNNEL_RAMP`` rect at ``apt_elev − tunnel_depth_m`` with a
    retaining wall around its open sides.  Gaps of grouped parallel
    ways (< ``UNDERPASS_GROUP_DIST_M`` apart) dissolve into ONE
    corridor via a morphological closing, so the group renders as a
    single depressed trench, never overlapping per-way rects.

    Walls take their crest from the §F1 STATION law like every other
    tunnel wall (LEMD fidelity spec law 1; the per-vertex DEM sample
    user 2026-06-13 asked for stands under ``O4_WALL_TOP_STATION=0``,
    and it is what twisted the -11960/-11930/-11961 bands); the
    strip under the taxiways themselves is
    NOT walled or paved here — the bores continue beneath.  All
    emitted pieces join ``exclusion_zones`` so the boundary ribbon
    and DEM bridges avoid them.  Takes the dissolved ``corridors``
    from :func:`_low_connector_corridors` (also used to suppress
    superseded portals).  Returns the number of corridor rects
    emitted.
    """
    if not corridors:
        return 0
    n_rects = 0
    for corridor in corridors:
        if corridor.is_empty or corridor.area < 20.0:
            continue
        try:
            centre = corridor.centroid
            apt_elev = airport_elevation_at(centre.x, centre.y)
        except _GEOM_EXC:
            apt_elev = None
        if apt_elev is None:
            continue
        elev_low = float(apt_elev) - tunnel_depth_m
        # The visible depressed surface: the corridor minus airside
        # pavement (a graze against a service road / building pad
        # must not put a −8 m rect under real pavement).
        #
        # RULING 3 (owner 2026-08-07, OTHH): the cutback clears
        # ``_TUNNEL_GRAZE_CLEARANCE_M`` (0.6 m) like every other tunnel
        # emitter, not SHARED_VERTEX_TOL_M (0.5 m) exactly — at exactly
        # the bucket size a corridor corner can still land in a solved
        # pavement vertex's intern bucket and inherit its altitude (the
        # −5.16/+3.19 needle on OTHH way -11724).
        try:
            open_part = (corridor if airside_gate_union is None
                         else corridor.difference(
                             airside_gate_union.buffer(
                                 _TUNNEL_GRAZE_CLEARANCE_M)))
        except _GEOM_EXC:
            open_part = corridor
        surf_parts = ([open_part] if open_part.geom_type == "Polygon"
                      else [g for g in getattr(open_part, "geoms", ())
                            if g.geom_type == "Polygon"])
        emitted_surface: list = []
        for part in surf_parts:
            if part.is_empty or part.area < 4.0:
                continue
            simple = part.simplify(0.05)
            if simple.geom_type != "Polygon" or simple.is_empty:
                simple = part
            n_vertices = len(simple.exterior.coords)
            layout.shapes.append(BuiltShape(
                polygon=simple, role=ROLE_TUNNEL_RAMP,
                ref="tunnel_low_connector",
                node_altitudes=[round(elev_low, 2)] * n_vertices))
            exclusion_zones.append(simple)
            emitted_surface.append(simple)
            n_rects += 1
        # Retaining wall around the corridor's open sides: a 1 m band
        # offset by the standard wall gap, minus airside pavement (the
        # bores continue under the taxiways — no wall across the road).
        try:
            # R16-2b: the face starts AT the EMITTED surface's edge (the
            # simplified, graze-cut rects — not the corridor they were
            # derived from), so the wall's inner boundary is that
            # surface's boundary vertex for vertex, and no strip between
            # them is left for the mesh to drape.
            _surface_u = (unary_union(emitted_surface) if emitted_surface
                          else corridor)
            band = (corridor.buffer(
                        wall_gap_m + retaining_wall_width_m,
                        join_style=2)
                    .difference(_surface_u))
            if airside_gate_union is not None:
                band = band.difference(airside_gate_union.buffer(0.5))
        except _GEOM_EXC:
            band = None
            _surface_u = corridor
        # ── §F1: THE WALL TOP IS FLAT ACROSS ITS WIDTH, HERE TOO ─────
        # (LEMD ramp/road fidelity spec law 1, DOCKETED by its
        # Amendment 1: "second wall emitter ``_emit_low_corridor_
        # connectors`` still samples DEM per node — owns the residual
        # 0.34/0.24/0.20 m twisted bands (-11960/-11930/-11961)".)
        # This band is the SAME structure ``emit_wall_band`` builds and
        # the defect is the same one: each crest vertex read ``dem_at``
        # at its own position, and the two vertices facing each other
        # across a ~1 m band stand at opposite ends of the ring, so
        # nothing tied their values together.  ONE LAW, ONE CLASS: the
        # crest is a function of STATION on the body being walled
        # (``_CrestProfile``), read at each vertex's nearest point on
        # the corridor's own ring — a cross-band pair projects to ONE
        # station and carries ONE value by construction.  Same gate
        # (``O4_WALL_TOP_STATION``); OFF restores the per-vertex sample
        # byte for byte.
        _crest = None
        if wall_top_station_law_enabled():
            try:
                from .groundside import (
                    GROUNDSIDE_MAX_GRADE as _GS_CAP,
                    _BelowGradeIndex,
                )
                _csrc = []
                for _sp in (emitted_surface or ()):
                    _sr = list(_sp.exterior.coords)
                    if len(_sr) > 1 and _sr[0] == _sr[-1]:
                        _sr = _sr[:-1]
                    if len(_sr) >= 3:
                        _csrc.append(
                            (_sp, _sr, [float(elev_low)] * len(_sr)))
                if _csrc:
                    _crest = _CrestProfile(
                        corridor, dem_at, float(apt_elev),
                        _BelowGradeIndex(_csrc), _GS_CAP)
                    if not _crest:
                        _crest = None
            except (ImportError, *_GEOM_EXC):        # pragma: no cover
                _crest = None
        band_parts = ([] if band is None else
                      ([band] if band.geom_type == "Polygon"
                       else [g for g in getattr(band, "geoms", ())
                             if g.geom_type == "Polygon"]))
        for wall in band_parts:
            if wall.is_empty or wall.area < 1.0:
                continue
            # to_osm drops interior rings — slit any annulus open at
            # its narrowest point (same trick as the perimeter wall).
            slit = wall
            guard = 0
            while (slit is not None and slit.geom_type == "Polygon"
                   and slit.interiors and guard < 8):
                guard += 1
                try:
                    pa, pb = nearest_points(
                        slit.interiors[0], slit.exterior)
                    kdx, kdy = pb.x - pa.x, pb.y - pa.y
                    kl = math.hypot(kdx, kdy) or 1.0
                    kux, kuy = kdx / kl, kdy / kl
                    knife = LineString([
                        (pa.x - kux * 0.1, pa.y - kuy * 0.1),
                        (pb.x + kux * 0.1, pb.y + kuy * 0.1),
                    ]).buffer(0.02, cap_style=2, join_style=2)
                    cut = slit.difference(knife)
                    if cut.geom_type == "MultiPolygon":
                        cut = max(cut.geoms, key=lambda g: g.area)
                    slit = (cut if cut.geom_type == "Polygon"
                            and not cut.is_empty else None)
                except _GEOM_EXC:
                    slit = None
            if (slit is None or slit.geom_type != "Polygon"
                    or slit.is_empty or slit.interiors):
                continue
            ring = list(slit.exterior.coords)
            if ring and ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) < 4:
                continue
            wall_alts = []
            for (vx, vy) in ring:
                # R16-2b: a vertex ON the corridor edge is the CORRIDOR's
                # vertex and carries its value (one node, one value); the
                # crest keeps the DEM.
                try:
                    _on_edge = (_surface_u.boundary.distance(Point(vx, vy))
                                <= _WALL_FACE_ON_PAVEMENT_TOL_M)
                except _GEOM_EXC:                      # pragma: no cover
                    _on_edge = False
                if _on_edge:
                    wall_alts.append(round(float(elev_low), 2))
                    continue
                # §F1: the crest at THIS vertex's station on the walled
                # body, not the DEM under the vertex itself.
                _cv = None if _crest is None else _crest.at((vx, vy))
                if _cv is not None:
                    wall_alts.append(round(float(_cv), 1))
                    continue
                ground = dem_at(vx, vy)
                wall_alts.append(round(
                    ground if ground is not None else float(apt_elev), 1))
            wall_alts.append(wall_alts[0])
            try:
                wall_poly = Polygon(ring)
                if wall_poly.is_empty:
                    continue
                layout.shapes.append(BuiltShape(
                    polygon=wall_poly, role=ROLE_RETAINING_WALL,
                    ref="tunnel_wall", node_altitudes=wall_alts))
                exclusion_zones.append(wall)
            except _GEOM_EXC:
                continue
    if n_rects:
        try:
            UI.vprint(1,
                f"  [pav-builder] emitted {n_rects} flat low-corridor "
                f"connector(s) between close taxiway underpasses.")
        except _GEOM_EXC:
            pass
    return n_rects


# Clearance kept between a graze-clipped tunnel piece and the airside
# pavement that grazed it.  Must exceed the OSM-emit shared-vertex
# bucket (SHARED_VERTEX_TOL_M = 0.5 m) so a clipped ramp/wall edge
# never hashes onto a pavement node — same rationale as ``wall_gap_m``
# (user 2026-05-03: one node with two altitudes renders as a vertical
# glitch).
_TUNNEL_GRAZE_CLEARANCE_M = 0.6

# R16-2b: how close a wall-band vertex must sit to the pavement it
# faces to BE that boundary's vertex (metres).  The band's inner ring
# is derived FROM the ramp/corridor polygon, so the coincidence is
# exact; the tolerance only absorbs buffer/difference round-off.  A
# vertex inside it carries the RAMP's value, which is what makes the
# shared node one value instead of two (the 2026-05-03 glitch class
# the old ``wall_gap`` standoff avoided by leaving the strip UNOWNED —
# and an unowned strip is drape-at-DEM, the defect this replaces).
_WALL_FACE_ON_PAVEMENT_TOL_M = 0.01

# The pavement union a tunnel piece is gated against (the per-portal
# AIRSIDE / DOUBLE-EMIT gate and the pavement-overlap clip read the same
# set).  Module-level because ``_finalize_tunnel_emission`` REBUILDS the
# union after ruling 4's ramp cut — a second literal list there is
# exactly the role-literal drift ``blast.py`` flags.
_AIRSIDE_GATE_ROLES = (
    "runway", "runway_crossing", "primary_parallel",
    "secondary_parallel", "stub", "cross_connector", "junction",
    "apron", "building", "groundside_pavement", "service_road",
    "service_junction")
# R10-1/A6's pavement side of the cover discriminator: the same roles
# MINUS ``building``, which is the other side.  Derived, never a second
# hand-written role list — a role added to the gate above is pavement
# here by construction.
_TUNNEL_COVER_PAVEMENT_ROLES = tuple(
    _role for _role in _AIRSIDE_GATE_ROLES if _role != "building")

# RULING 4 SAFETY FLOOR (owner-flagged 2026-08-07, spec
# ``tunnel-portal-fidelity-spec.md`` §2 C-4): the RUNWAY FAMILY a tunnel
# ramp may never cut.  ``pavement_cut_roles`` lists runway +
# runway_crossing as cuttable because a hard DECK seats flush in them;
# a road RAMP is a trench, and a trench across a runway (or its
# end-skirt / RESA clearance shapes) is unlawful at any overlap
# fraction.  So these roles are removed from the ramp's cut set, and a
# ramp piece mostly ON one is dropped LOUDLY rather than silently
# clipped.
# R20-2b (AMENDMENT 1): the AIRCRAFT-TRANSIT family, not just the runway
# family.  R14-2/A-3 already ruled that a cut never interrupts a taxiway
# ("an aircraft cannot detour round a trench") and removed those roles
# from :func:`_tunnel_ramp_cut_roles` — but the SAFETY FLOOR here only
# ever dropped runway-family pieces, so a ramp reaching a taxiway neither
# cut it nor stood down: it simply laid ramp pavement on top of it at
# ramp elevation.  Nothing produced that before, because the run could
# not reach; R20-2's DEM-reach extension can, and a run that never meets
# ground would walk its whole 500 m walk.  Not cutting and not yielding
# is the worst of the three, so the two sets are now the same set — the
# roles a ramp may not cut are exactly the roles a ramp yields to.
_RAMP_NEVER_CUT_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_RUNWAY_CLEARANCE,
}) | _TUNNEL_PROTECTED_TRANSIT_ROLES
# Fraction of a ramp piece's own area that must lie on a runway-family
# shape for the safety floor to drop it (mirrors the pavement-overlap
# clip's "mostly covered" discriminator).
_RAMP_RUNWAY_DROP_FRACTION = 0.5


def _tunnel_ramp_cut_roles() -> frozenset:
    """The pavement roles a tunnel ramp CUTS: ruling R13's
    groundside-inclusive set, minus the runway family the safety floor
    protects, minus R14-2/A-3's aircraft-transit family.

    Ruling 4 ("the tunnel ramp wins over pavement") still governs apron
    and the service/groundside roads where its beheading precedent was
    measured; it does NOT reach the taxiway family, which R14-2 protects
    outright."""
    return frozenset(
        pavement_cut_roles(include_groundside=True)
        - _RAMP_NEVER_CUT_ROLES - _TUNNEL_PROTECTED_TRANSIT_ROLES)


def _tunnel_ramp_pavement_cut(layout: "PavementLayout",
                              airside_gate_union,
                              pre_emit_shape_ids: set,
                              ramp_way_ids: dict | None = None,
                              clearance_m: float = 0.0):
    """RULING 4 (owner 2026-08-07, OTHH) — the tunnel ramp WINS over the
    pavement it surfaces through: it cuts that pavement, through the same
    helper ruling R13 uses over an open pit.

    Runs before the pavement-overlap clip, on the ramp pieces this
    emission produced.  Two steps:

      1. SAFETY FLOOR — a ramp piece whose area is ≥
         ``_RAMP_RUNWAY_DROP_FRACTION`` on a ``_RAMP_NEVER_CUT_ROLES``
         shape is DROPPED with a ``vprint(1)`` naming its source way and
         the shape.  A ramp never cuts the runway family, so the runway
         roles are also absent from :func:`_tunnel_ramp_cut_roles`.
      2. The surviving ramps' CLEARANCE ANNULUS cuts the pavement.

    ``clearance_m`` (spec ``tunnel-ramp-cut-boundaries-spec.md`` §2 —
    W/G-1) is what makes the cut a CLEARANCE ANNULUS instead of the bare
    ramp union, and it is the geometric fix for the whole minting class
    the parent round produced.  Ruling 4 removed the 0.6 m graze push,
    so a new ramp corner could land INSIDE a solved pavement vertex's
    ``SHARED_VERTEX_TOL_M`` (0.5 m) intern bucket; ``layout.to_osm``'s
    authority precedence then welded one value across what is physically
    a retaining wall (OTHH: 148 ways byte-identical in geometry with
    drifted altitudes; the ``-11816`` fork throat adopting junction node
    ``-1498``'s 3.60 against its own uniform 1.30).  Cutting the
    pavement back by ``wall_gap_m + retaining_wall_width_m`` — the SAME
    geometry the continuous perimeter wall band occupies — leaves no
    remaining pavement vertex within the bucket of any ramp ring, so
    cross-boundary interning is geometrically impossible and every cut
    edge reads pavement | wall | ramp.

    Returns the airside pavement union AS IT NOW STANDS — the SAME
    object when nothing was cut, so the caller's clip is byte-identical
    on airports with no ramp/pavement overlap.  The rebuild is R13's
    union bookkeeping (``_reindex_owned_ground``): without it a portal
    wall would be dropped for overlapping pavement its own ramp just
    removed.
    """
    if airside_gate_union is None:
        return airside_gate_union
    ramps = [s for s in layout.shapes
             if id(s) not in pre_emit_shape_ids
             and getattr(s, "ref", "") in _TUNNEL_PAVEMENT_CUT_REFS
             and s.polygon is not None and not s.polygon.is_empty]
    if not ramps:
        return airside_gate_union
    # ── 1. SAFETY FLOOR ──────────────────────────────────────────────
    protected = [s for s in layout.shapes
                 if s.role in _RAMP_NEVER_CUT_ROLES
                 and s.polygon is not None and not s.polygon.is_empty]
    dropped_ids: set[int] = set()
    for ramp in (ramps if protected else ()):
        try:
            ramp_area = ramp.polygon.area
        except _GEOM_EXC:
            continue
        if ramp_area <= 0.0:
            continue
        for shape in protected:
            try:
                overlap = ramp.polygon.intersection(shape.polygon).area
            except _GEOM_EXC:
                continue
            if overlap < _RAMP_RUNWAY_DROP_FRACTION * ramp_area:
                continue
            dropped_ids.add(id(ramp))
            _wid = (ramp_way_ids or {}).get(id(ramp))
            try:
                UI.vprint(1,
                    f"  [pav-builder] DROPPED tunnel ramp piece of way "
                    f"{_wid if _wid is not None else '?'} — "
                    f"{100.0 * overlap / ramp_area:.0f} % of it lies on "
                    f"{shape.role} '{getattr(shape, 'ref', '') or '-'}'; "
                    f"a tunnel ramp never cuts a runway-family shape.")
            except _GEOM_EXC:
                pass
            break
    if dropped_ids:
        layout.shapes = [s for s in layout.shapes
                         if id(s) not in dropped_ids]
        ramps = [r for r in ramps if id(r) not in dropped_ids]
    if not ramps:
        return airside_gate_union
    # ── 2. THE CUT ───────────────────────────────────────────────────
    try:
        ramp_union = unary_union([r.polygon for r in ramps])
    except _GEOM_EXC:
        return airside_gate_union
    if ramp_union is None or ramp_union.is_empty:
        return airside_gate_union
    # THE CLEARANCE ANNULUS: mitred (``join_style=2``) so the cut
    # follows the same offset geometry the perimeter wall band is built
    # from (``_emit_portal_cluster``: ``buffer(_g1, join_style=2)``) and
    # can never fall SHORT of the band's outer edge — a band judged
    # against pavement its own cut left behind would be dropped as
    # "under pavement".
    cut_footprint = ramp_union
    if clearance_m > 0.0:
        try:
            cut_footprint = ramp_union.buffer(clearance_m, join_style=2)
        except _GEOM_EXC:
            cut_footprint = ramp_union
    n_cut = cut_pavement_over_footprint(
        layout, cut_footprint, cut_roles=_tunnel_ramp_cut_roles())
    if not n_cut:
        return airside_gate_union
    try:
        UI.vprint(1,
            f"  [pav-builder] tunnel ramps cut {n_cut} pavement shape(s) "
            f"they surface through (ruling 4 — the ramp wins), with a "
            f"{clearance_m:.1f} m clearance annulus the wall band owns.")
    except _GEOM_EXC:
        pass
    try:
        post = unary_union(
            [s.polygon for s in layout.shapes
             if s.polygon is not None and not s.polygon.is_empty
             and s.role in _AIRSIDE_GATE_ROLES])
    except _GEOM_EXC:
        return airside_gate_union
    return None if post.is_empty else post


#: §W1 gate (spec ``docs/specs/claimed-corridor-wall-survival-spec.md``).
#: Default ON; OFF returns the post-cut gate object VERBATIM, so the
#: adjudication below is byte-identical to the pre-round behaviour.
_CLAIM_WALL_GATE_ENV = "O4_CLAIM_WALL_GATE"


def claim_wall_gate_enabled() -> bool:
    return os.environ.get(_CLAIM_WALL_GATE_ENV, "1") == "1"


def _claim_wall_adjudication_gate(layout: "PavementLayout",
                                  post_gate_u, clearance_m: float):
    """§W1 — A WALL FOLLOWS ITS CLAIM AS IT FOLLOWS ITS RAMP.

    Ruling 4 gave the wall/roof adjudication a POST-CUT pavement union:
    a wall must not be dropped for overlapping pavement its own ramp has
    removed (:func:`_tunnel_ramp_pavement_cut`).  Only SYNTHETIC ramp
    footprints are cut, though.  A CLAIMED corridor lowers its host
    WITHOUT cutting it — that is the whole of the mouth-D claim design
    (RULINGS 2026-08-25e option (a)) — so the §2.3 walls the claim just
    minted overlap host pavement 50-100 % and drop whole as "covered
    stretch".  Measured at OTHH 1.0.264: "15 claimed corridor bodies
    walled (20 wall pieces)" born, then ~20 dropped and 12 graze-clipped
    to slivers, the owner's own site among them (way 2291
    @25.2559488,51.6086658, coverage 0.743, area 319.4 m²).

    THE CUT IS FOR ADJUDICATION ONLY.  The host shape's geometry is not
    touched: this returns a JUDGING union, never the layout's pavement.
    The subtracted region is the ``_CLAIMED_BORE_REGISTER`` population
    (the very footprints :func:`_wall_claimed_corridors` walled — one
    population, published, never re-derived) buffered by the wall band's
    own annulus, exactly the annulus ruling 4's ramp cut uses and built
    with the same mitred join so it can never fall short of the band's
    outer edge.

    SCOPE GUARD.  A claim stretch that is ALSO in the item-12 covered-span
    mask stays COVERED: a genuinely roofed span (under the terminal
    bridge) has no visible structure and its walls still drop.  The mask
    is ``covered_span.mask_of`` — the published one, not a second
    derivation.

    Returns the union to judge wall/roof pieces against (possibly
    ``None`` when nothing airside is left), and is a NO-OP returning
    ``post_gate_u`` itself when the gate is off, when nothing was
    claimed, or when the relief is empty.
    """
    if not claim_wall_gate_enabled() or post_gate_u is None:
        return post_gate_u
    _register = getattr(layout, _CLAIMED_BORE_REGISTER, None) or set()
    # ── THE POPULATION IS THE CLAIM, MEASURED 2026-08-29 ──────────────
    # Three sources, unioned, because the first implementation used only
    # the third and OTHH's own removal ledger showed what that misses:
    #  (a) THE WALLED BODIES the §2.3 waller published — the footprints
    #      §W1's text names.  Re-deriving them from ``s.polygon`` at gate
    #      time drifts: 4 of 11 dropped pieces stood 2.8-382 m from any
    #      surviving below-grade claim, because a claim can lose its dug
    #      profile downstream (19 registered, 12 below-grade at emit).
    #  (b) EVERY SHAPE CARRYING A CLAIM VERDICT (``ref ==
    #      TUNNEL_ROAD_REF``, the predicate
    #      ``groundside.claimed_tunnel_corridor`` reads), whatever depth
    #      that stretch reached.  MEASURED: drops 2371/2373 sit on
    #      -12291 and 2353/2355 on -12298, both claimed corridors that
    #      happen to be AT GRADE, so the below-grade subset never
    #      relieved them.  A claimed corridor's footprint is the bore's
    #      footprint; it does not COVER the structure that retains it.
    #  (c) the id register, kept so a body whose ref was lost is still
    #      relieved.
    # Adjudication only — no host geometry is touched either way, and
    # the covered-span mask still holds genuinely roofed stretches back.
    _claims = list(getattr(layout, _CLAIMED_BORE_BODIES, None) or ())
    _claims = [g for g in _claims
               if g is not None and not g.is_empty]
    for s in layout.shapes:
        _p = getattr(s, "polygon", None)
        if _p is None or _p.is_empty:
            continue
        if (getattr(s, "ref", "") == TUNNEL_ROAD_REF
                or id(s) in _register):
            _claims.append(_p)
    if not _claims:
        return post_gate_u
    try:
        _relief = unary_union(_claims)
        if clearance_m > 0.0:
            _relief = _relief.buffer(clearance_m, join_style=2)
    except _GEOM_EXC:                                    # pragma: no cover
        return post_gate_u
    if _relief is None or _relief.is_empty:
        return post_gate_u
    _n_claims = len(_claims)
    _covered_area = 0.0
    try:
        from . import covered_span as _covered_span
        _mask = _covered_span.mask_of(layout)
    except Exception:                                    # pragma: no cover
        _mask = None
    if _mask is not None:
        try:
            _covered_area = _relief.intersection(_mask).area
            _relief = _relief.difference(_mask)
        except _GEOM_EXC:                                # pragma: no cover
            return post_gate_u
        if _relief is None or _relief.is_empty:
            try:
                UI.vprint(1,
                    f"  [pav-builder] §W1 claim wall gate: all "
                    f"{_n_claims} claimed-corridor footprint(s) lie "
                    f"inside the covered-span mask — every stretch is a "
                    f"genuinely roofed one, so the adjudication union is "
                    f"UNCHANGED and those walls still drop.")
            except _GEOM_EXC:                            # pragma: no cover
                pass
            return post_gate_u
    try:
        _gate = post_gate_u.difference(_relief)
    except _GEOM_EXC:                                    # pragma: no cover
        return post_gate_u
    try:
        UI.vprint(1,
            f"  [pav-builder] §W1 claim wall gate: {_n_claims} claimed-"
            f"corridor footprint(s) + the {clearance_m:.1f} m wall-band "
            f"annulus ({_relief.area:.0f} m²) subtracted from the "
            f"wall/roof adjudication union only "
            f"({post_gate_u.area:.0f} → "
            f"{0.0 if _gate is None or _gate.is_empty else _gate.area:.0f} "
            f"m²; {_covered_area:.0f} m² held back by the covered-span "
            f"mask) — a wall follows its CLAIM as it follows its ramp.  "
            f"No host geometry is touched.")
    except _GEOM_EXC:                                    # pragma: no cover
        pass
    return None if (_gate is None or _gate.is_empty) else _gate


def _sloped_rect_clipped_altitudes(orig_poly, alt_high, alt_low,
                                   new_poly):
    """Per-vertex altitudes for a clipped ``altitude_high/low`` rect.

    A sloped rect encodes its gradient by RING ORDER (corners 0,3 =
    high edge, corners 1,2 = low edge — the ``_rect_from_axis_extended``
    convention), which any polygon clip destroys.  Convert to explicit
    ``node_altitudes``: project every new ring vertex onto the rect's
    slope axis (low-edge midpoint → high-edge midpoint) and lerp.
    Returns the closed altitude list for ``new_poly``'s exterior ring,
    or None when the original ring is not the 4-corner rect the
    convention promises (caller should then drop the piece).
    """
    try:
        ring = list(orig_poly.exterior.coords)
    except _GEOM_EXC:
        return None
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) != 4:
        return None
    c0, c1, c2, c3 = ring
    mid_high = ((c0[0] + c3[0]) / 2.0, (c0[1] + c3[1]) / 2.0)
    mid_low = ((c1[0] + c2[0]) / 2.0, (c1[1] + c2[1]) / 2.0)
    ax = mid_high[0] - mid_low[0]
    ay = mid_high[1] - mid_low[1]
    axis_len_sq = ax * ax + ay * ay
    if axis_len_sq < 1e-6:
        return None
    alts = []
    try:
        new_ring = list(new_poly.exterior.coords)
    except _GEOM_EXC:
        return None
    for (vx, vy) in new_ring:
        t = ((vx - mid_low[0]) * ax + (vy - mid_low[1]) * ay) \
            / axis_len_sq
        t = max(0.0, min(1.0, t))
        alts.append(round(alt_low + t * (alt_high - alt_low), 2))
    return alts


def log_tunnel_piece_removal(layout, shape, predicate: str, *,
                             coverage=None, cluster=None,
                             index=None, verdict=None) -> None:
    """ONE LINE PER PIECE a post-emit pass removes or clips.

    Spec ``docs/specs/portal-corridor-claim-spec.md`` §1 (RULINGS
    2026-08-25e), and it is MANDATORY AND UNGATED — the instrument is
    law, not behaviour.  The evidence: OTHH mouth D is admitted and
    emitted ("[tunnel-cover-bore] admitted on cover (pavement=0.993)")
    and then every piece of it disappears through three aggregate-
    logging passes.  4 of 8 OTHH portal clusters lose every ramp that
    way, and because no remover NAMED what it deleted, the acceptance
    instrument could only report the mouth as 806 m away: absence is all
    there is to see.

    THE CENTROID IS THE JOIN KEY.  A removed piece never reaches the
    emit, so it has no way id and no ``shapeID`` — ``index`` is only its
    position in ``layout.shapes`` at removal time.  What survives is
    where it was, which is the coordinate a reviewer flies to and the
    one the sibling ``tunnel_airside_conflict`` finding already records
    for exactly this reason (that finding named a role, an area and NO
    PLACE, and saying which shape it meant took a geometric
    re-derivation off an emitted patch).

    Frame: ``_local_meter_projections`` — the module's own shared
    equirectangular projection, as every sibling finding here uses.
    """
    try:
        _poly = getattr(shape, "polygon", None)
        _lat = _lon = None
        if _poly is not None and not _poly.is_empty:
            _, _to_ll = _local_meter_projections(layout.anchor)
            _c = _poly.centroid
            _lat, _lon = _to_ll(_c.x, _c.y)
        _where = ("?" if _lat is None else f"{_lat:.7f},{_lon:.7f}")
        _cov = "" if coverage is None else f" coverage={coverage:.3f}"
        _cl = ""
        if cluster is not None:
            try:
                _cl = f" cluster=({cluster[0]:.0f},{cluster[1]:.0f})"
            except (TypeError, IndexError, ValueError):
                _cl = ""
        _area = (f" area={_poly.area:.1f}m2"
                 if _poly is not None and not _poly.is_empty else "")
        _vd = "" if not verdict else f" [{verdict}]"
        UI.vprint(1,
                  f"  [tunnel-remove] {predicate}: "
                  f"ref={getattr(shape, 'ref', '') or '-'} "
                  f"role={getattr(shape, 'role', '') or '-'} "
                  f"way={'-' if index is None else index} "
                  f"@{_where}{_cov}{_area}{_cl}{_vd}")
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        # An instrument may never take a build down.
        return


def _covering_shapes(layout: "PavementLayout", shape,
                     pre_emit_shape_ids: set, top: int = 3) -> str:
    """WHICH surfaces a dropped cover piece is judged to be under.

    Portal-corridor-claim §1 gave every removal a NAMED line; a drop
    predicate that names a coverage FRACTION and not the covering
    SURFACE still costs a re-derivation off the emitted patch to answer
    "covered by what?" — which is the question the §W1 residual turns
    on (a wall over its own claim's host is the defect; a wall under a
    terminal is the law).  Cheap: it runs only on the handful of pieces
    that actually drop.
    """
    try:
        _poly = getattr(shape, "polygon", None)
        if _poly is None or _poly.is_empty:
            return ""
        # THE GATE'S OWN POPULATION, not a narrower one: the union is
        # ``role in _AIRSIDE_GATE_ROLES`` over the CURRENT layout, so the
        # coverer may be a shape MINTED during this emission (a claim
        # strip, a cut host's remainder).  Reading only the pre-emit set
        # reported "covered by NOTHING" for 8 of 11 OTHH drops, which is
        # the instrument lying, not the union being stale.
        _reg = getattr(layout, _CLAIMED_BORE_REGISTER, None) or set()
        _hits = []
        for _o in layout.shapes:
            if _o is shape:
                continue
            if getattr(_o, "role", "") not in _AIRSIDE_GATE_ROLES:
                continue
            _op = getattr(_o, "polygon", None)
            if _op is None or _op.is_empty or _op.geom_type != "Polygon":
                continue
            try:
                _a = _poly.intersection(_op).area
            except _GEOM_EXC:                          # pragma: no cover
                continue
            if _a > 0.25:
                _hits.append((
                    _a, getattr(_o, "role", "") or "-",
                    getattr(_o, "ref", "") or "-",
                    ("pre-emit" if id(_o) in pre_emit_shape_ids
                     else "minted"),
                    ("claimed" if id(_o) in _reg else "unclaimed")))
        if not _hits:
            return "covered by NOTHING in the gate role set"
        _hits.sort(reverse=True)
        return "covered by " + ", ".join(
            f"{_r}/{_f} {_a:.0f}m2 [{_o},{_c}]"
            for _a, _r, _f, _o, _c in _hits[:top])
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        return ""


def _clip_piece_off_protected(shape, protected_union):
    """``shape`` clipped clear of AIRCRAFT-TRANSIT pavement, or ``None``.

    R14-2: a cut never interrupts a runway or taxiway — an aircraft
    cannot detour round a trench, and the only lawful way under one is a
    classified hard-deck object bridge.  A piece MOSTLY over protected
    pavement is covered bore and drops whole (the existing drop law
    already hides that stretch); a graze is clipped back to the pavement
    edge with the usual vertex-bucket clearance.  Altitudes carry by the
    same conversions every other tunnel clip uses; a piece whose profile
    cannot be answered drops rather than shipping a wrong one.
    """
    _poly = getattr(shape, "polygon", None)
    if _poly is None or _poly.is_empty or protected_union is None:
        return shape
    try:
        _ov = _poly.intersection(protected_union).area
    except _GEOM_EXC:
        return shape
    if _ov <= 0.25:
        return shape
    if _ov >= 0.5 * _poly.area:
        return None
    try:
        _cut = _poly.difference(
            protected_union.buffer(_TUNNEL_GRAZE_CLEARANCE_M))
    except _GEOM_EXC:
        return None
    if _cut.geom_type == "MultiPolygon":
        _cut = max(_cut.geoms, key=lambda g: g.area)
    if (_cut.geom_type != "Polygon" or _cut.is_empty or _cut.area < 1.0):
        return None
    if shape.node_altitudes:
        try:
            _ring = list(_poly.exterior.coords)
        except _GEOM_EXC:
            return None
        if _ring and _ring[0] == _ring[-1]:
            _ring = _ring[:-1]
        _res = _resample_node_altitudes_nn(
            _cut, _ring, list(shape.node_altitudes),
            interior_edge_project=True)
        if _res is None:
            return None
        shape.node_altitudes = _res
    elif (shape.altitude_high is not None
            and shape.altitude_low is not None):
        _res = _sloped_rect_clipped_altitudes(
            _poly, shape.altitude_high, shape.altitude_low, _cut)
        if _res is None:
            return None
        shape.altitude_high = None
        shape.altitude_low = None
        shape.node_altitudes = _res
    shape.polygon = _cut
    return shape


def _finalize_tunnel_emission(
        layout: "PavementLayout", exclusion_zones: list,
        boundary_clearance_m: float, airside_gate_union,
        pre_emit_shape_ids: set, n_emitted: int,
        ramp_way_ids: dict | None = None,
        ramp_cut_clearance_m: float = 0.0,
        protected_union=None) -> int:
    """Post-emission coordination: boundary-ribbon subtraction, the
    ruling-4 ramp pavement cut, the under-pavement piece drop, and the
    wall-vs-ramp clip.  Returns the emitted-portal count.

    ``ramp_way_ids`` maps ``id(shape)`` → source OSM way id for the
    pieces each portal cluster emitted; it only names the way in the
    ruling-4 safety-floor log line.

    ``ramp_cut_clearance_m`` is the spec §2 clearance annulus —
    ``wall_gap_m + retaining_wall_width_m``, the perimeter wall band's
    own geometry — see :func:`_tunnel_ramp_pavement_cut`.
    """
    # Boundary coordination: clip every ROLE_BOUNDARY shape so
    # it doesn't overlap the actual tunnel-polygon footprint.
    # The boundary ribbon is built by line-buffering the apt.dat
    # row-130 line, which extends ~2.5 m to either side of the
    # boundary line — so when a tunnel ramp crosses the boundary,
    # the ribbon overlaps both the inside-airport (LOW-end) and
    # outside-airport (HIGH-end) parts of the ramp.  Subtracting
    # the actual ramp+walls union (buffered by 0.5 m for a small
    # visible gap) handles both cases without carving exclusion
    # discs outside the tunnel's footprint — the boundary still
    # traces the rest of the perimeter unchanged.
    if exclusion_zones:
        try:
            tunnel_union = unary_union(exclusion_zones)
        except _GEOM_EXC:
            tunnel_union = None
        if tunnel_union is None or tunnel_union.is_empty:
            return n_emitted
        excl_union = tunnel_union.buffer(boundary_clearance_m)
        kept_shapes: list[BuiltShape] = []
        for s in layout.shapes:
            if s.role != ROLE_BOUNDARY:
                kept_shapes.append(s)
                continue
            # Capture the old ring + altitudes BEFORE the clip so
            # we can NN-resample altitudes for the new ring.  Per
            # user 2026-04-29 (HECA crash investigation): leaving
            # the boundary ribbon with no altitudes after a clip
            # made X-Plane crash on load — the 1066-vertex polygon
            # without elevation guidance was unrenderable.
            try:
                _old_ring = list(s.polygon.exterior.coords)
            except _GEOM_EXC:
                _old_ring = []
            if _old_ring and _old_ring[0] == _old_ring[-1]:
                _old_ring = _old_ring[:-1]
            _old_alts = (list(s.node_altitudes)
                          if s.node_altitudes else None)
            try:
                new_poly = s.polygon.difference(excl_union)
            except _GEOM_EXC:
                kept_shapes.append(s)
                continue
            if new_poly.is_empty:
                continue
            if new_poly.geom_type == "Polygon":
                s.polygon = new_poly
                resampled = _resample_node_altitudes_nn(
                    new_poly, _old_ring, _old_alts)
                if resampled is not None:
                    s.node_altitudes = resampled
                # else: keep existing s.altitude / node_altitudes
                # (possibly mismatched but better than nothing).
                kept_shapes.append(s)
            elif new_poly.geom_type == "MultiPolygon":
                # Split the boundary shape into the resulting pieces.
                for g in new_poly.geoms:
                    if (g.geom_type != "Polygon"
                            or g.is_empty
                            or g.area < 5.0):
                        continue
                    resampled = _resample_node_altitudes_nn(
                        g, _old_ring, _old_alts)
                    kept_shapes.append(BuiltShape(
                        polygon=g,
                        role=s.role,
                        ref=s.ref,
                        altitude=(s.altitude if resampled is None
                                  else None),
                        node_altitudes=resampled))
        layout.shapes = kept_shapes
    # PAVEMENT-OVERLAP CLIP (user 2026-06-12, KPHL): tunnel structure
    # is emitted for REAL under-pavement service roads too (the
    # small_roads ``building_passage`` ways threading the terminal
    # complex) — but a cap/wall/ramp piece may not overlap any
    # pavement shape; the covered stretch has no visible structure.
    # Pieces are short, so dropping the overlapping ones lets the
    # trench dive under a taxiway and re-emerge on the far side.
    if airside_gate_union is not None:
        # COVERED vs GRAZE discriminator (2026-07-10, SPJC big NW
        # crossing): the drop is meant for pieces UNDER pavement (a
        # covered stretch has no visible structure — overlap ≈ the
        # whole piece).  An implied bore crossing pavement OBLIQUELY
        # grazes the pavement corner with the piece nearest its portal
        # (SPJC: ~6 % of the piece area against the shoulder-widened
        # runway edge) — the old absolute 0.25 m² threshold wholesale-
        # dropped exactly the mouth descent and the perimeter wall
        # band, so the tunnel had no visible entrances.  Now: mostly-
        # covered pieces (≥ 50 %) still drop whole; grazes are CLIPPED
        # off the pavement instead, converting sloped rects to
        # node_altitudes (ring-order slope semantics do not survive a
        # clip) and NN-resampling clipped node_altitudes rings.
        #
        # RULING 4 (owner 2026-08-07, OTHH) — "tunnel ramp should win
        # over pavement": ``tunnel_ramp`` pieces are EXEMPT from both the
        # ≥ 50 % drop and the graze clip, and CUT the pavement they
        # surface through instead (the cut, and its safety floor, ran
        # just above).  The drop had beheaded the mapped OTHH portal —
        # every ramp dropped over the service_junction grid, leaving only
        # the 1 m perimeter wall band.  ``tunnel_wall`` bands are then
        # judged against the POST-CUT pavement (a wall follows its ramp:
        # it must not be dropped for overlapping pavement its own ramp
        # has removed); ``tunnel_cap`` behaviour is unchanged.
        _graze_clip = os.environ.get(
            "O4_TUNNEL_GRAZE_CLIP", "1") == "1"
        _post_gate_u = _tunnel_ramp_pavement_cut(
            layout, airside_gate_union, pre_emit_shape_ids, ramp_way_ids,
            clearance_m=ramp_cut_clearance_m)
        # §W1: the CLAIM variant of ruling 4's cut — a claimed corridor
        # never cuts its host, so the walls §2.3 just minted for it are
        # judged against a union that still contains the pavement they
        # are the visible structure of.  Adjudication only; the covered-
        # span mask holds genuinely roofed stretches back.
        _wall_gate_u = _claim_wall_adjudication_gate(
            layout, _post_gate_u, ramp_cut_clearance_m)
        _gate_bufs: dict[int, object] = {}
        _kept9 = []
        _n_clip = 0
        _n_graze = 0
        for _k9, s9 in enumerate(layout.shapes):
            _ref9 = getattr(s9, "ref", "")
            # R10-3: ``tunnel_roof`` joins the drop/graze set.  A roof
            # plate is half a carriageway + wall gap WIDE, so clipping
            # only its bore CENTERLINE against the pavement left the
            # plate overhanging the taxiway it was cover for (measured
            # KCLT: roof over junction 1668).  ``tunnel_mouth`` is road
            # surface (ROLE_TUNNEL_RAMP) and stays ruling-4 exempt with
            # the ramps.
            # RULINGS 2026-08-30i: ``TUNNEL_ROAD_REF`` joins this set.  A
            # terrain deck's footprint severs the tunnel corridor's OWN
            # road surface — claimed and synthetic alike — exactly as it
            # severs the ramp, and the corridor resumes at both deck
            # edges.  ``tunnel_road`` is already in
            # ``_TUNNEL_PAVEMENT_REFS``, so it takes the ruling-4 branch
            # below and is clipped against ``protected_union``, which is
            # where the deck footprint lives (§3/2026-08-30d).  Measured
            # at LEMD round 2 (build ``lemdr2b``): without it the
            # corridor surfaced across stations 12.3-66.9 m of the
            # owner's span at 600.18-601.60 m, under a deck at 604.49 m.
            if not (id(s9) not in pre_emit_shape_ids
                    and _ref9 in ("tunnel_cap", "tunnel_wall",
                                  TUNNEL_WALL_FOOT_REF,
                                  "tunnel_roof", "tunnel_ramp",
                                  "tunnel_mouth", TUNNEL_ROAD_REF)
                    and s9.polygon is not None
                    and not s9.polygon.is_empty):
                _kept9.append(s9)
                continue
            if _ref9 in _TUNNEL_PAVEMENT_REFS:
                # Ruling 4 — emitted whole over the pavement it may cut.
                # R14-2/A-3 carves out the AIRCRAFT-TRANSIT family: a
                # ramp neither cuts a taxiway nor sits on one.  Owner:
                # "nothing may cut a taxiway."  Over protected pavement
                # the stretch is COVERED BORE, so the mostly-covered
                # piece drops and a graze is clipped back to the edge —
                # the same two-way discriminator the cap/wall use.
                if protected_union is not None:
                    _before9 = s9
                    s9 = _clip_piece_off_protected(s9, protected_union)
                    if s9 is None:
                        _n_clip += 1
                        log_tunnel_piece_removal(
                            layout, _before9,
                            "protected-transit-cover (R14-2)",
                            index=_k9)
                        continue
                _kept9.append(s9)
                continue
            _gate9 = (_wall_gate_u
                      if _ref9 in ("tunnel_wall", TUNNEL_WALL_FOOT_REF,
                                   "tunnel_roof")
                      else airside_gate_union)
            if _gate9 is None:          # its pavement is entirely cut
                _kept9.append(s9)
                continue
            try:
                _ov = s9.polygon.intersection(_gate9).area
            except _GEOM_EXC:
                _ov = 0.0
            if _ov <= 0.25:
                _kept9.append(s9)
                continue
            if not _graze_clip or _ov >= 0.5 * s9.polygon.area:
                _n_clip += 1    # covered stretch — no visible structure
                log_tunnel_piece_removal(
                    layout, s9, "covered-stretch drop", index=_k9,
                    coverage=_ov / max(1e-9, s9.polygon.area),
                    verdict=_covering_shapes(layout, s9, pre_emit_shape_ids))
                continue
            # A graze — clip the piece off the pavement (with vertex-
            # bucket clearance) and keep the visible remainder.
            _gate_buf = _gate_bufs.get(id(_gate9))
            if _gate_buf is None:
                try:
                    _gate_buf = _gate9.buffer(
                        _TUNNEL_GRAZE_CLEARANCE_M)
                except _GEOM_EXC:
                    _gate_buf = _gate9
                _gate_bufs[id(_gate9)] = _gate_buf
            try:
                _cutg = s9.polygon.difference(_gate_buf)
            except _GEOM_EXC:
                _n_clip += 1
                log_tunnel_piece_removal(
                    layout, s9, "graze-clip: difference failed",
                    index=_k9,
                    coverage=_ov / max(1e-9, s9.polygon.area))
                continue
            if _cutg.geom_type == "MultiPolygon":
                _cutg = max(_cutg.geoms, key=lambda g: g.area)
            if (_cutg.geom_type != "Polygon" or _cutg.is_empty
                    or _cutg.area < 1.0):
                _n_clip += 1
                log_tunnel_piece_removal(
                    layout, s9, "graze-clip: nothing visible left",
                    index=_k9,
                    coverage=_ov / max(1e-9, s9.polygon.area))
                continue
            if s9.node_altitudes:
                try:
                    _oring = list(s9.polygon.exterior.coords)
                except _GEOM_EXC:
                    _oring = []
                if _oring and _oring[0] == _oring[-1]:
                    _oring = _oring[:-1]
                _res = _resample_node_altitudes_nn(
                    _cutg, _oring, list(s9.node_altitudes),
                    interior_edge_project=True)
                if _res is None:
                    _n_clip += 1
                    log_tunnel_piece_removal(
                        layout, s9,
                        "graze-clip: profile unanswerable", index=_k9,
                        coverage=_ov / max(1e-9, s9.polygon.area))
                    continue
                s9.node_altitudes = _res
            elif (s9.altitude_high is not None
                    and s9.altitude_low is not None):
                _res = _sloped_rect_clipped_altitudes(
                    s9.polygon, s9.altitude_high, s9.altitude_low,
                    _cutg)
                if _res is None:
                    _n_clip += 1
                    log_tunnel_piece_removal(
                        layout, s9,
                        "graze-clip: sloped profile unanswerable",
                        index=_k9,
                        coverage=_ov / max(1e-9, s9.polygon.area))
                    continue
                s9.altitude_high = None
                s9.altitude_low = None
                s9.node_altitudes = _res
            # (flat ``altitude`` pieces keep their altitude verbatim)
            log_tunnel_piece_removal(
                layout, s9, "graze-clip: kept the visible remainder",
                index=_k9, coverage=_ov / max(1e-9, s9.polygon.area))
            s9.polygon = _cutg
            _n_graze += 1
            _kept9.append(s9)
        if _n_clip or _n_graze:
            layout.shapes = _kept9
            try:
                UI.vprint(1,
                    f"  [pav-builder] dropped {_n_clip} tunnel "
                    f"piece(s) under pavement (covered stretch — no "
                    f"visible structure)"
                    + (f"; graze-clipped {_n_graze} portal piece(s) "
                       f"off the pavement edge." if _n_graze
                       else "."))
            except _GEOM_EXC:
                pass
    # WALL-vs-RAMP CLIP (user 2026-06-12, LMML): a retaining wall / cap
    # is flat at apt_elev and must never sit ON TOP of a tunnel ROAD
    # ramp surface.  Where two portal walks of one tunnel reach past
    # each other (LMML east cluster), one portal's walls land on the
    # other portal's ramps — walls entirely covered (#1327: 33 m² wall,
    # 32.7 m² on a ramp).  The per-cluster wall-opening clip above only
    # sees its OWN cluster's ramps; clip every emitted wall/cap against
    # the union of ALL emitted ramps.  The 0.6 m ``wall_gap_m`` keeps a
    # wall clear of its OWN ramp, so only cross-walk coverage is removed.
    # A4 (lead ruling 2026-08-11): this pass carries the SAME R10-2 law
    # as the per-append cut — it is the only one that sees cross-cluster
    # ordering, where a later cluster's ramp lands on an earlier
    # cluster's wall.  Four corrections against the version that let
    # 2003.9 m² of wall sit on KCLT's ramps: ``tunnel_roof`` is cut too;
    # ``tunnel_mouth`` is IN the cutting union (it is road surface); ALL
    # surviving pieces ≥ 0.5 m² are kept instead of the largest; and the
    # 0.25 m² overlap-ignore is gone — the law is zero, not nearly zero.
    _ramp_polys = [s9.polygon for s9 in layout.shapes
                   if id(s9) not in pre_emit_shape_ids
                   and getattr(s9, "ref", "") in _TUNNEL_PAVEMENT_REFS
                   and s9.polygon is not None
                   and not s9.polygon.is_empty]
    if _ramp_polys:
        try:
            _ramp_u = unary_union(_ramp_polys)
        except _GEOM_EXC:
            _ramp_u = None
        if _ramp_u is not None and not _ramp_u.is_empty:
            _keptW = []
            _n_wclip = 0
            _n_wsplit = 0
            for s9 in layout.shapes:
                if (id(s9) not in pre_emit_shape_ids
                        and getattr(s9, "ref", "") in _TUNNEL_COVER_REFS
                        and s9.polygon is not None
                        and not s9.polygon.is_empty):
                    try:
                        if s9.polygon.intersects(_ramp_u):
                            _pieces = _tunnel_cover_pieces(s9, _ramp_u)
                            if not _pieces:
                                _n_wclip += 1
                                log_tunnel_piece_removal(
                                    layout, s9,
                                    "wall/roof/cap over tunnel pavement")
                                continue
                            _head = _pieces[0]
                            s9.polygon = _head.polygon
                            s9.altitude = _head.altitude
                            s9.altitude_high = _head.altitude_high
                            s9.altitude_low = _head.altitude_low
                            s9.node_altitudes = _head.node_altitudes
                            _n_wclip += 1
                            for _extra in _pieces[1:]:
                                _keptW.append(_extra)
                                _n_wsplit += 1
                    except _GEOM_EXC:
                        pass
                _keptW.append(s9)
            if _n_wclip:
                layout.shapes = _keptW
                try:
                    UI.vprint(1,
                        f"  [pav-builder] clipped {_n_wclip} tunnel "
                        f"wall/roof/cap piece(s) off overlapping tunnel "
                        f"pavement"
                        + (f" (kept {_n_wsplit} extra arc(s) the "
                           f"largest-piece rule used to delete)."
                           if _n_wsplit else "."))
                except _GEOM_EXC:
                    pass
    _record_tunnel_mouth_walling(layout, pre_emit_shape_ids,
                                 airside_gate_union)
    return n_emitted


def _record_tunnel_mouth_walling(layout: "PavementLayout",
                                 pre_emit_shape_ids: set,
                                 airside_gate_union) -> None:
    """R10-2 build check: every below-grade mouth is WALLED.

    Reports, never fails — a mouth left open is a defect to attribute,
    not a reason to abandon a build.  A mouth edge is answered by a
    wall/roof/cap piece, by abutting pavement (the covered stretch), or
    by another tunnel-pavement piece continuing the road.  The residual
    is the mouth's uncovered edge LENGTH, which is what a reviewer flies
    to; a counted finding rides on the layout beside
    ``tunnel_passthrough_findings``.
    """
    # §T2.3: THE LIGHT-TOUCH EXEMPTION IS WITHDRAWN.  A7(c) exempted
    # DEM-cut mouths because the mode emits no side walls by design —
    # but "by design" is a claim about the emitter, not a measurement of
    # the mesh, and it made the one class of mouth this round found
    # unwalled the one class the finding could not see.  The finding
    # reports them like any mouth; it reports and never fails.
    _light_touch = (
        () if _demcut_provenance_gate_on()
        else (getattr(layout, "_tunnel_light_touch_mouths", None) or ()))
    _mouths = [s for s in layout.shapes
               if id(s) not in pre_emit_shape_ids
               and id(s) not in _light_touch
               and getattr(s, "ref", "") == "tunnel_mouth"
               and s.polygon is not None and not s.polygon.is_empty]
    # §T6.3: THE FINDING SEES CLAIMED CORRIDORS TOO.  A claimed corridor
    # is bore geometry (§2.3) and its open edge is the same defect a
    # mouth's is — the owner's ground read of an unwalled claimed ring
    # (RULINGS 2026-08-28c item 3) was invisible here because the
    # population was ``ref == "tunnel_mouth"`` alone.
    #
    # WHICH claimed corridors count is not re-derived: it is the register
    # ``_wall_claimed_corridors`` published when it decided what to wall
    # (below grade against the surface it sits in).  Two answers to "is
    # this claimed surface bore geometry" is the two-instruments trap.
    _bore_claims = getattr(layout, _CLAIMED_BORE_REGISTER, None) or set()
    for _s in layout.shapes:
        if (id(_s) in _bore_claims and _s.polygon is not None
                and not _s.polygon.is_empty):
            _mouths.append(_s)
    if not _mouths:
        return
    _cover = [s.polygon for s in layout.shapes
              if getattr(s, "ref", "") in _TUNNEL_COVER_REFS
              and s.polygon is not None and not s.polygon.is_empty]
    _findings: list = []
    for _mouth in _mouths:
        _answers = list(_cover)
        if airside_gate_union is not None:
            _answers.append(airside_gate_union)
        for _other in layout.shapes:
            if (_other is _mouth
                    or getattr(_other, "ref", "") not in
                    _TUNNEL_PAVEMENT_REFS
                    or _other.polygon is None
                    or _other.polygon.is_empty):
                continue
            _answers.append(_other.polygon)
        try:
            _ring = _mouth.polygon.exterior
            _total = _ring.length
            _u = unary_union(_answers).buffer(
                _TUNNEL_GRAZE_CLEARANCE_M + 0.1) if _answers else None
            _open = (_total if _u is None
                     else _ring.difference(_u).length)
        except _GEOM_EXC:
            continue
        if _open <= 0.5:
            continue
        _findings.append({
            "ref": _mouth.ref,
            "altitude": _mouth.altitude,
            "perimeter_m": round(_total, 1),
            "uncovered_m": round(_open, 1),
        })
    if not _findings:
        return
    try:
        existing = list(getattr(layout, "tunnel_unwalled_mouth", None)
                        or [])
        existing.extend(_findings)
        layout.tunnel_unwalled_mouth = existing
    except (AttributeError, TypeError):
        return
    try:
        UI.vprint(1,
            f"  [pav-builder] R10-2: {len(_findings)} tunnel mouth(s) "
            f"with an UNWALLED edge (worst "
            f"{max(f['uncovered_m'] for f in _findings):.1f} m of "
            f"perimeter answered by neither wall, cap nor pavement).")
    except _GEOM_EXC:
        pass


#: R14-1/A-1 — the road-family roles a tunnel system may CLAIM.  Exactly
#: the R5 ``TRANSITION_ROLES`` road members: these are the surfaces the
#: transition law already re-profiles post-solve, so claiming them is that
#: same precedent carried one step further (a LEVEL plate rather than a
#: graded one), not a new authority.  Airside is absent on purpose.
_TUNNEL_CLAIMABLE_ROAD_ROLES = frozenset({
    ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION, ROLE_GROUNDSIDE_PAVEMENT,
})
#: A claimed shape must actually COVER the alignment, not graze it.
_TUNNEL_CLAIM_MIN_OVERLAP_M2 = 2.0
#: A shape covering at least this FRACTION of its own area with the
#: between-portals seed is part of the LEVEL surface, not an approach.
_TUNNEL_CLAIM_LEVEL_AREA_FRAC = 0.25


def _tunnel_open_cut_regions(portal_data: list, facing_pairs: list,
                             wall_gap_m: float) -> list:
    """``[(level_zone, approach_zone, floor_elev)]`` — a tunnel system's
    OPEN-CUT EXTENT, one record per portal and per facing pair.

    ``level_zone`` is the ground the bore holds at ONE level: the mouth
    plate at each portal, and the whole roadway between two facing
    portals (the owner's "the whole triangular intersection and both
    portal areas are ONE level surface at bore depth").  ``approach_zone``
    is the R14-3 run outward from the mouth, where the surface climbs
    back to ambient.  Both are plan-space only — the elevations live in
    ``floor_elev`` and the R14-3 grade.
    """
    _regions: list = []

    def _quad(p_a, p_b, half_w):
        _dx, _dy = p_b[0] - p_a[0], p_b[1] - p_a[1]
        _len = math.hypot(_dx, _dy)
        if _len < 1e-6 or half_w <= 0.0:
            return None
        _px, _py = -_dy / _len, _dx / _len
        try:
            _q = Polygon([
                (p_a[0] + _px * half_w, p_a[1] + _py * half_w),
                (p_b[0] + _px * half_w, p_b[1] + _py * half_w),
                (p_b[0] - _px * half_w, p_b[1] - _py * half_w),
                (p_a[0] - _px * half_w, p_a[1] - _py * half_w),
            ])
            if not _q.is_valid:
                _q = _q.buffer(0)
            return _q if _q.geom_type == "Polygon" and not _q.is_empty else None
        except _GEOM_EXC:
            return None

    _paired: set = set()
    for (i, j) in facing_pairs:
        _paired.add(i)
        _paired.add(j)
        _a, _b = portal_data[i], portal_data[j]
        _half = 0.5 * max(float(_a[7]), float(_b[7])) + wall_gap_m
        _level = _quad(_a[2][0], _b[2][0], _half)
        if _level is None:
            continue
        _ga = _mouth_grade_with_clearance(_a[9], _a[11] if len(_a) > 11 else None)
        _gb = _mouth_grade_with_clearance(_b[9], _b[11] if len(_b) > 11 else None)
        if _ga is None or _gb is None:
            continue
        _floor = min(float(_ga), float(_gb))
        for _pd in (_a, _b):
            _app = _approach_zone(_pd, wall_gap_m)
            _regions.append((_level, _app, _floor))
    for k, _pd in enumerate(portal_data):
        if k in _paired:
            continue
        _grade = _mouth_grade_with_clearance(
            _pd[9], _pd[11] if len(_pd) > 11 else None)
        if _grade is None or len(_pd[2]) < 2:
            continue
        _walk = _pd[2]
        _dx, _dy = _walk[1][0] - _walk[0][0], _walk[1][1] - _walk[0][1]
        _dl = math.hypot(_dx, _dy) or 1.0
        _out = (_dx / _dl, _dy / _dl)
        _mouth_end = (_walk[0][0] + _out[0] * TUNNEL_MOUTH_PLATE_LENGTH_M,
                      _walk[0][1] + _out[1] * TUNNEL_MOUTH_PLATE_LENGTH_M)
        _level = _quad(_walk[0], _mouth_end,
                       0.5 * float(_pd[7]) + wall_gap_m)
        if _level is None:
            continue
        _regions.append((_level, _approach_zone(_pd, wall_gap_m),
                         float(_grade)))
    return _regions


def _approach_zone(portal_row, wall_gap_m: float):
    """The R14-3 run's plan footprint: the (already run-limited) walk
    widened to the carriageway.  ``None`` when the walk cannot buffer."""
    _walk = portal_row[2]
    if len(_walk) < 2:
        return None
    try:
        return LineString(_walk).buffer(
            0.5 * float(portal_row[7]) + wall_gap_m, cap_style=2)
    except _GEOM_EXC:
        return None


def _airside_conflict_finding(layout: "PavementLayout", shape, poly,
                              role: str, level_m: float) -> dict:
    """One ``tunnel_airside_conflict`` record — WITH ITS JOIN KEY.

    Folded-in finding, KCLT adjudication 2026-08-11 §4: the record named
    a role, an area and a level and NO PLACE, so saying WHICH shape it
    meant took a geometric re-derivation off an emitted patch — ``ref``
    is empty on most of these and the emitted ``shapeID`` does not
    survive a rebuild, while the classify instrument's rows carry
    lat/lon.  The centroid joins the two directly and is the coordinate
    the owner flies to.

    Frame: ``_local_meter_projections`` — the module's own shared
    equirectangular projection, the one every sibling finding here
    records (see the tunnel-passthrough findings' lat/lon/x_m/y_m).
    """
    finding = {
        "role": role, "ref": getattr(shape, "ref", ""),
        "area_m2": round(poly.area, 1),
        "level_it_would_need_m": round(float(level_m), 2),
    }
    try:
        centroid = poly.centroid
        _, meters_to_lat_lon = _local_meter_projections(layout.anchor)
        lat, lon = meters_to_lat_lon(centroid.x, centroid.y)
        finding["lat"] = round(lat, 7)
        finding["lon"] = round(lon, 7)
        finding["x_m"] = round(centroid.x, 1)
        finding["y_m"] = round(centroid.y, 1)
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        pass
    return finding


def _claim_road_pavement(layout: "PavementLayout", portal_data: list,
                         facing_pairs: list, wall_gap_m: float) -> tuple:
    """R14-1/A-1: THE PAVED AREA IS THE CORRIDOR.

    Where mapped road pavement covers a tunnel system's open-cut extent,
    that pavement IS the tunnel surface: it is re-profiled in place —
    bore-depth LEVEL across the mouths and the roadway between two facing
    portals, then climbing at ``TUNNEL_APPROACH_GRADE`` back to whatever
    the solver gave it — instead of a synthetic rectangle being emitted
    beside it.  A synthetic corridor next to at-grade road pavement is a
    CLIFF (measured KCLT: an 8.31 m step across the 0.6 m graze
    standoff), and that cliff is the defect class this law removes.

    The claim never RAISES a vertex: each one takes the lower of its
    solved value and the tunnel profile, so the claim can only dig, and
    it dies out on its own where the profile climbs back through the
    surrounding surface.

    AIRSIDE IS KING: an apron or any aircraft-transit shape inside the
    extent is never claimed and never sunk.  It mints a counted
    ``tunnel_airside_conflict`` finding instead — at KCLT that is almost
    certainly road pavement the scorer mis-roled, and that verdict
    belongs to the classify instrument, not to this emitter.

    Returns ``(n_claimed, claimed_polygons)``.
    """
    from .elevation import _resample_node_altitudes_nn
    from .groundside import _ring_and_altitudes
    _regions = _tunnel_open_cut_regions(
        portal_data, facing_pairs, wall_gap_m)
    if not _regions:
        return 0, []
    # ── §3 THIRD CLAUSE (RULINGS 2026-08-30f) ───────────────────────
    # "The claim resumes at both deck edges, exactly as the open cut
    # does."  So the deck is taken out of the claim's FOOTPRINT, not
    # vetoed shape by shape: the claim's hosts are large rings that
    # CONTAIN the deck strip (measured at LEMD round 2 — the hosts read
    # 4 % and 48 % inside the deck corridor, so a "mostly inside" veto
    # cannot see them, and the claim then cut them into pieces that were
    # 96-99 % deck and graded them 601.43 -> 600.18 m).  Subtracting the
    # deck from the region geometry makes the claim stop at one deck
    # edge and resume at the other, which is what the ruling says, and
    # it fixes the published open cut in the same stroke.
    try:
        from .road_bridge_deck import terrain_deck_union as _tdu
        _deck_keep_out = _tdu(layout)
    except Exception:                                    # pragma: no cover
        _deck_keep_out = None
    if _deck_keep_out is not None:
        _trimmed: list = []
        _n_trim = 0
        for _l, _a, _f in _regions:
            _parts = []
            for _z in (_l, _a):
                if _z is None or _z.is_empty:
                    _parts.append(_z)
                    continue
                try:
                    _d = _z.difference(_deck_keep_out)
                except _GEOM_EXC:                        # pragma: no cover
                    _parts.append(_z)
                    continue
                if _d.is_empty:
                    _parts.append(None)
                    _n_trim += 1
                else:
                    if _d.area < _z.area - 1e-9:
                        _n_trim += 1
                    _parts.append(_d)
            _trimmed.append((_parts[0], _parts[1], _f))
        _regions = _trimmed
        if _n_trim:
            UI.vprint(1,
                f"  [bridge-deck] §3 third clause: {_n_trim} open-cut "
                f"region part(s) trimmed at a road bridge deck — the "
                f"tunnel-road claim does not reach the deck and resumes "
                f"at both of its edges.")
    # THE OPEN CUT ITSELF is published here — beside the claim, from the
    # SAME records this function is about to judge every shape against
    # (spec ``tunnel-corridor-node-book-exclusion-spec.md`` AMENDMENT 5).
    # The claim set names the road surfaces the cut CAPTURED; the cut
    # names the ground the bore actually occupies, and the two are not
    # the same region — OTHH's bore floor is a groundside ring BESIDE
    # the claimed roads (0-2 of its 33 nodes in-claim, measured).  One
    # authority either way: nothing downstream re-derives a cut zone.
    publish_tunnel_open_cut_regions(layout, _regions)

    from .road_bridge_deck import is_deck_shape as _is_deck_claim

    def _claimable(shape):
        _poly = getattr(shape, "polygon", None)
        if _poly is None or _poly.is_empty or _poly.geom_type != "Polygon":
            return None
        # ── §3 THIRD CLAUSE (RULINGS 2026-08-30f) ───────────────────
        # "A ROAD BRIDGE DECK is not claimable road pavement either:
        # R14-1's tunnel-road claim does not reach a confirmed terrain
        # deck.  The deck's ground is the road ABOVE the corridor, not
        # the corridor, and re-profiling it toward bore depth is the
        # canyon the deck exists to remove.  The claim resumes at both
        # deck edges, exactly as the open cut does."
        #
        # MEASURED at LEMD (round 1, build lemddeck4): the claim took the
        # deck and graded it 601.67 -> 600.2 m eastward across the span,
        # which met the 601.36-606.6 m east receiver as a 5.13 m step at
        # 17.4 % and minted 220 groundside within_shape rows.
        if _is_deck_claim(shape, layout):
            return None
        return _poly

    _airside: list = []
    _shapes = [s for s in (getattr(layout, "shapes", ()) or ())]
    # ── PASS 1: THE LEVEL SURFACE ────────────────────────────────────
    # The carriageway quad between two facing portals is only a SEED.
    # The owner's law is about the whole INTERSECTION — "the whole
    # triangular intersection and both portal areas are ONE level
    # surface at bore depth" — so a road shape that substantially
    # covers the seed is levelled WHOLE, and the intersection comes out
    # one surface however its junction plates happen to be cut.  A shape
    # that merely clips the seed is left to pass 2, where it grades:
    # levelling it whole would sink pavement the bore never runs under.
    _level_members: list = []          # (shape, ring, alts, floor)
    _claimed_ids: set = set()
    for _shape in _shapes:
        _poly = _claimable(_shape)
        if _poly is None:
            continue
        _role = getattr(_shape, "role", "")
        _best = None
        for _level, _app, _floor in _regions:
            if _level is None:
                continue
            try:
                _ov = _poly.intersection(_level).area
            except _GEOM_EXC:
                continue
            if _ov < _TUNNEL_CLAIM_MIN_OVERLAP_M2:
                continue
            if _ov < _TUNNEL_CLAIM_LEVEL_AREA_FRAC * _poly.area:
                continue
            if _best is None or _floor < _best:
                _best = float(_floor)
        if _best is None:
            continue
        if _role not in _TUNNEL_CLAIMABLE_ROAD_ROLES:
            if _role in _TUNNEL_PROTECTED_TRANSIT_ROLES or _role == ROLE_APRON:
                _airside.append(_airside_conflict_finding(
                    layout, _shape, _poly, _role, _best))
            continue
        _ring, _alts = _ring_and_altitudes(_shape)
        if _ring is None or not _alts:
            continue
        _level_members.append((_shape, _ring, _alts, _best))
        _claimed_ids.add(id(_shape))
    # The LEVEL SURFACE those members now form: pass 2 grades away from
    # this, not from the seed, so an approach starts climbing at the real
    # edge of the level pavement.
    _level_parts = [_l for _l, _a, _f in _regions if _l is not None]
    _level_parts.extend(_s.polygon for _s, _r, _a, _f in _level_members)
    try:
        _level_surface = unary_union(_level_parts) if _level_parts else None
    except _GEOM_EXC:
        _level_surface = None
    # ── R16-3: ONE FLOOR PER CONNECTED CLAIMED PLATE ─────────────────
    # Two ADJACENT plates of one level surface used to carry different
    # clearance floors — each shape took the lowest floor among the
    # REGIONS it covers, and two members covering different regions
    # answered differently (measured KCLT triangle: 210.87 vs 210.98, a
    # 0.13 m spread against the level-plate bullet's 0.10 m).  A level
    # surface is ONE surface: connected members share the JOINT DEPTH,
    # the minimum of their own floors.  Connectivity is the claim law's
    # OWN — the components of ``_level_surface``, the union pass 2
    # already grades away from — never a private union built here.
    _joint_floor: dict[int, float] = {}
    if _level_members and _level_surface is not None:
        _bodies = [_g for _g in getattr(_level_surface, "geoms",
                                        [_level_surface])
                   if _g is not None and not _g.is_empty]
        if len(_bodies) > 1:
            try:
                from shapely.strtree import STRtree as _STRtree
                _body_tree = _STRtree(_bodies)
            except Exception:                          # pragma: no cover
                _body_tree = None
        else:
            _body_tree = None
        _component_of: dict[int, int] = {}
        for _shape, _r, _a, _floor in _level_members:
            _comp = 0
            if _body_tree is not None:
                try:
                    _pt = _shape.polygon.representative_point()
                    _hit = _body_tree.query(_pt)
                    _comp = id(_shape)
                    for _hi in _hit:                   # bbox hits: the
                        # body that really covers the plate decides
                        if _bodies[int(_hi)].intersects(_pt):
                            _comp = int(_hi)
                            break
                    else:
                        if len(_hit):
                            _comp = int(_hit[0])
                except _GEOM_EXC:                      # pragma: no cover
                    _comp = id(_shape)
            _component_of[id(_shape)] = _comp
            _cur = _joint_floor.get(_comp)
            if _cur is None or float(_floor) < _cur:
                _joint_floor[_comp] = float(_floor)
        _level_members = [
            (_shape, _r, _a,
             _joint_floor.get(_component_of[id(_shape)], _floor))
            for _shape, _r, _a, _floor in _level_members]
        _spread = [(_joint_floor[_c], _c) for _c in _joint_floor]
        if len(_spread) < len(_level_members):
            try:
                UI.vprint(1,
                    f"  [pav-builder] R16-3: {len(_level_members)} "
                    f"claimed plate(s) resolved to {len(_joint_floor)} "
                    f"connected level surface(s) — each plate takes its "
                    f"surface's JOINT DEPTH "
                    f"({', '.join(f'{_f:.2f}' for _f, _c in sorted(_spread))}"
                    f" m), so adjacent plates cannot carry different "
                    f"clearance floors.")
            except _GEOM_EXC:
                pass

    _claimed_polys: list = []
    #: ``(polygon, ring, altitudes)`` per claimed surface — the depth the
    #: claim gave it, which AMENDMENT 1's stand-down needs per footprint.
    _claimed_depth: list = []
    _n = 0
    for _shape, _ring, _alts, _floor in _level_members:
        _new = [round(min(float(_alts[_v]), _floor), 2)
                for _v in range(len(_ring))]
        if max(abs(_new[_v] - float(_alts[_v]))
               for _v in range(len(_ring))) < 0.01:
            continue
        _shape.node_altitudes = list(_new) + [_new[0]]
        _shape.altitude = None
        _shape.altitude_high = None
        _shape.altitude_low = None
        _shape.ref = TUNNEL_ROAD_REF
        _claimed_polys.append(_shape.polygon)
        # THE DEPTH THE CLAIM ACTUALLY GAVE THIS SURFACE, kept with its
        # ring so the stand-down can ask "does this claimant carry bore
        # depth HERE" per footprint (spec AMENDMENT 1).
        _claimed_depth.append((_shape.polygon, list(_ring), list(_new)))
        _stash_tunnel_claim_depth(_shape, _new)
        log_tunnel_road_claim(layout, _shape, _new, "levelled")
        _n += 1
    # ── PASS 2: THE GRADED APPROACHES ────────────────────────────────
    # §T6.2 / portal-corridor-claim §2.2: this pass RIDES THE CORRIDOR
    # FOOTPRINT.  Its whole-shape form relabelled OTHH -12168 — a
    # 19,461 m² landside ring — ``tunnel_road`` because an 8 m corridor
    # grazed one end, and its far tongues then reached into the covered
    # bore interior at z=1.90.  The host is CUT: it keeps its role, its
    # ref, its law and the rest of its area; only the strip is claimed.
    # A surface that IS the corridor (nothing survives the cut) is still
    # claimed whole — that is the case the whole-shape form is right for,
    # and ``_split_host_at_corridor`` returns ``None`` to say so.
    try:
        _cut_parts_p2 = [_z for _l, _a, _f in _regions
                         for _z in (_l, _a)
                         if _z is not None and not _z.is_empty]
        _cut_u_p2 = unary_union(_cut_parts_p2) if _cut_parts_p2 else None
    except _GEOM_EXC:                                  # pragma: no cover
        _cut_u_p2 = None
    _p2_minted: list = []
    _n_scoped = 0
    for _shape in _shapes:
        if id(_shape) in _claimed_ids:
            continue
        _poly = _claimable(_shape)
        if _poly is None:
            continue
        _role = getattr(_shape, "role", "")
        _hits = []
        for _level, _app, _floor in _regions:
            _zone = [_z for _z in (_level, _app) if _z is not None]
            if not _zone:
                continue
            try:
                _ov = max(_poly.intersection(_z).area for _z in _zone)
            except _GEOM_EXC:
                continue
            if _ov >= _TUNNEL_CLAIM_MIN_OVERLAP_M2:
                _hits.append((_level, float(_floor)))
        if not _hits:
            continue
        if _role not in _TUNNEL_CLAIMABLE_ROAD_ROLES:
            if _role in _TUNNEL_PROTECTED_TRANSIT_ROLES or _role == ROLE_APRON:
                _airside.append(_airside_conflict_finding(
                    layout, _shape, _poly, _role,
                    min(_f for _l, _f in _hits)))
            continue
        _ring, _alts = _ring_and_altitudes(_shape)
        if _ring is None or not _alts:
            continue

        def _p2_profile(_pt, _hits=_hits):
            """The approach profile at a point: the lowest any hit region
            offers.  ONE arithmetic for the whole pass, whether the
            claim takes the shape or only its strip."""
            _best = None
            for _level, _floor in _hits:
                _from = (_level_surface if _level_surface is not None
                         else _level)
                if _from is None:
                    continue
                try:
                    _d = _from.distance(_pt)
                except _GEOM_EXC:
                    continue
                _p = _floor + TUNNEL_APPROACH_GRADE * _d
                if _best is None or _p < _best:
                    _best = _p
            return _best

        _split = (_split_host_at_corridor(_poly, _cut_u_p2, _role)
                  if claim_footprint_scope_enabled() else None)
        if _split is not None:
            # ── THE SCOPED CLAIM: strip in, host out ─────────────────
            _strip_parts, _rest_parts = _split
            _open_ring = (_ring[:-1] if (_ring and _ring[0] == _ring[-1])
                          else _ring)
            _new_strips: list = []
            for _sp in _strip_parts:
                _sa = _resample_node_altitudes_nn(
                    _sp, _open_ring, list(_alts),
                    interior_edge_project=True)
                if _sa is None:
                    continue
                try:
                    _coords = list(_sp.exterior.coords)
                except _GEOM_EXC:                      # pragma: no cover
                    continue
                _lowered, _dug = [], 0.0
                for _v, _xy in enumerate(_coords):
                    _own = float(_sa[min(_v, len(_sa) - 1)])
                    _p = _p2_profile(Point(_xy))
                    _val = _own if _p is None else min(_own, _p)
                    _dug = max(_dug, _own - _val)
                    _lowered.append(round(_val, 2))
                if _dug < 0.01:
                    continue
                _new_strips.append((_sp, _coords, _lowered, _sa))
            if not _new_strips:
                continue
            _host_alts = _resample_node_altitudes_nn(
                _rest_parts[0], _open_ring, list(_alts),
                interior_edge_project=True)
            if _host_alts is None:
                continue
            for _extra in _rest_parts[1:]:
                _ea = _resample_node_altitudes_nn(
                    _extra, _open_ring, list(_alts),
                    interior_edge_project=True)
                if _ea is None:
                    continue
                # THE HOST'S PROVENANCE RIDES ITS REMAINDER: a
                # synthesised corridor cut in two is still synthesis on
                # both sides, and §T7's mask must still be able to see
                # it (the flag is the discriminator, not the role).
                _p2_minted.append(BuiltShape(
                    polygon=_extra, role=_role,
                    ref=getattr(_shape, "ref", ""), node_altitudes=_ea,
                    synthesised_road_corridor=getattr(
                        _shape, "synthesised_road_corridor", False)))
            _shape.polygon = _rest_parts[0]
            _shape.node_altitudes = _host_alts
            _shape.altitude = None
            _shape.altitude_high = None
            _shape.altitude_low = None
            for _sp, _coords, _lowered, _sa in _new_strips:
                _claim = BuiltShape(
                    polygon=_sp, role=_role, ref=TUNNEL_ROAD_REF,
                    node_altitudes=list(_lowered))
                _p2_minted.append(_claim)
                _claimed_polys.append(_sp)
                _claimed_depth.append(
                    (_sp, list(_coords), list(_lowered)))
                _stash_tunnel_claim_depth(_claim, _lowered)
                log_tunnel_road_claim(layout, _claim, _lowered,
                                      "graded (corridor footprint)")
                _n += 1
            _n_scoped += 1
            continue

        # ── THE WHOLE-SHAPE CLAIM ────────────────────────────────────
        # THE CORRIDOR IS ONE SURFACE (canonical-mouth law).  For a host
        # that IS the corridor the claim takes the shape whole — but the
        # whole-shape claim re-profiles the ring's OWN vertices, and a
        # mapped road bends where the ROAD bends, not where the open cut
        # begins.  Insert the cut's vertices first, so the claimed
        # surface descends AT the mouth line instead of at the nearest
        # road bend.  Committed only if the claim then actually digs.
        _dens_poly = _dens_ring = _dens_alts = None
        if _role in _CORRIDOR_OWN_ROAD_ROLES and _cut_u_p2 is not None:
            _dens_poly = _densify_ring_at_corridor(_poly, _cut_u_p2)
            if _dens_poly is not None:
                _da = _resample_node_altitudes_nn(
                    _dens_poly, list(_ring), list(_alts),
                    interior_edge_project=True)
                _dr = list(_dens_poly.exterior.coords)
                if _dr and _dr[0] == _dr[-1]:
                    _dr = _dr[:-1]
                if _da is None or len(_da) < len(_dr):
                    _dens_poly = None
                else:
                    _dens_ring = _dr
                    _dens_alts = [float(_a) for _a in _da[:len(_dr)]]
        if _dens_poly is not None:
            _ring, _alts = _dens_ring, _dens_alts
        _new = list(_alts)
        _moved = 0.0
        for _v in range(len(_ring)):
            _best = _p2_profile(Point(_ring[_v]))
            if _best is None:
                continue
            _value = min(float(_alts[_v]), _best)
            _moved = max(_moved, abs(_value - float(_alts[_v])))
            _new[_v] = round(_value, 2)
        if _moved < 0.01:
            continue
        if _dens_poly is not None:
            _shape.polygon = _dens_poly
        _shape.node_altitudes = list(_new) + [_new[0]]
        _shape.altitude = None
        _shape.altitude_high = None
        _shape.altitude_low = None
        _shape.ref = TUNNEL_ROAD_REF
        _claimed_polys.append(_shape.polygon)
        _claimed_depth.append((_shape.polygon, list(_ring), list(_new)))
        _stash_tunnel_claim_depth(_shape, _new)
        log_tunnel_road_claim(layout, _shape, _new, "graded")
        _n += 1
    if _p2_minted:
        layout.shapes.extend(_p2_minted)
        try:
            UI.vprint(1,
                f"  [pav-builder] §2.2 claim scope: {_n_scoped} host "
                f"surface(s) CUT at the corridor footprint instead of "
                f"claimed whole — each keeps its role, its ref and the "
                f"rest of its area (OTHH -12168 class).")
        except _GEOM_EXC:                              # pragma: no cover
            pass
    if _airside:
        try:
            _existing = list(
                getattr(layout, "tunnel_airside_conflict", None) or [])
            _existing.extend(_airside)
            layout.tunnel_airside_conflict = _existing
        except (AttributeError, TypeError):
            pass
        try:
            _at = ", ".join(
                f"{_a['role']} {_a['area_m2']:.0f} m² at "
                f"{_a['lat']:.6f},{_a['lon']:.6f}"
                for _a in _airside if "lat" in _a)
            UI.vprint(1,
                f"  [pav-builder] R14-1: {len(_airside)} AIRSIDE shape(s) "
                f"lie inside a tunnel open cut and were NOT claimed "
                f"(airside is king) — likely road pavement the scorer "
                f"mis-roled; adjudicate with the classify instrument"
                f"{' — ' + _at if _at else ''}.")
        except _GEOM_EXC:
            pass
    if _n:
        try:
            UI.vprint(1,
                f"  [pav-builder] R14-1: claimed {_n} road surface(s) as "
                f"the tunnel corridor ({len(_level_members)} levelled at "
                f"bore depth, the rest graded out at the "
                f"{TUNNEL_APPROACH_GRADE:.0%} cap) — the paved area IS "
                f"the corridor, so no synthetic rectangle stands beside "
                f"it.")
        except _GEOM_EXC:
            pass
    # ── THE CORRIDOR FOOTPRINT OF THE CLAIM (mouth-D fix, RULINGS
    # 2026-08-25e) ───────────────────────────────────────────────────
    # ``_claimed_polys`` are WHOLE SHAPES: a claimed road is re-profiled
    # in place, and the list its consumers get is the shape's own
    # polygon.  For the node book (which asks "is this ring the bore's
    # own geometry") that is the right list and it stays untouched.
    #
    # For the STAND-DOWN it is not, and the cost is measured: OTHH mouth
    # D's four ramp pieces were deleted at share=1.000 by ONE claimant of
    # 19,461.6 m² with a 1,525 m perimeter, whose centroid lies 147-258 m
    # away — a long service lot that covers the cut at one end and blankets
    # a DIFFERENT mouth's approach at the other, where it sits at grade and
    # carries no corridor at all.  "A claimed road carries the corridor
    # HERE" is a question about the ground under the piece, so the answer
    # is the claim ∩ THE CUT: the region the claim was judged against in
    # the first place, never a new geometric notion.
    _corridor_polys: list = []
    try:
        _cut_parts = [_z for _l, _a, _f in _regions
                      for _z in (_l, _a)
                      if _z is not None and not _z.is_empty]
        _cut_u = unary_union(_cut_parts) if _cut_parts else None
    except _GEOM_EXC:                                  # pragma: no cover
        _cut_u = None
    if _cut_u is not None and not _cut_u.is_empty:
        for _cp, _cring, _calts in _claimed_depth:
            try:
                _part = _cp.intersection(_cut_u)
            except _GEOM_EXC:                          # pragma: no cover
                continue
            if _part is None or _part.is_empty:
                continue
            # THE DEPTH AT THIS FOOTPRINT, not the shape's global
            # minimum: a claimed lot can run from the cut (deep) to open
            # ground (at grade), and "does the claimant carry bore depth"
            # is a question about the ground under the piece.  Vertices
            # inside the footprint answer it; a footprint with none of
            # its own (a sliver between vertices) falls back to the
            # shape's minimum, which is the conservative answer — it
            # keeps today's stand-down behaviour rather than inventing a
            # keep.
            _here: list = []
            try:
                for _xy, _a in zip(_cring, _calts):
                    if _a is None:
                        continue
                    if _part.covers(Point(_xy)):
                        _here.append(float(_a))
            except _GEOM_EXC:                          # pragma: no cover
                _here = []
            _depth = (min(_here) if _here
                      else min((float(_a) for _a in _calts
                                if _a is not None), default=None))
            _corridor_polys.append((_part, _depth))
    return _n, _claimed_polys, _corridor_polys


#: Spec ``docs/specs/portal-corridor-claim-spec.md`` §2 gate.  Default
#: ON; OFF is today's behaviour — which is now NAMED removal, because
#: §1's per-piece instrument is ungated (it is law, not behaviour).
_PORTAL_CORRIDOR_CLAIM_ENV = "O4_PORTAL_CORRIDOR_CLAIM"

#: The corridor claim cuts a strip only where the strip is real pavement
#: area, not a boundary graze — the same floor R14-1's own claim uses.
_CORRIDOR_CLAIM_MIN_STRIP_M2 = _TUNNEL_CLAIM_MIN_OVERLAP_M2

#: …and only where a HOST SURVIVES the cut.  Below this the "remainder"
#: is a sliver, and taking the shape whole is what §2 forbids by name.
_CORRIDOR_CLAIM_MIN_HOST_M2 = 4.0


#: §T6.1 gate — claimed corridors wall themselves (portal-corridor-claim
#: §2.3).  Default ON; OFF is today's unwalled claim.
_CLAIM_WALLS_ENV = "O4_CLAIM_WALLS"

#: THE REGISTER of claimed corridors judged to be BORE GEOMETRY — the
#: ``id()`` set ``_wall_claimed_corridors`` walled.  Published so the
#: R10-2 mouth-walling finding reads the same population instead of
#: asking the question a second way (§T6.3).
_CLAIMED_BORE_REGISTER = "_tunnel_claimed_bore_ids"

#: THE WALLED BODIES THEMSELVES, as geometry, published beside the id
#: set.  §W1's own text asks the adjudication gate to subtract "the very
#: footprints :func:`_wall_claimed_corridors` walled — one population,
#: published, never re-derived", and the first implementation re-derived
#: them from ``s.polygon`` at gate time.  MEASURED at OTHH (baseline
#: td_base_othh, 2026-08-29): the waller registered 19 corridors and
#: walled 15 bodies, the emitted patch carries 12 below-grade
#: ``tunnel_road`` ways, and 4 of the 11 dropped wall pieces stand
#: 2.8-382 m from ANY surviving below-grade claim — the re-derivation
#: had drifted off the bodies the walls belong to, and the walls dropped
#: as "covered stretch" over the very pavement they retain.
_CLAIMED_BORE_BODIES = "_tunnel_claimed_bore_bodies"


def claim_walls_enabled() -> bool:
    return os.environ.get(_CLAIM_WALLS_ENV, "1") == "1"


#: A claimed corridor is BORE GEOMETRY (and so gets walls) only where it
#: was actually dug below the surface it sits in.  Above this it is an
#: at-grade approach that happens to be claimed — the same discriminator
#: Amendment 1 gave the stand-down.
_CLAIM_WALL_MIN_DIG_M = 0.25


def _wall_claimed_corridors(layout: "PavementLayout",
                            exclusion_zones: list,
                            pre_emit_shape_ids: set,
                            wall_gap_m: float,
                            retaining_wall_width_m: float,
                            dem_at, apt_elev: float) -> int:
    """§2.3 / §T6.1: A CLAIMED CORRIDOR IS FIRST-CLASS BORE GEOMETRY.

    *"A claimed corridor walls itself exactly as the synthetic path does
    (the R2 node-split wall class through the host), both sides, ends
    wrapped."*  Measured before: claimed corridors carried 0–48 % wall
    coverage against the synthetic path's 82 %, because the perimeter
    band is built from the ``tunnel_ramp`` union and a claimed corridor
    rides ``ref=tunnel_road`` — it was never in the set the waller saw.

    ONE WALLER: this hands the claimed footprints to
    :func:`emit_wall_band`, the same construction (and the same §T5 foot)
    the synthetic ramps get.  ``arm_ends=[]`` is what "ends wrapped"
    means — the ramp band cuts its far ends OPEN because the road
    continues at grade there; a claimed corridor's ends are its mouths,
    and the wall wraps them.

    Returns the number of corridor bodies walled.
    """
    if not claim_walls_enabled():
        return 0
    _bodies, _sources = [], []
    _register: set = set()
    for _s in layout.shapes:
        if getattr(_s, "ref", "") != TUNNEL_ROAD_REF:
            continue
        _poly = getattr(_s, "polygon", None)
        if (_poly is None or _poly.is_empty
                or _poly.geom_type != "Polygon"):
            continue
        # BELOW GRADE, HERE.  The dig is measured against the surface the
        # corridor sits in (the DEM / airport elevation), never against
        # absolute zero — LEMD's 561-617 m field is what makes an
        # absolute predicate vacuous (§T8.1's lesson, applied).
        _alts = [float(_a) for _a in (getattr(_s, "node_altitudes", None)
                                      or ()) if _a is not None]
        if not _alts:
            _a0 = getattr(_s, "altitude", None)
            if _a0 is None:
                continue
            _alts = [float(_a0)]
        try:
            _rp = _poly.representative_point()
            _ground = dem_at(_rp.x, _rp.y)
        except _GEOM_EXC:                                # pragma: no cover
            _ground = None
        _ground = float(_ground if _ground is not None else apt_elev)
        if _ground - min(_alts) < _CLAIM_WALL_MIN_DIG_M:
            continue
        _bodies.append(_poly)
        _sources.append(_s)
        _register.add(id(_s))
    try:
        setattr(layout, _CLAIMED_BORE_REGISTER, _register)
    except (AttributeError, TypeError):                  # pragma: no cover
        pass
    if not _bodies:
        return 0
    try:
        _u = unary_union(_bodies)
    except _GEOM_EXC:                                    # pragma: no cover
        return 0
    _parts = [_g for _g in getattr(_u, "geoms", [_u])
              if _g is not None and not _g.is_empty
              and _g.geom_type == "Polygon"]
    if not _parts:
        return 0
    try:
        # PUBLISH THE BODIES, not just the ids (§W1's "one population,
        # published, never re-derived").  The gate buffers THESE.
        setattr(layout, _CLAIMED_BORE_BODIES, list(_parts))
    except (AttributeError, TypeError):                # pragma: no cover
        pass
    _before = len(layout.shapes)
    emit_wall_band(layout, exclusion_zones, _parts, _sources, [],
                   wall_gap_m, retaining_wall_width_m, dem_at, apt_elev)
    _n_pieces = len(layout.shapes) - _before
    try:
        UI.vprint(1,
            f"  [pav-builder] §2.3 claimed-corridor walls: "
            f"{len(_parts)} claimed corridor bod(y/ies) walled both "
            f"sides with wrapped ends ({_n_pieces} wall piece(s)) — a "
            f"claimed corridor is bore geometry, walled exactly as the "
            f"synthetic path is.")
    except _GEOM_EXC:                                    # pragma: no cover
        pass
    return len(_parts)


#: §T6.2 gate.  Default ON; OFF is the pre-round whole-shape pass-2
#: claim (the OTHH -12168 relabel).
_CLAIM_FOOTPRINT_SCOPE_ENV = "O4_CLAIM_FOOTPRINT_SCOPE"


def claim_footprint_scope_enabled() -> bool:
    return os.environ.get(_CLAIM_FOOTPRINT_SCOPE_ENV, "1") == "1"


#: THE CORRIDOR'S OWN CARRIAGEWAY.  A ``service_road`` /
#: ``service_junction`` surface inside a tunnel's open cut IS the
#: corridor — it is the mapped roadway that runs into the mouth, not a
#: landside area the corridor happens to cross.  Owner law
#: (``docs/specs/othh-tunnel-mouth-canonical-spec.md``, sim read of
#: 1.0.269): *"a service_road must not wrap around and share edges with
#: a tunnel_road — the corridor is ONE surface"*, and the canonical
#: mouth is ONE ramp, no second road shape sharing the corridor.
#:
#: MEASURED, OTHH 2026-08-29 owner patch: cutting these hosts is what
#: minted every road duplicate the three owner sites name — shape 50
#: (service_road, 1,697 m² remainder) tiling exactly against strips 2308
#: + 2309 (729 + 734 m², 0 m² overlap, 211 m of shared edge, union area
#: == sum of parts) at 25.2557909,51.6083778; shape 47 cut into strips
#: 2306/2307 plus remainders 47/2304 — the "dual adjacent ramps" of item
#: 2; and service_junction 732 cut into 2314/2315/2317 at item 3.  The
#: remainder also KEPT the mouth: at 25.255673,51.6080375 the only ring
#: covering the owner's mouth point was the unclaimed remainder -10051,
#: which is the "ramp stops 2.6 m short of the mouth" reading.
#:
#: ``groundside_pavement`` is deliberately absent: that is the OTHH
#: -12168 class the footprint cut exists for (a 19,461 m² landside ring
#: relabelled whole because an 8 m corridor grazed one end).  A landside
#: area is not the corridor; a service road IS.
_CORRIDOR_OWN_ROAD_ROLES = frozenset({
    ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
})


#: How close an inserted mouth-line vertex may come to a vertex the ring
#: already has (metres).  Below this the ring already carries the mouth
#: and a second node there would only mint a duplicate — the same scale
#: the OSM emit's shared-vertex bucket works at.
_RING_DENSIFY_MIN_GAP_M = 0.05


def _densify_ring_at_corridor(poly, corridor):
    """``poly`` with the CORRIDOR'S OWN boundary vertices inserted, or
    ``None`` when that cannot be done exactly.

    A service road claimed WHOLE (``_CORRIDOR_OWN_ROAD_ROLES``) is
    re-profiled at its own ring vertices, and a mapped road's ring has
    vertices where the ROAD bends — not where the open cut starts and
    ends.  Without this the claimed surface can descend at a vertex 30 m
    up the road and carry no vertex at the mouth line at all, which is
    the owner's "the ramp does not reach the mouth" reading arriving by
    a second route.

    The insertion is EXPLICIT — every crossing of the corridor's
    boundary with a ring edge becomes a vertex ON that edge, in order.
    (Re-uniting ``intersection`` + ``difference`` does not work: GEOS
    dissolves the shared boundary again and hands back the original
    four corners.)  Nothing else moves: the ring's own vertices are
    kept, the area is asserted unchanged, and any failure returns
    ``None`` so the caller re-profiles the undensified ring.
    """
    if poly is None or poly.is_empty or corridor is None \
            or corridor.is_empty:
        return None
    try:
        _bnd = corridor.boundary
        _ring = list(poly.exterior.coords)
    except _GEOM_EXC:                                    # pragma: no cover
        return None
    if _bnd is None or _bnd.is_empty or len(_ring) < 4:
        return None
    _out: list = []
    _added = 0
    for _i in range(len(_ring) - 1):
        _a, _b = _ring[_i], _ring[_i + 1]
        _out.append(_a)
        try:
            _seg = LineString([_a, _b])
            _hit = _seg.intersection(_bnd)
        except _GEOM_EXC:                                # pragma: no cover
            continue
        if _hit is None or _hit.is_empty:
            continue
        _pts: list = []
        for _g in getattr(_hit, "geoms", [_hit]):
            if _g is None or _g.is_empty:
                continue
            if _g.geom_type == "Point":
                _pts.append((_g.x, _g.y))
            elif _g.geom_type == "LineString":
                _pts.extend(list(_g.coords))
        _len = _seg.length
        if not (_len > 0.0):
            continue
        _keep = []
        for _p in _pts:
            try:
                _s = _seg.project(Point(_p))
            except _GEOM_EXC:                            # pragma: no cover
                continue
            # Not at either end: the ring already has those vertices.
            if _RING_DENSIFY_MIN_GAP_M < _s < _len - _RING_DENSIFY_MIN_GAP_M:
                _keep.append((_s, _p))
        for _s, _p in sorted(_keep):
            if math.hypot(_p[0] - _out[-1][0],
                          _p[1] - _out[-1][1]) < _RING_DENSIFY_MIN_GAP_M:
                continue
            _out.append(_p)
            _added += 1
    _out.append(_ring[-1])
    if not _added:
        return None
    try:
        _new = Polygon(_out)
    except (ValueError, _GEOM_EXC):                      # pragma: no cover
        return None
    if _new.is_empty or not _new.is_valid:
        return None
    if abs(_new.area - poly.area) > max(0.01, 1e-4 * poly.area):
        return None
    return _new


def _split_host_at_corridor(poly, corridor, host_role: str | None = None):
    """``(strip_parts, host_parts)`` — the CORRIDOR FOOTPRINT cut out of a
    host surface, or ``None`` when there is nothing to cut.

    Spec ``portal-corridor-claim-spec.md`` §2.2, enforced across BOTH
    claim authorities by §T6.2: *"the claim rides the corridor FOOTPRINT
    only — never the whole host ring"*.  OTHH -12168 is the exemplar: a
    19,461 m² landside ring relabelled ``tunnel_road`` WHOLE because an
    8 m corridor grazed one end of it, its far tongues then reaching into
    the covered interior at z=1.90.

    ``None`` has three distinct causes and all mean "do not cut here":

    * the strip is a graze below ``_CORRIDOR_CLAIM_MIN_STRIP_M2`` — there
      is no corridor on this surface;
    * NO host survives the cut — the surface IS the corridor (a road rect
      wholly inside it), which is the case the whole-shape claim is
      RIGHT for.  Cutting there would mint a strip and delete a host that
      was never anything else; and
    * ``host_role`` is one of ``_CORRIDOR_OWN_ROAD_ROLES`` — the surface
      IS the corridor by ROLE, whether or not an area of it survives the
      cut.  This is the same case as the one above, recognised before
      the arithmetic instead of after it: a service road running into a
      mouth is longer and wider than the open-cut region, so a host
      always "survived" and every such corridor shipped as a claimed
      strip plus a wrapping unclaimed remainder.  The canonical mouth
      law forbids that second road shape.

    One implementation, so the two claim paths can never disagree about
    what "the footprint" means.
    """
    if host_role in _CORRIDOR_OWN_ROAD_ROLES:
        return None
    if poly is None or poly.is_empty or corridor is None \
            or corridor.is_empty:
        return None
    try:
        _strip = poly.intersection(corridor)
        _rest = poly.difference(corridor)
    except _GEOM_EXC:                                    # pragma: no cover
        return None
    _strip_parts = [_g for _g in getattr(_strip, "geoms", [_strip])
                    if _g is not None and not _g.is_empty
                    and _g.geom_type == "Polygon"
                    and _g.area >= _CORRIDOR_CLAIM_MIN_STRIP_M2]
    if not _strip_parts:
        return None
    _host_parts = [_g for _g in getattr(_rest, "geoms", [_rest])
                   if _g is not None and not _g.is_empty
                   and _g.geom_type == "Polygon"
                   and _g.area >= _CORRIDOR_CLAIM_MIN_HOST_M2]
    if not _host_parts:
        return None
    _host_parts.sort(key=lambda g: g.area, reverse=True)
    return _strip_parts, _host_parts


def _claim_portal_corridor_footprint(layout: "PavementLayout",
                                     portal_data: list,
                                     facing_pairs: list,
                                     wall_gap_m: float,
                                     pre_emit_shape_ids: set) -> int:
    """THE CORRIDOR FOOTPRINT IS CLAIMED (RULINGS 2026-08-25e option (a);
    spec ``docs/specs/portal-corridor-claim-spec.md`` §2).

    R14-1 claims ROAD pavement covering the cut.  Where the corridor
    lands on pavement it may NOT claim — airside, or a landside role
    outside the claimable set — today's passes admit the mouth, emit its
    ramp, and then delete every piece for "pavement coverage": OTHH
    mouth D is emitted and then removed, and 4 of 8 OTHH portal clusters
    lose every ramp that way.  The owner's disposition is option (a):
    the ramp CLAIMS THE CORRIDOR'S OWN FOOTPRINT and lowers it to the
    bore profile.

    SCOPE, and it is the whole of the ruling's caution: the CORRIDOR
    STRIP only, never the host shape whole.  A 673,901 m² apron crossed
    by an 8 m ramp cedes the 8 m strip and keeps everything else — its
    role, its law, its census population — so the host is cut, never
    claimed.  A host that would not survive the cut is left alone and
    keeps its ``tunnel_airside_conflict`` finding.

    ONE CLAIM AUTHORITY.  The region is ``_tunnel_open_cut_regions``'
    own — the same records R14-1 judges against and the same ones
    ``publish_tunnel_open_cut_regions`` hands to the node book — and the
    profile is pass 2's arithmetic: each vertex takes the LOWER of its
    own solved value and ``floor + TUNNEL_APPROACH_GRADE × distance``
    from the level surface.  The claim can only DIG.

    The strip is minted as claimed corridor pavement (``TUNNEL_ROAD_REF``
    on ``ROLE_TUNNEL_RAMP``), which is what makes the removers stop
    deleting the ramp above it: the host no longer covers the alignment,
    because the host no longer includes it.

    Returns the number of strips claimed.
    """
    if os.environ.get(_PORTAL_CORRIDOR_CLAIM_ENV, "1") != "1":
        return 0
    from .elevation import _resample_node_altitudes_nn
    from .groundside import _ring_and_altitudes
    _regions = _tunnel_open_cut_regions(
        portal_data, facing_pairs, wall_gap_m)
    if not _regions:
        return 0
    _zones = [(_l, _a, float(_f)) for _l, _a, _f in _regions]
    _parts = [_z for _l, _a, _f in _zones for _z in (_l, _a)
              if _z is not None and not _z.is_empty]
    if not _parts:
        return 0
    try:
        _corridor = unary_union(_parts)
        _level_surface = unary_union(
            [_l for _l, _a, _f in _zones
             if _l is not None and not _l.is_empty])
    except _GEOM_EXC:                                  # pragma: no cover
        return 0
    if _corridor is None or _corridor.is_empty:
        return 0

    def _profile_at(pt, floors) -> float | None:
        """Pass 2's arithmetic, verbatim in kind: the lowest profile any
        hit region offers at this point."""
        _best = None
        for _floor in floors:
            _from = (_level_surface
                     if _level_surface is not None
                     and not _level_surface.is_empty else None)
            try:
                _d = 0.0 if _from is None else _from.distance(pt)
            except _GEOM_EXC:                          # pragma: no cover
                continue
            _p = _floor + TUNNEL_APPROACH_GRADE * _d
            if _best is None or _p < _best:
                _best = _p
        return _best

    _n = 0
    _minted: list = []
    for _idx, _shape in enumerate(list(layout.shapes)):
        # PRE-EXISTING PAVEMENT ONLY.  A tunnel piece this build just
        # emitted is not a host — it is what the claim is FOR.
        if id(_shape) not in pre_emit_shape_ids:
            continue
        if getattr(_shape, "ref", "") == TUNNEL_ROAD_REF:
            continue                    # R14-1 already claimed it whole
        _role = getattr(_shape, "role", "")
        if _role not in _AIRSIDE_GATE_ROLES or _role == "building":
            continue
        _poly = getattr(_shape, "polygon", None)
        if (_poly is None or _poly.is_empty
                or _poly.geom_type != "Polygon"):
            continue
        _floors = []
        for _l, _a, _f in _zones:
            for _z in (_l, _a):
                if _z is None or _z.is_empty:
                    continue
                try:
                    if _poly.intersects(_z):
                        _floors.append(_f)
                        break
                except _GEOM_EXC:                      # pragma: no cover
                    continue
        if not _floors:
            continue
        # §2.2, one implementation (§T6.2): the footprint cut, or None —
        # a graze, or a host that would not survive (NEVER THE HOST WHOLE:
        # leave it, and leave R14-1's airside finding to speak for it).
        _split = _split_host_at_corridor(_poly, _corridor, _role)
        if _split is None:
            continue
        _strip_parts, _rest_parts = _split
        _ring, _alts = _ring_and_altitudes(_shape)
        if _ring is None or not _alts:
            continue
        _open_ring = _ring[:-1] if (_ring and _ring[0] == _ring[-1]) else _ring
        _new_strips: list = []
        for _sp in _strip_parts:
            _sa = _resample_node_altitudes_nn(
                _sp, _open_ring, list(_alts), interior_edge_project=True)
            if _sa is None:
                continue
            try:
                _coords = list(_sp.exterior.coords)
            except _GEOM_EXC:                          # pragma: no cover
                continue
            _lowered = []
            _dug = 0.0
            for _v, _xy in enumerate(_coords):
                _own = float(_sa[min(_v, len(_sa) - 1)])
                _p = _profile_at(Point(_xy), _floors)
                _val = _own if _p is None else min(_own, _p)
                _dug = max(_dug, _own - _val)
                _lowered.append(round(_val, 2))
            if _dug < 0.01:
                # The corridor is already at or below this pavement —
                # nothing to dig, so nothing to claim.
                continue
            _new_strips.append(BuiltShape(
                polygon=_sp, role=ROLE_TUNNEL_RAMP, ref=TUNNEL_ROAD_REF,
                node_altitudes=_lowered))
        if not _new_strips:
            continue
        # THE HOST IS CUT, NOT CLAIMED: its largest remainder stays the
        # shape (identity, role and law preserved), and any further
        # piece the crossing severed is minted as its sibling — the
        # corridor may split a host, and dropping the far side would be
        # taking area the claim never asked for.
        _host_alts = _resample_node_altitudes_nn(
            _rest_parts[0], _open_ring, list(_alts),
            interior_edge_project=True)
        if _host_alts is None:
            continue
        for _extra in _rest_parts[1:]:
            _ea = _resample_node_altitudes_nn(
                _extra, _open_ring, list(_alts),
                interior_edge_project=True)
            if _ea is None:
                continue
            # Same rule as the R14-1 path: the host's provenance rides
            # its remainder (§T7's discriminator must survive the cut).
            _minted.append(BuiltShape(
                polygon=_extra, role=_role,
                ref=getattr(_shape, "ref", ""), node_altitudes=_ea,
                synthesised_road_corridor=getattr(
                    _shape, "synthesised_road_corridor", False)))
        _shape.polygon = _rest_parts[0]
        _shape.node_altitudes = _host_alts
        _shape.altitude = None
        _shape.altitude_high = None
        _shape.altitude_low = None
        _minted.extend(_new_strips)
        _n += len(_new_strips)
        for _sp_shape in _new_strips:
            log_tunnel_corridor_claim(layout, _sp_shape, _role, _idx)
    if not _n:
        return 0
    layout.shapes.extend(_minted)
    try:
        UI.vprint(1,
            f"  [pav-builder] portal corridor claim: {_n} corridor "
            f"strip(s) cut out of host pavement and lowered to the bore "
            f"profile (RULINGS 2026-08-25e) — the FOOTPRINT only, never "
            f"the host whole; each host keeps its role, its law and the "
            f"rest of its area.")
    except _GEOM_EXC:                                  # pragma: no cover
        pass
    return _n


#: The claim's own depth, stashed on the shape it authored.  Spec
#: ``portal-corridor-claim-spec.md`` AMENDMENT 2: the fields ride the
#: shape, so the shape is also where the VERIFICATION rides.
_TUNNEL_CLAIM_DEPTH_ATTR = "_tunnel_claim_depth"


def _stash_tunnel_claim_depth(shape, alts) -> None:
    _zs = [float(_a) for _a in (alts or ()) if _a is not None]
    if not _zs:
        return
    try:
        setattr(shape, _TUNNEL_CLAIM_DEPTH_ATTR, (min(_zs), max(_zs)))
    except (AttributeError, TypeError):                # pragma: no cover
        return


def audit_tunnel_claim_drift(layout, where: str,
                             tol_m: float = 0.10) -> int:
    """Has any claimed corridor DRIFTED off the depth R14-1 gave it?

    The claim's verification rides the shape beside the claim itself, so
    a pass that moves an authored corridor is named WHERE it happened
    rather than inferred from the emitted patch three hours later — the
    archaeology this round paid for twice (mouth D, then the service
    residual).  Reports only; never fails a build.

    Returns the number of drifted shapes.
    """
    _rows = []
    for _s in (getattr(layout, "shapes", None) or ()):
        _claim = getattr(_s, _TUNNEL_CLAIM_DEPTH_ATTR, None)
        if not _claim:
            continue
        _alts = [float(_a) for _a in (getattr(_s, "node_altitudes", None)
                                      or ()) if _a is not None]
        if not _alts:
            _flat = getattr(_s, "altitude", None)
            _alts = [] if _flat is None else [float(_flat)]
        if not _alts:
            _rows.append((_s, None, _claim))
            continue
        if abs(min(_alts) - _claim[0]) > tol_m:
            _rows.append((_s, min(_alts), _claim))
    if not _rows:
        return 0
    try:
        _, _to_ll = _local_meter_projections(layout.anchor)
        for _s, _now, _claim in _rows:
            _c = _s.polygon.centroid
            _lat, _lon = _to_ll(_c.x, _c.y)
            UI.vprint(1,
                      f"  [tunnel-claim-drift] at {where}: "
                      f"role={getattr(_s, 'role', '') or '-'} "
                      f"ref={getattr(_s, 'ref', '') or '-'} "
                      f"@{_lat:.7f},{_lon:.7f} "
                      f"area={_s.polygon.area:.1f}m2 claimed "
                      f"{_claim[0]:.2f} m -> "
                      + ("NO FIELD" if _now is None else f"{_now:.2f} m"))
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        pass
    return len(_rows)


def log_tunnel_road_claim(layout, shape, alts, how: str) -> None:
    """Name every surface R14-1 CLAIMS, with the depth it gave it.

    The third face of the same instrument (RULINGS 2026-08-25e §1): the
    removals are named, the refusals are named, and so is the claim that
    justifies a removal.  Without it "claimed 12 road surface(s)" was
    the only record, and answering "which shape, and did its corridor
    ever ship" took a geometric re-derivation off the emitted patch.
    """
    try:
        _poly = getattr(shape, "polygon", None)
        _, _to_ll = _local_meter_projections(layout.anchor)
        _c = _poly.centroid
        _lat, _lon = _to_ll(_c.x, _c.y)
        _zs = [float(_a) for _a in (alts or ()) if _a is not None]
        UI.vprint(1,
                  f"  [tunnel-claim] road {how}: "
                  f"role={getattr(shape, 'role', '') or '-'} "
                  f"@{_lat:.7f},{_lon:.7f} area={_poly.area:.1f}m2"
                  + (f" depth={min(_zs):.2f}..{max(_zs):.2f}m" if _zs
                     else ""))
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        return


def log_tunnel_piece_kept(layout, shape, predicate: str, *,
                          coverage=None, verdict=None) -> None:
    """A REFUSAL TO REMOVE is a verdict too (spec
    ``portal-corridor-claim-spec.md`` AMENDMENT 1 §2).

    The §1 instrument names every piece a pass deletes; a pass that
    decides NOT to delete one on a new rule must say so with the same
    identity, or the next reader cannot tell "the rule fired and kept
    it" from "the rule never ran".
    """
    try:
        _poly = getattr(shape, "polygon", None)
        _where = "?"
        if _poly is not None and not _poly.is_empty:
            _, _to_ll = _local_meter_projections(layout.anchor)
            _c = _poly.centroid
            _lat, _lon = _to_ll(_c.x, _c.y)
            _where = f"{_lat:.7f},{_lon:.7f}"
        _cov = "" if coverage is None else f" coverage={coverage:.3f}"
        _vd = "" if not verdict else f" [{verdict}]"
        _area = (f" area={_poly.area:.1f}m2"
                 if _poly is not None and not _poly.is_empty else "")
        UI.vprint(1,
                  f"  [tunnel-keep] {predicate}: "
                  f"ref={getattr(shape, 'ref', '') or '-'} "
                  f"role={getattr(shape, 'role', '') or '-'} "
                  f"@{_where}{_cov}{_area}{_vd}")
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        return


def log_tunnel_claimant_cover(layout, piece, claimed_members) -> None:
    """Name the CLAIM POLYGON that covered a stood-down piece.

    RULINGS 2026-08-25e requires every remover to name what it deletes;
    a stand-down is a removal justified by ANOTHER shape, so the
    justification is named too.  Without this the mouth-D log said "N
    rectangles stood down" and nothing about the claimant, and the
    lane's offline read found the nearest surviving ``tunnel_road``
    surface 702.7 m away — a claim covering a mouth whose road is not
    there.  This line is what tells those two facts apart: an OVERSIZED
    claimant (a whole road shape reaching far past the cut) reads as a
    huge area with a distant centroid, and a claim that outlived its
    road reads as a member with no surviving surface under it.
    """
    try:
        _best = None
        for _m in (claimed_members or ()):
            try:
                _ov = piece.polygon.intersection(_m).area
            except (*_GEOM_EXC,):
                continue
            if _ov <= 0.0:
                continue
            if _best is None or _ov > _best[0]:
                _best = (_ov, _m)
        if _best is None:
            UI.vprint(1,
                      "  [tunnel-claimant] (none: the union covered it "
                      "but no single member does)")
            return
        _ov, _m = _best
        _, _to_ll = _local_meter_projections(layout.anchor)
        _c = _m.centroid
        _lat, _lon = _to_ll(_c.x, _c.y)
        _pc = piece.polygon.centroid
        _plat, _plon = _to_ll(_pc.x, _pc.y)
        _dist = math.hypot(_c.x - _pc.x, _c.y - _pc.y)
        UI.vprint(1,
                  f"  [tunnel-claimant] covered by claim @"
                  f"{_lat:.7f},{_lon:.7f} area={_m.area:.1f}m2 "
                  f"span={_m.length:.0f}m centroid_dist={_dist:.0f}m "
                  f"share={_ov / max(1e-9, piece.polygon.area):.3f} "
                  f"(piece @{_plat:.7f},{_plon:.7f})")
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        return


def log_tunnel_corridor_claim(layout, strip, host_role: str,
                              host_index: int) -> None:
    """The §1 instrument's positive twin: name every strip the corridor
    claim CUTS, with the host it came from.

    A claim is a removal from the host's point of view, and the same
    rule applies — a pass that changes what ships names each piece it
    changed, so no surface moves anonymously.
    """
    try:
        _, _to_ll = _local_meter_projections(layout.anchor)
        _c = strip.polygon.centroid
        _lat, _lon = _to_ll(_c.x, _c.y)
        _z = strip.node_altitudes or []
        UI.vprint(1,
                  f"  [tunnel-claim] corridor footprint: "
                  f"host_role={host_role or '-'} host={host_index} "
                  f"@{_lat:.7f},{_lon:.7f} "
                  f"area={strip.polygon.area:.1f}m2"
                  + (f" depth={min(_z):.2f}..{max(_z):.2f}m" if _z else ""))
    except (AttributeError, TypeError, ValueError, *_GEOM_EXC):
        return


def publish_tunnel_open_cut_regions(layout: "PavementLayout",
                                    regions: list) -> int:
    """Publish THE OPEN CUT — the portal walk's own plan-space extent —
    on the layout, for every downstream consumer.

    Spec ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``
    AMENDMENT 5.  The sibling publisher below hands on the CLAIM SET:
    the road surfaces R14-1 re-profiled.  That answers "which pavement
    did the cut capture", and the node book asked it for four rounds on
    the strength of the two regions being the same.  They are not:
    OTHH's descending bore FLOOR is a ``groundside_pavement`` ring
    beside the claimed roads, 0-2 of its 33 nodes inside the claim, so
    every claim-keyed rule reached two vertices of the nine that needed
    protecting (finding 4, measured).

    THE REGION PUBLISHED HERE IS NOT DERIVED HERE.  It is
    :func:`_tunnel_open_cut_regions`' own output — the same records
    :func:`_claim_road_pavement` judges every shape against and the same
    ones behind the "N AIRSIDE shape(s) lie inside a tunnel open cut"
    report — flattened to the plan-space polygons (``level_zone`` and
    ``approach_zone``; the elevations stay with the regions, which is
    where the R14-3 grade lives).  A second geometric notion of "inside
    the cut" computed anywhere else is the spec violation this pattern
    exists to prevent.

    ACCUMULATES, never replaces: a tile has many tunnel systems and each
    one publishes its own.  Returns the number of polygons published.
    """
    _polys: list = []
    for _rec in (regions or ()):
        for _zone in (_rec[0] if len(_rec) > 0 else None,
                      _rec[1] if len(_rec) > 1 else None):
            if _zone is None or getattr(_zone, "is_empty", True):
                continue
            _polys.append(_zone)
    if not _polys:
        return 0
    try:
        _existing = list(
            getattr(layout, "tunnel_open_cut_polys", None) or [])
        _existing.extend(_polys)
        layout.tunnel_open_cut_polys = _existing
    except (AttributeError, TypeError):                # pragma: no cover
        return 0
    return len(_polys)


def publish_tunnel_open_cut_claim_set(layout: "PavementLayout",
                                      claimed_polys: list) -> int:
    """Publish R14-1's OWN claim set on the layout — ``THE`` tunnel
    open-cut claim set, for every downstream consumer.

    Spec ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md`` §2:
    the exclusion is defined by AUTHORITY, and the authority is this
    claim — the very shapes :func:`_claim_road_pavement` just re-profiled
    and logged as "claimed N road surface(s) as the tunnel corridor",
    the same list :func:`_stand_down_synthetic_over_claimed` consumes.
    ONE authority: a second geometric notion of "inside the cut"
    computed anywhere else is a spec violation, so this publishes the
    list verbatim and derives nothing.

    Returns the number of polygons published (0 when there is no claim —
    and no claim means no exclusion anywhere downstream).
    """
    _polys = [p for p in (claimed_polys or ())
              if p is not None and not getattr(p, "is_empty", True)]
    if not _polys:
        return 0
    try:
        _existing = list(
            getattr(layout, "tunnel_open_cut_claim_polys", None) or [])
        _existing.extend(_polys)
        layout.tunnel_open_cut_claim_polys = _existing
    except (AttributeError, TypeError):                # pragma: no cover
        return 0
    return len(_polys)


#: How close a claimant's surface must come to a below-grade piece
#: before the two count as THE SAME SURFACE (spec
#: ``portal-corridor-claim-spec.md`` AMENDMENT 1).  Half a metre is the
#: scale the emit already works at — ``SHARED_VERTEX_TOL_M`` merges
#: vertices at 0.5 m — so a claimant within it is carrying the piece's
#: own depth, and anything higher is a different surface standing above
#: the bore.
_STAND_DOWN_BORE_DEPTH_TOL_M = 0.5


def _piece_min_altitude(shape) -> float | None:
    """The lowest altitude a tunnel piece carries, whichever convention
    it uses (per-vertex, flat, or an end-pair rect)."""
    _alts = [float(_a) for _a in (getattr(shape, "node_altitudes", None)
                                  or ()) if _a is not None]
    if _alts:
        return min(_alts)
    for _attr in ("altitude", "altitude_low", "altitude_high"):
        _v = getattr(shape, _attr, None)
        if _v is not None:
            _alts.append(float(_v))
    return min(_alts) if _alts else None


def _claimant_carries_bore_depth(piece, pairs) -> tuple:
    """``(carries, verdict_text)`` — does the claim under ``piece``
    actually carry the piece's own depth?

    Spec ``portal-corridor-claim-spec.md`` AMENDMENT 1.  The comparison
    is local and it is between the two surfaces the stand-down is
    choosing among: the piece's lowest altitude, and the lowest depth
    any COVERING claim footprint was actually given.  A claimant within
    ``_STAND_DOWN_BORE_DEPTH_TOL_M`` of the piece is the same surface
    (duplicate geometry — stand the piece down, which is what this pass
    is for); one standing above it is the ground the bore is cut into,
    and deleting the piece would leave the mouth with no bore geometry
    at all — the measured mouth-D deletion.

    A caller that supplies no depths (the whole-shape list every
    pre-Amendment caller passes) gets ``True``: unknown depth keeps the
    pass exactly as it behaved, so this amendment can only ever SAVE a
    piece it can prove is alone.
    """
    _pz = _piece_min_altitude(piece)
    if _pz is None:
        return True, "piece depth unknown"
    _best = None
    _any_known = False
    for _poly, _depth in pairs:
        if _depth is None:
            continue
        try:
            if not piece.polygon.intersects(_poly):
                continue
        except _GEOM_EXC:                              # pragma: no cover
            continue
        _any_known = True
        if _best is None or float(_depth) < _best:
            _best = float(_depth)
    if not _any_known or _best is None:
        return True, "claimant depth unknown"
    _carries = _best <= _pz + _STAND_DOWN_BORE_DEPTH_TOL_M
    return _carries, (f"claimant {_best:.2f} m vs piece {_pz:.2f} m "
                      f"({'carries bore depth' if _carries else 'AT GRADE'})")


def _stand_down_synthetic_over_claimed(layout: "PavementLayout",
                                       claimed_polys: list,
                                       pre_emit_shape_ids: set) -> int:
    """R14-1 second bullet: a synthetic ramp/corridor rectangle emits ONLY
    where NO mapped road pavement covers the alignment.

    Where a claimed road now carries the tunnel surface, the rectangle
    beside it is the cliff's other half — it goes.  Judged by AREA
    COVERED (>= half), so a piece merely clipping a claimed edge stays
    and is welded by the ordinary cuts.

    THE CLAIMANT MUST CARRY BORE DEPTH (spec
    ``docs/specs/portal-corridor-claim-spec.md`` AMENDMENT 1, resolving
    the mouth-D fork).  This pass exists to stop DUPLICATE corridor
    geometry — a synthetic rectangle beside a claimed road that already
    carries the bore.  It was doing something else: at OTHH the R14-1
    line reads "claimed 12 road surface(s) (0 LEVELLED AT BORE DEPTH,
    the rest graded out at the 5 % cap)", so no claimed surface carried
    the corridor anywhere on the field — and the pass deleted mouth D's
    four ramp pieces, which were the ONLY below-grade geometry there.
    An at-grade claimant standing above a below-grade piece is not a
    duplicate of it; it is the ground the piece is cut into.  So a
    below-grade piece now stands down only where its claimant comes
    within ``_STAND_DOWN_BORE_DEPTH_TOL_M`` of the piece's own depth,
    and every verdict — stand-down or keep — is named per piece.

    ``claimed_polys`` members may be a bare polygon (the whole-shape
    list, and what every pre-Amendment caller passes: no depth known, so
    the pass behaves exactly as it did) or a ``(polygon, depth)`` pair
    from the corridor-footprint list, where ``depth`` is the altitude
    the claim actually gave that footprint.
    """
    if not claimed_polys:
        return 0
    _raw = (claimed_polys if isinstance(claimed_polys, (list, tuple))
            else [claimed_polys])
    #: ``[(polygon, depth_or_None)]`` — one normal form for both callers.
    _pairs = []
    for _m in _raw:
        if isinstance(_m, tuple):
            _poly, _depth = (_m + (None,))[:2]
        else:
            _poly, _depth = _m, None
        if _poly is None or getattr(_poly, "is_empty", True):
            continue
        _pairs.append((_poly, _depth))
    if not _pairs:
        return 0
    try:
        _claimed = unary_union([_poly for _poly, _d in _pairs])
    except _GEOM_EXC:
        return 0
    # THE CLAIMANT IS NAMED, NOT JUST THE VICTIM (RULINGS 2026-08-25e's
    # instrument clause, applied to the other side of this predicate).
    # A stood-down ramp is deleted because SOME claim polygon covers it,
    # and "which one, and how big is it" is the question the mouth-D
    # attribution could not answer from the log: the summary line said
    # only how many rectangles went.
    _members = [_poly for _poly, _d in _pairs]
    _kept, _n = [], 0
    for _s in layout.shapes:
        if (id(_s) not in pre_emit_shape_ids
                and getattr(_s, "ref", "") in ("tunnel_ramp",
                                               "tunnel_corridor")
                and _s.polygon is not None and not _s.polygon.is_empty):
            try:
                _ovc = _s.polygon.intersection(_claimed).area
                if _ovc >= 0.5 * _s.polygon.area:
                    _cov = _ovc / max(1e-9, _s.polygon.area)
                    _carries, _verdict = _claimant_carries_bore_depth(
                        _s, _pairs)
                    if not _carries:
                        # AMENDMENT 1: the claimant stands ABOVE this
                        # piece, so the piece is the bore geometry here
                        # and deleting it would leave the mouth with
                        # none.  Named, like every other verdict.
                        log_tunnel_piece_kept(
                            layout, _s,
                            "R14-1 stand-down REFUSED — claimant at grade",
                            coverage=_cov, verdict=_verdict)
                        _kept.append(_s)
                        continue
                    _n += 1
                    log_tunnel_piece_removal(
                        layout, _s, "R14-1 stand-down over claimed road",
                        coverage=_cov, verdict=_verdict)
                    log_tunnel_claimant_cover(layout, _s, _members)
                    continue
            except _GEOM_EXC:
                pass
        _kept.append(_s)
    if _n:
        layout.shapes = _kept
        try:
            UI.vprint(1,
                f"  [pav-builder] R14-1: stood down {_n} synthetic tunnel "
                f"rectangle(s) — claimed road pavement carries the "
                f"corridor there.")
        except _GEOM_EXC:
            pass
    return _n


def _emit_tunnel_portals(
        layout: "PavementLayout",
        dem,
        tile_lat: int,
        tile_lon: int,
        tunnel_depth_m: float = 8.0,
        max_ramp_grade: float = 0.04,
        ramp_min_length_m: float = 200.0,
        arm_max_length_m: float = 500.0,
        carriageway_width_m: float = TUNNEL_DEFAULT_CARRIAGEWAY_WIDTH_M,
        retaining_wall_width_m: float = 1.0,
        # ``wall_gap_m`` must exceed the OSM emit's vertex bucket
        # size (SHARED_VERTEX_TOL_M = 0.5 m) so the ramp's road-edge
        # corners and the wall's inner corners don't hash to the
        # same node id.  At the portal end the ramp altitude is
        # apt_elev − tunnel_depth; the wall altitude is apt_elev.
        # Sharing the vertex would emit one node with two altitudes,
        # rendering as a vertical glitch (user 2026-05-03).
        wall_gap_m: float = 0.6,
        # Divided-highway carriageways with two parallel ways
        # cluster into a single combined entrance.  User 2026-05-03:
        # one entrance per end of the tunnel, not one per
        # carriageway.  User 2026-07-04 (KDFW): ways less than 35 m
        # apart group into ONE corridor (motorway + frontage road +
        # rail together); KDFW's two motorway carriageways at ~113 m
        # correctly stay separate.
        portal_cluster_dist_m: float = UNDERPASS_GROUP_DIST_M,
        boundary_clearance_m: float = 0.5,
        # Per user 2026-05-04: skip portals more than this far from
        # any airport boundary edge.  Tunnels far from the airport
        # don't affect X-Plane's airport mesh and were generating
        # spurious ramps along distant urban roads.
        max_boundary_dist_m: float = 1000.0,
        excluded_way_ids: set | None = None,
        skip_if_adjacent_road: bool = SKIP_TUNNEL_RAMPS_NEAR_ROADS,
        adjacent_road_dist_m: float = TUNNEL_ADJACENT_ROAD_DIST_M,
        ) -> int:
    """For each tunnel portal (each end of an OSM ``aeroway=*``
    ``tunnel=yes|building_passage`` way), emit the visible road-
    surface structure that transitions outside-DEM elevation down
    to ``apt_elev − tunnel_depth_m`` at the portal:

      1. A flat ``ROLE_RETAINING_WALL`` CAP polygon AT the portal
         node (perpendicular to road direction at portal).  The
         cap's centre line is the portal node — its width spans
         the road (carriageway width + wall_gap on each side),
         its thickness is ``retaining_wall_width_m`` (1 m).
      2. Two flat ``ROLE_RETAINING_WALL`` ARM polygons reaching
         OUTWARD from the cap along the surface roadway, on each
         side of the carriageway.  The arms follow the OSM
         surface road's polyline — multi-segment when the road
         curves.  Arm length adapts to terrain: we first walk up
         to ``arm_max_length_m`` (default 500 m), sample DEM at
         the far end, then truncate the walk so the grade from
         ``apt_elev − tunnel_depth_m`` (portal) up to that DEM
         height never exceeds ``max_ramp_grade``.  Floor at
         ``ramp_min_length_m`` (default 200 m) so a flat road
         still gets a substantial visible approach.
      3. A chain of sloped ``ROLE_TUNNEL_RAMP`` polygons matching
         the surface-road segments under the arms.  Each segment's
         elevation interpolates linearly from
         ``apt_elev − tunnel_depth_m`` at the portal to outside
         DEM at the far end of the walk, in proportion to its
         cumulative distance from the portal.

    Per user 2026-04-29 (SPJC review): the previous geometry put
    the cap PAST the portal INSIDE the airport, with arms going
    AWAY from the tunnel only as far as the OSM way extended
    outside the airport.  That made SPJC's SW tunnel "too short
    and inside the tunnel" because the OSM way ended right at the
    boundary.  Walking the SURFACE road OUTWARD from the OSM
    portal node correctly lands the cap at the tunnel mouth and
    the arms on the highway approach.

    Two-carriageway tunnels (divided highways) cluster by portal-
    node proximity (within ``portal_cluster_dist_m``).  Each
    carriageway in a cluster gets its own arm pair; the caps form
    a perpendicular line across all member portals.

    Boundary coordination: subtract the tunnel-polygon union
    (buffered by ``boundary_clearance_m``, default 1 m which
    exceeds the OSM-emit vertex bucket size of 0.5 m so boundary
    nodes never collapse onto wall nodes) from every
    ``ROLE_BOUNDARY`` shape.

    Returns the number of tunnel PORTALS emitted (each contributing
    1 cap + 2 arm walls + a ramp chain).
    """
    nodes_r, ways_r, _big_way_ids, _node_tags_r = (
        _load_tunnel_road_network(layout))
    if not ways_r:
        return 0
    # Project nodes to meter space.
    _to_m, _m_to_ll = _local_meter_projections(layout.anchor)
    nodes_m: dict[str, tuple[float, float]] = {}
    for nid, (lat, lon) in nodes_r.items():
        nodes_m[nid] = _to_m(lon, lat)
    # Airside pavement union for the per-portal gate (see the
    # AIRSIDE / DOUBLE-EMIT GATE comment below).  Role set at module
    # level — ``_finalize_tunnel_emission`` rebuilds this union after
    # the ruling-4 ramp cut and must use the SAME set.
    try:
        _airside_gate_u = unary_union(
            [s.polygon for s in layout.shapes
             if s.polygon is not None and not s.polygon.is_empty
             and s.role in _AIRSIDE_GATE_ROLES])
        if _airside_gate_u.is_empty:
            _airside_gate_u = None
    except _GEOM_EXC:
        _airside_gate_u = None
    # We walk a generous maximum, then truncate per-portal based
    # on actual DEM at the far end so the resulting grade never
    # exceeds ``max_ramp_grade``.  The truncated length is at
    # least ``ramp_min_length_m`` so even flat-road portals get
    # a recognisable approach.  The planning grade is reduced by
    # 0.005 to leave headroom for the 0.1 m altitude rounding —
    # without it, short segments (e.g. 9 m) could round up to
    # ~4.4 % when the design grade is exactly 4 %.
    plan_grade = max(
        max_ramp_grade - TUNNEL_RAMP_GRADE_SAFETY_MARGIN, 1e-3)
    # A surface gap between two bores shorter than a full down+up ramp
    # pair cannot reach DEM and return — the bores MERGE across it (the
    # road stays below grade the whole way), so this threshold stays
    # purely KINEMATIC.  The DESIGN limit on the open-trench form
    # (``TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M``, user 2026-07-10, SPJC
    # big tunnel) applies inside the synthesizer at gap-RECORD time:
    # capping the merge threshold itself un-merged SPJC's bores and
    # minted phantom mid-gap portals whose ramps dug grooves into the
    # covered ground between the crossings.
    low_connector_max_gap_m = 2.0 * tunnel_depth_m / plan_grade
    ways_r, low_connector_gaps = _synthesize_implied_crossing_bores(
        layout, nodes_m, ways_r, excluded_way_ids,
        low_connector_max_gap_m=low_connector_max_gap_m,
        node_tags=_node_tags_r)
    way_by_id, node_to_ways = _build_surface_way_indices(ways_r)
    arm_walk_max_m = max(arm_max_length_m,
                         ramp_min_length_m,
                         tunnel_depth_m / plan_grade)
    # Helper: ground (DEM) elevation at a local-meter point.  Tunnel
    # retaining walls follow the DEM along their length (user 2026-06-13:
    # "the wall should work similar to the boundary, a chain of rects
    # following DEM elevations") so their top tracks the real ground the
    # trench is cut into, instead of a single flat apt_elev.
    def _dem_at(cx: float, cy: float) -> float | None:
        # A missing sample is ``None``, never a raise: every caller is
        # written for ``None`` (walls fall back to ``apt_elev``), but
        # ``float(None)`` raises TypeError, which ``_GEOM_EXC`` does not
        # catch — so a DEM that cannot answer took the whole emission
        # down.  Reachable since R10-1/A1 kept exactly one branch alive
        # for portals whose DEM is UNUSABLE.
        try:
            lat, lon = _m_to_ll(cx, cy)
            value = _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None
        return None if value is None else float(value)

    # Helper: airport surface elevation at (cx, cy).  Use the
    # boundary-ribbon ``node_altitudes`` (CIFP-anchored, grade-
    # clamped) when a vertex is nearby, else fall back to DEM.
    def _airport_elevation_at(cx: float, cy: float) -> float | None:
        best_d = float('inf')
        best_alt: float | None = None
        for s in layout.shapes:
            if s.role != ROLE_BOUNDARY:
                continue
            if s.ref != "airport_boundary":
                continue
            if not s.node_altitudes:
                continue
            try:
                rcoords = list(s.polygon.exterior.coords)
            except _GEOM_EXC:
                continue
            if rcoords and rcoords[0] == rcoords[-1]:
                rcoords = rcoords[:-1]
            for k, (vx, vy) in enumerate(rcoords):
                if k >= len(s.node_altitudes):
                    break
                d = math.hypot(vx - cx, vy - cy)
                if d < best_d:
                    best_d = d
                    best_alt = s.node_altitudes[k]
        if best_alt is not None and best_d <= 200.0:
            return float(best_alt)
        # Fall back to DEM at the point.
        try:
            lat, lon = _m_to_ll(cx, cy)
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None
    # (The old ROLE_BOUNDARY-distance portal gate lived here — retired
    # 2026-07-04, see the airside-pavement gate in the portal loop.)
    excluded = excluded_way_ids or set()
    # Identity-set of shapes that exist BEFORE this pass emits anything.
    # The under-pavement clip below (PAVEMENT-OVERLAP CLIP) must act
    # ONLY on pieces THIS pass emitted — but it cannot use a captured
    # start INDEX, because the boundary-coordination pass between emit
    # and clip rebuilds ``layout.shapes`` (drops empty ribbon pieces,
    # splits MultiPolygon results) and SHIFTS every index.  On LMML
    # that net-removed 23 shapes, so the first 23 tunnel pieces fell
    # below the stale index and skipped the clip — leaving ramps and
    # flat tunnel walls overlapping the apron.  Identity is stable:
    # the rebuild keeps tunnel pieces by object reference (only
    # ROLE_BOUNDARY shapes are replaced).
    _pre_emit_ids = {id(s) for s in layout.shapes}
    _other_road_lines, _other_road_tree, _tunnel_all_nodes = (
        _build_adjacent_road_index(ways_r, nodes_m,
                                   skip_if_adjacent_road))
    # R10-1/A6 cover evidence.  The PAVEMENT union deliberately excludes
    # ``building`` — ``_AIRSIDE_GATE_ROLES`` carries it for the
    # under-pavement drop, but here building-cover and pavement-cover are
    # the two sides of the discriminator and folding one into the other
    # would collapse it.
    try:
        _building_u = unary_union(
            [s.polygon for s in layout.shapes
             if s.role == ROLE_BUILDING and s.polygon is not None
             and not s.polygon.is_empty])
        if _building_u.is_empty:
            _building_u = None
    except _GEOM_EXC:
        _building_u = None
    try:
        _pavement_u = unary_union(
            [s.polygon for s in layout.shapes
             if s.role in _TUNNEL_COVER_PAVEMENT_ROLES
             and s.polygon is not None and not s.polygon.is_empty])
        if _pavement_u.is_empty:
            _pavement_u = None
    except _GEOM_EXC:
        _pavement_u = None
    # R20-2b: the aircraft-transit pavement every run stops at.  Built
    # here (the gatherer has no layout) from the SAME role set the ramp
    # cut and the ramp safety floor read, so a ramp cannot stop at one
    # definition of "taxiway" and be judged against another.
    try:
        _transit_u = unary_union(
            [s.polygon for s in layout.shapes
             if s.role in _TUNNEL_PROTECTED_TRANSIT_ROLES
             and s.polygon is not None and not s.polygon.is_empty])
        if _transit_u.is_empty:
            _transit_u = None
    except _GEOM_EXC:
        _transit_u = None
    # §T3.1's "the airport's own bore" cover: runway / apron / taxiway
    # pavement.  Built here, from the SAME layout shapes the cover
    # evidence above reads, so the exemption and the admission cannot
    # disagree about what "airside pavement" is.
    try:
        _own_bore_cover_u = unary_union(
            [s.polygon for s in layout.shapes
             if s.role in _TUNNEL_OWN_BORE_COVER_ROLES
             and s.polygon is not None and not s.polygon.is_empty])
        if _own_bore_cover_u.is_empty:
            _own_bore_cover_u = None
    except _GEOM_EXC:
        _own_bore_cover_u = None
    # THE VETO, COMPUTED AFTER ITS EVIDENCE (§T3.1): the scoping needs
    # the airside gate union and the own-bore cover union, so the call
    # sits below them.  Nothing between the index build and here reads
    # ``_system_veto``.
    _veto_detail: dict = {}
    _system_veto = _compute_tunnel_system_veto(
        ways_r, nodes_m, excluded, adjacent_road_dist_m,
        skip_if_adjacent_road, _other_road_lines,
        _other_road_tree, _tunnel_all_nodes,
        airside_gate_union=_airside_gate_u,
        own_bore_cover_union=_own_bore_cover_u,
        veto_detail=_veto_detail)
    _passthrough_findings: list = []
    portal_data = _gather_portal_walks(
        ways_r, nodes_m, way_by_id, node_to_ways, excluded,
        _system_veto, _big_way_ids, _airside_gate_u,
        max_boundary_dist_m, arm_walk_max_m, carriageway_width_m,
        _airport_elevation_at, _m_to_ll, dem, tile_lat, tile_lon,
        tunnel_depth_m, plan_grade, ramp_min_length_m,
        building_union=_building_u, pavement_union=_pavement_u,
        transit_union=_transit_u,
        passthrough_findings=_passthrough_findings,
        veto_detail=_veto_detail,
        dem_cut_provenance=_dem_cut_provenance(layout, dem))
    if _passthrough_findings:
        try:
            _existing = list(
                getattr(layout, "tunnel_passthrough_findings", None)
                or [])
            _existing.extend(_passthrough_findings)
            layout.tunnel_passthrough_findings = _existing
        except (AttributeError, TypeError):
            pass
    # Crossing OWNERSHIP (user 2026-07-10): where Feature B claims a
    # crossing (classified deck bridge or tunnel-portal pair), this
    # legacy machinery yields the WHOLE road — a portal whose tunnel
    # way or surface walk touches an owned region is dropped before
    # any dedup/cluster work.  Plan-space plate yield downstream is
    # NOT enough: the surviving approach pieces outside the plates
    # carried DEM values that dragged the mesh beside hard-pinned
    # plates (measured KBNA, taxiway-L and the runway-02C portals).
    _owned_union = _classifier_owned_crossing_union(layout)
    if _owned_union is not None and portal_data:
        _tunnel_way_lines: dict = {}
        for _w_id, _w_refs, _w_tags in ways_r:
            if _w_tags.get("tunnel") not in PORTAL_TUNNEL_VALUES:
                continue
            _way_points = [nodes_m[n] for n in _w_refs if n in nodes_m]
            if len(_way_points) >= 2:
                try:
                    _tunnel_way_lines[_w_id] = LineString(_way_points)
                except _GEOM_EXC:
                    continue
        _kept_portals = []
        _n_owned = 0
        for _portal_entry in portal_data:
            _way_line = _tunnel_way_lines.get(_portal_entry[1])
            _walk_line = None
            try:
                if len(_portal_entry[2]) >= 2:
                    _walk_line = LineString(_portal_entry[2])
            except _GEOM_EXC:
                _walk_line = None
            _owned_hit = False
            for _geometry in (_way_line, _walk_line):
                if _geometry is None:
                    continue
                try:
                    if _geometry.intersects(_owned_union):
                        _owned_hit = True
                        break
                except _GEOM_EXC:
                    continue
            if _owned_hit:
                _n_owned += 1
                continue
            _kept_portals.append(_portal_entry)
        if _n_owned:
            UI.vprint(
                1,
                f"  [tunnel] {_n_owned} legacy portal(s) dropped — "
                "Feature B owns the crossing (classified bridge / "
                "tunnel-portal records)")
            portal_data = _kept_portals
    # A low-connector gap inside an OWNED crossing stays COVERED (user
    # 2026-07-14): the classified portal pair says the road is a deep
    # bore there — digging the gap open leaves holes with no objects
    # over them (measured KBNA: two dug-open gaps exactly on the line
    # between the runway-02C portal mouths).
    if _owned_union is not None and low_connector_gaps:
        _kept_gaps = []
        _n_covered = 0
        for (_gap_line, _corridor_width_m) in low_connector_gaps:
            _inside_owned = False
            try:
                _inside_owned = _gap_line.intersects(_owned_union)
            except _GEOM_EXC:
                _inside_owned = False
            if _inside_owned:
                _n_covered += 1
                continue
            _kept_gaps.append((_gap_line, _corridor_width_m))
        if _n_covered:
            UI.vprint(
                1,
                f"  [tunnel] {_n_covered} low-connector gap(s) kept "
                "COVERED — Feature B owns the crossing (tunnel-portal "
                "pair / classified bridge)")
            low_connector_gaps = _kept_gaps
    # Flat low-connector corridors supersede any portal starting
    # inside them (cross-way facing portals the per-way gap merge
    # cannot see — user 2026-07-04, KDFW).
    _low_corridors = _low_connector_corridors(low_connector_gaps)
    portal_data = _suppress_portals_in_low_corridors(
        portal_data, _low_corridors)
    if not portal_data:
        return 0
    portal_data = _dedup_portal_walks(portal_data, nodes_m,
                                      portal_cluster_dist_m)
    if not portal_data:
        return 0
    # A3: distinct facing entrances both survive dedup, and the roadway
    # BETWEEN two same-road mouths is one lowered stretch — flagged per
    # portal (index 14) so the cluster emit withholds ramp-to-grade
    # there, and laid as an open corridor after the clusters.
    _facing_idx, _facing_pairs = _facing_same_road_portals(
        portal_data, way_by_id, TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M,
        min_gap_m=portal_cluster_dist_m)
    if _facing_idx:
        portal_data = [
            (tuple(_pd) + (None,) * max(0, 14 - len(_pd))
             + (_i in _facing_idx,))
            for _i, _pd in enumerate(portal_data)]
        # ONE DEPTH PER FACING SYSTEM (owner: "the whole area is lowered
        # … and flat between the two mouths").  Each portal's own floored
        # grade is a per-end reading — one end's DEM found the trench,
        # the other's was clamped up to the clearance floor — and letting
        # them stand gave a corridor sloping 1.61 m between two mouths
        # the owner describes as one lowered stretch.  The pair takes the
        # DEEPER reading, mouths included, so the mouths agree and the
        # interpolation between them is flat by construction.
        portal_data = [list(_pd) for _pd in portal_data]
        for (_i, _j) in _facing_pairs:
            _ga = _mouth_grade_with_clearance(
                portal_data[_i][9], portal_data[_i][11])
            _gb = _mouth_grade_with_clearance(
                portal_data[_j][9], portal_data[_j][11])
            if _ga is None or _gb is None:
                continue
            _joint = min(float(_ga), float(_gb))
            portal_data[_i][9] = _joint
            portal_data[_j][9] = _joint
        portal_data = [tuple(_pd) for _pd in portal_data]
    clusters = _cluster_portals(portal_data, nodes_m,
                                portal_cluster_dist_m)
    # Per-cluster: build cap + arm walls + ramp chain.
    exclusion_zones: list[Polygon] = []
    n_emitted = 0
    half_wall_w = retaining_wall_width_m / 2.0
    # R8-3 (round-8 VHHH close-out): ONE AUTHORITY PER TUNNEL.  Built
    # ONCE per airport — it unions every classified object-tunnel body
    # that actually cut a trench — and handed to every cluster.
    _object_trench_u = _object_trench_body_union(layout)
    _object_trench_stats: dict = {}
    # id(shape) → source OSM way id of the cluster that emitted it, for
    # the ruling-4 safety-floor log line (BuiltShape carries no way id).
    _ramp_way_ids: dict[int, object] = {}
    for cl in clusters:
        _n_before = len(layout.shapes)
        n_emitted += _emit_portal_cluster(
            cl, portal_data, nodes_m, layout, exclusion_zones,
            carriageway_width_m, tunnel_depth_m, wall_gap_m,
            retaining_wall_width_m, half_wall_w, _dem_at,
            airside_gate_union=_airside_gate_u,
            object_trench_union=_object_trench_u,
            object_trench_yield_stats=_object_trench_stats)
        try:
            _cl_wid = portal_data[cl[0]][1]
        except (IndexError, TypeError):
            _cl_wid = None
        if _cl_wid is not None:
            for _s9 in layout.shapes[_n_before:]:
                if getattr(_s9, "ref", "") == "tunnel_ramp":
                    _ramp_way_ids[id(_s9)] = _cl_wid
    if _object_trench_stats:
        UI.vprint(
            1,
            f"  [tunnel] R8-3 object-trench yield: "
            f"{_object_trench_stats.get('dropped', 0)} OSM ramp/wall "
            f"piece(s) dropped and "
            f"{_object_trench_stats.get('clipped', 0)} clipped inside "
            f"classified object-tunnel bodies (+"
            f"{_OBJECT_TRENCH_YIELD_MARGIN_M:g} m) — the object trench is "
            f"the rendered truth there.")
    # A3's open cut runs AFTER the clusters so the corridor is cut into
    # the walls its own mouths just emitted, and BEFORE finalize so the
    # ruling-4 pavement cut and the R10-2 patch-wide cut see it.
    if _facing_pairs:
        _emit_facing_corridors(
            layout, portal_data, _facing_pairs, exclusion_zones,
            wall_gap_m, retaining_wall_width_m, _dem_at)
    _emit_low_corridor_connectors(
        layout, _low_corridors, exclusion_zones,
        _airside_gate_u, _airport_elevation_at, _dem_at,
        tunnel_depth_m, wall_gap_m, retaining_wall_width_m)
    # R14-1/A-1: THE PAVED AREA IS THE CORRIDOR.  Claim the road
    # pavement covering this system's open cut and re-profile it, then
    # stand down the synthetic rectangles it replaces.  Runs after the
    # cluster/corridor emit (the regions are known) and before finalize
    # (so the R10-2 cuts and the pavement clip see the claim).
    _n_claim, _claimed, _claim_corridor = _claim_road_pavement(
        layout, portal_data, _facing_pairs, wall_gap_m)
    # THE CLAIM SET IS PUBLISHED, NOT RE-DERIVED (spec
    # ``tunnel-corridor-node-book-exclusion-spec.md`` §2): the
    # finalize-stage chord limiter excludes every ring with a node
    # inside THIS set from its unified node book, so a road ring's
    # bench value cannot travel across the cut boundary into the bore's
    # own below-grade floor.
    publish_tunnel_open_cut_claim_set(layout, _claimed)
    if _claimed:
        # THE STAND-DOWN JUDGES THE CORRIDOR, NOT THE SHAPE (mouth-D
        # fix, RULINGS 2026-08-25e; gated with the rest of that round).
        _stand_down_synthetic_over_claimed(
            layout,
            (_claim_corridor
             if (_claim_corridor
                 and os.environ.get(_PORTAL_CORRIDOR_CLAIM_ENV, "1") == "1")
             else _claimed),
            _pre_emit_ids)
    # RULINGS 2026-08-25e / spec ``portal-corridor-claim-spec.md`` §2.
    # R14-1 has now claimed every ROAD surface it may.  What remains is
    # the mouth-D class: a corridor landing on pavement R14-1 may not
    # claim, which the finalize removers below then delete the ramp for.
    # The ramp claims that corridor's own FOOTPRINT instead — the host
    # is cut, keeps its role and the rest of its area, and stops
    # covering the alignment.
    audit_tunnel_claim_drift(layout, "portal-emit (right after the claim)")
    _n_corr = _claim_portal_corridor_footprint(
        layout, portal_data, _facing_pairs, wall_gap_m, _pre_emit_ids)
    # §2.3 / §T6.1: every claimed corridor now walls itself, both sides,
    # ends wrapped — the R2 node-split wall class through the host.  Runs
    # after BOTH claim authorities so it sees every claimed footprint,
    # and before finalize so the R10-2 cuts see the walls.
    _wall_claimed_corridors(
        layout, exclusion_zones, _pre_emit_ids,
        wall_gap_m, retaining_wall_width_m, _dem_at,
        float(_airport_elevation_at(0.0, 0.0) or 0.0))
    if _n_corr:
        # THE GATE MUST SEE THE CUT.  ``_airside_gate_u`` was built
        # before the corridor claim, so a strip that is no longer host
        # pavement would still read as covering the ramp above it — the
        # very deletion this claim exists to stop.  Same role set, same
        # expression, current geometry (the union's own comment requires
        # the sets stay identical).
        try:
            _airside_gate_u = unary_union(
                [s.polygon for s in layout.shapes
                 if s.polygon is not None and not s.polygon.is_empty
                 and s.role in _AIRSIDE_GATE_ROLES])
            if _airside_gate_u.is_empty:
                _airside_gate_u = None
        except _GEOM_EXC:                              # pragma: no cover
            pass
    try:
        _protected_u = unary_union(
            [s.polygon for s in layout.shapes
             if s.role in _TUNNEL_PROTECTED_TRANSIT_ROLES
             and s.polygon is not None and not s.polygon.is_empty])
        if _protected_u.is_empty:
            _protected_u = None
    except _GEOM_EXC:
        _protected_u = None
    # ── THE TERRAIN-BASED ROAD BRIDGE DECK (RULINGS 2026-08-30d) ─────
    # HERE, and it has to be here: the deck CUTS the ramp, so §1 must be
    # confirmed while the ramp pieces still exist.  Confirm after the
    # pass and §1 would find the geometry the deck had just severed,
    # call the deck unconfirmed, stand it down, and leave the cut with
    # nothing spanning it.
    #
    # A confirmed terrain deck joins the PROTECTED-TRANSIT union and the
    # wall gate — the pass's own covered-stretch machinery, not a second
    # copy of it.  That is the whole amendment: over protected pavement
    # a mostly-covered ramp piece already drops and a graze is already
    # clipped to the edge, which severs the open cut inside the deck
    # footprint, keeps walls out of it, and leaves the ramp resuming at
    # both deck edges with its authored profile untouched.
    try:
        from .road_bridge_deck import confirm_and_sever as _deck_sever
        _deck_report, _deck_u = _deck_sever(layout, getattr(
            layout, "icao", "") or "")
        if _deck_u is not None:
            _protected_u = (_deck_u if _protected_u is None
                            else unary_union([_protected_u, _deck_u]))
            if _airside_gate_u is not None:
                _airside_gate_u = unary_union([_airside_gate_u, _deck_u])
            UI.vprint(1,
                f"  [bridge-deck] §3/2026-08-30d: "
                f"{_deck_report['confirmed_terrain']} terrain deck "
                f"footprint(s) joined the protected-transit union and the "
                f"wall gate — the stretch beneath each is a COVERED "
                f"STRETCH: open cut severed inside the footprint, no "
                f"walls within it, ramp resuming at both deck edges.")
        if _deck_report.get("candidates"):
            UI.vprint(1,
                f"  [bridge-deck] {_deck_report['candidates']} "
                f"candidate(s): {_deck_report['confirmed_terrain']} "
                f"terrain, {_deck_report['object_governed']} "
                f"object-governed, {_deck_report['unconfirmed']} "
                f"unconfirmed (§1), {_deck_report['refused']} refused "
                f"(§6).")
    except Exception as _deck_exc:                       # pragma: no cover
        UI.vprint(1, f"  [bridge-deck] adjudication skipped: {_deck_exc!r}")
    return _finalize_tunnel_emission(
        layout, exclusion_zones, boundary_clearance_m,
        _airside_gate_u, _pre_emit_ids, n_emitted,
        ramp_way_ids=_ramp_way_ids,
        protected_union=_protected_u,
        # Spec §2 W/G-1: the cut is the wall band's own annulus.
        ramp_cut_clearance_m=wall_gap_m + retaining_wall_width_m)


def _scenery_has_bridge_objects(
        layout: "PavementLayout",
        bridge_proximity_m: float = 30.0,
        ) -> bool:
    """Return True when the X-Plane scenery pack containing
    ``layout.apt_dat_path`` places at least one taxi-bridge OBJ
    near a bridge taxi rect.

    Detection logic (per user 2026-04-29):
      1. Find the DSF for the scenery pack via
         ``O4_DSF_Reader.find_associated_dsf``.
      2. Convert it to text with DSFTool when not already cached
         (``dsf_reader.ensure_dsf_text_path`` — dump lives under the
         data root, never inside the scenery pack).
      3. Walk OBJECT_DEF lines.  Mark a def as a "bridge def" when
         its path matches ``bridge|elevated|viaduct|overpass``
         AND does NOT match ``sign|signage|trafficsign|wall|
         truss|crane`` — KPHX has 3 ``lib/g10/roadsigns/SignBridge
         *.obj`` defs that are road sign gantries, NOT taxi
         bridges, and the exclude regex filters them out.
      4. Walk OBJECT placement lines.  When a placement uses a
         "bridge def" AND its lat/lon lies within
         ``bridge_proximity_m`` of any taxi rect with
         ``is_bridge=True``, return True.

    Confirmed signal at the test set:
      KBNA  — 23 OBJECT_DEFs match ``Objects/KBNA Bridges/...``
              (KBNA_Bridge_Taxiway-L_p1..p6, KBNA_Crossing_Bridge,
              elevated_edge_twy_B, ...) — many placements within
              the bridge taxi rect → True.
      KPHX  — only ``lib/g10/roadsigns/SignBridge*`` defs which
              the exclude regex drops → False.

    Feature B gate replacement (``O4_OBJECT_BRIDGE_TERRAIN``): when the
    object-terrain classifier has run (its result cached on the layout by
    ``object_terrain_assembly.attach_bridge_classification``), that
    geometry-based bridge recognition supersedes the name-grep below — it
    catches the EDDF crossings and the Spanish-named KMCO "puente" objects
    the ``bridge|elevated|viaduct|overpass`` regex misses entirely (spec
    section 3.2, step 4).  A pack is treated as carrying its own 3D bridge
    structure when the classifier found ANY bridge record; the legacy
    name-grep runs unchanged whenever the gate is off (no cached result).
    """
    classification = _object_bridge_classification(layout)
    if classification is not None:
        return bool(classification.bridges)
    if not layout.apt_dat_path:
        return False
    bridge_rects = [s.polygon for s in layout.shapes
                     if getattr(s, "is_bridge", False)
                     and s.polygon is not None
                     and not s.polygon.is_empty]
    if not bridge_rects:
        return False
    try:
        from . import dsf_reader as _DSFR
    except _GEOM_EXC:
        return False
    dsf_path = _DSFR.find_associated_dsf(
        layout.apt_dat_path,
        layout.anchor[0], layout.anchor[1])
    if dsf_path is None or not os.path.isfile(dsf_path):
        return False
    # Shared dump cache (user ruling 2026-07-15: dumps live under the
    # data root, never next to the DSF inside the scenery pack).
    text_path = _DSFR.ensure_dsf_text_path(dsf_path)
    if text_path is None:
        return False
    BRIDGE_RE = re.compile(
        r"(?i)bridge|elevated|viaduct|overpass")
    EXCLUDE_RE = re.compile(
        r"(?i)sign|signage|trafficsign|truss|crane")
    bridge_def_idx: set = set()
    object_def_count = 0
    placements: list[tuple[int, float, float]] = []
    try:
        with open(text_path, "r", encoding="utf-8",
                  errors="replace") as f:
            for line in f:
                if line.startswith("OBJECT_DEF"):
                    parts = line.strip().split(maxsplit=1)
                    path = parts[1] if len(parts) > 1 else ""
                    if (BRIDGE_RE.search(path)
                            and not EXCLUDE_RE.search(path)):
                        bridge_def_idx.add(object_def_count)
                    object_def_count += 1
                elif line.startswith("OBJECT "):
                    tok = line.split()
                    if len(tok) >= 4:
                        try:
                            idx = int(tok[1])
                            lon = float(tok[2])
                            lat = float(tok[3])
                            placements.append((idx, lon, lat))
                        except ValueError:
                            continue
    except _GEOM_EXC:
        return False
    if not bridge_def_idx or not placements:
        return False
    # Project bridge rects to lat/lon for proximity check.  The
    # rects' polygons are in meter space anchored at the layout —
    # convert each placement to meters and test against the
    # buffered rect union.
    _to_m, _m_to_ll = _local_meter_projections(layout.anchor)
    try:
        bridge_buf = unary_union(bridge_rects).buffer(
            bridge_proximity_m)
    except _GEOM_EXC:
        return False
    for idx, lon_v, lat_v in placements:
        if idx not in bridge_def_idx:
            continue
        x, y = _to_m(lon_v, lat_v)
        if bridge_buf.contains(Point(x, y)):
            return True
    return False


def _emit_taxi_bridges(
        layout: "PavementLayout",
        dem,
        tile_lat: int,
        tile_lon: int,
        retaining_wall_width_m: float = 1.0,
        wall_gap_m: float = 0.5,
        boundary_clearance_m: float = 1.0,
        scenery_has_bridge_objects: bool = False,
        ) -> int:
    """For each taxi rect marked ``is_bridge=True``, optionally
    emit two flat retaining walls along its long edges at the
    rect's average elevation (the bridge deck altitude).

    Per user 2026-04-29 (KBNA vs KPHX): when the X-Plane scenery
    pack ALREADY contains a 3D taxi-bridge OBJ (detected by
    ``_scenery_has_bridge_objects``, e.g. KBNA's
    ``Objects/KBNA Bridges/KBNA_Bridge_Taxiway-L_*.obj``), the
    scenery's own bridge model is the visible structure — we
    skip the wall emission entirely so we don't double up.  When
    the scenery has NO bridge OBJ (KPHX), our emitted walls
    provide the only visible side-face structure.

    No end-cap walls — the bridge's short edges connect to
    adjacent taxis or junctions at apt_elev (the deck continues
    onto the surrounding airport surface), so an end-cap would
    visually block that join.

    Boundary coordination: when a bridge rect lies inside the
    airport boundary (typical at SPJC / KBNA / KPHX), the walls
    are also inside.  The inside-airport portion of (rect ∪
    walls) gets buffered by ``boundary_clearance_m`` (0.5 m) and
    subtracted from each ``ROLE_BOUNDARY`` shape — same pattern
    as ``_emit_tunnel_portals``.

    Returns the number of bridge rects whose walls were emitted
    (0 when the scenery already has bridge OBJs).
    """
    from .pipeline import _load_osm_big_roads
    bridge_shapes = [s for s in layout.shapes
                     if getattr(s, "is_bridge", False)
                     and s.polygon is not None
                     and not s.polygon.is_empty]
    if not bridge_shapes:
        return 0
    if scenery_has_bridge_objects:
        # The scenery's own 3D bridge OBJs are the visible
        # structure.  Emit nothing here — the deck itself
        # already exists as the taxi rect, and the surrounding
        # mesh is handled by the road-approach helper.
        return 0
    n_emitted = 0
    exclusion_zones: list[Polygon] = []
    for s in bridge_shapes:
        rc = list(s.polygon.exterior.coords)
        if rc and rc[0] == rc[-1]:
            rc = rc[:-1]
        if len(rc) != 4:
            continue
        # Per ``_rect_from_axis_extended`` corner convention:
        # corners 0,3 = one short edge, corners 1,2 = other.
        # Long edges: corners (0,1) and (2,3).
        # Compute the deck elevation for the wall: average of
        # altitude_high/altitude_low on a sloped rect, or
        # altitude on a flat rect.  Walls match the deck so the
        # join is seamless.
        if (s.altitude_high is not None
                and s.altitude_low is not None):
            deck_elev = 0.5 * (s.altitude_high + s.altitude_low)
        elif s.altitude is not None:
            deck_elev = s.altitude
        else:
            # No elevation set yet — skip.  The post-elevation
            # pass calls _emit_taxi_bridges after rect altitudes
            # are filled in by the unified solver.
            continue
        for (a, b) in ((0, 1), (2, 3)):
            ax, ay = rc[a]
            bx, by = rc[b]
            ex = bx - ax
            ey = by - ay
            elen = math.hypot(ex, ey)
            if elen < 1.0:
                continue
            ux = ex / elen
            uy = ey / elen
            # Outward normal — flip if the test point is INSIDE
            # the rect.
            n_x = -uy
            n_y = ux
            mid_x = 0.5 * (ax + bx)
            mid_y = 0.5 * (ay + by)
            if s.polygon.contains(
                    Point(mid_x + n_x * 0.1,
                          mid_y + n_y * 0.1)):
                n_x = -n_x
                n_y = -n_y
            # Wall sits ``wall_gap_m`` outboard of the rect's
            # long edge, ``retaining_wall_width_m`` thick.
            inner = wall_gap_m
            outer = wall_gap_m + retaining_wall_width_m
            wc = [
                (ax + n_x * inner, ay + n_y * inner),
                (bx + n_x * inner, by + n_y * inner),
                (bx + n_x * outer, by + n_y * outer),
                (ax + n_x * outer, ay + n_y * outer),
            ]
            try:
                wall_poly = Polygon(wc)
                if not wall_poly.is_valid:
                    wall_poly = wall_poly.buffer(0)
                if (wall_poly.geom_type == "Polygon"
                        and not wall_poly.is_empty):
                    layout.shapes.append(BuiltShape(
                        polygon=wall_poly,
                        role=ROLE_RETAINING_WALL,
                        ref="bridge_wall",
                        altitude=round(float(deck_elev), 1)))
                    exclusion_zones.append(wall_poly)
            except _GEOM_EXC:
                continue
        # Track the bridge rect itself so the boundary subtraction
        # below also clears the deck area.
        exclusion_zones.append(s.polygon)
        n_emitted += 1

    # ── Deck coverage of the FULL tunnel-tagged road segment ──────
    # (user 2026-06-10, KPHX) The taxi-bridge deck is the taxi rect,
    # but the OSM road segment tagged ``tunnel`` often extends past
    # the rect's footprint — that overhang would otherwise be open
    # terrain draped over an underground road (a dirt strip between
    # the deck edge and the portal).  Emit flat deck plates at the
    # adjacent bridge's deck elevation covering every tunnel-tagged
    # segment near a bridge rect, minus the airport pavement that
    # already covers it.
    if n_emitted:
        try:
            nodes_r, ways_r = _load_osm_big_roads(
                layout.anchor[0], layout.anchor[1])
        except _GEOM_EXC:
            nodes_r, ways_r = {}, []
        _to_m, _m_to_ll = _local_meter_projections(layout.anchor)

        tunnel_lines: list[LineString] = []
        for _wid, nrefs, tags in ways_r:
            if not tags.get("highway"):
                continue
            if tags.get("tunnel", "") not in ("yes",
                                              "building_passage"):
                continue
            pts = [_to_m(lon, lat) for n in nrefs
                   if n in nodes_r
                   for (lat, lon) in (nodes_r[n],)]
            if len(pts) < 2:
                continue
            try:
                ls = LineString(pts)
            except _GEOM_EXC:
                continue
            if not ls.is_empty and ls.length >= 2.0:
                tunnel_lines.append(ls)
        if tunnel_lines:
            DECK_HALF_W_M = 12.0     # 22 m road + 1 m overhang each side
            MIN_DECK_PIECE_M2 = 10.0
            try:
                airside_cover = unary_union(
                    [sh.polygon for sh in layout.shapes
                     if sh.polygon is not None
                     and not sh.polygon.is_empty
                     and sh.role in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
                                     ROLE_PRIMARY_PARALLEL,
                                     ROLE_SECONDARY_PARALLEL,
                                     ROLE_STUB, ROLE_CROSS_CONNECTOR,
                                     ROLE_JUNCTION, ROLE_APRON,
                                     ROLE_BUILDING)])
            except _GEOM_EXC:
                airside_cover = None
            n_deck = 0
            deck_union: Polygon | None = None
            for ls in tunnel_lines:
                # Associate with the nearest bridge deck; skip tunnel
                # ways nowhere near a taxi bridge (handled by the
                # portal emitter alone).
                best = None
                best_d = 60.0
                for s in bridge_shapes:
                    try:
                        d = s.polygon.distance(ls)
                    except _GEOM_EXC:
                        continue
                    if d < best_d:
                        best_d = d
                        best = s
                if best is None:
                    continue
                if (best.altitude_high is not None
                        and best.altitude_low is not None):
                    deck_elev = 0.5 * (best.altitude_high
                                       + best.altitude_low)
                elif best.altitude is not None:
                    deck_elev = best.altitude
                else:
                    continue
                try:
                    zone = ls.buffer(DECK_HALF_W_M, cap_style=2,
                                     join_style=2)
                    if airside_cover is not None:
                        zone = zone.difference(airside_cover)
                    # Walls + bridge rects already emitted above
                    # (exclusion_zones) win their footprint — with the
                    # standard 0.5 m standoff, so the deck never shares
                    # an exact edge with a wall (the post-solve feature
                    # conformance would graft wall vertices into a
                    # coincident deck edge and bulge it into an
                    # overlap).
                    if exclusion_zones:
                        zone = zone.difference(
                            unary_union(exclusion_zones)
                            .buffer(wall_gap_m))
                    if deck_union is not None:
                        zone = zone.difference(deck_union)
                except _GEOM_EXC:
                    continue
                for g in (zone.geoms if hasattr(zone, "geoms")
                          else [zone]):
                    if (g.geom_type != "Polygon" or g.is_empty
                            or g.area < MIN_DECK_PIECE_M2):
                        continue
                    layout.shapes.append(BuiltShape(
                        polygon=g,
                        role=ROLE_TUNNEL_RAMP,
                        ref="bridge_deck",
                        altitude=round(float(deck_elev), 1)))
                    exclusion_zones.append(g)
                    n_deck += 1
                    try:
                        deck_union = (g if deck_union is None
                                      else deck_union.union(g))
                    except _GEOM_EXC:
                        pass
            if n_deck:
                UI.vprint(1,
                    f"  [pav-builder] emitted {n_deck} bridge-deck "
                    f"plate(s) covering tunnel-tagged road "
                    f"segment(s).")

    # Boundary coordination: subtract the actual (rect ∪ walls)
    # footprint, buffered by 0.5 m, from each ROLE_BOUNDARY shape.
    # Same pattern as ``_emit_tunnel_portals``.
    if exclusion_zones:
        try:
            bridge_union = unary_union(exclusion_zones)
        except _GEOM_EXC:
            bridge_union = None
        if bridge_union is not None and not bridge_union.is_empty:
            try:
                excl = bridge_union.buffer(boundary_clearance_m)
                kept_shapes: list[BuiltShape] = []
                for s in layout.shapes:
                    if s.role != ROLE_BOUNDARY:
                        kept_shapes.append(s)
                        continue
                    try:
                        _old_ring = list(s.polygon.exterior.coords)
                    except _GEOM_EXC:
                        _old_ring = []
                    if (_old_ring
                            and _old_ring[0] == _old_ring[-1]):
                        _old_ring = _old_ring[:-1]
                    _old_alts = (list(s.node_altitudes)
                                  if s.node_altitudes else None)
                    try:
                        new_poly = s.polygon.difference(excl)
                    except _GEOM_EXC:
                        kept_shapes.append(s)
                        continue
                    if new_poly.is_empty:
                        continue
                    if new_poly.geom_type == "Polygon":
                        s.polygon = new_poly
                        resampled = _resample_node_altitudes_nn(
                            new_poly, _old_ring, _old_alts)
                        if resampled is not None:
                            s.node_altitudes = resampled
                        kept_shapes.append(s)
                    elif new_poly.geom_type == "MultiPolygon":
                        for g in new_poly.geoms:
                            if (g.geom_type != "Polygon"
                                    or g.is_empty
                                    or g.area < 5.0):
                                continue
                            resampled = _resample_node_altitudes_nn(
                                g, _old_ring, _old_alts)
                            kept_shapes.append(BuiltShape(
                                polygon=g, role=s.role,
                                ref=s.ref,
                                altitude=(s.altitude
                                          if resampled is None
                                          else None),
                                node_altitudes=resampled))
                layout.shapes = kept_shapes
            except _GEOM_EXC:
                pass
    return n_emitted


# ---------------------------------------------------------------------------
# Feature B — object-derived depressed-road corridors (spec section 3.2)
#
# When the object-terrain classifier has run (gate O4_OBJECT_BRIDGE_TERRAIN,
# result cached on the layout), the depressed corridor under a DECK_CARRIED
# taxiway bridge is re-sourced from the OBJECT'S OWN geometry — deck
# footprint, deck elevation, girder clearance — rather than inferred from an
# ``is_bridge`` taxi rect + OSM proximity.  TERRAIN_CARRIED and
# PROFILE_CARRIED spans (pavement drapes across, solved continuous) SUPPRESS
# corridor emission inside their footprints.  All of this is dormant with
# the gate off (no cached classification ⇒ every path below is skipped and
# the legacy emitter is byte-identical).
# ---------------------------------------------------------------------------

def _object_bridge_classification(layout):
    """The cached :class:`object_terrain_features.ClassificationResult`, or
    ``None`` when feature B is off or the assembler did not run.  Gated on
    the live config flag so a flipped env/monkeypatched gate is honoured."""
    if not _CFG.OBJECT_BRIDGE_TERRAIN:
        return None
    return getattr(layout, _OBJECT_BRIDGE_CLASSIFICATION_ATTRIBUTE, None)


def _object_bridge_road_networks(layout):
    """The cached sibling DSF road networks (``[]`` when none discovered)."""
    return getattr(layout, _OBJECT_BRIDGE_ROAD_NETWORKS_ATTRIBUTE, None) or []


def _bridge_deck_elevation_m(bridge, dem, tile_lat, tile_lon):
    """Absolute deck-top elevation for a bridge record.

    ``absolute_deck_elevation_m`` (KBNA's OBJECT_MSL fixtures) when present;
    otherwise the terrain elevation sampled at the anchor plus the deck's
    effective crest height ``deck_top_y_m`` (spec section 3.2 step 1).

    **Anchor-datum caveat:** with no MSL fixture the datum is the DEM value
    at the single placement anchor — a proxy for the solved terrain there.
    The solved pavement network may differ by the solver's grading; this is
    the same one-sampled-anchor-point datum every object-terrain family
    lives with (spec section 3.4 anchor caution).  ``None`` when the DEM
    cannot be sampled."""
    if bridge.absolute_deck_elevation_m is not None:
        return float(bridge.absolute_deck_elevation_m)
    anchor_longitude, anchor_latitude = bridge.anchor_longitude_latitude
    try:
        datum = _sample_dem(
            dem, tile_lat, tile_lon, anchor_latitude, anchor_longitude
        )
    except _GEOM_EXC:
        return None
    if datum is None or datum != datum:
        return None
    return float(datum) + float(bridge.deck_top_y_m)


def _bridge_corridor_floor_m(bridge, deck_elevation_m):
    """The depressed-corridor floor elevation under a deck-carried span —
    GEOMETRY-DRIVEN per amendment A10: **floor = absolute deck elevation −
    hard-deck height above anchor terrain** (`deck_top_y_m`), which is the
    anchor-terrain datum the object was authored against.  KBNA
    calibration: 167.0 − 5.99 ≈ 161.0, matching the author mesh exactly;
    the previous clearance-driven floor (girder − 5.1) over-dug by ~0.9 m.

    The clearance constant is a CHECK, not the driver:
    ``config.BRIDGE_ROAD_CLEARANCE_MINIMUM_M`` (4.2, the measured
    in-the-wild girder clearance) is the validator's acceptance bound on
    floor-to-girder — see :func:`_bridge_girder_underside_m` and the
    emission-time warning in the corridor emitter."""
    return float(deck_elevation_m) - float(bridge.deck_top_y_m)


def _bridge_girder_underside_m(bridge, deck_elevation_m):
    """Absolute elevation of the clearance-limiting underside plane
    (girder line; the slab-underside ``ceiling_y_m`` as fallback), or
    ``None`` when the object exposes no underside plane.  Used by the
    corridor clearance CHECK (amendment A10: floor-to-girder must reach
    ``config.BRIDGE_ROAD_CLEARANCE_MINIMUM_M``), never by the floor
    computation."""
    underside = bridge.clearance_underside_y_m
    if underside is None:
        underside = bridge.ceiling_y_m
    if underside is None:
        return None
    return float(deck_elevation_m) - (
        float(bridge.deck_top_y_m) - float(underside)
    )


def _bridge_is_road_carried(bridge, layout, to_meters):
    """Road-overpass discriminator (stage 2b; KBNA Crossing_Bridge class):
    a deck-carried structure whose deck carries a ROAD, not a taxi/truck
    route — NO layout pavement or service shape crosses its deck
    footprint (measured: the nearest pavement to Crossing_Bridge is
    176 m away; every true taxi/truck bridge has pavement or a truck
    strip on the deck axis).  Terrain must NOT rise to a road deck: no
    abutment pins, no causeway, no object-sourced corridor — the
    existing road machinery owns the road beneath.  ``False`` when no
    layout is available (pure-classifier contexts cannot discriminate)."""
    if layout is None or to_meters is None:
        return False
    from .layout import ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION
    crossing_roles = _BRIDGE_PIN_ROLES | {
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
    }
    footprint = _bridge_footprint_meters(bridge, to_meters)
    if footprint is None:
        return False
    reach_band = footprint.buffer(
        float(_CFG.BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M)
    )
    # PRIMARY route evidence (stage 2b iteration 4): the RAW apt.dat
    # routing rows — 1202 taxi edges + 1206 truck edges — cached by the
    # assembler as layout-meter polylines.  The routing GRAPH says what
    # drives over the deck; neither emitted shapes (the Murfreesboro
    # truck strips end 36.7-60.9 m short) nor the QUALIFIED centerline
    # set (the Murfreesboro truck runs are disqualified before reaching
    # ``apt_taxi_centerlines`` — measured: 0 qualified centerlines
    # versus 3/5 raw truck edges in the two decks' reach bands, 3 raw
    # taxi edges at taxiway-L, zero of anything at the Crossing_Bridge
    # road overpass) carry the truth.
    for line in getattr(
            layout, _OBJECT_BRIDGE_ROUTE_LINES_ATTRIBUTE, None) or []:
        if line is None or line.is_empty:
            continue
        try:
            if line.intersects(reach_band):
                return False
        except _GEOM_EXC:
            continue
    # Secondary evidence: the qualified centerline set (for layouts
    # whose apt.dat carries no routing rows but centerlines exist).
    for centerline in getattr(layout, "apt_taxi_centerlines", None) or []:
        line = getattr(centerline, "line", None)
        if line is None or line.is_empty:
            continue
        try:
            if line.intersects(reach_band):
                return False
        except _GEOM_EXC:
            continue
    # Tertiary evidence: a pavement/service shape crossing or ending
    # within the pin capture band of the footprint (the KBNA cut: the
    # pack severs taxiway-L pavement 9.6 m short of the abutments).
    for shape in layout.shapes:
        if shape.role not in crossing_roles:
            continue
        if shape.polygon is None or shape.polygon.is_empty:
            continue
        try:
            if shape.polygon.intersects(reach_band):
                return False
        except _GEOM_EXC:
            continue
    return True


def _ambiguous_span_promoted_by_routes(bridge, layout, to_meters):
    """Dead-band AMBIGUOUS rescue (user 2026-07-17, KBNA Taxiway-L).

    The contract classifier's coverage dead band exists because partial
    mid-deck pavement coverage cannot say whether pavement drapes across
    (terrain-carried) or is cut at the abutments (deck-carried).  The
    KBNA border-line pavement feature (2026-07-16) pushed Taxiway-L's
    mid-deck coverage from ~0 to 0.20 — its wide ``.lin`` taxiway
    border runs across the deck — flipping the span from DECK_CARRIED
    to AMBIGUOUS and silently refusing the whole corridor treatment
    (trench, causeway, pins, approaches: the user-visible "underpass
    trench missing").

    The apt.dat ROUTING GRAPH is the truth about what drives over a
    deck (the ``_bridge_is_road_carried`` doctrine, tiers 1+2: raw
    1202/1206 routing rows, then qualified centerlines — NEVER the
    pavement-proximity tier, because nearby draped pavement is exactly
    what created the ambiguity).  A dead-band AMBIGUOUS span with a
    genuine hard deck and a taxi/truck route crossing it is a taxi
    bridge: promote to the corridor set.  High-coverage AMBIGUOUS
    (the flat-deck-with-draped-pavement contradiction) stays refused
    per ruling R5.
    """
    from .object_terrain_features import (
        BRIDGE_CONTRACT_PAVEMENT_COVERAGE_DECK_CARRIED_MAX,
        BRIDGE_CONTRACT_PAVEMENT_COVERAGE_TERRAIN_CARRIED_MIN,
        CONTRACT_EVIDENCE_PAVEMENT_COVERAGE,
        DECK_HARDNESS_HARD_DECK,
    )
    if layout is None or to_meters is None:
        return False
    if bridge.deck_hardness != DECK_HARDNESS_HARD_DECK:
        return False
    if bridge.contract_evidence != CONTRACT_EVIDENCE_PAVEMENT_COVERAGE:
        return False
    coverage = bridge.pavement_coverage_fraction
    if coverage is None:
        return False
    if not (BRIDGE_CONTRACT_PAVEMENT_COVERAGE_DECK_CARRIED_MAX
            < float(coverage)
            < BRIDGE_CONTRACT_PAVEMENT_COVERAGE_TERRAIN_CARRIED_MIN):
        return False
    footprint = _bridge_footprint_meters(bridge, to_meters)
    if footprint is None:
        return False
    try:
        reach_band = footprint.buffer(
            float(_CFG.BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M))
    except _GEOM_EXC:
        return False
    for line in getattr(
            layout, _OBJECT_BRIDGE_ROUTE_LINES_ATTRIBUTE, None) or []:
        if line is None or line.is_empty:
            continue
        try:
            if line.intersects(reach_band):
                return True
        except _GEOM_EXC:
            continue
    for centerline in getattr(layout, "apt_taxi_centerlines", None) or []:
        line = getattr(centerline, "line", None)
        if line is None or line.is_empty:
            continue
        try:
            if line.intersects(reach_band):
                return True
        except _GEOM_EXC:
            continue
    return False


def _detect_tunnel_portal_pairs(layout, dem, tile_lat, tile_lon):
    """Pair classified structures that are the two PORTALS of one buried
    tunnel (user ruling 2026-07-10, the KBNA runway-02C class) and cache
    the result on the layout.

    A pair is two would-be corridor records (deck-carried or cosmetic)
    whose centroid spacing lies inside the configured window, whose
    connecting segment aligns with BOTH objects' headings — side-by-side
    parallel decks fail this test because their connecting segment runs
    PERPENDICULAR to their headings — and whose connecting ground rises
    to at least the lower portal's top plus the buried margin (the hill
    that carries the runway over the bore).

    Portals never receive bridge treatment: no deck-end pins, no trench,
    no causeway plates, no cross-hill approaches.  Instead each mouth is
    seated at the ROAD grade so the portal object sits partly submerged
    with its bottom aligned to the road descending to it, the terrain on
    the runway side stays the natural hill (level with the object top at
    the face), and the road corridor climbs AWAY from the mouth.  For
    that, each portal record precomputes:

    * ``outward`` — unit vector away from the partner (out of the hill);
    * ``mouth_floor_m`` — MINIMUM digital-elevation-model sample along
      the outward ray (the descending road's grade at the face, robust
      against the embankment skirt inflating near samples);
    * ``footprint`` — the deck footprint in layout meters.

    Returns the cached pair list (computed once per layout; empty when
    the gate is off, the digital elevation model is unavailable, or no
    pair qualifies)."""
    cached = getattr(layout, _TUNNEL_PORTAL_PAIRS_ATTRIBUTE, None)
    if cached is not None:
        return cached
    pairs: list[dict] = []
    setattr(layout, _TUNNEL_PORTAL_PAIRS_ATTRIBUTE, pairs)
    classification = _object_bridge_classification(layout)
    if classification is None or dem is None:
        return pairs
    from .object_terrain_features import (
        DECK_CARRIED, DECK_HARDNESS_COSMETIC,
    )
    to_meters, meters_to_lat_lon = _local_meter_projections(layout.anchor)
    candidates = []
    for bridge in classification.bridges:
        is_cosmetic = bridge.deck_hardness == DECK_HARDNESS_COSMETIC
        if not (is_cosmetic or bridge.contract == DECK_CARRIED):
            continue
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is None:
            continue
        candidates.append((bridge, footprint))
    # Portal-FACE candidates (user 2026-07-17, EGGW class): bare soft
    # face quads hanging below grade, recognized by the classifier as
    # ``portal_faces``.  They pair only with EACH OTHER (a face and a
    # cosmetic deck are different physical modelling conventions).
    # Owner ruling 2026-07-18: a recognized face pair OWNS its crossing
    # and receives the KBNA-style mouth/crown/collar treatment ALIGNED
    # ON THE MOUTH ANCHORS — a mapped OSM ``tunnel=yes`` way between
    # the faces is corroboration that strengthens the pair, never a
    # reason to stand down (the OSM-side emitters yield through the
    # crossing-ownership union, exactly as they do for KBNA pairs).
    #
    # A face's own horizontal projection is a sliver (a vertical quad
    # projects to its face LINE), useless for the mouth/crown split and
    # the collar — synthesize the KBNA-shaped plate footprint instead:
    # a rectangle CENTERED ON THE ANCHOR (the anchor sits on the face
    # line), spanning the face width plus a shoulder, reaching
    # half-depth outward (the mouth half) and half-depth inward (the
    # buried crown half).
    face_candidates = []
    _mapped_tunnel_lines_m: list = []
    for face in getattr(classification, "portal_faces", None) or []:
        try:
            anchor_x, anchor_y = to_meters(
                face.anchor_longitude_latitude[0],
                face.anchor_longitude_latitude[1])
            line_bearing = math.radians(
                float(getattr(face, "face_line_bearing_degrees", 0.0)))
            along = (math.sin(line_bearing), math.cos(line_bearing))
            across = (-along[1], along[0])
            half_width = (0.5 * float(face.face_width_m)
                          + float(_CFG.PORTAL_FACE_PLATE_SHOULDER_M))
            half_depth = 0.5 * float(_CFG.PORTAL_FACE_PLATE_DEPTH_M)
            footprint = Polygon([
                (anchor_x + along[0] * half_width
                 + across[0] * half_depth,
                 anchor_y + along[1] * half_width
                 + across[1] * half_depth),
                (anchor_x - along[0] * half_width
                 + across[0] * half_depth,
                 anchor_y - along[1] * half_width
                 + across[1] * half_depth),
                (anchor_x - along[0] * half_width
                 - across[0] * half_depth,
                 anchor_y - along[1] * half_width
                 - across[1] * half_depth),
                (anchor_x + along[0] * half_width
                 - across[0] * half_depth,
                 anchor_y + along[1] * half_width
                 - across[1] * half_depth),
            ])
            if not footprint.is_valid:
                footprint = footprint.buffer(0)
            if footprint.geom_type != "Polygon" or footprint.is_empty:
                continue
        except _GEOM_EXC:
            continue
        face_candidates.append((face, footprint))
    if face_candidates:
        try:
            nodes_r, ways_r, _big_ids, _ntags = (
                _load_tunnel_road_network(layout))
            for _wid, _nrefs, _tags in ways_r:
                if _tags.get("tunnel") not in TUNNEL_VALUES:
                    continue
                _pts = []
                for _nref in _nrefs:
                    if _nref in nodes_r:
                        _lat, _lon = nodes_r[_nref]
                        _pts.append(to_meters(_lon, _lat))
                if len(_pts) >= 2:
                    _mapped_tunnel_lines_m.append(LineString(_pts))
        except _GEOM_EXC:
            _mapped_tunnel_lines_m = []
    if len(candidates) < 2 and len(face_candidates) < 2:
        return pairs

    def _dem_at_meters(x, y):
        try:
            lat, lon = meters_to_lat_lon(x, y)
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None

    def _mouth_floor(footprint, outward_x, outward_y):
        centroid = footprint.centroid
        edge_distance = None
        probe = 0.0
        while probe <= 400.0:
            point = Point(centroid.x + outward_x * probe,
                          centroid.y + outward_y * probe)
            if not footprint.covers(point):
                edge_distance = probe
                break
            probe += 5.0
        if edge_distance is None:
            return None
        samples = []
        distance = 5.0
        while distance <= float(_CFG.TUNNEL_PORTAL_MOUTH_SAMPLE_RANGE_M):
            value = _dem_at_meters(
                centroid.x + outward_x * (edge_distance + distance),
                centroid.y + outward_y * (edge_distance + distance))
            if value is not None:
                samples.append(value)
            distance += 5.0
        return min(samples) if samples else None

    all_candidates = (
        [(bridge, footprint, False) for bridge, footprint in candidates]
        + [(face, footprint, True) for face, footprint in face_candidates])
    used: set[int] = set()
    for i, (bridge_i, footprint_i, is_face_i) in enumerate(all_candidates):
        if id(bridge_i) in used:
            continue
        for bridge_j, footprint_j, is_face_j in all_candidates[i + 1:]:
            if id(bridge_j) in used:
                continue
            if is_face_i != is_face_j:
                continue
            centroid_i = footprint_i.centroid
            centroid_j = footprint_j.centroid
            east = centroid_j.x - centroid_i.x
            north = centroid_j.y - centroid_i.y
            spacing = math.hypot(east, north)
            if not (float(_CFG.TUNNEL_PORTAL_PAIR_MIN_SPACING_M)
                    <= spacing
                    <= float(_CFG.TUNNEL_PORTAL_PAIR_MAX_SPACING_M)):
                continue
            segment_bearing = math.degrees(math.atan2(east, north)) % 180.0
            tolerance = float(
                _CFG.TUNNEL_PORTAL_PAIR_HEADING_TOLERANCE_DEGREES)
            if is_face_i:
                # Face pairs: a portal face parallels the STRUCTURE it
                # passes under, not the road's perpendicular (EGGW: the
                # taxiway crosses the road at ~58°), so test (a) the
                # two faces are mutually parallel — two ends of one
                # structure — and (b) the connecting segment genuinely
                # CROSSES the faces (never runs along them: side-by-
                # side faces of neighbouring structures fail here).
                line_i = float(getattr(
                    bridge_i, "face_line_bearing_degrees", 0.0)) % 180.0
                line_j = float(getattr(
                    bridge_j, "face_line_bearing_degrees", 0.0)) % 180.0
                parallel_delta = abs(line_i - line_j)
                if parallel_delta > 90.0:
                    parallel_delta = 180.0 - parallel_delta
                # Mean face line, wraparound-safe (5° and 175° must
                # average near 0, not 90).
                adjusted_j = line_j
                if abs(line_j - line_i) > 90.0:
                    adjusted_j += 180.0 if line_j < line_i else -180.0
                mean_line = (0.5 * (line_i + adjusted_j)) % 180.0
                crossing_delta = abs(segment_bearing - mean_line)
                if crossing_delta > 90.0:
                    crossing_delta = 180.0 - crossing_delta
                if parallel_delta > tolerance \
                        or crossing_delta < tolerance:
                    continue
            else:
                aligned = True
                for bridge in (bridge_i, bridge_j):
                    heading = float(bridge.heading_degrees or 0.0) % 180.0
                    delta = abs(heading - segment_bearing)
                    if delta > 90.0:
                        delta = 180.0 - delta
                    if delta > tolerance:
                        aligned = False
                        break
                if not aligned:
                    continue
            unit_x = east / spacing
            unit_y = north / spacing
            mouth_i = _mouth_floor(footprint_i, -unit_x, -unit_y)
            mouth_j = _mouth_floor(footprint_j, unit_x, unit_y)
            if mouth_i is None or mouth_j is None:
                continue
            top_i = mouth_i + float(bridge_i.deck_top_y_m or 0.0)
            top_j = mouth_j + float(bridge_j.deck_top_y_m or 0.0)
            # Buried test, two independent signals (either qualifies):
            #
            # (a) AIRSIDE PAVEMENT crosses the middle of the connecting
            #     segment — a road running between two portal structures
            #     UNDER a runway/taxiway is a tunnel by the same axiom
            #     the implied-crossing machinery rests on (roads never
            #     cross airside pavement at grade).  This signal is
            #     immune to the smoothed digital elevation model, which
            #     FLATTENS embankments near runways (measured KBNA 02C:
            #     mid-line maximum 181.45 m against portal tops 187-188 —
            #     the raster erased the hill the runway visibly sits on).
            # (b) The connecting ground rises above the lower portal's
            #     top (unsmoothed hills away from pavement).
            buried = False
            try:
                middle = LineString([
                    (centroid_i.x, centroid_i.y),
                    (centroid_j.x, centroid_j.y),
                ]).difference(
                    footprint_i.buffer(20.0)
                ).difference(footprint_j.buffer(20.0))
            except _GEOM_EXC:
                middle = None
            if middle is not None and not middle.is_empty:
                for shape in layout.shapes:
                    if (shape.role not in _BRIDGE_PIN_ROLES
                            or shape.polygon is None
                            or shape.polygon.is_empty):
                        continue
                    try:
                        if shape.polygon.intersects(middle):
                            buried = True
                            break
                    except _GEOM_EXC:
                        continue
            mid_max = None
            if not buried:
                distance = 0.0
                while distance <= spacing:
                    value = _dem_at_meters(
                        centroid_i.x + unit_x * distance,
                        centroid_i.y + unit_y * distance)
                    if value is not None and (mid_max is None
                                              or value > mid_max):
                        mid_max = value
                    distance += 10.0
                buried = mid_max is not None and mid_max >= (
                    min(top_i, top_j)
                    + float(_CFG.TUNNEL_PORTAL_PAIR_BURIED_MARGIN_M))
            if not buried:
                continue
            osm_corroborated = False
            if is_face_i and _mapped_tunnel_lines_m:
                # Owner ruling 2026-07-18: a mapped OSM bore between
                # the faces CORROBORATES the pair (it never stands the
                # pair down — the pair owns the crossing and the OSM
                # emitters yield through the crossing-ownership union).
                try:
                    connecting = LineString([
                        (centroid_i.x, centroid_i.y),
                        (centroid_j.x, centroid_j.y),
                    ]).buffer(20.0)
                    osm_corroborated = any(
                        line.intersects(connecting)
                        for line in _mapped_tunnel_lines_m)
                except _GEOM_EXC:
                    osm_corroborated = False
            pairs.append({
                "portals": (
                    {"bridge": bridge_i, "footprint": footprint_i,
                     "outward": (-unit_x, -unit_y),
                     "mouth_floor_m": mouth_i},
                    {"bridge": bridge_j, "footprint": footprint_j,
                     "outward": (unit_x, unit_y),
                     "mouth_floor_m": mouth_j},
                ),
                "spacing_m": spacing,
                "is_face": bool(is_face_i),
                "osm_corroborated": osm_corroborated,
            })
            used.add(id(bridge_i))
            used.add(id(bridge_j))
            buried_evidence = (
                "airside pavement over the body" if mid_max is None
                else f"hill to {mid_max:.1f} m")
            if osm_corroborated:
                buried_evidence += ", mapped OSM tunnel corroborates"
            UI.vprint(
                1,
                "   [object-tunnel] portal pair recognized "
                f"({spacing:.0f} m apart, {buried_evidence}, "
                f"mouth floors {mouth_i:.1f} / {mouth_j:.1f} m): "
                f"{bridge_i.object_resources} + "
                f"{bridge_j.object_resources} — bridge treatment "
                "suppressed, mouths seated at road grade",
            )
            break
    return pairs


def _tunnel_portal_ids(layout) -> set[int]:
    """Identity set of classifier records consumed as tunnel portals.
    Empty when detection has not run yet — callers then see the plain
    bridge partition (the pre-pairing behavior); the build always runs
    detection first (``build_bridge_layout_shapes``)."""
    pairs = getattr(layout, _TUNNEL_PORTAL_PAIRS_ATTRIBUTE, None) or []
    ids: set[int] = set()
    for pair in pairs:
        for portal in pair["portals"]:
            ids.add(id(portal["bridge"]))
    return ids


def _partition_bridges_for_corridors(classification, layout=None):
    """Split the classifier's bridge records into the corridor set, the
    suppression set, the refused (ambiguous) set and — with a layout to
    read routes from — the road-carried overpass set (spec section 3.2,
    stage 2b).

    * corridor — DECK_CARRIED spans, plus every cosmetic (``hard_deck``-less
      Murfreesboro-class) deck regardless of its coverage contract: trucks
      ride the terrain there so the causeway-plus-corridor is mandatory.
    * suppress — TERRAIN_CARRIED / PROFILE_CARRIED spans (pavement drapes
      across and is already solved continuous; a corridor would break it).
    * refused — AMBIGUOUS spans (ruling R5: reported, never guessed).
    * road_carried — corridor-shaped spans with NO taxi/truck route
      crossing the deck footprint (``_bridge_is_road_carried``): a road
      overpass; excluded from pins, causeway and the object-sourced
      corridor, logged, left to the existing road machinery.
    * tunnel_portals — records consumed as the paired portals of one
      buried tunnel (``_detect_tunnel_portal_pairs``): no bridge
      treatment; the mouth seating and outward corridor are emitted by
      the portal branch instead."""
    from .object_terrain_features import (
        DECK_CARRIED, TERRAIN_CARRIED, PROFILE_CARRIED, AMBIGUOUS,
        DECK_HARDNESS_COSMETIC,
    )
    to_meters = None
    portal_ids: set[int] = set()
    if layout is not None:
        to_meters, _meters_to_lat_lon = (
            _local_meter_projections(layout.anchor)
        )
        portal_ids = _tunnel_portal_ids(layout)
    corridor: list = []
    suppress: list = []
    refused: list = []
    road_carried: list = []
    tunnel_portals: list = []
    for bridge in classification.bridges:
        is_cosmetic = bridge.deck_hardness == DECK_HARDNESS_COSMETIC
        if id(bridge) in portal_ids:
            tunnel_portals.append(bridge)
        elif is_cosmetic or bridge.contract == DECK_CARRIED:
            if _bridge_is_road_carried(bridge, layout, to_meters):
                road_carried.append(bridge)
                UI.vprint(
                    1,
                    "   [object-bridge] road-carried overpass (no "
                    "taxi/truck route on the deck): "
                    f"{bridge.object_resources} — no pins, no causeway, "
                    "road machinery owns the corridor",
                )
            else:
                corridor.append(bridge)
        elif bridge.contract in (TERRAIN_CARRIED, PROFILE_CARRIED):
            suppress.append(bridge)
        elif bridge.contract == AMBIGUOUS:
            if _ambiguous_span_promoted_by_routes(
                    bridge, layout, to_meters):
                corridor.append(bridge)
                UI.vprint(
                    1,
                    "   [object-bridge] dead-band AMBIGUOUS span "
                    "promoted to corridor (taxi/truck route crosses "
                    "the hard deck; partial coverage is draped "
                    f"decoration): {bridge.object_resources}",
                )
            else:
                refused.append(bridge)
    return corridor, suppress, refused, road_carried, tunnel_portals


def pavement_cut_roles(include_groundside: bool = False) -> frozenset:
    """The shape roles a footprint cut removes.

    The base set is R8's: airside pavement plus service roads/junctions.
    ``include_groundside`` adds LANDSIDE pavement, which ruling R13 needs
    and R8 does not — a hard deck seats flush in the airside network,
    while an open pit can sit anywhere, and at OTHH two of the six
    drainage basins are buried by groundside pavement rather than apron
    (Drainage_02 100 % of its body, Drainage_06 4 155 of 5 121 m²).
    R8's scope is deliberately left alone."""
    from .layout import (
        ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
    )
    roles = _BRIDGE_PIN_ROLES | {ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION}
    if include_groundside:
        roles = roles | {ROLE_GROUNDSIDE_PAVEMENT}
    return frozenset(roles)


def cut_pavement_over_footprint(layout, footprint, cut_roles=None) -> int:
    """Cut every pavement shape in ``cut_roles`` by an object footprint
    that OWNS the surface there.  Solved per-vertex values on the
    surviving pieces are preserved by nearest-neighbour resampling (the
    boundary-cut pattern above).  Returns the number of shapes cut.

    ``cut_roles`` defaults to :func:`pavement_cut_roles` with no
    groundside — R8's historical scope.

    Two rulings share this one cut — both are cases where leaving our
    pavement in place would draw a surface the pack contradicts:

    * **R8 flush seating** (hard decks, the caller below): a genuine
      ``ATTR_hard_deck`` span carries the drivable surface between the
      abutments and must sit flush, the pattern the KBNA author already
      uses in the source (auto_patch rebuilds pavement from centerlines,
      so it must repeat the cut).
    * **R13 open pits** (``object_terrain_assembly``, passing the
      groundside-inclusive set): a modelled hole open to the sky takes
      the pavement with it — there is no deck to seat flush, and pavement
      spanning the hole is what buried the OTHH drainage basins.

    Everything else keeps ruling R2 (pavement always wins): a cosmetic
    roof or deck stays under our pavement."""
    if cut_roles is None:
        cut_roles = pavement_cut_roles()
    from .road_bridge_deck import is_deck_shape as _is_deck
    n_cut = 0
    kept_shapes: list[BuiltShape] = []
    for shape in layout.shapes:
        if (shape.role not in cut_roles
                or shape.polygon is None
                or shape.polygon.is_empty):
            kept_shapes.append(shape)
            continue
        # ── §3 (RULINGS 2026-08-30c): A ROAD BRIDGE DECK IS NOT
        # CUTTABLE PAVEMENT.  The SECOND exception to R14-2/A-3, beside
        # the classified hard-deck object bridge: the deck carries the
        # road OVER the structure whose cut is asking to remove it, so
        # neither the tunnel-ramp cut nor its clearance annulus reaches
        # it.  Everything else about this cut is unchanged.
        if _is_deck(shape, layout):
            kept_shapes.append(shape)
            continue
        try:
            if not shape.polygon.intersects(footprint):
                kept_shapes.append(shape)
                continue
        except _GEOM_EXC:
            kept_shapes.append(shape)
            continue
        try:
            old_ring = list(shape.polygon.exterior.coords)
        except _GEOM_EXC:
            old_ring = []
        if old_ring and old_ring[0] == old_ring[-1]:
            old_ring = old_ring[:-1]
        old_altitudes = (
            list(shape.node_altitudes) if shape.node_altitudes else None
        )
        try:
            remainder = shape.polygon.difference(footprint)
        except _GEOM_EXC:
            kept_shapes.append(shape)
            continue
        n_cut += 1
        if remainder.is_empty:
            continue  # the shape lay entirely on the deck — removed
        parts = (
            list(remainder.geoms)
            if remainder.geom_type == "MultiPolygon" else [remainder]
        )
        for part in parts:
            if (part.geom_type != "Polygon" or part.is_empty
                    or part.area < 5.0):
                continue
            resampled = _resample_node_altitudes_nn(
                part, old_ring, old_altitudes
            )
            kept_shapes.append(BuiltShape(
                polygon=part,
                role=shape.role,
                ref=shape.ref,
                altitude=(shape.altitude if resampled is None else None),
                altitude_high=(
                    None if resampled is not None else shape.altitude_high),
                altitude_low=(
                    None if resampled is not None else shape.altitude_low),
                node_altitudes=resampled,
                is_bridge=getattr(shape, "is_bridge", False)))
    if n_cut:
        layout.shapes = kept_shapes
    return n_cut


def _bridge_footprint_meters(bridge, to_meters):
    """Project a bridge's deck footprint to a local-meter shapely polygon
    (``None`` on degenerate geometry)."""
    if bridge.deck_polygon is None:
        return None
    from .object_terrain_features import frame_polygon_to_longitude_latitude
    footprint_longitude_latitude = frame_polygon_to_longitude_latitude(
        bridge.deck_polygon, bridge.frame_origin_longitude_latitude
    )
    parts = (
        list(footprint_longitude_latitude.geoms)
        if footprint_longitude_latitude.geom_type == "MultiPolygon"
        else [footprint_longitude_latitude]
    )
    meter_polygons: list[Polygon] = []
    for part in parts:
        ring = [to_meters(lon, lat) for lon, lat in part.exterior.coords]
        if len(ring) < 3:
            continue
        try:
            polygon = Polygon(ring)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.geom_type == "Polygon" and not polygon.is_empty:
                meter_polygons.append(polygon)
        except _GEOM_EXC:
            continue
    if not meter_polygons:
        return None
    try:
        union = unary_union(meter_polygons)
    except _GEOM_EXC:
        return meter_polygons[0]
    if union.geom_type == "MultiPolygon":
        union = max(union.geoms, key=lambda geometry: geometry.area)
    return union if union.geom_type == "Polygon" else None


def _draped_road_centerlines_meters(bridge, road_networks, to_meters):
    """Fully-draped (level-0) road centerlines crossing a bridge footprint,
    from the sibling DSF road networks, as local-meter LineStrings (spec
    section 3.2 step 3 — an elevated ramp flies over on its own structure
    and is left alone; only draped roads want a depressed corridor)."""
    if bridge.deck_polygon is None or not road_networks:
        return []
    from .object_terrain_features import frame_polygon_to_longitude_latitude
    footprint_longitude_latitude = frame_polygon_to_longitude_latitude(
        bridge.deck_polygon, bridge.frame_origin_longitude_latitude
    )
    if footprint_longitude_latitude.geom_type == "MultiPolygon":
        footprint_longitude_latitude = max(
            footprint_longitude_latitude.geoms,
            key=lambda geometry: geometry.area,
        )
    ring = list(footprint_longitude_latitude.exterior.coords)
    lines: list[LineString] = []
    for network in road_networks:
        for segment in dsf_road_network.segments_crossing(network, ring):
            if not segment.is_fully_draped:
                continue
            points = [
                to_meters(point.longitude, point.latitude)
                for point in segment.shape_points
            ]
            if len(points) < 2:
                continue
            try:
                line = LineString(points)
            except _GEOM_EXC:
                continue
            if not line.is_empty and line.length >= 5.0:
                lines.append(line)
    return lines


def _dedup_parallel_road_lines(road_lines, half_width):
    """Twin carriageways give two near-coincident centerlines through one
    crossing — one full-width approach corridor each, overlapping in the
    written patch (the tunnel path's ``_dedup_portal_walks`` guard,
    applied at the road-line level).  Keep the longest line; drop any
    later line whose buffered corridor overlaps a kept corridor by more
    than half its own area."""
    kept: list = []
    kept_buffers: list = []
    for line in sorted(road_lines, key=lambda item: -item.length):
        try:
            buffered = line.buffer(half_width)
        except _GEOM_EXC:
            continue
        duplicate = False
        for other in kept_buffers:
            try:
                if (buffered.intersection(other).area
                        > 0.5 * buffered.area):
                    duplicate = True
                    break
            except _GEOM_EXC:
                continue
        if duplicate:
            continue
        kept.append(line)
        kept_buffers.append(buffered)
    return kept


def _split_portal_footprint(footprint, outward):
    """Split a paired portal's footprint at its centroid, perpendicular
    to the mouth (``outward``) direction: ``(mouth_half, buried_half,
    mouth_half_plane)``.  The mouth half faces the open road; the buried
    half faces the tunnel body under the runway; the half-plane is
    returned so the crown COLLAR can be clipped to the buried side.
    Halves may be ``None`` when the split degenerates (the caller then
    falls back to the whole footprint at road grade)."""
    try:
        centroid = footprint.centroid
        outward_x, outward_y = outward
        perpendicular_x, perpendicular_y = -outward_y, outward_x
        reach = 1000.0
        edge_a = (centroid.x + perpendicular_x * reach,
                  centroid.y + perpendicular_y * reach)
        edge_b = (centroid.x - perpendicular_x * reach,
                  centroid.y - perpendicular_y * reach)
        mouth_half_plane = Polygon([
            edge_a,
            edge_b,
            (edge_b[0] + outward_x * 2.0 * reach,
             edge_b[1] + outward_y * 2.0 * reach),
            (edge_a[0] + outward_x * 2.0 * reach,
             edge_a[1] + outward_y * 2.0 * reach),
        ])
        mouth_half = footprint.intersection(mouth_half_plane)
        buried_half = footprint.difference(mouth_half_plane)
    except _GEOM_EXC:
        return None, None, None

    def _largest_polygon(geometry):
        if geometry is None or geometry.is_empty:
            return None
        if geometry.geom_type == "Polygon":
            return geometry
        polygons = [part for part in getattr(geometry, "geoms", [])
                    if part.geom_type == "Polygon" and not part.is_empty]
        return max(polygons, key=lambda part: part.area) if polygons \
            else None

    return (_largest_polygon(mouth_half), _largest_polygon(buried_half),
            mouth_half_plane)


def _clip_collar_to_mouth_front(collar_geometry, footprint, outward):
    """Remove any collar region on the ROAD side of the mouth face
    (round-8 fact 3).

    The mouth face is the plane through ``footprint``'s forward-most
    extent along ``outward`` (the mouth->road direction), perpendicular
    to it — ``footprint`` is whichever reference polygon defines the
    face in the caller's frame (the object footprint against the pair
    axis; the emitted mouth plate against the opening axis).  The mouth
    plate and the road approaches own everything ahead of that face, so
    the collar keeps only the back and the lateral flanks up to the
    face.  The forward sweep already removes the band directly ahead of
    the footprint, but a diagonal lateral lobe can round-buffer past its
    end (measured KBNA 02C round-8 baseline: a 34 m2 collar lobe 46.7 m
    in front of the west mouth, flat at the crown elevation — a
    free-standing ~6 m face)."""
    try:
        front_extent = max(
            vertex_x * outward[0] + vertex_y * outward[1]
            for vertex_x, vertex_y in footprint.exterior.coords
        ) + 1.0
        centroid = footprint.centroid
    except _GEOM_EXC:
        return collar_geometry
    perpendicular = (-outward[1], outward[0])
    # Anchor the clip rectangle ON the footprint: project the centroid
    # onto the front line.  ``outward * front_extent`` is on the same
    # line but can sit KILOMETERS away laterally (layout meters are
    # anchored at the airport reference, not the portal), leaving the
    # finite rectangle to miss the site entirely — the exact silent
    # no-op measured at KBNA 02C (footprint 2070 m lateral of that
    # base point against a 2000 m reach).
    centroid_forward = centroid.x * outward[0] + centroid.y * outward[1]
    base = (centroid.x + outward[0] * (front_extent - centroid_forward),
            centroid.y + outward[1] * (front_extent - centroid_forward))
    reach = 2000.0
    mouth_front_plane = Polygon([
        (base[0] + perpendicular[0] * reach,
         base[1] + perpendicular[1] * reach),
        (base[0] - perpendicular[0] * reach,
         base[1] - perpendicular[1] * reach),
        (base[0] - perpendicular[0] * reach + outward[0] * reach,
         base[1] - perpendicular[1] * reach + outward[1] * reach),
        (base[0] + perpendicular[0] * reach + outward[0] * reach,
         base[1] + perpendicular[1] * reach + outward[1] * reach),
    ])
    try:
        return collar_geometry.difference(mouth_front_plane)
    except _GEOM_EXC:
        return collar_geometry


def _portal_pair_owned_polygons(pairs):
    """Plan-space region a tunnel portal pair OWNS: both portal
    footprints plus the connecting band over the buried body.  Approach
    rects must never land here (the hill carries the runway), and the
    legacy portal machinery yields the whole crossing to the pair."""
    polygons: list = []
    for pair in pairs:
        portal_a, portal_b = pair["portals"]
        polygons.append(portal_a["footprint"])
        polygons.append(portal_b["footprint"])
        centroid_a = portal_a["footprint"].centroid
        centroid_b = portal_b["footprint"].centroid
        half_width = 10.0 + 0.5 * max(
            math.sqrt(portal_a["footprint"].area),
            math.sqrt(portal_b["footprint"].area),
        )
        try:
            polygons.append(
                LineString([(centroid_a.x, centroid_a.y),
                            (centroid_b.x, centroid_b.y)]
                           ).buffer(half_width)
            )
        except _GEOM_EXC:
            continue
    return polygons


# ── R8-3: ONE AUTHORITY PER TUNNEL — OBJECTS OWN, OSM YIELDS ──────
# (docs/specs/round8-vhhh-closeout-spec.md R8-3, owner in-sim VHHH
# 1.0.232 screenshots.)  MEASURED: the emitted object trenches and the
# OSM-derived ramps/walls disagree by 2-7.6 m per structure — 58 % of
# OSM ramp area lies outside every pack body, and 61 overlapping quads
# carry -1..+5.4 m altitude conflicts.  Those are the jagged seams in
# the screenshots: two authorities grading one tunnel.
#
# THE LAW.  Where a CLASSIFIED object tunnel owns ground, the OSM tunnel
# chain YIELDS — the object trench is the rendered truth.  The owned
# region is the body-footprint union
# (``object_terrain_assembly._tunnel_footprint_longitude_latitude_parts``,
# the ONE body-outline reader) dilated by a small margin.
#
# ONLY WHERE A TRENCH EXISTS.  A classified body that emitted NO trench
# floor (too thin, fully pavement-yielded, or the uncovered ``tunnel4``
# class) owns nothing on the ground: there is no object surface there to
# be the truth, so its OSM ramps must survive untouched.  The predicate
# is therefore the EMITTED plate, not the classification — a body counts
# only when a ``ROLE_TUNNEL_TRENCH`` floor pan actually intersects it.
#
# OSM-ONLY TUNNELS (no classified object at all) emit exactly as today.

#: The margin the OSM chain yields BEYOND a classified object tunnel's
#: body outline (spec R8-3: "those bodies ⊕ a small margin (2 m)").  It
#: covers the trench rim band's own outward reach, so a ramp quad does
#: not land in the wall batter.
_OBJECT_TRENCH_YIELD_MARGIN_M = 2.0

#: A piece with at least this fraction of its area inside a classified
#: body is DROPPED rather than clipped.
_OBJECT_TRENCH_YIELD_DROP_FRACTION = 0.5


def _object_trench_body_union(layout, margin_m: float | None = None):
    """Union (layout metres) of every CLASSIFIED object-tunnel body that
    actually HAS a trench cut under it, dilated by ``margin_m``.

    ``None`` when the gate is off, nothing is classified, or no classified
    body carries an emitted floor pan — in which case the OSM tunnel chain
    is untouched, which is exactly the ``tunnel4_done`` case (a body with
    no trench must not lose its OSM ramps).
    """
    if margin_m is None:
        margin_m = _OBJECT_TRENCH_YIELD_MARGIN_M
    classification = _object_bridge_classification(layout)
    if classification is None:
        return None
    tunnels = getattr(classification, "tunnels", None) or []
    # §T1.2 — THE INDEPENDENT BELT.  A BRIDGE TRENCH IS STILL A TRENCH to
    # every consumer that asks "is this ground object-owned".  The union
    # was tunnel-only, so at LEMD's -2070 portal the object-bridge
    # corridor (``ROLE_BRIDGE_TRENCH``, ref ``object_bridge_corridor``,
    # born flat at 606.96) owned the ground while the OSM tunnel chain
    # emitted straight through it — two authorities, one patch of
    # ground, and the R8-3 yield had nothing to yield TO.  Widening it
    # here composes the two whatever the classifier called the
    # structure, so §T1.1's reclassification and this belt are
    # independent (spec: "a bridge trench is still a trench").
    from .layout import ROLE_BRIDGE_TRENCH as _ROLE_BRIDGE_TRENCH
    _widen = _obj_tunnel_compose_on()
    bridge_records = (
        (getattr(classification, "bridges", None) or []) if _widen else [])
    if not tunnels and not bridge_records:
        return None
    # THE PREDICATE: an EMITTED floor pan, not a classification.  The
    # plates are ``object_terrain_assembly.build_tunnel_layout_shapes``'s
    # own ``f"{plate_prefix}_trench"`` refs (``object_tunnel_trench`` /
    # ``object_basin_trench``), born pre-solve, so they are already in
    # ``layout.shapes`` when this legacy emitter runs (finalize).  The
    # object-bridge corridor is born the same way, in
    # ``build_bridge_layout_shapes``, under ``ROLE_BRIDGE_TRENCH``.
    _floor_roles = ((ROLE_TUNNEL_TRENCH, _ROLE_BRIDGE_TRENCH) if _widen
                    else (ROLE_TUNNEL_TRENCH,))
    floors = [
        shape.polygon for shape in layout.shapes
        if shape.role in _floor_roles
        and (str(getattr(shape, "ref", "") or "").endswith("_trench")
             or (shape.role == _ROLE_BRIDGE_TRENCH
                 and str(getattr(shape, "ref", "") or "")
                 == "object_bridge_corridor"))
        and shape.polygon is not None and not shape.polygon.is_empty
    ]
    if not floors:
        return None
    try:
        floor_union = unary_union(floors)
    except _GEOM_EXC:                                     # pragma: no cover
        return None

    from .object_terrain_assembly import _tunnel_footprint_meters_parts

    to_meters, _meters_to_lat_lon = _local_meter_projections(layout.anchor)
    bodies: list = []
    for tunnel in tunnels:
        try:
            parts = _tunnel_footprint_meters_parts(tunnel, to_meters)
        except Exception:                                 # pragma: no cover
            continue
        if not parts:
            continue
        try:
            body = unary_union(parts)
            if body.is_empty or not body.intersects(floor_union):
                continue
            bodies.append(body)
        except _GEOM_EXC:                                 # pragma: no cover
            continue
    for bridge in bridge_records:
        try:
            body = _bridge_footprint_meters(bridge, to_meters)
        except Exception:                                 # pragma: no cover
            continue
        if body is None:
            continue
        try:
            if body.is_empty or not body.intersects(floor_union):
                continue
            bodies.append(body)
        except _GEOM_EXC:                                 # pragma: no cover
            continue
    if not bodies:
        return None
    try:
        return unary_union(bodies).buffer(float(margin_m))
    except _GEOM_EXC:                                     # pragma: no cover
        return None


def _yield_piece_to_object_trench(polygon, trench_union, *,
                                  corner_shared: bool,
                                  min_area_m2: float = 0.5,
                                  stats: dict | None = None):
    """The R8-3 yield for ONE emitted OSM tunnel piece.

    Returns the polygon to emit, or ``None`` to drop it.

    ``corner_shared`` says whether this piece shares its corner NODES
    with its neighbours in the chain (every ramp quad and the fork
    throat do — see this file's "RAMP-INTERNAL CORNER AGREEMENT"
    comments).  Such a piece is DROPPED or KEPT WHOLE, never clipped: a
    clip mints new corners on the cut line whose altitude disagrees with
    what the neighbour quad offers the same shared nodes, which is the
    exact class of defect those comments were written for.  Flat,
    independently-valued pieces (the retaining-wall bands) are CLIPPED,
    so a wall that only grazes a body keeps the part outside it.
    """
    if trench_union is None or polygon is None or polygon.is_empty:
        return polygon
    try:
        if not polygon.intersects(trench_union):
            return polygon
        inside_area = polygon.intersection(trench_union).area
    except _GEOM_EXC:                                     # pragma: no cover
        return polygon
    if inside_area <= 0.0:
        return polygon
    area = polygon.area or 1.0
    if inside_area >= _OBJECT_TRENCH_YIELD_DROP_FRACTION * area:
        if stats is not None:
            stats["dropped"] = stats.get("dropped", 0) + 1
        return None
    if corner_shared:
        return polygon
    try:
        remainder = polygon.difference(trench_union)
    except _GEOM_EXC:                                     # pragma: no cover
        return polygon
    parts = [geometry for geometry in getattr(
        remainder, "geoms", [remainder])
        if geometry.geom_type == "Polygon" and not geometry.is_empty]
    if not parts:
        if stats is not None:
            stats["dropped"] = stats.get("dropped", 0) + 1
        return None
    largest = max(parts, key=lambda geometry: geometry.area)
    if largest.area < float(min_area_m2):
        if stats is not None:
            stats["dropped"] = stats.get("dropped", 0) + 1
        return None
    if stats is not None:
        stats["clipped"] = stats.get("clipped", 0) + 1
    return largest


def _classifier_owned_crossing_union(layout):
    """Union (layout meters) of every crossing Feature B owns — corridor
    deck boxes plus tunnel-portal-pair regions (footprints and the band
    over the buried body).  The legacy OSM / implied-crossing portal
    machinery yields these crossings entirely (user 2026-07-10): its
    DEM-referenced ramps otherwise land beside hard-pinned plates at
    foreign values (measured KBNA: legacy ramps at 173.9-177.2 m over
    the 167.0 m taxiway-L plates).  ``None`` when the gate is off or
    nothing is classified.  Road-carried overpasses are deliberately
    NOT owned — the road machinery keeps those (spec section 3.2)."""
    classification = _object_bridge_classification(layout)
    if classification is None:
        return None
    to_meters, _meters_to_lat_lon = _local_meter_projections(layout.anchor)
    corridor_bridges, _suppress, _refused, _road_carried, _portals = (
        _partition_bridges_for_corridors(classification, layout)
    )
    polygons: list = []
    for bridge in corridor_bridges:
        box = _bridge_deck_box_meters(bridge, layout)
        if box is None:
            box = _bridge_footprint_meters(bridge, to_meters)
        if box is not None:
            polygons.append(box)
    pairs = getattr(layout, _TUNNEL_PORTAL_PAIRS_ATTRIBUTE, None) or []
    polygons.extend(_portal_pair_owned_polygons(pairs))
    # The portal CROWN/COLLAR ring is the object's terrain story too: a
    # transition from the crown height at the object back down to the
    # surrounding ground.  Adjacent-ground bands and clearance cuts must
    # be masked off it as well, or a band welds to the collar's outer rim
    # and then cuts its own graded corridor DOWN to the law floor right
    # beside it — reinstating the very cliff the collar exists to remove
    # (measured KBNA 02C: a band dropping 6.9-7.8 m over ~1.3 m off the
    # collar's welded edge).  Own a collar-reach ring around each portal
    # footprint so those bands start OUTSIDE it, from the natural ground,
    # instead of severing the collar's feather.
    collar_ring_m = float(_CFG.TUNNEL_PORTAL_CROWN_COLLAR_M) + 2.0
    for pair in pairs:
        for portal in pair.get("portals", ()):  # type: ignore[union-attr]
            footprint = portal.get("footprint")
            if footprint is None or footprint.is_empty:
                continue
            try:
                polygons.append(footprint.buffer(collar_ring_m))
            except _GEOM_EXC:
                continue
    if not polygons:
        return None
    try:
        return unary_union(polygons)
    except _GEOM_EXC:
        return None


def _emit_object_sourced_bridge_corridors(
        layout, dem, tile_lat, tile_lon, classification, road_networks,
        road_width_m, ramp_step_m, approach_length_m):
    """Emit depressed-road corridors under DECK_CARRIED bridge spans from
    the object records, and return ``(count, suppression_polygons_meters,
    covered_polygons_meters)`` for the legacy emitter to honour.

    Road source per span (spec section 3.2 step 3): the sibling DSF road
    network's fully-draped segments crossing the footprint, else the OSM
    big-roads fallback (unchanged from legacy).  The corridor floor is
    geometry-driven (``_bridge_corridor_floor_m``, amendment A10 —
    the anchor-terrain datum, with the girder clearance CHECKED against
    ``config.BRIDGE_ROAD_CLEARANCE_MINIMUM_M``); the depressed approach
    walks extend ``config.BRIDGE_CORRIDOR_DEPRESSED_LENGTH_M`` (240 m,
    the author-mesh measurement) per side — the caller's
    ``approach_length_m`` acts only as a wider override."""
    to_meters, meters_to_lat_lon = _local_meter_projections(layout.anchor)
    (corridor_bridges, suppress_bridges, refused_bridges, _road_carried,
     _tunnel_portal_records) = (
        _partition_bridges_for_corridors(classification, layout)
    )
    suppression_polygons: list[Polygon] = []
    covered_polygons: list[Polygon] = []
    for bridge in suppress_bridges:
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is not None:
            suppression_polygons.append(footprint)
            UI.vprint(
                2,
                "   [object-bridge] corridor suppressed inside "
                f"{bridge.contract} span {bridge.object_resources}",
            )
    for bridge in refused_bridges:
        UI.vprint(
            2,
            "   [object-bridge] AMBIGUOUS span refused a corridor "
            f"(ruling R5): {bridge.object_resources}",
        )

    # Iteration 5 (audit 5): approach step rects must NEVER intrude
    # into a deck box or a causeway zone — the 240 m walks follow curved
    # interchange roads that loop BACK over the span (measured: approach
    # rects at 161-167.4 covered half the J/R centerline and both lip
    # lines, fighting the trench/causeway surfaces in the mesh).  The
    # keep-out is every corridor bridge's footprint plus its two
    # causeway zones at full cap length.
    keep_out_zones = []
    for bridge in corridor_bridges:
        footprint = _bridge_deck_box_meters(bridge, layout)
        if footprint is None:
            footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is None:
            continue
        bridge_zones = [footprint]
        centroid = footprint.centroid
        for line in _abutment_lines_layout_meters(
                bridge, layout, extension_fraction=0.0):
            midpoint = line.interpolate(0.5, normalized=True)
            outward_x = midpoint.x - centroid.x
            outward_y = midpoint.y - centroid.y
            norm = math.hypot(outward_x, outward_y)
            if norm < 1.0:
                continue
            outward_x /= norm
            outward_y /= norm
            (ax, ay), (bx, by) = list(line.coords)[0], list(line.coords)[-1]
            reach = float(_CFG.BRIDGE_CAUSEWAY_MAX_LENGTH_M)
            bridge_zones.append(Polygon([
                (ax, ay), (bx, by),
                (bx + outward_x * reach, by + outward_y * reach),
                (ax + outward_x * reach, ay + outward_y * reach),
            ]))
        try:
            bridge_keep_out = unary_union(bridge_zones)
        except _GEOM_EXC:
            keep_out_zones.extend(bridge_zones)
            continue
        # Round 10: the road-exit lane stays OPEN — a road leaving the
        # span through an abutment end descends through the causeway
        # gap, so its approach rects must be allowed in the lane while
        # the rest of the box/causeway zones stay excluded.  The trench
        # is re-excluded afterwards (its plate owns the under-span
        # ground; approaches begin outside it).
        exit_corridor = _road_exit_corridor_meters(
            bridge, layout, to_meters
        )
        if exit_corridor is not None:
            try:
                # The lane opens WIDER than the draped-carriageway
                # corridor itself (user ruling 2026-07-14c): the
                # approach ramps now run at the TRENCH width (~53 m at
                # KBNA Donelson against a 34-38 m carriageway
                # corridor), and a lane only as wide as the corridor
                # starves every rect of the wide chain.
                bridge_keep_out = bridge_keep_out.difference(
                    exit_corridor.buffer(12.0)
                )
                trench_zone = footprint.buffer(-_TRENCH_INSET_M)
                if not trench_zone.is_empty:
                    bridge_keep_out = bridge_keep_out.union(trench_zone)
            except _GEOM_EXC:
                pass
        keep_out_zones.append(bridge_keep_out)
    # Tunnel portal pairs own their footprints AND the connecting band
    # over the buried body — no approach rect may land there (the hill
    # carries the runway between the mouths).
    portal_pairs = _detect_tunnel_portal_pairs(
        layout, dem, tile_lat, tile_lon
    )
    portal_owned_polygons = _portal_pair_owned_polygons(portal_pairs)
    # User ruling 2026-07-14c: the road LANE out of each MOUTH stays
    # open (mirrors the round-10 road-exit lane for deck bridges) — the
    # first approach rect must reach the mouth plate instead of being
    # skipped for grazing the owned footprint, which left the ramps
    # stopping short of the portal.  Only the outward half opens; the
    # buried band stays fully excluded.
    mouth_lane_polygons: list = []
    for pair in portal_pairs:
        for portal in pair["portals"]:
            outward_vector = portal.get("outward")
            if outward_vector is None:
                continue
            lane_lines = _draped_road_centerlines_meters(
                portal["bridge"], road_networks, to_meters
            )
            if not lane_lines:
                continue
            centroid_point = portal["footprint"].centroid
            reach = 1000.0
            perpendicular = (-outward_vector[1], outward_vector[0])
            outward_half_plane = Polygon([
                (centroid_point.x + perpendicular[0] * reach,
                 centroid_point.y + perpendicular[1] * reach),
                (centroid_point.x - perpendicular[0] * reach,
                 centroid_point.y - perpendicular[1] * reach),
                (centroid_point.x - perpendicular[0] * reach
                 + outward_vector[0] * 2.0 * reach,
                 centroid_point.y - perpendicular[1] * reach
                 + outward_vector[1] * 2.0 * reach),
                (centroid_point.x + perpendicular[0] * reach
                 + outward_vector[0] * 2.0 * reach,
                 centroid_point.y + perpendicular[1] * reach
                 + outward_vector[1] * 2.0 * reach),
            ])
            lane_half_width = 0.5 * max(
                road_width_m,
                math.sqrt(portal["footprint"].area),
            )
            for lane_line in lane_lines:
                try:
                    mouth_lane_polygons.append(
                        lane_line.buffer(lane_half_width)
                        .intersection(outward_half_plane)
                    )
                except _GEOM_EXC:
                    continue
    if mouth_lane_polygons:
        try:
            mouth_lane_union = unary_union(mouth_lane_polygons)
            portal_owned_polygons = [
                polygon.difference(mouth_lane_union)
                for polygon in portal_owned_polygons
            ]
        except _GEOM_EXC:
            pass
    keep_out_zones.extend(portal_owned_polygons)
    try:
        approach_keep_out = (
            unary_union(keep_out_zones) if keep_out_zones else None
        )
    except _GEOM_EXC:
        approach_keep_out = None

    # Cross-deck awareness (user 2026-07-10, the double-bridge overlap
    # class): a road under TWO parallel decks must be split by BOTH
    # footprints, or each deck walks its approach chain under the other
    # deck and out the far side — two chains double-covering one road.
    crossing_polygons: list = []
    for bridge in corridor_bridges:
        crossing = _bridge_deck_box_meters(bridge, layout)
        if crossing is None:
            crossing = _bridge_footprint_meters(bridge, to_meters)
        if crossing is not None:
            crossing_polygons.append(crossing)
    for pair in portal_pairs:
        for portal in pair["portals"]:
            crossing_polygons.append(portal["footprint"])
    try:
        all_crossings_union = (
            unary_union(crossing_polygons) if crossing_polygons else None
        )
    except _GEOM_EXC:
        all_crossings_union = None

    # Already-emitted approach rects (all decks, all portals in this
    # pass): a later chain never overlaps an earlier one — the same
    # earlier-emitter-wins order ``deconflict_road_features`` walks.
    emitted_registry: list = []

    osm_road_lines: list[LineString] | None = None
    n_emitted = 0
    for bridge in corridor_bridges:
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is None:
            continue
        # Round 10: the corridor works on the abutment-to-abutment BOX
        # (the classified hard-face union can be multi-lobe; approach
        # walks measured from the LOBE edge left the road-exit lane
        # unconstrained between the lobe and the box at the J/R start
        # lip — audit 12: lane samples at raw DEM 171-174).
        deck_box = _bridge_deck_box_meters(bridge, layout)
        if deck_box is not None:
            footprint = deck_box
        covered_polygons.append(footprint)
        deck_elevation = _bridge_deck_elevation_m(
            bridge, dem, tile_lat, tile_lon
        )
        if deck_elevation is None:
            UI.vprint(
                2,
                "   [object-bridge] no deck datum (DEM unsampled, no MSL) "
                f"for {bridge.object_resources} — corridor skipped",
            )
            continue
        floor_elevation = _bridge_corridor_floor_m(bridge, deck_elevation)
        # Amendment A10 clearance CHECK (never the floor driver): the
        # floor-to-girder gap must reach the measured in-the-wild minimum.
        girder_underside = _bridge_girder_underside_m(bridge, deck_elevation)
        if girder_underside is not None:
            girder_clearance = girder_underside - floor_elevation
            if girder_clearance < float(
                _CFG.BRIDGE_ROAD_CLEARANCE_MINIMUM_M
            ) - 1e-6:
                UI.vprint(
                    1,
                    "   [object-bridge] WARNING: corridor clearance "
                    f"{girder_clearance:.2f} m under "
                    f"{bridge.object_resources} is below the "
                    f"{_CFG.BRIDGE_ROAD_CLEARANCE_MINIMUM_M} m acceptance "
                    "bound (amendment A10) — emitting anyway, audit "
                    "required",
                )

        road_lines = _draped_road_centerlines_meters(
            bridge, road_networks, to_meters
        )
        road_source = "dsf-road-network"
        if not road_lines:
            if osm_road_lines is None:
                osm_road_lines = _load_underpass_osm_road_lines(
                    layout, to_meters
                )
            road_lines = [
                line for line in osm_road_lines
                if line.intersects(footprint)
            ]
            road_source = "openstreetmap"
        if not road_lines:
            UI.vprint(
                1,
                "   [object-bridge] no draped road under "
                f"{bridge.object_resources} — corridor skipped",
            )
            continue
        # User ruling 2026-07-14c: the approach ramps match the WIDTH
        # of the bridge TRENCH they emerge from (the deck box minus the
        # trench inset — ~53 m at KBNA Donelson Pike), not one
        # carriageway each.  Deduping at that half-width merges the
        # parallel carriageway lines into one wide walk; genuinely
        # diverging branches (the Donelson Y) stay separate chains
        # whose full-width rects overlap through the fork.
        trench_width_m = None
        try:
            deck_box = _bridge_deck_box_meters(bridge, layout)
            if deck_box is not None and not deck_box.is_empty:
                rotated_rectangle = min_rotated_rect(deck_box)
                corners = list(rotated_rectangle.exterior.coords)
                if len(corners) >= 3:
                    edge_a = math.hypot(
                        corners[1][0] - corners[0][0],
                        corners[1][1] - corners[0][1],
                    )
                    edge_b = math.hypot(
                        corners[2][0] - corners[1][0],
                        corners[2][1] - corners[1][1],
                    )
                    trench_width_m = (
                        min(edge_a, edge_b) - 2.0 * _TRENCH_INSET_M
                    )
                    if trench_width_m < road_width_m:
                        trench_width_m = None
        except _GEOM_EXC:
            trench_width_m = None
        road_lines = _dedup_parallel_road_lines(
            road_lines, (trench_width_m or road_width_m) / 2.0
        )

        # The under-deck TRENCH and the R8 flush-seat cut moved to the
        # PRE-solve layout builder (``build_bridge_layout_shapes``, user
        # ruling R12) — this post-solve emitter now owns only the road
        # APPROACHES outside the footprint (DEM-coupled ramps, the
        # legacy-KDFW-proven block) and the suppression/refusal logs.

        # A10 point (iv): the depressed road runs >= 240 m per side
        # before rejoining grade; a caller may only widen that.
        depressed_length_m = max(
            float(approach_length_m),
            float(_CFG.BRIDGE_CORRIDOR_DEPRESSED_LENGTH_M),
        )
        _emit_corridor_for_footprint(
            layout, dem, tile_lat, tile_lon, meters_to_lat_lon,
            footprint, floor_elevation, road_lines,
            road_width_m, ramp_step_m, depressed_length_m,
            keep_out=approach_keep_out,
            crossing_union=all_crossings_union,
            emitted_registry=emitted_registry,
            width_override_m=trench_width_m,
        )
        n_emitted += 1
        UI.vprint(
            1,
            "   [object-bridge] corridor floor "
            f"{floor_elevation:.1f} m under {bridge.object_resources} "
            f"(deck {deck_elevation:.1f} m, road source {road_source})",
        )

    # ── Tunnel portal approaches (user ruling 2026-07-10): the road
    # corridor CLIMBS AWAY from each mouth — floor at the mouth's road
    # grade, rising to the digital elevation model outward.  Only
    # outward road pieces are walked; the hill side is owned by the
    # pair band in the keep-out.
    for pair in portal_pairs:
        for portal in pair["portals"]:
            footprint = portal["footprint"]
            mouth_floor = portal.get("mouth_floor_m")
            if mouth_floor is None:
                continue
            covered_polygons.append(footprint)
            road_lines = _draped_road_centerlines_meters(
                portal["bridge"], road_networks, to_meters
            )
            road_source = "dsf-road-network"
            if not road_lines:
                if osm_road_lines is None:
                    osm_road_lines = _load_underpass_osm_road_lines(
                        layout, to_meters
                    )
                road_lines = [
                    line for line in osm_road_lines
                    if line.intersects(footprint)
                ]
                road_source = "openstreetmap"
            if not road_lines:
                UI.vprint(
                    1,
                    "   [object-tunnel] no road through the portal of "
                    f"{portal['bridge'].object_resources} — outward "
                    "corridor skipped",
                )
                continue
            # Mouth-face width (the footprint's extent perpendicular to
            # the outward direction) — the CAP the ruling below enforces,
            # not the ramp width itself.
            mouth_face_width_m = None
            outward_vector = portal.get("outward")
            if outward_vector is not None:
                centroid_point = footprint.centroid
                minimum_p = maximum_p = 0.0
                try:
                    for vertex_x, vertex_y in footprint.exterior.coords:
                        projection = (
                            (vertex_x - centroid_point.x)
                            * -outward_vector[1]
                            + (vertex_y - centroid_point.y)
                            * outward_vector[0]
                        )
                        minimum_p = min(minimum_p, projection)
                        maximum_p = max(maximum_p, projection)
                    mouth_face_width_m = maximum_p - minimum_p
                except _GEOM_EXC:
                    mouth_face_width_m = None
            # User ruling 2026-07-15 (supersedes 2026-07-14c): the outward
            # ramp matches the DRIVABLE road width, not the full portal
            # footprint whose slanted wing walls flare far wider — mapped
            # OSM carriageway + shoulder, else the classified deck-face
            # width, else the mouth face, always capped at the mouth face.
            ramp_width_m, width_provenance = _portal_outward_ramp_width_m(
                layout, portal, footprint, to_meters, mouth_face_width_m)
            if ramp_width_m is None:
                ramp_width_m = mouth_face_width_m
            # The parallel-carriageway dedup keeps the mouth-face reach so
            # genuine twin carriageways still merge into one walk (the
            # ramp is then narrowed to ``ramp_width_m`` by the override).
            road_lines = _dedup_parallel_road_lines(
                road_lines,
                (mouth_face_width_m or road_width_m) / 2.0,
            )
            if _emit_corridor_for_footprint(
                layout, dem, tile_lat, tile_lon, meters_to_lat_lon,
                footprint, mouth_floor, road_lines,
                road_width_m, ramp_step_m,
                max(float(approach_length_m),
                    float(_CFG.BRIDGE_CORRIDOR_DEPRESSED_LENGTH_M)),
                keep_out=approach_keep_out,
                crossing_union=all_crossings_union,
                emitted_registry=emitted_registry,
                outward=outward_vector,
                width_override_m=ramp_width_m,
            ):
                n_emitted += 1
                UI.vprint(
                    1,
                    "   [object-tunnel] outward corridor from mouth "
                    f"floor {mouth_floor:.1f} m for "
                    f"{portal['bridge'].object_resources} "
                    f"(road source {road_source})",
                )
    return n_emitted, suppression_polygons, covered_polygons


def _load_underpass_osm_road_lines(layout, to_meters,
                                   include_small_roads=False):
    """OSM road LineStrings (local meters) eligible to pass under a
    bridge — the same filter the legacy underpass emitter applies (skip
    ways tagged ``bridge`` or ``tunnel``).

    ``include_small_roads`` merges the airport small-roads layer in
    (owner 2026-07-31: "OSM big or small roads should probably have the
    data").  The underpass caller keeps the historical big-roads-only
    set; the BRIDGE RAMP asks for both, because the roads a pack's
    service bridges carry are routinely small roads and the big-roads
    layer alone returned nothing at OTHH."""
    from .pipeline import _load_osm_big_roads
    nodes_raw, ways_raw = _load_osm_big_roads(
        layout.anchor[0], layout.anchor[1]
    )
    nodes_raw = dict(nodes_raw or {})
    ways_raw = list(ways_raw or [])
    if include_small_roads:
        try:
            from .pipeline import _load_osm_small_roads
            small_nodes, small_ways = _load_osm_small_roads(
                layout.anchor[0], layout.anchor[1]
            )
            nodes_raw.update(small_nodes or {})
            ways_raw.extend(small_ways or [])
        except Exception:      # a missing small-roads cache is not fatal
            pass
    if not ways_raw:
        return []
    nodes_meters: dict[str, tuple[float, float]] = {}
    for node_id, (latitude, longitude) in nodes_raw.items():
        nodes_meters[node_id] = to_meters(longitude, latitude)
    highway_types = {
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "motorway_link", "trunk_link", "primary_link", "residential",
        "service",
    }
    lines: list[LineString] = []
    for _way_id, node_refs, tags in ways_raw:
        if tags.get("highway") not in highway_types:
            continue
        if tags.get("bridge") and tags.get("bridge") != "no":
            continue
        if tags.get("tunnel") and tags.get("tunnel") != "no":
            continue
        points = [nodes_meters[n] for n in node_refs if n in nodes_meters]
        if len(points) < 2:
            continue
        try:
            line = LineString(points)
        except _GEOM_EXC:
            continue
        if not line.is_empty and line.length >= 5.0:
            lines.append(line)
    return lines


def _emit_corridor_for_footprint(
        layout, dem, tile_lat, tile_lon, meters_to_lat_lon,
        footprint, floor_elevation, road_lines,
        road_width_m, ramp_step_m, approach_length_m,
        keep_out=None, crossing_union=None, emitted_registry=None,
        outward=None, width_override_m=None, fill_grade=None,
        ramp_ref=None):
    """Emit stepped approach ramps from ``floor_elevation`` up to the DEM
    for each road crossing a bridge footprint (the under-deck trench
    plate itself is emitted by the caller as the FULL footprint, stage
    2b).  Returns True when at least one polygon was emitted.

    Mirrors the legacy underpass emitter's per-step ramp shape (a sloped
    ``ROLE_TUNNEL_RAMP`` rect per ``ramp_step_m`` interpolating floor→DEM),
    driven by the object footprint rather than a taxi rect.  Deconfliction
    against airport pavement is the shared downstream
    ``deconflict_road_features`` pass, exactly as for the legacy shapes.

    ``crossing_union`` — the union of EVERY classified crossing (all
    deck boxes + portal footprints): the road is split by ALL of them,
    not just this bridge's own footprint, so a walk never runs under a
    sibling deck and out the far side (the double-bridge overlap class).
    ``emitted_registry`` — shared list of already-emitted approach rects;
    a later chain skips rects overlapping an earlier chain's.
    ``outward`` — optional unit vector: walk only road pieces on that
    side of the footprint (tunnel portals ramp AWAY from the hill).
    ``width_override_m`` — full corridor width for the ramp rects when
    the caller matches the crossing opening (the trench road-exit
    width, the portal mouth face) instead of one carriageway (user
    ruling 2026-07-14c: ramps as wide as the opening they emerge
    from)."""
    emitted = False
    half_width = (width_override_m if width_override_m else
                  road_width_m) / 2.0
    split_region = footprint
    if crossing_union is not None:
        split_region = crossing_union
    centroid = footprint.centroid
    for road_line in road_lines:
        try:
            outside = road_line.difference(split_region)
        except _GEOM_EXC:
            outside = None
        if outside is None or outside.is_empty:
            continue
        pieces = (
            list(outside.geoms) if hasattr(outside, "geoms") else [outside]
        )
        for piece in pieces:
            if piece.is_empty or piece.geom_type != "LineString":
                continue
            coordinates = list(piece.coords)
            if len(coordinates) < 2:
                continue
            # Only pieces that BEGIN at this bridge's own footprint —
            # with the full crossing union splitting the road, a sibling
            # deck's pieces also appear here and belong to that deck's
            # own emission turn.
            if piece.distance(footprint) > 1.0:
                continue
            if outward is not None:
                midpoint = piece.interpolate(0.5, normalized=True)
                side = ((midpoint.x - centroid.x) * outward[0]
                        + (midpoint.y - centroid.y) * outward[1])
                if side <= 0.0:
                    continue
            distance_start = footprint.distance(Point(coordinates[0]))
            distance_end = footprint.distance(Point(coordinates[-1]))
            if distance_start <= distance_end:
                walk = LineString(coordinates)
            else:
                walk = LineString(list(reversed(coordinates)))
            walk_length = min(walk.length, approach_length_m)
            # Plate weld (defect A, 2026-07-15): deck corridors register
            # the chain's near edge on the corridor PLATE's exit edge —
            # verbatim shared corner coordinates are the weld.  Portal
            # mouths keep their own (untouched) geometry.
            weld_edge = None
            if outward is None:
                weld_edge = _corridor_plate_exit_edge(
                    layout, footprint, walk.coords[0], half_width
                )
            if _emit_corridor_ramp_chain(
                layout, dem, tile_lat, tile_lon, meters_to_lat_lon,
                walk, walk_length, floor_elevation, half_width, ramp_step_m,
                keep_out=keep_out,
                emitted_registry=emitted_registry,
                refuse_inverted=(outward is not None),
                weld_edge=weld_edge,
                fill_grade=fill_grade,
                ramp_ref=ramp_ref,
            ):
                emitted = True
    return emitted


def _corridor_plate_exit_edge(layout, footprint, start_xy, half_width):
    """The corridor PLATE's short-end edge nearest an approach walk's
    start point, as the plate's two EXACT ring corner coordinates
    ``((ax, ay), (bx, by))`` — the verbatim-shared-coordinate weld the
    chain's first quad copies into its near edge (defect A, KBNA
    2026-07-15: the chain started on the deck-box edge while the plate
    lip sits ``_TRENCH_INSET_M`` inside it — a 1.09 m open seam at
    36.12202,-86.66612 — with a 4-5 m lateral offset between the road
    line and the plate axis).

    Donelson-class only (guarded): the plate end must match the chain
    width (the road runs ALONG the deck axis and exits the short end,
    so the trench end edge and the trench-width approach are the same
    span).  Roads exiting through a deck's LONG side keep the previous
    behaviour.  ``None`` when there is no emitted plate, the geometry
    is degenerate, or the guards fail."""
    plate = None
    best_area = 0.0
    for shape in layout.shapes:
        if getattr(shape, "ref", "") != "object_bridge_corridor":
            continue
        polygon = shape.polygon
        if polygon is None or polygon.is_empty:
            continue
        try:
            overlap_area = polygon.intersection(footprint).area
        except _GEOM_EXC:
            continue
        if overlap_area > best_area:
            best_area = overlap_area
            plate = polygon
    if plate is None:
        return None
    try:
        rectangle_corners = list(
            min_rotated_rect(plate).exterior.coords)[:4]
    except _GEOM_EXC:
        return None
    if len(rectangle_corners) < 4:
        return None
    edges = [
        (rectangle_corners[index], rectangle_corners[(index + 1) % 4])
        for index in range(4)
    ]
    edges.sort(key=lambda edge: math.hypot(
        edge[1][0] - edge[0][0], edge[1][1] - edge[0][1]))
    short_edges = edges[:2]

    def _midpoint_distance(edge):
        return math.hypot(
            (edge[0][0] + edge[1][0]) / 2.0 - start_xy[0],
            (edge[0][1] + edge[1][1]) / 2.0 - start_xy[1],
        )

    exit_edge = min(short_edges, key=_midpoint_distance)
    if _midpoint_distance(exit_edge) > 30.0:
        return None
    edge_length = math.hypot(
        exit_edge[1][0] - exit_edge[0][0],
        exit_edge[1][1] - exit_edge[0][1],
    )
    # Width guard: the plate end and the approach must be the same
    # span for a two-corner verbatim copy to make sense.
    if abs(edge_length - 2.0 * half_width) > 3.0:
        return None
    # Snap the rotated-rectangle corners to the plate's ACTUAL ring
    # vertices — only exact ring coordinates intern into shared nodes.
    ring = list(plate.exterior.coords)
    snapped = []
    for corner_x, corner_y in exit_edge:
        nearest = min(
            ring,
            key=lambda vertex: (
                (vertex[0] - corner_x) ** 2 + (vertex[1] - corner_y) ** 2
            ),
        )
        if math.hypot(nearest[0] - corner_x, nearest[1] - corner_y) > 1.5:
            return None
        snapped.append((nearest[0], nearest[1]))
    if math.hypot(
        snapped[1][0] - snapped[0][0], snapped[1][1] - snapped[0][1]
    ) < 1.0:
        return None
    return snapped[0], snapped[1]


#: §F3 gate (LEMD ramp/road fidelity spec, law 3).  DEFAULT ON.  OFF
#: restores the raw floor→DEM blend, byte for byte.
_RAMP_MONOTONE_ENV = "O4_RAMP_MONOTONE"

#: The round's materiality floor (auto_patch CLAUDE.md convergence
#: guards, and the spec's own "no interior local maxima beyond 0.01 m").
#: A profile whose worst interior reversal is under it is left ALONE, so
#: the law never rewrites values it would not visibly change.
_RAMP_MONOTONE_FLOOR_M = 0.01


def ramp_monotone_law_enabled() -> bool:
    """§F3: does an approach ramp's station profile descend monotonically
    between grade and portal?

    THE DEFECT IT CLOSES (owner sim read of 1.0.265, LEMD item 1:
    "up-and-down humps and valleys in the ramp").  The chain's profile is
    a LINEAR BLEND from the portal floor to the DEM *at each station*::

        z(s) = (1 - s/L) * floor + (s/L) * ground(s)

    so every bump in ``ground`` along the walk is carried into the road,
    scaled by ``s/L``.  A ramp is not a terrain tracing — it is a road
    between two fixed ends — and the blend gives it interior local
    maxima wherever the terrain has any.

    THE LAW: conform the station profile to ONE monotone run with BOTH
    ENDS PINNED (the portal floor at station 0, the ground tie at the
    last station).  A forward cascade removes every reversal and a
    backward cascade re-seats the run under its far end; the result is
    monotone by construction, so it has no interior local maximum at all.
    """
    return os.environ.get(_RAMP_MONOTONE_ENV, "1") == "1"


def _monotone_ramp_profile(elevations: list) -> list:
    """§F3: ``elevations`` conformed to one monotone run, ends pinned.

    Direction is the profile's OWN (last against first), so a ramp
    climbing out of a portal and a corridor descending to one are the
    same law.  Two cascades:

      * forward, ``e[i] = extremum(e[i], e[i-1])`` — every interior
        reversal removed, the far end untouched;
      * backward from the far end, the opposite extremum — the run
        re-seated under its own ground tie, the near end untouched.

    The result is monotone, so it carries NO interior local maximum.
    Below :data:`_RAMP_MONOTONE_FLOOR_M` of worst reversal the input is
    returned unchanged: a profile that is already monotone to the round's
    materiality floor is not rewritten.
    """
    if not ramp_monotone_law_enabled() or len(elevations) < 3:
        return elevations
    values = [float(v) for v in elevations]
    ascending = values[-1] >= values[0]
    worst = 0.0
    for index in range(1, len(values)):
        step = values[index] - values[index - 1]
        reversal = -step if ascending else step
        worst = max(worst, reversal)
    if worst <= _RAMP_MONOTONE_FLOOR_M:
        return elevations
    out = list(values)
    last = len(out) - 1
    # Neither cascade ever WRITES an end: the forward one stops before
    # the far end and the backward one before the near end, so both pins
    # hold without a restore that could re-break the run.
    if ascending:
        for index in range(1, last):
            out[index] = max(out[index], out[index - 1])
        for index in range(last - 1, 0, -1):
            out[index] = min(out[index], out[index + 1])
    else:
        for index in range(1, last):
            out[index] = min(out[index], out[index - 1])
        for index in range(last - 1, 0, -1):
            out[index] = max(out[index], out[index + 1])
    return out


def _emit_corridor_ramp_chain(
        layout, dem, tile_lat, tile_lon, meters_to_lat_lon,
        walk, walk_length, floor_elevation, half_width, ramp_step_m,
        keep_out=None, emitted_registry=None, refuse_inverted=False,
        weld_edge=None, fill_grade=None, ramp_ref=None):
    """Step ``walk`` from the bridge edge (``floor_elevation``) out to the
    DEM in ``ramp_step_m`` increments, emitting one sloped
    ``ROLE_TUNNEL_RAMP`` quad per step.  Returns True when any quad was
    emitted.

    2026-07-15 rework (KBNA Donelson defects A+B, measured on the
    emitted patch):

    * **Shared facing edges.**  ONE corner pair is computed per chain
      station and used verbatim by both adjoining quads — the chain is
      contiguous by construction (zero facing gap, zero overlap on
      curved roads; the per-step independent rects overlapped under
      curvature and the registry then dropped every other step — the
      six measured terrain holes).
    * **Chain identity in the registry.**  A chain's quads are compared
      only against pieces registered BEFORE this chain started; the
      registry's purpose is cross-crossing / twin-carriageway
      protection (audit invariant 1), never self-comparison.
    * **[H,L,L,H] corner order.**  Quads are emitted with ring corners
      0,3 at the HIGH end, matching ``corner_alts_from_high_low`` (the
      legacy emitter's explicit reorder).  The fixed near-end-first
      order shipped every climbing rect INVERTED — the floor value on
      the FAR edge, a 2-4 m sawtooth per step (measured: rect -11066
      carried 161.0 on the edge away from the 161.01 plate).
    * **Plate weld** (``weld_edge``, deck corridors only): the first
      quad's near edge copies the corridor plate's two exit-edge ring
      coordinates VERBATIM (0.5 m interning makes them shared nodes —
      the weld), and the lateral offset between the plate axis and the
      road line decays linearly to zero over the next 3 stations so
      curved roads still track.  The near edge keeps the plate's floor
      elevation (fraction 0 of the floor→DEM interpolation); the far
      edge keeps the chain's existing climb values.

    ``refuse_inverted`` — the tunnel-portal inversion guard (user
    2026-07-10, the runway-02C climb): the mouth floor must never sit
    above the ground the chain welds to at its NEAR end — a floor above
    the adjacent road means the datum was wrong (embankment top instead
    of the road), producing a ramp climbing INTO the crossing and
    poking above the descending terrain.  The FAR end is deliberately
    not tested: terrain legitimately falls away from a mouth along the
    road (measured KBNA 02C west: 180 m at the face down to 174 m at
    240 m out).  Deck-carried BRIDGE corridors skip the guard entirely:
    a causeway over low ground sends its road DOWN to the valley."""
    if refuse_inverted:
        try:
            near_point = walk.interpolate(min(5.0, walk_length))
            near_lat, near_lon = meters_to_lat_lon(
                near_point.x, near_point.y)
            near_grade = _sample_dem(
                dem, tile_lat, tile_lon, near_lat, near_lon)
        except _GEOM_EXC:
            near_grade = None
        if near_grade is not None and floor_elevation > near_grade + 2.0:
            UI.vprint(
                1,
                "   [object-tunnel] refusing INVERTED portal approach: "
                f"mouth floor {floor_elevation:.1f} m sits above the "
                f"adjacent grade {near_grade:.1f} m",
            )
            return False
    # ── Chain stations ──
    stations = [0.0]
    position = 0.0
    while position < walk_length - 1.0:
        position = min(walk_length, position + ramp_step_m)
        stations.append(position)
    if len(stations) < 2:
        return False
    station_points = [
        (point.x, point.y)
        for point in (walk.interpolate(s) for s in stations)
    ]
    # Plate-weld lateral registration: shift station 0 onto the plate
    # exit edge's midpoint and decay the shift to zero over the next
    # 3 stations (fully back on the road line from station 3 on).
    weld_corners = None
    if weld_edge is not None:
        (weld_ax, weld_ay), (weld_bx, weld_by) = weld_edge
        edge_mid_x = (weld_ax + weld_bx) / 2.0
        edge_mid_y = (weld_ay + weld_by) / 2.0
        shift_x = edge_mid_x - station_points[0][0]
        shift_y = edge_mid_y - station_points[0][1]
        decay_stations = 3.0
        station_points = [
            (
                point_x + shift_x * max(0.0, 1.0 - index / decay_stations),
                point_y + shift_y * max(0.0, 1.0 - index / decay_stations),
            )
            for index, (point_x, point_y) in enumerate(station_points)
        ]
        weld_corners = ((weld_ax, weld_ay), (weld_bx, weld_by))

    # ── Per-station cross edges (bisector normals): ONE corner pair per
    # station, shared verbatim by the two adjoining quads. ──
    left_corners: list = []
    right_corners: list = []
    elevations: list = []
    usable_stations = len(station_points)
    for index, (point_x, point_y) in enumerate(station_points):
        behind_x, behind_y = station_points[max(0, index - 1)]
        ahead_x, ahead_y = station_points[
            min(len(station_points) - 1, index + 1)]
        tangent_x = ahead_x - behind_x
        tangent_y = ahead_y - behind_y
        tangent_norm = math.hypot(tangent_x, tangent_y)
        if tangent_norm < 1.0:
            usable_stations = index
            break
        tangent_x /= tangent_norm
        tangent_y /= tangent_norm
        normal_x = -tangent_y
        normal_y = tangent_x
        try:
            latitude, longitude = meters_to_lat_lon(point_x, point_y)
            ground = _sample_dem(
                dem, tile_lat, tile_lon, latitude, longitude)
        except _GEOM_EXC:
            ground = None
        if ground is None:
            usable_stations = index
            break
        if fill_grade is not None:
            # BRIDGE-RAMP law (owner ruling 2026-07-31): a grade-capped
            # FILL envelope anchored on the deck end —
            #     z(s) = max(ground(s), deck_end − grade · s)
            # the mirror of ``ols._road_regrade_profile``'s cut envelope
            # (that one takes ``min`` of ``bound + grade·|s−t|``).  With
            # a SINGLE anchor the two-pass forward/backward sweep the OLS
            # version needs collapses to this one expression, and the
            # ``max`` against the ground is what makes it fill-only: the
            # ramp descends at the cap until the terrain comes up to meet
            # it and never cuts below the DEM on the way.
            #
            # The default law below is a LINEAR blend to the far ground,
            # which is right for a tunnel corridor (both ends are ours)
            # and wrong here — it would dig through any rise between the
            # deck end and the ramp's end.
            elevations.append(
                max(ground, floor_elevation - fill_grade * stations[index])
            )
        else:
            fraction = stations[index] / walk_length
            elevations.append(
                (1.0 - fraction) * floor_elevation + fraction * ground)
        left_corners.append((point_x + normal_x * half_width,
                             point_y + normal_y * half_width))
        right_corners.append((point_x - normal_x * half_width,
                              point_y - normal_y * half_width))
        if index == 0 and weld_corners is not None:
            # Verbatim plate coordinates for the chain's near edge —
            # exact shared coordinates are the weld.
            corner_a, corner_b = weld_corners
            side_a = ((corner_a[0] - point_x) * normal_x
                      + (corner_a[1] - point_y) * normal_y)
            side_b = ((corner_b[0] - point_x) * normal_x
                      + (corner_b[1] - point_y) * normal_y)
            if side_a > 0.0 > side_b:
                left_corners[0], right_corners[0] = corner_a, corner_b
            elif side_b > 0.0 > side_a:
                left_corners[0], right_corners[0] = corner_b, corner_a
    if usable_stations < 2:
        return False
    # ── §F3: ONE MONOTONE PROFILE ────────────────────────────────────
    # SCOPED OUT of the BRIDGE-RAMP FILL law (``fill_grade``, owner ruling
    # 2026-07-31).  That profile is ``max(ground, deck_end - grade * s)``
    # — fill-only BY CONSTRUCTION, and deliberately not monotone: it
    # rides the ground wherever the ground comes up to meet it.  Making
    # it monotone would cut through exactly the rise the ``max`` exists
    # to preserve.  §F3 governs the DEFAULT law, the linear blend to the
    # DEM at each station, which is the one that carries the terrain's
    # humps into the road.
    if fill_grade is None:
        elevations = _monotone_ramp_profile(elevations[:usable_stations])

    # Chain identity (defect B): quads of THIS chain are tested only
    # against pieces registered before the chain started.
    pre_chain_registry = (
        list(emitted_registry) if emitted_registry is not None else [])

    emitted = False
    for index in range(usable_stations - 1):
        elevation_near = elevations[index]
        elevation_far = elevations[index + 1]
        # [H,L,L,H]: ring corners 0,3 at the HIGH end (the convention
        # ``corner_alts_from_high_low`` encodes; the legacy emitter's
        # explicit reorder).
        if elevation_far >= elevation_near:
            corners = [
                left_corners[index + 1], left_corners[index],
                right_corners[index], right_corners[index + 1],
            ]
        else:
            corners = [
                left_corners[index], left_corners[index + 1],
                right_corners[index + 1], right_corners[index],
            ]
        try:
            polygon = Polygon(corners)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if keep_out is not None and not polygon.is_empty:
                # FRACTIONAL skip (user ruling 2026-07-14c): a quad
                # merely GRAZING a keep-out boundary is emitted — the
                # absolute 0.5 m2 test dropped every leading rect at
                # the KBNA portal mouths (ramps stopped one step short
                # of the plate) and starved the wide Donelson chains.
                # A quad genuinely landing on owned ground still skips.
                try:
                    if (polygon.intersection(keep_out).area
                            > 0.25 * polygon.area):
                        continue
                except _GEOM_EXC:
                    pass
            # Approach-versus-approach exclusivity (user 2026-07-10):
            # a quad overlapping an EARLIER CHAIN's quad is skipped —
            # sloped quads can never be clipped without breaking their
            # two-corner altitude semantics, so overlap is prevented at
            # birth, not cleaned downstream.
            if not polygon.is_empty:
                overlapping = False
                for earlier in pre_chain_registry:
                    try:
                        if polygon.intersection(earlier).area > 0.5:
                            overlapping = True
                            break
                    except _GEOM_EXC:
                        continue
                if overlapping:
                    continue
            if polygon.geom_type == "Polygon" and not polygon.is_empty:
                if abs(elevation_near - elevation_far) >= 0.1:
                    layout.shapes.append(BuiltShape(
                        polygon=polygon,
                        role=ROLE_TUNNEL_RAMP,
                        ref=ramp_ref or "object_bridge_approach",
                        altitude_high=round(
                            max(elevation_near, elevation_far), 1),
                        altitude_low=round(
                            min(elevation_near, elevation_far), 1)))
                else:
                    layout.shapes.append(BuiltShape(
                        polygon=polygon,
                        role=ROLE_TUNNEL_RAMP,
                        ref=ramp_ref or "object_bridge_approach",
                        altitude=round(
                            0.5 * (elevation_near + elevation_far), 1)))
                if emitted_registry is not None:
                    emitted_registry.append(polygon)
                emitted = True
        except _GEOM_EXC:
            pass
    return emitted


# ---------------------------------------------------------------------------
# Feature B stage 2 — solve-side deck-end / profile pins + crossing floor
# (spec section 3.2 steps 1-2 and the bridge_crossing_floor law; all law
# values come from grade_law so the writers here and the verification
# checks can never drift — the lockstep pattern of the runway-end skirt.)
# ---------------------------------------------------------------------------

# Pavement roles eligible for bridge pins: the solved airside network the
# deck couples to.  Boundary / retaining walls / tunnel ramps / buildings
# are feature shapes, not the graded network the abutment meets.
_BRIDGE_PIN_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_PRIMARY_PARALLEL,
    ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_APRON, ROLE_JUNCTION,
})


def bridge_pin_roles(include_groundside: bool = False) -> frozenset:
    """The shape roles a bridge deck-end pin may attach to.

    The base set is the solved AIRSIDE network above.  ``include_
    groundside`` adds LANDSIDE pavement, which W1b's deck-flush pins need
    and the airside pin law does not — the same split ruling R13 made for
    :func:`pavement_cut_roles`, and copied from it deliberately.

    An airside deck meets taxiways and aprons, so the base set is
    complete for it.  A ROAD-carried overpass generally does not: OTHH's
    Bridge_01 lands on the main terminal's groundside pavement, and with
    the base set its deck ends have nothing to pin to — the owner's
    "flush with grade" would silently do nothing.  Owner ruling
    2026-07-31: bridges MAY pin groundside."""
    from .layout import ROLE_GROUNDSIDE_PAVEMENT

    if not include_groundside:
        return _BRIDGE_PIN_ROLES
    return frozenset(_BRIDGE_PIN_ROLES | {ROLE_GROUNDSIDE_PAVEMENT})

# A ring vertex within this distance (m) of an abutment line counts as
# lying ON it (inserted crossings are exact intersections; pre-existing
# deck-cut end vertices sit within layout snapping tolerance).
_BRIDGE_PIN_ON_LINE_TOLERANCE_M = 0.25

# Abutment lines are exactly deck-width; extend each end by this fraction
# of its own length so a ring crossing at the deck corner is still cut.
_ABUTMENT_LINE_EXTENSION_FRACTION = 0.25

# ── Stage 2b iteration 5: coverage-extent geometry (KBNA audit 5) ──
# The trench rim is inset this far inside the deck footprint; the
# causeway plate extends _CAUSEWAY_INWARD_OVERLAP_M INWARD past the
# abutment lip so a mesh sample exactly ON the lip line lands INSIDE
# the 167-flat plate even after to_osm's 0.5 m node interning wobbles
# the written edge (audit 5: on-line samples read the wall slope or
# raw terrain).  The remaining trench-to-causeway gap is the R2
# node-split wall and MUST stay above the 0.5 m weld tolerance:
# 1.2 − 0.6 = 0.6 m.
_TRENCH_INSET_M = 1.2
_CAUSEWAY_INWARD_OVERLAP_M = 0.6

# The causeway lip is widened this much per side beyond the deck width
# so the audit's line-END samples (t = 0 and t = 1, exactly at the deck
# corners) stay inside the plate under coordinate wobble.
_CAUSEWAY_WIDTH_MARGIN_M = 1.0

# ── Deck-lip weld strips (user directive 2026-07-15: aircraft must taxi
# SMOOTHLY onto the decks — the pavement must slightly OVERLAP the
# deck-elevation terrain, not merely touch it; at mesh-triangulation
# level edge-to-edge contact still leaves sliver triangles).  The R8
# hard-deck cut trims pavement at the deck-box boundary while the trench
# plate is ``deck_box.buffer(-_TRENCH_INSET_M)``, leaving a ~1.2 m ring
# of raw mesh whose triangles dive to the trench floor right at the lip
# (measured KBNA taxiway-L: pavement 167.0 pinned, plate edge 0.8-1.2 m
# away at 161.01).  On every pavement-facing rim segment a WELD STRIP is
# born at the deck-top profile law value, spanning from the causeway
# inward depth (keeping the R2 node-split wall to the trench) out to
# _DECK_WELD_OVERLAP_M INSIDE the pavement, whose fronting ring vertices
# are pinned at the same law value — a coplanar, invisible overlap.
# The depth must EXCEED to_osm's 0.5 m node interning (the audit-5
# causeway lesson): a 0.4 m offset merges the strip boundary into the
# pavement edge nodes and the written overlap collapses to contact
# (measured KBNA: eroded-overlap coverage 22-66 % at 0.4 m); above the
# 0.71 m worst-case bucket diagonal both rings survive verbatim.
_DECK_WELD_OVERLAP_M = 0.8
# Pavement within this reach OUTSIDE the deck box fronts the deck (the
# measured pavement cut sits within ~0.4 m of the box under the 0.5 m
# node-interning wobble; 2.5 m is generous without capturing bystanders).
_DECK_WELD_FRONT_REACH_M = 2.5

# Road-exit cut half-width (m) through a causeway plate (round 10): a
# road that leaves the span THROUGH an abutment end (KBNA: Donelson
# Pike runs along the deck axis, measured segments local x -64..+77)
# must not be dammed by the 167-flat causeway — the author mesh runs
# the 161 corridor ~144 m THROUGH the span and out both ends, flanked
# by the fill (A10 / spec section 2.2; corridor 34-38 m wide overall).
# Each fully-draped carriageway polyline is buffered by this half-width
# and the union is cut out of the plate; the parallel carriageways at
# KBNA (7 draped lines) union to the author's full corridor width.
_ROAD_EXIT_CUT_HALF_WIDTH_M = 11.0


def _road_exit_corridor_meters(bridge, layout, to_meters):
    """The union of the fully-draped road carriageway corridors crossing
    a bridge's deck footprint, buffered to carriageway width in layout
    meters — the ground the causeway must YIELD (round 10).  ``None``
    when no draped road crosses."""
    road_networks = _object_bridge_road_networks(layout)
    road_lines = _draped_road_centerlines_meters(
        bridge, road_networks, to_meters
    )
    if not road_lines:
        return None
    try:
        return unary_union([
            line.buffer(_ROAD_EXIT_CUT_HALF_WIDTH_M,
                        cap_style=2, join_style=2)
            for line in road_lines
        ])
    except _GEOM_EXC:
        return None


def _bridge_datum_elevation_m(bridge, dem, tile_lat, tile_lon):
    """Absolute elevation of the object's anchor-terrain plane (the datum
    every effective height is measured from): ``absolute_deck_elevation_m
    − deck_top_y_m`` when OBJECT_MSL fixtures pin the deck, else the DEM
    at the anchor.  ``None`` when neither source is available."""
    deck_elevation = _bridge_deck_elevation_m(bridge, dem, tile_lat, tile_lon)
    if deck_elevation is None:
        return None
    return float(deck_elevation) - float(bridge.deck_top_y_m)


def _abutment_lines_layout_meters(
        bridge, layout,
        extension_fraction=_ABUTMENT_LINE_EXTENSION_FRACTION):
    """The bridge's two abutment lines as layout-meter LineStrings,
    ordered [start end, far end] and extended by ``extension_fraction``
    per side (default :data:`_ABUTMENT_LINE_EXTENSION_FRACTION`; the
    causeway emitter passes 0.0 — its plate must be deck-width, not
    band-width).  Empty list on degenerate geometry."""
    from . import obj8_reader
    origin_longitude, origin_latitude = (
        bridge.frame_origin_longitude_latitude
    )
    lines: list[LineString] = []
    for (start_point, end_point) in bridge.abutment_lines:
        meter_points = []
        for frame_x, frame_z in (start_point, end_point):
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                origin_latitude, origin_longitude, 0.0, frame_x, frame_z
            )
            meter_points.append(layout.ll_to_m(latitude, longitude))
        (ax, ay), (bx, by) = meter_points
        length = math.hypot(bx - ax, by - ay)
        if length < 1.0:
            continue
        ux = (bx - ax) / length
        uy = (by - ay) / length
        reach = length * extension_fraction
        lines.append(LineString([
            (ax - ux * reach, ay - uy * reach),
            (bx + ux * reach, by + uy * reach),
        ]))
    return lines


def _bridge_deck_box_meters(bridge, layout):
    """The abutment-to-abutment deck BOX in layout meters — the convex
    hull of the two (unextended) abutment lines' endpoints.  Iteration 5:
    the classified ``deck_polygon`` is the union of HARD FACES and can be
    a partial, multi-lobe shape (KBNA taxiway-L pools parts p1/p4/p5/p6
    only — the under-deck trench built from it had a mid-deck gap that
    approach ramps legally filled at 162-165 m, breaking the <= 161.25
    corridor acceptance).  The physical under-deck corridor is the FULL
    box between the abutments — the author-mesh treatment.  ``None`` on
    degenerate geometry."""
    from shapely.geometry import MultiPoint
    lines = _abutment_lines_layout_meters(
        bridge, layout, extension_fraction=0.0)
    if len(lines) < 2:
        return None
    corners = [c for line in lines for c in line.coords]
    try:
        box = MultiPoint(corners).convex_hull
    except _GEOM_EXC:
        return None
    if box.geom_type != "Polygon" or box.is_empty:
        return None
    return box


def _record_pin(layout, x, y, value):
    """Record one bucket→elevation hard pin for the solver
    (``layout._object_bridge_pin_values``; consumed by the additive
    bridge-pin block in ``solver_primitives._seed_elevations``).  The
    bucket scheme is ``layout.vertex_bucket`` — the single source of
    truth, arithmetically identical to the solver's inline key."""
    from .layout import vertex_bucket
    pin_values = getattr(layout, "_object_bridge_pin_values", None)
    if pin_values is None:
        pin_values = {}
        setattr(layout, "_object_bridge_pin_values", pin_values)
    pin_values[vertex_bucket(float(x), float(y))] = float(value)


def born_flat_solver_plate(layout, polygon, role, ref, elevation,
                           record_pins: bool = True) -> int:
    """Append a densified flat plate (≈5 m vertex spacing) with per-vertex
    ``node_altitudes`` at ``elevation``; when ``record_pins`` is true (the
    default) also register EVERY ring vertex as a hard solver pin
    (``_record_pin`` → ``layout._object_bridge_pin_values``).

    THE shared birth primitive for object-derived terrain plates (ruling
    R12).  With ``record_pins`` the plate is a FIRST-CLASS solver graph
    member (its role is in the solver's PAVEMENT_ROLES): ``_seed_elevations``
    pins it exactly like a deck-end pin and protects it via the seam-pin
    index, the solve grades the neighbouring pavement to meet it, the
    writeback is the identity, and ``to_osm`` ships it per-node ``alt_abs``.
    Feature B's bridge trench and causeway birth this way.

    Feature A's tunnel trench passes ``record_pins=False``: it is
    OFF-PAVEMENT terrain (the airside pavement is subtracted from the body
    before birth, ruling R2), so it must NOT pin — and its role is NOT in
    PAVEMENT_ROLES — leaving it out of the pavement solve entirely.  It
    still ships per-node ``alt_abs`` (the flat-by-law encoding the mesh step
    consumes) and wins the LAW-tier weld at any shared vertex.  Returns the
    ring vertex count (0 on degenerate input)."""
    if (polygon is None or polygon.is_empty
            or polygon.geom_type != "Polygon"):
        return 0
    try:
        dense = polygon.segmentize(5.0)
    except (AttributeError, _GEOM_EXC):
        dense = polygon
    ring = list(dense.exterior.coords)
    if len(ring) < 4:
        return 0
    vertex_count = len(ring) - 1 if ring[0] == ring[-1] else len(ring)
    if record_pins:
        for x, y in ring[:vertex_count]:
            _record_pin(layout, x, y, elevation)
    layout.shapes.append(BuiltShape(
        polygon=dense,
        role=role,
        ref=ref,
        node_altitudes=[round(float(elevation), 2)] * (vertex_count + 1)))
    return vertex_count


def _pin_shape_vertices_on_line(layout, shape_index, line, pin_value,
                                capture_band_m=None):
    """Insert ring vertices where the shape crosses ``line`` (seam-anchor
    idiom, reusing ``seam_anchors._insert_seam_vertices``), then hard-pin
    every ring vertex within ``capture_band_m`` of the line at
    ``pin_value`` — both into the shape's ``node_altitudes`` (the
    solver's fallback and downstream readers) and into the solver pin
    registry.  Returns the number of vertices pinned.

    ``capture_band_m`` defaults to the tight on-line tolerance
    (:data:`_BRIDGE_PIN_ON_LINE_TOLERANCE_M`, PROFILE_CARRIED span-end
    pins on continuous pavement); DECK_CARRIED callers pass
    ``config.BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M`` — the pack cuts
    pavement up to ~10 m short of the abutment (measured, KBNA), and
    amendment A10's flat causeway makes the deck-end value exact
    anywhere in that band."""
    from .seam_anchors import _insert_seam_vertices
    if capture_band_m is None:
        capture_band_m = _BRIDGE_PIN_ON_LINE_TOLERANCE_M
    shape = layout.shapes[shape_index]
    inserted_keys: set = set()
    try:
        new_shape = _insert_seam_vertices(shape, [line], inserted_keys)
    except _GEOM_EXC:
        new_shape = None
    if new_shape is not None:
        layout.shapes[shape_index] = new_shape
        shape = new_shape
    if shape.polygon is None or shape.polygon.is_empty:
        return 0
    ring = list(shape.polygon.exterior.coords)
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    node_altitudes = (
        list(shape.node_altitudes[:len(ring)])
        if shape.node_altitudes else None
    )
    pinned = 0
    changed = False
    for vertex_index, (x, y) in enumerate(ring):
        try:
            if line.distance(Point(x, y)) > capture_band_m:
                continue
        except _GEOM_EXC:
            continue
        _record_pin(layout, x, y, pin_value)
        if node_altitudes is not None and vertex_index < len(node_altitudes):
            node_altitudes[vertex_index] = round(float(pin_value), 2)
            changed = True
        pinned += 1
    if changed and node_altitudes is not None:
        shape.node_altitudes = node_altitudes + [node_altitudes[0]]
    return pinned


def insert_bridge_deck_end_pins(layout, dem, tile_lat, tile_lon) -> int:
    """Feature B stage 2, step 1 (spec section 3.2): insert ring vertices
    where pavement rings cross a DECK_CARRIED (or cosmetic) bridge's
    abutment lines and hard-pin them at the deck-end elevation —
    ``grade_law.bridge_deck_end_pin_elevation_m`` (MSL-first datum).  The
    solved network grades up to the pins under the existing edge budgets.

    Runs pre-solve (called from the pipeline's seam-anchor hook region).
    No-op without a cached classification (gate off).  Returns the number
    of pinned vertices; abutment ends that pin NO vertex (pavement cut
    short of the abutment) are logged — the analytic causeway/approach
    emitters own that gap and take the same pin value (audited by W-V).

    W1b — THE DECK-FLUSH OUTCOME (owner ruling 2026-07-31, ``config.
    OBJECT_BRIDGE_DECK_FLUSH``).  ``road_carried`` spans are pinned here
    too.  Such a span already takes no causeway, no corridor and no
    trench — the road machinery owns the crossing — but it took no pins
    either, so nothing made the terrain meet its deck where it lands;
    that is the whole of the owner's report, and at OTHH it is where all
    three of the pack's road bridges end up.  Pinning adds ONLY the two
    end values: no causeway plate, no corridor, no trench, because those
    all read the ``corridor`` set and this set is not it.

    IMPLEMENTATION NOTE — smaller than the plan's letter, deliberately.
    The plan asked for a NEW partition outcome beside the existing four.
    Measured, the outcome already exists: ``road_carried`` means exactly
    "no causeway, no corridor, no trench", which is three quarters of the
    deck-flush contract, and every one of its consumers wants that
    unchanged.  What was missing was its pins.  A sixth return value that
    always equalled an existing one would have churned fourteen unpack
    sites to carry no information.

    Deck-flush pins may attach to GROUNDSIDE pavement (owner ruling: a
    bridge may pin groundside); airside pins keep the airside-only set.

    ⚠ AND THAT WIDENING IS NOT A CONVENIENCE — IT IS THE ONLY THING THAT
    CAN EVER FIRE HERE.  A road-carried span takes an AIRSIDE deck-end
    pin never, by construction, at any airport.  Proof:
    ``_bridge_is_road_carried`` returns True exactly when no shape whose
    role is in ``_BRIDGE_PIN_ROLES | {service road, service junction}``
    intersects ``deck footprint buffered by BRIDGE_ABUTMENT_PIN_CAPTURE_
    BAND_M``.  An abutment line lies ON the deck footprint edge, so every
    shape within the capture band of that line is inside the same
    buffered footprint.  Any airside shape close enough to pin would
    therefore have made the span NOT road-carried in the first place.
    ``ROLE_GROUNDSIDE_PAVEMENT`` is the one role in the pin set that is
    absent from the road-carried test, so it is the sole escape.

    Measured 2026-07-31, and the result is ZERO pins at both airports
    tested: at OTHH the nearest groundside pavement is 139-790 m from the
    six deck ends (nearest ANY pinnable role: 139 m), at EGLL likewise
    for 4.obj.  These bridges stand in open ground the patch does not
    pave.  The feature is correct and inert there; making the owner's
    ruling visible at OTHH needs terrain EMITTED at the deck ends, not a
    pin on a pavement ring that does not exist."""
    classification = _object_bridge_classification(layout)
    if classification is None:
        return 0
    from .grade_law import bridge_deck_end_pin_elevation_m
    corridor_bridges, _suppress, _refused, road_carried, _portals = (
        _partition_bridges_for_corridors(classification, layout)
    )
    deck_flush_bridges = (
        list(road_carried) if _CFG.OBJECT_BRIDGE_DECK_FLUSH else []
    )
    deck_flush_ids = {id(bridge) for bridge in deck_flush_bridges}
    airside_roles = bridge_pin_roles()
    groundside_roles = bridge_pin_roles(include_groundside=True)
    capture_band = float(_CFG.BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M)
    total_pinned = 0
    if deck_flush_bridges:
        UI.vprint(
            1,
            f"   [object-bridge] deck-flush: {len(deck_flush_bridges)} "
            "road-carried span(s) take deck-end pins (no causeway, no "
            "corridor, no trench)",
        )
    for bridge in list(corridor_bridges) + deck_flush_bridges:
        pin_roles = (
            groundside_roles
            if id(bridge) in deck_flush_ids
            else airside_roles
        )
        datum = _bridge_datum_elevation_m(bridge, dem, tile_lat, tile_lon)
        if datum is None:
            # Verbosity 1 ALWAYS: a silent skip here is the project's
            # classic silent-zero failure (stage 2b diagnosis — the
            # first gated KBNA build produced zero pins with every
            # diagnostic below the log's verbosity).
            UI.vprint(
                1,
                "   [object-bridge] no datum for deck-end pins of "
                f"{bridge.object_resources} — skipped",
            )
            continue
        abutment_lines = _abutment_lines_layout_meters(bridge, layout)
        for end_index, line in enumerate(abutment_lines):
            end_y = (
                bridge.deck_end_elevations_y_m[end_index]
                if end_index < len(bridge.deck_end_elevations_y_m)
                else bridge.deck_top_y_m
            )
            pin_value = bridge_deck_end_pin_elevation_m(datum, end_y)
            pinned_here = 0
            for shape_index, shape in enumerate(list(layout.shapes)):
                if shape.role not in pin_roles:
                    continue
                if shape.polygon is None or shape.polygon.is_empty:
                    continue
                try:
                    near = shape.polygon.exterior.distance(line) \
                        <= capture_band \
                        or shape.polygon.exterior.intersects(line)
                except _GEOM_EXC:
                    continue
                if not near:
                    continue
                pinned_here += _pin_shape_vertices_on_line(
                    layout, shape_index, line, pin_value,
                    capture_band_m=capture_band,
                )
            # Verbosity 1 in BOTH branches (silent-zero rule): the
            # zero-pin end is precisely the signal that the causeway
            # plate must carry the coupling.
            if pinned_here:
                UI.vprint(
                    1,
                    f"   [object-bridge] {pinned_here} deck-end pin(s) at "
                    f"{pin_value:.2f} m (end {end_index}) for "
                    f"{bridge.object_resources}",
                )
            elif id(bridge) in deck_flush_ids:
                # A deck-flush span has NO causeway plate to fall back
                # on, so a zero-pin end here means the ruling did nothing
                # at that end and the reason must say so honestly rather
                # than name a plate that was never born.
                UI.vprint(
                    1,
                    "   [object-bridge] ZERO deck-flush pins at end "
                    f"{end_index} of {bridge.object_resources} (no "
                    f"airside or groundside pavement ring within "
                    f"{capture_band:.0f} m) — the deck end is NOT made "
                    f"flush ({pin_value:.2f} m intended)",
                )
            else:
                UI.vprint(
                    1,
                    "   [object-bridge] ZERO deck-end pins at end "
                    f"{end_index} of {bridge.object_resources} (no "
                    f"pavement ring within {capture_band:.0f} m) — the "
                    "causeway plate carries the pin value "
                    f"({pin_value:.2f} m)",
                )
            total_pinned += pinned_here
    return total_pinned


def _bridge_ramp_road_lines(bridge, road_networks, to_meters, reach_m):
    """Road centrelines within ``reach_m`` of a deck, as local-meter
    LineStrings, from the pack's own DSF road networks.

    Deliberately NOT :func:`_draped_road_centerlines_meters`, which the
    under-deck corridor uses.  That one keeps only FULLY DRAPED segments
    crossing the deck footprint — right for "which road passes beneath
    this bridge", wrong for "which road does this bridge CARRY".  The
    carried road is elevated over the span by construction, so the drape
    filter discards exactly the road the ramp must follow (measured at
    OTHH: 0 fully-draped segments on Bridge_04's and Bridge_05's decks,
    yet 1-2 segments within 25 m of every deck end).

    The on-deck portion is not a hazard here: the caller splits these
    lines by the classifier-owned crossing union before walking, so only
    the pieces OUTSIDE the deck — the approaches, where the road comes
    back down to the ground — are ever ramped."""
    if bridge.deck_polygon is None or not road_networks:
        return []
    from .object_terrain_features import frame_polygon_to_longitude_latitude
    try:
        reach = bridge.deck_polygon.buffer(reach_m)
    except _GEOM_EXC:
        return []
    if reach.is_empty:
        return []
    reach_longitude_latitude = frame_polygon_to_longitude_latitude(
        reach, bridge.frame_origin_longitude_latitude
    )
    if reach_longitude_latitude.geom_type == "MultiPolygon":
        reach_longitude_latitude = max(
            reach_longitude_latitude.geoms,
            key=lambda geometry: geometry.area,
        )
    ring = list(reach_longitude_latitude.exterior.coords)
    lines: list[LineString] = []
    seen: set = set()
    for network in road_networks:
        for segment in dsf_road_network.segments_crossing(network, ring):
            points = [
                to_meters(point.longitude, point.latitude)
                for point in segment.shape_points
            ]
            if len(points) < 2:
                continue
            key = (round(points[0][0], 2), round(points[0][1], 2),
                   round(points[-1][0], 2), round(points[-1][1], 2))
            if key in seen:
                continue
            seen.add(key)
            try:
                line = LineString(points)
            except _GEOM_EXC:
                continue
            if not line.is_empty and line.length >= 5.0:
                lines.append(line)
    return lines


def emit_bridge_ramp_shapes(layout, dem, tile_lat, tile_lon) -> int:
    """W1b's emitter — the BRIDGE RAMP (owner ruling 2026-07-31).

    *"This is a bridge ramp, that follows a road and just ramps up to the
    object, rather than down to it like a tunnel."*

    Deck-end PINNING alone is provably inert for a road-carried span
    (see :func:`insert_bridge_deck_end_pins`): the only pinnable role it
    can ever reach is groundside pavement, and at OTHH the nearest is
    139-790 m from the six deck ends.  These bridges stand in open ground
    the patch does not pave, so terrain has to be EMITTED to meet them.

    The ramp follows the surface road out of each deck end and climbs to
    the deck-end elevation under a grade-capped FILL envelope — the
    mirror of the OLS road cut the owner named, and the inverse of a
    tunnel ramp, which descends from grade to a floor.  Reuses the proven
    corridor-ramp chain verbatim (shared facing edges, keep-out,
    cross-chain overlap registry, [H,L,L,H] corner order): only the
    elevation law differs, passed as ``fill_grade``.

    Returns the number of spans that emitted at least one ramp."""
    if not _CFG.OBJECT_BRIDGE_RAMP:
        return 0
    classification = _object_bridge_classification(layout)
    if classification is None:
        return 0
    from .grade_law import bridge_deck_end_pin_elevation_m

    _corridor, _suppress, _refused, road_carried, _portals = (
        _partition_bridges_for_corridors(classification, layout)
    )
    if not road_carried:
        return 0
    to_meters, meters_to_lat_lon = _local_meter_projections(layout.anchor)
    road_networks = _object_bridge_road_networks(layout)
    osm_road_lines = _load_underpass_osm_road_lines(
        layout, to_meters, include_small_roads=True)
    grade = float(_CFG.TUNNEL_RAMP_MAX_GRADE)
    ramp_step_m = float(_CFG.BRIDGE_RAMP_STEP_M)
    road_width_m = float(_CFG.BRIDGE_RAMP_WIDTH_M)
    max_length_m = float(_CFG.BRIDGE_RAMP_MAX_LENGTH_M)
    crossing_union = _classifier_owned_crossing_union(layout)
    emitted_registry: list = []
    n_spans = 0
    for bridge in road_carried:
        datum = _bridge_datum_elevation_m(bridge, dem, tile_lat, tile_lon)
        if datum is None:
            UI.vprint(
                1,
                "   [object-bridge] bridge ramp: no datum for "
                f"{bridge.object_resources} — skipped",
            )
            continue
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is None or footprint.is_empty:
            continue
        centroid = footprint.centroid
        # The pack's own DSF roads first — they are what the bridge
        # CARRIES.  OSM big roads are the fallback for packs that model
        # no road network of their own.
        road_lines = _bridge_ramp_road_lines(
            bridge, road_networks, to_meters, max_length_m
        ) or osm_road_lines
        if not road_lines:
            UI.vprint(
                1,
                "   [object-bridge] bridge ramp: no road line within "
                f"{max_length_m:.0f} m of {bridge.object_resources} — "
                "no ramp emitted",
            )
            continue
        span_emitted = False
        for end_index, line in enumerate(
                _abutment_lines_layout_meters(bridge, layout)):
            end_y = (
                bridge.deck_end_elevations_y_m[end_index]
                if end_index < len(bridge.deck_end_elevations_y_m)
                else bridge.deck_top_y_m
            )
            deck_end_elevation = bridge_deck_end_pin_elevation_m(
                datum, end_y)
            midpoint = line.interpolate(0.5, normalized=True)
            outward_x = midpoint.x - centroid.x
            outward_y = midpoint.y - centroid.y
            norm = math.hypot(outward_x, outward_y)
            if norm < 1e-6:
                continue
            outward = (outward_x / norm, outward_y / norm)
            try:
                latitude, longitude = meters_to_lat_lon(
                    midpoint.x, midpoint.y)
                ground = _sample_dem(
                    dem, tile_lat, tile_lon, latitude, longitude)
            except _GEOM_EXC:
                ground = None
            if ground is None or ground != ground:
                continue
            rise = deck_end_elevation - ground
            if rise <= _CFG.BRIDGE_RAMP_MIN_RISE_M:
                # The deck end already sits on the ground here; a ramp
                # would be a no-op plate.  Logged, never silent.
                UI.vprint(
                    2,
                    f"   [object-bridge] bridge ramp: end {end_index} of "
                    f"{bridge.object_resources} rises {rise:.2f} m — "
                    "already flush, no ramp",
                )
                continue
            # The ramp is exactly long enough to shed the rise at the cap.
            length_m = min(rise / grade, max_length_m)
            # Source order per the owner (2026-07-31): the PACK's own
            # roads first because they align best with the pack's own
            # objects, OSM as the fallback — and the fallback is tried
            # PER END, not per bridge, since a pack network can cover one
            # approach and miss the other (measured: OTHH Bridge_04
            # end 0 ramps from the DSF network, end 1 has no outward DSF
            # piece at all).
            sources = [road_lines]
            if osm_road_lines and osm_road_lines is not road_lines:
                sources.append(osm_road_lines)
            if any(
                _emit_corridor_for_footprint(
                    layout, dem, tile_lat, tile_lon, meters_to_lat_lon,
                    footprint, deck_end_elevation, source,
                    road_width_m, ramp_step_m, length_m,
                    crossing_union=crossing_union,
                    emitted_registry=emitted_registry,
                    outward=outward,
                    fill_grade=grade,
                    ramp_ref="object_bridge_ramp",
                )
                for source in sources
            ):
                span_emitted = True
                UI.vprint(
                    1,
                    f"   [object-bridge] bridge ramp: end {end_index} of "
                    f"{bridge.object_resources} climbs {rise:.2f} m over "
                    f"{length_m:.0f} m at {grade * 100:.1f}% to "
                    f"{deck_end_elevation:.2f} m",
                )
            else:
                # Silent-zero rule: a road exists but no quad was born.
                UI.vprint(
                    1,
                    f"   [object-bridge] bridge ramp: end {end_index} of "
                    f"{bridge.object_resources} emitted NOTHING (rise "
                    f"{rise:.2f} m, no outward road piece within reach) "
                    "— the deck end is NOT made flush",
                )
        if span_emitted:
            n_spans += 1
    return n_spans


def insert_bridge_profile_pins(layout, dem, tile_lat, tile_lon) -> int:
    """Feature B stage 2, step 2 (spec section 3.2, amendment A4):
    per-vertex profile pins across each PROFILE_CARRIED span — pavement
    ring vertices inside the deck footprint are hard-pinned to
    ``grade_law.bridge_profile_pin_elevation_m`` (datum + profile at the
    vertex's along-axis position), the runway-profile per-vertex
    mechanism.  Ring vertices are also inserted where rings cross the
    span-end abutment lines so the pins start exactly at the deck tips.
    Returns the number of pinned vertices."""
    classification = _object_bridge_classification(layout)
    if classification is None:
        return 0
    from .grade_law import (
        bridge_deck_end_pin_elevation_m,
        bridge_profile_pin_elevation_m,
    )
    from .object_terrain_features import PROFILE_CARRIED
    to_meters, _meters_to_lat_lon = _local_meter_projections(layout.anchor)
    total_pinned = 0
    for bridge in classification.bridges:
        if bridge.contract != PROFILE_CARRIED:
            continue
        datum = _bridge_datum_elevation_m(bridge, dem, tile_lat, tile_lon)
        if datum is None:
            continue
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is None:
            continue
        abutment_lines = _abutment_lines_layout_meters(bridge, layout)
        # Axis for along-position: start-end abutment midpoint → far-end
        # abutment midpoint (the profile's along coordinates are measured
        # from the deck rectangle's start edge; the law clamps outside the
        # sampled range).
        if len(abutment_lines) < 2:
            continue
        start_mid = abutment_lines[0].interpolate(0.5, normalized=True)
        far_mid = abutment_lines[1].interpolate(0.5, normalized=True)
        axis_length = math.hypot(
            far_mid.x - start_mid.x, far_mid.y - start_mid.y
        )
        if axis_length < 1.0:
            continue
        axis_unit = (
            (far_mid.x - start_mid.x) / axis_length,
            (far_mid.y - start_mid.y) / axis_length,
        )
        # Span-end insertion first (deck-tip pins).
        for end_index, line in enumerate(abutment_lines):
            end_y = (
                bridge.deck_end_elevations_y_m[end_index]
                if end_index < len(bridge.deck_end_elevations_y_m)
                else bridge.deck_top_y_m
            )
            end_pin = bridge_deck_end_pin_elevation_m(datum, end_y)
            for shape_index, shape in enumerate(list(layout.shapes)):
                if shape.role not in _BRIDGE_PIN_ROLES:
                    continue
                if shape.polygon is None or shape.polygon.is_empty:
                    continue
                try:
                    if not shape.polygon.exterior.intersects(line):
                        continue
                except _GEOM_EXC:
                    continue
                total_pinned += _pin_shape_vertices_on_line(
                    layout, shape_index, line, end_pin
                )
        # Interior per-vertex profile pins.
        pinned_interior = 0
        for shape in layout.shapes:
            if shape.role not in _BRIDGE_PIN_ROLES:
                continue
            if shape.polygon is None or shape.polygon.is_empty:
                continue
            try:
                if not shape.polygon.intersects(footprint):
                    continue
            except _GEOM_EXC:
                continue
            ring = list(shape.polygon.exterior.coords)
            if ring and ring[0] == ring[-1]:
                ring = ring[:-1]
            node_altitudes = (
                list(shape.node_altitudes[:len(ring)])
                if shape.node_altitudes else None
            )
            changed = False
            for vertex_index, (x, y) in enumerate(ring):
                try:
                    if not footprint.contains(Point(x, y)):
                        continue
                except _GEOM_EXC:
                    continue
                along = (
                    (x - start_mid.x) * axis_unit[0]
                    + (y - start_mid.y) * axis_unit[1]
                )
                pin_value = bridge_profile_pin_elevation_m(
                    datum, bridge.deck_top_profile, along
                )
                _record_pin(layout, x, y, pin_value)
                if (node_altitudes is not None
                        and vertex_index < len(node_altitudes)):
                    node_altitudes[vertex_index] = round(pin_value, 2)
                    changed = True
                pinned_interior += 1
            if changed and node_altitudes is not None:
                shape.node_altitudes = node_altitudes + [node_altitudes[0]]
        if pinned_interior:
            UI.vprint(
                2,
                f"   [object-bridge] {pinned_interior} profile pin(s) "
                f"across PROFILE_CARRIED span {bridge.object_resources}",
            )
        total_pinned += pinned_interior
    return total_pinned


def _emit_deck_lip_weld_strips(layout, bridge, deck_box, trench_polygon,
                               road_exit_corridor, causeway_parts, datum,
                               born_graded) -> int:
    """Deck-lip weld strips (user directive 2026-07-15: aircraft must
    taxi SMOOTHLY onto the decks — the resumed pavement must slightly
    OVERLAP the deck-elevation terrain, not merely touch it; at
    mesh-triangulation level edge-to-edge contact still leaves sliver
    triangles).

    Hard decks only: ruling R8 cuts the pavement AT the deck-box
    boundary while the trench plate is inset :data:`_TRENCH_INSET_M`,
    leaving a ring of raw mesh whose triangles dive to the trench floor
    right at the lip (measured KBNA taxiway-L: pavement pinned 167.0,
    trench edge 0.8-1.2 m away at 161.01 — the owner-visible gap onto
    the deck).  For every rim segment fronted by airside pavement
    (:data:`_BRIDGE_PIN_ROLES` within :data:`_DECK_WELD_FRONT_REACH_M`
    of the box — service roads descend through the road-exit cut and
    never weld to the deck), a strip is born at the deck-top PROFILE
    law value (``grade_law.bridge_profile_pin_elevation_m`` along the
    abutment-to-abutment axis — the deck-end pin law at the ends by
    construction), spanning from :data:`_CAUSEWAY_INWARD_OVERLAP_M`
    inside the box (preserving the R2 node-split wall against the
    trench) out to :data:`_DECK_WELD_OVERLAP_M` INSIDE the pavement.
    The fronting pavement ring vertices inside the overlap band are
    pinned at the same law value, so the overlap is coplanar and
    invisible.  The emitted causeway plates are cut out (the plates
    stay mutually exclusive); road faces get no strips by construction
    (the zone is pavement-driven and roads never cross airside pavement
    at grade), and pavement vertices inside the road-exit corridor are
    never pinned.  Returns the number of strip parts."""
    if not getattr(bridge, "hard_deck", False):
        # Cosmetic decks keep their pavement over the box (R2 pavement
        # wins) — no lip cut, nothing to weld.
        return 0
    from .grade_law import bridge_profile_pin_elevation_m
    from .layout import ROLE_BRIDGE_CAUSEWAY
    abutment_lines = _abutment_lines_layout_meters(
        bridge, layout, extension_fraction=0.0)
    if len(abutment_lines) < 2:
        return 0
    start_mid = abutment_lines[0].interpolate(0.5, normalized=True)
    far_mid = abutment_lines[1].interpolate(0.5, normalized=True)
    axis_x = far_mid.x - start_mid.x
    axis_y = far_mid.y - start_mid.y
    axis_norm = math.hypot(axis_x, axis_y)
    if axis_norm < 1.0:
        return 0
    axis_x /= axis_norm
    axis_y /= axis_norm
    profile = list(bridge.deck_top_profile or [])

    def _lip_value(x, y):
        along = (x - start_mid.x) * axis_x + (y - start_mid.y) * axis_y
        return bridge_profile_pin_elevation_m(datum, profile, along)

    fronting_indices = []
    for shape_index, shape in enumerate(layout.shapes):
        if shape.role not in _BRIDGE_PIN_ROLES:
            continue
        if shape.polygon is None or shape.polygon.is_empty:
            continue
        try:
            if (shape.polygon.distance(deck_box)
                    > _DECK_WELD_FRONT_REACH_M):
                continue
        except _GEOM_EXC:
            continue
        fronting_indices.append(shape_index)
    if not fronting_indices:
        return 0
    try:
        pavement_union = unary_union(
            [layout.shapes[i].polygon for i in fronting_indices])
        # Rim inside the box, down to the causeway-inward depth — only
        # the portions a fronting pavement edge actually faces.
        inner_rim = deck_box.difference(
            deck_box.buffer(-_CAUSEWAY_INWARD_OVERLAP_M))
        inner_rim = inner_rim.intersection(
            pavement_union.buffer(_DECK_WELD_FRONT_REACH_M))
        # The coplanar overlap: reach into the pavement past its cut.
        overlap_band = pavement_union.intersection(
            deck_box.buffer(_DECK_WELD_OVERLAP_M))
        strip = unary_union([inner_rim, overlap_band])
        if trench_polygon is not None:
            # R2 node-split wall: keep the same clearance to the trench
            # the causeway keeps (> the 0.5 m node-interning tolerance).
            strip = strip.difference(trench_polygon.buffer(
                _TRENCH_INSET_M - _CAUSEWAY_INWARD_OVERLAP_M))
        # The road-exit corridor is deliberately NOT subtracted from the
        # strip geometry: under the deck the road runs on the trench
        # floor a storey BELOW the lip strips (measured KBNA: the
        # trench-width Donelson corridor covers the whole box interior
        # and its polygon deleted every long-side strip), and the strip
        # zone is pavement-driven — roads never cross airside pavement
        # at grade, so no strip can land on the road's actual ground
        # opening at the trench mouths.  The pin loop below still skips
        # any pavement vertex inside the corridor (belt and braces).
        for causeway_part in causeway_parts:
            strip = strip.difference(causeway_part)
    except _GEOM_EXC:
        return 0
    strip_parts = list(strip.geoms) if hasattr(strip, "geoms") else [strip]
    # A strip wrapping the whole box is an ANNULUS (exterior + hole over
    # the trench); ring emission is exterior-only and would fill the
    # hole at the lip value, damming the corridor.  Break the loop with
    # a hair-line cut along the deck axis (crosses the rim at both
    # ends; the 0.1 m slot is negligible and object-hidden).
    simply_connected = []
    for part in strip_parts:
        if part.geom_type == "Polygon" and part.interiors:
            try:
                axis_cut = LineString([
                    (start_mid.x - axis_x * 5.0, start_mid.y - axis_y * 5.0),
                    (far_mid.x + axis_x * 5.0, far_mid.y + axis_y * 5.0),
                ]).buffer(0.05)
                split = part.difference(axis_cut)
                simply_connected.extend(
                    split.geoms if hasattr(split, "geoms") else [split])
                continue
            except _GEOM_EXC:
                continue
        simply_connected.append(part)
    emitted = 0
    for part in simply_connected:
        if (part.geom_type != "Polygon" or part.is_empty
                or part.area < 1.0 or part.interiors):
            continue
        try:
            born_graded(part, ROLE_BRIDGE_CAUSEWAY,
                        "object_bridge_deck_weld", _lip_value)
        except _GEOM_EXC:
            continue
        emitted += 1
    if not emitted:
        return 0
    # Pin the fronting pavement ring vertices inside the overlap band at
    # the same law value (node_altitudes stamp + solver pin registry) —
    # both surfaces of the overlap are then coplanar by construction.
    try:
        pin_zone = deck_box.buffer(_DECK_WELD_OVERLAP_M + 0.05)
    except _GEOM_EXC:
        return emitted
    for shape_index in fronting_indices:
        shape = layout.shapes[shape_index]
        try:
            ring = list(shape.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        node_altitudes = (
            list(shape.node_altitudes[:len(ring)])
            if shape.node_altitudes else None)
        changed = False
        for vertex_index, (x, y) in enumerate(ring):
            vertex_point = Point(x, y)
            if not pin_zone.covers(vertex_point):
                continue
            if (road_exit_corridor is not None
                    and road_exit_corridor.covers(vertex_point)):
                continue  # the road descends through the exit cut
            value = round(float(_lip_value(x, y)), 2)
            _record_pin(layout, x, y, value)
            if (node_altitudes is not None
                    and vertex_index < len(node_altitudes)):
                node_altitudes[vertex_index] = value
            changed = True
        if changed and node_altitudes is not None:
            shape.node_altitudes = node_altitudes + [node_altitudes[0]]
    return emitted


def build_bridge_layout_shapes(layout, dem, tile_lat, tile_lon):
    """User ruling R12 — bridge terrain as FIRST-CLASS layout shapes,
    born pre-solve with law values, immutable thereafter (the one-solve
    doctrine applied fully; replaces the post-solve trench emission and
    the late causeway plates).

    Per corridor (DECK_CARRIED / cosmetic, not road-carried) bridge:

    * **Building-pad removal** (the never-stack rule): the Phase 1 DSF
      building machinery footprint-extracts the bridge OBJECTS
      themselves into flat building pads over the decks (KBNA:
      ``building2`` covered the taxiway-L footprint 2959/2959 m² — the
      measured coverer that ate the trench in every gated build).  A
      building pad mostly inside ANY classified bridge footprint is a
      stacking artifact and is removed, logged per pad.
    * **Ruling R8 flush seat**: pavement cut over a genuine hard deck
      (``cut_pavement_over_footprint``); a cosmetic deck keeps its
      pavement (R2 pavement wins) and the trench carves around it.
    * **Trench** (:data:`layout.ROLE_BRIDGE_TRENCH`): the under-deck
      footprint inset 0.6 m (> the 0.5 m weld tolerance — the R2
      node-split wall against the causeway lip), densified to ~5 m
      vertex spacing, per-vertex ``node_altitudes`` at the law floor
      (``_bridge_corridor_floor_m``, amendment A10 geometry-driven).
    * **Causeway** (:data:`layout.ROLE_BRIDGE_CAUSEWAY`): the flat plate
      from each abutment lip back along the outward approach axis to
      the first pavement edge (+2 m weld overlap, clipped by the
      pavement union — R2), capped at
      ``config.BRIDGE_CAUSEWAY_MAX_LENGTH_M``; per-vertex
      ``node_altitudes`` at ``grade_law.bridge_deck_end_pin_elevation_m``
      (the SAME law function as the pins and the validator).

    Both roles are outside every mutation pass by construction: not
    pavement (solver never reshapes them), not road features (deconflict
    never walks them), no within-shape grade rule
    (``config.ROLE_GRADE_LIMITS`` ``None``).  Returns
    ``(trench_count, causeway_count, pads_removed)``; all zeros when the
    gate is off (no classification cached)."""
    classification = _object_bridge_classification(layout)
    if classification is None:
        return 0, 0, 0
    from .grade_law import bridge_deck_end_pin_elevation_m
    from .layout import (
        ROLE_BRIDGE_CAUSEWAY,
        ROLE_BRIDGE_TRENCH,
        ROLE_BUILDING,
        ROLE_SERVICE_JUNCTION,
        ROLE_SERVICE_ROAD,
    )
    to_meters, _meters_to_lat_lon = _local_meter_projections(layout.anchor)

    # ── Building-pad removal over EVERY classified bridge footprint ──
    all_footprints = []
    for bridge in classification.bridges:
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is not None:
            all_footprints.append((bridge, footprint))
    pads_removed = 0
    # Captured full-structure footprints (defect C, 2026-07-15): the
    # removed pads ARE the objects' FULL solid footprints
    # (``read_dsf_object_buildings`` → ``structure_ring``) — the portal
    # collar needs that full lateral extent (the deck-face union is
    # 6.3 m wide against the 13.3 m emitted back side at KBNA portal
    # 0), so keep the polygons per matched bridge instead of dropping
    # them on the floor.
    full_footprints_by_bridge_id: dict[int, list] = {}
    if all_footprints:
        kept_shapes = []
        for shape in layout.shapes:
            if (shape.role != ROLE_BUILDING
                    or shape.polygon is None or shape.polygon.is_empty):
                kept_shapes.append(shape)
                continue
            removed = False
            for bridge, footprint in all_footprints:
                try:
                    overlap = shape.polygon.intersection(footprint).area
                except _GEOM_EXC:
                    continue
                # Either-side criterion (measured, KBNA): the taxiway-L
                # pad is 100 % inside its footprint, but the Crossing /
                # Murfreesboro pads are LARGER than their deck boxes
                # (overlap 71 % / 98 % / 33 % of the FOOTPRINT while
                # under half of the pad) — a pad covering a third of a
                # deck box is still the bridge object's own pad.
                if (overlap >= 0.5 * shape.polygon.area
                        or overlap >= 0.3 * footprint.area):
                    pads_removed += 1
                    removed = True
                    full_footprints_by_bridge_id.setdefault(
                        id(bridge), []).append(shape.polygon)
                    UI.vprint(
                        1,
                        "   [object-bridge] removed building pad "
                        f"{shape.ref!r} over the deck of "
                        f"{bridge.object_resources} (terrain-to-object "
                        "corrections never stack)",
                    )
                    break
            if not removed:
                kept_shapes.append(shape)
        if pads_removed:
            layout.shapes = kept_shapes

    # Portal-pair detection runs HERE — the first Feature B consumer in
    # the pipeline — so every later partition call (pins, corridors,
    # validators) sees the same diversion via the layout cache.
    portal_pairs = _detect_tunnel_portal_pairs(
        layout, dem, tile_lat, tile_lon
    )
    (corridor_bridges, _suppress, _refused, _road_carried,
     _portal_records) = (
        _partition_bridges_for_corridors(classification, layout)
    )
    if not corridor_bridges and not portal_pairs:
        return 0, 0, pads_removed

    weld_roles = _BRIDGE_PIN_ROLES | {
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
    }

    def _pavement_union():
        polygons = [
            shape.polygon for shape in layout.shapes
            if shape.role in weld_roles
            and shape.polygon is not None and not shape.polygon.is_empty
        ]
        try:
            return unary_union(polygons) if polygons else None
        except _GEOM_EXC:
            return None

    def _born_flat(polygon, role, ref, elevation, record_pins=True):
        """Bind :func:`born_flat_solver_plate` to this layout (the shared
        R12 flat-plate birth primitive; see its docstring)."""
        return born_flat_solver_plate(layout, polygon, role, ref,
                                      elevation, record_pins=record_pins)

    def _born_graded(polygon, role, ref, altitude_at, record_pins=True):
        """Like :func:`_born_flat`, but every ring vertex takes its OWN
        law value from ``altitude_at(x, y)`` — a TRANSITION plate (the
        portal collar): crown-high at the object-hidden inner face,
        DEM-low at the exposed outer rim, so its perimeter feathers into
        the surrounding ground instead of standing as a vertical
        stretched-texture wall.  With ``record_pins`` (the default) each
        vertex is registered as a hard solver pin at its own value,
        exactly like ``_born_flat``; hanging-face portals pass False —
        their plates are DECOUPLED law plates (the Feature-A lesson:
        deep pinned plates couple through the one-solve and drag the
        neighbouring pavement toward the mouth floor)."""
        try:
            dense = polygon.segmentize(3.0)
        except (AttributeError, _GEOM_EXC):
            dense = polygon
        ring = list(dense.exterior.coords)
        if len(ring) < 4:
            return 0
        node_altitudes = [
            round(float(altitude_at(x, y)), 2) for x, y in ring
        ]
        # shapely closes exterior rings, so ring[0] == ring[-1]; keep the
        # closing altitude byte-identical to the first vertex's.
        if ring[0] == ring[-1]:
            node_altitudes[-1] = node_altitudes[0]
            vertex_count = len(ring) - 1
        else:
            vertex_count = len(ring)
        if record_pins:
            for (x, y), altitude in zip(
                    ring[:vertex_count], node_altitudes[:vertex_count]):
                _record_pin(layout, x, y, altitude)
        layout.shapes.append(BuiltShape(
            polygon=dense,
            role=role,
            ref=ref,
            node_altitudes=node_altitudes))
        return vertex_count

    maximum_length = float(_CFG.BRIDGE_CAUSEWAY_MAX_LENGTH_M)
    capture_band = float(_CFG.BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M)
    n_trench = 0
    n_causeway = 0

    # ── Tunnel portal mouths (user ruling 2026-07-10, runway-02C class):
    # a paired portal gets NO bridge treatment.  Its mouth is born as a
    # flat plate at the ROAD grade over the portal footprint — the object
    # drapes at terrain(anchor) = mouth floor, so it sits partly
    # submerged with its bottom aligned to the road descending to it,
    # and the plate's rim welds to the natural hill (level with the
    # object top at the face, rising to the runway beyond).  The ground
    # between the two portals is left UNTOUCHED — the hill carries the
    # runway; the outward road corridor is emitted by the corridors
    # stage (climbing away from the mouth by construction).
    # Airside pavement union for the FACE-portal plate clips (user JOSM
    # review 2026-07-18d: at EGGW the crown/collar sat 84-98 % under the
    # taxiway junctions over the bore — pavement owns its ground, R2).
    airside_pavement_union = _pavement_union() if portal_pairs else None
    for pair in portal_pairs:
        for portal in pair["portals"]:
            mouth_floor = portal.get("mouth_floor_m")
            footprint = portal.get("footprint")
            if mouth_floor is None or footprint is None:
                continue
            # FACE portals (user 2026-07-18, screenshots): the crown
            # split, forward sweep and collar clip must align with THE
            # FACE, not the pair axis — a road can enter the portal
            # obliquely (EGGW: 58° crossing), and splitting by the pair
            # axis draws the crown edge diagonally across the flat face
            # object.  Redirect this portal's working ``outward`` to
            # the FACE NORMAL (sign-matched to the road side) before
            # any plate geometry is derived; the road-following mouth
            # floor was already sampled along the true road direction
            # at pairing time and is unaffected.
            if pair.get("is_face") and portal.get("outward") is not None:
                face_line_bearing = math.radians(float(getattr(
                    portal["bridge"], "face_line_bearing_degrees", 0.0)))
                face_along = (math.sin(face_line_bearing),
                              math.cos(face_line_bearing))
                face_normal = (-face_along[1], face_along[0])
                road_outward = portal["outward"]
                if (face_normal[0] * road_outward[0]
                        + face_normal[1] * road_outward[1]) < 0.0:
                    face_normal = (-face_normal[0], -face_normal[1])
                portal["outward"] = face_normal
            # Crown split (user ruling 2026-07-14): the buried half of
            # the footprint — the side facing the runway over the
            # tunnel body — is seated at the OBJECT TOP (mouth floor +
            # deck top), so the terrain runway-side of the portal rides
            # over the tunnel roof instead of dipping to road grade.
            # Only the open-mouth half stays at the road.
            deck_top_metres = float(
                portal["bridge"].deck_top_y_m or 0.0)
            mouth_geometry = footprint
            crown_geometry = None
            mouth_half_plane = None
            if (_CFG.TUNNEL_PORTAL_CROWN and deck_top_metres > 0.5
                    and portal.get("outward") is not None):
                mouth_half, buried_half, mouth_half_plane = (
                    _split_portal_footprint(footprint, portal["outward"]))
                if (mouth_half is not None and buried_half is not None
                        and buried_half.area >= 4.0):
                    mouth_geometry = mouth_half
                    crown_geometry = buried_half
                    # NODE-SPLIT THE FACE MEETING for face portals
                    # (user 2026-07-18, screenshots): the mouth's back
                    # edge and the crown's front edge lie on the SAME
                    # face line — interned into one ~0.5 m node bucket
                    # the first writer's road-grade value wins and the
                    # crown renders as a RAMP across its whole depth
                    # (measured EGGW v18: 148.5 → 154.8 over the crown
                    # zone instead of a flat 157.8 shelf).  Trim the
                    # crown 1.0 m off the face so the two rows stay
                    # distinct nodes: mouth at road grade, crown flat
                    # at the object top, a near-vertical wall between
                    # them that the face object itself covers.  KBNA
                    # structural portals keep the coincident meeting —
                    # their objects hide it by design.
                    if pair.get("is_face") and mouth_half_plane is not None:
                        try:
                            outward_vector = portal["outward"]
                            face_setback = shapely_translate(
                                mouth_half_plane,
                                xoff=-outward_vector[0] * 1.0,
                                yoff=-outward_vector[1] * 1.0)
                            trimmed = crown_geometry.difference(
                                face_setback)
                            if (trimmed.geom_type == "MultiPolygon"
                                    and not trimmed.is_empty):
                                trimmed = max(
                                    trimmed.geoms,
                                    key=lambda part: part.area)
                            if (trimmed.geom_type == "Polygon"
                                    and not trimmed.is_empty
                                    and trimmed.area >= 4.0):
                                crown_geometry = trimmed
                        except _GEOM_EXC:
                            pass
            # Defect C (2026-07-15): the collar derives its lateral
            # extent from the object's FULL solid footprint (the
            # captured never-stack building pad), not the deck-face
            # union — measured KBNA: collars covered 86-87 % of the
            # portal back width, one side truncated by up to 8 m.
            # Clamped to the footprint's neighbourhood: the pads flow
            # through the building CLUSTERING passes and may be merged
            # with neighbours.
            plain_mouth_geometry = mouth_geometry
            anchor_seat = None
            anchor_seat_keep_out = None
            full_footprint = None
            captured_pads = full_footprints_by_bridge_id.get(
                id(portal["bridge"]), [])
            if captured_pads:
                try:
                    candidate = unary_union(
                        [footprint] + list(captured_pads)
                    ).intersection(footprint.buffer(25.0))
                    if candidate.geom_type == "MultiPolygon":
                        candidate = max(
                            candidate.geoms,
                            key=lambda geometry: geometry.area)
                    if (candidate.geom_type == "Polygon"
                            and not candidate.is_empty):
                        full_footprint = candidate
                except _GEOM_EXC:
                    full_footprint = None
            # Persist on the cached pair record (crossing influence zone,
            # spec Phase 1): the zone is published from the pairs AFTER
            # this function returns, and its portal pieces / collar rings
            # must reach the FULL solid extent the collar is cut from.
            portal["full_footprint"] = full_footprint
            # X-Plane drapes the portal object at terrain(anchor) — the
            # ROAD-GRADE plate must COVER the anchor point, or the
            # object seats on whatever solves beside it (a crown plate
            # under the anchor would LIFT the object by the deck top).
            # INVERTED for a portal-FACE pair (user 2026-07-17, EGGW
            # class): the face geometry HANGS BELOW its origin, so the
            # anchor must read DECK grade (the crown) — seating it on
            # the road-grade mouth would sink the whole face by the
            # face height.
            _face_seated = bool(pair.get("is_face")) or bool(
                getattr(portal["bridge"], "face_hangs_below", False))
            try:
                anchor_longitude, anchor_latitude = (
                    portal["bridge"].anchor_longitude_latitude
                )
                anchor_point = Point(
                    to_meters(anchor_longitude, anchor_latitude)
                )
                if _face_seated:
                    # SEAT REDUNDANCY (user JOSM review 2026-07-18d): an
                    # anchor lying UNDER the airside pavement needs no
                    # terrain seat at all — the pavement solves at the
                    # airside level the crown raises to, so the object
                    # drapes at deck grade off the pavement itself, and
                    # a seat there would double-grade the junction (the
                    # last 19-22 m2 plate-vs-pavement overlaps at EGGW).
                    _anchor_on_pavement = False
                    if airside_pavement_union is not None:
                        try:
                            _anchor_on_pavement = (
                                airside_pavement_union.covers(anchor_point))
                        except _GEOM_EXC:
                            _anchor_on_pavement = False
                    if (not _anchor_on_pavement
                            and footprint.distance(anchor_point) <= 30.0):
                        # FACE-ALIGNED anchor seat (user screenshots
                        # 2026-07-18b, EGGW): the previous 5 m ROUND
                        # disk protruded 5 m into the road at deck
                        # grade, and the mouth hole cut from the SAME
                        # disk shared its rim coordinates — one ~0.5 m
                        # mesh bucket per rim node, altitude decided by
                        # first-writer interning.  Mid-road it rendered
                        # as a ~10 m arc-shaped tower at both EGGW
                        # mouths.  Build a rectangle in the FACE frame
                        # instead — a minimal outward lip so the
                        # anchor's drape triangle stays wholly at deck
                        # grade, square edges flush against the face —
                        # and cut the mouth back an extra clearance
                        # margin so no seat node shares a bucket with a
                        # mouth node (the v18 face-meeting trap).
                        seat_outward = portal.get("outward")
                        if seat_outward is not None:
                            along_face = (-seat_outward[1],
                                          seat_outward[0])
                            half_width = float(
                                _CFG.PORTAL_FACE_ANCHOR_SEAT_HALF_WIDTH_M)
                            outward_lip = float(
                                _CFG.PORTAL_FACE_ANCHOR_SEAT_OUTWARD_M)
                            inward_reach = float(
                                _CFG.PORTAL_FACE_ANCHOR_SEAT_INWARD_M)
                            front = (
                                anchor_point.x
                                + seat_outward[0] * outward_lip,
                                anchor_point.y
                                + seat_outward[1] * outward_lip)
                            back = (
                                anchor_point.x
                                - seat_outward[0] * inward_reach,
                                anchor_point.y
                                - seat_outward[1] * inward_reach)
                            anchor_seat = Polygon([
                                (front[0] + along_face[0] * half_width,
                                 front[1] + along_face[1] * half_width),
                                (front[0] - along_face[0] * half_width,
                                 front[1] - along_face[1] * half_width),
                                (back[0] - along_face[0] * half_width,
                                 back[1] - along_face[1] * half_width),
                                (back[0] + along_face[0] * half_width,
                                 back[1] + along_face[1] * half_width),
                            ])
                            # An off-pavement anchor near the pavement
                            # edge: the seat's inward reach may cross
                            # under the junction — trim it back with the
                            # 0.6 m node-split margin, UNLESS that would
                            # eat the anchor's own drape neighbourhood
                            # (coverage beats overlap cleanliness; user
                            # JOSM review 2026-07-18d).  With the seat's
                            # front edge ON the face line the anchor
                            # legitimately sits on the exterior — the
                            # guard is that the front edge SURVIVES
                            # locally: the trimmed part still covers the
                            # anchor and keeps most of a 0.6 m half-disk
                            # behind it.
                            if airside_pavement_union is not None:
                                try:
                                    _seat_trim = anchor_seat.difference(
                                        airside_pavement_union.buffer(
                                            0.6, join_style=2,
                                            mitre_limit=2.0))
                                    _seat_parts = [
                                        part for part in getattr(
                                            _seat_trim, "geoms",
                                            [_seat_trim])
                                        if part.geom_type == "Polygon"
                                        # covers() is float-fragile for
                                        # the on-edge anchor; micron
                                        # distance is the robust test.
                                        and part.distance(anchor_point)
                                        < 1e-6]
                                    if _seat_parts and (
                                            _seat_parts[0].intersection(
                                                anchor_point.buffer(0.6))
                                            .area >= 0.4):
                                        anchor_seat = _seat_parts[0]
                                except _GEOM_EXC:
                                    pass
                            anchor_seat_keep_out = anchor_seat.buffer(
                                float(_CFG.
                                      PORTAL_FACE_ANCHOR_SEAT_CLEARANCE_M),
                                join_style=2, mitre_limit=2.0)
                        else:
                            # No face frame to align to — fall back to
                            # the round seat rather than leave the
                            # anchor over the road-grade mouth.
                            anchor_seat = anchor_point.buffer(5.0)
                            anchor_seat_keep_out = anchor_seat
                        mouth_geometry = mouth_geometry.difference(
                            anchor_seat_keep_out)
                        if mouth_geometry.geom_type != "Polygon":
                            mouth_geometry = max(
                                (part for part in getattr(
                                    mouth_geometry, "geoms", [])
                                 if part.geom_type == "Polygon"),
                                key=lambda part: part.area,
                                default=None)
                        if crown_geometry is not None:
                            crown_geometry = unary_union(
                                [crown_geometry, anchor_seat])
                            if crown_geometry.geom_type != "Polygon":
                                crown_geometry = (
                                    crown_geometry.convex_hull)
                        else:
                            crown_geometry = anchor_seat
                        if mouth_geometry is None \
                                or mouth_geometry.is_empty:
                            mouth_geometry = None
                elif (not mouth_geometry.covers(anchor_point)
                        and footprint.distance(anchor_point) <= 30.0):
                    anchor_seat = anchor_point.buffer(5.0)
                    anchor_seat_keep_out = anchor_seat
                    mouth_geometry = unary_union(
                        [mouth_geometry, anchor_seat]
                    )
                    if mouth_geometry.geom_type != "Polygon":
                        mouth_geometry = mouth_geometry.convex_hull
                    if crown_geometry is not None:
                        crown_geometry = crown_geometry.difference(
                            anchor_seat)
                        if crown_geometry.geom_type != "Polygon":
                            crown_geometry = max(
                                (part for part in getattr(
                                    crown_geometry, "geoms", [])
                                 if part.geom_type == "Polygon"),
                                key=lambda part: part.area,
                                default=None)
                        if (crown_geometry is not None
                                and (crown_geometry.is_empty
                                     or crown_geometry.area < 4.0)):
                            crown_geometry = None
            except (_GEOM_EXC, KeyError, TypeError):
                pass
            # PAVEMENT WINS over face-portal plates (user JOSM review
            # 2026-07-18d, ruling R2 applied to the portal family): at
            # EGGW the synthesized plate rectangles land 84-98 % under
            # the taxiway junctions crossing the bore — the junctions
            # own that ground (the raise pass already matches the crown
            # to the solved airside there), and double-graded ground
            # rendered as the JOSM overlap mess.  Clip mouth and crown
            # against the airside union with a 0.6 m node-split margin;
            # the ANCHOR SEAT is exempt (the object drapes at
            # terrain(anchor) — it must stay covered at deck grade).
            # KBNA-class structural portals keep their accepted
            # geometry (no clip).
            if (pair.get("is_face")
                    and airside_pavement_union is not None):
                try:
                    _pavement_keep_out = airside_pavement_union.buffer(
                        0.6, join_style=2, mitre_limit=2.0)
                    if (mouth_geometry is not None
                            and not mouth_geometry.is_empty):
                        _clipped_mouth = mouth_geometry.difference(
                            _pavement_keep_out)
                        if anchor_seat_keep_out is not None:
                            _clipped_mouth = _clipped_mouth.difference(
                                anchor_seat_keep_out)
                        _mouth_parts = [
                            part for part in getattr(
                                _clipped_mouth, "geoms", [_clipped_mouth])
                            if part.geom_type == "Polygon"
                            and part.area >= 4.0]
                        mouth_geometry = (
                            max(_mouth_parts, key=lambda p: p.area)
                            if _mouth_parts else None)
                    if (crown_geometry is not None
                            and not crown_geometry.is_empty):
                        _clipped_crown = crown_geometry.difference(
                            _pavement_keep_out)
                        if anchor_seat is not None:
                            _clipped_crown = unary_union(
                                [_clipped_crown, anchor_seat])
                        if _clipped_crown.is_empty:
                            crown_geometry = None
                        else:
                            crown_geometry = _clipped_crown
                except _GEOM_EXC:
                    pass
            # Hanging-face portals emit DECOUPLED law plates (the
            # Feature-A lesson, measured twice: solver-pinned deep
            # plates couple through the one-solve and drag the
            # neighbouring pavement toward the mouth floor — EGGW's
            # taxiway over the bore solved 2.6 m low with pinned
            # ROLE_BRIDGE_TRENCH mouths).  ``ROLE_TUNNEL_TRENCH`` is
            # the decoupled LAW-tier role: decimation-exempt,
            # force_per_node, never in the solver's pavement set.
            portal_plate_role = (ROLE_TUNNEL_TRENCH if _face_seated
                                 else ROLE_BRIDGE_TRENCH)
            portal_plate_pins = not _face_seated
            if mouth_geometry is None or mouth_geometry.is_empty:
                # Face-seated portal whose whole footprint became the
                # crown (thin face footprints): road grade continues in
                # the outward corridor; only the crown seat is emitted.
                vertex_count = 0
            else:
                try:
                    vertex_count = _born_flat(
                        mouth_geometry, portal_plate_role,
                        "object_tunnel_portal_mouth", mouth_floor,
                        record_pins=portal_plate_pins)
                except _GEOM_EXC:
                    continue
            n_trench += 1
            UI.vprint(
                1,
                "   [object-tunnel] portal mouth seated at road grade "
                f"{mouth_floor:.2f} m ({vertex_count} vertices) for "
                f"{portal['bridge'].object_resources}",
            )
            if crown_geometry is None:
                continue
            # User correction 2026-07-14c: the object top includes a
            # parapet/safety wall, so ``mouth + deck_top`` overshoots
            # the ground (KBNA: structure tops 185.0/185.3 against real
            # ground 174/177).  The crown holds the TERRAIN's own height
            # over the buried body.
            #
            # Round-8 fact 2 — TERRAIN-TRUE crown from the SAME
            # production inset DEM: the crown IS the runway embankment
            # riding over the tunnel roof, so seat it at the inset DEM
            # sampled over its OWN BURIED BODY (the crown geometry),
            # NOT at a single point 4 m beyond the buried edge.  That
            # prior mechanism read the mid-hill downslope on each
            # portal's inner face and diverged the two crowns (measured
            # KBNA 02C baseline: east crown 180.34 m vs west 181.32 m
            # over one embankment, each 1.5-1.9 m above its mouth).
            # Sample AT the crown centroid — the reported target — plus
            # a tight interior disk so a lone nodata / spike cell cannot
            # swing the plate, then clamp to a sane band around the
            # mouth (never above the object top, never a DEM dropout).
            crown_elevation = mouth_floor + deck_top_metres
            burial_x = -portal["outward"][0]
            burial_y = -portal["outward"][1]
            centroid_point = footprint.centroid
            buried_extent = 0.0
            try:
                for vertex_x, vertex_y in footprint.exterior.coords:
                    projection = (
                        (vertex_x - centroid_point.x) * burial_x
                        + (vertex_y - centroid_point.y) * burial_y
                    )
                    if projection > buried_extent:
                        buried_extent = projection
            except _GEOM_EXC:
                buried_extent = 0.0
            # ``ground_behind`` is retained ONLY as the collar's
            # outer-target fallback below (used when a collar vertex's
            # own DEM disk is entirely nodata).
            try:
                sample_lat, sample_lon = _meters_to_lat_lon(
                    centroid_point.x + burial_x * (buried_extent + 4.0),
                    centroid_point.y + burial_y * (buried_extent + 4.0),
                )
                ground_behind = _sample_dem(
                    dem, tile_lat, tile_lon, sample_lat, sample_lon
                )
            except _GEOM_EXC:
                ground_behind = None
            crown_centroid = crown_geometry.centroid
            crown_target = None
            try:
                target_lat, target_lon = _meters_to_lat_lon(
                    crown_centroid.x, crown_centroid.y)
                crown_target = _sample_dem(
                    dem, tile_lat, tile_lon, target_lat, target_lon)
            except _GEOM_EXC:
                crown_target = None
            disk_samples = []
            for radius in (2.0, 4.0):
                for step_index in range(6):
                    angle = math.pi * step_index / 3.0
                    try:
                        probe_lat, probe_lon = _meters_to_lat_lon(
                            crown_centroid.x + radius * math.cos(angle),
                            crown_centroid.y + radius * math.sin(angle))
                        sample = _sample_dem(
                            dem, tile_lat, tile_lon, probe_lat, probe_lon)
                    except (_GEOM_EXC, ValueError, TypeError):
                        sample = None
                    if sample is not None:
                        disk_samples.append(float(sample))
            crown_ground = (
                float(crown_target) if crown_target is not None
                else (sum(disk_samples) / len(disk_samples)
                      if disk_samples else None))
            # USER RULING 2026-07-17 — the OBJECT is the terrain
            # authority: its flat roof plane (``mouth_floor +
            # deck_top`` — the cosmetic classifier's dominant elevated
            # plane, parapet caps excluded by area) is the divider
            # between the below-grade road and the at-grade back
            # terrain, so the crown seats NO LOWER than that plane.
            # The DEM stays as an UPWARD override only (a hillside
            # portal buried deeper keeps the higher terrain).  The
            # former DEM-target seating left the Murfreesboro west
            # crown at 171.2 where the object roof is 176.8 — the
            # portal-mouth backside stood exposed toward the runway.
            # (The 2026-07-14c "DEM, not mouth+deck_top" correction
            # predates the mouth-floor fix; with today's mouth floors
            # the roof plane no longer overshoots real ground.)
            object_roof_elevation = mouth_floor + deck_top_metres
            if crown_ground is not None:
                crown_elevation = max(
                    float(crown_ground), object_roof_elevation)
            else:
                crown_elevation = object_roof_elevation
            crown_centroid_lat, crown_centroid_lon = _meters_to_lat_lon(
                crown_centroid.x, crown_centroid.y)
            UI.vprint(
                1,
                "   [object-tunnel] crown target: inset DEM at crown "
                f"centroid @{crown_centroid_lat:.5f},"
                f"{crown_centroid_lon:.5f} = "
                + (f"{crown_target:.2f} m" if crown_target is not None
                   else "nodata")
                + f" (mouth {mouth_floor:.2f}, object top "
                f"{mouth_floor + deck_top_metres:.2f})",
            )
            # The pavement clip can split the crown into parts (the seat
            # plus shoulder pieces flanking the taxiway) — birth each
            # part; the record carries them all for the airside raise.
            crown_part_list = [
                part for part in getattr(
                    crown_geometry, "geoms", [crown_geometry])
                if part.geom_type == "Polygon" and not part.is_empty
                and part.area >= 4.0]
            if not crown_part_list:
                continue
            crown_vertex_count = 0
            crown_shapes = []
            try:
                for crown_part in sorted(
                        crown_part_list, key=lambda p: -p.area):
                    part_count = _born_flat(
                        crown_part, portal_plate_role,
                        "object_tunnel_portal_crown", crown_elevation,
                        record_pins=portal_plate_pins)
                    if part_count:
                        crown_vertex_count += part_count
                        crown_shapes.append(layout.shapes[-1])
            except _GEOM_EXC:
                continue
            if not crown_shapes:
                continue
            # Portal terrain record (user ruling 2026-07-17): the
            # post-solve raise pass (``raise_portal_terrain_to_airside``,
            # called from finalize) lifts crown + collar to the
            # surrounding SOLVED airside level — capture the shape
            # references and blend parameters it needs.  Collar fields
            # are filled in below once computed; a ``continue`` before
            # then leaves a crown-only record, which the raise pass
            # handles.
            if not hasattr(layout, "portal_terrain_records"):
                layout.portal_terrain_records = []
            portal_terrain_record = {
                "crown_shape": crown_shapes[0],
                "crown_shapes": crown_shapes,
                "crown_geometry": crown_geometry,
                "crown_elevation": crown_elevation,
                "mouth_floor": mouth_floor,
                "collar_reach": float(_CFG.TUNNEL_PORTAL_CROWN_COLLAR_M),
                "collar_shapes": [],
                "mouth_geometry": None,
            }
            layout.portal_terrain_records.append(portal_terrain_record)
            n_trench += 1
            UI.vprint(
                1,
                "   [object-tunnel] portal crown seated TERRAIN-TRUE at "
                f"{crown_elevation:.2f} m ({crown_vertex_count} "
                "vertices) — the runway-side rim rides the tunnel "
                "roof",
            )
            # COLLAR (user ruling 2026-07-14; reworked for defect C,
            # 2026-07-15): a band around the BACK and sides of the
            # buried half, held at the crown elevation, so the ground
            # behind the portal keeps the deck/roof height while the
            # road grades down into the mouth on the other side.
            # Clipped to the buried side of the split, so it never
            # reaches the road.
            #
            # Defect C rework — the collar must span the WHOLE back
            # side of the portal OBJECT (measured KBNA: 86-87 %
            # coverage, up to 8 m truncated on one side):
            # * the band source is the FULL solid footprint (captured
            #   never-stack pad), not the disk-bitten crown plate
            #   built from the narrow deck-face union;
            # * the mouth-side clip is a FORWARD SWEEP of the
            #   footprint (translates along +outward over the collar
            #   depth), not the centroid half-plane — the measured
            #   KBNA portals are DIAGONAL bands relative to
            #   ``outward``, so a single global split line leaves the
            #   back side bare at one lateral end (the owner-observed
            #   slivers) while the sweep hugs the band's actual back
            #   edge and wraps the sides;
            # * subtract the PLAIN mouth half plus the anchor seat
            #   keep-out (mouth is the emitted road-grade plate; the
            #   seat is the deck-grade anchor cover) — never
            #   the convex-hull-enlarged mouth, whose hull fill ate
            #   up to 8 m of one collar side;
            # * keep ALL parts >= 4 m² instead of largest-part-only —
            #   coverage is the requirement; the largest-part rule
            #   was defensive against slivers and the 4 m² floor
            #   already handles those.
            if mouth_half_plane is None:
                continue
            outward_vector = portal.get("outward")
            if outward_vector is None:
                continue
            collar_footprint = (
                full_footprint if full_footprint is not None
                else footprint)
            collar_reach = float(_CFG.TUNNEL_PORTAL_CROWN_COLLAR_M)
            try:
                # Sweep length covers the collar reach PLUS the
                # footprint's own outward extent: on a diagonal band a
                # 10 m round buffer near the high-outward corner spills
                # 10-25 m forward of laterals whose own band column
                # sits far back (measured KBNA portal 1: a forward
                # wedge over the first approach quad).
                outward_extent = 0.0
                projections = [
                    (vertex_x * outward_vector[0]
                     + vertex_y * outward_vector[1])
                    for vertex_x, vertex_y
                    in collar_footprint.exterior.coords
                ]
                outward_extent = max(projections) - min(projections)
                sweep_length = collar_reach + outward_extent + 1.0
                sweep_steps = max(8, int(math.ceil(sweep_length / 1.5)))
                forward_sweep = unary_union([
                    shapely_translate(
                        collar_footprint,
                        xoff=outward_vector[0]
                        * sweep_length * step / sweep_steps,
                        yoff=outward_vector[1]
                        * sweep_length * step / sweep_steps,
                    )
                    for step in range(1, sweep_steps + 1)
                ])
                # Face portals get SQUARE collar corners (mitre join):
                # the round buffer's arcs read as curved ridges against
                # a flat straight-topped face object (user 2026-07-18
                # screenshots); KBNA-class structural portals keep the
                # round join against their natural hill.
                if pair.get("is_face"):
                    collar_band = collar_footprint.buffer(
                        collar_reach, join_style=2, mitre_limit=3.0)
                else:
                    collar_band = collar_footprint.buffer(collar_reach)
                collar_geometry = (
                    collar_band
                    .difference(collar_footprint)
                    .difference(footprint)
                    .difference(forward_sweep)
                    .difference(plain_mouth_geometry)
                )
                if anchor_seat_keep_out is not None:
                    collar_geometry = collar_geometry.difference(
                        anchor_seat_keep_out)
                # BACK-ONLY collar for FACE portals (user JOSM review
                # 2026-07-18d): the collar's job is to hold the ground
                # at the higher grade BEHIND the portal wall; terrain in
                # front slopes naturally down to the mouth.  The forward
                # sweep alone missed oblique roads (EGGW: the road
                # enters 25 deg off the face normal, and the south
                # collar's lateral lobe cut into the roadway).  Keep
                # ONLY the strict back half-plane, 1 m behind the face
                # line (matching the crown trim so no collar node lands
                # in the face-line bucket), and yield to airside
                # pavement with the same 0.6 m node-split margin as the
                # crown.  KBNA structural portals keep the sweep-based
                # wrap (accepted state).
                if pair.get("is_face"):
                    _face_centre = footprint.centroid
                    _along_face = (-outward_vector[1], outward_vector[0])
                    _back_reach = 500.0
                    _b0 = (_face_centre.x - outward_vector[0] * 1.0,
                           _face_centre.y - outward_vector[1] * 1.0)
                    back_half_plane = Polygon([
                        (_b0[0] + _along_face[0] * _back_reach,
                         _b0[1] + _along_face[1] * _back_reach),
                        (_b0[0] - _along_face[0] * _back_reach,
                         _b0[1] - _along_face[1] * _back_reach),
                        (_b0[0] - _along_face[0] * _back_reach
                         - outward_vector[0] * 2.0 * _back_reach,
                         _b0[1] - _along_face[1] * _back_reach
                         - outward_vector[1] * 2.0 * _back_reach),
                        (_b0[0] + _along_face[0] * _back_reach
                         - outward_vector[0] * 2.0 * _back_reach,
                         _b0[1] + _along_face[1] * _back_reach
                         - outward_vector[1] * 2.0 * _back_reach),
                    ])
                    collar_geometry = collar_geometry.intersection(
                        back_half_plane)
                    if airside_pavement_union is not None:
                        collar_geometry = collar_geometry.difference(
                            airside_pavement_union.buffer(
                                0.6, join_style=2, mitre_limit=2.0))
                # Round-8 fact 3 — NO collar part on the ROAD side of
                # the mouth face (a diagonal lateral lobe can round-
                # buffer past the forward sweep's end; measured KBNA 02C
                # baseline: a 34 m² lobe 46.7 m in front of the west
                # mouth @36.11196,-86.68564, flat at the crown height).
                # Two frames, both required for a diagonal-band portal:
                # * the PAIR AXIS (``outward``) against the footprint —
                #   the plane of the physical portal face the road
                #   emerges through;
                # * the OPENING AXIS (crown centroid → emitted mouth
                #   centroid) against the emitted MOUTH PLATE — a band
                #   end-lobe hugs the band's own tip BEHIND the pair-
                #   axis front line yet stands past the mouth plate over
                #   the descending road (the measured 20 m² survivor of
                #   the pair-axis clip alone).  Beyond the mouth plate's
                #   own extent along the opening, the terrain belongs to
                #   the road approaches, never the collar.
                collar_geometry = _clip_collar_to_mouth_front(
                    collar_geometry, footprint, outward_vector)
                try:
                    opening_x = (mouth_geometry.centroid.x
                                 - crown_geometry.centroid.x)
                    opening_y = (mouth_geometry.centroid.y
                                 - crown_geometry.centroid.y)
                    opening_norm = math.hypot(opening_x, opening_y)
                    if opening_norm > 0.5:
                        collar_geometry = _clip_collar_to_mouth_front(
                            collar_geometry, mouth_geometry,
                            (opening_x / opening_norm,
                             opening_y / opening_norm))
                except _GEOM_EXC:
                    pass
                # Road-lane clearance: the outward approach corridor —
                # the draped road buffered to the MOUTH-FACE width,
                # outward side only — is the approach chain's ground
                # (the road is offset from the band's centre, so its
                # lane reaches laterally past the band's end where no
                # sweep can exclude it; measured KBNA portal 1: the
                # collar end-lobe covered 201 m² of the first ramp
                # quad and the downstream plate cut left a 13 m²
                # quad-versus-quad overlap).  The collar yields the
                # lane; its BACK band (outward of the centroid split)
                # is untouched by the half-plane intersection.
                lane_lines = _draped_road_centerlines_meters(
                    portal["bridge"],
                    _object_bridge_road_networks(layout),
                    to_meters,
                )
                if lane_lines:
                    centroid_point = footprint.centroid
                    perpendicular = (-outward_vector[1],
                                     outward_vector[0])
                    face_projections = [
                        ((vertex_x - centroid_point.x) * perpendicular[0]
                         + (vertex_y - centroid_point.y)
                         * perpendicular[1])
                        for vertex_x, vertex_y
                        in footprint.exterior.coords
                    ]
                    mouth_face_width = (
                        max(face_projections) - min(face_projections))
                    reach = 1000.0
                    outward_half_plane = Polygon([
                        (centroid_point.x + perpendicular[0] * reach,
                         centroid_point.y + perpendicular[1] * reach),
                        (centroid_point.x - perpendicular[0] * reach,
                         centroid_point.y - perpendicular[1] * reach),
                        (centroid_point.x - perpendicular[0] * reach
                         + outward_vector[0] * 2.0 * reach,
                         centroid_point.y - perpendicular[1] * reach
                         + outward_vector[1] * 2.0 * reach),
                        (centroid_point.x + perpendicular[0] * reach
                         + outward_vector[0] * 2.0 * reach,
                         centroid_point.y + perpendicular[1] * reach
                         + outward_vector[1] * 2.0 * reach),
                    ])
                    lane_union = unary_union([
                        line.buffer(mouth_face_width / 2.0 + 1.0)
                        for line in lane_lines
                    ])
                    collar_geometry = collar_geometry.difference(
                        lane_union.intersection(outward_half_plane))
            except _GEOM_EXC:
                continue
            collar_parts = [
                part for part in (
                    collar_geometry.geoms
                    if hasattr(collar_geometry, "geoms")
                    else [collar_geometry])
                if part.geom_type == "Polygon" and not part.is_empty
                and part.area >= 4.0
            ]
            if not collar_parts:
                continue
            # Defect (2026-07-15): the collar was emitted FLAT at the
            # crown elevation, so its whole perimeter was a cliff (the
            # measured 7.76/7.09 m steps to the approach, 4.44 m to the
            # adjacent_ground band — vertical stretched-texture walls
            # flanking the portal objects).  It must be a TRANSITION
            # ring: the inner boundary meeting the crown keeps the crown
            # altitude (and the object facade hides its vertical meeting
            # with the low mouth — the by-design object-hidden face),
            # while the exposed outer rim tracks the surrounding ground.
            #
            # Per-vertex law value: sample the DEM at the vertex (the
            # smoothed tile DEM in production — the same source the crown
            # samples for ``ground_behind``, consistent with any
            # adjacent_ground band that abuts) and blend from the crown
            # elevation to that ground by DISTANCE TO THE CROWN polygon
            # (the buried half).  Vertices on the buried inner edge hug
            # the crown (distance ~ 0); vertices on the outer rim, and
            # everything laterally beyond the object where no facade
            # hides a face, reach the ground within one collar reach —
            # so no exposed vertical face survives.
            crown_for_collar = crown_geometry
            crown_reach = collar_reach if collar_reach > 1e-6 else 1.0
            # Round-8 fact 4 — a lateral flank BEYOND the object's own
            # width (the facade-hidden span) may not meet the low mouth
            # plate vertically.  Only the object-hidden span — within the
            # mouth face's lateral half-width — is allowed the by-design
            # vertical meeting (the facade covers it); a flank sticking
            # out sideways past the object must feather down to the mouth
            # floor where it abuts the mouth plate, exactly as the outer
            # rim feathers to the surrounding ground.  Measure the mouth
            # face half-width (footprint extent perpendicular to
            # ``outward``).
            face_centroid = footprint.centroid
            face_perpendicular = (-outward_vector[1], outward_vector[0])
            _face_lateral = [
                ((vertex_x - face_centroid.x) * face_perpendicular[0]
                 + (vertex_y - face_centroid.y) * face_perpendicular[1])
                for vertex_x, vertex_y in footprint.exterior.coords
            ]
            face_half_width = (
                (max(_face_lateral) - min(_face_lateral)) / 2.0
                if _face_lateral else 0.0)
            # Buried depth of the crown along the outward axis — bounds
            # the mouth-side VALUE-ceiling zone below, so on a shallow
            # portal the object-hidden back-face meeting stays at the
            # crown (the ceiling zone never reaches it).
            crown_depth_m = 0.0
            try:
                # The pavement clip can leave a MultiPolygon crown —
                # measure the depth across every part's ring.
                _crown_projections = [
                    (vertex_x * outward_vector[0]
                     + vertex_y * outward_vector[1])
                    for part in getattr(
                        crown_geometry, "geoms", [crown_geometry])
                    for vertex_x, vertex_y in part.exterior.coords]
                crown_depth_m = (max(_crown_projections)
                                 - min(_crown_projections))
            except (_GEOM_EXC, AttributeError, ValueError):
                crown_depth_m = 0.0
            # Complete the portal terrain record for the post-solve
            # airside raise (its mouth feather guard reuses the same
            # mouth plate geometry so the raise never rebuilds the
            # road-side cliff the feather removed).
            portal_terrain_record["mouth_geometry"] = plain_mouth_geometry
            portal_terrain_record["crown_depth_m"] = crown_depth_m

            def _collar_alt(vertex_x, vertex_y,
                            _crown=crown_for_collar,
                            _crown_elevation=crown_elevation,
                            _mouth_floor=mouth_floor,
                            _ground_behind=ground_behind,
                            _reach=crown_reach,
                            _mouth_geometry=plain_mouth_geometry,
                            _crown_depth=crown_depth_m):
                # The outer target is the ground the abutting
                # adjacent_ground band will drop to — NOT the smoothed
                # DEM AT the vertex.  Ortho4XP's airport-smoothed tile
                # DEM FLATTENS the runway embankment, so it holds the
                # crown height right up to the collar's outer edge and
                # only drops at the LIP just beyond; sampling at the
                # vertex therefore reads ~crown and the collar would
                # stay a plateau (measured KBNA 02C: the band welded to
                # a crown-high collar pin, then cliffed 6.9-7.8 m to the
                # DEM < 1 m further out).  Sample the DEM over a small
                # DISK around the vertex and take the MINIMUM, so the
                # exposed rim reaches the true surrounding ground the
                # band's first non-weld station reads — in whatever
                # direction the lip falls (a single outward ray misses
                # it: the drop is perpendicular to the collar arm, not
                # radial from the footprint centroid).  The
                # distance-to-crown blend below keeps the buried INNER
                # face at the crown regardless, so lowering the disk
                # target never disturbs the object-hidden meeting.
                # A tight disk: the embankment lip abuts the collar's
                # outer edge (measured KBNA: the DEM drop is < 1.5 m
                # outside the rim), so a few metres in every direction
                # catch it — while staying close enough that the collar
                # never dives BELOW the ground the band welds to just
                # outside it (a distant low would invert the step).
                ground_here = None
                offsets = [(0.0, 0.0)]
                for radius in (1.5, 3.0, 5.0):
                    for step_index in range(12):
                        angle = math.pi * step_index / 6.0
                        offsets.append((radius * math.cos(angle),
                                        radius * math.sin(angle)))
                for offset_x, offset_y in offsets:
                    try:
                        probe_lat, probe_lon = _meters_to_lat_lon(
                            vertex_x + offset_x, vertex_y + offset_y)
                        sample = _sample_dem(
                            dem, tile_lat, tile_lon, probe_lat, probe_lon)
                    except (_GEOM_EXC, ValueError, TypeError):
                        sample = None
                    if sample is not None:
                        ground_here = (
                            sample if ground_here is None
                            else min(ground_here, float(sample)))
                if ground_here is None:
                    ground_here = (
                        _ground_behind if _ground_behind is not None
                        else _crown_elevation)
                # Never above the crown, never an absurd DEM dropout
                # (mirror the crown's own clamp band).
                outer_target = min(
                    max(float(ground_here), _mouth_floor - 12.0),
                    _crown_elevation,
                )
                # Mouth transition — DISTANCE-BASED (2026-07-17,
                # supersedes the round-8 lateral gate): ANY collar
                # vertex within one reach of the low mouth plate
                # feathers its outer target down to the mouth floor,
                # UNLESS it hugs the crown's hidden face (distance to
                # the crown polygon < 2 m — the object facade hides
                # that by-design vertical meeting, and on a small
                # portal the whole back band is within a reach of the
                # mouth).  The old gate exempted the entire lateral
                # facade span, which left the collar's side wrap at
                # full crown height 0-2 m from the mouth plate — with
                # the crown now floored at the object roof plane
                # (mouth + deck_top) those seams measured 3.4-6.0 m
                # steps (audit check 7, 33 vertices at both
                # Murfreesboro portals).
                try:
                    distance_to_crown = _crown.distance(
                        Point(vertex_x, vertex_y))
                except (_GEOM_EXC, AttributeError):
                    distance_to_crown = _reach
                try:
                    distance_to_mouth = _mouth_geometry.distance(
                        Point(vertex_x, vertex_y))
                except (_GEOM_EXC, AttributeError):
                    distance_to_mouth = _reach
                if distance_to_crown >= 2.0 and distance_to_mouth < _reach:
                    mouth_blend = max(
                        0.0, min(1.0, distance_to_mouth / _reach))
                    outer_target = min(
                        outer_target,
                        (1.0 - mouth_blend) * _mouth_floor
                        + mouth_blend * outer_target)
                blend = max(0.0, min(1.0, distance_to_crown / _reach))
                value = ((1.0 - blend) * _crown_elevation
                         + blend * outer_target)
                # SPLIT-LINE VALUE CEILING (2026-07-17): at the mouth
                # plate's sides the collar hugs the CROWN's side edge
                # (distance_to_crown ~ 0), so the crown term dominates
                # the blend regardless of the outer-target feather and
                # the collar met the low mouth plate at ~70 % of the
                # crown height (audit: 3.2/4.7 m steps at both
                # Murfreesboro portals).  Cap the VALUE itself: within
                # the mouth zone a collar vertex may exceed the mouth
                # floor by at most (distance_to_mouth / reach) x
                # (crown - mouth) — zero step at the plate, full crown
                # one reach away.  The zone is bounded below the
                # crown's buried depth so a shallow portal's hidden
                # back-face meeting (which IS within a reach of the
                # mouth polygon) keeps the crown.
                ceiling_zone = min(_reach, max(0.0, _crown_depth - 1.0))
                if distance_to_mouth < ceiling_zone:
                    ceiling = (_mouth_floor
                               + (distance_to_mouth / _reach)
                               * max(0.0, _crown_elevation - _mouth_floor))
                    value = min(value, ceiling)
                return value

            collar_vertex_count = 0
            emitted_collar_parts = 0
            for collar_part in collar_parts:
                try:
                    part_vertex_count = _born_graded(
                        collar_part, portal_plate_role,
                        "object_tunnel_portal_collar", _collar_alt,
                        record_pins=portal_plate_pins)
                except _GEOM_EXC:
                    continue
                if part_vertex_count > 0:
                    # ``_born_graded`` appended the shape (a < 4-vertex
                    # ring returns 0 without appending).
                    portal_terrain_record["collar_shapes"].append(
                        layout.shapes[-1])
                collar_vertex_count += part_vertex_count
                emitted_collar_parts += 1
            if not emitted_collar_parts:
                continue
            n_trench += 1
            UI.vprint(
                1,
                "   [object-tunnel] portal collar feathers crown "
                f"{crown_elevation:.2f} m to ground around the portal "
                f"back ({emitted_collar_parts} part(s), "
                f"{collar_vertex_count} vertices)",
            )

    for bridge in corridor_bridges:
        datum = _bridge_datum_elevation_m(bridge, dem, tile_lat, tile_lon)
        if datum is None:
            UI.vprint(
                1,
                "   [object-bridge] no datum for bridge layout shapes of "
                f"{bridge.object_resources} — skipped",
            )
            continue
        footprint = _bridge_footprint_meters(bridge, to_meters)
        if footprint is None:
            continue
        # The under-deck working area is the abutment-to-abutment BOX
        # (iteration 5) — the hard-face union can be partial/multi-lobe.
        deck_box = _bridge_deck_box_meters(bridge, layout)
        if deck_box is None:
            deck_box = footprint
        deck_elevation = _bridge_deck_elevation_m(
            bridge, dem, tile_lat, tile_lon
        )
        floor_elevation = _bridge_corridor_floor_m(bridge, deck_elevation)
        # Round 10: the road-exit corridor — where a draped road leaves
        # the span through an abutment end, the causeway must yield.
        # User ruling 2026-07-14c: the exit opening matches the TRENCH
        # width (the approach ramps now run at trench width), so the
        # carriageway-width corridor is dilated up to the trench's
        # cross-section before it cuts the causeway plates.
        road_exit_corridor = _road_exit_corridor_meters(
            bridge, layout, to_meters
        )
        if road_exit_corridor is not None:
            try:
                rotated_rectangle = min_rotated_rect(deck_box)
                corners = list(rotated_rectangle.exterior.coords)
                short_side = min(
                    math.hypot(corners[1][0] - corners[0][0],
                               corners[1][1] - corners[0][1]),
                    math.hypot(corners[2][0] - corners[1][0],
                               corners[2][1] - corners[1][1]),
                )
                trench_width_m = short_side - 2.0 * _TRENCH_INSET_M
                dilation = (trench_width_m / 2.0
                            - _ROAD_EXIT_CUT_HALF_WIDTH_M)
                if dilation > 0.0:
                    road_exit_corridor = road_exit_corridor.buffer(
                        dilation)
            except _GEOM_EXC:
                pass

        # Ruling R8 flush seat (hard decks) / pavement wins (cosmetic).
        pavement_kept_union = None
        if bridge.hard_deck:
            n_cut = cut_pavement_over_footprint(layout, deck_box)
            if n_cut:
                UI.vprint(
                    1,
                    f"   [object-bridge] R8 flush seat: cut {n_cut} "
                    "pavement shape(s) over the hard deck of "
                    f"{bridge.object_resources}",
                )
        else:
            crossing_polygons = [
                shape.polygon for shape in layout.shapes
                if shape.role in weld_roles
                and shape.polygon is not None
                and not shape.polygon.is_empty
                and shape.polygon.intersects(deck_box)
            ]
            try:
                pavement_kept_union = (
                    unary_union(crossing_polygons)
                    if crossing_polygons else None
                )
            except _GEOM_EXC:
                pavement_kept_union = None

        # ── §T1.1: THE DECK-CLEARANCE CORRIDOR YIELDS TO A MAPPED BORE
        # (Fable ruling 2026-08-28, option (c)).  Where this structure's
        # corridor footprint overlaps ground a MAPPED bore already owns,
        # the trench and the causeway plates over that overlap are
        # SUPPRESSED — the bore's own portal machinery emits the mouth,
        # ramp and walls there.  Everything outside the overlap keeps its
        # existing treatment, pins included: the deck-clearance law is
        # for structures over OPEN ground, and this narrows it to that.
        bore_ground = _corridor_yields_to_mapped_bore(bridge, layout)

        def _yield_to_bore(polygon, ref, _bore=None):
            """``polygon`` minus the mapped-bore ground, or ``None`` when
            nothing survives.  Each removal takes its §1 named line."""
            _bore = bore_ground if _bore is None else _bore
            if (_bore is None or polygon is None or polygon.is_empty):
                return polygon
            try:
                if not polygon.intersects(_bore):
                    return polygon
                _kept = polygon.difference(_bore)
                _removed = polygon.area - (
                    0.0 if _kept.is_empty else _kept.area)
            except _GEOM_EXC:                            # pragma: no cover
                return polygon
            if _removed <= 0.0:
                return polygon
            _whole = _kept.is_empty or _kept.area < 1.0
            _record_corridor_suppression(
                layout, bridge, ref, polygon, _removed, _whole)
            if _whole:
                return None
            if _kept.geom_type == "MultiPolygon":
                _kept = max(_kept.geoms, key=lambda g: g.area)
            return None if _kept.is_empty else _kept

        # Trench (born flat at the law floor) — spans the deck BOX.
        trench_polygon_emitted = None
        try:
            trench = deck_box.buffer(-_TRENCH_INSET_M)
            if pavement_kept_union is not None:
                trench = trench.difference(pavement_kept_union)
            if trench.geom_type == "MultiPolygon" and not trench.is_empty:
                trench = max(trench.geoms, key=lambda g: g.area)
            trench = _yield_to_bore(trench, "object_bridge_corridor")
            if trench is None:
                trench = Polygon()
            if trench.geom_type == "Polygon" and not trench.is_empty:
                vertex_count = _born_flat(
                    trench, ROLE_BRIDGE_TRENCH,
                    "object_bridge_corridor", floor_elevation)
                trench_polygon_emitted = trench
                n_trench += 1
                UI.vprint(
                    1,
                    "   [object-bridge] trench born at "
                    f"{floor_elevation:.2f} m ({vertex_count} vertices) "
                    f"under {bridge.object_resources}",
                )
        except _GEOM_EXC:
            pass

        # Causeway plates (born flat at the deck-end law value).
        pavement_union = _pavement_union()
        centroid = footprint.centroid
        causeway_parts_emitted: list = []
        abutment_lines = _abutment_lines_layout_meters(
            bridge, layout, extension_fraction=0.0
        )
        for end_index, line in enumerate(abutment_lines):
            end_y = (
                bridge.deck_end_elevations_y_m[end_index]
                if end_index < len(bridge.deck_end_elevations_y_m)
                else bridge.deck_top_y_m
            )
            plate_elevation = bridge_deck_end_pin_elevation_m(datum, end_y)
            midpoint = line.interpolate(0.5, normalized=True)
            outward_x = midpoint.x - centroid.x
            outward_y = midpoint.y - centroid.y
            outward_norm = math.hypot(outward_x, outward_y)
            if outward_norm < 1.0:
                continue
            outward_x /= outward_norm
            outward_y /= outward_norm
            (ax, ay), (bx, by) = list(line.coords)[0], list(line.coords)[-1]
            # Iteration 5 (audit 5): widen the lip beyond the deck
            # corners and start the plate INWARD of the lip so on-line
            # and corner samples stay inside the 167-flat surface under
            # the 0.5 m node-interning wobble; the trench inset grows in
            # step so the R2 node-split wall gap stays 0.6 m.
            line_length = math.hypot(bx - ax, by - ay)
            direction_x = (bx - ax) / line_length
            direction_y = (by - ay) / line_length
            ax -= direction_x * _CAUSEWAY_WIDTH_MARGIN_M
            ay -= direction_y * _CAUSEWAY_WIDTH_MARGIN_M
            bx += direction_x * _CAUSEWAY_WIDTH_MARGIN_M
            by += direction_y * _CAUSEWAY_WIDTH_MARGIN_M
            ax -= outward_x * _CAUSEWAY_INWARD_OVERLAP_M
            ay -= outward_y * _CAUSEWAY_INWARD_OVERLAP_M
            bx -= outward_x * _CAUSEWAY_INWARD_OVERLAP_M
            by -= outward_y * _CAUSEWAY_INWARD_OVERLAP_M

            def _outward_rectangle(length_m):
                reach = length_m + _CAUSEWAY_INWARD_OVERLAP_M
                return Polygon([
                    (ax, ay),
                    (bx, by),
                    (bx + outward_x * reach, by + outward_y * reach),
                    (ax + outward_x * reach, ay + outward_y * reach),
                ])

            plate_length = maximum_length
            if pavement_union is not None:
                try:
                    outward_pavement = pavement_union.intersection(
                        _outward_rectangle(maximum_length)
                    )
                    if not outward_pavement.is_empty:
                        gap = line.distance(outward_pavement)
                        plate_length = min(gap + 2.0, maximum_length)
                except _GEOM_EXC:
                    pass
            if plate_length < 1.0:
                plate_length = 2.0
            try:
                plate = _outward_rectangle(plate_length)
                if not plate.is_valid:
                    plate = plate.buffer(0)
                if pavement_union is not None:
                    plate = plate.difference(pavement_union)
                # Round 10 road-exit cut: the road corridor passes
                # THROUGH this end — cut it out of the plate; the
                # remainders flank the road at the deck-end elevation
                # (the author-mesh shape: 161 corridor out both ends,
                # 167 fill on both sides).
                if road_exit_corridor is not None:
                    plate = plate.difference(road_exit_corridor)
                parts = (
                    list(plate.geoms)
                    if plate.geom_type == "MultiPolygon" else [plate]
                )
                emitted_parts = 0
                for part in parts:
                    if (part.geom_type != "Polygon" or part.is_empty
                            or part.area < 25.0):
                        continue
                    # §T1.1: a causeway plate over the mapped bore's own
                    # ground is deck-clearance furniture on ground the
                    # bore owns — suppressed here, kept outside.
                    part = _yield_to_bore(part, "object_bridge_causeway")
                    if (part is None or part.is_empty
                            or part.area < 25.0):
                        continue
                    _born_flat(part, ROLE_BRIDGE_CAUSEWAY,
                               "object_bridge_causeway", plate_elevation)
                    causeway_parts_emitted.append(part)
                    emitted_parts += 1
                # User ruling 2026-07-14b: the pavement the approach
                # RESUMES on around the plate zone is anchored AT the
                # deck height, so both sides of the crossing grade
                # smoothly to the same value.  The abutment-line pins
                # alone miss it — the resumed pavement across the
                # road-exit cut measures 13.3-13.6 m from the plate at
                # KBNA (its approach solved 6.3 m above the 167.0
                # deck, a quarantined wall at the lip).  Pinned around
                # the FULL outward plate rectangle, not the surviving
                # flank parts — with trench-width exit cuts (ruling
                # 2026-07-14c) the flanks can vanish entirely while the
                # anchoring must stay.  Taxi/runway/apron rings only —
                # service roads descend through the road-exit cut and
                # must never pin to the deck.
                weld_pinned = 0
                weld_band = float(
                    _CFG.BRIDGE_CAUSEWAY_WELD_PIN_BAND_M)
                try:
                    weld_line = LineString(list(
                        _outward_rectangle(plate_length)
                        .exterior.coords))
                except _GEOM_EXC:
                    weld_line = None
                if weld_line is not None:
                    for shape_index, shape in enumerate(
                            list(layout.shapes)):
                        if shape.role not in _BRIDGE_PIN_ROLES:
                            continue
                        if shape.polygon is None \
                                or shape.polygon.is_empty:
                            continue
                        try:
                            if shape.polygon.exterior.distance(
                                    weld_line) > weld_band:
                                continue
                        except _GEOM_EXC:
                            continue
                        weld_pinned += _pin_shape_vertices_on_line(
                            layout, shape_index, weld_line,
                            plate_elevation,
                            capture_band_m=weld_band,
                        )
                if weld_pinned:
                    UI.vprint(
                        1,
                        f"   [object-bridge] {weld_pinned} approach "
                        "weld pin(s) around the causeway zone "
                        f"({plate_elevation:.2f} m, end {end_index})",
                    )
                if not emitted_parts:
                    continue
                n_causeway += emitted_parts
                UI.vprint(
                    1,
                    "   [object-bridge] causeway born at "
                    f"{plate_elevation:.2f} m, {plate_length:.1f} m long, "
                    f"{emitted_parts} flank part(s)"
                    + (" (road-exit cut)" if road_exit_corridor is not None
                       and emitted_parts > 1 else "")
                    + f" (end {end_index}) for {bridge.object_resources}",
                )
            except _GEOM_EXC:
                continue

        # ── Deck-lip weld strips (user directive 2026-07-15): the R8
        # hard-deck cut trims pavement AT the deck box while the trench
        # is inset _TRENCH_INSET_M, leaving a ring of raw mesh whose
        # triangles dive to the trench floor right at the lip (measured
        # KBNA taxiway-L: pavement pinned 167.0, plate edge 0.8-1.2 m
        # away at 161.01 — the owner-visible gap onto the deck).  Every
        # pavement-facing rim segment gets a strip at the deck-top
        # PROFILE law value spanning from the causeway-inward depth
        # (preserving the R2 node-split wall to the trench) to
        # _DECK_WELD_OVERLAP_M INSIDE the pavement; the fronting
        # pavement ring vertices are pinned at the same law value, so
        # the overlap is coplanar and invisible.  Never on road faces:
        # the strip zone is pavement-driven (taxi/runway/apron roles
        # only — service roads descend through the road-exit cut) and
        # the road-exit corridor is cut out, so the approach chains and
        # their verbatim plate welds are untouched.
        n_weld_strips = _emit_deck_lip_weld_strips(
            layout, bridge, deck_box, trench_polygon_emitted,
            road_exit_corridor, causeway_parts_emitted, datum,
            _born_graded)
        if n_weld_strips:
            UI.vprint(
                1,
                f"   [object-bridge] {n_weld_strips} deck-lip weld "
                "strip(s) overlap the resumed pavement at the deck "
                f"profile value for {bridge.object_resources}",
            )
    return n_trench, n_causeway, pads_removed


def raise_portal_terrain_to_airside(layout) -> int:
    """POST-SOLVE raise of portal crown/collar terrain to the
    surrounding solved AIRSIDE level (user ruling 2026-07-17: the
    portal object's flat top sits close to level with the adjacent
    taxiway — the back terrain must RISE to meet the airside where the
    solved airside stands above the object-derived crown; it never
    falls, so the DEM feather survives wherever airside is lower or
    absent).

    Called from ``finalize.emit_terrain_transition_features`` — after
    the elevation solve (solved airside ring values exist), before
    ``final_grade_projection`` and adjacent-ground band emission.
    Every raised vertex re-records its solver pin (``_record_pin``)
    so the downstream scoped projection re-pins the RAISED value
    (post-writeback passes must re-pin every hard class).

    Returns the number of vertices raised.
    """
    if not getattr(_CFG, "TUNNEL_PORTAL_AIRSIDE_RAISE", True):
        return 0
    records = getattr(layout, "portal_terrain_records", None)
    if not records:
        return 0
    from .layout import corner_alts_from_high_low

    radius = float(_CFG.TUNNEL_PORTAL_AIRSIDE_SAMPLE_RADIUS_M)
    airside_roles = (
        ROLE_RUNWAY, ROLE_JUNCTION, ROLE_APRON, ROLE_PRIMARY_PARALLEL,
        ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR)
    # Solved airside samples in a coarse grid (cell = radius, so a
    # query only visits the 3x3 neighbourhood).
    grid: dict = {}
    for s in layout.shapes:
        if (s.role not in airside_roles or s.polygon is None
                or s.polygon.is_empty):
            continue
        try:
            ring = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        node_values = getattr(s, "node_altitudes", None)
        if node_values and len(node_values) >= len(ring) - 1:
            values = list(node_values)
        elif getattr(s, "altitude", None) is not None:
            values = [float(s.altitude)] * len(ring)
        elif (getattr(s, "altitude_high", None) is not None
                and getattr(s, "altitude_low", None) is not None
                and len(ring) in (4, 5)):
            corner_values = corner_alts_from_high_low(
                s.altitude_high, s.altitude_low)
            values = corner_values + corner_values[:1]
        else:
            continue
        for (x, y), value in zip(ring, values):
            if value is None:
                continue
            key = (int(x // radius), int(y // radius))
            grid.setdefault(key, []).append(
                (float(x), float(y), float(value)))
    if not grid:
        return 0

    def airside_samples(x, y):
        """``(median, nearest_distance)`` of solved airside ring values
        within ``radius`` of the point, or ``(None, None)``."""
        key_x, key_y = int(x // radius), int(y // radius)
        found = []
        nearest_sq = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (sx, sy, sv) in grid.get(
                        (key_x + dx, key_y + dy), ()):
                    d_sq = (sx - x) ** 2 + (sy - y) ** 2
                    if d_sq <= radius * radius:
                        found.append(sv)
                        if nearest_sq is None or d_sq < nearest_sq:
                            nearest_sq = d_sq
        if not found:
            return (None, None)
        found.sort()
        mid = len(found) // 2
        median = (found[mid] if len(found) % 2
                  else 0.5 * (found[mid - 1] + found[mid]))
        return (median, math.sqrt(nearest_sq))

    def airside_level(x, y):
        return airside_samples(x, y)[0]

    # RAMP-LAW CEILING (2026-07-17, preventive): raised collar/crown
    # values CAN propagate into coincident tunnel-ramp quad corners at
    # the to_osm per-node consensus (which merges shared coordinates
    # toward the feature side), steepening an at-cap ramp past
    # TUNNEL_RAMP_MAX_GRADE.  (The SPJC 4.13-4.21 % ramp violations
    # that prompted this were measured to be LATENT in the legacy ramp
    # emitter — present with the raise AND crown gated off — not
    # raise-induced; the guard stays because the mechanism is real by
    # construction.)  The raise yields to the ramp law:
    # a raised value at a coordinate shared with a sloped ramp quad may
    # not exceed the quad's far-end value + cap x quad length.  Index
    # every sloped tunnel-ramp quad corner once per call.
    from .layout import corner_alts_from_high_low as _corner_alts
    ramp_cap = float(_CFG.TUNNEL_RAMP_MAX_GRADE)
    ramp_corner_ceilings: dict = {}
    for s in layout.shapes:
        if (s.role != ROLE_TUNNEL_RAMP or s.polygon is None
                or s.polygon.is_empty
                or s.altitude_high is None or s.altitude_low is None):
            continue
        try:
            ring = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        open_ring = ring[:-1] if ring and ring[0] == ring[-1] else ring
        if len(open_ring) != 4:
            continue
        corner_values = _corner_alts(s.altitude_high, s.altitude_low)
        # [H, L, L, H]: corners (0, 3) = high short edge, (1, 2) = low.
        high_mid = (0.5 * (open_ring[0][0] + open_ring[3][0]),
                    0.5 * (open_ring[0][1] + open_ring[3][1]))
        low_mid = (0.5 * (open_ring[1][0] + open_ring[2][0]),
                   0.5 * (open_ring[1][1] + open_ring[2][1]))
        quad_length = math.hypot(high_mid[0] - low_mid[0],
                                 high_mid[1] - low_mid[1])
        if quad_length < 1.0:
            continue
        for corner_index, (cx, cy) in enumerate(open_ring):
            far_value = (float(s.altitude_high)
                         if corner_index in (1, 2)
                         else float(s.altitude_low))
            ceiling = far_value + ramp_cap * quad_length
            key = (int(cx // SHARED_VERTEX_TOL_M),
                   int(cy // SHARED_VERTEX_TOL_M))
            ramp_corner_ceilings.setdefault(key, []).append(
                (cx, cy, ceiling))

    def ramp_law_ceiling(x, y):
        """Tightest ramp-law ceiling among ramp corners within the
        to_osm interning tolerance of the point, or None."""
        key_x = int(x // SHARED_VERTEX_TOL_M)
        key_y = int(y // SHARED_VERTEX_TOL_M)
        tightest = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (cx, cy, ceiling) in ramp_corner_ceilings.get(
                        (key_x + dx, key_y + dy), ()):
                    if (math.hypot(cx - x, cy - y)
                            <= SHARED_VERTEX_TOL_M
                            and (tightest is None
                                 or ceiling < tightest)):
                        tightest = ceiling
        return tightest

    n_raised = 0
    for record in records:
        crown_geometry = record.get("crown_geometry")
        crown_elevation = float(record.get("crown_elevation") or 0.0)
        reach = float(record.get("collar_reach") or 1.0)
        if reach <= 1e-6:
            reach = 1.0
        raised_crown = crown_elevation
        if crown_geometry is not None:
            try:
                level = airside_level(
                    crown_geometry.centroid.x, crown_geometry.centroid.y)
            except _GEOM_EXC:
                level = None
            if level is not None and level > crown_elevation + 0.05:
                raised_crown = float(level)
        crown_shape_list = [
            shape for shape in (
                record.get("crown_shapes") or [record.get("crown_shape")])
            if shape is not None and shape.polygon is not None
            and getattr(shape, "node_altitudes", None)]
        if raised_crown > crown_elevation + 0.05 and crown_shape_list:
            crown_rings = []
            for crown_shape in crown_shape_list:
                try:
                    crown_rings.append(
                        list(crown_shape.polygon.exterior.coords))
                except _GEOM_EXC:
                    crown_rings.append([])
            # A flat crown clamps as a whole to the tightest ramp-law
            # ceiling among its ramp-coincident ring vertices (rare —
            # ramps attach at the mouth side, the crown is the back
            # half).  All parts share one raised value.
            for crown_ring in crown_rings:
                for (x, y) in crown_ring:
                    ceiling = ramp_law_ceiling(x, y)
                    if ceiling is not None and raised_crown > ceiling:
                        raised_crown = max(crown_elevation, ceiling)
            raised_count = 0
            for crown_shape, crown_ring in zip(
                    crown_shape_list, crown_rings):
                crown_shape.node_altitudes = (
                    [round(raised_crown, 2)]
                    * len(crown_shape.node_altitudes))
                open_count = (
                    len(crown_ring) - 1
                    if crown_ring and crown_ring[0] == crown_ring[-1]
                    else len(crown_ring))
                for (x, y) in crown_ring[:open_count]:
                    _record_pin(layout, x, y, raised_crown)
                raised_count += open_count
            n_raised += raised_count
            UI.vprint(1,
                "   [object-tunnel] portal crown raised to airside "
                f"level {raised_crown:.2f} m (was "
                f"{crown_elevation:.2f} m)")

        mouth_geometry = record.get("mouth_geometry")
        mouth_floor = float(record.get("mouth_floor") or 0.0)
        crown_depth = float(record.get("crown_depth_m") or 0.0)
        ceiling_zone = min(reach, max(0.0, crown_depth - 1.0))
        for collar_shape in record.get("collar_shapes") or ():
            node_values = getattr(collar_shape, "node_altitudes", None)
            if (collar_shape.polygon is None or not node_values):
                continue
            try:
                ring = list(collar_shape.polygon.exterior.coords)
            except _GEOM_EXC:
                continue
            if len(node_values) < len(ring):
                continue
            changed = False
            new_values = list(node_values)
            open_count = (len(ring) - 1
                          if ring and ring[0] == ring[-1] else len(ring))
            for i in range(open_count):
                x, y = ring[i]
                old_value = float(node_values[i])
                try:
                    distance_to_crown = (
                        crown_geometry.distance(Point(x, y))
                        if crown_geometry is not None else reach)
                except (_GEOM_EXC, AttributeError):
                    distance_to_crown = reach
                # Mouth feather guard — DISTANCE-BASED, mirroring
                # ``_collar_alt``: any vertex within one reach of the
                # low mouth plate keeps its feathered value (raising
                # it would rebuild the cliff onto the road), unless it
                # hugs the crown's hidden face (the object facade
                # hides that meeting by design).
                distance_to_mouth = reach
                if mouth_geometry is not None:
                    try:
                        distance_to_mouth = mouth_geometry.distance(
                            Point(x, y))
                    except (_GEOM_EXC, AttributeError):
                        distance_to_mouth = reach
                if distance_to_crown >= 2.0 and distance_to_mouth < reach:
                    continue
                blend = max(0.0, min(1.0, distance_to_crown / reach))
                # DISTANCE-DECAYED rim target: the rim rises toward
                # the airside median only in proportion to how close
                # the nearest airside vertex actually is — a rim
                # vertex 5 m from the abutting band takes ~the band
                # level, one 70 m away keeps ~its DEM feather.  A flat
                # airside-median target regardless of distance
                # flattened the whole collar into a plateau wherever
                # ANY airside vertex sat within the sample radius
                # (measured in the raise unit probe).
                outer_level, nearest_airside_m = airside_samples(x, y)
                if outer_level is None:
                    outer_target = old_value
                else:
                    weight = max(0.0, min(
                        1.0, 1.0 - float(nearest_airside_m) / radius))
                    outer_target = (weight * float(outer_level)
                                    + (1.0 - weight) * old_value)
                candidate = ((1.0 - blend) * raised_crown
                             + blend * outer_target)
                # Split-line value ceiling — mirrors ``_collar_alt``:
                # within the mouth zone the raised value may exceed the
                # mouth floor by at most the per-reach fraction of the
                # (raised) crown height.
                if distance_to_mouth < ceiling_zone:
                    candidate = min(
                        candidate,
                        mouth_floor + (distance_to_mouth / reach)
                        * max(0.0, raised_crown - mouth_floor))
                # Ramp-law ceiling: the raise yields to an abutting
                # sloped tunnel-ramp quad's grade cap (see the index
                # above).
                ramp_ceiling = ramp_law_ceiling(x, y)
                if ramp_ceiling is not None:
                    candidate = min(candidate, ramp_ceiling)
                if candidate > old_value + 0.05:
                    new_values[i] = round(candidate, 2)
                    _record_pin(layout, x, y, float(new_values[i]))
                    changed = True
                    n_raised += 1
            if changed:
                if len(ring) > open_count:
                    new_values[len(ring) - 1] = new_values[0]
                collar_shape.node_altitudes = new_values
    if n_raised:
        UI.vprint(1,
            f"   [object-tunnel] portal terrain airside raise: "
            f"{n_raised} vertices lifted across "
            f"{len(records)} portal(s).")
    return n_raised


def enforce_bridge_plate_exclusivity(layout) -> int:
    """Round 9 (user ruling): the WRITTEN patch must contain strictly
    non-overlapping rings over the bridge plates — the base mesh
    machinery is never taught to tolerate our overlaps.  Every terrain
    FEATURE shape (tunnel ramps/walls from the legacy portal emitters
    that fire on the ``tunnel=yes`` OSM ways under a deck, clearance
    cuts, adjacent-ground strips) is CUT against the trench/causeway
    plate footprints; pieces mostly inside a plate are dropped whole
    (measured at KBNA: 14 portal ramp/wall vertices constrained at
    170.0-178.3 inside the 161.01 trench box kept the corridor off its
    floor — Triangle interpolated the interior from them).

    The plates themselves are already mutually exclusive by
    construction (trench inset vs causeway lip, pavement weld clips).
    Deconflict's sloped-quad exemption (small overlaps kept to preserve
    the 4-corner altitude convention) does NOT apply here: a sloped
    piece that loses corners is converted to resampled per-vertex
    ``node_altitudes``, exactly like the boundary-cut pattern.

    Called after the road-feature emitters (finalize) AND after the
    adjacent-ground bands (pipeline tail).  Gate off ⇒ no plates ⇒ 0.
    Returns the number of shapes cut or dropped."""
    classification = _object_bridge_classification(layout)
    if classification is None:
        return 0
    from .layout import (
        ROLE_BRIDGE_CAUSEWAY,
        ROLE_BRIDGE_TRENCH,
        ROLE_GRADED_STRIP,
        ROLE_RETAINING_WALL,
        ROLE_TAXIWAY_CLEARANCE,
        ROLE_RUNWAY_CLEARANCE,
    )
    plate_roles = (ROLE_BRIDGE_TRENCH, ROLE_BRIDGE_CAUSEWAY)
    cut_roles = {
        ROLE_TUNNEL_RAMP, ROLE_RETAINING_WALL, ROLE_GRADED_STRIP,
        ROLE_TAXIWAY_CLEARANCE, ROLE_RUNWAY_CLEARANCE,
    }
    plate_polygons = [
        shape.polygon for shape in layout.shapes
        if shape.role in plate_roles
        and shape.polygon is not None and not shape.polygon.is_empty
    ]
    if not plate_polygons:
        return 0
    try:
        plate_union = unary_union(plate_polygons)
    except _GEOM_EXC:
        return 0
    n_touched = 0
    kept_shapes: list[BuiltShape] = []
    for shape in layout.shapes:
        if (shape.role not in cut_roles
                or shape.polygon is None or shape.polygon.is_empty):
            kept_shapes.append(shape)
            continue
        # Our own plates never cut each other here.
        if (shape.ref or "").startswith("object_bridge"):
            kept_shapes.append(shape)
            continue
        try:
            overlap = shape.polygon.intersection(plate_union).area
        except _GEOM_EXC:
            kept_shapes.append(shape)
            continue
        if overlap < 0.5:
            kept_shapes.append(shape)
            continue
        n_touched += 1
        try:
            old_ring = list(shape.polygon.exterior.coords)
        except _GEOM_EXC:
            old_ring = []
        if old_ring and old_ring[0] == old_ring[-1]:
            old_ring = old_ring[:-1]
        old_altitudes = (
            list(shape.node_altitudes) if shape.node_altitudes else None
        )
        try:
            remainder = shape.polygon.difference(plate_union)
        except _GEOM_EXC:
            kept_shapes.append(shape)
            continue
        if remainder.is_empty:
            UI.vprint(
                2,
                "   [object-bridge] dropped "
                f"{shape.role}/{shape.ref!r} inside a bridge plate "
                "(non-overlap rule)",
            )
            continue
        parts = (
            list(remainder.geoms)
            if remainder.geom_type == "MultiPolygon" else [remainder]
        )
        from .elevation import _resample_node_altitudes_nn as _resample
        for part in parts:
            if (part.geom_type != "Polygon" or part.is_empty
                    or part.area < 1.0):
                continue
            resampled = _resample(part, old_ring, old_altitudes)
            kept_shapes.append(BuiltShape(
                polygon=part,
                role=shape.role,
                ref=shape.ref,
                altitude=(shape.altitude if resampled is None else None),
                altitude_high=(
                    None if resampled is not None else shape.altitude_high),
                altitude_low=(
                    None if resampled is not None else shape.altitude_low),
                node_altitudes=resampled))
    if n_touched:
        layout.shapes = kept_shapes
        UI.vprint(
            1,
            f"   [object-bridge] non-overlap rule: cut/dropped "
            f"{n_touched} feature shape(s) against the bridge plates",
        )
    return n_touched


def _bridge_crossing_floor_for_bridge(
        bridge, road_networks, dem, tile_lat, tile_lon,
        to_meters, meters_to_lat_lon):
    """The crossing-floor decision for ONE bridge record: ``(floor_value,
    footprint_meters)`` when the span must rise over an un-lowered draped
    road, else ``None``.  Shared verbatim by the solve-side producer
    (:func:`bridge_crossing_floor_nodes`) and the validator
    (``verification.check_bridge_crossing_floor``) so their guards, road
    sampling and law evaluation can never drift (lockstep beyond the law
    function itself).

    Guards: TERRAIN/PROFILE_CARRIED contracts only; flush decks
    (crest below ``config.BRIDGE_ROAD_CLEARANCE_M``) encode "the pack
    handles the road" and get restraint, never a floor (ruling R9); a
    fully-draped DSF road segment must cross the footprint.  Road
    surface = median DEM sample of the draped polyline inside the
    footprint (the road-untouched case; pack-trench and solved-corridor
    sources land with the W-V audits)."""
    from .grade_law import bridge_crossing_floor_m
    from .object_terrain_features import TERRAIN_CARRIED, PROFILE_CARRIED
    if bridge.contract not in (TERRAIN_CARRIED, PROFILE_CARRIED):
        return None
    if float(bridge.deck_top_y_m) < float(_CFG.BRIDGE_ROAD_CLEARANCE_M):
        return None  # flush deck: pack-handled road, restraint only
    footprint = _bridge_footprint_meters(bridge, to_meters)
    if footprint is None:
        return None
    road_lines = _draped_road_centerlines_meters(
        bridge, road_networks, to_meters
    )
    if not road_lines:
        return None
    road_samples: list[float] = []
    for line in road_lines:
        for x, y in line.coords:
            try:
                if not footprint.contains(Point(x, y)):
                    continue
                latitude, longitude = meters_to_lat_lon(x, y)
                sample = _sample_dem(
                    dem, tile_lat, tile_lon, latitude, longitude
                )
            except _GEOM_EXC:
                continue
            if sample is not None and sample == sample:
                road_samples.append(float(sample))
    if not road_samples:
        return None
    road_samples.sort()
    road_surface = road_samples[len(road_samples) // 2]
    underside = bridge.clearance_underside_y_m
    if underside is None:
        underside = bridge.ceiling_y_m
    structure_thickness = (
        max(0.0, float(bridge.deck_top_y_m) - float(underside))
        if underside is not None else 0.0
    )
    return bridge_crossing_floor_m(road_surface, structure_thickness), \
        footprint


def bridge_crossing_floor_nodes(layout, nodes, dem, tile_lat, tile_lon):
    """Feature B stage 2, step 3: per-node floors for TERRAIN/
    PROFILE_CARRIED spans whose road beneath is NOT lowered — the
    crossing must rise, and ``grade_law.bridge_crossing_floor_m`` (road
    surface + clearance + structure thickness) is merged into the
    one-solve's floor dict by max so the hump solves itself under the
    existing grade caps (spec section 3.2, amendment A2).

    Returns ``{node_index: floor_elevation_m}``.  Guards:

    * only spans with a fully-draped DSF road segment crossing the
      footprint (an elevated ramp flies over on its own structure);
    * only decks whose own crest stands at least the road clearance
      above the datum (``deck_top_y_m >= BRIDGE_ROAD_CLEARANCE_M``) —
      a flush deck (EDDF Bridge_2/3/4, crest ≈ 0) encodes "the pack
      handles the road" and gets restraint, never a floor (ruling R9:
      the vertical split is read from the object, not assumed).

    Road surface elevation source (spec order, stage-2 subset): the
    draped road polyline's DEM samples inside the footprint (median) —
    the road-untouched case; the pack-trench and solved-corridor
    sources land with the audits (W-V) once a measured record carries
    them."""
    classification = _object_bridge_classification(layout)
    if classification is None:
        return {}
    road_networks = _object_bridge_road_networks(layout)
    if not road_networks:
        return {}
    to_meters, meters_to_lat_lon = _local_meter_projections(layout.anchor)
    floors: dict = {}
    for bridge in classification.bridges:
        crossing = _bridge_crossing_floor_for_bridge(
            bridge, road_networks, dem, tile_lat, tile_lon,
            to_meters, meters_to_lat_lon,
        )
        if crossing is None:
            continue
        floor_value, footprint = crossing
        applied = 0
        for node_index, (x, y) in enumerate(nodes):
            try:
                if not footprint.contains(Point(x, y)):
                    continue
            except _GEOM_EXC:
                continue
            known = floors.get(node_index)
            if known is None or floor_value > known:
                floors[node_index] = floor_value
                applied += 1
        if applied:
            UI.vprint(
                2,
                f"   [object-bridge] crossing floor {floor_value:.2f} m "
                f"on {applied} node(s) inside {bridge.contract} span "
                f"{bridge.object_resources}",
            )
    return floors


def _emit_underpass_road_approaches(
        layout: "PavementLayout",
        dem,
        tile_lat: int,
        tile_lon: int,
        clearance_depth_m: float = 8.0,
        approach_length_m: float = 80.0,
        road_width_m: float = 22.0,
        ramp_step_m: float = 20.0,
        scenery_has_bridge_objects: bool = False,
        ) -> int:
    """For each underpass case (taxi BRIDGE rect or road TUNNEL
    portal), emit a chain of sloped road-following polygons that
    transition the road surface from outside-DEM elevation down
    to ``apt_elev − clearance_depth_m`` near the underpass and
    back up to DEM after.

    Per user 2026-04-29 (KBNA / KPHX taxi-bridge case): without
    these polygons, the patch's mesh under a bridge sits at
    apt_elev (interpolated from the surrounding airport pavement),
    and OSM-tagged roads rendered at DEM elevation by Ortho4XP's
    road layer get buried.  Emitting a chain of road-following
    polygons forces the mesh under the road to step down to a
    height low enough for the road to clear the bridge underside
    (default 8 m below airport surface), then ramp back up to DEM
    away from the airport.

    Algorithm per underpass surface (bridge rect or tunnel portal
    region):

      1. Find OSM road LineStrings that cross the surface's
         footprint (or pass within 5 m of its long edges, for
         tunnel portals where the road just barely touches).
      2. For each crossing road, find the exterior segments
         immediately approaching and departing the surface.
      3. Walk each approach segment in ``ramp_step_m`` (20 m)
         increments, emitting a sloped 4-corner rect per step
         where elevation interpolates between DEM (start) and
         ``apt_elev − clearance_depth_m`` (end).
      4. Inside the underpass surface itself, emit a flat road-
         following polygon at ``apt_elev − clearance_depth_m``.

    Width of every emitted road polygon: ``road_width_m``
    (22 m by default; matches tunnel-ramp width).

    Returns the number of UNDERPASS surfaces processed.

    Feature B re-source (``O4_OBJECT_BRIDGE_TERRAIN``, spec section 3.2):
    when the object-terrain classifier has run, DECK_CARRIED spans get
    their corridor from the OBJECT'S geometry (footprint, deck elevation,
    girder clearance) and the sibling DSF road network, computed FIRST;
    TERRAIN_CARRIED / PROFILE_CARRIED footprints then SUPPRESS the legacy
    OSM-driven corridor beneath them, and object-handled footprints are not
    re-emitted by the legacy path.  With the gate off there is no cached
    classification and the whole block below is byte-identical to today.
    """
    from .pipeline import _load_osm_big_roads
    # Feature-B object-sourced corridors (gated; no-op when off).
    object_corridor_count = 0
    object_suppression_polygons: list[Polygon] = []
    object_covered_polygons: list[Polygon] = []
    _classification = _object_bridge_classification(layout)
    if _classification is not None:
        (object_corridor_count,
         object_suppression_polygons,
         object_covered_polygons) = _emit_object_sourced_bridge_corridors(
            layout, dem, tile_lat, tile_lon, _classification,
            _object_bridge_road_networks(layout),
            road_width_m, ramp_step_m, approach_length_m,
        )
    _object_footprints = (
        object_suppression_polygons + object_covered_polygons
    )
    # Collect underpass surfaces.
    bridge_shapes = [s for s in layout.shapes
                     if getattr(s, "is_bridge", False)
                     and s.polygon is not None
                     and not s.polygon.is_empty]
    if not bridge_shapes:
        return object_corridor_count
    nodes_r, ways_r = _load_osm_big_roads(
        layout.anchor[0], layout.anchor[1])
    if not ways_r:
        return object_corridor_count
    _to_m, _m_to_ll = _local_meter_projections(layout.anchor)
    nodes_m: dict[str, tuple[float, float]] = {}
    for nid, (lat, lon) in nodes_r.items():
        nodes_m[nid] = _to_m(lon, lat)
    HW_TYPES = {
        "motorway", "trunk", "primary", "secondary",
        "tertiary", "motorway_link", "trunk_link",
        "primary_link", "residential", "service",
    }
    # Collect candidate road LineStrings (not bridge or tunnel
    # tagged — those are special cases).  A road that PASSES
    # UNDER a taxi bridge typically isn't tagged bridge=yes
    # itself; only the airport surface is.  But a ROAD that
    # itself bridges over something else IS tagged bridge=yes;
    # we skip those because we don't want to emit road shapes
    # for road-on-road bridges.
    road_lines: list[LineString] = []
    for _wid, nrefs, tags in ways_r:
        if tags.get("highway") not in HW_TYPES:
            continue
        if tags.get("bridge") and tags.get("bridge") != "no":
            continue
        if (tags.get("tunnel")
                and tags.get("tunnel") != "no"):
            continue
        pts = [nodes_m[n] for n in nrefs if n in nodes_m]
        if len(pts) < 2:
            continue
        try:
            ls = LineString(pts)
        except _GEOM_EXC:
            continue
        if ls.is_empty or ls.length < 5.0:
            continue
        road_lines.append(ls)
    if not road_lines:
        return object_corridor_count
    n_processed = 0
    for s in bridge_shapes:
        # Feature B: skip a bridge rect already handled by an
        # object-sourced corridor (DECK_CARRIED) or lying inside a
        # suppressed TERRAIN/PROFILE_CARRIED span footprint — the object
        # geometry, not the OSM inference, governs there (spec section 3.2).
        if _object_footprints:
            try:
                if any(s.polygon.intersects(footprint)
                       for footprint in _object_footprints):
                    continue
            except _GEOM_EXC:
                pass
        # Bridge deck elevation.
        if (s.altitude_high is not None
                and s.altitude_low is not None):
            deck_elev = 0.5 * (s.altitude_high + s.altitude_low)
        elif s.altitude is not None:
            deck_elev = s.altitude
        else:
            continue
        low_elev = float(deck_elev) - clearance_depth_m
        # Find road LineStrings that cross the bridge footprint.
        for road_ls in road_lines:
            try:
                inside = road_ls.intersection(s.polygon)
            except _GEOM_EXC:
                continue
            if inside.is_empty:
                continue
            # Pick the longest contiguous piece if multiple.
            if hasattr(inside, "geoms"):
                cand = [g for g in inside.geoms
                        if g.geom_type == "LineString"
                        and g.length > 1.0]
                if not cand:
                    continue
                inside = max(cand, key=lambda g: g.length)
            elif inside.geom_type != "LineString":
                continue
            # Inside-bridge flat polygon at low_elev — only emit
            # when the scenery has a 3D bridge OBJ (KBNA case).
            # In that case the road cuts straight through under
            # the bridge model.  Without a bridge OBJ (KPHX
            # case) the taxi rect itself acts as a flat plate
            # and the road approaches stop at the bridge edge.
            if scenery_has_bridge_objects:
                try:
                    inside_buf = inside.buffer(
                        road_width_m / 2.0,
                        cap_style=2, join_style=2)
                    if (inside_buf.geom_type == "Polygon"
                            and not inside_buf.is_empty):
                        layout.shapes.append(BuiltShape(
                            polygon=inside_buf,
                            role=ROLE_TUNNEL_RAMP,
                            ref="bridge_underpass",
                            altitude=round(low_elev, 1)))
                except _GEOM_EXC:
                    pass
            # Approach + departure ramp chains.  Find the parts
            # of the road OUTSIDE the bridge polygon, then walk
            # each in ramp_step_m steps emitting one sloped rect
            # per step.
            try:
                outside = road_ls.difference(s.polygon)
            except _GEOM_EXC:
                outside = None
            if outside is None or outside.is_empty:
                continue
            outside_pieces = (
                list(outside.geoms)
                if hasattr(outside, "geoms")
                else [outside])
            for piece in outside_pieces:
                if (piece.is_empty
                        or piece.geom_type != "LineString"):
                    continue
                # Decide which end of the piece TOUCHES the bridge.
                pcoords = list(piece.coords)
                if len(pcoords) < 2:
                    continue
                p_start = Point(pcoords[0])
                p_end = Point(pcoords[-1])
                d_start = s.polygon.distance(p_start)
                d_end = s.polygon.distance(p_end)
                if d_start <= d_end:
                    # piece runs FROM bridge edge OUT to far end —
                    # walk it as approach (low → high).
                    # Cap to approach_length_m.
                    walk_len = min(piece.length, approach_length_m)
                    bridge_end_pt = piece.interpolate(0.0)
                    far_end_pt = piece.interpolate(walk_len)
                    walk = LineString([(bridge_end_pt.x,
                                          bridge_end_pt.y),
                                        (far_end_pt.x,
                                          far_end_pt.y)])
                    # Use the actual sub-LineString shape for
                    # better following; but for simplicity use the
                    # straight sub-segment for ramp emission.
                    walk = LineString(pcoords[:])
                    # Trim walk to first ``walk_len`` metres.
                else:
                    walk_len = min(piece.length, approach_length_m)
                    walk = LineString(list(reversed(pcoords)))
                # Step through walk_len in ramp_step_m steps.
                # Each step is a sloped rect of (low_elev → DEM).
                u_prev = 0.0
                while u_prev < walk_len - 1.0:
                    u_next = min(walk_len, u_prev + ramp_step_m)
                    p0 = walk.interpolate(u_prev)
                    p1 = walk.interpolate(u_next)
                    seg_len = math.hypot(p1.x - p0.x, p1.y - p0.y)
                    if seg_len < 1.0:
                        break
                    # Tangent + perpendicular.
                    tx = (p1.x - p0.x) / seg_len
                    ty = (p1.y - p0.y) / seg_len
                    nx = -ty
                    ny = tx
                    half_w = road_width_m / 2.0
                    # Elevation interpolation: u_prev → low_elev
                    # at the bridge, DEM at the far end.
                    frac0 = u_prev / walk_len
                    frac1 = u_next / walk_len
                    try:
                        lat0_p, lon0_p = _m_to_ll(p0.x, p0.y)
                        lat1_p, lon1_p = _m_to_ll(p1.x, p1.y)
                        dem0 = _sample_dem(
                            dem, tile_lat, tile_lon,
                            lat0_p, lon0_p)
                        dem1 = _sample_dem(
                            dem, tile_lat, tile_lon,
                            lat1_p, lon1_p)
                    except _GEOM_EXC:
                        dem0 = dem1 = None
                    if dem0 is None or dem1 is None:
                        break
                    e0 = (1.0 - frac0) * low_elev + frac0 * dem0
                    e1 = (1.0 - frac1) * low_elev + frac1 * dem1
                    corners = [
                        (p0.x + nx * half_w,
                         p0.y + ny * half_w),
                        (p1.x + nx * half_w,
                         p1.y + ny * half_w),
                        (p1.x - nx * half_w,
                         p1.y - ny * half_w),
                        (p0.x - nx * half_w,
                         p0.y - ny * half_w),
                    ]
                    try:
                        seg_poly = Polygon(corners)
                        if not seg_poly.is_valid:
                            seg_poly = seg_poly.buffer(0)
                        if (seg_poly.geom_type == "Polygon"
                                and not seg_poly.is_empty):
                            # corners 0,3 = "high" end vs corners
                            # 1,2 = "low" end depends on which
                            # end is closer to the bridge.  e0
                            # (start = bridge side) is lower.
                            if abs(e0 - e1) >= 0.1:
                                layout.shapes.append(BuiltShape(
                                    polygon=seg_poly,
                                    role=ROLE_TUNNEL_RAMP,
                                    ref="bridge_approach",
                                    altitude_high=round(
                                        max(e0, e1), 1),
                                    altitude_low=round(
                                        min(e0, e1), 1)))
                            else:
                                layout.shapes.append(BuiltShape(
                                    polygon=seg_poly,
                                    role=ROLE_TUNNEL_RAMP,
                                    ref="bridge_approach",
                                    altitude=round(
                                        0.5 * (e0 + e1), 1)))
                    except _GEOM_EXC:
                        pass
                    u_prev = u_next
        n_processed += 1
    return n_processed + object_corridor_count


def _discover_depressed_roads(
        layout: "PavementLayout",
        xplane_root: str,
        icao: str,
        ) -> tuple[dict | None, set | None, BaseGeometry | None]:
    """Shared discovery for the depressed-road system (geometry only,
    no DEM): which OSM highway ways must be depressed through this
    airport.  A way qualifies when its inside-boundary stretch passes
    under an ``aeroway=*, bridge=yes`` way, plus every way CONNECTED
    to a qualifying one via shared OSM nodes inside the boundary
    (on/off ramps).  Factored out of
    ``_emit_through_airport_depressed_roads`` so the PRE-solve
    terminal-gap carve can see the same corridors the POST-solve
    plate emitter will pave.

    Returns ``(way_lookup, depressed_set, boundary)`` —
    ``way_lookup``: wid → (LineString in layout meters, node refs);
    ``depressed_set``: the qualifying wids — or ``(None, None,
    None)`` when the airport has no depressed roads.
    """
    from .pipeline import _load_osm_airports, _load_osm_big_roads
    if (layout.airport_boundary is None
            or layout.airport_boundary.is_empty):
        return (None, None, None)
    boundary = layout.airport_boundary
    # Build a slightly contracted boundary for inside-vs-outside
    # tests so a road point exactly ON the boundary doesn't bounce
    # between true / false on numeric jitter.
    try:
        boundary_strict = boundary.buffer(-0.5)
        if boundary_strict.is_empty:
            boundary_strict = boundary
    except _GEOM_EXC:
        boundary_strict = boundary

    # Load OSM airport-layer tile (for aeroway=bridge LineStrings).
    try:
        nodes_a, ways_a, _ = _load_osm_airports(
            xplane_root, icao,
            layout.anchor[0], layout.anchor[1])
    except _GEOM_EXC:
        return (None, None, None)
    if not ways_a:
        return (None, None, None)

    _to_m, _m_to_ll = _local_meter_projections(layout.anchor)

    # ── Bridge LineStrings (airport-layer OSM) ─────────────────
    bridge_lines: list[LineString] = []
    nodes_a_m: dict[str, tuple[float, float]] = {}
    for nid, (lat, lon) in nodes_a.items():
        nodes_a_m[nid] = _to_m(lon, lat)
    for wid, nrefs, tags in ways_a:
        if not tags.get("aeroway"):
            continue
        if tags.get("bridge", "") not in ("yes", "viaduct"):
            continue
        pts = [nodes_a_m[n] for n in nrefs if n in nodes_a_m]
        if len(pts) < 2:
            continue
        try:
            ls = LineString(pts)
        except _GEOM_EXC:
            continue
        if ls.is_empty or ls.length < 5.0:
            continue
        bridge_lines.append(ls)
    if not bridge_lines:
        return (None, None, None)

    # Load OSM big_roads (for highway ways) — only now that we know
    # the airport actually has aeroway bridges.
    nodes_r, ways_r = _load_osm_big_roads(
        layout.anchor[0], layout.anchor[1])
    if not ways_r:
        return (None, None, None)

    # ── Highway candidates (big_roads OSM) ─────────────────────
    HW_TYPES = {
        "motorway", "trunk", "primary", "secondary",
        "tertiary", "motorway_link", "trunk_link",
        "primary_link", "secondary_link", "tertiary_link",
        "residential", "service", "unclassified",
    }
    nodes_r_m: dict[str, tuple[float, float]] = {}
    for nid, (lat, lon) in nodes_r.items():
        nodes_r_m[nid] = _to_m(lon, lat)
    way_data: list[tuple[str, LineString, list[str]]] = []
    for wid, nrefs, tags in ways_r:
        if tags.get("highway") not in HW_TYPES:
            continue
        if tags.get("bridge", "") in ("yes", "viaduct"):
            # The road IS the bridge, not what's under — skip.
            continue
        # tunnel=building_passage tagging is INCLUDED.  At KPHX,
        # the under-bridge road segments use this tag; they're
        # exactly the seeds we want.
        pts = [nodes_r_m[n] for n in nrefs if n in nodes_r_m]
        if len(pts) < 2:
            continue
        try:
            ls = LineString(pts)
        except _GEOM_EXC:
            continue
        if ls.is_empty or ls.length < 5.0:
            continue
        way_data.append((wid, ls, list(nrefs)))
    if not way_data:
        return (None, None, None)

    # ── Seed: ways whose inside-boundary section crosses a bridge ──
    BRIDGE_PROXIMITY_M = 5.0
    seed_depressed: set = set()
    for wid, ls, _nrefs in way_data:
        try:
            inside = ls.intersection(boundary)
        except _GEOM_EXC:
            continue
        if inside.is_empty:
            continue
        segs = []
        if inside.geom_type == "LineString":
            segs = [inside]
        elif inside.geom_type == "MultiLineString":
            segs = list(inside.geoms)
        for seg in segs:
            if seg.is_empty or seg.length < 1.0:
                continue
            for bls in bridge_lines:
                try:
                    if seg.distance(bls) < BRIDGE_PROXIMITY_M:
                        seed_depressed.add(wid)
                        break
                except _GEOM_EXC:
                    continue
            if wid in seed_depressed:
                break
    if not seed_depressed:
        return (None, None, None)

    # ── BFS over OSM-graph node-sharing INSIDE the boundary ────
    # On-ramps/off-ramps inside the airport are separate OSM
    # ways; if they connect to a depressed seed at any node
    # INSIDE the boundary, they must be depressed too (otherwise
    # the seed and the connecting way disagree on altitude at
    # their shared node and X-Plane renders a cliff).
    node_to_ways: dict[str, list[str]] = {}
    way_lookup: dict[str, tuple[LineString, list[str]]] = {}
    for wid, ls, nrefs in way_data:
        way_lookup[wid] = (ls, nrefs)
        for n in nrefs:
            node_to_ways.setdefault(n, []).append(wid)
    depressed_set: set = set(seed_depressed)
    queue: list[str] = list(seed_depressed)
    while queue:
        wid = queue.pop()
        ls, nrefs = way_lookup[wid]
        for n in nrefs:
            n_xy = nodes_r_m.get(n)
            if n_xy is None:
                continue
            try:
                if not boundary_strict.contains(Point(n_xy)):
                    continue
            except _GEOM_EXC:
                continue
            for other_wid in node_to_ways.get(n, []):
                if other_wid in depressed_set:
                    continue
                # Only propagate if the other way also has an
                # inside-boundary portion (otherwise it's just a
                # surface road glancing the boundary node).
                _o_ls, _o_nrefs = way_lookup[other_wid]
                try:
                    if _o_ls.intersection(boundary).is_empty:
                        continue
                except _GEOM_EXC:
                    continue
                depressed_set.add(other_wid)
                queue.append(other_wid)
    return (way_lookup, depressed_set, boundary)


def _depressed_road_corridor_band(
        layout: "PavementLayout",
        xplane_root: str,
        icao: str,
        road_width_m: float = 22.0,
        clearance_m: float = 0.5,
        ) -> BaseGeometry | None:
    """The inside-boundary depressed-road corridor, buffered to road
    half-width + ``clearance_m`` — the band that must stay OPEN
    through terminal pads (per user 2026-06-10: terminals split and
    leave a gap for the road to pass through; the road then keeps
    ``clearance_m`` to the terminal edges).  ``None`` when the
    airport has no depressed roads."""
    way_lookup, depressed_set, boundary = _discover_depressed_roads(
        layout, xplane_root, icao)
    if not depressed_set:
        return None
    bands: list[BaseGeometry] = []
    half_w = road_width_m / 2.0
    for wid in sorted(depressed_set):
        ls, _nrefs = way_lookup[wid]
        try:
            inside = ls.intersection(boundary)
        except _GEOM_EXC:
            continue
        if inside.is_empty:
            continue
        try:
            band = inside.buffer(half_w + clearance_m,
                                 cap_style=2, join_style=2)
        except _GEOM_EXC:
            continue
        if not band.is_empty:
            bands.append(band)
    if not bands:
        return None
    try:
        return unary_union(bands)
    except _GEOM_EXC:
        return None


def _emit_through_airport_depressed_roads(
        layout: "PavementLayout",
        dem,
        tile_lat: int,
        tile_lon: int,
        xplane_root: str,
        icao: str,
        depression_depth_m: float = 8.0,
        max_ramp_grade: float = 0.04,
        ramp_min_length_m: float = 200.0,
        arm_max_length_m: float = 500.0,
        road_width_m: float = 22.0,
        retaining_wall_width_m: float = 1.0,
        wall_gap_m: float = 0.5,
        boundary_clearance_m: float = 1.0,
        ) -> tuple[int, set]:
    """For each public road that ENTERS the airport boundary
    AND passes under a tagged ``aeroway=*, bridge=yes`` way (or
    is connected via OSM-graph node-sharing to a road that does)
    inside the airport, emit:

      1. A flat road-following polygon along the entire inside-
         boundary stretch at ``apt_elev − depression_depth_m``.
         Subsequent OSM road rendering (Ortho4XP's own road
         layer) sits on top of this flat plate.
      2. At each boundary entry/exit point, a ramp polygon
         OUTSIDE the airport that climbs from the depressed
         level back up to the local DEM, capped at
         ``max_ramp_grade`` (default 4 %).

    Per user 2026-04-29 (KPHX Sky Harbor Blvd): when a road
    passes under multiple airport bridges, the road MUST be
    depressed for its entire inside-airport stretch — not just
    at the bridges.  Two bridges spanning the same continuous
    road imply the road can never come back up between them.
    The general solution: any road that enters the airport
    boundary and crosses any aeroway=bridge inside is treated
    this way, plus any road CONNECTED to it via shared OSM
    nodes within the boundary (so on/off ramps inside the
    airport stay coherent with the main road).

    OSM tags consulted:
      * ``aeroway=*, bridge=yes|viaduct`` — bridge LineStrings
        (the airport surface above the depression).
      * ``highway=*`` (motorway, trunk, primary, secondary,
        tertiary, residential, service + their *_link forms) —
        the road network candidates.
      * ``bridge=yes|viaduct`` on a highway — that road is
        ITSELF a bridge over something else (skip; we're
        looking for the road UNDERNEATH).
      * ``tunnel=yes|building_passage`` on a highway — INCLUDED
        as seeds (the airport-bridge case typically tags the
        under-bridge road segment as building_passage in OSM).
        ``_emit_tunnel_portals`` is told to skip every OSM way
        depressed here so we don't double-emit.

    Boundary coordination: the union of every emitted polygon
    is buffered by ``boundary_clearance_m`` and subtracted from
    each ``ROLE_BOUNDARY`` shape (same pattern as the tunnel
    and taxi-bridge emitters), with NN-resampling of per-vertex
    altitudes so the boundary ribbon retains its altitude tags
    after the clip.

    Returns ``(n_emitted, depressed_way_ids)``.  The way-id
    set is intended for ``_emit_tunnel_portals`` to skip — it
    contains every OSM highway way (raw road network) handled
    by this pass, so the explicit-tunnel emitter doesn't
    double-process the same building_passage segments.
    """
    way_lookup, depressed_set, boundary = _discover_depressed_roads(
        layout, xplane_root, icao)
    if not depressed_set:
        return (0, set())

    plan_grade = max(
        max_ramp_grade - TUNNEL_RAMP_GRADE_SAFETY_MARGIN, 1e-3)
    arm_walk_max_m = max(arm_max_length_m, ramp_min_length_m,
                         depression_depth_m / plan_grade)

    _to_m, _m_to_ll = _local_meter_projections(layout.anchor)

    def _airport_elevation_at(cx: float, cy: float) -> float | None:
        # Reuse pattern from _emit_tunnel_portals: prefer the
        # boundary-ribbon's per-vertex altitude near the point,
        # fall back to DEM.
        best_d = float('inf')
        best_alt: float | None = None
        for s in layout.shapes:
            if s.role != ROLE_BOUNDARY:
                continue
            if s.ref != "airport_boundary":
                continue
            if not s.node_altitudes:
                continue
            try:
                rcoords = list(s.polygon.exterior.coords)
            except _GEOM_EXC:
                continue
            if rcoords and rcoords[0] == rcoords[-1]:
                rcoords = rcoords[:-1]
            for k, (vx, vy) in enumerate(rcoords):
                if k >= len(s.node_altitudes):
                    break
                d = math.hypot(vx - cx, vy - cy)
                if d < best_d:
                    best_d = d
                    best_alt = s.node_altitudes[k]
        if best_alt is not None and best_d <= 400.0:
            return float(best_alt)
        try:
            lat, lon = _m_to_ll(cx, cy)
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None

    # ── Emit one set of polygons per depressed way ─────────────
    n_emitted = 0
    exclusion_zones: list[Polygon] = []
    half_w = road_width_m / 2.0

    # Airside clearance union (user 2026-06-10): a depressed-road
    # plate must STOP ``wall_gap_m`` (0.5 m) short of taxiway /
    # junction / apron / runway pavement — the airside surface IS
    # the bridge deck there — and resume on the other side.
    # Terminals are NOT in this union: they yield instead (the
    # pre-solve terminal-gap carve splits the pad around the road
    # corridor), so a plate crossing an uncarved terminal shows up
    # as an overlap warning rather than silently truncating the
    # road.
    _AIRSIDE_STOP_ROLES = {
        ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_PRIMARY_PARALLEL,
        ROLE_SECONDARY_PARALLEL, ROLE_STUB, ROLE_CROSS_CONNECTOR,
        ROLE_JUNCTION, ROLE_APRON,
    }
    try:
        _airside_polys = [s.polygon for s in layout.shapes
                          if s.role in _AIRSIDE_STOP_ROLES
                          and s.polygon is not None
                          and not s.polygon.is_empty]
        airside_clear = (unary_union(_airside_polys)
                         .buffer(wall_gap_m)
                         if _airside_polys else None)
    except _GEOM_EXC:
        airside_clear = None
    # Terminal pads: the pre-solve carve already splits them around
    # the road corridor with the 0.5 m clearance; subtract them
    # UNBUFFERED here too so buffer-miter mismatches between the
    # carve band and the plate buffer can't leave cm² overlaps at
    # bends (KPHX terminal2, 0.4 m²).
    try:
        _term_polys = [s.polygon for s in layout.shapes
                       if s.role == ROLE_BUILDING
                       and s.polygon is not None
                       and not s.polygon.is_empty]
        terminal_union = (unary_union(_term_polys)
                          if _term_polys else None)
    except _GEOM_EXC:
        terminal_union = None
    # Running union of already-emitted plates: parallel
    # carriageways / ramp chains closer than the 22 m plate width
    # used to emit overlapping plates (KPHX Sky Harbor Blvd,
    # overlap storm up to 1 437 m²); subtracting the running union
    # (buffered 1 cm so shared-edge float noise becomes a hairline
    # gap, not an epsilon overlap) keeps the depressed surface
    # single-cover.
    plate_union: BaseGeometry | None = None
    MIN_PLATE_PIECE_M2 = 25.0

    def _smooth_walk(pts: list[tuple[float, float]],
                      min_segment_m: float = 15.0
                      ) -> list[tuple[float, float]]:
        """Drop near-colinear / closely-spaced intermediate
        vertices so altitude rounding can't push per-segment
        grade above the design limit."""
        if len(pts) < 3:
            return list(pts)
        merged: list[tuple[float, float]] = [pts[0]]
        for k in range(1, len(pts)):
            d = math.hypot(pts[k][0] - merged[-1][0],
                           pts[k][1] - merged[-1][1])
            if d < min_segment_m and k != len(pts) - 1:
                continue
            merged.append(pts[k])
        return merged

    for wid in sorted(depressed_set):
        ls, nrefs = way_lookup[wid]
        # 1) Inside-boundary flat plate(s).
        try:
            inside = ls.intersection(boundary)
        except _GEOM_EXC:
            continue
        if inside.is_empty:
            continue
        inside_segs = []
        if inside.geom_type == "LineString":
            inside_segs = [inside]
        elif inside.geom_type == "MultiLineString":
            inside_segs = list(inside.geoms)
        for seg in inside_segs:
            if seg.is_empty or seg.length < 5.0:
                continue
            ctr = seg.centroid
            apt_elev = _airport_elevation_at(ctr.x, ctr.y)
            if apt_elev is None:
                continue
            elev_low = apt_elev - depression_depth_m
            try:
                flat_poly = seg.buffer(
                    half_w, cap_style=2, join_style=2)
                if not flat_poly.is_valid:
                    flat_poly = flat_poly.buffer(0)
            except _GEOM_EXC:
                continue
            if flat_poly.is_empty:
                continue
            # Stop short of airside pavement (0.5 m) and of plates
            # already emitted; what survives on each side of a
            # bridge deck is its own plate ("start again on the
            # other side").
            clipped = flat_poly
            try:
                if airside_clear is not None:
                    clipped = clipped.difference(airside_clear)
                if terminal_union is not None:
                    clipped = clipped.difference(terminal_union)
                if plate_union is not None:
                    clipped = clipped.difference(
                        plate_union.buffer(0.01))
            except _GEOM_EXC:
                pass
            if clipped.is_empty:
                continue
            plate_pieces = [g for g in
                            (clipped.geoms
                             if hasattr(clipped, "geoms")
                             else [clipped])
                            if g.geom_type == "Polygon"
                            and not g.is_empty
                            and g.area >= MIN_PLATE_PIECE_M2]
            for plate in plate_pieces:
                layout.shapes.append(BuiltShape(
                    polygon=plate,
                    role=ROLE_TUNNEL_RAMP,
                    ref="depressed_road",
                    altitude=round(elev_low, 1)))
                exclusion_zones.append(plate)
                n_emitted += 1
            if plate_pieces:
                try:
                    new_u = unary_union(plate_pieces)
                    plate_union = (new_u if plate_union is None
                                   else plate_union.union(new_u))
                except _GEOM_EXC:
                    pass

        # 2) Outside-boundary ramp(s) — one per side of the
        #    boundary the way crosses.  Take the OSM polyline
        #    OUTSIDE the boundary; for each outside piece, walk
        #    OUTWARD from the boundary edge, truncate where the
        #    grade requirement is satisfied, then emit ramp
        #    polygons with bisector vertex sharing at bends.
        try:
            outside = ls.difference(boundary)
        except _GEOM_EXC:
            outside = None
        if outside is None or outside.is_empty:
            continue
        outside_pieces = ([outside]
                          if outside.geom_type == "LineString"
                          else (list(outside.geoms)
                                if outside.geom_type == "MultiLineString"
                                else []))
        for piece in outside_pieces:
            if piece.is_empty or piece.length < 5.0:
                continue
            coords = list(piece.coords)
            # Order coords so coords[0] is at the boundary,
            # coords[-1] is far outside.  The boundary edge is
            # the closest of the two endpoints to the boundary
            # exterior (distance 0 vs distance > 0).
            try:
                d_start = boundary.exterior.distance(
                    Point(coords[0]))
            except _GEOM_EXC:
                d_start = float('inf')
            try:
                d_end = boundary.exterior.distance(
                    Point(coords[-1]))
            except _GEOM_EXC:
                d_end = float('inf')
            if d_end < d_start:
                coords = list(reversed(coords))
            walk = _smooth_walk(coords)
            if len(walk) < 2:
                continue
            # Truncate the walk to a length whose grade keeps
            # ≤ plan_grade given DEM at the far end.
            apt_elev = _airport_elevation_at(*walk[0])
            if apt_elev is None:
                continue
            elev_low = apt_elev - depression_depth_m
            cum = 0.0
            kept_pts: list[tuple[float, float]] = [walk[0]]
            grade_ok_at: float = 0.0
            for i in range(1, len(walk)):
                seg_len = math.hypot(
                    walk[i][0] - walk[i - 1][0],
                    walk[i][1] - walk[i - 1][1])
                cum += seg_len
                kept_pts.append(walk[i])
                if cum > arm_walk_max_m:
                    grade_ok_at = cum
                    break
                try:
                    plat, plon = _m_to_ll(*walk[i])
                    dem_h = _sample_dem(
                        dem, tile_lat, tile_lon, plat, plon)
                except _GEOM_EXC:
                    dem_h = None
                if dem_h is None:
                    continue
                drop = float(dem_h) - elev_low
                req = (drop / plan_grade if drop > 0 else 0.0)
                if cum >= req and cum >= ramp_min_length_m:
                    grade_ok_at = cum
                    break
                grade_ok_at = cum
            walk = kept_pts
            if len(walk) < 2:
                continue
            far_xy = walk[-1]
            try:
                far_lat, far_lon = _m_to_ll(*far_xy)
                far_dem = _sample_dem(
                    dem, tile_lat, tile_lon, far_lat, far_lon)
            except _GEOM_EXC:
                far_dem = None
            if far_dem is None:
                far_dem = apt_elev
            max_drop = plan_grade * grade_ok_at
            if (far_dem - elev_low) > max_drop:
                far_dem = elev_low + max_drop
            elev_high = far_dem
            cum_dists = [0.0]
            for i in range(1, len(walk)):
                cum_dists.append(cum_dists[-1] + math.hypot(
                    walk[i][0] - walk[i - 1][0],
                    walk[i][1] - walk[i - 1][1]))
            total_walk = cum_dists[-1]
            if total_walk < 5.0:
                continue
            # Per-vertex bisector perpendicular for shared corners
            # at bends (same pattern as _emit_tunnel_portals).
            n_w = len(walk)
            verts_perp: list[tuple[float, float]] = []
            verts_scale: list[float] = []
            for i in range(n_w):
                if i == 0:
                    s = (walk[1][0] - walk[0][0],
                         walk[1][1] - walk[0][1])
                    sl = math.hypot(*s) or 1e-6
                    verts_perp.append((-s[1] / sl, s[0] / sl))
                    verts_scale.append(1.0)
                elif i == n_w - 1:
                    s = (walk[i][0] - walk[i - 1][0],
                         walk[i][1] - walk[i - 1][1])
                    sl = math.hypot(*s) or 1e-6
                    verts_perp.append((-s[1] / sl, s[0] / sl))
                    verts_scale.append(1.0)
                else:
                    s1 = (walk[i][0] - walk[i - 1][0],
                          walk[i][1] - walk[i - 1][1])
                    s2 = (walk[i + 1][0] - walk[i][0],
                          walk[i + 1][1] - walk[i][1])
                    l1 = math.hypot(*s1) or 1e-6
                    l2 = math.hypot(*s2) or 1e-6
                    u1 = (s1[0] / l1, s1[1] / l1)
                    u2 = (s2[0] / l2, s2[1] / l2)
                    avg = ((u1[0] + u2[0]) / 2.0,
                           (u1[1] + u2[1]) / 2.0)
                    al = math.hypot(*avg)
                    if al < 1e-6:
                        verts_perp.append((-u1[1], u1[0]))
                        verts_scale.append(1.0)
                        continue
                    tangent = (avg[0] / al, avg[1] / al)
                    perp = (-tangent[1], tangent[0])
                    dot = u1[0] * u2[0] + u1[1] * u2[1]
                    cos_half = max(0.1, math.sqrt(
                        max(0.0, (1.0 + dot) / 2.0)))
                    verts_perp.append(perp)
                    verts_scale.append(1.0 / cos_half)

            def _vertex_offset(idx: int, off: float
                               ) -> tuple[float, float]:
                px, py = walk[idx]
                nx, ny = verts_perp[idx]
                scaled = off * verts_scale[idx]
                return (px + nx * scaled, py + ny * scaled)

            # Same EFFECTIVE-length lerp as ``_emit_chain``: the miter
            # join shortens the inner quad edge on bends, so a
            # centerline-proportional Δe reads over the ramp cap along
            # that edge.
            effective_cums = [0.0]
            for i in range(n_w - 1):
                seg_len = cum_dists[i + 1] - cum_dists[i]
                edge_plus = math.dist(_vertex_offset(i, +half_w),
                                      _vertex_offset(i + 1, +half_w))
                edge_minus = math.dist(_vertex_offset(i, -half_w),
                                       _vertex_offset(i + 1, -half_w))
                effective_cums.append(
                    effective_cums[-1]
                    + min(seg_len, edge_plus, edge_minus))
            effective_total = effective_cums[-1]
            if effective_total < 1.0:
                continue

            for i in range(n_w - 1):
                d_a = cum_dists[i]
                d_b = cum_dists[i + 1]
                seg_len = d_b - d_a
                if seg_len < 0.5:
                    continue
                frac_a = effective_cums[i] / effective_total
                frac_b = effective_cums[i + 1] / effective_total
                e_a = (1 - frac_a) * elev_low + frac_a * elev_high
                e_b = (1 - frac_b) * elev_low + frac_b * elev_high
                ra = _vertex_offset(i, +half_w)
                rb = _vertex_offset(i + 1, +half_w)
                rc = _vertex_offset(i + 1, -half_w)
                rd = _vertex_offset(i, -half_w)
                # Corners [0, 3] = HIGH end, [1, 2] = LOW end.
                if e_b >= e_a:
                    ramp_corners = [rb, ra, rd, rc]
                    eh, el = e_b, e_a
                else:
                    ramp_corners = [ra, rb, rc, rd]
                    eh, el = e_a, e_b
                try:
                    rp = Polygon(ramp_corners)
                    if not rp.is_valid:
                        rp = rp.buffer(0)
                    if (rp.geom_type != "Polygon"
                            or rp.is_empty
                            or rp.area < 0.5):
                        continue
                except _GEOM_EXC:
                    continue
                if abs(eh - el) >= 0.1:
                    layout.shapes.append(BuiltShape(
                        polygon=rp,
                        role=ROLE_TUNNEL_RAMP,
                        ref="depressed_approach",
                        altitude_high=round(eh, 2),
                        altitude_low=round(el, 2)))
                else:
                    layout.shapes.append(BuiltShape(
                        polygon=rp,
                        role=ROLE_TUNNEL_RAMP,
                        ref="depressed_approach",
                        altitude=round(0.5 * (eh + el), 2)))
                exclusion_zones.append(rp)

    # ── Boundary coordination ─────────────────────────────────
    if exclusion_zones:
        try:
            depressed_union = unary_union(exclusion_zones)
        except _GEOM_EXC:
            depressed_union = None
        if (depressed_union is None
                or depressed_union.is_empty):
            return (n_emitted, depressed_set)
        excl_union = depressed_union.buffer(boundary_clearance_m)
        kept_shapes: list[BuiltShape] = []
        for s in layout.shapes:
            if s.role != ROLE_BOUNDARY:
                kept_shapes.append(s)
                continue
            try:
                _old_ring = list(s.polygon.exterior.coords)
            except _GEOM_EXC:
                _old_ring = []
            if _old_ring and _old_ring[0] == _old_ring[-1]:
                _old_ring = _old_ring[:-1]
            _old_alts = (list(s.node_altitudes)
                          if s.node_altitudes else None)
            try:
                new_poly = s.polygon.difference(excl_union)
            except _GEOM_EXC:
                kept_shapes.append(s)
                continue
            if new_poly.is_empty:
                continue
            if new_poly.geom_type == "Polygon":
                s.polygon = new_poly
                resampled = _resample_node_altitudes_nn(
                    new_poly, _old_ring, _old_alts)
                if resampled is not None:
                    s.node_altitudes = resampled
                kept_shapes.append(s)
            elif new_poly.geom_type == "MultiPolygon":
                for g in new_poly.geoms:
                    if (g.geom_type != "Polygon"
                            or g.is_empty
                            or g.area < 5.0):
                        continue
                    resampled = _resample_node_altitudes_nn(
                        g, _old_ring, _old_alts)
                    kept_shapes.append(BuiltShape(
                        polygon=g,
                        role=s.role,
                        ref=s.ref,
                        altitude=(s.altitude
                                  if resampled is None
                                  else None),
                        node_altitudes=resampled))
        layout.shapes = kept_shapes
    return (n_emitted, depressed_set)
