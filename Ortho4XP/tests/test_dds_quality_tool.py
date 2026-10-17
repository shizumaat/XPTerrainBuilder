"""Twin of ``tools/dds_quality.py``: it runs the converter exactly as ``convert_texture``
does, and scores and tabulates what it measured."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

import O4_DDS_Encode as ENCODE

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import dds_quality as Q  # noqa: E402


def test_tool_command_is_the_convert_site_argv(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert Q.tool_command(True, "a.png", "b.dds", "/x/DDSTool") == [
        "/x/DDSTool", "--png2dxt5", "a.png", "b.dds"]
    monkeypatch.setattr(sys, "platform", "linux")
    assert Q.tool_command(False, "a.jpg", "b.dds", "/x/nvcompress") == [
        "/x/nvcompress", "-bc1", "-fast", "a.jpg", "b.dds"]


@pytest.mark.skipif(not ENCODE.ispc_available(), reason="needs ispc_texcomp")
def test_score_and_table(tmp_path) -> None:
    from PIL import Image

    rng = np.random.default_rng(3)
    rgb = (np.add.outer(np.arange(64), np.arange(64)) * 2 % 256).astype(np.uint8)
    img = np.dstack([rgb, rgb[::-1], rng.integers(0, 256, (64, 64), np.uint8)])
    path = str(tmp_path / "t.png")
    Image.fromarray(img, "RGB").save(path)
    dds_path = str(tmp_path / "t.dds")
    ENCODE.encode_file(path, "bc1", dds_path)
    src = Q.source_pixels(path, None)
    rows = Q.score(dds_path, Q.MIPS.mip_chain(src, levels=3), False)
    assert len(rows) == 3 and all(r["psnr"] > 25 and 0 < r["ssim"] <= 1 for r in rows)
    fake = {"texture": "t", "fmt": "bc1", "seconds": {"tool": [2.0], "inproc": [0.5]},
            "tool": rows, "inproc": rows}
    text = Q.table([fake], 3)
    assert "| 0 |" in text and "+0.00" in text and "inproc: 0.500-0.500 s" in text
