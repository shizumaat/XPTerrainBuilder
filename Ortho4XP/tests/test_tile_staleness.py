"""#1958: a built tile reads stale when the airport pack X-Plane draws is
no longer the one its patch was fitted to — gone, disabled, superseded by
a pack above it, or changed (``O4_Tile_Staleness``) — and the build
record keeps the packs.  Temporary X-Plane folders only."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_Scenery_Packs as SP  # noqa: E402
import O4_Tile_Build_Log as TILELOG  # noqa: E402
import O4_Tile_Info as TINFO  # noqa: E402
import O4_Tile_Staleness as STALE  # noqa: E402
import pytest  # noqa: E402

LAT, LON = 30, -82
TILE = "+30-082"


def _apt(icao, runway_lat=30.5):
    return ("I\n1200 test\n\n1 100 0 0 %s Test field\n"
            "100 30.00 1 0 0.25 0 2 0 09 %.4f -81.6000 0 0 2 0 0 0 "
            "27 %.4f -81.5800 0 0 2 0 0 0\n\n99\n" % (icao, runway_lat, runway_lat))


def _pack(root, name, icao="KTST", **kw):
    folder = os.path.join(root, "Custom Scenery", name, "Earth nav data")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "apt.dat"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_apt(icao, **kw))
    return os.path.join(folder, "apt.dat")


def _ini(root, rows):
    ini = os.path.join(root, "Custom Scenery", SP.INI_FILENAME)
    with open(ini, "w", encoding="utf-8", newline="\n") as h:
        h.write("I\n1000 Version\nSCENERY\n\n")
        for state, name in rows:
            h.write("%s Custom Scenery/%s/\n" % (state, name))


def _tile(root, apt_dat, airports=None):
    """A built tile whose newest build selected ``apt_dat`` for KTST."""
    build_dir = os.path.join(root, "Tiles", "zOrtho4XP_" + TILE)
    logs = os.path.join(build_dir, TILELOG.LOGS_DIR)
    os.makedirs(logs)
    with open(os.path.join(logs, "b.log"), "w", encoding="utf-8", newline="\n") as h:
        h.write("  [pav-builder] KTST: apt.dat %s\n" % apt_dat)
    row = {"tile": TILE, "start": 1.0, "end": 2.0, "outcome": "ok",
           "log": "b.log", "builder": {"tool": TILELOG.BUILDER_TOOL}}
    if airports is not None:
        row["airports"] = airports
    with open(os.path.join(logs, TILELOG.RECORD_NAME), "w", encoding="utf-8", newline="\n") as h:
        json.dump({"schema": 1, "builds": [row]}, h)
    return build_dir


@pytest.fixture
def xp(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "_data_root_override", str(tmp_path / "data"))
    root = tmp_path / "X-Plane 12"
    (root / "Custom Scenery").mkdir(parents=True)
    return str(root)


def _verdict(xp, build_dir):
    return STALE._tile_staleness(build_dir, LAT, LON,
                                os.path.join(xp, "Custom Scenery"))


def test_log_airports_takes_the_last_choice(tmp_path):
    logs = tmp_path / TILELOG.LOGS_DIR
    logs.mkdir()
    (logs / "a.log").write_text(
        "  [pav-builder] KTST: apt.dat /x/Custom Scenery/A/Earth nav data/apt.dat\n"
        "noise\n"
        "  [pav-builder] KTST: apt.dat /x/Custom Scenery/B/Earth nav data/apt.dat\n",
        encoding="utf-8", newline="\n")
    assert STALE._log_airports(str(tmp_path), "a.log") == {
        "KTST": "/x/Custom Scenery/B/Earth nav data/apt.dat"}


def test_a_tile_on_the_pack_xplane_draws_is_not_stale(xp):
    apt = _pack(xp, "Test pack")
    verdict = _verdict(xp, _tile(xp, apt))
    assert verdict["checked"] and not verdict["stale"]
    assert verdict["packs"] == {"KTST": "Test pack"}


def test_gone_pack(xp):
    apt = _pack(xp, "Old pack")
    build_dir = _tile(xp, apt)
    os.rename(os.path.dirname(os.path.dirname(apt)),
              os.path.join(xp, "Custom Scenery", "Renamed pack"))
    (airport,) = _verdict(xp, build_dir)["airports"]
    assert airport["reason"] == "gone" and airport["pack"] == "Old pack"


def test_disabled_pack(xp):
    apt = _pack(xp, "Test pack")
    _ini(xp, [("SCENERY_PACK_DISABLED", "Test pack")])
    (airport,) = _verdict(xp, _tile(xp, apt))["airports"]
    assert airport["reason"] == "disabled"
    assert "disabled in scenery_packs.ini" in airport["text"]


def test_superseded_by_a_pack_above_it(xp):
    apt = _pack(xp, "Lower pack")
    _pack(xp, "Upper pack")
    _ini(xp, [("SCENERY_PACK", "Upper pack"), ("SCENERY_PACK", "Lower pack")])
    (airport,) = _verdict(xp, _tile(xp, apt))["airports"]
    assert airport["reason"] == "superseded"
    assert airport["now_pack"] == "Upper pack"
    assert airport["text"] == "KTST: X-Plane now draws Upper pack, not Lower pack"


def test_changed_pack_content_by_signature(xp, monkeypatch):
    apt = _pack(xp, "Test pack")
    recorded = {"KTST": {"pack": "Test pack", "custom": True,
                         "signature": "before", "apt_dat": apt}}
    build_dir = _tile(xp, apt, airports=recorded)
    monkeypatch.setattr(STALE, "_pack_now",
                        lambda *a: {"pack": "Test pack", "signature": "before"})
    assert not _verdict(xp, build_dir)["stale"]
    monkeypatch.setattr(STALE, "_pack_now",
                        lambda *a: {"pack": "Test pack", "signature": "after"})
    (airport,) = _verdict(xp, build_dir)["airports"]
    assert airport["reason"] == "changed"


def test_record_airports_takes_the_real_signature(xp):
    apt = _pack(xp, "Test pack")
    build_dir = _tile(xp, apt)
    entry = STALE.record_airports(build_dir, "b.log", LAT, LON)["KTST"]
    assert entry["pack"] == "Test pack" and entry["custom"] is True
    assert entry["apt_dat"] == apt and len(entry["signature"]) == 32
    # Same pack, same bytes: the signature matches and the tile is fresh.
    rewritten = _tile(os.path.join(xp, "again"), apt, airports={"KTST": entry})
    assert not _verdict(xp, rewritten)["stale"]
    # the developer's update
    with open(apt, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_apt("KTST", runway_lat=30.6))
    (airport,) = _verdict(xp, rewritten)["airports"]
    assert airport["reason"] == "changed"


def test_a_tile_without_records_is_not_checked(xp):
    build_dir = os.path.join(xp, "Tiles", "zOrtho4XP_" + TILE)
    os.makedirs(build_dir)
    verdict = _verdict(xp, build_dir)
    assert not verdict["checked"] and not verdict["stale"]
    reply = STALE.check_tiles(os.path.join(xp, "Custom Scenery"),
                              [(LAT, LON, build_dir)])
    assert reply == {"tiles": [], "stale": 0, "checked": 0}


def test_failed_newest_build_reads_the_build_before_it(xp):
    apt = _pack(xp, "Test pack")
    build_dir = _tile(xp, apt)
    path = os.path.join(build_dir, TILELOG.LOGS_DIR, TILELOG.RECORD_NAME)
    with open(path, encoding="utf-8") as h:
        doc = json.load(h)
    doc["builds"].append({"tile": TILE, "start": 5.0, "outcome": "failed",
                          "log": "missing.log"})
    with open(path, "w", encoding="utf-8", newline="\n") as h:
        json.dump(doc, h)
    row, recorded = STALE._recorded_airports(build_dir, LAT, LON)
    assert row["log"] == "b.log" and set(recorded) == {"KTST"}


def test_check_tiles_lists_the_stale_count(xp):
    apt = _pack(xp, "Test pack")
    _ini(xp, [("SCENERY_PACK_DISABLED", "Test pack")])
    build_dir = _tile(xp, apt)
    reply = STALE.check_tiles(os.path.join(xp, "Custom Scenery"),
                              [[LAT, LON, build_dir]])
    assert reply["stale"] == 1 and reply["checked"] == 1
    assert reply["tiles"][0]["airports"][0]["reason"] == "disabled"


def test_finished_build_records_its_airport_packs(xp):
    apt = _pack(xp, "Test pack")
    build_dir = os.path.join(xp, "Tiles", "zOrtho4XP_" + TILE)
    logs = TILELOG.TileBuildLogs(who={"tool": TILELOG.BUILDER_TOOL,
                                      "app_version": "t", "engine_version": "t"})
    logs.begin((LAT, LON), build_dir)
    logs.line((LAT, LON), "  [pav-builder] KTST: apt.dat %s" % apt)
    logs.finish((LAT, LON), "ok")
    row = TILELOG.last_build(build_dir, LAT, LON)
    assert row["airports"]["KTST"]["pack"] == "Test pack"
    assert row["airports"]["KTST"]["signature"]


def test_listing_snapshot_reads_the_folder_once(tmp_path, monkeypatch):
    scenery = tmp_path / "Custom Scenery"
    (scenery / "A").mkdir(parents=True)
    calls = []
    real = SP._enabled_pack_names
    monkeypatch.setattr(SP, "_enabled_pack_names",
                        lambda d: calls.append(d) or real(d))
    with SP.listing_snapshot():
        SP.load_order(str(scenery))
        SP.load_order(str(scenery))
    assert len(calls) == 1
    SP.load_order(str(scenery))                 # outside: read again
    assert len(calls) == 2


def test_origin_tells_this_apps_tiles_from_others(tmp_path):
    ours = tmp_path / ("zOrtho4XP_" + TILE)
    dsf = ours / "Earth nav data" / (FNAMES.long_latlon(LAT, LON) + ".dsf")
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"x")
    info = TINFO.tile_info(LAT, LON, str(tmp_path))
    assert info.origin == TINFO.ORIGIN_OTHER
    (ours / ("Ortho4XP_" + TILE + "_steps.json")).write_text(
        "{}", encoding="utf-8", newline="\n")
    assert TINFO.tile_info(LAT, LON, str(tmp_path)).origin == TINFO.ORIGIN_HERE
