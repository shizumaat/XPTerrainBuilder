"""Width-tolerant Qt widgets shared by every Ortho4XP window.

ONE definition of the squeeze idiom, imported by the main window
(``O4_Qt_GUI``), the settings sheet (``O4_Qt_Settings``) and the
onboarding wizard (``O4_Qt_Wizard``) — never copied.

The problem these solve is the same in all three places: a plain Qt
widget reports its FULL TEXT WIDTH as its MINIMUM, so every label,
button and combo is a hard floor under its window, and that floor is
measured in the platform's font.  On the Windows CI runner the
offscreen font advances a digit at 12 px against 8 px on macOS, which
is also what a Windows user at 125 % display scaling sees: the settings
window's minimum came out 1228 px (unusable on a 1280 px laptop) and
the wizard preferred 864 px.  Nothing here changes what is DRAWN where
there is room — only what happens when there is not.

* :class:`ElidedRowLabel` — one line, hint = full text, minimum = one
  ellipsis, tail elision, full text in the tooltip.
* :class:`SqueezableLineEdit` — keeps a preferred width (so the form
  looks exactly as it did) but may shrink to a small floor.
* :func:`may_be_squeezed` — a combo stops demanding its widest item.
* :func:`never_widen` — Ignored horizontal policy: the widget accepts
  whatever is left instead of setting a floor.
* :func:`wrap_and_never_widen` — the same, for a rich-text paragraph
  that should re-wrap rather than push its dialog wider.
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QSizePolicy


class ElidedRowLabel(QLabel):
    """One-line label that PREFERS its full text but may be squeezed.

    A plain QLabel reports its whole text width as its MINIMUM, so every
    such label is a hard floor under the fixed-width side panel.  That
    floor is measured in the platform's font: on the Windows CI runner
    the offscreen font's glyphs are 1.5x the mac's, the panel's minimum
    came out 452 px against its 266 px viewport, and the panel clipped
    silently (its horizontal scrollbar is off by design — beta plan §1
    B4).  Here the size HINT still carries the full text, so wherever
    the row has room nothing changes; only a squeezed row elides the
    label (tail elision, full text in the tooltip) instead of widening
    its panel.

    Height never depends on width — no word wrap — so this cannot start
    the scroll-area relayout oscillation TwoLineElidedLabel documents.
    ``text()`` answers the FULL text, not what is painted.
    """

    #: Squeezed-out floor, in ellipsis widths: enough that a fully
    #: squeezed label still shows it EXISTS, small enough that a form
    #: full of them cannot add up past the panel.
    MIN_CHARS = 1

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.PlainText)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._full_text = ""
        self.setText(text)

    def text(self):
        return self._full_text

    def setText(self, text):
        self._full_text = str(text or "")
        self._apply_elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange:
            self.updateGeometry()
            self._apply_elide()

    def _margin_width(self):
        margins = self.contentsMargins()
        return margins.left() + margins.right() + 2 * self.margin()

    def sizeHint(self):
        # Computed from the FULL text: painting an elided string must
        # never shrink the hint (that would ratchet the label down and
        # never let it back).
        hint = super().sizeHint()
        hint.setWidth(
            self.fontMetrics().horizontalAdvance(self._full_text)
            + self._margin_width()
        )
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(
            self.fontMetrics().horizontalAdvance("…" * self.MIN_CHARS)
            + self._margin_width()
        )
        return hint

    def _apply_elide(self):
        width = self.contentsRect().width()
        if width <= 0:  # not laid out yet: nothing to elide against
            display = self._full_text
        else:
            display = self.fontMetrics().elidedText(
                self._full_text, Qt.ElideRight, width
            )
        if display != QLabel.text(self):
            QLabel.setText(self, display)
        elided = display != self._full_text
        # A tooltip the CALLER set (the row's own explanation) outranks
        # the full-text fallback and is never overwritten.
        if self.toolTip() in ("", self._full_text):
            self.setToolTip(self._full_text if elided else "")


class SqueezableLineEdit(QLineEdit):
    """Line edit with a PREFERRED width instead of a fixed one.

    ``setFixedWidth(280)`` is what the settings sheet used for its path
    fields: font-independent, but an absolute floor — with the row
    label, the browse button and the revert button beside it, twelve
    such rows put the window's minimum past a laptop screen once the
    platform font grew.  Preferring the same width leaves every form
    pixel-identical wherever the window has room, and lets the field
    give way first when it has not.
    """

    #: Enough to read a few characters and to aim a cursor at.
    MIN_WIDTH = 56

    def __init__(self, preferred_width, parent=None):
        super().__init__(parent)
        self._preferred_width = int(preferred_width)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(self._preferred_width)
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(min(self.MIN_WIDTH, self._preferred_width))
        return hint


def may_be_squeezed(combo, chars=4):
    """Stop *combo* demanding room for its widest item.

    QComboBox reports the same width as its minimum and its hint (the
    widest item, by default), which in the fixed-width side panel is a
    floor that grows with the platform's font.  These combos always fill
    the width their row has left over (stretch 1), so a small minimum
    changes nothing that is drawn — it only lets the row shrink.
    """
    combo.setSizeAdjustPolicy(
        QComboBox.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(chars)


def never_widen(widget):
    """Let *widget* clip rather than widen the fixed-width side panel.

    The panel is 280 px with its horizontal scrollbar off, so a child
    that demands more width clips SILENTLY — and a push button neither
    wraps nor elides its label.  Ignored horizontal policy is the same
    answer the Activity title already uses; the tooltip carries the full
    text.
    """
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Ignored)
    widget.setSizePolicy(policy)


def wrap_and_never_widen(label, tooltip=None):
    """A paragraph label that RE-WRAPS instead of widening its dialog.

    Word wrap alone is not enough: a QLabel's minimum still covers its
    longest unbreakable run, which for the wizard's X-Plane rejection
    reason is a whole filesystem path (771 px on macOS, ~1150 px on the
    Windows runner).  With Ignored horizontal policy the paragraph takes
    whatever width the dialog has and wraps into it; the tooltip keeps
    the full text readable when a path still overruns.
    """
    label.setWordWrap(True)
    never_widen(label)
    if tooltip is not None:
        label.setToolTip(tooltip)
    return label
