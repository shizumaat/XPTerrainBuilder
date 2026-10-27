"""A step that ends abnormally must not leave the process "working" (#1175).

Every step function opens with ``if UI.is_working: return 0``.  A vector
step that RAISED (an elevation refusal, tile +59-002) left the flag set in
its parallel worker child; the next tile that child took (+45+005) then
"failed" its vector step at once with nothing logged and no cause — the
app said "The app did not record a specific cause".  The session's step
runner clears the flag however the step ends; these twins drive the REAL
vector step's guard through it.
"""
from __future__ import annotations

from types import SimpleNamespace

import O4_UI_Utils as UI
import O4_Vector_Map as VMAP
import pytest
from o4_engine.session import EngineSession


class _Reached(Exception):
    """The step got past its busy guard."""


def _tile():
    return SimpleNamespace(lat=45, lon=5)


@pytest.fixture(autouse=True)
def _idle(monkeypatch):
    monkeypatch.setattr(UI, "is_working", False)


def _reach(*_a, **_k):
    raise _Reached


def test_a_raising_step_leaves_the_next_step_runnable(monkeypatch):
    session = EngineSession()

    def raises(tile):
        UI.is_working = 1               # what every step does on entry
        raise RuntimeError("elevation refused")

    with pytest.raises(RuntimeError):
        session._run_step(raises, "vector", _tile(), [("vector", 0, 1)])
    assert not UI.is_working
    monkeypatch.setattr(VMAP, "_refuse_on_broken_proj", _reach)
    with pytest.raises(_Reached):       # NOT a silent ``return 0``
        session._run_step(VMAP.build_poly_file, "vector", _tile(),
                          [("vector", 0, 1)])


def test_an_early_return_that_keeps_the_flag_is_cleared(monkeypatch):
    # build_poly_file's PROJ refusal returns 0 with the flag still set.
    session = EngineSession()
    monkeypatch.setattr(VMAP, "_refuse_on_broken_proj", lambda: True)
    assert session._run_step(VMAP.build_poly_file, "vector", _tile(),
                             [("vector", 0, 1)]) == 0
    assert not UI.is_working
