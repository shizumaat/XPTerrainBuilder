"""The Qt map band, tile pane row and "Use auto patch" for a tile with a
custom patch (#1229, owner RULINGS 2026-10-26c).  Offscreen, no network,
no engine: the window driven through its own handlers (the seam of
``test_qt_tile_customizations``)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

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
    assert window.use_auto_patch_btn.text() == CUSTOM.USE_AUTO_PATCH_TITLE

    window.use_auto_patch_btn.click()

    assert not os.path.exists(custom)
    assert os.path.isfile(custom + CUSTOM.SET_ASIDE_SUFFIX)  # never deleted
    assert not window._info_layout.isRowVisible(window.custom_patch_row)
    assert window.map.custom_patched() == set()
    assert _bands_drawn(window.map, monkeypatch) == 0


def test_no_custom_patch_no_row(window, tiles_dir):  # noqa: F811
    window._refresh_custom_patch((45, 5))
    assert not window._info_layout.isRowVisible(window.custom_patch_row)
