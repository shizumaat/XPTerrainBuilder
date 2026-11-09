"""#1979: patches dropped on the map or the app icon are identified (airport,
tile) and installed into the tile's Patches folder — the engine commands
``patch_drop_plan`` / ``patch_drop_install`` both apps call.  Temp-dir
fixtures only: the data root's Patches folder is redirected."""

import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
from o4_engine import events  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine import patch_drop as PD  # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    drop = tmp_path / "drop"
    drop.mkdir()
    return drop


def _patch(path, icao=None, tiles=None, lat=39.22, lon=-106.87):
    attrs = "version='0.6'"
    if icao:
        attrs += " o4_icao='%s'" % icao
    if tiles:
        attrs += " o4_dsf_tiles='%s'" % tiles
    nodes = ("  <node id='-1' lat='%.5f' lon='%.5f'>\n"
             "    <tag k='alt_abs' v='2341.6' />\n  </node>\n" % (lat, lon)
             if lat is not None else "")
    text = ("<?xml version='1.0' encoding='UTF-8'?>\n<osm %s>\n%s</osm>\n"
            % (attrs, nodes))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return str(path)


def test_a_patch_goes_to_its_header_tile_with_its_family(root):
    src = _patch(root / "KASE_auto.patch.osm", "KASE", "39,-107")
    (root / "KASE_auto.patch.osm.axes.json").write_text("{}", encoding="utf-8", newline="")
    (root / "o4_v2_rebake_KASE.json").write_text("{}", encoding="utf-8", newline="")
    (root / "KASE.graded.json").write_text("{}", encoding="utf-8", newline="")
    (root / "notes.txt").write_text("x", encoding="utf-8", newline="")

    plan = PD.patch_drop_plan([src])
    (item,) = plan["items"]
    target = os.path.join(FNAMES.patch_dir(39, -107), "KASE_auto.patch.osm")
    assert (item["icao"], item["tile"], item["found_by"]) == ("KASE", "+39-107", "header")
    assert item["destination"] == target and item["replaces"] is False
    assert sorted(item["companions"]) == ["KASE.graded.json",
                                          "KASE_auto.patch.osm.axes.json",
                                          "o4_v2_rebake_KASE.json"]
    assert not os.path.exists(FNAMES.patch_dir(39, -107))    # plan writes nothing

    PD.patch_drop_install([src])
    assert sorted(os.listdir(FNAMES.patch_dir(39, -107))) == [
        "KASE.graded.json", "KASE_auto.patch.osm",
        "KASE_auto.patch.osm.axes.json", "o4_v2_rebake_KASE.json"]


def test_no_header_falls_back_to_the_name_and_the_nodes(root):
    src = _patch(root / "HECA.patch.osm", lat=30.11, lon=31.40)
    (item,) = PD.patch_drop_plan([src])["items"]
    assert (item["icao"], item["tile"], item["found_by"]) == ("HECA", "+30+031", "geometry")


def test_a_header_tile_the_nodes_miss_is_not_trusted(root):
    src = _patch(root / "HECA.patch.osm", "HECA", "29,31", lat=30.11, lon=31.40)
    (item,) = PD.patch_drop_plan([src])["items"]
    assert item["tile"] == "+30+031"


def test_a_name_for_another_airport_is_prefixed(root):
    src = _patch(root / "mine.patch.osm", "KASE", "39,-107")
    (item,) = PD.patch_drop_plan([src])["items"]
    assert os.path.basename(item["destination"]) == "KASE_mine.patch.osm"


def test_a_folder_is_searched_and_others_are_skipped(root):
    _patch(root / "a" / "KASE_edited.patch.osm", "KASE", "39,-107")
    _patch(root / "a" / "b" / "HECA.patch.osm", "HECA", lat=30.1, lon=31.4)
    _patch(root / "a" / ".hidden" / "XXXX.patch.osm", "XXXX")
    readme = root / "README.txt"
    readme.write_text("x", encoding="utf-8", newline="")

    plan = PD.patch_drop_plan([str(root / "a"), str(readme)])
    assert plan["summary"] == [
        "KASE_edited.patch.osm → KASE, tile +39-107",
        "HECA.patch.osm → HECA, tile +30+031",
        "Skipped: README.txt is not a patch (a .patch.osm file, a folder "
        "or a .zip of them)"]
    assert sorted(i["icao"] for i in plan["items"]) == ["HECA", "KASE"]
    assert plan["tiles"] == ["+30+031", "+39-107"]
    (skip,) = plan["skipped"]
    assert skip["source"] == str(readme) and "not a patch" in skip["skip"]


def test_a_zip_is_unpacked_and_installed(root):
    src = _patch(root / "KASE_auto.patch.osm", "KASE", "39,-107")
    archive = root / "kase.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(src, "pack/KASE_auto.patch.osm")
        zf.writestr("__MACOSX/pack/._KASE_auto.patch.osm", "junk")
    out = PD.patch_drop_install([str(archive)])
    (item,) = out["items"]
    assert item["source"] == os.path.join(str(archive), "pack", "KASE_auto.patch.osm")
    assert os.path.isfile(item["destination"])


def test_a_zip_reaching_outside_itself_is_refused(root):
    archive = root / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../KASE.patch.osm", "<osm o4_icao='KASE'/>")
    with pytest.raises(ValueError, match="outside its own folder"):
        PD.patch_drop_plan([str(archive)])
    assert not (root.parent / "KASE.patch.osm").exists()


def test_a_replaced_file_is_set_aside_and_an_identical_one_skipped(root):
    src = _patch(root / "KASE_edited.patch.osm", "KASE", "39,-107")
    directory = FNAMES.patch_dir(39, -107)
    os.makedirs(directory)
    old = os.path.join(directory, "KASE_edited.patch.osm")
    with open(old, "w", encoding="utf-8", newline="") as handle:
        handle.write("<osm version='0.6'/>")

    (item,) = PD.patch_drop_plan([src])["items"]
    assert item["replaces"] is True
    (done,) = PD.patch_drop_install([src])["items"]
    assert done["backups"] == [old + ".disabled"]
    with open(old + ".disabled", encoding="utf-8") as handle:
        assert handle.read() == "<osm version='0.6'/>"

    with pytest.raises(ValueError, match="already installed"):
        PD.patch_drop_plan([src])


def test_nothing_installable_is_one_sentence(root):
    other = root / "photo.png"
    other.write_bytes(b"x")
    with pytest.raises(ValueError) as error:
        PD.patch_drop_plan([str(other)])
    assert str(error.value).startswith("Nothing to install: photo.png is not a patch")


def test_two_drops_to_one_destination_keep_the_first(root):
    a = _patch(root / "a" / "KASE.patch.osm", "KASE", "39,-107")
    _patch(root / "b" / "KASE.patch.osm", "KASE", "39,-107")
    plan = PD.patch_drop_plan([a, str(root / "b")])
    assert [i["source"] for i in plan["items"]] == [a]
    assert "already goes to" in plan["skipped"][0]["skip"]


def test_the_engine_serves_both_commands():
    assert "patch_drop" in events.CAPABILITIES
    handlers = jsonl._build_handlers(object.__new__(jsonl.EngineSession))
    assert handlers["patch_drop_plan"] is PD.patch_drop_plan
    assert handlers["patch_drop_install"] is PD.patch_drop_install
