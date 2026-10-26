"""The "Set elevation…" dialog for the selected patch shapes (issue #1357;
the Mac app's ``PatchSetElevationSheet``).

It states first what the edit touches ("N shared nodes, M neighbouring
shapes affected", :mod:`O4_Qt_Patch_Elevation`), then takes one value in
metres or feet, prefilled with the selection's mean ``alt_abs``.  "Also
set shared nodes" is on by default.  Apply is ONE undoable edit
(``PatchEditModel.set_shapes_alt``), saved through the normal path.
"""
from __future__ import annotations

import O4_Qt_Patch_Elevation as ELEV
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

__all__ = ["SetElevationDialog", "TITLE"]

TITLE = "Set elevation…"


def _number(text: str) -> float | None:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


class SetElevationDialog(QDialog):
    """See the module docstring; ``model`` is the ``PatchEditModel``."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Set elevation")
        self.plan = ELEV.plan(model.doc, model.shape_selection)
        n = len(model.shape_selection)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("<b>%s</b>" % ("1 shape" if n == 1 else "%s shapes" % format(n, ","))))
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        v.addWidget(self.summary)
        row = QHBoxLayout()
        row.addWidget(QLabel("Elevation"))
        self.value = QLineEdit()
        row.addWidget(self.value, 1)
        self.unit = QComboBox()
        self.unit.addItems(ELEV.UNITS)
        row.addWidget(self.unit)
        v.addLayout(row)
        self.shared = QCheckBox("Also set shared nodes (they move the neighbouring shapes)")
        self.shared.setChecked(True)
        v.addWidget(self.shared)
        if self.plan.mean_alt is None:
            v.addWidget(QLabel("These nodes take their elevation from the mesh today."))
        self.buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        self.apply_button = self.buttons.button(QDialogButtonBox.Apply)
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self.apply)
        self.buttons.rejected.connect(self.reject)
        v.addWidget(self.buttons)
        self._unit = ELEV.UNITS[0]
        self._fill(self.plan.mean_alt)
        self.unit.currentTextChanged.connect(self._unit_changed)
        self.value.textChanged.connect(self._refresh)
        self.shared.toggled.connect(self._refresh)
        self._refresh()

    def _fill(self, alt_m: float | None) -> None:
        self.value.setText("" if alt_m is None else "%.2f" % ELEV.from_metres(alt_m, self._unit))

    def _unit_changed(self, unit: str) -> None:
        """Keep the typed value: convert it into the new unit."""
        v = _number(self.value.text())
        metres = None if v is None else ELEV.to_metres(v, self._unit)
        self._unit = unit
        self._fill(metres)

    def _refresh(self, *_args) -> None:
        self.summary.setText(ELEV.summary(self.plan, self.shared.isChecked()))
        self.apply_button.setEnabled(_number(self.value.text()) is not None)

    def metres(self) -> float | None:
        v = _number(self.value.text())
        return None if v is None else ELEV.to_metres(v, self._unit)

    def apply(self) -> bool:
        alt = self.metres()
        if alt is None:
            return False
        done = self.model.set_shapes_alt(alt, self.shared.isChecked())
        self.accept()
        return done
