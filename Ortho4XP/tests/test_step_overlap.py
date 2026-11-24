"""O4_Step_Overlap: a side task beside a step, on a machine slot of its
own, and the mesh step's hairline pre-flight beside Triangle4XP (#1264)."""
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Mesh_Utils as MESH  # noqa: E402
import O4_Step_Overlap as OVERLAP  # noqa: E402


class _Held:
    def __init__(self, count):
        self.count = count
        self.released = 0

    def release(self):
        self.released += 1


def test_beside_runs_the_task_on_a_slot_and_gives_it_back(monkeypatch):
    held = _Held(1)
    monkeypatch.setattr(OVERLAP.MACHINE_SLOTS, "try_take",
                        lambda n, **kw: held)
    ran_in = []
    task = OVERLAP.beside(
        lambda a, b: ran_in.append(threading.current_thread()) or a + b,
        2, 3, what="test")
    assert task.result() == 5
    assert ran_in and ran_in[0] is not threading.current_thread()
    assert held.released == 1


def test_beside_answers_none_without_a_free_slot(monkeypatch):
    held = _Held(0)
    monkeypatch.setattr(OVERLAP.MACHINE_SLOTS, "try_take",
                        lambda n, **kw: held)
    assert OVERLAP.beside(lambda: 1) is None
    assert held.released == 1


def test_a_task_error_is_raised_by_result(monkeypatch):
    held = _Held(1)
    monkeypatch.setattr(OVERLAP.MACHINE_SLOTS, "try_take",
                        lambda n, **kw: held)

    def fails():
        raise ValueError("boom")
    task = OVERLAP.beside(fails)
    with pytest.raises(ValueError):
        task.result()
    assert held.released == 1


@pytest.mark.parametrize("mode", ["refuse", "off"])
def test_only_a_report_preflight_waits_for_the_mesher(monkeypatch, mode):
    monkeypatch.setenv("O4_HAIRLINE_PREFLIGHT", mode)
    monkeypatch.setattr(OVERLAP, "beside", lambda *a, **k: "started")
    assert MESH._hairline_preflight_beside("x.poly", object()) is None


def test_a_report_preflight_starts_beside(monkeypatch):
    monkeypatch.delenv("O4_HAIRLINE_PREFLIGHT", raising=False)
    calls = []
    monkeypatch.setattr(OVERLAP, "beside",
                        lambda task, *a, **k: calls.append((task, a)) or "t")
    tile = object()
    assert MESH._hairline_preflight_beside("x.poly", tile) == "t"
    assert calls == [(MESH.hairline_preflight, ("x.poly", tile))]
