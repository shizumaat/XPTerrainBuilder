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


def test_a_needle_over_the_area_floor_is_refused_on_CLEARANCE():
    """The area is only a proxy.  MEASURED on a second arm of the same
    patch (level rings 5 m apart instead of 10): a NEEDLE of 1.14 m^2 —
    four corners spanning 50 m, a couple of centimetres wide — put its
    representative point on the map's own line and the audit refused
    again.  Its own coordinates, from that arm's patch."""
    needle = geometry.Polygon([
        (0.41822324592771959, 0.12614235266942569),
        (0.41823185575000110, 0.12611145576000027),
        (0.41822450708000147, 0.12613782693999909),
        (0.41817944277000052, 0.12613129950999991),
    ])
    assert needle.area * VMAP._SQ_M_PER_SQ_DEG > 1.0    # over the area floor
    seed = needle.representative_point()
    assert needle.exterior.distance(seed) < VMAP.INTERP_ALT_SEED_CLEARANCE_DEG
    assert VMAP.interp_alt_seed_point(needle) is None


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
