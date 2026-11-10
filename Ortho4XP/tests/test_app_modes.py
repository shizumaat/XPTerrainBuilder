"""Build · Fly · Library (RULINGS 2026-11-10j; spec §14, lane U1).

``src/O4_App_Modes.py`` (the Qt window's) and the Mac app's
``AppMode.swift`` hold the same keys, words and Fly-offer rule.  This twin
proves the rule on hand cases and parses the Swift file for the words.
Hermetic: no Qt, no network.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_App_Modes as MODES  # noqa: E402
import O4_Glossary as GLOSSARY  # noqa: E402

SWIFT = Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder" / "AppMode.swift"


def test_modes_and_remembered_mode():
    assert MODES.MODES == ("build", "fly", "library")
    assert MODES.restore("fly") == "fly"
    assert MODES.restore(None) == MODES.DEFAULT == "build"
    assert MODES.restore("manage") == "build"
    swift = SWIFT.read_text(encoding="utf-8")
    assert "case build, fly, library" in swift
    assert all(GLOSSARY.TERMS["mode_" + m] for m in MODES.MODES)


def test_the_words_are_the_macs():
    swift = SWIFT.read_text(encoding="utf-8")
    for name, value in (("flyPlaceholder", MODES.FLY_PLACEHOLDER),
                        ("offerText", MODES.OFFER_TEXT),
                        ("offerOpen", MODES.OFFER_OPEN),
                        ("offerDismiss", MODES.OFFER_DISMISS),
                        ("storagePointer", MODES.STORAGE_POINTER),
                        ("storagePointerButton", MODES.STORAGE_POINTER_BUTTON)):
        said = re.search(r'static let %s = "([^"]+)"' % name, swift)
        assert said and said.group(1) == value, name


def test_the_offer_rule_is_the_macs():
    swift = SWIFT.read_text(encoding="utf-8")
    assert 'xplane && (state == "following" || state == "paused")' in swift
    assert "isLoaded && (!loaded || status.flightLoads > loads)" in swift


def test_fly_is_offered_never_switched():
    offer = MODES.FlyOffer()
    assert not offer.observe("waiting", False, 0, "build")     # no X-Plane
    assert offer.observe("following", True, 0, "build")        # flight loaded
    assert offer.observe("following", True, 0, "build")        # stays shown
    offer.dismiss()                                             # "Not now"
    assert not offer.observe("following", True, 0, "library")  # same flight
    assert offer.observe("following", True, 1, "library")      # a new load
    assert not offer.observe("following", True, 1, "fly")      # in Fly: hidden
    assert not offer.observe("waiting", False, 1, "build")     # X-Plane gone
    assert offer.observe("paused", True, 1, "build")           # back again


def test_no_offer_while_already_in_fly():
    offer = MODES.FlyOffer()
    assert not offer.observe("following", True, 0, "fly")
    # Leaving Fly during the same flight does not offer it back.
    assert not offer.observe("following", True, 0, "build")
