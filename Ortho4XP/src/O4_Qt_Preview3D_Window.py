"""The Qt app's 3D preview window (spec patch-editor-20261015 §5, A8, §6;
mockup "3D preview"; the Mac app's ``TerrainPreviewWindow``): terrain with
the patch applied, live while editing, read-only — a separate window,
opened with Ctrl/⌘3 or the "3D" button on the map's patch toolbar.

The 3D view is a ``QQuickWidget`` running :data:`SCENE_QML`; the toolbar,
legend, chip and "Reset view" are ordinary widgets floated over it, with
the Mac window's words.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QSlider, QToolButton, QVBoxLayout, QWidget)

import O4_Qt_Preview3D_Drape as DRP
import O4_Qt_Preview3D_Scene as SC
from O4_Qt_Preview3D_Model import LOADING, NO_PATCH, NO_PATCH_TEXT, PreviewModel

__all__ = ["PreviewWindow", "SHORTCUT", "BUTTON_HELP", "MODE_HELP", "IMAGERY_HELP",
           "BUILDINGS_HELP", "EXAGGERATION_HELP", "RESET_HELP", "LEGEND"]

SHORTCUT = QKeySequence("Ctrl+3")
BUTTON_HELP = "Open the 3D preview of this airport's patch (%s)." % SHORTCUT.toString(
    QKeySequence.NativeText)
MODE_HELP = ("Preview follows your edits; Last build is the mesh X-Plane loads, refreshed "
             "after a rebuild.")
IMAGERY_HELP = "Drape the map's imagery over the ground (the tiles the map has cached)."
BUILDINGS_HELP = "The airport pack's buildings as grey massing, standing where X-Plane seats them."
EXAGGERATION_HELP = "Vertical exaggeration of the terrain and the patch (×1 is true scale)."
RESET_HELP = "Back to the first view: above the airport from the south (Home or 0)."
#: The camera controls (the Mac's ``TerrainPreviewWindow.controlsHelp``).
CONTROLS_HELP = ("The scene stays still; you move and turn the viewpoint.\n"
                 "Keys (as in X-Plane): Q E turn left and right · R F tilt up and down · "
                 "← → move sideways · ↑ ↓ move forward and back · "
                 ", . move back and forward along the view · - = zoom · "
                 "Home or 0 back to the first view. Hold Shift for fast, Control for slow.\n"
                 "Mouse: drag to look around · scroll to move along the view · "
                 "Alt-drag or right-drag to move over the ground.")
LEGEND = ((SC.TERRAIN_COLOR, "DEM terrain"), (SC.PATCH_COLOR, "patch surface"),
          (SC.BUILDING_COLOR, "pack buildings"), (SC.MARKER_COLOR, "selected node"))

_PANEL = ("background: rgba(0,0,0,140); border-radius: 8px; color: rgba(255,255,255,217);")


def _divider(parent) -> QFrame:
    """The toolbar's thin vertical rule (the Mac's ``Divider``)."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.VLine)
    line.setFixedHeight(16)
    return line


#: X-Plane's default view keys (``X-Plane Keys.prf``) → ``SC.KEYS``.
_XP_KEYS = {
    Qt.Key_Left: "left", Qt.Key_Right: "right", Qt.Key_Up: "forward", Qt.Key_Down: "backward",
    Qt.Key_Period: "view_forward", Qt.Key_Greater: "view_forward",
    Qt.Key_Comma: "view_backward", Qt.Key_Less: "view_backward",
    Qt.Key_Equal: "zoom_in", Qt.Key_Plus: "zoom_in",
    Qt.Key_Minus: "zoom_out", Qt.Key_Underscore: "zoom_out",
    Qt.Key_Q: "turn_left", Qt.Key_E: "turn_right",
    Qt.Key_R: "tilt_up", Qt.Key_F: "tilt_down",
}
#: Back to the first view.
_RESET_KEYS = (Qt.Key_Home, Qt.Key_0)
# On macOS Qt reports ⌘ as Control and the Control key as Meta.
_SLOW = Qt.MetaModifier if sys.platform == "darwin" else Qt.ControlModifier
_MENU = Qt.ControlModifier if sys.platform == "darwin" else Qt.NoModifier


def key_speed(modifiers) -> str:
    """Shift fast, Control slow, otherwise X-Plane's plain (slow) rate."""
    if modifiers & Qt.ShiftModifier:
        return "fast"
    if modifiers & _SLOW:
        return "slow"
    return "normal"


class _MouseFilter(QObject):
    """Look / move from the 3D view's mouse, and X-Plane's view keys from
    its keyboard (read-only: no picking)."""

    def __init__(self, scene: SC.PreviewScene, view: QWidget):
        super().__init__(view)
        self.scene, self.view = scene, view

    def eventFilter(self, _obj, event) -> bool:          # noqa: N802 (Qt override)
        t = event.type()
        if t in (QEvent.KeyPress, QEvent.KeyRelease):
            return self._key(event, t == QEvent.KeyPress)
        if t == QEvent.FocusOut:
            self.scene.release_keys()
            return False
        kind = {QEvent.MouseButtonPress: "press", QEvent.MouseMove: "move",
                QEvent.Wheel: "wheel"}.get(t)
        if kind is None:
            return False
        h = self.view.height()
        if kind == "wheel":
            return self.scene.handle_mouse("wheel", None, None, None, h,
                                           event.angleDelta().y() / 8.0)
        if kind == "press":
            self.view.setFocus(Qt.MouseFocusReason)
        return self.scene.handle_mouse(kind, event.position(), event.buttons(),
                                       event.modifiers(), h)

    def _key(self, event, down: bool) -> bool:
        name = _XP_KEYS.get(event.key())
        if event.key() in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Meta):
            self.scene.set_speed(key_speed(event.modifiers()))
            return False
        if _MENU != Qt.NoModifier and event.modifiers() & _MENU:
            return False                       # ⌘ chords stay menu shortcuts
        if event.key() in _RESET_KEYS:
            if down and not event.isAutoRepeat():
                self.scene.go_home()
            return True
        if name is None:
            return False
        if event.isAutoRepeat():
            return True                        # held keys run on the camera's own clock
        self.scene.key(name, down, key_speed(event.modifiers()))
        return True


class PreviewWindow(QWidget):
    """"3D Preview · ICAO"."""

    def __init__(self, engine, patch_model, built=dict, imagery=None, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("3D Preview")
        self.setMinimumSize(560, 360)
        self.resize(980, 640)
        self.setStyleSheet("PreviewWindow { background: %s; }" % SC.BACKGROUND.name())
        self.scene = SC.PreviewScene(self)
        self.model = PreviewModel(engine, patch_model, self.scene, built, imagery, self)
        self.view = self._make_view()
        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: rgba(255,255,255,150);")
        self.toolbar = self._make_toolbar()
        self.legend = self._make_legend()
        self.chip = QLabel(self)
        self.chip.setWordWrap(True)
        self.chip.setMaximumWidth(520)
        self.chip.setStyleSheet("QLabel { %s font-family: Menlo, monospace; font-size: 11px;"
                                " padding: 3px 8px; }" % _PANEL)
        self.reset_button = QToolButton(self)
        self.reset_button.setText("↺ Reset view")
        self.reset_button.setToolTip(RESET_HELP + "\n\n" + CONTROLS_HELP)
        self.reset_button.setStyleSheet("QToolButton { %s padding: 4px 8px; }" % _PANEL)
        self.reset_button.clicked.connect(self.scene.reset_view)
        self.model.changed.connect(self.refresh)
        self.refresh()

    def _make_view(self) -> QWidget:
        from PySide6.QtQuickWidgets import QQuickWidget
        view = QQuickWidget(self)
        view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        view.setClearColor(SC.BACKGROUND)
        view.rootContext().setContextProperty("scene3d", self.scene)
        from PySide6.QtQml import QQmlComponent
        # the scene is compiled from the module's string (nothing to bundle)
        url = QUrl("file:///o4_preview3d.qml")
        self._component = QQmlComponent(view.engine(), view)
        self._component.setData(SC.SCENE_QML.encode("utf-8"), url)
        self._root = self._component.create(view.rootContext())
        self.qml_errors = [e.toString() for e in self._component.errors()]
        if self._root is not None:
            view.setContent(url, self._component, self._root)
        view.setFocusPolicy(Qt.StrongFocus)
        view.installEventFilter(_MouseFilter(self.scene, view))
        return view

    # ─── chrome ────────────────────────────────────────────────────────
    def _make_toolbar(self) -> QFrame:
        bar = QFrame(self)
        bar.setObjectName("preview3dToolbar")
        bar.setStyleSheet(
            "#preview3dToolbar { background: rgba(0,0,0,140); border-radius: 8px; }"
            "#preview3dToolbar QCheckBox, #preview3dToolbar QLabel { color: white; }"
            "#preview3dToolbar QToolButton { color: white; background: transparent;"
            " border: none; padding: 2px 6px; }"
            "#preview3dToolbar QToolButton:disabled { color: rgba(255,255,255,90); }"
            "#preview3dToolbar QToolButton:checked { background: rgba(255,255,255,60);"
            " border-radius: 4px; }"
            "#preview3dToolbar QCheckBox { spacing: 5px; margin-right: 4px; }"
            "#preview3dToolbar QCheckBox::indicator { width: 11px; height: 11px;"
            " border: 1px solid rgba(255,255,255,170); border-radius: 3px; }"
            "#preview3dToolbar QCheckBox::indicator:checked { background: rgba(255,255,255,200); }"
            "#preview3dToolbar QSlider::groove:horizontal { height: 3px;"
            " background: rgba(255,255,255,90); border-radius: 1px; }"
            "#preview3dToolbar QSlider::handle:horizontal { width: 12px; margin: -5px 0;"
            " background: white; border-radius: 6px; }"
            "#preview3dToolbar QFrame[frameShape=\"5\"] { color: rgba(255,255,255,70); }")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(8)
        self.mode_group = QButtonGroup(bar)
        self.mode_buttons = {}
        for mode in (DRP.PREVIEW, DRP.LAST_BUILD):
            b = QToolButton(bar)
            b.setText(mode)
            b.setCheckable(True)
            self.mode_group.addButton(b)
            self.mode_buttons[mode] = b
            row.addWidget(b)
            b.clicked.connect(lambda _c=False, m=mode: self.model.select_mode(m))
        self.imagery_box = QCheckBox("Imagery", bar)
        self.imagery_box.setToolTip(IMAGERY_HELP)
        self.imagery_box.toggled.connect(self.model.set_show_imagery)
        self.buildings_box = QCheckBox("Buildings", bar)
        self.buildings_box.setChecked(True)
        self.buildings_box.setToolTip(BUILDINGS_HELP)
        self.buildings_box.toggled.connect(self.model.set_show_buildings)
        self.wireframe_box = QCheckBox("Wireframe", bar)
        self.wireframe_box.toggled.connect(self.model.set_wireframe)
        row.addWidget(_divider(bar))
        for w in (self.imagery_box, self.buildings_box, self.wireframe_box):
            row.addWidget(w)
        row.addWidget(_divider(bar))
        row.addWidget(QLabel("Vertical ×", bar))
        self.exaggeration_label = QLabel("3.0", bar)
        self.exaggeration_label.setFixedWidth(30)
        row.addWidget(self.exaggeration_label)
        self.exaggeration_slider = QSlider(Qt.Horizontal, bar)
        self.exaggeration_slider.setRange(10, 100)           # tenths: ×1.0 … ×10.0
        self.exaggeration_slider.setValue(30)
        self.exaggeration_slider.setFixedWidth(110)
        self.exaggeration_slider.setToolTip(EXAGGERATION_HELP)
        self.exaggeration_slider.valueChanged.connect(
            lambda v: self.model.set_exaggeration(v / 10.0))
        row.addWidget(self.exaggeration_slider)
        return bar

    def _make_legend(self) -> QFrame:
        box = QFrame(self)
        box.setObjectName("preview3dLegend")
        box.setStyleSheet("#preview3dLegend { %s } QLabel { color: rgba(255,255,255,217);"
                          " font-size: 11px; }" % _PANEL)
        col = QVBoxLayout(box)
        col.setContentsMargins(9, 6, 9, 6)
        col.setSpacing(3)
        for color, text in LEGEND:
            line = QHBoxLayout()
            swatch = QLabel(box)
            swatch.setFixedSize(14, 8)
            swatch.setStyleSheet("background: %s; border-radius: 2px;" % QColor(color).name())
            line.addWidget(swatch)
            line.addWidget(QLabel(text, box))
            col.addLayout(line)
        return box

    def chip_text(self) -> str:
        m = self.model
        lines = []
        if m.terrain_error:
            lines.append("⚠ " + m.terrain_error)
        if m.chip:
            lines.append(m.chip + m.buildings_chip + m.drape_chip + m.last_build_chip)
        if m.last_build.mesh == "loading":
            lines.append("Reading the last build's mesh…")
        if m.buildings_status == "failed":
            lines.append("⚠ " + m.buildings_error)
        return "\n".join(lines)

    def refresh(self) -> None:
        m = self.model
        self.setWindowTitle("3D Preview · %s" % m.icao if m.icao else "3D Preview")
        self.status_label.setText(NO_PATCH_TEXT if m.status == NO_PATCH else
                                  "Reading the terrain under %s…" % m.icao if m.status == LOADING
                                  else "")
        self.status_label.setVisible(m.status in (NO_PATCH, LOADING))
        self.mode_buttons[m.last_build.mode].setChecked(True)
        last = self.mode_buttons[DRP.LAST_BUILD]
        last.setEnabled(m.last_build.can_show_last_build)
        for b in self.mode_buttons.values():
            b.setToolTip(m.last_build.reason or MODE_HELP)
        self.exaggeration_label.setText("%.1f" % m.exaggeration)
        text = self.chip_text()
        self.chip.setText(text)
        self.chip.setVisible(bool(text))
        self.chip.setToolTip("\n".join(m.buildings_missing))
        self._place()

    # ─── layout ────────────────────────────────────────────────────────
    def _place(self) -> None:
        w, h = self.width(), self.height()
        self.view.setGeometry(0, 0, w, h)
        for widget in (self.toolbar, self.legend, self.chip, self.reset_button, self.status_label):
            widget.adjustSize()
        self.toolbar.move(10, 10)
        self.legend.move(w - self.legend.width() - 10, 10)
        self.chip.move(10, h - self.chip.height() - 10)
        self.reset_button.move(w - self.reset_button.width() - 10,
                               h - self.reset_button.height() - 10)
        self.status_label.setGeometry(0, h // 2 - 20, w, 40)
        for widget in (self.toolbar, self.legend, self.chip, self.reset_button, self.status_label):
            widget.raise_()

    def resizeEvent(self, event) -> None:              # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._place()

    def showEvent(self, event) -> None:                # noqa: N802 (Qt override)
        super().showEvent(event)
        self.model.set_active(True)

    def closeEvent(self, event) -> None:               # noqa: N802 (Qt override)
        self.model.set_active(False)
        self.model.clear()
        super().closeEvent(event)
