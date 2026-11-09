"""The Gateway airports question (issue #1989; Qt half).

The engine names every graded airport X-Plane flattens (its Global
Airports entry carries ``1302 flatten 1``) and every Gateway pack the app
installed that has a newer Gateway version in one
:class:`o4_engine.events.GatewayAirports` event; this module is the
question the Qt window asks for it: one checkbox per airport, every one
checked when it opens, each with its explanation.  **Install** sends
``gateway_airports`` with ``action="install"``, the checked ICAOs as
``items`` and every ICAO shown as ``shown``; **Never for these airports**
sends ``action="never"`` with ``shown``; **Not now** sends nothing.

The COPY is identical to the macOS sheet
(``Sources/SceneryKit/GatewayAirports.swift``); the twin
``tests/test_qt_gateway_airports.py`` pins both.  Non-modal: the event
arrives in the middle of a build and the build goes on.
"""

from __future__ import annotations

from O4_Qt_Choice_Dialog import ChoiceDialog
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

# --- copy (verbatim; identical to the Swift sheet) ----------------------
TITLE = "Install airports from the X-Plane Gateway?"
BODY = ("X-Plane flattens the ground under these airports, so it does not "
        "draw the graded ground this app builds. Choose the airports to "
        "install:")
REASON_DETAILS = {
    "flatten": "Install the latest Gateway version without the flatten tag.",
    "update": ("A newer Gateway version is available ({installed} → "
               "{latest}); it installs without the flatten tag."),
}
DETAIL = ("Each airport is installed as a custom airport pack in Custom "
          "Scenery and filed with your airports. Every build of its tile "
          "checks the Gateway for a newer version.")
INSTALL_BUTTON = "Install"
NOT_NOW_BUTTON = "Not now"
NEVER_BUTTON = "Never for these airports"


def offers(event) -> list[dict]:
    """The rows to offer: a flattened entry or a newer Gateway version."""
    return [r for r in (getattr(event, "items", None) or ())
            if r.get("reason") in REASON_DETAILS]


def _row_title(row) -> str:
    name = row.get("name") or ""
    return f"{row['icao']} {name}" if name else row["icao"]


def _row_detail(row) -> str:
    return REASON_DETAILS[row["reason"]].format(
        installed=int(row.get("installed_id", 0)),
        latest=int(row.get("latest_id", 0)))


def question_key(event) -> tuple:
    """One question per tile and airport set."""
    return (int(getattr(event, "lat", 0)), int(getattr(event, "lon", 0)),
            tuple((r.get("icao"), r.get("reason")) for r in offers(event)))


class _GatewayAirportsBox(ChoiceDialog):
    """The question: its words, one checkbox per airport, and Install /
    Never for these airports / Not now (``ChoiceDialog``'s message-box
    surface); :meth:`answer_extra` is what the answer sends besides the
    action."""

    def __init__(self, event, parent=None):
        super().__init__(TITLE, parent)
        lay = QVBoxLayout(self)
        heading = QLabel(TITLE)
        heading.setStyleSheet("font-weight: bold")
        lay.addWidget(heading)
        body = QLabel(BODY)
        body.setWordWrap(True)
        lay.addWidget(body)
        self.item_boxes: dict[str, QCheckBox] = {}
        for row in offers(event):
            box = QCheckBox(_row_title(row))
            box.setChecked(True)
            self.item_boxes[row["icao"]] = box
            detail = QLabel(_row_detail(row))
            detail.setWordWrap(True)
            detail.setContentsMargins(24, 0, 0, 6)
            lay.addWidget(box)
            lay.addWidget(detail)
        note = QLabel(DETAIL)
        note.setWordWrap(True)
        lay.addWidget(note)
        self._buttons = QDialogButtonBox(self)
        self.install = self._buttons.addButton(INSTALL_BUTTON,
                                               QDialogButtonBox.AcceptRole)
        self.never = self._buttons.addButton(NEVER_BUTTON,
                                             QDialogButtonBox.DestructiveRole)
        self.not_now = self._buttons.addButton(NOT_NOW_BUTTON,
                                               QDialogButtonBox.RejectRole)
        self.install.setDefault(True)
        self._buttons.clicked.connect(self._on_clicked)
        lay.addWidget(self._buttons)

    def answer_extra(self, action: str) -> dict:
        """The ``gateway_airports`` arguments besides the action: every
        airport shown, and for Install the ones left checked."""
        extra: dict = {"shown": list(self.item_boxes)}
        if action == "install":
            extra["items"] = [k for k, b in self.item_boxes.items()
                              if b.isChecked()]
        return extra


def gateway_airports_box(event, parent=None):
    """The question for one ``GatewayAirports(state="found")`` event.

    Returns ``(box, {action: button})``: ``"install"`` and ``"never"`` —
    the buttons that send ``gateway_airports``; Not now is the escape."""
    box = _GatewayAirportsBox(event, parent)
    return box, {"install": box.install, "never": box.never}
