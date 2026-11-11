"""Twins for the three choices of Convert existing tiles (owner
2026-11-11T15:32Z, RULINGS 2026-11-11l item 4, ``o4_engine.world_retire``
through ``world_migrate``), offline on ``test_world_migrate``'s synthetic
X-Plane folder in ``tmp_path`` (never the real install or a real drive):

* a custom airport tile is a tile holding an airport of an ENABLED
  installed airport pack;
* the dry run gives each choice's figures before anything moves: kept,
  dynamic, bytes this Mac gets back, bytes another drive no longer
  needs, the drives still needed, tiles another tool built;
* keep-custom moves the custom tile as it is and makes the rest dynamic
  (a World pack placeholder, the ini row disabled in place, a link
  removed, a local folder kept); the library is byte for byte unchanged;
* Undo makes the links again and enables the rows; Free space removes
  the local dynamic tiles, which then stay dynamic.
"""
from __future__ import annotations

import os
import sys
import textwrap

import O4_Unmounted_Links as UL
import O4_World_Pack as WP
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_retire as RETIRE
from test_world_migrate import _hashes, _rows, xp  # noqa: F401

APT = textwrap.dedent("""\
    I
    1100 Version
    1 25 0 0 ZZAA Test Field
    1302 icao_code ZZAA
    1302 datum_lat 45.40
    1302 datum_lon 7.60
    """)


def _airport_pack(scenery: str, name: str = "Test Field") -> str:
    nav = os.path.join(scenery, name, "Earth nav data")
    os.makedirs(nav)
    with open(os.path.join(nav, "apt.dat"), "w", encoding="utf-8",
              newline="\n") as handle:
        handle.write(APT)
    return name


def test_a_custom_airport_tile_holds_an_enabled_airport_pack(xp):  # noqa: F811
    assert RETIRE.custom_airport_tiles(xp["scenery"]) == {}
    name = _airport_pack(xp["scenery"])
    assert RETIRE.custom_airport_tiles(xp["scenery"]) == {(45, 7): ["ZZAA"]}
    ini = os.path.join(xp["scenery"], "scenery_packs.ini")
    with open(ini, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"SCENERY_PACK_DISABLED Custom Scenery/{name}/\n")
    assert RETIRE.custom_airport_tiles(xp["scenery"]) == {}


def test_a_drive_is_named_by_its_mount_point(tmp_path):
    assert RETIRE._drive_of(str(tmp_path)) == ""              # this computer
    if sys.platform == "win32":
        system = os.environ.get("SystemDrive", "C:").upper()
        free = next(f"{c}:" for c in "QRSTUVWXYZ" if f"{c}:" != system
                    and not os.path.exists(f"{c}:\\"))
        assert RETIRE._drive_of(f"{free}\\Tiles\\zOrtho4XP_+45+007") == free
        assert RETIRE._drive_of(f"\\\\?\\{free}\\Tiles") == free  # readlink form
        return
    gone = tmp_path / "NoSuchDrive9" / "Tiles" / "zOrtho4XP_+45+007"
    assert RETIRE._drive_of(str(gone)) == "NoSuchDrive9"      # not connected
    if sys.platform == "darwin":
        assert RETIRE._drive_of("/Volumes/NoSuchDrive9/Tiles/zOrtho4XP_+45+007") \
            == "NoSuchDrive9"


def test_the_dry_run_gives_every_choice_before_anything_moves(xp, monkeypatch):  # noqa: F811
    _airport_pack(xp["scenery"])
    real, lib = RETIRE._drive_of, os.path.realpath(xp["library"])
    monkeypatch.setattr(RETIRE, "_drive_of", lambda path: (
        "Library" if path.startswith(lib) else real(path)))
    before = _hashes(os.path.dirname(xp["scenery"]))
    result = MIGRATE.run_command(True, scenery_dir=xp["scenery"])
    assert _hashes(os.path.dirname(xp["scenery"])) == before
    rows = {row["id"]: row for row in result["choices"]}
    assert list(rows) == list(RETIRE.CHOICES)
    library = "Library"
    keep, custom, dynamic = (rows[c] for c in RETIRE.CHOICES)
    # +45+007 (link, custom airport), +46+008 (local), +47+009 (disabled
    # link: left), +48+010 (link to a drive that is not connected)
    assert (keep["kept"], keep["dynamic"], keep["left"]) == (2, 0, 2)
    assert keep["drives_needed"] == {library: 1, "Gone": 1}
    assert keep["freed_bytes"] == 0 and keep["new_bytes"] > 0
    assert (custom["kept"], custom["dynamic"], custom["left"]) == (1, 2, 1)
    assert custom["drives_needed"] == {library: 1}
    assert custom["links_removed"] == 1 and custom["released"] == {"Gone": 0}
    assert custom["freed_bytes"] > 0              # the local tile, after Free space
    assert custom["not_ours"] == 2                # no stamp of this app on either
    assert (dynamic["kept"], dynamic["dynamic"], dynamic["left"]) == (0, 3, 1)
    assert dynamic["drives_needed"] == {}
    assert dynamic["released"][library] > 0
    assert dynamic["line"].endswith("No other drive is needed afterwards.")
    assert "not the same tile" in dynamic["line"]
    assert f"Still needs {library} (1 tile)" in custom["line"]


def test_keep_custom_moves_the_custom_tile_and_makes_the_rest_dynamic(xp):  # noqa: F811
    _airport_pack(xp["scenery"])
    library = _hashes(xp["library"])
    scenery = xp["scenery"]
    result = MIGRATE.migrate(scenery, index=xp["index"], workers=2,
                             choice=RETIRE.KEEP_CUSTOM)
    status = {r["name"]: r["status"] for r in result["rows"]}
    assert status == {"zOrtho4XP_+45+007": "migrated",
                      "zOrtho4XP_+46+008": "dynamic",
                      "zOrtho4XP_+47+009": "skip: disabled in scenery_packs.ini",
                      "zOrtho4XP_+48+010": "dynamic"}
    assert WP.world_tiles(xp["pack"]) == {
        (45, 7): "full", (46, 8): "placeholder", (48, 10): "placeholder"}
    rows = _rows(scenery)
    for name in ("zOrtho4XP_+45+007", "zOrtho4XP_+46+008", "zOrtho4XP_+48+010"):
        assert rows[name] == "SCENERY_PACK_DISABLED", name     # kept in place
    assert os.path.islink(os.path.join(scenery, "zOrtho4XP_+45+007"))
    assert not os.path.lexists(os.path.join(scenery, "zOrtho4XP_+48+010"))
    assert os.path.isdir(os.path.join(scenery, "zOrtho4XP_+46+008"))
    assert _hashes(xp["library"]) == library
    assert "made 2 dynamic" in MIGRATE.summary("migrate", result)
    again = MIGRATE.migrate(scenery, index=xp["index"], choice=RETIRE.DYNAMIC)
    assert {r["name"]: r["status"] for r in again["rows"]}["zOrtho4XP_+46+008"] \
        == "dynamic"
    # Undo: the link again (its target as it was), every row enabled, the
    # placeholders this run wrote removed
    target = os.path.join(os.path.dirname(xp["library"]), "Gone", "zOrtho4XP_+48+010")
    back = MIGRATE.revert(scenery, index=xp["index"])
    assert sorted(back["reverted"]) == ["zOrtho4XP_+45+007", "zOrtho4XP_+46+008",
                                        "zOrtho4XP_+48+010"]
    assert UL.clean_target(os.readlink(os.path.join(scenery, "zOrtho4XP_+48+010"))) \
        == target                    # Windows readlink: the \\?\ form
    rows = _rows(scenery)
    assert all(rows[n] == "SCENERY_PACK" for n in back["reverted"])
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "placeholder"}
    assert _hashes(xp["library"]) == library


def test_everything_dynamic_then_free_space_then_undo(xp):  # noqa: F811
    scenery = xp["scenery"]
    library = _hashes(xp["library"])
    MIGRATE.run_command(False, scenery_dir=scenery, choice=RETIRE.DYNAMIC)
    assert not os.path.lexists(os.path.join(scenery, "zOrtho4XP_+45+007"))
    assert os.path.islink(os.path.join(scenery, "zOrtho4XP_+47+009"))  # disabled: left
    freed = MIGRATE.run_command(False, scenery_dir=scenery, purge=True)
    assert freed["action"] == "free_space" and freed["removed"] == ["zOrtho4XP_+46+008"]
    assert freed["freed_bytes"] > 0
    assert not os.path.exists(os.path.join(scenery, "zOrtho4XP_+46+008"))
    assert _hashes(xp["library"]) == library       # another drive: never touched
    back = MIGRATE.run_command(False, True, scenery_dir=scenery)
    assert back["gone"] == ["zOrtho4XP_+46+008"]
    assert "stay dynamic" in back["summary"]
    assert os.path.islink(os.path.join(scenery, "zOrtho4XP_+45+007"))
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "placeholder",
                                          (46, 8): "placeholder"}


def test_a_half_done_retire_finishes_on_the_next_run(xp):  # noqa: F811
    scenery = xp["scenery"]
    journal = MIGRATE.Journal(xp["work"])
    entry = next(e for e in MIGRATE.entries(scenery) if e.lat == 48)
    journal.set(entry.name, state="retiring", kind=entry.kind,
                source=entry.source, prior=None,
                link_target=os.readlink(entry.path))
    out = MIGRATE.migrate(scenery, names=[entry.name])     # keep_all: still finishes
    assert out["rows"][0]["status"] == "dynamic"
    assert not os.path.lexists(entry.path)
    assert MIGRATE.Journal(xp["work"]).get(entry.name)["state"] == "dynamic"
