"""The "3D trees" question for an airport pack with old flat (X-Plane 11)
forests (issue #1360; Qt half).

The engine's object stage names such a pack with a
:class:`o4_engine.events.PackOldForests` event; this module is the
question the Qt window asks for it.  **Update** sends the
``pack_forests`` command with ``action="update"`` (the tile's DSF is
rewritten to the X-Plane 12 3D trees, the pristine file kept as its
backup, and the pack remembered as "update"), **Never for this pack**
with ``action="never"``, **Not now** sends nothing (the next build asks
again).  Undo is the pack row's tree button under Modified airports.

The COPY is identical to the macOS app's alert
(``Sources/SceneryKit/PackOldForests.swift``); the twin
``tests/test_qt_pack_forests.py`` pins both.

Non-modal: the event arrives in the middle of a build and the build goes
on; the box never blocks the event loop.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

# --- copy (verbatim; identical to the Swift alert) ----------------------
TITLE = "3D trees for “{pack}”"
BODY = ("This airport’s scenery uses {n} old flat (X-Plane 11) tree "
        "resources. Switch them to the X-Plane 12 3D trees?")
DETAIL = ("The original scenery file is kept as a backup. "
          "Undo is on the pack’s row under Modified airports.")
UNMAPPED = ("{n} other flat tree resource(s) have no X-Plane 12 3D "
            "equivalent and stay as they are (first: {path}).")
UPDATE_BUTTON = "Update"
NOT_NOW_BUTTON = "Not now"
NEVER_BUTTON = "Never for this pack"
UNDO_HELP = ("Undo 3D trees: put back this package’s "
             "original flat (X-Plane 11) tree resources.")


def body_text(event) -> str:
    text = BODY.format(n=int(getattr(event, "mapped", 0) or 0)) + "\n\n" + DETAIL
    unmapped = int(getattr(event, "unmapped", 0) or 0)
    if unmapped:
        paths = list(getattr(event, "first_unmapped", None) or [])
        text += "\n\n" + UNMAPPED.format(n=unmapped,
                                         path=paths[0] if paths else "")
    return text


def question_key(event) -> tuple:
    """One question per pack, tile and set: every airport of a pack runs
    the check, and the second airport's event is the same news."""
    return (getattr(event, "pack_root", ""), int(getattr(event, "lat", 0)),
            int(getattr(event, "lon", 0)),
            tuple(getattr(event, "first_paths", None) or ()),
            int(getattr(event, "mapped", 0) or 0))


def pack_forests_box(event, parent=None):
    """The question for one ``PackOldForests(state="found")`` event.

    Returns ``(box, {action: button})``: ``"update"`` and ``"never"`` —
    the buttons that send ``pack_forests``; Not now is the box's escape."""
    title = TITLE.format(pack=getattr(event, "pack", ""))
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body_text(event))
    box.setWindowModality(Qt.NonModal)
    update = box.addButton(UPDATE_BUTTON, QMessageBox.AcceptRole)
    never = box.addButton(NEVER_BUTTON, QMessageBox.DestructiveRole)
    not_now = box.addButton(NOT_NOW_BUTTON, QMessageBox.RejectRole)
    box.setDefaultButton(update)
    box.setEscapeButton(not_now)
    return box, {"update": update, "never": never}
