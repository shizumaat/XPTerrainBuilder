"""issue #880 — THE PATCH FRESHNESS GATE KEYS ON THE PATCH BUILD'S CODE
CLOSURE, not the whole tree (``auto_patch.provenance_code``).

``PATCH_CODE_MODULES`` is a declared list; this twin recomputes the static
import closure of the patch build from the SOURCES with the shared walker
(``src/O4_Code_Closure.py``: every module under ``src``, function-level
imports included, the packages above them) and fails on a module the build
imports and the list omits — a STALE REUSE after an edit there, the #346
guarantee — and on the reverse.  A second, independent walker (the v1
retirement twin's) must land inside the list too.  Then: an edit outside
the closure keeps the patch's code key and an edit inside moves it; the
off switch restores the whole-tree key; the freeze reproduces by path and
a frozen engine reads its file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))

import O4_Code_Closure as CLOSURE  # noqa: E402
from auto_patch import provenance_code as CODE  # noqa: E402


def _drift(src: Path, entries, declared) -> tuple[list, list]:
    """``(missing, extra)``: closure modules the list omits, listed modules
    outside the closure."""
    closure = set(CLOSURE.closure(str(src), entries, packages=True))
    return sorted(closure - set(declared)), sorted(set(declared) - closure)


def test_every_module_the_patch_build_imports_is_in_its_code_key():
    missing, extra = _drift(SRC, CODE.PATCH_ENTRY_MODULES, CODE.PATCH_CODE_MODULES)
    assert not missing, (
        "the patch build imports these and provenance_code.PATCH_CODE_MODULES "
        "does not key on them — a change there would be a STALE REUSE of "
        f"every airport's patch; add them: {missing}")
    assert not extra, (
        "provenance_code.PATCH_CODE_MODULES names modules the patch build does "
        f"not import; drop them: {extra}")
    listed = CODE.PATCH_CODE_MODULES
    assert list(listed) == sorted(set(listed))          # one order, no repeats
    assert all(os.path.isfile(CLOSURE.source_path(str(SRC), m)) for m in listed)
    for must in ("auto_patch.driver", "auto_patch.engine_v2",
                 "auto_patch_v2.pipeline.build", "auto_patch_v2.solve.project_strip",
                 "O4_DEM_Utils", "auto_patch_v2.pipeline"):
        assert must in listed, must


def test_a_second_walker_lands_inside_the_list_too():
    """The v1 retirement twin walks imports its own way (``__import__``
    blind spot table included); whatever it reaches from the patch build's
    entries must be keyed as well."""
    import test_v1_retired as RETIRED

    mods = RETIRED._modules()
    seen: set[str] = set()
    stack = ["auto_patch.driver", "auto_patch.engine_v2"]
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        seen.add(module)
        for name in RETIRED._imports_of(mods[module], module):
            resolved = RETIRED._resolve(name, mods)
            if resolved and resolved not in seen:
                stack.append(resolved)
    assert len(seen) > 300, f"the closure collapsed to {len(seen)}"
    outside = sorted(seen - set(CODE.PATCH_CODE_MODULES))
    assert not outside, outside


def test_the_entry_is_where_the_tile_build_enters_the_patch_build():
    vmap = (SRC / "O4_Vector_Map.py").read_text(encoding="utf-8")
    assert "generate_auto_patches" in vmap
    driver = (SRC / "auto_patch" / "driver.py").read_text(encoding="utf-8")
    assert "\ndef generate_auto_patches(" in driver
    assert CODE.PATCH_ENTRY_MODULES == ("auto_patch.driver",)


def test_what_cannot_shape_a_patch_is_outside_the_key():
    """The point of #880: the app around the build."""
    listed = set(CODE.PATCH_CODE_MODULES)
    for outside in ("O4_Qt_GUI", "O4_Qt_Settings", "O4_Qt_Patch_Editor",
                    "o4_engine.patch_commands", "o4_engine.jsonl",
                    "O4_MSFS_Package", "auto_patch_v2.pipeline.__main__"):
        assert outside not in listed, outside


def test_every_law_table_under_src_is_keyed():
    """The whole-tree digest covered every ``.toml``; the closure key must
    not lose one."""
    found = sorted(p.relative_to(SRC).as_posix() for p in SRC.rglob("*.toml")
                   if "__pycache__" not in p.parts)
    assert list(CODE.PATCH_DATA_FILES) == found


def _toy_tree(root: Path) -> Path:
    src = root / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    (src / "O4_Entry.py").write_text("import O4_Helper\n", encoding="utf-8",
                                     newline="\n")
    (src / "O4_Helper.py").write_text("X = 1\n", encoding="utf-8", newline="\n")
    (src / "pkg" / "later.py").write_text("Y = 2\n", encoding="utf-8", newline="\n")
    return src


def test_the_twin_bites(tmp_path):
    """PLANTED: an entry that starts importing a module the list omits
    fails the check — inside a function, with its package — and the
    reverse; on the real tree, dropping one module fails it."""
    src = _toy_tree(tmp_path)
    entries, declared = ("O4_Entry",), ("O4_Entry", "O4_Helper")
    assert _drift(src, entries, declared) == ([], [])
    (src / "O4_Entry.py").write_text(
        "import O4_Helper\n\ndef f():\n    from pkg.later import Y\n    return Y\n",
        encoding="utf-8", newline="\n")
    assert _drift(src, entries, declared) == (["pkg", "pkg.later"], [])
    (src / "pkg" / "__init__.py").write_text("import O4_Late\n", encoding="utf-8",
                                             newline="\n")
    (src / "O4_Late.py").write_text("Z = 3\n", encoding="utf-8", newline="\n")
    assert _drift(src, entries, declared)[0] == ["O4_Late", "pkg", "pkg.later"]
    short = tuple(m for m in CODE.PATCH_CODE_MODULES
                  if m != "auto_patch_v2.pipeline.emit_stage")
    assert _drift(SRC, CODE.PATCH_ENTRY_MODULES, short)[0] == [
        "auto_patch_v2.pipeline.emit_stage"]


def _copy_sources(dest: Path) -> Path:
    """The ``.py`` / ``.toml`` sources under ``src``, copied to ``dest``."""
    def ignore(directory, names):
        return [n for n in names if n == "__pycache__" or (
            os.path.isfile(os.path.join(directory, n))
            and not n.endswith((".py", ".toml")))]
    shutil.copytree(SRC, dest, ignore=ignore)
    return dest


def _append(path: Path) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n# edited\n")


@pytest.mark.parametrize("path", [
    ("O4_Qt_GUI.py",), ("O4_Qt_Settings.py",), ("O4_Qt_Patch_Editor.py",),
    ("o4_engine", "patch_commands.py"), ("O4_MSFS_Package.py",)])
def test_an_edit_outside_the_closure_keeps_the_patch_code_key(tmp_path, path):
    """A UI / app-command edit moved the whole-tree digest — and so staled
    every patch; it no longer moves the patch's key."""
    copy = _copy_sources(tmp_path / "src")
    before = CODE.patch_freeze_digest(str(copy))
    whole = CODE.freeze_digest(str(copy))
    assert before and whole
    _append(copy.joinpath(*path))
    assert CODE.patch_freeze_digest(str(copy)) == before
    assert CODE.freeze_digest(str(copy)) != whole


@pytest.mark.parametrize("path", [
    ("auto_patch_v2", "pipeline", "emit_stage.py"),      # a stage
    ("auto_patch_v2", "solve", "project_strip.py"),
    ("auto_patch", "driver.py"),                          # the gate itself
    ("O4_DEM_Utils.py",),                                 # the DEM the solve reads
    ("auto_patch_v2", "pipeline", "__init__.py"),         # a package above one
    ("auto_patch_v2", "law", "zones.toml")])              # a law table
def test_an_edit_inside_the_closure_moves_the_patch_code_key(tmp_path, path):
    copy = _copy_sources(tmp_path / "src")
    before = CODE.patch_freeze_digest(str(copy))
    _append(copy.joinpath(*path))
    assert CODE.patch_freeze_digest(str(copy)) != before


def test_the_off_switch_restores_the_whole_tree_key(monkeypatch):
    """``O4_PATCH_FRESHNESS_WHOLE_TREE=1`` stamps #346's digest — the one an
    engine before #880 stamped, so its patches read as current again."""
    monkeypatch.setattr(CODE, "_PATCH_DIGEST", None)
    closure = CODE.freshness_code_digest({})
    assert closure == CODE.patch_freeze_digest(str(SRC))[:16]
    assert CODE.freshness_code_digest({CODE.WHOLE_TREE_ENV: "1"}) == CODE.code_digest()
    assert CODE.freshness_code_digest({CODE.WHOLE_TREE_ENV: "0"}) == closure
    assert closure != CODE.code_digest()
    monkeypatch.setenv(CODE.WHOLE_TREE_ENV, "1")
    assert CODE.freshness_code_digest() == CODE.code_digest()


def test_the_off_switch_is_classified():
    from auto_patch import provenance_env as ENV
    assert CODE.WHOLE_TREE_ENV in ENV.RUN_ENVIRONMENT


_FREEZE = r"""
import os, runpy, sys
src, out = sys.argv[1], sys.argv[2]
assert not any(os.path.isfile(os.path.join(p or ".", "O4_Code_Closure.py"))
               for p in sys.path), "the helper must not be importable here"
code = runpy.run_path(os.path.join(src, "auto_patch", "provenance_code.py"))
print(code["write_patch_freeze_digest"](src, out))
"""


def test_the_freeze_digest_reproduces_by_path(tmp_path):
    """The specs execute ``provenance_code.py`` BY PATH with ``src`` off
    ``sys.path``: the shared helper is loaded by path, and the file written
    equals the checkout's digest."""
    script = tmp_path / "freeze.py"
    script.write_text(_FREEZE, encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, "-I", str(script), str(SRC), str(out)],
                         cwd=str(tmp_path), capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stderr
    path = run.stdout.strip().splitlines()[-1]
    assert os.path.basename(path) == CODE.PATCH_DIGEST_FILENAME
    assert CODE.frozen_patch_digest(str(out)) == CODE.patch_freeze_digest(str(SRC))


def test_a_frozen_engine_reads_the_file_not_the_sources(tmp_path, monkeypatch):
    (tmp_path / CODE.PATCH_DIGEST_FILENAME).write_text(
        "cd" * 32 + "\n", encoding="ascii", newline="\n")
    monkeypatch.setattr(CODE, "frozen_patch_digest",
                        lambda directory=None, _f=CODE.frozen_patch_digest:
                        _f(str(tmp_path)))
    monkeypatch.setattr(CODE, "_PATCH_DIGEST", None)
    assert CODE.freshness_code_digest({}) == "cd" * 8


def test_the_freeze_refuses_what_it_cannot_digest(tmp_path):
    assert CODE.frozen_patch_digest(str(tmp_path)) is None          # a checkout
    (tmp_path / CODE.PATCH_DIGEST_FILENAME).write_text(
        "not a digest\n", encoding="ascii", newline="\n")
    assert CODE.frozen_patch_digest(str(tmp_path)) is None
    with pytest.raises(SystemExit):                 # a listed module with no source
        CODE.write_patch_freeze_digest(str(tmp_path), str(tmp_path / "o5"))
    assert not (tmp_path / "o5" / CODE.PATCH_DIGEST_FILENAME).exists()


def test_both_specs_write_and_bundle_the_patch_digest():
    for spec in ("Ortho4XP.spec", "Ortho4XP_Qt.spec"):
        text = (ROOT / spec).read_text(encoding="utf-8")
        assert ('os.path.join("src", "auto_patch", "provenance_code.py")\n)'
                '["write_patch_freeze_digest"]("src"') in text, spec
        assert '(_patch_digest_file, "auto_patch")' in text, spec
