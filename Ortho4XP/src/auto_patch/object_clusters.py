"""Cluster formation inside a structure — the seat-disagreement cut.

Design: ``docs/specs/per-cluster-object-seating-spec.md`` sections 3.2
(the cut), 3.4 (degenerate handling), 3.5 (determinism) and 4.2 (the
inheritance / bridge rules).  Read section 2 before changing anything
here; the charter change this implements (invariant I-20 becoming
I-20', bounded justified tearing) is the reason the module exists.

The one-paragraph version.  A STRUCTURE is a connected component of the
epsilon-contact graph and stays the unit of pooling, discovery and
provenance.  Within a structure, the ground-to-ground contact edges are
re-examined: an edge whose two ends want rigid seats more than the
tolerance apart is CUT, and the connected components of what remains are
the structure's CLUSTERS — each a rigid body with its own seat.  Elevated
parts never vote on the cut; they are ASSIGNED to a cluster afterwards
and can never merge two clusters (ground truth flows upward only).  An
elevated component touching two or more clusters is a BRIDGE: it joins
its majority-contact cluster and every contact it keeps toward the other
clusters becomes an audited seam, reported and never averaged across.

Everything here is pure integer/float bookkeeping over data the caller
has already measured: no geometry, no mesh sampling, no configuration
(the tolerance arrives as an argument).  ``object_anchor`` owns the
measurement and the seat arithmetic.

PART IDENTITY.  A part is identified by its KEY — the lowest pool-frame
shared vertex index it touches.  Welding is intra-part, so the partition
(which welds the whole pool at once) and ``structure_deltas`` (which
re-welds one structure's triangles) produce the same parts in possibly
different order; the key is the same either way, which is what lets the
contact edges computed during partitioning be threaded through to
seating without recomputing the narrow phase (spec section 3.1).

SPANNING-SUBSET NOTE (deliberate, do not "fix").
``obj8_partition.contact_graph`` returns a connectivity-equivalent
SPANNING subset of the in-contact pairs, not every pair, so every edge
it returns is a bridge of the structure and cutting one always splits.
The measured distribution the tolerance was chosen from (spec section 1)
was taken on exactly that subset, so the cut law is calibrated for it.
The consequence is that two parts in true contact may land in different
clusters when the spanning path between them crossed a cut — each side
still seats on its own measured ground, which is the property that
matters; recovering the full pair set would only ever merge more.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClusterPart:
    """One welded part of a structure, as the cut law sees it.

    ``ground_metres`` is the mesh elevation under the part's centroid
    (ground parts only).  ``ground_measured`` is False when that sample
    fell outside the mesh and the structure centroid's ground was
    borrowed for it — merge-on-doubt survives for UNMEASURED ground
    (spec section 3.2), so such an edge is never cut.
    """

    key: int
    is_ground: bool
    base_y: float
    ground_metres: float | None = None
    ground_measured: bool = True

    @property
    def seat_target_metres(self) -> float | None:
        """``ground_under(p) − base_y(p)`` — the world elevation of the
        object's ``y = 0`` plane that lands this part exactly on the
        mesh (spec section 3.2; the same statistic the foot machinery
        fits)."""
        if self.ground_metres is None:
            return None
        return self.ground_metres - self.base_y


@dataclass(frozen=True)
class CutEdge:
    """A ground-to-ground contact edge the cut law severed, with the
    measured ground step ``g(e)`` that justifies it (the tear audit,
    spec section 4.5, reads this)."""

    left_key: int
    right_key: int
    ground_step_metres: float


@dataclass(frozen=True)
class BridgeSeam:
    """An elevated component contacting more than one cluster (spec
    section 4.2a; HECA's people-mover / road_train rail connector is the
    type specimen).

    The component joins ``cluster_id`` — the cluster it shares the most
    elevated-to-ground contacts with — and this record reports the
    residual toward ``other_cluster_id``, which is REPORTED, never
    averaged across.  ``seam_metres`` is filled by the caller once the
    two cluster seats are known.
    """

    cluster_id: int
    other_cluster_id: int
    contact_count: int
    other_contact_count: int
    part_count: int
    seam_metres: float | None = None


@dataclass(frozen=True)
class ClusterPartition:
    """The result of :func:`form_clusters` for ONE structure."""

    # Every part key of the structure -> its cluster id, except the keys
    # of elevated components that touched no cluster at all (those are
    # in ``unassigned_elevated_components`` for the caller's
    # containment/nearest fallback, spec section 4.2b).
    cluster_id_by_part_key: dict[int, int]
    cluster_count: int
    kept_edges: tuple[tuple[int, int], ...]
    cut_edges: tuple[CutEdge, ...]
    bridge_seams: tuple[BridgeSeam, ...]
    unassigned_elevated_components: tuple[tuple[int, ...], ...]

    @property
    def is_degenerate(self) -> bool:
        """True when nothing was cut — one cluster, identical arithmetic
        to per-structure seating (the KCLT/KBNA guarantee, spec
        section 2)."""
        return not self.cut_edges and self.cluster_count <= 1


def _normalised_edges(
    contact_edges,
    known_keys: set[int],
) -> list[tuple[int, int]]:
    """De-duplicated, orientation-normalised, deterministically ordered
    edges restricted to parts this structure actually has."""
    normalised = {
        (min(left, right), max(left, right))
        for left, right in contact_edges
        if left != right and left in known_keys and right in known_keys
    }
    return sorted(normalised)


class _UnionFind:
    """Union-find over an explicit key list (deterministic: the caller
    supplies the order, and unions run over sorted edges)."""

    def __init__(self, keys: list[int]) -> None:
        self._index_by_key = {key: index for index, key in enumerate(keys)}
        self._parent = list(range(len(keys)))
        self._keys = keys

    def __contains__(self, key: int) -> bool:
        return key in self._index_by_key

    def _find(self, node: int) -> int:
        while self._parent[node] != node:
            self._parent[node] = self._parent[self._parent[node]]
            node = self._parent[node]
        return node

    def union(self, left_key: int, right_key: int) -> None:
        left = self._find(self._index_by_key[left_key])
        right = self._find(self._index_by_key[right_key])
        if left != right:
            self._parent[left] = right

    def root_of(self, key: int) -> int:
        return self._find(self._index_by_key[key])

    def components(self) -> list[list[int]]:
        """Components as key lists, each in the caller's key order,
        ordered by their lowest member key (spec section 3.5)."""
        grouped: dict[int, list[int]] = {}
        for key in self._keys:
            grouped.setdefault(self.root_of(key), []).append(key)
        return sorted(grouped.values(), key=lambda members: min(members))


def form_clusters(
    parts: list[ClusterPart],
    contact_edges,
    tolerance_metres: float,
) -> ClusterPartition:
    """Cut the structure's ground-to-ground contact edges and return its
    clusters (spec sections 3.2 and 4.2a).

    ``parts`` is every welded part of one structure in a deterministic
    order (``object_anchor`` passes weld order); ``contact_edges`` are
    the epsilon-contact edges AMONG those parts as ``(part key, part
    key)`` pairs, threaded through from ``partition_structures``.

        CUT (i, j)  <=>  both ends ground, both grounds MEASURED, and
                         |seat(i) − seat(j)| > tolerance_metres

    Every other edge is kept: elevated ends never vote (they are
    assigned below), and an unmeasured ground keeps its edge — only
    measured divergence tears (invariant I-20').

    A ``tolerance_metres`` of 0 disables the cut entirely, which yields
    exactly one cluster per structure and reproduces per-structure
    seating.
    """
    part_by_key = {part.key: part for part in parts}
    ordered_keys = [part.key for part in parts]
    edges = _normalised_edges(contact_edges, set(ordered_keys))

    ground_keys = [key for key in ordered_keys if part_by_key[key].is_ground]
    elevated_keys = [
        key for key in ordered_keys if not part_by_key[key].is_ground
    ]

    # ── the cut (spec section 3.2) ────────────────────────────────────
    ground_union = _UnionFind(ground_keys)
    kept_edges: list[tuple[int, int]] = []
    cut_edges: list[CutEdge] = []
    for left_key, right_key in edges:
        left, right = part_by_key[left_key], part_by_key[right_key]
        if not (left.is_ground and right.is_ground):
            continue  # an elevated end cannot vote (assigned below)
        left_seat = left.seat_target_metres
        right_seat = right.seat_target_metres
        if (
            tolerance_metres > 0.0
            and left.ground_measured
            and right.ground_measured
            and left_seat is not None
            and right_seat is not None
        ):
            ground_step = abs(left_seat - right_seat)
            if ground_step > tolerance_metres:
                cut_edges.append(
                    CutEdge(left_key, right_key, ground_step)
                )
                continue
        kept_edges.append((left_key, right_key))
        ground_union.union(left_key, right_key)

    ground_clusters = ground_union.components()
    cluster_id_by_part_key: dict[int, int] = {}
    for cluster_id, member_keys in enumerate(ground_clusters):
        for key in member_keys:
            cluster_id_by_part_key[key] = cluster_id

    # ── elevated components assign to clusters (spec section 4.2a) ────
    # Components of the ELEVATED-only subgraph; each joins exactly one
    # cluster and can never merge two.
    elevated_union = _UnionFind(elevated_keys)
    for left_key, right_key in edges:
        if (
            not part_by_key[left_key].is_ground
            and not part_by_key[right_key].is_ground
        ):
            elevated_union.union(left_key, right_key)

    contacts_by_elevated_key: dict[int, list[int]] = {}
    for left_key, right_key in edges:
        left, right = part_by_key[left_key], part_by_key[right_key]
        if left.is_ground == right.is_ground:
            continue
        elevated_key = right_key if left.is_ground else left_key
        ground_key = left_key if left.is_ground else right_key
        cluster_id = cluster_id_by_part_key.get(ground_key)
        if cluster_id is not None:
            contacts_by_elevated_key.setdefault(elevated_key, []).append(
                cluster_id
            )

    bridge_seams: list[BridgeSeam] = []
    unassigned: list[tuple[int, ...]] = []
    for component_keys in elevated_union.components():
        contact_count_by_cluster: dict[int, int] = {}
        for key in component_keys:
            for cluster_id in contacts_by_elevated_key.get(key, ()):
                contact_count_by_cluster[cluster_id] = (
                    contact_count_by_cluster.get(cluster_id, 0) + 1
                )
        if not contact_count_by_cluster:
            # No ground path inside its own structure: the caller falls
            # back to the containing/nearest cluster (spec 4.2b).
            unassigned.append(tuple(component_keys))
            continue
        # Majority contact wins; ties go to the lower cluster id.  (The
        # spec's intermediate tie-break is contact AREA; the contact
        # graph carries no area, and a tie on integer contact counts
        # between two clusters of one bridge has not been observed —
        # noted in the module docstring's honesty tradition.)
        chosen_cluster_id = min(
            contact_count_by_cluster,
            key=lambda cluster_id: (
                -contact_count_by_cluster[cluster_id],
                cluster_id,
            ),
        )
        for key in component_keys:
            cluster_id_by_part_key[key] = chosen_cluster_id
        for other_cluster_id in sorted(contact_count_by_cluster):
            if other_cluster_id == chosen_cluster_id:
                continue
            bridge_seams.append(
                BridgeSeam(
                    cluster_id=chosen_cluster_id,
                    other_cluster_id=other_cluster_id,
                    contact_count=contact_count_by_cluster[
                        chosen_cluster_id
                    ],
                    other_contact_count=contact_count_by_cluster[
                        other_cluster_id
                    ],
                    part_count=len(component_keys),
                )
            )

    return ClusterPartition(
        cluster_id_by_part_key=cluster_id_by_part_key,
        cluster_count=len(ground_clusters),
        kept_edges=tuple(kept_edges),
        cut_edges=tuple(cut_edges),
        bridge_seams=tuple(bridge_seams),
        unassigned_elevated_components=tuple(unassigned),
    )


def residual_part_groups(
    part_keys: list[int],
    kept_edges,
    over_tolerance_keys: set[int],
) -> list[tuple[int, ...]]:
    """Maximal connected groups of OVER-TOLERANCE ground parts within one
    cluster (spec section 5.3).

    Grouping connected residual parts — rather than one request per part
    — keeps a sloping terminal end as a handful of coherent pads instead
    of hundreds of confetti rings.  Groups come back ordered by their
    lowest member key.
    """
    members = [key for key in part_keys if key in over_tolerance_keys]
    if not members:
        return []
    union = _UnionFind(members)
    member_set = set(members)
    for left_key, right_key in kept_edges:
        if left_key in member_set and right_key in member_set:
            union.union(left_key, right_key)
    return [tuple(group) for group in union.components()]
