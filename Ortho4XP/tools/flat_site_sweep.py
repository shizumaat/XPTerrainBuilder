#!/usr/bin/env python3
"""FLAT-SITE sweep — run the detector IN-PROCESS across a set of airports.

Spec: ``docs/specs/flat-site-detector-spec.md`` section 3 ("the
deliverable the owner reads").  For every airport named, this reads the
CIFP thresholds, the on-disk base DEM tile and the apt.dat
pavement/boundary extent, calls ``auto_patch.flat_site.classify_site``
and prints one table: per airport all four signals plus the verdict.

**It measures nothing itself.**  Every number comes from the detector's
own code path — the same functions the pipeline calls at its DEM-in-hand
point — so a sweep row and a build's ``site_class`` sidecar record cannot
disagree.  A private re-implementation of any signal here would be the
census-wrapper defect (tools/INDEX.md).

NO BUILDS, NO NETWORK, NO WRITES.  The DEM is the base ``.hgt`` already
on disk for the tile (``--dem-source base``), read through
``O4_DEM_Utils.read_elevation_from_file`` and never composed, densified
or fetched: composing would run production DEM prep, which is a build
step and can touch the shared data repo.  An airport whose tile has no
base DEM on disk, or no CIFP file, is reported ``no_data`` — never
skipped silently and never downloaded.

Run from ``Ortho4XP/``::

    venv/bin/python tools/flat_site_sweep.py                  # the spec's set
    venv/bin/python tools/flat_site_sweep.py OTHH HECA        # named airports
    venv/bin/python tools/flat_site_sweep.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _path in (os.path.join(_ROOT, "src"), _ROOT, os.path.join(_ROOT, "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)


#: The spec section 3 set, in the spec's order, followed by the OWNER-NAMED
#: FLAT TEST AIRPORTS (spec section 3 amendment, owner 2026-08-09).  An
#: airport whose tile raster is absent reports ``no_data`` — never skipped.
DEFAULT_AIRPORTS = ("OTHH", "OTBD", "OTBH", "HEAZ", "HECA",
                    "SPJC", "SPLP", "CYXY", "KCLT", "KBNA",
                    "VHHH", "VMMC", "YSSY", "KSFO", "KOAK", "KBOS")

#: RECORDED EXPECTATIONS.  A row that disagrees is a FINDING to report
#: with its numbers, never a constant to tune.  The first four are the
#: spec's original set; the six below are the owner's named flat test
#: airports (2026-08-09), all expected flat candidates.
EXPECTED = {
    "OTHH": "flat_candidate",
    "HECA": "not_flat",
    "KCLT": "not_flat",
    "CYXY": "not_flat",
    "VHHH": "flat_candidate",
    "VMMC": "flat_candidate",
    "YSSY": "flat_candidate",
    "KSFO": "flat_candidate",
    "KOAK": "flat_candidate",
    "KBOS": "flat_candidate",
}


def _tile_name(tile_lat: int, tile_lon: int) -> str:
    """``N25E051`` — the standard whole-tile raster stem."""
    return (f"{'S' if tile_lat < 0 else 'N'}{abs(tile_lat):02d}"
            f"{'W' if tile_lon < 0 else 'E'}{abs(tile_lon):03d}")


def _base_dem_path(tile_lat: int, tile_lon: int, *,
                   elevation_dir: str | None = None,
                   dem_paths: dict | None = None):
    """``(path, origin)`` for a tile's base raster, or ``(None, None)``.

    Search order, most explicit first:

    1. ``--dem-path TILE=PATH`` — an operator-named raster;
    2. ``--elevation-dir DIR`` — a LANE-LOCAL directory holding
       ``<TILE>.hgt``.  This is how an airport whose tile is not in the
       shared corpus is swept without touching the corpus: spec §3's
       amendment ("the sweep tool takes a DEM path — no shared-repo
       write, no corpus ceremony");
    3. the shared corpus, via the engine's own ``FNAMES`` layout.
    """
    import O4_File_Names as FNAMES

    tile = _tile_name(tile_lat, tile_lon)
    explicit = (dem_paths or {}).get(tile)
    if explicit:
        if not os.path.isfile(explicit):
            return None, None
        return explicit, "explicit (--dem-path)"
    if elevation_dir:
        candidate = os.path.join(elevation_dir, tile + ".hgt")
        if os.path.isfile(candidate):
            return candidate, "lane-local (--elevation-dir)"
    path = FNAMES.base_file_name(tile_lat, tile_lon) + ".hgt"
    if os.path.isfile(path):
        return path, "shared corpus"
    return None, None


def _load_base_dem(tile_lat: int, tile_lon: int, elevation_level: str, *,
                   elevation_dir: str | None = None,
                   dem_paths: dict | None = None):
    """The tile's base DEM, read straight off disk.  None when absent."""
    import O4_DEM_Utils as DEM

    path, origin = _base_dem_path(tile_lat, tile_lon,
                                  elevation_dir=elevation_dir,
                                  dem_paths=dem_paths)
    if path is None:
        return None, None, None
    dem = DEM.DEM(tile_lat, tile_lon, path, fill_nodata=True,
                  info_only=False, elevation_level=elevation_level)
    return dem, path, origin


def _load_airport_inset_dem(tile_lat: int, tile_lon: int, icao: str,
                            elevation_level: str):
    """THE SURFACE PRODUCTION GRADES ON, when an inset is cached for this
    airport: the fetched airport-elevation inset GeoTIFF, plus the
    provenance record the bake would stamp on the DEM.

    Read-only and never composed — production BLENDS this into the base
    with a feather, so a row measured here is the inset's own surface
    over the part of the extent it covers, which is the airport itself.
    The provenance comes from ``O4_Airport_Elevation_Insets``' OWN reader
    (``_inset_bake_provenance_entry``), the same one the bake uses, so
    the source class is the fetch sidecar's declared
    ``native_resolution_m`` and never a value this tool invented.
    """
    import O4_Airport_Elevation_Insets as INSETS
    import O4_DEM_Utils as DEM

    candidates = [p for p in INSETS.list_cached_inset_dems(tile_lat, tile_lon)
                  if os.path.basename(p).upper().startswith(
                      str(icao).upper() + "_")]
    if not candidates:
        return None, None, None
    path = candidates[0]
    entry = INSETS._inset_bake_provenance_entry(path)
    dem = DEM.DEM(tile_lat, tile_lon, path, fill_nodata=False,
                  info_only=False, elevation_level=elevation_level)
    return dem, path, {"insets": [entry], "raw": False}


def sweep_one(icao: str, xplane_root: str, *, elevation_level: str,
              dem_source: str = "base",
              elevation_dir: str | None = None,
              dem_paths: dict | None = None,
              patch_dir: str | None = None) -> dict:
    """One airport's detector record plus the inputs it was measured on."""
    import O4_File_Names as FNAMES
    from auto_patch import apt_dat_reader as APR
    from auto_patch import flat_site
    from auto_patch.layout import _airport_anchor, _projection
    from auto_patch.osm_load import _pick_best_apt_dat_against_osm

    row = {"icao": icao.upper(), "apt_dat": None, "dem_path": None,
           "record": None, "note": None}

    apt_path = _pick_best_apt_dat_against_osm(xplane_root, icao)
    if apt_path is None:
        row["note"] = "no apt.dat for this ICAO"
        return row
    row["apt_dat"] = apt_path
    apt = APR.load_airport(apt_path, icao)
    if apt is None:
        row["note"] = "apt.dat has no airport block"
        return row

    anchor = _airport_anchor(apt)
    to_m = _projection(anchor)
    tile_lat = int(math.floor(anchor[0]))
    tile_lon = int(math.floor(anchor[1]))
    row["tile"] = f"{tile_lat:+03d}{tile_lon:+04d}"

    dem_meta = None
    dem_origin = None
    if dem_source == "airport-inset":
        dem, dem_path, dem_meta = _load_airport_inset_dem(
            tile_lat, tile_lon, icao, elevation_level)
        dem_origin = None if dem is None else "shared corpus (inset cache)"
        if dem is None:
            row["note"] = f"no cached airport inset for {icao}"
    else:
        dem, dem_path, dem_origin = _load_base_dem(
            tile_lat, tile_lon, elevation_level,
            elevation_dir=elevation_dir, dem_paths=dem_paths)
        if dem is None:
            row["note"] = (
                f"no base raster for tile {_tile_name(tile_lat, tile_lon)} "
                f"— supply one with --elevation-dir/--dem-path")
    row["dem_source"] = dem_source
    row["dem_path"] = dem_path
    row["dem_origin"] = dem_origin
    row["dem_tile"] = _tile_name(tile_lat, tile_lon)

    extent_m = flat_site.extent_from_apt(apt, to_m)
    elevations = flat_site.cifp_threshold_elevations(xplane_root, icao)
    if not elevations:
        row["note"] = ((row["note"] + "; " if row["note"] else "")
                       + "no CIFP file")
    if patch_dir is None:
        patch_dir = FNAMES.patch_dir(tile_lat, tile_lon)
    pack = flat_site.pack_seat_targets(patch_dir, icao)

    row["record"] = flat_site.classify_site(
        icao=icao, cifp_elevations_m=elevations, dem=dem,
        tile_lat=tile_lat, tile_lon=tile_lon, anchor=anchor,
        extent_m=extent_m, dem_meta=dem_meta,
        pack_targets=pack["targets"], pack_meta=pack)
    row["extent_km2"] = (None if extent_m is None
                         else round(extent_m.area / 1e6, 3))
    return row


def _cell(value, digits=2):
    return "—" if value is None else f"{float(value):.{digits}f}"


def _pct(fraction):
    """S2a's excluded share as a percentage.  "—" means the sea-band
    exclusion did NOT run (no Z0, or a site at or below sea level whose
    zeros are plausible terrain) — a different statement from "0 %"."""
    return "—" if fraction is None else f"{100.0 * float(fraction):.0f}%"


def print_table(rows) -> None:
    header = (f"{'ICAO':<6}{'verdict':<16}{'Z0 m':>8}{'S1 spr':>8}"
              f"{'S2 slope%':>10}{'S2 relief':>10}{'floor':>7}"
              f"{'class':>11}{'sea%':>7}{'S3 off':>8}{'S4':>22}"
              f"{'expect':>14}")
    print(header)
    print("-" * len(header))
    for row in rows:
        record = row.get("record") or {}
        s4 = record.get("s4") or {}
        if s4.get("pass") is None:
            s4_text = f"no_data (n={s4.get('n', 0)})"
        else:
            s4_text = (f"{'ok' if s4['pass'] else 'FAIL'} n={s4.get('n')} "
                       f"off {_cell(s4.get('offset_m'))}")
        verdict = record.get("verdict") or "no_data"
        expected = EXPECTED.get(row["icao"])
        if expected is None:
            flag = ""
        elif expected == verdict:
            flag = f"= {expected}"
        else:
            flag = f"!! {expected}"
        print(f"{row['icao']:<6}{verdict:<16}"
              f"{_cell(record.get('z0_m')):>8}"
              f"{_cell(record.get('s1_spread_m')):>8}"
              f"{_cell(record.get('s2_slope_pct'), 3):>10}"
              f"{_cell(record.get('s2_relief_m')):>10}"
              f"{_cell(record.get('s2_relief_floor_m'), 1):>7}"
              f"{str(record.get('s2_source_class') or '—'):>11}"
              f"{_pct(record.get('s2_sea_excluded_frac')):>7}"
              f"{_cell(record.get('s3_offset_m')):>8}"
              f"{s4_text:>22}{flag:>14}")
        if row.get("note"):
            print(f"       note: {row['note']}")


def print_dem_provenance(rows) -> None:
    """WHICH raster every row was measured on, and where it came from.

    Spec §3 amendment: the download source per tile is part of the
    deliverable — a row measured on a lane-local raster and a row
    measured on the shared corpus are not the same kind of evidence.
    """
    seen = {}
    for row in rows:
        tile = row.get("dem_tile")
        if not tile:
            continue
        seen.setdefault(tile, (row.get("dem_origin"), row.get("dem_path")))
    if not seen:
        return
    print("DEM PROVENANCE (per tile)")
    for tile in sorted(seen):
        origin, path = seen[tile]
        if origin is None:
            print(f"  {tile}: ABSENT — no raster supplied")
        else:
            print(f"  {tile}: {origin}\n           {path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("icaos", nargs="*", default=None,
                        help="airports to sweep (default: the spec set)")
    parser.add_argument("--xplane-root", default=None,
                        help="X-Plane install root (default: the test "
                             "fixture's resolution)")
    parser.add_argument("--dem-source", default="base",
                        choices=("base", "airport-inset"),
                        help="'base' (default) reads the tile's base .hgt; "
                             "'airport-inset' reads the cached airport "
                             "elevation inset — THE SURFACE PRODUCTION "
                             "GRADES ON where one exists")
    parser.add_argument("--elevation-dir", default=None,
                        help="a LANE-LOCAL directory holding <TILE>.hgt "
                             "rasters, searched before the shared corpus — "
                             "how an airport whose tile is not in the corpus "
                             "is swept without writing it")
    parser.add_argument("--dem-path", action="append", default=[],
                        metavar="TILE=PATH",
                        help="explicit raster for one tile, e.g. "
                             "N22E113=/path/to/N22E113.hgt (repeatable)")
    parser.add_argument("--elevation-level", default="auto",
                        help="tile elevation level the base DEM is read "
                             "under; drives the base-tier source class")
    parser.add_argument("--patch-dir", default=None,
                        help="directory holding o4_object_foot_pads.json "
                             "(default: this tree's Patches/<tile>)")
    parser.add_argument("--json", dest="json_out", default=None,
                        help="also write the full records here")
    parser.add_argument("--detail", action="store_true",
                        help="print every field of every record")
    args = parser.parse_args(argv)

    xplane_root = args.xplane_root
    if xplane_root is None:
        from conftest import xplane_root as _fixture_root

        xplane_root = _fixture_root()

    dem_paths = {}
    for item in args.dem_path:
        if "=" not in item:
            parser.error(f"--dem-path wants TILE=PATH, got {item!r}")
        tile, path = item.split("=", 1)
        dem_paths[tile.strip().upper()] = os.path.expanduser(path.strip())

    icaos = [i.upper() for i in (args.icaos or DEFAULT_AIRPORTS)]
    rows = []
    for icao in icaos:
        try:
            rows.append(sweep_one(icao, xplane_root,
                                  elevation_level=args.elevation_level,
                                  dem_source=args.dem_source,
                                  elevation_dir=args.elevation_dir,
                                  dem_paths=dem_paths,
                                  patch_dir=args.patch_dir))
        except Exception as error:
            rows.append({"icao": icao, "record": None,
                         "note": f"{type(error).__name__}: {error}"})

    print()
    print_table(rows)
    print()
    print_dem_provenance(rows)
    print()
    surprises = [r["icao"] for r in rows
                 if r["icao"] in EXPECTED
                 and (r.get("record") or {}).get("verdict") != EXPECTED[
                     r["icao"]]]
    if surprises:
        print(f"FINDINGS: {', '.join(surprises)} disagree with the spec's "
              f"recorded expectations — report the numbers, do not tune.")
    else:
        print("Every recorded expectation held.")

    if args.detail:
        for row in rows:
            print()
            print(json.dumps(row, indent=2, sort_keys=True))
    if args.json_out:
        with open(args.json_out, "w") as handle:
            json.dump(rows, handle, indent=2, sort_keys=True)
        print(f"records written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
