"""The patch editor's engine commands (spec patch-editor-20261015 §1-§2,
protocol 1.12): ``patch_list`` / ``patch_load`` / ``patch_save`` /
``patch_revert``.  Headless: every patch is a copy under ``tmp_path``
(the data repo is only READ, for one real auto patch)."""

import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
from auto_patch import build_support as BS  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine import patch_commands as PC  # noqa: E402
from o4_engine import patch_file as PF  # noqa: E402

TILE = "+30+031"
_REAL_STALENESS = PC._staleness
HECA = "/Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031/HECA_auto.patch.osm"

_JOSM = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="JOSM">
  <node id="-1" lat="30.1" lon="31.4"><tag k="alt_abs" v="100.125"/><tag k="note" v="kept"/></node>
  <node id="-2" lat="30.1" lon="31.401"><tag k="alt_abs" v="101"/></node>
  <node id="-3" lat="30.101" lon="31.4"/>
  <way id="-10"><nd ref="-1"/><nd ref="-2"/><nd ref="-3"/><nd ref="-1"/><tag k="aeroway" v="apron"/></way>
  <relation id="-20"><member type="way" ref="-10" role="outer"/><tag k="type" v="multipolygon"/></relation>
</osm>
"""


@pytest.fixture
def patches(tmp_path, monkeypatch):
    """A Patches root under tmp_path; staleness answered without an
    X-Plane install (its own test drives the real computation)."""
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    monkeypatch.setattr(PC, "_staleness", lambda tile, icao, doc, source: (False, []))
    directory = FNAMES.patch_dir(30, 31)
    os.makedirs(directory)
    return directory


@pytest.fixture
def heca(patches):
    if not os.path.isfile(HECA):
        pytest.skip("the data repo's HECA auto patch is not on this machine")
    path = os.path.join(patches, "HECA_auto.patch.osm")
    shutil.copyfile(HECA, path)
    return path


def _body(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n", 2)[2]          # past the XML line and the root


def test_load_then_save_with_no_edits_rewrites_the_same_nodes_and_ways(heca, patches):
    listed = PC.patch_list(TILE)["airports"]
    assert [(a["icao"], a["source"], a["path"]) for a in listed] == [("HECA", "auto", heca)]
    doc = PC.patch_load(TILE, "HECA")
    assert doc["min_distinct_spacing_m"] == 0.5 and doc["identity_dp"] == 11
    assert listed[0]["nodes"] == len(doc["nodes"]) and listed[0]["ways"] == len(doc["ways"])
    saved = PC.patch_save(TILE, "HECA", doc["path"], doc["nodes"], doc["ways"])
    edited = os.path.join(patches, "HECA_edited.patch.osm")
    assert saved == {"path": edited, "nodes": len(doc["nodes"]), "ways": len(doc["ways"])}
    # the same nodes and ways, byte for byte below the header — the
    # sub-spacing pairs (0.499-0.500 m) included: nothing merges at save
    assert _body(edited) == _body(heca)
    again = PF.read_patch(edited)
    assert again.nodes == doc["nodes"] and again.ways == doc["ways"]
    # the header: the base's stamps re-keyed, the editor's mark
    assert again.header["o4_user_edited"] == "1"
    assert again.header["o4_edited_from_cfg"] == doc["header"]["o4_cfg"]
    assert not any(k.startswith("o4_") and not k.startswith(("o4_edited_from_", "o4_user"))
                   for k in again.header)
    assert BS.is_user_edited_patch(edited) and not BS.is_user_edited_patch(heca)
    # no live-stamp reader mistakes a recorded stamp for its own …
    assert BS.read_patch_source(edited) is None
    # … and the recorded ones parse back to exactly the base's
    line = PF.recorded_stamps_line(again.root_raw)
    assert BS.parse_patch_source(line) == BS.read_patch_source(heca)
    # the build's own manual detection picks the file up
    assert VMAP.manual_patch_files_for(patches, "HECA") == ["HECA_edited.patch.osm"]
    assert "HECA" in FNAMES.manual_patch_icaos_in(patches)
    assert PC.patch_list(TILE)["airports"][0]["source"] == "manual"


def test_resave_keeps_the_stamps_of_the_first_base(heca, patches):
    doc = PC.patch_load(TILE, "HECA")
    PC.patch_save(TILE, "HECA", doc["path"], doc["nodes"], doc["ways"])
    first = PF.read_patch(os.path.join(patches, "HECA_edited.patch.osm")).header
    doc2 = PC.patch_load(TILE, "HECA")
    assert doc2["source"] == "manual"
    nodes = [list(n) for n in doc2["nodes"]]
    nodes[0][3] = 1.5
    PC.patch_save(TILE, "HECA", doc2["path"], nodes, doc2["ways"])
    second = PF.read_patch(doc2["path"])
    assert second.header == first
    assert second.nodes[0][3] == 1.5


def test_revert_renames_and_never_deletes(heca, patches):
    doc = PC.patch_load(TILE, "HECA")
    for n in (1, 2):
        PC.patch_save(TILE, "HECA", doc["path"], doc["nodes"], doc["ways"])
        out = PC.patch_revert(TILE, "HECA")["disabled_path"]
        edited = os.path.join(patches, "HECA_edited.patch.osm")
        assert out == edited + (".disabled" if n == 1 else ".disabled.2")
        assert os.path.isfile(out) and not os.path.exists(edited)
    assert PC.patch_list(TILE)["airports"][0]["source"] == "auto"
    with pytest.raises(ValueError, match="no edited patch"):
        PC.patch_revert(TILE, "HECA")


def test_a_hand_made_patch_is_saved_back_to_itself(patches):
    path = os.path.join(patches, "LXYZ.patch.osm")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_JOSM)
    doc = PC.patch_load(TILE, "lxyz")
    assert doc["source"] == "manual" and doc["path"] == path and doc["stale"] is False
    assert doc["nodes"][2] == [-3, 30.101, 31.4, None]
    nodes = [list(n) for n in doc["nodes"]]
    nodes[1][3] = 99.0
    assert PC.patch_save(TILE, "LXYZ", path, nodes, doc["ways"])["path"] == path
    again = PF.read_patch(path)
    assert again.nodes[1][3] == 99.0 and again.nodes[0][3] == 100.125
    assert again.node_tags == {-1: [("note", "kept")]}
    assert len(again.extras) == 1 and "multipolygon" in again.extras[0]
    assert again.header["o4_user_edited"] == "1" and again.header["generator"] == "JOSM"


def test_save_refuses_a_way_whose_node_is_missing_and_a_foreign_base(patches):
    path = os.path.join(patches, "LXYZ.patch.osm")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_JOSM)
    doc = PC.patch_load(TILE, "LXYZ")
    with pytest.raises(ValueError, match="references node -3"):
        PC.patch_save(TILE, "LXYZ", path, doc["nodes"][:2], doc["ways"])
    with pytest.raises(ValueError, match="not a patch of HECA"):
        PC.patch_save(TILE, "HECA", path, doc["nodes"], doc["ways"])
    with pytest.raises(ValueError, match="build this tile first"):
        PC.patch_load(TILE, "HECA")
    with pytest.raises(ValueError, match="not a tile name"):
        PC.patch_list("30,31")


def test_staleness_compares_the_recorded_stamps(heca, patches, monkeypatch):
    """§1.4: the edited patch's RECORDED stamps reach the reuse gate's own
    computation, under their original names."""
    monkeypatch.setattr(PC, "_staleness", _REAL_STALENESS)
    seen = {}

    class _Tile:
        def __init__(self, lat, lon, _d):
            self.lat, self.lon = lat, lon

        def read_from_config(self):
            pass

    import O4_Config_Utils as CFG
    from auto_patch import cifp_reader, driver
    monkeypatch.setattr(CFG, "Tile", _Tile)
    monkeypatch.setattr(VMAP, "resolve_cifp_dir_for_tile", lambda t: "/cifp")
    monkeypatch.setattr(cifp_reader, "xplane_root_from_cifp_path", lambda p: "/xp")
    monkeypatch.setattr(cifp_reader, "discover_cifp_airports", lambda p: {"HECA": "/cifp/HECA.dat"})

    def stale(meta, patch_file, xp_root, icao, **kw):
        seen.update(meta=meta, xp_root=xp_root, cifp=kw["cifp_file"])
        return [("o4_cfg", "a", "b"), ("o4_dem", "c", "d")]

    monkeypatch.setattr(driver, "auto_patch_stale_inputs", stale)
    base = PC.patch_load(TILE, "HECA")
    assert base["stale"] is True and base["stale_inputs"] == ["o4_cfg", "o4_dem"]
    PC.patch_save(TILE, "HECA", base["path"], base["nodes"], base["ways"])
    edited = PC.patch_load(TILE, "HECA")
    assert edited["source"] == "manual" and edited["stale_inputs"] == ["o4_cfg", "o4_dem"]
    assert seen == {"meta": BS.read_patch_source(heca), "xp_root": "/xp",
                    "cifp": "/cifp/HECA.dat"}


class _Capture(io.StringIO):
    def objects(self):
        return [json.loads(line) for line in self.getvalue().splitlines() if line.strip()]


def test_the_four_commands_round_trip_through_the_jsonl_transport(patches):
    path = os.path.join(patches, "LXYZ.patch.osm")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_JOSM)
    load = PC.patch_load(TILE, "LXYZ")
    commands = [
        {"cmd": "patch_list", "id": 1, "tile": TILE},
        {"cmd": "patch_load", "id": 2, "tile": TILE, "icao": "LXYZ"},
        {"cmd": "patch_save", "id": 3, "tile": TILE, "icao": "LXYZ",
         "base_path": path, "nodes": load["nodes"], "ways": load["ways"]},
        {"cmd": "patch_revert", "id": 4, "tile": TILE, "icao": "LXYZ"},
        {"cmd": "shutdown", "id": 5},
    ]
    capture = _Capture()
    jsonl.serve(io.StringIO("\n".join(json.dumps(c) for c in commands) + "\n"), capture)
    objects = capture.objects()
    assert objects[0]["event"] == "EngineHello" and objects[0]["protocol"] == EV.PROTOCOL_VERSION == "1.12"
    replies = {o["reply"]: o for o in objects if "reply" in o}
    assert replies[1]["ok"] and replies[1]["result"]["airports"][0]["bbox"] == [30.1, 31.4, 30.101, 31.401]
    assert replies[2]["ok"] and replies[2]["result"]["nodes"] == [list(n) for n in load["nodes"]]
    assert set(replies[2]["result"]) == {
        "icao", "source", "path", "stale", "stale_inputs", "min_distinct_spacing_m",
        "identity_dp", "header", "nodes", "ways"}
    assert replies[3]["ok"] and replies[3]["result"] == {"path": path, "nodes": 3, "ways": 1}
    # a hand-made file is not the editor's to revert: ok=false, a sentence
    assert replies[4]["ok"] is False and "renamed by hand" in replies[4]["error"]
