"""How the Qt window shows a tile that was not built, or was built without
an airport patch (issue #562; owner RULINGS 2026-10-12a, #564; Qt half).

The TEXT is the engine's (``O4_Tile_Failures`` through
``BuildDone.failures`` / ``BuildDone.warnings``): what failed, why, what to
do.  This module only lays it out — the console block per tile, the phrase
in the end-of-run report, and ONE non-modal box per run with the technical
detail behind its "Show Details…" disclosure (a batch of twenty tiles must
not raise twenty boxes).  Parity with the macOS app
(``Sources/SceneryKit/TileFailure.swift``).

The box carries the two report buttons (issue #565): "Report this
problem" shows the engine's REDACTED report for the user to read, then
copies it and opens the prefilled GitHub issue; "Save report file" writes
it where the user chooses.  Nothing leaves the machine without that press.

Everything above the "Qt" rule is pure and imports no Qt.
"""

from __future__ import annotations

import os
import sys

from O4_Tile_Failures import SEVERITY_LABELS

__all__ = ["AIRPORT_FAILED_LINE", "REPORT_BUTTON", "SAVE_REPORT_BUTTON",
           "console_lines", "report_phrase", "box_texts", "tile_report",
           "REMOVE_LINK_BUTTON", "REQUEUED_LINE", "BUILD_AGAIN_BUTTON",
           "removable_links", "issues_box", "severity_label"]

# --- copy (identical to the mac app's O4TileFailureCopy) ----------------
REPORT_BUTTON = "Report this problem"
SAVE_REPORT_BUTTON = "Save report file"
REPORT_PREVIEW_TITLE = "This is what the report says"
REPORT_PREVIEW_NOTE = (
    "Nothing has been sent. Pressing the button below copies this text and "
    "opens a new GitHub issue in your browser, where you can read it again "
    "before posting.")
OPEN_ISSUE_BUTTON = "Copy and Open GitHub"
# A tile folder behind a link to a drive that is not mounted (#668); the
# mac app's O4TileFailureCopy.removeLinkButton on macOS.
REMOVE_LINK_BUTTON = ("Remove the link and build on this %s drive"
                      % ("Mac's" if sys.platform == "darwin"
                         else "computer's"))
# A failure the user fixed while the run went on (#695; the mac app's
# O4TileFailureCopy.requeuedLine).
REQUEUED_LINE = "Fixed and re-queued."
# #821: re-queue the run's failed and not-started tiles, same options.
BUILD_AGAIN_BUTTON = "Build failed tiles again"

# The live line for one airport, while its tile is still building.
AIRPORT_FAILED_LINE = ("*** Tile {tile}: airport {airport} could not be "
                       "patched — the tile's report will say why.")


def _entries(event) -> list:
    """``(is_warning, entry)`` for every message of one ``BuildDone``:
    its failures, then warnings, then notes (stand-in elevation, RULINGS
    2026-10-12e — shown under the warnings)."""
    return ([(False, f) for f in getattr(event, "failures", None) or []]
            + [(True, w) for w in getattr(event, "warnings", None) or []]
            + [("note", n) for n in getattr(event, "notes", None) or []])


def severity_label(is_warning, entry) -> str:
    """The entry's severity as both apps label it (#853): the wire's
    ``severity`` (protocol 1.13), else the list it came in (an older
    engine sends no key)."""
    severity = entry.get("severity") or (
        "info" if is_warning == "note" else
        "degraded" if is_warning else "blocking")
    return SEVERITY_LABELS.get(severity, SEVERITY_LABELS["blocking"])


def console_lines(event) -> list:
    """The console block of one ``BuildDone``: three lines per cause, then
    its technical detail, indented."""
    lines = []
    for is_warning, entry in _entries(event):
        label = severity_label(is_warning, entry)
        lines.append(("*** " if label == SEVERITY_LABELS["blocking"]
                      else label + ": ") + entry.get("what", ""))
        lines.append("    " + entry.get("why", ""))
        lines.append("    " + entry.get("remedy", ""))
        for detail in (entry.get("detail") or "").splitlines():
            lines.append("      detail: " + detail)
    return lines


def report_phrase(event) -> str:
    """The end-of-run report's reason for one tile: why it failed, or
    ``"with warnings"`` for a tile built without an airport patch."""
    if getattr(event, "ok", False):
        return "with warnings" if (getattr(event, "warnings", None)
                                   or getattr(event, "notes", None)) else ""
    failures = getattr(event, "failures", None) or []
    if not failures:
        return getattr(event, "error", "") or ""
    return " ".join(f.get("what", "").split(": ", 1)[-1] for f in failures)


def box_texts(events, requeued=()) -> tuple:
    """``(title, body, detail)`` of the run's one box; ``None`` when no
    tile of the run failed or carries a warning.  A failure whose event
    is in ``requeued`` (its ``id``, #695) was fixed while the run went on:
    it is still listed, followed by :data:`REQUEUED_LINE`."""
    entries = [pair for event in events for pair in _entries(event)]
    if not entries:
        return None
    failed = sum(1 for event in events if not getattr(event, "ok", False))
    warned = sum(1 for event in events if getattr(event, "ok", False)
                 and _entries(event))
    parts = []
    if failed:
        parts.append("%d tile%s not built"
                     % (failed, " was" if failed == 1 else "s were"))
    if warned:
        parts.append("%d built with warnings" % warned)
    body = "\n\n".join(
        "%s: %s\n%s\n%s" % (severity_label(warning, e), e.get("what", ""),
                            e.get("why", ""), e.get("remedy", ""))
        + ("\n" + REQUEUED_LINE if id(event) in requeued else "")
        for event in events for warning, e in _entries(event))
    detail = "\n\n".join("%s\n%s" % (e.get("what", ""), e.get("detail", ""))
                         for _warning, e in entries if e.get("detail"))
    return (", ".join(parts), body, detail)


def removable_links(events, requeued=()) -> list:
    """``(event, link)`` for every tile NOT built because its Custom
    Scenery folder is a link to a drive that is not mounted (#668): the
    links the box offers to remove — none for an event in ``requeued``
    (already fixed mid-run, #695)."""
    out = []
    for event in events:
        if getattr(event, "ok", False) or id(event) in requeued:
            continue
        for entry in getattr(event, "failures", None) or []:
            if (entry.get("code") == "output_link_unmounted"
                    and entry.get("link")):
                out.append((event, entry["link"]))
                break
    return out


def tile_report(event, save_path="", app_version=""):
    """The engine's redacted report of one ``BuildDone`` (the in-process
    form of the ``failure_report`` command, #565): its result dict."""
    from o4_engine.failure_report import failure_report
    import O4_Config_Utils as CFG

    return failure_report(
        lat=int(event.lat), lon=int(event.lon),
        failures=[entry for _warning, entry in _entries(event)],
        app_version=app_version, app_name="qt",
        xplane_dir=os.path.dirname(
            (getattr(CFG, "custom_scenery_dir", "") or "").rstrip("/\\")),
        save_path=save_path)


# --- Qt ------------------------------------------------------------------
def _pick_event(events, parent):
    """The tile a report button acts on: asked when the run has several."""
    if len(events) == 1:
        return events[0]
    from PySide6.QtWidgets import QInputDialog

    names = ["%+03d%+04d" % (int(e.lat), int(e.lon)) for e in events]
    (name, ok) = QInputDialog.getItem(parent, REPORT_BUTTON, "Tile:", names,
                                      0, False)
    return events[names.index(name)] if ok else None


def _report(events, parent, app_version):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices, QGuiApplication
    from PySide6.QtWidgets import QMessageBox

    event = _pick_event(events, parent)
    if event is None:
        return
    result = tile_report(event, app_version=app_version)
    preview = QMessageBox(parent)
    preview.setWindowTitle(REPORT_BUTTON)
    preview.setText(REPORT_PREVIEW_TITLE)
    preview.setInformativeText(REPORT_PREVIEW_NOTE)
    preview.setDetailedText(result["report"])
    send = preview.addButton(OPEN_ISSUE_BUTTON, QMessageBox.AcceptRole)
    preview.addButton(QMessageBox.Cancel)
    preview.exec()
    if preview.clickedButton() is send:
        QGuiApplication.clipboard().setText(result["report"])
        QDesktopServices.openUrl(QUrl(result["issue_url"]))


def _save(events, parent, app_version):
    from PySide6.QtWidgets import QFileDialog

    event = _pick_event(events, parent)
    if event is None:
        return
    name = tile_report(event, app_version=app_version)["file_name"]
    (path, _filter) = QFileDialog.getSaveFileName(
        parent, SAVE_REPORT_BUTTON, name)
    if path:
        tile_report(event, save_path=path, app_version=app_version)


def issues_box(events, parent=None, app_version="", on_remove_link=None,
               requeued=(), on_build_again=None):
    """The run's one non-modal box, or ``None`` when there is nothing to
    say.  The technical detail sits behind "Show Details…".  With
    ``on_remove_link`` and a tile behind an unmounted drive's link (#668)
    it offers "Remove the link…" (``on_remove_link(event, link)``) and
    "Cancel".  ``requeued``: see :func:`box_texts`.  With
    ``on_build_again`` it offers "Build failed tiles again" (#821)."""
    texts = box_texts(events, requeued)
    if texts is None:
        return None
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox

    (title, body, detail) = texts
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(title[:1].upper() + title[1:] + ".")
    box.setInformativeText(body)
    if detail:
        box.setDetailedText(detail)
    box.setWindowModality(Qt.NonModal)
    with_issues = [event for event in events if _entries(event)]
    for (label, action) in ((REPORT_BUTTON, _report),
                            (SAVE_REPORT_BUTTON, _save)):
        button = box.addButton(label, QMessageBox.ActionRole)
        # An action button closes its box by default: these two act and
        # leave the messages on screen.
        button.clicked.disconnect()
        button.clicked.connect(
            lambda _checked=False, action=action: action(
                with_issues, box, app_version))
    if on_build_again is not None:
        again = box.addButton(BUILD_AGAIN_BUTTON, QMessageBox.ActionRole)
        again.clicked.connect(lambda _checked=False: on_build_again())
    removable = (removable_links(events, requeued) if on_remove_link
                 else [])
    if removable:
        remove = box.addButton(REMOVE_LINK_BUTTON, QMessageBox.AcceptRole)
        remove.clicked.connect(
            lambda _checked=False: [on_remove_link(event, link)
                                    for (event, link) in removable])
        box.addButton(QMessageBox.Cancel)
    else:
        box.addButton(QMessageBox.Ok)
    return box
