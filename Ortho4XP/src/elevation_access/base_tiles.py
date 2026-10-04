"""Whole base tiles: cache validity, coverage and the manual-drop message.

Shared by the four base-tile strategies and the pipeline's base-tile
selection.
"""

import os

from elevation_access.definitions import (
    ROLE_AIRPORT_INSET,
    _parse_float,
    coverage_boxes,
)

__all__ = [
    "DEFERRANTI_ALPHABET",
    "_manual_drop_setup_information",
    "base_definition_covers_tile",
    "cached_elevation_file_is_valid",
    "deferranti_archive_code",
]


# =====================================================================
# Base-tier (role=base) sources -- legacy refactor (spec section 3.6)
# =====================================================================
# The tile-wide "base" elevation sources -- historically a hardcoded
# tuple + if/elif download chain in O4_DEM_Utils.ensure_elevation -- are
# described by the same Providers/Elevation/<CODE>.elv registry, with
# role=base.  Unlike airport insets, base strategies download WHOLE-TILE
# files to the LEGACY cache paths (FNAMES.viewfinderpanorama /
# FNAMES.elevation_data), never to the airport_insets directory, so the
# on-disk cache layout is byte-identical to the historic behaviour.
#
# O4_DEM_Utils.ensure_elevation is now a thin shim over
# ensure_base_tile() below (its signature is unchanged -- the DEM loader,
# the 3x3 combined-raster assembly and the GUI keep calling it with the
# legacy short keywords).

DEFERRANTI_ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def cached_elevation_file_is_valid(cache_path):
    """Is a cached whole-tile elevation file present AND non-empty?

    A bare ``os.path.exists`` recycle check is not enough: an archive
    extraction that died mid-member (upstream CRC corruption, disk
    full, a kill) can leave a zero-byte file, and recycling it silently
    yields a zero-altitude tile.  Every base strategy's recycle test
    goes through here so poisoned caches self-heal on the next build.
    """
    try:
        return os.path.getsize(cache_path) > 0
    except OSError:
        return False


def deferranti_archive_code(lat, lon):
    """The Viewfinderpanoramas letter+number archive code for a tile.

    Exact transliteration of the legacy math (previously inline in
    O4_DEM_Utils.ensure_elevation): column number ``31 + lon // 6``
    zero-padded under 10, row letter from ``lat // 4`` (mirrored and
    prefixed ``S`` south of the equator).
    """
    deferranti_number = 31 + lon // 6
    if deferranti_number < 10:
        deferranti_number = "0" + str(deferranti_number)
    else:
        deferranti_number = str(deferranti_number)
    deferranti_letter = (
        DEFERRANTI_ALPHABET[lat // 4]
        if lat >= 0
        else DEFERRANTI_ALPHABET[(-1 - lat) // 4]
    )
    if lat < 0:
        deferranti_letter = "S" + deferranti_letter
    return deferranti_letter + deferranti_number


def _tile_centre_in_coverage(definition, lat, lon):
    """Does the tile CENTRE fall inside the definition's coverage_bbox?

    Base sources are whole-tile files, so coverage is judged at the tile
    centre (a tile straddling the coverage edge is not a safe automatic
    pick -- the un-covered part would read as nodata/zero).
    """
    boxes = coverage_boxes(definition)
    if not boxes:
        return True
    centre_longitude = lon + 0.5
    centre_latitude = lat + 0.5
    return any(
        west <= centre_longitude <= east
        and south <= centre_latitude <= north
        for (west, south, east, north) in boxes
    )


def base_definition_covers_tile(definition, lat, lon):
    """Full coverage test for a role=base definition at one tile."""
    if not _tile_centre_in_coverage(definition, lat, lon):
        return False
    if (lat, lon) in definition.get("exclude_tiles", ()):
        return False
    zones = definition.get("dem1_zones")
    if zones is not None and deferranti_archive_code(lat, lon) not in zones:
        return False
    return True


def _manual_drop_setup_information(definition, drop_directory, file_kinds):
    """Shared manual-setup entry builder for the drop-folder strategies."""
    already = False
    try:
        already = any(
            entry
            for entry in os.listdir(drop_directory)
            if not entry.startswith(".") and entry != "converted"
        )
    except OSError:
        pass
    resolution = definition.get("native_resolution_m")
    if resolution is None:
        resolution = definition.get("resolution_arc_seconds")
        resolution_text = (
            str(resolution) + " arc-second" if resolution else "unknown"
        )
    else:
        resolution_text = "%g m" % _parse_float(resolution, 0.0)
    return {
        "code": definition["code"],
        "role": definition.get("role", ROLE_AIRPORT_INSET),
        "native_resolution": resolution_text,
        "download_page": definition.get("download_page", ""),
        "drop_directory": drop_directory,
        "already_dropped": already,
        "steps": [
            "Open the download page in your browser and download the "
            + file_kinds
            + " covering your region.",
            "Drop the downloaded files into the folder below "
            "(no unpacking needed).",
            "Rebuild the tile; the data is picked up automatically. "
            "If the tile was already built once, refresh its elevation "
            "insets so cached no-coverage results are re-checked.",
        ],
        "attribution": definition.get("attribution", ""),
        "license": definition.get("license", ""),
    }
