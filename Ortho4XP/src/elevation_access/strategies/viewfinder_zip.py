"""Viewfinderpanoramas (J. de Ferranti) zip archives, whole tiles.

The ``viewfinder_zip`` access strategy (:class:`ViewfinderZipStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import os

import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base_tiles import (
    base_definition_covers_tile,
    cached_elevation_file_is_valid,
    deferranti_archive_code,
)
from elevation_access.registry import register_access_strategy

__all__ = [
    "ARCHIVE_MEMBERS_IN_REFUSAL",
    "ViewfinderZipStrategy",
    "refuse_absent_base_archive",
]


#: How many archive member names a refusal lists before eliding.  A
#: de Ferranti zip holds up to 24 .hgt members (a 6x4 degree zone), so
#: the whole manifest fits -- the elision only guards a mis-pointed URL
#: that served some other, huge archive.
ARCHIVE_MEMBERS_IN_REFUSAL = 24


def refuse_absent_base_archive(definition, lat, lon, url, detail):
    """A base source answered "not there" for a tile it SHOULD hold.

    THE LAW (alpha.2 "broken = refuse, never degrade"; issue #121 for
    the transport half, issue #173 for this one): the historic ``return
    0`` made the DEM loader substitute an ALL-ZERO raster for the cell
    and finish the build at 0 m with exit 0.  A 404 on the archive of a
    tile the source covers, or an archive that downloaded but holds no
    member for it, is a MAPPING defect -- the zip name or the member
    name is wrong, or upstream moved -- and the one thing it must never
    do is become a silent zero.

    The discriminator is the land mask the DEM loader already consults
    before it asks for a cell at all (``O4_DEM_Utils.tile_is_land``, the
    ONE predicate): an OCEAN-only tile is lawfully absent and keeps the
    historic 0, a LAND tile refuses the build naming the URL, the tile
    and what came back.
    """
    code = definition.get("code") or "base elevation source"
    cell = "%+03d%+04d" % (lat, lon)
    if not DEM.tile_is_land(lat, lon):
        UI.vprint(
            2,
            "      " + code, "has no archive for the ocean-only cell",
            cell + ";", "it is zero-filled, which is lawful.",
        )
        return 0
    raise DEM.ElevationDownloadRefused(
        "%s has no elevation for the LAND cell %s: %s (%s) -- REFUSING "
        "to build this tile on an all-zero elevation raster.  The cell "
        "is land in Utils/world_tiles.png and this source covers it, so "
        "this is a MAPPING defect (the archive name or the member name), "
        "not missing data; re-run with the URL above to confirm what the "
        "server serves" % (code, cell, url, detail))


@register_access_strategy("viewfinder_zip")
class ViewfinderZipStrategy:
    """Viewfinderpanoramas (J. de Ferranti) zip archives, whole tiles.

    One archive covers several 1x1 degree tiles; download extracts every
    ``.hgt`` member to its own legacy cache path with the historic size
    guard (never overwrite a larger -- i.e. 1 arc-second -- file with a
    smaller 3 arc-second neighbour from a nearby archive).
    """

    def covers(self, definition, lat, lon):
        return base_definition_covers_tile(definition, lat, lon)

    def download_url(self, definition, lat, lon):
        return definition["download_url_template"].replace(
            "{archive_code}", deferranti_archive_code(lat, lon)
        )

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.viewfinderpanorama(lat, lon)

    def ensure_tile(self, definition, lat, lon, verbose=True):
        import io
        import zipfile
        import zlib

        cache_path = self.tile_cache_path(definition, lat, lon)
        if cached_elevation_file_is_valid(cache_path):
            UI.vprint(2, "   Recycling ", cache_path)
            return 1
        UI.vprint(
            1,
            "    Downloading ",
            cache_path,
            "from Viewfinderpanoramas (J. de Ferranti).",
        )
        url = self.download_url(definition, lat, lon)
        response = DEM.http_request(
            url, definition.get("legacy_keyword", definition["code"]), verbose
        )
        if not response:
            # Every answer but a 404/410 already refused inside
            # ``http_request``, so reaching here means the server LOOKED
            # and the archive is not there.  For a land tile this source
            # covers, that is the #173 mapping defect, never a zero.
            return refuse_absent_base_archive(
                definition, lat, lon, url,
                "the archive is not on the server (404/410)")
        member_names = []
        # Did the archive hold a member for the cell that was ASKED for?
        # The two failures must not be confused (#173): a member that is
        # ABSENT is a mapping defect and refuses, while a member that is
        # present and unreadable is upstream data damage, contained as
        # before (the dem1/P32.zip CRC case).
        requested_member_seen = False
        with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
            for zipped_file in zip_ref.filelist:
                member_names.append(zipped_file.filename)
            for zipped_file in zip_ref.filelist:
                file_name = os.path.basename(zipped_file.filename)
                if not file_name:
                    continue
                try:
                    lat0 = int(file_name[1:3])
                    lon0 = int(file_name[4:7])
                except (ValueError, IndexError):
                    UI.vprint(
                        2,
                        "      Archive contains the unknown file name",
                        file_name,
                        "which is skipped.",
                    )
                    continue
                if ("S" in file_name) or ("s" in file_name):
                    lat0 *= -1
                if ("W" in file_name) or ("w" in file_name):
                    lon0 *= -1
                if (lat0, lon0) == (lat, lon):
                    requested_member_seen = True
                out_file_name = FNAMES.viewfinderpanorama(lat0, lon0)
                # we don't wish to overwrite a 1 arc-second version by
                # downloading the whole archive of a nearby 3 arc-second one
                if (
                    not os.path.exists(out_file_name)
                    or os.path.getsize(out_file_name) <= zipped_file.file_size
                ):
                    if not os.path.isdir(os.path.dirname(out_file_name)):
                        os.makedirs(os.path.dirname(out_file_name))
                    # Decompress BEFORE touching the destination, and land
                    # atomically: a corrupt member (upstream CRC damage --
                    # seen live in dem1/P32.zip) must neither abort the
                    # other members nor leave a zero-byte cache file behind.
                    try:
                        member_bytes = zip_ref.open(zipped_file, "r").read()
                    except (zipfile.BadZipFile, zlib.error, EOFError) as error:
                        UI.vprint(
                            1,
                            "    WARNING : skipping the corrupt archive "
                            "member",
                            zipped_file.filename,
                            "(" + str(error) + ") -- the archive on "
                            "viewfinderpanoramas.org is damaged for that "
                            "tile.",
                        )
                        continue
                    UI.vprint(2, "      Extracting", out_file_name)
                    temporary_path = out_file_name + ".part"
                    with open(temporary_path, "wb") as out:
                        out.write(member_bytes)
                    os.replace(temporary_path, out_file_name)
        # Success is judged on the tile actually requested: a corrupt
        # OTHER member in the same archive costs a warning, nothing more.
        if cached_elevation_file_is_valid(cache_path):
            return 1
        if requested_member_seen:
            # The member WAS in the archive and could not be extracted:
            # upstream CRC damage, contained exactly as before (a warning
            # above, no cache file, 0 here).
            return 0
        # The archive DOWNLOADED and holds NO member for the cell that
        # was asked for -- the second half of #173, and the half the
        # historic ``return 0`` hid completely.  The refusal lists what
        # the archive DOES hold, which is the measurement the attribution
        # needs (wrong zone, or a member grammar this parser misreads).
        return refuse_absent_base_archive(
            definition, lat, lon, url,
            "the archive downloaded but holds no member for this cell; "
            "its %d members are %s"
            % (len(member_names),
               ", ".join(sorted(member_names)[:ARCHIVE_MEMBERS_IN_REFUSAL])
               + ("..." if len(member_names) > ARCHIVE_MEMBERS_IN_REFUSAL
                  else "")))
