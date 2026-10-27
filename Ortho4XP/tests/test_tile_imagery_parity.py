"""A built tile's imagery: the cfg's, else the one its textures carry
(#1334).  The Mac app resolves it the same way; both read
``Tests/SceneryKitTests/Fixtures/Imagery/tile_imagery.json``
(``TileImageryTests.swift``)."""
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

import O4_Custom_Scenery as PACKS  # noqa: E402
import O4_Tile_Info as TINFO  # noqa: E402

FIXTURE = os.path.join(REPO_ROOT, "..", "Tests", "SceneryKitTests", "Fixtures",
                       "Imagery", "tile_imagery.json")


def _fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def test_detection_matches_the_shared_fixture():
    for case in _fixture()["detect"]:
        found = PACKS.imagery_from_file_names(case["names"])
        expected = None if case["provider"] is None else (case["provider"], case["zl"])
        assert found == expected, case["names"]


def test_resolver_matches_the_shared_fixture():
    for case in _fixture()["resolve"]:
        found = TINFO.effective_imagery(case["info"])
        expected = None if case["expect"] is None else tuple(case["expect"])
        assert found == expected, case["info"]


def test_scan_reports_detected_imagery(tmp_path):
    import O4_File_Names as FNAMES

    build_dir = tmp_path / "zOrtho4XP_+47+011"
    dsf = build_dir / "Earth nav data" / FNAMES.round_latlon(47, 11) / "+47+011.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"")
    (build_dir / "textures").mkdir()
    for name in ("5424_8720_BI16.dds", "5440_8720_BI16.dds", "5424_8720_BI16.ter"):
        (build_dir / "textures" / name).write_bytes(b"")
    info = TINFO._build_tile_info(str(build_dir), 47, 11, build_dir.name)
    assert (info.detected_provider, info.detected_zl) == ("BI", 16)
    assert TINFO.effective_imagery(info) == ("BI", 16, TINFO.SOURCE_DETECTED)
