"""TEMPORARY diagnostic (lane betawinpanel) — DELETE before merge.

Walks the right panel's widget tree and reports every widget whose
minimum width pushes the panel past its fixed-width viewport.  Fails on
purpose so pytest prints the captured report (CI runs without -s).
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLayout  # noqa: E402


LONG_TEXT = (
    "1/9 arc-second (~3 m) lidar: USGS_3DEP_1M, HRDEM_QUEBEC_1M, "
    "PT_DGT_LIDAR_COASTAL, SWEDEN_LM_1M, DK_SDFE_DTM and 12 more sources"
)


def _describe(widget):
    text = ""
    for attr in ("text", "title", "placeholderText"):
        getter = getattr(widget, attr, None)
        if callable(getter):
            try:
                value = getter()
            except Exception:
                value = ""
            if value:
                text = str(value)
                break
    return text.replace("\n", " ")[:46]


ROWS = []


def _walk(widget, lines, depth=0):
    msh = widget.minimumSizeHint().width()
    sh = widget.sizeHint().width()
    ROWS.append((msh, type(widget).__name__, _describe(widget), depth))
    lines.append(
        "%-44s %5d %5d %5d %5d  %s"
        % (
            "  " * depth + type(widget).__name__,
            msh,
            sh,
            widget.minimumWidth(),
            widget.width(),
            _describe(widget),
        )
    )
    layout = widget.layout()
    if layout is None:
        return
    for i in range(layout.count()):
        item = layout.itemAt(i)
        child = item.widget()
        if child is not None:
            _walk(child, lines, depth + 1)
        elif isinstance(item.layout(), QLayout):
            sub = item.layout()
            for j in range(sub.count()):
                grand = sub.itemAt(j).widget()
                if grand is not None:
                    _walk(grand, lines, depth + 1)


def _about_box(GUI, window):
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox(window)
    box.setWindowTitle("Ortho4XP")
    box.setText(window.about_text())
    return box


def test_panel_offender_table(tmp_path, monkeypatch, capsys):
    import O4_Qt_GUI as GUI

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(GUI, "PREFS_FILE", str(tmp_path / "prefs.json"))
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json")
    )
    # First run queues run_wizard() 200 ms after construction, and its
    # exec() is modal: on the Windows runner construction is slow enough
    # that the timer fires inside our processEvents and the test hangs
    # until the 180 s timeout (CI round 1).
    monkeypatch.setattr(
        GUI.MainWindow, "run_wizard", lambda self: None, raising=True
    )
    with capsys.disabled():
        original_stdout = sys.stdout
        window = GUI.MainWindow()
        sys.stdout = original_stdout
    window.show()
    app.processEvents()
    window.build_summary.setText(
        "12 tiles selected · rough est. 48.0 GB · airport lidar on 12"
    )
    window.info_elevation.setText(LONG_TEXT)
    window.info_airport_lidar.setText(LONG_TEXT)
    app.processEvents()

    panel = window.info_group.parentWidget()
    scroll = panel.parentWidget()
    while not hasattr(scroll, "viewport"):
        scroll = scroll.parentWidget()

    lines = [
        "PLATFORM=%s style=%s" % (sys.platform, app.style().objectName()),
        "viewport width=%d  panel msh=%d  panel width=%d"
        % (
            scroll.viewport().width(),
            panel.minimumSizeHint().width(),
            panel.width(),
        ),
        "font: %s %spt  '0' advance=%d"
        % (
            panel.font().family(),
            panel.font().pointSizeF(),
            panel.fontMetrics().horizontalAdvance("0"),
        ),
        "%-44s %5s %5s %5s %5s  %s"
        % ("WIDGET", "msh", "sh", "minW", "w", "TEXT"),
    ]
    _walk(panel, lines)

    # Also the dialogs/wizard the brief asks about (top-level, so the
    # bar is the 800x600 offscreen screen, not a fixed container).
    import O4_Qt_Settings as QTSET
    import O4_Qt_Wizard as QTWIZ

    extras = []

    def _settings():
        return QTSET.SettingsWindow(
            dict(window.prefs), [(48, -6)], window.output_dir(), window
        )

    for name, factory in (
        ("SettingsWindow", _settings),
        (
            "OnboardingWizard",
            lambda: QTWIZ.OnboardingWizard(
                dict(window.prefs), ["BI", "GO2"], window
            ),
        ),
        ("AboutMessageBox", lambda: _about_box(GUI, window)),
    ):
        try:
            dialog = factory()
            app.processEvents()
            extras.append(
                "%-20s msh=%d x %d  sh=%d x %d  screen=800x600"
                % (
                    name,
                    dialog.minimumSizeHint().width(),
                    dialog.minimumSizeHint().height(),
                    dialog.sizeHint().width(),
                    dialog.sizeHint().height(),
                )
            )
            dialog.deleteLater()
        except Exception as exc:  # pragma: no cover - diagnostic
            extras.append("%-20s RAISED %r" % (name, exc))

    window.deleteLater()
    top = ["TOP OFFENDERS (by minimumSizeHint width)"]
    for msh, cls, text, depth in sorted(ROWS, reverse=True)[:14]:
        top.append("  %5d  d%d %-22s %s" % (msh, depth, cls, text))
    pytest.fail("\n".join(lines + [""] + top + [""] + extras))
