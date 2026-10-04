"""Round 12 — a bridge seats by its DECK TOP, and a bridge is ONE body.

``docs/specs/round12-bridge-deck-datum-spec.md``.  Three laws:

* **R12-1** the seat datum is the DECK TOP, not the authored ``y = 0``
  plane: the deck top lands AT the abutment grade, and the record's
  promised deck top is asserted against the one the deltas achieve.
* **R12-2** one bridge is one rigid body: the member set is the whole
  ANCHOR FAMILY, and a family never tears across per-structure grounds.
  (The refused-piered-viaduct limb is MEASURED, not written — see
  ``TestRefusedViaductIsMeasuredNotWritten`` and the STOP recorded
  there.)
* **R12-3** the pipeline/post-mesh verdict split is RECORDED as a
  counted finding; nothing about which verdict is used changes.

Headless, ``tmp_path``-based, no network and no X-Plane install: the
mesh is a written MeshVersionFormatted dump and the pack is three tiny
OBJ8 boxes.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch import object_terrain_features as features  # noqa: E402
from auto_patch.obj8_reader import local_offset_to_lonlat  # noqa: E402


ANCHOR_LATITUDE = 36.1245
ANCHOR_LONGITUDE = -86.6782

# The OTHH class-A geometry, in metres about the anchor.
WATER_ELEVATION_M = 0.0
LAND_ELEVATION_M = 3.96
WATER_HALF_SPAN_M = 50.0
ABUTMENT_X_M = 80.0
ABUTMENT_HALF_WIDTH_M = 27.5
MESH_EXTENT_M = 260.0
MESH_STEP_M = 10.0

FLUSH_DECK_TOP_Y_M = -0.31      # OTHH Bridge_01
RAISED_DECK_TOP_Y_M = 1.19      # OTHH Bridge_05 (1.187, rounded)

DECK_RESOURCE = "Objects/Bridges/bridge_deck.obj"
PIER_RESOURCE = "Objects/Bridges/bridge_pier.obj"
RAIL_RESOURCE = "Objects/Bridges/bridge_rail.obj"   # the LOD0_004 class

_BOX_OBJ_TEXT = "\n".join([
    "I", "800", "OBJ", "",
    "POINT_COUNTS 8 0 0 12", "",
    "VT -12.0 0.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 0.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 0.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "VT -12.0 0.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "VT -12.0 3.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 3.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 3.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "VT -12.0 3.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "IDX 0", "IDX 1", "IDX 2", "IDX 0", "IDX 2", "IDX 3",
    "IDX 4", "IDX 5", "IDX 6", "IDX 4", "IDX 6", "IDX 7",
    "TRIS 0 12",
]) + "\n"


def _write_two_level_mesh(mesh_path, *, water_half_span_m,
                          water_bits_half_span_m=None,
                          water_bits_z_band_m=None) -> None:
    """A built-mesh dump: water inside a square about the anchor, land
    outside.  The sampler reads z in 100 km units.

    ``water_bits_half_span_m`` is the square whose triangles carry the
    mesh's WATER ATTRIBUTE (terrain type 2, the sea class — any bit of
    ``mesh_sampler.WATER_BIT_MASK``); it defaults to the elevation
    square.  Keeping the two separable is the point: the seat must read
    the ATTRIBUTE, never the elevation, so a fixture can hold water at
    3.96 m or dry land at 0.00 m and the twins still pin the right
    behaviour."""
    if water_bits_half_span_m is None:
        water_bits_half_span_m = water_half_span_m
    steps = int(2 * MESH_EXTENT_M / MESH_STEP_M) + 1
    coordinates = [
        -MESH_EXTENT_M + index * MESH_STEP_M for index in range(steps)
    ]
    vertices = []
    for east in coordinates:
        for south in coordinates:
            latitude, longitude = local_offset_to_lonlat(
                ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0, east, south)
            inside = (abs(east) <= water_half_span_m
                      and abs(south) <= water_half_span_m)
            vertices.append((
                longitude, latitude,
                WATER_ELEVATION_M if inside else LAND_ELEVATION_M,
            ))
    def _water_bit(*vertex_indices):
        # Attribute 2 = the sea class; a triangle is water only when
        # EVERY corner is inside the attributed region, so the shoreline
        # triangle reads as land exactly as a real mesh's does.
        #
        # ``water_bits_z_band_m`` attributes an infinite BAND across the
        # deck axis instead of a square — a canal, which is what lets a
        # twin drown one member's deck ends and leave its neighbour's
        # dry.
        for index in vertex_indices:
            east, south = coordinate_pairs[index]
            if water_bits_z_band_m is not None:
                if abs(south) > water_bits_z_band_m:
                    return 0
                continue
            if not (abs(east) <= water_bits_half_span_m
                    and abs(south) <= water_bits_half_span_m):
                return 0
        return 2

    coordinate_pairs = [
        (east, south) for east in coordinates for south in coordinates
    ]
    triangles = []
    for i in range(steps - 1):
        for j in range(steps - 1):
            a, b = i * steps + j, (i + 1) * steps + j
            c, d = (i + 1) * steps + j + 1, i * steps + j + 1
            triangles.append((a + 1, b + 1, c + 1, _water_bit(a, b, c)))
            triangles.append((a + 1, c + 1, d + 1, _water_bit(a, c, d)))
    lines = ["MeshVersionFormatted 2", "Dimension 3", "", "Vertices",
             str(len(vertices))]
    for longitude, latitude, elevation in vertices:
        lines.append(
            f"{longitude:.15f} {latitude:.15f} {elevation / 100000.0:.15f} 0")
    lines += ["", "Normals", "0", "", "Triangles", str(len(triangles))]
    for first, second, third, attribute in triangles:
        lines.append(f"{first} {second} {third} {attribute}")
    mesh_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def _abutment_lines(*, centre_z_m=0.0, half_width_m=ABUTMENT_HALF_WIDTH_M):
    """The two deck-END lines of one deck, at x = +-ABUTMENT_X_M.

    ``centre_z_m`` slides the whole deck sideways (across its own axis),
    which is how a twin puts a SECOND member's deck beside the first —
    two real bridges in one connected assembly."""
    lines = []
    for sign in (-1.0, 1.0):
        points = []
        for half in (-half_width_m, half_width_m):
            latitude, longitude = local_offset_to_lonlat(
                ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0,
                sign * ABUTMENT_X_M, centre_z_m + half)
            points.append((longitude, latitude))
        lines.append(tuple(points))
    return tuple(lines)


def _member_record(resource_path, deck_top_y_m, *, centre_z_m=0.0):
    """One ``deck_member_records`` entry: a member's own end lines and
    its own EFFECTIVE crest (amendment 3)."""
    return {
        "resource_path": resource_path,
        "abutment_points_longitude_latitude": _abutment_lines(
            centre_z_m=centre_z_m),
        "deck_top_y_m": deck_top_y_m,
    }


@dataclass
class _Classification:
    bridges: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    tunnels: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    ground_interfaces: list = field(default_factory=list)
    portal_faces: list = field(default_factory=list)


def _bridge(**overrides):
    """A minimal :class:`features.BridgeStructure` for the candidacy
    pass — only the fields the pass reads carry meaning."""
    from shapely.geometry import Polygon

    defaults = dict(
        object_resources=[DECK_RESOURCE],
        anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        frame_origin_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        heading_degrees=0.0,
        deck_polygon=Polygon([(-80, -27), (80, -27), (80, 27), (-80, 27)]),
        deck_top_profile=[(-80.0, 0.0), (80.0, 0.0)],
        deck_top_y_m=FLUSH_DECK_TOP_Y_M,
        deck_end_elevations_y_m=(0.0, 0.0),
        absolute_deck_elevation_m=None,
        hard_deck=False,
        deck_hardness=features.DECK_HARDNESS_COSMETIC,
        deck_length_m=160.0,
        deck_width_m=54.0,
        ceiling_y_m=None,
        clearance_underside_y_m=None,
        abutment_lines=[
            ((-ABUTMENT_X_M, -ABUTMENT_HALF_WIDTH_M),
             (-ABUTMENT_X_M, ABUTMENT_HALF_WIDTH_M)),
            ((ABUTMENT_X_M, -ABUTMENT_HALF_WIDTH_M),
             (ABUTMENT_X_M, ABUTMENT_HALF_WIDTH_M)),
        ],
        abutment_reaches_grade=(True, True),
        contract=features.TERRAIN_CARRIED,
    )
    defaults.update(overrides)
    return features.BridgeStructure(**defaults)


class _Harness:
    """One airport rebake against a written mesh and a written pack."""

    _mesh_serial = 0

    def pack(self, tmp_path, monkeypatch, resources, *, agl_by_resource=None,
             obj_text=_BOX_OBJ_TEXT):
        from auto_patch import dsf_reader

        pack_root = tmp_path / "R12 Test Pack"
        for resource in resources:
            path = pack_root / resource
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(obj_text, encoding="utf-8", newline="")
        dsf_path = pack_root / "overlay.dsf"
        dsf_path.write_bytes(b"")
        agl_by_resource = agl_by_resource or {}
        lines = []
        for resource in resources:
            lines.append(f"OBJECT_DEF {resource}")
        for index, resource in enumerate(resources):
            agl = agl_by_resource.get(resource)
            if agl is None:
                lines.append(
                    f"OBJECT {index} {ANCHOR_LONGITUDE} "
                    f"{ANCHOR_LATITUDE} 0.0")
            else:
                # OBJECT_AGL <def> <lon> <lat> <agl> <heading>
                lines.append(
                    f"OBJECT_AGL {index} {ANCHOR_LONGITUDE} "
                    f"{ANCHOR_LATITUDE} {agl} 0.0")
        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text", lambda _path: lines)
        return dsf_path, pack_root

    def mesh(self, tmp_path, *, water=True, water_half_span_m=None,
             water_bits_half_span_m=None, water_bits_z_band_m=None):
        # A fresh name per fixture: mesh_sampler memoizes its parse by
        # (path, mtime, size), and two fixtures can collide on all three.
        mesh_path = tmp_path / f"Data+36-087_{self._mesh_serial}.mesh"
        self._mesh_serial += 1
        if water_half_span_m is None:
            water_half_span_m = WATER_HALF_SPAN_M if water else -1.0
        _write_two_level_mesh(
            mesh_path, water_half_span_m=water_half_span_m,
            water_bits_half_span_m=water_bits_half_span_m,
            water_bits_z_band_m=water_bits_z_band_m)
        return mesh_path

    def rebake(self, dsf_path, mesh_path, pack_root, candidates, **kwargs):
        from auto_patch import post_mesh

        return post_mesh.discover_and_rebake_airport(
            str(dsf_path), str(mesh_path), str(pack_root), None,
            excluded_resources={
                (str(pack_root), resource)
                for candidate in candidates
                for resource in candidate.object_resources
            },
            bridge_abutment_seat_candidates=candidates,
            **kwargs,
        )


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "o4root"))
    monkeypatch.setenv("O4_OBJECT_EXCLUSION_CACHE", "0")
    monkeypatch.setenv("O4_OBJECT_PARTITION_CACHE", "0")
    monkeypatch.setenv("O4_REANCHOR_SHORT_CIRCUIT", "0")


@pytest.fixture
def harness():
    return _Harness()


def _vertex_y_values(path) -> list:
    return [
        float(line.split()[2])
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("VT ")
    ]


# ── 1. the datum twin (R12-1) ────────────────────────────────────────


# ── 2. the rigid-family twin (R12-2) ─────────────────────────────────


# ── 3. the refused-viaduct limb (R12-2, STOP) ────────────────────────


# ── 3b. one seat for a connected assembly (amendment 3) ──────────────


# ── 3c. the agreeing coalition (amendment 4) ─────────────────────────


class TestTheAgreeingCoalitionSeatsTheAssembly:
    """AMENDMENT 4.  Agreement is the signature of a real measurement;
    scatter is the signature of an artifact.  The largest group of member
    deltas inside one 0.25 m window AUTHORS the family's level; the rest
    are named as outliers with their end-line sample censuses, which is
    the standing evidence trail for the canal-floor residual B2 cannot
    see.

    Every member here reads the same LAND grade, so a member's delta is
    set purely by its own crest (``delta = grade − crest − mesh(anchor)``
    with the anchor over water at 0.00 m).  That is what lets a fixture
    place deltas exactly where the OTHH measurement put them."""

    def _members(self, deltas):
        """One deck member per delta, each its own deck across the same
        canal, all reading the same land grade."""
        resources = [
            f"Objects/Bridges/member_{index:02d}.obj"
            for index in range(len(deltas))
        ]
        # The row is CENTRED on the anchor so every member's end lines
        # stay inside the fixture mesh: a member off the mesh is silent,
        # which would quietly change the member count under test.
        spacing = 55.0
        offset = (len(deltas) - 1) / 2.0
        records = [
            _member_record(
                resource,
                # delta = grade - crest - mesh(anchor); mesh(anchor) = 0.
                LAND_ELEVATION_M - delta,
                centre_z_m=(index - offset) * spacing,
            )
            for index, (resource, delta) in enumerate(zip(resources, deltas))
        ]
        return resources, records


    #: The OTHH class-B shape, amendment 3's measurement: four clean
    #: members agreeing inside 0.05 m, and scattered artifacts.
    OTHH_SHAPED = [0.946, 0.957, 0.959, 0.996,
                   1.349, -0.247, -0.780, -2.835]


    def test_the_coalition_is_pure_arithmetic_over_the_deltas(self):
        """The finder itself, away from any mesh: it returns the largest
        agreeing group, the outliers in delta order, and a reason only
        when no group may seat."""
        from auto_patch import post_mesh

        def _entries(deltas):
            return [{"member": f"m{index}", "delta_m": delta}
                    for index, delta in enumerate(deltas)]

        coalition, outliers, refusal = post_mesh.agreeing_coalition(
            _entries(self.OTHH_SHAPED), 0.25)
        assert refusal is None
        assert [entry["delta_m"] for entry in coalition] == [
            0.946, 0.957, 0.959, 0.996]
        assert [entry["delta_m"] for entry in outliers] == [
            -2.835, -0.780, -0.247, 1.349]

        # A lone member cannot corroborate itself.
        _coalition, _outliers, refusal = post_mesh.agreeing_coalition(
            _entries([1.0]), 0.25)
        assert refusal and "nothing corroborates" in refusal

        # The window is inclusive at exactly the tolerance.
        coalition, _outliers, refusal = post_mesh.agreeing_coalition(
            _entries([0.0, 0.25, 9.0]), 0.25)
        assert refusal is None
        assert len(coalition) == 2


# ── 4. the frame-split finding (R12-3) ───────────────────────────────


# ── 5. the classifier keeps the refusal's deck measurements ──────────


class TestRefusalRecordsCarryTheDeck:
    """R12-2's enabling data: refusing a terrain FEATURE and refusing to
    know where the deck is are two different acts.  ``_classify_bridge``
    measures the axis, the abutment lines and the crest BEFORE the
    viaduct guard fires; the refusal record now carries them."""

    def test_a_refusal_with_merged_lines_but_no_members_is_unmeasurable(
        self,
    ):
        """AMENDMENT 3 retires the merged min-rect: a refusal carrying
        ONLY the whole-component chords has nothing the seat may use."""
        refusal = features.RefusedStructure(
            object_resources=[DECK_RESOURCE],
            reason="piered viaduct",
            deck_object_resources=[DECK_RESOURCE],
            anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            frame_origin_longitude_latitude=(
                ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            abutment_lines=_bridge().abutment_lines,
            deck_top_y_m=RAISED_DECK_TOP_Y_M,
        )
        assert refusal.has_measurable_deck is False

    def test_a_refusal_without_deck_data_has_no_measurable_deck(self):
        refusal = features.RefusedStructure(
            object_resources=[DECK_RESOURCE], reason="island deck")
        assert refusal.has_measurable_deck is False

    def test_a_refusal_with_deck_data_has_a_measurable_deck(self):
        refusal = features.RefusedStructure(
            object_resources=[DECK_RESOURCE],
            reason="piered viaduct",
            deck_object_resources=[DECK_RESOURCE],
            anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            frame_origin_longitude_latitude=(
                ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            abutment_lines=_bridge().abutment_lines,
            deck_top_y_m=RAISED_DECK_TOP_Y_M,
            deck_members=(
                features.RefusedDeckMember(
                    resource_path=DECK_RESOURCE,
                    abutment_lines=_bridge().abutment_lines,
                    deck_top_y_m=RAISED_DECK_TOP_Y_M,
                ),
            ),
        )
        assert refusal.has_measurable_deck is True

    def test_widening_keeps_the_measurements_and_takes_the_component(self):
        refusal = features.RefusedStructure(
            object_resources=[DECK_RESOURCE],
            reason="piered viaduct",
            deck_object_resources=[DECK_RESOURCE],
            anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            frame_origin_longitude_latitude=(
                ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
            abutment_lines=_bridge().abutment_lines,
            deck_top_y_m=RAISED_DECK_TOP_Y_M,
            deck_members=(
                features.RefusedDeckMember(
                    resource_path=DECK_RESOURCE,
                    abutment_lines=_bridge().abutment_lines,
                    deck_top_y_m=RAISED_DECK_TOP_Y_M,
                ),
            ),
        )
        widened = features._widen_refusal_to_component(
            refusal, {DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE})
        assert widened.object_resources == sorted(
            [DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE])
        assert widened.deck_object_resources == [DECK_RESOURCE]
        assert widened.deck_top_y_m == pytest.approx(RAISED_DECK_TOP_Y_M)
        assert widened.reason == refusal.reason
        # ...and the per-member records ride along, or the seat would
        # have nothing to measure after the widening.
        assert widened.deck_members == refusal.deck_members


# ── 6. the offline-replay arithmetic pins (spec section 6) ───────────


class TestOTHHReplayArithmetic:
    """The class-A numbers from the offline replay against the current
    +25+051 mesh (2026-08-11), as pure arithmetic pins.  The replay
    itself needs the shared corpus; these pin what it proved."""

    @pytest.mark.parametrize(
        "name, abutment_grade, deck_top_y, agl, old_delta, new_delta",
        [
            # AMENDMENT 2 B1's pins, from the offline replay against the
            # current +25+051 mesh (2026-08-11).  ``old_delta`` is R6-3's,
            # which landed the authored y = 0 plane at the grade.
            ("Bridge_05", 5.088544, 1.187266, -3.500114, 8.5887, 3.9013),
            ("Bridge_04", 4.050594, 1.067460, -3.800870, 7.8515, 2.9831),
            ("Bridge_01", 3.851457, -0.307454, -3.500114, 7.3516, 4.1589),
        ],
    )
    def test_the_seat_delta_arithmetic(
        self, name, abutment_grade, deck_top_y, agl, old_delta, new_delta
    ):
        # Every OTHH anchor sits over the canal, which the built mesh
        # answers at 0.00 m.
        mesh_at_anchor = 0.0
        # R6-3's delta put the authored y = 0 plane at the grade...
        anchor_ground = mesh_at_anchor + agl
        assert abutment_grade - anchor_ground == pytest.approx(
            old_delta, abs=0.001)
        # ...the corrected law puts the DECK TOP there, in the effective
        # frame the crest is measured in.
        assert new_delta == pytest.approx(
            abutment_grade - deck_top_y - mesh_at_anchor, abs=0.001)
        # The seated deck top IS the abutment grade.
        assert mesh_at_anchor + deck_top_y + new_delta == pytest.approx(
            abutment_grade, abs=0.001)
        # ...and the superseded formula was exactly |AGL| too large.
        superseded = (abutment_grade - deck_top_y) - anchor_ground
        assert superseded - new_delta == pytest.approx(-agl, abs=0.001)

    @pytest.mark.parametrize(
        "name, abutment_grade, deck_top_y, agl, authored_min, authored_max",
        [
            # OTHH Bridge_04's real members, from the pack's authored
            # bytes: the big LOD0_003 carries deck AND supports.
            ("Bridge_04_LOD0_003", 4.050594, 1.067460, -3.800870,
             -1.774, 5.712),
            ("Bridge_05_LOD0_003", 5.088544, 1.187266, -3.500114,
             -1.820, 5.659),
        ],
    )
    def test_the_supports_descend_below_the_water_line(
        self, name, abutment_grade, deck_top_y, agl,
        authored_min, authored_max
    ):
        """Spec section 6 as amendment 2 pins it: deck top at the grade,
        supports going DOWN past the 0.00 m canal surface — instead of
        being lifted clear of the water they descend to."""
        mesh_at_anchor = 0.0
        delta = abutment_grade - deck_top_y - mesh_at_anchor
        # world y = mesh(anchor) + AGL + (authored y + delta)
        base = mesh_at_anchor + agl + delta
        assert base + authored_min < 0.0, "the supports must reach water"
        assert base + authored_max > abutment_grade
        if name.startswith("Bridge_04"):
            # The lead's pinned figure.
            assert base + authored_min == pytest.approx(-2.59, abs=0.01)
