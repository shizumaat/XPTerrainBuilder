"""The elevation detail levels of ``docs/specs/elevation-level-spec.md``
in the Qt settings model: both config values render as enumerated combos
(values + labels) in Settings ▸ Elevation.

The build-area rows these tests once covered were removed with the
texture-mode row (#1243): as in the Mac app, the three per-tile values
are set in Settings only (``tests/test_qt_layout_parity.py``).

No network, no X-Plane install.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402


def test_modules_resolve_to_this_worktree():
    """Guard against sys.path/conftest leakage from another checkout."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for module in (GUI, SM):
        assert os.path.abspath(module.__file__).startswith(here), (
            "%s resolved to %s, not this worktree" % (module, module.__file__)
        )


def test_settings_model_renders_enumerated_combo():
    setting = SM.get_setting("elevation_level")
    assert setting is not None
    assert setting.scope == "tile"
    assert setting.category == "elevation"
    assert setting.values == (
        "auto", "coastline", "90", "30", "10", "5", "1",
    )
    assert setting.label_for("auto").startswith("Auto")
    assert setting.label_for("90").startswith("90 m")
    assert setting.label_for("1").startswith("1 m")


def test_settings_model_renders_airport_enumerated_combo():
    setting = SM.get_setting("airport_elevation_level")
    assert setting is not None
    assert setting.scope == "tile"
    assert setting.category == "elevation"
    assert setting.values == ("auto", "0.5", "1", "5", "10", "30")
    assert setting.label_for("auto").startswith("Auto")
    assert setting.label_for("0.5").startswith("0.5 m")
