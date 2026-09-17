"""THROWAWAY diagnostic (lane betawinsettings) — delete before merge.

Reports, per platform, what each offending widget class costs in
MINIMUM width with the old spelling (plain QLabel / QLineEdit /
QComboBox, exactly what the dialogs used before this lane) against the
new one, plus the two dialogs' own size hints.

It ends in ``pytest.fail`` ON PURPOSE: a passing test's captured stdout
never reaches the CI log, and the CI recipe carries no ``-s``.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
)

from O4_Qt_Widgets import (  # noqa: E402
    ElidedRowLabel,
    SqueezableLineEdit,
    may_be_squeezed,
    never_widen,
    wrap_and_never_widen,
)

LONG_PATH = (
    "/Volumes/Scenery Archive 2026/X-Plane 12 Beta Testing/"
    "Custom Scenery/zOrtho4XP_Very_Long_Folder_Name_Here"
)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _min_width(widget):
    widget.show()
    QApplication.processEvents()
    width = widget.minimumSizeHint().width()
    widget.hide()
    return width


def _plain_label(text, rich=False):
    label = QLabel(text)
    if rich:
        label.setTextFormat(Qt.RichText)
    return label


def _rows():
    """(what, before widget, after widget) for each named offender."""
    name = "X-Plane Custom Scenery folder"
    hint = ("Your X-Plane Custom Scenery. Used only for 1-click "
            "creation of the scenery in your X-Plane installation.")
    legend = ('<span style="color: #C7861B; font-weight: bold;">●</span>'
              " overrides the global value &nbsp;·&nbsp; ↺ reverts a"
              " setting &nbsp;·&nbsp; blank = mixed across tiles")
    note = ("<i>7 advanced settings hidden — enable “Show advanced”.</i>")
    reason = ("<span style='color:#b00'>%s has no Custom Scenery folder"
              "</span>" % LONG_PATH)
    body = ("Required. Ortho4XP reads X-Plane's own airport and CIFP data\n"
            "to grade runways, taxiways and aprons — without it every\n"
            "airport would drape over the raw terrain, so a build refuses.")
    combo = QComboBox()
    combo.addItem("Auto — synthesize when Global Scenery is missing")
    squeezed = QComboBox()
    squeezed.addItem("Auto — synthesize when Global Scenery is missing")
    may_be_squeezed(squeezed, chars=8)
    wrapped_hint = QLabel(hint)
    wrapped_hint.setWordWrap(True)
    chip_before = QPushButton("Customized (12)")
    chip_after = QPushButton("Customized (12)")
    never_widen(chip_after)
    fixed_path = QLineEdit()
    fixed_path.setFixedWidth(280)
    return [
        ("settings row name label", _plain_label(name),
         ElidedRowLabel(name)),
        ("settings row hint (word-wrapped)", wrapped_hint,
         wrap_and_never_widen(QLabel(hint))),
        ("settings path field", fixed_path, SqueezableLineEdit(280)),
        ("settings enum combo", combo, squeezed),
        ("settings footer legend", _plain_label(legend, rich=True),
         wrap_and_never_widen(_plain_label(legend, rich=True))),
        ("settings advanced note", _plain_label(note, rich=True),
         wrap_and_never_widen(_plain_label(note, rich=True))),
        ("settings customized chip", chip_before, chip_after),
        ("wizard X-Plane rejection reason", _plain_label(reason, rich=True),
         wrap_and_never_widen(_plain_label(reason, rich=True))),
        ("wizard body paragraph", _plain_label(body),
         wrap_and_never_widen(QLabel(body))),
        ("wizard field label", _plain_label("Zoom level:"),
         ElidedRowLabel("Zoom level:")),
    ]


def _dialog_sizes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from O4_Qt_Settings import SettingsWindow
    import O4_Qt_Wizard as WIZ

    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    out = []
    window = SettingsWindow(prefs={}, tiles=[], custom_build_dir="")
    for row in window.rows.values():
        if isinstance(row.control, QLineEdit):
            row.control.setText(LONG_PATH)
    window.show()
    QApplication.processEvents()
    out.append(("SettingsWindow (global, long paths)", window))
    blended = SettingsWindow(
        prefs={}, tiles=[(36, -87), (37, -88)], custom_build_dir="")
    blended.show()
    QApplication.processEvents()
    out.append(("SettingsWindow (2 tiles)", blended))
    wizard = WIZ.OnboardingWizard(
        {"xplane_dir": LONG_PATH, "output_dir": LONG_PATH},
        ["BI", "GO2", "USA_5M_DEM_AND_A_VERY_LONG_PROVIDER_CODE"],
    )
    wizard._set_step(WIZ.STEPS.index("X-Plane"))
    wizard.show()
    QApplication.processEvents()
    out.append(("OnboardingWizard (X-Plane page, rejected path)", wizard))
    return out


def test_diagnostic_offender_table(qapp, tmp_path, monkeypatch):
    lines = ["", "OFFENDER TABLE on %s" % sys.platform,
             "%-40s %8s %8s" % ("widget", "before", "after")]
    for what, before, after in _rows():
        lines.append("%-40s %8d %8d"
                     % (what, _min_width(before), _min_width(after)))
    lines.append("")
    lines.append("DIALOG SIZES on %s" % sys.platform)
    lines.append("%-46s %10s %10s %8s"
                 % ("dialog", "minHint", "sizeHint", "minWidth"))
    for title, dialog in _dialog_sizes(tmp_path, monkeypatch):
        lines.append("%-46s %10s %10s %8d" % (
            title,
            "%dx%d" % (dialog.minimumSizeHint().width(),
                       dialog.minimumSizeHint().height()),
            "%dx%d" % (dialog.sizeHint().width(),
                       dialog.sizeHint().height()),
            dialog.minimumWidth(),
        ))
        dialog.close()
    pytest.fail("\n".join(lines), pytrace=False)
