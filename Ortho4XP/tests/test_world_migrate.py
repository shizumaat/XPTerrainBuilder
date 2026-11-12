"""Twins for moving per-tile ortho packs into the World pack (World spec
§13 M1, ``o4_engine.world_migrate``), offline on a synthetic X-Plane
folder in ``tmp_path`` (never the real install):

* a linked tile gets an on-demand copy (P1c) beside Custom Scenery and
  lands in the World pack from it; a local tile lands with its textures
  hard-linked; both verify, and the library and the local folder are
  byte for byte unchanged; the link stays a link; the local folder moves
  out of Custom Scenery into the work folder's ``originals/`` (owner
  2026-11-12T13:42Z) and the index reads it there;
* a link's ``scenery_packs.ini`` row is DISABLED (kept in place), the
  local tile's row is gone, the ini is backed up, the World pack has its
  row;
* a second run is a no-op; a run killed between the swap and the ini
  finishes on the next run; ``revert`` gives everything back;
* refused while X-Plane runs; the dry run writes nothing in the X-Plane
  folder and times a sample;
* a 7z DSF is unpacked (the engine's reader, else 7-Zip).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time

import O4_DDS_File as DDS
import O4_DSF_Binary as DSFB
import O4_DSF_Compress as DSFC
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Overlay_Utils as OVL
import O4_Scenery_Packs as SP
import O4_World_Pack as WP
import pytest
from o4_engine import imagery_convert as ICONV
from o4_engine import world_adopt as ADOPT
from o4_engine import world_commands as WORLD
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_migrate_size as SIZE

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "mesh_dsf", "full_ortho.dsf")
HAS_7Z = OVL.resolve_unzip_cmd() is not None
TEX = "23456_34112_BI16"


def _dds(width: int, seed: int) -> bytes:
    count = DDS.full_mip_count(width, width)
    levels = [bytes((seed + k + i) % 251 for i in range(DDS.level_size(w, h, "bc1")))
              for k, (w, h) in enumerate(DDS.mip_dims(width, width, count))]
    return DDS.assemble(width, width, "bc1", levels)


def _write(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data.encode() if isinstance(data, str) else data)


def _tile(root: str, lat: int, lon: int, *, on_demand: bool) -> str:
    """A built tile folder around the fixture DSF: the two ``.ter`` its
    terrain definitions name, one DDS (with mips) and a border PNG."""
    tile = WP.tile_name(lat, lon)
    folder = os.path.join(root, "zOrtho4XP_" + tile)
    shutil.copyfile(FIXTURE, _mk(os.path.join(folder, WP.dsf_relpath(lat, lon))))
    for ter in (TEX, TEX + "_water_overlay"):
        _write(os.path.join(folder, "terrain", ter + ".ter"),
               f"A\n800\nTERRAIN\n\nLOAD_CENTER {lat}.5 {lon}.5 4744 4096\n"
               f"BASE_TEX_NOWRAP ../textures/{TEX}.dds\n"
               f"BORDER_TEX ../textures/water_transition.png\nWET\n")
    _write(os.path.join(folder, "textures", TEX + ".dds"), _dds(256, lat))
    _write(os.path.join(folder, "textures", "water_transition.png"), b"PNG1")
    _write(os.path.join(folder, f"Ortho4XP_{tile}.cfg"), "zoomlevel=16\n")
    _write(os.path.join(folder, f"Ortho4XP_{tile}_imagery.json"),
           json.dumps({"provider": "BI", "zoomlevel": 16,
                       "on_demand": on_demand}))
    return folder


def _mk(path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _hashes(folder: str) -> dict:
    out = {}
    for root, _dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            if not os.path.isfile(path):        # a dangling link
                continue
            with open(path, "rb") as handle:
                out[os.path.relpath(path, folder).replace(os.sep, "/")] = hashlib.sha256(
                    handle.read()).hexdigest()
    return out


def _rows(scenery: str) -> dict:
    lines, _nl = SP.read_ini_lines(os.path.join(scenery, "scenery_packs.ini"))
    out = {}
    for line in lines:
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].startswith("SCENERY_PACK"):
            out[SP.pack_name_from_ini_path(parts[1])] = parts[0]
    return out


@pytest.fixture()
def xp(tmp_path, monkeypatch):
    """An X-Plane folder: Custom Scenery with a link to a library tile
    (+45+007), a local tile (+46+008), a disabled link (+47+009) and an
    unmounted link (+48+010); a World pack with a placeholder at
    +45+007; a data root and an index."""
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda rel: str(tmp_path / "data" / rel))
    monkeypatch.setattr(CORES, "airport_points", lambda lat, lon: [])
    for module in (ICONV, MIGRATE, WORLD):
        monkeypatch.setattr(module, "_xplane_running", lambda: False)
    # the disk has room: a run skips every tile under RESERVE_BYTES free,
    # and a CI runner's disk (Windows: ~14 GB) has less than that
    monkeypatch.setattr(ADOPT, "room_left", lambda path: 10**13)
    library = str(tmp_path / "Library")
    scenery = tmp_path / "X-Plane" / "Custom Scenery"
    scenery.mkdir(parents=True)
    os.symlink(_tile(library, 45, 7, on_demand=False),
               scenery / "zOrtho4XP_+45+007")
    _tile(str(scenery), 46, 8, on_demand=True)
    os.symlink(_tile(library, 47, 9, on_demand=False),
               scenery / "zOrtho4XP_+47+009")
    os.symlink(str(tmp_path / "Gone" / "zOrtho4XP_+48+010"),
               scenery / "zOrtho4XP_+48+010")
    (scenery / "scenery_packs.ini").write_text(
        "I\n1000 Version\nSCENERY\n\n"
        "SCENERY_PACK Custom Scenery/zOrtho4XP_+45+007/\n"
        "SCENERY_PACK Custom Scenery/zOrtho4XP_+46+008/\n"
        "SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+47+009/\n"
        "SCENERY_PACK Custom Scenery/zOrtho4XP_+48+010/\n",
        encoding="utf-8", newline="\n")
    WORLD.world_install(str(scenery))
    WP.write_placeholders(WORLD.pack_dir(str(scenery)), [(45, 7)])
    return {"scenery": str(scenery), "library": library,
            "pack": WORLD.pack_dir(str(scenery)),
            "index": str(tmp_path / "data" / "index.sqlite"),
            "work": MIGRATE.work_dir_for(str(scenery))}


def test_ini_rows_are_disabled_in_place_and_enabled_again():
    lines = ["I", "SCENERY_PACK Custom Scenery/zOrtho4XP_+45+007/",
             "SCENERY_PACK Custom Scenery/Other/"]
    assert SP.set_rows_enabled(lines, ["zOrtho4XP_+45+007"], False) == \
        ["zOrtho4XP_+45+007"]
    assert lines[1] == "SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+45+007/"
    assert SP.set_rows_enabled(lines, ["zOrtho4XP_+45+007"], False) == []
    assert SP.set_rows_enabled(lines, ["zOrtho4XP_+45+007", "Nope"], True) == \
        ["zOrtho4XP_+45+007"]
    assert lines[1:] == ["SCENERY_PACK Custom Scenery/zOrtho4XP_+45+007/",
                         "SCENERY_PACK Custom Scenery/Other/"]


def test_migrate_moves_link_and_local_tiles_and_keeps_the_sources(xp):
    before = {"lib": _hashes(xp["library"]),
              "local": _hashes(os.path.join(xp["scenery"], "zOrtho4XP_+46+008"))}
    result = MIGRATE.migrate(xp["scenery"], index=xp["index"], workers=2)
    status = {r["name"]: r["status"] for r in result["rows"]}
    assert status == {"zOrtho4XP_+45+007": "migrated",
                      "zOrtho4XP_+46+008": "migrated",
                      "zOrtho4XP_+47+009": "skip: disabled in scenery_packs.ini",
                      "zOrtho4XP_+48+010": "skip: library not mounted"}
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "full", (46, 8): "full"}
    for lat, lon in ((45, 7), (46, 8)):
        assert not WP.verify_tile(xp["pack"], lat, lon)["problems"]
    # the link's textures come from its on-demand copy (no DSF there:
    # the pack has the relaid one); the local tile's are hard links
    kept = os.path.join(xp["work"], "originals", "zOrtho4XP_+46+008")
    assert not os.path.lexists(os.path.join(xp["scenery"],
                                            "zOrtho4XP_+46+008"))
    local_dds = os.path.join(kept, "textures", TEX + ".dds")
    pack_dds = os.path.join(xp["pack"], "textures", "+46+008", TEX + ".dds")
    assert os.stat(local_dds).st_ino == os.stat(pack_dds).st_ino
    lean = os.path.join(xp["work"], "lean", "zOrtho4XP_+45+007")
    assert os.path.isfile(os.path.join(lean, "textures", TEX + ".dds"))
    assert not os.path.exists(os.path.join(lean, "Earth nav data"))
    # sources untouched; the link is still a link onto the library
    assert _hashes(xp["library"]) == before["lib"]
    local_now = _hashes(kept)
    manifest = "Ortho4XP_+46+008_imagery.json"
    assert {k: v for k, v in local_now.items() if k != manifest} == \
        {k: v for k, v in before["local"].items() if k != manifest}
    assert os.path.islink(os.path.join(xp["scenery"], "zOrtho4XP_+45+007"))
    rows = _rows(xp["scenery"])
    assert rows["zOrtho4XP_+45+007"] == "SCENERY_PACK_DISABLED"
    assert "zOrtho4XP_+46+008" not in rows
    assert rows["zOrtho4XP_+48+010"] == "SCENERY_PACK"
    record = MIGRATE.Journal(xp["work"]).get("zOrtho4XP_+46+008")
    assert record["original"] == record["config_dir"] == kept
    assert rows[WP.PACK_NAME] == "SCENERY_PACK"
    assert os.path.isfile(result["ini_backup"])
    # the on-demand index reads and lands textures in the pack
    conn = INDEX.open_index(xp["index"])
    try:
        found = [INDEX.texture_path(r) for r in INDEX.rows(conn)]
    finally:
        conn.close()
    assert found and all(p.startswith(os.path.join(xp["pack"], "textures"))
                         for p in found)
    again = MIGRATE.migrate(xp["scenery"], index=xp["index"])
    assert again["counts"]["migrated"] == 1     # the local folder is gone
    assert all(r.get("action") != "copy" for r in again["rows"])


def test_a_run_killed_after_the_swap_finishes_next_time(xp, monkeypatch):
    real = MIGRATE._set_row

    def killed(*_a, **_k):
        raise OSError("killed")
    monkeypatch.setattr(MIGRATE, "_set_row", killed)
    first = MIGRATE.migrate(xp["scenery"], ["zOrtho4XP_+46+008"],
                            index=xp["index"])
    assert first["counts"] == {"failed": 1}
    journal = MIGRATE.Journal(xp["work"])
    assert journal.get("zOrtho4XP_+46+008")["state"] == "swapped"
    assert WP.world_tiles(xp["pack"])[(46, 8)] == "full"
    monkeypatch.setattr(MIGRATE, "_set_row", real)
    second = MIGRATE.migrate(xp["scenery"], ["zOrtho4XP_+46+008"],
                             index=xp["index"])
    assert second["rows"][0]["action"] == "resume"
    assert second["counts"] == {"migrated": 1}
    assert "zOrtho4XP_+46+008" not in _rows(xp["scenery"])
    assert os.path.isdir(os.path.join(xp["work"], "originals",
                                      "zOrtho4XP_+46+008"))


def test_revert_gives_everything_back(xp):
    ini_before = open(os.path.join(xp["scenery"], "scenery_packs.ini"),
                      encoding="utf-8").read()
    MIGRATE.migrate(xp["scenery"], index=xp["index"])
    done = MIGRATE.revert(xp["scenery"], index=xp["index"])
    assert done["reverted"] == ["zOrtho4XP_+45+007", "zOrtho4XP_+46+008"]
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "placeholder"}
    for sub in ("terrain", "textures"):
        assert os.listdir(os.path.join(xp["pack"], sub)) == []
    rows = _rows(xp["scenery"])
    assert rows["zOrtho4XP_+45+007"] == rows["zOrtho4XP_+46+008"] == "SCENERY_PACK"
    ini_after = open(os.path.join(xp["scenery"], "scenery_packs.ini"),
                     encoding="utf-8").read()
    assert [ln for ln in ini_after.splitlines() if WP.PACK_NAME not in ln] == \
        [ln for ln in ini_before.splitlines() if WP.PACK_NAME not in ln]
    assert MIGRATE.Journal(xp["work"]).records == {}
    manifest = os.path.join(xp["scenery"], "zOrtho4XP_+46+008",
                            "Ortho4XP_+46+008_imagery.json")
    with open(manifest, encoding="utf-8") as handle:
        assert INDEX.LAYOUT_KEY not in json.load(handle)


def test_refused_while_xplane_runs(xp, monkeypatch):
    monkeypatch.setattr(MIGRATE, "_xplane_running", lambda: True)
    with pytest.raises(ValueError, match="Quit X-Plane"):
        MIGRATE.migrate(xp["scenery"])
    with pytest.raises(ValueError, match="Quit X-Plane"):
        MIGRATE.revert(xp["scenery"])


def test_dry_run_writes_nothing_and_times_a_sample(xp, tmp_path):
    xplane = os.path.dirname(xp["scenery"])
    before = (_hashes(xplane), _hashes(xp["library"]))
    result = SIZE.dry_run(xp["scenery"], sample=6,
                          sample_root=str(tmp_path / "sample"))
    assert (_hashes(xplane), _hashes(xp["library"])) == before
    assert not os.path.exists(xp["work"])
    assert os.listdir(tmp_path / "sample") == []
    totals = result["totals"]
    assert totals["by_action"] == {
        "copy": 1, "skip: disabled in scenery_packs.ini": 1,
        "skip: library not mounted": 1, "stage": 1}
    assert totals["dsf_bytes"] == 2 * os.path.getsize(FIXTURE)
    assert totals["linked_texture_bytes"] == 0 and totals["copy_bytes"] > 0
    assert sorted(s["action"] for s in totals["sample"]) == ["copy", "stage"]
    assert all(s["status"] == "migrated" for s in totals["sample"])
    assert set(totals["seconds_per_tile"]) == {"copy", "stage"}


def test_engine_command_completes_through_world_ready(xp):
    events = []
    reply = MIGRATE.start_world_migrate(events.append, request=7,
                                        dry_run=True,
                                        scenery_dir=xp["scenery"])
    assert reply == {"status": "started"}
    deadline = time.monotonic() + 60
    while not any(type(e).__name__ == "WorldReady" for e in events):
        assert time.monotonic() < deadline, "TIMED_OUT"
        time.sleep(0.05)
    ready = next(e for e in events if type(e).__name__ == "WorldReady")
    assert ready.request == 7 and not ready.error
    assert ready.result["totals"]["entries"] == 4
    assert ready.result["summary"].startswith("2 tiles can move")
    assert "rows" not in ready.result and ready.result["failed"] == []
    assert MIGRATE.start_world_migrate(events.append, stop=True) == \
        {"status": "stopping"}


@pytest.mark.skipif(not HAS_7Z, reason="no 7-Zip")
def test_a_compressed_dsf_is_unpacked_before_the_relayout(xp, tmp_path):
    dsf = os.path.join(xp["scenery"], "zOrtho4XP_+46+008",
                       WP.dsf_relpath(46, 8))
    DSFC.compress(dsf, dsf + ".7z")
    os.replace(dsf + ".7z", dsf)
    assert DSFC.is_compressed(dsf)
    result = MIGRATE.migrate(xp["scenery"], ["zOrtho4XP_+46+008"],
                             index=xp["index"])
    assert result["counts"] == {"migrated": 1}
    out = open(os.path.join(xp["pack"], WP.dsf_relpath(46, 8)), "rb").read()
    assert out.startswith(b"XPLNEDSF") and DSFB.dsf_md5_ok(out)
    assert not WP.verify_tile(xp["pack"], 46, 8)["problems"]


@pytest.mark.skipif(not HAS_7Z, reason="no 7-Zip")
def test_unpack_takes_a_7z_the_engine_reader_cannot(tmp_path):
    """An archive with a compressed header (7-Zip's default) is not one
    the pure reader decodes: 7-Zip unpacks it."""
    import subprocess
    member = tmp_path / "+45+007.dsf"
    shutil.copyfile(FIXTURE, member)
    archive = tmp_path / "packed.dsf"
    subprocess.run([OVL.resolve_unzip_cmd(), "a", "-t7z", "-mhc=on", "-bd",
                    "-y", str(archive) + ".7z", str(member)],
                   check=True, capture_output=True)
    os.replace(str(archive) + ".7z", archive)
    out = tmp_path / "out.dsf"
    assert DSFC.unpack(str(archive), str(out)) == os.path.getsize(FIXTURE)
    assert open(out, "rb").read() == open(FIXTURE, "rb").read()
    with pytest.raises(DSFC.CompressError):
        DSFC.unpack(str(tmp_path / "out.dsf.missing"), str(tmp_path / "x"))


FIXTURE_READY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "fixtures", "world", "world_migrate_ready.json")


def test_world_ready_matches_the_shared_swift_fixture(xp):
    """The keys of a dry run's ``WorldReady`` are those of the fixture
    ``WorldWireTests.swift`` decodes (``O4WorldMigrateResult``)."""
    from o4_engine.events import WorldReady
    from o4_engine.jsonl import serialize_event
    result = MIGRATE.run_command(True, scenery_dir=xp["scenery"])
    wire = json.loads(json.dumps(serialize_event(
        WorldReady(request=3, result=result))))
    with open(FIXTURE_READY, encoding="utf-8") as handle:
        fixture = json.load(handle)
    assert set(wire) == set(fixture)
    assert set(wire["result"]) == set(fixture["result"])
    assert set(wire["result"]["totals"]) == set(fixture["result"]["totals"])


def test_the_dry_run_and_the_move_count_their_tiles(xp):
    """Owner 2026-11-11T15:32Z: a bar and a count while it runs.  The
    measure counts every pack and then the timed sample, the move every
    tile; the totals are known at the first event and the last is done."""
    from o4_engine.events import WorldMigrateProgress
    events = []
    MIGRATE.run_command(True, scenery_dir=xp["scenery"], emit=events.append)
    measure = [e for e in events if isinstance(e, WorldMigrateProgress)]
    assert measure and {e.phase for e in measure} == {"measure"}
    assert len({e.total for e in measure}) == 1
    assert measure[0].done == 0 and measure[-1].done == measure[-1].total
    assert measure[-1].total == 4 + 2          # four packs, a sample of two
    assert [e.done for e in measure] == sorted(e.done for e in measure)
    assert any(e.tile.startswith("zOrtho4XP_") for e in measure)
    events.clear()
    MIGRATE.run_command(False, scenery_dir=xp["scenery"], emit=events.append)
    move = [e for e in events if isinstance(e, WorldMigrateProgress)]
    assert move and {e.phase for e in move} == {"move"}
    assert move[-1].done == move[-1].total == 4


def test_cancel_stops_the_dry_run_and_moves_nothing(xp, monkeypatch):
    """Cancel while measuring: the dry run ends with the sentence and no
    sample folder is left; the X-Plane folder is unchanged."""
    before = _hashes(xp["scenery"])
    rows = _rows(xp["scenery"])

    def cancel_at_first(done, total, name):
        if done == 1:
            MIGRATE.stop()
    with pytest.raises(ValueError, match="cancelled"):
        SIZE.dry_run(xp["scenery"], workers=1, progress=cancel_at_first)
    assert _hashes(xp["scenery"]) == before and _rows(xp["scenery"]) == rows
    # The next run starts afresh (Cancel does not stick).
    assert SIZE.dry_run(xp["scenery"], sample=0)["totals"]["entries"] == 4


FIXTURE_PROGRESS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "fixtures", "world",
                                "world_migrate_progress_event.json")


def test_world_migrate_progress_matches_the_shared_swift_fixture():
    """The wire of ``WorldMigrateProgress`` is the fixture
    ``WorldWireTests.swift`` decodes (``O4WorldMigrateProgress``)."""
    from o4_engine.events import WorldMigrateProgress
    from o4_engine.jsonl import serialize_event
    wire = json.loads(json.dumps(serialize_event(WorldMigrateProgress(
        phase="measure", done=3, total=12, tile="zOrtho4XP_+45+007",
        seq=41, ts=1762874400.5))))
    with open(FIXTURE_PROGRESS, encoding="utf-8") as handle:
        assert wire == json.load(handle)
