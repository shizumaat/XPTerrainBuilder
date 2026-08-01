"""Object-derived BASIN trenches — the open-pit limb of feature C
(``docs/object_terrain_features_spec.md`` section 3.4, owner defect
2026-07-30).

The reported defect, at OTHH (Aeroscape): the pack models drainage
basins as open pits whose rim is flush with grade and whose body reaches
~3.8 m below it.  Two things went wrong and both are covered here.

* The pit read as a BUILDING.  ``object_footprints.structure_ring``
  measured TOTAL vertical extent against the A11 has-walls floor, so a
  3.87 m hole passed as a 3.87 m building and got a flat pad that buried
  it (measured: 2 337 m² at Drainage_04, 20 055 m² at Drainage_06).
* The pit read as FLAT.  The bowl rule's only "is this sunken" signal
  was the ground-contact fraction, and a shallow open basin's own rim
  and upper batter sit inside the ±1 m ground band — the SHALLOWER the
  pit the MORE ground contact it scores (measured 0.44-0.68 across the
  six OTHH basins, against a 0.10 bowl gate).  Nothing was ever carved.

Fixtures are synthetic (ruling R6): hand-built pit / building geometry
and a minimal fake layout and DEM.  No third-party pack content enters
the repository.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from shapely.geometry import Polygon  # noqa: E402

from auto_patch import bridges  # noqa: E402
from auto_patch import config  # noqa: E402
from auto_patch import grade_law  # noqa: E402
from auto_patch import object_anchor  # noqa: E402
from auto_patch import object_footprints  # noqa: E402
from auto_patch import object_terrain_assembly as assembly  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.layout import ROLE_TUNNEL_TRENCH  # noqa: E402
from auto_patch.obj8_reader import (  # noqa: E402
    ObjectGeometry,
    ObjectPlacement,
)

ANCHOR_LATITUDE = 25.2539
ANCHOR_LONGITUDE = 51.6221
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)

TILE_LATITUDE = 25
TILE_LONGITUDE = 51


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------

class _GeometryBuilder:
    """Accumulate up-facing rectangles into an :class:`ObjectGeometry`.

    Deliberately the same shape of helper as
    ``test_object_terrain_features._GeometryBuilder`` but local: these
    tests need SLOPED batter faces (a real basin's sides are ≤45° earth
    slopes, not vertical walls — measured at OTHH: ~100 % of every
    basin's face area is near-horizontal), and keeping the fixture beside
    the tests it serves is the repo's harness pattern.
    """

    def __init__(self) -> None:
        self.vertices: list[tuple[float, float, float]] = []
        self.solid: list[tuple[int, int, int]] = []
        self.hardness: list[str] = []

    def _vertex(self, x: float, y: float, z: float) -> int:
        self.vertices.append((x, y, z))
        return len(self.vertices) - 1

    def add_horizontal_rectangle(
        self, x0: float, x1: float, z0: float, z1: float, y: float,
        *, hardness: str = "", segments: int = 1,
    ) -> None:
        for segment in range(segments):
            sx0 = x0 + (x1 - x0) * segment / segments
            sx1 = x0 + (x1 - x0) * (segment + 1) / segments
            a = self._vertex(sx0, y, z0)
            b = self._vertex(sx1, y, z0)
            c = self._vertex(sx1, y, z1)
            d = self._vertex(sx0, y, z1)
            self.solid.append((a, b, c))
            self.solid.append((a, c, d))
            self.hardness.extend([hardness, hardness])

    def add_sloped_rectangle(
        self, x0: float, x1: float, z0: float, z1: float,
        y0: float, y1: float, *, hardness: str = "",
    ) -> None:
        a = self._vertex(x0, y0, z0)
        b = self._vertex(x1, y1, z0)
        c = self._vertex(x1, y1, z1)
        d = self._vertex(x0, y0, z1)
        self.solid.append((a, b, c))
        self.solid.append((a, c, d))
        self.hardness.extend([hardness, hardness])

    def add_vertical_wall(
        self, x: float, z0: float, z1: float, y0: float, y1: float
    ) -> None:
        a = self._vertex(x, y0, z0)
        b = self._vertex(x, y0, z1)
        c = self._vertex(x, y1, z1)
        d = self._vertex(x, y1, z0)
        self.solid.append((a, b, c))
        self.solid.append((a, c, d))
        self.hardness.extend(["", ""])

    def build(self) -> ObjectGeometry:
        return ObjectGeometry(
            vertices=list(self.vertices),
            solid_triangles=list(self.solid),
            draped_triangles=[],
            positional_commands=[],
            animation_block_count=0,
            level_of_detail_count=0,
            vertex_line_indices=list(range(len(self.vertices))),
            solid_triangle_hardness=tuple(self.hardness),
        )


def _placement(
    resource_path: str,
    *,
    longitude: float = ANCHOR_LONGITUDE,
    latitude: float = ANCHOR_LATITUDE,
) -> ObjectPlacement:
    return ObjectPlacement(
        definition_index=0,
        resource_path=resource_path,
        longitude=longitude,
        latitude=latitude,
        heading_degrees=0.0,
        above_ground_level_metres=0.0,
        placement_kind="OBJECT",
        mean_sea_level_elevation_m=None,
    )


def _pit_shell(
    half_span_m: float, batter_m: float, floor_y: float, rim_y: float
) -> ObjectGeometry:
    """One shell of an open pit: a flat floor at ``floor_y``, four sloped
    batters rising to ``rim_y``, and one steep headwall.

    The batters carry nearly all the face AREA (measured on the real
    objects: ~100 % of every basin's face area is near-horizontal), while
    the headwall — the concrete inlet structure every drainage basin has
    — is what puts floor and rim vertices in ONE plan cell and so gives
    the structure its wall COLUMNS.  Both are needed: area drives the
    ground-contact and above-grade fractions, columns drive the interface
    levels.  The real ``OTHH_Drainage_0N`` pairs measure 12 such columns
    of 46 plan cells, one of them spanning −3.82 .. +0.06 within a single
    shell.
    """
    builder = _GeometryBuilder()
    inner = half_span_m - batter_m
    builder.add_horizontal_rectangle(
        -inner, inner, -inner, inner, floor_y, segments=3)
    builder.add_sloped_rectangle(
        -half_span_m, -inner, -half_span_m, half_span_m, rim_y, floor_y)
    builder.add_sloped_rectangle(
        inner, half_span_m, -half_span_m, half_span_m, floor_y, rim_y)
    builder.add_sloped_rectangle(
        -half_span_m, half_span_m, -half_span_m, -inner, rim_y, rim_y)
    builder.add_sloped_rectangle(
        -half_span_m, half_span_m, inner, half_span_m, rim_y, rim_y)
    builder.add_vertical_wall(inner, -inner, inner, floor_y, rim_y)
    return builder.build()


def _open_pit_pair(
    *,
    half_span_m: float = 30.0,
    batter_m: float = 6.0,
    depth_m: float = 4.0,
) -> dict[str, ObjectGeometry]:
    """An OTHH-class drainage basin the way the pack actually ships one:
    TWO co-located shells (an outer earthwork and an inner liner) at
    slightly different floors and rim heights, sharing an anchor.

    The stacked pair is what gives the structure wall COLUMNS — a 1 m
    plan cell spanning liner floor to outer rim — which is exactly how
    the real ``OTHH_Drainage_0N_000`` / ``_001`` pairs measure (verified
    on the pack: 12 of 46 plan cells clear the 2.5 m column extent, most
    of them spanning both shells).  Nothing in either shell reaches above
    grade, which is the signal the open-pit limb keys on.
    """
    return {
        "Buildings/Drainage/basin_000.obj": _pit_shell(
            half_span_m, batter_m, -abs(depth_m) + 0.6, 0.0),
        "Buildings/Drainage/basin_001.obj": _pit_shell(
            half_span_m - 1.5, batter_m, -abs(depth_m), 0.06),
    }


def _at_grade_building_geometry(
    *, half_span_m: float = 30.0, height_m: float = 12.0,
    base_y: float = 0.0,
) -> ObjectGeometry:
    """A plain building: a slab at ``base_y``, walls rising from it, roof
    well above grade — the structure the pit rules must never claim."""
    builder = _GeometryBuilder()
    builder.add_horizontal_rectangle(
        -half_span_m, half_span_m, -half_span_m, half_span_m, base_y,
        segments=3)
    builder.add_horizontal_rectangle(
        -half_span_m, half_span_m, -half_span_m, half_span_m, height_m,
        segments=3)
    for x in (-half_span_m, half_span_m):
        builder.add_vertical_wall(
            x, -half_span_m, half_span_m, base_y, height_m)
    return builder.build()


class _FakeDem:
    nodata = -32768

    def __init__(self, elevation_m: float) -> None:
        self.elevation_m = elevation_m

    def alt(self, _xy) -> float:
        return self.elevation_m


class _FakeLayout:
    def __init__(self) -> None:
        self.anchor = ANCHOR
        self.shapes: list = []
        self.icao = "TEST"
        self._to_meters, self._meters_to_lat_lon = (
            bridges._local_meter_projections(ANCHOR)
        )
        from auto_patch.canonical_points import CanonicalPointRegistry
        self.canonical_points = CanonicalPointRegistry()

    def ll_to_m(self, latitude: float, longitude: float):
        return self._to_meters(longitude, latitude)

    def m_to_ll(self, x: float, y: float):
        return self._meters_to_lat_lon(x, y)


class _Classification:
    """Just enough of ``ClassificationResult`` for the emitter."""

    def __init__(self, *, tunnels=(), ground_interfaces=()) -> None:
        self.bridges: list = []
        self.tunnels = list(tunnels)
        self.ground_interfaces = list(ground_interfaces)
        self.exclusions: list = []
        self.refusals: list = []


def _interface(
    *,
    interface_class: str = otf.INTERFACE_BOWL_UNDER_DECK,
    floor_y_m: float | None = -4.0,
    footprint: Polygon | None = None,
    resources=("Buildings/Drainage/basin.obj",),
    above_grade_area_fraction: float = 0.0,
) -> otf.StructureGroundInterface:
    return otf.StructureGroundInterface(
        object_resources=list(resources),
        anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        frame_origin_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        heading_degrees=0.0,
        perimeter_base_profile=[],
        interface_levels=[],
        split_level=False,
        ground_contact_fraction=0.5,
        ground_contact_fraction_by_sector=[],
        at_grade_wall_base_share=0.0,
        interface_class=interface_class,
        below_grade_footprint=(
            Polygon([(-25, -25), (25, -25), (25, 25), (-25, 25)])
            if footprint is None
            else footprint
        ),
        floor_y_m=floor_y_m,
        floor_is_bound_not_target=True,
        elevated_deck_above=False,
        above_grade_area_fraction=above_grade_area_fraction,
    )


def _classify(geometry_by_resource):
    placements = [_placement(resource) for resource in geometry_by_resource]
    return otf.classify_object_terrain_features(
        placements, geometry_by_resource, pack_root="PACK",
        basin_trench_enabled=True,
    )


def _basin_plates(layout, suffix):
    return [
        shape for shape in layout.shapes
        if shape.role == ROLE_TUNNEL_TRENCH
        and str(shape.ref) == f"object_basin_{suffix}"
    ]


@pytest.fixture(autouse=True)
def basin_gate_on(monkeypatch):
    """Default-on in production; pinned here so a config edit cannot make
    these tests silently vacuous.  The gate-off test flips it back."""
    monkeypatch.setattr(config, "OBJECT_BASIN_TRENCH", True)


# ---------------------------------------------------------------------------
# the pit is not a building (object_footprints, A11 above-grade extent)
# ---------------------------------------------------------------------------

class TestPitIsNotABuilding:
    def _ring(self, geometry_by_resource):
        placements = [
            _placement(resource) for resource in geometry_by_resource]
        resolved = {
            resource: resource for resource in geometry_by_resource}
        pools = object_anchor.discover_object_pools(
            placements, resolved, geometry_by_resource,
            epsilon_metres=config.DSF_OBJECT_CONTACT_EPSILON_M,
        )
        rings = []
        for pool in pools:
            pool_geometry = {
                resource: geometry_by_resource[resource]
                for resource in pool.resolved_paths}
            for structure in object_anchor.partition_structures(
                    pool, pool_geometry,
                    epsilon_metres=config.DSF_OBJECT_CONTACT_EPSILON_M):
                ring = object_footprints.structure_ring(
                    structure, pool_geometry, pool.placements)
                if ring is not None:
                    rings.append(ring)
        return rings

    def test_below_grade_pit_gets_no_building_pad(self):
        """The reported defect: a 4 m-deep pit has 4 m of extent, but not
        one millimetre of it stands above grade."""
        assert self._ring(_open_pit_pair(depth_m=4.0)) == []

    def test_ordinary_building_still_gets_its_pad(self):
        rings = self._ring(
            {"terminal.obj": _at_grade_building_geometry(height_m=12.0)})
        assert len(rings) == 1
        assert len(rings[0]) >= 3

    def test_sunk_building_measured_from_grade_not_from_its_footings(self):
        """A building whose footings start below grade keeps its pad — the
        gate clamps at grade, it does not require a base AT grade."""
        rings = self._ring({"sunk.obj": _at_grade_building_geometry(
            half_span_m=20.0, height_m=9.0, base_y=-1.5)})
        assert len(rings) == 1


# ---------------------------------------------------------------------------
# the pit is a bowl (object_terrain_features, open-pit limb)
# ---------------------------------------------------------------------------

class TestOpenPitClassification:
    def test_shallow_open_pit_is_a_bowl_despite_ground_contact(self):
        result = _classify(_open_pit_pair(depth_m=4.0))
        assert len(result.ground_interfaces) == 1
        interface = result.ground_interfaces[0]
        assert interface.interface_class == otf.INTERFACE_BOWL_UNDER_DECK
        # The A7 ground-contact limb alone would REFUSE this structure —
        # that is the whole defect.  Its own rim is inside the ground band.
        assert (interface.ground_contact_fraction
                > otf.BOWL_MAX_GROUND_CONTACT_FRACTION)
        # The signal a pit cannot fake: nothing above grade.
        assert (interface.above_grade_area_fraction
                <= otf.BOWL_MAX_ABOVE_GRADE_AREA_FRACTION)
        assert interface.floor_y_m is not None
        assert interface.floor_y_m < 0.0

    def test_at_grade_building_stays_flat_confirmed(self):
        """The ELLX decoy guard: real above-grade geometry with bases at
        grade is flat terrain and object-carried drama, never a pit."""
        result = _classify(
            {"terminal.obj": _at_grade_building_geometry(height_m=12.0)})
        assert len(result.ground_interfaces) == 1
        interface = result.ground_interfaces[0]
        assert interface.interface_class == otf.INTERFACE_FLAT_CONFIRMED
        assert (interface.above_grade_area_fraction
                > otf.BOWL_MAX_ABOVE_GRADE_AREA_FRACTION)

    def test_trench_spine_keeps_precedence_over_the_pit_limb(self):
        """LFPG-T2 pattern: halls at grade over one continuous −7.5 m
        level.  It has nothing above +1 m either, so the open-pit limb
        must YIELD — TRENCH_SPINE is the narrower, correct verdict."""
        geometry = {}
        for part_index in range(3):
            builder = _GeometryBuilder()
            x0 = -30.0 + part_index * 20.0
            x1 = x0 + 20.0
            builder.add_horizontal_rectangle(x0, x1, -10, 10, 0.0, segments=2)
            builder.add_horizontal_rectangle(
                x0, x1, -10, 10, -7.5, segments=2)
            builder.add_vertical_wall(x0, -10, 10, -7.5, 0.0)
            builder.add_vertical_wall(x1, -10, 10, -7.5, 0.0)
            geometry[f"hall_{part_index}.obj"] = builder.build()
        result = _classify(geometry)
        assert len(result.ground_interfaces) == 1
        assert (result.ground_interfaces[0].interface_class
                == otf.INTERFACE_TRENCH_SPINE)

    def test_pit_inside_a_terminals_pool_is_still_a_pit(self):
        """The OTHH Drainage_05 defect: pools group by world-footprint
        OVERLAP, not by structure, so a basin standing inside a terminal
        complex's footprint had its pit metrics averaged away by the
        terminal (measured 0.944 above-grade area) and vanished into
        FLAT_CONFIRMED — while the geometrically identical Drainage_04,
        which happened to pool alone, classified as a bowl.  Pit
        COMPONENTS are classified on their own frames."""
        geometry = dict(_open_pit_pair(depth_m=4.0))
        geometry["Buildings/Terminal/terminal.obj"] = (
            _at_grade_building_geometry(half_span_m=120.0, height_m=25.0))
        result = _classify(geometry)
        pits = [interface for interface in result.ground_interfaces
                if otf.is_carved_basin_interface(interface)]
        assert len(pits) == 1
        assert set(pits[0].object_resources) == set(_open_pit_pair())
        assert pits[0].floor_y_m == pytest.approx(-4.0, abs=0.3)
        # The terminal is NOT dragged into the pit's record, and keeps its
        # own flat verdict.
        assert any(
            interface.interface_class == otf.INTERFACE_FLAT_CONFIRMED
            and "Buildings/Terminal/terminal.obj"
            in interface.object_resources
            for interface in result.ground_interfaces)

    def test_pit_component_pass_is_gated(self):
        """With the adapter off nothing consumes the components, so the
        pass must not run and change what stage 3 sees."""
        geometry = dict(_open_pit_pair(depth_m=4.0))
        geometry["Buildings/Terminal/terminal.obj"] = (
            _at_grade_building_geometry(half_span_m=120.0, height_m=25.0))
        result = otf.classify_object_terrain_features(
            [_placement(resource) for resource in geometry], geometry,
            pack_root="PACK", basin_trench_enabled=False,
        )
        assert not [interface for interface in result.ground_interfaces
                    if otf.is_carved_basin_interface(interface)]

    def test_shallow_scrape_is_not_a_bowl(self):
        """Depth still has to clear BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M —
        a 2.6 m dip is sunk-object slack, not a basin (the round-5
        calibration: every true bowl measures −3.41 m or deeper, every
        false positive between −1.03 and −2.47)."""
        result = _classify(_open_pit_pair(depth_m=2.6))
        assert all(
            interface.interface_class != otf.INTERFACE_BOWL_UNDER_DECK
            for interface in result.ground_interfaces)


# ---------------------------------------------------------------------------
# the carve predicate (one source of truth for carved AND excluded)
# ---------------------------------------------------------------------------

class TestCarvePredicate:
    def test_bowl_with_footprint_and_floor_is_carved(self):
        assert otf.is_carved_basin_interface(_interface())

    def test_trench_spine_is_carved(self):
        assert otf.is_carved_basin_interface(
            _interface(interface_class=otf.INTERFACE_TRENCH_SPINE))

    def test_flat_is_never_carved(self):
        assert not otf.is_carved_basin_interface(
            _interface(interface_class=otf.INTERFACE_FLAT_CONFIRMED))

    def test_interior_cutout_is_not_this_features_business(self):
        """Ruling R10 cuts inside the at-grade perimeter — a different
        shape from the open trench, and it has no emitter yet."""
        assert not otf.is_carved_basin_interface(
            _interface(interface_class=otf.INTERFACE_INTERIOR_CUTOUT))

    def test_missing_floor_is_not_carved(self):
        assert not otf.is_carved_basin_interface(_interface(floor_y_m=None))

    def test_floor_at_or_above_grade_is_not_carved(self):
        assert not otf.is_carved_basin_interface(_interface(floor_y_m=0.0))

    def test_empty_footprint_is_not_carved(self):
        assert not otf.is_carved_basin_interface(
            _interface(footprint=Polygon()))


# ---------------------------------------------------------------------------
# ruling R13 — which carved basins may cut pavement (the NARROWER predicate)
# ---------------------------------------------------------------------------

class TestOpenPitPredicate:
    """Owner ruling 2026-07-30: "for below grade drainage objects, cut a
    trench in the pavement".  Removing taxiable pavement is only right
    where the hole is open to the sky, so R13 keys on the bowl rule's own
    open-pit limb — not on the wider carve predicate."""

    def test_open_pit_cuts_pavement(self):
        assert otf.is_open_pit_interface(
            _interface(above_grade_area_fraction=0.0))

    def test_bowl_with_something_standing_over_it_keeps_r2(self):
        """The amendment-A7 limb (LFPG Terminal 1's drum over its sunken
        floor): the pack's own structure is the visible surface, so
        pavement still wins."""
        assert not otf.is_open_pit_interface(
            _interface(above_grade_area_fraction=0.35))

    def test_trench_spine_keeps_r2_even_with_nothing_above(self):
        """LFPG Terminal 2 / the OTHH Dewatering pits: halls at grade over
        one continuous below-grade level.  Carved, never pavement-cut."""
        interface = _interface(
            interface_class=otf.INTERFACE_TRENCH_SPINE,
            above_grade_area_fraction=0.0)
        assert otf.is_carved_basin_interface(interface)
        assert not otf.is_open_pit_interface(interface)

    def test_uncarved_interfaces_never_cut(self):
        for interface in (
            _interface(interface_class=otf.INTERFACE_FLAT_CONFIRMED),
            _interface(interface_class=otf.INTERFACE_INTERIOR_CUTOUT),
            _interface(floor_y_m=None),
            _interface(floor_y_m=0.0),
        ):
            assert not otf.is_open_pit_interface(interface)

    def test_the_gate_is_exactly_the_bowl_rules_own_limb(self):
        """Keyed on the classifier's constant, not a second threshold that
        could drift away from it."""
        limb = otf.BOWL_MAX_ABOVE_GRADE_AREA_FRACTION
        assert otf.is_open_pit_interface(
            _interface(above_grade_area_fraction=limb))
        assert not otf.is_open_pit_interface(
            _interface(above_grade_area_fraction=limb * 2.0))


# ---------------------------------------------------------------------------
# the adapter (feature-C interface -> feature-A trench record)
# ---------------------------------------------------------------------------

class TestBasinTrenchAdapter:
    def test_floor_and_depth_come_from_the_objects_own_floor(self):
        records = assembly.basin_trench_structures(
            _Classification(ground_interfaces=[_interface(floor_y_m=-3.81)]))
        assert len(records) == 1
        record = records[0]
        assert record.body_depth_m == pytest.approx(3.81)
        assert record.solid_minimum_y_m == pytest.approx(-3.81)
        # No roof: an open pit's WHOLE footprint is cut.
        assert record.roof_footprint is None
        assert record.deck_footprint is not None
        assert record.terrain_feature == otf.TERRAIN_FEATURE_BASIN
        # The classifier already folded any AGL offset into its effective
        # heights; re-applying it here would double-count.
        assert record.above_ground_offset_m == 0.0

    def test_flat_interfaces_produce_no_records(self):
        records = assembly.basin_trench_structures(
            _Classification(ground_interfaces=[
                _interface(interface_class=otf.INTERFACE_FLAT_CONFIRMED)]))
        assert records == []

    def test_classification_without_interfaces_is_safe(self):
        assert assembly.basin_trench_structures(_Classification()) == []


# ---------------------------------------------------------------------------
# birth through the shared feature-A emitter
# ---------------------------------------------------------------------------

class TestBasinTrenchBirth:
    def _emit(self, layout, interfaces, datum_m=8.0):
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(ground_interfaces=interfaces))
        return assembly.build_tunnel_layout_shapes(
            layout, _FakeDem(datum_m), TILE_LATITUDE, TILE_LONGITUDE)

    def test_floor_and_rim_born_at_the_trench_law_values(self):
        layout = _FakeLayout()
        floors, rims = self._emit(
            layout, [_interface(floor_y_m=-3.81)], datum_m=8.0)
        assert floors >= 1
        assert rims >= 1
        expected_floor = grade_law.tunnel_trench_floor_elevation_m(8.0, -3.81)
        for plate in _basin_plates(layout, "trench"):
            assert plate.node_altitudes
            assert all(altitude == pytest.approx(expected_floor)
                       for altitude in plate.node_altitudes)
        for plate in _basin_plates(layout, "rim"):
            assert plate.node_altitudes
            assert all(altitude == pytest.approx(8.0)
                       for altitude in plate.node_altitudes)

    def test_floor_sits_strictly_below_the_modelled_basin_floor(self):
        """The whole point: the mesh must clear the object so the basin
        is visible, never sit at or above its floor."""
        layout = _FakeLayout()
        self._emit(layout, [_interface(floor_y_m=-3.81)], datum_m=8.0)
        object_floor_world = 8.0 - 3.81
        for plate in _basin_plates(layout, "trench"):
            assert all(altitude < object_floor_world
                       for altitude in plate.node_altitudes)

    def test_plates_are_named_for_the_classifier_that_produced_them(self):
        layout = _FakeLayout()
        self._emit(layout, [_interface()])
        assert _basin_plates(layout, "trench")
        assert not [
            shape for shape in layout.shapes
            if str(shape.ref).startswith("object_tunnel")]

    def test_basin_never_pins_the_pavement_solver(self):
        """Ruling R2, same as the tunnel trench: off-pavement terrain must
        not enter the pavement pin registry, or the deep floor drags the
        adjacent airside pavement down through the one-solve."""
        layout = _FakeLayout()
        self._emit(layout, [_interface()])
        plates = _basin_plates(layout, "trench") + _basin_plates(layout, "rim")
        assert plates
        for plate in plates:
            assert plate.role == ROLE_TUNNEL_TRENCH
            assert not getattr(plate, "pins", None)

    def test_gate_off_births_nothing(self, monkeypatch):
        monkeypatch.setattr(config, "OBJECT_BASIN_TRENCH", False)
        layout = _FakeLayout()
        floors, rims = self._emit(layout, [_interface()])
        assert (floors, rims) == (0, 0)
        assert layout.shapes == []

    def test_tunnel_gate_off_does_not_disable_basins(self):
        """The two gates are independent — a pack with no tunnels still
        gets its pits cut."""
        layout = _FakeLayout()
        import unittest.mock as mock
        with mock.patch.object(config, "OBJECT_TUNNEL_TERRAIN", False):
            floors, _rims = self._emit(layout, [_interface()])
        assert floors >= 1


# ---------------------------------------------------------------------------
# ruling R13 — the open pit takes the pavement with it
# ---------------------------------------------------------------------------

class TestOpenPitPavementCut:
    """Owner ruling 2026-07-30.  The two OTHH basins the owner reported
    lay WHOLLY under an apron (the pack's own DSF draws asphalt across the
    pit; apt.dat leaves the notch unpaved, and auto_patch unions the two),
    so under ruling R2 the floor pan yielded to the last square metre —
    Drainage_04 2 054 of 2 055 m², Drainage_05 all 519 m² — and no plate
    was ever born."""

    #: comfortably larger than the 50 x 50 m default pit footprint
    APRON = Polygon([(-90, -90), (90, -90), (90, 90), (-90, 90)])

    def _layout_with_apron(self, apron=None):
        from auto_patch.layout import ROLE_APRON
        layout = _FakeLayout()
        layout.shapes.append(bridges.BuiltShape(
            polygon=self.APRON if apron is None else apron,
            role=ROLE_APRON, ref="apron", altitude=8.0))
        return layout

    def _emit(self, layout, interfaces, datum_m=8.0):
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(ground_interfaces=interfaces))
        return assembly.build_tunnel_layout_shapes(
            layout, _FakeDem(datum_m), TILE_LATITUDE, TILE_LONGITUDE)

    def _apron_area(self, layout):
        from auto_patch.layout import ROLE_APRON
        return sum(shape.polygon.area for shape in layout.shapes
                   if shape.role == ROLE_APRON)

    def test_pit_under_an_apron_is_still_cut(self):
        """The reported defect, end to end: apron over the whole body, and
        a trench floor is born anyway."""
        layout = self._layout_with_apron()
        floors, _rims = self._emit(layout, [_interface(floor_y_m=-3.81)])
        assert floors >= 1
        assert _basin_plates(layout, "trench")

    def test_the_apron_loses_exactly_the_pit_footprint(self):
        layout = self._layout_with_apron()
        before = self._apron_area(layout)
        self._emit(layout, [_interface(floor_y_m=-3.81)])
        after = self._apron_area(layout)
        pit_area = _interface().below_grade_footprint.area
        assert after == pytest.approx(before - pit_area, rel=0.02)
        # ...and the pit's own middle is no longer pavement.
        from shapely.geometry import Point
        from auto_patch.layout import ROLE_APRON
        centre = Point(*layout.ll_to_m(ANCHOR_LATITUDE, ANCHOR_LONGITUDE))
        assert not [shape for shape in layout.shapes
                    if shape.role == ROLE_APRON
                    and shape.polygon.covers(centre)]

    def test_the_anchor_seat_is_judged_after_the_cut(self):
        """ORDERING guard.  The anchor seat only fires where no earlier
        shape owns the anchor, so R13 must cut BEFORE it is judged — with
        the apron still in place the seat declines, and the object then
        drapes on our own trench floor and sinks by the cut depth (the
        "object sitting below terrain" defect the seat exists for).  The
        default fixture anchors at the centre of its own pit."""
        layout = self._layout_with_apron()
        self._emit(layout, [_interface(floor_y_m=-3.81)])
        assert _basin_plates(layout, "anchor_seat"), (
            "no anchor seat — the seat was judged while the apron still "
            "owned the anchor")

    def test_a_trench_spine_under_an_apron_still_yields(self):
        """The scope guard: R13 is the OPEN-pit limb only.  A carved basin
        with the pack's own halls over it keeps ruling R2 — the apron is
        untouched and nothing is born under it."""
        layout = self._layout_with_apron()
        before = self._apron_area(layout)
        floors, rims = self._emit(layout, [_interface(
            interface_class=otf.INTERFACE_TRENCH_SPINE,
            above_grade_area_fraction=0.0)])
        assert (floors, rims) == (0, 0)
        assert self._apron_area(layout) == pytest.approx(before)

    def test_gate_off_leaves_the_apron_alone(self, monkeypatch):
        monkeypatch.setattr(config, "OBJECT_BASIN_TRENCH", False)
        layout = self._layout_with_apron()
        before = self._apron_area(layout)
        assert self._emit(layout, [_interface()]) == (0, 0)
        assert self._apron_area(layout) == pytest.approx(before)

    def test_a_cut_that_seats_no_floor_is_put_back(self):
        """Pavement removed with no trench under it is a HOLE in the
        drivable surface — strictly worse than the buried pit.  Here a
        building pad owns the whole body, so the floor pan is eaten after
        the cut and the apron must be restored."""
        from auto_patch.layout import ROLE_BUILDING
        layout = self._layout_with_apron()
        layout.shapes.append(bridges.BuiltShape(
            polygon=Polygon([(-60, -60), (60, -60), (60, 60), (-60, 60)]),
            role=ROLE_BUILDING, ref="pad", altitude=8.0))
        before = self._apron_area(layout)
        floors, rims = self._emit(layout, [_interface()])
        assert (floors, rims) == (0, 0)
        assert self._apron_area(layout) == pytest.approx(before)

    def test_a_pit_under_LANDSIDE_pavement_is_cut_too(self):
        """Measured at OTHH: two of the six basins are buried by
        GROUNDSIDE pavement with zero apron over them (Drainage_02 100 %
        of its body, Drainage_06 4 155 of 5 121 m²).  Gating R13 on the
        airside union alone would skip them entirely."""
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        layout = _FakeLayout()
        layout.shapes.append(bridges.BuiltShape(
            polygon=self.APRON, role=ROLE_GROUNDSIDE_PAVEMENT,
            ref="groundside", altitude=8.0))
        before = sum(shape.polygon.area for shape in layout.shapes
                     if shape.role == ROLE_GROUNDSIDE_PAVEMENT)
        floors, _rims = self._emit(layout, [_interface(floor_y_m=-3.81)])
        after = sum(shape.polygon.area for shape in layout.shapes
                    if shape.role == ROLE_GROUNDSIDE_PAVEMENT)
        assert floors >= 1
        pit_area = _interface().below_grade_footprint.area
        assert after == pytest.approx(before - pit_area, rel=0.02)

    def test_r8_scope_is_not_widened_by_r13(self):
        """R13 needs landside pavement; R8 (hard decks in the airside
        network) must keep the scope it had."""
        assert (bridges.pavement_cut_roles()
                == bridges.pavement_cut_roles(include_groundside=False))
        from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
        assert ROLE_GROUNDSIDE_PAVEMENT not in bridges.pavement_cut_roles()
        assert ROLE_GROUNDSIDE_PAVEMENT in bridges.pavement_cut_roles(
            include_groundside=True)

    def test_a_pit_clear_of_pavement_cuts_nothing(self):
        """No pavement over the body ⇒ no cut attempted, and the emitter
        behaves exactly as it did before R13."""
        apron = Polygon([(200, 200), (300, 200), (300, 300), (200, 300)])
        layout = self._layout_with_apron(apron=apron)
        before = self._apron_area(layout)
        floors, _rims = self._emit(layout, [_interface()])
        assert floors >= 1
        assert self._apron_area(layout) == pytest.approx(before)


# ---------------------------------------------------------------------------
# ruling R4 — carved implies excluded from the Phase 2 y-bake
# ---------------------------------------------------------------------------

class TestPhaseTwoInterlock:
    def test_carved_basin_joins_the_exclusion_list(self):
        result = _classify(_open_pit_pair(depth_m=4.0))
        assert any(otf.is_carved_basin_interface(interface)
                   for interface in result.ground_interfaces)
        assert {resource for _root, resource in result.exclusions} == set(
            _open_pit_pair())

    def test_gate_off_excludes_nothing(self):
        geometry = _open_pit_pair(depth_m=4.0)
        result = otf.classify_object_terrain_features(
            [_placement(resource) for resource in geometry], geometry,
            pack_root="PACK", basin_trench_enabled=False,
        )
        assert result.exclusions == []

    def test_flat_structure_stays_bakeable(self):
        result = _classify(
            {"terminal.obj": _at_grade_building_geometry(height_m=12.0)})
        assert result.exclusions == []

    def test_carved_basin_leaves_the_building_pool(self):
        """``terrain_material_resources`` is the building-pool drop set —
        a carved pit must never also chain into a pad."""
        result = _classify(_open_pit_pair(depth_m=4.0))
        assert set(_open_pit_pair()) <= result.terrain_material_resources()
