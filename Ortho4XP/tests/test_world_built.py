"""Twins of the World tiles built outside the working folder (owner
2026-11-12T22:19Z: a tile a flight had just built showed no patch view or
editor when zoomed in): the scan lists the World pack's tiles whose
folders are in the data folder's ``Tiles/`` when the working folder is
another one (``o4_engine.world_built``); ``tile_info`` finds a tile in
the folder the session built it into; both apps rescan on a World/flight
swap (``O4_World_Swap_Watch``, the Mac's ``WorldSwapWatch`` on the same
fixture).  All on ``tmp_path``; nothing touches a real install."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import O4_DSF_Binary as DSFB
import O4_File_Names as FNAMES
import O4_World_Pack as WP
import O4_World_Swap_Watch as SWAPWATCH
import pytest
from o4_engine import world_built as WB
from o4_engine.events import ScanBatch, ScanDone

CASES = Path(__file__).parent / "fixtures" / "world_swap_watch_cases.json"
AGENT = "XPTerrainBuilder 1.0.500 (engine 1.50.1902) [world full]"


def _built_tile(tiles: Path, lat: int, lon: int) -> Path:
    folder = tiles / ("zOrtho4XP_" + WP.tile_name(lat, lon))
    dsf = Path(FNAMES.dsf_file(str(folder), lat, lon))
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(DSFB.placeholder_bytes(lat, lon, AGENT))
    return folder


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """A custom build folder (empty), the data folder's Tiles/ with two
    built tiles, and a World pack holding one of them."""
    scenery = tmp_path / "X-Plane 12" / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    path = pack / WP.dsf_relpath(8, 38)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(DSFB.placeholder_bytes(8, 38, AGENT))
    tiles = tmp_path / "Data" / "Tiles"
    _built_tile(tiles, 8, 38)
    _built_tile(tiles, 9, 38)               # not in the World pack
    monkeypatch.setattr(FNAMES, "Tile_dir", str(tiles))
    custom = tmp_path / "Custom build"
    custom.mkdir()
    return str(scenery), str(tiles), str(custom)


def _scan(session, working_dir, scenery):
    events, finished = [], threading.Event()

    def on(event):
        events.append(event)
        if isinstance(event, ScanDone):
            finished.set()
    session.subscribe(on)
    session.scan(working_dir, scenery)
    assert finished.wait(30)
    built = {}
    for event in events:
        if isinstance(event, ScanBatch):
            built.update(event.built)
    return built, events[-1]


def test_the_scan_lists_world_tiles_built_in_the_data_folder(layout):
    from o4_engine.session import EngineSession
    scenery, tiles, custom = layout
    built, done = _scan(EngineSession(), custom, scenery)
    assert set(built) == {(8, 38)}          # (9, 38): not a World tile
    assert built[(8, 38)].build_dir.startswith(tiles)
    assert done.built_count == 1


def test_one_folder_is_read_once(layout):
    _scenery, tiles, _custom = layout
    assert list(WB.iter_world_built(tiles, {(8, 38)}, set())) == []
    rows = [r for r in WB.iter_world_built("", {(8, 38)}, {(8, 38)}) if r[2]]
    assert rows == []                        # the working folder's wins


def test_tile_info_finds_the_folder_the_session_built_into(layout):
    from o4_engine.session import EngineSession
    _scenery, tiles, custom = layout
    session = EngineSession()
    assert session.tile_info(8, 38, custom) is None
    session._note_build_dirs([(8, 38)], "")  # a World/flight job's build
    info = session.tile_info(8, 38, custom)
    assert info is not None and info.dsf_present
    assert info.build_dir.startswith(tiles)


def test_a_swap_rescans_once():
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    assert cases
    for case in cases:
        watch = SWAPWATCH.SwapWatch()
        for step in case["steps"]:
            if "flight" in step:
                got = watch.flight_status(step["flight"])
            else:
                got = watch.world_status(step["world"])
            assert got is step["rescan"], case["name"]


def _records_only_tile(tiles: Path, scenery: str, lat: int, lon: int) -> Path:
    """An adopted World tile (#2027): its mesh in the World pack, only its
    imagery record in the data folder's Tiles/."""
    folder = tiles / ("zOrtho4XP_" + WP.tile_name(lat, lon))
    folder.mkdir(parents=True)
    (folder / ("Ortho4XP_%s_imagery.json" % WP.tile_name(lat, lon))).write_text(
        json.dumps({"on_demand": True, "pinned": False}), encoding="utf-8",
        newline="\n")
    path = Path(scenery) / WP.PACK_NAME / WP.dsf_relpath(lat, lon)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(DSFB.placeholder_bytes(lat, lon, AGENT))
    return folder


def test_one_built_answer_counts_a_world_tile_whose_records_are_in_tiles(layout):
    """#2027: Favorite said "not built" -- ``imagery_pin`` read only the
    working folder; ``tile_info`` is the scan's rule for one tile."""
    scenery, tiles, custom = layout
    folder = _records_only_tile(Path(tiles), scenery, 8, 39)
    info = WB.tile_info(8, 39, custom, scenery_dir=scenery)
    assert info is not None and not info.dsf_present
    assert info.build_dir == str(folder)
    assert WB.tile_info(9, 38, custom, scenery_dir=scenery) is None  # not in the pack
    assert WB.tile_info(8, 39, custom, scenery_dir="") is None       # no World pack


def test_a_world_tile_with_records_only_can_be_a_favorite(layout, monkeypatch, tmp_path):
    import O4_DDS_Cache as DDSC
    from o4_engine import imagery_ondemand as ONDEMAND
    scenery, tiles, custom = layout
    folder = _records_only_tile(Path(tiles), scenery, 8, 39)
    from o4_engine import storage_redundant
    monkeypatch.setattr(storage_redundant, "_custom_scenery_dir", lambda: scenery)
    monkeypatch.setattr(DDSC, "key_users", lambda: {})
    out = ONDEMAND.imagery_pin(8, 39, custom, pinned=True,
                               index=str(tmp_path / "index.sqlite"))
    assert out["pinned"] is True
    record = json.loads((folder / "Ortho4XP_+08+039_imagery.json").read_text(
        encoding="utf-8"))
    assert record["pinned"] is True
