"""THE LERC DECODER, SOURCE AND FROZEN (owner RULINGS 2026-09-12as (3)).

The packaged 1.0.324 engine printed "LERC-compressed elevation sources
are not available in the packaged application - skipping NEWZEALAND1M"
and carried on: New Zealand's 1 m lidar silently degraded to the base
tier, because the decode spawned ``sys.executable`` with a Python
snippet and a frozen binary has no interpreter to spawn.  The decode is
now ``src/O4_LERC_Decode.py``, run out of process either way — as a
script from source, as ``Ortho4XP --lerc-decode IN OUT`` when frozen.

OUT OF PROCESS IS NOT OPTIONAL, and this suite is the proof: a process
that has loaded the ``osgeo`` libraries ABORTS (SIGABRT, no traceback)
the moment imagecodecs decodes LERC in it — measured again 2026-09-12.
Importing both is harmless; DECODING is not.  So every functional twin
here decodes through the production argv in a child, and the fixture is
written in a child too.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy
import pytest

# MODULE LEVEL, DELIBERATELY (the ``highspy`` precedent): the decoder's
# own ``import tifffile`` / ``import imagecodecs`` are module level so
# PyInstaller's static scan sees them, and this import is what makes the
# suite fail when they are missing instead of a user's terrain quietly
# losing a tier.  Importing is safe; only a decode beside GDAL aborts.
import O4_LERC_Decode as LERC
import O4_Airport_Elevation_Insets as INSETS

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = os.path.join(ENGINE_DIR, "Ortho4XP.py")


def _write_lerc_tiff(path):
    """A 64x64 LERC-compressed GeoTIFF with the georeferencing tags,
    written in a CHILD (this process may have GDAL loaded)."""
    completed = subprocess.run(
        [sys.executable, "-c",
         "import sys\n"
         "import numpy\n"
         "import tifffile\n"
         "values = (numpy.arange(64 * 64, dtype=numpy.float32)\n"
         "          .reshape(64, 64) / 7.0)\n"
         "tifffile.imwrite(sys.argv[1], values, compression='lerc',\n"
         "    extratags=[(33550, 'd', 3, (1.0, 1.0, 0.0)),\n"
         "               (33922, 'd', 6, (0.0, 0.0, 0.0, 170.0, -45.0, 0.0))])\n",
         str(path)],
        capture_output=True, text=True, timeout=180)
    if completed.returncode != 0:
        pytest.skip("tifffile/imagecodecs LERC not available: "
                    + completed.stderr.strip()[-200:])


def _write_lerc_blob(path):
    completed = subprocess.run(
        [sys.executable, "-c",
         "import sys\n"
         "import numpy\n"
         "import imagecodecs\n"
         "values = numpy.full((257, 257), 12.5, dtype=numpy.float32)\n"
         "open(sys.argv[1], 'wb').write(imagecodecs.lerc_encode(values))\n",
         str(path)],
        capture_output=True, text=True, timeout=180)
    if completed.returncode != 0:
        pytest.skip("imagecodecs LERC not available")


def test_the_codecs_are_imported_at_MODULE_level():
    """A function-level third-party import is invisible to PyInstaller
    AND to this suite (highspy, 2026-09-10): the codecs the frozen
    bundle must carry are imported where the freeze can see them."""
    source = open(os.path.join(ENGINE_DIR, "src", "O4_LERC_Decode.py")).read()
    body = source[source.index("from __future__"):]
    top = [line for line in body.splitlines() if line.startswith("import ")]
    assert "import tifffile" in top
    assert "import imagecodecs" in top
    # the child must never load GDAL: no osgeo import, at any level
    assert "osgeo" not in "".join(line for line in body.splitlines()
                                  if "import" in line)
    assert LERC.tifffile is not None and LERC.imagecodecs is not None


def test_the_geotiff_decode_carries_the_values_and_the_tags(tmp_path):
    tiff = tmp_path / "fixture.tif"
    npy = tmp_path / "out.npy"
    _write_lerc_tiff(tiff)
    completed = subprocess.run(
        INSETS.lerc_worker_argv(str(tiff), str(npy)),
        capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-400:]
    tags = json.loads(completed.stdout)
    assert tags["tiepoint"][3:5] == [170.0, -45.0]
    assert tags["scale"][:2] == [1.0, 1.0]
    values = numpy.load(npy)
    assert values.shape == (64, 64)
    assert values[3, 4] == pytest.approx(28.0, abs=1e-3)


def test_the_blob_decode_crops_the_shared_edge(tmp_path):
    """The ArcGIS pyramid serves 257x257 for a 256 grid: the decoder
    crops to the tile proper, and a DIRECTORY argument is that decode."""
    blobs = tmp_path / "blobs"
    out = tmp_path / "npy"
    blobs.mkdir()
    out.mkdir()
    _write_lerc_blob(blobs / "7_9.lerc")
    completed = subprocess.run(
        INSETS.lerc_worker_argv(str(blobs), str(out)),
        capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-400:]
    values = numpy.load(out / "7_9.npy")
    assert values.shape == (256, 256)
    assert values[0, 0] == pytest.approx(12.5)


def test_the_ENGINE_ENTRY_decodes_the_same_argv(tmp_path):
    """The frozen path in from-source clothing: the branch the frozen
    binary takes is ``Ortho4XP.py --lerc-decode IN OUT``, dispatched
    ahead of every heavy import — run it and read the array back."""
    tiff = tmp_path / "fixture.tif"
    npy = tmp_path / "out.npy"
    _write_lerc_tiff(tiff)
    completed = subprocess.run(
        [sys.executable, ENTRY, "--lerc-decode", str(tiff), str(npy)],
        capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-400:]
    assert json.loads(completed.stdout)["tiepoint"][3] == 170.0
    assert numpy.load(npy).shape == (64, 64)


def test_the_FROZEN_engine_spawns_its_own_binary(monkeypatch):
    """Frozen, ``sys.executable`` IS the engine: the argv is the
    internal ``--lerc-decode``, never a bare interpreter with ``-c``
    (which is what silently skipped NEWZEALAND1M)."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    argv = INSETS.lerc_worker_argv("/tmp/in.tif", "/tmp/out.npy")
    assert argv == [sys.executable, "--lerc-decode", "/tmp/in.tif",
                    "/tmp/out.npy"]
    assert "-c" not in argv


def test_the_SOURCE_engine_spawns_the_decoder_module(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    argv = INSETS.lerc_worker_argv("/tmp/in.tif", "/tmp/out.npy")
    assert argv[0] == sys.executable
    assert argv[1].endswith(os.path.join("src", "O4_LERC_Decode.py"))
    assert os.path.isfile(argv[1])


def test_no_frozen_skip_is_left_in_the_fetchers():
    """The two fetchers used to bail out under ``sys.frozen`` with a
    WARNING and no data.  Neither may again."""
    source = open(os.path.join(ENGINE_DIR, "src",
                               "O4_Airport_Elevation_Insets.py")).read()
    assert "not available in the packaged application" not in source


def test_the_engine_entry_dispatches_the_argv():
    """The dispatch must stay AHEAD of the heavy imports: a decode child
    that loads the pipeline would load GDAL and abort."""
    entry = open(ENTRY).read()
    branch = entry.index("'--lerc-decode' in sys.argv")
    assert branch < entry.index("import O4_File_Names as FNAMES")


# ──────────────────────────────────────────────────────────────────────
# WINDOWS AND LINUX (owner RULINGS 2026-09-13a (1))
#
# On those platforms there is no separate frozen engine: the Qt app IS
# the engine (it answers --engine-jsonl and serves as its own build
# worker), so ``sys.executable`` in ``lerc_worker_argv`` is the Qt
# binary.  Everything the mac engine needs to decode LERC, that binary
# needs too — and 1.0.325 shipped with none of it.
# ──────────────────────────────────────────────────────────────────────
QT_ENTRY = os.path.join(ENGINE_DIR, "Ortho4XP_Qt.py")
QT_SPEC = os.path.join(ENGINE_DIR, "Ortho4XP_Qt.spec")
MAC_SPEC = os.path.join(ENGINE_DIR, "Ortho4XP.spec")
REPO_ROOT = os.path.dirname(ENGINE_DIR)
LERC_CHECK = os.path.join(REPO_ROOT, "scripts", "check_frozen_lerc.sh")
MAKE_ENGINE = os.path.join(REPO_ROOT, "scripts", "make_engine.sh")
RELEASE_WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows",
                                "release.yml")


def test_the_QT_entry_dispatches_the_argv_AHEAD_of_Qt():
    """Same branch as the engine entry, same place: before the PROJ
    preflight, before ``o4_engine``, before any Qt import — a decode
    child that loads the pipeline would load GDAL and abort."""
    entry = open(QT_ENTRY).read()
    branch = entry.index('"--lerc-decode" in sys.argv')
    assert branch < entry.index("import O4_LERC_Decode")
    assert branch < entry.index("from o4_engine import jsonl")
    assert branch < entry.index("O4_Proj_Runtime.preflight()\n    if _proj_error")


def test_the_QT_spec_carries_every_lazy_dependency():
    """The freeze's static scan sees none of these: the LERC codecs are
    reached only through the --lerc-decode branch, highspy only inside
    the solve (1.0.298 shipped without it), auto_patch_v2 only per
    engine selection — and its law is TOML data, not modules."""
    spec = open(QT_SPEC).read()
    for needed in ("collect_all('tifffile')", "collect_all('imagecodecs')",
                   "imagecodecs._lerc", "imagecodecs._shared",
                   "'O4_LERC_Decode'", "collect_all('highspy')",
                   "collect_submodules('auto_patch_v2')", "v2_law_datas"):
        assert needed in spec, needed + " missing from Ortho4XP_Qt.spec"
    # …and each collected package actually reaches the Analysis.
    for wired in ("tifffile_binaries", "imagecodecs_datas",
                  "highspy_hidden", "tifffile_hidden"):
        assert wired in spec.split("a = Analysis(")[1]


def test_BOTH_specs_pin_the_codecs():
    """One law, two specs: whatever the mac engine pins for LERC, the
    Windows/Linux app pins too."""
    mac = open(MAC_SPEC).read()
    qt = open(QT_SPEC).read()
    for needed in ("collect_all('tifffile')", "collect_all('imagecodecs')",
                   "imagecodecs._lerc", "'O4_LERC_Decode'"):
        assert needed in mac and needed in qt


def test_ONE_fixture_check_serves_every_frozen_artifact():
    """The 64x64 LERC fixture check is one script — the engine freeze and
    both release jobs run THAT, never a copy of it (the census-wrapper
    precedent: a slightly-different duplicate is a defect)."""
    assert os.path.isfile(LERC_CHECK)
    check = open(LERC_CHECK).read()
    assert "--lerc-decode" in check
    assert "compression=\"lerc\"" in check or "compression='lerc'" in check

    engine = open(MAKE_ENGINE).read()
    assert "check_frozen_lerc.sh" in engine
    # the Qt freeze tests the Qt binary, not the engine's name
    assert "dist/Ortho4XP_Qt/Ortho4XP_Qt" in engine
    # and no second copy of the fixture was left behind in the script
    assert "tifffile.imwrite" not in engine

    workflow = open(RELEASE_WORKFLOW).read()
    # Count INVOCATIONS, not mentions: the mac job's comment names the
    # script in prose (it runs inside scripts/make_engine.sh), which made
    # this assertion red on main at 74c9d813 for a comment.
    assert workflow.count("bash scripts/check_frozen_lerc.sh") == 2, (
        "the Windows and Linux release jobs must each run the check")
    assert "Ortho4XP_Qt.exe" in workflow


def test_the_tags_also_land_BESIDE_the_array(tmp_path):
    """A console-less frozen binary can run with ``sys.stdout`` None,
    where ``print`` writes nowhere: the caller would read an empty
    stdout, fail to parse it, and SKIP the source — the silent
    degradation all over again.  The sidecar cannot go missing."""
    tiff = tmp_path / "fixture.tif"
    npy = tmp_path / "out.npy"
    _write_lerc_tiff(tiff)
    completed = subprocess.run(
        [sys.executable, ENTRY, "--lerc-decode", str(tiff), str(npy)],
        capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stderr[-400:]
    sidecar = str(npy) + ".tags.json"
    assert os.path.isfile(sidecar)
    assert json.load(open(sidecar)) == json.loads(completed.stdout)


def test_the_fetcher_falls_back_to_the_sidecar():
    """The reader of that sidecar is the inset fetcher, and it deletes
    it with the array — a scratch file must not survive the fetch."""
    source = open(os.path.join(ENGINE_DIR, "src",
                               "O4_Airport_Elevation_Insets.py")).read()
    assert 'npy_path + ".tags.json"' in source
    assert source.count('npy_path + ".tags.json"') >= 2  # read AND cleanup
# ── THE CAPABILITY PROBE (owner RULINGS 2026-09-13b) ──────────────────
#
# "Can this run decode LERC?" had no answer, so the fetcher's inability
# arrived at the index as a coverage answer.  The probe runs the SAME
# worker argv a real decode would spawn — frozen binary included — and
# asks it nothing but whether the codecs imported.
def test_the_selftest_argv_is_the_production_worker():
    argv = INSETS.lerc_selftest_argv()
    assert argv[:-1] == INSETS.lerc_worker_argv("IN", "OUT")[:-2]
    assert argv[-1] == "--selftest"


def test_the_selftest_answers_and_the_capability_is_memoised():
    completed = subprocess.run(INSETS.lerc_selftest_argv(),
                               capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stderr[-400:]
    INSETS._LERC_CAPABILITY[0] = None
    try:
        assert INSETS.lerc_decode_available() is True
        # Memoised: a second call spawns nothing.
        INSETS._LERC_CAPABILITY[0] = False
        assert INSETS.lerc_decode_available() is False
    finally:
        INSETS._LERC_CAPABILITY[0] = None


def test_the_ENGINE_ENTRY_answers_the_selftest():
    """The frozen dispatch carries the probe too, ahead of every heavy
    import — otherwise a packaged engine could not tell the difference
    between "no decoder" and "no data"."""
    completed = subprocess.run(
        [sys.executable, ENTRY, "--lerc-decode", "--selftest"],
        capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stderr[-400:]


def test_a_missing_decoder_raises_instead_of_answering_no_coverage(
        monkeypatch):
    """The 1.0.324 defect, in one assertion: the fetcher used to return
    an EMPTY list here, which became ``None``, which became a durable
    ``no-coverage`` for New Zealand's 1 m LiDAR at NZQN."""
    monkeypatch.setattr(INSETS, "lerc_decode_available", lambda: False)
    strategy = INSETS.ACCESS_STRATEGIES["static_stac"]()
    with pytest.raises(INSETS.ProviderUnavailable):
        strategy._decode_lerc_sources(
            {"code": "NEWZEALAND1M", "asset_compression": "lerc"},
            [{"href": "https://example.invalid/a.tif"}], "/tmp/unused")
