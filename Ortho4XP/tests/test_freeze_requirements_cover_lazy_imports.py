"""The frozen engine must carry every third-party module the engine
imports LAZILY (inside a function), because PyInstaller's static scan sees
only module-level imports and ``scripts/make_engine.sh`` installs the
freeze venv from ``requirements.txt``.

Precedent (owner 2026-09-10): ``auto_patch_v2/solve/project.py`` imports
``highspy`` inside the solve; the dev venv had it, ``requirements.txt`` and
the spec did not, and app 1.0.298/1.0.299 failed every v2 airport with
"No module named 'highspy'" (HECA, LERM) while the suite stayed green.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

#: Top-level packages that are neither stdlib nor the engine's own.
_ENGINE_TOP = {"auto_patch", "auto_patch_v2", "o4_engine"}


def _requirement_names() -> set[str]:
    names = set()
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)", line)
        if m:
            names.add(m.group(1).lower().replace("-", "_"))
    return names


#: Distribution name → importable top-level module, where they differ.
_IMPORT_OF = {"pillow": "pil", "scikit_fmm": "skfmm", "rtree": "rtree",
              "pyside6": "pyside6", "imagecodecs": "imagecodecs",
              "gdal": "osgeo"}


def _lazy_third_party_imports() -> dict[str, list[str]]:
    """``{module: [file:line, ...]}`` for every import statement that is
    NOT at module level, whose top-level package is neither stdlib nor
    the engine nor a relative import."""
    stdlib = set(sys.stdlib_module_names)
    found: dict[str, list[str]] = {}
    for py in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    tops = [a.name.split(".")[0] for a in sub.names]
                elif isinstance(sub, ast.ImportFrom) and sub.level == 0 and sub.module:
                    tops = [sub.module.split(".")[0]]
                else:
                    continue
                for top in tops:
                    if top in stdlib or top in _ENGINE_TOP or top.startswith("O4_"):
                        continue
                    if (SRC / f"{top}.py").exists() or (SRC / top).is_dir():
                        continue
                    if (ROOT / "tools" / f"{top}.py").exists() or \
                            (ROOT / "tools" / "harness" / f"{top}.py").exists():
                        continue          # repo-local tool modules (dev paths)
                    found.setdefault(top, []).append(f"{py.relative_to(ROOT)}:{sub.lineno}")
    return found


def test_every_lazily_imported_third_party_module_is_pinned():
    pinned = _requirement_names()
    importable = {_IMPORT_OF.get(n, n) for n in pinned} | pinned
    lazy = _lazy_third_party_imports()
    assert "highspy" in lazy, "the precedent itself must be seen by this scan"
    missing = {m: sites for m, sites in lazy.items()
               if m.lower() not in importable and m.lower() not in {"pyinstaller"}}
    assert not missing, (
        "lazily imported third-party modules absent from requirements.txt — "
        "the frozen engine will not carry them (the highspy precedent): "
        f"{missing}")
