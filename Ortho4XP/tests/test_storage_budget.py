"""The one disk budget (RULINGS 2026-11-10d, ``o4_engine.storage_budget``)
on a synthetic data folder (``test_storage_settings.root``): the floor
is never cleared, the tiers go cheapest to rebuild first and oldest
first within a tier, the recommended minimum is the floor plus working
room, and a budget under the floor warns.
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
from o4_engine import storage_range as RANGE  # noqa: E402
from test_storage_settings import _write, root  # noqa: E402,F401

#: Every test runs on test_storage_settings' synthetic data folder.
pytestmark = pytest.mark.usefixtures("root")


def _root() -> Path:
    return Path(FNAMES.current_data_root())


BLOCK = 40960   # a whole number of allocation blocks


def _budget(monkeypatch, nbytes):
    monkeypatch.setattr(TOTAL, "_budget_bytes", lambda raw=None: int(nbytes))


def test_unset_budget_clears_nothing_and_says_so(monkeypatch):
    data = _root()
    assert TOTAL._budget_bytes({"storage_budget_gb": "0"}) == 0
    assert TOTAL._budget_bytes({"storage_budget_gb": "1.5"}) == 1_500_000_000
    _budget(monkeypatch, 0)
    old = _write(str(data / "tmp" / "x.bin"), 5000, age_days=30)
    # RULINGS 2026-11-11h (1): unconfirmed, the default holds what is in
    # use, so it is never over the default and nothing is cleared.
    monkeypatch.setattr(TOTAL, "DEFAULT_BUDGET_GB", 1e-9)
    monkeypatch.setattr(TOTAL, "_recommended_bytes", lambda floor: 1)
    out = TOTAL.hold(ST._Sweep(False, "t", None), time.time())
    assert not out["budget_set"] and not out["over_budget"]
    assert out["budget_bytes"] == out["default_bytes"] == out["held_bytes"]
    assert out["held_bytes"] >= 5000
    assert os.path.exists(old)


def test_the_default_is_200_gb_the_recommended_minimum_or_the_held_install():
    assert TOTAL.DEFAULT_BUDGET_GB == 200
    assert TOTAL._default_budget_bytes(10**9) == 200 * 10**9
    assert TOTAL._default_budget_bytes(170 * 10**9) == 255 * 10**9
    assert TOTAL._default_budget_bytes(10**9, 400 * 10**9) == 400 * 10**9


def test_the_held_figure_is_measured_once_and_only_grows(monkeypatch):
    """RULINGS 2026-11-11h (1): the first run's use (installed tiles and
    caches) is recorded; less in use later keeps it, more raises it, and a
    confirmed budget leaves it alone."""
    _budget(monkeypatch, 0)
    rows = ST.storage_scan()["stores"]
    first = TOTAL.status(rows, installed_bytes=300 * 10**9)
    assert first["held_bytes"] >= 300 * 10**9
    assert first["default_bytes"] == first["held_bytes"] and not first["over_budget"]
    assert TOTAL.status(rows)["held_bytes"] == first["held_bytes"]      # held
    more = TOTAL.status(rows, installed_bytes=500 * 10**9)["held_bytes"]
    assert more > first["held_bytes"]
    _budget(monkeypatch, 10**9)
    assert TOTAL.status(rows, installed_bytes=900 * 10**9)["held_bytes"] == 0
    _budget(monkeypatch, 0)
    assert TOTAL.status(rows)["held_bytes"] == more


def test_tiers_go_cheapest_first_and_the_floor_stays(monkeypatch):
    data = _root()
    tile = data / "Tiles" / "zOrtho4XP_+45+007"
    dsf = _write(str(tile / "Earth nav data" / "+40+000" / "+45+007.dsf"), 4000)
    patch = _write(str(data / "Patches" / "+45+007" / "A.patch.osm"), 3000)
    tmp_old = _write(str(data / "tmp" / "old.bin"), BLOCK, age_days=20)
    tmp_new = _write(str(data / "tmp" / "new.bin"), BLOCK, age_days=2)
    mask = _write(str(data / "Masks" / "+45+007" / "m.png"), BLOCK, age_days=90)
    elevation = _write(str(data / "Elevation_data" / "e.hgt"), BLOCK, age_days=90)
    figures = TOTAL.status(ST.storage_scan()["stores"])
    floor = figures["floor_bytes"]
    assert figures["floor"]["dsf"] >= 4000 and figures["floor"]["patches"] >= 3000
    assert figures["recommended_bytes"] == floor + TOTAL.ROOM_MIN_BYTES
    used = figures["used_bytes"]
    # 2.5 cache files over 90 % of the budget: tmp (old first) and then
    # the masks go; elevation (a later tier) stays.
    _budget(monkeypatch, int((used - 2.5 * BLOCK) / 0.9) + 1)
    out = TOTAL.hold(ST._Sweep(False, "budget", None), time.time())
    assert out["over_budget"]
    gone = [not os.path.exists(p) for p in (tmp_old, tmp_new, mask, elevation)]
    assert gone == [True, True, True, False]
    assert os.path.exists(dsf) and os.path.exists(patch)    # the floor


def test_a_budget_under_the_minimum_is_raised_to_it(monkeypatch):
    """#2022: a budget set below what is always kept applies as the
    minimum, with the notice; the floor is never over it."""
    import O4_Storage_Text as TEXT
    data = _root()
    _write(str(data / "Tiles" / "zOrtho4XP_+45+007" / "Earth nav data"
                / "+40+000" / "+45+007.dsf"), 9000)
    _budget(monkeypatch, 1000)
    figures = TOTAL.status(ST.storage_scan()["stores"])
    assert figures["clamped"] == "minimum" and figures["chosen_bytes"] == 1000
    assert figures["budget_bytes"] == figures["minimum_bytes"] >= figures["floor_bytes"]
    assert not figures["under_floor"]
    assert TEXT.range_notice(figures).startswith("Your budget of 0.0 MB is below")


def test_a_budget_over_the_disk_follows_it_down(monkeypatch):
    """#2022: the most is what is in use plus the free space less 50 GB;
    a budget above it follows the disk down, never under the minimum."""
    _budget(monkeypatch, 900 * 10**9)
    monkeypatch.setattr(RANGE, "_free_bytes", lambda folder: 120 * 10**9)
    figures = TOTAL.status(ST.storage_scan()["stores"])
    used = figures["used_bytes"]
    assert figures["maximum_bytes"] == used + 70 * 10**9
    assert figures["budget_bytes"] == figures["maximum_bytes"]
    assert figures["clamped"] == "followed"
    monkeypatch.setattr(RANGE, "_free_bytes", lambda folder: 10 * 10**9)
    figures = TOTAL.status(ST.storage_scan()["stores"])
    assert figures["budget_bytes"] == figures["maximum_bytes"] == figures["minimum_bytes"]
    monkeypatch.setattr(RANGE, "_free_bytes", lambda folder: None)
    assert TOTAL.status(ST.storage_scan()["stores"])["maximum_bytes"] == max(
        figures["used_bytes"], figures["minimum_bytes"])


def test_the_minimum_counts_world_placeholders_pack_tiles_and_airport_packages(
        tmp_path, monkeypatch):
    """RULINGS 2026-11-10d (2): the World pack's placeholders and tile
    DSFs and the airport tiles' packages are always kept; a package of a
    tile with no airport is not."""
    import O4_World_Pack as WP
    from o4_engine import storage_packages as PACKAGES
    scenery = tmp_path / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    WP.write_placeholders(str(pack), [(45, 7), (45, 8)])
    placeholder = os.path.getsize(pack / WP.dsf_relpath(45, 7))
    _write(str(pack / WP.dsf_relpath(46, 7)), 50000)          # a tile of ours
    monkeypatch.setattr(TOTAL, "_scenery_dir", lambda: str(scenery))
    data = _root()
    airport = _write(str(data / PACKAGES.STORE_DIR / "a.xptb"), 7000)
    other = _write(str(data / PACKAGES.STORE_DIR / "b.xptb"), 3000)
    PACKAGES.remember("+45+007", path=airport, airports=["ZZAA"])
    PACKAGES.remember("+45+008", path=other, airports=[])
    _write(str(data / "tmp" / "cache.bin"), 4000)                 # a cache
    _budget(monkeypatch, 0)
    scan = ST.storage_scan()
    figures = TOTAL.status(scan["stores"])
    least = figures["minimum"]
    assert least["world_placeholders"] == 2 * placeholder
    assert least["world_dsf"] == 50000 and least["packages"] == 7000
    assert figures["minimum_bytes"] == sum(least.values())
    assert figures["used_bytes"] >= 2 * placeholder + 50000 + 10000
    bar = figures["breakdown"]
    assert set(bar) == set(RANGE.BAR_PARTS)
    assert sum(bar.values()) == figures["used_bytes"]
    assert bar["placeholders"] == 2 * placeholder and bar["tiles"] >= 50000
    assert bar["packages"] >= 10000
    # owner 2026-11-12: the bar's Caches is the Caches line's figure
    assert bar["caches"] == scan["cache_bytes"] == ST.cache_bytes(scan["stores"])
    assert bar["caches"] >= 4000
    assert list(figures["ladder"]) == list(RANGE.LADDER_STEPS)


def test_the_recommended_minimum_is_half_again_above_50_gb():
    assert TOTAL._recommended_bytes(10**9) == 10**9 + TOTAL.ROOM_MIN_BYTES
    assert TOTAL._recommended_bytes(400 * 10**9) == 600 * 10**9
    assert [t[0] for t in TOTAL.TIERS] == ["tmp", "imagery", "dsf_dumps",
                                           "elevation", ST.ONDEMAND,
                                           TOTAL.REBUILD_DATA]


def test_the_rebuild_store_is_the_last_tier_and_clears_its_cfg_backups():
    assert TOTAL.TIERS[-1] == (ST.REBUILD,)
    store = ST._BY_KIND[ST.REBUILD]
    old = os.stat(__file__)
    later = old.st_mtime + 10 * ST.IN_FLIGHT_SECONDS
    assert ST._deletable(store, "tile.cfg.bak", old, later)
    assert not ST._deletable(store, "tile.cfg", old, later)
    assert not ST._deletable(ST._BY_KIND["tmp"], "tile.cfg.bak", old, later)
