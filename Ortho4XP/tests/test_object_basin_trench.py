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

from auto_patch import config  # noqa: E402
from auto_patch import object_anchor  # noqa: E402
from auto_patch import object_footprints  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
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


def _check_grade():
    """The HARNESS LIBRARY, imported the way the grade tests import it.

    ``tools/`` is not on ``sys.path`` for every test session, and a twin
    that asserts the census honours an emitter's declaration has to ask
    the census itself — never a local re-spelling of its rule."""
    import sys as _sys
    from pathlib import Path as _Path
    tools = str(_Path(__file__).resolve().parent.parent / "tools")
    if tools not in _sys.path:
        _sys.path.insert(0, tools)
    import check_grade
    return check_grade


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


# ---------------------------------------------------------------------------
# birth through the shared feature-A emitter
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ruling R13 — the open pit takes the pavement with it
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# LEMD ROUND 2 §B — the trench is SENIOR TO PAVEMENT at its rim
# (docs/specs/lemd-rim-and-stations-spec.md §B; owner RULINGS 2026-08-28
# item 2, extending the 2026-08-26 trench-seniority ruling from pads to
# pavement)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# LEMD ROUND 2 §C — the rim seats at the SOLVED NEIGHBOUR, DEM LAST
# (docs/specs/lemd-rim-and-stations-spec.md §C; owner RULINGS 2026-08-28
# item 3 + DEM-LAST 2026-08-25; the basin-rim-flush spec's own §1(2))
# ---------------------------------------------------------------------------


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


class TestBasinFloorLaw:
    """Spec section 2.1 items 2 and 3 — ``R_est``, the TRUE deepest solid
    and the seat-estimate margin, all in ONE law function that the
    emitter and any validator import (ruling R1)."""


    def test_the_margin_default_is_the_specced_one(self):
        assert config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M == pytest.approx(1.0)


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


# ---------------------------------------------------------------------------
# 2.1e E1 — no basin member is baked, by construction
# ---------------------------------------------------------------------------


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
    mesh_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


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
        for line in path.read_text(encoding="utf-8").splitlines()
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
            path.write_text(_obj8_text(geometry[resource]), encoding="utf-8", newline="")
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


    # -- item 6: scope ----------------------------------------------------


    # -- item 7: clearance ------------------------------------------------


    # -- the measure-only mode (reseat-threshold spec section 2.3) --------


    # -- item 8: idempotence ---------------------------------------------


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


    # -- the records come from the classifier, never a re-derivation -----


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


class TestBasinFloorDisagreementGate:
    """§2.2.  Two instruments described one bottom and the 43 m
    disagreement between them rode the same log line unchecked
    (``body_depth_m 7.02`` beside ``floor_m 545.52``)."""

    def test_the_threshold_is_the_specced_one(self):
        assert config.BASIN_FLOOR_DISAGREEMENT_M == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# A PAD INSIDE A BASIN SITS AT THE BASIN FLOOR (owner RULINGS 2026-08-25f)
# spec docs/specs/basin-pad-floor-seating-spec.md §1 + §2
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# THE RAMP REACH COMPLETION (spec
# docs/specs/lemd-basin-trench-ramp-extension-spec.md; owner sim read of
# 1.0.264: "the terrain is poking through the ramp")
# ---------------------------------------------------------------------------

#: A pit and its entrance ramp, in the geometry the defect is made of.
#: The pit is the 60 x 60 m T4S rectangle at −7 m.  The ramp runs 60 m
#: EAST of it, rising 7.5 m from the pit floor (−7.0) to just over grade
#: (+0.5), so it crosses −``TRENCH_SPINE_MIN_DEPTH_M`` at x = 66 and the
#: TOP of the ground-contact band nowhere at all — it is below +1 m over
#: its whole run.  The DEPTH ADMISSION therefore stops the ring at x=66
#: and leaves 24 m of authored ramp with terrain standing through it,
#: which is the owner's LEMD read in miniature.
_RAMP_PIT_EAST_EDGE_X = 30.0
_RAMP_TOP_X = 90.0
_RAMP_DEPTH_CROSSING_X = 66.0


def _ramp_pit_pattern():
    ramp = _GeometryBuilder()
    ramp.add_sloped_rectangle(
        _RAMP_PIT_EAST_EDGE_X, _RAMP_TOP_X, -15.0, 15.0, -7.0, 0.5)
    return {
        "T4S/pit.obj": _region_wall(-30.0, 30.0, -30.0, 30.0, -7.0),
        "T4S/ramp.obj": ramp.build(),
    }


def _completed(geometry, regions=None):
    placements = [_placement(resource) for resource in geometry]
    if regions is None:
        regions = otf.below_grade_regions(placements, geometry)
    return regions, otf.regions_completed_to_ramp_reach(
        regions, placements, geometry)


class TestBasinRegionRampReach:
    """The COMPLETION pass: an admitted region is followed up its own
    entrance ramp to the ground-contact band.

    Admission asks "is this a trench?" at −2.5 m and is unchanged.  This
    asks the different question "where does this trench's own shell stop
    being below grade?", and only for a region that has already been
    admitted.

    The gate SHIPS OFF (it moves the committed LEMD group seat by
    0.81 m — see ``config.BASIN_REGION_RAMP_REACH``), so the arm under
    test here is turned on explicitly, exactly as a lane turns it on."""

    @pytest.fixture(autouse=True)
    def _the_arm_under_test(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_REGION_RAMP_REACH", True)

    def test_the_gate_ships_off_pending_the_owner_ruling(self):
        """The HELD state is itself law: a default-ON build would move
        G=596.682, which the spec calls a STOP, not a side effect.

        Read from the SOURCE, never by reloading the module — a config
        reload mid-suite is the hazard this repo redirects around."""
        import inspect
        import re

        source = inspect.getsource(config)
        default = re.search(
            r'_os\.environ\.get\(\s*"O4_BASIN_REGION_RAMP_REACH",\s*'
            r'"(\d)"\s*\)',
            source,
        )
        assert default is not None, "the gate lost its environment read"
        assert default.group(1) == "0", (
            "the ramp-reach gate must ship OFF until the owner rules on "
            "the 0.81 m group-seat move it carries")

    def test_the_depth_admission_stops_part_way_up_the_ramp(self):
        """THE DEFECT, stated as a measurement: without the completion
        the ring ends at the −2.5 m crossing and 24 m of authored ramp
        is left with terrain standing through it."""
        regions, _completed_regions = _completed(_ramp_pit_pattern())
        assert len(regions) == 1
        assert regions[0].polygon.bounds[2] == pytest.approx(
            _RAMP_DEPTH_CROSSING_X, abs=otf.AT_GRADE_FOOTPRINT_CLOSE_M + 0.1)

    def test_the_completion_reaches_the_top_of_the_ramp(self):
        regions, done = _completed(_ramp_pit_pattern())
        assert done[0].polygon.bounds[2] == pytest.approx(
            _RAMP_TOP_X, abs=otf.AT_GRADE_FOOTPRINT_CLOSE_M + 0.1)
        assert done[0].polygon.area > regions[0].polygon.area

    def test_the_plane_is_the_ground_contact_band(self):
        """One band, read from both sides: the openness reading clips
        ABOVE it, the completion clips BELOW it.  Aliased, never
        re-numbered."""
        assert otf.REGION_RAMP_REACH_PLANE_Y_M == (
            otf.GROUND_CONTACT_BAND_HALF_WIDTH_M)

    def test_the_gate_off_returns_the_admitted_rings_untouched(
        self, monkeypatch
    ):
        """``O4_BASIN_REGION_RAMP_REACH=0`` — the same rings, not merely
        equal ones, so a gate-off build cannot differ by a rounding."""
        assert config.BASIN_REGION_RAMP_REACH in (True, False)
        monkeypatch.setattr(config, "BASIN_REGION_RAMP_REACH", False)
        regions, done = _completed(_ramp_pit_pattern())
        assert [region.polygon for region in done] == [
            region.polygon for region in regions]

    def test_admission_membership_and_openness_are_untouched(self):
        """SCOPE.  Only ``polygon`` grows.  Depth, the contributor list
        and their clipped areas are all measured on the ADMITTED ring —
        which is what keeps founding admitting exactly what it did."""
        regions, done = _completed(_ramp_pit_pattern())
        before, after = regions[0], done[0]
        assert after.object_resources == before.object_resources
        assert after.solid_minimum_y_m == before.solid_minimum_y_m
        assert (after.contributor_area_m2_by_resource
                == before.contributor_area_m2_by_resource)
        assert (after.above_grade_area_fraction
                == before.above_grade_area_fraction)
        assert (after.frame_origin_longitude_latitude
                == before.frame_origin_longitude_latitude)

    def test_a_pit_with_no_ramp_does_not_grow(self):
        """The completion is not a dilation: a shell that is already
        vertical at its rim reaches the band nowhere new."""
        regions, done = _completed(_t4s_pattern())
        assert done[0].polygon.area == pytest.approx(
            regions[0].polygon.area, rel=1e-3)

    def test_a_non_contributing_resource_is_never_swept_in(self):
        """The completion grows into the region's OWN contributors only.
        A shallow neighbour that never reached the depth admission is
        not a contributor, so it stays outside however close it is —
        this is the scope guard AND the perf guard."""
        geometry = dict(_ramp_pit_pattern())
        shallow = _GeometryBuilder()
        # A 60 x 30 m slab at −1.2 m, its own vertical extent from a
        # skirt, butted against the ramp's far end.  Never below −2.5,
        # so never a contributor.
        shallow.add_horizontal_rectangle(
            _RAMP_TOP_X, _RAMP_TOP_X + 60.0, -15.0, 15.0, -1.2)
        shallow.add_vertical_wall(
            _RAMP_TOP_X + 60.0, -15.0, 15.0, -1.2, 0.5)
        geometry["T4S/shallow_apron.obj"] = shallow.build()
        regions, done = _completed(geometry)
        assert "T4S/shallow_apron.obj" not in regions[0].object_resources
        assert done[0].polygon.bounds[2] == pytest.approx(
            _RAMP_TOP_X, abs=otf.AT_GRADE_FOOTPRINT_CLOSE_M + 0.1)

    def test_two_completions_that_would_overlap_are_both_refused(self):
        """ONE BODY, ONE CUT.  Two pits whose ramps run into each other
        are admitted as two regions; completing both would cut the same
        ground twice, so both completions stand down and the admitted
        rings survive."""
        west = _GeometryBuilder()
        west.add_sloped_rectangle(-40.0, 20.0, -15.0, 15.0, -7.0, 0.5)
        east = _GeometryBuilder()
        east.add_sloped_rectangle(40.0, -20.0, -15.0, 15.0, -7.0, 0.5)
        geometry = {
            "T4S/pit_west.obj": _region_wall(
                -100.0, -40.0, -30.0, 30.0, -7.0),
            "T4S/pit_east.obj": _region_wall(
                40.0, 100.0, -30.0, 30.0, -7.0),
            "T4S/ramp_west.obj": west.build(),
            "T4S/ramp_east.obj": east.build(),
        }
        regions, done = _completed(geometry)
        assert len(regions) == 2, [r.polygon.area for r in regions]
        assert [region.polygon for region in done] == [
            region.polygon for region in regions]

    def test_the_classifier_runs_the_completion(self):
        """END TO END: the pass is wired into the classifier, AFTER the
        openness reading, so the ring the assembly extends records with
        is the completed one."""
        result = _classify(_ramp_pit_pattern())
        assert len(result.below_grade_regions) == 1
        assert result.below_grade_regions[0].polygon.bounds[2] == (
            pytest.approx(_RAMP_TOP_X,
                          abs=otf.AT_GRADE_FOOTPRINT_CLOSE_M + 0.1))


class TestBasinRampReachCorridor:
    """AMENDMENT 1 §2 — the RULED lever: the ramp is carried BESIDE the
    admitted ring as a corridor and consumed at EMIT.

    The class above is the refuted one: growing the ring moved the floor
    value, the rim value, the pad seat and the group-seat datum, because
    the ring is the facility's single measurement body.  Everything here
    exists to keep that from happening again — so the load-bearing
    assertion is not "the corridor covers the ramp", it is "the ring and
    every reading on it are the same object they were".

    The gate is HELD OFF (it reaches the ramp by colliding with the
    building8 pad — see ``config.BASIN_RAMP_REACH_PLATE``), so the arm
    under test is turned on explicitly, exactly as a lane turns it on."""

    @pytest.fixture(autouse=True)
    def _the_arm_under_test(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_RAMP_REACH_PLATE", True)
        # ...and the CARVE off, because this class is the RETIRED arm:
        # the plate laid with the pad's authority still standing.  Its
        # successor has its own class (``TestBasinPadAuthorityCarve``).
        monkeypatch.setattr(config, "BASIN_PAD_AUTHORITY_CARVE", False)

    def test_the_corridor_is_the_ramp_and_the_ring_is_untouched(self):
        placements = [_placement(r) for r in _ramp_pit_pattern()]
        geometry = _ramp_pit_pattern()
        admitted = otf.below_grade_regions(placements, geometry)
        carried = otf.regions_with_ramp_reach_corridor(
            admitted, placements, geometry)
        before, after = admitted[0], carried[0]
        # THE RING: the same polygon object, not merely an equal one.
        assert after.polygon is before.polygon
        corridor = after.ramp_reach_corridor
        assert corridor is not None and not corridor.is_empty
        # The corridor is the ramp BEYOND the depth admission, so it
        # starts where the ring stopped and runs to the ramp's top.
        assert corridor.bounds[2] == pytest.approx(
            _RAMP_TOP_X, abs=otf.AT_GRADE_FOOTPRINT_CLOSE_M + 0.1)
        assert not corridor.intersection(before.polygon).area > 1e-6

    def test_every_reading_that_gates_founding_is_identical(self):
        """The refutation, encoded: depth, openness, the contributor
        list and their clipped areas are what founding and the floor/rim
        laws key on, and the corridor pass may not touch one of them."""
        placements = [_placement(r) for r in _ramp_pit_pattern()]
        geometry = _ramp_pit_pattern()
        admitted = otf.below_grade_regions(placements, geometry)
        carried = otf.regions_with_ramp_reach_corridor(
            admitted, placements, geometry)
        before, after = admitted[0], carried[0]
        assert after.object_resources == before.object_resources
        assert after.solid_minimum_y_m == before.solid_minimum_y_m
        assert (after.above_grade_area_fraction
                == before.above_grade_area_fraction)
        assert (after.contributor_area_m2_by_resource
                == before.contributor_area_m2_by_resource)
        assert (after.frame_origin_longitude_latitude
                == before.frame_origin_longitude_latitude)

    def test_the_gate_off_carries_no_corridor(self, monkeypatch):
        # BOTH consumers off: the corridor is carried when EITHER the
        # retired plate arm or the owner-sanctioned PAD-AUTHORITY CARVE
        # wants it (``config.basin_ramp_corridor_carried``), so "the
        # gate off" is only a real control when neither asks for it.
        monkeypatch.setattr(config, "BASIN_RAMP_REACH_PLATE", False)
        monkeypatch.setattr(config, "BASIN_PAD_AUTHORITY_CARVE", False)
        placements = [_placement(r) for r in _ramp_pit_pattern()]
        geometry = _ramp_pit_pattern()
        admitted = otf.below_grade_regions(placements, geometry)
        carried = otf.regions_with_ramp_reach_corridor(
            admitted, placements, geometry)
        assert all(region.ramp_reach_corridor is None
                   for region in carried)

    def test_the_gate_ships_off_pending_the_pad_ruling(self):
        """HELD.  The plate DOES reach the owner's ramp — and the ramp is
        inside the building8 pad, whose flattening authority is yielded
        only INSIDE the facility, so the pan and the pad end up sharing a
        boundary with a 12.74 m step (+196 within_shape rows, 212 of them
        airside).  Which lever moves the pad is an owner ruling."""
        import inspect
        import re

        default = re.search(
            r'_os\.environ\.get\(\s*"O4_BASIN_RAMP_REACH_PLATE",\s*'
            r'"(\d)"\s*\)',
            inspect.getsource(config),
        )
        assert default is not None, "the gate lost its environment read"
        assert default.group(1) == "0", (
            "the ramp-reach plate must ship OFF until the owner rules on "
            "the building8 pad authority it collides with")

    def test_the_shell_batter_is_not_a_ramp(self):
        """THE DELTA IS NOT THE RAMP, and this is the test that says so.

        Clipping at the ground-contact band instead of the depth
        admission widens the ring EVERYWHERE the shell is battered, so
        the raw difference carries a thin annulus wrapping the pit
        alongside the ramp.  MEASURED at LEMD: 1,779 m² of delta, of
        which the batter annulus is 690 m² over 24 % of the ring's
        perimeter, reaching 2.25 m; the ramp is 798 m² over 11 %,
        reaching 11.22 m.  Emitting the annulus would widen the pan and
        stand the rim band down all the way round — Amendment 1's
        refuted ring-widening, arriving by the back door.
        """
        from shapely.geometry import Point
        from shapely.ops import unary_union

        ring = Polygon([(-40, -40), (40, -40), (40, 40), (-40, 40)])
        # A 3 m batter skirt all the way round (what the reach plane
        # adds to a 45° side) and a 30 m ramp running east.
        batter = ring.buffer(3.0).difference(ring)
        ramp = Polygon([(40, -8), (70, -8), (70, 8), (40, 8)]).difference(
            ring)
        delta = batter.union(ramp)
        kept, _dropped = otf._ramp_lobes_of(delta, ring)
        assert kept, "the ramp itself was dropped"
        corridor = kept[0] if len(kept) == 1 else unary_union(kept)
        assert corridor.covers(Point(60.0, 0.0)), "the ramp is not carried"
        # The batter is gone: nothing survives on the far side of the pit.
        assert not corridor.covers(Point(-42.0, 0.0))
        assert corridor.area < 0.5 * delta.area, (
            corridor.area, delta.area)

    def test_the_reach_bound_is_the_batter_slope_not_a_knob(self):
        """The bound is the plan travel of a 45° side over the height
        the reach pass spans — both numbers already in the module."""
        assert otf.RAMP_REACH_CORRIDOR_MIN_REACH_M == pytest.approx(
            otf.TRENCH_SPINE_MIN_DEPTH_M + otf.REGION_RAMP_REACH_PLANE_Y_M)

    def test_sub_plate_slivers_are_dropped_part_by_part(self):
        """``completed − admitted`` leaves numerical dust all the way
        round the shared ring.  Kept, each speck would be a plate
        fragment AND would stand the rim band down at a random point on
        the pit's own wall — so parts are judged ALONE, never summed."""
        placements = [_placement(r) for r in _ramp_pit_pattern()]
        geometry = _ramp_pit_pattern()
        admitted = otf.below_grade_regions(placements, geometry)
        corridor = otf.regions_with_ramp_reach_corridor(
            admitted, placements, geometry)[0].ramp_reach_corridor
        parts = (list(corridor.geoms)
                 if corridor.geom_type == "MultiPolygon" else [corridor])
        assert parts, "the ramp itself must survive"
        assert all(part.area >= otf.RAMP_REACH_CORRIDOR_MIN_AREA_M2
                   for part in parts), [p.area for p in parts]

    def test_a_pit_with_no_ramp_carries_no_corridor(self):
        placements = [_placement(r) for r in _t4s_pattern()]
        geometry = _t4s_pattern()
        admitted = otf.below_grade_regions(placements, geometry)
        carried = otf.regions_with_ramp_reach_corridor(
            admitted, placements, geometry)
        assert carried[0].ramp_reach_corridor is None


    # ── THE EMIT PREDICATE (Amendment 1 §2) ──────────────────────────
    #: The interface's own 50 x 50 m below-grade footprint, and a region
    #: exactly on it — so the record is EXTENDED, the LEMD relation.
    EMIT_REGION = Polygon([(-25, -25), (25, -25), (25, 25), (-25, 25)])
    #: The ramp running EAST out of it, 20 m long and 16 m wide.  It
    #: touches the body outline so the emitter's bridge can reach the
    #: floor pan, and it reaches well past the rim band.
    EMIT_CORRIDOR = Polygon([(25, -8), (45, -8), (45, 8), (25, 8)])
    #: A point 15 m out along the ramp: OUTSIDE the body, outside the
    #: rim band, and squarely in the corridor.  This is the owner's
    #: poke-through point in miniature.
    EMIT_PROBE = (40.0, 0.0)


    def test_an_old_classification_reads_back_as_no_corridor(self):
        """DEFAULTED both sides, so a pre-v25 pickle cannot raise — the
        VERSION is what retires it, never an AttributeError."""
        assert otf.BelowGradeRegion(
            polygon=Polygon([(0, 0), (1, 0), (1, 1)]),
            frame_origin_longitude_latitude=(0.0, 0.0),
            solid_minimum_y_m=-7.0).ramp_reach_corridor is None
        assert getattr(
            otf.TunnelStructure(
                object_resources=[], anchor_longitude_latitude=(0.0, 0.0),
                frame_origin_longitude_latitude=(0.0, 0.0),
                heading_degrees=0.0, placement_kind="OBJECT",
                above_ground_offset_m=0.0, roof_footprint=None,
                deck_footprint=None, mouth_polygons=[],
                mouth_depth_samples=[], body_depth_m=1.0),
            "ramp_reach_corridor") is None
        assert otf._clip_triangle_below_plane(
            ((0.0, 1.0, 0.0), (10.0, 2.0, 0.0), (10.0, 3.0, 10.0)),
            -2.5) is None


class TestBasinPadAuthorityCarve:
    """THE OWNER-SANCTIONED CARVE (spec
    ``docs/specs/lemd-pad-authority-carve-spec.md``, owner 2026-08-28
    item 2: "identify the ramp coming down into the big pit and ensure
    we cut away enough so the terrain is not extending above the
    object").

    The class above is the REFUSED predecessor: the same plate, laid
    while ``building8``'s flattening authority still stood over the
    ground it lands on — 587.75 m against 600.49 m across one boundary,
    +196 ``within_shape`` rows, 212 of them airside.  Everything here is
    about WHICH AUTHORITY OWNS WHICH GROUND, so the load-bearing
    assertions are the two scope clauses: the carve reaches exactly as
    far as the authority it carves, and inside the corridor only the
    carved pads yield.

    The gate ships ON, so the arm under test is the default and the
    CONTROL is what has to be asked for.
    """

    #: The facility, its ramp and the probe out along it — the SAME
    #: miniature the retired arm's emit predicate uses, imported rather
    #: than re-spelled so the two classes cannot describe two ramps.
    EMIT_REGION = TestBasinRampReachCorridor.EMIT_REGION
    EMIT_CORRIDOR = TestBasinRampReachCorridor.EMIT_CORRIDOR
    EMIT_PROBE = TestBasinRampReachCorridor.EMIT_PROBE
    #: The ``building8`` class: a pad LARGER than the facility, covering
    #: it whole AND containing the whole ramp corridor.
    COVERING_PAD = Polygon([(-60, -60), (60, -60), (60, 60), (-60, 60)])
    #: The same pad cut short at x = 35, so the corridor's far half
    #: (x 35..45, the probe included) lies OUTSIDE the carved authority.
    SHORT_PAD = Polygon([(-60, -60), (35, -60), (35, 60), (-60, 60)])
    #: An apron REACHING the facility's own rim band (the strip along
    #: y 8..20) and running out over the corridor's FAR half only
    #: (x >= 38).  Reaching the band is what puts it in the §B PAVEMENT
    #: yield population — the population the pan's own yield set carries
    #: and the corridor's does not; covering only the far half is what
    #: leaves the near half for the carve to keep, so the two clauses
    #: are separable in one fixture.
    FAR_APRON = Polygon([(20, 8), (38, 8), (38, -20), (90, -20),
                         (90, 20), (20, 20)])


    # ── the gate ────────────────────────────────────────────────────
    def test_the_gate_ships_ON(self):
        import inspect
        import re

        default = re.search(
            r'_os\.environ\.get\(\s*"O4_BASIN_PAD_AUTHORITY_CARVE",\s*'
            r'"(\d)"\s*\)',
            inspect.getsource(config),
        )
        assert default is not None, "the gate lost its environment read"
        assert default.group(1) == "1"


    def test_one_reader_decides_whether_a_corridor_is_carried(self):
        """Two consumers, ONE predicate — a second spelling of "is there
        a ramp here" is the census-wrapper class."""
        import unittest.mock as _mock

        for plate, carve, expected in (
                (False, False, False), (True, False, True),
                (False, True, True), (True, True, True)):
            with _mock.patch.object(
                    config, "BASIN_RAMP_REACH_PLATE", plate), \
                    _mock.patch.object(
                        config, "BASIN_PAD_AUTHORITY_CARVE", carve):
                assert config.basin_ramp_corridor_carried() is expected


class TestBasinCarveGInstrumentScope:
    """§4 — THE G INSTRUMENT IS SCOPED, NEVER RE-BASELINED.

    ``R_mesh`` is defined as "the first terrain OUTSIDE OUR OWN PLATES",
    and the carve lays a floor plate in the ramp corridor, which lies
    beside the body and therefore under that band (measured at LEMD: 8
    of 70 stations).  Unscoped, the instrument would median our own
    587.75 m plate and call it the surrounding grade.

    What is lawful is dropping those stations.  What is NOT lawful is
    moving the ring, its offset or its step — so that is what these
    twins pin."""

    RING = (((-0.0005, -0.0005), (0.0005, -0.0005),
             (0.0005, 0.0005), (-0.0005, 0.0005), (-0.0005, -0.0005)),)
    #: A box over the ring's whole +x side, well outside the body — the
    #: corridor in miniature, in the same longitude/latitude spelling.
    EXCLUSION = (((0.0004, -0.0006), (0.0009, -0.0006),
                  (0.0009, 0.0006), (0.0004, 0.0006),
                  (0.0004, -0.0006)),)

    def _stations(self, exclusion=None):
        from auto_patch import post_mesh

        points, _parts = post_mesh._basin_facility_rim_sample_ring(
            self.RING, 0.0, 0.0, exclusion)
        return points

    def test_no_exclusion_is_the_instrument_it_was(self):
        """The default path is byte-identical to the unscoped read —
        both spellings of "nothing to exclude"."""
        assert self._stations() == self._stations(())
        assert self._stations() == self._stations(None)
        assert len(self._stations()) > 8

    def test_the_excluded_stations_are_dropped_and_no_others(self):
        """SCOPE, and only scope: the survivors are the unscoped
        stations minus the excluded ones, in the same order."""
        from shapely.geometry import Point, Polygon as _Polygon

        unscoped = self._stations()
        scoped = self._stations(self.EXCLUSION)
        assert len(scoped) < len(unscoped)
        assert scoped == [p for p in unscoped if p in scoped]
        box = _Polygon(self.EXCLUSION[0])
        dropped = [p for p in unscoped if p not in scoped]
        assert dropped, "the fixture excludes nothing"
        for latitude, longitude in dropped:
            assert box.covers(Point(longitude, latitude))
        for latitude, longitude in scoped:
            assert not box.covers(Point(longitude, latitude))

    def test_the_ring_itself_never_moves(self):
        """The body parts the band is offset from are the same object
        either way — the instrument is scoped at the STATION, never by
        re-deriving the ring."""
        from auto_patch import post_mesh

        _points, bare = post_mesh._basin_facility_rim_sample_ring(
            self.RING, 0.0, 0.0)
        _points2, scoped = post_mesh._basin_facility_rim_sample_ring(
            self.RING, 0.0, 0.0, self.EXCLUSION)
        assert len(bare) == len(scoped)
        for before, after in zip(bare, scoped):
            assert before.equals(after)


class TestBasinRegionFootprintGate:
    """Spec §2.4 / §3 test 5.  ``O4_BASIN_REGION_FOOTPRINT=0`` → the
    records are what they were before this round, object for object."""


    def test_the_gate_defaults_on(self):
        assert config.BASIN_REGION_FOOTPRINT is True


    def test_gate_off_derives_no_region_at_all(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_REGION_FOOTPRINT", False)
        assert _classify(_t4s_pattern()).below_grade_regions == []


# ---------------------------------------------------------------------------
# BASIN FOUNDING FROM UNMATCHED REGIONS (spec docs/specs/
# basin-region-founding-spec.md, follow-up docket A of the owner's
# 2026-08-26 LEMD T4S rulings)
# ---------------------------------------------------------------------------


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


class TestBasinFoundingDepthRefusal:
    """Spec §3 test 2.  Founding is inference without an interface to key
    on, so the 2.5-3.0 m band stays EXTENSION-ONLY evidence."""


    def test_the_floor_is_the_shared_constant(self):
        assert otf.BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M == pytest.approx(3.0)


class TestBasinFoundingOpennessRefusal:
    """Spec §3 test 3 / ruling R13.  A COVERED region is a bore/tunnel
    candidate, not an open pit — and it stays attributable."""


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


class TestBasinFoundingGate:
    """Spec §2.4 / §3 test 6.  ``O4_BASIN_REGION_FOUNDING=0`` → nothing
    is founded and extension is exactly the landed round."""

    def test_the_gate_defaults_on(self):
        assert config.BASIN_REGION_FOUNDING is True


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
