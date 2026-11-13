"""Twins of the World states (#2024, ``o4_engine.world_state``): every tile
the World pack or the Convert journal knows gets its state (full, mesh with
imagery streaming, drape, placeholder, nothing), who made it (built here,
adopted, another tool) and where its own files live (originals, a lean
copy, another drive); the scan streams them in ``ScanBatch.world``; the
Library rows carry them; both apps say the same words and draw the same
legend.  All on ``tmp_path``; nothing touches a real install."""
from __future__ import annotations

import dataclasses
import json
import os
import re
import threading
from pathlib import Path

import O4_DSF_Binary as DSFB
import O4_Imagery_OnDemand_Index as INDEX
import O4_Tile_Info as TINFO
import O4_World_Pack as WP
import O4_World_State_Text as TEXT
import pytest
from o4_engine import library as LIB
from o4_engine import world_state as WS
from o4_engine.events import ScanBatch, ScanDone
from o4_engine.world_migrate import WORK_DIR_NAME

REPO = Path(__file__).resolve().parents[2]
SWIFT_TEXT = REPO / "Sources" / "SceneryKit" / "WorldStateText.swift"

HERE_AGENT = "XPTerrainBuilder 1.0.495 (engine 1.50.1903) [world full]"
OTHER_AGENT = "Ortho4XP [world full]"
DRAPE_AGENT = "XPTerrainBuilder world drape"


def _dsf(pack: Path, lat: int, lon: int, agent: str) -> None:
    path = pack / WP.dsf_relpath(lat, lon)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(DSFB.placeholder_bytes(lat, lon, agent))


def _textures(pack: Path, lat: int, lon: int) -> None:
    folder = pack / "textures" / WP.tile_name(lat, lon)
    folder.mkdir(parents=True)
    (folder / "1_2_BI16.dds").write_bytes(b"DDS ")


@pytest.fixture
def world(tmp_path):
    """A Custom Scenery with the app's World pack, a Convert journal and
    an on-demand index: one tile of every state, origin and source."""
    scenery = tmp_path / "X-Plane 12" / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    work = scenery.parent / WORK_DIR_NAME
    lean = work / "lean"
    originals = work / "originals"
    journal = {}

    def record(lat, lon, **fields):
        journal["zOrtho4XP_" + WP.tile_name(lat, lon)] = fields

    # (10, 10) FULL, built here, its folder kept in originals/.
    _dsf(pack, 10, 10, HERE_AGENT)
    _textures(pack, 10, 10)
    (originals / "zOrtho4XP_+10+010").mkdir(parents=True)
    record(10, 10, state="done", kind="dir",
           original=str(originals / "zOrtho4XP_+10+010"))
    # (10, 11) FULL, another tool's, every index row sharp; a lean copy
    # whose full imagery is on another drive.
    _dsf(pack, 10, 11, OTHER_AGENT)
    (lean / "zOrtho4XP_+10+011").mkdir(parents=True)
    record(10, 11, state="done", kind="link",
           source="/Volumes/Archive/Ortho/zOrtho4XP_+10+011",
           config_dir=str(lean / "zOrtho4XP_+10+011"))
    # (10, 12) MESH, adopted (journal), half its textures sharp.
    _dsf(pack, 10, 12, OTHER_AGENT)
    record(10, 12, state="done", kind="link", adopted=True,
           source="/Volumes/Archive/Ortho/zOrtho4XP_+10+012")
    # (10, 13) MESH, adopted (the stamp of its on-demand copy); its one
    # upgraded texture is not at full width: none sharp.
    _dsf(pack, 10, 13, OTHER_AGENT)
    stamped = lean / "zOrtho4XP_+10+013"
    stamped.mkdir(parents=True)
    (stamped / TINFO.ADOPTED_STAMP).write_text('{"adopted": "now"}',
                                               encoding="utf-8", newline="\n")
    record(10, 13, state="done", kind="link", config_dir=str(stamped),
           source="/Volumes/Archive/Ortho/zOrtho4XP_+10+013")
    # (10, 14) DRAPE.
    _dsf(pack, 10, 14, DRAPE_AGENT)
    # (10, 15) PLACEHOLDER, made dynamic: the old tile is on another drive.
    WP.write_placeholder(str(pack), 10, 15)
    record(10, 15, state="dynamic", kind="link",
           link_target="/Volumes/Archive/Ortho/zOrtho4XP_+10+015")
    # (10, 16) PLACEHOLDER, coverage only (no record).
    WP.write_placeholder(str(pack), 10, 16)
    # (10, 17) NOTHING: a journal record, no DSF.
    record(10, 17, state="staging", kind="dir")
    # (10, 18) a mesh with no index rows and no textures: nothing sharp.
    _dsf(pack, 10, 18, HERE_AGENT)

    work.mkdir(exist_ok=True)
    (work / "journal.json").write_text(json.dumps(journal), encoding="utf-8",
                                       newline="\n")
    index = tmp_path / "index.sqlite"
    conn = INDEX.open_index(str(index))
    for i in range(4):
        INDEX.upsert(conn, {"tile": "+10+011", "name": f"a{i}.dds",
                            "state": "upgraded", "tier_px": 4096})
        INDEX.upsert(conn, {"tile": "+10+012", "name": f"b{i}.dds",
                            "state": "upgraded" if i < 2 else "low",
                            "tier_px": 4096 if i < 2 else 512})
        INDEX.upsert(conn, {"tile": "+10+013", "name": f"c{i}.dds",
                            "state": "upgraded" if i == 0 else "low",
                            "tier_px": 2048 if i == 0 else 512})
    conn.close()
    return str(scenery), str(index)


def test_every_state_origin_and_source(world):
    scenery, index = world
    got = WS.read_world(scenery, index_path=index)
    # each held tile names its DSF in the pack (#2027); a journal record none
    assert got[(10, 12)].dsf == os.path.join(scenery, WP.PACK_NAME, WP.dsf_relpath(10, 12))
    assert got[(10, 17)].dsf == ""
    got = {key: dataclasses.replace(tile, dsf="") for key, tile in got.items()}
    assert got == {
        (10, 10): WS.WorldTile("full", "xptb", 1.0, "originals", ""),
        (10, 11): WS.WorldTile("full", "other", 1.0, "lean", "Archive"),
        (10, 12): WS.WorldTile("mesh_lowres", "adopted", 0.5, "drive", "Archive"),
        (10, 13): WS.WorldTile("mesh_lowres", "adopted", 0.0, "lean", "Archive"),
        (10, 14): WS.WorldTile("drape", "xptb", 0.0, "", ""),
        (10, 15): WS.WorldTile("placeholder", "", 0.0, "drive", "Archive"),
        (10, 16): WS.WorldTile("placeholder", "", 0.0, "", ""),
        (10, 17): WS.WorldTile("nothing", "", 0.0, "", ""),
        (10, 18): WS.WorldTile("mesh_lowres", "xptb", 0.0, "", ""),
    }


def test_a_pack_the_app_did_not_make_reads_nothing(world):
    scenery, index = world
    os.remove(os.path.join(scenery, WP.PACK_NAME, WP.MARKER))
    assert WS.read_world(scenery, index_path=index) == {}
    assert WS.read_world("", index_path=index) == {}


def test_the_index_is_one_read_only_query(tmp_path):
    missing = tmp_path / "none" / "index.sqlite"
    assert INDEX.tile_sharpness(str(missing)) == {}
    assert not missing.parent.exists()          # nothing created


def test_the_scan_streams_world_rows(world, tmp_path, monkeypatch):
    from o4_engine.session import EngineSession
    scenery, index = world
    real = WS.iter_world
    monkeypatch.setattr(WS, "iter_world",
                        lambda d, **kw: real(d, index_path=index))
    session = EngineSession()
    events, finished = [], threading.Event()

    def on(event):
        events.append(event)
        if isinstance(event, ScanDone):
            finished.set()
    session.subscribe(on)
    tiles = tmp_path / "Tiles"
    tiles.mkdir()
    session.scan(str(tiles), scenery)
    assert finished.wait(30)
    rows = [row for e in events if isinstance(e, ScanBatch) for row in e.world]
    assert [10, 12, "mesh_lowres", "adopted", 0.5, "drive", "Archive"] in [
        row[:7] for row in rows]
    assert len(rows) == 9
    assert events[-1].world_count == 9
    assert session.scanned_world(str(tiles))[(10, 14)].state == "drape"


def test_library_rows_carry_the_world_state(world, tmp_path):
    scenery, index = world
    tiles = tmp_path / "Tiles"
    build = tiles / "zOrtho4XP_+10+012"
    build.mkdir(parents=True)
    import O4_Config_Names as CN
    Path(CN.tile_cfg_path(str(build), 10, 12)).write_text("", encoding="utf-8",
                                                          newline="\n")
    known = WS.read_world(scenery, index_path=index)
    out = LIB.library_scan(str(tiles), scenery, caches=False, world=known)
    (row,) = out["tiles"]
    assert row["world"].pop("dsf").endswith(WP.dsf_relpath(10, 12))
    assert row["world"] == {"state": "mesh_lowres", "origin": "adopted",
                            "sharp": 0.5, "source": "drive", "volume": "Archive"}
    assert TEXT.cell_text(row["world"]) == "Mesh, 50% sharp · adopted · on Archive"


def test_cell_words():
    assert TEXT.cell_text(None) == ""
    assert TEXT.cell_text(WS.WorldTile("full", "other", 1, "lean", "X").fields()) \
        == "Full · another tool's · low-res copy here, full imagery on X"
    assert TEXT.cell_text(WS.WorldTile("placeholder").fields()) == "Placeholder"


def _swift_literals() -> dict:
    """The Swift text table's string constants and string dictionaries."""
    text = SWIFT_TEXT.read_text(encoding="utf-8", newline="\n")
    out = dict(re.findall(r'static let (\w+) = "([^"]*)"', text))
    for name, body in re.findall(
            r"static let (\w+): \[String: String\] = \[(.*?)\]", text, re.S):
        out[name] = dict(re.findall(r'"(\w+)": "([^"]*)"', body))
    return out


def _camel(name: str) -> str:
    head, *rest = name.lower().split("_")
    return head + "".join(part.title() for part in rest)


def test_swift_says_what_python_says():
    python = {_camel(name): getattr(TEXT, name) for name in TEXT.__all__
              if not callable(getattr(TEXT, name))}
    assert _swift_literals() == python


def test_the_wire_states_are_the_swift_states():
    swift = SWIFT_TEXT.read_text(encoding="utf-8", newline="\n")
    cases = re.search(r"enum State: String[^{]*\{(.*?)\}", swift, re.S).group(1)
    named = set(re.findall(r'= "(\w+)"', cases))
    for line in re.findall(r"case ([^\n]+)", cases):
        named |= {word.strip() for word in line.split("=")[0].split(",")}
    assert set(WS.STATES) <= named


def test_both_legends_and_libraries_carry_the_world():
    import O4_Qt_Library as QTLIBRARY
    import O4_Qt_Map_Legend as QTLEGEND
    import O4_Qt_Map_World as QTWORLD
    assert (TEXT.COLUMN_TITLE, "world") in QTLIBRARY.COLUMNS
    library = (REPO / "Sources" / "XPTerrainBuilder" / "LibraryView.swift").read_text(
        encoding="utf-8", newline="\n")
    assert "TableColumn(O4WorldStateText.columnTitle" in library
    world = QTWORLD.from_wire([[10, 12, "mesh_lowres", "other", 0.5, "", ""],
                               [10, 13, "placeholder", "", 0, "", ""]])
    kinds = QTLEGEND.legend_kinds({}, {}, world, custom_patch=True)
    # a tile with no build has no key item (RULINGS 2026-11-13a)
    assert kinds == [QTLEGEND.WORLD_MESH, QTLEGEND.WORLD_PLACEHOLDER,
                     QTLEGEND.WORLD_OTHER_TOOL, QTLEGEND.CUSTOM_PATCH]
    assert TEXT.cell_text({"state": "nothing"}) == ""
    mac = (REPO / "Sources" / "XPTerrainBuilder" / "MapWorldStates.swift").read_text(
        encoding="utf-8", newline="\n")
    for hexcode in (QTWORLD.MESH_COLOR, QTWORLD.DRAPE_COLOR):
        assert hexcode in mac


def test_show_in_finder_reveals_the_world_dsf_of_a_records_only_tile(tmp_path):
    """#2027: an adopted tile's folder in Tiles/ holds only records, so
    "Show in Finder" reveals its DSF in the World pack (both apps:
    ``world_dsf`` / ``O4WorldTile.revealDSF``), and the map draws its
    World state alone (``built_look`` / ``MapKey.builtLook``, #2031)."""
    import types

    import O4_Qt_Map_Legend as QTLEGEND
    import O4_Qt_Map_World as QTWORLD
    dsf = str(tmp_path / "a.dsf")
    world = QTWORLD.from_wire([[51, 22, "full", "adopted", 1, "lean", "", dsf]])[(51, 22)]
    assert world.dsf == dsf and world.wire((51, 22))[-1] == dsf
    assert world.fields()["dsf"] == dsf
    records = types.SimpleNamespace(dsf_present=False, origin="adopted")
    own = types.SimpleNamespace(dsf_present=True, origin="xptb")
    assert TEXT.world_dsf(records, world) == dsf
    assert TEXT.world_dsf(None, world) == dsf
    assert TEXT.world_dsf(own, world) == ""          # its own DSF: the folder
    assert TEXT.world_dsf(records, None) == ""
    assert QTWORLD.from_wire([[1, 2, "full", "", 1, "", ""]])[(1, 2)].dsf == ""
    assert QTLEGEND.built_look(records, world, False) is None
    assert QTLEGEND.legend_kinds({(51, 22): records}, {}, {(51, 22): world}) == [
        QTLEGEND.WORLD_FULL]
    # #2031: a built tile the World pack does not list is "Full", dotted
    # when another tool built it; a stale one is "Pack changed" alone
    other = types.SimpleNamespace(dsf_present=True, origin="other")
    assert QTLEGEND.built_look(own, None, False) == (QTLEGEND.WORLD_FULL, False)
    assert QTLEGEND.built_look(other, None, False) == (QTLEGEND.WORLD_FULL, True)
    assert QTLEGEND.built_look(own, world, True) == (QTLEGEND.STALE, False)
    assert QTLEGEND.legend_kinds({(1, 1): own, (1, 2): other}, {}) == [
        QTLEGEND.WORLD_FULL, QTLEGEND.WORLD_OTHER_TOOL]
    assert QTLEGEND.legend_kinds({(51, 22): own}, {(51, 22): {"airports": []}},
                                 {(51, 22): world}) == [QTLEGEND.STALE]
    swift = SWIFT_TEXT.read_text(encoding="utf-8", newline="\n")
    assert "func revealDSF(_ info: O4TileInfo?)" in swift and "entry[7]" in swift
