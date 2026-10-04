"""The ``hgt_archive_drop`` access strategy (:class:`HgtArchiveDropStrategy`).

Manually downloaded .hgt tile archives recycled from a drop folder.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base_tiles import (
    _manual_drop_setup_information,
    base_definition_covers_tile,
    cached_elevation_file_is_valid,
)
from elevation_access.registry import register_access_strategy

__all__ = [
    "HgtArchiveDropStrategy",
]


@register_access_strategy("hgt_archive_drop")
class HgtArchiveDropStrategy:
    """Manually downloaded .hgt tile archives recycled from a drop folder.

    For sources distributed through file-sharing folders with no stable
    per-tile URL scheme (Sonny's LiDAR Digital Terrain Models of Europe,
    published as Google Drive country archives): the user downloads the
    archives once and drops them -- the zip files themselves, or
    already-extracted ``.hgt`` tiles -- into
    ``Elevation_data/<drop_directory_name>/``; ``ensure_tile`` then
    extracts (or copies) the one NxxEyyy.hgt tile it needs to the legacy
    cache path on demand.

    ``covers`` additionally REQUIRES the tile to be locally present
    (cached, dropped bare, or found inside a dropped archive): automatic
    base selection must never pick a manual source whose data the user
    has not downloaded, since a wrong automatic pick means a
    zero-altitude tile.  Explicit selection bypasses coverage as usual
    and prints download instructions when the tile is missing.
    """

    def covers(self, definition, lat, lon):
        if not base_definition_covers_tile(definition, lat, lon):
            return False
        if cached_elevation_file_is_valid(
            self.tile_cache_path(definition, lat, lon)
        ):
            return True
        return self._locate_dropped_tile(definition, lat, lon) is not None

    def download_url(self, definition, lat, lon):
        return None

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.elevation_data(
            definition["legacy_keyword"], lat, lon
        )

    def drop_directory(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition.get("drop_directory_name", definition["code"]),
        )

    def manual_setup_information(self, definition):
        """Model data for the GUI's manual-setup affordance."""
        return _manual_drop_setup_information(
            definition,
            self.drop_directory(definition),
            "archives (zip) or extracted .hgt tiles",
        )

    def _locate_dropped_tile(self, definition, lat, lon):
        """Find one tile among the dropped files.

        Returns ``("hgt", path)`` for a bare .hgt file, ``("zip",
        archive_path, member_name)`` for a member of a dropped zip
        archive, or ``None``.  The match is case-insensitive on the
        ``NxxEyyy.hgt`` basename, whatever folder structure the archive
        carries inside.
        """
        import zipfile

        drop_directory = self.drop_directory(definition)
        if not os.path.isdir(drop_directory):
            return None
        wanted = (FNAMES.hem_latlon(lat, lon) + ".hgt").lower()
        entries = sorted(os.listdir(drop_directory))
        for entry in entries:
            if entry.lower() == wanted:
                return ("hgt", os.path.join(drop_directory, entry))
        for entry in entries:
            if not entry.lower().endswith(".zip"):
                continue
            archive_path = os.path.join(drop_directory, entry)
            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    for member_name in archive.namelist():
                        if os.path.basename(member_name).lower() == wanted:
                            return ("zip", archive_path, member_name)
            except zipfile.BadZipFile:
                UI.vprint(
                    2, "      Skipping the unreadable archive", archive_path
                )
        return None

    def ensure_tile(self, definition, lat, lon, verbose=True):
        import shutil
        import zipfile

        cache_path = self.tile_cache_path(definition, lat, lon)
        if cached_elevation_file_is_valid(cache_path):
            UI.vprint(2, "   Recycling ", cache_path)
            return 1
        located = self._locate_dropped_tile(definition, lat, lon)
        if located is None:
            UI.vprint(
                1,
                "    WARNING : "
                + definition["code"]
                + " is a manual-download source: fetch the archives from "
                + definition.get("download_page", "its download page")
                + " and drop them (zip files or extracted .hgt tiles) into "
                + self.drop_directory(definition)
                + " .",
            )
            return 0
        if not os.path.isdir(os.path.dirname(cache_path)):
            os.makedirs(os.path.dirname(cache_path))
        if located[0] == "hgt":
            UI.vprint(
                1, "    Recycling", located[1], "from the drop folder."
            )
            shutil.copyfile(located[1], cache_path)
            return 1
        (_, archive_path, member_name) = located
        UI.vprint(
            1,
            "    Extracting",
            os.path.basename(member_name),
            "from the dropped archive",
            archive_path,
            ".",
        )
        with zipfile.ZipFile(archive_path, "r") as archive:
            with open(cache_path, "wb") as out:
                out.write(archive.open(member_name, "r").read())
        return 1
