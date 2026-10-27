"""The Build box's cost panel (issue #820): what the selected build will
download, write to disk and take, as ranges, before Build is pressed.

The engine's ``plan_estimate`` command answers
(``o4_engine.plan_estimate``; :class:`o4_engine.events.PlanEstimateReady`
completes it).  This panel shows its total line, a per-tile list behind a
disclosure button, and the engine's disk verdict: ``warn`` is a line in
orange, ``refuse`` turns Build off with the reason in the window's
why-Build-is-off line (:meth:`PlanEstimatePanel.blocking_reason`).  The Mac app's twin is
``Sources/XPTerrainBuilder/PlanEstimatePanel.swift``; the text helpers
below spell the same lines as its ``PlanEstimateText``.
"""
from __future__ import annotations

import math

from O4_Qt_Widgets import never_widen, wrap_and_never_widen
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget

__all__ = ["PlanEstimatePanel", "gb_text", "time_text", "total_text",
           "tile_text"]

WARN_COLOUR = "#D9822B"


def gb_text(pair) -> str:
    """``[0.96, 5.05]`` -> ``"1.0–5.1 GB"``; nothing to move is ``"none"``."""
    lo, hi = float(pair[0]), float(pair[1])
    if hi < 0.05:
        return "none"
    return "%.1f–%.1f GB" % (lo, hi)


def time_text(pair) -> str:
    """Seconds ``[lo, hi]`` as minutes, or hours past 90 minutes."""
    lo, hi = float(pair[0]), float(pair[1])
    if hi <= 0:
        return "none"
    if hi < 90 * 60:
        # Half rounds up, as Swift's ``rounded()`` does (not to even).
        lo_m = max(1, int(math.floor(lo / 60.0 + 0.5)))
        hi_m = max(lo_m, int(math.ceil(hi / 60.0)))
        return "about %d min" % lo_m if lo_m == hi_m else "%d–%d min" % (lo_m, hi_m)
    return "%.1f–%.1f h" % (lo / 3600.0, hi / 3600.0)


def total_text(result) -> str:
    """The panel's first line, e.g. ``"Download 1.0–5.1 GB · Disk 3.4–16.2
    GB of 27.3 GB free · 16–79 min"``."""
    total = result.get("total") or {}
    disk = "Disk %s" % gb_text(total.get("disk_gb") or (0, 0))
    if result.get("free_gb") is not None:
        disk += " of %.1f GB free" % result["free_gb"]
    return " · ".join(("Download %s" % gb_text(total.get("download_gb") or (0, 0)),
                       disk, time_text(total.get("time_s") or (0, 0))))


def tile_label(row) -> str:
    return "%+03d%+04d" % (int(row["lat"]), int(row["lon"]))


def tile_text(row) -> str:
    """One per-tile line: ``"+45-123  ↓ 0.5–2.7 GB · disk 1.8–8.5 GB ·
    8–42 min"``."""
    return "%s  ↓ %s · disk %s · %s" % (
        tile_label(row), gb_text(row["download_gb"]), gb_text(row["disk_gb"]),
        time_text(row["time_s"]))


class PlanEstimatePanel(QWidget):
    """Total line, per-tile disclosure and disk verdict.  Holds no combo or
    checkbox (the Build box's parity manifest counts those)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.total_label = wrap_and_never_widen(QLabel(""))
        layout.addWidget(self.total_label)
        self.details_btn = QToolButton()
        self.details_btn.setText("Per tile")
        self.details_btn.setCheckable(True)
        self.details_btn.setAutoRaise(True)
        self.details_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.details_btn.setArrowType(_arrow(False))
        self.details_btn.toggled.connect(self._toggle_details)
        never_widen(self.details_btn)
        layout.addWidget(self.details_btn)
        self.tiles_label = wrap_and_never_widen(QLabel(""))
        self.tiles_label.setStyleSheet("color: gray;")
        self.tiles_label.setVisible(False)
        layout.addWidget(self.tiles_label)
        self.verdict_label = wrap_and_never_widen(QLabel(""))
        self.verdict_label.setStyleSheet("color: %s;" % WARN_COLOUR)
        self.verdict_label.setVisible(False)
        layout.addWidget(self.verdict_label)
        self._result = None
        self.clear()

    def clear(self):
        """Nothing to estimate (no tiles, or no steps)."""
        self._result = None
        self.setVisible(False)

    def show_pending(self):
        """A new estimate is on its way; the last figures stay readable."""
        self.setVisible(True)
        if self._result is None:
            self.total_label.setText("Estimating…")
            self.details_btn.setVisible(False)

    def show_error(self, text):
        self._result = None
        self.setVisible(True)
        self.total_label.setText("No estimate: %s" % text)
        self.details_btn.setVisible(False)
        self.tiles_label.setVisible(False)
        self.verdict_label.setVisible(False)

    def show_result(self, result):
        self._result = result or {}
        self.setVisible(True)
        self.total_label.setText(total_text(self._result))
        rows = self._result.get("tiles") or []
        self.details_btn.setVisible(len(rows) > 0)
        self.tiles_label.setText("\n".join(tile_text(r) for r in rows))
        self.tiles_label.setVisible(self.details_btn.isChecked() and bool(rows))
        reason = self._result.get("reason") or ""
        self.verdict_label.setText(reason)
        # A refusal is said once, by the window's why-Build-is-off line
        # under the button (``blocking_reason``); a warning is said here.
        self.verdict_label.setVisible(
            self._result.get("verdict") == "warn" and bool(reason))

    def blocking_reason(self):
        """The refusal sentence when the build cannot fit, else ``None``."""
        if self._result and self._result.get("verdict") == "refuse":
            return self._result.get("reason") or "Not enough free disk space."
        return None

    def _toggle_details(self, shown):
        self.details_btn.setArrowType(_arrow(shown))
        self.tiles_label.setVisible(shown and bool(self.tiles_label.text()))


def _arrow(shown):
    return Qt.DownArrow if shown else Qt.RightArrow
