"""#2175 / RULINGS 2026-11-19e: a Build-tab tile goes into the World pack
while X-Plane runs; it waits staged only while X-Plane has one of its
files open, and the staged sweep swaps it in within seconds after.

Temp X-Plane, data root and pack only (``test_world_commands.world``);
X-Plane's open files are a stub."""
from __future__ import annotations

import json
import os
import time

import O4_World_Pack as WP
import O4_World_State_Text as TEXT
import pytest
from o4_engine import jsonl
from o4_engine import reload_offer as RELOAD
from o4_engine import world_commands as WORLD
from o4_engine import world_publish as PUBLISH
from o4_engine import world_staged_sweep as SWEEP
from o4_engine import xplane_open_files as XOPEN
from o4_engine.events import WorldTilesWaiting

from tests.test_world_commands import _build, world  # noqa: F401  (fixture)

HERE = os.path.dirname(os.path.abspath(__file__))
WIRE_FIXTURE = os.path.join(HERE, "fixtures", "world",
                            "world_tiles_waiting_event.json")


@pytest.fixture(autouse=True)
def _clean_sweep_state(monkeypatch):
    """The sweep's lists and the reload offer are the engine's: start and
    end each test empty; X-Plane runs and its Log.txt saw nothing."""
    SWEEP._WAITING.clear()
    SWEEP._RELOAD.clear()
    monkeypatch.setitem(RELOAD._STATE, "offer", "")
    monkeypatch.setattr(WORLD, "xplane_reads",
                        lambda _s: {"xplane_running": True, "loads": {}})
    yield
    SWEEP._WAITING.clear()
    SWEEP._RELOAD.clear()


def _open(monkeypatch, paths):
    """X-Plane holds ``paths()`` open (a callable: the tests change it)."""
    monkeypatch.setattr(XOPEN, "open_paths", lambda pids=None: set(paths()))


def _pack_dsf(world_dir, lat=45, lon=7):
    return os.path.realpath(os.path.join(WORLD.pack_dir(world_dir),
                                         WP.dsf_relpath(lat, lon)))


def _old_version(world_dir):
    """An earlier real version of +45+007 in the pack (so ``nothing_held``
    lets nothing through)."""
    old = os.path.join(WORLD.pack_dir(world_dir), "textures", "+45+007")
    os.makedirs(old)
    open(os.path.join(old, "old.dds"), "wb").close()


def test_loading_reads_the_tile_files_x_plane_holds_open(tmp_path):
    pack = str(tmp_path / "pack")
    textures = os.path.realpath(os.path.join(pack, "textures", "+45+007"))
    held = XOPEN.loading(pack, paths=lambda: {textures + "/a.dds"})
    assert held(45, 7) is True and held(45, 8) is False
    dsf = os.path.realpath(os.path.join(pack, WP.dsf_relpath(45, 8)))
    held = XOPEN.loading(pack, paths=lambda: {dsf})
    assert held(45, 8) is True and held(45, 7) is False
    assert XOPEN.open_paths(pids=[]) == set()


def test_a_build_goes_in_while_x_plane_runs(world, tmp_path, monkeypatch):  # noqa: F811
    """X-Plane runs and loaded the tile's area (rule S3 would keep it
    staged), but holds none of its files open: it goes in at once."""
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: True)
    _open(monkeypatch, lambda: {"/elsewhere/a.dds"})
    WORLD.world_install(world)
    _old_version(world)
    res = PUBLISH._publish_built(world, _build(tmp_path), 45, 7)
    assert res["state"] == "swapped"
    assert WP.holds_tile(world, 45, 7)
    assert SWEEP.waiting_tiles() == []


def test_a_tile_x_plane_is_loading_waits_then_the_sweep_puts_it_in(
        world, tmp_path, monkeypatch):  # noqa: F811
    holding = {"now": True}
    _open(monkeypatch, lambda: {_pack_dsf(world)} if holding["now"] else set())
    WORLD.world_install(world)
    _old_version(world)
    build = _build(tmp_path)
    res = PUBLISH._publish_built(world, build, 45, 7)
    assert res["state"] == "staged" and not WP.holds_tile(world, 45, 7)
    assert SWEEP.waiting_tiles() == [(45, 7)]
    emitted = []
    sweeper = SWEEP.Sweeper(emitted.append, lambda: world, lambda la, lo: build)
    # Still loading: it waits, and the apps hear so.
    assert sweeper.sweep_once()["swapped"] == []
    assert emitted == [WorldTilesWaiting(waiting=("+45+007",), reload=())]
    assert TEXT.waiting_note("+45+007", *(emitted[-1].waiting, ())) == (
        "+45+007 is waiting for X-Plane to finish loading it")
    # X-Plane closed its files: the next sweep swaps it and clears the note.
    holding["now"] = False
    assert sweeper.sweep_once()["swapped"] == ["+45+007"]
    assert WP.holds_tile(world, 45, 7)
    assert emitted[-1] == WorldTilesWaiting(waiting=(), reload=())
    log = open(os.path.join(os.path.dirname(WORLD.staging_root()), "logs",
                            WORLD.LOG_NAME), encoding="utf-8").read()
    assert '"swap_in": "+45+007", "from": "staged"' in log


def test_the_sweep_thread_swaps_when_x_plane_lets_go_and_ends(
        world, tmp_path, monkeypatch):  # noqa: F811
    """X-Plane closing the files (or quitting) is seen by the sweep's
    beat; its thread ends once nothing waits."""
    holding = {"now": True}
    _open(monkeypatch, lambda: {_pack_dsf(world)} if holding["now"] else set())
    WORLD.world_install(world)
    _old_version(world)
    build = _build(tmp_path)
    assert PUBLISH._publish_built(world, build, 45, 7)["state"] == "staged"
    emitted = []
    sweeper = SWEEP.Sweeper(emitted.append, lambda: world, lambda la, lo: build,
                            every_s=0.05)
    sweeper.poke()
    deadline = time.monotonic() + 10
    while not emitted and time.monotonic() < deadline:
        time.sleep(0.01)
    assert emitted and emitted[0].waiting == ("+45+007",)
    holding["now"] = False                      # X-Plane quit
    while sweeper._thread is not None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert sweeper._thread is None, "TIMED_OUT"
    assert WP.holds_tile(world, 45, 7)
    assert emitted[-1] == WorldTilesWaiting(waiting=(), reload=())


def test_the_engine_start_adopts_a_tile_left_staged(world, tmp_path, monkeypatch):  # noqa: F811
    """A tile an earlier run left staged (the owner's case) goes in at the
    next start; an unverified leftover stays."""
    _open(monkeypatch, set)
    WORLD.world_install(world)
    _old_version(world)
    build = _build(tmp_path)
    WP.publish(WORLD.pack_dir(world), build, 45, 7,
               staging_root=WORLD.staging_root(), loaded=lambda la, lo: True)
    broken = os.path.join(WORLD.staging_root(), "+45+008")
    os.makedirs(os.path.dirname(os.path.join(broken, WP.dsf_relpath(45, 8))))
    with open(os.path.join(broken, WP.dsf_relpath(45, 8)), "wb") as h:
        h.write(b"not a dsf")
    emitted = []
    sweeper = SWEEP.Sweeper(emitted.append, lambda: world, lambda la, lo: build,
                            every_s=0.05)
    sweeper.poke(leftovers=True)
    deadline = time.monotonic() + 10
    while not WP.holds_tile(world, 45, 7) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert WP.holds_tile(world, 45, 7), "TIMED_OUT"
    assert os.path.isdir(broken)


def test_a_swap_over_a_loaded_tile_offers_the_reload(world, tmp_path, monkeypatch):  # noqa: F811
    _open(monkeypatch, set)
    monkeypatch.setattr(WORLD, "xplane_reads", lambda _s: {
        "xplane_running": True, "loads": {(45, 7): object()}})
    WORLD.world_install(world)
    build = _build(tmp_path)
    assert PUBLISH._publish_built(world, build, 45, 7)["state"] == "swapped"
    assert RELOAD.current() == "tiles"
    emitted = []
    sweeper = SWEEP.Sweeper(emitted.append, lambda: world, lambda la, lo: build)
    sweeper.sweep_once()
    assert emitted == [WorldTilesWaiting(waiting=(), reload=("+45+007",))]
    assert TEXT.waiting_note("+45+007", (), ("+45+007",)).startswith(
        "+45+007 is in the World pack")
    # The user's "Reload scenery" clears the offer, and the note.
    monkeypatch.setitem(RELOAD._STATE, "offer", "")
    sweeper.sweep_once()
    assert emitted[-1] == WorldTilesWaiting(waiting=(), reload=())


def test_world_tiles_waiting_wire_fixture_is_what_python_emits():
    """The JSON the Swift twin (``WorldWireTests.swift``) decodes."""
    event = WorldTilesWaiting(waiting=("+41-088",), reload=("+45+007",))
    payload = json.loads(json.dumps(jsonl.serialize_event(event)))
    payload.pop("seq")
    payload.pop("ts")
    with open(WIRE_FIXTURE, encoding="utf-8") as h:
        assert json.load(h) == payload
