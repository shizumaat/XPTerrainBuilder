"""``.xptb`` packages in the Qt window (#2014; mac-app parity:
``TilePackageSheets.swift``).

* File ▸ Export Package… (and the map's tile menu) saves the selected
  tiles' package — whole tiles, or the airports ticked in the dialog —
  with its maker's optional title, name, notes and link.
* A package dropped on the map or the window, opened on the app icon or
  given as a launch argument (Windows "Open with" and the file
  association, Linux desktop files) is planned by the engine
  (``o4_engine.library.package_plan``) and shown: its tiles and airports,
  the packs they match, its sources and terms, and, per airport that
  already has a patch, "Keep my patch" or "Back up mine and use the
  package's".  Install runs ``package_install``.
* File ▸ Combine Packages… merges several packages into one.

``O4_Qt_Patch_Drop`` hands this module every dropped package.
"""
from __future__ import annotations

import os

from o4_engine import library as LIB
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QVBoxLayout)

__all__ = ["EXPORT_TITLE", "INSTALL_TITLE", "INSTALL", "KEEP_MINE", "USE_THEIRS",
           "COMBINE_TITLE", "SUFFIXES", "is_package", "offer", "export",
           "combine"]

#: The words both apps use (the Mac app: ``O4TilePackageCopy``).
EXPORT_TITLE = "Export Package…"
INSTALL_TITLE = "Install package?"
INSTALL = "Install"
KEEP_MINE = "Keep my patch"
USE_THEIRS = "Back up mine and use the package's"
COMBINE_TITLE = "Combine Packages…"

#: A package's and a tile bundle's suffixes (``tile_bundle.SUFFIXES``).
SUFFIXES = (".xptb", ".xptbundle")
_FILTER = "XPTerrainBuilder package (*.xptb *.xptbundle)"


def is_package(path: str) -> bool:
    """True for a file the package install takes (not a patch drop)."""
    return str(path).lower().endswith(SUFFIXES)


def _tiles_dir(window) -> str:
    return getattr(window, "working_dir", lambda: "")()


class _InstallDialog(QDialog):
    """The plan's lines, a choice per conflicting airport, Install."""

    def __init__(self, parent, plan: dict):
        super().__init__(parent)
        self.setWindowTitle(INSTALL_TITLE)
        layout = QVBoxLayout(self)
        text = QPlainTextEdit("\n".join(plan["summary"]))
        text.setReadOnly(True)
        layout.addWidget(text)
        self.combos = {}
        for conflict in plan.get("conflicts") or []:
            combo = QComboBox()
            combo.addItem(KEEP_MINE, "keep")
            combo.addItem(USE_THEIRS, "replace")
            combo.setToolTip("Backed up as %s in the tile's patch folder"
                             % os.path.basename(conflict["backup"]))
            layout.addWidget(QLabel("%s (tile %s): %s" % (
                conflict["icao"], conflict["tile"], conflict["installed"])))
            layout.addWidget(combo)
            self.combos[conflict["icao"]] = combo
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.addButton(INSTALL, QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choices(self) -> dict:
        return {icao: combo.currentData() for icao, combo in self.combos.items()}

    def ask(self):
        """The choices on Install, None on Cancel (a seam for tests)."""
        return self.choices() if self.exec() == QDialog.Accepted else None


def offer(window, paths) -> bool:
    """Show what installing the first package of ``paths`` does and
    install it on "Install".  True when it was installed."""
    path = list(paths)[0]
    try:
        plan = LIB.package_plan(path, _tiles_dir(window))
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, INSTALL_TITLE, str(error))
        return False
    choices = _InstallDialog(window, plan).ask()
    if choices is None:
        return False
    try:
        done = LIB.package_install(path, _tiles_dir(window), choices)
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, INSTALL_TITLE, str(error))
        return False
    left = {k: v for k, v in (done.get("downloads_left") or {}).items() if v}
    print("Installed %s for tile %s: %s" % (
        done.get("title") or "the package",
        ", ".join(t["tile"] for t in done["tiles"]),
        "building it downloads only imagery." if not left
        else "still to download: %s" % left))
    for name in ("refresh_tiles", "_refresh_custom_patch_tiles"):
        refresh = getattr(window, name, None)
        if refresh is not None:
            refresh()
    return True


class _ExportDialog(QDialog):
    """The tiles, an airport tick box each, and the maker's fields."""

    def __init__(self, parent, tiles, airports: dict):
        super().__init__(parent)
        self.setWindowTitle(EXPORT_TITLE.rstrip("…"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Tiles %s. Imagery is never included. Tick airports to export only "
            "them; none ticked exports the whole tiles." % ", ".join(sorted(airports))))
        self.boxes = {}
        for tile in sorted(airports):
            for icao in airports[tile]:
                box = QCheckBox("%s (tile %s)" % (icao, tile))
                layout.addWidget(box)
                self.boxes[icao] = box
        form = QFormLayout()
        self.fields = {}
        for key, label in (("title", "Title"), ("creator", "Made by"),
                           ("notes", "Notes"), ("url", "Link")):
            self.fields[key] = QLineEdit()
            form.addRow(label, self.fields[key])
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttons.addButton("Save…", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def answer(self) -> dict:
        return {"airports": sorted(i for i, b in self.boxes.items() if b.isChecked()),
                **{k: f.text() for k, f in self.fields.items()}}

    def ask(self):
        """The answer on Save, None on Cancel (a seam for tests)."""
        return self.answer() if self.exec() == QDialog.Accepted else None


def _save_path(window, name: str) -> str:
    """Where to save (a seam for tests)."""
    return QFileDialog.getSaveFileName(window, EXPORT_TITLE.rstrip("…"), name,
                                       _FILTER)[0]


def export(window, tiles) -> dict | None:
    """File ▸ Export Package… for ``tiles`` (``[(lat, lon)]``)."""
    tiles = sorted(tiles)
    if not tiles:
        return None
    try:
        found = LIB.package_airports(tiles, _tiles_dir(window))["tiles"]
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, EXPORT_TITLE, str(error))
        return None
    answer = _ExportDialog(window, tiles, found).ask()
    if answer is None:
        return None
    from tile_bundle import package
    out = _save_path(window, package.package_name(found))
    if not out:
        return None
    try:
        done = LIB.package_save(tiles, _tiles_dir(window), out, **answer)
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, EXPORT_TITLE, str(error))
        return None
    print("Saved package %s (%.1f MB)%s." % (os.path.basename(done["path"]),
                                             done["bytes"] / 1e6,
                                             ", non-commercial" if done["noncommercial"] else ""))
    return done


def combine(window) -> dict | None:
    """File ▸ Combine Packages…: several packages into one."""
    paths = QFileDialog.getOpenFileNames(window, COMBINE_TITLE.rstrip("…"), "",
                                         "XPTerrainBuilder package (*.xptb)")[0]
    if len(paths) < 2:
        return None
    out = _save_path(window, "XPTerrainBuilder_combined.xptb")
    if not out:
        return None
    try:
        done = LIB.package_merge(paths, out)
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, COMBINE_TITLE, str(error))
        return None
    print("Combined %d packages into %s." % (len(paths), os.path.basename(out)))
    return done
