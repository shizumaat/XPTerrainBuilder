"""The elevation provider registry does not leak between tests (issue #510).

The polluting sequence, in process: one test parses a scratch ``.elv``
directory (as ``test_arcgis_export_image`` does), the next reads the registry
through the engine's lazy ``if not elevation_providers_dict`` idiom (as
``tools/elevation_gap_census.py`` does) and must find the SHIPPED ladder
root.  The pair is pinned to one xdist worker; file order is run order."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

import O4_Airport_Elevation_Insets as INSETS
from tests import provider_registry_isolation as isolation

ROOT = Path(__file__).resolve().parents[1]
SCRATCH_CODE = "SCRATCHONLY510"


def _scratch_directory(tmp_path):
    (tmp_path / (SCRATCH_CODE + ".elv")).write_text(
        "access_strategy=wcs_kvp\n"
        "wcs_getcoverage_template=https://x.test/wcs?REQUEST=GetCoverage\n",
        encoding="utf-8", newline="\n")
    return str(tmp_path)


@pytest.mark.xdist_group("provider_registry_leak_510")
def test_a_scratch_parse_replaces_the_registry_for_its_own_test(tmp_path):
    registry = INSETS.initialize_elevation_providers_dict(
        _scratch_directory(tmp_path))
    assert set(registry) == {SCRATCH_CODE}
    assert INSETS.elevation_providers_dict is registry


@pytest.mark.xdist_group("provider_registry_leak_510")
def test_the_next_lazy_reader_finds_the_shipped_ladder_root():
    pytest.importorskip("osgeo.gdal")
    spec = importlib.util.spec_from_file_location(
        "gap_census_isolation_twin", ROOT / "tools" / "elevation_gap_census.py")
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    registry = census._engine().elevation_providers_dict
    assert SCRATCH_CODE not in registry
    assert "USGS3DEP" in registry


def test_restore_undoes_a_rebind_an_added_code_and_an_edited_definition(
        tmp_path):
    INSETS.initialize_elevation_providers_dict(
        str(ROOT / "Providers" / "Elevation"))
    found = INSETS.elevation_providers_dict
    codes, root = set(found), dict(found["USGS3DEP"])
    saved = isolation.snapshot()
    found["USGS3DEP"]["priority"] = 999.0
    found[SCRATCH_CODE] = {"access_strategy": "wcs_kvp"}
    assert isolation.restore(saved) is True
    assert set(found) == codes and found["USGS3DEP"] == root

    saved = isolation.snapshot()
    INSETS.initialize_elevation_providers_dict(_scratch_directory(tmp_path))
    assert isolation.restore(saved) is True
    assert INSETS.elevation_providers_dict is found
    assert set(found) == codes
    assert isolation.restore(isolation.snapshot()) is False


def test_restore_without_a_snapshot_returns_the_import_state(monkeypatch):
    stand_in = types.ModuleType(isolation.REGISTRY_MODULE)
    stand_in.elevation_providers_dict = {SCRATCH_CODE: {}}
    monkeypatch.setitem(sys.modules, isolation.REGISTRY_MODULE, stand_in)
    assert isolation.restore(None) is False        # a test's stand-in: untouched
    assert stand_in.elevation_providers_dict == {SCRATCH_CODE: {}}

    monkeypatch.setitem(sys.modules, isolation.REGISTRY_MODULE, INSETS)
    monkeypatch.setattr(INSETS, "elevation_providers_dict", {SCRATCH_CODE: {}})
    assert isolation.restore(None) is True
    assert INSETS.elevation_providers_dict == {}
