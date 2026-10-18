"""Twin of ``Tests/SceneryKitTests/TextScaleTests.swift`` (#827): both
read ``fixtures/text_scale_cases.json`` -- the steps, the prefs key, the
menu titles and the step rule -- so the Mac and Qt apps size text alike."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Text_Scale as TS  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "text_scale_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


def test_steps_key_and_titles():
    assert list(TS.STEPS) == CASES["steps"]
    assert TS.DEFAULT == CASES["default"]
    assert TS.PREF_KEY == CASES["pref_key"]
    titles = CASES["titles"]
    assert (TS.BIGGER_TITLE, TS.SMALLER_TITLE, TS.ACTUAL_TITLE) == (
        titles["bigger"], titles["smaller"], titles["actual"])


def test_the_acceptance_steps_are_offered():
    # #827 acceptance: 100 / 115 / 130 % or more.
    assert {1.0, 1.15, 1.3} <= set(TS.STEPS)
    assert max(TS.STEPS) > 1.3


@pytest.mark.parametrize("case", CASES["clamp"])
def test_clamp(case):
    assert TS.clamp(case["value"]) == case["step"]


@pytest.mark.parametrize("value", [None, "", "big", float("nan")])
def test_an_unreadable_value_is_actual_size(value):
    assert TS.clamp(value) == TS.DEFAULT


@pytest.mark.parametrize("case", CASES["bigger"])
def test_bigger(case):
    assert TS.bigger(case["value"]) == case["next"]


@pytest.mark.parametrize("case", CASES["smaller"])
def test_smaller(case):
    assert TS.smaller(case["value"]) == case["next"]


@pytest.mark.parametrize("case", CASES["scaled"])
def test_scaled(case):
    assert TS.scaled(case["points"], case["value"]) == case["result"]
