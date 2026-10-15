"""The map's patch toolbar for the Qt app (mockup, top left; the Mac app's
``PatchModeToolbar``): the View | Edit segmented control, Undo / Redo and
the "Pack outlines" check box.  Shown while the patch layer is drawn;
pinned to the viewport's top-left corner (viewport children are dragged
along by scrolling, so the map re-pins it through :meth:`place`).
"""
from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout,
                               QToolButton)

from O4_Qt_Patch_Model import MODE_EDIT, MODE_VIEW

__all__ = ["PatchToolbar"]


class PatchToolbar(QFrame):
    """View | Edit, ↶ ↷, Pack outlines."""

    def __init__(self, viewport, controller, outlines=None):
        super().__init__(viewport)
        self.controller = controller
        self.model = controller.model
        self.outlines = outlines
        self.setObjectName("patchToolbar")
        self.setStyleSheet(
            "#patchToolbar { background: rgba(0,0,0,115); border-radius: 8px; }"
            "#patchToolbar QCheckBox { color: white; }"
            "#patchToolbar QToolButton { color: white; background: transparent;"
            " border: none; padding: 2px 6px; }"
            "#patchToolbar QToolButton:disabled { color: rgba(255,255,255,90); }"
            "#patchToolbar QToolButton:checked { background: rgba(255,255,255,60);"
            " border-radius: 4px; }")
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(4)
        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}
        for mode in (MODE_VIEW, MODE_EDIT):
            b = QToolButton(self)
            b.setText(mode)
            b.setCheckable(True)
            b.setToolTip("View the patch, or edit its nodes.")
            self.mode_group.addButton(b)
            self.mode_buttons[mode] = b
            row.addWidget(b)
            b.clicked.connect(lambda _c=False, m=mode: self.model.set_mode(m))
        stack = self.model.undo_stack
        self.undo_button = QToolButton(self)
        self.undo_button.setText("↶")
        self.undo_button.clicked.connect(stack.undo)
        self.redo_button = QToolButton(self)
        self.redo_button.setText("↷")
        self.redo_button.clicked.connect(stack.redo)
        row.addWidget(self.undo_button)
        row.addWidget(self.redo_button)
        self.outlines_box = None
        if outlines is not None:
            self.outlines_box = QCheckBox("Pack outlines", self)
            self.outlines_box.toggled.connect(outlines.set_enabled)
            outlines.changed.connect(self.refresh)
            row.addWidget(self.outlines_box)
        self.model.status_changed.connect(self.refresh)
        controller.state_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        showing = self.controller.is_showing
        self.setVisible(showing)
        if not showing:
            return
        self.mode_buttons[self.model.mode].setChecked(True)
        stack = self.model.undo_stack
        self.undo_button.setEnabled(stack.canUndo())
        self.redo_button.setEnabled(stack.canRedo())
        self.undo_button.setToolTip(("Undo " + stack.undoText()).strip())
        self.redo_button.setToolTip(("Redo " + stack.redoText()).strip())
        if self.outlines_box is not None:
            self.outlines_box.blockSignals(True)
            self.outlines_box.setChecked(self.outlines.enabled)
            self.outlines_box.blockSignals(False)
            self.outlines_box.setToolTip(self.outlines.help_text)
        self.adjustSize()
        self.place()

    def place(self) -> None:
        self.move(8, 8)
        self.raise_()
