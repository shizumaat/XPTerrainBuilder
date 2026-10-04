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

import json
import math
import os
import sys
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
    with open(mesh_path, "w", encoding="utf-8", newline="") as handle:
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
    dsf.write_text("binary-placeholder", encoding="utf-8", newline="")
    text = dsf_directory / (TILE_NAME + ".dsf.text")
    text.write_text(dsf_body, encoding="utf-8", newline="")
    now = os.path.getmtime(text)
    os.utime(dsf, (now - 10, now - 10))
    for resource_path, content in objects_by_resource.items():
        physical = pack_root.joinpath(*resource_path.split("/"))
        physical.parent.mkdir(parents=True, exist_ok=True)
        physical.write_text(content, encoding="utf-8", newline="")
    return str(dsf), str(pack_root)


def _vertex_y_values(object_path: str) -> list[float]:
    values = []
    with open(object_path, encoding="utf-8") as handle:
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
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="")

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


# ── the end-to-end bake ──────────────────────────────────────────────


# ── the reseat threshold, end to end ─────────────────────────────────


# ── partition sidecar cache (Airport_mod_cache/<pack>/) ─────────────


# ── multi-ground-cluster foot pads (sidecar) ─────────────────────────


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
    with open(double_path, encoding="utf-8") as handle:
        assert handle.read() == OFFSET_SLAB_OBJECT
    assert not os.path.isfile(double_path + ".anchor_bak")

    single_path = os.path.join(pack_root, "objects", "offset_bake.obj")
    assert _vertex_y_values(single_path)[0] == pytest.approx(
        _expected_slab_offset(), abs=1e-4)


# ── worklist staleness (amendment A5: identification only) ───────────


# ── per-airport failure containment ──────────────────────────────────


# ── the command line (tools/reanchor_dsf_objects.py) — RETIRED ───────
# Four CLI twins stood here (dry run, apply/check/restore, worklist
# mode).  ``tools/reanchor_dsf_objects.py`` was DELETED with the seat
# (owner RULINGS 2026-09-12s, spec §8): it was the hand entry into v1's
# vertex re-bake, a refuted mechanism.  ``post_mesh``'s own library twins
# above are untouched.


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
    with open(worklist_path, encoding="utf-8") as handle:
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
    with open(worklist_path, encoding="utf-8") as handle:
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
              "w", encoding="utf-8", newline="") as handle:
        handle.write(APT_DAT_STUB)
    return dsf_path, pack_root


def _write_scenery_packs_ini(custom_scenery, enabled=(), disabled=()):
    lines = [f"SCENERY_PACK Custom Scenery/{name}/" for name in enabled]
    lines += [f"SCENERY_PACK_DISABLED Custom Scenery/{name}/"
              for name in disabled]
    (custom_scenery / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n" + "\n".join(lines) + "\n", encoding="utf-8", newline="")


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
    from auto_patch import build_support

    xp_root, custom_scenery = scan_xplane_root
    dsf_a, pack_a = _make_airport_pack(
        custom_scenery, "Pack A", NO_PLACEMENT_DSF_BODY, {})
    dsf_b, pack_b = _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(
        custom_scenery, enabled=["Pack A", "Pack B"])
    monkeypatch.setattr(
        build_support, "_pick_best_apt_dat_against_osm",
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
    from auto_patch import build_support

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
        build_support, "_pick_best_apt_dat_against_osm",
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
    from auto_patch import build_support

    xp_root, custom_scenery = scan_xplane_root
    _dsf_b, pack_b = _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(custom_scenery, enabled=["Pack B"])
    monkeypatch.setattr(
        build_support, "_pick_best_apt_dat_against_osm",
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
    from auto_patch import build_support

    xp_root, custom_scenery = scan_xplane_root
    _make_airport_pack(
        custom_scenery, "Pack B", SINGLE_PLACEMENT_DSF_BODY,
        {"objects/offset_bake.obj": OFFSET_SLAB_OBJECT})
    _write_scenery_packs_ini(custom_scenery, enabled=["Pack B"])
    monkeypatch.setattr(
        build_support, "_pick_best_apt_dat_against_osm",
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
    # A Python stub behind a shebang (POSIX) or a .cmd shim (Windows cannot
    # exec a shell script, WinError 193 — #92).
    stub_py = tmp_path / "dsftool_stub.py"
    stub_py.write_text("import sys\n"
                       "open(sys.argv[3], 'w', newline='').write("
                       "'OBJECT_DEF objects/x.obj\\n')\n",
                       encoding="utf-8", newline="")
    if sys.platform == "win32":
        stub = tmp_path / "dsftool_stub.cmd"
        stub.write_text(f'@"{sys.executable}" "{stub_py}" %*\r\n',
                        encoding="utf-8", newline="")
    else:
        stub = tmp_path / "dsftool_stub"
        stub.write_text(f"#!{sys.executable}\n" + stub_py.read_text(encoding="utf-8"),
                        encoding="utf-8", newline="")
        stub.chmod(0o755)
    monkeypatch.setattr(D, "_dsftool_path", lambda: str(stub))

    text_path = D.ensure_dsf_text_path(dsf_path)

    assert not os.path.isfile(dsf_path + ".text")
    assert text_path == D._default_pack_text_cache_path(
        D.airport_mod_cache_dir(pack_root), dsf_path)
    with open(text_path, encoding="utf-8") as handle:
        assert handle.read() == "OBJECT_DEF objects/x.obj\n"


def test_bare_dsf_outside_a_pack_keeps_legacy_alongside_cache(
        tmp_path, monkeypatch):
    """No ``Earth nav data`` component → no pack to keep clean: the
    dump still lands next to the DSF (probe/fixture behaviour)."""
    dsf_path = tmp_path / "fake.dsf"
    dsf_path.write_text("binary-placeholder", encoding="utf-8", newline="")
    text = tmp_path / "fake.dsf.text"
    text.write_text(SINGLE_PLACEMENT_DSF_BODY, encoding="utf-8", newline="")
    now = os.path.getmtime(text)
    os.utime(dsf_path, (now - 10, now - 10))
    monkeypatch.setattr(D, "_dsftool_path", lambda: "/bin/true")

    assert D.ensure_dsf_text_path(str(dsf_path)) == str(text)
    assert text.is_file()


# ── the O4_Mesh_Utils hook (amendment A4) ────────────────────────────

def test_mesh_hook_swallows_exceptions(monkeypatch):
    """``build_mesh``'s tail (and ``sort_mesh``'s) calls the shared
    guard ``_auto_patch_post_mesh_rebake``; a raising re-seat must never
    propagate out of it.  The re-seat is v2's ``rebake_after_mesh`` (v1
    retired, RULINGS 2026-09-13au — the guard no longer dispatches to
    ``post_mesh_v1.rebake_dsf_objects``)."""
    from auto_patch import engine_v2

    def exploding_rebake(tile):
        raise RuntimeError("synthetic post-mesh failure")

    monkeypatch.setattr(engine_v2, "rebake_after_mesh", exploding_rebake)
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
    with open(live_path, encoding="utf-8") as handle:
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
    library_object.write_text(OFFSET_SLAB_OBJECT, encoding="utf-8", newline="")

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
    with open(library_object, encoding="utf-8") as handle:
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


# ── object_rebake run-record unit cases (synthetic sidecar) ──────────

def test_matching_run_record_reports_each_miss_reason(tmp_path):
    """Every rejection path returns a human reason and never raises."""
    pack_root = tmp_path / "pack"
    pack_root.mkdir()
    mesh_path = tmp_path / ("Data" + TILE_NAME + ".mesh")
    mesh_path.write_text("mesh", encoding="utf-8", newline="")
    dsf_path = tmp_path / (TILE_NAME + ".dsf")
    dsf_path.write_text("dsf", encoding="utf-8", newline="")

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
    with open(provenance_path, encoding="utf-8") as handle:
        provenance = json.load(handle)
    for stored in provenance[object_rebake.RUN_RECORDS_KEY].values():
        stored["record_version"] = object_rebake.RUN_RECORD_VERSION - 1
    with open(provenance_path, "w", encoding="utf-8", newline="") as handle:
        json.dump(provenance, handle)
    miss, reason = check()
    assert miss is None and "older code" in reason


def test_matching_run_record_misses_when_a_resource_moves(tmp_path):
    """Resolution is fingerprinted, not just content: a resource that now
    resolves to a different physical file is a new input."""
    pack_root = tmp_path / "pack"
    (pack_root / "objects").mkdir(parents=True)
    live_path = pack_root / "objects" / "thing.obj"
    live_path.write_text(OFFSET_SLAB_OBJECT, encoding="utf-8", newline="")
    mesh_path = tmp_path / ("Data" + TILE_NAME + ".mesh")
    mesh_path.write_text("mesh", encoding="utf-8", newline="")
    dsf_path = tmp_path / (TILE_NAME + ".dsf")
    dsf_path.write_text("dsf", encoding="utf-8", newline="")

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
