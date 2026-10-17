"""Twin of ``Tests/SceneryKitTests/MapGuidanceTests.swift`` (#828): both
read ``fixtures/map_guidance_cases.json`` -- the words and the hint's
dismissal rule -- so the Mac and Qt apps guide a first visit alike."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Map_Guidance as GUIDE  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "map_guidance_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


def test_copy():
    copy = CASES["copy"]
    assert GUIDE.HINT_TEXT == copy["hint"]
    assert GUIDE.SHOW_TIPS_TITLE == copy["show_tips"]
    assert GUIDE.EMPTY_SELECTION_TEXT == copy["empty_selection"]
    assert GUIDE.NOTHING_BUILT_TEXT == copy["nothing_built"]
    assert GUIDE.HINT_DISMISSED_PREF == copy["pref_key"]


@pytest.mark.parametrize("case", CASES["sequences"])
def test_dismissal(case):
    assert GUIDE.visibility(case["dismissed"], case["events"]) == case["shown"]
