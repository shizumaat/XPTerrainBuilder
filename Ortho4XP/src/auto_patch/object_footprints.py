"""OBJ8 structure footprints — Phase 1 of the DSF object integration.

Contract frozen by workstream W1 (``docs/dsf_object_integration_spec.md``
sections 3 and 4-W6); implementation lands in workstream W6.

Turns a partitioned :class:`~auto_patch.object_anchor.Structure` into a
building footprint ring so auto_patch's pad grading, clearance and
terminal attraction can see buildings it is blind to today (roughly 105
at KCLT).  Rulings in force:

* R3 — convex hull ships as the default ring; the faithful
  triangle-union ring sits behind ``DSF_OBJECT_FOOTPRINT_UNION`` until
  the pad-grading interaction is measured on the gate airports.
* R4 — footprints are ADDITIVE: they enter the existing DSF building
  pool (role ``"object"``), where ``_cluster_dsf_building_facades``
  unions any overlap with ``.fac`` facades and
  ``_combine_building_sources`` resolves the OSM overlap.  No new
  overlap predicate (spec section 2.3).  (2026-08-09: that resolution
  REVERSED — an OSM terminal way is now the identity of its building
  and a cluster majority-inside one is ABSORBED, where the old rule
  dropped the OSM way; see
  docs/specs/osm-terminal-way-authority-spec.md.)
* R5 — buildings are FLAT; footprints obey it.

Phase 1 never touches the mesh, and — amendment A1 — it MUST use the same
contact-graph partition as Phase 2: a pad flattened under a
differently-partitioned structure is not flat under the structure the
y offset seats (spec section 7.3).
"""

from __future__ import annotations

import math

from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

import O4_UI_Utils as UI

# Imported as modules (not names) so tests can monkeypatch the
# projection while workstream W2's implementation is still landing, and
# so the real implementation is picked up the moment it does.
from . import obj8_reader
from .obj8_reader import ObjectGeometry, ObjectPlacement
from .object_anchor import Structure

# Douglas-Peucker tolerance for the triangle-union ring, in degrees of
# longitude/latitude (~0.2 m at mid latitudes).  The union of thousands
# of projected triangles carries collinear seam vertices that would
# bloat the building pool for no geometric information; the hull path
# never needs simplification.
FOOTPRINT_SIMPLIFY_TOLERANCE_DEGREES = 2.0e-6

# Exceptions the geometry combinators here may legitimately raise on
# degenerate input (shapely domain only — never built-ins that would
# mask a real bug).
try:  # shapely 2
    from shapely.errors import GEOSException as _GEOS_EXCEPTION
except ImportError:  # pragma: no cover - shapely 1 fallback
    from shapely.errors import TopologicalError as _GEOS_EXCEPTION


def _footprint_area_square_metres(footprint_lonlat: Polygon) -> float:
    """Approximate metric area of a small lon/lat polygon (local
    equirectangular scale at the polygon's own latitude — exactly the
    projection ``obj8_reader.local_offset_to_lonlat`` inverts)."""
    centroid_latitude = footprint_lonlat.centroid.y
    metres_per_degree_longitude = (
        obj8_reader.METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(centroid_latitude)))
    return (footprint_lonlat.area
            * obj8_reader.METRES_PER_DEGREE_LATITUDE
            * metres_per_degree_longitude)


def _footprint_span_metres(footprint_lonlat: Polygon) -> float:
    """Larger side of the metric bounding box of a small lon/lat polygon
    (same local equirectangular scale as ``_footprint_area_square_metres``)
    — the structure span gate's metric (defect 2026-07-17)."""
    centroid_latitude = footprint_lonlat.centroid.y
    metres_per_degree_longitude = (
        obj8_reader.METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(centroid_latitude)))
    minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude = (
        footprint_lonlat.bounds)
    return max(
        (maximum_longitude - minimum_longitude) * metres_per_degree_longitude,
        (maximum_latitude - minimum_latitude)
        * obj8_reader.METRES_PER_DEGREE_LATITUDE)


# ── BUILDING EVIDENCE (R18-2, owner ruling 2026-08-11b) ─────────────
# A DSF-object footprint ring may seed a building pad only with BUILDING
# EVIDENCE.  This module owns the half of that ruling that is readable
# from the object's OWN solid geometry — the vertical-structure test;
# the OSM-footprint half is the pipeline's (it is the only place an OSM
# building polygon exists).  Both halves are OR-ed there.
#
# The vertical test, one sentence: a real building is TALL OVER ITS OWN
# FOOTPRINT.  Per member resource of the structure we already measure
# (a) its own ABOVE-GRADE vertical extent and (b) the footprint area its
# base triangles contribute; the evidence is the fraction of the
# structure's hull covered by members that are building-tall.
#
# This is deliberately NOT the ``DSF_OBJECT_MIN_TALL_BASE_FILL`` gate a
# few hundred lines below, even though it reads the same two quantities.
# That floor is a REFUSAL calibrated at 0.002 against HECA's thin-wall
# terminal shells (raising it toward 0.05 culled ~140 real buildings —
# see its config note), so it cannot be raised to a confident-building
# bar without deleting real pads.  The evidence coverage is the
# confident-building bar, and a structure that misses it is not refused:
# it falls through to the OSM half of the ruling.

#: One evidence row per member resource of a structure.
#: ``(resource_path, above_grade_extent_metres, base_area_degrees2)``.
StructureMemberEvidence = tuple[str, float, float]


def tall_member_coverage(
    member_evidence: list[StructureMemberEvidence],
    hull_area_degrees2: float,
    minimum_above_grade_extent_metres: float,
) -> float:
    """Fraction of a structure's footprint hull covered by the base
    triangles of members whose OWN above-grade vertical extent reaches
    ``minimum_above_grade_extent_metres``.

    THE one definition: the gate in :func:`structure_ring`, the twins,
    and ``tools/object_pad_evidence_report.py``'s population table all
    call this — a second implementation of "how tall is it over its own
    footprint" is exactly the census-wrapper defect.

    Areas are both in degree space (the lat/lon anisotropy cancels), and
    the triangle sum may double-count overlaps, which can only ever KEEP
    a structure.  Returns 0.0 for a degenerate hull.
    """
    if hull_area_degrees2 <= 0.0:
        return 0.0
    covered = sum(
        base_area
        for _resource, above_grade_extent, base_area in member_evidence
        if above_grade_extent >= minimum_above_grade_extent_metres)
    return covered / hull_area_degrees2


def tallest_member_extent(
    member_evidence: list[StructureMemberEvidence],
) -> float:
    """Tallest ABOVE-GRADE vertical extent among a structure's member
    resources — the vertical test's primary reading."""
    return max(
        (above_grade_extent
         for _resource, above_grade_extent, _base_area in member_evidence),
        default=0.0)


def has_vertical_structure_evidence(
    member_evidence: list[StructureMemberEvidence],
    hull_area_degrees2: float,
    name_vouched: bool = False,
) -> tuple[bool, float]:
    """``(verdict, coverage)`` for the vertical half of the R18-2
    evidence ruling, at the armed configuration values.

    THE TEST: some member resource of the structure stands at least
    ``DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M`` above grade on its own, and the
    tall members cover at least ``DSF_OBJECT_EVIDENCE_MIN_COVERAGE`` of
    the hull.  The coverage term is a floor for packs that need it and
    is armed at 0 by default — MEASURED at HECA (2026-08-11): a
    material-split pack authors a terminal shell as thin per-material
    wall strips whose tall members cover 0.000-0.02 of the fused hull,
    which is the SAME range as the phantom slab class, so no coverage
    floor separates them.  Height does, cleanly.  The coverage-shaped
    defence is already carried upstream by
    ``DSF_OBJECT_MIN_TALL_BASE_FILL`` (the plate+mast weld).

    ``name_vouched`` — a resource whose LIBRARY path names it a hangar
    or terminal (owner CYXY 2026-07-28).  Note the caller passes the
    EVIDENCE vouching (``evidence_name_vouches``), not the hull-fill
    gate's wider path match: at HECA every object of the Tai Models pack
    lives under ``Airport/Hangar_Tower/``, which vouched 667 of 817
    rings on a DIRECTORY name and would have vouched every phantom pad
    this gate exists to refuse (measured 2026-08-11).
    """
    from .config import (
        DSF_OBJECT_EVIDENCE_MIN_COVERAGE,
        DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M,
    )
    coverage = tall_member_coverage(
        member_evidence, hull_area_degrees2,
        DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M)
    if name_vouched:
        return True, coverage
    if DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M > 0.0 and (
            tallest_member_extent(member_evidence)
            < DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M):
        return False, coverage
    return coverage >= DSF_OBJECT_EVIDENCE_MIN_COVERAGE, coverage


# ── A SEGMENTED LINEAR FEATURE IS NOT N BUILDINGS ───────────────────
# (owner item 3, LEMD sim read of 1.0.269; inside the R18-2 EVIDENCE
# GATE ruling, RULINGS 2026-08-11b — "building-pad seeds require
# BUILDING EVIDENCE ... the two pending default-OFF defences get ruled
# by measurement inside the same round".)
#
# THE MEASURED CASE.  LEMD ``objects/LEMD_OBJ-Airport_Munoza-LEMD80.obj``
# is ONE placement (shared-datum authoring) whose solid geometry lays a
# row of SEVEN congruent 23 x 21 m modules on a straight line at a 25.7 m
# pitch — a viaduct/gallery, drawn as one texture page.  Each module
# clears the vertical-structure test on its own (tallest member 6.96-7.01
# m against the 6.0 m floor) so all seven were stamped ``object`` and
# seeded flat building pads at 570.78-573.08 m, cutting across taxiway
# junction shapeID 137 (coincident to 0.00 m).
#
# WHY AT THE GROUP, NOT THE RING.  Nothing about ONE module says "not a
# building": area 338 m², hull fill 0.63, 7 m tall.  The signature is the
# ARRAY — congruent rings, evenly spaced, colinear, all from one solo
# member resource.  Measured over all 21 multi-ring groups in the LEMD
# pack, exactly ONE passes the predicate below (the seven) and zero
# genuine buildings do; the next-closest groups fail on spacing CV
# (1.65 / 1.69) or colinearity (155-780 m residual).
#
# WHY THE TWO REFUTED DEFENCES ARE NOT USED (the measurement the ruling
# asked for, recorded here rather than kept as dead default-OFF code):
#   * the RESOURCE-LEVEL connector prefilter returns True for LEMD80
#     (span 3508.8 m, hull fill 0.0012) AND for every genuine building
#     resource tested (Terminal4 661.6 m/0.19, Cargo 1211.5 m/0.011,
#     OldTerminal 2865.6 m/0.0069) — an FS2XPlane pack splits by TEXTURE
#     PAGE, so one .obj spans the whole field whatever it draws.
#   * the STRUCTURE-SPAN gate at 300/500/750 m catches 0 of the seven
#     (their span is 25.2 m) and 2 genuine terminal structures.
# Neither separates this class; the array signature does.
#
# WHAT THE VERDICT DOES.  It demotes the rings to the UNVOUCHED role —
# it does not drop them.  The pipeline's OSM half of R18-2 still runs,
# so a real row of identical hangars that IS mapped in OSM keeps its
# pads; at LEMD all seven carry ``osm_evidence=False`` and every pad,
# with the grading it imposed, disappears.

#: Fewest members an array must have before the signature means
#: anything.  Three colinear congruent rings happen; four at an even
#: pitch do not.
SEGMENTED_ARRAY_MIN_MEMBERS = 4
#: Coefficient of variation of member FOOTPRINT AREA.  The measured
#: array is 0.00002 (one module stamped N times); the loosest genuine
#: group that is otherwise array-like is 0.98.
SEGMENTED_ARRAY_MAX_AREA_CV = 0.01
#: Coefficient of variation of the centre-to-centre SPACING along the
#: chain.  Measured 0.011; the two congruent-but-clustered groups that
#: share the pack are 1.65 and 1.69.
SEGMENTED_ARRAY_MAX_SPACING_CV = 0.15
#: Colinearity: the worst centroid offset from the chain's own
#: end-to-end line, in metres OR as a fraction of the chain length,
#: whichever is the more permissive.  Measured 0.78 m over 154.1 m.
SEGMENTED_ARRAY_MAX_OFFSET_M = 2.0
SEGMENTED_ARRAY_MAX_OFFSET_FRACTION = 0.02
#: The chain must be LINEAR: at least this many mean member widths long,
#: so a 2x2 block of identical sheds is not an array.  Measured 7.3x.
SEGMENTED_ARRAY_MIN_LENGTH_IN_WIDTHS = 4.0


def _mean_and_cv(values) -> tuple[float, float]:
    """``(mean, coefficient of variation)``; CV is ``inf`` at mean 0."""
    values = [float(v) for v in values]
    if not values:
        return 0.0, float("inf")
    mean = sum(values) / len(values)
    if mean <= 0.0:
        return mean, float("inf")
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, math.sqrt(variance) / mean


def segmented_linear_array_indices(candidates) -> set:
    """Indices of ``candidates`` that belong to a SEGMENTED LINEAR
    FEATURE — a repeated-congruent-colinear array of rings drawn by one
    solo member resource, which is one object and not N buildings.

    ``candidates`` is ``[(resources, ring_lonlat), ...]`` where
    ``resources`` is the structure's member-resource collection and
    ``ring_lonlat`` its footprint ring as ``[(lon, lat), ...]``.  Only
    SOLO-member structures group (a fused multi-resource structure is
    not a stamped module), and only structures sharing the SAME solo
    resource group together.

    Pure and deterministic: geometry in, indices out.  Returns an empty
    set for anything that does not clear every constant above.
    """
    groups: dict = {}
    for index, (resources, ring) in enumerate(candidates):
        members = tuple(sorted(resources or ()))
        if len(members) != 1 or ring is None or len(ring) < 3:
            continue
        try:
            polygon = Polygon(ring)
        except (ValueError, _GEOS_EXCEPTION):             # pragma: no cover
            continue
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0.0:
            continue
        groups.setdefault(members[0], []).append((index, polygon))

    flagged: set = set()
    for _resource, members in groups.items():
        if len(members) < SEGMENTED_ARRAY_MIN_MEMBERS:
            continue
        areas = [_footprint_area_square_metres(p) for _i, p in members]
        _area_mean, area_cv = _mean_and_cv(areas)
        if area_cv > SEGMENTED_ARRAY_MAX_AREA_CV:
            continue
        # Centroids in local metres, at the group's own latitude.
        latitude = sum(p.centroid.y for _i, p in members) / len(members)
        metres_per_degree_longitude = (
            obj8_reader.METRES_PER_DEGREE_LATITUDE
            * math.cos(math.radians(latitude)))
        points = [(p.centroid.x * metres_per_degree_longitude,
                   p.centroid.y * obj8_reader.METRES_PER_DEGREE_LATITUDE)
                  for _i, p in members]
        # Order along the chain's dominant axis, then measure it.
        x_spread = max(x for x, _y in points) - min(x for x, _y in points)
        y_spread = max(y for _x, y in points) - min(y for _x, y in points)
        points.sort(key=(lambda pt: pt[0]) if x_spread >= y_spread
                    else (lambda pt: pt[1]))
        first, last = points[0], points[-1]
        chain_length = math.hypot(last[0] - first[0], last[1] - first[1])
        if chain_length <= 0.0:
            continue
        spacings = [math.hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(points, points[1:])]
        _spacing_mean, spacing_cv = _mean_and_cv(spacings)
        if spacing_cv > SEGMENTED_ARRAY_MAX_SPACING_CV:
            continue
        ux = (last[0] - first[0]) / chain_length
        uy = (last[1] - first[1]) / chain_length
        worst_offset = max(
            abs((pt[0] - first[0]) * uy - (pt[1] - first[1]) * ux)
            for pt in points)
        if worst_offset > max(
                SEGMENTED_ARRAY_MAX_OFFSET_M,
                SEGMENTED_ARRAY_MAX_OFFSET_FRACTION * chain_length):
            continue
        widths = [min(_footprint_span_metres(p),
                      _footprint_area_square_metres(p)
                      / max(_footprint_span_metres(p), 1e-9))
                  for _i, p in members]
        width_mean = sum(widths) / len(widths)
        if width_mean <= 0.0 or chain_length < (
                SEGMENTED_ARRAY_MIN_LENGTH_IN_WIDTHS * width_mean):
            continue
        flagged.update(i for i, _p in members)
    return flagged


#: Tokens that NAME a resource a building.  Matched on the resource
#: BASENAME, or anywhere inside a stock-library virtual path — the same
#: "basename only, so a directory cannot false-vouch" discipline
#: ``dsf_reader._is_pavement_object`` already applies to its decorative
#: veto vocabulary, and the fix for the measured HECA trap above.
_BUILDING_NAME_TOKENS = ("hangar", "term_building", "terminal")


def evidence_name_vouches(resource_paths) -> bool:
    """True when a structure's own resource NAMES it a building (R18-2).

    The CYXY ruling's subject is a STOCK LIBRARY resource whose virtual
    path (``lib/airport/…/hangars/…``) is a semantic statement by the
    library author.  A payware pack's directory layout is not: HECA's
    Tai Models pack files its whole airport — jet-blast fences, apron
    slabs, barriers — under ``Airport/Hangar_Tower/`` and
    ``Airport/Hangar/``, and a path-anywhere match vouched 667 of its
    817 rings, the phantom pads included.  So: the token must be in the
    resource's own BASENAME, or the path must be a library virtual path.
    """
    import os as _os

    for resource_path in resource_paths:
        lowered = resource_path.lower().replace("\\", "/")
        basename = _os.path.basename(lowered)
        if any(token in basename for token in _BUILDING_NAME_TOKENS):
            return True
        if (lowered.startswith("lib/") or "/lib/" in lowered) and any(
                token in lowered for token in _BUILDING_NAME_TOKENS):
            return True
    return False


def _wide_path_name_vouches(resource_paths) -> bool:
    """The SHIPPED (wide) name-vouch of the two hull floors — a token
    ANYWHERE in the resource path.

    Kept only because ``DSF_OBJECT_NAME_VOUCH_SCOPED`` is parked OFF
    (r18b STOP — the gate's comment in ``config`` carries the measured
    numbers).  It is a claim about the DIRECTORY as often as the object,
    which is exactly the HECA trap ``evidence_name_vouches`` above
    refuses; when the band remedy lands, this function goes with the
    gate and ``evidence_name_vouches`` is the only implementation.
    """
    for resource_path in resource_paths:
        lowered = resource_path.lower()
        if ("hangar" in lowered or "term_building" in lowered
                or "/terminal" in lowered):
            return True
    return False


def _triangle_union_parts(
    triangle_corner_points: list[tuple[tuple[float, float],
                                       tuple[float, float],
                                       tuple[float, float]]],
) -> list[Polygon]:
    """THE triangle-union primitive: unary_union of the projected
    triangles, ``buffer(0)``-repaired, split into its DISJOINT
    components, each exterior-only (interior rings are dropped in v1)
    and DP-simplified, ordered largest first.

    One implementation, two consumers: :func:`_triangle_union_footprint`
    (the ``DSF_OBJECT_FOOTPRINT_UNION`` single ring — the dominant
    component) and :func:`structure_footprint_parts` (the
    structure-walls footprint, which keeps every component because five
    buildings drawn by one texture page are five footprints and the
    ground between them is not footprint).  The order is deterministic —
    ``(-area, bounds)``, never GEOS order — because a ring's INDEX is
    part of its identity downstream (``object_pads`` keys a stored
    record by ring index; ``foot_pad_rings`` sorts the same way for the
    same reason).  Returns ``[]`` when the union degenerates."""
    triangle_polygons = []
    for corner_points in triangle_corner_points:
        try:
            triangle_polygon = Polygon(corner_points)
            if not triangle_polygon.is_valid:
                triangle_polygon = triangle_polygon.buffer(0)
            if (not triangle_polygon.is_empty
                    and triangle_polygon.geom_type == "Polygon"
                    and triangle_polygon.area > 0.0):
                triangle_polygons.append(triangle_polygon)
        except (ValueError, _GEOS_EXCEPTION):
            continue
    if not triangle_polygons:
        return []
    try:
        union = unary_union(triangle_polygons)
        if not union.is_valid:
            union = union.buffer(0)
    except (ValueError, _GEOS_EXCEPTION):
        return []
    if union.is_empty:
        return []
    components = ([union] if union.geom_type == "Polygon"
                  else [geometry for geometry in getattr(union, "geoms", ())
                        if geometry.geom_type == "Polygon"])
    parts: list[Polygon] = []
    for component in components:
        if component.is_empty or component.area <= 0.0:
            continue
        exterior_only = Polygon(component.exterior)
        try:
            simplified = exterior_only.simplify(
                FOOTPRINT_SIMPLIFY_TOLERANCE_DEGREES, preserve_topology=True)
        except (ValueError, _GEOS_EXCEPTION):
            simplified = exterior_only
        if simplified.is_empty or simplified.geom_type != "Polygon":
            simplified = exterior_only
        parts.append(simplified)
    parts.sort(key=lambda geometry: (-geometry.area, geometry.bounds))
    return parts


def _triangle_union_footprint(
    triangle_corner_points: list[tuple[tuple[float, float],
                                       tuple[float, float],
                                       tuple[float, float]]],
) -> Polygon | None:
    """The ``DSF_OBJECT_FOOTPRINT_UNION`` ring — the DOMINANT component
    of :func:`_triangle_union_parts`.  Base-filtered triangles of one
    structure can form several disjoint ground patches (separate wall
    footings); this flag's contract is one structure, one ring, so it
    keeps the largest.  Returns ``None`` when the union degenerates."""
    parts = _triangle_union_parts(triangle_corner_points)
    return parts[0] if parts else None


def foot_pad_rings(
    contact_parts_lonlat: list[list[tuple[float, float]]],
    margin_metres: float,
) -> list[list[tuple[float, float]]]:
    """THE FOOTPRINT-HUGGING PAD RING (object-reseat-threshold-spec §2.5,
    v2 amendment 2026-08-09) — the rings of ONE pad request.

    Each element of ``contact_parts_lonlat`` is one CONTACT PART's ground
    points (a cluster part's plan-box corners, a foot's contact
    vertices).  Every part is hulled ON ITS OWN, dilated by
    ``margin_metres``, and the dilated hulls are UNIONED; each connected
    component of that union comes back as its own ring, largest first.
    Components are never re-hulled together — that re-hull is exactly the
    retired law, whose single group hull bridged the non-object ground
    between spread-out parts and flattened it (OTHH in-sim, build
    1.0.226: a 162,219 m² pad spanning water and parking lots).

    Two structural consequences hold by construction, and the tests
    assert them: no ring spans a gap wider than ``2 × margin_metres``
    (two dilated hulls that far apart cannot meet), and every ring vertex
    lies within ``margin_metres`` of a real contact hull.

    Same coordinate contract as :func:`structure_ring` — ``(longitude,
    latitude)``, unclosed.  Hull, dilation and union run in local metres
    at the request's own latitude (the projection
    ``obj8_reader.local_offset_to_lonlat`` inverts), then map back.
    Returns ``[]`` when the input degenerates.
    """
    parts = [list(part) for part in (contact_parts_lonlat or ()) if part]
    if not parts:
        return []
    all_points = [point for part in parts for point in part]
    centroid_latitude = sum(
        latitude for _longitude, latitude in all_points) / len(all_points)
    metres_per_degree_longitude = (
        obj8_reader.METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(centroid_latitude)))
    if metres_per_degree_longitude <= 0.0:
        return []
    centroid_longitude = sum(
        longitude for longitude, _latitude in all_points) / len(all_points)

    def _local(part):
        return [
            ((longitude - centroid_longitude) * metres_per_degree_longitude,
             (latitude - centroid_latitude)
             * obj8_reader.METRES_PER_DEGREE_LATITUDE)
            for longitude, latitude in part]

    dilated = []
    for part in parts:
        try:
            hull = MultiPoint(_local(part)).convex_hull
            padded = hull.buffer(margin_metres, quad_segs=2)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if padded.is_empty or padded.area <= 0.0:
            continue
        dilated.append(padded)
    if not dilated:
        return []
    try:
        union = unary_union(dilated)
        if not union.is_valid:
            union = union.buffer(0)
    except (ValueError, _GEOS_EXCEPTION):
        return []
    if union.is_empty:
        return []
    components = ([union] if union.geom_type == "Polygon"
                  else [geometry for geometry in getattr(union, "geoms", ())
                        if geometry.geom_type == "Polygon"])
    # Largest first, ties broken on the bounding box: the ring ORDER is
    # part of a pad's identity downstream (``object_pads`` keys a stored
    # record by its ring index), so it must not depend on GEOS ordering.
    components.sort(key=lambda geometry: (-geometry.area, geometry.bounds))
    rings: list[list[tuple[float, float]]] = []
    for component in components:
        ring = [
            (float(centroid_longitude + x / metres_per_degree_longitude),
             float(centroid_latitude
                   + y / obj8_reader.METRES_PER_DEGREE_LATITUDE))
            for x, y in component.exterior.coords[:-1]]
        if len(ring) >= 3:
            rings.append(ring)
    return rings


def foot_pad_ring(
    contact_points_lonlat: list[tuple[float, float]],
    margin_metres: float,
) -> list[tuple[float, float]] | None:
    """The single-contact-part case of :func:`foot_pad_rings`: the convex
    hull of ONE part's contact points, dilated by ``margin_metres``.

    One part is one hull is one component, so this is the union law with
    nothing to union — kept as the name callers with a single contact
    part (a foot cluster; a hand-built test request) already use.  A
    caller holding SEVERAL parts must call :func:`foot_pad_rings`:
    hulling them together is the retired law (§2.5).  Returns ``None``
    when the input degenerates.
    """
    if not contact_points_lonlat:
        return None
    rings = foot_pad_rings([list(contact_points_lonlat)], margin_metres)
    return rings[0] if rings else None


def clip_pad_ring_against_pavement(
    ring_lonlat: list[tuple[float, float]],
    pavement_rings_lonlat: list[list[tuple[float, float]]],
    minimum_area_fraction: float = 0.02,
) -> list[list[tuple[float, float]]]:
    """THE PAD LAW's clip (per-cluster seating spec section 5.1 clause 2,
    owner ruling R2): **pavement wins absolutely**.

    A building pad may raise or lower open terrain to meet a seated
    building, but it must never contribute, move or re-value a graded
    pavement vertex — at HECA the Private Hall's north face is INSIDE an
    apron polygon, and a pad that ignored the apron would grade the
    apron.  So the pad footprint is DIFFERENCED against the union of the
    airport's airside polygons before it can be emitted; what survives
    is the open-terrain remainder, which may be several pieces or none.

    Both the ring and the pavement rings are ``(longitude, latitude)``,
    unclosed, in the :func:`foot_pad_ring` convention.  Returns the
    surviving pieces in the same convention, largest first; an empty
    list means the pad was wholly inside pavement and is INADMISSIBLE
    (spec section 5.4 — the caller reports it, never emits a shrunken
    stand-in).  Pieces smaller than ``minimum_area_fraction`` of the
    original are dropped as clip slivers.

    This function is the single source both the future pad emitter and
    its validator must clip with (ruling R5, lockstep).
    """
    if not ring_lonlat or len(ring_lonlat) < 3:
        return []
    try:
        pad = Polygon(ring_lonlat)
        if not pad.is_valid:
            pad = pad.buffer(0)
    except (ValueError, _GEOS_EXCEPTION):
        return []
    if pad.is_empty or pad.area <= 0.0:
        return []
    original_area = pad.area

    pavement_polygons = []
    for pavement_ring in pavement_rings_lonlat or ():
        if not pavement_ring or len(pavement_ring) < 3:
            continue
        try:
            pavement = Polygon(pavement_ring)
            if not pavement.is_valid:
                pavement = pavement.buffer(0)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if not pavement.is_empty and pavement.area > 0.0:
            pavement_polygons.append(pavement)
    if pavement_polygons:
        try:
            remainder = pad.difference(unary_union(pavement_polygons))
        except (ValueError, _GEOS_EXCEPTION):
            return []
    else:
        remainder = pad
    if remainder.is_empty:
        return []

    pieces = (
        list(remainder.geoms)
        if remainder.geom_type == "MultiPolygon"
        else [remainder]
    )
    kept = [
        piece
        for piece in pieces
        if piece.geom_type == "Polygon"
        and not piece.is_empty
        and piece.area > original_area * minimum_area_fraction
    ]
    kept.sort(key=lambda piece: -piece.area)
    return [
        [(float(x), float(y)) for x, y in piece.exterior.coords[:-1]]
        for piece in kept
    ]


def draped_pavement_patches(
    geometry: ObjectGeometry,
    placement: ObjectPlacement,
    minimum_patch_area_square_metres: float,
) -> list[tuple[list[tuple[float, float]],
                list[list[tuple[float, float]]]]]:
    """Union one placement's DRAPED triangles into pavement patches.

    The object-pavement source (HECA Tai Models,
    ``dsf_reader.read_dsf_object_pavements``): a ground-paint ``.obj``
    carries the whole airport's geometry for one texture, so its draped
    triangles union into MANY disjoint pavement areas.  Unlike the
    building-pad ring (:func:`structure_ring` — one structure, one
    dominant patch, holes dropped), pavement keeps EVERY patch above
    ``minimum_patch_area_square_metres`` and honours interior rings: a
    perforated apron sheet must not fill its infield holes.

    Returns ``(outer_ring, hole_rings)`` pairs in ``(longitude,
    latitude)``, rings unclosed — the ``read_dsf_pavements`` ring
    contract, so the caller can feed both sources through one path.
    Returns ``[]`` when the geometry has no draped triangles or the
    union degenerates.
    """
    if not geometry.draped_triangles:
        return []
    projected_by_vertex_index: dict[int, tuple[float, float]] = {}
    triangle_polygons = []
    for triangle in geometry.draped_triangles:
        corner_points = []
        for vertex_index in triangle:
            point = projected_by_vertex_index.get(vertex_index)
            if point is None:
                local_x, _local_y, local_z = (
                    geometry.vertices[vertex_index])
                latitude, longitude = obj8_reader.local_offset_to_lonlat(
                    placement.latitude,
                    placement.longitude,
                    placement.heading_degrees,
                    local_x,
                    local_z,
                )
                point = (longitude, latitude)
                projected_by_vertex_index[vertex_index] = point
            corner_points.append(point)
        try:
            triangle_polygon = Polygon(corner_points)
            if not triangle_polygon.is_valid:
                triangle_polygon = triangle_polygon.buffer(0)
            if (not triangle_polygon.is_empty
                    and triangle_polygon.geom_type == "Polygon"
                    and triangle_polygon.area > 0.0):
                triangle_polygons.append(triangle_polygon)
        except (ValueError, _GEOS_EXCEPTION):
            continue
    if not triangle_polygons:
        return []
    try:
        union = unary_union(triangle_polygons)
        if not union.is_valid:
            union = union.buffer(0)
    except (ValueError, _GEOS_EXCEPTION):
        return []
    if union.is_empty:
        return []
    patches = list(union.geoms) if union.geom_type == "MultiPolygon" else (
        [union] if union.geom_type == "Polygon" else [])

    out: list[tuple[list[tuple[float, float]],
                    list[list[tuple[float, float]]]]] = []
    for patch in patches:
        if (_footprint_area_square_metres(patch)
                < minimum_patch_area_square_metres):
            continue
        try:
            simplified = patch.simplify(
                FOOTPRINT_SIMPLIFY_TOLERANCE_DEGREES,
                preserve_topology=True)
        except (ValueError, _GEOS_EXCEPTION):
            simplified = patch
        if simplified.is_empty or simplified.geom_type != "Polygon":
            simplified = patch
        outer_ring = [(float(longitude), float(latitude))
                      for longitude, latitude
                      in simplified.exterior.coords[:-1]]
        if len(outer_ring) < 3:
            continue
        hole_rings = []
        for interior in simplified.interiors:
            hole_ring = [(float(longitude), float(latitude))
                         for longitude, latitude in interior.coords[:-1]]
            if len(hole_ring) >= 3:
                hole_rings.append(hole_ring)
        out.append((outer_ring, hole_rings))
    return out


def is_vehicle_pavement_patch(
    patch_polygon_metres,
    minimum_aircraft_width_metres: float,
    opening_area_ratio: float,
) -> bool:
    """True when a ground-paint pavement patch is vehicle/drainage paint
    rather than aircraft-capable pavement (owner direction 2026-07-18).

    The test is a morphological OPENING RATIO: erode the patch by half
    ``minimum_aircraft_width_metres``, dilate back, and compare the
    surviving area to the original.  A painted service road or drainage
    channel is a long corridor narrower than any aircraft pavement, so
    almost nothing survives — but plain erosion-to-empty is NOT enough:
    a road NETWORK patch has occasional wide pockets (intersections,
    small plazas) that survive erosion and would keep the whole
    connected snake (measured: HECA ``road.obj``'s 165,820 m² patch,
    ~6 m corridors over a 2.7 × 7.4 km span, survived plain erosion).
    Opening recovers the aircraft-capable cores at full extent, and the
    area fraction separates cleanly (HECA: vehicle/drainage ≤ 0.29,
    real pavement ≥ 0.37, bulk ≥ 0.96).

    The caller gates on ``minimum_aircraft_width_metres > 0`` (0 =
    filter disabled) and on the patch being OBJECT-sourced.  Geometry
    errors classify as NOT vehicle (keep the patch — admission must
    fail open, never silently drop real pavement).
    """
    try:
        half_width = 0.5 * minimum_aircraft_width_metres
        eroded = patch_polygon_metres.buffer(-half_width)
        opened_area = (0.0 if eroded.is_empty
                       else eroded.buffer(half_width).area)
        return opened_area < opening_area_ratio * patch_polygon_metres.area
    except (ValueError, _GEOS_EXCEPTION):
        return False


def abutting_contact_ratio(
    patch_polygon_metres,
    neighbour_polygons_metres,
    contact_tolerance_metres: float = 0.5,
) -> float:
    """Fraction of a patch's LONG side in edge-contact with neighbour
    pavement: shared-boundary length / half the patch perimeter.

    A taxiway SHOULDER abuts the pavement it serves for its whole run
    (ratio ~1.0 one-sided, ~2.0 sandwiched between two pavements); a
    perimeter road or an offset strip only meets pavement at crossings
    (measured HECA: roads <= 0.32, abutting strips >= 0.58 — a clean
    gap).  Used by the pipeline's vehicle-pavement admission filter to
    READMIT narrow object patches that are really shoulders.  Geometry
    errors return 0.0 (no readmission claim).
    """
    try:
        exterior = patch_polygon_metres.exterior
        half_perimeter = 0.5 * exterior.length
        if half_perimeter <= 0.0:
            return 0.0
        contact_length = 0.0
        for neighbour in neighbour_polygons_metres:
            try:
                contact_length += exterior.intersection(
                    neighbour.buffer(contact_tolerance_metres)).length
            except (ValueError, _GEOS_EXCEPTION):
                continue
        return contact_length / half_perimeter
    except (ValueError, _GEOS_EXCEPTION):
        return 0.0


def structure_ring(
    structure: Structure,
    geometry_by_resource: dict[str, ObjectGeometry],
    placements: list[ObjectPlacement],
    evidence_out: dict | None = None,
) -> list[tuple[float, float]] | None:
    """Build a footprint ring for one structure, in ``(longitude,
    latitude)``, unclosed (first vertex not repeated) — matching
    ``read_dsf_buildings``'s existing building-tuple contract.

    * Take solid vertices with ``y <= minimum_base_y +
      DSF_OBJECT_FOOTPRINT_HEIGHT_M`` (roof overhang must not inflate the
      pad); fewer than 3 qualifying falls back to all solid vertices.
    * Project each vertex through its OWN object's placement.
    * Ring: convex hull by default; under ``DSF_OBJECT_FOOTPRINT_UNION``,
      the buffer(0)-repaired union of the projected triangles, exterior
      only, simplified.
    * Return ``None`` for a structure with no ground-touching part
      (rooftop clutter is not a building pad), and — reported, never
      silent — above ``DSF_OBJECT_MAX_FOOTPRINT_AREA_M2`` when that cap
      is enabled.

    ``evidence_out``, when passed, is FILLED with this structure's
    building-evidence measurement (R18-2) whatever the outcome — the
    refusals included, so the population table can say what each gate
    would catch.  Keys: ``verdict`` (``"ring"`` or the refusing gate's
    name), ``members`` (:data:`StructureMemberEvidence` rows),
    ``hull_area_degrees2`` / ``hull_area_m2`` / ``span_m`` /
    ``centroid`` (absent before a hull exists), ``above_grade_extent_m``,
    ``total_extent_m``, ``name_vouched``, ``hull_fill``,
    ``tall_base_fill``, ``vertical_evidence`` and ``evidence_coverage``.
    It never changes what this function returns: the OSM half of the
    ruling lives in the pipeline, so the reader stamps the verdict on the
    ring's ROLE and the gate closes there.
    """
    # Function-local flag imports so tests can monkeypatch the config
    # module (the module-level idiom freezes the value — spec section
    # 4-W1, "one trap").
    from .config import (
        DSF_OBJECT_BUILDING_EVIDENCE,
        DSF_OBJECT_FOOTPRINT_HEIGHT_M,
        DSF_OBJECT_FOOTPRINT_UNION,
        DSF_OBJECT_MAX_FOOTPRINT_AREA_M2,
        DSF_OBJECT_MAX_STRUCTURE_SPAN_M,
        DSF_OBJECT_MIN_BUILDING_HEIGHT_M,
        DSF_OBJECT_MIN_FOOTPRINT_FILL,
        DSF_OBJECT_MIN_TALL_BASE_FILL,
        DSF_OBJECT_NAME_VOUCH_SCOPED,
        DSF_OBJECT_TALL_MEMBER_MIN_EXTENT_M,
    )

    def _record(verdict: str, **fields):
        """Stamp the evidence record and return ``None`` — every early
        return of this function goes through it, so a refused structure
        is measured exactly like an admitted one."""
        if evidence_out is not None:
            evidence_out["verdict"] = verdict
            evidence_out.update(fields)
        return None

    if evidence_out is not None:
        evidence_out.clear()
        evidence_out.update({
            "verdict": "unmeasured",
            "members": [],
            "name_vouched": False,
            "vertical_evidence": False,
            "evidence_coverage": 0.0,
        })

    if not structure.is_ground_touching:
        return _record("not_ground_touching")
    if (not structure.triangles_by_resource
            or not structure.minimum_base_y_by_resource):
        return _record("no_geometry")

    placement_by_resource = {
        placement.resource_path: placement for placement in placements}
    minimum_base_y = min(structure.minimum_base_y_by_resource.values())
    # The footprint band reaches from the lowest solid vertex up to
    # GRADE plus the band height — never just ``minimum + height``.  A
    # below-grade pocket (KBNA terminal: a basement piece at authored
    # y = -2.85, a garage level at -23) would otherwise pull the whole
    # band under grade, and the "footprint" of a 780,000 m² terminal
    # complex collapses to the 2 m hull of its deepest basement
    # (found 2026-07-14).  For structures based at or above grade
    # (including baked-offset feet at +6.5) this is exactly the old
    # ``minimum + height`` band.
    base_ceiling_y = (
        max(minimum_base_y, 0.0) + DSF_OBJECT_FOOTPRINT_HEIGHT_M)

    base_points: list[tuple[float, float]] = []
    all_points: list[tuple[float, float]] = []
    base_triangle_corner_points: list = []
    all_triangle_corner_points: list = []
    maximum_local_y = minimum_base_y
    # TALL-BASE accumulator (see config.DSF_OBJECT_MIN_TALL_BASE_FILL):
    # base-triangle footprint area contributed by resources whose OWN
    # vertical extent clears the building-height floor — the evidence a
    # tall member covers the footprint.
    tall_base_area = 0.0
    # R18-2 evidence rows — one per member resource, kept whatever the
    # outcome (``StructureMemberEvidence``).
    member_evidence: list[StructureMemberEvidence] = []

    for resource_path, triangles in structure.triangles_by_resource.items():
        geometry = geometry_by_resource.get(resource_path)
        placement = placement_by_resource.get(resource_path)
        if geometry is None or placement is None or not triangles:
            continue
        _res_min_y = None
        _res_max_y = None
        _res_base_area = 0.0
        # Project each vertex through its OWN object's placement (spec
        # section 2.4: the anchor is a per-object property).
        projected_by_vertex_index: dict[int, tuple[float, float]] = {}
        is_base_vertex: dict[int, bool] = {}
        for triangle in triangles:
            for vertex_index in triangle:
                if vertex_index in projected_by_vertex_index:
                    continue
                local_x, local_y, local_z = geometry.vertices[vertex_index]
                if local_y > maximum_local_y:
                    maximum_local_y = local_y
                if _res_min_y is None or local_y < _res_min_y:
                    _res_min_y = local_y
                if _res_max_y is None or local_y > _res_max_y:
                    _res_max_y = local_y
                latitude, longitude = obj8_reader.local_offset_to_lonlat(
                    placement.latitude,
                    placement.longitude,
                    placement.heading_degrees,
                    local_x,
                    local_z,
                )
                point = (longitude, latitude)
                projected_by_vertex_index[vertex_index] = point
                is_base_vertex[vertex_index] = local_y <= base_ceiling_y
                all_points.append(point)
                if is_base_vertex[vertex_index]:
                    base_points.append(point)
        # Corner tuples feed the union footprint AND the fill/tall-base
        # floors — collect them whenever any consumer is active.
        if (DSF_OBJECT_FOOTPRINT_UNION
                or DSF_OBJECT_MIN_FOOTPRINT_FILL > 0.0
                or DSF_OBJECT_MIN_TALL_BASE_FILL > 0.0
                or DSF_OBJECT_BUILDING_EVIDENCE
                or evidence_out is not None):
            for triangle in triangles:
                corner_points = tuple(
                    projected_by_vertex_index[vertex_index]
                    for vertex_index in triangle)
                all_triangle_corner_points.append(corner_points)
                if all(is_base_vertex[vertex_index]
                       for vertex_index in triangle):
                    base_triangle_corner_points.append(corner_points)
                    if len(corner_points) >= 3:
                        (bx0, by0), (bx1, by1), (bx2, by2) = \
                            corner_points[:3]
                        _res_base_area += abs(
                            (bx1 - bx0) * (by2 - by0)
                            - (bx2 - bx0) * (by1 - by0)) * 0.5
        _res_extent = ((_res_max_y - _res_min_y)
                       if (_res_min_y is not None
                           and _res_max_y is not None) else 0.0)
        if (DSF_OBJECT_TALL_MEMBER_MIN_EXTENT_M <= 0.0
                or _res_extent >= DSF_OBJECT_TALL_MEMBER_MIN_EXTENT_M):
            tall_base_area += _res_base_area
        # R18-2: the member's own ABOVE-GRADE extent (the A11 clamp, per
        # member) — a 3.9 m drainage pit and a 3.9 m wall are not the
        # same evidence, and only the part standing above grade is a
        # building.
        member_evidence.append((
            resource_path,
            ((max(_res_max_y, 0.0) - max(_res_min_y, 0.0))
             if (_res_min_y is not None and _res_max_y is not None)
             else 0.0),
            _res_base_area,
        ))

    if evidence_out is not None:
        evidence_out["members"] = list(member_evidence)
        evidence_out["total_extent_m"] = maximum_local_y - minimum_base_y
        evidence_out["above_grade_extent_m"] = (
            max(maximum_local_y, 0.0) - max(minimum_base_y, 0.0))

    if len(all_points) < 3:
        return _record("degenerate")
    # Amendment A11 (from the HECA Tai Models pack): a building has
    # walls; a ground plate, sign or decal does not.  A near-flat
    # structure gets NO Phase-1 pad — Phase 2 still y-bakes it, since a
    # mis-elevated ground plate is exactly a float/sink artifact.
    # HECA's ``heca_ground_polygon.obj`` spans 2.1 km and must never
    # become a 2 km flat building pad.
    #
    # ABOVE GRADE, not total extent (owner defect 2026-07-30, OTHH
    # Aeroscape ``Buildings/Dewatering Drainage/*``): the extent that
    # makes a structure a building is the part standing ABOVE grade.
    # The drainage basins there are open pits authored −3.82 .. +0.06 —
    # every millimetre of their 3.87 m extent is BELOW grade — and the
    # raw ``maximum − minimum`` read a 3.87 m hole as a 3.87 m building,
    # emitting a flat pad that buried the pit (measured: Drainage_04
    # 2337 m², Drainage_06 20 055 m²).  Clamping both ends at grade is
    # exactly the ``base_ceiling_y`` idiom a few lines above and leaves
    # every at-or-above-grade structure's extent unchanged (a building
    # based at +6.5 reaching +20 still measures 13.5 m).
    above_grade_extent = (
        max(maximum_local_y, 0.0) - max(minimum_base_y, 0.0))
    if (DSF_OBJECT_MIN_BUILDING_HEIGHT_M > 0.0
            and above_grade_extent < DSF_OBJECT_MIN_BUILDING_HEIGHT_M):
        UI.vprint(
            2,
            "  [object-footprints] structure above-grade vertical extent "
            f"{above_grade_extent:.2f} m (total "
            f"{maximum_local_y - minimum_base_y:.2f} m) is below the "
            f"{DSF_OBJECT_MIN_BUILDING_HEIGHT_M:.2f} m building floor "
            "(O4_DSF_OBJECT_MIN_BUILDING_HEIGHT_M) — ground plate, decal "
            "or below-grade pit, no pad.")
        return _record("min_building_height")
    # Fewer than 3 base vertices → all solid vertices (low flat objects
    # authored entirely above the height window).
    use_base_vertices = len(base_points) >= 3
    # NAME-VOUCHED BUILDINGS (owner CYXY 2026-07-28, missing hangar at
    # 60.706235,-135.0696776): a resource whose library path NAMES it a
    # building (lib/airport/hangars/…, terminal kits) is definitionally a
    # building — the same semantic trust the .fac path classifier
    # (dsf_reader._building_role_for_def) already extends.  An
    # arched-shell hangar's footings project ~0.001 of its hull (below
    # the 0.002 slab/mast floor calibrated at HECA), so the heuristic
    # alone would cull real stock hangars.
    #
    # HISTORY — the WIDE predicate this line replaced (R18-2 round 18
    # STOP report 2026-08-11, remedied in r18b 2026-08-12).  Until r18b
    # this gate matched "hangar"/"term_building"/"/terminal" ANYWHERE in
    # the resource path, which is a claim about the DIRECTORY as often as
    # the object.  HECA's Tai Models pack files its whole airport — apron
    # slabs, jersey barriers, jet-blast fences — under
    # ``Airport/Hangar_Tower/`` and ``Airport/Hangar/``, so 667 of its
    # 817 rings were name-vouched and BOTH floors below were disabled
    # across the entire pack.  That was the deeper cause of the phantom
    # pads: the 31,184 m² ring under HECA's building176 measures hull
    # fill 0.00036 against the 0.1 floor and was kept anyway.
    #
    # ``evidence_name_vouches`` — the SAME predicate the R18-2 evidence
    # gate uses, and the one the CYXY 2026-07-28 case was calibrated for
    # (a STOCK LIBRARY hangar at ``lib/airport/…``, which vouches via its
    # library virtual path) — is the correct predicate, and the r18b spec
    # ruled the substitution TOTAL.  It is PARKED behind
    # ``DSF_OBJECT_NAME_VOUCH_SCOPED`` (default OFF) instead: measured
    # right on population (HECA 817 → 210 rings, 215 → 73 building pads)
    # and it makes the HECA build REFUSE the final band-inversion law,
    # whose remedy is measured OUTSIDE this file — see the gate's own
    # comment in ``config`` for the numbers and the STOP.
    name_vouched = (
        evidence_name_vouches(structure.triangles_by_resource)
        if DSF_OBJECT_NAME_VOUCH_SCOPED
        else _wide_path_name_vouches(structure.triangles_by_resource))
    if evidence_out is not None:
        evidence_out["use_base_vertices"] = use_base_vertices
        evidence_out["name_vouched"] = name_vouched

    footprint: Polygon | None
    if DSF_OBJECT_FOOTPRINT_UNION:
        footprint = _triangle_union_footprint(
            base_triangle_corner_points if use_base_vertices
            else all_triangle_corner_points)
    else:
        try:
            hull = MultiPoint(
                base_points if use_base_vertices else all_points
            ).convex_hull
        except (ValueError, _GEOS_EXCEPTION):
            return _record("hull_failed")
        footprint = hull if (not hull.is_empty
                             and hull.geom_type == "Polygon") else None
        # HULL-FILL FLOOR (owner defect 2026-07-27, HECA building188 —
        # see config.DSF_OBJECT_MIN_FOOTPRINT_FILL): the hull over
        # SPARSE bases (one floodlight mast + jersey barriers + a stray
        # below-grade fragment) is street furniture, not a building.
        # Fill = Σ(projected base-triangle areas) / hull area, both in
        # the same degree space so the lat/lon anisotropy cancels; the
        # triangle sum may double-count overlaps, which only ever KEEPS
        # a real building.  Empty triangle evidence skips the gate.
        if (footprint is not None
                and (DSF_OBJECT_MIN_FOOTPRINT_FILL > 0.0
                     or DSF_OBJECT_MIN_TALL_BASE_FILL > 0.0)):
            def _tri_area_sum(corner_lists):
                total = 0.0
                for corners in corner_lists:
                    if len(corners) < 3:
                        continue
                    (x0, y0), (x1, y1), (x2, y2) = corners[:3]
                    total += abs(
                        (x1 - x0) * (y2 - y0)
                        - (x2 - x0) * (y1 - y0)) * 0.5
                return total

            corner_lists = (base_triangle_corner_points
                            if use_base_vertices
                            else all_triangle_corner_points)
            triangle_area = _tri_area_sum(corner_lists)
            hull_area = footprint.area
            if evidence_out is not None and hull_area > 0.0:
                evidence_out["hull_fill"] = triangle_area / hull_area
                evidence_out["tall_base_fill"] = tall_base_area / hull_area
            # TALL-BASE FILL (see config.DSF_OBJECT_MIN_TALL_BASE_FILL):
            # a plate+mast weld passes base fill AND the height gate,
            # but no TALL member covers the footprint.  Base-evidence
            # structures only — a fewer-than-3-base-vertices structure
            # has no base rows to measure.
            if (DSF_OBJECT_MIN_TALL_BASE_FILL > 0.0 and hull_area > 0.0
                    and use_base_vertices and not name_vouched):
                tall_fill = tall_base_area / hull_area
                if tall_fill < DSF_OBJECT_MIN_TALL_BASE_FILL:
                    _c = footprint.centroid
                    UI.vprint(
                        1,
                        "  [object-footprints] structure tall-base "
                        f"fill {tall_fill:.3f} is below the "
                        f"{DSF_OBJECT_MIN_TALL_BASE_FILL:.2f} floor "
                        "(O4_DSF_OBJECT_MIN_TALL_BASE_FILL) at "
                        f"{_c.y:.6f},{_c.x:.6f} "
                        f"({_footprint_area_square_metres(footprint):.0f}"
                        " m2 hull) — no tall member covers the "
                        "footprint: a slab/mast weld, not a building; "
                        "skipped.")
                    return _record(
                        "min_tall_base_fill",
                        hull_area_degrees2=hull_area,
                        hull_area_m2=_footprint_area_square_metres(
                            footprint),
                        span_m=_footprint_span_metres(footprint),
                        centroid=(footprint.centroid.y,
                                  footprint.centroid.x))
            if (DSF_OBJECT_MIN_FOOTPRINT_FILL > 0.0
                    and corner_lists and hull_area > 0.0
                    and not name_vouched):
                fill = triangle_area / hull_area
                if fill < DSF_OBJECT_MIN_FOOTPRINT_FILL:
                    _c = footprint.centroid
                    UI.vprint(
                        1,
                        "  [object-footprints] structure hull fill "
                        f"{fill:.3f} is below the "
                        f"{DSF_OBJECT_MIN_FOOTPRINT_FILL:.2f} floor "
                        "(O4_DSF_OBJECT_MIN_FOOTPRINT_FILL) at "
                        f"{_c.y:.6f},{_c.x:.6f} "
                        f"({_footprint_area_square_metres(footprint):.0f}"
                        " m2 hull) — sparse bases under one hull are "
                        "street furniture, not a building pad; skipped.")
                    return _record(
                        "min_footprint_fill",
                        hull_area_degrees2=hull_area,
                        hull_area_m2=_footprint_area_square_metres(
                            footprint),
                        span_m=_footprint_span_metres(footprint),
                        centroid=(footprint.centroid.y,
                                  footprint.centroid.x))
    if footprint is None:
        return _record("no_footprint")

    # R18-2 building evidence, vertical half — measured on the FINAL
    # hull, so what the pipeline gates on is what a reviewer sees.
    _hull_area_degrees2 = footprint.area
    # The EVIDENCE gate uses the scoped predicate, never the wide one
    # above (see its note): at HECA the wide match vouches 667 of 817
    # rings on a directory name, phantom pads included.
    _evidence_name_vouched = evidence_name_vouches(
        structure.triangles_by_resource)
    _vertical_evidence, _evidence_coverage = has_vertical_structure_evidence(
        member_evidence, _hull_area_degrees2, _evidence_name_vouched)
    if evidence_out is not None:
        evidence_out["evidence_name_vouched"] = _evidence_name_vouched
        evidence_out["tallest_member_extent_m"] = tallest_member_extent(
            member_evidence)
        evidence_out["hull_area_degrees2"] = _hull_area_degrees2
        evidence_out["hull_area_m2"] = _footprint_area_square_metres(
            footprint)
        evidence_out["span_m"] = _footprint_span_metres(footprint)
        evidence_out["centroid"] = (footprint.centroid.y,
                                    footprint.centroid.x)
        evidence_out["vertical_evidence"] = _vertical_evidence
        evidence_out["evidence_coverage"] = _evidence_coverage

    # Structure span gate (defect 2026-07-17): a structure whose footprint
    # ring spans past the cap is a residual field-spanning hull the
    # connector pre-filter did not fully un-chain — never a building-pad
    # seed.  Skip-and-report through the same path as the area cap.
    if DSF_OBJECT_MAX_STRUCTURE_SPAN_M > 0.0:
        span_metres = _footprint_span_metres(footprint)
        if span_metres > DSF_OBJECT_MAX_STRUCTURE_SPAN_M:
            UI.vprint(
                1,
                "  [object-footprints] structure footprint span "
                f"{span_metres:.0f} m exceeds the "
                f"{DSF_OBJECT_MAX_STRUCTURE_SPAN_M:.0f} m structure span "
                "gate (O4_DSF_OBJECT_MAX_STRUCTURE_SPAN_M) — skipped; a "
                "field-spanning structure is not a building pad.")
            return _record("max_structure_span")

    if DSF_OBJECT_MAX_FOOTPRINT_AREA_M2 > 0.0:
        area_square_metres = _footprint_area_square_metres(footprint)
        if area_square_metres > DSF_OBJECT_MAX_FOOTPRINT_AREA_M2:
            # Skip-and-report, never a quiet clip (spec section 2.3).
            UI.vprint(
                1,
                "  [object-footprints] structure footprint "
                f"{area_square_metres:.0f} m2 exceeds the "
                f"{DSF_OBJECT_MAX_FOOTPRINT_AREA_M2:.0f} m2 cap "
                "(O4_DSF_OBJECT_MAX_FOOTPRINT_AREA_M2) — skipped; "
                "the structure needs a pad review.")
            return _record("max_footprint_area")

    ring = [(float(longitude), float(latitude))
            for longitude, latitude in footprint.exterior.coords[:-1]]
    if len(ring) < 3:
        return _record("degenerate_ring")
    if evidence_out is not None:
        evidence_out["verdict"] = "ring"
    return ring


# ── FOOTPRINTS FROM THE STRUCTURE'S OWN GEOMETRY ─────────────────────
# (owner ruling 2026-08-30e, HECA building79; round-6 Family B law "a
# building pad is one building's footprint".)
#
# ``structure_ring`` above answers WHO QUALIFIES — every evidence gate
# (hull fill, tall-base fill, span, area cap, R18-2 coverage) is measured
# on the structure's convex HULL and stays exactly as it was.  What the
# hull is NOT is a footprint: at HECA the Tai Models pack draws a whole
# terminal complex as material-split texture pages, so one welded
# structure's base vertices spread over 308 x 338 m and their hull is
# 60,392 m² of ground — five buildings and the apron between them
# arriving as ONE flat pad (building79, 100,886 m², measured round 6b).
#
# A qualifying structure therefore contributes the PLAN SILHOUETTE of its
# own solid geometry, split into disjoint parts: one polygon per
# disjoint structure, and the ground between structures is not footprint.
#
# WHY THE FULL SOLID SILHOUETTE AND NOT THE BASE BAND (measured on
# building79's structures, 2026-08-30): the ``DSF_OBJECT_FOOTPRINT_HEIGHT_M``
# band exists to stop a roof overhang inflating a hull OF POINTS, and it
# cannot be reused here — this pack models buildings as walls with no
# ground-level floor slab, so the band's triangles are a few door sills.
# The 22,743 m² structure's base-band union is 659 m² in 18 scraps where
# its solid silhouette is 21,974 m² in ONE 220 x 221 m part; banding the
# silhouette would delete the building instead of shrinking the pad.  The
# silhouette's own overshoot is the roof overhang — metres against the
# hull's hundreds of metres, and in the SAFE direction (never a smaller
# pad than the walls stand on).

#: A union component below this is the numerical residue of coincident
#: triangles (a seam, a decal quad), never a building.  A CONSTANT, not a
#: gate: the union already drops zero-area triangles, and every consumer
#: of a ring downstream keys on its index, so emitting sub-square-metre
#: slivers as building pads is cost without information.
FOOTPRINT_MIN_PART_AREA_M2 = 1.0


def structure_footprint_parts(
    structure: Structure,
    geometry_by_resource: dict[str, ObjectGeometry],
    placements: list[ObjectPlacement],
    hull_ring: list[tuple[float, float]],
) -> tuple[list[list[tuple[float, float]]], str]:
    """The footprint a QUALIFYING structure contributes: one unclosed
    ``(longitude, latitude)`` ring per disjoint part of its own solid
    geometry, largest first.

    ``hull_ring`` is the ring :func:`structure_ring` returned for the
    same structure — the FALLBACK.  Degenerate geometry (no projectable
    triangle, a union that collapses, nothing above
    :data:`FOOTPRINT_MIN_PART_AREA_M2`) never yields zero footprint for a
    structure that has already passed the evidence gates; it falls back
    to the hull and says so.

    Returns ``(rings, source)`` where ``source`` is ``"structure"`` or
    ``"hull_fallback"`` — the caller records it per object, so a
    fallback is reported rather than silent.

    The qualification verdict is NOT re-decided here: this function is
    only ever called for a structure ``structure_ring`` admitted, and it
    applies no gate of its own.
    """
    placement_by_resource = {
        placement.resource_path: placement for placement in placements}
    triangle_corner_points: list = []
    for resource_path, triangles in structure.triangles_by_resource.items():
        geometry = geometry_by_resource.get(resource_path)
        placement = placement_by_resource.get(resource_path)
        if geometry is None or placement is None or not triangles:
            continue
        # Project each vertex through its OWN object's placement — the
        # same per-object anchor rule ``structure_ring`` uses (spec
        # section 2.4), memoised per vertex index within the resource.
        projected_by_vertex_index: dict[int, tuple[float, float]] = {}
        for triangle in triangles:
            corner_points = []
            for vertex_index in triangle:
                point = projected_by_vertex_index.get(vertex_index)
                if point is None:
                    local_x, _local_y, local_z = geometry.vertices[
                        vertex_index]
                    latitude, longitude = obj8_reader.local_offset_to_lonlat(
                        placement.latitude,
                        placement.longitude,
                        placement.heading_degrees,
                        local_x,
                        local_z,
                    )
                    point = (longitude, latitude)
                    projected_by_vertex_index[vertex_index] = point
                corner_points.append(point)
            if len(corner_points) >= 3:
                triangle_corner_points.append(tuple(corner_points))

    rings: list[list[tuple[float, float]]] = []
    for part in _triangle_union_parts(triangle_corner_points):
        if _footprint_area_square_metres(part) < FOOTPRINT_MIN_PART_AREA_M2:
            continue
        ring = [(float(longitude), float(latitude))
                for longitude, latitude in part.exterior.coords[:-1]]
        if len(ring) >= 3:
            rings.append(ring)
    if not rings:
        return [list(hull_ring)], "hull_fallback"
    return rings, "structure"
