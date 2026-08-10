"""Post-mesh DSF object re-anchor stage — workstream W7 of the DSF
object integration (``docs/dsf_object_integration_spec.md`` section
4-W7, as amended by A4/A5/A13).

Everything is hermetic under ``tmp_path``: a fake tile is a
``types.SimpleNamespace``, the scenery pack and its ``.dsf`` are
synthetic (harness pattern (b) from ``tests/test_dsf_buildings.py`` —
fake ``.dsf`` plus a pre-seeded, mtime-backdated ``.dsf.text`` and a
monkeypatched ``_dsftool_path``), and the mesh is a small hand-written
two-triangle plane in the exact ``O4_Mesh_Utils.write_mesh_file`` format
(see ``tests/test_mesh_sampler.py``'s fixture).  No real X-Plane packs
or meshes are ever touched.

The synthetic terrain is a plane whose elevation depends only on the
longitude, so the expected per-structure offset is computable in closed
form: ``delta = (centroid_longitude - anchor_longitude) * SLOPE``.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import types

import pytest

import O4_File_Names as FNAMES
import O4_Mesh_Utils
import O4_UI_Utils as UI
from auto_patch import config
from auto_patch import driver
from auto_patch import dsf_reader as D
from auto_patch import obj8_reader, object_rebake, post_mesh

TILE_LATITUDE = 35
TILE_LONGITUDE = -81
TILE_NAME = "+35-081"

ANCHOR_LATITUDE = 35.21
ANCHOR_LONGITUDE = -80.93

# The synthetic mesh: one square split into two triangles, elevation a
# linear function of the longitude alone (barycentric interpolation of a
# linear function is exact, so the sampler reproduces the plane).
MESH_WEST_LONGITUDE = ANCHOR_LONGITUDE - 0.002
MESH_EAST_LONGITUDE = ANCHOR_LONGITUDE + 0.002
MESH_SOUTH_LATITUDE = ANCHOR_LATITUDE - 0.002
MESH_NORTH_LATITUDE = ANCHOR_LATITUDE + 0.002
ELEVATION_SLOPE_PER_DEGREE = 10000.0
BASE_ELEVATION = 100.0


def _plane_elevation(longitude: float) -> float:
    return BASE_ELEVATION + (
        longitude - MESH_WEST_LONGITUDE
    ) * ELEVATION_SLOPE_PER_DEGREE


def _write_synthetic_mesh(mesh_path: str) -> None:
    corner_positions = [
        (MESH_WEST_LONGITUDE, MESH_SOUTH_LATITUDE),
        (MESH_EAST_LONGITUDE, MESH_SOUTH_LATITUDE),
        (MESH_EAST_LONGITUDE, MESH_NORTH_LATITUDE),
        (MESH_WEST_LONGITUDE, MESH_NORTH_LATITUDE),
    ]
    lines = ["MeshVersionFormatted 2", "Dimension 3", "", "Vertices", "4"]
    for longitude, latitude in corner_positions:
        scaled_elevation = _plane_elevation(longitude) / 100000.0
        lines.append(
            f"{longitude:.15f} {latitude:.15f} {scaled_elevation:.15f} 0"
        )
    lines += ["", "Normals", "0", "", "Triangles", "2",
              "1 2 3 0", "1 3 4 0"]
    os.makedirs(os.path.dirname(mesh_path), exist_ok=True)
    with open(mesh_path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


# A 10 x 10 metre slab whose geometry sits 30..40 m east and south of
# its anchor (solid reach ~56.6 m, past the 25 m detector floor), at
# authored y = 0 — the offset-geometry case Phase 2 exists for.
OFFSET_SLAB_OBJECT = "\n".join([
    "A",
    "800",
    "OBJ",
    "",
    "POINT_COUNTS 4 0 0 6",
    "VT 30.000000 0.000000 30.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 40.000000 0.000000 30.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 40.000000 0.000000 40.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 30.000000 0.000000 40.000000 0.0 1.0 0.0 0.0 0.0",
    "IDX10 0 1 2 0 2 3",
    "TRIS 0 6",
]) + "\n"

# The slab's local centroid — used to compute the expected offset.
SLAB_LOCAL_CENTROID_EAST = 35.0
SLAB_LOCAL_CENTROID_SOUTH = 35.0


def _expected_slab_offset() -> float:
    _centroid_latitude, centroid_longitude = (
        obj8_reader.local_offset_to_lonlat(
            ANCHOR_LATITUDE,
            ANCHOR_LONGITUDE,
            0.0,
            SLAB_LOCAL_CENTROID_EAST,
            SLAB_LOCAL_CENTROID_SOUTH,
        )
    )
    return (
        centroid_longitude - ANCHOR_LONGITUDE
    ) * ELEVATION_SLOPE_PER_DEGREE


def _make_pack(base_directory, pack_name: str, dsf_body: str,
               objects_by_resource: dict) -> tuple[str, str]:
    """Harness pattern (b): fake ``.dsf`` + pre-seeded, backdated
    ``.dsf.text`` under ``<pack>/Earth nav data/<group>/``, plus the
    pack's ``.obj`` files.  Returns ``(dsf_path, pack_root)``."""
    pack_root = base_directory / pack_name
    dsf_directory = pack_root / "Earth nav data" / "+30-090"
    dsf_directory.mkdir(parents=True)
    dsf = dsf_directory / (TILE_NAME + ".dsf")
    dsf.write_text("binary-placeholder")
    text = dsf_directory / (TILE_NAME + ".dsf.text")
    text.write_text(dsf_body)
    now = os.path.getmtime(text)
    os.utime(dsf, (now - 10, now - 10))
    for resource_path, content in objects_by_resource.items():
        physical = pack_root.joinpath(*resource_path.split("/"))
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_text(content)
    return str(dsf), str(pack_root)


def _vertex_y_values(object_path: str) -> list[float]:
    values = []
    with open(object_path) as handle:
        for line in handle:
            tokens = line.split()
            if tokens and tokens[0] == "VT":
                values.append(float(tokens[2]))
    return values


SINGLE_PLACEMENT_DSF_BODY = "\n".join([
    "OBJECT_DEF objects/offset_bake.obj",
    f"OBJECT 0 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE:.9f} 0.000000",
]) + "\n"

# A two-foot gantry with an author-BAKED vertical offset (multi-ground-
# cluster re-anchor, project memory kbna-gantry-pond-multi-foot-objects):
# two vertical foot quads (authored bases +6.5 and +7.7) joined by a
# 40 m deck along the EAST axis — across the synthetic plane's slope,
# so no rigid offset can seat both feet and the west foot must raise a
# terrain-pad request.
def _two_foot_gantry_object(span_metres: float) -> str:
    east_far = span_metres
    east_foot_b = span_metres - 2.0
    return "\n".join([
        "A",
        "800",
        "OBJ",
        "",
        "POINT_COUNTS 12 0 0 18",
        "VT 0.000000 6.500000 0.000000 0.0 1.0 0.0 0.0 0.0",
        "VT 2.000000 6.500000 0.000000 0.0 1.0 0.0 0.0 0.0",
        "VT 2.000000 9.200000 0.000000 0.0 1.0 0.0 0.0 0.0",
        "VT 0.000000 9.200000 0.000000 0.0 1.0 0.0 0.0 0.0",
        "VT 0.000000 9.200000 0.000000 0.0 1.0 0.0 0.0 0.0",
        f"VT {east_far:.6f} 9.200000 0.000000 0.0 1.0 0.0 0.0 0.0",
        f"VT {east_far:.6f} 9.200000 2.000000 0.0 1.0 0.0 0.0 0.0",
        "VT 0.000000 9.200000 2.000000 0.0 1.0 0.0 0.0 0.0",
        f"VT {east_foot_b:.6f} 7.700000 0.000000 0.0 1.0 0.0 0.0 0.0",
        f"VT {east_far:.6f} 7.700000 0.000000 0.0 1.0 0.0 0.0 0.0",
        f"VT {east_far:.6f} 9.200000 0.000000 0.0 1.0 0.0 0.0 0.0",
        f"VT {east_foot_b:.6f} 9.200000 0.000000 0.0 1.0 0.0 0.0 0.0",
        "IDX10 0 1 2 0 2 3 4 5 6 4",
        "IDX10 6 7 8 9 10 8 10 11",
        "TRIS 0 18",
    ]) + "\n"


TWO_FOOT_GANTRY_OBJECT = _two_foot_gantry_object(40.0)

TWO_FOOT_GANTRY_DSF_BODY = "\n".join([
    "OBJECT_DEF objects/gantry.obj",
    f"OBJECT 0 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE:.9f} 0.000000",
]) + "\n"


class Harness:
    pass


@pytest.fixture(autouse=True)
def sandbox_ortho4xp_data_root(tmp_path, monkeypatch):
    """The partition sidecar cache lands under the Ortho4XP data root
    (``Airport_mod_cache/<pack>/``), which in a source checkout resolves
    to the current working directory — without this pin the tests here
    would write ``Airport_mod_cache/`` into the repository (same sandbox
    as test_dsf_object_buildings.py)."""
    monkeypatch.setenv(
        "ORTHO4XP_DATA_ROOT", str(tmp_path / "o4_data_root"))


@pytest.fixture()
def phase_two_harness(tmp_path, monkeypatch):
    """A fake tile, a synthetic mesh at ``FNAMES.mesh_file(...)``, a
    Patches directory redirected into ``tmp_path``, the DSFTool
    monkeypatch, and the re-anchor flag ON."""
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    monkeypatch.setattr(config, "DSF_OBJECT_REANCHOR", True)

    patches_directory = tmp_path / "Patches" / TILE_NAME
    patches_directory.mkdir(parents=True)
    monkeypatch.setattr(
        FNAMES, "patch_dir",
        lambda latitude, longitude: str(patches_directory))

    build_directory = tmp_path / "Tiles" / ("zOrtho4XP_" + TILE_NAME)
    build_directory.mkdir(parents=True)
    tile = types.SimpleNamespace(
        lat=TILE_LATITUDE, lon=TILE_LONGITUDE,
        build_dir=str(build_directory))
    mesh_path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
    _write_synthetic_mesh(mesh_path)

    harness = Harness()
    harness.tmp_path = tmp_path
    harness.tile = tile
    harness.mesh_path = mesh_path
    harness.patches_directory = patches_directory
    harness.worklist_path = patches_directory / (
        post_mesh.OBJECT_ANCHOR_WORKLIST_FILENAME)

    def write_worklist(airports):
        payload = {
            "version": post_mesh.OBJECT_ANCHOR_WORKLIST_VERSION,
            "tile": TILE_NAME,
            "xplane_root": None,
            "airports": airports,
        }
        harness.worklist_path.write_text(
            json.dumps(payload, indent=2) + "\n")

    harness.write_worklist = write_worklist

    def worklist_entry(icao, dsf_path, pack_root, dsf_mtime=None):
        return {
            "icao": icao,
            "dsf_path": dsf_path,
            "dsf_mtime": (
                dsf_mtime if dsf_mtime is not None
                else os.path.getmtime(dsf_path)),
            "pack_root": pack_root,
            "xplane_root": None,
        }

    harness.worklist_entry = worklist_entry
    return harness


# ── flag gating and worklist presence ────────────────────────────────

def test_flag_off_returns_empty_without_reading_anything(monkeypatch):
    """With the flag off (the default) the function returns ``{}``
    BEFORE deriving the worklist path or reading any file — the sentinel
    ``patch_dir`` raises if consulted."""
    monkeypatch.setattr(config, "DSF_OBJECT_REANCHOR", False)

    def exploding_patch_dir(latitude, longitude):
        raise AssertionError(
            "the worklist path must not be derived with the flag off")

    monkeypatch.setattr(FNAMES, "patch_dir", exploding_patch_dir)
    tile = types.SimpleNamespace(lat=35, lon=-81, build_dir="/nonexistent")
    assert post_mesh.rebake_dsf_objects(tile) == {}


def test_missing_worklist_returns_empty_without_error(phase_two_harness):
    assert post_mesh.rebake_dsf_objects(phase_two_harness.tile) == {}


def test_missing_mesh_reports_and_returns_zero_counts(
        phase_two_harness, monkeypatch):
    harness = phase_two_harness
    os.remove(harness.mesh_path)
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    messages = []
    monkeypatch.setattr(
        UI, "vprint",
        lambda level, *message_parts: messages.append(
            (level, " ".join(str(part) for part in message_parts))))
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert counts == {key: 0 for key in post_mesh._COUNT_KEYS}
    assert any("mesh not found" in message for _level, message in messages)


# ── the end-to-end bake ──────────────────────────────────────────────

def test_end_to_end_bake_rewrites_live_file_with_backup_and_provenance(
        phase_two_harness):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])

    counts = post_mesh.rebake_dsf_objects(harness.tile)

    assert counts["airports_processed"] == 1
    assert counts["packs_corrected"] == 1
    assert counts["structures_baked"] == 1
    assert counts["structures_needing_pad"] == 0
    assert counts["vertices_offset"] == 4
    assert counts["objects_skipped"] == 0
    assert counts["airports_failed"] == 0

    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    backup_path = live_path + ".anchor_bak"
    assert os.path.isfile(backup_path)
    with open(backup_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT

    expected_offset = _expected_slab_offset()
    assert expected_offset > 1.0  # the fixture genuinely slopes
    for y_value in _vertex_y_values(live_path):
        assert y_value == pytest.approx(expected_offset, abs=1e-4)

    provenance_path = os.path.join(
        pack_root, ".o4_reanchor_provenance.json")
    assert os.path.isfile(provenance_path)
    with open(provenance_path) as handle:
        provenance = json.load(handle)
    assert "objects/offset_bake.obj" in provenance["objects"]
    assert TILE_NAME in provenance["meshes"]


# ── the reseat threshold, end to end ─────────────────────────────────

# The same 10 x 10 m slab, moved SOUTH instead of east: the synthetic
# plane's elevation depends on the longitude alone, so a slab this far
# from its anchor still clears the 25 m reach floor while needing only a
# sub-metre correction — the OTHH population the reseat threshold hands
# to the terrain side (spec section 2.1, 74 % of measured clusters).
SOUTH_SLAB_OBJECT = "\n".join([
    "A",
    "800",
    "OBJ",
    "",
    "POINT_COUNTS 4 0 0 6",
    "VT 0.000000 0.000000 40.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 10.000000 0.000000 40.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 10.000000 0.000000 50.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 0.000000 0.000000 50.000000 0.0 1.0 0.0 0.0 0.0",
    "IDX10 0 1 2 0 2 3",
    "TRIS 0 6",
]) + "\n"

SOUTH_SLAB_LOCAL_CENTROID_EAST = 5.0
SOUTH_SLAB_LOCAL_CENTROID_SOUTH = 45.0


def _expected_south_slab_offset() -> float:
    _centroid_latitude, centroid_longitude = (
        obj8_reader.local_offset_to_lonlat(
            ANCHOR_LATITUDE,
            ANCHOR_LONGITUDE,
            0.0,
            SOUTH_SLAB_LOCAL_CENTROID_EAST,
            SOUTH_SLAB_LOCAL_CENTROID_SOUTH,
        )
    )
    return (
        centroid_longitude - ANCHOR_LONGITUDE
    ) * ELEVATION_SLOPE_PER_DEGREE


def _provenance_objects(pack_root: str) -> dict:
    """The sidecar's BAKED-OBJECT entries (``{}`` when the pack was
    never modified), independent of the run fingerprint stored beside
    them."""
    path = os.path.join(pack_root, ".o4_reanchor_provenance.json")
    if not os.path.isfile(path):
        return {}
    with open(path) as handle:
        return json.load(handle).get("objects", {})


def _single_slab_worklist(harness, object_text):
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": object_text})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    return pack_root, os.path.join(
        pack_root, "objects", "offset_bake.obj")


def test_a_below_threshold_pack_is_never_touched(phase_two_harness):
    """Spec section 2.4, the owner's stated preference: an airport whose
    every unit deviates under a metre ends the run with an UNTOUCHED
    pack — no backup, no provenance, no write."""
    harness = phase_two_harness
    pack_root, live_path = _single_slab_worklist(harness, SOUTH_SLAB_OBJECT)
    assert abs(_expected_south_slab_offset()) < 1.0  # the premise

    counts = post_mesh.rebake_dsf_objects(harness.tile)

    assert counts["airports_processed"] == 1  # the pass ran
    assert counts["structures_baked"] == 0
    assert counts["vertices_offset"] == 0
    assert counts["units_below_bake_threshold"] == 1
    assert counts["packs_corrected"] == 0
    with open(live_path) as handle:
        assert handle.read() == SOUTH_SLAB_OBJECT
    assert not os.path.exists(live_path + ".anchor_bak")
    # The pack's own content is untouched.  The sidecar may still hold
    # this run's FINGERPRINT (the short-circuit cache every run writes,
    # baked or not — pre-existing behaviour, and what keeps a flat
    # airport's next build cheap), but it records no baked object.
    assert _provenance_objects(pack_root) == {}


def test_a_previous_bake_is_reverted_when_the_threshold_excludes_it(
        phase_two_harness, monkeypatch):
    """Spec section 4's reversion witness: a pack baked under the old
    always-bake law converges back to its authored bytes on the next
    build, because a below-threshold unit is excluded-from-bake exactly
    like a refused one."""
    harness = phase_two_harness
    pack_root, live_path = _single_slab_worklist(harness, SOUTH_SLAB_OBJECT)
    # Captured, never ``monkeypatch.undo()``: undo would also tear down
    # this harness's sandbox (the ``FNAMES.patch_dir`` redirect and the
    # DSFTool stub), and the pass would then read the REAL worklist for
    # this tile and touch an installed pack.
    shipping_threshold = config.DSF_OBJECT_BAKE_MIN_DELTA_M

    # Round 1: the pre-2026-08-09 law (threshold disabled) bakes it.
    monkeypatch.setattr(config, "DSF_OBJECT_BAKE_MIN_DELTA_M", 0.0)
    first = post_mesh.rebake_dsf_objects(harness.tile)
    assert first["structures_baked"] == 1
    with open(live_path) as handle:
        assert handle.read() != SOUTH_SLAB_OBJECT
    assert os.path.isfile(live_path + ".anchor_bak")

    # Round 2: the threshold back at its shipping value.  The bake is
    # undone from the backup — a stale reseat is exactly what the owner
    # asked not to have.
    monkeypatch.setattr(
        config, "DSF_OBJECT_BAKE_MIN_DELTA_M", shipping_threshold)
    second = post_mesh.rebake_dsf_objects(harness.tile)
    assert second["objects_reverted"] == 1
    assert second["structures_baked"] == 0
    with open(live_path) as handle:
        assert handle.read() == SOUTH_SLAB_OBJECT


def test_measure_only_runs_the_pass_and_writes_nothing(phase_two_harness):
    """Spec section 2.3: ``modify_custom_airports`` off gates PACK
    MODIFICATION, not the pass.  A metre-class correction the default law
    would bake is measured, routed as below-threshold, and the installed
    package stays exactly as its author shipped it."""
    harness = phase_two_harness
    harness.tile.modify_custom_airports = False
    pack_root, live_path = _single_slab_worklist(harness, OFFSET_SLAB_OBJECT)
    assert _expected_slab_offset() > 1.0  # the default law WOULD bake it

    counts = post_mesh.rebake_dsf_objects(harness.tile)

    assert counts["airports_processed"] == 1
    assert counts["structures_baked"] == 0
    assert counts["vertices_offset"] == 0
    assert counts["units_below_bake_threshold"] == 1
    with open(live_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT
    assert not os.path.exists(live_path + ".anchor_bak")
    assert _provenance_objects(pack_root) == {}


def test_measure_only_still_reverts_an_earlier_bake(phase_two_harness):
    """The state the switch exists to prevent: a pack baked while it was
    ON must not stay baked once it is OFF.  The run record cannot
    short-circuit the reversion either — ``measure_only`` is part of the
    gate digest."""
    harness = phase_two_harness
    _pack_root, live_path = _single_slab_worklist(
        harness, OFFSET_SLAB_OBJECT)

    baked = post_mesh.rebake_dsf_objects(harness.tile)
    assert baked["structures_baked"] == 1
    with open(live_path) as handle:
        assert handle.read() != OFFSET_SLAB_OBJECT

    harness.tile.modify_custom_airports = False
    measured = post_mesh.rebake_dsf_objects(harness.tile)
    assert measured["airports_up_to_date"] == 0  # no stale short-circuit
    assert measured["objects_reverted"] == 1
    with open(live_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT


def test_measure_only_still_records_the_pad_requests(phase_two_harness):
    """Requests are the terrain side's input, and the switch does not
    gate terrain: the foot-pad sidecar is written exactly as it would
    have been (spec section 2.3)."""
    harness = phase_two_harness
    harness.tile.modify_custom_airports = False
    _pack_root, live_path = _single_slab_worklist(
        harness, _two_foot_gantry_object(40.0))

    post_mesh.rebake_dsf_objects(harness.tile)

    sidecar_path = os.path.join(
        str(harness.patches_directory),
        post_mesh.OBJECT_FOOT_PAD_SIDECAR_FILENAME)
    assert os.path.isfile(sidecar_path)
    with open(sidecar_path) as handle:
        sidecar = json.load(handle)
    requests = sidecar["airports"][0]["requests"]
    assert requests, "the terrain side still learns what the pack kept"
    assert all(request["rings_lonlat"] for request in requests)
    with open(live_path) as handle:
        assert handle.read() == _two_foot_gantry_object(40.0)


def test_idempotent_through_the_full_path(phase_two_harness):
    """Two full ``rebake_dsf_objects`` runs leave the pack byte-identical
    (delegates the guarantee to invariant I-15, proves the wiring passes
    backups correctly — including discovery reading the ``.anchor_bak``
    original on the second run)."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    backup_path = live_path + ".anchor_bak"

    first_counts = post_mesh.rebake_dsf_objects(harness.tile)
    with open(live_path, "rb") as handle:
        live_after_first_run = handle.read()
    with open(backup_path, "rb") as handle:
        backup_after_first_run = handle.read()

    second_counts = post_mesh.rebake_dsf_objects(harness.tile)
    with open(live_path, "rb") as handle:
        live_after_second_run = handle.read()
    with open(backup_path, "rb") as handle:
        backup_after_second_run = handle.read()

    assert live_after_first_run == live_after_second_run
    assert backup_after_first_run == backup_after_second_run
    assert first_counts["structures_baked"] == 1
    assert second_counts["structures_baked"] == 1


def test_idempotent_rerun_does_not_touch_the_live_file(phase_two_harness):
    """A byte-identical re-bake must not REWRITE the live ``.obj`` — the
    old unconditional write churned mtimes, invalidating every
    mtime-fingerprinted pack sidecar (classification, footprints, road
    network) and X-Plane's object cache on every mesh build."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")

    post_mesh.rebake_dsf_objects(harness.tile)
    backdated = os.path.getmtime(live_path) - 1000.0
    os.utime(live_path, (backdated, backdated))

    post_mesh.rebake_dsf_objects(harness.tile)
    assert os.path.getmtime(live_path) == pytest.approx(backdated), (
        "identical re-bake rewrote the live file (mtime churn)")


# ── partition sidecar cache (Airport_mod_cache/<pack>/) ─────────────


def test_partition_cache_serves_second_run_and_content_invalidates(
        phase_two_harness, monkeypatch):
    """Run 2 takes its partition from the pack sidecar cache (the
    partition is pure pack geometry — 2026-07-15 profile put it at 195 s
    of the 385 s KBNA rebake) and bakes identically; changing the
    geometry SOURCE bytes invalidates the content-hash key."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")

    partition_calls = []
    real_partition = post_mesh.object_anchor.partition_structures

    def counting_partition(*args, **kwargs):
        partition_calls.append(1)
        return real_partition(*args, **kwargs)

    monkeypatch.setattr(
        post_mesh.object_anchor, "partition_structures",
        counting_partition)

    first_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert first_counts["structures_baked"] == 1
    assert len(partition_calls) == 1
    with open(live_path, "rb") as handle:
        live_after_first_run = handle.read()

    second_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert second_counts["structures_baked"] == 1
    assert len(partition_calls) == 1  # served from the sidecar cache
    with open(live_path, "rb") as handle:
        assert handle.read() == live_after_first_run

    # Content invalidation: the geometry source after run 1 is the
    # ``.anchor_bak`` original (ruling R1) — rewriting it with different
    # bytes must recompute the partition, not serve the stale entry.
    backup_path = live_path + ".anchor_bak"
    with open(backup_path) as handle:
        original = handle.read()
    with open(backup_path, "w") as handle:
        handle.write(original + "# trailing comment changes the bytes\n")
    post_mesh.rebake_dsf_objects(harness.tile)
    assert len(partition_calls) == 2


def test_partition_cache_disabled_by_environment_flag(
        phase_two_harness, monkeypatch):
    monkeypatch.setenv("O4_OBJECT_PARTITION_CACHE", "0")
    # This test is about the PARTITION cache only; the outer re-anchor
    # short-circuit would skip run 2 before the partition is reached.
    monkeypatch.setenv("O4_REANCHOR_SHORT_CIRCUIT", "0")
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])

    partition_calls = []
    real_partition = post_mesh.object_anchor.partition_structures

    def counting_partition(*args, **kwargs):
        partition_calls.append(1)
        return real_partition(*args, **kwargs)

    monkeypatch.setattr(
        post_mesh.object_anchor, "partition_structures",
        counting_partition)

    post_mesh.rebake_dsf_objects(harness.tile)
    post_mesh.rebake_dsf_objects(harness.tile)
    assert len(partition_calls) == 2  # no cache with the flag off


# ── multi-ground-cluster foot pads (sidecar) ─────────────────────────


def test_foot_pad_sidecar_written_and_removed(
        phase_two_harness, monkeypatch):
    """A baked-offset two-foot gantry across the plane's slope: the
    rigid offset seats only the topmost-target foot, the other raises a
    terrain-pad request, and ``rebake_dsf_objects`` records it in the
    per-tile sidecar — refreshed on the next run (removed here, since
    the gate turned off leaves no request)."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Gantry Pack", TWO_FOOT_GANTRY_DSF_BODY,
        {"objects/gantry.obj": TWO_FOOT_GANTRY_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])

    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert counts["structures_baked"] == 1
    assert counts["foot_pad_requests"] == 1

    sidecar_path = harness.patches_directory / (
        post_mesh.OBJECT_FOOT_PAD_SIDECAR_FILENAME)
    payload = json.loads(sidecar_path.read_text())
    assert payload["version"] == post_mesh.OBJECT_FOOT_PAD_SIDECAR_VERSION
    (airport,) = payload["airports"]
    assert airport["icao"] == "KTST"
    assert airport["pack_root"] == pack_root
    (request,) = airport["requests"]
    assert request["resource_path"] == "objects/gantry.obj"
    assert request["base_y"] == pytest.approx(6.5, abs=1e-9)
    # The west foot floats by the slope between the feet minus the
    # authored base difference (contact centroids 38 m apart east).
    west_ground = _plane_elevation(obj8_reader.local_offset_to_lonlat(
        ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0, 1.0, 0.0)[1])
    east_ground = _plane_elevation(obj8_reader.local_offset_to_lonlat(
        ANCHOR_LATITUDE, ANCHOR_LONGITUDE, 0.0, 39.0, 0.0)[1])
    expected_residual = (east_ground - west_ground) - (7.7 - 6.5)
    assert expected_residual > config.DSF_OBJECT_FOOT_PAD_RESIDUAL_M
    assert request["residual_metres"] == pytest.approx(
        expected_residual, abs=1e-2)
    assert request["target_ground_metres"] == pytest.approx(
        west_ground + expected_residual, abs=1e-2)
    # A FOOT IS ONE CONTACT PART, so the footprint-hugging law
    # (object-reseat-threshold-spec §2.5) gives it exactly one ring.
    rings = request["rings_lonlat"]
    assert len(rings) == 1
    ring = rings[0]
    assert ring is not None and len(ring) >= 3
    assert all(len(point) == 2 for point in ring)

    # Gate off, run again: no request remains, the stale sidecar goes.
    monkeypatch.setattr(config, "DSF_OBJECT_FOOT_ANCHOR", False)
    second_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert second_counts["foot_pad_requests"] == 0
    assert not sidecar_path.exists()


REACH_FLOOR_DSF_BODY = "\n".join([
    "OBJECT_DEF objects/short_gantry.obj",
    "OBJECT_DEF objects/small_slab.obj",
    f"OBJECT 0 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE:.9f} 0.000000",
    f"OBJECT 1 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE + 0.001:.9f} "
    "0.000000",
]) + "\n"

# A compact base-0 slab (reach ~21 m): correctly anchored, X-Plane's
# business — must stay below the standard 25 m discovery floor.
SMALL_SLAB_OBJECT = "\n".join([
    "A",
    "800",
    "OBJ",
    "",
    "POINT_COUNTS 4 0 0 6",
    "VT 5.000000 0.000000 5.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 15.000000 0.000000 5.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 15.000000 0.000000 15.000000 0.0 1.0 0.0 0.0 0.0",
    "VT 5.000000 0.000000 15.000000 0.0 1.0 0.0 0.0 0.0",
    "IDX10 0 1 2 0 2 3",
    "TRIS 0 6",
]) + "\n"


def test_baked_offset_geometry_admitted_at_reduced_reach_floor(
        phase_two_harness):
    """The KBNA gap: the stairs reach 24.3 / 20.6 m — under the 25 m
    discovery floor — so Phase 2 never saw them.  Baked-offset geometry
    (lowest solid vertex above the elevated threshold) is admitted at
    the reduced DSF_OBJECT_FOOT_MIN_REACH_M floor; compact base-0
    geometry keeps the standard floor."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Short Gantry Pack", REACH_FLOOR_DSF_BODY,
        {
            # Reach ~20 m: over the 15 m foot floor, under the 25 m one.
            "objects/short_gantry.obj": _two_foot_gantry_object(20.0),
            "objects/small_slab.obj": SMALL_SLAB_OBJECT,
        })

    result = post_mesh.discover_and_rebake_airport(
        dsf_path, harness.mesh_path, pack_root, None)

    assert result["objects_written"] == ["objects/short_gantry.obj"]
    assert result["structures_baked"] == 1
    # Two feet, both kept: over 18 m the plane's slope (~2.1 m) less
    # the 1.2 m base difference is within the contact tolerance.
    ((_pool, decision),) = result["decisions"]
    (feet,) = decision.foot_clusters_by_structure_index.values()
    assert len(feet) == 2
    assert all(foot.kept_for_fit for foot in feet)


# ── invariant I-4 (enforced at Phase 2 discovery, amendment A13) ─────

I4_DSF_BODY = "\n".join([
    "OBJECT_DEF objects/offset_bake.obj",
    "OBJECT_DEF objects/double_bake.obj",
    f"OBJECT 0 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE:.9f} 0.000000",
    f"OBJECT 1 {ANCHOR_LONGITUDE + 0.001:.9f} {ANCHOR_LATITUDE:.9f} "
    "0.000000",
    f"OBJECT 1 {ANCHOR_LONGITUDE - 0.001:.9f} {ANCHOR_LATITUDE:.9f} "
    "0.000000",
]) + "\n"


def test_multi_placement_resource_excluded_single_sibling_baked(
        phase_two_harness):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", I4_DSF_BODY,
        {
            "objects/offset_bake.obj": OFFSET_SLAB_OBJECT,
            "objects/double_bake.obj": OFFSET_SLAB_OBJECT,
        })

    result = post_mesh.discover_and_rebake_airport(
        dsf_path, harness.mesh_path, pack_root, None)

    assert result["objects_written"] == ["objects/offset_bake.obj"]
    skipped_by_resource = dict(result["skipped"])
    assert "objects/double_bake.obj" in skipped_by_resource
    assert "invariant I-4" in skipped_by_resource[
        "objects/double_bake.obj"]

    # The excluded file is untouched: no rewrite, no backup.
    double_path = os.path.join(pack_root, "objects", "double_bake.obj")
    with open(double_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT
    assert not os.path.isfile(double_path + ".anchor_bak")

    single_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    assert _vertex_y_values(single_path)[0] == pytest.approx(
        _expected_slab_offset(), abs=1e-4)


def test_multi_placement_exclusion_counts_through_the_worklist(
        phase_two_harness):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", I4_DSF_BODY,
        {
            "objects/offset_bake.obj": OFFSET_SLAB_OBJECT,
            "objects/double_bake.obj": OFFSET_SLAB_OBJECT,
        })
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert counts["structures_baked"] == 1
    assert counts["objects_skipped"] == 1
    assert counts["airports_failed"] == 0


# ── worklist staleness (amendment A5: identification only) ───────────

def test_stale_dsf_mtime_still_processes_against_current_dsf(
        phase_two_harness):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist([
        harness.worklist_entry(
            "KTST", dsf_path, pack_root,
            dsf_mtime=os.path.getmtime(dsf_path) - 500.0),
    ])
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert counts["airports_processed"] == 1
    assert counts["structures_baked"] == 1
    assert counts["airports_failed"] == 0


# ── per-airport failure containment ──────────────────────────────────

def test_one_broken_airport_never_blocks_the_next(phase_two_harness):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist([
        harness.worklist_entry(
            "KBAD", str(harness.tmp_path / "no-such.dsf"), pack_root,
            dsf_mtime=0.0),
        harness.worklist_entry("KTST", dsf_path, pack_root),
    ])
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert counts["airports_failed"] == 1
    assert counts["airports_processed"] == 1
    assert counts["structures_baked"] == 1


# ── the command line (tools/reanchor_dsf_objects.py) ─────────────────

_CLI_TOOL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools",
    "reanchor_dsf_objects.py",
)


@pytest.fixture(scope="module")
def cli_module():
    specification = importlib.util.spec_from_file_location(
        "reanchor_dsf_objects_tool", _CLI_TOOL_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _mode_two_arguments(dsf_path, mesh_path, pack_root):
    return ["--dsf", dsf_path, "--mesh", mesh_path,
            "--pack-root", pack_root]


def test_cli_dry_run_writes_nothing(phase_two_harness, cli_module,
                                    capsys):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")

    exit_code = cli_module.main(
        _mode_two_arguments(dsf_path, harness.mesh_path, pack_root)
        + ["--dry-run"])
    assert exit_code == 0

    with open(live_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT
    assert not os.path.isfile(live_path + ".anchor_bak")
    assert not os.path.isfile(
        os.path.join(pack_root, ".o4_reanchor_provenance.json"))
    output = capsys.readouterr().out
    assert "would bake 1 structure(s)" in output
    assert "4 vertices offset" in output


def test_cli_apply_check_and_restore(phase_two_harness, cli_module,
                                     capsys):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    common_arguments = _mode_two_arguments(
        dsf_path, harness.mesh_path, pack_root)

    # Apply (the default action).
    assert cli_module.main(common_arguments) == 0
    assert _vertex_y_values(live_path)[0] == pytest.approx(
        _expected_slab_offset(), abs=1e-4)
    capsys.readouterr()

    # --check reports CURRENT against the same mesh.
    assert cli_module.main(common_arguments + ["--check"]) == 0
    assert "CURRENT" in capsys.readouterr().out

    # --restore puts the original back byte-identically and removes the
    # provenance sidecar.
    assert cli_module.main(common_arguments + ["--restore"]) == 0
    with open(live_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT
    assert not os.path.isfile(
        os.path.join(pack_root, ".o4_reanchor_provenance.json"))


def test_cli_worklist_mode_processes_every_airport(
        phase_two_harness, cli_module, capsys):
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])

    exit_code = cli_module.main([
        "--worklist", str(harness.worklist_path),
        "--mesh", harness.mesh_path,
    ])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "KTST" in output and "baked 1 structure(s)" in output
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    assert _vertex_y_values(live_path)[0] == pytest.approx(
        _expected_slab_offset(), abs=1e-4)


# ── the driver's worklist writer (amendment A5) ──────────────────────

def test_driver_worklist_write_is_atomic_and_versioned(tmp_path):
    patch_directory = str(tmp_path / "Patches" / TILE_NAME)
    entries = [{
        "icao": "KTST",
        "dsf_path": "/somewhere/+35-081.dsf",
        "dsf_mtime": 1.0,
        "pack_root": "/somewhere",
        "xplane_root": "/xplane",
    }]
    driver._write_object_anchor_worklist(
        patch_directory, TILE_LATITUDE, TILE_LONGITUDE, entries,
        "/xplane")
    worklist_path = os.path.join(
        patch_directory, post_mesh.OBJECT_ANCHOR_WORKLIST_FILENAME)
    with open(worklist_path) as handle:
        payload = json.load(handle)
    assert payload["version"] == post_mesh.OBJECT_ANCHOR_WORKLIST_VERSION
    assert payload["tile"] == TILE_NAME
    assert payload["xplane_root"] == "/xplane"
    assert payload["airports"] == entries
    # The atomic-write temporary never survives.
    assert not os.path.exists(worklist_path + ".tmp")


def test_driver_worklist_refreshes_to_empty_but_never_creates_empty(
        tmp_path):
    patch_directory = str(tmp_path / "Patches" / TILE_NAME)
    worklist_path = os.path.join(
        patch_directory, post_mesh.OBJECT_ANCHOR_WORKLIST_FILENAME)

    # No entries and no existing file: nothing is created.
    driver._write_object_anchor_worklist(
        patch_directory, TILE_LATITUDE, TILE_LONGITUDE, [], None)
    assert not os.path.exists(worklist_path)

    # Entries, then none: the stale file is refreshed to empty rather
    # than left lying about airports that no longer resolve.
    entries = [{
        "icao": "KTST",
        "dsf_path": "/somewhere/+35-081.dsf",
        "dsf_mtime": 1.0,
        "pack_root": "/somewhere",
        "xplane_root": "/xplane",
    }]
    driver._write_object_anchor_worklist(
        patch_directory, TILE_LATITUDE, TILE_LONGITUDE, entries,
        "/xplane")
    driver._write_object_anchor_worklist(
        patch_directory, TILE_LATITUDE, TILE_LONGITUDE, [], None)
    with open(worklist_path) as handle:
        assert json.load(handle)["airports"] == []


# ── the driver's per-(airport, pack) entry builder (amendment A22) ───
#
# Field case LSGL 2026-07-23: the custom pack's apt.dat lost the quality
# contest to Global Airports, so the single apt.dat-derived worklist
# entry pointed at the Global Airports DSF (A15-skipped) and the custom
# pack's objects were never re-seated.  Object discovery must enumerate
# packs independently of the apt.dat contest.

APT_DAT_STUB = "I\n1100 Version\n99\n"

# A DSF that defines an object resource but places none — the apt.dat
# winner's DSF in the two-pack scenario.
NO_PLACEMENT_DSF_BODY = "OBJECT_DEF objects/unused.obj\n"

# A placement ~45 km east of the airport — inside the tile, far outside
# the DSF_OBJECT_WORKLIST_BBOX_MARGIN_M bbox.
FAR_PLACEMENT_DSF_BODY = "\n".join([
    "OBJECT_DEF objects/far.obj",
    f"OBJECT 0 {ANCHOR_LONGITUDE + 0.5:.9f} {ANCHOR_LATITUDE:.9f} 0.0",
]) + "\n"


def _make_airport_pack(custom_scenery, pack_name, dsf_body,
                       objects_by_resource):
    """``_make_pack`` plus the ``Earth nav data/apt.dat`` marker that
    makes the directory an airport pack for the worklist scan."""
    dsf_path, pack_root = _make_pack(
        custom_scenery, pack_name, dsf_body, objects_by_resource)
    with open(os.path.join(pack_root, "Earth nav data", "apt.dat"),
              "w") as handle:
        handle.write(APT_DAT_STUB)
    return dsf_path, pack_root


def _write_scenery_packs_ini(custom_scenery, enabled=(), disabled=()):
    lines = [f"SCENERY_PACK Custom Scenery/{name}/" for name in enabled]
    lines += [f"SCENERY_PACK_DISABLED Custom Scenery/{name}/"
              for name in disabled]
    (custom_scenery / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n" + "\n".join(lines) + "\n")


def _worklist_entries(icao, xp_root, seen=None, scan_cache=None):
    runways = {"RW16": {"lat": ANCHOR_LATITUDE, "lon": ANCHOR_LONGITUDE}}
    return driver._object_anchor_worklist_entries(
        icao, str(xp_root), runways, TILE_LATITUDE, TILE_LONGITUDE,
        set() if seen is None else seen, scan_cache)


@pytest.fixture()
def scan_xplane_root(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    xp_root = tmp_path / "XPlane"
    custom_scenery = xp_root / "Custom Scenery"
    custom_scenery.mkdir(parents=True)
    return xp_root, custom_scenery


def test_worklist_entries_cover_object_packs_beyond_apt_dat_winner(
        scan_xplane_root, monkeypatch):
    """apt.dat winner in pack A, placements in pack B → both entries
    present, B tagged as a pack-scan discovery."""
    from auto_patch import osm_load

    xp_root, custom_scenery = scan_xplane_root
    dsf_a, pack_a = _make_airport_pack(
        custom_scenery, "Pack A", NO_PLACEMENT_DSF_BODY, {})
    dsf_b, pack_b = _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(
        custom_scenery, enabled=["Pack A", "Pack B"])
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda root, icao: os.path.join(
            pack_a, "Earth nav data", "apt.dat"))

    entries = _worklist_entries("LSTS", xp_root)

    assert [(e["dsf_path"], e["source"]) for e in entries] == [
        (dsf_a, "apt_dat"), (dsf_b, "pack_scan")]
    assert entries[1]["pack_root"] == pack_b
    assert all(e["icao"] == "LSTS" for e in entries)
    assert entries[1]["dsf_mtime"] == os.path.getmtime(dsf_b)


def test_worklist_scan_skips_disabled_far_and_global_airports(
        scan_xplane_root, monkeypatch):
    from auto_patch import osm_load

    xp_root, custom_scenery = scan_xplane_root
    _make_airport_pack(
        custom_scenery, "Disabled Pack", SINGLE_PLACEMENT_DSF_BODY, {})
    _make_airport_pack(
        custom_scenery, "Far Pack", FAR_PLACEMENT_DSF_BODY, {})
    _make_airport_pack(
        custom_scenery, "Global Airports", SINGLE_PLACEMENT_DSF_BODY, {})
    _write_scenery_packs_ini(
        custom_scenery, enabled=["Far Pack", "Global Airports"],
        disabled=["Disabled Pack"])
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda root, icao: None)

    assert _worklist_entries("LSTS", xp_root) == []


def test_worklist_entries_dedupe_winner_pack_and_repeat_airports(
        scan_xplane_root, monkeypatch):
    """The apt.dat winner's DSF is never queued twice by the scan, and a
    second AIRPORT now queues it once for itself (round-4 spec R2: the
    entry key is (airport, DSF), and Phase 2 partitions the cell's
    placements between the two by containment).  The tile-wide dedup
    this replaced gave a shared cell whole to whichever airport sorted
    first — measured on +25+051, OTBD owned all of OTHH's pack."""
    from auto_patch import osm_load

    xp_root, custom_scenery = scan_xplane_root
    _dsf_b, pack_b = _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(custom_scenery, enabled=["Pack B"])
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda root, icao: os.path.join(
            pack_b, "Earth nav data", "apt.dat"))

    seen = set()
    first = _worklist_entries("LSTS", xp_root, seen)
    assert [e["source"] for e in first] == ["apt_dat"]

    second = _worklist_entries("LSTT", xp_root, seen)
    assert [e["icao"] for e in second] == ["LSTT"]
    assert [e["source"] for e in second] == ["apt_dat"]
    assert first[0]["dsf_path"] == second[0]["dsf_path"]
    # Still deduped WITHIN an airport: asking twice adds nothing.
    assert _worklist_entries("LSTT", xp_root, seen) == []


def test_worklist_scan_enumerates_packs_once_per_tile(
        scan_xplane_root, monkeypatch):
    """The pack enumeration and positions reads are airport-invariant;
    with the tile-wide scan cache a second airport must not re-list
    Custom Scenery (optimization review 2026-07-24)."""
    from auto_patch import osm_load

    xp_root, custom_scenery = scan_xplane_root
    _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(custom_scenery, enabled=["Pack B"])
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda root, icao: None)
    enumerations = []
    real_enumerate = driver._enabled_airport_pack_tile_dsfs
    monkeypatch.setattr(
        driver, "_enabled_airport_pack_tile_dsfs",
        lambda *args: (enumerations.append(args)
                       or real_enumerate(*args)))

    seen: set = set()
    scan_cache: dict = {}
    first = _worklist_entries("LSTS", xp_root, seen, scan_cache)
    second = _worklist_entries("LSTT", xp_root, seen, scan_cache)

    assert [entry["source"] for entry in first] == ["pack_scan"]
    # Round-4 spec R2: the second airport gets its OWN entry for the
    # same pack; what stays once per tile is the ENUMERATION.
    assert [entry["source"] for entry in second] == ["pack_scan"]
    assert [entry["icao"] for entry in second] == ["LSTT"]
    assert len(enumerations) == 1


def test_two_pack_fixture_bakes_the_pack_scan_entry(
        phase_two_harness, monkeypatch):
    """End to end: driver entries → worklist sidecar → rebake.  The
    pack that lost the apt.dat contest still gets its objects baked."""
    from auto_patch import osm_load

    harness = phase_two_harness
    xp_root = harness.tmp_path / "XPlane"
    custom_scenery = xp_root / "Custom Scenery"
    custom_scenery.mkdir(parents=True)
    _dsf_a, pack_a = _make_airport_pack(
        custom_scenery, "Pack A", NO_PLACEMENT_DSF_BODY, {})
    _dsf_b, pack_b = _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(
        custom_scenery, enabled=["Pack A", "Pack B"])
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda root, icao: os.path.join(
            pack_a, "Earth nav data", "apt.dat"))

    entries = _worklist_entries("LSTS", xp_root)
    assert len(entries) == 2
    driver._write_object_anchor_worklist(
        str(harness.patches_directory), TILE_LATITUDE, TILE_LONGITUDE,
        entries, str(xp_root))

    counts = post_mesh.rebake_dsf_objects(harness.tile)

    assert counts["airports_processed"] == 2
    live_path = os.path.join(pack_b, "objects", "offset_bake.obj")
    assert _vertex_y_values(live_path)[0] == pytest.approx(
        _expected_slab_offset(), abs=1e-4)


def test_worklist_v1_payload_still_processed(phase_two_harness):
    """Tolerant reading: a version-1 sidecar (pre-A22, no ``source``
    field) processes identically."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.worklist_path.write_text(json.dumps({
        "version": 1,
        "tile": TILE_NAME,
        "xplane_root": None,
        "airports": [{
            "icao": "KTST",
            "dsf_path": dsf_path,
            "dsf_mtime": os.path.getmtime(dsf_path),
            "pack_root": pack_root,
            "xplane_root": None,
        }],
    }, indent=2) + "\n")

    counts = post_mesh.rebake_dsf_objects(harness.tile)

    assert counts["airports_processed"] == 1
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    assert _vertex_y_values(live_path)[0] == pytest.approx(
        _expected_slab_offset(), abs=1e-4)


def test_object_positions_sidecar_serves_repeat_reads(
        tmp_path, monkeypatch):
    """The positions sidecar answers a repeat scan without the text
    dump: after the first read, the (migrated) ``.dsf.text`` can vanish
    and the in-process line cache be cleared, and the positions still
    come back."""
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    dsf_path, pack_root = _make_pack(
        tmp_path, "Pack S", SINGLE_PLACEMENT_DSF_BODY, {})

    first = D.read_dsf_object_placement_positions(dsf_path, pack_root)
    assert first is not None and len(first) == 1
    assert first[0][0] == pytest.approx(ANCHOR_LONGITUDE)
    assert first[0][1] == pytest.approx(ANCHOR_LATITUDE)

    # The pre-seeded in-pack dump was migrated to the data-root cache
    # on first read (ruling 2026-07-15); remove the migrated copy too,
    # so only the sidecar can answer.
    assert not os.path.isfile(dsf_path + ".text")
    migrated = D._default_pack_text_cache_path(
        D.airport_mod_cache_dir(pack_root), dsf_path)
    os.remove(migrated)
    monkeypatch.setattr(D, "_DSF_LINES_CACHE", {})
    assert D.read_dsf_object_placement_positions(
        dsf_path, pack_root) == first


# ── text dumps never litter scenery packs (ruling 2026-07-15) ────────

def test_fresh_in_pack_text_dump_is_migrated_on_sight(
        tmp_path, monkeypatch):
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")
    dsf_path, pack_root = _make_pack(
        tmp_path, "Pack M", SINGLE_PLACEMENT_DSF_BODY, {})

    lines = D._load_dsf_text(dsf_path)

    assert lines and "OBJECT_DEF" in lines[0]
    assert not os.path.isfile(dsf_path + ".text")
    migrated = D._default_pack_text_cache_path(
        D.airport_mod_cache_dir(pack_root), dsf_path)
    assert os.path.isfile(migrated)


def test_stale_in_pack_text_dump_is_removed_and_redumped_to_data_root(
        tmp_path, monkeypatch):
    """A stale legacy in-pack dump is deleted; the fresh dump lands in
    the data-root cache — the scenery pack stays clean."""
    dsf_path, pack_root = _make_pack(
        tmp_path, "Pack N", SINGLE_PLACEMENT_DSF_BODY, {})
    # Invert the harness mtimes: DSF newer than its pre-seeded text.
    now = os.path.getmtime(dsf_path)
    os.utime(dsf_path + ".text", (now - 20, now - 20))
    # A DSFTool stand-in that actually writes the requested dump.
    stub = tmp_path / "dsftool_stub.sh"
    stub.write_text("#!/bin/sh\nprintf 'OBJECT_DEF objects/x.obj\\n' "
                    "> \"$3\"\n")
    stub.chmod(0o755)
    monkeypatch.setattr(D, "_dsftool_path", lambda: str(stub))

    text_path = D.ensure_dsf_text_path(dsf_path)

    assert not os.path.isfile(dsf_path + ".text")
    assert text_path == D._default_pack_text_cache_path(
        D.airport_mod_cache_dir(pack_root), dsf_path)
    with open(text_path) as handle:
        assert handle.read() == "OBJECT_DEF objects/x.obj\n"


def test_bare_dsf_outside_a_pack_keeps_legacy_alongside_cache(
        tmp_path, monkeypatch):
    """No ``Earth nav data`` component → no pack to keep clean: the
    dump still lands next to the DSF (probe/fixture behaviour)."""
    dsf_path = tmp_path / "fake.dsf"
    dsf_path.write_text("binary-placeholder")
    text = tmp_path / "fake.dsf.text"
    text.write_text(SINGLE_PLACEMENT_DSF_BODY)
    now = os.path.getmtime(text)
    os.utime(dsf_path, (now - 10, now - 10))
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")

    assert D.ensure_dsf_text_path(str(dsf_path)) == str(text)
    assert text.is_file()


# ── the O4_Mesh_Utils hook (amendment A4) ────────────────────────────

def test_mesh_hook_swallows_exceptions(monkeypatch):
    """``build_mesh``'s tail (and ``sort_mesh``'s) calls the shared
    guard ``_auto_patch_post_mesh_rebake``; a raising
    ``rebake_dsf_objects`` must never propagate out of it."""
    def exploding_rebake(tile):
        raise RuntimeError("synthetic post-mesh failure")

    monkeypatch.setattr(
        post_mesh, "rebake_dsf_objects", exploding_rebake)
    messages = []
    monkeypatch.setattr(
        O4_Mesh_Utils.UI, "vprint",
        lambda level, *message_parts: messages.append(
            " ".join(str(part) for part in message_parts)))

    tile = types.SimpleNamespace(lat=35, lon=-81, build_dir="/nonexistent")
    O4_Mesh_Utils._auto_patch_post_mesh_rebake(tile)  # must not raise

    assert any("re-anchor failed" in message for message in messages)


def test_mesh_hook_is_wired_into_build_mesh_and_sort_mesh():
    """The guard must be CALLED from both tails (amendment A4).  Source
    inspection keeps this hermetic — running a real mesh build is out of
    the question."""
    import inspect

    build_mesh_source = inspect.getsource(O4_Mesh_Utils.build_mesh)
    sort_mesh_source = inspect.getsource(O4_Mesh_Utils.sort_mesh)
    assert "_auto_patch_post_mesh_rebake(tile)" in build_mesh_source
    assert "_auto_patch_post_mesh_rebake(tile)" in sort_mesh_source


# ---------------------------------------------------------------------------
# amendment A15: base/global scenery and library-resolved resources are
# never rebaked (found live: Global Airports static airliners pass the
# reach floor, and only an unwritable directory stopped a base-sim write)
# ---------------------------------------------------------------------------

def test_protected_scenery_root_is_never_rebaked(phase_two_harness):
    harness = phase_two_harness
    global_scenery = harness.tmp_path / "Global Scenery"
    global_scenery.mkdir()
    dsf_path, pack_root = _make_pack(
        global_scenery, "Global Airports", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})

    result = post_mesh.discover_and_rebake_airport(
        dsf_path, harness.mesh_path, pack_root, None)

    assert result["objects_written"] == []
    assert result["structures_baked"] == 0
    assert any("never rebaked" in reason for _, reason in result["skipped"])
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    assert not os.path.isfile(live_path + ".anchor_bak")
    with open(live_path) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT


def test_library_resolved_resource_outside_the_pack_is_skipped(
        phase_two_harness, monkeypatch):
    harness = phase_two_harness
    dsf_body = "\n".join([
        "OBJECT_DEF objects/offset_bake.obj",
        "OBJECT_DEF lib/airport/shared_hangar.obj",
        f"OBJECT 0 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE:.9f} 0.000000",
        f"OBJECT 1 {ANCHOR_LONGITUDE:.9f} {ANCHOR_LATITUDE:.9f} 0.000000",
    ]) + "\n"
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", dsf_body,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    # The shared library object lives in ANOTHER pack entirely.
    library_pack = harness.tmp_path / "Library Pack"
    library_object = library_pack / "shared_hangar.obj"
    library_object.parent.mkdir(parents=True)
    library_object.write_text(OFFSET_SLAB_OBJECT)

    real_resolve = post_mesh.obj8_reader.resolve_object_resource

    def resolving_through_a_library(resource_path, pack, xplane):
        if resource_path == "lib/airport/shared_hangar.obj":
            return str(library_object)
        return real_resolve(resource_path, pack, xplane)

    monkeypatch.setattr(
        post_mesh.obj8_reader, "resolve_object_resource",
        resolving_through_a_library)

    result = post_mesh.discover_and_rebake_airport(
        dsf_path, harness.mesh_path, pack_root, None)

    # The library resource is skipped with the A15 reason...
    assert any(
        resource == "lib/airport/shared_hangar.obj"
        and "library.txt outside the pack" in reason
        for resource, reason in result["skipped"])
    # ...its file is untouched...
    assert not os.path.isfile(str(library_object) + ".anchor_bak")
    with open(library_object) as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT
    # ...and the pack-local sibling still bakes.
    assert result["objects_written"] == ["objects/offset_bake.obj"]


# ── Phase 2 short-circuit (O4_REANCHOR_SHORT_CIRCUIT) ────────────────
#
# The re-anchor re-derived every structure on every mesh build (10,607
# structures, ~811 s of hook wall at +30+031, profile 2026-07-26) even
# when nothing had changed.  The pack's provenance sidecar now carries a
# fingerprint of EVERY input the decision reads; a run whose fingerprint
# still matches is skipped.  These tests pin the hit case and each miss
# case — the whole value of the short-circuit is that it misses whenever
# it possibly could matter.


def _count_derivations(monkeypatch):
    """Count the calls that only a FULL run makes."""
    calls = []
    real_deltas = post_mesh.object_anchor.structure_deltas

    def counting_deltas(*args, **kwargs):
        calls.append(1)
        return real_deltas(*args, **kwargs)

    monkeypatch.setattr(
        post_mesh.object_anchor, "structure_deltas", counting_deltas)
    return calls


def _slab_pack(harness):
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Fake Pack", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])
    return dsf_path, pack_root


def test_second_consecutive_build_short_circuits(
        phase_two_harness, monkeypatch):
    """Run 2 skips the whole airport: no structure_deltas call, the pack
    untouched, and the counts still report the baked structures."""
    harness = phase_two_harness
    _dsf_path, pack_root = _slab_pack(harness)
    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")

    first_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert first_counts["airports_up_to_date"] == 0
    assert first_counts["structures_baked"] == 1
    with open(live_path, "rb") as handle:
        live_after_first_run = handle.read()
    live_mtime = os.path.getmtime(live_path)

    calls = _count_derivations(monkeypatch)
    messages = []
    monkeypatch.setattr(
        UI, "vprint",
        lambda level, *parts: messages.append(" ".join(map(str, parts))))

    second_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert calls == []  # nothing re-derived
    assert second_counts["airports_up_to_date"] == 1
    assert second_counts["airports_processed"] == 1
    assert second_counts["structures_baked"] == 1
    assert second_counts["packs_corrected"] == 0
    assert any("re-anchor up to date" in message for message in messages)
    with open(live_path, "rb") as handle:
        assert handle.read() == live_after_first_run
    assert os.path.getmtime(live_path) == pytest.approx(live_mtime)


def test_short_circuit_records_its_fingerprint_in_the_sidecar(
        phase_two_harness):
    harness = phase_two_harness
    dsf_path, pack_root = _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    with open(os.path.join(
            pack_root, ".o4_reanchor_provenance.json")) as handle:
        provenance = json.load(handle)
    (record,) = provenance[object_rebake.RUN_RECORDS_KEY].values()
    assert record["record_version"] == object_rebake.RUN_RECORD_VERSION
    assert record["mesh"]["path"] == harness.mesh_path
    assert record["dsf"]["path"] == dsf_path
    assert record["structures_baked"] == 1
    assert record["gate_digest"] and record["excluded_digest"]
    (resource_entry,) = record["resources"]
    assert resource_entry["resource"] == "objects/offset_bake.obj"
    # Both the live file and the .anchor_bak original are fingerprinted.
    assert set(resource_entry["files"]) == {
        os.path.join("objects", "offset_bake.obj"),
        os.path.join("objects", "offset_bake.obj.anchor_bak"),
    }
    for file_record in resource_entry["files"].values():
        assert len(file_record["sha256"]) == 64


def test_touching_an_object_forces_a_full_run(
        phase_two_harness, monkeypatch):
    """`touch` on a pack ``.obj`` — same bytes, new mtime — must re-run:
    the owner touching a file is the owner asking for a reconsideration."""
    harness = phase_two_harness
    _dsf_path, pack_root = _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    live_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    stamp = os.path.getmtime(live_path) + 500.0
    os.utime(live_path, (stamp, stamp))

    calls = _count_derivations(monkeypatch)
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1
    assert counts["airports_up_to_date"] == 0
    assert counts["structures_baked"] == 1


def test_editing_an_object_behind_its_mtime_forces_a_full_run(
        phase_two_harness, monkeypatch):
    """Content change with the mtime restored — only the sha256 leg can
    catch this, and it must."""
    harness = phase_two_harness
    _dsf_path, pack_root = _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    backup_path = os.path.join(
        pack_root, "objects", "offset_bake.obj.anchor_bak")
    stat_before = os.stat(backup_path)
    with open(backup_path, "r+b") as handle:
        handle.seek(0)
        handle.write(b"B")  # 'A' -> 'B' on line 1: same size, new bytes
    os.utime(backup_path, ns=(stat_before.st_atime_ns,
                              stat_before.st_mtime_ns))
    assert os.stat(backup_path).st_size == stat_before.st_size
    assert os.stat(backup_path).st_mtime_ns == stat_before.st_mtime_ns

    calls = _count_derivations(monkeypatch)
    post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1  # the hash caught it


def test_deleting_the_anchor_bak_forces_a_full_run(
        phase_two_harness, monkeypatch):
    """The recorded FILE SET matters: ruling R1 reads geometry from the
    backup when one exists, so losing (or gaining) one is a new input."""
    harness = phase_two_harness
    _dsf_path, pack_root = _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)
    os.remove(os.path.join(
        pack_root, "objects", "offset_bake.obj.anchor_bak"))

    calls = _count_derivations(monkeypatch)
    post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1


def test_changing_the_mesh_forces_a_full_run(
        phase_two_harness, monkeypatch):
    harness = phase_two_harness
    _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    _write_synthetic_mesh(harness.mesh_path)  # a fresh mesh build
    stamp = os.path.getmtime(harness.mesh_path) + 100.0
    os.utime(harness.mesh_path, (stamp, stamp))

    calls = _count_derivations(monkeypatch)
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1
    assert counts["airports_up_to_date"] == 0


def test_changing_the_dsf_forces_a_full_run(
        phase_two_harness, monkeypatch):
    harness = phase_two_harness
    dsf_path, _pack_root = _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    # Run 1 migrated the pre-seeded ``.dsf.text`` into the pack cache;
    # keep that dump newer than the touched ``.dsf`` so the second run
    # reads it instead of invoking DSFTool.
    stamp = os.path.getmtime(dsf_path) + 100.0
    os.utime(dsf_path, (stamp, stamp))
    cache_directory = post_mesh.dsf_reader.airport_mod_cache_dir(
        os.path.dirname(os.path.dirname(os.path.dirname(dsf_path))))
    for name in os.listdir(cache_directory):
        if name.endswith(".text"):
            os.utime(os.path.join(cache_directory, name),
                     (stamp + 10.0, stamp + 10.0))

    calls = _count_derivations(monkeypatch)
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1
    assert counts["airports_up_to_date"] == 0


def test_changing_a_configuration_gate_forces_a_full_run(
        phase_two_harness, monkeypatch):
    harness = phase_two_harness
    _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    monkeypatch.setattr(config, "DSF_OBJECT_MIN_REACH_M", 24.0)
    calls = _count_derivations(monkeypatch)
    post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1


def test_short_circuit_flag_off_always_runs_in_full(
        phase_two_harness, monkeypatch):
    harness = phase_two_harness
    _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    monkeypatch.setenv("O4_REANCHOR_SHORT_CIRCUIT", "0")
    calls = _count_derivations(monkeypatch)
    counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1
    assert counts["airports_up_to_date"] == 0


def test_dry_run_never_short_circuits(phase_two_harness, monkeypatch):
    """``write_changes=False`` exists to REPORT the decision; a cached
    'nothing to do' would report nothing."""
    harness = phase_two_harness
    dsf_path, pack_root = _slab_pack(harness)
    post_mesh.rebake_dsf_objects(harness.tile)

    calls = _count_derivations(monkeypatch)
    result = post_mesh.discover_and_rebake_airport(
        dsf_path, harness.mesh_path, pack_root, None, write_changes=False)
    assert len(calls) == 1
    assert result["short_circuited"] is False
    assert result["structures_baked"] == 1


def test_short_circuit_keeps_the_foot_pad_sidecar(phase_two_harness):
    """A skipped airport must still contribute its foot-pad requests, or
    the per-tile sidecar would be deleted as stale on every second
    build."""
    harness = phase_two_harness
    dsf_path, pack_root = _make_pack(
        harness.tmp_path, "Gantry Pack", TWO_FOOT_GANTRY_DSF_BODY,
        {"objects/gantry.obj": TWO_FOOT_GANTRY_OBJECT})
    harness.write_worklist(
        [harness.worklist_entry("KTST", dsf_path, pack_root)])

    first_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert first_counts["foot_pad_requests"] == 1
    sidecar_path = harness.patches_directory / (
        post_mesh.OBJECT_FOOT_PAD_SIDECAR_FILENAME)
    first_payload = json.loads(sidecar_path.read_text())

    second_counts = post_mesh.rebake_dsf_objects(harness.tile)
    assert second_counts["airports_up_to_date"] == 1
    assert second_counts["foot_pad_requests"] == 1
    assert sidecar_path.exists()
    assert json.loads(sidecar_path.read_text()) == first_payload


def test_short_circuit_survives_a_prototype_era_sidecar(
        phase_two_harness, monkeypatch):
    """A pack carrying the prototype's flat provenance has no run
    fingerprint: run in full, then record one."""
    harness = phase_two_harness
    _dsf_path, pack_root = _slab_pack(harness)
    provenance_path = os.path.join(
        pack_root, ".o4_reanchor_provenance.json")
    with open(provenance_path, "w") as handle:
        json.dump({"mesh": harness.mesh_path, "size": 1, "mtime": 1,
                   "objects": ["objects/offset_bake.obj"],
                   "anchor": [0.0, 0.0, 0.0], "anchor_ground": 1.0},
                  handle)

    calls = _count_derivations(monkeypatch)
    post_mesh.rebake_dsf_objects(harness.tile)
    assert len(calls) == 1
    with open(provenance_path) as handle:
        assert json.load(handle)[object_rebake.RUN_RECORDS_KEY]


# ── object_rebake run-record unit cases (synthetic sidecar) ──────────

def test_matching_run_record_reports_each_miss_reason(tmp_path):
    """Every rejection path returns a human reason and never raises."""
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    mesh_path = tmp_path / ("Data" + TILE_NAME + ".mesh")
    mesh_path.write_text("mesh")
    dsf_path = tmp_path / (TILE_NAME + ".dsf")
    dsf_path.write_text("dsf")

    def check():
        return object_rebake.matching_run_record(
            str(pack_root), str(dsf_path), str(mesh_path),
            epsilon_metres=0.25, excluded_resources=None,
            resolve_resource=lambda resource_path: None)

    record, reason = check()
    assert record is None and "no provenance sidecar" in reason

    record = object_rebake.build_run_record(
        str(pack_root), str(dsf_path), str(mesh_path),
        epsilon_metres=0.25, excluded_resources=None,
        referenced_resources=[], resolve_resource=lambda path: None,
        structures_baked=7, structures_needing_pad=0, foot_pad_requests=[])
    object_rebake.store_run_record(
        str(pack_root), str(dsf_path), str(mesh_path), record)

    hit, reason = check()
    assert hit is not None and hit["structures_baked"] == 7

    # a different epsilon is a different decision
    miss, reason = object_rebake.matching_run_record(
        str(pack_root), str(dsf_path), str(mesh_path),
        epsilon_metres=0.5, excluded_resources=None,
        resolve_resource=lambda resource_path: None)
    assert miss is None and "configuration gate" in reason

    # a different exclusion set is a different decision
    miss, reason = object_rebake.matching_run_record(
        str(pack_root), str(dsf_path), str(mesh_path),
        epsilon_metres=0.25,
        excluded_resources={(str(pack_root), "objects/a.obj")},
        resolve_resource=lambda resource_path: None)
    assert miss is None and "exclusion set" in reason

    # a stale record version never serves new code
    provenance_path = os.path.join(
        str(pack_root), ".o4_reanchor_provenance.json")
    with open(provenance_path) as handle:
        provenance = json.load(handle)
    for stored in provenance[object_rebake.RUN_RECORDS_KEY].values():
        stored["record_version"] = object_rebake.RUN_RECORD_VERSION - 1
    with open(provenance_path, "w") as handle:
        json.dump(provenance, handle)
    miss, reason = check()
    assert miss is None and "older code" in reason


def test_matching_run_record_misses_when_a_resource_moves(tmp_path):
    """Resolution is fingerprinted, not just content: a resource that now
    resolves to a different physical file is a new input."""
    pack_root = tmp_path / "pack"
    (pack_root / "objects").mkdir(parents=True)
    live_path = pack_root / "objects" / "thing.obj"
    live_path.write_text(OFFSET_SLAB_OBJECT)
    mesh_path = tmp_path / ("Data" + TILE_NAME + ".mesh")
    mesh_path.write_text("mesh")
    dsf_path = tmp_path / (TILE_NAME + ".dsf")
    dsf_path.write_text("dsf")

    record = object_rebake.build_run_record(
        str(pack_root), str(dsf_path), str(mesh_path),
        epsilon_metres=0.25, excluded_resources=None,
        referenced_resources=["objects/thing.obj"],
        resolve_resource=lambda path: str(live_path),
        structures_baked=1, structures_needing_pad=0, foot_pad_requests=[])
    object_rebake.store_run_record(
        str(pack_root), str(dsf_path), str(mesh_path), record)

    hit, _reason = object_rebake.matching_run_record(
        str(pack_root), str(dsf_path), str(mesh_path),
        epsilon_metres=0.25, excluded_resources=None,
        resolve_resource=lambda path: str(live_path))
    assert hit is not None

    miss, reason = object_rebake.matching_run_record(
        str(pack_root), str(dsf_path), str(mesh_path),
        epsilon_metres=0.25, excluded_resources=None,
        resolve_resource=lambda path: "/elsewhere/thing.obj")
    assert miss is None and "resolves elsewhere" in reason
