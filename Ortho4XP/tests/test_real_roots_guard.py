"""Twins of the real-roots audit guard (``tests/real_roots_guard.py``):
the events it reads, the roots and exemptions it applies, and that it is
ARMED in this run -- a probe aimed at the real install is refused before
it runs (each probe would fail harmlessly anyway: its folder does not
exist, so an unarmed guard writes nothing)."""
import _io
import os
import posix
import sqlite3

import pytest
from conftest import xplane_root

import O4_File_Names as FNAMES
from tests import real_roots_guard as GUARD


def test_the_events_it_reads():
    assert GUARD.write_targets("open", ("/a/b", "rb", 0)) == ()
    assert GUARD.write_targets("open", ("/a/b", "a", 0)) == ("/a/b",)
    assert GUARD.write_targets("open", ("/a/b", None, os.O_RDONLY)) == ()
    assert GUARD.write_targets("open", ("/a/b", None, os.O_CREAT)) == ("/a/b",)
    assert GUARD.write_targets("open", (7, "w", 0)) == ()          # an fd
    assert GUARD.write_targets("os.rename", ("/a", "/b", None, None)) == \
        ("/a", "/b")
    assert GUARD.write_targets("os.symlink", ("/t", "/l", None)) == ("/l",)
    assert GUARD.write_targets("shutil.rmtree", (b"/x", None)) == ("/x",)
    assert GUARD.write_targets("os.rmdir", ("logs", 5)) == ()     # of a dir_fd
    assert GUARD.write_targets("sqlite3.connect", (":memory:",)) == ()
    assert GUARD.write_targets("os.listdir", ("/a",)) == ()


def test_roots_exemptions_links_and_lock_churn(tmp_path):
    real = tmp_path / "XP"
    (real / "Custom Scenery").mkdir(parents=True)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    roots, exempt = [str(real)], [str(scratch)]
    inside = str(real / "Custom Scenery" / "scenery_packs.ini")
    assert GUARD.violation([inside], roots, exempt) == os.path.realpath(inside)
    assert GUARD.violation([str(scratch / "x")], roots, exempt) is None
    assert GUARD.violation([inside + ".lock"], roots, exempt) is None
    # writing THROUGH a link into the root, and removing a link IN it
    os.symlink(real / "Custom Scenery", scratch / "via")
    assert GUARD.violation([str(scratch / "via" / "f")], roots, []) is not None
    os.symlink(scratch, real / "Custom Scenery" / "zOrtho4XP_+45+007")
    assert GUARD.violation([str(real / "Custom Scenery" / "zOrtho4XP_+45+007")],
                           roots, exempt) is not None


def test_the_guard_is_armed_on_the_real_install():
    assert GUARD.state["armed"]
    probe = os.path.join(xplane_root(), "__o4_guard_probe__", "x")
    try:
        with pytest.raises(GUARD.RealRootWrite):
            _io.open(probe, "w")                      # past any monkeypatch
        with pytest.raises(GUARD.RealRootWrite):
            posix.remove(probe)
        with pytest.raises(GUARD.RealRootWrite):
            sqlite3.connect(probe)
        assert {b["via"] for b in GUARD.blocked} == {
            "open", "os.remove", "sqlite3.connect"}
    finally:
        del GUARD.blocked[:]                          # expected refusals


def test_data_root_logs_resolve_under_the_run_tmp_tree(tmp_path_factory):
    base = os.path.realpath(str(tmp_path_factory.getbasetemp()))
    assert os.path.realpath(FNAMES.data_path("logs")).startswith(base + os.sep)
