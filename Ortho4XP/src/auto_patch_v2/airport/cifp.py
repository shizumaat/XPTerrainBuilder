"""CIFP runway thresholds (ARINC 424 ``RWY:`` records) — the ABSOLUTE
runway-end pins (RULINGS :511-516; CIFP thresholds absolute).

Record grammar (v1 ``cifp_reader.parse_cifp_file`` is the reference)::

    RWY:RW14R,+0432,      ,02277, ,    , ,   ;N60431814,W135043590,0000;

Before the first ``;`` (comma fields): designator, magnetic bearing,
reserved, threshold elevation FEET, reserved, ILS ident, ILS category.
After it: latitude ``N60431814`` (DDMMSSss), longitude ``W135043590``
(DDDMMSSss), displaced-threshold distance in feet.
"""
from __future__ import annotations

import dataclasses as _dc
import re

FT_TO_M = 0.3048

__all__ = ["CifpRunway", "read_cifp_runways", "parse_lat", "parse_lon",
           "match_designator"]


@_dc.dataclass(frozen=True)
class CifpRunway:
    """One threshold record.  ``designator`` is the bare runway id
    (``14R``), i.e. the ``RW`` prefix stripped and blanks trimmed."""

    designator: str
    lat: float
    lon: float
    elevation_m: float
    displaced_m: float
    source: str


def parse_lat(s: str) -> float:
    """``N60431814`` -> 60.7217 (DD MM SS.ss)."""
    hem, deg, mins, secs = s[0], int(s[1:3]), int(s[3:5]), int(s[5:9]) / 100
    v = deg + mins / 60 + secs / 3600
    return -v if hem in "Ss" else v


def parse_lon(s: str) -> float:
    """``W135043590`` -> -135.0766 (DDD MM SS.ss)."""
    hem, deg, mins, secs = s[0], int(s[1:4]), int(s[4:6]), int(s[6:10]) / 100
    v = deg + mins / 60 + secs / 3600
    return -v if hem in "Ww" else v


def read_cifp_runways(path: str) -> dict[str, CifpRunway]:
    """Every ``RWY:`` record of one airport's CIFP file, keyed by bare
    designator.  A record without a numeric elevation or a parsable
    coordinate is skipped (the end then has no pin — never an invented
    one, plan §2)."""
    out: dict[str, CifpRunway] = {}
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line.startswith("RWY:"):
                continue
            parts = line[4:].split(";")
            if len(parts) < 2:
                continue
            fields = parts[0].split(",")
            coords = parts[1].split(",")
            if len(fields) < 4 or len(coords) < 3:
                continue
            desig = fields[0].strip()
            if not desig.startswith("RW"):
                continue
            elev = fields[3].strip()
            lat_s, lon_s = coords[0].strip(), coords[1].strip()
            if not elev.lstrip("-").isdigit() or len(lat_s) < 9 or len(lon_s) < 10:
                continue
            try:
                lat, lon = parse_lat(lat_s), parse_lon(lon_s)
            except (ValueError, IndexError):
                continue
            disp = coords[2].strip().rstrip(";")
            key = desig[2:].strip()
            out[key] = CifpRunway(
                key, lat, lon, int(elev) * FT_TO_M,
                int(disp) * FT_TO_M if disp.isdigit() else 0.0, path)
    return out


def match_designator(apt_desig: str, cifp: dict[str, CifpRunway]
                     ) -> CifpRunway | None:
    """Join an apt.dat end designator to its CIFP record: exact, then
    zero-padded (``02`` vs ``2``), then the bare number."""
    d = apt_desig.strip().upper()
    m = re.match(r"^(\d+)([A-Z]*)$", d)
    cands = [d]
    if m:
        cands.append(m.group(1).zfill(2) + m.group(2))
        cands.append(m.group(1).lstrip("0") + m.group(2))
    for cand in cands:
        if cand in cifp:
            return cifp[cand]
    return None
