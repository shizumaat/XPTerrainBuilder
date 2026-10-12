"""How the Qt window shows a tile that was not built, or was built without
an airport patch (issue #562; owner RULINGS 2026-10-12a, #564; Qt half).

The TEXT is the engine's (``O4_Tile_Failures`` through
``BuildDone.failures`` / ``BuildDone.warnings``): what failed, why, what to
do.  This module only lays it out — the console block per tile, the phrase
in the end-of-run report, and ONE non-modal box per run with the technical
detail behind its "Show Details…" disclosure (a batch of twenty tiles must
not raise twenty boxes).  Parity with the macOS app
(``Sources/SceneryKit/TileFailure.swift``).

Everything but :func:`issues_box` is pure and imports no Qt.
"""

from __future__ import annotations

__all__ = ["AIRPORT_FAILED_LINE", "console_lines", "report_phrase",
           "box_texts", "issues_box"]

# The live line for one airport, while its tile is still building.
AIRPORT_FAILED_LINE = ("*** Tile {tile}: airport {airport} could not be "
                       "patched — the tile's report will say why.")


def _entries(event) -> list:
    """``(is_warning, entry)`` for every message of one ``BuildDone``."""
    return ([(False, f) for f in getattr(event, "failures", None) or []]
            + [(True, w) for w in getattr(event, "warnings", None) or []])


def console_lines(event) -> list:
    """The console block of one ``BuildDone``: three lines per cause, then
    its technical detail, indented."""
    lines = []
    for is_warning, entry in _entries(event):
        lines.append(("Warning: " if is_warning else "*** ")
                     + entry.get("what", ""))
        lines.append("    " + entry.get("why", ""))
        lines.append("    " + entry.get("remedy", ""))
        for detail in (entry.get("detail") or "").splitlines():
            lines.append("      detail: " + detail)
    return lines


def report_phrase(event) -> str:
    """The end-of-run report's reason for one tile: why it failed, or
    ``"with warnings"`` for a tile built without an airport patch."""
    if getattr(event, "ok", False):
        return "with warnings" if getattr(event, "warnings", None) else ""
    failures = getattr(event, "failures", None) or []
    if not failures:
        return getattr(event, "error", "") or ""
    return " ".join(f.get("what", "").split(": ", 1)[-1] for f in failures)


def box_texts(events) -> tuple:
    """``(title, body, detail)`` of the run's one box; ``None`` when no
    tile of the run failed or carries a warning."""
    entries = [pair for event in events for pair in _entries(event)]
    if not entries:
        return None
    failed = sum(1 for event in events if not getattr(event, "ok", False))
    warned = sum(1 for event in events if getattr(event, "ok", False)
                 and getattr(event, "warnings", None))
    parts = []
    if failed:
        parts.append("%d tile%s not built"
                     % (failed, " was" if failed == 1 else "s were"))
    if warned:
        parts.append("%d built with warnings" % warned)
    body = "\n\n".join("%s\n%s\n%s" % (e.get("what", ""), e.get("why", ""),
                                      e.get("remedy", ""))
                       for _warning, e in entries)
    detail = "\n\n".join("%s\n%s" % (e.get("what", ""), e.get("detail", ""))
                         for _warning, e in entries if e.get("detail"))
    return (", ".join(parts), body, detail)


def issues_box(events, parent=None):
    """The run's one non-modal box, or ``None`` when there is nothing to
    say.  The technical detail sits behind "Show Details…"."""
    texts = box_texts(events)
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
    box.addButton(QMessageBox.Ok)
    return box
