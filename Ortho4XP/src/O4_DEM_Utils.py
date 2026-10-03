import os
import json
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


def tile_is_land(lat, lon) -> bool:
    """Does the world mask say this 1x1 tile holds any LAND?

    THE ONE land/ocean predicate (issue #173): the mask indexing
    (``[89 - lat, (180 + lon) % 360]``) lived open-coded at both reading
    sites, and a third reader spelling it its own way is the
    census-wrapper defect.  ``True`` whenever the mask cannot be read --
    the conservative direction every caller wants: a land verdict only
    ever demands MORE of a source (a file fetched, a 404 refused), never
    less.
    """
    mask = _world_tiles()
    if mask is None:
        return True
    try:
        latitude = int(lat)
        longitude = int(lon)
    except (TypeError, ValueError):
        return True
    # The mask has one row per latitude from +89 down to -90.  Bounds are
    # checked rather than caught: ``mask[89 - 95]`` is a NEGATIVE index,
    # which numpy answers from the far side of the array instead of
    # raising -- a silently wrong land verdict for an impossible tile.
    if not -90 <= latitude <= 89:
        return True
    return bool(mask[89 - latitude, (180 + longitude) % 360])


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
        for (lat0, lon0) in itertools.product(
            (lat, lat - 1, lat + 1), (lon, lon - 1, lon + 1)
        ):
            if not tile_is_land(lat0, lon0):
                continue          # ocean only: zero-filled, never fetched
            if not ELEVATION_PROVIDERS.base_tile_is_cached(
                    source, lat0, (lon0 + 180) % 360 - 180,
                    prefer_coarse=prefer_coarse):
                return False
        return True
    except Exception:
        return False


################################################################################
# ---- THE .alt RASTER'S FRAME SIDECAR (#238) ---------------------------
#
# ``DEM.write_to_file`` emits a HEADERLESS raw float32 raster, so nothing
# in the ``.alt`` file tells a reader which patch of the world its
# samples span.  Readers therefore used to ASSUME the historic
# viewfinder frame -- [-0.01, 1.01]^2 on a 3673-square grid.  A tile
# whose base is a GeoTIFF or a densified inset grid does not have that
# frame: KASE +39-107 at ``elevation_level=10`` is 10834 square over
# about +-5.5 arc-seconds, and reading it as the viewfinder's put the
# samples 58 m away from the mesh they were baked into (#238, lanes
# kaseread368 / meshbox233).
#
# So the BUILD records its own working-grid frame beside the raster, at
# the one site that writes the raster (``DEM.write_frame_sidecar``), and
# readers resolve the frame through ``resolve_alt_frame`` below.  The
# viewfinder frame stays assumable -- but only for a raster whose grid
# actually IS the viewfinder's, and only when no sidecar contradicts it;
# anything else refuses rather than quietly reading the wrong metres.
ALT_FRAME_SIDECAR_SUFFIX = ".frame.json"
ALT_FRAME_SCHEMA = "o4.alt.frame/1"

# The frame itself.  ``tile_lat``/``tile_lon``/``epsg`` ride along as
# context and are cross-checked when present, but they are not the frame.
ALT_FRAME_KEYS = ("x0", "y0", "x1", "y1", "nxdem", "nydem")

# The source whose frame a header-less ``.alt`` may be assumed to carry.
# Its extent and grid are NOT restated here: ``build_combined_raster``
# derives them, and asking it (``info_only``, so no download and no
# array) keeps this file the only place either number lives.
VIEWFINDER_ALT_SOURCE = "View"

# The reader interprets the frame as tile-relative DEGREES.
ALT_FRAME_EPSG = 4326


class AltFrameRefused(RuntimeError):
    """A ``.alt`` raster whose frame cannot be established honestly."""


def alt_frame_sidecar_path(alt_filename):
    """The frame sidecar that belongs beside ``alt_filename``."""
    return str(alt_filename) + ALT_FRAME_SIDECAR_SUFFIX


def viewfinder_alt_frame(lat, lon):
    """The frame a viewfinder-grid ``.alt`` for this tile carries."""
    (epsg, x0, y0, x1, y1, _nodata, nxdem, nydem, _array) = (
        build_combined_raster(VIEWFINDER_ALT_SOURCE, lat, lon, True)
    )
    return {
        "schema": ALT_FRAME_SCHEMA,
        "x0": float(x0), "y0": float(y0),
        "x1": float(x1), "y1": float(y1),
        "nxdem": int(nxdem), "nydem": int(nydem),
        "epsg": int(epsg),
        "tile_lat": int(lat), "tile_lon": int(lon),
        "origin": "viewfinder-grid fallback (no sidecar)",
    }


def read_alt_frame_sidecar(alt_filename):
    """The sidecar beside ``alt_filename``, or ``None`` if there is none.

    A sidecar that is present but unreadable, or missing a frame key,
    REFUSES: it is the record the build was supposed to leave, and
    falling back past a broken one is how a wrong frame gets read
    silently (#238).
    """
    path = alt_frame_sidecar_path(alt_filename)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            frame = json.load(handle)
    except (OSError, ValueError) as error:
        raise AltFrameRefused(
            "%s is not readable as a frame sidecar: %s" % (path, error)
        ) from error
    if not isinstance(frame, dict):
        raise AltFrameRefused("%s does not hold a frame object" % path)
    missing = [key for key in ALT_FRAME_KEYS if key not in frame]
    if missing:
        raise AltFrameRefused(
            "%s carries no %s -- it does not describe a frame"
            % (path, ", ".join(missing))
        )
    frame = dict(frame)
    frame.setdefault("origin", path)
    return frame


def resolve_alt_frame(alt_filename, side, tile_lat, tile_lon):
    """The frame of a ``side``-square ``.alt``, or a refusal saying why.

    Order: the build's own sidecar, then -- only when there is none AND
    the grid is the viewfinder's -- the viewfinder frame.  A raster on
    any other grid with no sidecar has no knowable frame, so it refuses.
    """
    frame = read_alt_frame_sidecar(alt_filename)
    if frame is None:
        frame = viewfinder_alt_frame(tile_lat, tile_lon)
        if (frame["nxdem"], frame["nydem"]) != (side, side):
            raise AltFrameRefused(
                "%s holds a %d-square raster and carries no frame sidecar "
                "(%s). Only the viewfinder grid (%dx%d) can be assumed, so "
                "this raster's extent is unknowable -- rebuild the tile with "
                "a build that writes the sidecar, or pass the extent "
                "explicitly."
                % (alt_filename, side, alt_frame_sidecar_path(alt_filename),
                   frame["nxdem"], frame["nydem"])
            )
        return frame
    if (frame["nxdem"], frame["nydem"]) != (side, side):
        raise AltFrameRefused(
            "%s describes a %dx%d grid but %s holds a %d-square raster -- "
            "the sidecar does not belong to this raster"
            % (frame.get("origin"), frame["nxdem"], frame["nydem"],
               alt_filename, side)
        )
    epsg = frame.get("epsg")
    if epsg is not None and int(epsg) != ALT_FRAME_EPSG:
        raise AltFrameRefused(
            "%s records EPSG %s; the frame is read as tile-relative "
            "degrees (EPSG %d) and cannot be reprojected here"
            % (frame.get("origin"), epsg, ALT_FRAME_EPSG)
        )
    for key, expected in (("tile_lat", tile_lat), ("tile_lon", tile_lon)):
        recorded = frame.get(key)
        if recorded is not None and int(recorded) != int(expected):
            raise AltFrameRefused(
                "%s records %s %d but the raster is being read as tile "
                "%+03d%+04d -- wrong tile, or a stale sidecar"
                % (frame.get("origin"), key, int(recorded),
                   int(tile_lat), int(tile_lon))
            )
    return frame


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
        self.write_frame_sidecar(filename)
        return

    def write_frame_sidecar(self, filename):
        """Record THIS raster's own frame beside it (see ALT_FRAME_* below).

        The grid is read back off ``alt_dem.shape`` rather than off
        ``nxdem``/``nydem`` so the sidecar describes the BYTES that were
        just written -- ``tofile`` flattens the array, and a reader that
        trusted a stale pair of counters would stride the file wrong.
        ``tile_lat``/``tile_lon``/``epsg`` are context, written only when
        the object carries them; the FRAME keys are not optional.
        """
        nydem, nxdem = self.alt_dem.shape
        frame = {
            "schema": ALT_FRAME_SCHEMA,
            "x0": float(self.x0),
            "y0": float(self.y0),
            "x1": float(self.x1),
            "y1": float(self.y1),
            "nxdem": int(nxdem),
            "nydem": int(nydem),
        }
        for key, attribute in (
            ("tile_lat", "lat"), ("tile_lon", "lon"), ("epsg", "epsg"),
        ):
            value = getattr(self, attribute, None)
            if value is not None:
                frame[key] = int(value)
        with open(alt_frame_sidecar_path(filename), "w",
                  encoding="utf-8", newline="\n") as handle:
            json.dump(frame, handle, indent=1, sort_keys=True)
            handle.write("\n")
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
def _ensure_cell_elevation(source, lat, lon, lat0, lon0, verbose,
                           prefer_coarse):
    """:func:`ensure_elevation` for one cell of the 3x3 assembly, with a
    transport refusal NAMED by cell.  A NEIGHBOUR's failure refuses the
    tile too — its border band would otherwise be meshed at 0 m, a wall
    at the tile edge (never degrade silently) — and the message says it
    is a neighbour, so nobody hunts the home tile's own download."""
    try:
        return ensure_elevation(source, lat0, lon0, verbose,
                                prefer_coarse=prefer_coarse)
    except ElevationDownloadRefused as error:
        cell = "%+03d%+04d" % (lat0, lon0)
        if (lat0, lon0) == (lat, lon):
            role = "the tile itself"
        else:
            role = ("a NEIGHBOUR of tile %+03d%+04d, whose elevation "
                    "border band it supplies" % (lat, lon))
        raise ElevationDownloadRefused(
            "elevation cell %s (%s): %s" % (cell, role, error)) from error


def build_combined_raster(source, lat, lon, info_only, prefer_coarse=False):
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
        if not tile_is_land(lat0, lon0):
            tmparray = numpy.zeros((base, base), dtype=numpy.float32)
        elif _ensure_cell_elevation(
            source, lat, lon, lat0, (lon0 + 180) % 360 - 180, verbose,
            prefer_coarse,
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
class ElevationDownloadRefused(RuntimeError):
    """A base elevation download that failed on the TRANSPORT.

    Every attempt of :func:`http_request` died without an HTTP answer (a
    connection, DNS or TLS/certificate failure) or on a 5xx.  That says
    nothing about whether the source has the tile, and the historic
    ``return 0`` made the DEM loader substitute an ALL-ZERO raster and
    finish the build at 0 m with exit 0 (issue #121: the shipped beta.1
    exe on windows-latest under a broken TLS stack, run 36661272964 --
    "Min altitude: 0.0 , Max altitude: 0.0", BuildDone ok).  The alpha.2
    law -- broken = refuse, never degrade
    (docs/specs/proj-runtime-robustness-spec.md) -- applies: the tile
    build fails, naming the source, the URL and the last error.

    A 404/410 answer is NOT this: the server looked, the file is not
    there, and the historic 0 convention stands (the STRATEGY then
    decides whether an absent file is lawful for that tile -- see
    ``O4_Airport_Elevation_Insets.refuse_absent_base_archive``).

    Every OTHER non-2xx answer is this (issues #124/#173): a 403 from a
    CDN or a bot wall, a 407 from a proxy, a 429, a surfacing 3xx, a
    400 -- none of them says the file is not there, and the historic
    classifier read all of 400-409 and 300-309 as "Not Found" (and
    retried 410/429/451 six times before returning 0 with no refusal at
    all, because it recorded no ``last_failure`` for them).
    """


#: Attempts :func:`http_request` makes before it gives up.  Named so a
#: twin can shorten the loop instead of waiting out the 2+4+8+16+32 s
#: exponential back-off.
HTTP_REQUEST_ATTEMPT_CAP = 6

#: Seconds one base-tile GET may take.
HTTP_REQUEST_TIMEOUT_S = 10

#: Redirect hops :func:`http_request` follows before refusing (issue
#: #193).  Named so a twin can prove the bound instead of waiting out
#: ``requests``' own 30-hop default.  Five is far above what any real
#: service needs (viewfinderpanoramas.org's http -> https move is ONE)
#: and far below the cost of the default: measured 2026-10-02 against a
#: looping fake server, a redirect loop cost 31 requests per attempt x
#: :data:`HTTP_REQUEST_ATTEMPT_CAP` attempts = 186 requests and 62 s of
#: exponential back-off, and then refused with "failed on the
#: transport", never naming the redirect at all.
HTTP_REQUEST_REDIRECT_HOPS = 5

#: Statuses :func:`http_request` follows.  301/302 are the pair #193
#: names (viewfinderpanoramas.org answers 301 on http); 303/307/308 are
#: the same answer in later HTTP revisions, and a GET -- the only method
#: this transport issues -- is safe to repeat under all five.
HTTP_REQUEST_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


def http_request_get_following_redirects(session, url, source,
                                         verbose=False):
    """One GET, following at most :data:`HTTP_REQUEST_REDIRECT_HOPS`
    redirects EXPLICITLY; ``(response, chain)``.

    ``requests`` follows redirects on its own, up to thirty, and says
    nothing about it -- so a moved host worked by accident and a looping
    one burned 186 requests before refusing (both measured 2026-10-02;
    #193).  The follow is made explicit here so that it is BOUNDED, so
    that each hop is RECORDED (``chain``, lifted onto the response as
    ``o4_redirect_chain`` and printed), and so that exhausting the bound
    refuses NAMING THE REDIRECT instead of looking like a dead
    transport.  A same-host hop is the quiet case; a hop that changes
    host is followed too -- narrowing that would be a new refusal for
    any provider that later rides a CDN -- but says so on one line.

    A 3xx this function cannot follow (no ``Location``, a 304, a status
    outside :data:`HTTP_REQUEST_REDIRECT_STATUSES`) is returned AS IS,
    so the one outcome classifier still judges it.
    """
    from urllib.parse import urljoin, urlparse

    chain = []
    current = url
    for _hop in range(HTTP_REQUEST_REDIRECT_HOPS + 1):
        response = session.get(current, timeout=HTTP_REQUEST_TIMEOUT_S,
                               allow_redirects=False)
        status = int(response.status_code)
        location = (response.headers or {}).get("Location")
        if status not in HTTP_REQUEST_REDIRECT_STATUSES or not location:
            if chain:
                response.o4_redirect_chain = list(chain)
                UI.vprint(1, "    ", source, "followed", len(chain),
                          "redirect(s):", " -> ".join(chain))
            else:
                response.o4_redirect_chain = []
            return (response, chain)
        target = urljoin(current, location)
        if urlparse(target).hostname != urlparse(current).hostname:
            UI.vprint(1, "    ", source, "redirect leaves the host:",
                      current, "->", target)
        elif verbose:
            UI.vprint(2, "    ", source, "redirected", status, "to", target)
        response.close()
        chain.append("%d %s" % (status, target))
        current = target
    # The bound is spent and the host is still redirecting: it will not
    # serve this object, and repeating identical GETs cannot change that
    # (the UNAVAILABLE precedent a few lines below -- a server that never
    # looked for the file is refused now, not five times more).
    raise ElevationDownloadRefused(
        "the %s elevation download of %s was REDIRECTED more than %d "
        "times (%s) -- the host will not serve this object, so this "
        "build will not fall back to an all-zero elevation raster; "
        "check the provider's download_url_template in its .elv"
        % (source, url, HTTP_REQUEST_REDIRECT_HOPS, " -> ".join(chain)))


def http_request(url, source, verbose=False):
    # Guarded import of the process-wide throughput meter (sanctioned
    # pattern copied from O4_OSM_Extracts): telemetry must never break a
    # download, so a missing engine leaves METER as None and every feed
    # is skipped.
    try:
        from o4_engine import download_meter as METER
    except Exception:
        METER = None
    # Imported lazily for the same reason every other reference in this
    # module is: O4_Airport_Elevation_Insets imports THIS module at
    # module level.  It owns the ONE answer-outcome classifier (SQ3: a
    # second convention at a call site is the defect, not a refinement).
    import O4_Airport_Elevation_Insets as ELEVATION_OUTCOMES
    s = requests.Session()
    tentative = 0
    last_failure = None
    while True:
        # Cancellation: the user pressed Stop.  Abort before spending
        # another request on this source and match http_request's
        # existing failure convention -- a falsy 0 return, which every
        # caller already treats as "download failed".
        if UI.red_flag:
            return 0
        try:
            t0 = time.time()
            (r, _redirects) = http_request_get_following_redirects(
                s, url, source, verbose)
            elapsed = time.time() - t0
            # THE ONE OUTCOME LAW, classified on the STATUS INTEGER
            # (issues #124/#173).  The historic test was a substring of
            # ``str(response)``: "[40" matched 400-409, so a CDN 403 and
            # a proxy 407 both printed "Server said 'Not Found'" and
            # returned 0 -- which the DEM loader turns into an ALL-ZERO
            # raster for that cell.  A 410/429/451 matched nothing at
            # all, so it was retried six times and then returned 0
            # SILENTLY, with no ``last_failure`` to refuse on.
            outcome = ELEVATION_OUTCOMES.http_answer_outcome(r.status_code)
            if outcome == ELEVATION_OUTCOMES.HTTP_OUTCOME_OK:
                # Feed the throughput meter with this completed fetch so
                # the build-time ETA prices elevation downloads from
                # measurement.  Never raise from telemetry.
                if METER is not None:
                    try:
                        METER.record(len(r.content), elapsed)
                    except Exception:
                        pass
                return r
            elif outcome == ELEVATION_OUTCOMES.HTTP_OUTCOME_ABSENT:
                if verbose:
                    UI.vprint(2, "    Server said 'Not Found'")
                return 0
            elif outcome == ELEVATION_OUTCOMES.HTTP_OUTCOME_UNAVAILABLE:
                # The host refused to serve THIS CLIENT.  It never looked
                # for the file, so this can never become a 0: refuse now,
                # without spending five more identical refusals.
                raise ElevationDownloadRefused(
                    "the %s elevation download of %s was REFUSED by the "
                    "server with status %d -- that says nothing about "
                    "whether the tile exists, so this build will not "
                    "fall back to an all-zero elevation raster; check "
                    "for a proxy, a bot wall or an expired credential"
                    % (source, url, r.status_code))
            else:
                last_failure = "status %d" % r.status_code
                if verbose:
                    UI.vprint(
                        2, "    Server answered", r.status_code,
                        "- transient, retrying."
                    )
        except ElevationDownloadRefused:
            # OUR OWN refusal, raised a few lines above for a host that
            # would not serve this client.  It must pass through: the
            # broad ``except`` below used to catch it, log it as a
            # transport failure and RETRY it five more times before
            # raising a vaguer refusal of its own.
            raise
        except Exception as e:
            last_failure = "%s: %s" % (type(e).__name__, e)
            # ALWAYS printed (it used to need verbose): the transport
            # error is the one line that says WHY the elevation is missing.
            UI.vprint(1, "    ", source, "download failed:", last_failure)
        tentative += 1
        if tentative >= HTTP_REQUEST_ATTEMPT_CAP:
            if last_failure is not None and not UI.red_flag:
                raise ElevationDownloadRefused(
                    "the %s elevation download of %s failed %d times on "
                    "the transport (last: %s) -- REFUSING to build this "
                    "tile on an all-zero elevation raster; check the "
                    "network / TLS (antivirus or proxy HTTPS inspection) "
                    "and rebuild" % (source, url, tentative, last_failure))
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
