"""The Build box's Airports card in the Qt window (#818).

Twin of the Mac app's ``BuildAirportsCard.swift``: what airport grading
and custom-airport object fitting do, what they cost, and a switch for
each that changes THIS build only — Settings keeps the defaults, and
:meth:`AirportsCard.take_overrides` hands the press its
``enqueue_build(overrides=...)`` and puts the switches back.  The list is
``o4_engine.build_airports``, the reader the Mac app asks through the
``build_airports`` command, read here on a worker thread.
``tests/test_qt_layout_parity.py`` holds the two cards to one order and
one wording.
"""

import threading

import O4_Glossary as GLOSSARY
from O4_Qt_Widgets import never_widen, wrap_and_never_widen
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QToolButton,
    QVBoxLayout,
)

__all__ = ["AirportsCard", "summary_suffix"]

GRADE_SENTENCE = (
    "Runways, taxiways and aprons are reshaped to meet FAA (USA) or ICAO "
    "slope and smoothness rules, so you don't get bumpy runways or cliffs "
    "at the apron edge. Without this, airports drape over the raw "
    "elevation data.")
FIT_SENTENCE = (
    "Moves the 3-D buildings, jetways and roads of these custom airports "
    "onto the reshaped ground so nothing floats or sinks.")
BACKUP_NOTE = ("Originals are backed up. Restore a pack from Modified "
               "airports in the Selection box.")
NEEDS_GRADING = "Needs airport grading on."
NO_PACKS = "No custom airport with its own 3-D objects in these tiles."
PER_BUILD_TIP = "For this build only. The default is in Settings."

#: The engine keys of the two switches (``Tile.apply_build_overrides``).
GRADE_KEY = "auto_patch"
FIT_KEY = "modify_custom_airports"

#: A drag-selection changes the selection per tile: ask once it settles.
DEBOUNCE_MS = 300


def minutes_text(seconds) -> str:
    """``[low, high]`` seconds as "about 2–5 min" (whole minutes, at
    least one) — the Mac app's ``BuildModel.minutesText``."""
    (low_s, high_s) = (float(seconds[0]), float(seconds[1]))
    low = max(1, int(round(min(low_s, high_s) / 60.0)))
    high = max(low, int(round(max(low_s, high_s) / 60.0)))
    return "about %d min" % low if low == high else "about %d–%d min" % (low, high)


def summary_suffix(card) -> str:
    """" · 4 airports · 1 custom airport (2 packs, 1,204 objects)"."""
    if not card:
        return ""
    count = len(card.get("airports") or ())
    text = " · %d airport%s" % (count, "" if count == 1 else "s")
    packs = card.get("packs") or ()
    custom = len({icao for pack in packs for icao in pack.get("airports", ())})
    if custom:
        objects = sum(int(pack.get("objects", 0)) for pack in packs)
        text += " · %d custom airport%s (%d pack%s, %s objects)" % (
            custom, "" if custom == 1 else "s", len(packs),
            "" if len(packs) == 1 else "s", format(objects, ","))
    return text


def total_line(card, grading: bool) -> str:
    count = len(card.get("airports") or ())
    airports = "%d airport%s" % (count, "" if count == 1 else "s")
    if not grading:
        return airports + " · not graded in this build"
    return "%s · adds %s to this build" % (
        airports, minutes_text(card.get("total_s") or (0, 0)))


def grade_by_default() -> bool:
    """Settings' ``auto_patch``: on unless its mode is "None"."""
    import O4_Airport_Modes as MODES
    import O4_Config_Utils as CFG

    return MODES.normalize_mode(getattr(CFG, "auto_patch", None),
                                GRADE_KEY) != "None"


def fit_by_default() -> bool:
    import O4_Config_Utils as CFG

    return bool(getattr(CFG, "modify_custom_airports", True))


class _Bridge(QObject):
    ready = Signal(object)


class AirportsCard(QGroupBox):
    """The card: grading switch, its airports, fitting switch, its packs."""

    def __init__(self, parent=None):
        super().__init__("✈ Airports", parent)
        self.overrides = {}
        self.card = None
        self._error = ""
        self._loading = False
        self._generation = 0
        self._pending = None
        self._bridge = _Bridge()
        self._bridge.ready.connect(self._on_ready)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._ask)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)
        self.chk_grade = QCheckBox(GLOSSARY.TERMS["grade_airports"])
        self.chk_grade.setToolTip(
            GLOSSARY.TERMS["grade_airports"] + "\n" + PER_BUILD_TIP)
        self.chk_grade.toggled.connect(
            lambda checked: self._switched(GRADE_KEY, checked))
        self.grade_text = self._caption(GRADE_SENTENCE)
        self.airports_toggle = QToolButton()
        self.airports_toggle.setCheckable(True)
        self.airports_toggle.setAutoRaise(True)
        self.airports_toggle.toggled.connect(self._render)
        never_widen(self.airports_toggle)
        self.airports_text = self._caption("")
        self.chk_fit = QCheckBox(GLOSSARY.TERMS["fit_buildings"])
        self.chk_fit.toggled.connect(
            lambda checked: self._switched(FIT_KEY, checked))
        self.fit_text = self._caption(FIT_SENTENCE)
        self.packs_text = self._caption("")
        for widget in (self.chk_grade, self.grade_text,
                       self.airports_toggle, self.airports_text,
                       self.chk_fit, self.fit_text, self.packs_text):
            if isinstance(widget, QCheckBox):
                never_widen(widget)
            layout.addWidget(widget)
        self.refresh_switches()

    @staticmethod
    def _caption(text):
        label = QLabel(text)
        label.setStyleSheet("color: gray;")
        wrap_and_never_widen(label)
        return label

    # ── the per-build switches ─────────────────────────────────────────
    def defaults(self) -> dict:
        return {GRADE_KEY: grade_by_default(), FIT_KEY: fit_by_default()}

    def grading(self) -> bool:
        return self.overrides.get(GRADE_KEY, self.defaults()[GRADE_KEY])

    def _switched(self, key, checked):
        if self.defaults()[key] == bool(checked):
            self.overrides.pop(key, None)
        else:
            self.overrides[key] = bool(checked)
        self._render()

    def take_overrides(self) -> dict:
        """The press's ``overrides``; the switches go back to Settings."""
        taken = dict(self.overrides)
        self.overrides.clear()
        self.refresh_switches()
        return taken

    def refresh_switches(self):
        """Show this build's switches (Settings' values unless changed)."""
        defaults = self.defaults()
        for (box, key) in ((self.chk_grade, GRADE_KEY),
                           (self.chk_fit, FIT_KEY)):
            box.blockSignals(True)
            box.setChecked(self.overrides.get(key, defaults[key]))
            box.blockSignals(False)
        self._render()

    # ── the engine's answer ────────────────────────────────────────────
    def request(self, cells, custom_build_dir=""):
        """Ask for ``cells``' card once the selection settles."""
        self._pending = ([(int(c[0]), int(c[1])) for c in cells],
                         custom_build_dir)
        self._generation += 1
        if not self._pending[0]:
            self._debounce.stop()
            (self.card, self._error, self._loading) = (None, "", False)
            self._render()
            return
        self._loading = True
        self._render()
        self._debounce.start()

    def _ask(self):
        (cells, folder) = self._pending
        generation = self._generation

        def work():
            from o4_engine import build_airports as CARD

            try:
                answer = (generation, CARD.build_airports(cells, folder), "")
            except Exception as error:       # the card says so
                answer = (generation, None, str(error))
            try:
                self._bridge.ready.emit(answer)
            except RuntimeError:
                pass                          # the window went away

        threading.Thread(target=work, daemon=True,
                         name="o4-build-airports").start()

    def _on_ready(self, answer):
        (generation, card, error) = answer
        if generation != self._generation:
            return                            # a newer selection asks
        (self.card, self._error, self._loading) = (card, error, False)
        self._render()
        changed = getattr(self, "on_card_changed", None)
        if changed is not None:
            changed()

    # ── the words ──────────────────────────────────────────────────────
    def fit_disabled_reason(self):
        if not self.grading():
            return NEEDS_GRADING
        if self.card is not None and not self.card.get("packs"):
            return NO_PACKS
        return None

    def _render(self, *_):
        card = self.card
        airports = (card or {}).get("airports") or []
        if self._loading and card is None:
            line = "Reading the airports in the selected tiles…"
        elif self._error:
            line = "The airport list could not be read: %s" % self._error
        elif card is None:
            line = ""
        elif not airports:
            line = "No airport in the selected tiles is graded."
        else:
            line = ""
        self.airports_toggle.setVisible(bool(airports) and not self._error)
        if airports:
            self.airports_toggle.setText(
                ("▾ " if self.airports_toggle.isChecked() else "▸ ")
                + total_line(card, self.grading()))
        rows = [line] if line else []
        if airports and self.airports_toggle.isChecked():
            rows += ["%s %s · %s · %s" % (
                a["icao"], a.get("name", ""), a.get("ruleset", ""),
                minutes_text(a.get("estimate_s") or (0, 0)))
                for a in airports]
        self.airports_text.setText("\n".join(rows))
        self.airports_text.setVisible(bool(rows))
        reason = self.fit_disabled_reason()
        self.chk_fit.setEnabled(reason is None)
        self.chk_fit.setToolTip(reason or PER_BUILD_TIP)
        self.fit_text.setText(reason or FIT_SENTENCE)
        packs = (card or {}).get("packs") or []
        self.packs_text.setText("\n".join(
            ["%s · %s object%s" % (p["name"], format(int(p["objects"]), ","),
                                   "" if int(p["objects"]) == 1 else "s")
             for p in packs] + ([BACKUP_NOTE] if packs else [])))
        self.packs_text.setVisible(bool(packs))
