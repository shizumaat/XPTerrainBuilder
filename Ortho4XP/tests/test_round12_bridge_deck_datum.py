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

from auto_patch import object_terrain_assembly as assembly  # noqa: E402
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


_PIER_OBJ_TEXT = "\n".join([
    "I", "800", "OBJ", "",
    "POINT_COUNTS 8 0 0 12", "",
    "VT -12.0 -2.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 -2.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 -2.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "VT -12.0 -2.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "VT -12.0 3.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 3.0000 -12.0 0.0 1.0 0.0 0.0 0.0",
    "VT 12.0 3.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "VT -12.0 3.0000 12.0 0.0 1.0 0.0 0.0 0.0",
    "IDX 0", "IDX 1", "IDX 2", "IDX 0", "IDX 2", "IDX 3",
    "IDX 4", "IDX 5", "IDX 6", "IDX 4", "IDX 6", "IDX 7",
    "TRIS 0 12",
]) + "\n"

# The pier box's authored crest: its deck top in the structure frame.
PIER_DECK_TOP_Y_M = 3.0
PIER_FOOT_Y_M = -2.0


def _write_two_level_mesh(mesh_path, *, water_half_span_m,
                          water_bits_half_span_m=None) -> None:
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
        # EVERY corner is inside the attributed square, so the shoreline
        # triangle reads as land exactly as a real mesh's does.
        for index in vertex_indices:
            east, south = coordinate_pairs[index]
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
    mesh_path.write_text("\n".join(lines) + "\n")


def _abutment_lines():
    lines = []
    for sign in (-1.0, 1.0):
        points = []
        for half in (-ABUTMENT_HALF_WIDTH_M, ABUTMENT_HALF_WIDTH_M):
            latitude, longitude = local_offset_to_lonlat(
                ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0,
                sign * ABUTMENT_X_M, half)
            points.append((longitude, latitude))
        lines.append(tuple(points))
    return tuple(lines)


def _candidate(resources, deck_top_y_m, *,
               seat_source=assembly.SEAT_SOURCE_CLASSIFIED):
    return assembly.BridgeAbutmentSeatCandidate(
        object_resources=tuple(resources),
        anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        abutment_points_longitude_latitude=_abutment_lines(),
        deck_top_y_m=deck_top_y_m,
        deck_object_resources=(resources[0],),
        seat_source=seat_source,
    )


@dataclass
class _Placement:
    resource_path: str
    latitude: float
    longitude: float
    heading_degrees: float = 0.0
    above_ground_level_metres: float = 0.0
    placement_kind: str = "OBJECT"


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
            path.write_text(obj_text)
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
             water_bits_half_span_m=None):
        # A fresh name per fixture: mesh_sampler memoizes its parse by
        # (path, mtime, size), and two fixtures can collide on all three.
        mesh_path = tmp_path / f"Data+36-087_{self._mesh_serial}.mesh"
        self._mesh_serial += 1
        if water_half_span_m is None:
            water_half_span_m = WATER_HALF_SPAN_M if water else -1.0
        _write_two_level_mesh(
            mesh_path, water_half_span_m=water_half_span_m,
            water_bits_half_span_m=water_bits_half_span_m)
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


def _local_east_north(origin_latitude, origin_longitude):
    """``to_metres(longitude, latitude) -> (east, north)`` for the twins'
    own fixture geometry."""
    import math

    cosine = math.cos(math.radians(origin_latitude))

    def to_metres(longitude, latitude):
        return ((longitude - origin_longitude) * 111320.0 * cosine,
                (latitude - origin_latitude) * 111320.0)

    return to_metres


def _vertex_y_values(path) -> list:
    return [
        float(line.split()[2])
        for line in path.read_text().splitlines()
        if line.startswith("VT ")
    ]


# ── 1. the datum twin (R12-1) ────────────────────────────────────────


class TestTheDatumIsTheDeckTop:
    """R12-1.  The seat lands the DECK TOP at the abutment grade.  A
    flush deck (crest -0.31) therefore moves 0.31 m from the old law; a
    raised deck (+1.19) moves 1.19 m, which is the whole defect: its
    supports were left hanging that far above the water."""

    def test_a_raised_deck_lands_its_deck_top_at_the_abutment_grade(
        self, tmp_path, monkeypatch, harness
    ):
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate([DECK_RESOURCE], RAISED_DECK_TOP_Y_M)])

        record = result["bridge_abutment_seat"][0]
        assert record["abutment_grade_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=1e-4)
        # THE LAW: the deck top IS the abutment grade...
        assert record["expected_deck_top_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=1e-4)
        # ...reached by ONE family delta of grade - crest - mesh(anchor)
        # (this fixture places at AGL 0, so the member's y = 0 plane
        # lands on the same number).
        assert record["seat_delta_m"] == pytest.approx(
            LAND_ELEVATION_M - RAISED_DECK_TOP_Y_M - WATER_ELEVATION_M,
            abs=1e-4)
        assert record["member_world_y0_m"][DECK_RESOURCE] == pytest.approx(
            LAND_ELEVATION_M - RAISED_DECK_TOP_Y_M, abs=1e-4)
        # ...and what the deltas achieve agrees, within materiality.
        assert record["achieved_deck_top_m"] == pytest.approx(
            record["expected_deck_top_m"], abs=0.01)
        assert record["deck_top_residual_m"] <= 0.01
        assert "datum_finding" not in record

    def test_the_flush_deck_moves_by_exactly_its_authored_crest(
        self, tmp_path, monkeypatch, harness
    ):
        """OTHH Bridge_01, the control: crest -0.31, so the new law
        seats it 0.31 m HIGHER than R6-3 did.  Its deck sat at 3.544 m,
        below its own 3.851 m abutment grade — the move is correct and
        the old behaviour is deliberately NOT pinned."""
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate([DECK_RESOURCE], FLUSH_DECK_TOP_Y_M)])

        record = result["bridge_abutment_seat"][0]
        old_law_delta = record["drop_m"]
        new_law_delta = record["seat_delta_by_resource_m"][DECK_RESOURCE]
        assert new_law_delta - old_law_delta == pytest.approx(
            -FLUSH_DECK_TOP_Y_M, abs=1e-6)
        assert record["achieved_deck_top_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=0.01)

    @pytest.mark.parametrize(
        "deck_top_y_m", [FLUSH_DECK_TOP_Y_M, 0.0, RAISED_DECK_TOP_Y_M, 3.0])
    def test_promised_and_achieved_deck_tops_agree_at_every_crest(
        self, tmp_path, monkeypatch, harness, deck_top_y_m
    ):
        """The record's promise is asserted against the bake, materiality
        0.01 m — a record that promises one number and bakes another is
        how R6-3's flush-deck assumption survived unread."""
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate([DECK_RESOURCE], deck_top_y_m)])
        record = result["bridge_abutment_seat"][0]
        assert record["achieved_deck_top_m"] == pytest.approx(
            record["expected_deck_top_m"], abs=0.01)
        assert record["intra_family_tear_m"] <= 0.01

    def test_the_pack_really_moves_by_the_deck_top_delta(
        self, tmp_path, monkeypatch, harness
    ):
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate([DECK_RESOURCE], RAISED_DECK_TOP_Y_M)])
        record = result["bridge_abutment_seat"][0]

        live = _vertex_y_values(pack_root / DECK_RESOURCE)
        authored = _vertex_y_values(
            pack_root / (DECK_RESOURCE + ".anchor_bak"))
        offsets = {round(baked - original, 4)
                   for baked, original in zip(live, authored)}
        assert offsets == {
            round(LAND_ELEVATION_M - RAISED_DECK_TOP_Y_M, 4)}
        assert record["baked"] is True


# ── 2. the rigid-family twin (R12-2) ─────────────────────────────────


class TestOneBridgeIsOneRigidBody:
    """R12-2.  Every member takes the SAME seat plane.  The generic
    y-bake's per-structure grounds — which tore OTHH Bridge_02/03/06
    across 0.00 / 1.63 / 3.96 m — never enter this arithmetic."""

    def test_three_members_at_one_anchor_take_one_delta(
        self, tmp_path, monkeypatch, harness
    ):
        members = [DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE]
        dsf_path, pack_root = harness.pack(tmp_path, monkeypatch, members)
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate(members, RAISED_DECK_TOP_Y_M)])

        record = result["bridge_abutment_seat"][0]
        deltas = record["seat_delta_by_resource_m"]
        assert sorted(deltas) == sorted(members)
        assert len(set(round(value, 6) for value in deltas.values())) == 1
        # The tear the law forbids, measured: zero.
        assert record["intra_family_tear_m"] == pytest.approx(0.0, abs=1e-9)
        assert sorted(result["objects_written"]) == sorted(members)

    def test_every_member_moves_and_none_is_left_behind(
        self, tmp_path, monkeypatch, harness
    ):
        """THE ``OTHH_Bridge_04_LOD0_004`` PIN: a family member that
        carries no deck face is still part of the bridge.  Left out of
        the seat while R4-excluded from the y-bake, it sat 7.85 m under
        its own bridge."""
        members = [DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE]
        dsf_path, pack_root = harness.pack(tmp_path, monkeypatch, members)
        harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate(members, RAISED_DECK_TOP_Y_M)])

        moved = {}
        for resource in members:
            live = _vertex_y_values(pack_root / resource)
            authored = _vertex_y_values(
                pack_root / (resource + ".anchor_bak"))
            offsets = {round(b - a, 4) for b, a in zip(live, authored)}
            assert len(offsets) == 1, resource
            moved[resource] = offsets.pop()
        assert len(set(moved.values())) == 1, moved

    def test_the_member_set_is_the_whole_anchor_family(self):
        """The candidacy pass widens the classifier's measured subset to
        the anchor family — the SAME predicate ruling R4 uses to decide
        what the generic y-bake may not touch, so a member can never be
        both withheld from the bake and left out of the seat."""
        placements = [
            _Placement(DECK_RESOURCE, ANCHOR_LATITUDE, ANCHOR_LONGITUDE),
            _Placement(PIER_RESOURCE, ANCHOR_LATITUDE, ANCHOR_LONGITUDE),
            _Placement(RAIL_RESOURCE, ANCHOR_LATITUDE, ANCHOR_LONGITUDE),
        ]
        candidates, findings = assembly.bridge_abutment_seat_candidates(
            _Classification([_bridge(object_resources=[DECK_RESOURCE])]),
            placements,
        )
        assert findings == []
        assert candidates[0].object_resources == (
            DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE)
        # ...and the measured subset survives as provenance.
        assert candidates[0].deck_object_resources == (DECK_RESOURCE,)

    def test_a_far_away_resource_is_not_family(self):
        """The family is an ANCHOR test, not a proximity guess: a
        resource placed elsewhere never joins the rigid seat."""
        far_latitude = ANCHOR_LATITUDE + 0.01
        placements = [
            _Placement(DECK_RESOURCE, ANCHOR_LATITUDE, ANCHOR_LONGITUDE),
            _Placement(PIER_RESOURCE, far_latitude, ANCHOR_LONGITUDE),
        ]
        candidates, _findings = assembly.bridge_abutment_seat_candidates(
            _Classification([_bridge(object_resources=[DECK_RESOURCE])]),
            placements,
        )
        assert candidates[0].object_resources == (DECK_RESOURCE,)

    def test_a_pack_datum_anchor_is_not_a_family(self):
        """More than ``ANCHOR_FAMILY_MAX_RESOURCES`` distinct resources
        at one anchor is a pack datum, and expanding from it would pull
        the airport onto the seat."""
        placements = [
            _Placement(DECK_RESOURCE, ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
        ] + [
            _Placement(f"Objects/clutter_{index}.obj",
                       ANCHOR_LATITUDE, ANCHOR_LONGITUDE)
            for index in range(assembly.ANCHOR_FAMILY_MAX_RESOURCES + 1)
        ]
        candidates, _findings = assembly.bridge_abutment_seat_candidates(
            _Classification([_bridge(object_resources=[DECK_RESOURCE])]),
            placements,
        )
        assert candidates[0].object_resources == (DECK_RESOURCE,)


# ── 3. the refused-viaduct limb (R12-2, STOP) ────────────────────────


class TestWaterNeverAuthorsABridgeDatum:
    """Round-12 AMENDMENT 1 (the law) with AMENDMENT 2's B2 authority
    (the instrument).  An abutment stands on LAND.  A sample whose MESH
    TRIANGLE carries the water bits is DISCARDED, and a deck end that
    loses its line to water WALKS LANDWARD along the deck axis — away
    from the span — in sample-step increments up to 60 m until at least
    four non-water samples exist.  A family that finds no land at either
    end within the cap keeps its y-bake and says so.

    The instrument is the MESH, not the OSM union: the seat already
    samples that mesh, the same triangle carries the water bits
    ``O4_DSF_Utils.remap_water_tri_type`` reads, and it knows a canal
    OSM maps only as a coastline.  Elevation is NEVER a water proxy —
    ``test_water_is_read_from_the_attribute_not_the_elevation`` is the
    pin."""

    def test_a_canal_end_walks_ashore_and_seats_at_the_land_grade(
        self, tmp_path, monkeypatch, harness
    ):
        """OTHH class B in miniature: both deck ends stand over the
        canal, so both walk landward onto the 3.96 m shore — one rigid
        family delta, the deck top at the LAND grade, and the piers
        descending below the water line."""
        members = [DECK_RESOURCE, PIER_RESOURCE]
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, members, obj_text=_PIER_OBJ_TEXT)
        result = harness.rebake(
            dsf_path,
            # A canal wide enough to swallow both abutment lines
            # (x = +-80), attributed one cell WIDER than it is deep so
            # the shoreline triangle is land, as a real mesh's is.
            harness.mesh(tmp_path, water_half_span_m=90.0,
                         water_bits_half_span_m=100.0),
            pack_root,
            [_candidate(members, PIER_DECK_TOP_Y_M,
                        seat_source=assembly.SEAT_SOURCE_REFUSED_VIADUCT)],
        )

        record = result["bridge_abutment_seat"][0]
        # Both ends had to walk, and both found their land.
        assert [end["found_land"] for end in record["abutment_ends"]] == [
            True, True]
        assert all(end["walked_m"] > 0.0 for end in record["abutment_ends"])
        assert all(end["samples_over_water"] == 0
                   for end in record["abutment_ends"])
        assert record["abutment_walked_m"] <= 60.0
        # The grade is the LAND grade, not the canal's 0.00 m.
        assert record["abutment_grade_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=1e-4)
        assert record["achieved_deck_top_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=0.01)
        # ONE rigid family delta.
        deltas = record["seat_delta_by_resource_m"]
        assert sorted(deltas) == sorted(members)
        assert len(set(round(value, 9) for value in deltas.values())) == 1
        assert record["intra_family_tear_m"] == pytest.approx(0.0, abs=1e-9)
        assert record["baked"] is True

        # THE OWNER'S PICTURE: deck top at the land grade, supports going
        # DOWN to the water — the pier foot ends BELOW the 0.00 m line.
        for resource in members:
            live = _vertex_y_values(pack_root / resource)
            assert max(live) == pytest.approx(LAND_ELEVATION_M, abs=1e-3)
            assert min(live) == pytest.approx(
                LAND_ELEVATION_M - (PIER_DECK_TOP_Y_M - PIER_FOOT_Y_M),
                abs=1e-3)
            assert min(live) < WATER_ELEVATION_M

    def test_an_all_water_family_keeps_its_y_bake_and_mints_the_finding(
        self, tmp_path, monkeypatch, harness
    ):
        """No land within the cap at either end ⇒ no seat.  The refused
        family keeps the generic y-bake it has today, the pack is not
        touched, and a counted ``bridge_seat_fallback`` says why."""
        members = [DECK_RESOURCE, PIER_RESOURCE]
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, members, obj_text=_PIER_OBJ_TEXT)
        authored = (pack_root / DECK_RESOURCE).read_text()
        result = harness.rebake(
            dsf_path,
            # Water everywhere the 60 m walk can reach (lines at +-80, so
            # the walk tops out at +-140).
            harness.mesh(tmp_path, water_half_span_m=200.0),
            pack_root,
            [_candidate(members, PIER_DECK_TOP_Y_M,
                        seat_source=assembly.SEAT_SOURCE_REFUSED_VIADUCT)],
        )

        record = result["bridge_abutment_seat"][0]
        assert [end["found_land"] for end in record["abutment_ends"]] == [
            False, False]
        assert record["abutment_walked_m"] == pytest.approx(60.0, abs=5.0)
        assert "abutment_grade_m" not in record
        assert "water never authors a bridge datum" in record["decision"]
        assert record["seat_fallback"] is True
        assert record["baked"] is False
        # Not routed: nothing claimed, so the generic y-bake still owns it.
        assert not (result.get("bridge_seat_claimed_resources") or set())
        assert (pack_root / DECK_RESOURCE).read_text() == authored
        assert [f["finding"] for f in result["bridge_findings"]] == [
            assembly.BRIDGE_SEAT_FALLBACK_FINDING]

    def test_water_is_read_from_the_attribute_not_the_elevation(
        self, tmp_path, monkeypatch, harness
    ):
        """B2 forbids approximating water by elevation, and this is the
        pin: a mesh whose canal is at 0.00 m but carries NO water bits
        is LAND.  The seat reads the attribute and takes the 0.00 m
        grade — wrong-looking, and exactly what an honest instrument
        says when the mesh does not claim water."""
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path,
            # Elevation water out past both abutment lines; NO water
            # bits anywhere.
            harness.mesh(tmp_path, water_half_span_m=200.0,
                         water_bits_half_span_m=-1.0),
            pack_root,
            [_candidate([DECK_RESOURCE], RAISED_DECK_TOP_Y_M)])

        record = result["bridge_abutment_seat"][0]
        assert all(end["samples_over_water"] == 0
                   for end in record["abutment_ends"])
        assert all(end["walked_m"] == 0.0
                   for end in record["abutment_ends"])
        assert record["abutment_grade_m"] == pytest.approx(
            WATER_ELEVATION_M, abs=1e-4)

    def test_a_mesh_with_no_water_bits_samples_exactly_as_before(
        self, tmp_path, monkeypatch, harness
    ):
        """The clause is an EXTRA discriminator: where the mesh claims no
        water, nothing is discarded and no end walks."""
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path,
            harness.mesh(tmp_path, water_bits_half_span_m=-1.0),
            pack_root,
            [_candidate([DECK_RESOURCE], RAISED_DECK_TOP_Y_M)])

        record = result["bridge_abutment_seat"][0]
        assert all(end["walked_m"] == 0.0
                   for end in record["abutment_ends"])
        assert all(end["samples_over_water"] == 0
                   for end in record["abutment_ends"])
        assert record["abutment_grade_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=1e-4)

    def test_a_classified_family_declining_is_not_a_fallback(
        self, tmp_path, monkeypatch, harness
    ):
        """Only the REFUSED limb falls back: it has a generic y-bake to
        fall back TO.  A classified family is R4-excluded before the mesh
        is read, so its decline means "stays draped" — R6-3's own answer,
        not a finding."""
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, [DECK_RESOURCE])
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path, water=False), pack_root,
            [_candidate([DECK_RESOURCE], RAISED_DECK_TOP_Y_M)])

        record = result["bridge_abutment_seat"][0]
        assert record["baked"] is False
        assert "drapes as authored" in record["decision"]
        assert "seat_fallback" not in record
        assert result["bridge_findings"] == []

    def test_a_seated_refused_family_is_routed_off_the_generic_bake(
        self, tmp_path, monkeypatch, harness
    ):
        """The routing is made from what the seat ACTUALLY produced, so a
        family that seats is claimed (and the generic pass skips it) while
        one that falls back is not."""
        members = [DECK_RESOURCE, PIER_RESOURCE]
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, members, obj_text=_PIER_OBJ_TEXT)
        result = harness.rebake(
            dsf_path,
            harness.mesh(tmp_path, water_half_span_m=90.0,
                         water_bits_half_span_m=100.0),
            pack_root,
            [_candidate(members, PIER_DECK_TOP_Y_M,
                        seat_source=assembly.SEAT_SOURCE_REFUSED_VIADUCT)],
        )
        assert result["bridge_seat_claimed_resources"] == set(members)
        reasons = [reason for resource, reason in result["skipped"]
                   if resource in members]
        assert any("bridge_abutment_seat law" in reason
                   for reason in reasons), reasons

    def test_the_walk_leaves_the_span_never_crosses_it(self):
        """LANDWARD is away from the span.  A walk towards the other deck
        end would sample the bridge's own opposite shore — or its own
        deck — and author the datum from the wrong ground."""
        from auto_patch import post_mesh
        from auto_patch.mesh_sampler import MeshSample

        candidate = _candidate([DECK_RESOURCE], PIER_DECK_TOP_Y_M)
        lines = post_mesh._abutment_line_frame_points(candidate)
        assert len(lines) == 2
        midpoints = [((s[0] + e[0]) / 2.0, (s[1] + e[1]) / 2.0)
                     for s, e in lines]
        # The two ends sit either side of the anchor on the deck axis...
        assert midpoints[0][0] < 0.0 < midpoints[1][0]

        to_metres = _local_east_north(ANCHOR_LATITUDE, ANCHOR_LONGITUDE)

        class _CanalSampler:
            """Water inside |east| <= 100 m, land at 3.96 outside."""

            def sample_at_or_none(self, latitude, longitude):
                east, _north = to_metres(longitude, latitude)
                water = abs(east) <= 100.0
                return MeshSample(
                    elevation_metres=(
                        WATER_ELEVATION_M if water else LAND_ELEVATION_M),
                    terrain_type=2 if water else 0,
                    is_water=water,
                )

        samples, ends = post_mesh._abutment_grade_samples_on_land(
            candidate, _CanalSampler())
        assert [end["found_land"] for end in ends] == [True, True]
        for end in ends:
            assert end["walked_m"] >= 20.0
        assert samples and all(
            value == pytest.approx(LAND_ELEVATION_M) for value in samples)


# ── 4. the frame-split finding (R12-3) ───────────────────────────────


class TestVerdictFrameSplitIsRecorded:
    """R12-3.  Post-mesh classification has no pavement, so its contract
    falls back to the deck-crest rule; pipeline-time classification has
    the draped pavement.  At OTHH the fallback says TERRAIN_CARRIED
    where a pipeline coverage of 0.0 says AMBIGUOUS.  RECORD it — do not
    change which verdict is used."""

    def _sidecar(self, tmp_path, monkeypatch, contract, coverage):
        import pickle

        from auto_patch import dsf_reader

        cache_directory = tmp_path / "cache"
        cache_directory.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            dsf_reader, "airport_mod_cache_dir",
            lambda _pack_root: str(cache_directory))
        pipeline_bridge = _bridge(
            contract=contract, pavement_coverage_fraction=coverage)
        path = cache_directory / (
            f"{assembly._CLASSIFICATION_SIDECAR_PREFIX}_overlay.cache")
        with open(path, "wb") as handle:
            pickle.dump(
                {"fingerprint": "x",
                 "result": _Classification([pipeline_bridge])},
                handle)
        return str(tmp_path / "overlay.dsf")

    def test_a_disagreeing_verdict_mints_one_finding(
        self, tmp_path, monkeypatch
    ):
        dsf_path = self._sidecar(
            tmp_path, monkeypatch, features.AMBIGUOUS, 0.0)
        post_mesh_result = _Classification(
            [_bridge(contract=features.TERRAIN_CARRIED,
                     pavement_coverage_fraction=None)])

        findings = assembly.bridge_verdict_frame_split_findings(
            post_mesh_result, dsf_path, "pack")
        assert len(findings) == 1
        finding = findings[0]
        assert finding["finding"] == (
            assembly.BRIDGE_VERDICT_FRAME_SPLIT_FINDING)
        assert finding["resource"] == DECK_RESOURCE
        assert finding["post_mesh_contract"] == features.TERRAIN_CARRIED
        assert finding["pipeline_contract"] == features.AMBIGUOUS
        # BOTH coverage inputs, so the reader can see WHY they differ.
        assert finding["post_mesh_coverage_fraction"] is None
        assert finding["pipeline_coverage_fraction"] == 0.0

    def test_agreeing_verdicts_mint_nothing(self, tmp_path, monkeypatch):
        dsf_path = self._sidecar(
            tmp_path, monkeypatch, features.TERRAIN_CARRIED, 0.9)
        post_mesh_result = _Classification(
            [_bridge(contract=features.TERRAIN_CARRIED,
                     pavement_coverage_fraction=None)])
        assert assembly.bridge_verdict_frame_split_findings(
            post_mesh_result, dsf_path, "pack") == []

    def test_no_sidecar_means_no_finding(self, tmp_path, monkeypatch):
        from auto_patch import dsf_reader

        monkeypatch.setattr(
            dsf_reader, "airport_mod_cache_dir",
            lambda _pack_root: str(tmp_path / "absent"))
        assert assembly.bridge_verdict_frame_split_findings(
            _Classification([_bridge()]),
            str(tmp_path / "overlay.dsf"), "pack") == []

    def test_the_findings_are_counted_and_logged(self):
        """Counted, not merely recorded: both round-12 findings have a
        count key, so a tile summary can never lose them."""
        from auto_patch import post_mesh

        assert "bridge_seat_fallbacks" in post_mesh._COUNT_KEYS
        assert "bridge_verdict_frame_splits" in post_mesh._COUNT_KEYS
        counts = {key: 0 for key in post_mesh._COUNT_KEYS}
        post_mesh._report_bridge_findings(
            "OTHH",
            [
                {"finding": assembly.BRIDGE_VERDICT_FRAME_SPLIT_FINDING,
                 "resource": DECK_RESOURCE,
                 "post_mesh_contract": features.TERRAIN_CARRIED,
                 "pipeline_contract": features.AMBIGUOUS,
                 "post_mesh_coverage_fraction": None,
                 "pipeline_coverage_fraction": 0.0},
                {"finding": assembly.BRIDGE_SEAT_FALLBACK_FINDING,
                 "resources": [DECK_RESOURCE], "reason": "no deck"},
            ],
            counts,
        )
        assert counts["bridge_verdict_frame_splits"] == 1
        assert counts["bridge_seat_fallbacks"] == 1


# ── 5. the classifier keeps the refusal's deck measurements ──────────


class TestRefusalRecordsCarryTheDeck:
    """R12-2's enabling data: refusing a terrain FEATURE and refusing to
    know where the deck is are two different acts.  ``_classify_bridge``
    measures the axis, the abutment lines and the crest BEFORE the
    viaduct guard fires; the refusal record now carries them."""

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
        )
        widened = features._widen_refusal_to_component(
            refusal, {DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE})
        assert widened.object_resources == sorted(
            [DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE])
        assert widened.deck_object_resources == [DECK_RESOURCE]
        assert widened.deck_top_y_m == pytest.approx(RAISED_DECK_TOP_Y_M)
        assert widened.reason == refusal.reason

    def test_the_classification_cache_version_moved_for_the_new_fields(self):
        """Adding a field to a PICKLED record is a cache-version event: a
        v15 pickle restores them as ``None`` and every refused viaduct
        would read as "no measurable deck"."""
        assert assembly._CLASSIFICATION_CACHE_VERSION >= 16
        assert assembly._EXCLUSION_CACHE_VERSION >= 6


# ── 6. the offline-replay arithmetic pins (spec section 6) ───────────


class TestTheDeltaIsMeasuredInTheEffectiveFrame:
    """AMENDMENT 2 B1.  ``deck_top_y_m`` is an EFFECTIVE height —
    ``object_terrain_features._build_structure_frame`` computes
    ``effective_y = above_ground_level_metres + authored_y``, metres
    above the ANCHOR'S TERRAIN — while ``anchor_ground_by_resource`` is
    world-frame (``mesh(anchor) + AGL``, the elevation of the authored
    y = 0 plane).  Subtracting one from the other double-counts the AGL
    and leaves the deck top exactly where the OLD law left the y = 0
    plane.  The law is ``grade − crest_effective − mesh_at_anchor``, ONE
    delta for the family.

    A placement with AGL = 0 cannot tell the two apart, which is why
    every twin here carries a real AGL."""

    AGL_M = -3.8009          # OTHH Bridge_04's own placement offset
    # The fixture boxes' authored deck top is +3.0.  The classifier would
    # record its EFFECTIVE height, so the candidate's crest must be
    # ``authored + AGL`` — a fixture that passed the authored value would
    # be internally inconsistent and could not tell the frames apart.
    CREST_EFFECTIVE = 3.0 + AGL_M

    def _seat(self, tmp_path, monkeypatch, harness, crest, *, members=None,
              obj_text=None):
        members = members or [DECK_RESOURCE]
        dsf_path, pack_root = harness.pack(
            tmp_path, monkeypatch, members,
            agl_by_resource={resource: self.AGL_M for resource in members},
            obj_text=obj_text or _BOX_OBJ_TEXT)
        result = harness.rebake(
            dsf_path, harness.mesh(tmp_path), pack_root,
            [_candidate(members, crest)])
        return result, pack_root

    def test_the_delta_is_grade_minus_crest_minus_mesh_at_anchor(
        self, tmp_path, monkeypatch, harness
    ):
        result, _pack_root = self._seat(
            tmp_path, monkeypatch, harness, self.CREST_EFFECTIVE)
        record = result["bridge_abutment_seat"][0]

        assert record["mesh_at_anchor_m"] == pytest.approx(
            WATER_ELEVATION_M, abs=1e-4)
        expected = (
            LAND_ELEVATION_M - self.CREST_EFFECTIVE - WATER_ELEVATION_M)
        assert record["seat_delta_m"] == pytest.approx(expected, abs=1e-6)
        # The superseded formula would have added |AGL| on top.
        superseded = expected - self.AGL_M
        assert record["seat_delta_m"] != pytest.approx(superseded, abs=0.1)
        assert record["achieved_deck_top_m"] == pytest.approx(
            LAND_ELEVATION_M, abs=0.01)

    def test_one_delta_for_every_member_whatever_their_anchor_grounds(
        self, tmp_path, monkeypatch, harness
    ):
        members = [DECK_RESOURCE, PIER_RESOURCE, RAIL_RESOURCE]
        result, _pack_root = self._seat(
            tmp_path, monkeypatch, harness, self.CREST_EFFECTIVE,
            members=members)
        deltas = result["bridge_abutment_seat"][0][
            "seat_delta_by_resource_m"]
        assert sorted(deltas) == sorted(members)
        assert len(set(round(value, 9) for value in deltas.values())) == 1

    def test_the_deck_top_really_lands_at_the_grade_in_world_y(
        self, tmp_path, monkeypatch, harness
    ):
        """The bake, read back off the pack and put through X-Plane's own
        placement arithmetic: world y = mesh(anchor) + AGL + baked y."""
        result, pack_root = self._seat(
            tmp_path, monkeypatch, harness, self.CREST_EFFECTIVE,
            obj_text=_PIER_OBJ_TEXT)
        assert result["bridge_abutment_seat"][0]["baked"] is True

        baked = _vertex_y_values(pack_root / DECK_RESOURCE)
        world = [WATER_ELEVATION_M + self.AGL_M + y for y in baked]
        # The authored crest IS the deck top of this box, so the top of
        # the baked geometry lands on the abutment grade...
        assert max(world) == pytest.approx(LAND_ELEVATION_M, abs=1e-3)
        # ...and the piers descend below the water line, which is the
        # whole of the owner's picture.
        assert min(world) == pytest.approx(
            LAND_ELEVATION_M - (PIER_DECK_TOP_Y_M - PIER_FOOT_Y_M),
            abs=1e-3)
        assert min(world) < WATER_ELEVATION_M


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
