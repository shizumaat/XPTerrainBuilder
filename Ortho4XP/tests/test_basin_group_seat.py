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

import json
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

from auto_patch import config  # noqa: E402
from auto_patch import obj8_reader  # noqa: E402
from auto_patch import object_rebake  # noqa: E402
from auto_patch import object_terrain_assembly as assembly  # noqa: E402
from auto_patch import post_mesh  # noqa: E402

from test_object_basin_trench import (  # noqa: E402
    ANCHOR_LATITUDE,
    ANCHOR_LONGITUDE,
    _Classification,
    _GeometryBuilder,
    _at_grade_building_geometry,
    _interface,
    _obj8_text,
    _pit_shell,
    _square_ring,
    _vertex_y_values,
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
                              flat_elevation_m: float | None = None) -> None:
    """The built mesh under the fixture.

    ``flat_elevation_m`` writes one flat plane instead (the threshold
    no-op arm: the family already drapes on the plane its author drew
    it on, which is what OTHH's anchor-outside facilities measured).
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
            if flat_elevation_m is not None:
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
    mesh_path.write_text("\n".join(lines) + "\n")


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
            path.write_text(_obj8_text(geometry[resource]))
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

    def _facility(self, *, resources=(PIT_SHELL,)):
        """The classifier's record for the synthetic pit: the body ring
        the emitter cut, and the pit shell as its interface member."""
        ring = tuple(
            (ANCHOR_LONGITUDE + longitude_offset,
             ANCHOR_LATITUDE + latitude_offset)
            for longitude_offset, latitude_offset
            in _square_ring(BODY_HALF_SPAN_M)
        )
        return assembly.BasinRimFlushFacility(
            object_resources=tuple(sorted(resources)),
            anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            body_rings_longitude_latitude=(ring,),
            solid_minimum_y_m=PIT_FLOOR_Y_M,
            anchor_inside_body=True,
        )

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

    def _run(self, tmp_path, monkeypatch, **mesh_kwargs):
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path, **mesh_kwargs)
        facility = self._facility()
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])
        return result, pack_root

    # -- §3 case 1: the relationship invariant (the owner's metric) -------

    def test_every_member_lands_on_one_datum_plane(
        self, tmp_path, monkeypatch
    ):
        """THE LAW: ``mesh(anchor) + delta == G`` for every group member,
        across two anchors 6 m apart on differently sloping ground."""
        result, _pack_root = self._run(tmp_path, monkeypatch)

        record = result["basin_group_seat"][0]
        assert record["decision_kind"] == "basin_group_seat"
        seat_datum = record["g_m"]
        assert seat_datum == pytest.approx(RIM_ELEVATION_M)
        assert record["baked"] is True
        deltas = record["delta_by_resource"]
        # The at-grade shell and both below-grade decks joined the pit
        # shell — the whole local complex, and only it.
        assert set(deltas) == {
            PIT_SHELL, TERMINAL, DECK_MINUS_3, DECK_MINUS_7}
        # Two different anchor grounds (the slope is real)...
        grounds = {
            resource: seat_datum - delta
            for resource, delta in deltas.items()
        }
        assert grounds[DECK_MINUS_7] > grounds[PIT_SHELL] + 0.3
        # ...and ONE rendered datum plane.
        for resource, delta in deltas.items():
            assert grounds[resource] + delta == pytest.approx(
                seat_datum, abs=1e-9), resource

    def test_the_authored_relationships_survive(self, tmp_path, monkeypatch):
        """The owner's metric stated in rendered metres: every pair's
        rendered vertical relationship equals its authored one — 0.000 m
        relative shift, materiality 0.01 m."""
        result, pack_root = self._run(tmp_path, monkeypatch)
        record = result["basin_group_seat"][0]
        deltas = record["delta_by_resource"]
        seat_datum = record["g_m"]

        rendered_top: dict[str, float] = {}
        for resource in (PIT_SHELL, TERMINAL, DECK_MINUS_3, DECK_MINUS_7):
            live = _vertex_y_values(pack_root / resource)
            authored = _vertex_y_values(
                pack_root / (resource + ".anchor_bak"))
            per_vertex = {round(baked - original, 6)
                          for baked, original in zip(live, authored)}
            # Rigid within the file: ONE delta, never a per-cluster set.
            assert len(per_vertex) == 1, resource
            assert per_vertex.pop() == pytest.approx(
                deltas[resource], abs=1e-4)
            ground = seat_datum - deltas[resource]
            rendered_top[resource] = ground + deltas[resource] + max(authored)

        # Authored: the −3 deck's top sits 4 m above the −7 deck's, and
        # the terminal's roof 14 m above grade.  Rendered: the same.
        assert (rendered_top[DECK_MINUS_3]
                - rendered_top[DECK_MINUS_7]) == pytest.approx(
                    DECK_MINUS_3_TOP_Y - DECK_MINUS_7_TOP_Y, abs=0.01)
        assert (rendered_top[TERMINAL]
                - rendered_top[DECK_MINUS_3]) == pytest.approx(
                    14.0 - DECK_MINUS_3_TOP_Y, abs=0.01)

    # -- §3 case 3: seat-group membership --------------------------------

    def test_an_overlapping_structure_joins_and_leaves_the_generic_pass(
        self, tmp_path, monkeypatch
    ):
        """Widening is ONE step (trap T1, the LSGG starvation law): the
        structure over the body is seated by this law AND removed from
        the generic pass's population in the same decision."""
        result, pack_root = self._run(tmp_path, monkeypatch)

        seated_by_group = {
            resource
            for _pool, decision in result["decisions"]
            for resource in decision.decision_kind_by_resource
        }
        assert TERMINAL in seated_by_group
        skip_reasons = {
            resource: reason for resource, reason in result["skipped"]
        }
        assert "basin_group_seat" in skip_reasons.get(TERMINAL, ""), (
            "the seat-group member was not withheld from the generic pass "
            "in the same step")
        provenance = json.loads(
            (pack_root / ".o4_reanchor_provenance.json").read_text())
        assert provenance["objects"][TERMINAL]["decision_kind"] == (
            "basin_group_seat")

    def test_a_distant_structure_on_the_same_datum_never_joins(
        self, tmp_path, monkeypatch
    ):
        """The scope test the spec draws: the group is the local complex,
        never the whole shared-datum family (the LSGG lesson)."""
        result, pack_root = self._run(tmp_path, monkeypatch)

        record = result["basin_group_seat"][0]
        assert FAR_BUILDING not in record["delta_by_resource"]
        provenance = json.loads(
            (pack_root / ".o4_reanchor_provenance.json").read_text())
        far_entry = provenance["objects"].get(FAR_BUILDING)
        if far_entry is not None:
            assert far_entry.get("decision_kind") is None

    # -- §3 case 4: the threshold no-op (item 6 retired) -----------------

    def test_a_family_already_on_its_plane_is_a_recorded_no_op(
        self, tmp_path, monkeypatch
    ):
        """The OTHH pattern: anchor ground == R_mesh, the drape is
        already correct, so the bake is a RECORDED no-op and no ``.obj``
        is rewritten (spec §2.3 item 2)."""
        result, pack_root = self._run(
            tmp_path, monkeypatch, flat_elevation_m=RIM_ELEVATION_M)

        record = result["basin_group_seat"][0]
        assert record["threshold_no_op"] is True
        assert record["baked"] is False
        assert "NO-OP" in record["decision"]
        assert record["delta_max_m"] == pytest.approx(0.0, abs=1e-6)
        for resource in (PIT_SHELL, TERMINAL, DECK_MINUS_3, DECK_MINUS_7):
            assert not (pack_root / (resource + ".anchor_bak")).exists()

    def test_the_no_op_still_withholds_the_group(self, tmp_path, monkeypatch):
        """A no-op is an ANSWER, not an abstention: the group stays out of
        the generic pass, or the cluster law would seat it after all."""
        result, _pack_root = self._run(
            tmp_path, monkeypatch, flat_elevation_m=RIM_ELEVATION_M)
        skip_reasons = {
            resource: reason for resource, reason in result["skipped"]
        }
        assert "basin_group_seat" in skip_reasons.get(TERMINAL, "")

    # -- the modes the pre-amendment law already had (carried forward) ----

    def test_measure_only_records_the_group_and_writes_nothing(
        self, tmp_path, monkeypatch
    ):
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path)
        result = self._rebake(
            dsf_path, mesh_path, pack_root, [self._facility()],
            measure_only=True)
        record = result["basin_group_seat"][0]
        assert record["measure_only"] is True
        assert record["baked"] is False
        assert record["g_m"] == pytest.approx(RIM_ELEVATION_M)
        assert result["objects_written"] == []
        for resource in (PIT_SHELL, TERMINAL, DECK_MINUS_3, DECK_MINUS_7):
            backup = pack_root / (resource + ".anchor_bak")
            if backup.exists():
                assert (pack_root / resource).read_bytes() == (
                    backup.read_bytes())

    def test_a_dry_run_reports_the_group_without_writing(
        self, tmp_path, monkeypatch
    ):
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path)
        result = self._rebake(
            dsf_path, mesh_path, pack_root, [self._facility()],
            write_changes=False)
        record = result["basin_group_seat"][0]
        assert record["dry_run"] is True
        assert record["baked"] is False
        assert record["delta_by_resource"]
        for resource in (PIT_SHELL, TERMINAL):
            assert not (pack_root / (resource + ".anchor_bak")).exists()

    def test_the_group_bake_is_byte_idempotent(self, tmp_path, monkeypatch):
        """Invariant I-15: the second run rewrites from ``.anchor_bak``,
        so it lands on the same bytes — never twice the delta."""
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path)
        facility = self._facility()
        self._rebake(dsf_path, mesh_path, pack_root, [facility])
        first = {
            resource: (pack_root / resource).read_bytes()
            for resource in (PIT_SHELL, TERMINAL, DECK_MINUS_3, DECK_MINUS_7)
        }
        self._rebake(dsf_path, mesh_path, pack_root, [facility])
        for resource, expected in first.items():
            assert (pack_root / resource).read_bytes() == expected

    def test_the_clearance_finding_still_fires_on_the_group_datum(
        self, tmp_path, monkeypatch
    ):
        """Item 7 unchanged, wider membership: a built rim below
        ``R_est − margin`` means the section-2.1 margin is too small for
        this airport — reported, never silently re-derived."""
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        # A 7 m pit needs 7.5 m of clearance under its rim; give it 5.
        _write_sloped_trench_mesh(mesh_path, floor_slope=0.0)
        facility = self._facility()
        result = self._rebake(dsf_path, mesh_path, pack_root, [facility])
        record = result["basin_group_seat"][0]
        assert record["clearance_finding"] is True
        # R_est = floor + DECK + MARGIN - y_true_min = 10 + 0.5 + 1 + 7
        assert record["rim_estimate_m"] == pytest.approx(18.5)
        assert record["r_mesh_minus_r_est_m"] == pytest.approx(-3.5)

    def test_two_facilities_sharing_one_rigid_unit_are_refused(
        self, tmp_path, monkeypatch, capsys
    ):
        """MEASURED AT LEMD (2026-08-27 acceptance run): the §2.1 split
        produced a second, DEGENERATE body component (1.6e-13 m² beside
        the real 27,806 m² T4S ring) whose seat group was the same rigid
        unit — and it seated those 42 files onto a SECOND datum 3.705 m
        away, last writer winning.  A group that overlaps an earlier
        group is REFUSED and named, never silently re-seated."""
        import O4_UI_Utils as UI

        UI.verbosity = 1
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path)
        facility = self._facility()
        result = self._rebake(
            dsf_path, mesh_path, pack_root, [facility, facility])

        first, second = result["basin_group_seat"]
        assert first["baked"] is True
        assert second["baked"] is False
        assert "SHARES" in second["decision"]
        assert "BASIN GROUP SEAT FINDING" in capsys.readouterr().out
        # ...and the pack is left on ONE datum plane.
        provenance = json.loads(
            (pack_root / ".o4_reanchor_provenance.json").read_text())
        datums = {
            entry["seat_datum_m"]
            for entry in provenance["objects"].values()
            if entry.get("decision_kind") == "basin_group_seat"
        }
        assert len(datums) == 1

    # -- §2.4: the member fates are LOUD, never silent -------------------

    def test_a_multi_placement_member_is_named_against_its_facility(
        self, tmp_path, monkeypatch, capsys
    ):
        """Invariant I-4 stands — one shared file cannot carry
        per-placement offsets — but the skip is no longer silent to the
        facility whose relationships the member is missing from."""
        import O4_UI_Utils as UI

        from auto_patch import dsf_reader

        UI.verbosity = 1
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        # A SECOND draped placement of the pit shell — the I-4 pattern
        # (~19 of LEMD's 203 placements).
        original = dsf_reader._load_dsf_text(str(dsf_path))
        index = [
            line for line in original if line.startswith("OBJECT_DEF")
        ].index(f"OBJECT_DEF {PIT_SHELL}")
        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text",
            lambda _path: list(original) + [
                f"OBJECT {index} {_metres_east_to_longitude(80.0)} "
                f"{ANCHOR_LATITUDE} 0.0"])
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path)
        result = self._rebake(
            dsf_path, mesh_path, pack_root, [self._facility()])

        out = capsys.readouterr().out
        assert "BASIN GROUP SEAT: facility member" in out, (
            "the I-4 skip was silent to the facility")
        assert PIT_SHELL in out
        assert PIT_SHELL not in result["basin_group_seat"][0].get(
            "delta_by_resource", {})

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

    def test_the_provenance_records_the_delta_and_the_datum(
        self, tmp_path, monkeypatch
    ):
        """Trap T6: until now no delta survived the write, so LEMD's
        applied offsets were unrecoverable from a restored pack."""
        result, pack_root = self._run(tmp_path, monkeypatch)
        record = result["basin_group_seat"][0]
        provenance = json.loads(
            (pack_root / ".o4_reanchor_provenance.json").read_text())
        for resource, delta in record["delta_by_resource"].items():
            entry = provenance["objects"][resource]
            assert entry["decision_kind"] == "basin_group_seat"
            assert entry["seat_datum_m"] == pytest.approx(record["g_m"])
            assert entry["delta_m"] == pytest.approx(delta)
            # ...and the invariant is re-readable from the sidecar alone.
            assert (entry["anchor_ground_m"] + entry["delta_m"]
                    == pytest.approx(entry["seat_datum_m"], abs=1e-9))

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

    def test_the_gate_off_restores_the_interface_member_law(
        self, tmp_path, monkeypatch
    ):
        """``O4_BASIN_GROUP_SEAT=0`` is the pre-amendment behaviour:
        ``basin_rim_flush``, interface members only, the group untouched
        by the basin law."""
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", False)
        result, pack_root = self._run(tmp_path, monkeypatch)

        assert result["basin_group_seat"] == []
        record = result["basin_rim_flush"][0]
        assert record["decision_kind"] == "basin_rim_flush"
        assert record["baked"] is True
        assert record["objects_written"] == [PIT_SHELL]
        provenance = json.loads(
            (pack_root / ".o4_reanchor_provenance.json").read_text())
        assert provenance["objects"][PIT_SHELL]["decision_kind"] == (
            "basin_rim_flush")
        # ...and the pre-amendment entry gains no group fields.
        assert "seat_datum_m" not in provenance["objects"][PIT_SHELL]
        terminal_entry = provenance["objects"].get(TERMINAL)
        if terminal_entry is not None:
            assert terminal_entry.get("decision_kind") is None

    def test_the_gate_off_keeps_the_topological_item_six(
        self, tmp_path, monkeypatch
    ):
        """The retired scope test still decides under the gate: an
        anchor-OUTSIDE facility does not bake at all."""
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", False)
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = tmp_path / "Data+25+051.mesh"
        _write_sloped_trench_mesh(mesh_path)
        facility = self._facility()
        outside = assembly.BasinRimFlushFacility(
            object_resources=facility.object_resources,
            anchor_longitude_latitude=facility.anchor_longitude_latitude,
            body_rings_longitude_latitude=(
                facility.body_rings_longitude_latitude),
            solid_minimum_y_m=facility.solid_minimum_y_m,
            anchor_inside_body=False,
        )
        result = self._rebake(dsf_path, mesh_path, pack_root, [outside])
        assert result["basin_rim_flush"][0]["baked"] is False
        assert "OUTSIDE its body" in result["basin_rim_flush"][0]["decision"]


class TestFacilitySplitPerConnectedBody:
    """Spec §3 case 2 / §2.1.  The anchor key is the pack's DATUM, so a
    shared-datum pack lands every below-grade structure in ONE facility
    whose body unions unrelated pits — which is how LEMD's T4S facility
    "contained" an anchor 406 m outside its own ring."""

    NEAR_PIT = Polygon([(-40, -40), (40, -40), (40, 40), (-40, 40)])
    FAR_PIT = Polygon([(400, -40), (480, -40), (480, 40), (400, 40)])

    def _facilities(self):
        return assembly.basin_rim_flush_facilities(_Classification(
            ground_interfaces=[
                _interface(
                    footprint=self.NEAR_PIT,
                    resources=("T4S/near_pit.obj",),
                    floor_y_m=-6.0,
                ),
                _interface(
                    footprint=self.FAR_PIT,
                    resources=("T4S/far_pit.obj",),
                    floor_y_m=-4.0,
                ),
            ]))

    def test_two_disjoint_pits_become_two_facilities(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", True)
        facilities = self._facilities()
        assert len(facilities) == 2
        by_resource = {
            facility.object_resources: facility for facility in facilities
        }
        assert set(by_resource) == {
            ("T4S/near_pit.obj",), ("T4S/far_pit.obj",)}
        # Each component keeps its OWN floor key — the far pit's shallower
        # body never deepens the near pit's, and vice versa.
        assert by_resource[("T4S/near_pit.obj",)].solid_minimum_y_m == (
            pytest.approx(-6.0))
        assert by_resource[("T4S/far_pit.obj",)].solid_minimum_y_m == (
            pytest.approx(-4.0))
        # Exactly one of them contains the shared datum anchor.
        assert sorted(
            facility.anchor_inside_body for facility in facilities
        ) == [False, True]

    #: A body part twenty orders of magnitude below anything this project
    #: models — the LEMD artifact (1.6e-13 m²) at test scale: ~9e-10 m².
    SLIVER = Polygon([
        (60.0, 0.0), (60.00003, 0.0), (60.00003, 0.00003), (60.0, 0.00003)])

    def test_a_degenerate_sliver_is_dropped_not_founded(
        self, monkeypatch, capsys
    ):
        """§2.1 Amendment 2 (Fable 2026-08-27).  MEASURED AT LEMD: the
        body union split into the real 27,806 m² T4S ring AND a
        1.6e-13 m² sliver, and the sliver became a full facility with its
        own datum ``G`` 3.705 m away that double-seated 42 files.  It is
        numerical noise, not a facility: repaired, measured in metres,
        dropped LOUDLY — and the overlap refusal never has to fire."""
        import O4_UI_Utils as UI

        UI.verbosity = 1
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", True)
        facilities = assembly.basin_rim_flush_facilities(_Classification(
            ground_interfaces=[
                _interface(
                    footprint=self.NEAR_PIT,
                    resources=("T4S/near_pit.obj",),
                    floor_y_m=-6.0,
                ),
                _interface(
                    footprint=self.SLIVER,
                    resources=("T4S/sliver.obj",),
                    floor_y_m=-6.0,
                ),
            ]))
        # ONE facility — the real pit — and the sliver is not among them.
        assert len(facilities) == 1
        assert facilities[0].object_resources == ("T4S/near_pit.obj",)
        out = capsys.readouterr().out
        assert "DEGENERATE BODY COMPONENT dropped" in out, (
            "the sliver was dropped SILENTLY")
        assert "geometric-validity floor" in out
        # With one facility there is no second seat group, so the
        # ratified overlap refusal is never reached.
        assert "BASIN GROUP SEAT FINDING" not in out

    def test_the_gate_off_keeps_the_one_unioned_facility(self, monkeypatch):
        monkeypatch.setattr(config, "BASIN_GROUP_SEAT", False)
        facilities = self._facilities()
        assert len(facilities) == 1
        facility = facilities[0]
        assert set(facility.object_resources) == {
            "T4S/near_pit.obj", "T4S/far_pit.obj"}
        # The pre-amendment reading: one body, both rings, the deepest
        # member's key, and ``covers`` judged against the union.
        assert len(facility.body_rings_longitude_latitude) == 2
        assert facility.solid_minimum_y_m == pytest.approx(-6.0)
        assert facility.anchor_inside_body is True
