"""The "X-Plane will not load this pack" warning (owner RULINGS
2026-10-06c, issue #433; Qt half).

X-Plane skips a WHOLE scenery pack when its DSF declares one definition
whose file is not installed.  The engine's object stage names such a pack
with a :class:`o4_engine.events.PackMissingArt` event; this module is the
warning the Qt window shows for it, and the offer: the primary button
sends the ``omit_missing_art`` command, which writes the pack's DSF
without the missing definitions (the pristine file is kept as its
backup).

The COPY is owner-fixed and identical to the macOS app's alert
(``Sources/XPTerrainBuilder/PackMissingArtAlert.swift``); the twin
``tests/test_qt_pack_art.py`` pins both.  A missing TERRAIN definition
cannot be omitted (its patches are the mesh): the event's ``can_omit`` is
false and the warning is shown WITHOUT the primary button and without
the backup line, which only describes the omission.

Non-modal: the event arrives in the middle of a build and the build goes
on; the box never blocks the event loop.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

# --- copy (verbatim; identical to the Swift alert) ----------------------
TITLE = "X-Plane will not load “{pack}”"
BODY = ("Its scenery file refers to {n} file(s) that are not installed "
        "(first: {path}). X-Plane skips a scenery pack entirely when any "
        "file it refers to is missing, so this airport’s buildings "
        "and ground would not appear in the simulator.")
PRIMARY_BUTTON = "Build without the missing items"
SECONDARY_BUTTON = "Leave the pack as it is"
DETAIL = "The original scenery file is kept as a backup and can be restored."


def title_text(event) -> str:
    return TITLE.format(pack=getattr(event, "pack", ""))


def body_text(event) -> str:
    paths = list(getattr(event, "first_paths", None) or [])
    return BODY.format(n=int(getattr(event, "total", 0) or 0),
                       path=paths[0] if paths else "")


def warning_key(event) -> tuple:
    """One warning per pack, tile and missing set: every airport of a pack
    runs the check, and the second airport's event is the same news."""
    return (getattr(event, "pack_root", ""), int(getattr(event, "lat", 0)),
            int(getattr(event, "lon", 0)),
            tuple(getattr(event, "first_paths", None) or ()),
            int(getattr(event, "total", 0) or 0))


def pack_art_box(event, parent=None):
    """The warning for one ``PackMissingArt(state="found")`` event.

    Returns ``(box, primary)``; ``primary`` is ``None`` when the event
    cannot be omitted (``can_omit`` false)."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title_text(event))
    box.setText(title_text(event))
    box.setWindowModality(Qt.NonModal)
    primary = None
    informative = body_text(event)
    if getattr(event, "can_omit", False):
        primary = box.addButton(PRIMARY_BUTTON, QMessageBox.AcceptRole)
        informative += "\n\n" + DETAIL
    box.setInformativeText(informative)
    secondary = box.addButton(SECONDARY_BUTTON, QMessageBox.RejectRole)
    box.setDefaultButton(secondary)
    box.setEscapeButton(secondary)
    return box, primary
