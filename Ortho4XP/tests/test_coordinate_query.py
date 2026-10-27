"""Twin of ``Tests/SceneryKitTests/CoordinateQueryTests.swift`` (#1317).

Both read ``fixtures/latlon_search_cases.json`` -- tile keys, typed
points (decimal, hemisphere letters, DMS, decimal minutes) and the texts
that are not coordinates -- so the Mac and Qt search fields read a typed
coordinate the same way.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Coordinate_Query as CQ  # noqa: E402
import pytest  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "latlon_search_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


@pytest.mark.parametrize("case", CASES["tiles"], ids=lambda c: c["text"])
def test_tile_key_wins(case):
    assert CQ.classify(case["text"]) == ("tile", (case["lat"], case["lon"]))


@pytest.mark.parametrize("case", CASES["points"], ids=lambda c: c["text"])
def test_point(case):
    kind, (lat, lon) = CQ.classify(case["text"])
    assert kind == "point"
    assert lat == pytest.approx(case["lat"], abs=1e-9)
    assert lon == pytest.approx(case["lon"], abs=1e-9)


@pytest.mark.parametrize("text", CASES["rejects"])
def test_not_a_coordinate(text):
    assert CQ.classify(text) is None
