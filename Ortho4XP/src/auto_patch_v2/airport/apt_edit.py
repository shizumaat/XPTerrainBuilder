"""THE apt.dat REGION CUT (spec 2123 §A3): a region R -- a generated
deck's footprint, a road bridge's span -- taken out of an airport block.

* every ``110`` pavement that R touches becomes ``pavement - R``: a HOLE
  where R lies inside it, a notch where R crosses its edge, two or more
  ``110`` chunks where R cuts it through.  Contours R does not touch are
  copied as their RAW rows (beziers and node codes intact); a contour R
  changes is written flattened (``111`` / ``113`` rows), each new edge
  keeping the line / light codes of the original segment it lies on, and
  none on R's own edges;
* every ``120`` linear feature R touches is split at R and its inside
  dropped -- returned to the caller as :class:`Dropped` (the deck redraws
  the paint and lights on its top); untouched features stay raw;
* nothing else changes (``130`` boundary, taxi routes ``1201``/``1202``,
  runways, signs): a route still crosses the deck.

THE GRAMMAR IT WRITES (X-Plane apt.dat 1100 spec, checked by P0 R1):
an outer boundary runs COUNTER-CLOCKWISE, each hole CLOCKWISE, every hole
closes with ``113``/``114`` and lies inside its boundary, holes never
overlap and a pavement never overlaps itself.  ESSA's shipped pavement 24
(WED 2.5) already carries exactly that: exterior CCW, 56 holes CW.  The
spec does not say what a node WITHOUT a code means; the writer keeps each
segment's own codes on the node that starts it, which reproduces the
original under either reading for every segment it does not cut.

Coordinates are ``(lon, lat)`` degrees, as ``apt_dat`` hands them out.
:func:`cut_block` is pure; :func:`edit_apt_dat` reads one file and writes
another plus the transform record ``<out>.o4_edits.json``.  Build-time
impact: shapely on a handful of features, milliseconds.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import math
import typing as _t

from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.geometry.polygon import orient

from . import apt_dat as _apt

__all__ = ["Dropped", "CutResult", "cut_block", "edit_apt_dat",
           "EDITS_SUFFIX"]

LonLat = tuple[float, float]
EDITS_SUFFIX = ".o4_edits.json"
_NODE = ("111", "112", "113", "114", "115", "116")
_CLOSE = ("113", "114")
_END = ("113", "114", "115", "116")
#: an edge belongs to an original segment when its midpoint lies this
#: close to it (degrees; ~1 cm)
_ON_SEGMENT_DEG = 1e-7


@_dc.dataclass(frozen=True)
class Dropped:
    """A piece of a ``120`` feature inside R: its points and the codes of
    the segment it came from (``line``, ``light``; 0 = none)."""

    feature_line: int
    points: tuple[LonLat, ...]
    line: int
    light: int


@_dc.dataclass(frozen=True)
class CutResult:
    block: list[str]
    dropped: tuple[Dropped, ...]
    record: tuple[dict, ...]


def _codes(t: list[str]) -> tuple[str, ...]:
    return tuple(t[3:] if t[0] in ("111", "113", "115") else t[5:])


def _split_codes(codes: _t.Sequence[str]) -> tuple[int, int]:
    line = light = 0
    for c in codes:
        v = int(c)
        if v >= 100:
            light = v
        else:
            line = v
    return line, light


def _features(block: list[str]) -> list[dict]:
    """``{code, start, end, header, contours: [[tokens…]…]}`` per
    ``110``/``120``/``130``; ``end`` is one past its last node row."""
    out: list[dict] = []
    cur: dict | None = None
    for i, raw in enumerate(block):
        t = raw.split()
        if t and t[0] in ("110", "120", "130"):
            cur = {"code": t[0], "start": i, "end": i + 1, "header": raw,
                   "contours": [[]]}
            out.append(cur)
            continue
        if cur is not None and t and t[0] in _NODE:
            cur["contours"][-1].append(t)
            cur["end"] = i + 1
            if t[0] in _END:
                cur["contours"].append([])
            continue
        cur = None
    for f in out:
        f["contours"] = [c for c in f["contours"] if c]
    return out


def _segments(contour: list[list[str]]) -> list[tuple[list[LonLat], tuple[str, ...]]]:
    """``(flattened points, codes)`` per node-to-node segment; a closed
    contour includes its closing segment back to the first node."""
    closed = contour[-1][0] in _CLOSE
    n = len(contour)
    last = n if closed else n - 1
    return [(_apt.segment_points(contour[i], contour[(i + 1) % n]), _codes(contour[i]))
            for i in range(last)]


def _ring(segs) -> list[LonLat]:
    pts: list[LonLat] = []
    for p, _ in segs:
        for q in p:
            if not pts or pts[-1] != q:
                pts.append(q)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def _row(code: str, p: LonLat, codes: _t.Sequence[str] = ()) -> str:
    return " ".join((code, f"{p[1]:.8f}", f"{p[0]:.8f}", *codes))


def _codes_on(seg_lines, a: LonLat, b: LonLat) -> tuple[str, ...]:
    mid = Point((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    for ls, codes in seg_lines:
        if ls.distance(mid) < _ON_SEGMENT_DEG:
            return codes
    return ()


def _key(coords) -> tuple[float, float, float]:
    g = Polygon(coords)
    c = g.centroid
    return (abs(g.area), c.x, c.y)


def _same(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    return abs(a[0] - b[0]) <= 1e-12 + 1e-9 * a[0] and abs(a[1] - b[1]) < 1e-9 \
        and abs(a[2] - b[2]) < 1e-9


def _m2(area_deg2: float, lat: float) -> float:
    return area_deg2 * 111320.0 ** 2 * math.cos(math.radians(lat))


def _cut_pavement(f: dict, region: Polygon) -> tuple[list[str], dict] | None:
    segs = [_segments(c) for c in f["contours"]]
    rings = [_ring(s) for s in segs]
    if len(rings[0]) < 3:
        return None
    poly = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])
    if not poly.is_valid:
        poly = poly.buffer(0)
    if not poly.intersects(region) or poly.intersection(region).area <= 0:
        return None
    rest = poly.difference(region)
    pieces = [g for g in getattr(rest, "geoms", [rest]) if g.area > 0]
    keys = [_key(r) if len(r) >= 3 else None for r in rings]
    seg_lines = [(LineString(p), c) for s in segs for p, c in s if len(p) >= 2]
    lines: list[str] = []
    rewritten = 0
    for piece in pieces:
        piece = orient(piece, 1.0)                       # exterior CCW, holes CW
        lines.append(f["header"])
        for ring in (piece.exterior, *piece.interiors):
            coords = list(ring.coords)[:-1]
            k = _key(coords)
            raw = next((j for j, kj in enumerate(keys) if kj is not None and _same(k, kj)), None)
            if raw is not None:
                lines += [" ".join(t) for t in f["contours"][raw]]
                continue
            rewritten += 1
            n = len(coords)
            for j, p in enumerate(coords):
                code = "113" if j == n - 1 else "111"
                lines.append(_row(code, p, _codes_on(seg_lines, p, coords[(j + 1) % n])))
    lat = region.centroid.y
    return lines, {"kind": "pavement_cut", "line": f["start"], "header": f["header"].strip(),
                   "pieces": len(pieces), "contours_rewritten": rewritten,
                   "area_removed_m2": round(_m2(poly.area - rest.area, lat), 3)}


def _ordered_parts(geom, along: LineString) -> list[list[LonLat]]:
    parts = [g for g in getattr(geom, "geoms", [geom]) if not g.is_empty and g.length > 0]
    parts.sort(key=lambda g: along.project(Point(g.coords[0])))
    return [list(g.coords) for g in parts]


def _cut_line(f: dict, region: Polygon) -> tuple[list[str], list[Dropped], dict] | None:
    segs = [s for c in f["contours"] for s in _segments(c)]
    if not any(len(p) >= 2 and LineString(p).intersects(region) for p, _ in segs):
        return None
    runs: list[list[tuple[LonLat, tuple[str, ...]]]] = []
    run: list[tuple[LonLat, tuple[str, ...]]] = []
    dropped: list[Dropped] = []
    removed = 0.0
    for pts, codes in segs:
        if len(pts) < 2:
            continue
        ls = LineString(pts)
        if not ls.intersects(region):
            outside = [pts]
        else:
            outside = _ordered_parts(ls.difference(region), ls)
            inside = _ordered_parts(ls.intersection(region), ls)
            line, light = _split_codes(codes)
            for p in inside:
                if len(p) < 2:
                    continue
                last = dropped[-1] if dropped else None
                if last is not None and (last.line, last.light) == (line, light) \
                        and last.points[-1] == tuple(p[0]):
                    dropped[-1] = _dc.replace(last, points=last.points + tuple(p[1:]))
                else:
                    dropped.append(Dropped(f["start"], tuple(p), line, light))
            removed += sum(LineString(p).length for p in inside if len(p) >= 2)
        for part in outside:
            starts_here = Point(part[0]).distance(Point(pts[0])) < 1e-12
            if not (starts_here and run and run[-1][0] == part[0]):
                if len(run) >= 2:
                    runs.append(run)
                run = [(part[0], codes)]
            for q in part[1:]:
                run.append((q, codes))
            if Point(part[-1]).distance(Point(pts[-1])) > 1e-12:
                runs.append(run)
                run = []
    if len(run) >= 2:
        runs.append(run)
    lines: list[str] = []
    for r in runs:
        lines.append(f["header"])
        for j, (p, _) in enumerate(r):
            if j == len(r) - 1:
                lines.append(_row("115", p))
            else:
                lines.append(_row("111", p, r[j + 1][1]))
    lat = region.centroid.y
    return lines, dropped, {"kind": "line_split", "line": f["start"],
                            "header": f["header"].strip(), "pieces": len(runs),
                            "length_removed_m": round(removed * 111320.0 * math.cos(
                                math.radians(lat)), 2)}


def cut_block(block: list[str], region: Polygon) -> CutResult:
    """``block`` (``apt_dat.read_airport_block``'s lines) with ``region``
    cut out of its pavements and linear features."""
    out: list[str] = []
    dropped: list[Dropped] = []
    record: list[dict] = []
    pos = 0
    for f in _features(block):
        got = None
        if f["code"] == "110":
            got = _cut_pavement(f, region)
            if got is not None:
                new, rec = got
        elif f["code"] == "120":
            got = _cut_line(f, region)
            if got is not None:
                new, d, rec = got
                dropped += d
        if got is None:
            continue
        out += block[pos:f["start"]]
        out += new
        record.append(rec)
        pos = f["end"]
    out += block[pos:]
    return CutResult(out, tuple(dropped), tuple(record))


def edit_apt_dat(src: str, dst: str, icao: str, region: Polygon) -> CutResult:
    """Cut ``region`` out of ``icao``'s block of ``src``; write the whole
    file to ``dst`` (every other line byte-identical) and the transform
    record to ``dst + EDITS_SUFFIX``."""
    with open(src, "r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        text = fh.read()
    eol = "\r\n" if "\r\n" in text[:4096] else "\n"
    lines = text.split(eol)
    block = _apt.read_airport_block(src, icao)
    if not block:
        raise ValueError(f"{src}: no {icao} block")
    start = next(i for i, ln in enumerate(lines) if ln.rstrip() == block[0].rstrip())
    if [ln.rstrip() for ln in lines[start:start + len(block)]] != [b.rstrip() for b in block]:
        raise ValueError(f"{src}: {icao} block does not match the file's lines")
    res = cut_block(block, region)
    lines[start:start + len(block)] = res.block
    with open(dst, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(eol.join(lines))
    with open(dst + EDITS_SUFFIX, "w", encoding="utf-8") as fh:
        json.dump({"icao": icao, "region_wkt": region.wkt, "edits": list(res.record)},
                  fh, indent=1)
    return res
