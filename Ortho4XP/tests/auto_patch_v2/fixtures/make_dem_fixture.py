"""Regenerate the CYXY DEM fixtures DETERMINISTICALLY (M3a fixture repair).

M1's synthetic ``.hgt`` / inset GeoTIFF were written once and never
committed: ``Ortho4XP/.gitignore`` ignores every ``Elevation_data/``,
``OSM_data/`` and ``Airport_mod_cache/`` directory, and the fixture tree
reuses those names on purpose (the loaders resolve the shared-corpus
layout).  The negations now live in ``.gitignore``; this script is the
record of how the two rasters are made, and
``test_airport_load.py::test_dem_fixture_is_the_generator_output`` holds
the committed bytes to it.

    venv/bin/python tests/auto_patch_v2/fixtures/make_dem_fixture.py [--check]

The surface is one plane through CYXY's reference point (60.710278,
-135.067778) at 700 m, rising 2000 m per degree of latitude and 1000 m
per degree of longitude (≈ 1.8 % north, 1.8 % east at this latitude):
the base ``N60W136.hgt`` is that plane on a 61 × 61 grid rounded to
int16; the inset ``CYXY_fixture.tif`` is the same plane + 3 m on a
48 × 48 WGS84 grid (1/600° × 1/800°, PixelIsArea) whose north-west
corner is 0.03° north / 0.04° west of the reference point — so the
composite reads the inset (+3 m) in the core and the base beyond the
feather, which is what ``test_dem_composite_and_feather`` asserts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ELEV = HERE / "CYXY" / "Elevation_data" / "+60-140"
HGT = ELEV / "N60W136.hgt"
TIF = ELEV / "N60W136_airport_insets" / "CYXY_fixture.tif"
JSON = ELEV / "N60W136_airport_insets" / "CYXY_fixture.json"

LAT0, LON0, Z0 = 60.710278, -135.067778, 700.0
DZ_DLAT, DZ_DLON = 2000.0, 1000.0
N_HGT = 61
INSET_N = 48
INSET_LON_W, INSET_LAT_N = LON0 - 0.04, LAT0 + 0.03
INSET_DLON, INSET_DLAT = 1.0 / 600.0, 1.0 / 800.0
INSET_LIFT_M = 3.0


def plane(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    return Z0 + DZ_DLAT * (lat - LAT0) + DZ_DLON * (lon - LON0)


def hgt_bytes() -> bytes:
    rr, cc = np.mgrid[0:N_HGT, 0:N_HGT]
    lat = 61.0 - rr / (N_HGT - 1)
    lon = -136.0 + cc / (N_HGT - 1)
    return np.round(plane(lat, lon)).astype(">i2").tobytes()


def inset_array() -> np.ndarray:
    rr, cc = np.mgrid[0:INSET_N, 0:INSET_N]
    lat = INSET_LAT_N - (rr + 0.5) * INSET_DLAT
    lon = INSET_LON_W + (cc + 0.5) * INSET_DLON
    return (plane(lat, lon) + INSET_LIFT_M).astype(np.float32)


def inset_tags() -> list:
    """GeoTIFF tags: ModelPixelScale, ModelTiepoint, GeoKeyDirectory
    (GTModelType geographic, GTRasterType PixelIsArea, GCS WGS84)."""
    return [
        (33550, "d", 3, (INSET_DLON, INSET_DLAT, 0.0), True),
        (33922, "d", 6, (0.0, 0.0, 0.0, INSET_LON_W, INSET_LAT_N, 0.0), True),
        (34735, "H", 16, (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1,
                          2048, 0, 1, 4326), True),
    ]


def inset_json() -> str:
    return json.dumps({"provider": "FIXTURE",
                       "source_ids": ["synthetic-plane+3m"],
                       "vertical_datum": "n/a", "resolution_m": 100.0})


def write(root: Path = ELEV) -> None:
    import tifffile
    hgt = root / HGT.name
    tif = root / TIF.parent.name / TIF.name
    tif.parent.mkdir(parents=True, exist_ok=True)
    hgt.write_bytes(hgt_bytes())
    tifffile.imwrite(tif, inset_array(), extratags=inset_tags(),
                     photometric="minisblack")
    (tif.parent / JSON.name).write_text(inset_json())


def check() -> list[str]:
    """Names of the committed files that differ from the generator."""
    import tempfile
    bad = []
    with tempfile.TemporaryDirectory() as d:
        write(Path(d))
        for rel in (HGT.name, f"{TIF.parent.name}/{TIF.name}",
                    f"{JSON.parent.name}/{JSON.name}"):
            a, b = ELEV / rel, Path(d) / rel
            if not a.is_file() or a.read_bytes() != b.read_bytes():
                bad.append(rel)
    return bad


if __name__ == "__main__":
    if "--check" in sys.argv:
        bad = check()
        print("OK" if not bad else f"DIFFERS: {bad}")
        sys.exit(1 if bad else 0)
    write()
    print(f"wrote {HGT}, {TIF}, {JSON}")
