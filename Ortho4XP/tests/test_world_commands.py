"""Twins of the World pack in the engine (flight manager / World spec
§5.2, §7, §18; ``o4_engine.world_commands``, ``o4_engine.world_publish``):
install, status, regions -> placeholders (land tiles only), a region given
back, "Give this tile back", publish of a build (layout in the manifest,
index rows in the pack, the tile's own link removed), and the scanners of
spec §18 reading placeholders as no tile.  All on ``tmp_path``; X-Plane
reads as not running; nothing touches a real install."""
from __future__ import annotations

import json
import os
import shutil
import time
from unittest import mock

import O4_Custom_Scenery as CS
import O4_DSF_Binary as DSFB
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Regions as REGIONS
import O4_Mesh_Order as MO
import O4_Scenery_Links as LINKS
import O4_Settings_Model as SM
import O4_World_Pack as WP
import pytest
from o4_engine import jsonl
from o4_engine import world_commands as WORLD
from o4_engine import world_publish as PUBLISH
from o4_engine.events import WorldReady, WorldStatus

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE_DSF = os.path.join(HERE, "fixtures", "mesh_dsf", "full_ortho.dsf")
WIRE_FIXTURE = os.path.join(HERE, "fixtures", "world",
                            "world_status_event.json")
TER = ("A\n800\nTERRAIN\n\nLOAD_CENTER 45.5 7.5 5000 4096\n"
       "BASE_TEX_NOWRAP ../textures/23456_34112_BI16.dds\n")


def wire_sample() -> WorldStatus:
    """The event the shared wire fixture holds."""
    return WorldStatus(state="idle", reason="", installed=True,
                       seen_by_xplane=True, restart_needed=False,
                       tiles={"placeholder": 3, "drape": 1, "full": 2,
                              "staged": 1},
                       queue=2,
                       building=(("+53-065", "drape", "building", 41),),
                       jobs=([[53, -65], "ahead", "drape", "building"],
                             [[53, -64], "ahead", "drape", "swapped"]),
                       loaded=("+53-063",),
                       last_swap=("+53-064", "drape", "2026-11-10T15:02:24Z"),
                       slots=1, frame_ms=21.8, governor="ok", bytes=1234)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A tmp X-Plane (Custom Scenery + a Global Scenery with three land
    tiles), data root and global cfg; X-Plane not running."""
    xp = tmp_path / "X-Plane 12"
    scenery = xp / "Custom Scenery"
    scenery.mkdir(parents=True)
    land = xp / "Global Scenery" / "X-Plane 12 Global Scenery"
    for lat, lon in ((45, 7), (45, 8), (-34, 18)):
        dsf = land / WP.dsf_relpath(lat, lon)
        dsf.parent.mkdir(parents=True, exist_ok=True)
        dsf.write_bytes(b"XPLNEDSF")
    data = tmp_path / "data"
    monkeypatch.setattr(FNAMES, "data_path", lambda rel: str(data / rel))
    cfg = tmp_path / "XPTerrainBuilder.cfg"
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(cfg))
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: False)
    return str(scenery)


def _build(root, lat=45, lon=7, on_demand=True) -> str:
    tile = WP.tile_name(lat, lon)
    build = os.path.join(str(root), "Tiles", "zOrtho4XP_" + tile)
    dsf = os.path.join(build, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf))
    shutil.copyfile(FIXTURE_DSF, dsf)
    os.makedirs(os.path.join(build, "terrain"))
    os.makedirs(os.path.join(build, "textures"))
    for ref in DSFB.definitions(open(dsf, "rb").read())["TERT"]:
        if ref.startswith("terrain/"):
            with open(os.path.join(build, ref), "w", encoding="utf-8",
                      newline="\n") as h:
                h.write(TER)
    with open(os.path.join(build, "textures", "23456_34112_BI16.dds"),
              "wb") as h:
        h.write(b"DDS ")
    with open(os.path.join(build, f"Ortho4XP_{tile}_imagery.json"), "w",
              encoding="utf-8", newline="\n") as h:
        json.dump({"on_demand": on_demand}, h)
    return build


def test_install_status_and_regions(world):
    assert WORLD.world_status(world)["state"] == "off"
    done = WORLD.world_install(world)
    assert done["ini_added"] is True and done["restart_needed"] is False
    # World coverage (#2019): every land tile of the enabled regions (all,
    # by default) gets its placeholder at install; again: none.
    assert done["placeholders"] == 3
    again = WORLD.world_install(world)
    assert again["ini_added"] is False and again["placeholders"] == 0
    europe = REGIONS.region_of(45, 7)
    africa = REGIONS.region_of(-34, 18)
    order = [c for c, _ in REGIONS.REGIONS]
    res = WORLD._regions_set([europe, africa], world)
    # Only the tiles X-Plane's own scenery has (land) get a placeholder.
    assert res["written"] == 0 and res["kept"] == 3
    assert res["regions"] == sorted([europe, africa], key=order.index)
    status = WORLD.world_status(world)
    assert status["installed"] and status["tiles"]["placeholder"] == 3
    rows = {r["id"]: r for r in status["regions"]}
    assert rows[europe]["enabled"] and rows[europe]["placeholders"] == 2
    assert not rows[REGIONS.region_of(40, -100)]["enabled"]
    assert SM.read_global_raw()[REGIONS.setting_name(europe)] == "True"
    # Giving Africa back removes its placeholder; Europe's stay.
    res = WORLD._regions_set([europe], world)
    assert res["removed"] == 1 and res["written"] == 0 and res["kept"] == 2
    assert WORLD.world_status(world)["tiles"]["placeholder"] == 2
    with pytest.raises(ValueError):
        WORLD._regions_set(["atlantis"], world)


def test_world_coverage_places_land_tiles_only_and_never_over_a_real_tile(
        world, monkeypatch):
    """Owner 2026-11-12T15:05Z: "Yes add world coverage otherwise draping
    won't work" (#2019).  Regions on -> a placeholder for every LAND tile
    (X-Plane's Global Scenery list); ocean tiles none; a full or drape tile
    of ours untouched; idempotent; X-Plane running -> the "coverage"
    reload OFFER, nothing sent."""
    from o4_engine import reload_offer as RELOAD
    monkeypatch.setattr(RELOAD, "_STATE", {"offer": ""})
    monkeypatch.setattr(RELOAD, "send", lambda base=None: (
        _ for _ in ()).throw(AssertionError("reload without the user")))
    os.makedirs(os.path.join(WORLD.pack_dir(world), "Earth nav data"))
    with open(os.path.join(WORLD.pack_dir(world), WP.MARKER), "w",
              encoding="utf-8", newline="\n") as h:
        h.write("{}")
    pack = WORLD.pack_dir(world)
    real = os.path.join(pack, WP.dsf_relpath(45, 8))
    os.makedirs(os.path.dirname(real), exist_ok=True)
    shutil.copyfile(FIXTURE_DSF, real)              # a built tile of ours
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: True)
    done = WORLD.ensure_coverage(world)
    assert (done["written"], done["kept"]) == (2, 1)
    kinds = WP.world_tiles(pack)
    assert kinds[(45, 7)] == kinds[(-34, 18)] == "placeholder"
    assert kinds[(45, 8)] != "placeholder"          # never over a real tile
    assert (0, -30) not in kinds                    # ocean: none
    assert RELOAD.current() == "coverage"
    again = WORLD.ensure_coverage(world)
    assert (again["written"], again["kept"]) == (0, 3)
    # Without Global Scenery the start writes nothing; the user's region
    # choice falls back to the world mask.
    shutil.rmtree(os.path.join(os.path.dirname(world), "Global Scenery"))
    assert WORLD.ensure_coverage(world)["written"] == 0


def test_world_coverage_of_the_whole_world_takes_seconds(tmp_path):
    """The owner's ~20k land tiles: written in seconds (one listing, one
    folder each), again in well under one."""
    import O4_DEM_Utils as DEM
    tiles = [t for code, _ in REGIONS.REGIONS if code != "antarctica"
             for t in REGIONS.region_tiles(code) if DEM.tile_is_land(*t)]
    assert len(tiles) > 15_000
    pack = str(tmp_path / "pack")
    t0 = time.monotonic()
    assert WP.write_placeholders(pack, tiles)["written"] == len(tiles)
    first = time.monotonic() - t0
    t1 = time.monotonic()
    assert WP.write_placeholders(pack, tiles)["kept"] == len(tiles)
    # a bound for a loaded CI runner (5 s alone on the owner's Mac; 51 s seen
    # beside four builds): the twin guards against a per-tile O(n) listing
    assert first < 120.0 and time.monotonic() - t1 < 20.0


def test_publish_a_build_and_give_it_back(world, tmp_path):
    WORLD.world_install(world)
    WORLD._regions_set([REGIONS.region_of(45, 7)], world)
    build = _build(tmp_path)
    LINKS.install(45, 7, build, world)              # the app's auto-install
    assert os.path.islink(os.path.join(world, "zOrtho4XP_+45+007"))
    res = PUBLISH._publish_built(world, build, 45, 7,
                                loaded=lambda la, lo: False)
    assert res["state"] == "swapped" and not res["problems"]
    pack = WORLD.pack_dir(world)
    assert WP.world_tiles(pack)[(45, 7)] == "full"
    # The World pack draws the tile now: the link is gone and not re-made.
    assert not os.path.lexists(os.path.join(world, "zOrtho4XP_+45+007"))
    LINKS.install(45, 7, build, world)
    assert not os.path.lexists(os.path.join(world, "zOrtho4XP_+45+007"))
    # The manifest names the pack's folders; the index reads through them.
    with open(os.path.join(build, "Ortho4XP_+45+007_imagery.json"),
              encoding="utf-8") as h:
        layout = json.load(h)[INDEX.LAYOUT_KEY]
    assert layout["textures_dir"] == os.path.join(pack, "textures", "+45+007")
    row = {"build_dir": build, "name": "a.dds", **layout}
    assert INDEX.texture_path(row) == os.path.join(layout["textures_dir"],
                                                   "a.dds")
    assert INDEX._tile_dir({"build_dir": build}, "terrain") == os.path.join(
        build, "terrain")
    assert INDEX._tile_dir({"build_dir": build}, "config") == build
    # Status: one full tile; the engine scan sees it installed.
    status = WORLD.world_status(world)
    assert status["tiles"]["full"] == 1 and status["tiles"]["placeholder"] == 1
    assert (45, 7) in LINKS.installed_tiles(world)
    # "Give this tile back".
    back = WORLD.world_tile_set(45, 7, scenery_dir=world)
    assert back["folders_removed"] is True
    assert WP.world_tiles(pack)[(45, 7)] == "placeholder"
    assert (45, 7) not in LINKS.installed_tiles(world)
    with pytest.raises(ValueError):
        WORLD.world_tile_set(45, 7, kind="full", scenery_dir=world)


def test_no_pack_publishes_nothing_every_build_publishes(world, tmp_path):
    build = _build(tmp_path)
    assert PUBLISH._publish_built(world, build, 45, 7) is None
    # A pack of that name the app did not make (the CYYR kit's): untouched.
    os.makedirs(os.path.join(WORLD.pack_dir(world), "Earth nav data"))
    assert PUBLISH._publish_built(world, build, 45, 7) is None
    assert WORLD.world_status(world)["installed"] is False
    WORLD.world_install(world)
    assert WORLD.managed(world)
    # RULINGS 2026-11-12g: every build goes into the World folder, imagery
    # on demand or not.
    other = _build(tmp_path / "b", on_demand=False)
    res = PUBLISH._publish_built(world, other, 45, 7,
                                 loaded=lambda la, lo: False)
    assert res is not None and res["state"] == "swapped", res


def test_a_held_tile_waits_staged(world, tmp_path):
    WORLD.world_install(world)
    build = _build(tmp_path)
    # an earlier version's name in the pack (S4/S5: X-Plane may map it);
    # with none the tile goes in at once (#2032, below)
    old = os.path.join(WORLD.pack_dir(world), "textures", "+45+007")
    os.makedirs(old)
    open(os.path.join(old, "old.dds"), "wb").close()
    res = PUBLISH._publish_built(world, build, 45, 7,
                                loaded=lambda la, lo: True)
    assert res["state"] == "staged"
    assert not WP.holds_tile(world, 45, 7)
    assert PUBLISH._swap_waiting(world, lambda la, lo: build,
                                loaded=lambda la, lo: False) == ["+45+007"]
    assert WP.holds_tile(world, 45, 7)


def test_2032_a_held_tile_the_pack_names_nothing_of_goes_in(world, tmp_path):
    WORLD.world_install(world)
    build = _build(tmp_path)
    res = PUBLISH._publish_built(world, build, 45, 7,
                                loaded=lambda la, lo: True)
    assert res["state"] == "swapped" and WP.holds_tile(world, 45, 7)


def test_scanners_read_placeholders_as_no_tile(world, tmp_path):
    """Spec §18 seam: before W1 the World pack read as a landmark pack
    covering every placeholder, and its real tiles as not installed."""
    WORLD.world_install(world)
    WORLD._regions_set([REGIONS.region_of(45, 7)], world)
    build = _build(tmp_path)
    for i in range(30):
        with open(os.path.join(build, "textures", f"{i}_x_BI16.dds"),
                  "wb") as h:
            h.write(b"DDS ")
    PUBLISH._publish_built(world, build, 45, 7, loaded=lambda la, lo: False)
    # Ours, so never "other scenery" (lane ltilepane, owner
    # 2026-11-12T20:23Z); its own listing still reads placeholders as no tile.
    assert WP.PACK_NAME not in {p.name for p in CS.scan_packs(world)}
    assert CS.pack_tiles(WORLD.pack_dir(world)) == {(45, 7)}  # (45, 8): a placeholder
    assert MO.tile_mesh_order(world, 45, 7, build_dir=build)["checked"] is True
    assert MO.drawn_mesh_dsf(world, 45, 8) is None   # a placeholder: no mesh
    assert sorted(LINKS.installed_tiles(world)) == [(45, 7)]


def test_regions_set_command_completes_with_world_ready(world):
    WORLD.world_install(world)
    got = []
    reply = WORLD.start_world_regions_set(got.append, request=7,
                                          regions=["nowhere"],
                                          scenery_dir=world)
    assert reply == {"status": "started"}
    deadline = time.monotonic() + 10
    while not got and time.monotonic() < deadline:
        time.sleep(0.01)
    assert isinstance(got[0], WorldReady) and got[0].request == 7
    assert "unknown regions" in got[0].error
    # The transport hands the command's id to it as ``request``.
    assert "world_regions_set" in jsonl._TAKES_REQUEST_ID
    assert {"world_status", "world_install", "world_regions_set",
            "world_tile_set"} <= set(jsonl.command_table(mock.MagicMock()))


def test_world_status_wire_fixture_is_what_python_emits():
    """The JSON the Swift twin (``WorldWireTests.swift``) decodes is the
    serialized event, field for field."""
    payload = json.loads(json.dumps(jsonl.serialize_event(wire_sample())))
    payload.pop("seq")
    payload.pop("ts")
    with open(WIRE_FIXTURE, encoding="utf-8") as h:
        assert json.load(h) == payload


def test_s3_while_xplane_runs(world, monkeypatch):
    """S3: with X-Plane running a tile is held when the witness saw it
    load, when the aircraft has it in (or within the margin of) the DSF
    window, or when no position is known."""
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: True)
    monkeypatch.setattr(WORLD, "_witness", lambda _s: ({(50, 0): None}, []))
    assert WORLD.tile_loaded(world, position=lambda: None)(10, 10) is True
    held = WORLD.tile_loaded(world, position=lambda: (53.3, -60.4))
    assert held(50, 0) is True                  # the witness saw it load
    assert held(53, -61) is True                # under the aircraft
    assert held(53, -66) is False               # far west, outside
    # +53-062 enters at lon -60.35 (0.65° past its column): 5 km out.
    near = WORLD.tile_loaded(world, position=lambda: (53.3, -60.30))
    assert near(53, -63) is False and near(53, -62) is True


def test_watch_holds_no_thread_until_a_tile_is_built():
    """``watch`` starts its worker with the first job: a session (a test
    window) that never builds leaks no thread (#2004 CI: 98 idle workers
    at the Qt suite's segfault)."""
    import threading

    class Session:
        def subscribe(self, fn):
            pass
    before = sum(t.name == "o4-world-publish" for t in threading.enumerate())
    for _ in range(3):
        PUBLISH.watch(Session(), scenery_dir=lambda: "/nowhere")
    after = sum(t.name == "o4-world-publish" for t in threading.enumerate())
    assert after == before


def test_watch_publishes_a_built_tile_on_its_worker(world, tmp_path):
    """``watch``: a ``BuildDone`` ok of an on-demand tile is published and
    a ``WorldStatus`` follows; the configured folder is read at the event."""
    from o4_engine.events import BuildDone
    WORLD.world_install(world)
    build = _build(tmp_path)
    emitted, handlers = [], []

    class Session:
        _stepwise_run = False

        def tile_build_dir(self, lat, lon):
            return build

        def subscribe(self, fn):
            handlers.append(fn)

        def _emit(self, event):
            emitted.append(event)
    PUBLISH.watch(Session(), scenery_dir=lambda: world)
    handlers[0](BuildDone(lat=45, lon=7, ok=True))
    deadline = time.monotonic() + 20
    while not emitted and time.monotonic() < deadline:
        time.sleep(0.02)
    assert emitted and emitted[0].tiles["full"] == 1
    assert emitted[0].last_swap[0] == "+45+007"
