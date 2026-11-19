"""THE DECK-PLATE BANDS AND CELLS OF ONE OBJ8 CUT (#2112; walled-multibridge
spec W6; ``airport/deck_plates``).

``obj8_split`` cuts a file into bodies; a body carrying a ``band`` keeps
only its source body's geometry inside that band -- or CELL -- of the
authored plan, and the bodies cut from one source body that way are
SIBLINGS.  A band ``(ux, uz, lo, hi)`` and a cell (its half-planes,
``geom/plate_cells``) are read alike, as half-planes (``plate_cells.
planes_of``).  This module is that one reading: which sibling a point
belongs to, and a static triangle CLIPPED at the cell lines
(Sutherland-Hodgman, the new corners appended to the source's own ``VT``
table, interpolated position, normal and texture coordinate; a corner on
a line is made once, whichever side asks first, so the two sides share
it).  The split writer's four rules are untouched: an ``ANIM`` block still
moves whole (to the cell of its middle), and a clipped triangle keeps its
authored winding.  A band's two planes are the exact negation of its
``lo <= s < hi`` reading, so a banded cut is the pre-cell cut byte for
byte.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..geom.plate_cells import holds, planes_of

__all__ = ["Bands"]


def _line_key(plane: tuple) -> tuple[float, float, float]:
    """One key per LINE, whichever side's plane names it."""
    nx, nz, c = plane[0], plane[1], plane[2]
    if nx < 0.0 or (nx == 0.0 and nz < 0.0):
        return (-nx, -nz, -c)
    return (nx, nz, c)


class Bands:
    """The band siblings of one cut (``obj8_split.BodyCut.band``): which band a
    point falls in, and a static triangle CLIPPED to each sibling's band.
    A clipped triangle's new corners are new ``VT`` rows APPENDED to the
    source table ``vt`` (each interpolated once per edge and line, so the
    two sides of a band line share their corners); every original index
    keeps its row.  With no banded body every method is the identity."""

    #: a corner this close to a band line (metres) stands on it
    EPS_M = 1e-6

    def __init__(self, bodies: _t.Sequence[_t.Any], vt: list[str]) -> None:
        self.planes = {b.body_id: planes_of(b.band) for b in bodies if b.band is not None}
        fam: dict[tuple, list[int]] = {}
        for b in bodies:
            if b.band is not None:
                fam.setdefault((tuple(b.comps), tuple(b.tris)), []).append(b.body_id)
        self.siblings = {bid: tuple(g) for g in fam.values() for bid in g}
        self._vt = vt
        self._rows: dict[int, list[float]] = {}
        self._cut: dict[tuple, int] = {}

    def _row(self, v: int) -> list[float]:
        hit = self._rows.get(v)
        if hit is None:
            t = self._vt[v].split()[1:9] if 0 <= v < len(self._vt) else []
            try:
                hit = [float(q) for q in t] + [0.0] * (8 - len(t))
            except ValueError:
                hit = [0.0] * 8
            self._rows[v] = hit
        return hit

    def _s(self, v: int, plane: tuple) -> float:
        r = self._row(v)
        return plane[0] * r[0] + plane[1] * r[2]

    def middle_of(self, tri: _t.Sequence[int]) -> np.ndarray:
        """The plan middle ``(x, y, z)`` of the vertices ``tri``."""
        return np.asarray([self._row(int(v))[:3] for v in tri]).mean(axis=0)

    def middle(self, commands: list[str], lines: _t.Sequence[int],
               idx: np.ndarray) -> np.ndarray:
        """The middle of the ``TRIS`` an ``ANIM`` block's ``lines`` draw."""
        vs: list[int] = []
        for j in lines:
            t = commands[j].split()
            if t[0] == "TRIS" and len(t) >= 3:
                off, cnt = int(t[1]), int(t[2])
                vs.extend(int(q) for q in idx[off:off + cnt])
        return self.middle_of(vs) if vs else np.zeros(3)

    def pick(self, bid: int, p: _t.Sequence[float]) -> int:
        """``bid``'s sibling whose band holds the point ``p``; ``bid``
        itself where it has none."""
        x, z = float(p[0]), float(p[2])
        for s in self.siblings.get(bid, ()):
            if all(holds(q, q[0] * x + q[1] * z) for q in self.planes[s]):
                return s
        return bid

    def _corner(self, i: int, j: int, plane: tuple) -> int:
        """The row on edge ``i``-``j`` where ``plane``'s line crosses it."""
        if i > j:
            i, j = j, i
        key = (i, j, _line_key(plane))
        hit = self._cut.get(key)
        if hit is not None:
            return hit
        c = plane[2]
        si, sj = self._s(i, plane), self._s(j, plane)
        t = 0.0 if sj == si else (c - si) / (sj - si)
        a, b = self._row(i), self._row(j)
        r = [a[k] + t * (b[k] - a[k]) for k in range(8)]
        n = math.sqrt(r[3] ** 2 + r[4] ** 2 + r[5] ** 2)
        if n > 0.0:
            r[3:6] = [q / n for q in r[3:6]]
        self._vt.append(f"VT\t{r[0]:.4f} {r[1]:.4f} {r[2]:.4f}\t{r[3]:.4f} {r[4]:.4f} "
                        f"{r[5]:.4f}\t{r[6]:.6f} {r[7]:.6f}")
        self._rows[len(self._vt) - 1] = r
        self._cut[key] = len(self._vt) - 1
        return len(self._vt) - 1

    def _half(self, poly: list[int], plane: tuple) -> list[int]:
        """Sutherland-Hodgman: ``poly`` cut to ``plane``'s side."""
        def inside(v: int) -> bool:
            return self._s(v, plane) - plane[2] >= -self.EPS_M
        out: list[int] = []
        for k, cur in enumerate(poly):
            prev = poly[k - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(self._corner(prev, cur, plane))
                out.append(cur)
            elif inside(prev):
                out.append(self._corner(prev, cur, plane))
        return out

    def clip(self, bid: int, tri: tuple[int, int, int]
             ) -> list[tuple[int, tuple[int, int, int]]]:
        """``(sibling, triangle)`` for every piece of ``tri`` in each of
        ``bid``'s siblings' cells, in the authored winding."""
        out: list[tuple[int, tuple[int, int, int]]] = []
        for s in self.siblings[bid]:
            planes = self.planes[s]
            sv = [[self._s(v, q) for v in tri] for q in planes]
            if all(min(x) >= q[2] - self.EPS_M for x, q in zip(sv, planes, strict=True)):
                # within the cell to EPS: whole, to the one sibling that
                # holds its corners or its middle (a line is one side's)
                if all(holds(q, e) for x, q in zip(sv, planes, strict=True) for e in x) \
                        or all(holds(q, sum(x) / 3.0) for x, q in zip(sv, planes, strict=True)):
                    out.append((s, tri))
                continue
            if any(max(x) <= q[2] + self.EPS_M for x, q in zip(sv, planes, strict=True)):
                continue
            poly = list(tri)
            for q in planes:
                if len(poly) < 3:
                    break
                poly = self._half(poly, q)
            out.extend((s, (poly[0], poly[k], poly[k + 1]))
                       for k in range(1, len(poly) - 1))
        return out
