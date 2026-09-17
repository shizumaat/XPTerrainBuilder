#!/usr/bin/env python3
"""READ-ONLY census of the airport elevation inset cache's COVERAGE.

Answers, over every cached inset raster on the data corpus, the one
question a staleness rule turns on: WHAT DOES THIS RASTER ACTUALLY COVER,
against what this airport needs today, and against what was asked for when
it was cut?

Three boxes per raster, never conflated:

``boundary``   the OSM aerodrome boundary's bounding box, TODAY, from the
               cached airports layer (no margin).  Expanding it by a
               margin reproduces ``_airport_bounding_boxes`` exactly.
``requested``  the box the fetch ASKED the provider for, recorded verbatim
               in the manifest as ``bounding_box_wgs84`` by every access
               strategy (``requested_bounding_box_wgs84`` in manifests
               written since 2026-09-17).
``delivered``  the box the raster on disk CARRIES, read from its own
               GeoTIFF geotransform.  Measured 2026-09-17: it differs from
               ``requested`` by a median 5.1e-6 deg and up to 1.4e-2 deg
               (~1.6 km for the England 1 m WCS), in both directions.

WHY A TOOL AND NOT A SCRIPT.  A staleness rule that re-cuts insets changes
the terrain every airport is graded against (a warm-vs-cold inset has
moved measured terrain 12 m), so the rule is chosen from a corpus-wide
table, not from an example -- and the table has to be reproducible by the
next session.

IT WRITES NOTHING.  Every run is wrapped in a refusing
``SharedRepoWriteGuard`` and prints ``[guard] blocked writes: N`` last; a
non-zero count is a defect in this tool.  Tiles whose airports OSM layer
is not cached are SKIPPED and counted, never queried.

Sections (``--section``, default ``all``):

  sweep     For each functional margin in ``--margins``: how many rasters
            fail to contain (boundary + margin), judged against the
            DELIVERED box with a tolerance of one delivered pixel per
            axis.  Table by provider; every stale raster named, with its
            per-edge shortfall in metres, up to ``--name-below-m``.
  battery   Per-edge delivered margin, in metres, for ``--battery``.
  delivery  requested vs delivered per provider: which providers hand back
            materially less than they were asked for (the re-cut LOOP
            hazard -- re-asking such a provider returns the same raster).
  shipped   The rule that ships today (``_bounding_box_extends_beyond``
            over required-vs-requested at 1e-6 deg), its count bucketed by
            shortfall magnitude, and the proposed pair:
            RE-CUT iff required not inside requested-at-cut-time,
            WARN   iff required(+margin) not inside delivered.

Run from ``Ortho4XP/``:

    venv/bin/python tools/inset_coverage_census.py
    venv/bin/python tools/inset_coverage_census.py --section sweep \\
        --margins 0,250,500 --name-below-m 500
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

_TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIRECTORY = os.path.dirname(_TOOLS_DIRECTORY)
for _directory in (
    os.path.join(_ENGINE_DIRECTORY, "src"),
    os.path.join(_TOOLS_DIRECTORY, "harness"),
):
    if _directory not in sys.path:
        sys.path.insert(0, _directory)

import O4_File_Names as FNAMES                             # noqa: E402
import O4_Geo_Utils as GEO                                 # noqa: E402
import O4_Airport_Elevation_Insets as INSETS               # noqa: E402

#: Functional margins swept by default, in metres.  0 is "the aerodrome
#: boundary itself"; 2000 is the configured
#: ``airport_elevation_inset_margin_m`` default, i.e. today's rule.
DEFAULT_MARGINS_M = (0, 100, 250, 500, 750, 1000, 1500, 2000)

#: The campaign's battery airports, reported edge by edge so a rule can be
#: seen not to touch them.
DEFAULT_BATTERY = ("HECA", "CYXY", "LEMD", "SPJC", "OTHH", "KCLT", "KPHX",
                   "LGAV", "VHHH")

#: A delivered box short of the requested one by more than this many
#: DELIVERED pixels is the provider's limit, not warp rounding.
PROVIDER_LIMIT_PIXELS = 3.0

EDGES = ("west", "south", "east", "north")


# =====================================================================
# Geometry (pure; the twin pins it against _airport_bounding_boxes)
# =====================================================================
def expand_box(boundary_box, margin_m, latitude):
    """``boundary_box`` grown by ``margin_m`` true metres.

    The SAME arithmetic ``_airport_bounding_boxes`` uses -- degrees per
    metre from :mod:`O4_Geo_Utils` at the tile's mid-latitude -- so at the
    configured margin this reproduces the engine's required box.
    """
    (west, south, east, north) = boundary_box
    margin_lon = margin_m / GEO.lon_to_m(latitude)
    margin_lat = margin_m / GEO.lat_to_m
    return (west - margin_lon, south - margin_lat,
            east + margin_lon, north + margin_lat)


def edge_shortfalls_m(required_box, covering_box, latitude):
    """How far ``covering_box`` falls SHORT of ``required_box`` per edge,
    in true metres.  Positive = short (uncovered ground); negative = the
    covering box reaches beyond the requirement, which is never a defect
    (a superset raster stays valid).
    """
    metres_per_degree_longitude = GEO.lon_to_m(latitude)
    return {
        "west": (covering_box[0] - required_box[0])
        * metres_per_degree_longitude,
        "south": (covering_box[1] - required_box[1]) * GEO.lat_to_m,
        "east": (required_box[2] - covering_box[2])
        * metres_per_degree_longitude,
        "north": (required_box[3] - covering_box[3]) * GEO.lat_to_m,
    }


def fails_to_contain(required_box, covering_box, tolerance_lon,
                     tolerance_lat):
    """True when ``required_box`` reaches outside ``covering_box``, with a
    per-AXIS tolerance (one raster pixel, which is not square in degrees).
    """
    return (
        required_box[0] < covering_box[0] - tolerance_lon
        or required_box[1] < covering_box[1] - tolerance_lat
        or required_box[2] > covering_box[2] + tolerance_lon
        or required_box[3] > covering_box[3] + tolerance_lat
    )


# =====================================================================
# Corpus walk
# =====================================================================
def tile_of_stem(stem):
    """``(lat, lon)`` from an ``N51W001``-style tile stem."""
    latitude = int(stem[1:3]) * (1 if stem[0] in "+N" else -1)
    longitude = int(stem[4:7]) * (1 if stem[3] in "+E" else -1)
    return latitude, longitude


def _manifest_of(inset_path):
    try:
        with open(os.path.splitext(inset_path)[0] + ".json") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _box_from(value):
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            return tuple(float(item) for item in value)
        except (TypeError, ValueError):
            return None
    return None


def collect_records(elevation_directory, out=print):
    """One record per cached inset raster whose airport is judgeable.

    ``(records, skipped)``; ``skipped`` counts rasters whose tile has no
    cached airports layer (never queried) or whose airport key is not in
    today's dico.  Importing the OSM/vector modules is deferred to here so
    ``--section`` runs that need no dico stay cheap.
    """
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_UI_Utils as UI
    import O4_Vector_Map as VMAP

    UI.verbosity = 0
    records = []
    skipped = {"no_airports_layer": [], "not_in_dico": []}
    if not os.path.isdir(elevation_directory):
        return records, skipped
    inset_directories = sorted(
        os.path.join(elevation_directory, block, name)
        for block in sorted(os.listdir(elevation_directory))
        if os.path.isdir(os.path.join(elevation_directory, block))
        for name in sorted(os.listdir(os.path.join(elevation_directory,
                                                   block)))
        if name.endswith("_airport_insets")
    )
    for inset_directory in inset_directories:
        stem = os.path.basename(inset_directory)[: -len("_airport_insets")]
        (latitude, longitude) = tile_of_stem(stem)
        rasters = sorted(name for name in os.listdir(inset_directory)
                         if name.endswith(".tif"))
        if not rasters:
            continue
        layer_path = os.path.join(
            FNAMES.osm_dir(latitude, longitude),
            "%+03d%+04d_airports.osm.bz2" % (latitude, longitude))
        if not os.path.isfile(layer_path):
            # NEVER a query: an uncached layer is reported, not fetched.
            skipped["no_airports_layer"].extend(
                "%s/%s" % (stem, name) for name in rasters)
            continue
        tile = CFG.Tile(latitude, longitude, "")
        tile.read_from_config()
        layer = OSM.OSM_layer()
        OSM.OSM_queries_to_OSM_layer(VMAP.AIRPORTS_QUERIES, layer, latitude,
                                     longitude, ["all"],
                                     cached_suffix="airports")
        dico = VMAP.build_airports_dico(tile, layer)
        configured_margin_m = float(getattr(
            tile, "airport_elevation_inset_margin_m", 2000.0))
        mid_latitude = latitude + 0.5
        boundaries = {}
        for airport in dico:
            if not isinstance(airport, str):
                continue
            boundary = dico[airport].get("boundary")
            if boundary is None or boundary.is_empty:
                continue
            (xmin, ymin, xmax, ymax) = boundary.bounds
            boundaries[airport.upper()] = (longitude + xmin, latitude + ymin,
                                           longitude + xmax, latitude + ymax)
        for name in rasters:
            path = os.path.join(inset_directory, name)
            airport = INSETS._inset_icao_from_path(path)
            boundary_box = boundaries.get(airport.upper())
            if boundary_box is None:
                skipped["not_in_dico"].append("%s/%s" % (stem, name))
                continue
            header = INSETS._inset_header_geometry(path)
            delivered = pixel_lon = pixel_lat = None
            if header is not None:
                (geotransform, rows, columns) = header
                west, north = geotransform[0], geotransform[3]
                delivered = (west, north + rows * geotransform[5],
                             west + columns * geotransform[1], north)
                pixel_lon = abs(geotransform[1])
                pixel_lat = abs(geotransform[5])
            manifest = _manifest_of(path)
            records.append({
                "tile_stem": stem, "lat": latitude, "lon": longitude,
                "mid_latitude": mid_latitude, "name": name, "path": path,
                "airport": airport,
                "provider": INSETS._inset_provider_code_from_path(path),
                "boundary_box": boundary_box,
                "requested_box": (
                    _box_from(manifest.get("requested_bounding_box_wgs84"))
                    or _box_from(manifest.get("bounding_box_wgs84"))),
                "delivered_box": delivered,
                "pixel_lon": pixel_lon, "pixel_lat": pixel_lat,
                "configured_margin_m": configured_margin_m,
            })
    out("  corpus: %d raster(s) judgeable, %d skipped (no cached airports "
        "layer), %d skipped (airport not in today's dico)"
        % (len(records), len(skipped["no_airports_layer"]),
           len(skipped["not_in_dico"])))
    return records, skipped


# =====================================================================
# Sections
# =====================================================================
def _stale_at(record, margin_m):
    """``(is_stale, shortfalls)`` for one record at one functional margin,
    judged against the DELIVERED box with a one-delivered-pixel tolerance.
    ``(None, None)`` when the raster could not be opened.
    """
    if record["delivered_box"] is None:
        return None, None
    required = expand_box(record["boundary_box"], margin_m,
                          record["mid_latitude"])
    stale = fails_to_contain(required, record["delivered_box"],
                             record["pixel_lon"], record["pixel_lat"])
    return stale, edge_shortfalls_m(required, record["delivered_box"],
                                    record["mid_latitude"])


def section_sweep(records, margins_m, name_below_m, out=print):
    out("")
    out("=== SWEEP: rasters failing to contain (boundary + m_min) ===")
    out("    judged against the DELIVERED box, tolerance one delivered "
        "pixel per axis")
    providers = sorted({record["provider"] for record in records})
    header = "%8s  %6s  " % ("m_min", "stale") + "  ".join(
        "%s" % provider[:14] for provider in providers)
    out(header)
    results = {}
    for margin_m in margins_m:
        stale = [record for record in records
                 if _stale_at(record, margin_m)[0]]
        results[margin_m] = stale
        by_provider = {
            provider: sum(1 for record in stale
                          if record["provider"] == provider)
            for provider in providers}
        out("%8d  %6d  " % (margin_m, len(stale)) + "  ".join(
            "%*d" % (max(len(provider[:14]), 1), by_provider[provider])
            for provider in providers))
    for margin_m in margins_m:
        if margin_m > name_below_m:
            continue
        out("")
        out("  --- stale at m_min = %d m (%d) ---"
            % (margin_m, len(results[margin_m])))
        for record in results[margin_m]:
            (_stale, shortfalls) = _stale_at(record, margin_m)
            out("    %s/%s  " % (record["tile_stem"], record["name"])
                + "  ".join("%s %+.1fm" % (edge, shortfalls[edge])
                            for edge in EDGES))
    return results


def section_battery(records, battery, out=print):
    out("")
    out("=== BATTERY: delivered margin per edge (metres beyond the "
        "aerodrome boundary) ===")
    wanted = {name.upper() for name in battery}
    for record in sorted(records, key=lambda item: item["airport"].upper()):
        if record["airport"].upper() not in wanted:
            continue
        if record["delivered_box"] is None:
            out("    %-6s %-18s  RASTER UNREADABLE"
                % (record["airport"], record["provider"]))
            continue
        # Shortfall against the bare boundary, negated: how far the
        # delivered raster reaches BEYOND the boundary on each edge.
        shortfalls = edge_shortfalls_m(record["boundary_box"],
                                       record["delivered_box"],
                                       record["mid_latitude"])
        out("    %-6s %-18s %s  " % (record["airport"], record["provider"],
                                     record["tile_stem"])
            + "  ".join("%s %7.0fm" % (edge, -shortfalls[edge])
                        for edge in EDGES))


def section_delivery(records, out=print):
    out("")
    out("=== DELIVERY: what the provider handed back vs what was asked "
        "for ===")
    out("    (worst edge, in metres SHORT of the requested box; and in "
        "delivered pixels)")
    out("%-18s %6s %6s %10s %10s %9s"
        % ("provider", "n", "short", "median_m", "max_m", "max_px"))
    limited = []
    for provider in sorted({record["provider"] for record in records}):
        rows = [record for record in records
                if record["provider"] == provider
                and record["delivered_box"] is not None
                and record["requested_box"] is not None]
        if not rows:
            continue
        worst = []
        for record in rows:
            shortfalls = edge_shortfalls_m(record["requested_box"],
                                           record["delivered_box"],
                                           record["mid_latitude"])
            metres = max(shortfalls.values())
            pixel_m = max(record["pixel_lon"] * GEO.lon_to_m(
                record["mid_latitude"]), record["pixel_lat"] * GEO.lat_to_m)
            worst.append((metres, metres / pixel_m if pixel_m else 0.0,
                          record))
        short = [item for item in worst if item[1] > PROVIDER_LIMIT_PIXELS]
        metres_sorted = sorted(item[0] for item in worst)
        out("%-18s %6d %6d %10.1f %10.1f %9.1f"
            % (provider, len(rows), len(short),
               metres_sorted[len(metres_sorted) // 2], metres_sorted[-1],
               max(item[1] for item in worst)))
        if short:
            limited.append((provider, short))
    for provider, short in limited:
        out("")
        out("  --- %s: %d raster(s) more than %.0f delivered pixels short "
            "of the REQUEST ---" % (provider, len(short),
                                    PROVIDER_LIMIT_PIXELS))
        out("      a re-cut re-asks for the same box and gets the same "
            "clipped raster: this is a WARN class, never a RE-CUT class")
        for metres, pixels, record in sorted(
                short, key=lambda item: item[0], reverse=True)[:8]:
            out("      %s/%s  %.0f m (%.0f px) short of its request"
                % (record["tile_stem"], record["name"], metres, pixels))
        if len(short) > 8:
            out("      ... and %d more" % (len(short) - 8))
    return limited


def implied_margins_m(record):
    """The margin the REQUEST carried on each edge, measured against
    TODAY's boundary, in metres.

    ``_airport_bounding_boxes`` is pure arithmetic over
    ``boundary.bounds`` and ``airport_elevation_inset_margin_m``, and
    every strategy stores that box verbatim.  So for a raster cut with
    today's margin over today's boundary all four numbers are the
    configured margin; anything else says which INPUT moved.
    """
    # edge_shortfalls_m is positive when the covering box falls SHORT; a
    # request that reaches 2000 m beyond the boundary reads as -2000.
    shortfalls = edge_shortfalls_m(record["boundary_box"],
                                   record["requested_box"],
                                   record["mid_latitude"])
    return {edge: -shortfalls[edge] for edge in EDGES}


def classify_cause(record, uniform_tolerance_m=1.0):
    """Why the shipped rule calls this raster stale: WHICH INPUT MOVED.

    The margin deficit per edge is ``configured_margin_m`` minus the
    margin the request actually carried against today's boundary.  Only a
    POSITIVE deficit can make a raster stale (a request that over-reaches
    is a superset and stays valid), so the classification keys on the
    worst positive deficit and on whether all four edges moved together:

    ``margin setting``    all four deficits equal within
                          ``uniform_tolerance_m`` and at least 10 m -- the
                          cut ran under a different
                          ``airport_elevation_inset_margin_m``.
    ``boundary moved ...`` otherwise: the OSM aerodrome boundary's bounds
                          are not where they were at cut time, bucketed by
                          how far.

    NOT float noise, and the tool deliberately offers no such bucket: the
    box arithmetic is IEEE double over degrees, whose rounding is ~1e-10
    deg, while the staleness tolerance is 1e-6 deg (0.11 m).  Three to
    four orders of magnitude separate them, so a deficit that clears the
    tolerance at all is a real input change.
    """
    margins = implied_margins_m(record)
    configured = record["configured_margin_m"]
    deficits = {edge: configured - margins[edge] for edge in EDGES}
    worst = max(deficits.values())
    spread = max(deficits.values()) - min(deficits.values())
    if spread <= uniform_tolerance_m and worst >= 10.0:
        return "margin setting", deficits
    if worst < 1.0:
        return "boundary moved < 1 m", deficits
    if worst < 10.0:
        return "boundary moved 1-10 m", deficits
    return "boundary moved >= 10 m", deficits


def section_shipped(records, warn_margin_m, out=print):
    out("")
    out("=== SHIPPED RULE vs THE PROPOSED PAIR ===")
    shipped, recut, warn, unjudgeable = [], [], [], []
    buckets = {"< 0.1 m": [], "0.1-1 m": [], "1-10 m": [], "10-100 m": [],
               ">= 100 m": []}
    for record in records:
        required = expand_box(record["boundary_box"],
                              record["configured_margin_m"],
                              record["mid_latitude"])
        requested = record["requested_box"]
        if requested is None:
            unjudgeable.append(record)
            continue
        # The rule that ships today, and the proposed RE-CUT rule: they
        # are the same predicate -- required vs the box asked for at cut
        # time, at INSET_BOUNDING_BOX_TOLERANCE_DEGREES.
        if INSETS._bounding_box_extends_beyond(required, requested):
            shipped.append(record)
            recut.append(record)
            metres = max(edge_shortfalls_m(required, requested,
                                           record["mid_latitude"]).values())
            if metres < 0.1:
                buckets["< 0.1 m"].append((metres, record))
            elif metres < 1.0:
                buckets["0.1-1 m"].append((metres, record))
            elif metres < 10.0:
                buckets["1-10 m"].append((metres, record))
            elif metres < 100.0:
                buckets["10-100 m"].append((metres, record))
            else:
                buckets[">= 100 m"].append((metres, record))
        if _stale_at(record, warn_margin_m)[0]:
            warn.append(record)
    out("    shipped rule (required vs requested-at-cut-time, 1e-6 deg): "
        "%d stale" % len(shipped))
    out("    proposed RE-CUT (identical predicate)                     : "
        "%d" % len(recut))
    out("    proposed WARN   (boundary + %d m not inside delivered)    : "
        "%d" % (warn_margin_m, len(warn)))
    out("    manifests with no requested box (unjudgeable, reusable)   : "
        "%d" % len(unjudgeable))
    both = {id(record) for record in recut} & {id(record) for record in warn}
    out("    both RE-CUT and WARN: %d   RE-CUT only: %d   WARN only: %d"
        % (len(both), len(recut) - len(both), len(warn) - len(both)))
    out("")
    out("  --- the shipped rule's shortfall, bucketed ---")
    for label in ("< 0.1 m", "0.1-1 m", "1-10 m", "10-100 m", ">= 100 m"):
        rows = buckets[label]
        out("    %-10s %4d   %s" % (
            label, len(rows),
            ", ".join(sorted({record["provider"] for _m, record in rows}))
            or "-"))
    for label in ("10-100 m", ">= 100 m"):
        for metres, record in sorted(
                buckets[label], key=lambda item: item[0], reverse=True)[:10]:
            out("      %-10s %s/%s  %.1f m"
                % (label, record["tile_stem"], record["name"], metres))
    out("")
    out("  --- WHICH INPUT MOVED (the shipped rule's %d) ---" % len(shipped))
    causes = {}
    for record in shipped:
        (cause, deficits) = classify_cause(record)
        causes.setdefault(cause, []).append((record, deficits))
    for cause in sorted(causes):
        rows = causes[cause]
        worst = sorted(max(deficits.values()) for _r, deficits in rows)
        out("    %-22s %4d   worst deficit min %.2fm median %.2fm max %.2fm"
            "   providers: %s" % (
                cause, len(rows), worst[0], worst[len(worst) // 2], worst[-1],
                ", ".join(sorted({record["provider"] for record, _d in rows}))))
        for record, deficits in rows[:4]:
            out("        %s/%s  margin deficit per edge: %s"
                % (record["tile_stem"], record["name"],
                   "  ".join("%s %.2fm" % (edge, deficits[edge])
                             for edge in EDGES)))
        if len(rows) > 4:
            out("        ... and %d more" % (len(rows) - 4))
    return {"shipped": shipped, "recut": recut, "warn": warn,
            "causes": causes}


# =====================================================================
def parse_margins(text):
    try:
        return [float(part) for part in text.split(",") if part.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--margins must be comma-separated metres, got: " + text)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only coverage census of the airport elevation "
                    "inset cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--section", default="all",
                        choices=("all", "sweep", "battery", "delivery",
                                 "shipped"))
    parser.add_argument("--margins", type=parse_margins,
                        default=list(DEFAULT_MARGINS_M),
                        help="functional margins to sweep, metres")
    parser.add_argument("--battery", default=",".join(DEFAULT_BATTERY),
                        help="comma-separated airport keys for --section "
                             "battery")
    parser.add_argument("--warn-margin-m", type=float, default=500.0,
                        help="functional margin the proposed WARN rule "
                             "uses (default 500)")
    parser.add_argument("--name-below-m", type=float, default=500.0,
                        help="name every stale raster at margins up to "
                             "this (default 500)")
    parser.add_argument("--elevation-dir", default=None,
                        help="read this inset cache instead of "
                             "FNAMES.Elevation_dir")
    args = parser.parse_args(argv)

    elevation_directory = args.elevation_dir or FNAMES.Elevation_dir
    print("inset coverage census — %s" % elevation_directory)
    (records, _skipped) = collect_records(elevation_directory)
    if args.section in ("all", "sweep"):
        section_sweep(records, args.margins, args.name_below_m)
    if args.section in ("all", "battery"):
        section_battery(records, args.battery.split(","))
    if args.section in ("all", "delivery"):
        section_delivery(records)
    if args.section in ("all", "shipped"):
        section_shipped(records, args.warn_margin_m)
    return 0


if __name__ == "__main__":
    from shared_repo_guard import SharedRepoWriteGuard

    _guard = SharedRepoWriteGuard(requested=(), root=os.getcwd())
    with _guard:
        _rc = main()
    print("[guard] blocked writes: %d" % len(_guard.blocked))
    for _entry in _guard.blocked[:20]:
        print("   ", _entry)
    sys.exit(_rc or (1 if _guard.blocked else 0))
