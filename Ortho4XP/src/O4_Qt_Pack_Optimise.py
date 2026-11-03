"""The "Optimise pack" question for a heavy airport pack (issue #1707;
Qt half).

The engine's object stage names such a pack with a
:class:`o4_engine.events.PackOptimise` event; this module is the question
the Qt window asks for it.  **Optimise** sends the ``pack_optimise``
command with ``action="update"`` (the tile's DSF is rewritten without
its duplicate placements, the pristine file kept as its backup, the
recipe re-applied on every later write, and the pack remembered as
"update"), **Never for this pack** with ``action="never"``, **Not now**
sends nothing (the next build asks again).  The pack's row under Modified
airports carries Optimise and Undo optimise.

The COPY is identical to the macOS app's alert
(``Sources/SceneryKit/PackOptimise.swift``); the twin
``tests/test_qt_pack_optimise.py`` pins both.

Non-modal: the event arrives in the middle of a build and the build goes
on; the box never blocks the event loop.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

# --- copy (verbatim; identical to the Swift alert) ----------------------
TITLE = "Optimise “{pack}”?"
BODY = ("This airport’s objects draw {before} million triangles on this "
        "tile, enough to cost frame rate. {n} of its object placements "
        "repeat another on the same spot. Optimise removes them ({after} "
        "million triangles).")
DETAIL = ("The original scenery file is kept as a backup, and the "
          "optimisation is applied again whenever the app rewrites this "
          "pack. Undo is on the pack’s row under Modified airports.")
OPTIMISE_BUTTON = "Optimise"
NOT_NOW_BUTTON = "Not now"
NEVER_BUTTON = "Never for this pack"
OPTIMISE_HELP = ("Optimise pack: remove object placements that repeat "
                 "another on the same spot.")
UNDO_HELP = ("Undo optimise: put back this package’s original object "
             "placements.")


def _millions(count) -> str:
    """Triangles in millions, one decimal (``"275.5"``)."""
    return "%.1f" % (int(count or 0) / 1e6)


def _body_text(event) -> str:
    return BODY.format(before=_millions(getattr(event, "est_tris_before", 0)),
                       n=int(getattr(event, "dedupe", 0) or 0),
                       after=_millions(getattr(event, "est_tris_after", 0))
                       ) + "\n\n" + DETAIL


def question_key(event) -> tuple:
    """One question per pack, tile and count: every airport of a pack runs
    the check, and the second airport's event is the same news."""
    return (getattr(event, "pack_root", ""), int(getattr(event, "lat", 0)),
            int(getattr(event, "lon", 0)), int(getattr(event, "dedupe", 0) or 0))


def pack_optimise_box(event, parent=None):
    """The question for one ``PackOptimise(state="found")`` event.

    Returns ``(box, {action: button})``: ``"update"`` and ``"never"`` —
    the buttons that send ``pack_optimise``; Not now is the box's escape."""
    title = TITLE.format(pack=getattr(event, "pack", ""))
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(_body_text(event))
    box.setWindowModality(Qt.NonModal)
    optimise = box.addButton(OPTIMISE_BUTTON, QMessageBox.AcceptRole)
    never = box.addButton(NEVER_BUTTON, QMessageBox.DestructiveRole)
    not_now = box.addButton(NOT_NOW_BUTTON, QMessageBox.RejectRole)
    box.setDefaultButton(optimise)
    box.setEscapeButton(not_now)
    return box, {"update": optimise, "never": never}
