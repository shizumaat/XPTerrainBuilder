"""Capability flags replace protocol bumps (owner RULINGS 2026-11-03d (1),
item 3): the protocol number is frozen at 1.32, every hello names
``events.CAPABILITIES``, and every flag the Mac app asks for is one the
engine announces (a cross-language STRING LITERAL — the Swift side lives
in ``Sources/SceneryKit/EngineCapabilities.swift``)."""
from __future__ import annotations

import json
import pathlib
import re

from o4_engine import events as EV
from o4_engine.events import CAPABILITIES, EngineHello
from o4_engine.jsonl import serialize_event

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SWIFT = _REPO / "Sources" / "SceneryKit" / "EngineCapabilities.swift"

#: The flags the JSONL hello named before the freeze: a released app may
#: ask for any of them, so none is ever dropped.
_BEFORE = ("scan", "build", "enqueue_build", "cancel", "tile_info", "config",
           "links", "siblings", "secrets", "tile_settings_write",
           "missing_art", "library", "pack_forests", "pack_optimise",
           "pack_optimise_steps")


def test_the_protocol_number_is_frozen():
    assert EV.PROTOCOL_VERSION == "1.32", (
        "the protocol number is frozen (RULINGS 2026-11-03d (1) item 3): "
        "add a flag to events.CAPABILITIES instead of a bump")


def test_the_flags_are_names_and_only_grow():
    assert all(isinstance(f, str) and re.fullmatch(r"[a-z][a-z0-9_]*", f)
               for f in CAPABILITIES)
    assert len(set(CAPABILITIES)) == len(CAPABILITIES)
    assert set(_BEFORE) <= set(CAPABILITIES)


def test_every_hello_names_the_flags():
    wire = json.loads(json.dumps(serialize_event(EngineHello(ortho4xp_version="dev"))))
    assert tuple(wire["capabilities"]) == CAPABILITIES
    assert wire["protocol"] == EV.PROTOCOL_VERSION
    # neither transport spells its own list again
    src = _REPO / "Ortho4XP" / "src" / "o4_engine"
    for name in ("jsonl.py", "session.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert "capabilities=(" not in text, name


def test_every_flag_the_mac_app_asks_for_is_announced():
    text = _SWIFT.read_text(encoding="utf-8")
    asked = re.findall(r'public static let \w+ = "([a-z0-9_]+)"', text)
    assert asked, "the Swift capability names moved; update this twin"
    missing = sorted(set(asked) - set(CAPABILITIES))
    assert not missing, ("the Mac app asks for flags the engine never "
                         "announces: %s" % missing)
