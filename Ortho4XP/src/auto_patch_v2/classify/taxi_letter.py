"""THE TAXIWAY LETTER WHERE THE ROUTE STATES NONE (master 2026-10-16, lane
regL3 round 2; RULINGS 2026-10-15l (1), audit row 3).

A taxiway's letter is its apt.dat 1202 ``width_class``.  Where a taxi chain
carries none, the letter is a WITNESS question, never a default: the
pavement's own width across the chain, read through the one letter-by-width
classifier (``law.reference_code.taxi_code_letter``):

* :func:`letter_chains_by_width` — every unlettered chain is cut by a
  perpendicular every ``_STATION_M`` along it; the pavement piece under the
  centreline is the cross-section, and the chain's width is the MEDIAN of
  the cross-sections no wider than ``_MAX_SECTION_FACTOR`` × the widest
  lettered taxiway (a cross-section over an apron or a junction is not a
  taxiway width).  With no such cross-section the chain stays unlettered.
* :func:`letter_faces_by_neighbour` — a taxi-family FACE no lettered chain
  reaches takes the widest letter of the taxi faces it shares an edge with
  (the taxiways it joins).

The letter C default (``zones.toml`` / ``rulesets.toml``) is left for what
neither witness reaches.  Both functions count what they lettered.
"""
from __future__ import annotations

import dataclasses as _dc
import statistics
import typing as _t

import shapely.prepared

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from ..law import Law
from ..law.reference_code import taxi_code_letter
from .evidence import Chain

__all__ = ["letter_chains_by_width", "letter_faces_by_neighbour"]

_LETTERS = "ABCDEF"
#: the spacing of the cross-sections along a chain (m)
_STATION_M = 10.0
#: a cross-section wider than this many times the widest taxiway width the
#: authority states is apron or junction, not a taxiway's width
_MAX_SECTION_FACTOR = 2.0


def _sections(line: LineString, pavement, half_m: float, runway=None) -> list[float]:
    """The pavement cross-section under the centreline at each station (a
    station on a runway is the runway's section, not the taxiway's)."""
    out: list[float] = []
    n = max(1, int(line.length // _STATION_M))
    for k in range(n):
        s = (k + 0.5) * line.length / n
        p = line.interpolate(s)
        if runway is not None and runway.contains(p):
            continue
        a, b = line.interpolate(max(0.0, s - 0.5)), line.interpolate(min(line.length, s + 0.5))
        dx, dy = b.x - a.x, b.y - a.y
        norm = (dx * dx + dy * dy) ** 0.5
        if norm <= 0.0:
            continue
        nx, ny = -dy / norm * half_m, dx / norm * half_m
        cut = LineString([(p.x - nx, p.y - ny), (p.x + nx, p.y + ny)]).intersection(pavement)
        for g in getattr(cut, "geoms", [cut]):
            if g.length > 0.0 and g.distance(Point(p.x, p.y)) < 1e-6:
                out.append(float(g.length))
                break
    return out


def letter_chains_by_width(chains: _t.Sequence[Chain], pavement, law: Law | None,
                           runway=None) -> tuple[list[Chain], dict[str, int]]:
    """``chains`` with every unlettered one lettered by its pavement width,
    and the count of chains per letter source (``1202`` / ``width`` /
    ``default``)."""
    counts = {"1202": 0, "width": 0, "default": 0}
    tbl = law.ruleset.taxi.width_m if law is not None else None
    widest = max((tbl.by_letter or {}).values(), default=0.0) if tbl is not None else 0.0
    out: list[Chain] = []
    rw = shapely.prepared.prep(runway) if runway is not None and not runway.is_empty else None
    for c in chains:
        if c.letter:
            counts["1202"] += 1
            out.append(c)
            continue
        cap = _MAX_SECTION_FACTOR * float(widest)
        secs = _sections(c.line, pavement, cap, rw) if cap > 0.0 \
            and pavement is not None and not pavement.is_empty else []
        secs = [w for w in secs if w < cap]
        letter = taxi_code_letter(law, statistics.median(secs)) if secs else None
        if letter:
            counts["width"] += 1
            c = _dc.replace(c, letters=tuple(letter for _l in c.letters) or (letter,))
        else:
            counts["default"] += 1
        out.append(c)
    return out, counts


def letter_faces_by_neighbour(final: list[list], taxi_roles: _t.Collection[str]
                              ) -> dict[str, int]:
    """Fill the letter (slot 3) of every unlettered taxi-family entry of
    ``final`` (``[role, ref, face, letter, evid, kind]``, edited in place)
    from the lettered taxi faces it shares an edge with; the counts of
    faces lettered by a chain, by a neighbour, and left to the default."""
    taxi = [e for e in final if e[0] in taxi_roles]
    lettered = [e for e in taxi if e[3]]
    counts = {"chain": len(lettered), "neighbour": 0, "default": 0}
    tree = STRtree([e[2] for e in lettered]) if lettered else None
    filled: list[tuple[list, str]] = []
    for e in taxi:
        if e[3]:
            continue
        near = []
        if tree is not None:
            for i in tree.query(e[2], predicate="intersects"):
                other = lettered[int(i)]
                if e[2].intersection(other[2]).length > 0.0:
                    near.append(other[3])
        if near:
            filled.append((e, max(near, key=_LETTERS.find)))
        else:
            counts["default"] += 1
    for e, letter in filled:
        e[3] = letter
        e[4] = dict(e[4], letter_source="neighbour")
        counts["neighbour"] += 1
    return counts
