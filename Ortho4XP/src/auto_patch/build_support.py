"""The small build-input helpers the SURVIVING modules need — moved here ONCE
when the v1 engine was retired (RULINGS 2026-09-13au/13aw stage B, lane
``v1retire`` round 1, 2026-09-17).

Every function below used to live in a module the deletion takes
(``layout``, ``osm_load``, ``elevation``, ``object_pads``,
``pavement/runway_geometry``) and was reached from a KEEP module — those
import edges were the SEAMS that re-admitted the whole 185k-line v1 tree
into the production import closure (S1/S2 of 13aw).  Nothing is re-derived
and nothing is re-spelled: each definition is the one that shipped, MOVED,
and the v1 modules re-export it from here until they are deleted, so the
two sides cannot drift for the one round they coexist.

  ``_pick_best_apt_dat_against_osm``  the apt.dat SELECTOR the driver, the
      freshness gate and the DSF object-anchor worklist call (its policy is
      ``engine_v2.select_apt_dat`` — one selector, one datum)
  ``ensure_airports_osm_tile_cached``  the tile driver's ``airports`` OSM
      prefetch
  ``read_patch_source``  the build-input provenance a patch header carries
      (the freshness gate's reader)
  ``_find_cifp_path``  the CIFP ``.dat`` resolver (AIRAC, then stock)
  ``_projection`` / ``_airport_anchor``  the local-metre frame every
      airport-scoped reader works in
  ``pair_runways`` / ``get_reciprocal``  threshold pairing
  ``_CLAIM_MARGIN_M``  the Phase-2 worklist claim dilation
"""

from __future__ import annotations

import math
import os
import re
from typing import overload

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import Polygon

import O4_File_Names as FNAMES
import O4_UI_Utils as UI
from O4_Geo_Utils import earth_radius as R_EARTH  # single source of truth

# Narrow exception tuple for shapely / numeric-geometry failure modes.
# Programming errors propagate so they surface immediately.  Includes
# ``OSError`` because the OSM prefetch mixes shapely ops with file I/O.
_GEOM_EXC = (OSError, ValueError, GEOSException, TopologicalError)

#: The Phase-2 worklist claim dilation — the constant ``object_pads``'
#: footprint claim is drawn with (moved from ``object_pads._CLAIM_MARGIN_M``).
_CLAIM_MARGIN_M = 250.0


# ──────────────────────────────────────────────────────────────────────
# apt.dat selection and the airports OSM cache
# ──────────────────────────────────────────────────────────────────────

def _pick_best_apt_dat_against_osm(
        xplane_root: str,
        icao: str,
        apron_threshold: float = 0.7,
        taxi_threshold: float = 0.7,
        ) -> str | None:
    """Select the apt.dat for ``icao`` — v2's selector, nothing else.

    ONE SELECTOR, ONE DATUM (lane ``aptstamp`` 2026-09-17).  This
    function is the NAME the driver, the freshness gate and the DSF
    object-anchor worklist call; its POLICY is
    ``auto_patch.engine_v2.select_apt_dat`` →
    ``auto_patch_v2.airport.apt_dat.find_apt_dat``, the same call the
    build makes, so nothing downstream can watch a file the build never
    opened.

    What was deleted here: the 2026-05-21/06-16 policy — first Custom
    Scenery pack carrying a 1201/1202 taxi-routing network, ELSE fall
    back to Global Airports (the MKStudios LPPT case).  §44 (1) (owner
    RULINGS 2026-09-15m) rules that tail out for the build: THE PACK IS
    STILL THE PACK, and a pack whose pavement is thin borrows Global's
    pavement (``airport/borrow.py``) instead of losing the selection.
    Keeping a second policy alive on the gate side made the two disagree
    at 225 of 1,327 CIFP airports on the owner's install (2026-09-17).

    The ``*_threshold`` parameters were already unused when the coverage
    scorer was removed; they stay for signature compatibility.

    ``None`` is returned when NOTHING in the install carries the airport,
    and it is returned WITHOUT a v1 fallback resolver: a second walk that
    found a file v2's does not is how the driver came to queue an airport
    the build then failed on with "no apt.dat under xp_root".  None here
    means the driver's skip line, which is the truthful answer.
    """
    from . import engine_v2 as _engine_v2
    chosen = _engine_v2.select_apt_dat(xplane_root, icao)
    if chosen is not None:
        UI.vprint(1, f"  [pav-builder] {icao}: apt.dat {chosen}")
    return chosen


def ensure_airports_osm_tile_cached(tile_latitude: int,
                                    tile_longitude: int) -> bool:
    """Download the ``airports`` OSM cache for one 1°×1° tile if absent.

    Used by the tile driver's prefetch, which downloads every tile the
    airport builds will need ONCE, up front, so the parallel airport
    worker processes never issue duplicate Overpass queries for the same
    tile.  Returns True when the cache file exists on return.
    """
    cache_path = FNAMES.osm_cached(tile_latitude, tile_longitude,
                                   "airports")
    if os.path.isfile(cache_path):
        return True
    try:
        import O4_OSM_Utils as _OSM
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        layer = _OSM.OSM_layer()
        queries = [('node["aeroway"]', 'way["aeroway"]',
                    'rel["aeroway"]')]
        _OSM.OSM_queries_to_OSM_layer(
            queries, layer, tile_latitude, tile_longitude,
            tags_of_interest=["all"],
            cached_suffix="airports")
    except _GEOM_EXC as exc:
        UI.vprint(1,
            f"  [pav-builder] WARN: airport OSM download error: "
            f"{exc}")
    return os.path.isfile(cache_path)


# ──────────────────────────────────────────────────────────────────────
# CIFP location
# ──────────────────────────────────────────────────────────────────────

_CIFP_DIRS = (
    ("Custom Data", "CIFP"),
    ("Resources", "default data", "CIFP"),
)


def _find_cifp_path(xplane_root: str, icao: str) -> str | None:
    """Locate the CIFP ``.dat`` file for an ICAO under the X-Plane root.

    Prefers an AIRAC update in ``Custom Data/CIFP``, falling back to the
    stock cycle in ``Resources/default data/CIFP``.  Without that fallback
    an install with no Navigraph resolved to ``None`` and silently skipped
    the ENTIRE segmented-runway block — no CIFP threshold elevations, no
    FAA vertical profile, no segmentation at apt.dat pavement joins —
    because the stock CIFP X-Plane ships with was never consulted.

    The fallback is PER FILE, not per directory: a partial AIRAC update
    carrying only some airports still resolves the rest from stock, which
    a directory-level choice could not do.

    Returns None when neither location has the airport.
    """
    if not xplane_root:
        return None
    name = f"{icao.upper()}.dat"
    for parts in _CIFP_DIRS:
        p = os.path.join(xplane_root, *parts, name)
        if os.path.isfile(p):
            return p
    return None


# ──────────────────────────────────────────────────────────────────────
# Patch provenance (the freshness gate's reader)
# ──────────────────────────────────────────────────────────────────────

def _xml_unescape(value: str) -> str:
    """The inverse of the v2 emitter's attribute quoter
    (``emit/osm_adapter._q``: ``escape(v, {"'": "&apos;", '"':
    "&quot;"})``) — for header values that ride RAW rather than
    percent-encoded."""
    from xml.sax.saxutils import unescape as _unescape
    return _unescape(value, {"&apos;": "'", "&quot;": '"'})


_PATCH_SOURCE_APT_RE = re.compile(r"o4_apt_dat='([^']*)'")
_PATCH_SOURCE_MTIME_RE = re.compile(r"o4_apt_dat_mtime='([^']*)'")
# §44's BORROWED Global Airports apt.dat (v2's emitter only).  Neither of
# the two regexes above may match these longer names — they cannot: both
# require ``=`` straight after ``o4_apt_dat`` / ``o4_apt_dat_mtime``,
# where these carry ``_borrowed``.  Pinned by
# ``test_borrowed_keys_do_not_capture_the_selected_apt_dat``.
_PATCH_SOURCE_BORROWED_RE = re.compile(r"o4_apt_dat_borrowed='([^']*)'")
_PATCH_SOURCE_BORROWED_MTIME_RE = re.compile(
    r"o4_apt_dat_borrowed_mtime='([^']*)'")
_PATCH_FRESHNESS_RE = re.compile(r"(o4_(?:fresh_v|cfg|dem|cifp|pack|engine"
                                 r"|ap_engine|dsf_tiles|dsf))='([^']*)'")


def read_patch_source(path: str) -> dict | None:
    """Read the build-input provenance stamped into an auto-patch file.

    The emitter records the apt.dat the build consumed as
    ``o4_apt_dat`` / ``o4_apt_dat_mtime`` attributes on the ``<osm>``
    root element, plus — for a driver-driven build — the freshness
    stamps for the build's other inputs (``o4_fresh_v``, ``o4_cfg``,
    ``o4_dem``, ``o4_cifp``, ``o4_pack``, ``o4_engine``, ``o4_dsf``,
    ``o4_dsf_tiles``; see ``provenance.FRESHNESS_KEYS``).

    v2's emitter additionally records §44's BORROWED Global Airports
    apt.dat as ``o4_apt_dat_borrowed`` / ``o4_apt_dat_borrowed_mtime``
    (``pipeline/build.py``, :func:`~auto_patch_v2.pipeline.build.
    borrowed_apt_dat_stamp`).  Unlike ``o4_apt_dat`` that path rides RAW
    (XML-escaped by the emitter's attribute quoter, not percent-encoded),
    so it is read back XML-unescaped — the encoding it is written in.

    Returns ``{"apt_dat": str, "apt_dat_mtime": float | None,
    "apt_dat_borrowed": str, "apt_dat_borrowed_mtime": float | None,
    "freshness": {key: raw value}}``, or ``None`` when the file is
    missing, unreadable, or pre-dates the apt.dat stamp.
    ``apt_dat_borrowed`` is ``""`` when the patch borrowed nothing or
    pre-dates §44; ``apt_dat_borrowed_mtime`` is ``None`` when the key is
    absent or unparseable (which the gate reads as "not current" for a
    patch that DID borrow).  ``freshness``
    is EMPTY for a patch written before those stamps existed or by a
    standalone tool — which the driver's gate reads as "inputs
    unverifiable" and rebuilds.
    """
    import urllib.parse

    try:
        with open(path, "r", encoding="utf-8") as f:
            # The root element is line 1 or 2 (after the XML
            # declaration) — same convention O4_OSM_Utils relies on.
            line = f.readline()
            if "<osm " not in line:
                line = f.readline()
    except OSError:
        return None
    if "<osm " not in line:
        return None
    m = _PATCH_SOURCE_APT_RE.search(line)
    if not m:
        return None
    apt_dat = urllib.parse.unquote(m.group(1))
    mtime: float | None = None
    m = _PATCH_SOURCE_MTIME_RE.search(line)
    if m:
        try:
            mtime = float(m.group(1))
        except ValueError:
            mtime = None
    # Freshness stamps ride RAW (already percent-encoded where they carry a
    # path): the gate compares them byte-for-byte against freshly computed
    # values in the same encoding, so decoding here would only invite a
    # round-trip mismatch.
    freshness = {
        match.group(1): match.group(2)
        for match in _PATCH_FRESHNESS_RE.finditer(line)
    }
    borrowed = ""
    m = _PATCH_SOURCE_BORROWED_RE.search(line)
    if m:
        borrowed = _xml_unescape(m.group(1))
    borrowed_mtime: float | None = None
    m = _PATCH_SOURCE_BORROWED_MTIME_RE.search(line)
    if m:
        try:
            borrowed_mtime = float(m.group(1))
        except ValueError:
            borrowed_mtime = None
    return {"apt_dat": apt_dat, "apt_dat_mtime": mtime,
            "apt_dat_borrowed": borrowed,
            "apt_dat_borrowed_mtime": borrowed_mtime,
            "freshness": freshness}


# ──────────────────────────────────────────────────────────────────────
# The local-metre frame
# ──────────────────────────────────────────────────────────────────────

def _projection(anchor: tuple[float, float]):
    lat0, lon0 = anchor
    cos0 = math.cos(math.radians(lat0))

    @overload
    def to_m(lon: float, lat: float) -> tuple[float, float]: ...
    @overload
    def to_m(lon: float, lat: float, z: float | None
             ) -> tuple[float, float] | tuple[float, float, float]: ...

    def to_m(lon: float, lat: float, z: float | None = None
             ) -> tuple[float, float] | tuple[float, float, float]:
        x = math.radians(lon - lon0) * R_EARTH * cos0
        y = math.radians(lat - lat0) * R_EARTH
        return (x, y) if z is None else (x, y, z)

    return to_m


def _airport_anchor(apt) -> tuple[float, float]:
    if apt.runways:
        r = apt.runways[0]
        return ((r.lat_a + r.lat_b) / 2.0,
                (r.lon_a + r.lon_b) / 2.0)
    if apt.boundary:
        c = apt.boundary.centroid
        return (c.y, c.x)
    return (0.0, 0.0)


# ──────────────────────────────────────────────────────────────────────
# Runway threshold pairing
# ──────────────────────────────────────────────────────────────────────

def get_reciprocal(designator: str) -> str | None:
    """Get the reciprocal runway designator. RW16L → RW34R, RW09 → RW27."""
    match = re.match(r"RW(\d{2})([LRC]?)", designator)
    if not match:
        return None
    num = int(match.group(1))
    suffix = match.group(2)
    recip_num = num + 18
    if recip_num > 36:
        recip_num -= 36
    recip_suffix = {"L": "R", "R": "L", "C": "C", "": ""}.get(suffix, "")
    return "RW{:02d}{}".format(recip_num, recip_suffix)


def pair_runways(runways: dict) -> list:
    """Match runway thresholds into pairs.

    Returns list of tuples:
        (desig_a, data_a, desig_b, data_b)
    where a is the higher-numbered threshold (higher heading number) by
    convention, and b is the reciprocal. If unpaired, desig_b/data_b are None.
    """
    paired: set[str] = set()
    pairs: list = []
    for desig in sorted(runways.keys()):
        if desig in paired:
            continue
        data = runways[desig]
        recip = get_reciprocal(desig)
        if recip and recip in runways:
            paired.add(desig)
            paired.add(recip)
            pairs.append((desig, data, recip, runways[recip]))
        else:
            pairs.append((desig, data, None, None))
    return pairs


# ──────────────────────────────────────────────────────────────────────
# Runway rects
# ──────────────────────────────────────────────────────────────────────

def _runway_rect_m(runway, to_m) -> Polygon:
    """4-vertex runway rect spanning end-to-end including blast pads.

    Targets are drawn with blast pads included (matches how the
    runway paint looks in satellite imagery).
    """
    ax, ay = to_m(runway.lon_a, runway.lat_a)
    bx, by = to_m(runway.lon_b, runway.lat_b)
    dx, dy = bx - ax, by - ay
    mag = math.hypot(dx, dy)
    if mag < 1e-9:
        return Polygon()
    ux, uy = dx / mag, dy / mag
    a_extra = runway.blast_a_m or 0.0
    b_extra = runway.blast_b_m or 0.0
    ax2 = ax - ux * a_extra
    ay2 = ay - uy * a_extra
    bx2 = bx + ux * b_extra
    by2 = by + uy * b_extra
    px, py = -uy, ux
    half = runway.width_m / 2.0
    return Polygon([
        (ax2 + px * half, ay2 + py * half),
        (bx2 + px * half, by2 + py * half),
        (bx2 - px * half, by2 - py * half),
        (ax2 - px * half, ay2 - py * half),
    ])
