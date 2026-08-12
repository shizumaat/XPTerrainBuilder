"""Headless tests for the Qt UI's second parity round — the optimistic
launch overlay, honest run estimates, and mixed-imagery-source badges
(docs/specs/qt-backlog-parity2-spec.md §QB1-QB3).

Offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no engine: the
window is driven through its engine-event handlers, which is the seam
the other Qt tests use.  Both stores are monkeypatched BEFORE the window
is constructed — it loads prefs and the scan cache in ``__init__`` and
writes them on close, so an unisolated window clobbers the user's real
``.qt_prefs.json`` and ``.tile_scan_cache.json``.
"""

import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Tile_Info as TINFO  # noqa: E402
from o4_engine import events as EV  # noqa: E402


TILE = (48, -6)
OTHER = (49, -6)


def _tile_info(lat, lon, build_dir, provider="BI", zl=16):
    return TINFO.TileInfo(
        lat=lat, lon=lon, build_dir=build_dir,
        dir_name=os.path.basename(build_dir), dsf_present=True,
        provider=provider, zl=zl)


# ===========================================================================
# QB1 — the scan cache (pure)
# ===========================================================================
def test_scan_cache_round_trip(tmp_path):
    built = {TILE: _tile_info(*TILE, build_dir="/w/zOrtho4XP_+48-006")}
    path = str(tmp_path / "cache.json")
    GUI.save_scan_cache(built, {TILE, OTHER}, "/w", "/cs", path=path)
    restored = GUI.load_scan_cache("/w", "/cs", path=path)
    assert restored is not None
    (restored_built, restored_installed) = restored
    assert restored_installed == {TILE, OTHER}
    assert set(restored_built) == {TILE}
    info = restored_built[TILE]
    assert (info.provider, info.zl, info.build_dir) == (
        "BI", 16, "/w/zOrtho4XP_+48-006")


def test_scan_cache_is_keyed_by_both_folders(tmp_path):
    """A snapshot describes ONE (working dir, Custom Scenery dir) pair."""
    path = str(tmp_path / "cache.json")
    GUI.save_scan_cache(
        {TILE: _tile_info(*TILE, build_dir="/w/t")}, {TILE},
        "/w", "/cs", path=path)
    assert GUI.load_scan_cache("/w", "/cs", path=path) is not None
    assert GUI.load_scan_cache("/other", "/cs", path=path) is None
    assert GUI.load_scan_cache("/w", "/other", path=path) is None


def test_scan_cache_version_bump_drops_the_snapshot(tmp_path):
    path = str(tmp_path / "cache.json")
    GUI.save_scan_cache(
        {TILE: _tile_info(*TILE, build_dir="/w/t")}, set(),
        "/w", "/cs", path=path)
    with open(path, "r") as handle:
        payload = json.load(handle)
    payload["version"] = GUI.TILE_SCAN_CACHE_VERSION + 1
    assert GUI.scan_cache_restore(payload, "/w", "/cs") is None


def test_scan_cache_drops_malformed_entries_silently():
    payload = {
        "version": GUI.TILE_SCAN_CACHE_VERSION,
        "working_dir": "/w",
        "custom_scenery_dir": "/cs",
        "built": [
            "not a dict",
            {"lat": 48},                       # missing required fields
            {"lat": 48, "lon": -6, "build_dir": "/w/t", "dir_name": "t",
             "dsf_present": True, "provider": "BI", "zl": 16,
             "gone_in_a_later_schema": 1},     # unknown key: ignored
        ],
        "installed": [[48, -6], "nonsense", [1]],
    }
    restored = GUI.scan_cache_restore(payload, "/w", "/cs")
    assert restored is not None
    (built, installed) = restored
    assert set(built) == {TILE}
    assert installed == {TILE}


def test_scan_cache_normalizes_the_provider():
    """The mac app's v3 lesson: a legacy cfg's quoted ``'Arc'`` cached
    verbatim matches no provider, so every texture reads as foreign."""
    built = {TILE: _tile_info(*TILE, build_dir="/w/t", provider="'Arc'")}
    payload = GUI.scan_cache_payload(built, set(), "/w", "/cs")
    assert payload["built"][0]["provider"] == "Arc"
    (restored, _installed) = GUI.scan_cache_restore(payload, "/w", "/cs")
    assert restored[TILE].provider == "Arc"


def test_scan_cache_absent_file_is_not_an_error(tmp_path):
    assert GUI.load_scan_cache(
        "/w", "/cs", path=str(tmp_path / "nothing.json")) is None


# ===========================================================================
# QB2 — the climbing-estimate detector (pure)
# ===========================================================================
def test_eta_needs_a_baseline_before_judging():
    """Nothing is unreliable until a sample is 30 s old — every estimate
    wobbles in its first seconds."""
    (samples, unreliable) = GUI.eta_credibility([], 0.0, 100.0)
    assert (samples, unreliable) == ([(0.0, 100.0)], False)
    (samples, unreliable) = GUI.eta_credibility(samples, 20.0, 400.0)
    assert unreliable is False


def test_eta_climbing_past_the_tolerance_is_unreliable():
    (samples, _u) = GUI.eta_credibility([], 0.0, 100.0)
    (samples, unreliable) = GUI.eta_credibility(samples, 30.0, 105.0)
    assert unreliable is False, "exactly the tolerance is still credible"
    (_samples, unreliable) = GUI.eta_credibility(samples, 31.0, 105.1)
    assert unreliable is True


def test_eta_falling_estimate_stays_credible():
    samples = []
    for elapsed in (0.0, 10.0, 20.0, 31.0, 42.0):
        (samples, unreliable) = GUI.eta_credibility(
            samples, elapsed, 200.0 - elapsed)
        assert unreliable is False


def test_eta_window_forgets_samples_older_than_45_s():
    (samples, _u) = GUI.eta_credibility([], 0.0, 100.0)
    (samples, unreliable) = GUI.eta_credibility(samples, 46.0, 900.0)
    assert samples == [(46.0, 900.0)], "the 46 s-old sample is gone"
    assert unreliable is False, "and with it the only possible baseline"


def test_eta_absent_estimate_clears_window_and_flag():
    (samples, _u) = GUI.eta_credibility([], 0.0, 100.0)
    (samples, unreliable) = GUI.eta_credibility(samples, 31.0, 200.0)
    assert unreliable is True
    (samples, unreliable) = GUI.eta_credibility(samples, 32.0, None)
    assert (samples, unreliable) == ([], False)


def test_eta_constants_are_the_specified_ones():
    assert GUI.ETA_SAMPLE_WINDOW_SECONDS == 45.0
    assert GUI.ETA_BASELINE_AGE_SECONDS == 30.0
    assert GUI.ETA_CLIMB_TOLERANCE_SECONDS == 5.0


# ===========================================================================
# QB3 — the foreign-source audit predicate (pure)
# ===========================================================================
@pytest.mark.parametrize("name,expected", [
    ("22528_38912_BI16.dds", "BI"),
    ("22528_38912_USA_216.dds", "USA_2"),      # provider ending in a digit
    ("22528_38912_Arc17_mask.dds", "Arc"),
    ("22528_38912_BI16.DDS", "BI"),            # case-insensitive extension
    ("22528_38912_BI16.png", None),            # not a texture
    ("textures.txt", None),
    ("", None),
    (None, None),
])
def test_texture_provider(name, expected):
    assert QTMAP.texture_provider(name) == expected


def test_has_foreign_sources(tmp_path):
    textures = tmp_path / "textures"
    textures.mkdir()
    for name in ("22528_38912_BI16.dds", "22528_38912_BI17.dds",
                 "22528_38912_BI16_mask.dds", "notes.txt"):
        (textures / name).write_text("")
    # Zones legitimately mix ZOOM LEVELS — only the provider decides.
    assert QTMAP.has_foreign_sources(str(textures), "BI") is False
    assert QTMAP.has_foreign_sources(str(textures), "bi") is False
    (textures / "22528_38912_Arc16.dds").write_text("")
    assert QTMAP.has_foreign_sources(str(textures), "BI") is True


def test_has_foreign_sources_needs_a_current_provider(tmp_path):
    textures = tmp_path / "textures"
    textures.mkdir()
    (textures / "22528_38912_Arc16.dds").write_text("")
    assert QTMAP.has_foreign_sources(str(textures), "") is False
    assert QTMAP.has_foreign_sources(str(tmp_path / "gone"), "BI") is False


# ===========================================================================
# The window: cache round-trip and badge plumbing
# ===========================================================================
@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def scenery_dir():
    """The Custom Scenery folder the window will key its cache against —
    read from the same place the window reads it."""
    import O4_Config_Utils as CFG
    return CFG.custom_scenery_dir


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch):
    """A MainWindow against isolated prefs and scan-cache files, with its
    working dir pointed at ``tmp_path`` from the start (the cache load
    runs in ``__init__``, before a test could set it)."""
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w") as handle:
        # An EXISTING prefs file: an absent one arms the onboarding
        # wizard, whose modal exec would sit there forever headless.
        json.dump({"output_dir": str(tmp_path)}, handle)
    cache_path = str(tmp_path / "tile-scan.json")
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(GUI, "TILE_SCAN_CACHE_FILE", cache_path)
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    windows = []

    def _make():
        win = GUI.MainWindow()
        monkeypatch.setattr(win, "refresh_tiles", lambda: None)
        windows.append(win)
        return win

    _make.cache_path = cache_path
    try:
        yield _make
    finally:
        for win in windows:
            win._building = False
            win.close()
            win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def _wait_for(qapp, predicate, seconds=5.0):
    """Pump the event loop until a worker sweep's signal has landed."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_scan_done_writes_the_cache_and_next_launch_paints_it(
        qapp, tmp_path, make_window, scenery_dir):
    build_dir = tmp_path / "zOrtho4XP_+48-006"
    build_dir.mkdir()
    first = make_window()
    first._scan_dirs = (first.working_dir(), scenery_dir)
    first._on_scan_batch(EV.ScanBatch(
        built={TILE: _tile_info(*TILE, build_dir=str(build_dir))},
        installed=(TILE,)))
    first._on_scan_done(EV.ScanDone(built_count=1, installed_count=1))
    assert os.path.isfile(make_window.cache_path)

    # A second launch has the squares before any engine has booted.
    second = make_window()
    assert set(second._built) == {TILE}
    assert second._built[TILE].provider == "BI"
    assert second._installed == {TILE}
    assert set(second.map._built) == {TILE}


def test_cache_from_another_working_dir_is_not_adopted(
        qapp, tmp_path, make_window, scenery_dir):
    GUI.save_scan_cache(
        {TILE: _tile_info(*TILE, build_dir="/elsewhere/t")}, {TILE},
        "/a/different/working/dir", scenery_dir,
        path=make_window.cache_path)
    window = make_window()
    assert window._built == {}
    assert window._installed == set()


def test_cached_state_never_overwrites_a_live_overlay(
        qapp, tmp_path, make_window, scenery_dir):
    window = make_window()
    live = {OTHER: _tile_info(*OTHER, build_dir="/w/live")}
    window._built = dict(live)
    GUI.save_scan_cache(
        {TILE: _tile_info(*TILE, build_dir="/w/cached")}, {TILE},
        window.working_dir(), scenery_dir, path=make_window.cache_path)
    window._load_cached_tile_states()
    assert set(window._built) == {OTHER}


def test_conflict_sweep_reaches_the_map_and_the_info_panel(
        qapp, tmp_path, make_window):
    build_dir = tmp_path / "zOrtho4XP_+48-006"
    (build_dir / "textures").mkdir(parents=True)
    for name in ("22528_38912_BI16.dds", "22528_38912_Arc16.dds"):
        (build_dir / "textures" / name).write_text("")
    window = make_window()
    window._built = {TILE: _tile_info(*TILE, build_dir=str(build_dir))}
    window._refresh_conflict_tiles()
    assert _wait_for(qapp, lambda: window._conflict_tiles == {TILE})
    assert window.map._conflicts == {TILE}
    window._refresh_conflict_indicator(TILE)
    assert "mixed" in window.info_provider.text()

    # The foreign textures go away: the badge clears without a rescan.
    os.remove(str(build_dir / "textures" / "22528_38912_Arc16.dds"))
    window._reaudit_conflict(TILE)
    assert _wait_for(qapp, lambda: window._conflict_tiles == set())
    assert window.map._conflicts == set()
    window._refresh_conflict_indicator(TILE)
    assert window.info_provider.text() == "BI"


def test_a_superseded_sweep_is_discarded(qapp, make_window):
    window = make_window()
    window._conflict_generation = 7
    window._on_conflicts_ready((6, {TILE}))
    assert window._conflict_tiles == set()
    window._on_conflicts_ready((7, {TILE}))
    assert window._conflict_tiles == {TILE}


def test_climbing_estimate_replaces_the_number_in_the_run_clock(
        qapp, make_window):
    window = make_window()
    window._build_t0 = time.time()
    window._on_run_eta(EV.RunEta(elapsed_seconds=0.0, remaining_seconds=100.0))
    window._update_build_clock()
    assert "≈" in window.eta_label.text()
    window._on_run_eta(
        EV.RunEta(elapsed_seconds=31.0, remaining_seconds=300.0))
    window._update_build_clock()
    assert window.eta_label.text() == "Total remaining: still estimating…"
    # No estimate at all is a dash, never a wild number.
    window._on_run_eta(
        EV.RunEta(elapsed_seconds=32.0, remaining_seconds=None))
    window._update_build_clock()
    assert window.eta_label.text() == "Total remaining —"
