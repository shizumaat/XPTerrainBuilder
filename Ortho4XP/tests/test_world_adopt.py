"""Twins for ADOPTING the tiles another tool built in Convert existing
tiles (``o4_engine.world_adopt``, ``tile_bundle.adopted``; owner
2026-11-12T14:19Z), offline on ``test_world_migrate``'s synthetic X-Plane
folder in ``tmp_path`` (never the real install or a real drive):

* a kept tile another tool built is adopted: its DSF in the World pack,
  its on-demand copy stamped, its adopted package written, its journal
  ``adopted``, its index rows written; a tile's own folder is never
  written;
* a tile an earlier run made dynamic (chosen again: link removed) is
  adopted again by the next Convert run under a choice that keeps it --
  the dry run counts it -- and Undo makes its link again;
* the adopted package round-trips: laid out it gives back the DSF,
  terrain and masks, placeholders from where they are kept, and it
  installs into the World pack;
* the cores come from the enabled custom airport packs, and the budget
  makes them low-res last;
* the cores are landed from the tile's own imagery only, within the
  budget's room;
* the disk guard: nothing is written below the reserve;
* the lander: a combined provider (EUR) lands its tier from the tile's
  own layers without touching the module's dict; a tile whose ``.ter``
  files name mask PNGs is never imprinted, and its own tool's cfg is
  read for its masks and imagery.
"""
from __future__ import annotations

import os
import textwrap
import types

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Tile_Info as TINFO
import O4_World_Pack as WP
import pytest
from o4_engine import imagery_follow_land as LAND
from o4_engine import world_adopt as ADOPT
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_migrate_size as SIZE
from o4_engine import world_rechoose as RECHOOSE
from o4_engine import world_retire as RETIRE
from test_world_migrate import TEX, _hashes, _rows, xp  # noqa: F401
from tile_bundle import adopted as ADOPTED
from tile_bundle import install as INSTALL

LINK, LOCAL = "zOrtho4XP_+45+007", "zOrtho4XP_+46+008"


def _blank_dds(width: int) -> bytes:
    count = DDS.full_mip_count(width, width)
    return DDS.assemble(width, width, "bc1", [
        bytes(DDS.level_size(w, h, "bc1"))
        for (w, h) in DDS.mip_dims(width, width, count)])


def test_convert_adopts_the_kept_tiles_another_tool_built(xp):  # noqa: F811
    scenery = xp["scenery"]
    library = _hashes(xp["library"])
    out = MIGRATE.migrate(scenery, index=xp["index"])
    assert out["adopted"] == 2 and out["counts"]["migrated"] == 2
    assert "2 built by another tool, adopted" in MIGRATE.summary("migrate", out)
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "full", (46, 8): "full"}
    journal = MIGRATE.Journal(xp["work"])
    link, local = journal.get(LINK), journal.get(LOCAL)
    assert link["adopted"] and local["adopted"]
    assert os.path.isfile(link["package"]) and os.path.isfile(local["package"])
    assert link["package"].endswith("+45+007" + ADOPT.PACKAGE_SUFFIX)
    # the on-demand copy is ours (stamped); the tile's own folder is not
    assert TINFO.origin_of(link["config_dir"], 45, 7) == TINFO.ORIGIN_ADOPTED
    assert not TINFO.adopted_record(local["config_dir"])
    assert _hashes(xp["library"]) == library              # never touched
    conn = INDEX.open_index(xp["index"])
    try:
        assert INDEX.rows(conn, tile="+45+007")
    finally:
        conn.close()


def test_the_disk_guard_writes_nothing_below_the_reserve(xp, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ADOPT, "room_left", lambda path: 0)
    out = MIGRATE.migrate(xp["scenery"], index=xp["index"])
    assert {r["status"] for r in out["rows"]} == {
        "skip: not enough free disk space"}
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "placeholder"}
    assert MIGRATE.Journal(xp["work"]).records == {}


def test_convert_again_adopts_the_tiles_made_dynamic(xp, monkeypatch):  # noqa: F811
    scenery = xp["scenery"]
    real = ADOPT.foreign
    monkeypatch.setattr(ADOPT, "foreign", lambda *a: False)   # the 11-11 run
    MIGRATE.migrate(scenery, index=xp["index"])
    RECHOOSE.rechoose(scenery, [LINK], index=xp["index"])
    record = MIGRATE.Journal(xp["work"]).get(LINK)
    assert record["state"] == "dynamic" and record["rechosen"]
    assert not os.path.lexists(os.path.join(scenery, LINK))
    monkeypatch.setattr(ADOPT, "foreign", real)
    # the dry run counts it under the choices that keep it
    dry = SIZE.dry_run(scenery, sample=0)
    again = {c["id"]: c["again"] for c in dry["choices"]}
    assert again == {RETIRE.KEEP_ALL: 1, RETIRE.KEEP_CUSTOM: 0,
                     RETIRE.DYNAMIC: 0}
    keep_all = next(c for c in dry["choices"] if c["id"] == RETIRE.KEEP_ALL)
    assert "adopted" in keep_all["line"]
    assert "can be adopted again" in MIGRATE.summary("dry_run", dry)
    # a choice that does not keep it leaves it dynamic
    MIGRATE.migrate(scenery, index=xp["index"], choice=RETIRE.DYNAMIC)
    assert MIGRATE.Journal(xp["work"]).get(LINK)["state"] == "dynamic"
    out = MIGRATE.migrate(scenery, index=xp["index"])
    row = next(r for r in out["rows"] if r["name"] == LINK)
    assert row["status"] == "migrated" and row["adopted"]
    record = MIGRATE.Journal(xp["work"]).get(LINK)
    assert record["state"] == "done" and record["adopted"]
    assert not record["rechosen"]
    assert WP.world_tiles(xp["pack"])[(45, 7)] == "full"
    assert not WP.verify_tile(xp["pack"], 45, 7)["problems"]
    assert not os.path.lexists(os.path.join(scenery, LINK))   # no link again
    # Undo makes the link again and turns its row on
    back = MIGRATE.revert(scenery, index=xp["index"])
    assert LINK in back["reverted"]
    assert os.path.islink(os.path.join(scenery, LINK))
    assert _rows(scenery)[LINK] == "SCENERY_PACK"


def test_the_adopted_package_round_trips_and_installs(xp, tmp_path):  # noqa: F811
    scenery = xp["scenery"]
    MIGRATE.migrate(scenery, [LINK], index=xp["index"])
    record = MIGRATE.Journal(xp["work"]).get(LINK)
    path, lean = record["package"], record["config_dir"]
    shown = INSTALL.plan(path)
    assert shown["kind"] == "adopted" and shown["personal"] and shown["warning"]
    out = str(tmp_path / "restored")
    laid = ADOPTED.lay_out(path, out)
    assert laid["missing"] == [TEX + ".dds"]                 # no imagery
    for rel in ("terrain/%s.ter" % TEX, "textures/water_transition.png",
                "Ortho4XP_+45+007.cfg"):
        assert _hashes(out)[rel] == _hashes(lean)[rel]
    source_dsf = os.path.join(xp["library"], LINK, WP.dsf_relpath(45, 7))
    with open(source_dsf, "rb") as a, open(laid["dsf"], "rb") as b:
        assert a.read() == b.read()
    again = ADOPTED.lay_out(path, out, placeholder=lambda name: os.path.join(
        lean, "textures", name))
    assert again["missing"] == []
    # the World pack lost the tile; the package puts it back
    MIGRATE._give_back(xp["pack"], 45, 7, "placeholder")
    assert WP.world_tiles(xp["pack"])[(45, 7)] == "placeholder"
    done = ADOPT.install_package(path, scenery)
    assert done["tile"] == "+45+007" and done["missing"] == []
    assert WP.world_tiles(xp["pack"])[(45, 7)] == "full"
    assert not WP.verify_tile(xp["pack"], 45, 7)["problems"]
    assert MIGRATE.Journal(xp["work"]).get(LINK)["adopted"]


def test_a_damaged_adopted_package_is_refused(xp, tmp_path):  # noqa: F811
    from tile_bundle import BundleRefused
    MIGRATE.migrate(xp["scenery"], [LINK], index=xp["index"])
    path = MIGRATE.Journal(xp["work"]).get(LINK)["package"]
    with open(path, "r+b") as handle:
        handle.seek(os.path.getsize(path) // 2)
        handle.write(b"\0" * 64)
    with pytest.raises(BundleRefused):
        ADOPTED.lay_out(path, str(tmp_path / "out"))


APT_DAT = textwrap.dedent("""\
    I
    1100 Version
    1 25 0 0 ZZZZ Somewhere
    1302 icao_code ZZZZ
    1302 datum_lat 45.5
    1302 datum_lon 7.5
    """)


def _airport_pack(scenery, name: str = "Some Airport") -> None:
    nav = os.path.join(scenery, name, "Earth nav data")
    os.makedirs(nav)
    with open(os.path.join(nav, "apt.dat"), "w", encoding="utf-8",
              newline="\n") as handle:
        handle.write(APT_DAT)


def _row(name: str, lat: float, lon: float, **more) -> dict:
    return {"tile": "+45+007", "name": name, "zl": 16, "provider": "BI",
            "centre_lat": lat, "centre_lon": lon, "load_size_m": 2400.0,
            **more}


def test_cores_come_from_the_enabled_custom_airport_packs(tmp_path):
    scenery = str(tmp_path / "Custom Scenery")
    _airport_pack(scenery)
    assert CORES.custom_points(45, 7, scenery) == [("ZZZZ", 45.5, 7.5)]
    points = CORES.airport_points(45, 7, patch_dir=str(tmp_path / "none"),
                                  scenery_dir=scenery)
    rows = [_row("near", 45.5, 7.5), _row("far", 45.95, 7.95)]
    assert CORES.core_names(rows, points) == {"near"}
    with open(os.path.join(scenery, "scenery_packs.ini"), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write("I\n1000 Version\nSCENERY\n\n"
                     "SCENERY_PACK_DISABLED Custom Scenery/Some Airport/\n")
    assert CORES.custom_points(45, 7, scenery) == []


def test_the_budget_makes_custom_airport_cores_low_res_last(tmp_path):
    scenery = str(tmp_path / "Custom Scenery")
    _airport_pack(scenery)
    conn = INDEX.open_index(str(tmp_path / "index.sqlite"))
    try:
        for name, lat, lon in (("near", 45.5, 7.5), ("far", 45.95, 7.95)):
            INDEX.upsert(conn, _row(name, lat, lon, state="upgraded",
                                    tier_px=4096, full_bytes=1000,
                                    build_dir=str(tmp_path)))
        points = CORES.custom_points(45, 7, scenery)
        INDEX.set_core(conn, "+45+007", CORES.core_names(
            INDEX.rows(conn, tile="+45+007"), points))
        order = [r["name"] for r in INDEX.lru_order(conn, favorites=True)]
    finally:
        conn.close()
    assert order == ["far", "near"]


def test_keep_cores_lands_from_the_tile_and_stops_at_the_room(xp, monkeypatch):  # noqa: F811
    MIGRATE.migrate(xp["scenery"], [LINK], index=xp["index"])
    lean = MIGRATE.Journal(xp["work"]).get(LINK)["config_dir"]
    monkeypatch.setattr(CORES, "airport_points",
                        lambda lat, lon: [("ZZZZ", 45.5, 7.5)])
    monkeypatch.setattr(ADOPT, "room_left", lambda path: 10**13)
    calls = []

    def lander(row, tier):
        calls.append((row["name"], tier))
        return {"tier_px": 4096, "full_bytes": 1000, "network": False}
    out = ADOPT.keep_cores([(lean, 45, 7)], index=xp["index"],
                           lander=lander, room=0)
    assert out["no_room"] == 1 and out["landed"] == 0 and calls == []
    out = ADOPT.keep_cores([(lean, 45, 7)], index=xp["index"],
                           lander=lander, room=10**9)
    assert out["landed"] == 1 and out["bytes"] == 1000
    assert calls == [(TEX + ".dds", 3)]
    with pytest.raises(RuntimeError, match="source is not here"):
        LAND.TierLander(source_only=True)(
            {"name": TEX + ".dds", "build_dir": lean, "tile": "+45+007",
             "source_path": None}, 1)


def test_a_combined_provider_lands_from_the_tiles_own_layers(tmp_path, monkeypatch):
    import O4_Imagery_Utils as IMG
    build, pack = tmp_path / "lean", tmp_path / "pack"
    (build / "textures").mkdir(parents=True)
    pack.mkdir()
    name = "23456_34112_EUR16.dds"
    layer = {"layer_code": "BI", "extent_code": "World", "priority": "low"}
    monkeypatch.setitem(IMG.combined_providers_dict, "EUR", [layer])
    monkeypatch.setattr(IMG, "local_combined_providers_dict", {})
    asked = []

    def layers(tile, only=None):
        asked.append(only)
        return {"EUR": [layer]}

    def fetch(tile, *attrs, drop=None):
        assert IMG.local_combined_providers_dict["EUR"] == [layer]
        assert drop is None                     # the full composite
        return 1

    def convert(tile, *attrs, drop=None):
        assert drop == 0
        with open(build / "textures" / name, "wb") as handle:
            handle.write(_blank_dds(TIERS.FULL_WIDTH))
    monkeypatch.setattr(IMG, "initialize_local_combined_providers_dict",
                        layers)
    monkeypatch.setattr(IMG, "build_jpeg_ortho", fetch)
    monkeypatch.setattr(IMG, "convert_texture", convert)
    lander = LAND.TierLander()
    lander._tiles[str(build)] = types.SimpleNamespace(
        build_dir=str(build), lat=45, lon=7)
    row = {"tile": "+45+007", "name": name, "zl": 16, "provider": "EUR",
           "build_dir": str(build), "textures_dir": str(pack)}
    facts = lander(row, 1)
    assert facts["tier_px"] == 1024 and facts["network"]
    assert TIERS.texture_header(str(pack / name))[0] == 1024
    assert asked == [["EUR"]]
    assert "EUR" not in IMG.local_combined_providers_dict   # left as it was
    assert lander(row, 3)["tier_px"] == TIERS.FULL_WIDTH
    assert asked == [["EUR"]]                               # read once


def test_a_tile_whose_terrain_names_mask_pngs_is_never_imprinted(tmp_path, monkeypatch):
    import O4_Config_Utils as CFG
    build = tmp_path / "lean"
    (build / "terrain").mkdir(parents=True)
    (build / "terrain" / "a.ter").write_text(
        "A\n800\nTERRAIN\n\nLOAD_CENTER 45.5 7.5 2400 4096\n"
        "BASE_TEX_NOWRAP ../textures/23456_34112_BI16.dds\n"
        "BORDER_TEX ../textures/23456_34112_ZL16.png\nWET\n",
        encoding="utf-8", newline="\n")
    (build / "Ortho4XP_+45+007.cfg").write_text(
        "imprint_masks_to_dds=True\nmask_zl=14\ndefault_website='EUR'\n"
        "zone_list=[]\n", encoding="utf-8", newline="\n")

    class Tile:
        def __init__(self, lat, lon, folder):
            self.lat, self.lon = lat, lon
            self.imprint_masks_to_dds, self.mask_zl = False, 16
            self.default_website, self.zone_list = "BI", [[0, 0, "X"]]
            self.color_harmonization = False

        def read_from_config(self):
            return 1
    monkeypatch.setattr(CFG, "Tile", Tile)
    tile = LAND.TierLander()._tile({"tile": "+45+007",
                                    "build_dir": str(build)})
    assert (tile.mask_zl, tile.default_website, tile.zone_list) == (14, "EUR", [])
    assert tile.imprint_masks_to_dds is False       # its cfg said True
    os.remove(build / "terrain" / "a.ter")
    tile = LAND.TierLander()._tile({"tile": "+45+007",
                                    "build_dir": str(build)})
    assert tile.imprint_masks_to_dds is True        # no mask named: its cfg
