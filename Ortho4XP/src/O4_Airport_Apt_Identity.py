"""A tile's AIRPORT IDENTITY from apt.dat: the code and extent every
airport of ``dico_airports`` is listed, smoothed and cached under.

The tile build's airport dictionary (``O4_Airport_Dico``) is discovered
from the OSM airports layer: an airport's key is the ``icao`` tag of an
``aeroway=aerodrome`` element, and runways no aerodrome claims become an
unnamed strip keyed by a representative node.  When OSM loses the
aerodrome element (2026-10-13..18 an edit stripped one major airport's
``aeroway``/``icao`` tags and the regional extract caught it) that
airport is built as ``unnamed airport at LAT, LON`` -- no inset, no
flat-site record, because both are cached under the code.

The owner's rule (2026-10-19): the airport's identity and extent come
from X-Plane's apt.dat, the data the patcher itself reads; OSM aerodromes
are the fallback.  apt.dat is read through the offline airport index
(``O4_Airport_Index``: code, name, datum, category, and the extent of the
row-130 boundary nodes, runway ends, helipads and datum).

Two passes around ``O4_Airport_Utils.attach_surfaces_to_airports``:

* :func:`adopt_apt_dat_identities` (before): an OSM aerodrome without an
  ICAO tag takes the code of the apt.dat airport whose extent its geometry
  overlaps most (an ICAO tag is kept: it is OSM's own identity claim, and
  the apt.dat airport it overlaps is counted as claimed); every
  apt.dat airport no aerodrome claimed is SEEDED with its apt.dat extent
  as the boundary, so the OSM runways inside it attach to it by geometry.
* closed ``[X]`` fields (owner 2026-10-19): no seed and no inset, unless
  an enabled Custom Scenery pack provides the airport (auto_patch's own
  ``select_apt_dat``);
* :func:`drop_unclaimed_seeds` (after): a seed no OSM surface attached to
  is removed -- apt.dat alone never adds smoothing to ground OSM maps
  nothing on (the dictionary's population stays what OSM shows).
* :func:`assign_synthetic_ids` (last): every aerodrome still without a
  code (keyed by its OSM name, or by a representative-node tuple) is
  re-keyed to :func:`synthetic_airport_id`, a stable code derived from
  its position (owner ruling 2026-10-26, #1353: an airport in the list
  always has an identifier, so no pass skips it).

No index and no X-Plane install to build one from: both passes are no-ops
and the dictionary is the OSM-only one, said once.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Set

from shapely import geometry

from auto_patch_v2.airport import apt_dat as APT_DAT

import O4_Airport_Elevation_Insets as INSETS
import O4_Airport_Index as AIRPORT_INDEX
import O4_Airport_Modes as MODES
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_UI_Utils as UI

__all__ = [
    "IDENTITY_CATEGORIES",
    "SEED_FLAG",
    "tile_apt_dat_airports",
    "adopt_apt_dat_identities",
    "drop_unclaimed_seeds",
    "SYNTHETIC_KEY_TYPE",
    "synthetic_airport_id",
    "assign_synthetic_ids",
    "is_closed",
    "custom_pack_serves",
    "CLOSED_PREFIX",
    "COUNTRY_KEY",
    "iso_country",
]

#: apt.dat categories that name a land airport (heliports and seaplane
#: bases are never airport-smoothed by the OSM chain either).
IDENTITY_CATEGORIES = ("icao_airport", "airport")

#: dico key_type of each identity category: the ICAO-code consumers
#: (``O4_DSF_Utils`` "ICAO" cover, the inset "ICAO" mode) read "icao".
_KEY_TYPE = {"icao_airport": "icao", "airport": "local_ref"}

#: apt.dat's name prefix for a CLOSED field.
CLOSED_PREFIX = "[X]"

#: The record key holding the airport's ISO 3166-1 alpha-3 country, read
#: by the elevation-inset country rule (RULINGS 2026-10-20bc).
COUNTRY_KEY = "country"


def iso_country(text: str) -> str:
    """The ISO alpha-3 code apt.dat's ``1302 country`` value leads with
    (``"CAN"``, ``"USA United States"``), or ``""`` when it has none."""
    token = (str(text or "").split() or [""])[0]
    return token.upper() if len(token) == 3 and token.isalpha() else ""


def _stamp_country(record: dict, entry) -> None:
    country = iso_country(getattr(entry, "country", ""))
    if country:
        record[COUNTRY_KEY] = country


#: Marks an entry seeded from apt.dat until a surface claims it.
SEED_FLAG = "apt_dat_seed"

_SURFACE_LISTS = ("runway", "runway_as_rel", "taxiway", "apron", "hangar")


def tile_apt_dat_airports(lat: int, lon: int,
                          cache_file: Optional[str] = None,
                          xplane_root: Optional[str] = None,
                          known_codes: Optional[Set[str]] = None) -> list:
    """The index's land airports whose extent (or datum) meets the tile's
    1 degree box, or ``[]`` when there is no index to read.

    ``known_codes``, when a set, is FILLED with every code of the index
    (all categories, the whole globe): the codes a synthetic identifier
    must never take (:func:`assign_synthetic_ids`).

    The index is the one the map window builds (``O4_File_Names.
    airport_index_cache``); when it is missing or older than the X-Plane
    install's apt.dat it is (re)built here first -- 2.8 s for the
    38,854-airport Global Airports file (measured 2026-10-19), paid once
    per apt.dat, never per tile."""
    cache_file = cache_file or FNAMES.airport_index_cache()
    _refresh_index(cache_file, xplane_root)
    try:
        entries = AIRPORT_INDEX.load_index(cache_file)
    except OSError:
        entries = []
    if not entries:
        UI.vprint(1, "   INFO: no offline airport index (apt.dat) at",
                  cache_file, "- airport codes come from OSM alone.")
        return []
    if known_codes is not None:
        known_codes.update(entry.code.upper() for entry in entries)
    return [entry for entry in entries
            if entry.category in IDENTITY_CATEGORIES
            and _meets_tile(_extent(entry), lat, lon)]


def _refresh_index(cache_file: str, xplane_root: Optional[str]) -> None:
    """Build the index from the install's apt.dat when it is missing or
    stale; any failure leaves whatever index there is."""
    if xplane_root is None:
        xplane_root = INSETS._xplane_root_for_package_footprints()
    if not xplane_root:
        return
    try:
        sources = AIRPORT_INDEX.find_apt_dats(xplane_root)
        if sources and AIRPORT_INDEX.index_is_stale(sources, cache_file):
            UI.vprint(1, "   Indexing apt.dat for airport identities:",
                      ", ".join(sources))
            AIRPORT_INDEX.build_index(sources, cache_file)
    except Exception as error:
        UI.vprint(1, "   WARNING: could not index apt.dat (" + str(error)
                  + "); the existing airport index is used as it is.")


def _extent(entry) -> tuple:
    """(min_lat, min_lon, max_lat, max_lon); the datum point when the
    index row carries no extent."""
    if entry.extent:
        return entry.extent
    return (entry.lat, entry.lon, entry.lat, entry.lon)


def _meets_tile(extent: tuple, lat: int, lon: int) -> bool:
    (min_lat, min_lon, max_lat, max_lon) = extent
    return (min_lat <= lat + 1 and max_lat >= lat
            and min_lon <= lon + 1 and max_lon >= lon)


#: An extent whose longer side exceeds this many times the airport's
#: longest runway (and the floor below) is a mapping error, not an
#: airfield: 225 of 38,854 Global Airports rows (2026-10-19) span over
#: half a degree, one a stray boundary node at longitude +110 for a
#: Washington strip.  Such an airport is its datum point only.
EXTENT_RUNWAY_FACTOR = 3.0
EXTENT_FLOOR_M = 3000.0


def _extent_box(entry):
    """The extent as a (lon, lat) shapely box, ``None`` when it has no
    area (a datum-only row cannot claim runways) or is implausibly large
    for the airport (:data:`EXTENT_RUNWAY_FACTOR`)."""
    (min_lat, min_lon, max_lat, max_lon) = _extent(entry)
    if max_lat <= min_lat or max_lon <= min_lon:
        return None
    limit_m = max(EXTENT_RUNWAY_FACTOR * entry.runway_m, EXTENT_FLOOR_M)
    mid_lat = 0.5 * (min_lat + max_lat)
    if (max(GEO.lat_to_m * (max_lat - min_lat),
            GEO.lon_to_m(mid_lat) * (max_lon - min_lon)) > limit_m):
        return None
    return geometry.box(min_lon, min_lat, max_lon, max_lat)


def _overlap(record: dict, entry) -> float:
    """How much of ``entry``'s apt.dat extent the OSM aerodrome covers:
    its boundary's intersection area with the extent box; a token 1e-12
    when only points meet (a node aerodrome inside the box, or the apt.dat
    datum inside the aerodrome's boundary); 0 when they do not meet."""
    box = _extent_box(entry)
    boundary = record.get("boundary")
    has_boundary = boundary is not None and not boundary.is_empty
    if box is not None and has_boundary:
        try:
            area = boundary.intersection(box).area
            if area > 0:
                return area
        except Exception:
            pass
    if box is not None and box.covers(geometry.Point(record["repr_node"])):
        return 1e-12
    if has_boundary:
        try:
            if boundary.covers(geometry.Point(entry.lon, entry.lat)):
                return 1e-12
        except Exception:
            pass
    return 0.0


def _matches_by_overlap(dico_airports: dict, keys: List,
                        entries: List) -> List[tuple]:
    """``(key, entry)`` pairs, each key and each entry used once, taken
    greedily by descending overlap: an aerodrome meets the apt.dat airport
    it covers most, whatever order OSM listed them in."""
    scored = sorted(
        ((_overlap(dico_airports[key], entry), index, key, entry)
         for index, key in enumerate(keys) for entry in entries),
        key=lambda item: (-item[0], item[1]))
    used_keys, used_codes, pairs = set(), set(), []
    for (score, _index, key, entry) in scored:
        if score <= 0:
            break
        if key in used_keys or entry.code in used_codes:
            continue
        used_keys.add(key)
        used_codes.add(entry.code)
        pairs.append((key, entry))
    return pairs


def is_closed(entry) -> bool:
    """apt.dat marks a closed field by the ``[X]`` name prefix."""
    return entry.name.lstrip().startswith(CLOSED_PREFIX)


def custom_pack_serves(code: str, xplane_root: Optional[str] = None) -> bool:
    """True when an enabled Custom Scenery pack provides ``code``: the
    apt.dat auto_patch's own selector (``select_apt_dat``) picks for it is
    not a Global Airports / default one.  No install resolved: False."""
    if xplane_root is None:
        xplane_root = INSETS._xplane_root_for_package_footprints()
    if not xplane_root:
        return False
    try:
        chosen = APT_DAT.select_apt_dat(xplane_root, code)
    except Exception:
        return False
    return bool(chosen) and chosen not in APT_DAT.global_candidates(
        xplane_root)


def adopt_apt_dat_identities(dico_airports: dict, entries: Iterable,
                             custom_serves=custom_pack_serves) -> int:
    """Re-key the OSM aerodromes of ``dico_airports`` (as
    ``O4_Airport_Utils.discover_airport_names`` left it: absolute
    degrees) to their apt.dat codes and seed the airports no aerodrome
    claimed.  Returns the number of seeds.

    A CLOSED field (:func:`is_closed`) no Custom Scenery pack provides
    (``custom_serves(code)``, auto_patch's own pack selection) is never
    seeded, and the airport identified with it is marked
    ``O4_Airport_Modes.INSET_EXCLUDED`` -- no inset (owner 2026-10-19)."""
    unclaimed = {entry.code: entry for entry in entries}
    if not unclaimed:
        return 0
    excluded = {code for (code, entry) in unclaimed.items()
                if is_closed(entry) and not custom_serves(code)}
    adopted = set()
    for key in [k for k in dico_airports if k in unclaimed]:
        # OSM's own code is an apt.dat airport of this tile: same identity.
        entry = unclaimed.pop(key)
        if dico_airports[key].get("key_type") != "icao":
            dico_airports[key]["key_type"] = _KEY_TYPE[entry.category]
        _mark_closed(dico_airports[key], entry.code, excluded)
        _stamp_country(dico_airports[key], entry)
        adopted.add(key)
    others = [k for k in dico_airports if k not in adopted]
    for (key, entry) in _matches_by_overlap(
            dico_airports, others, list(unclaimed.values())):
        if entry.code in dico_airports:
            continue
        unclaimed.pop(entry.code)
        if dico_airports[key].get("key_type") == "icao":
            # OSM's own ICAO tag is an identity claim apt.dat does not
            # contradict by CODE (the code is not on this tile in apt.dat):
            # it is kept, and the overlapped apt.dat airport is not seeded
            # a second time over the same ground.
            continue
        UI.vprint(2, "   OSM airport", _label(key), "is", entry.code,
                  "in apt.dat (" + entry.name + ").")
        record = dico_airports.pop(key)
        _mark_closed(record, entry.code, excluded)
        _stamp_country(record, entry)
        record["key_type"] = _KEY_TYPE[entry.category]
        if record.get("name", "****") == "****":
            record["name"] = entry.name
        dico_airports[entry.code] = record
    seeds = 0
    for entry in unclaimed.values():
        box = _extent_box(entry)
        if box is None or entry.code in dico_airports:
            continue
        if entry.code in excluded:
            continue
        dico_airports[entry.code] = {
            "key_type": _KEY_TYPE[entry.category],
            "name": entry.name,
            "repr_node": (entry.lon, entry.lat),
            "boundary": box,
            "runway": [], "runway_as_rel": [], "taxiway": [],
            "apron": [], "hangar": [],
            SEED_FLAG: True,
        }
        _stamp_country(dico_airports[entry.code], entry)
        seeds += 1
    return seeds


def _mark_closed(record: dict, code: str, excluded: set) -> None:
    if code in excluded:
        record[MODES.INSET_EXCLUDED] = "closed field " + code


def _label(key) -> str:
    import O4_Airport_Utils as APT  # leaf use: keeps this module's load light
    return APT.airport_label(key)


def drop_unclaimed_seeds(dico_airports: dict) -> List[str]:
    """Remove the seeds no OSM surface attached to; clear the flag on the
    rest.  Returns the codes the seeds kept (each now an airport OSM
    shows runways or pavement for, under its apt.dat code)."""
    kept = []
    for key in [k for k, v in dico_airports.items() if v.get(SEED_FLAG)]:
        record = dico_airports[key]
        if any(record.get(name) for name in _SURFACE_LISTS):
            del record[SEED_FLAG]
            kept.append(key)
        else:
            del dico_airports[key]
    if kept:
        UI.vprint(1, "   Airport(s) with no OSM aerodrome, identified from "
                  "apt.dat by their surfaces:", ", ".join(sorted(kept)))
    return kept


# ──────────────────────────────────────────────────────────────────────
# Synthetic identifiers (#1353)
# ──────────────────────────────────────────────────────────────────────
#: key_type of an aerodrome re-keyed to its synthetic identifier.  Not
#: "icao", so the ICAO-only consumers (the "ICAO" inset mode, the "ICAO"
#: high-res cover, flat-site prep) never admit one.
SYNTHETIC_KEY_TYPE = "synthetic"

#: key_types :func:`assign_synthetic_ids` re-keys: no code, only a name or
#: a representative node (``O4_Airport_Utils`` discovery).
_UNCODED_KEY_TYPES = ("name", "repr_node")

#: The identifier's position cell, in degrees: 0.001 is 111 m north-south
#: and 111 m x cos(latitude) east-west, so an OSM edit that moves the
#: aerodrome's centroid by metres keeps its identifier.
SYNTHETIC_CELL_DEG = 0.001

#: "X" + 7 base-36 digits: 8 characters, longer than any apt.dat code in
#: the global index (3 to 7 measured, 38,854 rows, 2026-10-26).
_SYNTHETIC_PREFIX = "X"
_SYNTHETIC_DIGITS = 7
_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LAT_CELLS = 180000
_LON_CELLS = 360000


def synthetic_airport_id(lon: float, lat: float) -> str:
    """The stable identifier of an aerodrome without a code at (lon, lat):
    ``X`` + the base-36 index of its :data:`SYNTHETIC_CELL_DEG` cell,
    zero-padded to 7 digits.  Pure: the same on every build and machine."""
    row = int(round(float(lat) / SYNTHETIC_CELL_DEG)) + _LAT_CELLS // 2
    col = (int(round(float(lon) / SYNTHETIC_CELL_DEG))
           + _LON_CELLS // 2) % _LON_CELLS
    number = min(max(row, 0), _LAT_CELLS) * _LON_CELLS + col
    digits = ""
    for _ in range(_SYNTHETIC_DIGITS):
        number, digit = divmod(number, 36)
        digits = _BASE36[digit] + digits
    return _SYNTHETIC_PREFIX + digits


def _record_position(record: dict) -> tuple:
    """(lon, lat) the identifier is derived from: the area centroid of the
    OSM aerodrome boundary (absolute degrees at this stage), which a node
    added or nudged barely moves; else the representative node."""
    boundary = record.get("boundary")
    if boundary is not None and not boundary.is_empty:
        centroid = boundary.centroid
        return (float(centroid.x), float(centroid.y))
    (lon, lat) = record["repr_node"]
    return (float(lon), float(lat))


def _free_identifier(base: str, taken: set) -> str:
    """``base``, else ``base`` + the first free 1, 2, ... (a code apt.dat
    uses, or a second uncoded aerodrome in the same cell)."""
    if base not in taken:
        return base
    suffix = 1
    while base + str(suffix) in taken:
        suffix += 1
    return base + str(suffix)


def assign_synthetic_ids(dico_airports: dict,
                         known_codes: Iterable[str] = ()) -> List[str]:
    """Re-key every aerodrome of ``dico_airports`` without a code (key_type
    ``name`` / ``repr_node``) to its :func:`synthetic_airport_id`, never
    one of ``known_codes`` (the global airport index) or a key already on
    the tile.  An unnamed aerodrome is named "Unnamed airstrip (LAT, LON)";
    an OSM name is kept.  Returns the identifiers given, in order.

    Runs on the dictionary as :func:`drop_unclaimed_seeds` leaves it
    (absolute degrees).  Records are taken in position order, so the
    suffix of a shared cell does not depend on OSM's element order."""
    uncoded = sorted(
        ((_record_position(record), str(key), key)
         for (key, record) in dico_airports.items()
         if record.get("key_type") in _UNCODED_KEY_TYPES),
        key=lambda item: (item[0], item[1]))
    if not uncoded:
        return []
    taken = {str(code).upper() for code in known_codes}
    taken.update(str(key).upper() for key in dico_airports
                 if isinstance(key, str)
                 and dico_airports[key].get("key_type")
                 not in _UNCODED_KEY_TYPES)
    given = []
    for ((lon, lat), _order, key) in uncoded:
        identifier = _free_identifier(synthetic_airport_id(lon, lat), taken)
        taken.add(identifier)
        record = dico_airports.pop(key)
        record["key_type"] = SYNTHETIC_KEY_TYPE
        if record.get("name", "****") == "****":
            record["name"] = "Unnamed airstrip (%s)" % _position(lon, lat)
        dico_airports[identifier] = record
        given.append(identifier)
    return given


def _position(lon: float, lat: float) -> str:
    import O4_Airport_Utils as APT  # leaf use: keeps this module's load light
    return APT.position_label((lon, lat))
