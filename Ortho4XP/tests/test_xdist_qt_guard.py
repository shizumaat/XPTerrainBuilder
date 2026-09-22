"""Twins for the Qt-under-xdist refusal armed in ``tests/conftest.py``.

The property under test: ``tests/test_qt_*.py`` collected into a PARALLEL
run refuse LOUDLY instead of hanging the controller (issue #35 item 4).
CI already splits them (``-n0`` in its own step); this is what happens when
a human does not.

Deliberately NOT named ``test_qt_*.py`` — a file with that prefix would
arm the guard against itself.
"""

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from conftest import (_is_qt_item, _refuse_qt_under_xdist, _xdist_role,
                      _QT_XDIST_SKIP)

ORTHO4XP = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# The arming decision, against fake items (no subprocess, no Qt)
# ---------------------------------------------------------------------------
class FakeItem:
    """The three attributes the guard touches on a collected item."""

    def __init__(self, filename: str):
        self.path = Path("tests") / filename
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker)

    @property
    def marker_names(self):
        return [m.name for m in self.markers]


def _worker_config():
    cfg = types.SimpleNamespace(option=types.SimpleNamespace(numprocesses=0))
    cfg.workerinput = {"workerid": "gw0"}
    return cfg


def _controller_config(numprocesses):
    return types.SimpleNamespace(
        option=types.SimpleNamespace(numprocesses=numprocesses))


def _items():
    return [FakeItem("test_qt_about.py"), FakeItem("test_qt_console.py"),
            FakeItem("test_harness.py")]


def test_is_qt_item_keys_on_the_file_prefix():
    assert _is_qt_item(FakeItem("test_qt_about.py"))
    assert not _is_qt_item(FakeItem("test_harness.py"))
    # the twin file itself must never arm the guard against itself
    assert not _is_qt_item(FakeItem("test_xdist_qt_guard.py"))


@pytest.mark.parametrize("config,expected_role", [
    (_controller_config(0), None),        # -n0
    (_controller_config(None), None),     # xdist not installed / no -n
    (_controller_config(4), "the xdist controller"),
    (_controller_config("auto"), "the xdist controller"),  # unresolved
])
def test_xdist_role_reads_serial_and_parallel_runs(config, expected_role):
    assert _xdist_role(config) == expected_role


def test_xdist_role_names_the_worker(monkeypatch):
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    assert _xdist_role(_worker_config()) == "gw3"


def test_a_serial_run_arms_nothing(monkeypatch):
    monkeypatch.delenv("O4_ALLOW_QT_XDIST", raising=False)
    items = _items()
    _refuse_qt_under_xdist(_controller_config(0), items)
    assert [i.marker_names for i in items] == [[], [], []]


@pytest.mark.parametrize("config", [_worker_config(), _controller_config(4)])
def test_a_parallel_run_arms_one_refusal_and_skips_its_siblings(
        config, monkeypatch):
    monkeypatch.delenv("O4_ALLOW_QT_XDIST", raising=False)
    items = _items()
    _refuse_qt_under_xdist(config, items)

    # ONE item carries the refusal: 300 identical failures are not a report.
    assert items[0].marker_names == ["qt_xdist_refusal"]
    message = items[0].markers[0].args[0]
    assert "REFUSED" in message
    assert "-n0 tests/test_qt_*.py" in message
    assert "--ignore-glob='tests/test_qt_*.py'" in message
    assert "test_qt_about.py, test_qt_console.py" in message

    assert items[1].marker_names == ["skip"]
    assert items[1].markers[0].kwargs["reason"] == _QT_XDIST_SKIP

    # the non-Qt item is untouched — the rest of the suite still runs parallel
    assert items[2].marker_names == []


def test_a_parallel_run_without_qt_files_is_untouched(monkeypatch):
    monkeypatch.delenv("O4_ALLOW_QT_XDIST", raising=False)
    items = [FakeItem("test_harness.py"), FakeItem("test_engine_jsonl.py")]
    _refuse_qt_under_xdist(_worker_config(), items)
    assert [i.marker_names for i in items] == [[], []]


def test_the_override_disarms_the_guard(monkeypatch):
    monkeypatch.setenv("O4_ALLOW_QT_XDIST", "1")
    items = _items()
    _refuse_qt_under_xdist(_worker_config(), items)
    assert [i.marker_names for i in items] == [[], [], []]


# ---------------------------------------------------------------------------
# End to end: a real pytest, a real xdist controller, a real Qt file
# ---------------------------------------------------------------------------
def _pytest_run(*args, timeout=300):
    """A child pytest under this interpreter, from ``Ortho4XP/``.

    ``PYTEST_*`` is scrubbed so the child is not mistaken for a worker of
    the parent run; the Qt platform is forced offscreen (no display on any
    CI runner).
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MPLBACKEND"] = "Agg"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header",
         "-p", "no:cacheprovider", *args],
        cwd=str(ORTHO4XP), env=env, capture_output=True, text=True,
        timeout=timeout)


def test_a_parallel_qt_run_refuses_fast_instead_of_hanging():
    """The whole chain: marker registered, worker detected, message read.

    ``timeout=`` is the assertion that matters as much as the exit code —
    a hang is the failure mode this guard exists to replace.
    """
    pytest.importorskip("PySide6")
    run = _pytest_run("-n2", "tests/test_qt_about.py", timeout=120)

    assert run.returncode != 0, run.stdout
    assert "REFUSED" in run.stdout, run.stdout
    assert "pytest -n0 tests/test_qt_*.py" in run.stdout, run.stdout
    assert "--ignore-glob='tests/test_qt_*.py'" in run.stdout, run.stdout


def test_a_serial_qt_run_is_not_refused():
    """The guard must not cost the split run CI actually uses."""
    pytest.importorskip("PySide6")
    run = _pytest_run("-n0", "--collect-only", "tests/test_qt_about.py",
                      timeout=120)

    assert run.returncode == 0, run.stdout + run.stderr
    assert "REFUSED" not in run.stdout, run.stdout
