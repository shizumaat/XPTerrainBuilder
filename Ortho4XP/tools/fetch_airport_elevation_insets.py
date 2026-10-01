"""Fetch and cache a high-resolution airport elevation inset from the terminal.

Standalone command-line front end to
``src/O4_Airport_Elevation_Insets.py``.  It runs the SAME declarative
provider discovery + access-strategy fetch + cache/index/provenance chain
the tile build performs (this tool IMPORTS the module, never edits it), so a
human can pre-warm or refresh the ``Elevation_data/`` inset cache for one
airport and inspect the result before a full tile build.

The cache is written under ``Elevation_data/<block>/<tile>_airport_insets/``
relative to the current working directory (Ortho4XP's standard resource
root), exactly where the build looks for it.  ``--elevation-data-dir`` points
the cache elsewhere (for example a specific worktree checkout).

What it does
------------
1. Resolves the target 1 degree tile from ``--tile`` or the bounding-box
   centre.
2. Selects providers via ``airport_elevation_providers`` semantics
   (``auto`` = every enabled ``role=airport_inset`` definition by priority,
   or an explicit comma-separated list of provider codes).
3. Runs discovery + fetch for the airport bounding box, writing the
   EPSG:4326 float32 GeoTIFF, its provenance sidecar, and the tile
   ``index.json`` (negative results included).
4. Prints the cache paths, the provenance, and -- when ``gdallocationinfo``
   is on the PATH -- a bilinear elevation sample at an optional probe point.

Requires the GDAL python bindings (osgeo) and network access.

Usage:
    venv/bin/python tools/fetch_airport_elevation_insets.py \\
        --airport ICAO --bbox WEST,SOUTH,EAST,NORTH [options]

Options:
    --airport ICAO            Airport identifier used as the cache key (required).
    --bbox W,S,E,N            Bounding box in EPSG:4326 degrees (required).
    --tile LAT,LON            Integer tile corner; default = bbox-centre floor.
    --provider CODES          "auto" (default) or a comma-separated code list.
    --resolution-m FLOAT      Warp target resolution in metres (default:
                              auto — each provider's best available,
                              floored at 0.5 m, matching production).
    --refresh                 Ignore cached results and re-query/re-fetch.
    --probe LAT,LON           Sample the fetched raster at this point and print it.
    --elevation-data-dir DIR  Write the cache under DIR instead of ./Elevation_data.
    --footprint-bbox W,S,E,N  The aerodrome boundary (as a rectangle) the
                              production fetch passes from OSM: airport-cover
                              rungs (USGS OPR, PITKIN1M, USGS LPC) are judged
                              over it and surgical LAS fetches cut to it
                              (#153; without it they see the whole box).

WITNESS MODE (``--witness ICAO``, promoted 2026-09-30 from the aoi154 /
opr153 / tx154 scratch ``witness.py`` scripts on their second use, RULINGS
``7e90032``): the airport box comes from apt.dat instead of ``--bbox`` --
THE apt.dat serving the ICAO (``engine_v2.select_apt_dat``, the one
selector; ``--apt-dat`` overrides), its aerodrome footprint (runway ends +
pavement nodes + 130 boundary rings, the gap census's ``footprint``) as the
production ``footprint_polygon``, and the inset box = the footprint's box
plus ``airport_elevation_inset_margin_m``.  The fetch is the production
chain above (``--provider`` as usual: ``auto`` runs the USGS3DEP ladder
with its global members, a code pins one provider), run under an ARMED
shared-repo write guard into ``--elevation-data-dir`` (required: a witness
never writes the shared corpus).  It prints ONE record: delivered provider
/ rung, native and stored resolution, box-wide valid fraction,
``airport_valid_fraction`` over the footprint box, bytes fetched, wall
time, the vertical-unit keys, the ARP-disc median vs the apt.dat field
elevation (``build_airport.inset_arp_sanity_record``, the harness's own
check), the inset read at every runway end, and every ladder rung row;
``--witness-json PATH`` also writes it.

    venv/bin/python tools/fetch_airport_elevation_insets.py --witness KRDU \\
        --elevation-data-dir tmp/LANE/Elevation_data --refresh

Examples:
    # Nashville (KBNA), tile +36-087, a box around the water-treatment shelf:
    venv/bin/python tools/fetch_airport_elevation_insets.py \\
        --airport KBNA --tile 36,-87 \\
        --bbox -86.72,36.10,-86.62,36.16 \\
        --probe 36.1376,-86.6759

    # Pin an explicit provider and force a refresh:
    venv/bin/python tools/fetch_airport_elevation_insets.py \\
        --airport KBNA --bbox -86.72,36.10,-86.62,36.16 \\
        --provider USGS3DEP --refresh
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

_TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
_SOURCE_DIRECTORY = os.path.join(
    os.path.dirname(_TOOLS_DIRECTORY), "src"
)
if _SOURCE_DIRECTORY not in sys.path:
    sys.path.insert(0, _SOURCE_DIRECTORY)

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS


def _parse_pair(text, label):
    parts = text.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            label + " must be two comma-separated numbers, got: " + text
        )
    return (float(parts[0]), float(parts[1]))


def _parse_bounding_box(text):
    parts = text.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "--bbox must be WEST,SOUTH,EAST,NORTH, got: " + text
        )
    return tuple(float(part) for part in parts)


#: The disc read at each runway end in witness mode: about one runway
#: half-width, so the read is the threshold's own pavement, not the strip.
RUNWAY_END_DISC_RADIUS_M = 15.0


def _harness_module():
    """``tools/harness/build_airport.py`` -- the ARP sanity check, the
    apt.dat selector's install root and the guard arming live there."""
    harness = os.path.join(_TOOLS_DIRECTORY, "harness")
    if harness not in sys.path:
        sys.path.insert(0, harness)
    import build_airport

    return build_airport


def _census_module():
    """``tools/elevation_gap_census.py`` -- the apt.dat airport reader and
    the aerodrome footprint (one parser for the census and the witness)."""
    if _TOOLS_DIRECTORY not in sys.path:
        sys.path.insert(0, _TOOLS_DIRECTORY)
    import elevation_gap_census

    return elevation_gap_census


def apt_dat_airport(apt_dat_path, icao, scratch_dir):
    """``(footprint_polygon, runway_ends)`` for ``icao`` from the ONE apt.dat
    block that serves it, or ``None``.  The block is read with the
    engine's reader and parsed by the gap census's ``iter_airports`` (one
    parser); the footprint is the census's ``footprint`` at zero buffer;
    ``runway_ends`` is ``[(name, lat, lon)]`` from every row 100."""
    from auto_patch.apt_dat_reader import _read_airport_block

    block = _read_airport_block(apt_dat_path, icao)
    if not block:
        return None
    census = _census_module()
    os.makedirs(scratch_dir, exist_ok=True)
    block_path = os.path.join(scratch_dir, "%s.apt.dat" % icao.upper())
    with open(block_path, "w", newline="\n") as handle:
        handle.write("\n".join(line.rstrip("\n") for line in block) + "\n")
    airport = next(iter(census.iter_airports(block_path)), None)
    if airport is None or not (airport.pts or airport.boundary):
        return None
    ends = []
    for line in block:
        columns = line.split()
        if columns[:1] == ["100"] and len(columns) >= 20:
            ends.append((columns[8], float(columns[9]), float(columns[10])))
            ends.append((columns[17], float(columns[18]),
                         float(columns[19])))
    polygon = census.footprint(airport, 0.0)
    if polygon.is_empty:
        # A runway-only block: its hull is a line.  The narrowest real
        # footprint is the runway itself.
        polygon = census.footprint(airport, RUNWAY_END_DISC_RADIUS_M)
    return (polygon, ends)


def witness_record(inset_path, apt_dat_path, icao, footprint_polygon,
                   runway_ends, wall_s):
    """THE WITNESS RECORD (pure: an inset, its sidecar and the apt.dat in;
    one dict out) -- what every holder-provider lane quoted per airport."""
    harness = _harness_module()
    sidecar = os.path.splitext(inset_path)[0] + ".json"
    try:
        with open(sidecar) as handle:
            provenance = json.load(handle)
    except (OSError, ValueError):
        provenance = {}
    ladder = provenance.get("ladder") or {}
    footprint_box = tuple(footprint_polygon.bounds)
    record = {
        "icao": icao,
        "inset": inset_path,
        "provider": provenance.get("provider"),
        "delivered_provider": ladder.get("delivered_provider"),
        "delivered_rung": ladder.get("delivered_rung"),
        "delivered_label": ladder.get("delivered_label"),
        "native_resolution_m": provenance.get("native_resolution_m"),
        "resolution_m": provenance.get("resolution_m"),
        "valid_fraction": round(INSETS.inset_valid_fraction(inset_path), 6),
        # THE CORE'S OWN COVER beside the cover AFTER the ladder fills
        # (spec las-tile §12): the sidecar's rung-selection number, else
        # (a pre-§12 sidecar) the raster's own cover -- one and the same
        # there, nothing was filled.
        "airport_valid_fraction": (
            provenance["airport_valid_fraction"]
            if provenance.get("airport_valid_fraction") is not None
            else round(INSETS.raster_valid_fraction_in_box(
                inset_path, footprint_box), 6)),
        "airport_filled_fraction": round(
            INSETS.raster_valid_fraction_in_box(inset_path, footprint_box),
            6),
        "fill": INSETS.inset_fill_summary(provenance),
        "holes": provenance.get("holes") or [],
        "footprint_box": [round(value, 6) for value in footprint_box],
        "bytes_fetched": provenance.get("bytes_fetched"),
        "wall_s": None if wall_s is None else round(wall_s, 1),
        "vertical_unit_source": provenance.get("vertical_unit_source"),
        "vertical_unit_applied": provenance.get("vertical_unit_applied"),
        "surround": provenance.get("surround"),
        "arp_sanity": harness.inset_arp_sanity_record(
            [inset_path], apt_dat_path, icao),
        "runway_ends": [],
        "rungs": [
            {key: row.get(key) for key in (
                "rung", "label", "provider", "role", "native_resolution_m",
                "outcome", "valid_fraction", "airport_valid_fraction",
                "vertical_unit_source", "vertical_unit_applied",
                "bytes_fetched", "unavailable_reason", "transient_reason")
             if row.get(key) is not None}
            for row in ladder.get("rungs_tried") or ()],
    }
    for (name, latitude, longitude) in runway_ends:
        (median, cells) = harness._inset_disc_median_m(
            inset_path, latitude, longitude, RUNWAY_END_DISC_RADIUS_M)
        record["runway_ends"].append({
            "end": name, "lat": latitude, "lon": longitude, "cells": cells,
            "inset_m": None if median is None else round(median, 3)})
    return record


def _print_witness(record):
    arp = record["arp_sanity"]
    worst = [entry.get("delta_m") for entry in arp.get("insets") or ()
             if entry.get("delta_m") is not None]
    print("\nWITNESS %s" % record["icao"])
    print("  delivered      %s (rung %s '%s'), provider record %s"
          % (record["delivered_provider"], record["delivered_rung"],
             record["delivered_label"], record["provider"]))
    print("  resolution     native %s m, stored %s m"
          % (record["native_resolution_m"], record["resolution_m"]))
    print("  cover          box valid %.4f, airport valid %.4f, airport "
          "filled %.4f"
          % (record["valid_fraction"], record["airport_valid_fraction"],
             record["airport_filled_fraction"]))
    print("  ladder fill    %s"
          % INSETS.inset_fill_summary_text(record["fill"]))
    for hole in record["holes"]:
        filled_by = hole.get("filled_by")
        print("  hole %-8s %8d cells %10.1f m2 filled by %-18s unfilled %d "
              "now %s m ring %s m seam %s m box %s"
              % (hole.get("kind"), hole.get("cells"), hole.get("area_m2"),
                 filled_by.get("label") if isinstance(filled_by, dict)
                 else filled_by,
                 hole.get("unfilled_cells"), hole.get("fill_median_m"),
                 hole.get("ring_median_m"), hole.get("seam_median_m"),
                 hole.get("bounding_box_wgs84")))
    print("  vertical unit  source %s, applied %s"
          % (record["vertical_unit_source"],
             record["vertical_unit_applied"]))
    print("  bytes / wall   %s / %s s"
          % (record["bytes_fetched"], record["wall_s"]))
    print("  ARP sanity     %s: field %s m, inset disc delta %s m"
          % (arp.get("status"), arp.get("field_elevation_m"),
             worst[0] if worst else arp.get("why")))
    for end in record["runway_ends"]:
        print("  runway end %-4s %s m (%d cells)"
              % (end["end"], end["inset_m"], end["cells"]))
    for row in record["rungs"]:
        print("  rung %s %-34s %-10s %-16s valid %s airport %s unit %s/%s"
              % (row.get("rung"), "%s [%s]" % (row.get("label"),
                                               row.get("provider")),
                 row.get("role") or "", row.get("outcome"),
                 row.get("valid_fraction"),
                 row.get("airport_valid_fraction"),
                 row.get("vertical_unit_source"),
                 row.get("vertical_unit_applied")))


def disable_providers_in_process(codes_text):
    """``--disable-provider CODE[,CODE]`` (witness mode): mark those
    provider definitions disabled IN THIS PROCESS ONLY -- the ladder then
    drops a ``provider:`` rung naming one (one line, the rung's own
    "disabled" path) and global assembly skips it, exactly as a shipped
    ``enabled=False`` would, without editing the shipped ``.elv``.  The
    spec §12 KGEG replay ("OPR removed from the ladder") is this.
    Returns the codes disabled (unknown codes refuse)."""
    if not codes_text:
        return []
    providers = INSETS.initialize_elevation_providers_dict()
    disabled = []
    for code in [c.strip() for c in codes_text.split(",") if c.strip()]:
        key = next((k for k in providers if k.upper() == code.upper()),
                   None)
        if key is None:
            raise SystemExit("ERROR: --disable-provider names no provider "
                             "%r" % code)
        providers[key] = dict(providers[key], enabled=False)
        disabled.append(key)
    return disabled


def run_witness(arguments) -> int:
    """``--witness ICAO``: the production fetch over the apt.dat airport,
    lane-local and guarded; prints and optionally writes the record."""
    import time

    import O4_Cfg_Vars

    icao = arguments.witness.upper()
    if not arguments.elevation_data_dir:
        print("ERROR: --witness needs --elevation-data-dir (a witness never "
              "writes the shared corpus).")
        return 2
    harness = _harness_module()
    apt_dat = arguments.apt_dat
    if not apt_dat:
        from auto_patch.engine_v2 import select_apt_dat

        apt_dat = select_apt_dat(harness._owner_xplane_root(), icao)
    if not apt_dat:
        print("ERROR: no apt.dat serves", icao)
        return 2
    scratch = os.path.join(FNAMES.Elevation_dir, "_witness")
    airport = apt_dat_airport(apt_dat, icao, scratch)
    if airport is None:
        print("ERROR: %s has no airport block / footprint in %s"
              % (icao, apt_dat))
        return 2
    (polygon, runway_ends) = airport
    (west, south, east, north) = polygon.bounds
    margin = (arguments.margin_m if arguments.margin_m is not None
              else O4_Cfg_Vars.cfg_tile_vars[
                  "airport_elevation_inset_margin_m"]["default"])
    latitude = (south + north) / 2.0
    margin_lon = margin / INSETS.GEO.lon_to_m(latitude)
    margin_lat = margin / INSETS.GEO.lat_to_m
    bounding_box = (west - margin_lon, south - margin_lat,
                    east + margin_lon, north + margin_lat)
    tile_latitude = int(math.floor(latitude))
    tile_longitude = int(math.floor((west + east) / 2.0))
    disabled = disable_providers_in_process(arguments.disable_provider)
    definitions = INSETS.select_provider_definitions(arguments.provider)
    if not definitions:
        print("ERROR: no airport-inset providers matched",
              repr(arguments.provider))
        return 2
    if disabled:
        print("  lane-local override: providers DISABLED in this process "
              "only (the shipped .elv files are untouched): %s"
              % ", ".join(disabled))
    print("Witness %s: apt.dat %s\n  footprint box %s\n  inset box %s\n"
          "  providers %s" % (icao, apt_dat, polygon.bounds, bounding_box,
                              ", ".join(d["code"] for d in definitions)))
    guard, _redirects = harness.arm_shared_repo_protection(
        os.path.dirname(_TOOLS_DIRECTORY), scratch, "witness_" + icao)
    # The harness import re-applies the data root (O4_Config_Utils ->
    # O4_File_Names.set_data_root), which points Elevation_dir back at the
    # worktree's mounted -- SHARED -- Elevation_data.  Re-assert the
    # lane-local root, and refuse if it still resolves into the shared
    # repo: the warp writes through GDAL (C level), where the Python guard
    # cannot see it (measured 2026-09-30, KRDU, two rasters).
    FNAMES.Elevation_dir = os.path.abspath(arguments.elevation_data_dir)
    import shared_repo_guard                   # tools/harness, on the path

    shared = os.path.realpath(str(shared_repo_guard.DATA_REPO))
    real = os.path.realpath(FNAMES.Elevation_dir)
    if real == shared or real.startswith(shared + os.sep):
        print("ERROR: --elevation-data-dir resolves into the shared data "
              "repo (%s); a witness writes lane-local only." % real)
        return 2
    started = time.time()
    with guard:
        INSETS.ensure_airport_insets(
            tile_latitude, tile_longitude, {icao: bounding_box},
            definitions, arguments.resolution_m,
            refresh=arguments.refresh, airport_polygons={icao: polygon})
    wall_s = time.time() - started
    print("[guard]", "shared repo UNCHANGED" if not guard.blocked
          else "BLOCKED %s" % (guard.blocked,))
    inset = next(
        (path for path in (
            FNAMES.airport_inset_dem(tile_latitude, tile_longitude, icao,
                                     definition["code"])
            for definition in definitions) if os.path.isfile(path)), None)
    if inset is None:
        print("\nNo inset was fetched (no provider reported coverage).")
        return 1
    record = witness_record(inset, apt_dat, icao, polygon, runway_ends,
                            wall_s)
    record["disabled_providers"] = disabled
    _print_witness(record)
    if arguments.witness_json:
        with open(arguments.witness_json, "w", newline="\n") as handle:
            json.dump(record, handle, indent=1, sort_keys=True, default=str)
    return 0 if not guard.blocked else 3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch one airport elevation inset into the cache.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--airport", default=None,
                        help="cache-key identifier (required without "
                             "--witness)")
    parser.add_argument(
        "--bbox",
        default=None,
        type=_parse_bounding_box,
        help="WEST,SOUTH,EAST,NORTH in EPSG:4326 degrees (required without "
             "--witness)",
    )
    parser.add_argument(
        "--witness", default=None, metavar="ICAO",
        help="witness mode: box + footprint from apt.dat, guarded "
             "lane-local fetch, one summary record (see the module doc)")
    parser.add_argument("--apt-dat", default=None,
                        help="--witness: the apt.dat to read (default: "
                             "the one selector's answer)")
    parser.add_argument("--margin-m", type=float, default=None,
                        help="--witness: inset margin beyond the footprint "
                             "(default: airport_elevation_inset_margin_m)")
    parser.add_argument(
        "--disable-provider", default=None, metavar="CODES",
        help="--witness: disable these provider codes in this process only "
             "(a lane-local ladder override; the .elv files are untouched)")
    parser.add_argument("--witness-json", default=None,
                        help="--witness: also write the record here")
    parser.add_argument(
        "--tile",
        default=None,
        help="integer tile corner LAT,LON (default: bbox-centre floor)",
    )
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--resolution-m", type=float, default=None)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--probe",
        default=None,
        help="LAT,LON to sample from the fetched raster",
    )
    parser.add_argument("--elevation-data-dir", default=None)
    parser.add_argument(
        "--footprint-bbox",
        default=None,
        type=_parse_bounding_box,
        help="the aerodrome boundary as WEST,SOUTH,EAST,NORTH (production "
             "passes the OSM boundary polygon)",
    )
    arguments = parser.parse_args()

    if arguments.elevation_data_dir:
        FNAMES.Elevation_dir = os.path.abspath(arguments.elevation_data_dir)

    if arguments.witness and not arguments.elevation_data_dir:
        # The lane-local refusal is answered before anything else (it
        # needs no GDAL; CI runners without osgeo read it too).
        print("ERROR: --witness needs --elevation-data-dir (a witness never "
              "writes the shared corpus).")
        return 2

    if not INSETS.has_gdal:
        print(
            "ERROR: the GDAL python bindings (osgeo) are unavailable; "
            "install them to fetch elevation insets."
        )
        return 2

    if arguments.witness:
        return run_witness(arguments)
    if not arguments.airport or not arguments.bbox:
        parser.error("--airport and --bbox are required without --witness")

    (west, south, east, north) = arguments.bbox
    if arguments.tile:
        (tile_latitude_raw, tile_longitude_raw) = _parse_pair(
            arguments.tile, "--tile"
        )
        tile_latitude = int(math.floor(tile_latitude_raw))
        tile_longitude = int(math.floor(tile_longitude_raw))
    else:
        tile_latitude = int(math.floor((south + north) / 2.0))
        tile_longitude = int(math.floor((west + east) / 2.0))

    provider_definitions = INSETS.select_provider_definitions(
        arguments.provider
    )
    if not provider_definitions:
        print(
            "ERROR: no airport-inset providers matched",
            repr(arguments.provider),
        )
        return 2
    print(
        "Providers (in order):",
        ", ".join(
            definition["code"] for definition in provider_definitions
        ),
    )
    print(
        "Tile: {:+d},{:+d}   bbox: {}".format(
            tile_latitude, tile_longitude, arguments.bbox
        )
    )

    footprint = {}
    if arguments.footprint_bbox:
        from shapely.geometry import box as _box

        footprint = {"airport_polygons": {
            arguments.airport: _box(*arguments.footprint_bbox)}}
    index = INSETS.ensure_airport_insets(
        tile_latitude,
        tile_longitude,
        {arguments.airport: arguments.bbox},
        provider_definitions,
        arguments.resolution_m,
        refresh=arguments.refresh,
        **footprint,
    )

    print("\nindex.json entry:")
    print(json.dumps(index.get(arguments.airport, {}), indent=2))

    fetched_path = None
    for definition in provider_definitions:
        candidate = FNAMES.airport_inset_dem(
            tile_latitude,
            tile_longitude,
            arguments.airport,
            definition["code"],
        )
        if os.path.isfile(candidate):
            fetched_path = candidate
            provenance_path = FNAMES.airport_inset_provenance(
                tile_latitude,
                tile_longitude,
                arguments.airport,
                definition["code"],
            )
            print("\nCached GeoTIFF:", candidate)
            if os.path.isfile(provenance_path):
                print("Provenance:", provenance_path)
                with open(provenance_path, "r") as handle:
                    print(json.dumps(json.load(handle), indent=2))
            break

    if fetched_path is None:
        print("\nNo inset was fetched (no provider reported coverage).")
        return 1

    if arguments.probe:
        (probe_latitude, probe_longitude) = _parse_pair(
            arguments.probe, "--probe"
        )
        _print_probe_sample(fetched_path, probe_latitude, probe_longitude)

    return 0


def _print_probe_sample(raster_path, latitude, longitude):
    """Print a bilinear elevation sample via gdallocationinfo, if available."""
    executable = shutil.which("gdallocationinfo")
    if not executable:
        print(
            "\n(gdallocationinfo not on PATH; skipping the probe sample.)"
        )
        return
    command = [
        executable,
        "-wgs84",
        "-b",
        "1",
        "-valonly",
        raster_path,
        repr(longitude),
        repr(latitude),
    ]
    try:
        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT
        ).decode()
    except subprocess.CalledProcessError as error:
        print("\nProbe failed:", error.output.decode())
        return
    print(
        "\nProbe at (lat={}, lon={}): {} m".format(
            latitude, longitude, output.strip()
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
