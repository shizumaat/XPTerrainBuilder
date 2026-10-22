"""Settings ▸ General's app-level sections, as the Mac app shows them (#1267).

``SettingsView.swift``'s GeneralPane, section for section:

* **Application** — the version, the X-Plane folder's status, and the data
  folder with its chooser (#1266: the folder the Mac app uses too).
* **Build Engine** — which engine runs, its version, the runtime, the
  imagery provider count and where the config schema comes from.

Provider Accounts follows them (``O4_Qt_Settings._ProviderSignInSection``).
The Mac app's Appearance picker has no Qt counterpart: Qt follows the
system theme.  Building these never touches the network.
"""

import os
import sys

import O4_Build_Info as BUILD
import O4_File_Names as FNAMES
import O4_Settings_Model as SM
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["ApplicationSection", "BuildEngineSection", "SECTION_TITLES",
           "app_version"]

#: The General sections above the engine defaults, in the Mac app's order.
SECTION_TITLES = ("Application", "Build Engine", "Provider Accounts")

OK_STYLE = "color: #2E9E4F;"
WARN_STYLE = "color: #D9822B;"
NOTE_STYLE = "color: gray; font-size: 11px;"

ENGINE_FOOTER = (
    "XPTerrainBuilder ships with its own build engine (derived from "
    "Ortho4XP) and uses it by default.")
RESTART_NOTE = "XPTerrainBuilder uses this folder the next time it starts."

#: The Mac app's VERSION resource, read when no artifact stamped one.
_SOURCE_VERSION = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Sources", "XPTerrainBuilder", "Resources", "VERSION")


def app_version():
    """The app version the Mac app's Settings shows (``AppVersion.current``)."""
    stamped = BUILD.build_info().app
    if stamped != BUILD.DEV:
        return stamped
    try:
        with open(_SOURCE_VERSION, encoding="utf-8") as handle:
            return handle.read().strip() or BUILD.DEV
    except OSError:
        return BUILD.DEV


def _header(layout, title):
    label = QLabel("<b>%s</b>" % title)
    label.setContentsMargins(0, 14, 0, 2)
    layout.addWidget(label)
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: palette(mid);")
    layout.addWidget(line)
    return label


def _row(layout, title, *widgets):
    row = QHBoxLayout()
    name = QLabel(title)
    name.setMinimumWidth(130)
    row.addWidget(name)
    for widget in widgets:
        row.addWidget(widget, 1 if isinstance(widget, QLabel) else 0)
    layout.addLayout(row)


def _value(text="", style=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if style:
        label.setStyleSheet(style)
    return label


class _Section(QWidget):
    """A titled block; :meth:`matches` serves the settings search."""

    title = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.header = _header(self.layout_, self.title)
        self._haystack = self.title.lower()

    def _searchable(self, *words):
        self._haystack += " " + " ".join(words).lower()

    def matches(self, query):
        return query in self._haystack


class ApplicationSection(_Section):
    title = "Application"

    def __init__(self, xplane_dir="", parent=None):
        super().__init__(parent)
        self.version_label = _value("XPTerrainBuilder %s" % app_version())
        self.version_label.setToolTip("Include this when reporting a problem.")
        _row(self.layout_, "Version", self.version_label)

        self.xplane_label = _value()
        self.xplane_status = _value()
        _row(self.layout_, "X-Plane Folder", self.xplane_label)
        _row(self.layout_, "Status", self.xplane_status)
        self.set_xplane(xplane_dir)

        self.data_label = _value(FNAMES.current_data_root())
        self.data_label.setToolTip(FNAMES.current_data_root())
        self.data_button = QPushButton("Choose…")
        self.data_button.clicked.connect(self.choose_data_folder)
        _row(self.layout_, "Data Folder", self.data_label, self.data_button)
        self.data_note = _value("", NOTE_STYLE)
        self.data_note.setVisible(False)
        self.layout_.addWidget(self.data_note)
        self._searchable("version x-plane folder data folder storage")

    def set_xplane(self, path):
        """Show ``path`` and the SAME verdict Build uses (beta plan §1 B2)."""
        path = (path or "").strip()
        self.xplane_label.setText(path or "Not set")
        problem = SM.xplane_install_problem(path) if path else None
        self.xplane_status.setVisible(bool(path))
        self.xplane_status.setText(problem or "Looks like an X-Plane installation")
        self.xplane_status.setStyleSheet(WARN_STYLE if problem else OK_STYLE)

    def choose_data_folder(self):
        start = FNAMES.current_data_root()
        chosen = QFileDialog.getExistingDirectory(self, "Choose a Data Folder", start)
        if chosen:
            self.adopt_data_folder(chosen)

    def adopt_data_folder(self, path):
        """Remember ``path`` for both apps' next launch; refuse an unusable one."""
        path = os.path.abspath(os.path.expanduser(path))
        problem = FNAMES.data_root_problem(path)
        if problem:
            QMessageBox.warning(
                self, "Folder not usable",
                "XPTerrainBuilder cannot write to this folder:\n\n%s\n\n%s"
                % (path, problem))
            return False
        FNAMES.write_data_root_pointer(path)
        self.data_label.setText(path)
        self.data_label.setToolTip(path)
        pending = os.path.normcase(path) != os.path.normcase(
            FNAMES.current_data_root())
        self.data_note.setText(RESTART_NOTE)
        self.data_note.setVisible(pending)
        return True


class BuildEngineSection(_Section):
    title = "Build Engine"

    def __init__(self, parent=None):
        super().__init__(parent)
        info = BUILD.build_info()
        frozen = FNAMES.is_frozen_app()
        _row(self.layout_, "Engine", _value(
            "Bundled with the app" if frozen
            else "This checkout: %s" % os.path.abspath(".")))
        _row(self.layout_, "Status", _value("Engine %s" % info.engine, OK_STYLE))
        _row(self.layout_, "Runtime", _value(
            "Self-contained — no Python setup needed" if frozen
            else "Python %d.%d — %s" % (sys.version_info[0], sys.version_info[1],
                                        sys.executable),
            OK_STYLE))
        self.providers_label = _value(self._providers_text(), "color: gray;")
        _row(self.layout_, "Imagery Providers", self.providers_label)
        _row(self.layout_, "Config Schema", _value(
            "From engine %s" % info.engine, "color: gray;"))
        footer = _value(ENGINE_FOOTER, NOTE_STYLE)
        self.layout_.addWidget(footer)
        self._searchable("engine status runtime python imagery providers schema")

    @staticmethod
    def _providers_text():
        try:
            import O4_Imagery_Utils as IMG
        except Exception:
            return "Not loaded"
        count = len(getattr(IMG, "providers_dict", {}) or {})
        return "{:,} available".format(count)
