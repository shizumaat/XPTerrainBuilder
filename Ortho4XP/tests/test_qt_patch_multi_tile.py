"""An airport whose patch spans several tiles shows every tile's patch
(issue #1646; the Mac twin is ``PatchSiblingTests.swift``).

The map edits the patch nearest the view centre and draws the same
airport's patches on the other tiles in view read-only beside it.
Offscreen, no network, no engine.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from O4_Qt_Patch_Controller import sibling_entries  # noqa: E402


def _entry(icao, path):
    return {"icao": icao, "path": path, "bbox": [33.4, -112.05, 33.45, -111.95]}


def test_other_tiles_of_the_shown_airport_are_siblings():
    a = _entry("KPHX", "+33-112/KPHX_auto.patch.osm")
    b = _entry("KPHX", "+33-113/KPHX_auto.patch.osm")
    other = _entry("KXYZ", "+33-113/KXYZ_auto.patch.osm")
    candidates = [("+33-112", a), ("+33-113", b), ("+33-113", other)]
    assert sibling_entries(candidates, "+33-112", "KPHX") == [("+33-113", b)]


def test_a_single_tile_airport_has_no_siblings():
    a = _entry("KPHX", "+33-112/KPHX_auto.patch.osm")
    assert sibling_entries([("+33-112", a)], "+33-112", "KPHX") == []
