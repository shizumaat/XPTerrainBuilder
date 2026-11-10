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
                       tiles={"placeholder": 3, "drape": 0, "light": 1,
                              "full": 2, "staged": 1},
                       queue=2, building=(), loaded=("+53-063",),
                       last_swap=("+53-064", "light", "2026-11-10T15:02:24Z"),
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
    assert WORLD.world_install(world)["ini_added"] is False
    europe = REGIONS.region_of(45, 7)
    africa = REGIONS.region_of(-34, 18)
    order = [c for c, _ in REGIONS.REGIONS]
    res = WORLD._regions_set([europe, africa], world)
    # Only the tiles X-Plane's own scenery has (land) get a placeholder.
    assert res["written"] == 3
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


def test_no_pack_or_not_on_demand_publishes_nothing(world, tmp_path):
    build = _build(tmp_path)
    assert PUBLISH._publish_built(world, build, 45, 7) is None
    WORLD.world_install(world)
    other = _build(tmp_path / "b", on_demand=False)
    assert PUBLISH._publish_built(world, other, 45, 7) is None


def test_a_held_tile_waits_staged(world, tmp_path):
    WORLD.world_install(world)
    build = _build(tmp_path)
    res = PUBLISH._publish_built(world, build, 45, 7,
                                loaded=lambda la, lo: True)
    assert res["state"] == "staged"
    assert not WP.holds_tile(world, 45, 7)
    assert PUBLISH._swap_waiting(world, lambda la, lo: build,
                                loaded=lambda la, lo: False) == ["+45+007"]
    assert WP.holds_tile(world, 45, 7)


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
    pack = {p.name: p for p in CS.scan_packs(world)}[WP.PACK_NAME]
    assert pack.tiles == frozenset({(45, 7)})       # (45, 8): a placeholder
    assert pack.kind == "ortho"
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


def test_world_status_wire_fixture_is_what_python_emits():
    """The JSON the Swift twin (``WorldWireTests.swift``) decodes is the
    serialized event, field for field."""
    payload = json.loads(json.dumps(jsonl.serialize_event(wire_sample())))
    payload.pop("seq")
    payload.pop("ts")
    with open(WIRE_FIXTURE, encoding="utf-8") as h:
        assert json.load(h) == payload
