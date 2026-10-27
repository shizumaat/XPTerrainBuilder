#!/usr/bin/env python3
"""THE RUNWAY-END PIN CENSUS (owner RULINGS 2026-10-25a item 4: "how many
runways each rule flags. Report it to the owner before the gate is turned
on"; issues #1342, #1358; spec ``docs/findings/lrwypin-runway-end-pins.md``
§6).

Every CIFP airport of ``--cifp`` (the cfg's ``cifp_data_path``) is joined
to the Global Airports apt.dat (``airport/load.join_cifp``, the build's own
join) and judged by THE ENGINE'S OWN RULE (``airport/end_pins.verify`` and
``shifted_ends``; never a second implementation).  The DEM is the AUTHORED
sampler (``airport/dem.load_dem``: the base ``.hgt`` plus the airport's own
inset) where the shared corpus holds the tile; its class is the inset's
pixel (``law.tables.flat_source_class``), else ``coarse``.  No cross-check
cache is read unless ``--mod-cache`` names one (rule (c)).

Counts per rule, per DEM class, plus the moved pins (#1358: a CIFP pin
more than ``cifp_threshold_join_m`` from the apt.dat threshold) and the
shifted runways.

THE apt.dat-ONLY RUNWAYS (owner RULINGS 2026-10-26e lidar, 2026-10-28m any
DEM class, 2026-10-28o lidar and fine only; #1394, #1348): a runway with
no CIFP end follows a lidar or fine DEM where its datum line stands off it
by more than the class's ``runway_ends.dem_noise_m``; coarse keeps it.
The census ESTIMATES the datum line off the DEM end reads
(``constraints/runway_profile._datum_line`` needs the planar ridge
trends): the higher end at the field elevation less the fall from the
airport's highest DEM end, tilted with the DEM — so a runway yields where
``|field - highest DEM end| > noise``.  Counted per class; only ``lidar``
and ``fine`` rows yield (28o).  ``--all-apt`` judges every airport of the
apt.dat (with or without CIFP) the corpus holds a DEM tile for.
``--json OUT`` writes every flagged runway.  Read-only:
writes nothing but ``--json``.

    venv/bin/python tools/runway_end_census.py [--cifp DIR] [--apt PATH]
        [--elevation-root DIR] [--mod-cache DIR] [--icao ICAO ...]
        [--limit N] [--json OUT] [--all-apt]
"""
from __future__ import annotations

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py`` (twin: ``tests/test_console_encoding.py``).
import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse  # noqa: E402
import collections  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

from auto_patch_v2.airport import apt_dat as A  # noqa: E402
from auto_patch_v2.airport import cifp as C  # noqa: E402
from auto_patch_v2.airport import dem as D  # noqa: E402
from auto_patch_v2.airport import end_pins as EP  # noqa: E402
from auto_patch_v2.airport import runway_refs as REFS  # noqa: E402
from auto_patch_v2.airport.load import _vector_to_xy, join_cifp  # noqa: E402
from auto_patch_v2.law import load_default  # noqa: E402
from auto_patch_v2.law.tables import flat_source_class  # noqa: E402
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack  # noqa: E402
from auto_patch_v2.model.frame import Frame  # noqa: E402

XP = "/Users/noah/X-Plane 12"
DEFAULT_APT = os.path.join(XP, "Global Scenery", "Global Airports", "Earth nav data", "apt.dat")
DEFAULT_CIFP = os.path.join(XP, "Custom Data", "CIFP")
DEFAULT_ELEV = os.path.join(HERE, "..", "Elevation_data")


def _klass(law, js: str | None, have_inset: bool) -> str:
    """The DEM class: the inset's own pixel, else the base tier (coarse)."""
    if have_inset and js:
        try:
            with open(js, encoding="utf-8") as fh:
                meta = json.load(fh)
            px = meta.get("native_resolution_m") or meta.get("resolution_m")
            k = flat_source_class(law, float(px)) if px else None
            if k:
                return k
        except (OSError, ValueError, TypeError):
            pass
    return "coarse"


def _airport(icao, apt, cifp, law, elev_root, tiles):
    """``(Airport, dem class, shifted lines)`` built the loader's way, or
    ``None`` when no runway or no DEM tile."""
    if not apt.runways:
        return None
    lat0, lon0 = apt.reference_point()
    frame = Frame(icao, origin=(lat0, lon0), identity_dp=11)
    to_xy = _vector_to_xy(frame)
    tol = float(law.tables.emit.identity.cifp_threshold_join_m)
    recs, _missing, _joins = join_cifp(icao, apt.runways, cifp, to_xy, tol)
    shifted, shift_lines = EP.shifted_ends(icao, apt.runways, cifp, recs, to_xy, tol)
    runways = []
    for i, rw in enumerate(apt.runways):
        ends = []
        for k, (desig, lat, lon, disp, over) in enumerate(rw.ends):
            rec = recs[(i, k)]
            other = rw.ends[1 - k]
            if (i, k) in shifted:
                z, far = shifted[(i, k)]
                ends.append(RunwayEnd(desig, to_xy(lon, lat), (lat, lon), disp, over, z,
                                      far.source, pin_source=EP.SHIFTED))
                continue
            along = (EP.cifp_station(to_xy(lon, lat), to_xy(other[2], other[1]),
                                     to_xy(rec.lon, rec.lat)) if rec else None)
            ends.append(RunwayEnd(desig, to_xy(lon, lat), (lat, lon), disp, over,
                                  rec.elevation_m if rec else None, rec.source if rec else "",
                                  pin_along_m=along, pin_source="cifp" if rec else ""))
        r = Runway(f"{ends[0].name}/{ends[1].name}", rw.width_m, rw.surface,
                   (ends[0], ends[1]), None, "C")
        if r.length_m > 0.0:
            runways.append(r)
    try:
        hgt, tif, js = D.resolve_dem_files(elev_root, lat0, lon0, icao)
        if not os.path.isfile(hgt):
            return None
        dem = D.load_dem(frame, elev_root, icao)
    except (OSError, ValueError):
        return None
    dem._tiles = tiles                       # one base-tile cache for the run
    klass = _klass(law, js, tif is not None)
    pack = SceneryPack("Global Airports", "apt.dat", "0", (), ())
    ap = Airport(icao, apt.name, frame, apt.elevation_ft * 0.3048, tuple(runways), (), (), {},
                 (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    return ap, klass, shift_lines


def _apt_only(icao, airport, klass, rows, law, by_class, out) -> None:
    """THE apt.dat-ONLY RUNWAYS of one airport (module docstring): one
    ``out`` row per runway with no CIFP end and both ends read."""
    dems = [e["dem_m"] for ends in rows.values() for e in ends if e["dem_m"] is not None]
    if not dems:
        return
    off = float(airport.elevation_m) - max(dems)
    noise = float(law.tables.runway_ends.dem_noise_m.of(klass))
    for rid, ends in rows.items():
        if any(e["cifp_m"] is not None for e in ends) or any(e["dem_m"] is None for e in ends):
            continue
        yields = klass in ("lidar", "fine") and abs(off) > noise
        by_class[klass]["apt_only_runways"] += 1
        by_class[klass]["apt_only_yield"] += int(yields)
        out.append({"icao": icao, "runway": rid, "class": klass, "field_m":
                    round(float(airport.elevation_m), 2), "datum_off_m": round(off, 2),
                    "dem_m": [e["dem_m"] for e in ends], "yields": yields})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cifp", default=DEFAULT_CIFP)
    ap.add_argument("--apt", default=DEFAULT_APT)
    ap.add_argument("--elevation-root", default=DEFAULT_ELEV)
    ap.add_argument("--mod-cache", default="", help="read the cross-check cache here (rule (c))")
    ap.add_argument("--icao", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", default="")
    ap.add_argument("--all-apt", action="store_true",
                    help="every apt.dat airport, not only the CIFP ones")
    a = ap.parse_args(argv)
    law = load_default()
    order = law.tables.runway_ends.crosscheck_order
    files = C.discover_cifp_airports(a.cifp)
    icaos = sorted(a.icao or (A._block_index(a.apt) or {} if a.all_apt else files))
    if a.limit:
        icaos = icaos[: a.limit]
    t0 = time.time()
    n = collections.Counter()
    by_rule = collections.Counter()
    by_class = collections.defaultdict(collections.Counter)
    flagged, shifted_all, moved_all, judged, apt_only = [], [], [], [], []
    tiles: dict = {}
    last_tile = None
    for icao in icaos:
        path = files.get(icao)
        if not path and not a.all_apt:
            continue
        n["cifp_airports" if path else "apt_only_airports"] += 1
        cifp = C.read_cifp_runways(path) if path else {}
        block = A.read_airport_block(a.apt, icao)
        if not block or (path and not cifp):
            n["no_apt_dat_block"] += 1
            continue
        apt = A.parse_airport_block(block)
        if not apt.runways:
            n["no_runway"] += 1
            continue
        n["joined_airports"] += 1
        lat0, lon0 = apt.reference_point()
        tile = (math.floor(lat0), math.floor(lon0))
        if tile != last_tile:
            tiles.clear()
            last_tile = tile
        built = _airport(icao, apt, cifp, law, a.elevation_root, tiles)
        if built is None:
            n["no_dem"] += 1
            continue
        airport, klass, shift_lines = built
        refs = REFS.lookup(icao, a.mod_cache, order) if a.mod_cache else ()
        _ap, recs, _lines = EP.verify(airport, law, refs, klass=klass)
        n["dem_airports"] += 1
        by_class[klass]["airports"] += 1
        shifted_all += shift_lines
        tol = float(law.tables.emit.identity.cifp_threshold_join_m)
        rows = collections.defaultdict(list)
        for r in recs:
            rows[r["runway"]].append(r)
        _apt_only(icao, airport, klass, rows, law, by_class, apt_only)
        for rid, ends in rows.items():
            cifp_n = sum(1 for e in ends if e["cifp_m"] is not None)
            if not cifp_n:
                continue
            n["runways_with_cifp"] += 1
            by_class[klass]["runways"] += 1
            if cifp_n == 2:
                n["runways_two_cifp"] += 1
                c0, c1 = (e["cifp_m"] for e in ends)
                d0, d1 = (e["dem_m"] for e in ends)
                if d0 is not None and d1 is not None:
                    judged.append([icao, rid, klass, round(c1 - c0, 3), round(d1 - d0, 3),
                                   round(airport.elevation_m, 2), c0, c1])
                f = airport.elevation_m
                if abs(c1 - c0) <= 1 * 0.3048 + 1e-6 and all(
                        abs(c - f) <= 3 * 0.3048 + 1e-6 for c in (c0, c1)):
                    n["placeholder_pattern_no_dem"] += 1
            fl = sorted({x for e in ends for x in e["flags"]})
            for e in ends:
                if e["cifp_m"] is not None and abs(e["pin_moved_m"]) > tol:
                    moved_all.append({"icao": icao, "runway": rid, "end": e["end"],
                                      "pin_along_m": e["pin_along_m"],
                                      "moved_m": e["pin_moved_m"]})
            if not fl:
                continue
            n["runways_flagged"] += 1
            by_class[klass]["flagged"] += 1
            for x in fl:
                by_rule[x] += 1
                by_class[klass][x] += 1
            flagged.append({"icao": icao, "runway": rid, "class": klass, "flags": fl,
                            "field_m": round(airport.elevation_m, 2),
                            "cifp_m": [e["cifp_m"] for e in ends],
                            "dem_m": [e["dem_m"] for e in ends],
                            "source": [e["source"] for e in ends]})
        if (n["cifp_airports"] + n["apt_only_airports"]) % 1000 == 0:
            print(f"  ... {n['cifp_airports']} airports, {time.time() - t0:.0f} s", flush=True)
    print(f"RUNWAY-END PIN CENSUS over {n['cifp_airports']} CIFP airports "
          f"(+{n['apt_only_airports']} apt.dat-only) "
          f"({time.time() - t0:.0f} s)")
    for k, v in n.items():
        print(f"  {k}: {v}")
    print(f"  flagged by rule: {dict(by_rule)}")
    for k, c in sorted(by_class.items()):
        print(f"  class {k}: {dict(c)}")
    print(f"  pins moved > tolerance (#1358): {len(moved_all)} ends; shifted runways: "
          f"{len(shifted_all)}")
    yields = collections.Counter(r["class"] for r in apt_only if r["yields"])
    print(f"  apt.dat-only runways judged: {len(apt_only)}; yield to the DEM (estimate): "
          f"{dict(yields)} — lidar is 26e's, the rest 28m's")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"counts": dict(n), "by_rule": dict(by_rule),
                       "by_class": {k: dict(v) for k, v in by_class.items()},
                       "flagged": flagged, "moved": moved_all, "shifted": shifted_all,
                       "judged": judged, "apt_only": apt_only},
                      fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
