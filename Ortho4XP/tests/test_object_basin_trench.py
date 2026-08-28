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

import math
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

    def __init__(self, *, tunnels=(), ground_interfaces=(),
                 below_grade_regions=()) -> None:
        self.bridges: list = []
        self.tunnels = list(tunnels)
        self.ground_interfaces = list(ground_interfaces)
        self.exclusions: list = []
        self.refusals: list = []
        self.below_grade_regions = list(below_grade_regions)


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


def _open_pit_floor(rim_estimate_m, floor_key_depth_m):
    """The OPEN-PIT floor, THROUGH THE ONE LAW FUNCTION — never a
    hand-typed number (ruling R1; the census-wrapper defect in
    miniature).

    ``floor_key_depth_m`` is the facility's FLOOR KEY depth, positive
    down, i.e. what ``assembly.basin_facility_deck_reference_y`` returns
    negated.  Owner 2026-08-26 retired Amendment 3's zero-margin
    deck-face clause: an open pit now keys on its deepest genuine solid
    and takes BOTH tunnel margins, exactly like a bore, so this helper
    calls the law with its default.  The Amendment-3 arithmetic is kept
    behind ``O4_BASIN_OPEN_PIT_DECK_KEY`` and pinned in
    ``TestBasinRegionFloorKey``."""
    return grade_law.basin_trench_floor_elevation_m(
        rim_estimate_m, -abs(floor_key_depth_m))


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
        # makes R_est == the anchor datum.  AMENDMENT 3: this fixture is
        # an OPEN pit, so the floor is its deck face with no margins.
        expected_floor = _open_pit_floor(8.0, 3.81)
        for plate in _basin_plates(layout, "trench"):
            assert plate.node_altitudes
            assert all(altitude == pytest.approx(expected_floor)
                       for altitude in plate.node_altitudes)
        for plate in _basin_plates(layout, "rim"):
            assert plate.node_altitudes
            assert all(altitude == pytest.approx(8.0)
                       for altitude in plate.node_altitudes)

    def test_an_open_pit_floor_clears_the_modelled_basin_floor(self):
        """OWNER 2026-08-26 (docs/RULINGS.md "LEMD T4S basin"), replacing
        Amendment 3's by-class exemption: the mesh must clear the
        modelled bottom for an OPEN PIT too, so both margins apply.  ERR
        DEEP — extra depth is occluded by the modelled shell and free,
        shallowness is the visible poke-through (LEMD's deck-face floor
        sat 0.07 m ABOVE the family's deepest solid).  The property, not
        a number: the plate is never above the object's own floor."""
        layout = _FakeLayout()
        self._emit(layout, [_interface(floor_y_m=-3.81)], datum_m=8.0)
        object_floor_world = 8.0 - 3.81
        plates = _basin_plates(layout, "trench")
        assert plates
        for plate in plates:
            assert all(
                altitude == pytest.approx(_open_pit_floor(8.0, 3.81))
                and altitude <= object_floor_world
                - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M + 1e-9
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

    def test_a_cut_that_seats_no_floor_is_put_back(self, monkeypatch):
        """Pavement removed with no trench under it is a HOLE in the
        drivable surface — strictly worse than the buried pit.  Here a
        building pad owns the whole body, so the floor pan is eaten after
        the cut and the apron must be restored.

        RE-PINNED WITH ``BASIN_PAD_FLOOR_SEAT`` OFF (owner RULINGS
        2026-08-25f).  A pad covering the whole body is now precisely the
        case the pad-floor-seating law reverses: the pad seats at the
        floor and the cut emits THROUGH it (see
        ``TestBasinPadFloorSeating``).  The restore guard itself is
        unchanged and still law for every other way a floor can be eaten
        — this is the same re-pinning the §2.1 twin took when the pool
        scoping gate landed: the premise lives with the gate off."""
        from auto_patch.layout import ROLE_BUILDING
        monkeypatch.setattr(config, "BASIN_PAD_FLOOR_SEAT", False)
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
# LEMD ROUND 2 §B — the trench is SENIOR TO PAVEMENT at its rim
# (docs/specs/lemd-rim-and-stations-spec.md §B; owner RULINGS 2026-08-28
# item 2, extending the 2026-08-26 trench-seniority ruling from pads to
# pavement)
# ---------------------------------------------------------------------------


class TestTrenchSeniorToPavementAtItsRim:
    """MEASURED DEFECT (lane/lemd123, LEMD 1.0.263).  The 2026-08-26
    implementation scoped its authority-yield population to
    ``ROLE_BUILDING``, so apron -10228 — standing 0.70-0.89 m off the pan
    along one 98 m run — consumed the floor cutback AND the whole 0.6 m
    rim band there.  Rim coverage was 289 of 338 perimeter samples, and
    EVERY missing sample had pavement less than 0.9 m away: a 12.75 m
    unwalled drop at the owner's own coordinate 40.4910231,-3.5688464.

    Two legs, one law, and either alone leaves the band short: pavement
    reaching pan ∪ rim-band YIELDS its flattening authority there (the
    pan and the wall band are born THROUGH it), and it is CLIPPED BACK by
    the rim-band width so its edge abuts the rim's OUTER edge, never the
    pan."""

    #: comfortably larger than the 50 x 50 m default pit footprint
    APRON = Polygon([(-90, -90), (90, -90), (90, 90), (-90, 90)])

    def _layout_with_apron(self, apron=None):
        from auto_patch.layout import ROLE_APRON
        layout = _FakeLayout()
        layout.shapes.append(bridges.BuiltShape(
            polygon=self.APRON if apron is None else apron,
            role=ROLE_APRON, ref="apron", altitude=8.0))
        return layout

    def _emit(self, layout, interfaces=None, datum_m=8.0):
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(ground_interfaces=(
                    interfaces if interfaces is not None
                    else [_interface(floor_y_m=-3.81)])))
        return assembly.build_tunnel_layout_shapes(
            layout, _FakeDem(datum_m), TILE_LATITUDE, TILE_LONGITUDE)

    def _apron_polygons(self, layout):
        from auto_patch.layout import ROLE_APRON
        return [shape.polygon for shape in layout.shapes
                if shape.role == ROLE_APRON]

    def _band_reach(self):
        """The pan grown by the rim-band width — the ground the band
        occupies, which no pavement vertex may enter."""
        return _interface().below_grade_footprint.buffer(
            assembly._TUNNEL_RIM_BAND_WIDTH_M, join_style=2,
            mitre_limit=2.0)

    def test_the_pavement_is_clipped_back_to_the_rim_bands_outer_edge(self):
        layout = self._layout_with_apron()
        self._emit(layout)
        for polygon in self._apron_polygons(layout):
            overlap = polygon.intersection(self._band_reach()).area
            assert overlap < 1.0, (
                "pavement still stands over the pan or its rim band — "
                f"{overlap:.1f} m2")

    def test_no_pavement_VERTEX_lies_inside_the_pan_or_the_band(self):
        """The acceptance the spec states, asked of the geometry: the
        apron edge ABUTS the rim's outer edge."""
        from shapely.geometry import Point
        band = self._band_reach()
        layout = self._layout_with_apron()
        self._emit(layout)
        inside = [
            (x, y) for polygon in self._apron_polygons(layout)
            for (x, y) in polygon.exterior.coords
            if band.contains(Point(x, y))
            and band.exterior.distance(Point(x, y)) > 0.01]
        assert not inside, inside[:5]

    def test_the_rim_band_survives_on_the_WHOLE_perimeter(self):
        """The 289/338 coverage read, as a twin: sample the pan
        perimeter and require a rim plate over every sample.  Without the
        yield leg the apron's ``_TUNNEL_WALL_SETBACK_M`` collar eats the
        band exactly where the pavement abuts it."""
        from shapely.geometry import Point
        pan = _interface().below_grade_footprint
        rims = [plate.polygon for plate in _basin_plates(
            self._pan_layout(), "rim")]
        assert rims
        ring = pan.exterior
        misses = []
        for k in range(338):
            point = ring.interpolate(k / 338.0, normalized=True)
            probe = Point(point.x, point.y).buffer(
                0.5 * assembly._TUNNEL_RIM_BAND_WIDTH_M)
            if not any(rim.intersects(probe) for rim in rims):
                misses.append((round(point.x, 1), round(point.y, 1)))
        assert not misses, f"{len(misses)} of 338 perimeter samples " \
                           f"carry no rim band: {misses[:5]}"

    def _pan_layout(self):
        layout = self._layout_with_apron()
        self._emit(layout)
        return layout

    def test_the_pavement_joins_the_authority_yield_population(self):
        """The yield leg alone, isolated: with the CLIP disabled the band
        must still be born, because the pavement no longer owns that
        ground.  (Belt and braces — the spec asks for both legs.)"""
        layout = self._layout_with_apron()
        self._emit(layout)
        assert _basin_plates(layout, "rim"), "no rim band emitted at all"

    def test_flag_off_restores_the_body_only_cut_and_the_pad_only_yield(
            self, monkeypatch):
        """``O4_TRENCH_PAVEMENT_YIELD=0`` is byte-identical to the
        pre-ruling engine: the cut stops at the body and the apron keeps
        every square metre outside it."""
        monkeypatch.setattr(config, "TRENCH_PAVEMENT_YIELD", False)
        layout = self._layout_with_apron()
        before = sum(p.area for p in self._apron_polygons(layout))
        self._emit(layout)
        after = sum(p.area for p in self._apron_polygons(layout))
        pit_area = _interface().below_grade_footprint.area
        assert after == pytest.approx(before - pit_area, rel=1e-3)

    def test_the_clip_costs_exactly_the_rim_band_ring(self):
        """The ON arm's own arithmetic, against the OFF arm's: the extra
        pavement removed is the band ring and nothing more."""
        layout = self._layout_with_apron()
        before = sum(p.area for p in self._apron_polygons(layout))
        self._emit(layout)
        after = sum(p.area for p in self._apron_polygons(layout))
        expected = before - self._band_reach().area
        assert after == pytest.approx(expected, rel=0.02)

    def test_a_BORE_never_yields_its_pavement(self):
        """SCOPE.  §B rides R13's own predicate (``cuts_pavement``): a
        bore runs UNDER live pavement, and yielding there would let a
        floor pan be born beneath a drivable surface."""
        layout = self._layout_with_apron()
        before = sum(p.area for p in self._apron_polygons(layout))
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(ground_interfaces=[_interface(
                    interface_class=otf.INTERFACE_TRENCH_SPINE,
                    above_grade_area_fraction=0.0)]))
        assembly.build_tunnel_layout_shapes(
            layout, _FakeDem(8.0), TILE_LATITUDE, TILE_LONGITUDE)
        assert sum(p.area for p in self._apron_polygons(layout)) == \
            pytest.approx(before)


# ---------------------------------------------------------------------------
# LEMD ROUND 2 §C — the rim seats at the SOLVED NEIGHBOUR, DEM LAST
# (docs/specs/lemd-rim-and-stations-spec.md §C; owner RULINGS 2026-08-28
# item 3 + DEM-LAST 2026-08-25; the basin-rim-flush spec's own §1(2))
# ---------------------------------------------------------------------------


class TestRimSeatsAtTheSolvedNeighbour:
    """MEASURED DEFECT (lane/lemd123, LEMD 1.0.263).  Every rim band part
    seated at the RAW DEM at its own centroid, with ``R_est`` only the
    nodata fallback: all 13 LEMD parts read LOW against their nearest
    built neighbour — median -3.84 m, worst -5.41 m against building8's
    600.50 — with 4.14 m of rim self-spread between parts of ONE band,
    and a 67 m nodeless span between rim (595.2/597.8) and apron (599.98)
    that the owner saw as a down-slope into the pit.

    The rungs are: nearest ANCHORED built neighbour → ``R_est`` → raw DEM
    LAST."""

    #: An apron ringing the pit at a value the DEM does not carry, so
    #: neighbour and DEM can never be confused for one another.
    NEIGHBOUR_VALUE = 20.0

    def _layout(self, *, with_neighbour=True, role=None, value=None):
        from auto_patch.layout import ROLE_APRON
        layout = _FakeLayout()
        if with_neighbour:
            layout.shapes.append(bridges.BuiltShape(
                polygon=Polygon([(-90, -90), (90, -90), (90, 90),
                                 (-90, 90)]),
                role=role or ROLE_APRON, ref="neighbour",
                altitude=(self.NEIGHBOUR_VALUE if value is None
                          else value)))
        return layout

    def _emit(self, layout, dem=None):
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(ground_interfaces=[
                    _interface(floor_y_m=-3.81)]))
        return assembly.build_tunnel_layout_shapes(
            layout, dem if dem is not None else _FakeDem(8.0),
            TILE_LATITUDE, TILE_LONGITUDE)

    def _rim_values(self, layout):
        return sorted({
            round(float(altitude), 3)
            for plate in _basin_plates(layout, "rim")
            for altitude in plate.node_altitudes})

    # ── RUNG 1: the nearest anchored built neighbour ─────────────────

    def test_the_rim_takes_its_NEIGHBOURS_value_not_the_DEM(self):
        layout = self._layout()
        self._emit(layout)
        assert self._rim_values(layout) == [self.NEIGHBOUR_VALUE]

    def test_every_part_of_one_band_takes_the_SAME_value(self):
        """The 4.14 m self-spread was per-part DEM sampling.  One
        neighbour, one value — the spread collapses to the neighbour's
        own lawful variation."""
        layout = self._layout()
        self._emit(layout, dem=_SpikeDem(
            8.0, 12.0, radius_degrees=0.0002,
            anchor_longitude=ANCHOR_LONGITUDE + 0.00025))
        assert len(self._rim_values(layout)) == 1

    def test_a_pad_is_a_neighbour_too(self):
        """The LEMD case verbatim: ``building8`` CONTAINS the pit, so its
        seated value is what the rim must match."""
        from auto_patch.layout import ROLE_BUILDING
        layout = self._layout(role=ROLE_BUILDING, value=600.5)
        self._emit(layout)
        assert self._rim_values(layout) == [600.5]

    def test_a_pad_seated_at_the_BASIN_FLOOR_is_not_a_rim_neighbour(self):
        """A pad seated at the pit bottom carries the FLOOR, not the
        surrounding grade — adopting it would sink the rim into the
        trench it is supposed to wall."""
        from auto_patch.layout import ROLE_BUILDING
        layout = self._layout(role=ROLE_BUILDING, value=600.5)
        layout.shapes[0].basin_floor_seat_m = 1.0
        self._emit(layout)
        assert self._rim_values(layout) == [8.0], "R_est, not the seat"

    def test_our_OWN_trench_plates_are_never_the_neighbour(self):
        """A rim seating off the floor pan beside it would be the
        facility grading itself."""
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        floors = _basin_plates(layout, "trench")
        assert floors, "vacuous — no floor pan to be tempted by"
        floor_value = float(floors[0].node_altitudes[0])
        assert floor_value not in self._rim_values(layout)

    def test_a_neighbour_beyond_the_WINDOW_is_not_adopted(self):
        """"Adjacent" has an edge to it: a surface the band does not
        touch is not the surface the wall top must match, and beyond the
        window the law median R_est is the honest answer."""
        from auto_patch.layout import ROLE_APRON
        layout = _FakeLayout()
        far = config.TUNNEL_RIM_NEIGHBOUR_WINDOW_M + 100.0
        layout.shapes.append(bridges.BuiltShape(
            polygon=Polygon([(far, far), (far + 60.0, far),
                             (far + 60.0, far + 60.0), (far, far + 60.0)]),
            role=ROLE_APRON, ref="far", altitude=self.NEIGHBOUR_VALUE))
        self._emit(layout)
        assert self._rim_values(layout) == [8.0], "R_est, not the far apron"

    # ── RUNG 2: R_est, the law median ────────────────────────────────

    def test_with_NO_built_neighbour_the_rim_takes_R_est(self):
        layout = self._layout(with_neighbour=False)
        self._emit(layout, dem=_SpikeDem(
            8.0, 12.0, radius_degrees=0.0002,
            anchor_longitude=ANCHOR_LONGITUDE + 0.00025))
        assert self._rim_values(layout) == [8.0]

    # ── RUNG 3 / the OFF arm: raw DEM, last ──────────────────────────

    def test_flag_off_restores_the_per_part_DEM_sample(self, monkeypatch):
        """``O4_RIM_SOLVED_NEIGHBOUR=0`` is byte-identical to the
        pre-ruling engine: per-part DEM samples, R_est only on nodata —
        which is exactly the spread this section retires."""
        monkeypatch.setattr(config, "RIM_SOLVED_NEIGHBOUR", False)
        layout = self._layout()
        self._emit(layout, dem=_SpikeDem(
            8.0, 12.0, radius_degrees=0.0002,
            anchor_longitude=ANCHOR_LONGITUDE + 0.00025))
        values = self._rim_values(layout)
        assert len(values) > 1, "the OFF arm must still spread"
        assert self.NEIGHBOUR_VALUE not in values

    def test_a_TUNNEL_facility_keeps_its_per_part_DEM_sample(self):
        """SCOPE, and it is the sibling spec's own: basin-rim-flush §2.1
        froze the tunnel arm verbatim — "no OTHH fixture exercises them
        and the EGLL class must not move" — and §0's whole measured
        population is basin rim bands.  A tunnel rim stays terrain-true;
        widening §C to it is a separate ruling."""
        layout = _FakeLayout()
        setattr(layout, assembly.CLASSIFICATION_ATTRIBUTE,
                _Classification(tunnels=[_tunnel_record()]))
        assembly.build_tunnel_layout_shapes(
            layout, _SpikeDem(8.0, 12.0, radius_degrees=0.0002,
                              anchor_longitude=ANCHOR_LONGITUDE + 0.00025),
            TILE_LATITUDE, TILE_LONGITUDE)
        rims = [shape for shape in layout.shapes
                if shape.role == ROLE_TUNNEL_TRENCH
                and str(shape.ref) == "object_tunnel_rim"]
        assert rims, "vacuous — the tunnel arm emitted no rim"
        values = {round(float(a), 3)
                  for plate in rims for a in plate.node_altitudes}
        assert len(values) > 1, (
            "the tunnel rim must still be TERRAIN-TRUE: per-part DEM "
            "samples, spreading under a spike — §C did not reach it")

    # ── AMENDMENT 1 §2: THE RIM RE-SEATS POST-SOLVE ──────────────

    def test_the_pre_solve_plate_keeps_R_est_as_its_SEED(self):
        """Rung 1 CANNOT fire pre-solve — no built neighbour carries a
        value at the emitter's slot (measured at LEMD: all 18 parts took
        R_est while the apron beside them emitted ~599.98).  The seed is
        the law median, and the re-seat is a separate pass."""
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        assert self._rim_values(layout) == [8.0]

    def _reseat(self, layout):
        return assembly.reseat_basin_rim_plates_post_solve(layout)

    def _solved_neighbour(self, layout, value=None, role=None):
        """A neighbour carrying a SOLVED value, added AFTER the emit —
        the post-solve world the re-seat runs in."""
        from auto_patch.layout import ROLE_APRON
        layout.shapes.append(bridges.BuiltShape(
            polygon=Polygon([(-90, -90), (90, -90), (90, 90), (-90, 90)]),
            role=role or ROLE_APRON, ref="solved",
            altitude=(self.NEIGHBOUR_VALUE if value is None else value)))
        return layout

    def test_the_rim_RE_SEATS_at_the_solved_neighbour(self):
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        assert self._rim_values(layout) == [8.0], "vacuous — no seed"
        self._solved_neighbour(layout)
        report = self._reseat(layout)
        assert report["reseated"] == report["parts"] > 0
        assert self._rim_values(layout) == [self.NEIGHBOUR_VALUE]
        assert report["worst_move_m"] == pytest.approx(12.0, abs=0.01)

    def test_the_ADOPTION_is_ONE_DIRECTIONAL(self):
        """The rim moves; the neighbour never does."""
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        self._solved_neighbour(layout)
        neighbour = layout.shapes[-1]
        before = (neighbour.altitude, neighbour.node_altitudes,
                  neighbour.polygon.wkt)
        self._reseat(layout)
        assert (neighbour.altitude, neighbour.node_altitudes,
                neighbour.polygon.wkt) == before

    def test_with_NO_solved_neighbour_the_R_est_seed_STANDS(self):
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        report = self._reseat(layout)
        assert report["kept_seed"] == report["parts"] > 0
        assert report["reseated"] == 0
        assert self._rim_values(layout) == [8.0]

    def test_the_re_seat_never_reads_our_OWN_floor_pan(self):
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        floors = _basin_plates(layout, "trench")
        assert floors, "vacuous — no floor pan to be tempted by"
        floor_value = float(floors[0].node_altitudes[0])
        self._reseat(layout)
        assert floor_value not in self._rim_values(layout)

    def test_a_pad_seated_at_the_FLOOR_is_not_a_re_seat_neighbour(self):
        from auto_patch.layout import ROLE_BUILDING
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        self._solved_neighbour(layout, value=600.5, role=ROLE_BUILDING)
        layout.shapes[-1].basin_floor_seat_m = 1.0
        report = self._reseat(layout)
        assert report["reseated"] == 0
        assert self._rim_values(layout) == [8.0]

    def test_the_re_seat_leaves_the_band_FLAT(self):
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        self._solved_neighbour(layout)
        self._reseat(layout)
        for plate in _basin_plates(layout, "rim"):
            assert len(set(plate.node_altitudes)) == 1
            assert plate.altitude_high is None
            assert plate.altitude_low is None

    def test_the_re_seat_is_VACUOUS_with_the_flag_off(self, monkeypatch):
        layout = self._layout(with_neighbour=False)
        self._emit(layout)
        self._solved_neighbour(layout)
        monkeypatch.setattr(config, "RIM_SOLVED_NEIGHBOUR", False)
        report = self._reseat(layout)
        assert report["parts"] == 0
        assert self._rim_values(layout) == [8.0]

    def test_the_re_seat_is_WIRED_at_the_post_solve_slot(self):
        """RULING 2026-08-21d was found UNIMPLEMENTED in production
        because its call site never existed.  This twin fails on the
        unwired state, and pins that the call is AFTER the solve."""
        import inspect
        from auto_patch import pipeline as PL
        source = inspect.getsource(PL)
        assert "reseat_basin_rim_plates_post_solve" in source
        i_call = source.index("reseat_basin_rim_plates_post_solve")
        i_solve = source.index("per_surface_solve(layout, icao,")
        assert i_solve < i_call, "the re-seat must run AFTER the solve"

    def test_the_rungs_are_in_the_stated_ORDER(self):
        """One reading of the law, asserted on the source: neighbour
        first, R_est second, DEM last."""
        import inspect
        source = inspect.getsource(assembly.build_tunnel_layout_shapes)
        neighbour = source.index("_rim_neighbour_value(")
        r_est = source.index('_rim_source = "r_est"')
        dem = source.index('_rim_source = "dem"')
        assert r_est < neighbour < dem


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
        expected = _open_pit_floor(8.0, 3.81)
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

    def test_the_floor_keys_on_the_true_deepest_solid_for_a_BORE(self):
        """OTHH Drainage_06: the clustered interface level is -3.859 m and
        the deepest solid is -4.201 m.  Keying on the level spent 0.342 m
        of the promised 0.5 m clearance before the floor was even cut.

        OWNER 2026-08-26 re-pins this for EVERY basin: the deepest-solid
        key and both margins are now the law for open pits as for bores
        (Amendment 3's deck-face clause is retired-kept-gated), so the
        two readers below agree."""
        from auto_patch import object_terrain_assembly as _A
        record = assembly.basin_trench_structures(_Classification(
            ground_interfaces=[
                _interface(floor_y_m=-3.859, solid_minimum_y_m=-4.201)]))[0]
        assert _A.basin_facility_deck_reference_y(record) == (
            pytest.approx(-4.201), None, _A.BASIN_FLOOR_KEY_SOLID_WITNESS)
        assert grade_law.basin_trench_floor_elevation_m(
            8.0, -4.201) == pytest.approx(
                8.0 - 4.201
                - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
                - config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)
        # ...and the OPEN-pit reader on the SAME record now takes the
        # SAME path (the retired clause is pinned under its gate in
        # ``TestBasinRegionFloorKey``).
        assert _A.basin_facility_deck_reference_y(
            record, open_pit=True) == (
                pytest.approx(-4.201), None,
                _A.BASIN_FLOOR_KEY_SOLID_WITNESS)

    def test_the_emitted_open_pit_floor_keys_on_its_deepest_solid(self):
        """Every fixture here is an OPEN pit (BOWL_UNDER_DECK, zero
        above-grade area) — the LEMD class exactly — and under the
        2026-08-26 law that keys on the deepest genuine solid (-4.201),
        not on the deck face (-3.859)."""
        layout = _FakeLayout()
        _emit_basin(
            layout,
            [_interface(floor_y_m=-3.859, solid_minimum_y_m=-4.201)],
            _FakeDem(8.0))
        expected = _open_pit_floor(8.0, 4.201)
        plates = _basin_plates(layout, "trench")
        assert plates
        for plate in plates:
            # ``abs``, not ``rel``: emitted plate altitudes are quantised
            # to the millimetre, so the tolerance is one quantum.
            assert all(altitude == pytest.approx(expected, abs=2e-3)
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

    def test_a_BORE_floor_still_clears_the_modelled_bottom(self):
        """The acceptance property the margins exist to protect, pinned
        where the margins now live: the BORE limb of the law.  A deck you
        pass under must be cleared; an open pit has no deck to clear."""
        modelled_bottom_world = 8.0 - 4.201
        assert grade_law.basin_trench_floor_elevation_m(8.0, -4.201) <= (
            modelled_bottom_world
            - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M + 1e-9)

    def test_the_open_pit_limb_takes_THE_MARGINS_TOO(self, monkeypatch):
        """OWNER 2026-08-26 on the law function itself: ``bore_class``
        no longer exempts anything by default — the Amendment-3
        zero-margin arm fires only under its gate."""
        assert grade_law.basin_trench_floor_elevation_m(
            593.0288, -7.0159, bore_class=False) == pytest.approx(584.5129)
        assert grade_law.basin_trench_floor_elevation_m(
            593.0288, -7.0159) == pytest.approx(584.5129)
        monkeypatch.setattr(config, "BASIN_OPEN_PIT_DECK_KEY", True)
        assert grade_law.basin_trench_floor_elevation_m(
            593.0288, -7.0159, bore_class=False) == pytest.approx(586.0129)

    def test_the_bore_default_keeps_every_two_argument_caller(self):
        """``bore_class`` defaults True so every validator and twin that
        reproduces a BORE floor with two arguments is unchanged."""
        for rim, key in ((12.0, -4.201), (8.0, -3.81), (0.0, -13.199)):
            assert grade_law.basin_trench_floor_elevation_m(rim, key) == \
                pytest.approx(grade_law.basin_trench_floor_elevation_m(
                    rim, key, bore_class=True))


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
            _open_pit_floor(8.0, 3.81))
        # The draped object seats on the terrain at its anchor, and with
        # the seat gone that terrain IS the floor pan.
        assert record["predicted_drape_elevation_m"] == pytest.approx(
            record["floor_m"])
        assert record["predicted_rim_elevation_m"] == pytest.approx(8.0)
        assert record["shell_count"] == 1
        assert record["floor_plates"] >= 1

    def test_the_record_reports_the_emitted_rim_range(self, monkeypatch):
        """THE GAP RECON NAMED, reproduced: the band parts take their OWN
        DEM samples and the law value is only their nodata fallback, so a
        single reported number cannot be both.  Here an off-centre rise
        lifts the eastern band parts to 12 m while the law value (the
        outline median) stays 8 m — measured at OTHH Dewatering_01 as a
        0.71-2.96 m band behind a single 0.80 m number.

        RE-PINNED WITH ``RIM_SOLVED_NEIGHBOUR`` OFF (spec
        lemd-rim-and-stations §C, owner RULINGS 2026-08-28 item 3).  The
        per-part DEM sample IS the defect §C retires: with the flag on
        the band has ONE value source and this fixture can no longer
        produce a range at all.  What the twin pins — that the RECORD
        reports what was EMITTED, not what the law said — is unchanged
        and still law; it just needs the arm where emitted and law can
        still disagree.  The same re-pinning the pool-scoping and
        pad-seating gates took: the premise lives with the gate off.
        """
        monkeypatch.setattr(config, "RIM_SOLVED_NEIGHBOUR", False)
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
    plates instead.

    RETIRED-KEPT-GATED (docket B, docs/specs/basin-group-seat-spec.md
    §2.6): the shipped law is now the GROUP seat, and this class is the
    gate-off pin — spec §3 case 6, "old behaviour byte-identical on the
    synthetic fixture".  Every assertion below is the PRE-AMENDMENT
    behaviour and must keep passing with ``O4_BASIN_GROUP_SEAT=0``; the
    group law's own arms live in ``tests/test_basin_group_seat.py``."""

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
        # THE GATE-OFF ARM (see the class docstring).
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", False)

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


# ---------------------------------------------------------------------------
# A DECAL IS NOT A SOLID — facility floor integrity (spec docs/specs/
# tunnel-trench-law-and-basin-floor-spec.md §2)
# ---------------------------------------------------------------------------

def _ground_decal(y: float, half_span_m: float = 20.0) -> ObjectGeometry:
    """A GROUND DECAL the way a pack ships one: a single flat 4-vertex
    quad, no vertical extent at all.  LEMD's
    ``AESlite-LEMD-VOR-15-T4S-{1,2}.obj`` are exactly this, authored at
    y = −48.244."""
    builder = _GeometryBuilder()
    builder.add_horizontal_rectangle(
        -half_span_m, half_span_m, -half_span_m, half_span_m, y)
    return builder.build()


class TestDecalIsNotASolid:
    """§2.1.  The LEMD class: two 4-vertex VOR ground decals authored at
    −48.244 m (−50.0 effective) pooled with the airport's own objects by
    the 2.0 m chain join, and ``_StructureFrame.minimum_effective_height_m``
    — a plain min over the pooled placements — handed −50.0 to the basin
    floor law.  The trench came out 51.5 m below its own rim under a
    7.02 m body, and 90.7 % of LEMD's census rows were the wall of it.

    Pooling itself is NOT changed by this round (spec §2.3): the floor
    witness is made immune to the pool's worst member instead.
    """

    def test_the_threshold_is_the_specced_one(self):
        assert config.MIN_SOLID_PART_THICKNESS_M == pytest.approx(0.3)

    def test_a_flat_decal_never_witnesses_the_floor(self, monkeypatch):
        """(a) The decal is a COMPONENT member — it is not thrown out of
        the classification — but the floor comes from the REAL solids.

        Run with ``BASIN_POOL_SCOPING`` OFF, because that gate is what
        keeps a decal out of the pit SEED set (see
        :class:`TestBasinPoolScoping`); with it on there is no pooled
        decal left for this twin's premise to turn on.  §2.1 and the
        scoping law are independent, and this pins the §2.1 half.
        """
        monkeypatch.setattr(config, "BASIN_POOL_SCOPING", False)
        geometry = dict(_open_pit_pair(depth_m=4.0))
        geometry["Decals/vor_ground_decal.obj"] = _ground_decal(-48.244)
        classification = _classify(geometry)
        interfaces = [
            interface for interface in classification.ground_interfaces
            if otf.is_carved_basin_interface(interface)
        ]
        assert interfaces, "fixture no longer classifies as a carved basin"
        assert "Decals/vor_ground_decal.obj" in \
            interfaces[0].object_resources, (
            "the decal is not in the pool — the fixture would prove "
            "nothing about the exclusion")
        frame = otf._build_structure_frame(
            [_placement(resource) for resource in geometry], geometry)
        assert frame.minimum_effective_height_m == pytest.approx(-48.244), (
            "the frame's full minimum must still SEE the decal — this is "
            "the value that dug LEMD's basin, and the counterfactual this "
            "twin turns on")
        assert interfaces[0].solid_minimum_y_m == pytest.approx(-4.0), (
            f"the floor witness reads "
            f"{interfaces[0].solid_minimum_y_m} — a flat quad with no "
            f"vertical extent dug the facility's floor")

    def test_a_genuine_deep_solid_still_sets_the_floor(self):
        """(b) The scope guard: a part WITH vertical extent is a solid
        whatever its depth, and the deepest one is still the witness (the
        Drainage_06 sibling-shell class, at 8 m)."""
        geometry = {
            "Buildings/Drainage/basin_000.obj": _pit_shell(
                30.0, 6.0, -3.859, 0.0),
            "Buildings/Drainage/basin_001.obj": _pit_shell(
                28.5, 6.0, -8.0, 0.06),
        }
        interfaces = [
            interface
            for interface in _classify(geometry).ground_interfaces
            if otf.is_carved_basin_interface(interface)
        ]
        assert interfaces
        assert interfaces[0].solid_minimum_y_m == pytest.approx(-8.0)

    def test_the_full_minimum_still_sees_every_part(self):
        """The exclusion is the FLOOR WITNESS only.  Ground contact and
        the cosmetic-bridge test read
        ``minimum_effective_height_m``, which keeps every part —
        narrowing that too would change classifications this round never
        measured."""
        placements = [_placement("Decals/vor_ground_decal.obj")]
        geometry = {"Decals/vor_ground_decal.obj": _ground_decal(-48.244)}
        frame = otf._build_structure_frame(placements, geometry)
        assert frame.minimum_effective_height_m == pytest.approx(-48.244)
        assert frame.solid_floor_witness_y_m == pytest.approx(0.0), (
            "a pool of decals witnesses NO floor; the fallback says so")


class TestBasinPoolScoping:
    """The POOLING half of the LEMD defect — spec §2.3's deferred docket,
    measured and closed 2026-08-25.

    §2.1 made the pool's FLOOR immune to a decal.  Its EXTENT was not:
    an open-pit SEED contributes its FULL footprint and chains every
    other seed within :data:`otf.TUNNEL_COMPONENT_JOIN_BUFFER_M` to it,
    so a flat quad with no vertical extent is the one shape that can
    make a basin arbitrarily large.  Measured at LEMD: five
    ``AESlite-LEMD-VOR-*.obj`` decals, each a SINGLE 4-vertex quad
    1.4-1.6 km on a side at exactly y = −50.0, seeded three pit
    components of 2.0-2.6 million m² and dragged the real 11,705 m²
    control-tower cutout into a 2,078,883 m² basin spanning 1.4 km.
    With the decals off the seed set the basin measures 12,251 m² at
    the owner's JOSM bbox for the real sunken cutout, at an UNCHANGED
    floor (−7.016 m both ways).

    The discriminator is :func:`otf.part_has_solid_thickness` — the SAME
    predicate §2.1 uses.  Paint is not structure, in either law.
    """

    @staticmethod
    def _decal_bridge_pool(*, decal_y: float = -48.244):
        """Two real pits far apart, plus one huge flat decal spanning
        both — the LEMD shape, minimised.  The pits are 400 m apart, far
        beyond the 2.0 m join buffer, so ONLY the decal can chain them.
        """
        geometry = {
            "Buildings/Drainage/near_000.obj": _pit_shell(
                30.0, 6.0, -4.0, 0.0),
            "Buildings/Drainage/near_001.obj": _pit_shell(
                28.5, 6.0, -4.06, 0.06),
            "Buildings/Drainage/far_000.obj": _pit_shell(
                30.0, 6.0, -4.0, 0.0),
            "Buildings/Drainage/far_001.obj": _pit_shell(
                28.5, 6.0, -4.06, 0.06),
            "Decals/vor_ground_decal.obj": _ground_decal(
                decal_y, half_span_m=900.0),
        }
        far_latitude = ANCHOR_LATITUDE + 400.0 / 111320.0
        placements = [
            _placement("Buildings/Drainage/near_000.obj"),
            _placement("Buildings/Drainage/near_001.obj"),
            _placement("Buildings/Drainage/far_000.obj",
                       latitude=far_latitude),
            _placement("Buildings/Drainage/far_001.obj",
                       latitude=far_latitude),
            _placement("Decals/vor_ground_decal.obj"),
        ]
        return placements, geometry

    @staticmethod
    def _pit_components(placements, geometry):
        cache = otf._ResourceGeometryCache(geometry)
        frame = otf._build_structure_frame(placements, geometry, cache)
        return [
            sorted(component)
            for component in otf._open_pit_components(
                placements, frame, cache)
        ]

    def test_the_gate_is_default_on(self):
        assert config.BASIN_POOL_SCOPING is True

    def test_the_discriminator_is_the_2_1_predicate(self):
        """One notion, one spelling.  A second "is it thin" test is the
        drift this shares a function to prevent."""
        thickness = config.MIN_SOLID_PART_THICKNESS_M
        assert otf.part_has_solid_thickness(0.0, thickness)
        assert otf.part_has_solid_thickness(-4.0, -4.0 + 2.0 * thickness)
        assert not otf.part_has_solid_thickness(-50.0, -50.0)
        assert not otf.part_has_solid_thickness(-4.0, -4.0 + thickness / 2.0)

    def test_a_thin_bridge_part_does_not_chain_two_basins(self):
        """ON: the decal seeds nothing, so each real pit is its own
        component and neither inherits the decal's kilometre-wide
        footprint."""
        placements, geometry = self._decal_bridge_pool()
        components = self._pit_components(placements, geometry)
        assert components == [
            ["Buildings/Drainage/far_000.obj",
             "Buildings/Drainage/far_001.obj"],
            ["Buildings/Drainage/near_000.obj",
             "Buildings/Drainage/near_001.obj"],
        ], components

    def test_the_confined_basin_is_the_real_object_only(self):
        """...and the emitted interface's below-grade footprint is the
        pit's own, not the decal's 3.24 km² quad."""
        placements, geometry = self._decal_bridge_pool()
        classification = otf.classify_object_terrain_features(
            placements, geometry, pack_root="PACK",
            basin_trench_enabled=True)
        carved = [
            interface for interface in classification.ground_interfaces
            if otf.is_carved_basin_interface(interface)
        ]
        assert carved, "fixture no longer classifies as a carved basin"
        for interface in carved:
            assert "Decals/vor_ground_decal.obj" not in \
                interface.object_resources
            assert interface.below_grade_footprint.area < 10_000.0, (
                f"basin footprint {interface.below_grade_footprint.area} m² "
                f"— the decal's footprint escaped into it")

    def test_gate_off_reproduces_the_chain(self, monkeypatch):
        """OFF is the pre-fix law exactly: one component, both pits and
        the decal in it."""
        monkeypatch.setattr(config, "BASIN_POOL_SCOPING", False)
        placements, geometry = self._decal_bridge_pool()
        components = self._pit_components(placements, geometry)
        assert components == [[
            "Buildings/Drainage/far_000.obj",
            "Buildings/Drainage/far_001.obj",
            "Buildings/Drainage/near_000.obj",
            "Buildings/Drainage/near_001.obj",
            "Decals/vor_ground_decal.obj",
        ]], components

    def test_a_thick_deep_neighbour_is_still_pooled(self):
        """The scope guard.  A genuinely-deep part WITH vertical extent
        is structure however deep it goes, and still seeds and chains —
        this is the OTHH sibling-shell class (Drainage_06 at −4.2 beside
        −3.86), and narrowing it would tear real basins apart."""
        placements, geometry = self._decal_bridge_pool()
        # Replace the decal with a SOLID slab of the same plan extent.
        builder = _GeometryBuilder()
        builder.add_horizontal_rectangle(-40.0, 40.0, -40.0, 40.0, -8.0)
        builder.add_horizontal_rectangle(-40.0, 40.0, -40.0, 40.0, -7.0)
        builder.add_vertical_wall(-40.0, -40.0, 40.0, -8.0, -7.0)
        geometry["Decals/vor_ground_decal.obj"] = builder.build()
        components = self._pit_components(placements, geometry)
        assert any(
            "Decals/vor_ground_decal.obj" in component
            and "Buildings/Drainage/near_000.obj" in component
            for component in components
        ), components

    def test_othh_class_basins_are_untouched(self):
        """An OTHH drainage pair carries no thin part at all, so the gate
        cannot move it — the byte-identity claim, in a twin."""
        geometry = _open_pit_pair(depth_m=4.0)
        placements = [_placement(resource) for resource in geometry]
        assert (self._pit_components(placements, geometry)
                == [sorted(geometry)])

    def test_the_frame_still_carries_every_part(self):
        """SCOPE IS THE SEED SET, NOT THE FRAME.  Measured 2026-08-25:
        dropping thin parts from the structure frame re-seeded OTHH
        ``Bridge_04`` as a tunnel, because
        ``_agl_tunnel_seed_resources`` reads its above-grade cap off the
        WHOLE structure (owner ruling 2026-07-31).  The frame must keep
        seeing them."""
        placements, geometry = self._decal_bridge_pool()
        frame = otf._build_structure_frame(placements, geometry)
        assert frame.minimum_effective_height_m == pytest.approx(-48.244)

    def test_the_cache_fingerprint_moves_with_the_gate(self, monkeypatch,
                                                      tmp_path):
        """A flip changes the CLASSIFICATION, so a flipped run must miss
        a pickle written by the other arm (the version-14 lesson)."""
        dsf_path = tmp_path / "+40-004.dsf"
        dsf_path.write_text("x")
        pack_root = tmp_path / "pack"
        pack_root.mkdir()
        monkeypatch.setattr(
            assembly.dsf_reader, "airport_mod_cache_dir",
            lambda root: str(tmp_path))
        monkeypatch.setattr(config, "BASIN_POOL_SCOPING", True)
        _path, on_digest = assembly._classification_sidecar(
            str(dsf_path), str(pack_root), None)
        monkeypatch.setattr(config, "BASIN_POOL_SCOPING", False)
        _path, off_digest = assembly._classification_sidecar(
            str(dsf_path), str(pack_root), None)
        assert on_digest and off_digest and on_digest != off_digest


class TestBasinFloorDisagreementGate:
    """§2.2.  Two instruments described one bottom and the 43 m
    disagreement between them rode the same log line unchecked
    (``body_depth_m 7.02`` beside ``floor_m 545.52``)."""

    def test_the_threshold_is_the_specced_one(self):
        assert config.BASIN_FLOOR_DISAGREEMENT_M == pytest.approx(2.0)

    def test_the_gate_fires_on_the_lemd_disagreement(self):
        """(c) The floor derives from the deck-face population and the
        discarded witness comes back for the caller to NAME."""
        record = _tunnel_record(body_depth_m=7.016)
        object.__setattr__(record, "solid_minimum_y_m", -50.0)
        deck_reference_y, discarded, key_source = (
            assembly.basin_facility_deck_reference_y(record))
        assert deck_reference_y == pytest.approx(-7.016)
        assert discarded == pytest.approx(-50.0)
        assert key_source == assembly.BASIN_FLOOR_KEY_DECK_FACE

    def test_an_agreeing_facility_is_byte_identical(self):
        """(d) The OTHH class — every basin there agrees within 0.4 m, and
        an EGLL-class shell wall ~2 m below its deck is the case this
        must NOT catch: the deeper reading still wins, nothing is
        discarded."""
        for body_depth, solid_minimum, expected in (
            (3.859, -4.201, -4.201),      # OTHH Drainage_06, 0.342 m
            (13.082, -13.199, -13.199),   # OTHH AuxBuilding_17, 0.117 m
            (3.816, -3.816, -3.816),      # exact agreement
            (2.0, -3.9, -3.9),            # EGLL-class 1.9 m liner wall
        ):
            record = _tunnel_record(body_depth_m=body_depth)
            object.__setattr__(record, "solid_minimum_y_m", solid_minimum)
            assert assembly.basin_facility_deck_reference_y(record) == (
                pytest.approx(expected), None,
                assembly.BASIN_FLOOR_KEY_SOLID_WITNESS
                if expected != -body_depth
                else assembly.BASIN_FLOOR_KEY_DECK_FACE)

    def test_the_threshold_constant_moves_the_gate(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_FLOOR_DISAGREEMENT_M", 0.2)
        record = _tunnel_record(body_depth_m=3.859)
        object.__setattr__(record, "solid_minimum_y_m", -4.201)
        deck_reference_y, discarded, _ks = (
            assembly.basin_facility_deck_reference_y(record))
        assert deck_reference_y == pytest.approx(-3.859)
        assert discarded == pytest.approx(-4.201)

    def test_the_emitter_names_the_resource_out_loud(self, capsys):
        """The whole point of the gate: the discarded witness is HEARD.
        The emitted floor is the one the body depth evidences, and the
        line carries the resource and the y it claimed."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        layout = _FakeLayout()
        _emit_basin(
            layout,
            [_interface(floor_y_m=-7.016, solid_minimum_y_m=-50.0,
                        resources=("Decals/vor_ground_decal.obj",))],
            _FakeDem(8.0))
        line = "".join(
            row for row in capsys.readouterr().out.splitlines(keepends=True)
            if "BASIN FLOOR DISAGREEMENT" in row)
        assert line, "the discarded witness was DISCARDED SILENTLY"
        assert "vor_ground_decal.obj" in line
        assert "-50.000" in line
        record = getattr(
            layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE)[0]
        assert record["floor_m"] == pytest.approx(
            _open_pit_floor(8.0, 7.016))
        assert record["solid_minimum_y_m"] == pytest.approx(-7.016)

    def test_an_agreeing_facility_prints_no_gate_line(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        layout = _FakeLayout()
        _emit_basin(layout,
                    [_interface(floor_y_m=-3.859, solid_minimum_y_m=-4.201)],
                    _FakeDem(8.0))
        assert "BASIN FLOOR DISAGREEMENT" not in capsys.readouterr().out
        record = getattr(
            layout, assembly.BASIN_FACILITY_RECORDS_ATTRIBUTE)[0]
        # The agreeing witness (-4.201) is the key under the 2026-08-26
        # law, deck face (-3.859) or not.
        assert record["floor_m"] == pytest.approx(
            _open_pit_floor(8.0, 4.201))

    def test_the_seating_predictor_reads_the_same_floor_key(self):
        """ONE implementation, both readers: the rim-flush seating
        predictor mirrors the emitter's grouping character for character,
        so it must mirror its floor key too — otherwise a facility is cut
        to one floor and seated against another."""
        classification = _Classification(ground_interfaces=[
            _interface(floor_y_m=-7.016, solid_minimum_y_m=-50.0)])
        facilities = assembly.basin_rim_flush_facilities(classification)
        assert facilities
        assert facilities[0].solid_minimum_y_m == pytest.approx(-7.016)


class TestClassificationCacheVersionCoversTheFloorWitness:
    """The version-14 lesson, again: the FIELD did not change, its
    MEANING did, and a pickle's fingerprint covers the PACK, not the
    classifier's rules.  A v18 LEMD result still carries −50.0 m."""

    def test_the_cache_version_retires_pre_witness_pickles(self):
        assert assembly._CLASSIFICATION_CACHE_VERSION >= 20


# ---------------------------------------------------------------------------
# A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR (owner RULINGS 2026-08-25f)
# spec docs/specs/basin-pad-floor-seating-spec.md §1 + §2
# ---------------------------------------------------------------------------

class TestBasinPadFloorSeating:
    """The building8 disposition, through THREE owner amendments.

    LEMD ships ``building8`` — a 33,237 m² flat pad — over the whole
    11,805 m² sunken tower circle.  The floor pan was differenced against
    every earlier-born shape, so the pad ERASED it and a classified,
    scoped, floor-agreed basin emitted nothing.

    AMENDMENT 3 (owner 2026-08-25) is the landed law: "a simple 7 m deep
    cutout for the whole area should work without having to sever the
    buildings".  NO SEVERING, NO SEATING — the pad keeps its authored
    grade, geometry, welds and identity everywhere, and only its
    FLATTENING AUTHORITY yields inside the facility: the floor plates and
    the R2 wall band are born THROUGH it and own the interior.

    Amendment 1's whole-pad SEAT and Amendment 2's boundary CUT are kept
    and gated OFF (``config.BASIN_PAD_WHOLE_SEAT`` /
    ``config.BASIN_PAD_SEVER``); their twins live at the foot of this
    class so a revival is not a rewrite.
    """

    APRON = Polygon([(-90, -90), (90, -90), (90, 90), (-90, 90)])
    #: 120 x 120 m, comfortably larger than the 50 x 50 m default body —
    #: the ``building8`` class: a pad LARGER than the facility it covers.
    COVERING_PAD = Polygon([(-60, -60), (60, -60), (60, 60), (-60, 60)])
    #: 20 x 20 m, wholly inside the same body — the §1.1 limb.
    INSIDE_PAD = Polygon([(-10, -10), (10, -10), (10, 10), (-10, 10)])
    #: 20 x 20 m straddling the body's +x rim: 50 % of the PAD is inside
    #: and it covers 8 % of the FACILITY — under threshold BOTH ways.
    STRADDLING_PAD = Polygon([(15, -10), (35, -10), (35, 10), (15, 10)])
    #: 20 x 20 m clear of the body altogether.
    OUTSIDE_PAD = Polygon([(60, -10), (80, -10), (80, 10), (60, 10)])
    #: welded to COVERING_PAD's +x edge, wholly outside the basin — the
    #: ``building18`` class (rigidly coupled, must never move).
    RIGID_NEIGHBOUR = Polygon([(60, -60), (200, -60), (200, 60), (60, 60)])

    def _layout(self, *pads, apron=False):
        from auto_patch.layout import ROLE_APRON, ROLE_BUILDING
        layout = _FakeLayout()
        if apron:
            layout.shapes.append(bridges.BuiltShape(
                polygon=self.APRON, role=ROLE_APRON, ref="apron",
                altitude=8.0))
        for index, polygon in enumerate(pads):
            layout.shapes.append(bridges.BuiltShape(
                polygon=polygon, role=ROLE_BUILDING,
                ref=f"building{index}", altitude=8.0))
        return layout

    def _pads(self, layout):
        from auto_patch.layout import ROLE_BUILDING
        return {shape.ref: shape for shape in layout.shapes
                if shape.role == ROLE_BUILDING}

    def _expected_floor(self, dem_m=8.0, body_depth=4.0):
        return _open_pit_floor(dem_m, body_depth)

    # ── AMENDMENT 3: the authority clip ─────────────────────────────
    def test_a_pad_spanning_the_facility_is_UNTOUCHED(self):
        """Item 2, the whole of it: grade, geometry, welds, identity."""
        layout = self._layout(self.COVERING_PAD, apron=True)
        pad = self._pads(layout)["building0"]
        floors, _rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert floors >= 1
        assert self._pads(layout) == {"building0": pad}
        assert pad.polygon.equals(self.COVERING_PAD)
        assert pad.altitude == pytest.approx(8.0)
        assert pad.basin_floor_seat_m is None

    def test_the_floor_plates_emit_THROUGH_the_pad(self):
        """The authority clip, measured against its own control: with the
        pad owning the ground the basin emitted NOTHING (that is the
        reported defect); with its interior claim clipped the pan is
        exactly the pan of an unobstructed facility."""
        layout = self._layout(self.COVERING_PAD, apron=True)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        clipped = sum(plate.polygon.area
                      for plate in _basin_plates(layout, "trench"))
        # The control is the SAME layout without the pad — apron and all,
        # so the only difference between the two arms is the pad.
        bare = self._layout(apron=True)
        _emit_basin(bare, [_interface()], _FakeDem(8.0))
        bare_area = sum(plate.polygon.area
                        for plate in _basin_plates(bare, "trench"))
        assert clipped == pytest.approx(bare_area, rel=1e-9)
        assert clipped > 0.0

    def test_the_WALL_band_emits_through_the_pad_too(self):
        """The R2 wall is the rim band — a node split OUTSIDE the body at
        surrounding grade against the pan at the floor.  LEMD arm 1
        measured what happens when only the FLOOR yields: "no rim band
        emitted", and the hole ramped out to the pad's distant ring
        instead of walling at the facility boundary."""
        # No apron: R13's cut leaves the apron's remainder ON the body
        # boundary, and THAT owned ground yields the band on its own —
        # unchanged, and not what this twin is about.  Here the pad is
        # the band's only competitor.
        layout = self._layout(self.COVERING_PAD)
        _floors, rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert rims >= 1
        band = _basin_plates(layout, "rim")
        assert band
        # the wall: band at grade, pan at the floor, a node split apart
        for plate in band:
            assert all(altitude == pytest.approx(8.0)
                       for altitude in plate.node_altitudes)
        for plate in _basin_plates(layout, "trench"):
            assert all(altitude == pytest.approx(self._expected_floor())
                       for altitude in plate.node_altitudes)

    def test_a_rigid_coupled_neighbour_is_UNMOVED(self):
        """Amendment 3 item 3, the LEMD shape in miniature.  Amendment 1
        measured that seating ``building8`` either sinks its 75,885 m²
        rigid partner 16 m or is silently discarded; the authority clip
        touches neither pad."""
        layout = self._layout(self.COVERING_PAD, self.RIGID_NEIGHBOUR,
                              apron=True)
        pads_before = dict(self._pads(layout))
        floors, _rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert floors >= 1
        pads_after = self._pads(layout)
        assert pads_after == pads_before
        for pad in pads_after.values():
            assert pad.basin_floor_seat_m is None
            assert pad.altitude == pytest.approx(8.0)
        assert pads_after["building1"].polygon.equals(self.RIGID_NEIGHBOUR)

    def test_a_pad_wholly_inside_yields_its_authority_too(self):
        """Item 2 is unconditional — INSIDE or SPANNING, the pad is
        neither split nor seated and the interior is the plates'."""
        layout = self._layout(self.INSIDE_PAD)
        pad = self._pads(layout)["building0"]
        floors, rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert floors >= 1 and rims >= 1
        assert pad.basin_floor_seat_m is None
        assert pad.polygon.equals(self.INSIDE_PAD)
        clipped = sum(plate.polygon.area
                      for plate in _basin_plates(layout, "trench"))
        bare = _FakeLayout()
        _emit_basin(bare, [_interface()], _FakeDem(8.0))
        assert clipped == pytest.approx(
            sum(plate.polygon.area
                for plate in _basin_plates(bare, "trench")), rel=1e-9)

    def test_the_yield_is_reported_by_name(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        layout = self._layout(self.COVERING_PAD, apron=True)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        out = "".join(
            row for row in capsys.readouterr().out.splitlines(keepends=True)
            if "BASIN PAD AUTHORITY YIELDED" in row)
        assert out, "the authority clip was applied SILENTLY"
        assert "building0" in out

    # ── twin (b): outside, and the rim straddler ────────────────────
    def test_a_pad_outside_the_facility_is_untouched(self):
        layout = self._layout(self.OUTSIDE_PAD)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert self._pads(layout)["building0"].basin_floor_seat_m is None

    def test_a_rim_straddler_keeps_its_authority_and_IS_reported(
            self, capsys):
        """A pad under threshold on BOTH sides straddles the basin RIM —
        a real design case this rule is not about.  Its authority is
        KEPT (it still differences the floor) and it is named."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        layout = self._layout(self.STRADDLING_PAD)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        line = "".join(
            row for row in capsys.readouterr().out.splitlines(keepends=True)
            if "BASIN RIM STRADDLER" in row)
        assert line, "a straddler was sorted out SILENTLY"
        assert "building0" in line

    def test_the_straddler_still_differences_the_floor(self):
        layout = self._layout(self.STRADDLING_PAD)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        straddled = sum(plate.polygon.area
                        for plate in _basin_plates(layout, "trench"))
        bare = _FakeLayout()
        _emit_basin(bare, [_interface()], _FakeDem(8.0))
        bare_area = sum(plate.polygon.area
                        for plate in _basin_plates(bare, "trench"))
        assert straddled < bare_area - 1.0

    # ── the flag ────────────────────────────────────────────────────
    def test_flag_off_reproduces_the_erasure(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_PAD_FLOOR_SEAT", False)
        layout = self._layout(self.COVERING_PAD, apron=True)
        floors, rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert (floors, rims) == (0, 0)
        assert self._pads(layout)["building0"].basin_floor_seat_m is None

    def test_flag_off_still_reports_the_pad(self, capsys):
        """The BEHAVIOUR rides the flag; the INSTRUMENT never does."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        import unittest.mock as _mock
        with _mock.patch.object(config, "BASIN_PAD_FLOOR_SEAT", False):
            layout = self._layout(self.COVERING_PAD, apron=True)
            _emit_basin(layout, [_interface()], _FakeDem(8.0))
        out = capsys.readouterr().out
        assert "BASIN PAD" in out and "building0" in out
        assert "O4_BASIN_PAD_FLOOR_SEAT=0" in out

    # ── §2: THE SILENCE DIES ────────────────────────────────────────
    def test_zero_floor_plates_names_the_facility_and_its_differencers(
            self, capsys, monkeypatch):
        """§2.1, UNGATED.  ``body_floor_born == 0`` used to ``continue``
        without a word — the silence that let LEMD ship a basin that
        emitted nothing.  The line names the facility, its floor, and
        every shape the floor was differenced against, with role and
        area."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        monkeypatch.setattr(config, "BASIN_PAD_FLOOR_SEAT", False)
        layout = self._layout(self.COVERING_PAD, apron=True)
        floors, _rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert floors == 0
        out = capsys.readouterr().out
        assert "NO FLOOR PLATE BORN" in out, "zero plates shipped SILENTLY"
        assert "basin.obj" in out
        assert f"{self._expected_floor():.2f} m" in out
        assert "building 'building0'" in out

    def test_the_named_line_is_ungated(self, capsys, monkeypatch):
        """Instrument is law: it fires for a floor eaten by anything."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        monkeypatch.setattr(assembly, "_TUNNEL_WALL_SETBACK_M", 30.0)
        layout = _FakeLayout()
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert "NO FLOOR PLATE BORN" in capsys.readouterr().out

    # ── RETIRED, KEPT, GATED OFF (the keep-work rule) ───────────────
    def test_the_whole_pad_SEAT_is_retired_but_revivable(self, monkeypatch):
        """Amendment 1's §1.1 seat: COMPLETE, retired by Amendment 3
        item 2 ("pads are neither split nor seated"), kept behind
        ``O4_BASIN_PAD_WHOLE_SEAT``."""
        assert config.BASIN_PAD_WHOLE_SEAT is False
        monkeypatch.setattr(config, "BASIN_PAD_WHOLE_SEAT", True)
        layout = self._layout(self.INSIDE_PAD)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert self._pads(layout)["building0"].basin_floor_seat_m == \
            pytest.approx(self._expected_floor())

    def test_the_boundary_CUT_is_retired_but_revivable(self, monkeypatch):
        """Amendment 2's cut: COMPLETE and twinned, never built at an
        airport, superseded outright by Amendment 3, kept behind
        ``O4_BASIN_PAD_SEVER``.  The in-facility piece became its own pad
        at the floor; the remainder kept grade, welds and identity."""
        assert config.BASIN_PAD_SEVER is False
        monkeypatch.setattr(config, "BASIN_PAD_SEVER", True)
        layout = self._layout(self.COVERING_PAD, apron=True)
        _emit_basin(layout, [_interface()], _FakeDem(8.0))
        pads = self._pads(layout)
        assert pads["building0"].basin_floor_seat_m is None
        assert pads["building0_basin"].basin_floor_seat_m == \
            pytest.approx(self._expected_floor())
        outer = {(round(x, 3), round(y, 3))
                 for (x, y) in pads["building0"].polygon.exterior.coords}
        inner = {(round(x, 3), round(y, 3))
                 for (x, y) in
                 pads["building0_basin"].polygon.exterior.coords}
        assert not (outer & inner), "the two halves share a ring vertex"

    def test_a_seat_with_no_floor_plate_is_withdrawn(self, monkeypatch):
        """The withdrawal path stays live for the retired seat."""
        monkeypatch.setattr(config, "BASIN_PAD_WHOLE_SEAT", True)
        monkeypatch.setattr(assembly, "_TUNNEL_WALL_SETBACK_M", 30.0)
        layout = self._layout(self.INSIDE_PAD)
        floors, _rims = _emit_basin(layout, [_interface()], _FakeDem(8.0))
        assert floors == 0
        assert self._pads(layout)["building0"].basin_floor_seat_m is None


# ---------------------------------------------------------------------------
# THE BELOW-GRADE REGION (spec docs/specs/basin-region-footprint-spec.md,
# owner rulings 2026-08-26 "LEMD T4S basin")
# ---------------------------------------------------------------------------

def _region_wall(x0, x1, z0, z1, floor_y):
    """A below-grade WALL object of the T4S class: a floor slab at
    ``floor_y`` with vertical walls rising to grade.  The slab carries
    the horizontal footprint, the walls give the welded component its
    vertical EXTENT — without them the slab is a flat quad and the
    thickness gate would (correctly) read it as ground paint."""
    builder = _GeometryBuilder()
    builder.add_horizontal_rectangle(x0, x1, z0, z1, floor_y)
    builder.add_vertical_wall(x0, z0, z1, floor_y, 0.0)
    builder.add_vertical_wall(x1, z0, z1, floor_y, 0.0)
    return builder.build()


def _region_buried_box(x0, x1, z0, z1, y0, y1):
    """A fully-buried box — the ``LEMD_OBJ-Ground-FSX-LEMD36.obj`` class,
    the ONE member of the real T4S family that escapes the mega-pool."""
    builder = _GeometryBuilder()
    builder.add_horizontal_rectangle(x0, x1, z0, z1, y0)
    builder.add_horizontal_rectangle(x0, x1, z0, z1, y1)
    builder.add_vertical_wall(x0, z0, z1, y0, y1)
    builder.add_vertical_wall(x1, z0, z1, y0, y1)
    return builder.build()


def _region_decal(half_span_m, y):
    """A 0-thickness quad — the ``AESlite-LEMD-VOR-15-T4S-*.obj`` class,
    1.4 km on a side at −50 m.  Without the thickness gate it takes the
    LEMD union to 2.08 M m²."""
    builder = _GeometryBuilder()
    builder.add_horizontal_rectangle(
        -half_span_m, half_span_m, -half_span_m, half_span_m, y)
    return builder.build()


#: The T4S pattern in miniature: two below-grade walls tiling a KNOWN
#: 60 x 60 m rectangle, one fully-buried box inside it, an at-grade hall
#: over it, and a huge 0-thickness decal at −50 m.  Every object shares
#: one placement anchor, exactly like the real 358-object family.
_T4S_KNOWN_RECTANGLE_AREA_M2 = 60.0 * 60.0


def _t4s_pattern():
    return {
        "T4S/wall_west.obj": _region_wall(-30.0, 0.0, -30.0, 30.0, -7.0),
        "T4S/wall_east.obj": _region_wall(0.0, 30.0, -30.0, 30.0, -7.0),
        "T4S/buried_cutout.obj": _region_buried_box(
            -10.0, 10.0, -10.0, 10.0, -6.0, -3.0),
        "T4S/hall.obj": _at_grade_building_geometry(),
        "T4S/vor_decal.obj": _region_decal(200.0, -50.0),
    }


def _t4s_regions(geometry=None):
    geometry = _t4s_pattern() if geometry is None else geometry
    placements = [_placement(resource) for resource in geometry]
    return otf.below_grade_regions(placements, geometry)


class TestBelowGradeRegionRecipe:
    """Spec §2.1 / §3 test 1.  THE CUT SHAPE IS DERIVED FROM THE OBJECTS
    THEMSELVES, region-level and pool-independent — the instrument that
    sees LEMD's four below-grade shells inside a FLAT_CONFIRMED
    358-object mega-pool."""

    def test_the_region_is_the_known_rectangle(self):
        regions = _t4s_regions()
        assert len(regions) == 1, [r.polygon.area for r in regions]
        assert regions[0].polygon.area == pytest.approx(
            _T4S_KNOWN_RECTANGLE_AREA_M2, rel=0.02)

    def test_the_decal_contributes_nothing(self):
        """The gate is ``config.MIN_SOLID_PART_THICKNESS_M`` — ONE
        notion, shared with the floor witness and the pit seed set.
        Without it the region would be the decal's 160,000 m²."""
        regions = _t4s_regions()
        assert regions[0].polygon.area < 160000.0
        assert "T4S/vor_decal.obj" not in regions[0].object_resources
        # ...and the decal is excluded because it is THIN, not because it
        # is deep: give it thickness and it joins.
        with_thickness = dict(_t4s_pattern())
        with_thickness["T4S/vor_decal.obj"] = _region_buried_box(
            -200.0, 200.0, -200.0, 200.0, -50.0, -40.0)
        thick_regions = _t4s_regions(with_thickness)
        assert thick_regions[0].polygon.area > 100000.0

    def test_the_region_carries_the_deepest_gated_solid(self):
        regions = _t4s_regions()
        assert regions[0].solid_minimum_y_m == pytest.approx(-7.0)

    def test_the_at_grade_hall_contributes_nothing(self):
        regions = _t4s_regions()
        assert "T4S/hall.obj" not in regions[0].object_resources

    def test_a_wall_only_member_cannot_kill_the_region(self):
        """REGRESSION (measured at LEMD 2026-08-26).  A resource of pure
        VERTICAL faces clips to polygons with no horizontal extent (0 m²).
        Unioned beside the real rings those made ``shapely.union_all``
        raise ``TopologyException: side location conflict``, the
        derivation caught it, and the WHOLE 27,857 m² T4S ring came back
        as "no regions" — in silence.  A zero-area member contributes
        nothing by construction, so the region must be unchanged."""
        geometry = dict(_t4s_pattern())
        walls = _GeometryBuilder()
        for x in (-30.0, -15.0, 0.0, 15.0, 30.0):
            walls.add_vertical_wall(x, -30.0, 30.0, -7.0, 0.0)
        geometry["T4S/wall_only.obj"] = walls.build()
        regions = _t4s_regions(geometry)
        assert len(regions) == 1, "a 0 m² member erased the region"
        assert regions[0].polygon.area == pytest.approx(
            _T4S_KNOWN_RECTANGLE_AREA_M2, rel=0.02)
        assert "T4S/wall_only.obj" not in regions[0].object_resources

    def test_the_union_helper_repairs_rather_than_returning_nothing(self):
        """The helper itself: an invalid bow-tie and a zero-area sliver
        beside a real square still union to the square."""
        from shapely.geometry import Polygon as _P
        square = _P([(0, 0), (10, 0), (10, 10), (0, 10)])
        bowtie = _P([(20, 0), (30, 10), (30, 0), (20, 10)])
        sliver = _P([(0, 0), (10, 0), (0, 0)])
        union = otf._union_all_repairing([square, bowtie, sliver])
        assert union is not None and union.is_valid
        assert union.area >= square.area
        assert otf._repaired_area_polygon(sliver) is None
        assert otf._union_all_repairing([]) is None

    def test_a_region_under_the_area_floor_is_dropped(self):
        """``TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2`` (1,000 m²) — scattered
        below-grade pockets are not a region."""
        geometry = {"T4S/pocket.obj": _region_wall(
            -10.0, 10.0, -10.0, 10.0, -7.0)}
        assert otf.below_grade_regions(
            [_placement("T4S/pocket.obj")], geometry) == []

    def test_a_pack_with_nothing_below_grade_derives_nothing(self):
        geometry = {"T4S/hall.obj": _at_grade_building_geometry()}
        assert otf.below_grade_regions(
            [_placement("T4S/hall.obj")], geometry) == []

    def test_the_classifier_carries_the_regions(self):
        """END TO END: the field is on ``ClassificationResult`` and the
        classifier fills it under the basin gate."""
        result = _classify(_t4s_pattern())
        assert len(result.below_grade_regions) == 1
        assert result.below_grade_regions[0].polygon.area == pytest.approx(
            _T4S_KNOWN_RECTANGLE_AREA_M2, rel=0.02)

    def test_an_old_result_reads_back_as_no_regions(self):
        """The field is DEFAULTED, so a hand-built or pre-version-21
        pickled result cannot raise — the cache VERSION is what retires a
        stale sidecar."""
        assert otf.ClassificationResult(
            tunnels=[], bridges=[]).below_grade_regions == []
        assert assembly._CLASSIFICATION_CACHE_VERSION >= 21


class TestBelowGradeRegionTriangleClip:
    """Spec §2.1 / §3 test 2.  TRIANGLES ARE CLIPPED, NEVER KEPT WHOLE:
    a long ramp panel must contribute only its below-threshold portion."""

    #: +1 m at x = −50 falling to −6 m at x = +50, 60 m wide.  It crosses
    #: −TRENCH_SPINE_MIN_DEPTH_M (−2.5) at exactly x = 0, so half of its
    #: 6,000 m² projection is below the plane.
    FULL_PROJECTION_M2 = 100.0 * 60.0
    BELOW_PORTION_M2 = 50.0 * 60.0

    def _ramp(self):
        builder = _GeometryBuilder()
        builder.add_sloped_rectangle(-50.0, 50.0, -30.0, 30.0, 1.0, -6.0)
        return {"T4S/ramp.obj": builder.build()}

    def test_only_the_below_threshold_portion_contributes(self):
        regions = otf.below_grade_regions(
            [_placement("T4S/ramp.obj")], self._ramp())
        assert len(regions) == 1
        assert regions[0].polygon.area == pytest.approx(
            self.BELOW_PORTION_M2, rel=0.02)
        assert regions[0].polygon.area < 0.75 * self.FULL_PROJECTION_M2

    def test_the_clip_crossing_point_is_the_law_threshold(self):
        """The crossing is at −``TRENCH_SPINE_MIN_DEPTH_M``, the constant
        the spec reuses — never a private number."""
        assert otf.TRENCH_SPINE_MIN_DEPTH_M == pytest.approx(2.5)
        minimum_x = otf.below_grade_regions(
            [_placement("T4S/ramp.obj")], self._ramp()
        )[0].polygon.bounds[0]
        # x = 0 is where the panel reaches −2.5; the morphological close
        # can only round the corner outward by AT_GRADE_FOOTPRINT_CLOSE_M.
        assert minimum_x == pytest.approx(
            0.0, abs=otf.AT_GRADE_FOOTPRINT_CLOSE_M + 0.1)

    def test_the_clip_primitive_returns_the_sub_polygon(self):
        """The primitive itself: one corner above the plane leaves a
        4-point ring, never the whole triangle."""
        ring = otf._clip_triangle_below_plane(
            ((0.0, 1.0, 0.0), (10.0, -6.0, 0.0), (10.0, -6.0, 10.0)), -2.5)
        assert ring is not None and len(ring) == 4
        assert all(x >= 5.0 - 1e-9 for x, _z in ring)
        assert otf._clip_triangle_below_plane(
            ((0.0, 1.0, 0.0), (10.0, 2.0, 0.0), (10.0, 3.0, 10.0)),
            -2.5) is None


def _region_at(polygon, *, solid_minimum_y_m=-7.087):
    return otf.BelowGradeRegion(
        polygon=polygon,
        frame_origin_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        solid_minimum_y_m=solid_minimum_y_m,
        object_resources=("T4S/wall_west.obj",),
    )


class TestBasinRecordRegionExtension:
    """Spec §2.2 / §3 test 3.  The record's FOOTPRINT is widened to the
    region; nothing else about the record moves."""

    #: The interface's own below-grade footprint (``_interface``'s
    #: default): 50 x 50 m about the anchor.
    RECORD_FOOTPRINT = Polygon([(-25, -25), (25, -25), (25, 25), (-25, 25)])
    #: A region CONTAINING it, the LEMD relation exactly (the record's
    #: 12,434 m² member inside the 27,612 m² authored ring).
    OVERLAPPING_REGION = Polygon(
        [(-60, -60), (60, -60), (60, 60), (-60, 60)])
    #: 400 m away — a region no basin record reaches.
    DISJOINT_REGION = Polygon(
        [(400, -60), (520, -60), (520, 60), (400, 60)])

    def _records(self, regions, **interface_kwargs):
        return assembly.basin_trench_structures(_Classification(
            ground_interfaces=[_interface(**interface_kwargs)],
            below_grade_regions=regions))

    def test_the_footprint_becomes_the_union(self):
        record = self._records([_region_at(self.OVERLAPPING_REGION)])[0]
        assert record.deck_footprint.area == pytest.approx(
            self.OVERLAPPING_REGION.area, rel=1e-6)
        assert record.solid_outline_footprint.area == pytest.approx(
            self.OVERLAPPING_REGION.area, rel=1e-6)

    def test_the_solid_minimum_takes_the_deeper_reading(self):
        record = self._records(
            [_region_at(self.OVERLAPPING_REGION, solid_minimum_y_m=-7.087)],
            floor_y_m=-4.0, solid_minimum_y_m=-4.2)[0]
        assert record.solid_minimum_y_m == pytest.approx(-7.087)
        # ...and never the SHALLOWER one.
        shallow = self._records(
            [_region_at(self.OVERLAPPING_REGION, solid_minimum_y_m=-3.0)],
            floor_y_m=-4.0, solid_minimum_y_m=-4.2)[0]
        assert shallow.solid_minimum_y_m == pytest.approx(-4.2)

    def test_membership_and_the_depth_bound_are_untouched(self):
        """Spec §2.2, explicit scope: ``object_resources`` drives the R4
        exclusions and the rim-flush grouping, and widening it is a
        separate docket."""
        plain = self._records([])[0]
        extended = self._records([_region_at(self.OVERLAPPING_REGION)])[0]
        assert extended.object_resources == plain.object_resources
        assert extended.cuts_pavement == plain.cuts_pavement
        assert extended.anchor_longitude_latitude == \
            plain.anchor_longitude_latitude
        assert extended.body_depth_m == pytest.approx(plain.body_depth_m)

    def test_a_disjoint_region_extends_nothing_and_is_REPORTED(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        record = self._records([_region_at(self.DISJOINT_REGION)])[0]
        assert record.deck_footprint.area == pytest.approx(
            self.RECORD_FOOTPRINT.area, rel=1e-6)
        out = capsys.readouterr().out
        assert "UNMATCHED BELOW-GRADE REGION" in out, \
            "an unfounded region was passed over SILENTLY"

    def test_the_seating_predictor_sees_the_SAME_widened_body(self):
        """ONE producer, both consumers: the emitter and the rim-flush
        seating predictor read ``basin_trench_structures``, so they
        cannot disagree about where the body is."""
        classification = _Classification(
            ground_interfaces=[_interface()],
            below_grade_regions=[_region_at(self.OVERLAPPING_REGION)])
        facility = assembly.basin_rim_flush_facilities(classification)[0]
        ring = facility.body_rings_longitude_latitude[0]
        longitudes = [point[0] for point in ring]
        east_metres = max(
            abs(longitude - ANCHOR_LONGITUDE) for longitude in longitudes
        ) * 111120.0 * math.cos(math.radians(ANCHOR_LATITUDE))
        assert east_metres > 50.0, "the facility kept the narrow body"


class TestBasinRegionFloorKey:
    """Spec §2.3 / §3 test 4.  Owner 2026-08-26: the floor keys on the
    facility's deepest genuine solid WITH the tunnel margins restored,
    for open pits as for bores.  Both arms asserted through the ONE law
    function — never a hand-typed constant (ruling R1)."""

    #: LEMD, measured 2026-08-26: R_est, the family's deepest genuine
    #: solid, and Amendment 3's deck-face body depth.
    REST_M = 593.0288
    SOLID_WITNESS_Y = -7.087
    DECK_FACE_Y = -7.0159

    def test_the_open_pit_floor_is_r_est_plus_solid_min_less_the_margins(
            self):
        expected = (
            self.REST_M + self.SOLID_WITNESS_Y
            - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
            - config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)
        assert grade_law.basin_trench_floor_elevation_m(
            self.REST_M, self.SOLID_WITNESS_Y,
            bore_class=False) == pytest.approx(expected)
        assert grade_law.basin_trench_floor_elevation_m(
            self.REST_M, self.SOLID_WITNESS_Y) == pytest.approx(expected)

    def test_the_key_reader_takes_the_solid_witness_for_an_open_pit(self):
        record = assembly.basin_trench_structures(_Classification(
            ground_interfaces=[_interface(
                floor_y_m=self.DECK_FACE_Y,
                solid_minimum_y_m=self.SOLID_WITNESS_Y)]))[0]
        assert assembly.basin_facility_deck_reference_y(
            record, open_pit=True) == (
                pytest.approx(self.SOLID_WITNESS_Y), None,
                assembly.BASIN_FLOOR_KEY_SOLID_WITNESS)

    def test_the_gate_reproduces_the_amendment_3_value(self, monkeypatch):
        """RETIRED, KEPT, GATED (the keep-work rule):
        ``O4_BASIN_OPEN_PIT_DECK_KEY=1`` restores the deck-face key AND
        its zero margins — they are one law read twice, so one gate."""
        assert config.BASIN_OPEN_PIT_DECK_KEY is False
        monkeypatch.setattr(config, "BASIN_OPEN_PIT_DECK_KEY", True)
        record = assembly.basin_trench_structures(_Classification(
            ground_interfaces=[_interface(
                floor_y_m=self.DECK_FACE_Y,
                solid_minimum_y_m=self.SOLID_WITNESS_Y)]))[0]
        deck_reference_y, _discarded, key_source = (
            assembly.basin_facility_deck_reference_y(record, open_pit=True))
        assert deck_reference_y == pytest.approx(self.DECK_FACE_Y)
        assert key_source == assembly.BASIN_FLOOR_KEY_DECK_FACE
        assert grade_law.basin_trench_floor_elevation_m(
            self.REST_M, deck_reference_y,
            bore_class=False) == pytest.approx(
                self.REST_M + self.DECK_FACE_Y)

    def test_the_disagreement_gate_is_unchanged(self):
        """Spec §2.3: the §2.2 gate stays — an absurd witness that
        survives the thickness gate is still discarded."""
        record = _tunnel_record(body_depth_m=7.016)
        object.__setattr__(record, "solid_minimum_y_m", -50.0)
        assert assembly.basin_facility_deck_reference_y(
            record, open_pit=True)[0] == pytest.approx(-7.016)


class TestBasinRegionFootprintGate:
    """Spec §2.4 / §3 test 5.  ``O4_BASIN_REGION_FOOTPRINT=0`` → the
    records are what they were before this round, object for object."""

    def _records(self, regions):
        return assembly.basin_trench_structures(_Classification(
            ground_interfaces=[_interface()], below_grade_regions=regions))

    def test_the_gate_defaults_on(self):
        assert config.BASIN_REGION_FOOTPRINT is True

    def test_gate_off_leaves_the_footprint_byte_identical(self, monkeypatch):
        region = _region_at(
            TestBasinRecordRegionExtension.OVERLAPPING_REGION)
        control = self._records([])[0]
        monkeypatch.setattr(config, "BASIN_REGION_FOOTPRINT", False)
        gated = self._records([region])[0]
        assert gated.deck_footprint.equals(control.deck_footprint)
        assert gated.solid_outline_footprint.equals(
            control.solid_outline_footprint)
        assert gated.solid_minimum_y_m == control.solid_minimum_y_m

    def test_gate_off_derives_no_region_at_all(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_REGION_FOOTPRINT", False)
        assert _classify(_t4s_pattern()).below_grade_regions == []

    def test_the_gate_salts_the_classification_sidecar(
            self, tmp_path, monkeypatch):
        """A gate flip must MISS the cache — the classification it
        changes is the cut shape itself."""
        dsf_path = tmp_path / "+40-004.dsf"
        dsf_path.write_text("x")
        pack_root = tmp_path / "pack"
        pack_root.mkdir()
        monkeypatch.setattr(
            assembly.dsf_reader, "airport_mod_cache_dir",
            lambda root: str(tmp_path))
        monkeypatch.setattr(config, "BASIN_REGION_FOOTPRINT", True)
        _path, on_digest = assembly._classification_sidecar(
            str(dsf_path), str(pack_root), None)
        monkeypatch.setattr(config, "BASIN_REGION_FOOTPRINT", False)
        _path, off_digest = assembly._classification_sidecar(
            str(dsf_path), str(pack_root), None)
        assert on_digest and off_digest and on_digest != off_digest


# ---------------------------------------------------------------------------
# BASIN FOUNDING FROM UNMATCHED REGIONS (spec docs/specs/
# basin-region-founding-spec.md, follow-up docket A of the owner's
# 2026-08-26 LEMD T4S rulings)
# ---------------------------------------------------------------------------

#: The founding fixture in miniature — the LEMD defect class MINUS the
#: luck: below-grade walls tiling a KNOWN 60 x 60 m rectangle and NO
#: interface record anywhere (at LEMD one member happened to escape the
#: 358-object mega-pool as its own BOWL_UNDER_DECK; a pack whose
#: below-grade members all pool into one FLAT_CONFIRMED mega-structure
#: gets no record at all, and before founding the pit was never cut).
_FOUNDING_KNOWN_RECTANGLE_AREA_M2 = 60.0 * 60.0

#: A contributor of ~2 m² — the tight-list probe of spec §2.2.  Well
#: under both 5 % of the region (180 m²) and the 100 m² absolute floor.
_FOUNDING_SPECK_AREA_M2 = 1.4 * 1.4


def _founding_pattern(floor_y: float = -6.0, *, deck_over: bool = False):
    geometry = {
        "T4S/found_wall_west.obj": _region_wall(
            -30.0, 0.0, -30.0, 30.0, floor_y),
        "T4S/found_wall_east.obj": _region_wall(
            0.0, 30.0, -30.0, 30.0, floor_y),
        # The 2 m² speck: a genuine below-grade contributor that must NOT
        # reach the founded record's membership.
        "T4S/found_speck.obj": _region_buried_box(
            0.0, 1.4, 0.0, 1.4, floor_y, floor_y + 1.5),
    }
    if deck_over:
        # A solid deck spanning the whole region, +2 .. +12 m — the R13
        # openness refusal: something of the pack's own stands over it.
        geometry["T4S/found_deck.obj"] = _region_buried_box(
            -30.0, 30.0, -30.0, 30.0, 2.0, 12.0)
    return geometry


def _founding_regions(geometry=None, *, ground_interfaces=(), **kwargs):
    """The fixture's regions WITH the openness reading filled in.

    Amendment 1 (2026-08-27): the coverage fraction is lazy — it is
    taken only for regions that intersect NO ground interface's own
    below-grade footprint.  The founding fixture's whole premise is a
    pack with no interface record over its pit, so with no interfaces
    every region is un-prematched and every one gets a real fraction —
    exactly what production does for such a pack.
    """
    geometry = _founding_pattern(**kwargs) if geometry is None else geometry
    placements = [_placement(resource) for resource in geometry]
    return otf.regions_with_lazy_above_grade_coverage(
        otf.below_grade_regions(placements, geometry),
        ground_interfaces, placements, geometry)


def _founding_records(regions, *, ground_interfaces=(), tunnels=(),
                      bridges=()):
    classification = _Classification(
        tunnels=tunnels,
        ground_interfaces=ground_interfaces,
        below_grade_regions=regions)
    classification.bridges = list(bridges)
    return assembly.basin_trench_structures(classification)


class TestBasinFoundingFromRegion:
    """Spec §2.1-§2.2 / §3 test 1.  A deep OPEN region that matches no
    record FOUNDS one — otherwise the pit is derived, logged and never
    cut, which is the LEMD defect class minus the luck."""

    def test_one_record_is_founded_over_the_known_rectangle(self):
        records = _founding_records(_founding_regions())
        assert len(records) == 1
        assert records[0].deck_footprint.area == pytest.approx(
            _FOUNDING_KNOWN_RECTANGLE_AREA_M2, rel=0.05)
        assert records[0].solid_outline_footprint.area == pytest.approx(
            records[0].deck_footprint.area, rel=1e-9)

    def test_the_record_is_a_basin_that_cuts_pavement(self):
        record = _founding_records(_founding_regions())[0]
        assert record.terrain_feature == otf.TERRAIN_FEATURE_BASIN
        assert record.cuts_pavement is True
        assert record.placement_kind == "OBJECT"
        assert record.heading_degrees == 0.0
        assert record.above_ground_offset_m == 0.0
        assert record.roof_footprint is None
        assert record.mouth_polygons == []
        assert record.mouth_depth_samples == []

    def test_the_floor_is_the_law_over_the_regions_own_depth(self):
        """THROUGH THE ONE LAW FUNCTION (ruling R1): rim + (−6) − the two
        restored tunnel margins.  The record's depth bound and its solid
        witness are ONE reading, so the §2.2 disagreement gate is vacuous
        by construction."""
        record = _founding_records(_founding_regions())[0]
        assert record.solid_minimum_y_m == pytest.approx(-6.0)
        assert record.body_depth_m == pytest.approx(6.0)
        deck_reference_y, discarded, _key = (
            assembly.basin_facility_deck_reference_y(record, open_pit=True))
        assert deck_reference_y == pytest.approx(-6.0)
        assert discarded is None
        rim = 100.0
        assert grade_law.basin_trench_floor_elevation_m(
            rim, deck_reference_y) == pytest.approx(
                rim - 6.0
                - config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
                - config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)
        assert _open_pit_floor(rim, 6.0) == pytest.approx(rim - 7.5)

    def test_the_contributor_list_is_TIGHT(self):
        """Spec §2.2: this field feeds ``basin_rim_flush_facilities``
        grouping and hence SEATING — sweeping a shared-anchor family's
        at-grade members in would be the LSGG y-bake starvation class.
        The 2 m² speck is a real contributor and is still absent."""
        regions = _founding_regions()
        areas = dict(regions[0].contributor_area_m2_by_resource)
        assert areas["T4S/found_speck.obj"] == pytest.approx(
            _FOUNDING_SPECK_AREA_M2, rel=0.05)
        record = _founding_records(regions)[0]
        assert record.object_resources == [
            "T4S/found_wall_east.obj", "T4S/found_wall_west.obj"]
        assert "T4S/found_speck.obj" not in record.object_resources
        assert (
            assembly.FOUNDED_BASIN_CONTRIBUTOR_AREA_FRACTION == 0.05
            and assembly.FOUNDED_BASIN_CONTRIBUTOR_AREA_M2 == 100.0)

    def test_the_anchor_is_INSIDE_the_region(self):
        """A representative point, never the centroid: the anchor is the
        facility grouping key and the point a draped member seats on."""
        from shapely.geometry import Point
        region = _founding_regions()[0]
        record = _founding_records([region])[0]
        longitude, latitude = record.anchor_longitude_latitude
        local_x, local_z = assembly.obj8_reader.lonlat_to_local_offset(
            region.frame_origin_longitude_latitude[1],
            region.frame_origin_longitude_latitude[0],
            0.0, latitude, longitude)
        assert region.polygon.contains(Point(local_x, local_z))

    def test_the_founding_is_reported_by_name(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        _founding_records(_founding_regions())
        out = capsys.readouterr().out
        assert "FOUNDED BASIN FROM REGION" in out

    def test_the_seating_predictor_sees_the_founded_facility(self):
        """ONE producer, both consumers — a founded record reaches the
        rim-flush seating predictor exactly like an interface-derived
        one, because there is only one producer."""
        classification = _Classification(
            below_grade_regions=_founding_regions())
        facilities = assembly.basin_rim_flush_facilities(classification)
        assert len(facilities) == 1
        assert facilities[0].solid_minimum_y_m == pytest.approx(-6.0)

    def test_founding_adds_NO_ruling_R4_exclusions(self, monkeypatch):
        """Spec §2.3, deliberate boundary: exclusions stay
        interface-driven.  A founded record changes TERRAIN, not the
        y-bake population (seating interplay is docket B).

        Two arms.  Founding a record leaves the classification's own
        exclusion feed exactly as it found it; and the R4 feed the
        classifier builds does not move when the founding gate flips."""
        classification = _Classification(
            below_grade_regions=_founding_regions())
        assert assembly.basin_trench_structures(classification)
        assert classification.exclusions == []

        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", True)
        with_founding = _classify(_founding_pattern()).exclusions
        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", False)
        without_founding = _classify(_founding_pattern()).exclusions
        assert with_founding == without_founding


class TestBasinFoundingDepthRefusal:
    """Spec §3 test 2.  Founding is inference without an interface to key
    on, so the 2.5-3.0 m band stays EXTENSION-ONLY evidence."""

    def test_a_shallow_region_is_not_founded(self):
        regions = _founding_regions(floor_y=-2.8)
        assert regions, "the fixture no longer derives a region at all"
        assert regions[0].solid_minimum_y_m == pytest.approx(-2.8)
        assert _founding_records(regions) == []

    def test_the_refusal_is_logged_against_the_depth_floor(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        _founding_records(_founding_regions(floor_y=-2.8))
        out = capsys.readouterr().out
        assert "UNMATCHED BELOW-GRADE REGION" in out
        assert "SHALLOWER" in out
        assert "FOUNDED BASIN FROM REGION" not in out

    def test_the_floor_is_the_shared_constant(self):
        assert otf.BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M == pytest.approx(3.0)


class TestBasinFoundingOpennessRefusal:
    """Spec §3 test 3 / ruling R13.  A COVERED region is a bore/tunnel
    candidate, not an open pit — and it stays attributable."""

    def test_a_covered_region_is_not_founded(self):
        regions = _founding_regions(deck_over=True)
        assert regions[0].above_grade_area_fraction == pytest.approx(
            1.0, rel=0.05)
        assert _founding_records(regions) == []

    def test_the_refusal_names_the_coverage_fraction(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        regions = _founding_regions(deck_over=True)
        _founding_records(regions)
        out = capsys.readouterr().out
        assert "UNMATCHED BELOW-GRADE REGION" in out
        assert "COVERED" in out
        assert f"{regions[0].above_grade_area_fraction:.3f}" in out

    def test_an_OPEN_region_reads_zero_coverage(self):
        """The instrument itself: the fixture's own walls stop at grade,
        so nothing of the pack stands over the pit."""
        assert _founding_regions()[0].above_grade_area_fraction == \
            pytest.approx(0.0, abs=1e-9)

    def test_the_cap_is_the_shared_open_pit_constant(self):
        assert otf.BOWL_MAX_ABOVE_GRADE_AREA_FRACTION == pytest.approx(0.02)

    def test_the_clip_is_ABOVE_the_ground_band(self):
        """A deck INSIDE the ±1 m ground band is not standing over
        anything — the plane is +GROUND_CONTACT_BAND_HALF_WIDTH_M, the
        module's ONE spelling of "clear of the ground"."""
        geometry = _founding_pattern()
        geometry["T4S/found_kerb.obj"] = _region_buried_box(
            -30.0, 30.0, -30.0, 30.0, -0.4, 0.4)
        assert _founding_regions(geometry)[0].above_grade_area_fraction == \
            pytest.approx(0.0, abs=1e-9)
        ring = otf._clip_triangle_above_plane(
            ((0.0, -6.0, 0.0), (10.0, 4.0, 0.0), (10.0, 4.0, 10.0)), 1.0)
        assert ring is not None and len(ring) == 4
        assert otf._clip_triangle_above_plane(
            ((0.0, -6.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.5, 10.0)),
            1.0) is None


class TestBasinFoundingNoDoubleFound:
    """Spec §3 test 4.  A region that reaches an existing record is that
    record's business: EXTENSION only, exactly as the landed round."""

    def test_a_region_over_a_basin_record_extends_and_founds_nothing(self):
        region = _region_at(
            TestBasinRecordRegionExtension.OVERLAPPING_REGION,
            solid_minimum_y_m=-7.087)
        object.__setattr__(region, "above_grade_area_fraction", 0.0)
        records = _founding_records(
            [region], ground_interfaces=[_interface()])
        assert len(records) == 1
        assert records[0].object_resources == [
            "Buildings/Drainage/basin.obj"]
        assert records[0].deck_footprint.area == pytest.approx(
            TestBasinRecordRegionExtension.OVERLAPPING_REGION.area, rel=1e-6)

    def test_a_region_under_a_feature_A_TUNNEL_is_not_founded(self, capsys):
        """A region under a tunnel record is that structure's business —
        never founded twice (spec §2.1)."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        region = _founding_regions()[0]
        tunnel = otf.TunnelStructure(
            object_resources=["Tunnels/bore.obj"],
            anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            frame_origin_longitude_latitude=(
                ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            heading_degrees=0.0,
            placement_kind="OBJECT",
            above_ground_offset_m=0.0,
            roof_footprint=None,
            deck_footprint=Polygon(
                [(-40, -40), (40, -40), (40, 40), (-40, 40)]),
            mouth_polygons=[],
            mouth_depth_samples=[],
            body_depth_m=6.0,
        )
        assert _founding_records([region], tunnels=[tunnel]) == []
        assert "feature-A TUNNEL" in capsys.readouterr().out

    def test_a_region_under_a_BRIDGE_record_is_not_founded(self, capsys):
        """Spec §2.3: a bridge deck's under-space is the bridge
        contract's — logged, never founded."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        region = _founding_regions()[0]

        class _Bridge:
            frame_origin_longitude_latitude = (
                ANCHOR_LONGITUDE, ANCHOR_LATITUDE)
            deck_polygon = Polygon(
                [(-40, -40), (40, -40), (40, 40), (-40, 40)])

        assert _founding_records([region], bridges=[_Bridge()]) == []
        assert "BRIDGE record" in capsys.readouterr().out


class TestBasinFoundingStaleSidecarRefusal:
    """Spec §3 test 5.  UNKNOWN openness REFUSES founding and names the
    stale sidecar — never a silent guess."""

    def test_a_region_without_the_field_founds_nothing(self):
        region = _region_at(
            TestBasinRecordRegionExtension.DISJOINT_REGION,
            solid_minimum_y_m=-7.087)
        assert region.above_grade_area_fraction is None
        assert _founding_records([region]) == []

    def test_the_stale_sidecar_line_fires(self, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        _founding_records([_region_at(
            TestBasinRecordRegionExtension.DISJOINT_REGION,
            solid_minimum_y_m=-7.087)])
        out = capsys.readouterr().out
        assert "STALE SIDECAR" in out
        assert "UNKNOWN" in out

    def test_the_cache_version_retires_pre_coverage_pickles(self):
        # 22 is the last version written WITHOUT the coverage fraction.
        assert assembly._CLASSIFICATION_CACHE_VERSION >= 23


class TestBasinFoundingGate:
    """Spec §2.4 / §3 test 6.  ``O4_BASIN_REGION_FOUNDING=0`` → nothing
    is founded and extension is exactly the landed round."""

    def test_the_gate_defaults_on(self):
        assert config.BASIN_REGION_FOUNDING is True

    def test_gate_off_founds_nothing(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", False)
        assert _founding_records(_founding_regions()) == []

    def test_gate_off_leaves_EXTENSION_untouched(self, monkeypatch):
        region = _region_at(
            TestBasinRecordRegionExtension.OVERLAPPING_REGION)
        object.__setattr__(region, "above_grade_area_fraction", 0.0)
        control = _founding_records(
            [region], ground_interfaces=[_interface()])[0]
        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", False)
        gated = _founding_records(
            [region], ground_interfaces=[_interface()])[0]
        assert gated.deck_footprint.equals(control.deck_footprint)
        assert gated.solid_minimum_y_m == control.solid_minimum_y_m
        assert gated.object_resources == control.object_resources

    def test_gate_off_still_REPORTS_the_region(self, monkeypatch, capsys):
        import O4_UI_Utils as UI
        UI.verbosity = 1
        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", False)
        _founding_records(_founding_regions())
        assert "UNMATCHED BELOW-GRADE REGION" in capsys.readouterr().out

    def test_the_gate_salts_the_classification_sidecar(
            self, tmp_path, monkeypatch):
        dsf_path = tmp_path / "+40-004.dsf"
        dsf_path.write_text("x")
        pack_root = tmp_path / "pack"
        pack_root.mkdir()
        monkeypatch.setattr(
            assembly.dsf_reader, "airport_mod_cache_dir",
            lambda root: str(tmp_path))
        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", True)
        _path, on_digest = assembly._classification_sidecar(
            str(dsf_path), str(pack_root), None)
        monkeypatch.setattr(config, "BASIN_REGION_FOUNDING", False)
        _path, off_digest = assembly._classification_sidecar(
            str(dsf_path), str(pack_root), None)
        assert on_digest and off_digest and on_digest != off_digest


class TestBasinFoundingLazyCoverage:
    """Spec §2.1 Amendment 1 (Fable 2026-08-27) — THE OPENNESS READING IS
    LAZY, BY PREMATCH.

    Coverage gates founding, and founding can only reach a region that
    matches NO record.  A region already intersecting a ground
    interface's own below-grade footprint will be EXTENDED onto that
    interface's record in assembly, so its coverage is a number nobody
    reads — and it is not free: 33.4 s CPU at LEMD eagerly (12.3 s with
    the bbox pre-filter) against 0.65 s for the region derivation."""

    def test_a_PREMATCHED_region_carries_no_reading(self):
        """The classifier's own fixture: the walls DO form a carved-basin
        interface, so the region is prematched and the pass is skipped."""
        result = _classify(_founding_pattern())
        assert result.below_grade_regions, "fixture derives no region"
        assert any(
            otf.is_carved_basin_interface(interface)
            for interface in result.ground_interfaces
        ), "fixture no longer produces an interface to prematch against"
        assert result.below_grade_regions[0].above_grade_area_fraction \
            is None

    def test_an_UNMATCHED_region_still_gets_a_computed_fraction(self):
        """With no interface in hand there is nothing to prematch to, so
        the reading IS taken — this is the founding path."""
        placements = [_placement(r) for r in _founding_pattern()]
        geometry = _founding_pattern()
        regions = otf.regions_with_lazy_above_grade_coverage(
            otf.below_grade_regions(placements, geometry),
            (), placements, geometry)
        assert regions[0].above_grade_area_fraction == pytest.approx(
            0.0, abs=1e-9)
        covered = _founding_regions(deck_over=True)
        assert covered[0].above_grade_area_fraction == pytest.approx(
            1.0, rel=0.05)

    def test_the_prematched_region_REFUSES_founding_out_loud(self, capsys):
        """The corner Amendment 1 names: prematched here, record dropped
        upstream.  ``None`` is NOT COMPUTED, so founding refuses and says
        so — never a fabricated openness, never a silent skip."""
        import O4_UI_Utils as UI
        UI.verbosity = 1
        region = _classify(_founding_pattern()).below_grade_regions[0]
        assert region.above_grade_area_fraction is None
        assert _founding_records([region]) == []
        out = capsys.readouterr().out
        assert "UNMATCHED BELOW-GRADE REGION" in out
        assert "NOT COMPUTED" in out
        assert "PREMATCHED" in out and "STALE SIDECAR" in out

    def test_the_lazy_pass_is_ONE_projection_with_the_assembly(self):
        """The prematch test and the record-extension test read the same
        converter — ``_region_polygon_in_frame`` delegates to it."""
        assert assembly._region_polygon_in_frame.__module__ == \
            "auto_patch.object_terrain_assembly"
        region = _region_at(
            TestBasinRecordRegionExtension.OVERLAPPING_REGION)
        through_assembly = assembly._region_polygon_in_frame(
            region, (ANCHOR_LONGITUDE, ANCHOR_LATITUDE))
        through_features = otf.region_polygon_in_frame(
            region, (ANCHOR_LONGITUDE, ANCHOR_LATITUDE))
        assert through_assembly.equals(through_features)

    def test_nothing_un_prematched_never_enters_the_machinery(
            self, monkeypatch):
        """When every region is prematched the above-grade union is never
        built — that is the whole saving."""
        calls = []
        monkeypatch.setattr(
            otf, "_above_grade_union_in_frame",
            lambda *a, **k: calls.append(1))
        placements = [_placement(r) for r in _founding_pattern()]
        geometry = _founding_pattern()
        regions = otf.below_grade_regions(placements, geometry)
        interfaces = [_interface(footprint=Polygon(
            [(-30, -30), (30, -30), (30, 30), (-30, 30)]))]
        otf.regions_with_lazy_above_grade_coverage(
            regions, interfaces, placements, geometry)
        assert calls == []
        otf.regions_with_lazy_above_grade_coverage(
            regions, (), placements, geometry)
        assert calls == [1]
