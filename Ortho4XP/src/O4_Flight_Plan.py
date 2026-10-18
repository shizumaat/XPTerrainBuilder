"""Select tiles from a flight plan (issue #829).

The ONE rule behind "Select from flight plan…", shared by the Qt window
(in-process) and the macOS app (``Sources/SceneryKit/FlightPlan.swift``,
the Swift half), twinned on ``tests/fixtures/flight_plan_cases.json`` and
the plan files beside it in ``tests/fixtures/flight_plan/``.

Reading a plan (stdlib only):

* :func:`parse_fms` -- an X-Plane ``.fms`` (v3 and v11/1100): every line
  ``TYPE IDENT ... LAT LON`` whose type is a waypoint type is a fix.
* :func:`parse_lnmpln` -- a Little Navmap ``.lnmpln``:
  ``Flightplan/Waypoints/Waypoint/Pos @Lat @Lon``.
* :func:`parse_simbrief` -- SimBrief's fetcher answer
  (:func:`simbrief_url`): ``origin``, ``navlog/fix`` and ``destination``,
  each ``pos_lat`` / ``pos_long``.

Route -> tiles: :func:`route_tiles` densifies every leg along the GREAT
CIRCLE (a long leg bends poleward of the straight lat/lon line, and a
straight-line walk would skip the tiles it really crosses), then keeps
every 1x1 tile whose nearest point lies within the radius of a sample.
Samples are :data:`SAMPLE_STEP_KM` apart, so a tile is judged to within
half a step; the step is fixed, so a larger radius never drops a tile.
The departure and arrival tiles are always kept.  Longitudes wrap, so a
route over the antimeridian selects tiles on both sides of it;
:func:`route_drawing` splits the drawn line there.

No airport is named here (owner standing 2026-10-05).
"""

import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, NamedTuple, Optional, Sequence, Tuple

__all__ = [
    "FlightPlan", "FlightPlanError", "Waypoint", "parse_fms", "parse_lnmpln",
    "parse_simbrief", "parse_plan_text", "read_plan_file", "simbrief_url",
    "fetch_simbrief", "route_tiles", "route_drawing", "radius_km",
    "summary_text", "tiles_text", "densify", "route_length_km",
]

Tile = Tuple[int, int]

#: Mean earth radius (IUGG), the value ``O4_Airport_Rank`` uses.
EARTH_RADIUS_KM = 6371.0088
KM_PER_NM = 1.852
#: Spacing of the samples along the route (see the module docstring).
SAMPLE_STEP_KM = 5.0
#: The radius control's range and default, per unit (km is the app's
#: unit everywhere else; nm is the pilot's).
RADIUS_MAX = {"km": 300, "nm": 160}
RADIUS_DEFAULT = {"km": 50, "nm": 25}
UNITS = ("km", "nm")

# --- copy (verbatim; identical to the Swift half, twinned) ---------------
MENU_TITLE = "Select from flight plan…"
OPEN_BUTTON = "Open plan file…"
SIMBRIEF_PLACEHOLDER = "SimBrief username or pilot ID"
SIMBRIEF_BUTTON = "Fetch latest SimBrief plan"
SIMBRIEF_NOTE = "Downloads your latest plan from simbrief.com (needs internet)."
RADIUS_LABEL = "Tiles within"
OF_ROUTE_LABEL = "of the route"
FILE_TYPES = ("fms", "lnmpln")

SIMBRIEF_ENDPOINT = "https://www.simbrief.com/api/xml.fetcher.php"

# X-Plane .fms waypoint type codes: airport, NDB, VOR, fix, DME, lat/lon.
_FMS_TYPES = frozenset({1, 2, 3, 11, 12, 13, 28})


class FlightPlanError(ValueError):
    """A plan that cannot be read; the message is for the user."""


class Waypoint(NamedTuple):
    ident: str
    lat: float
    lon: float


class FlightPlan(NamedTuple):
    waypoints: List[Waypoint]
    #: Where the plan came from, for the summary: "file.fms", "SimBrief".
    source: str = ""

    @property
    def origin(self) -> str:
        return self.waypoints[0].ident

    @property
    def destination(self) -> str:
        return self.waypoints[-1].ident

    def points(self) -> List[Tuple[float, float]]:
        return [(w.lat, w.lon) for w in self.waypoints]


# ===========================================================================
# Reading plans
# ===========================================================================
def _plausible(lat: float, lon: float) -> bool:
    return (math.isfinite(lat) and math.isfinite(lon)
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0)


def _plan(waypoints: List[Waypoint], source: str, kind: str) -> FlightPlan:
    """Drop repeated consecutive positions; a route needs two points."""
    kept: List[Waypoint] = []
    for w in waypoints:
        if kept and (kept[-1].lat, kept[-1].lon) == (w.lat, w.lon):
            continue
        kept.append(w)
    if not kept:
        raise FlightPlanError("No waypoints found in this %s." % kind)
    if len(kept) == 1:
        kept.append(kept[0])
    return FlightPlan(kept, source)


def parse_fms(text: str, source: str = "") -> FlightPlan:
    """An X-Plane ``.fms`` (v3 or v11): its waypoint lines in order."""
    waypoints: List[Waypoint] = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) < 5:
            continue
        try:
            kind = int(tokens[0])
            lat, lon = float(tokens[-2]), float(tokens[-1])
        except ValueError:
            continue
        if kind in _FMS_TYPES and _plausible(lat, lon):
            waypoints.append(Waypoint(tokens[1], lat, lon))
    return _plan(waypoints, source, "X-Plane flight plan")


def _xml_root(text: str, kind: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        raise FlightPlanError("This %s is not valid XML." % kind) from None


def parse_lnmpln(text: str, source: str = "") -> FlightPlan:
    """A Little Navmap ``.lnmpln``: ``Flightplan/Waypoints/Waypoint``."""
    root = _xml_root(text, "Little Navmap plan")
    waypoints: List[Waypoint] = []
    for wp in root.findall("./Flightplan/Waypoints/Waypoint"):
        pos = wp.find("Pos")
        if pos is None:
            continue
        try:
            lat, lon = float(pos.get("Lat", "")), float(pos.get("Lon", ""))
        except ValueError:
            continue
        if _plausible(lat, lon):
            ident = (wp.findtext("Ident") or wp.findtext("Name") or "").strip()
            waypoints.append(Waypoint(ident, lat, lon))
    return _plan(waypoints, source, "Little Navmap plan")


def _simbrief_point(node: Optional[ET.Element]) -> Optional[Waypoint]:
    if node is None:
        return None
    try:
        lat = float(node.findtext("pos_lat") or "")
        lon = float(node.findtext("pos_long") or "")
    except ValueError:
        return None
    if not _plausible(lat, lon):
        return None
    ident = (node.findtext("icao_code") or node.findtext("ident") or "").strip()
    return Waypoint(ident, lat, lon)


def parse_simbrief(text: str, source: str = "SimBrief") -> FlightPlan:
    """SimBrief's fetcher XML: origin, the navlog fixes, destination.

    A fetch SimBrief refused (unknown user, no plan) carries its reason
    in ``fetch/status``; that reason is the error message."""
    root = _xml_root(text, "SimBrief answer")
    status = (root.findtext("./fetch/status") or "").strip()
    if status and status.lower() != "success":
        reason = re.sub(r"^error:\s*", "", status, flags=re.IGNORECASE)
        raise FlightPlanError("SimBrief: %s" % reason)
    points = [_simbrief_point(root.find("origin"))]
    points += [_simbrief_point(fix) for fix in root.findall("./navlog/fix")]
    points.append(_simbrief_point(root.find("destination")))
    return _plan([p for p in points if p is not None], source, "SimBrief plan")


def parse_plan_text(text: str, name: str = "") -> FlightPlan:
    """Any of the three, chosen by the file extension, else by content."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "lnmpln":
        return parse_lnmpln(text, name)
    if ext == "fms":
        return parse_fms(text, name)
    head = text.lstrip()[:4096]
    if head.startswith("<"):
        if "<LittleNavmap" in head:
            return parse_lnmpln(text, name)
        if "<OFP" in head:
            return parse_simbrief(text, name or "SimBrief")
    return parse_fms(text, name)


def read_plan_file(path: str) -> FlightPlan:
    """Read ``path`` (UTF-8; an unreadable byte is replaced) and parse it."""
    try:
        with open(path, encoding="utf-8", errors="replace", newline=None) as fh:
            text = fh.read()
    except OSError as exc:
        raise FlightPlanError("Could not read %s (%s)." % (path, exc.strerror))
    return parse_plan_text(text, path.replace("\\", "/").rsplit("/", 1)[-1])


def simbrief_url(user: str) -> str:
    """The fetcher URL for a SimBrief pilot ID (digits) or username."""
    user = user.strip()
    if not user:
        raise FlightPlanError("Enter your SimBrief username or pilot ID.")
    key = "userid" if re.fullmatch(r"\d+", user) else "username"
    # Percent-encoding with only A-Z a-z 0-9 - . _ ~ left bare (the Swift
    # half encodes the same set).
    return "%s?%s=%s" % (SIMBRIEF_ENDPOINT, key, urllib.parse.quote(user, safe=""))


def fetch_simbrief(user: str, timeout: float = 20.0) -> FlightPlan:
    """Download and parse the user's latest SimBrief plan (network)."""
    import urllib.error
    import urllib.request

    url = simbrief_url(user)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
    except urllib.error.HTTPError as exc:
        # SimBrief answers an unknown user with an error status AND an
        # XML body that names the reason.
        body = exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise FlightPlanError("Could not reach simbrief.com (%s)." % (
            getattr(exc, "reason", None) or exc))
    return parse_simbrief(body.decode("utf-8", errors="replace"))


# ===========================================================================
# Route -> tiles
# ===========================================================================
def _vec(lat: float, lon: float) -> Tuple[float, float, float]:
    p, l = math.radians(lat), math.radians(lon)
    return (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))


def _norm_lon(lon: float) -> float:
    """``lon`` in [-180, 180); an in-range value is returned unchanged."""
    if -180.0 <= lon < 180.0:
        return lon
    lon = math.fmod(lon + 180.0, 360.0)
    if lon < 0:
        lon += 360.0
    return lon - 180.0


def _latlon(v: Sequence[float]) -> Tuple[float, float]:
    x, y, z = v
    lat = math.degrees(math.atan2(z, math.hypot(x, y)))
    lon = _norm_lon(math.degrees(math.atan2(y, x)))
    return lat, lon


def _central_angle(a, b) -> float:
    """Angle between unit vectors, radians (atan2 form: exact when small)."""
    cx = a[1] * b[2] - a[2] * b[1]
    cy = a[2] * b[0] - a[0] * b[2]
    cz = a[0] * b[1] - a[1] * b[0]
    dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    return math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), dot)


def densify(points: Sequence[Tuple[float, float]],
            step_km: float = SAMPLE_STEP_KM) -> List[Tuple[float, float]]:
    """``points`` (lat, lon) with great-circle samples at most ``step_km``
    apart along every leg; the waypoints themselves are kept."""
    out: List[Tuple[float, float]] = []
    for i, (lat, lon) in enumerate(points):
        if i == 0:
            out.append((lat, _norm_lon(lon)))
            continue
        a, b = _vec(*points[i - 1]), _vec(lat, lon)
        omega = _central_angle(a, b)
        n = max(1, math.ceil(omega * EARTH_RADIUS_KM / step_km))
        sin_omega = math.sin(omega)
        for k in range(1, n):
            t = k / n
            if sin_omega < 1e-12:
                wa, wb = 1.0 - t, t
            else:
                wa = math.sin((1.0 - t) * omega) / sin_omega
                wb = math.sin(t * omega) / sin_omega
            out.append(_latlon(tuple(wa * a[j] + wb * b[j] for j in range(3))))
        out.append((lat, _norm_lon(lon)))
    return out


def _tile_distance_km(lat: float, lon: float, tlat: int, tlon: int) -> float:
    """Great-circle distance from (lat, lon) to the nearest point of tile
    ``(tlat, tlon)`` (its 1x1 lat/lon rectangle), km."""
    east = (lon - tlon) % 360.0          # degrees east of the west edge
    if east <= 1.0:                      # within the tile's longitudes
        nearest = min(max(lat, tlat), tlat + 1)
        return EARTH_RADIUS_KM * math.radians(abs(lat - nearest))
    dl = math.radians(min(east - 1.0, 360.0 - east))
    p = math.radians(lat)
    sp, cp, cdl = math.sin(p), math.cos(p), math.cos(dl)
    lo, hi = math.radians(tlat), math.radians(tlat + 1)
    candidates = [lo, hi]
    star = math.atan2(sp, cp * cdl)       # the closest latitude on the meridian
    if lo < star < hi:
        candidates.append(star)
    best = max(sp * math.sin(q) + cp * math.cos(q) * cdl for q in candidates)
    return EARTH_RADIUS_KM * math.acos(max(-1.0, min(1.0, best)))


def _candidate_tiles(lat: float, lon: float, radius: float):
    dlat = math.degrees(radius / EARTH_RADIUS_KM) + 1e-9
    lat_lo = max(-90, math.floor(lat - dlat))
    lat_hi = min(89, math.floor(lat + dlat))
    reach = min(90.0, abs(lat) + dlat)
    if reach >= 89.0:
        lons = range(-180, 180)
    else:
        dlon = dlat / math.cos(math.radians(reach))
        lon_lo, lon_hi = math.floor(lon - dlon), math.floor(lon + dlon)
        if lon_hi - lon_lo >= 359:
            lons = range(-180, 180)
        else:
            lons = [((x + 180) % 360) - 180 for x in range(lon_lo, lon_hi + 1)]
    for tlat in range(lat_lo, lat_hi + 1):
        for tlon in lons:
            yield (tlat, tlon)


def _tile_of(lat: float, lon: float) -> Tile:
    return (min(89, math.floor(lat)), ((math.floor(lon) + 180) % 360) - 180)


def route_tiles(points: Sequence[Tuple[float, float]],
                radius_km_: float) -> List[Tile]:
    """Every tile within ``radius_km_`` of the route through ``points``
    (lat, lon), plus the departure and arrival tiles; sorted."""
    if not points:
        return []
    radius = max(0.0, float(radius_km_))
    chosen = {_tile_of(*points[0]), _tile_of(*points[-1])}
    for lat, lon in densify(points):
        chosen.add(_tile_of(lat, lon))
        for tile in _candidate_tiles(lat, lon, radius):
            if tile not in chosen and _tile_distance_km(lat, lon, *tile) <= radius:
                chosen.add(tile)
    return sorted(chosen)


def route_drawing(points: Sequence[Tuple[float, float]]
                  ) -> List[List[Tuple[float, float]]]:
    """The densified route as polylines (lat, lon) for a flat map: split
    where it crosses the antimeridian, each piece ending on +-180."""
    dense = densify(points)
    parts: List[List[Tuple[float, float]]] = [[dense[0]]] if dense else []
    for (lat0, lon0), (lat1, lon1) in zip(dense, dense[1:]):
        if abs(lon1 - lon0) > 180.0:
            edge = 180.0 if lon0 > 0 else -180.0
            unwrapped = lon1 + (360.0 if lon0 > 0 else -360.0)
            t = (edge - lon0) / (unwrapped - lon0)
            lat_x = lat0 + t * (lat1 - lat0)
            parts[-1].append((lat_x, edge))
            parts.append([(lat_x, -edge)])
        parts[-1].append((lat1, lon1))
    return parts


# ===========================================================================
# Units and words
# ===========================================================================
def radius_km(value: float, unit: str) -> float:
    """The radius control's value in km (``unit`` "km" or "nm")."""
    return float(value) * (KM_PER_NM if unit == "nm" else 1.0)


def route_length_km(points: Sequence[Tuple[float, float]]) -> float:
    vecs = [_vec(lat, lon) for lat, lon in points]
    return EARTH_RADIUS_KM * sum(_central_angle(a, b) for a, b in zip(vecs, vecs[1:]))


def summary_text(plan: FlightPlan, unit: str) -> str:
    """"ORIG → DEST · 4 waypoints · 233 km"."""
    length = route_length_km(plan.points())
    if unit == "nm":
        length /= KM_PER_NM
    return "%s → %s · %d waypoints · %s %s" % (
        plan.origin or "?", plan.destination or "?", len(plan.waypoints),
        format(round(length), ","), unit)


def tiles_text(count: int) -> str:
    """"12 tiles selected"."""
    return "%s tile%s selected" % (format(count, ","), "" if count == 1 else "s")
