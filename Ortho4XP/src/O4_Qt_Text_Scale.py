"""The Qt window's text size (issue #827): the View menu's Bigger Text /
Smaller Text / Actual Size actions and the one place a scale is applied.

The RULE (steps, clamping, the prefs key) is :mod:`O4_Text_Scale`, shared
with the macOS app.  Applying a scale sets the application font once --
every widget that inherits it follows -- and re-sizes the widgets that
carry a FIXED size of their own (the console's monospace font, the
Activity rows' small print, the patch panel's notes), which
:func:`size_text` registers.  The map's painted labels read
:func:`current_scale` when they paint.
"""

from typing import Callable, Dict, Optional

import O4_Text_Scale as TS
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

__all__ = ["current_scale", "base_points", "size_text", "apply_text_scale",
           "make_actions"]

# Dynamic properties: the application's Actual Size point size (recorded
# the first time a scale is applied), the scale in force, and a fixed-
# size widget's Actual Size points or pixels.
_BASE_PROP = "o4_text_base_points"
_SCALE_PROP = "o4_text_scale"
_POINTS_PROP = "o4_text_points"
_PIXELS_PROP = "o4_text_pixels"


def current_scale() -> float:
    """The scale in force (Actual Size before any is applied)."""
    app = QApplication.instance()
    value = app.property(_SCALE_PROP) if app is not None else None
    return TS.clamp(value) if value is not None else TS.DEFAULT


def base_points() -> float:
    """The application font's point size at Actual Size."""
    app = QApplication.instance()
    if app is None:
        return 13.0
    value = app.property(_BASE_PROP)
    if value is None:
        value = QApplication.font().pointSizeF()
        if not value > 0:
            value = 13.0
        app.setProperty(_BASE_PROP, float(value))
    return float(value)


def _resize(widget: QWidget, scale: float) -> None:
    points = widget.property(_POINTS_PROP)
    pixels = widget.property(_PIXELS_PROP)
    if points is None and pixels is None:
        return
    font = QFont(widget.font())
    if points is not None:
        font.setPointSizeF(TS.scaled(float(points), scale))
    else:
        font.setPixelSize(max(1, int(round(TS.scaled(float(pixels), scale)))))
    widget.setFont(font)


def size_text(widget: QWidget, points: Optional[float] = None,
              pixels: Optional[float] = None) -> QWidget:
    """Give ``widget`` a fixed text size -- ``points`` or ``pixels`` at
    Actual Size -- that follows the text scale; sized now at the scale
    in force.  Returns ``widget``."""
    if points is not None:
        widget.setProperty(_POINTS_PROP, float(points))
    elif pixels is not None:
        widget.setProperty(_PIXELS_PROP, float(pixels))
    _resize(widget, current_scale())
    return widget


def apply_text_scale(value) -> float:
    """Apply text scale ``value`` (clamped to a step) to the whole
    application; returns the scale applied."""
    scale = TS.clamp(value)
    app = QApplication.instance()
    if app is None:
        return scale
    base = base_points()
    app.setProperty(_SCALE_PROP, scale)
    font = QFont(QApplication.font())
    font.setPointSizeF(TS.scaled(base, scale))
    QApplication.setFont(font)
    for widget in QApplication.allWidgets():
        _resize(widget, scale)
    return scale


def make_actions(parent, on_change: Callable[[float], None]
                 ) -> Dict[str, QAction]:
    """View > Bigger Text (Ctrl+= / Ctrl++), Smaller Text (Ctrl+-) and
    Actual Size (Ctrl+0) -- the platform's zoom keys, Cmd on macOS.
    Each calls ``on_change`` with the new scale."""
    def action(title, shortcuts, step):
        act = QAction(title, parent)
        unique = {}
        for seq in shortcuts:  # the standard key may BE the explicit one
            if not seq.isEmpty():
                unique.setdefault(seq.toString(), seq)
        act.setShortcuts(list(unique.values()))
        act.triggered.connect(lambda _checked=False: on_change(step(current_scale())))
        return act

    return {
        "bigger": action(TS.BIGGER_TITLE,
                         [QKeySequence(QKeySequence.ZoomIn), QKeySequence("Ctrl+=")],
                         TS.bigger),
        "smaller": action(TS.SMALLER_TITLE,
                          [QKeySequence(QKeySequence.ZoomOut), QKeySequence("Ctrl+-")],
                          TS.smaller),
        "actual": action(TS.ACTUAL_TITLE, [QKeySequence("Ctrl+0")],
                         lambda _scale: TS.DEFAULT),
    }
