"""Twin for the Windows branding pair (RELEASES-PLAN §C1).

Two things brand ``XPTerrainBuilder.exe``, and BOTH fail silently:

* the version resource — a malformed ``VSVersionInfo(...)`` file makes
  PyInstaller drop it (or die late in the freeze), and Explorer then shows
  an exe with blank Details fields;
* the ``Ortho4XP_Qt.spec`` fallback — the release job generates
  ``Utils/icons/generated/icon.ico`` before the freeze, and a dev tree has
  neither that nor ``version_info.txt``.  If the spec did not fall back,
  every local ``pyinstaller Ortho4XP_Qt.spec`` would break.

So the generated file is EXECUTED here in the namespace PyInstaller
provides (stub classes that record their kwargs — PyInstaller itself is not
installed in the dev venv), and the spec's two branding branches are
evaluated against a tmp_path tree.

Hermetic: the repo's own files and ``tmp_path``.  No freeze, no network.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_DIR.parent
MAKE_VERSION_RESOURCE = REPO_ROOT / "scripts" / "make_version_resource.py"
QT_SPEC = ENGINE_DIR / "Ortho4XP_Qt.spec"
APP_VERSION_FILE = REPO_ROOT / "Sources" / "XPTerrainBuilder" / "Resources" / "VERSION"

pytestmark = pytest.mark.skipif(
    not MAKE_VERSION_RESOURCE.is_file() or not APP_VERSION_FILE.is_file(),
    reason="engine used standalone: the app-side release scripts are absent",
)


def _parse_version_info(text: str) -> dict:
    """Execute the file the way PyInstaller does, recording the structure."""
    captured = {}

    class Node:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs

    class VSVersionInfo(Node):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["root"] = self

    class StringStruct(Node):
        def __init__(self, key, value):
            super().__init__(key, value)
            captured.setdefault("strings", {})[key] = value

    namespace = {
        "VSVersionInfo": VSVersionInfo,
        "FixedFileInfo": Node,
        "StringFileInfo": Node,
        "StringTable": Node,
        "StringStruct": StringStruct,
        "VarFileInfo": Node,
        "VarStruct": Node,
    }
    # PyInstaller evaluates the file's single expression.  Drop the leading
    # generator comment (eval mode takes an expression, not a module).
    expression = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    eval(compile(expression, "version_info.txt", "eval"), namespace)
    return captured


def _tracked_app_version() -> str:
    match = re.search(r"[0-9]+\.[0-9]+\.[0-9]+", APP_VERSION_FILE.read_text())
    assert match, "no app version triple tracked"
    return match.group(0)


def test_version_resource_carries_the_release_identity(tmp_path):
    out = tmp_path / "version_info.txt"
    env = dict(os.environ, GITHUB_SHA="0123456789abcdef0123456789abcdef01234567")
    subprocess.run([sys.executable, str(MAKE_VERSION_RESOURCE), str(out)],
                   cwd=REPO_ROOT, check=True, capture_output=True, text=True,
                   env=env)
    parsed = _parse_version_info(out.read_text(encoding="utf-8"))
    strings = parsed["strings"]
    app = _tracked_app_version()

    assert strings["ProductName"] == "XPTerrainBuilder"
    assert strings["FileVersion"] == app
    assert strings["ProductVersion"] == app
    assert strings["OriginalFilename"] == "XPTerrainBuilder.exe"
    # The engine version and the commit live in Comments — the triple a bug
    # report quotes (docs/BETA-PLAN-20260916.md §1 B3).
    assert re.match(r"engine \d+\.\d+\.\d+ · commit 0123456789abcdef",
                    strings["Comments"]), strings["Comments"]

    ffi = parsed["root"].kwargs["ffi"]
    expected = tuple(int(p) for p in app.split(".")) + (0,)
    assert ffi.kwargs["filevers"] == expected
    assert ffi.kwargs["prodvers"] == expected


def test_version_resource_is_deterministic(tmp_path):
    env = dict(os.environ, GITHUB_SHA="deadbeef" * 5)
    first, second = tmp_path / "a.txt", tmp_path / "b.txt"
    for out in (first, second):
        subprocess.run([sys.executable, str(MAKE_VERSION_RESOURCE), str(out)],
                       cwd=REPO_ROOT, check=True, capture_output=True, env=env)
    assert first.read_bytes() == second.read_bytes()


def _spec_branding(cwd: Path) -> dict:
    """Evaluate the spec's branding block with `cwd` as the freeze dir."""
    source = QT_SPEC.read_text(encoding="utf-8")
    start = source.index("_generated_ico =")
    end = source.index("a = Analysis(")
    block = source[start:end]
    namespace = {"os": os}
    here = Path.cwd()
    try:
        os.chdir(cwd)
        exec(block, namespace)
    finally:
        os.chdir(here)
    return namespace


def test_spec_prefers_the_generated_icon_and_version_resource(tmp_path):
    (tmp_path / "Utils" / "icons" / "generated").mkdir(parents=True)
    (tmp_path / "Utils" / "icons" / "generated" / "icon.ico").write_bytes(b"")
    (tmp_path / "version_info.txt").write_text("VSVersionInfo()")
    branding = _spec_branding(tmp_path)
    assert branding["win_icon"] == os.path.join(
        "Utils", "icons", "generated", "icon.ico")
    assert branding["win_version"] == "version_info.txt"


def test_spec_falls_back_in_a_dev_tree(tmp_path):
    """A local freeze with no generated branding must still work."""
    (tmp_path / "Utils" / "icons").mkdir(parents=True)
    (tmp_path / "Utils" / "icons" / "Ortho4XP.ico").write_bytes(b"")
    branding = _spec_branding(tmp_path)
    assert branding["win_icon"] == os.path.join(
        "Utils", "icons", "Ortho4XP.ico")
    assert branding["win_version"] is None


def test_upstream_fallback_icon_is_tracked():
    """The fallback must exist in the tree the dev freeze runs from."""
    assert (ENGINE_DIR / "Utils" / "icons" / "Ortho4XP.ico").is_file()
