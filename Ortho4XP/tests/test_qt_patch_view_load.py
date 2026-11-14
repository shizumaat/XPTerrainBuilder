"""#2061: the map's patch loads without the staleness check when the
engine answers it on its own (``patch_staleness``), and the answer
completes only the document it was asked for.  Twin of
``Tests/SceneryKitTests/PatchViewLoadTests.swift``: both read
``fixtures/patch_view_load_cases.json``."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Qt_Patch_View_Load as VIEWLOAD  # noqa: E402

_CASES = os.path.join(os.path.dirname(__file__), "fixtures", "patch_view_load_cases.json")


def _fixture():
    with open(_CASES, encoding="utf-8") as f:
        return json.load(f)


def test_the_shared_load_cases():
    cases = _fixture()["load_cases"]
    assert cases
    for case in cases:
        got = VIEWLOAD.load_arguments(case["tile"], case["icao"], case["fast"])
        assert got == case["arguments"], case["name"]


def test_the_shared_applies_cases():
    cases = _fixture()["applies_cases"]
    assert cases
    for case in cases:
        assert VIEWLOAD.staleness_applies(case["opened_path"], case["answer_path"]) \
            is case["applies"], case["name"]
