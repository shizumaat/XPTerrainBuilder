"""OSM cache + apt.dat selection helpers used by the pipeline.

These functions sit between the orchestrator (``driver``) and the
per-airport build (``pipeline.build_airport_pavement``):

* ``_load_osm_tile``: parse one Ortho4XP-cached OSM tile via
  ``O4_OSM_Utils.OSM_layer.update_dicosm``.  Returns the tile's
  nodes, ways, and outer-relation members in auto_patch's tuple
  shape.
* ``_load_osm_airports``: load + namespace-merge the 9 adjacent
  airport-layer tiles around a given airport coord.  Auto-downloads
  the natural tile on first use if not cached.
* ``_score_apt_dat_against_osm``: rate how well an apt.dat covers
  the OSM-known apron / taxiway features at a given airport.
* ``_pick_best_apt_dat_against_osm``: choose the apt.dat for an
  airport — currently a Custom Scenery pack if present, else Global
  Airports / default (no pavement / OSM coverage analysis).
* ``_load_osm_big_roads``: load the highway-layer OSM tile for the
  airport's bbox (used by groundside / boundary / bridges).
* ``_load_airport_road_network``: the AIRPORT-REGION ROAD FEED — the
  shared road/rail dataset published on ``layout.airport_road_network``,
  read from the regional-extract clip when the tile ``small_roads``
  cache is absent (which, at default ``road_level``, is always).  See
  the section header at the bottom of this module.

All public names are leading-underscored to keep them
package-internal; ``pipeline.build_airport_pavement`` imports them
via ``from .osm_load import ...``.
"""
from __future__ import annotations

import functools
import math
import os
import time

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from . import apt_dat_reader as APR
from .layout import R_EARTH
from .pavement.runways import _runway_rect_m

# Narrow exception tuple for shapely / numeric-geometry failure
# modes.  Programming errors propagate so they surface immediately.
# Includes ``OSError`` because osm_load mixes shapely ops with file
# I/O (apt.dat / OSM cache reads, Overpass downloads).
_GEOM_EXC = (OSError, ValueError,
             GEOSException, TopologicalError)


__all__ = [
    "AirportRoadNetwork",
    "_load_airport_road_network",
    "_load_osm_airports",
    "_load_osm_big_roads",
    "_load_osm_small_roads",
    "_load_osm_tile",
    "_pick_best_apt_dat_against_osm",
    "_score_apt_dat_against_osm",
]


@functools.lru_cache(maxsize=32)
def _load_osm_tile(path: str) -> tuple[dict[str, tuple[float, float]],
                                       list[tuple[str, list[str], dict[str, str]]],
                                       list[tuple[str, list[str], dict[str, str]]],
                                       dict[str, dict[str, str]]]:
    """Parse an Ortho4XP-cached OSM tile (.osm.bz2 or .osm).

    Cached by PATH (``maxsize=32`` covers a tile's 3×3 neighbourhood across the
    airport / big_roads / small_roads layers).  ``_load_osm_road_layer`` /
    ``_load_osm_airports`` are keyed on the AIRPORT COORD, so without this each
    airport in a tile re-parsed the same (up to 50 MB, dense-area) bz2 files —
    N× per tile serially, and once per worker in the parallel build.  Callers
    build NEW namespace-prefixed node/way structures from the return, so the
    cached objects are never mutated (READ-ONLY contract).

    Delegates to ``O4_OSM_Utils.OSM_layer.update_dicosm`` for the
    actual XML parsing (handles bz2 + plain, encoding edge cases,
    self-closing tags, escaped quotes, etc.) then adapts the layer's
    data structures into the auto_patch tuple shape:

      * nodes: ``{id: (lat, lon)}``  — note auto_patch uses ``(lat, lon)``;
        OSM_layer stores ``(lon, lat)``, so coords are flipped here.
      * ways:  ``[(id, [nd_ref, ...], {tag: val})]``
      * relations: ``[(id, [member_way_ref, ...], {tag: val})]``
        — only outer-role way members are included.
      * node_tags: ``{id: {tag: val}}`` for the (few) nodes that carry
        tags the layer's download whitelist retained — e.g. the road
        layers' at-grade level-crossing evidence
        (``aeroway=aircraft_crossing``, ``barrier`` gates).  Caches
        written before the tag-schema bump simply yield ``{}``.

    All IDs are stringified at the boundary because every downstream
    auto_patch caller treats node/way IDs as opaque strings (and
    builds tile-prefixed keys like ``"t+30+031:-42"`` for the
    cross-tile-merge step in ``_load_osm_airports``).
    """
    import O4_OSM_Utils as OSM
    layer = OSM.OSM_layer()
    if not layer.update_dicosm(path):
        return {}, [], [], {}
    return _osm_layer_to_tuples(layer)


def _osm_layer_to_tuples(layer) -> tuple[dict[str, tuple[float, float]],
                                         list[tuple[str, list[str], dict[str, str]]],
                                         list[tuple[str, list[str], dict[str, str]]],
                                         dict[str, dict[str, str]]]:
    """Adapt a populated ``O4_OSM_Utils.OSM_layer`` into auto_patch's
    ``(nodes, ways, relations, node_tags)`` tuple shape.

    Factored out of :func:`_load_osm_tile` so the airport-region road
    feed (which populates a layer from EXTRACT-filtered XML bytes rather
    than from a cached tile file) produces byte-for-byte the same
    structures — one adapter, one coordinate-flip convention, one place
    to change."""
    nodes: dict[str, tuple[float, float]] = {
        str(nid): (lat, lon)
        for nid, (lon, lat) in layer.dicosmn.items()
    }
    way_tags = layer.dicosmtags.get("w", {})
    ways: list[tuple[str, list[str], dict[str, str]]] = [
        (str(wid), [str(nid) for nid in nds], way_tags.get(wid, {}))
        for wid, nds in layer.dicosmw.items()
    ]
    rel_tags = layer.dicosmtags.get("r", {})
    relations: list[tuple[str, list[str], dict[str, str]]] = []
    for rid, role_dict in layer.dicosmrorig.items():
        outer = role_dict.get("outer", []) if isinstance(role_dict, dict) else []
        relations.append(
            (str(rid), [str(wid) for wid in outer], rel_tags.get(rid, {})))
    node_tags: dict[str, dict[str, str]] = {
        str(nid): tags
        for nid, tags in layer.dicosmtags.get("n", {}).items()
    }
    return nodes, ways, relations, node_tags


# `_osm_tile_path` removed — was a hand-rolled reimplementation of
# `O4_File_Names.osm_cached(lat, lon, suffix)`.  Call sites now use
# `FNAMES.osm_cached` directly.


def ensure_airports_osm_tile_cached(tile_latitude: int,
                                    tile_longitude: int) -> bool:
    """Download the ``airports`` OSM cache for one 1°×1° tile if absent.

    Shared by the per-airport loader below (which keeps
    build_airport_pavement self-sufficient for standalone use, e.g.
    tests) and by the tile driver's prefetch, which downloads every
    tile the airport builds will need ONCE, up front, so the parallel
    airport worker processes never issue duplicate Overpass queries
    for the same tile.  Returns True when the cache file exists on
    return.
    """
    cache_path = FNAMES.osm_cached(tile_latitude, tile_longitude,
                                   "airports")
    if os.path.isfile(cache_path):
        return True
    try:
        import O4_OSM_Utils as _OSM
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        layer = _OSM.OSM_layer()
        queries = [('node["aeroway"]', 'way["aeroway"]',
                    'rel["aeroway"]')]
        _OSM.OSM_queries_to_OSM_layer(
            queries, layer, tile_latitude, tile_longitude,
            tags_of_interest=["all"],
            cached_suffix="airports")
    except _GEOM_EXC as exc:
        UI.vprint(1,
            f"  [pav-builder] WARN: airport OSM download error: "
            f"{exc}")
    return os.path.isfile(cache_path)


def _load_osm_airports(xplane_root: str, icao: str,
                       apt_lat: float, apt_lon: float,
                       radius_deg: float = 0.05
                       ) -> tuple[dict[str, tuple[float, float]],
                                  list[tuple[str, list[str], dict[str, str]]],
                                  list[tuple[str, list[str], dict[str, str]]]]:
    """Load the airports-layer OSM cache covering the given lat/lon.

    Returns nodes + ways filtered to a bbox around the airport.
    """
    def _tile_path(lat_tile: int, lon_tile: int) -> str:
        return FNAMES.osm_cached(lat_tile, lon_tile, "airports")

    # An airport near a tile boundary may be cached in an adjacent
    # tile — try the natural tile + all 8 neighbours and merge.
    base_lat = int(math.floor(apt_lat))
    base_lon = int(math.floor(apt_lon))
    # If the natural tile's airport-OSM cache is missing, download it.
    # In a full Ortho4XP run the driver has normally prefetched it
    # already; this fallback keeps build_airport_pavement
    # self-sufficient when called outside the full run (e.g. for
    # standalone testing of new airports whose OSM tile hasn't been
    # pre-cached).
    if not ensure_airports_osm_tile_cached(base_lat, base_lon):
        UI.vprint(1,
            f"  [pav-builder] WARN: Overpass download failed "
            f"for airports tile +{base_lat}{base_lon:+04d}; "
            f"junctions/rects will be empty.")
    # Per user 2026-04-29: OSM Overpass exports use locally-
    # generated NEGATIVE IDs that aren't globally unique.  At
    # HECA (and any airport with adjacent OSM tiles), tile A's
    # node ``-1`` and tile B's node ``-1`` typically refer to
    # entirely different geographic coordinates.  The previous
    # ``nodes.update(n2)`` merge across the 9-tile grid silently
    # overwrites tile A's coordinates with tile B's whenever
    # there's an ID collision — leaving every way that
    # references the colliding ID with the WRONG coordinates.
    #
    # At HECA: 2762 node IDs collide between +30+030 and +30+031
    # (every node ID in +30+030 also appears in +30+031, with
    # different coordinates).  The post-merge HECA centerlines
    # spanned 154 km and the 14 explicit ``aeroway=terminal``
    # ways all had their centroids dragged outside the airport
    # bbox by the overwritten coordinates.
    #
    # Fix: namespace each tile's node IDs by prefixing with the
    # tile coordinate.  Way node-id references are rewritten to
    # use the same prefix at load time, so each way only ever
    # resolves to its own tile's nodes.  After this no ID
    # collision is possible — and the previous "centroid in
    # bbox" filter alone is sufficient (no need for the cross-
    # tile-span guard since corrupted ways no longer exist).
    nodes: dict[str, tuple[float, float]] = {}
    ways: list[tuple[str, list[str], dict[str, str]]] = []
    relations: list[tuple[str, list[str], dict[str, str]]] = []
    seen_paths = set()
    for dlat in (0, -1, 1):
        for dlon in (0, -1, 1):
            tile_lat_n = base_lat + dlat
            tile_lon_n = base_lon + dlon
            osm_path = _tile_path(tile_lat_n, tile_lon_n)
            if osm_path in seen_paths or not os.path.isfile(osm_path):
                continue
            seen_paths.add(osm_path)
            n2, w2, r2, _nt2 = _load_osm_tile(osm_path)
            # Namespace this tile's node IDs.
            tile_prefix = f"t{tile_lat_n:+03d}{tile_lon_n:+04d}:"
            for nid, coord in n2.items():
                nodes[tile_prefix + nid] = coord
            for wid, nds, tags in w2:
                ways.append(
                    (tile_prefix + wid,
                     [tile_prefix + n for n in nds],
                     tags))
            for rid, outer_ids, tags in r2:
                relations.append(
                    (tile_prefix + rid,
                     [tile_prefix + w for w in outer_ids],
                     tags))
    if not nodes:
        return {}, [], []

    # Filter ways: keep only those whose node centroid lies
    # within ``radius_deg`` of the airport AND whose own bbox
    # spans no more than ``MAX_WAY_SPAN_DEG``.  With per-tile
    # node namespacing above, ID collisions can no longer
    # pollute a way's resolved coordinates — but the span check
    # is cheap and provides a defensive guard against any other
    # data quality issues (e.g. cross-tile ways that genuinely
    # span more than an airport's worth of geography).
    MAX_WAY_SPAN_DEG = 0.1  # ~11 km; airport ways are at most a few km.

    def _in_box(lat, lon):
        return (abs(lat - apt_lat) <= radius_deg and
                abs(lon - apt_lon) <= radius_deg)

    def _way_passes_filters(nds):
        pts = [nodes[n] for n in nds if n in nodes]
        if not pts:
            return False
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        clat = sum(lats) / len(pts)
        clon = sum(lons) / len(pts)
        if not _in_box(clat, clon):
            return False
        if (max(lats) - min(lats) > MAX_WAY_SPAN_DEG
                or max(lons) - min(lons) > MAX_WAY_SPAN_DEG):
            return False
        return True

    kept_ways = []
    way_by_id: dict[str, tuple[str, list[str], dict[str, str]]] = {}
    for wid, nds, tags in ways:
        way_by_id[wid] = (wid, nds, tags)
        if _way_passes_filters(nds):
            kept_ways.append((wid, nds, tags))
    # Relations: keep if ANY member way passes the filters.
    kept_rels = []
    for rid, outer_ids, tags in relations:
        for wid in outer_ids:
            if wid not in way_by_id:
                continue
            _, nds, _ = way_by_id[wid]
            if _way_passes_filters(nds):
                kept_rels.append((rid, outer_ids, tags))
                break
    return nodes, kept_ways, kept_rels


def _score_apt_dat_against_osm(
        apt_path: str,
        icao: str,
        nodes: dict[str, tuple[float, float]],
        ways: list[tuple[str, list[str], dict[str, str]]],
        taxi_buffer_m: float = 5.0,
        ) -> tuple[float, float]:
    """Score how well ``apt_path`` covers OSM-known features at
    this airport.

    Returns ``(apron_coverage, taxi_coverage)`` where:

      * ``apron_coverage`` = (area of OSM ``aeroway=apron`` polygons
        that lies inside the apt.dat row-110 pavement union) /
        (total area of OSM apron polygons).  1.0 = perfect, 0.0 =
        no apt.dat coverage of OSM-known apron areas.

      * ``taxi_coverage`` = (length of OSM ``aeroway=taxiway``
        centerline LineStrings within ``taxi_buffer_m`` of any
        apt.dat pavement) / (total length of OSM taxi
        centerlines).  Buffer matches typical taxiway half-width.
        1.0 = every OSM-known taxiway centerline has apt.dat
        pavement underneath it.

    Returns (1.0, 1.0) if no OSM apron / taxi data exists (the
    apt.dat passes by default).  Returns (0.0, 0.0) if the apt.dat
    can't be loaded.

    Per user 2026-04-30: when a custom-scenery apt.dat scores
    below 0.7 on either metric, it's "missing a lot vs OSM" and
    we fall back to the global apt.dat instead.
    """
    try:
        apt = APR.load_airport(apt_path, icao)
    except _GEOM_EXC:
        return (0.0, 0.0)
    if apt is None:
        return (0.0, 0.0)
    if not apt.pavements and not apt.runways:
        return (0.0, 0.0)
    # Anchor + projection (use first runway threshold).
    if not apt.runways:
        return (1.0, 1.0)
    r0 = apt.runways[0]
    lat0, lon0 = r0.lat_a, r0.lon_a
    cos0 = math.cos(math.radians(lat0))
    R = R_EARTH

    def to_m(lon: float, lat: float) -> tuple[float, float]:
        return (math.radians(lon - lon0) * R * cos0,
                math.radians(lat - lat0) * R)
    # Build apt.dat pavement union in meter space.  apt.dat
    # polygons are stored in lat/lon — project to meters for
    # consistent area / distance math.
    from shapely.ops import transform as shp_transform
    pav_polys_m: list[Polygon] = []
    for pav in apt.pavements:
        if pav.polygon is None or pav.polygon.is_empty:
            continue
        try:
            pm = shp_transform(
                lambda lon, lat, z=None:
                    to_m(lon, lat) if z is None
                    else (*to_m(lon, lat), z),
                pav.polygon)
            if pm.is_empty:
                continue
            if not pm.is_valid:
                pm = pm.buffer(0)
            if pm.geom_type == "Polygon" and not pm.is_empty:
                pav_polys_m.append(pm)
            elif pm.geom_type == "MultiPolygon":
                for g in pm.geoms:
                    if (g.geom_type == "Polygon"
                            and not g.is_empty):
                        pav_polys_m.append(g)
        except _GEOM_EXC:
            continue
    # Also include runway rects so a taxi centerline that ends on
    # the runway counts as covered.
    for rwy in apt.runways:
        try:
            rect = _runway_rect_m(rwy, to_m)
            if rect is not None and not rect.is_empty:
                pav_polys_m.append(rect)
        except _GEOM_EXC:
            continue
    if not pav_polys_m:
        return (0.0, 0.0)
    try:
        pav_union = unary_union(pav_polys_m)
    except _GEOM_EXC:
        return (0.0, 0.0)
    if pav_union.is_empty:
        return (0.0, 0.0)
    pav_buf = pav_union.buffer(taxi_buffer_m)
    # Apron coverage: OSM apron polygons (closed ways tagged
    # aeroway=apron) → fraction inside pav_union.
    apron_total = 0.0
    apron_inside = 0.0
    taxi_total = 0.0
    taxi_inside = 0.0
    for wid, nrefs, tags in ways:
        ay = tags.get("aeroway", "")
        if ay == "apron":
            pts = []
            for n in nrefs:
                if n in nodes:
                    la, lo = nodes[n]
                    pts.append(to_m(lo, la))
            if (len(pts) >= 4
                    and abs(pts[0][0] - pts[-1][0]) < 0.5
                    and abs(pts[0][1] - pts[-1][1]) < 0.5):
                try:
                    poly = Polygon(pts)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if (poly.is_empty
                            or poly.geom_type != "Polygon"):
                        continue
                    apron_total += poly.area
                    inter = poly.intersection(pav_union)
                    if not inter.is_empty:
                        apron_inside += inter.area
                except _GEOM_EXC:
                    continue
        elif ay == "taxiway":
            # Open ways (centerlines).  Closed taxi polygons are
            # rare in OSM; treat as line either way.
            pts = []
            for n in nrefs:
                if n in nodes:
                    la, lo = nodes[n]
                    pts.append(to_m(lo, la))
            if len(pts) < 2:
                continue
            try:
                from shapely.geometry import LineString as _LS
                ls = _LS(pts)
                if ls.is_empty or ls.length < 1.0:
                    continue
                taxi_total += ls.length
                inter = ls.intersection(pav_buf)
                if not inter.is_empty:
                    if hasattr(inter, "length"):
                        taxi_inside += inter.length
                    elif hasattr(inter, "geoms"):
                        for g in inter.geoms:
                            if hasattr(g, "length"):
                                taxi_inside += g.length
            except _GEOM_EXC:
                continue
    apron_cov = (apron_inside / apron_total
                  if apron_total > 0 else 1.0)
    taxi_cov = (taxi_inside / taxi_total
                 if taxi_total > 0 else 1.0)
    return (apron_cov, taxi_cov)


def _pick_best_apt_dat_against_osm(
        xplane_root: str,
        icao: str,
        apron_threshold: float = 0.7,
        taxi_threshold: float = 0.7,
        ) -> str | None:
    """Select the apt.dat for ``icao``.

    TEMPORARY policy (user 2026-05-21): always use a Custom Scenery
    pack that contains the airport if one is present; only fall back
    to Global Airports (then default scenery) when NO Custom Scenery
    pack has it.  No pavement / OSM coverage analysis is performed.

    This replaces the earlier coverage-scoring selector (preserved in
    git history) that scored every candidate's apron + taxi coverage
    against OSM and skipped a custom pack whose coverage fell below
    ``apron_threshold`` / ``taxi_threshold``.  That surprised users
    whose hand-built scenery was silently ignored in favour of the
    Global definition (e.g. KPHX, whose custom pack scored 0 % apron
    against OSM and was skipped).  The ``*_threshold`` parameters are
    retained for signature compatibility but are now unused.

    ``find_all_airport_apt_dats`` returns header matches in priority
    order — Custom Scenery packs first, then Global Airports, then
    default scenery — using a header-only check (no pavement scan).
    """
    candidates = APR.find_all_airport_apt_dats(xplane_root, icao)
    if not candidates:
        return APR.find_airport_apt_dat(xplane_root, icao)

    def _is_global_or_default(c: str) -> bool:
        # The Global Airports pack lives under Custom Scenery on
        # X-Plane 11, so identify it (and the default-scenery pack) by
        # path rather than by directory position.
        return "Global Airports" in c or "default scenery" in c

    custom = [c for c in candidates if not _is_global_or_default(c)]

    # Prefer the first genuine Custom Scenery pack that can actually
    # drive the taxi build — i.e. one whose apt.dat carries a 1201/1202
    # taxi-routing network.  Some packs (MKStudios LPPT) draw the
    # airport as draped pavement polygons + painted lines but ship NO
    # routing graph; picking such a pack emits a taxi-less,
    # boundary-only patch.  User 2026-06-16: fall back to a candidate
    # (Global) that does route rather than honour the custom pack
    # blindly.  Custom packs that DO route are unchanged.
    for cand in custom:
        if APR._file_has_airport_with_taxi_routing(cand, icao):
            UI.vprint(1,
                f"  [pav-builder] {icao}: using Custom Scenery "
                f"apt.dat (no pavement analysis): {cand}")
            return cand
    # No Custom Scenery pack has a taxi network.  Fall back to the
    # first remaining candidate (Global, then default) that does.
    if custom:
        for cand in candidates:
            if (_is_global_or_default(cand)
                    and APR._file_has_airport_with_taxi_routing(cand, icao)):
                UI.vprint(1,
                    f"  [pav-builder] {icao}: Custom Scenery pack has no "
                    f"taxi-routing network; falling back to {cand}")
                return cand
    # Nothing routes anywhere — preserve the prior policy (first custom
    # pack, else first candidate) so runways/boundary still emit.
    if custom:
        UI.vprint(1,
            f"  [pav-builder] {icao}: using Custom Scenery "
            f"apt.dat (no pavement analysis): {custom[0]}")
        return custom[0]
    UI.vprint(1,
        f"  [pav-builder] {icao}: no Custom Scenery pack; using "
        f"{candidates[0]}")
    return candidates[0]


def _load_osm_big_roads(apt_lat: float, apt_lon: float,
                        radius_deg: float = 0.05
                        ) -> tuple[dict[str, tuple[float, float]],
                                   list[tuple[str, list[str], dict[str, str]]]]:
    """Load the ``big_roads`` OSM cache (motorway / trunk / primary /
    secondary / railway ways with ``tunnel`` and ``bridge`` tag
    annotations).  Same multi-tile namespace + bbox-filter logic as
    ``_load_osm_airports``.

    Returns ``(nodes, ways)``.  Relations are not used by the road
    pipeline.  Returns empty containers when no cache exists at
    this tile (tile builds without road data — e.g. SPLP, where
    big_roads.osm.bz2 was never generated — silently skip tunnel
    emission).  Callers that also need the node tags use
    ``_load_osm_road_layer`` directly.
    """
    return _load_osm_road_layer(
        "big_roads", apt_lat, apt_lon, radius_deg)[:2]


def _load_osm_small_roads(apt_lat: float, apt_lon: float,
                          radius_deg: float = 0.05
                          ) -> tuple[dict[str, tuple[float, float]],
                                     list[tuple[str, list[str], dict[str, str]]]]:
    """Load the ``small_roads`` OSM cache (minor drivable highways:
    service / residential / unclassified / track / tertiary / …).

    Used by the ground-vehicle ``service_road`` grading (session 47):
    small roads inside (or just outside) the airport boundary are graded
    with car logic (≤ 4 %).  Same multi-tile + bbox logic as the big-road
    loader; returns empty containers when no cache exists for the tile.
    """
    return _load_osm_road_layer(
        "small_roads", apt_lat, apt_lon, radius_deg)[:2]


@functools.lru_cache(maxsize=16)
def _load_osm_road_layer(layer: str, apt_lat: float, apt_lon: float,
                         radius_deg: float = 0.05
                         ) -> tuple[dict[str, tuple[float, float]],
                                    list[tuple[str, list[str], dict[str, str]]],
                                    dict[str, dict[str, str]]]:
    """Shared loader for a road OSM cache ``layer`` (``big_roads`` /
    ``small_roads``): merge the 3×3 tile neighbourhood, namespace node /
    way IDs per tile, and keep ways whose centroid OR any vertex lies
    within ``radius_deg`` of the airport.

    Returns ``(nodes, ways, node_tags)``; ``node_tags`` holds the tag
    dicts of the (few) nodes whose tags the download whitelist retained
    (level-crossing evidence: ``aeroway=aircraft_crossing``,
    ``barrier`` gates) — empty for caches written before the tag-schema
    bump.

    Cached (``lru_cache``): a process that builds the same airport
    repeatedly (the test suite builds CYXY/HECA/… many times) parses each
    tile's road bz2 only once.  Callers must treat the returned nodes/ways
    as READ-ONLY (they are shared across calls)."""
    base_lat = int(math.floor(apt_lat))
    base_lon = int(math.floor(apt_lon))
    nodes: dict[str, tuple[float, float]] = {}
    ways: list[tuple[str, list[str], dict[str, str]]] = []
    node_tags: dict[str, dict[str, str]] = {}
    seen_paths = set()
    for dlat in (0, -1, 1):
        for dlon in (0, -1, 1):
            tile_lat_n = base_lat + dlat
            tile_lon_n = base_lon + dlon
            osm_path = FNAMES.osm_cached(
                tile_lat_n, tile_lon_n, layer)
            if osm_path in seen_paths or not os.path.isfile(osm_path):
                continue
            seen_paths.add(osm_path)
            n2, w2, _r2, nt2 = _load_osm_tile(osm_path)
            tile_prefix = (
                f"r{tile_lat_n:+03d}{tile_lon_n:+04d}:")
            for nid, coord in n2.items():
                nodes[tile_prefix + nid] = coord
            for nid, tags in nt2.items():
                node_tags[tile_prefix + nid] = tags
            for wid, nds, tags in w2:
                ways.append(
                    (tile_prefix + wid,
                     [tile_prefix + n for n in nds],
                     tags))
    if not nodes:
        return {}, [], {}

    def _in_box(lat, lon):
        return (abs(lat - apt_lat) <= radius_deg
                and abs(lon - apt_lon) <= radius_deg)

    kept = []
    for wid, nds, tags in ways:
        pts = [nodes[n] for n in nds if n in nodes]
        if not pts:
            continue
        clat = sum(p[0] for p in pts) / len(pts)
        clon = sum(p[1] for p in pts) / len(pts)
        # A road may cross the airport bbox without its centroid
        # landing inside — keep the way if EITHER (centroid in box)
        # OR (any vertex within ``radius_deg``).
        if _in_box(clat, clon):
            kept.append((wid, nds, tags))
            continue
        for lat, lon in pts:
            if _in_box(lat, lon):
                kept.append((wid, nds, tags))
                break
    return nodes, kept, node_tags


# ═════════════════════════════════════════════════════════════════════
# AIRPORT-REGION ROAD FEED (2026-07-26)
# ═════════════════════════════════════════════════════════════════════
#
# THE HOLE IT CLOSES.  ``_load_osm_small_roads`` above reads the TILE-WIDE
# ``<tile>_small_roads.osm.bz2`` cache.  That file is written by the vector
# step only at ``road_level >= 2`` (``O4_Vector_Map.py``, ``build_roads``)
# and the shipped default is 1 (``O4_Cfg_Vars.py`` ``road_level``), so at
# default config it exists NOWHERE — verified 2026-07-26 across the whole
# production data root: not one ``*_small_roads.osm.bz2`` in any tile.
# ``_load_osm_road_layer`` skips a missing file silently, so every airport
# built at default config saw ZERO minor-road evidence while the code read
# as though it had some (the service-road builder's comment expects
# "HECA: ~9k small roads" and got 0).  Even a user who raises the level to
# 2 gets only ``highway=tertiary``; ``service`` needs 4 and ``track`` 5.
#
# THE SOURCE.  The regional-extract accelerator already keeps a CLIPPED
# pbf of this area on disk (``OSM_data/_regional_extracts/clips/
# clip_+0LL+0LLL_<digest>-part<N>.osm.pbf``), cut by the same tile build.
# Filtering ``way["highway"]`` + ``way["railway"]`` out of it for the
# AIRPORT REGION ONLY yields the full drivable + rail network at the
# field — 6,066 ways in a 0.072° box at HECA where the tile cache path
# yields 0.
#
# SCOPE — FOUNDATION ONLY.  This module publishes ONE shared dataset on
# the layout (``layout.airport_road_network``) plus one shared corridor
# union (``clearance.airport_road_feed_corridors``).  It REWIRES NOTHING:
# clearance keeps reading the tile caches through
# ``bridges._load_tunnel_road_network`` and the service-road builder keeps
# reading ``_load_osm_small_roads``, so the emitted patch is byte-identical
# with the gate ON or OFF at every airport.  Wiring the feed into those
# consumers would widen corridors at EVERY airport (they see 0 small roads
# today), which is a behaviour change for the owner features to make
# deliberately, not a side effect of the loader landing.

# Bump when the shape of the cached feed changes (fields, tag whitelist,
# statements): older sidecars stop matching and are recomputed once.
AIRPORT_ROAD_FEED_CACHE_VERSION = 1

# Overpass-style statements handed to the extract filter.  ``highway``
# key-existence (NOT the per-type lists the tile queries use) is the whole
# point — ``service`` / ``track`` / ``residential`` are exactly the classes
# the tile cache never had; consumers narrow by tag afterwards.
_ROAD_FEED_STATEMENTS = ('way["highway"]', 'way["railway"]')

# Way / node tag whitelists, deliberately a SUPERSET of the road caches'
# (``O4_Vector_Map.ROADS_TAGS_OF_INTEREST`` / ``ROAD_NODE_TAGS_OF_INTEREST``)
# so a feed way carries everything a tile-cache way would, plus the class
# tags themselves and the name/access tags classification will want.
_ROAD_FEED_WAY_TAGS = (
    "highway", "railway", "bridge", "tunnel", "width", "lanes",
    "name", "ref", "service", "access", "oneway", "surface", "layer",
)
_ROAD_FEED_NODE_TAGS = ("aeroway", "crossing:aircraft", "barrier", "railway")

# Sidecar directory, next to the extracts the feed is cut from.
_ROAD_FEED_DIR_NAME = "_airport_road_feed"

# Query boxes are rounded OUTWARD to this grid so a millimetre of drift in
# the airport footprint (a re-picked apt.dat, a DSF pavement change) does
# not invalidate the sidecar or re-cut anything.  0.001° ≈ 111 m.
_ROAD_FEED_BOX_QUANTUM_DEG = 0.001

# Fallback half-span (m) for the query box when a layout carries no
# boundary, no pavement and no runways (a degenerate apt.dat).
_ROAD_FEED_FALLBACK_HALF_SPAN_M = 3000.0


class AirportRoadNetwork:
    """The shared road/rail dataset for one airport region.

    ONE dataset, several consumers: classification refinement, inset-area
    road grading, and (should the owner choose to rewire it) the corridor
    union.  Everything a consumer needs to go from a way to a corridor is
    here, so nobody re-derives widths or re-parses OSM.

    Attributes
    ----------
    icao, bbox
        The airport and the WGS84 query box ``(lat_min, lon_min, lat_max,
        lon_max)`` the ways were selected for.
    nodes
        ``{node id: (lat, lon)}`` — auto_patch's (lat, lon) order, same as
        every other loader in this module.
    ways
        ``[(way id, [node id, ...], {tag: value})]``, document order.
    node_tags
        ``{node id: {tag: value}}`` for the nodes whose tags the whitelist
        retained (level-crossing / barrier evidence).
    widths
        ``{way id: carriageway width in metres}``, resolved ONCE through
        ``bridges._carriageway_width_from_tags`` (way ``width=`` →
        ``lanes=`` → per-type table) so every consumer buffers the same
        road to the same width.
    source
        ``"regional_extract"``, ``"tile_cache"`` or ``"none"``.
    road_way_count, rail_way_count
        Ways carrying ``highway`` / ``railway`` respectively.
    load_seconds
        Wall time of the load that produced this object (0.0 on a sidecar
        hit is normal — the hit path records its own, much smaller, time).

    IDs are opaque strings and are namespaced differently per source (the
    extract path uses the OSM layer's synthetic ids, the tile-cache path
    the established ``r+30+031:`` / ``S|`` prefixes).  Never compare an id
    across two networks.  Treat the containers as READ-ONLY: a sidecar hit
    and an in-process reuse return the same objects.
    """

    __slots__ = ("icao", "bbox", "nodes", "ways", "node_tags", "widths",
                 "source", "road_way_count", "rail_way_count",
                 "load_seconds")

    def __init__(self, icao, bbox, nodes, ways, node_tags, widths,
                 source, load_seconds=0.0):
        self.icao = icao
        self.bbox = bbox
        self.nodes = nodes
        self.ways = ways
        self.node_tags = node_tags
        self.widths = widths
        self.source = source
        self.road_way_count = sum(1 for _w in ways if _w[2].get("highway"))
        self.rail_way_count = sum(1 for _w in ways if _w[2].get("railway"))
        self.load_seconds = load_seconds

    def __getstate__(self):
        return {name: getattr(self, name) for name in self.__slots__}

    def __setstate__(self, state):
        for name, value in state.items():
            setattr(self, name, value)

    def __repr__(self):
        return ("AirportRoadNetwork(%s, source=%s, roads=%d, rails=%d)"
                % (self.icao, self.source, self.road_way_count,
                   self.rail_way_count))


def _round_box_outward(box: tuple[float, float, float, float]
                       ) -> tuple[float, float, float, float]:
    """Snap a ``(lat_min, lon_min, lat_max, lon_max)`` box outward onto the
    :data:`_ROAD_FEED_BOX_QUANTUM_DEG` grid (cache stability, see there)."""
    q = _ROAD_FEED_BOX_QUANTUM_DEG
    return (math.floor(box[0] / q) * q, math.floor(box[1] / q) * q,
            math.ceil(box[2] / q) * q, math.ceil(box[3] / q) * q)


def _airport_road_feed_box(layout, pad_m: float
                           ) -> tuple[float, float, float, float]:
    """WGS84 query box for the airport region: the row-130 boundary ∪ the
    source pavement union ∪ the runway union, padded by ``pad_m`` and
    rounded outward.

    Meter-space geometry converted through ``layout.m_to_ll`` — the same
    projection every shape in the layout lives in.  A layout with none of
    the three (degenerate apt.dat) falls back to a
    :data:`_ROAD_FEED_FALLBACK_HALF_SPAN_M` square around the anchor, so
    the feed still covers the field rather than returning nothing."""
    bounds = []
    for geometry_object in (getattr(layout, "airport_boundary", None),
                            getattr(layout, "source_pavement_union", None),
                            getattr(layout, "runway_union", None)):
        if geometry_object is None:
            continue
        try:
            if geometry_object.is_empty:
                continue
            bounds.append(geometry_object.bounds)
        except _GEOM_EXC:
            continue
    if bounds:
        min_x = min(b[0] for b in bounds) - pad_m
        min_y = min(b[1] for b in bounds) - pad_m
        max_x = max(b[2] for b in bounds) + pad_m
        max_y = max(b[3] for b in bounds) + pad_m
    else:
        span = _ROAD_FEED_FALLBACK_HALF_SPAN_M + pad_m
        min_x = min_y = -span
        max_x = max_y = span
    lat_min, lon_min = layout.m_to_ll(min_x, min_y)
    lat_max, lon_max = layout.m_to_ll(max_x, max_y)
    return _round_box_outward((lat_min, lon_min, lat_max, lon_max))


def _regional_clip_parts_for_box(box) -> list[str] | None:
    """Part paths of an ALREADY-CUT regional-extract clip covering ``box``,
    or ``None``.

    Strictly read-only, and that is the design: it reuses
    ``O4_OSM_Extracts``' own key (``covering_regions`` →
    ``_clip_bounding_box`` → ``_clip_path`` → ``_read_clip_parts``) but
    never calls ``_clip_for_query``, which would CUT a clip, nor
    ``osm_xml_from_local_extracts``, which would DOWNLOAD a country
    extract.  An auto-patch build must never turn into a multi-minute cut
    or a network fetch on the strength of an evidence feed — an absent
    clip simply means the loud no-road-data line.

    TWO lookups, because the exact key alone is too strict.  The clip
    cache is keyed on the EXACT padded box its cutter was called with, and
    that box is the integer-degree hull of ALL the query boxes of that one
    call — the airport-inset footprint prefetch batches a tile's airports
    and can span two degrees of longitude, so the clip on disk for Peru
    was cut for ``(-13.05,-78.05,-11.95,-75.95)`` while an airport-sized
    box hashes to ``(-13.05,-78.05,-11.95,-76.95)`` and missed a clip that
    covers it completely (observed 2026-07-26: SPJC got NO ROAD DATA while
    SPLP, 20 km away, was served).

    So: exact key first, then the same-area fallback.  A clip's file name
    prefix encodes the FLOOR CORNER of its box, and every clip box is
    ``(floor(lat_min)-pad, floor(lon_min)-pad, ceil(lat_max)+pad,
    ceil(lon_max)+pad)`` — so a clip whose prefix matches this box's floor
    corner provably covers at least that corner's 1°×1° square GROWN BY
    THE PAD on every side.  (The pad matters: SPJC's 3.4 km north-south
    runway pushes its query box 0.007° past the −12° parallel, and the
    bare square would refuse a clip that covers it comfortably.)  A box
    reaching further than the pad into the next degree gets no fallback —
    only the exact key can serve it.

    ACCEPTED RISK: the "≥ one degree" step assumes the cutter's own hull
    was not degenerate (``lat_min == lat_max`` exactly on an integer),
    which no tile or airport query box is.  Were that ever to happen the
    feed would read a smaller clip and report fewer ways — evidence
    thinner than it could be, never a wrong patch.

    ``_prune_stale_clips`` keeps at most one clip per prefix; if several
    survive, the freshest wins and the sidecar fingerprint records which
    files were actually read.
    """
    try:
        import O4_OSM_Extracts as EXTRACTS
        if not EXTRACTS.extracts_enabled():
            return None
        regions = EXTRACTS.covering_regions(box)
        if not regions:
            return None
        clip_box = EXTRACTS._clip_bounding_box([box])
        parts = EXTRACTS._read_clip_parts(
            EXTRACTS._clip_path(regions, clip_box))
        if parts:
            return parts
        return _same_area_clip_parts(box)
    except Exception:
        return None


def _same_area_clip_parts(box) -> list[str] | None:
    """Fallback clip lookup: any cached clip whose floor corner opens the
    padded 1°×1° square that fully contains ``box``.  See
    :func:`_regional_clip_parts_for_box` for why this is sound."""
    import O4_OSM_Extracts as EXTRACTS
    lat_min, lon_min, lat_max, lon_max = box
    lat_floor = math.floor(lat_min)
    lon_floor = math.floor(lon_min)
    pad = EXTRACTS._CLIP_PAD_DEGREES
    if not (lat_min >= lat_floor - pad and lon_min >= lon_floor - pad
            and lat_max <= lat_floor + 1.0 + pad
            and lon_max <= lon_floor + 1.0 + pad):
        return None  # reaches past the guaranteed extent — refuse
    prefix = "clip_%+04d%+05d_" % (lat_floor, lon_floor)
    directory = EXTRACTS._clip_directory()
    try:
        names = [name for name in os.listdir(directory)
                 if name.startswith(prefix) and name.endswith(".parts.json")]
    except OSError:
        return None
    candidates = []
    for name in names:
        path = os.path.join(directory, name)
        try:
            candidates.append((-os.path.getmtime(path), name, path))
        except OSError:
            continue
    for _mtime, _name, path in sorted(candidates):
        parts = EXTRACTS._read_clip_parts(path[:-len(".parts.json")])
        if parts:
            return parts
    return None


def _road_feed_sidecar(icao: str, box, clip_parts) -> tuple[str | None,
                                                            str | None]:
    """``(sidecar path, fingerprint)`` for one airport's feed, or
    ``(None, None)`` with the cache gate off.

    Same shape as ``dsf_reader._object_footprint_sidecar``: the fingerprint
    covers every input the cached result is a pure function of — the clip
    part files (basename, size, mtime: a re-downloaded extract re-cuts the
    clip, which changes them), the rounded query box, the statement and tag
    whitelists, and the schema version.  The sidecar lives under
    ``OSM_data/_airport_road_feed/`` next to the extracts it is cut from,
    never inside a scenery pack (user ruling 2026-07-15)."""
    from .config import AIRPORT_ROAD_FEED_CACHE
    if not AIRPORT_ROAD_FEED_CACHE:
        return None, None
    import hashlib
    digest = hashlib.sha1()
    digest.update(("v%d;" % AIRPORT_ROAD_FEED_CACHE_VERSION).encode())
    digest.update(("%.6f,%.6f,%.6f,%.6f;" % tuple(box)).encode())
    digest.update((";".join(_ROAD_FEED_STATEMENTS)).encode())
    digest.update((";".join(_ROAD_FEED_WAY_TAGS)).encode())
    digest.update((";".join(_ROAD_FEED_NODE_TAGS)).encode())
    # The drivable / rail-track cut is applied to the CACHED ways, so a
    # change to either set must invalidate every sidecar.
    from .config import (OSM_NON_DRIVABLE_HIGHWAY_TYPES,
                         OSM_RAIL_TRACK_TYPES)
    digest.update((";".join(sorted(OSM_NON_DRIVABLE_HIGHWAY_TYPES))).encode())
    digest.update((";".join(sorted(OSM_RAIL_TRACK_TYPES))).encode())
    try:
        for part in sorted(clip_parts):
            stat = os.stat(part)
            digest.update(("%s|%d|%d;" % (
                os.path.basename(part), stat.st_size,
                int(stat.st_mtime))).encode())
    except OSError:
        return None, None
    directory = os.path.join(FNAMES.OSM_dir, _ROAD_FEED_DIR_NAME)
    safe_icao = "".join(c for c in str(icao) if c.isalnum()) or "APT"
    return (os.path.join(directory, "%s_road_feed.cache" % safe_icao),
            digest.hexdigest())


def _read_road_feed_sidecar(sidecar_path, fingerprint):
    """The cached feed on a fingerprint match, else ``None`` (missing,
    stale or unreadable — the caller recomputes).  Mirrors
    ``dsf_reader._read_footprint_sidecar``."""
    if not (sidecar_path and fingerprint and os.path.isfile(sidecar_path)):
        return None
    import pickle
    try:
        with open(sidecar_path, "rb") as sidecar_file:
            payload = pickle.load(sidecar_file)
        if payload.get("fingerprint") == fingerprint:
            return payload["network"]
        UI.vprint(
            1, "   [road-feed] sidecar STALE (extract clip or query box "
               "changed since it was written) - re-extracting")
    except Exception:
        pass
    return None


def _write_road_feed_sidecar(sidecar_path, fingerprint, network) -> None:
    """Persist a feed for the next build.  A write failure must never break
    a build (read-only volume, out of space) — swallowed, next run
    recomputes."""
    if not (sidecar_path and fingerprint):
        return
    import pickle
    try:
        os.makedirs(os.path.dirname(sidecar_path), exist_ok=True)
        temporary_path = "%s.tmp-%d" % (sidecar_path, os.getpid())
        with open(temporary_path, "wb") as sidecar_file:
            pickle.dump({"fingerprint": fingerprint, "network": network},
                        sidecar_file)
        os.replace(temporary_path, sidecar_path)
    except Exception:
        pass


def _extract_region_roads(clip_parts, box):
    """``(nodes, ways, node_tags)`` for ``box`` filtered out of the clip.

    Two-stage on purpose.  ``osmium extract`` (the bundled C++ binary the
    clip cutter already uses) cuts the airport box out of the area clip
    first, and the pyosmium filter then reads that few-hundred-kB file
    instead of the whole clip: measured on HECA's 65 MB clip, 0.43 s cut +
    0.71 s filter = 1.1 s versus 11.7 s filtering the clip directly, for a
    BYTE-IDENTICAL result (``cut_clip_with_osmium`` guarantees that
    contract — filtering the cut with any statements and any bbox inside
    the cut box equals filtering the source).  With no osmium binary the
    clip is filtered directly — correct, just slower.

    The filtered XML goes through ``OSM_layer.update_dicosm`` and
    :func:`_osm_layer_to_tuples`, so the structures are indistinguishable
    from a tile cache's."""
    import tempfile
    import O4_OSM_Extract_Filter as FILTER
    import O4_OSM_Extracts as EXTRACTS
    import O4_OSM_Utils as OSM

    sources = list(clip_parts)
    temporary_directory = None
    try:
        binary = EXTRACTS._osmium_binary()
        if binary:
            temporary_directory = tempfile.mkdtemp(prefix="o4_road_feed_")
            cut_parts = [
                os.path.join(temporary_directory, "part%d.osm.pbf" % index)
                for index in range(len(sources))]
            try:
                FILTER.cut_clip_parts_with_osmium(
                    sources, box, cut_parts, binary,
                    should_stop=lambda: UI.red_flag,
                    spawn_kwargs=UI.external_tool_keyword_arguments(),
                )
                sources = cut_parts
            except Exception as error:
                if UI.red_flag:
                    raise
                UI.vprint(
                    1, "   [road-feed] osmium-tool cut failed (%s); "
                       "filtering the area clip directly." % error)
        xml_bytes = FILTER.filter_extracts_to_osm_xml(
            sources, _ROAD_FEED_STATEMENTS, box)
    finally:
        if temporary_directory is not None:
            import shutil
            shutil.rmtree(temporary_directory, ignore_errors=True)
    if not xml_bytes:
        return {}, [], {}
    tags = {
        "n": [(key, "") for key in _ROAD_FEED_NODE_TAGS],
        "w": [(key, "") for key in _ROAD_FEED_WAY_TAGS],
        "r": [],
    }
    layer = OSM.OSM_layer()
    if not layer.update_dicosm(xml_bytes, tags, tags):
        return {}, [], {}
    nodes, ways, _relations, node_tags = _osm_layer_to_tuples(layer)
    drivable = [way for way in ways if _is_drivable_or_rail(way[2])]
    return nodes, drivable, node_tags


def _is_drivable_or_rail(tags: dict) -> bool:
    """Is this way a drivable road or a rail TRACK?

    The extract statements select on the ``highway`` / ``railway`` KEY —
    that is what finds the ``service`` / ``track`` / ``residential``
    classes the tile caches never held — so the "drivable" cut is made
    here, against the config sets (pedestrian ways and yard furniture
    out).  See ``config.OSM_NON_DRIVABLE_HIGHWAY_TYPES`` /
    ``OSM_RAIL_TRACK_TYPES``."""
    from .config import (OSM_NON_DRIVABLE_HIGHWAY_TYPES,
                         OSM_RAIL_TRACK_TYPES)
    highway_type = tags.get("highway")
    if highway_type is not None:
        return highway_type not in OSM_NON_DRIVABLE_HIGHWAY_TYPES
    return tags.get("railway") in OSM_RAIL_TRACK_TYPES


def _road_feed_from_tile_caches(apt_lat: float, apt_lon: float, box):
    """``(nodes, ways, node_tags)`` from the TILE road caches — the
    big-roads layer plus the ``S|``-namespaced small-roads layer.

    Same merge scheme (and the same warning) as
    ``bridges._load_tunnel_road_network``: the two caches use SYNTHETIC
    per-layer negative ids, so ``r-13-078:-202`` means different features
    in each and a raw dict merge silently displaces ways by kilometres.
    Kept here rather than reused from ``bridges`` because that helper takes
    a layout and this one must also run for a bare coordinate (tests)."""
    nodes, ways, node_tags = _load_osm_road_layer(
        "big_roads", apt_lat, apt_lon)
    nodes_small, ways_small, node_tags_small = _load_osm_road_layer(
        "small_roads", apt_lat, apt_lon)
    merged_nodes = dict(nodes)
    merged_node_tags = dict(node_tags)
    merged_ways = list(ways)
    if nodes_small:
        for node_id, coordinate in nodes_small.items():
            merged_nodes["S|" + node_id] = coordinate
        for node_id, tags in node_tags_small.items():
            merged_node_tags["S|" + node_id] = tags
        merged_ways += [
            ("S|" + way_id, ["S|" + n for n in node_refs], tags)
            for way_id, node_refs, tags in ways_small]
    lat_min, lon_min, lat_max, lon_max = box
    kept = []
    for way_id, node_refs, tags in merged_ways:
        if not _is_drivable_or_rail(tags):
            continue
        for node_ref in node_refs:
            coordinate = merged_nodes.get(node_ref)
            if coordinate is None:
                continue
            if (lat_min <= coordinate[0] <= lat_max
                    and lon_min <= coordinate[1] <= lon_max):
                kept.append((way_id, node_refs, tags))
                break
    return merged_nodes, kept, merged_node_tags


def _tile_small_roads_cache_exists(apt_lat: float, apt_lon: float) -> bool:
    """Is the tile-wide ``small_roads`` cache present for the airport's own
    1°×1° tile?  That file is the pre-feed source of minor-road evidence;
    its absence (the default-config case — see the section header) is what
    sends the feed to the regional extract."""
    return os.path.isfile(FNAMES.osm_cached(
        int(math.floor(apt_lat)), int(math.floor(apt_lon)), "small_roads"))


def _carriageway_widths(ways) -> dict[str, float]:
    """``{way id: carriageway width (m)}`` for every way, resolved once
    through ``bridges._carriageway_width_from_tags`` (the single source of
    truth for road width: ``width=`` → ``lanes=`` → per-type table).
    Railways get the same 8 m corridor the skirt reader uses."""
    from .bridges import _carriageway_width_from_tags
    from .clearance import _SKIRT_RAILWAY_CORRIDOR_M
    widths = {}
    for way_id, _node_refs, tags in ways:
        highway_type = tags.get("highway")
        if highway_type is None and tags.get("railway") is not None:
            widths[way_id] = _SKIRT_RAILWAY_CORRIDOR_M
        else:
            widths[way_id] = _carriageway_width_from_tags(
                highway_type, tags, 6.0)
    return widths


def _load_airport_road_network(layout) -> "AirportRoadNetwork | None":
    """Build and publish ``layout.airport_road_network``; also returns it.

    Source order, and why:

    1. the TILE ``small_roads`` cache when it exists — a user who raised
       ``road_level`` gets exactly the data the pre-feed loaders used
       (merged with ``big_roads``, both already on disk and lru-cached);
    2. otherwise the regional-extract CLIP for this area, filtered to the
       airport region — the default-config case, where path 1 has nothing;
    3. otherwise NOTHING, announced with one loud line rather than the
       silent empty return that hid this hole.

    Costs one extract read per airport per clip refresh (~1.1 s at HECA,
    see :func:`_extract_region_roads`); every later build of the same
    airport is a sidecar pickle load.  Returns ``None`` when the feed gate
    is off, so an OFF build does not even compute the query box."""
    from .config import AIRPORT_ROAD_FEED, AIRPORT_ROAD_FEED_PAD_M
    if not AIRPORT_ROAD_FEED:
        return None
    started = time.time()
    icao = getattr(layout, "icao", "") or "????"
    apt_lat, apt_lon = layout.anchor
    try:
        box = _airport_road_feed_box(layout, AIRPORT_ROAD_FEED_PAD_M)
    except Exception:
        return None

    if _tile_small_roads_cache_exists(apt_lat, apt_lon):
        nodes, ways, node_tags = _road_feed_from_tile_caches(
            apt_lat, apt_lon, box)
        network = AirportRoadNetwork(
            icao, box, nodes, ways, node_tags, _carriageway_widths(ways),
            "tile_cache", time.time() - started)
        layout.airport_road_network = network
        if not ways:
            _announce_no_road_data(
                icao, "the tile OSM road caches hold no road within the "
                      "airport region")
            return network
        UI.vprint(
            1, "   [road-feed] %s: %d road + %d rail way(s) from the tile "
               "OSM road caches (%.2f s)."
               % (icao, network.road_way_count, network.rail_way_count,
                  network.load_seconds))
        return network

    clip_parts = _regional_clip_parts_for_box(box)
    if clip_parts:
        sidecar_path, fingerprint = _road_feed_sidecar(
            icao, box, clip_parts)
        network = _read_road_feed_sidecar(sidecar_path, fingerprint)
        if network is not None:
            layout.airport_road_network = network
            UI.vprint(
                1, "   [road-feed] %s: %d road + %d rail way(s) from the "
                   "per-airport sidecar cache (%.2f s)."
                   % (icao, network.road_way_count, network.rail_way_count,
                      time.time() - started))
            return network
        try:
            nodes, ways, node_tags = _extract_region_roads(clip_parts, box)
        except Exception as error:
            _announce_no_road_data(
                icao, "regional extract clip unreadable: %s" % error)
            return None
        network = AirportRoadNetwork(
            icao, box, nodes, ways, node_tags, _carriageway_widths(ways),
            "regional_extract", time.time() - started)
        # Cache even an EMPTY result: a genuinely road-free airfield must
        # not re-parse the clip on every build to rediscover that.
        _write_road_feed_sidecar(sidecar_path, fingerprint, network)
        layout.airport_road_network = network
        if not ways:
            _announce_no_road_data(
                icao, "the regional extract clip holds no road within the "
                      "airport region")
            return network
        UI.vprint(
            1, "   [road-feed] %s: %d road + %d rail way(s) from the "
               "regional extract clip, box %.3f,%.3f..%.3f,%.3f (%.2f s, "
               "cached for the next build)."
               % (icao, network.road_way_count, network.rail_way_count,
                  box[0], box[1], box[2], box[3], network.load_seconds))
        return network

    # Nothing anywhere.  ONE loud line — this is the state that was silent
    # at every airport before the feed existed.
    _announce_no_road_data(
        icao, "no tile small_roads cache at road_level>=2, no regional "
              "extract clip for this area")
    return None


def _announce_no_road_data(icao: str, reason: str) -> None:
    """THE loud line.  Every path that ends with an airport having no road
    evidence goes through here — an absent source, an unreadable clip, or a
    present source that simply holds no road near the field.  ``vprint(0)``
    so it survives every verbosity setting: the whole point of the feed is
    that this state stopped being silent."""
    UI.vprint(
        0, "   [road-feed] %s: NO ROAD DATA - classification and road "
           "grading run without road evidence (%s)." % (icao, reason))
