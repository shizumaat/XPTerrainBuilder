import os
import time
import threading
from math import pi, sin, cos, sqrt, atan, exp, floor
from typing import NamedTuple
import numpy
from shapely import affinity, geometry, ops
from shapely.prepared import prep
from shapely.strtree import STRtree

# from PIL import Image, ImageDraw, ImageFilter
import O4_DEM_Utils as DEM
import O4_UI_Utils as UI
import O4_OSM_Utils as OSM
import O4_Vector_Utils as VECT
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Proj_Runtime as PROJRT
import O4_Airport_Utils as APT
import O4_Airport_Elevation_Insets as INSETS
import O4_Elevation_Level as ELEVATION_LEVEL
from auto_patch import driver as AUTOPATCH
from auto_patch import selection as _SELECTION
from auto_patch import osm_aeroway as OSMAERO
# The road grade cap, one constant for the whole engine (census #115),
# read from the V2 LAW TABLE since 2026-09-17 (lane ``v1retire`` round 1,
# session ruling (c)): the user knob ``road_grade_limit`` defaults to the
# SAME reader in ``O4_Cfg_Vars`` and this is the fallback for a tile
# object that predates the knob.  ONE definition —
# ``auto_patch_v2/law/rulesets.toml`` ``[common.roles]``
# ``service_road.longitudinal`` — and both readers point at it; it used to
# be ``auto_patch.config.SERVICE_ROAD_MAX_GRADE``, inside the retired v1
# engine.
from O4_Cfg_Vars import _road_grade_cap_from_law as _road_cap_from_law
from O4_Cfg_Vars import road_neighbourhood_law as _road_neighbourhood_law

ROAD_GRADE_CAP_DEFAULT = _road_cap_from_law()
import O4_Config_Utils as CFG

good_imagery_list = ()

################################################################################
# OSM layer download specifications, shared between the include_* encoders
# below and the background prefetch: a single source for each layer's
# Overpass statements and tags, so the cache a prefetch writes is exactly
# the cache the encoder would have written itself.
################################################################################
BIG_ROADS_QUERIES = [
    'way["highway"="motorway"]',
    'way["highway"="trunk"]',
    'way["highway"="primary"]',
    'way["highway"="secondary"]',
    'way["railway"="rail"]',
    'way["railway"="narrow_gauge"]',
]
# ``width`` / ``lanes`` size the auto-patch tunnel ramps from the mapped
# carriageway instead of the per-type width table (user 2026-07-16,
# EGPB: the table's 18 m ``primary`` default tripled the A970's width).
# ``layer`` / ``cutting`` / ``covered`` / ``embankment`` are the DEPTH
# WITNESSES the feed used to throw away at download (spec §45 (9), owner
# 2026-09-15 "Bump the schema now").  A below-grade road/rail channel cut
# through an airport (LGAV, KPHX, KDFW) is stated by ``cutting=yes`` or
# ``layer < 0`` on a way crossing the airside pavement union — §45 (1)(d)'s
# fourth identification witness — and ``covered`` / ``embankment``
# separate a roofed span and a raised causeway from a true cut.  The
# airports layer already keeps ["all"]; the road layers did not.
ROADS_TAGS_OF_INTEREST = ["bridge", "tunnel", "width", "lanes",
                          "layer", "cutting", "covered", "embankment"]
# Node tags retained on the road ways' child nodes: at-grade
# level-crossing evidence for the implied-crossing-tunnel veto (user
# 2026-07-16, EGPB/Gibraltar — the world's few public roads that cross
# an active runway at grade are mapped with ``aeroway=aircraft_crossing``
# and barrier gates, and must NOT get a synthetic tunnel).
ROAD_NODE_TAGS_OF_INTEREST = ["aeroway", "crossing:aircraft", "barrier"]
# Tag-schema version stamped into the road layer caches.  Bump it when
# the retained-tag whitelists above grow: caches written under an older
# schema are re-downloaded once instead of silently recycled without
# the new tags.
ROAD_CACHE_TAG_SCHEMA = "2026-09-15"
COASTLINE_QUERIES = ['way["natural"="coastline"]']
AIRPORTS_QUERIES = [('node["aeroway"]', 'way["aeroway"]', 'rel["aeroway"]')]
WATER_QUERIES = [
    'rel["natural"="water"]',
    'rel["waterway"="riverbank"]',
    'way["natural"="water"]',
    'way["waterway"="riverbank"]',
    'way["waterway"="dock"]',
]
# "tidal" and "water" feed the SEA_EQUIV routing of tidal ponds and
# lagoons (see water_polygon_is_tidal); bump WATER_CACHE_TAG_SCHEMA
# when this list grows so pre-existing caches re-download with the
# new tags.
WATER_TAGS_OF_INTEREST = ["name", "tidal", "water"]
WATER_CACHE_TAG_SCHEMA = "2026-07-17"

# PAVEMENT THAT IS IN OUR PATCH IS LAND (owner 2026-08-10, VMMC).
# Closed patch pavement rings are inserted carrying the WATER, SEA and
# SEA_EQUIV bits ALONGSIDE INTERP_ALT.  Triangle4XP's regionplague
# (Triangle4XP.c:13545) crosses any segment whose mark does not share a
# bit with the flood's own attribute, so an INTERP_ALT-only (8) ring
# does NOT stop a SEA flood: VMMC's taxiways C1/G/H are OSM
# ``bridge=yes`` viaducts over open water, and 263 mesh triangles /
# 114,406 m2 of patch pavement came out SEA|INTERP_ALT (attr 10) —
# wet texture and transparent mask over pavement we levelled.  With
# all four bits on the ring every water flood stops AT the pavement
# boundary; the interior keeps the INTERP_ALT seed's bit 8 alone
# (segment marks never become triangle attributes — see
# setelemattribute, Triangle4XP.c:1225), which reads as land in
# O4_DSF_Utils.remap_water_tri_type (8 & 7 == 0) and in
# O4_Mask_Utils.water_type_is_inland, and stays exempt from sea
# levelling in O4_Mesh_Utils (attr >= INTERP_ALT).  A patch ring that
# genuinely encloses water no longer floods it — intended.
# SCOPE: closed patch pavement rings ONLY.  Road ribbons
# (include_roads, INTERP_ALT at :966) and OBJ8 patch objects keep the
# bare INTERP_ALT marker, so genuine road bridges over water keep
# their WATER|INTERP_ALT (attr 9) triangles.
PATCH_RING_MARKER = (
    VECT.Vector_Map.dico_attributes["INTERP_ALT"]
    | VECT.Vector_Map.dico_attributes["WATER"]
    | VECT.Vector_Map.dico_attributes["SEA"]
    | VECT.Vector_Map.dico_attributes["SEA_EQUIV"]
)

# AN OPEN LOAD-BEARING RUN IS A BREAKLINE, NOT A DUMMY EDGE (owner
# RULINGS 2026-09-13cp).  MEASURED on the owner's 1.0.329 +40-004 tile:
# since §37 (3) ("the bank is emitted where it is load-bearing",
# c632622d) LEMD's patch carries 105 OPEN ``bank_foot`` ways and 0
# closed, and the ``else`` branch of the way loop below inserted every
# open way as ``DUMMY`` (attr 0).  The foot then stopped being the
# INTERP_ALT flood barrier and the Dirichlet datum of R18-1b, the bank
# annulus collapsed from 33,377 valued vertices to 15, and the harmonic
# extension interpolated the vacated corridor from remote data — road
# ribbons authored at 588-590 m emitted at 568 (a 20.7 m canyon at
# 40.465414,-3.5531888).
#
# THE RULE, and its SCOPE: an open way whose CLOSED form would wear
# :data:`PATCH_RING_MARKER` wears it open too.  That is exactly the
# features the emitter may split — a ``bank_foot`` ring cut by a tile
# piece or by §37 (3)'s load-bearing runs, and a ``structure_rim`` cut
# the same way (``auto_patch_v2.emit.osm_adapter``).  ``crown_spine``
# and ``terrain_edge`` are ALWAYS open and never wore the marker, so
# they keep ``DUMMY``: widening to them would be a new law, separately
# measured, not this repair.
OPEN_BREAKLINE_FEATURES = ("bank_foot", "structure_rim")

# SEAWALL AT THE PAVEMENT/WATER EDGE (owner 2026-08-10, VMMC; Round 7,
# docs/specs/round7-seawall-spec.md).  The ring above stops the flood, so
# the pavement comes out land — but the mesh OUTSIDE the ring still had to
# get from deck elevation down to the water over whatever horizontal run
# the triangulation happened to give it, which is a ramp where reality has
# a wall ("the water itself is sloping up to the taxiway").  Where a patch
# pavement ring borders water we therefore emit a companion breakline
# offset OUTWARD by SEAWALL_OFFSET_M at the WATER's own level: the drop
# then happens over 0.5 m and reads vertical.
#
# The wall carries INTERP_ALT and NOTHING ELSE.  It is an elevation
# constraint, never a region boundary: bit 8 shares no bit with WATER (1),
# SEA (2) or SEA_EQUIV (4), so every water flood crosses it freely and the
# 0.5 m band between ring and wall stays owned by the sea (wet texture,
# mask, sea levelling) exactly as it was.  Giving the wall any water bit
# would fence the sea OUT of its own foreshore.
#
# Land-bordering ring segments emit nothing: the offset curve is
# intersected with the water geometry, so a fully inland patch is
# untouched and the normal blends are unchanged.
SEAWALL_OFFSET_M = 0.5
SEAWALL_OFFSET_ENV = "O4_SEAWALL_OFFSET_M"

# THE ADMISSION SET IS THE EMITTED GRADED COVERAGE (Round 17 §R17-3,
# owner ruling: "the WHOLE airport edge is vertical sea wall").  The wall
# law's geometry used to be ``patches_area`` — EVERY valid closed way in
# the patch, which is the LAND cutter's union (R4) and includes the
# aerodrome BOUNDARY ribbon and the water-spanning bridge/road ribbons.
# The admission set is now role-scoped: the rings that carry a LAND
# altitude.  Two spellings of the role vocabulary would be a second law,
# so ``tests/test_r17_seawall_admission.py`` twin-asserts these against
# ``auto_patch.layout``'s own constants; they are spelled literally here
# only to keep the vector map's import light.
#
# EXCLUDED, and why: ``boundary`` (the OSM aerodrome boundary — VMMC's
# spans real open sea, the standing R4 control), ``service_road`` /
# ``bridge_causeway`` / ``bridge_trench`` (ribbon roles that legitimately
# cross water), and the clearance / OLS cuts (cut-only rings, not graded
# ground).
SEAWALL_PAVEMENT_ROLES = frozenset({
    "runway", "runway_crossing", "primary_parallel", "secondary_parallel",
    "stub", "cross_connector", "apron", "junction", "service_junction",
    "groundside_pavement", "building", "object_pad",
})
GRADED_COVERAGE_ROLES = frozenset(SEAWALL_PAVEMENT_ROLES | {
    "graded_strip", "tunnel_trench", "tunnel_ramp", "retaining_wall",
})
# Sea level.  The coastline limb of the wall sits at zero because that is
# where O4_Mesh_Utils levels SEA triangles; the inland-water limb is given
# the same altitude source the water rings themselves are draped on
# (``tile.dem.alt_vec``), which is the only water level the vector map
# knows for a lake or a river.
SEAWALL_SEA_LEVEL_M = 0.0
SEAWALL_MARKER = VECT.Vector_Map.dico_attributes["INTERP_ALT"]


def seawall_offset_m():
    """The outward seawall offset in metres.

    ``SEAWALL_OFFSET_M`` (0.5 m) unless ``O4_SEAWALL_OFFSET_M`` overrides
    it.  An unparseable or non-positive override falls back to the
    constant rather than silently disabling the wall.
    """
    raw = os.environ.get(SEAWALL_OFFSET_ENV)
    if raw is None:
        return SEAWALL_OFFSET_M
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return SEAWALL_OFFSET_M
    return value if value > 0 else SEAWALL_OFFSET_M


def _flatten_linestrings(geom):
    """Every LineString inside ``geom``, at any nesting depth."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    if hasattr(geom, "geoms"):
        out = []
        for sub in geom.geoms:
            out.extend(_flatten_linestrings(sub))
        return out
    return []


def seawall_admission_area(patches_area, graded_area):
    """THE WALL'S ADMISSION GEOMETRY (Round 17 §R17-3).

    The emitted GRADED COVERAGE — ``include_patches``' role-scoped union
    — when there is one, and the full patch union otherwise.  The
    fallback is not a second law: it is the pre-R17 behaviour for a patch
    that carries no role tags at all (a hand-written manual patch), where
    "the rings that carry land altitudes" is unanswerable and the only
    honest answer is the whole coverage.  A patch WITH roles never takes
    it, so VMMC's aerodrome boundary ribbon — which spans real open sea —
    is out of the admission set for every generated patch.
    """
    if graded_area is None or getattr(graded_area, "is_empty", True):
        return patches_area
    return graded_area


#: R17c-3 — the provenance KINDS that carry the airport's own island
#: UNCONDITIONALLY: the airport's flat-site constant CORE and (R21) the
#: ISTHMUS the flat-site family was found to be land-connected across.
#: The isthmus is unconditional here for the same reason the core is: it
#: is not a claim about distant ground, it is the LAND MEASURED between
#: two footprints already admitted on one sea-bounded component.
AIRPORT_ISLAND_INSET_KINDS = ("synthetic_flat_site", "flat_site_isthmus")

#: R17D LAW 2 — the CLAIMED-OBJECT CLUSTER kind, admitted CONDITIONALLY
#: (see :func:`connected_cluster_inset_area`).  r17c kept it out whole,
#: because a cluster rectangle is the box that reached the mainland
#: (VHHH's 15.11 km² HZMB cluster; 66,971 m of wall over 55.47 km²).
#: The owner's 2026-08-12 ruling ("CONNECTED-ISLAND WALLS", in-sim on the
#: rebuilt +22+113) names the other half: the island CONNECTED to the
#: airport complex gets the straight seawall too — its edge must not
#: slope to water.  So the kind joins the reading exactly where it is
#: connected, and stays out where it is not.
AIRPORT_ISLAND_CLUSTER_INSET_KIND = "synthetic_flat_site_object_cluster"


def constant_inset_area(tile, kinds=AIRPORT_ISLAND_INSET_KINDS):
    """THE FLAT-SITE CONSTANT-INSET FOOTPRINT, tile-relative (R17b-2).

    The union of the boxes DEM prep actually BAKED a synthetic constant
    inset over on this tile, read from the stamp
    ``O4_Airport_Elevation_Insets.overlay_flat_site_insets`` writes on the
    DEM object (``synthetic_flat_site_provenance``).

    ``kinds`` selects which stamped families count.  The default is
    R17c-3's: the airport's own extent and the owner's declared
    corridors.  ``None`` takes every stamped entry (the pre-R17c
    reading), which is what a caller measuring the BAKED surface — as
    opposed to the airport's island — wants.

    IT IS READ, NEVER RE-DERIVED.  The extents are decided by the flat-site
    detector, the cluster law and the owner's declaration, and a cluster
    the R11-2 datum check REFUSED is not stamped — so a second computation
    here would claim ground the DEM does not actually hold at Z0.  Empty
    geometry (the inert answer) on every tile with no flat-site
    substitution.
    """
    dem = getattr(tile, "dem", None)
    entries = list(getattr(dem, "synthetic_flat_site_provenance", None) or [])
    boxes = []
    for entry in entries:
        if kinds is not None and entry.get("kind") not in kinds:
            continue
        extent = entry.get("extent_tile_degrees")
        if not extent or len(extent) != 4:
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in extent)
            box = geometry.box(min(x0, x1), min(y0, y1),
                               max(x0, x1), max(y0, y1))
        except (TypeError, ValueError):
            continue
        if box.is_valid and box.area:
            boxes.append(box)
    if not boxes:
        return geometry.Polygon()
    try:
        return ops.unary_union(boxes)
    except Exception:
        return geometry.Polygon()


def connected_cluster_inset_area(tile, core_area):
    """R17D LAW 2 — the CLAIMED-CLUSTER inset boxes JOINED to the airport
    complex, tile-relative.

    THE LAW (owner ruling 2026-08-12, "CONNECTED-ISLAND WALLS", in-sim on
    the rebuilt +22+113): the wall/feather treatment extends to the
    claimed-cluster inset islands CONNECTED to the airport complex —
    contact with the core/corridor footprint, or joined by a DECLARED
    corridor, which is what declaring one means.  Distant, unconnected
    clusters stay out: r17c excluded the kind whole precisely because a
    cluster box can reach the mainland, and admitting one that touches
    nothing of the airport would re-open that.

    CONNECTED IS TRANSITIVE, by fixpoint: a cluster that touches a
    cluster that touches the core is joined to the core.  A chain of
    reclamation boxes along one causeway is one complex, and stopping at
    the first hop would split it arbitrarily.

    This is the FOOTPRINT half of the ruling only.  Which LAND inside the
    admitted boxes is the airport's stays :func:`airport_island_land`'s
    question, and it still refuses the mainland reach of an admitted
    cluster box: the mainland is a different land COMPONENT and carries
    none of the tile's graded coverage.  Two gates, two different
    failures, neither one spelled twice.

    ``core_area`` — the union of the unconditional kinds
    (:data:`AIRPORT_ISLAND_INSET_KINDS`).  Empty core ⇒ empty: with no
    airport footprint on the tile there is nothing to be connected TO.
    """
    if core_area is None or getattr(core_area, "is_empty", True):
        return geometry.Polygon()
    clusters = []
    dem = getattr(tile, "dem", None)
    for entry in list(getattr(dem, "synthetic_flat_site_provenance", None)
                      or []):
        if entry.get("kind") != AIRPORT_ISLAND_CLUSTER_INSET_KIND:
            continue
        extent = entry.get("extent_tile_degrees")
        if not extent or len(extent) != 4:
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in extent)
            box = geometry.box(min(x0, x1), min(y0, y1),
                               max(x0, x1), max(y0, y1))
        except (TypeError, ValueError):
            continue
        if box.is_valid and box.area:
            clusters.append(box)
    if not clusters:
        return geometry.Polygon()
    joined = []
    frontier = core_area
    pending = list(clusters)
    while True:
        reached = []
        rest = []
        for box in pending:
            try:
                (reached if box.intersects(frontier) else rest).append(box)
            except Exception:                              # pragma: no cover
                rest.append(box)
        if not reached:
            break
        joined.extend(reached)
        pending = rest
        try:
            frontier = ops.unary_union(reached)
        except Exception:                                  # pragma: no cover
            break
    if not joined:
        return geometry.Polygon()
    try:
        return ops.unary_union(joined)
    except Exception:                                      # pragma: no cover
        return geometry.Polygon()


def airport_island_land(inset_land, graded_area):
    """R17c-3 — THE AIRPORT'S ISLAND, out of the inset's land.

    A flat-site extent is a RECTANGLE around an airport, so the land
    inside it is not only the airport's island: at VHHH the box also
    holds Lantau's north shore, and r17b's tile-wide union admitted
    66,971 m of wall over 55.47 km² spanning three flat sites and the
    mainland.  The owner's ruling walls THE AIRPORT's reclaimed edge.

    THE ISLAND IS THE LAND COMPONENT THE AIRPORT STANDS ON — a connected
    component of the inset's land that carries some of the tile's EMITTED
    GRADED COVERAGE.  Production's own coverage union answers it: an
    island with an airport on it has graded rings on it, mainland inside
    the same rectangle does not, and a component reached only across
    water is a different island.  A DECLARED corridor joins the island
    exactly when the declaration has made the two continuous, which is
    what declaring it means.

    ``graded_area`` empty ⇒ empty: with no coverage there is nothing that
    says which land is the airport's, and admitting the whole rectangle
    is the wrong scope the ruling names.  Every airport on the tile is
    served by the same pass — VMMC's island is admitted by VMMC's own
    coverage — so this scopes without ever naming an ICAO.
    """
    if inset_land is None or getattr(inset_land, "is_empty", True):
        return geometry.Polygon()
    if graded_area is None or getattr(graded_area, "is_empty", True):
        return geometry.Polygon()
    keep = []
    for piece in getattr(inset_land, "geoms", [inset_land]):
        if piece is None or piece.is_empty:
            continue
        try:
            if piece.intersects(graded_area):
                keep.append(piece)
        except Exception:                                  # pragma: no cover
            continue
    if not keep:
        return geometry.Polygon()
    try:
        return ops.unary_union(keep)
    except Exception:                                      # pragma: no cover
        return geometry.Polygon()


def coastline_wall_admission(tile, sea_area, graded_area=None):
    """R17b-2 — THE WALL STANDS ON THE COASTLINE, R17c-3 — ON THE
    AIRPORT'S ISLAND.

    Owner ruling (2026-08-11): the WHOLE edge of a reclaimed airport
    island is a vertical sea wall, not the ~26 % beach ramps R7's
    pavement-touches-water admission left it as.  Where the OSM coastline
    runs INSIDE a flat site's constant-inset footprint, the ground on the
    land side of it is held at the inset's Z0 by the inset itself (the
    coastline is encoded with ``tile.dem.alt_vec``, so its own nodes
    already carry Z0 there) — what is missing is the sea-side node that
    turns the drop into a face instead of a ramp.

    So this returns the LAND inside the inset, and the wall law's own
    unchanged 0.5 m outward-offset idiom does the rest: the breakline
    lands 0.5 m seaward of the coastline ring, at sea level, and the face
    between it and the Z0 coastline is vertical.  The admission geometry
    widens; not one line of ``seawall_breaklines`` changes.

    R17c-3 SCOPES IT to the airport's island (see
    :func:`airport_island_land`): the constant CORE and the DECLARED
    corridors, and of their land only the components the tile's graded
    coverage stands on.  ``graded_area`` omitted ⇒ empty, because
    "which land is the airport's" is then unanswerable and the whole
    rectangle is the wrong scope.

    R17D LAW 2 EXTENDS THE FOOTPRINT to the claimed-cluster inset
    islands CONNECTED to the airport complex (owner 2026-08-12,
    "CONNECTED-ISLAND WALLS": the island joined to the airport by the
    declared corridor gets the straight seawall too) — see
    :func:`connected_cluster_inset_area`.  The island scoping below is
    unchanged and still refuses the mainland an admitted cluster box
    happens to reach.

    VMMC is NOT a byte-identical control (owner ruling 2026-08-12: it is
    itself a flat site at Z0 6.10) — its island is admitted by the same
    scoping, judged against its own island edge.
    """
    inset = constant_inset_area(tile)
    if inset is None or inset.is_empty:
        return geometry.Polygon()
    clusters = connected_cluster_inset_area(tile, inset)
    if clusters is not None and not getattr(clusters, "is_empty", True):
        try:
            inset = ops.unary_union([inset, clusters])
        except Exception:                                  # pragma: no cover
            pass
    if sea_area is None or getattr(sea_area, "is_empty", True):
        # No sea on this tile: the inset is all land and its own outer
        # box edge is not a coastline.  Nothing to admit.
        return geometry.Polygon()
    try:
        land = inset.difference(sea_area)
    except Exception:
        return geometry.Polygon()
    if land is None or land.is_empty:
        return geometry.Polygon()
    return airport_island_land(land, graded_area)


def seawall_breaklines(patches_area, water_area, lat, offset_m=None):
    """Outward-offset breaklines along the patch ring where it meets water.

    ``patches_area`` is the patch pavement union from ``include_patches``
    and ``water_area`` the water the vector map itself knows — the sea
    seed area in ``include_sea``, the OSM water / sea-equivalent
    multipolygons in ``include_water``.  Both are tile-relative
    (``lon - tile.lon``, ``lat - tile.lat``); ``lat`` is the tile's base
    latitude.

    The offset is taken by BUFFERING the pavement union outward in a
    locally isotropic frame (longitudes scaled by cos(latitude), so one
    unit is one degree of latitude in both axes) and reading the buffer's
    boundary.  Buffering — rather than offsetting each segment by its own
    normal — is what makes "outward" unambiguous for holes as well as
    exteriors, keeps the curve continuous around corners, and can never
    self-intersect at a concave one.  The result is then intersected with
    the water: ring segments that border land contribute nothing.

    Returns a list of ``(N, 2)`` float arrays.  Any geometry failure
    returns an empty list — a seawall is a refinement, and must never
    cost the coastline or the water encoding.
    """
    if patches_area is None or water_area is None:
        return []
    try:
        if patches_area.is_empty or water_area.is_empty:
            return []
        (pminx, pminy, pmaxx, pmaxy) = patches_area.bounds
        (wminx, wminy, wmaxx, wmaxy) = water_area.bounds
    except (AttributeError, ValueError):
        return []
    # Cheap reject: pavement and water nowhere near each other.  Most
    # tiles pay only this.
    if pminx > wmaxx or pmaxx < wminx or pminy > wmaxy or pmaxy < wminy:
        return []
    offset = seawall_offset_m() if offset_m is None else float(offset_m)
    if not offset > 0:
        return []
    cos_lat = cos((lat + (pminy + pmaxy) / 2) * pi / 180)
    if not cos_lat > 1e-6:
        return []
    try:
        scaled = affinity.scale(
            patches_area, xfact=cos_lat, yfact=1.0, origin=(0, 0)
        )
        grown = scaled.buffer(
            offset * GEO.m_to_lat, join_style=2, mitre_limit=2.0
        )
        if grown.is_empty:
            return []
        curve = affinity.scale(
            grown.boundary, xfact=1 / cos_lat, yfact=1.0, origin=(0, 0)
        )
        wall = VECT.cut_to_tile(curve.intersection(water_area))
    except Exception:
        return []
    lines = []
    for piece in _flatten_linestrings(wall):
        coords = numpy.array(piece.coords, dtype=float)
        if len(coords) >= 2:
            lines.append(coords)
    return lines


def insert_seawalls(
    vector_map, tile, patches_area, water_area, alt_vec=None, offset_m=None
):
    """Insert the seawall breaklines for one water limb.  Returns the count.

    ``alt_vec`` is the altitude source for the wall's nodes: ``None``
    means the constant sea level (the coastline limb), otherwise a
    ``tile.dem.alt_vec``-shaped callable (the inland-water limb, whose
    level is whatever the water rings themselves are draped on).

    Node identity is by coordinate (``Vector_Map.insert_node``), so a
    stretch of wall shared between the two limbs keeps the altitude of
    whichever ran first — and the coastline limb runs first, so the sea
    wins where sea and mapped water overlap.
    """
    lines = seawall_breaklines(
        patches_area, water_area, tile.lat, offset_m=offset_m
    )
    inserted = 0
    wall_m = 0.0
    for coords in lines:
        try:
            # THE LENGTH IS THE ACCEPTANCE NUMBER (R17-3 / R17b-2 state
            # the wall as a PERCENTAGE of the shoreline), so production
            # states it rather than leaving every reader to re-measure
            # the breaklines from the built tile.
            step = numpy.diff(numpy.asarray(coords, dtype=float), axis=0)
            wall_m += float(numpy.hypot(
                step[:, 0] * GEO.lon_to_m(tile.lat + 0.5),
                step[:, 1] * GEO.lat_to_m).sum())
        except Exception:
            pass
        try:
            if alt_vec is None:
                alti = numpy.full(
                    (len(coords), 1), float(SEAWALL_SEA_LEVEL_M)
                )
            else:
                alti = numpy.asarray(
                    alt_vec(coords), dtype=float
                ).reshape((len(coords), 1))
            vector_map.insert_way(
                numpy.hstack([coords, alti]), SEAWALL_MARKER, check=True
            )
            inserted += 1
        except Exception:
            UI.vprint(2, "     Skipping an unusable seawall breakline.")
    if inserted:
        UI.vprint(
            1,
            "      Seawall: {} breakline(s), {:.0f} m at the graded"
            " coverage/water edge.".format(inserted, wall_m),
        )
    return inserted


def water_polygon_is_tidal(osmid, dicosmtags):
    """Whether an OpenStreetMap water polygon belongs to the tidal regime.

    True for polygons tagged ``tidal=yes`` (the Ria Formosa salinas and
    esteros) or mapped as coastal lagoons (``water=lagoon`` — the Ria
    Formosa itself is one such relation).  These areas keep the INLAND
    water treatment (orthophoto at the constant ``ratio_water``
    transparency with X-Plane water on top) even where the coastline
    polygon claims them as open sea: :func:`include_sea` refuses to
    seed the SEA attribute inside them, so the deep-water fade begins
    at the true coast, never inside a mapped lagoon.  (Routing these to
    SEA_EQUIV instead was tried on 2026-07-17 and reverted: the sea's
    depth-graded masks read the intertidal lidar as exposed flats and
    printed permanently wet water — marinas, channels — as opaque dark
    imagery with razor polygon-edge seams.)
    """
    tags = dicosmtags.get(osmid, {})
    return tags.get("tidal") == "yes" or tags.get("water") == "lagoon"


def sea_seed_areas(sea_area, tidal_water_area, patch_pavement_area=None):
    """Where the SEA attribute may be seeded: the sea minus tidal water
    and minus patch pavement.

    The coastline's contiguous sea polygon often reaches through inlets
    INTO a mapped lagoon, and its representative point (the flood seed)
    can land there — classifying the whole lagoon as deep sea.  Tidal
    water polygons' boundaries are already encoded mesh constraints, so
    withholding seeds from their interiors is sufficient: the flood
    stops at their rings and the lagoon's own WATER seeds win.  Slivers
    between the coastline and a lagoon ring keep their own seeds (they
    are genuinely sea).

    ``patch_pavement_area`` is the patch pavement union
    (``include_patches``' ``patches_area``) and applies the same
    treatment as belt and braces to the ring marker (see
    PATCH_RING_MARKER): pavement in our patch is LAND, so no SEA seed
    is planted inside it even where the coastline claims it — VMMC's
    seaward taxiway viaducts.  THE CUTTER IS THE PAVEMENT UNION, never
    the flat-site extent or the aerodrome boundary: VMMC's boundary
    spans the genuine channel, and drying that would be wrong.

    Any geometry failure falls back to the sea area as accumulated so
    far — a mis-seeded lagoon (or a bad patch union) must never cost
    the whole coastline.
    """
    remainder = sea_area
    for subtractor in (tidal_water_area, patch_pavement_area):
        if subtractor is None or subtractor.is_empty:
            continue
        try:
            remainder = VECT.ensure_MultiPolygon(
                remainder.difference(subtractor)
            )
        except Exception:
            continue
        if remainder.is_empty:
            return remainder
    return remainder


def small_roads_queries(road_level):
    queries = ['way["highway"="tertiary"]']
    if road_level >= 3:
        queries += [
            'way["highway"="unclassified"]',
            'way["highway"="residential"]',
        ]
    if road_level >= 4:
        queries += ['way["highway"="service"]']
    if road_level >= 5:
        queries += ['way["highway"="track"]']
    return queries


def resolved_road_level(tile):
    """``(numeric_level, auto)`` for the tile's ``road_level`` setting.

    "auto" (the default since 2026-07-27, owner ruling — same pattern as
    the elevation/imagery auto modes) means: level 1 tile-wide (major
    roads + railways) PLUS full level-5 roads and rails inside each
    airport's elevation-inset neighbourhood (see ``build_roads``).
    Numeric strings and legacy ints resolve to the historical tile-wide
    levels.  Unparseable values read as "auto" rather than crashing a
    build over a config typo."""
    raw = getattr(tile, "road_level", "auto")
    if isinstance(raw, str) and raw.strip().lower() == "auto":
        return 1, True
    try:
        return int(raw), False
    except (TypeError, ValueError):
        return 1, True


#: MOVED to ``auto_patch.selection`` (spec §A.2): ONE spelling of the mode
#: normalisation, shared with the inset selection.  Re-exported here because
#: this module is where every existing caller looks for it.
resolved_auto_patch_mode = _SELECTION.resolved_auto_patch_mode


def auto_patch_runs(tile):
    """True when this tile build generates auto-patches at all."""
    return resolved_auto_patch_mode(tile) != "None"


# Rail classes added on top of ``small_roads_queries(5)`` inside the
# airport-inset regions in auto mode: the tile-wide big_roads layer
# already levels ``rail``/``narrow_gauge`` mainlines, but airport rail
# yards, sidings and people-mover lines are none of those.
AUTO_AIRPORT_RAIL_QUERIES = [
    'way["railway"="siding"]',
    'way["railway"="spur"]',
    'way["railway"="yard"]',
    'way["railway"="tram"]',
    'way["railway"="light_rail"]',
]


def _airport_auto_roads_layer(tile):
    """The auto-road-mode OSM layer of ``tile`` — see
    :func:`_airport_auto_roads_layer_at`, which is the body.  The split
    exists because :func:`ensure_auto_patch_road_feeds` must be able to
    re-derive a NEIGHBOUR tile's feed, for which no ``Tile`` object
    exists in this build (only ``lat`` / ``lon`` were ever read here)."""
    return _airport_auto_roads_layer_at(tile.lat, tile.lon)


def _airport_auto_roads_layer_at(lat, lon):
    """The auto-road-mode OSM layer: level-5 road classes + airport rail
    classes fetched ONLY inside the airport elevation-inset bounding
    boxes (read from the inset GeoTIFF json sidecars), merged into one
    per-tile cache (``airport_small_roads``).  Returns ``None`` when the
    tile has no cached insets (feature off, no airports) or every bbox
    query failed — the caller then simply keeps the level-1 behaviour."""
    import json as _json

    import O4_Airport_Elevation_Insets as INSETS

    try:
        inset_paths = INSETS.list_cached_inset_dems(lat, lon)
    except Exception:
        inset_paths = []
    boxes = []
    for tif_path in inset_paths:
        sidecar = os.path.splitext(tif_path)[0] + ".json"
        try:
            with open(sidecar, "r", encoding="utf-8") as handle:
                meta = _json.load(handle)
            lon_min, lat_min, lon_max, lat_max = meta["bounding_box_wgs84"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        boxes.append((lat_min, lon_min, lat_max, lon_max))
    if not boxes:
        return None
    queries = small_roads_queries(5) + AUTO_AIRPORT_RAIL_QUERIES
    # target/input tag dicts exactly as ``OSM_query_to_OSM_layer``
    # derives them from (queries, tags_of_interest) — needed for the
    # merged-cache recycle path, which that function cannot serve
    # (it caches per call, we cache per tile across all boxes).
    target_tags = {"n": [], "w": [], "r": []}
    input_tags = {"n": [], "w": [], "r": []}
    for q in queries:
        items = q.split('"')
        osm_type = items[0][0]
        target_tags[osm_type].append((items[1], items[3]))
        input_tags[osm_type].append((items[1], items[3]))
        for tag in ROADS_TAGS_OF_INTEREST:
            target_tags[osm_type].append((tag, ""))
    layer = OSM.OSM_layer()
    cache_path = FNAMES.osm_cached(lat, lon, "airport_small_roads")
    # THE CACHE IS RECYCLED ONLY WHEN SCHEMA-CURRENT (2026-09-17, app
    # 1.0.349 aborted EVERY tile: auto_patch_v2's reader refuses a road
    # feed carrying a superseded or absent ``o4_tag_schema`` — RULINGS
    # 2026-09-17t chip D — and this writer had never stamped its cache
    # nor re-derived it, so every airport at every tile read an
    # unstamped file).  Same predicate the tile-wide layers use
    # (``_layer_cache_is_current``).  A stale copy is MOVED ASIDE, not
    # deleted, and put back if the re-derivation yields nothing (the
    # harness precedent ``build_airport.refresh_stale_osm_layers``: a
    # stale corpus beats an absent one when Overpass fails).
    aside_path = None
    if os.path.isfile(cache_path):
        if OSM._cached_osm_schema_matches(cache_path, ROAD_CACHE_TAG_SCHEMA):
            UI.vprint(1, "    * Recycling airport-area road data from",
                      cache_path)
            layer.update_dicosm(cache_path, input_tags, target_tags)
            return layer
        aside_path = cache_path + ".stale"
        UI.vprint(1, "    * Airport-area road cache", cache_path,
                  "predates tag schema", ROAD_CACHE_TAG_SCHEMA,
                  "- re-deriving it (stale copy set aside).")
        try:
            os.replace(cache_path, aside_path)
        except OSError:
            aside_path = None
    got_any = False
    # Regional-extract backend first, all inset boxes batched into ONE
    # filtering pass (the pbf filtering cost is dominated by reading the
    # whole extract, so N boxes in one pass cost one read instead of N).
    # ``OSM_query_to_OSM_layer`` below has no extract path — before this
    # attempt existed, a cold cache meant one Overpass round per airport
    # bbox even with the covering extract already on disk.  Same
    # accelerator-never-dependency discipline as the tile-wide layers:
    # any failure falls through to the historic Overpass loop.
    try:
        import O4_OSM_Extracts as EXTRACTS

        xml_bytes = EXTRACTS.osm_xml_from_local_extracts(
            queries, boxes, request_description="airport_small_roads")
    except Exception:
        xml_bytes = None
    if xml_bytes:
        layer.update_dicosm(xml_bytes, input_tags, target_tags)
        got_any = True
    else:
        for bbox in boxes:
            if OSM.OSM_query_to_OSM_layer(
                    queries, bbox, layer,
                    tags_of_interest=ROADS_TAGS_OF_INTEREST):
                got_any = True
            if UI.red_flag:
                return None
    if not got_any:
        if aside_path and not os.path.isfile(cache_path):
            try:
                os.replace(aside_path, cache_path)
            except OSError:
                pass
        return None
    try:
        layer.write_to_file(
            cache_path,
            header_attributes={"o4_tag_schema": ROAD_CACHE_TAG_SCHEMA})
    except OSError:
        pass
    if aside_path and os.path.isfile(cache_path):
        try:
            os.remove(aside_path)
        except OSError:
            pass
    return layer


#: The road feeds auto_patch_v2 reads, and the fallback tile square, used
#: when ``auto_patch_v2.airport.osm`` cannot be imported (see
#: :func:`_v2_road_feed_paths`).  The reader's own constants are preferred
#: — a second spelling would ensure a different file set than the one it
#: refuses.
_ROAD_FEED_NEIGHBOURHOOD = (-1, 0, 1)


def _v2_road_feed_paths(lat, lon):
    """Every cached road feed the auto_patch_v2 reader will TOUCH for a
    build of tile ``(lat, lon)``, as ``(tlat, tlon, feed, path_or_None)``.

    The square and the spelling are the READER'S OWN — ``ROAD_FEEDS``
    (which feeds carry a tag whitelist) and ``feed_path`` (``.osm.bz2``
    then ``.osm``), imported from ``auto_patch_v2.airport.osm``, never
    copied: the harness's ``superseded_road_feeds`` sets the precedent.
    ``load_feed`` merges the 3x3 tile neighbourhood, so a NEIGHBOUR
    tile's feed is read exactly as the home tile's is.

    ``path`` is ``None`` when the tile has no such file — absence is
    lawful (the reader treats a missing tile as an empty feed) and is
    NEVER turned into a download here.
    """
    from auto_patch_v2.airport import osm as _v2osm   # in-tree, bundled

    osm_root = FNAMES.OSM_dir
    out = []
    for dlat in _ROAD_FEED_NEIGHBOURHOOD:
        for dlon in _ROAD_FEED_NEIGHBOURHOOD:
            tlat, tlon = int(lat) + dlat, int(lon) + dlon
            for feed in _v2osm.ROAD_FEEDS:
                path = _v2osm.feed_path(osm_root, tlat, tlon, feed)
                out.append((tlat, tlon, feed,
                            path if os.path.isfile(path) else None))
    return out


def _rederive_road_feed(lat, lon, feed):
    """Re-derive one cached road feed through its ONE existing
    production writer.  Returns True when a layer came back.

    ``airport_small_roads`` -> :func:`_airport_auto_roads_layer_at`,
    which moves the stale copy aside and puts it BACK when the
    derivation yields nothing.  ``big_roads`` -> ``O4_OSM_Utils.
    OSM_queries_to_OSM_layer``, which leaves the stale cache untouched
    on the disk when the download fails (the same "a stale corpus beats
    an absent one" discipline, already implemented there) and holds the
    per-cache-file lock, so it can never race the background prefetch.
    """
    if feed == "airport_small_roads":
        return _airport_auto_roads_layer_at(lat, lon) is not None
    if feed == "big_roads":
        return bool(OSM.OSM_queries_to_OSM_layer(
            BIG_ROADS_QUERIES,
            OSM.OSM_layer(),
            lat,
            lon,
            ROADS_TAGS_OF_INTEREST,
            cached_suffix="big_roads",
            node_tags_of_interest=ROAD_NODE_TAGS_OF_INTEREST,
            cache_schema=ROAD_CACHE_TAG_SCHEMA,
        ))
    return False


class RoadFeedPrecheck(NamedTuple):
    """What :func:`ensure_auto_patch_road_feeds` found and could do.

    ``derived`` — the ``(lat, lon, feed)`` triples it re-derived.
    ``stale``   — the ``(lat, lon, feed, path)`` feeds that are STILL on
    disk and STILL not schema-current after the attempt (offline, no
    extract, the download failed).  The v2 reader refuses exactly these,
    once inside every airport's worker, so the caller narrates them ONCE
    for the tile instead (issue #24, RULINGS 2026-09-18d (1) residual
    (a)).  An ABSENT feed is never listed: absence is lawful and the
    reader reads it as an empty feed.
    """

    derived: list
    stale: list


def ensure_auto_patch_road_feeds(tile):
    """Make EVERY cached road feed auto_patch_v2 will read SCHEMA-CURRENT
    before it reads them — the home tile's and its eight neighbours'.

    ``auto_patch_v2.airport.load.load_with_report`` refuses a PRESENT
    road feed whose ``o4_tag_schema`` is superseded (RULINGS
    2026-09-15u) or absent (RULINGS 2026-09-17t) and names the file.
    An app user has no ``build_airport.py --refresh-data osm_layers`` to
    run, so the production path must make the feeds current HERE, before
    ``generate_auto_patches``.  RULINGS 2026-09-17ad did this for the
    HOME tile's ``airport_small_roads`` only, and tile +46+006 then
    aborted ALL ELEVEN of its airports (LSGG, LSGB, LFLI, LFSP, LSGL,
    LSGN, LSGP, LSGY, LSMP, LSTO, LSTR) on ONE stale file — the
    NEIGHBOUR tile's ``+46+007_big_roads.osm.bz2`` (app engine 1.50.1796,
    engine-stderr 2026-09-18).  Nine tiles x two feeds is the reader's
    square; anything less leaves the same abort reachable.

    ABSENCE IS LAWFUL AND NEVER DOWNLOADED.  A feed not on disk makes
    the reader read an empty feed for that tile, which it accepts, so
    this function leaves it alone — a tile build must never widen into
    its neighbours' tile-wide downloads.  The ONE exception is the home
    tile's own ``airport_small_roads`` (RULINGS 2026-09-17ad): this
    tile's vector step WOULD write it, but only AFTER auto_patch has
    read it, so an absent one is derived here.

    COST WHEN CURRENT: one ``isfile`` plus a two-line header read per
    feed present — at most 18 small bz2 header decompressions, no parse,
    far under the 1 % build-time floor.

    Under the harness's armed shared-repo guard the write is REFUSED and
    named (``SharedRepoWriteBlocked`` is a ``RuntimeError``, not an
    ``OSError``, and nothing here swallows it); the harness's explicit,
    locked, ledgered form is ``build_airport.py <ICAO> --refresh-data
    osm_layers``.  In the app the tile build is the writer of record.

    Returns a :class:`RoadFeedPrecheck` — what it re-derived, and what
    is STILL stale on disk afterwards (the offline residual the caller
    turns into ONE tile-level line).
    """
    lat0, lon0 = int(tile.lat), int(tile.lon)
    try:
        candidates = _v2_road_feed_paths(lat0, lon0)
    except Exception as exc:                      # pragma: no cover
        # The reader is in-tree; if it cannot be imported it cannot run
        # either, so fall back to 17ad's home-tile rule and say so.
        UI.vprint(1, "    * Road-feed schema pre-check degraded to the "
                     "home tile only (", repr(exc), ")")
        candidates = [(lat0, lon0, "airport_small_roads",
                       FNAMES.osm_cached(lat0, lon0, "airport_small_roads"))]
        if not os.path.isfile(candidates[0][3]):
            candidates = [(lat0, lon0, "airport_small_roads", None)]
    derived = []
    still_stale = []
    for tlat, tlon, feed, path in candidates:
        home_small = (tlat == lat0 and tlon == lon0
                      and feed == "airport_small_roads")
        if path is None:
            if not home_small:
                continue                  # lawful absence, never a download
        elif OSM._cached_osm_schema_matches(path, ROAD_CACHE_TAG_SCHEMA):
            continue                      # current: the header read is all
        else:
            UI.vprint(1, "    * Cached", feed, "of tile",
                      f"{tlat:+03d}{tlon:+04d}",
                      "predates tag schema", ROAD_CACHE_TAG_SCHEMA,
                      "- re-deriving it before auto_patch reads it.")
        # A stale HOME big_roads is exactly what the background prefetch
        # is re-downloading right now (it filters on the same predicate).
        # Join it rather than queue behind its cache lock, so the tile
        # makes ONE Overpass round for that file, not two in a row.
        if feed == "big_roads" and tlat == lat0 and tlon == lon0:
            wait_for_background_osm_prefetch()
            if path is not None and OSM._cached_osm_schema_matches(
                    path, ROAD_CACHE_TAG_SCHEMA):
                continue
        if _rederive_road_feed(tlat, tlon, feed):
            derived.append((tlat, tlon, feed))
        # DID IT ACTUALLY COME BACK?  ``_rederive_road_feed`` returns
        # False offline (no extract, the download failed) and both
        # writers deliberately leave the STALE bytes on the disk — a
        # stale corpus beats an absent one — so the reader will refuse
        # this exact file.  Ask the file, not the writer's return value:
        # a writer can report a layer and still not have rewritten the
        # cache.  Only reached for a feed that was NOT current, so a
        # current corpus still costs exactly one header read per feed.
        if path is None:
            path = FNAMES.osm_cached(tlat, tlon, feed)
        if os.path.isfile(path) and not OSM._cached_osm_schema_matches(
                path, ROAD_CACHE_TAG_SCHEMA):
            still_stale.append((tlat, tlon, feed, path))
        if UI.red_flag:
            break
    return RoadFeedPrecheck(derived, still_stale)


def _osm_layer_prefetch_specifications(tile):
    """Every OSM layer this tile build will download besides the airports
    layer, in download order, honouring the same conditions the encoders
    apply (road_level gates; custom coastline/water data replaces the
    Overpass download entirely)."""
    specifications = []
    _road_level, _road_auto = resolved_road_level(tile)
    if _road_level:
        specifications.append(
            ("big_roads", BIG_ROADS_QUERIES, ROADS_TAGS_OF_INTEREST,
             ROAD_NODE_TAGS_OF_INTEREST, ROAD_CACHE_TAG_SCHEMA))
    if _road_level >= 2:
        specifications.append(
            ("small_roads", small_roads_queries(_road_level),
             ROADS_TAGS_OF_INTEREST,
             ROAD_NODE_TAGS_OF_INTEREST, ROAD_CACHE_TAG_SCHEMA))
    # Auto mode's per-airport-inset road fetch uses bbox queries with its
    # own merged cache (``airport_small_roads``) — not a tile-wide layer,
    # so it has no prefetch specification here.
    if not (os.path.isfile(FNAMES.custom_coastline(tile.lat, tile.lon))
            or os.path.isdir(FNAMES.custom_coastline_dir(tile.lat,
                                                         tile.lon))):
        specifications.append(("coastline", COASTLINE_QUERIES, [], [], ""))
    if not (os.path.isfile(FNAMES.custom_water(tile.lat, tile.lon))
            or os.path.isdir(FNAMES.custom_water_dir(tile.lat, tile.lon))):
        specifications.append(
            ("water", WATER_QUERIES, WATER_TAGS_OF_INTEREST, [],
             WATER_CACHE_TAG_SCHEMA))
    return specifications


def osm_layer_warm_specifications(tile):
    """Every OSM layer a build of this tile downloads, airports first.

    Consumed by the parallel-build OSM warmer
    (docs/specs/parallel-tile-builds.md §3.7), which pre-downloads queued
    tiles' caches one Overpass request at a time while earlier tiles
    compute.  Same 5-tuple shape as the prefetch specifications:
    ``(cached_suffix, queries, tags_of_interest, node_tags_of_interest,
    cache_schema)``.
    """
    return [
        ("airports", AIRPORTS_QUERIES, ["all"], [], "")
    ] + _osm_layer_prefetch_specifications(tile)


def _layer_cache_is_current(lat, lon, cached_suffix, cache_schema):
    """True when this OSM layer's cache is on disk AND schema-current.

    The single source for "would this layer download?" — the background
    prefetch filter below and the parallel scheduler's fetch-admission
    predicate (:func:`is_cached`) both ask through here, so the two can
    never drift apart.  Exactly the test
    ``O4_OSM_Utils._OSM_queries_to_OSM_layer_serialized`` applies before
    it recycles a cache: presence plus the ``o4_tag_schema`` marker.
    """
    cache_path = FNAMES.osm_cached(lat, lon, cached_suffix)
    return (os.path.isfile(cache_path)
            and OSM._cached_osm_schema_matches(cache_path, cache_schema))


def is_cached(tile) -> bool:
    """True when this tile's vector step would fetch no OSM layer.

    One of the per-subsystem fetch-admission predicates of
    docs/specs/apron-string-and-scheduling-spec.md §A.2: cheap (an
    ``isfile`` plus a two-line read of each cache's header), never a
    network probe, and conservative — an absent, unreadable or
    wrong-schema cache reads as NOT cached.

    A tile fully covered by locally stored regional extracts also counts
    as cached: its build filters the stored ``.pbf`` files in its own
    process and never reaches Overpass (the same reasoning the parent
    warmer applies).  That check comes second because it is the dearer
    of the two.

    ``tile`` is a configured ``O4_Config_Utils.Tile``.
    """
    try:
        specifications = osm_layer_warm_specifications(tile)
    except Exception:
        return False
    missing = [
        specification[0]
        for specification in specifications
        if not _layer_cache_is_current(
            tile.lat, tile.lon, specification[0], specification[4])
    ]
    if not missing:
        return True
    try:
        import O4_OSM_Extracts as EXTRACTS

        return bool(EXTRACTS.local_extracts_cover(
            (tile.lat, tile.lon, tile.lat + 1, tile.lon + 1)))
    except Exception:
        return False


_osm_prefetch_thread = None


def start_background_osm_prefetch(tile):
    """Download this tile's remaining OSM layer caches in the background.

    Started as soon as the airports layer (the only data the next
    pipeline stages need immediately) has arrived: the road, coastline
    and water layers then download WHILE airport processing and the
    auto-patch builds compute, instead of after them.  Downloads run
    sequentially — one Overpass request at a time — so the prefetch is
    no harder on the servers than the old inline order, just earlier.
    Consumers call wait_for_background_osm_prefetch() and then read the
    cache exactly as before.
    """
    global _osm_prefetch_thread
    wait_for_background_osm_prefetch()  # never two prefetches at once
    specifications = [
        specification
        for specification in _osm_layer_prefetch_specifications(tile)
        if not _layer_cache_is_current(
            tile.lat, tile.lon, specification[0], specification[4])
    ]
    if not specifications:
        return
    UI.vprint(
        1,
        "    * Prefetching OSM data in the background:",
        ", ".join(specification[0] for specification in specifications),
    )

    def download_missing_layer_caches():
        for (cached_suffix, queries, tags_of_interest,
                node_tags_of_interest, cache_schema) in specifications:
            if UI.red_flag:
                return
            # The layer object is discarded: the point is the cache file
            # OSM_queries_to_OSM_layer writes, which the encoder later
            # recycles.
            OSM.OSM_queries_to_OSM_layer(
                queries,
                OSM.OSM_layer(),
                tile.lat,
                tile.lon,
                tags_of_interest,
                cached_suffix=cached_suffix,
                node_tags_of_interest=node_tags_of_interest,
                cache_schema=cache_schema,
            )

    _osm_prefetch_thread = threading.Thread(
        target=download_missing_layer_caches, daemon=True)
    _osm_prefetch_thread.start()


def wait_for_background_osm_prefetch():
    """Block until the background OSM prefetch (if any) has finished.
    Callers that read a layer cache MUST call this first, so they never
    race the prefetch on the same cache file."""
    global _osm_prefetch_thread
    if _osm_prefetch_thread is not None:
        _osm_prefetch_thread.join()
        _osm_prefetch_thread = None


def _refuse_on_broken_proj() -> bool:
    """Report and abort the step when the PROJ runtime failed its self-check.

    A broken PROJ runtime silently degrades a tile (every elevation inset
    fetch fails and the build continues on base DEM only), so the step
    refuses instead — docs/specs/proj-runtime-robustness-spec.md.
    """
    reason = PROJRT.refuse_reason()
    if not reason:
        return False
    UI.lvprint(
        0,
        "ERROR: PROJ runtime is broken — builds are disabled to avoid a "
        "silently degraded tile.",
    )
    UI.lvprint(0, reason)
    UI.exit_message_and_bottom_line("")
    return True


################################################################################
def build_poly_file(tile):
    if UI.is_working:
        return 0
    UI.is_working = 1
    UI.red_flag = 0
    if _refuse_on_broken_proj():
        return 0
    # in case that was forgotten by the user
    tile.iterate = 0
    # update the lat/lon scaling factor in VECT
    VECT.scalx = cos((tile.lat + 0.5) * pi / 180)
    # Let's go !
    UI.logprint(
        "Step 1 for tile lat=", tile.lat, ", lon=", tile.lon, ": starting."
    )
    UI.vprint(
        0,
        "\nStep 1 : Building vector data for tile "
        + FNAMES.short_latlon(tile.lat, tile.lon)
        + " : \n--------\n",
    )
    timer = time.time()

    if not os.path.exists(tile.build_dir):
        os.makedirs(tile.build_dir)
    if not os.path.exists(FNAMES.osm_dir(tile.lat, tile.lon)):
        os.makedirs(FNAMES.osm_dir(tile.lat, tile.lon))

    # Start the coastal bathymetry band fetch in the background when this
    # tile will want it: the network fetch then overlaps the vector and
    # mesh steps instead of serializing in front of the masks step
    # (docs/specs/coastal-bathymetry-spec.md section 3).  A no-op on
    # non-coastal tiles and when the mask settings do not call for it.
    import O4_Bathymetry_Band as BATHYBAND

    BATHYBAND.prefetch_bathymetry_band(tile)

    node_file = FNAMES.input_node_file(tile)
    poly_file = FNAMES.input_poly_file(tile)
    vector_map = VECT.Vector_Map()

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Airports
    try:
        (apt_array, apt_area, patches_area, graded_area) = include_airports(
            vector_map, tile)
    except AUTOPATCH.AutoPatchBuildFailure as auto_patch_failure:
        # THE SILENT TILE-DEATH CLASS, CLOSED (H1; docs/POSTMORTEM-
        # 20260831.md Task C).  An airport that did not produce its patch
        # is FATAL to the tile: continuing would mesh whatever stale
        # patch is on disk and finish with exit 0 — which is exactly what
        # shipped Aug-29 geometry to the owner as the Aug-30 build.  The
        # airport, stage and cause are already on the engine log and on
        # the JSONL protocol (one ``AutoPatchFailed`` event each); step 1
        # reports failure, so the session emits ``BuildDone(ok=False)``
        # and every entry point that checks the step's return value
        # exits nonzero.
        UI.lvprint(0, "ERROR: " + str(auto_patch_failure))
        UI.lvprint(
            0,
            "   The tile build is ABORTED — no mesh is built on a patch "
            "set this build did not write.")
        UI.exit_message_and_bottom_line("")
        return 0
    UI.vprint(
        1, "   Number of edges at this point:", len(vector_map.dico_edges)
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Roads
    include_roads(vector_map, tile, apt_array, apt_area, patches_area)
    if resolved_road_level(tile)[0]:
        UI.vprint(
            1, "   Number of edges at this point:", len(vector_map.dico_edges)
        )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Sea
    include_sea(vector_map, tile, patches_area=patches_area,
                graded_area=graded_area)
    UI.vprint(
        1, "   Number of edges at this point:", len(vector_map.dico_edges)
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Water
    include_water(vector_map, tile, patches_area=patches_area,
                  graded_area=graded_area)
    UI.vprint(
        1, "   Number of edges at this point:", len(vector_map.dico_edges)
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # R18-1: patch faces are cut into SUB-CELLS by the INTERP_ALT
    # geometry encoded after ``include_patches`` seeded them — the
    # banked road ribbons above all, the seawall breaklines too.  Seed
    # each of those sub-cells now that every one of those encoders has
    # run; an unseeded sub-cell keeps the raw DEM inside a patched
    # apron.  Purely additive (see ``seed_interp_alt_subcells``).
    seed_interp_alt_subcells(vector_map)

    # R18-1c: every INTERP_ALT seed must be ENCLOSED by INTERP_ALT edges
    # before the plague ever runs — the last point at which the seeds and
    # the marked edges are both in hand.  Loud refusal, never a silent
    # clip (see :func:`audit_interp_alt_seed_sealing`).
    audit_interp_alt_seed_sealing(vector_map)

    # Buildings
    # include_buildings(vector_map)
    # if UI.red_flag: UI.exit_message_and_bottom_line(); return 0

    # Orthogrid
    UI.vprint(0, "-> Inserting edges related to the orthophotos grid")
    xgrid = set()  # x coordinates of vertical grid lines
    ygrid = set()  # y coordinates of horizontal grid lines
    (til_xul, til_yul) = GEO.wgs84_to_orthogrid(
        tile.lat + 1, tile.lon, tile.mesh_zl
    )
    (til_xlr, til_ylr) = GEO.wgs84_to_orthogrid(
        tile.lat, tile.lon + 1, tile.mesh_zl
    )
    for til_x in range(til_xul + 16, til_xlr + 1, 16):
        pos_x = til_x / (2 ** (tile.mesh_zl - 1)) - 1
        xgrid.add(pos_x * 180 - tile.lon)
        #print("x", pos_x * 180 - tile.lon)
    for til_y in range(til_yul + 16, til_ylr + 1, 16):
        pos_y = 1 - (til_y) / (2 ** (tile.mesh_zl - 1))
        ygrid.add(360 / pi * atan(exp(pi * pos_y)) - 90 - tile.lat)
        #print("y", (360 / pi * atan(exp(pi * pos_y)) - 90 - tile.lat))

    xgrid.add(0)
    xgrid.add(1)
    ygrid.add(0)
    ygrid.add(1)
    xgrid = list(sorted(xgrid))
    ygrid = list(sorted(ygrid))
    eps = 2 ** -5
    ortho_network = geometry.MultiLineString(
        [geometry.LineString([(x, 0.0 - eps), (x, 1.0 + eps)]) for x in xgrid]
        + [geometry.LineString([(0.0 - eps, y), (1.0 + eps, y)]) for y in ygrid]
    )
    # The grid lines overshoot the tile by eps so every line crosses the
    # boundary cleanly — but the overshoot must be CUT OFF before the
    # lines reach the triangulation.  Triangle4XP re-samples every output
    # vertex's altitude itself, clamping the SAMPLE position to the
    # raster extent while clamping the WRITTEN position to the tile: a
    # beyond-tile endpoint therefore lands exactly on the tile edge
    # carrying terrain from up to the raster margin beyond it (0.01 deg
    # for the combined "View"-class bases — SPLP 2026-07-24: 97-264 m
    # spikes and duplicate conflicting vertices along the -13-078 seam,
    # which survived an altitude-attribution fix because the attribution
    # is re-sampled away).  Clipping to the unit square keeps the
    # boundary crossings (endpoints sit exactly on the edge) and leaves
    # no beyond-tile vertex for Triangle4XP to snap.
    ortho_network = VECT.ensure_MultiLineString(
        ortho_network.intersection(geometry.box(0.0, 0.0, 1.0, 1.0))
    )
    # Belt to the clip's suspenders: sample altitudes with tile-clamped
    # coordinates too, so any residual out-of-tile point can never carry
    # a beyond-seam value (no-op for on-boundary points).
    def alt_vec_tile_clamped(way):
        return tile.dem.alt_vec(numpy.clip(way, 0.0, 1.0))

    vector_map.encode_MultiLineString(
        ortho_network, alt_vec_tile_clamped, "DUMMY", check=True,
        skip_cut=True
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0

    # Gluing edges
    UI.vprint(0, "-> Inserting additional boundary edges for gluing")
    segs = 2048
    gluing_network = geometry.MultiLineString(
        [
            geometry.LineString(
                [(x, 0) for x in numpy.arange(0, segs + 1) / segs]
            ),
            geometry.LineString(
                [(x, 1) for x in numpy.arange(0, segs + 1) / segs]
            ),
            geometry.LineString(
                [(0, y) for y in numpy.arange(0, segs + 1) / segs]
            ),
            geometry.LineString(
                [(1, y) for y in numpy.arange(0, segs + 1) / segs]
            ),
        ]
    )
    vector_map.encode_MultiLineString(
        gluing_network, tile.dem.alt_vec, "DUMMY", check=True, skip_cut=True
    )

    if UI.red_flag:
        UI.exit_message_and_bottom_line()
        return 0
    UI.vprint(0, "-> Transcription to the files ", poly_file, "and .node")
    if not vector_map.seeds:
        if tile.dem.alt_dem.max() >= 1:
            vector_map.seeds["SEA"] = [numpy.array([1000, 1000])]
        else:
            vector_map.seeds["SEA"] = [numpy.array([0.5, 0.5])]
    UI.vprint(1, "   Crossing identity (§39 (iv), RULINGS 13cp): "
                 f"{vector_map.split_z_carried} crossing(s) resolved to an "
                 "existing node and took the crossed chain's altitude.")
    vector_map.snap_to_grid(9)
    # §39 (i) THE HAIRLINE WELD (owner RULINGS 2026-09-13bu), at the LAST
    # site every pass's output has arrived: two constrained nodes closer
    # than the weld radius are ONE node to any mesher, and the degenerate
    # segment between them is what Triangle4XP cascades off (KCLT:
    # 481,602 + 723,015 triangles under 0.1 m2 off a 2.7913 mm and a
    # 0.2401 mm constrained WATER segment).
    if vector_map.weld_spacing_m > 0.0:
        vector_map.weld_hairlines(vector_map.weld_spacing_m, tile.lat)
    # THE BANK ANNULUS IS A TRIANGLE REGION WITH A MAXIMUM AREA (owner
    # RULINGS 2026-09-09x).  The blend law
    # (``O4_Mesh_Utils.bank_annulus_blend_values``) is exact but has
    # almost no free vertex to be carried on; sizing the annulus's own
    # region records gives it some.  Derived at the SAME site as the
    # blend, from the same patch ``.osm`` rings, so the two steps can
    # never disagree about where the annulus is.  Purely additive: a seed
    # that gets no area is written exactly as before.
    size_bank_annulus_regions(vector_map, tile)
    vector_map.write_node_file(node_file)
    vector_map.write_poly_file(poly_file)

    UI.vprint(
        1, "\nFinal number of constrained edges :", len(vector_map.dico_edges)
    )
    UI.timings_and_bottom_line(timer)
    UI.logprint(
        "Step 1 for tile lat=", tile.lat, ", lon=", tile.lon, ": normal exit."
    )
    return 1


################################################################################
def load_airports_and_prepare_dem(tile):
    """Airport OSM layer + ``dico_airports`` + the PRODUCTION tile DEM.

    This is the exact prelude the tile build runs before auto-patch
    generation: airports layer load, airport dictionaries, elevation
    insets, tile-wide overlay, DEM construction, inset densification,
    overlay bake, and airport smoothing — ``tile.dem`` afterwards IS the
    DEM every production ``build_airport_pavement`` call receives via
    ``tile_dem``.  Factored out (2026-07-18, user: standalone probes
    must test with the production DEM) so
    ``tools/production_airport_patch.py`` can run single-airport builds
    against the identical surface.  Returns ``(airport_layer,
    dico_airports)``, or ``(None, None)`` when the airports layer
    cannot be loaded."""
    airport_layer = OSM.OSM_layer()
    queries = AIRPORTS_QUERIES
    tags_of_interest = ["all"]
    if not OSM.OSM_queries_to_OSM_layer(
        queries,
        airport_layer,
        tile.lat,
        tile.lon,
        tags_of_interest,
        cached_suffix="airports",
    ):
        return (None, None)
    # The airports layer was the only download the next stages need
    # right away — fetch every other layer this build will read in the
    # background while airport processing / auto-patch builds compute.
    # (The auto-patch road-aware grading reads the big_roads cache at
    # build time, so without this the roads would arrive too late on a
    # freshly built tile.)
    start_background_osm_prefetch(tile)
    dico_airports = build_airports_dico(tile, airport_layer)
    APT.list_airports_and_runways(dico_airports)
    derive_auto_patch_selection(tile)
    UI.vprint(1, "   Loading elevation data and smoothing it over airports.")
    # Airport elevation insets (spec section 3.3): fetch meter-class public
    # elevation for each airport neighbourhood, then augment the DEM source
    # in memory with the cached insets (base;inset1;inset2). No-op -- and a
    # byte-identical build -- when the feature is gated off, no provider
    # covers the tile, or GDAL is unavailable. The user's custom_dem config
    # value is never rewritten.
    INSETS.ensure_insets_for_tile(tile, dico_airports)
    # §D.1: once per COLD neighbour of a class-S airport, and only after
    # an explicit "build adjacent" answer.  Never in the pool child, never
    # without a choice, never under the harness's shared-repo guard.
    if getattr(tile, "boundary_policy", None) == "neighbour":
        for (lat, lon) in getattr(tile, "boundary_neighbours", ()) or ():
            try:
                ensure_tile_frame(lat, lon,
                                  reason="neighbour of %s" % tile_stem(tile))
            except Exception as error:
                UI.lvprint(0, "   Airport insets: tile %+03d%+04d — frame "
                              "warm FAILED (%s: %s); the frame check will "
                              "decide." % (lat, lon, type(error).__name__,
                                           str(error)))
    # Tile-wide elevation detail level (docs/specs/elevation-level-spec.md):
    # fetch the whole-tile overlay for a numeric elevation_level, or the
    # coastline lidar band for "coastline" (dico_airports feeds its
    # approach-visibility ladder). No-op -- and a byte-identical build --
    # on the default "auto".
    ELEVATION_LEVEL.ensure_tile_overlay(tile, dico_airports)
    compose_tile_dem_from_disk(tile, dico_airports)
    return (airport_layer, dico_airports)


################################################################################
#: THE BOUNDARY ANSWER for this PROCESS (spec §C.3).  ``None`` means "not
#: answered" and resolves from the ``auto_patch_boundary`` app setting,
#: whose unattended meaning is SKIP-loudly (owner RULINGS 18c Q5, 18i (3)).
#: ``EngineSession.build`` sets it in the parent and in every worker child
#: (``parallel.py`` carries it beside provider/zoomlevel).
BOUNDARY_POLICY = None


def tile_stem(tile):
    """``"+38-010"`` for a tile object."""
    return "%+03d%+04d" % (int(tile.lat), int(tile.lon))


def set_boundary_policy(policy):
    """Land the user's boundary answer for this process."""
    global BOUNDARY_POLICY
    BOUNDARY_POLICY = policy if policy in ("neighbour", "skip") else None


def resolved_boundary_policy(tile=None):
    """``"neighbour"`` or ``"skip"`` — never ``None``, never a prompt here.

    Order: the answer this run was given (``set_boundary_policy`` / the
    tile object) beats the remembered app setting, which beats SKIP.  The
    ENGINE never blocks waiting for a user: asking is the front end's job
    (``boundary_airports`` + the dialog), and anything that reaches a
    build with no answer is by definition unattended.
    """
    explicit = getattr(tile, "boundary_policy", None) or BOUNDARY_POLICY
    if explicit in ("neighbour", "skip"):
        return explicit
    choice = str(getattr(CFG, "auto_patch_boundary", "Ask") or "Ask")
    if choice == "Build adjacent":
        return "neighbour"
    return "skip"


def tile_frame_is_warm(lat, lon):
    """Is this 1° cell's frame already warm enough not to ask about?

    Cheap and OFFLINE (the preflight must never query): its airports OSM
    layer is cached AND its airport insets are settled under ITS OWN inset
    mode (``INSETS.is_cached``, which is trivially True when that tile's
    mode is ``"None"``).  An already-built neighbour asks nothing.
    """
    try:
        if not os.path.isfile(FNAMES.osm_cached(lat, lon, "airports")):
            return False
        neighbour = CFG.Tile(lat, lon, "")
        neighbour.read_from_config()
        return bool(INSETS.is_cached(neighbour))
    except Exception:
        return False


def ensure_tile_frame(lat, lon, *, reason=""):
    """Warm ONE neighbour tile's frame, in the MAIN process (spec §D.1).

    Exactly the FETCH HALF of that tile's own step 1 — its OSM dir, its
    airports layer, its ``dico_airports`` and ``INSETS.ensure_insets_for_tile``
    under THAT TILE'S OWN inset mode — so when the neighbour's own build
    runs it finds ``is_cached`` True and fetches nothing twice.  The base
    raster is NOT fetched here; ``compose_tile_dem_from_disk`` owns that.

    This is what replaces ``ProductionDem._warm_tile`` (§C.6).  The
    difference that matters is not the code, it is WHERE it runs: in the
    tile's main build process, where ``UI.progress_bar`` and the airport-
    insets task meter already reach the front end as ``StepProgress``.
    Inside the auto-patch pool child, where the old one ran, neither did —
    which is how tile +38-010 spent ~3 h downloading in silence.

    ORDERING WITHOUT A SCHEDULER EDGE (§D.2): two tiles can need each
    other's frame, so a dependency edge could cycle.  Instead this holds a
    per-tile lock on ``<tile>_airport_insets/.frame.lock`` (the ``.lock``
    family the shared-repo guard records as churn, never contamination):
    whoever arrives first fetches, the other waits and then finds the pass
    settled.  On a lock timeout it logs and proceeds — ``frame_state``
    refuses honestly downstream rather than this inventing a verdict.

    Returns True when the tile's frame is warm on return.
    """
    import O4_File_Lock as LOCK

    stem = "%+03d%+04d" % (lat, lon)
    neighbour = CFG.Tile(lat, lon, "")
    neighbour.read_from_config()
    inset_dir = FNAMES.airport_inset_directory(lat, lon)
    os.makedirs(FNAMES.osm_dir(lat, lon), exist_ok=True)
    os.makedirs(inset_dir, exist_ok=True)
    lock_path = os.path.join(inset_dir, ".frame.lock")
    UI.lvprint(0, "   Airport insets: tile %s%s — warming its frame "
                  "(airports layer + its own inset selection)"
               % (stem, (" (%s)" % reason) if reason else ""))
    with LOCK.hold_file_lock(lock_path) as held:
        if not held:
            UI.lvprint(0, "   Airport insets: tile %s — timed out waiting "
                          "for another build's frame lock; continuing and "
                          "letting the frame check decide." % stem)
        layer = OSM.OSM_layer()
        OSM.OSM_queries_to_OSM_layer(AIRPORTS_QUERIES, layer, lat, lon,
                                     ["all"], cached_suffix="airports")
        dico = build_airports_dico(neighbour, layer)
        mode = _SELECTION.resolved_inset_mode(neighbour)
        selected = _SELECTION.inset_keys(dico, mode)
        UI.lvprint(0, "   Airport insets: tile %s: %d selected (insets = %s) "
                      "of %d aerodrome(s)%s"
                   % (stem, len(selected), mode, len(dico),
                      (" — " + ", ".join(sorted(selected)[:8]))
                      if selected else ""))
        # The task meter labels a NEIGHBOUR pass by its tile so the
        # activity view distinguishes it from the home tile's (§D.3).
        INSETS.ensure_insets_for_tile(neighbour, dico)
    return tile_frame_is_warm(lat, lon)


def derive_auto_patch_selection(tile):
    """THE derivation site of the patch set (spec §A.3), once per build.

    Lands ``tile.auto_patch_selection`` — the list of
    :class:`auto_patch.selection.PatchCandidate` every later consumer reads
    instead of re-spelling the mode filter: ``generate_auto_patches``
    (iterates it), :func:`include_patches` (applies exactly its ``"patch"``
    set and refuses a ``boundary_skipped`` airport's stale file), the §C
    boundary check, and the patch∖inset cross-report below.

    Also emits ONE level-0 line per airport that IS patched but is NOT in
    the inset selection (spec §A.6): that airport solves on the base
    raster without meter-class data, which is lawful (it is every
    no-coverage airport today) and must not be mistaken for a cold frame.

    Never fatal: a selector failure leaves the attribute absent and every
    consumer recomputes, i.e. the pre-selector behaviour.
    """
    cifp_path = resolve_cifp_dir_for_tile(tile)
    if not cifp_path:
        tile.auto_patch_selection = []
        return []
    policy = resolved_boundary_policy(tile)
    record = []
    skipper = _SELECTION.boundary_skipper(
        int(tile.lat), int(tile.lon),
        is_cold=lambda cell: not tile_frame_is_warm(*cell),
        reach_m=_SELECTION.ask_reach_m(), record=record)

    def boundary(icao, runways, candidate=None):
        # The decision is RECORDED either way (the skipper appends to
        # ``record``); under "neighbour" nothing is skipped — those tiles
        # are warmed instead, in ``load_airports_and_prepare_dem``.
        reason = skipper(icao, runways, candidate)
        return None if policy == "neighbour" else reason

    try:
        selection = _SELECTION.select_patch_airports(
            tile, cifp_path, resolved_auto_patch_mode(tile),
            manual_icaos=manual_patch_icaos(tile),
            boundary=boundary)
    except Exception as error:
        UI.vprint(1, "   WARNING: auto-patch selection failed (",
                  type(error).__name__, ":", str(error),
                  ") - each consumer will recompute it.")
        return []
    tile.auto_patch_selection = selection
    # The class-S airports' COLD neighbour cells: warmed under
    # "neighbour" (§D), named in the skip line under "skip" (§C.3), and
    # DECLARED to ProductionDem either way so its frame check knows which
    # cells are this build's business and which are class-M far side.
    neighbours = set()
    for (_icao, cls, cold, _crossing_m) in record:
        if cls == "S":
            neighbours.update(cold)
    tile.boundary_policy = policy
    tile.boundary_neighbours = sorted(neighbours)
    if neighbours and policy == "skip":
        UI.lvprint(
            0, "   Auto-patch: %d airport(s) reach into %d tile(s) this "
               "build is not building (%s); their patches are SKIPPED by "
               "your boundary choice."
            % (sum(1 for r in record if r[1] == "S" and r[2]),
               len(neighbours),
               ", ".join("%+03d%+04d" % c for c in sorted(neighbours))))
    inset_mode = _SELECTION.resolved_inset_mode(tile)
    for candidate in selection:
        if candidate.disposition != "patch":
            continue
        if _SELECTION.mode_admits(candidate.icao.upper(), inset_mode):
            continue
        UI.lvprint(
            0, "   Auto-patch: %s is patched but outside the inset "
            "selection (airport lidar insets = %s) — solving on the base "
            "elevation." % (candidate.icao, inset_mode))
    return selection


def manual_patch_icaos(tile):
    """The ICAO prefixes the tile's Patches dir already covers by hand."""
    patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
    out = set()
    if not os.path.isdir(patch_dir):
        return out
    for fname in os.listdir(patch_dir):
        if fname.endswith(".patch.osm") and "_auto.patch.osm" not in fname:
            out.add(fname[:-10].split("_")[0].upper())
        elif os.path.isdir(os.path.join(patch_dir, fname)):
            out.add(fname.upper())
    return out


def resolve_cifp_dir_for_tile(tile):
    """The CIFP directory THIS tile build will read, or ``""``."""
    import O4_Settings_Model as SETTINGS

    # The SAME spelling ``run_auto_patch_generation`` uses — one resolution
    # of the CIFP dir for the engine and both UIs.
    return SETTINGS.resolve_cifp_dir(CFG.cifp_data_path,
                                     CFG.custom_scenery_dir)


################################################################################
def build_airports_dico(tile, airport_layer):
    """The tile build's airport-dictionary chain, exactly as
    ``load_airports_and_prepare_dem`` runs it (discovery, surfaces,
    runway reconstruction, discards, hangar/apron/taxiway areas,
    boundaries).  Factored out (2026-07-19, production-DEM parity v2)
    so the standalone DEM loader in ``auto_patch.elevation`` can build
    the same ``dico_airports`` the production airport smoothing uses.
    Pure compute over the already-loaded layer — no network."""
    dico_airports = {}
    APT.discover_airport_names(airport_layer, dico_airports)
    APT.attach_surfaces_to_airports(airport_layer, dico_airports)
    APT.sort_and_reconstruct_runways(tile, airport_layer, dico_airports)
    APT.discard_unwanted_airports(tile, dico_airports)
    APT.build_hangar_areas(tile, airport_layer, dico_airports)
    APT.build_apron_areas(tile, airport_layer, dico_airports)
    APT.build_taxiway_areas(tile, airport_layer, dico_airports)
    APT.update_airport_boundaries(tile, dico_airports)
    return dico_airports


################################################################################
def compose_tile_dem_from_disk(tile, dico_airports, write_alt_file=True):
    """DEM construction from CACHED disk state: composite assembly,
    densification, tile-overlay bake, airport smoothing + inset bake.

    This is the tail of the production DEM prelude, after the two
    network ``ensure_*`` fetch steps — everything here reads only what
    is already on disk.  Factored out (2026-07-19, owner ruling: "the
    tests have to use the same DEM as production or they're useless")
    so the standalone loader ``auto_patch.elevation._load_airport_dem``
    runs the IDENTICAL code over the cached state instead of a
    replication.  ``write_alt_file=False`` keeps the result in memory
    (tests/probes must not write tile build state).  Sets ``tile.dem``
    and returns it."""
    dem_source = INSETS.assemble_inset_composite_source(
        tile, DEM.drop_missing_pinned_files(tile.custom_dem))
    tile.dem = DEM.DEM(
        tile.lat,
        tile.lon,
        dem_source,
        tile.fill_nodata or "to zero",
        info_only=False,
        elevation_level=getattr(tile, "elevation_level", "auto"),
    )
    # Densify the working grid over inset tiles (spec Phase C1) BEFORE
    # smoothing and baking, so the finer posting carries the meter-class
    # airport relief through to the mesh. No-op (byte-identical) when no
    # inset covers the tile or the feature is gated off.
    INSETS.densify_tile_dem_for_insets(tile)
    # The tile-wide overlay is base terrain: bake it BEFORE the airport
    # smoothing pass (airport insets keep baking last, after smoothing).
    ELEVATION_LEVEL.bake_tile_overlay_into_alt_dem(tile)
    APT.smooth_raster_over_airports(
        tile, dico_airports, write_alt_file=write_alt_file
    )
    return tile.dem


################################################################################
def run_auto_patch_generation(tile, airport_layer, dico_airports):
    """The tile build's auto-patch generation call, exactly as
    ``include_airports`` runs it (mode resolution, CIFP discovery, lazy
    taxiway/building/road providers).  ``tile.dem`` must already be the
    production DEM (:func:`load_airports_and_prepare_dem`).  Factored
    out with it (2026-07-18) for the single-airport production lab loop
    in ``tools/production_airport_patch.py``."""
    # Auto-generate runway, taxiway, and building patches from CIFP data +
    # OSM geometry (before loading patches so include_patches() picks them up)
    # Backward compat: legacy bool True/False configs map to "All"/"None"
    auto_patch_mode = resolved_auto_patch_mode(tile)
    if auto_patch_mode != "None":
        # ONE spelling of "which CIFP folder will this build read" and of
        # the refusal, shared with tools/harness/build_airport.py and with
        # both UIs (``O4_Settings_Model``).  ``autodetect_cifp`` owns the
        # precedence inside it (an AIRAC update in Custom Data/CIFP wins
        # over the stock Resources/default data/CIFP).
        import O4_Settings_Model as SETTINGS
        cifp_path = SETTINGS.resolve_cifp_dir(
            CFG.cifp_data_path, CFG.custom_scenery_dir)
        refusal = SETTINGS.cifp_refusal_reason(
            CFG.cifp_data_path, CFG.custom_scenery_dir, auto_patch_mode)
        if refusal is not None:
            # FATAL, not a warning (beta plan §1 B2).  This used to print
            # a loud banner and carry on: the tile finished with exit 0,
            # a ~20 s vector phase instead of ~400 s, and every runway,
            # taxiway and apron draped over the raw DEM — the same silent
            # tile-death class H1 closed for per-airport failures.  Raised
            # through the EXISTING ``AutoPatchBuildFailure`` path so step 1
            # returns 0, the session emits ``BuildDone(ok=False)`` and the
            # process exits nonzero: no new protocol event.
            raise AUTOPATCH.AutoPatchBuildFailure([{
                "icao": "*", "stage": "config", "error": refusal,
            }])
        # The taxiway/building/road extraction below is passed as
        # zero-arg callables: generate_auto_patches invokes them
        # only when at least one airport actually needs a rebuild.
        # A tile whose auto-patches are all up to date (apt.dat
        # unchanged) skips the parsing — and its log output —
        # entirely.

        # Taxiway centerlines from OSM data for patch generation.
        def _taxiway_provider():
            return OSMAERO.extract_taxiway_info(
                airport_layer, dico_airports, tile
            )

        # Building data: rely solely on aeroway=hangar and
        # aeroway=terminal features that are ALREADY in the
        # per-tile airport_layer cache.  Per user 2026-04-27:
        # the previous per-airport ``way["building"]`` Overpass
        # queries (one per airport, with a 1 km buffer) caused
        # rate-limit cascades and partial failures on tiles
        # with many small airports (e.g. 25+ airports in the
        # Charlotte tile), and the resulting building cache
        # often failed to write entirely.  General building
        # footprints (control towers, fire stations, fuel
        # depots, etc.) catch only edge cases — terminals and
        # hangars dominate the apron-paint cut-outs.  Skipping
        # the extra query trades minor coverage for speed,
        # robustness, and zero rate-limit risk.
        def _building_provider():
            return OSMAERO.extract_building_info(
                airport_layer, dico_airports, tile,
                building_layer=None,
            )

        # Cached big roads for tunnel/road-aware terrain modeling.
        def _road_provider():
            # The background prefetch may still be downloading the
            # roads — wait for it, so a freshly built tile gets its
            # road data instead of silently building without it.
            wait_for_background_osm_prefetch()
            cached_roads = FNAMES.osm_cached(
                tile.lat, tile.lon, "big_roads"
            )
            if not os.path.isfile(cached_roads):
                return None
            road_osm_layer = OSM.OSM_layer()
            road_osm_layer.update_dicosm(
                cached_roads,
                {"n": [], "w": [("highway", ""), ("tunnel", ""),
                                ("bridge", "")], "r": []},
                {"n": [], "w": [("highway", ""), ("tunnel", ""),
                                ("bridge", "")], "r": []},
            )
            return OSMAERO.extract_road_info(
                dico_airports, tile, road_layer=road_osm_layer)

        # EVERY road feed the v2 reader will touch — this tile's and its
        # eight neighbours', both whitelisted feeds — must be schema-
        # current BEFORE it loads them (it refuses a stale/unstamped copy
        # by name, and an app user has no --refresh-data to run).  One
        # bz2 header read per feed when current.
        road_feeds = ensure_auto_patch_road_feeds(tile)
        AUTOPATCH.generate_auto_patches(
            tile, cifp_path,
            taxiway_data=_taxiway_provider,
            building_data=_building_provider,
            dico_airports=dico_airports,
            road_data=_road_provider,
            mode=auto_patch_mode,
            # What the pre-check could NOT refresh (offline, no extract).
            # The driver says it ONCE for the tile instead of letting the
            # v2 reader refuse it inside each airport's worker with a
            # developer --refresh-data command (issue #24).
            stale_road_feeds=road_feeds.stale,
        )


################################################################################
def include_airports(vector_map, tile):
    """``(apt_array, treated_area, patches_area)`` for the tile.

    ``patches_area`` — the patch pavement union alone, WITHOUT the
    apt.dat runway/taxiway/apron area that ``treated_area`` adds — is
    surfaced because it is the LAND authority of the water law
    (``sea_seed_areas``, PATCH_RING_MARKER): pavement that is in our
    patch never takes a sea seed.
    """
    UI.vprint(0, "-> Dealing with airports")
    (airport_layer, dico_airports) = load_airports_and_prepare_dem(tile)
    if airport_layer is None:
        return (0, 0, geometry.Polygon(), geometry.Polygon())
    run_auto_patch_generation(tile, airport_layer, dico_airports)
    (patches_area, patches_list, graded_area) = include_patches(
        vector_map, tile)
    runway_taxiway_apron_area = APT.encode_runways_taxiways_and_aprons(
        tile, airport_layer, dico_airports, vector_map, patches_list,
        patches_area=patches_area,
    )
    treated_area = ops.unary_union([patches_area, runway_taxiway_apron_area])
    APT.encode_hangars(tile, dico_airports, vector_map, patches_list,
                       patches_area=patches_area)
    APT.flatten_helipads(airport_layer, vector_map, tile, treated_area)
    # APT.encode_aprons(tile,dico_airports,vector_map)
    apt_array = APT.build_airport_array(tile, dico_airports)
    return (apt_array, treated_area, patches_area, graded_area)


################################################################################
#: The clamp pass's own measurement, beside the tile it describes.
LEVELLED_ROADS_SIDECAR = "o4_levelled_roads.json"


def road_bridge_deck_pins(tile):
    """``[(polygon, level_m, way_id)]`` — the ROAD BRIDGE DECKS
    auto_patch confirmed for this tile, in the tile-relative
    ``(lon − tile.lon, lat − tile.lat)`` frame.

    RULINGS 2026-08-30c §5, RE-EXPRESSED (redesign spec §4).  The deck's
    value used to be "a PIN in the free-road profile solve"; that pass
    is retired (RULINGS 2026-08-31b) and general roads are the CORE's,
    so the pin is a CLAMPED-STATION OVERRIDE here.  Its function is not
    to move the deck — per 2026-08-30d the deck sits at the road solve's
    own level and the structure beneath holds bore datum — but to make
    the APPROACHES reach it at the road cap, and to let the clamp price
    §6's refusal when the two abutment values cannot both be reached.

    The records are read from the patch sidecars auto_patch already
    writes (``<patch>.axes.json`` → ``road_bridge_decks``).  ONE
    AUTHORITY: nothing here re-derives a deck or its level.
    """
    import json

    pins = []
    try:
        patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
        if not os.path.isdir(patch_dir):
            return pins
        for name in sorted(os.listdir(patch_dir)):
            if not name.endswith(".patch.osm.axes.json"):
                continue
            try:
                with open(os.path.join(patch_dir, name), "r",
                          encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                continue
            for rec in (data.get("road_bridge_decks") or []):
                if rec.get("verdict") != "confirmed_terrain":
                    continue
                level = rec.get("deck_pin_m")
                ring = rec.get("corridor_ll") or []
                if level is None or len(ring) < 4:
                    continue
                try:
                    poly = geometry.Polygon(
                        [(float(lon) - tile.lon, float(lat) - tile.lat)
                         for lat, lon in ring])
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                except (TypeError, ValueError):
                    continue
                if poly.is_empty:
                    continue
                pins.append((poly, float(level), rec.get("way_id")))
    except Exception:                                    # pragma: no cover
        return []
    return pins


def levelled_roads_sidecar_path(build_dir):
    """Path of a tile's levelled-roads sidecar (one spelling, shared with
    ``tools/road_terrain_conformance.py --levelled-roads``)."""
    return os.path.join(build_dir, LEVELLED_ROADS_SIDECAR)


def write_levelled_roads_sidecar(tile, levelled_roads):
    """Publish the clamp's per-way stations beside the tile.

    THE MEASURABILITY CLAUSE (spec §2 item 4; the blindness
    docs/POSTMORTEM-20260831.md names).  Core-owned roads leave no patch
    rows, so a census cannot see them at all and the 2026-08-30 road
    regression shipped under a green one.  This file IS the population:
    every clamped station's lat/lon, the terrain under it and the value
    the road took, which ``tools/road_terrain_conformance.py
    --levelled-roads`` prices as follow-ratio, cut and fill.

    Never fatal: a sidecar that cannot be written costs the tile its
    measurement, not its geometry.
    """
    import json

    build_dir = getattr(tile, "build_dir", None)
    if not build_dir or levelled_roads is None:
        return None
    path = levelled_roads_sidecar_path(build_dir)
    try:
        os.makedirs(build_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(levelled_roads.sidecar(tile.lat, tile.lon), handle)
    except (OSError, TypeError, ValueError) as e:
        UI.vprint(1, "      Could not write", path, ":", e)
        return None
    UI.vprint(2, "      Levelled-roads sidecar written to", path)
    return path


################################################################################
def _way_classes(osm_layer, way_ids):
    """The OSM CLASS of each accepted way, in the geoms' own order
    (spec §2-SUPPLEMENT S.4 row 5): the ``highway`` value, else the
    ``railway`` value prefixed ``railway:``, else ``None`` (which takes
    ``road_grade_limit``, counted loudly).  Never raises: a layer whose
    tags went missing degrades to all-default caps."""
    out = []
    try:
        tags = osm_layer.dicosmtags["w"]
    except (AttributeError, KeyError, TypeError):       # pragma: no cover
        return [None] * len(way_ids)
    for wid in way_ids:
        t = tags.get(wid) or {}
        v = t.get("highway")
        if v:
            out.append(str(v))
            continue
        v = t.get("railway")
        out.append("railway:" + str(v) if v else None)
    return out


def include_roads(vector_map, tile, apt_array, apt_area, patches_area=None):
    """``patches_area`` — the union of every closed patch ring (13be), the
    seed of THE BAND the longitudinal clamp is scoped to (owner RULINGS
    2026-09-18n; spec §2-SUPPLEMENT S.1 (1)).  ``None``/empty = no patch
    was built, so no way is clamped: pure upstream."""
    def road_is_too_much_banked(way, filtered_segs):
        (col, row) = numpy.minimum(
            numpy.maximum(numpy.round(way[0] * 1000), 0), 1000
        )
        if apt_array[int(1000 - row), int(col)]:
            return True
        (col, row) = numpy.minimum(
            numpy.maximum(numpy.round(way[-1] * 1000), 0), 1000
        )
        if apt_array[int(1000 - row), int(col)]:
            return True
        if filtered_segs >= tile.max_levelled_segs:
            return False
        return (
            numpy.abs(
                tile.dem.alt_vec(way)
                - tile.dem.alt_vec(VECT.shift_way(way, tile.lane_width))
            )
            >= tile.road_banking_limit
        ).any()

    #: The tile's clamped centerline stations, published by the clamp
    #: pass below and consulted by ``alt_vec_shift``.  ``None`` until
    #: the pass has run (and when it has nothing to say).
    levelled = {"roads": None}

    def alt_vec_shift(way):
        """The altitude the road ribbon's ring vertices take.

        Historically the shifted DEM: a ring vertex reads the DEM one
        ``lane_width`` INWARD, which lands on the road's own centerline,
        so both kerbs of a ribbon read one value and the road comes out
        LATERALLY LEVEL.  It now asks the LONGITUDINAL CLAMP first — the
        nearest clamped centerline station within ``lane_width x 2`` —
        and falls back to that same shifted DEM beyond, because ground
        the clamp never stationed is ground it may not invent.
        """
        pts = VECT.shift_way(way, tile.lane_width)
        alt = tile.dem.alt_vec(pts)
        roads = levelled["roads"]
        if roads is None:
            return alt
        return roads.answer(pts, alt)

    road_level, road_auto = resolved_road_level(tile)
    # PATCH-AREA MAX DETAIL IS UNCONDITIONAL (owner 2026-08-31; spec §2
    # item 2): the airport-inset level-5 + rail leveling runs whenever
    # auto_patch runs, whatever the user's road_level says.  The knob
    # governs the TILE-WIDE layers only — auto_patch's airports need the
    # detail near the pavement it builds, and a numeric road_level used
    # to silently switch it off.
    patch_area_detail = auto_patch_runs(tile)
    if not road_level and not patch_area_detail:
        return
    UI.vprint(0, "-> Dealing with roads")
    wait_for_background_osm_prefetch()
    tags_of_interest = ROADS_TAGS_OF_INTEREST
    # THE SEAM WITH auto_patch (spec §2 item 3): what auto_patch owns is
    # the TAGGED SPAN — a bridge deck, a tunnel bore.  The exclusion is
    # therefore on an ASSERTED value, not on the key being present:
    # ``bridge=no`` is an ordinary road and levels with the core, as do
    # every span's approaches.
    tags_for_exclusion = set(["bridge", "tunnel"])
    # tags_for_exclusion=set(["tunnel"])
    road_network_banked = geometry.MultiLineString()
    road_network_flat = geometry.MultiLineString()
    #: THE WAY CLASSES, parallel to ``road_network_banked.geoms`` (spec
    #: §2-SUPPLEMENT S.4 row 5): each layer's accepted ids in the geoms'
    #: own order, mapped to the OSM class the per-class cap is read by.
    banked_classes = []
    banked_ids = []
    if road_level:
        road_layer = OSM.OSM_layer()
        if not OSM.OSM_queries_to_OSM_layer(
            BIG_ROADS_QUERIES,
            road_layer,
            tile.lat,
            tile.lon,
            tags_of_interest,
            cached_suffix="big_roads",
            node_tags_of_interest=ROAD_NODE_TAGS_OF_INTEREST,
            cache_schema=ROAD_CACHE_TAG_SCHEMA,
        ):
            return 0
        UI.vprint(1, "    * Checking which large roads need leveling.")
        _ids_1 = []
        (road_network_banked, road_network_flat) = OSM.OSM_to_MultiLineString(
            road_layer,
            tile.lat,
            tile.lon,
            tags_for_exclusion,
            road_is_too_much_banked,
            accepted_ids=_ids_1,
        )
        banked_classes = _way_classes(road_layer, _ids_1)
        banked_ids = list(_ids_1)
    if UI.red_flag:
        return 0
    if road_level >= 2:
        road_layer = OSM.OSM_layer()
        if not OSM.OSM_queries_to_OSM_layer(
            small_roads_queries(road_level),
            road_layer,
            tile.lat,
            tile.lon,
            tags_of_interest,
            cached_suffix="small_roads",
            node_tags_of_interest=ROAD_NODE_TAGS_OF_INTEREST,
            cache_schema=ROAD_CACHE_TAG_SCHEMA,
        ):
            return 0
        UI.vprint(1, "    * Checking which smaller roads need leveling.")
        timer = time.time()
        _ids_2 = []
        (
            road_network_banked_2,
            road_network_flat_2,
        ) = OSM.OSM_to_MultiLineString(
            road_layer,
            tile.lat,
            tile.lon,
            tags_for_exclusion,
            road_is_too_much_banked,
            accepted_ids=_ids_2,
        )
        UI.vprint(3, "Time for check :", time.time() - timer)
        road_network_banked = geometry.MultiLineString(
            list(road_network_banked.geoms) + list(road_network_banked_2.geoms)
        )
        banked_classes += _way_classes(road_layer, _ids_2)
        banked_ids += list(_ids_2)
    if road_auto or patch_area_detail:
        # AUTO MODE (owner ruling 2026-07-27): level-5 roads + airport
        # rail classes, fetched ONLY inside each airport's elevation-
        # inset bounding box (bbox Overpass queries, one merged per-tile
        # cache), then levelled through the identical banked-check +
        # buffer + INTERP_ALT encoding as every other road.  The
        # existing ``apt_area`` subtraction below still keeps them out
        # of the flattened airport polygons themselves — auto_patch
        # owns that ground.
        #
        # UNCONDITIONAL WHENEVER auto_patch RUNS (owner 2026-08-31, spec
        # §2 item 2): this pass is not the "auto" road MODE's private
        # feature, it is the detail auto_patch's airports need under
        # them.  A numeric user road_level scopes the TILE-WIDE layers
        # above and no longer switches this off.
        auto_layer = _airport_auto_roads_layer(tile)
        if auto_layer is not None:
            UI.vprint(1, "    * Checking which airport-area roads need "
                         "leveling (auto road mode).")
            _ids_3 = []
            (road_network_banked_3, _flat_3) = OSM.OSM_to_MultiLineString(
                auto_layer,
                tile.lat,
                tile.lon,
                tags_for_exclusion,
                road_is_too_much_banked,
                accepted_ids=_ids_3,
            )
            if not road_network_banked_3.is_empty:
                road_network_banked = geometry.MultiLineString(
                    list(road_network_banked.geoms)
                    + list(road_network_banked_3.geoms)
                )
                banked_classes += _way_classes(auto_layer, _ids_3)
                banked_ids += list(_ids_3)
    if not road_network_banked.is_empty:
        # ── THE LONGITUDINAL CLAMP (spec §2 item 1) ──────────────────
        # PER WAY, ON THE CENTERLINE, BEFORE THE BUFFER (census #110/
        # #111 option i).  It must run here and not on ``road_area``:
        # the buffered ring is one merged multipolygon whose vertices
        # walk up one kerb and back down the other and then jump to an
        # unrelated road, so a profile law run in that order would read
        # a 8 m-wide carriageway as an 8 m-long climb and would fuse
        # roads that merely share a ring.  A way's profile is its own.
        UI.vprint(1, "    * Clamping road profiles to the grade limit.")
        timer = time.time()
        # THE BRIDGE-DECK PINS (spec §4): auto_patch has already run
        # (``include_airports`` above), so the decks it confirmed this
        # build are on disk beside its patches.
        _deck_pins = road_bridge_deck_pins(tile)
        # ── THE BAND (spec §2-SUPPLEMENT S.1 (1)) ────────────────────
        # ``patches_area`` (the union of every closed patch ring, 13be —
        # NOT ``apt_area``, which also carries apt.dat pavement of
        # airports no patch was built for) ∪ the road bridge decks, at
        # the SAME ``lane_width + 2`` offset the ribbon is differenced by
        # below: "in the band" = "where the core has no ribbon and the
        # patch is the authority".  No patch ⇒ an EMPTY band ⇒ NO way is
        # clamped, which is 18n's "normal engine road processing".
        _band_seed = [patches_area] if patches_area is not None else []
        _band_seed += [p for (p, _lvl, _w) in _deck_pins
                       if p is not None and not p.is_empty]
        _band_seed = [p for p in _band_seed if p is not None and not p.is_empty]
        _band = (VECT.improved_buffer(ops.unary_union(_band_seed),
                                      tile.lane_width + 2, 0, 0)
                 if _band_seed else geometry.Polygon())
        _law = _road_neighbourhood_law()
        levelled["roads"] = VECT.clamp_road_network(
            road_network_banked,
            tile.dem.alt_vec,
            getattr(tile, "road_grade_limit", ROAD_GRADE_CAP_DEFAULT),
            tile.lane_width,
            deck_pins=_deck_pins,
            coverage=_band,
            way_classes=banked_classes or None,
            way_ids=banked_ids or None,
            runout_m=_law["runout_m"],
            budget_m=_law["budget_m"],
            cap_ceiling=_law["cap_ceiling"],
            class_caps=_law["class_caps"],
        )
        _clamp_report = levelled["roads"].summary()
        UI.vprint(3, "Time for road profile clamp:", time.time() - timer)
        UI.vprint(
            1,
            "      %d ways, %d stations, %d clamped (max lift %.2f m, "
            "max cut %.2f m)." % (
                _clamp_report["ways"], _clamp_report["stations"],
                _clamp_report["clamped_stations"],
                _clamp_report["max_lift_m"], _clamp_report["max_cut_m"]),
        )
        # ── THE ONE LOUD LINE (spec §2-SUPPLEMENT S.3; no gate, no
        # verify family): who was in the neighbourhood, which runs
        # yielded and how far the worst one stands off the terrain.
        _lr = levelled["roads"]
        _worst_run = max(
            ((r.get("max_offset_m", 0.0), r.get("cap_eff"), w.get("class"),
              w.get("layer_way_id"))
             for w in _lr.ways for r in w.get("runs", ())),
            default=(0.0, None, None, None))
        _yield_worst = max(
            ((r.get("cap_eff") or 0.0, w.get("class"), w.get("layer_way_id"))
             for w in _lr.ways for r in w.get("runs", ())
             if r.get("yielded")), default=(None, None, None))
        _unclassed = sum(1 for w in _lr.ways
                         if w.get("scope") == "neighbourhood"
                         and not w.get("class"))
        UI.vprint(
            1,
            "      %d way(s) in the patch neighbourhood, %d run(s), "
            "%d yielded (worst cap_eff %s on way %s, class %s), %d at the "
            "%.0f %% ceiling, max offset %.2f m; %d unclassed way(s) at "
            "road_grade_limit." % (
                _clamp_report["neighbourhood_ways"], _clamp_report["runs"],
                _clamp_report["yielded_runs"],
                ("%.1f %%" % (100.0 * _yield_worst[0]))
                if _yield_worst[0] else "-",
                _yield_worst[2], _yield_worst[1],
                _clamp_report["ceiling_runs"],
                100.0 * _law["cap_ceiling"], _worst_run[0], _unclassed),
        )
        if _deck_pins:
            UI.vprint(
                1,
                "      %d road bridge deck(s): %d station(s) on %d way(s) "
                "PINNED at deck level, %d span(s) REFUSED (§6; worst "
                "infeasibility %.2f m)." % (
                    len(_deck_pins),
                    _clamp_report["deck_pinned_stations"],
                    _clamp_report["deck_pinned_ways"],
                    _clamp_report["deck_pins_refused"],
                    _clamp_report["deck_pin_worst_infeasibility_m"]),
            )
        write_levelled_roads_sidecar(tile, levelled["roads"])
        if UI.red_flag:
            return 0
        UI.vprint(1, "    * Buffering banked road network as multipolygon.")
        timer = time.time()
        road_area = VECT.improved_buffer(
            road_network_banked.difference(
                VECT.improved_buffer(apt_area, tile.lane_width + 2, 0, 0)
            ),
            tile.lane_width,
            2,
            0.5,
            show_progress=True,
        )
        UI.vprint(3, "Time for improved buffering:", time.time() - timer)
        if UI.red_flag:
            return 0
        UI.vprint(1, "      Encoding it.")
        # NOTE the two granularities (census #112, ruled by spec §2.4).
        # The CLAMP stations are <= 20 m — fine enough for the
        # instrument to outresolve emit_decimate's 60 m chords — while
        # ``refine=100`` still samples the ring's authored altitudes
        # every <= 100 m, so what EMITS is a subsample of the clamped
        # profile.  The spec rules the station spacing only; changing
        # ``refine`` changes the mesh's vertex count tile-wide and is
        # not this batch's to make.
        vector_map.encode_MultiPolygon(
            road_area, alt_vec_shift, "INTERP_ALT", check=True, refine=100
        )
        if UI.red_flag:
            return 0
    # Hack (23/02/2024 : seems better without actually, keep it just in case)
    if False and not road_network_flat.is_empty:
        road_network_flat = road_network_flat.difference(road_network_banked)
        road_network_flat = road_network_flat.difference(
            VECT.improved_buffer(apt_area, 15, 0, 0)
        ).simplify(0.00001)
        UI.vprint(
            1,
            "    * Encoding the remaining primary road network as linestrings.",
        )
        vector_map.encode_MultiLineString(
            road_network_flat, tile.dem.alt_vec, "DUMMY", check=True
        )
    return 1


################################################################################
def _tidal_water_area(tile):
    """Union of the tile's tidal / lagoon water polygons (tile-relative).

    Loads the same water layer the water encoder uses — the cached
    Overpass download (a cache hit after the prefetch) or the user's
    custom water files — and polygonizes just the polygons matching
    :func:`water_polygon_is_tidal`.  Returns an empty MultiPolygon on
    any failure: the sea-seed subtraction is an override, never a
    dependency the coastline step can fail on.
    """
    try:
        water_layer = OSM.OSM_layer()
        custom_water = FNAMES.custom_water(tile.lat, tile.lon)
        custom_water_dir = FNAMES.custom_water_dir(tile.lat, tile.lon)
        if os.path.isfile(custom_water):
            water_layer.update_dicosm(
                custom_water, input_tags=None, target_tags=None
            )
        elif os.path.isdir(custom_water_dir):
            for osm_file in os.listdir(custom_water_dir):
                water_layer.update_dicosm(
                    os.path.join(custom_water_dir, osm_file),
                    input_tags=None,
                    target_tags=None,
                )
        elif not OSM.OSM_queries_to_OSM_layer(
            WATER_QUERIES,
            water_layer,
            tile.lat,
            tile.lon,
            WATER_TAGS_OF_INTEREST,
            cached_suffix="water",
            cache_schema=WATER_CACHE_TAG_SCHEMA,
        ):
            return geometry.MultiPolygon()
        (_area, tidal_area) = OSM.OSM_to_MultiPolygon(
            water_layer,
            tile.lat,
            tile.lon,
            lambda pol, osmid, dicosmtags: water_polygon_is_tidal(
                osmid, dicosmtags
            ),
        )
        return tidal_area
    except Exception:
        return geometry.MultiPolygon()


def sea_area_from_coastline(coastline, lat, lon, custom_source=False):
    """THE SEA, out of a coastline MultiLineString (tile-relative).

    The topology reconstruction ``include_sea`` has always done, factored
    out so the SEA/LAND partition has exactly ONE implementation in the
    tree.  R21's land-connected continuity asks the same question in DEM
    prep — which ground is land — and a second derivation there would be
    two instruments over one population: the ground that grades flat and
    the ground that counts as land must never be two different polygons
    (the lesson the retired declared corridor was written around).

    Closed rings are set aside first because ``linemerge`` is expensive;
    the open remainder is cut to the tile and merged, and
    ``VECT.coastline_to_MultiPolygon`` closes the result against the tile
    frame.  Returns a (possibly empty) MultiPolygon.
    """
    loops = geometry.MultiLineString(
        [line for line in coastline.geoms if line.is_ring]
    )
    remainder = VECT.ensure_MultiLineString(
        VECT.cut_to_tile(
            geometry.MultiLineString(
                [line for line in coastline.geoms if not line.is_ring]
            ),
            strictly_inside=True,
        )
    )
    UI.vprint(3, "Linemerge...")
    if not remainder.is_empty:
        remainder = VECT.ensure_MultiLineString(ops.linemerge(remainder))
    UI.vprint(3, "...done.")
    closed = geometry.MultiLineString(
        list(remainder.geoms) + list(loops.geoms)
    )
    return VECT.ensure_MultiPolygon(
        VECT.coastline_to_MultiPolygon(closed, lat, lon, custom_source)
    )


def cached_coastline_multilinestring(tile):
    """The tile's coastline from data ALREADY ON DISK — never a download.

    R21: DEM prep (``overlay_flat_site_insets``) needs the land/sea
    partition BEFORE ``include_sea`` runs, and a fetch there would be an
    implicit download into the shared data repo — the exact class the
    harness guard refuses.  So this reads the user's custom coastline
    when there is one and the layer cache when it is present, and answers
    ``(None, False)`` otherwise: no cache, no continuity claim, said out
    loud by the caller rather than silently downloaded.

    Returns ``(coastline, custom_source)``.
    """
    custom_coastline = FNAMES.custom_coastline(tile.lat, tile.lon)
    custom_coastline_dir = FNAMES.custom_coastline_dir(tile.lat, tile.lon)
    sea_layer = OSM.OSM_layer()
    custom_source = False
    if os.path.isfile(custom_coastline):
        sea_layer.update_dicosm(custom_coastline, input_tags=None,
                                target_tags=None)
        custom_source = True
    elif os.path.isdir(custom_coastline_dir):
        # READ ONLY: ``include_sea``'s merge of this directory writes the
        # merged file; this reader never writes anything.
        for osm_file in sorted(os.listdir(custom_coastline_dir)):
            sea_layer.update_dicosm(
                os.path.join(custom_coastline_dir, osm_file),
                input_tags=None, target_tags=None)
        custom_source = True
    else:
        cached = FNAMES.osm_cached(tile.lat, tile.lon, "coastline")
        if not os.path.isfile(cached):
            return (None, False)
        try:
            if not OSM._cached_osm_schema_matches(cached, ""):
                # A stale-schema cache would make the normal reader
                # RE-DOWNLOAD; here that is exactly what must not happen.
                return (None, False)
        except Exception:                                  # pragma: no cover
            return (None, False)
        if not OSM.OSM_queries_to_OSM_layer(
                COASTLINE_QUERIES, sea_layer, tile.lat, tile.lon, [],
                cached_suffix="coastline"):
            return (None, False)
    try:
        coastline = OSM.OSM_to_MultiLineString(sea_layer, tile.lat, tile.lon)
    except Exception:                                      # pragma: no cover
        return (None, False)
    if coastline is None or coastline.is_empty:
        return (None, custom_source)
    return (coastline, custom_source)


def cached_water_multipolygon(tile):
    """The tile's INLAND WATER polygons from data ALREADY ON DISK.

    WATER IS A DATUM (RULINGS 2026-09-09m/09o).  The flat-site inset cut
    (``auto_patch.flat_site_mode.water_cutout``) and the v2 production
    frame's water witness (``auto_patch_v2.airport.dem_production``) both
    need "where is water on this tile" BEFORE the vector map is built,
    and a second derivation of that question would put DEM prep, the
    solve and the mesh's own masks on different populations — the census
    lesson this repo keeps re-learning.  So this is the ONE reader, and
    it reads exactly what ``include_water`` reads: ``WATER_QUERIES`` over
    the ``water`` layer with ``WATER_TAGS_OF_INTEREST`` /
    ``WATER_CACHE_TAG_SCHEMA``, or the user's custom water files.

    CACHE ONLY, never a download (``cached_coastline_multilinestring``'s
    reason, verbatim: a fetch inside DEM prep is the implicit-download
    class the harness guard refuses).  ``None`` — never an empty polygon
    — when nothing is on disk: "no data" and "no water" are different
    answers.
    """
    custom_water = FNAMES.custom_water(tile.lat, tile.lon)
    custom_water_dir = FNAMES.custom_water_dir(tile.lat, tile.lon)
    water_layer = OSM.OSM_layer()
    if os.path.isfile(custom_water):
        water_layer.update_dicosm(custom_water, input_tags=None,
                                  target_tags=None)
    elif os.path.isdir(custom_water_dir):
        for osm_file in sorted(os.listdir(custom_water_dir)):
            water_layer.update_dicosm(
                os.path.join(custom_water_dir, osm_file),
                input_tags=None, target_tags=None)
    else:
        cached = FNAMES.osm_cached(tile.lat, tile.lon, "water")
        if not os.path.isfile(cached):
            return None
        try:
            if not OSM._cached_osm_schema_matches(cached,
                                                  WATER_CACHE_TAG_SCHEMA):
                return None
        except Exception:                                  # pragma: no cover
            return None
        if not OSM.OSM_queries_to_OSM_layer(
                WATER_QUERIES, water_layer, tile.lat, tile.lon,
                WATER_TAGS_OF_INTEREST, cached_suffix="water",
                cache_schema=WATER_CACHE_TAG_SCHEMA):
            return None
    try:
        (area, _tidal) = OSM.OSM_to_MultiPolygon(
            water_layer, tile.lat, tile.lon,
            lambda pol, osmid, dicosmtags: water_polygon_is_tidal(
                osmid, dicosmtags))
    except Exception:                                      # pragma: no cover
        return None
    return VECT.ensure_MultiPolygon(area)


def cached_tile_water(tile):
    """``(sea, inland)`` for this tile from cached data, tile-relative.

    ``sea`` is the coastline partition's own answer
    (:func:`sea_area_from_coastline` — the tree's single SEA/LAND
    implementation); ``inland`` is :func:`cached_water_multipolygon`.
    Either may be ``None`` (no data on disk).  Memoised on the tile: one
    read per build, shared by DEM prep and the v2 frame.
    """
    cached = getattr(tile, "_water_datum_layers", "unset")
    if cached != "unset":
        return cached
    sea = None
    coastline, custom_source = cached_coastline_multilinestring(tile)
    if coastline is not None:
        try:
            sea = sea_area_from_coastline(
                coastline, tile.lat, tile.lon, custom_source)
        except Exception:                                  # pragma: no cover
            sea = None
    inland = cached_water_multipolygon(tile)
    out = (sea, inland)
    try:
        tile._water_datum_layers = out
    except Exception:                                      # pragma: no cover
        pass
    return out


def cached_constrained_shore(tile):
    """§39 (i) THE ONE WITNESS (owner RULINGS 2026-09-13cg) — the SHORE
    GEOMETRY THE MESH WILL ACTUALLY CONSTRAIN, from cached data only.

    ``cached_tile_water`` answers "where is water" as POLYGONS, and its
    sea limb is :func:`sea_area_from_coastline`'s polygonisation.  That is
    the right witness for a point sample (is this vertex wet?) and the
    WRONG one for a hairline: the mesh does not constrain that polygon.
    :func:`include_sea` encodes ``cut_to_tile(coastline,
    strictly_inside=True)`` — the RAW coastline lines — under ``SEA``, and
    :func:`include_water` encodes :func:`cached_water_multipolygon`'s own
    rings under ``WATER`` (``water_simplification`` defaults to 0, so
    verbatim).  The two sea derivations differ by micrometres, and
    micrometres are exactly what §39 is about: VMMC's emit-side weld,
    reading the polygon, left a ``bank_foot`` vertex 0.0025 mm from the
    SEA line the mesh constrained (13cg), slenderness 4,004,066.

    So THIS is the derivation site the emitter's ``shore_edges`` and the
    mesh's own ``.poly`` both read, and there is no second one.

    Returns a list of ``(N, 2)`` float arrays in TILE-RELATIVE degrees
    (``lon - tile.lon``, ``lat - tile.lat``), open chains and closed rings
    alike.  Empty when nothing is cached — "no data" is not "no water",
    and the caller says so.  Memoised on the tile.
    """
    cached = getattr(tile, "_constrained_shore", "unset")
    if cached != "unset":
        return cached
    out = []

    def _add(geom):
        if geom is None or getattr(geom, "is_empty", True):
            return
        parts = getattr(geom, "geoms", None)
        if parts is not None:
            for g in parts:
                _add(g)
            return
        if geom.geom_type == "Polygon":
            _add(geom.exterior)
            for ring in geom.interiors:
                _add(ring)
            return
        try:
            coords = numpy.asarray(geom.coords, dtype=float)
        except (AttributeError, ValueError):
            return
        if len(coords) >= 2:
            out.append(coords)

    coastline, _custom = cached_coastline_multilinestring(tile)
    if coastline is not None and not coastline.is_empty:
        try:
            _add(VECT.cut_to_tile(coastline, strictly_inside=True))
        except Exception:                                  # pragma: no cover
            pass
    try:
        _add(cached_water_multipolygon(tile))
    except Exception:                                      # pragma: no cover
        pass
    try:
        tile._constrained_shore = out
    except Exception:                                      # pragma: no cover
        pass
    return out


def cached_tile_land_area(tile):
    """THE TILE'S LAND from already-cached coastline data, tile-relative.

    ``tile frame minus sea``.  ``None`` — never an empty polygon — when
    no coastline data is on disk, because "no data" and "no land" are
    different answers and the continuity law must refuse the first.
    A tile with coastline data but no sea (an inland tile whose cache
    holds nothing) answers the whole frame, which is one land component
    touching the frame: not an island, so nothing is flattened.

    Memoised on the tile: one read per build.
    """
    cached = getattr(tile, "_r21_land_area", "unset")
    if cached != "unset":
        return cached
    coastline, custom_source = cached_coastline_multilinestring(tile)
    land = None
    if coastline is not None:
        try:
            sea = sea_area_from_coastline(
                coastline, tile.lat, tile.lon, custom_source)
            land = VECT.ensure_MultiPolygon(
                geometry.box(0, 0, 1, 1).difference(sea))
        except Exception:                                  # pragma: no cover
            land = None
    try:
        tile._r21_land_area = land
    except Exception:                                      # pragma: no cover
        pass
    return land


def include_sea(vector_map, tile, patches_area=None, graded_area=None):
    """Encode the coastline and seed the SEA attribute.

    ``patches_area`` is the patch pavement union from
    ``include_patches`` (via ``include_airports``); it joins the tidal
    water polygons as a seed subtractor, so no SEA seed is ever planted
    inside pavement we levelled (see ``sea_seed_areas``).
    """
    UI.vprint(0, "-> Dealing with coastline")
    wait_for_background_osm_prefetch()
    sea_layer = OSM.OSM_layer()
    custom_source = False
    custom_coastline = FNAMES.custom_coastline(tile.lat, tile.lon)
    custom_coastline_dir = FNAMES.custom_coastline_dir(tile.lat, tile.lon)
    if os.path.isfile(custom_coastline):
        UI.vprint(1, "    * User defined custom coastline data detected.")
        sea_layer.update_dicosm(
            custom_coastline, input_tags=None, target_tags=None
        )
        custom_source = True
    elif os.path.isdir(custom_coastline_dir):
        UI.vprint(
            1,
            "    * User defined custom coastline data detected ",
            "(multiple files).",
        )
        for osm_file in os.listdir(custom_coastline_dir):
            UI.vprint(2, "      ", osm_file)
            sea_layer.update_dicosm(
                os.path.join(custom_coastline_dir, osm_file),
                input_tags=None,
                target_tags=None,
            )
            sea_layer.write_to_file(custom_coastline)
        custom_source = True
    else:
        if not OSM.OSM_queries_to_OSM_layer(
            COASTLINE_QUERIES,
            sea_layer,
            tile.lat,
            tile.lon,
            [],
            cached_suffix="coastline",
        ):
            return 0
    coastline = OSM.OSM_to_MultiLineString(sea_layer, tile.lat, tile.lon)
    if not coastline.is_empty:
        # 1) encoding the coastline
        UI.vprint(1, "    * Encoding coastline.")
        vector_map.encode_MultiLineString(
            VECT.cut_to_tile(coastline, strictly_inside=True),
            tile.dem.alt_vec,
            "SEA",
            check=True,
            refine=False,
        )
        UI.vprint(3, "...done.")
        # 2) finding seeds (transform multilinestring coastline to polygon
        # coastline linemerge being expensive we first set aside what is
        # already known to be closed loops
        UI.vprint(1, "    * Reconstructing its topology.")
        sea_area = sea_area_from_coastline(
            coastline, tile.lat, tile.lon, custom_source
        )
        if sea_area.geoms:
            UI.vprint(
                1, "      Found ", len(sea_area.geoms), "contiguous patch(es)."
            )
        tidal_water = _tidal_water_area(tile)
        if not tidal_water.is_empty:
            UI.vprint(
                1,
                "      Tidal / lagoon water polygons override the"
                " coastline: keeping their interiors inland.",
            )
        if patches_area is not None and not patches_area.is_empty:
            UI.vprint(
                1,
                "      Patch pavement is land: withholding sea seeds"
                " inside it.",
            )
        seed_area = sea_seed_areas(
            sea_area, tidal_water, patch_pavement_area=patches_area
        )
        for polygon in seed_area.geoms:
            seed = numpy.array(polygon.representative_point().coords[0])
            if "SEA" in vector_map.seeds:
                vector_map.seeds["SEA"].append(seed)
            else:
                vector_map.seeds["SEA"] = [seed]
        # Seawall along the pavement/sea edge (see SEAWALL_MARKER).  The
        # cutter is ``seed_area``, not the raw ``sea_area``: it is exactly
        # where the SEA attribute will live, so it is exactly where the
        # mesh will be levelled to zero — a tidal lagoon, whose seeds are
        # deliberately withheld, keeps its inland treatment and gets its
        # wall from the inland limb in ``include_water`` instead.  The
        # pavement subtraction inside ``seed_area`` costs nothing here:
        # the wall lies 0.5 m OUTSIDE the pavement.
        # R17b-2: the wall also stands on the COASTLINE wherever the
        # coastline runs inside the flat site's constant inset (the
        # reclaimed island, its claimed-object clusters and the declared
        # corridor).  One admission union, one wall law — the offset and
        # the breakline idiom are untouched.
        admission = seawall_admission_area(patches_area, graded_area)
        # R17c-3: SCOPED to the airport's island — the graded coverage is
        # what says which land inside a flat-site rectangle is the
        # airport's, so it is threaded in rather than the whole box
        # admitted (the mainland/other-island scope the owner refused).
        coastal = coastline_wall_admission(
            tile, sea_area, graded_area=seawall_admission_area(
                patches_area, graded_area))
        if not coastal.is_empty:
            try:
                admission = (coastal if admission is None
                             or getattr(admission, "is_empty", True)
                             else ops.unary_union([admission, coastal]))
                UI.vprint(
                    1,
                    "      R17b-2/R17c-3: the AIRPORT ISLAND's constant-inset "
                    "coastline joins the wall admission set ({:.2f} km2 of "
                    "island land).".format(
                        coastal.area * GEO.lat_to_m
                        * GEO.lon_to_m(tile.lat + 0.5) / 1e6),
                )
            except Exception:
                UI.vprint(1, "      R17b-2 coastline admission union "
                             "failed — the wall keeps its patch admission.")
        insert_seawalls(vector_map, tile, admission, seed_area)


################################################################################
def include_water(vector_map, tile, patches_area=None, graded_area=None):
    """Encode the tile's inland water.

    ``patches_area`` is the patch pavement union from
    ``include_patches`` (via ``include_airports``), threaded here for the
    inland limb of the seawall (see ``SEAWALL_MARKER``): a patch ring
    that borders a lake, a river or a dock gets the same outward
    breakline the coastline limb gets in ``include_sea``, at the level
    the water rings themselves are draped on.
    """
    large_lake_threshold = (
        tile.max_area * 1e6 / (GEO.lat_to_m * GEO.lon_to_m(tile.lat + 0.5))
    )

    def filter_large_lakes(pol, osmid, dicosmtags):
        if pol.area < large_lake_threshold:
            return False
        area = int(pol.area * GEO.lat_to_m * GEO.lon_to_m(tile.lat + 0.5) / 1e6)
        if (osmid in dicosmtags) and ("name" in dicosmtags[osmid]):
            if dicosmtags[osmid]["name"] in good_imagery_list:
                UI.vprint(
                    1,
                    "      * ",
                    dicosmtags[osmid]["name"],
                    "kept will complete imagery although it is",
                    area,
                    "km^2.",
                )
                return False
            else:
                UI.vprint(
                    1,
                    "      * ",
                    dicosmtags[osmid]["name"],
                    "will be masked like the sea due to its large area of",
                    area,
                    "km^2.",
                )
                return True
        else:
            pt = (
                pol.exterior.coords[0]
                if "Multi" not in pol.geom_type
                else pol.geoms[0].exterior.coords[0]
            )
            UI.vprint(
                1,
                "      * ",
                "Some large OSM water patch close to lat=",
                "{:.2f}".format(pt[1] + tile.lon),
                "lon=",
                "{:.2f}".format(pt[0] + tile.lat),
                "will be masked due to its large area of",
                area,
                "km^2.",
            )
            return True

    UI.vprint(0, "-> Dealing with inland water")
    wait_for_background_osm_prefetch()
    water_layer = OSM.OSM_layer()
    custom_water = FNAMES.custom_water(tile.lat, tile.lon)
    custom_water_dir = FNAMES.custom_water_dir(tile.lat, tile.lon)
    if os.path.isfile(custom_water):
        UI.vprint(1, "    * User defined custom water data detected.")
        water_layer.update_dicosm(
            custom_water, input_tags=None, target_tags=None
        )
    elif os.path.isdir(custom_water_dir):
        UI.vprint(
            1, "    * User defined custom water data detected (multiple files)."
        )
        for osm_file in os.listdir(custom_water_dir):
            UI.vprint(2, "      ", osm_file)
            water_layer.update_dicosm(
                os.path.join(custom_water_dir, osm_file),
                input_tags=None,
                target_tags=None,
            )
            water_layer.write_to_file(custom_water)
    else:
        if not OSM.OSM_queries_to_OSM_layer(
            WATER_QUERIES,
            water_layer,
            tile.lat,
            tile.lon,
            WATER_TAGS_OF_INTEREST,
            cached_suffix="water",
            cache_schema=WATER_CACHE_TAG_SCHEMA,
        ):
            return 0
    # Airport-inset water supplement — RETIRED (owner ruling 2026-07-26).
    # The hydro-flat basin scan (O4_Airport_Elevation_Insets.
    # ensure_inset_water_supplement) re-read every cached lidar inset in
    # the tile whenever any one raster changed (~11 min on +35-081 for
    # 658 farm ponds) and never fixed the KBNA case it was built for.
    # Water comes from OpenStreetMap / custom data only; the
    # ``airport_inset_water`` cfg var is retired and ignored here
    # regardless of its saved value.
    UI.vprint(1, "    * Building water multipolygon.")
    (water_area, sea_equiv_area) = OSM.OSM_to_MultiPolygon(
        water_layer, tile.lat, tile.lon, filter_large_lakes
    )
    if not water_area.is_empty:
        UI.vprint(1, "      Cleaning it.")
        try:
            (idx_water, dico_water) = VECT.MultiPolygon_to_Indexed_Polygons(
                water_area, merge_overlappings=tile.clean_bad_geometries
            )
        except:
            return 0
        UI.vprint(
            2, "      Number of water Multipolygons : " + str(len(dico_water))
        )
        UI.vprint(1, "      Encoding it.")
        vector_map.encode_MultiPolygon(
            dico_water,
            tile.dem.alt_vec,
            "WATER",
            area_limit=tile.min_area / 10000,
            simplify=tile.water_simplification * GEO.m_to_lat,
            check=True,
        )
    if not sea_equiv_area.is_empty:
        UI.vprint(
            1, "      Separate treatment for larger pieces requiring masks."
        )
        try:
            (idx_water, dico_water) = VECT.MultiPolygon_to_Indexed_Polygons(
                sea_equiv_area, merge_overlappings=tile.clean_bad_geometries
            )
        except:
            return 0
        UI.vprint(
            2, "      Number of water Multipolygons : " + str(len(dico_water))
        )
        UI.vprint(1, "      Encoding them.")
        vector_map.encode_MultiPolygon(
            dico_water,
            tile.dem.alt_vec,
            "SEA_EQUIV",
            area_limit=tile.min_area / 10000,
            simplify=tile.water_simplification * GEO.m_to_lat,
            check=True,
        )
    # Inland limb of the seawall, run AFTER the water rings are encoded so
    # the wall's edges split against them.  Both mapped-water families
    # qualify; where a stretch was already walled by the coastline limb
    # the node coordinates coincide and the sea's zero altitude stands.
    for inland_area in (water_area, sea_equiv_area):
        insert_seawalls(
            vector_map,
            tile,
            seawall_admission_area(patches_area, graded_area),
            inland_area,
            alt_vec=tile.dem.alt_vec,
        )
    return 1


################################################################################
# def include_buildings(vector_map, tile):
#     # should be all revisited
#     UI.vprint(0, "-> Dealing with buildings")
#     building_layer = OSM.OSM_layer()
#     queries = []  #'way["building"="yes"]']
#     tags_of_interest = []
#     if not OSM.OSM_queries_to_OSM_layer(
#         queries,
#         building_layer,
#         tile.lat,
#         tile.lon,
#         tags_of_interest,
#         cached_suffix="buildings",
#     ):
#         return 0
#     for (i, j) in itertools.product(range(1), range(1)):
#         print("    Obtaining part ", 4 * i + j, " of OSM data for " + tag)
#         response = get_overpass_data(
#             tag,
#             (lat + i / 4, lon + j / 4, lat + (i + 1) / 4, lon + (j + 1) / 4),
#             "FR",
#         )
#         if UI.red_flag:
#             return 0
#         if response[0] != "ok":
#             print("    Error while trying to obtain ", query, ", exiting.")
#             return 0
#         building_layer.update_dicosm(response[1], tags_of_interest)
#     building_area = OSM.OSM_to_MultiPolygon(building_layer, lat, lon)
#     try:
#         (idx_building, dico_building) = MultiPolygon_to_Indexed_Polygons(
#             building_area, merge_overlappings=True
#         )
#     except:
#         return 0
#     UI.vprint(2, "Number of building Multipolygons :", len(dico_pol_building))
#     vector_map.encode_MultiPolygon(
#         dico_building,
#         dem.alt_vec,
#         "WATER",
#         area_limit=min_area / 10000,
#         check=True,
#     )
#     return 1


################################################################################
def _read_obj8_anchor(objfile_name, alt_lookup):
    """Parse the ANCHOR line of a candidate OBJ8 patch object file.

    Returns ``(lon, lat, alt, heading)``, or ``None`` when the file cannot
    be opened, is not UTF-8 text, carries no ANCHOR in its first line, or
    encodes its anchor wrongly.  Both anchor forms are accepted: the
    4-value ``lon lat alt heading`` one and the 3-value ``lon lat heading``
    one, whose altitude comes from ``alt_lookup(lon, lat)``.

    The patch object directories are ordinary folders on disk, so they
    routinely contain files that are not OBJ8 at all — a macOS
    ``.DS_Store`` is binary and used to kill the whole tile build with a
    ``UnicodeDecodeError`` at the first-line sniff.  An undecodable file is
    treated exactly like one whose first line lacks ANCHOR: logged and
    skipped.
    """
    pfile_name = os.path.basename(objfile_name)
    try:
        with open(objfile_name, "r") as pfile:
            firstline = pfile.readline()
    except UnicodeDecodeError:
        UI.vprint(
            1,
            "     Object ",
            pfile_name,
            " is not UTF-8 text (binary file?), skipping it.",
        )
        return None
    except:
        return None
    if not "ANCHOR" in firstline:
        UI.vprint(
            1,
            "     Object ",
            pfile_name,
            " is missing and ANCHOR in first line, skipping it.",
        )
        return None
    try:
        (lon_anchor, lat_anchor, alt_anchor, heading_anchor) = [
            float(x) for x in firstline.split()[1:]
        ]
    except:
        try:
            (lon_anchor, lat_anchor, heading_anchor) = [
                float(x) for x in firstline.split()[1:]
            ]
            alt_anchor = alt_lookup(lon_anchor, lat_anchor)
        except:
            UI.vprint(
                1,
                "     Anchor wrongly encode for : ",
                pfile_name,
                " skipping that one.",
            )
            return None
    return (lon_anchor, lat_anchor, alt_anchor, heading_anchor)


################################################################################
# THE DEGENERATE FACE FLOOR (RULINGS 2026-09-09i (2), lane ``v2seedseal``).
#
# Both INTERP_ALT seeders place their seed at ``face.representative_point()``
# of a face of a SHAPELY arrangement (``ops.polygonize`` over the ring
# boundaries), while :func:`audit_interp_alt_seed_sealing` — and
# Triangle4XP's own point location after it — reads the arrangement the
# VECTOR MAP built from the same lines through ``insert_way(check=True)``.
# The two arrangements agree everywhere a face has room; they disagree, at
# the last bits of a double, over a face that has none.
#
# MEASURED (HECA +30+031, patch of 2026-09-09 14:05, 2,081 patch faces): six
# coincident bank level rings share a node A exactly, one of them carries an
# extra node C that the other five pass 2.7 NANOMETRES clear of, and the
# noders answer that with a TRIANGLE of 2.0e-9 m^2 — A, C, and the foot of C
# on the other five (B).  Shapely put the seed inside its own version of that
# triangle; the map's version of B, from ``are_encroached``'s linear solve,
# stands 1.5e-14 deg away, which leaves the seed 1.7 NANOMETRES OUTSIDE the
# map's face union and ``audit_interp_alt_seed_sealing`` REFUSES the tile.
# No way was rejected, split or moved: all 9,336 vertices of the six rings
# are in the map, and both arrangements hold the sliver.
#
# A face this size holds no mesh vertex and no triangle a sim can render, so
# it needs no seed — and it cannot be located reliably by ANY consumer.  A
# face below the floor is therefore skipped by both seeders.  The floor is
# one square MILLIMETRE: fifteen of HECA's 2,081 faces (the largest 1e-6 m^2)
# fall under it, and the smallest face any airport's mesh can carry is many
# orders above it.
INTERP_ALT_MIN_FACE_AREA_M2 = 1.0e-6
#: Square metres in one square degree at the EQUATOR — the largest such
#: value, so the same degree-area floor is a smaller (more conservative)
#: metre floor at every other latitude.  Faces here are in tile-relative
#: degrees and the seeders carry no latitude.
_SQ_M_PER_SQ_DEG = 111320.0 ** 2
INTERP_ALT_MIN_FACE_AREA_DEG2 = (
    INTERP_ALT_MIN_FACE_AREA_M2 / _SQ_M_PER_SQ_DEG
)
#: AND THE CLEARANCE, which is the criterion the area is only a proxy for
#: (MEASURED on a second arm of the same patch, with the level rings 5 m
#: apart instead of 10: a NEEDLE of 1.14 m^2 — four corners spanning 50 m,
#: a couple of centimetres wide — put its representative point on the map's
#: own line and the audit refused again).  A seed nearer its own face's
#: boundary than this is not reliably inside ANY implementation's version
#: of that face, so it is no seed at all.  One MICROMETRE in degrees: an
#: honest face's representative point stands metres clear.
#
# THE CLEARANCE IS THE ENCODING'S OWN QUANTUM (owner RULINGS 2026-09-13cp
# follow-up; the VHHH +22+113 refusal, measured 2026-09-14).  One
# micrometre was FAR below anything the vector map can hold: it snaps
# every node onto a 1e-9 degree grid (``snap_to_grid(9)``, 0.11 mm),
# ``are_encroached`` moves a crossing onto an endpoint on a dimensionless
# 1e-8, and §39 (i)'s weld may move a constrained node by
# ``Vector_Map.weld_spacing_m``.  MEASURED at VHHH on app 1.0.331: the
# face seed (0.876712142, 0.321098147) stands 0.856 mm inside its own raw
# face -- a scanline representative point that grazed the boundary of
# ``adjacent_ground:runway:4:zone2#24``, a 767 m x 5.2 km graded strip --
# and in the ENCODED arrangement it is OUTSIDE every bounded face: one
# marked edge 0.78 mm away and the next 13 m away.  The seal audit
# refused the tile (correctly: Triangle4XP's plague would flood the whole
# land component from it) and the owner's build died in the mesh step.
#
# So the floor is stated in METRES and derived: a seed nearer its face's
# boundary than the map can move that boundary is not in the ENCODED face
# at all, whatever the raw polygon says.
INTERP_ALT_SEED_CLEARANCE_M = 0.5
INTERP_ALT_SEED_CLEARANCE_DEG = (
    INTERP_ALT_SEED_CLEARANCE_M / 111320.0
)

#: The vector map's own coordinate quantum — ``snap_to_grid(9)``, 1e-9
#: degrees, 0.11 mm.  A seed is only real if it is still inside its face
#: AFTER the map rounds it onto this grid.
INTERP_ALT_SEED_SNAP_DEG = 1.0e-9

#: THE ONLY FLOOR THAT DROPS A FACE (owner request 2026-09-14, via the
#: round's coordinator; RULINGS 2026-09-14m): the HAIRLINE degenerate
#: bar, ``O4_Mesh_Utils.HAIRLINE_DEGENERATE_M`` = 10 mm — a face narrower
#: than that is a noding artifact of two near-coincident ways and nothing
#: can hold a vertex in it.  Spelled here against the mesh module's own
#: constant rather than re-typed; the twin asserts they agree.
INTERP_ALT_SEED_DEGENERATE_M = 0.010
INTERP_ALT_SEED_DEGENERATE_DEG = INTERP_ALT_SEED_DEGENERATE_M / 111320.0


def interp_alt_seed_point(face):
    """The point to seed ``face`` at, or ``None`` when nothing can hold a
    seed there.

    A NARROW FACE IS STILL A FACE (owner 2026-09-14).  The round-3 form
    of this function DROPPED any face whose inscribed radius was under
    :data:`INTERP_ALT_SEED_CLEARANCE_M`, and a dropped face gets no
    INTERP_ALT seed, so its triangles keep the RAW DEM — at VHHH that
    silently returned 132 sub-metre faces to the terrain, among them 14
    slivers against tunnel trench floors.  Narrow is not degenerate: the
    cut faces of a tunnel — the wall strips, the pieces between a ramp
    and its wall — are exactly the sub-metre faces that floor threw away.

    THE LAW: every face is seeded at its POLE OF INACCESSIBILITY (the
    interior point farthest from the boundary), with the clearance it can
    actually afford — ``min(INTERP_ALT_SEED_CLEARANCE_M, inradius / 2)``.
    A face is dropped for exactly two reasons, both of them about whether
    a point can EXIST there at all rather than about width:

    * its inscribed radius is under the HAIRLINE floor
      (:data:`INTERP_ALT_SEED_DEGENERATE_M`, 10 mm), or
    * the seed does not survive the encoding — the vector map rounds
      every coordinate onto a 1e-9 degree grid, and a seed that lands
      outside its own face after that rounding is the VHHH +22+113
      unsealed-seed class (a build that dies in the mesh step).
    """
    if face.area < INTERP_ALT_MIN_FACE_AREA_DEG2:
        return None
    # ``boundary``, not ``exterior``: a seed grazing a HOLE's edge is as
    # unreliable as one grazing the rim.
    boundary = face.boundary
    seed_point = face.representative_point()
    if (boundary.distance(seed_point) >= INTERP_ALT_SEED_CLEARANCE_DEG
            and _survives_encoding(face, seed_point)):
        return seed_point
    # ``representative_point`` is a horizontal-scanline construction: on
    # an ample but re-entrant face it can graze the boundary (VHHH, by
    # 0.856 mm).  The pole of inaccessibility is the face's own best
    # point, and for a narrow face it is the ONLY one.
    (deepest, inradius) = _pole_of_inaccessibility(face)
    if deepest is None:
        return None
    if inradius < INTERP_ALT_SEED_DEGENERATE_DEG:
        return None
    needed = min(INTERP_ALT_SEED_CLEARANCE_DEG, inradius / 2.0)
    if boundary.distance(deepest) < needed:
        return None
    if not _survives_encoding(face, deepest):
        return None
    return deepest


def _survives_encoding(face, point):
    """True when ``point`` is still strictly inside ``face`` after the
    vector map rounds it onto its own 1e-9 degree grid.  That rounding is
    what put the VHHH seed outside its face and killed the tile build, so
    it is checked HERE, where the seed is chosen, and not left to the
    audit to refuse."""
    try:
        snapped = geometry.Point(
            round(point.x / INTERP_ALT_SEED_SNAP_DEG) * INTERP_ALT_SEED_SNAP_DEG,
            round(point.y / INTERP_ALT_SEED_SNAP_DEG) * INTERP_ALT_SEED_SNAP_DEG)
        return bool(face.contains(snapped))
    except Exception:
        return False


def _pole_of_inaccessibility(face):
    """``(point, inscribed_radius)`` — the interior point of ``face``
    farthest from its boundary, or ``(None, 0.0)`` when it cannot be
    computed.  A refinement, never a build stopper: every failure returns
    ``None`` and the caller drops the face, the conservative direction.

    The tolerance is the ENCODING GRID, not a fraction of the clearance:
    a coarse tolerance answers "0.49 m" for a 0.503 m face and the
    decision flips on the approximation rather than on the geometry.
    """
    try:
        import shapely as _sh

        spoke = _sh.maximum_inscribed_circle(face, INTERP_ALT_SEED_SNAP_DEG)
        point = geometry.Point(spoke.coords[0])
        if not face.contains(point):
            return (None, 0.0)
        return (point, float(spoke.length))
    except Exception:
        return (None, 0.0)


def is_degenerate_interp_alt_face(face):
    """True when ``face`` can hold no INTERP_ALT seed (see
    :func:`interp_alt_seed_point`)."""
    return interp_alt_seed_point(face) is None


################################################################################
def size_bank_annulus_regions(vector_map, tile):
    """Give every seed inside a BANK ANNULUS a Triangle regional AREA
    constraint (owner RULINGS 2026-09-09x).

    ``O4_Mesh_Utils.bank_annulus_region_areas`` is the one derivation of
    the annulus and of its local width; this only marries the answer to
    the seeds the vector map is about to write.  Returns the number of
    seeds sized.  Never raises: an unsized annulus is the round-1 mesh,
    which builds.
    """
    try:
        import O4_Mesh_Utils as MESH

        keys, points = [], []
        for key, seeds in vector_map.seeds.items():
            for index, seed in enumerate(seeds):
                keys.append((key, index))
                points.append((float(seed[0]), float(seed[1])))
        if not points:
            return 0
        areas = MESH.bank_annulus_region_areas(tile, points)
        if not areas:
            UI.vprint(1, "   Bank annulus: no region seed inside an annulus "
                         "— no area constraint written.")
            return 0
        for index, area in areas.items():
            vector_map.seed_areas[keys[index]] = float(area)
        values = sorted(areas.values())
        scalx = cos((tile.lat + 0.5) * pi / 180)
        # report in m2 as well: .poly units are lon x lat degrees
        to_m2 = scalx * (GEO.lat_to_m ** 2)
        UI.vprint(
            1,
            f"   Bank annulus: {len(areas)} region seed(s) given a maximum "
            f"triangle area, {values[0] * to_m2:.1f} - "
            f"{values[-1] * to_m2:.1f} m2 "
            f"(median {values[len(values) // 2] * to_m2:.1f} m2).")
        return len(areas)
    except Exception as error:
        UI.vprint(1, "   Bank annulus region sizing skipped:", str(error))
        return 0


################################################################################
def seed_interp_alt_subcells(vector_map):
    """R18-1 — seed every ROAD-CUT SUB-CELL of every patch face.

    ``include_patches`` seeds one point per planar FACE of the patch
    coverage, polygonizing the patch RING boundaries.  But the flood
    Triangle4XP runs is blocked by ANY segment carrying the same
    attribute bit, and the patch rings are not the only INTERP_ALT
    geometry on the tile: ``include_roads`` encodes the buffered banked
    road network with the very same marker, and the seawall breaklines
    do too.  Those ribbons cut a patch face into SUB-CELLS that the
    per-face seeding never sees, because they are encoded several steps
    AFTER ``include_patches`` runs.  A sub-cell with no seed keeps the
    raw DEM altitude even though every ring vertex around it carries the
    patched one.

    MEASURED (HECA, +30+031, 2026-08-11): the 339,000 m² apron face is
    cut by 40 road lines into 38 cells; the single seed sits in cell #9,
    and the owner's point at 30.1170578,31.4098155 sits in cell #3 whose
    one interior vertex keeps 99.33 m inside an 86 m apron.  Tile-wide,
    89 free interior vertices stand more than 3 m above their 8 nearest
    patch nodes.

    THE CUTTER SET IS THE VECTOR MAP'S OWN EDGES, not a re-derivation of
    the road geometry: what blocks the flood is exactly what was
    encoded, the edges are already planar-noded by ``insert_way``'s
    intersection cutting, and re-running the road extraction here would
    be a second construction of one thing (the ONE BAND CONSTRUCTION
    discipline, RULINGS 2026-08-11b).  No new marker semantics: the
    seeds are the same ``INTERP_ALT`` seeds, in the same list.

    Call AFTER every INTERP_ALT-carrying encoder has run.  Existing
    seeds are honoured — a sub-cell that already holds one gets no
    second — so this is purely additive and a tile whose patch faces no
    road crosses is left byte-identical.  Returns the number of seeds
    added.  Never raises: a failure here must not break a tile build,
    and the historical seeding already stands.
    """
    patch_polygons = getattr(vector_map, "interp_alt_patch_polygons", None)
    patches_area = getattr(vector_map, "interp_alt_patches_area", None)
    if not patch_polygons or patches_area is None or patches_area.is_empty:
        return 0
    interp_alt_bit = vector_map.dico_attributes["INTERP_ALT"]
    try:
        # Every INTERP_ALT-carrying edge whose bbox meets the patch
        # coverage — the ribbons that will block the flood inside it.
        # The rtree query is a bbox prefilter; faces outside the
        # coverage are dropped by the ``covered`` test below anyway.
        cutters = [pol.boundary for pol in patch_polygons]
        for edge_id in vector_map.ebbox.intersection(patches_area.bounds):
            if not (vector_map.data_edges.get(edge_id, 0) & interp_alt_bit):
                continue
            id0, id1 = vector_map.edges_dico[edge_id]
            cutters.append(geometry.LineString(
                [vector_map.nodes_dico[id0], vector_map.nodes_dico[id1]]))
        covered = prep(patches_area)
        existing = [
            geometry.Point(seed[0], seed[1])
            for seed in vector_map.seeds.get("INTERP_ALT", [])]
        existing_tree = STRtree(existing) if existing else None
        added = []
        degenerate = 0
        for face in ops.polygonize(ops.unary_union(cutters)):
            seed_point = interp_alt_seed_point(face)
            if seed_point is None:
                degenerate += 1      # a noding artifact, see the floor above
                continue
            if not covered.contains(seed_point):
                continue
            if existing_tree is not None:
                prepared_face = prep(face)
                if any(prepared_face.contains(existing[index])
                       for index in existing_tree.query(face)):
                    continue
            added.append(numpy.array(seed_point.coords[0]))
        if added:
            vector_map.seeds.setdefault("INTERP_ALT", []).extend(added)
        UI.vprint(
            1,
            f"   Patch faces: {len(added)} road-cut sub-cell(s) seeded "
            f"INTERP_ALT beside the {len(existing)} face seed(s) "
            f"already placed ({degenerate} degenerate face(s) skipped).")
        return len(added)
    except Exception as error:
        UI.vprint(
            1,
            "   Sub-cell INTERP_ALT seeding skipped (the per-face seeds "
            "stand):", str(error))
        return 0


################################################################################
# R18-1c SEALING PREDICATE (docs/specs/cyxy-interp-alt-flood-leak-spec.md
# item 2, "seed placement refuses an unsealed face").
#
# Triangle4XP's regionplague (Triangle4XP.c:13545) crosses any segment
# whose mark shares no bit with the flood's own attribute, so an
# INTERP_ALT seed is contained exactly when it sits in a BOUNDED face of
# the arrangement of the INTERP_ALT-carrying edges.  A seed that does not
# floods the whole uncut land component — which is what the VMMC
# SEA|INTERP_ALT incident cost in the other direction (see
# PATCH_RING_MARKER above) and what the +60-136 spec hypothesised.
#
# MEASURED at +60-136 (2026-08-28): all 578 INTERP_ALT seeds ARE sealed
# and every one of the mesh's 22,923 bit-8 triangles lands inside this
# same arrangement — the plague did not leak there, and the tile's
# defect was the mesh-side Dirichlet domain instead (R18-1c, see
# O4_Mesh_Utils).  The predicate is kept anyway: this class has now
# fired once (VMMC) and been hypothesised once, and it is the cheap half
# — 11,206 edges polygonize + union in 0.09 s, 0.03 % of the 300 s
# whole-tile budget.
INTERP_ALT_SEAL_ENV = "O4_INTERP_ALT_SEAL"


class UnsealedInterpAltSeed(Exception):
    """An INTERP_ALT seed sits in an UNBOUNDED face of its own marker."""


def audit_interp_alt_seed_sealing(vector_map):
    """REFUSE when an INTERP_ALT seed is not enclosed by INTERP_ALT edges.

    Returns the number of seeds checked.  ``O4_INTERP_ALT_SEAL=warn``
    downgrades the refusal to a loud line; a failure to BUILD the
    arrangement is always a warning only — a diagnostic must not be the
    thing that breaks a tile build.
    """
    seeds = vector_map.seeds.get("INTERP_ALT", [])
    if not seeds:
        return 0
    interp_alt_bit = vector_map.dico_attributes["INTERP_ALT"]
    try:
        nodes_dico = vector_map.nodes_dico
        lines = [
            geometry.LineString([nodes_dico[id0], nodes_dico[id1]])
            for edge_id, (id0, id1) in vector_map.edges_dico.items()
            if vector_map.data_edges.get(edge_id, 0) & interp_alt_bit
        ]
        if not lines:
            faces = []
        else:
            faces = list(ops.polygonize(ops.unary_union(lines)))
        envelope = ops.unary_union(faces) if faces else geometry.Polygon()
        sealed = prep(envelope) if not envelope.is_empty else None
    except Exception as error:
        UI.vprint(
            1,
            "   INTERP_ALT seal audit skipped (arrangement failed):",
            str(error))
        return 0
    unsealed = [
        seed for seed in seeds
        if sealed is None
        or not sealed.contains(geometry.Point(seed[0], seed[1]))
    ]
    if not unsealed:
        UI.vprint(
            1,
            f"   INTERP_ALT seal: all {len(seeds)} seed(s) enclosed by "
            f"INTERP_ALT edges ({len(faces)} bounded face(s), "
            f"{len(lines)} marked edge(s)).")
        return len(seeds)
    message = (
        "UNSEALED INTERP_ALT SEED(S): {} of {} INTERP_ALT seed(s) sit in an "
        "UNBOUNDED face of the INTERP_ALT edge arrangement. Triangle4XP's "
        "plague will flood the whole uncut land component from each of them "
        "(the VMMC leak class). A ring edge lost its bit-8 mark, or a seed "
        "was placed outside its ring. First ones: {}".format(
            len(unsealed), len(seeds),
            ", ".join("({:.9f}, {:.9f})".format(s[0], s[1])
                      for s in unsealed[:3])))
    if os.environ.get(INTERP_ALT_SEAL_ENV, "").strip().lower() == "warn":
        UI.lvprint(0, "WARNING:", message)
        return len(seeds)
    raise UnsealedInterpAltSeed(message)


################################################################################
def include_patches(vector_map, tile):
    def tanh_profile(alpha, x):
        return (numpy.tanh((x - 0.5) * alpha) / numpy.tanh(0.5 * alpha) + 1) / 2

    def spline_profile(x):
        return 3 * x ** 2 - 2 * x ** 3

    def plane_profile(x):
        return x

    patches_list = []
    patches_area = geometry.Polygon()
    # Inputs of ``patches_area``, unioned in ONE pass after the file loop.
    # The former per-way ``patches_area = patches_area.union(pol)``
    # accumulator rebuilt the whole accumulated geometry once per closed
    # way — quadratic in way count, and the dominant cost of this
    # function on multi-airport tiles (22 s of the 27 s spent here at
    # +30+031, HECA + HEAZ ≈ 3.7k ways).  ``ops.unary_union`` at the end
    # computes the same region.
    patches_area_polys = []
    # R17-3: the SEAWALL ADMISSION union — the rings whose role carries a
    # LAND altitude (GRADED_COVERAGE_ROLES), which is a SUBSET of
    # ``patches_area``: the aerodrome boundary ribbon and the
    # water-spanning bridge/road ribbons are land cutters (R4) but must
    # never admit a sea wall (VMMC's boundary spans real open sea).
    graded_area_polys = []
    # Closed patch polygons, kept so that INTERP_ALT seeds can be placed
    # per planar FACE after all patch files are read (see below).
    interp_alt_patch_polygons = []
    # RULINGS 2026-09-13cp: how many OPEN load-bearing runs took the
    # patch-ring marker (a report figure — the 1.0.329 defect was 105 of
    # them silently going in as DUMMY).
    open_breaklines = 0
    patch_dir = FNAMES.patch_dir(tile.lat, tile.lon)
    if not os.path.exists(patch_dir):
        return (patches_area, patches_list, geometry.Polygon())
    # Sort patch files so manual patches are processed before auto patches.
    # This ensures manual patches take priority: if a manual patch covers an
    # airport, the corresponding _auto patch is skipped.
    all_patch_files = [
        f for f in os.listdir(patch_dir) if f[-10:] == ".patch.osm"
    ]
    manual_patches = [f for f in all_patch_files if "_auto.patch.osm" not in f]
    auto_patches = [f for f in all_patch_files if "_auto.patch.osm" in f]
    # Track which ICAO codes are covered by manual patches
    manual_icao_codes = set()
    for f in manual_patches:
        base = f[:-10]  # strip .patch.osm
        icao_prefix = base.split("_")[0].upper()
        manual_icao_codes.add(icao_prefix)
    # Honor the auto_patch mode when LOADING, not just when generating
    # (user 2026-05-22): the setting governs which auto-patches are
    # APPLIED, so changing it takes effect even when auto-patch files
    # already exist from a previous run (e.g. set to "None" → no auto
    # patches loaded, even if the .osm files are still on disk).  Manual
    # patches are always applied — the setting only governs auto-patches.
    # Backward compat: legacy bool True/False map to "All"/"None".
    auto_patch_mode = resolved_auto_patch_mode(tile)
    boundary_skipped = {
        candidate.icao
        for candidate in (getattr(tile, "auto_patch_selection", None) or ())
        if candidate.disposition == "boundary_skipped"
    }
    # Process manual patches first, then auto patches
    ordered_patch_files = manual_patches + auto_patches
    for pfile_name in ordered_patch_files:
        # Skip auto-patches for airports that have a manual patch
        is_auto = "_auto.patch.osm" in pfile_name
        if is_auto:
            auto_icao = pfile_name.replace("_auto.patch.osm", "").upper()
            # Apply the auto_patch mode filter (mirrors generation in
            # driver.generate_auto_patches): None loads nothing; ICAO
            # loads only real 4-letter-alpha ICAO codes; All loads every.
            if not _SELECTION.mode_admits(auto_icao, auto_patch_mode):
                # ONE spelling of the mode filter (spec §A.2) — this was
                # the SECOND inline copy of it.
                UI.vprint(
                    1, "   Skipping auto-patch", pfile_name,
                    "(auto_patch=%s)." % auto_patch_mode)
                continue
            if auto_icao in boundary_skipped:
                # Spec §C.5: a patch this build DECIDED to skip must not be
                # applied from an earlier build's file.  The file is not
                # deleted — a later "build adjacent" run reuses or rebuilds
                # it by the freshness law.
                UI.vprint(
                    0, "   Skipping auto-patch", pfile_name,
                    "(boundary choice: skipped).")
                continue
            if auto_icao in manual_icao_codes:
                UI.vprint(
                    1,
                    "   Skipping auto-patch",
                    pfile_name,
                    "(manual patch exists).",
                )
                continue
        UI.vprint(1, "   Patching", pfile_name)
        patch_layer = OSM.OSM_layer()
        try:
            patch_layer.update_dicosm(
                os.path.join(patch_dir, pfile_name),
                input_tags=None,
                target_tags=None,
            )
        except:
            UI.vprint(1, "     Error in treating", pfile_name, ", skipped.")
        patches_list.append(pfile_name[:-10])
        # For auto-patches, also add the bare ICAO code so that
        # encode_runways_taxiways_and_aprons() skips this airport.
        # The auto-patch must handle the full airport surface because
        # building flattening can create large DEM variances that the
        # normal pipeline's DEM-based polynomial fitting can't account for.
        if is_auto:
            patches_list.append(auto_icao)
        dw = patch_layer.dicosmw
        dn = patch_layer.dicosmn
        df = patch_layer.dicosmfirst
        dt = patch_layer.dicosmtags
        # reorganize them so that untagged dummy ways are treated last (due to
        # altitude being first done kept for all)
        # waylist=list(set(dw).intersection(df['w']).intersection(dt['w']))+
        # list(set(dw).intersection(df['w']).difference(dt['w']))
        # HACK
        waylist = tuple(df["w"].intersection(dt["w"])) + tuple(
            df["w"].difference(dt["w"])
        )
        for wayid in waylist:
            way = numpy.array(
                [dn[nodeid] for nodeid in dw[wayid]], dtype=float
            )
            way = way - numpy.array([[tile.lon, tile.lat]])
            alti_way_orig = tile.dem.alt_vec(way)
            cplx_way = False
            if wayid in dt["w"]:
                wtags = dt["w"][wayid]
                if "cst_alt_abs" in wtags:
                    alti_way = numpy.ones((len(way), 1)) * float(
                        wtags["cst_alt_abs"]
                    )
                elif "cst_alt_rel" in wtags:
                    alti_way = numpy.ones((len(way), 1)) * (
                        numpy.mean(tile.dem.alt_vec(way))
                        + float(wtags["cst_alt_rel"])
                    )
                elif "var_alt_rel" in wtags:
                    alti_way = alti_way_orig + float(wtags["var_alt_rel"])
                elif (
                    "altitude" in wtags
                ):  # deprecated : for backward compatibility only
                    try:
                        alti_way = numpy.ones((len(way), 1)) * float(
                            wtags["altitude"]
                        )
                    except:
                        alti_way = numpy.ones((len(way), 1)) * numpy.mean(
                            tile.dem.alt_vec(way)
                        )
                elif "node_altitudes" in wtags:
                    # Per-node altitude: comma-separated elevation values,
                    # one per node. Supports arbitrary polygon shapes with
                    # individually specified elevations at each vertex.
                    try:
                        alts = [
                            float(x)
                            for x in wtags["node_altitudes"].split(",")
                        ]
                        if len(alts) == len(way):
                            alti_way = numpy.array(alts).reshape(-1, 1)
                        else:
                            UI.vprint(
                                1,
                                "    node_altitudes count ({}) != node"
                                " count ({}), using DEM.".format(
                                    len(alts), len(way)
                                ),
                            )
                            alti_way = alti_way_orig
                    except Exception:
                        alti_way = alti_way_orig
                elif "altitude_high" in wtags:
                    cplx_way = True
                    if len(way) != 5 or (way[0] != way[-1]).all():
                        UI.vprint(
                            1,
                            "    Wrong number of nodes or non closed way for ",
                            "a altitude_high/altitude_low polygon, skipped.",
                        )
                        continue
                    short_high = way[-2:]
                    short_low = way[1:3]
                    try:
                        altitude_high = float(wtags["altitude_high"])
                        altitude_low = float(wtags["altitude_low"])
                    except:
                        altitude_high = tile.dem.alt_vec(short_high).mean()
                        altitude_low = tile.dem.alt_vec(short_low).mean()
                    try:
                        cell_size = float(wtags["cell_size"])
                    except:
                        cell_size = 10
                    try:
                        rnw_profile = wtags["profile"]
                    except:
                        rnw_profile = "plane"
                    try:
                        alpha = float(wtags["steepness"])
                    except:
                        alpha = 2
                    if "tanh" in rnw_profile:
                        rnw_profile = lambda x: tanh_profile(alpha, x)
                    elif rnw_profile == "spline":
                        rnw_profile = spline_profile
                    else:
                        rnw_profile = plane_profile
                    rnw_vect = (
                        short_high[0]
                        + short_high[1]
                        - short_low[0]
                        - short_low[1]
                    ) / 2
                    rnw_length = (
                        sqrt(
                            rnw_vect[0] ** 2 * cos(tile.lat * pi / 180) ** 2
                            + rnw_vect[1] ** 2
                        )
                        * 111120
                    )
                    # Floor at 1 cut: a large ``cell_size`` (the patch
                    # node-density knob) can drive ``int(rnw_length /
                    # cell_size)`` to 0, which skipped the graded-altitude
                    # path and left ``alti_way`` unbound (UnboundLocalError
                    # below).  One cut is negligible for triangle count and
                    # keeps the graded ``altitude_high/low`` profile (the
                    # alt fallback samples the raw DEM, which would drop a
                    # sloped pavement onto terrain).
                    cuts_long = max(1, int(rnw_length / cell_size))
                    if cuts_long:
                        cuts_long += 1
                        way = numpy.array(
                            [
                                way[0] + i / cuts_long * (way[1] - way[0])
                                for i in range(cuts_long)
                            ]
                            + [way[1]]
                            + [
                                way[2] + i / cuts_long * (way[3] - way[2])
                                for i in range(cuts_long)
                            ]
                            + [way[3], way[4]]
                        )
                        alti_way = numpy.array(
                            [
                                altitude_high
                                - rnw_profile(i / cuts_long)
                                * (altitude_high - altitude_low)
                                for i in range(cuts_long + 1)
                            ]
                        )
                        alti_way = numpy.hstack(
                            [alti_way, alti_way[::-1], alti_way[0]]
                        )
                else:
                    alti_way = alti_way_orig
            else:
                alti_way = alti_way_orig
            if not cplx_way:
                for i in range(len(way)):
                    nodeid = dw[wayid][i]
                    if nodeid in dt["n"]:
                        ntags = dt["n"][nodeid]
                        if "alt_abs" in ntags:
                            alti_way[i] = float(ntags["alt_abs"])
                        elif "alt_rel" in ntags:
                            alti_way[i] = alti_way_orig[i] + float(
                                ntags["alt_rel"]
                            )
            alti_way = alti_way.reshape((len(alti_way), 1))
            if (way[0] == way[-1]).all():
                try:
                    pol = geometry.Polygon(way)
                    if pol.is_valid and pol.area:
                        patches_area_polys.append(pol)
                        # R17-3: role-scoped seawall admission.  The role
                        # tag is the patch's own (``layout.to_osm``);
                        # a ring without one is not graded coverage.
                        if (dt["w"].get(wayid, {}).get("role")
                                in GRADED_COVERAGE_ROLES):
                            graded_area_polys.append(pol)
                        # Pavement in our patch is LAND: the ring blocks
                        # the WATER / SEA / SEA_EQUIV floods as well as
                        # the INTERP_ALT one (see PATCH_RING_MARKER).
                        vector_map.insert_way(
                            numpy.hstack([way, alti_way]),
                            PATCH_RING_MARKER,
                            check=True,
                        )
                        interp_alt_patch_polygons.append(pol)
                        if cplx_way and cuts_long:
                            for i in range(1, cuts_long):
                                id0 = vector_map.dico_nodes[tuple(way[i])]
                                id1 = vector_map.dico_nodes[tuple(way[-2 - i])]
                                vector_map.insert_edge(
                                    id0,
                                    id1,
                                    vector_map.dico_attributes["DUMMY"],
                                )
                    else:
                        UI.vprint(2, "     Skipping invalid patch polygon.")
                except:
                    UI.vprint(2, "     Skipping invalid patch polygon.")
            else:
                # RULINGS 2026-09-13cp: an OPEN load-bearing run is a
                # BREAKLINE (see OPEN_BREAKLINE_FEATURES above) — the
                # INTERP_ALT barrier and the Dirichlet datum its closed
                # predecessor was.  Anything else open stays DUMMY.
                if (dt["w"].get(wayid, {}).get("o4_feature")
                        in OPEN_BREAKLINE_FEATURES):
                    vector_map.insert_way(
                        numpy.hstack([way, alti_way]),
                        PATCH_RING_MARKER,
                        check=True,
                    )
                    open_breaklines += 1
                else:
                    vector_map.insert_way(
                        numpy.hstack([way, alti_way]), "DUMMY", check=True
                    )
    if open_breaklines:
        UI.vprint(
            1,
            f"   Patch breaklines: {open_breaklines} OPEN load-bearing run(s) "
            "took the patch-ring marker (INTERP_ALT barrier + Dirichlet "
            "datum) instead of DUMMY (RULINGS 2026-09-13cp).")
    # ── R21: THE ISTHMUS NEEDS NO RING ─────────────────────────────────
    # (owner ruling 2026-08-12, "LAND-CONNECTED CONTINUITY".)  R17-2's
    # DECLARED CORRIDOR needed the two authorities above — a ring to stop
    # the sea flood and an entry in the wall admission — because it
    # claimed WATER as land.  The isthmus claims nothing: it is land the
    # coastline data already carries, so the sea flood already stops at
    # its own shoreline and the wall admission already finds it through
    # ``coastline_wall_admission`` (the isthmus inset kind joins
    # :data:`AIRPORT_ISLAND_INSET_KINDS`).  Only its LEVEL was missing,
    # and that is the flat-site inset's job, in DEM prep.
    graded_area = geometry.Polygon()
    if graded_area_polys:
        try:
            graded_area = ops.unary_union(graded_area_polys)
        except Exception:
            # A wall is a refinement: a union failure costs the wall,
            # never the coastline.  (The land cutter below has its own
            # per-polygon fallback because it costs the WATER LAW.)
            UI.vprint(1, "     Seawall admission union failed — no wall "
                         "this tile.")
            graded_area = geometry.Polygon()
    if patches_area_polys:
        try:
            patches_area = ops.unary_union(patches_area_polys)
        except Exception:
            # Fall back to the historical per-polygon accumulation so a
            # single bad pairwise interaction drops that polygon only.
            for pol in patches_area_polys:
                try:
                    patches_area = patches_area.union(pol)
                except Exception:
                    UI.vprint(2, "     Skipping invalid patch polygon.")
    # Seed every planar FACE of the patch coverage, not one point per ring.
    # Triangle4XP spreads a regional attribute by plague, and the flood is
    # blocked by ANY segment carrying the same attribute bit (see the
    # preamble of O4_Vector_Utils and regionplague in Triangle4XP.c).  When
    # closed patch ways overlap — a bridge trench crossing pavement rings, a
    # retaining wall crossing an apron — their boundaries partition each
    # other's interiors into several faces, and a single seed per ring
    # leaves the other faces unmarked: their triangles keep the raw DEM
    # altitude even though every ring vertex carries the intended one.
    if interp_alt_patch_polygons:
        try:
            interp_alt_seeds = []
            covered = prep(patches_area)
            for face in ops.polygonize(
                ops.unary_union(
                    [pol.boundary for pol in interp_alt_patch_polygons]
                )
            ):
                # A face with no room holds no mesh vertex and cannot be
                # located identically by the map's own arrangement — see
                # INTERP_ALT_MIN_FACE_AREA_M2.
                seed_point = interp_alt_seed_point(face)
                if seed_point is not None and covered.contains(seed_point):
                    interp_alt_seeds.append(
                        numpy.array(seed_point.coords[0])
                    )
            if not interp_alt_seeds:
                raise ValueError("face seeding produced no seeds")
        except Exception:
            # Fall back to the historical one-seed-per-ring placement.
            interp_alt_seeds = [
                numpy.array(pol.representative_point().coords[0])
                for pol in interp_alt_patch_polygons
            ]
        vector_map.seeds.setdefault("INTERP_ALT", []).extend(
            interp_alt_seeds
        )
        # R18-1: the faces above are cut by the patch RING boundaries
        # only, and the roads have not been encoded yet — they come in
        # ``include_roads``, several steps later in ``build_poly_file``.
        # Carry the inputs so the sub-cell pass can run once the road
        # ribbons exist (see :func:`seed_interp_alt_subcells`).
        vector_map.interp_alt_patch_polygons = interp_alt_patch_polygons
        vector_map.interp_alt_patches_area = patches_area
    for pdir_name in os.listdir(patch_dir):
        if not os.path.isdir(os.path.join(patch_dir, pdir_name)):
            continue
        UI.vprint(1, "   Including OBJ8 objects from", pdir_name)
        patches_list.append(pdir_name)
        for pfile_name in os.listdir(os.path.join(patch_dir, pdir_name)):
            pfile_namelong = os.path.join(patch_dir, pdir_name, pfile_name)
            anchor = _read_obj8_anchor(
                pfile_namelong,
                lambda lon, lat: tile.dem.alt(
                    (lon - tile.lon, lat - tile.lat)
                ),
            )
            if anchor is None:
                continue
            (lon_anchor, lat_anchor, alt_anchor, heading_anchor) = anchor
            patches_area = patches_area.union(
                keep_obj8(
                    lat_anchor,
                    lon_anchor,
                    alt_anchor,
                    heading_anchor,
                    pfile_namelong,
                    vector_map,
                    tile,
                )
            )
    return (patches_area, patches_list, graded_area)


################################################################################
def keep_obj8(
    lat_anchor,
    lon_anchor,
    alt_anchor,
    heading_anchor,
    objfile_name,
    vector_map,
    tile,
):
    dico_idx_nodes = {}
    idx_node = 0
    dico_index = {}
    index = 0
    latscale = GEO.m_to_lat
    lonscale = latscale / cos(lat_anchor * pi / 180)
    f = open(objfile_name, "r")
    for line in f.readlines():
        if line[0:2] == "VT":
            (xo, yo, zo) = [float(s) for s in line.split()[1:4]]
            Xo = xo * cos(heading_anchor * pi / 180) - zo * sin(
                heading_anchor * pi / 180
            )
            Zo = xo * sin(heading_anchor * pi / 180) + zo * cos(
                heading_anchor * pi / 180
            )
            y = numpy.round(lat_anchor - latscale * float(Zo) - tile.lat, 7)
            x = numpy.round(lon_anchor + lonscale * float(Xo) - tile.lon, 7)
            z = yo + alt_anchor
            dico_idx_nodes[idx_node] = vector_map.insert_node(x, y, z)
            idx_node += 1
        elif line[0:3] == "IDX":
            dico_index[index] = [int(x) for x in line.split()[1:]]
            index += 1
        elif line[0:4] == "TRIS":
            (offset, count) = [int(x) for x in line.split()[1:3]]
            list = []
            count_tmp = 0
            try:
                polist = []
                while count_tmp < count:
                    list += dico_index[offset]
                    count_tmp += len(dico_index[offset])
                    offset += 1
                for j in range(count // 3):
                    (a, b, c) = [
                        dico_idx_nodes[x] for x in list[3 * j : 3 * j + 3]
                    ]
                    if a == b or a == c or b == c:
                        continue
                    for (initp, endp) in ((a, b), (b, c), (c, a)):
                        vector_map.insert_edge(
                            initp,
                            endp,
                            vector_map.dico_attributes["INTERP_ALT"],
                            check=True,
                        )
                    seed = (
                        numpy.array(vector_map.nodes_dico[a])
                        + numpy.array(vector_map.nodes_dico[b])
                        + numpy.array(vector_map.nodes_dico[c])
                    ) / 3
                    if "INTERP_ALT" in vector_map.seeds:
                        vector_map.seeds["INTERP_ALT"].append(seed)
                    else:
                        vector_map.seeds["INTERP_ALT"] = [seed]
                    polist.append(
                        geometry.Polygon(
                            [
                                vector_map.nodes_dico[a],
                                vector_map.nodes_dico[b],
                                vector_map.nodes_dico[c],
                                vector_map.nodes_dico[a],
                            ]
                        )
                    )
                multipol = VECT.ensure_MultiPolygon(ops.unary_union(polist))
            except:
                pass
    f.close()
    return multipol
