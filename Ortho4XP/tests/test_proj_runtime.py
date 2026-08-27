"""PROJ runtime pinning, self-check and build gate.

Headless and offline (docs/specs/proj-runtime-robustness-spec.md §5.1): the
bundle layouts are fake ``tmp_path`` trees, and the only real library work is
one EPSG transform inside the venv's own pyproj.
"""

from __future__ import annotations

import os
import types
from pathlib import Path

import pytest

import O4_Proj_Runtime as PROJRT

_ENV_VARS = (
    "PROJ_LIB",
    "PROJ_DATA",
    "PROJ_AUX_DB",
    "GDAL_DATA",
    "GDAL_DRIVER_PATH",
    "PROJ_NETWORK",
)


def _fake_bundle(root: Path, pyproj_db: bool, gdal_db: bool) -> str:
    """Build a fake frozen bundle tree; return its ``_MEIPASS`` path."""
    pyproj_dir = root / "pyproj" / "proj_dir" / "share" / "proj"
    gdal_dir = root / "osgeo" / "data" / "proj"
    pyproj_dir.mkdir(parents=True)
    gdal_dir.mkdir(parents=True)
    if pyproj_db:
        (pyproj_dir / "proj.db").write_bytes(b"")
    if gdal_db:
        (gdal_dir / "proj.db").write_bytes(b"")
    return str(root)


# ---------------------------------------------------------------------------
# scrub_proj_env
# ---------------------------------------------------------------------------
def test_scrub_removes_every_hijackable_var(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.setenv(name, "/somewhere/from/the/users/shell")
    PROJRT.scrub_proj_env()
    for name in _ENV_VARS[:-1]:
        assert name not in os.environ
    assert os.environ["PROJ_NETWORK"] == "OFF"


def test_scrub_tolerates_none_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    PROJRT.scrub_proj_env()
    assert os.environ["PROJ_NETWORK"] == "OFF"


# ---------------------------------------------------------------------------
# frozen_proj_dirs
# ---------------------------------------------------------------------------
def test_frozen_dirs_both_databases(tmp_path: Path) -> None:
    meipass = _fake_bundle(tmp_path, pyproj_db=True, gdal_db=True)
    pyproj_dir, gdal_dir = PROJRT.frozen_proj_dirs(meipass)
    assert pyproj_dir == os.path.join(
        meipass, "pyproj", "proj_dir", "share", "proj"
    )
    assert gdal_dir == os.path.join(meipass, "osgeo", "data", "proj")


def test_frozen_dirs_pyproj_only(tmp_path: Path) -> None:
    meipass = _fake_bundle(tmp_path, pyproj_db=True, gdal_db=False)
    pyproj_dir, gdal_dir = PROJRT.frozen_proj_dirs(meipass)
    assert pyproj_dir is not None
    assert gdal_dir is None


def test_frozen_dirs_gdal_only(tmp_path: Path) -> None:
    meipass = _fake_bundle(tmp_path, pyproj_db=False, gdal_db=True)
    pyproj_dir, gdal_dir = PROJRT.frozen_proj_dirs(meipass)
    assert pyproj_dir is None
    assert gdal_dir is not None


def test_frozen_dirs_neither(tmp_path: Path) -> None:
    meipass = _fake_bundle(tmp_path, pyproj_db=False, gdal_db=False)
    assert PROJRT.frozen_proj_dirs(meipass) == (None, None)


# ---------------------------------------------------------------------------
# pin_frozen_proj — the two libraries must land on DIFFERENT databases
# ---------------------------------------------------------------------------
def test_pin_diverges_pyproj_and_gdal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pyproj

    for name in _ENV_VARS:
        monkeypatch.setenv(name, "/somewhere/from/the/users/shell")
    meipass = _fake_bundle(tmp_path, pyproj_db=True, gdal_db=True)
    real_data_dir = pyproj.datadir.get_data_dir()
    try:
        PROJRT.pin_frozen_proj(meipass)
        expected_pyproj = os.path.join(
            meipass, "pyproj", "proj_dir", "share", "proj"
        )
        expected_gdal = os.path.join(meipass, "osgeo", "data", "proj")
        assert os.environ["PROJ_DATA"] == expected_gdal
        assert pyproj.datadir.get_data_dir() == expected_pyproj
    finally:
        pyproj.datadir.set_data_dir(real_data_dir)


def test_pin_without_gdal_leaves_proj_data_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pyproj

    for name in _ENV_VARS:
        monkeypatch.setenv(name, "/somewhere/from/the/users/shell")
    meipass = _fake_bundle(tmp_path, pyproj_db=True, gdal_db=False)
    real_data_dir = pyproj.datadir.get_data_dir()
    try:
        PROJRT.pin_frozen_proj(meipass)
        assert "PROJ_DATA" not in os.environ
    finally:
        pyproj.datadir.set_data_dir(real_data_dir)


# ---------------------------------------------------------------------------
# preflight / refuse_reason
# ---------------------------------------------------------------------------
def test_preflight_is_clean_in_this_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(PROJRT, "PREFLIGHT_ERROR", None, raising=False)
    assert PROJRT.preflight() is None
    assert PROJRT.PREFLIGHT_ERROR is None
    assert PROJRT.refuse_reason() is None


def test_preflight_reports_a_broken_pyproj(monkeypatch: pytest.MonkeyPatch) -> None:
    import pyproj

    monkeypatch.setattr(PROJRT, "PREFLIGHT_ERROR", None, raising=False)

    def broken_from_crs(*args: object, **kwargs: object) -> None:
        raise RuntimeError("proj_create_from_database: layout version mismatch")

    monkeypatch.setattr(pyproj.Transformer, "from_crs", broken_from_crs)
    error = PROJRT.preflight()
    assert error is not None
    assert "proj_create_from_database" in error
    assert "pyproj.__version__" in error
    assert "pyproj.proj_version_str" in error
    assert "pyproj data dir" in error
    assert "sys.frozen" in error
    assert PROJRT.PREFLIGHT_ERROR == error
    assert PROJRT.refuse_reason() == error


def test_preflight_reports_a_broken_gdal(monkeypatch: pytest.MonkeyPatch) -> None:
    osr = pytest.importorskip("osgeo.osr")

    monkeypatch.setattr(PROJRT, "PREFLIGHT_ERROR", None, raising=False)

    class BrokenSpatialReference:
        def ImportFromEPSG(self, code: int) -> int:
            return 1

    monkeypatch.setattr(osr, "SpatialReference", BrokenSpatialReference)
    error = PROJRT.preflight()
    assert error is not None
    assert "ImportFromEPSG(4326) returned 1" in error


# ---------------------------------------------------------------------------
# The build gate
# ---------------------------------------------------------------------------
def test_build_tile_refuses_when_proj_is_broken(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import O4_Tile_Utils as TILE
    import O4_UI_Utils as UI

    monkeypatch.setattr(
        PROJRT, "PREFLIGHT_ERROR", "ERROR: pyproj transform failed", raising=False
    )
    monkeypatch.setattr(UI, "is_working", 0, raising=False)
    # A stub tile suffices: the gate fires before the step reads any of it,
    # and an attribute error would surface as a failure here.
    tile = types.SimpleNamespace(lat=30, lon=31, build_dir=".")
    assert TILE.build_tile(tile) == 0
    assert not UI.is_working
    assert "PROJ runtime is broken" in capsys.readouterr().out


def test_build_tile_gate_is_open_when_proj_is_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import O4_Tile_Utils as TILE

    monkeypatch.setattr(PROJRT, "PREFLIGHT_ERROR", None, raising=False)
    assert TILE._refuse_on_broken_proj() is False
