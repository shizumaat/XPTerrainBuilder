"""The tile selection's focus ring, one definition for the map and the
Activity list (issue #1537).

The map draws it on its selected tiles; an Activity row whose tile is
selected draws it around itself.  A ring, not a fill: a fill tints the
very imagery the user is judging.  The active tile: a solid ring with a
soft outer glow; other selected tiles: dashed.  The colour is the
palette's highlight, so it follows the desktop's selection colour (the
Mac app: the system accent colour, ``TileSelectionRing.swift``).

:func:`ringed_rows` is the rule for which rows ring -- the twin of the Mac
app's ``SelectionRing.rings``; both read
``tests/fixtures/selection_ring_cases.json``.
"""

from PySide6.QtGui import QColor, QPalette, QPen

__all__ = ["ACTIVE", "OTHER", "ringed_rows", "ring_color", "draw",
           "apply_rings"]

#: The two ring styles: solid with a glow, and dashed.
ACTIVE = "active"
OTHER = "other"


def ringed_rows(rows, selected, active):
    """The ring each Activity row draws, keyed by the rows that draw one.

    A row rings when its tile is selected -- unless the selection holds
    every row's tile, or none of them: a list lit up wholesale tells the
    user nothing.  The active tile's row is :data:`ACTIVE`, the others
    :data:`OTHER`."""
    every = set(rows)
    hit = every & set(selected)
    if not hit or hit == every:
        return {}
    return {key: (ACTIVE if key == active else OTHER) for key in hit}


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


def apply_rings(rows, selected, active):
    """Set each Activity row's ring from the selection.  ``rows`` maps a
    tile to its row widget (anything with ``set_ring``)."""
    rings = ringed_rows(list(rows), selected, active)
    for tile, row in rows.items():
        row.set_ring(rings.get(tile))
