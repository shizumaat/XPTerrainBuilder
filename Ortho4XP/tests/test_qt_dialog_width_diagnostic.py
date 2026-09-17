"""THROWAWAY diagnostic (lane betawinsettings) — delete before merge.

Prints, per platform, the Settings window's and the onboarding wizard's
size hints plus the widest children, so the offenders behind the Windows
1228 px floor can be named rather than guessed.  Never asserts.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _describe(widget):
    text = ""
    for getter in ("text", "currentText", "windowTitle"):
        method = getattr(widget, getter, None)
        if callable(method):
            try:
                text = str(method() or "")
            except TypeError:
                text = ""
            if text:
                break
    return "%s %r" % (type(widget).__name__, text[:48])


def _report(title, dialog, limit=20):
    print("\n===== %s on %s =====" % (title, sys.platform))
    print("  minimumSizeHint = %s x %s"
          % (dialog.minimumSizeHint().width(),
             dialog.minimumSizeHint().height()))
    print("  sizeHint        = %s x %s"
          % (dialog.sizeHint().width(), dialog.sizeHint().height()))
    print("  minimumWidth    = %s" % dialog.minimumWidth())
    rows = []
    for child in dialog.findChildren(object):
        if not hasattr(child, "minimumSizeHint"):
            continue
        try:
            minimum = child.minimumSizeHint().width()
            hint = child.sizeHint().width()
        except Exception:
            continue
        rows.append((minimum, hint, _describe(child)))
    rows.sort(reverse=True)
    print("  %-8s %-8s %s" % ("minW", "hintW", "widget"))
    for minimum, hint, description in rows[:limit]:
        print("  %-8s %-8s %s" % (minimum, hint, description))


LONG_PATH = (
    "/Volumes/Scenery Archive 2026/X-Plane 12 Beta Testing/"
    "Custom Scenery/zOrtho4XP_Very_Long_Folder_Name_Here"
)


def test_diagnostic_settings_window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from O4_Qt_Settings import SettingsWindow

    window = SettingsWindow(prefs={}, tiles=[], custom_build_dir="")
    for row in window.rows.values():
        from PySide6.QtWidgets import QLineEdit

        if isinstance(row.control, QLineEdit):
            row.control.setText(LONG_PATH)
    window.show()
    qapp.processEvents()
    _report("SettingsWindow (global)", window)
    window.close()

    blended = SettingsWindow(
        prefs={}, tiles=[(36, -87), (37, -88)], custom_build_dir="")
    blended.show()
    qapp.processEvents()
    _report("SettingsWindow (2 tiles)", blended)
    blended.close()


def test_diagnostic_wizard(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import O4_Qt_Wizard as WIZ

    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    wizard = WIZ.OnboardingWizard(
        {"xplane_dir": LONG_PATH, "output_dir": LONG_PATH},
        ["BI", "GO2", "USA_5M_DEM_AND_A_VERY_LONG_PROVIDER_CODE"],
    )
    wizard.show()
    qapp.processEvents()
    for step in range(len(WIZ.STEPS)):
        wizard._set_step(step)
        qapp.processEvents()
        _report("OnboardingWizard step %d (%s)" % (step, WIZ.STEPS[step]),
                wizard, limit=12)
    wizard.close()
