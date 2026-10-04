"""The ``xyz_archive_drop`` access strategy (:class:`XyzArchiveDropStrategy`).

Manually downloaded archives of ASCII-grid elevation sheets.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base_tiles import _manual_drop_setup_information
from elevation_access.definitions import (
    _bounding_boxes_intersect,
    _coverage_bbox_intersects,
    transform_bounding_box_to_epsg,
)
from elevation_access.gdal_support import gdal, has_gdal, osr
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "XyzArchiveDropStrategy",
]


# =====================================================================
# Strategy 7: xyz_archive_drop (manual archives of ASCII grid sheets)
# =====================================================================
@register_access_strategy("xyz_archive_drop")
class XyzArchiveDropStrategy:
    """Manually downloaded archives of ASCII-grid elevation sheets.

    Taiwan's Ministry of the Interior 20 m terrain model is genuinely
    open (Taiwan Open Government Data License) and its INDEX is a
    keyless API -- but the file host (tgos.tw) hard-blocks every
    non-browser client, so the archives must be fetched once by hand
    (the .elv definition's download_page lists them) and dropped into
    ``Elevation_data/<drop_directory_name>/``.

    On first use each dropped zip is extracted and every sheet is
    parsed ONCE: GDAL's XYZ driver reads the ASCII grid (the
    ``xyz_column_order`` definition key handles northing-first files),
    and the sheet is converted to a small GeoTIFF stamped with
    ``source_epsg`` under ``<drop>/converted/``; sheet extents are
    memoised in a per-provider index file.  Airport fetches then warp
    only the intersecting converted sheets -- the ASCII is never
    parsed again.
    """

    def drop_directory(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition.get("drop_directory_name", definition["code"]),
        )

    def index_path(self, definition):
        return os.path.join(
            self.drop_directory(definition), "converted", "index.json"
        )

    def manual_setup_information(self, definition):
        """Model data for the GUI's manual-setup affordance."""
        return _manual_drop_setup_information(
            definition,
            self.drop_directory(definition),
            "county or whole-country archives (zip)",
        )

    def _load_index(self, definition):
        try:
            with open(self.index_path(definition), "r") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def _save_index(self, definition, index):
        os.makedirs(os.path.dirname(self.index_path(definition)), exist_ok=True)
        with open(self.index_path(definition), "w", newline="\n") as handle:
            json.dump(index, handle)

    def _open_ascii_grid(self, definition, sheet_path):
        """Open one extracted sheet through GDAL's XYZ (or native) driver."""
        column_order = str(
            definition.get("xyz_column_order", "AUTO")
        ).upper()
        try:
            return gdal.OpenEx(
                sheet_path,
                allowed_drivers=["XYZ"],
                open_options=["COLUMN_ORDER=" + column_order],
            )
        except Exception:
            pass
        try:
            return gdal.Open(sheet_path)
        except Exception:
            return None

    def _convert_new_archives(self, definition, index):
        """Extract + convert any dropped archive not yet in the index."""
        import zipfile

        drop_directory = self.drop_directory(definition)
        if not os.path.isdir(drop_directory):
            return
        converted_directory = os.path.join(drop_directory, "converted")
        source_epsg = int(float(definition.get("source_epsg", 4326)))
        spatial_reference = osr.SpatialReference()
        spatial_reference.ImportFromEPSG(source_epsg)
        done_archives = index.setdefault("archives", [])
        sheets = index.setdefault("sheets", {})
        # Loose (non-zip) dropped grid files convert the same way --
        # Hamburg publishes its whole-city model as ONE big ASCII file.
        for entry in sorted(os.listdir(drop_directory)):
            if entry in done_archives or not entry.lower().endswith(
                (".xyz", ".txt", ".asc", ".ascii", ".grd", ".tif")
            ):
                continue
            loose_path = os.path.join(drop_directory, entry)
            UI.vprint(
                1,
                "    Converting the dropped elevation file",
                entry,
                "(once; large files take a while).",
            )
            dataset = self._open_ascii_grid(definition, loose_path)
            if dataset is None:
                done_archives.append(entry)
                continue
            converted_directory = os.path.join(drop_directory, "converted")
            os.makedirs(converted_directory, exist_ok=True)
            converted_path = os.path.join(
                converted_directory, entry + ".tif"
            )
            spatial_reference = osr.SpatialReference()
            spatial_reference.ImportFromEPSG(source_epsg)
            try:
                translated = gdal.Translate(
                    converted_path,
                    dataset,
                    format="GTiff",
                    outputType=gdal.GDT_Float32,
                    outputSRS=spatial_reference.ExportToWkt(),
                    creationOptions=["COMPRESS=DEFLATE", "BIGTIFF=IF_SAFER"],
                )
            except Exception as error:
                UI.vprint(
                    1, "   WARNING:", entry, "did not convert:", str(error)
                )
                translated = None
            if translated is not None:
                geotransform = translated.GetGeoTransform()
                x0 = geotransform[0]
                y0 = geotransform[3]
                x1 = x0 + geotransform[1] * translated.RasterXSize
                y1 = y0 + geotransform[5] * translated.RasterYSize
                sheets[converted_path] = [
                    min(x0, x1),
                    min(y0, y1),
                    max(x0, x1),
                    max(y0, y1),
                ]
                translated = None
            dataset = None
            done_archives.append(entry)
        for entry in sorted(os.listdir(drop_directory)):
            if not entry.lower().endswith(".zip") or entry in done_archives:
                continue
            archive_path = os.path.join(drop_directory, entry)
            UI.vprint(
                1,
                "    Converting the dropped elevation archive",
                entry,
                "(once).",
            )
            try:
                archive = zipfile.ZipFile(archive_path, "r")
            except zipfile.BadZipFile:
                UI.vprint(1, "   WARNING: unreadable archive", archive_path)
                done_archives.append(entry)
                continue
            with archive:
                for member in archive.filelist:
                    member_name = os.path.basename(member.filename)
                    if not member_name or member_name.lower().endswith(
                        (".hdr", ".xml", ".pdf", ".doc")
                    ):
                        continue
                    # GeoTIFF members carrying their own CRS (Wallonia's
                    # multi-gigabyte province zips) are indexed IN PLACE
                    # through /vsizip -- no extraction, no conversion.
                    if member_name.lower().endswith((".tif", ".tiff")):
                        vsizip_path = (
                            "/vsizip/" + archive_path + "/" + member.filename
                        )
                        try:
                            in_place = gdal.Open(vsizip_path)
                        except Exception:
                            in_place = None
                        if in_place is not None and in_place.GetProjection():
                            geotransform = in_place.GetGeoTransform()
                            x0 = geotransform[0]
                            y0 = geotransform[3]
                            x1 = x0 + geotransform[1] * in_place.RasterXSize
                            y1 = y0 + geotransform[5] * in_place.RasterYSize
                            sheets[vsizip_path] = [
                                min(x0, x1),
                                min(y0, y1),
                                max(x0, x1),
                                max(y0, y1),
                            ]
                            in_place = None
                            continue
                    scratch_path = os.path.join(
                        converted_directory, member_name + ".scratch"
                    )
                    os.makedirs(converted_directory, exist_ok=True)
                    try:
                        with open(scratch_path, "wb") as out:
                            out.write(archive.open(member, "r").read())
                    except Exception:
                        continue
                    dataset = self._open_ascii_grid(definition, scratch_path)
                    if dataset is None:
                        os.remove(scratch_path)
                        continue
                    converted_path = os.path.join(
                        converted_directory, member_name + ".tif"
                    )
                    try:
                        translated = gdal.Translate(
                            converted_path,
                            dataset,
                            format="GTiff",
                            outputType=gdal.GDT_Float32,
                            # Only ASSIGN a CRS when the sheet has none
                            # of its own (Taiwan's bare grids); sheets
                            # carrying one (Pernambuco spans two UTM
                            # zones) keep it.
                            outputSRS=(
                                None
                                if dataset.GetProjection()
                                else spatial_reference.ExportToWkt()
                            ),
                            creationOptions=["COMPRESS=DEFLATE"],
                        )
                    except Exception as error:
                        UI.vprint(
                            2,
                            "      Sheet",
                            member_name,
                            "did not convert:",
                            str(error),
                        )
                        translated = None
                    if translated is not None:
                        geotransform = translated.GetGeoTransform()
                        x0 = geotransform[0]
                        y0 = geotransform[3]
                        x1 = x0 + geotransform[1] * translated.RasterXSize
                        y1 = y0 + geotransform[5] * translated.RasterYSize
                        sheets[converted_path] = [
                            min(x0, x1),
                            min(y0, y1),
                            max(x0, x1),
                            max(y0, y1),
                        ]
                        translated = None
                    dataset = None
                    os.remove(scratch_path)
            done_archives.append(entry)

    def _bounding_box_in_source_crs(self, definition, bounding_box_wgs84):
        return transform_bounding_box_to_epsg(
            bounding_box_wgs84,
            int(float(definition.get("source_epsg", 4326))),
        )

    def discover(self, definition, bounding_box_wgs84):
        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        index = self._load_index(definition)
        self._convert_new_archives(definition, index)
        self._save_index(definition, index)
        sheets = index.get("sheets") or {}
        if not sheets:
            UI.vprint(
                1,
                "    "
                + definition["code"]
                + " is a manual-download source: fetch the archives from "
                + definition.get("download_page", "its download page")
                + " in a browser and drop the zip files into "
                + self.drop_directory(definition)
                + " .",
            )
            return None
        source_box = self._bounding_box_in_source_crs(
            definition, bounding_box_wgs84
        )
        hits = [
            path
            for (path, extent) in sheets.items()
            if _bounding_boxes_intersect(extent, source_box)
            and (path.startswith("/vsi") or os.path.isfile(path))
        ]
        return [{"path": path} for path in sorted(hits)] or None

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        sources = self.discover(definition, bounding_box_wgs84)
        if not sources:
            return None
        if not warp_vsicurl_sources_to_geotiff(
            [entry["path"] for entry in sources],
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        ):
            return None
        if not _geotiff_has_valid_data(destination_path):
            try:
                os.remove(destination_path)
            except OSError:
                pass
            return None
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [entry["path"] for entry in sources],
            "native_resolution_m": definition.get("native_resolution_m"),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "resolution_m": target_resolution_m,
        }
