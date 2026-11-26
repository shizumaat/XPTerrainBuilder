"""#2226: a built tile that does not go into the World pack is never
silent -- the engine publishes it once more, and one still refused is
noted in the user's words (``world_publish_failed``) and carried to both
apps by ``WorldTilesWaiting.failed`` until its next publish succeeds.

Temp X-Plane, data root and pack only (``test_world_commands.world``)."""
from __future__ import annotations

import errno
import os

import O4_Tile_Failures as FAIL
import O4_World_Pack as WP
import pytest
from o4_engine import world_commands as WORLD
from o4_engine import world_publish as PUBLISH
from o4_engine import world_publish_failed as FAILED
from o4_engine import world_staged_sweep as SWEEP
from o4_engine import xplane_open_files as XOPEN
from tests.test_world_commands import _build, world  # noqa: F401  (fixture)

TEXTURE = os.path.join("textures", "23456_34112_BI16.dds")


@pytest.fixture(autouse=True)
def _nothing_open(monkeypatch):
    SWEEP._WAITING.clear()
    monkeypatch.setattr(XOPEN, "open_paths", lambda pids=None: set())
    monkeypatch.setattr(WORLD, "xplane_reads",
                        lambda _s: {"xplane_running": False, "loads": {}})
    yield
    SWEEP._WAITING.clear()


def _broken_build(tmp_path):
    """A build whose terrain names a texture that is not there: the
    publish's verify refuses it."""
    build = _build(tmp_path)
    os.remove(os.path.join(build, TEXTURE))
    return build


def test_a_tile_refused_twice_is_noted_and_reaches_the_wire(world, tmp_path):  # noqa: F811
    WORLD.world_install(world)
    build = _broken_build(tmp_path)
    res = PUBLISH._publish_or_note(world, build, 45, 7, retry_after_s=0)
    assert res["state"] == "failed" and res["where"] == "verify"
    (entry,) = FAILED.entries()
    assert entry["code"] == "world_publish_failed"
    assert entry["tile"] == "+45+007" and entry["severity"] == "degraded"
    assert entry["what"] == ("Tile +45+007 was built, but it did not go into "
                             "X-Plane: the World pack kept its previous "
                             "version of the tile.")
    assert entry["why"].startswith("Files its scenery names were missing")
    assert entry["remedy"].startswith("Build the tile again.")
    assert "BI16.dds" in entry["detail"]
    log = open(os.path.join(os.path.dirname(WORLD.staging_root()), "logs",
                            WORLD.LOG_NAME), encoding="utf-8").read()
    assert '"publish_retry": "+45+007"' in log
    # The staged sweep carries it to the apps, even with nothing waiting.
    emitted = []
    sweeper = SWEEP.Sweeper(emitted.append, lambda: world, lambda la, lo: build)
    sweeper.sweep_once()
    assert emitted[-1].failed == (entry,)
    # The next publish that goes in clears it, and the apps hear so.
    with open(os.path.join(build, TEXTURE), "wb") as handle:
        handle.write(b"DDS ")
    assert PUBLISH._publish_or_note(world, build, 45, 7)["state"] == "swapped"
    assert FAILED.entries() == ()
    sweeper.sweep_once()
    assert emitted[-1].failed == ()


def test_the_retry_recovers_a_texture_still_being_written(
        world, tmp_path, monkeypatch):  # noqa: F811
    """The automatic second publish: the texture another writer was
    finishing is there now, so the tile goes in and nothing is noted."""
    WORLD.world_install(world)
    build = _broken_build(tmp_path)

    def finish_the_texture(_seconds):
        with open(os.path.join(build, TEXTURE), "wb") as handle:
            handle.write(b"DDS ")
    monkeypatch.setattr("time.sleep", finish_the_texture)
    assert PUBLISH._publish_or_note(world, build, 45, 7)["state"] == "swapped"
    assert WP.holds_tile(world, 45, 7)
    assert FAILED.entries() == ()


def test_a_full_disk_says_free_space(world):  # noqa: F811
    entry = FAILED.note("+45+007", "error",
                        error=OSError(errno.ENOSPC, "No space left on device"))
    assert entry["code"] == "world_publish_no_space"
    assert entry["remedy"] == FAIL.REMEDIES["disk"]
    assert FAILED.note("+45+007", "stage", problems=["[Errno 28] full"],
                       errnum=errno.ENOSPC)["code"] == "world_publish_no_space"
    # one entry per tile, kept on disk until cleared
    assert [e["tile"] for e in FAILED.entries()] == ["+45+007"]
    assert FAILED.clear("+45+007") is True
    assert FAILED.clear("+45+007") is False


def test_a_swap_the_sweep_is_refused_is_noted(world, tmp_path, monkeypatch):  # noqa: F811
    WORLD.world_install(world)
    build = _build(tmp_path)

    def refuse(pack, staging_root, held, only=None, refused=None):
        refused.append(WP.IncompleteTile("+45+007", "staged",
                                         ["terrain/+45+007/a.ter"]))
        return []
    monkeypatch.setattr(WP, "swap_staged", refuse)
    assert PUBLISH._swap_waiting(world, lambda la, lo: build) == []
    (entry,) = FAILED.entries()
    assert entry["tile"] == "+45+007" and "a.ter" in entry["detail"]
    assert entry["why"].startswith("Files its scenery names were missing "
                                   "from the copy")
