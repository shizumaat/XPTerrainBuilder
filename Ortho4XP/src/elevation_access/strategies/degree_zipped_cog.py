"""1-degree GeoTIFF cells packed in ranged-readable 10-degree zip archives.

The ``degree_zipped_cog`` access strategy (:class:`DegreeZippedCogStrategy`):
the ``degree_named_cog`` reading for a publisher that zips its 1-degree
cells by 10-degree block -- FABDEM (University of Bristol data portal,
issue #1942).  Nothing is downloaded whole: each archive's central
directory is listed once per process through ``/vsizip//vsicurl/`` (one
ranged read at the end of the zip), and the warp reads the cell's
member in place, the way ``tile_grid_http`` reads Hamburg's city zip.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

from elevation_access.base import TransientFetchError
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.strategies.degree_named_cog import DegreeNamedCogStrategy

__all__ = [
    "ARCHIVE_BLOCK_DEGREES",
    "DegreeZippedCogStrategy",
]

#: Degrees per side of one archive's block of cells.
ARCHIVE_BLOCK_DEGREES = 10


@register_access_strategy("degree_zipped_cog")
class DegreeZippedCogStrategy(DegreeNamedCogStrategy):
    """Degree cells read out of 10-degree zip archives.

    ``url_template`` names the ARCHIVE and may use the block tokens
    ``{block_latitude_token}{block_longitude_token}`` (its south-west
    corner) and ``{block_end_latitude_token}{block_end_longitude_token}``
    (its north-east corner, longitude wrapped: 180 -> ``W180``), in the
    hemisphere grammar of :meth:`degree_cell_tokens`.
    ``member_template`` names the cell's raster inside the archive with
    the cell tokens ``{latitude_token}{longitude_token}``.

    An archive the server answers 404/410 for holds no land (a durable
    absent, the outcome law of :meth:`_url_exists`); a cell missing from
    a listed archive's directory is likewise absent.  A listing that
    fails on an archive the server says exists is TRANSIENT.
    """

    # Process-lifetime memo: archive URL -> frozenset of member names.
    _members_by_archive = {}

    @classmethod
    def block_tokens(cls, cell_latitude, cell_longitude):
        """The four name tokens of the archive block holding a cell.

        ``(54, -5) -> ("N50", "W010", "N60", "E000")``;
        ``(-1, 175) -> ("S10", "E170", "N00", "W180")``.
        """
        size = ARCHIVE_BLOCK_DEGREES
        south = (cell_latitude // size) * size
        west = (cell_longitude // size) * size
        east = (west + size + 180) % 360 - 180
        (south_token, west_token) = cls.degree_cell_tokens(south, west)
        (north_token, east_token) = cls.degree_cell_tokens(south + size, east)
        return south_token, west_token, north_token, east_token

    def _cell_url(self, definition, cell_latitude, cell_longitude):
        """The ARCHIVE's URL for this cell (its member is named apart)."""
        (south, west, north, east) = self.block_tokens(
            cell_latitude, cell_longitude)
        return str(definition.get("url_template", "")).format(
            block_latitude_token=south, block_longitude_token=west,
            block_end_latitude_token=north, block_end_longitude_token=east)

    def _member_name(self, definition, cell_latitude, cell_longitude):
        (latitude_token, longitude_token) = self.degree_cell_tokens(
            cell_latitude, cell_longitude)
        return str(definition.get("member_template", "")).format(
            latitude_token=latitude_token, longitude_token=longitude_token)

    def _archive_members(self, archive_url):
        """Member names of an archive the server says exists."""
        memo = DegreeZippedCogStrategy._members_by_archive
        if archive_url in memo:
            return memo[archive_url]
        listing = gdal.ReadDir("/vsizip//vsicurl/" + archive_url)
        if not listing:
            raise TransientFetchError(
                "the directory of %s could not be read (the server says "
                "the archive exists) - transient, NOT recorded as "
                "no-coverage" % archive_url)
        members = frozenset(str(name) for name in listing)
        memo[archive_url] = members
        return members

    def cell_source(self, definition, cell_latitude, cell_longitude):
        """``/vsizip//vsicurl/<archive>/<member>``, or ``None`` when the
        archive or the member is absent."""
        if not has_gdal:
            return None
        archive_url = self._cell_url(definition, cell_latitude, cell_longitude)
        if not self._url_exists(archive_url):
            return None
        member = self._member_name(definition, cell_latitude, cell_longitude)
        if member not in self._archive_members(archive_url):
            return None
        return "/vsizip//vsicurl/%s/%s" % (archive_url, member)
