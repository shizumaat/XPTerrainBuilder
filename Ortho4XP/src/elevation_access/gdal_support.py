"""GDAL, imported once: ``gdal``, ``ogr``, ``osr`` and whether they exist.

Every module that touches a raster takes its GDAL names from here, so
the "raise instead of returning ``None``" switch is thrown exactly once
and an engine without GDAL answers ``has_gdal = False`` instead of
failing at import.
"""

from typing import Any

__all__ = ["gdal", "has_gdal", "ogr", "osr"]

gdal: Any = None
ogr: Any = None
osr: Any = None

try:
    from osgeo import gdal, ogr, osr

    has_gdal: bool = True
    gdal.UseExceptions()
    ogr.UseExceptions()
    osr.UseExceptions()
except Exception:
    has_gdal = False
