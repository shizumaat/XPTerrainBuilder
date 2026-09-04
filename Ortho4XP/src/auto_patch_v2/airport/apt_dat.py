"""apt.dat reader — the X-Plane 1100/1200 record grammar, rewritten from
the v1 reference (``apt_dat_reader.py`` rows 106-121 / 531-610; owner
decision 2026-09-03d #3: loaders are rewritten, v1 is reference only).

Records read (Appendix A §4):

* ``1``     airport header (elevation ft, ICAO, name); ``1302`` metadata
            (``datum_lat`` / ``datum_lon`` = the airport reference point);
* ``100``   runway (width, surface, two 9-token end blocks);
* ``102``   helipad (parsed and REPORTED, never graded — M0 §4 step 1);
* ``110``   pavement header + ``111``-``114`` node rows (beziers
            flattened, first contour = exterior, later contours = holes);
* ``120``   linear feature (painted line) + node rows, ``115``/``116``
            terminate an OPEN polyline, ``113``/``114`` close a ring;
* ``130``   boundary + node rows;
* ``1201``  taxi node; ``1202`` taxi edge; ``1206`` ground-vehicle edge;
* ``1300``  startup location.

Coordinates leave this module as ``(lon, lat)`` degrees; ``load.py``
projects them into the frame.  Bezier flattening follows the apt.dat
1100 spec conventions (a node's control point applies to the segment it
starts; the NEXT node's control point is mirrored through that node) and
the v1 tessellation bounds (sagitta 0.4 m, vertex spacing ≥ 0.5 m, a
corner-softening curve deviating < 1.5 m is a straight chord — user
2026-05-04; user 2026-07-05 minimum-node profile).  No environment reads.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import math
import os
import typing as _t

LonLat = tuple[float, float]

__all__ = [
    "AptRunway", "AptHelipad", "AptPavement", "AptLine", "AptBoundary",
    "AptTaxiNode", "AptTaxiEdge", "AptStartup", "AptAirport",
    "read_airport_block", "parse_airport_block", "find_apt_dat",
    "file_has_airport", "block_sha256",
]

# Row types (apt.dat 1100 / 1200).
ROW_AIRPORT = 1
ROW_RUNWAY = 100
ROW_HELIPAD = 102
ROW_PAVEMENT = 110
ROW_NODE = 111
ROW_NODE_BEZIER = 112
ROW_CLOSE = 113
ROW_CLOSE_BEZIER = 114
ROW_END = 115
ROW_END_BEZIER = 116
ROW_LINE = 120
ROW_BOUNDARY = 130
ROW_TAXI_NODE = 1201
ROW_TAXI_EDGE = 1202
ROW_TRUCK_EDGE = 1206
ROW_STARTUP = 1300
ROW_METADATA = 1302
_HEADER_ROWS = (1, 16, 17)
_NODE_ROWS = (ROW_NODE, ROW_NODE_BEZIER, ROW_CLOSE, ROW_CLOSE_BEZIER)

FT_TO_M = 0.3048

# Tessellation bounds (v1 CURVE_SAGITTA_MAX_M / CURVE_MIN_VERTEX_SPACING_M /
# BEZIER_FLATTEN_DEV_M, here as plain constants: no environment reads).
SAGITTA_MAX_M = 0.4
MIN_VERTEX_SPACING_M = 0.5
FLATTEN_DEVIATION_M = 1.5
_LAT_SCALE = 111320.0


@_dc.dataclass(frozen=True)
class AptRunway:
    """Row 100.  ``ends`` = two ``(designator, lat, lon, displaced_m,
    overrun_m)`` tuples; ``surface`` the raw apt.dat code."""

    width_m: float
    surface: int
    ends: tuple[tuple[str, float, float, float, float],
                tuple[str, float, float, float, float]]


@_dc.dataclass(frozen=True)
class AptHelipad:
    """Row 102: reported, not graded."""

    name: str
    lat: float
    lon: float
    heading_deg: float
    length_m: float
    width_m: float
    surface: int


@_dc.dataclass(frozen=True)
class AptPavement:
    """Row 110 + contours.  ``rings[0]`` is the exterior; each ring is
    an unclosed ``(lon, lat)`` list."""

    index: int
    surface: int
    smoothness: float
    orientation_deg: float
    description: str
    rings: tuple[tuple[LonLat, ...], ...]


@_dc.dataclass(frozen=True)
class AptLine:
    """Row 120 painted line: ``points`` unclosed; ``closed`` when the
    contour ended with 113/114; ``line_type`` the FIRST node's type."""

    index: int
    description: str
    line_type: int
    points: tuple[LonLat, ...]
    closed: bool


@_dc.dataclass(frozen=True)
class AptBoundary:
    """Row 130 + contours (exterior first)."""

    index: int
    description: str
    rings: tuple[tuple[LonLat, ...], ...]


@_dc.dataclass(frozen=True)
class AptTaxiNode:
    """Row 1201."""

    id: int
    lat: float
    lon: float
    usage: str
    label: str


@_dc.dataclass(frozen=True)
class AptTaxiEdge:
    """Rows 1202 (``kind`` = ``runway`` / ``taxiway_X``) and 1206
    (``kind`` = ``truck``)."""

    a: int
    b: int
    one_way: bool
    kind: str
    name: str


@_dc.dataclass(frozen=True)
class AptStartup:
    """Row 1300."""

    name: str
    lat: float
    lon: float
    heading_deg: float
    kind: str
    traffic: str


@_dc.dataclass(frozen=True)
class AptAirport:
    """One parsed airport block, in degrees."""

    icao: str
    name: str
    elevation_ft: float
    metadata: _t.Mapping[str, str]
    runways: tuple[AptRunway, ...]
    helipads: tuple[AptHelipad, ...]
    pavements: tuple[AptPavement, ...]
    lines: tuple[AptLine, ...]
    boundaries: tuple[AptBoundary, ...]
    taxi_nodes: _t.Mapping[int, AptTaxiNode]
    taxi_edges: tuple[AptTaxiEdge, ...]
    truck_edges: tuple[AptTaxiEdge, ...]
    startups: tuple[AptStartup, ...]

    def reference_point(self) -> tuple[float, float]:
        """``(lat, lon)`` of the airport reference point: the 1302
        ``datum_lat``/``datum_lon`` when authored, else the mean of the
        runway ends, else the first pavement vertex."""
        md = self.metadata
        if "datum_lat" in md and "datum_lon" in md:
            try:
                return (float(md["datum_lat"]), float(md["datum_lon"]))
            except ValueError:
                pass
        pts = [(e[1], e[2]) for r in self.runways for e in r.ends]
        if not pts:
            pts = [(p[1], p[0]) for pv in self.pavements for p in pv.rings[0]]
        if not pts:
            raise ValueError(f"{self.icao}: no reference point derivable")
        return (sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts))


# ── file access ──────────────────────────────────────────────────────────

def _is_header_for(toks: list[str], icao: str) -> bool:
    return (len(toks) >= 5 and toks[0] in ("1", "16", "17")
            and toks[4].upper() == icao)


def file_has_airport(path: str, icao: str) -> bool:
    """Whether ``path`` starts an airport block for ``icao``."""
    icao = icao.upper()
    try:
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                if line[:1] in "1" and _is_header_for(line.split(), icao):
                    return True
    except OSError:
        return False
    return False


def read_airport_block(path: str, icao: str) -> list[str] | None:
    """The lines of ``icao``'s block (header included, up to the next
    header or the ``99`` terminator), or ``None``."""
    icao = icao.upper()
    out: list[str] = []
    inside = False
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            toks = line.split()
            if toks and toks[0] in ("1", "16", "17", "99"):
                if inside:
                    break
                inside = _is_header_for(toks, icao)
            if inside:
                out.append(line.rstrip("\n"))
    return out or None


def block_sha256(block: list[str]) -> str:
    """sha256 of the block text — the airport's own signature (the whole
    Global Airports file is hundreds of MB; the block is what is read)."""
    h = hashlib.sha256()
    for line in block:
        h.update(line.encode("utf-8", "replace"))
        h.update(b"\n")
    return h.hexdigest()


def _has_pavement(path: str, icao: str) -> bool:
    block = read_airport_block(path, icao)
    return bool(block) and any(ln.startswith("110 ") for ln in block)


def find_apt_dat(xplane_root: str, icao: str) -> str | None:
    """The apt.dat that serves ``icao``, in v1's precedence (``find_airport_
    apt_dat``): a Custom Scenery pack whose apt.dat carries the airport
    WITH row-110 pavement wins, then Global Airports (XP12 ``Global
    Scenery`` layout, then the XP11 Custom Scenery one), then the stock
    default; a pack without pavement is the fallback of last resort."""
    icao = icao.upper()
    custom = os.path.join(xplane_root, "Custom Scenery")
    cands: list[str] = []
    if os.path.isdir(custom):
        for entry in sorted(os.listdir(custom)):
            if entry == "Global Airports":
                continue
            p = os.path.join(custom, entry, "Earth nav data", "apt.dat")
            if os.path.isfile(p) and file_has_airport(p, icao):
                cands.append(p)
    for p in (os.path.join(xplane_root, "Global Scenery", "Global Airports",
                           "Earth nav data", "apt.dat"),
              os.path.join(custom, "Global Airports", "Earth nav data",
                           "apt.dat"),
              os.path.join(xplane_root, "Resources", "default scenery",
                           "default apt dat", "Earth nav data", "apt.dat")):
        if os.path.isfile(p) and file_has_airport(p, icao):
            cands.append(p)
    for c in cands:
        if _has_pavement(c, icao):
            return c
    return cands[0] if cands else None


# ── block parser ─────────────────────────────────────────────────────────

def parse_airport_block(block: list[str]) -> AptAirport:
    """Parse one airport block (``read_airport_block`` output)."""
    head = block[0].split()
    if len(head) < 5:
        raise ValueError("apt.dat block: malformed header")
    elevation_ft = float(head[1])
    icao = head[4].upper()
    name = " ".join(head[5:])
    metadata: dict[str, str] = {}
    runways: list[AptRunway] = []
    helipads: list[AptHelipad] = []
    pavements: list[AptPavement] = []
    lines: list[AptLine] = []
    boundaries: list[AptBoundary] = []
    taxi_nodes: dict[int, AptTaxiNode] = {}
    taxi_edges: list[AptTaxiEdge] = []
    truck_edges: list[AptTaxiEdge] = []
    startups: list[AptStartup] = []

    # Contour-block state: header tokens + node rows.
    kind: int | None = None
    header: list[str] = []
    rows: list[list[str]] = []

    def flush() -> None:
        nonlocal kind, header, rows
        if kind == ROW_PAVEMENT:
            pv = _pavement(header, rows, len(pavements))
            if pv is not None:
                pavements.append(pv)
        elif kind == ROW_BOUNDARY:
            bd = _boundary(header, rows, len(boundaries))
            if bd is not None:
                boundaries.append(bd)
        elif kind == ROW_LINE:
            ln = _line(header, rows, len(lines))
            if ln is not None:
                lines.append(ln)
        kind, header, rows = None, [], []

    for raw in block[1:]:
        toks = raw.split()
        if not toks:
            continue
        try:
            rt = int(toks[0])
        except ValueError:
            continue
        if rt in (ROW_PAVEMENT, ROW_BOUNDARY, ROW_LINE):
            flush()
            kind, header = rt, toks
            continue
        if rt in _NODE_ROWS:
            if kind is not None:
                rows.append(toks)
            continue
        if rt in (ROW_END, ROW_END_BEZIER):
            if kind == ROW_LINE:
                rows.append(toks)
                flush()
            continue
        flush()
        if rt == ROW_RUNWAY:
            rw = _runway(toks)
            if rw is not None:
                runways.append(rw)
        elif rt == ROW_HELIPAD:
            hp = _helipad(toks)
            if hp is not None:
                helipads.append(hp)
        elif rt == ROW_TAXI_NODE and len(toks) >= 5:
            try:
                n = AptTaxiNode(int(toks[4]), float(toks[1]), float(toks[2]),
                                toks[3], " ".join(toks[5:]))
                taxi_nodes[n.id] = n
            except ValueError:
                pass
        elif rt == ROW_TAXI_EDGE and len(toks) >= 5:
            try:
                taxi_edges.append(AptTaxiEdge(
                    int(toks[1]), int(toks[2]), toks[3] == "oneway",
                    toks[4], " ".join(toks[5:])))
            except ValueError:
                pass
        elif rt == ROW_TRUCK_EDGE and len(toks) >= 4:
            try:
                truck_edges.append(AptTaxiEdge(
                    int(toks[1]), int(toks[2]), toks[3] == "oneway",
                    "truck", " ".join(toks[4:])))
            except ValueError:
                pass
        elif rt == ROW_STARTUP and len(toks) >= 6:
            try:
                startups.append(AptStartup(
                    " ".join(toks[6:]), float(toks[1]), float(toks[2]),
                    float(toks[3]), toks[4], toks[5]))
            except ValueError:
                pass
        elif rt == ROW_METADATA and len(toks) >= 2:
            metadata[toks[1]] = " ".join(toks[2:])
    flush()
    return AptAirport(icao, name, elevation_ft, metadata, tuple(runways),
                      tuple(helipads), tuple(pavements), tuple(lines),
                      tuple(boundaries), taxi_nodes, tuple(taxi_edges),
                      tuple(truck_edges), tuple(startups))


def _runway(toks: list[str]) -> AptRunway | None:
    """``100 width surface shoulder smoothness centerline edge_lights
    distance_signs <end_a:9> <end_b:9>``; an end block is ``desig lat lon
    displaced blastpad markings approach tdz reil``."""
    if len(toks) < 26:
        return None
    try:
        width = float(toks[1])
        surface = int(toks[2])
        ends = []
        for i in (8, 17):
            e = toks[i:i + 9]
            ends.append((e[0], float(e[1]), float(e[2]), float(e[3]),
                         float(e[4])))
    except (ValueError, IndexError):
        return None
    return AptRunway(width, surface, (ends[0], ends[1]))


def _helipad(toks: list[str]) -> AptHelipad | None:
    """``102 name lat lon heading length width surface ...``."""
    if len(toks) < 8:
        return None
    try:
        return AptHelipad(toks[1], float(toks[2]), float(toks[3]),
                          float(toks[4]), float(toks[5]), float(toks[6]),
                          int(toks[7]))
    except ValueError:
        return None


def _pavement(header: list[str], rows: list[list[str]],
              index: int) -> AptPavement | None:
    try:
        surface = int(header[1])
        smooth = float(header[2])
        orient = float(header[3])
    except (ValueError, IndexError):
        return None
    rings = [tuple(r) for r in _contours(rows, closed_only=True) if len(r) >= 3]
    if not rings:
        return None
    return AptPavement(index, surface, smooth, orient,
                       " ".join(header[4:]).strip(), tuple(rings))


def _boundary(header: list[str], rows: list[list[str]],
              index: int) -> AptBoundary | None:
    rings = [tuple(r) for r in _contours(rows, closed_only=True) if len(r) >= 3]
    if not rings:
        return None
    return AptBoundary(index, " ".join(header[1:]).strip(), tuple(rings))


def _line(header: list[str], rows: list[list[str]],
          index: int) -> AptLine | None:
    if not rows:
        return None
    closed = int(rows[-1][0]) in (ROW_CLOSE, ROW_CLOSE_BEZIER)
    pts = _tessellate(rows, closed)
    if len(pts) < 2:
        return None
    try:
        line_type = int(rows[0][3]) if int(rows[0][0]) == ROW_NODE else \
            int(rows[0][5])
    except (ValueError, IndexError):
        line_type = 0
    return AptLine(index, " ".join(header[1:]).strip(), line_type,
                   tuple(pts), closed)


def _contours(rows: list[list[str]], closed_only: bool
              ) -> list[list[LonLat]]:
    """Split node rows into contours at each 113/114 (or 115/116) and
    tessellate each."""
    out: list[list[LonLat]] = []
    cur: list[list[str]] = []
    for r in rows:
        cur.append(r)
        rt = int(r[0])
        if rt in (ROW_CLOSE, ROW_CLOSE_BEZIER):
            out.append(_tessellate(cur, True))
            cur = []
        elif rt in (ROW_END, ROW_END_BEZIER):
            if not closed_only:
                out.append(_tessellate(cur, False))
            cur = []
    return out


# ── bezier flattening ────────────────────────────────────────────────────

def _xy(r: list[str]) -> LonLat:
    return (float(r[2]), float(r[1]))


def _ctrl(r: list[str]) -> LonLat | None:
    if int(r[0]) in (ROW_NODE_BEZIER, ROW_CLOSE_BEZIER, ROW_END_BEZIER):
        try:
            return (float(r[4]), float(r[3]))
        except (ValueError, IndexError):
            return None
    return None


def _mirror(p: LonLat, about: LonLat) -> LonLat:
    return (2 * about[0] - p[0], 2 * about[1] - p[1])


def _metres(a: LonLat, b: LonLat, lon_scale: float) -> float:
    return math.hypot((a[0] - b[0]) * lon_scale, (a[1] - b[1]) * _LAT_SCALE)


def _bezier(p0: LonLat, ctrls: tuple[LonLat, ...], p3: LonLat,
            n: int) -> list[LonLat]:
    """Quadratic (one control) or cubic (two) samples, ``n`` segments."""
    pts: list[LonLat] = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        if len(ctrls) == 1:
            c = ctrls[0]
            pts.append((u * u * p0[0] + 2 * u * t * c[0] + t * t * p3[0],
                        u * u * p0[1] + 2 * u * t * c[1] + t * t * p3[1]))
        else:
            c1, c2 = ctrls
            b0, b1, b2, b3 = u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3
            pts.append((b0 * p0[0] + b1 * c1[0] + b2 * c2[0] + b3 * p3[0],
                        b0 * p0[1] + b1 * c1[1] + b2 * c2[1] + b3 * p3[1]))
    return pts


def _segments_for(a: LonLat, ctrls: tuple[LonLat, ...], b: LonLat,
                  lon_scale: float) -> int:
    """Adaptive segment count: enough for the sagitta bound, never denser
    than the minimum vertex spacing (v1 ``_effective_bezier_segments``)."""
    span = 0.0
    prev = a
    for p in (*ctrls, b):
        span += _metres(prev, p, lon_scale)
        prev = p
    chord = _metres(a, b, lon_scale)
    if chord < 1e-9:
        return 1
    ux = (b[0] - a[0]) * lon_scale / chord
    uy = (b[1] - a[1]) * _LAT_SCALE / chord
    dev = 0.0
    for c in ctrls:
        wx = (c[0] - a[0]) * lon_scale
        wy = (c[1] - a[1]) * _LAT_SCALE
        dev = max(dev, abs(wx * uy - wy * ux))
    if dev <= 1e-9:
        return 1
    n_sag = math.ceil(math.sqrt(dev / SAGITTA_MAX_M))
    n_sp = int(span // MIN_VERTEX_SPACING_M)
    return max(1, min(n_sag, n_sp))


def _tessellate(rows: list[list[str]], closed: bool) -> list[LonLat]:
    """Flatten a contour's node rows into ``(lon, lat)`` vertices."""
    n = len(rows)
    if n < 2:
        return [_xy(r) for r in rows]
    lon_scale = _LAT_SCALE * math.cos(math.radians(float(rows[0][1])))
    out: list[LonLat] = []
    last = n if closed else n - 1
    for i in range(last):
        a_row, b_row = rows[i], rows[(i + 1) % n]
        a, b = _xy(a_row), _xy(b_row)
        if not out or out[-1] != a:
            out.append(a)
        if a == b:
            continue
        ca, cb = _ctrl(a_row), _ctrl(b_row)
        if ca is None and cb is None:
            continue
        if ca is not None and cb is not None:
            ctrls: tuple[LonLat, ...] = (ca, _mirror(cb, b))
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            dev = 0.5 * max(_metres(ctrls[0], mid, lon_scale),
                            _metres(ctrls[1], mid, lon_scale))
        else:
            c = ca if ca is not None else _mirror(cb, b)  # type: ignore[arg-type]
            ctrls = (c,)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            dev = 0.5 * _metres(c, mid, lon_scale)
        if dev < FLATTEN_DEVIATION_M:
            continue
        for p in _bezier(a, ctrls, b, _segments_for(a, ctrls, b, lon_scale))[1:-1]:
            if out[-1] != p:
                out.append(p)
    if not closed:
        b = _xy(rows[-1])
        if not out or out[-1] != b:
            out.append(b)
    return _sparsify(out, closed, lon_scale)


def _sparsify(pts: list[LonLat], closed: bool,
              lon_scale: float) -> list[LonLat]:
    """Douglas-Peucker at the sagitta bound; a ring keeps its first vertex
    and antipode so it stays a ring (v1 ``_sparsify_ring_points``)."""
    if len(pts) < (4 if closed else 3):
        return pts

    def perp(p: LonLat, s: LonLat, e: LonLat) -> float:
        sx, sy = (e[0] - s[0]) * lon_scale, (e[1] - s[1]) * _LAT_SCALE
        px, py = (p[0] - s[0]) * lon_scale, (p[1] - s[1]) * _LAT_SCALE
        seg = math.hypot(sx, sy)
        return math.hypot(px, py) if seg < 1e-9 else abs(px * sy - py * sx) / seg

    def dp(seq: list[LonLat]) -> list[LonLat]:
        if len(seq) < 3:
            return list(seq)
        s, e = seq[0], seq[-1]
        best_i, best_d = 0, -1.0
        for i in range(1, len(seq) - 1):
            d = perp(seq[i], s, e)
            if d > best_d:
                best_i, best_d = i, d
        if best_d <= SAGITTA_MAX_M:
            return [s, e]
        return dp(seq[:best_i + 1])[:-1] + dp(seq[best_i:])

    if not closed:
        return dp(pts)
    half = len(pts) // 2
    first = dp(pts[:half + 1])
    second = dp(pts[half:] + [pts[0]])
    ring = first[:-1] + second[:-1]
    return ring if len(ring) >= 3 else pts
