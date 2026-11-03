"""The "Optimise pack" question for a heavy airport pack (issue #1707;
Qt half).

The engine's object stage names such a pack with a
:class:`o4_engine.events.PackOptimise` event; this module is the question
the Qt window asks for it.  **Optimise** sends the ``pack_optimise``
command with ``action="update"`` (the tile's DSF is rewritten without
its duplicate placements and with its heavy vehicles swapped for
X-Plane's library ones, the pristine file kept as its backup, the
recipe re-applied on every later write, and the pack remembered as
"update"), **Never for this pack** with ``action="never"``, **Not now**
sends nothing (the next build asks again).  The pack's row under Modified
airports carries Optimise and Undo optimise.

The COPY is identical to the macOS app's alert
(``Sources/SceneryKit/PackOptimise.swift``); the twin
``tests/test_qt_pack_optimise.py`` pins both.

THE STEPS (owner 2026-11-03: "present the user with the options, all
defaulted on with an explanation and estimated impact, but provide check
boxes so they can choose to disable some"): one checkbox per step the
engine says has work on this pack (``PackOptimise.steps``), checked as
the pack's last choice was (``chosen``; every step at first), each with
its one-line explanation and estimate; Optimise sends the checked ones
and is disabled with none checked.

Non-modal: the event arrives in the middle of a build and the build goes
on; the box never blocks the event loop.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

# --- copy (verbatim; identical to the Swift alert) ----------------------
TITLE = "Optimise “{pack}”?"
BODY = ("This airport’s objects draw {before} million triangles on this "
        "tile, enough to cost frame rate. {n} of its object placements "
        "repeat another on the same spot. Optimise removes them ({after} "
        "million triangles).")
BODY_SWAPPED = ("This airport’s objects draw {before} million triangles on "
                "this tile, enough to cost frame rate. Optimise removes the "
                "{n} object placements that repeat another on the same spot "
                "and swaps {s} heavy vehicles and ground equipment for "
                "X-Plane’s lighter library ones ({after} million triangles).")
DETAIL = ("The original scenery file is kept as a backup, and the "
          "optimisation is applied again whenever the app rewrites this "
          "pack. Undo is on the pack’s row under Modified airports.")
#: the question when the engine lists the steps (``PackOptimise.steps``)
BODY_STEPS = ("This airport’s objects draw {before} million triangles on "
              "this tile, enough to cost frame rate. Choose what Optimise "
              "does:")
#: per step: its checkbox and its explanation with the estimate
STEP_TITLES = {
    "dedupe": "Remove repeated placements",
    "swap": "Use X-Plane’s library vehicles",
    "objects": "Draw small props only nearby",
    "textures": "Compress large textures",
}
STEP_DETAILS = {
    "dedupe": ("{n} objects are placed twice on the same spot "
               "(−{tris} million triangles)."),
    "swap": ("{n} heavy cars and ground equipment become X-Plane’s lighter "
             "models (−{tris} million triangles up close)."),
    "objects": ("{n} props get a draw distance of up to 1.5 km and can be "
                "drawn in batches (−{tris} million triangles past 1.5 km)."),
    "textures": ("{n} textures are compressed or halved (about −{mb} MB of "
                 "video memory)."),
}
OPTIMISE_BUTTON = "Optimise"
NOT_NOW_BUTTON = "Not now"
NEVER_BUTTON = "Never for this pack"
OPTIMISE_HELP = ("Optimise pack: remove object placements that repeat "
                 "another on the same spot, and swap heavy vehicles for "
                 "X-Plane’s lighter library ones.")
UNDO_HELP = ("Undo optimise: put back this package’s original object "
             "placements.")


def _millions(count) -> str:
    """Triangles in millions, one decimal (``"275.5"``)."""
    return "%.1f" % (int(count or 0) / 1e6)


def _body_text(event) -> str:
    if getattr(event, "steps", None):
        return BODY_STEPS.format(
            before=_millions(getattr(event, "est_tris_before", 0)))
    swapped = int(getattr(event, "swapped", 0) or 0)
    return (BODY_SWAPPED if swapped > 0 else BODY).format(
        before=_millions(getattr(event, "est_tris_before", 0)),
        n=int(getattr(event, "dedupe", 0) or 0), s=swapped,
        after=_millions(getattr(event, "est_tris_after", 0))) + "\n\n" + DETAIL


def _step_detail(row) -> str:
    """One step's explanation and estimate (``PackOptimise.steps`` row)."""
    return STEP_DETAILS[row["key"]].format(
        n=int(row.get("count", 0)), tris=_millions(row.get("tris", 0)),
        mb="%.0f" % float(row.get("mb", 0.0)))


def question_key(event) -> tuple:
    """One question per pack, tile and count: every airport of a pack runs
    the check, and the second airport's event is the same news."""
    return (getattr(event, "pack_root", ""), int(getattr(event, "lat", 0)),
            int(getattr(event, "lon", 0)), int(getattr(event, "dedupe", 0) or 0),
            int(getattr(event, "swapped", 0) or 0))


class _PackOptimiseBox(QDialog):
    """The question: its words, one checkbox per step, and Optimise /
    Never for this pack / Not now.  Answers like a ``QMessageBox``
    (``clickedButton``, ``finished``) so the window's per-pack choice
    handler drives it; :meth:`checked_steps` are what Optimise sends."""

    def __init__(self, event, parent=None):
        super().__init__(parent)
        self._title = TITLE.format(pack=getattr(event, "pack", ""))
        self._text = _body_text(event)
        self._clicked = None
        self.setWindowTitle(self._title)
        self.setWindowModality(Qt.NonModal)
        lay = QVBoxLayout(self)
        heading = QLabel(self._title)
        heading.setStyleSheet("font-weight: bold")
        lay.addWidget(heading)
        body = QLabel(self._text)
        body.setWordWrap(True)
        lay.addWidget(body)
        chosen = set(getattr(event, "chosen", None) or ())
        self.step_boxes: dict[str, QCheckBox] = {}
        for row in getattr(event, "steps", None) or ():
            if row.get("key") not in STEP_TITLES:
                continue
            box = QCheckBox(STEP_TITLES[row["key"]])
            box.setChecked(not chosen or row["key"] in chosen)
            detail = QLabel(_step_detail(row))
            detail.setWordWrap(True)
            detail.setContentsMargins(24, 0, 0, 6)
            lay.addWidget(box)
            lay.addWidget(detail)
            self.step_boxes[row["key"]] = box
            box.toggled.connect(self._enable)
        if self.step_boxes:
            note = QLabel(DETAIL)
            note.setWordWrap(True)
            lay.addWidget(note)
        self._buttons = QDialogButtonBox(self)
        self.optimise = self._buttons.addButton(OPTIMISE_BUTTON,
                                                QDialogButtonBox.AcceptRole)
        self.never = self._buttons.addButton(NEVER_BUTTON,
                                             QDialogButtonBox.DestructiveRole)
        self.not_now = self._buttons.addButton(NOT_NOW_BUTTON,
                                               QDialogButtonBox.RejectRole)
        self.optimise.setDefault(True)
        self._buttons.clicked.connect(self._on_clicked)
        lay.addWidget(self._buttons)
        self._enable()

    def _enable(self, *_args) -> None:
        self.optimise.setEnabled(not self.step_boxes or any(
            b.isChecked() for b in self.step_boxes.values()))

    def _on_clicked(self, button) -> None:
        self._clicked = button
        if button is self.not_now:
            self.reject()
        else:
            self.accept()

    def reject(self) -> None:                       # Esc is Not now
        if self._clicked is None:
            self._clicked = self.not_now
        super().reject()

    # the QMessageBox surface the window's handler and the twins read
    def clickedButton(self):
        return self._clicked

    def buttons(self):
        return self._buttons.buttons()

    def text(self) -> str:
        return self._title

    def informativeText(self) -> str:
        return self._text

    def defaultButton(self):
        return self.optimise

    def escapeButton(self):
        return self.not_now

    def checked_steps(self) -> list[str]:
        """The steps checked, in the engine's order (``None``-free)."""
        return [k for k, b in self.step_boxes.items() if b.isChecked()]


def pack_optimise_box(event, parent=None):
    """The question for one ``PackOptimise(state="found")`` event.

    Returns ``(box, {action: button})``: ``"update"`` and ``"never"`` —
    the buttons that send ``pack_optimise``; Not now is the box's escape."""
    box = _PackOptimiseBox(event, parent)
    return box, {"update": box.optimise, "never": box.never}
