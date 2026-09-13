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
