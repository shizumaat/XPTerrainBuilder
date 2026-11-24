"""Qt dialog for the Allen Coral Atlas local reef bathymetry library.

The GUI face of :mod:`O4_Coral_Atlas` (which stays GUI-free): how to get
packages by hand, the library folder and a rescan.  The engine never
signs in to the Atlas or downloads from it: its Terms of Use bar
automated retrieval.
"""

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

import O4_Coral_Atlas as CORAL

INSTRUCTIONS = (
    "<b>Allen Coral Atlas — 10 m reef bathymetry</b><br>"
    "The Atlas maps shallow reefs worldwide (CC-BY 4.0). Downloading its"
    " packages needs a <i>free</i> Atlas account, and you do that yourself"
    " on the Atlas website; XPTerrainBuilder does not sign in or download"
    " for you.<br><br>"
    "<b>1.</b> Open the Atlas, sign in or register, and download the"
    " bathymetry package for your area.<br>"
    "<b>2.</b> Drop the zip into the library folder"
    " (<code>Elevation_data/AllenCoralAtlas/</code>), then Rescan.<br>"
    "<b>3.</b> Rebuild the tile (Step 2.5 + Step 3): tiles covered by"
    " library data use it automatically."
)


class CoralAtlasDialog(QDialog):
    """Manual instructions + library management."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Allen Coral Atlas reef bathymetry")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        instructions = QLabel(INSTRUCTIONS)
        instructions.setWordWrap(True)
        instructions.setTextFormat(Qt.RichText)
        layout.addWidget(instructions)

        buttons = QHBoxLayout()
        open_site = QPushButton("Open allencoralatlas.org")
        open_site.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(CORAL.ATLAS_WEBSITE_URL))
        )
        buttons.addWidget(open_site)
        open_library = QPushButton("Open library folder")
        open_library.clicked.connect(self._open_library_folder)
        buttons.addWidget(open_library)
        rescan = QPushButton("Rescan library")
        rescan.clicked.connect(self._rescan_library)
        buttons.addWidget(rescan)
        layout.addLayout(buttons)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        layout.addWidget(self.log_view)

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _open_library_folder(self) -> None:
        os.makedirs(CORAL.library_directory(), exist_ok=True)
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(CORAL.library_directory())
        )

    def _rescan_library(self) -> None:
        entries = CORAL.rescan_library(self._append_log)
        self._append_log(
            "Library rescanned: %d bathymetry raster(s) indexed."
            % len(entries)
        )
