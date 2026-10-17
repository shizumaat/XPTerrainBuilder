"""Twin of ``Tests/SceneryKitTests/AirportSearchTests.swift`` (#543).

Both read ``fixtures/airport_search_cases.json`` -- normalisation, the
result row text, the no-match row and the ranking -- so the Mac and Qt
search fields find and order airports the same way.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Airport_Index as AI  # noqa: E402
import O4_Airport_Search as SEARCH  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "airport_search_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)

INDEX = SEARCH.AirportSearchIndex([
    AI.AirportEntry(e["code"], e["name"], e["city"], e["country"], 0.0, 0.0,
                    runway_m=e["runway_m"], size_class=e["size_class"])
    for e in CASES["index"]])


@pytest.mark.parametrize("case", CASES["normalize"])
def test_normalize(case):
    assert SEARCH.normalize(case["text"]) == case["normal"]


@pytest.mark.parametrize("case", CASES["labels"])
def test_result_label(case):
    assert SEARCH.result_label(case["code"], case["name"], case["city"],
                               case["country"]) == case["label"]


@pytest.mark.parametrize("case", CASES["no_match"])
def test_no_match_text(case):
    assert SEARCH.no_match_text(case["query"]) == case["text"]


@pytest.mark.parametrize("case", CASES["search"])
def test_search(case):
    assert [e.code for e in INDEX.search(case["query"])] == case["codes"]


def test_limit():
    index = SEARCH.AirportSearchIndex([
        AI.AirportEntry("A%03d" % i, "Alpha %d" % i, "", "", 0.0, 0.0)
        for i in range(20)])
    assert len(index.search("alpha")) == SEARCH.RESULT_LIMIT
    assert len(index.search("alpha", limit=3)) == 3
