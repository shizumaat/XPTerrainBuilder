"""The "Select from flight plan" dialog and its route layer (issue #829, Qt
half; the Mac half is ``FlightPlanPanel.swift``).

Open an X-Plane ``.fms`` or Little Navmap ``.lnmpln``, or fetch the
user's latest SimBrief plan (network, said in the dialog), then pick a
radius in km or nm.  While the dialog is open the route is drawn on the
map and the selection is the tiles that were selected before plus every
tile within the radius of the route (:mod:`O4_Flight_Plan`, the rule the
Mac app shares); the radius changes it live.  "Select" keeps it, with the
departure tile active; "Cancel" puts the old selection back.

The dialog is not modal, so the map can be panned and zoomed while the
radius is set.
"""

from __future__ import annotations

import typing as _t

import O4_Flight_Plan as FP
from O4_Qt_Widgets import SqueezableLineEdit, wrap_and_never_widen
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

__all__ = ["FlightPlanDialog", "RouteLayer"]

#: The map's magenta (MapCanvasView.magenta on the Mac).
ROUTE_COLOR = QColor(199, 64, 120)

PREF_UNIT = "flight_plan_unit"
PREF_RADIUS = "flight_plan_radius"
PREF_SIMBRIEF = "simbrief_user"


class RouteLayer:
    """The route over the map: a map layer (``MapView.add_layer``) that
    paints polylines in viewport space and never takes the mouse."""

    def __init__(self, map_view) -> None:
        self._map = map_view
        self._parts: list[list[tuple[float, float]]] = []

    def set_parts(self, parts) -> None:
        self._parts = [list(p) for p in parts]
        self._map.viewport().update()

    def parts(self):
        return self._parts

    def paint(self, painter) -> None:
        if not self._parts:
            return
        pen = QPen(ROUTE_COLOR, 2.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        for part in self._parts:
            painter.drawPolyline(QPolygonF(
                [self._map._viewport_point(lat, lon) for lat, lon in part]))

    def mouse_press(self, _event) -> bool:
        return False

    def mouse_move(self, _event) -> bool:
        return False

    def mouse_release(self, _event) -> bool:
        return False

    def viewport_moved(self) -> None:
        pass


class FlightPlanDialog(QDialog):
    """See the module docstring.  ``layer`` is the window's
    :class:`RouteLayer`; ``fetch`` and ``choose_file`` are the network and
    file-picker seams (tests pass fakes; no network there)."""

    def __init__(self, parent, map_view, layer: RouteLayer, prefs: dict,
                 save_prefs: _t.Callable[[dict], None],
                 fetch: _t.Callable[[str], FP.FlightPlan] = FP.fetch_simbrief,
                 choose_file: _t.Optional[_t.Callable[[], str]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(FP.MENU_TITLE.rstrip("…"))
        self.setModal(False)
        self._map = map_view
        self._prefs = prefs
        self._save_prefs = save_prefs
        self._fetch = fetch
        self._choose_file = choose_file or self._ask_for_file
        self._base = set(map_view.selection())
        self._base_active = map_view.active_tile()
        self._plan: _t.Optional[FP.FlightPlan] = None
        self._tiles: list[tuple[int, int]] = []
        self.layer = layer  # installed on the map once, by its owner
        self._build_ui()

    # --- layout ---------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.open_button = QPushButton(FP.OPEN_BUTTON)
        self.open_button.clicked.connect(self.open_file)
        layout.addWidget(self.open_button)

        row = QHBoxLayout()
        self.simbrief_edit = SqueezableLineEdit(220)
        self.simbrief_edit.setPlaceholderText(FP.SIMBRIEF_PLACEHOLDER)
        self.simbrief_edit.setText(str(self._prefs.get(PREF_SIMBRIEF, "")))
        self.simbrief_edit.returnPressed.connect(self.fetch_simbrief)
        self.simbrief_button = QPushButton(FP.SIMBRIEF_BUTTON)
        self.simbrief_button.clicked.connect(self.fetch_simbrief)
        row.addWidget(self.simbrief_edit, 1)
        row.addWidget(self.simbrief_button)
        layout.addLayout(row)
        note = QLabel(FP.SIMBRIEF_NOTE)
        note.setStyleSheet("color: gray;")
        wrap_and_never_widen(note)
        layout.addWidget(note)

        self.summary = QLabel("")
        wrap_and_never_widen(self.summary)
        layout.addWidget(self.summary)

        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel(FP.RADIUS_LABEL))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(list(FP.UNITS))
        unit = self._prefs.get(PREF_UNIT, "km")
        self.unit_combo.setCurrentText(unit if unit in FP.UNITS else "km")
        self.radius_spin = QSpinBox()
        self._set_radius_range(self.unit_combo.currentText())
        try:
            radius = int(self._prefs.get(PREF_RADIUS, FP.RADIUS_DEFAULT[self.unit]))
        except (TypeError, ValueError):
            radius = FP.RADIUS_DEFAULT[self.unit]
        self.radius_spin.setValue(radius)
        self.radius_spin.valueChanged.connect(self._radius_changed)
        self.unit_combo.currentTextChanged.connect(self._unit_changed)
        radius_row.addWidget(self.radius_spin)
        radius_row.addWidget(self.unit_combo)
        radius_row.addWidget(QLabel(FP.OF_ROUTE_LABEL))
        radius_row.addStretch(1)
        layout.addLayout(radius_row)

        self.count_label = QLabel("")
        layout.addWidget(self.count_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Select")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    @property
    def unit(self) -> str:
        return self.unit_combo.currentText()

    def _set_radius_range(self, unit: str) -> None:
        self.radius_spin.setRange(0, FP.RADIUS_MAX[unit])
        self.radius_spin.setSuffix(" " + unit)

    # --- loading a plan ---------------------------------------------------------
    def _ask_for_file(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self, FP.OPEN_BUTTON.rstrip("…"), "",
            "Flight plans (%s);;All files (*)" % " ".join(
                "*." + ext for ext in FP.FILE_TYPES))
        return path

    def open_file(self) -> None:
        path = self._choose_file()
        if not path:
            return
        try:
            self.load_plan(FP.read_plan_file(path))
        except FP.FlightPlanError as exc:
            self._show_error(str(exc))

    def fetch_simbrief(self) -> None:
        user = self.simbrief_edit.text().strip()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            plan = self._fetch(user)
        except FP.FlightPlanError as exc:
            self._show_error(str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._prefs[PREF_SIMBRIEF] = user
        self._save_prefs(self._prefs)
        self.load_plan(plan)

    def load_plan(self, plan: FP.FlightPlan) -> None:
        self._plan = plan
        self.summary.setStyleSheet("")
        self.layer.set_parts(FP.route_drawing(plan.points()))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
        self.refresh()
        self._map.zoom_to_tiles(self._tiles)

    def _show_error(self, text: str) -> None:
        self.summary.setStyleSheet("color: #E5372B;")
        self.summary.setText(text)

    # --- the live selection ---------------------------------------------------
    def _radius_changed(self, _value: int) -> None:
        self._prefs[PREF_RADIUS] = self.radius_spin.value()
        self._save_prefs(self._prefs)
        self.refresh()

    def _unit_changed(self, unit: str) -> None:
        old = "nm" if unit == "km" else "km"
        km = FP.radius_km(self.radius_spin.value(), old)
        value = round(km / FP.radius_km(1, unit))
        self.radius_spin.blockSignals(True)
        self._set_radius_range(unit)
        self.radius_spin.setValue(value)
        self.radius_spin.blockSignals(False)
        self._prefs[PREF_UNIT] = unit
        self._prefs[PREF_RADIUS] = self.radius_spin.value()
        self._save_prefs(self._prefs)
        self.refresh()

    def radius_km(self) -> float:
        return FP.radius_km(self.radius_spin.value(), self.unit)

    def tiles(self) -> list[tuple[int, int]]:
        return list(self._tiles)

    def refresh(self) -> None:
        if self._plan is None:
            return
        self.summary.setText(FP.summary_text(self._plan, self.unit))
        self._tiles = FP.route_tiles(self._plan.points(), self.radius_km())
        self._map.set_selection(self._base | set(self._tiles))
        self.count_label.setText(FP.tiles_text(len(self._tiles)))

    # --- closing ------------------------------------------------------------------
    def accept(self) -> None:
        if self._plan is not None:
            lat, lon = self._plan.points()[0]
            self._map.set_active(int(lat // 1), int(lon // 1), select=False)
        self.layer.set_parts([])
        super().accept()

    def reject(self) -> None:
        self._map.set_selection(self._base)
        if self._base_active is not None:
            self._map.set_active(*self._base_active, select=False)
        self.layer.set_parts([])
        super().reject()
