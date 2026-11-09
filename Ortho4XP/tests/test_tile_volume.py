"""#1987: a tile whose folder lives on another drive — the engine rule
(``O4_Tile_Volume``), the scan's ``TileInfo`` fields, and the Qt map and
tile pane that read them.  The Mac twin is ``TileVolumeTests`` (SceneryKit
parsing + words).  Fixtures are temp-dir links; the "unmounted drive" is a
link to a ``/Volumes/<name>`` that does not exist.
"""

import os
import sys
import uuid
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Tile_Info as TINFO  # noqa: E402
import O4_Tile_Volume as TVOL  # noqa: E402

posix_links = pytest.mark.skipif(sys.platform.startswith("win"),
                                 reason="POSIX symlinks to /Volumes")


@pytest.mark.parametrize("path,name", [
    ("/Volumes/ThunderBlade/Custom Scenery Library/x", "ThunderBlade"),
    ("/Volumes/My Drive", "My Drive"),
    ("/media/noah/Scenery/x", "Scenery"),
    ("/run/media/noah/Scenery/x", "Scenery"),
    ("/mnt/data/pack", "data"),
    ("E:\\Scenery\\pack", "E:"),
    ("\\\\?\\f:\\x", "F:"),
    ("/Users/noah/X-Plane 12/Custom Scenery", ""),
    ("/Volumes", ""),
    ("", ""),
])
def test_volume_name_names_the_drive_mounted_or_not(path, name):
    assert TVOL.volume_name(path) == name


def test_the_words():
    assert TVOL.requires_label("ThunderBlade") == "Requires ThunderBlade"
    assert TVOL.offline_note("ThunderBlade") == "ThunderBlade is not connected."


def _gone_volume():
    return "/Volumes/O4TestGone_%s" % uuid.uuid4().hex[:8]


def test_a_plain_folder_is_on_its_parents_drive(tmp_path):
    tile = tmp_path / "zOrtho4XP_+10+010"
    tile.mkdir()
    resolved, volume, mounted = TVOL.tile_volume(str(tile))
    assert resolved == os.path.realpath(str(tile))
    assert (volume, mounted) == ("", True)


@posix_links
def test_a_link_to_an_unmounted_drive_names_it(tmp_path):
    gone = _gone_volume()
    target = gone + "/Ortho4XP/zOrtho4XP_+10+010"
    link = tmp_path / "zOrtho4XP_+10+010"
    os.symlink(target, link)
    resolved, volume, mounted = TVOL.tile_volume(str(link))
    assert resolved == target
    assert volume == os.path.basename(gone)
    assert mounted is False


@posix_links
def test_a_custom_scenery_on_the_same_drive_is_not_external(tmp_path, monkeypatch):
    # The whole folder is on drive "Ext": a tile there needs nothing extra.
    monkeypatch.setattr(TVOL, "volume_name", lambda path: "Ext")
    tile = tmp_path / "zOrtho4XP_+10+010"
    tile.mkdir()
    assert TVOL.tile_volume(str(tile))[1] == ""


def _tile_with_dsf(root, lat=10, lon=10):
    import O4_File_Names as FNAMES
    folder = root / ("zOrtho4XP_" + FNAMES.short_latlon(lat, lon))
    end = folder / "Earth nav data" / FNAMES.round_latlon(lat, lon)
    end.mkdir(parents=True)
    (end / (FNAMES.short_latlon(lat, lon) + ".dsf")).write_bytes(b"x")
    return folder


@posix_links
def test_the_scan_keeps_a_tile_whose_drive_is_away(tmp_path):
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    gone = _gone_volume()
    os.symlink(gone + "/Ortho4XP/zOrtho4XP_+10+010",
               scenery / "zOrtho4XP_+10+010")
    tiles = TINFO.scan_tiles(str(scenery))
    info = tiles[(10, 10)]
    assert info.volume == os.path.basename(gone)
    assert info.volume_mounted is False
    assert info.dsf_present is True
    assert info.resolved_dir == gone + "/Ortho4XP/zOrtho4XP_+10+010"


@posix_links
def test_a_broken_link_on_the_system_drive_is_still_skipped(tmp_path):
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    os.symlink(str(tmp_path / "nowhere"), scenery / "zOrtho4XP_+10+010")
    assert TINFO.scan_tiles(str(scenery)) == {}


@posix_links
def test_the_scan_resolves_a_linked_tile(tmp_path, monkeypatch):
    library = tmp_path / "Library"
    library.mkdir()
    real = _tile_with_dsf(library)
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    os.symlink(real, scenery / real.name)
    # The library stands in for an external drive.
    monkeypatch.setattr(
        TVOL, "volume_name",
        lambda path: "Lib" if "/Library" in path else "")
    info = TINFO.scan_tiles(str(scenery))[(10, 10)]
    assert info.resolved_dir == os.path.realpath(str(real))
    assert (info.volume, info.volume_mounted) == ("Lib", True)
    assert info.build_dir == str(scenery / real.name)


# ─── the Qt map and tile pane ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _info(volume="", mounted=True, resolved="/Volumes/Ext/zOrtho4XP_+10+010"):
    return TINFO.TileInfo(lat=10, lon=10, build_dir="/cs/zOrtho4XP_+10+010",
                          dir_name="zOrtho4XP_+10+010", dsf_present=True,
                          resolved_dir=resolved, volume=volume,
                          volume_mounted=mounted)


def test_the_qt_map_draws_an_external_tile_brown(qapp, tmp_path, monkeypatch):
    import O4_Qt_Map as QTMAP
    monkeypatch.setattr(QTMAP, "livemap_cache_dir",
                        lambda: str(tmp_path / "livemap"))
    view = QTMAP.MapView()
    view._start_workers = lambda: None
    view._update_timer.stop()
    try:
        colors = []
        for info in (_info(), _info(volume="Ext")):
            view.set_built({(10, 10): info})
            painter = mock.MagicMock()
            view._draw_tile_overlay(painter, (10, 10), 1.0)
            pen = painter.setPen.call_args_list[0].args[0]
            colors.append(pen.color().name().upper())
        assert colors == [QTMAP.BUILT_COLOR.upper(),
                          QTMAP.BUILT_EXTERNAL_COLOR.upper()]
    finally:
        view.deleteLater()


def test_the_qt_map_says_requires_top_right(qapp):
    import O4_Qt_Map_Labels as QTLABELS
    from PySide6.QtCore import QPointF
    painter = mock.MagicMock()

    def point_of(lat, lon):
        return QPointF((lon - 10) * 400.0, (11 - lat) * 400.0)

    QTLABELS.paint_tile_labels(
        painter, point_of, 1e9, (10.2, 10.8, 10.2, 10.8),
        lambda lat, lon: "+%02d+%03d" % (lat, lon),
        {(10, 10): _info(volume="Ext")}, None)
    texts = [c.args[2] for c in painter.drawText.call_args_list]
    assert "Requires Ext" in texts
    rects = [c.args[0] for c in painter.drawText.call_args_list
             if c.args[2] == "Requires Ext"]
    assert rects[0].right() == pytest.approx(400.0 - 4)


def test_the_qt_path_row(qapp):
    import O4_Qt_Tile_Path_Row as ROW
    row = ROW.TilePathRow()
    row.show_info(_info(volume="Ext", mounted=False))
    assert row.path_label.text() == "/Volumes/Ext/zOrtho4XP_+10+010"
    assert not row.reveal_button.isEnabled()
    assert row.note_label.text() == "Ext is not connected."
    assert not row.note_label.isHidden()
    row.show_info(_info(volume="Ext", mounted=True))
    assert row.reveal_button.isEnabled()
    assert row.note_label.isHidden()
    row.show_info(None)
    assert row.path_label.text() == "—"
    assert not row.reveal_button.isEnabled()
    row.deleteLater()
