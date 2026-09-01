"""OBJ8 scenery-object building footprints — workstream W6 of the DSF
object integration (``docs/dsf_object_integration_spec.md`` section
4-W6, rulings R3/R4/R5, invariant I-5).

Three tiers:

(a) HERMETIC ``object_footprints.structure_ring`` tests — the
    ``Structure`` / ``ObjectGeometry`` inputs are constructed directly
    (no file parsing, no partition) and the placement projection is a
    local equirectangular fake mirroring ``obj8_reader``'s documented
    convention, so nothing here waits on workstream W2.
(b) ``dsf_reader.read_dsf_object_buildings`` plumbing tests — fake
    ``.dsf`` + pre-seeded backdated ``.dsf.text`` (harness pattern (b)
    from ``tests/test_dsf_buildings.py``), with
    ``object_anchor.discover_object_pools`` / ``partition_structures``
    monkeypatched to trivial fakes (they are Wave-2 stubs).  A final
    variant drops the ``obj8_reader`` monkeypatches and runs against the
    real workstream-W2 reader; it skips while that reader still raises
    ``NotImplementedError``.
(c) Flag gating and the shared building-admission helper the pipeline
    loop refactor introduced — the ``.fac`` facade path must be
    behavior-identical (``tests/test_dsf_buildings.py`` and
    ``tests/test_dsf_surface_pavement.py`` prove the reader side).
"""
import math
import os

import pytest
from shapely.geometry import Polygon

from auto_patch import config
from auto_patch import dsf_reader as D
from auto_patch import obj8_reader
from auto_patch import object_anchor
from auto_patch import object_footprints
# Imported at module scope ON PURPOSE: ``object_terrain_features`` binds
# ``discover_object_pools`` by from-import at its first import.  The
# reader imports it lazily, so without this line the first harness test
# to run in a worker would import it while the fixture's fake is
# installed, freezing that test's fake (a dead closure after teardown)
# into the classifier for the rest of the process.  Importing here
# captures the REAL binding before any monkeypatch can run.
from auto_patch import object_terrain_features
from auto_patch import pipeline

METRES_PER_DEGREE_LATITUDE = obj8_reader.METRES_PER_DEGREE_LATITUDE

ANCHOR_LATITUDE = 35.0
ANCHOR_LONGITUDE = -80.0


@pytest.fixture(autouse=True)
def sandbox_ortho4xp_data_root(tmp_path, monkeypatch):
    """USER RULING 2026-07-15 moved the sidecar caches under the
    Ortho4XP data root (``Airport_mod_cache/<pack>/``).  In a source
    checkout the data root resolves to the current working directory, so
    without this pin any test that exercises ``read_dsf_object_buildings``
    would write ``Airport_mod_cache/`` into the repository.  Sandbox
    every test in this module (``ORTHO4XP_DATA_ROOT`` wins
    ``O4_File_Names.resolve_data_root``)."""
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT",
                       str(tmp_path / "o4_data_root"))


@pytest.fixture(autouse=True)
def disable_minimum_building_height(monkeypatch):
    """The geometric fixtures in this file are deliberately FLAT slabs
    (walls would obscure the ring-shape assertions), which the
    amendment-A11 ground-plate filter would reject wholesale.  Default
    it off for this file; ``TestStructureRingMinimumBuildingHeight``
    re-enables it explicitly to test the filter itself.  The TALL-BASE
    fill floor rejects flat slabs for the same reason (no tall member)
    — off here too; ``TestStructureRingTallBaseFill`` re-enables it
    per test."""
    monkeypatch.setattr(config, "DSF_OBJECT_MIN_BUILDING_HEIGHT_M", 0.0)
    monkeypatch.setattr(config, "DSF_OBJECT_MIN_TALL_BASE_FILL", 0.0)


# ── shared construction helpers ──────────────────────────────────────

def equirectangular_local_offset_to_lonlat(
        anchor_latitude, anchor_longitude, heading_degrees,
        local_x, local_z):
    """Test double for ``obj8_reader.local_offset_to_lonlat``, mirroring
    its documented convention (local +x = east, +z = south; heading
    clockwise from north) so tier (a) never waits on workstream W2."""
    heading = math.radians(heading_degrees)
    east = local_x * math.cos(heading) - local_z * math.sin(heading)
    south = local_x * math.sin(heading) + local_z * math.cos(heading)
    metres_per_degree_longitude = (
        METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(anchor_latitude)))
    return (anchor_latitude - south / METRES_PER_DEGREE_LATITUDE,
            anchor_longitude + east / metres_per_degree_longitude)


@pytest.fixture()
def fake_projection(monkeypatch):
    monkeypatch.setattr(obj8_reader, "local_offset_to_lonlat",
                        equirectangular_local_offset_to_lonlat)


def make_geometry(vertices, solid_triangles):
    return obj8_reader.ObjectGeometry(
        vertices=list(vertices),
        solid_triangles=list(solid_triangles),
        draped_triangles=[],
        positional_commands=[],
        animation_block_count=0,
        level_of_detail_count=0,
        vertex_line_indices=list(range(len(vertices))),
    )


def make_placement(resource_path,
                   longitude=ANCHOR_LONGITUDE,
                   latitude=ANCHOR_LATITUDE,
                   heading_degrees=0.0,
                   definition_index=0):
    return obj8_reader.ObjectPlacement(
        definition_index=definition_index,
        resource_path=resource_path,
        longitude=longitude,
        latitude=latitude,
        heading_degrees=heading_degrees,
    )


def make_structure(triangles_by_resource, minimum_base_y_by_resource,
                   *, is_ground_touching=True):
    return object_anchor.Structure(
        triangles_by_resource=triangles_by_resource,
        surface_area_square_metres=1.0,
        centroid_latitude=ANCHOR_LATITUDE,
        centroid_longitude=ANCHOR_LONGITUDE,
        minimum_base_y_by_resource=minimum_base_y_by_resource,
        is_ground_touching=is_ground_touching,
        ground_span_metres=None,
        needs_pad=False,
        skip_reason=None,
        inherited_from_structure_index=None,
    )


def ring_to_local_metres(ring,
                         anchor_latitude=ANCHOR_LATITUDE,
                         anchor_longitude=ANCHOR_LONGITUDE):
    """Invert the equirectangular projection back to heading-0 local
    ``(x = east, z = south)`` metres for geometric assertions."""
    metres_per_degree_longitude = (
        METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(anchor_latitude)))
    return [
        ((longitude - anchor_longitude) * metres_per_degree_longitude,
         -(latitude - anchor_latitude) * METRES_PER_DEGREE_LATITUDE)
        for longitude, latitude in ring
    ]


# The L-shaped ground plan of tier (a): a 20 x 10 slab plus a 10 x 10
# wing, 300 square metres, whose convex hull (350 square metres) swallows
# the notch corner at (10, 10) — ruling R3's known, accepted cost.
L_SHAPE_VERTICES = [
    (0.0, 0.0, 0.0),     # 0
    (20.0, 0.0, 0.0),    # 1
    (20.0, 0.0, 10.0),   # 2
    (10.0, 0.0, 10.0),   # 3  the notch corner
    (10.0, 0.0, 20.0),   # 4
    (0.0, 0.0, 20.0),    # 5
    (0.0, 0.0, 10.0),    # 6
]
L_SHAPE_TRIANGLES = [(0, 1, 2), (2, 6, 0), (6, 3, 4), (4, 5, 6)]


# ── tier (a): hermetic structure_ring ────────────────────────────────

class TestStructureRingHull:
    def test_hull_swallows_l_shape_notch(self, fake_projection):
        geometry = make_geometry(L_SHAPE_VERTICES, L_SHAPE_TRIANGLES)
        structure = make_structure({"a.obj": L_SHAPE_TRIANGLES},
                                   {"a.obj": 0.0})
        ring = object_footprints.structure_ring(
            structure, {"a.obj": geometry}, [make_placement("a.obj")])
        assert ring is not None
        # Unclosed: the first vertex is not repeated.
        assert ring[0] != ring[-1]
        # (longitude, latitude) order: the first coordinate is the
        # longitude (near -80), not the latitude (near 35).
        for longitude, latitude in ring:
            assert abs(longitude - ANCHOR_LONGITUDE) < 0.01
            assert abs(latitude - ANCHOR_LATITUDE) < 0.01
        local = ring_to_local_metres(ring)
        # The EXPECTED hull is the 5-corner pentagon: the notch corner
        # (10, 10) is swallowed (ruling R3 — measure first, fidelity
        # behind DSF_OBJECT_FOOTPRINT_UNION).
        assert len(local) == 5
        assert all(math.hypot(x - 10.0, z - 10.0) > 0.5
                   for x, z in local)
        hull_polygon = Polygon(local)
        assert hull_polygon.area == pytest.approx(350.0, abs=2.0)
        # The swallowed notch region is inside the pad.
        from shapely.geometry import Point
        assert hull_polygon.contains(Point(14.0, 14.0))

    def test_footprint_height_filter_excludes_roof_overhang(
            self, fake_projection):
        # 10 x 10 walls on the ground, roof overhanging to 15 m at
        # y = 8 — the overhang must not inflate the pad.
        vertices = [
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
            (10.0, 0.0, 10.0), (0.0, 0.0, 10.0),
            (-5.0, 8.0, -5.0), (15.0, 8.0, -5.0),
            (15.0, 8.0, 15.0), (-5.0, 8.0, 15.0),
        ]
        triangles = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
        geometry = make_geometry(vertices, triangles)
        structure = make_structure({"a.obj": triangles}, {"a.obj": 0.0})
        ring = object_footprints.structure_ring(
            structure, {"a.obj": geometry}, [make_placement("a.obj")])
        assert ring is not None
        local = ring_to_local_metres(ring)
        xs = [x for x, _ in local]
        zs = [z for _, z in local]
        assert max(xs) == pytest.approx(10.0, abs=0.1)
        assert min(xs) == pytest.approx(0.0, abs=0.1)
        assert max(zs) == pytest.approx(10.0, abs=0.1)
        assert min(zs) == pytest.approx(0.0, abs=0.1)

    def test_fewer_than_three_base_vertices_falls_back_to_all(
            self, fake_projection):
        # Only 2 vertices within the 1.5 m base window — the footprint
        # falls back to ALL solid vertices (low flat objects).
        vertices = [
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
            (0.0, 5.0, 20.0), (10.0, 5.0, 20.0),
            (0.0, 5.0, 10.0), (10.0, 5.0, 10.0),
        ]
        triangles = [(0, 1, 4), (1, 5, 4), (4, 5, 2), (5, 3, 2)]
        geometry = make_geometry(vertices, triangles)
        structure = make_structure({"a.obj": triangles}, {"a.obj": 0.0})
        ring = object_footprints.structure_ring(
            structure, {"a.obj": geometry}, [make_placement("a.obj")])
        assert ring is not None
        local = ring_to_local_metres(ring)
        zs = [z for _, z in local]
        # Two base points alone are a degenerate (line) hull; the ring
        # spanning the full 0..20 depth proves the fallback engaged.
        assert max(zs) == pytest.approx(20.0, abs=0.1)
        assert min(zs) == pytest.approx(0.0, abs=0.1)

    def test_no_ground_contact_returns_none(self, fake_projection):
        geometry = make_geometry(L_SHAPE_VERTICES, L_SHAPE_TRIANGLES)
        structure = make_structure({"a.obj": L_SHAPE_TRIANGLES},
                                   {"a.obj": 6.0},
                                   is_ground_touching=False)
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry},
            [make_placement("a.obj")]) is None


class TestStructureRingMinimumBuildingHeight:
    """Amendment A11 (HECA Tai Models pack): a building has walls; a
    ground plate, sign or decal does not.  A near-flat structure gets no
    Phase-1 pad — ``heca_ground_polygon.obj`` spans 2.1 km and must
    never become a 2 km flat building pad."""

    # A 20 x 20 plate: solid, ground-touching, 0.2 m of vertical extent.
    PLATE_VERTICES = [
        (0.0, 0.0, 0.0), (20.0, 0.0, 0.0),
        (20.0, 0.2, 20.0), (0.0, 0.2, 20.0),
    ]
    PLATE_TRIANGLES = [(0, 1, 2), (0, 2, 3)]

    def _plate_ring(self):
        geometry = make_geometry(self.PLATE_VERTICES, self.PLATE_TRIANGLES)
        structure = make_structure({"a.obj": self.PLATE_TRIANGLES},
                                   {"a.obj": 0.0})
        return object_footprints.structure_ring(
            structure, {"a.obj": geometry}, [make_placement("a.obj")])

    def test_flat_plate_gets_no_pad(self, fake_projection, monkeypatch):
        monkeypatch.setattr(
            config, "DSF_OBJECT_MIN_BUILDING_HEIGHT_M", 2.5)
        assert self._plate_ring() is None

    def test_zero_disables_the_filter(self, fake_projection, monkeypatch):
        monkeypatch.setattr(
            config, "DSF_OBJECT_MIN_BUILDING_HEIGHT_M", 0.0)
        assert self._plate_ring() is not None

    def test_walled_building_passes_the_filter(self, fake_projection,
                                               monkeypatch):
        monkeypatch.setattr(
            config, "DSF_OBJECT_MIN_BUILDING_HEIGHT_M", 2.5)
        # The same plate with an 8 m roof slab above it: real walls.
        vertices = self.PLATE_VERTICES + [
            (0.0, 8.0, 0.0), (20.0, 8.0, 0.0),
            (20.0, 8.0, 20.0), (0.0, 8.0, 20.0),
        ]
        triangles = self.PLATE_TRIANGLES + [(4, 5, 6), (4, 6, 7)]
        geometry = make_geometry(vertices, triangles)
        structure = make_structure({"a.obj": triangles}, {"a.obj": 0.0})
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry},
            [make_placement("a.obj")]) is not None

    def test_area_cap_returns_none_and_reports(self, fake_projection,
                                               monkeypatch):
        geometry = make_geometry(L_SHAPE_VERTICES, L_SHAPE_TRIANGLES)
        structure = make_structure({"a.obj": L_SHAPE_TRIANGLES},
                                   {"a.obj": 0.0})
        placements = [make_placement("a.obj")]
        # Under the 100,000 m2 backstop default (defect 2026-07-17): the
        # 350 m2 hull is far below the cap and admitted.
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry}, placements) is not None
        # Cap enabled below the hull area: None, and reported.
        reports = []
        monkeypatch.setattr(
            object_footprints.UI, "vprint",
            lambda level, message: reports.append(message))
        monkeypatch.setattr(config, "DSF_OBJECT_MAX_FOOTPRINT_AREA_M2",
                            100.0)
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry}, placements) is None
        assert len(reports) == 1
        assert "exceeds" in reports[0] and "cap" in reports[0]

    def test_structure_span_gate_returns_none_and_reports(
            self, fake_projection, monkeypatch):
        # Defect 2026-07-17: a field-spanning structure (residual chained
        # hull) is skipped-and-reported through the same path as the area
        # cap.  A 600 m long, 10 m wide flat slab: 6,000 m2 (well under the
        # backstop) but its 600 m span trips the structure span gate.
        long_slab_vertices = [
            (0.0, 0.0, 0.0), (600.0, 0.0, 0.0),
            (600.0, 0.0, 10.0), (0.0, 0.0, 10.0),
        ]
        long_slab_triangles = [(0, 1, 2), (0, 2, 3)]
        geometry = make_geometry(long_slab_vertices, long_slab_triangles)
        structure = make_structure({"a.obj": long_slab_triangles},
                                   {"a.obj": 0.0})
        placements = [make_placement("a.obj")]
        # Gate disabled (the 0.0 shipping default): the slab is admitted.
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry}, placements) is not None
        # Gate enabled at 500 m: the 600 m-spanning slab is skipped-and-
        # reported through the same path as the area cap.
        reports = []
        monkeypatch.setattr(
            object_footprints.UI, "vprint",
            lambda level, message: reports.append(message))
        monkeypatch.setattr(config, "DSF_OBJECT_MAX_STRUCTURE_SPAN_M", 500.0)
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry}, placements) is None
        assert any("structure span gate" in message for message in reports)

    def test_two_placements_project_through_their_own_anchor(
            self, fake_projection):
        # One structure fed by TWO objects with different anchors and
        # headings (spec section 2.4: the anchor is a per-object
        # property).  Each object is the same local 10 x 10 slab; the
        # ring must span both PLACED positions.
        slab_vertices = [
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
            (10.0, 0.0, 10.0), (0.0, 0.0, 10.0),
        ]
        slab_triangles = [(0, 1, 2), (0, 2, 3)]
        geometry = make_geometry(slab_vertices, slab_triangles)
        metres_per_degree_longitude = (
            METRES_PER_DEGREE_LATITUDE
            * math.cos(math.radians(ANCHOR_LATITUDE)))
        placements = [
            make_placement("walls.obj", definition_index=0),
            # 100 m east, rotated 90 degrees clockwise: local +x maps
            # to south, local +z maps to west.
            make_placement(
                "roof.obj",
                longitude=(ANCHOR_LONGITUDE
                           + 100.0 / metres_per_degree_longitude),
                heading_degrees=90.0,
                definition_index=1),
        ]
        structure = make_structure(
            {"walls.obj": slab_triangles, "roof.obj": slab_triangles},
            {"walls.obj": 0.0, "roof.obj": 0.0})
        ring = object_footprints.structure_ring(
            structure,
            {"walls.obj": geometry, "roof.obj": geometry},
            placements)
        assert ring is not None
        local = ring_to_local_metres(ring)
        xs = [x for x, _ in local]
        zs = [z for _, z in local]
        # walls.obj covers x 0..10, z 0..10.  roof.obj at heading 90:
        # east = -z (90..100 from its +100 m anchor), south = x (0..10).
        assert min(xs) == pytest.approx(0.0, abs=0.1)
        assert max(xs) == pytest.approx(100.0, abs=0.1)
        assert min(zs) == pytest.approx(0.0, abs=0.1)
        assert max(zs) == pytest.approx(10.0, abs=0.1)


class TestStructureRingUnion:
    def test_union_ring_preserves_l_shape(self, fake_projection,
                                          monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_FOOTPRINT_UNION", True)
        geometry = make_geometry(L_SHAPE_VERTICES, L_SHAPE_TRIANGLES)
        structure = make_structure({"a.obj": L_SHAPE_TRIANGLES},
                                   {"a.obj": 0.0})
        ring = object_footprints.structure_ring(
            structure, {"a.obj": geometry}, [make_placement("a.obj")])
        assert ring is not None
        assert ring[0] != ring[-1]
        union_polygon = Polygon(ring_to_local_metres(ring))
        # The faithful ring keeps the notch: 300 m2, not the hull's 350.
        assert union_polygon.area == pytest.approx(300.0, abs=5.0)


# ── structure-walls footprints (owner ruling 2026-08-30e) ────────────
# ONE structure, drawn by one material-split texture page, can describe
# SEVERAL separate buildings; its convex hull is those buildings plus
# the ground between them (HECA building79: five buildings, one
# 100,886 m2 pad).  A qualifying structure contributes the plan
# silhouette of its OWN geometry, one ring per disjoint part.

# Two 20 x 20 boxes 20 m apart, each a floor at y = 0 and a roof at
# y = 8 — the spec's synthetic twin.  Hull: 60 x 20 = 1200 m2.  Own
# geometry: two 400 m2 parts with a 20 m gap between them.
TWO_BOX_VERTICES = [
    (0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 0.0, 20.0), (0.0, 0.0, 20.0),
    (0.0, 8.0, 0.0), (20.0, 8.0, 0.0), (20.0, 8.0, 20.0), (0.0, 8.0, 20.0),
    (40.0, 0.0, 0.0), (60.0, 0.0, 0.0), (60.0, 0.0, 20.0), (40.0, 0.0, 20.0),
    (40.0, 8.0, 0.0), (60.0, 8.0, 0.0), (60.0, 8.0, 20.0), (40.0, 8.0, 20.0),
]
TWO_BOX_TRIANGLES = [
    (0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
    (8, 9, 10), (8, 10, 11), (12, 13, 14), (12, 14, 15),
]

# A structure whose only geometry is VERTICAL: two wall quads standing
# on the ground, projecting to zero plan area.  The union degenerates,
# and a structure that has already passed the evidence gates must never
# come out with no footprint at all.
VERTICAL_ONLY_VERTICES = [
    (0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 8.0, 0.0), (0.0, 8.0, 0.0),
    (0.0, 0.0, 20.0), (20.0, 0.0, 20.0), (20.0, 8.0, 20.0), (0.0, 8.0, 20.0),
]
VERTICAL_ONLY_TRIANGLES = [
    (0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
]


class TestStructureFootprintParts:
    def _two_box_structure(self):
        geometry = make_geometry(TWO_BOX_VERTICES, TWO_BOX_TRIANGLES)
        structure = make_structure({"a.obj": TWO_BOX_TRIANGLES},
                                   {"a.obj": 0.0})
        return structure, {"a.obj": geometry}, [make_placement("a.obj")]

    def test_hull_still_swallows_the_gap(self, fake_projection):
        # The QUALIFICATION half is unchanged: structure_ring still
        # returns the structure's convex hull, gates and all.
        structure, geometry, placements = self._two_box_structure()
        ring = object_footprints.structure_ring(
            structure, geometry, placements)
        assert ring is not None
        assert Polygon(ring_to_local_metres(ring)).area == pytest.approx(
            1200.0, abs=10.0)

    def test_two_disjoint_boxes_yield_two_parts_with_a_gap(
            self, fake_projection):
        structure, geometry, placements = self._two_box_structure()
        hull_ring = object_footprints.structure_ring(
            structure, geometry, placements)
        parts, source = object_footprints.structure_footprint_parts(
            structure, geometry, placements, hull_ring)
        assert source == "structure"
        assert len(parts) == 2
        polygons = [Polygon(ring_to_local_metres(part)) for part in parts]
        for polygon in polygons:
            # Unclosed rings, same contract as structure_ring.
            assert polygon.area == pytest.approx(400.0, abs=5.0)
        for part in parts:
            assert part[0] != part[-1]
        # The GROUND BETWEEN the two buildings is not footprint — the
        # whole point of the ruling.
        from shapely.geometry import Point
        gap_centre = Point(30.0, 10.0)   # x = 30 m, z = 10 m (south)
        assert not any(polygon.contains(gap_centre)
                       for polygon in polygons)
        # ... and the hull DOES swallow it, which is the defect.
        assert Polygon(ring_to_local_metres(hull_ring)).contains(gap_centre)
        # Deterministic order: largest first (equal here, so the tie
        # breaks on bounds — never on GEOS ordering).
        assert [round(polygon.area) for polygon in polygons] == [400, 400]

    def test_degenerate_geometry_falls_back_to_the_hull(
            self, fake_projection):
        # Vertical-only geometry projects to zero plan area; a
        # qualifying structure must never lose its pad entirely.
        geometry = make_geometry(VERTICAL_ONLY_VERTICES,
                                 VERTICAL_ONLY_TRIANGLES)
        structure = make_structure({"a.obj": VERTICAL_ONLY_TRIANGLES},
                                   {"a.obj": 0.0})
        placements = [make_placement("a.obj")]
        hull_ring = object_footprints.structure_ring(
            structure, {"a.obj": geometry}, placements)
        assert hull_ring is not None
        parts, source = object_footprints.structure_footprint_parts(
            structure, {"a.obj": geometry}, placements, hull_ring)
        assert source == "hull_fallback"
        assert parts == [list(hull_ring)]

    def test_sub_square_metre_residue_is_not_a_part(self, fake_projection):
        # A 20 x 20 building plus a 0.5 x 0.5 m decal quad 40 m away:
        # the decal is union residue, not a building.
        vertices = list(TWO_BOX_VERTICES[:8]) + [
            (60.0, 0.0, 0.0), (60.5, 0.0, 0.0),
            (60.5, 0.0, 0.5), (60.0, 0.0, 0.5),
        ]
        triangles = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
                     (8, 9, 10), (8, 10, 11)]
        geometry = make_geometry(vertices, triangles)
        structure = make_structure({"a.obj": triangles}, {"a.obj": 0.0})
        placements = [make_placement("a.obj")]
        hull_ring = object_footprints.structure_ring(
            structure, {"a.obj": geometry}, placements)
        parts, source = object_footprints.structure_footprint_parts(
            structure, {"a.obj": geometry}, placements, hull_ring)
        assert source == "structure"
        assert len(parts) == 1
        assert Polygon(ring_to_local_metres(parts[0])).area == (
            pytest.approx(400.0, abs=5.0))


# ── a slender member does not join two buildings (owner 2026-08-31c) ──
# HECA building100: two buildings 11.1 m apart, welded into ONE 28,389 m²
# part through a 3.5 m² isthmus — a flat plate at y = 3.00 m and a 0.3 m
# wide member rising from grade to 5.81 m.  The twins below encode the
# law (a plan isthmus thinner than FOOTPRINT_CONNECTOR_NECK_M does not
# join) AND the formulation it replaces (vertical-structure evidence in
# the connector, which the site refutes).

def _two_boxes_plus(extra_vertices, extra_triangles):
    """The two-box structure with an extra member spanning the gap."""
    base = len(TWO_BOX_VERTICES)
    vertices = list(TWO_BOX_VERTICES) + list(extra_vertices)
    triangles = list(TWO_BOX_TRIANGLES) + [
        tuple(base + index for index in triangle)
        for triangle in extra_triangles]
    geometry = make_geometry(vertices, triangles)
    structure = make_structure({"a.obj": triangles}, {"a.obj": 0.0})
    return structure, {"a.obj": geometry}, [make_placement("a.obj")]


def _span_plate(height, half_width):
    """A plate at ``height`` bridging x = 20…40 at z = 10 ± half_width."""
    low, high = 10.0 - half_width, 10.0 + half_width
    return ([(20.0, height, low), (40.0, height, low),
             (40.0, height, high), (20.0, height, high)],
            [(0, 1, 2), (0, 2, 3)])


def _parts_of(structure, geometry, placements):
    hull_ring = object_footprints.structure_ring(
        structure, geometry, placements)
    parts, source = object_footprints.structure_footprint_parts(
        structure, geometry, placements, hull_ring)
    return parts, source


class TestSlenderConnectorSplit:
    def test_an_elevated_catwalk_does_not_join_two_buildings(
            self, fake_projection):
        # The measured HECA joiner: a 0.4 m wide plate at y = 3, no
        # ground contact, bridging two 400 m² buildings 20 m apart.
        vertices, triangles = _span_plate(3.0, 0.2)
        parts, source = _parts_of(*_two_boxes_plus(vertices, triangles))
        assert source == "structure"
        assert len(parts) == 2
        areas = sorted(Polygon(ring_to_local_metres(part)).area
                       for part in parts)
        assert areas == pytest.approx([400.0, 400.0], abs=5.0)

    def test_a_ground_REACHING_slender_member_still_does_not_join(
            self, fake_projection):
        # THE REFUTATION the site measured: the joiner reaches the
        # ground (grade to 5 m here, −0.02 to 5.81 m at HECA), so a
        # "no vertical-structure evidence" test would keep the two
        # buildings welded.  Width, not height, is the discriminant.
        low_vertices, low_triangles = _span_plate(0.0, 0.15)
        high_vertices, high_triangles = _span_plate(5.0, 0.15)
        vertices = low_vertices + high_vertices
        triangles = list(low_triangles) + [
            tuple(4 + index for index in triangle)
            for triangle in high_triangles]
        parts, source = _parts_of(*_two_boxes_plus(vertices, triangles))
        assert source == "structure"
        assert len(parts) == 2
        areas = sorted(Polygon(ring_to_local_metres(part)).area
                       for part in parts)
        assert areas == pytest.approx([400.0, 400.0], abs=5.0)

    def test_a_wide_link_keeps_a_two_wing_building_whole(
            self, fake_projection):
        # A genuine two-wing building: the wings are joined by a 6 m
        # wide link block, wider than the neck width, so the structure
        # stays ONE footprint — wings, link and all.
        vertices, triangles = _span_plate(8.0, 3.0)
        parts, source = _parts_of(*_two_boxes_plus(vertices, triangles))
        assert source == "structure"
        assert len(parts) == 1
        assert Polygon(ring_to_local_metres(parts[0])).area == (
            pytest.approx(920.0, abs=10.0))

    def test_a_part_with_no_isthmus_is_the_same_object(self):
        # The no-op invariant: the split is a detector, so a part it has
        # nothing to say about is passed through UNTOUCHED — not
        # re-projected, not re-buffered, not simplified.
        square = Polygon([(0.0, 0.0), (0.0, 0.001), (0.001, 0.001),
                          (0.001, 0.0)])
        refined = object_footprints._split_slender_connectors([square])
        assert len(refined) == 1
        assert refined[0] is square

    def test_a_broken_part_is_kept_whole(self, monkeypatch):
        # Any geometry failure keeps the part: the split may shrink a
        # footprint, never delete one.
        square = Polygon([(0.0, 0.0), (0.0, 0.001), (0.001, 0.001),
                          (0.001, 0.0)])

        def explode(_part, _radius):
            raise ValueError("synthetic GEOS failure")

        monkeypatch.setattr(object_footprints, "_split_one_part", explode)
        assert object_footprints._split_slender_connectors(
            [square]) == [square]

    def test_a_sub_lobe_bump_is_not_a_second_building(self,
                                                     fake_projection):
        # A 4 m² bump hanging off a building on a 1 m neck is boundary
        # detail (FOOTPRINT_MIN_LOBE_AREA_M2), not a second pad — and
        # its area stays with the building it hangs off.
        vertices = [(20.0, 0.0, 9.5), (22.0, 0.0, 9.5),
                    (22.0, 0.0, 11.5), (20.0, 0.0, 11.5)]
        triangles = [(0, 1, 2), (0, 2, 3)]
        parts, source = _parts_of(*_two_boxes_plus(vertices, triangles))
        assert source == "structure"
        # Two boxes (still disjoint from each other) — the bump joined
        # the first box, it did not become a third part.
        assert len(parts) == 2
        assert max(Polygon(ring_to_local_metres(part)).area
                   for part in parts) == pytest.approx(404.0, abs=5.0)


# ── tier (b): read_dsf_object_buildings plumbing ─────────────────────

def _write_fake_dsf(tmp_path, body):
    """Harness pattern (b) from ``tests/test_dsf_buildings.py``: a fake
    ``.dsf`` plus a pre-seeded, mtime-backdated ``.dsf.text`` so
    ``_load_dsf_text`` uses the cache and DSFTool never runs — laid out
    as ``<pack>/Earth nav data/<group>/<tile>.dsf`` so
    ``_pack_root_for_dsf`` resolves the pack."""
    pack_root = tmp_path / "Fake Scenery Pack"
    dsf_directory = pack_root / "Earth nav data" / "+30-090"
    dsf_directory.mkdir(parents=True)
    dsf = dsf_directory / "+35-081.dsf"
    dsf.write_text("binary-placeholder")
    text = dsf_directory / "+35-081.dsf.text"
    text.write_text(body)
    now = os.path.getmtime(text)
    os.utime(dsf, (now - 10, now - 10))
    return str(dsf), str(pack_root)


def _parse_placements_like_the_real_reader(dsf_text_lines,
                                           accept_resource=None,
                                           include_object_msl=False):
    """Trivial stand-in for ``obj8_reader.read_dsf_object_placements``
    (plain ``OBJECT`` only, honouring ``accept_resource``).

    Accepts (and ignores) ``include_object_msl`` to match the real
    reader's signature: ``read_dsf_object_buildings`` opts in so the
    Feature-B terrain classifier can see absolute-deck ``OBJECT_MSL``
    rows.  These synthetic DSFs carry only plain ``OBJECT`` rows, so
    there is nothing extra to emit."""
    definitions = []
    placements = []
    for line in dsf_text_lines:
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "OBJECT_DEF":
            definitions.append(line.split(None, 1)[1].strip())
        elif tokens[0] == "OBJECT":
            index = int(tokens[1])
            resource = definitions[index]
            if accept_resource is not None \
                    and not accept_resource(resource):
                continue
            placements.append(obj8_reader.ObjectPlacement(
                definition_index=index,
                resource_path=resource,
                longitude=float(tokens[2]),
                latitude=float(tokens[3]),
                heading_degrees=float(tokens[4]),
            ))
    return placements


class FakeObjectGeometry:
    """Duck-typed stand-in for ``obj8_reader.ObjectGeometry`` exposing
    exactly what the Phase 1 path consumes."""

    def __init__(self, vertices, solid_triangles):
        self.vertices = list(vertices)
        self.solid_triangles = list(solid_triangles)

    @property
    def has_solid_geometry(self):
        return bool(self.solid_triangles)

    def solid_reach_metres(self):
        used = {index for triangle in self.solid_triangles
                for index in triangle}
        return max((math.hypot(self.vertices[index][0],
                               self.vertices[index][2])
                    for index in used), default=0.0)


def _square_slab_geometry(side_metres):
    half = side_metres / 2.0
    vertices = [(-half, 0.0, -half), (half, 0.0, -half),
                (half, 0.0, half), (-half, 0.0, half)]
    return FakeObjectGeometry(vertices, [(0, 1, 2), (0, 2, 3)])


_DSF_BODY = "\n".join([
    "OBJECT_DEF Terminals/Hangar/big_bake.obj",
    "OBJECT_DEF objects/row_warehouse.obj",
    "OBJECT_DEF otros/cone.obj",
    "OBJECT_DEF Terminals/Hangar/missing_shed.obj",
    "OBJECT_DEF lib/airport/Common_Elements/Hangars/Lg_Maint.agp",
    "OBJECT 0 -80.930000 35.210000 0.000000",
    "OBJECT 1 -80.931000 35.211000 0.000000",     # I-5: two placements
    "OBJECT 1 -80.932000 35.212000 90.000000",    #      of one .obj
    "OBJECT 2 -80.933000 35.213000 0.000000",
    "OBJECT 3 -80.934000 35.214000 0.000000",
    "OBJECT 4 -80.935000 35.215000 0.000000",     # .agp: never a candidate
]) + "\n"


@pytest.fixture()
def object_building_harness(tmp_path, monkeypatch, fake_projection):
    """Fake DSF + monkeypatched ``obj8_reader`` + trivial
    ``object_anchor`` fakes (the Wave-2 stubs raise
    ``NotImplementedError`` until workstream W4 lands)."""
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    dsf_path, pack_root = _write_fake_dsf(tmp_path, _DSF_BODY)

    # Physical files exist so the (absolute path, mtime) geometry cache
    # has an mtime to key on; the parse itself is monkeypatched.
    geometry_by_resource = {
        "Terminals/Hangar/big_bake.obj": _square_slab_geometry(80.0),
        "objects/row_warehouse.obj": _square_slab_geometry(60.0),
        "otros/cone.obj": _square_slab_geometry(1.0),  # reach << 25
    }
    physical_by_resource = {}
    geometry_by_physical = {}
    for resource_path, geometry in geometry_by_resource.items():
        physical = os.path.join(pack_root, *resource_path.split("/"))
        os.makedirs(os.path.dirname(physical), exist_ok=True)
        with open(physical, "w") as handle:
            handle.write("placeholder\n")
        physical_by_resource[resource_path] = physical
        geometry_by_physical[os.path.abspath(physical)] = geometry
    # "Terminals/Hangar/missing_shed.obj" stays unresolvable.

    resolve_calls = []

    def fake_resolve_object_resource(resource_path, pack_root_argument,
                                     xplane_root_argument):
        resolve_calls.append((resource_path, pack_root_argument,
                              xplane_root_argument))
        return physical_by_resource.get(resource_path)

    load_calls = []

    def fake_load_object_file(path):
        load_calls.append(path)
        return geometry_by_physical[os.path.abspath(path)]

    monkeypatch.setattr(obj8_reader, "read_dsf_object_placements",
                        _parse_placements_like_the_real_reader)
    monkeypatch.setattr(obj8_reader, "resolve_object_resource",
                        fake_resolve_object_resource)
    monkeypatch.setattr(obj8_reader, "load_object_file",
                        fake_load_object_file)

    pool_calls = []

    def fake_discover_object_pools(placements, resolved_paths,
                                   geometry_by_resource_argument, *,
                                   epsilon_metres):
        pool_calls.append((list(placements), dict(resolved_paths),
                           epsilon_metres))
        return [object_anchor.ObjectPool(
            placements=list(placements),
            resolved_paths=dict(resolved_paths))]

    partition_calls = []

    def fake_partition_structures(pool, geometry_by_resource_argument,
                                  *, epsilon_metres):
        partition_calls.append((pool, epsilon_metres))
        structures = []
        for placement in pool.placements:
            geometry = geometry_by_resource_argument[
                placement.resource_path]
            structures.append(make_structure(
                {placement.resource_path:
                     list(geometry.solid_triangles)},
                {placement.resource_path:
                     min(vertex[1] for vertex in geometry.vertices)},
            ))
        return structures

    monkeypatch.setattr(object_anchor, "discover_object_pools",
                        fake_discover_object_pools)
    monkeypatch.setattr(object_anchor, "partition_structures",
                        fake_partition_structures)

    # The Feature-B classifier runs inside ``read_dsf_object_buildings``
    # BEFORE pooling (gate ``OBJECT_BRIDGE_TERRAIN``, default on) and
    # would call ``discover_object_pools`` itself with every kept
    # placement.  Stub it to "no exclusions" so ``pool_calls`` records
    # ONLY the reader's own pooling and the harness stays hermetic; the
    # classifier has its own test files, and the two gate/exclusion
    # tests below override this stub with their own fakes.
    monkeypatch.setattr(
        object_terrain_features, "classify_object_terrain_features",
        lambda *args, **kwargs: object_terrain_features
        .ClassificationResult(tunnels=[], bridges=[]))

    class Harness:
        pass

    harness = Harness()
    harness.dsf_path = dsf_path
    harness.pack_root = pack_root
    # The fake parser's path -> geometry map, exposed so a test can
    # register a ``.anchor_bak`` original (the reader loads geometry
    # from the backup when one exists — ruling R1).
    harness.geometry_by_physical = geometry_by_physical
    harness.resolve_calls = resolve_calls
    harness.load_calls = load_calls
    harness.pool_calls = pool_calls
    harness.partition_calls = partition_calls
    return harness


class TestReadDsfObjectBuildings:
    def test_placements_become_buildings(self, object_building_harness):
        harness = object_building_harness
        buildings = D.read_dsf_object_buildings(
            harness.dsf_path, xplane_root="/nonexistent-xplane")
        # big_bake (1 placement) + row_warehouse (2 placements, each a
        # building — invariant I-5).  cone fails the 25 m reach floor,
        # missing_shed is unresolvable, the .agp is not a .obj.
        assert len(buildings) == 3
        for outer_ring, holes, role in buildings:
            # R18-2: the role carries the vertical-evidence verdict.
            # These harness fixtures are FLAT slabs (the autouse fixture
            # disables the height/tall-base gates so the ring SHAPE can
            # be asserted), so they come back UNVOUCHED — which is the
            # honest reading of a flat slab and the whole point of the
            # gate.  Both values are the object vocabulary.
            assert role in (D.OBJECT_BUILDING_ROLE,
                            D.OBJECT_BUILDING_UNVOUCHED_ROLE)
            assert role == D.OBJECT_BUILDING_UNVOUCHED_ROLE
            assert holes == []
            assert len(outer_ring) >= 3
            assert outer_ring[0] != outer_ring[-1]

    def test_multi_placement_definition_yields_one_building_each(
            self, object_building_harness):
        harness = object_building_harness
        buildings = D.read_dsf_object_buildings(
            harness.dsf_path, xplane_root=None)
        warehouse_centroids = []
        for outer_ring, _holes, _role in buildings:
            polygon = Polygon(outer_ring)
            centroid = polygon.centroid
            if abs(centroid.x - -80.930) > 2e-4:     # not big_bake
                warehouse_centroids.append((centroid.x, centroid.y))
        assert len(warehouse_centroids) == 2
        # Each footprint sits at its OWN placement anchor.
        anchors = {(-80.931, 35.211), (-80.932, 35.212)}
        for centroid_longitude, centroid_latitude in warehouse_centroids:
            assert min(
                math.hypot(centroid_longitude - anchor_longitude,
                           centroid_latitude - anchor_latitude)
                for anchor_longitude, anchor_latitude in anchors) < 2e-5
        # And the multi-placement resource never entered the shared
        # pooling (an ObjectPool carries one placement per resource):
        # EVERY pooling call the reader made carried the single-placement
        # resource alone.
        assert harness.pool_calls, "shared pooling was never consulted"
        for pooled_placements, _resolved, _epsilon in harness.pool_calls:
            assert [p.resource_path for p in pooled_placements] == [
                "Terminals/Hangar/big_bake.obj"]

    def test_resolution_receives_pack_root_and_xplane_root(
            self, object_building_harness):
        harness = object_building_harness
        D.read_dsf_object_buildings(
            harness.dsf_path, xplane_root="/some/xplane/root")
        assert harness.resolve_calls, "resolver was never consulted"
        resolved_resources = set()
        for (resource_path, pack_root_argument,
                xplane_root_argument) in harness.resolve_calls:
            resolved_resources.add(resource_path)
            assert pack_root_argument == harness.pack_root
            assert xplane_root_argument == "/some/xplane/root"
        # Only .obj resources reach resolution; the .agp was filtered by
        # the accept_resource predicate.
        assert resolved_resources == {
            "Terminals/Hangar/big_bake.obj",
            "objects/row_warehouse.obj",
            "otros/cone.obj",
            "Terminals/Hangar/missing_shed.obj",
        }

    def test_reach_floor_filters_compact_objects(
            self, object_building_harness):
        harness = object_building_harness
        buildings = D.read_dsf_object_buildings(
            harness.dsf_path, xplane_root=None)
        for outer_ring, _holes, _role in buildings:
            centroid = Polygon(outer_ring).centroid
            # Nothing footprinted at the cone's anchor.
            assert math.hypot(centroid.x - -80.933,
                              centroid.y - 35.213) > 1e-4

    def test_partition_epsilon_comes_from_config(
            self, object_building_harness, monkeypatch):
        harness = object_building_harness
        monkeypatch.setattr(config, "DSF_OBJECT_CONTACT_EPSILON_M", 0.4)
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        assert harness.pool_calls[-1][2] == 0.4
        assert all(epsilon == 0.4
                   for _pool, epsilon in harness.partition_calls[-3:])

    def test_geometry_cache_parses_each_file_once(
            self, object_building_harness):
        harness = object_building_harness
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        first_load_count = len(harness.load_calls)
        assert first_load_count > 0
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        # Second read: every geometry served from the
        # (absolute path, mtime) cache.
        assert len(harness.load_calls) == first_load_count

    def test_no_object_placements_returns_empty(self, tmp_path,
                                                monkeypatch,
                                                fake_projection):
        monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
        monkeypatch.setattr(obj8_reader, "read_dsf_object_placements",
                            _parse_placements_like_the_real_reader)
        dsf_path, _pack_root = _write_fake_dsf(
            tmp_path, "POLYGON_DEF lib/airport/pavement/asphalt.pol\n")
        assert D.read_dsf_object_buildings(dsf_path,
                                           xplane_root=None) == []

    def test_terrain_classified_resource_excluded_from_pool(
            self, object_building_harness, monkeypatch):
        """Defect 2026-07-17 (EGLL Building36): a resource the Feature-B
        classifier consumes as tunnel/bridge/deck terrain is dropped
        from the building pool BEFORE pooling, so it can never chain
        into a pad.  Here ``objects/row_warehouse.obj`` (its two
        placements would be two buildings) is returned in the
        classifier's exclusions; only ``big_bake.obj``'s single building
        must survive."""
        harness = object_building_harness
        pack_root = harness.pack_root

        def fake_classify(placements, geometry_by_resource, *,
                          pavement_polygons_longitude_latitude=None,
                          mean_sea_level_placements=None, pack_root="",
                          **kwargs):
            return object_terrain_features.ClassificationResult(
                tunnels=[], bridges=[],
                exclusions=[(pack_root, "objects/row_warehouse.obj")])

        monkeypatch.setattr(object_terrain_features,
                            "classify_object_terrain_features",
                            fake_classify)

        buildings = D.read_dsf_object_buildings(
            harness.dsf_path, xplane_root="/nonexistent-xplane")
        # big_bake alone remains; the two row_warehouse placements are
        # excluded as classified terrain — the reader never pooled them.
        assert len(buildings) == 1
        pooled_resources = {
            resource
            for _placements, resolved_paths, _epsilon in harness.pool_calls
            for resource in resolved_paths}
        assert "objects/row_warehouse.obj" not in pooled_resources
        assert "Terminals/Hangar/big_bake.obj" in pooled_resources

    def test_terrain_exclusion_off_when_feature_gate_off(
            self, object_building_harness, monkeypatch):
        """With ``OBJECT_BRIDGE_TERRAIN`` off the classifier never runs,
        so no resource is excluded and the full building set is
        emitted (the pre-feature behaviour)."""
        monkeypatch.setattr(config, "OBJECT_BRIDGE_TERRAIN", False)

        def exploding_classify(*args, **kwargs):
            raise AssertionError(
                "classifier must not run when the gate is off")

        monkeypatch.setattr(object_terrain_features,
                            "classify_object_terrain_features",
                            exploding_classify)

        harness = object_building_harness
        buildings = D.read_dsf_object_buildings(
            harness.dsf_path, xplane_root="/nonexistent-xplane")
        assert len(buildings) == 3


# ── footprint sidecar cache (data root Airport_mod_cache/<pack>/) ────

_FOOTPRINT_LEGACY_SIDECAR_NAME = "o4_object_footprints.cache"


class TestObjectFootprintCache:
    """The sidecar cache around ``read_dsf_object_buildings`` — a warm
    hit must skip the O(n^2) contact-graph partition entirely and
    reproduce the ring set byte-for-byte, invalidate on any ``.obj``
    edit, and degrade safely on a corrupt sidecar or a disabled gate.
    Per the user ruling 2026-07-15 the sidecar lives under the data
    root's ``Airport_mod_cache/<pack name>/`` — never inside the pack —
    and any pre-ruling in-pack sidecar is removed on resolution."""

    @pytest.fixture(autouse=True)
    def _isolated_data_root(self, tmp_path, monkeypatch):
        """Pin the data root under ``tmp_path`` — ``ORTHO4XP_DATA_ROOT``
        wins ``O4_File_Names.resolve_data_root`` — so sidecars never
        escape the test sandbox."""
        self.data_root = tmp_path / "o4root"
        monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(self.data_root))

    def _sidecar_path(self, harness):
        pack_name = os.path.basename(
            os.path.abspath(harness.pack_root))
        dsf_stem = os.path.splitext(
            os.path.basename(harness.dsf_path))[0]
        return os.path.join(
            str(self.data_root), "Airport_mod_cache", pack_name,
            f"o4_object_footprints_{dsf_stem}.cache")

    def _bump_obj_mtime(self, harness, resource_relative_path):
        obj_path = os.path.join(harness.pack_root,
                                *resource_relative_path.split("/"))
        file_stat = os.stat(obj_path)
        os.utime(obj_path,
                 (file_stat.st_atime + 100, file_stat.st_mtime + 100))

    def test_warm_hit_returns_equal_and_skips_partition(
            self, object_building_harness):
        harness = object_building_harness
        first = D.read_dsf_object_buildings(harness.dsf_path,
                                            xplane_root=None)
        partitions_after_first = len(harness.partition_calls)
        assert partitions_after_first > 0
        assert os.path.isfile(self._sidecar_path(harness))

        # Drop the in-process memo so the second call exercises the DISK
        # sidecar (the memo alone is proven by
        # ``TestObjectReaderInProcessMemo``).
        D._OBJECT_READER_MEMO.clear()
        second = D.read_dsf_object_buildings(harness.dsf_path,
                                             xplane_root=None)
        # Identical ring set …
        assert second == first
        # … produced WITHOUT re-running the partition (cache hit).
        assert len(harness.partition_calls) == partitions_after_first

    def test_touching_an_obj_invalidates(self, object_building_harness):
        harness = object_building_harness
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        partitions_before = len(harness.partition_calls)
        assert os.path.isfile(self._sidecar_path(harness))

        self._bump_obj_mtime(harness, "Terminals/Hangar/big_bake.obj")
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        # Stale fingerprint forces a full recompute (partition ran again).
        assert len(harness.partition_calls) > partitions_before

    def _bake_in_place(self, harness, resource_relative_path):
        """Simulate the Phase 2 y-bake of one object exactly as
        ``object_rebake.apply`` performs it: ``copy2`` the original to
        ``.anchor_bak``, then rewrite the LIVE file (different bytes,
        new mtime).  No provenance sidecar is written — a backup with no
        recorded hashes is authoritative (amendment A2)."""
        import shutil
        obj_path = os.path.join(harness.pack_root,
                                *resource_relative_path.split("/"))
        backup_path = obj_path + ".anchor_bak"
        shutil.copy2(obj_path, backup_path)
        # The backup is what the reader parses from now on (ruling R1).
        harness.geometry_by_physical[os.path.abspath(backup_path)] = (
            harness.geometry_by_physical[os.path.abspath(obj_path)])
        with open(obj_path, "w") as handle:
            handle.write("placeholder\nVT 0 -9.4 0\n")
        file_stat = os.stat(obj_path)
        os.utime(obj_path,
                 (file_stat.st_atime + 200, file_stat.st_mtime + 200))

    def test_the_engines_own_y_bake_does_not_invalidate(
            self, object_building_harness):
        """OWNER RULING 2026-08-13 (pristine inputs).  The sidecar is
        written BEFORE Phase 2 bakes the very ``.obj`` files it was
        fingerprinted over, so keying on the live stat block made a
        build invalidate the sidecar it had just written and the NEXT
        build pay the whole O(n²) partition again — once per bake cycle,
        in production app builds (~66 s HECA, ~455 s OTHH; perf lane A).
        The bake changes no INPUT: the reader parses the ``.anchor_bak``
        original (ruling R1)."""
        harness = object_building_harness
        first = D.read_dsf_object_buildings(harness.dsf_path,
                                            xplane_root=None)
        partitions_after_first = len(harness.partition_calls)
        assert partitions_after_first > 0

        self._bake_in_place(harness, "Terminals/Hangar/big_bake.obj")

        D._OBJECT_READER_MEMO.clear()
        second = D.read_dsf_object_buildings(harness.dsf_path,
                                             xplane_root=None)
        assert second == first
        assert len(harness.partition_calls) == partitions_after_first

    def test_an_external_edit_after_a_bake_still_invalidates(
            self, object_building_harness):
        """The other half of the ruling: a GENUINE pack change must
        still miss.  With recorded hashes present, a live file matching
        neither is invariant I-14's PACK CHANGED verdict."""
        harness = object_building_harness
        import json

        from auto_patch import object_rebake as REBAKE

        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        self._bake_in_place(harness, "Terminals/Hangar/big_bake.obj")
        resource = "Terminals/Hangar/big_bake.obj"
        obj_path = os.path.join(harness.pack_root, *resource.split("/"))
        # Provenance as ``apply`` writes it (this bake's two hashes).
        with open(os.path.join(harness.pack_root,
                               REBAKE.PROVENANCE_FILENAME), "w") as handle:
            json.dump({
                "version": REBAKE.PROVENANCE_VERSION,
                "meshes": {}, "runs": {},
                "objects": {resource: {
                    "backup_sha256": REBAKE._sha256_of_file(
                        obj_path + ".anchor_bak"),
                    "written_sha256": REBAKE._sha256_of_file(obj_path),
                }},
            }, handle)
        D._OBJECT_READER_MEMO.clear()
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        partitions_before = len(harness.partition_calls)

        # A new pack version lands on the live file.
        with open(obj_path, "w") as handle:
            handle.write("placeholder\n# new pack version\n")
        D._OBJECT_READER_MEMO.clear()
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        assert len(harness.partition_calls) > partitions_before

    def test_gate_zero_disables_read_and_write(
            self, object_building_harness, monkeypatch):
        harness = object_building_harness
        monkeypatch.setenv("O4_OBJECT_FOOTPRINT_CACHE", "0")
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        partitions_first = len(harness.partition_calls)
        # No sidecar is written when the gate is off.
        assert not os.path.isfile(self._sidecar_path(harness))
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        # And the second call recomputes rather than serving a cache.
        assert len(harness.partition_calls) > partitions_first

    def test_corrupt_sidecar_falls_back_to_recompute(
            self, object_building_harness):
        harness = object_building_harness
        first = D.read_dsf_object_buildings(harness.dsf_path,
                                            xplane_root=None)
        sidecar = self._sidecar_path(harness)
        assert os.path.isfile(sidecar)
        with open(sidecar, "wb") as handle:
            handle.write(b"not a valid pickle \x00\x01\x02")
        partitions_before = len(harness.partition_calls)

        # Drop the in-process memo — it would (correctly) serve the
        # result without touching the corrupt file; this test is about
        # the DISK fallback path.
        D._OBJECT_READER_MEMO.clear()
        second = D.read_dsf_object_buildings(harness.dsf_path,
                                             xplane_root=None)
        # A garbled sidecar never raises — it recomputes and rewrites …
        assert second == first
        assert len(harness.partition_calls) > partitions_before

    def test_no_pack_root_disables_caching(self, tmp_path):
        # With no resolvable pack root (None) or a non-directory, the
        # sidecar helper declines — the reader then behaves as it did
        # before the cache existed.
        loose_dsf = tmp_path / "loose.dsf"
        loose_dsf.write_text("binary-placeholder")
        assert D._object_footprint_sidecar(
            str(loose_dsf), None, 1.0, 25.0) == (None, None)
        assert D._object_footprint_sidecar(
            str(loose_dsf), str(tmp_path / "missing"), 1.0, 25.0) \
            == (None, None)

    def test_sidecar_lands_under_data_root_not_in_pack(
            self, object_building_harness):
        harness = object_building_harness
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        sidecar = self._sidecar_path(harness)
        assert os.path.isfile(sidecar)
        assert sidecar.startswith(
            os.path.join(str(self.data_root), "Airport_mod_cache"))
        # Nothing cache-shaped may land inside the scenery pack (user
        # ruling 2026-07-15).
        pack_files = []
        for directory, _subdirectories, file_names in os.walk(
                harness.pack_root):
            pack_files.extend(file_names)
        assert not any(name.endswith(".cache") for name in pack_files)

    def test_stale_legacy_in_pack_sidecar_removed(
            self, object_building_harness):
        harness = object_building_harness
        legacy = os.path.join(harness.pack_root,
                              _FOOTPRINT_LEGACY_SIDECAR_NAME)
        with open(legacy, "wb") as handle:
            handle.write(b"pre-ruling in-pack sidecar")
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        # The old in-pack file was cleaned up on sidecar resolution.
        assert not os.path.exists(legacy)


# ── in-process memo + per-DSF lock (``_serve_object_reader``) ────────

class TestObjectReaderInProcessMemo:
    """The in-process layer above the disk sidecar: the airport-insets
    phase fetches every airport of a tile from the SAME pack DSF on a
    ThreadPoolExecutor, so a cold cache must compute once — concurrent
    callers block on the per-DSF lock and reuse the winner's result —
    and later same-process calls must not even need the sidecar file.
    (Memo keys embed the tmp_path-unique DSF path + fingerprint, so no
    cross-test clearing is needed.)"""

    def _sidecar_path(self, tmp_path, harness):
        pack_name = os.path.basename(os.path.abspath(harness.pack_root))
        dsf_stem = os.path.splitext(
            os.path.basename(harness.dsf_path))[0]
        return os.path.join(
            str(tmp_path / "o4_data_root"), "Airport_mod_cache",
            pack_name, f"o4_object_footprints_{dsf_stem}.cache")

    def test_memo_serves_after_sidecar_deleted(
            self, object_building_harness, tmp_path):
        harness = object_building_harness
        first = D.read_dsf_object_buildings(harness.dsf_path,
                                            xplane_root=None)
        partitions_after_first = len(harness.partition_calls)
        sidecar = self._sidecar_path(tmp_path, harness)
        assert os.path.isfile(sidecar)
        os.remove(sidecar)

        second = D.read_dsf_object_buildings(harness.dsf_path,
                                             xplane_root=None)
        assert second == first
        # No recompute — and the missing sidecar was never consulted or
        # rewritten: the result came from the in-process memo.
        assert len(harness.partition_calls) == partitions_after_first
        assert not os.path.isfile(sidecar)

    def test_concurrent_cold_calls_compute_once(
            self, object_building_harness, monkeypatch):
        """Two threads race a cold cache on one DSF.  The first is held
        at the top of the computation (already inside the per-DSF lock)
        while the second is submitted, so without the lock both would
        miss sidecar + memo and each run the full computation; with it,
        ``_compute_dsf_object_buildings`` runs exactly once and both
        callers get the same ring set."""
        import threading
        from concurrent.futures import ThreadPoolExecutor

        harness = object_building_harness
        first_entered = threading.Event()
        release_first = threading.Event()
        compute_calls = []
        real_compute = D._compute_dsf_object_buildings

        def gated_compute(*arguments, **keyword_arguments):
            compute_calls.append(threading.get_ident())
            first_entered.set()
            assert release_first.wait(timeout=10), \
                "test choreography stuck"
            return real_compute(*arguments, **keyword_arguments)

        monkeypatch.setattr(D, "_compute_dsf_object_buildings",
                            gated_compute)

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(
                D.read_dsf_object_buildings, harness.dsf_path)
            assert first_entered.wait(timeout=10), \
                "first reader never reached the computation"
            # The first reader now holds the per-DSF lock mid-compute;
            # the racer must block on it, then reuse the memo.
            future_b = executor.submit(
                D.read_dsf_object_buildings, harness.dsf_path)
            release_first.set()
            result_a = future_a.result(timeout=30)
            result_b = future_b.result(timeout=30)

        assert result_a == result_b
        assert len(result_a) == 3
        # ONE computation for two callers.
        assert len(compute_calls) == 1

    def test_gate_off_means_no_memo_and_no_lock_path(
            self, object_building_harness, monkeypatch):
        """``O4_OBJECT_FOOTPRINT_CACHE=0`` keeps meaning "no read, no
        write": with no fingerprint there is no memo either, so every
        call recomputes (tests that monkeypatch reader internals rely
        on this)."""
        harness = object_building_harness
        monkeypatch.setenv("O4_OBJECT_FOOTPRINT_CACHE", "0")
        compute_calls = []
        real_compute = D._compute_dsf_object_buildings

        def counting_compute(*arguments, **keyword_arguments):
            compute_calls.append(True)
            return real_compute(*arguments, **keyword_arguments)

        monkeypatch.setattr(D, "_compute_dsf_object_buildings",
                            counting_compute)
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        D.read_dsf_object_buildings(harness.dsf_path, xplane_root=None)
        assert len(compute_calls) == 2


# ── tier (b), real workstream-W2 reader ──────────────────────────────

def _obj8_reader_is_implemented():
    try:
        obj8_reader.read_dsf_object_placements([])
    except NotImplementedError:
        return False
    except Exception:
        return True
    return True


_REAL_BOX_OBJ = "\n".join([
    "A",
    "800",
    "OBJ",
    "",
    "POINT_COUNTS 8 0 0 12",
    # 40 x 40 base at y = 0 (reach ~28 m > the 25 m floor), roof at y=3.
    "VT -20.0 0.0 -20.0 0 1 0 0 0",
    "VT 20.0 0.0 -20.0 0 1 0 0 0",
    "VT 20.0 0.0 20.0 0 1 0 0 0",
    "VT -20.0 0.0 20.0 0 1 0 0 0",
    "VT -20.0 3.0 -20.0 0 1 0 0 0",
    "VT 20.0 3.0 -20.0 0 1 0 0 0",
    "VT 20.0 3.0 20.0 0 1 0 0 0",
    "VT -20.0 3.0 20.0 0 1 0 0 0",
    "IDX10 0 1 2 0 2 3 4 5 6 4",
    "IDX 6",
    "IDX 7",
    "TRIS 0 12",
]) + "\n"

_REAL_SMALL_BOX_OBJ = _REAL_BOX_OBJ.replace("20.0", "5.0")

# ONE resource drawing TWO separate 40 x 40 buildings 40 m apart — the
# HECA building79 shape in miniature.  Convex hull 120 x 40 = 4800 m2
# (both buildings AND the ground between them); own geometry 2 x 1600.
_REAL_TWO_BOX_OBJ = "\n".join([
    "A",
    "800",
    "OBJ",
    "",
    "POINT_COUNTS 16 0 0 24",
    "VT -60.0 0.0 -20.0 0 1 0 0 0",
    "VT -20.0 0.0 -20.0 0 1 0 0 0",
    "VT -20.0 0.0 20.0 0 1 0 0 0",
    "VT -60.0 0.0 20.0 0 1 0 0 0",
    "VT -60.0 3.0 -20.0 0 1 0 0 0",
    "VT -20.0 3.0 -20.0 0 1 0 0 0",
    "VT -20.0 3.0 20.0 0 1 0 0 0",
    "VT -60.0 3.0 20.0 0 1 0 0 0",
    "VT 20.0 0.0 -20.0 0 1 0 0 0",
    "VT 60.0 0.0 -20.0 0 1 0 0 0",
    "VT 60.0 0.0 20.0 0 1 0 0 0",
    "VT 20.0 0.0 20.0 0 1 0 0 0",
    "VT 20.0 3.0 -20.0 0 1 0 0 0",
    "VT 60.0 3.0 -20.0 0 1 0 0 0",
    "VT 60.0 3.0 20.0 0 1 0 0 0",
    "VT 20.0 3.0 20.0 0 1 0 0 0",
    "IDX10 0 1 2 0 2 3 4 5 6 4",
    "IDX10 6 7 8 9 10 8 10 11 12 13",
    "IDX 14",
    "IDX 12",
    "IDX 14",
    "IDX 15",
    "TRIS 0 24",
]) + "\n"


@pytest.mark.skipif(
    not _obj8_reader_is_implemented(),
    reason="pending workstream W2 (obj8_reader still raises "
           "NotImplementedError)")
class TestReadDsfObjectBuildingsRealReader:
    """Tier (b) with the REAL obj8_reader (no reader monkeypatch; the
    Wave-2 partition fakes remain)."""

    @pytest.fixture()
    def partition_fakes(self, monkeypatch):
        def fake_discover_object_pools(placements, resolved_paths,
                                       geometry_by_resource, *,
                                       epsilon_metres):
            return [object_anchor.ObjectPool(
                placements=list(placements),
                resolved_paths=dict(resolved_paths))]

        def fake_partition_structures(pool, geometry_by_resource, *,
                                      epsilon_metres):
            structures = []
            for placement in pool.placements:
                geometry = geometry_by_resource[placement.resource_path]
                structures.append(make_structure(
                    {placement.resource_path:
                         list(geometry.solid_triangles)},
                    {placement.resource_path:
                         min(vertex[1]
                             for vertex in geometry.vertices)},
                ))
            return structures

        monkeypatch.setattr(object_anchor, "discover_object_pools",
                            fake_discover_object_pools)
        monkeypatch.setattr(object_anchor, "partition_structures",
                            fake_partition_structures)

    def test_synthetic_boxes_footprint_end_to_end(
            self, tmp_path, monkeypatch, partition_fakes):
        monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
        body = "\n".join([
            "OBJECT_DEF Terminals/Hangar/pack_box.obj",
            "OBJECT 0 -80.930000 35.210000 0.000000",
        ]) + "\n"
        dsf_path, pack_root = _write_fake_dsf(tmp_path, body)
        physical = os.path.join(pack_root, "Terminals", "Hangar",
                                "pack_box.obj")
        os.makedirs(os.path.dirname(physical), exist_ok=True)
        with open(physical, "w") as handle:
            handle.write(_REAL_BOX_OBJ)

        buildings = D.read_dsf_object_buildings(dsf_path,
                                                xplane_root=None)
        assert len(buildings) == 1
        outer_ring, holes, role = buildings[0]
        # 3 m tall box → no building-height member → UNVOUCHED (R18-2);
        # the ring itself is unchanged, which is what this test asserts.
        assert role == D.OBJECT_BUILDING_UNVOUCHED_ROLE and holes == []
        polygon = Polygon(outer_ring)
        centroid = polygon.centroid
        assert centroid.x == pytest.approx(-80.930, abs=2e-5)
        assert centroid.y == pytest.approx(35.210, abs=2e-5)
        # 40 m base box → ~1600 m2 in local metres.
        metres_per_degree_longitude = (
            METRES_PER_DEGREE_LATITUDE
            * math.cos(math.radians(35.210)))
        area_square_metres = (polygon.area
                              * METRES_PER_DEGREE_LATITUDE
                              * metres_per_degree_longitude)
        assert area_square_metres == pytest.approx(1600.0, rel=0.02)

    def test_one_structure_two_buildings_emits_two_rings(
            self, tmp_path, monkeypatch, partition_fakes):
        # Owner ruling 2026-08-30e end to end: ONE structure whose own
        # geometry describes two separate buildings emits TWO rings,
        # and the ground between them is in neither.  ``partition_fakes``
        # makes the whole resource one structure on purpose — that is
        # the HECA case, where a material-split page welds a complex
        # into a single structure the contact graph cannot split.
        monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
        body = "\n".join([
            "OBJECT_DEF Terminals/Hangar/two_box.obj",
            "OBJECT 0 -80.930000 35.210000 0.000000",
        ]) + "\n"
        dsf_path, pack_root = _write_fake_dsf(tmp_path, body)
        physical = os.path.join(pack_root, "Terminals", "Hangar",
                                "two_box.obj")
        os.makedirs(os.path.dirname(physical), exist_ok=True)
        with open(physical, "w") as handle:
            handle.write(_REAL_TWO_BOX_OBJ)

        buildings = D.read_dsf_object_buildings(dsf_path,
                                                xplane_root=None)
        assert len(buildings) == 2
        metres_per_degree_longitude = (
            METRES_PER_DEGREE_LATITUDE
            * math.cos(math.radians(35.210)))

        def _area(ring):
            return (Polygon(ring).area
                    * METRES_PER_DEGREE_LATITUDE
                    * metres_per_degree_longitude)

        for outer_ring, holes, role in buildings:
            assert holes == []
            assert role == D.OBJECT_BUILDING_UNVOUCHED_ROLE
            assert _area(outer_ring) == pytest.approx(1600.0, rel=0.02)
        # The 40 m of ground between the two buildings is footprint of
        # neither — under the convex hull it was one 4800 m2 pad.
        from shapely.geometry import Point
        centre = Point(-80.930, 35.210)
        assert not any(Polygon(ring).contains(centre)
                       for ring, _holes, _role in buildings)

    def test_pack_relative_resolution_beats_library(
            self, tmp_path, monkeypatch, partition_fakes):
        monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
        body = "\n".join([
            "OBJECT_DEF Terminals/Hangar/pack_box.obj",
            "OBJECT 0 -80.930000 35.210000 0.000000",
        ]) + "\n"
        dsf_path, pack_root = _write_fake_dsf(tmp_path, body)
        # Pack-relative candidate: the 40 m box.
        pack_physical = os.path.join(pack_root, "Terminals", "Hangar",
                                     "pack_box.obj")
        os.makedirs(os.path.dirname(pack_physical), exist_ok=True)
        with open(pack_physical, "w") as handle:
            handle.write(_REAL_BOX_OBJ)
        # A library.txt in a synthetic X-Plane root exports the SAME
        # virtual path to a DIFFERENT (10 m) box.
        xplane_root = tmp_path / "XPlane"
        library_pack = xplane_root / "Custom Scenery" / "TestLibrary"
        library_pack.mkdir(parents=True)
        library_physical = library_pack / "library_box.obj"
        library_physical.write_text(_REAL_SMALL_BOX_OBJ)
        (library_pack / "library.txt").write_text(
            "A\n800\nLIBRARY\n\n"
            "EXPORT Terminals/Hangar/pack_box.obj library_box.obj\n")

        buildings = D.read_dsf_object_buildings(
            dsf_path, xplane_root=str(xplane_root))
        assert len(buildings) == 1
        polygon = Polygon(buildings[0][0])
        metres_per_degree_longitude = (
            METRES_PER_DEGREE_LATITUDE
            * math.cos(math.radians(35.210)))
        area_square_metres = (polygon.area
                              * METRES_PER_DEGREE_LATITUDE
                              * metres_per_degree_longitude)
        # Pack-relative wins: the 40 m box (~1600 m2), not the library's
        # 10 m box (~100 m2).
        assert area_square_metres == pytest.approx(1600.0, rel=0.02)


# ── tier (c): flag gating and the shared admission helper ────────────

class TestPipelineFlagGating:
    def test_flag_off_object_reader_never_called(self, monkeypatch):
        def sentinel(*arguments, **keyword_arguments):
            raise AssertionError(
                "read_dsf_object_buildings must not be called with "
                "DSF_OBJECT_BUILDINGS off")

        monkeypatch.setattr(D, "read_dsf_object_buildings", sentinel)
        monkeypatch.setattr(config, "DSF_OBJECT_BUILDINGS", False)
        admitted = pipeline._collect_dsf_object_building_footprints(
            "/nonexistent.dsf", None,
            lambda outer_ring, hole_rings: True)
        assert admitted == 0

    def test_flag_on_object_reader_feeds_admission(self, monkeypatch):
        ring = [(-80.930, 35.210), (-80.929, 35.210), (-80.929, 35.211)]
        monkeypatch.setattr(
            D, "read_dsf_object_buildings",
            lambda dsf_path, cache_dir=None, xplane_root=None: [
                (ring, [], "object"),
                ([(-80.0, 35.0)], [], "object"),    # < 3 vertices: skipped
            ])
        monkeypatch.setattr(config, "DSF_OBJECT_BUILDINGS", True)
        admitted_rings = []

        def admit(outer_ring, hole_rings):
            admitted_rings.append((outer_ring, hole_rings))
            return True

        admitted = pipeline._collect_dsf_object_building_footprints(
            "/fake.dsf", "/fake/xplane", admit)
        assert admitted == 1
        assert admitted_rings == [(ring, [])]


def _scaled_to_metres_transform(longitude, latitude, altitude=None):
    """A tiny stand-in for the pipeline's local-metres projection."""
    return longitude * 1000.0, latitude * 1000.0


class TestAdmissionHelper:
    """The single downstream path both DSF building sources share
    (the ``.fac`` behavior itself is pinned by the untouched
    ``tests/test_dsf_buildings.py`` / ``tests/test_dsf_surface_pavement.py``)."""

    def test_valid_ring_is_admitted(self):
        pool = []
        assert pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01)],
            [], _scaled_to_metres_transform, None, None, pool)
        assert len(pool) == 1
        assert pool[0].area == pytest.approx(100.0)

    def test_bounding_box_reject(self):
        pool = []
        assert not pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01)],
            [], _scaled_to_metres_transform,
            (100.0, 100.0, 200.0, 200.0),   # far away
            None, pool)
        assert pool == []

    def test_boundary_centroid_gate(self):
        inside_gate = Polygon([(-1.0, -1.0), (20.0, -1.0),
                               (20.0, 20.0), (-1.0, 20.0)])
        pool = []
        assert pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01)],
            [], _scaled_to_metres_transform, None, inside_gate, pool)
        far_gate = Polygon([(500.0, 500.0), (600.0, 500.0),
                            (600.0, 600.0), (500.0, 600.0)])
        assert not pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01)],
            [], _scaled_to_metres_transform, None, far_gate, pool)
        assert len(pool) == 1

    def test_invalid_ring_repaired_or_rejected(self):
        # A bow-tie ring is buffer(0)-repaired to a valid Polygon and
        # admitted — exactly the pre-refactor inline behavior.
        pool = []
        assert pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.01), (0.01, 0.0), (0.0, 0.01)],
            [], _scaled_to_metres_transform, None, None, pool)
        assert len(pool) == 1 and pool[0].is_valid
        # A degenerate (collinear, zero-area) ring repairs to empty and
        # is rejected.
        assert not pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.01), (0.02, 0.02), (0.03, 0.03)],
            [], _scaled_to_metres_transform, None, None, pool)
        assert len(pool) == 1

    def test_short_hole_rings_are_ignored(self):
        pool = []
        assert pipeline._admit_dsf_building_footprint(
            [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01)],
            [[(0.001, 0.001), (0.002, 0.002)]],     # only 2 vertices
            _scaled_to_metres_transform, None, None, pool)
        assert len(pool) == 1
        assert pool[0].area == pytest.approx(100.0)


class TestStructureRingHullFill:
    """HULL-FILL FLOOR (owner defect 2026-07-27, HECA building188): a
    convex hull over SPARSE bases — one floodlight mast, a few jersey
    barriers, a stray below-grade fragment — minted a phantom 4,638 m²
    building pad punched into a graded apron.  Fill = Σ(base-triangle
    areas)/hull area; below ``DSF_OBJECT_MIN_FOOTPRINT_FILL`` the
    structure gets no pad."""

    # Three tiny 2 m "masts" at the corners of a ~100 m triangle: tall
    # (passes the building-height floor) but the hull is ~99.98 % empty.
    def _sparse_ring(self, resource="a.obj"):
        vertices = []
        triangles = []
        for cx, cz in ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0)):
            base = len(vertices)
            vertices += [
                (cx, 0.0, cz), (cx + 2.0, 0.0, cz),
                (cx + 2.0, 0.0, cz + 2.0),
                (cx, 28.0, cz), (cx + 2.0, 28.0, cz),
                (cx + 2.0, 28.0, cz + 2.0),
            ]
            triangles += [(base, base + 1, base + 2),
                          (base + 3, base + 4, base + 5)]
        geometry = make_geometry(vertices, triangles)
        structure = make_structure({resource: triangles}, {resource: 0.0})
        return object_footprints.structure_ring(
            structure, {resource: geometry}, [make_placement(resource)])

    def test_sparse_bases_get_no_pad(self, fake_projection, monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_FOOTPRINT_FILL", 0.1)
        assert self._sparse_ring() is None

    def test_pack_hangar_directory_does_not_disable_the_floor(
            self, fake_projection, monkeypatch):
        # r18b ruling 1 (PARKED behind DSF_OBJECT_NAME_VOUCH_SCOPED):
        # with the gate ON the floors' name-vouch is
        # ``evidence_name_vouches`` — basename or library virtual path —
        # so a payware pack's DIRECTORY name cannot switch them off.
        # Measured at HECA: the wide path-anywhere predicate vouched 667
        # of 817 rings under ``Airport/Hangar_Tower/`` and kept every
        # phantom pad; 817 → 210 rings with the scoped predicate.
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_FOOTPRINT_FILL", 0.1)
        monkeypatch.setattr(config, "DSF_OBJECT_NAME_VOUCH_SCOPED", True)
        assert self._sparse_ring(
            "Airport/Hangar_Tower/jet_blast_02.obj") is None
        assert self._sparse_ring("Airport/Hangar/Plastic.obj") is None

    def test_gate_off_keeps_the_shipped_wide_predicate(
            self, fake_projection, monkeypatch):
        # THE PARKED STATE IS ALSO A CONTRACT (r18b STOP): default OFF is
        # the shipped behaviour — the pack directory still vouches and
        # the floor still yields — so the park is measured, not assumed.
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_FOOTPRINT_FILL", 0.1)
        monkeypatch.setattr(config, "DSF_OBJECT_NAME_VOUCH_SCOPED", False)
        assert self._sparse_ring(
            "Airport/Hangar_Tower/jet_blast_02.obj") is not None

    def test_library_hangar_path_still_vouches_past_the_floor(
            self, fake_projection, monkeypatch):
        # The CYXY 2026-07-28 calibration case, preserved by
        # construction under BOTH gate states: the stock arched hangar's
        # footings project ~0.001 of its hull, and its LIBRARY VIRTUAL
        # PATH is the library author's semantic statement, so the floor
        # yields either way.
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_FOOTPRINT_FILL", 0.1)
        for scoped in (True, False):
            monkeypatch.setattr(
                config, "DSF_OBJECT_NAME_VOUCH_SCOPED", scoped)
            assert self._sparse_ring(
                "lib/airport/Common_Elements/Hangars/hangar_01.obj"
            ) is not None, scoped

    def test_zero_disables_the_gate(self, fake_projection, monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_FOOTPRINT_FILL", 0.0)
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_TALL_BASE_FILL", 0.0)
        assert self._sparse_ring() is not None

    def test_dense_building_passes(self, fake_projection, monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_FOOTPRINT_FILL", 0.1)
        # A solid 20 x 20 floor with an 8 m roof: fill ≈ 1.
        vertices = [
            (0.0, 0.0, 0.0), (20.0, 0.0, 0.0),
            (20.0, 0.0, 20.0), (0.0, 0.0, 20.0),
            (0.0, 8.0, 0.0), (20.0, 8.0, 0.0),
            (20.0, 8.0, 20.0), (0.0, 8.0, 20.0),
        ]
        triangles = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
        geometry = make_geometry(vertices, triangles)
        structure = make_structure({"a.obj": triangles}, {"a.obj": 0.0})
        assert object_footprints.structure_ring(
            structure, {"a.obj": geometry},
            [make_placement("a.obj")]) is not None


class TestStructureRingTallBaseFill:
    """TALL-BASE FILL (owner defect 2026-07-27, HECA building124): a
    SOLID 0.3 m ground plate welded to a 28 m mast defeats the height
    gate (mast supplies extent) AND the base-fill gate (plate supplies
    dense base) — but no TALL member covers the footprint, so it is a
    slab/mast weld, not a building."""

    def _plate_and_mast_ring(self):
        # 40 x 40 solid plate, 0.3 m thick (dense base, short) …
        vertices = [
            (0.0, 0.0, 0.0), (40.0, 0.0, 0.0),
            (40.0, 0.3, 40.0), (0.0, 0.3, 40.0),
        ]
        plate_triangles = [(0, 1, 2), (0, 2, 3)]
        # … plus a 2 x 2 x 28 m mast in one corner (tall, tiny base).
        base = len(vertices)
        vertices += [
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 0.0, 2.0),
            (0.0, 28.0, 0.0), (2.0, 28.0, 0.0), (2.0, 28.0, 2.0),
        ]
        mast_triangles = [(base, base + 1, base + 2),
                          (base + 3, base + 4, base + 5)]
        geometry = make_geometry(vertices,
                                 plate_triangles + mast_triangles)
        structure = make_structure(
            {"plate.obj": plate_triangles, "mast.obj": mast_triangles},
            {"plate.obj": 0.0, "mast.obj": 0.0})
        return object_footprints.structure_ring(
            structure,
            {"plate.obj": geometry, "mast.obj": geometry},
            [make_placement("plate.obj"), make_placement("mast.obj")])

    def test_plate_plus_mast_gets_no_pad(self, fake_projection,
                                         monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_TALL_BASE_FILL", 0.05)
        assert self._plate_and_mast_ring() is None

    def test_zero_disables(self, fake_projection, monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_TALL_BASE_FILL", 0.0)
        assert self._plate_and_mast_ring() is not None

    def test_tall_building_on_plate_passes(self, fake_projection,
                                           monkeypatch):
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_TALL_BASE_FILL", 0.05)
        # A real terminal: a 30 x 30 tall block whose own base covers
        # most of the hull, welded to the same kind of apron plate.
        vertices = [
            (0.0, 0.0, 0.0), (40.0, 0.0, 0.0),
            (40.0, 0.3, 40.0), (0.0, 0.3, 40.0),
        ]
        plate_triangles = [(0, 1, 2), (0, 2, 3)]
        base = len(vertices)
        vertices += [
            (0.0, 0.0, 0.0), (30.0, 0.0, 0.0), (30.0, 0.0, 30.0),
            (0.0, 12.0, 0.0), (30.0, 12.0, 0.0), (30.0, 12.0, 30.0),
        ]
        block_triangles = [(base, base + 1, base + 2),
                           (base + 3, base + 4, base + 5)]
        geometry = make_geometry(vertices,
                                 plate_triangles + block_triangles)
        structure = make_structure(
            {"plate.obj": plate_triangles,
             "terminal.obj": block_triangles},
            {"plate.obj": 0.0, "terminal.obj": 0.0})
        assert object_footprints.structure_ring(
            structure,
            {"plate.obj": geometry, "terminal.obj": geometry},
            [make_placement("plate.obj"),
             make_placement("terminal.obj")]) is not None


# ── R18-2: A BUILDING PAD NEEDS BUILDING EVIDENCE ────────────────────
# Owner ruling 2026-08-11b; spec docs/specs/round18-heca-mesh-and-pads-
# spec.md.  Four HECA pads (172/176/177/186) sat 11-18 m below their own
# ground on footprints that were pack OBJECT rings — apron slabs,
# jersey barriers, fuel trucks, buses — with ZERO OSM buildings under
# them.  The gate: a DSF-object ring may seed a pad only with an
# intersecting OSM building footprint OR a vertical-structure test on
# its own solid geometry.

def _slab_and_member(member_height_m, member_resource="member.obj"):
    """A 40 x 40 apron slab welded to one upright member of the given
    height — the phantom-pad shape (barrier / vehicle) at low heights,
    a building at high ones."""
    vertices = [
        (0.0, 0.0, 0.0), (40.0, 0.0, 0.0),
        (40.0, 0.1, 40.0), (0.0, 0.1, 40.0),
    ]
    slab_triangles = [(0, 1, 2), (0, 2, 3)]
    base = len(vertices)
    vertices += [
        (0.0, 0.0, 0.0), (6.0, 0.0, 0.0), (6.0, 0.0, 6.0),
        (0.0, member_height_m, 0.0), (6.0, member_height_m, 0.0),
        (6.0, member_height_m, 6.0),
    ]
    member_triangles = [(base, base + 1, base + 2),
                        (base + 3, base + 4, base + 5)]
    geometry = make_geometry(vertices, slab_triangles + member_triangles)
    structure = make_structure(
        {"slab.obj": slab_triangles, member_resource: member_triangles},
        {"slab.obj": 0.0, member_resource: 0.0})
    return (structure,
            {"slab.obj": geometry, member_resource: geometry},
            [make_placement("slab.obj"), make_placement(member_resource)])


def _evidence_of(member_height_m, member_resource="member.obj"):
    structure, geometry, placements = _slab_and_member(
        member_height_m, member_resource)
    evidence = {}
    ring = object_footprints.structure_ring(
        structure, geometry, placements, evidence_out=evidence)
    return ring, evidence


class TestVerticalStructureEvidence:
    def test_barrier_height_member_is_not_building_evidence(
            self, fake_projection):
        # 3.00 m is the HECA pack's measured barrier/strip class, and
        # 5.87 m its jet-blast deflectors — the tallest NON-building
        # structure on the field.  Neither vouches at the armed 6.0 m.
        for height in (3.0, 4.53, 5.87):
            ring, evidence = _evidence_of(height)
            assert ring is not None, height       # still a ring …
            assert evidence["vertical_evidence"] is False, height
            assert evidence["verdict"] == "ring"

    def test_building_height_member_is_building_evidence(
            self, fake_projection):
        # 6.09-6.10 m is where the pack's building members start.
        for height in (6.1, 12.0, 113.0):
            ring, evidence = _evidence_of(height)
            assert ring is not None, height
            assert evidence["vertical_evidence"] is True, height

    def test_threshold_moves_the_verdict(self, fake_projection,
                                         monkeypatch):
        # Mutation check: the armed value is what decides, not a
        # coincidence of the fixture.
        monkeypatch.setattr(config, "DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M", 3.0)
        _ring, evidence = _evidence_of(5.87)
        assert evidence["vertical_evidence"] is True
        monkeypatch.setattr(config, "DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M", 20.0)
        _ring, evidence = _evidence_of(12.0)
        assert evidence["vertical_evidence"] is False

    def test_coverage_floor_is_a_second_condition_when_armed(
            self, fake_projection, monkeypatch):
        # Armed at 0 by measurement (a material-split pack's real
        # terminal shells cover as little of their hull as the phantom
        # class), but it must still BE a condition when a pack arms it:
        # the member's one BASE triangle (its roof face sits above the
        # footprint band) covers 18 / 1600 = 0.01125 of the slab hull.
        _ring, evidence = _evidence_of(12.0)
        assert evidence["evidence_coverage"] == pytest.approx(0.01125,
                                                              rel=0.05)
        monkeypatch.setattr(config, "DSF_OBJECT_EVIDENCE_MIN_COVERAGE", 0.5)
        _ring, evidence = _evidence_of(12.0)
        assert evidence["vertical_evidence"] is False

    def test_above_grade_not_total_extent(self, fake_projection):
        # A below-grade pit is not a building however deep (the A11
        # rationale, applied per MEMBER).
        vertices = [
            (0.0, 0.0, 0.0), (40.0, 0.0, 0.0),
            (40.0, 0.1, 40.0), (0.0, 0.1, 40.0),
        ]
        slab_triangles = [(0, 1, 2), (0, 2, 3)]
        base = len(vertices)
        vertices += [
            (0.0, -20.0, 0.0), (6.0, -20.0, 0.0), (6.0, -20.0, 6.0),
            (0.0, 0.05, 0.0), (6.0, 0.05, 0.0), (6.0, 0.05, 6.0),
        ]
        pit_triangles = [(base, base + 1, base + 2),
                         (base + 3, base + 4, base + 5)]
        geometry = make_geometry(vertices, slab_triangles + pit_triangles)
        structure = make_structure(
            {"slab.obj": slab_triangles, "pit.obj": pit_triangles},
            {"slab.obj": 0.0, "pit.obj": -20.0})
        evidence = {}
        object_footprints.structure_ring(
            structure, {"slab.obj": geometry, "pit.obj": geometry},
            [make_placement("slab.obj"), make_placement("pit.obj")],
            evidence_out=evidence)
        assert evidence["vertical_evidence"] is False

    def test_tall_member_coverage_is_one_definition(self):
        # The gate, the twins and tools/object_pad_evidence_report.py
        # all call THIS function; a second implementation of "how tall
        # is it over its own footprint" is the census-wrapper defect.
        members = [("a.obj", 10.0, 2.0), ("b.obj", 1.0, 8.0)]
        assert object_footprints.tall_member_coverage(
            members, 10.0, 6.0) == pytest.approx(0.2)
        assert object_footprints.tall_member_coverage(
            members, 10.0, 0.5) == pytest.approx(1.0)
        assert object_footprints.tall_member_coverage(members, 0.0, 6.0) == 0.0
        assert object_footprints.tallest_member_extent(members) == 10.0
        assert object_footprints.tallest_member_extent([]) == 0.0


class TestEvidenceNameVouching:
    def test_pack_directory_named_hangar_does_not_vouch(self):
        # THE MEASURED TRAP (HECA 2026-08-11): the Tai Models pack files
        # its whole airport under ``Airport/Hangar_Tower/`` and
        # ``Airport/Hangar/``, and a path-anywhere match vouched 667 of
        # its 817 rings — every phantom pad included.
        assert object_footprints.evidence_name_vouches(
            ["Airport/Hangar_Tower/metal_strip_2.obj"]) is False
        assert object_footprints.evidence_name_vouches(
            ["Airport/Hangar/Plastic.obj",
             "Airport/Hangar_Tower/jet_Blash_02.obj"]) is False

    def test_basename_and_library_paths_vouch(self):
        # The CYXY ruling's subject: a STOCK LIBRARY resource whose
        # virtual path is the library author's semantic statement.
        assert object_footprints.evidence_name_vouches(
            ["lib/airport/Common_Elements/Hangars/hangar_01.obj"]) is True
        assert object_footprints.evidence_name_vouches(
            ["Objects/term_building_Ground.obj"]) is True
        assert object_footprints.evidence_name_vouches(
            ["opensceneryx/objects/buildings/terminal_a.obj"]) is True
        assert object_footprints.evidence_name_vouches(
            ["Objects/box.obj"]) is False

    def test_name_vouching_overrides_the_height_test(self, fake_projection):
        _ring, evidence = _evidence_of(
            3.0, member_resource="lib/airport/hangars/shed.obj")
        assert evidence["evidence_name_vouched"] is True
        assert evidence["vertical_evidence"] is True


class TestReaderStampsTheEvidenceRole:
    def test_role_carries_the_vertical_verdict(self, fake_projection,
                                               monkeypatch):
        # The tuple SHAPE is unchanged (role is already a vocabulary);
        # the pipeline reads the role and OR-s it with the OSM half.
        for height, expected in ((3.0, D.OBJECT_BUILDING_UNVOUCHED_ROLE),
                                 (12.0, D.OBJECT_BUILDING_ROLE)):
            structure, geometry, placements = _slab_and_member(height)
            monkeypatch.setattr(
                object_anchor, "partition_structures",
                lambda *args, **kwargs: [structure])
            evidence_records = []
            out = []
            # Drive structure_ring exactly as the reader does.
            evidence = {}
            ring = object_footprints.structure_ring(
                structure, geometry, placements, evidence_out=evidence)
            evidence_records.append(evidence)
            out.append((ring, [],
                        D.OBJECT_BUILDING_ROLE
                        if evidence.get("vertical_evidence")
                        else D.OBJECT_BUILDING_UNVOUCHED_ROLE))
            assert out[0][2] == expected, height

    def test_real_reader_stamps_unvouched_for_a_flat_pack_ring(
            self, tmp_path, monkeypatch):
        # End to end through the real reader: a 40 m box only 3 m tall
        # is a slab, and comes back UNVOUCHED even though it is a ring.
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_BUILDING_HEIGHT_M", 0.0)
        monkeypatch.setattr(config, "DSF_OBJECT_MIN_TALL_BASE_FILL", 0.0)
        body = "\n".join([
            "OBJECT_DEF Objects/slab.obj",
            "OBJECT 0 -80.930000 35.210000 0.000000",
        ]) + "\n"
        dsf_path, pack_root = _write_fake_dsf(tmp_path, body)
        physical = os.path.join(pack_root, "Objects", "slab.obj")
        os.makedirs(os.path.dirname(physical), exist_ok=True)
        with open(physical, "w") as handle:
            handle.write(_REAL_BOX_OBJ)
        buildings, evidence = D.read_dsf_object_building_evidence(
            dsf_path, xplane_root=None)
        assert len(buildings) == 1
        assert buildings[0][2] == D.OBJECT_BUILDING_UNVOUCHED_ROLE
        # The evidence record is populated for every structure the
        # reader considered — that is what the population table reads.
        assert evidence and evidence[0]["verdict"] == "ring"
        assert evidence[0]["vertical_evidence"] is False


class TestPipelineBuildingEvidenceGate:
    """The gate closes in the PIPELINE (R18-2): the reader's vertical
    verdict rides on the role, the OSM half is only knowable here, and
    the two are OR-ed before anything enters the building pool — so a
    refused ring never reaches facade clustering."""

    RING = [(-80.930, 35.210), (-80.929, 35.210), (-80.929, 35.211)]

    def _collect(self, monkeypatch, role, osm=None, **flags):
        monkeypatch.setattr(config, "DSF_OBJECT_BUILDINGS", True)
        for name, value in flags.items():
            monkeypatch.setattr(config, name, value)
        monkeypatch.setattr(
            D, "read_dsf_object_buildings",
            lambda dsf_path, cache_dir=None, xplane_root=None: [
                (self.RING, [], role)])
        refused = []
        admitted = pipeline._collect_dsf_object_building_footprints(
            "/nonexistent.dsf", None,
            lambda outer_ring, hole_rings: True,
            osm_building_evidence=osm, refused_out=refused)
        return admitted, refused

    def test_no_height_and_no_osm_is_refused(self, monkeypatch):
        admitted, refused = self._collect(
            monkeypatch, D.OBJECT_BUILDING_UNVOUCHED_ROLE,
            osm=lambda ring: False)
        assert admitted == 0
        assert refused == [self.RING]

    def test_no_osm_ARM_AT_ALL_is_not_evidence_of_absence(self, monkeypatch):
        # ``osm_building_evidence=None`` means the caller has no OSM in
        # hand — the gate then rests on the vertical test alone, and an
        # unvouched ring is still refused.
        admitted, refused = self._collect(
            monkeypatch, D.OBJECT_BUILDING_UNVOUCHED_ROLE, osm=None)
        assert admitted == 0 and refused == [self.RING]

    def test_osm_building_alone_admits(self, monkeypatch):
        admitted, refused = self._collect(
            monkeypatch, D.OBJECT_BUILDING_UNVOUCHED_ROLE,
            osm=lambda ring: True)
        assert admitted == 1 and refused == []

    def test_vertical_evidence_alone_admits(self, monkeypatch):
        admitted, refused = self._collect(
            monkeypatch, D.OBJECT_BUILDING_ROLE, osm=lambda ring: False)
        assert admitted == 1 and refused == []

    def test_gate_off_admits_everything(self, monkeypatch):
        admitted, refused = self._collect(
            monkeypatch, D.OBJECT_BUILDING_UNVOUCHED_ROLE,
            osm=lambda ring: False,
            DSF_OBJECT_BUILDING_EVIDENCE=False)
        assert admitted == 1 and refused == []


class TestOsmBuildingEvidenceExtraction:
    """Evidence source (a).  Deliberately NOT ``_extract_osm_terminals``:
    that function carries pad-SELECTION policy (the explicit-terminal
    restriction, HANGAR_PADS, the 100 m² pad floor), and reusing it
    would make a DSF ring's admission depend on how mappers tagged some
    other building on the field."""

    def _square(self, x0, y0, size=10.0):
        return [(x0, y0), (x0 + size, y0), (x0 + size, y0 + size),
                (x0, y0 + size), (x0, y0)]

    def _osm(self, tags, x0=0.0, y0=0.0):
        from auto_patch import terminals
        nodes = {}
        node_ids = []
        for index, (x, y) in enumerate(self._square(x0, y0)[:-1]):
            node_id = f"n{x0}_{index}"
            nodes[node_id] = (y, x)          # (lat, lon)
            node_ids.append(node_id)
        node_ids.append(node_ids[0])
        ways = [("w1", node_ids, tags)]
        return terminals._extract_osm_building_evidence(
            nodes, ways, [], lambda lon, lat: (lon, lat))

    def test_plain_building_tag_is_evidence(self):
        assert len(self._osm({"building": "yes"})) == 1
        assert len(self._osm({"building": "warehouse"})) == 1
        assert len(self._osm({"aeroway": "terminal"})) == 1
        assert len(self._osm({"aeroway": "hangar"})) == 1

    def test_non_building_tags_are_not_evidence(self):
        assert self._osm({"aeroway": "taxiway"}) == []
        assert self._osm({"building": "no"}) == []
        assert self._osm({"highway": "service"}) == []

    def test_no_area_floor_a_small_mapped_building_is_evidence(self):
        # ``_extract_osm_terminals`` drops anything under 100 m²; the
        # evidence set must not — a small mapped building is still a
        # building, and the phantom pads have NO building at all.
        from auto_patch import terminals
        nodes, node_ids = {}, []
        for index, (x, y) in enumerate(
                [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]):
            nodes[f"s{index}"] = (y, x)
            node_ids.append(f"s{index}")
        node_ids.append(node_ids[0])
        polygons = terminals._extract_osm_building_evidence(
            nodes, [("w", node_ids, {"building": "yes"})], [],
            lambda lon, lat: (lon, lat))
        assert len(polygons) == 1 and polygons[0].area == pytest.approx(4.0)

    def test_predicate_is_false_with_no_mapped_buildings(self):
        predicate, count = pipeline._osm_building_evidence_predicate(
            {}, [], [], lambda lon, lat: (lon, lat))
        assert count == 0
        assert predicate([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]) is False

    def test_predicate_answers_intersection(self):
        nodes, node_ids = {}, []
        for index, (x, y) in enumerate(
                [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]):
            nodes[f"b{index}"] = (y, x)
            node_ids.append(f"b{index}")
        node_ids.append(node_ids[0])
        predicate, count = pipeline._osm_building_evidence_predicate(
            nodes, [("w", node_ids, {"building": "yes"})], [],
            lambda lon, lat: (lon, lat))
        assert count == 1
        assert predicate([(1.0, 1.0), (2.0, 1.0), (2.0, 2.0)]) is True
        assert predicate([(50.0, 50.0), (51.0, 50.0), (51.0, 51.0)]) is False


class TestPendingDefencesStayOffByMeasurement:
    """Both pending defences were RULED BY MEASUREMENT in this round
    (spec R18-2, "MEASURE what each would have caught ... then arm at
    the values the measurement supports (or report why not)").  Neither
    is armed; these twins pin that decision to its reason, and prove
    each still WORKS when a pack arms it."""

    def test_neither_defence_is_armed(self):
        # HECA measurement (tools/object_pad_evidence_report.py):
        #  * span gate — 6 rings caught at 300 m, 3 already refused by
        #    the evidence gate, and all 3 marginal ones are REAL
        #    buildings (60,392 m² shell, 113 m member).  No value
        #    removes a phantom the evidence gate misses.
        #  * connector pre-filter — drops 192 of the 336 evidence-
        #    vouched rings (433,766 m² of real building footprint): the
        #    documented EGGW/EGLL failure reproduced, because in a
        #    material-split pack EVERY texture page spans the field.
        assert config.DSF_OBJECT_MAX_STRUCTURE_SPAN_M == 0.0
        assert config.DSF_OBJECT_CONNECTOR_PREFILTER is False

    def test_span_gate_still_works_when_a_pack_arms_it(
            self, fake_projection, monkeypatch):
        # Mutation check on the OFF default: the gate is off, not dead.
        structure, geometry, placements = _slab_and_member(12.0)
        assert object_footprints.structure_ring(
            structure, geometry, placements) is not None
        monkeypatch.setattr(config, "DSF_OBJECT_MAX_STRUCTURE_SPAN_M", 10.0)
        evidence = {}
        assert object_footprints.structure_ring(
            structure, geometry, placements,
            evidence_out=evidence) is None
        assert evidence["verdict"] == "max_structure_span"


class TestSegmentedLinearArray:
    """A SEGMENTED LINEAR FEATURE IS NOT N BUILDINGS (owner item 3, LEMD
    sim read of 1.0.269; inside R18-2's evidence gate).

    The LEMD miniature: seven congruent 23 x 21 m modules on a straight
    line at a 25.7 m pitch, all drawn by ONE solo member resource
    (``objects/LEMD_OBJ-Airport_Munoza-LEMD80.obj``, one placement,
    shared-datum authoring).  Each module is 7 m tall and clears the
    vertical-structure test on its own, so nothing about a single ring
    says "not a building" — the signature is the array.
    """

    LATITUDE = 40.4614
    #: degrees of longitude per metre at the fixture's latitude
    @staticmethod
    def _degrees(latitude):
        from auto_patch import obj8_reader
        import math
        return (1.0 / obj8_reader.METRES_PER_DEGREE_LATITUDE,
                1.0 / (obj8_reader.METRES_PER_DEGREE_LATITUDE
                       * math.cos(math.radians(latitude))))

    def _module(self, index, *, pitch_m=25.7, width_m=23.0, depth_m=21.0,
                offset_m=0.0, latitude=None):
        latitude = self.LATITUDE if latitude is None else latitude
        dlat, dlon = self._degrees(latitude)
        x0 = index * pitch_m * dlon
        y0 = offset_m * dlat
        w, d = 0.5 * width_m * dlon, 0.5 * depth_m * dlat
        cx, cy = -3.5398 + x0, latitude + y0
        return [(cx - w, cy - d), (cx + w, cy - d),
                (cx + w, cy + d), (cx - w, cy + d), (cx - w, cy - d)]

    def _row(self, n, resource="objects/LEMD80.obj", **kw):
        return [((resource,), self._module(i, **kw)) for i in range(n)]

    def test_the_lemd_row_of_seven_is_one_object(self):
        found = object_footprints.segmented_linear_array_indices(
            self._row(7))
        assert found == set(range(7))

    def test_three_modules_are_not_an_array(self):
        """SEGMENTED_ARRAY_MIN_MEMBERS: three colinear congruent rings
        happen; four at an even pitch do not."""
        assert object_footprints.segmented_linear_array_indices(
            self._row(3)) == set()

    def test_two_resources_in_one_structure_never_group(self):
        """Only SOLO-member structures are stamped modules."""
        rows = [(("a.obj", "b.obj"), ring)
                for _r, ring in self._row(7)]
        assert object_footprints.segmented_linear_array_indices(
            rows) == set()

    def test_different_resources_do_not_group_with_each_other(self):
        rows = [((f"obj{i}.obj",), ring)
                for i, (_r, ring) in enumerate(self._row(7))]
        assert object_footprints.segmented_linear_array_indices(
            rows) == set()

    def test_unequal_spacing_is_not_an_array(self):
        rows = self._row(7)
        # Push one module far out of the even pitch (spacing CV blows up).
        rows[6] = (rows[6][0], self._module(20))
        assert object_footprints.segmented_linear_array_indices(
            rows) == set()

    def test_a_bent_chain_is_not_an_array(self):
        rows = [((("objects/LEMD80.obj"),), self._module(
            i, offset_m=(0.0 if i < 4 else 40.0)))
            for i in range(7)]
        rows = [(("objects/LEMD80.obj",), r[1]) for r in rows]
        assert object_footprints.segmented_linear_array_indices(
            rows) == set()

    def test_differently_sized_modules_are_not_an_array(self):
        rows = self._row(7)
        rows[3] = (rows[3][0], self._module(3, width_m=40.0))
        assert object_footprints.segmented_linear_array_indices(
            rows) == set()

    def test_a_short_block_of_identical_sheds_is_not_an_array(self):
        """SEGMENTED_ARRAY_MIN_LENGTH_IN_WIDTHS: four 23 m modules at a
        24 m pitch span 72 m — barely 3 widths — and read as a block, not
        a line."""
        assert object_footprints.segmented_linear_array_indices(
            self._row(4, pitch_m=24.0)) == set()

    def test_the_verdict_is_a_demotion_not_a_drop(self):
        """The reader stamps the UNVOUCHED role, so R18-2's OSM half
        still decides — a real mapped row of hangars keeps its pads."""
        import inspect
        from auto_patch import dsf_reader
        source = inspect.getsource(dsf_reader._compute_dsf_object_buildings)
        assert "segmented_linear_array_indices" in source
        assert "OBJECT_BUILDING_UNVOUCHED_ROLE" in source
