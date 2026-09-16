"""These tests pin the loud-warning contract for the silent CIFP-missing
auto_patch skip: when ``auto_patch`` is enabled but no CIFP path resolves,
``run_auto_patch_generation`` still skips generation (behavior unchanged)
but must now say so loudly on stdout and, when an engine session is
attached, as a warning-level Log event.  Headless: no network and no
X-Plane install required.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402


class _Recorder:
    """Stand-in for AUTOPATCH.generate_auto_patches."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def _stub_generate(monkeypatch):
    """Keep the log file untouched and record generation calls."""
    monkeypatch.setattr(UI, "log", False)
    recorder = _Recorder()
    monkeypatch.setattr(VMAP.AUTOPATCH, "generate_auto_patches", recorder)
    return recorder


def _no_cifp(monkeypatch):
    monkeypatch.setattr(VMAP.CFG, "cifp_data_path", "")
    monkeypatch.setattr(VMAP.CFG, "custom_scenery_dir", "")


def test_warns_when_cifp_missing(monkeypatch, capsys):
    recorder = _stub_generate(monkeypatch)
    _no_cifp(monkeypatch)
    tile = types.SimpleNamespace(auto_patch="All")

    VMAP.run_auto_patch_generation(tile, None, {})

    assert recorder.calls == []
    out = capsys.readouterr().out
    assert "cifp_data_path" in out
    assert "NO AIRPORTS WILL BE GRADED" in out


@pytest.mark.parametrize("auto_patch", ["None", False])
def test_silent_when_auto_patch_off(monkeypatch, capsys, auto_patch):
    recorder = _stub_generate(monkeypatch)
    _no_cifp(monkeypatch)
    tile = types.SimpleNamespace(auto_patch=auto_patch)

    VMAP.run_auto_patch_generation(tile, None, {})

    assert recorder.calls == []
    assert "WARNING" not in capsys.readouterr().out


def test_no_warning_when_cifp_present(monkeypatch, capsys, tmp_path):
    recorder = _stub_generate(monkeypatch)
    monkeypatch.setattr(VMAP.CFG, "cifp_data_path", str(tmp_path))
    tile = types.SimpleNamespace(auto_patch="All")

    VMAP.run_auto_patch_generation(tile, None, {})

    assert len(recorder.calls) == 1
    assert "WARNING" not in capsys.readouterr().out


def test_engine_session_gets_warning_event(monkeypatch):
    _stub_generate(monkeypatch)
    _no_cifp(monkeypatch)

    class _Session:
        def __init__(self):
            self.warnings = []

        def log_warning(self, text):
            self.warnings.append(text)

    session = _Session()
    monkeypatch.setattr(UI, "engine_session", session)
    tile = types.SimpleNamespace(auto_patch="All")

    VMAP.run_auto_patch_generation(tile, None, {})

    assert len(session.warnings) == 1
    assert "cifp_data_path" in session.warnings[0]
    assert "NO AIRPORTS WILL BE GRADED" in session.warnings[0]
