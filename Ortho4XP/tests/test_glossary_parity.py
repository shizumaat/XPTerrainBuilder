"""One glossary, three readers (issue #831).

``src/O4_Glossary.py`` (the Qt app's table), its Swift mirror
``Sources/SceneryKit/Glossary.swift`` (the Mac app's) and the user docs'
``docs/glossary.md`` hold the same plain wording.  This twin parses the
Swift file and requires its tables to equal the Python ones, requires every
wording in the docs, pins the step-label mapping on the engine's real label
forms, and greps both apps for the retired PRIMARY labels.

Hermetic: the repo's own files, no Qt, no network.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Glossary as GLOSSARY  # noqa: E402

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
SWIFT_GLOSSARY = REPO_ROOT / "Sources" / "SceneryKit" / "Glossary.swift"
DOC = REPO_ROOT / "docs" / "glossary.md"
SWIFT_UI_DIRS = (REPO_ROOT / "Sources" / "XPTerrainBuilder",
                 REPO_ROOT / "Sources" / "SceneryKit")
QT_UI_GLOB = "O4_Qt_*.py"


def _swift_table(name: str) -> dict:
    """The literal ``static let <name>: [K: String] = [ … ]`` table."""
    text = SWIFT_GLOSSARY.read_text(encoding="utf-8")
    block = re.search(
        r"static let %s: \[(\w+): String\] = \[(.*?)\n    \]" % name,
        text, re.S)
    assert block, "Glossary.swift has no %s table" % name
    key_type, body = block.groups()
    pairs = re.findall(r'^\s*("?[\w]+"?): "((?:[^"\\]|\\.)*)",\s*$',
                       body, re.M)
    if key_type == "Int":
        return {int(key): value for key, value in pairs}
    return {key.strip('"'): value for key, value in pairs}


@pytest.mark.parametrize("swift_name, python_table", [
    ("terms", GLOSSARY.TERMS),
    ("stepNames", GLOSSARY.STEP_NAMES),
    ("detailNames", GLOSSARY.DETAIL_NAMES),
    ("detailPixelSizes", GLOSSARY.DETAIL_PIXEL_SIZES),
])
def test_swift_tables_equal_python(swift_name, python_table):
    assert _swift_table(swift_name) == python_table


def test_docs_carry_every_wording():
    doc = DOC.read_text(encoding="utf-8")
    missing = [value for key, value in GLOSSARY.TERMS.items()
               if value.replace("{n}", "N") not in doc]
    assert missing == []


def test_every_engine_step_has_a_plain_name():
    from o4_engine import session
    assert set(session.STEP_LABELS) <= set(GLOSSARY.STEP_NAMES)


def test_every_legacy_driver_step_has_a_plain_name():
    text = (REPO_ROOT / "Sources" / "SceneryKit"
            / "OrthoBuildRunner.swift").read_text(encoding="utf-8")
    steps = re.search(r"static let allSteps = \[(.*?)\]", text).group(1)
    for step in re.findall(r'"(\w+)"', steps) + ["overlay"]:
        assert step in GLOSSARY.STEP_NAMES


@pytest.mark.parametrize("key, label, shown", [
    # The engine's label forms (o4_engine.session: _step_label,
    # reused_label, the auto-patch fold).
    ("mesh", "triangulating", "Shape the ground"),
    ("vector", "vector data · airport insets +38-009",
     "Download map data (roads, water, airports) · airport insets +38-009"),
    ("masks", "water masks · reused (unchanged since the last build)",
     "Blend coastlines and water · reused (unchanged since the last build)"),
    ("vector", "auto-patch 2/5 · LFRB", "Grading airports 2/5 · LFRB"),
    ("imagery", "imagery & DSF", "Imagery and scenery file"),
    ("unknown", "something else", "something else"),
])
def test_step_display(key, label, shown):
    assert GLOSSARY.step_display(key, label) == shown


def test_detail_label():
    assert GLOSSARY.detail_label(16) == "Standard (~2 m per pixel)"
    assert GLOSSARY.detail_choice(16) == "Standard (~2 m per pixel) · ZL16"
    assert GLOSSARY.detail_label(9) == "ZL9"
    assert set(GLOSSARY.DETAIL_NAMES) == set(GLOSSARY.DETAIL_PIXEL_SIZES)


def test_surface_check():
    assert GLOSSARY.surface_check(3) == (
        "Airport surface check: 3 spots outside the rules")


# --- The acceptance grep: no retired word as a primary label ---------------
#
# Every string literal of both apps' UI code (docstrings and comments are not
# UI) is searched for the RETIRED phrases.  The phrases are specific enough
# ("Build ZL", "Revert to auto", "Patch · ") that secondary text rarely
# carries them; a literal that legitimately does is listed here with why.
ALLOWED = {
    # (file name, retired phrase): reason
}


def _swift_literals(path: Path):
    for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        code = line.split("//", 1)[0] if not line.lstrip().startswith(
            "//") else ""
        for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', code):
            yield number, literal


def _python_literals(path: Path):
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(
                    getattr(first, "value", None), ast.Constant):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node.lineno, node.value


def _ui_sources():
    for directory in SWIFT_UI_DIRS:
        for path in sorted(directory.glob("*.swift")):
            if path != SWIFT_GLOSSARY:
                yield path, _swift_literals(path)
    src = ENGINE_DIR / "src"
    for path in sorted(src.glob(QT_UI_GLOB)) + [src / "O4_Settings_Model.py"]:
        yield path, _python_literals(path)


def test_no_retired_primary_label():
    phrases = [phrase for retired in GLOSSARY.RETIRED.values()
               for phrase in retired]
    found = []
    for path, literals in _ui_sources():
        for number, literal in literals:
            for phrase in phrases:
                if (phrase in literal
                        and (path.name, phrase) not in ALLOWED):
                    found.append("%s:%d %r" % (path.name, number, literal))
    assert found == []
