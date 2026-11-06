"""The package adjustments question for an airport pack the app modifies
(issue #1916; Qt half).

The engine's object stage names every adjustment that applies to such a
pack in one :class:`o4_engine.events.PackAdjust` event; this module is the
question the Qt window asks for it: one checkbox per row the user chooses
(``trees``, ``drapes``), every one checked when it opens, each with its
explanation, and the automatic rows (``flatten``: the apt.dat's flatten
flag, removed with no question) listed without a checkbox.  **Apply**
sends ``pack_adjust`` with ``action="update"``, the checked rows as
``items`` and every row shown as ``shown``; **Never for this pack** sends
``action="never"`` with ``shown``; **Not now** sends nothing.

The COPY is identical to the macOS sheet
(``Sources/SceneryKit/PackAdjust.swift``); the twin
``tests/test_qt_pack_adjust.py`` pins both.  Non-modal: the event arrives
in the middle of a build and the build goes on.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from O4_Qt_Choice_Dialog import ChoiceDialog

# --- copy (verbatim; identical to the Swift sheet) ----------------------
TITLE = "Adjust “{pack}”?"
BODY = ("The app is modifying this airport package. These changes help it "
        "fit your scenery. Choose what to apply:")
ITEM_TITLES = {
    "trees": "Update trees",
    "drapes": "Hide draped orthophotos included with the package",
    "flatten": "Remove the airport’s flatten flag (always)",
}
ITEM_DETAILS = {
    "trees": ("{n} old flat (X-Plane 11) tree resources become X-Plane 12 "
              "3D trees."),
    "drapes": ("{n} photo images ({uses} polygons) laid over the airport "
               "cover the tile’s imagery."),
    "flatten": ("The apt.dat asks X-Plane to flatten the airport, which "
                "does not work with this app’s terrain mesh."),
}
DETAIL = ("The original files are kept as backups. Undo is Restore "
          "originals on the pack’s row under Modified airports.")
APPLY_BUTTON = "Apply"
NOT_NOW_BUTTON = "Not now"
NEVER_BUTTON = "Never for this pack"


def _rows(event) -> list[dict]:
    return [r for r in (getattr(event, "items", None) or ())
            if r.get("key") in ITEM_TITLES]


def _detail(row) -> str:
    return ITEM_DETAILS[row["key"]].format(n=int(row.get("count", 0)),
                                           uses=int(row.get("uses", 0)))


def question_key(event) -> tuple:
    """One question per pack, tile and row set."""
    return (getattr(event, "pack_root", ""), int(getattr(event, "lat", 0)),
            int(getattr(event, "lon", 0)),
            tuple(r.get("key") for r in _rows(event)))


def has_choice(event) -> bool:
    """Whether the event names a row the user chooses."""
    return any(not r.get("automatic") for r in _rows(event))


class _PackAdjustBox(ChoiceDialog):
    """The question: its words, one checkbox per choice, the automatic
    rows, and Apply / Never for this pack / Not now.  Answers like a
    ``QMessageBox`` (``clickedButton``, ``finished``) so the window's
    per-pack choice handler drives it; :meth:`answer_extra` is what the
    answer sends besides the action."""

    def __init__(self, event, parent=None):
        super().__init__(TITLE.format(pack=getattr(event, "pack", "")), parent)
        lay = QVBoxLayout(self)
        heading = QLabel(self._title)
        heading.setStyleSheet("font-weight: bold")
        lay.addWidget(heading)
        body = QLabel(BODY)
        body.setWordWrap(True)
        lay.addWidget(body)
        self.item_boxes: dict[str, QCheckBox] = {}
        self.automatic: list[str] = []
        rows = _rows(event)
        for row in sorted(rows, key=lambda r: bool(r.get("automatic"))):
            if row.get("automatic"):
                head = QLabel("✓ " + ITEM_TITLES[row["key"]])
                self.automatic.append(row["key"])
            else:
                head = QCheckBox(ITEM_TITLES[row["key"]])
                head.setChecked(True)
                self.item_boxes[row["key"]] = head
            detail = QLabel(_detail(row))
            detail.setWordWrap(True)
            detail.setContentsMargins(24, 0, 0, 6)
            lay.addWidget(head)
            lay.addWidget(detail)
        note = QLabel(DETAIL)
        note.setWordWrap(True)
        lay.addWidget(note)
        self._buttons = QDialogButtonBox(self)
        self.apply = self._buttons.addButton(APPLY_BUTTON,
                                             QDialogButtonBox.AcceptRole)
        self.never = self._buttons.addButton(NEVER_BUTTON,
                                             QDialogButtonBox.DestructiveRole)
        self.not_now = self._buttons.addButton(NOT_NOW_BUTTON,
                                               QDialogButtonBox.RejectRole)
        self.apply.setDefault(True)
        self._buttons.clicked.connect(self._on_clicked)
        lay.addWidget(self._buttons)

    def checked_items(self) -> list[str]:
        """The rows left checked, in the engine's order."""
        return [k for k, b in self.item_boxes.items() if b.isChecked()]

    def answer_extra(self, action: str) -> dict:
        """The ``pack_adjust`` arguments besides the action: every row
        shown, and for Apply the rows left checked."""
        extra: dict = {"shown": list(self.item_boxes)}
        if action == "update":
            extra["items"] = self.checked_items()
        return extra


def pack_adjust_box(event, parent=None):
    """The question for one ``PackAdjust(state="found")`` event.

    Returns ``(box, {action: button})``: ``"update"`` and ``"never"`` —
    the buttons that send ``pack_adjust``; Not now is the box's escape."""
    box = _PackAdjustBox(event, parent)
    return box, {"update": box.apply, "never": box.never}
