"""Allen Coral Atlas bathymetry: the local package library.

The Allen Coral Atlas (allencoralatlas.org, Arizona State University)
publishes 10 m satellite-derived bathymetry for every shallow reef on
Earth under CC-BY 4.0 — exactly the 0-20 m reef-transparency zone the
depth-graded masks need, and the only open source for most Pacific and
Asian reef areas.  Downloads are account-gated (free registration), so
the data cannot be a live ``/vsicurl`` provider (spec section 8):

* **Local library** — the user downloads Atlas packages (zip files with
  ``*bathymetry*.tif`` rasters) and drops them, zipped or extracted,
  into ``Elevation_data/AllenCoralAtlas/``.  :func:`rescan_library`
  indexes every bathymetry raster; the ``coral_atlas_library`` access
  strategy (registered in ``O4_Airport_Elevation_Insets``) serves
  windowed reads from that index like any other bathymetry provider.

The Atlas Terms of Use bar automated retrieval, so the engine never signs in
to the Atlas or downloads from it: the user fetches packages themselves.

DATA FORMAT (verified against Methods-Bathymetry.pdf, 2026-07-16):
16-bit integer GeoTIFF, 10 m resolution, depth in POSITIVE CENTIMETERS
where the bottom is visible in satellite imagery; everything else is
nodata.  The pipeline convention is metres relative to the sea surface,
negative below — :func:`convert_centimeter_depths_to_metres` negates
and scales, mapping non-positive values to the -32768 nodata sentinel.

This is a CORE module: no GUI-toolkit imports (the Qt dialog lives in
``O4_Qt_Coral_Atlas``).
"""

import json
import os
import zipfile
from typing import Callable

import numpy

try:
    from osgeo import gdal, osr

    gdal.UseExceptions()
    osr.UseExceptions()
    has_gdal = True
except ImportError:
    has_gdal = False

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

ATLAS_WEBSITE_URL = "https://allencoralatlas.org/atlas/"
PROVIDER_CODE = "CORALATLAS"
NODATA = -32768.0

# Atlas rasters are 16-bit positive centimetres; anything at or below
# zero is not a measured depth.
CENTIMETERS_PER_METRE = 100.0


def library_directory() -> str:
    """The local Atlas package library (created on demand)."""
    return os.path.join(FNAMES.Elevation_dir, "AllenCoralAtlas")


def library_index_path() -> str:
    return os.path.join(library_directory(), "library_index.json")


def _bounding_box_of_raster(path: str):
    """(west, south, east, north) in EPSG:4326, or None on failure."""
    try:
        dataset = gdal.Open(path)
        transform = dataset.GetGeoTransform()
        west = transform[0]
        north = transform[3]
        east = west + transform[1] * dataset.RasterXSize
        south = north + transform[5] * dataset.RasterYSize
        projection = dataset.GetProjection()
        dataset = None
    except Exception:
        return None
    if projection and "4326" not in projection:
        try:
            source = osr.SpatialReference(wkt=projection)
            target = osr.SpatialReference()
            target.ImportFromEPSG(4326)
            target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            transformation = osr.CoordinateTransformation(source, target)
            (west, south, _) = transformation.TransformPoint(west, south)
            (east, north, _) = transformation.TransformPoint(east, north)
        except Exception:
            return None
    if south > north:
        (south, north) = (north, south)
    return (west, south, east, north)


def _extract_zip_packages(progress: Callable[[str], None]) -> int:
    """Unpack any Atlas zip dropped in the library; returns count."""
    extracted = 0
    for name in sorted(os.listdir(library_directory())):
        if not name.lower().endswith(".zip"):
            continue
        zip_path = os.path.join(library_directory(), name)
        target = os.path.join(library_directory(), name[:-4])
        if os.path.isdir(target):
            continue
        try:
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(target)
            extracted += 1
            progress("   Unpacked Atlas package " + name + ".")
        except Exception as error:
            progress(
                "   WARNING: could not unpack " + name + ": " + str(error)
            )
    return extracted


def rescan_library(
    progress: Callable[[str], None] = lambda message: UI.vprint(1, message)
) -> list:
    """(Re)index every bathymetry raster in the library.

    Unpacks freshly dropped zips first, then walks the library for
    ``*.tif`` files whose name contains ``bathymetry``, records each
    raster's EPSG:4326 bounding box, and persists the index.  Returns
    the index entries (``{"path", "bbox"}``).
    """
    if not has_gdal:
        progress(
            "   INFO: the Allen Coral Atlas library requires the GDAL"
            " python bindings."
        )
        return []
    os.makedirs(library_directory(), exist_ok=True)
    _extract_zip_packages(progress)
    entries = []
    for (directory, _subdirectories, files) in os.walk(library_directory()):
        for name in files:
            if not name.lower().endswith((".tif", ".tiff")):
                continue
            if "bathymetry" not in name.lower():
                continue
            path = os.path.join(directory, name)
            bounding_box = _bounding_box_of_raster(path)
            if bounding_box is None:
                progress(
                    "   WARNING: unreadable raster skipped: " + name
                )
                continue
            entries.append(
                {
                    "path": os.path.relpath(path, library_directory()),
                    "bbox": list(bounding_box),
                }
            )
    with open(library_index_path(), "w", newline="\n") as index_file:
        json.dump({"entries": entries}, index_file, indent=1)
    progress(
        "   Allen Coral Atlas library: "
        + str(len(entries))
        + " bathymetry raster(s) indexed."
    )
    if entries:
        # New data may cover tiles that previously recorded durable
        # no-coverage negatives — drop every bathymetry band stamp so the
        # next masks build re-queries the providers.
        _forget_all_no_coverage_stamps(progress)
    return entries


def _forget_all_no_coverage_stamps(
    progress: Callable[[str], None]
) -> None:
    """Delete every tile's bathymetry-band stamp (cheap; re-created on
    the next build)."""
    import glob

    stamp_paths = glob.glob(
        os.path.join(
            FNAMES.Elevation_dir, "*", "*_bathymetry_band", "index.json"
        )
    )
    for stamp_path in stamp_paths:
        try:
            os.remove(stamp_path)
        except OSError:
            pass
    if stamp_paths:
        progress(
            "   Cleared "
            + str(len(stamp_paths))
            + " tile bathymetry stamp(s); rebuilt tiles will re-check"
            " coverage."
        )


def load_library_index() -> list:
    """The persisted index entries (no rescan)."""
    try:
        with open(library_index_path(), "r") as index_file:
            return json.load(index_file).get("entries", [])
    except (OSError, ValueError):
        return []


def entries_intersecting(bounding_box_wgs84) -> list:
    """Index entries whose bbox intersects (west, south, east, north)."""
    (west, south, east, north) = bounding_box_wgs84[:4]
    matches = []
    for entry in load_library_index():
        (entry_west, entry_south, entry_east, entry_north) = entry["bbox"]
        if not (
            entry_east < west
            or east < entry_west
            or entry_north < south
            or north < entry_south
        ):
            matches.append(
                os.path.join(library_directory(), entry["path"])
            )
    return matches


def convert_centimeter_depths_to_metres(values):
    """Atlas positive centimetres -> pipeline metres (negative down).

    Non-positive values are unmeasured (land, deep, or nodata) and map
    to the -32768 sentinel.
    """
    metres = numpy.where(
        values > 0, -values.astype(numpy.float32) / CENTIMETERS_PER_METRE,
        numpy.float32(NODATA),
    )
    return metres.astype(numpy.float32)


def fetch_window_to_geotiff(
    source_paths,
    bounding_box_wgs84,
    target_resolution_m,
    destination_path,
) -> bool:
    """Mosaic + warp library rasters to a metres float32 window.

    The Atlas-specific replacement for the shared warp helper: the
    sources carry positive centimetres, so the warped window is
    converted with :func:`convert_centimeter_depths_to_metres` before it
    is written.  Returns True on success.
    """
    if not has_gdal:
        return False
    import O4_Geo_Utils as GEO

    (west, south, east, north) = bounding_box_wgs84
    centre_latitude = (south + north) / 2.0
    x_resolution = target_resolution_m / GEO.lon_to_m(centre_latitude)
    y_resolution = target_resolution_m / GEO.lat_to_m
    try:
        warped = gdal.Warp(
            "",
            list(source_paths),
            options=gdal.WarpOptions(
                format="MEM",
                outputType=gdal.GDT_Float32,
                dstSRS="EPSG:4326",
                outputBounds=(west, south, east, north),
                xRes=x_resolution,
                yRes=y_resolution,
                resampleAlg="bilinear",
                srcNodata=0,
                dstNodata=NODATA,
            ),
        )
        if warped is None:
            return False
        values = warped.GetRasterBand(1).ReadAsArray()
        transform = warped.GetGeoTransform()
        warped = None
    except Exception as error:
        UI.vprint(1, "   WARNING: Atlas library warp failed:", str(error))
        return False
    if values is None:
        return False
    metres = convert_centimeter_depths_to_metres(
        numpy.where(values == NODATA, 0, values)
    )
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    output = driver.Create(
        destination_path,
        metres.shape[1],
        metres.shape[0],
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "PREDICTOR=3"],
    )
    output.SetGeoTransform(transform)
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    output.SetProjection(spatial_reference.ExportToWkt())
    band = output.GetRasterBand(1)
    band.WriteArray(metres)
    band.SetNoDataValue(NODATA)
    band.FlushCache()
    output = None
    return True
