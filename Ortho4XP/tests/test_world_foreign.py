"""A World folder that is not the app's own (a link, or a folder whose
real path lies outside Custom Scenery, inside the data folder or inside a
``.harness`` folder) is never offered into, migrated into, installed
into or published into; a real World folder is unchanged.  All on
``tmp_path``; X-Plane reads as not running."""
from __future__ import annotations

import os

import O4_File_Names as FNAMES
import O4_Settings_Model as SM
import O4_Storage_Text as TEXT
import O4_World_Pack as WP
import pytest
from o4_engine import world_commands as WORLD
from o4_engine import world_migrate as MIGRATE


@pytest.fixture
def scenery(tmp_path, monkeypatch):
    folder = tmp_path / "Custom Scenery"
    folder.mkdir()
    (folder / "zOrtho4XP_+45+007" / "Earth nav data").mkdir(parents=True)
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(tmp_path / "x.cfg"))
    monkeypatch.setattr(FNAMES, "current_data_root", lambda: str(tmp_path / "data"))
    for module in (WORLD, MIGRATE):
        monkeypatch.setattr(module, "_xplane_running", lambda: False)
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    return folder


def _kit(root, name="kit"):
    """A World pack made elsewhere (a test kit), with its marker."""
    kit = root / name / WP.PACK_NAME
    (kit / "Earth nav data").mkdir(parents=True)
    (kit / WP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    return kit


def _sentence(target) -> str:
    return TEXT.WORLD_FOREIGN.format(target=os.path.realpath(target))


def test_a_linked_world_folder_is_not_offered(scenery, tmp_path):
    kit = _kit(tmp_path / ".harness" / "frames")
    os.symlink(str(kit), WORLD.pack_dir(str(scenery)))
    done = WORLD.world_onboard(str(scenery))
    assert done["offer"] == 0 and done["created"] is False
    assert done["reason"] == "world_foreign"
    assert done["target"] == os.path.realpath(kit)
    assert done["message"] == _sentence(kit)
    assert not WORLD.managed(str(scenery))                 # builds never publish
    status = WORLD.world_status(str(scenery))
    assert status["state"] == "off" and status["reason"] == _sentence(kit)
    assert sorted(os.listdir(kit)) == ["Earth nav data", WP.MARKER]  # untouched


def test_a_linked_world_folder_refuses_migrate_and_install(scenery, tmp_path):
    kit = _kit(tmp_path)
    os.symlink(str(kit), WORLD.pack_dir(str(scenery)))
    for call in (lambda: MIGRATE.run_command(True, scenery_dir=str(scenery)),
                 lambda: MIGRATE.run_command(False, scenery_dir=str(scenery)),
                 lambda: MIGRATE.run_command(False, True, scenery_dir=str(scenery)),
                 lambda: MIGRATE.migrate(str(scenery), work_dir=str(tmp_path / "w")),
                 lambda: WORLD.world_install(str(scenery))):
        with pytest.raises(ValueError) as refused:
            call()
        assert str(refused.value) == _sentence(kit)
    assert sorted(os.listdir(kit)) == ["Earth nav data", WP.MARKER]
    assert (scenery / "zOrtho4XP_+45+007").is_dir()        # nothing moved
    assert not (scenery / "scenery_packs.ini").exists()    # no row filed


def test_a_broken_link_is_foreign_too(scenery, tmp_path):
    os.symlink(str(tmp_path / "gone"), WORLD.pack_dir(str(scenery)))
    assert WORLD.world_onboard(str(scenery))["reason"] == "world_foreign"
    with pytest.raises(ValueError):
        WORLD.world_install(str(scenery))


def test_a_world_folder_inside_the_data_folder_is_foreign(scenery, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "current_data_root", lambda: str(scenery))
    os.makedirs(WORLD.pack_dir(str(scenery)))
    assert WORLD._foreign_target(str(scenery)) == os.path.realpath(
        WORLD.pack_dir(str(scenery)))


def test_a_real_world_folder_is_unchanged(scenery):
    assert WORLD._foreign_target(str(scenery)) == ""
    first = WORLD.world_onboard(str(scenery))
    assert first == {"created": True, "offer": 1, "restart_needed": False}
    assert WORLD._foreign_target(str(scenery)) == "" and WORLD.managed(str(scenery))
