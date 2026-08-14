"""THE OBJECT PAD FRAME — one build, one read, no mesh.

WHY (RULINGS "OBJECT PADS: EMISSION-TIME RELATIVE", owner 2026-08-14;
Fable resolution R3, "one frame, single pass", 2026-08-14).  A pad
request is made of PACK data — which parts of which structure touch the
ground, where they touch (the contact band), the authored ``base_y`` they
touch at, and the placement anchor the object renders from.  None of that
consults the mesh.  Until now it existed only inside
``object_anchor.structure_deltas``, which runs AFTER the mesh, so the pad
emitter could reach it only by replaying the PREVIOUS build's sidecar —
the cross-build convergence the owner retired ("no convergence and no
multi-build anything").

So this module lifts exactly the mesh-free half out, to be built ONCE
per build, pre-solve, and cached on PRISTINE pack inputs (owner ruling
2026-08-13, "AIRPORT DERIVED CACHES KEY ON PRISTINE INPUTS" — the same
discipline as the footprint and classification sidecars, and keyed
through the one implementation,
``object_rebake.pristine_object_fingerprint_entries``).  Warm builds pay
~0 for it; the cold one-time re-key is the known class and never belongs
in a baseline.

WHAT IS AND IS NOT HERE.  Here: parts, contact-band geometry, ``base_y``,
part centroids, the anchor datum and AGL, resource identity.  Not here:
any ground elevation at all.  The two consumers each supply their own
ground authority and NEITHER re-derives the frame —

* pad emission (``object_pads``) reads the ground from the emitted patch
  itself (``patch_ground.PatchGroundField``), post-solve, same build;
* the y-bake fallback (``post_mesh.rebake_dsf_objects``) reads it from
  the BUILT mesh, which is the one genuinely mesh-dependent measurement
  and the only reason that phase still exists.

THE ARITHMETIC IS UNCHANGED, and that is deliberate.  A part's rendered
base is ``ground(anchor of its resource) + base_y(part)`` and its
residual is the distance from that to the ground under the part —
verbatim ``object_anchor._raise_cluster_pad_requests``' ``seated=False``
branch (reseat-threshold spec §2.2).  The emission-time design changes
WHICH SURFACE answers "ground", never the formula.

PURITY.  Nothing in this module opens a file or looks at a clock: it
takes a pool, its geometry and its structures and returns records.  The
disk half lives with the rest of Phase 2's file work
(``post_mesh._cached_pad_frame``), exactly as ``object_anchor`` stays
pure while ``post_mesh._cached_partition_structures`` owns its cache.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass, field as dataclass_field

#: Bump when a field or a derivation below changes; the cache key
#: carries it, so a stale sidecar can never be read as a fresh frame.
#: 2: the WELDING rides along (``welded_labels_by_structure`` +
#:    ``pool_frame_signature``) so the post-mesh y-bake consumes this
#:    frame instead of re-welding — step (2) of the R3 order.
PAD_FRAME_VERSION = 2


@dataclass(frozen=True)
class PadPart:
    """One ground-touching part's pad evidence — PACK data only.

    ``contact_parts_lonlat`` is the ring law's own input
    (object-reseat-threshold-spec §2.5 v2b): one tuple per
    ground-contact TRIANGLE, which ``object_footprints.foot_pad_rings``
    hulls and unions.  It is NEVER a convex hull over the part, and
    never a plan box except in the degenerate case
    ``object_anchor._contact_band_triangles_lonlat`` still allows — the
    single-group hull is the RETIRED law that spanned water and parking
    lots (OTHH 1.0.226, 162,219 m²).
    """

    structure_index: int
    part_key: int
    base_resource: str
    base_y: float
    latitude: float                     # the part centroid
    longitude: float
    contact_parts_lonlat: tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True)
class PadAnchor:
    """A resource's RENDER DATUM: the object draws its ``y = 0`` plane at
    ``ground(latitude, longitude) + above_ground_level_metres``
    (``object_anchor`` amendment A18).  Datums are commonly SHARED — at
    HECA one point carries 199 resources — so this is keyed by resource
    and the sharing is a property of the values, never assumed away."""

    latitude: float
    longitude: float
    above_ground_level_metres: float


@dataclass(frozen=True)
class ObjectPadFrame:
    """Everything a pad request needs and nothing a mesh decides."""

    parts: tuple[PadPart, ...]
    anchor_by_resource: dict[str, PadAnchor]
    #: (resource_path, reason) for resources the pool frame excluded —
    #: carried so a consumer reports the same refusals the rebake does
    #: rather than silently padding something the bake would not touch.
    excluded_resources: tuple[tuple[str, str], ...] = ()
    #: THE WELDING, per structure index — as PART LABELS, one per shared
    #: triangle in the structure's own triangle order (see
    #: :func:`regroup_welded_parts`).  Welding is the expensive half of a
    #: part measurement and it is pure pack data, so the frame is the ONE
    #: place a build pays for it; the post-mesh y-bake consumes this
    #: rather than re-welding (R3 step 2, the basis of acceptance (c)).
    #:
    #: LABELS, not the triangle groups themselves, because this record
    #: goes to a sidecar: a group carries every triangle again (three
    #: ints each, a pack-sized pickle), while the label array is one
    #: small int per triangle and regroups EXACTLY — ``weld_parts``
    #: appends in input order into a dict keyed by root, so parts come
    #: back in first-appearance order with their triangles in input
    #: order, which is what the regroup reproduces.
    welded_labels_by_structure: dict[int, array] = (
        dataclass_field(default_factory=dict))
    #: ``object_anchor.pool_frame_signature`` of the frame these welded
    #: triangle INDICES point into.  A consumer whose own pool frame has
    #: a different signature must re-weld: the indices would otherwise
    #: read the wrong vertices, plausibly and silently.
    pool_frame_signature: tuple = ()

    def parts_by_structure(self) -> dict:
        """``{structure_index: [PadPart]}`` — the grouping unit.  A pad
        request groups CONNECTED over-residual parts of one structure
        (per-cluster seating spec §5.3), and ``foot_pad_rings`` supplies
        the connectivity geometrically: it dilates each part's contact
        hulls and unions them, returning one ring per connected
        component.  So the caller hands it a structure's over-residual
        parts and the ring law does the grouping it always did."""
        out: dict = {}
        for part in self.parts:
            out.setdefault(part.structure_index, []).append(part)
        return out


def welded_part_labels(shared_triangles, welded_parts) -> array:
    """``weld_parts``' output as one small int per triangle.

    The label of a triangle is the ordinal of the part it landed in, in
    the order ``weld_parts`` returned the parts.  Triangle identity is
    POSITIONAL — the i-th label belongs to the i-th of
    ``shared_triangles`` — because a welded part holds the very tuple
    objects the caller passed in, in input order, so position is exact
    and never needs the triangle's contents.
    """
    label_by_position: dict[int, int] = {}
    for part_ordinal, part in enumerate(welded_parts):
        for triangle in part:
            label_by_position[id(triangle)] = part_ordinal
    return array("i", (label_by_position[id(triangle)]
                       for triangle in shared_triangles))


def regroup_welded_parts(shared_triangles, labels) -> list[list]:
    """The inverse of :func:`welded_part_labels` — ``weld_parts``' exact
    output rebuilt from the labels.

    ``weld_parts`` groups by appending each triangle, in input order,
    into a dict keyed by its part's union-find root, then returns
    ``list(values())``.  Dicts preserve insertion order, so parts come
    out in FIRST-APPEARANCE order with their triangles in INPUT order —
    both of which this reproduces by construction, which is why a
    consumed welding and a performed one cannot differ.
    """
    groups: dict[int, list] = {}
    for triangle, label in zip(shared_triangles, labels):
        groups.setdefault(label, []).append(triangle)
    return list(groups.values())


def build_pad_frame(pool, geometry_by_resource, structures) -> ObjectPadFrame:
    """The mesh-free frame for one object pool.

    Reuses ``object_anchor``'s own builders — ``_build_pool_frame``,
    ``_measure_structure_parts`` (with ``sampler=None``, the mesh-free
    reading) and ``_contact_band_triangles_lonlat`` — so the frame and
    the rebake cannot drift about what a part is or where it touches.  A
    private re-derivation of any of them would be the census-wrapper
    defect at object scale.
    """
    from . import object_anchor
    from .config import (
        DSF_OBJECT_ELEVATED_BASE_M,
        DSF_OBJECT_FOOT_BAND_M,
    )

    frame = object_anchor._build_pool_frame(pool, geometry_by_resource)

    anchor_by_resource: dict[str, PadAnchor] = {}
    placement_by_resource = {
        placement.resource_path: placement for placement in pool.placements
    }
    for resource_path in frame.included_resources:
        placement = placement_by_resource.get(resource_path)
        if placement is None:                         # pragma: no cover
            continue
        anchor_by_resource[resource_path] = PadAnchor(
            latitude=float(placement.latitude),
            longitude=float(placement.longitude),
            above_ground_level_metres=float(
                placement.above_ground_level_metres),
        )

    parts: list[PadPart] = []
    welded_labels_by_structure: dict = {}
    for structure_index, structure in enumerate(structures):
        shared_triangles = []
        for resource_path, triangles in (
            structure.triangles_by_resource.items()
        ):
            base_offset = frame.base_offset_by_resource.get(resource_path)
            if base_offset is None:
                continue
            shared_triangles.extend(
                tuple(base_offset + index for index in triangle)
                for triangle in triangles
            )
        if not shared_triangles:
            continue
        # THE ONE WELD (R3 step 2).  Performed here, kept on the frame,
        # and handed to the measurement below — so the post-mesh y-bake
        # reads this product instead of repeating the pool's most
        # expensive pure-pack computation against the same inputs.
        welded = object_anchor.obj8_partition.weld_parts(
            frame.shared_vertices, shared_triangles)
        welded_labels_by_structure[structure_index] = welded_part_labels(
            shared_triangles, welded)
        measurements = object_anchor._measure_structure_parts(
            frame,
            None,                                     # MESH-FREE
            shared_triangles,
            0.0,                                      # unused with no sampler
            DSF_OBJECT_ELEVATED_BASE_M,
            for_clustering=True,
            welded_parts=welded,
        )
        for measurement in measurements:
            if not measurement.is_ground:
                continue
            groups = object_anchor._contact_band_triangles_lonlat(
                frame, measurement, DSF_OBJECT_FOOT_BAND_M)
            if not groups:
                # R1 (round-4 spec): a part that cannot say WHERE it
                # touches raises no pad request.  Dropped, never
                # fallen back onto a plan box.
                continue
            parts.append(PadPart(
                structure_index=structure_index,
                part_key=int(measurement.key),
                base_resource=measurement.base_resource,
                base_y=float(measurement.base_y),
                latitude=float(measurement.latitude),
                longitude=float(measurement.longitude),
                contact_parts_lonlat=tuple(tuple(g) for g in groups),
            ))

    return ObjectPadFrame(
        parts=tuple(parts),
        anchor_by_resource=anchor_by_resource,
        excluded_resources=tuple(frame.excluded_resources),
        welded_labels_by_structure=welded_labels_by_structure,
        pool_frame_signature=object_anchor.pool_frame_signature(frame),
    )


def rendered_base_metres(part: PadPart, anchor_ground_metres) -> float | None:
    """A part's rendered ground-contact base.

    ``object_anchor._raise_cluster_pad_requests``' ``seated=False``
    formula verbatim: ``ground(anchor) + base_y(part)``.  ``None`` when
    the anchor has no ground — a part rendered at no known elevation
    raises nothing (invariant I-13).
    """
    if anchor_ground_metres is None:
        return None
    return float(anchor_ground_metres) + float(part.base_y)


def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return float(ordered[middle])
    return float(ordered[middle - 1] + ordered[middle]) / 2.0


def pad_requests_from_frame(frame: ObjectPadFrame, datum_ground_at,
                            surface_ground_at, *,
                            residual_floor_m: float,
                            margin_metres: float,
                            maximum_relief_metres: float):
    """THE PAD REQUESTS a frame raises against its GROUND AUTHORITIES.

    TWO authorities, because the two points a request measures are not
    the same kind of point:

    * ``datum_ground_at(latitude, longitude)`` — the RENDER DATUM's
      ground.  This is the ruling's own clause ("pad target = the
      patch's own evaluated ground at the datum + base_y"), and it is
      the PATCH, exactly: the premise test that authorised this design
      measured patch-evaluated against built-mesh at HOSTED datums only
      (p90 0.60 m, under the 0.75 m cap, and 0.0000 at every
      request-carrying datum).  ``None`` — an unhosted datum, where the
      mesh drapes ambient DEM and the patch authors nothing — means the
      relative coupling has no node to read, and the object keeps the
      y-bake path.  Never approximated: that population is 588 of 2700
      datums at HECA and 1514 of 8537 at OTHH, and guessing at it is how
      a coupling turns into a DEM approximation the ruling rejected.

    * ``surface_ground_at(latitude, longitude)`` — the ground UNDER A
      PART, which is what the residual is measured against.  That point
      is almost never on the patch (a pad exists precisely where terrain
      is not already graded — where it were, the pad would be clipped
      away by pavement), so this authority is the MESH'S OWN RULE:
      the patch where the patch authors, ambient DEM where it does not.
      It replaces ``MeshElevationSampler.elevation_at_or_none``, which is
      the same rule evaluated on a mesh that does not exist yet.

    THE ARITHMETIC IS ``object_anchor._raise_cluster_pad_requests``'
    ``seated=False`` branch, moved and not rewritten — which is the only
    branch available before the mesh exists, and the right one: the
    emission-time design is "the object stays where its author put it and
    the terrain comes to it" (reseat-threshold spec §2.2).  Per part,

        rendered base = ground(render datum) + AGL + base_y
        residual      = rendered base − ground(under the part)

    and a part is a pad candidate when ``|residual| > residual_floor_m``.
    A group's target is the MEDIAN of its parts' rendered bases, exactly
    as the rebake's, so the pad still asks terrain for the least it can.

    ``maximum_relief_metres`` is NOT measured here.  ``over_relief_cap``
    below is the parts-vs-host question — a part floating further than
    the cap above the ground under IT is not padable — while the pad's
    own admissibility is plate-vs-LANDING-ground and can only be taken
    once the plate survives the pavement clip, in
    ``object_pads.emit_object_pads`` (RULINGS "PAD CAP REFERENCE IS THE
    PLATE'S LANDING GROUND", owner 2026-08-14).  The two compose; neither
    reads raw DEM.

    THE GROUPING IS THE RING LAW'S (``object_footprints.foot_pad_rings``):
    the candidate parts' contact hulls are dilated and unioned and each
    connected component comes back as one ring, which is the same
    connectivity ``object_clusters.residual_part_groups`` expressed
    geometrically — see :meth:`ObjectPadFrame.parts_by_structure`.  A part
    is assigned to the ring covering its first contact triangle's
    centroid; that point is inside its own hull and therefore inside the
    dilated component that swallowed it, so the assignment is exact by
    construction rather than by proximity.

    Returns ``(requests, findings)``.  ``requests`` are plain dicts in the
    shape the emitter consumes (one per RING, carrying the group's
    identity); ``findings`` are ``(kind, key, measured, tolerance, "")``
    tuples for everything that did NOT become a request, because a
    request that quietly disappears is the blindness the pad specs exist
    to remove.
    """
    from . import object_footprints

    requests: list[dict] = []
    findings: list[tuple] = []
    anchor_ground_cache: dict[str, float | None] = {}

    def _anchor_ground(resource_path):
        """``ground(datum) + AGL`` — the object's rendered ``y = 0``
        plane (``object_anchor`` amendment A18).  Memoized because HECA's
        pack shares ONE datum across 199 resources (the LSGG authoring
        class) and the field query is a point location."""
        if resource_path in anchor_ground_cache:
            return anchor_ground_cache[resource_path]
        anchor = frame.anchor_by_resource.get(resource_path)
        value = None
        if anchor is not None:
            ground = datum_ground_at(anchor.latitude, anchor.longitude)
            if ground is not None:
                value = float(ground) + float(
                    anchor.above_ground_level_metres)
        anchor_ground_cache[resource_path] = value
        return value

    for structure_index, parts in sorted(
            frame.parts_by_structure().items()):
        candidates: list[tuple] = []
        for part in parts:
            anchor_ground = _anchor_ground(part.base_resource)
            base = rendered_base_metres(part, anchor_ground)
            if base is None:
                # The render datum stands on ground the patch does not
                # author (or the resource has no anchor at all): the
                # relative coupling has nothing to read, so the object
                # keeps the y-bake path.  Invariant I-13, restated at
                # emission time.
                findings.append(("pad_datum_unhosted", part.base_resource,
                                 0.0, 0.0, ""))
                continue
            part_ground = surface_ground_at(part.latitude, part.longitude)
            if part_ground is None:
                findings.append(("pad_part_unhosted", part.base_resource,
                                 0.0, 0.0, ""))
                continue
            residual = base - float(part_ground)
            if abs(residual) > residual_floor_m:
                candidates.append((part, base, residual))
        if not candidates:
            continue

        hulls = [list(hull) for part, _base, _residual in candidates
                 for hull in part.contact_parts_lonlat if hull]
        rings = object_footprints.foot_pad_rings(hulls, margin_metres)
        if not rings:
            findings.append(("pad_no_ring", str(structure_index),
                             float(len(candidates)), 0.0, ""))
            continue

        from shapely.geometry import Point, Polygon

        polygons = []
        for ring in rings:
            try:
                polygon = Polygon(ring)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
            except Exception:                     # pragma: no cover
                polygon = None
            polygons.append(polygon)

        members: dict[int, list] = {}
        for part, base, residual in candidates:
            hull = next((h for h in part.contact_parts_lonlat if h), None)
            if not hull:                          # pragma: no cover
                continue
            point = Point(sum(x for x, _y in hull) / len(hull),
                          sum(y for _x, y in hull) / len(hull))
            for ring_index, polygon in enumerate(polygons):
                if polygon is not None and polygon.covers(point):
                    members.setdefault(ring_index, []).append(
                        (part, base, residual))
                    break

        for ring_index, ring in enumerate(rings):
            group = members.get(ring_index)
            if not group:
                # A component none of the candidates centres in — it can
                # only be a sliver of a hull whose own centroid landed in
                # a neighbour.  Reported, never emitted at a guessed
                # target (§5.5: no silent pad, and no invented one).
                findings.append(("pad_ring_unclaimed", str(structure_index),
                                 0.0, 0.0, ""))
                continue
            worst_part, _worst_base, worst_residual = max(
                group, key=lambda row: (abs(row[2]), row[0].part_key))
            anchor = frame.anchor_by_resource.get(worst_part.base_resource)
            if anchor is not None and ring_covers_its_own_datum(
                    [ring], anchor):
                # THE CIRCULARITY (step 5).  Raising this ground raises
                # the object with it: the residual is AGL + base_y under
                # every target, so no pad can close it.  Routed to the
                # y-bake, which moves the OBJECT instead.
                findings.append((
                    "pad_self_covering_datum",
                    worst_part.base_resource, abs(worst_residual), 0.0,
                    f"{anchor.latitude:.5f},{anchor.longitude:.5f}"))
                continue
            target = _median(
                [base for _part, base, _residual in group])
            requests.append({
                "kind": "cluster",
                "structure_index": structure_index,
                "cluster_id": None,
                "resource_path": worst_part.base_resource,
                "latitude": worst_part.latitude,
                "longitude": worst_part.longitude,
                "base_y": worst_part.base_y,
                "residual_metres": worst_residual,
                "target_ground_metres": target,
                "part_count": len(group),
                # UNCHANGED, and deliberately NOT folded into the cap's
                # re-frame: this flag is the WORST PART's own residual
                # against the ground under IT — already an in-run,
                # local-ground measurement, and a different question from
                # "how far does the pad stand over its own ground" (a
                # group can have a within-cap median target and one part
                # still floating far above it).  Re-framing the reference
                # is this lane's charter; widening admissibility is not.
                "over_relief_cap": (
                    abs(worst_residual) > maximum_relief_metres),
                "ring_index": ring_index,
                "ring_lonlat": ring,
            })
    return requests, findings


def ring_covers_its_own_datum(rings_lonlat, anchor: PadAnchor) -> bool:
    """Is this pad's own RENDER DATUM inside the pad?

    THE CIRCULARITY (measured on lane/s5pads3, HECA: 1 of 1883
    requests).  An object draws its base at ``ground(datum) + AGL +
    base_y``.  If the pad the request would emit COVERS that datum, then
    raising the ground raises the object with it and the residual is
    ``AGL + base_y`` no matter what target is chosen — invariant, so no
    pad can ever close it.  Such a request is not padable and belongs to
    the y-bake fallback, which moves the OBJECT instead of the ground.
    """
    from shapely.geometry import Point, Polygon

    point = Point(anchor.longitude, anchor.latitude)
    for ring in rings_lonlat or ():
        if len(ring) < 3:
            continue
        try:
            if Polygon(ring).covers(point):
                return True
        except Exception:                             # pragma: no cover
            continue
    return False
