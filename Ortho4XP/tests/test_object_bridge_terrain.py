"""Workstream W-B tests — object-derived bridge terrain (feature B of
``docs/object_terrain_features_spec.md``, stage 1: assembler, gate
replacement, DECK_CARRIED corridor re-source, TERRAIN/PROFILE_CARRIED
suppression, gate-off neutrality).

Fixtures are synthetic (ruling R6): :class:`BridgeStructure` records and a
minimal fake layout / DEM / DSF road network are built in code — no
third-party pack content enters the repository.  The tests drive the
DECISION logic (corridor floor, deck datum, contract partition, road
sourcing, suppression, gate off) rather than the full mesh so they stay
deterministic and independent of a scenery install.
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
from auto_patch.obj8_reader import local_offset_to_lonlat  # noqa: E402
from auto_patch.object_terrain_features import (
    BridgeStructure,
    DECK_CARRIED,
    TERRAIN_CARRIED,
    PROFILE_CARRIED,
    DECK_HARDNESS_HARD_DECK,
)

# A KBNA-ish anchor; the structure frame origin is the same point, so the
# frame→lon/lat→meter round trip is (numerically) the identity and frame
# coordinates read directly as local metres in assertions.
ANCHOR_LATITUDE = 36.124
ANCHOR_LONGITUDE = -86.678
ANCHOR = (ANCHOR_LATITUDE, ANCHOR_LONGITUDE)


@pytest.fixture(autouse=True)
def sandbox_ortho4xp_data_root(tmp_path, monkeypatch):
    """USER RULING 2026-07-15 moved the sidecar caches under the
    Ortho4XP data root (``Airport_mod_cache/<pack>/``).  In a source
    checkout the data root resolves to the current working directory, so
    without this pin any test that exercises the classification /
    road-network cache paths would write ``Airport_mod_cache/`` into the
    repository.  Sandbox every test in this module
    (``ORTHO4XP_DATA_ROOT`` wins ``O4_File_Names.resolve_data_root``)."""
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT",
                       str(tmp_path / "o4_data_root"))


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------

class _FakeDem:
    """A flat DEM: ``alt`` returns a constant for any tile-frame point."""

    def __init__(self, elevation_m: float) -> None:
        self.elevation_m = elevation_m
        self.nodata = -32768

    def alt(self, _xy) -> float:
        return self.elevation_m


class _FakeLayout:
    """Minimal layout stand-in: anchor, shapes, and the projection /
    canonical-registry surface the pin writers and the solver seeding
    touch (stage 2)."""


    def ll_to_m(self, latitude: float, longitude: float):
        return self._to_meters(longitude, latitude)

    def m_to_ll(self, x: float, y: float):
        return self._meters_to_lat_lon(x, y)


def _deck_rectangle_frame(
    length_m: float = 131.0, half_width_m: float = 27.5
) -> Polygon:
    """A deck footprint in the structure frame: a rectangle from x=0 to
    x=length along the axis, centred on z=0."""
    return Polygon(
        [
            (0.0, -half_width_m),
            (length_m, -half_width_m),
            (length_m, half_width_m),
            (0.0, half_width_m),
        ]
    )


def _bridge(
    *,
    contract: str = DECK_CARRIED,
    deck_hardness: str = DECK_HARDNESS_HARD_DECK,
    hard_deck: bool = True,
    deck_top_y_m: float = 5.99,
    clearance_underside_y_m: float | None = 4.2,
    ceiling_y_m: float | None = 4.8,
    absolute_deck_elevation_m: float | None = 167.0,
    length_m: float = 131.0,
    resource: str = "Objects/Bridges/taxiway_L.obj",
) -> BridgeStructure:
    deck_polygon = _deck_rectangle_frame(length_m=length_m)
    return BridgeStructure(
        object_resources=[resource],
        anchor_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        frame_origin_longitude_latitude=(ANCHOR_LONGITUDE, ANCHOR_LATITUDE),
        heading_degrees=0.0,
        deck_polygon=deck_polygon,
        deck_top_profile=[(0.0, deck_top_y_m), (length_m, deck_top_y_m)],
        deck_top_y_m=deck_top_y_m,
        deck_end_elevations_y_m=(deck_top_y_m, deck_top_y_m),
        deck_length_m=length_m,
        deck_width_m=55.0,
        ceiling_y_m=ceiling_y_m,
        clearance_underside_y_m=clearance_underside_y_m,
        abutment_lines=[
            ((0.0, -27.5), (0.0, 27.5)),
            ((length_m, -27.5), (length_m, 27.5)),
        ],
        abutment_reaches_grade=(True, True),
        contract=contract,
        absolute_deck_elevation_m=absolute_deck_elevation_m,
        hard_deck=hard_deck,
        deck_hardness=deck_hardness,
    )


class _Classification:
    """Just enough of ``ClassificationResult`` for the emitter."""

    def __init__(self, bridges_list) -> None:
        self.bridges = list(bridges_list)
        self.tunnels: list = []
        self.exclusions: list = []
        self.refusals: list = []


# ---------------------------------------------------------------------------
# pure decision helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# object-sourced corridor emission
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# portal OUTWARD ramp width (user ruling 2026-07-15, KBNA 02C)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# gate-off neutrality
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# assembler tile-path helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ruling R4 — Phase 2 y-bake exclusion wiring
# ---------------------------------------------------------------------------

_BRIDGE_RESOURCE = "Objects/Bridges/taxiway_L.obj"
_OTHER_RESOURCE = "Objects/Other/shed.obj"

_SYNTHETIC_DSF_LINES = [
    f"OBJECT_DEF {_BRIDGE_RESOURCE}",
    f"OBJECT_DEF {_OTHER_RESOURCE}",
    "OBJECT 0 -86.678000 36.124000 108.0",
    "OBJECT 1 -86.679000 36.125000 0.0",
]

_R4_REASON_FRAGMENT = "excluded from the Phase 2 y-bake (ruling R4)"


class TestExclusionWiringR4:
    def _run_discover(self, tmp_path, monkeypatch, excluded_resources):
        """Drive ``discover_and_rebake_airport`` against a synthetic DSF
        dump (loader monkeypatched; resources unresolvable on purpose, so
        discovery ends after the R4 filter — exactly the surface under
        test)."""
        from auto_patch import post_mesh
        from auto_patch import dsf_reader

        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text",
            lambda _path: list(_SYNTHETIC_DSF_LINES),
        )
        pack_root = str(tmp_path / "SomePack")
        os.makedirs(pack_root, exist_ok=True)
        result = post_mesh.discover_and_rebake_airport(
            str(tmp_path / "fake.dsf"),
            str(tmp_path / "fake_mesh.mesh"),
            pack_root,
            None,
            excluded_resources=excluded_resources,
        )
        return result, pack_root

    def test_excluded_resource_dropped_and_reported(
        self, tmp_path, monkeypatch
    ):
        pack_root = str(tmp_path / "SomePack")
        result, pack_root = self._run_discover(
            tmp_path, monkeypatch,
            excluded_resources={(pack_root, _BRIDGE_RESOURCE)},
        )
        r4_skips = [
            (resource, reason)
            for resource, reason in result["skipped"]
            if _R4_REASON_FRAGMENT in reason
        ]
        assert len(r4_skips) == 1, (
            f"expected exactly one R4 skip, got {result['skipped']}"
        )
        assert r4_skips[0][0] == _BRIDGE_RESOURCE
        # The non-excluded resource was NOT R4-skipped (it proceeds into
        # discovery; here it silently fails resolution, which produces no
        # skip entry) and nothing was baked.
        assert all(
            resource != _OTHER_RESOURCE for resource, _ in result["skipped"]
        )
        assert result["structures_baked"] == 0
        assert result["objects_written"] == []

    def test_all_placements_excluded_returns_early_with_reports(
        self, tmp_path, monkeypatch
    ):
        pack_root = str(tmp_path / "SomePack")
        result, pack_root = self._run_discover(
            tmp_path, monkeypatch,
            excluded_resources={
                (pack_root, _BRIDGE_RESOURCE),
                (pack_root, _OTHER_RESOURCE),
            },
        )
        r4_skipped_resources = sorted(
            resource
            for resource, reason in result["skipped"]
            if _R4_REASON_FRAGMENT in reason
        )
        assert r4_skipped_resources == sorted(
            [_BRIDGE_RESOURCE, _OTHER_RESOURCE]
        )
        assert result["objects_written"] == []
        assert result["structures_baked"] == 0

    def test_no_exclusions_is_the_pre_change_behaviour(
        self, tmp_path, monkeypatch
    ):
        result, _pack_root = self._run_discover(
            tmp_path, monkeypatch, excluded_resources=None
        )
        assert not any(
            _R4_REASON_FRAGMENT in reason
            for _resource, reason in result["skipped"]
        )


# ---------------------------------------------------------------------------
# classification reads AUTHORED geometry (ruling R1 parity)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# cold-scan progress (2026-08-09: the app window looked hung for ~8 min
# while the OTHH Aeroscape pack's classification cache rebuilt with no
# progress event — the cold classify path now reports through
# progress.substep, the channel the driver's pool queue drains)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2 — bridge laws (grade_law lockstep source)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2 — deck-end pin insertion (seam-anchor idiom)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2 — solver seeding honours the bridge pin registry
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2 — crossing floor producer + validator lockstep
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2b — capture band, causeway plates, road-carried, deconflict order
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2b iteration 3 — routing-evidence discriminator + R8 flush seat
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ruling R12 — building-pad removal + by-construction pass immunity
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stage 2b iteration 5 — approach keep-out + lip coverage geometry
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ruling R4 breadth (round 6) — anchor-family sibling exclusion
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# round 8 — flat-by-law plates ship per-node alt_abs (mesh-consumer reality)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# per-DSF sibling road-network sidecar cache
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2026-07-15 defects A+B (KBNA Donelson) — approach-chain continuity,
# [H,L,L,H] slope orientation, and the corridor-plate weld
# ---------------------------------------------------------------------------


def _open_ring(polygon):
    ring = list(polygon.exterior.coords)
    return ring[:-1] if ring[0] == ring[-1] else ring


# ---------------------------------------------------------------------------
# W1b — the deck-flush outcome (owner ruling 2026-07-31)
# ---------------------------------------------------------------------------


class TestBridgeRampFillLaw:
    """The grade-capped FILL envelope — the mirror of the OLS road cut.

    ``z(s) = max(ground(s), deck_end - grade * s)``.  Two properties make
    it a ramp rather than the linear blend the tunnel corridor uses:
    it never cuts below the DEM, and its descent is capped.
    """

    @staticmethod
    def _profile(deck_end, grounds, step, grade):
        return [
            max(ground, deck_end - grade * (index * step))
            for index, ground in enumerate(grounds)
        ]

    def test_never_cuts_below_the_ground(self):
        """A rise between the deck end and the ramp's end must not be
        dug through — the linear blend to the far ground would."""
        deck_end = 1.0
        grounds = [0.0, 0.0, 6.0, 0.0, 0.0]      # a knoll at station 2
        profile = self._profile(deck_end, grounds, 10.0, 0.04)
        assert all(z >= g - 1e-9 for z, g in zip(profile, grounds))
        linear = [
            (1.0 - i / 4.0) * deck_end + (i / 4.0) * grounds[i]
            for i in range(5)
        ]
        assert linear[2] < grounds[2], (
            "the tunnel-corridor blend digs through the knoll — the "
            "reason the ramp needs its own law"
        )

    def test_descent_is_grade_capped(self):
        grade, step = 0.04, 10.0
        grounds = [0.0] * 40
        profile = self._profile(10.0, grounds, step, grade)
        for near, far in zip(profile, profile[1:]):
            assert (near - far) <= grade * step + 1e-9

    def test_anchored_exactly_on_the_deck_end(self):
        profile = self._profile(3.0, [0.0] * 10, 10.0, 0.04)
        assert profile[0] == pytest.approx(3.0)

    def test_reaches_the_ground_and_stays(self):
        """Past the point where the cap has shed the whole rise the ramp
        is the ground — no plate hovering over terrain."""
        grade, step, deck_end = 0.04, 10.0, 1.2
        profile = self._profile(deck_end, [0.0] * 12, step, grade)
        settled = deck_end / grade          # 30 m
        for index, z in enumerate(profile):
            if index * step > settled:
                assert z == pytest.approx(0.0)

    def test_config_defaults_are_sane(self):
        assert config.OBJECT_BRIDGE_RAMP in (True, False)
        assert config.BRIDGE_RAMP_MIN_RISE_M > 0.0
        assert config.BRIDGE_RAMP_MAX_LENGTH_M > config.BRIDGE_RAMP_STEP_M
        # One navigable-ramp number shared with the tunnel ramp.
        assert config.TUNNEL_RAMP_MAX_GRADE > 0.0


# ---------------------------------------------------------------------------
# R6-3 — flush-deck bridges over water seat at abutment grade
# (docs/specs/round6-othh-residuals-spec.md, owner in-sim residual)
# ---------------------------------------------------------------------------

# The mesh under the synthetic bridge: a square of WATER around the
# anchor (OTHH Bridge_01 samples 0.00 m at its anchor and at every deck
# station) with LAND everywhere outside it — the ground the certified
# abutments actually stand on.
_SEAT_MESH_EXTENT_M = 200.0
_SEAT_MESH_STEP_M = 10.0
_SEAT_WATER_HALF_SPAN_M = 50.0
_SEAT_WATER_ELEVATION_M = 0.0
_SEAT_LAND_ELEVATION_M = 3.96

_SEAT_RESOURCE = "Objects/Bridges/bridge_01.obj"

# The seat tests read the BAKED y values back, and the rewriter preserves
# each token's authored decimal precision verbatim (invariant I-16), so a
# ``0.0`` source would quantize a 3.96 m seat to 4.0.  Six decimals here:
# the arithmetic under test must be visible, not rounded away.
_SEAT_BOX_OBJ_TEXT = "\n".join([
    "A",
    "800",
    "OBJ",
    "",
    "POINT_COUNTS 8 0 0 12",
    "VT -20.000000 0.000000 -20.000000 0 1 0 0 0",
    "VT 20.000000 0.000000 -20.000000 0 1 0 0 0",
    "VT 20.000000 0.000000 20.000000 0 1 0 0 0",
    "VT -20.000000 0.000000 20.000000 0 1 0 0 0",
    "VT -20.000000 3.000000 -20.000000 0 1 0 0 0",
    "VT 20.000000 3.000000 -20.000000 0 1 0 0 0",
    "VT 20.000000 3.000000 20.000000 0 1 0 0 0",
    "VT -20.000000 3.000000 20.000000 0 1 0 0 0",
    "IDX10 0 1 2 0 2 3 4 5 6 4",
    "IDX 6",
    "IDX 7",
    "TRIS 0 12",
]) + "\n"


def _write_two_level_mesh(mesh_path, *, water_half_span_m,
                          water_elevation_m, land_elevation_m) -> None:
    """A built-mesh dump: ``water_elevation_m`` inside a square of
    ``water_half_span_m`` about the anchor, ``land_elevation_m`` outside.

    Same writer shape as the basin suite's trench mesh — the sampler
    reads a MeshVersionFormatted dump whose z is in 100 km units.
    """
    steps = int(2 * _SEAT_MESH_EXTENT_M / _SEAT_MESH_STEP_M) + 1
    coordinates = [
        -_SEAT_MESH_EXTENT_M + index * _SEAT_MESH_STEP_M
        for index in range(steps)
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
                water_elevation_m if inside else land_elevation_m,
            ))
    triangles = []
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


class TestBridgeAbutmentSeat:
    """R6-3, post-mesh side.  OTHH ``Bridge_01`` is a cosmetic flush deck
    classified TERRAIN_CARRIED: its resources are R4-EXCLUDED from the
    y-bake and it simply drapes — and its anchor sits over WATER, so it
    draped ~3.96 m below the ground its own abutments stand on.  The law
    lifts it to the abutment-grade median; a bridge whose anchor samples
    land within the reseat threshold is left exactly as before."""

    @pytest.fixture(autouse=True)
    def _sandbox(self, tmp_path, monkeypatch):
        # Every sidecar cache under the test's own root, and off: the arm
        # must compute, never inherit another arm's answer.
        monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "o4root"))
        monkeypatch.setenv("O4_OBJECT_EXCLUSION_CACHE", "0")
        monkeypatch.setenv("O4_OBJECT_PARTITION_CACHE", "0")
        monkeypatch.setenv("O4_REANCHOR_SHORT_CIRCUIT", "0")

    def _pack(self, tmp_path, monkeypatch):
        from auto_patch import dsf_reader

        pack_root = tmp_path / "OTHH-TEST Pack"
        (pack_root / _SEAT_RESOURCE).parent.mkdir(parents=True,
                                                  exist_ok=True)
        (pack_root / _SEAT_RESOURCE).write_text(_SEAT_BOX_OBJ_TEXT, encoding="utf-8", newline="")
        dsf_path = pack_root / "overlay.dsf"
        dsf_path.write_bytes(b"")
        monkeypatch.setattr(
            dsf_reader, "_load_dsf_text",
            lambda _path: [
                f"OBJECT_DEF {_SEAT_RESOURCE}",
                f"OBJECT 0 {ANCHOR_LONGITUDE} {ANCHOR_LATITUDE} 0.0",
            ])
        return dsf_path, pack_root


    def _mesh(self, tmp_path, *, water=True):
        mesh_path = tmp_path / "Data+36-087.mesh"
        _write_two_level_mesh(
            mesh_path,
            # -1 m: NO vertex is inside, so the whole mesh is land.
            # (0.0 would still put the anchor vertex itself in the water.)
            water_half_span_m=(_SEAT_WATER_HALF_SPAN_M if water else -1.0),
            water_elevation_m=_SEAT_WATER_ELEVATION_M,
            land_elevation_m=_SEAT_LAND_ELEVATION_M,
        )
        return mesh_path

    def _rebake(self, dsf_path, mesh_path, pack_root, candidates, **kwargs):
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


    def test_no_candidates_leaves_the_pass_unchanged(
        self, tmp_path, monkeypatch
    ):
        """The degeneracy gate: with no candidate the result carries an
        empty record list and nothing else differs."""
        dsf_path, pack_root = self._pack(tmp_path, monkeypatch)
        mesh_path = self._mesh(tmp_path)
        result = self._rebake(dsf_path, mesh_path, pack_root, [])
        assert result["bridge_abutment_seat"] == []
