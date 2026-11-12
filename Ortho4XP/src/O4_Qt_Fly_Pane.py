"""Fly mode's pane in the Qt window (RULINGS 2026-11-10g/j; spec
flight-manager-and-world-20261110 §4.3, §14; lanes U1, U2).

The Mac app's ``FlyPane.swift`` / ``FlyModel.swift`` are the layout;
``tests/test_qt_layout_parity.py`` (``FLY_PANE``) holds the rows equal,
top to bottom: name a flight (X-Plane's saved FMS plans, SimBrief, a plan
file, a departure + arrival), the flight card, "Also build the alternate"
(off, 10g), cruise speed and corridor, the readiness checklist and
countdown, the World pack and follow lines, "While flying", "Photo detail
ahead" (the global ``drape_photo_px`` the World job's drapes are fetched
at, RULINGS 2026-11-11j), "Live flight preview" (#2001; the map's
``O4_Qt_Live_Preview`` draws it), Divert… and End flight.  With no flight
and no plan the map shows build-ahead's drapes (``WorldStatus.jobs``).
Lane F2 adds the offline waiver row (RULINGS 2026-11-10k Q3), the reload
offer in the air (rule S6 (b): "Reload scenery now" / "Not now") and the
"Divert…" airport search (``O4_Qt_Fly_Divert.DivertDialog``).

Words and rules: :mod:`O4_Fly_Text`, :mod:`O4_Fly_Layers`.  Engine
commands go through ``run(name, **arguments)`` (the window's command
table, never re-spelled); the ``flight_*`` commands, ``FlightStatus`` and
``FlightReady`` are the flight manager's (lane F1b, capability
``flight_manager``); an engine without them makes the pane say
:data:`O4_Fly_Text.NO_FLIGHT_MANAGER`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import O4_App_Modes as MODES
import O4_Fly_Divert_Text as DTEXT
import O4_Fly_Layers as LAYERS
import O4_Fly_Text as TEXT
import O4_Glossary as GLOSSARY
import O4_Qt_Fly_Divert as DIVERT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

__all__ = ["FlyPane", "PREF_SIM_PRIORITY", "PREF_LIVE_PREVIEW"]

PREF_SIMBRIEF = "simbrief_user"          # shared with "Select from flight plan…"
PREF_SIM_PRIORITY = "fly_sim_priority"
PREF_LIVE_PREVIEW = "fly_live_preview"


def _fields(event) -> Optional[Dict[str, Any]]:
    """An event (or its dict) as a dict of its fields."""
    if event is None or isinstance(event, dict):
        return event
    return {k: v for k, v in vars(event).items() if not k.startswith("_")}


def _drape_px() -> int:
    """The global ``drape_photo_px`` (512 when unread)."""
    import O4_Settings_Model as SM
    try:
        return int(SM.read_global_raw().get(TEXT.DRAPE_PX_KEY) or 512)
    except (OSError, TypeError, ValueError):
        return 512


def _set_drape_px(value) -> None:
    """Write ``drape_photo_px`` to the global cfg (build-ahead reads it
    per tile)."""
    import O4_Settings_Model as SM
    SM.write_global({TEXT.DRAPE_PX_KEY: int(value)})


def _no_engine(name, **_arguments):
    raise KeyError("unknown command: %r" % (name,))


def _caption(text: str = "", gray: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    if gray:
        label.setStyleSheet("color: gray;")
    return label


class FlyPane(QWidget):
    """See the module docstring.  ``changed`` fires when what the map
    draws changes (plan, corridor, status, aircraft)."""

    changed = Signal()

    def __init__(self, follow_line, run: Callable = None, airports: Callable = None,
                 prefs: Optional[dict] = None, save_prefs: Callable = None,
                 parent=None):
        super().__init__(parent)
        self._run = run or _no_engine
        self._airports = airports or (lambda: [])
        self.prefs = prefs if prefs is not None else {}
        self._save = save_prefs or (lambda prefs: None)
        self.plan: Optional[Dict[str, Any]] = None
        self.status: Optional[Dict[str, Any]] = None
        self.world: Optional[Dict[str, Any]] = None
        self.track = LAYERS.AircraftTrack()
        self.plans: list = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(QLabel("<b>%s</b>" % GLOSSARY.TERMS["mode_fly"]))
        self.placeholder = _caption(MODES.FLY_PLACEHOLDER, gray=True)
        layout.addWidget(self.placeholder)
        self.plan_source_combo = QComboBox()
        self.plan_source_combo.setToolTip(TEXT.PLAN_SOURCE_LABEL)
        self.plan_source_combo.activated.connect(self._source_chosen)
        layout.addWidget(self.plan_source_combo)
        self.simbrief_row, self.simbrief_edit, self.simbrief_btn = self._simbrief_row()
        layout.addWidget(self.simbrief_row)
        self.open_plan_btn = QPushButton(TEXT.OPEN_PLAN)
        self.open_plan_btn.clicked.connect(self._open_plan_file)
        layout.addWidget(self.open_plan_btn)
        self.quick_route_row, self.quick_from, self.quick_to = self._quick_row()
        layout.addWidget(self.quick_route_row)
        self.flight_card = self._card()
        layout.addWidget(self.flight_card)
        self.message_label = _caption()
        self.message_label.setStyleSheet("color: #d97706;")
        self.message_label.setVisible(False)
        layout.addWidget(self.message_label)
        self.chk_build_alternate = QCheckBox(TEXT.BUILD_ALTERNATE)
        self.chk_build_alternate.setChecked(False)          # RULINGS 2026-11-10g
        self.chk_build_alternate.setEnabled(False)
        self.chk_build_alternate.toggled.connect(
            lambda on: self._update(build_alternate=on))
        layout.addWidget(self.chk_build_alternate)
        self.cruise_speed_edit = self._spin(TEXT.CRUISE_LABEL, 40, 700,
                                            int(TEXT.DEFAULT_CRUISE_KT))
        layout.addWidget(self.cruise_speed_edit)
        self.corridor_edit = self._spin(TEXT.CORRIDOR_LABEL, 0, 200,
                                        TEXT.DEFAULT_CORRIDOR_KM)
        layout.addWidget(self.corridor_edit)
        self.readiness_list = _caption(TEXT.NO_STATUS, gray=True)
        layout.addWidget(self.readiness_list)
        self.offline_waiver_row, self.waiver_label = self._button_row(
            ((DTEXT.WAIVE_OFFLINE, self.waive_offline),))
        layout.addWidget(self.offline_waiver_row)
        self.countdown_label = _caption()
        self.countdown_label.setVisible(False)
        layout.addWidget(self.countdown_label)
        self.world_line = _caption(TEXT.world_line(None), gray=True)
        layout.addWidget(self.world_line)
        self.follow_line = follow_line
        layout.addWidget(follow_line)
        self.sim_priority_combo = QComboBox()
        self.sim_priority_combo.setToolTip(TEXT.SIM_PRIORITY_LABEL)
        for value, words in TEXT.SIM_PRIORITIES:
            self.sim_priority_combo.addItem(words, value)
        saved = self.prefs.get(PREF_SIM_PRIORITY, "balanced")
        self.sim_priority_combo.setCurrentIndex(
            max(0, self.sim_priority_combo.findData(saved)))
        self.sim_priority_combo.currentIndexChanged.connect(
            lambda _i: self._remember(PREF_SIM_PRIORITY,
                                      self.sim_priority_combo.currentData()))
        layout.addWidget(self.sim_priority_combo)
        self.drape_px_combo = QComboBox()
        self.drape_px_combo.setToolTip(TEXT.DRAPE_PX_LABEL)
        for value, words in TEXT.DRAPE_PX_CHOICES:
            self.drape_px_combo.addItem(words, value)
        self.drape_px_combo.setCurrentIndex(
            max(0, self.drape_px_combo.findData(_drape_px())))
        self.drape_px_combo.currentIndexChanged.connect(
            lambda _i: _set_drape_px(self.drape_px_combo.currentData()))
        layout.addWidget(self.drape_px_combo)
        self.chk_live_preview = QCheckBox(TEXT.LIVE_PREVIEW)
        self.chk_live_preview.setToolTip(TEXT.LIVE_PREVIEW_HELP)
        self.chk_live_preview.setChecked(bool(self.prefs.get(PREF_LIVE_PREVIEW)))
        self.chk_live_preview.toggled.connect(
            lambda on: self._remember(PREF_LIVE_PREVIEW, bool(on)))
        layout.addWidget(self.chk_live_preview)
        self.reload_offer_row, self.reload_label = self._button_row(
            ((DTEXT.RELOAD_NOW, lambda: self.reload(False)),
             (DTEXT.NOT_NOW, lambda: self.reload(True))))
        self.not_now_btn = self.reload_offer_row.buttons[1]
        layout.addWidget(self.reload_offer_row)
        self.notice_label = _caption(gray=True)
        self.notice_label.setVisible(False)
        layout.addWidget(self.notice_label)
        self.divert_btn = QPushButton(TEXT.DIVERT)
        self.divert_btn.clicked.connect(self._divert)
        layout.addWidget(self.divert_btn)
        self.end_flight_btn = QPushButton(TEXT.END_FLIGHT)
        self.end_flight_btn.clicked.connect(self._end_flight)
        layout.addWidget(self.end_flight_btn)
        layout.addStretch(1)
        self.set_plans([])
        self._show()

    # ------------------------------------------------------------------
    # rows
    # ------------------------------------------------------------------
    def _simbrief_row(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(self.prefs.get(PREF_SIMBRIEF, ""))
        edit.setPlaceholderText(TEXT.SIMBRIEF_PLACEHOLDER)
        edit.editingFinished.connect(
            lambda: self._remember(PREF_SIMBRIEF, edit.text().strip()))
        h.addWidget(edit, 1)
        button = QPushButton(TEXT.SIMBRIEF_BUTTON)
        button.clicked.connect(self.fetch_simbrief)
        h.addWidget(button)
        return row, edit, button

    def _quick_row(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        edits = []
        for words in (TEXT.QUICK_FROM, TEXT.QUICK_TO):
            edit = QLineEdit()
            edit.setPlaceholderText(words)
            h.addWidget(edit, 1)
            edits.append(edit)
        button = QPushButton(TEXT.QUICK_BUTTON)
        button.clicked.connect(self.use_quick_entry)
        h.addWidget(button)
        return row, edits[0], edits[1]

    def _button_row(self, buttons):
        """A line of words over buttons, hidden while the words are empty."""
        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 0, 0, 0)
        label = _caption()
        v.addWidget(label)
        h = QHBoxLayout()
        row.buttons = []
        for words, slot in buttons:
            button = QPushButton(words)
            button.clicked.connect(slot)
            h.addWidget(button)
            row.buttons.append(button)
        h.addStretch(1)
        v.addLayout(h)
        row.setVisible(False)
        return row, label

    def _card(self):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 6)
        self.card_label = _caption()
        v.addWidget(self.card_label)
        self.legend_label = _caption(" · ".join(w for _k, w in TEXT.LEGEND),
                                     gray=True)
        v.addWidget(self.legend_label)
        self.prepare_btn = QPushButton(TEXT.PREPARE)
        self.prepare_btn.clicked.connect(self.prepare)
        v.addWidget(self.prepare_btn)
        return card

    def _spin(self, words, lo, hi, value):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QLabel(words), 1)
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(value)
        spin.valueChanged.connect(self._show)
        h.addWidget(spin)
        row.spin = spin
        return row

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------
    def cruise_kt(self) -> int:
        return self.cruise_speed_edit.spin.value()

    def corridor_km(self) -> int:
        return self.corridor_edit.spin.value()

    def cells(self):
        jobs = LAYERS.map_jobs((self.status or {}).get("jobs") or (),
                               self.plan is not None,
                               (self.world or {}).get("jobs") or ())
        return LAYERS.corridor_cells(self.plan, self.corridor_km(), jobs)

    def _remember(self, key, value):
        if self.prefs.get(key) != value:
            self.prefs[key] = value
            self._save(self.prefs)

    def _say(self, text: str = ""):
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))

    def _show(self, *_args):
        plan = self.plan
        self.placeholder.setVisible(plan is None and self.status is None)
        self.flight_card.setVisible(plan is not None)
        if plan is not None:
            self.card_label.setText("\n".join(TEXT.card_lines(plan, self.cruise_kt())))
        self.chk_build_alternate.setEnabled(bool(plan and plan.get("alternate")))
        items = (self.status or {}).get("items") or []
        self.readiness_list.setText("\n".join(TEXT.item_text(r) for r in items)
                                    if items else TEXT.NO_STATUS)
        self.countdown_label.setVisible(self.status is not None)
        if self.status is not None:
            line = TEXT.follow_status_line(self.status)
            self.countdown_label.setText(
                "<b>%s</b>%s" % (TEXT.countdown_text(self.status.get("countdown_s")),
                                 "<br>" + line if line else ""))
        self.world_line.setText(TEXT.world_line(self.world))
        for row, label, line in (
                (self.offline_waiver_row, self.waiver_label,
                 DTEXT.waiver_line(self.status)),
                (self.reload_offer_row, self.reload_label,
                 DTEXT.reload_line(self.status))):
            label.setText(line)
            row.setVisible(bool(line))
        self.not_now_btn.setVisible((self.status or {}).get("reload") == "scheduled")
        for button in (self.divert_btn, self.end_flight_btn):
            button.setEnabled(self.status is not None)
        self.changed.emit()

    def set_plan(self, plan: Optional[Dict[str, Any]]):
        self.plan = plan
        if plan is not None:
            self.cruise_speed_edit.spin.setValue(TEXT.cruise_kt(plan))
        self._show()

    def set_plans(self, rows):
        """``flight_plans_list``'s rows in the plan menu."""
        self.plans = list(rows)
        combo = self.plan_source_combo
        combo.clear()
        combo.addItem(TEXT.PLAN_CHOOSE, "")
        combo.addItem(TEXT.PLAN_SIMBRIEF, "simbrief")
        for row in self.plans:
            combo.addItem(TEXT.plan_row_label(row), row.get("path", ""))
        combo.addItem(TEXT.PLAN_NONE, "none")

    # ------------------------------------------------------------------
    # events (the window feeds them)
    # ------------------------------------------------------------------
    def show_status(self, event):
        """A ``FlightStatus`` (the flight manager's event, or its dict)."""
        self.status = _fields(event)
        self._show()

    def show_ready(self, event):
        """A ``FlightReady``: the SimBrief plan, or why there is none."""
        if getattr(event, "error", ""):
            self._say(TEXT.refusal(event.error))
        elif isinstance(getattr(event, "result", None), dict):
            self._say()
            self.set_plan(event.result)

    def show_notice(self, event):
        """A ``FlightNotice`` (lane F2): the pane's last notice line (the
        window posts the system notification)."""
        fields = _fields(event) or {}
        text = " — ".join(w for w in (fields.get("title"), fields.get("text"))
                          if w)
        self.notice_label.setText(text)
        self.notice_label.setVisible(bool(text))

    def show_world(self, event):
        """A ``WorldStatus`` (every 2 s while build-ahead runs): the World
        line, and in free flight the tiles it lays ahead on the map."""
        self.world = _fields(event)
        self._show()

    def show_position(self, event):
        """An ``AircraftPosition``."""
        self.track.add(event.lat, event.lon, event.track_deg)
        self.changed.emit()      # the aircraft moves even when the track does not

    # ------------------------------------------------------------------
    # commands
    # ------------------------------------------------------------------
    def _command(self, name, **arguments):
        try:
            result = self._run(name, **arguments)
        except Exception as error:      # noqa: BLE001 -- said to the user
            self._say(TEXT.refusal(str(error).strip("\"'")))
            return None
        self._say()
        return result

    def refresh_plans(self, xplane_dir: str):
        result = self._command("flight_plans_list", xplane_dir=xplane_dir or "")
        self.set_plans((result or {}).get("plans", []))

    def _source_chosen(self, _index):
        choice = self.plan_source_combo.currentData()
        self._say()
        if choice == "simbrief":
            self.fetch_simbrief()
        elif choice == "none":
            self.set_plan(None)
            self.follow_aircraft()
        elif choice:
            self.read_plan(choice)

    def read_plan(self, path: str):
        plan = self._command("flight_plan_read", path=path)
        if plan is not None:
            self.set_plan(plan)

    def _open_plan_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, TEXT.OPEN_PLAN, "", "Flight plans (*.fms *.lnmpln)")
        if path:
            self.read_plan(path)

    def fetch_simbrief(self):
        user = self.simbrief_edit.text().strip()
        self._remember(PREF_SIMBRIEF, user)
        if user:
            self._command("flight_plan_simbrief", user=user)

    def use_quick_entry(self):
        """Departure + arrival from X-Plane's airport list."""
        codes = {}
        for entry in self._airports() or ():
            codes.setdefault(entry.code.upper(), entry)
        ends = []
        for edit in (self.quick_from, self.quick_to):
            entry = codes.get(edit.text().strip().upper())
            if entry is None:
                self._say(TEXT.unknown_airport(edit.text()))
                return
            ends.append((entry.code, entry.lat, entry.lon))
        self._say()
        self.set_plan(TEXT.quick_plan(*ends))

    def prepare(self):
        if self.plan is not None:
            self._command("flight_create", plan=self.plan,
                          build_alternate=self.chk_build_alternate.isChecked(),
                          cruise_kt=self.cruise_kt(),
                          corridor_km=self.corridor_km())

    def _update(self, **arguments):
        if self.status:
            self._command("flight_update", flight=self.status.get("flight"),
                          **arguments)

    def _divert(self):
        """"Divert…": the alternate first, then any airport by search."""
        if not self.status:
            return
        dialog = DIVERT.DivertDialog(
            self._airports, bool(self.plan and self.plan.get("alternate")),
            self)
        if dialog.exec() and dialog.choice() is not None:
            self.divert_to(dialog.choice())

    def divert_to(self, to):
        """``flight_divert`` to ``"alternate"`` or ``{ident, lat, lon}``."""
        if self.status:
            return self._command("flight_divert",
                                 flight=self.status.get("flight"), to=to)
        return None

    def reload(self, not_now: bool):
        """The reload in the air (S6 (b)): now, or "Not now"."""
        if self.status:
            self._command("flight_reload", flight=self.status.get("flight"),
                          not_now=bool(not_now))

    def waive_offline(self):
        """"Fly with X-Plane's own scenery there" (RULINGS 2026-11-10k Q3)."""
        self._update(waive_offline=True)

    def follow_aircraft(self):
        """"No plan: follow the aircraft": a flight still preparing or
        ready closes (``flight_end {if_prepared: true}``) so a stale
        prepared record never owns build-ahead; one in the air stays
        (#2019).  Track mode runs either way.  Swift: ``FlyModel``."""
        reply = self._command("flight_end", if_prepared=True)
        if (reply or {}).get("flight"):
            self.show_status(None)

    def _end_flight(self):
        if self.status and self._command(
                "flight_end", flight=self.status.get("flight")) is not None:
            self.show_status(None)
