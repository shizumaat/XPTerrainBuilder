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


class _SpikeDem:
    """A flat DEM with ONE raised disc around a chosen point.

    The point-versus-median question needs a DEM whose value at the
    placement ANCHOR differs from the median around the body OUTLINE.
    A spike centred on the anchor does exactly that with one number in
    each place: ``anchor_elevation_m`` at (and within ``radius_degrees``
    of) the anchor, ``elevation_m`` everywhere else — so ``R_est`` is
    the flat value and the old point datum is the spike.
    """

    nodata = -32768

    def __init__(
        self,
        elevation_m: float,
        anchor_elevation_m: float,
        *,
        radius_degrees: float = 0.00005,
        anchor_longitude: float = ANCHOR_LONGITUDE,
        anchor_latitude: float = ANCHOR_LATITUDE,
    ) -> None:
        self.elevation_m = elevation_m
        self.anchor_elevation_m = anchor_elevation_m
        self.radius_degrees = radius_degrees
        self._anchor_xy = (
            anchor_longitude - TILE_LONGITUDE,
            anchor_latitude - TILE_LATITUDE,
        )

    def alt(self, xy) -> float:
        offset_x = xy[0] - self._anchor_xy[0]
        offset_y = xy[1] - self._anchor_xy[1]
        if (offset_x * offset_x + offset_y * offset_y
                <= self.radius_degrees ** 2):
            return self.anchor_elevation_m
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
    solid_minimum_y_m: float | None = None,
    anchor_longitude: float = ANCHOR_LONGITUDE,
    anchor_latitude: float = ANCHOR_LATITUDE,
) -> otf.StructureGroundInterface:
    return otf.StructureGroundInterface(
        object_resources=list(resources),
        anchor_longitude_latitude=(anchor_longitude, anchor_latitude),
        frame_origin_longitude_latitude=(anchor_longitude, anchor_latitude),
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
        solid_minimum_y_m=solid_minimum_y_m,
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
        # The BASIN limb of the trench law (spec 2.1 item 3): a flat DEM
        # makes R_est == the anchor datum, so the only difference from
        # the old datum-keyed value is the seat-estimate margin.
        expected_floor = grade_law.basin_trench_floor_elevation_m(8.0, -3.81)
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

    def test_a_pit_under_an_apron_gets_no_anchor_seat_either(self):
        """SUPERSEDED ORDERING GUARD (owner ruling 2026-08-09).  This case
        used to assert that R13 cut BEFORE the anchor seat was judged, so
        that a seat still fired under an apron.  The basin class has no
        seat at all now — the floor covers the anchor — so what the cut
        must leave behind is a clean floor: pavement gone, floor born,
        and nothing standing in the middle of it."""
        layout = self._layout_with_apron()
        floors, _rims = self._emit(layout, [_interface(floor_y_m=-3.81)])
        assert floors >= 1
        assert not _basin_plates(layout, "anchor_seat")

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


# ---------------------------------------------------------------------------
# PHASE E — the basin experiment (owner ruling 2026-08-09, docs/RULINGS.md;
# spec docs/specs/basin-rim-flush-seating-spec.md sections 2.1 and 2.1e)
#
# Owner, verbatim: "Let's try cutting the trench, but don't modify the
# objects so I can see how it looks."  Three things follow and each has
# its section below: the pillar in the middle of the pit goes, the floor
# and rim stop keying on one arbitrary point sample, and no basin member
# may be y-baked (the pack stays byte-authored through a tile pass).
# ---------------------------------------------------------------------------

def _emit_basin(layout, interfaces, dem):
    setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
            _Classification(ground_interfaces=interfaces))
    return assembly.build_tunnel_layout_shapes(
        layout, dem, TILE_LATITUDE, TILE_LONGITUDE)


class TestBasinHasNoAnchorSeat:
    """Spec section 2.1 item 1.  The 3x3 m ``object_basin_anchor_seat``
    plate stood at the pre-solve DEM datum — ``body_depth + 0.5`` m proud
    of the trench floor (4.31 m at the OTHH Drainage bowls, 13.50 m at
    Dewatering_01) — over 7.4-9.0 m2 of the object's own interior floor
    faces, with a 17.64 m2 keep-out hole punched through the floor pan
    beside it.  That IS the "terrain poking up in the middle" the owner
    reported."""

    def test_no_seat_plate_is_born(self):
        layout = _FakeLayout()
        _emit_basin(layout, [_interface(floor_y_m=-3.81)], _FakeDem(8.0))
        assert not _basin_plates(layout, "anchor_seat")
        assert not [shape for shape in layout.shapes
                    if "anchor_seat" in str(shape.ref)]

    def test_the_floor_covers_the_anchor(self):
        """No seat means the floor must reach the anchor point — the
        draped object then seats ON the floor, which is the whole
        experiment.  A keep-out hole here would put the object back on
        raw terrain in a 3 m hole."""
        from shapely.geometry import Point
        layout = _FakeLayout()
        _emit_basin(layout, [_interface(floor_y_m=-3.81)], _FakeDem(8.0))
        anchor_point = Point(
            *layout.ll_to_m(ANCHOR_LATITUDE, ANCHOR_LONGITUDE))
        covering = [plate for plate in _basin_plates(layout, "trench")
                    if plate.polygon.covers(anchor_point)]
        assert covering, "the trench floor does not reach the anchor"

    def test_no_interior_ring_is_left_in_the_floor(self):
        """The keep-out emitted as an UNVALUED ``shape_interior_ring``
        way.  With no seat there is no keep-out, so every floor part is a
        simple polygon with no hole."""
        layout = _FakeLayout()
        _emit_basin(layout, [_interface(floor_y_m=-3.81)], _FakeDem(8.0))
        plates = _basin_plates(layout, "trench")
        assert plates
        for plate in plates:
            assert list(plate.polygon.interiors) == []

    def test_the_seat_is_gone_even_when_the_anchor_is_free(self):
        """The old seat fired only where no earlier shape owned the
        anchor.  The default fixture is exactly that case — an empty
        layout — so this is the arm that used to emit."""
        layout = _FakeLayout()
        floors, _rims = _emit_basin(
            layout, [_interface()], _FakeDem(8.0))
        assert floors >= 1
        assert not _basin_plates(layout, "anchor_seat")


class TestBasinFloorLaw:
    """Spec section 2.1 items 2 and 3 — ``R_est``, the TRUE deepest solid
    and the seat-estimate margin, all in ONE law function that the
    emitter and any validator import (ruling R1)."""

    def test_the_law_is_r_est_plus_true_min_less_both_offsets(self):
        assert grade_law.basin_trench_floor_elevation_m(
            12.0, -4.201) == pytest.approx(
                12.0 - 4.201
                - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
                - config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)

    def test_the_margin_constant_moves_the_law(self, monkeypatch):
        monkeypatch.setattr(config, "TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M", 2.5)
        assert grade_law.basin_trench_floor_elevation_m(
            12.0, -4.0) == pytest.approx(12.0 - 4.0 - 0.5 - 2.5)

    def test_the_margin_default_is_the_specced_one(self):
        assert config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M == pytest.approx(1.0)

    def test_the_tunnel_law_is_untouched_by_the_margin(self, monkeypatch):
        """SCOPE GUARD.  The new constant may never reach the tunnel
        floor law — the EGLL class must not move."""
        monkeypatch.setattr(config, "TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M", 9.0)
        assert grade_law.tunnel_trench_floor_elevation_m(
            12.0, -4.0) == pytest.approx(
                12.0 - 4.0 - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M)

    def test_the_emitted_floor_uses_the_outline_median_not_the_anchor(self):
        """THE POINT-DATUM DEFECT, in a fixture: the DEM reads 30 m at the
        anchor (the pack's arbitrary placement point) and 8 m everywhere
        around the body outline.  Keying on the point would put the floor
        22 m too high."""
        layout = _FakeLayout()
        dem = _SpikeDem(8.0, 30.0)
        _emit_basin(layout, [_interface(floor_y_m=-3.81)], dem)
        expected = grade_law.basin_trench_floor_elevation_m(8.0, -3.81)
        plates = _basin_plates(layout, "trench")
        assert plates
        for plate in plates:
            assert all(altitude == pytest.approx(expected)
                       for altitude in plate.node_altitudes)

    def test_the_law_rim_uses_the_outline_median_too(self):
        """The rim BAND samples the DEM per part (unchanged), but the law
        value the facility reports and falls back to is ``R_est``."""
        layout = _FakeLayout()
        _emit_basin(layout, [_interface(floor_y_m=-3.81)],
                    _SpikeDem(8.0, 30.0))
        record = getattr(
            layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE)[0]
        assert record["rim_estimate_m"] == pytest.approx(8.0)
        assert record["rim_law_m"] == pytest.approx(8.0)
        assert record["anchor_datum_m"] == pytest.approx(30.0)

    def test_the_floor_keys_on_the_true_deepest_solid(self):
        """OTHH Drainage_06: the clustered interface level is -3.859 m and
        the deepest solid is -4.201 m.  Keying on the level spent 0.342 m
        of the promised 0.5 m clearance before the floor was even cut."""
        layout = _FakeLayout()
        _emit_basin(
            layout,
            [_interface(floor_y_m=-3.859, solid_minimum_y_m=-4.201)],
            _FakeDem(8.0))
        expected = grade_law.basin_trench_floor_elevation_m(8.0, -4.201)
        plates = _basin_plates(layout, "trench")
        assert plates
        for plate in plates:
            # ``abs``, not ``rel``: emitted plate altitudes are quantised
            # to the millimetre, and the law value here is 2.299 m.
            assert all(altitude == pytest.approx(expected, abs=1e-3)
                       for altitude in plate.node_altitudes)

    def test_the_adapter_carries_the_true_minimum(self):
        record = assembly.basin_trench_structures(_Classification(
            ground_interfaces=[
                _interface(floor_y_m=-3.859, solid_minimum_y_m=-4.201)]))[0]
        assert record.solid_minimum_y_m == pytest.approx(-4.201)
        # ``body_depth_m`` still carries the interface LEVEL: the depth
        # bound (amendment A7) is a different quantity and stays.
        assert record.body_depth_m == pytest.approx(3.859)

    def test_a_record_without_a_true_minimum_falls_back(self):
        """Hand-built records and old sidecars carry no true minimum;
        they must behave exactly as they did before this spec."""
        record = assembly.basin_trench_structures(_Classification(
            ground_interfaces=[_interface(floor_y_m=-3.81)]))[0]
        assert record.solid_minimum_y_m == pytest.approx(-3.81)

    def test_the_classifier_measures_the_true_minimum(self):
        """END TO END through the real classifier: the interface record
        must actually carry the frame's deepest solid, or the law above
        keys on a fallback forever."""
        geometry = _open_pit_pair(depth_m=4.0)
        interfaces = _classify(geometry).ground_interfaces
        carved = [interface for interface in interfaces
                  if otf.is_carved_basin_interface(interface)]
        assert carved
        assert carved[0].solid_minimum_y_m == pytest.approx(-4.0)

    def test_the_floor_still_clears_the_modelled_bottom(self):
        """The acceptance property the margin exists to protect."""
        layout = _FakeLayout()
        _emit_basin(
            layout,
            [_interface(floor_y_m=-3.859, solid_minimum_y_m=-4.201)],
            _FakeDem(8.0))
        modelled_bottom_world = 8.0 - 4.201
        for plate in _basin_plates(layout, "trench"):
            assert all(altitude
                       <= modelled_bottom_world
                       - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M + 1e-9
                       for altitude in plate.node_altitudes)


class TestBasinInstrumentation:
    """Spec section 2.1 item 4 and section 2.1e item E2.  The build log
    used to print the LAW rim value while the plates carried per-part DEM
    samples — the number in the log was not the number in the patch."""

    def test_a_record_lands_for_every_basin_facility(self):
        layout = _FakeLayout()
        _emit_basin(layout, [_interface(floor_y_m=-3.81)], _FakeDem(8.0))
        records = getattr(
            layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE, None)
        assert records and len(records) == 1
        record = records[0]
        assert record["resources"] == ["Buildings/Drainage/basin.obj"]
        assert record["anchor_seat_emitted"] is False
        assert record["rim_estimate_m"] == pytest.approx(8.0)
        assert record["floor_m"] == pytest.approx(
            grade_law.basin_trench_floor_elevation_m(8.0, -3.81))
        # The draped object seats on the terrain at its anchor, and with
        # the seat gone that terrain IS the floor pan.
        assert record["predicted_drape_elevation_m"] == pytest.approx(
            record["floor_m"])
        assert record["predicted_rim_elevation_m"] == pytest.approx(8.0)
        assert record["shell_count"] == 1
        assert record["floor_plates"] >= 1

    def test_the_record_reports_the_emitted_rim_range(self):
        """THE GAP RECON NAMED, reproduced: the band parts take their OWN
        DEM samples and the law value is only their nodata fallback, so a
        single reported number cannot be both.  Here an off-centre rise
        lifts the eastern band parts to 12 m while the law value (the
        outline median) stays 8 m — measured at OTHH Dewatering_01 as a
        0.71-2.96 m band behind a single 0.80 m number."""
        layout = _FakeLayout()
        dem = _SpikeDem(
            8.0, 12.0, radius_degrees=0.0002,
            anchor_longitude=ANCHOR_LONGITUDE + 0.00025)
        _emit_basin(layout, [_interface(floor_y_m=-3.81)], dem)
        record = getattr(
            layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE)[0]
        emitted = [
            altitude
            for plate in _basin_plates(layout, "rim")
            for altitude in plate.node_altitudes]
        assert emitted
        assert min(emitted) < max(emitted), (
            "the fixture no longer produces a rim RANGE — the test would "
            "pass on a single value and prove nothing")
        assert record["emitted_rim_min_m"] == pytest.approx(min(emitted))
        assert record["emitted_rim_max_m"] == pytest.approx(max(emitted))
        assert record["emitted_rim_part_count"] == len(
            _basin_plates(layout, "rim"))
        # ...and this is exactly the disagreement the old log line hid.
        assert record["rim_law_m"] == pytest.approx(8.0)
        assert record["emitted_rim_max_m"] == pytest.approx(12.0)

    def test_no_record_for_a_tunnel_facility(self):
        layout = _FakeLayout()
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(tunnels=[_tunnel_record()]))
        floors, _rims = assembly.build_tunnel_layout_shapes(
            layout, _FakeDem(8.0), TILE_LATITUDE, TILE_LONGITUDE)
        assert floors >= 1, "the tunnel arm emitted nothing — vacuous test"
        assert not getattr(
            layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE, None)

    def test_the_records_reach_the_patch_sidecar(self, tmp_path):
        """END TO END through the real writer.  The integration report
        reads these off the patch's own ``.axes.json`` — the established
        one-JSON-beside-the-patch convention, and the only file
        ``test_auto_patch_freshness`` allows in a patch dir."""
        import json
        from auto_patch.layout import PavementLayout

        emitting_layout = _FakeLayout()
        _emit_basin(
            emitting_layout, [_interface(floor_y_m=-3.81)], _FakeDem(8.0))
        records = getattr(
            emitting_layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE)
        assert records

        patch = tmp_path / "TEST_auto.patch.osm"
        patch_layout = PavementLayout(icao="TEST", anchor=ANCHOR)
        patch_layout.basin_facility_records = records
        patch_layout.to_osm(str(patch))
        sidecar = json.loads(
            (tmp_path / "TEST_auto.patch.osm.axes.json").read_text())
        assert sidecar["basin_facilities"] == records

    def test_a_patch_with_no_basins_still_declares_the_key(self, tmp_path):
        """``[]`` means "no basins here"; a MISSING key means "this patch
        predates the experiment".  A reader must be able to tell them
        apart, so the key is written unconditionally."""
        import json
        from auto_patch.layout import PavementLayout

        patch = tmp_path / "NONE_auto.patch.osm"
        PavementLayout(icao="NONE", anchor=ANCHOR).to_osm(str(patch))
        sidecar = json.loads(
            (tmp_path / "NONE_auto.patch.osm.axes.json").read_text())
        assert sidecar["basin_facilities"] == []


def _tunnel_record(*, body_depth_m: float = 5.0):
    """A feature-A TUNNEL facility record, anchored like the basin
    fixtures so the two arms differ in exactly one thing: the terrain
    feature tag."""
    from auto_patch.object_terrain_features import TunnelStructure

    footprint = Polygon([(-50, -15), (50, -15), (50, 15), (-50, 15)])
    return TunnelStructure(
        object_resources=["Airport/Tunnel/1.obj"],
        anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        frame_origin_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        heading_degrees=0.0,
        placement_kind="OBJECT",
        above_ground_offset_m=0.0,
        roof_footprint=footprint.buffer(-2.0),
        deck_footprint=footprint,
        mouth_polygons=[],
        mouth_depth_samples=[],
        body_depth_m=body_depth_m,
    )


class TestTunnelScopeBoundary:
    """THE REGRESSION PIN (spec section 4, last bullet).  Everything above
    is scoped to ``terrain_feature == TERRAIN_FEATURE_BASIN``.  No OTHH
    fixture exercises tunnels and the EGLL class must not move, so the
    tunnel arm is pinned to the DATUM-keyed law, seat and all."""

    def _emit_tunnel(self, layout, dem, **kwargs):
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(tunnels=[_tunnel_record(**kwargs)]))
        return assembly.build_tunnel_layout_shapes(
            layout, dem, TILE_LATITUDE, TILE_LONGITUDE)

    def _tunnel_plates(self, layout, suffix):
        return [shape for shape in layout.shapes
                if shape.role == ROLE_TUNNEL_TRENCH
                and str(shape.ref) == f"object_tunnel_{suffix}"]

    def test_a_tunnel_still_gets_its_anchor_seat(self):
        layout = _FakeLayout()
        self._emit_tunnel(layout, _FakeDem(8.0))
        assert self._tunnel_plates(layout, "anchor_seat"), (
            "the basin change removed the TUNNEL seat — scope breach")

    def test_a_tunnel_floor_keys_on_the_point_datum(self):
        """The spike DEM reads 30 m at the anchor and 8 m around the body.
        A tunnel must take the ANCHOR value — if it took the outline
        median the basin law leaked into this class."""
        layout = _FakeLayout()
        self._emit_tunnel(layout, _SpikeDem(8.0, 30.0), body_depth_m=5.0)
        expected = grade_law.tunnel_trench_floor_elevation_m(30.0, -5.0)
        plates = self._tunnel_plates(layout, "trench")
        assert plates
        for plate in plates:
            assert all(altitude == pytest.approx(expected)
                       for altitude in plate.node_altitudes)

    def test_a_tunnel_floor_takes_no_basin_margin(self):
        layout = _FakeLayout()
        self._emit_tunnel(layout, _FakeDem(8.0), body_depth_m=5.0)
        expected = grade_law.tunnel_trench_floor_elevation_m(8.0, -5.0)
        for plate in self._tunnel_plates(layout, "trench"):
            assert all(altitude == pytest.approx(expected)
                       for altitude in plate.node_altitudes)
        # ...and the basin law would have been a metre deeper.
        assert grade_law.basin_trench_floor_elevation_m(
            8.0, -5.0) == pytest.approx(expected - 1.0)

    def test_a_tunnel_seat_still_punches_its_keep_out(self):
        """The seat's keep-out is what the basin arm drops with it; the
        tunnel arm keeps it, so the floor must NOT cover the anchor."""
        from shapely.geometry import Point
        layout = _FakeLayout()
        self._emit_tunnel(layout, _FakeDem(8.0))
        anchor_point = Point(
            *layout.ll_to_m(ANCHOR_LATITUDE, ANCHOR_LONGITUDE))
        assert not [plate for plate in self._tunnel_plates(layout, "trench")
                    if plate.polygon.covers(anchor_point)]


# ---------------------------------------------------------------------------
# 2.1e E1 — no basin member is baked, by construction
# ---------------------------------------------------------------------------

_PIT_RESOURCES = sorted(_open_pit_pair())


class TestBasinExclusionCoverage:
    """Spec section 2.1e item E1.  ``exclusion_set_for_dsf`` is the
    post-mesh limb of ruling R4 and it never received the basin gate, so
    it defaulted to FALSE: stage 2b (open-pit components) did not run at
    all and stage 3's basin limb never fired.  The build CARVED basin
    terrain and then y-baked the objects onto the terrain it had just
    cut — the stacked correction R4 exists to forbid.  The 2026-08-08
    pad-request corpus is the fingerprint (Dewatering pool shells raising
    cluster requests at −13.6 m)."""

    @pytest.fixture(autouse=True)
    def _sandbox(self, tmp_path, monkeypatch):
        # The exclusion sidecar cache writes under the data root; pin it
        # inside the test sandbox and switch it off so each arm computes.
        monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "o4root"))
        monkeypatch.setenv("O4_OBJECT_EXCLUSION_CACHE", "0")

    def _pack(self, tmp_path, monkeypatch, *, sibling: bool = False):
        """A synthetic pack on disk: the two pit shells the OTHH pack
        ships, optionally with a co-anchored sibling shell (the Dewatering
        pool case, where the pool's other members share the anchor but
        contribute nothing to the interface record)."""
        from auto_patch import dsf_reader

        pack_root = tmp_path / "OTHH-TEST Aeroscape"
        geometry = dict(_open_pit_pair())
        if sibling:
            geometry["Buildings/Drainage/pool_shell.obj"] = (
                _at_grade_building_geometry(half_span_m=8.0, height_m=2.0))
        definition_lines = []
        placement_lines = []
        for index, resource in enumerate(sorted(geometry)):
            path = pack_root / resource
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {resource}\n")
            (pack_root / (resource + ".anchor_bak")).write_text(
                f"# {resource}\n")
            definition_lines.append(f"OBJECT_DEF {resource}")
            placement_lines.append(
                f"OBJECT {index} {ANCHOR_LONGITUDE} {ANCHOR_LATITUDE} 0.0")
        dsf_path = pack_root / "overlay.dsf"
        dsf_path.write_bytes(b"")
        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text",
            lambda _path: definition_lines + placement_lines)
        monkeypatch.setattr(
            assembly, "_load_object_geometry_by_resource",
            lambda _placements, _pack_root, _xplane_root: geometry)
        return dsf_path, pack_root, sorted(geometry)

    def test_every_basin_member_is_excluded(self, tmp_path, monkeypatch):
        dsf_path, pack_root, resources = self._pack(tmp_path, monkeypatch)
        excluded = assembly.exclusion_set_for_dsf(
            str(dsf_path), None, pack_root=str(pack_root))
        assert {resource for _root, resource in excluded} >= set(
            _PIT_RESOURCES)
        assert all(root == str(pack_root) for root, _resource in excluded)
        assert set(resources) <= {
            resource for _root, resource in excluded}

    def test_co_anchored_pool_siblings_are_excluded_too(
        self, tmp_path, monkeypatch
    ):
        """The measured gap: a pool member that contributes nothing to the
        interface record still shares the anchor, and a bake there moves
        geometry inside the cut."""
        dsf_path, pack_root, resources = self._pack(
            tmp_path, monkeypatch, sibling=True)
        excluded = {
            resource for _root, resource
            in assembly.exclusion_set_for_dsf(
                str(dsf_path), None, pack_root=str(pack_root))}
        assert set(resources) <= excluded
        assert "Buildings/Drainage/pool_shell.obj" in excluded

    def test_the_basin_gate_off_excludes_nothing(
        self, tmp_path, monkeypatch
    ):
        """PROOF THE GATE IS THE LEVER — with the basin adapter off no
        basin terrain is carved, so nothing may be withheld from the
        bake either."""
        monkeypatch.setattr(config, "OBJECT_BASIN_TRENCH", False)
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        excluded = assembly.exclusion_set_for_dsf(
            str(dsf_path), None, pack_root=str(pack_root))
        assert {resource for _root, resource in excluded} & set(
            _PIT_RESOURCES) == set()

    def test_every_gate_off_reads_nothing(self, tmp_path, monkeypatch):
        from auto_patch import dsf_reader

        for name in ("OBJECT_BRIDGE_TERRAIN", "OBJECT_TUNNEL_TERRAIN",
                     "OBJECT_BASIN_TRENCH"):
            monkeypatch.setattr(config, name, False)
        dsf_path = tmp_path / "present.dsf"
        dsf_path.write_bytes(b"")

        def _explode(_path):
            raise AssertionError("every gate off must not read the DSF")

        monkeypatch.setattr(dsf_reader, "_load_dsf_text", _explode)
        assert assembly.exclusion_set_for_dsf(str(dsf_path), None) == set()

    def test_the_pack_stays_byte_authored_through_a_rebake(
        self, tmp_path, monkeypatch
    ):
        """THE E1 ACCEPTANCE PROPERTY: run the Phase 2 rebake with the
        computed exclusion set and every member's LIVE ``.obj`` must still
        equal its ``.anchor_bak`` byte for byte — the GENERIC y-bake never
        touches a basin member.

        Still the law after section 2.2's activation, and still what this
        arm measures: no ``basin_rim_flush_facilities`` are handed in, so
        the dedicated seat does not run.  With them (see
        ``TestBasinRimFlushSeat``) an anchor-INSIDE facility is seated by
        that law instead — never by the arithmetic this test pins."""
        from auto_patch import post_mesh

        dsf_path, pack_root, resources = self._pack(
            tmp_path, monkeypatch, sibling=True)
        excluded = assembly.exclusion_set_for_dsf(
            str(dsf_path), None, pack_root=str(pack_root))
        assert excluded, "nothing excluded — the test would be vacuous"

        result = post_mesh.discover_and_rebake_airport(
            str(dsf_path),
            str(tmp_path / "absent_mesh.mesh"),
            str(pack_root),
            None,
            excluded_resources=excluded,
        )
        assert result["objects_written"] == []
        assert result["structures_baked"] == 0
        r4_skipped = {
            resource for resource, reason in result["skipped"]
            if "ruling R4" in reason}
        assert set(resources) <= r4_skipped
        for resource in resources:
            live = (pack_root / resource).read_bytes()
            authored = (pack_root / (resource + ".anchor_bak")).read_bytes()
            assert live == authored, f"{resource} was rewritten"

    def test_the_basin_gate_salts_the_rebake_run_fingerprint(
        self, monkeypatch
    ):
        """A recorded Phase 2 run must never short-circuit past a changed
        decision.  The basin gate now DECIDES exclusion membership, so it
        joins the digested set exactly like the three gates beside it —
        otherwise a run recorded with basins on would be replayed with
        them off and every basin member would silently bake."""
        from auto_patch import object_rebake

        monkeypatch.setenv("O4_OBJECT_BASIN_TRENCH", "1")
        digest_on = object_rebake._gate_digest(0.25)
        monkeypatch.setenv("O4_OBJECT_BASIN_TRENCH", "0")
        digest_off = object_rebake._gate_digest(0.25)
        assert digest_on != digest_off
        assert ("O4_OBJECT_BASIN_TRENCH"
                in object_rebake._GATE_ENVIRONMENT_NAMES)


# ---------------------------------------------------------------------------
# 2.2 — the post-mesh basin_rim_flush seat (ACTIVATED by the owner's
# 2026-08-09 in-sim verdict: anchor-inside facilities are "sunk below the
# bottom of their trench", anchor-outside ones "look just right")
# ---------------------------------------------------------------------------

# The synthetic built mesh: a flat rim plain with a square trench floor
# cut into it, centred on the anchor.  The floor zone is deliberately
# SMALLER than the body outline's R_mesh band (body half-span 30 m, band
# +1.6 m => samples at 31.6 m) so the band lands on rim terrain while the
# facility anchor lands on the floor — the exact geometry the verdict
# describes.
MESH_FLOOR_HALF_SPAN_M = 20.0
MESH_EXTENT_M = 100.0
MESH_STEP_M = 5.0


def _write_trench_mesh(
    mesh_path, *, floor_elevation_m: float, rim_elevation_m: float
) -> None:
    from auto_patch import obj8_reader as _obj8

    steps = int(2 * MESH_EXTENT_M / MESH_STEP_M) + 1
    coordinates = [
        -MESH_EXTENT_M + index * MESH_STEP_M for index in range(steps)
    ]
    vertices: list[tuple[float, float, float]] = []
    for east in coordinates:
        for south in coordinates:
            latitude, longitude = _obj8.local_offset_to_lonlat(
                ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0, east, south)
            inside = (abs(east) <= MESH_FLOOR_HALF_SPAN_M
                      and abs(south) <= MESH_FLOOR_HALF_SPAN_M)
            vertices.append((
                longitude,
                latitude,
                floor_elevation_m if inside else rim_elevation_m,
            ))
    triangles: list[tuple[int, int, int]] = []
    for i in range(steps - 1):
        for j in range(steps - 1):
            a = i * steps + j
            b = (i + 1) * steps + j
            c = (i + 1) * steps + j + 1
            d = i * steps + j + 1
            triangles.append((a + 1, b + 1, c + 1))
            triangles.append((a + 1, c + 1, d + 1))
    lines = ["MeshVersionFormatted 2", "Dimension 3", "", "Vertices",
             str(len(vertices))]
    for longitude, latitude, elevation in vertices:
        lines.append(
            f"{longitude:.15f} {latitude:.15f} {elevation / 100000.0:.15f} 0")
    lines += ["", "Normals", "0", "", "Triangles", str(len(triangles))]
    for first, second, third in triangles:
        lines.append(f"{first} {second} {third} 0")
    mesh_path.write_text("\n".join(lines) + "\n")


def _obj8_text(geometry) -> str:
    """``ObjectGeometry`` back to OBJ8 source — the tests need REAL pack
    files because the post-mesh pass reads and rewrites them."""
    lines = ["A", "800", "OBJ", ""]
    index_count = 3 * len(geometry.solid_triangles)
    lines.append(f"POINT_COUNTS {len(geometry.vertices)} 0 0 {index_count}")
    for x, y, z in geometry.vertices:
        lines.append(f"VT {x:.6f} {y:.6f} {z:.6f} 0.0 1.0 0.0 0.0 0.0")
    flat = [index for triangle in geometry.solid_triangles
            for index in triangle]
    for start in range(0, len(flat), 10):
        lines.append(
            "IDX10 " + " ".join(str(index) for index in flat[start:start + 10])
        )
    lines.append(f"TRIS 0 {index_count}")
    return "\n".join(lines) + "\n"


def _vertex_y_values(path) -> list[float]:
    return [
        float(line.split()[2])
        for line in path.read_text().splitlines()
        if line.split() and line.split()[0] == "VT"
    ]


class TestBasinRimFlushSeat:
    """Spec section 2.2 items 5-8.  A draped object seats on the terrain
    at its anchor; with the section-2.1 anchor pillar gone, that terrain
    is the trench floor, so the six anchor-inside OTHH facilities sank by
    the cut depth.  The dedicated law seats each facility's ``y = 0``
    plane — the authored rim plane — on the first terrain outside our own
    plates instead."""

    FLOOR_ELEVATION_M = 10.0
    RIM_ELEVATION_M = 15.0

    @pytest.fixture(autouse=True)
    def _sandbox(self, tmp_path, monkeypatch):
        # Every sidecar cache under the test's own root, and off: each
        # arm must compute, never inherit another arm's answer.
        monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "o4root"))
        monkeypatch.setenv("O4_OBJECT_EXCLUSION_CACHE", "0")
        monkeypatch.setenv("O4_OBJECT_PARTITION_CACHE", "0")
        monkeypatch.setenv("O4_REANCHOR_SHORT_CIRCUIT", "0")

    # -- fixtures ---------------------------------------------------------

    def _pack(self, tmp_path, monkeypatch, *, extra_objects=None):
        """A synthetic pack on disk: the two co-anchored pit shells, plus
        any extra objects the arm needs.  Real OBJ8 files (the pass reads
        and rewrites them) and a monkeypatched DSF text."""
        from auto_patch import dsf_reader

        pack_root = tmp_path / "OTHH-TEST Aeroscape"
        geometry = dict(_open_pit_pair())
        geometry.update(extra_objects or {})
        placements = {
            resource: (ANCHOR_LONGITUDE, ANCHOR_LATITUDE)
            for resource in geometry
        }
        for resource, override in (extra_objects or {}).items():
            del override
        definition_lines = []
        placement_lines = []
        for index, resource in enumerate(sorted(geometry)):
            path = pack_root / resource
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_obj8_text(geometry[resource]))
            longitude, latitude = placements[resource]
            definition_lines.append(f"OBJECT_DEF {resource}")
            placement_lines.append(
                f"OBJECT {index} {longitude} {latitude} 0.0")
        dsf_path = pack_root / "overlay.dsf"
        dsf_path.write_bytes(b"")
        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text",
            lambda _path: definition_lines + placement_lines)
        return dsf_path, pack_root, sorted(geometry)

    def _mesh(self, tmp_path, *, rim_elevation_m=None):
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_trench_mesh(
            mesh_path,
            floor_elevation_m=self.FLOOR_ELEVATION_M,
            rim_elevation_m=(
                self.RIM_ELEVATION_M if rim_elevation_m is None
                else rim_elevation_m),
        )
        return mesh_path

    def _facility(self, *, anchor_inside_body=True, half_span_m=30.0,
                  solid_minimum_y_m=-4.0, resources=None):
        """A hand-built facility record with the ring the classifier
        would produce for the synthetic pit pair."""
        ring = tuple(
            (ANCHOR_LONGITUDE + longitude_offset,
             ANCHOR_LATITUDE + latitude_offset)
            for longitude_offset, latitude_offset in _square_ring(half_span_m)
        )
        return assembly.BasinRimFlushFacility(
            object_resources=tuple(
                sorted(resources or _open_pit_pair())),
            anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            body_rings_longitude_latitude=(ring,),
            solid_minimum_y_m=solid_minimum_y_m,
            anchor_inside_body=anchor_inside_body,
        )

    def _rebake(self, dsf_path, mesh_path, pack_root, facilities, **kwargs):
        from auto_patch import post_mesh

        return post_mesh.discover_and_rebake_airport(
            str(dsf_path),
            str(mesh_path),
            str(pack_root),
            None,
            excluded_resources={
                (str(pack_root), resource)
                for facility in facilities
                for resource in facility.object_resources
            },
            basin_rim_flush_facilities=facilities,
            **kwargs,
        )

    # -- item 5: the seat -------------------------------------------------

    def test_the_delta_seats_y_zero_at_r_mesh(self, tmp_path, monkeypatch):
        """THE LAW: ``delta = R_mesh - mesh_at_anchor``, so the authored
        ``y = 0`` rim plane lands exactly on the first terrain outside
        our plates."""
        dsf_path, pack_root, resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])

        record = result["basin_rim_flush"][0]
        assert record["decision_kind"] == "basin_rim_flush"
        assert record["r_mesh_m"] == pytest.approx(self.RIM_ELEVATION_M)
        assert record["mesh_at_anchor_m"] == pytest.approx(
            self.FLOOR_ELEVATION_M)
        expected_delta = self.RIM_ELEVATION_M - self.FLOOR_ELEVATION_M
        assert record["delta_m"] == pytest.approx(expected_delta)
        assert record["baked"] is True
        assert sorted(result["objects_written"]) == sorted(
            facility.object_resources)

        for resource in facility.object_resources:
            live = pack_root / resource
            authored = pack_root / (resource + ".anchor_bak")
            live_y = _vertex_y_values(live)
            authored_y = _vertex_y_values(authored)
            assert live_y != authored_y
            for baked, original in zip(live_y, authored_y):
                # y = 0 renders at anchor_ground + delta = R_mesh.
                assert baked == pytest.approx(
                    original + expected_delta, abs=1e-4)

    def test_the_whole_facility_moves_rigidly(self, tmp_path, monkeypatch):
        """One seat target for the whole facility: every member shell's
        rim plane lands on the SAME R_mesh, and no shell is bent."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        self._rebake(dsf_path, mesh_path, pack_root, [facility])

        deltas = set()
        for resource in facility.object_resources:
            live_y = _vertex_y_values(pack_root / resource)
            authored_y = _vertex_y_values(
                pack_root / (resource + ".anchor_bak"))
            per_vertex = {round(baked - original, 6)
                          for baked, original in zip(live_y, authored_y)}
            # Rigid within the shell...
            assert len(per_vertex) == 1, resource
            deltas |= per_vertex
        # ...and one delta family across the facility.
        assert len(deltas) == 1

    def test_a_non_member_never_takes_the_basin_law(
        self, tmp_path, monkeypatch
    ):
        """Pool siblings whose anchors lie outside the cut are NOT
        members (spec section 2.2 item 5) — they keep the generic law,
        which is recorded by the ABSENCE of a decision kind."""
        import json

        sibling = "Buildings/Drainage/pool_shell.obj"
        dsf_path, pack_root, _resources = self._pack(
            tmp_path, monkeypatch,
            extra_objects={
                sibling: _at_grade_building_geometry(
                    half_span_m=40.0, height_m=12.0)},
        )
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])

        assert sibling not in result["basin_rim_flush"][0].get(
            "objects_written", [])
        provenance = json.loads(
            (pack_root / ".o4_reanchor_provenance.json").read_text())
        for resource in facility.object_resources:
            assert provenance["objects"][resource]["decision_kind"] == (
                "basin_rim_flush")
        sibling_entry = provenance["objects"].get(sibling)
        if sibling_entry is not None:
            assert "decision_kind" not in sibling_entry

    # -- item 6: scope ----------------------------------------------------

    def test_an_anchor_outside_facility_is_not_baked(
        self, tmp_path, monkeypatch
    ):
        """The class the owner measured as "just right" in-sim.  A
        regression here is a defect, not an improvement."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility(anchor_inside_body=False)
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])

        record = result["basin_rim_flush"][0]
        assert record["baked"] is False
        assert "OUTSIDE its body" in record["decision"]
        assert "r_mesh_m" not in record
        assert result["objects_written"] == []
        for resource in facility.object_resources:
            # Untouched means UNTOUCHED: not even a backup was taken.
            assert not (pack_root / (resource + ".anchor_bak")).exists()

    # -- item 7: clearance ------------------------------------------------

    def test_the_clearance_finding_fires_and_names_r_mesh_minus_r_est(
        self, tmp_path, monkeypatch
    ):
        """A built rim BELOW ``R_est - margin`` means the section-2.1
        margin constant is too small for this airport: report it, never
        silently re-derive a seat."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        # 2 m of trench where the law needs y_true_min + DECK = 4.5 m.
        mesh_path = self._mesh(tmp_path, rim_elevation_m=12.0)
        facility = self._facility(solid_minimum_y_m=-4.0)
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])

        record = result["basin_rim_flush"][0]
        assert record["clearance_finding"] is True
        # R_est = floor + DECK + MARGIN - y_true_min = 10 + 0.5 + 1 + 4
        assert record["rim_estimate_m"] == pytest.approx(15.5)
        assert record["r_mesh_minus_r_est_m"] == pytest.approx(-3.5)

    def test_a_clearing_seat_raises_no_finding(self, tmp_path, monkeypatch):
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility(solid_minimum_y_m=-4.0)
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])
        record = result["basin_rim_flush"][0]
        assert record["clearance_finding"] is False
        assert record["clearance_m"] == pytest.approx(0.5)

    # -- the measure-only mode (reseat-threshold spec section 2.3) --------

    def test_measure_only_records_the_seat_and_writes_nothing(
        self, tmp_path, monkeypatch
    ):
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        result = self._rebake(
            dsf_path, mesh_path, pack_root, [facility], measure_only=True)

        record = result["basin_rim_flush"][0]
        assert record["measure_only"] is True
        assert record["baked"] is False
        assert record["r_mesh_m"] == pytest.approx(self.RIM_ELEVATION_M)
        assert record["delta_m"] == pytest.approx(
            self.RIM_ELEVATION_M - self.FLOOR_ELEVATION_M)
        assert result["objects_written"] == []
        for resource in facility.object_resources:
            backup = pack_root / (resource + ".anchor_bak")
            if backup.exists():
                assert (pack_root / resource).read_bytes() == (
                    backup.read_bytes())

    def test_measure_only_reverts_an_earlier_basin_bake(
        self, tmp_path, monkeypatch
    ):
        """Item 8: the reversion pass needs no change — a basin bake
        reverts like any other."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        self._rebake(dsf_path, mesh_path, pack_root, [facility])
        baked = {
            resource: (pack_root / resource).read_bytes()
            for resource in facility.object_resources
        }
        self._rebake(
            dsf_path, mesh_path, pack_root, [facility], measure_only=True)
        for resource in facility.object_resources:
            authored = (pack_root / (resource + ".anchor_bak")).read_bytes()
            assert (pack_root / resource).read_bytes() == authored
            assert baked[resource] != authored

    def test_a_dry_run_reports_the_seat_without_writing(
        self, tmp_path, monkeypatch
    ):
        """A dry run computes the same seat and writes NOTHING — the
        report must not claim a bake that never touched a file."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        result = self._rebake(
            dsf_path, mesh_path, pack_root, [facility], write_changes=False)
        record = result["basin_rim_flush"][0]
        assert record["dry_run"] is True
        assert record["baked"] is False
        assert record["delta_m"] == pytest.approx(
            self.RIM_ELEVATION_M - self.FLOOR_ELEVATION_M)
        for resource in facility.object_resources:
            assert not (pack_root / (resource + ".anchor_bak")).exists()

    # -- item 8: idempotence ---------------------------------------------

    def test_the_bake_is_byte_idempotent(self, tmp_path, monkeypatch):
        """Invariant I-15: the second run rewrites from ``.anchor_bak``,
        so it lands on the same bytes — never twice the delta."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        self._rebake(dsf_path, mesh_path, pack_root, [facility])
        first = {
            resource: (pack_root / resource).read_bytes()
            for resource in facility.object_resources
        }
        self._rebake(dsf_path, mesh_path, pack_root, [facility])
        for resource in facility.object_resources:
            assert (pack_root / resource).read_bytes() == first[resource]

    def test_the_basin_law_constants_salt_the_rebake_gate_digest(
        self, monkeypatch
    ):
        from auto_patch import object_rebake

        baseline = object_rebake._gate_digest(0.25)
        monkeypatch.setattr(
            config, "TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M",
            config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M + 1.0)
        assert object_rebake._gate_digest(0.25) != baseline
        monkeypatch.undo()
        monkeypatch.setattr(
            config, "TUNNEL_FLOOR_BELOW_OBJECT_DECK_M",
            config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M + 1.0)
        assert object_rebake._gate_digest(0.25) != baseline

    # -- the reseat threshold is a different law (regression pin) --------

    def test_the_reseat_threshold_does_not_gate_the_basin_class(
        self, tmp_path, monkeypatch
    ):
        """Basin units bake regardless of ``DSF_OBJECT_BAKE_MIN_DELTA_M``
        — their deltas are metres by construction, and the generic
        arithmetic that consults the threshold never runs for them."""
        monkeypatch.setattr(config, "DSF_OBJECT_BAKE_MIN_DELTA_M", 1000.0)
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])
        assert result["basin_rim_flush"][0]["baked"] is True
        assert sorted(result["objects_written"]) == sorted(
            facility.object_resources)

    def test_a_generic_unit_below_the_threshold_still_does_not_bake(
        self, tmp_path, monkeypatch
    ):
        """The other half of the pin: the threshold law is untouched for
        everything that is not a basin member."""
        sibling = "Buildings/Drainage/pool_shell.obj"
        dsf_path, pack_root, _resources = self._pack(
            tmp_path, monkeypatch,
            extra_objects={
                sibling: _at_grade_building_geometry(
                    half_span_m=40.0, height_m=12.0)},
        )
        mesh_path = self._mesh(tmp_path)
        facility = self._facility()
        monkeypatch.setattr(config, "DSF_OBJECT_BAKE_MIN_DELTA_M", 1000.0)
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])
        assert sibling not in result["objects_written"]
        counts: dict = {}
        for _pool, decision in result["decisions"]:
            for key, value in (decision.cluster_counts or {}).items():
                counts[key] = counts.get(key, 0) + value
        # The generic law measured the sibling and the threshold — not
        # the basin law — is what left it alone.
        assert counts.get("clusters_below_threshold", 0) >= 1
        # ...while the basin facility beside it baked regardless.
        assert result["basin_rim_flush"][0]["baked"] is True

    # -- the records come from the classifier, never a re-derivation -----

    def test_the_facilities_come_from_the_classifier_records(
        self, tmp_path, monkeypatch
    ):
        """Section 2.2's scope test and geometry are read off the SAME
        ``basin_trench_structures`` records section 2.1 cut terrain
        from."""
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        records = assembly.post_mesh_object_terrain_records(
            str(dsf_path), None, pack_root=str(pack_root))
        facilities = records.basin_rim_flush_facilities
        assert len(facilities) == 1
        facility = facilities[0]
        assert set(facility.object_resources) == set(_open_pit_pair())
        # Both shells are placed AT the anchor and the pit surrounds it.
        assert facility.anchor_inside_body is True
        assert facility.solid_minimum_y_m < 0.0
        assert facility.body_rings_longitude_latitude
        # And the members are still withheld from the GENERIC bake.
        assert {resource for _root, resource in records.exclusions} >= set(
            _open_pit_pair())

    def test_the_gate_off_yields_no_facility(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OBJECT_BASIN_TRENCH", False)
        dsf_path, pack_root, _resources = self._pack(tmp_path, monkeypatch)
        records = assembly.post_mesh_object_terrain_records(
            str(dsf_path), None, pack_root=str(pack_root))
        assert records.basin_rim_flush_facilities == []


def _square_ring(half_span_m: float):
    """A square ring in DEGREES around the anchor, ``half_span_m`` on
    each side — the body outline shape the synthetic pit produces."""
    from auto_patch import obj8_reader as _obj8

    corners = [
        (-half_span_m, -half_span_m), (half_span_m, -half_span_m),
        (half_span_m, half_span_m), (-half_span_m, half_span_m),
        (-half_span_m, -half_span_m),
    ]
    out = []
    for east, south in corners:
        latitude, longitude = _obj8.local_offset_to_lonlat(
            ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0, east, south)
        out.append((longitude - ANCHOR_LONGITUDE,
                    latitude - ANCHOR_LATITUDE))
    return out


# ---------------------------------------------------------------------------
# 2.2 prerequisite — the TRUE deepest solid must reach the record
# ---------------------------------------------------------------------------

class TestTrueDeepestSolidPlumbing:
    """The Drainage_06 class.  The section-2.1 adapter takes
    ``min(floor_y, interface.solid_minimum_y_m)``, but the OTHH sidecar
    kept reporting the clustered interface LEVEL (−3.859 m) where the
    deepest solid — modelled in the ``_001`` SIBLING shell — reaches
    −4.201 m.  The cause was not the arithmetic: the classification is
    PICKLED under ``_CLASSIFICATION_CACHE_VERSION``, the section-2.1
    landing added the field without bumping it, and an old pickle
    restores a frozen dataclass from a ``__dict__`` that has no such key
    — so every interface read back with the class default ``None`` and
    the adapter took its documented fallback."""

    def test_the_classification_cache_version_retires_pre_field_pickles(
        self,
    ):
        # 13 is the last version written WITHOUT
        # StructureGroundInterface.solid_minimum_y_m.  A pickle at or
        # below it must never be served again.
        assert assembly._CLASSIFICATION_CACHE_VERSION >= 14

    def test_a_deep_sibling_shell_sets_the_true_minimum(self):
        """The fixture is Drainage_06's shape: the deeper solid lives in
        the sibling resource, so a per-resource or per-level answer is
        the shallow one and only the pooled frame minimum is right."""
        geometry = {
            "Buildings/Drainage/basin_000.obj": _pit_shell(
                30.0, 6.0, -3.859, 0.0),
            "Buildings/Drainage/basin_001.obj": _pit_shell(
                28.5, 6.0, -4.201, 0.06),
        }
        classification = _classify(geometry)
        interfaces = [
            interface for interface in classification.ground_interfaces
            if otf.is_carved_basin_interface(interface)
        ]
        assert interfaces, "fixture no longer classifies as a carved basin"
        assert interfaces[0].solid_minimum_y_m == pytest.approx(-4.201)

        records = assembly.basin_trench_structures(classification)
        assert records
        assert records[0].solid_minimum_y_m == pytest.approx(-4.201)

        facilities = assembly.basin_rim_flush_facilities(classification)
        assert facilities
        # y_true_min is what item 7's clearance check consumes.
        assert facilities[0].solid_minimum_y_m == pytest.approx(-4.201)
