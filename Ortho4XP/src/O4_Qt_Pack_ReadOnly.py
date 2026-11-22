"""The question for a READ-ONLY airport pack (issue #2174, RULINGS
2026-11-19d; Qt half).

The engine's object stage names a pack whose folders are read-only (as it
was downloaded) with a :class:`o4_engine.events.PackReadOnly` event, and
that pack's writes wait for the answer.  **Make writable** sends the
``pack_readonly`` command with ``action="writable"`` (the engine adds the
owner's write permission to the pack's folders and files; the build's
writes go on), **Not now** with ``action="not_now"`` (the pack is left as
it is; the tile's row under Modified airports reads "read-only — not
adjusted" with Ask again).

The COPY is identical to the macOS app's alert
(``Sources/SceneryKit/PackReadOnly.swift``); the twin
``tests/test_qt_pack_readonly.py`` pins both.  Non-modal: the box never
blocks the event loop.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QToolButton

__all__ = ["ASK_AGAIN_BUTTON", "ASK_AGAIN_HELP", "BODY", "DETAIL", "FOLDERS",
           "NOT_NOW_BUTTON", "ROW_STATUS", "TITLE", "WRITABLE_BUTTON",
           "REBUILD_LATER", "RUN_BUSY", "pack_readonly_box",
           "question_key", "row_widgets"]

# --- copy (verbatim; identical to the Swift alert) ----------------------
TITLE = "“{pack}” is read-only"
BODY = ("{pack} is read-only (as it was downloaded), so XPTerrainBuilder "
        "can't adjust it. Make it writable?")
DETAIL = ("Make writable adds your write permission to this package's "
          "folders and files only; its originals are kept as backups when "
          "it is adjusted.")
FOLDERS = "Read-only: {folders}"
WRITABLE_BUTTON = "Make writable"
NOT_NOW_BUTTON = "Not now"
ROW_STATUS = "read-only — not adjusted"
ASK_AGAIN_BUTTON = "Ask again"
ASK_AGAIN_HELP = ("This package is read-only, so it was not adjusted. "
                  "Ask again to make it writable.")
RUN_BUSY = "a run is building; rebuild it when the run finishes"
REBUILD_LATER = "Rebuild tile {tile} to adjust {pack} now that it is writable: {reason}"


def _body_text(event) -> str:
    pack = getattr(event, "pack", "")
    text = BODY.format(pack=pack) + "\n\n" + DETAIL
    folders = list(getattr(event, "folders", None) or ())
    if folders:
        text += "\n\n" + FOLDERS.format(folders=", ".join(folders))
    return text


def question_key(event) -> str:
    """One question per pack: every tile and airport of it waits on the
    same answer."""
    return getattr(event, "pack_root", "")


def pack_readonly_box(event, parent=None):
    """The question for one ``PackReadOnly(state="found")`` event.

    Returns ``(box, {action: button})``: ``"writable"`` and ``"not_now"``
    — both send ``pack_readonly`` (the build waits on either)."""
    title = TITLE.format(pack=getattr(event, "pack", ""))
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(_body_text(event))
    box.setWindowModality(Qt.NonModal)
    writable = box.addButton(WRITABLE_BUTTON, QMessageBox.AcceptRole)
    not_now = box.addButton(NOT_NOW_BUTTON, QMessageBox.RejectRole)
    box.setDefaultButton(writable)
    box.setEscapeButton(not_now)
    return box, {"writable": writable, "not_now": not_now}


def row_widgets(ask) -> list:
    """A read-only pack's Modified airports row (the mac row's twin): its
    words and Ask again, which calls ``ask()``."""
    status = QLabel(ROW_STATUS)
    status.setEnabled(False)            # the secondary text colour
    again = QToolButton()
    again.setAutoRaise(True)
    again.setText(ASK_AGAIN_BUTTON)
    again.setFixedHeight(18)
    again.setToolTip(ASK_AGAIN_HELP)
    again.clicked.connect(lambda _checked=False: ask())
    return [status, again]
