"""The map's ONE key (owner 2026-11-12T22:05Z; ``O4_Map_Key_Text``,
``O4_Qt_Map_Key``; Mac ``MapKeyText`` / ``MapKey.swift``): the same
items, words and order in both apps and both views, a pill at the map's
bottom-right with the ZL pill one row above it, its words truncated when
the row runs out of room and the full sentence on hover."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Fly_Text as FLYTEXT  # noqa: E402
import O4_Map_Key_Text as KEYTEXT  # noqa: E402
import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SWIFT = REPO / "Sources" / "SceneryKit" / "MapKeyText.swift"


def _swift_items():
    text = SWIFT.read_text(encoding="utf-8", newline="\n")
    world = dict(re.findall(r'static let (\w+) = "([^"]*)"', (
        SWIFT.parent / "WorldStateText.swift").read_text(encoding="utf-8")))
    body = text[text.index("items: [(String"):text.index("public static let short")]
    rows = re.findall(r'\("(\w+)", "([^"]+)", (?:"([^"]+)"|O4WorldStateText\.(\w+))\)', body)
    return [(item, short, literal or world[name]) for item, short, literal, name in rows], text


def test_the_items_words_and_order_are_the_macs():
    items, text = _swift_items()
    assert items == list(KEYTEXT.ITEMS)
    fly = dict(re.findall(r'"(\w+)": "(\w+)"', text[text.index("flyKeyItems"):
                                                    text.index("maxWidthFraction")]))
    assert fly == KEYTEXT.FLY_KEY_ITEMS
    assert ("maxWidthFraction: Double = %s" % KEYTEXT.MAX_WIDTH_FRACTION) in text


def test_every_fly_key_has_an_item_and_the_words_are_short():
    assert {key for key, _w in FLYTEXT.LEGEND} == set(KEYTEXT.FLY_KEY_ITEMS)
    assert set(KEYTEXT.FLY_KEY_ITEMS.values()) <= set(KEYTEXT.SHORT)
    assert all(len(short) <= 12 for short in KEYTEXT.SHORT.values())
    assert KEYTEXT.ordered(["custom", "full", "full", "drape"]) == ["full", "drape", "custom"]


def test_short_words_keep_theirs_and_long_ones_share_the_rest():
    import O4_Qt_Map_Key as QTKEY
    assert QTKEY._fit_caps([10, 20, 30], 100) == [10, 20, 30]
    caps = QTKEY._fit_caps([10, 40, 60], 70)
    assert caps == [10, 30, 30] and sum(caps) == 70


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _paint(items, width):
    import O4_Qt_Map_Key as QTKEY
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter
    image = QImage(width, 300, QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    pill, hits = QTKEY.paint_key(painter, QRectF(0, 0, width, 300), items)
    painter.end()
    return pill, hits


def test_the_pill_sits_bottom_right_and_hover_gives_the_sentence(qapp):
    import O4_Qt_Map_Key as QTKEY
    items = KEYTEXT.ordered(KEYTEXT.SHORT)
    pill, hits = _paint(items, 4000)
    assert pill.right() == pytest.approx(4000 - QTKEY.MARGIN)
    assert pill.bottom() == pytest.approx(300 - QTKEY.MARGIN)
    assert len(hits) == len(items)
    # a row: left to right in the key's order
    assert [h[0].left() for h in hits] == sorted(h[0].left() for h in hits)
    assert QTKEY.tooltip_at(hits, hits[0][0].center()) == KEYTEXT.FULL[items[0]]
    assert QTKEY.tooltip_at(hits, pill.topLeft() - pill.center()) is None


def test_a_narrow_map_truncates_the_words_within_its_limit(qapp):
    import O4_Qt_Map_Key as QTKEY
    items = KEYTEXT.ordered(KEYTEXT.SHORT)
    wide, _ = _paint(items, 4000)
    narrow, hits = _paint(items, 600)
    assert narrow.width() < wide.width()
    assert narrow.left() >= QTKEY.MARGIN - 1   # never off the map
    assert len(hits) == len(items)             # every item, words truncated
    few = ["full", "mesh", "drape", "placeholder", "custom"]
    pill, _ = _paint(few, 400)
    assert pill.width() <= 400 * KEYTEXT.MAX_WIDTH_FRACTION + 1


def test_no_items_no_pill(qapp):
    pill, hits = _paint([], 800)
    assert pill.isEmpty() and hits == []


def test_the_zl_pill_moves_up_one_row_above_the_key(qapp, tmp_path, monkeypatch):
    from unittest import mock

    import O4_Qt_Map as QTMAP
    monkeypatch.setattr(QTMAP, "livemap_cache_dir", lambda: str(tmp_path / "livemap"))
    view = QTMAP.MapView()
    view._start_workers = lambda: None
    view._update_timer.stop()
    view.resize(900, 600)
    lifts = []
    with mock.patch.object(view, "_draw_zoom_badge",
                           side_effect=lambda _p, lift=0.0: lifts.append(lift)):
        view.grab()                                    # Build view, nothing on the map
        view.fly_key = lambda: ["draping", "full"]     # the Fly view's key
        view.grab()
    assert lifts[0] == 0 and lifts[-1] > 0
    assert [t for _r, t in view._key_hits] == [KEYTEXT.FULL["draping"], KEYTEXT.FULL["full"]]
    view.deleteLater()
