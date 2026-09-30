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
           "match_designator", "match_threshold"]


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


def match_threshold(xy: tuple[float, float],
                    cifp_xy: dict[str, tuple[float, float]], tol_m: float,
                    ) -> tuple[str | None, str, float]:
    """THE COORDINATE FALLBACK (issue #119) for an end whose designator
    matched nothing: ``(designator, verdict, distance)`` of the ONE CIFP
    record whose landing threshold (``cifp_xy``, in the caller's metric
    frame, already stripped of records other ends joined by name) lies
    within ``tol_m`` of ``xy`` — the apt.dat end advanced by its displaced
    distance.  ``verdict`` is ``joined``, ``ambiguous`` (two or more within
    the radius: refused, never a guess) or ``none`` (the nearest is
    farther); the designator is ``None`` unless joined, and the distance is
    the nearest record's (``inf`` with no record)."""
    by = sorted((((xy[0] - x) ** 2 + (xy[1] - y) ** 2) ** 0.5, k)
                for k, (x, y) in cifp_xy.items())
    if not by:
        return None, "none", float("inf")
    d0, k0 = by[0]
    if d0 > tol_m:
        return None, "none", d0
    if len(by) > 1 and by[1][0] <= tol_m:
        return None, "ambiguous", d0
    return k0, "joined", d0
