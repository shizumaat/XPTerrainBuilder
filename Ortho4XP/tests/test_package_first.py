"""Twins for PACKAGE FIRST (owner 2026-11-11T16:45Z: "Yes, when
"clearing" or compressing a tile, we should create a package for it.",
``o4_engine.package_first``) on ``test_storage_packages``' synthetic data
folder: every path that clears a built tile's rebuild data or inputs
writes the tile's package first —

* Free space by hand (``storage_clear``) of the rebuild, elevation and
  map stores; a dry run writes none;
* a package already holding every input the tile has is kept, never
  replaced by one written after some inputs went;
* Library ▸ Delete and Library ▸ Free cache;
* Convert existing tiles ▸ Free space… (``world_retire.purge``);
* a tile that cannot be packaged is cleared as before, and the log
  says why.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
from o4_engine import library as LIB  # noqa: E402
from o4_engine import storage as ST  # noqa: E402
from o4_engine import storage_packages as PACKAGES  # noqa: E402
from o4_engine import world_retire as RETIRE  # noqa: E402
from test_storage_packages import BARE, OLD, data  # noqa: E402,F401
from test_storage_settings import root  # noqa: E402,F401

ALL = ["+29+031", "+30+031", "+31+031", "+32+031"]


def _packaged():
    return sorted(PACKAGES.packaged())


def test_free_space_by_hand_packages_each_built_tile_first(data):  # noqa: F811
    out = ST.storage_clear(kinds=["rebuild"], confirm=True)
    assert out["freed_bytes"] > 0
    assert not os.path.exists(os.path.join(data[OLD]["cache"], "Data+30+031.mesh"))
    assert _packaged() == ALL
    for row in PACKAGES.packaged().values():
        assert os.path.isfile(row["path"]) and not row["restored"]
    assert out["kinds"][PACKAGES.KIND] < 0             # the packages' bytes, booked


def test_a_dry_run_writes_no_package(data):  # noqa: F811
    ST.storage_clear(kinds=["elevation"], dry_run=True)
    assert _packaged() == [] and os.path.exists(data[OLD]["hgt"])


def test_a_package_holding_every_input_is_kept(data):  # noqa: F811
    ST.storage_clear(kinds=["rebuild"], confirm=True)
    path = PACKAGES.packaged()["+30+031"]["path"]
    mtime = os.stat(path).st_mtime_ns
    ST.storage_clear(kinds=["elevation"], confirm=True)
    ST.storage_clear(kinds=["osm"], confirm=True)
    assert not os.path.exists(data[OLD]["hgt"])
    assert os.stat(path).st_mtime_ns == mtime          # never a smaller one


def test_library_delete_and_free_cache_package_first(data):  # noqa: F811
    LIB.library_delete([OLD], FNAMES.Tile_dir, confirm=True)
    assert not os.path.exists(data[OLD]["folder"])
    assert _packaged() == ["+30+031"]
    LIB.free_cache("osm", confirm=True)
    assert not os.path.exists(data[BARE]["osm"]) or not os.listdir(data[BARE]["osm"])
    assert _packaged() == ALL


def test_free_space_after_convert_packages_the_tile_first(data):  # noqa: F811
    name = os.path.basename(data[OLD]["folder"])
    out = RETIRE.purge(FNAMES.Tile_dir, {name: {"state": "dynamic"}})
    assert out["removed"] == [name] and not os.path.exists(data[OLD]["folder"])
    assert _packaged() == ["+30+031"]


def test_a_tile_that_cannot_be_packaged_is_still_cleared(data):  # noqa: F811
    for name in os.listdir(data[BARE]["osm"]):
        os.remove(os.path.join(data[BARE]["osm"], name))
    ST.storage_clear(kinds=["rebuild"], confirm=True)
    assert "+32+031" not in _packaged()
    assert not os.path.exists(os.path.join(FNAMES.rebuild_root(), "+32+031",
                                           "Data+32+031.mesh"))
    with open(os.path.join(FNAMES.data_path("logs"), ST.LOG_NAME), encoding="utf-8") as log:
        assert "not packaged +32+031 before clearing" in log.read()
