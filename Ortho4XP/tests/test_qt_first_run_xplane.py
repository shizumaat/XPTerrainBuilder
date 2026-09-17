"""Beta plan §1 B2, Qt side: the X-Plane folder is REQUIRED.

The onboarding wizard's X-Plane page validates a real install (``Custom
Scenery/`` *and* ``Resources/default data/CIFP/``) and does not let the
user walk past it while it is invalid; the Build button refuses while no
CIFP corpus resolves.  The engine twin of the same law lives in
``tests/test_cifp_missing_refusal.py`` — both call ONE predicate,
``O4_Settings_Model.xplane_install_problem`` / ``cifp_refusal_reason``.

Offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no engine; prefs
monkeypatched BEFORE the window is constructed, as
``tests/test_qt_mac_parity.py`` does.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Wizard as WIZ  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _xplane_tree(root, with_cifp=True):
    """A fake X-Plane install — never the owner's real one."""
    (root / "Custom Scenery").mkdir(parents=True)
    if with_cifp:
        (root / "Resources" / "default data" / "CIFP").mkdir(parents=True)
    return str(root)


# ── the wizard page ───────────────────────────────────────────────────

def test_the_wizard_validates_a_real_xplane_tree(qapp, tmp_path,
                                                 monkeypatch):
    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    wizard = WIZ.OnboardingWizard({}, ["BI"])
    try:
        page = WIZ.STEPS.index("X-Plane")
        wizard._set_step(page)

        # Empty: cannot continue.
        assert wizard.next_btn.isEnabled() is False
        wizard._next()
        assert wizard.stack.currentIndex() == page

        # Custom Scenery alone is NOT an install we can build against.
        half = _xplane_tree(tmp_path / "half", with_cifp=False)
        wizard.xplane_edit.setText(half)
        assert wizard.next_btn.isEnabled() is False
        assert "CIFP" in wizard.unlock_label.text()
        wizard._next()
        assert wizard.stack.currentIndex() == page

        # The full tree unlocks the page.
        full = _xplane_tree(tmp_path / "full")
        wizard.xplane_edit.setText(full)
        assert wizard.next_btn.isEnabled() is True
        wizard._next()
        assert wizard.stack.currentIndex() == page + 1
        wizard._collect()
        assert wizard.prefs["xplane_dir"] == full
    finally:
        wizard.deleteLater()


def test_the_wizard_prefills_a_detected_install(qapp, tmp_path,
                                                monkeypatch):
    full = _xplane_tree(tmp_path / "full")
    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [full])
    wizard = WIZ.OnboardingWizard({}, ["BI"])
    try:
        assert wizard.xplane_edit.text() == full
        assert wizard.detect_tag.text() == "detected"
    finally:
        wizard.deleteLater()


def test_detection_rejects_a_tree_without_cifp(tmp_path, monkeypatch):
    """One predicate: detection uses the same validity test as the page."""
    half = _xplane_tree(tmp_path / "half", with_cifp=False)
    assert WIZ.looks_like_xplane(half) is False
    assert SM.xplane_install_problem(half) is not None


# ── the Build button ──────────────────────────────────────────────────

@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w") as handle:
        # An EXISTING prefs file: an absent one arms the wizard, whose
        # modal exec would sit there forever headless.
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def _no_cifp_config(monkeypatch):
    monkeypatch.setattr(SM, "read_global_raw",
                        lambda *a, **k: {"cifp_data_path": "",
                                         "custom_scenery_dir": ""})


def test_the_build_button_refuses_without_an_xplane_folder(window,
                                                           monkeypatch):
    _no_cifp_config(monkeypatch)
    window.prefs["xplane_dir"] = ""
    reason = window.xplane_block_reason()
    assert reason is not None
    assert "X-Plane" in reason

    said = []
    monkeypatch.setattr(window, "_status", said.append)
    monkeypatch.setattr(window, "_start_run",
                        lambda *a, **k: pytest.fail("build started"))
    window.start_build()
    assert said == [reason]


def test_a_valid_install_unblocks_the_build(window, tmp_path, monkeypatch):
    full = _xplane_tree(tmp_path / "full")
    monkeypatch.setattr(
        SM, "read_global_raw",
        lambda *a, **k: {"cifp_data_path": "",
                         "custom_scenery_dir": os.path.join(
                             full, "Custom Scenery")})
    window.prefs["xplane_dir"] = full
    assert window.xplane_block_reason() is None


def test_a_navigraph_only_config_is_not_blocked(window, tmp_path,
                                                monkeypatch):
    """The gate is the ENGINE's law, not a folder-shaped ritual: a user
    who pointed cifp_data_path at a Navigraph corpus can build."""
    cifp = tmp_path / "navigraph" / "CIFP"
    cifp.mkdir(parents=True)
    monkeypatch.setattr(
        SM, "read_global_raw",
        lambda *a, **k: {"cifp_data_path": str(cifp),
                         "custom_scenery_dir": ""})
    window.prefs["xplane_dir"] = ""
    assert window.xplane_block_reason() is None
