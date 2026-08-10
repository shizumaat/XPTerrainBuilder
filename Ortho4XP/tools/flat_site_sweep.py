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


#: The spec section 3 set, in the spec's order.  KBNA is included and
#: reports ``no_data`` unless its tile data is present in the corpus.
DEFAULT_AIRPORTS = ("OTHH", "OTBD", "OTBH", "HEAZ", "HECA",
                    "SPJC", "SPLP", "CYXY", "KCLT", "KBNA")

#: The spec's RECORDED EXPECTATIONS.  A row that disagrees is a FINDING
#: to report with its numbers, never a constant to tune.
EXPECTED = {
    "OTHH": "flat_candidate",
    "HECA": "not_flat",
    "KCLT": "not_flat",
    "CYXY": "not_flat",
}


def _base_dem_path(tile_lat: int, tile_lon: int) -> str | None:
    """The on-disk base ``.hgt`` for a tile, or None when absent."""
    import O4_File_Names as FNAMES

    path = FNAMES.base_file_name(tile_lat, tile_lon) + ".hgt"
    return path if os.path.isfile(path) else None


def _load_base_dem(tile_lat: int, tile_lon: int, elevation_level: str):
    """The tile's base DEM, read straight off disk.  None when absent."""
    import O4_DEM_Utils as DEM

    path = _base_dem_path(tile_lat, tile_lon)
    if path is None:
        return None, None
    dem = DEM.DEM(tile_lat, tile_lon, path, fill_nodata=True,
                  info_only=False, elevation_level=elevation_level)
    return dem, path


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
    if dem_source == "airport-inset":
        dem, dem_path, dem_meta = _load_airport_inset_dem(
            tile_lat, tile_lon, icao, elevation_level)
        if dem is None:
            row["note"] = f"no cached airport inset for {icao}"
    else:
        dem, dem_path = _load_base_dem(tile_lat, tile_lon, elevation_level)
        if dem is None:
            row["note"] = f"no base DEM on disk for {row['tile']}"
    row["dem_source"] = dem_source
    row["dem_path"] = dem_path

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


def print_table(rows) -> None:
    header = (f"{'ICAO':<6}{'verdict':<16}{'Z0 m':>8}{'S1 spr':>8}"
              f"{'S2 slope%':>10}{'S2 relief':>10}{'floor':>7}"
              f"{'class':>11}{'whence':>10}{'S3 off':>8}{'S4':>22}"
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
              f"{str(record.get('s2_source_whence') or '—'):>10}"
              f"{_cell(record.get('s3_offset_m')):>8}"
              f"{s4_text:>22}{flag:>14}")
        if row.get("note"):
            print(f"       note: {row['note']}")


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

    icaos = [i.upper() for i in (args.icaos or DEFAULT_AIRPORTS)]
    rows = []
    for icao in icaos:
        try:
            rows.append(sweep_one(icao, xplane_root,
                                  elevation_level=args.elevation_level,
                                  dem_source=args.dem_source,
                                  patch_dir=args.patch_dir))
        except Exception as error:
            rows.append({"icao": icao, "record": None,
                         "note": f"{type(error).__name__}: {error}"})

    print()
    print_table(rows)
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
