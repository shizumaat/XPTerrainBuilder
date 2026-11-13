"""Twins for older airport tiles shrunk to their package when the disk
budget is full (owner 2026-11-11T15:32Z, RULINGS 2026-11-11l item 5,
``o4_engine.storage_packages`` as the rebuild tier's ``TIER_HOOKS`` entry
of ``storage_budget``), on a synthetic data folder in ``tmp_path``
(``test_storage_settings.root``; ``test_tile_package``'s stand-ins for
the pack key and schemas).  No pipeline; the suite's network guard
refuses any download.

* the oldest non-favorite BUILT airport tile goes first, favorites last,
  a tile with no airport never;
* its package is written in the local store, then its rebuild data, its
  own downloaded inputs and its sharp imagery go; its DSF, its patches
  and the neighbours' shared rasters stay;
* the earlier elevation / map tier leaves those inputs for the package,
  and a built tile whose inputs it does clear is packaged first;
* restoring before a build lays every input back, byte and time
  identical: the rebuild downloads nothing but imagery.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import pytest  # noqa: E402
from o4_engine import storage as ST  # noqa: E402
from o4_engine import storage_budget as TOTAL  # noqa: E402
from o4_engine import storage_packages as PACKAGES  # noqa: E402
from test_storage_settings import _write, root  # noqa: E402,F401
from tile_bundle import export as EXPORT  # noqa: E402
from tile_bundle import inputs as INPUTS  # noqa: E402
from tile_bundle import install as INSTALL  # noqa: E402
from tile_bundle import key as KEY  # noqa: E402
from tile_bundle import package as PACKAGE  # noqa: E402

DAY = 86400.0
OLD, NEW, FAV, BARE = (30, 31), (31, 31), (29, 31), (32, 31)


class _Tile:
    def __init__(self, lat, lon, *_a, **_k):
        self.lat, self.lon = lat, lon
        self.build_dir = os.path.join(FNAMES.Tile_dir, FNAMES.tile_dir(lat, lon))
        self.custom_build_dir = ""
        self.base_elevation_source = "auto"


def _built(lat, lon, age_days, airport="ZZAA"):
    """A tile this app built ``age_days`` ago: its DSF and stamped cfg,
    its rebuild cache (a mesh), its downloads and (``airport``) a patch."""
    import O4_Cfg_Vars as CFGVARS
    folder = os.path.join(FNAMES.Tile_dir, FNAMES.tile_dir(lat, lon))
    key = FNAMES.short_latlon(lat, lon)
    _write(os.path.join(folder, "Earth nav data", FNAMES.round_latlon(lat, lon),
                        key + ".dsf"), 5000, age_days)
    with open(os.path.join(folder, "Ortho4XP_%s.cfg" % key), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write("%s=1\n" % CFGVARS.cfg_stamp_key)
    cache = os.path.join(FNAMES.rebuild_root(), key)
    _write(os.path.join(cache, "Data%s.mesh" % key), 400_000, age_days)
    pointer = FNAMES.rebuild_pointer_path(folder, lat, lon)
    with open(pointer, "w", encoding="utf-8", newline="\n") as handle:
        handle.write('{"cache": %s}' % __import__("json").dumps(cache))
    osm = FNAMES.osm_dir(lat, lon)
    _write(os.path.join(osm, key + "_airports.osm.bz2"), 30_000, age_days)
    stem = FNAMES.hem_latlon(lat, lon)
    block = os.path.dirname(FNAMES.base_file_name(lat, lon))
    _write(os.path.join(block, stem + ".hgt"), 60_000, age_days)
    if airport:
        _write(os.path.join(FNAMES.patch_dir(lat, lon),
                            airport + "_edited.patch.osm"), 900, age_days)
    return {"folder": folder, "cache": cache, "osm": osm,
            "hgt": os.path.join(block, stem + ".hgt")}


@pytest.fixture
def data(root, monkeypatch):  # noqa: F811
    from patch_library import client as LIBCLIENT
    from patch_library import terms as TERMS
    monkeypatch.setattr(LIBCLIENT, "licences", lambda: TERMS.DEFAULT_LICENCES)
    monkeypatch.setattr(PACKAGE, "_schemas", lambda tile: {"insets": "x"})
    monkeypatch.setattr(KEY, "xplane_root", lambda tile: None)
    monkeypatch.setattr(KEY, "airport_signatures", lambda tile: {
        "ZZAA": {"pack": "", "custom": False, "signature": "s"}})
    monkeypatch.setattr(EXPORT, "load_tile", _Tile)
    monkeypatch.setattr(INSTALL, "load_tile", _Tile)
    monkeypatch.setattr(PACKAGES, "_favorites",
                        lambda: {FNAMES.short_latlon(*FAV)})
    tiles = {OLD: _built(*OLD, 90), NEW: _built(*NEW, 5),
             FAV: _built(*FAV, 400), BARE: _built(*BARE, 900, airport=None)}
    return tiles


def _sweep():
    return ST._Sweep(False, "budget", None)


def test_the_oldest_non_favorite_airport_tile_goes_first(data):
    order = [(c["lat"], c["lon"]) for c in PACKAGES._candidates()]
    assert order == [OLD, NEW, FAV]          # no airport: never; favorite: last


def test_a_tile_shrinks_to_its_package_and_keeps_its_floor(data):
    tile = data[OLD]
    own = INPUTS.own_files(*OLD)
    shared = os.path.join(os.path.dirname(FNAMES.base_file_name(*OLD)),
                          FNAMES.hem_latlon(30, 30) + ".hgt")
    _write(shared, 100, 90)                  # a neighbour's raster: shared
    sweep = _sweep()
    freed = PACKAGES.evict(1, sweep, time.time())
    record = PACKAGES.packaged()
    assert list(record) == [FNAMES.short_latlon(*OLD)]
    package = record[FNAMES.short_latlon(*OLD)]["path"]
    assert os.path.isfile(package) and package.endswith(".xptb")
    assert os.path.dirname(package) == PACKAGES.store_dir()
    assert freed > 400_000 - os.path.getsize(package)
    assert not os.listdir(tile["cache"])     # rebuild data gone
    assert own and not any(os.path.exists(p) for p in own)   # inputs, in the package
    assert os.path.exists(shared)
    dsf = os.path.join(tile["folder"], "Earth nav data", "+30+030", "+30+031.dsf")
    assert os.path.exists(dsf)               # the floor
    assert os.listdir(FNAMES.patch_dir(*OLD))
    assert os.path.exists(data[NEW]["cache"] + "/Data+31+031.mesh")
    assert sweep.result()["kinds"][PACKAGES.KIND] == -os.path.getsize(package)
    assert [(c["lat"], c["lon"]) for c in PACKAGES._candidates()] == [NEW, FAV]


def test_a_restore_lays_every_input_back_with_nothing_to_download(data, monkeypatch):
    before = {p: (Path(p).read_bytes(), os.stat(p).st_mtime_ns)
              for p in INPUTS.own_files(*OLD)}
    PACKAGES.evict(1, _sweep(), time.time())
    assert not any(os.path.exists(p) for p in before)
    left = []
    monkeypatch.setattr(INSTALL, "_downloads_left", lambda tile: left)
    details = PACKAGES.restore(*OLD)
    assert details["downloads_left"] == {"+30+031": []}
    for path, (body, mtime) in before.items():
        assert Path(path).read_bytes() == body and os.stat(path).st_mtime_ns == mtime
    assert PACKAGES.packaged()["+30+031"]["restored"]
    assert PACKAGES.restore(*OLD) is None    # once
    assert PACKAGES.restore(*NEW) is None    # never packaged


def test_the_budget_packages_at_the_rebuild_tier_and_keeps_its_inputs(data, monkeypatch):
    """Over a SET budget by more than the caches hold: the elevation/map
    tier leaves the airport tiles' inputs; the rebuild tier packages the
    oldest; the built tile with no airport is packaged before its
    downloads go (package first, owner 2026-11-11T16:45Z)."""
    assert TOTAL.TIER_HOOKS[TOTAL.REBUILD_DATA] is TOTAL._package_rebuild
    used = TOTAL.status(ST.storage_scan()["stores"])["used_bytes"]
    monkeypatch.setattr(TOTAL, "_budget_bytes",
                        lambda raw=None: int((used - 450_000) / 0.9) + 1)
    TOTAL.hold(_sweep(), time.time())
    assert not os.path.exists(data[BARE]["hgt"])          # in its package
    assert sorted(PACKAGES.packaged()) == ["+30+031", "+32+031"]
    assert os.path.isfile(PACKAGES.packaged()["+32+031"]["path"])
    assert not os.path.exists(data[OLD]["hgt"])           # in its package
    assert os.path.exists(data[NEW]["hgt"])               # kept for its package
    assert os.path.exists(data[NEW]["cache"] + "/Data+31+031.mesh")


def test_the_world_job_installs_a_package_before_a_full_build(monkeypatch):
    """The World job and the flight manager build a packaged tile from its
    package (``world_job_run._SessionBuilder``); a drape needs none."""
    from o4_engine import world_job_run as RUN
    restored, queued = [], []
    monkeypatch.setattr(PACKAGES, "restore", lambda lat, lon: restored.append((lat, lon)))

    class _Session:
        def subscribe(self, _callback):
            pass

        def enqueue_build(self, tiles, *_a, **_k):
            queued.append(tiles)
            return True
    builder = RUN._SessionBuilder(_Session(), "BI", 16, drape=lambda tile: True)
    assert builder.start(OLD, "full", 600, "destination")
    assert restored == [OLD] and queued == [[OLD]]
    builder.start(NEW, "drape", 600, "corridor")
    assert restored == [OLD]
