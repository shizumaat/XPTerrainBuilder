"""The "same structures in two packs" question (issue #2145; Qt half).

The engine names every pair of installed packs that draw the same large
structures near an airport in one :class:`o4_engine.events.PackOverlaps`
event; this module is the question the Qt window asks for it: per pair,
its summary and a picker — either pack, or "Keep both" — set to the
remembered answer, else the airport pack (owner 2026-11-17T19:15Z
"Default would be to prefer the airport pack").  **Apply** sends
``pack_overlaps`` with ``action="choose"`` and ``items`` ``[{"key",
"winner"}]``; **Not now** sends nothing.  A row of ``"kind":
"duplicate"`` is two packs defining the same airport (RULINGS 17s): its
picker offers to disable the lower pack or keep both enabled, and a
report row (a pack the ini does not list) has no picker.  A row of
``"kind": "drapes"`` (RULINGS 2026-11-19h) is a lower pack's draped
polygons inside a custom airport: hide them (the airport pack wins) or
keep both.

The tile pane's **Pack choices…** (#2180) sends ``pack_overlaps``
``action="ask"``; the report opens this question on every pair with its
stored answer, or says the tile has no pair.  The box has a standard
size: more than a few pairs scroll.

The question opens CONDENSED (#2190, owner 2026-11-20T01:00Z): one
answer for the whole tile -- "Prefer the airports" (each pair's row
``prefer``) or "Keep everything" (``keep``) -- and "Use this for all
tiles" (Apply sends ``default``: the answer, or ``""`` to clear it).
Pairs the answer cannot decide (``""``: two airport packs) are listed
with their pickers at once; "Choose by airport…" expands the rest, each
picker following the tile's answer until the user picks it.

The COPY is identical to the macOS sheet
(``Sources/SceneryKit/PackOverlaps.swift``); the twin
``tests/test_qt_pack_overlaps.py`` pins both.  Non-modal: the event
arrives after a build and the next one goes on.
"""

from __future__ import annotations

from O4_Qt_Choice_Dialog import ChoiceDialog
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
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
# two packs defining the same airport (RULINGS 17s, owner 2026-11-17T23:37Z)
SAME_AIRPORT = ("Some packs define the same airport. X-Plane uses the "
                "layout of the pack higher in scenery_packs.ini; the lower pack's "
                "scenery may still overlap it.")
DISABLE_PREFIX = "Disable "
KEEP_ENABLED = "Keep both enabled"
RESTART_NOTE = ("Disabling a pack changes only its line in "
                "scenery_packs.ini; its files stay. Restart X-Plane to use the change.")
DUPLICATE_KIND = "duplicate"
DISABLE = "disable"
KEEP = "keep"
# a lower pack's draped polygons inside a custom airport (RULINGS 2026-11-19h)
DRAPES_NOTE = ("Some packs lower in scenery_packs.ini drape their own "
               "ground polygons inside a custom airport, under the airport's layout. "
               "Hiding them leaves them out of that pack's tile; no file is deleted.")
HIDE_PREFIX = "Hide "
HIDE_SUFFIX = "'s polygons inside the airport"
DRAPES_KIND = "drapes"
# reviewing a tile's answers later (#2180): the tile pane's button sends
# ``pack_overlaps`` "ask" and opens this question on every pair
REVIEW_BUTTON = "Pack choices…"
REVIEW_HELP = ("Review and change this tile's answers about packs "
               "that draw the same structures.")
NO_PAIRS = "No two packs draw the same structures on this tile."
OK_BUTTON = "OK"
# the condensed question (#2190, owner 2026-11-20T01:00Z)
CONDENSED_BODY = ("Some packs draw scenery in the same places as an airport pack "
                  "on this tile. Choose for the whole tile:")
PREFER_LABEL = "Prefer the airports (hide conflicting overlays)"
KEEP_ALL_LABEL = "Keep everything"
ALL_TILES = "Use this for all tiles"
ALL_TILES_NOTE = ("Later builds use this answer and ask only about pairs it "
                  "cannot decide. Pack choices… still opens every pair.")
UNDECIDED_NOTE = "These pairs need your answer:"
BY_AIRPORT = "Choose by airport…"
#: the condensed answers (``pack_overlap_default.MODES``) and the row
#: field each one reads
PREFER = "prefer_airports"
KEEP_ALL = "keep_all"
MODE_FIELDS = {PREFER: "prefer", KEEP_ALL: "keep"}

# A standard size (#2180; the Swift sheet's ``boxWidth`` /
# ``listMaxHeight`` / ``unscrolledPairs``): the words and buttons always
# show; more than UNSCROLLED_PAIRS pairs scroll inside LIST_MAX_HEIGHT,
# which fits a 13" laptop screen.
BOX_WIDTH = 520
LIST_MAX_HEIGHT = 360
UNSCROLLED_PAIRS = 4


def offers(event) -> list[dict]:
    """The pairs to offer: two packs and a summary each."""
    return [r for r in (getattr(event, "items", None) or ())
            if len(r.get("packs") or ()) == 2 and r.get("key")]


def _same_airport(row) -> bool:
    return row.get("kind") == DUPLICATE_KIND


def _drapes(row) -> bool:
    return row.get("kind") == DRAPES_KIND


def _choices(row) -> list[tuple[str, str]]:
    """The picker's ``(label, winner)`` entries: each pack, then both; for
    a same-airport pair, disable the lower pack or keep both enabled (none
    for a report: a pack the ini does not list); for a drape pair, hide the
    lower pack's polygons (the airport pack wins) or keep both."""
    if _same_airport(row):
        lower = row.get("lower") or ""
        return [(DISABLE_PREFIX + lower, DISABLE), (KEEP_ENABLED, KEEP)] if lower else []
    if _drapes(row):
        return [(HIDE_PREFIX + (row.get("lower") or "") + HIDE_SUFFIX,
                 row.get("default") or ""), (KEEP_BOTH, BOTH)]
    return [(KEEP_PREFIX + p, p) for p in row["packs"]] + [(KEEP_BOTH, BOTH)]


def _preselected(row) -> str:
    """The remembered answer, else the airport pack."""
    return row.get("winner") or row.get("default") or row["packs"][0]


def _mode_winner(row, mode: str) -> str:
    """The ``winner`` the tile's condensed answer gives ``row``; ``""``
    when it cannot decide it (the row is listed with its picker)."""
    return str(row.get(MODE_FIELDS.get(mode, "")) or "") if _choices(row) else ""


def _initial_mode(event) -> str:
    """The stored default for all tiles, else Prefer the airports (owner
    2026-11-17T19:15Z: the airport pack by default)."""
    value = getattr(event, "default", "") or ""
    return value if value in MODE_FIELDS else PREFER


def reports_none(event) -> bool:
    """The report of a tile with no pair: shown as "no pairs" (#2180)."""
    return getattr(event, "state", "") == "ask" and not offers(event)


def question_key(event) -> tuple:
    """One question per tile and pair set."""
    return (int(getattr(event, "lat", 0)), int(getattr(event, "lon", 0)),
            tuple(r["key"] for r in offers(event)))


def _wrapped(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class _PackOverlapsBox(ChoiceDialog):
    """The question: its words, one picker per pair, and Apply / Not now
    (``ChoiceDialog``'s message-box surface); :meth:`answer_extra` is what
    Apply sends besides the action."""

    def __init__(self, event, parent=None):
        super().__init__(TITLE, parent)
        self.setFixedWidth(BOX_WIDTH)
        lay = QVBoxLayout(self)
        heading = QLabel(TITLE)
        heading.setStyleSheet("font-weight: bold")
        lay.addWidget(heading)
        self.pickers: dict[str, QComboBox] = {}
        self.scroll = None
        self._buttons = QDialogButtonBox(self)
        self._buttons.clicked.connect(self._on_clicked)
        if reports_none(event):
            lay.addWidget(_wrapped(NO_PAIRS))
            self.apply = None
            self.not_now = self._buttons.addButton(OK_BUTTON,
                                                   QDialogButtonBox.AcceptRole)
            self.not_now.setDefault(True)
            lay.addWidget(self._buttons)
            return
        self._rows = offers(event)
        self._touched: set[str] = set()
        self._condensed(lay, event)
        self.by_airport = QToolButton()
        self.by_airport.setText(BY_AIRPORT)
        self.by_airport.setCheckable(True)
        self.by_airport.setAutoRaise(True)
        self.by_airport.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        lay.addWidget(self.by_airport)
        self.details = _wrapped(BODY)
        lay.addWidget(self.details)
        same = any(_same_airport(r) for r in self._rows)
        if same:
            lay.addWidget(_wrapped(SAME_AIRPORT))
        if any(_drapes(r) for r in self._rows):
            lay.addWidget(_wrapped(DRAPES_NOTE))
        self.undecided_note = _wrapped(UNDECIDED_NOTE)
        lay.addWidget(self.undecided_note)
        lay.addWidget(self._pair_list(event))
        self.by_airport.toggled.connect(lambda _on: self._follow_mode())
        self._prefill()
        lay.addWidget(_wrapped(DETAIL))
        if same:
            lay.addWidget(_wrapped(RESTART_NOTE))
        self.apply = self._buttons.addButton(APPLY_BUTTON,
                                             QDialogButtonBox.AcceptRole)
        self.not_now = self._buttons.addButton(NOT_NOW_BUTTON,
                                               QDialogButtonBox.RejectRole)
        self.apply.setDefault(True)
        lay.addWidget(self._buttons)

    def _condensed(self, lay, event) -> None:
        """The tile's answer: the two choices and Use this for all tiles."""
        lay.addWidget(_wrapped(CONDENSED_BODY))
        self.modes = QButtonGroup(self)
        self.mode_buttons: dict[str, QRadioButton] = {}
        for mode, label in ((PREFER, PREFER_LABEL), (KEEP_ALL, KEEP_ALL_LABEL)):
            button = QRadioButton(label)
            self.modes.addButton(button)
            self.mode_buttons[mode] = button
            lay.addWidget(button)
        self.mode_buttons[_initial_mode(event)].setChecked(True)
        self.all_tiles = QCheckBox(ALL_TILES)
        self.all_tiles.setChecked(bool(getattr(event, "default", "")))
        lay.addWidget(self.all_tiles)
        note = _wrapped(ALL_TILES_NOTE)
        note.setStyleSheet("color: gray")
        lay.addWidget(note)
        self.modes.buttonToggled.connect(lambda *_a: self._follow_mode())

    def mode(self) -> str:
        return next(m for m, b in self.mode_buttons.items() if b.isChecked())

    def _prefill(self) -> None:
        """A stored answer the tile's answer would change is the user's
        pick (kept, shown expanded); then every picker follows the mode."""
        for row in self._rows:
            w = row.get("winner") or ""
            if w and row["key"] in self.pickers and w != _mode_winner(row, self.mode()):
                self._touched.add(row["key"])
        self.by_airport.setChecked(any(
            _mode_winner(r, self.mode()) for r in self._rows
            if r["key"] in self._touched))
        self._follow_mode()

    def _follow_mode(self) -> None:
        """Each untouched picker on the mode's winner; the pairs the mode
        cannot decide shown at once, the rest under Choose by airport…"""
        mode = self.mode()
        undecided = 0
        for row in self._rows:
            decided = bool(_mode_winner(row, mode))
            undecided += not decided
            pick = self.pickers.get(row["key"])
            if pick is not None and row["key"] not in self._touched:
                pick.setCurrentIndex(max(0, pick.findData(
                    _mode_winner(row, mode) or _preselected(row))))
            for w in self._row_widgets[row["key"]]:
                w.setVisible(not decided or self.by_airport.isChecked())
        expanded = self.by_airport.isChecked()
        self.undecided_note.setVisible(bool(undecided) and not expanded)
        self.by_airport.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.by_airport.setVisible(expanded or undecided < len(self._rows))
        self.details.setVisible(expanded)
        if self.scroll is not None:
            self.scroll.setVisible(expanded or bool(undecided))

    def _pair_list(self, event) -> QWidget:
        """One summary and picker per pair; more than UNSCROLLED_PAIRS
        scroll inside LIST_MAX_HEIGHT."""
        rows = QWidget()
        lay = QVBoxLayout(rows)
        lay.setContentsMargins(0, 0, 0, 0)
        self._row_widgets: dict[str, list] = {}
        for row in offers(event):
            summary = _wrapped(row.get("summary") or " / ".join(row["packs"]))
            lay.addWidget(summary)
            self._row_widgets[row["key"]] = [summary]
            if not _choices(row):
                continue                    # a report: nothing to answer
            pick = QComboBox()
            for label, winner in _choices(row):
                pick.addItem(label, winner)
            pick.setCurrentIndex(max(0, pick.findData(_preselected(row))))
            pick.activated.connect(lambda _i, k=row["key"]: self._touched.add(k))
            self.pickers[row["key"]] = pick
            self._row_widgets[row["key"]].append(pick)
            lay.addWidget(pick)
        if len(offers(event)) <= UNSCROLLED_PAIRS:
            return rows
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(rows)
        self.scroll.setFixedHeight(LIST_MAX_HEIGHT)
        return self.scroll

    def answer_extra(self, action: str) -> dict:
        """The ``pack_overlaps`` arguments besides the action: each pair's
        picked winner (the tile's answer where the user did not pick), and
        the default for all tiles (``""`` clears it)."""
        return {"items": [{"key": k, "winner": p.currentData()}
                          for k, p in self.pickers.items()],
                "default": self.mode() if self.all_tiles.isChecked() else ""}


def pack_overlaps_box(event, parent=None):
    """The question for one ``PackOverlaps(state="found")`` event, or the
    tile's report (``state="ask"``, #2180).

    Returns ``(box, {action: button})``: ``"choose"`` — the button that
    sends ``pack_overlaps``; Not now is the escape.  A report with no pair
    says so, with OK only (no action)."""
    box = _PackOverlapsBox(event, parent)
    return box, ({"choose": box.apply} if box.apply is not None else {})
