"""Object pooling, structure partitioning and per-structure offsets.

Contract frozen by workstream W1 (``docs/dsf_object_integration_spec.md``
section 3.3, as amended by A1/A3/A10); implemented in workstream W4.
This module is the heart of the correction and the single most likely
place for a subtle bug — read spec section 2.4 and
``docs/obj8_structure_partition.md`` before writing a line.

The rule that must never be collapsed (spec section 2.4, invariant I-3):

    A structure's ground elevation is a property of the STRUCTURE.
    The y offset applied to a vertex is a property of the
    (structure, object) PAIR, because X-Plane puts each object's
    ``y = 0`` plane at the terrain under THAT object's own anchor::

        delta(S, O) = ground_under(centroid(S)) - ground_under(anchor(O))

When two objects contribute geometry to one structure — the KCLT case,
where walls and roof of one building live in different texture-page
bakes — they receive DIFFERENT deltas, and the walls still meet the roof,
because each delta is measured from its own object's ``y = 0`` plane.
A single per-structure delta is correct only when all contributing
objects share an anchor, and silently tears geometry when they do not.

The pool frame (invariant I-2, partition document section 3 step 1).
All cross-object geometry work happens in ONE local east-north-up frame
per pool, in AUTHORED space:

* Origin: the arithmetic mean of the pool's placement latitudes and
  longitudes.  Axes UNROTATED — the frame is exactly a synthetic
  heading-0 placement at that origin, so
  ``obj8_reader.lonlat_to_local_offset(origin_latitude,
  origin_longitude, 0.0, ...)`` and its inverse ARE the frame maps
  (frame ``x`` = metres east of the origin, frame ``z`` = metres south,
  matching the OBJ8 local convention at heading 0).  A fixed unrotated
  frame is required because workstream W2's audit found axis-aligned
  bounding-box results are not rotation invariant: every pool member
  must be measured against the same axes.
* Horizontal position: each vertex is projected to world
  latitude/longitude through ITS OWN placement
  (``local_offset_to_lonlat``), then into the pool frame.  Two nearby
  world points keep their true separation to well under the weld and
  contact tolerances, whatever their anchors.
* Vertical position: the AUTHORED ``v.y`` — never
  ``terrain(anchor) + v.y``.  The author assembled the parts against a
  common assumed-flat plane; authored space is the frame in which they
  fit.
* Mapping back: a pool-frame centroid ``(x, z)`` returns to
  latitude/longitude through ``local_offset_to_lonlat(origin_latitude,
  origin_longitude, 0.0, x, z)`` — the exact inverse of the frame map.

Everything here is pure: geometry and a sampler in, numbers out, no file
input/output (that is ``object_rebake``'s job).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field, replace

from . import obj8_partition, obj8_reader
from .mesh_sampler import MeshElevationSampler
from .obj8_reader import ObjectGeometry, ObjectPlacement

Triangle = tuple[int, int, int]

# Amendment A3 do-not-bake tie-break: the single-offset correction is
# "worse than uncorrected" only when its mean ground-part residual
# exceeds the uncorrected mean by more than this.  Without the
# tolerance, a structure sitting exactly at its anchor's elevation
# (corrected residual == uncorrected residual up to float noise) could
# flip to skipped on a nanometre.
RESIDUAL_COMPARISON_TOLERANCE_METRES = 1e-6

# Amendment A19: the A3 do-not-bake guard applies only to structures
# smaller than this diameter.  A mega-structure (HECA's kilometre-wide
# chained terminal web) always bakes with its best single offset and
# flags ``needs_pad`` — judging it by mean residual and silently
# skipping left 49 resources floating at anchor minus local ground.
A3_GUARD_MAXIMUM_DIAMETER_METRES = 100.0

# Stable phrase carried in the ``skip_reason`` of a structure left at its
# authored elevations because its ground-contact terrain span exceeds
# ``DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M``.  ``post_mesh`` matches on it to
# count the per-airport "left at authored elevations" summary, so the
# reason text and this phrase must stay in lockstep.
GROUND_SPAN_SKIP_REASON_PHRASE = "exceeds the rigid-seat limit"

# Stable phrase opening the ``skip_reason`` of a structure left at its
# authored elevations because the SUPPORTER whose ground it inherits was
# itself skipped (``DSF_OBJECT_SUPPORTER_FATE``, config.py — the HECA
# 2026-07-26 tear diagnosis).  ``post_mesh`` matches on it for the
# per-airport summary count, so the phrase and the reason text built in
# :func:`structure_deltas` must stay in lockstep.
SUPPORTER_FATE_SKIP_REASON_PHRASE = "supporter skipped"

# Stable phrase carried in the ``skip_reason`` of a seating unit left at
# its authored elevations because its required correction never reached
# ``DSF_OBJECT_BAKE_MIN_DELTA_M`` (docs/specs/object-reseat-threshold-
# spec.md section 2.1).  This is NOT a refusal: the unit is fine where
# the author put it, the pack is deliberately not modified, and the
# terrain adapts to it instead (section 2.2's pad requests).
# ``post_mesh`` matches on this phrase for the per-airport summary count,
# so the phrase and the reason text built below must stay in lockstep.
BELOW_BAKE_THRESHOLD_SKIP_REASON_PHRASE = "below_bake_threshold"

# The same phrase TAGGED with the unit it decided about.  A structure all
# of whose clusters fall below the threshold echoes its first cluster's
# reason (that is how supporter fate reaches its inheritors), so the
# per-airport summary would count one unit twice if it matched the bare
# phrase on both.  The plain-structure path carries this tag and the
# cluster path does not, so the two populations add up exactly once.
BELOW_BAKE_THRESHOLD_STRUCTURE_TAG = "below_bake_threshold[structure]"


@dataclass(frozen=True)
class ObjectPool:
    """Objects whose geometry must be partitioned together because their
    placed world footprints interact — a structure may span several of
    them.

    Pooling is by world axis-aligned-bounding-box overlap (transitively,
    with an epsilon margin), NOT by anchor proximity: contact is a
    world-geometry property, and the 41 KCLT terminal-layer objects share
    buildings across anchors 10 metres apart (invariant I-1, amendment
    A10).  Exactly one placement per resource — multi-placement
    definitions are Phase-2-refused upstream (invariant I-4).
    """

    placements: list[ObjectPlacement]
    resolved_paths: dict[str, str]  # resource_path -> file on disk


@dataclass(frozen=True)
class Structure:
    """One rigid unit: a connected component of the contact graph over the
    pooled parts, possibly spanning several objects."""

    triangles_by_resource: dict[str, list[Triangle]]
    surface_area_square_metres: float
    centroid_latitude: float
    centroid_longitude: float
    minimum_base_y_by_resource: dict[str, float]
    is_ground_touching: bool
    # None until Phase 2 has a mesh to sample (footprints never need it).
    ground_span_metres: float | None
    # Amendment A3: large ground span is bake-and-flag, never refuse/split.
    needs_pad: bool
    skip_reason: str | None
    # Set only for structures with no ground-touching part that inherit a
    # supporter's offset (invariant I-8).
    inherited_from_structure_index: int | None
    # The epsilon-contact edges AMONG this structure's parts, as pairs of
    # PART KEYS (a part's key is the lowest pool-frame shared vertex index
    # it touches — see ``object_clusters``).  ``partition_structures``
    # computes the contact graph once and used to throw it away; per-cluster
    # seating (docs/specs/per-cluster-object-seating-spec.md section 3.1)
    # needs those edges again in ``structure_deltas``, and recomputing the
    # narrow phase there would be the one way that phase could breach the
    # build-time budget.  EMPTY means "not available" (a hand-built
    # structure, a pre-clustering partition cache, or a group whose edges
    # could not be verified spanning after the connector split): seating
    # then falls back to the per-STRUCTURE rigid seat, never to a shredded
    # cluster set.
    contact_edges: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class FootCluster:
    """One ground-contact FOOT of a structure: a cluster of solid
    vertices at the structure's own lowest band (project memory
    kbna-gantry-pond-multi-foot-objects).

    Detected in the pool frame by :func:`detect_foot_clusters`;
    ``structure_deltas`` fills the world/mesh fields
    (``latitude``/``longitude``/``ground_metres``/``kept_for_fit``/
    ``residual_metres``) via ``dataclasses.replace`` when the structure
    is foot-anchored."""

    centroid_x: float  # pool frame metres east
    centroid_z: float  # pool frame metres south
    base_y: float  # authored y of the cluster's lowest solid vertex
    base_resource: str  # resource owning that lowest vertex
    contact_points: tuple[tuple[float, float], ...]  # frame (x, z)
    latitude: float | None = None
    longitude: float | None = None
    ground_metres: float | None = None
    # False when the foot's seat target fell more than
    # DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M below the topmost target and
    # was excluded from the rigid fit.
    kept_for_fit: bool = True
    # ``rendered base − ground`` after the fitted rigid offset
    # (positive floats, negative sinks); None until fitted.
    residual_metres: float | None = None


@dataclass(frozen=True)
class FootPadRequest:
    """A per-foot terrain-pad request: after the best rigid offset this
    foot still misses the mesh by more than
    ``DSF_OBJECT_FOOT_PAD_RESIDUAL_M`` — a rigid body cannot seat it,
    only terrain shaped to ``target_ground_metres`` under the foot can.
    Recorded on the decision and written to the post-mesh sidecar; the
    ring itself is built downstream by
    ``object_footprints.foot_pad_rings`` from
    ``contact_parts_lonlat``.
    """

    structure_index: int
    resource_path: str
    latitude: float
    longitude: float
    base_y: float
    residual_metres: float
    target_ground_metres: float
    contact_points_lonlat: tuple[tuple[float, float], ...]  # (lon, lat)
    # The same points GROUPED BY CONTACT PART — the ring builder's real
    # input under the footprint-hugging law (object-reseat-threshold-spec
    # §2.5).  A foot is ONE contact part, so this is a one-element tuple
    # and the foot ring is unchanged; empty means "not grouped" and the
    # builder falls back to the flat point list as a single part.
    contact_parts_lonlat: tuple[tuple[tuple[float, float], ...], ...] = ()


@dataclass(frozen=True)
class ClusterPadRequest:
    """A per-CLUSTER terrain-pad request — the sibling of
    :class:`FootPadRequest` (per-cluster seating spec section 5.3).

    Raised for every maximal connected group of a baked cluster's ground
    parts whose post-seat residual ``|cluster_ground + base_y −
    ground_under(part)|`` exceeds ``DSF_OBJECT_FOOT_PAD_RESIDUAL_M``:
    the rigid seat took the whole cluster as far as one offset can, and
    what is left is terrain's share of the work.  Grouping CONNECTED
    residual parts (rather than one request per part) keeps a sloping
    terminal end as a handful of coherent pads instead of hundreds of
    confetti rings.

    ``over_relief_cap`` marks a group whose required relief exceeds
    ``DSF_OBJECT_PAD_MAX_RELIEF_M``: the pad is inadmissible as-is (spec
    section 5.1 clause 1) and the request is kept as a FINDING carrying
    the measured numbers — the cluster still bakes, the residual is not
    hidden.
    """

    structure_index: int
    cluster_id: int
    resource_path: str
    latitude: float
    longitude: float
    base_y: float
    residual_metres: float
    target_ground_metres: float
    contact_points_lonlat: tuple[tuple[float, float], ...]  # (lon, lat)
    part_count: int = 1
    over_relief_cap: bool = False
    # THE RING LAW's input (object-reseat-threshold-spec §2.5 v2b): the
    # group's GROUND-CONTACT GEOMETRY, one tuple per contact-band
    # TRIANGLE of each part.  Read instead of the flattened list, which
    # is the plan-box audit trail: hulling the whole group bridged water
    # and parking lots between spread-out parts (v2), and hulling each
    # part's plan box left the mega-part rectangles untouched (v2b).
    # Empty means "not grouped" (a hand-built request); the builder then
    # treats the flat list as one part, i.e. the retired hull.
    contact_parts_lonlat: tuple[tuple[tuple[float, float], ...], ...] = ()


@dataclass(frozen=True)
class ClusterSeam:
    """One reported seam of the per-cluster tear audit (spec section
    4.5), in two classes.

    ``kind="cut"`` — a ground-to-ground contact edge the cut law severed:
    ``ground_step_metres`` is the measured ``g(e)`` that justified it and
    ``seam_metres`` the rendered displacement between the two cluster
    seats.  ``kind="bridge"`` — an elevated component contacting several
    clusters (spec section 4.2a): it joined its majority-contact cluster
    and ``seam_metres`` is the residual toward the cluster it left.
    Reported, counted, never averaged across.
    """

    kind: str  # "cut" | "bridge"
    structure_index: int
    cluster_id: int
    other_cluster_id: int
    seam_metres: float
    ground_step_metres: float | None = None
    part_count: int = 0


@dataclass(frozen=True)
class RebakeDecision:
    """Everything ``object_rebake.apply`` needs, and nothing it must
    compute: per-resource, per-vertex y offsets plus the audit trail."""

    structures: list[Structure]
    delta_by_resource_and_vertex: dict[str, dict[int, float]]
    anchor_ground_by_resource: dict[str, float]
    # (resource_path, reason) for resources that must not be baked AT
    # ALL: ``object_rebake.apply`` refuses every resource listed here.
    # A resource where only SOME structures were skipped is not listed —
    # its passing structures' deltas are in
    # ``delta_by_resource_and_vertex`` and bake normally (amendment
    # A21); the skipped structures keep their ``skip_reason`` in
    # ``structures``, which is where per-structure detail comes from.
    skipped: list[tuple[str, str]]
    # Amendment A13: (latitude, longitude, heading_degrees) per resource,
    # so the provenance sidecar can record each object's anchor on fresh
    # bakes (workstream W5's escalation: ``apply`` has no placements).
    anchor_by_resource: dict[str, tuple[float, float, float]] = (
        dataclass_field(default_factory=dict))
    # Foot re-anchor audit trail: every foot-anchored structure's
    # detected feet (world/mesh fields filled), keyed by index into
    # ``structures``.  Present even when the structure was later
    # A3-skipped, so the seating audit is never blind to a
    # baked-offset object again.
    foot_clusters_by_structure_index: dict[int, tuple[FootCluster, ...]] = (
        dataclass_field(default_factory=dict))
    # Feet the rigid offset could not seat (see FootPadRequest).
    foot_pad_requests: list[FootPadRequest] = (
        dataclass_field(default_factory=list))
    # Per-cluster seating (DSF_OBJECT_CLUSTER_SEATING; all empty when the
    # gate is off).  ``cluster_pad_requests`` is the ClusterPadRequest
    # sibling of the foot requests; ``cluster_seams`` is the tear audit's
    # reported cut/bridge seams; ``cluster_counts`` carries the run
    # record's reporting numbers (clusters, clusters_baked,
    # clusters_refused, cut_edges, bridge_seams).
    cluster_pad_requests: list[ClusterPadRequest] = (
        dataclass_field(default_factory=list))
    cluster_seams: list[ClusterSeam] = (
        dataclass_field(default_factory=list))
    cluster_counts: dict[str, int] = (
        dataclass_field(default_factory=dict))
    # WHICH LAW seated each resource, for the provenance sidecar
    # (docs/specs/basin-rim-flush-seating-spec.md section 2.2 item 5:
    # "decision kind recorded in provenance").  Absent for the generic
    # seating law — a resource with no entry was seated by the
    # median/A3/threshold arithmetic in :func:`structure_deltas`, which
    # is what every entry-less provenance record already means.  The one
    # value in use today is
    # ``object_terrain_assembly.BASIN_RIM_FLUSH_DECISION_KIND``.
    decision_kind_by_resource: dict[str, str] = (
        dataclass_field(default_factory=dict))


@dataclass(frozen=True)
class _PoolFrame:
    """The shared authored-space frame for one pool (module docstring,
    "the pool frame").  ``shared_vertices`` concatenates every included
    object's vertices, each projected through its own placement into the
    unrotated frame with ``y`` = authored ``v.y``;
    ``base_offset_by_resource`` gives each object's slice start, so
    shared index = original index + base offset (the prototype's shared
    index-space idiom)."""

    origin_latitude: float
    origin_longitude: float
    shared_vertices: list[tuple[float, float, float]]
    base_offset_by_resource: dict[str, int]
    resource_of_shared_vertex: list[str]
    included_resources: list[str]
    excluded_resources: list[tuple[str, str]]  # (resource_path, reason)


def _placements_mean_origin(
    placements: list[ObjectPlacement],
) -> tuple[float, float]:
    origin_latitude = sum(
        placement.latitude for placement in placements
    ) / len(placements)
    origin_longitude = sum(
        placement.longitude for placement in placements
    ) / len(placements)
    return origin_latitude, origin_longitude


def _world_point_to_pool_frame(
    origin_latitude: float,
    origin_longitude: float,
    latitude: float,
    longitude: float,
) -> tuple[float, float]:
    """Map a world position into the unrotated pool frame: ``x`` = metres
    east of the origin, ``z`` = metres south (a synthetic heading-0
    placement at the pool origin)."""
    return obj8_reader.lonlat_to_local_offset(
        origin_latitude, origin_longitude, 0.0, latitude, longitude
    )


def _pool_frame_to_world_point(
    origin_latitude: float,
    origin_longitude: float,
    frame_x: float,
    frame_z: float,
) -> tuple[float, float]:
    """Inverse of :func:`_world_point_to_pool_frame`: pool-frame metres
    back to ``(latitude, longitude)``."""
    return obj8_reader.local_offset_to_lonlat(
        origin_latitude, origin_longitude, 0.0, frame_x, frame_z
    )


def detect_foot_clusters(
    points: list[tuple[float, float, float]],
    resources: list[str],
    *,
    band_metres: float,
    cluster_gap_metres: float,
    maximum_base_spread_metres: float,
) -> list[FootCluster]:
    """Detect a structure's ground-contact FEET relative to its own
    lowest band (never the absolute ``y <= DSF_OBJECT_ELEVATED_BASE_M``
    test, which an author-baked vertical offset defeats).

    ``points`` are the structure's solid vertices ``(x, y, z)`` in the
    pool frame (``y`` = authored vertical); ``resources`` is parallel.
    Three stages, each doing one job (constants documented in
    ``config.py``):

    1. CONTACT BAND — a vertex qualifies when it lies within
       ``band_metres`` of the lowest vertex in its own horizontal
       neighbourhood (radius ``cluster_gap_metres``).  A local band,
       not a global one: the 45 m KBNA stair's feet sit 1.17 m apart
       in authored y, and near each foot the band must exclude the
       stair stringers right above it.
    2. CLUSTERING — band vertices chain into one foot when within
       ``cluster_gap_metres`` horizontally AND ``band_metres``
       vertically per link.  The vertical constraint keeps a foot from
       chaining up a staircase onto the deck underside.
    3. FOOT GATE — a cluster is a foot only when its base lies within
       ``maximum_base_spread_metres`` of the structure's overall lowest
       vertex.  Mid-span deck-underside clusters (their own local
       minima, stage 1 cannot see the feet from there) start ~1.9 m up
       on the measured KBNA stairs and are dropped here.

    Returns feet ordered by ``(centroid_x, centroid_z)`` for
    determinism.  A single-foot result is normal (most objects); the
    caller decides what to do with it.
    """
    if not points:
        return []
    minimum_y_overall = min(point[1] for point in points)

    # Stage 1 — grid-bucketed local-minimum band.
    cell_size = cluster_gap_metres if cluster_gap_metres > 0.0 else 1.0
    indices_by_cell: dict[tuple[int, int], list[int]] = defaultdict(list)
    for point_index, (x, _y, z) in enumerate(points):
        indices_by_cell[
            (int(math.floor(x / cell_size)), int(math.floor(z / cell_size)))
        ].append(point_index)

    def _neighbour_indices(x: float, z: float):
        cell_x = int(math.floor(x / cell_size))
        cell_z = int(math.floor(z / cell_size))
        for offset_x in (-1, 0, 1):
            for offset_z in (-1, 0, 1):
                yield from indices_by_cell.get(
                    (cell_x + offset_x, cell_z + offset_z), ()
                )

    candidate_indices: list[int] = []
    for point_index, (x, y, z) in enumerate(points):
        local_minimum_y = y
        for other_index in _neighbour_indices(x, z):
            other_x, other_y, other_z = points[other_index]
            if other_y < local_minimum_y and (
                math.hypot(other_x - x, other_z - z) <= cluster_gap_metres
            ):
                local_minimum_y = other_y
        if y <= local_minimum_y + band_metres:
            candidate_indices.append(point_index)
    if not candidate_indices:
        return []

    # Stage 2 — single-linkage union-find over the candidates.
    position_in_candidates = {
        point_index: candidate_position
        for candidate_position, point_index in enumerate(candidate_indices)
    }
    parent = list(range(len(candidate_indices)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    for candidate_position, point_index in enumerate(candidate_indices):
        x, y, z = points[point_index]
        for other_index in _neighbour_indices(x, z):
            other_position = position_in_candidates.get(other_index)
            if other_position is None or other_position <= candidate_position:
                continue
            other_x, other_y, other_z = points[other_index]
            if (
                abs(other_y - y) <= band_metres
                and math.hypot(other_x - x, other_z - z)
                <= cluster_gap_metres
            ):
                union(candidate_position, other_position)

    members_by_root: dict[int, list[int]] = defaultdict(list)
    for candidate_position, point_index in enumerate(candidate_indices):
        members_by_root[find(candidate_position)].append(point_index)

    # Stage 3 — the foot gate, then one FootCluster per surviving group.
    feet: list[FootCluster] = []
    for member_indices in members_by_root.values():
        base_index = min(
            member_indices, key=lambda point_index: points[point_index][1]
        )
        base_y = points[base_index][1]
        if base_y > minimum_y_overall + maximum_base_spread_metres:
            continue
        contact_indices = [
            point_index
            for point_index in member_indices
            if points[point_index][1] <= base_y + band_metres
        ]
        centroid_x = sum(
            points[point_index][0] for point_index in contact_indices
        ) / len(contact_indices)
        centroid_z = sum(
            points[point_index][2] for point_index in contact_indices
        ) / len(contact_indices)
        feet.append(
            FootCluster(
                centroid_x=centroid_x,
                centroid_z=centroid_z,
                base_y=base_y,
                base_resource=resources[base_index],
                contact_points=tuple(
                    (points[point_index][0], points[point_index][2])
                    for point_index in contact_indices
                ),
            )
        )
    feet.sort(key=lambda foot: (foot.centroid_x, foot.centroid_z))
    return feet


# ---------------------------------------------------------------------------
# Supporter selection (invariant I-8) — the smallest containing parent.
# ---------------------------------------------------------------------------
# Defect B (HECA, 2026-07-26): "first containing supporter in index
# order" hands every nested inheritor to whichever containing structure
# the partition happened to emit first, which for a co-baked payware pack
# is the kilometre-scale terminal web (HECA structure 0, 1237 x 2480 m,
# 8,102 inheritors — 1,761 of them with a SMALLER containing supporter
# available).  ``DSF_OBJECT_SUPPORTER_SMALLEST`` picks the smallest
# containing box instead.
#
# Done naively that costs a full scan of every supporter for every
# inheritor whose only container is the mega-structure (8,102 x 2,500 =
# 20 M box tests at HECA, seconds of build time), because the winning
# candidate no longer sits at the front of the list.  The grid below
# keeps it linear: supporters are bucketed by the cells their plan box
# covers, each bucket ordered smallest-area-first, so the first
# containing member of a bucket IS that bucket's answer.  A box covering
# more than ``_SUPPORTER_GRID_OVERSIZED_CELLS`` cells is held aside in
# one small ``oversized`` list rather than written into every cell — one
# airport-sized structure must never cost the whole grid.
_SUPPORTER_GRID_TARGET_CELLS = 4096
_SUPPORTER_GRID_OVERSIZED_CELLS = 64


def _plan_box_area_square_metres(
    box: tuple[float, float, float, float] | None,
) -> float:
    """Plan (horizontal) area of a ``(min_x, max_x, min_z, max_z)`` box.
    ``None`` — a structure with no triangles in this pool's frame — is
    infinitely large so it can never win the smallest-containing test."""
    if box is None:
        return math.inf
    return (box[1] - box[0]) * (box[3] - box[2])


@dataclass(frozen=True)
class _SupporterIndex:
    """Grid index over candidate supporters' plan boxes.

    ``cells`` maps a ``(cell_x, cell_z)`` key to the supporter indices
    whose box reaches that cell, ordered by ``(plan box area, structure
    index)``; ``oversized`` holds the same ordering for boxes too large
    to bucket.  Both orderings put the smallest box first, so the FIRST
    containing member of either list is that list's smallest containing
    supporter and the overall answer is the smaller of the two."""

    cell_size_metres: float
    origin_x: float
    origin_z: float
    cells: dict[tuple[int, int], list[int]]
    oversized: list[int]


def _build_supporter_index(
    supporter_indices: list[int],
    bounding_box_by_structure: list[tuple[float, float, float, float] | None],
) -> _SupporterIndex:
    """Bucket the candidate supporters for smallest-containing lookup."""
    boxed_indices = [
        candidate_index
        for candidate_index in supporter_indices
        if bounding_box_by_structure[candidate_index] is not None
    ]
    if not boxed_indices:
        return _SupporterIndex(1.0, 0.0, 0.0, {}, [])

    minimum_x = min(
        bounding_box_by_structure[index][0] for index in boxed_indices
    )
    maximum_x = max(
        bounding_box_by_structure[index][1] for index in boxed_indices
    )
    minimum_z = min(
        bounding_box_by_structure[index][2] for index in boxed_indices
    )
    maximum_z = max(
        bounding_box_by_structure[index][3] for index in boxed_indices
    )
    width = max(maximum_x - minimum_x, 1.0)
    depth = max(maximum_z - minimum_z, 1.0)
    cell_size_metres = max(
        math.sqrt(width * depth / _SUPPORTER_GRID_TARGET_CELLS), 1.0
    )

    # Smallest box first, ties by lowest structure index — the ordering
    # every bucket inherits, and the tie-break the design specifies.
    ordered_indices = sorted(
        boxed_indices,
        key=lambda candidate_index: (
            _plan_box_area_square_metres(
                bounding_box_by_structure[candidate_index]
            ),
            candidate_index,
        ),
    )

    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    oversized: list[int] = []
    for candidate_index in ordered_indices:
        box = bounding_box_by_structure[candidate_index]
        first_cell_x = int(math.floor((box[0] - minimum_x) / cell_size_metres))
        last_cell_x = int(math.floor((box[1] - minimum_x) / cell_size_metres))
        first_cell_z = int(math.floor((box[2] - minimum_z) / cell_size_metres))
        last_cell_z = int(math.floor((box[3] - minimum_z) / cell_size_metres))
        covered_cells = (last_cell_x - first_cell_x + 1) * (
            last_cell_z - first_cell_z + 1
        )
        if covered_cells > _SUPPORTER_GRID_OVERSIZED_CELLS:
            oversized.append(candidate_index)
            continue
        for cell_x in range(first_cell_x, last_cell_x + 1):
            for cell_z in range(first_cell_z, last_cell_z + 1):
                cells[(cell_x, cell_z)].append(candidate_index)
    return _SupporterIndex(
        cell_size_metres=cell_size_metres,
        origin_x=minimum_x,
        origin_z=minimum_z,
        cells=dict(cells),
        oversized=oversized,
    )


def _smallest_containing_supporter_index(
    index: _SupporterIndex,
    bounding_box_by_structure: list[tuple[float, float, float, float] | None],
    centroid_x: float,
    centroid_z: float,
) -> int | None:
    """The containing supporter with the smallest plan box (ties: lowest
    structure index), or ``None`` when no candidate box contains the
    point."""
    cell_size = index.cell_size_metres
    cell_key = (
        int(math.floor((centroid_x - index.origin_x) / cell_size)),
        int(math.floor((centroid_z - index.origin_z) / cell_size)),
    )
    best_index: int | None = None
    best_key: tuple[float, int] | None = None
    for candidates in (index.cells.get(cell_key, ()), index.oversized):
        for candidate_index in candidates:
            box = bounding_box_by_structure[candidate_index]
            if (
                box[0] <= centroid_x <= box[1]
                and box[2] <= centroid_z <= box[3]
            ):
                candidate_key = (
                    _plan_box_area_square_metres(box),
                    candidate_index,
                )
                if best_key is None or candidate_key < best_key:
                    best_index, best_key = candidate_index, candidate_key
                # Each list is ordered smallest-first, so the first hit
                # is that list's best; nothing after it can improve on it.
                break
    return best_index


@dataclass(frozen=True)
class ConnectorMetrics:
    """Footprint metrics that recognise a CONNECTOR object.

    Defect 2026-07-17 (UK payware co-baked airports): scenery packs bake
    a whole airport as many ``.obj`` files sharing one anchor, and among
    them are CONNECTOR meshes — perimeter fences, road/rail networks,
    whole-complex ground slabs — whose base geometry physically touches
    (within the contact epsilon) every real building.  Left in the pool
    they chain all the buildings into one connected structure whose
    convex hull fills the field, burying the real buildings and the
    below-grade tunnels under one airport-sized pad (EGGW building1 was
    2,814,841 m²; EGLL's T5 web 537,939 m²).

    A connector is long AND sparse: a fence or branching road covers only
    a thin sliver of the convex hull it stretches across; a solid terminal
    slab, however large, fills most of its hull.  Both must hold to flag,
    so a genuine large filled terminal is never mistaken for a connector.

    * ``span_metres`` — the larger side of the solid footprint's
      axis-aligned bounding box (the object's own authored horizontal
      frame; span is invariant to translation and, for the elongated
      connectors this targets, dominated by the long axis regardless of
      heading — measuring in the tight authored frame is the conservative
      choice against false positives on a rotated compact building).
    * ``hull_fill_ratio`` — horizontal solid-triangle area ÷ convex-hull
      area of the footprint (0 when the hull is degenerate).
    """

    span_metres: float
    hull_fill_ratio: float
    footprint_area_square_metres: float
    hull_area_square_metres: float


def _convex_hull_area_square_metres(
    points: list[tuple[float, float]],
) -> float:
    """Area of the convex hull of 2-D ``points`` (Andrew's monotone chain
    followed by the shoelace formula).  Zero when the points do not span
    a two-dimensional area (fewer than three, or all collinear)."""
    unique_points = sorted(set(points))
    if len(unique_points) < 3:
        return 0.0

    def cross(
        origin: tuple[float, float],
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (
            first[1] - origin[1]
        ) * (second[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        return 0.0
    twice_area = 0.0
    for index in range(len(hull)):
        x1, y1 = hull[index]
        x2, y2 = hull[(index + 1) % len(hull)]
        twice_area += x1 * y2 - x2 * y1
    return abs(twice_area) / 2.0


def resource_connector_metrics(
    geometry: ObjectGeometry,
) -> ConnectorMetrics:
    """Measure one object's solid footprint span and hull-fill ratio.

    Pure: geometry in, numbers out (see :class:`ConnectorMetrics` for the
    defect and the metric definitions).  Works on the object's own
    authored ``(x, z)`` horizontal coordinates — both the footprint area
    and the hull area are rotation-invariant, and the bounding-box span is
    measured in the tight authored frame."""
    solid_triangles = geometry.solid_triangles
    if not solid_triangles:
        return ConnectorMetrics(0.0, 0.0, 0.0, 0.0)
    used_indices = {
        index for triangle in solid_triangles for index in triangle
    }
    x_values = [geometry.vertices[index][0] for index in used_indices]
    z_values = [geometry.vertices[index][2] for index in used_indices]
    span_metres = max(
        max(x_values) - min(x_values), max(z_values) - min(z_values)
    )
    footprint_area = 0.0
    for first, second, third in solid_triangles:
        ax, az = geometry.vertices[first][0], geometry.vertices[first][2]
        bx, bz = geometry.vertices[second][0], geometry.vertices[second][2]
        cx, cz = geometry.vertices[third][0], geometry.vertices[third][2]
        footprint_area += abs(
            (bx - ax) * (cz - az) - (cx - ax) * (bz - az)
        ) / 2.0
    hull_area = _convex_hull_area_square_metres(
        [
            (geometry.vertices[index][0], geometry.vertices[index][2])
            for index in used_indices
        ]
    )
    hull_fill_ratio = (
        footprint_area / hull_area if hull_area > 0.0 else 0.0
    )
    return ConnectorMetrics(
        span_metres=span_metres,
        hull_fill_ratio=hull_fill_ratio,
        footprint_area_square_metres=footprint_area,
        hull_area_square_metres=hull_area,
    )


def is_connector_resource(
    geometry: ObjectGeometry,
    *,
    connector_span_metres: float,
    connector_maximum_fill: float,
) -> tuple[bool, ConnectorMetrics]:
    """Return ``(is_connector, metrics)`` for one object.

    A resource is a CONNECTOR — excluded from building pooling and
    partitioning before weld/contact so it cannot chain real buildings
    into one field-spanning structure — only when BOTH conditions hold:
    its footprint span exceeds ``connector_span_metres`` AND its hull-fill
    ratio is below ``connector_maximum_fill``.  A large but FILLED
    footprint (a real mega-terminal) fails the fill test and is kept."""
    metrics = resource_connector_metrics(geometry)
    is_connector = (
        metrics.span_metres > connector_span_metres
        and metrics.hull_fill_ratio < connector_maximum_fill
    )
    return is_connector, metrics


def _build_pool_frame(
    pool: ObjectPool,
    geometry_by_resource: dict[str, ObjectGeometry],
) -> _PoolFrame:
    """Project every usable object's vertices into the pool frame.

    An object is EXCLUDED (with a reason) when its geometry is missing,
    has no solid triangles, or shares vertices between draped and solid
    triangles — the un-correctable case of invariant I-9.
    ``partition_structures`` simply leaves excluded objects out;
    ``structure_deltas`` records the invariant-I-9 exclusions in
    ``RebakeDecision.skipped``.
    """
    origin_latitude, origin_longitude = _placements_mean_origin(
        pool.placements
    )
    shared_vertices: list[tuple[float, float, float]] = []
    base_offset_by_resource: dict[str, int] = {}
    resource_of_shared_vertex: list[str] = []
    included_resources: list[str] = []
    excluded_resources: list[tuple[str, str]] = []

    for placement in pool.placements:
        resource_path = placement.resource_path
        geometry = geometry_by_resource.get(resource_path)
        if geometry is None:
            excluded_resources.append(
                (resource_path, "no parsed geometry available")
            )
            continue
        if not geometry.solid_triangles:
            excluded_resources.append(
                (resource_path, "no solid triangles")
            )
            continue
        # ``getattr`` keeps this duck-type friendly for test doubles that
        # expose only ``vertices`` / ``solid_triangles``.
        if getattr(geometry, "has_mixed_draped_solid_vertices", False):
            excluded_resources.append(
                (
                    resource_path,
                    "vertices shared between draped and solid triangles "
                    "— un-correctable, refused (invariant I-9)",
                )
            )
            continue
        base_offset_by_resource[resource_path] = len(shared_vertices)
        for local_x, authored_y, local_z in geometry.vertices:
            world_latitude, world_longitude = (
                obj8_reader.local_offset_to_lonlat(
                    placement.latitude,
                    placement.longitude,
                    placement.heading_degrees,
                    local_x,
                    local_z,
                )
            )
            frame_x, frame_z = _world_point_to_pool_frame(
                origin_latitude,
                origin_longitude,
                world_latitude,
                world_longitude,
            )
            shared_vertices.append((frame_x, authored_y, frame_z))
        resource_of_shared_vertex.extend(
            [resource_path] * len(geometry.vertices)
        )
        included_resources.append(resource_path)

    return _PoolFrame(
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        shared_vertices=shared_vertices,
        base_offset_by_resource=base_offset_by_resource,
        resource_of_shared_vertex=resource_of_shared_vertex,
        included_resources=included_resources,
        excluded_resources=excluded_resources,
    )


def discover_object_pools(
    placements: list[ObjectPlacement],
    resolved_paths: dict[str, str],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    epsilon_metres: float,
) -> list[ObjectPool]:
    """Group correction-candidate placements whose placed world
    axis-aligned bounding boxes overlap (transitively, expanded by
    ``epsilon_metres``).

    Candidates only: small, correctly anchored objects — a light mast
    beside a terminal wall — must never be pooled; X-Plane already places
    them right, and correcting the terminal moves it towards the mast,
    not away (partition document, section 3 step 0).  Callers pass only
    correction candidates; reach is NOT re-filtered here.

    The world box of each placement is the horizontal bounding box of
    its SOLID triangles, projected through its own placement.  Because
    the heading rotates the box, all FOUR corners are projected — two
    opposite corners under-cover any rotated box.  Overlap is tested on
    the horizontal (east/south) plane only: an elevated clutter object
    hovering over a ground object must pool with it so the inheritance
    rule (invariant I-8) can see its supporter.

    Pooling coarseness is harmless: parts that never come within the
    contact epsilon stay separate structures regardless of how large
    their pool is.
    """
    if not placements:
        return []
    origin_latitude, origin_longitude = _placements_mean_origin(placements)

    expanded_boxes: list[tuple[float, float, float, float]] = []
    for placement in placements:
        geometry = geometry_by_resource.get(placement.resource_path)
        if geometry is not None and geometry.solid_triangles:
            minimum_x, maximum_x, minimum_z, maximum_z = (
                obj8_reader.horizontal_bounding_box(
                    geometry.vertices, geometry.solid_triangles
                )
            )
            corner_offsets = [
                (minimum_x, minimum_z),
                (minimum_x, maximum_z),
                (maximum_x, minimum_z),
                (maximum_x, maximum_z),
            ]
        else:
            # Degenerate: no solid footprint — a point box at the anchor.
            corner_offsets = [(0.0, 0.0)]
        frame_corner_points = []
        for local_x, local_z in corner_offsets:
            world_latitude, world_longitude = (
                obj8_reader.local_offset_to_lonlat(
                    placement.latitude,
                    placement.longitude,
                    placement.heading_degrees,
                    local_x,
                    local_z,
                )
            )
            frame_corner_points.append(
                _world_point_to_pool_frame(
                    origin_latitude,
                    origin_longitude,
                    world_latitude,
                    world_longitude,
                )
            )
        corner_x_values = [point[0] for point in frame_corner_points]
        corner_z_values = [point[1] for point in frame_corner_points]
        expanded_boxes.append(
            (
                min(corner_x_values) - epsilon_metres,
                max(corner_x_values) + epsilon_metres,
                min(corner_z_values) - epsilon_metres,
                max(corner_z_values) + epsilon_metres,
            )
        )

    parent = list(range(len(placements)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    for first_index in range(len(placements)):
        first_box = expanded_boxes[first_index]
        for second_index in range(first_index + 1, len(placements)):
            second_box = expanded_boxes[second_index]
            boxes_overlap = (
                first_box[0] <= second_box[1]
                and second_box[0] <= first_box[1]
                and first_box[2] <= second_box[3]
                and second_box[2] <= first_box[3]
            )
            if boxes_overlap:
                union(first_index, second_index)

    members_by_root: dict[int, list[int]] = defaultdict(list)
    for placement_index in range(len(placements)):
        members_by_root[find(placement_index)].append(placement_index)

    pools: list[ObjectPool] = []
    # Deterministic pool order: by each group's first placement in the
    # caller's input order.
    for members in sorted(members_by_root.values(), key=lambda group: group[0]):
        pool_placements = [placements[index] for index in members]
        pool_resolved_paths = {
            placement.resource_path: resolved_paths[placement.resource_path]
            for placement in pool_placements
            if placement.resource_path in resolved_paths
        }
        pools.append(
            ObjectPool(
                placements=pool_placements,
                resolved_paths=pool_resolved_paths,
            )
        )
    return pools


def _edges_span_group(
    part_indices: list[int],
    group_edges: tuple[tuple[int, int], ...],
    part_key_by_index: list[int],
) -> bool:
    """True when ``group_edges`` is a spanning tree of the group.

    The contact graph is a spanning SUBSET, so a component of ``k``
    parts carries exactly ``k − 1`` of its edges and they connect it.
    Anything else means the group was re-partitioned after the graph was
    built (the connector split) and its restricted edges no longer
    describe its connectivity — per-cluster seating must not cut on
    them (see ``Structure.contact_edges``).
    """
    if len(part_indices) <= 1:
        return not group_edges
    if len(group_edges) != len(part_indices) - 1:
        return False
    index_of_key = {
        part_key_by_index[part_index]: position
        for position, part_index in enumerate(part_indices)
    }
    parent = list(range(len(part_indices)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for left_key, right_key in group_edges:
        left, right = index_of_key.get(left_key), index_of_key.get(right_key)
        if left is None or right is None:
            return False
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return False  # a cycle: cannot be the spanning subset
        parent[left_root] = right_root
    return len({find(node) for node in range(len(part_indices))}) == 1


def partition_structures(
    pool: ObjectPool,
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    epsilon_metres: float,
) -> list[Structure]:
    """Partition a pool's solid geometry into structures.

    Thin composition over ``obj8_partition`` (amendment A1 — Phases 1 and
    2 MUST share this partition): project every object's vertices into
    the pool frame using its own placement (module docstring, "the pool
    frame"), offset each object's vertex indices into one shared index
    space, ``weld_parts`` → ``contact_graph`` → ``connected_structures``,
    then map back per-object.  Draped triangles are discarded before
    partitioning (invariant I-9); an object with vertices shared between
    draped and solid triangles is excluded entirely (``structure_deltas``
    records it in ``RebakeDecision.skipped``).

    Per-resource triangles carry the ORIGINAL per-object vertex indices
    — downstream, ``object_footprints.structure_ring`` and the rebake
    writer index into each object's own ``geometry.vertices``.

    ``ATTR_LOD`` copies are spatially coincident, so the contact graph
    merges them into one structure by itself; being coincident copies,
    they do not displace the area-weighted centroid either (invariant
    I-12).  Positional commands and ``ANIM`` handling are workstream
    W5's concern.

    Phase 2 fields (``ground_span_metres``, ``needs_pad``,
    ``skip_reason``, ``inherited_from_structure_index``) are left at
    their pre-mesh defaults here; ``structure_deltas`` fills them via
    ``dataclasses.replace``.
    """
    from .config import DSF_OBJECT_ELEVATED_BASE_M

    frame = _build_pool_frame(pool, geometry_by_resource)

    shared_triangles: list[Triangle] = []
    for resource_path in frame.included_resources:
        base_offset = frame.base_offset_by_resource[resource_path]
        geometry = geometry_by_resource[resource_path]
        shared_triangles.extend(
            (
                first_index + base_offset,
                second_index + base_offset,
                third_index + base_offset,
            )
            for first_index, second_index, third_index in (
                geometry.solid_triangles
            )
        )
    if not shared_triangles:
        return []

    parts = obj8_partition.weld_parts(frame.shared_vertices, shared_triangles)
    contact_edges = obj8_partition.contact_graph(
        frame.shared_vertices, parts, epsilon_metres
    )
    part_index_groups = obj8_partition.connected_structures(
        len(parts), contact_edges
    )
    # Connector split (2026-07-18, EGGW floating buildings): an
    # airport-scale chained component can never be seated by one rigid
    # offset — re-partition it at its linear connectors so each real
    # building bakes on its own (see the CONNECTOR_SPLIT constants in
    # obj8_partition for the design and the accepted fence-joint cost).
    # ``..._with_edges`` because a split group's connectivity is NOT the
    # pool graph restricted to it — the split re-derives it, and seating
    # needs the re-derived edges (per-cluster seating spec section 3.1;
    # at HECA the split re-partitions exactly the mega-structure the
    # whole spec is about).
    part_index_groups, connector_splits, split_edges_by_group = (
        obj8_partition.split_oversized_components_with_edges(
            frame.shared_vertices, parts, part_index_groups, epsilon_metres
        )
    )
    if connector_splits:
        import O4_UI_Utils as UI

        UI.vprint(
            1,
            f"   [object-anchor] connector split: {connector_splits} "
            "oversized chained component(s) re-partitioned at their "
            "linear connectors (fences/barriers) so member buildings "
            "seat individually",
        )

    # Thread the contact edges through to seating (per-cluster seating
    # spec section 3.1): a part's KEY is the lowest shared vertex index it
    # touches, which ``structure_deltas`` reproduces exactly when it
    # re-welds the structure (welding is intra-part), so keys — not the
    # pool's part indices — are what survives the trip.
    part_key_by_index = [
        min(shared_index for triangle in part for shared_index in triangle)
        for part in parts
    ]
    group_of_part: dict[int, int] = {
        part_index: group_index
        for group_index, part_indices in enumerate(part_index_groups)
        for part_index in part_indices
    }
    edges_by_group: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for left, right in sorted(contact_edges):
        left_group = group_of_part.get(left)
        if left_group is not None and left_group == group_of_part.get(right):
            edges_by_group[left_group].append(
                (part_key_by_index[left], part_key_by_index[right])
            )

    structures: list[Structure] = []
    for group_index, part_indices in enumerate(part_index_groups):
        # A component's share of the spanning contact subset is exactly
        # ``len(parts) - 1`` edges AND connects it.  A group the connector
        # split BUILT carries its own re-derived edges instead (the pool
        # graph restricted to it would describe the wrong connectivity).
        # Either way the set is VERIFIED spanning before seating may cut
        # on it; a set that fails becomes empty, and seating falls back
        # to the per-structure rigid seat rather than mis-cutting.
        split_edges = split_edges_by_group[group_index]
        group_edges = tuple(
            (part_key_by_index[left], part_key_by_index[right])
            for left, right in split_edges
        ) if split_edges is not None else tuple(
            edges_by_group.get(group_index, ())
        )
        if not _edges_span_group(part_indices, group_edges, part_key_by_index):
            group_edges = ()
        structure_shared_triangles = [
            triangle
            for part_index in part_indices
            for triangle in parts[part_index]
        ]
        surface_area_square_metres, centroid_x, centroid_z = (
            obj8_reader.area_weighted_centroid(
                frame.shared_vertices, structure_shared_triangles
            )
        )
        centroid_latitude, centroid_longitude = _pool_frame_to_world_point(
            frame.origin_latitude,
            frame.origin_longitude,
            centroid_x,
            centroid_z,
        )

        triangles_by_resource: dict[str, list[Triangle]] = defaultdict(list)
        minimum_base_y_by_resource: dict[str, float] = {}
        for shared_triangle in structure_shared_triangles:
            # All three indices of one triangle come from one object —
            # index offsets are applied per object.
            resource_path = frame.resource_of_shared_vertex[
                shared_triangle[0]
            ]
            base_offset = frame.base_offset_by_resource[resource_path]
            triangles_by_resource[resource_path].append(
                (
                    shared_triangle[0] - base_offset,
                    shared_triangle[1] - base_offset,
                    shared_triangle[2] - base_offset,
                )
            )
            for shared_index in shared_triangle:
                authored_y = frame.shared_vertices[shared_index][1]
                known_minimum = minimum_base_y_by_resource.get(resource_path)
                if known_minimum is None or authored_y < known_minimum:
                    minimum_base_y_by_resource[resource_path] = authored_y

        is_ground_touching = (
            min(minimum_base_y_by_resource.values())
            <= DSF_OBJECT_ELEVATED_BASE_M
        )
        structures.append(
            Structure(
                triangles_by_resource=dict(triangles_by_resource),
                surface_area_square_metres=surface_area_square_metres,
                centroid_latitude=centroid_latitude,
                centroid_longitude=centroid_longitude,
                minimum_base_y_by_resource=minimum_base_y_by_resource,
                is_ground_touching=is_ground_touching,
                ground_span_metres=None,
                needs_pad=False,
                skip_reason=None,
                inherited_from_structure_index=None,
                contact_edges=group_edges,
            )
        )
    return structures


@dataclass(frozen=True)
class _PartMeasurement:
    """One welded part of a structure with everything the seat needs.

    Exactly the measurement pass 3 always made per part, hoisted into a
    helper so per-cluster seating can run it once, before inheritance,
    without duplicating (or perturbing) the arithmetic.  Ground parts —
    base at or below ``DSF_OBJECT_ELEVATED_BASE_M`` — additionally carry
    their centroid, its world position and the mesh elevation there;
    ``ground_measured`` is False when that sample fell off the mesh and
    the structure centroid's ground was borrowed.
    """

    key: int  # lowest shared vertex index — the part's stable identity
    triangles: list[Triangle]  # shared-index triangles
    base_y: float
    base_resource: str
    is_ground: bool
    plan_box: tuple[float, float, float, float]  # min_x, max_x, min_z, max_z
    area_square_metres: float = 0.0
    centroid_x: float = 0.0
    centroid_z: float = 0.0
    latitude: float | None = None
    longitude: float | None = None
    ground_metres: float | None = None
    ground_measured: bool = True


@dataclass
class _SeatCluster:
    """One rigid body inside a structure (per-cluster seating spec
    section 4): its parts, its median seat, and its own gate outcome."""

    cluster_id: int
    part_keys: list[int]
    ground_keys: list[int]
    # (ground, base_y, base_resource) in part order — the A19/A3 input.
    ground_records: list[tuple[float, float, str]]
    ground_metres: float
    span_metres: float
    box: tuple[float, float, float, float] | None
    centroid_x: float
    centroid_z: float
    diameter_metres: float
    needs_pad: bool = False
    skip_reason: str | None = None


def _median(values: list[float]) -> float:
    """Amendment A19's statistic, verbatim (the seat of a set of ground
    samples: the best single rigid offset)."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _measure_structure_parts(
    frame: _PoolFrame,
    sampler: MeshElevationSampler,
    structure_shared_triangles: list[Triangle],
    structure_ground: float,
    elevated_base_metres: float,
    *,
    for_clustering: bool = False,
) -> list[_PartMeasurement]:
    """Weld one structure's triangles into parts and measure each one.

    Ground-touching parts, re-derived from the SAME welding the
    partition used (welding is intra-part, so welding a structure's own
    triangles reproduces exactly its parts).  A part centroid off the
    mesh borrows the structure centroid's ground — noted, not fatal:
    the structure centroid IS on the mesh, and one stray part must not
    poison the whole structure (invariant I-13 applies to the structure).

    ``for_clustering`` adds the two fields only per-cluster seating needs
    — the part KEY and its plan box — which cost a sweep over every
    part's vertices.  Off (the default, and the whole per-STRUCTURE
    path) this function performs exactly the operations the pass-3
    inline loop always did: the seating gate must not be paid for by
    builds that have it switched off (build-time HARD LAW, repo-root
    CLAUDE.md).
    """
    measurements: list[_PartMeasurement] = []
    for part_triangles in obj8_partition.weld_parts(
        frame.shared_vertices, structure_shared_triangles
    ):
        used_shared_indices = {
            shared_index
            for triangle in part_triangles
            for shared_index in triangle
        }
        base_shared_index = min(
            used_shared_indices,
            key=lambda shared_index: frame.shared_vertices[shared_index][1],
        )
        part_base_y = frame.shared_vertices[base_shared_index][1]
        base_resource = frame.resource_of_shared_vertex[base_shared_index]
        if for_clustering:
            plan_x = [
                frame.shared_vertices[shared_index][0]
                for shared_index in used_shared_indices
            ]
            plan_z = [
                frame.shared_vertices[shared_index][2]
                for shared_index in used_shared_indices
            ]
            plan_box = (min(plan_x), max(plan_x), min(plan_z), max(plan_z))
            key = min(used_shared_indices)
        else:
            plan_box = (0.0, 0.0, 0.0, 0.0)
            key = base_shared_index
        common = dict(
            key=key,
            triangles=part_triangles,
            base_y=part_base_y,
            base_resource=base_resource,
            plan_box=plan_box,
        )
        if part_base_y > elevated_base_metres:
            measurements.append(_PartMeasurement(is_ground=False, **common))
            continue
        part_area, part_x, part_z = obj8_reader.area_weighted_centroid(
            frame.shared_vertices, part_triangles
        )
        part_latitude, part_longitude = _pool_frame_to_world_point(
            frame.origin_latitude, frame.origin_longitude, part_x, part_z
        )
        part_ground = sampler.elevation_at_or_none(part_latitude, part_longitude)
        ground_measured = part_ground is not None
        if part_ground is None:
            import O4_UI_Utils as UI

            UI.vprint(
                2,
                "  [object-anchor] ground part centroid "
                f"({part_latitude:.6f}, {part_longitude:.6f}) lies "
                "outside the built mesh; using the structure "
                "centroid's ground for it",
            )
            part_ground = structure_ground
        measurements.append(
            _PartMeasurement(
                is_ground=True,
                area_square_metres=part_area,
                centroid_x=part_x,
                centroid_z=part_z,
                latitude=part_latitude,
                longitude=part_longitude,
                ground_metres=part_ground,
                ground_measured=ground_measured,
                **common,
            )
        )
    return measurements


def _union_plan_boxes(
    boxes: list[tuple[float, float, float, float]],
) -> tuple[float, float, float, float] | None:
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        max(box[1] for box in boxes),
        min(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _build_structure_clusters(
    measurements: list[_PartMeasurement],
    partition,
    structure_box: tuple[float, float, float, float] | None,
    structure_centroid: tuple[float, float],
) -> list[_SeatCluster]:
    """Turn a :class:`object_clusters.ClusterPartition` into seated
    clusters: members, median seat, span, plan box, diameter.

    Elevated components that touched no cluster (spec section 4.2a,
    "touches zero clusters") are re-homed here by the invariant-I-8 rule
    applied to CLUSTER boxes: the smallest containing box, else the
    nearest cluster centroid.

    Degeneracy (spec section 2): with exactly one cluster the box and
    centroid are the STRUCTURE's own, so the A3 diameter guard and the
    nearest-supporter arithmetic are bit-for-bit what per-structure
    seating computed.
    """
    measurement_by_key = {
        measurement.key: measurement for measurement in measurements
    }
    order_by_key = {
        measurement.key: order
        for order, measurement in enumerate(measurements)
    }
    keys_by_cluster: dict[int, list[int]] = {
        cluster_id: [] for cluster_id in range(partition.cluster_count)
    }
    for measurement in measurements:
        cluster_id = partition.cluster_id_by_part_key.get(measurement.key)
        if cluster_id is not None:
            keys_by_cluster[cluster_id].append(measurement.key)

    if partition.unassigned_elevated_components:
        preliminary_boxes = {
            cluster_id: _union_plan_boxes(
                [measurement_by_key[key].plan_box for key in keys]
            )
            for cluster_id, keys in keys_by_cluster.items()
        }
        preliminary_centroids = {
            cluster_id: (
                ((box[0] + box[1]) / 2.0, (box[2] + box[3]) / 2.0)
                if box is not None
                else (0.0, 0.0)
            )
            for cluster_id, box in preliminary_boxes.items()
        }
        for component_keys in partition.unassigned_elevated_components:
            component_box = _union_plan_boxes(
                [measurement_by_key[key].plan_box for key in component_keys]
            )
            if component_box is None or not keys_by_cluster:
                continue
            point_x = (component_box[0] + component_box[1]) / 2.0
            point_z = (component_box[2] + component_box[3]) / 2.0
            containing = [
                cluster_id
                for cluster_id, box in preliminary_boxes.items()
                if box is not None
                and box[0] <= point_x <= box[1]
                and box[2] <= point_z <= box[3]
            ]
            if containing:
                host = min(
                    containing,
                    key=lambda cluster_id: (
                        _plan_box_area_square_metres(
                            preliminary_boxes[cluster_id]
                        ),
                        cluster_id,
                    ),
                )
            else:
                host = min(
                    keys_by_cluster,
                    key=lambda cluster_id: (
                        math.hypot(
                            preliminary_centroids[cluster_id][0] - point_x,
                            preliminary_centroids[cluster_id][1] - point_z,
                        ),
                        cluster_id,
                    ),
                )
            keys_by_cluster[host].extend(component_keys)

    clusters: list[_SeatCluster] = []
    single = partition.cluster_count == 1
    for cluster_id in range(partition.cluster_count):
        keys = sorted(keys_by_cluster[cluster_id], key=order_by_key.get)
        ground_keys = [
            key for key in keys if measurement_by_key[key].is_ground
        ]
        ground_records = [
            (
                measurement_by_key[key].ground_metres,
                measurement_by_key[key].base_y,
                measurement_by_key[key].base_resource,
            )
            for key in ground_keys
        ]
        grounds = [record[0] for record in ground_records]
        box = (
            structure_box
            if single
            else _union_plan_boxes(
                [measurement_by_key[key].plan_box for key in keys]
            )
        )
        if single:
            centroid_x, centroid_z = structure_centroid
        else:
            total_area = sum(
                measurement_by_key[key].area_square_metres
                for key in ground_keys
            )
            if total_area > 0.0:
                centroid_x = sum(
                    measurement_by_key[key].centroid_x
                    * measurement_by_key[key].area_square_metres
                    for key in ground_keys
                ) / total_area
                centroid_z = sum(
                    measurement_by_key[key].centroid_z
                    * measurement_by_key[key].area_square_metres
                    for key in ground_keys
                ) / total_area
            elif box is not None:
                centroid_x = (box[0] + box[1]) / 2.0
                centroid_z = (box[2] + box[3]) / 2.0
            else:
                centroid_x, centroid_z = structure_centroid
        clusters.append(
            _SeatCluster(
                cluster_id=cluster_id,
                part_keys=keys,
                ground_keys=ground_keys,
                ground_records=ground_records,
                ground_metres=_median(grounds) if grounds else 0.0,
                span_metres=(
                    max(grounds) - min(grounds) if grounds else 0.0
                ),
                box=box,
                centroid_x=centroid_x,
                centroid_z=centroid_z,
                diameter_metres=(
                    math.hypot(box[1] - box[0], box[3] - box[2])
                    if box is not None
                    else 0.0
                ),
            )
        )
    return clusters


def _max_abs_delta_metres(
    resource_paths,
    seat_ground_metres: float,
    anchor_ground_by_resource: dict[str, float],
    threshold_metres: float,
) -> float:
    """``max |delta(unit, O)|`` over a seating unit's resources — the
    reseat threshold's statistic (reseat-threshold spec section 2.1).

    ``delta(unit, O) = seat_ground − anchor_ground(O)`` is exactly the
    offset the bake would write (invariant I-3), so this measures the
    correction in AUTHORED space and nothing is re-derived.  A resource
    with no anchor ground never receives a delta (invariant I-13 skipped
    it), so it cannot vote.

    Short-circuits as soon as the threshold is reached: the value itself
    is only needed when the unit stays BELOW it (the reason text quotes
    it), and above it the only question is whether the unit bakes.
    """
    maximum_metres = 0.0
    for resource_path in resource_paths:
        anchor_ground = anchor_ground_by_resource.get(resource_path)
        if anchor_ground is None:
            continue
        magnitude = abs(seat_ground_metres - anchor_ground)
        if magnitude > maximum_metres:
            maximum_metres = magnitude
            if maximum_metres >= threshold_metres:
                break
    return maximum_metres


def _cluster_resource_paths(cluster, measurement_by_key, frame):
    """Every resource a cluster's parts carry geometry from, in the
    partition's own order (the resource the delta loop resolves per
    triangle — a welded part may span several)."""
    for key in cluster.part_keys:
        for triangle in measurement_by_key[key].triangles:
            yield frame.resource_of_shared_vertex[triangle[0]]


def _below_bake_threshold_reason(
    maximum_delta_metres: float,
    threshold_metres: float,
    unit_description: str,
    *,
    measure_only: bool,
) -> str:
    """The ``skip_reason`` of a unit the reseat threshold leaves alone
    (spec section 2.1) — the measured max |delta| is part of the record,
    not a rounded adjective.

    ``unit_description`` is ``"structure"`` on the plain path and
    ``"cluster <id>"`` on the clustered one; it is TAGGED into the phrase
    so the per-airport summary can add the two populations without
    counting a clustered structure's echo twice
    (:data:`BELOW_BAKE_THRESHOLD_STRUCTURE_TAG`).
    """
    tagged_phrase = (
        f"{BELOW_BAKE_THRESHOLD_SKIP_REASON_PHRASE}[{unit_description}]"
    )
    if measure_only:
        return (
            f"{tagged_phrase}: measure-only run "
            "(modify_custom_airports is off) — every unit is routed as if "
            "below the reseat threshold, so the installed package is not "
            f"modified; the correction this {unit_description} would have "
            f"baked is {maximum_delta_metres:.3f} m (max over its "
            "resources).  Terrain adapts instead (reseat-threshold spec "
            "section 2.3)"
        )
    return (
        f"{tagged_phrase}: max resource "
        f"|delta| {maximum_delta_metres:.3f} m is under the "
        f"{threshold_metres:.3f} m reseat threshold "
        f"(DSF_OBJECT_BAKE_MIN_DELTA_M) — this {unit_description} stays "
        "at its authored elevations and the terrain adapts to it "
        "(reseat-threshold spec section 2.1)"
    )


def _seat_clusters(
    *,
    structure: Structure,
    structure_index: int,
    clusters: list[_SeatCluster],
    partition,
    measurements: list[_PartMeasurement],
    frame: _PoolFrame,
    anchor_ground_by_resource: dict[str, float],
    delta_by_resource_and_vertex: dict[str, dict[int, float]],
    cluster_pad_requests: list[ClusterPadRequest],
    cluster_seams: list[ClusterSeam],
    maximum_ground_span_metres: float,
    pad_flag_span_metres: float,
    pad_residual_metres: float,
    pad_maximum_relief_metres: float,
    bake_minimum_delta_metres: float,
    nobake_pad_floor_metres: float,
    measure_only: bool = False,
) -> tuple[Structure, int, int, int]:
    """Seat one clustered structure: per-cluster gates, deltas, pads and
    seams (per-cluster seating spec sections 4.1, 4.3, 4.5, 5.3).

    Returns ``(updated structure, clusters baked, clusters refused,
    clusters below the reseat threshold)``.  Each cluster is a rigid
    body:

    * RESEAT THRESHOLD (reseat-threshold spec section 2.1) — a cluster
      whose largest per-resource correction is under
      ``DSF_OBJECT_BAKE_MIN_DELTA_M`` is not baked at all: the pack is
      left exactly as its author shipped it and the cluster's ground
      contacts are routed to the pad system (section 2.2), which is the
      owner's stated preference.  Checked BEFORE the A3 arithmetic (it
      is cheaper, and A3 only ever governed units that bake).
    * SPAN GATE — a cluster over ``DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M`` is
      no longer refused outright.  It is **baked and padded** (spec
      section 4.3): seated at its median, flagged ``needs_pad``, and its
      out-of-tolerance ground parts raise ``ClusterPadRequest``s.  The
      backstop survives as an accumulation guard (a chain of kept edges
      each under T can climb a gentle slope without bound), but its
      OUTCOME changes — refusing a real terminal zone and leaving it at
      authored elevations is the failure this whole spec exists to fix.
    * ROBUST A3 — the median-seat-vs-authored comparison runs per
      cluster, with the diameter guard now applied to a building-scale
      diameter (which is the meaning A19 took away from it at
      mega-structure scale).  A cluster whose correction would worsen
      its seating stays unbaked.

    Only the parts of BAKED clusters receive deltas; a refused cluster's
    vertices simply carry none and keep their authored y, exactly as a
    refused structure's do (amendment A21 accounting is unchanged).
    """
    measurement_by_key = {
        measurement.key: measurement for measurement in measurements
    }
    all_grounds = [
        record[0] for cluster in clusters for record in cluster.ground_records
    ]
    structure_span_metres = (
        max(all_grounds) - min(all_grounds) if all_grounds else 0.0
    )

    clusters_baked = 0
    clusters_refused = 0
    clusters_below_threshold = 0
    for cluster in clusters:
        cluster.needs_pad = cluster.span_metres > pad_flag_span_metres
        over_span = cluster.span_metres > maximum_ground_span_metres
        if over_span:
            # Bake-and-pad (spec section 4.3): seated at its median, the
            # residue handed to the terrain side.
            cluster.needs_pad = True

        # THE RESEAT THRESHOLD (reseat-threshold spec section 2.1),
        # before the A3 comparison.  A cluster is one rigid body, so the
        # MAX over its resources decides for all of them: one member
        # needing the threshold reseats the whole cluster, and a cluster
        # whose every member is under it stays entirely at its authored
        # elevations with the terrain coming to it instead.
        maximum_delta_metres = _max_abs_delta_metres(
            _cluster_resource_paths(cluster, measurement_by_key, frame),
            cluster.ground_metres,
            anchor_ground_by_resource,
            bake_minimum_delta_metres,
        )
        if maximum_delta_metres < bake_minimum_delta_metres:
            cluster.skip_reason = _below_bake_threshold_reason(
                maximum_delta_metres,
                bake_minimum_delta_metres,
                f"cluster {cluster.cluster_id}",
                measure_only=measure_only,
            )
            clusters_below_threshold += 1
            # Terrain adapts (spec section 2.2): the same request
            # builder, measured against the UNBAKED (authored,
            # as-draped) base, at the no-bake materiality floor.
            _raise_cluster_pad_requests(
                cluster=cluster,
                structure_index=structure_index,
                partition=partition,
                measurement_by_key=measurement_by_key,
                frame=frame,
                cluster_pad_requests=cluster_pad_requests,
                pad_residual_metres=nobake_pad_floor_metres,
                pad_maximum_relief_metres=pad_maximum_relief_metres,
                anchor_ground_by_resource=anchor_ground_by_resource,
                seated=False,
            )
            continue

        # Amendment A3, bounded by amendment A19, per cluster.
        if cluster.ground_records and (
            cluster.diameter_metres <= A3_GUARD_MAXIMUM_DIAMETER_METRES
        ):
            corrected_residuals = [
                abs(cluster.ground_metres + part_base_y - part_ground)
                for part_ground, part_base_y, _base_resource in (
                    cluster.ground_records
                )
            ]
            uncorrected_residuals = [
                abs(
                    anchor_ground_by_resource[base_resource]
                    + part_base_y
                    - part_ground
                )
                for part_ground, part_base_y, base_resource in (
                    cluster.ground_records
                )
            ]
            corrected_mean = sum(corrected_residuals) / len(
                corrected_residuals
            )
            uncorrected_mean = sum(uncorrected_residuals) / len(
                uncorrected_residuals
            )
            if corrected_mean > (
                uncorrected_mean + RESIDUAL_COMPARISON_TOLERANCE_METRES
            ):
                cluster.skip_reason = (
                    "single-offset correction would worsen the seating: "
                    f"mean ground-part residual {corrected_mean:.3f} m "
                    f"corrected vs {uncorrected_mean:.3f} m uncorrected "
                    f"over {len(cluster.ground_records)} ground-touching "
                    "part(s) — left unbaked (amendment A3, per cluster "
                    f"{cluster.cluster_id})"
                )
        if cluster.skip_reason is not None:
            clusters_refused += 1
            continue

        clusters_baked += 1
        # The deltas.  Invariant I-3 at cluster granularity: each
        # resource's offset is measured from ITS OWN anchor's ground, and
        # a resource contributing to several clusters simply carries
        # several values across its vertex map (the rebake writer, the
        # reversion pass and the I-16 rewriter are all vertex-granular).
        for key in cluster.part_keys:
            for triangle in measurement_by_key[key].triangles:
                resource_path = frame.resource_of_shared_vertex[triangle[0]]
                anchor_ground = anchor_ground_by_resource.get(resource_path)
                if anchor_ground is None:
                    continue
                base_offset = frame.base_offset_by_resource[resource_path]
                delta = cluster.ground_metres - anchor_ground
                resource_deltas = delta_by_resource_and_vertex.setdefault(
                    resource_path, {}
                )
                for shared_index in triangle:
                    resource_deltas[shared_index - base_offset] = delta

        # Pad requests (spec section 5.3): maximal CONNECTED groups of
        # ground parts the rigid seat still leaves off the mesh.
        _raise_cluster_pad_requests(
            cluster=cluster,
            structure_index=structure_index,
            partition=partition,
            measurement_by_key=measurement_by_key,
            frame=frame,
            cluster_pad_requests=cluster_pad_requests,
            pad_residual_metres=pad_residual_metres,
            pad_maximum_relief_metres=pad_maximum_relief_metres,
            anchor_ground_by_resource=anchor_ground_by_resource,
            seated=True,
        )

    # The tear audit's reported seams (spec section 4.5).  A cut seam is
    # explained by the ground step measured at decision time; a bridge
    # seam is the residual an elevated component spanning two clusters
    # keeps toward the cluster it did not join — reported, never
    # averaged across.
    ground_metres_by_cluster = {
        cluster.cluster_id: cluster.ground_metres for cluster in clusters
    }
    cluster_id_by_part_key = partition.cluster_id_by_part_key
    for cut in partition.cut_edges:
        left_cluster = cluster_id_by_part_key.get(cut.left_key)
        right_cluster = cluster_id_by_part_key.get(cut.right_key)
        if left_cluster is None or right_cluster is None:
            continue
        cluster_seams.append(
            ClusterSeam(
                kind="cut",
                structure_index=structure_index,
                cluster_id=left_cluster,
                other_cluster_id=right_cluster,
                seam_metres=abs(
                    ground_metres_by_cluster.get(left_cluster, 0.0)
                    - ground_metres_by_cluster.get(right_cluster, 0.0)
                ),
                ground_step_metres=cut.ground_step_metres,
            )
        )
    for seam in partition.bridge_seams:
        cluster_seams.append(
            ClusterSeam(
                kind="bridge",
                structure_index=structure_index,
                cluster_id=seam.cluster_id,
                other_cluster_id=seam.other_cluster_id,
                seam_metres=abs(
                    ground_metres_by_cluster.get(seam.cluster_id, 0.0)
                    - ground_metres_by_cluster.get(seam.other_cluster_id, 0.0)
                ),
                part_count=seam.part_count,
            )
        )

    unbaked_reasons = [
        cluster.skip_reason
        for cluster in clusters
        if cluster.skip_reason is not None
    ]
    structure_skip_reason = None
    if unbaked_reasons and len(unbaked_reasons) == len(clusters):
        # No cluster baked (refused, or below the reseat threshold): the
        # structure as a whole stays at its authored elevations, and its
        # inheritors share that fate — supporter-fate is unchanged by the
        # threshold law (reseat-threshold spec section 2.1).
        structure_skip_reason = unbaked_reasons[0]
    return (
        replace(
            structure,
            ground_span_metres=structure_span_metres,
            needs_pad=any(cluster.needs_pad for cluster in clusters),
            skip_reason=structure_skip_reason,
        ),
        clusters_baked,
        clusters_refused,
        clusters_below_threshold,
    )


def _contact_band_triangles_lonlat(
    frame: _PoolFrame,
    measurement: _PartMeasurement,
    band_metres: float,
) -> list[tuple[tuple[float, float], ...]]:
    """One part's GROUND-CONTACT GEOMETRY: the 2D projection of the
    triangles whose vertices all sit inside the part's contact band
    (object-reseat-threshold-spec §2.5 v2b).

    The band is ``DSF_OBJECT_FOOT_BAND_M`` above the part's own base —
    the same band the foot machinery clusters vertices in — so a wall
    rising off the ground is excluded and what is left is the skin the
    part actually stands on.  One group per triangle: the ring law
    (``object_footprints.foot_pad_rings``) hulls each group and unions
    the dilated hulls, so a road network yields thin bands along the
    road and a bridge yields its touchdown patches, instead of the one
    560 x 534 m plan box that mega-part reduced to before (the v2b
    falsification: the padrings lane measured that per-part PLAN BOXES
    moved OTHH's corpus by −1.1 % and left shapeID 1878 untouched).

    Falls back to the plan box when no triangle qualifies: a request
    must never lose its geometry, and the plan box is what it always
    was.
    """
    ceiling = measurement.base_y + band_metres
    groups: list[tuple[tuple[float, float], ...]] = []
    for triangle in measurement.triangles:
        vertices = [frame.shared_vertices[index] for index in triangle]
        if any(vertex[1] > ceiling for vertex in vertices):
            continue
        points = []
        for vertex in vertices:
            latitude, longitude = _pool_frame_to_world_point(
                frame.origin_latitude,
                frame.origin_longitude,
                vertex[0],
                vertex[2],
            )
            points.append((longitude, latitude))
        groups.append(tuple(points))
    if groups:
        return groups
    return [tuple(_plan_box_corners_lonlat(frame, measurement))]


def _plan_box_corners_lonlat(
    frame: _PoolFrame,
    measurement: _PartMeasurement,
) -> list[tuple[float, float]]:
    """The part's plan-box corners in ``(lon, lat)`` — the request's
    durable audit trail (and the pre-v2b contact geometry)."""
    box = measurement.plan_box
    corners = []
    for corner_x, corner_z in (
        (box[0], box[2]),
        (box[1], box[2]),
        (box[1], box[3]),
        (box[0], box[3]),
    ):
        latitude, longitude = _pool_frame_to_world_point(
            frame.origin_latitude,
            frame.origin_longitude,
            corner_x,
            corner_z,
        )
        corners.append((longitude, latitude))
    return corners


def _raise_cluster_pad_requests(
    *,
    cluster: _SeatCluster,
    structure_index: int,
    partition,
    measurement_by_key: dict[int, _PartMeasurement],
    frame: _PoolFrame,
    cluster_pad_requests: list[ClusterPadRequest],
    pad_residual_metres: float,
    pad_maximum_relief_metres: float,
    anchor_ground_by_resource: dict[str, float],
    seated: bool = True,
) -> None:
    """One ``ClusterPadRequest`` per maximal connected group of the
    cluster's still-unseated ground parts (spec section 5.3).

    The pad target under a group is the median of its parts' rendered
    bases — the same robust statistic the seat uses, so the pad asks
    terrain for the least it can.  A group whose required relief exceeds
    ``DSF_OBJECT_PAD_MAX_RELIEF_M`` is still recorded, flagged
    ``over_relief_cap``: the pad law (spec section 5.1 clause 1) refuses
    to promise that much terrain movement, and an unrecorded residual is
    exactly the blindness that spec set out to remove.

    ``seated`` selects which base the terrain is asked to meet, which is
    the whole difference between the two callers (reseat-threshold spec
    section 2.2):

    * ``True`` — the cluster BAKED, so its parts are rendered at
      ``cluster_ground + base_y(p)`` and the pads serve the post-seat
      residue (floor ``DSF_OBJECT_FOOT_PAD_RESIDUAL_M``).
    * ``False`` — the cluster stays at its AUTHORED elevations (below the
      reseat threshold, or a measure-only run), so its parts are
      rendered at ``anchor_ground(O) + base_y(p)`` — the unbaked,
      as-draped base — and terrain is what moves (floor
      ``DSF_OBJECT_NOBAKE_PAD_FLOOR_M``).  A part whose resource has no
      anchor ground is not rendered at any known elevation and raises
      nothing (invariant I-13).
    """
    from . import object_clusters

    def _rendered_ground(measurement: _PartMeasurement) -> float | None:
        if seated:
            return cluster.ground_metres
        return anchor_ground_by_resource.get(measurement.base_resource)

    residual_by_key: dict[int, float] = {}
    ground_by_key: dict[int, float] = {}
    for key in cluster.ground_keys:
        measurement = measurement_by_key[key]
        rendered_ground = _rendered_ground(measurement)
        if rendered_ground is None:
            continue
        ground_by_key[key] = rendered_ground
        residual = (
            rendered_ground + measurement.base_y - measurement.ground_metres
        )
        if abs(residual) > pad_residual_metres:
            residual_by_key[key] = residual
    if not residual_by_key:
        return
    for group_keys in object_clusters.residual_part_groups(
        cluster.ground_keys, partition.kept_edges, set(residual_by_key)
    ):
        worst_key = max(
            group_keys, key=lambda key: (abs(residual_by_key[key]), key)
        )
        worst = measurement_by_key[worst_key]
        target_ground_metres = _median(
            [
                ground_by_key[key] + measurement_by_key[key].base_y
                for key in group_keys
            ]
        )
        # THE RING LAW'S INPUT (§2.5 v2b): each part's ground-contact
        # TRIANGLES, one group per triangle, never the pooled points and
        # never the plan box — per-part boxes are the mechanism the
        # replay falsified.  ``contact_points_lonlat`` keeps carrying the
        # plan-box corners: it is the run record's audit trail and the
        # extent the ungrouped fallback uses, and nothing derives a ring
        # from it any more.
        from .config import DSF_OBJECT_FOOT_BAND_M

        contact_points_lonlat: list[tuple[float, float]] = []
        contact_parts_lonlat: list[tuple[tuple[float, float], ...]] = []
        for key in group_keys:
            measurement = measurement_by_key[key]
            contact_points_lonlat.extend(
                _plan_box_corners_lonlat(frame, measurement)
            )
            contact_parts_lonlat.extend(
                _contact_band_triangles_lonlat(
                    frame, measurement, DSF_OBJECT_FOOT_BAND_M
                )
            )
        cluster_pad_requests.append(
            ClusterPadRequest(
                structure_index=structure_index,
                cluster_id=cluster.cluster_id,
                resource_path=worst.base_resource,
                latitude=worst.latitude,
                longitude=worst.longitude,
                base_y=worst.base_y,
                residual_metres=residual_by_key[worst_key],
                target_ground_metres=target_ground_metres,
                contact_points_lonlat=tuple(contact_points_lonlat),
                contact_parts_lonlat=tuple(contact_parts_lonlat),
                part_count=len(group_keys),
                over_relief_cap=(
                    abs(residual_by_key[worst_key])
                    > pad_maximum_relief_metres
                ),
            )
        )


def _raise_foot_pad_requests(
    *,
    feet: tuple[FootCluster, ...],
    structure_index: int,
    frame: _PoolFrame,
    foot_pad_requests: list[FootPadRequest],
    seat_ground_metres: float | None,
    anchor_ground_by_resource: dict[str, float],
    pad_residual_metres: float,
) -> None:
    """One ``FootPadRequest`` per foot the structure's elevation still
    leaves off the mesh — the ground under that foot, not the object, is
    what has to move.

    ``seat_ground_metres`` is the elevation of the object's y = 0 plane
    once the decision is applied: the fitted rigid offset for a structure
    that BAKES, and ``None`` for one that stays at its AUTHORED
    elevations (below the reseat threshold, or a measure-only run —
    reseat-threshold spec section 2.2), where each foot is rendered at
    its own resource's anchor ground instead.  A foot whose resource has
    no anchor ground is not rendered at any known elevation and raises
    nothing (invariant I-13).
    """
    for foot in feet:
        rendered_ground = (
            seat_ground_metres
            if seat_ground_metres is not None
            else anchor_ground_by_resource.get(foot.base_resource)
        )
        if rendered_ground is None or foot.ground_metres is None:
            continue
        residual_metres = (
            rendered_ground + foot.base_y - foot.ground_metres
        )
        if abs(residual_metres) <= pad_residual_metres:
            continue
        # A FOOT IS ONE CONTACT PART (``detect_foot_clusters`` unions its
        # vertices by proximity, so the cluster is compact by
        # construction): the §2.5 union law over a single part is that
        # part's own hull, and the foot ring is unchanged.  Grouped
        # anyway so both paths reach the ring builder the same way.
        contact_points_lonlat = tuple(
            _pool_frame_to_world_point(
                frame.origin_latitude,
                frame.origin_longitude,
                contact_x,
                contact_z,
            )[::-1]
            for contact_x, contact_z in foot.contact_points
        )
        foot_pad_requests.append(
            FootPadRequest(
                structure_index=structure_index,
                resource_path=foot.base_resource,
                latitude=foot.latitude,
                longitude=foot.longitude,
                base_y=foot.base_y,
                residual_metres=residual_metres,
                target_ground_metres=rendered_ground + foot.base_y,
                contact_points_lonlat=contact_points_lonlat,
                contact_parts_lonlat=(contact_points_lonlat,),
            )
        )


def structure_deltas(
    pool: ObjectPool,
    geometry_by_resource: dict[str, ObjectGeometry],
    structures: list[Structure],
    sampler: MeshElevationSampler,
    *,
    measure_only: bool = False,
) -> RebakeDecision:
    """Compute per-(structure, object) y offsets against the built mesh.

    Per structure: sample ``ground_under(centroid)``; on an
    outside-the-mesh sample skip-and-report, never guess (invariant
    I-13).  Each placement's anchor is sampled once; an anchor outside
    the mesh skips every structure touching that object.  A structure
    with no ground-touching part inherits its supporter's ground
    (invariant I-8): the ground-touching structure whose horizontal
    bounding box (pool frame) contains its centroid — the SMALLEST such
    box, ties by lowest structure index
    (``DSF_OBJECT_SUPPORTER_SMALLEST``, defect B: the pre-fix
    first-in-index-order choice handed 8,102 HECA inheritors to a
    1237 x 2480 m mega-structure, 1,761 of them over a smaller
    containing supporter) — else the nearest by centroid distance;
    ``inherited_from_structure_index`` records it (an index into the
    returned ``structures`` list, which preserves the caller's order).

    ``ground_span_metres`` is the max−min of ``ground_under`` over the
    structure's ground-touching parts' centroids; a part centroid
    outside the mesh borrows the structure centroid's ground (noted, not
    fatal).  ``needs_pad`` flags a span past
    ``DSF_OBJECT_PAD_FLAG_SPAN_M`` — the structure is STILL baked with
    the best single offset (amendment A3).  The only do-not-bake case is
    arithmetic: over the ground-touching parts, if the mean corrected
    residual ``|ground(anchor) + base_y + delta − ground(part)|``
    exceeds the mean uncorrected residual
    ``|ground(anchor) + base_y − ground(part)|``, correction would
    worsen the seating and the structure is skipped with both numbers in
    ``skip_reason``.  A skip is per STRUCTURE, never per resource
    (amendment A21): a resource whose other structures pass still bakes
    those structures' deltas, and only lands in ``skipped`` when every
    structure carrying it was skipped.

    Foot re-anchor (``DSF_OBJECT_FOOT_ANCHOR``, project memory
    kbna-gantry-pond-multi-foot-objects): a structure the absolute
    elevated test classifies as clutter, but whose lowest band IS its
    own object's lowest band, carries an author-BAKED vertical offset.
    Unless every detected foot sits over a ground-touching supporter
    (genuine baked rooftop clutter — inheritance stands), the structure
    is FOOT-ANCHORED: its ground records are its feet
    (:func:`detect_foot_clusters`), and the seating elevation is the
    midpoint of the kept per-foot seat targets ``ground(foot) −
    base_y(foot)`` — the rigid offset minimising the worst foot
    residual across feet whose authored bases differ.  Detected feet
    land in ``RebakeDecision.foot_clusters_by_structure_index`` (the
    audit trail); feet the rigid offset cannot seat raise
    ``RebakeDecision.foot_pad_requests``.

    Supporter FATE (``DSF_OBJECT_SUPPORTER_FATE``, HECA 2026-07-26): an
    inheritor is only correct while its supporter actually moves to the
    inherited ground.  A supporter left at its authored elevations (the
    rigid-seat span limit, the A3 guard, anything) that still hands its
    ground to its inheritors tears them off it — 8,102 HECA structures
    baked −2.00…−2.45 m relative to a mega-structure that never budged.
    So an inheritor SHARES ITS SUPPORTER'S FATE: skipped supporter ⇒
    skipped inheritor, ``skip_reason`` opening with
    :data:`SUPPORTER_FATE_SKIP_REASON_PHRASE` and quoting the parent's
    reason.  This is why pass 3 below evaluates supporters BEFORE their
    inheritors; with the gate off it runs in plain index order and every
    byte is as it was.

    THE RESEAT THRESHOLD (``DSF_OBJECT_BAKE_MIN_DELTA_M``,
    docs/specs/object-reseat-threshold-spec.md section 2.1, owner charter
    2026-08-09): a seating unit — a cluster, a structure, a foot-anchored
    structure's fitted rigid offset — bakes only when
    ``max |delta(unit, O)|`` over its resources REACHES the threshold.
    Under it the pack is left exactly as its author shipped it (no
    backup, no provenance, no write) and the unit's ground contacts are
    routed to the pad system instead, so the terrain comes to the
    building: ``skip_reason`` opens with
    :data:`BELOW_BAKE_THRESHOLD_SKIP_REASON_PHRASE` and carries the
    measured max |delta|.  The test runs BEFORE the A3 arithmetic (it is
    cheaper, and A3 only ever governed units that bake) and AFTER the
    kind-based exclusions and the rigid-seat span limit, which are
    unchanged.  Supporter fate is unchanged and applies: the inheritors
    of a below-threshold unit stay at authored elevations with it.

    ``measure_only`` (the tile's ``modify_custom_airports`` switch turned
    off, spec section 2.3) routes EVERY unit as if it were below the
    threshold: the decision carries no deltas at all, so nothing is
    written to the pack, while the pad requests are still raised and
    ``object_rebake.apply``'s reversion pass still restores any earlier
    bake to its authored bytes.  The flag gates pack modification, not
    terrain.

    Positional commands and ``ANIM`` handling are workstream W5's
    concern, not this function's.
    """
    from .config import (
        DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M,
        DSF_OBJECT_BAKE_MIN_DELTA_M,
        DSF_OBJECT_NOBAKE_PAD_FLOOR_M,
        DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M,
        DSF_OBJECT_CLUSTER_SEATING,
        DSF_OBJECT_ELEVATED_BASE_M,
        DSF_OBJECT_PAD_MAX_RELIEF_M,
        DSF_OBJECT_SUPPORTER_FATE,
        DSF_OBJECT_SUPPORTER_SMALLEST,
        DSF_OBJECT_FOOT_ANCHOR,
        DSF_OBJECT_FOOT_BAND_M,
        DSF_OBJECT_FOOT_CLUSTER_GAP_M,
        DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M,
        DSF_OBJECT_FOOT_MAX_BASE_SPREAD_M,
        DSF_OBJECT_FOOT_PAD_RESIDUAL_M,
        DSF_OBJECT_PAD_FLAG_SPAN_M,
    )

    # Measure-only (spec section 2.3) is exactly "no correction is ever
    # large enough to justify touching the pack": one threshold value
    # expresses it, so the routing below has a single law and no second
    # branch that could drift from it.
    bake_minimum_delta_metres = (
        math.inf if measure_only else DSF_OBJECT_BAKE_MIN_DELTA_M
    )

    frame = _build_pool_frame(pool, geometry_by_resource)

    skipped: list[tuple[str, str]] = []
    unusable_reason_by_resource: dict[str, str] = {}
    for resource_path, reason in frame.excluded_resources:
        unusable_reason_by_resource[resource_path] = reason
        if "invariant I-9" in reason:
            # The un-correctable mixed draped/solid case is a real
            # refusal and part of the audit trail; geometry that is
            # merely absent or empty never needed correcting.
            skipped.append((resource_path, reason))

    # Anchor grounds: one sample per placement.  An anchor outside the
    # mesh poisons every structure touching that object (invariant I-13).
    placement_by_resource = {
        placement.resource_path: placement for placement in pool.placements
    }
    anchor_ground_by_resource: dict[str, float] = {}
    for resource_path in frame.included_resources:
        placement = placement_by_resource[resource_path]
        anchor_ground = sampler.elevation_at_or_none(
            placement.latitude, placement.longitude
        )
        if anchor_ground is None:
            reason = (
                f"anchor ({placement.latitude:.6f}, "
                f"{placement.longitude:.6f}) lies outside the built mesh "
                "— skipped, never nearest-vertex sampled (invariant I-13)"
            )
            unusable_reason_by_resource[resource_path] = reason
            skipped.append((resource_path, reason))
        else:
            # Amendment A18: an OBJECT_AGL placement puts the object's
            # ``y = 0`` plane at ``terrain(anchor) + elevation``, so the
            # effective anchor elevation carries the offset (zero for a
            # plain ``OBJECT``).  Everything downstream — deltas, the
            # rendered-elevation identity, provenance — uses this sum.
            anchor_ground_by_resource[resource_path] = (
                anchor_ground + placement.above_ground_level_metres
            )

    # Per-structure pool-frame geometry: shared-index triangles, the
    # horizontal bounding box, and the frame-coordinate centroid.
    shared_triangles_by_structure: list[list[Triangle]] = []
    bounding_box_by_structure: list[
        tuple[float, float, float, float] | None
    ] = []
    frame_centroid_by_structure: list[tuple[float, float]] = []
    for structure in structures:
        structure_shared_triangles: list[Triangle] = []
        for resource_path, triangles in (
            structure.triangles_by_resource.items()
        ):
            base_offset = frame.base_offset_by_resource.get(resource_path)
            if base_offset is None:
                continue  # excluded object; the skip pass below handles it
            structure_shared_triangles.extend(
                (
                    first_index + base_offset,
                    second_index + base_offset,
                    third_index + base_offset,
                )
                for first_index, second_index, third_index in triangles
            )
        shared_triangles_by_structure.append(structure_shared_triangles)
        if structure_shared_triangles:
            bounding_box_by_structure.append(
                obj8_reader.horizontal_bounding_box(
                    frame.shared_vertices, structure_shared_triangles
                )
            )
        else:
            bounding_box_by_structure.append(None)
        frame_centroid_by_structure.append(
            _world_point_to_pool_frame(
                frame.origin_latitude,
                frame.origin_longitude,
                structure.centroid_latitude,
                structure.centroid_longitude,
            )
        )

    # Pass 1 — structure grounds and the unconditional skips.
    skip_reason_by_index: dict[int, str] = {}
    ground_by_index: dict[int, float] = {}
    for structure_index, structure in enumerate(structures):
        blocking_resource = None
        for resource_path in structure.triangles_by_resource:
            if resource_path in unusable_reason_by_resource:
                blocking_resource = resource_path
                break
            if resource_path not in frame.base_offset_by_resource:
                blocking_resource = resource_path
                unusable_reason_by_resource[resource_path] = (
                    "resource is not part of this pool's frame"
                )
                break
        if blocking_resource is not None:
            skip_reason_by_index[structure_index] = (
                f"object {blocking_resource} is unusable: "
                f"{unusable_reason_by_resource[blocking_resource]}"
            )
            continue
        centroid_ground = sampler.elevation_at_or_none(
            structure.centroid_latitude, structure.centroid_longitude
        )
        if centroid_ground is None:
            skip_reason_by_index[structure_index] = (
                f"structure centroid ({structure.centroid_latitude:.6f}, "
                f"{structure.centroid_longitude:.6f}) lies outside the "
                "built mesh — skipped, never nearest-vertex sampled "
                "(invariant I-13)"
            )
            continue
        ground_by_index[structure_index] = centroid_ground

    # Foot re-anchor pre-pass (project memory
    # kbna-gantry-pond-multi-foot-objects): a structure classified as
    # elevated whose lowest band IS its own object's lowest band carries
    # an author-BAKED vertical offset — the KBNA 45 m stair's lowest
    # solid vertex sits at authored y = +6.5 m.  Such a structure never
    # rests on a sibling structure the way rooftop clutter does; its
    # feet were authored for TERRAIN.  Detect the feet here; pass 2
    # decides between inheritance (all feet over a supporter — genuine
    # baked rooftop clutter) and foot-anchoring (pass 3 seats the best
    # rigid offset across the feet).
    foot_candidate_by_index: dict[int, list[FootCluster]] = {}
    if DSF_OBJECT_FOOT_ANCHOR:
        resource_minimum_solid_y: dict[str, float] = {}
        for resource_path in frame.included_resources:
            geometry = geometry_by_resource[resource_path]
            resource_minimum_solid_y[resource_path] = min(
                geometry.vertices[vertex_index][1]
                for triangle in geometry.solid_triangles
                for vertex_index in triangle
            )
        for structure_index, structure in enumerate(structures):
            if (
                structure_index in skip_reason_by_index
                or structure.is_ground_touching
            ):
                continue
            sits_at_own_lowest_band = any(
                resource_path in resource_minimum_solid_y
                and structure_minimum_base_y
                <= resource_minimum_solid_y[resource_path]
                + DSF_OBJECT_ELEVATED_BASE_M
                for resource_path, structure_minimum_base_y in (
                    structure.minimum_base_y_by_resource.items()
                )
            )
            if not sits_at_own_lowest_band:
                continue
            structure_shared_triangles = shared_triangles_by_structure[
                structure_index
            ]
            used_shared_indices = sorted({
                shared_index
                for triangle in structure_shared_triangles
                for shared_index in triangle
            })
            feet = detect_foot_clusters(
                [
                    frame.shared_vertices[shared_index]
                    for shared_index in used_shared_indices
                ],
                [
                    frame.resource_of_shared_vertex[shared_index]
                    for shared_index in used_shared_indices
                ],
                band_metres=DSF_OBJECT_FOOT_BAND_M,
                cluster_gap_metres=DSF_OBJECT_FOOT_CLUSTER_GAP_M,
                maximum_base_spread_metres=(
                    DSF_OBJECT_FOOT_MAX_BASE_SPREAD_M
                ),
            )
            if feet:
                foot_candidate_by_index[structure_index] = feet

    # Pass 2a — CLUSTER FORMATION (DSF_OBJECT_CLUSTER_SEATING; per-cluster
    # seating spec sections 3.2 and 4.2).  A payware pack welds its whole
    # terminal complex into one contact component; on flat ground that is
    # harmless, on 26 m of real relief (HECA) no rigid body can seat it
    # and the whole complex — plus everything inheriting from it — stays
    # at authored elevations.  So: measure every ground part FIRST, cut
    # the ground-to-ground contact edges whose ends want seats more than
    # T apart, and seat the resulting clusters independently.  This runs
    # before pass 2 because inheritance re-points at supporter CLUSTERS
    # (spec section 4.2b), which do not exist until here.
    #
    # With the gate off, nothing below runs and pass 3 measures its parts
    # inline exactly as it always did.
    cluster_seating = (
        DSF_OBJECT_CLUSTER_SEATING
        and DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M > 0.0
    )
    measurements_by_index: dict[int, list[_PartMeasurement]] = {}
    clusters_by_index: dict[int, list[_SeatCluster]] = {}
    cluster_partition_by_index: dict[int, object] = {}
    unthreaded_structures = 0
    if cluster_seating:
        from . import object_clusters

        for structure_index, structure in enumerate(structures):
            if (
                structure_index in skip_reason_by_index
                or not structure.is_ground_touching
                or structure_index not in ground_by_index
            ):
                continue
            structure_shared_triangles = shared_triangles_by_structure[
                structure_index
            ]
            if not structure_shared_triangles:
                continue
            measurements = _measure_structure_parts(
                frame,
                sampler,
                structure_shared_triangles,
                ground_by_index[structure_index],
                DSF_OBJECT_ELEVATED_BASE_M,
                for_clustering=True,
            )
            measurements_by_index[structure_index] = measurements
            if len(measurements) > 1 and not structure.contact_edges:
                # Edges unavailable (hand-built structure, pre-clustering
                # partition cache, connector-split group): merge on doubt
                # — this structure keeps the per-STRUCTURE rigid seat.
                unthreaded_structures += 1
                del measurements_by_index[structure_index]
                continue
            partition = object_clusters.form_clusters(
                [
                    object_clusters.ClusterPart(
                        key=measurement.key,
                        is_ground=measurement.is_ground,
                        base_y=measurement.base_y,
                        ground_metres=measurement.ground_metres,
                        ground_measured=measurement.ground_measured,
                    )
                    for measurement in measurements
                ],
                structure.contact_edges,
                DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M,
            )
            clusters = _build_structure_clusters(
                measurements,
                partition,
                bounding_box_by_structure[structure_index],
                frame_centroid_by_structure[structure_index],
            )
            if not clusters:
                # No ground cluster at all (nothing the cut law can seat
                # on): keep the per-STRUCTURE path rather than silently
                # leaving every part delta-less.
                del measurements_by_index[structure_index]
                continue
            cluster_partition_by_index[structure_index] = partition
            clusters_by_index[structure_index] = clusters
        if unthreaded_structures:
            import O4_UI_Utils as UI

            UI.vprint(
                2,
                f"   [object-anchor] {unthreaded_structures} structure(s) "
                "carry no threaded contact edges (connector-split or "
                "cached pre-clustering partition) — per-structure rigid "
                "seat kept for them",
            )

    # Pass 2 — inheritance for structures with no ground-touching part
    # (invariant I-8).  Supporters are ground-touching structures with a
    # valid ground sample; containment wins over distance.  Among the
    # CONTAINING candidates the supporter is the smallest plan box, ties
    # by lowest structure index (``DSF_OBJECT_SUPPORTER_SMALLEST``,
    # defect B); with the gate off it is the first containing candidate
    # in structure-index order, exactly as before.
    #
    # With per-cluster seating on, the candidates are supporter CLUSTERS
    # (spec section 4.2b): the same smallest-containing rule applied to
    # cluster plan boxes, so an inheritor hovering over one terminal zone
    # follows THAT zone's seat and fate instead of the mega-structure's.
    supporter_indices = [
        structure_index
        for structure_index, structure in enumerate(structures)
        if structure.is_ground_touching
        and structure_index in ground_by_index
    ]
    supporter_index_grid = (
        _build_supporter_index(supporter_indices, bounding_box_by_structure)
        if DSF_OBJECT_SUPPORTER_SMALLEST and supporter_indices
        else None
    )
    # Cluster-granular candidate list: entry i is (structure index,
    # cluster id) and ``cluster_candidate_boxes[i]`` its plan box, so the
    # existing smallest-containing machinery works unchanged over
    # clusters.  A ground-touching structure with no cluster set (edges
    # unthreaded) contributes its whole-structure box, keeping it a
    # legitimate supporter.
    cluster_candidates: list[tuple[int, int]] = []
    cluster_candidate_boxes: list[
        tuple[float, float, float, float] | None
    ] = []
    cluster_candidate_centroids: list[tuple[float, float]] = []
    if cluster_seating:
        for structure_index in supporter_indices:
            clusters = clusters_by_index.get(structure_index)
            if clusters is None:
                cluster_candidates.append((structure_index, -1))
                cluster_candidate_boxes.append(
                    bounding_box_by_structure[structure_index]
                )
                cluster_candidate_centroids.append(
                    frame_centroid_by_structure[structure_index]
                )
                continue
            for cluster in clusters:
                cluster_candidates.append(
                    (structure_index, cluster.cluster_id)
                )
                cluster_candidate_boxes.append(cluster.box)
                cluster_candidate_centroids.append(
                    (cluster.centroid_x, cluster.centroid_z)
                )
    cluster_candidate_grid = (
        _build_supporter_index(
            list(range(len(cluster_candidates))), cluster_candidate_boxes
        )
        if cluster_seating
        and DSF_OBJECT_SUPPORTER_SMALLEST
        and cluster_candidates
        else None
    )
    inherited_from_cluster_by_index: dict[int, tuple[int, int]] = {}
    inherited_from_by_index: dict[int, int] = {}
    foot_anchored_by_index: dict[int, list[FootCluster]] = {}
    for structure_index, structure in enumerate(structures):
        if (
            structure_index in skip_reason_by_index
            or structure.is_ground_touching
        ):
            continue
        feet = foot_candidate_by_index.get(structure_index)
        if feet:
            # Baked rooftop clutter rests ON a sibling: every foot sits
            # over one ground-touching supporter's box, and inheritance
            # (below) remains the correct seating.  Feet over open
            # terrain mean the author baked the offset against THEIR
            # mesh — the structure is foot-anchored and pass 3 fits the
            # rigid offset across its feet instead.
            supported = any(
                bounding_box_by_structure[candidate_index] is not None
                and all(
                    bounding_box_by_structure[candidate_index][0]
                    <= foot.centroid_x
                    <= bounding_box_by_structure[candidate_index][1]
                    and bounding_box_by_structure[candidate_index][2]
                    <= foot.centroid_z
                    <= bounding_box_by_structure[candidate_index][3]
                    for foot in feet
                )
                for candidate_index in supporter_indices
            )
            if not supported:
                foot_anchored_by_index[structure_index] = feet
                continue
        centroid_x, centroid_z = frame_centroid_by_structure[structure_index]
        if cluster_seating and cluster_candidates:
            # Supporter CLUSTER (spec section 4.2b): identical rule, one
            # level finer — smallest containing cluster box, else the
            # nearest cluster centroid.
            candidate_position = None
            if cluster_candidate_grid is not None:
                candidate_position = _smallest_containing_supporter_index(
                    cluster_candidate_grid,
                    cluster_candidate_boxes,
                    centroid_x,
                    centroid_z,
                )
            else:
                for position, box in enumerate(cluster_candidate_boxes):
                    if box is None:
                        continue
                    if (
                        box[0] <= centroid_x <= box[1]
                        and box[2] <= centroid_z <= box[3]
                    ):
                        candidate_position = position
                        break
            if candidate_position is None:
                candidate_position = min(
                    range(len(cluster_candidates)),
                    key=lambda position: (
                        math.hypot(
                            cluster_candidate_centroids[position][0]
                            - centroid_x,
                            cluster_candidate_centroids[position][1]
                            - centroid_z,
                        ),
                        position,
                    ),
                )
            supporter_index, supporter_cluster_id = cluster_candidates[
                candidate_position
            ]
            inherited_from_by_index[structure_index] = supporter_index
            inherited_from_cluster_by_index[structure_index] = (
                supporter_index,
                supporter_cluster_id,
            )
            if supporter_cluster_id < 0:
                ground_by_index[structure_index] = ground_by_index[
                    supporter_index
                ]
            else:
                ground_by_index[structure_index] = clusters_by_index[
                    supporter_index
                ][supporter_cluster_id].ground_metres
            continue
        supporter_index = None
        if supporter_index_grid is not None:
            supporter_index = _smallest_containing_supporter_index(
                supporter_index_grid,
                bounding_box_by_structure,
                centroid_x,
                centroid_z,
            )
        else:
            for candidate_index in supporter_indices:
                candidate_box = bounding_box_by_structure[candidate_index]
                if candidate_box is None:
                    continue
                minimum_x, maximum_x, minimum_z, maximum_z = candidate_box
                if (
                    minimum_x <= centroid_x <= maximum_x
                    and minimum_z <= centroid_z <= maximum_z
                ):
                    supporter_index = candidate_index
                    break
        if supporter_index is None and supporter_indices:
            supporter_index = min(
                supporter_indices,
                key=lambda candidate_index: math.hypot(
                    frame_centroid_by_structure[candidate_index][0]
                    - centroid_x,
                    frame_centroid_by_structure[candidate_index][1]
                    - centroid_z,
                ),
            )
        if supporter_index is None:
            skip_reason_by_index[structure_index] = (
                "no ground-touching part, and no ground-touching "
                "supporter structure with a valid mesh sample to inherit "
                "from (invariant I-8)"
            )
            continue
        inherited_from_by_index[structure_index] = supporter_index
        ground_by_index[structure_index] = ground_by_index[supporter_index]

    # Pass 3 — ground span, the amendment-A3 residual arithmetic, and the
    # per-(structure, object) deltas (spec section 2.4, invariant I-3).
    #
    # SUPPORTERS FIRST (``DSF_OBJECT_SUPPORTER_FATE``): an inheritor may
    # only bake if the supporter it took its ground from is itself going
    # to move, and that is decided right here — so every non-inheritor
    # (which is every possible supporter: pass 2 only ever inherits from
    # a ground-touching structure, and a ground-touching structure never
    # inherits) is evaluated before the first inheritor.  Results land in
    # ``updated_by_index`` and are re-serialised in index order at the
    # end, so the returned list still matches ``structures`` positionally
    # whichever order the work happened in.  With the gate off the order
    # is plain ``enumerate`` and nothing below changes at all.
    updated_by_index: dict[int, Structure] = {}
    delta_by_resource_and_vertex: dict[str, dict[int, float]] = {}
    foot_clusters_by_structure_index: dict[int, tuple[FootCluster, ...]] = {}
    foot_pad_requests: list[FootPadRequest] = []
    cluster_pad_requests: list[ClusterPadRequest] = []
    cluster_seams: list[ClusterSeam] = []
    clusters_seen = 0
    clusters_baked = 0
    clusters_refused = 0
    clusters_below_threshold = 0
    if DSF_OBJECT_SUPPORTER_FATE:
        processing_order = sorted(
            range(len(structures)),
            key=lambda index: (index in inherited_from_by_index, index),
        )
    else:
        processing_order = list(range(len(structures)))
    for structure_index in processing_order:
        structure = structures[structure_index]
        if structure_index in skip_reason_by_index:
            updated_by_index[structure_index] = replace(
                structure,
                skip_reason=skip_reason_by_index[structure_index],
            )
            continue
        structure_ground = ground_by_index[structure_index]

        # Supporter fate.  The supporter has already been evaluated (see
        # the processing order above); if it was skipped it stayed at its
        # authored elevations, and the ground this structure inherited
        # from it describes a seat that no longer exists.
        supporter_index = inherited_from_by_index.get(structure_index)
        if DSF_OBJECT_SUPPORTER_FATE and supporter_index is not None:
            supporter_cluster = inherited_from_cluster_by_index.get(
                structure_index
            )
            supporter_skip_reason = (
                updated_by_index[supporter_index].skip_reason
                if supporter_index in updated_by_index
                else None
            )
            if (
                supporter_skip_reason is None
                and supporter_cluster is not None
                and supporter_cluster[1] >= 0
                and supporter_index in clusters_by_index
            ):
                # Per-cluster fate (spec section 4.2b): the inheritor
                # follows the CLUSTER it hovers over, not the whole
                # mega-structure — which is the HECA payoff line.  The
                # supporter has already been evaluated (processing order),
                # so its clusters carry their outcomes.
                supporter_skip_reason = clusters_by_index[supporter_index][
                    supporter_cluster[1]
                ].skip_reason
            if supporter_skip_reason:
                # NOTE (measured 2026-07-26, and deliberately NOT done):
                # pass 2's foot-candidate ``supported`` test also counts
                # skipped supporters, which is why HECA detects zero
                # foot-anchored structures.  Making it ignore them is
                # WRONG: a skipped supporter is still physically there,
                # at its authored elevations, and the clutter still
                # rests on it.  Re-routing those candidates to the
                # per-foot path seats them on TERRAIN — measured at
                # HECA it dropped 80 structures by 4.3 m to 25.7 m
                # (``T23/yellow_metal.obj``, authored base y = +19.7 m,
                # would have fallen from the terminal roof to the
                # apron), and 33 more at EGGW.  Leaving them at their
                # authored elevations with their supporter is the
                # correct outcome; re-homing them needs the
                # supporter-bbox size gate, which is separate future
                # work.
                updated_by_index[structure_index] = replace(
                    structure,
                    # No ground-touching part of its own, hence no
                    # ground span (the value a baked inheritor gets).
                    ground_span_metres=0.0,
                    needs_pad=False,
                    inherited_from_structure_index=supporter_index,
                    skip_reason=(
                        f"{SUPPORTER_FATE_SKIP_REASON_PHRASE} "
                        f"({supporter_skip_reason}) — this structure "
                        "inherits that supporter's ground (invariant "
                        "I-8) and must share its fate; left at "
                        "authored elevations"
                    ),
                )
                continue

        anchored_feet = foot_anchored_by_index.get(structure_index)
        if anchored_feet is not None:
            # Foot-anchored: one record per FOOT, sampled under the
            # foot's own contact centroid.  A foot centroid off the
            # mesh borrows the structure centroid's ground — noted,
            # not fatal, exactly like a part centroid below.
            enriched_feet: list[FootCluster] = []
            ground_part_records = []
            for foot in anchored_feet:
                foot_latitude, foot_longitude = _pool_frame_to_world_point(
                    frame.origin_latitude,
                    frame.origin_longitude,
                    foot.centroid_x,
                    foot.centroid_z,
                )
                foot_ground = sampler.elevation_at_or_none(
                    foot_latitude, foot_longitude
                )
                if foot_ground is None:
                    import O4_UI_Utils as UI

                    UI.vprint(
                        2,
                        "  [object-anchor] foot centroid "
                        f"({foot_latitude:.6f}, {foot_longitude:.6f}) "
                        "lies outside the built mesh; using the "
                        "structure centroid's ground for it",
                    )
                    foot_ground = structure_ground
                enriched_feet.append(
                    replace(
                        foot,
                        latitude=foot_latitude,
                        longitude=foot_longitude,
                        ground_metres=foot_ground,
                    )
                )
                ground_part_records.append(
                    (foot_ground, foot.base_y, foot.base_resource)
                )
        else:
            enriched_feet = []
            ground_part_records = []

        # PER-CLUSTER SEATING (spec sections 4.1–4.3).  A clustered
        # structure is not one rigid body: each cluster seats on its own
        # median ground, runs the span and A3 gates for itself, and
        # raises its own pad requests.  Handled entirely in the helper
        # below, which then continues the loop.
        if (
            anchored_feet is None
            and structure_index in clusters_by_index
        ):
            clusters = clusters_by_index[structure_index]
            partition = cluster_partition_by_index[structure_index]
            measurements = measurements_by_index[structure_index]
            outcome = _seat_clusters(
                structure=structure,
                structure_index=structure_index,
                clusters=clusters,
                partition=partition,
                measurements=measurements,
                frame=frame,
                anchor_ground_by_resource=anchor_ground_by_resource,
                delta_by_resource_and_vertex=delta_by_resource_and_vertex,
                cluster_pad_requests=cluster_pad_requests,
                cluster_seams=cluster_seams,
                maximum_ground_span_metres=(
                    DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M
                ),
                pad_flag_span_metres=DSF_OBJECT_PAD_FLAG_SPAN_M,
                pad_residual_metres=DSF_OBJECT_FOOT_PAD_RESIDUAL_M,
                pad_maximum_relief_metres=DSF_OBJECT_PAD_MAX_RELIEF_M,
                bake_minimum_delta_metres=bake_minimum_delta_metres,
                nobake_pad_floor_metres=DSF_OBJECT_NOBAKE_PAD_FLOOR_M,
                measure_only=measure_only,
            )
            clusters_seen += len(clusters)
            clusters_baked += outcome[1]
            clusters_refused += outcome[2]
            clusters_below_threshold += outcome[3]
            updated_by_index[structure_index] = outcome[0]
            continue

        # Ground-touching parts, re-derived from the SAME welding the
        # partition used (welding is intra-part, so welding a structure's
        # own triangles reproduces exactly its parts).
        structure_shared_triangles = shared_triangles_by_structure[
            structure_index
        ]
        if structure_shared_triangles and anchored_feet is None:
            for measurement in _measure_structure_parts(
                frame,
                sampler,
                structure_shared_triangles,
                structure_ground,
                DSF_OBJECT_ELEVATED_BASE_M,
            ):
                if not measurement.is_ground:
                    continue
                ground_part_records.append(
                    (
                        measurement.ground_metres,
                        measurement.base_y,
                        measurement.base_resource,
                    )
                )

        if anchored_feet is not None:
            part_grounds = [record[0] for record in ground_part_records]
            ground_span_metres = max(part_grounds) - min(part_grounds)
            # Foot-anchored seating: each foot's SEAT TARGET is the
            # world elevation of the object's y = 0 plane that lands
            # that foot exactly on the mesh (its ground minus its
            # authored base — feet with different authored bases are
            # the whole point).  The rigid offset that minimises the
            # WORST foot residual is the midpoint of the kept targets.
            # A foot whose target fell more than the contact tolerance
            # below the topmost target is excluded from the fit — the
            # body rests on its highest contacts; a cluster hanging
            # over a pond must never drag the true feet down.
            seat_targets = [
                foot_ground - foot_base_y
                for foot_ground, foot_base_y, _resource in (
                    ground_part_records
                )
            ]
            topmost_target = max(seat_targets)
            kept_targets = [
                target
                for target in seat_targets
                if target
                >= topmost_target - DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M
            ]
            structure_ground = (
                min(kept_targets) + max(kept_targets)
            ) / 2.0
            enriched_feet = [
                replace(
                    foot,
                    kept_for_fit=(
                        target
                        >= topmost_target
                        - DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M
                    ),
                    residual_metres=(
                        structure_ground + foot.base_y - foot.ground_metres
                    ),
                )
                for foot, target in zip(enriched_feet, seat_targets)
            ]
            foot_clusters_by_structure_index[structure_index] = tuple(
                enriched_feet
            )
        elif ground_part_records:
            part_grounds = [record[0] for record in ground_part_records]
            ground_span_metres = max(part_grounds) - min(part_grounds)
            # Amendment A19: the seating elevation of a structure with
            # ground-touching parts is the MEDIAN of those parts'
            # grounds — the best single rigid offset — not the ground at
            # the area-weighted centroid, which is one unrepresentative
            # sample for a large structure (a kilometre-wide chained web
            # at HECA was judged, and wrongly skipped, by it).
            structure_ground = _median(part_grounds)
        else:
            ground_span_metres = 0.0
        needs_pad = ground_span_metres > DSF_OBJECT_PAD_FLAG_SPAN_M

        # Rigid-seat span limit (design 2026-07-17, EGGW UK2000 pack): a
        # structure whose ground-contact terrain span exceeds
        # ``DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M`` cannot be seated by one
        # rigid vertical offset — whatever offset the best fit picks,
        # one end floats or sinks past the seating tolerance.  Co-baked
        # payware packs chain real buildings into airport-scale contact
        # components via connector objects; baking one offset for such a
        # component floated the EGGW chains by +33 m and +20 m.  Leave
        # the whole structure at its AUTHORED elevations; its real
        # buildings are carried by their own Phase-1 pads instead.  Feet
        # keep the per-foot machinery below — each foot seats
        # independently, so a large inter-foot span is exactly what that
        # path is for, never a reason to refuse.  A skip is per
        # STRUCTURE: the resource carries no delta, so the byte-idempotent
        # rewrite (and the reversion pass) leave it at its authored y.
        #
        # DEFECT A, MEASURED AND NOT LANDED (2026-07-26).  This test is
        # max−min, and it runs BEFORE the amendment-A3 arithmetic below,
        # so a structure whose median seat would be a large A3
        # improvement is refused unheard — at HECA structure 0 the
        # authored ground-part residuals run at a median of 3.089 m
        # against 0.450 m at the A19 median seat, over 1,821 parts.
        # Replacing the outright skip with "bake when the median seat
        # strictly improves the A3 MEAN" was built and dry-run, and it
        # fails the EGGW stop condition: all three UK2000 over-span
        # components bake, including the 662,669 m² / 9.39 m-span one the
        # owner verified in-sim must skip, which the mean test accepts on
        # a 0.025 m margin while its residual median gets WORSE.  The
        # replacement test has to be one those components fail; see
        # ``DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M`` in config.py for the
        # numbers and docs/specs/per-cluster-object-seating-spec.md for
        # the structural fix.
        if (
            anchored_feet is None
            and ground_span_metres > DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M
        ):
            updated_by_index[structure_index] = replace(
                structure,
                ground_span_metres=ground_span_metres,
                needs_pad=needs_pad,
                skip_reason=(
                    f"ground span {ground_span_metres:.1f} m "
                    f"{GROUND_SPAN_SKIP_REASON_PHRASE} — left at "
                    "authored elevations"
                ),
            )
            continue

        # THE RESEAT THRESHOLD (reseat-threshold spec section 2.1), on
        # the same deltas the bake would write and before the A3
        # arithmetic.  For a foot-anchored structure the unit is its
        # FITTED RIGID OFFSET (``structure_ground`` above), which is the
        # correction the whole gantry would move by.  Under the
        # threshold the pack is not touched at all and the terrain
        # adapts instead (section 2.2), which is the owner's stated
        # preference: an airport whose every unit deviates under a metre
        # ends the run with an untouched pack.
        maximum_delta_metres = _max_abs_delta_metres(
            structure.triangles_by_resource,
            structure_ground,
            anchor_ground_by_resource,
            bake_minimum_delta_metres,
        )
        if maximum_delta_metres < bake_minimum_delta_metres:
            if anchored_feet is not None:
                _raise_foot_pad_requests(
                    feet=foot_clusters_by_structure_index[structure_index],
                    structure_index=structure_index,
                    frame=frame,
                    foot_pad_requests=foot_pad_requests,
                    seat_ground_metres=None,
                    anchor_ground_by_resource=anchor_ground_by_resource,
                    pad_residual_metres=DSF_OBJECT_NOBAKE_PAD_FLOOR_M,
                )
            # Counted per airport by ``post_mesh`` off the stable phrase,
            # the same way the span-limit and supporter-fate skips are.
            updated_by_index[structure_index] = replace(
                structure,
                ground_span_metres=ground_span_metres,
                needs_pad=needs_pad,
                inherited_from_structure_index=inherited_from_by_index.get(
                    structure_index
                ),
                skip_reason=_below_bake_threshold_reason(
                    maximum_delta_metres,
                    bake_minimum_delta_metres,
                    "structure",
                    measure_only=measure_only,
                ),
            )
            continue

        # Amendment A3, bounded by amendment A19: always bake the best
        # single offset; do-not-bake ONLY when the arithmetic says
        # correction worsens the seating AND the structure is small
        # enough for that judgment to be meaningful.  A mega-structure
        # (a chained web) always bakes and flags ``needs_pad`` — its
        # real fix is the hinge cut, never a silent skip.
        a3_skip_reason = None
        bounding_box = bounding_box_by_structure[structure_index]
        structure_diameter_metres = (
            math.hypot(
                bounding_box[1] - bounding_box[0],
                bounding_box[3] - bounding_box[2],
            )
            if bounding_box is not None
            else 0.0
        )
        if ground_part_records and (
            structure_diameter_metres <= A3_GUARD_MAXIMUM_DIAMETER_METRES
        ):
            corrected_residuals = [
                abs(structure_ground + part_base_y - part_ground)
                for part_ground, part_base_y, _base_resource in (
                    ground_part_records
                )
            ]
            uncorrected_residuals = [
                abs(
                    anchor_ground_by_resource[base_resource]
                    + part_base_y
                    - part_ground
                )
                for part_ground, part_base_y, base_resource in (
                    ground_part_records
                )
            ]
            corrected_mean = sum(corrected_residuals) / len(
                corrected_residuals
            )
            uncorrected_mean = sum(uncorrected_residuals) / len(
                uncorrected_residuals
            )
            if corrected_mean > (
                uncorrected_mean + RESIDUAL_COMPARISON_TOLERANCE_METRES
            ):
                a3_skip_reason = (
                    "single-offset correction would worsen the seating: "
                    f"mean ground-part residual {corrected_mean:.3f} m "
                    f"corrected vs {uncorrected_mean:.3f} m uncorrected "
                    f"over {len(ground_part_records)} ground-touching "
                    "part(s) — left unbaked (amendment A3)"
                )
        if a3_skip_reason is not None:
            updated_by_index[structure_index] = replace(
                structure,
                ground_span_metres=ground_span_metres,
                needs_pad=needs_pad,
                skip_reason=a3_skip_reason,
            )
            continue

        # A baked foot-anchored structure whose rigid offset still
        # leaves a foot off the mesh past the residual threshold gets a
        # per-foot terrain-pad REQUEST — the ground under that foot,
        # not the object, is what needs to move (target recorded).
        if anchored_feet is not None:
            _raise_foot_pad_requests(
                feet=foot_clusters_by_structure_index[structure_index],
                structure_index=structure_index,
                frame=frame,
                foot_pad_requests=foot_pad_requests,
                seat_ground_metres=structure_ground,
                anchor_ground_by_resource=anchor_ground_by_resource,
                pad_residual_metres=DSF_OBJECT_FOOT_PAD_RESIDUAL_M,
            )

        # The deltas.  Invariant I-3: per (structure, object) — each
        # resource's offset is measured from ITS OWN anchor's ground.
        for resource_path, triangles in (
            structure.triangles_by_resource.items()
        ):
            delta = (
                structure_ground - anchor_ground_by_resource[resource_path]
            )
            resource_deltas = delta_by_resource_and_vertex.setdefault(
                resource_path, {}
            )
            for triangle in triangles:
                for vertex_index in triangle:
                    resource_deltas[vertex_index] = delta

        updated_by_index[structure_index] = replace(
            structure,
            ground_span_metres=ground_span_metres,
            needs_pad=needs_pad,
            inherited_from_structure_index=inherited_from_by_index.get(
                structure_index
            ),
        )

    if cluster_seating and clusters_seen:
        import O4_UI_Utils as UI

        cut_edge_count = sum(
            len(partition.cut_edges)
            for partition in cluster_partition_by_index.values()
        )
        bridge_count = sum(
            1 for seam in cluster_seams if seam.kind == "bridge"
        )
        UI.vprint(
            1,
            f"   [object-anchor] per-cluster seating: {clusters_seen} "
            f"cluster(s) across {len(clusters_by_index)} structure(s) "
            f"({clusters_baked} seated, {clusters_refused} refused, "
            f"{clusters_below_threshold} under the "
            "DSF_OBJECT_BAKE_MIN_DELTA_M reseat threshold — terrain "
            f"adapts to those) from {cut_edge_count} cut contact "
            f"edge(s); {bridge_count} bridge seam(s) reported, "
            f"{len(cluster_pad_requests)} pad request(s)",
        )
        for seam in cluster_seams:
            if seam.kind != "bridge":
                continue
            UI.vprint(
                2,
                "  [object-anchor] bridge seam: structure "
                f"{seam.structure_index} elevated component "
                f"({seam.part_count} part(s)) joined cluster "
                f"{seam.cluster_id}; residual toward cluster "
                f"{seam.other_cluster_id} is {seam.seam_metres:.2f} m "
                "(reported, never averaged across)",
            )

    # Back to caller order: ``structures[i]`` ↔ ``updated_structures[i]``,
    # whatever order pass 3 evaluated them in.
    updated_structures: list[Structure] = [
        updated_by_index[structure_index]
        for structure_index in range(len(structures))
    ]

    # Amendment A19: structure-level skips must be VISIBLE at the
    # resource level.  Forty-nine HECA resources vanished from the bake
    # because every structure carrying their geometry was skipped and
    # nothing said so.  One aggregated entry per affected resource — but
    # ONLY for resources left with no delta at all (amendment A21): a
    # resource whose OTHER structures baked stays out of ``skipped``
    # (``object_rebake.apply`` refuses everything listed there), bakes
    # the passing structures' deltas, and surfaces its per-structure
    # skips through the report and the provenance sidecar instead.
    skip_count_by_resource: dict[str, int] = {}
    first_skip_reason_by_resource: dict[str, str] = {}
    for updated_structure in updated_structures:
        if not updated_structure.skip_reason:
            continue
        for resource_path in updated_structure.triangles_by_resource:
            skip_count_by_resource[resource_path] = (
                skip_count_by_resource.get(resource_path, 0) + 1
            )
            first_skip_reason_by_resource.setdefault(
                resource_path, updated_structure.skip_reason
            )
    for resource_path in sorted(skip_count_by_resource):
        if resource_path in delta_by_resource_and_vertex:
            continue
        count = skip_count_by_resource[resource_path]
        skipped.append(
            (
                resource_path,
                f"ALL {count} structure(s) carrying this resource "
                "were skipped — resource left unbaked; first reason: "
                + first_skip_reason_by_resource[resource_path],
            )
        )

    return RebakeDecision(
        structures=updated_structures,
        delta_by_resource_and_vertex=delta_by_resource_and_vertex,
        anchor_ground_by_resource=anchor_ground_by_resource,
        skipped=skipped,
        anchor_by_resource={
            resource_path: (
                placement.latitude,
                placement.longitude,
                placement.heading_degrees,
            )
            for resource_path, placement in placement_by_resource.items()
            if resource_path in anchor_ground_by_resource
        },
        foot_clusters_by_structure_index=foot_clusters_by_structure_index,
        foot_pad_requests=foot_pad_requests,
        cluster_pad_requests=cluster_pad_requests,
        cluster_seams=cluster_seams,
        cluster_counts=(
            {
                "structures_clustered": len(clusters_by_index),
                "clusters": clusters_seen,
                "clusters_baked": clusters_baked,
                "clusters_refused": clusters_refused,
                # Not a refusal: the reseat threshold decided the pack
                # should not be modified for these (reseat-threshold
                # spec section 2.1), so they are counted apart from the
                # gate refusals they must never be confused with.
                "clusters_below_threshold": clusters_below_threshold,
                "cut_edges": sum(
                    len(partition.cut_edges)
                    for partition in cluster_partition_by_index.values()
                ),
                "bridge_seams": sum(
                    1 for seam in cluster_seams if seam.kind == "bridge"
                ),
                "structures_unthreaded": unthreaded_structures,
            }
            if cluster_seating
            else {}
        ),
    )
