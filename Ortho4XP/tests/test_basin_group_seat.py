"""THE BASIN GROUP SEAT — docket B of the basin-region round
(``docs/specs/basin-group-seat-spec.md``, owner 2026-08-26 "spec and
implement the follow-up dockets").

THE DEFECT the spec names, measured at LEMD T4S: 203 placements / 184
resources drape on ONE datum, so every authored inter-object vertical
relationship is carried by that shared drape.  On a sloping mesh the
shipped machinery split the family across five fates — one member seated
by the ``basin_rim_flush`` law at anchor ground 595.97, its neighbours
generically cluster-seated at 597.52 (a 1.544 m two-instrument gap at one
identical point), four structures A3-skipped, ~19 placements I-4-skipped,
78 resources never baked — and cut an 8.95 m seam INSIDE the fused
terminal complex whose below-grade decks must stay −2/−3/−7 relative to
the terminal.

THE LAW under test: one connected body = one facility (§2.1); the seat
group is every partition structure whose footprint reaches that body
(§2.2); the whole group lands on ONE datum plane ``G = R_mesh`` with
``delta(member) = G − anchor_ground(member)``, seated and withheld from
the generic pass in the SAME step (§2.2 widening rule, trap T1); item 6
is a threshold no-op on the existing ``DSF_OBJECT_BAKE_MIN_DELTA_M``
(§2.3 item 2); the provenance records the applied delta and ``G`` (§2.5).

Fixtures are synthetic (ruling R6): hand-built geometry, a hand-written
mesh, a monkeypatched DSF text.  No pack content enters the repository.
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


from auto_patch import config  # noqa: E402
from auto_patch import obj8_reader  # noqa: E402
from auto_patch import object_rebake  # noqa: E402
from auto_patch import post_mesh  # noqa: E402

from test_object_basin_trench import (
    ANCHOR_LATITUDE,
    ANCHOR_LONGITUDE,
    _GeometryBuilder,
    _at_grade_building_geometry,
    _obj8_text,
    _pit_shell,
    _square_ring,
)

# The synthetic pit: a 30 m half-span body about the datum, floor 7 m
# down — the LEMD T4S relation (a deep open pit with an at-grade shell
# standing over it and below-grade decks hanging inside it).
BODY_HALF_SPAN_M = 30.0
PIT_FLOOR_Y_M = -7.0

# The built mesh: a trench floor about the datum, SLOPING east, inside a
# flat rim plain.  The slope is what makes the invariant testable — two
# members 6 m apart drape on different ground and must still end on ONE
# plane.
MESH_FLOOR_HALF_SPAN_M = 20.0
MESH_EXTENT_M = 120.0
MESH_STEP_M = 4.0
FLOOR_AT_DATUM_M = 10.0
FLOOR_SLOPE_PER_METRE = 0.1
RIM_ELEVATION_M = 15.0

#: The second anchor: 6 m east of the pack datum (LEMD's second datum
#: sits 6.2 m from the first and carries 98 placements).
SECOND_ANCHOR_EAST_M = 6.0


def _metres_east_to_longitude(east_metres: float) -> float:
    return ANCHOR_LONGITUDE + east_metres / (
        obj8_reader.METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(ANCHOR_LATITUDE))
    )


def _slab(
    *, half_span_m: float, top_y: float, thickness_m: float = 0.4,
    centre_east_m: float = 0.0, centre_south_m: float = 0.0,
) -> object:
    """A closed box — one below-grade deck of the family."""
    builder = _GeometryBuilder()
    x0 = centre_east_m - half_span_m
    x1 = centre_east_m + half_span_m
    z0 = centre_south_m - half_span_m
    z1 = centre_south_m + half_span_m
    builder.add_horizontal_rectangle(x0, x1, z0, z1, top_y, segments=2)
    builder.add_horizontal_rectangle(
        x0, x1, z0, z1, top_y - thickness_m, segments=2)
    for x in (x0, x1):
        builder.add_vertical_wall(x, z0, z1, top_y - thickness_m, top_y)
    return builder.build()


def _write_sloped_trench_mesh(mesh_path, *, floor_slope=FLOOR_SLOPE_PER_METRE,
                              flat_elevation_m: float | None = None,
                              carved_corridor_m: float | None = None) -> None:
    """The built mesh under the fixture.

    ``flat_elevation_m`` writes one flat plane instead (the threshold
    no-op arm: the family already drapes on the plane its author drew
    it on, which is what OTHH's anchor-outside facilities measured).

    ``carved_corridor_m`` cuts the CARVE CORRIDOR into it — the ground
    east of the body that the pad-authority carve plates at the pit
    floor.  It is what a tile rebuilt WITH the carve actually looks
    like, and it is the only way to ask §4b's question honestly: is the
    corridor-EXCLUDED read stable ACROSS the carve?
    """
    steps = int(2 * MESH_EXTENT_M / MESH_STEP_M) + 1
    coordinates = [
        -MESH_EXTENT_M + index * MESH_STEP_M for index in range(steps)
    ]
    vertices: list[tuple[float, float, float]] = []
    for east in coordinates:
        for south in coordinates:
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0, east, south)
            if (carved_corridor_m is not None
                    and BODY_HALF_SPAN_M < east <= 2.0 * BODY_HALF_SPAN_M
                    and abs(south) <= BODY_HALF_SPAN_M / 3.0):
                # The carved corridor, at the pit floor.
                elevation = carved_corridor_m
            elif flat_elevation_m is not None:
                elevation = flat_elevation_m
            elif (abs(east) <= MESH_FLOOR_HALF_SPAN_M
                    and abs(south) <= MESH_FLOOR_HALF_SPAN_M):
                elevation = FLOOR_AT_DATUM_M + floor_slope * east
            else:
                elevation = RIM_ELEVATION_M
            vertices.append((longitude, latitude, elevation))
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


#: THE FAMILY.  One flat authored datum, one at-grade shell over the pit,
#: two below-grade decks at authored −3 and −7 (the LEMD relation), the
#: pit shell itself, and one structure two kilometres away on the SAME
#: datum that must never join the group.
PIT_SHELL = "T4S/pit_shell.obj"
TERMINAL = "T4S/terminal_shell.obj"
DECK_MINUS_3 = "T4S/deck_minus3.obj"
DECK_MINUS_7 = "T4S/deck_minus7.obj"
FAR_BUILDING = "Cargo/far_building.obj"

DECK_MINUS_3_TOP_Y = -3.0
DECK_MINUS_7_TOP_Y = -7.0


def _family_geometry() -> dict:
    return {
        PIT_SHELL: _pit_shell(BODY_HALF_SPAN_M, 6.0, PIT_FLOOR_Y_M, 0.0),
        TERMINAL: _at_grade_building_geometry(
            half_span_m=28.0, height_m=14.0),
        DECK_MINUS_3: _slab(half_span_m=12.0, top_y=DECK_MINUS_3_TOP_Y),
        DECK_MINUS_7: _slab(half_span_m=10.0, top_y=DECK_MINUS_7_TOP_Y),
        FAR_BUILDING: _at_grade_building_geometry(
            half_span_m=40.0, height_m=12.0),
    }


def _family_placement_longitudes() -> dict:
    """Every member on the pack datum, except the −7 deck on the SECOND
    datum 6 m east (LEMD ships two datums 6.2 m apart)."""
    return {
        PIT_SHELL: ANCHOR_LONGITUDE,
        TERMINAL: ANCHOR_LONGITUDE,
        DECK_MINUS_3: ANCHOR_LONGITUDE,
        DECK_MINUS_7: _metres_east_to_longitude(SECOND_ANCHOR_EAST_M),
        FAR_BUILDING: ANCHOR_LONGITUDE,
    }


def _far_local_offset_metres() -> float:
    """Two kilometres east — same datum, different world."""
    return 2000.0


class TestBasinGroupSeat:
    """Spec §3 cases 1 and 3-6.  One pit, one family, one datum plane."""

    @pytest.fixture(autouse=True)
    def _sandbox(self, tmp_path, monkeypatch):
        # Every sidecar cache under the test's own root, and off: each
        # arm must compute, never inherit another arm's answer.
        monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "o4root"))
        monkeypatch.setenv("O4_OBJECT_EXCLUSION_CACHE", "0")
        monkeypatch.setenv("O4_OBJECT_PARTITION_CACHE", "0")
        monkeypatch.setenv("O4_REANCHOR_SHORT_CIRCUIT", "0")

    # -- fixtures ---------------------------------------------------------

    def _pack(self, tmp_path, monkeypatch):
        from auto_patch import dsf_reader

        pack_root = tmp_path / "LEMD-TEST Aerosoft"
        geometry = _family_geometry()
        # The far building is placed on the datum but MODELLED two
        # kilometres east — a shared-datum pack's geography lives in its
        # local coordinates, which is exactly why anchor proximity is not
        # a family test (project memory: shared-datum pack authoring).
        far = geometry[FAR_BUILDING]
        offset = _far_local_offset_metres()
        geometry[FAR_BUILDING] = type(far)(
            vertices=[(x + offset, y, z) for x, y, z in far.vertices],
            solid_triangles=list(far.solid_triangles),
            draped_triangles=[],
            positional_commands=[],
            animation_block_count=0,
            level_of_detail_count=0,
            vertex_line_indices=list(range(len(far.vertices))),
            solid_triangle_hardness=tuple(far.solid_triangle_hardness),
        )
        longitudes = _family_placement_longitudes()
        definition_lines = []
        placement_lines = []
        for index, resource in enumerate(sorted(geometry)):
            path = pack_root / resource
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_obj8_text(geometry[resource]), encoding="utf-8", newline="")
            definition_lines.append(f"OBJECT_DEF {resource}")
            placement_lines.append(
                f"OBJECT {index} {longitudes[resource]} "
                f"{ANCHOR_LATITUDE} 0.0")
        dsf_path = pack_root / "overlay.dsf"
        dsf_path.write_bytes(b"")
        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text",
            lambda _path: definition_lines + placement_lines)
        return dsf_path, pack_root


    def _rebake(self, dsf_path, mesh_path, pack_root, facilities, **kwargs):
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


    # -- §3 case 1: the relationship invariant (the owner's metric) -------


    # -- §3 case 3: seat-group membership --------------------------------


    # -- §3 case 4: the threshold no-op (item 6 retired) -----------------


    # -- the modes the pre-amendment law already had (carried forward) ----


    # -- §2.4: the member fates are LOUD, never silent -------------------


    def test_the_reach_floor_drop_reports_itself(self):
        """Trap T5's silent fate: the generic discovery's reach-floor
        drop was a bare ``continue``, so a resource that never reached a
        decision left no trace of why."""
        from auto_patch.obj8_reader import ObjectPlacement

        geometry = _slab(half_span_m=1.0, top_y=0.5)
        resource = "T4S/tiny.obj"
        placement = ObjectPlacement(
            definition_index=0,
            resource_path=resource,
            longitude=ANCHOR_LONGITUDE,
            latitude=ANCHOR_LATITUDE,
            heading_degrees=0.0,
            above_ground_level_metres=0.0,
            placement_kind="OBJECT",
            mean_sea_level_elevation_m=None,
        )
        skipped: list = []
        monkey = pytest.MonkeyPatch()
        try:
            from auto_patch import dsf_reader, obj8_reader as reader

            monkey.setattr(
                reader, "resolve_object_resource",
                lambda *args, **kwargs: "/pack/" + resource)
            monkey.setattr(
                post_mesh, "_resolved_path_is_inside_pack",
                lambda *args, **kwargs: True)
            monkey.setattr(
                dsf_reader, "_load_object_geometry",
                lambda *args, **kwargs: geometry)
            post_mesh._resolve_pack_geometry(
                [placement], {resource: 1}, "/pack", None, skipped)
        finally:
            monkey.undo()
        assert skipped, "the reach-floor drop is still silent"
        assert "floor" in skipped[0][1]

    # -- §3 case 5: provenance + the gate lists ---------------------------


    def test_the_gate_lists_carry_every_basin_environment_name(self):
        """Spec §2.5 and recon trap T3: four basin gates were missing
        from the run-record digest, so a pre-region record could
        short-circuit a post-region decision."""
        for name in (
            "O4_BASIN_GROUP_SEAT",
            "O4_BASIN_REGION_FOOTPRINT",
            "O4_BASIN_REGION_FOUNDING",
            "O4_BASIN_OPEN_PIT_DECK_KEY",
            "O4_BASIN_POOL_SCOPING",
            # ...and the ramp-reach gate (spec lemd-basin-trench-ramp-
            # extension): it moves the body OUTLINE, which is exactly
            # what R_mesh's sample band is offset from.
            "O4_BASIN_REGION_RAMP_REACH",
        ):
            assert name in object_rebake._GATE_ENVIRONMENT_NAMES, name
        assert "BASIN_GROUP_SEAT" in object_rebake._GATE_NAMES

    def test_the_group_seat_gate_salts_the_run_digest(self, monkeypatch):
        baseline = object_rebake._gate_digest(0.25)
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", False)
        assert object_rebake._gate_digest(0.25) != baseline

    # -- §3 case 6: the gate off ------------------------------------------


# ── §4a/§4c: THE FOUNDED DATUM IS CARRIED, NEVER RE-DERIVED ──────────
#
# Spec ``docs/specs/lemd-pad-authority-carve-spec.md`` §4, AMENDED
# 2026-08-28.  ``R_mesh`` is a median of the BUILT MESH just outside the
# facility's own plates; where a round deliberately CARVES that ground
# the mesh is no longer the surface the pack's seat was founded on, and
# re-deriving from it moves the whole rigid family.  MEASURED on the
# carve lane with ONE instrument over ONE facility: 596.682 m on the
# 2026-08-27 +40-004 surface and 600.510 m on the 2026-08-28 one — 3.83 m
# of "seat" that is only which mesh answered.


class TestDriftDetectorAcrossTheCarve:
    """§4b — the corridor-EXCLUDED read is the DRIFT DETECTOR.

    Its acceptance is not a value, it is a STABILITY: the scoped read
    must be the same before and after the carve (tolerance 0.01 m),
    because the carve is only allowed to touch the corridor.  A moved
    scoped read means it reached ambient ground — a STOP, never a
    re-seat.  These twins ask that question the only honest way: two
    meshes, one built without the carve and one with it cut in, ONE
    station set, both reads.
    """

    #: §4b's own tolerance.
    DRIFT_TOLERANCE_M = 0.01

    def _rings(self):
        ring = tuple(
            (ANCHOR_LONGITUDE + longitude_offset,
             ANCHOR_LATITUDE + latitude_offset)
            for longitude_offset, latitude_offset
            in _square_ring(BODY_HALF_SPAN_M))
        step = BODY_HALF_SPAN_M / 111320.0
        corridor = tuple(
            (ANCHOR_LONGITUDE + longitude, ANCHOR_LATITUDE + latitude)
            for longitude, latitude in (
                (step, -step / 3.0), (2.0 * step, -step / 3.0),
                (2.0 * step, step / 3.0), (step, step / 3.0),
                (step, -step / 3.0)))
        return (ring,), (corridor,)

    def _reads(self, tmp_path, **mesh_kwargs):
        from statistics import median
        from auto_patch.mesh_sampler import MeshElevationSampler

        body_rings, corridor_rings = self._rings()
        unscoped, _parts = post_mesh._basin_facility_rim_sample_ring(
            body_rings, ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
        scoped, _parts2 = post_mesh._basin_facility_rim_sample_ring(
            body_rings, ANCHOR_LATITUDE, ANCHOR_LONGITUDE, corridor_rings)
        name = "carved" if mesh_kwargs.get("carved_corridor_m") else "plain"
        mesh_path = tmp_path / f"Data+25+051.{name}.mesh"
        _write_sloped_trench_mesh(mesh_path, **mesh_kwargs)
        latitudes = [p[0] for p in unscoped]
        longitudes = [p[1] for p in unscoped]
        sampler = MeshElevationSampler(
            str(mesh_path),
            (min(longitudes) - 0.002, min(latitudes) - 0.002,
             max(longitudes) + 0.002, max(latitudes) + 0.002))

        def _read(points):
            values = [v for v in (sampler.elevation_at_or_none(a, b)
                                  for a, b in points) if v is not None]
            return median(values), len(values), values

        return _read(unscoped), _read(scoped)

    def test_the_corridor_really_is_under_the_band(self, tmp_path):
        """The premise: without the exclusion the band samples the
        corridor, so stations are actually dropped by it."""
        (_u, unscoped_n, _uv), (_s, scoped_n, _sv) = self._reads(tmp_path)
        assert scoped_n < unscoped_n

    def test_the_scoped_read_is_STABLE_across_the_carve(self, tmp_path):
        """§4b's acceptance, in miniature: the carve cuts the corridor to
        the pit floor and the corridor-EXCLUDED read does not move."""
        (_pu, _n1, _puv), (plain_s, _n2, _psv) = self._reads(tmp_path)
        (_cu, _n3, _cuv), (carved_s, _n4, _csv) = self._reads(
            tmp_path, carved_corridor_m=FLOOR_AT_DATUM_M)
        assert abs(carved_s - plain_s) <= self.DRIFT_TOLERANCE_M, (
            plain_s, carved_s)

    def test_the_UNSCOPED_band_SAMPLES_OUR_OWN_PLATE(self, tmp_path):
        """The control for the twin above, and the reason the scope
        exists at all — stated on the SAMPLES, not on the median.

        A median is a rank statistic: at LEMD the band spans 589-600 m
        and losing 8 of 70 stations moves it 0.682 m, but on a fixture
        whose ambient rim is one flat value it cannot move at all.  What
        is TRUE either way, and what §4a is actually about, is WHICH
        GROUND was read: unscoped, the band lands on the plate this
        round laid at the pit floor; scoped, it never does."""
        (_pu, _n1, _puv), (_ps, _n2, _psv) = self._reads(tmp_path)
        (_cu, _n3, unscoped_values), (_cs, _n4, scoped_values) = (
            self._reads(tmp_path, carved_corridor_m=FLOOR_AT_DATUM_M))
        # Stated against the AMBIENT RIM, never against the plate's own
        # value: the band's stations fall between mesh vertices, so a
        # station over the corridor reads the triangle's interpolation
        # (10.50 m here, not the 10.00 m the plate was written at) —
        # asserting the exact plate value would be asserting the
        # fixture's triangulation, not the law.
        assert min(unscoped_values) < RIM_ELEVATION_M - 1.0, (
            "the unscoped band did not reach the carved corridor, so "
            "this fixture proves nothing")
        assert min(scoped_values) == pytest.approx(
            RIM_ELEVATION_M, abs=0.01), (
            "the scoped band sampled ground the carve had lowered")
