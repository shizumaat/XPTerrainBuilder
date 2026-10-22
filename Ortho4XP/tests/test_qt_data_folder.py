"""The Qt app opens the Mac app's data folder and can change it (#1266).

Both apps read ``~/.ortho4xp/data_root.txt`` (the Mac app writes it,
``DataRootPointer.swift``); Settings ▸ General's Data Folder row records a
new choice for the next launch.  The pointer file is redirected into the
test's tmp dir: the real one is never touched.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import pytest  # noqa: E402

SWIFT = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                     "XPTerrainBuilder")


@pytest.fixture
def pointer(tmp_path, monkeypatch):
    path = tmp_path / "home" / ".ortho4xp" / "data_root.txt"
    monkeypatch.setattr(FNAMES, "data_root_pointer_file", str(path))
    monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
    return path


def test_the_environment_wins_then_an_existing_remembered_folder(
        tmp_path, pointer, monkeypatch):
    assert FNAMES.remembered_data_root() is None   # first launch: ask
    chosen = tmp_path / "Data"
    FNAMES.write_data_root_pointer(str(chosen))
    assert FNAMES.remembered_data_root() is None   # unplugged: ask again
    chosen.mkdir()
    assert FNAMES.remembered_data_root() == str(chosen)
    monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(tmp_path / "Env"))
    assert FNAMES.remembered_data_root() == str(tmp_path / "Env")


def test_data_root_problem_creates_or_refuses(tmp_path):
    assert FNAMES.data_root_problem(str(tmp_path / "new" / "Data")) is None
    assert (tmp_path / "new" / "Data").is_dir()
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8", newline="")
    assert FNAMES.data_root_problem(str(blocker / "Data"))
    assert FNAMES.data_root_problem("")


def test_the_default_is_the_mac_apps():
    with open(os.path.join(SWIFT, "DataFolderSheet.swift"), encoding="utf-8") as f:
        assert 'appendingPathComponent("XPTerrainBuilderData")' in f.read()
    assert FNAMES.default_data_root() == os.path.join(
        os.path.expanduser("~"), "XPTerrainBuilderData")


def test_the_mac_app_writes_the_pointer_qt_reads():
    with open(os.path.join(SWIFT, "DataRootPointer.swift"), encoding="utf-8") as f:
        text = f.read()
    assert '".ortho4xp/data_root.txt"' in text
    assert FNAMES.data_root_pointer_file.endswith(
        os.path.join(".ortho4xp", "data_root.txt"))
    with open(os.path.join(SWIFT, "BuildModel.swift"), encoding="utf-8") as f:
        assert f.read().count("DataRootPointer.write(dataRootPath)") == 2


def test_settings_records_a_new_data_folder(qapp, tmp_path, pointer):
    import O4_Qt_Settings_General as GENERAL

    section = GENERAL.ApplicationSection("")
    try:
        assert section.data_label.text() == FNAMES.current_data_root()
        chosen = tmp_path / "Elsewhere"
        assert section.adopt_data_folder(str(chosen))
        assert FNAMES.read_data_root_pointer() == str(chosen)
        assert section.data_label.text() == str(chosen)
        assert not section.data_note.isHidden()   # takes effect on restart
    finally:
        section.deleteLater()


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    yield QApplication.instance() or QApplication([])
