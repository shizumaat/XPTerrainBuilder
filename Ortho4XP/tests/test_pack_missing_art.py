"""#433 (owner RULINGS 2026-10-06c): a pack X-Plane will not load — the
engine stage's decision and the protocol 1.9 surface.

The object stage (``auto_patch.engine_v2``) names a pack whose DSF declares
art that is not installed; a harness / measure-only run ONLY reports; the
DSF is written without the missing definitions only when the user accepted
that; the event never claims an omission that is not on disk.  The
``PackMissingArt`` event, the ``omit_missing_art`` command and the
``missing_art`` build keyword are additive (``events.py`` class names ARE
the wire names; ``OrthoEngineClient.swift`` matches them as literals).

Headless, no network, no DSFTool: the check and the write are stubbed here
(their own twins are ``tests/auto_patch_v2/test_pack_art.py``).
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_UI_Utils as UI                                   # noqa: E402
from auto_patch import engine_v2 as E                     # noqa: E402
from auto_patch_v2.airport.pack_art import MissingDef     # noqa: E402
from o4_engine import events as EV                         # noqa: E402

POL = (MissingDef("polygon", 0, "Imagery/a.pol", 1),
       MissingDef("polygon", 1, "Imagery/b.pol", 1))
TER = (MissingDef("terrain", 0, "terrain/gone.ter", 3),)


def _art(missing=POL, omit=False, stale=False, current=False):
    return E._PackArt("Some Pack", "/p/dsf", missing, omit, stale, current)


@pytest.fixture
def stage(monkeypatch):
    """Stub the check and the write; collect what the UI hook was told."""
    seen = {"events": [], "writes": [], "art": None, "raise": None}

    def fake_pack_art(pack_root, lat, lon, *, read_only, policy):
        seen["read_only"], seen["policy"] = read_only, policy
        return seen["art"]

    def fake_write(art, pack_root, icao=""):
        if seen["raise"]:
            raise seen["raise"]
        seen["writes"].append((art.omit, art.stale))

    monkeypatch.setattr(E, "_pack_art", fake_pack_art)
    monkeypatch.setattr(E, "_write_art_only", fake_write)
    monkeypatch.setattr(UI, "pack_missing_art",
                        lambda **f: seen["events"].append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    monkeypatch.setattr(E, "MISSING_ART_POLICY", None)
    return seen


PLAN = types.SimpleNamespace(pack_root="/X/Custom Scenery/Some Pack")
TILE = types.SimpleNamespace(lat=25, lon=51)


def test_a_read_only_run_reports_and_writes_nothing(stage):
    stage["art"] = _art(omit=True)
    E._art_stage(PLAN, TILE, writes=False, place=False)
    assert stage["read_only"] is True
    assert stage["writes"] == []
    [ev] = stage["events"]
    assert ev["state"] == "found" and ev["total"] == 2 and ev["can_omit"]
    assert ev["pack"] == "Some Pack" and (ev["lat"], ev["lon"]) == (25, 51)


def test_nothing_missing_says_nothing(stage):
    stage["art"] = _art(missing=())
    assert E._art_stage(PLAN, TILE, writes=True, place=False) is None
    assert stage["events"] == [] and stage["writes"] == []


def test_unaccepted_is_named_and_left(stage):
    stage["art"] = _art(omit=False)
    E._art_stage(PLAN, TILE, writes=True, place=False)
    assert stage["writes"] == []
    assert [e["state"] for e in stage["events"]] == ["found"]


def test_accepted_without_placement_writes_then_says_omitted(stage):
    stage["art"] = _art(omit=True)
    E._art_stage(PLAN, TILE, writes=True, place=False)
    assert stage["writes"] == [(True, False)]
    assert [e["state"] for e in stage["events"]] == ["omitted"]


def test_an_omission_already_on_disk_is_not_rewritten(stage):
    stage["art"] = _art(omit=True, current=True)
    E._art_stage(PLAN, TILE, writes=True, place=False)
    assert stage["writes"] == []
    assert [e["state"] for e in stage["events"]] == ["omitted"]


def test_a_failed_write_says_failed(stage):
    stage["art"] = _art(omit=True)
    stage["raise"] = RuntimeError("encoder refused")
    E._art_stage(PLAN, TILE, writes=True, place=False)
    [ev] = stage["events"]
    assert ev["state"] == "failed" and "encoder refused" in ev["error"]


def test_a_stale_omission_is_put_back_silently_when_art_returned(stage):
    stage["art"] = _art(missing=(), omit=False, stale=True)
    E._art_stage(PLAN, TILE, writes=True, place=False)
    assert stage["writes"] == [(False, True)]
    assert stage["events"] == []


def test_with_placement_nothing_is_announced_before_the_write(stage):
    stage["art"] = _art(omit=True)
    art = E._art_stage(PLAN, TILE, writes=True, place=True)
    assert stage["events"] == [] and stage["writes"] == []
    E._art_after_place(art, PLAN, TILE, written=True)
    assert stage["writes"] == [], "the placement write carried it"
    assert [e["state"] for e in stage["events"]] == ["omitted"]


def test_a_placement_that_wrote_nothing_still_applies_the_answer(stage):
    stage["art"] = _art(omit=True)
    art = E._art_stage(PLAN, TILE, writes=True, place=True)
    E._art_after_place(art, PLAN, TILE, written=False)
    assert stage["writes"] == [(True, False)]
    assert [e["state"] for e in stage["events"]] == ["omitted"]


def test_terrain_is_named_but_never_omitted(stage):
    stage["art"] = _art(missing=TER, omit=False)
    E._art_stage(PLAN, TILE, writes=True, place=False)
    [ev] = stage["events"]
    assert ev["can_omit"] is False and ev["kinds"] == {"terrain": 1}
    assert stage["writes"] == []


def test_the_policy_reaches_the_check(stage):
    stage["art"] = None
    E.set_missing_art_policy("omit")
    try:
        E._art_stage(PLAN, TILE, writes=True, place=False)
        assert stage["policy"] == "omit"
    finally:
        E.set_missing_art_policy(None)
    E.set_missing_art_policy("bogus")
    assert E.MISSING_ART_POLICY is None


def test_the_offer_with_terrain_only_fails_without_writing(stage):
    stage["art"] = _art(missing=TER, omit=False)
    out = E.omit_missing_art("/X/Custom Scenery/Some Pack", 25, 51)
    assert out["state"] == "failed" and stage["writes"] == []


def test_the_offer_writes_and_reports(stage):
    stage["art"] = _art(omit=True)
    out = E.omit_missing_art("/X/Custom Scenery/Some Pack", 25, 51)
    assert out["state"] == "omitted" and stage["writes"] == [(True, False)]
    assert [e["state"] for e in stage["events"]] == ["omitted"]


# ── protocol 1.9 ────────────────────────────────────────────────────────

def test_the_protocol_version_is_1_9():
    assert EV.PROTOCOL_VERSION == "1.9"


def test_the_wire_name_and_fields_are_frozen():
    assert EV.PackMissingArt.__name__ == "PackMissingArt"
    assert [f.name for f in dataclasses.fields(EV.PackMissingArt)
            if f.name not in ("seq", "ts")] == [
        "pack", "pack_root", "lat", "lon", "total", "kinds", "uses",
        "first_paths", "can_omit", "state", "error"]
    assert EV.PackMissingArt().can_omit is False, "no offer without a yes"


def test_it_serialises_and_the_swift_client_matches_it():
    from o4_engine.jsonl import serialize_event

    line = json.dumps(serialize_event(EV.PackMissingArt(
        pack="P", total=2, kinds={"polygon": 2}, first_paths=["a.pol"],
        can_omit=True)))
    assert '"PackMissingArt"' in line and '"first_paths"' in line
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "OrthoEngineClient.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    assert 'case "PackMissingArt"' in text
    assert '"omit_missing_art"' in text


def test_the_parallel_forwarder_carries_it():
    from o4_engine import parallel as P

    assert "PackMissingArt" in P._FORWARDED_EVENT_TYPES
    event = P._rebuild_event({"event": "PackMissingArt", "pack": "P",
                              "can_omit": True, "state": "found"})
    assert isinstance(event, EV.PackMissingArt) and event.can_omit


def test_the_command_is_registered_and_never_blocks(monkeypatch):
    from o4_engine import jsonl as J
    from o4_engine.session import EngineSession

    session = EngineSession()
    assert J._build_handlers(session)["omit_missing_art"] \
        == session.omit_missing_art
    got = []
    session.subscribe(got.append)
    monkeypatch.setattr(E, "omit_missing_art", lambda root, lat, lon: {
        "pack": "P", "pack_root": root, "lat": lat, "lon": lon,
        "state": "none", "error": ""})
    assert session.omit_missing_art("/p", 25, 51) == {"status": "started"}
    deadline = time.time() + 10
    while not [e for e in got if isinstance(e, EV.PackMissingArt)] \
            and time.time() < deadline:
        time.sleep(0.01)
    [ev] = [e for e in got if isinstance(e, EV.PackMissingArt)]
    assert ev.state == "none" and ev.pack_root == "/p"


def test_the_session_hook_drops_unknown_fields():
    from o4_engine.session import EngineSession

    session = EngineSession()
    got = []
    session.subscribe(got.append)
    session.pack_missing_art(pack="P", state="found", someday_field=1)
    [ev] = [e for e in got if isinstance(e, EV.PackMissingArt)]
    assert ev.pack == "P"
