"""Settings > Storage, the engine half (#1724, ``o4_engine.storage``), on a
synthetic data folder in ``tmp_path`` — never the shared data repo: every
store sized, a KEPT store (tiles, patches) never cleared, nothing deleted
without ``confirm`` or while it may be in flight, the age and size-cap
cleanups, and every deletion logged.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Disk_Usage as DISK  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_OSM_Extracts as OSMX  # noqa: E402
import pytest  # noqa: E402
from o4_engine import library as LIB  # noqa: E402
from o4_engine import storage as ST  # noqa: E402
from o4_engine import storage_redundant as REDUNDANT  # noqa: E402

DAY = 86400.0


def _write(path, size, age_days=0.0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)
    when = time.time() - age_days * DAY
    os.utime(path, (when, when))
    return path


@pytest.fixture
def root(tmp_path, monkeypatch):
    for name in ("O4_DDS_CACHE_DIR", "O4_DSF_CACHE_DIR", "O4_AIRPORT_MOD_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)
    original = FNAMES._data_root_override
    FNAMES.set_data_root(str(tmp_path))
    monkeypatch.setattr(OSMX, "STORE_DIRECTORY",
                        str(tmp_path / "OSM_data" / "_regional_extracts"))
    monkeypatch.setattr(ST, "_settings", lambda: (0.0, {}))
    monkeypatch.setattr(REDUNDANT, "_custom_scenery_dir", lambda: "")
    try:
        yield tmp_path
    finally:
        FNAMES._data_root_override = original
        FNAMES._apply_data_root()


def _rows(out):
    return {row["kind"]: row for row in out["stores"]}


def test_scan_sizes_every_store_and_splits_extracts_from_clips(root):
    _write(str(root / "Orthophotos" / "+40-130" / "a.jpg"), 3000, age_days=10)
    _write(str(root / "OSM_data" / "_regional_extracts" / "alps.osm.pbf"), 700)
    _write(str(root / "OSM_data" / "+45+007" / "tile.osm.bz2"), 40)
    _write(str(root / "Tiles" / "zOrtho4XP_+45+007" / "x.dsf"), 900)
    out = ST.storage_scan()
    rows = _rows(out)
    assert [r["kind"] for r in out["stores"]] == [s.kind for s in ST.STORES]
    assert rows["imagery"]["files"] == 1 and rows["imagery"]["apparent_bytes"] == 3000
    assert rows["osm_extracts"]["apparent_bytes"] == 700
    assert rows["osm"]["apparent_bytes"] == 40          # the extracts are not counted twice
    assert rows["tiles"]["policy"] == ST.KEPT and rows["imagery"]["policy"] == ST.CACHE
    assert rows["imagery"]["last_used"] < time.time() - 9 * DAY
    assert rows["masks"]["files"] == 0 and rows["masks"]["last_used"] is None
    assert out["cache_bytes"] == sum(r["bytes"] for r in out["stores"]
                                     if r["policy"] == ST.CACHE)


def test_a_hard_link_frees_nothing(root):
    entry = _write(str(root / "DDS_cache" / "ab" / "abcd.dds"), 4096, age_days=5)
    os.makedirs(root / "Tiles" / "t" / "textures")
    os.link(entry, str(root / "Tiles" / "t" / "textures" / "a.dds"))
    assert DISK.freeable_bytes(entry) == 0
    assert _rows(ST.storage_scan())["dds"]["bytes"] == 0


def test_clear_refuses_kept_stores_and_needs_confirm(root):
    tile = _write(str(root / "Tiles" / "zOrtho4XP_+45+007" / "x.dsf"), 10, age_days=99)
    patch = _write(str(root / "Patches" / "+40+000" / "+45+007" / "KXXX.patch.osm"),
                   10, age_days=99)
    photo = _write(str(root / "Orthophotos" / "a.jpg"), 10, age_days=99)
    for kind in ("tiles", "patches", "overlays"):
        with pytest.raises(ValueError):
            ST.storage_clear(kinds=[kind], confirm=True)
    with pytest.raises(ValueError, match="confirm"):
        ST.storage_clear(kinds=["imagery"])
    preview = ST.storage_clear(older_than_days=30, dry_run=True)
    assert preview["dry_run"] and preview["files"] == 1 and os.path.exists(photo)
    done = ST.storage_clear(older_than_days=30, confirm=True)       # every cache
    assert done["files"] == 1 and not os.path.exists(photo)
    assert os.path.exists(tile) and os.path.exists(patch)          # never in a bulk clear


def test_clear_keeps_in_flight_protected_and_locked_files(root):
    fresh = _write(str(root / "Elevation_data" / "new.tif"), 10)              # in flight
    cfg = _write(str(root / "Elevation_data" / "x.cfg"), 10, age_days=50)
    backup = _write(str(root / "tmp" / "pack.dsf.anchor_bak"), 10, age_days=50)
    _write(str(root / "Airport_mod_cache" / "Pack" / "build.lock"), 1)
    held = _write(str(root / "Airport_mod_cache" / "Pack" / "dump.txt"), 10, age_days=50)
    old = _write(str(root / "Elevation_data" / "old.tif"), 10, age_days=50)
    ST.storage_clear(confirm=True)
    assert not os.path.exists(old)
    for path in (fresh, cfg, backup, held):
        assert os.path.exists(path), path


def test_older_than_keeps_recent_files_and_logs_each_deletion(root):
    old = _write(str(root / "Orthophotos" / "z" / "old.jpg"), 10, age_days=40)
    recent = _write(str(root / "Orthophotos" / "recent.jpg"), 10, age_days=5)
    ST.storage_clear(kinds=["imagery"], older_than_days=30, confirm=True)
    assert not os.path.exists(old) and os.path.exists(recent)
    assert not os.path.exists(os.path.dirname(old))                # emptied folder goes
    log = (root / "logs" / ST.LOG_NAME).read_text(encoding="utf-8")
    assert old in log and "freed" in log and recent not in log


def test_auto_clean_is_off_by_default_and_ages_out_when_on(root):
    old = _write(str(root / "Masks" / "+45+007" / "m.png"), 10, age_days=100)
    assert ST.storage_auto_clean()["ran"] is False and os.path.exists(old)
    out = ST.storage_auto_clean(days=90)
    assert out["ran"] and out["kinds"] == {"masks": out["freed_bytes"]}
    assert not os.path.exists(old)


def test_cap_evicts_least_recently_used_first(root):
    paths = [_write(str(root / "OSM_data" / "_regional_extracts" / f"r{i}.osm.pbf"),
                    1000, age_days=10 - i) for i in range(4)]
    sizes = [DISK.freeable_bytes(p) for p in paths]
    cap = sum(sizes[2:])                       # room for the two newest
    ST.storage_auto_clean(days=0, caps={"osm_extracts": cap})
    assert [os.path.exists(p) for p in paths] == [False, False, True, True]


def test_parse_caps_reads_kinds_and_refuses_kept_or_bad_values():
    assert ST.parse_caps("imagery=100, dds=2.5") == {"imagery": 100 * 10**9,
                                                     "dds": int(2.5e9)}
    assert ST.parse_caps("") == {}
    for bad in ("tiles=10", "nothing=1", "imagery=0", "imagery=lots"):
        with pytest.raises(ValueError):
            ST.parse_caps(bad)


def test_abort_stops_a_sweep(root):
    for i in range(3):
        _write(str(root / "tmp" / f"f{i}"), 10, age_days=50)
    out = ST.storage_clear(kinds=["tmp"], confirm=True, abort=lambda: True)
    assert out["stopped"] and out["files"] == 0


def test_library_start_refuses_clearing_while_building(root):
    with pytest.raises(ValueError, match="build is running"):
        LIB.start(lambda _e: None, "storage_clear", busy=lambda: True, confirm=True)
    with pytest.raises(ValueError, match="confirm"):
        LIB.start(lambda _e: None, "storage_clear", kinds=["tmp"])


def test_auto_clean_drops_texture_copies_their_tiles_hold(root, monkeypatch):
    import O4_DDS_Cache as DDSC
    import O4_DDS_File as DDS
    texture = root / "Tiles" / "zOrtho4XP_+45+007" / "textures" / "a.dds"
    texture.parent.mkdir(parents=True)
    header = DDS.build_header(8, 8, "bc1", 1)
    texture.write_bytes(header + b"U" * (DDS.expected_size(header)
                                         - DDS.HEADER_BYTES))
    with monkeypatch.context() as patch:
        patch.setattr(DDSC.os, "link", lambda *a: (_ for _ in ()).throw(OSError()))
        assert DDSC.store("ab" + "0" * 62, str(texture))
    entry = DDSC.held_by_built_tiles()[0]
    os.utime(entry, (time.time() - 2 * DAY,) * 2)
    out = ST.storage_auto_clean()
    assert out["ran"] and out["kinds"] == {"dds": out["freed_bytes"]}
    assert not os.path.exists(entry) and texture.exists()
    assert os.listdir(os.path.join(DDSC.cache_root(), "_tiles")) == []


def test_auto_clean_drops_caches_of_packs_no_longer_installed(root, monkeypatch):
    scenery = root / "X-Plane" / "Custom Scenery"
    pack = scenery / "Some Airport"
    (pack / "Earth nav data" / "+40+000").mkdir(parents=True)
    dsf = pack / "Earth nav data" / "+40+000" / "+45+007.dsf"
    dsf.write_bytes(b"current dsf")
    (scenery / "Unmounted Pack").symlink_to(root / "nowhere")
    monkeypatch.setattr(REDUNDANT, "_custom_scenery_dir", lambda: str(scenery))
    from auto_patch.dsf_reader import dsf_content_tag
    cache = root / "Airport_mod_cache"
    current = _write(str(cache / "Some Airport" / ("+45+007.dsf.%s.text"
                                                   % dsf_content_tag(str(dsf)))),
                     50, age_days=2)
    old = _write(str(cache / "Some Airport" / "+45+007.dsf.0badc0de.text"), 50,
                 age_days=2)
    stage = _write(str(cache / "Some Airport" / "o4_stage_x_1.cache"), 50, age_days=2)
    kept = _write(str(cache / "Unmounted Pack" / "+1.dsf.00000000.text"), 50,
                  age_days=2)
    gone = [_write(str(cache / name / "+1.dsf.00000000.text"), 50, age_days=2)
            for name in ("Removed Pack",)]
    preview = ST.storage_auto_clean(dry_run=True)
    assert preview["files"] == 2 and os.path.exists(old)
    ST.storage_auto_clean()
    assert [os.path.exists(p) for p in (current, old, stage, kept, *gone)] == [
        True, False, True, True, False]
    assert not os.path.exists(cache / "Removed Pack")


def test_a_custom_scenery_that_matches_few_packs_removes_none(root, monkeypatch):
    scenery = root / "Other X-Plane" / "Custom Scenery"
    scenery.mkdir(parents=True)
    monkeypatch.setattr(REDUNDANT, "_custom_scenery_dir", lambda: str(scenery))
    for name in ("A", "B", "C"):
        _write(str(root / "Airport_mod_cache" / name / "x.dsf.00000000.text"),
               10, age_days=5)
    assert REDUNDANT.airport_pack_leftovers() == []
