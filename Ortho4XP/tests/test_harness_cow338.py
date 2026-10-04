"""THE COPY-ON-WRITE TWINS — issue #338, "a worktree must not cost 29 GB".

MEASURED 2026-10-04: every lane's ``tmp/engine_caches/Airport_mod_cache``
reads ~29 GB under ``du`` and was taken for a full copy made by
``lane_worktree.sh up``.  Neither half held: ``up`` never touches ``tmp``
(the first build seeds the overlay), and the overlay is APFS clones — 0 to
130 MB PRIVATE in five live trees.  What these twins pin is the instrument
that can tell (``tools/harness/cow_audit.py``: private bytes, not ``du``),
the one real full copy ``up`` did make (``Patches``, now ``cp -cR``), and
``reclaim`` — which re-clones only private files that are byte-identical
to the shared corpus and refuses under a live build.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":                                # pragma: no cover
    pytest.skip("tools/harness is a POSIX-only lane instrument",
                allow_module_level=True)

from test_harness import _ritual, _tiny_repo               # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
CACHE = Path("tmp") / "engine_caches" / "Airport_mod_cache"
BLOB = b"sidecar " * 32768                                  # 256 KB


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HARNESS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cow():
    return _load("cow_audit")


@pytest.fixture(scope="module")
def clonefile():
    sys.path.insert(0, str(HARNESS))
    from shared_repo_guard import _clonefile
    return _clonefile


def _needs_cow(cow, clonefile, tmp_path):
    """Skip where the volume cannot clone or cannot report private size."""
    probe, clone = tmp_path / "probe", tmp_path / "probe.clone"
    probe.write_bytes(BLOB)
    if not clonefile(str(probe), str(clone)) or cow.private_bytes(clone) is None:
        pytest.skip("needs macOS + APFS (clonefile and ATTR_CMNEXT_PRIVATESIZE)")


def _seed(shared: Path, tree: Path, clonefile) -> None:
    """A corpus of three files and an overlay holding one of each class:
    an untouched clone, a private IDENTICAL copy, a REWRITTEN sidecar and
    a lane-DERIVED file with no shared counterpart."""
    (shared / "Pack").mkdir(parents=True, exist_ok=True)
    for name in ("clone.bin", "copy.bin", "rewritten.bin"):
        (shared / "Pack" / name).write_bytes(BLOB + name.encode())
    (tree / "Pack").mkdir(parents=True)
    assert clonefile(str(shared / "Pack" / "clone.bin"),
                     str(tree / "Pack" / "clone.bin"))
    (tree / "Pack" / "copy.bin").write_bytes(BLOB + b"copy.bin")
    (tree / "Pack" / "rewritten.bin").write_bytes(BLOB + b"the lane's own")
    (tree / "Pack" / "derived.bin").write_bytes(BLOB + b"lane only")


def test_private_bytes_tells_a_clone_from_a_copy(cow, clonefile, tmp_path):
    """``du`` cannot: both files allocate the same blocks.  A clone's
    private size is 0; a byte copy's is its whole allocation."""
    _needs_cow(cow, clonefile, tmp_path)
    source, clone, copy = (tmp_path / n for n in ("s", "clone", "copy"))
    source.write_bytes(BLOB)
    assert clonefile(str(source), str(clone))
    copy.write_bytes(BLOB)
    assert clone.stat().st_blocks == copy.stat().st_blocks
    assert cow.private_bytes(clone) == 0
    assert cow.private_bytes(copy) >= len(BLOB)


def test_reseed_reclones_identical_files_and_keeps_the_lanes_own(
        cow, clonefile, tmp_path):
    _needs_cow(cow, clonefile, tmp_path)
    shared, tree = tmp_path / "shared", tmp_path / "tree"
    _seed(shared, tree, clonefile)
    before = cow.audit_tree(str(tree), str(shared))
    assert (before["files"], before["identical"][0], before["rewritten"][0],
            before["lane_only"][0]) == (4, 1, 1, 1)

    after = cow.reseed_tree(str(tree), str(shared))
    assert (after["recloned"], after["failed"]) == (1, 0)
    assert cow.private_bytes(tree / "Pack" / "copy.bin") == 0
    assert (tree / "Pack" / "copy.bin").read_bytes() == BLOB + b"copy.bin"
    assert (tree / "Pack" / "rewritten.bin").read_bytes() == BLOB + b"the lane's own"
    assert (tree / "Pack" / "derived.bin").read_bytes() == BLOB + b"lane only"
    assert (shared / "Pack" / "rewritten.bin").read_bytes() == BLOB + b"rewritten.bin"
    assert sorted(p.name for p in (tree / "Pack").iterdir()) == [
        "clone.bin", "copy.bin", "derived.bin", "rewritten.bin"], (
        "no .reclone scratch file may be left behind")
    assert cow.audit_tree(str(tree), str(shared))["identical"][0] == 0


def test_audit_is_total_where_private_size_is_unknown(cow, tmp_path, monkeypatch):
    """Off APFS the audit says NOT MEASURABLE instead of guessing."""
    (tmp_path / "f").write_bytes(BLOB)
    monkeypatch.setattr(cow, "private_bytes", lambda path: None)
    report = cow.audit_tree(str(tmp_path))
    assert report["measurable"] is False and report["files"] == 1
    assert "NOT MEASURABLE" in cow.describe(report)


def _lane(tmp_path):
    main, data, env, _old = _tiny_repo(tmp_path)
    env["O4_HARNESS_PYTHON"] = sys.executable
    # A tile dir the checkout does not already carry (`up` clones per tile
    # dir), and the real repo's ignore of the lane's ``tmp`` product area.
    big = main / "Ortho4XP" / "Patches" / "+10+010" / "big.patch.osm"
    big.parent.mkdir()
    big.write_bytes(BLOB)
    with open(main / ".git" / "info" / "exclude", "a", encoding="utf-8") as fh:
        fh.write("Ortho4XP/tmp/\n")
    up = _ritual(env, "up", "lane1")
    assert up.returncode == 0, up.stdout + up.stderr
    return main, data, env, up, main / ".claude" / "worktrees" / "lane1"


def test_up_clones_patches_copy_on_write_and_leaves_tmp_alone(
        cow, clonefile, tmp_path):
    """The one full copy `up` really made was ``Patches`` (cp -R).  It is
    a clone now, and ``tmp/engine_caches`` is not created at all — the
    first build seeds it."""
    _needs_cow(cow, clonefile, tmp_path)
    _main, _data, env, up, lane = _lane(tmp_path)
    cloned = lane / "Ortho4XP" / "Patches" / "+10+010" / "big.patch.osm"
    assert cloned.read_bytes() == BLOB
    assert cow.private_bytes(cloned) == 0, "Patches must be clonefile clones"
    assert "copy-on-write clones" in up.stdout and "FULL COPY" not in up.stdout
    assert not (lane / "Ortho4XP" / "tmp").exists()
    check = _ritual(env, "check", "lane1")
    assert check.returncode == 0, check.stdout + check.stderr
    assert "the first build seeds it" in check.stdout


def test_check_flags_a_full_copy_and_reclaim_fixes_it(cow, clonefile, tmp_path):
    _needs_cow(cow, clonefile, tmp_path)
    _main, data, env, _up, lane = _lane(tmp_path)
    shared, tree = data / "Airport_mod_cache", lane / "Ortho4XP" / CACHE
    _seed(shared, tree, clonefile)
    for i in range(6):                       # most of the tree a real copy
        (shared / "Pack" / f"c{i}.bin").write_bytes(BLOB + b"x")
        (tree / "Pack" / f"c{i}.bin").write_bytes(BLOB + b"x")

    check = _ritual(env, "check", "lane1")
    assert "FULL COPY" in check.stdout and "reclaim lane1" in check.stdout
    assert check.returncode == 0, "a full copy is REPORTED, never a refusal"

    # A python process whose cwd is the lane's engine dir IS a build.
    build = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=lane / "Ortho4XP")
    try:
        refused = _ritual(env, "reclaim", "lane1")
        assert refused.returncode == 2, refused.stdout + refused.stderr
        assert "a build is running" in refused.stderr
        assert cow.private_bytes(tree / "Pack" / "copy.bin") > 0
    finally:
        build.kill()
        build.wait()

    done = _ritual(env, "reclaim", "lane1")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "RECLONED 7" in done.stdout
    assert cow.private_bytes(tree / "Pack" / "copy.bin") == 0
    assert (tree / "Pack" / "rewritten.bin").read_bytes() == BLOB + b"the lane's own"
    assert "FULL COPY" not in _ritual(env, "check", "lane1").stdout


def test_reclaim_takes_the_main_tree_and_nothing_else_does(
        cow, clonefile, tmp_path):
    """The main tree holds a lane-persistent overlay too, so `reclaim`
    accepts its PATH; `check` and `down` still refuse it."""
    _needs_cow(cow, clonefile, tmp_path)
    main, data, env, _up, _lane_dir = _lane(tmp_path)
    _seed(data / "Airport_mod_cache", main / "Ortho4XP" / CACHE, clonefile)
    done = _ritual(env, "reclaim", str(main) + "/")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "RECLONED 1" in done.stdout
    for action in ("check", "down"):
        refused = _ritual(env, action, str(main) + "/")
        assert refused.returncode == 2 and "MAIN repository" in refused.stderr
