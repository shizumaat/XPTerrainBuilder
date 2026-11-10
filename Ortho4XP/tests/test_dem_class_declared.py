"""A provider DECLARES its DEM class (#1929).

``law.tables.flat_source_class`` classes a DEM by its native pixel: at or
under ``lidar_credible_max_m`` (2 m) it is lidar.  ARCTICDEM2M is a 2 m
satellite-stereo DSM (vertical error ~1-4 m, strips that may predate the
airport), so the pixel rule called it lidar -- the old-DEM witness never
fired, ``grade_disagree_m`` took the lidar tolerance, ``runway_profile``
read CASE_LIDAR.  An ``.elv`` ``dem_class=`` key now overrides the pixel
rule; ARCTICDEM2M and NPOLARS0 (#1926) declare ``fine``.  Every other
shipped provider declares nothing, so its class is unchanged (the twin below).  No network,
no corpus: a hand-built ``ProductionDem`` tile carries the manifest.
"""
import json
import os
import types

import O4_Airport_Elevation_Insets as INSETS
import pytest
from auto_patch_v2.airport import dem_production as DP
from auto_patch_v2.law import Law, inset_class
from auto_patch_v2.law import tables as T
from elevation_access.definitions import DEM_CLASS_KEY, DEM_CLASSES, declared_dem_class

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROVIDERS = os.path.normpath(
    os.path.join(_HERE, "..", "Providers", "Elevation"))

#: The providers that declare a class, and the class.  A provider added
#: here is a deliberate change of its class for every consumer of
#: ``law/inset_class`` (census in the #1929 lane report).
DECLARED = {"ARCTICDEM2M": T.FLAT_CLASS_FINE,
            # #1926: NPI S0 photogrammetric DTM, 2.5-5 m pixel -- "fine"
            # by its pixel too, declared so no future pixel reads lidar.
            "NPOLARS0": T.FLAT_CLASS_FINE}


@pytest.fixture
def shipped():
    INSETS.initialize_elevation_providers_dict(_PROVIDERS)
    yield INSETS.elevation_providers_dict
    INSETS.initialize_elevation_providers_dict(_PROVIDERS)


@pytest.fixture
def law():
    return Law.for_airport("ZZZZ")


def test_the_vocabulary_is_the_laws_source_classes():
    assert set(DEM_CLASSES) == {T.FLAT_CLASS_LIDAR, T.FLAT_CLASS_FINE,
                                T.FLAT_CLASS_COARSE}
    assert declared_dem_class(" Fine ") == "fine"
    assert declared_dem_class("dsm") is None
    assert declared_dem_class(None) is None


def test_only_the_declared_providers_carry_a_class(shipped):
    """THE TWIN: no other shipped provider declares a class, so every
    other provider is classed by its pixel exactly as before."""
    declared = {code: d[DEM_CLASS_KEY] for (code, d) in shipped.items()
                if DEM_CLASS_KEY in d}
    assert declared == DECLARED


def test_an_unknown_class_is_dropped_and_the_pixel_rule_stands(tmp_path):
    (tmp_path / "XDSM.elv").write_text(
        "role=airport_inset\naccess_strategy=wcs\nnative_resolution_m=2\n"
        "dem_class=dsm\n", encoding="utf-8", newline="\n")
    parsed = INSETS.initialize_elevation_providers_dict(str(tmp_path))
    assert DEM_CLASS_KEY not in parsed["XDSM"]
    INSETS.initialize_elevation_providers_dict(_PROVIDERS)


def _dem(entries, icao="ZZZZ"):
    dem = object.__new__(DP.ProductionDem)
    dem.icao = icao
    dem._out = lambda _m: None
    dem.frame = types.SimpleNamespace(origin=(64.19, -51.68))
    tile = object.__new__(DP._BakedTile)
    tile.inset_provenance = list(entries)
    tile.overlay_provenance = {}
    dem.tile = lambda lat, lon: tile if (lat, lon) == (64, -52) else None
    return dem


def test_a_declared_inset_is_classed_by_its_declaration(law):
    dem = _dem([{"icao": "ZZZZ", "provider": "ARCTICDEM2M",
                 "native_resolution_m": 2, DEM_CLASS_KEY: "fine"}])
    assert dem.declared_source_class() == "fine"
    assert inset_class.dem_source_class(dem, law) == (
        T.FLAT_CLASS_FINE, 2.0, "inset")


def test_an_undeclared_2m_inset_is_still_lidar(law):
    dem = _dem([{"icao": "ZZZZ", "provider": "FINLAND2M",
                 "native_resolution_m": 2}])
    assert dem.declared_source_class() is None
    assert inset_class.dem_source_class(dem, law)[0] == T.FLAT_CLASS_LIDAR


def test_the_class_follows_the_finest_inset_the_pixel_reads(law):
    """Pixel and class describe ONE entry: a declared coarser inset does
    not reclass the finer undeclared one baked beside it."""
    dem = _dem([{"icao": "ZZZZ", "provider": "ARCTICDEM2M",
                 "native_resolution_m": 2, DEM_CLASS_KEY: "fine"},
                {"icao": "ZZZZ", "provider": "LIDAR1M",
                 "native_resolution_m": 1}])
    assert inset_class.dem_source_class(dem, law) == (
        T.FLAT_CLASS_LIDAR, 1.0, "inset")


def test_the_bake_stamps_the_providers_current_class(shipped, tmp_path):
    """The manifest entry carries the class the registry declares now --
    an inset fetched before the declaration is classed by it too."""
    tif = tmp_path / "ZZZZ_arcticdem2m.tif"
    tif.write_bytes(b"\x00")
    (tmp_path / "ZZZZ_arcticdem2m.json").write_text(json.dumps(
        {"provider": "ARCTICDEM2M", "resolution_m": 2.0}),
        encoding="utf-8", newline="")
    entry = INSETS._inset_bake_provenance_entry(str(tif))
    assert entry[DEM_CLASS_KEY] == "fine"
    other = tmp_path / "ZZZZ_finland2m.tif"
    other.write_bytes(b"\x00")
    assert DEM_CLASS_KEY not in INSETS._inset_bake_provenance_entry(
        str(other))
