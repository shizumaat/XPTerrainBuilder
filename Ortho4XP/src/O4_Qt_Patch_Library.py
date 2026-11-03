"""The shared patch library in the Qt window (#1699 phase 2) — the twin of
the Mac app's ``PatchLibraryView.swift``, calling the same engine
functions in process (``o4_engine.library.patch_library_command``).

Three homes, each the Mac app's:

* Library dialog ▸ "Patch library" (:class:`PatchLibraryBox`): the check
  when the app opens, one row per airport with Build / Update / Ignore;
* Library dialog ▸ "Publish patch…" (:class:`PublishPatchDialog`):
  preview, licence, GitHub sign-in, pull request;
* Build box ▸ Airports card ▸ "Library patches" (:class:`LibraryMatchList`):
  the match list for the airports this build grades.

Work runs on daemon threads; results come back through queued signals.
"""

import threading
import time

from o4_engine import library as LIB
from O4_Qt_Widgets import wrap_and_never_widen
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

__all__ = ["TITLE", "LICENCE_TEXT", "NONCOMMERCIAL_TEXT", "terms_lines",
           "check_at_launch", "applied_text",
           "PatchLibraryBox", "LibraryMatchList", "PublishPatchDialog"]

TITLE = "Patch library"
LICENCE_TEXT = ("I publish this patch under the Open Database License (ODbL) 1.0 "
                "and each source's terms shown above.")
NONCOMMERCIAL_TEXT = ("Non-commercial: a source allows non-commercial use only, "
                      "so the whole entry is marked non-commercial.")


def terms_lines(preview):
    """The preview's lines for each source's terms (owner Q319), as the
    Mac app's ``PatchLibraryText.terms`` writes them."""
    lines = ["Source: %s — %s%s" % (s["provider"], s["licence"],
                                     " · non-commercial" if s["noncommercial"] else "")
             for s in preview.get("sources") or []]
    return lines + ([NONCOMMERCIAL_TEXT] if preview.get("noncommercial") else [])
KINDS = (("freeware", "Free pack"), ("payware", "Paid pack"))


def command(name):
    return LIB.patch_library_command(name)


def _state_text(row) -> str:
    """The Mac app's ``PatchLibraryText.state``."""
    if row["state"] == "available":
        return "patch v%d available" % row["version"]
    if row["state"] == "newer":
        return "v%d available (you have v%d)" % (row["version"], row.get("local_version") or 0)
    if row["state"] == "pack_changed":
        return "your pack changed — the next build solves it here"
    return "patches for another version of this pack"


def _tier_text(match) -> str:
    return {"exact": "exact match", "same_pack": "same pack, other version"}.get(
        match["tier"], "other pack")


def _notice(rows) -> str:
    """The console line of the check when the app opens (the Mac app's
    ``BuildModel.patchLibraryNotice``)."""
    count = {s: sum(1 for r in rows if r["state"] == s)
             for s in ("available", "newer", "pack_changed", "other")}
    parts = []
    if count["available"]:
        parts.append("%d with a patch available" % count["available"])
    if count["newer"]:
        parts.append("%d with a newer patch" % count["newer"])
    if count["pack_changed"]:
        parts.append("%d whose pack changed" % count["pack_changed"])
    if count["other"]:
        parts.append("%d with patches for another pack version" % count["other"])
    return "Patch library: airports " + ", ".join(parts) + " — see Library."


def check_at_launch(working_dir, say=print):
    """The check when the app opens, on a daemon thread: one console line
    when the library has something for this installation (the window's
    stdout tee carries a worker thread's print to the console)."""
    def run():
        try:
            result = command("library_check")(working_dir=working_dir)
        except Exception:                  # offline: the Library box says so
            return
        if result.get("configured") and result.get("rows"):
            say(_notice(result["rows"]))
    threading.Thread(target=run, daemon=True, name="o4-qt-patch-library-launch").start()


def applied_text(done) -> str:
    if done["mode"] == "solved":
        text = "%s v%d laid down: the next build of %s skips its solve." % (
            done["icao"], done["version"], done["tile"])
    else:
        text = "%s will be solved here (%s)." % (done["icao"], done["reason"])
    if done.get("conflict"):
        text += " " + done["conflict"][:1].upper() + done["conflict"][1:] + "."
    if done.get("warning"):
        text += " " + done["warning"]
    return text


class _Bridge(QObject):
    ready = Signal(object)


def _run(work, signal):
    def run():
        try:
            result = work()
        except Exception as error:        # shown, never raised on a thread
            result = error
        try:
            signal.emit(result)
        except RuntimeError:
            pass                          # the window went away
    threading.Thread(target=run, daemon=True, name="o4-qt-patch-library").start()


def _caption(text=""):
    label = QLabel(text)
    label.setStyleSheet("color: gray;")
    wrap_and_never_widen(label)
    return label


class PatchLibraryBox(QGroupBox):
    """Library dialog ▸ Patch library: what the library has for this
    installation, one row per airport."""

    def __init__(self, working_dir, building=lambda: False, parent=None):
        super().__init__(TITLE, parent)
        self.working_dir = working_dir
        self._building = building
        self.result = None
        self._bridge = _Bridge()
        self._bridge.ready.connect(self._on_ready)
        self._applied = _Bridge()
        self._applied.ready.connect(self._on_applied)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.status_label = _caption("Not checked yet.")
        top.addWidget(self.status_label, 1)
        self.check_btn = QPushButton("Check now")
        self.check_btn.setToolTip("Read the library's index again")
        self.check_btn.clicked.connect(lambda: self.check(force=True))
        top.addWidget(self.check_btn)
        layout.addLayout(top)
        self.rows_box = QVBoxLayout()
        layout.addLayout(self.rows_box)
        self.row_widgets = []

    def check(self, force=False):
        self.status_label.setText("Checking the patch library…")
        _run(lambda: command("library_check")(working_dir=self.working_dir,
                                              force=force), self._bridge.ready)

    def _on_ready(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self.set_check(result)

    def set_check(self, result):
        """Show one ``library_check`` result (tests call it directly)."""
        self.result = result
        for widget in self.row_widgets:
            widget.setParent(None)
        self.row_widgets = []
        if not result.get("configured"):
            self.status_label.setText("The patch library is not set up in this app yet.")
            return
        rows = result.get("rows") or []
        self.status_label.setText(
            "" if rows else "No patch in the library for your installed airports "
            "and built tiles.")
        for row in rows:
            self.row_widgets.append(self._row_widget(row))
            self.rows_box.addWidget(self.row_widgets[-1])

    def _row_widget(self, row):
        widget = QWidget()
        line = QHBoxLayout(widget)
        line.setContentsMargins(0, 0, 0, 0)
        text = "%s  %s%s · %s" % (row["icao"], row["entry_pack"],
                                  " · verified developer" if row["verified"] else "",
                                  _state_text(row))
        if not row["solved_usable"] and row["reason"] and row["state"] != "pack_changed":
            text += " (%s)" % row["reason"]
        line.addWidget(QLabel(text), 1)
        widget.buttons = {}
        label = {"available": "Build", "newer": "Update", "other": "Use"}.get(row["state"])
        if label:
            button = QPushButton(label)
            button.clicked.connect(lambda _c=False, r=row: self.apply(r))
            line.addWidget(button)
            widget.buttons[label] = button
        ignore = QPushButton("Ignore")
        ignore.clicked.connect(lambda _c=False, r=row: self.ignore(r))
        line.addWidget(ignore)
        widget.buttons["Ignore"] = ignore
        for button in widget.buttons.values():
            button.setEnabled(not self._building())
        return widget

    def apply(self, row):
        self.status_label.setText("Downloading %s…" % row["icao"])
        _run(lambda: command("library_apply")(entry=row["entry"],
                                              working_dir=self.working_dir),
             self._applied.ready)

    def _on_applied(self, result):
        self.status_label.setText(str(result) if isinstance(result, Exception)
                                  else applied_text(result))
        self.check()

    def ignore(self, row):
        def work():
            command("library_ignore")(icao=row["icao"], signature=row["signature"],
                                      version=row["version"])
            return command("library_check")(working_dir=self.working_dir)
        _run(work, self._bridge.ready)


class LibraryMatchList(QWidget):
    """Build box ▸ Airports card ▸ Library patches: the best entry per
    graded airport, with "Use"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.matches = None
        self.working_dir = ""
        self._bridge = _Bridge()
        self._bridge.ready.connect(self._on_ready)
        self._applied = _Bridge()
        self._applied.ready.connect(self._on_applied)
        self._generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 0, 0, 0)
        layout.setSpacing(2)
        self.title = QLabel("Library patches")
        layout.addWidget(self.title)
        self.rows_box = QVBoxLayout()
        layout.addLayout(self.rows_box)
        self.status_label = _caption("")
        layout.addWidget(self.status_label)
        self.row_widgets = []
        self.setVisible(False)

    def request(self, cells, working_dir=""):
        self.working_dir = working_dir
        self._generation += 1
        generation = self._generation
        cells = [[int(c[0]), int(c[1])] for c in cells]
        if not cells:
            self.set_matches(None)
            return
        _run(lambda: (generation, command("library_matches")(cells=cells,
                                                            working_dir=working_dir)),
             self._bridge.ready)

    def _on_ready(self, answer):
        if isinstance(answer, Exception):
            self.set_matches(None)
            return
        generation, matches = answer
        if generation == self._generation:
            self.set_matches(matches)

    def set_matches(self, matches):
        """Show one ``library_matches`` result (tests call it directly)."""
        self.matches = matches if matches and matches.get("configured") else None
        for widget in self.row_widgets:
            widget.setParent(None)
        self.row_widgets = []
        airports = (self.matches or {}).get("airports") or {}
        for icao in sorted(airports):
            best = airports[icao][0]
            widget = QWidget()
            line = QHBoxLayout(widget)
            line.setContentsMargins(0, 0, 0, 0)
            label = QLabel("%s  v%d · %s%s" % (icao, best["version"], _tier_text(best),
                                              " · verified developer" if best["verified"] else ""))
            label.setToolTip("Skips this airport's solve" if best["solved_usable"]
                             else "Solved here from its edits: " + best["reason"])
            line.addWidget(label, 1)
            use = QPushButton("Use")
            use.clicked.connect(lambda _c=False, e=best["entry"]: self.use(e))
            line.addWidget(use)
            widget.use_btn = use
            self.rows_box.addWidget(widget)
            self.row_widgets.append(widget)
        self.setVisible(bool(airports))

    def use(self, entry):
        _run(lambda: command("library_apply")(entry=entry, working_dir=self.working_dir),
             self._applied.ready)

    def _on_applied(self, result):
        self.status_label.setText(str(result) if isinstance(result, Exception)
                                  else applied_text(result))


class PublishPatchDialog(QDialog):
    """Library dialog ▸ Publish patch…: one airport of a built tile."""

    previewed = Signal(object)
    signed = Signal(object)
    published = Signal(object)

    def __init__(self, parent, row, working_dir):
        super().__init__(parent)
        self.setWindowTitle("Publish patch — %s" % row["tile"])
        self.row, self.working_dir = row, working_dir
        self.preview = None
        layout = QVBoxLayout(self)
        self.airport_combo = QComboBox()
        self.airport_combo.addItems(list(row.get("airports") or []))
        self.kind_combo = QComboBox()
        for value, label in KINDS:
            self.kind_combo.addItem(label, value)
        self.kind_combo.setToolTip("The global default airports are recognised by themselves")
        for label, widget in (("Airport", self.airport_combo), ("Pack", self.kind_combo)):
            line = QHBoxLayout()
            line.addWidget(QLabel(label))
            line.addWidget(widget, 1)
            layout.addLayout(line)
        self.preview_label = _caption("")
        layout.addWidget(self.preview_label)
        self.licence_chk = QCheckBox(LICENCE_TEXT)
        self.licence_chk.toggled.connect(self._sync)
        layout.addWidget(self.licence_chk)
        self.code_label = QLabel("")
        self.code_label.setOpenExternalLinks(True)
        layout.addWidget(self.code_label)
        self.status_label = _caption("")
        self.status_label.setOpenExternalLinks(True)
        layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.run_preview)
        self.signin_btn = QPushButton("Sign in to GitHub…")
        self.signin_btn.clicked.connect(self.run_sign_in)
        self.publish_btn = QPushButton("Publish")
        self.publish_btn.clicked.connect(self.run_publish)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for button in (self.preview_btn, self.signin_btn):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(close)
        buttons.addWidget(self.publish_btn)
        layout.addLayout(buttons)
        self.previewed.connect(self._on_preview)
        self.signed.connect(self._on_signed)
        self.published.connect(self._on_published)
        self._sync()

    def _args(self):
        return dict(lat=self.row["lat"], lon=self.row["lon"],
                    icao=self.airport_combo.currentText(),
                    working_dir=self.working_dir,
                    kind=self.kind_combo.currentData())

    def _sync(self, *_):
        p = self.preview
        self.signin_btn.setVisible(p is not None and not p["signed_in"])
        self.publish_btn.setEnabled(bool(p) and not p["problems"] and bool(p["signed_in"])
                                    and self.licence_chk.isChecked())

    def run_preview(self):
        self.status_label.setText("Packaging %s…" % self.airport_combo.currentText())
        args = self._args()
        _run(lambda: command("library_publish_preview")(**args), self.previewed)

    def _on_preview(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self.preview = result
        if result["licence_accepted"]:
            self.licence_chk.setChecked(True)
        lines = ["%s version %d for %s (%s) · %.1f MB" % (
            result["icao"], result["version"], result["pack"], result["kind"],
            result["bytes"] / 1e6),
            "You are this pack's verified developer: it merges when the checks pass."
            if result["verified"] else "It goes to the community reviewers."]
        lines += terms_lines(result)
        lines += ["• " + p for p in result["problems"]]
        self.preview_label.setText("\n".join(lines))
        self.status_label.setText("Ready to publish." if not result["problems"]
                                  else "The library would refuse it.")
        self._sync()

    def run_sign_in(self):
        def work():
            start = command("library_signin_start")()
            self.signed.emit({"start": start})
            QDesktopServices.openUrl(QUrl(start["verification_uri"]))
            for _attempt in range(180):
                time.sleep(max(int(start.get("interval") or 5), 1))
                poll = command("library_signin_poll")(device_code=start["device_code"])
                if poll["status"] in ("ok", "expired", "denied"):
                    return {"poll": poll}
            return {"poll": {"status": "expired", "login": ""}}
        _run(work, self.signed)

    def _on_signed(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
        elif "start" in result:
            start = result["start"]
            self.code_label.setText('Enter <b>%s</b> at <a href="%s">%s</a>' % (
                start["user_code"], start["verification_uri"], start["verification_uri"]))
            self.status_label.setText("Waiting for GitHub…")
        elif result["poll"]["status"] == "ok":
            self.code_label.setText("")
            self.status_label.setText("Signed in as %s." % result["poll"]["login"])
            self.run_preview()
        else:
            self.code_label.setText("")
            self.status_label.setText("The sign-in was %s. Try again." % result["poll"]["status"])

    def run_publish(self):
        args = dict(self._args(), notes="", accept=self.licence_chk.isChecked())
        self.status_label.setText("Publishing…")
        _run(lambda: command("library_publish")(**args), self.published)

    def _on_published(self, result):
        if isinstance(result, Exception):
            self.status_label.setText(str(result))
            return
        self.status_label.setText('Published v%d: %s <a href="%s">Open the pull request</a>' % (
            result["version"], "it merges when the library's checks pass."
            if result["auto_merge"] else "the community reviewers will look at it.",
            result["pull_url"]))
