"""The package adjustments question for an airport pack the app modifies
(issue #1916; Qt half), and the pack row's "Adjust…" (owner
2026-11-15T13:12Z).

The engine's object stage names every adjustment that applies to such a
pack in one :class:`o4_engine.events.PackAdjust` event; this module is the
question the Qt window asks for it: one checkbox per row the user chooses
(``trees``, ``drapes``, ``ground``, ``terrain``, ``generic`` — the stock
X-Plane ground any overlay pack drapes over the tile, #2085, with its
hectares), each ticked when it opens as the row's ``checked`` says (the
engine's ``adjust_stage.UNCHECKED``: only ``ground``, the large ground
textures of #1962, opens unticked — RULINGS 2026-11-09a (3); ``terrain``
opens ticked since owner 2026-11-15T13:12Z), each with its explanation,
and the automatic rows (``flatten``: the apt.dat's flatten flag, removed
with no question) listed without a checkbox.  **Apply** sends
``pack_adjust`` with ``action="update"``, the checked rows as ``items``
and every row shown as ``shown``; **Never for this pack** sends
``action="never"`` with ``shown``; **Not now** sends nothing.

ADJUST… (``state="adjust"``, capability ``pack_adjust_edit``): the same
rows, ticked as the pack is now, and the "Optimise pack" steps
(``O4_Qt_Pack_Optimise``'s words) under :data:`OPTIMISE_HEADING`.
**Apply** sends ``action="change"`` with ``items``, ``shown`` and
``steps``; **Cancel** sends nothing.  A row the tile's mesh reads
(``rebuild``: the terrain objects) says so (:data:`REBUILD_NOTE`), and
while its tick differs from how the pack is, Apply reads
:data:`APPLY_REBUILD_BUTTON` — the window rebuilds the tile when the
engine's outcome says ``rebuild`` (during a run: :data:`REBUILD_QUEUED`,
and the engine's ``state="pending"`` after the run names every tile still
owed a rebuild, :data:`REBUILDING`).

The COPY is identical to the macOS sheet
(``Sources/SceneryKit/PackAdjust.swift``); the twin
``tests/test_qt_pack_adjust.py`` pins both.  Non-modal: the event arrives
in the middle of a build and the build goes on.
"""

from __future__ import annotations

import O4_Qt_Pack_Optimise as QTOPT
from O4_Qt_Choice_Dialog import ChoiceDialog
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

# --- copy (verbatim; identical to the Swift sheet) ----------------------
TITLE = "Adjust “{pack}”?"
BODY = ("The app is modifying this airport package. These changes help it "
        "fit your scenery. Choose what to apply:")
ITEM_TITLES = {
    "trees": "Update trees",
    "drapes": "Hide draped orthophotos included with the package",
    "ground": "Hide large ground textures included with the package",
    "terrain": "Hide terrain objects included with the package",
    "generic": "Hide generic X-Plane ground textures the package drapes",
    "flatten": "Remove the airport’s flatten flag (always)",
}
ITEM_DETAILS = {
    "trees": ("{n} old flat (X-Plane 11) tree resources become X-Plane 12 "
              "3D trees."),
    "drapes": ("{n} photo images ({uses} polygons) laid over the airport "
               "cover the tile’s imagery."),
    "ground": ("{n} painted ground or grass images ({uses} polygons) laid "
               "mostly over unpaved ground at the airport cover the tile’s "
               "imagery."),
    "terrain": ("{n} objects ({uses} placements) model hills or shoreline "
                "that the tile’s detailed elevation data already describes."),
    "generic": ("{n} stock X-Plane grass, sand or scrub textures ({uses} "
                "polygons, about {ha} ha) cover the tile’s imagery."),
    "flatten": ("The apt.dat asks X-Plane to flatten the airport, which "
                "does not work with this app’s terrain mesh."),
}
DETAIL = ("The original files are kept as backups. Undo is Restore "
          "originals on the pack’s row under Modified airports.")
APPLY_BUTTON = "Apply"
NOT_NOW_BUTTON = "Not now"
NEVER_BUTTON = "Never for this pack"
# the pack row's Adjust… (owner 2026-11-15T13:12Z)
EDIT_TITLE = "Adjust “{pack}”"
EDIT_BODY = ("Change what the app does to this airport package. Only what "
             "you change is written again, from the original files.")
OPTIMISE_HEADING = "Optimise pack:"
REBUILD_NOTE = ("Changing this also rebuilds the tile: the ground under "
                "these objects is shaped to them while they are shown.")
APPLY_REBUILD_BUTTON = "Apply and rebuild tile"
CANCEL_BUTTON = "Cancel"
ADJUST_BUTTON = "Adjust…"
ADJUST_HELP = ("Adjust: change what is hidden or optimised in this package. "
               "Only the package’s scenery file is written again; a change "
               "to its terrain objects also rebuilds the tile.")
REBUILD_LATER = ("Rebuild tile {tile} to finish the change to "
                 "{pack}’s terrain objects: {reason}")
# a terrain answer given during a run: the engine keeps the tile's debt
# (``o4_engine.tile_rebuild_pending``) and names it when the run ends
REBUILD_QUEUED = ("Tile {tile} will be rebuilt when this run finishes, to "
                  "match the change to {pack}’s terrain objects.")
REBUILDING = "Rebuilding tile {tile} to match: terrain objects {change} in “{pack}”."


def _rows(event) -> list[dict]:
    return [r for r in (getattr(event, "items", None) or ())
            if r.get("key") in ITEM_TITLES]


def _detail(row) -> str:
    text = ITEM_DETAILS[row["key"]].format(n=int(row.get("count", 0)),
                                           uses=int(row.get("uses", 0)),
                                           ha=f"{int(row.get('hectares', 0)):,}")
    return text + " " + REBUILD_NOTE if row.get("rebuild") else text


def _editing(event) -> bool:
    """The pack row's Adjust… (``state="adjust"``)."""
    return getattr(event, "state", "") == "adjust"


def _baseline(row, edit: bool) -> bool:
    """The tick that changes nothing: the pack as it is (Adjust…), or not
    applied (a build's question)."""
    return bool(row.get("checked")) if edit else False


def question_key(event) -> tuple:
    """One question per pack, tile and row set."""
    return (getattr(event, "pack_root", ""), int(getattr(event, "lat", 0)),
            int(getattr(event, "lon", 0)),
            tuple(r.get("key") for r in _rows(event)))


def has_choice(event) -> bool:
    """Whether the event names a row the user chooses (or, Adjust…, an
    Optimise step)."""
    return (any(not r.get("automatic") for r in _rows(event))
            or (_editing(event) and bool(_steps(event))))


def _steps(event) -> list[dict]:
    return [r for r in (getattr(event, "steps", None) or ())
            if r.get("key") in QTOPT.STEP_TITLES]


class _PackAdjustBox(ChoiceDialog):
    """The question: its words, one checkbox per choice, the automatic
    rows, and Apply / Never for this pack / Not now — or, Adjust…, the
    Optimise steps too and Apply / Cancel.  Answers like a
    ``QMessageBox`` (``clickedButton``, ``finished``) so the window's
    per-pack choice handler drives it; :meth:`answer_extra` is what the
    answer sends besides the action."""

    def __init__(self, event, parent=None):
        self.edit = _editing(event)
        pack = getattr(event, "pack", "")
        super().__init__((EDIT_TITLE if self.edit else TITLE).format(pack=pack),
                         parent)
        lay = QVBoxLayout(self)
        heading = QLabel(self._title)
        heading.setStyleSheet("font-weight: bold")
        lay.addWidget(heading)
        body = QLabel(EDIT_BODY if self.edit else BODY)
        body.setWordWrap(True)
        lay.addWidget(body)
        self.item_boxes: dict[str, QCheckBox] = {}
        self.step_boxes: dict[str, QCheckBox] = {}
        self.automatic: list[str] = []
        self._rebuild: dict[str, bool] = {}
        rows = _rows(event)
        for row in sorted(rows, key=lambda r: bool(r.get("automatic"))):
            if row.get("automatic"):
                head = QLabel("✓ " + ITEM_TITLES[row["key"]])
                self.automatic.append(row["key"])
            else:
                head = QCheckBox(ITEM_TITLES[row["key"]])
                head.setChecked(bool(row.get("checked", True)))
                self.item_boxes[row["key"]] = head
                if row.get("rebuild"):
                    self._rebuild[row["key"]] = _baseline(row, self.edit)
                    head.toggled.connect(self._relabel)
            self._add(lay, head, _detail(row))
        steps = _steps(event) if self.edit else []
        if steps:
            lay.addWidget(QLabel(OPTIMISE_HEADING))
        for row in steps:
            box = QCheckBox(QTOPT.STEP_TITLES[row["key"]])
            box.setChecked(bool(row.get("checked")))
            self.step_boxes[row["key"]] = box
            self._add(lay, box, QTOPT.step_detail(row))
        note = QLabel(DETAIL)
        note.setWordWrap(True)
        lay.addWidget(note)
        self._buttons = QDialogButtonBox(self)
        self.apply = self._buttons.addButton(APPLY_BUTTON,
                                             QDialogButtonBox.AcceptRole)
        self.never = (None if self.edit else self._buttons.addButton(
            NEVER_BUTTON, QDialogButtonBox.DestructiveRole))
        self.not_now = self._buttons.addButton(
            CANCEL_BUTTON if self.edit else NOT_NOW_BUTTON,
            QDialogButtonBox.RejectRole)
        self.apply.setDefault(True)
        self._buttons.clicked.connect(self._on_clicked)
        lay.addWidget(self._buttons)
        self._relabel()

    @staticmethod
    def _add(lay, head, text) -> None:
        detail = QLabel(text)
        detail.setWordWrap(True)
        detail.setContentsMargins(24, 0, 0, 6)
        lay.addWidget(head)
        lay.addWidget(detail)

    def rebuilds(self) -> bool:
        """A row the tile's mesh reads is ticked otherwise than the pack."""
        return any(self.item_boxes[k].isChecked() != was
                   for k, was in self._rebuild.items())

    def _relabel(self, *_args) -> None:
        self.apply.setText(APPLY_REBUILD_BUTTON if self.rebuilds()
                           else APPLY_BUTTON)

    def checked_items(self) -> list[str]:
        """The rows left checked, in the engine's order."""
        return [k for k, b in self.item_boxes.items() if b.isChecked()]

    def answer_extra(self, action: str) -> dict:
        """The ``pack_adjust`` arguments besides the action: every row
        shown, for Apply the rows left checked, and for Adjust… the
        Optimise steps left checked."""
        extra: dict = {"shown": list(self.item_boxes)}
        if action in ("update", "change"):
            extra["items"] = self.checked_items()
        if action == "change":
            extra["steps"] = [k for k, b in self.step_boxes.items()
                              if b.isChecked()]
        return extra


def pack_adjust_box(event, parent=None):
    """The question for one ``PackAdjust(state="found")`` event, or the
    pack row's Adjust… for one ``state="adjust"``.

    Returns ``(box, {action: button})``: ``"update"`` and ``"never"`` —
    or, Adjust…, ``"change"`` — the buttons that send ``pack_adjust``;
    Not now (Cancel) is the box's escape."""
    box = _PackAdjustBox(event, parent)
    if box.edit:
        return box, {"change": box.apply}
    return box, {"update": box.apply, "never": box.never}
