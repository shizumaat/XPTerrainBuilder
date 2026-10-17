"""Twin of ``Tests/SceneryKitTests/MapLabelLayoutTests.swift`` (#817).

Both run ``fixtures/map_label_cases.json`` -- the size-class gates, the
label point size, the imagery label text and label placement (rank
order, no overlap) -- so the Qt and Mac maps label the same airports.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Map_Labels as LABELS  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "map_label_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


@pytest.mark.parametrize("case", CASES["gates"])
def test_gates(case):
    args = (case["size_class"], case["custom"], case["scale"])
    assert LABELS.mark_visible(*args) is case["mark"]
    assert LABELS.label_allowed(*args) is case["label"]


@pytest.mark.parametrize("case", CASES["font"])
def test_font_size(case):
    assert LABELS.label_font_size(case["scale"]) == case["size"]


@pytest.mark.parametrize("case", CASES["radius"])
def test_mark_radius(case):
    assert LABELS.mark_radius(case["scale"]) == case["radius"]


@pytest.mark.parametrize("case", CASES["imagery"])
def test_imagery_label(case):
    assert LABELS.imagery_label(case["provider"], case["zl"],
                                case["zones"]) == case["text"]


@pytest.mark.parametrize("case", CASES["place"])
def test_place_airport_labels(case):
    candidates = [LABELS.LabelCandidate(
        c["code"], c["x"], c["y"], c["size_class"], c["runway_m"],
        c["custom"]) for c in case["candidates"]]
    marks, labels = LABELS.place_airport_labels(
        candidates, case["scale"], case["radius"])
    assert [candidates[i].code for i in marks] == case["marks"]
    assert [candidates[i].code for i, _ in labels] == case["labels"]
    boxes = [box for _, box in labels]
    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            assert not LABELS._overlaps(boxes[a], boxes[b])


def test_placement_never_overlaps_on_a_dense_grid():
    """A carpet of same-class airports 8 px apart: whatever survives
    never overlaps, and the cap holds."""
    candidates = [LABELS.LabelCandidate("A%03d" % (i * 40 + j), 8.0 * i,
                                        8.0 * j, 0, 3000, False)
                  for i in range(40) for j in range(40)]
    _, labels = LABELS.place_airport_labels(candidates, 100.0, 5.0)
    boxes = [box for _, box in labels]
    assert 0 < len(boxes) <= LABELS.MAX_AIRPORT_LABELS
    for a in range(len(boxes)):
        for b in range(a + 1, len(boxes)):
            assert not LABELS._overlaps(boxes[a], boxes[b])


def test_slippy_zoom_scale_matches_the_old_gates():
    # The old Qt default-label zoom 6.2 was the Mac scale 52.
    assert LABELS.scale_for_slippy_zoom(6.2) == pytest.approx(52.3, abs=0.1)
