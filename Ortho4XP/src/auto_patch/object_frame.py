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

from dataclasses import dataclass

#: Bump when a field or a derivation below changes; the cache key
#: carries it, so a stale sidecar can never be read as a fresh frame.
PAD_FRAME_VERSION = 1


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
        measurements = object_anchor._measure_structure_parts(
            frame,
            None,                                     # MESH-FREE
            shared_triangles,
            0.0,                                      # unused with no sampler
            DSF_OBJECT_ELEVATED_BASE_M,
            for_clustering=True,
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
