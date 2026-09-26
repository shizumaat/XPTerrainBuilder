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


def test_harness_build_dir_resolves_its_tile_and_a_vacuous_census_refuses(
        synthetic_tile, tmp_path, capsys):
    """A harness lane build dir is ``tile_<tag>``, not ``zOrtho4XP_+LL+LLL``.
    The tile must come from the dir's own products, else every source JPEG
    reads as absent, 0 seams are judged and ``--fail-over-bar`` passed
    vacuously (hv2 closing arm 2026-09-25: 0 of 186 textures sourced)."""
    tile, ortho = synthetic_tile
    m = _load()
    lane_dir = tmp_path / "tile_hv2"
    tile.rename(lane_dir)
    rc = m.main([str(lane_dir), "--orthophotos", str(ortho), "--strip", "4",
                 "--bar", "5", "--fail-over-bar"])
    assert rc == 2  # no product names the tile: 0 judged -> REFUSING
    assert "REFUSING" in capsys.readouterr().err
    (lane_dir / "Data+25+051.mesh").write_text("")
    report = m.census(lane_dir, ortho, strip=4)
    assert sum(t["source_found"] for t in report["textures"]) == 4
    rc = m.main([str(lane_dir), "--orthophotos", str(ortho), "--strip", "4",
                 "--bar", "5", "--fail-over-bar"])
    assert rc == 0


def test_land_threshold_excludes_the_feather_band(synthetic_tile, tmp_path):
    """``LAND_THRESHOLD`` is 250, not 128: the feathered shore band is not
    land (colour-harmonization spec §2.1 / §5 Q6).  The instrument and the
    mechanism must mean the same thing by "land", or the census judges
    seams on pixels the solver never measured."""
    tile, ortho = synthetic_tile
    m = _load()
    assert m.LAND_THRESHOLD == 250
    mask = numpy.full((N, N), 255, numpy.uint8)
    mask[:, N // 2 :] = 200  # feather: shore, wet sand, shallow water
    Image.fromarray(mask).save(tile / "textures" / "0_0_ZL16.png")
    land, source = m._load_land(tile, 0, 0, 16, N)
    assert source == "tile-mask"
    assert land[:, : N // 2].all() and not land[:, N // 2 :].any()


def test_simulate_harmonizer_v2_leaves_no_step_at_the_seam(synthetic_tile):
    """THE regression this whole rework exists for, on the same case the v1
    twin used to pin: A = 100, B = 140, C = 140, all land, ZL16 strength
    0.70.

    v1 gave each texture ONE constant (A clipped to +20, B and C zero) and
    therefore predicted a −20-count step right down the A|B seam.  v2
    solves a field: the measured +40 cast is cancelled to the spec's −28
    residual between the NODE values (+18.5 vs −9.3), but because both
    textures evaluate the same interpolant on the seam itself, the step the
    correction introduces THERE is zero.  That is the difference between a
    per-texture shift and a field.
    """
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
    assert sim["version"] == 2
    assert sim["casts"] == {"16_FAKE": 2}  # two east casts, +40 and 0

    nodes = {t["texture"]: t["node"][0] for t in sim["textures"]}
    assert nodes["0_0_FAKE16"] == pytest.approx(18.5, abs=0.5)
    assert nodes["0_16_FAKE16"] == pytest.approx(-9.3, abs=0.5)
    assert nodes["0_16_FAKE16"] - nodes["0_0_FAKE16"] == pytest.approx(
        -28.0, abs=0.5)
    # Every texture is a witness (all land) and none clips at the cap.
    assert all(t["witness"] for t in sim["textures"])
    assert max(abs(v) for t in sim["textures"] for v in t["shift_max"]) < 20

    seams = {(s["a"], s["b"]): s for s in sim["seams"]}
    assert set(seams) == {("0_0_FAKE16", "0_16_FAKE16"),
                          ("0_16_FAKE16", "0_32_FAKE16")}
    for seam in seams.values():
        assert seam["predicted"] == [0, 0, 0]
        assert seam["max_abs"] <= 1.0
    summary = m.print_simulation(sim, bar=2.0, top=5)
    assert summary["seams_over_bar"] == 0
    assert summary["max_predicted_step"] <= 1.0
    assert summary["witnesses"] == 3
    assert summary["all_water_textures_with_shift"] == 0
    # No whole-tile hue drift: the witness nodes average out (spec §2.3).
    assert max(abs(v) for v in summary["mean_witness_node"]) < 0.5


@pytest.fixture()
def nested_zoom_tile(synthetic_tile):
    """One ZL18 texture nested inside the ZL16 texture at (0, 0).

    ZL16 (0,0): source 100, built 100  -> no shift.
    ZL18 (0,0): source 104, built 110  -> the build moved it +6 relative to
    the ZL16 square around it.  factor = 4, sub-square (0, 0), so the ZL18
    texture sits in the coarse texture's top-left sixteenth and all four of
    its edges are zone edges (it has no ZL18 neighbour).
    """
    tile, ortho = synthetic_tile
    fine = ortho / "+20+050" / "+25+051" / "FAKE_18"
    fine.mkdir(parents=True)
    Image.fromarray(_flat((104, 104, 104))).save(
        fine / "0_0_FAKE18.jpg", quality=100)
    Image.fromarray(_flat((110, 110, 110))).save(
        tile / "textures" / "0_0_FAKE18.dds")
    # Make the covering ZL16 texture unshifted so the arithmetic is clean.
    Image.fromarray(_flat((100, 100, 100))).save(
        tile / "textures" / "0_0_FAKE16.dds")
    for f in (tile / "textures").glob("*_ZL16.png"):
        f.unlink()
    return tile, ortho


def test_cross_zl_seams_measure_the_nested_zone_edge(nested_zoom_tile):
    """Spec §2.5.  The ZL18 texture's outer strips are compared with the
    co-located sub-strips of the ZL16 texture covering it:
    ``step = coarse − fine`` is 100 − 110 = −10 in the DDS and
    100 − 104 = −4 in the source, so the build INTRODUCED −6 counts at a
    zone edge no same-zoom pair covers."""
    tile, ortho = nested_zoom_tile
    m = _load()
    report = m.census(tile, ortho, strip=4, cross_zl=True)
    cross = [s for s in report["seams"] if s.get("cross_zl")]
    assert report["cross_zl_seams"] == 4  # one per side of the ZL18 texture
    assert {s["direction"] for s in cross} == {"L", "R", "T", "B"}
    for seam in cross:
        assert seam["a"] == "0_0_FAKE18.dds" and seam["b"] == "0_0_FAKE16.dds"
        assert seam["land_rows"] == 16  # 64 fine rows block-averaged to 64/4
        assert seam["step_dds"] == [-10.0, -10.0, -10.0]
        assert seam["step_src"] == [-4.0, -4.0, -4.0]
        assert seam["introduced"] == [-6.0, -6.0, -6.0]
        assert seam["max_abs"] == 6.0
    summary = m.summarize(report, bar=2.0)
    assert summary["seams_cross_zl"] == 4


def test_cross_zl_is_opt_in(nested_zoom_tile):
    """Without the flag the zone edge is simply not reported, and nothing
    else about the census changes."""
    tile, ortho = nested_zoom_tile
    m = _load()
    report = m.census(tile, ortho, strip=4)
    assert report["cross_zl_seams"] == 0
    assert not any(s.get("cross_zl") for s in report["seams"])
    assert m.summarize(report, bar=2.0)["seams_cross_zl"] == 0
    # The CLI flag turns it on.
    rc = m.main([str(tile), "--orthophotos", str(ortho), "--strip", "4",
                 "--cross-zl", "--bar", "2", "--fail-over-bar"])
    assert rc == 1  # the -6-count zone edge is over the 2-count bar
