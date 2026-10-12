"""Base-tile fallback: another source when the configured one is down.

THE RULE (issue #561).  A whole base cell comes from, in this order:

1. the configured source's cached file, when it is valid;
2. the configured source's download;
3. ONLY when that download died on the TRANSPORT after its retries
   (``O4_DEM_Utils.ElevationTransportRefused``): each fallback source in
   ``fallback_rank`` order -- a ``role=base`` definition whose ``.elv``
   carries ``fallback_rank=N`` (``N`` >= 1, lowest first).

A source that answered "not there" for a land cell, refused this client
or looped on redirects still refuses the tile (issues #173, #124, #193):
those are defects to see, not outages to route around.  When every
source fails the tile is refused, naming each source and its failure --
never meshed at 0 m.

PROVENANCE.  A fallback file lives at its OWN cache path (the fallback
strategy's ``tile_cache_path``, keyed by the fallback's CODE), never at
the configured source's.  A reader takes it only where the configured
file is absent (:func:`cell_file`), so every build asks the configured
source again first, and once it answers the fallback file is never read
again.  Each build that reads a substituted cell says so on one log
line, and the cell is listed in the airport freshness stamp
(``auto_patch.provenance.dem_fingerprint``), so a patch solved beside a
substituted cell is rebuilt when the configured source is back.

SEAM.  A substituted cell is tied to its cached configured neighbours
(``base_seam``) when it is read.
"""

import os
import time
from urllib.parse import urlparse

import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_Tile_Failures as FAIL
import O4_UI_Utils as UI

from elevation_access import base_seam
from elevation_access.base_tiles import cached_elevation_file_is_valid
from elevation_access.definitions import ROLE_BASE, _parse_float
from elevation_access.registry import ACCESS_STRATEGIES

__all__ = [
    "FALLBACK_RANK_KEY",
    "UNREACHABLE_MEMORY_S",
    "cell_file",
    "ensure_tile_or_fallback",
    "fallback_definitions",
    "forget_unreachable_sources",
    "read_base_cell",
    "source_label",
]

#: The ``.elv`` key that makes a ``role=base`` definition a fallback, and
#: orders the fallbacks (1 is asked first; absent or 0 = not a fallback).
FALLBACK_RANK_KEY = "fallback_rank"

#: Seconds a host that just failed on the transport is not asked again.
#: One archive serves many cells, and each refusal costs the whole retry
#: schedule (about two minutes): the other cells of the same build go
#: straight to the fallback.  It expires, so a long-lived engine process
#: asks the configured source again on a later build.
UNREACHABLE_MEMORY_S = 600.0

# host (or source CODE when the strategy publishes no URL) ->
# (time.monotonic() of the failure, the failure in words)
_unreachable = {}
# host -> whether that failure was a PROXY's refusal (O4_Tile_Failures).
_proxied = {}


def forget_unreachable_sources():
    """Drop the memory of failed hosts (a twin's reset)."""
    _unreachable.clear()
    _proxied.clear()


def source_label(definition):
    """The name a log line gives a source: ``display_name``, else CODE."""
    return str(definition.get("display_name") or definition.get("code"))


def _cell_label(lat, lon):
    return "%+03d%+04d" % (lat, lon)


def fallback_definitions(providers):
    """The fallback definitions of a parsed registry (``CODE ->
    definition``), first to ask first."""
    ranked = []
    for definition in providers.values():
        rank = _parse_float(definition.get(FALLBACK_RANK_KEY), 0.0) or 0.0
        if definition.get("role") != ROLE_BASE or rank <= 0:
            continue
        if definition.get("access_strategy") not in ACCESS_STRATEGIES:
            continue
        ranked.append((rank, definition["code"], definition))
    return [definition for (_rank, _code, definition) in sorted(
        ranked, key=lambda entry: entry[:2])]


def _strategy(definition):
    return ACCESS_STRATEGIES[definition["access_strategy"]]()


def _cache_path(strategy, definition, lat, lon):
    path_of = getattr(strategy, "tile_cache_path", None)
    return path_of(definition, lat, lon) if path_of else None


def cell_file(configured_path, lat, lon, providers):
    """Which file a build reads for one base cell: ``(path, fallback)``.

    The configured file whenever it is valid (``fallback`` is ``None``);
    else the first fallback whose own cache file is valid, with its
    definition; else the configured path unchanged, for the reader to
    report as it always did.
    """
    if not configured_path or cached_elevation_file_is_valid(configured_path):
        return (configured_path, None)
    for definition in fallback_definitions(providers):
        path = _cache_path(_strategy(definition), definition, lat, lon)
        if path and cached_elevation_file_is_valid(path):
            return (path, definition)
    return (configured_path, None)


def _neighbour_edge_reader(source, lat, lon, shape):
    """``side -> shared posts`` from the cached CONFIGURED neighbours."""
    steps = {"north": (1, 0), "south": (-1, 0), "west": (0, -1),
             "east": (0, 1)}

    def neighbour_edge(side):
        (north, east) = steps[side]
        lat0 = lat + north
        lon0 = (lon + east + 180) % 360 - 180
        path = FNAMES.elevation_data(source, lat0, lon0)
        if lat0 < -90 or lat0 > 89 or not path:
            return None
        if not cached_elevation_file_is_valid(path):
            return None
        neighbour = DEM.read_elevation_from_file(
            path, lat0, lon0, False, shape[0])[-1]
        if neighbour is None or neighbour.shape != shape:
            UI.vprint(
                1, "    Elevation cell", _cell_label(lat, lon),
                "is not tied to its", side, "neighbour",
                _cell_label(lat0, lon0) + ": that file is on a different "
                "grid, so the edge between them may show a step.")
            return None
        return base_seam.shared_edge_of_neighbour(neighbour, side)

    return neighbour_edge


def read_base_cell(source, lat, lon, providers, info_only=False,
                   base_if_error=3601, substitutions=None):
    """``O4_DEM_Utils.read_elevation_from_file`` for one base cell of the
    legacy keyword ``source``, reading the fallback file where the cell
    is substituted and tying it to its configured neighbours.
    ``providers`` is the parsed registry (``CODE -> definition``).

    ``substitutions`` (a list, optional) receives one record per
    substituted cell -- ``{"cell", "code", "path"}`` -- for the caller's
    provenance.
    """
    configured_path = FNAMES.elevation_data(source, lat, lon)
    (path, fallback) = cell_file(configured_path, lat, lon, providers)
    result = DEM.read_elevation_from_file(
        path, lat, lon, info_only, base_if_error)
    if fallback is None:
        return result
    if substitutions is not None:
        # ``source`` / ``fallback`` are the names the tile's closing note
        # shows (RULINGS 2026-10-12e); the fingerprint reads the first
        # three keys only.
        substitutions.append({"cell": _cell_label(lat, lon),
                              "code": fallback["code"], "path": path,
                              "source": str(source),
                              "fallback": source_label(fallback)})
    cell = result[-1]
    if info_only or cell is None:
        return result
    tied = base_seam.tie_cell_to_neighbours(
        cell, _neighbour_edge_reader(source, lat, lon, cell.shape),
        nodata=result[5])
    for (side, closed_m) in tied:
        UI.vprint(
            1, "    Elevation cell", _cell_label(lat, lon),
            "(" + source_label(fallback) + ") tied to its", side,
            "neighbour: edge difference up to %.1f m closed over %d posts."
            % (closed_m, base_seam.TIE_FEATHER_POSTS))
    return result


def _source_host(strategy, definition, lat, lon):
    url_of = getattr(strategy, "download_url", None)
    if url_of is not None:
        try:
            return urlparse(url_of(definition, lat, lon)).hostname or ""
        except Exception:
            pass
    return str(definition.get("code"))


def _remembered_failure(host):
    remembered = _unreachable.get(host)
    if remembered is None:
        return None
    (when, failure) = remembered
    if time.monotonic() - when > UNREACHABLE_MEMORY_S:
        del _unreachable[host]
        return None
    return failure


def ensure_tile_or_fallback(strategy, definition, lat, lon, verbose,
                            providers, before_fallback=None):
    """``strategy.ensure_tile`` under THE RULE above; ``0`` or ``1``.

    ``providers`` is the parsed registry the fallbacks are read from;
    ``before_fallback`` (optional, no arguments) is called once before
    the first fallback is asked -- the pipeline's remote-read set-up.

    Raises ``O4_DEM_Utils.ElevationDownloadRefused`` exactly where the
    strategy alone did, except for a transport failure that a fallback
    source could cover.
    """
    cache_path = _cache_path(strategy, definition, lat, lon)
    if cache_path and cached_elevation_file_is_valid(cache_path):
        return strategy.ensure_tile(definition, lat, lon, verbose)
    host = _source_host(strategy, definition, lat, lon)
    failure = _remembered_failure(host)
    if failure is None:
        try:
            return strategy.ensure_tile(definition, lat, lon, verbose)
        except DEM.ElevationTransportRefused as error:
            failure = str(error)
            _unreachable[host] = (time.monotonic(), failure)
            _proxied[host] = FAIL.is_proxy_refusal(error)
    else:
        UI.vprint(
            1, "    ", source_label(definition), "did not answer earlier "
            "in this run; it is not asked again for cell",
            _cell_label(lat, lon) + ".")
    if UI.red_flag:
        return 0
    if before_fallback is not None:
        before_fallback()
    return _take_fallback(definition, lat, lon, failure, verbose, providers,
                          _proxied.get(host, False))


def _take_fallback(configured, lat, lon, configured_failure, verbose,
                   providers, configured_proxied=False):
    cell = _cell_label(lat, lon)
    failures = [(source_label(configured), configured_failure)]
    # Whether EVERY source that was asked was refused by a proxy: the
    # user's own proxy or VPN, not the servers (the refusal then says so).
    proxied = [configured_proxied]
    for definition in fallback_definitions(providers):
        label = source_label(definition)
        strategy = _strategy(definition)
        try:
            if not strategy.covers(definition, lat, lon):
                failures.append((label, "does not cover this cell"))
                continue
            UI.vprint(
                1, "    ", source_label(configured), "did not answer; "
                "asking", label, "for elevation cell", cell + ".")
            obtained = strategy.ensure_tile(definition, lat, lon, verbose)
        except Exception as error:
            failures.append((label, "%s: %s" % (type(error).__name__, error)))
            proxied.append(FAIL.is_proxy_refusal(error))
            continue
        if obtained:
            UI.lvprint(
                1, "    %s did not answer; elevation cell %s taken from %s "
                "instead (%s). %s is asked again on the next build. "
                "Reason: %s"
                % (source_label(configured), cell, label,
                   _cache_path(strategy, definition, lat, lon),
                   source_label(configured), configured_failure))
            return 1
        failures.append((label, "has no data for this cell"))
    refusal = DEM.ElevationTransportRefused(
        "elevation cell %s could not be fetched from any source -- "
        "REFUSING to build this tile on an all-zero elevation raster. %s "
        "Check the network connection (a proxy, or antivirus HTTPS "
        "inspection, can block every source at once) and build again."
        % (cell, " ".join("%s: %s." % (label, str(text).rstrip("."))
                          for (label, text) in failures)))
    if all(proxied):
        refusal.failure_code = "proxy_refused"
    raise refusal
