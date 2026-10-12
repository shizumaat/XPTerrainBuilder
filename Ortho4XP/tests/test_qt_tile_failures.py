"""The Qt layout of a tile failure / warning (issue #562, #564): the engine's
three sentences reach the console, the run report and the run's one box;
the technical detail stays behind the disclosure.  Pure — no Qt import."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Qt_Tile_Failures as QTFAIL  # noqa: E402
import O4_Tile_Failures as FAIL  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402


def _failed():
    return SESSION.build_done(45, -123, False, [FAIL.record(
        "elevation_download_failed",
        "ElevationDownloadRefused: REFUSING to build this tile")])


def _warned():
    return SESSION.build_done(47, -123, True, [
        FAIL.record("pack_dump_stale", "(build) [v2] stale", airport=a)
        for a in ("AAAA", "BBBB")])


def test_the_module_imports_no_qt():
    source = open(QTFAIL.__file__, encoding="utf-8").read()
    assert "\nfrom PySide6" not in source and "\nimport PySide6" not in source
    assert source.index("# --- Qt ---") < source.index("from PySide6")


def test_console_block_is_what_why_remedy_then_detail():
    lines = QTFAIL.console_lines(_failed())
    assert lines[0] == ("*** Tile +45-123 was not built: its elevation data "
                        "could not be downloaded.")
    assert "internet connection" in lines[2]
    assert lines[3].startswith("      detail: ElevationDownloadRefused")
    assert QTFAIL.console_lines(_warned())[0].startswith(
        "Warning: Tile +47-123 was built, but scenery for airports AAAA "
        "and BBBB")
    assert QTFAIL.console_lines(SESSION.build_done(1, 2, True, [])) == []


def test_report_phrase():
    assert QTFAIL.report_phrase(_failed()) == (
        "its elevation data could not be downloaded.")
    assert QTFAIL.report_phrase(_warned()) == "with warnings"
    assert QTFAIL.report_phrase(SESSION.build_done(1, 2, True, [])) == ""


def test_one_box_per_run_with_the_detail_behind_the_disclosure():
    assert QTFAIL.box_texts([SESSION.build_done(1, 2, True, [])]) is None
    (title, body, detail) = QTFAIL.box_texts([_failed(), _warned()])
    assert title == "1 tile was not built, 1 built with warnings"
    assert "REFUSING" not in body and "[v2]" not in body
    assert "REFUSING" in detail and "AAAA: (build) [v2] stale" in detail
    assert body.count("\n\n") == 1


def test_run_report_says_built_with_warnings():
    import pytest
    pytest.importorskip("PySide6")
    import O4_Qt_GUI as GUI
    (summary, _lines) = GUI._compose_run_report(
        [(47, -123)], {(47, -123): (True, "with warnings", 60.0)},
        {(47, -123): ("done", "", 100)}, 61.0, stopped=False)
    assert summary == "Tile +47-123 finished in 1 m 00 s with warnings."


def test_the_report_button_gets_the_engines_redacted_report(tmp_path,
                                                            monkeypatch):
    """#565: the in-process form of the ``failure_report`` command, fed the
    BuildDone's own entries unchanged; "Save report file" writes it."""
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "data_path", lambda rel: str(tmp_path / rel))
    result = QTFAIL.tile_report(_failed(), app_version="9.9")
    assert "+45-123" in result["title"]
    assert "elevation_download_failed" in result["report"]
    assert result["issue_url"].startswith("https://github.com/")
    assert result["saved_path"] == ""
    target = tmp_path / "out" / result["file_name"]
    target.parent.mkdir()
    saved = QTFAIL.tile_report(_failed(), save_path=str(target))
    assert saved["saved_path"] == str(target) and target.is_file()


def test_the_button_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "TileFailure.swift")
    if not os.path.exists(swift):
        import pytest
        pytest.skip("Swift sources not present in this tree")
    with open(swift, encoding="utf-8") as handle:
        source = handle.read()
    for text in (QTFAIL.REPORT_BUTTON, QTFAIL.SAVE_REPORT_BUTTON,
                 QTFAIL.REPORT_PREVIEW_TITLE, QTFAIL.OPEN_ISSUE_BUTTON):
        assert '"%s"' % text in source, text
