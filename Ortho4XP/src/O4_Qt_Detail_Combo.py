"""The imagery detail picker: plain wording shown, the zoom level kept.

Issue #831: a user picks "Standard (~2 m per pixel) · ZL16", never a bare
"16".  The window, the wizard and their tests speak zoom levels through
the combo's text API (``currentText() == "16"``, ``setCurrentText("17")``,
``findText``); :class:`DetailCombo` keeps that API in zoom levels while
each item DISPLAYS its glossary label (``O4_Glossary.detail_choice``).
"""

import O4_Glossary as GLOSSARY
from PySide6.QtWidgets import QComboBox

__all__ = ["DetailCombo"]


class DetailCombo(QComboBox):
    """A combo of zoom levels whose items read as plain detail levels.

    The text API is in zoom levels: ``currentText()`` is ``"16"`` (``""``
    when unresolved), ``findText("16")`` the index of ZL16."""

    def __init__(self, levels, parent=None):
        super().__init__(parent)
        for zl in levels:
            self.addItem(GLOSSARY.detail_choice(zl), zl)

    def currentText(self):  # noqa: N802 (Qt API)
        zl = self.currentData()
        return "" if zl is None else str(zl)

    def findText(self, text, *args):  # noqa: N802 (Qt API)
        try:
            return self.findData(int(text))
        except (TypeError, ValueError):
            return -1

    def setCurrentText(self, text):  # noqa: N802 (Qt API)
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)
