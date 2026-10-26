"""Issue #825: the per-step strip of each tile's Activity row.

``O4_Step_Strip`` (the Qt window's mapping) replays the shared fixture
``fixtures/step_strip_cases.json``; the Mac app's ``O4StepStrip`` replays
the same file in ``Tests/SceneryKitTests/StepStripTests.swift``, so both
apps show the same strip for the same events.  The airport-stage table is
compared with the Swift one here; ``test_qt_step_strip.py`` feeds an
offscreen Qt window a build's events and reads the strip on the row.
"""

import dataclasses
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Step_Strip as STRIP  # noqa: E402
import pytest  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine.jsonl import serialize_event  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "step_strip_cases.json")
SWIFT = os.path.join(HERE, "..", "..", "Sources", "SceneryKit",
                     "StepStrip.swift")


def _cases():
    with open(FIXTURE, "r", encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def event_from_wire(payload):
    """The engine event a JSONL payload (``serialize_event``) carries."""
    cls = getattr(EV, payload["event"])
    names = {field.name for field in dataclasses.fields(cls)}
    kwargs = {k: v for k, v in payload.items() if k in names}
    if "airports" in kwargs:
        kwargs["airports"] = tuple(kwargs["airports"])
    return cls(**kwargs)


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["name"])
def test_fixture_case(case):
    strip = STRIP.new_strip()
    checked = 0
    for step in case["steps"]:
        event = event_from_wire(step["event"])
        # The fixture is the wire: what the engine would really send.
        assert serialize_event(event) == step["event"]
        STRIP.apply_event(strip, event, float(step["t"]))
        if "expect" in step:
            got = [list(segment) for segment in STRIP.segments(strip)]
            assert got == step["expect"], "after t=%s" % step["t"]
            checked += 1
    assert checked


def test_every_state_and_step_is_in_the_fixture():
    states, texts = set(), []
    for case in _cases():
        for step in case["steps"]:
            for state, text in step.get("expect", ()):
                states.add(state)
                texts.append(text)
    assert states == set(STRIP.GLYPHS)
    assert any("shaping runways (65 %)" in text for text in texts)
    assert any(text.endswith("reused") for text in texts)


def test_airport_stage_words():
    assert STRIP.airport_stage(
        "Solving the surface (HiGHS LP) — still working: 0:40") == (
        "shaping runways")
    assert STRIP.airport_stage("Emitting the patch & verifying") == (
        "writing the airport patch")
    assert STRIP.airport_stage("Something new") == "grading"


def test_every_airport_phase_has_plain_words():
    """A phase label the airport builder sends is never 'grading'."""
    from auto_patch import engine_v2, progress
    for label in progress.PHASE_LABELS + engine_v2.V2_PHASE_LABELS:
        assert STRIP.airport_stage(label) != STRIP.AIRPORT_STAGE_DEFAULT, label


def _swift_table(name):
    with open(SWIFT, "r", encoding="utf-8") as handle:
        source = handle.read()
    body = re.search(r"static let %s[^=]*= \[(.*?)\n    \]" % name,
                     source, re.S)
    assert body, name
    return re.findall(r'\("([^"]*)", "([^"]*)"\)', body.group(1))


def test_swift_tables_match():
    assert tuple(_swift_table("airportStages")) == STRIP.AIRPORT_STAGES
    assert tuple(_swift_table("steps")) == STRIP.PILLS


def test_stop_freezes_the_strip():
    strip = STRIP.new_strip()
    tile = dict(lat=1, lon=2)
    STRIP.apply_event(strip, EV.StepProgress(step_key="mesh", **tile), 0.0)
    STRIP.stop(strip, 5.0)
    STRIP.apply_event(strip, EV.StepProgress(step_key="masks", **tile), 6.0)
    assert [s for s, _t in STRIP.segments(strip)] == [
        "skipped", "skipped", "stopped", "waiting", "waiting", "waiting"]
