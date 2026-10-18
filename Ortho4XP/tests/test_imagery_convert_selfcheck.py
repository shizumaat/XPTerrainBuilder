"""``--imagery-fetch-selfcheck … --convert N`` (#900): N textures converted concurrently
through the production convert path, cached JPEGs copied from ``--imagery-dir`` (read
only), the rest fetched; exit 0 only when every DDS lands whole.

Headless: the fetcher is a stub that writes a small JPEG; no network, no X-Plane.
"""

from __future__ import annotations

import os

import numpy
import O4_DDS_Encode as DDSENC
import O4_DDS_File as DDS
import O4_File_Names as FNAMES
import O4_Imagery_Fetch_Selfcheck as SELFCHECK
import O4_Imagery_Utils as IMG
import pytest
from PIL import Image

ARGS = ["BI", "16", "43.56", "-116.22"]


def _jpeg(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pixels = numpy.random.default_rng(0).integers(0, 256, (64, 64, 3), dtype=numpy.uint8)
    Image.fromarray(pixels, "RGB").save(path, quality=90)


@pytest.fixture
def selfcheck(tmp_path, monkeypatch):
    """A stub fetcher (records its downloads) and a read-only cache holding ONE of the
    four textures of the block; returns (out dir, cache dir, downloads)."""
    downloads = []

    def fetch(file_dir, name, *args, **kwargs):
        downloads.append(name)
        _jpeg(os.path.join(file_dir, name))

    monkeypatch.setattr(IMG, "download_jpeg_ortho", fetch)
    monkeypatch.setattr(IMG.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(FNAMES, "Imagery_dir", FNAMES.Imagery_dir)
    monkeypatch.setattr(FNAMES, "Tmp_dir", FNAMES.Tmp_dir)
    cache = tmp_path / "cache"
    til_x, til_y = 11552, 24032
    _jpeg(str(cache / "+40-120" / "+43-117" / "BI_16"
              / ("%d_%d_BI16.jpg" % (til_y, til_x))))
    monkeypatch.setattr(SELFCHECK, "_texture_block",
                        lambda x, y, n: [(til_x + 16 * i, til_y) for i in range(n)])
    return str(tmp_path / "out"), str(cache), downloads


def _run(out, cache, count=4):
    return SELFCHECK.main(["x", "--imagery-fetch-selfcheck", *ARGS, out,
                           "--convert", str(count), "--imagery-dir", cache])


def _dds_files(out):
    folder = os.path.join(out, "selfcheck", "build", "textures")
    return sorted(os.path.join(folder, f) for f in os.listdir(folder))


@pytest.mark.skipif(not DDSENC.ispc_available(), reason="needs ispc_texcomp")
def test_every_texture_converts_whole_and_the_cache_is_only_read(selfcheck, monkeypatch,
                                                                  capsys):
    out, cache, downloads = selfcheck
    monkeypatch.setenv(DDSENC.ENCODER_ENV, "inproc")
    before = sorted(os.walk(cache))

    assert _run(out, cache) == 0

    files = _dds_files(out)
    assert len(files) == 4 and all(DDS.is_whole(f) for f in files)
    # the fetch proof + the three textures the cache does not hold
    assert len(downloads) == 4
    assert sorted(os.walk(cache)) == before
    assert ("encoder=inproc textures=4 whole=4 failed=0"
            in capsys.readouterr().out)


def test_a_texture_neither_converter_makes_fails_the_selfcheck(selfcheck, monkeypatch,
                                                               capsys):
    out, cache, _downloads = selfcheck
    monkeypatch.setenv(DDSENC.ENCODER_ENV, "inproc")
    monkeypatch.setattr(DDSENC, "ispc_available", lambda: True)

    def broken(*args):
        raise RuntimeError("encoder broke")

    monkeypatch.setattr(DDSENC, "encode_texture", broken)
    monkeypatch.setattr(IMG.subprocess, "call", lambda command, **kwargs: 1)

    assert _run(out, cache, count=2) == 1
    assert "textures=2 whole=0 failed=2" in capsys.readouterr().out


def test_bad_convert_arguments_are_refused(capsys):
    assert SELFCHECK.main(["x", "--imagery-fetch-selfcheck", *ARGS, "out",
                           "--convert", "many"]) == 2
    assert "--convert N" in capsys.readouterr().out
