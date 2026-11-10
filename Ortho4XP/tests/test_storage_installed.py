"""Installed ortho tiles (``o4_engine.storage_installed``): real
``zOrtho4XP_*`` folders of Custom Scenery are sized (and the size is
cached), links are counted by the volume their text names and never
followed, other entries are ignored."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import storage_installed as INSTALLED  # noqa: E402


def _file(path, size):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)


def test_folders_sized_links_counted_never_followed(tmp_path, monkeypatch):
    scenery = tmp_path / "Custom Scenery"
    _file(str(scenery / "zOrtho4XP_+45+007" / "textures" / "a.dds"), 50_000)
    _file(str(scenery / "zOrtho4XP_+45+008" / "Earth nav data" / "x.dsf"), 20_000)
    _file(str(scenery / "KSEA Pack" / "big.bin"), 90_000)        # not ortho
    os.symlink("/Volumes/Ortho8TB/zOrtho4XP_+46+007",
               str(scenery / "zOrtho4XP_+46+007"))               # dangling
    os.symlink("/Volumes/Ortho8TB/zOrtho4XP_+46+008",
               str(scenery / "zOrtho4XP_+46+008"))
    os.symlink(str(tmp_path / "elsewhere"), str(scenery / "zOrtho4XP_+47+007"))
    cache = str(tmp_path / "cache.json")
    out = INSTALLED.installed_tiles(str(scenery), cache)
    assert out["measured"] and out["local_count"] == 2
    assert out["local_bytes"] >= 70_000
    assert out["linked_count"] == 3
    assert {(v["volume"], v["count"]) for v in out["linked"]} == {
        ("Ortho8TB", 2), (INSTALLED.THIS_DISK, 1)}
    # The second scan reads the cache: no file is walked again.
    monkeypatch.setattr(INSTALLED, "_folder_bytes",
                        lambda folder: (_ for _ in ()).throw(AssertionError(folder)))
    assert INSTALLED.installed_tiles(str(scenery), cache) == out


def test_unset_or_missing_scenery_measures_nothing(tmp_path):
    assert not INSTALLED.installed_tiles("", str(tmp_path / "c.json"))["measured"]
    assert not INSTALLED.installed_tiles(str(tmp_path / "nope"))["measured"]
    assert INSTALLED._link_volume("D:\\Tiles\\zOrtho4XP_+1+1") == "D:"
