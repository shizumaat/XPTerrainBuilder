"""Twins of "Use XPTerrainBuilder here" (#2100, owner 2026-11-15T19:19Z):
``O4_World_Pack_Off`` and the engine command ``world_tile_use``.

* off then on is a byte-identical round trip: the placeholder over the
  DSF, the tile's DSF, folders and imagery record kept aside in the pack,
  all of it back on;
* the held-by-X-Plane rule: a tile X-Plane may hold waits
  (``turning_off``) and :func:`world_tile_use.settle` completes it;
* the set persists in the pack (one file);
* a tile off is never published into the pack (a build goes to its kept
  folder; on shows the newest), and no flight, build-ahead job, link or
  follow job works on it.

All on ``tmp_path``; X-Plane reads as not running unless a test says."""
from __future__ import annotations

import json
import os

import O4_DSF_Binary as DSFB
import O4_Scenery_Links as LINKS
import O4_World_Imagery_Record as IREC
import O4_World_Pack as WP
import O4_World_Pack_Off as OFF
import pytest
from o4_engine import flight_manager as FM
from o4_engine import world_commands as WORLD
from o4_engine import world_job_run as JOBRUN
from o4_engine import world_state as WS
from o4_engine import world_tile_use as USE

AGENT = "XPTerrainBuilder 1.0.536 (engine 1.50.1903) [world full]"
TILE = (30, 31)


def _files(pack: str, lat: int, lon: int) -> dict:
    """``{relative path: bytes}`` of the tile's own files in ``pack``."""
    out = {}
    name = WP.tile_name(lat, lon)
    for top in (os.path.join("terrain", name), os.path.join("textures", name),
                IREC.RECORD_DIR):
        root = os.path.join(pack, top)
        for folder, _dirs, files in os.walk(root):
            for file in files:
                path = os.path.join(folder, file)
                with open(path, "rb") as handle:
                    out[os.path.relpath(path, pack)] = handle.read()
    with open(os.path.join(pack, WP.dsf_relpath(lat, lon)), "rb") as handle:
        out["dsf"] = handle.read()
    return out


def _no_record(files: dict) -> dict:
    return {k: v for k, v in files.items() if not k.startswith(IREC.RECORD_DIR)}


def _real_tile(root: str, lat: int, lon: int, tag: bytes = b"",
               staged: bool = False) -> None:
    """A real tile in a pack-shaped ``root``: DSF, .ter, .dds, record (a
    ``staged`` tile's record under the name a publish stages it)."""
    name = WP.tile_name(lat, lon)
    dsf = os.path.join(root, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf), exist_ok=True)
    with open(dsf, "wb") as handle:
        handle.write(DSFB.placeholder_bytes(lat, lon, AGENT) + b"\1" * 8192 + tag)
    for sub, file, body in (("terrain", "a.ter", b"TERRAIN " + tag),
                            ("textures", "a.dds", b"DDS " + tag)):
        os.makedirs(os.path.join(root, sub, name), exist_ok=True)
        with open(os.path.join(root, sub, name, file), "wb") as handle:
            handle.write(body)
    if staged:
        IREC.write_staged(root, {"provider": "BI"})
        return
    record = IREC.record_path(root, lat, lon)
    os.makedirs(os.path.dirname(record), exist_ok=True)
    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"provider": "BI"}, handle)


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Custom Scenery with the World pack: a real tile and a placeholder."""
    scenery = tmp_path / "X-Plane 12" / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    _real_tile(str(pack), *TILE)
    WP.write_placeholder(str(pack), 30, 32)
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: False)
    monkeypatch.setattr(USE, "_CACHE", {"at": -1e18, "names": frozenset()})
    monkeypatch.setattr(WORLD, "scenery_dir_or_default",
                        lambda given="": given or str(scenery))
    return str(scenery), str(pack)


def test_off_then_on_is_a_byte_identical_round_trip(world):
    scenery, pack = world
    before = _files(pack, *TILE)
    done = USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    assert done == {"tile": "+30+031", "use": False, "state": OFF.OFF}
    dsf = os.path.join(pack, WP.dsf_relpath(*TILE))
    assert WP.is_placeholder(dsf)                   # X-Plane's own scenery
    name = WP.tile_name(*TILE)
    for sub in ("terrain", "textures"):
        assert not os.path.exists(os.path.join(pack, sub, name))
    assert not os.path.exists(IREC.record_path(pack, *TILE))
    assert _files(OFF.kept_root(pack, *TILE), *TILE) == before
    # X-Plane reads Earth nav data only: nothing kept is under it
    assert not os.path.relpath(OFF.kept_root(pack, *TILE), pack).startswith(
        "Earth nav data")
    assert WP.world_tiles(pack)[TILE] == OFF.OFF
    assert WP.real_tiles(pack) == {}
    tile = WS.read_tile(scenery, TILE)
    assert tile.state == WS.OFF and tile.provider == "BI"
    assert tile.dsf.startswith(OFF.kept_root(pack, *TILE))
    done = USE.world_tile_use(*TILE, use=True, scenery_dir=scenery)
    assert done["state"] == OFF.ON
    assert _files(pack, *TILE) == before
    assert not os.path.exists(os.path.join(pack, OFF.KEPT_DIR))
    assert not os.path.exists(os.path.join(pack, OFF.SET_FILE))
    assert WP.world_tiles(pack)[TILE] == "full"


def test_a_placeholder_can_be_turned_off_and_nothing_moves(world):
    scenery, pack = world
    assert USE.world_tile_use(30, 32, use=False, scenery_dir=scenery)["state"] == OFF.OFF
    assert WP.world_tiles(pack)[(30, 32)] == OFF.OFF
    assert not os.path.exists(os.path.join(pack, OFF.KEPT_DIR))
    with pytest.raises(ValueError, match="holds no tile"):
        USE.world_tile_use(40, 40, use=False, scenery_dir=scenery)
    assert USE.world_tile_use(30, 32, use=True, scenery_dir=scenery)["state"] == OFF.ON


def test_a_tile_x_plane_may_hold_waits_and_settle_completes_it(world, monkeypatch):
    scenery, pack = world
    before = _files(pack, *TILE)
    monkeypatch.setattr(WORLD, "tile_loaded", lambda *_a, **_k: (lambda la, lo: True))
    done = USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    assert done["state"] == OFF.TURNING_OFF
    assert _files(pack, *TILE) == before            # nothing moved yet
    assert WP.world_tiles(pack)[TILE] == OFF.OFF    # but no job builds it
    assert USE.settle(scenery) == []                # still held
    monkeypatch.setattr(WORLD, "tile_loaded", lambda *_a, **_k: (lambda la, lo: False))
    assert USE.settle(scenery) == [("+30+031", OFF.OFF)]
    assert WP.is_placeholder(os.path.join(pack, WP.dsf_relpath(*TILE)))
    assert _files(OFF.kept_root(pack, *TILE), *TILE) == before
    # on while held: the placeholder names no file, so on goes at once
    monkeypatch.setattr(WORLD, "tile_loaded", lambda *_a, **_k: (lambda la, lo: True))
    assert USE.world_tile_use(*TILE, use=True, scenery_dir=scenery)["state"] == OFF.ON
    assert _files(pack, *TILE) == before


def test_turning_off_then_on_before_x_plane_lets_go_changes_nothing(world, monkeypatch):
    scenery, pack = world
    before = _files(pack, *TILE)
    monkeypatch.setattr(WORLD, "tile_loaded", lambda *_a, **_k: (lambda la, lo: True))
    USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    assert USE.world_tile_use(*TILE, use=True, scenery_dir=scenery)["state"] == OFF.ON
    assert _files(pack, *TILE) == before and OFF.off_tiles(pack) == {}


def test_the_set_persists_in_the_pack(world):
    scenery, pack = world
    USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    with open(os.path.join(pack, OFF.SET_FILE), encoding="utf-8") as handle:
        assert json.load(handle) == {"version": 1, "tiles": {"+30+031": "off"}}
    assert OFF.off_tiles(pack) == {TILE: OFF.OFF}   # a fresh read
    assert USE.off_names() == frozenset({"+30+031"})


def test_a_build_while_off_goes_to_the_kept_folder_and_on_shows_it(world, tmp_path):
    scenery, pack = world
    USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    staged = str(tmp_path / "staged")
    _real_tile(staged, *TILE, tag=b"newer", staged=True)
    newest = _files(staged, *TILE)
    done = WP.swap_in(pack, staged, *TILE, merge=True)
    assert done["kept"] is True and done["stale"] == []
    assert WP.is_placeholder(os.path.join(pack, WP.dsf_relpath(*TILE)))
    kept = _files(OFF.kept_root(pack, *TILE), *TILE)
    assert _no_record(kept) == newest
    assert IREC.read(OFF.kept_root(pack, *TILE), *TILE)["provider"] == "BI"
    # a staged tile of it never waits for X-Plane and is not named
    stage = str(tmp_path / "stage")
    _real_tile(os.path.join(stage, WP.tile_name(*TILE)), *TILE, tag=b"newest",
               staged=True)
    assert WP.swap_staged(pack, stage, lambda la, lo: True) == []
    assert not os.path.exists(os.path.join(stage, WP.tile_name(*TILE)))
    USE.world_tile_use(*TILE, use=True, scenery_dir=scenery)
    with open(os.path.join(pack, WP.dsf_relpath(*TILE)), "rb") as handle:
        assert handle.read().endswith(b"newest")


def test_a_build_while_turning_off_is_the_one_kept(world, tmp_path, monkeypatch):
    scenery, pack = world
    monkeypatch.setattr(WORLD, "tile_loaded", lambda *_a, **_k: (lambda la, lo: True))
    USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    staged = str(tmp_path / "staged")
    _real_tile(staged, *TILE, tag=b"newer", staged=True)
    newest = _files(staged, *TILE)
    WP.swap_in(pack, staged, *TILE)
    monkeypatch.setattr(WORLD, "tile_loaded", lambda *_a, **_k: (lambda la, lo: False))
    USE.settle(scenery)
    kept = _files(OFF.kept_root(pack, *TILE), *TILE)
    assert _no_record(kept) == newest
    assert IREC.read(OFF.kept_root(pack, *TILE), *TILE)["provider"] == "BI"
    assert not os.path.exists(os.path.join(pack, "terrain", WP.tile_name(*TILE)))


def test_no_flight_job_build_ahead_link_or_follow_job_works_on_it(world, tmp_path,
                                                                  monkeypatch):
    scenery, pack = world
    USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    USE.world_tile_use(30, 32, use=False, scenery_dir=scenery)
    for role in ("departure", "destination", "alternate", "enroute"):
        assert FM._job_for(role, OFF.OFF, "drape") is None, role
    assert FM.OFF_KIND == OFF.OFF
    wanted = JOBRUN._Wanted(scenery)
    monkeypatch.setattr(wanted, "_is_external", lambda tile: False)
    assert wanted.kind((30, 32)) == OFF.OFF and not wanted((30, 32))
    # no zOrtho4XP_ link puts it back
    build = tmp_path / "Tiles" / "zOrtho4XP_+30+031"
    build.mkdir(parents=True)
    LINKS.install(30, 31, str(build), scenery)
    assert sorted(os.listdir(scenery)) == [WP.PACK_NAME]
    # the follow job holds it
    assert USE.off_names() == frozenset({"+30+031", "+30+032"})
    from o4_engine import imagery_follow as FOLLOW
    job = FOLLOW.FollowJob.__new__(FOLLOW.FollowJob)
    job.busy = lambda: ()
    assert {"+30+031", "+30+032"} <= job._held()


def test_undo_of_convert_forgets_the_tile(world):
    scenery, pack = world
    from o4_engine import world_migrate as MIGRATE
    USE.world_tile_use(*TILE, use=False, scenery_dir=scenery)
    MIGRATE._give_back(pack, *TILE, "placeholder")
    assert OFF.off_tiles(pack) == {}
    assert not os.path.exists(OFF.kept_root(pack, *TILE))


def test_the_command_and_its_capability_are_registered():
    import inspect

    from o4_engine import events as EV
    from o4_engine import jsonl as JSONL
    assert "world_tile_use" in EV.CAPABILITIES
    assert '"world_tile_use": world_tile_use' in inspect.getsource(JSONL)
