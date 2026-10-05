"""THE BASIN RIM DIAGNOSTICS, READ ON DEMAND — the two note lines of a
basin that read the members' at-grade LINEWORK (owner RULINGS 2026-10-04x
(2), issue #362; split out of ``planar/basins.py``).

Two readings, both REPORTED per basin and neither ever a refusal:

* rule 3's OPEN STATIONS (:func:`_rim_open`, RULINGS 2026-09-04i): the
  region ring's stations farther than ``footprint_close_m`` from the
  founding shells' at-grade geometry;
* §24 (1) (a)'s RIM AGAINST THE SHELLS (``basin_geometry.rim_wall_report``,
  RULINGS 2026-09-14bp item 5 — refuted as a snap source, kept as numbers).

They are the ONLY readers of the at-grade linework in the basin pass, and
at OTHH that linework was ~145 s of every build for two sentences nothing
downstream reads (the cut is decided on the POLYGONS: the basement test).
A build therefore makes neither: ``build_basins`` holds no
:class:`RimReader` unless it is asked for one (``rim_diagnostics=True`` —
the ``--stage structures`` replay and ``tools/v2_solve_replay.py
--rim-diagnostics``), and writes :data:`ON_DEMAND` in the notes' place.
The text an on-demand read writes is the text every build wrote before.

Twins: ``tests/auto_patch_v2/test_rim362.py``, ``test_v2gradecache.py``.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as _np
import shapely
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..model.frame import XY
from .basin_geometry import rim_wall_report

__all__ = ["RimReader", "ON_DEMAND", "TREE_WINDOW"]

#: the note a BUILD carries in place of the two readings
ON_DEMAND = ("rim diagnostics (04i rule 3 open stations; §24 (1) (a) rim vs the shells' "
             "at-grade geometry) NOT READ in a build (owner RULINGS 2026-10-04x (2)): "
             "read on demand — `python -m auto_patch_v2.planar ICAO --stage structures` "
             "or `tools/v2_solve_replay.py --replay PKL --from planar --rim-diagnostics`")

#: How many MEMBER RIM INDEXES the reader keeps at once.  One shell's
#: linework can be 1.6 M parts, so this window is the ceiling on what the
#: rim diagnostic holds; the same two shells found their way into ~40 of
#: VHHH's rings, so a window at all is worth 1.25 s of part-derivation each.
TREE_WINDOW = 4

#: the end of the member walk (a member's index may legitimately be ``None``)
_DONE = object()


def _rim_open(ring: Polygon, rim_trees: _t.Iterable, step: float, reach: float
              ) -> tuple[int, int, XY | None]:
    """The closed-region test (04i rule 3): ``(open stations, stations,
    the first open station)`` — a station is OPEN when it lies farther
    than ``reach`` from the founding shells' at-grade geometry.

    ``rim_trees`` is a LAZY sequence of ONE INDEX PER MEMBER, never one
    index over the union — lazy because holding all of them is the same
    peak (owner 2026-09-13, round 2).  The distance from a point to a set
    of lines is the minimum over the set, so unioning the members changes
    neither the point set nor that minimum — but at VHHH the union cost
    979.5 s over 96 rings, and materialising every member's linework at
    once cost basin:0 alone 60,402,378 ``LineString`` objects, 96.4 s and
    12.4 -> 34.9 GB of resident memory.  Per member, each index is one
    shell's parts; a station once closed is never asked again, so the
    query shrinks as the members are walked."""
    ext = ring.exterior
    n = max(4, int(math.ceil(ext.length / step)))
    pts = shapely.line_interpolate_point(ext, [ext.length * i / n for i in range(n)])
    near = _np.zeros(n, dtype=bool)
    todo = _np.arange(n)
    walk = iter(rim_trees)
    while todo.size:
        tree = next(walk, _DONE)
        if tree is _DONE:
            break
        if tree is None:
            continue
        hit = tree.query_nearest(pts[todo], max_distance=reach, all_matches=False)
        idx = _np.asarray(hit[0] if _np.ndim(hit) == 2 else hit, dtype=int)
        if idx.size:
            near[todo[idx]] = True
            keep = _np.ones(todo.size, dtype=bool)
            keep[idx] = False
            todo = todo[keep]
    open_i = _np.flatnonzero(~near)
    if open_i.size == 0:
        return 0, n, None
    p0 = pts[int(open_i[0])]
    return int(open_i.size), n, (float(p0.x), float(p0.y))


def _rim_index(geom):
    """One member's at-grade linework as an index over its PARTS: a point
    against a whole multi-part rim is an O(parts) GEOS distance (VHHH's
    96 rings cost 549,207 of them, 1,196 s of a 3,580 s build), and the
    rim reading is a REPORTED DIAGNOSTIC that refuses nothing.

    THE EMPTY TEST IS VECTORISED (owner RULINGS 2026-09-14q, scout
    ``v2partcost2``): ``g.is_empty`` is a PROPERTY read per part, and
    VHHH's 336 calls of ~370 k parts each made 120,820,793 of them — 137 s
    profiled, ~105 s shipped, to filter a list that is almost never
    filtered.  ``shapely.is_empty`` over the array is one C call and
    yields the same parts in the same order."""
    if geom is None:
        return None
    parts = shapely.get_parts(geom)
    if parts.size:
        parts = parts[~shapely.is_empty(parts)]
    return STRtree(parts) if parts.size else None


class RimReader:
    """The two readings of one basin pass, as its note lines.

    ``lines_of(member)`` is the member's at-grade linework (the basin
    pass's own at-grade read, so the placement is read ONCE for the rim
    and the own-cover test); ``trees`` a bounded map (``get`` / ``put``)
    of the members' indexes; ``once(key, read)`` the pass's ring-reading
    memo (``planar/pack_reads.ring_reads``); ``ll(geom)`` the report's
    ``lat,lon`` of a point."""

    def __init__(self, lines_of: _t.Callable, trees, once: _t.Callable,
                 ll: _t.Callable[[object], str], step: float, reach: float) -> None:
        self._lines_of, self._trees, self._once, self._ll = lines_of, trees, once, ll
        self._step, self._reach = step, reach

    def _tree(self, o):
        v = self._trees.get(o.id)
        if v is None:
            v = (_rim_index(self._lines_of(o)),)
            self._trees.put(o.id, v)
        return v[0]

    def notes(self, ring: Polygon, rim: Polygon, members: _t.Sequence) -> tuple[str, str]:
        """``(rule 3's note, §24 (1) (a)'s note)`` for the admitted basin
        of region ``ring`` cut at ``rim``."""
        mk = tuple(o.id for o in members)
        open_n, n, first = self._once(("rim_open", ring.wkb, mk), lambda: _rim_open(
            ring, (self._tree(o) for o in members), self._step, self._reach))
        rim_note = (f"rim stations beyond {self._reach} m of the shells' at-grade "
                    f"geometry: {open_n} of {n} ({open_n * ring.exterior.length / n:.0f} of "
                    f"{ring.exterior.length:.0f} m"
                    + (f", first at {self._ll(Point(first))}" if first else "") + ")")
        # §24 (1) (a) THE RIM IS THE WALL (RULINGS 2026-09-14bp item 5) —
        # REFUTED AS RULED, and this is the measurement that refutes it
        # (``rim_wall_report``'s docstring carries the reading).  The ring
        # is REPORTED against the reference, never snapped onto it.
        d_before, probe = self._once(("rim_wall", rim.wkb, mk), lambda: rim_wall_report(
            rim, (self._tree(o) for o in members), self._step, self._reach))
        fin = sorted(d for d in d_before if d != float('inf'))
        snap_note = (
            "rim vs the shells' at-grade geometry (§24 (1) (a), REPORTED — the snap that "
            "ruling states is refuted: the reference is a per-component contour, not the "
            "wall's ground trace): "
            + (f"median {fin[len(fin) // 2]:.2f} m, worst {fin[-1]:.2f} m over {len(fin)} "
               f"stations" if fin else "no station had at-grade geometry at all")
            + "; stations within " + ", ".join(f"{r:g} m: {probe[r]}" for r in sorted(probe)))
        return rim_note, snap_note
