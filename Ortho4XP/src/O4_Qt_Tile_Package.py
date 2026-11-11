"""``.xptb`` packages in the Qt window (#2014; mac-app parity:
``TilePackageSheets.swift``).

* File ▸ Export Package… (and the map's tile menu) is AIRPORT-FIRST
  (owner 2026-11-11T16:10Z): pick one airport (it opens on the one with a
  custom patch), then a kind — Exact match, Airport patch only, or Whole
  tile (last) — each with the engine's explanation, estimated size and
  the recipient's downloads and build time
  (``o4_engine.library.package_estimate``), and the maker's optional
  title, name, notes and link.
* A package dropped on the map or the window, opened on the app icon or
  given as a launch argument (Windows "Open with" and the file
  association, Linux desktop files) is planned by the engine
  (``o4_engine.library.package_plan``) and shown: its tiles and airports,
  the packs they match, its sources and terms, and, per airport that
  already has a patch, "Keep my patch" or "Back up mine and use the
  package's".  Install runs ``package_install``.
* File ▸ Combine Packages… merges several packages into one.
* For an airport served by the user's own pack, the export window also
  holds the pack author's rows (RULINGS 2026-11-11m (3); mac app:
  ``developerRows``): "Objects are final", "Apply XPTerrainBuilder's
  object fixes into my pack…" and "Save into this airport's pack folder"
  (``o4_engine.library.package_developer``).
* A package an installed pack ships (``PackPackage``, RULINGS 11m (4)) is
  a log line every build and one tray notice per package and state; a
  ``conflict`` opens the install dialog on it (:func:`on_pack_package`).

``O4_Qt_Patch_Drop`` hands this module every dropped package.
"""
from __future__ import annotations

import os

from o4_engine import library as LIB
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

__all__ = ["EXPORT_TITLE", "INSTALL_TITLE", "INSTALL", "KEEP_MINE", "USE_THEIRS",
           "COMBINE_TITLE", "AIRPORT_LABEL", "WHOLE_TILE_ONLY", "ESTIMATE_NOTE",
           "INTO_PACK", "OBJECTS_LABEL", "OBJECTS_DEFAULT", "OBJECTS_FINAL",
           "OBJECTS_APPLIED", "APPLY_FIXES", "APPLY_CONFIRM", "SUFFIXES",
           "is_package", "offer", "export", "combine", "on_pack_package"]

#: The words both apps use (the Mac app: ``O4TilePackageCopy``).
EXPORT_TITLE = "Export Package…"
INSTALL_TITLE = "Install package?"
INSTALL = "Install"
KEEP_MINE = "Keep my patch"
USE_THEIRS = "Back up mine and use the package's"
COMBINE_TITLE = "Combine Packages…"
AIRPORT_LABEL = "Airport"
WHOLE_TILE_ONLY = "Whole tile (no airport)"
ESTIMATE_NOTE = "Sizes and times are estimates; imagery is never included."
#: The export window's developer rows (RULINGS 2026-11-11m (3)).
INTO_PACK = "Save into this airport's pack folder"
OBJECTS_LABEL = "Objects of my pack"
OBJECTS_DEFAULT = "Let XPTerrainBuilder fit them"
OBJECTS_FINAL = "Objects are final"
OBJECTS_APPLIED = "XPTerrainBuilder's fixes are applied"
APPLY_FIXES = "Apply XPTerrainBuilder's object fixes into my pack…"
APPLY_CONFIRM = ("The object stage's splits and seats become your pack's own "
                 "files; the originals are moved to the pack's "
                 "XPTerrainBuilder/backup folder, and recipients of a package "
                 "saved from it leave its objects alone.")

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
    """The airport, a kind each with its explanation and estimate, the
    pack author's rows, and the maker's fields.  ``estimate(airport)`` is
    the engine's ``package_estimate`` for the dialog's tiles and
    ``developer(airport, action)`` its ``package_developer`` (seams for
    tests; a refusal hides the pack rows)."""

    def __init__(self, parent, found: dict, estimate, developer=None):
        super().__init__(parent)
        self.setWindowTitle(EXPORT_TITLE.rstrip("…"))
        self.estimate, self.rows = estimate, []
        self.developer, self.pack = developer, None
        layout = QVBoxLayout(self)
        custom = {i for icaos in (found.get("custom") or {}).values() for i in icaos}
        self.airport = QComboBox()
        for icao in sorted({i for icaos in found["tiles"].values() for i in icaos}):
            self.airport.addItem("%s (custom patch)" % icao if icao in custom else icao, icao)
        self.airport.addItem(WHOLE_TILE_ONLY, "")
        start = self.airport.findData(found.get("default") or "")
        self.airport.setCurrentIndex(max(0, start))
        form = QFormLayout()
        form.addRow(AIRPORT_LABEL, self.airport)
        layout.addLayout(form)
        self.kinds = QVBoxLayout()
        self.group = QButtonGroup(self)
        layout.addLayout(self.kinds)
        layout.addWidget(QLabel(ESTIMATE_NOTE))
        layout.addLayout(self._pack_rows())
        fields = QFormLayout()
        self.fields = {}
        for key, label in (("title", "Title"), ("creator", "Made by"),
                           ("notes", "Notes"), ("url", "Link")):
            self.fields[key] = QLineEdit()
            fields.addRow(label, self.fields[key])
        layout.addLayout(fields)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.save = buttons.addButton("Save…", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.airport.currentIndexChanged.connect(self._estimate)
        self.airport.currentIndexChanged.connect(lambda *_a: self._read_pack())
        self._estimate()
        self._read_pack()

    def _pack_rows(self) -> QFormLayout:
        """The pack author's three controls (hidden without a pack)."""
        rows = QFormLayout()
        self.pack_label = QLabel("")
        self.objects = QComboBox()
        self.objects.addItem(OBJECTS_DEFAULT, "")
        self.objects.addItem(OBJECTS_FINAL, "final")
        self.objects.addItem(OBJECTS_APPLIED, "applied")
        self.objects.activated.connect(self._objects_chosen)
        self.apply = QPushButton(APPLY_FIXES)
        self.apply.clicked.connect(self._apply)
        self.into_pack = QCheckBox(INTO_PACK)
        rows.addRow(self.pack_label)
        rows.addRow(OBJECTS_LABEL, self.objects)
        rows.addRow(self.apply)
        rows.addRow(self.into_pack)
        self.pack_widgets = (self.pack_label, self.objects, self.apply, self.into_pack)
        return rows

    def _read_pack(self, action: str = "read") -> None:
        """The chosen airport's pack, after ``action``."""
        self.pack = None
        airport = self.airport.currentData() or ""
        if airport and self.developer is not None:
            try:
                self.pack = self.developer(airport, action)
            except (ValueError, OSError) as error:
                if action != "read":
                    QMessageBox.warning(self, EXPORT_TITLE, str(error))
                    return self._read_pack()
        for widget in self.pack_widgets:
            widget.setVisible(self.pack is not None)
        if self.pack is None:
            self.into_pack.setChecked(False)
            return
        self.pack_label.setText("Your pack: %s" % self.pack["pack"])
        self.objects.setCurrentIndex(max(0, self.objects.findData(self.pack["objects"])))
        self.apply.setEnabled(bool(self.pack["modified"]))

    def _objects_chosen(self, *_args) -> None:
        mode = self.objects.currentData()
        if self.pack is not None and mode != self.pack["objects"] and mode != "applied":
            self._read_pack("final" if mode == "final" else "default")
        elif self.pack is not None:
            self._read_pack()

    def _confirm_apply(self) -> bool:
        """A seam for tests."""
        return QMessageBox.question(self, APPLY_FIXES, APPLY_CONFIRM) == QMessageBox.Yes

    def _apply(self) -> None:
        if self.pack is not None and self._confirm_apply():
            self._read_pack("apply")

    def _estimate(self, *_args) -> None:
        """Every kind estimated again for the airport chosen."""
        for button in self.group.buttons():
            self.group.removeButton(button)
        while self.kinds.count():
            widget = self.kinds.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        try:
            self.rows = self.estimate(self.airport.currentData() or "")["kinds"]
        except (ValueError, OSError) as error:
            self.rows = []
            self.kinds.addWidget(QLabel(str(error)))
        for row in self.rows:
            button = QRadioButton("%s — %s\n%s" % (row["title"], row["explanation"],
                                                    row["figures"] if row["available"]
                                                    else row["why"]))
            button.setProperty("kind", row["kind"])
            button.setEnabled(bool(row["available"]))
            self.group.addButton(button)
            self.kinds.addWidget(button)
        first = next((b for b in self.group.buttons() if b.isEnabled()), None)
        if first is not None:
            first.setChecked(True)
        self.save.setEnabled(first is not None)

    def answer(self) -> dict:
        checked = self.group.checkedButton()
        kind = checked.property("kind") if checked is not None else "tile"
        airport = self.airport.currentData() or ""
        return {"airports": [airport] if airport and kind != "tile" else [],
                "kind": kind, "into_pack": bool(self.pack is not None and kind != "tile"
                                               and self.into_pack.isChecked()),
                **{k: f.text() for k, f in self.fields.items()}}

    def ask(self):
        """The answer on Save, None on Cancel (a seam for tests)."""
        return self.answer() if self.exec() == QDialog.Accepted else None


def _default_name(tile_airports: dict, answer: dict) -> str:
    """``XPTerrainBuilder_<ICAO>_<kind>.xptb``, or the tiles' package name."""
    from tile_bundle import package
    if answer["airports"]:
        return "XPTerrainBuilder_%s_%s.xptb" % (answer["airports"][0], answer["kind"])
    return package.package_name(tile_airports)


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
        found = LIB.package_airports(tiles, _tiles_dir(window))
    except (ValueError, OSError) as error:
        QMessageBox.warning(window, EXPORT_TITLE, str(error))
        return None
    answer = _ExportDialog(window, found, lambda airport: LIB.package_estimate(
        tiles, _tiles_dir(window), airport), lambda airport, action: LIB.package_developer(
        airport, tiles, _tiles_dir(window), action)).ask()
    if answer is None:
        return None
    out = "" if answer["into_pack"] else _save_path(
        window, _default_name(found["tiles"], answer))
    if not out and not answer["into_pack"]:
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


#: The packages already noticed (one tray notice per package and state).
_NOTICED: set = set()


def on_pack_package(window, event) -> None:
    """A ``PackPackage`` (RULINGS 2026-11-11m (4); mac app:
    ``BuildModel.packPackage``): the log line every build, one tray notice
    per package and state, and for a ``conflict`` the install dialog on the
    package (the 11l (3) "Keep my patch" question)."""
    import types

    import O4_Qt_Fly_Divert as QTFLYDIVERT
    print(event.text)
    key = (event.path, event.state)
    if key in _NOTICED:
        return
    _NOTICED.add(key)
    QTFLYDIVERT.post_notice(window, types.SimpleNamespace(
        title="XPTerrainBuilder", text=event.text, severity=""))
    if event.state == "conflict":
        offer(window, [event.path])
