"""One settings wording, two apps (issue #823).

``src/O4_Settings_Model._LAYOUT`` words the Qt settings window;
``Sources/XPTerrainBuilder/SettingsLayout.swift`` mirrors it row for row for
the Mac app.  This twin parses the Swift layout and requires it to equal the
Python one (category keys and titles, row order, labels, scopes, the Expert
flag and the one-line summaries), and pins the rules the wording follows:
a row outside Expert is a question (or a glossary term) with a summary, and
the Expert rows close their category.

Hermetic: the repo's own files, no Qt, no network.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Glossary as GLOSSARY  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SWIFT_LAYOUT = REPO_ROOT / "Sources" / "XPTerrainBuilder" / "SettingsLayout.swift"

_LITERAL = r'"((?:[^"\\]|\\.)*)"'
_ITEM = re.compile(
    r"SettingItem\(" + _LITERAL + ", " + _LITERAL + r", \.(app|tile)"
    r"(, expert: true)?(?:, summary: " + _LITERAL + r")?\)")
_CATEGORY = re.compile(
    r'SettingCategory\(key: "(\w+)", title: ' + _LITERAL)


def _rows(text: str) -> list:
    return [(name, label, scope, bool(expert), summary)
            for name, label, scope, expert, summary in _ITEM.findall(text)]


def swift_layout() -> list:
    """``[(key, title, rows)]`` as SettingsLayout.swift declares it; the
    General rows are its ``engineGeneral`` table."""
    text = SWIFT_LAYOUT.read_text(encoding="utf-8")
    general = text.split("static let engineGeneral", 1)[1].split(
        "static let categories", 1)[0]
    layout = [("general", "General", _rows(general))]
    chunks = _CATEGORY.split(text.split("static let categories", 1)[1])
    for index in range(1, len(chunks), 3):
        key, title, body = chunks[index:index + 3]
        layout.append((key, title, _rows(body)))
    return layout


def python_layout() -> list:
    """The same shape from ``_LAYOUT``; the Qt-only preference rows (the
    Mac app has its own X-Plane and output-folder settings) are left out."""
    return [(key, title, [tuple(member) for member in members
                          if member[2] != "pref"])
            for key, title, members in SM._LAYOUT]


def test_swift_layout_equals_python():
    swift, python = swift_layout(), python_layout()
    assert [(k, t) for k, t, _ in swift] == [(k, t) for k, t, _ in python]
    for (key, _, swift_rows), (_, _, python_rows) in zip(
            swift, python, strict=True):
        assert swift_rows == python_rows, key


def test_every_swift_row_was_parsed():
    text = SWIFT_LAYOUT.read_text(encoding="utf-8")
    declared = text.count("SettingItem(\"")
    assert declared == sum(len(rows) for _, _, rows in swift_layout())


def _members():
    for key, _title, members in SM._LAYOUT:
        for member in members:
            yield key, member


def test_rows_outside_expert_are_questions_with_a_summary():
    terms = set(GLOSSARY.TERMS.values())
    for _key, (name, label, _scope, expert, summary) in _members():
        if expert:
            assert summary == "", name
            continue
        assert label.endswith("?") or label in terms, name
        assert summary, name
        assert "\n" not in summary and len(summary) <= 90, name


def test_expert_rows_close_their_category():
    for key, _title, members in SM._LAYOUT:
        flags = [member[3] for member in members]
        assert flags == sorted(flags), key


def test_the_technical_knobs_are_expert():
    # The issue's named knobs: mesh, mask and texture-format tuning.
    for name in ("curvature_tol", "min_angle", "limit_tris", "mask_zl",
                 "texture_mode", "masks_width", "apt_curv_tol"):
        assert SM.get_setting(name).advanced, name


def test_secondary_text():
    plain = SM.get_setting("road_level")
    assert plain.secondary_text() == (
        plain.summary + " · Recommended: "
        + plain.label_for(plain.default))
    assert SM.get_setting("fill_nodata").recommended() == "On"
    expert = SM.get_setting("curvature_tol")
    assert expert.secondary_text() == "curvature_tol · Recommended: 2.0"
    assert SM.get_setting("xplane_dir").secondary_text() == (
        SM.get_setting("xplane_dir").summary)


def test_wording_never_changes_a_key():
    # Wording and grouping only: every row still names a registry key (or
    # a preference), so stored configs read exactly as before.
    import O4_Cfg_Vars
    for _key, (name, _label, scope, _expert, _summary) in _members():
        assert scope == "pref" or name in O4_Cfg_Vars.cfg_vars, name
