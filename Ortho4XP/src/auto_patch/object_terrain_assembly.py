"""Assemble a bridge/tunnel :class:`ClassificationResult` for one airport.

Workstream W-B of ``docs/object_terrain_features_spec.md`` — the *impure*
front end to the pure classifier (:mod:`object_terrain_features`).  Where
the classifier takes placements + geometry and returns records, this
module does the file work the classifier deliberately refuses: locate the
airport pack's overlay DSF, run the (cached) DSFTool text dump, read the
placements (``include_object_msl=True`` so KBNA's absolute deck fixtures
survive), load the referenced OBJ8 geometry, hand the pipeline's own
draped pavement in as the contract-coverage evidence, and — for the
depressed-road corridor re-source (spec section 3.2 step 3) — discover the
sibling roads pack's DSF road network on the same tile.

Everything here is gated behind ``config.OBJECT_BRIDGE_TERRAIN`` (default
off).  With the gate off :func:`attach_bridge_classification` is a no-op
that touches nothing and attaches nothing, so every downstream reader in
``bridges.py`` sees ``getattr(layout, ATTRIBUTE, None) is None`` and takes
its unchanged legacy path — the build is byte-identical to today.

The two artefacts cached on the layout when the gate is on:

* ``layout._object_bridge_classification`` — the
  :class:`object_terrain_features.ClassificationResult` (may itself carry
  empty ``bridges``/``tunnels`` when the pack has no such objects — KDFW —
  which is the designed "feature B does not fire, legacy handles it" path).
* ``layout._object_bridge_road_networks`` — a list of
  :class:`dsf_road_network.RoadNetwork` from every Custom Scenery pack that
  carries a vector road network on the airport's tile (the KBNA "US-KBNA
  Nashville Roads" pack is the exemplar; the bridged roads exist ONLY
  there).

The reader/loader APIs consumed here are all already merged and tested
(W-R1/W-R2/W-R3); this module wires them together and adds no new parsing.

ACCEPTANCE-LOOP RULE (round 6, measured the hard way): iteration builds
must run with ``O4_DSF_OBJECT_REANCHOR=0``.  The Phase 2 y-bake mutates
pack OBJ8 files; across repeated builds an unexcluded sibling part
(KBNA Taxiway-L p3) drifted until it qualified into the classifier pool
and moved the deck box.  The bake belongs after a FINAL mesh only.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
from dataclasses import dataclass, field, replace as _dataclass_replace
from statistics import median

import O4_UI_Utils as UI

from . import dsf_reader
from . import obj8_reader
from . import dsf_road_network
from . import object_terrain_features
from . import config
from .geom_safe import min_rotated_rect


# The layout attribute names the bridge emitters read.  Kept as module
# constants so the producer here and the consumers in ``bridges.py`` can
# never drift on a spelling.
CLASSIFICATION_ATTRIBUTE = "_object_bridge_classification"
ROAD_NETWORKS_ATTRIBUTE = "_object_bridge_road_networks"
ROUTE_LINES_ATTRIBUTE = "_object_bridge_route_lines"

# A resource placed more often than this is scenery clutter (trees, lamp
# posts, fence posts) and is never a tunnel/bridge structure — skip it so
# the classifier is not fed thousands of identical footprints.  Mirrors
# Phase 1's posture of not pooling mass-placed resources; a real
# tunnel/bridge object is placed a handful of times (EGLL: one placement
# per tunnel; KBNA taxiway-L: six part objects).
MAXIMUM_PLACEMENTS_PER_RESOURCE = 50

# Ruling R4 exclusion breadth (round 6): every resource placed at the
# SAME ANCHOR as a consumed structure belongs to that structure's part
# family and must be excluded from the Phase 2 y-bake — the classifier's
# ``object_resources`` lists only the parts that carried usable deck
# geometry (KBNA taxiway-L pools p1/p4/p5/p6; p2/p3 have no qualifying
# faces yet sit on the SAME anchor and got re-baked build after build
# until their drifted geometry qualified into the pool and moved the
# deck box).  MEASURED at KBNA: all six Taxiway-L parts (and every
# Crossing / Murfreesboro part set) share ONE anchor to the millimetre
# (max intra-family spread 0.00 m), while the nearest FOREIGN placement
# (GPU_1.obj) sits 1.5 m from a bridge anchor — 0.5 m separates the
# families from neighbours with a 3x margin both ways (the 2 m
# structure-grouping epsilon would wrongly swallow the GPU).
ANCHOR_FAMILY_RADIUS_M = 0.5

# Pack-datum guard for the family expansion.  Some payware authors bake
# EVERY object against one shared anchor (spec section 3.4 anchor
# caution: geometry 150 m–3.3 km from a single sampled point; MEASURED
# at Aerosoft LSGG 2026-07-23: 265 of 292 terrain placements on ONE
# coordinate).  Such an anchor carries no part-family information — one
# consumed structure there would pull the whole airport onto the R4
# exclusion list and starve the Phase 2 y-bake.  A real part family is
# small (KBNA's largest: six Taxiway-L parts); an anchor shared by more
# distinct resources than this is a pack datum and never expanded from.
ANCHOR_FAMILY_MAX_RESOURCES = 12


def anchor_family_resources(placements, seed_resources, *, label="R4"):
    """Every resource with a placement anchored within
    :data:`ANCHOR_FAMILY_RADIUS_M` of a placement of ``seed_resources``
    — the whole part family (p1..p6, shell+deck pairs, deck+railings).
    The seeds themselves are included.

    Anchors shared by more than :data:`ANCHOR_FAMILY_MAX_RESOURCES`
    distinct resources are pack datums, not families, and contribute
    nothing (``label`` names the caller in the log line).

    ONE family predicate, two readers: the ruling-R4 exclusion breadth
    below and the R12-2 seat member set.  A seat whose family is
    narrower than the exclusion's leaves a sibling excluded from the
    y-bake AND unseated — which is exactly how
    ``OTHH_Bridge_04_LOD0_004`` came to sit 7.85 m under its own bridge.
    """
    seeds = set(seed_resources)
    if not seeds:
        return set()
    candidate_anchors = sorted({
        (placement.longitude, placement.latitude)
        for placement in placements
        if placement.resource_path in seeds
    })
    family_anchors = []
    for anchor_longitude, anchor_latitude in candidate_anchors:
        cosine = math.cos(math.radians(anchor_latitude))
        resources_at_anchor = {
            placement.resource_path
            for placement in placements
            if math.hypot(
                (placement.latitude - anchor_latitude) * 111320.0,
                (placement.longitude - anchor_longitude)
                * 111320.0 * cosine,
            ) <= ANCHOR_FAMILY_RADIUS_M
        }
        if len(resources_at_anchor) > ANCHOR_FAMILY_MAX_RESOURCES:
            UI.vprint(
                2,
                f"   [object-bridge] {label} family expansion: anchor "
                f"({anchor_latitude:.6f}, {anchor_longitude:.6f}) is "
                f"shared by {len(resources_at_anchor)} distinct "
                "resources — a pack datum, not a part family; sibling "
                "expansion skipped there",
            )
            continue
        family_anchors.append((anchor_longitude, anchor_latitude))
    if not family_anchors:
        return set(seeds)
    family = set(seeds)
    for placement in placements:
        if placement.resource_path in family:
            continue
        cosine = math.cos(math.radians(placement.latitude))
        for anchor_longitude, anchor_latitude in family_anchors:
            distance = math.hypot(
                (placement.latitude - anchor_latitude) * 111320.0,
                (placement.longitude - anchor_longitude)
                * 111320.0 * cosine,
            )
            if distance <= ANCHOR_FAMILY_RADIUS_M:
                family.add(placement.resource_path)
                break
    return family


def _expand_exclusions_to_anchor_families(result, placements, pack_root):
    """Append to ``result.exclusions`` every resource in the anchor
    family (:func:`anchor_family_resources`) of a consumed structure.
    Returns the sorted list of newly excluded resource paths."""
    consumed = {resource for _root, resource in result.exclusions}
    if not consumed:
        return []
    added = sorted(
        anchor_family_resources(placements, consumed) - consumed
    )
    for resource_path in added:
        result.exclusions.append((pack_root, resource_path))
    return added


def _tile_dsf_path(earth_nav_data_dir: str, tile_lat: int, tile_lon: int) -> str:
    """The ``<grp>/<tile>.dsf`` path under an ``Earth nav data`` dir for a
    1-degree tile, using X-Plane's ``+NN-MMM`` naming (the exact scheme
    :func:`dsf_reader.find_associated_dsf` builds internally)."""
    group_lat = (tile_lat // 10) * 10
    group_lon = (tile_lon // 10) * 10

    def _format(value: int, pad: int) -> str:
        sign = "+" if value >= 0 else "-"
        return f"{sign}{abs(value):0{pad}d}"

    group = f"{_format(group_lat, 2)}{_format(group_lon, 3)}"
    tile = f"{_format(tile_lat, 2)}{_format(tile_lon, 3)}"
    return os.path.join(earth_nav_data_dir, group, tile + ".dsf")


def _pavement_polygons_longitude_latitude(layout) -> list | None:
    """Project the pipeline's own draped source pavement into
    ``(longitude, latitude)`` rings for the classifier's contract-coverage
    test.  ``None`` when the layout carries no pavement union yet — the
    classifier then falls back to the crest-height contract and the caller
    records that the height fallback governed."""
    union = getattr(layout, "source_pavement_union", None)
    if union is None or getattr(union, "is_empty", True):
        return None
    parts = (
        list(union.geoms)
        if union.geom_type == "MultiPolygon"
        else [union]
    )
    rings: list = []
    from shapely.geometry import Polygon

    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        ring_longitude_latitude = []
        for x, y in part.exterior.coords:
            latitude, longitude = layout.m_to_ll(x, y)
            ring_longitude_latitude.append((longitude, latitude))
        if len(ring_longitude_latitude) >= 3:
            rings.append(Polygon(ring_longitude_latitude))
    return rings or None


def _load_object_geometry_by_resource(
    placements, pack_root, xplane_root
):
    """Resolve and load OBJ8 geometry for every terrain-relative placement
    resource, skipping light-only objects (no solid geometry), mass-placed
    clutter (more than :data:`MAXIMUM_PLACEMENTS_PER_RESOURCE` placements)
    — the same two skips Phase 1 applies — and stock library assets
    (``lib/...``), which the classifier refuses anyway (2026-07-18): not
    loading them saves parsing catalogue geometry such as the 27k-triangle
    ``lib/ships/OilRig.obj``."""
    placement_count_by_resource: dict[str, int] = {}
    for placement in placements:
        placement_count_by_resource[placement.resource_path] = (
            placement_count_by_resource.get(placement.resource_path, 0) + 1
        )
    geometry_by_resource: dict = {}
    for resource_path in sorted(
        {placement.resource_path for placement in placements}
    ):
        if (
            placement_count_by_resource[resource_path]
            > MAXIMUM_PLACEMENTS_PER_RESOURCE
        ):
            continue
        if object_terrain_features.is_stock_library_resource(resource_path):
            continue
        physical_path = obj8_reader.resolve_object_resource(
            resource_path, pack_root, xplane_root
        )
        if physical_path is None:
            continue
        # Ruling R1 parity (same choice as the building-ring read in
        # ``dsf_reader`` and Phase 2 discovery): classify the AUTHORED
        # geometry from the ``.anchor_bak`` original when one exists.
        # The Phase 2 y-bake writes per-vertex offsets into the LIVE
        # file, so on a baked pack the live geometry sits metres below
        # its authored base and plain terminal buildings measure as
        # below-grade bowls/tunnels (LSGG 2026-07-23: a −9.4 m live
        # shift manufactured the very signatures whose exclusions then
        # reverted the bake).
        from .object_rebake import BACKUP_SUFFIX

        backup_path = physical_path + BACKUP_SUFFIX
        geometry_source_path = (
            backup_path if os.path.isfile(backup_path) else physical_path
        )
        geometry = dsf_reader._load_object_geometry(geometry_source_path)
        if geometry is None or not geometry.has_solid_geometry:
            continue
        geometry_by_resource[resource_path] = geometry
    return geometry_by_resource


# Bump when ``dsf_road_network.parse_dsf_road_networks`` changes its
# record shapes — invalidates every road-network sidecar.
_ROAD_NETWORK_CACHE_VERSION = 1

# Sidecar file name prefix; the full name carries the DSF stem
# (``o4_dsf_road_network_<dsf-stem>.cache``).  Lives under
# ``dsf_reader.airport_mod_cache_dir`` — NOT in the roads pack (user
# ruling 2026-07-15, no Ortho4XP clutter in scenery packs).
_ROAD_NETWORK_SIDECAR_PREFIX = "o4_dsf_road_network"

# Pre-ruling in-pack sidecar name, removed on sight (legacy cleanup).
_ROAD_NETWORK_LEGACY_SIDECAR_NAME = "o4_dsf_road_network.cache"


def _road_network_sidecar(dsf_path: str) -> tuple[str | None, str | None]:
    """Sidecar path + fingerprint for one sibling DSF's road network.

    ``parse_dsf_road_networks`` output is a pure function of the DSF text
    dump, which is itself a pure function of the DSF file, so the
    fingerprint is just a code version salt plus the DSF's own size and
    mtime — any layout edit to a roads pack necessarily rewrites the DSF.
    The sidecar lives under ``dsf_reader.airport_mod_cache_dir`` for that
    roads pack (user ruling 2026-07-15 — Ortho4XP-only caches stay out of
    scenery pack folders); a pre-ruling in-pack sidecar found at the pack
    root is removed here.  Returns ``(None, None)`` when no pack root
    resolves or the DSF cannot be stat-ed."""
    pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
    cache_directory = dsf_reader.airport_mod_cache_dir(pack_root)
    if cache_directory is None:
        return None, None
    # Legacy cleanup: exactly the old filename at the pack root, every
    # OSError swallowed.
    try:
        os.remove(os.path.join(pack_root,
                               _ROAD_NETWORK_LEGACY_SIDECAR_NAME))
    except OSError:
        pass
    try:
        dsf_stat = os.stat(dsf_path)
    except OSError:
        return None, None
    fingerprint = (
        f"{_ROAD_NETWORK_CACHE_VERSION}:{os.path.basename(dsf_path)}"
        f":{dsf_stat.st_size}:{dsf_stat.st_mtime}"
    )
    dsf_stem = os.path.splitext(os.path.basename(dsf_path))[0]
    return (
        os.path.join(
            cache_directory,
            f"{_ROAD_NETWORK_SIDECAR_PREFIX}_{dsf_stem}.cache",
        ),
        fingerprint,
    )


def _discover_sibling_road_networks(
    xplane_root: str, tile_lat: int, tile_lon: int
) -> list:
    """Every Custom Scenery pack's vector road network that covers the
    airport's tile (spec section 3.2 step 3 — the KBNA bridged roads live
    only in the sibling "US-KBNA Nashville Roads" pack).

    Scans the ``scenery_packs.ini`` pack order, builds each pack's tile
    DSF path, and — for those that exist and dump to text — parses the
    road network, keeping any that carries at least one segment.  Base and
    global scenery are skipped (never a bespoke roads pack)."""
    if not xplane_root:
        return []
    try:
        from .agp_reader import _scenery_pack_order
    except ImportError:
        return []
    custom_scenery = os.path.join(xplane_root, "Custom Scenery")
    networks: list = []
    for pack_name in _scenery_pack_order(xplane_root):
        earth_nav_data = os.path.join(
            custom_scenery, pack_name, "Earth nav data"
        )
        if not os.path.isdir(earth_nav_data):
            continue
        dsf_path = _tile_dsf_path(earth_nav_data, tile_lat, tile_lon)
        if not os.path.isfile(dsf_path):
            continue

        # ── Per-DSF road-network sidecar cache (default ON) ──  A hit
        # skips BOTH the DSFTool text dump (``_load_dsf_text``) and the
        # parse, the two costs the profile attributes to this discovery.
        # ``O4_DSF_ROAD_NETWORK_CACHE=0`` disables read and write.
        cache_enabled = (
            os.environ.get("O4_DSF_ROAD_NETWORK_CACHE", "1") == "1"
        )
        sidecar_path = None
        fingerprint = None
        if cache_enabled:
            import pickle
            sidecar_path, fingerprint = _road_network_sidecar(dsf_path)
            if (
                sidecar_path
                and fingerprint
                and os.path.isfile(sidecar_path)
            ):
                try:
                    with open(sidecar_path, "rb") as sidecar_file:
                        payload = pickle.load(sidecar_file)
                    if payload.get("fingerprint") == fingerprint:
                        network = payload["result"]
                        if network.segments:
                            networks.append(network)
                        continue
                except Exception:
                    pass

        lines = dsf_reader._load_dsf_text(dsf_path)
        if not lines:
            continue
        network = dsf_road_network.parse_dsf_road_networks(lines)

        if sidecar_path is not None and fingerprint is not None:
            import pickle
            try:
                os.makedirs(os.path.dirname(sidecar_path), exist_ok=True)
                with open(sidecar_path, "wb") as sidecar_file:
                    pickle.dump(
                        {"fingerprint": fingerprint, "result": network},
                        sidecar_file,
                    )
            except Exception:
                pass

        if network.segments:
            networks.append(network)
    return networks


# Bump when classifier logic or record shapes change — invalidates every
# pack-sidecar classification cache (see attach_bridge_classification).
# Version 3: classifier performance round 2026-07-10 (evidence
# pre-screen, composed placement transform, bulk footprint unions) —
# results are equivalent within float tolerance but must be rebuilt on
# the new code path.
# 5: face records grew bridge-shaped compatibility fields
# (deck_polygon/frame_origin) — older pickles lack them and crash pair
# consumers once face pairs own crossings.
# 7: tunnels carry solid_outline_footprint (flush-bottom trench floors).
# 8: stock-library (lib/...) resources excluded from classification, plus
# the AGL-limb above-grade height cap (EGKR Redhill control tower).
# 9: classification reads AUTHORED geometry (.anchor_bak when present),
# and feature-C ground-interface exclusions are gated behind
# config.OBJECT_SPLIT_LEVEL_TERRAIN (LSGG 2026-07-23 y-bake starvation).
# 10: the bowl rule grew its OPEN-PIT limb (BOWL_MAX_ABOVE_GRADE_AREA_
# FRACTION) so shallow basins stop reading FLAT_CONFIRMED, interfaces
# carry above_grade_area_fraction, and carved basins join the R4
# exclusions under config.OBJECT_BASIN_TRENCH — a cached v9 result would
# hand back the pre-fix FLAT verdicts on an unchanged pack.
# 11: open-pit COMPONENTS are classified on their own frames before the
# whole-pool feature-C pass (_open_pit_components), so a basin pooled
# with a terminal complex stops being averaged away — a v10 result still
# carries the diluted mega-pool records (measured at OTHH: Drainage_05
# absent entirely, Dewatering_02 cut 3.96 m instead of 13.08 m).
# 12: the AGL tunnel seed's above-grade cap and below-grade deck floor
# are judged on the WHOLE structure, not one resource (owner ruling
# 2026-07-31) — a v11 result still classifies OTHH's above-ground
# Bridge_01/_04 as tunnels and cuts trenches under them.
# 13: the AGL tunnel seed also refuses a structure carrying a deck's worth
# of near-horizontal area standing clear above grade (TUNNEL_AGL_MAX_
# ABOVE_GRADE_DECK_AREA_M2) — the low-bridge case the +2.0 m height cap
# cannot see.  A v12 result still cuts a trench under OTHH Bridge_04
# (crest +1.91, 1,650.6 m² of deck above grade).
# 14: ``StructureGroundInterface`` grew ``solid_minimum_y_m`` (the TRUE
# deepest solid of the structure's frame, spec basin-rim-flush-seating
# section 2.1 item 3).  THE VERSION IS THE FIX for a measured defect: the
# section-2.1 landing (3402698) added the field but left this number at
# 13, so a fingerprint-matching v13 pickle written before it kept being
# accepted — and an OLD pickle restores a frozen dataclass from its
# recorded ``__dict__``, which has no such key, so every interface read
# back with the CLASS DEFAULT ``None``.  ``basin_trench_structures`` then
# took its documented fallback (the clustered interface LEVEL) and OTHH
# Drainage_06 carried −3.859 m into the floor law and the E2 sidecar
# where its deepest solid is −4.201 m (in the ``_001`` sibling shell) —
# 0.342 m of the promised 0.5 m clearance spent before the cut.  Adding
# a field to a PICKLED record is a cache-version event; nothing else in
# the fingerprint can see it.
# 15: the round-5 feature-A ADMISSION guards (spec
# docs/specs/round5-vhhh-tunnel-admission-spec.md) — a candidate with no
# solid geometry within TUNNEL_MIN_ABOVE_GRADE_TOP_M of grade is
# submerged scenery, and a record whose deck footprint exceeds
# TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2 is not a tunnel.  A v14 result for an
# unedited pack still carries VHHH's 21,495,901 m² ``tunnel/sea.obj`` +
# ``sea_X.obj`` record, whose −21.38 m trench claimed all unowned ground
# on the island; the fingerprint cannot see a classifier rule change, so
# the version is what retires it.
# 16: round-12 R12-2 — ``RefusedStructure`` grew the deck measurements a
# refused piered viaduct is seated from (``abutment_lines``,
# ``deck_top_y_m``, the frame origin, the deck resources).  Adding a
# field to a PICKLED record is a cache-version event; a v15 pickle
# restores those fields as the class default ``None``, and the R12-2
# seat would then read every refused viaduct as "no measurable deck"
# and hand it back to the per-structure y-bake it exists to replace.
# 17: amendment 3 — ``RefusedStructure`` grew ``deck_members``
# (per-resource deck end lines + effective crests).  A v16 pickle
# restores it as the class default ``()``, and ``has_measurable_deck``
# now reads THAT, so every refused viaduct would fall back.
# 18: the KDFW contract refusals (docs/specs/kdfw-bridge-refusal-spec.md
# clause 1, ``object_terrain_features.contract_refusal_reason``) — an
# implausibly-scaled DECK_CARRIED verdict on profile-fallback evidence,
# and a girder clearance under BRIDGE_ROAD_CLEARANCE_MINIMUM_M, are
# refused a terrain feature instead of emitted.  Exactly the version-15
# situation: a v17 result for an unedited pack still carries KDFW's
# 2,849.6 x 820.6 m pavement-inset "deck", whose 193 hard deck-end pins
# at 183.29 inverted the final band — the fingerprint covers the PACK,
# and cannot see a classifier rule change, so the version is what
# retires the record.
# 19: A DECAL IS NOT A SOLID (spec docs/specs/
# tunnel-trench-law-and-basin-floor-spec.md §2.1) —
# ``StructureGroundInterface.solid_minimum_y_m`` now carries the frame's
# FLOOR WITNESS (parts with no vertical extent excluded) rather than its
# bare vertex minimum.  Exactly the version-14/15 situation: the field
# already exists, so a v18 pickle restores a value that LOOKS valid and
# the fingerprint covers the PACK, not the classifier rule — a v18 LEMD
# result still carries −50.0 m from two 4-vertex VOR ground decals and
# still cuts the basin 51.5 m below its own rim.  The version is what
# retires it.
# 20 -> 21: ``ClassificationResult`` grew ``below_grade_regions`` (spec
# docs/specs/basin-region-footprint-spec.md §2.1, owner ruling
# 2026-08-26).  The version-14 situation exactly: a v20 pickle restores
# a frozen dataclass from its recorded ``__dict__``, which has no such
# key, so the result reads back with the CLASS DEFAULT ``[]`` — the
# basin records would then keep their pool-derived footprints and LEMD
# would go on cutting 36.5 % of its own authored pit on a warm cache,
# with nothing in the log to say why.  Adding a field to a PICKLED
# record is a cache-version event; nothing else in the fingerprint can
# see it.
# 21 -> 22: the region UNION was repaired (``object_terrain_features.
# _union_all_repairing`` / ``_repaired_area_polygon``).  The version-19
# situation, and the sharpest instance of it yet: a v21 result has the
# ``below_grade_regions`` FIELD and it reads back EMPTY, because
# ``shapely.union_all`` raised ``TopologyException: side location
# conflict`` on a set containing one zero-area wall-only member and the
# derivation caught it into "no regions" (measured at LEMD 2026-08-26 —
# the whole 27,857 m² T4S ring vanished, and a v21 sidecar reproduces
# that on every warm build).  The value LOOKS valid and the fingerprint
# covers the PACK, not the classifier's arithmetic, so the version is
# what retires it.
# 22 -> 23: each ``BelowGradeRegion`` now carries its ABOVE-GRADE
# COVERAGE FRACTION and its contributors' clipped areas (spec
# docs/specs/basin-region-founding-spec.md §2.1).  The version-21
# situation once more: a v22 pickle restores the frozen dataclass from a
# ``__dict__`` with no such keys, so the coverage reads back as the class
# default ``None`` — which is UNKNOWN, and unknown REFUSES founding.  A
# warm v22 sidecar would therefore silently disable the whole founding
# limb on exactly the packs it exists for.  The version is what retires
# it; nothing else in the fingerprint can see a new field.
# 23 -> 24: an admitted ``BelowGradeRegion``'s ``polygon`` is now
# COMPLETED up its own entrance ramp to the ground-contact band
# (``object_terrain_features.regions_completed_to_ramp_reach``, spec
# docs/specs/lemd-basin-trench-ramp-extension-spec.md).  No FIELD moves,
# so this is not the version-21 class — but the ring itself is a
# different shape, and the ring IS the cut.  A warm v23 sidecar would go
# on serving the pre-completion ring, cutting the pit short of the ramp
# the owner reported terrain poking through, with nothing in the log to
# say why.  The fingerprint covers the pack and the gates, never the
# derivation's own arithmetic; the version is what retires it.
# 24 -> 25: ``BelowGradeRegion`` and ``TunnelStructure`` each gained a
# ``ramp_reach_corridor`` (spec lemd-basin-trench-ramp-extension
# Amendment 1 §2) — the version-21 class exactly: a v24 pickle restores
# the frozen dataclass from a ``__dict__`` with no such key, so the
# corridor reads back as the class default ``None``, which is NO RAMP,
# and a warm v24 sidecar would silently disable the whole plate limb on
# the one pack it exists for.  The version is what retires it; nothing
# else in the fingerprint can see a new field.
# 25 -> 26: the corridor DERIVATION changed — ``_ramp_lobes_of`` now
# separates the shell's own BATTER from its ramp, so the same field
# holds a different (798 m² not 1,779 m²) polygon.  CAUGHT IN THE ACT,
# 2026-08-28: a v25 sidecar written by an earlier arm was served to the
# next build, which then emitted the batter annulus and reported it in
# the log as if freshly derived.  The fingerprint covers the PACK and
# the GATES, never the derivation's own arithmetic; the version is the
# only thing that can retire a ring or a corridor whose SHAPE changed.
# v27 (2026-08-28, the PAD-AUTHORITY CARVE): the facility payload grew
# ``carve_corridor_rings_longitude_latitude`` — the ramp corridor the
# post-mesh G instrument scopes its sample band by (spec
# ``docs/specs/lemd-pad-authority-carve-spec.md`` §4).  A v26 sidecar
# carries no such key, so a warm one would hand the instrument an
# UNSCOPED band and call it scoped.  The version, not the gate salt, is
# what retires a payload whose SHAPE changed.
_CLASSIFICATION_CACHE_VERSION = 27

# Sidecar file name prefix; the full name carries the DSF stem
# (``o4_object_terrain_classification_<dsf-stem>.cache``).  Lives under
# ``dsf_reader.airport_mod_cache_dir`` — NOT in the airport pack (user
# ruling 2026-07-15: Ortho4XP-only caches stay out of scenery pack
# folders; the ``.anchor_bak`` object BACKUPS explicitly stay in-pack
# next to the files they back up).
_CLASSIFICATION_SIDECAR_PREFIX = "o4_object_terrain_classification"

# Pre-ruling in-pack sidecar name, removed on sight (legacy cleanup).
_CLASSIFICATION_LEGACY_SIDECAR_NAME = (
    "o4_object_terrain_classification.cache"
)


def _classification_sidecar(dsf_path, pack_root, pavement_polygons,
                            apt_dat_path=None):
    """Sidecar path + input fingerprint for the pack classification
    cache.  The fingerprint covers everything the classification reads:

    * the overlay DSF (path, size, mtime) — any airport layout change
      necessarily rewrites it (user ruling 2026-07-10);
    * the airport's ``apt.dat`` (size, mtime) when known — layout edits
      usually rewrite it too, and the pavement evidence derives from it;
    * every ``.obj`` under the pack root, keyed on its PRISTINE state —
      the ``.anchor_bak`` original where the engine's own y-bake mutated
      the file, the live file otherwise (owner ruling 2026-08-13,
      "AIRPORT DERIVED CACHES KEY ON PRISTINE INPUTS"; one
      implementation in
      ``object_rebake.pristine_object_fingerprint_entries``).  It is
      needed BESIDE the DSF check because an external object-geometry
      edit changes no DSF byte — but OUR OWN y-bake rewrites must NOT
      invalidate it: the classifier reads the ``.anchor_bak`` original
      too (ruling R1 parity in
      ``_load_object_geometry_by_resource``), so a baked live file was
      never an input to this result;
    * the pavement-coverage evidence (well-known-binary hash of the
      rings — contract selection depends on it);
    * :data:`_CLASSIFICATION_CACHE_VERSION`.

    O3 verdict (spec section 7, verified 2026-07-11): the fingerprint
    DELIBERATELY does NOT include the built mesh or the ``.alt`` elevation
    raster, and that is CORRECT.  The classifier's output is a geometric
    bridge/tunnel/draped classification (plus the DSF-fixture absolute deck
    MSL) — it samples no terrain elevation (``object_terrain_features`` does
    "no mesh sampling"), so a rebuilt mesh with unchanged pack files cannot
    change the classification and reusing it is sound.  The elevation-
    DEPENDENT artefact is the Phase 2 object y-bake, and that is recomputed
    against the current mesh on EVERY mesh build (``post_mesh`` reruns
    ``structure_deltas`` fresh and ``object_rebake.apply`` re-reads geometry
    from the ``.anchor_bak`` backup; the reanchor provenance sidecar is a
    diagnostic, not a rebuild-skip gate), so no stale delta is ever reused
    across a mesh change — the ``O4_AUTO_PATCH_REBUILD=1`` gotcha class does
    not apply here.

    The sidecar lives under ``dsf_reader.airport_mod_cache_dir`` (user
    ruling 2026-07-15 — Ortho4XP-only caches stay out of scenery pack
    folders); a pre-ruling in-pack sidecar found at the pack root is
    removed here so the pack stays clean.

    Returns ``(None, None)`` when no pack root is known (nowhere to key
    a sidecar on) or fingerprinting fails."""
    cache_directory = dsf_reader.airport_mod_cache_dir(pack_root)
    if cache_directory is None:
        return None, None
    # Legacy cleanup: exactly the old filename at the pack root, every
    # OSError swallowed.
    try:
        os.remove(os.path.join(pack_root,
                               _CLASSIFICATION_LEGACY_SIDECAR_NAME))
    except OSError:
        pass
    import hashlib
    digest = hashlib.sha1()
    try:
        digest.update(str(_CLASSIFICATION_CACHE_VERSION).encode())
        # The section 3.4 gate changes which resources the classifier
        # feeds to the R4 exclusion list — a flip must miss the cache.
        digest.update(
            f"split-level:{config.OBJECT_SPLIT_LEVEL_TERRAIN}".encode()
        )
        # Same reason for the basin-trench gate: it decides whether a
        # carved open pit joins those exclusions.
        digest.update(
            f"basin-trench:{config.OBJECT_BASIN_TRENCH}".encode()
        )
        # ...and the pool-scoping gate: it decides which resources SEED an
        # open-pit component, so a flip changes the classification itself
        # (LEMD: a 2,078,883 m² basin against a 12,251 m² one).
        digest.update(
            f"basin-pool-scoping:{config.BASIN_POOL_SCOPING}".encode()
        )
        # ...and the region-footprint gate: it decides whether the
        # classification carries below-grade REGIONS at all, which is
        # the cut shape itself (spec basin-region-footprint §2.1).
        digest.update(
            f"basin-region-footprint:{config.BASIN_REGION_FOOTPRINT}".encode()
        )
        # ...and the region-FOUNDING gate beside it: it decides whether an
        # unmatched region becomes a basin at all, i.e. whether a pit is
        # cut where the pool partition saw no structure (spec
        # basin-region-founding §2.4).  Salted exactly like its
        # predecessor so a flip can never be answered from a warm sidecar.
        digest.update(
            f"basin-region-founding:{config.BASIN_REGION_FOUNDING}".encode()
        )
        # ...and the RAMP REACH gate (spec lemd-basin-trench-ramp-
        # extension): it decides how far an admitted region's ring runs
        # up its own entrance ramp, i.e. the cut shape itself, so a flip
        # must never be answered from a warm sidecar either.
        digest.update(
            f"basin-region-ramp-reach:"
            f"{config.BASIN_REGION_RAMP_REACH}".encode()
        )
        # ...and the RAMP-REACH PLATE gate (Amendment 1 §2): it decides
        # whether the classification carries a ramp CORRIDOR at all, and
        # the corridor is emitted terrain.
        digest.update(
            f"basin-ramp-reach-plate:"
            f"{config.BASIN_RAMP_REACH_PLATE}".encode()
        )
        # ...and the PAD-AUTHORITY CARVE gate (spec ``docs/specs/lemd-
        # pad-authority-carve-spec.md``): it is the OTHER reader of
        # ``basin_ramp_corridor_carried``, so it too decides whether the
        # classification carries a ramp CORRIDOR at all — and the
        # corridor is emitted terrain.  Salted separately from the plate
        # gate because the two arms are distinguishable builds.
        digest.update(
            f"basin-pad-authority-carve:"
            f"{config.BASIN_PAD_AUTHORITY_CARVE}".encode()
        )
        # ...and the GROUP-SEAT gate (docket B, basin-group-seat §2.6): it
        # decides how the facility records this classification feeds are
        # GROUPED (one per connected body component, not one per pack
        # datum), so a flip must never be answered from a warm sidecar.
        digest.update(
            f"basin-group-seat:{config.BASIN_GROUP_SEAT}".encode()
        )
        dsf_stat = os.stat(dsf_path)
        digest.update(
            f"{os.path.basename(dsf_path)}:{dsf_stat.st_size}"
            f":{dsf_stat.st_mtime}".encode()
        )
        if apt_dat_path:
            try:
                apt_dat_stat = os.stat(apt_dat_path)
                digest.update(
                    f"apt:{apt_dat_stat.st_size}"
                    f":{apt_dat_stat.st_mtime}".encode()
                )
            except OSError:
                digest.update(b"apt:unreadable")
        from .object_rebake import pristine_object_fingerprint_entries
        for entry in sorted(
                pristine_object_fingerprint_entries(pack_root)):
            digest.update(entry.encode())
        if pavement_polygons:
            for polygon in pavement_polygons:
                try:
                    digest.update(polygon.wkb)
                except Exception:
                    digest.update(b"?")
        else:
            digest.update(b"no-pavement-evidence")
    except OSError:
        return None, None
    dsf_stem = os.path.splitext(os.path.basename(dsf_path))[0]
    return (
        os.path.join(
            cache_directory,
            f"{_CLASSIFICATION_SIDECAR_PREFIX}_{dsf_stem}.cache",
        ),
        digest.hexdigest(),
    )


def attach_bridge_classification(layout, xplane_root: str):
    """Classify the airport pack's bridge/tunnel objects and cache the
    result (plus sibling road networks) on ``layout``.

    Gated by ``config.OBJECT_BRIDGE_TERRAIN`` OR
    ``config.OBJECT_TUNNEL_TERRAIN`` (feature A shares this one classifier
    pass — spec section 3.1): with BOTH gates OFF this is a complete no-op —
    nothing is read, nothing is attached, and every emitter takes its
    unchanged legacy path (flag-off byte identity).

    Returns the :class:`object_terrain_features.ClassificationResult` (also
    cached on ``layout``) or ``None`` when both gates are off or no overlay
    DSF could be located.

    Idempotent: stage 2 attaches PRE-solve (the pin writers need the
    records before the seam hook), and the post-solve emitter hook calls
    this again as a fallback — a result already cached on the layout is
    returned as-is, never recomputed."""
    if not (config.OBJECT_BRIDGE_TERRAIN or config.OBJECT_TUNNEL_TERRAIN):
        return None
    cached = getattr(layout, CLASSIFICATION_ATTRIBUTE, None)
    if cached is not None:
        return cached
    apt_dat_path = getattr(layout, "apt_dat_path", None)
    anchor = getattr(layout, "anchor", None)
    if not apt_dat_path or anchor is None:
        return None
    anchor_latitude, anchor_longitude = anchor[0], anchor[1]

    dsf_path = dsf_reader.find_associated_dsf(
        apt_dat_path, anchor_latitude, anchor_longitude
    )
    if dsf_path is None or not os.path.isfile(dsf_path):
        UI.vprint(
            1,
            "   [object-bridge] no overlay DSF for "
            f"{getattr(layout, 'icao', '?')} — feature B inactive",
        )
        return None

    # ── Pack-sidecar classification cache (user directive 2026-07-10,
    # default ON) ──  The read → load → classify chain is recomputed
    # byte-identically on every build of an unchanged pack.  The
    # FINISHED result (R4 family expansion included) is pickled as a
    # sidecar under the data root's ``Airport_mod_cache/<pack>/`` (user
    # ruling 2026-07-15: never inside the pack) guarded by a fingerprint
    # of everything the classification reads: the overlay DSF, every
    # ``.obj`` in the pack (a Phase 2 y-bake rewrite invalidates
    # automatically), the pavement-coverage evidence, and a code
    # version salt.  ``O4_OBJECT_CLASSIFICATION_CACHE=0`` disables.
    pavement_polygons = _pavement_polygons_longitude_latitude(layout)
    pack_root_early = dsf_reader._pack_root_for_dsf(dsf_path)
    sidecar_path = None
    fingerprint = None
    if os.environ.get("O4_OBJECT_CLASSIFICATION_CACHE", "1") == "1":
        import pickle
        sidecar_path, fingerprint = _classification_sidecar(
            dsf_path, pack_root_early, pavement_polygons,
            apt_dat_path=apt_dat_path,
        )
        if sidecar_path and fingerprint and os.path.isfile(sidecar_path):
            try:
                with open(sidecar_path, "rb") as sidecar_file:
                    payload = pickle.load(sidecar_file)
                if payload.get("fingerprint") == fingerprint:
                    UI.vprint(
                        1,
                        "   [object-bridge] classification read from the "
                        "pack sidecar cache (fingerprint match)",
                    )
                    return _attach_classification_tail(
                        layout, payload["result"], xplane_root,
                        anchor_latitude, anchor_longitude,
                    )
                UI.vprint(
                    1,
                    "   [object-bridge] pack sidecar cache STALE "
                    "(pack edited since it was written) — reclassifying",
                )
            except Exception:
                pass

    lines = dsf_reader._load_dsf_text(dsf_path)
    if not lines:
        UI.vprint(
            1,
            "   [object-bridge] DSF text unavailable (missing file or "
            "DSFTool) — feature B inactive",
        )
        return None

    all_placements = obj8_reader.read_dsf_object_placements(
        lines,
        accept_resource=lambda resource: resource.lower().endswith(".obj"),
        include_object_msl=True,
    )
    mean_sea_level_placements = [
        placement
        for placement in all_placements
        if placement.placement_kind == "OBJECT_MSL"
    ]
    terrain_placements = [
        placement
        for placement in all_placements
        if placement.placement_kind != "OBJECT_MSL"
    ]
    if not terrain_placements:
        return None

    pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
    geometry_by_resource = _load_object_geometry_by_resource(
        terrain_placements, pack_root, xplane_root
    )
    if not geometry_by_resource:
        return None

    # (``pavement_polygons`` computed above, ahead of the sidecar
    # fingerprint — contract selection depends on it.)
    if pavement_polygons is None:
        UI.vprint(
            2,
            "   [object-bridge] no draped pavement available at the "
            "classifier hook — contract falls back to deck-crest height",
        )

    result = object_terrain_features.classify_object_terrain_features(
        terrain_placements,
        geometry_by_resource,
        pavement_polygons_longitude_latitude=pavement_polygons,
        mean_sea_level_placements=mean_sea_level_placements,
        pack_root=pack_root or "",
        split_level_terrain_enabled=config.OBJECT_SPLIT_LEVEL_TERRAIN,
        basin_trench_enabled=config.OBJECT_BASIN_TRENCH,
    )

    # Ruling R4 breadth: pull the whole anchor family of every consumed
    # structure onto the exclusion list (sibling parts the classifier's
    # records do not carry — see ANCHOR_FAMILY_RADIUS_M).
    family_added = _expand_exclusions_to_anchor_families(
        result, terrain_placements, pack_root or ""
    )
    if family_added:
        UI.vprint(
            1,
            f"   [object-bridge] R4 exclusions widened to {len(family_added)} "
            f"anchor-family sibling resource(s): "
            f"{[r.split('/')[-1] for r in family_added]}",
        )

    if sidecar_path is not None and fingerprint is not None:
        import pickle
        try:
            os.makedirs(os.path.dirname(sidecar_path), exist_ok=True)
            with open(sidecar_path, "wb") as sidecar_file:
                pickle.dump(
                    {"fingerprint": fingerprint, "result": result},
                    sidecar_file,
                )
            UI.vprint(
                1,
                "   [object-bridge] classification written to the pack "
                f"sidecar cache ({os.path.basename(sidecar_path)})",
            )
        except Exception:
            pass

    return _attach_classification_tail(
        layout, result, xplane_root, anchor_latitude, anchor_longitude
    )


def _attach_classification_tail(layout, result, xplane_root,
                                anchor_latitude, anchor_longitude):
    """Common tail of :func:`attach_bridge_classification` for both the
    fresh-classify and lab-cache paths: cache on the layout, discover
    sibling road networks and route lines, log the summary."""
    setattr(layout, CLASSIFICATION_ATTRIBUTE, result)

    tile_lat = int(math.floor(anchor_latitude))
    tile_lon = int(math.floor(anchor_longitude))
    road_networks = _discover_sibling_road_networks(
        xplane_root, tile_lat, tile_lon
    )
    setattr(layout, ROAD_NETWORKS_ATTRIBUTE, road_networks)
    setattr(
        layout, ROUTE_LINES_ATTRIBUTE,
        _raw_route_lines_layout_meters(layout),
    )

    _log_classification_summary(
        getattr(layout, "icao", "?"), result, road_networks
    )
    return result


def _raw_route_lines_layout_meters(layout) -> list:
    """The RAW apt.dat routing polylines (row-1202 taxi edges + row-1206
    truck edges) as layout-meter LineStrings — the road-carried
    discriminator's primary evidence (stage 2b iteration 4).

    The QUALIFIED centerline set (``layout.apt_taxi_centerlines``) is the
    wrong evidence: at KBNA the Murfreesboro truck runs are disqualified
    before reaching it (0 centerlines within the reach band of either
    deck), while the raw 1206 rows genuinely cross — measured: 3 and 5
    truck edges in the two decks' bands, 3 taxi edges at taxiway-L, zero
    of anything at the Crossing_Bridge road overpass.  Empty list when
    the apt.dat carries no routing rows or cannot be read."""
    from shapely.geometry import LineString

    apt_dat_path = getattr(layout, "apt_dat_path", None)
    icao = getattr(layout, "icao", None)
    if not apt_dat_path or not icao:
        return []
    try:
        from .apt_dat_reader import load_airport
        airport = load_airport(apt_dat_path, icao)
    except (OSError, ValueError):
        return []
    if airport is None:
        return []
    nodes = airport.taxi_nodes  # dict id -> TaxiNode
    lines: list = []
    for edge in list(airport.taxi_edges) + list(airport.truck_edges):
        node_a = nodes.get(edge.node_from)
        node_b = nodes.get(edge.node_to)
        if node_a is None or node_b is None:
            continue
        try:
            lines.append(LineString([
                layout.ll_to_m(node_a.lat, node_a.lon),
                layout.ll_to_m(node_b.lat, node_b.lon),
            ]))
        except (ValueError, TypeError):
            continue
    return lines


# Bump together with classifier-behavior changes that
# ``_CLASSIFICATION_CACHE_VERSION`` alone would not capture for the
# post-mesh exclusion path (both versions salt the exclusion cache key).
# v3 (2026-08-09, spec basin-rim-flush-seating section 2.1e item E1): the
# basin gate is now threaded into the post-mesh classify call.  Every v2
# entry was computed with that gate effectively OFF while the flag rode
# the digest as ON, so a v2 entry is a WRONG answer for an unchanged pack
# — the version, not the digest, is what retires them.
# v4 (2026-08-09, section 2.2): the payload carries the BASIN RIM-FLUSH
# FACILITY records beside the exclusion pairs — one classify feeds both
# post-mesh consumers.  A v3 entry has no facilities key at all, and
# reading it as "no basin facility" would silently leave every
# anchor-inside basin unbaked on a warm cache.
# v5 (2026-08-10, round-6 R6-3): the payload gains the BRIDGE ABUTMENT
# SEAT candidate records — same reasoning, one classify, three consumers.
# A v4 entry has no candidates key, and reading it as "no candidate"
# would leave every flush-deck bridge over water draped on a warm cache,
# which is exactly the residual R6-3 exists to close.
# v6 (2026-08-11, round 12): the candidate records changed SHAPE and
# MEANING — ``object_resources`` is now the whole anchor family (R12-2
# member completeness), the payload gains ``seat_source`` /
# ``deck_object_resources`` and the refused-viaduct candidates, the
# exclusion set now routes those families away from the generic y-bake,
# and the payload carries the round-12 bridge FINDINGS.  A v5 entry
# carries the narrow member set and no refused family: read on a warm
# cache it would leave OTHH_Bridge_04_LOD0_004 unseated and Bridge_02/
# 03/06 torn — the two defects round 12 closes.
# v7 (2026-08-11, amendment 3): a refused-viaduct candidate carries
# ``deck_member_records`` — the PER-MEMBER deck end lines and crests the
# seat now measures from — and no longer carries the merged min-rect
# pair at all.  A v6 entry hands the seat the mega-rect chord (175 m,
# canal-parallel at OTHH), which is the instrument this amendment
# retires; read warm it would silently restore it.
# v8 (2026-08-26, spec basin-region-footprint): the basin rim-flush
# FACILITY records carry ``solid_minimum_y_m`` = the emitter's floor key,
# and both the key (open pits now key on the deepest genuine solid) and
# the body outline (widened to the below-grade region) changed under the
# owner's LEMD T4S rulings.  A v7 entry seats every basin object against
# the retired Amendment-3 floor over the pool-derived outline — read warm
# it would silently reinstate exactly what this round retires.
# v9 (2026-08-27, spec basin-region-founding): the payload can now carry
# basin rim-flush facilities that exist ONLY because an unmatched
# below-grade region FOUNDED a record.  A v8 entry has no such facility
# and reading it warm would leave a founded pit's objects unseated over
# terrain that was nevertheless cut — the two halves of one round
# disagreeing, which is the lockstep this producer exists to guarantee.
# v10 (2026-08-27, spec basin-group-seat §2.1 + Amendment 2): the facility
# records are SPLIT per connected body component and degenerate components
# are dropped, so a payload's facility LIST is a different object under
# this round than under the last one.  MEASURED: a v9 entry for LEMD
# carries TWO T4S facilities — the real 27,806 m² ring and a 1.6e-13 m²
# sliver — and read warm it re-creates the double-seat the amendment
# exists to end (the overlap backstop then refuses the sliver, which is
# the backstop doing the amendment's job on stale data).
_EXCLUSION_CACHE_VERSION = 10


def _cached_post_mesh_records(
    pack_root: str,
    terrain_placements,
    mean_sea_level_placements,
    geometry_by_resource,
    compute,
) -> tuple[set[tuple[str, str]], list, list, list]:
    """Content-hash sidecar cache for the post-mesh classifier reads: the
    ruling-R4 exclusion set, the section-2.2 basin rim-flush facility
    records, the bridge abutment-seat candidates AND the round-12 bridge
    findings (``compute`` returns all four, from ONE classification).

    They are a pure function of the DSF placements, the loaded OBJ8
    geometry and the classifier version — never the mesh — yet were
    recomputed on every mesh build (profiled 2026-07-15: 46 s of the
    KBNA rebake, the classifier being the bulk).  Keyed by CONTENT
    (placements + a digest of each loaded geometry), not file mtimes:
    the Phase 2 y-bake rewrites pack ``.obj`` files each run, churning
    mtimes while the classification inputs stay put.  Stored as JSON
    under ``Airport_mod_cache/<pack>/``.  ``O4_OBJECT_EXCLUSION_CACHE=0``
    disables; any read problem silently recomputes.
    """
    cache_directory = dsf_reader.airport_mod_cache_dir(pack_root)
    if (
        cache_directory is None
        or os.environ.get("O4_OBJECT_EXCLUSION_CACHE", "1") != "1"
    ):
        return compute()

    digest = hashlib.sha1()
    digest.update(
        repr(
            (
                _EXCLUSION_CACHE_VERSION,
                _CLASSIFICATION_CACHE_VERSION,
                pack_root,
                # Section 3.4 gate: decides whether feature-C ground
                # interfaces join the exclusion set — key it.
                config.OBJECT_SPLIT_LEVEL_TERRAIN,
                # Basin-trench gate: decides whether carved open pits
                # join it — same reason.
                config.OBJECT_BASIN_TRENCH,
                # Bridge-terrain gate (R6-3): decides whether the
                # abutment-seat candidate list is populated at all.
                config.OBJECT_BRIDGE_TERRAIN,
                # The two LEMD T4S gates (2026-08-26): the first decides
                # the basin BODY OUTLINE the facilities carry, the
                # second its FLOOR KEY — both are in the payload.
                config.BASIN_REGION_FOOTPRINT,
                config.BASIN_OPEN_PIT_DECK_KEY,
                # ...and the founding gate: a founded basin is a FACILITY
                # in this payload that does not exist without it.
                config.BASIN_REGION_FOUNDING,
                # ...and the ramp-reach gate: it decides the BODY OUTLINE
                # every facility in this payload carries (the ring
                # followed up its own entrance ramp).
                config.BASIN_REGION_RAMP_REACH,
                # ...and the ramp-reach PLATE gate: the corridor beside
                # the body is emitted terrain, so a flip changes what a
                # post-mesh decision is derived from.
                config.BASIN_RAMP_REACH_PLATE,
                # ...and the PAD-AUTHORITY CARVE gate, the corridor's
                # other reader: it decides whether a facility in this
                # payload carries a carve corridor, which is exactly what
                # the post-mesh G instrument scopes its band by.
                config.BASIN_PAD_AUTHORITY_CARVE,
                # ...and the group-seat gate (docket B): it decides how
                # many facilities the payload carries (one per connected
                # body component) and which body each one owns.
                config.BASIN_GROUP_SEAT,
            )
        ).encode()
    )
    for placement in terrain_placements:
        digest.update(repr(placement).encode())
    digest.update(b"|mean-sea-level|")
    for placement in mean_sea_level_placements:
        digest.update(repr(placement).encode())
    for resource_path in sorted(geometry_by_resource):
        digest.update(resource_path.encode())
        digest.update(
            hashlib.sha1(
                pickle.dumps(geometry_by_resource[resource_path])
            ).digest()
        )
    cache_path = os.path.join(
        cache_directory,
        "o4_object_exclusions_%s.cache" % digest.hexdigest()[:16],
    )

    if os.path.isfile(cache_path):
        try:
            with open(cache_path) as handle:
                payload = json.load(handle)
            if payload.get("version") == _EXCLUSION_CACHE_VERSION:
                return (
                    {(pair[0], pair[1]) for pair in payload["exclusions"]},
                    [
                        BasinRimFlushFacility.from_json(entry)
                        for entry in payload["basin_facilities"]
                    ],
                    [
                        BridgeAbutmentSeatCandidate.from_json(entry)
                        for entry in payload["bridge_abutment_seats"]
                    ],
                    list(payload.get("bridge_findings", ())),
                )
        except Exception:
            pass  # corrupt/unreadable — recompute below

    (
        exclusions,
        basin_facilities,
        abutment_candidates,
        bridge_findings,
    ) = compute()
    try:
        os.makedirs(cache_directory, exist_ok=True)
        temporary_path = cache_path + ".tmp"
        with open(temporary_path, "w") as handle:
            json.dump(
                {
                    "version": _EXCLUSION_CACHE_VERSION,
                    "exclusions": sorted(exclusions),
                    "basin_facilities": [
                        facility.to_json() for facility in basin_facilities
                    ],
                    "bridge_abutment_seats": [
                        candidate.to_json()
                        for candidate in abutment_candidates
                    ],
                    "bridge_findings": bridge_findings,
                },
                handle,
            )
        os.replace(temporary_path, cache_path)
    except OSError:
        pass  # best effort — the records are already computed
    return (
        exclusions, basin_facilities, abutment_candidates, bridge_findings
    )


def _pipeline_verdicts_by_resource(dsf_path: str, pack_root: str) -> dict:
    """``{resource_path: (contract, pavement_coverage_fraction)}`` from
    the PIPELINE-time classification sidecar for this DSF, or ``{}``.

    Best effort by design: the sidecar is fingerprinted against the
    pavement evidence, which post-mesh does not have, so its fingerprint
    is neither checked nor checkable here.  Nothing is decided from what
    it says — R12-3 only RECORDS the disagreement."""
    cache_directory = dsf_reader.airport_mod_cache_dir(pack_root)
    if not cache_directory or not dsf_path:
        return {}
    dsf_stem = os.path.splitext(os.path.basename(dsf_path))[0]
    sidecar_path = os.path.join(
        cache_directory,
        f"{_CLASSIFICATION_SIDECAR_PREFIX}_{dsf_stem}.cache",
    )
    if not os.path.isfile(sidecar_path):
        return {}
    try:
        with open(sidecar_path, "rb") as sidecar_file:
            payload = pickle.load(sidecar_file)
        result = payload["result"]
    except Exception:
        return {}  # unreadable / older shape — no finding, never a guess
    verdicts: dict = {}
    for bridge in getattr(result, "bridges", None) or []:
        for resource in bridge.object_resources:
            verdicts[resource] = (
                bridge.contract,
                bridge.pavement_coverage_fraction,
            )
    return verdicts


def bridge_verdict_frame_split_findings(
    result, dsf_path: str, pack_root: str
) -> list:
    """THE FRAME SPLIT, RECORDED (round-12 R12-3).

    Post-mesh classification runs with
    ``pavement_polygons_longitude_latitude=None`` — the pipeline-time
    layout is long gone — so the contract falls back to the deck-crest
    height rule.  Pipeline-time classification runs WITH the draped
    pavement.  Two frames, two verdicts, one pack: at OTHH the height
    fallback says TERRAIN_CARRIED where a pipeline-time coverage of 0.0
    says AMBIGUOUS.

    One counted finding per resource that disagrees, carrying BOTH
    verdicts and BOTH coverage inputs.  Which verdict is USED does not
    change here — with R12-1 the TERRAIN_CARRIED seat is right for this
    class, and re-sourcing verdicts is a separate design decision."""
    pipeline = _pipeline_verdicts_by_resource(dsf_path, pack_root)
    if not pipeline:
        return []
    findings: list = []
    for bridge in getattr(result, "bridges", None) or []:
        for resource in sorted(bridge.object_resources):
            if resource not in pipeline:
                continue
            pipeline_contract, pipeline_coverage = pipeline[resource]
            if pipeline_contract == bridge.contract:
                continue
            findings.append({
                "finding": BRIDGE_VERDICT_FRAME_SPLIT_FINDING,
                "resource": resource,
                "post_mesh_contract": bridge.contract,
                "pipeline_contract": pipeline_contract,
                "post_mesh_coverage_fraction": (
                    bridge.pavement_coverage_fraction),
                "pipeline_coverage_fraction": pipeline_coverage,
            })
    return findings


@dataclass(frozen=True)
class PostMeshObjectTerrainRecords:
    """Everything the Phase 2 post-mesh pass needs from the object-terrain
    classifier, from ONE classification of one overlay DSF.

    ``exclusions`` is the ruling-R4 set the GENERIC y-bake must not
    touch; ``basin_rim_flush_facilities`` is the section-2.2 dedicated
    class.  Basin members stay on BOTH lists deliberately: they are
    withheld from the generic median/A3/threshold arithmetic (which
    section 2.2 item 5 says does not run for this class) and seated by
    the dedicated law instead.

    ``bridge_abutment_seat_candidates`` (R6-3, round-6 OTHH residuals
    spec) is the same pattern for TERRAIN_CARRIED bridges with certified
    abutments: still excluded from the generic y-bake, ROUTED to the
    dedicated abutment-grade seat, which then either seats them or leaves
    them draped exactly as today.  Candidacy is decided here — from
    geometry the classifier already has — and QUALIFICATION post-mesh,
    where the built mesh can answer how far below the abutments the
    anchor actually sits.

    ``bridge_findings`` (round 12) are the counted findings the candidacy
    pass minted — ``bridge_seat_fallback`` (R12-2) and
    ``bridge_verdict_frame_split`` (R12-3).  Findings only: nothing on
    this list changes a verdict or a seat."""

    exclusions: set[tuple[str, str]]
    basin_rim_flush_facilities: list
    bridge_abutment_seat_candidates: list = field(default_factory=list)
    bridge_findings: list = field(default_factory=list)


def post_mesh_object_terrain_records(
    dsf_path: str,
    xplane_root: str | None,
    pack_root: str | None = None,
) -> PostMeshObjectTerrainRecords:
    """The ruling-R4 exclusion set for one overlay DSF — every
    ``(pack_root, resource_path)`` pair whose terrain is carved or seated
    to match the object (a structure consumed by terrain feature A or B),
    for :func:`post_mesh.discover_and_rebake_airport` to drop from the
    Phase 2 y-bake, terrain-to-object and object-to-terrain corrections
    never stacking — AND the section-2.2 basin rim-flush facilities, AND
    the R6-3 bridge abutment-seat candidates, from the same single
    classification.

    ONE classify, every consumer: a second call for the facilities or the
    candidates would re-run the classifier (the bulk of a 46 s KBNA
    rebake, profiled 2026-07-15) over identical inputs.

    Gate-checked: with ``O4_OBJECT_BRIDGE_TERRAIN``,
    ``O4_OBJECT_TUNNEL_TERRAIN`` and ``O4_OBJECT_BASIN_TRENCH`` ALL off
    this returns an empty set having read NOTHING (Phase 2 behaviour
    unchanged).  With any one gate on, it reruns
    the same cached read→load→classify chain as
    :func:`attach_bridge_classification` — deterministic over the same
    DSF, and the pipeline-time layout is gone by post-mesh time, so
    recomputing beats threading state.  Classification here passes
    ``pavement=None`` (the contract falls back to deck-crest height); the
    R4 exclusion list is contract-independent — every consumed structure
    is excluded whichever contract it classifies to — so the fallback
    cannot change the set's membership, only the (unused here) contract
    label.

    ``pack_root`` should be the same string the caller hands to
    ``discover_and_rebake_airport`` so the pair keys match exactly;
    defaults to ``dsf_reader._pack_root_for_dsf``.

    Feature A (W-T) shares this list: tunnel structures the classifier
    consumes land on the same exclusion list (spec section 3.3 step 5), so
    the gate below is an either-gate check.
    """
    # THE BASIN GATE JOINS THE DISJUNCTION (spec section 2.1e item E1).
    # The basin adapter is INDEPENDENT of the tunnel gate — proven by
    # ``test_tunnel_gate_off_does_not_disable_basins`` — so a tree with
    # both the bridge and tunnel features off but basins on still CARVES
    # basin terrain while this returned an empty set, and every carved
    # basin's object was then y-baked onto the terrain we just cut it.
    # A gate that decides whether the exclusion is computed must name
    # every feature that does the carving.
    empty = PostMeshObjectTerrainRecords(exclusions=set(),
                                         basin_rim_flush_facilities=[])
    if not (config.OBJECT_BRIDGE_TERRAIN or config.OBJECT_TUNNEL_TERRAIN
            or config.OBJECT_BASIN_TRENCH):
        return empty
    if not dsf_path or not os.path.isfile(dsf_path):
        return empty
    lines = dsf_reader._load_dsf_text(dsf_path)
    if not lines:
        return empty
    all_placements = obj8_reader.read_dsf_object_placements(
        lines,
        accept_resource=lambda resource: resource.lower().endswith(".obj"),
        include_object_msl=True,
    )
    mean_sea_level_placements = [
        placement
        for placement in all_placements
        if placement.placement_kind == "OBJECT_MSL"
    ]
    terrain_placements = [
        placement
        for placement in all_placements
        if placement.placement_kind != "OBJECT_MSL"
    ]
    if not terrain_placements:
        return empty
    if pack_root is None:
        pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
    geometry_by_resource = _load_object_geometry_by_resource(
        terrain_placements, pack_root, xplane_root
    )
    if not geometry_by_resource:
        return empty

    def compute() -> tuple[set[tuple[str, str]], list, list, list]:
        result = object_terrain_features.classify_object_terrain_features(
            terrain_placements,
            geometry_by_resource,
            pavement_polygons_longitude_latitude=None,
            mean_sea_level_placements=mean_sea_level_placements,
            pack_root=pack_root or "",
            split_level_terrain_enabled=config.OBJECT_SPLIT_LEVEL_TERRAIN,
            # THE BASIN GATE, THREADED (spec section 2.1e item E1, defect
            # found 2026-08-09).  This call omitted it, so it defaulted to
            # FALSE here while the pipeline-side classifier (:682) passed
            # it — and the two disagreed about the same pack: stage 2b
            # (open-pit components) never ran at all, and stage 3's basin
            # limb never fired, so NO basin member reached the R4
            # exclusion set.  A basin whose terrain this build cut then
            # got its object y-baked to that cut terrain as well: exactly
            # the stacked terrain-to-object / object-to-terrain
            # correction R4 forbids.  The 2026-08-08 pad-request corpus
            # is the fingerprint — Dewatering pool shells raising cluster
            # requests at -13.6 m.  The cache digest already keyed on
            # this flag; only the call omitted it.
            basin_trench_enabled=config.OBJECT_BASIN_TRENCH,
        )
        _expand_exclusions_to_anchor_families(
            result, terrain_placements, pack_root or ""
        )
        candidates, findings = bridge_abutment_seat_candidates(
            result, terrain_placements
        )
        findings.extend(
            bridge_verdict_frame_split_findings(
                result, dsf_path, pack_root or ""
            )
        )
        exclusions = set(result.exclusions)
        # A family taking the rigid deck-top seat must not ALSO take the
        # generic per-structure bake — that is the stacked correction
        # ruling R4 forbids.  The seat's own member set is the authority
        # on who is routed, so the two can never drift.
        #
        # REFUSED VIADUCTS ARE ROUTED POST-MESH, NOT HERE (round-12
        # R12-2 as amended).  Whether a refused family seats depends on
        # whether its deck ends find LAND within the walk cap — a
        # question only the built mesh answers — so the seat pass makes
        # the claim and ``discover_and_rebake_airport`` widens the
        # exclusion set with it.  Routing them here, before the mesh,
        # would strand a family whose seat then declines: excluded from
        # the y-bake AND unseated, i.e. draped, which is worse than the
        # tear R12-2 closes.
        for candidate in candidates:
            if candidate.seat_source != SEAT_SOURCE_CLASSIFIED:
                continue
            for resource in candidate.object_resources:
                exclusions.add((pack_root or "", resource))
        return (exclusions,
                basin_rim_flush_facilities(result),
                candidates,
                findings)

    (
        exclusions,
        facilities,
        abutment_candidates,
        bridge_findings,
    ) = _cached_post_mesh_records(
        pack_root or "",
        terrain_placements,
        mean_sea_level_placements,
        geometry_by_resource,
        compute,
    )
    return PostMeshObjectTerrainRecords(
        exclusions=exclusions,
        basin_rim_flush_facilities=facilities,
        bridge_abutment_seat_candidates=abutment_candidates,
        bridge_findings=bridge_findings,
    )


def exclusion_set_for_dsf(
    dsf_path: str,
    xplane_root: str | None,
    pack_root: str | None = None,
) -> set[tuple[str, str]]:
    """The ruling-R4 exclusion set alone —
    :func:`post_mesh_object_terrain_records`'s ``exclusions``.  Kept as
    the name every existing caller and pin uses."""
    return post_mesh_object_terrain_records(
        dsf_path, xplane_root, pack_root
    ).exclusions


def _log_classification_summary(icao, result, road_networks) -> None:
    contract_counts: dict[str, int] = {}
    for bridge in result.bridges:
        contract_counts[bridge.contract] = (
            contract_counts.get(bridge.contract, 0) + 1
        )
    contract_summary = ", ".join(
        f"{contract}={count}"
        for contract, count in sorted(contract_counts.items())
    ) or "none"
    total_segments = sum(len(network.segments) for network in road_networks)
    UI.vprint(
        1,
        f"   [object-bridge] {icao}: "
        f"{len(result.bridges)} bridge(s) [{contract_summary}], "
        f"{len(result.tunnels)} tunnel(s), "
        f"{len(result.refusals)} refused, "
        f"{len(road_networks)} road network(s) "
        f"({total_segments} segment(s))",
    )
    for refusal in result.refusals:
        UI.vprint(
            2,
            "   [object-bridge] refused "
            f"{refusal.object_resources}: {refusal.reason}",
        )


# ---------------------------------------------------------------------------
# Feature A — object-derived tunnel terrain (spec section 3.3 + amendment A1,
# ruling R12).  Born pre-solve as first-class layout shapes, mirroring
# bridges.build_bridge_layout_shapes.
# ---------------------------------------------------------------------------


def _tunnel_footprint_longitude_latitude_parts(tunnel) -> list:
    """A tunnel's WHOLE-BODY OUTER footprint (amendment A1: the author
    cuts the entire body, not the mouths alone; user 2026-07-18: the cut
    must be flush with the OUTSIDE of the objects, so the roof slab —
    which spans the shell's outer walls — joins the drivable deck in the
    union, else ground pokes through the side walls) as shapely
    ``Polygon`` parts in LONGITUDE/LATITUDE.  Empty list on
    absent/degenerate geometry.

    THE one body-outline reader: the layout emitter takes these parts
    into layout metres (:func:`_tunnel_footprint_meters_parts`) and the
    post-mesh basin pass takes the same parts into its own metre frame.
    A second projection of "the body" is a second body."""
    from shapely.ops import unary_union
    from .object_terrain_features import frame_polygon_to_longitude_latitude

    frame_parts = [
        footprint for footprint in (
            tunnel.deck_footprint, tunnel.roof_footprint,
            getattr(tunnel, "solid_outline_footprint", None))
        if footprint is not None and not footprint.is_empty
    ]
    if not frame_parts:
        return []
    try:
        outer_footprint = unary_union(frame_parts)
    except Exception:
        outer_footprint = tunnel.deck_footprint
    if outer_footprint is None or outer_footprint.is_empty:
        return []
    footprint_longitude_latitude = frame_polygon_to_longitude_latitude(
        outer_footprint, tunnel.frame_origin_longitude_latitude
    )
    return (
        list(footprint_longitude_latitude.geoms)
        if footprint_longitude_latitude.geom_type == "MultiPolygon"
        else [footprint_longitude_latitude]
    )


def _tunnel_ramp_corridor_longitude_latitude_rings(tunnel) -> list:
    """A facility member's RAMP CORRIDOR as exterior rings in
    longitude/latitude, or ``[]`` (spec ``docs/specs/lemd-pad-authority-
    carve-spec.md`` §4).

    The lon/lat sibling of :func:`_tunnel_ramp_corridor_meters`, and it
    travels the SAME road that reader travels — the record's own
    ``ramp_reach_corridor`` through
    ``frame_polygon_to_longitude_latitude`` — so the corridor the
    emitter plates and the corridor the G instrument scopes by can never
    be two different polygons.  Deliberately NOT a body reader: the
    corridor never joins ``body_rings_longitude_latitude``.
    """
    from .object_terrain_features import frame_polygon_to_longitude_latitude

    corridor = getattr(tunnel, "ramp_reach_corridor", None)
    if corridor is None or corridor.is_empty:
        return []
    try:
        longitude_latitude = frame_polygon_to_longitude_latitude(
            corridor, tunnel.frame_origin_longitude_latitude)
    except Exception:                                     # pragma: no cover
        return []
    if longitude_latitude is None or longitude_latitude.is_empty:
        return []
    rings = []
    for part in getattr(longitude_latitude, "geoms", [longitude_latitude]):
        exterior = getattr(part, "exterior", None)
        if exterior is None:
            continue
        ring = tuple((float(x), float(y)) for (x, y) in exterior.coords)
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def _ring_touches_component(ring_longitude_latitude, component) -> bool:
    """Does a lon/lat ring meet ``component`` (a lon/lat body polygon)?

    Used to give each connected body component its OWN corridors when a
    pack's members group into several facilities.  A ring that touches
    nothing is carried by nobody, which is right: a corridor with no body
    to plate against was never emitted either.
    """
    from shapely.geometry import Polygon as _Polygon

    try:
        polygon = _Polygon(ring_longitude_latitude)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        return bool(polygon.intersects(component))
    except Exception:                                     # pragma: no cover
        return False


def _tunnel_ramp_corridor_meters(tunnel, to_meters):
    """A facility's RAMP CORRIDOR in the layout metre frame, or ``None``
    (spec ``docs/specs/lemd-basin-trench-ramp-extension-spec.md``
    Amendment 1 §2).

    Deliberately a SEPARATE reader from
    :func:`_tunnel_footprint_meters_parts`, travelling the same road: the
    corridor must never be able to leak into "the body", because the
    body is what R_est, the floor and rim laws, the pad-coverage test and
    the post-mesh R_mesh band are all read from — and Amendment 1 exists
    because a round that put the ramp in there moved every one of them.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from .object_terrain_features import frame_polygon_to_longitude_latitude

    corridor = getattr(tunnel, "ramp_reach_corridor", None)
    if corridor is None or corridor.is_empty:
        return None
    longitude_latitude = frame_polygon_to_longitude_latitude(
        corridor, tunnel.frame_origin_longitude_latitude)
    parts = (
        list(longitude_latitude.geoms)
        if longitude_latitude.geom_type == "MultiPolygon"
        else [longitude_latitude]
    )
    meter_polygons = []
    for part in parts:
        ring = [to_meters(lon, lat) for lon, lat in part.exterior.coords]
        if len(ring) < 3:
            continue
        try:
            polygon = Polygon(ring)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
        except Exception:
            continue
        if polygon.is_empty or polygon.geom_type not in (
                "Polygon", "MultiPolygon"):
            continue
        meter_polygons.append(polygon)
    if not meter_polygons:
        return None
    try:
        merged = unary_union(meter_polygons)
    except Exception:
        return None
    return None if merged.is_empty else merged


def _tunnel_footprint_meters_parts(tunnel, to_meters) -> list:
    """:func:`_tunnel_footprint_longitude_latitude_parts` projected into
    the layout metre frame, as shapely ``Polygon`` parts."""
    from shapely.geometry import Polygon

    parts = _tunnel_footprint_longitude_latitude_parts(tunnel)
    meter_polygons: list = []
    for part in parts:
        ring = [to_meters(lon, lat) for lon, lat in part.exterior.coords]
        if len(ring) < 3:
            continue
        try:
            polygon = Polygon(ring)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
        except Exception:
            continue
        if polygon.geom_type == "Polygon" and not polygon.is_empty:
            meter_polygons.append(polygon)
        elif polygon.geom_type == "MultiPolygon":
            meter_polygons.extend(
                geometry for geometry in polygon.geoms
                if geometry.geom_type == "Polygon" and not geometry.is_empty
            )
    return meter_polygons


def _split_annulus_to_simple_parts(geometry) -> list:
    """Split a rim-collar annulus (a polygon with a hole over the floor
    pan) into simply-connected ``Polygon`` parts so the flat-plate birth
    primitive — which triangulates from the exterior ring only — cannot
    fill the hole and bury the floor.  A polygon WITHOUT a hole passes
    through unchanged; an annulus is cut by a thin centroid cross into
    simply-connected arc pieces (the idiom
    ``bridges._emit_deck_lip_weld_strips`` uses for its box-wrapping
    strips)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    parts = (
        list(geometry.geoms)
        if geometry.geom_type == "MultiPolygon" else [geometry]
    )
    simple_parts: list = []
    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        if not part.interiors:
            simple_parts.append(part)
            continue
        centroid = part.centroid
        minimum_x, minimum_y, maximum_x, maximum_y = part.bounds
        reach = max(maximum_x - minimum_x, maximum_y - minimum_y) + 10.0
        try:
            cross = unary_union([
                LineString([(centroid.x - reach, centroid.y),
                            (centroid.x + reach, centroid.y)]).buffer(0.05),
                LineString([(centroid.x, centroid.y - reach),
                            (centroid.x, centroid.y + reach)]).buffer(0.05),
            ])
            opened = part.difference(cross)
        except Exception:
            continue
        for piece in (
                opened.geoms if hasattr(opened, "geoms") else [opened]):
            if (piece.geom_type == "Polygon" and not piece.is_empty
                    and not piece.interiors):
                simple_parts.append(piece)
    return simple_parts


# Flush-wall trench geometry (user screenshots 2026-07-18c).  Every gap
# is above the ~0.5 m canonical node-interning bucket so the paired rows
# survive as distinct nodes (the R2 node-split wall):
# * the datum rim band starts this far OUTSIDE the body footprint — the
#   wall spans band-inner (datum) → body edge (floor), so the batter
#   leans outward and the floor reaches the shell wall flush;
_TUNNEL_WALL_SETBACK_M = 0.6
# * width of the flat datum band beyond the setback;
_TUNNEL_RIM_BAND_WIDTH_M = 0.6
# * where the body abuts ANY earlier-born shape (pavement, building
#   pads, …) the wall top is that shape's own edge and the floor stays
#   this far from it (slightly over the setback: foreign edges carry
#   arbitrary authored vertices, not our own offset curve; a floor edge
#   collinear with a building ring minted the EGKR mm-jitter Triangle
#   failure).
_TUNNEL_FLOOR_OWNED_CLEARANCE_M = 0.7

#: How far the ramp corridor is grown back INTO the body so it overlaps
#: the floor pan (spec ``docs/specs/lemd-basin-trench-ramp-extension-
#: spec.md`` Amendment 1 §2).  DERIVED, never a knob: the pan is inset
#: ``_TUNNEL_WALL_SETBACK_M`` inside the body outline and the rim band
#: occupies ``_TUNNEL_RIM_BAND_WIDTH_M`` outside it, so anything less
#: than their sum leaves un-plated ground in the corridor's mouth — the
#: very poke-through the plate exists to close.  The extra metre is the
#: same margin the floor's own envelope carries.
_RAMP_CORRIDOR_BODY_BRIDGE_M = (
    _TUNNEL_WALL_SETBACK_M + _TUNNEL_RIM_BAND_WIDTH_M + 1.0)

# * THE BASIN-PAD CUT LINE (spec ``basin-pad-floor-seating-spec.md``
#   Amendment 2, owner-ratified 2026-08-25).  A pad that only PARTIALLY
#   covers a basin facility is CUT at the facility boundary: the
#   in-facility piece seats at the floor, the remainder keeps grade.
#   The sunken piece is inset from the cut line by exactly the three
#   margins the wall needs, and by no more:
#     * one ``_TUNNEL_WALL_SETBACK_M`` — the node split against the
#       REMAINDER's inner ring, which lies ON the cut line (two rows a
#       split apart at a 15.9 m drop ARE the R2 wall; sharing the ring
#       would weld the two halves into one level and undo the cut);
#     * ``_TUNNEL_FLOOR_OWNED_CLEARANCE_M`` + one more setback — the
#       clearance the floor pan keeps from every earlier-born shape,
#       so a FLOOR-PAN RING survives between the wall and the sunken
#       piece instead of the pan being differenced away to nothing.
#   The pan and the piece are both AT the floor, so that ring carries no
#   step; what it buys is that the two never overlap (a coincident twin
#   ring is the round-16 geometry-consistency defect class) and the
#   basin still emits floor plates of its own.
_BASIN_PAD_CUT_INSET_M = (2.0 * _TUNNEL_WALL_SETBACK_M
                          + _TUNNEL_FLOOR_OWNED_CLEARANCE_M)
# A Global-Airports tile DSF covers EVERY airport on the tile, so each
# airport's classifier sees every other airport's objects — without a
# proximity gate, twelve airports each emitted a jittered copy of the
# SAME Redhill control-tower trench into their own patches, and the
# twelve near-identical rings exploded the vector map's edge splitter
# (Triangle4XP "Unable to locate PSLG vertex", tile +51-001
# 2026-07-18).  A tunnel body farther than this from the airport's own
# airside pavement belongs to some other airport (or to nothing) and is
# never cut here.
_TUNNEL_MAX_AIRSIDE_DISTANCE_M = 500.0

# BASIN RIM ESTIMATE (spec docs/specs/basin-rim-flush-seating-spec.md
# section 2.1 item 2): step along the facility body outline between DEM
# samples whose MEDIAN becomes ``R_est``.  The spec's bound is "every
# <= 10 m"; a 50 x 50 m OTHH bowl therefore contributes ~20 samples and
# the whole airport ~tens — the per-facility cost is O(perimeter / 10)
# point DEM reads, which is nothing beside the union work already in
# this pass (the build-time tripwire is stated in the spec section 3
# item 4).
_BASIN_RIM_SAMPLE_STEP_M = 10.0

# R6-3 abutment-grade sampling density.  The abutment LINE is the land
# witness the classifier certified (``abutment_reaches_grade``), and its
# median built-mesh elevation is the seat target, so the samples must
# resolve the ground the abutment actually stands on — an abutment is
# tens of metres long, not hundreds.  Half the basin rim step: the rim
# band is a long closed outline where 10 m is plenty; two short lines
# want a denser median.
_ABUTMENT_GRADE_SAMPLE_STEP_M = 5.0


def _basin_rim_estimate_elevation_m(
    body_parts,
    dem,
    tile_lat: int,
    tile_lon: int,
    meters_to_lat_lon,
) -> float | None:
    """``R_est`` — the MEDIAN DEM elevation around a basin facility's own
    body outline, or ``None`` when the DEM answers nowhere.

    THE POINT (spec section 2.1 item 2, recon 2026-08-09).  The trench
    law used to key on a POINT DEM sample at ``placements[0]``, which is
    wherever the pack happened to put the placement anchor — inside its
    own pit, and arbitrary within it.  Measured at OTHH Dewatering_01:
    that point read 0.80 m while the DEM around the facility's rim ranged
    0.71-2.96 m, so both the floor and the rim were keyed to one
    unrepresentative corner of the ground the rim has to meet.

    The median (not the mean) because a rim band that clips the shoulder
    of a neighbouring embankment must not drag the whole facility with
    it; and every part of a multi-part body pools its samples into ONE
    estimate, because the facility is cut to ONE floor and walled to ONE
    rim — a per-part estimate would be a second authority over the same
    plates.
    """
    from .elevation import _sample_dem

    samples: list[float] = []
    for part in body_parts or []:
        exterior = getattr(part, "exterior", None)
        if exterior is None:
            continue
        try:
            length = float(exterior.length)
        except Exception:
            continue
        if not (length > 0.0):
            continue
        step_count = max(4, int(math.ceil(length / _BASIN_RIM_SAMPLE_STEP_M)))
        for index in range(step_count):
            try:
                point = exterior.interpolate(
                    length * index / step_count)
                latitude, longitude = meters_to_lat_lon(point.x, point.y)
                sample = _sample_dem(
                    dem, tile_lat, tile_lon, latitude, longitude)
            except Exception:
                continue
            if sample is not None and sample == sample:
                samples.append(float(sample))
    if not samples:
        return None
    return float(median(samples))


#: Layout attribute the per-facility basin records accumulate on, and the
#: key ``layout._write_axes_sidecar`` writes them under.  One name, read
#: by the emitter, the sidecar writer and the tests — a second spelling
#: is a report that silently reports nothing.
BASIN_FACILITY_RECORDS_ATTRIBUTE = "basin_facility_records"


def _record_basin_facility(layout, record: dict) -> None:
    """Append one basin facility's emitted numbers to the layout, for the
    patch's ``.axes.json`` sidecar to publish (spec section 2.1e item E2).

    Best effort by design: instrumentation must never be able to fail a
    build.  The values are plain JSON scalars so the sidecar writer needs
    no encoder of its own.
    """
    try:
        records = getattr(layout, BASIN_FACILITY_RECORDS_ATTRIBUTE, None)
        if records is None:
            records = []
            setattr(layout, BASIN_FACILITY_RECORDS_ATTRIBUTE, records)
        records.append(record)
    except Exception:
        pass


def _chop_long_band_parts(parts, maximum_length_m=25.0):
    """Subdivide long rim-band pieces so the per-part terrain-true DEM
    sample tracks the ground along the trench (one 300 m C-shaped band
    sampled once would flatten the whole rim to a single value — the
    berm class the per-part sampling exists to prevent)."""
    from shapely import affinity as shapely_affinity
    from shapely.geometry import box as shapely_box

    out = []
    for part in parts:
        try:
            rectangle = min_rotated_rect(part)
            ring = list(rectangle.exterior.coords)
            side_a = math.hypot(ring[1][0] - ring[0][0],
                                ring[1][1] - ring[0][1])
            side_b = math.hypot(ring[2][0] - ring[1][0],
                                ring[2][1] - ring[1][1])
            length = max(side_a, side_b)
            if length <= maximum_length_m:
                out.append(part)
                continue
            if side_a >= side_b:
                angle = math.degrees(math.atan2(
                    ring[1][1] - ring[0][1], ring[1][0] - ring[0][0]))
            else:
                angle = math.degrees(math.atan2(
                    ring[2][1] - ring[1][1], ring[2][0] - ring[1][0]))
            origin = part.centroid
            flat = shapely_affinity.rotate(
                part, -angle, origin=origin)
            minimum_x, minimum_y, maximum_x, maximum_y = flat.bounds
            slice_count = max(
                2, int(math.ceil((maximum_x - minimum_x)
                                 / maximum_length_m)))
            step = (maximum_x - minimum_x) / slice_count
            for index in range(slice_count):
                window = shapely_box(
                    minimum_x + index * step, minimum_y - 1.0,
                    minimum_x + (index + 1) * step, maximum_y + 1.0)
                piece = flat.intersection(window)
                for simple in getattr(piece, "geoms", [piece]):
                    if (simple.geom_type == "Polygon"
                            and not simple.is_empty):
                        out.append(shapely_affinity.rotate(
                            simple, angle, origin=origin))
        except Exception:
            out.append(part)
    return out


def basin_trench_structures(classification) -> list:
    """Feature-C open pits as feature-A trench records.

    Owner defect 2026-07-30 (OTHH Aeroscape ``Buildings/Dewatering
    Drainage/*``): the pack models drainage basins as open pits whose rim
    is flush with grade and whose body reaches ~3.8 m below it.  Left
    alone the mesh stays at grade over them and the whole object is
    buried — invisible in the sim.

    An open pit is geometrically the cut-and-cover tunnel case with the
    roof removed: rim at the anchor datum, floor strictly below the
    object's own lowest solid, near-vertical walls between them as an R2
    node split.  So this adapts, rather than duplicates —
    :func:`build_tunnel_layout_shapes` cuts both under the same
    ``grade_law.tunnel_trench_floor_elevation_m`` /
    ``…_rim_elevation_m`` (ruling R1: one law, every consumer imports
    it).  ``terrain_feature`` tags the record so the plates and log lines
    still name the classifier they came from.

    Which interfaces qualify is
    :func:`object_terrain_features.is_carved_basin_interface` — the same
    predicate the classifier uses to place them on the ruling-R4
    exclusion list, so carved and excluded can never disagree.  Whether a
    qualifying pit also CUTS PAVEMENT is the narrower ruling-R13 question
    (:func:`object_terrain_features.is_open_pit_interface`), carried onto
    the record as ``cuts_pavement``.

    Depth is the object's own floor, never deeper.  A bowl's
    ``floor_y_m`` is a BOUND, not a target (amendment A7: LFPG T1's shell
    bases at −3.4 m where the reference hand patch cuts −8 m), and this
    emitter deliberately takes the bound: cutting to the object's floor
    less ``TUNNEL_FLOOR_BELOW_OBJECT_DECK_M`` makes the modelled basin
    visible and keeps the mesh clear of it, which is the whole ask.
    Inventing extra depth is a law/audit decision with no object
    evidence behind it.
    """
    interfaces = getattr(classification, "ground_interfaces", None) or []
    structures: list = []
    for interface in interfaces:
        if not object_terrain_features.is_carved_basin_interface(interface):
            continue
        floor_y = float(interface.floor_y_m)
        # THE TRUE DEEPEST SOLID (spec basin-rim-flush-seating section 2.1
        # item 3).  ``TunnelStructure.solid_minimum_y_m`` is CONTRACTED as
        # "deepest SOLID effective height across the WHOLE structure" and
        # the trench floor keys on it; this adapter used to put the
        # interface's clustered LEVEL there instead, which is a different
        # quantity and always the shallower one — OTHH Drainage_06
        # clusters −3.859 m over a true minimum of −4.201 m, so 0.342 m
        # of the promised 0.5 m clearance was already spent before the
        # floor was cut.  Filling the field with what it says it holds is
        # a correction to THIS producer only: feature-A tunnel records
        # are built by ``object_terrain_features`` and are untouched.
        # ``floor_y`` remains the depth BOUND (amendment A7) and stays in
        # ``body_depth_m``; the emitter takes the deeper of the two.
        true_solid_minimum_y = getattr(interface, "solid_minimum_y_m", None)
        if true_solid_minimum_y is None or (
                true_solid_minimum_y != true_solid_minimum_y):
            # Hand-built records (tests, old sidecars) carry no true
            # minimum — the pre-2026-08-09 behaviour is the fallback.
            true_solid_minimum_y = floor_y
        structures.append(
            object_terrain_features.TunnelStructure(
                object_resources=list(interface.object_resources),
                anchor_longitude_latitude=(
                    interface.anchor_longitude_latitude),
                frame_origin_longitude_latitude=(
                    interface.frame_origin_longitude_latitude),
                heading_degrees=interface.heading_degrees,
                placement_kind="OBJECT",
                # The classifier folds any OBJECT_AGL offset into its
                # effective heights before the interface levels are
                # clustered, so ``floor_y_m`` is already effective and no
                # offset may be re-applied (the double-count the trench
                # law's own docstring warns about).
                above_ground_offset_m=0.0,
                # No roof: the pit is open to the sky, which is why its
                # WHOLE footprint is cut rather than deck-minus-roof.
                roof_footprint=None,
                deck_footprint=interface.below_grade_footprint,
                mouth_polygons=[],
                mouth_depth_samples=[],
                body_depth_m=-floor_y,
                solid_minimum_y_m=min(floor_y,
                                      float(true_solid_minimum_y)),
                solid_outline_footprint=interface.below_grade_footprint,
                terrain_feature=object_terrain_features.
                TERRAIN_FEATURE_BASIN,
                # Ruling R13 (owner 2026-07-30): an OPEN pit takes the
                # pavement with it.  The narrower predicate, not the
                # carve one — a carved basin with the pack's own
                # structure over it keeps R2 (see
                # ``is_open_pit_interface``).
                cuts_pavement=(
                    object_terrain_features.is_open_pit_interface(
                        interface)),
            )
        )
    return _extend_records_with_below_grade_regions(structures,
                                                    classification)


def _region_polygon_in_frame(region, frame_origin_longitude_latitude):
    """One :class:`object_terrain_features.BelowGradeRegion` ring in
    another record's metre frame.

    THE ONE PROJECTION PATH.  The ring goes region frame →
    longitude/latitude through
    ``object_terrain_features.frame_polygon_to_longitude_latitude`` — the
    same converter ``_tunnel_footprint_longitude_latitude_parts`` uses —
    and then into the record's frame through
    ``obj8_reader.lonlat_to_local_offset``, that converter's documented
    inverse.  A hand-rolled frame-to-frame translation here would be a
    second projection of the same body, which is exactly what the
    body-outline reader's docstring forbids.

    ONE IMPLEMENTATION, and it lives in
    ``object_terrain_features.region_polygon_in_frame``: the
    classifier's own PREMATCH test (spec basin-region-founding
    Amendment 1) needs the identical projection, and two spellings of
    "the region in someone else's frame" is the census-wrapper class.
    """
    return object_terrain_features.region_polygon_in_frame(
        region, frame_origin_longitude_latitude)


def _extend_records_with_below_grade_regions(structures, classification):
    """Widen each basin record's FOOTPRINT to the below-grade region it
    sits in (spec ``docs/specs/basin-region-footprint-spec.md`` §2.2;
    owner ruling 2026-08-26).

    ``deck_footprint`` and ``solid_outline_footprint`` become (region ∪
    the record's own footprint) and ``solid_minimum_y_m`` becomes the
    deeper of the two readings.  EVERYTHING ELSE IS UNTOUCHED —
    ``object_resources``, ``cuts_pavement``, the anchor, the depth bound.
    Membership drives the ruling-R4 exclusions and the rim-flush seating
    grouping, and widening it is a separate docket (spec §5).

    WHY HERE.  :func:`basin_trench_structures` is the ONE producer both
    :func:`build_tunnel_layout_shapes` and
    :func:`basin_rim_flush_facilities` group from, so extending at this
    single point keeps the emitted trench and the seated object in
    lockstep BY CONSTRUCTION — they cannot disagree about where the body
    is because there is only one body.

    A region matching NO record is NOT founded as a basin this round
    (there is no interface record to found one from): it is reported
    loudly with its area and centroid and left alone — founding is the
    follow-up docket in spec §5.
    """
    regions = getattr(classification, "below_grade_regions", None) or []
    if not regions or not config.BASIN_REGION_FOOTPRINT:
        return structures
    from shapely.ops import unary_union

    matched_regions: set[int] = set()
    extended = []
    for record in structures:
        footprint = record.deck_footprint
        if footprint is None or footprint.is_empty:
            extended.append(record)
            continue
        region_parts = []
        region_minimum_y = None
        corridor_parts = []
        for index, region in enumerate(regions):
            in_frame = _region_polygon_in_frame(
                region, record.frame_origin_longitude_latitude)
            if in_frame is None:
                continue
            try:
                if not in_frame.intersects(footprint):
                    continue
            except Exception:
                continue
            matched_regions.add(index)
            region_parts.append(in_frame)
            # THE RAMP TRAVELS BESIDE THE BODY, never inside it (spec
            # lemd-basin-trench-ramp-extension Amendment 1 §2).  Same
            # projection path as the ring above — one implementation, so
            # the ring and its own ramp can never land in two frames.
            corridor = getattr(region, "ramp_reach_corridor", None)
            if corridor is not None and not corridor.is_empty:
                corridor_in_frame = (
                    object_terrain_features.polygon_between_frames(
                        corridor, region.frame_origin_longitude_latitude,
                        record.frame_origin_longitude_latitude))
                if corridor_in_frame is not None:
                    corridor_parts.append(corridor_in_frame)
            region_minimum_y = (
                float(region.solid_minimum_y_m) if region_minimum_y is None
                else min(region_minimum_y,
                         float(region.solid_minimum_y_m)))
        if not region_parts:
            extended.append(record)
            continue
        try:
            widened = unary_union(region_parts + [footprint])
        except Exception:
            extended.append(record)
            continue
        if widened.is_empty:
            extended.append(record)
            continue
        solid_minimum_y = record.solid_minimum_y_m
        if solid_minimum_y is None or solid_minimum_y != solid_minimum_y:
            solid_minimum_y = region_minimum_y
        elif region_minimum_y is not None:
            solid_minimum_y = min(float(solid_minimum_y), region_minimum_y)
        UI.vprint(
            1,
            "   [object-basin] REGION FOOTPRINT: "
            f"{[r.split('/')[-1] for r in record.object_resources]} "
            f"{footprint.area:,.0f} m2 -> {widened.area:,.0f} m2 "
            f"(the below-grade region the pack's own objects describe); "
            f"deepest solid {record.solid_minimum_y_m} -> "
            f"{solid_minimum_y}",
        )
        corridor = None
        if corridor_parts:
            try:
                corridor = unary_union(corridor_parts)
            except Exception:
                corridor = None
            if corridor is not None and corridor.is_empty:
                corridor = None
            if corridor is not None:
                UI.vprint(
                    1,
                    "   [object-basin] RAMP CORRIDOR carried: "
                    f"{corridor.area:,.0f} m2 beside the "
                    f"{widened.area:,.0f} m2 body — NOT part of it (spec "
                    "lemd-basin-trench-ramp-extension Amendment 1 §2: the "
                    "body is the one measurement frame and stays put; the "
                    "corridor is consumed at emit only)",
                )
        extended.append(_dataclass_replace(
            record,
            deck_footprint=widened,
            solid_outline_footprint=widened,
            solid_minimum_y_m=solid_minimum_y,
            ramp_reach_corridor=corridor,
        ))
    return extended + _found_basins_from_unmatched_regions(
        regions, matched_regions, classification)


#: Spec ``docs/specs/basin-region-founding-spec.md`` §2.2 — a FOUNDED
#: record's contributor list is TIGHT: a resource joins it only if its
#: clipped below-grade area inside the region reaches this fraction of
#: the region, or this absolute area.  The field feeds
#: :func:`basin_rim_flush_facilities` grouping and hence SEATING, so
#: sweeping a shared-anchor family's 350 at-grade members in would be
#: the LSGG y-bake starvation class.  Spec'd values, not tuning knobs.
FOUNDED_BASIN_CONTRIBUTOR_AREA_FRACTION = 0.05
FOUNDED_BASIN_CONTRIBUTOR_AREA_M2 = 100.0


def _region_longitude_latitude(region, point):
    """One point of a region's own frame as ``(latitude, longitude)``."""
    origin_longitude, origin_latitude = (
        region.frame_origin_longitude_latitude)
    return obj8_reader.local_offset_to_lonlat(
        origin_latitude, origin_longitude, 0.0, point.x, point.y)


def _region_intersects_record_footprint(region, record, footprints):
    """Whether ``region`` reaches any of ``record``'s ``footprints``,
    read in THAT record's own metre frame through the one converter."""
    in_frame = _region_polygon_in_frame(
        region, record.frame_origin_longitude_latitude)
    if in_frame is None:
        return False
    for footprint in footprints:
        if footprint is None or footprint.is_empty:
            continue
        try:
            if in_frame.intersects(footprint):
                return True
        except Exception:
            continue
    return False


def _founded_basin_contributors(region) -> list:
    """The TIGHT contributor list of a founded record (spec §2.2)."""
    region_area = float(region.polygon.area)
    entries = getattr(region, "contributor_area_m2_by_resource", ()) or ()
    return sorted(
        resource
        for resource, contributed_area in entries
        if contributed_area
        >= FOUNDED_BASIN_CONTRIBUTOR_AREA_FRACTION * region_area
        or contributed_area >= FOUNDED_BASIN_CONTRIBUTOR_AREA_M2
    )


def _founded_basin_record(region):
    """One below-grade region AS a basin record (spec §2.2), or ``None``
    when its ring will not convert.

    Every field is the region's own reading, so the §2.2 floor
    DISAGREEMENT gate is vacuous by construction: ``body_depth_m`` and
    ``solid_minimum_y_m`` are one instrument read once
    (``−solid_minimum_y_m`` and ``solid_minimum_y_m``).  There is no
    deck-face population to disagree with — a founded record has no
    interface behind it, which is the whole reason it is founded.
    """
    frame_origin = region.frame_origin_longitude_latitude
    footprint = _region_polygon_in_frame(region, frame_origin)
    if footprint is None:
        return None
    # A REPRESENTATIVE POINT, never the centroid: the anchor is the
    # facility grouping key and the point a draped member seats on, and
    # a concave pit's centroid can fall outside its own ring.
    interior = region.polygon.representative_point()
    anchor_latitude, anchor_longitude = _region_longitude_latitude(
        region, interior)
    return object_terrain_features.TunnelStructure(
        object_resources=_founded_basin_contributors(region),
        anchor_longitude_latitude=(anchor_longitude, anchor_latitude),
        frame_origin_longitude_latitude=frame_origin,
        heading_degrees=0.0,
        placement_kind="OBJECT",
        # Regions are already in EFFECTIVE heights (the derivation folds
        # each placement's AGL offset into its own grade plane), so
        # re-applying an offset here would double-count it.
        above_ground_offset_m=0.0,
        roof_footprint=None,
        deck_footprint=footprint,
        mouth_polygons=[],
        mouth_depth_samples=[],
        body_depth_m=-float(region.solid_minimum_y_m),
        solid_minimum_y_m=float(region.solid_minimum_y_m),
        solid_outline_footprint=footprint,
        terrain_feature=object_terrain_features.TERRAIN_FEATURE_BASIN,
        # Admission item 2 IS ruling R13's open-pit predicate, asked at
        # region level: nothing of the pack's own stands over it.
        cuts_pavement=True,
        # The ramp travels with the record it belongs to, in that
        # record's frame.  A founded record's frame IS the region's, so
        # the corridor needs no projection here — but it goes through the
        # ONE converter anyway, because "no projection needed" is exactly
        # the assumption that rots when a frame changes.
        ramp_reach_corridor=object_terrain_features.polygon_between_frames(
            getattr(region, "ramp_reach_corridor", None),
            region.frame_origin_longitude_latitude, frame_origin),
    )


def _found_basins_from_unmatched_regions(regions, matched_regions,
                                         classification):
    """FOUND a basin record from a below-grade region that matched
    nothing (spec ``docs/specs/basin-region-founding-spec.md`` §2.1-§2.3;
    follow-up docket A of the owner's 2026-08-26 LEMD T4S rulings).

    Region EXTENSION can only widen a record that already exists, and
    LEMD got one only by luck — a single fully-buried member escaped the
    358-object shared-anchor mega-pool as its own BOWL_UNDER_DECK
    interface.  A pack whose below-grade members ALL pool into one
    FLAT_CONFIRMED mega-structure derives the region, matches nothing,
    and (before this) only logged it: the pit was never cut and the
    shell stayed buried.

    Admission is all of:

    1. the region intersects NO existing record footprint — basin
       (extension has already claimed those) or feature-A TUNNEL (a
       region under a tunnel record is that structure's business, never
       founded twice);
    2. DEPTH: at or below −``BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M``.
       Founding is inference without an interface to key on, so the
       2.5-3.0 m band stays extension-only evidence — logged, not
       founded;
    3. OPENNESS (ruling R13): above-grade coverage at or under
       ``BOWL_MAX_ABOVE_GRADE_AREA_FRACTION``.  A COVERED region is a
       bore/tunnel candidate, not a pit.  UNKNOWN coverage (a pre-v23
       cached classification) refuses too, naming the stale sidecar —
       never a silent guess;
    4. and it does not overlap a BRIDGE record: a bridge deck's
       under-space belongs to the bridge contract (spec §2.3).

    A founded record adds NO ruling-R4 exclusions — exclusions stay
    interface-driven, and founding changes terrain, not the y-bake
    population (spec §2.3; seating interplay is docket B).  Nothing here
    touches them, which is how that boundary stays clean.

    Every refusal keeps the loud UNMATCHED BELOW-GRADE REGION line with
    the reading that refused it, so a pit that is not cut is always
    attributable.
    """
    # The three spec'd thresholds, read from their ONE definitions.
    depth_floor_m = (
        object_terrain_features.BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M)
    coverage_cap = (
        object_terrain_features.BOWL_MAX_ABOVE_GRADE_AREA_FRACTION)
    area_floor_m2 = (
        object_terrain_features.TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2)
    founded: list = []
    for index, region in enumerate(regions):
        if index in matched_regions:
            continue
        region_area = float(region.polygon.area)
        centroid = region.polygon.centroid
        latitude, longitude = _region_longitude_latitude(region, centroid)
        coverage = getattr(region, "above_grade_area_fraction", None)
        reported = (
            f"{region_area:,.0f} m2 at {latitude:.7f},{longitude:.7f} "
            f"(deepest solid {region.solid_minimum_y_m:.3f} m, "
            "above-grade coverage "
            + ("UNKNOWN" if coverage is None else f"{coverage:.3f}")
            + f", {[r.split('/')[-1] for r in region.object_resources][:6]})"
        )

        def refuse(reason: str) -> None:
            UI.vprint(
                1,
                "   [object-basin] UNMATCHED BELOW-GRADE REGION: "
                f"{reported} {reason}",
            )

        if not config.BASIN_REGION_FOUNDING:
            refuse(
                "intersects NO basin record and founding is OFF "
                "(O4_BASIN_REGION_FOUNDING=0) — no basin is founded "
                "from it"
            )
            continue
        tunnel_records = getattr(classification, "tunnels", None) or []
        under_tunnel = any(
            _region_intersects_record_footprint(
                region, record,
                (record.deck_footprint, record.solid_outline_footprint))
            for record in tunnel_records
        )
        if under_tunnel:
            refuse(
                "lies under a feature-A TUNNEL record — that structure's "
                "business, never founded twice (spec §2.1)"
            )
            continue
        bridge_records = getattr(classification, "bridges", None) or []
        under_bridge = any(
            _region_intersects_record_footprint(
                region, record, (record.deck_polygon,))
            for record in bridge_records
        )
        if under_bridge:
            refuse(
                "overlaps a BRIDGE record — a bridge deck's under-space "
                "is the bridge contract's, never founded (spec §2.3)"
            )
            continue
        if coverage is None:
            refuse(
                "carries NO above-grade coverage reading (NOT COMPUTED) "
                "— either the classifier PREMATCHED it to a ground "
                "interface and the record was then dropped (spec "
                "Amendment 1's lazy rule), or this classification came "
                "from a STALE SIDECAR written before cache version "
                f"{_CLASSIFICATION_CACHE_VERSION} "
                "(o4_object_terrain_classification_*.cache); founding is "
                "REFUSED rather than guessed"
            )
            continue
        if region.solid_minimum_y_m > -depth_floor_m:
            refuse(
                "is SHALLOWER than the founding depth floor "
                f"({depth_floor_m:.1f} m) — it stays extension-only "
                "evidence, never founded (spec §2.1 item 1)"
            )
            continue
        if coverage > coverage_cap:
            refuse(
                "is COVERED by the pack's own geometry "
                f"({coverage:.3f} > {coverage_cap}) — a bore/tunnel "
                "candidate, not an open pit (ruling R13, spec §2.1 "
                "item 2)"
            )
            continue
        # Spec §2.1 item 3: the area floor is the REGION instrument's own
        # admission (``TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2``) — asserted
        # here, never re-derived into a second gate.
        assert region_area >= area_floor_m2, (
            f"region of {region_area} m2 survived region admission")
        record = _founded_basin_record(region)
        if record is None:  # pragma: no cover - ring would not convert
            refuse("could not be converted into a record frame")
            continue
        founded.append(record)
        UI.vprint(
            1,
            "   [object-basin] FOUNDED BASIN FROM REGION: "
            f"{reported} matched no record and is a deep OPEN pit — "
            "founding a basin record over it "
            f"(floor keys on {record.solid_minimum_y_m:.3f} m; "
            "contributors "
            f"{[r.split('/')[-1] for r in record.object_resources]})",
        )
    return founded


#: Decision kind recorded in the rebake provenance for a basin facility
#: seated by the section-2.2 rim-flush law.  ONE spelling, read by the
#: post-mesh pass, the provenance writer and the tests.
BASIN_RIM_FLUSH_DECISION_KIND = "basin_rim_flush"

#: Decision kind recorded in the rebake provenance for a basin facility
#: seated RIGIDLY AS A GROUP (docket B, docs/specs/basin-group-seat-spec.md
#: §2.3 item 3).  ONE spelling, read by the post-mesh pass, the
#: provenance writer and the tests.  A record carrying this kind was
#: seated onto the group's single datum plane ``G``; a record carrying
#: :data:`BASIN_RIM_FLUSH_DECISION_KIND` was seated by the
#: pre-amendment interface-member law (``O4_BASIN_GROUP_SEAT=0``).
BASIN_GROUP_SEAT_DECISION_KIND = "basin_group_seat"


@dataclass(frozen=True)
class BasinRimFlushFacility:
    """One basin FACILITY as the post-mesh bake needs to see it (spec
    basin-rim-flush-seating section 2.2 items 5-7).

    Built from the SAME classifier records section 2.1 emits terrain
    from (:func:`basin_trench_structures`, grouped by the emitter's own
    anchor key) — never a re-derivation, so the terrain that was cut and
    the object that is seated into it can never disagree about which
    facility they belong to, where its body is, or how deep its solids
    reach.

    * ``object_resources`` — every member shell (the ``TunnelStructure
      .object_resources`` of the facility's members, pooled).
    * ``anchor_longitude_latitude`` — the facility anchor, i.e. the point
      a DRAPED member seats on.
    * ``body_rings_longitude_latitude`` — exterior rings of the body
      outline parts, the ring the R_mesh band is offset outward from.
    * ``solid_minimum_y_m`` — ``y_true_min``: the deepest SOLID the
      facility's members model (the emitter's own ``deck_reference_y``,
      = min(−body_depth, the true deepest solid)).  Item 7's clearance
      check keys on this, which is why the section-2.1 true-min plumbing
      had to be correct FIRST (see _CLASSIFICATION_CACHE_VERSION 14).
    * ``anchor_inside_body`` — item 6's scope test: only an
      anchor-INSIDE facility bakes.  An anchor-outside facility drapes
      on neighbour terrain and was measured correct in-sim
      (docs/RULINGS.md 2026-08-09 consequence 5).
    """

    object_resources: tuple[str, ...]
    anchor_longitude_latitude: tuple[float, float]
    body_rings_longitude_latitude: tuple[tuple[tuple[float, float], ...], ...]
    solid_minimum_y_m: float
    anchor_inside_body: bool
    #: THE CARVE CORRIDOR (spec ``docs/specs/lemd-pad-authority-carve-
    #: spec.md`` §4), exterior rings in longitude/latitude, empty when
    #: this facility carries none.  It is NOT part of the body and never
    #: joins it — the body is the one measurement frame — but the G
    #: instrument has to know where our own corridor plate lies so its
    #: sample band can stay OUTSIDE it.  Carried on the facility because
    #: the facility is what the post-mesh pass is handed.
    carve_corridor_rings_longitude_latitude: tuple[
        tuple[tuple[float, float], ...], ...] = ()

    def to_json(self) -> dict:
        """Plain-JSON form for the post-mesh records cache."""
        return {
            "object_resources": list(self.object_resources),
            "anchor_longitude_latitude": list(
                self.anchor_longitude_latitude),
            "body_rings_longitude_latitude": [
                [list(point) for point in ring]
                for ring in self.body_rings_longitude_latitude
            ],
            "solid_minimum_y_m": float(self.solid_minimum_y_m),
            "anchor_inside_body": bool(self.anchor_inside_body),
            "carve_corridor_rings_longitude_latitude": [
                [list(point) for point in ring]
                for ring in self.carve_corridor_rings_longitude_latitude
            ],
        }

    @classmethod
    def from_json(cls, payload: dict) -> "BasinRimFlushFacility":
        return cls(
            object_resources=tuple(payload["object_resources"]),
            anchor_longitude_latitude=(
                float(payload["anchor_longitude_latitude"][0]),
                float(payload["anchor_longitude_latitude"][1]),
            ),
            body_rings_longitude_latitude=tuple(
                tuple((float(point[0]), float(point[1])) for point in ring)
                for ring in payload["body_rings_longitude_latitude"]
            ),
            solid_minimum_y_m=float(payload["solid_minimum_y_m"]),
            anchor_inside_body=bool(payload["anchor_inside_body"]),
            # ABSENT is EMPTY, never a KeyError: a payload written before
            # the carve existed carries no corridor because that build
            # had none.  (A payload written before v27 is retired by the
            # cache VERSION, which is the mechanism that must catch a
            # SHAPE change — this default is for in-process records the
            # post-mesh pass rebuilds, not a way around it.)
            carve_corridor_rings_longitude_latitude=tuple(
                tuple((float(point[0]), float(point[1])) for point in ring)
                for ring in (payload.get(
                    "carve_corridor_rings_longitude_latitude") or ())
            ),
        )


#: ``basin_facility_deck_reference_y`` key sources.  Which instrument won
#: is LAW, not diagnostics: the trench law's two margins clear a modelled
#: SOLID, so they apply to a solid-witness key and NOT to a deck-face one
#: (owner Amendment 3, 2026-08-25; ``grade_law.
#: basin_trench_floor_elevation_m``'s ``bore_class``).
BASIN_FLOOR_KEY_SOLID_WITNESS = "solid_witness"
BASIN_FLOOR_KEY_DECK_FACE = "deck_face"


def basin_facility_deck_reference_y(
        record, *, open_pit: bool = False
) -> "tuple[float, float | None, str]":
    """THE FLOOR KEY of one facility member, the witness it discarded, and
    WHICH INSTRUMENT the key came from.

    Returns ``(deck_reference_y, discarded_solid_minimum_y, key_source)``,
    ``key_source`` one of :data:`BASIN_FLOOR_KEY_SOLID_WITNESS` /
    :data:`BASIN_FLOOR_KEY_DECK_FACE`.  The floor key is the deeper of
    the modelled body depth and the structure's TRUE deepest solid — the
    reading the trench law has always taken — EXCEPT where the two
    disagree by more than :data:`config.BASIN_FLOOR_DISAGREEMENT_M`.

    ── THE LAW (owner 2026-08-26, docs/RULINGS.md "LEMD T4S basin") ───
    "A PACK'S AUTHORED PIT DEPTH IS NEVER THE FLOOR KEY; THE FLOOR KEYS
    ON THE FACILITY'S DEEPEST GENUINE SOLID, WITH THE TUNNEL MARGINS
    RESTORED — for open pits as for bores."  ``open_pit`` therefore
    changes NOTHING under the default law: both take the path below, and
    ``grade_law.basin_trench_floor_elevation_m`` subtracts both margins
    in both cases.  MEASURED BASIS: LEMD's Amendment-3 deck-face floor
    586.01 sat 0.07 m ABOVE the family's deepest genuine solid (−7.087),
    while the pack's own mesh patch cuts 10.9 m BELOW its own deepest
    solid.  The loss is asymmetric — extra depth is occluded by the
    modelled shell and free, shallowness is the visible poke-through —
    so err deep.

    Amendment 3 (2026-08-25) is RETIRED-KEPT-GATED behind
    ``config.BASIN_OPEN_PIT_DECK_KEY`` (``O4_BASIN_OPEN_PIT_DECK_KEY=1``),
    which restores the deck-face key for open pits here and the
    zero-margin arm in the law function.  The two ride ONE gate because
    they are one law read twice; ``key_source`` is still returned
    because it is that law's input, and deriving it a second time at the
    call site would be the census-wrapper defect in miniature.

    THE DISAGREEMENT GATE (spec ``docs/specs/
    tunnel-trench-law-and-basin-floor-spec.md`` §2.2).  ``body_depth_m``
    (the deck-face median population) and ``solid_minimum_y_m`` (the
    deepest solid vertex) are two instruments describing ONE bottom.
    Where they agree — every OTHH basin agrees within 0.4 m, and an
    EGLL-class shell wall reaching ~2 m below its deck is exactly the
    case this must NOT catch — the deeper reading wins as before.  Where
    they disagree grossly the witness is not believed: LEMD pooled two
    4-vertex VOR ground decals authored at −48.244 m into a facility
    whose body is 7.02 m deep and cut its basin 51.5 m below its own rim.
    The floor then derives from the deck-face population and the
    discarded witness is RETURNED so the caller can name it out loud —
    the 43 m disagreement used to be printed silently, as two numbers on
    one log line.

    ONE IMPLEMENTATION, both readers: the emitter
    (:func:`build_tunnel_layout_shapes`) and the rim-flush seating
    predictor (:func:`basin_rim_flush_facilities`, which mirrors the
    emitter's grouping character for character) call this, so a facility
    can never be cut to one floor and seated against another.
    """
    deck_reference_y = -float(record.body_depth_m)
    solid_minimum_y = getattr(record, "solid_minimum_y_m", None)
    if solid_minimum_y is not None and solid_minimum_y == solid_minimum_y:
        solid_minimum_y = float(solid_minimum_y)
        disagrees = (abs(solid_minimum_y - deck_reference_y)
                     > config.BASIN_FLOOR_DISAGREEMENT_M)
    else:
        solid_minimum_y = None
        disagrees = False
    if open_pit and config.BASIN_OPEN_PIT_DECK_KEY:
        # ── RETIRED-KEPT-GATED (owner 2026-08-26 supersedes Amendment
        # 3 of 2026-08-25); ``O4_BASIN_OPEN_PIT_DECK_KEY=1`` ──────────
        # Amendment 3: "an open-pit facility's floor is the pooled
        # solids' deck-face median (body_depth_m)" — a hole with nothing
        # of the pack's own standing over it has no solid BELOW that
        # face to clear, so the deepest-solid reading never deepens it.
        # MEASURED AGAINST THE PACK'S OWN MESH PATCH (LEMD, 2026-08-26):
        # that floor is 586.01, which is 0.07 m ABOVE the family's
        # deepest genuine solid (−7.087) — the mesh pokes through the
        # modelled walls.  Under the new law an open pit takes the same
        # path as a bore (below).  The §2.2 disagreement witness is
        # still RETURNED so the caller names it out loud.
        return (deck_reference_y,
                solid_minimum_y if disagrees else None,
                BASIN_FLOOR_KEY_DECK_FACE)
    if solid_minimum_y is None:
        return deck_reference_y, None, BASIN_FLOOR_KEY_DECK_FACE
    if disagrees:
        return deck_reference_y, solid_minimum_y, BASIN_FLOOR_KEY_DECK_FACE
    if solid_minimum_y < deck_reference_y:
        return solid_minimum_y, None, BASIN_FLOOR_KEY_SOLID_WITNESS
    return deck_reference_y, None, BASIN_FLOOR_KEY_DECK_FACE


#: THE GEOMETRIC-VALIDITY FLOOR for a split body component (spec
#: ``basin-group-seat`` §2.1 Amendment 2, Fable 2026-08-27).  NOT a design
#: threshold and NOT a config knob: it separates a POLYGON from
#: floating-point noise, nothing else.  MEASURED at LEMD (2026-08-27
#: acceptance run): the T4S body union split into the real 27,806 m² ring
#: AND a 1.6e-13 m² sliver — twenty orders of magnitude below the
#: smallest thing this project models — which became a second facility
#: with its own datum ``G`` 3.705 m away and double-seated 42 files.  Any
#: value between "float noise" and "a square millimetre" gives the same
#: answer on every real body, which is what makes it a validity floor.
_DEGENERATE_BODY_COMPONENT_AREA_M2 = 1e-6


def _admissible_body_components(components, anchor_longitude_latitude):
    """Split body components made VALID, with degenerate noise dropped.

    Each connected part goes through the region round's own repair idiom
    (``object_terrain_features._repaired_area_polygon`` — ``buffer(0)``
    plus the zero-area drop, ONE implementation, never a second spelling
    of "repaired"), and a part whose area is under
    :data:`_DEGENERATE_BODY_COMPONENT_AREA_M2` is DROPPED with a loud
    line naming its area.  Areas are read in metres at the facility's own
    latitude, because the rings are in degrees and a degree² threshold
    would mean a different thing at every airport.
    """
    metres_per_degree_latitude = obj8_reader.METRES_PER_DEGREE_LATITUDE
    metres_per_degree_longitude = (
        metres_per_degree_latitude
        * math.cos(math.radians(anchor_longitude_latitude[1]))
    )
    square_metres_per_square_degree = (
        metres_per_degree_latitude * metres_per_degree_longitude)
    admissible = []
    for component in components:
        repaired = object_terrain_features._repaired_area_polygon(component)
        if repaired is None:
            UI.vprint(
                1,
                "   [object-basin] DEGENERATE BODY COMPONENT dropped: a "
                "split part of the facility body would not repair into an "
                "area (spec basin-group-seat §2.1 Amendment 2)",
            )
            continue
        for part in getattr(repaired, "geoms", [repaired]):
            if part.geom_type != "Polygon" or part.is_empty:
                continue
            area_square_metres = (
                float(part.area) * square_metres_per_square_degree)
            if area_square_metres < _DEGENERATE_BODY_COMPONENT_AREA_M2:
                UI.vprint(
                    1,
                    "   [object-basin] DEGENERATE BODY COMPONENT dropped: "
                    f"{area_square_metres:.3e} m2 is below the "
                    f"{_DEGENERATE_BODY_COMPONENT_AREA_M2:.0e} m2 "
                    "geometric-validity floor — numerical noise from the "
                    "body union, not a facility (spec basin-group-seat "
                    "§2.1 Amendment 2)",
                )
                continue
            admissible.append(part)
    return admissible


def basin_rim_flush_facilities(classification) -> list:
    """The section-2.2 facility records for one classification.

    Grouping is the EMITTER's grouping, character for character: the
    same ``basin_trench_structures`` records, the same
    ``(terrain_feature, anchor×1e5, anchor×1e5)`` key
    :func:`build_tunnel_layout_shapes` groups facilities by, and the
    same members dropped (no below-grade body depth, no footprint to
    cut).  A facility the emitter cut one trench for is one facility
    here; anything else would seat an object into a hole nobody dug.

    ONE CONNECTED BODY = ONE FACILITY (docket B, basin-group-seat spec
    §2.1, ``config.BASIN_GROUP_SEAT``).  The anchor key above is the
    PACK'S DATUM, and in a shared-datum pack every below-grade structure
    carries the same one: the grouping then unions geographically
    unrelated pits into a single facility whose ``anchor_inside_body``
    is judged against that union — which is how LEMD's T4S facility
    "contained" an anchor 406 m outside its own ring.  With the gate on,
    the grouped records' unioned body is split into its CONNECTED
    COMPONENTS and each component becomes its own facility (members =
    the records whose own footprint touches that component,
    ``solid_minimum_y_m`` the min over those members).  The anchor stays
    the records' shared datum; the emitter's trench grouping is
    untouched (it already cuts per-part rings), so this splits seating
    records only.

    Returns ``[]`` with the basin gate off — with no trench cut there is
    nothing for the rim-flush law to seat into.
    """
    if not config.OBJECT_BASIN_TRENCH:
        return []
    from shapely.geometry import Point
    from shapely.ops import unary_union

    facilities: dict = {}
    for record in basin_trench_structures(classification):
        anchor_longitude, anchor_latitude = record.anchor_longitude_latitude
        key = (
            getattr(record, "terrain_feature", "tunnel"),
            round(anchor_longitude * 100000.0),
            round(anchor_latitude * 100000.0),
        )
        facilities.setdefault(key, []).append(record)

    out: list = []
    for members in facilities.values():
        # One entry per ADMITTED member record: its own footprint parts,
        # its resources and its floor key.  The per-component split below
        # needs the member-to-footprint association, which a pooled part
        # list throws away.
        admitted: list[tuple[list, tuple[str, ...], float]] = []
        # THE CARVE CORRIDORS this facility's members carry (spec
        # lemd-pad-authority-carve §4), in longitude/latitude — collected
        # beside ``admitted`` and NEVER folded into ``body_parts``: the
        # body is the one measurement frame, and Amendment 1 of the
        # trench spec exists because a round that put the ramp in there
        # moved the floor value, the rim value, the pad coverage test and
        # G at once.
        corridor_rings: list = []
        anchor_longitude_latitude = None
        for record in members:
            # The emitter's own member admission (a member with no
            # below-grade depth or no footprint cuts nothing, so it
            # seats nothing).
            if record.body_depth_m is None or record.body_depth_m <= 0.0:
                continue
            parts = _tunnel_footprint_longitude_latitude_parts(record)
            if not parts:
                continue
            # ``deck_reference_y`` — the emitter's floor key, i.e. the
            # deeper of the modelled body depth and the structure's TRUE
            # deepest solid, under the §2.2 disagreement gate.  ONE
            # implementation with the emitter (the discarded witness is
            # named there, at the cut, not twice).
            deck_reference_y, _discarded, _key_source = (
                basin_facility_deck_reference_y(record))
            admitted.append(
                (list(parts), tuple(record.object_resources),
                 float(deck_reference_y))
            )
            corridor_rings.extend(
                _tunnel_ramp_corridor_longitude_latitude_rings(record))
            if anchor_longitude_latitude is None:
                anchor_longitude_latitude = (
                    float(record.anchor_longitude_latitude[0]),
                    float(record.anchor_longitude_latitude[1]),
                )
        if not admitted or anchor_longitude_latitude is None:
            continue
        body_parts = [part for parts, _resources, _key in admitted
                      for part in parts]
        resources = {resource for _parts, member_resources, _key in admitted
                     for resource in member_resources}
        if not resources or not body_parts:
            continue
        try:
            body = unary_union(body_parts)
        except Exception:
            body = None
        if body is None or body.is_empty:
            continue
        anchor_point = Point(*anchor_longitude_latitude)
        components = [
            component
            for component in getattr(body, "geoms", [body])
            if component.geom_type == "Polygon" and not component.is_empty
        ]
        if not components:
            continue
        if not config.BASIN_GROUP_SEAT:
            # PRE-AMENDMENT (gate off): one facility per anchor key, its
            # body the union of every grouped member's parts.
            rings = tuple(
                tuple(
                    (float(longitude), float(latitude))
                    for longitude, latitude in component.exterior.coords
                )
                for component in components
            )
            out.append(
                BasinRimFlushFacility(
                    object_resources=tuple(sorted(resources)),
                    anchor_longitude_latitude=anchor_longitude_latitude,
                    body_rings_longitude_latitude=rings,
                    solid_minimum_y_m=min(
                        key for _parts, _resources, key in admitted),
                    anchor_inside_body=bool(body.covers(anchor_point)),
                    carve_corridor_rings_longitude_latitude=tuple(
                        corridor_rings),
                )
            )
            continue
        # §2.1: one connected body component = one facility, after the
        # region round's own polygon repair and the GEOMETRIC-VALIDITY
        # FLOOR below (Amendment 2, Fable 2026-08-27).
        for component in _admissible_body_components(
                components, anchor_longitude_latitude):
            component_resources: set[str] = set()
            component_keys: list[float] = []
            for parts, member_resources, key in admitted:
                touches = False
                for part in parts:
                    try:
                        if component.intersects(part):
                            touches = True
                            break
                    except Exception:
                        continue
                if not touches:
                    continue
                component_resources.update(member_resources)
                component_keys.append(key)
            if not component_resources or not component_keys:
                continue
            ring = tuple(
                (float(longitude), float(latitude))
                for longitude, latitude in component.exterior.coords
            )
            out.append(
                BasinRimFlushFacility(
                    object_resources=tuple(sorted(component_resources)),
                    anchor_longitude_latitude=anchor_longitude_latitude,
                    body_rings_longitude_latitude=(ring,),
                    solid_minimum_y_m=min(component_keys),
                    anchor_inside_body=bool(component.covers(anchor_point)),
                    # ONE BODY, ONE CORRIDOR SET: a corridor belongs to
                    # the component it touches, so a facility never
                    # scopes G by a ramp that is not its own.
                    carve_corridor_rings_longitude_latitude=tuple(
                        ring_ll for ring_ll in corridor_rings
                        if _ring_touches_component(ring_ll, component)),
                )
            )
    return out


#: Decision kind recorded in the rebake provenance for a TERRAIN_CARRIED
#: bridge seated by the R6-3 abutment-grade law.  ONE spelling, read by
#: the post-mesh pass, the provenance writer and the tests.
BRIDGE_ABUTMENT_SEAT_DECISION_KIND = "bridge_abutment_seat"

#: Which limb produced a seat candidate (round-12 R12-2).  ONE spelling
#: each, read by the post-mesh records, the findings and the tests.
SEAT_SOURCE_CLASSIFIED = "classified"
SEAT_SOURCE_REFUSED_VIADUCT = "refused_viaduct"

#: Counted findings this module mints for the post-mesh pass to report.
#: ``bridge_seat_fallback`` (R12-2): a REFUSED family that has no
#: measurable deck, so it keeps today's generic y-bake instead of the
#: rigid deck-top seat.  ``bridge_verdict_frame_split`` (R12-3): the
#: post-mesh classification derived a different contract for a resource
#: than the pipeline-time classification cached for the same pack — two
#: frames, two verdicts, one pack.  Both are RECORDED; neither changes
#: which verdict is used.
BRIDGE_SEAT_FALLBACK_FINDING = "bridge_seat_fallback"
#: ``bridge_seat_coalition`` (amendment 4): a family that DID seat, and
#: which of its deck members authored the level.  Informational, not a
#: defect — but counted, because its OUTLIERS are the standing evidence
#: trail for the canal-floor residual B2 cannot see (a member whose end
#: lines cross unattributed water reads low and lands here).
BRIDGE_SEAT_COALITION_FINDING = "bridge_seat_coalition"
BRIDGE_VERDICT_FRAME_SPLIT_FINDING = "bridge_verdict_frame_split"


@dataclass(frozen=True)
class BridgeAbutmentSeatCandidate:
    """One TERRAIN_CARRIED bridge as the R6-3 post-mesh seat needs to see
    it (round-6 OTHH residuals spec).

    THE DEFECT.  OTHH ``Bridge_01`` is a cosmetic flush deck
    (TERRAIN_CARRIED, deck top −0.31 m in its own frame).  Its resources
    are R4-EXCLUDED from the Phase 2 y-bake, and its anchor sits OVER
    WATER — the built mesh answers 0.00 m at the anchor and at every deck
    station — so the object draped ~3.96 m below the ground its own
    abutments stand on.

    THE LAW.  A TERRAIN_CARRIED bridge whose anchor ground sample sits
    more than the reseat threshold (``DSF_OBJECT_BAKE_MIN_DELTA_M``,
    1.0 m) BELOW its CERTIFIED abutment grade leaves the
    excluded-and-draped treatment and takes a Phase-2 seat at the
    abutment-grade consensus.  "Certified" is the classifier's own
    ``abutment_reaches_grade`` — solid geometry of any hardness reaching
    effective grade at BOTH ends (a piered viaduct never becomes a
    ``BridgeStructure`` at all).  Bridges whose anchors sample land
    within the threshold stay excluded and draped exactly as today.

    Only the CANDIDACY is decided at classify time — it is a pure
    function of the classifier's records, so it caches with them.  The
    qualification (how far below the abutments the anchor really sits) is
    a question only the BUILT MESH can answer, and post_mesh asks it.

    * ``object_resources`` — the bridge's member resources.
    * ``anchor_longitude_latitude`` — ``(longitude, latitude)`` of the
      structure anchor, i.e. the point a DRAPED member seats on.
    * ``abutment_points_longitude_latitude`` — the two abutment lines'
      endpoints, already projected out of the structure metre frame, in
      ``[start end, far end]`` order.  Projected HERE so the post-mesh
      pass never re-derives a frame (``_abutment_lines_layout_meters``
      needs a layout, and the pipeline-time layout is gone by then).
    * ``deck_top_y_m`` — the authored deck crest in the structure frame.
      Under R12-1 this is the DATUM the seat works from: the deck top is
      landed AT the abutment grade, so the seat plane (the authored
      ``y = 0`` plane) goes to ``abutment grade − deck_top_y_m``.

    ROUND 12.  Two things widened:

    * ``object_resources`` is now the whole ANCHOR FAMILY
      (:func:`anchor_family_resources`), not just the resources whose
      geometry the classifier measured the deck on — a family member
      that carries no deck face (a railing: ``OTHH_Bridge_04_LOD0_004``)
      is still part of the bridge and must move with it.
      ``deck_object_resources`` keeps the measured subset, as provenance.
    * ``seat_source`` says which limb produced the record:
      ``classified`` (a TERRAIN_CARRIED bridge with certified abutments,
      R6-3) or ``refused_viaduct`` (a piered viaduct refused a terrain
      feature, which R12-2 gives the same rigid seat rather than the
      per-structure y-bake that tears it).
    """

    object_resources: tuple[str, ...]
    anchor_longitude_latitude: tuple[float, float]
    abutment_points_longitude_latitude: tuple[
        tuple[tuple[float, float], tuple[float, float]], ...]
    deck_top_y_m: float
    deck_object_resources: tuple[str, ...] = ()
    seat_source: str = SEAT_SOURCE_CLASSIFIED
    #: AMENDMENT 3, the refused-viaduct limb's real instrument: one entry
    #: per deck-carrying member, ``(resource_path, lines, crest)``, with
    #: ``lines`` in the same ``(longitude, latitude)`` spelling as
    #: ``abutment_points_longitude_latitude``.  Empty for a CLASSIFIED
    #: candidate, whose single certified pair is the R6-3 instrument and
    #: is untouched by this amendment.
    deck_member_records: tuple = ()

    def to_json(self) -> dict:
        """Plain-JSON form for the post-mesh records cache."""
        return {
            "object_resources": list(self.object_resources),
            "anchor_longitude_latitude": list(
                self.anchor_longitude_latitude),
            "abutment_points_longitude_latitude": [
                [list(point) for point in line]
                for line in self.abutment_points_longitude_latitude
            ],
            "deck_top_y_m": float(self.deck_top_y_m),
            "deck_object_resources": list(self.deck_object_resources),
            "seat_source": str(self.seat_source),
            "deck_member_records": [
                {
                    "resource_path": record["resource_path"],
                    "abutment_points_longitude_latitude": [
                        [list(point) for point in line]
                        for line in record[
                            "abutment_points_longitude_latitude"]
                    ],
                    "deck_top_y_m": float(record["deck_top_y_m"]),
                }
                for record in self.deck_member_records
            ],
        }

    @classmethod
    def from_json(cls, payload: dict) -> "BridgeAbutmentSeatCandidate":
        return cls(
            object_resources=tuple(payload["object_resources"]),
            anchor_longitude_latitude=(
                float(payload["anchor_longitude_latitude"][0]),
                float(payload["anchor_longitude_latitude"][1]),
            ),
            abutment_points_longitude_latitude=tuple(
                tuple(
                    (float(point[0]), float(point[1]))
                    for point in line
                )
                for line in payload["abutment_points_longitude_latitude"]
            ),
            deck_top_y_m=float(payload["deck_top_y_m"]),
            deck_object_resources=tuple(
                payload.get("deck_object_resources", ())),
            seat_source=str(
                payload.get("seat_source", SEAT_SOURCE_CLASSIFIED)),
            deck_member_records=tuple(
                {
                    "resource_path": record["resource_path"],
                    "abutment_points_longitude_latitude": tuple(
                        tuple(
                            (float(point[0]), float(point[1]))
                            for point in line
                        )
                        for line in record[
                            "abutment_points_longitude_latitude"]
                    ),
                    "deck_top_y_m": float(record["deck_top_y_m"]),
                }
                for record in payload.get("deck_member_records", ())
            ),
        )


def _abutment_lines_longitude_latitude(
    abutment_lines, frame_origin_longitude_latitude
) -> list:
    """The first two abutment lines projected out of the structure metre
    frame into ``(longitude, latitude)`` pairs.

    Projected HERE, once, so the post-mesh pass never re-derives a frame
    (the pipeline-time layout is gone by then).  NOTE the obj8 helper
    returns ``(latitude, longitude)``; every post-mesh record carries
    ``(longitude, latitude)``, so the flip happens ONCE, here."""
    origin_longitude, origin_latitude = frame_origin_longitude_latitude
    lines: list = []
    for (start_point, end_point) in list(abutment_lines)[:2]:
        projected = []
        for frame_x, frame_z in (start_point, end_point):
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                origin_latitude, origin_longitude, 0.0, frame_x, frame_z,
            )
            projected.append((longitude, latitude))
        lines.append(tuple(projected))
    return lines


def bridge_abutment_seat_candidates(
    classification, placements=None
) -> tuple[list, list]:
    """The seat candidate records for one classification, and the
    findings the candidacy pass minted.

    Returns ``(candidates, findings)``.

    A candidate comes from one of two limbs:

    * **R6-3, ``classified``** — a
      :data:`object_terrain_features.TERRAIN_CARRIED` bridge with TWO
      abutment lines, both certified by ``abutment_reaches_grade``.
    * **R12-2, ``refused_viaduct``** — a piered viaduct REFUSED a terrain
      feature.  Refusing the feature was right (a deck-end pin there
      builds a false causeway); handing the family to the generic
      per-structure y-bake was not, because that bakes one bridge to
      three different grounds (OTHH Bridge_02/03/06: 0.00 / 1.63 /
      3.96 m).  It takes the SAME rigid deck-top seat, off the deck
      measurements the classifier already took before the guard fired.
      A refused family with NO measurable deck keeps today's y-bake and
      mints a counted ``bridge_seat_fallback`` finding saying why.

    ``placements`` (the DSF's terrain placements) widens each candidate's
    member set to its whole ANCHOR FAMILY — the same predicate ruling R4
    uses to decide what the generic y-bake may not touch, so a family
    member can never be both withheld from the y-bake and left out of
    the seat.  Omitted, the member set is the classifier's own (the
    pre-round-12 behaviour, kept for callers with no placement list).

    Nothing here consults the mesh: the threshold test lives post-mesh,
    where the ground is measurable.

    Returns ``([], [])`` with ``O4_OBJECT_BRIDGE_TERRAIN`` off — with no
    bridge terrain adapted, the bridge is not R4-excluded and the generic
    y-bake already owns it.
    """
    if not config.OBJECT_BRIDGE_TERRAIN:
        return [], []

    placements = list(placements or [])

    def _family(seed_resources) -> tuple[str, ...]:
        seeds = set(seed_resources)
        if not placements:
            return tuple(sorted(seeds))
        return tuple(sorted(
            anchor_family_resources(placements, seeds, label="R12-2")
        ))

    out: list = []
    findings: list = []
    for bridge in getattr(classification, "bridges", None) or []:
        if bridge.contract != object_terrain_features.TERRAIN_CARRIED:
            continue
        if len(bridge.abutment_lines) < 2:
            continue
        if not all(bridge.abutment_reaches_grade):
            # Belt and braces: an emitted record always certifies both
            # ends (a failing end is refused upstream).  If that ever
            # changes, an UNCERTIFIED abutment must not become a seat
            # target — there is no land witness behind it.
            continue
        out.append(
            BridgeAbutmentSeatCandidate(
                object_resources=_family(bridge.object_resources),
                anchor_longitude_latitude=tuple(
                    bridge.anchor_longitude_latitude),
                abutment_points_longitude_latitude=tuple(
                    _abutment_lines_longitude_latitude(
                        bridge.abutment_lines,
                        bridge.frame_origin_longitude_latitude,
                    )
                ),
                deck_top_y_m=float(bridge.deck_top_y_m),
                deck_object_resources=tuple(
                    sorted(bridge.object_resources)),
                seat_source=SEAT_SOURCE_CLASSIFIED,
            )
        )

    for refusal in getattr(classification, "refusals", None) or []:
        if not getattr(refusal, "has_measurable_deck", False):
            findings.append({
                "finding": BRIDGE_SEAT_FALLBACK_FINDING,
                "resources": sorted(refusal.object_resources),
                "reason": (
                    "refused structure with no measurable deck "
                    f"({refusal.reason}) — kept on the generic y-bake, "
                    "no rigid deck-top seat is possible without a deck "
                    "axis (R12-2)"
                ),
            })
            continue
        # AMENDMENT 3: the MEMBER deck faces are the instrument.  The
        # merged component's own min-rect lines are NOT carried onto a
        # refused candidate at all — on a mega-pool merge they are a
        # chord across everything the merge swallowed, and carrying them
        # "just in case" is how a retired instrument comes back.
        member_records = tuple(
            {
                "resource_path": member.resource_path,
                "abutment_points_longitude_latitude": tuple(
                    _abutment_lines_longitude_latitude(
                        member.abutment_lines,
                        refusal.frame_origin_longitude_latitude,
                    )
                ),
                "deck_top_y_m": float(member.deck_top_y_m),
            }
            for member in refusal.deck_members
        )
        member_records = tuple(
            record for record in member_records
            if len(record["abutment_points_longitude_latitude"]) >= 2
        )
        if not member_records:
            findings.append({
                "finding": BRIDGE_SEAT_FALLBACK_FINDING,
                "resources": sorted(refusal.object_resources),
                "reason": (
                    "refused structure whose deck members yielded no "
                    f"usable end lines ({refusal.reason}) — kept on the "
                    "generic y-bake (R12-2, amendment 3)"
                ),
            })
            continue
        out.append(
            BridgeAbutmentSeatCandidate(
                object_resources=_family(refusal.object_resources),
                anchor_longitude_latitude=tuple(
                    refusal.anchor_longitude_latitude),
                # The FAMILY-level pair stays empty for this limb: the
                # per-member records below are what the seat samples.
                abutment_points_longitude_latitude=(),
                deck_top_y_m=float(refusal.deck_top_y_m),
                deck_object_resources=tuple(
                    sorted(refusal.deck_object_resources or ())),
                seat_source=SEAT_SOURCE_REFUSED_VIADUCT,
                deck_member_records=member_records,
            )
        )
    return out, findings


# ── §C: THE RIM SEATS AT THE SOLVED NEIGHBOUR, DEM LAST ──────────────
# (spec docs/specs/lemd-rim-and-stations-spec.md §C; owner RULINGS
# 2026-08-28 item 3, and the basin-rim-flush spec's own §1(2), which
# recon 2026-08-09 already recorded as unimplemented: "the neighbour the
# rim must match is the SOLVED surface, not DEM".)
#
# The rim band's job is to pin the wall TOP at the surface it abuts.  A
# per-part DEM sample answers a different question — what the ground was
# before anything was built — and at LEMD it put all 13 rim parts LOW
# against their neighbour (median -3.84 m, worst -5.41 m against
# building8's 600.50) with 4.14 m of self-spread between parts of one
# band.  DEM-LAST (RULINGS 2026-08-25) says the built value comes first
# and raw DEM appears only where nothing else reaches.
#
# The neighbour population is BUILT SURFACE: pavement (airside, service,
# groundside) and pads.  Our own trench plates are excluded by
# construction — a rim seating off the floor pan beside it would be the
# facility grading itself.
def _rim_neighbour_roles():
    from .bridges import pavement_cut_roles
    from .layout import ROLE_BUILDING, ROLE_OBJECT_PAD
    return frozenset(pavement_cut_roles(include_groundside=True)
                     | {ROLE_BUILDING, ROLE_OBJECT_PAD})


def _shape_value_at(shape, point):
    """``shape``'s own built value nearest ``point``: the ring LERP where
    it carries per-node altitudes, its flat level where it is flat, else
    ``None``.

    A pad seated at a basin FLOOR is not a rim neighbour — its value is
    the pit bottom, not the surrounding grade — and says so by returning
    ``None``.
    """
    if getattr(shape, "basin_floor_seat_m", None) is not None:
        return None
    alts = getattr(shape, "node_altitudes", None)
    poly = getattr(shape, "polygon", None)
    if alts and poly is not None and not poly.is_empty:
        try:
            ring = list(poly.exterior.coords)
        except Exception:                                 # pragma: no cover
            ring = []
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        n = len(ring)
        if n >= 2 and len(alts) >= n:
            px, py = float(point.x), float(point.y)
            best = None
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                if L2 < 1e-12:
                    t = 0.0
                    qx, qy = ax, ay
                else:
                    t = ((px - ax) * dx + (py - ay) * dy) / L2
                    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                    qx, qy = ax + t * dx, ay + t * dy
                d = math.hypot(qx - px, qy - py)
                if best is None or d < best[0]:
                    best = (d, i, t)
            if best is not None:
                _d, i, t = best
                try:
                    return (float(alts[i])
                            + t * (float(alts[(i + 1) % n])
                                   - float(alts[i])))
                except (TypeError, ValueError):           # pragma: no cover
                    return None
    alt = getattr(shape, "altitude", None)
    if alt is not None:
        try:
            return float(alt)
        except (TypeError, ValueError):                   # pragma: no cover
            return None
    return None


def _rim_neighbour_value(band_part, candidates, window_m):
    """``(value, ref, distance_m)`` of the nearest ANCHORED built
    neighbour of ``band_part`` within ``window_m``, else ``None``.

    ``candidates`` is ``[(polygon, shape), ...]`` — the caller's
    bbox-filtered population, so this never unions the layout.
    """
    best = None
    for (poly, shape) in candidates:
        try:
            d = float(band_part.distance(poly))
        except Exception:                                 # pragma: no cover
            continue
        if d > float(window_m):
            continue
        if best is not None and d >= best[0]:
            continue
        value = _shape_value_at(shape, band_part.centroid)
        if value is None or value != value:
            continue
        best = (d, value, getattr(shape, "ref", None) or "?")
    if best is None:
        return None
    return (best[1], best[2], best[0])


#: The emitted ref of a BASIN rim band part — the population §C's
#: post-solve re-seat re-values.  A literal, and flagged as one.
BASIN_RIM_PLATE_REF = "object_basin_rim"
#: ...and the FLOOR pan's, the other side of the declared wall.
BASIN_FLOOR_PLATE_REF = "object_basin_trench"


def reseat_basin_rim_plates_post_solve(layout):
    """§C RUNG 1, IN THE ONLY SLOT WHERE IT CAN MEAN ANYTHING (spec
    lemd-rim-and-stations Amendment 1 §2, 2026-08-28).

    ``build_tunnel_layout_shapes`` runs PRE-SOLVE, and measured at LEMD
    that is why rung 1 never fired: no built neighbour carries a value
    there yet — pads are seated and pavement solved later — so all 18
    parts took ``R_est`` 596.30 while the apron beside them emitted
    ~599.98.  The pre-solve plate therefore keeps ``R_est`` as its SEED,
    and this pass re-values each part from its nearest SOLVED anchored
    neighbour once the solve has run.

    ONE-DIRECTIONAL ADOPTION, the adoption precedent: the rim part moves
    to its neighbour; the neighbour never moves.  A basin rim plate is
    born ``record_pins=False`` with a role outside ``PAVEMENT_ROLES``, so
    it is not a solver variable and nothing downstream re-derives it —
    re-valuing it here is additive, exactly like the other post-solve
    emission passes.

    Rungs, unchanged from §C: nearest ANCHORED built neighbour within
    ``config.TUNNEL_RIM_NEIGHBOUR_WINDOW_M`` → the pre-solve ``R_est``
    seed → (the raw DEM already lives in that seed's own fallback).
    Returns a report dict; nothing is printed here.
    """
    report = {"parts": 0, "reseated": 0, "kept_seed": 0,
              "worst_move_m": 0.0, "refs": {}, "before": [], "after": []}
    if not config.RIM_SOLVED_NEIGHBOUR:
        return report
    from .layout import ROLE_TUNNEL_TRENCH
    shapes = list(getattr(layout, "shapes", None) or ())
    plates = [s for s in shapes
              if getattr(s, "role", None) == ROLE_TUNNEL_TRENCH
              and str(getattr(s, "ref", "") or "") == BASIN_RIM_PLATE_REF
              and s.polygon is not None and not s.polygon.is_empty]
    if not plates:
        return report
    roles = _rim_neighbour_roles()
    window = float(config.TUNNEL_RIM_NEIGHBOUR_WINDOW_M)
    # Bounds-filtered, never a whole-layout union (the HARD-LAW budget:
    # this is O(rim parts x neighbours near them), tens of distance
    # calls per facility).
    neighbours = []
    for s in shapes:
        if getattr(s, "role", None) not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        try:
            neighbours.append((poly.bounds, poly, s))
        except Exception:                                 # pragma: no cover
            continue
    for plate in plates:
        report["parts"] += 1
        try:
            seed = float(plate.node_altitudes[0])
        except (TypeError, ValueError, IndexError):       # pragma: no cover
            continue
        report["before"].append(seed)
        b = plate.polygon.bounds
        near = [(poly, s) for (bb, poly, s) in neighbours
                if bb[0] <= b[2] + window and bb[2] >= b[0] - window
                and bb[1] <= b[3] + window and bb[3] >= b[1] - window]
        hit = _rim_neighbour_value(plate.polygon, near, window)
        if hit is None:
            report["kept_seed"] += 1
            report["after"].append(seed)
            continue
        value = float(hit[0])
        move = abs(value - seed)
        n = len(plate.node_altitudes or ())
        plate.node_altitudes = [round(value, 2)] * n
        plate.altitude = None
        plate.altitude_high = None
        plate.altitude_low = None
        report["reseated"] += 1
        report["refs"][hit[1]] = report["refs"].get(hit[1], 0) + 1
        report["after"].append(value)
        if move > report["worst_move_m"]:
            report["worst_move_m"] = move
    _republish_basin_declarations(layout, plates, report)
    return report


#: ``terrace_joints`` rows minted for a pan↔rim wall carry this kind, so
#: a reader can tell a declared PIT WALL from a declared apron terrace
#: without re-deriving either.  Ignored by ``check_grade``'s
#: ``_terrace_joints_to_m``, which reads ``points`` and ``step_m`` only.
BASIN_WALL_JOINT_KIND = "basin_trench_wall"

#: ...and the PAD-AUTHORITY CARVE's own joint kind (spec
#: ``docs/specs/lemd-pad-authority-carve-spec.md`` §2): the declared step
#: between a carve corridor's floor plate and the PAD whose flattening
#: authority the owner carved.  A distinct kind from the pan↔rim wall
#: because the two sides differ — that one walls the pit's own rim band,
#: this one walls a building pad — and an attribution that cannot tell
#: them apart cannot say which law drew the step.
BASIN_CARVE_WALL_JOINT_KIND = "basin_pad_carve_wall"

#: Where the emitter records its carve plates for the post-solve
#: declaration.  ONE spelling, read by the emitter, the publisher and
#: the tests.
BASIN_CARVE_PLATES_ATTRIBUTE = "_basin_carve_plates"


def _republish_basin_declarations(layout, plates, report):
    """THE DECLARATION FOLLOWS THE EMISSION (spec lemd-rim-and-stations
    Amendment 2, 2026-08-28), in two halves.

    (a) THE SIDECAR RECORD BECOMES HONEST.  The facility record is
    written at the PRE-SOLVE emitter, so after the re-seat above it
    declared ``emitted_rim_parts_m`` = R_est while the patch carried the
    adopted value — measured at LEMD: 596.30 declared against 600.47
    emitted.  That is the 2026-08-09 recon's own defect ("the facility
    log line prints the law value, not what was emitted"), and it is
    what made ``check_grade._basin_declared_drop`` allow only 8.55 m of a
    12.72 m wall: 4.17 m of excess on every wall pair, 1,932 rows.

    (b) THE PAN↔RIM JOINT IS DECLARED BY NAME.  The wall between the
    floor pan and its rim band is the trench law's own designed step —
    the declared-terrace class — so each part publishes a JOINT into the
    census's existing declared-step register (the ``terrace_joints``
    key).  The line is the BODY OUTLINE, which lies exactly between the
    pan (``body`` inset by the wall setback) and the band (``body``
    grown by the rim width): a pan↔rim chord crosses it, and so does the
    pad↔pan standoff chord §1's stand-down created.  An UNDECLARED
    trench step still prices in full — this is a joint register, never a
    role-based blanket exemption.
    """
    from shapely.ops import unary_union
    records = getattr(layout, BASIN_FACILITY_RECORDS_ATTRIBUTE, None) or []
    values = [v for v in (report.get("after") or ()) if v == v]
    if records and values:
        for record in records:
            record["emitted_rim_parts_m"] = sorted(
                round(float(v), 4) for v in values)
            record["emitted_rim_min_m"] = round(float(min(values)), 4)
            record["emitted_rim_max_m"] = round(float(max(values)), 4)
            record["emitted_rim_part_count"] = len(values)
            record["rim_reseated_post_solve"] = bool(report.get("reseated"))
    floors = [s.polygon for s in (getattr(layout, "shapes", None) or ())
              if str(getattr(s, "ref", "") or "") == BASIN_FLOOR_PLATE_REF
              and s.polygon is not None and not s.polygon.is_empty]
    joints = list(getattr(layout, "_basin_wall_joints", None) or [])
    # (c) THE CARVED PAD EDGE, declared FIRST so it does not ride on the
    # rim wall's own preconditions below (a facility whose floors or
    # records are missing still owes its carve declaration).
    _declare_carve_walls(layout, joints, report)
    if not floors or not plates:
        layout._basin_wall_joints = joints
        return
    try:
        pan = unary_union(floors)
        wall = pan.buffer(_TUNNEL_WALL_SETBACK_M, join_style=2,
                          mitre_limit=2.0).boundary
    except Exception:                                     # pragma: no cover
        layout._basin_wall_joints = joints
        return
    floor_m = None
    for record in records:
        try:
            floor_m = float(record["floor_m"])
        except (KeyError, TypeError, ValueError):         # pragma: no cover
            continue
        break
    if floor_m is None:                                   # pragma: no cover
        layout._basin_wall_joints = joints
        return
    reach = (_TUNNEL_RIM_BAND_WIDTH_M + _TUNNEL_WALL_SETBACK_M + 0.5)
    for plate in plates:
        try:
            value = float(plate.node_altitudes[0])
            arc = wall.intersection(plate.polygon.buffer(reach))
        except Exception:                                 # pragma: no cover
            continue
        if arc.is_empty:
            continue
        step = value - floor_m
        if step <= 0.0:
            continue
        parts = (list(arc.geoms) if arc.geom_type.startswith("Multi")
                 or arc.geom_type == "GeometryCollection" else [arc])
        for piece in parts:
            if getattr(piece, "geom_type", "") != "LineString":
                continue
            pts = [(float(x), float(y)) for (x, y) in piece.coords]
            if len(pts) < 2:
                continue
            joints.append({"points_m": pts, "step_m": float(step)})
    layout._basin_wall_joints = joints
    report["wall_joints"] = len(joints)


def _declare_carve_walls(layout, joints, report):
    """(c) THE PAD EDGE ALONG THE CARVE CORRIDOR IS DECLARED (spec
    ``docs/specs/lemd-pad-authority-carve-spec.md`` §2).

    The carve takes the ramp corridor out of a building pad's flattening
    authority, so the corridor's own outer edge is a step from the pad's
    flat level down to the facility floor.  That step is the trench law's
    DESIGNED wall exactly as the pan↔rim step is — the difference is only
    which surface stands on the high side — so it publishes into the SAME
    declared-step register (``terrace_joints``), through the same rows,
    under its own ``kind``.  An UNDECLARED step still prices in full;
    this is a joint register, never a role-based blanket exemption.

    The high side is read from the PAD ITSELF, post-solve
    (``_shape_value_at``), never from the law: the pad is a solved
    variable and the declaration must describe what was emitted, which is
    exactly the honesty half (a) of this pass exists to fix.  Only the
    stretch of the plate boundary that lies INSIDE the carved pad is
    declared — where the plate meets the body it is the pan↔rim wall's
    joint, already published above, and declaring one step twice would
    let a reader believe two walls stand there.
    """
    records = getattr(layout, BASIN_CARVE_PLATES_ATTRIBUTE, None) or []
    if not records:
        return
    declared = 0
    for record in records:
        try:
            floor_m = float(record["floor_m"])
        except (KeyError, TypeError, ValueError):         # pragma: no cover
            continue
        pads = [pad for pad in (record.get("pads") or ())
                if getattr(pad, "polygon", None) is not None
                and not pad.polygon.is_empty]
        if not pads:
            continue
        for plate in (record.get("plates") or ()):
            if plate is None or plate.is_empty:
                continue
            for pad in pads:
                try:
                    arc = plate.boundary.intersection(
                        pad.polygon.buffer(-_TUNNEL_WALL_SETBACK_M,
                                           join_style=2, mitre_limit=2.0))
                except Exception:                         # pragma: no cover
                    continue
                if arc is None or arc.is_empty:
                    continue
                value = _shape_value_at(pad, plate.centroid)
                if value is None or value != value:
                    continue
                step = float(value) - floor_m
                if step <= 0.0:
                    continue
                parts = (list(arc.geoms)
                         if arc.geom_type.startswith("Multi")
                         or arc.geom_type == "GeometryCollection"
                         else [arc])
                for piece in parts:
                    if getattr(piece, "geom_type", "") != "LineString":
                        continue
                    pts = [(float(x), float(y)) for (x, y) in piece.coords]
                    if len(pts) < 2:
                        continue
                    joints.append({"points_m": pts, "step_m": step,
                                   "kind": BASIN_CARVE_WALL_JOINT_KIND})
                    declared += 1
    if declared:
        report["carve_wall_joints"] = declared
        UI.vprint(
            1,
            f"  [object-basin] PAD-AUTHORITY CARVE: {declared} declared "
            "wall joint(s) published along the carved pad edge — the "
            "plate-to-pad step is the trench law's designed wall, "
            "declared in the census's own register (spec §2)",
        )


def basin_wall_joints_sidecar(layout) -> list:
    """The pan↔rim wall joints as ``terrace_joints`` rows (lat/lon at 11
    decimals, the canonical identity spelling).

    ONE REGISTER, two producers — the apron terrace plan and this — so
    ``check_grade`` reads the identical declared population from the
    identical key and nothing here re-derives a second notion of "a
    declared step".  Empty when no basin re-seated.

    ``carried`` is the Amendment-3 flag, ONE PER POINT and aligned with
    ``points``: is this stretch of the wall inside a below-grade region
    a pad/shell CARRIES?  The geometry is the yield population's own
    (``layout._basin_carried_regions``, recorded where the 2026-08-26
    ruling yields a pad's authority over the region it spans), so there
    is no second notion of "carried" to drift.  A carried stretch does
    not sever a taxi route — the route rides the shell above it — and
    the census exempts the route/strip terrace families exactly there;
    an arc on OPEN ground prices in full.
    """
    from shapely.geometry import Point as _Pt
    carried_regions = [r for r in (getattr(
        layout, "_basin_carried_regions", None) or ())
        if r is not None and not r.is_empty]
    rows = []
    for joint in (getattr(layout, "_basin_wall_joints", None) or ()):
        try:
            pts_m = [(float(x), float(y)) for (x, y) in joint["points_m"]]
            pts = [layout.m_to_ll(x, y) for (x, y) in pts_m]
        except Exception:                                 # pragma: no cover
            continue
        if len(pts) < 2:
            continue
        carried = []
        for (x, y) in pts_m:
            hit = False
            for region in carried_regions:
                try:
                    if region.covers(_Pt(x, y)):
                        hit = True
                        break
                except Exception:                         # pragma: no cover
                    continue
            carried.append(hit)
        rows.append({
            "points": [[round(float(la), 11), round(float(lo), 11)]
                       for (la, lo) in pts],
            "step_m": round(float(joint["step_m"]), 4),
            "declared_step_m": round(float(joint["step_m"]), 4),
            "faced": True,
            # The joint carries its OWN kind when it has one (the
            # PAD-AUTHORITY CARVE's plate↔pad wall); the pan↔rim wall is
            # the default because it is the kind that predates the key.
            "kind": joint.get("kind") or BASIN_WALL_JOINT_KIND,
            "carried": carried,
            "actual_step_m": None,
            "flank_span_m": None,
            "panel_lo": None,
            "panel_hi": None,
        })
    return rows


def format_rim_reseat_report(icao: str, report: dict) -> str:
    """The build log's one line for the §C post-solve re-seat."""
    before = report.get("before") or [0.0]
    after = report.get("after") or [0.0]
    refs = report.get("refs") or {}
    ref_text = ("" if not refs else "; adopted " + ", ".join(
        f"{k!r}×{v}" for k, v in sorted(refs.items())[:6]))
    return (f"  [object-basin] {icao}: rim RE-SEAT post-solve — "
            f"{report['reseated']} of {report['parts']} band part(s) took "
            f"their nearest SOLVED anchored neighbour (worst move "
            f"{report['worst_move_m']:.2f} m), {report['kept_seed']} kept "
            f"the R_est seed; band {min(before):.2f}-{max(before):.2f} m "
            f"-> {min(after):.2f}-{max(after):.2f} m{ref_text}.  "
            f"One-directional adoption: the neighbour never moves "
            f"(spec lemd-rim-and-stations Amendment 1 §2)")


def build_tunnel_layout_shapes(layout, dem, tile_lat, tile_lon):
    """Feature A (``O4_OBJECT_TUNNEL_TERRAIN``, spec section 3.3 + amendment
    A1, ruling R12): born pre-solve tunnel-trench terrain as FIRST-CLASS
    layout shapes — the one-solve doctrine, mirroring
    ``bridges.build_bridge_layout_shapes``.

    Per classified tunnel (``classification.tunnels``, cached by
    :func:`attach_bridge_classification`):

    * **Datum** (the circular-datum rule): the object drapes at
      ``terrain(anchor)``, so the anchor's terrain is PINNED at layout as a
      solver INPUT — the DEM value at the placement anchor.
    * **Whole-body trench** (amendment A1): the WHOLE deck footprint (body +
      mouths) is cut, not the mouths alone — the roof OBJECT is the visible
      ground over the body, and terrain left at grade there would z-fight
      the roof slab.  A flat floor pan is born at the law floor
      (``grade_law.tunnel_trench_floor_elevation_m`` = datum − body depth −
      ``TUNNEL_FLOOR_BELOW_OBJECT_DECK_M``), and a rim band is born at the
      datum (``grade_law.tunnel_trench_rim_elevation_m``) — the two rows a
      node-split apart form the near-vertical R2 wall.
    * **FLUSH WALLS** (user screenshots 2026-07-18c): the floor pan covers
      the body footprint TO ITS EDGE, and the datum rim band sits OUTSIDE
      the body (``_TUNNEL_WALL_SETBACK_M`` .. + ``_TUNNEL_RIM_BAND_WIDTH_M``)
      — so the unavoidable mesh batter (two node rows can never share an
      x,y) leans OUTWARD from the shell and the terrain never pokes through
      the object's own vertical walls.  The previous inside-the-body
      collar + 1.2 m floor inset left the wall base protruding up to
      1.2 m INTO the shell.  Where the body abuts airside pavement the
      wall top is the pavement edge itself (the outward band yields to
      every already-born shape) and the floor keeps a
      ``_TUNNEL_FLOOR_OWNED_CLEARANCE_M`` bucket-safe clearance from
      every earlier-born shape.
    * **PAVEMENT WINS** (rulings R2/R8): the airside pavement union is
      subtracted from the body before birth and the yielded area is logged.
      **Except over an OPEN PIT** (ruling R13, owner 2026-07-30): there the
      pavement is CUT instead — see the open-pit note below.

    Both plates carry ``layout.ROLE_TUNNEL_TRENCH`` — a flat-by-law terrain
    role wired (decimation exemption, weld LAW tier, per-node ``alt_abs`` at
    ``to_osm``, no within-shape grade rule) exactly like the bridge plates
    with ONE deliberate difference: it is OFF-PAVEMENT terrain (R2 subtracts
    the airside pavement from the body before birth), so it is NOT a
    pavement solver member (absent from ``PAVEMENT_ROLES``) and is born with
    ``record_pins=False``.  That keeps the deep floor from dragging adjacent
    airside pavement through the one-solve while the flat-by-law per-node
    ``alt_abs`` still cuts the trench and wins the LAW-tier weld at any
    shared vertex.  Returns ``(floor_plate_count, rim_plate_count)``; all
    zeros when the gate is off or no tunnel classified.

    **Open pits ride the same machinery** (``config.OBJECT_BASIN_TRENCH``):
    :func:`basin_trench_structures` adapts feature-C BOWL_UNDER_DECK /
    TRENCH_SPINE interfaces into trench records, which enter here beside
    the classified tunnels and are cut identically — an open basin is the
    cut-and-cover case with no roof.  The two gates are independent, so
    either family can be exercised alone.

    **RULING R13 — an open pit takes the pavement with it** (owner
    2026-07-30, "for below grade drainage objects, cut a trench in the
    pavement").  A basin whose interface is an OPEN pit
    (``object_terrain_features.is_open_pit_interface``: nothing of the
    pack's own stands over it) cuts every taxi/junction/apron/service
    shape over its body through the SAME
    ``bridges.cut_pavement_over_footprint`` R8 uses for hard decks,
    instead of yielding to them under R2.  Without it the two OTHH basins
    the owner reported stayed buried: their bodies lay wholly under an
    apron the pack's own DSF draws across the pit, so the floor pan
    yielded to the last square metre and no plate was ever born.  A cut
    that then fails to seat a floor is PUT BACK — pavement removed with
    no trench under it is a hole in the drivable surface.  Every other
    carved basin (and every tunnel) keeps R2 unchanged."""
    tunnel_terrain_enabled = config.OBJECT_TUNNEL_TERRAIN
    basin_terrain_enabled = config.OBJECT_BASIN_TRENCH
    if not (tunnel_terrain_enabled or basin_terrain_enabled):
        return 0, 0
    classification = getattr(layout, CLASSIFICATION_ATTRIBUTE, None)
    if classification is None:
        return 0, 0
    trench_structures = []
    if tunnel_terrain_enabled:
        trench_structures.extend(
            getattr(classification, "tunnels", None) or [])
    if basin_terrain_enabled:
        trench_structures.extend(basin_trench_structures(classification))
    if not trench_structures:
        return 0, 0

    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    from .bridges import (
        _local_meter_projections,
        _BRIDGE_PIN_ROLES,
        born_flat_solver_plate,
        cut_pavement_over_footprint,
        pavement_cut_roles,
    )
    from .elevation import _sample_dem
    from .grade_law import (
        basin_trench_floor_elevation_m,
        tunnel_trench_floor_elevation_m,
        tunnel_trench_rim_elevation_m,
    )
    from .layout import ROLE_BUILDING, ROLE_TUNNEL_TRENCH

    to_meters, _meters_to_lat_lon = _local_meter_projections(layout.anchor)

    # Airside pavement union (rulings R2/R8: pavement always wins over the
    # trench — the roof-slab-versus-pavement coplanarity is open question 5).
    pavement_polygons = [
        shape.polygon for shape in layout.shapes
        if shape.role in _BRIDGE_PIN_ROLES
        and shape.polygon is not None and not shape.polygon.is_empty
    ]
    try:
        pavement_union = (
            unary_union(pavement_polygons) if pavement_polygons else None
        )
    except Exception:
        pavement_union = None
    # RULING R13's own coverage view.  It is WIDER than the airside union
    # above — an open pit can sit under LANDSIDE pavement just as easily
    # (Drainage_02 is buried by groundside pavement alone, with zero
    # apron over it), so gating the cut on the airside union would have
    # skipped it entirely.  R8's scope is unchanged.
    open_pit_cut_roles = pavement_cut_roles(include_groundside=True)
    open_pit_union = None

    def _reindex_open_pit_union():
        nonlocal open_pit_union
        polygons = [
            shape.polygon for shape in layout.shapes
            if shape.role in open_pit_cut_roles
            and shape.polygon is not None and not shape.polygon.is_empty
        ]
        try:
            open_pit_union = unary_union(polygons) if polygons else None
        except Exception:
            open_pit_union = None

    # Ground already owned by ANY earlier-born shape: the outward rim band
    # must never re-grade it (its nodes then serve as the wall-top row).
    # Kept as (bounds, polygon) entries and bbox-filtered per body — a
    # whole-layout unary_union costs seconds at an EGLL-sized airport
    # (HARD-LAW budget) and only the shapes beside each trench matter.
    #
    # Each entry carries its SHAPE as well as its bounds and polygon: the
    # basin-pad floor seating (spec ``basin-pad-floor-seating-spec.md``
    # §1.2) excludes named shapes from the differencing, and the §2 named
    # line reports each differencing shape's ROLE and AREA — both need the
    # shape, not just its geometry.
    owned_entries = [
        (shape.polygon.bounds, shape.polygon, shape)
        for shape in layout.shapes
        if shape.polygon is not None and not shape.polygon.is_empty
    ]

    def _reindex_owned_ground():
        """Re-derive the owned-ground index from ``layout.shapes``.

        It is a snapshot of the layout AS IT STOOD when this emitter
        started, and the ruling-R13 cut below REPLACES pavement shapes
        mid-pass — a stale index would keep yielding the trench floor to
        pavement this function has already removed.  Bounds only, no
        geometry ops: this runs after every cut."""
        owned_entries[:] = [
            (shape.polygon.bounds, shape.polygon, shape)
            for shape in layout.shapes
            if shape.polygon is not None and not shape.polygon.is_empty
        ]

    def _drop_cut_from_unions(body):
        """Take a just-cut body out of the cached pavement unions.

        REBUILDING them from ``layout.shapes`` after every cut is what a
        first version did, and at OTHH it put this whole function at
        1.179 s — past the 0.6 s review line — because each rebuild
        unions ~1 500 polygons twice over.  Subtracting the body is
        local, and exact where it is read: the cut removes precisely
        ``body`` from pavement, and pit bodies never overlap each other,
        so no later facility can observe the difference.  (The tiny
        sub-5 m² remainder slivers the cut also drops are pavement
        OUTSIDE the body; they survive here, which only ever makes the
        next facility's coverage estimate conservative.)"""
        nonlocal pavement_union, open_pit_union
        if pavement_union is not None:
            try:
                pavement_union = pavement_union.difference(body)
            except Exception:
                pass
        if open_pit_union is not None:
            try:
                open_pit_union = open_pit_union.difference(body)
            except Exception:
                pass

    def _rebuild_pavement_unions():
        """Full rebuild — only the RESTORE path needs it (a subtraction
        cannot be undone), and restores are the rare failure branch."""
        nonlocal pavement_union
        current_pavement = [
            shape.polygon for shape in layout.shapes
            if shape.role in _BRIDGE_PIN_ROLES
            and shape.polygon is not None and not shape.polygon.is_empty
        ]
        try:
            pavement_union = (
                unary_union(current_pavement) if current_pavement else None
            )
        except Exception:
            pavement_union = None
        _reindex_open_pit_union()

    def _owned_entries_near(bounds, exclude_ids=()):
        """The owned-ground entries whose bbox meets ``bounds``.

        ``exclude_ids`` is a set of ``id(shape)`` the caller has taken OUT
        of the owned ground — the basin-pad floor seating's one and only
        mechanism (spec §1.2: "the facility floor is NOT differenced
        against such a pad").  Bounds-filtered, never a whole-layout
        union: see ``owned_entries``."""
        minimum_x, minimum_y, maximum_x, maximum_y = bounds
        return [
            entry for entry in owned_entries
            if entry[0][0] <= maximum_x and entry[0][2] >= minimum_x
            and entry[0][1] <= maximum_y and entry[0][3] >= minimum_y
            and id(entry[2]) not in exclude_ids
        ]

    # §C's neighbour population, read off the SAME owned-ground index —
    # it is already maintained across every cut (``_reindex_owned_
    # ground``), so the rim never asks a stale layout what its
    # neighbours are, and there is no second enumeration to drift.
    _rim_neighbour_role_set = _rim_neighbour_roles()

    def _rim_neighbours_near(bounds):
        """``[(polygon, shape), ...]`` — built-surface shapes whose bbox
        comes within the §C window of ``bounds``."""
        window = float(config.TUNNEL_RIM_NEIGHBOUR_WINDOW_M)
        min_x, min_y, max_x, max_y = bounds
        return [
            (entry[1], entry[2]) for entry in owned_entries
            if entry[2].role in _rim_neighbour_role_set
            and entry[0][0] <= max_x + window
            and entry[0][2] >= min_x - window
            and entry[0][1] <= max_y + window
            and entry[0][3] >= min_y - window
        ]

    def _owned_near(bounds, exclude_ids=()):
        candidates = [
            entry[1] for entry in _owned_entries_near(bounds, exclude_ids)]
        if not candidates:
            return None
        try:
            return unary_union(candidates)
        except Exception:
            return None

    floor_plate_count = 0
    rim_plate_count = 0
    # SAME-ANCHOR FACILITY GROUPING (user 2026-07-18f): a long cut-and-
    # cover facility ships as SEVERAL shell objects placed at ONE anchor
    # (EGLL west: the ramp skin and the crossing box share a placement
    # point, the open trench between them has no object at all — it was
    # left covered by terrain).  Tunnels sharing an anchor are one
    # facility: their bodies merge, and for two or more members the
    # open CORRIDOR between the shells (the union's minimum rotated
    # rectangle, only when trench-shaped) is cut at the facility floor.
    facilities: dict = {}
    for tunnel in trench_structures:
        anchor_longitude, anchor_latitude = tunnel.anchor_longitude_latitude
        # The feature tag joins the key: a basin and a tunnel that happen
        # to share an anchor point are not one facility, and the
        # corridor cut below would bridge the gap between them.
        anchor_key = (getattr(tunnel, "terrain_feature", "tunnel"),
                      round(anchor_longitude * 100000.0),
                      round(anchor_latitude * 100000.0))
        facilities.setdefault(anchor_key, []).append(tunnel)

    for facility_tunnels in facilities.values():
        # Plate and log naming follow the classifier the facility came
        # from (the geometry treatment is identical) so an in-sim defect
        # is traceable without re-running the classifier.
        is_basin_facility = (
            getattr(facility_tunnels[0], "terrain_feature", "tunnel")
            == object_terrain_features.TERRAIN_FEATURE_BASIN)
        log_tag = "object-basin" if is_basin_facility else "object-tunnel"
        plate_prefix = "object_basin" if is_basin_facility \
            else "object_tunnel"
        # RULING R13 (owner 2026-07-30, "for below grade drainage objects,
        # cut a trench in the pavement"): an OPEN pit takes the airside
        # pavement with it instead of yielding to it under R2.  ALL
        # members must qualify — a facility with one non-pit shell has
        # something of the pack's own standing over the shared anchor,
        # and R2 keeps that surface.
        facility_cuts_pavement = all(
            getattr(tunnel, "cuts_pavement", False)
            for tunnel in facility_tunnels)
        member_records = []
        for tunnel in facility_tunnels:
            resources = tunnel.object_resources
            if tunnel.body_depth_m is None or tunnel.body_depth_m <= 0.0:
                UI.vprint(
                    1,
                    f"   [{log_tag}] {resources}: no below-grade body "
                    "depth — skipped",
                )
                continue
            anchor_longitude, anchor_latitude = (
                tunnel.anchor_longitude_latitude)
            datum = _sample_dem(
                dem, tile_lat, tile_lon, anchor_latitude, anchor_longitude
            )
            if datum is None or datum != datum:
                # Silent-zero rule (this project's classic failure mode):
                # a missing datum is announced at verbosity 1, never
                # swallowed.
                UI.vprint(
                    1,
                    f"   [{log_tag}] {resources}: no DEM datum at the "
                    "anchor — skipped",
                )
                continue
            # The deck's effective level is negative below grade; the AGL
            # offset is already folded into ``body_depth_m`` (classifier
            # effective height).  The floor keys on the DEEPEST SOLID of
            # the whole structure when the classifier measured it (user
            # 2026-07-18: EGLL shell walls reach up to ~2 m below the
            # road deck — a deck-median floor left the object bottoms
            # buried), falling back to the deck median for older records.
            # THE OPEN-PIT LIMB (owner Amendment 3): a hole with nothing
            # of the pack's own over it keys on its DECK FACE and takes
            # no bore margins.  ``cuts_pavement`` IS
            # ``object_terrain_features.is_open_pit_interface`` read off
            # the record (R13's own predicate) — one notion, one
            # spelling, never re-derived.
            _member_open_pit = bool(getattr(tunnel, "cuts_pavement", False))
            deck_reference_y, discarded_witness, floor_key_source = (
                basin_facility_deck_reference_y(
                    tunnel, open_pit=_member_open_pit))
            if discarded_witness is not None:
                # LOUD, NEVER SILENT (spec §2.2): the resource whose
                # authored geometry claimed the floor, the y it claimed
                # it at, and the population that overrode it.  The 43 m
                # LEMD disagreement used to ride two numbers on one
                # trench-floor log line and nothing looked at it.
                UI.vprint(
                    1,
                    f"   [{log_tag}] BASIN FLOOR DISAGREEMENT: "
                    f"{resources}: deepest-solid witness "
                    f"{discarded_witness:.3f} m disagrees with the "
                    f"deck-face body depth "
                    f"{float(tunnel.body_depth_m):.3f} m by "
                    f"{abs(discarded_witness + float(tunnel.body_depth_m)):.3f}"
                    f" m (> {config.BASIN_FLOOR_DISAGREEMENT_M:.1f} m) — "
                    f"the witness is DISCARDED and the floor derives from "
                    f"the body depth",
                )
            member_floor = tunnel_trench_floor_elevation_m(
                float(datum), deck_reference_y
            )
            member_rim = tunnel_trench_rim_elevation_m(float(datum))
            member_parts = _tunnel_footprint_meters_parts(tunnel, to_meters)
            if not member_parts:
                UI.vprint(
                    1,
                    f"   [{log_tag}] {resources}: no deck footprint to "
                    "cut — skipped",
                )
                continue
            member_records.append(
                (tunnel, float(datum), member_floor, member_rim,
                 deck_reference_y, member_parts, floor_key_source))
        if not member_records:
            continue
        resources = sorted({
            resource for tunnel, *_rest in member_records
            for resource in tunnel.object_resources})
        datum = min(record[1] for record in member_records)
        # Indexed, not star-unpacked: the record grew a seventh field
        # (the floor KEY SOURCE, owner Amendment 3) and ``*_head, parts``
        # would silently have bound ``parts`` to it.
        body_parts = [
            part for record in member_records for part in record[5]]
        # ── THE RAMP-REACH CORRIDOR (spec lemd-basin-trench-ramp-
        # extension Amendment 1 §2; gate BASIN_RAMP_REACH_PLATE) ──
        # Read AFTER ``body_parts`` and kept strictly out of them.  Every
        # law input below — R_est, the floor and rim values, the pad
        # coverage test — and the post-mesh R_mesh sample band are read
        # from ``body_parts``, and Amendment 1 exists because a round
        # that folded the ramp into them moved all four.  The corridor is
        # consumed in exactly two places: it JOINS the floor pan, and the
        # rim band STANDS DOWN inside it.
        ramp_corridor = None
        if config.basin_ramp_corridor_carried() and is_basin_facility:
            corridor_parts = [
                corridor for corridor in (
                    _tunnel_ramp_corridor_meters(record[0], to_meters)
                    for record in member_records)
                if corridor is not None
            ]
            if corridor_parts:
                try:
                    ramp_corridor = unary_union(corridor_parts)
                    # Never inside the body: the body owns its own floor
                    # pan and rim band, and an overlap would emit the
                    # same ground twice.
                    ramp_corridor = ramp_corridor.difference(
                        unary_union(body_parts))
                except Exception:
                    ramp_corridor = None
                if ramp_corridor is not None and ramp_corridor.is_empty:
                    ramp_corridor = None
        # ── THE BASIN RIM REFERENCE (spec section 2.1 item 2) ──
        # For a BASIN facility the point datum above is replaced, for the
        # floor and rim LAWS, by ``R_est``: the median DEM elevation
        # around this facility's own body outline.  The anchor sample
        # stays what it always was — the value the DRAPED object seats on
        # — and is still reported; it is no longer a law input here.
        # Tunnel facilities are untouched: they keep the datum-keyed law
        # byte for byte (no OTHH fixture exercises them and the EGLL
        # class must not move).
        basin_rim_estimate = None
        basin_rim_estimate_is_fallback = False
        if is_basin_facility:
            basin_rim_estimate = _basin_rim_estimate_elevation_m(
                body_parts, dem, tile_lat, tile_lon, _meters_to_lat_lon)
            if basin_rim_estimate is None:
                # Silent-zero rule: a DEM that answers nowhere around the
                # outline falls back to the anchor datum — the value this
                # facility used before the spec — and SAYS SO.
                basin_rim_estimate = float(datum)
                basin_rim_estimate_is_fallback = True
                UI.vprint(
                    1,
                    f"   [{log_tag}] {resources}: no DEM sample around "
                    "the body outline — the rim reference falls back to "
                    f"the anchor datum {float(datum):.2f} m",
                )
        if basin_rim_estimate is not None:
            # ── THE MARGINS ARE A BORE'S, NOT A PIT'S (owner Amendment
            # 3, 2026-08-25: "a simple 7 m deep cutout for the whole area
            # should work without having to sever the buildings") ──────
            # "An open-pit facility's floor is the pooled solids'
            # deck-face median (body_depth_m) with ZERO tunnel margins —
            # TUNNEL_FLOOR_BELOW_OBJECT_DECK_M and
            # TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M apply only to true bore
            # basins (a deck you pass under)."
            #
            # THE DISCRIMINATOR IS THE ENGINE'S OWN NOTION OF A DECK YOU
            # PASS UNDER: ``is_open_pit_interface`` — "a hole with
            # nothing of the pack's own standing over it" — read off the
            # record as ``cuts_pavement``, the same predicate R13 keys
            # on.  Its docstring names the bore cases in the owner's own
            # terms: a BOWL_UNDER_DECK with a drum floating over it, a
            # TRENCH_SPINE with halls at grade over it.  Nothing is
            # re-derived here.
            #
            # This reproduces the amendment's own arithmetic exactly:
            # LEMD R_est 593.029 − body 7.0159 = 586.013 ("≈586.01",
            # "593.03 − 7.02"), against today's 584.499.
            #
            # ⚠ MEASURED CONFLICT WITH THE AMENDMENT'S OTHH CLAUSE — see
            # the commit message.  Item 4 asserts "OTHH's basins are
            # bore-class"; the classification says otherwise for six of
            # its eight facilities.  OTHH's Drainage_01/02/03/04/05/06
            # are BOWL_UNDER_DECK, ``is_open_pit_interface`` TRUE,
            # ``elevated_deck_above`` FALSE, above-grade fraction 0.000 —
            # structurally IDENTICAL to LEMD's LEMD36 on every axis, and
            # numerically inseparable from it too (solid witness within
            # 0.014-0.34 m of the deck face at BOTH airports).  Only
            # AuxBuilding_13/17 are genuine bores (TRENCH_SPINE, deck
            # above, above-grade 0.24-0.36) and those are unchanged.  So
            # the rule as ruled moves the six Drainage floors +1.5 m and
            # OTHH is NOT byte-identical; there is no predicate that
            # separates LEMD from them.  Ruled law implemented, conflict
            # reported with the numbers rather than silently scoped away.
            facility_is_bore = not facility_cuts_pavement
            floor_elevation = min(
                basin_trench_floor_elevation_m(
                    basin_rim_estimate, record[4],
                    bore_class=facility_is_bore)
                for record in member_records)
            rim_elevation = tunnel_trench_rim_elevation_m(basin_rim_estimate)
        else:
            floor_elevation = min(record[2] for record in member_records)
            rim_elevation = min(record[3] for record in member_records)
        if len(member_records) >= 2:
            # The open trench BETWEEN the facility's shells: the union's
            # minimum rotated rectangle, admitted only when it is
            # trench-shaped (elongated) — a blocky spread would over-cut.
            try:
                facility_union = unary_union(body_parts)
                corridor = min_rotated_rect(facility_union)
                ring = list(corridor.exterior.coords)
                side_a = math.hypot(ring[1][0] - ring[0][0],
                                    ring[1][1] - ring[0][1])
                side_b = math.hypot(ring[2][0] - ring[1][0],
                                    ring[2][1] - ring[1][1])
                long_side = max(side_a, side_b)
                short_side = max(min(side_a, side_b), 1e-9)
                if long_side / short_side >= 3.0:
                    added = corridor.difference(facility_union).area
                    body_parts = [corridor]
                    UI.vprint(
                        1,
                        f"   [{log_tag}] {resources}: facility corridor "
                        f"cut joins {len(member_records)} shells sharing "
                        f"one anchor (+{added:.0f} m2 of open trench)",
                    )
            except Exception:
                pass
        else:
            try:
                merged = unary_union(body_parts)
                body_parts = [
                    part for part in getattr(merged, "geoms", [merged])
                    if part.geom_type == "Polygon" and not part.is_empty]
            except Exception:
                pass
        # Airside-proximity gate (Global-Airports tile DSF: every
        # airport sees every object on the tile — see the constant's
        # comment).  Gated only when pavement evidence exists; a
        # pavement-less layout keeps the legacy behaviour.
        if pavement_union is not None:
            try:
                airside_distance = min(
                    body.distance(pavement_union) for body in body_parts)
            except Exception:
                airside_distance = 0.0
            if airside_distance > _TUNNEL_MAX_AIRSIDE_DISTANCE_M:
                UI.vprint(
                    1,
                    f"   [{log_tag}] {resources}: body "
                    f"{airside_distance:.0f} m from this airport's "
                    "airside — another airport's object, skipped",
                )
                continue

        # ── RULING R13 (owner 2026-07-30) — THE OPEN-PIT PAVEMENT CUT ──
        # "for below grade drainage objects, cut a trench in the
        # pavement".  The pack draws this pit as a hole open to the sky,
        # and at OTHH its own DSF draws apron straight across it (apt.dat
        # leaves the notch unpaved; ``pipeline.pav_polys`` unions the two,
        # so the apron is a FAITHFUL read of the source, not an
        # over-reach).  Under R2 that pavement won and the whole body
        # yielded — Drainage_05 all 519 m2, Drainage_04 2054 of 2055 — so
        # no floor plate was ever born and the modelled pit stayed buried.
        # R13 amends R2/R8 for this one class: cut the pavement, through
        # the same helper R8 uses over a hard deck.
        #
        # ORDER MATTERS TWICE.  It runs BEFORE the anchor seat, because
        # the seat only fires where no earlier shape owns the anchor —
        # with the apron still in place the seat would decline, and then
        # the object would drape on our own trench floor and sink by the
        # cut depth (the exact "object sitting below terrain" defect the
        # seat exists for).  And it runs before the floor geometry, so the
        # floor stops yielding to pavement this pass has just removed.
        pre_cut_shapes = None
        cut_pavement_area = 0.0
        cut_shape_count = 0
        # ── §B, LEG 2 — THE CLIP (spec lemd-rim-and-stations §B.1) ────
        # R13 cut the pavement over the BODY and stopped there, so the
        # 0.6 m rim band — which lives OUTSIDE the body — stayed under
        # the apron, and the apron's own ownership then erased it.
        # Measured at LEMD: apron -10228 standing 0.70-0.89 m off the pan
        # along a 98 m run took the floor cutback AND the whole band, and
        # the owner walked off a 12.75 m unwalled drop at
        # 40.4910231,-3.5688464.  The cut now reaches the rim band's
        # OUTER edge: the pavement abuts the rim, never the pan.
        _rim_clip_on = bool(config.TRENCH_PAVEMENT_YIELD)
        if facility_cuts_pavement:
            if open_pit_union is None:
                _reindex_open_pit_union()
        if facility_cuts_pavement and open_pit_union is not None:
            for body in body_parts:
                cut_footprint = body
                if _rim_clip_on:
                    try:
                        cut_footprint = body.buffer(
                            _TUNNEL_RIM_BAND_WIDTH_M,
                            join_style=2, mitre_limit=2.0)
                    except Exception:                     # pragma: no cover
                        cut_footprint = body
                try:
                    covered_area = cut_footprint.intersection(
                        open_pit_union).area
                except Exception:
                    covered_area = 0.0
                if covered_area <= 0.0:
                    continue
                if pre_cut_shapes is None:
                    pre_cut_shapes = list(layout.shapes)
                body_cut_shapes = cut_pavement_over_footprint(
                    layout, cut_footprint, cut_roles=open_pit_cut_roles)
                if body_cut_shapes:
                    _reindex_owned_ground()
                    _drop_cut_from_unions(cut_footprint)
                    cut_shape_count += body_cut_shapes
                    cut_pavement_area += covered_area
        # (the cut is REPORTED at the end of the facility, where its
        # restore guard has already run — a cut that was put back must
        # never be logged as one that happened.)

        # ── A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR ─────────────
        # (owner RULINGS 2026-08-25f, the building8 disposition; spec
        # ``basin-pad-floor-seating-spec.md`` §1.)
        #
        # A ROLE_BUILDING pad whose footprint lies INSIDE this basin's
        # footprint — ``config.BASIN_PAD_COVERAGE_MIN`` of the PAD's own
        # area — is below the surrounding grade.  Two consequences, and
        # they are one law read twice:
        #
        #   (1) the pad SEATS AT THE FACILITY FLOOR: its declared flat
        #       level is ``floor_elevation``, which the seat producers
        #       stamp onto its ring (``BuiltShape.basin_floor_seat_m``);
        #   (2) the FLOOR IS NOT DIFFERENCED against it — the cut emits
        #       THROUGH the pad, at the same elevation the pad now
        #       carries, instead of being erased by it.
        #
        # WHY BOTH.  LEMD's pack ships ``building8`` (33,447 m²) flat at
        # 600.28 m over the whole 12,251 m² sunken tower circle; the
        # floor pan is differenced against every earlier-born shape, so
        # the pad erased it completely and the basin emitted NOTHING
        # (basinpool round, finding 1).  Seating the pad without the
        # exclusion would leave the basin with a pad but no floor;
        # excluding without seating would leave an 8 m pad-vs-floor
        # z-fight over the same ground.
        #
        # A PARTIAL-COVERAGE PAD IS A DIFFERENT DESIGN CASE and is NOT
        # this rule's: a pad straddling a basin rim keeps today's
        # behaviour (it differences the floor as before, it is not
        # seated) and is REPORTED by name — never silently sorted into
        # either class.  Both reports are UNGATED; only the BEHAVIOUR
        # rides ``config.BASIN_PAD_FLOOR_SEAT``.
        floor_seated_pad_ids: set = set()
        # THE AUTHORITY CLIP's own set (owner Amendment 3): the pads whose
        # FLATTENING AUTHORITY yields inside this facility.  They are not
        # seated and not cut — only taken out of the owned ground the pan
        # and the wall band are differenced against, so both are born
        # THROUGH them.
        authority_yield_pad_ids: set = set()
        # ...and the CARVE's own population (spec lemd-pad-authority-
        # carve §2): the yielding pads themselves, kept in order so the
        # carve can ask them for their geometry and their emitted value.
        # A SUBSET of ``authority_yield_pad_ids`` by construction — it is
        # appended at the same decision.
        carve_pads: list = []
        # ...and the plates the carve actually laid, for §2's DECLARED
        # wall (published post-solve, where the pad carries its solved
        # value).
        _carve_plates: list = []
        if is_basin_facility:
            try:
                facility_geometry = unary_union(body_parts)
            except Exception:
                facility_geometry = None
            if facility_geometry is not None \
                    and not facility_geometry.is_empty:
                facility_area = float(facility_geometry.area)
                # SNAPSHOT.  The Amendment-2 cut below REPLACES pad shapes
                # in ``layout.shapes``; iterating the live list while
                # mutating it is the classic way to miss one.
                pad_snapshot = [
                    s for s in layout.shapes
                    if s.role == ROLE_BUILDING and s.polygon is not None
                    and not s.polygon.is_empty]
                for pad in pad_snapshot:
                    pad_area = float(pad.polygon.area)
                    if pad_area <= 0.0:
                        continue
                    try:
                        overlap = float(
                            pad.polygon.intersection(facility_geometry).area)
                    except Exception:
                        continue
                    if overlap <= 0.0:
                        continue
                    pad_coverage = overlap / pad_area
                    facility_coverage = (
                        overlap / facility_area if facility_area > 0.0
                        else 0.0)
                    where = (f"{pad.ref!r} ({pad_area:.0f} m2) is "
                             f"{100.0 * pad_coverage:.0f} % inside "
                             f"{resources} and covers "
                             f"{100.0 * facility_coverage:.0f} % of it")
                    if max(pad_coverage, facility_coverage) \
                            < config.BASIN_PAD_COVERAGE_MIN:
                        # A pad under threshold on BOTH sides straddles the
                        # basin RIM — a real design case this rule is not
                        # about.  Today's behaviour, and REPORTED by name so
                        # a straddler is never silently sorted into either
                        # class.
                        UI.vprint(
                            1,
                            f"   [{log_tag}] BASIN RIM STRADDLER: pad "
                            f"{where} (both under "
                            f"{100.0 * config.BASIN_PAD_COVERAGE_MIN:.0f} "
                            "%) — its flattening authority is KEPT over "
                            "the facility; today's behaviour",
                        )
                        continue
                    if not config.BASIN_PAD_FLOOR_SEAT:
                        UI.vprint(
                            1,
                            f"   [{log_tag}] BASIN PAD {where} — its "
                            f"flattening authority is NOT yielded over "
                            f"the floor {floor_elevation:.2f} m "
                            "(O4_BASIN_PAD_FLOOR_SEAT=0)",
                        )
                        continue
                    # ── AMENDMENT 3 (owner 2026-08-25): THE AUTHORITY
                    # CLIP — no severing, no seating ──────────────────
                    # "a simple 7 m deep cutout for the whole area
                    # should work without having to sever the
                    # buildings."
                    #
                    # The pad keeps its authored grade, geometry, welds
                    # and identity EVERYWHERE — nothing about the shape
                    # is touched.  What yields is its FLATTENING
                    # AUTHORITY inside the facility: the pad stops
                    # counting as owned ground there, so the floor pan
                    # and the R2 wall band are born THROUGH it and the
                    # facility interior is theirs.  Outside the
                    # footprint the pad's claim stands untouched, and
                    # the mesh interpolates the pad's own ring level
                    # across the ground between (``O4_Vector_Map``'s
                    # INTERP_ALT faces are cut by every patch ring, the
                    # plates' included).
                    #
                    # BOTH ``_owned_near`` reads yield, not just the
                    # floor's: the WALL is the band a node-split
                    # OUTSIDE the body at surrounding grade against the
                    # pan at the floor.  With only the floor yielding,
                    # the band still fell to the pad and the hole
                    # ramped out to the pad's distant ring instead of
                    # walling at the boundary (LEMD arm 1: "no rim band
                    # emitted").
                    #
                    # WHY NOT SEAT OR SEVER — both measured, both kept
                    # and gated off (``config.BASIN_PAD_WHOLE_SEAT`` /
                    # ``config.BASIN_PAD_SEVER``).  Seating the whole
                    # pad cannot bind: LEMD's ``building8`` rigidly
                    # couples to ``building18`` (75,885 m², outside the
                    # basin) through three shared canonical ring nodes,
                    # so the seat either sinks a terminal complex 16 m
                    # or is silently discarded (arm 1 measured the
                    # second).  Severing works but edits the pack's
                    # authored geometry, which the owner ruled out.
                    authority_yield_pad_ids.add(id(pad))
                    # ── THE CARVE POPULATION (spec ``docs/specs/lemd-
                    # pad-authority-carve-spec.md`` §2) ────────────────
                    # THIS is the pad whose flattening authority the
                    # owner carved: the ramp corridor comes out of the
                    # authority of the very pads that already yield to
                    # this facility, and out of NO other pad.  Recorded
                    # off the yield population's own decision — there is
                    # no second test of "does this pad yield here" to
                    # drift from the one above.
                    carve_pads.append(pad)
                    # Amendment 3, 2026-08-28) ──────────────────────
                    # THIS pad is the shell the 2026-08-26 ruling calls
                    # "a shell/bridge over the pit", and the ground it
                    # carries is exactly its footprint inside the
                    # facility.  Recorded HERE, off the yield
                    # population's own geometry, so the declared-wall
                    # route/strip exemption has no second notion of
                    # "carried" to drift from: a wall arc under this
                    # region does not sever a taxi route (the route
                    # rides the shell above it); the same arc on OPEN
                    # ground still prices in full.
                    #
                    # THE REGION INCLUDES ITS OWN WALL BAND, and that is
                    # not a widening: the declared joint line IS the body
                    # outline, so clipping the carried region exactly at
                    # ``facility_geometry`` puts every joint point on the
                    # region's own BOUNDARY, where ``covers`` is a
                    # coin-toss against buffer rounding.  Measured: 248 of
                    # 462 points flagged, 0 arcs fully carried, and 7 of
                    # 11 route rows survived an exemption that should have
                    # cleared them.  The carrier is the PAD; the region is
                    # the pit AND the wall that walls it.
                    try:
                        _carried = pad.polygon.intersection(
                            facility_geometry.buffer(
                                _TUNNEL_RIM_BAND_WIDTH_M
                                + _TUNNEL_WALL_SETBACK_M,
                                join_style=2, mitre_limit=2.0))
                        if not _carried.is_empty:
                            _prev = list(getattr(
                                layout, "_basin_carried_regions", None)
                                or [])
                            _prev.append(_carried)
                            layout._basin_carried_regions = _prev
                    except Exception:                     # pragma: no cover
                        pass
                    UI.vprint(
                        1,
                        f"   [{log_tag}] BASIN PAD AUTHORITY YIELDED: "
                        f"{where} — the pad is UNTOUCHED (grade, "
                        f"geometry, welds, identity) and its flattening "
                        f"authority is clipped to OUTSIDE the facility; "
                        f"the floor plates at {floor_elevation:.2f} m "
                        "and the R2 walls own the interior",
                    )
                    if config.BASIN_PAD_WHOLE_SEAT \
                            and pad_coverage >= config.BASIN_PAD_COVERAGE_MIN:
                        # RETIRED (Amendment 3 item 2), kept and gated
                        # off: §1.1's whole-pad seat.
                        pad.basin_floor_seat_m = float(floor_elevation)
                        floor_seated_pad_ids.add(id(pad))
                        UI.vprint(
                            1,
                            f"   [{log_tag}] BASIN PAD SEATED AT THE "
                            f"FLOOR: {where} — its flat level is the "
                            f"facility floor {floor_elevation:.2f} m "
                            "(O4_BASIN_PAD_WHOLE_SEAT=1, retired path)",
                        )
                        continue
                    if not (config.BASIN_PAD_SEVER
                            and pad_coverage
                            < config.BASIN_PAD_COVERAGE_MIN):
                        continue
                    # ── RETIRED (Amendment 3 supersedes Amendment 2),
                    # kept and gated off: the boundary CUT.  The
                    # in-facility piece became its own pad seated at the
                    # floor; the remainder kept grade, welds and
                    # identity through ``dataclasses.replace``; the
                    # inset was the R2 node split against the cut line.
                    try:
                        inside_geometry = pad.polygon.intersection(
                            facility_geometry)
                        sunken_geometry = inside_geometry.buffer(
                            -_BASIN_PAD_CUT_INSET_M,
                            join_style=2, mitre_limit=2.0)
                        remainder_geometry = pad.polygon.difference(
                            facility_geometry)
                    except Exception:
                        sunken_geometry = None
                        remainder_geometry = None

                    def _pieces(geometry):
                        if geometry is None or geometry.is_empty:
                            return []
                        parts = (list(geometry.geoms)
                                 if geometry.geom_type == "MultiPolygon"
                                 else [geometry])
                        return [part for part in parts
                                if part.geom_type == "Polygon"
                                and not part.is_empty
                                and part.area >= config.PAD_MIN_AREA_M2]

                    sunken_parts = _pieces(sunken_geometry)
                    remainder_parts = _pieces(remainder_geometry)
                    if not sunken_parts:
                        UI.vprint(
                            1,
                            f"   [{log_tag}] BASIN PAD CUT WITHDRAWN: "
                            f"{where}, but its in-facility piece does not "
                            f"survive the {_BASIN_PAD_CUT_INSET_M:.1f} m "
                            f"wall inset at "
                            f"{config.PAD_MIN_AREA_M2:.0f} m2",
                        )
                        continue
                    replacements = []
                    for part in remainder_parts:
                        replacements.append(_dataclass_replace(
                            pad, polygon=part, node_altitudes=None,
                            basin_floor_seat_m=None))
                    for part in sunken_parts:
                        replacements.append(_dataclass_replace(
                            pad, polygon=part, node_altitudes=None,
                            ref=f"{pad.ref}_basin",
                            basin_floor_seat_m=float(floor_elevation)))
                    layout.shapes = [
                        replacement
                        for shape in layout.shapes
                        for replacement in (replacements if shape is pad
                                            else [shape])]
                    authority_yield_pad_ids.discard(id(pad))
                    # ...and out of the carve population with it: the
                    # SEVER path replaced this pad in ``layout.shapes``,
                    # so it no longer exists to carve anything from.
                    carve_pads[:] = [p for p in carve_pads if p is not pad]
                    _reindex_owned_ground()
                    UI.vprint(
                        1,
                        f"   [{log_tag}] BASIN PAD CUT AT THE FACILITY "
                        f"BOUNDARY: {where} — "
                        f"{sum(p.area for p in sunken_parts):.0f} m2 in "
                        f"{len(sunken_parts)} piece(s) seat at the floor "
                        f"{floor_elevation:.2f} m as "
                        f"{pad.ref + '_basin'!r}; "
                        f"{sum(p.area for p in remainder_parts):.0f} m2 in "
                        f"{len(remainder_parts)} piece(s) keep grade as "
                        f"{pad.ref!r} (O4_BASIN_PAD_SEVER=1, retired path)",
                    )

        # ── §B, LEG 1 — PAVEMENT JOINS THE AUTHORITY-YIELD POPULATION ─
        # (spec lemd-rim-and-stations §B.1; owner RULINGS 2026-08-28
        # item 2, extending the 2026-08-26 trench-seniority ruling from
        # pads to pavement.)
        #
        # The 2026-08-26 implementation scoped its yield population to
        # ``ROLE_BUILDING`` (the pad loop above).  Inside the below-grade
        # region AND its rim band, PAVEMENT authority yields exactly as
        # building authority does: the floor pan and the R2 wall band are
        # born THROUGH it.  Leg 2's clip has already taken the pavement
        # back to the band's outer edge, so what remains here is the
        # pavement that ABUTS the band — and ``owned_near.buffer
        # (_TUNNEL_WALL_SETBACK_M)`` would eat the band from outside
        # exactly as the apron did before the clip.  Both legs are
        # needed; either alone leaves the band short.
        #
        # Geometry, welds and identity of the surviving pavement are
        # untouched (the Amendment-3 authority-yield mechanics, third
        # population).  SCOPED to open pits (``facility_cuts_pavement``,
        # R13's own predicate): a BORE runs under live pavement, and
        # yielding there would let a floor pan be born under a drivable
        # surface.
        authority_yield_pavement_ids: set = set()
        if config.TRENCH_PAVEMENT_YIELD and facility_cuts_pavement:
            _band_reach = None
            try:
                _band_reach = unary_union([
                    body.buffer(
                        _TUNNEL_RIM_BAND_WIDTH_M + _TUNNEL_WALL_SETBACK_M,
                        join_style=2, mitre_limit=2.0)
                    for body in body_parts])
            except Exception:                             # pragma: no cover
                _band_reach = None
            if _band_reach is not None and not _band_reach.is_empty:
                _yield_area = 0.0
                for shape in layout.shapes:
                    if shape.role not in open_pit_cut_roles:
                        continue
                    if shape.polygon is None or shape.polygon.is_empty:
                        continue
                    try:
                        if not shape.polygon.intersects(_band_reach):
                            continue
                    except Exception:                     # pragma: no cover
                        continue
                    authority_yield_pavement_ids.add(id(shape))
                    try:
                        _yield_area += float(shape.polygon.area)
                    except Exception:                     # pragma: no cover
                        pass
                if authority_yield_pavement_ids:
                    UI.vprint(
                        1,
                        f"   [{log_tag}] TRENCH SENIOR TO PAVEMENT AT ITS "
                        f"RIM: {len(authority_yield_pavement_ids)} pavement "
                        f"shape(s) ({_yield_area:.0f} m2) reaching the "
                        f"{_TUNNEL_RIM_BAND_WIDTH_M:.1f} m rim band of "
                        f"{resources} yield their flattening authority "
                        "there — the floor pan and the wall band are born "
                        "THROUGH them; their geometry, welds and identity "
                        "are untouched (spec lemd-rim-and-stations §B)",
                    )

        # ANCHOR SEAT (user 2026-07-18f, "object sitting below terrain"):
        # every shell of the facility drapes at terrain(anchor), and the
        # classifier's whole depth model assumed that value is the DATUM
        # it sampled — but the corridor cut (and the rim band) can move
        # the terrain AT the anchor, sinking every shell by the cut
        # depth.  Where OUR plates would touch the anchor and no earlier
        # shape owns it, a small seat plate pins terrain(anchor) = datum
        # (the pin the module docstring always promised).  The floor and
        # band are cut back a node-split margin around it.
        #
        # NOT FOR BASINS (owner ruling 2026-08-09, docs/RULINGS.md "the
        # basin experiment"; spec section 2.1 item 1).  A basin is an
        # OPEN pit whose interior faces are the thing the owner wants to
        # see: "we don't want any terrain poking up in the middle".  The
        # seat's 3x3 m plate at the datum stood ``body_depth + 0.5`` m
        # proud of the trench floor (4.31 m at the Drainage bowls,
        # 13.50 m at Dewatering_01), covering 7.4-9.0 m2 of the object's
        # own floor faces, and its keep-out punched a 17.64 m2 UNVALUED
        # interior ring through the floor pan.  Nothing is lost by
        # dropping it: the floor covers the anchor, so the object drapes
        # on the floor — which is precisely the experiment the owner
        # asked for ("let's try cutting the trench, but don't modify the
        # objects so I can see how it looks").
        anchor_seat_keep_out = None
        if not is_basin_facility:
            try:
                first_tunnel = member_records[0][0]
                seat_longitude, seat_latitude = (
                    first_tunnel.anchor_longitude_latitude)
                seat_x, seat_y = to_meters(seat_longitude, seat_latitude)
                seat_point = Point(seat_x, seat_y)
                plates_reach = unary_union([
                    body.buffer(
                        _TUNNEL_WALL_SETBACK_M + _TUNNEL_RIM_BAND_WIDTH_M,
                        join_style=2, mitre_limit=2.0)
                    for body in body_parts])
                if plates_reach.covers(seat_point):
                    owned_at_anchor = _owned_near(
                        (seat_x - 2.0, seat_y - 2.0,
                         seat_x + 2.0, seat_y + 2.0))
                    anchor_owned = (
                        owned_at_anchor is not None
                        and owned_at_anchor.covers(seat_point))
                    if not anchor_owned:
                        seat_polygon = Polygon([
                            (seat_x - 1.5, seat_y - 1.5),
                            (seat_x + 1.5, seat_y - 1.5),
                            (seat_x + 1.5, seat_y + 1.5),
                            (seat_x - 1.5, seat_y + 1.5)])
                        if born_flat_solver_plate(
                                layout, seat_polygon, ROLE_TUNNEL_TRENCH,
                                f"{plate_prefix}_anchor_seat", float(datum),
                                record_pins=False):
                            anchor_seat_keep_out = seat_polygon.buffer(
                                _TUNNEL_WALL_SETBACK_M,
                                join_style=2, mitre_limit=2.0)
                            UI.vprint(
                                1,
                                f"   [{log_tag}] {resources}: anchor seat "
                                f"pinned at datum {float(datum):.2f} m (the "
                                "facility cut reaches the placement anchor)",
                            )
            except Exception:
                anchor_seat_keep_out = None

        yielded_area = 0.0
        facility_floor_born = 0
        # EMITTED rim values (spec section 2.1 item 4).  The rim band is
        # born from PER-PART DEM samples, the law value being only the
        # nodata fallback — and until now the facility log line printed
        # the LAW value, so the number in the build log was not the
        # number in the patch (recon 2026-08-09).  Collect what actually
        # went into the plates and report the range beside the law.
        emitted_rim_values: list[float] = []
        # §C's own instrument: which RUNG each rim part took, and which
        # neighbour it adopted.  Ungated (the instrument is law) — the
        # 2026-08-09 recon's finding was precisely that the log printed
        # the law value while the patch carried something else.
        _rim_sources: dict = {}
        _rim_refs: dict = {}
        # ONE BODY OWNS THE RAMP.  The corridor joins exactly one body
        # part's floor pan — the part its mouth actually meets — because
        # adding it to each part in turn would emit the same ground once
        # per part.  Chosen by the largest overlap with the corridor's
        # own reach, never by order.
        # ── THE CARVE CLIPS THE CORRIDOR TO ITS OWN AUTHORITY ────────
        # (spec ``docs/specs/lemd-pad-authority-carve-spec.md`` §2.)
        #
        # The owner carved the ramp corridor out of the PAD's flattening
        # authority.  So the corridor may reach exactly as far as that
        # carved authority reaches — the facility itself, plus the pads
        # that actually yielded to it above — and no further.  Ground the
        # carve does not own is ground somebody else still owns, and a
        # plate laid there would be the retired arm's collision again,
        # only with a different neighbour.
        #
        # RUN HERE, after the yield loop and before the corridor is
        # consumed: the carved population is a decision that loop makes.
        # With the carve OFF the corridor is untouched and the retired
        # plate arm reproduces byte-identically.
        carve_authority = None
        if (ramp_corridor is not None
                and config.BASIN_PAD_AUTHORITY_CARVE):
            _carve_pad_polygons = [
                pad.polygon for pad in carve_pads
                if pad.polygon is not None and not pad.polygon.is_empty]
            if _carve_pad_polygons:
                try:
                    carve_authority = unary_union(
                        _carve_pad_polygons + list(body_parts))
                except Exception:                         # pragma: no cover
                    carve_authority = None
            if carve_authority is None or carve_authority.is_empty:
                UI.vprint(
                    1,
                    f"   [{log_tag}] PAD-AUTHORITY CARVE: no pad yielded "
                    f"its flattening authority to {resources}, so the "
                    f"{ramp_corridor.area:,.0f} m2 ramp corridor has NO "
                    "carved authority to lie in — no plate is laid and "
                    "the rim band is untouched (spec §2)",
                )
                ramp_corridor = None
            else:
                before_area = float(ramp_corridor.area)
                try:
                    clipped = ramp_corridor.intersection(carve_authority)
                except Exception:                         # pragma: no cover
                    clipped = None
                if clipped is None or clipped.is_empty:
                    UI.vprint(
                        1,
                        f"   [{log_tag}] PAD-AUTHORITY CARVE: the "
                        f"{before_area:,.0f} m2 ramp corridor of "
                        f"{resources} lies ENTIRELY outside the carved "
                        "authority — no plate is laid (spec §2)",
                    )
                    ramp_corridor = None
                else:
                    ramp_corridor = clipped
                    UI.vprint(
                        1,
                        f"   [{log_tag}] PAD-AUTHORITY CARVE: ramp "
                        f"corridor {before_area:,.0f} -> "
                        f"{float(clipped.area):,.0f} m2, clipped to the "
                        f"{len(carve_pads)} pad(s) whose flattening "
                        f"authority yielded to {resources} plus the "
                        "facility itself — the carve reaches exactly as "
                        "far as the authority it carves (spec §2)",
                    )
        ramp_corridor_body_index = None
        if ramp_corridor is not None:
            best_overlap = 0.0
            reach = ramp_corridor.buffer(
                _RAMP_CORRIDOR_BODY_BRIDGE_M, join_style=2, mitre_limit=2.0)
            for index, body in enumerate(body_parts):
                try:
                    overlap = float(reach.intersection(body).area)
                except Exception:
                    continue
                if overlap > best_overlap:
                    best_overlap, ramp_corridor_body_index = overlap, index
            if ramp_corridor_body_index is None:
                UI.vprint(
                    1,
                    f"   [{log_tag}] RAMP CORRIDOR NOT JOINED for "
                    f"{resources}: the {ramp_corridor.area:,.0f} m2 "
                    "corridor meets no body part of this facility — no "
                    "plate is laid and the rim band is untouched",
                )
                ramp_corridor = None
        for body_index, body in enumerate(body_parts):
            # R2 accounting.  A facility that CUT (R13) has no yield left
            # to report — its pavement is already gone.
            if pavement_union is not None and not facility_cuts_pavement:
                try:
                    kept = body.intersection(pavement_union)
                    if not kept.is_empty:
                        yielded_area += kept.area
                except Exception:
                    pass
            # FLUSH WALLS, INVERTED (user 2026-07-18f): the wall TOP must
            # be exactly flush with — or slightly inside — the shell's
            # outer wall plane, and the wall base may hide INSIDE the
            # shell but never protrude outward.  The previous outward
            # batter (floor to the body edge, rim band starting 0.6 m
            # outside) left a visible CREVICE between the shell top and
            # the terrain wall top.  Now the rim band's inner ring lies
            # exactly ON the body outline (flush top) and the floor is
            # inset one node-split gap INSIDE it — the batter lives
            # within the shell's wall thickness.  Mitre joins everywhere:
            # round buffer arcs read as curved ridges against the
            # straight object walls (the v19 collar lesson).
            #
            # The floor clearance is kept from EVERY earlier-born shape,
            # not pavement alone (Triangle4XP failure, tile +51-001
            # 2026-07-18): the EGKR micro-trench's body outline ran
            # collinear with its terminal's building-pad ring, and the
            # un-inset floor edge minted a mm-jittered constraint mess
            # (125 nodes in half a metre) that killed segment recovery.
            floor_owned_entries: list = []
            body_ramp_corridor = None
            try:
                floor_geometry = body.buffer(
                    -_TUNNEL_WALL_SETBACK_M, join_style=2, mitre_limit=2.0)
                envelope = body.buffer(
                    _TUNNEL_WALL_SETBACK_M + _TUNNEL_RIM_BAND_WIDTH_M
                    + 1.0)
                # ── THE RAMP JOINS THE FLOOR PAN (spec Amendment 1 §2) ──
                # Not a second plate: the SAME pan, the same role, the
                # same ref, the same floor elevation, one contiguous
                # surface.  The corridor is grown
                # ``_RAMP_CORRIDOR_BODY_BRIDGE_M`` back INTO the body so
                # it overlaps the pan's own inset edge — the pan is
                # ``body.buffer(-_TUNNEL_WALL_SETBACK_M)``, so a corridor
                # that merely reached the body OUTLINE would leave a
                # setback-wide strip of un-plated ground between the two
                # and the terrain would still stand in the mouth.
                carve_plate = None
                if (ramp_corridor is not None
                        and body_index == ramp_corridor_body_index):
                    body_ramp_corridor = ramp_corridor.union(
                        body.intersection(ramp_corridor.buffer(
                            _RAMP_CORRIDOR_BODY_BRIDGE_M,
                            join_style=2, mitre_limit=2.0)))
                    if config.BASIN_PAD_AUTHORITY_CARVE:
                        # ── THE CORRIDOR IS DIFFERENCED UNDER ITS OWN
                        # AUTHORITY (spec lemd-pad-authority-carve §2,
                        # clause 3) ────────────────────────────────────
                        # The pan's yield set below also carries the §B
                        # PAVEMENT population and the retired whole-pad
                        # seat's — yields that were ruled INSIDE THE
                        # FACILITY, and the corridor is outside it.
                        # Letting them apply out here is exactly how the
                        # retired plate arm ran into the apron (census
                        # within_shape 35 -> 231, 212 airside, worst
                        # 12.74 m).  So only the CARVED PADS yield in
                        # the corridor; every other earlier-born shape
                        # clips it under the same
                        # ``_TUNNEL_FLOOR_OWNED_CLEARANCE_M`` law the pan
                        # obeys.  The part INSIDE the body stays with the
                        # pan and keeps the pan's rule — the bridge
                        # exists to overlap the pan's own inset edge, and
                        # judging one strip of ground two ways is the
                        # thing this clause exists to stop.
                        carve_plate = body_ramp_corridor.difference(body)
                        floor_geometry = floor_geometry.union(
                            body_ramp_corridor.intersection(body))
                    else:
                        floor_geometry = floor_geometry.union(
                            body_ramp_corridor)
                    envelope = envelope.union(
                        body_ramp_corridor.buffer(
                            _TUNNEL_FLOOR_OWNED_CLEARANCE_M + 1.0))
                body_bounds = envelope.bounds
                # THE FLOOR-SEATED PADS ARE NOT OWNED GROUND (spec §1.2):
                # a pad seated AT this floor cannot also erase it.  The
                # entries are kept for the §2 named line below, which
                # reports what the floor WAS differenced against.
                _yielded_pad_ids = (floor_seated_pad_ids
                                    | authority_yield_pad_ids
                                    | authority_yield_pavement_ids)
                floor_owned_entries = _owned_entries_near(
                    body_bounds, _yielded_pad_ids)
                owned_near_floor = _owned_near(
                    body_bounds, _yielded_pad_ids)
                if owned_near_floor is not None \
                        and not owned_near_floor.is_empty:
                    floor_geometry = floor_geometry.difference(
                        owned_near_floor.intersection(envelope).buffer(
                            _TUNNEL_FLOOR_OWNED_CLEARANCE_M,
                            join_style=2, mitre_limit=2.0))
                if carve_plate is not None and not carve_plate.is_empty:
                    # The CARVED yield set: the pads whose flattening
                    # authority the owner carved, and nothing else.
                    _carve_yield_ids = {id(pad) for pad in carve_pads}
                    _carve_envelope = carve_plate.buffer(
                        _TUNNEL_FLOOR_OWNED_CLEARANCE_M + 1.0)
                    _owned_carve = _owned_near(
                        _carve_envelope.bounds, _carve_yield_ids)
                    _carve_before = float(carve_plate.area)
                    if _owned_carve is not None and not _owned_carve.is_empty:
                        try:
                            carve_plate = carve_plate.difference(
                                _owned_carve.intersection(
                                    _carve_envelope).buffer(
                                    _TUNNEL_FLOOR_OWNED_CLEARANCE_M,
                                    join_style=2, mitre_limit=2.0))
                        except Exception:                 # pragma: no cover
                            pass
                    if carve_plate.is_empty:
                        UI.vprint(
                            1,
                            f"   [{log_tag}] PAD-AUTHORITY CARVE: the "
                            f"{_carve_before:,.0f} m2 corridor plate of "
                            f"{resources} was differenced away entirely "
                            "by earlier-born shapes that did NOT yield "
                            "here — no plate is laid (spec §2 clause 3)",
                        )
                        body_ramp_corridor = None
                    else:
                        UI.vprint(
                            1,
                            f"   [{log_tag}] PAD-AUTHORITY CARVE: corridor "
                            f"plate {_carve_before:,.0f} -> "
                            f"{float(carve_plate.area):,.0f} m2 after "
                            "clearance from every earlier-born shape "
                            f"except the {len(carve_pads)} carved pad(s) "
                            "— the carved pad is born THROUGH, everything "
                            "else still owns its ground (spec §2 clause "
                            "3)",
                        )
                        floor_geometry = floor_geometry.union(carve_plate)
                        _carve_plates.append(carve_plate)
                band_geometry = body.buffer(
                    _TUNNEL_RIM_BAND_WIDTH_M,
                    join_style=2, mitre_limit=2.0).difference(body)
                band_bounds = band_geometry.bounds
                # THE WALL YIELDS TOO (owner Amendment 3).  The R2 wall
                # is this band — a node split OUTSIDE the body at the
                # surrounding grade, against the pan at the floor.  A pad
                # that owns the ground here takes the band with it and
                # the hole ramps out to the pad's distant ring instead of
                # walling at the facility boundary (LEMD arm 1, measured:
                # "no rim band emitted").  The pad's authority is clipped
                # to outside the facility, and the band is inside it.
                owned_near = _owned_near((
                    band_bounds[0] - 1.0, band_bounds[1] - 1.0,
                    band_bounds[2] + 1.0, band_bounds[3] + 1.0),
                    _yielded_pad_ids)
                if owned_near is not None and not owned_near.is_empty:
                    # Yield the band to every already-born shape WITH a
                    # setback margin: a band edge cut exactly on another
                    # shape's boundary would bucket-share its nodes and
                    # the datum-versus-solved first-writer race returns.
                    band_geometry = band_geometry.difference(
                        owned_near.buffer(
                            _TUNNEL_WALL_SETBACK_M,
                            join_style=2, mitre_limit=2.0))
                # ── THE RIM BAND STANDS DOWN IN THE CORRIDOR ──────────
                # (spec Amendment 1 §2, and the only reason the plate can
                # work.)  The band is a wall from the floor up to grade
                # laid all the way round the body — including straight
                # across the corridor's MOUTH, which is precisely the
                # ground the pit has to reach through.  Left standing it
                # would wall the pan off from its own ramp.  It stands
                # down INSIDE THE CORRIDOR ONLY; everywhere else the band
                # is byte-identical.
                if body_ramp_corridor is not None:
                    band_geometry = band_geometry.difference(
                        body_ramp_corridor)
                if anchor_seat_keep_out is not None:
                    floor_geometry = floor_geometry.difference(
                        anchor_seat_keep_out)
                    band_geometry = band_geometry.difference(
                        anchor_seat_keep_out)
            except Exception:
                continue
            floor_parts = (
                list(floor_geometry.geoms)
                if floor_geometry.geom_type == "MultiPolygon"
                else [floor_geometry]
            )
            body_floor_born = 0
            for floor_part in floor_parts:
                if (floor_part.geom_type != "Polygon" or floor_part.is_empty
                        or floor_part.area < 4.0):
                    continue
                if born_flat_solver_plate(
                        layout, floor_part, ROLE_TUNNEL_TRENCH,
                        f"{plate_prefix}_trench", floor_elevation,
                        record_pins=False):
                    body_floor_born += 1
            if not body_floor_born:
                # A body too thin/covered to seat any floor pan (the tiny
                # negative-AGL shells, or fully pavement-yielded bodies) is
                # left at grade rather than emitting a floorless rim ring —
                # the rim is meaningless without a floor to wall down to.
                #
                # ── THE SILENCE DIES (spec §2, the 2026-08-25e named-line
                # class).  UNGATED — instrument is law.  This branch used
                # to ``continue`` in complete silence, and that silence is
                # what let LEMD ship a classified, scoped, floor-agreed
                # basin that emitted NOTHING: the build log said the
                # facility's floor was 584.5 m and nothing said no plate
                # was ever born, let alone what erased it.  Name the
                # facility, its floor, and EVERY shape the floor was
                # differenced against, with role and area — the shape at
                # the top of that list IS the answer.
                _diff_rows = []
                for _entry in floor_owned_entries:
                    _shape = _entry[2]
                    try:
                        _hit = float(_entry[1].intersection(body).area)
                    except Exception:
                        _hit = 0.0
                    if _hit <= 0.0:
                        continue
                    _diff_rows.append(
                        (_hit, _shape.role, _shape.ref or "?",
                         float(_entry[1].area)))
                _diff_rows.sort(reverse=True)
                _body_area = float(getattr(body, "area", 0.0) or 0.0)
                UI.vprint(
                    1,
                    f"   [{log_tag}] NO FLOOR PLATE BORN for {resources}: "
                    f"the {_body_area:.0f} m2 body at floor "
                    f"{floor_elevation:.2f} m seated ZERO plates — the "
                    f"floor was differenced against "
                    f"{len(_diff_rows)} earlier-born shape(s)"
                    + (":" if _diff_rows else " (none: the body's own "
                       "inset left nothing above the 4 m2 plate floor)"),
                )
                for (_hit, _role, _ref, _area) in _diff_rows[:10]:
                    _pct = (f" ({100.0 * _hit / _body_area:.0f} %)"
                            if _body_area > 0.0 else "")
                    UI.vprint(
                        1,
                        f"   [{log_tag}]     {_role} {_ref!r}: "
                        f"{_area:.0f} m2 shape covering {_hit:.0f} m2"
                        f"{_pct} of the body",
                    )
                if len(_diff_rows) > 10:
                    UI.vprint(
                        1,
                        f"   [{log_tag}]     ... and "
                        f"{len(_diff_rows) - 10} more.",
                    )
                continue
            floor_plate_count += body_floor_born
            facility_floor_born += body_floor_born
            for band_part in _chop_long_band_parts(
                    _split_annulus_to_simple_parts(band_geometry)):
                if band_part.area < 1.0:
                    continue
                # TERRAIN-TRUE rim (user screenshots 2026-07-18c, EGLL
                # west end): the anchor's datum can sit metres off the
                # ground AT the band — the Tunnel/6+7 placements anchor
                # ~100 m from their geometry and the datum-flat rim
                # stood ~5 m proud of the surrounding ground as a
                # raised berm box.  The band's job is to pin the wall
                # top AT the surrounding grade, so each part samples
                # the DEM at its own centroid; the drape-law datum
                # stays the fallback on nodata.  The FLOOR keeps the
                # anchor datum — that is where the draped object's
                # solids actually land (terrain(anchor) + offsets).
                #
                # ── §C SUPERSEDES THE PER-PART DEM SAMPLE ────────────
                # (spec lemd-rim-and-stations §C.1; owner RULINGS
                # 2026-08-28 item 3 + DEM-LAST.)  The paragraph above is
                # the reason the rim must not take the ANCHOR DATUM; it
                # is not a reason to take the DEM.  Both questions have
                # one answer — the surface the band abuts — and with the
                # flag ON the rungs are: nearest ANCHORED built
                # neighbour → ``R_est`` (the law median, ``rim_
                # elevation``) → the raw DEM sample, last.
                part_centroid = band_part.centroid
                part_elevation = rim_elevation
                _rim_source = "r_est"
                _rim_ref = None
                _neighbour = None
                # SCOPE: basin facilities.  The basin-rim-flush spec's
                # §2.1 froze the TUNNEL arm verbatim — "no OTHH fixture
                # exercises them and the EGLL class must not move" — and
                # §0's whole measured population is basin rim bands, so
                # the tunnel rim keeps its per-part DEM sample and stays
                # byte-identical.  Widening it is a separate ruling.
                _rim_law_on = bool(config.RIM_SOLVED_NEIGHBOUR
                                   and is_basin_facility)
                if _rim_law_on:
                    _neighbour = _rim_neighbour_value(
                        band_part,
                        _rim_neighbours_near(band_part.bounds),
                        config.TUNNEL_RIM_NEIGHBOUR_WINDOW_M)
                if _neighbour is not None:
                    part_elevation = float(_neighbour[0])
                    _rim_source = "neighbour"
                    _rim_ref = _neighbour[1]
                elif not _rim_law_on or rim_elevation != rim_elevation:
                    try:
                        centroid_latitude, centroid_longitude = (
                            _meters_to_lat_lon(
                                part_centroid.x, part_centroid.y))
                        sample = _sample_dem(
                            dem, tile_lat, tile_lon,
                            centroid_latitude, centroid_longitude)
                        if sample is not None and sample == sample:
                            part_elevation = float(sample)
                            _rim_source = "dem"
                    except Exception:
                        part_elevation = rim_elevation
                        _rim_source = "r_est"
                _rim_sources[_rim_source] = _rim_sources.get(
                    _rim_source, 0) + 1
                if _rim_ref is not None:
                    _rim_refs[_rim_ref] = _rim_refs.get(_rim_ref, 0) + 1
                if born_flat_solver_plate(
                        layout, band_part, ROLE_TUNNEL_TRENCH,
                        f"{plate_prefix}_rim", part_elevation,
                        record_pins=False):
                    rim_plate_count += 1
                    emitted_rim_values.append(float(part_elevation))

        if _carve_plates and carve_pads and facility_floor_born:
            # ── THE CARVE'S DECLARATION (spec lemd-pad-authority-carve
            # §2: "the pad edge along the corridor is a declared
            # wall/terrace") ──────────────────────────────────────────
            # RECORDED here, PUBLISHED post-solve
            # (:func:`_republish_basin_declarations`), because the step
            # is plate-to-PAD and the pad does not carry its solved
            # value yet.  The pad shapes travel with the plates: the
            # declaration is about the pair, and re-deriving "which pad
            # is this plate's" later would be a second answer to a
            # question already decided.
            _prev = list(getattr(layout, BASIN_CARVE_PLATES_ATTRIBUTE,
                                 None) or [])
            _prev.append({
                "plates": list(_carve_plates),
                "pads": list(carve_pads),
                "floor_m": float(floor_elevation),
            })
            setattr(layout, BASIN_CARVE_PLATES_ATTRIBUTE, _prev)
        if floor_seated_pad_ids and not facility_floor_born:
            # NO FLOOR, NO SEAT (spec §1.1's premise).  A facility that
            # seated no plate anywhere has no emitted floor for a pad to
            # sit on, and a pad declared 8 m down with nothing cut around
            # it is a pit with no basin — strictly worse than the buried
            # pad it was meant to expose.  Withdrawn, and SAID SO: the
            # §2 named line above has already reported why no plate was
            # born.
            for _pad in layout.shapes:
                if id(_pad) in floor_seated_pad_ids:
                    _pad.basin_floor_seat_m = None
            UI.vprint(
                1,
                f"   [{log_tag}] BASIN PAD SEAT WITHDRAWN for "
                f"{resources}: {len(floor_seated_pad_ids)} pad(s) were "
                "seated at the facility floor but no floor plate was "
                "born — nothing to sit on",
            )
            floor_seated_pad_ids = set()
        if cut_shape_count and not facility_floor_born:
            # RULING R13's GUARD: the cut bought nothing, so PUT IT BACK.
            # Pavement removed with no trench under it is a hole in the
            # drivable surface — strictly worse than the buried pit it was
            # meant to expose.  Nothing born since the snapshot survives
            # either, which is right: the only plates that could exist are
            # this facility's own anchor seat and rim bands, and a rim is
            # meaningless without a floor to wall down to.
            layout.shapes = pre_cut_shapes
            _reindex_owned_ground()
            _rebuild_pavement_unions()
            # Nothing born since the snapshot survives, the rim bands
            # included — so nothing was EMITTED to report.
            emitted_rim_values = []
            UI.vprint(
                1,
                f"   [{log_tag}] R13 open-pit cut RESTORED for "
                f"{resources}: {cut_pavement_area:.0f} m2 of pavement was "
                "removed but no trench floor could be seated under it",
            )
        elif cut_shape_count:
            UI.vprint(
                1,
                f"   [{log_tag}] R13 open-pit cut: {cut_pavement_area:.0f} "
                f"m2 of pavement (airside + landside) removed from "
                f"{cut_shape_count} shape(s) over the open pit of "
                f"{resources}",
            )
        if yielded_area > 1.0:
            UI.vprint(
                1,
                f"   [{log_tag}] {resources}: {yielded_area:.0f} m2 of "
                "body under airside pavement kept at pavement grade",
            )
        facility_depth = max(
            float(record[0].body_depth_m) for record in member_records)
        # THE EMITTED rim band range beside the law value (spec section
        # 2.1 item 4): the two disagree by construction — the band takes
        # per-part DEM samples and the law value is its nodata fallback —
        # and printing only the law is what hid a 0.71-2.96 m rim behind
        # a single 0.80 m number at OTHH Dewatering_01.
        if emitted_rim_values:
            emitted_rim_text = (
                f"emitted rim {min(emitted_rim_values):.2f}"
                f"-{max(emitted_rim_values):.2f} m over "
                f"{len(emitted_rim_values)} band part(s)")
        else:
            emitted_rim_text = "no rim band emitted"
        if is_basin_facility:
            fallback_text = (
                " (DEM fallback to anchor datum)"
                if basin_rim_estimate_is_fallback else "")
            reference_text = (
                f"R_est {basin_rim_estimate:.2f}{fallback_text}, "
                f"anchor datum {float(datum):.2f}")
        else:
            reference_text = f"datum {float(datum):.2f}"
        UI.vprint(
            1,
            f"   [{log_tag}] {resources}: trench floor {floor_elevation:.2f} "
            f"m, rim law {rim_elevation:.2f} m, {emitted_rim_text} "
            f"({reference_text}, body "
            f"depth {facility_depth:.2f} m, "
            f"{len(member_records)} shell(s))",
        )
        if _rim_sources:
            _src_text = ", ".join(
                f"{k}×{v}" for k, v in sorted(_rim_sources.items()))
            _ref_text = ("" if not _rim_refs else "; adopted "
                         + ", ".join(f"{k!r}×{v}" for k, v in
                                     sorted(_rim_refs.items())[:6]))
            UI.vprint(
                1,
                f"   [{log_tag}] {resources}: rim VALUE SOURCE {_src_text}"
                f"{_ref_text} — nearest anchored built neighbour, then "
                f"R_est {rim_elevation:.2f} m, then raw DEM last "
                f"(spec lemd-rim-and-stations §C"
                + ("" if (config.RIM_SOLVED_NEIGHBOUR and is_basin_facility)
                   else ("; TUNNEL arm, per-part DEM kept verbatim"
                         if is_basin_facility is False
                         else "; O4_RIM_SOLVED_NEIGHBOUR=0, per-part DEM"))
                + ")",
            )
        if is_basin_facility:
            # THE PER-FACILITY RECORD the integration report reads (spec
            # section 2.1e item E2).  It rides the patch's own
            # ``.axes.json`` sidecar — the established "one small JSON
            # beside the patch" convention (``layout._write_axes_sidecar``)
            # — rather than a new file: the patch dir's contents are
            # pinned by ``tests/test_auto_patch_freshness.py`` to the
            # patch and that sidecar, and a second artifact there is a
            # freshness-test failure and an undeclared coupling.
            #
            # PREDICTED DRAPE ELEVATION IS THE FLOOR.  A draped OBJECT
            # seats on the terrain at its anchor; with the anchor seat
            # gone the terrain there IS the trench floor pan.  That is
            # the prediction the owner's in-sim look adjudicates (the
            # measurement on record says the placement origin is the
            # RIM, so the rims are predicted to sit ``floor - R_est``
            # below grade).
            _record_basin_facility(layout, {
                "resources": list(resources),
                "anchor_longitude_latitude": [
                    float(member_records[0][0]
                          .anchor_longitude_latitude[0]),
                    float(member_records[0][0]
                          .anchor_longitude_latitude[1]),
                ],
                "anchor_datum_m": float(datum),
                "rim_estimate_m": float(basin_rim_estimate),
                "rim_estimate_is_dem_fallback": bool(
                    basin_rim_estimate_is_fallback),
                "floor_m": float(floor_elevation),
                "rim_law_m": float(rim_elevation),
                "emitted_rim_min_m": (
                    float(min(emitted_rim_values))
                    if emitted_rim_values else None),
                "emitted_rim_max_m": (
                    float(max(emitted_rim_values))
                    if emitted_rim_values else None),
                "emitted_rim_part_count": len(emitted_rim_values),
                # ── THE PER-PART WALL ALLOWANCE (trench-law spec
                # Amendment 1, 2026-08-25) ───────────────────────────
                # The band is TERRAIN-TRUE: each part takes its own DEM
                # sample, so on sloping ground one facility declares ONE
                # floor and MANY rims.  A census that prices every wall
                # contact against the flat ``rim_law_m`` therefore
                # reports the terrain's own relief as excess — measured
                # at LEMD_a4: emitted rim 592.64-595.24 against a
                # 593.03 law value, +930 lawful wall rows, worst 9.23 m.
                # OTHH never showed it because its DEM is flat there
                # (emitted rim 3.96-3.96 == the law value exactly).
                #
                # So the parts are PUBLISHED, sorted, and the census
                # joins a wall row to its own part BY VALUE — the
                # declared-number join, never proximity
                # (``check_grade._basin_declared_drop``).  min/max/count
                # stay: they are the human-readable summary the log line
                # prints, and an older artifact that carries only those
                # falls back to the flat drop, exactly as before.
                "emitted_rim_parts_m": sorted(
                    float(value) for value in emitted_rim_values),
                "predicted_drape_elevation_m": float(floor_elevation),
                "predicted_rim_elevation_m": float(rim_elevation),
                "solid_minimum_y_m": min(
                    float(record[4]) for record in member_records),
                "body_depth_m": float(facility_depth),
                "shell_count": len(member_records),
                "floor_plates": int(facility_floor_born),
                "anchor_seat_emitted": False,
            })
    return floor_plate_count, rim_plate_count
