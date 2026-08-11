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
from dataclasses import dataclass, field
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
_CLASSIFICATION_CACHE_VERSION = 17

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
    * every ``.obj`` under the pack root (relative path, size, mtime) —
      needed BESIDE the DSF check because object-geometry edits (our own
      Phase 2 y-bake rewrites included) change no DSF byte;
      ``.anchor_bak`` backups are not ``.obj`` files and stay out of it;
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
        object_entries = []
        for directory, _subdirectories, file_names in os.walk(pack_root):
            for file_name in file_names:
                if not file_name.lower().endswith(".obj"):
                    continue
                full_path = os.path.join(directory, file_name)
                try:
                    file_stat = os.stat(full_path)
                except OSError:
                    continue
                object_entries.append(
                    f"{os.path.relpath(full_path, pack_root)}"
                    f":{file_stat.st_size}:{file_stat.st_mtime}"
                )
        for entry in sorted(object_entries):
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
_EXCLUSION_CACHE_VERSION = 7


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
    return structures


#: Decision kind recorded in the rebake provenance for a basin facility
#: seated by the section-2.2 rim-flush law.  ONE spelling, read by the
#: post-mesh pass, the provenance writer and the tests.
BASIN_RIM_FLUSH_DECISION_KIND = "basin_rim_flush"


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
        )


def basin_rim_flush_facilities(classification) -> list:
    """The section-2.2 facility records for one classification.

    Grouping is the EMITTER's grouping, character for character: the
    same ``basin_trench_structures`` records, the same
    ``(terrain_feature, anchor×1e5, anchor×1e5)`` key
    :func:`build_tunnel_layout_shapes` groups facilities by, and the
    same members dropped (no below-grade body depth, no footprint to
    cut).  A facility the emitter cut one trench for is one facility
    here; anything else would seat an object into a hole nobody dug.

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
        resources: set[str] = set()
        body_parts: list = []
        deck_reference_values: list[float] = []
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
            resources.update(record.object_resources)
            body_parts.extend(parts)
            # ``deck_reference_y`` — the emitter's floor key, i.e. the
            # deeper of the modelled body depth and the structure's TRUE
            # deepest solid.
            deck_reference_y = -float(record.body_depth_m)
            solid_minimum_y = getattr(record, "solid_minimum_y_m", None)
            if solid_minimum_y is not None:
                deck_reference_y = min(
                    deck_reference_y, float(solid_minimum_y))
            deck_reference_values.append(deck_reference_y)
            if anchor_longitude_latitude is None:
                anchor_longitude_latitude = (
                    float(record.anchor_longitude_latitude[0]),
                    float(record.anchor_longitude_latitude[1]),
                )
        if not resources or not body_parts:
            continue
        try:
            body = unary_union(body_parts)
        except Exception:
            body = None
        if body is None or body.is_empty:
            continue
        parts = list(getattr(body, "geoms", [body]))
        rings = tuple(
            tuple(
                (float(longitude), float(latitude))
                for longitude, latitude in part.exterior.coords
            )
            for part in parts
            if part.geom_type == "Polygon" and not part.is_empty
        )
        if not rings:
            continue
        anchor_point = Point(*anchor_longitude_latitude)
        out.append(
            BasinRimFlushFacility(
                object_resources=tuple(sorted(resources)),
                anchor_longitude_latitude=anchor_longitude_latitude,
                body_rings_longitude_latitude=rings,
                solid_minimum_y_m=min(deck_reference_values),
                anchor_inside_body=bool(body.covers(anchor_point)),
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
    from .layout import ROLE_TUNNEL_TRENCH

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
    owned_entries = [
        (shape.polygon.bounds, shape.polygon) for shape in layout.shapes
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
            (shape.polygon.bounds, shape.polygon) for shape in layout.shapes
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

    def _owned_near(bounds):
        minimum_x, minimum_y, maximum_x, maximum_y = bounds
        candidates = [
            polygon for (bounds_x0, bounds_y0, bounds_x1, bounds_y1), polygon
            in owned_entries
            if bounds_x0 <= maximum_x and bounds_x1 >= minimum_x
            and bounds_y0 <= maximum_y and bounds_y1 >= minimum_y
        ]
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
            deck_reference_y = -float(tunnel.body_depth_m)
            solid_minimum_y = getattr(tunnel, "solid_minimum_y_m", None)
            if solid_minimum_y is not None:
                deck_reference_y = min(deck_reference_y,
                                       float(solid_minimum_y))
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
                 deck_reference_y, member_parts))
        if not member_records:
            continue
        resources = sorted({
            resource for tunnel, *_rest in member_records
            for resource in tunnel.object_resources})
        datum = min(record[1] for record in member_records)
        body_parts = [
            part for *_head, parts in member_records for part in parts]
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
            floor_elevation = min(
                basin_trench_floor_elevation_m(
                    basin_rim_estimate, record[4])
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
        if facility_cuts_pavement:
            if open_pit_union is None:
                _reindex_open_pit_union()
        if facility_cuts_pavement and open_pit_union is not None:
            for body in body_parts:
                try:
                    covered_area = body.intersection(open_pit_union).area
                except Exception:
                    covered_area = 0.0
                if covered_area <= 0.0:
                    continue
                if pre_cut_shapes is None:
                    pre_cut_shapes = list(layout.shapes)
                body_cut_shapes = cut_pavement_over_footprint(
                    layout, body, cut_roles=open_pit_cut_roles)
                if body_cut_shapes:
                    _reindex_owned_ground()
                    _drop_cut_from_unions(body)
                    cut_shape_count += body_cut_shapes
                    cut_pavement_area += covered_area
        # (the cut is REPORTED at the end of the facility, where its
        # restore guard has already run — a cut that was put back must
        # never be logged as one that happened.)

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
        for body in body_parts:
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
            try:
                floor_geometry = body.buffer(
                    -_TUNNEL_WALL_SETBACK_M, join_style=2, mitre_limit=2.0)
                envelope = body.buffer(
                    _TUNNEL_WALL_SETBACK_M + _TUNNEL_RIM_BAND_WIDTH_M
                    + 1.0)
                body_bounds = envelope.bounds
                owned_near_floor = _owned_near(body_bounds)
                if owned_near_floor is not None \
                        and not owned_near_floor.is_empty:
                    floor_geometry = floor_geometry.difference(
                        owned_near_floor.intersection(envelope).buffer(
                            _TUNNEL_FLOOR_OWNED_CLEARANCE_M,
                            join_style=2, mitre_limit=2.0))
                band_geometry = body.buffer(
                    _TUNNEL_RIM_BAND_WIDTH_M,
                    join_style=2, mitre_limit=2.0).difference(body)
                band_bounds = band_geometry.bounds
                owned_near = _owned_near((
                    band_bounds[0] - 1.0, band_bounds[1] - 1.0,
                    band_bounds[2] + 1.0, band_bounds[3] + 1.0))
                if owned_near is not None and not owned_near.is_empty:
                    # Yield the band to every already-born shape WITH a
                    # setback margin: a band edge cut exactly on another
                    # shape's boundary would bucket-share its nodes and
                    # the datum-versus-solved first-writer race returns.
                    band_geometry = band_geometry.difference(
                        owned_near.buffer(
                            _TUNNEL_WALL_SETBACK_M,
                            join_style=2, mitre_limit=2.0))
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
                part_centroid = band_part.centroid
                part_elevation = rim_elevation
                try:
                    centroid_latitude, centroid_longitude = (
                        _meters_to_lat_lon(
                            part_centroid.x, part_centroid.y))
                    sample = _sample_dem(
                        dem, tile_lat, tile_lon,
                        centroid_latitude, centroid_longitude)
                    if sample is not None and sample == sample:
                        part_elevation = float(sample)
                except Exception:
                    part_elevation = rim_elevation
                if born_flat_solver_plate(
                        layout, band_part, ROLE_TUNNEL_TRENCH,
                        f"{plate_prefix}_rim", part_elevation,
                        record_pins=False):
                    rim_plate_count += 1
                    emitted_rim_values.append(float(part_elevation))

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
