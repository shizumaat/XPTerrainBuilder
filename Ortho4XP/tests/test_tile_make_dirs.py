"""``Tile.make_dirs`` names the real reason it cannot use a tile dir.

A build dir that is a DANGLING SYMLINK — the link is there, its target
is not — used to fall into the ``os.makedirs`` branch, raise
``FileExistsError``, and be reported as "check file permissions".  Found
in the wild 2026-09-16: VHHH lived on an external volume that was not
mounted, and the message sent the user hunting permissions.

The failure still RAISES, so ``o4_engine.session``'s handler surfaces a
tile error exactly as before; only the sentence changes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Config_Utils as CFG  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402


class _Dir:
    """Just the make_dirs seam: the Tile constructor reads global config."""

    def __init__(self, build_dir):
        self.build_dir = build_dir

    make_dirs = CFG.Tile.make_dirs


@pytest.fixture
def said(monkeypatch):
    lines = []
    monkeypatch.setattr(
        UI, "vprint",
        lambda level, *parts: lines.append(
            " ".join(str(part) for part in parts)))
    return lines


def test_a_dangling_symlink_names_the_missing_target(tmp_path, said):
    target = tmp_path / "Volumes" / "Scenery" / "zOrtho4XP_+22+113"
    link = tmp_path / "zOrtho4XP_+22+113"
    os.symlink(str(target), str(link))
    assert os.path.islink(str(link)) and not os.path.exists(str(link))

    with pytest.raises(Exception):
        _Dir(str(link)).make_dirs()

    assert len(said) == 1
    message = said[0]
    assert "symlink whose target is missing" in message
    assert str(link) in message
    assert str(target) in message
    assert "(is the volume mounted?)" in message
    assert "permissions" not in message


def test_a_live_symlink_is_just_a_directory(tmp_path, said):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "zOrtho4XP_+22+113"
    os.symlink(str(target), str(link))
    _Dir(str(link)).make_dirs()
    assert said == []


def test_a_missing_directory_is_still_created(tmp_path, said):
    build_dir = tmp_path / "zOrtho4XP_+22+113"
    _Dir(str(build_dir)).make_dirs()
    assert build_dir.is_dir()
    assert said == []


def test_an_uncreatable_directory_reports_the_os_error(tmp_path, said):
    """The bare ``except`` swallowed the cause; the OSError is now quoted."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory")
    with pytest.raises(Exception):
        _Dir(str(blocker / "zOrtho4XP_+22+113")).make_dirs()
    assert len(said) == 1
    assert "Cannot create tile directory" in said[0]
    assert "Not a directory" in said[0] or "NotADirectoryError" in said[0]
