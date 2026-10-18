"""issue #836 (B3-04, spec ``step-reuse-content-keys-spec.md`` §2.1) — EACH
REUSABLE TILE STEP'S CODE KEY IS THE IMPORT CLOSURE of its entry modules.

``O4_Step_Code.CODE_MODULES[step]`` is a declared list; this twin
recomputes each step's closure from the SOURCES with the shared walker
(``src/O4_Code_Closure.py``, every module under ``src``, function-level
imports included) and fails on a module the step imports and its list
omits (a STALE REUSE after an edit there — the #346 guarantee), and on a
listed module the step no longer imports.  The freeze digests reproduce
from the specs' by-path execution; a frozen engine reads the file.
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

import O4_Code_Closure as CLOSURE  # noqa: E402
import O4_Step_Code as STEPCODE  # noqa: E402


def _drift(src: Path, entries, declared) -> tuple[list, list]:
    """``(missing, extra)``: closure modules the list omits, listed
    modules outside the closure."""
    closure = set(CLOSURE.closure(str(src), entries))
    return sorted(closure - set(declared)), sorted(set(declared) - closure)


@pytest.mark.parametrize("step", STEPCODE.STEPS)
def test_every_module_a_step_imports_is_in_its_code_key(step):
    missing, extra = _drift(SRC, STEPCODE.ENTRY_MODULES[step],
                            STEPCODE.CODE_MODULES[step])
    assert not missing, (
        f"the {step} step imports these and O4_Step_Code.CODE_MODULES"
        f"[{step!r}] does not key on them — a change there would be a "
        f"STALE REUSE; add them: {missing}")
    assert not extra, (
        f"O4_Step_Code.CODE_MODULES[{step!r}] names modules the step does "
        f"not import; drop them: {extra}")
    listed = STEPCODE.CODE_MODULES[step]
    assert list(listed) == sorted(set(listed))          # one order, no repeats
    assert all(os.path.isfile(CLOSURE.source_path(str(SRC), m)) for m in listed)


def test_the_steps_are_the_reusable_steps():
    import O4_Step_Reuse as REUSE
    assert STEPCODE.STEPS == REUSE.REUSABLE_STEPS
    assert set(STEPCODE.CODE_MODULES) == set(STEPCODE.STEPS)


def test_the_entry_modules_are_where_the_build_enters_each_step():
    """``o4_engine/session.py`` calls these functions; if one moves to
    another module, the step's closure must be re-rooted there."""
    session = (SRC / "o4_engine" / "session.py").read_text(encoding="utf-8")
    for step, (alias, module, function) in {
            "vector": ("VMAP", "O4_Vector_Map", "build_poly_file"),
            "mesh": ("MESH", "O4_Mesh_Utils", "build_mesh"),
            "masks": ("MASK", "O4_Mask_Utils", "build_masks")}.items():
        assert f'"{step}": {alias}.{function},' in session, step
        assert f"import {module} as {alias}" in session, step
        text = (SRC / f"{module}.py").read_text(encoding="utf-8")
        assert f"\ndef {function}(" in text, (module, function)
        assert STEPCODE.ENTRY_MODULES[step][0] == module, step


def test_every_law_table_under_src_is_keyed():
    """The whole-tree digest covered every ``.toml``; the per-step key
    must not lose one."""
    found = sorted(p.relative_to(SRC).as_posix() for p in SRC.rglob("*.toml")
                   if "__pycache__" not in p.parts)
    assert list(STEPCODE.DATA_FILES) == found


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
    """PLANTED: a step that starts importing a module its list omits fails
    the check — inside a function — and the reverse."""
    src = _toy_tree(tmp_path)
    entries, declared = ("O4_Entry",), ("O4_Entry", "O4_Helper")
    assert _drift(src, entries, declared) == ([], [])
    (src / "O4_Entry.py").write_text(
        "import O4_Helper\n\ndef f():\n    from pkg.later import Y\n    return Y\n",
        encoding="utf-8", newline="\n")
    assert _drift(src, entries, declared) == (["pkg.later"], [])
    # on the real tree: drop one module from the mesh step's list
    short = tuple(m for m in STEPCODE.CODE_MODULES["mesh"]
                  if m != "auto_patch.post_mesh")
    assert _drift(SRC, STEPCODE.ENTRY_MODULES["mesh"], short)[0] == [
        "auto_patch.post_mesh"]


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


def test_an_edit_outside_the_closure_keeps_every_step_and_inside_moves_it(
        tmp_path):
    """The point of #836: an edit to the app session (outside every
    step's closure) moved the whole-tree digest and so every step; it no
    longer moves a step.  An edit inside a closure — code or law table —
    does."""
    from auto_patch import provenance_code
    copy = _copy_sources(tmp_path / "src")
    before = STEPCODE.freeze_digests(str(copy))
    whole_before = provenance_code.freeze_digest(str(copy))
    assert all(before.values())
    assert "o4_engine.session" not in STEPCODE.CODE_MODULES["mesh"]
    _append(copy / "o4_engine" / "session.py")
    assert STEPCODE.freeze_digests(str(copy)) == before
    assert provenance_code.freeze_digest(str(copy)) != whole_before
    _append(copy / "O4_Mask_Utils.py")
    inside = STEPCODE.freeze_digests(str(copy))
    assert all(inside[s] != before[s] for s in STEPCODE.STEPS
               if "O4_Mask_Utils" in STEPCODE.CODE_MODULES[s])
    _append(copy / "auto_patch_v2" / "law" / "zones.toml")
    assert all(v != inside[s]
               for s, v in STEPCODE.freeze_digests(str(copy)).items())


@pytest.mark.parametrize("step, module, path", [
    ("mesh", "auto_patch.object_stage", ("auto_patch", "object_stage.py")),
    ("masks", "O4_Imagery_Utils", ("O4_Imagery_Utils.py",)),
])
def test_an_edit_to_one_steps_own_code_moves_that_step_alone(
        tmp_path, step, module, path):
    """The hub cuts (lane ``cloudstepcut``): the post-mesh object stage is
    the mesh step's alone, the imagery module the masks step's alone — an
    edit there re-runs that step and keeps the others."""
    owners = [s for s in STEPCODE.STEPS if module in STEPCODE.CODE_MODULES[s]]
    assert owners == [step], owners
    copy = _copy_sources(tmp_path / "src")
    before = STEPCODE.freeze_digests(str(copy))
    _append(copy.joinpath(*path))
    after = STEPCODE.freeze_digests(str(copy))
    assert {s for s in STEPCODE.STEPS if after[s] != before[s]} == {step}


_FREEZE = r"""
import os, runpy, sys
src, out = sys.argv[1], sys.argv[2]
assert not any(os.path.isfile(os.path.join(p or ".", "O4_Code_Closure.py"))
               for p in sys.path), "the helper must not be importable here"
step = runpy.run_path(os.path.join(src, "O4_Step_Code.py"))
print(step["write_freeze_digest"](src, out))
"""


def test_the_freeze_digests_reproduce_by_path(tmp_path):
    """The specs execute ``O4_Step_Code.py`` BY PATH with ``src`` off
    ``sys.path``: the shared helper is loaded by path, and the file
    written equals the checkout's digests."""
    script = tmp_path / "freeze.py"
    script.write_text(_FREEZE, encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    run = subprocess.run([sys.executable, "-I", str(script), str(SRC), str(out)],
                         cwd=str(tmp_path), capture_output=True, text=True,
                         encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stderr
    path = run.stdout.strip().splitlines()[-1]
    assert os.path.basename(path) == STEPCODE.DIGEST_FILENAME
    table = STEPCODE.frozen_digests(str(out))
    assert table == STEPCODE.freeze_digests(str(SRC))
    assert set(table) == set(STEPCODE.STEPS)


def test_a_frozen_engine_reads_the_file_not_the_sources(tmp_path, monkeypatch):
    table = {s: f"{i:x}" * 64 for i, s in enumerate(STEPCODE.STEPS, 10)}
    text = "".join(f"{s} {table[s]}\n" for s in sorted(table))
    (tmp_path / STEPCODE.DIGEST_FILENAME).write_text(text, encoding="ascii",
                                                    newline="\n")
    monkeypatch.setattr(STEPCODE, "_HERE", str(tmp_path))
    monkeypatch.setattr(STEPCODE, "_DIGESTS", None)
    assert {s: STEPCODE.step_digest(s) for s in STEPCODE.STEPS} == table


def test_the_digest_table_reader_refuses_what_is_not_one(tmp_path):
    assert STEPCODE.frozen_digests(str(tmp_path)) is None           # a checkout
    path = tmp_path / STEPCODE.DIGEST_FILENAME
    path.write_text("mesh not-a-digest\n", encoding="ascii", newline="\n")
    assert STEPCODE.frozen_digests(str(tmp_path)) is None
    with pytest.raises(SystemExit):                 # a listed module with no source
        STEPCODE.write_freeze_digest(str(tmp_path), str(tmp_path / "o5"))
    assert not (tmp_path / "o5" / STEPCODE.DIGEST_FILENAME).exists()


def test_both_specs_write_and_bundle_the_step_digests():
    for spec in ("Ortho4XP.spec", "Ortho4XP_Qt.spec"):
        text = (ROOT / spec).read_text(encoding="utf-8")
        assert ('os.path.join("src", "O4_Step_Code.py")\n)["write_freeze_digest"]'
                '("src"') in text, spec
        assert 'v2_law_datas + [(_step_digest_file, ".")]' in text, spec
