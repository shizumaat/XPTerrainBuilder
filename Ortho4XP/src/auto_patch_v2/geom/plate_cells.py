"""THE CELLS OF A WALLED MULTI-BRIDGE FRAME (walled-multibridge-frames spec
W6): the frame cut on EVERY span's own axis, not on one.

A CELL is an intersection of half-planes ``(nx, nz, c, strict)`` in the
deck's authored plan ``(x, z)``: a point is in it where ``nx*x + nz*z >= c``
for every plane (``>`` where ``strict``).  A BAND ``(ux, uz, lo, hi)``
(``plate_bands.Plates.band``, #2112 / RULINGS 2026-11-18i) is the two-plane
case ``(ux, uz, lo, False), (-ux, -uz, -hi, True)`` (:func:`planes_of`), so
``obj8_band`` clips both through one reading.

THE PARTITION.  Each span PIECE ``i`` (its axis ``a -> b``, its spans along
it, its ring) owns a REGION: the frame's plan split between the pieces by a
POWER DIAGRAM whose weights put each pair's line at the MIDDLE OF THE GAP
between the two rings along their centres' line (exact for two pieces, the
least-squares fit for more) -- a power diagram, so the regions tile the
plane with no point in two and none in none.  Inside its region the piece's
band lines cut it as ``deck_plates._span_plates`` cuts a one-axis frame:
each span grown ``seat_m`` past its end lines is a SPAN cell; between two
spans of one cut is an AT-GRADE cell (18i (3): dropped); before the first
and after the last is a REST cell (trench, walls, riders) that is never
dropped and reads the end line it lies beyond (W6: "each rest cell takes
its nearest span's end-line reading -- a rigid translate").

No airport, pack or resource is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["SpanAxis", "Cell", "Cells", "planes_of", "span_cells"]

#: one half-plane: ``(nx, nz, c, strict)`` -- ``n.p >= c`` (``>`` if strict)
HalfPlane = tuple[float, float, float, bool]


def planes_of(band: _t.Sequence[_t.Any]) -> tuple[HalfPlane, ...]:
    """The half-planes of a BAND ``(ux, uz, lo, hi)`` (an infinite side
    dropped), or a CELL's own planes unchanged."""
    if len(band) == 4 and not isinstance(band[0], (tuple, list)):
        ux, uz, lo, hi = (float(q) for q in band)
        out: list[HalfPlane] = []
        if math.isfinite(lo):
            out.append((ux, uz, lo, False))
        if math.isfinite(hi):
            out.append((-ux, -uz, -hi, True))
        return tuple(out)
    return tuple((float(p[0]), float(p[1]), float(p[2]), bool(p[3])) for p in band)


def holds(plane: HalfPlane, s: float) -> bool:
    """Does the coordinate ``s = n.p`` lie on ``plane``'s side?"""
    return s > plane[2] if plane[3] else s >= plane[2]


@_dc.dataclass(frozen=True)
class SpanAxis:
    """One span piece in the authored plan: its cut's axis ends ``a``,
    ``b``, its spans ``((s_a, s_b), ...)`` in metres from ``a`` and its
    ring (the gap between pieces is read off the rings)."""

    a: tuple[float, float]
    b: tuple[float, float]
    spans: tuple[tuple[float, float], ...]
    ring: tuple[tuple[float, float], ...]


@_dc.dataclass(frozen=True)
class Cell:
    """One cell: its planes, the piece it belongs to, its kind (``span``,
    ``rest``, ``grade``), for a rest cell the end line it reads (0 the
    ``a`` side, 1 the ``b`` side; -1 otherwise), its piece's axis and its
    extent ``(lo, hi)`` along it."""

    planes: tuple[HalfPlane, ...]
    piece: int
    kind: str
    end: int
    axis: tuple[float, float]
    extent: tuple[float, float]


@_dc.dataclass(frozen=True)
class Cells:
    """The cells of a frame (module doc), read as ``deck_plates`` reads a
    ``Plates``: ``len``, the cell of a point, the cell a body clips to."""

    cells: tuple[Cell, ...]

    def __len__(self) -> int:
        return len(self.cells)

    def band_of(self, x: float, z: float) -> int:
        """The cell the authored plan point ``(x, z)`` stands in."""
        x, z = float(x), float(z)
        for k, c in enumerate(self.cells):
            if all(holds(p, p[0] * x + p[1] * z) for p in c.planes):
                return k
        return -1

    def band(self, k: int) -> tuple[HalfPlane, ...]:
        """Cell ``k``'s planes: what ``obj8_split.BodyCut.band`` clips to."""
        return self.cells[k].planes

    def axis_of(self, k: int) -> tuple[float, float]:
        return self.cells[k].axis

    def extent_of(self, k: int) -> tuple[float, float]:
        return self.cells[k].extent

    def anchor_of(self, k: int) -> "tuple[int, int] | None":
        """A REST cell's reading ``(its piece's span cell on that side, the
        end)``; ``None`` for a span or at-grade cell."""
        c = self.cells[k]
        if c.kind != "rest":
            return None
        spans = [j for j, q in enumerate(self.cells) if q.piece == c.piece and q.kind == "span"]
        return (spans[0] if c.end == 0 else spans[-1]), c.end

    def neighbours(self, reach_m: float = 1e4) -> list[tuple[int, int]]:
        """Pairs of cells of DIFFERENT pieces sharing a stretch of line (the
        steps W6 lists), read inside a box ``reach_m`` round the origin."""
        import shapely
        box = shapely.box(-reach_m, -reach_m, reach_m, reach_m)
        polys = [_clip(box, c.planes, reach_m) for c in self.cells]
        out = []
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                if self.cells[i].piece == self.cells[j].piece:
                    continue
                if polys[i].is_empty or polys[j].is_empty:
                    continue
                if polys[i].boundary.intersection(polys[j].boundary).length > 0.01:
                    out.append((i, j))
        return out


def _clip(poly: _t.Any, planes: _t.Sequence[HalfPlane], reach_m: float) -> _t.Any:
    """``poly`` cut to ``planes`` (each as a big box on its side)."""
    import shapely
    big = 4.0 * reach_m
    for nx, nz, c, _s in planes:
        ox, oz, tx, tz = nx * c, nz * c, -nz, nx       # a point on the line, along it
        poly = poly.intersection(shapely.Polygon([
            (ox + tx * big, oz + tz * big), (ox - tx * big, oz - tz * big),
            (ox - tx * big + nx * big, oz - tz * big + nz * big),
            (ox + tx * big + nx * big, oz + tz * big + nz * big)]))
    return poly


def _weights(cen: np.ndarray, rings: list[np.ndarray]) -> np.ndarray:
    """Power weights putting each pair's line at its rings' gap middle
    along the centres' line (module doc)."""
    n = len(cen)
    rows, rhs = [], []
    for i in range(n):
        for j in range(i + 1, n):
            d = cen[j] - cen[i]
            dist = float(np.hypot(*d))
            if dist <= 0.0:
                continue
            u = d / dist
            mid = 0.5 * (float((rings[i] @ u).max()) + float((rings[j] @ u).min()))
            r = np.zeros(n)
            r[i], r[j] = 1.0, -1.0
            rows.append(r)
            rhs.append(2.0 * dist * mid - (float(cen[j] @ cen[j]) - float(cen[i] @ cen[i])))
    if not rows:
        return np.zeros(n)
    return np.linalg.lstsq(np.asarray(rows), np.asarray(rhs), rcond=None)[0]


def _region(i: int, cen: np.ndarray, w: np.ndarray) -> "list[HalfPlane] | None":
    """Piece ``i``'s power-diagram planes (the lower index holds the line)."""
    out: list[HalfPlane] = []
    for j in range(len(cen)):
        if j == i:
            continue
        lo, hi = min(i, j), max(i, j)
        d = cen[hi] - cen[lo]
        dist = float(np.hypot(*d))
        if dist <= 0.0:
            return None
        nx, nz = float(d[0] / dist), float(d[1] / dist)
        k = (float(cen[hi] @ cen[hi]) - float(cen[lo] @ cen[lo]) + w[lo] - w[hi]) / (2.0 * dist)
        out.append((-nx, -nz, -k, False) if i == lo else (nx, nz, k, True))
    return out


def span_cells(pieces: _t.Sequence[SpanAxis], seat_m: float) -> "Cells | None":
    """The frame's cells (module doc), or None: fewer than two pieces, a
    piece with no axis or no span, two pieces on one centre, or spans whose
    grown bands overlap along their axis."""
    if len(pieces) < 2:
        return None
    rings = [np.asarray(p.ring, float).reshape(-1, 2) for p in pieces]
    if any(r.shape[0] < 3 for r in rings):
        return None
    cen = np.asarray([r.mean(axis=0) for r in rings])
    w = _weights(cen, rings)
    cells: list[Cell] = []
    for i, p in enumerate(pieces):
        region = _region(i, cen, w)
        length = math.hypot(p.b[0] - p.a[0], p.b[1] - p.a[1])
        if region is None or length <= 0.0 or not p.spans:
            return None
        ux, uz = (p.b[0] - p.a[0]) / length, (p.b[1] - p.a[1]) / length
        s0 = ux * p.a[0] + uz * p.a[1]
        lines = [s0 + float(q) for sa, sb in sorted(p.spans)
                 for q in (sa - seat_m, sb + seat_m)]
        if any(b <= a for a, b in zip(lines, lines[1:], strict=False)):
            return None
        edges = (-math.inf, *lines, math.inf)
        last = len(edges) - 2
        for k, (lo, hi) in enumerate(zip(edges[:-1], edges[1:], strict=True)):
            kind = "span" if k % 2 == 1 else ("rest" if k in (0, last) else "grade")
            cells.append(Cell(tuple(region) + planes_of((ux, uz, lo, hi)), i, kind,
                              (0 if k == 0 else 1) if kind == "rest" else -1,
                              (ux, uz), (lo, hi)))
    return Cells(tuple(cells))
