import os
import time
import requests
import itertools
from math import sqrt
import array
import numpy

try:
    from osgeo import gdal
    has_gdal = True
    gdal.UseExceptions()
except:
    has_gdal = False
from PIL import Image
import O4_UI_Utils as UI
import O4_File_Names as FNAMES

available_sources = (
    "View",
    "Viewfinderpanoramas (J. de Ferranti) - mostly worldwide",
    "SRTM",
    "SRTMv3 (from OpenTopography) - NOW REQUIRES MANUAL DOWNLOAD",
    "NED1",
    'NED 1" (from USGS) - USA, Canada, Mexico',
    "NED1/3",
    'NED 1/3" (from USGS) - USA',
    "ALOS",
    "ALOS 3W30 (from OpenTopography) - NOW REQUIRES MANUAL DOWNLOAD",
    "SONNY1",
    'Sonny LiDAR 1" (manual download from sonny.4lima.de) - Europe',
)

global_sources = ("View", "SRTM", "ALOS")

# Which base (tile-wide) elevation source to use when no custom_dem is
# set: "auto" ranks the enabled role=base definitions from
# Providers/Elevation/<CODE>.elv covering the tile (capped at
# 1 arc-second), or a provider CODE / legacy keyword pins one.  Declared
# as a configuration variable in O4_Cfg_Vars.py with module "DEM", so the
# configuration machinery overrides this module-level default in place.
base_elevation_source = "auto"


def drop_missing_pinned_files(source):
    """Drop pinned absolute file paths that do not exist from a
    ``custom_dem`` source string.

    A tile cfg written by whatever install originally built the tile may
    pin that install's own ``Elevation_data`` files by absolute path.  A
    missing pin must never reach the loader: the load errors and the
    fill logic then builds against a zero/garbage base — the "airport
    inset differs from the base DEM by hundreds of metres" symptom.
    Dropped LOUDLY and for this run only: the cfg value is never
    rewritten, because the pinned file may live on a temporarily
    unmounted volume.  Source-name tokens (provider codes) pass through
    untouched.
    """
    if not source:
        return source
    kept = []
    for token in str(source).split(";"):
        candidate = token.strip()
        if (candidate and os.path.isabs(candidate)
                and not os.path.exists(candidate)):
            UI.vprint(
                0,
                "   WARNING: pinned elevation file missing:", candidate,
                "— ignoring it for this run; default elevation sources"
                " will be used instead.",
            )
            continue
        kept.append(token)
    return ";".join(kept)


def resolve_default_base_source(lat, lon, elevation_level="auto"):
    """Map the ``base_elevation_source`` configuration to a legacy long name.

    Returns one of the ``available_sources`` long display names so
    ``DEM.load_data``'s existing dispatch (combined raster for global
    sources, single-file read otherwise) is reused untouched.  Falls back
    to the historic default (Viewfinderpanoramas) when the registry
    resolves nothing for this tile.  ``elevation_level`` is the tile's
    detail level: auto/"90"/"coastline" prefer the 90 m (3 arc-second)
    base class, numeric levels the 1 arc-second class (see
    ``O4_Elevation_Level.base_prefers_coarse``).
    """
    # Imported lazily: O4_Airport_Elevation_Insets imports this module at
    # top level (for the raster helpers), so a top-level import here would
    # be circular.
    import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS
    import O4_Elevation_Level as ELEVATION_LEVEL

    definition = ELEVATION_PROVIDERS.resolve_base_definition(
        lat,
        lon,
        base_elevation_source,
        prefer_coarse=ELEVATION_LEVEL.base_prefers_coarse(elevation_level),
    )
    if definition is None:
        return available_sources[1]
    legacy_keyword = definition.get("legacy_keyword")
    if legacy_keyword in available_sources:
        return available_sources[
            available_sources.index(legacy_keyword) + 1
        ]
    return available_sources[1]


_world_tiles_mask = [None]


def _world_tiles():
    """The land/ocean mask ``build_combined_raster`` consults, loaded once.

    ``None`` when it cannot be read — :func:`is_cached` then treats every
    neighbour as land, which is the conservative direction (more files
    demanded, so fewer tiles claim to be cached).
    """
    if _world_tiles_mask[0] is None:
        try:
            _world_tiles_mask[0] = numpy.array(
                Image.open(os.path.join(FNAMES.Utils_dir, "world_tiles.png"))
            )
        except Exception:
            _world_tiles_mask[0] = False
    mask = _world_tiles_mask[0]
    return None if mask is False else mask


def is_cached(tile) -> bool:
    """True when this tile's base elevation is already on disk.

    One of the per-subsystem fetch-admission predicates of
    docs/specs/apron-string-and-scheduling-spec.md §A.2 — filesystem
    only, never a network probe, conservative in every unknown.

    It mirrors, in order, the source dispatch :meth:`DEM.__init__`
    performs and the neighbourhood :func:`build_combined_raster`
    assembles:

    * a ``custom_dem`` whose first token names a file needs no download;
    * a ``generic_tif`` present for the tile short-circuits the default
      resolution exactly as the loader does;
    * a GLOBAL source is read over the 3x3 neighbourhood, so all nine
      tiles must be cached — ocean-only neighbours excepted, which
      ``build_combined_raster`` zero-fills instead of fetching;
    * any other source is a single-file read.

    ``tile`` is a configured ``O4_Config_Utils.Tile``.
    """
    try:
        import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS
        import O4_Elevation_Level as ELEVATION_LEVEL

        lat, lon = tile.lat, tile.lon
        elevation_level = getattr(tile, "elevation_level", "auto")
        source = str(getattr(tile, "custom_dem", "") or "").replace(
            "{latlon}", FNAMES.hem_latlon(lat, lon))
        source = source.split(";")[0].strip()
        if source and (os.path.isabs(source) or os.path.exists(source)):
            return os.path.exists(source)
        if not source:
            if os.path.exists(FNAMES.generic_tif(lat, lon)):
                return True
            source = resolve_default_base_source(lat, lon, elevation_level)
        if source in available_sources[1::2]:
            source = available_sources[available_sources.index(source) - 1]
        prefer_coarse = ELEVATION_LEVEL.base_prefers_coarse(elevation_level)
        if source not in global_sources:
            return ELEVATION_PROVIDERS.base_tile_is_cached(
                source, lat, lon, prefer_coarse=prefer_coarse)
        world_tiles = _world_tiles()
        for (lat0, lon0) in itertools.product(
            (lat, lat - 1, lat + 1), (lon, lon - 1, lon + 1)
        ):
            if (world_tiles is not None
                    and not world_tiles[89 - lat0, (180 + lon0) % 360]):
                continue          # ocean only: zero-filled, never fetched
            if not ELEVATION_PROVIDERS.base_tile_is_cached(
                    source, lat0, (lon0 + 180) % 360 - 180,
                    prefer_coarse=prefer_coarse):
                return False
        return True
    except Exception:
        return False


################################################################################
class DEM:
    def __init__(
        self,
        lat,
        lon,
        source="",
        fill_nodata=True,
        info_only=False,
        elevation_level="auto",
    ):
        self.lat = lat
        self.lon = lon
        # The tile's elevation detail level, driving the base-class
        # preference (90 m for auto/"90"/"coastline", 1 arc-second for
        # numeric levels) whenever this load resolves a default or a
        # "View" source; explicit files/CODES in ``source`` ignore it.
        self.elevation_level = elevation_level
        source = source.replace("{latlon}", FNAMES.hem_latlon(lat, lon))
        # The (post-substitution) source token this object was built from:
        # lets consumers recognise a sub-DEM by its file path (the airport
        # inset bake reuses the already-decoded subdem instead of decoding
        # the same GeoTIFF a second time).
        self.source_path = source
        # True once ``enable_baked_query`` has re-pointed the query path at
        # the baked working raster (see that method).
        self.baked_query_active = False
        if ";" in source:
            self.alt = self.alt_composite
            self.alt_vec = self.alt_vec_composite
        else:
            self.alt = self.alt_nostrict
            self.alt_vec = self.alt_vec_nostrict
        self.load_data(source, info_only)
        if info_only:
            return
        if fill_nodata == "to zero":
            self.nodata_to_zero()
        elif fill_nodata:
            if not fill_nodata_values_with_nearest_neighbor(
                self.alt_dem, self.nodata
            ):
                UI.vprint(
                    1,
                    "   INFO: Dataset contains too much no_data to be filled.",
                )
                self.nodata_to_zero()

        UI.vprint(
            1,
            "    * Min altitude:",
            self.alt_dem.min(),
            ", Max altitude:",
            self.alt_dem.max(),
            ", Mean:",
            self.alt_dem.mean(),
        )

    def load_data(self, source, info_only=False):
        if ";" in source:
            source, local_sources = source.split(";")[0], source.split(";")[1:]
        else:
            local_sources = None
        # The default-base resolution runs AFTER the composite split so an
        # empty BASE TOKEN (";inset1;...", which the airport-inset
        # augmentation produces whenever custom_dem is unset) resolves the
        # default exactly like an empty source does.  Before this reorder
        # an empty first token fell through to read_elevation_from_file("")
        # and silently produced an all-zero base raster.
        if not source:
            if os.path.exists(FNAMES.generic_tif(self.lat, self.lon)):
                source = FNAMES.generic_tif(self.lat, self.lon)
            else:
                source = resolve_default_base_source(
                    self.lat, self.lon, self.elevation_level
                )
        # The 90 m base-class preference rides along into the legacy
        # keyword dispatch: "View" is how the automatic ranking
        # round-trips through the long-name path, so its per-tile
        # dem1-vs-dem3 choice must honour the tile's elevation level.
        import O4_Elevation_Level as ELEVATION_LEVEL

        prefer_coarse = ELEVATION_LEVEL.base_prefers_coarse(
            self.elevation_level
        )
        if source in available_sources[1::2]:
            short_source = available_sources[
                available_sources.index(source) - 1
            ]
            if short_source in global_sources:
                (
                    self.epsg,
                    self.x0,
                    self.y0,
                    self.x1,
                    self.y1,
                    self.nodata,
                    self.nxdem,
                    self.nydem,
                    self.alt_dem,
                ) = build_combined_raster(
                    short_source,
                    self.lat,
                    self.lon,
                    info_only,
                    prefer_coarse=prefer_coarse,
                )
            else:
                if ensure_elevation(
                    short_source,
                    self.lat,
                    self.lon,
                    prefer_coarse=prefer_coarse,
                ):
                    (
                        self.epsg,
                        self.x0,
                        self.y0,
                        self.x1,
                        self.y1,
                        self.nodata,
                        self.nxdem,
                        self.nydem,
                        self.alt_dem,
                    ) = read_elevation_from_file(
                        FNAMES.elevation_data(short_source, self.lat, self.lon),
                        self.lat,
                        self.lon,
                        info_only,
                        3601,
                    )
                else:
                    (
                        self.epsg,
                        self.x0,
                        self.y0,
                        self.x1,
                        self.y1,
                        self.nodata,
                        self.nxdem,
                        self.nydem,
                        self.alt_dem,
                    ) = (
                        4326,
                        0,
                        0,
                        1,
                        1,
                        -32768,
                        3601,
                        3601,
                        numpy.zeros((3601, 3601), dtype=numpy.float32),
                    )
        else:
            file_name = source
            (
                self.epsg,
                self.x0,
                self.y0,
                self.x1,
                self.y1,
                self.nodata,
                self.nxdem,
                self.nydem,
                self.alt_dem,
            ) = read_elevation_from_file(
                file_name, self.lat, self.lon, info_only
            )
        if not local_sources:
            return
        self.subdems = tuple()
        for local_source in local_sources:
            # Cancellation at the sub-source boundary: constructing each
            # sub-DEM may download.  On Stop, keep whatever's assembled
            # and return -- load_data sets attributes rather than
            # returning a status, and the cancelled build discards the
            # object anyway.
            if UI.red_flag:
                break
            self.subdems += (
                DEM(self.lat, self.lon, local_source, False, info_only),
            )
            self.subdems[-1].alt = self.subdems[-1].alt_strict
            self.subdems[-1].alt_vec = self.subdems[-1].alt_vec_strict

    def nodata_to_zero(self):
        if (self.alt_dem == self.nodata).any():
            UI.vprint(1, "   INFO: Replacing nodata nodes with zero altitude.")
            self.alt_dem[self.alt_dem == self.nodata] = 0
        self.nodata = -32768
        return

    def write_to_file(self, filename):
        self.alt_dem.astype(numpy.float32).tofile(filename)
        return

    def create_normal_map(self, pixx, pixy):
        dx = numpy.zeros((self.nxdem, self.nydem))
        dy = numpy.zeros((self.nxdem, self.nydem))
        dx[:, 1:-1] = (self.alt_dem[:, 2:] - self.alt_dem[:, 0:-2]) / (2 * pixx)
        dx[:, 0] = (self.alt_dem[:, 1] - self.alt_dem[:, 0]) / (pixx)
        dx[:, -1] = (self.alt_dem[:, -1] - self.alt_dem[:, -2]) / (pixx)
        dy[1:-1, :] = (self.alt_dem[:-2, :] - self.alt_dem[2:, :]) / (2 * pixy)
        dy[0, :] = (self.alt_dem[0, :] - self.alt_dem[1, :]) / (pixy)
        dy[-1, :] = (self.alt_dem[-2, :] - self.alt_dem[-1, :]) / (pixy)
        del self.alt_dem
        norm = numpy.sqrt(1 + dx ** 2 + dy ** 2)
        dx = dx / norm
        dy = dy / norm
        del norm
        band_r = Image.fromarray(
            ((1 + dx) / 2 * 255).astype(numpy.uint8)
        ).resize((4096, 4096))
        del dx
        band_g = Image.fromarray(
            ((1 - dy) / 2 * 255).astype(numpy.uint8)
        ).resize((4096, 4096))
        del dy
        band_b = Image.fromarray(
            (numpy.ones((4096, 4096)) * 10).astype(numpy.uint8)
        )
        band_a = Image.fromarray(
            (numpy.ones((4096, 4096)) * 128).astype(numpy.uint8)
        )
        im = Image.merge("RGBA", (band_r, band_g, band_b, band_a))
        im.save("normal_map.png")

    def super_level_set(self, level, wgs84_bbox):
        (lonmin, lonmax, latmin, latmax) = wgs84_bbox
        xmin = lonmin - self.lon
        xmax = lonmax - self.lon
        ymin = latmin - self.lat
        ymax = latmax - self.lat
        if xmin < self.x0:
            xmin = self.x0
        if xmax > self.x1:
            xmax = self.x1
        if ymin < self.y0:
            ymin = self.y0
        if ymax > self.y1:
            ymax = self.y1
        pixx0 = round((xmin - self.x0) / (self.x1 - self.x0) * (self.nxdem - 1))
        pixx1 = round((xmax - self.x0) / (self.x1 - self.x0) * (self.nxdem - 1))
        pixy0 = round((self.y1 - ymax) / (self.y1 - self.y0) * (self.nydem - 1))
        pixy1 = round((self.y1 - ymin) / (self.y1 - self.y0) * (self.nydem - 1))
        return (
            (
                xmin + self.lon,
                xmax + self.lon,
                ymin + self.lat,
                ymax + self.lat,
            ),
            self.alt_dem[pixy0 : pixy1 + 1, pixx0 : pixx1 + 1] >= level,
        )

    def alt_nostrict(self, node):
        Nx = self.nxdem - 1
        Ny = self.nydem - 1
        x = node[0]
        y = node[1]
        x = max(x, self.x0)
        x = min(x, self.x1)
        y = max(y, self.y0)
        y = min(y, self.y1)
        px = (x - self.x0) / (self.x1 - self.x0) * Nx
        py = (y - self.y0) / (self.y1 - self.y0) * Ny
        nx = int(px)
        Nminusny = Ny - int(py)
        rx = px - nx
        ry = py + Nminusny - Ny
        t1 = self.alt_dem[Nminusny, nx]
        t2 = self.alt_dem[
            (Nminusny - 1) * (Nminusny >= 1),
            (nx + 1) * (nx < Nx) + Nx * (nx == Nx),
        ]
        t3 = self.alt_dem[Nminusny, (nx + 1) * (nx < Nx) + Nx * (nx == Nx)]
        t4 = self.alt_dem[(Nminusny - 1) * (Nminusny >= 1), nx]
        return ((1 - rx) * t1 + ry * t2 + (rx - ry) * t3) * (rx >= ry) + (
            (1 - ry) * t1 + rx * t2 + (ry - rx) * t4
        ) * (rx < ry)

    def alt_strict(self, node):
        x = node[0]
        y = node[1]
        return (
            self.nodata
            if (
                (x > self.x1) or (x < self.x0) or (y < self.y0) or (y > self.y1)
            )
            else self.alt_dem[
                int(
                    round(
                        (self.y1 - y) / (self.y1 - self.y0) * (self.nydem - 1)
                    )
                ),
                int(
                    round(
                        (x - self.x0) / (self.x1 - self.x0) * (self.nxdem - 1)
                    )
                ),
            ]
        )

    def alt_composite(self, node):
        for subdem in self.subdems[::-1]:
            tmp = subdem.alt_strict(node)
            if tmp != subdem.nodata:
                return tmp
        return self.alt_nostrict(node)

    # ------------------------------------------------------------------
    # THE BAKED-RASTER QUERY (owner ruling 2026-07-25)
    #
    # the grading law measures the surface the mesher renders -- one
    # surface, two readers.
    #
    # ``alt_baked``/``alt_vec_baked`` reproduce, in Python, the
    # interpolation Triangle4XP performs on the ``.alt`` raster it is
    # handed (``Utils/src/Triangle4XP.c:3571`` ``altitude()``): TRUE
    # BILINEAR on the working grid ``alt_dem``, whose four corners are
    # weighted (1-rx)(1-ry), rx(1-ry), (1-rx)ry, rx*ry.  That is the only
    # surface the mesh actually renders, so it is the only surface a
    # "pin this vertex to the DEM" rule may legitimately measure.
    #
    # Note that neither of the pre-existing readers equals it inside a
    # grid cell:
    #   * ``alt_strict`` (which ``alt_composite`` reaches for first) is
    #     NEAREST NEIGHBOUR on the sub-DEM's own native posting -- a 30 m
    #     staircase against the mesh's ramp;
    #   * ``alt_nostrict`` is a TRIANGLE-SPLIT (barycentric) interpolant,
    #     which agrees with bilinear only on the cell edges and differs by
    #     +-(t1+t2-t3-t4)/4 at the cell centre.
    # ``alt_nostrict`` is left untouched: it is the legacy reader for
    # non-composite DEMs and for the ``smoothen``/curvature paths, and
    # re-pointing it would change every tile ever built.
    # ------------------------------------------------------------------

    def alt_baked(self, node):
        """Bilinear altitude on the baked working raster ``alt_dem``.

        Bit-for-bit the interpolation ``Triangle4XP.altitude()`` applies
        to the ``.alt`` file written from this same array, save that the
        node is CLAMPED into the raster extent first (``alt_nostrict``'s
        convention -- Triangle4XP assumes its callers stay in range) and
        that a nodata corner is not propagated: by the time a query DEM
        reaches the grading law its nodata has been filled, and returning
        the -32768 sentinel into a grade computation would be far worse
        than the interpolation it replaces.
        """
        Nx = self.nxdem - 1
        Ny = self.nydem - 1
        x = min(max(node[0], self.x0), self.x1)
        y = min(max(node[1], self.y0), self.y1)
        px = (x - self.x0) / (self.x1 - self.x0) * Nx
        py = (self.y1 - y) / (self.y1 - self.y0) * Ny
        nx = min(int(px), Nx)
        ny = min(int(py), Ny)
        nxp = min(nx + 1, Nx)
        nyp = min(ny + 1, Ny)
        rx = px - nx
        ry = py - ny
        return (
            self.alt_dem[ny, nx] * (1 - rx) * (1 - ry)
            + self.alt_dem[ny, nxp] * rx * (1 - ry)
            + self.alt_dem[nyp, nx] * (1 - rx) * ry
            + self.alt_dem[nyp, nxp] * rx * ry
        )

    def alt_vec_baked(self, way):
        """Vectorized :meth:`alt_baked` over an ``(n, 2)`` array of nodes."""
        Nx = self.nxdem - 1
        Ny = self.nydem - 1
        x = numpy.clip(numpy.asarray(way)[:, 0], self.x0, self.x1)
        y = numpy.clip(numpy.asarray(way)[:, 1], self.y0, self.y1)
        px = (x - self.x0) / (self.x1 - self.x0) * Nx
        py = (self.y1 - y) / (self.y1 - self.y0) * Ny
        nx = numpy.minimum(px.astype(numpy.int64), Nx)
        ny = numpy.minimum(py.astype(numpy.int64), Ny)
        nxp = numpy.minimum(nx + 1, Nx)
        nyp = numpy.minimum(ny + 1, Ny)
        rx = px - nx
        ry = py - ny
        return (
            self.alt_dem[ny, nx] * (1 - rx) * (1 - ry)
            + self.alt_dem[ny, nxp] * rx * (1 - ry)
            + self.alt_dem[nyp, nx] * (1 - rx) * ry
            + self.alt_dem[nyp, nxp] * rx * ry
        )

    def enable_baked_query(self, baked_source_paths):
        """Re-point ``alt``/``alt_vec`` at the baked working raster.

        Called once by ``O4_Airport_Elevation_Insets`` at the end of the
        raster bake -- the moment ``alt_dem`` becomes the surface the
        mesher will render.  Returns True when the switch was made.

        GATE ``O4_DEM_QUERY_BAKED``, default ON.  It shipped OFF for one
        session: reading each tile's OWN baked raster exposed a 3.80 m
        cross-tile disagreement on the SPLP seam, because the two tiles had
        auto-picked different working grids (1/3" on -13/-077, 1/2" on
        -13/-078) and bilinear between different post sets straddles the
        same escarpment differently.  The rasters always agreed EXACTLY
        (0.0000 m over 225 exactly-shared posts) -- the divergence was
        never in this query, it was the ballot, and it was equally present
        in the two tiles' RENDERED meshes; the old nearest-neighbour
        composite merely hid it by measuring a surface neither tile draws.
        ``seam_harmonized_ballot_insets`` (gate ``O4_INSET_SEAM_HARMONIZE``)
        now makes seam-sharing tiles ballot identically, and the same
        601-sample probe reads 0.0000 m on all three seam lines.

        Refused (legacy composite behaviour kept, byte-identical) when:

        * the gate ``O4_DEM_QUERY_BAKED`` is off;
        * this DEM is not a composite, or has no raster;
        * ANY sub-DEM is absent from ``baked_source_paths``.  A sub-DEM
          that was never baked lives only in the query path (the legacy
          ``custom_dem = "base;local1"`` feature), so bypassing the
          composite would silently drop it.  The switch is made only when
          the baked raster provably represents the WHOLE composite.
        """
        if os.environ.get("O4_DEM_QUERY_BAKED", "1") != "1":
            return False
        subdems = getattr(self, "subdems", None)
        if not subdems or self.alt_dem is None:
            return False
        baked = set(baked_source_paths or ())
        for subdem in subdems:
            if getattr(subdem, "source_path", None) not in baked:
                return False
        self.alt = self.alt_baked
        self.alt_vec = self.alt_vec_baked
        self.baked_query_active = True
        return True

    def alt_vec_nostrict(self, way):
        Nx = self.nxdem - 1
        Ny = self.nydem - 1
        x, y = way[:, 0], way[:, 1]
        x = numpy.maximum.reduce([x, self.x0 * numpy.ones(x.shape)])
        x = numpy.minimum.reduce([x, self.x1 * numpy.ones(x.shape)])
        y = numpy.maximum.reduce([y, self.y0 * numpy.ones(y.shape)])
        y = numpy.minimum.reduce([y, self.y1 * numpy.ones(y.shape)])
        px = (x - self.x0) / (self.x1 - self.x0) * Nx
        py = (y - self.y0) / (self.y1 - self.y0) * Ny
        nx = px.astype(numpy.uint16)
        Nminusny = Ny - py.astype(numpy.uint16)
        rx = px - nx
        ry = py + Nminusny - Ny
        t1 = [self.alt_dem[i][j] for i, j in zip(Nminusny, nx)]
        t2 = [
            self.alt_dem[i][j]
            for i, j in zip(
                (Nminusny - 1) * (Nminusny >= 1),
                (nx + 1) * (nx < Nx) + Nx * (nx == Nx),
            )
        ]
        t3 = [
            self.alt_dem[i][j]
            for i, j in zip(Nminusny, (nx + 1) * (nx < Nx) + Nx * (nx == Nx))
        ]
        t4 = [
            self.alt_dem[i][j]
            for i, j in zip((Nminusny - 1) * (Nminusny >= 1), nx)
        ]
        return ((1 - rx) * t1 + ry * t2 + (rx - ry) * t3) * (rx >= ry) + (
            (1 - ry) * t1 + rx * t2 + (ry - rx) * t4
        ) * (rx < ry)

    def alt_vec_strict(self, way):
        x, y = way[:, 0], way[:, 1]
        mask = (x >= self.x0) * (x <= self.x1) * (y >= self.y0) * (y <= self.y1)
        nx = numpy.round(
            (x - self.x0) / (self.x1 - self.x0) * (self.nxdem - 1)
        ).astype(numpy.uint16)
        Nminusny = numpy.round(
            (self.y1 - y) / (self.y1 - self.y0) * (self.nydem - 1)
        ).astype(numpy.uint16)
        return numpy.array(
            [
                self.alt_dem[i][j] if k else self.nodata
                for i, j, k in zip(Nminusny, nx, mask)
            ]
        )

    def alt_vec_bilinear_strict(self, way):
        """Strict-extent BILINEAR altitude on this DEM's own posting.

        The interpolating twin of :meth:`alt_vec_strict`: same extent
        semantics (``nodata`` for every node outside ``[x0, x1] x [y0,
        y1]``), but the value inside comes from the four surrounding
        posts weighted (1-rx)(1-ry), rx(1-ry), (1-rx)ry, rx*ry instead of
        from the single nearest post.

        This is the reader the airport-inset BAKE uses when the inset is
        COARSER than the working grid (see
        ``O4_Airport_Elevation_Insets._bake_one_inset``): stamping a 30 m
        inset onto a 10 m working grid with nearest neighbour writes a
        literal 30 m staircase into the ``.alt`` file, which Triangle4XP
        --- a TRUE BILINEAR reader (``Utils/src/Triangle4XP.c:3571``
        ``altitude()``) --- then refines against, at no fidelity gain.

        NODATA handling is RENORMALISING rather than propagating: corners
        carrying the sentinel are dropped from the weighted sum and the
        remaining weights are rescaled, so a node keeps a value as long as
        ANY of its four posts has one.  Propagating instead would erode
        the inset's data footprint by one post all round on every hole
        edge --- a coverage change --- whereas renormalising keeps the
        footprint at least as large as nearest neighbour's.  Only a node
        whose four posts are all nodata returns ``nodata``.
        """
        way = numpy.asarray(way)
        x, y = way[:, 0], way[:, 1]
        inside = (
            (x >= self.x0) * (x <= self.x1) * (y >= self.y0) * (y <= self.y1)
        )
        Nx = self.nxdem - 1
        Ny = self.nydem - 1
        px = numpy.clip((x - self.x0) / (self.x1 - self.x0) * Nx, 0, Nx)
        py = numpy.clip((self.y1 - y) / (self.y1 - self.y0) * Ny, 0, Ny)
        # Anchor on the LOWER post of each cell so ``+1`` stays in range;
        # a node landing exactly on the far edge gets rx (or ry) == 1 and
        # therefore reads that edge post exactly.
        nx = numpy.minimum(px.astype(numpy.int64), max(Nx - 1, 0))
        ny = numpy.minimum(py.astype(numpy.int64), max(Ny - 1, 0))
        nxp = numpy.minimum(nx + 1, Nx)
        nyp = numpy.minimum(ny + 1, Ny)
        rx = px - nx
        ry = py - ny
        corners = numpy.stack(
            (
                self.alt_dem[ny, nx],
                self.alt_dem[ny, nxp],
                self.alt_dem[nyp, nx],
                self.alt_dem[nyp, nxp],
            )
        ).astype(numpy.float64)
        weights = numpy.stack(
            (
                (1 - rx) * (1 - ry),
                rx * (1 - ry),
                (1 - rx) * ry,
                rx * ry,
            )
        )
        valid = corners != self.nodata
        weights = weights * valid
        total = weights.sum(axis=0)
        values = (weights * numpy.where(valid, corners, 0.0)).sum(axis=0)
        return numpy.where(
            inside * (total > 0),
            values / numpy.where(total > 0, total, 1.0),
            self.nodata,
        )

    def alt_vec_composite(self, way):
        tmp = self.alt_vec_nostrict(way)
        for subdem in self.subdems:
            tmp2 = subdem.alt_vec_strict(way)
            tmp[tmp2 != subdem.nodata] = tmp2[tmp2 != subdem.nodata]
        return tmp

################################################################################
def build_combined_raster(source, lat, lon, info_only, prefer_coarse=False):
    world_tiles = numpy.array(
        Image.open(os.path.join(FNAMES.Utils_dir, "world_tiles.png"))
    )
    if source in ("View", "SRTM"):
        base = 3601
        overlap = 1
        beyond = 36
        x0 = y0 = -0.01
        x1 = y1 = 1.01
        epsg = 4326
        nodata = -32768
        nxdem = nydem = base + 2 * beyond  # = 3673
    elif source == ("ALOS"):
        base = 3600
        overlap = 0
        beyond = 36
        eps = 1 / 7200
        x0 = y0 = -0.01 + eps
        x1 = y1 = 1.01 - eps
        epsg = 4326
        nodata = -32768
        nxdem = nydem = base + 2 * beyond  # = 3672
    if info_only:
        return (epsg, x0, y0, x1, y1, nodata, nxdem, nydem, None)
    alt_dem = numpy.zeros((nydem, nxdem), dtype=numpy.float32)
    for (lat0, lon0) in itertools.product(
        (lat, lat - 1, lat + 1), (lon, lon - 1, lon + 1)
    ):
        # Cancellation at the tile boundary: each of the 9 iterations may
        # trigger a whole-tile elevation download via ensure_elevation.
        # On Stop, leave the remaining neighbours as the zeros alt_dem
        # was initialised to and return the partial raster -- this keeps
        # build_combined_raster's always-returns-the-9-tuple contract
        # intact (no new failure path), and the cancelled build discards
        # the result anyway.
        if UI.red_flag:
            break
        verbose = True if (lat0 == lat and lon0 == lon) else False
        x = (180 + lon0) % 360
        y = 89 - lat0
        if not world_tiles[y, x]:
            tmparray = numpy.zeros((base, base), dtype=numpy.float32)
        elif ensure_elevation(
            source,
            lat0,
            (lon0 + 180) % 360 - 180,
            verbose,
            prefer_coarse=prefer_coarse,
        ):
            tmparray = read_elevation_from_file(
                FNAMES.elevation_data(source, lat0, (lon0 + 180) % 360 - 180),
                lat0,
                (lon0 + 180) % 360 - 180,
                info_only,
                base,
            )[-1]
        else:
            tmparray = numpy.zeros((base, base), dtype=numpy.float32)
        by = beyond
        ov = overlap
        if lat0 == lat and lon0 == lon:
            alt_dem[by:-by, by:-by] = tmparray
        elif lat0 == lat and lon0 == lon - 1:
            alt_dem[by:-by, :by] = (
                tmparray[:, -by - ov : -ov] if ov else tmparray[:, -by:]
            )
        elif lat0 == lat and lon0 == lon + 1:
            alt_dem[by:-by, -by:] = (
                tmparray[:, ov : ov + by] if ov else tmparray[:, :by]
            )
        elif lat0 == lat + 1 and lon0 == lon:
            alt_dem[:by, by:-by] = (
                tmparray[-ov - by : -ov, :] if ov else tmparray[-by:, :]
            )
        elif lat0 == lat - 1 and lon0 == lon:
            alt_dem[-by:, by:-by] = (
                tmparray[ov : ov + by, :] if ov else tmparray[:by, :]
            )
        elif lat0 == lat + 1 and lon0 == lon - 1:
            alt_dem[:by, :by] = (
                tmparray[-ov - by : -ov, -ov - by : -ov]
                if ov
                else tmparray[-by:, -by:]
            )
        elif lat0 == lat + 1 and lon0 == lon + 1:
            alt_dem[:by, -by:] = (
                tmparray[-ov - by : -ov, ov : ov + by]
                if ov
                else tmparray[-by:, :by]
            )
        elif lat0 == lat - 1 and lon0 == lon - 1:
            alt_dem[-by:, :by] = (
                tmparray[ov : ov + by, -ov - by : -ov]
                if ov
                else tmparray[:by, -by:]
            )
        elif lat0 == lat - 1 and lon0 == lon + 1:
            alt_dem[-by:, -by:] = (
                tmparray[ov : ov + by, ov : ov + by]
                if ov
                else tmparray[:by, :by]
            )
    return (epsg, x0, y0, x1, y1, nodata, nxdem, nydem, alt_dem)

################################################################################
def read_elevation_from_file(
    file_name, lat, lon, info_only=False, base_if_error=3601
):
    alt_dem = None
    if file_name[-4:].lower() == ".hgt":
        x0 = y0 = 0
        x1 = y1 = 1
        epsg = 4326
        nodata = -32768
        try:
            nxdem = nydem = int(round(sqrt(os.path.getsize(file_name) / 2)))
            if not info_only:
                alt_dem = (
                    numpy.fromfile(file_name, numpy.dtype(">i2"))
                    .astype(numpy.float32)
                    .reshape((nydem, nxdem))
                )
            if nxdem == 1201:
                nxdem = nydem = 3601
                if not info_only:
                    fill_nodata_values_with_nearest_neighbor(alt_dem, nodata)
                    alt_dem = upsample(alt_dem)
        except Exception as e:
            print(e)
            UI.lvprint(
                1,
                "    ERROR: in reading elevation from",
                file_name,
                "-> replaced with zero altitude.",
            )
            nxdem = nydem = base_if_error
            if not info_only:
                alt_dem = numpy.zeros(
                    (base_if_error, base_if_error), dtype=numpy.float32
                )

    elif file_name[-4:].lower() == ".raw":
        try:
            nxdem = nydem = int(round(sqrt(os.path.getsize(file_name) / 2)))
            f = open(file_name, "rb")
            alt = array.array("h")
            alt.fromfile(f, nxdem * nydem)
            f.close()
            if not info_only:
                alt_dem = numpy.asarray(alt, dtype=numpy.float32).reshape(
                    (nxdem, nydem)
                )[::-1]
        except:
            UI.lvprint(
                1,
                "    ERROR: in reading elevation from",
                file_name,
                "-> replaced with zero altitude.",
            )
            nxdem = nydem = base_if_error
            if not info_only:
                alt_dem = numpy.zeros(
                    (base_if_error, base_if_error), dtype=numpy.float32
                )
        x0 = y0 = 0
        x1 = y1 = 1
        epsg = 4326
        nodata = -32768
    elif has_gdal:
        try:
            ds = gdal.Open(file_name)
            rs = ds.GetRasterBand(1)
            if not info_only:
                alt_dem = rs.ReadAsArray().astype(numpy.float32)
            (nxdem, nydem) = (ds.RasterXSize, ds.RasterYSize)
            nodata = rs.GetNoDataValue()
            if nodata is None:
                UI.vprint(
                    1,
                    "    WARNING: raster DEM does not advertise its no_data ",
                    "value, assuming -32768.",
                )
                nodata = -32768
            else:  
                # elevations being stored as float32, we push the nodata to that 
                # framework too, and then replace no_data values by -32768 
                # anyway for uniformity
                nodata = numpy.float32(nodata)
                if not info_only:
                    alt_dem[alt_dem == nodata] = -32768
                nodata = -32768
            try:
                epsg = int(ds.GetProjection().split('"')[-2])
            except:
                UI.vprint(
                    1,
                    "    WARNING: raster DEM does not advertise its EPSG ",
                    "code, assuming 4326.",
                )
                epsg = 4326
            if epsg not in (
                4326,
                4269,
            ):  
            # let's be blind about 4269 which might be sufficiently close to 
            # 4326 for our purposes
                UI.lvprint(
                    1,
                    "    WARNING: unsupported EPSG code ",
                    epsg,
                    ". Only EPSG:4326 is supported, result is likely to ",
                    "be non sense.",
                )
            geo = ds.GetGeoTransform()
            # We are assuming AREA_OR_POINT is area here
            x0 = geo[0] + 0.5 * geo[1] - lon
            y1 = geo[3] + 0.5 * geo[5] - lat
            x1 = x0 + (nxdem - 1) * geo[1]
            y0 = y1 + (nydem - 1) * geo[5]
        except:
            UI.lvprint(
                1,
                "   ERROR: in reading ",
                file_name,
                "-> replaced with zero altitude.",
            )
            nxdem = nydem = base_if_error
            if not info_only:
                alt_dem = numpy.zeros(
                    (base_if_error, base_if_error), dtype=numpy.float32
                )
            x0 = y0 = 0
            x1 = y1 = 1
            epsg = 4326
            nodata = -32768
    elif not has_gdal:
        UI.lvprint(
            1,
            "   WARNING: unsupported raster (install Gdal):",
            file_name,
            "-> replaced with zero altitude.",
        )
        nxdem = nydem = base_if_error
        if not info_only:
            alt_dem = numpy.zeros(
                (base_if_error, base_if_error), dtype=numpy.float32
            )
        x0 = y0 = 0
        x1 = y1 = 1
        epsg = 4326
        nodata = -32768
    return (epsg, x0, y0, x1, y1, nodata, nxdem, nydem, alt_dem)


##############################################################################

##############################################################################
def ensure_elevation(source, lat, lon, verbose=True, prefer_coarse=False):
    """Ensure the whole-tile file for a base elevation source is cached.

    Thin compatibility shim over the declarative provider registry in
    O4_Airport_Elevation_Insets (spec section 3.6): the historic inline
    if/elif chain (Viewfinderpanoramas archive math + zip extraction,
    USGS staged-products downloads, the SRTM/ALOS dead-download warning)
    now lives in the registry's viewfinder_zip / usgs_seamless /
    manual_download access strategies, configured by the
    Providers/Elevation/<CODE>.elv definition files.

    The signature and the 0/1 return convention are unchanged -- the DEM
    loader, the 3x3 combined-raster assembly and the GUI keep calling
    this with the legacy short keywords ("View", "SRTM", "NED1",
    "NED1/3", "ALOS"), which the registry resolves as aliases; registry
    CODES (e.g. "VIEWFINDER1") are accepted too.  Downloads land at the
    LEGACY cache paths (FNAMES.viewfinderpanorama / FNAMES.
    elevation_data), byte-identical to the historic layout.
    """
    # Imported lazily: O4_Airport_Elevation_Insets imports this module at
    # top level (for the raster helpers), so a top-level import here would
    # be circular.
    import O4_Airport_Elevation_Insets as ELEVATION_PROVIDERS

    return ELEVATION_PROVIDERS.ensure_base_tile(
        source, lat, lon, verbose, prefer_coarse=prefer_coarse
    )

################################################################################
def http_request(url, source, verbose=False):
    # Guarded import of the process-wide throughput meter (sanctioned
    # pattern copied from O4_OSM_Extracts): telemetry must never break a
    # download, so a missing engine leaves METER as None and every feed
    # is skipped.
    try:
        from o4_engine import download_meter as METER
    except Exception:
        METER = None
    s = requests.Session()
    tentative = 0
    while True:
        # Cancellation: the user pressed Stop.  Abort before spending
        # another request on this source and match http_request's
        # existing failure convention -- a falsy 0 return, which every
        # caller already treats as "download failed".
        if UI.red_flag:
            return 0
        try:
            t0 = time.time()
            r = s.get(url, timeout=10)
            elapsed = time.time() - t0
            status_code = str(r)
            if "[20" in status_code:
                # Feed the throughput meter with this completed fetch so
                # the build-time ETA prices elevation downloads from
                # measurement.  Never raise from telemetry.
                if METER is not None:
                    try:
                        METER.record(len(r.content), elapsed)
                    except Exception:
                        pass
                return r
            elif "[40" in status_code or "[30" in status_code:
                if verbose:
                    UI.vprint(2, "    Server said 'Not Found'")
                return 0
            elif "[5" in status_code:
                if verbose:
                    UI.vprint(
                        2, "    Server said 'Internal Error'.", status_code
                    )
            else:
                if verbose:
                    UI.vprint(2, status_code)
        except Exception as e:
            if verbose:
                UI.vprint(2, e)
        tentative += 1
        if tentative == 6:
            return 0
        # Cancellation before the exponential back-off sleep: Stop must
        # not be blocked for up to 2**tentative seconds waiting to retry
        # a source the user no longer wants.  Same 0 failure convention.
        if UI.red_flag:
            return 0
        UI.vprint(
            1,
            "    ",
            source,
            "server may be down or busy, new tentative in",
            2 ** tentative,
            "sec...",
        )
        time.sleep(2 ** tentative)

################################################################################
def fill_nodata_values_with_nearest_neighbor(alt_dem, nodata):
    step = 0
    while (alt_dem == nodata).any():
        if not step:
            if numpy.sum(alt_dem == nodata) >= 10000:
                return 0
            UI.vprint(
                2,
                "    INFO: Elevation file contains voids, trying to fill ",
                "them recursively by nearest neighbour.",
            )
        else:
            UI.vprint(2, "    ", step)
        alt10 = numpy.roll(alt_dem, 1, axis=0)
        alt10[0] = alt_dem[0]
        alt20 = numpy.roll(alt_dem, -1, axis=0)
        alt20[-1] = alt_dem[-1]
        alt01 = numpy.roll(alt_dem, 1, axis=1)
        alt01[:, 0] = alt_dem[:, 0]
        alt02 = numpy.roll(alt_dem, -1, axis=1)
        alt02[:, -1] = alt_dem[:, -1]
        if (nodata < 0):
            atemp = numpy.maximum(alt10, alt20)
            atemp = numpy.maximum(atemp, alt01)
            atemp = numpy.maximum(atemp, alt02)
        else:
            atemp = numpy.minimum(alt10, alt20)
            atemp = numpy.minimum(atemp, alt01)
            atemp = numpy.minimum(atemp, alt02)
        alt_dem[alt_dem == nodata] = atemp[alt_dem == nodata]
        step += 1
        if step > 20:
            UI.vprint(
                1,
                "    WARNING: The raster contain holes that seem to big to ",
                "be filled... I'm filling the remainder with zero.",
            )
            alt_dem[alt_dem == nodata] = 0
            break
    if step:
        UI.vprint(2, "    Done.")
    return 1

################################################################################
def upsample(alt_dem):
    # only implemented from 1201 to 3601, might be worth upgrading it some day
    alt_dem_tmp = numpy.zeros((3601, 3601), dtype=numpy.float32)
    for i in range(1201):
        alt_dem_tmp[3 * i, ::3] = alt_dem[i]
        alt_dem_tmp[3 * i, 1::3] = (
            2 / 3 * alt_dem[i, :-1] + 1 / 3 * alt_dem[i, 1:]
        )
        alt_dem_tmp[3 * i, 2::3] = (
            1 / 3 * alt_dem[i, :-1] + 2 / 3 * alt_dem[i, 1:]
        )
        if i == 1200:
            break
        alt_dem_tmp[3 * i + 1, ::3] = (
            2 / 3 * alt_dem[i] + 1 / 3 * alt_dem[i + 1]
        )
        alt_dem_tmp[3 * i + 2, ::3] = (
            1 / 3 * alt_dem[i] + 2 / 3 * alt_dem[i + 1]
        )
        alt_dem_tmp[3 * i + 1, 1::3] = (
            4 / 9 * alt_dem[i][:-1]
            + 2 / 9 * alt_dem[i, 1:]
            + 2 / 9 * alt_dem[i + 1, :-1]
            + 1 / 9 * alt_dem[i + 1, 1:]
        )
        alt_dem_tmp[3 * i + 2, 1::3] = (
            2 / 9 * alt_dem[i][:-1]
            + 1 / 9 * alt_dem[i, 1:]
            + 4 / 9 * alt_dem[i + 1, :-1]
            + 2 / 9 * alt_dem[i + 1, 1:]
        )
        alt_dem_tmp[3 * i + 1, 2::3] = (
            2 / 9 * alt_dem[i][:-1]
            + 4 / 9 * alt_dem[i, 1:]
            + 1 / 9 * alt_dem[i + 1, :-1]
            + 2 / 9 * alt_dem[i + 1, 1:]
        )
        alt_dem_tmp[3 * i + 2, 2::3] = (
            1 / 9 * alt_dem[i][:-1]
            + 2 / 9 * alt_dem[i, 1:]
            + 2 / 9 * alt_dem[i + 1, :-1]
            + 4 / 9 * alt_dem[i + 1, 1:]
        )
    return alt_dem_tmp

################################################################################
def smoothen(raster, pix_width, mask_im, preserve_boundary=True):
    if not pix_width:
        return raster
    if not mask_im:
        return raster
    tmp = numpy.array(raster)
    mask_array = numpy.array(mask_im, dtype=numpy.float32) / 255
    kernel = numpy.array(range(1, 2 * (pix_width + 1)))
    kernel[pix_width + 1 :] = range(pix_width, 0, -1)
    kernel = kernel / (pix_width + 1) ** 2
    tmp = tmp * mask_array
    tmpw = numpy.array(mask_array)
    for i in range(0, len(tmp)):
        tmp[i] = numpy.convolve(tmp[i], kernel)[pix_width:-pix_width]
        tmpw[i] = numpy.convolve(tmpw[i], kernel)[pix_width:-pix_width]
    tmp = tmp.transpose()
    tmpw = tmpw.transpose()
    for i in range(0, len(tmp)):
        tmp[i] = numpy.convolve(tmp[i], kernel)[pix_width:-pix_width]
        tmpw[i] = numpy.convolve(tmpw[i], kernel)[pix_width:-pix_width]
    tmp = tmp.transpose()
    tmpw = tmpw.transpose()
    tmp[mask_array != 0] = (
        mask_array[mask_array != 0]
        * tmp[mask_array != 0]
        / tmpw[mask_array != 0]
        + (1 - mask_array[mask_array != 0]) * raster[mask_array != 0]
    )
    if preserve_boundary:
        for i in range(pix_width):
            tmp[i] = (
                i / pix_width * tmp[i] + (pix_width - i) / pix_width * raster[i]
            )
            tmp[-i - 1] = (
                i / pix_width * tmp[-i - 1]
                + (pix_width - i) / pix_width * raster[-i - 1]
            )
        for i in range(pix_width):
            tmp[:, i] = (
                i / pix_width * tmp[:, i]
                + (pix_width - i) / pix_width * raster[:, i]
            )
            tmp[:, -i - 1] = (
                i / pix_width * tmp[:, -i - 1]
                + (pix_width - i) / pix_width * raster[:, -i - 1]
            )
    return raster * (mask_array == 0) + tmp * (mask_array != 0)
