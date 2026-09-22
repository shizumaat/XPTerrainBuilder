"""KNOWN-ANSWER twin for ``tools/texture_seam_census.py`` (issue #1, GEN-2).

RULINGS 2026-08-06 "Instrument truth is law": every instrument carries a
calibration twin feeding it a case whose answer is known and asserting the
report.  Every answer below is hand-derived before it is asserted.  No
build, no network, ``tmp_path`` only.  The "DDS" files are uncompressed DDS
written by Pillow (the census opens them through the same ``Image.open`` it
uses for DXT ones).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "texture_seam_census.py"

N = 64  # texture edge in the twin (the census never assumes 4096)


def _load():
    spec = importlib.util.spec_from_file_location("texture_seam_census", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flat(rgb, n=N):
    return numpy.full((n, n, 3), rgb, dtype=numpy.uint8)


@pytest.fixture()
def synthetic_tile(tmp_path):
    """Three ZL16 textures of provider FAKE in a row (x = 0, 16, 32) plus
    one to the south of the first (y = 16), with sources under a
    ``grouped`` orthophoto layout.

    Source: every texture flat (100, 100, 100).
    Built:  A (y0,x0)  = source + (+10, 0, -10)  -> shift (+10, 0, -10)
            B (y0,x16) = source                  -> shift (0, 0, 0)
            C (y0,x32) = source + (+4, +4, +4)   -> shift (+4, +4, +4)
            D (y16,x0) = source, but its mask says the TOP half is water.
    Masks: B's ``textures/0_16_ZL16.png`` marks the left half water, so the
    A|B seam is judged on ALL rows (A's right strip and B's left strip are
    both land? no: B's left strip IS water) -> A|B has zero land rows;
    the D mask marks the top half water, so the A|D seam (A's bottom strip
    vs D's top strip) has zero land rows too; B|C has every row.
    """
    tile = tmp_path / "zOrtho4XP_+25+051"
    tex = tile / "textures"
    tex.mkdir(parents=True)
    ortho = tmp_path / "Orthophotos" / "+20+050" / "+25+051" / "FAKE_16"
    ortho.mkdir(parents=True)
    src = _flat((100, 100, 100))
    built = {
        "0_0": src.astype(int) + numpy.array([10, 0, -10]),
        "0_16": src.astype(int),
        "0_32": src.astype(int) + 4,
        "16_0": src.astype(int),
    }
    for stem, arr in built.items():
        Image.fromarray(src).save(ortho / f"{stem}_FAKE16.jpg", quality=100)
        Image.fromarray(arr.astype(numpy.uint8)).save(tex / f"{stem}_FAKE16.dds")
    mask_b = numpy.full((N, N), 255, numpy.uint8)
    mask_b[:, : N // 2] = 0  # left half water
    Image.fromarray(mask_b).save(tex / "0_16_ZL16.png")
    mask_d = numpy.full((N, N), 255, numpy.uint8)
    mask_d[: N // 2, :] = 0  # top half water
    Image.fromarray(mask_d).save(tex / "16_0_ZL16.png")
    return tile, tmp_path / "Orthophotos"


def test_shift_and_seam_known_answers(synthetic_tile):
    tile, ortho = synthetic_tile
    m = _load()
    report = m.census(tile, ortho, strip=4)
    by_name = {t["texture"]: t for t in report["textures"]}
    assert set(by_name) == {"0_0_FAKE16.dds", "0_16_FAKE16.dds",
                            "0_32_FAKE16.dds", "16_0_FAKE16.dds"}
    # JPEG quality 100 of a flat image is exact, so the shifts are exact.
    assert by_name["0_0_FAKE16.dds"]["shift"] == [10.0, 0.0, -10.0]
    assert by_name["0_16_FAKE16.dds"]["shift"] == [0.0, 0.0, 0.0]
    assert by_name["0_32_FAKE16.dds"]["shift"] == [4.0, 4.0, 4.0]
    assert by_name["0_16_FAKE16.dds"]["land_fraction"] == pytest.approx(0.5)
    assert by_name["0_16_FAKE16.dds"]["land_source"] == "tile-mask"
    assert by_name["0_0_FAKE16.dds"]["land_source"] in ("no-masks-dir", "no-mask-square")
    # B's land median is measured on land pixels only.
    assert by_name["0_16_FAKE16.dds"]["median_src_land"] == [100.0, 100.0, 100.0]

    seams = {(s["a"], s["b"]): s for s in report["seams"]}
    assert set(seams) == {
        ("0_0_FAKE16.dds", "0_16_FAKE16.dds"),   # A|B east
        ("0_0_FAKE16.dds", "16_0_FAKE16.dds"),   # A|D south
        ("0_16_FAKE16.dds", "0_32_FAKE16.dds"),  # B|C east
    }
    ab = seams[("0_0_FAKE16.dds", "0_16_FAKE16.dds")]
    assert ab["land_rows"] == 0 and ab["introduced"] is None  # water side
    ad = seams[("0_0_FAKE16.dds", "16_0_FAKE16.dds")]
    assert ad["direction"] == "S" and ad["land_rows"] == 0
    bc = seams[("0_16_FAKE16.dds", "0_32_FAKE16.dds")]
    assert bc["land_rows"] == N
    assert bc["step_src"] == [0.0, 0.0, 0.0]
    assert bc["step_dds"] == [4.0, 4.0, 4.0]
    assert bc["introduced"] == [4.0, 4.0, 4.0] and bc["max_abs"] == 4.0

    summary = m.summarize(report, bar=2.0)
    assert summary["seams"] == 3 and summary["seams_all_water"] == 2
    assert summary["seams_judged"] == 1 and summary["seams_over_bar"] == 1
    assert summary["max_introduced_step"] == 4.0
    assert summary["max_texture_shift"] == 10.0


def test_cli_fail_over_bar_and_json(synthetic_tile, tmp_path, capsys):
    tile, ortho = synthetic_tile
    m = _load()
    out = tmp_path / "census.json"
    rc = m.main([str(tile), "--orthophotos", str(ortho), "--strip", "4",
                 "--json", str(out), "--fail-over-bar"])
    assert rc == 1  # the B|C seam introduces 4 counts > the 2-count bar
    assert json.loads(out.read_text())["summary"]["seams_over_bar"] == 1
    rc = m.main([str(tile), "--orthophotos", str(ortho), "--strip", "4",
                 "--bar", "5", "--fail-over-bar"])
    assert rc == 0
    assert "seams_over_bar" in capsys.readouterr().out


def test_simulate_harmonizer_predicts_constant_step(synthetic_tile):
    """The shipped harmonizer on two flat sources with a 40-count cast:
    ZL16 strength 0.7, targets = neighbourhood median.  Sources are
    remade here: A = 100, B = 140, C = 140 (all land, no masks) so the
    3-texture row has target 140 everywhere; A's shift is
    clip(0.7 * 40) = +28 -> capped to +20; B and C shift 0.  Predicted
    A|B step is therefore exactly -20 per channel."""
    tile, ortho = synthetic_tile
    sub = ortho / "+20+050" / "+25+051" / "FAKE_16"
    for f in (tile / "textures").glob("*_ZL16.png"):
        f.unlink()
    for stem, value in (("0_0", 100), ("0_16", 140), ("0_32", 140)):
        Image.fromarray(_flat((value, value, value))).save(
            sub / f"{stem}_FAKE16.jpg", quality=100)
    (sub / "16_0_FAKE16.jpg").unlink()
    m = _load()
    sim = m.simulate_harmonizer(tile, ortho, ["FAKE"], [16])
    shifts = {t["texture"]: t["shift"] for t in sim["textures"]}
    assert shifts == {"0_0_FAKE16": [20, 20, 20], "0_16_FAKE16": [0, 0, 0],
                      "0_32_FAKE16": [0, 0, 0]}
    seams = {(s["a"], s["b"]): s["predicted"] for s in sim["seams"]}
    assert seams == {("0_0_FAKE16", "0_16_FAKE16"): [-20, -20, -20],
                     ("0_16_FAKE16", "0_32_FAKE16"): [0, 0, 0]}
