"""Twin of ``Tests/SceneryKitTests/ActivityOrderTests.swift`` (#1341): both
read ``fixtures/activity_order_cases.json`` -- which rows count as
finished, each status's colour role, and the Activity list's order -- so
the Mac and Qt apps keep and order their rows alike."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Activity_Order as ORDER  # noqa: E402
import pytest  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "activity_order_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


@pytest.mark.parametrize("case", CASES["finished"])
def test_finished(case):
    assert ORDER.is_finished(case["state"], case["label"]) is case["finished"]


@pytest.mark.parametrize("case", CASES["compact"])
def test_compact(case):
    assert ORDER.is_compact(case["state"]) is case["compact"]


@pytest.mark.parametrize("case", CASES["tones"])
def test_tone(case):
    assert ORDER.status_tone(case["state"], case["label"],
                             case["has_issues"]) == case["tone"]


@pytest.mark.parametrize("sequence", CASES["sequences"],
                         ids=[s["name"] for s in CASES["sequences"]])
def test_order(sequence):
    (stamps, counter) = ({}, 0)
    for number, step in enumerate(sequence["steps"]):
        rows = [(key, ORDER.is_finished(state, label))
                for key, state, label in step["rows"]]
        (stamps, counter) = ORDER.restamp(rows, stamps, counter)
        keys = [key for key, _state, _label in step["rows"]]
        assert ORDER.display_order(keys, stamps) == step["order"], number
