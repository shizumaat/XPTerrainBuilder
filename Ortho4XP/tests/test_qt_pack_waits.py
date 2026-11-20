"""#2200: the pack commands' working state — the Qt copy is the mac
app's VERBATIM (``Sources/XPTerrainBuilder/PackCommandWaits.swift``,
``PackWaitCopy``), the keys and the outcome line.  Headless."""
from __future__ import annotations

import os
import re
import types

import O4_Qt_Pack_Waits as W

_SWIFT = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                      "XPTerrainBuilder", "PackCommandWaits.swift")


def _swift() -> str:
    with open(_SWIFT, encoding="utf-8") as fh:
        return fh.read()


def test_the_copy_is_the_mac_apps():
    src = _swift()
    assert f'static let checking = "{W.CHECKING}"' in src
    tile = "\\(tile)"
    for line in (W.checking_line(tile), W.applying_line(tile),
                 W._failed_line(tile, "\\(error)"), W.refused_line("\\(reason)"),
                 W._applied_line(tile, 0)):
        assert f'"{line}"' in src, line
    one, two = W._applied_line("T", 1), W._applied_line("T", 2)
    assert one.endswith("(1 pack DSF rewritten).") and two.endswith("(2 pack DSFs rewritten).")
    assert re.search(r'applied \(\\\(files\) pack DSF\\\(files == 1 \? "" : "s"\) rewritten\)\.',
                     src)


def test_the_outcome_line_of_an_answer_and_none_for_a_question():
    ev = types.SimpleNamespace(lat=25, lon=55, state="chosen",
                               files=["a.dsf"], error="")
    assert W.outcome_line(ev) == "Pack choices on +25+055: applied (1 pack DSF rewritten)."
    assert W.outcome_line(types.SimpleNamespace(lat=25, lon=55, state="failed",
                                                files=[], error="no X-Plane")) \
        == "Pack choices on +25+055: could not be applied (no X-Plane)."
    assert W.outcome_line(types.SimpleNamespace(lat=25, lon=55, state="ask")) == ""


def test_one_wait_per_key_and_refusals():
    waits = W.PackWaits()
    key = W.pack_key("/X/Custom Scenery/Pack A/")
    assert key == "pack|Pack A" and W.overlaps_key(-3, 7) == "overlaps|-03+007"
    assert waits.start(key) and not waits.start(key) and waits.waiting(key)
    waits.end(key)
    assert not waits.waiting(key)
    assert W.refusal({"status": "refused", "reason": "building"}) == "building"
    assert W.refusal({"status": "started"}) == "" and W.refusal(None) == ""
