"""CIFP runway thresholds (ARINC 424 ``RWY:`` records) — the ABSOLUTE
runway-end pins (RULINGS :511-516; CIFP thresholds absolute).

Record grammar::

    RWY:RW14R,+0432,      ,02277, ,    , ,   ;N60431814,W135043590,0000;

Before the first ``;`` (comma fields): designator, magnetic bearing,
reserved, threshold elevation FEET, reserved, ILS ident, ILS category.
After it: latitude ``N60431814`` (DDMMSSss), longitude ``W135043590``
(DDDMMSSss), displaced-threshold distance in feet.

Tile selection, the flat-site S1 consensus and DEM prep read this file too
(owner 2026-10-18, #911 Q1: they read below-sea-level thresholds, as the
airport load does): :func:`read_threshold_dicts` is their shape, and the
install-layout helpers below (:func:`xplane_root_from_cifp_path`,
:func:`discover_cifp_airports`, :func:`airport_in_tile`) came here with the
retired v1 ``auto_patch.cifp_reader``.
"""
from __future__ import annotations

import dataclasses as _dc
import logging
import os
import re

from ..law.reference_code import NPA, stronger_class

FT_TO_M = 0.3048

__all__ = ["CifpRunway", "read_cifp_runways", "read_cifp_approach_runways",
           "parse_lat", "parse_lon", "match_designator", "match_threshold",
           "read_threshold_dicts", "xplane_root_from_cifp_path",
           "discover_cifp_airports", "airport_in_tile"]

_log = logging.getLogger(__name__)


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
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
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


def read_threshold_dicts(path: str) -> dict[str, dict]:
    """:func:`read_cifp_runways` in the shape tile selection and the
    object-anchor worklist consume: ``{"RW16L": {lat, lon, elevation_m,
    displaced_m}}`` (``build_support.pair_runways`` pairs ``RW`` keys).

    An UNREADABLE file is no runways (``{}``, one log line), never an
    exception: a CIFP file that vanished or cannot be decoded skips that
    airport and must not fail the tile's whole selection."""
    try:
        runways = read_cifp_runways(path)
    except (OSError, ValueError) as exc:
        _log.warning("could not read CIFP file %s: %s", path, exc)
        return {}
    return {"RW" + key: {"lat": r.lat, "lon": r.lon,
                         "elevation_m": r.elevation_m,
                         "displaced_m": r.displaced_m}
            for key, r in runways.items()}


def xplane_root_from_cifp_path(cifp_path: str) -> str | None:
    """The X-Plane install root two levels above a CIFP directory
    (``<X-Plane>/Custom Data/CIFP``), or ``None`` when the derived root
    holds neither ``Custom Scenery`` nor ``Resources``."""
    if not cifp_path:
        return None
    try:
        root = os.path.dirname(os.path.dirname(os.path.normpath(cifp_path)))
        if (os.path.isdir(os.path.join(root, "Custom Scenery"))
                or os.path.isdir(os.path.join(root, "Resources"))):
            return root
    except OSError:
        pass
    return None


def discover_cifp_airports(cifp_path: str) -> dict[str, str]:
    """``{ICAO: file path}`` for every ``.dat`` file of a CIFP directory
    whose stem is a 2-4 character alphanumeric code (``-`` allowed)."""
    airports: dict[str, str] = {}
    if not cifp_path or not os.path.isdir(cifp_path):
        return airports
    for fname in os.listdir(cifp_path):
        if fname.lower().endswith(".dat"):
            icao = fname[:-4].upper()
            if 2 <= len(icao) <= 4 and icao.replace("-", "").isalnum():
                airports[icao] = os.path.join(cifp_path, fname)
    return airports


def airport_in_tile(runways: dict, tile_lat: int, tile_lon: int) -> bool:
    """Whether any threshold of ``runways`` (:func:`read_threshold_dicts`
    shape) lies in the 1x1 degree tile whose SW corner is
    ``(tile_lat, tile_lon)``; the tile is half-open on its N and E edges."""
    return any(tile_lat <= d["lat"] < tile_lat + 1
               and tile_lon <= d["lon"] < tile_lon + 1
               for d in runways.values())


#: an ``APPCH:`` procedure identifier naming its runway: one type letter
#: (``I`` ILS, ``R`` RNAV, ``L`` LOC, ``N`` NDB, ``V`` VOR, ``D`` VOR/DME …),
#: the runway number and side, then an optional multiple-approach suffix
#: (``I32LY``, ``R14L``, ``N25``).  A circling procedure (``VOR-A``) names
#: no runway and witnesses none.
_APPROACH_RUNWAY = re.compile(r"^([A-Z])(\d{2}[LRC]?)(?:[A-Z-]?|-[A-Z])$")
#: THE ARINC 424 ROUTE TYPE (the ident's first letter) -> approach class
#: (regulation-conformance spec §3.4; owner RULINGS 2026-10-15m (2)):
#: ILS (I), GLS (J), MLS (M / W / Y) are PRECISION; RNAV (R) and RNP (H)
#: carry vertical guidance (APV); every other procedure is non-precision.
_ROUTE_TYPE_CLASS = {"I": "pa", "J": "pa", "M": "pa", "W": "pa", "Y": "pa",
                     "R": "apv", "H": "apv"}


def read_cifp_approach_runways(path: str) -> dict[str, str]:
    """THE CIFP HALF OF THE APPROACH WITNESS (owner RULINGS 2026-10-15k
    (3), 15m (2)): ``{bare designator: approach class}`` (``RWY:`` keys of
    :func:`read_cifp_runways`) for every runway some ``APPCH:`` procedure
    of this airport's CIFP file is flown TO, the strongest class of its
    procedures (``pa`` > ``apv`` > ``npa``; ``law.reference_code``).  A
    runway absent from it has no procedure.  An unreadable file witnesses
    nothing (an empty mapping)."""
    out: dict[str, str] = {}
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return {}
    with fh:
        for raw in fh:
            if not raw.startswith("APPCH:"):
                continue
            fields = raw[6:].split(",")
            if len(fields) < 3:
                continue
            m = _APPROACH_RUNWAY.match(fields[2].strip())
            if m:
                cls = _ROUTE_TYPE_CLASS.get(m.group(1), NPA)
                out[m.group(2)] = stronger_class(out.get(m.group(2)), cls)
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
