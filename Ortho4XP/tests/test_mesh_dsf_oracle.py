"""The frozen vector -> mesh -> DSF byte oracle (#856, B3-24;
``docs/specs/code-quality-beta3-spec.md`` section 6).

``tests/fixtures/mesh_dsf/`` holds a synthetic 0.02 deg window written once
by ``tools/fixtures/make_mesh_dsf_fixture.py``; each twin below replays ONE
stage with the engine's own functions and asserts the committed bytes:

* the step-1 writer (``Vector_Map.write_node_file`` / ``write_poly_file``)
  and the DEM raster reproduce ``.node`` / ``.poly`` / ``.alt``;
* Triangle4XP reproduces ``.1.node`` / ``.1.ele`` where this platform's
  binary was pinned (#875: the mesher may differ by platform) and is
  skipped, with the reason, where it was not;
* ``post_process_nodes_altitudes`` + ``write_mesh_file`` on the committed
  Triangle outputs reproduce the ``.mesh``;
* ``build_dsf`` on the committed ``.mesh`` reproduces both DSFs (MD5 footer
  included).

A change that MUST move bytes regenerates the fixture in the same PR
(``--write --reason``); the manifest's history keeps the reason.
"""

import hashlib
import os
import sys

import pytest

_FIXTURE_TOOLS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "tools", "fixtures"))
if _FIXTURE_TOOLS not in sys.path:
    sys.path.insert(0, _FIXTURE_TOOLS)
import make_mesh_dsf_fixture as FIX  # noqa: E402

REGENERATE = ("if the change MUST move these bytes, regenerate in the same "
              "PR: venv/bin/python tools/fixtures/make_mesh_dsf_fixture.py "
              "--write --reason '...'")


@pytest.fixture(scope="module")
def manifest():
    return FIX.read_manifest()


def _committed(name):
    with open(os.path.join(FIX.FIXTURE_DIR, name), "rb") as handle:
        return handle.read()


def _first_difference(got, want):
    for (k, (a, b)) in enumerate(zip(got, want)):
        if a != b:
            return k
    return min(len(got), len(want))


def _assert_digest(name, data, expected):
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        committed = _committed(name)
        pytest.fail(
            f"{name} moved: {len(data)} bytes (committed {len(committed)}), "
            f"first difference at byte {_first_difference(data, committed)}"
            f"; sha256 {digest[:16]} != {expected[:16]}.  {REGENERATE}")


def test_the_committed_files_are_the_manifest(manifest):
    names = set(FIX.committed_names())
    assert set(manifest["files"]) == names
    total = 0
    for name in sorted(names):
        data = _committed(name)
        total += len(data)
        assert hashlib.sha256(data).hexdigest() == manifest["files"][name], (
            f"{name} differs from MANIFEST.json: a fixture file was edited "
            f"by hand or a checkout rewrote it.  {REGENERATE}")
    assert total == manifest["total_bytes"] <= FIX.SIZE_BUDGET
    assert manifest["history"] and all(
        entry["reason"].strip() for entry in manifest["history"])


def test_the_vector_writer_reproduces_node_and_poly(tmp_path, manifest):
    FIX.write_vector_inputs(str(tmp_path))
    for name in (FIX.STEM + ".node", FIX.STEM + ".poly"):
        _assert_digest(name, (tmp_path / name).read_bytes(),
                       manifest["files"][name])


def test_the_dem_raster_reproduces_alt(tmp_path, manifest):
    FIX.write_dem(str(tmp_path))
    name = FIX.STEM + ".alt"
    _assert_digest(name, (tmp_path / name).read_bytes(),
                   manifest["files"][name])


def test_triangle4xp_reproduces_its_outputs(tmp_path, manifest):
    binary = FIX.triangle_binary()
    if not os.path.isfile(binary):
        pytest.skip(f"no Triangle4XP at {binary}")
    for name in FIX.INPUTS:
        (tmp_path / name).write_bytes(_committed(name))
    result = FIX.run_triangle(str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    pinned = FIX.expected_triangle_hashes(manifest)
    if pinned is None:
        # Not pinned here: the committed outputs (another platform's) are
        # the question #875 asks.  Identical is a measured pass; different
        # is reported, never asserted, until this platform is pinned.
        moved = [name for name in FIX.TRIANGLE_OUTPUTS
                 if (tmp_path / name).read_bytes() != _committed(name)]
        if moved:
            pytest.skip(
                f"Triangle4XP on {FIX.platform_key()} ({binary}) is not "
                f"pinned and its {', '.join(moved)} differ from the "
                "committed outputs (#875); pin with make_mesh_dsf_fixture.py"
                " --pin-platform --reason ...")
        return
    for name in FIX.TRIANGLE_OUTPUTS:
        _assert_digest(name, (tmp_path / name).read_bytes(), pinned[name])


@pytest.fixture(scope="module")
def downstream(tmp_path_factory):
    """Steps 2-3 replayed once on the committed inputs and Triangle outputs."""
    work = tmp_path_factory.mktemp("mesh_dsf_replay")
    return FIX.replay_downstream(FIX.FIXTURE_DIR, str(work))


def test_post_processing_reproduces_the_mesh(downstream, manifest):
    name = FIX.MESH_OUTPUT
    _assert_digest(name, downstream[name], FIX.expected_sha256(manifest, name))


@pytest.mark.parametrize("mode", FIX.DSF_MODES)
def test_build_dsf_reproduces_the_dsf(downstream, manifest, mode):
    name = mode + ".dsf"
    data = downstream[name]
    assert data[:8] == b"XPLNEDSF"
    assert hashlib.md5(data[:-16]).digest() == data[-16:], (
        "the DSF's MD5 footer does not cover its body")
    _assert_digest(name, data, FIX.expected_sha256(manifest, name))


def test_the_window_exercises_water_and_patch_paths():
    """The fixture is only an oracle for paths it reaches: the mesh carries
    land, inland water and the patch's INTERP_ALT triangles."""
    text = _committed(FIX.MESH_OUTPUT).decode("ascii")
    triangles = text.split("Triangles\n", 1)[1].split("\n")
    count = int(triangles[0])
    attributes = {int(line.split()[3]) for line in triangles[1:1 + count]}
    assert {0, 1, 8} <= attributes, attributes
