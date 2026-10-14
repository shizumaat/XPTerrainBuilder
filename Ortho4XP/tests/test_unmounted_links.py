"""Twins for :mod:`O4_Unmounted_Links` (issue #668): a Custom Scenery link
to a drive that is not mounted — detected, worded, and removable.

Every path is under ``tmp_path``; a "/Volumes/<name>" target is simulated
with a missing path whose text starts ``/Volumes/`` (nothing is created
there — the link only names it)."""

import os
import uuid

import pytest

import O4_Tile_Failures as FAIL
import O4_Unmounted_Links as UL
import O4_Unpatched_Airports as UNPATCHED


def _missing_volume_target(name="NoSuchDrive668"):
    # a /Volumes path that is not mounted: unique, never created
    return "/Volumes/%s-%s/Custom Scenery Library/pack" % (
        name, uuid.uuid4().hex[:8])


@pytest.fixture
def scenery(tmp_path):
    custom = tmp_path / "X-Plane 12" / "Custom Scenery"
    custom.mkdir(parents=True)
    return custom


def _present(monkeypatch, *roots):
    """``os.path.exists`` that says only ``roots`` exist (any platform)."""
    monkeypatch.setattr(UL.os.path, "exists", lambda p: p in roots)


def test_volume_named_only_when_the_drive_is_missing(monkeypatch):
    _present(monkeypatch, "/Volumes/Mounted", "C:\\")
    assert UL.volume_of("/Volumes/ThunderBlade/a/b") == "ThunderBlade"
    assert UL.volume_of("/Volumes/Mounted/gone/pack") == ""
    assert UL.volume_of("E:\\Scenery\\pack") == "E:"
    assert UL.volume_of("C:\\Scenery\\gone") == ""       # present drive
    assert UL.volume_of("\\\\?\\F:\\x") == "F:"
    assert UL.volume_of("\\\\?\\C:\\x") == ""
    assert UL.volume_of("/mnt/data/pack") == ""
    assert UL.volume_of("") == ""


def test_extended_length_targets_are_cleaned():
    assert UL.clean_target("\\\\?\\C:\\Users\\x") == "C:\\Users\\x"
    assert UL.clean_target("\\\\?\\UNC\\host\\share\\p") == \
        "\\\\host\\share\\p"
    assert UL.clean_target("/Volumes/D/p") == "/Volumes/D/p"


def test_a_windows_readlink_is_reported_clean(monkeypatch, scenery):
    link = scenery / "pack"
    os.symlink(_missing_volume_target(), link)
    monkeypatch.setattr(UL.os, "readlink",
                        lambda p: "\\\\?\\G:\\Library\\pack")
    found = UL.dangling_link(str(link))
    assert found["target"] == "G:\\Library\\pack"
    assert found["volume"] == ("" if os.path.exists("G:\\") else "G:")
    (entry,) = FAIL.fold([FAIL.record(
        "output_link_unmounted", link=found["link"], target=found["target"],
        volume="")], "+01+001")
    assert "which no longer exists" in entry["why"]       # not "not mounted"
    assert entry["remedy"].startswith("Restore the folder the link points")


def test_dangling_link_to_unmounted_volume(scenery):
    target = _missing_volume_target()
    link = scenery / "zOrtho4XP_-12-078"
    os.symlink(target, link)
    found = UL.dangling_link(str(link))
    assert found["link"] == str(link)
    assert found["target"] == target
    assert found["volume"].startswith("NoSuchDrive668-")
    with pytest.raises(UL.UnmountedLink) as raised:
        UL.check_output(str(link))
    assert FAIL.code_for_exception(raised.value) == "output_link_unmounted"
    assert FAIL.params_for_exception(raised.value)["link"] == str(link)


def test_dangling_link_without_a_volume(tmp_path, scenery):
    link = scenery / "pack"
    os.symlink(str(tmp_path / "gone"), link)
    found = UL.dangling_link(str(link))
    assert found and found["volume"] == ""


def test_a_dangling_parent_is_found(tmp_path):
    custom = tmp_path / "Custom Scenery"
    os.symlink(_missing_volume_target(), custom)
    found = UL.dangling_link(str(custom / "zOrtho4XP_+10+010"))
    assert found and found["link"] == str(custom)


def test_healthy_links_and_plain_folders_are_silent(tmp_path, scenery):
    real = tmp_path / "MountedDrive" / "pack"
    real.mkdir(parents=True)
    link = scenery / "pack"
    os.symlink(str(real), link)
    assert UL.dangling_link(str(link)) is None
    assert UL.dangling_link(str(link / "Earth nav data")) is None
    UL.check_output(str(link))                     # no raise
    assert UL.dangling_link(str(scenery / "not_yet_built")) is None


def test_output_failure_words_name_link_target_and_drive():
    rec = FAIL.record("output_link_unmounted", "detail",
                      link="/X/Custom Scenery/zOrtho4XP_-12-078",
                      target="/Volumes/ThunderBlade/O/zOrtho4XP_-12-078",
                      volume="ThunderBlade")
    (entry,) = FAIL.fold([rec], "-12-078", report_button=True)
    assert entry["what"] == ("Tile -12-078 was not built: its folder in "
                             "Custom Scenery could not be reached.")
    assert "“zOrtho4XP_-12-078”" in entry["why"]
    assert "/Volumes/ThunderBlade/O/zOrtho4XP_-12-078" in entry["why"]
    assert "the drive “ThunderBlade” is not mounted" in entry["why"]
    assert entry["remedy"] == (
        "Mount the drive “ThunderBlade” and build the tile again, or remove "
        "the link to build on this computer's drive.")
    assert entry["link"] == "/X/Custom Scenery/zOrtho4XP_-12-078"


def test_other_failures_carry_no_link():
    (entry,) = FAIL.fold([FAIL.record("disk_full")], "+01+001")
    assert entry["link"] == ""


def _patch(path, icao, apt_dat):
    path.parent.mkdir(parents=True, exist_ok=True)
    quoted = apt_dat.replace(" ", "%20")
    path.write_text("<?xml version='1.0' encoding='UTF-8'?>\n<osm "
                    "version='0.6' o4_icao='%s' o4_apt_dat='%s'>\n</osm>\n"
                    % (icao, quoted), encoding="utf-8", newline="\n")


def test_read_packs_on_an_unmounted_drive_warn(tmp_path, scenery):
    dangling = scenery / "KBLU - Blue Canyon"
    os.symlink(_missing_volume_target("Drive"), dangling)
    real = tmp_path / "Mounted" / "Fine pack"
    (real / "Earth nav data").mkdir(parents=True)
    os.symlink(str(real), scenery / "Fine pack")
    patches = tmp_path / "Patches" / "+30-120" / "+39-121"
    _patch(patches / "KBLU_auto.patch.osm", "KBLU",
           str(dangling / "Earth nav data" / "apt.dat"))
    _patch(patches / "KFIN_auto.patch.osm", "KFIN",
           str(scenery / "Fine pack" / "Earth nav data" / "apt.dat"))
    rows = UL.unmounted_packs(str(patches))
    assert [(r["icao"], r["pack"]) for r in rows] == [
        ("KBLU", "KBLU - Blue Canyon")]
    (entry,) = FAIL.fold(FAIL.from_unmounted(rows), "+39-121", built=True)
    assert entry["what"] == ("Tile +39-121 was built, but airport KBLU was "
                             "graded without the scenery pack “KBLU - Blue "
                             "Canyon”.")
    assert "is not mounted" in entry["why"]
    assert FAIL.UNPATCHED not in entry["why"]      # it HAS a patch
    assert entry["remedy"].startswith("Mount the drive “Drive-")
    assert entry["link"] == ""                     # nothing to remove here
    # the next build regraded KBLU from X-Plane's data: its patch no longer
    # names the pack, and the earlier row carries it while the link dangles
    _patch(patches / "KBLU_auto.patch.osm", "KBLU", "/XP/Global/apt.dat")
    assert [r["icao"] for r in UL.unmounted_packs(str(patches), rows)] == [
        "KBLU"]
    os.unlink(dangling)
    assert UL.unmounted_packs(str(patches), rows) == []


def test_unmounted_rows_ride_the_sidecar(tmp_path):
    class Tile:
        build_dir = str(tmp_path / "tile")
    rows = [{"icao": "KBLU", "pack": "p", "link": "/l", "target": "/t",
             "volume": "V"}]
    UNPATCHED.record_unmounted_packs(Tile(), rows)
    assert UNPATCHED.read_unmounted_packs(Tile()) == rows


# --- the removal command ---------------------------------------------------
def test_remove_link_removes_only_the_dangling_link(scenery):
    link = scenery / "zOrtho4XP_-12-078"
    os.symlink(_missing_volume_target(), link)
    assert UL.remove_link(str(link)) == {"removed": str(link)}
    assert not os.path.lexists(link)


def test_remove_link_refuses_a_folder(scenery):
    folder = scenery / "real pack"
    folder.mkdir()
    with pytest.raises(ValueError, match="not a link"):
        UL.remove_link(str(folder))
    assert folder.is_dir()


def test_remove_link_refuses_a_reachable_target(tmp_path, scenery):
    real = tmp_path / "Mounted" / "pack"
    real.mkdir(parents=True)
    (real / "keep.txt").write_text("x", encoding="utf-8", newline="\n")
    link = scenery / "pack"
    os.symlink(str(real), link)
    with pytest.raises(ValueError, match="reachable"):
        UL.remove_link(str(link))
    assert os.path.islink(link) and (real / "keep.txt").exists()


def test_remove_link_refuses_outside_custom_scenery(tmp_path):
    elsewhere = tmp_path / "Elsewhere"
    elsewhere.mkdir()
    link = elsewhere / "pack"
    os.symlink(_missing_volume_target(), link)
    with pytest.raises(ValueError, match="Custom Scenery"):
        UL.remove_link(str(link))
    assert os.path.islink(link)


def test_remove_link_refuses_nothing_named(scenery):
    with pytest.raises(ValueError):
        UL.remove_link("")
    with pytest.raises(ValueError, match="does not exist"):
        UL.remove_link(str(scenery / "absent"))


def test_command_is_on_the_wire():
    from o4_engine import jsonl
    import inspect
    assert "remove_scenery_link" in inspect.getsource(jsonl._build_handlers)


def test_make_dirs_raises_the_typed_failure(tmp_path, scenery):
    import O4_Config_Utils as CFG
    link = scenery / "zOrtho4XP_+10+010"
    os.symlink(_missing_volume_target(), link)
    tile = CFG.Tile.__new__(CFG.Tile)
    tile.build_dir = str(link)
    with pytest.raises(UL.UnmountedLink):
        tile.make_dirs()
