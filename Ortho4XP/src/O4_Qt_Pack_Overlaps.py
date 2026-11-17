"""The "same structures in two packs" question (issue #2145; Qt half).

The engine names every pair of installed packs that draw the same large
structures near an airport in one :class:`o4_engine.events.PackOverlaps`
event; this module is the question the Qt window asks for it: per pair,
its summary and a picker — either pack, or "Keep both" — set to the
remembered answer, else the airport pack (owner 2026-11-17T19:15Z
"Default would be to prefer the airport pack").  **Apply** sends
``pack_overlaps`` with ``action="choose"`` and ``items`` ``[{"key",
"winner"}]``; **Not now** sends nothing.

The COPY is identical to the macOS sheet
(``Sources/SceneryKit/PackOverlaps.swift``); the twin
``tests/test_qt_pack_overlaps.py`` pins both.  Non-modal: the event
arrives after a build and the next one goes on.
"""

from __future__ import annotations

from O4_Qt_Choice_Dialog import ChoiceDialog
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

# --- copy (verbatim; identical to the Swift sheet) ----------------------
TITLE = "Two packs draw the same structures"
BODY = ("These packs both draw large structures in the same place near the "
        "airport. Choose the pack to keep for each pair; the other pack's "
        "copies are hidden, and the one you keep is fitted to the terrain.")
KEEP_BOTH = "Keep both"
KEEP_PREFIX = "Keep "
DETAIL = ("Only this app's rewrite of the pack's tile changes; Restore "
          "originals on the pack puts everything back.")
APPLY_BUTTON = "Apply"
NOT_NOW_BUTTON = "Not now"
BOTH = "both"


def offers(event) -> list[dict]:
    """The pairs to offer: two packs and a summary each."""
    return [r for r in (getattr(event, "items", None) or ())
            if len(r.get("packs") or ()) == 2 and r.get("key")]


def _choices(row) -> list[tuple[str, str]]:
    """The picker's ``(label, winner)`` entries: each pack, then both."""
    return [(KEEP_PREFIX + p, p) for p in row["packs"]] + [(KEEP_BOTH, BOTH)]


def _preselected(row) -> str:
    """The remembered answer, else the airport pack."""
    return row.get("winner") or row.get("default") or row["packs"][0]


def question_key(event) -> tuple:
    """One question per tile and pair set."""
    return (int(getattr(event, "lat", 0)), int(getattr(event, "lon", 0)),
            tuple(r["key"] for r in offers(event)))


class _PackOverlapsBox(ChoiceDialog):
    """The question: its words, one picker per pair, and Apply / Not now
    (``ChoiceDialog``'s message-box surface); :meth:`answer_extra` is what
    Apply sends besides the action."""

    def __init__(self, event, parent=None):
        super().__init__(TITLE, parent)
        lay = QVBoxLayout(self)
        heading = QLabel(TITLE)
        heading.setStyleSheet("font-weight: bold")
        lay.addWidget(heading)
        body = QLabel(BODY)
        body.setWordWrap(True)
        lay.addWidget(body)
        self.pickers: dict[str, QComboBox] = {}
        for row in offers(event):
            summary = QLabel(row.get("summary") or " / ".join(row["packs"]))
            summary.setWordWrap(True)
            pick = QComboBox()
            for label, winner in _choices(row):
                pick.addItem(label, winner)
            pick.setCurrentIndex(max(0, pick.findData(_preselected(row))))
            self.pickers[row["key"]] = pick
            lay.addWidget(summary)
            lay.addWidget(pick)
        note = QLabel(DETAIL)
        note.setWordWrap(True)
        lay.addWidget(note)
        self._buttons = QDialogButtonBox(self)
        self.apply = self._buttons.addButton(APPLY_BUTTON,
                                             QDialogButtonBox.AcceptRole)
        self.not_now = self._buttons.addButton(NOT_NOW_BUTTON,
                                               QDialogButtonBox.RejectRole)
        self.apply.setDefault(True)
        self._buttons.clicked.connect(self._on_clicked)
        lay.addWidget(self._buttons)

    def answer_extra(self, action: str) -> dict:
        """The ``pack_overlaps`` arguments besides the action: each pair's
        picked winner."""
        return {"items": [{"key": k, "winner": p.currentData()}
                          for k, p in self.pickers.items()]}


def pack_overlaps_box(event, parent=None):
    """The question for one ``PackOverlaps(state="found")`` event.

    Returns ``(box, {action: button})``: ``"choose"`` — the button that
    sends ``pack_overlaps``; Not now is the escape."""
    box = _PackOverlapsBox(event, parent)
    return box, {"choose": box.apply}
