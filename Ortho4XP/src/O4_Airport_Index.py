"""Offline airport search index built from X-Plane's Global Airports.

This module builds a small, fast, offline search index of airports from
X-Plane's ``apt.dat`` (the Global Airports gateway data set).  The real
``apt.dat`` is hundreds of megabytes, so parsing is done strictly
line-by-line (streaming) and never loads the whole file into memory.

The public surface is intentionally tiny and stdlib-only (no tkinter/Qt,
no network access, no printing):

* :func:`find_apt_dats` -- locate the Global Airports ``apt.dat`` file(s).
* :func:`build_index`   -- stream-parse ``apt.dat`` into a compact cache.
* :func:`load_index`    -- fast reload from that cache.
* :func:`index_count`   -- the cache's recorded airport count (header only).
* :func:`index_is_stale` -- decide whether the cache needs rebuilding.

Searching the index by code or name is :mod:`O4_Airport_Search` (#543); a
typed coordinate or tile key is :mod:`O4_Coordinate_Query` (#1317).

This module is the SINGLE airport-index implementation every front end
uses: the Qt map consumes it in-process, and the macOS application asks
for it over the engine protocol's ``airport_index`` command (which builds
the cache off the transport read loop and replies with the cache path --
the application only READS the TSV, it never parses ``apt.dat`` itself;
see docs/specs/airport-index-engine-command-spec.md).

The cache is a compact TSV file (see :func:`build_index`) so reloads are
cheap and the on-disk format is easy to inspect.

Cache format v6 and the freshness contract
-------------------------------------------
The cache header is ``O4AIRPORTIDX 6 <count>``.  Immediately after the
header, :func:`build_index` writes one ``#SRC <mtime_ns> <size_bytes>
<path>`` line for every source ``apt.dat`` it actually read (the path is
written last because it may contain spaces; ``mtime_ns`` comes from
:func:`os.stat`'s ``st_mtime_ns`` for full precision, and the byte size is
recorded as a second freshness signal).  The tab-separated data rows
carry a trailing ``category`` column since v3, the airport's four
extent columns since v5 (v4 changed only what gets INDEXED, not the row
shape) and its size -- longest runway in metres and size class
(:mod:`O4_Airport_Rank`) -- since v6.  :func:`load_index`
transparently loads v1 (no ``#SRC`` lines) through v6 caches, skipping any
``#SRC`` lines, and ignores columns after the ones it knows.  :func:`index_is_stale` reads only the header and ``#SRC``
lines to report whether the recorded sources still match the requested
ones (same set of paths, and identical ``st_mtime_ns`` and size for each),
so callers can rebuild only when something has actually changed on disk.
"""

import os
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Tuple

import O4_Airport_Rank as RANK

__all__ = [
    "AirportEntry",
    "find_apt_dats",
    "iter_airports",
    "build_index",
    "load_index",
    "index_count",
    "index_is_stale",
]

# Magic header written as the first line of the cache file.  The integer
# is a format version so a future change can invalidate old caches.
#
# Version 2 adds ``#SRC <mtime_ns> <size_bytes> <path>`` lines right after
# the header, recording every source file used to build the index so
# :func:`index_is_stale` can tell when a rebuild is needed.
#
# Version 3 adds the trailing per-airport ``category`` column.
#
# Version 4 changes what gets indexed, not the row shape: water runways
# (row 101) now provide a fallback position, so seaplane bases that carry
# no datum metadata are indexed instead of skipped, and
# :func:`find_apt_dats` looks in one more place (the shipped default
# scenery) and at both ``Earth nav data`` spellings.  Both change the
# CONTENT a source set produces, so v3 caches must rebuild once.
#
# Version 5 appends the airport's EXTENT -- four columns ``min_lat min_lon
# max_lat max_lon`` spanning its boundary (row 130) nodes, runway ends,
# helipads and datum -- so a code can select every tile the airport
# touches, not only the tile of its datum point (issue #542).
#
# Version 6 appends two SIZE columns, ``runway_m size_class``: the
# longest runway (metres, any surface) and the O4_Airport_Rank class the
# map labels and the progress-row titles rank airports by (#815, #817).
_CACHE_MAGIC = "O4AIRPORTIDX"
_CACHE_VERSION = 6

# Data-row column counts load_index accepts: v1/v2 (no category), v3/v4
# (category); from v5 (category + extent) on, any width of 11 or more --
# the columns a reader knows are read, later ones ignored.
_ROW_WIDTHS = (6, 7)
_EXTENT_WIDTH = 11
_SIZE_WIDTH = 13

# Prefix marking a source-file provenance line in a v2+ cache.
_SRC_PREFIX = "#SRC"

# The v3 per-airport category values (the bathymetry gate's anchor
# checkboxes select among these):
#   icao_airport  -- apt.dat type 1 with an ``icao_code`` metadata row
#   airport       -- apt.dat type 1 without one (small strips, local IDs)
#   seaplane_base -- apt.dat type 16
#   heliport      -- apt.dat type 17
AIRPORT_CATEGORIES = (
    "icao_airport", "airport", "seaplane_base", "heliport",
)


@dataclass
class AirportEntry:
    """A single indexed airport.

    Attributes:
        code: ICAO code (or the ``apt.dat`` header airport ID when no
            ``icao_code`` metadata row is present).
        name: Human-readable airport name.
        city: City the airport serves, or ``""`` if unknown.
        country: Country the airport is in, or ``""`` if unknown.
        lat: Reference latitude in decimal degrees.
        lon: Reference longitude in decimal degrees.
        category: One of :data:`AIRPORT_CATEGORIES`.  Rows loaded from a
            pre-v3 cache carry the default (they predate the category
            column; ``index_is_stale`` rebuilds such caches anyway).
        extent: ``(min_lat, min_lon, max_lat, max_lon)`` over the
            airport's boundary nodes, runway ends, helipads and datum, or
            ``None`` (pre-v5 rows): the airport is then its point.
        runway_m: Longest runway, whole metres, any surface (0: none, or
            a pre-v6 row).
        size_class: :func:`O4_Airport_Rank.size_class` (0 = largest);
            pre-v6 rows read :data:`O4_Airport_Rank.UNKNOWN_SIZE_CLASS`.
    """

    code: str
    name: str
    city: str
    country: str
    lat: float
    lon: float
    category: str = "icao_airport"
    extent: Optional[Tuple[float, float, float, float]] = None
    runway_m: int = 0
    size_class: int = RANK.UNKNOWN_SIZE_CLASS


# ---------------------------------------------------------------------------
# Locating apt.dat
# ---------------------------------------------------------------------------
# The folders (relative to the X-Plane root) that may hold a Global
# Airports ``apt.dat``, highest priority first.  The ``Earth nav data``
# level is appended per spelling by :func:`find_apt_dats`.
_APT_DAT_FOLDERS = (
    ("Global Scenery", "Global Airports"),                    # XP12
    ("Custom Scenery", "Global Airports"),                    # XP11
    ("Resources", "default scenery", "default apt dat"),      # shipped default
)

# Both spellings of the nav-data folder, in preference order.  Linux is
# case-sensitive and packs in the wild carry either.
_NAV_DATA_SPELLINGS = ("Earth nav data", "Earth Nav Data")


def find_apt_dats(xplane_dir: str) -> List[str]:
    """Return existing Global Airports ``apt.dat`` paths under ``xplane_dir``.

    Three well-known locations are checked, in priority order:

    1. ``<xp>/Global Scenery/Global Airports/...`` (XP12)
    2. ``<xp>/Custom Scenery/Global Airports/...`` (XP11)
    3. ``<xp>/Resources/default scenery/default apt dat/...`` (the
       airports X-Plane itself ships, the last resort when neither
       Global Airports pack is installed)

    Each is tried with both nav-data spellings (``Earth nav data`` and
    ``Earth Nav Data``), and only the FIRST spelling that exists is taken:
    on a case-insensitive volume both answer for the same file, and a
    duplicated path would make :func:`build_index` stream the same 380 MB
    file twice.  The same file reached through two candidates (a symlinked
    pack) is likewise emitted once.

    Args:
        xplane_dir: Path to the X-Plane installation root.

    Returns:
        A list of the ``apt.dat`` paths that actually exist, in the order
        above.  Returns ``[]`` when none are found.
    """
    found: List[str] = []
    seen: set = set()
    for folder in _APT_DAT_FOLDERS:
        for nav_data in _NAV_DATA_SPELLINGS:
            path = os.path.join(xplane_dir, *folder, nav_data, "apt.dat")
            if not os.path.isfile(path):
                continue
            key = os.path.normcase(os.path.realpath(path))
            if key not in seen:
                seen.add(key)
                found.append(path)
            break   # this candidate answered; never take its other spelling
    return found


# ---------------------------------------------------------------------------
# apt.dat parsing (streaming)
# ---------------------------------------------------------------------------
# Airport header row codes.
_HEADER_CODES = frozenset(("1", "16", "17"))
# Chain node row codes (plain / bezier, open / closed / end of chain).
_NODE_CODES = frozenset(("111", "112", "113", "114", "115", "116"))


def _airport_category(header_code: str, saw_icao_code: bool) -> str:
    """Map an apt.dat header row code (+ icao_code presence) to a
    :data:`AIRPORT_CATEGORIES` value."""
    if header_code == "16":
        return "seaplane_base"
    if header_code == "17":
        return "heliport"
    return "icao_airport" if saw_icao_code else "airport"


def _flush_airport(
    code: Optional[str],
    name: str,
    city: str,
    country: str,
    meta_lat: Optional[float],
    meta_lon: Optional[float],
    rwy_lat: Optional[float],
    rwy_lon: Optional[float],
    category: str = "icao_airport",
    extent: Optional[List[float]] = None,
    runways: Tuple[float, float] = (0.0, 0.0),
) -> Optional[AirportEntry]:
    """Assemble an :class:`AirportEntry` from an airport's accumulated rows.

    Metadata datum coordinates win over the runway/helipad fallback; the
    position is folded into ``extent`` (a ``[min_lat, min_lon, max_lat,
    max_lon]`` accumulator, or ``None``).  ``runways`` is ``(longest_m,
    longest_paved_m)``.  Returns ``None`` when no code or no usable
    coordinate is available, so the caller can skip the airport.
    """
    if not code:
        return None
    lat = meta_lat if meta_lat is not None else rwy_lat
    lon = meta_lon if meta_lon is not None else rwy_lon
    if lat is None or lon is None:
        return None
    extent = _extend(extent, lat, lon)
    (longest_m, paved_m) = runways
    return AirportEntry(code=code, name=name, city=city, country=country,
                        lat=lat, lon=lon, category=category,
                        extent=tuple(extent),
                        runway_m=int(round(longest_m)),
                        size_class=RANK.size_class(category, longest_m,
                                                   paved_m))


def _runway_length(row: List[str], ends: Tuple[int, int, int, int]) -> float:
    """Metres between a runway row's two ends (fields ``ends``: lat1,
    lon1, lat2, lon2), 0 for a short or malformed row."""
    if len(row) <= max(ends):
        return 0.0
    values = [_parse_float(row[i]) for i in ends]
    if any(v is None for v in values):
        return 0.0
    return RANK.runway_length_m(*values)


def _extend(extent: Optional[List[float]], lat: float,
            lon: float) -> List[float]:
    """Grow a ``[min_lat, min_lon, max_lat, max_lon]`` accumulator (or
    start one from ``None``) to cover ``(lat, lon)``."""
    if extent is None:
        return [lat, lon, lat, lon]
    extent[0] = min(extent[0], lat)
    extent[1] = min(extent[1], lon)
    extent[2] = max(extent[2], lat)
    extent[3] = max(extent[3], lon)
    return extent


def _extend_from(extent: Optional[List[float]], row: List[str],
                 lat_index: int, lon_index: int) -> Optional[List[float]]:
    """``_extend`` with the coordinate read from ``row`` (a short or
    malformed row leaves the accumulator unchanged)."""
    if len(row) <= max(lat_index, lon_index):
        return extent
    lat = _parse_float(row[lat_index])
    lon = _parse_float(row[lon_index])
    if lat is None or lon is None:
        return extent
    return _extend(extent, lat, lon)


def _parse_float(value: str) -> Optional[float]:
    """Return ``value`` parsed as ``float`` or ``None`` if malformed."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iter_airports(path: str) -> Iterator[AirportEntry]:
    """Yield :class:`AirportEntry` objects streamed from one ``apt.dat``.

    The file is read one line at a time (never fully into memory).  Rows
    are interpreted as follows:

    * ``1``/``16``/``17`` -- airport header, ``<code> <elev> ... <ID> <Name>``.
    * ``1302 <key> <value>`` -- metadata; keys ``icao_code`` (overrides the
      header ID), ``city``, ``country``, ``datum_lat``, ``datum_lon``.
    * ``100`` -- land runway; end-1 lat/lon are fields 9 and 10 (0-based).
    * ``101`` -- water runway; end-1 lat/lon are fields 4 and 5 (0-based).
    * ``102`` -- helipad; lat/lon are fields 2 and 3 (0-based).
    * ``111``-``116`` after a ``130`` boundary header -- boundary nodes;
      lat/lon are fields 1 and 2.  They, every runway end and every
      helipad grow the airport's ``extent``.
    * Every ``100``/``101`` row's length (end to end) feeds the airport's
      size: the longest runway, and the longest hard one (row 100 field 2
      is the surface code).

    An airport with no metadata datum and no runway/helipad coordinate is
    skipped (not yielded).
    """
    # Accumulator state for the airport currently being parsed.
    have_airport = False
    code: Optional[str] = None
    name = ""
    city = ""
    country = ""
    header_code = "1"
    saw_icao_code = False
    meta_lat: Optional[float] = None
    meta_lon: Optional[float] = None
    rwy_lat: Optional[float] = None
    rwy_lon: Optional[float] = None
    extent: Optional[List[float]] = None
    in_boundary = False
    longest_m = 0.0
    paved_m = 0.0

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            row = line.split()
            row_code = row[0]

            if row_code in _HEADER_CODES:
                # New airport begins: flush the previous one first.
                if have_airport:
                    entry = _flush_airport(
                        code, name, city, country,
                        meta_lat, meta_lon, rwy_lat, rwy_lon,
                        _airport_category(header_code, saw_icao_code),
                        extent, (longest_m, paved_m))
                    if entry is not None:
                        yield entry
                # Reset accumulators for the new header.
                have_airport = True
                city = ""
                country = ""
                header_code = row_code
                saw_icao_code = False
                meta_lat = None
                meta_lon = None
                rwy_lat = None
                rwy_lon = None
                extent = None
                in_boundary = False
                longest_m = 0.0
                paved_m = 0.0
                # Header layout: 1 <elev> <dep> <dep> <ID> <Name...>
                code = row[4] if len(row) >= 5 else None
                name = " ".join(row[5:]) if len(row) >= 6 else ""
                continue

            if not have_airport:
                # Rows before the first header (e.g. file preamble) are
                # not part of any airport; ignore them.
                continue

            # Extent: boundary nodes (a node row continues the chain its
            # header opened; any other row closes it), runway ends and
            # helipads.  The position fallbacks below are unchanged.
            if row_code in _NODE_CODES:
                if in_boundary:
                    extent = _extend_from(extent, row, 1, 2)
                continue
            in_boundary = row_code == "130"
            if row_code == "100":
                extent = _extend_from(extent, row, 9, 10)
                extent = _extend_from(extent, row, 18, 19)
                length = _runway_length(row, (9, 10, 18, 19))
                longest_m = max(longest_m, length)
                if len(row) > 2 and RANK.is_paved(row[2]):
                    paved_m = max(paved_m, length)
            elif row_code == "101":
                extent = _extend_from(extent, row, 4, 5)
                extent = _extend_from(extent, row, 7, 8)
                longest_m = max(longest_m,
                                _runway_length(row, (4, 5, 7, 8)))
            elif row_code == "102":
                extent = _extend_from(extent, row, 2, 3)

            if row_code == "1302" and len(row) >= 3:
                key = row[1]
                value = " ".join(row[2:])
                if key == "icao_code":
                    if value:
                        code = value
                        saw_icao_code = True
                elif key == "city":
                    city = value
                elif key == "country":
                    country = value
                elif key == "datum_lat":
                    parsed = _parse_float(value)
                    if parsed is not None:
                        meta_lat = parsed
                elif key == "datum_lon":
                    parsed = _parse_float(value)
                    if parsed is not None:
                        meta_lon = parsed
                continue

            # Runway / helipad coordinate fallbacks -- only the FIRST such
            # row is used (datum metadata still overrides these anyway).
            # All three share the ``rwy_lat is None`` gate, so whichever
            # kind of runway comes first in the airport's block wins.
            if row_code == "100" and rwy_lat is None and len(row) >= 11:
                lat = _parse_float(row[9])
                lon = _parse_float(row[10])
                if lat is not None and lon is not None:
                    rwy_lat = lat
                    rwy_lon = lon
                continue

            # Water runway: `101 <width> <buoys> <end1> <lat> <lon> ...`.
            # Without this a seaplane base carrying no datum metadata has
            # no position at all and is skipped entirely.
            if row_code == "101" and rwy_lat is None and len(row) >= 6:
                lat = _parse_float(row[4])
                lon = _parse_float(row[5])
                if lat is not None and lon is not None:
                    rwy_lat = lat
                    rwy_lon = lon
                continue

            if row_code == "102" and rwy_lat is None and len(row) >= 4:
                lat = _parse_float(row[2])
                lon = _parse_float(row[3])
                if lat is not None and lon is not None:
                    rwy_lat = lat
                    rwy_lon = lon
                continue

    # Flush the trailing airport at end-of-file.
    if have_airport:
        entry = _flush_airport(
            code, name, city, country,
            meta_lat, meta_lon, rwy_lat, rwy_lon,
            _airport_category(header_code, saw_icao_code), extent,
            (longest_m, paved_m))
        if entry is not None:
            yield entry


def iter_airports(path: str) -> Iterator[AirportEntry]:
    """Stream one ``apt.dat``'s airports — THE apt.dat parser.

    :func:`build_index` drains this over the Global Airports sources.
    Callers surveying a SINGLE pack's own ``apt.dat`` (a handful of rows,
    no cache worth writing — see :mod:`O4_Custom_Scenery`) consume it
    directly rather than growing a second parser: one apt.dat reader in
    the engine, whatever the caller.
    """
    return _iter_airports(path)


# ---------------------------------------------------------------------------
# Cache (build / load)
# ---------------------------------------------------------------------------
def _sanitize(value: str) -> str:
    """Strip TSV-hostile characters (tabs/newlines) from a cache field."""
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def build_index(apt_dat_paths: Iterable[str], cache_file: str) -> int:
    """Stream-parse ``apt.dat`` file(s) into a compact TSV cache.

    Each airport is parsed once; when the same airport code appears in more
    than one file the FIRST occurrence wins (so callers should list the
    highest-priority file -- typically the XP12 path -- first).

    The cache is a UTF-8 TSV file whose first line is::

        O4AIRPORTIDX 6 <count>

    followed by one ``#SRC <mtime_ns> <size_bytes> <path>`` line per source
    file actually read, then one tab-separated ``code<TAB>name<TAB>city<TAB>
    country<TAB>lat<TAB>lon<TAB>category<TAB>min_lat<TAB>min_lon<TAB>
    max_lat<TAB>max_lon<TAB>runway_m<TAB>size_class`` row per airport (the
    extent of an entry without one is its point).  The file is
    written atomically (to a temporary file then :func:`os.replace`).

    Args:
        apt_dat_paths: Ordered iterable of ``apt.dat`` paths to index.
        cache_file: Destination cache path.

    Returns:
        The number of airports written to the cache.
    """
    seen: set = set()
    rows: List[AirportEntry] = []
    # (path, mtime_ns, size_bytes) for every source we actually read, in the
    # order read, so v2 caches can record their freshness signals.
    sources: List[Tuple[str, int, int]] = []
    for path in apt_dat_paths:
        if not path or not os.path.isfile(path):
            continue
        stat = os.stat(path)
        sources.append((path, stat.st_mtime_ns, stat.st_size))
        for entry in _iter_airports(path):
            if entry.code in seen:
                continue
            seen.add(entry.code)
            rows.append(entry)

    tmp_file = cache_file + ".tmp"
    directory = os.path.dirname(cache_file)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)

    with open(tmp_file, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{} {} {}\n".format(
            _CACHE_MAGIC, _CACHE_VERSION, len(rows)))
        for path, mtime_ns, size in sources:
            # Path is written last (and verbatim) because it may contain
            # spaces; tabs/newlines are stripped so the line stays parseable.
            handle.write("{} {} {} {}\n".format(
                _SRC_PREFIX, mtime_ns, size, _sanitize(path)))
        for e in rows:
            extent = e.extent or (e.lat, e.lon, e.lat, e.lon)
            handle.write("\t".join((
                _sanitize(e.code),
                _sanitize(e.name),
                _sanitize(e.city),
                _sanitize(e.country),
                repr(e.lat),
                repr(e.lon),
                _sanitize(e.category),
            ) + tuple(repr(v) for v in extent)
              + (str(int(e.runway_m)), str(int(e.size_class)))) + "\n")
    os.replace(tmp_file, cache_file)
    return len(rows)


def load_index(cache_file: str) -> List[AirportEntry]:
    """Load airports from a cache written by :func:`build_index`.

    The cache is streamed line-by-line.  A missing file or a file without
    the expected magic header yields an empty list.  v1 (no ``#SRC``
    lines) through v6 caches are all accepted; ``#SRC`` provenance lines
    are skipped, pre-v3 rows (no category column) load with the
    :class:`AirportEntry` category default, pre-v5 rows (no extent)
    with ``extent=None`` and pre-v6 rows (no size) with the size
    defaults; columns past the last known one are ignored.  Malformed data rows are
    skipped rather than raising.

    Args:
        cache_file: Path to a cache produced by :func:`build_index`.

    Returns:
        The list of :class:`AirportEntry` objects in file order.
    """
    entries: List[AirportEntry] = []
    if not os.path.isfile(cache_file):
        return entries
    with open(cache_file, "r", encoding="utf-8", errors="replace") as handle:
        first = handle.readline()
        if not first.startswith(_CACHE_MAGIC):
            return entries
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith(_SRC_PREFIX):
                # v2 source-provenance line -- not an airport entry.
                continue
            parts = line.split("\t")
            if len(parts) not in _ROW_WIDTHS and len(parts) < _EXTENT_WIDTH:
                continue
            lat = _parse_float(parts[4])
            lon = _parse_float(parts[5])
            if lat is None or lon is None:
                continue
            entry = AirportEntry(
                code=parts[0], name=parts[1], city=parts[2],
                country=parts[3], lat=lat, lon=lon)
            if len(parts) >= 7 and parts[6] in AIRPORT_CATEGORIES:
                entry.category = parts[6]
            if len(parts) >= _EXTENT_WIDTH:
                entry.extent = _parse_extent(parts[7:11])
            if len(parts) >= _SIZE_WIDTH:
                _read_size(entry, parts[11], parts[12])
            entries.append(entry)
    return entries


def _read_size(entry: AirportEntry, runway_m: str, size_class: str) -> None:
    """Set a v6 row's size columns on ``entry``; a malformed value keeps
    the default."""
    try:
        entry.runway_m = int(runway_m)
        entry.size_class = int(size_class)
    except ValueError:
        pass


def _parse_extent(fields: List[str]
                  ) -> Optional[Tuple[float, float, float, float]]:
    """The four v5 extent columns as floats, or ``None`` if any is
    malformed (the entry then falls back to its point)."""
    values = [_parse_float(v) for v in fields]
    if any(v is None for v in values):
        return None
    return tuple(values)


def index_count(cache_file: str) -> Optional[int]:
    """Return the airport count recorded in a cache's header line.

    ONLY the header is read -- the point of this helper is to answer "how
    many airports does that cache hold?" without loading 40k rows (the
    engine protocol's ``airport_index`` command answers on the transport's
    read loop, where a full load is exactly what must not happen).

    Args:
        cache_file: Path to a cache produced by :func:`build_index`.

    Returns:
        The recorded count, or ``None`` when the file is missing,
        unreadable, or its header is not ``<magic> <version> <count>``.
    """
    try:
        with open(cache_file, "r", encoding="utf-8",
                  errors="replace") as handle:
            tokens = handle.readline().split()
    except OSError:
        return None
    if len(tokens) < 3 or tokens[0] != _CACHE_MAGIC:
        return None
    try:
        return int(tokens[2])
    except ValueError:
        return None


def index_is_stale(apt_dat_paths: List[str], cache_file: str) -> bool:
    """Return ``True`` when ``cache_file`` needs rebuilding from the sources.

    Only the header and the ``#SRC`` provenance lines of the cache are read
    (never the airport rows), so this is cheap to call on every run.  The
    cache is considered stale -- i.e. this returns ``True`` -- when ANY of
    the following hold:

    * the cache file is missing or unreadable;
    * the header is malformed (missing/incorrect magic or version);
    * the header version is below the current one (v1 caches carry no
      source info; pre-v3 caches carry no airport categories; pre-v4
      caches were built by a parse that skipped water-only seaplane
      bases, from a smaller candidate set; pre-v5 caches carry no
      extent; pre-v6 caches carry no size);
    * the set of recorded source paths differs from ``apt_dat_paths``
      (compared order-insensitively after :func:`os.path.abspath`);
    * a recorded source no longer exists on disk;
    * a source's current ``st_mtime_ns`` or byte size differs from the
      recorded value (compared with ``!=`` so a restored/downgraded file
      also triggers a rebuild).

    It returns ``False`` only when every recorded source still matches.  An
    empty ``apt_dat_paths`` against a v2 cache that itself recorded zero
    sources is *fresh* (there is nothing to compare); empty paths with no
    cache is stale.

    Args:
        apt_dat_paths: The source ``apt.dat`` paths the cache should cover.
        cache_file: Path to a cache produced by :func:`build_index`.

    Returns:
        ``True`` if a rebuild is warranted, ``False`` otherwise.
    """
    desired = {os.path.abspath(p) for p in apt_dat_paths if p}

    if not os.path.isfile(cache_file):
        return True

    recorded: dict = {}
    try:
        with open(cache_file, "r", encoding="utf-8",
                  errors="replace") as handle:
            first = handle.readline()
            tokens = first.split()
            if len(tokens) < 2 or tokens[0] != _CACHE_MAGIC:
                return True
            try:
                version = int(tokens[1])
            except ValueError:
                return True
            if version < _CACHE_VERSION:
                # Pre-v3 caches carry no airport categories (v1 also no
                # source info), pre-v4 caches were built without the
                # water-runway fallback and pre-v5 caches carry no
                # extent: rebuild once to catch up.
                return True
            # Read only the leading #SRC provenance lines.
            for line in handle:
                line = line.rstrip("\n")
                if not line.startswith(_SRC_PREFIX):
                    break
                parts = line.split(None, 3)
                if len(parts) != 4:
                    return True
                try:
                    mtime_ns = int(parts[1])
                    size = int(parts[2])
                except ValueError:
                    return True
                recorded[os.path.abspath(parts[3])] = (mtime_ns, size)
    except OSError:
        return True

    if set(recorded) != desired:
        return True

    for abs_path, (mtime_ns, size) in recorded.items():
        if not os.path.exists(abs_path):
            return True
        try:
            stat = os.stat(abs_path)
        except OSError:
            return True
        if stat.st_mtime_ns != mtime_ns or stat.st_size != size:
            return True

    return False

