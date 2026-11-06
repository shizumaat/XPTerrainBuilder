"""Twin for scripts/engine_stamp.sh: make_app.sh refuses a frozen engine not
frozen from its own source (app 1.0.471 embedded the 1.0.470 engine).

Fake repo + fake bundle dir; no real freeze."""
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *_ID, *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _stamp(mode, frozen, root):
    return subprocess.run(
        ["bash", str(root / "scripts/engine_stamp.sh"), mode, str(frozen), str(root)],
        capture_output=True, text=True)


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    for name in ("engine_stamp.sh", "tree_dirty.sh"):
        shutil.copy(REPO / "scripts" / name, root / "scripts" / name)
    (root / "Ortho4XP/src").mkdir(parents=True)
    (root / "Ortho4XP/src/O4_Version.py").write_text(
        "version = '1.0'\n", encoding="utf-8", newline="\n")
    (root / "Ortho4XP/src/code.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "a")
    frozen = tmp_path / "dist/Ortho4XP"
    frozen.mkdir(parents=True)
    return root, frozen


def test_missing_stamp_refuses(tmp_path):
    root, frozen = _repo(tmp_path)
    r = _stamp("check", frozen, root)
    assert r.returncode == 1 and "REFUSING" in r.stderr
    assert "run scripts/make_engine.sh" in r.stderr


def test_matching_stamp_reports_embedded_commit(tmp_path):
    root, frozen = _repo(tmp_path)
    assert _stamp("write", frozen, root).returncode == 0
    # The version bump both scripts make is not dirt.
    (root / "Ortho4XP/src/O4_Version.py").write_text(
        "version = '1.1'\n", encoding="utf-8", newline="\n")
    r = _stamp("check", frozen, root)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == _git(root, "rev-parse", "HEAD")


def test_stale_stamp_refuses_with_both_shas(tmp_path):
    root, frozen = _repo(tmp_path)
    _stamp("write", frozen, root)
    old = _git(root, "rev-parse", "HEAD")
    (root / "Ortho4XP/src/code.py").write_text("x = 2\n", encoding="utf-8", newline="\n")
    _git(root, "commit", "-qam", "b")
    r = _stamp("check", frozen, root)
    assert r.returncode == 1
    assert f"frozen at {old}, source is {_git(root, 'rev-parse', 'HEAD')}" in r.stderr


def test_dirty_tree_matches_only_its_own_edits(tmp_path):
    root, frozen = _repo(tmp_path)
    (root / "Ortho4XP/src/code.py").write_text("x = 3\n", encoding="utf-8", newline="\n")
    _stamp("write", frozen, root)
    assert _stamp("check", frozen, root).returncode == 0
    (root / "Ortho4XP/src/code.py").write_text("x = 4\n", encoding="utf-8", newline="\n")
    r = _stamp("check", frozen, root)
    assert r.returncode == 1 and "-dirty(" in r.stderr


def test_build_scripts_wire_the_stamp():
    app = (REPO / "scripts/make_app.sh").read_text(encoding="utf-8")
    eng = (REPO / "scripts/make_engine.sh").read_text(encoding="utf-8")
    assert 'engine_stamp.sh" check "$FROZEN"' in app
    assert "embedded engine commit $EMBEDDED_SHA" in app
    assert 'engine_stamp.sh" write "$OUT"' in eng
