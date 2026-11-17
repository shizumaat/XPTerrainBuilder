"""Twins for #2093 (reopened): the app's automatic cleanup never clears
the dev corpus, nor shared data used this week, and a file whose extents
a clone shares still books its allocation as budget progress.

Synthetic, on ``test_storage_settings.root`` (a temp data folder); the
real data repo is never read.  No network, no build."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Disk_Usage as DISK  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
from o4_engine import storage as ST  # noqa: E402
from o4_engine import storage_floor as FLOOR  # noqa: E402
from test_storage_priority import BLOCK, _over, _tile, data  # noqa: E402,F401
from test_storage_settings import _write, root  # noqa: E402,F401


def _corpus_files(root_dir):
    out = []
    for name in FLOOR.CORPUS_DIRS:
        for folder, _dirs, names in os.walk(os.path.join(str(root_dir), name)):
            out += [os.path.join(folder, n) for n in names]
    return sorted(out)


def test_auto_clean_over_budget_spares_a_corpus_data_root(
        data, monkeypatch):  # noqa: F811
    old = _tile(45, 7, 90)
    extract = _write(os.path.join(FNAMES.OSM_dir, "_regional_extracts",
                                  "region.osm.pbf"), BLOCK, 90)
    os.makedirs(os.path.join(str(data), FLOOR.CORPUS_MARKER))
    before = _corpus_files(data)
    assert extract in before and old["elevation"] in before
    _over(monkeypatch, 1 << 40)                     # far below usage
    ST.storage_auto_clean(days=0, caps={})
    assert _corpus_files(data) == before


def test_hand_clear_spares_the_corpus_too(data):  # noqa: F811
    _tile(45, 7, 90)
    os.makedirs(os.path.join(str(data), FLOOR.CORPUS_MARKER))
    before = _corpus_files(data)
    ST.storage_clear(confirm=True)
    assert _corpus_files(data) == before


def test_shared_data_used_this_week_is_not_cleared_by_the_budget(
        data, monkeypatch):  # noqa: F811
    fresh = _write(os.path.join(FNAMES.OSM_dir, "_regional_extracts",
                                "fresh.osm.pbf"), BLOCK, 0.2)
    stale = _write(os.path.join(FNAMES.OSM_dir, "_regional_extracts",
                                "stale.osm.pbf"), BLOCK, 30)
    _over(monkeypatch, 1 << 40)
    ST.storage_auto_clean(days=0, caps={})
    assert os.path.exists(fresh) and not os.path.exists(stale)


def test_a_cloned_file_books_its_allocation_as_budget_progress(
        tmp_path, monkeypatch):
    path = _write(str(tmp_path / "x.osm.pbf"), BLOCK, 30)
    st = os.lstat(path)
    monkeypatch.setattr(DISK, "private_bytes", lambda p: 0)
    assert DISK.freeable_bytes(path, st) == 0       # the Settings figure
    assert DISK.freeable_bytes(path, st, unshared=True) == st.st_blocks * 512
    monkeypatch.setattr(DISK, "private_bytes", lambda p: None)
    assert DISK.freeable_bytes(path, st, unshared=True) == st.st_blocks * 512


def test_zero_private_bytes_stop_the_budget_after_one_file(
        data, monkeypatch):  # noqa: F811
    a = _write(os.path.join(str(data), "tmp", "a.bin"), BLOCK, 40)
    b = _write(os.path.join(str(data), "tmp", "b.bin"), BLOCK, 30)
    monkeypatch.setattr(DISK, "private_bytes", lambda p: 0)
    sweep = ST._Sweep(False, "t", None)
    store = ST._BY_KIND["tmp"]
    freed = ST._evict_rows([(store, p, os.lstat(p)) for p in (a, b)],
                           BLOCK, sweep)
    assert freed >= BLOCK
    assert not os.path.exists(a) and os.path.exists(b)
