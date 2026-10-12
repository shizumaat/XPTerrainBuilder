"""A refused ACTIVATION ends the tile as a named failure (issue #585).

The imagery step's last move — ``<dsf>.tmp`` onto ``<dsf>`` — printed
"tile is not active" and the step still returned success: the session
reported a BUILT tile that X-Plane would not load.  These twins inject the
refusal (``PermissionError``, ``FileNotFoundError``, a full disk) and pin:

* the step returns 0 and the tile's ``BuildDone`` names the cause with the
  catalogue's copy (``O4_Tile_Failures.code_for_activation``);
* the state left behind, and that the next build repairs it unaided;
* a Stop inside the encoder never activates its truncated file;
* the overlay's install is staged, so a refusal keeps the previous overlay.

Headless: stub tiles, ``tmp_path`` build directories, no network.
"""

import errno
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_DSF_Utils as DSF  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Imagery_Utils as IMG  # noqa: E402
import O4_Overlay_Utils as OVL  # noqa: E402
import O4_Tile_Failures as FAIL  # noqa: E402
import O4_Tile_Utils as TILE  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402

from test_engine_session import (  # noqa: E402
    _tile_events, install_stub_pipeline, run_build)

REFUSALS = [
    (PermissionError(errno.EACCES, "Access is denied"), "scenery_file_locked"),
    (FileNotFoundError(errno.ENOENT, "No such file"),
     "scenery_file_not_activated"),
    (OSError(errno.ENOSPC, "No space left on device"), "disk_full"),
]
REAL_REPLACE = os.replace


@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.engine_session = None
    UI.red_flag = False
    UI.is_working = False


class _Recorder:
    """Stands in for the engine session: keeps what a step names."""

    def __init__(self):
        self.named = []

    def tile_failure(self, code, detail="", exc=None, **params):
        if exc is not None:
            code = FAIL.code_for_exception(exc, default=code)
        self.named.append(code)

    def __getattr__(self, name):          # every other UI hook: a no-op
        return lambda *args, **kwargs: None


def _refuse_replace(monkeypatch, error, suffix=".dsf.tmp"):
    """``os.replace`` refuses the move of ``*<suffix>``; others are real."""
    def replace(source, destination):
        if str(source).endswith(suffix):
            raise error
        return REAL_REPLACE(source, destination)

    monkeypatch.setattr(TILE.os, "replace", replace)


def _dsf_path(build_dir, lat=60, lon=5):
    return os.path.join(build_dir, "Earth nav data",
                        FNAMES.long_latlon(lat, lon) + ".dsf")


def _write(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------
def test_a_refused_activation_has_its_own_copy():
    for error, code in REFUSALS:
        assert FAIL.code_for_activation(error) == code
    held = OSError("The process cannot access the file")
    held.winerror = 32
    assert FAIL.code_for_activation(held) == "scenery_file_locked"
    assert FAIL.code_for_activation(OSError("?")) == (
        "scenery_file_not_activated")
    locked = FAIL.CATALOGUE["scenery_file_locked"]
    assert locked.remedy == "quit_xplane"
    assert FAIL.REMEDIES["quit_xplane"].startswith(
        "Quit X-Plane if it is running, then build the tile again.")
    assert FAIL.CATALOGUE["scenery_file_not_activated"].remedy == "retry"
    assert locked.what == FAIL.CATALOGUE["scenery_file_not_activated"].what


# ---------------------------------------------------------------------------
# The move itself
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("error, code", REFUSALS,
                         ids=[code for _error, code in REFUSALS])
def test_a_refused_move_is_named_and_leaves_a_repairable_state(
        tmp_path, monkeypatch, error, code):
    dsf = _dsf_path(str(tmp_path))
    _write(dsf + ".bak", b"previous")       # build_dsf moved it aside
    _write(dsf + ".tmp", b"finished")
    UI.engine_session = recorder = _Recorder()
    _refuse_replace(monkeypatch, error)

    assert TILE.activate_dsf(dsf) is False

    assert recorder.named == [code]
    # no scenery file: X-Plane flies default scenery on the tile
    assert not os.path.exists(dsf)
    assert _read(dsf + ".tmp") == b"finished"
    assert _read(dsf + ".bak") == b"previous"


def test_a_move_that_works_activates(tmp_path):
    dsf = _dsf_path(str(tmp_path))
    _write(dsf + ".tmp", b"finished")
    UI.engine_session = recorder = _Recorder()

    assert TILE.activate_dsf(dsf) is True

    assert recorder.named == []
    assert _read(dsf) == b"finished"
    assert not os.path.exists(dsf + ".tmp")


# ---------------------------------------------------------------------------
# The imagery step
# ---------------------------------------------------------------------------
class _StubTile:
    """Just enough of ``O4_Config_Utils.Tile`` for ``build_tile`` in the
    default-X-Plane texture mode (no imagery threads)."""

    lat, lon = 60, 5
    grouped = False
    texture_mode = "default_xplane"

    def __init__(self, build_dir):
        self.build_dir = build_dir
        self.default_website = next(iter(IMG.providers_dict), "stub")

    def write_to_config(self):
        pass


def _stub_step(tmp_path, monkeypatch, encoder):
    """A tile whose ``build_dsf`` is ``encoder(dsf_path)``."""
    build_dir = str(tmp_path / "tile")
    os.makedirs(build_dir)
    with open(FNAMES.mesh_file(build_dir, 60, 5), "w", encoding="utf-8",
              newline="") as handle:
        handle.write("stub mesh\n")
    tile = _StubTile(build_dir)
    monkeypatch.setitem(IMG.providers_dict, tile.default_website, {})
    monkeypatch.setattr(IMG, "initialize_local_combined_providers_dict",
                        lambda tile: True)
    monkeypatch.setattr(TILE, "_refuse_on_broken_proj", lambda: False)
    monkeypatch.setattr(TILE, "_write_imagery_manifest",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(TILE, "warn_if_imagery_incomplete", lambda tile: None)
    monkeypatch.setattr(UI, "is_working", False)
    monkeypatch.setattr(UI, "cleaning_level", 0)
    monkeypatch.setattr(
        DSF, "build_dsf", lambda tile, queue: encoder(_dsf_path(build_dir)))
    return tile


def _encode(dsf):
    """What ``build_dsf`` leaves: the previous file aside, a whole .tmp."""
    if os.path.exists(dsf):
        REAL_REPLACE(dsf, dsf + ".bak")
    _write(dsf + ".tmp", b"finished")
    return 1


def test_the_step_fails_then_the_next_build_repairs_it(tmp_path,
                                                       monkeypatch):
    tile = _stub_step(tmp_path, monkeypatch, _encode)
    dsf = _dsf_path(tile.build_dir)
    _write(dsf, b"previous")
    UI.engine_session = recorder = _Recorder()

    with monkeypatch.context() as refusing:
        _refuse_replace(refusing, REFUSALS[0][0])
        assert TILE.build_tile(tile) == 0          # was 1: "built"
    assert recorder.named == ["scenery_file_locked"]
    assert not os.path.exists(dsf)
    assert UI.is_working is False

    # the next build, nothing done by hand in between
    assert TILE.build_tile(tile) == 1
    assert _read(dsf) == b"finished"
    assert not os.path.exists(dsf + ".tmp")
    assert recorder.named == ["scenery_file_locked"]


def test_a_stop_inside_the_encoder_activates_nothing(tmp_path, monkeypatch):
    def stopped(dsf):
        REAL_REPLACE(dsf, dsf + ".bak")
        _write(dsf + ".tmp", b"trunc")
        UI.red_flag = True
        return 0

    tile = _stub_step(tmp_path, monkeypatch, stopped)
    dsf = _dsf_path(tile.build_dir)
    _write(dsf, b"previous")
    UI.engine_session = recorder = _Recorder()

    assert TILE.build_tile(tile) == 0

    assert recorder.named == []                    # a cancel names nothing
    assert not os.path.exists(dsf)                 # NOT the truncated file
    assert _read(dsf + ".bak") == b"previous"


def test_a_refused_move_aside_is_the_same_failure(tmp_path, monkeypatch):
    """``build_dsf`` moves the previous file to ``.bak`` first — where a
    running X-Plane's hold is met — and marks the refusal; the step's guard
    then names it by that mark, not by the exception's class."""
    def refused(dsf):
        error = PermissionError(errno.EACCES, "Access is denied")
        error.failure_code = FAIL.code_for_activation(error)
        raise error

    tile = _stub_step(tmp_path, monkeypatch, refused)
    dsf = _dsf_path(tile.build_dir)
    _write(dsf, b"previous")
    UI.engine_session = recorder = _Recorder()

    assert TILE.build_tile(tile) == 0

    assert recorder.named == ["scenery_file_locked"]
    assert _read(dsf) == b"previous"               # untouched, still active


# ---------------------------------------------------------------------------
# The wire
# ---------------------------------------------------------------------------
def test_the_tile_is_reported_not_built_with_the_remedy(monkeypatch,
                                                        tmp_path):
    dsf = _dsf_path(str(tmp_path / "pack"), 10, 20)
    _write(dsf + ".tmp", b"finished")

    def imagery(tile):
        if tile.lat != 10:
            return 1
        return 1 if TILE.activate_dsf(dsf) else 0

    install_stub_pipeline(monkeypatch, results={"imagery": imagery})
    _refuse_replace(monkeypatch, REFUSALS[0][0])
    events = run_build(EngineSession(), [(10, 20), (11, 21)], tmp_path)

    def done(lat, lon):
        return [e for e in _tile_events(events, lat, lon)
                if isinstance(e, EV.BuildDone)][0]

    assert done(10, 20).ok is False
    (failure,) = done(10, 20).failures
    assert failure["code"] == "scenery_file_locked"
    assert failure["what"] == ("Tile +10+020 was not built: its new scenery "
                               "file could not be put in place.")
    assert failure["why"] == "The file it replaces is in use or protected."
    assert failure["remedy"].startswith("Quit X-Plane if it is running")
    assert "Access is denied" not in done(10, 20).error
    assert done(11, 21).ok is True                 # the run goes on
    run_done = [e for e in events if isinstance(e, EV.RunDone)][-1]
    assert (run_done.done_count, run_done.error_count,
            run_done.cancelled) == (1, 1, False)


# ---------------------------------------------------------------------------
# The overlay's install
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("error, code", REFUSALS[::2],
                         ids=[code for _error, code in REFUSALS[::2]])
def test_a_refused_overlay_install_keeps_the_previous_overlay(
        tmp_path, monkeypatch, error, code):
    converted = str(tmp_path / "tmp" / "converted.dsf")
    destination = str(tmp_path / "overlays" / "+60+005.dsf")
    _write(converted, b"new overlay")
    _write(destination, b"previous overlay")
    UI.engine_session = recorder = _Recorder()
    _refuse_replace(monkeypatch, error)

    assert OVL.install_overlay_dsf(converted, destination) is False

    assert recorder.named == [code]
    assert _read(destination) == b"previous overlay"
    assert not os.path.exists(destination + ".tmp")


def test_an_overlay_the_converter_did_not_write_names_the_converter(
        tmp_path):
    UI.engine_session = recorder = _Recorder()
    destination = str(tmp_path / "+60+005.dsf")

    assert OVL.install_overlay_dsf(str(tmp_path / "absent.dsf"),
                                   destination) is False

    assert recorder.named == ["overlay_tool_failed"]
    assert not os.path.exists(destination)


def test_an_overlay_install_that_works(tmp_path):
    converted = str(tmp_path / "converted.dsf")
    destination = str(tmp_path / "+60+005.dsf")
    _write(converted, b"new overlay")
    UI.engine_session = recorder = _Recorder()

    assert OVL.install_overlay_dsf(converted, destination) is True

    assert recorder.named == []
    assert _read(destination) == b"new overlay"
    assert not os.path.exists(destination + ".tmp")
