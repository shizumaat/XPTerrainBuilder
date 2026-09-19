"""The "Airports on a tile edge" dialog (spec §C.7, Qt half).

An airport whose AIRSIDE claim (apt.dat runways + taxiway/apron
pavement, buffered by ``law.emit.seam.ask_reach_m``) reaches into a
1 degree tile the user did not select cannot be graded whole: either the
adjacent tile is built too, or that airport gets no elevation patch this
run.  The engine's ``boundary_airports`` preflight answers WHICH airports
those are (:class:`o4_engine.events.BoundaryAirportsReady`); this module
is the one modal sheet that asks, once per build, for the whole batch.

Copy parity with the macOS app's sheet is LAW (owner RULINGS
2026-09-18i): the strings below are the ones
``BoundaryAirportsSheet.swift`` renders, and the preselected action comes
from the event's ``default_choice`` rather than being spelled here, so
the two front ends cannot disagree about it.

Widget discipline (beta plan §1 B4, ``tests/test_qt_dialog_fits_small_screen``):
a plain QLabel reports its whole text as its MINIMUM width, so the airport
rows are :class:`O4_Qt_Widgets.ElidedRowLabel` and the list lives in a
scroll area with a bounded height — 20 airports must not make a dialog
that a 1280x720 laptop cannot show.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from O4_Qt_Widgets import ElidedRowLabel

# --- copy (verbatim; identical to the Swift sheet) ---------------------
TITLE = "Airports on a tile edge"
BODY = ("These airports extend into tiles you haven't selected. "
        "To grade a whole airport, the adjacent tiles have to be built "
        "too.")
FOOTNOTE = "Skipped airports keep ungraded terrain in this build."
NEIGHBOUR_BUTTON = "Build adjacent tiles too (%d)"
SKIP_BUTTON = "Skip these airports' patches"
CANCEL_BUTTON = "Cancel build"
REMEMBER_CHECKBOX = "Remember my choice"

#: ``boundary_policy`` value -> the ``auto_patch_boundary`` app-cfg value
#: the "Remember my choice" tick persists (spec §C.4).
CFG_VALUE_FOR_POLICY = {
    "neighbour": "Build adjacent",
    "skip": "Skip patch",
}

#: How many airport rows the scroll area shows before it scrolls.
VISIBLE_ROWS = 6

#: How long the GUI waits for :class:`BoundaryAirportsReady` before it
#: proceeds as if the preflight had errored (spec §C.7 — generous, and
#: never a reason a build does not start).
PREFLIGHT_TIMEOUT_MS = 20000


def build_kwargs(settings, boundary_policy):
    """``settings`` plus ``boundary_policy`` when there is one.

    The keyword is additive (protocol 1.8): an unanswered preflight sends
    nothing and the engine resolves the policy from ``auto_patch_boundary``
    itself.
    """
    kwargs = dict(settings or {})
    if boundary_policy is not None:
        kwargs["boundary_policy"] = boundary_policy
    return kwargs


def tile_label(cell) -> str:
    """``(38, -9)`` -> ``"+38-009"`` — the X-Plane tile spelling."""
    return "%+03d%+04d" % (int(cell[0]), int(cell[1]))


def crossing_metres(crossing_m) -> int:
    """The row's distance, rounded to 10 m (the dialog's precision)."""
    try:
        value = float(crossing_m)
    except (TypeError, ValueError):
        return 0
    return int(round(value / 10.0)) * 10


def airport_row_text(airport) -> str:
    """One list row: what the airport is and where it reaches.

    ``{icao} {name} - extends {metres} m into {tiles}``; an airport whose
    cold neighbours are unknown still names itself and its distance.
    """
    icao = str(airport.get("icao", "") or "").strip()
    name = str(airport.get("name", "") or "").strip()
    head = (icao + " " + name).strip()
    tiles = ", ".join(tile_label(cell)
                      for cell in (airport.get("neighbours") or []))
    text = "%s — extends %d m" % (head, crossing_metres(
        airport.get("crossing_m", 0)))
    if tiles:
        text += " into %s" % tiles
    return text


class BoundaryAirportsDialog(QDialog):
    """The one modal sheet for a whole batch.

    After :meth:`exec` returns, :attr:`choice` is the chosen
    ``boundary_policy`` — ``"neighbour"``, ``"skip"``, or ``None`` when
    the user cancelled the build — and :attr:`remember` says whether the
    answer is to be persisted as ``auto_patch_boundary``.
    """

    def __init__(self, airports, add_tiles, default_choice="neighbour",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setModal(True)
        self.choice = None
        self.remember = False
        raw_default = str(default_choice or "")
        self._default_choice = (raw_default
                                if raw_default in ("neighbour", "skip")
                                else "neighbour")
        self._airports = list(airports or [])
        self._add_tiles = list(add_tiles or [])

        layout = QVBoxLayout(self)

        heading = QLabel("<b>%s</b>" % TITLE, self)
        heading.setTextFormat(Qt.RichText)
        layout.addWidget(heading)

        body = QLabel(BODY, self)
        body.setWordWrap(True)
        body.setMinimumWidth(1)
        layout.addWidget(body)

        self.rows = []
        list_host = QWidget(self)
        list_layout = QVBoxLayout(list_host)
        list_layout.setContentsMargins(0, 0, 0, 0)
        for airport in self._airports:
            row = ElidedRowLabel(airport_row_text(airport), list_host)
            row.setToolTip(row.text())
            self.rows.append(row)
            list_layout.addWidget(row)
        list_layout.addStretch(1)

        self.scroll = QScrollArea(self)
        self.scroll.setWidget(list_host)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        # A bounded height is what keeps 20 airports inside a 720 px
        # screen; below that bound the list simply scrolls.
        row_height = (self.rows[0].sizeHint().height() if self.rows
                      else self.fontMetrics().height())
        self.scroll.setMinimumHeight(row_height * 2)
        self.scroll.setMaximumHeight(row_height * VISIBLE_ROWS + 8)
        layout.addWidget(self.scroll, 1)

        footnote = QLabel(FOOTNOTE, self)
        footnote.setWordWrap(True)
        footnote.setMinimumWidth(1)
        layout.addWidget(footnote)

        self.remember_check = QCheckBox(REMEMBER_CHECKBOX, self)
        layout.addWidget(self.remember_check)

        self.buttons = QDialogButtonBox(self)
        self.neighbour_btn = QPushButton(
            NEIGHBOUR_BUTTON % len(self._add_tiles), self)
        self.skip_btn = QPushButton(SKIP_BUTTON, self)
        self.cancel_btn = QPushButton(CANCEL_BUTTON, self)
        self.buttons.addButton(self.neighbour_btn,
                               QDialogButtonBox.AcceptRole)
        self.buttons.addButton(self.skip_btn, QDialogButtonBox.AcceptRole)
        self.buttons.addButton(self.cancel_btn, QDialogButtonBox.RejectRole)
        for button in (self.neighbour_btn, self.skip_btn, self.cancel_btn):
            button.setAutoDefault(False)
            button.setDefault(False)
            # A push button neither wraps nor elides: let it clip rather
            # than put a font-scaled floor under the dialog.
            policy = button.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Ignored)
            button.setSizePolicy(policy)
        self.neighbour_btn.clicked.connect(lambda: self._finish("neighbour"))
        self.skip_btn.clicked.connect(lambda: self._finish("skip"))
        self.cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self.buttons)

        # The Return-key action is the ENGINE's (``default_choice``), not
        # this file's opinion.
        self.default_button.setAutoDefault(True)
        self.default_button.setDefault(True)
        self.default_button.setFocus()

    # ------------------------------------------------------------------
    @property
    def default_choice(self) -> str:
        return self._default_choice

    @property
    def default_button(self):
        """The button Return presses — driven by ``default_choice``."""
        return (self.skip_btn if self._default_choice == "skip"
                else self.neighbour_btn)

    def _finish(self, choice):
        self.choice = choice
        self.remember = self.remember_check.isChecked()
        self.accept()

    def _cancel(self):
        self.choice = None
        self.remember = False
        self.reject()

    def reject(self):                      # Escape closes as "cancel"
        self.choice = None
        super().reject()
