"""The map's ONE key, painted (Qt half; the Mac app's ``MapKey.swift``):
a pill at the map's bottom-right, its items in a row, each a swatch in
its one colour and a short word (``O4_Map_Key_Text``), the words
truncated with "…" when the row runs out of room; :func:`tooltip_at`
gives the full sentence under the pointer.  The Build view and the Fly
view both paint it (``O4_Qt_Map.MapView.paintEvent``).
"""
from __future__ import annotations

import O4_Map_Key_Text as KEYTEXT
import O4_Qt_Map_Legend as QTLEGEND
import O4_Qt_Map_World as QTWORLD
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen

__all__ = ["MARGIN", "item_color", "paint_key", "tooltip_at"]

#: The pill's right and bottom margin, the ZL pill's (O4_Qt_Map).
MARGIN = 10
_PAD, _SWATCH_W, _SWATCH_H, _GAP, _SPACING = 9, 12, 9, 4, 10
#: Another tool's tile: the swatch is white, its dots the item (the map
#: draws such a tile in its state's colour, dotted).
_OTHER_TOOL = "#FFFFFF"


def item_color(item: str) -> QColor | None:
    """The item's one colour (Mac ``MapKey.color``), the same on the
    Build and Fly views (#2031)."""
    if item == "placeholder":
        color = QColor(QTWORLD.PLACEHOLDER_COLOR)
        color.setAlphaF(QTWORLD.PLACEHOLDER_ALPHA)
        return color
    color = {
        "full": QTWORLD.FULL_COLOR, "mesh": QTWORLD.MESH_COLOR,
        "drape": QTWORLD.DRAPE_COLOR, "building": QTLEGEND.BUILDING_COLOR,
        "other_tool": _OTHER_TOOL, "stale": QTLEGEND.STALE_COLOR,
        "custom": QTLEGEND.CUSTOM_PATCH_COLOR,
    }.get(item)
    return None if color is None else QColor(color)


def _item_pen(item: str) -> QPen | None:
    """The swatch's pen: dashed for a stale tile, dotted for another
    tool's tile, thick for the custom-patch band."""
    color = item_color(item)
    if color is None:
        return None
    pen = QPen(color)
    pen.setWidthF({"custom": 3, "placeholder": 1}.get(item, 2))
    if item == "stale":
        pen.setDashPattern([2, 1])
    elif item == "other_tool":
        pen.setDashPattern([1, 1.5])
    return pen


def _fit_caps(widths: list, available: float) -> list:
    """Each word's width so the row fits ``available``: the short words
    keep theirs, the long ones share the rest equally (and truncate)."""
    caps = list(widths)
    if sum(widths) <= available:
        return caps
    remaining, left = max(available, 0.0), len(widths)
    for index in sorted(range(len(widths)), key=widths.__getitem__):
        share = remaining / left
        if widths[index] <= share:
            remaining -= widths[index]
            left -= 1
            continue
        for rest in range(len(widths)):
            if widths[rest] > share:
                caps[rest] = share
        break
    return caps


def paint_key(painter, viewport: QRectF, items: list) -> tuple:
    """The key pill at the viewport's bottom-right; returns ``(pill,
    hits)`` with ``hits`` each item's ``(QRectF, sentence)`` (an empty
    pill and no hits when there are no items)."""
    if not items:
        return QRectF(), []
    metrics = painter.fontMetrics()
    height = metrics.height() + 8
    words = [KEYTEXT.SHORT[item] for item in items]
    fixed = 2 * _PAD + len(items) * (_SWATCH_W + _GAP) + (len(items) - 1) * _SPACING
    # capped at MAX_WIDTH_FRACTION of the map, like the Mac: the words
    # truncate to fit and the pill never grows past it (RULINGS 2026-11-13f)
    limit = min(viewport.width() * KEYTEXT.MAX_WIDTH_FRACTION,
                viewport.width() - 2 * MARGIN)
    natural = [metrics.horizontalAdvance(w) for w in words]
    caps = _fit_caps(natural, limit - fixed)
    shown = [w if c >= n else metrics.elidedText(w, Qt.ElideRight, int(c))
             for w, c, n in zip(words, caps, natural, strict=True)]
    width = fixed + sum(metrics.horizontalAdvance(w) for w in shown)
    pill = QRectF(viewport.right() - width - MARGIN,
                  viewport.bottom() - height - MARGIN, width, height)
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(20, 22, 28, 175))
    painter.drawRoundedRect(pill, height / 2, height / 2)
    hits, x = [], pill.left() + _PAD
    for item, word in zip(items, shown, strict=True):
        text_w = metrics.horizontalAdvance(word)
        pen = _item_pen(item)
        if pen is not None:
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(x, pill.center().y() - _SWATCH_H / 2,
                                    _SWATCH_W, _SWATCH_H))
        painter.setPen(QColor(235, 238, 245, 220))
        painter.drawText(QRectF(x + _SWATCH_W + _GAP, pill.top(), text_w + 1, height),
                         Qt.AlignVCenter | Qt.AlignLeft, word)
        span = QRectF(x, pill.top(), _SWATCH_W + _GAP + text_w, height)
        hits.append((span, KEYTEXT.FULL[item]))
        x += _SWATCH_W + _GAP + text_w + _SPACING
    painter.restore()
    return pill, hits


def tooltip_at(hits: list, pos) -> str | None:
    """The full sentence of the item under ``pos`` (viewport space)."""
    for rect, sentence in hits:
        if rect.contains(pos):
            return sentence
    return None
