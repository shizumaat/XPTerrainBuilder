"""The Qt map band, tile pane row and the per-airport picker ("As made" /
"Our auto patch") for a tile with a custom patch (#1229, #2179; owner
RULINGS 2026-10-26c, 2026-11-23d/f).  Offscreen, no network,
no engine: the window driven through its own handlers (the seam of
``test_qt_tile_customizations``)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Custom_Patch_Use as USE  # noqa: E402
import O4_Custom_Patches as CUSTOM  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
from test_qt_tile_customizations import window  # noqa: E402,F401
from test_tile_customizations import make_data  # noqa: E402


@pytest.fixture
def tiles_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    return make_data(tmp_path, monkeypatch)


def _bands_drawn(tile_map, monkeypatch):
    drawn = []
    monkeypatch.setattr(tile_map, "_draw_custom_patch_band",
                        lambda painter, r, scale: drawn.append(r))
    tile_map.grab()
    return len(drawn)


def test_band_row_and_use_auto_patch(window, tiles_dir, monkeypatch):  # noqa: F811
    tile = (45, 5)
    directory = FNAMES.patch_dir(*tile)
    os.makedirs(directory)
    custom = os.path.join(directory, "LFLS.patch.osm")
    with open(custom, "w", encoding="utf-8", newline="") as handle:
        handle.write("<osm/>")

    # The band: an UNBUILT tile carries it too — a patch dropped in before
    # the first build already stops the auto patch.
    window.map.resize(600, 600)
    window.map.center_on_tile(45, 5, zoom=7)
    window._refresh_custom_patch_tiles()
    assert window.map.custom_patched() == {tile}
    assert _bands_drawn(window.map, monkeypatch) == 1

    window._refresh_custom_patch(tile)
    assert window._info_layout.isRowVisible(window.custom_patch_row)
    assert window.custom_patch_label.text() == CUSTOM.info_text(
        ["LFLS.patch.osm"])
    combo = window.custom_patch_use.combos["LFLS"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        CUSTOM.AS_MADE_TITLE, CUSTOM.AUTO_PATCH_TITLE]
    assert combo.currentText() == CUSTOM.AS_MADE_TITLE      # the default
    assert CUSTOM.AS_MADE_WARNING in window.custom_patch_use.warnings[
        "LFLS"].text()

    combo.setCurrentIndex(1)                     # Our auto patch

    assert os.path.isfile(custom)                # never renamed
    assert USE.use_of(FNAMES.patch_dir(*tile), "LFLS") == ("auto_patch", True)
    combo = window.custom_patch_use.combos["LFLS"]
    assert combo.currentText() == CUSTOM.AUTO_PATCH_TITLE
    assert window.custom_patch_use.warnings["LFLS"].text() == ""
    # the patch is still installed: the row and the band stay
    assert window._info_layout.isRowVisible(window.custom_patch_row)
    assert window.map.custom_patched() == {tile}


def test_no_custom_patch_no_row(window, tiles_dir):  # noqa: F811
    window._refresh_custom_patch((45, 5))
    assert not window._info_layout.isRowVisible(window.custom_patch_row)


def test_the_picker_waits_only_for_its_own_tile(window, tiles_dir):  # noqa: F811
    """#1922: another tile building leaves the picker enabled; the
    tile queued or building in the run disables it."""
    tile, other = (45, 5), (46, 6)
    os.makedirs(FNAMES.patch_dir(*tile))
    with open(os.path.join(FNAMES.patch_dir(*tile), "LFLS.patch.osm"), "w",
              encoding="utf-8", newline="") as handle:
        handle.write("<osm/>")
    window._building = True
    window._run_tiles = {other}
    window._progress_states[other] = ("active", "building", 10)
    window._refresh_custom_patch(tile)
    assert window.custom_patch_use.combos["LFLS"].isEnabled()
    window._run_tiles.add(tile)
    window._progress_states[tile] = ("queued", "queued", 0)
    window._refresh_custom_patch(tile)
    assert not window.custom_patch_use.combos["LFLS"].isEnabled()
    window._building = False


@pytest.mark.parametrize("answer", ["use", "keep"])
def test_the_elevation_notice_is_asked_once(window, tiles_dir, monkeypatch,  # noqa: F811
                                           answer):
    """#2179: the engine's notice, its two answers in the engine's words
    (the Mac app's alert: ``O4CustomPatchText``), remembered either way;
    "Use our auto patch" switches that airport to it (nothing renamed)."""
    import O4_Qt_GUI as GUI

    tile = (45, 5)
    os.makedirs(FNAMES.patch_dir(*tile))
    custom = os.path.join(FNAMES.patch_dir(*tile), "LFLS.patch.osm")
    with open(custom, "w", encoding="utf-8", newline="") as handle:
        handle.write("<osm/>")
    notice = {"icao": "LFLS", "file": "LFLS.patch.osm", "source": "x",
              "text": CUSTOM._notice_text("LFLS.patch.osm", "x")}
    asked, seen = [], []
    monkeypatch.setattr(CUSTOM, "custom_patch_tiles", lambda: [
        {"lat": 45, "lon": 5, "files": ["LFLS.patch.osm"],
         "notices": [] if seen else [notice]}])
    monkeypatch.setattr(CUSTOM, "notice_seen",
                        lambda lat, lon, file: seen.append(file))

    class Box:
        Information = GUI.QMessageBox.Information
        AcceptRole = GUI.QMessageBox.AcceptRole
        RejectRole = GUI.QMessageBox.RejectRole

        def __init__(self, icon, title, text, parent=None):
            asked.append((title, text))
            self.buttons = []

        def addButton(self, label, role):
            self.buttons.append(label)
            return label

        def exec(self):
            assert self.buttons == [CUSTOM.USE_AUTO_PATCH_TITLE,
                                    CUSTOM.KEEP_CUSTOM_PATCH_TITLE]

        def clickedButton(self):
            return self.buttons[0 if answer == "use" else 1]

    monkeypatch.setattr(GUI, "QMessageBox", Box)
    window._refresh_custom_patch_tiles()
    window._refresh_custom_patch_tiles()          # answered: not again
    assert asked == [(CUSTOM.CUSTOM_PATCH_TITLE, notice["text"])]
    assert seen == ["LFLS.patch.osm"]
    assert os.path.exists(custom)
    assert USE.use_of(FNAMES.patch_dir(*tile), "LFLS")[0] == (
        "auto_patch" if answer == "use" else "as_made")
