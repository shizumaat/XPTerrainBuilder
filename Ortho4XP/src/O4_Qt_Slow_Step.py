"""The slow-step alert (issue #1351; Qt half).

The engine names a slow step of one tile with a
:class:`o4_engine.events.SlowStep` event and writes every word of it —
title, message (what, why, ETA) and one button per answer the step
supports.  This module is the box the Qt window shows for it: NON-MODAL
(the build goes on), its words replaced in place when a later event of
the same tile and step refreshes the ETA, closed when the step resolves.
"Cancel this tile" is the row's own per-tile stop; the other answers go
back through ``slow_step_choice``.

The macOS app shows the same event as a banner at the top of the Build
pane (``Sources/XPTerrainBuilder/SlowStepBanner.swift``); neither app
holds copy of its own.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

__all__ = ["alert_key", "slow_step_box", "update_slow_step_box"]

#: The box's button role for each answer: Escape continues.
_ROLES = {"continue": QMessageBox.RejectRole,
          "coarser": QMessageBox.AcceptRole,
          "cancel": QMessageBox.DestructiveRole}


def alert_key(event) -> tuple:
    """One alert per tile and step."""
    return (int(getattr(event, "lat", 0)), int(getattr(event, "lon", 0)),
            str(getattr(event, "step_key", "")))


def update_slow_step_box(box, event) -> None:
    """A refreshed alert: the engine's new words, in place."""
    box.setWindowTitle(event.title)
    box.setText(event.title)
    box.setInformativeText(event.message)


def slow_step_box(event, parent=None):
    """The box for one ``SlowStep`` event.

    Returns ``(box, {choice: button})`` in the engine's option order."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowModality(Qt.NonModal)
    update_slow_step_box(box, event)
    options = list(getattr(event, "options", ()) or ())
    labels = list(getattr(event, "option_labels", ()) or ())
    buttons = {}
    for index, choice in enumerate(options):
        label = labels[index] if index < len(labels) else choice
        buttons[choice] = box.addButton(
            label, _ROLES.get(choice, QMessageBox.ActionRole))
    if "continue" in buttons:
        box.setDefaultButton(buttons["continue"])
        box.setEscapeButton(buttons["continue"])
    return box, buttons
