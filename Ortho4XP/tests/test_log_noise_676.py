"""App log noise (#676): readable unnamed-airport labels, no neighbour
``Data*.apt`` write, and the GDAL >= 3.11 in-memory vector driver name."""
import pytest

import sys

sys.path.insert(0, "src")

import numpy


def test_unnamed_airport_label_is_readable():
    import O4_Airport_Utils as APT

    key = (numpy.float64(51.29168617142857), numpy.float64(25.747622028571424))
    assert APT.airport_label(key) == "unnamed airport at 25.7476, 51.2917"
    assert APT.airport_label("OTHH") == "OTHH"
    assert "np.float64" not in APT.position_label(key)


def test_neighbour_dico_is_not_persisted(monkeypatch):
    from types import SimpleNamespace

    import O4_Airport_Apt_Identity as APT_IDENTITY
    import O4_Airport_Utils as APT
    import O4_Vector_Map as VMAP

    saved = []
    for name in ("discover_airport_names", "attach_surfaces_to_airports",
                 "sort_and_reconstruct_runways", "discard_unwanted_airports",
                 "build_hangar_areas", "build_apron_areas",
                 "build_taxiway_areas", "update_airport_boundaries"):
        monkeypatch.setattr(APT, name, lambda *a, **k: None)
    # The apt.dat identity pass (#994) reads the tile's position and the
    # X-Plane airport index: a Tile-shaped stand-in, and no index read.
    monkeypatch.setattr(APT_IDENTITY, "tile_apt_dat_airports",
                        lambda lat, lon, *a, **k: [])
    monkeypatch.setattr(APT, "save_airport_info",
                        lambda tile, dico: saved.append(tile))
    neighbour = SimpleNamespace(lat=41, lon=-88)
    home = SimpleNamespace(lat=41, lon=-87)
    VMAP.build_airports_dico(neighbour, None, persist=False)
    assert saved == []
    VMAP.build_airports_dico(home, None)
    assert saved == [home]


def test_memory_vector_driver_is_not_the_deprecated_name():
    gdal = pytest.importorskip("osgeo.gdal")
    from elevation_access.gdal_support import memory_vector_driver

    driver = memory_vector_driver()
    assert driver is not None
    if int(gdal.VersionInfo()) >= 3110000:
        assert driver.GetName() == "MEM"
