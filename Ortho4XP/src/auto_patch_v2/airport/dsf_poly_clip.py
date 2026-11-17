"""THE DSF POLYGON CLIP (spec 2123 §A3 / §B3): a region R taken out of
the draped pavement pages (``.pol``) and painted lines (``.lin``) of a
pack DSF's DSFTool text dump -- the DSF half of what ``apt_edit`` does to
apt.dat.

* a ``.pol`` page R touches becomes ``page - R`` (one ``BEGIN_POLYGON``
  per piece, same definition and parameter); a page R does not touch is
  copied line for line;
* a ``.lin`` R touches is split at R, its inside dropped (each piece an
  open line, parameter 0);
* a UV-MAPPED page (parameter 65535: the texture is pinned per vertex) R
  touches is REFUSED by name (:class:`UvMappedPage`) -- a clip would need
  new texture coordinates nobody authored;
* every other polygon (facades, forests, ``.ags``/``.agb``) is never
  touched.

Points are ``POLYGON_POINT lon lat [clon clat]``: a page's bezier control
point shapes the segment the way an apt.dat ``112`` row does, so each
segment is flattened by ``apt_dat.segment_points``.  A rewritten page
keeps its coordinate count; its new points carry the control point equal
to the point (WED's straight node, 705 of 3,171 points in ESSA's pack).
The encoder reorders polygons; ``dsf_write.verify_roundtrip`` compares
them as a multiset, so a clip verifies like any other edit.  Build-time
impact: shapely on the pages R touches, milliseconds.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient

from . import apt_dat as _apt

__all__ = ["UvMappedPage", "ClipReport", "clip_text"]

UV_PARAM = 65535


class UvMappedPage(ValueError):
    """A UV-mapped ``.pol`` lies under the region: the clip refuses."""


@_dc.dataclass(frozen=True)
class ClipReport:
    pages_cut: int
    lines_cut: int
    area_removed_m2: float
    length_removed_m: float


def _pseudo_row(t: list[str], bezier: bool) -> list[str]:
    """A ``POLYGON_POINT`` as an apt.dat node row (lat before lon); its
    3rd/4th coordinates are a control point only on a ``bezier`` page (on
    a UV page they are the texture coordinates)."""
    if bezier and len(t) >= 5 and (t[3], t[4]) != (t[1], t[2]):
        return ["112", t[2], t[1], t[4], t[3]]
    return ["111", t[2], t[1]]


def _flatten(points: list[list[str]], closed: bool,
             bezier: bool) -> list[tuple[float, float]]:
    rows = [_pseudo_row(t, bezier) for t in points]
    n = len(rows)
    out: list[tuple[float, float]] = []
    for i in range(n if closed else n - 1):
        for q in _apt.segment_points(rows[i], rows[(i + 1) % n]):
            if not out or out[-1] != q:
                out.append(q)
    if closed and len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _point(lon: float, lat: float, ncoords: int) -> str:
    xy = f"{lon:.9f} {lat:.9f}"
    return f"POLYGON_POINT {xy} {xy}" if ncoords >= 4 else f"POLYGON_POINT {xy}"


def _blocks(lines: list[str]) -> _t.Iterator[tuple[int, int, list[str], list[list[list[str]]]]]:
    """``(start, end, header tokens, windings)`` per ``BEGIN_POLYGON``."""
    i = 0
    while i < len(lines):
        t = lines[i].split()
        if t and t[0] == "BEGIN_POLYGON":
            start, head, wind = i, t, []
            while i < len(lines) and lines[i].split()[:1] != ["END_POLYGON"]:
                u = lines[i].split()
                if u[:1] == ["BEGIN_WINDING"]:
                    wind.append([])
                elif u[:1] == ["POLYGON_POINT"]:
                    wind[-1].append(u)
                i += 1
            yield start, i + 1, head, wind
        i += 1


def clip_text(text: str, region: Polygon,
              wanted: _t.Callable[[str], bool] = lambda p: p.endswith((".pol", ".lin"))
              ) -> tuple[str, ClipReport]:
    """``text`` with ``region`` (lon/lat) clipped out of every draped
    page and line whose definition path ``wanted`` admits."""
    lines = text.split("\n")
    defs = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("POLYGON_DEF ")]
    out: list[str] = []
    pos = 0
    pages = n_lines = 0
    area = length = 0.0
    k = math.cos(math.radians(region.centroid.y)) * 111320.0 ** 2
    for start, end, head, wind in _blocks(lines):
        path = defs[int(head[1])]
        if not wanted(path) or not wind or not wind[0]:
            continue
        param, ncoords = int(head[2]), int(head[3])
        is_line = path.endswith(".lin")
        # coordinates per point: 2 plain, 4 bezier -- or, on a UV page
        # (param 65535), 4 = u v and 8 = bezier + u v
        bezier = ncoords >= 8 if (param == UV_PARAM and not is_line) else ncoords >= 4
        if is_line:
            pts = _flatten(wind[0], param == 1, bezier)
            if param == 1:
                pts = pts + pts[:1]
            g = LineString(pts) if len(pts) >= 2 else None
        else:
            rings = [_flatten(w, True, bezier) for w in wind]
            g = (Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])
                 if len(rings[0]) >= 3 else None)
            if g is not None and not g.is_valid:
                g = g.buffer(0)
        if g is None or not g.intersects(region):
            continue
        cut = g.intersection(region)
        if (cut.length if is_line else cut.area) <= 0:
            continue
        if not is_line and param == UV_PARAM:
            raise UvMappedPage(f"polygon at text line {start + 1} ({path}) is UV-mapped "
                               "and lies under the region")
        rest = g.difference(region)
        new: list[str] = []
        pieces = [p for p in getattr(rest, "geoms", [rest]) if not p.is_empty]
        for p in pieces:
            if is_line:
                new.append(f"BEGIN_POLYGON {head[1]} 0 {ncoords}")
                new.append("BEGIN_WINDING")
                new += [_point(x, y, ncoords) for x, y in p.coords]
                new.append("END_WINDING")
            else:
                p = orient(p, 1.0)
                new.append(f"BEGIN_POLYGON {head[1]} {head[2]} {ncoords}")
                for ring in (p.exterior, *p.interiors):
                    new.append("BEGIN_WINDING")
                    new += [_point(x, y, ncoords) for x, y in list(ring.coords)[:-1]]
                    new.append("END_WINDING")
            new.append("END_POLYGON")
        out += lines[pos:start] + new
        pos = end
        if is_line:
            n_lines += 1
            length += cut.length * math.sqrt(k)
        else:
            pages += 1
            area += cut.area * k
    out += lines[pos:]
    return "\n".join(out), ClipReport(pages, n_lines, round(area, 3), round(length, 2))
