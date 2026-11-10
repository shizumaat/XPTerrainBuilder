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
    assert TOTAL.hold(ST._Sweep(False, "t", None), time.time()) is None
    assert os.path.exists(old)


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


def test_a_budget_under_the_floor_warns(monkeypatch):
    data = _root()
    _write(str(data / "Tiles" / "zOrtho4XP_+45+007" / "Earth nav data"
                / "+40+000" / "+45+007.dsf"), 9000)
    _budget(monkeypatch, 1000)
    figures = TOTAL.status(ST.storage_scan()["stores"])
    assert figures["under_floor"] and figures["over_budget"]
    assert ST.storage_scan()["budget"]["under_floor"]


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
