"""#2055: the Qt window's GUI thread is not repainted per streamed scan
batch.  The engine streams ScanBatch / ScanProgress at ~10 Hz; each one the
window published repainted the whole map (the airport layer alone ~100 ms
of Python on a large install), so a ~25 s launch scan kept the GUI thread
busy for most of it.  With a stub engine (no scan is ever sent), 25 s of
batches at 10 Hz reach the map about once a second; the active tile's own
result and a new phase still show at once; ScanDone publishes the truth.
The rule is ``O4_Scan_Stream_Throttle`` (Mac twin: ``ScanStreamThrottle``).
"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch, capsys):
    import O4_Config_Utils as CFG
    import O4_Qt_GUI as GUI
    import O4_UI_Utils as UI

    monkeypatch.setattr(GUI, "PREFS_FILE", str(tmp_path / "prefs.json"))
    monkeypatch.setattr(GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    monkeypatch.setattr(CFG, "custom_scenery_dir", "")
    with capsys.disabled():
        original_stdout = sys.stdout
        built = GUI.MainWindow()
        sys.stdout = original_stdout
    built._session.scan = lambda *args, **kwargs: None   # the stub engine
    clock = types.SimpleNamespace(now=1000.0)
    monkeypatch.setattr(GUI, "time", types.SimpleNamespace(
        monotonic=lambda: clock.now))
    built._clock = clock
    yield built
    built.deleteLater()
    UI.engine_session = None


def _count(monkeypatch, obj, name):
    calls = []
    real = getattr(obj, name)
    monkeypatch.setattr(obj, name, lambda *a, **k: (calls.append(a), real(*a, **k))[1])
    return calls


def test_a_25_s_launch_scan_repaints_the_map_about_once_a_second(window, monkeypatch):
    import o4_engine.events as EV

    window.refresh_tiles()
    built_calls = _count(monkeypatch, window.map, "set_built")
    status_calls = _count(monkeypatch, window.map, "set_scan_status")
    for step in range(250):                       # 25 s at the engine's 10 Hz
        window._clock.now = 1000.0 + step / 10
        window._on_scan_progress(EV.ScanProgress(
            phase="Reading installed scenery…", done=step, total=250))
        window._on_scan_batch(EV.ScanBatch(installed=[(10 + step // 100, step % 100)]))
    assert 24 <= len(built_calls) <= 26, len(built_calls)
    assert 24 <= len(status_calls) <= 26, len(status_calls)
    # A new phase shows at once.
    window._on_scan_progress(EV.ScanProgress(phase="Reading the World pack…", done=0, total=0))
    assert status_calls[-1][0] == "Reading the World pack…"
    # Nothing streamed is lost: ScanDone publishes every tile.
    window._on_scan_done(EV.ScanDone())
    assert len(window._installed) == 250


def _tile_info(lat, lon):
    import inspect

    import O4_Tile_Info as TINFO
    required = {"lat": lat, "lon": lon, "build_dir": "/nonexistent",
                "dir_name": "zOrtho4XP_%+03d%+04d" % (lat, lon), "dsf_present": True}
    signature = inspect.signature(TINFO.TileInfo)
    return TINFO.TileInfo(**{name: required.get(name)
                             for name, parameter in signature.parameters.items()
                             if parameter.default is inspect.Parameter.empty})


def test_the_active_tiles_own_result_shows_at_once(window, monkeypatch):
    import o4_engine.events as EV

    window.refresh_tiles()
    window._on_scan_batch(EV.ScanBatch(installed=[(1, 1)]))      # publishes
    window.map.set_active(36, -87)
    changed = _count(monkeypatch, window, "_active_changed")
    window._clock.now += 0.1
    window._on_scan_batch(EV.ScanBatch(installed=[(2, 2)]))      # held back
    assert changed == [] and (2, 2) not in window._installed
    window._clock.now += 0.1
    window._on_scan_batch(EV.ScanBatch(built={(36, -87): _tile_info(36, -87)}))
    assert changed and (36, -87) in window._built and (2, 2) in window._installed
