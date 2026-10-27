"""Headless tests for the Build box's Imagery and the build detail level
following the selection.

When tiles are selected on the map, the imagery-source combo and the build
detail level (``build_zl``, set in Settings since #1242) follow the
``default_website`` / ``default_zl`` recorded in the selected tiles'
per-tile configs.  When the selected tiles disagree on the source, the
combo unresolves to the "--" placeholder (``currentIndex() == -1``) and
``start_build`` refuses to run until the user picks one; disagreeing
detail levels keep the Settings value.  Tiles with no recorded value
impose nothing.

All offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no X-Plane
install.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402


def test_modules_resolve_to_this_worktree():
    """Guard against sys.path/conftest leakage from another checkout."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for module in (GUI, SM):
        assert os.path.abspath(module.__file__).startswith(here), (
            "%s resolved to %s, not this worktree" % (module, module.__file__)
        )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    # Isolate the prefs file BEFORE construction: MainWindow loads the
    # prefs in __init__ and closeEvent SAVES them.
    monkeypatch.setattr(GUI, "PREFS_FILE", str(tmp_path / "prefs.json"))
    # A fake X-Plane CIFP corpus: since beta plan §1 B2 the Build button
    # refuses while none resolves (tests/test_qt_first_run_xplane.py owns
    # that law), and these tests are about the imagery/ZL combos.
    cifp = tmp_path / "CIFP"
    cifp.mkdir()
    monkeypatch.setattr(SM, "read_global_raw",
                        lambda *a, **k: {"cifp_data_path": str(cifp),
                                         "custom_scenery_dir": ""})
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    # No boundary-airport preflight in these tests (see
    # tests/test_qt_boundary_dialog.py): an unanswered ask makes the
    # build start as it did before the preflight existed.
    monkeypatch.setattr(win._session, "boundary_airports",
                        lambda tiles=None: None)
    # Route all per-tile config reads/writes into the isolated temp dir.
    win.prefs["output_dir"] = str(tmp_path)
    # Headless runs skip the entry point's initialize_providers_dict(),
    # leaving the imagery combo empty; seed two stand-in codes.
    win.imagery_combo.addItems(["TEST_PROVIDER_A", "TEST_PROVIDER_B"])
    # Startup may have synced the combos from whatever tile the default
    # prefs activate; pin a known state for the assertions below.
    win.imagery_combo.setCurrentIndex(0)
    win.build_zl = 16
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()
        sys.stdout = saved_stdout


def _write_tile_cfg(window, lat, lon, website=None, zoomlevel=None):
    """Seed a per-tile config file with build provenance keys."""
    path = SM._tile_cfg_path(lat, lon, window.output_dir())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # STAMPED (owner RULINGS 2026-09-18c (2)): an unstamped tile cfg is a
    # pre-1.0.352 file, MOVED aside on first touch rather than read.
    lines = [SM.tile_cfg_stamp_line().rstrip("\n")]
    if website is not None:
        lines.append("default_website=%s" % website)
    if zoomlevel is not None:
        lines.append("default_zl=%s" % zoomlevel)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines) + "\n")


def _two_provider_codes(window):
    combo = window.imagery_combo
    codes = [combo.itemText(i) for i in range(combo.count())]
    assert len(codes) >= 2, "need at least two GUI providers for the test"
    return codes[0], codes[1]


def test_single_tile_config_drives_source_and_detail(window):
    code, _ = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=code, zoomlevel=17)
    window.map.set_selection({(48, -6)})
    assert window.imagery_combo.currentText() == code
    assert window.build_zl == 17


def test_agreeing_tiles_select_the_shared_value(window):
    code, _ = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=code, zoomlevel=18)
    _write_tile_cfg(window, 48, -5, website=code, zoomlevel=18)
    window.map.set_selection({(48, -6), (48, -5)})
    assert window.imagery_combo.currentText() == code
    assert window.build_zl == 18


def test_disagreeing_tiles_unresolve_and_block_build(window):
    first, second = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=first, zoomlevel=16)
    _write_tile_cfg(window, 48, -5, website=second, zoomlevel=17)
    window.map.set_selection({(48, -6), (48, -5)})
    assert window.imagery_combo.currentIndex() == -1
    # Disagreeing detail levels keep the Settings value (the Mac app's
    # one buildZL); only the imagery source can be unresolved.
    assert window.build_zl == 16

    window.start_build()  # must refuse: unresolved imagery combo
    assert window._building is False
    assert "disagree" in window.statusBar().currentMessage()


def test_unconfigured_tiles_leave_combos_alone(window):
    before_imagery = window.imagery_combo.currentText()
    before_zoomlevel = window.build_zl
    window.map.set_selection({(41, 12), (41, 13)})
    assert window.imagery_combo.currentText() == before_imagery
    assert window.build_zl == before_zoomlevel


def test_unconfigured_tile_does_not_dilute_agreement(window):
    _, code = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=code, zoomlevel=12)
    window.map.set_selection({(48, -6), (48, -5)})
    assert window.imagery_combo.currentText() == code
    assert window.build_zl == 12


def test_unknown_provider_code_unresolves_the_combo(window):
    _write_tile_cfg(window, 48, -6, website="NO_SUCH_PROVIDER", zoomlevel=16)
    window.map.set_selection({(48, -6)})
    assert window.imagery_combo.currentIndex() == -1
    assert window.build_zl == 16


def test_picking_a_value_resolves_the_block(window):
    first, second = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=first, zoomlevel=16)
    _write_tile_cfg(window, 48, -5, website=second, zoomlevel=17)
    window.map.set_selection({(48, -6), (48, -5)})
    assert window.imagery_combo.currentIndex() == -1

    # The user picks a source in the Build box: the "--" state clears and
    # the unresolved-combo guard in start_build no longer applies.
    window.imagery_combo.setCurrentText(first)
    assert window.imagery_combo.currentIndex() >= 0


def test_user_pick_survives_panel_refresh_on_same_selection(window):
    """Async panel refreshes (scan results streaming in, build
    bookkeeping) re-run the sync on an unchanged selection; they must
    not snap the combos back to the tiles' recorded provenance after
    the user deliberately picked different values."""
    first, second = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=first, zoomlevel=17)
    window.map.set_selection({(48, -6)})
    assert window.imagery_combo.currentText() == first

    window.imagery_combo.setCurrentText(second)
    window.build_zl = 16
    window._active_changed(window.map.active_tile())
    assert window.imagery_combo.currentText() == second
    assert window.build_zl == 16


def test_reselecting_tiles_resyncs_the_combos(window):
    first, second = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=first, zoomlevel=17)
    window.map.set_selection({(48, -6)})
    window.imagery_combo.setCurrentText(second)

    # A GENUINE selection change re-arms the sync: dropping and
    # re-taking the selection points the combos back at the config.
    window.map.set_selection(set())
    window.map.set_selection({(48, -6)})
    assert window.imagery_combo.currentText() == first
    assert window.build_zl == 17


def test_start_build_uses_the_user_picked_values(window, monkeypatch):
    """start_build must hand the engine the values showing in the
    Build box at click time — its own panel refresh used to reset the
    combos to the tiles' recorded provenance BEFORE they were read,
    silently rebuilding with the old imagery source."""
    first, second = _two_provider_codes(window)
    _write_tile_cfg(window, 48, -6, website=first, zoomlevel=17)
    window.map.set_selection({(48, -6)})
    assert window.imagery_combo.currentText() == first

    window.imagery_combo.setCurrentText(second)
    window.build_zl = 16

    calls = []

    def fake_enqueue_build(tiles, **kwargs):
        calls.append((list(tiles), kwargs))
        # "Not started": start_build unwinds its run bookkeeping, so the
        # window closes cleanly without a live build to stop.
        return False

    monkeypatch.setattr(window._session, "enqueue_build",
                        fake_enqueue_build)
    window.start_build()
    assert calls, "start_build never reached enqueue_build"
    kwargs = calls[0][1]
    assert kwargs["provider"] == second
    assert kwargs["zoomlevel"] == 16


def _fake_built_tile(window, lat, lon, texture_names):
    """A built tile with NO cfg: a DSF and textures named by the imagery
    writer, scanned the way the engine scans it."""
    import O4_File_Names as FNAMES
    import O4_Tile_Info as TINFO

    build_dir = os.path.join(window.output_dir(), "zOrtho4XP_" + FNAMES.short_latlon(lat, lon))
    dsf = os.path.join(build_dir, "Earth nav data", FNAMES.round_latlon(lat, lon),
                       FNAMES.short_latlon(lat, lon) + ".dsf")
    os.makedirs(os.path.dirname(dsf), exist_ok=True)
    open(dsf, "wb").close()
    os.makedirs(os.path.join(build_dir, "textures"), exist_ok=True)
    for name in texture_names:
        open(os.path.join(build_dir, "textures", name), "wb").close()
    info = TINFO._build_tile_info(build_dir, lat, lon, os.path.basename(build_dir))
    window._built[(lat, lon)] = info
    return info


def test_built_tile_without_cfg_adopts_its_detected_imagery(window):
    """#1334: a built tile with only _BI16.dds textures selects BI / 16."""
    window.imagery_combo.addItems(["BI"])
    info = _fake_built_tile(window, 47, 11, ["%d_8720_BI16.dds" % (5424 + 16 * i)
                                            for i in range(3)])
    assert (info.provider, info.detected_provider, info.detected_zl) == ("", "BI", 16)
    window.build_zl = 18
    window.map.set_selection({(47, 11)})
    assert window.imagery_combo.currentText() == "BI"
    assert window.build_zl == 16


def test_offline_detected_imagery_is_not_adopted(window):
    window.imagery_combo.addItems(["BI"])
    _fake_built_tile(window, 47, 12, ["5424_8720_BI16.dds"])
    window._imagery_status["BI"] = ("offline", "No answer within 5 seconds.")
    before = window.imagery_combo.currentText()
    window.map.set_selection({(47, 12)})
    assert window.imagery_combo.currentText() == before
