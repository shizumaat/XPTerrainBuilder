"""THE DEGENERATE FACE GETS NO INTERP_ALT SEED (RULINGS 2026-09-09i (2)).

Both INTERP_ALT seeders place their seed at the representative point of a
face of a SHAPELY arrangement, while ``audit_interp_alt_seed_sealing`` —
and Triangle4XP's own point location after it — reads the arrangement
``O4_Vector_Utils.Vector_Map`` built from the same lines through
``insert_way(check=True)``.  The two agree wherever a face has room.

MEASURED (HECA +30+031, the patch of 2026-09-09 14:05): six coincident
bank level rings share a node A exactly; one of them carries an extra
node C that the other five pass 2.7 NANOMETRES clear of; and the two
noders answer that with a triangle of 2.0e-9 m^2 whose corners they place
1.5e-14 deg apart.  The seed shapely put inside its own triangle stood
1.7 nanometres OUTSIDE the map's, and the tile mesh REFUSED — with no way
rejected, split or moved (all 9,336 vertices of the six rings are in the
map, and both arrangements hold the sliver).

A face that small holds no mesh vertex and no triangle a sim can render,
so it needs no seed, and no consumer can locate it identically.  The
coordinates below are HECA's own: A and its neighbouring shared node, and
C placed 3e-14 deg off the segment between them.

Headless: production's own ``Vector_Map`` and ``O4_Vector_Map``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy
from shapely import geometry, ops

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

#: Two nodes HECA's six coincident bank level rings share exactly.
A = (0.41367461122, 0.12822382732)
D = (0.41366859242, 0.12822486347)
#: The rest of a ring big enough to be a real face.
FAR = [(0.4130, 0.1290), (0.4140, 0.1290)]
#: How far off the A->D segment the sixth ring's extra node stands, in
#: degrees — the measured 2.7 nanometres, rounded up.
OFFSET_DEG = 3.0e-14


def _extra_node():
    ux, uy = D[0] - A[0], D[1] - A[1]
    length = math.hypot(ux, uy)
    px, py = -uy / length, ux / length
    return (A[0] + 0.5 * ux + OFFSET_DEG * px,
            A[1] + 0.5 * uy + OFFSET_DEG * py)


def _rings():
    """The five rings' straight edge, and the sixth ring's extra node."""
    straight = [A, D] + FAR + [A]
    with_node = [A, _extra_node(), D] + FAR + [A]
    return straight, with_node


def _faces(rings):
    polys = [geometry.Polygon(ring) for ring in rings]
    assert all(poly.is_valid and poly.area for poly in polys)
    boundaries = ops.unary_union([poly.boundary for poly in polys])
    return polys, list(ops.polygonize(boundaries))


def test_two_nanometre_apart_ways_node_into_a_sliver_face():
    """The mechanism itself: the noders mint a sliver of ~1e-9 m^2."""
    _polys, faces = _faces(_rings())
    areas = sorted(face.area * VMAP._SQ_M_PER_SQ_DEG for face in faces)
    assert len(faces) == 2
    assert areas[0] < 1.0e-6      # the sliver: below one square millimetre
    assert areas[-1] > 1000.0     # the real face


def test_a_needle_over_the_area_floor_MOVES_its_seed_off_the_line():
    """The area is only a proxy.  MEASURED on a second arm of the same
    patch (level rings 5 m apart instead of 10): a NEEDLE of 1.14 m^2 —
    four corners spanning 50 m, a couple of centimetres wide — put its
    representative point on the map's own line and the audit refused
    again.  Its own coordinates, from that arm's patch.

    AMENDED 2026-09-14 (owner: the tunnel cuts): the answer is to MOVE
    the seed, not to throw the face away.  A face this size is a tunnel
    wall strip's size, and a face with no seed keeps the RAW DEM — which
    is the tunnel filling back in.  The needle's own pole of
    inaccessibility stands 0.2475 m clear of its boundary and survives
    the map's 1e-9 degree grid, so it is a perfectly good seed."""
    needle = geometry.Polygon([
        (0.41822324592771959, 0.12614235266942569),
        (0.41823185575000110, 0.12611145576000027),
        (0.41822450708000147, 0.12613782693999909),
        (0.41817944277000052, 0.12613129950999991),
    ])
    assert needle.area * VMAP._SQ_M_PER_SQ_DEG > 1.0    # over the area floor
    graze = needle.representative_point()
    assert needle.exterior.distance(graze) < VMAP.INTERP_ALT_SEED_CLEARANCE_DEG
    seed = VMAP.interp_alt_seed_point(needle)
    assert seed is not None and needle.contains(seed)
    assert seed != graze
    # clear of the line, and still inside after the map rounds it
    assert needle.boundary.distance(seed) > 100.0 * VMAP.INTERP_ALT_SEED_SNAP_DEG
    assert VMAP._survives_encoding(needle, seed)


def test_a_real_face_keeps_its_seed():
    """The clearance refuses needles, never rooms: a 100 m square's
    representative point stands metres clear of its own boundary."""
    room = geometry.Polygon([(0.10, 0.10), (0.101, 0.10),
                             (0.101, 0.101), (0.10, 0.101)])
    seed = VMAP.interp_alt_seed_point(room)
    assert seed is not None and room.contains(seed)


def test_the_floor_separates_the_sliver_from_the_real_face():
    _polys, faces = _faces(_rings())
    flags = sorted(VMAP.is_degenerate_interp_alt_face(f) for f in faces)
    assert flags == [False, True]


def test_subcell_seeder_places_no_seed_in_a_degenerate_face():
    """The production path: ``seed_interp_alt_subcells`` seeds the real
    face and skips the sliver."""
    rings = _rings()
    polys, faces = _faces(rings)
    vector_map = VECT.Vector_Map()
    for ring in rings:
        way = numpy.array(ring, dtype=float)
        vector_map.insert_way(
            numpy.hstack([way, numpy.zeros((len(way), 1))]),
            VMAP.PATCH_RING_MARKER,
            check=True,
        )
    vector_map.interp_alt_patch_polygons = polys
    vector_map.interp_alt_patches_area = ops.unary_union(polys)

    added = VMAP.seed_interp_alt_subcells(vector_map)

    assert added == 1, "the sliver must not be seeded"
    seeds = vector_map.seeds.get("INTERP_ALT", [])
    assert len(seeds) == 1
    real = max(faces, key=lambda f: f.area)
    assert real.contains(geometry.Point(seeds[0][0], seeds[0][1]))


def test_the_audit_accepts_the_floor_seeded_map():
    rings = _rings()
    polys, _faces_ = _faces(rings)
    vector_map = VECT.Vector_Map()
    for ring in rings:
        way = numpy.array(ring, dtype=float)
        vector_map.insert_way(
            numpy.hstack([way, numpy.zeros((len(way), 1))]),
            VMAP.PATCH_RING_MARKER,
            check=True,
        )
    vector_map.interp_alt_patch_polygons = polys
    vector_map.interp_alt_patches_area = ops.unary_union(polys)
    VMAP.seed_interp_alt_subcells(vector_map)

    assert VMAP.audit_interp_alt_seed_sealing(vector_map) == 1


# ── THE CLEARANCE IS THE ENCODING'S QUANTUM (VHHH, 2026-09-14) ─────────
#
# The owner's 1.0.331 build of +22+113 died in the mesh step:
# ``UnsealedInterpAltSeed`` on ONE of 4,095 seeds, at tile-relative
# (0.876712142, 0.321098147).  MEASURED: that seed is a face seed of
# ``adjacent_ground:runway:4:zone2#24`` (a 767 m x 5.2 km graded strip)
# standing **0.856 mm** inside its own raw face — a horizontal-scanline
# ``representative_point`` that grazed the boundary — while in the
# ENCODED arrangement it lies OUTSIDE every bounded face (one marked
# edge 0.78 mm away, the next 13 m away).  The clearance floor was
# 1e-11 degrees, ONE MICROMETRE: a hundred times finer than the vector
# map's own ``snap_to_grid(9)`` grid (0.11 mm) and far under
# ``are_encroached``'s 1e-8 and §39 (i)'s weld.
#
# ATTRIBUTED INTERVENTIONALLY, not inferred: the same seed refuses with
# ``OPEN_BREAKLINE_FEATURES = ()``, i.e. with RULINGS 2026-09-13cp's
# marker change fully OFF.  It is the seeder's floor, not the marker.

def test_the_clearance_is_stated_in_metres_and_derived():
    assert VMAP.INTERP_ALT_SEED_CLEARANCE_M == 0.5
    assert abs(VMAP.INTERP_ALT_SEED_CLEARANCE_DEG - 0.5 / 111320.0) < 1e-18
    # and it is far COARSER than the vector map's own coordinate grid,
    # which is the whole point (snap_to_grid(9) = 1e-9 degrees).
    assert VMAP.INTERP_ALT_SEED_CLEARANCE_DEG > 1.0e-9 * 100


def test_a_seed_grazing_its_own_boundary_MOVES_to_the_deepest_point():
    """VHHH's class: an AMPLE face whose scanline representative point
    grazes the boundary keeps its seed — at the pole of inaccessibility,
    not at the graze.  Dropping it would throw away a real region."""
    # An AMPLE block (1 km x 11 m) with a 0.4 m-wide, 110 m-tall SPIKE on
    # top: the face's mid-height scanline runs through the spike, so the
    # representative point grazes, while the block is metres deep.
    w = 0.2 / 111320.0
    face = geometry.Polygon([
        (0.100000, 0.100000), (0.110000, 0.100000),
        (0.110000, 0.100100), (0.105000 + w, 0.100100),
        (0.105000 + w, 0.101100), (0.105000 - w, 0.101100),
        (0.105000 - w, 0.100100), (0.100000, 0.100100),
    ])
    graze = face.representative_point()
    assert face.boundary.distance(graze) < VMAP.INTERP_ALT_SEED_CLEARANCE_DEG
    seed = VMAP.interp_alt_seed_point(face)
    assert seed is not None and face.contains(seed)
    assert face.boundary.distance(seed) >= VMAP.INTERP_ALT_SEED_CLEARANCE_DEG
    assert not VMAP.is_degenerate_interp_alt_face(face)


def test_a_TUNNEL_WALL_WIDTH_face_keeps_its_seed():
    """NARROW IS NOT DEGENERATE (owner 2026-09-14, the VHHH tunnels).

    A 0.6 m-wide, 60 m-long strip is a tunnel WALL face — the piece
    between a ramp and its wall.  The round-3 floor dropped every face
    whose inscribed radius was under 0.5 m, and a dropped face gets no
    INTERP_ALT seed, so its triangles keep the RAW DEM: the cut fills
    back in.  It is seeded, at its pole, with the clearance it can
    afford."""
    w = 0.3 / 111320.0                       # half-width 0.3 m
    wall = geometry.Polygon([
        (0.100, 0.100 - w), (0.1006, 0.100 - w),
        (0.1006, 0.100 + w), (0.100, 0.100 + w),
    ])
    (_pole, inradius) = VMAP._pole_of_inaccessibility(wall)
    assert inradius * 111320.0 < VMAP.INTERP_ALT_SEED_CLEARANCE_M
    seed = VMAP.interp_alt_seed_point(wall)
    assert seed is not None and wall.contains(seed)
    assert not VMAP.is_degenerate_interp_alt_face(wall)
    assert VMAP._survives_encoding(wall, seed)


def test_only_the_HAIRLINE_floor_drops_a_face():
    """The one width that drops a face is the hairline degenerate bar
    (10 mm), and it is the mesh module's own constant, not a second
    spelling."""
    import O4_Mesh_Utils as MESH

    assert VMAP.INTERP_ALT_SEED_DEGENERATE_M == MESH.HAIRLINE_DEGENERATE_M
    w = 0.004 / 111320.0                     # 8 mm wide, under the bar
    hair = geometry.Polygon([
        (0.100, 0.100 - w), (0.109, 0.100 - w),
        (0.109, 0.100 + w), (0.100, 0.100 + w),
    ])
    assert hair.area * VMAP._SQ_M_PER_SQ_DEG > 1.0   # over the AREA floor
    assert VMAP.interp_alt_seed_point(hair) is None
    assert VMAP.is_degenerate_interp_alt_face(hair)


def test_a_seed_that_the_ENCODING_GRID_pushes_out_is_refused():
    """The VHHH +22+113 class, checked where the seed is CHOSEN: the map
    rounds every coordinate onto a 1e-9 degree grid, and a seed that is
    not inside its own face after that rounding kills the tile build in
    the mesh step."""
    inside = geometry.Point(0.1000000004, 0.1000000004)
    tiny = inside.buffer(0.3e-9, quad_segs=32)
    assert tiny.contains(inside)
    assert not VMAP._survives_encoding(tiny, inside)   # snaps to a corner
    assert VMAP.interp_alt_seed_point(tiny) is None


def test_a_seed_grazing_a_HOLE_is_as_unreliable_as_one_grazing_the_rim():
    """``boundary``, not ``exterior``: the encoded map can move a hole's
    edge exactly as it can move the outer ring."""
    ring = geometry.Polygon([(0.100, 0.100), (0.102, 0.100),
                             (0.102, 0.102), (0.100, 0.102)])
    hole = geometry.Point(0.101, 0.101).buffer(0.0009, quad_segs=64)
    face = ring.difference(hole)
    seed = VMAP.interp_alt_seed_point(face)
    assert seed is None or (
        face.boundary.distance(seed) >= VMAP.INTERP_ALT_SEED_CLEARANCE_DEG)
