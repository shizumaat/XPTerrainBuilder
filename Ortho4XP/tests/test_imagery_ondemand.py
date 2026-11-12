"""Twins for the on-demand imagery index, the storage cap and the pins
(#1992, local-imagery-cache spec §5, §6, §8 and §14 P2), offline on
synthetic ``textures/`` folders:

* a rebuild restores every column the disk holds (all but
  ``last_near_at``, which takes the rebuild time, and the index-only
  counts);
* a random run of upgrades, downgrades and kills (mid-write, between the
  landing and the index) never leaves a texture name missing or short,
  and a restart brings the index back to the disk;
* the cap holds with 90 / 110 % hysteresis; nothing within 2 x its tier
  distance of the camera is downgraded; pins never; cores only after
  every other row;
* "Update Imagery" on an on-demand and on a pinned tile never deletes a
  texture name; pinning lands the full textures the DDS cache holds;
* the ``imagery`` / ``dds`` caches never delete a sharp texture's
  source or entry, and the ``ondemand`` Storage row is the index's.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import time
import types

import O4_DDS_Cache as DDSC
import O4_DDS_File as DDS
import O4_Disk_Usage as DISK
import O4_File_Names as FNAMES
import O4_Imagery_Freshness as FRESH
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Placeholder as PLACEHOLDER
import O4_Tile_Info as TINFO
import pytest
from o4_engine import imagery_downgrade as DOWNGRADE
from o4_engine import imagery_ondemand as ONDEMAND
from o4_engine import storage as STORAGE

LAT, LON = 60, -136
TILE = FNAMES.short_latlon(LAT, LON)
PROVIDER = "FAKE"
ZL = 16
S = 4740.0                      # a ZL16 square's LOAD_CENTER size at 60 N


def _dds_bytes(width: int, fill: int) -> bytes:
    count = DDS.full_mip_count(width, width)
    levels = [bytes([fill]) * DDS.level_size(w, h, "bc1")
              for (w, h) in DDS.mip_dims(width, width, count)]
    return DDS.assemble(width, width, "bc1", levels)


def _land(path: str, width: int, fill: int) -> None:
    partial = DDS.partial_name(path)
    with open(partial, "wb") as handle:
        handle.write(_dds_bytes(width, fill))
    assert DDS.land(partial, path)


def _name(i: int) -> str:
    return "%d_%d_%s%d.dds" % (18752 + 16 * i, 35552, PROVIDER, ZL)


def _centre(i: int):
    return 60.5, -135.5 + i * (4 * S / 55_000.0)   # ~4 S apart, west to east


def _store_root(tmp):
    return str(tmp / "data" / "Imagery_on_demand" / "placeholders")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """A data root, a DDS cache, and one on-demand tile of ``n`` textures
    as a placeholder build leaves it (512 px, kept in the store)."""
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda relative: str(tmp_path / "data" / relative))
    monkeypatch.setenv("O4_DDS_CACHE_DIR", str(tmp_path / "dds_cache"))
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    monkeypatch.setattr(STORAGE, "_logs_dir", lambda: str(tmp_path / "logs"))
    build = tmp_path / "Tiles" / ("zOrtho4XP_" + TILE)

    def make(n=6, pinned=False):
        (build / "textures").mkdir(parents=True, exist_ok=True)
        (build / "terrain").mkdir(parents=True, exist_ok=True)
        tile = types.SimpleNamespace(lat=LAT, lon=LON)
        for i in range(n):
            name = _name(i)
            lat, lon = _centre(i)
            (build / "terrain" / (name[:-4] + ".ter")).write_text(
                "A\n800\nTERRAIN\n\nLOAD_CENTER %.5f %.5f %d 4096\n"
                "BASE_TEX_NOWRAP ../textures/%s\n" % (lat, lon, S, name),
                encoding="utf-8", newline="\n")
            texture = str(build / "textures" / name)
            _land(texture, 512, 0x11)
            assert PLACEHOLDER.keep(tile, texture)
        (build / ("Ortho4XP_%s_imagery.json" % TILE)).write_text(json.dumps(
            {"on_demand": True, "placeholder_zl": ZL - 3, "pinned": pinned,
             "zoomlevel": ZL, "provider": PROVIDER}),
            encoding="utf-8", newline="\n")
        conn = INDEX.open_index()
        INDEX.rebuild(conn, [(str(build), LAT, LON)],
                      placeholder_root=_store_root(tmp_path))
        return conn
    return types.SimpleNamespace(make=make, build=build, tmp=tmp_path)


def _upgrade(conn, row, width=1024, fill=0x22, fetched_at=0.0, jpeg=None):
    path = INDEX.texture_path(row)
    _land(path, width, fill)
    INDEX.set_state(conn, row["tile"], row["name"], "upgraded", tier_px=width,
                    full_bytes=DISK.counted_once_bytes(path), fetched_at=fetched_at,
                    jpeg_path=jpeg)


def _all_whole(conn) -> bool:
    return all(DDS.is_whole(INDEX.texture_path(r)) for r in INDEX.rows(conn))


# --- the index ------------------------------------------------------------


def test_rebuild_restores_every_column_but_last_near_at(world):
    conn = world.make(4)
    rows = INDEX.rows(conn)
    _upgrade(conn, rows[0], 1024)
    _upgrade(conn, rows[1], 2048, fill=0x33)
    before = INDEX.rows(conn)
    path = INDEX.index_path()
    conn.close()
    os.remove(path)                                  # the index is lost
    conn = INDEX.open_index()
    INDEX.rebuild(conn, [(str(world.build), LAT, LON)], now=1234.0,
                  placeholder_root=_store_root(world.tmp))
    after = INDEX.rows(conn)
    index_only = {"last_near_at", "near_count", "late_count", "jpeg_path",
                  "fetched_at"}
    for old, new in zip(before, after, strict=True):
        assert {k: v for k, v in old.items() if k not in index_only} == \
            {k: v for k, v in new.items() if k not in index_only}
        assert new["last_near_at"] == 1234.0     # nothing downgraded by a loss
    assert after[0]["state"] == "upgraded" and after[0]["tier_px"] == 1024
    assert after[1]["tier_px"] == 2048 and after[2]["state"] == "low"
    assert after[0]["fetched_at"] == pytest.approx(
        os.stat(INDEX.texture_path(after[0])).st_mtime)
    assert all(r["placeholder_path"] for r in after)
    assert after[0]["centre_lat"] == pytest.approx(_centre(0)[0])
    assert after[0]["load_size_m"] == S and after[0]["zl"] == ZL
    assert after[0]["provider"] == PROVIDER


def test_a_rescan_keeps_what_only_the_index_knows(world):
    conn = world.make(2)
    row = INDEX.rows(conn)[0]
    INDEX.set_state(conn, TILE, row["name"], "low", last_near_at=None)
    INDEX.mark_near(conn, TILE, [row["name"]], 5000.0,
                    approaching=[row["name"]])
    INDEX.mark_late(conn, TILE, row["name"])
    INDEX.set_core(conn, TILE, [row["name"]])
    INDEX.rebuild(conn, [(str(world.build), LAT, LON)], now=9999.0)
    again = INDEX.get(conn, TILE, row["name"])
    assert (again["last_near_at"], again["near_count"], again["late_count"],
            again["core"]) == (5000.0, 1, 1, 1)


def test_mark_near_writes_at_most_once_a_minute(world):
    conn = world.make(1)
    name = INDEX.rows(conn)[0]["name"]
    INDEX.set_state(conn, TILE, name, "low", last_near_at=None)
    assert INDEX.mark_near(conn, TILE, [name], 10_000.0) == 1
    assert INDEX.mark_near(conn, TILE, [name], 10_030.0) == 0
    assert INDEX.mark_near(conn, TILE, [name], 10_061.0) == 1


# --- crash safety (spec §4.7, §8) ----------------------------------------


def test_upgrades_downgrades_and_kills_never_leave_a_name_missing(world):
    conn = world.make(5)
    rng = random.Random(1992)
    for step in range(160):
        row = rng.choice(INDEX.rows(conn))
        path = INDEX.texture_path(row)
        kind = rng.choice(("upgrade", "downgrade", "kill_mid_write",
                           "kill_after_land", "kill_mid_downgrade"))
        if kind == "upgrade":
            INDEX.set_state(conn, TILE, row["name"], "upgrading")
            _upgrade(conn, row, rng.choice((1024, 2048)), fill=step % 250)
        elif kind == "downgrade" and row["state"] == "upgraded":
            assert DOWNGRADE._downgrade(conn, row) is not None
        elif kind == "kill_mid_write":
            INDEX.set_state(conn, TILE, row["name"], "upgrading")
            with open(DDS.partial_name(path), "wb") as handle:
                handle.write(_dds_bytes(1024, 0x44)[:50_000])   # killed
        elif kind == "kill_after_land":
            INDEX.set_state(conn, TILE, row["name"], "upgrading")
            _land(path, 2048, 0x55)                  # the index never told
        elif kind == "kill_mid_downgrade" and row["placeholder_path"]:
            DDSC.link_or_copy(row["placeholder_path"], DDS.partial_name(path))
        assert _all_whole(conn), (step, kind)
        if rng.random() < 0.2:                       # the app restarts
            INDEX.reset_upgrading(conn)
            for r in INDEX.rows(conn):
                DDS.sweep_partials(INDEX.texture_path(r))
                facts = INDEX._disk_state(r)
                assert facts is not None
                assert r["state"] != "upgrading"
                assert (r["state"], r["tier_px"]) == facts[:2], (step, r)
    assert _all_whole(conn)


# --- the cap ---------------------------------------------------------------


def _sharp(conn, n_rows=6, width=1024):
    for row in INDEX.rows(conn)[:n_rows]:
        _upgrade(conn, row, width)
    return INDEX.capped_bytes(conn)


def test_hysteresis_90_110(world):
    conn = world.make(6)
    total = _sharp(conn)
    each = total // 6
    cap = int(total / 1.05)                          # at 105 % of the cap
    quiet = DOWNGRADE.sweep(conn, cap, in_session=True, now=1e10)
    assert not quiet["ran"] and quiet["downgraded"] == 0
    launch = DOWNGRADE.sweep(conn, cap, in_session=False, now=1e10)
    assert launch["ran"] and launch["total_after"] <= cap * 0.90
    assert launch["total_after"] > cap * 0.90 - each  # stops at 90 %
    _sharp(conn)
    cap = int(total / 1.12)                          # 112 %: in session too
    busy = DOWNGRADE.sweep(conn, cap, in_session=True, now=1e10)
    assert busy["ran"] and busy["total_after"] <= cap * 0.90
    assert _all_whole(conn)


def test_the_camera_the_hour_and_cores(world):
    conn = world.make(6)
    _sharp(conn)
    rows = INDEX.rows(conn)
    INDEX.set_core(conn, TILE, [rows[5]["name"]])
    now = 1e10
    INDEX.set_state(conn, TILE, rows[3]["name"], "upgraded",
                    fetched_at=now - 60)            # landed a minute ago
    camera = types.SimpleNamespace(lat=rows[0]["centre_lat"],
                                   lon=rows[0]["centre_lon"])
    reach = 2 * INDEX.tier_distance_m(INDEX.get(conn, TILE, rows[0]["name"]))
    near = {r["name"] for r in rows
            if INDEX.distance_m(r, camera.lat, camera.lon) <= reach}
    assert rows[0]["name"] in near and rows[5]["name"] not in near
    out = DOWNGRADE.sweep(conn, 1, camera=camera, now=now)   # cap ~0: all go
    left = {r["name"]: r["state"] for r in INDEX.rows(conn)}
    assert all(left[name] == "upgraded" for name in near)
    assert left[rows[3]["name"]] == "upgraded"               # the hour
    assert out["skipped_near"] == len(near) - (rows[3]["name"] in near)
    assert left[rows[5]["name"]] == "low"                    # core, last
    assert _all_whole(conn)


def test_cores_go_only_after_every_other_row(world):
    conn = world.make(6)
    total = _sharp(conn)
    rows = INDEX.rows(conn)
    INDEX.set_core(conn, TILE, [rows[0]["name"], rows[1]["name"]])
    for i, row in enumerate(rows):
        INDEX.set_state(conn, TILE, row["name"], "upgraded",
                        last_near_at=1000.0 + 100 * i)
    order = [r["name"] for r in INDEX.lru_order(conn)]
    assert order[-2:] == [rows[0]["name"], rows[1]["name"]]
    assert order[:4] == [r["name"] for r in rows[2:]]   # oldest first
    DOWNGRADE.sweep(conn, int(total / 1.5), now=1e10)   # 3 of 6 must go
    left = {r["name"]: r["state"] for r in INDEX.rows(conn)}
    assert left[rows[0]["name"]] == left[rows[1]["name"]] == "upgraded"


def test_favorites_count_and_go_last(world):
    """RULINGS 2026-11-10c (2): favorites are inside the budget, made
    low-res after every other row (cores just before them); the
    hand-made "Make all low-res again" keeps them."""
    conn = world.make(6)
    total = _sharp(conn, 6)
    rows = INDEX.rows(conn)
    INDEX.set_pinned(conn, TILE, True)
    assert INDEX.capped_bytes(conn) == total == INDEX.pinned_bytes(conn)
    assert DOWNGRADE.downgrade_all(conn)["downgraded"] == 0
    assert DOWNGRADE._downgrade(conn, INDEX.rows(conn)[0]) is None  # kept
    for row in rows[:3]:                                     # 3 not favorites
        conn.execute("UPDATE textures SET pinned = 0 WHERE name = ?",
                     (row["name"],))
    INDEX.set_core(conn, TILE, [rows[2]["name"]])
    order = [(r["name"], r["pinned"]) for r in INDEX.lru_order(conn, favorites=True)]
    assert [n for n, _p in order][:3] == [rows[0]["name"], rows[1]["name"],
                                          rows[2]["name"]]   # core third
    assert [p for _n, p in order] == [0, 0, 0, 1, 1, 1]      # favorites last
    out = DOWNGRADE.sweep(conn, int(total / 1.5), now=1e10)  # 3 of 6 go
    left = {r["name"]: r["state"] for r in INDEX.rows(conn)}
    assert out["ran"] and all(left[r["name"]] == "low" for r in rows[:3])
    assert all(left[r["name"]] == "upgraded" for r in rows[3:])
    out = DOWNGRADE.sweep(conn, 1, now=1e10)                 # then favorites
    assert {r["state"] for r in INDEX.rows(conn)} == {"low"}
    assert _all_whole(conn)


def test_the_budget_floor_counts_and_warns(world):
    """The placeholders and DSFs sit in the budget; a budget under them
    is ``over_at_floor`` (the apps warn)."""
    import O4_Imagery_OnDemand_Budget as BUDGET
    conn = world.make(4)
    floor = BUDGET._floor_bytes(conn)
    assert floor > 0
    budget = BUDGET.measure(conn, floor // 2)
    assert budget.fixed == floor and budget.over_at_floor
    sharp = _sharp(conn, 4)
    out = DOWNGRADE.sweep(conn, budget, now=1e10)
    assert out["over_at_floor"] and out["floor_bytes"] == floor
    assert out["total_before"] == floor + sharp
    assert out["total_after"] == floor                       # all low-res
    assert not BUDGET.measure(conn, floor * 2).over_at_floor
    assert [BUDGET._tier_of(r) for r in (
        {"pinned": 0, "core": 0}, {"pinned": 0, "core": 1},
        {"pinned": 1, "core": 1})] == [0, 1, 2]


def test_a_downgrade_frees_the_cache_entry_and_jpeg_and_logs(world):
    conn = world.make(2)
    row = INDEX.rows(conn)[0]
    jpeg = world.tmp / "tier.jpg"
    jpeg.write_bytes(b"x" * 5000)
    _upgrade(conn, row, 1024, jpeg=str(jpeg))
    key = "ab" + "0" * 38
    texture = INDEX.texture_path(row)
    assert DDSC.store(key, texture)
    INDEX.set_state(conn, TILE, row["name"], "upgraded", dds_cache_key=key)
    freed = DOWNGRADE._downgrade(conn, INDEX.get(conn, TILE, row["name"]))
    assert freed and not os.path.exists(DDSC.entry_path(key))
    assert not jpeg.exists()
    assert INDEX.get(conn, TILE, row["name"])["state"] == "low"
    assert DDS.is_whole(texture)
    log = (world.tmp / "logs" / STORAGE.LOG_NAME).read_text(
        encoding="utf-8")
    assert "downgraded" in log and row["name"] in log


def test_a_neighbours_cache_entry_stays(world):
    conn = world.make(1)
    row = INDEX.rows(conn)[0]
    _upgrade(conn, row)
    key = "cd" + "1" * 38
    assert DDSC.store(key, INDEX.texture_path(row))
    other = world.tmp / "Tiles" / "zOrtho4XP_+60-135" / "textures"
    other.mkdir(parents=True)
    _land(str(other / row["name"]), 1024, 0x22)
    DDSC._note_use(key, str(other / row["name"]))
    INDEX.set_state(conn, TILE, row["name"], "upgraded", dds_cache_key=key)
    DOWNGRADE._downgrade(conn, INDEX.get(conn, TILE, row["name"]))
    assert os.path.exists(DDSC.entry_path(key))


# --- storage -----------------------------------------------------------------


def test_caches_never_delete_a_sharp_textures_source(world, monkeypatch):
    conn = world.make(2)
    rows = INDEX.rows(conn)
    jpegs = world.tmp / "Orthophotos"
    jpegs.mkdir(exist_ok=True)
    sharp, plain = jpegs / "sharp.jpg", jpegs / "plain.jpg"
    old = time.time() - 10 * 86400
    for path in (sharp, plain):
        path.write_bytes(b"j" * 1000)
        os.utime(path, (old, old))
    _upgrade(conn, rows[0], jpeg=str(sharp))
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(jpegs))
    store = STORAGE._BY_KIND["imagery"]
    listed = {p: d for p, _st, d in STORAGE._files(store, time.time())}
    assert listed[str(sharp)] is False and listed[str(plain)] is True
    key = "ef" + "2" * 38
    assert DDSC.store(key, INDEX.texture_path(rows[0]))
    INDEX.set_state(conn, TILE, rows[0]["name"], "upgraded", dds_cache_key=key)
    assert DDSC._kept_by_ondemand() == INDEX.protected_cache_keys(conn) == {key}
    assert DDSC.evict(cap=0) == []                   # the sharp entry stays
    assert os.path.exists(DDSC.entry_path(key))
    assert DDSC.evict(cap=0, keep=set()) != []


def test_the_ondemand_storage_row_and_its_clear(world):
    conn = world.make(4)
    _sharp(conn, 3)
    INDEX.set_core(conn, TILE, [INDEX.rows(conn)[0]["name"]])
    conn.close()
    row = STORAGE._measure(STORAGE._BY_KIND[STORAGE.ONDEMAND], time.time())
    assert row["files"] == 3 and row["bytes"] > 0 and row["core_files"] == 1
    assert row["pinned_bytes"] == 0
    dry = STORAGE.storage_clear(kinds=[STORAGE.ONDEMAND], dry_run=True)
    assert dry["kinds"][STORAGE.ONDEMAND] == row["bytes"] and dry["files"] == 3
    done = STORAGE.storage_clear(kinds=[STORAGE.ONDEMAND], confirm=True)
    assert done["files"] == 3
    conn = INDEX.open_index()
    assert INDEX.capped_bytes(conn) == 0 and _all_whole(conn)


# --- commands, pins, Update Imagery -----------------------------------------


@pytest.fixture()
def scanned(world, monkeypatch):
    info = types.SimpleNamespace(build_dir=str(world.build))
    monkeypatch.setattr(TINFO, "tile_info", lambda lat, lon, wd: info)
    monkeypatch.setattr(TINFO, "scan_tiles", lambda wd: {(LAT, LON): info})
    return world


def test_pin_lands_the_full_textures_the_cache_holds(scanned):
    conn = scanned.make(3)
    rows = INDEX.rows(conn)
    full = scanned.tmp / "full.dds"
    full.write_bytes(_dds_bytes(4096, 0x66))
    key = "ab" + "3" * 38
    assert DDSC.store(key, str(full))
    DDSC._note_use(key, INDEX.texture_path(rows[0]))      # built here before
    conn.close()
    out = ONDEMAND.imagery_pin(LAT, LON, "x", pinned=True)
    assert (out["served"], out["to_fetch"], out["pinned"]) == (1, 2, True)
    conn = INDEX.open_index()
    first = INDEX.get(conn, TILE, rows[0]["name"])
    assert first["tier_px"] == 4096 and first["pinned"] == 1
    assert DDS.is_whole(INDEX.texture_path(first))
    record = json.loads((scanned.build / ("Ortho4XP_%s_imagery.json" % TILE))
                        .read_text(encoding="utf-8"))
    assert record["pinned"] is True
    assert ONDEMAND.imagery_pin(LAT, LON, "x", pinned=False)["pinned"] is False
    assert INDEX.capped_bytes(conn) > 0                  # counted again


def test_scan_marks_cores_from_the_graded_airports(scanned, monkeypatch):
    scanned.make(6).close()
    patches = scanned.tmp / "patches"
    patches.mkdir()
    lat, lon = _centre(0)
    (patches / "TEST.graded.json").write_text(json.dumps(
        {"frame": {"origin": [lat, lon]}}), encoding="utf-8", newline="\n")
    monkeypatch.setattr(CORES, "_tile_patch_dir", lambda la, lo: str(patches))
    out = ONDEMAND.imagery_ondemand_scan("x")
    assert out["tiles"] == 1 and out["rows"] == 6 and 0 < out["core_rows"] < 6
    conn = INDEX.open_index()
    first = INDEX.rows(conn)[0]
    assert first["core"] == 1 and CORES.core_tier(first, [("T", lat, lon)]) == 3


def test_downgrade_all_needs_confirm(scanned):
    scanned.make(2).close()
    with pytest.raises(ValueError):
        ONDEMAND.imagery_ondemand_downgrade_all()
    assert ONDEMAND.imagery_ondemand_downgrade_all(dry_run=True)["dry_run"]


@pytest.mark.parametrize("pinned", [False, True])
def test_update_imagery_never_deletes_a_texture_name(world, pinned):
    conn = world.make(3, pinned=pinned)
    rows = INDEX.rows(conn)
    _upgrade(conn, rows[0], 1024)
    key = "ab" + "4" * 38
    assert DDSC.store(key, INDEX.texture_path(rows[0]))
    conn.close()
    providers = {PROVIDER: {"code": PROVIDER, "imagery_dir": "normal"}}
    out = FRESH.discard_tile_imagery(LAT, LON, str(world.build), PROVIDER, ZL,
                                     providers=providers)
    tile = types.SimpleNamespace(lat=LAT, lon=LON, imagery_on_demand=True,
                                 placeholder_zl_drop=3)
    for row in rows:
        path = INDEX.texture_path(row)
        assert DDS.is_whole(path)
        assert PLACEHOLDER.needs_build(tile, path)   # made anew by the rebuild
    assert out["placeholders"] == 3
    assert out["refetch"] == (3 if pinned else 0)
    assert os.path.exists(DDSC.entry_path(key)) is (not pinned)
    conn = INDEX.open_index()
    assert {r["state"] for r in INDEX.rows(conn)} == {"low"}


def test_the_imagery_manifest_keeps_the_pin(tmp_path, monkeypatch):
    import O4_Tile_Utils as TILEU
    tile = types.SimpleNamespace(lat=LAT, lon=LON, build_dir=str(tmp_path),
                                 default_website="X", default_zl=16,
                                 texture_mode="full_ortho",
                                 imagery_on_demand=True, placeholder_zl_drop=3)
    with open(TILEU.imagery_manifest_path(tile), "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump({"pinned": True}, handle)
    monkeypatch.setattr(TILEU, "_mesh_identity", lambda tile: None)
    TILEU._write_imagery_manifest(tile, {}, {})
    assert TILEU.read_imagery_manifest(tile)["pinned"] is True


def test_the_sweep_command_takes_a_cap_and_a_camera(scanned):
    conn = scanned.make(4)
    _sharp(conn, 4)
    for row in INDEX.rows(conn):
        INDEX.set_state(conn, TILE, row["name"], "upgraded", fetched_at=0.0)
    first = INDEX.rows(conn)[0]
    conn.close()
    out = ONDEMAND.imagery_ondemand_sweep(cap_gb=1e-9, camera_lat=first[
        "centre_lat"], camera_lon=first["centre_lon"])
    assert out["ran"] and out["skipped_near"] >= 1 and out["downgraded"] >= 1
    conn = INDEX.open_index()
    assert INDEX.get(conn, TILE, first["name"])["state"] == "upgraded"


def test_a_second_opener_never_drops_the_first_ones_rows(tmp_path, monkeypatch):
    """Convert's workers open a new index at once: the opener that read
    the old schema version first must not drop the table the other has
    created and filled since (ubuntu CI 2026-11-12, a tile's 4 rows gone)."""
    path = str(tmp_path / "index.sqlite")
    real, state = sqlite3.connect, {"armed": True}

    class Conn(sqlite3.Connection):
        def execute(self, sql, *args):
            out = super().execute(sql, *args)
            if state["armed"] and sql == "PRAGMA user_version":
                state["armed"] = False
                stale = out.fetchall()              # this opener's read ...
                first = INDEX.open_index(path)      # ... then the other opens,
                INDEX.upsert(first, {"tile": "+45+007", "name": "a.dds"})
                first.close()                       # writes and leaves
                return types.SimpleNamespace(fetchone=lambda: stale[0])
            return out
    shim = types.SimpleNamespace(**vars(sqlite3))
    shim.connect = lambda p, **kw: real(p, factory=Conn, **kw)
    monkeypatch.setattr(INDEX, "sqlite3", shim)
    conn = INDEX.open_index(path)
    INDEX.upsert(conn, {"tile": "+60-136", "name": "b.dds"})
    assert sorted(r["tile"] for r in INDEX.rows(conn)) == ["+45+007", "+60-136"]
    conn.close()
