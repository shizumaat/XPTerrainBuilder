"""Tests for the bare tunnel-portal FACE feature (user 2026-07-17, EGGW).

Some packs author a road tunnel's portals as nothing but a textured face
quad hanging BELOW grade — a handful of soft triangles from ``y ~ 0`` down
to the road deck.  Such a face matches neither the tunnel signature nor
any bridge signature, so two new pieces recognise and use it:

A. ``object_terrain_features._detect_portal_faces`` — the resource-level
   signature gate (single plain-``OBJECT`` placement, 1..8 soft solid
   triangles, ``min y <= -2``, ``max y <= +1``, height ``>= 2``, min-
   rotated-rect long side ``4..60 m``), plus the exclusion wiring that
   drops a recognised face's resource from the Phase 2 y-bake.

B. ``bridges._detect_tunnel_portal_pairs`` — face candidates pair only
   with each other, by mutual parallelism of the two face lines AND the
   connecting segment CROSSING the mean face line, inside the spacing
   window, over a buried body; a mapped ``tunnel=yes`` way between the
   faces suppresses the pair (OSM owns the crossing).

All fixtures are synthetic (ruling R6): geometry, classification records,
DEM sampler and road-layer loader are built / monkeypatched in code — no
third-party pack content enters the repository.  Mirrors the geometry-
builder idiom of ``tests/test_object_terrain_features.py`` and the
classification/layout idiom of ``tests/test_object_bridge_terrain.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.obj8_reader import ObjectGeometry, ObjectPlacement  # noqa: E402

ANCHOR_LATITUDE = 51.874
ANCHOR_LONGITUDE = -0.368
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
TILE_LATITUDE = 51
TILE_LONGITUDE = -1

_PORTAL_RESOURCE = "Objects/Airport/portal_face.obj"


# ---------------------------------------------------------------------------
# geometry + placement builders (synthetic, object local metre frame)
# ---------------------------------------------------------------------------
def _portal_face_geometry(
    *,
    width_m: float = 20.0,
    min_y_m: float = -8.0,
    max_y_m: float = 0.0,
    segments: int = 1,
    first_triangle_hardness: str | None = None,
    tilt_m: float = 0.2,
) -> ObjectGeometry:
    """A near-vertical face quad spanning ``width_m`` horizontally (along
    local z) and ``min_y_m..max_y_m`` vertically, split into ``segments``
    (2 triangles each).  The small ``tilt_m`` in x keeps the projected
    footprint a genuine 2-D sliver so the min-rotated-rect width is exact.
    """
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    hardness: list[str] = []
    z_start = -width_m / 2.0
    for segment in range(segments):
        z_a = z_start + width_m * segment / segments
        z_b = z_start + width_m * (segment + 1) / segments
        base = len(vertices)
        vertices.extend([
            (0.0, min_y_m, z_a),
            (0.0, min_y_m, z_b),
            (tilt_m, max_y_m, z_b),
            (tilt_m, max_y_m, z_a),
        ])
        triangles.append((base, base + 1, base + 2))
        triangles.append((base, base + 2, base + 3))
        hardness.extend(["", ""])
    if first_triangle_hardness is not None:
        hardness[0] = first_triangle_hardness
    return ObjectGeometry(
        vertices=vertices,
        solid_triangles=triangles,
        draped_triangles=[],
        positional_commands=[],
        animation_block_count=0,
        level_of_detail_count=0,
        vertex_line_indices=list(range(len(vertices))),
        solid_triangle_hardness=tuple(hardness),
    )


def _placement(
    resource: str = _PORTAL_RESOURCE,
    *,
    placement_kind: str = "OBJECT",
) -> ObjectPlacement:
    return ObjectPlacement(
        definition_index=0,
        resource_path=resource,
        longitude=ANCHOR_LONGITUDE,
        latitude=ANCHOR_LATITUDE,
        heading_degrees=0.0,
        placement_kind=placement_kind,
    )


# ---------------------------------------------------------------------------
# A. portal-face detection
# ---------------------------------------------------------------------------
class TestPortalFaceDetection:
    """``_detect_portal_faces`` recognises a single below-grade soft face
    quad and rejects everything outside the signature."""

    def test_vertical_soft_quad_is_detected(self) -> None:
        faces = otf._detect_portal_faces(
            [_placement()], {_PORTAL_RESOURCE: _portal_face_geometry()})
        assert len(faces) == 1
        face = faces[0]
        assert face.object_resources == [_PORTAL_RESOURCE]
        assert face.face_width_m == pytest.approx(20.0, abs=0.1)
        assert face.face_min_y_m == pytest.approx(-8.0)
        assert face.face_max_y_m == pytest.approx(0.0)
        assert face.deck_top_y_m == pytest.approx(8.0)
        # A north-south face line (long side along north); the implied
        # tunnel axis is its perpendicular (+90 deg).
        assert face.face_line_bearing_degrees == pytest.approx(0.0, abs=0.5)
        assert face.heading_degrees == pytest.approx(90.0, abs=0.5)
        assert face.face_hangs_below is True

    def test_oblique_face_line_carries_its_bearing(self) -> None:
        # A portal face is NOT necessarily perpendicular to the tunnel axis
        # (EGGW: the taxiway edge crosses the road obliquely).  A vertical
        # face along the x=z diagonal projects to a face line at 135 deg;
        # the implied axis is its perpendicular (45 deg), never derived by
        # assuming face-perpendicular-equals-axis.
        half_diagonal = 14.142  # long side ~40 m along the x=z diagonal
        vertices = [
            (-half_diagonal, -8.0, -half_diagonal),
            (half_diagonal, -8.0, half_diagonal),
            (half_diagonal + 0.14, 0.0, half_diagonal - 0.14),
            (-half_diagonal + 0.14, 0.0, -half_diagonal - 0.14),
        ]
        geometry = ObjectGeometry(
            vertices=vertices,
            solid_triangles=[(0, 1, 2), (0, 2, 3)],
            draped_triangles=[],
            positional_commands=[],
            animation_block_count=0,
            level_of_detail_count=0,
            vertex_line_indices=[0, 1, 2, 3],
            solid_triangle_hardness=("", ""),
        )
        faces = otf._detect_portal_faces(
            [_placement()], {_PORTAL_RESOURCE: geometry})
        assert len(faces) == 1
        face = faces[0]
        # A genuinely oblique face line (not axis-aligned).
        assert face.face_line_bearing_degrees == pytest.approx(135.0, abs=1.0)
        assert face.face_width_m == pytest.approx(40.0, abs=0.5)
        expected_axis = (face.face_line_bearing_degrees + 90.0) % 180.0
        assert face.heading_degrees == pytest.approx(expected_axis, abs=0.5)
        assert face.heading_degrees == pytest.approx(45.0, abs=1.0)

    def test_hard_triangle_is_rejected(self) -> None:
        # Anything drivable is the A6 tunnel signature's business.
        faces = otf._detect_portal_faces(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry(
                first_triangle_hardness="hard")})
        assert faces == []

    def test_too_many_triangles_is_rejected(self) -> None:
        # 5 segments => 10 solid triangles > PORTAL_FACE_MAX_SOLID_TRIANGLES.
        assert otf.PORTAL_FACE_MAX_SOLID_TRIANGLES == 8
        faces = otf._detect_portal_faces(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry(segments=5)})
        assert faces == []

    def test_too_shallow_face_is_rejected(self) -> None:
        # min y = -1 sits above the -2 m depth floor.
        faces = otf._detect_portal_faces(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry(
                min_y_m=-1.0, max_y_m=0.0)})
        assert faces == []

    def test_too_narrow_face_is_rejected(self) -> None:
        faces = otf._detect_portal_faces(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry(width_m=2.0)})
        assert faces == []

    def test_too_wide_face_is_rejected(self) -> None:
        faces = otf._detect_portal_faces(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry(width_m=80.0)})
        assert faces == []

    def test_multiple_placements_of_one_resource_are_rejected(self) -> None:
        # A face shared by N placements cannot mark N distinct mouths.
        faces = otf._detect_portal_faces(
            [_placement(), _placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry()})
        assert faces == []

    def test_object_agl_placement_is_rejected(self) -> None:
        # Negative-AGL rows already carry the A6 tunnel signature.
        faces = otf._detect_portal_faces(
            [_placement(placement_kind="OBJECT_AGL")],
            {_PORTAL_RESOURCE: _portal_face_geometry()})
        assert faces == []


class TestPortalFaceClassificationExclusion:
    """A recognised face surfaces in ``ClassificationResult.portal_faces``
    and its resource joins ``exclusions`` (dropped from the Phase 2 bake)."""

    def test_face_resource_lands_in_exclusions(self) -> None:
        result = otf.classify_object_terrain_features(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry()},
            pack_root="PACK",
        )
        assert len(result.portal_faces) == 1
        assert result.portal_faces[0].object_resources == [_PORTAL_RESOURCE]
        assert (("PACK", _PORTAL_RESOURCE)) in result.exclusions

    def test_non_face_object_is_not_excluded(self) -> None:
        # A shallow (non-portal) quad is neither a portal face nor excluded.
        result = otf.classify_object_terrain_features(
            [_placement()],
            {_PORTAL_RESOURCE: _portal_face_geometry(
                min_y_m=-1.0, max_y_m=0.0)},
            pack_root="PACK",
        )
        assert result.portal_faces == []
        assert ("PACK", _PORTAL_RESOURCE) not in result.exclusions


