"""The About dialog carries the build triple (beta plan §1 B3(3)).

A beta report that says "1.0.347" identifies nothing: the app version, the
engine version and the commit are three independent numbers, and the About
box is where a tester copies them from.  Guarded here:

* ``O4_Build_Info.build_info()`` reads the artifact-root ``VERSION.txt``
  written by ``scripts/write_version_txt.sh`` (``app=`` / ``engine=`` /
  ``sha=``), tolerates the pre-B3 bare-engine-version file, and reports
  ``dev`` for whatever it cannot know rather than guessing;
* the Qt Help ▸ About body shows all three.

Headless (offscreen platform); the About body is rendered without opening
a modal dialog, which no CI runner could dismiss.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------
def test_reads_the_triple_from_an_artifact_root(tmp_path, monkeypatch):
    import O4_Build_Info

    (tmp_path / "VERSION.txt").write_text(
        "app=1.0.347\nengine=1.50.1793\nsha=5883949fdeadbeef\n", encoding="utf-8"
    )
    monkeypatch.setattr(O4_Build_Info, "_artifact_roots", lambda: [str(tmp_path)])
    info = O4_Build_Info.build_info()
    assert (info.app, info.engine, info.sha) == ("1.0.347", "1.50.1793", "5883949fdeadbeef")


def test_missing_file_reports_dev_not_a_guess(tmp_path, monkeypatch):
    import O4_Build_Info
    import O4_Version

    monkeypatch.setattr(O4_Build_Info, "_artifact_roots", lambda: [str(tmp_path)])
    info = O4_Build_Info.build_info()
    assert info.app == "dev"
    assert info.sha == "dev"
    # The engine version is importable in a dev tree, so it is never "dev".
    assert info.engine == O4_Version.version


def test_pre_b3_bare_engine_version_file_is_still_understood(tmp_path, monkeypatch):
    import O4_Build_Info

    (tmp_path / "VERSION.txt").write_text("1.50.1700\n", encoding="utf-8")
    monkeypatch.setattr(O4_Build_Info, "_artifact_roots", lambda: [str(tmp_path)])
    info = O4_Build_Info.build_info()
    assert info.engine == "1.50.1700"
    assert (info.app, info.sha) == ("dev", "dev")


def test_as_lines_labels_all_three(tmp_path, monkeypatch):
    import O4_Build_Info

    (tmp_path / "VERSION.txt").write_text(
        "app=1.0.347\nengine=1.50.1793\nsha=abc1234\n", encoding="utf-8"
    )
    monkeypatch.setattr(O4_Build_Info, "_artifact_roots", lambda: [str(tmp_path)])
    lines = O4_Build_Info.build_info().as_lines().splitlines()
    assert len(lines) == 3
    assert "1.0.347" in lines[0] and "App" in lines[0]
    assert "1.50.1793" in lines[1] and "Engine" in lines[1]
    assert "abc1234" in lines[2] and "Commit" in lines[2]


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_qt_about_body_shows_the_triple(qapp, tmp_path, monkeypatch, capsys):
    import O4_Build_Info
    import O4_Qt_GUI as GUI
    import O4_UI_Utils as UI

    (tmp_path / "VERSION.txt").write_text(
        "app=1.0.347\nengine=1.50.1793\nsha=5883949f\n", encoding="utf-8"
    )
    monkeypatch.setattr(O4_Build_Info, "_artifact_roots", lambda: [str(tmp_path)])
    monkeypatch.setattr(GUI, "PREFS_FILE", str(tmp_path / "prefs.json"))

    with capsys.disabled():
        original_stdout = sys.stdout
        window = GUI.MainWindow()
        sys.stdout = original_stdout
    try:
        body = window.about_text()
        for expected in ("1.0.347", "1.50.1793", "5883949f"):
            assert expected in body, body
    finally:
        window.deleteLater()
        UI.engine_session = None
