"""Issue #346 — THE PATCH FRESHNESS GATE'S CODE DIGEST
(``auto_patch.provenance_code``): what it reads, that an edit moves it,
that a frozen engine gets it from the file the freeze wrote, and that the
patch build's import closure stays inside what is digested.

The gate-side twins (same code → reuse; changed code → rebuild with the
reason line) live with the gate's other inputs in
``tests/test_auto_patch_freshness.py``.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
SRC = ENGINE / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ENGINE / "tests"))

from auto_patch import provenance_code as CODE          # noqa: E402

SPECS = ("Ortho4XP.spec", "Ortho4XP_Qt.spec")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def _toy_engine(root: Path) -> Path:
    """A minimal ``src``: the version file, one module, one law table and
    the real ``partition_code`` whose ``digest_of`` the digest reuses."""
    src = root / "src"
    airport = src / "auto_patch_v2" / "airport"
    airport.mkdir(parents=True)
    shutil.copy(SRC / "auto_patch_v2" / "airport" / "partition_code.py", airport)
    _write(src / "O4_Version.py", "version='1.50.1'\n")
    (src / "auto_patch_v2" / "law").mkdir()
    _write(src / "auto_patch_v2" / "law" / "grades.toml", "limit = 1.5\n")
    _write(src / "solve.py", "STEP = 1\n")
    return src


def test_the_digest_reads_every_module_and_law_table():
    names = [name for name, _path in CODE.source_files(str(SRC))]
    assert names == sorted(names) and len(names) == len(set(names))
    assert "auto_patch/driver.py" in names
    assert "auto_patch_v2/pipeline/__init__.py" in names
    assert "O4_DEM_Utils.py" in names
    tables = [n for n in names if n.endswith(".toml")]
    assert "auto_patch_v2/law/families.toml" in tables
    assert "auto_patch_v2/classify/rules.toml" in tables, (
        "a table outside law/ is law too — the rule is the suffix")
    assert not [n for n in names if "__pycache__" in n]
    digest = CODE.freeze_digest(str(SRC))
    assert digest and len(digest) == 64
    assert CODE.code_digest() == digest[:16]


def test_an_edit_anywhere_moves_the_digest_and_the_version_does_not(tmp_path):
    """THE DEFECT (#346): the solve changed, ``O4_Version`` did not."""
    src = _toy_engine(tmp_path)
    before = CODE.freeze_digest(str(src))
    assert before == CODE.freeze_digest(str(src)), "stable across reads"
    _write(src / "solve.py", "STEP = 2\n")
    edited = CODE.freeze_digest(str(src))
    _write(src / "auto_patch_v2" / "law" / "grades.toml", "limit = 2.0\n")
    law = CODE.freeze_digest(str(src))
    _write(src / "new_pass.py", "")
    added = CODE.freeze_digest(str(src))
    assert len({before, edited, law, added}) == 4
    assert (src / "O4_Version.py").read_text(encoding="utf-8") == \
        "version='1.50.1'\n"
    # a compiled cache is not source
    (src / "__pycache__").mkdir()
    _write(src / "__pycache__" / "solve.cpython-312.py", "x")
    assert CODE.freeze_digest(str(src)) == added


def test_the_freeze_writes_the_file_a_frozen_engine_reads(tmp_path,
                                                          monkeypatch):
    src = _toy_engine(tmp_path)
    written = CODE.write_freeze_digest(str(src), str(tmp_path / "out"))
    assert os.path.basename(written) == CODE.DIGEST_FILENAME
    assert CODE.frozen_digest(str(tmp_path / "out")) == \
        CODE.freeze_digest(str(src))
    # the frozen engine: no sources, the file beside the module
    monkeypatch.setattr(CODE, "frozen_digest",
                        lambda directory=None: "ab" * 32)
    monkeypatch.setattr(CODE, "_CODE_DIGEST", None)
    assert CODE.code_digest() == "ab" * 8


def test_a_frozen_engine_without_the_file_never_digests_its_bundle(
        monkeypatch, tmp_path):
    """``_internal`` holds third-party ``.py`` files; walking it would be
    a digest of somebody else's code.  ``absent`` is the stamp instead,
    and the freeze refuses to be that engine."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(CODE, "frozen_digest", lambda directory=None: None)
    monkeypatch.setattr(CODE, "_CODE_DIGEST", None)
    assert CODE.code_digest() == "absent"
    monkeypatch.undo()
    _write(tmp_path / CODE.DIGEST_FILENAME, "not a digest\n")
    assert CODE.frozen_digest(str(tmp_path)) is None
    try:
        CODE.write_freeze_digest(str(tmp_path / "no_engine"), str(tmp_path))
    except SystemExit as refusal:
        assert "refusing to freeze" in str(refusal)
    else:                                               # pragma: no cover
        raise AssertionError("a freeze with no digest must refuse")


def test_the_patch_builds_import_closure_is_inside_the_digest():
    """THE GUARD (the partition key's closure twin, for the patch): every
    first-party module the patch build can import is a file the digest
    reads — a module that moved outside ``src`` would be a stale HIT."""
    import test_v1_retired as RETIRED

    mods = RETIRED._modules()
    digested = {path for _name, path in CODE.source_files(str(SRC))}
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
    outside = sorted(m for m in seen if str(mods[m]) not in digested)
    assert not outside, outside


def test_both_specs_write_the_digest_into_the_bundle():
    """A freeze that skips it ships an engine keyed on the version alone;
    each spec runs the module's own writer and bundles the file beside it."""
    for name in SPECS:
        source = (ENGINE / name).read_text(encoding="utf-8")
        assert 'os.path.join("src", "auto_patch", "provenance_code.py")' \
            in source, name
        assert '(_engine_digest_file, "auto_patch")' in source, name
