"""The step strip line of a Qt Activity row (issue #825).

One wrapping label under the row's bar: ``✓ Map data 0:42 → ● Airports ·
KSEA — shaping runways (65 %) → ○ Ground …``, each step in its state's
colour.  The words and states are ``O4_Step_Strip``'s (the mapping both
apps share); this module only paints them.  The Mac half is
``TileStepStrip`` in ``Sources/XPTerrainBuilder/TileProgressRowLines.swift``.
"""

import html

import O4_Qt_Map as QTMAP
import O4_Qt_Text_Scale as QTTEXT
import O4_Step_Strip as STRIP
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

__all__ = ["STATE_COLORS", "strip_html", "make_label", "show"]

#: Step state -> text colour (the row's own: green done, red failed,
#: orange stopped; the running step in the selection blue).
STATE_COLORS = {
    "waiting": "gray",
    "running": "#2A7AE2",
    "done": "green",
    "skipped": "gray",
    "failed": "red",
    "stopped": QTMAP.STOPPED_COLOR,
}


def strip_html(strip):
    """The strip as rich text: one coloured span per step, arrows between."""
    spans = [
        '<span style="color: %s;">%s</span>'
        % (STATE_COLORS[state], html.escape(text, quote=False))
        for state, text in STRIP.segments(strip)
    ]
    return '<span style="color: gray;">%s</span>' % (
        html.escape(STRIP.SEPARATOR, quote=False)).join(spans)


def make_label(pixels):
    """The empty, hidden strip label of a new row (object name
    ``tile_steps``)."""
    label = QLabel("")
    label.setObjectName("tile_steps")
    label.setTextFormat(Qt.RichText)
    label.setWordWrap(True)
    QTTEXT.size_text(label, pixels=pixels)
    label.setVisible(False)
    return label


def show(label, strip):
    """Paint ``strip`` into ``label``; hidden while there is none."""
    if strip is None:
        label.setText("")
        label.setVisible(False)
        return
    label.setText(strip_html(strip))
    label.setToolTip(STRIP.strip_text(strip).replace(STRIP.NBSP, " "))
    label.setVisible(True)
