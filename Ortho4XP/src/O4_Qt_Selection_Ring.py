"""The map's tile selection focus ring (issue #1537).

A ring, not a fill: a fill tints the very imagery the user is judging.
The active tile: a solid ring with a soft outer glow; other selected
tiles: dashed.  The colour is the
palette's highlight, so it follows the desktop's selection colour (the
Mac app: the system accent colour, ``TileSelectionRing.swift``).  The
Activity rows of selected tiles are filled instead
(``O4_Qt_Click_Row.fill_color``).
"""

from PySide6.QtGui import QColor, QPalette, QPen

__all__ = ["ring_color", "draw"]


def ring_color(palette):
    """The ring's colour: the palette's highlight (selection) colour."""
    return QColor(palette.color(QPalette.Highlight))


def draw(painter, rect, active, color, px1=1.0):
    """Stroke the ring on ``rect`` (a QRectF).  ``px1`` is one screen
    pixel in the painter's units (``1 / scale`` on the zoomed map); the
    pens are cosmetic, so widths are screen pixels at any zoom."""
    if active:
        glow = QColor(color)
        glow.setAlphaF(0.35)
        pen = QPen(glow)
        pen.setCosmetic(True)
        pen.setWidth(5)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(-1.5 * px1, -1.5 * px1,
                                       1.5 * px1, 1.5 * px1))
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidthF(2.5)
    else:
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidth(2)
        pen.setDashPattern([5 / 2, 4 / 2])  # 5 px on, 4 off at width 2
    painter.setPen(pen)
    painter.drawRect(rect.adjusted(px1, px1, -px1, -px1))

