"""Twins for the disk budget's TILE PRIORITY (#2087, owner
2026-11-14T16:57Z, ``o4_engine.storage_priority``) and its storage tier
(owner 2026-11-14T17:01Z, ``o4_engine.storage_tier_data``), on a
synthetic data folder in ``tmp_path`` (``test_storage_settings.root``).
No network, no build.

* an old non-favorite tile is cleared fully before a more recent one
  loses anything; favorites go last;
* a tile of this session, a tile used this week and the inputs of their
  builds are never cleared; under the budget nothing is;
* with a storage tier mounted, a cleared file MOVES there; without one it
  is deleted; a full tier gives up its files used longest ago, never one
  newer than the file coming in; a build lays back what the tier holds;
  a file X-Plane reads never moves.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import pytest  # noqa: E402
from o4_engine import storage as ST  # noqa: E402
from o4_engine import storage_budget as TOTAL  # noqa: E402
from o4_engine import storage_packages as PACKAGES  # noqa: E402
from o4_engine import storage_priority as PRIORITY  # noqa: E402
from o4_engine import storage_tier_data as TIER_DATA  # noqa: E402
from o4_engine import storage_tiers as TIERS  # noqa: E402
from test_storage_settings import _write, root  # noqa: E402,F401

BLOCK = 40960       # a whole number of allocation blocks


@pytest.fixture
def data(root, monkeypatch):  # noqa: F811
    monkeypatch.setattr(PRIORITY, "_SESSION", set())
    monkeypatch.setattr(PACKAGES, "_favorites", lambda: set())
    monkeypatch.setattr(TIERS, "_configured", lambda raw=None: {})
    monkeypatch.setattr(TIERS, "_USED", {})
    return root


def _tile(lat, lon, age_days):
    """A tile's cache data, ``age_days`` old: orthophotos, a mask, map
    data, its cell's elevation and rebuild data, one block each."""
    key = FNAMES.short_latlon(lat, lon)
    return {
        "imagery": _write(os.path.join(FNAMES.Imagery_dir, FNAMES.long_latlon(
            lat, lon), "BI", "photo.jpg"), BLOCK, age_days),
        "masks": _write(os.path.join(FNAMES.mask_dir(lat, lon), "m.png"),
                        BLOCK, age_days),
        "osm": _write(os.path.join(FNAMES.osm_dir(lat, lon),
                                   key + "_roads.osm.bz2"), BLOCK, age_days),
        "elevation": _write(FNAMES.base_file_name(lat, lon) + ".hgt",
                            BLOCK, age_days),
        "rebuild": _write(os.path.join(FNAMES.rebuild_root(), key,
                                       "Data%s.mesh" % key), BLOCK, age_days),
    }


def _over(monkeypatch, nbytes):
    """Set a budget ``nbytes`` over its 90 % low water."""
    used = TOTAL.status(ST.storage_scan()["stores"])["used_bytes"]
    monkeypatch.setattr(TOTAL, "_budget_bytes",
                        lambda raw=None: int((used - nbytes) / 0.9) + 1)


def _hold():
    return TOTAL.hold(ST._Sweep(False, "budget", None), time.time())


def _left(files):
    return {kind for kind, path in files.items() if os.path.exists(path)}


def _log():
    with open(os.path.join(FNAMES.data_path("logs"), ST.LOG_NAME),
              encoding="utf-8") as handle:
        return handle.read()


def test_imagery_of_every_tile_goes_before_any_tiles_rebuild_inputs(
        data, monkeypatch):
    """#2207: bulk first (each tile's imagery and masks, the oldest tile
    first), then every tile's rebuild data, then the map and elevation
    data -- never an old tile's map data while a newer tile's imagery
    could go."""
    old, recent = _tile(45, 7, 90), _tile(46, 7, 20)
    _over(monkeypatch, 1.5 * BLOCK)
    _hold()
    assert _left(old) == set(old) - {"imagery", "masks"}    # the oldest first
    assert _left(recent) == set(recent)
    _over(monkeypatch, 1.5 * BLOCK)
    _hold()
    assert _left(old) == _left(recent) == {"elevation", "osm", "rebuild"}
    _over(monkeypatch, 1.5 * BLOCK)
    _hold()
    assert _left(old) == _left(recent) == {"elevation", "osm"}
    _over(monkeypatch, 0.5 * BLOCK)
    _hold()
    assert len(_left(old)) == 1                     # inputs last, oldest first
    assert _left(recent) == {"elevation", "osm"}


def test_a_built_tiles_map_data_goes_after_a_tile_never_built(
        data, monkeypatch):
    built, bare = _tile(45, 7, 400), _tile(46, 7, 20)
    folder = os.path.join(FNAMES.Tile_dir, FNAMES.tile_dir(45, 7))
    monkeypatch.setattr(PRIORITY.FIRST, "built_tiles",
                        lambda: {(45, 7): folder})
    _over(monkeypatch, 7.5 * BLOCK)
    _hold()
    assert _left(bare) == set()                     # never built: first
    assert _left(built) == {"elevation", "osm"}     # built: kept longest


def test_favorites_go_last(data, monkeypatch):
    favorite, other = _tile(45, 7, 400), _tile(46, 7, 20)
    monkeypatch.setattr(PACKAGES, "_favorites", lambda: {"+45+007"})
    _over(monkeypatch, 1.5 * BLOCK)
    _hold()
    assert _left(other) == set(other) - {"imagery", "masks"}
    assert _left(favorite) == set(favorite)
    _over(monkeypatch, 5.5 * BLOCK)
    _hold()
    assert _left(other) == set()
    assert _left(favorite) == {"elevation", "osm"}


def test_a_budget_pass_logs_its_trigger_with_the_numbers(data, monkeypatch):
    """#2207: the first line of a budget pass says why it ran: the
    budget, what is in use, the free space and the target, before any
    deletion (and before any package line) of the pass."""
    _tile(45, 7, 90)
    _over(monkeypatch, 0.5 * BLOCK)
    _hold()
    lines = _log().splitlines()
    first = next(i for i, line in enumerate(lines) if "disk budget:" in line)
    assert "over the budget" in lines[first] and "free space" in lines[first]
    assert "clearing" in lines[first] and "90 % of the budget" in lines[first]
    deleted = [i for i, line in enumerate(lines) if " deleted " in line]
    assert deleted and min(deleted) > first
    assert all("disk budget)" in lines[i] for i in deleted)


def test_session_recent_tiles_and_their_build_inputs_are_never_cleared(
        data, monkeypatch):
    building, recent = _tile(45, 7, 90), _tile(47, 7, 3)
    neighbour = _tile(45, 8, 90)                    # its raster: an input
    PRIORITY.note_session([(45, 7)])
    _over(monkeypatch, 100 * BLOCK)                 # far more than there is
    _hold()
    assert _left(building) == set(building)
    assert _left(recent) == set(recent)
    assert _left(neighbour) == {"elevation"}        # the building tile reads it
    assert "disk budget still over" in _log()


def test_under_the_budget_nothing_is_cleared(data, monkeypatch):
    old = _tile(45, 7, 900)
    used = TOTAL.status(ST.storage_scan()["stores"])["used_bytes"]
    monkeypatch.setattr(TOTAL, "_budget_bytes", lambda raw=None: used + 10**10)
    assert not _hold()["over_budget"]
    assert _left(old) == set(old)


# ---------------------------------------------------------------- tiers
@pytest.fixture
def drive(data, monkeypatch):
    mount = str(data / "Drive")
    os.makedirs(mount)
    monkeypatch.setattr(TIERS, "_mounted", lambda m: os.path.isdir(m))
    return mount


def _tier(monkeypatch, mount, nbytes):
    monkeypatch.setattr(TIERS, "_configured",
                        lambda raw=None: {mount: nbytes / TIERS._GB})


def test_with_a_tier_a_cleared_file_moves_there(data, drive, monkeypatch):
    _tier(monkeypatch, drive, 100 * BLOCK)
    old = _tile(45, 7, 90)
    _over(monkeypatch, 1.5 * BLOCK)                 # imagery and the mask
    _hold()
    assert _left(old) == set(old) - {"imagery", "masks"}
    moved = TIER_DATA._target(drive, FNAMES.Imagery_dir, old["imagery"])
    assert os.path.getsize(moved) == BLOCK
    assert moved.startswith(os.path.join(drive, TIERS.TIER_DIR, "Orthophotos"))
    assert os.path.isfile(TIER_DATA._target(drive, FNAMES.masks_root(),
                                            old["masks"]))
    assert "moved %d bytes" % BLOCK in _log()


def test_without_a_tier_a_cleared_file_is_deleted(data, drive, monkeypatch):
    old = _tile(45, 7, 90)
    _over(monkeypatch, 0.5 * BLOCK)
    _hold()
    assert _left(old) == set(old) - {"imagery"}
    assert not os.listdir(drive)


def test_a_full_tier_gives_up_older_files_never_newer(data, drive, monkeypatch):
    _tier(monkeypatch, drive, 1.5 * BLOCK)
    older = _write(os.path.join(drive, TIERS.TIER_DIR, "Orthophotos", "a.jpg"),
                   BLOCK, 200)
    old = _tile(45, 7, 90)
    st = os.stat(old["imagery"])
    target = TIER_DATA.keep("imagery", FNAMES.Imagery_dir, old["imagery"], st)
    assert target and os.path.isfile(target) and not os.path.exists(older)
    newer = _tile(46, 7, 10)
    os.utime(target, (time.time(), time.time()))    # used after it
    st = os.stat(newer["imagery"])
    assert TIER_DATA.keep("imagery", FNAMES.Imagery_dir, newer["imagery"], st) == ""
    assert os.path.isfile(target) and os.path.isfile(newer["imagery"])


def test_a_build_lays_back_its_inputs_from_the_tier(data, drive, monkeypatch):
    _tier(monkeypatch, drive, 100 * BLOCK)
    tile = _tile(45, 7, 90)
    ring = _write(os.path.join(os.path.dirname(FNAMES.base_file_name(45, 8)),
                               "N45E008_approach_rings", "c.tif"), 10, 90)
    neighbour = _write(FNAMES.base_file_name(45, 8) + ".hgt", 10, 90)
    for kind, root_dir in (("osm", FNAMES.OSM_dir),
                           ("elevation", FNAMES.Elevation_dir),
                           ("rebuild", FNAMES.rebuild_root())):
        assert TIER_DATA.keep(kind, root_dir, tile[kind], os.stat(tile[kind]))
    for path in (ring, neighbour):
        assert TIER_DATA.keep("elevation", FNAMES.Elevation_dir, path,
                              os.stat(path))
    assert _left(tile) == {"imagery", "masks"}
    assert TIER_DATA.recall_tile(45, 7) == 4        # own three + neighbour raster
    assert _left(tile) == set(tile)
    assert os.path.exists(neighbour) and not os.path.exists(ring)
    assert os.path.getmtime(tile["osm"]) < time.time() - 80 * 86400


def test_a_file_xplane_reads_never_moves(data, drive, monkeypatch):
    _tier(monkeypatch, drive, 100 * BLOCK)
    dsf = _write(os.path.join(FNAMES.Tile_dir, "zOrtho4XP_+45+007",
                              "Earth nav data", "+40+000", "+45+007.dsf"),
                 BLOCK, 90)
    st = os.stat(dsf)
    for kind, store_root in (("tiles", FNAMES.Tile_dir),
                             ("imagery", FNAMES.Tile_dir),
                             ("imagery", FNAMES.data_path("")),
                             (ST.ONDEMAND, FNAMES.data_path("")),
                             ("patches", FNAMES.Patch_dir)):
        assert TIER_DATA.keep(kind, store_root, dsf, st) == ""
    assert os.path.isfile(dsf) and not os.listdir(drive)
