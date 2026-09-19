"""§E test 7 — protocol 1.8: the boundary command, event and policy.

Spec ``docs/specs/insets-follow-patch-set-spec.md`` §C.2/§C.3/§C.4.
ADDITIVE ONLY: ``events.py`` class names ARE the JSONL wire names and
``Sources/SceneryKit/OrthoEngineClient.swift`` matches them as string
literals, so this file pins the name and the field set the two UI slices
will be briefed from.  Headless, no network.
"""
from __future__ import annotations

import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from o4_engine import events as EV                       # noqa: E402


def test_the_protocol_version_is_1_8():
    assert EV.PROTOCOL_VERSION == "1.8"


def test_the_wire_name_and_field_set_are_frozen():
    """The UI slices decode THIS.  A rename here silently breaks them."""
    assert EV.BoundaryAirportsReady.__name__ == "BoundaryAirportsReady"
    fields = [f.name for f in
              dataclasses.fields(EV.BoundaryAirportsReady)]
    assert fields[-5:] == ["request_id", "airports", "add_tiles",
                           "remembered", "error"]


def test_it_serialises_through_the_event_encoder():
    from o4_engine.jsonl import serialize_event

    payload = serialize_event(EV.BoundaryAirportsReady(
        request_id=7,
        airports=[{"icao": "LPMT", "name": "Montijo", "home": [38, -10],
                   "neighbours": [[38, -9]], "crossing_m": 620.0}],
        add_tiles=[[38, -9]], remembered=""))
    import json

    line = json.dumps(payload)
    assert '"BoundaryAirportsReady"' in line       # THE WIRE NAME
    assert "LPMT" in line and "crossing_m" in line
    assert payload["add_tiles"] == [[38, -9]]


def test_the_defaults_are_empty_so_an_old_front_end_sees_nothing_new():
    event = EV.BoundaryAirportsReady()
    assert (event.airports, event.add_tiles, event.remembered,
            event.error) == ([], [], "", "")


# ── the command replies at once (the read-loop hazard) ────────────────
def test_boundary_airports_replies_started_without_blocking(monkeypatch):
    from o4_engine.session import EngineSession

    session = EngineSession.__new__(EngineSession)
    import threading

    session._boundary_request_lock = threading.Lock()
    session._boundary_request_id = 0
    emitted = []
    session._emit = emitted.append
    monkeypatch.setattr(
        EngineSession, "_boundary_preflight",
        lambda self, rid, cells: EV.BoundaryAirportsReady(request_id=rid))

    reply = session.boundary_airports(tiles=[[38, -10]])
    assert reply == {"status": "started", "request_id": 1}
    # the answer arrives as an EVENT, off the read loop
    for _ in range(200):
        if emitted:
            break
        import time

        time.sleep(0.01)
    assert emitted and emitted[0].request_id == 1


def test_a_failing_preflight_never_takes_the_build_down(monkeypatch):
    from o4_engine.session import EngineSession

    session = EngineSession.__new__(EngineSession)
    import threading
    import time

    session._boundary_request_lock = threading.Lock()
    session._boundary_request_id = 0
    emitted = []
    session._emit = emitted.append

    def boom(self, rid, cells):
        raise RuntimeError("no CIFP here")

    monkeypatch.setattr(EngineSession, "_boundary_preflight", boom)
    assert session.boundary_airports(tiles=[[38, -10]])["status"] == "started"
    for _ in range(200):
        if emitted:
            break
        time.sleep(0.01)
    assert emitted[0].error == "no CIFP here"
    assert emitted[0].airports == []


# ── the policy keyword ────────────────────────────────────────────────
def test_build_and_enqueue_build_take_the_additive_keyword():
    import inspect

    from o4_engine.session import EngineSession

    for name in ("build", "enqueue_build"):
        parameters = inspect.signature(
            getattr(EngineSession, name)).parameters
        assert "boundary_policy" in parameters
        assert parameters["boundary_policy"].default is None


def test_the_policy_reaches_a_worker_childs_tile_arguments():
    from o4_engine import parallel

    class _Bare(parallel.ParallelBuildRun):
        """Every private collection the admission touches, auto-created —
        this twin is about the ARGUMENT reaching the batch record, not
        about the dispatcher's state machine."""

        def __getattr__(self, name):
            if name.startswith("_"):
                value = {} if name != "_queue" else []
                object.__setattr__(self, name, value)
                return value
            raise AttributeError(name)

    run = _Bare.__new__(_Bare)
    run._children = []
    run._queue = []
    run._total = 0
    admitted = parallel.ParallelBuildRun._admit_batch_locked(
        run, [(38, -10)], "BI", 16, "", (True, False, False),
        boundary_policy="neighbour")
    assert admitted == [(38, -10)]
    assert run._tile_arguments[(38, -10)]["boundary_policy"] == "neighbour"


# ── the remembered answer (§C.4) ──────────────────────────────────────
def test_the_app_cfg_var_carries_the_three_choices():
    import O4_Cfg_Vars

    spec = O4_Cfg_Vars.cfg_app_vars["auto_patch_boundary"]
    assert spec["type"] is str and spec["default"] == "Ask"
    assert tuple(spec["values"]) == ("Ask", "Build adjacent", "Skip patch")


@pytest.mark.parametrize("cfg_value,expected", [
    ("Ask", "skip"),                 # nobody to ask ⇒ SKIP loudly
    ("Build adjacent", "neighbour"),
    ("Skip patch", "skip"),
])
def test_an_unattended_run_never_grows_its_own_tile_list(cfg_value, expected,
                                                         monkeypatch):
    """Owner RULINGS 18c Q5, reaffirmed 18i (3)."""
    import O4_Vector_Map as VMAP

    VMAP.set_boundary_policy(None)
    monkeypatch.setattr(VMAP.CFG, "auto_patch_boundary", cfg_value,
                        raising=False)
    assert VMAP.resolved_boundary_policy(None) == expected


def test_an_explicit_answer_beats_the_remembered_one(monkeypatch):
    import O4_Vector_Map as VMAP

    monkeypatch.setattr(VMAP.CFG, "auto_patch_boundary", "Skip patch",
                        raising=False)
    VMAP.set_boundary_policy("neighbour")
    try:
        assert VMAP.resolved_boundary_policy(None) == "neighbour"
    finally:
        VMAP.set_boundary_policy(None)


def test_garbage_from_an_older_front_end_is_not_a_policy(monkeypatch):
    import O4_Vector_Map as VMAP

    monkeypatch.setattr(VMAP.CFG, "auto_patch_boundary", "Ask",
                        raising=False)
    VMAP.set_boundary_policy("whatever")
    try:
        assert VMAP.resolved_boundary_policy(None) == "skip"
    finally:
        VMAP.set_boundary_policy(None)


# ── the harness flag (§C.4) ───────────────────────────────────────────
def test_the_harness_tile_entry_defaults_to_skip():
    """The harness is UNATTENDED, so it never grows its own tile list."""
    import inspect

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "harness"))
    import build_airport

    assert (inspect.signature(build_airport.build_tile)
            .parameters["boundary"].default == "skip")
    source = inspect.getsource(build_airport.main)
    assert '"--boundary"' in source and 'default="skip"' in source
