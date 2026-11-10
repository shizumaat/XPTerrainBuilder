"""The suite never reaches the owner's real Custom Scenery (#1999).

On 2026-10-26 ``tests/test_qt_activity_keep.py`` left two symlinks,
``zOrtho4XP_+48-006`` and ``zOrtho4XP_+49-006``, in the owner's real
``X-Plane 12/Custom Scenery``, pointing into a pytest temp folder: the Qt
window auto-installed a finished tile into the CONFIGURED install
(``CFG.custom_scenery_dir``, read from the checkout's cfg) through
``os.symlink``, which the install write guard did not patch.  Two closures,
twinned here:

* the write guards (shared repo and X-Plane install, one interceptor)
  refuse the link family — ``os.symlink`` / ``Path.symlink_to`` /
  ``os.link`` — judged on the path the call CREATES;
* ``tests/conftest.py`` points every test's configured Custom Scenery
  (``CFG.custom_scenery_dir`` and the global cfg as ``read_global_raw``
  returns it) at a folder under pytest's basetemp.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import conftest  # noqa: E402


def _fake_install(tmp_path):
    install = tmp_path / "X-Plane 12"
    (install / "Custom Scenery").mkdir(parents=True)
    tile = tmp_path / "Tiles" / "zOrtho4XP_+48-006"
    tile.mkdir(parents=True)
    return install, tile


def test_the_install_guard_REFUSES_a_symlink_into_the_install(tmp_path):
    install, tile = _fake_install(tmp_path)
    link = install / "Custom Scenery" / tile.name
    with conftest._xplane_guard_class()(str(install)):
        with pytest.raises(conftest.XPlaneInstallWriteBlocked) as exc:
            os.symlink(str(tile), str(link), target_is_directory=True)
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            link.symlink_to(tile, target_is_directory=True)
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            os.symlink(src=str(tile), dst=str(link))
    assert "os.symlink" in str(exc.value)
    assert not os.path.lexists(str(link)), "the guard must prevent the link"


def test_the_install_guard_REFUSES_a_hard_link_into_the_install(tmp_path):
    install, tile = _fake_install(tmp_path)
    source = tile / "Earth nav data.txt"
    source.write_text("x", encoding="utf-8", newline="")
    target = install / "Custom Scenery" / "copy.txt"
    with conftest._xplane_guard_class()(str(install)):
        with pytest.raises(conftest.XPlaneInstallWriteBlocked):
            os.link(str(source), str(target))
    assert not target.exists()


def test_a_link_OUTSIDE_the_install_pointing_into_it_stays_free(tmp_path):
    """The first argument is only the link's TARGET text: a scratch link
    that points at an install pack (a test reading pack originals through
    a stand-in folder) creates nothing inside the install."""
    install, _ = _fake_install(tmp_path)
    link = tmp_path / "scratch_link"
    with conftest._xplane_guard_class()(str(install)):
        os.symlink(str(install / "Custom Scenery"), str(link),
                   target_is_directory=True)
    assert link.is_symlink()


def _under(path, base) -> bool:
    return not conftest.scenery_outside_tmp(path, base)


def test_the_configured_custom_scenery_is_under_pytest_tmp(tmp_path_factory):
    """THE LIVE TWIN: every reader of the configured install resolves
    under basetemp inside a running test — whatever the checkout's cfg
    names."""
    import O4_Config_Utils as CFG
    import O4_Settings_Model as SM
    from o4_engine import storage_redundant
    base = tmp_path_factory.getbasetemp()
    readers = {
        "CFG.custom_scenery_dir": CFG.custom_scenery_dir,
        "SM.read_global_raw()": SM.read_global_raw().get(
            "custom_scenery_dir", ""),
        "storage_redundant._custom_scenery_dir()":
            storage_redundant._custom_scenery_dir(),
    }
    outside = {name: value for name, value in readers.items()
               if not _under(value, base)}
    assert not outside, (
        f"configured Custom Scenery resolves outside pytest's tmp "
        f"({base}): {outside}")


def test_a_tile_install_lands_in_the_redirected_folder(tmp_path,
                                                        tmp_path_factory):
    """The incident's own call — ``LINKS.install`` into the configured
    folder — now creates its link under basetemp."""
    import O4_Config_Utils as CFG
    import O4_Scenery_Links as LINKS
    scenery = CFG.custom_scenery_dir
    if not scenery:
        pytest.skip("the checkout's cfg configures no Custom Scenery")
    build = tmp_path / "Tiles"
    (build / LINKS.link_name(48, -6) / "Earth nav data").mkdir(parents=True)
    LINKS.install(48, -6, str(build), scenery)
    link = os.path.join(scenery, LINKS.link_name(48, -6))
    try:
        assert os.path.islink(link)
        assert _under(link, tmp_path_factory.getbasetemp())
    finally:
        if os.path.islink(link):
            os.unlink(link)


def test_a_cfg_file_a_test_writes_keeps_its_own_folder(tmp_path):
    """The redirect rewrites only the checkout's global cfg; a cfg the
    test writes and reads back by path keeps what it wrote."""
    import O4_Settings_Model as SM
    cfg = tmp_path / "XPTerrainBuilder.cfg"
    cfg.write_text("custom_scenery_dir=/X/CS\n", encoding="utf-8",
                   newline="")
    assert SM.read_global_raw(str(cfg))["custom_scenery_dir"] == "/X/CS"
