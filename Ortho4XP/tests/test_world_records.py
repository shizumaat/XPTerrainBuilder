"""Twins for a kept tile's records copied where a new tile keeps them
(owner 2026-11-12T21:56Z: "The point is not to need the old source
because they've been converted"; ``o4_engine.world_records``), offline,
on homes shaped like the owner's real records (an ``originals/`` folder
with this app's cfg, airport record and build record; a lean copy with
cfgs, imagery record and colour field; a source drive with build logs):

* each record comes from the FIRST home that has it, a newer record in
  the Tiles folder is never overwritten, build rows merge by build;
* the dry run writes nothing and counts by home; the run then finds
  them all there;
* the tile pane's read of the Tiles folder (``O4_Tile_Info``) shows the
  provider, detail, both dates, Built by, the airport elevation and the
  graded airports from the records alone;
* a ``world-migrate`` run gives a kept tile its records itself, and a
  folder holding only an imagery record is a tile whose imagery the
  record names.
"""
from __future__ import annotations

import json
import os
import time

import O4_File_Names as FNAMES
import O4_Tile_Build_Log as TLOG
import O4_Tile_Info as TINFO
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_records as RECORDS
from test_world_migrate import xp  # noqa: F401

LAT, LON = 51, -115
TILE = "+51-115"
NAME = "zOrtho4XP_" + TILE
MESH_TIME = 1794322214.03


def _write(path, data, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(data if isinstance(data, str) else json.dumps(data))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _row(start, app="1.0.481", airports=None):
    row = {"builder": {"app_version": app, "engine_version": "1.50.1903",
                       "tool": "XPTerrainBuilder"},
           "duration": 10.0, "start": start, "end": start + 10,
           "log": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(start))
           + f"_{TILE}.log", "outcome": "ok", "tile": TILE, "warnings": 0}
    if airports:
        row["airports"] = airports
    return row


def _builds(folder, rows):
    for row in rows:
        _write(os.path.join(folder, "build_logs", row["log"]), "log\n")
    _write(os.path.join(folder, "build_logs", "build_record.json"),
           {"schema": 1, "builds": rows})


def _homes(tmp_path):
    """``(record, tiles_dir)``: an originals/ folder, a lean copy and a
    drive folder, as the journal names them."""
    old = time.time() - 86400
    original = str(tmp_path / "work" / "originals" / NAME)
    lean = str(tmp_path / "work" / "lean" / NAME)
    drive = str(tmp_path / "Drive" / NAME)
    _write(os.path.join(original, f"XPTerrainBuilder_{TILE}.cfg"),
           "cfg_written_by=1.0.481\ndefault_website=Arc\ndefault_zl=16\n"
           "zone_list=[]\n", old)
    _write(os.path.join(original, "o4_unpatched_airports.json"),
           {"airport_inset_sources": [
               {"icao": "CYYC", "provider": "HRDEM", "resolution_m": 1.0},
               {"icao": "CYBW", "provider": "HRDEM", "resolution_m": 1.0},
               {"icao": "Field", "provider": "COPERNICUSGLO30",
                "resolution_m": 30.0}]}, old)
    _builds(original, [_row(1794000000.0, airports={
        "CYYC": {"custom": True, "pack": "Calgary pack"},
        "CYBW": {"custom": False, "pack": "Global Airports"}})])
    _write(os.path.join(lean, f"XPTerrainBuilder_{TILE}.cfg"),
           "default_website=BI\n", old)            # originals/ wins
    _write(os.path.join(lean, f"Ortho4XP_{TILE}.cfg"), "mesh_zl=19\n", old)
    _write(os.path.join(lean, f"Ortho4XP_{TILE}_imagery.json"),
           {"provider": "Arc", "zoomlevel": 16, "on_demand": True,
            "mesh": [162895705, MESH_TIME]}, old)
    _write(os.path.join(lean, "color_field.json"), {"grids": []}, old)
    _write(os.path.join(lean, ".ondemand_convert.json"), {"version": 1}, old)
    _builds(drive, [_row(1793000000.0, app="1.0.470")])
    record = {"state": "done", "original": original, "config_dir": lean,
              "source": drive}
    return record, str(tmp_path / "data" / "Tiles" / NAME)


def test_each_record_comes_from_the_first_home_that_has_it(tmp_path):
    record, tiles = _homes(tmp_path)
    done = RECORDS.copy_records(record, LAT, LON, tiles)
    assert done["homes"] == ["originals", "lean", "drive"]
    assert set(done["copied"]) == {
        f"XPTerrainBuilder_{TILE}.cfg", f"Ortho4XP_{TILE}.cfg",
        f"Ortho4XP_{TILE}_imagery.json", "o4_unpatched_airports.json",
        "color_field.json", "build_record.json"}
    with open(os.path.join(tiles, f"XPTerrainBuilder_{TILE}.cfg"),
              encoding="utf-8") as handle:
        assert "default_website=Arc" in handle.read()
    # the lean copy's own stamp marks a lean copy: never copied
    assert not os.path.exists(os.path.join(tiles, ".ondemand_convert.json"))
    rows = TLOG.read_records(tiles, LAT, LON)
    assert [r["start"] for r in rows] == [1794000000.0, 1793000000.0]
    for row in rows:                                  # each with its log
        assert TLOG.read_log(tiles, row["log"]) == "log\n"
    # no home is written
    assert not os.path.exists(os.path.join(record["config_dir"],
                                           "build_logs"))
    # a second copy has nothing left to do
    assert RECORDS.copy_records(record, LAT, LON, tiles)["copied"] == []


def test_a_newer_record_in_the_tiles_folder_wins(tmp_path):
    record, tiles = _homes(tmp_path)
    mine = _write(os.path.join(tiles, f"Ortho4XP_{TILE}_imagery.json"),
                  {"provider": "GO2", "zoomlevel": 17})
    _builds(tiles, [_row(1795000000.0, app="1.0.482")])
    RECORDS.copy_records(record, LAT, LON, tiles)
    with open(mine, encoding="utf-8") as handle:
        assert json.load(handle)["provider"] == "GO2"
    rows = TLOG.read_records(tiles, LAT, LON)
    assert [r["start"] for r in rows] == [1795000000.0, 1794000000.0,
                                          1793000000.0]


def test_the_pane_reads_the_tiles_folder_like_a_new_tile(tmp_path):
    record, tiles = _homes(tmp_path)
    RECORDS.copy_records(record, LAT, LON, tiles)
    info = TINFO.tile_info(LAT, LON, os.path.dirname(tiles))
    assert info is not None and not info.dsf_present
    assert (info.provider, info.zl, info.on_demand) == ("Arc", 16, True)
    assert info.mesh_date == MESH_TIME                 # the record's mesh
    assert info.imagery_date is not None               # the record's date
    assert info.built_by == "XPTerrainBuilder 1.0.481"
    assert info.origin == TINFO.ORIGIN_HERE
    assert info.airport_elevation == ("HRDEM 1 m: CYBW, CYYC; "
                                      "COPERNICUSGLO30 30 m: Field")
    assert info.airports == "CYBW, CYYC (Calgary pack)"


def _journal(tmp_path, record):
    scenery = tmp_path / "X-Plane" / "Custom Scenery"
    scenery.mkdir(parents=True)
    journal = MIGRATE.Journal(MIGRATE.work_dir_for(str(scenery)))
    journal.set(NAME, **record)
    journal.set("zOrtho4XP_+52-115", state="dynamic",
                source=record["source"])                # not kept: skipped
    return str(scenery)


def test_backfill_dry_run_writes_nothing_then_the_run_copies(
        tmp_path, monkeypatch):
    record, tiles = _homes(tmp_path)
    monkeypatch.setattr(FNAMES, "Tile_dir", os.path.dirname(tiles))
    scenery = _journal(tmp_path, record)
    dry = RECORDS.backfill(scenery)
    assert (dry["kept"], dry["copied"], dry["files"]) == (1, 1, 6)
    assert dry["from"] == {"originals": 1, "lean": 1, "drive": 0}
    assert not os.path.exists(tiles)
    assert dry["summary"].startswith("Would give 1 of 1 kept tiles")
    done = RECORDS.backfill(scenery, dry_run=False)
    assert (done["copied"], done["files"]) == (1, 6)
    assert RECORDS.backfill(scenery)["complete"] == 1


def test_a_tile_with_no_home_left_is_named(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Tile_dir", str(tmp_path / "Tiles"))
    scenery = _journal(tmp_path, {"state": "done",
                                  "source": str(tmp_path / "Gone" / NAME)})
    out = RECORDS.backfill(scenery)
    assert out["no_home"] == [NAME] and out["copied"] == 0


def test_world_migrate_gives_a_kept_tile_its_records(xp):  # noqa: F811
    MIGRATE.migrate(xp["scenery"], ["zOrtho4XP_+46+008"],
                    index=xp["index"], workers=1)
    tiles = os.path.join(FNAMES.Tile_dir, "zOrtho4XP_+46+008")
    assert os.path.isfile(os.path.join(tiles, "Ortho4XP_+46+008.cfg"))
    info = TINFO.tile_info(46, 8, FNAMES.Tile_dir)
    # its records only (no DSF, Ortho4XP's cfg): the imagery record says
    # what imagery it carries (#1334)
    assert info is not None and info.on_demand and not info.dsf_present
    assert TINFO.effective_imagery(info) == ("BI", 16, TINFO.SOURCE_DETECTED)
