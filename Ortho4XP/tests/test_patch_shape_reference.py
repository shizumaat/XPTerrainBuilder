""""Copy shape reference" (#1281): the Qt formatter against the twin
fixture the Mac app's ``PatchShapeReferenceTests`` reads, and the menu
titles both apps share.  Pure; no Qt."""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Qt_Patch_Reference as REFERENCE  # noqa: E402
import pytest  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "patch_shape_reference.json")
with open(FIXTURE, encoding="utf-8") as _f:
    CASES = json.load(_f)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_every_fixture_case_formats_exactly(case):
    i = case["input"]
    text = REFERENCE.shape_reference_text(
        i["tile"], i["icao"], i["patch_file"], i["engine_version"], i["way_id"], i["tags"],
        i["closed"], i["area_m2"], [tuple(v) for v in i["vertices"]])
    assert text == case["expected"]


def test_the_block_lists_at_most_five_vertices():
    assert REFERENCE.FIRST_VERTICES == 5
    longest = max(CASES, key=lambda c: len(c["input"]["vertices"]))
    assert len(longest["input"]["vertices"]) > REFERENCE.FIRST_VERTICES
    listed = longest["expected"].split("First vertices:\n")[1].splitlines()
    assert len(listed) == REFERENCE.FIRST_VERTICES


def test_the_mac_app_uses_the_same_menu_titles():
    swift = (Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder"
             / "PatchCopy.swift").read_text(encoding="utf-8")
    def title(name):
        return re.search(name + r' = "([^"]*)"', swift).group(1)
    assert title("coordinatesTitle") == REFERENCE.COPY_COORDINATES
    assert title("shapeReferenceTitle") == REFERENCE.COPY_SHAPE_REFERENCE
