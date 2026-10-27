"""Twin of ``Tests/SceneryKitTests/ActivityOrderTests.swift`` (#1341): both
read ``fixtures/activity_order_cases.json`` -- which rows count as
finished, each status's colour role, the Activity list's order, the
section a row sits in, the rows shown selected and a list edit's map
selection -- so
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


@pytest.mark.parametrize("case", CASES["section"])
def test_section(case):
    assert ORDER.section(case["state"]) == case["section"]


@pytest.mark.parametrize("case", CASES["shown"], ids=lambda c: c["name"])
def test_shown_selected(case):
    assert ORDER.shown_selected(case["rows"], case["selected"]) == set(
        case["shown"])


@pytest.mark.parametrize("case", CASES["list_edit"], ids=lambda c: c["name"])
def test_list_edit(case):
    assert ORDER.list_edit(case["new"], case["shown"], case["active"]) == (
        set(case["selected"]), case["to_active"], case["frame"])


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
