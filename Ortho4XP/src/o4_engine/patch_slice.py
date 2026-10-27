"""Slice one shape in two along the straight cut between two of its
nodes (issue #1318; owner rulings Q130-Q133, 2026-10-24).

Pure geometry over a polygon with holes, no I/O and no patch types:
:func:`cut` takes rings of node ids and their ``(lat, lon, alt)`` and says
which two rings the shape becomes.  ``patch_edit.slice_shape`` turns that
into a document edit (ids, ways, tags); the Mac app's
``SceneryKit/PatchSlice.swift`` is the twin, and both run the
``slice_shape`` cases of ``tests/fixtures/patch_edit_ops.json``.

THE RULES:

* The cut runs from node ``a`` to node ``b`` of the outer ring, two nodes
  that are not neighbours.  It must stay inside the shape: a cut that
  crosses or touches the outer ring, or runs outside it, is refused.
* Each cut node becomes two nodes :data:`GAP_M` apart, moved half the gap
  to either side of the cut line, perpendicular to it.  Every copy keeps
  the original node's height.
* A hole the cut crosses is sliced too: a node is added where the cut
  meets each of its edges (height interpolated along that edge), split the
  same way.  The hole stops being a hole; its two sides become notches in
  the two halves.  A cut through a corner of a hole is refused.
* The result is exactly two shapes; a cut that would leave more pieces (a
  U-shaped hole crossed through both arms) is refused.

Working orientation: the outer ring counter-clockwise, holes clockwise, so
the shape is always on the LEFT of every directed edge.  "L" is the side
to the left of the direction a -> b, "R" the side to its right.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["GAP_M", "SliceRefused", "Cut", "cut", "ring_area"]

#: The gap a slice leaves between the two halves (owner Q130), metres.
GAP_M = 0.5

_M_PER_DEG_LAT = 111320.0

#: A ring entry in a :class:`Cut`: a node id, or ``(k, side)`` for the
#: copy of cut point ``k`` on ``side`` ("L" or "R").
Label = _t.Union[int, _t.Tuple[int, str]]


class SliceRefused(ValueError):
    """The cut is not one this shape can take; the message says why."""


class Cut(_t.NamedTuple):
    #: The two halves, each starting at its copy of ``a``, counter-
    #: clockwise (``ccw`` says whether the input outer ring was).
    left: tuple
    right: tuple
    #: ``(lat, lon, alt)`` of every cut point, ``a`` first, ``b`` last,
    #: the hole crossings between in order along the cut.
    points: tuple
    #: ``(k, side) -> (lat, lon)`` of every copy.
    copies: dict
    #: The plan areas (m²) of the two halves.
    left_area: float
    right_area: float
    ccw: bool
    #: The keys of the holes the cut crossed (they become notches).
    crossed: tuple


def _orient(p, q, r) -> float:
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def ring_area(pts: _t.Sequence[tuple[float, float]]) -> float:
    """Signed plan area (positive counter-clockwise) of an open ring."""
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _inside(p, pts) -> bool:
    """Even-odd point in an open ring."""
    x, y = p
    hit = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _on_segment(p, q, r) -> bool:
    """r, collinear with p-q, lies on the closed segment p-q."""
    return (min(p[0], q[0]) <= r[0] <= max(p[0], q[0])
            and min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))


def _touch(p1, p2, q1, q2) -> bool:
    """The closed segments p1-p2 and q1-q2 share a point."""
    o1, o2 = _orient(p1, p2, q1), _orient(p1, p2, q2)
    o3, o4 = _orient(q1, q2, p1), _orient(q1, q2, p2)
    if ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0)) and \
            ((o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0)):
        return True
    return ((o1 == 0 and _on_segment(p1, p2, q1)) or (o2 == 0 and _on_segment(p1, p2, q2))
            or (o3 == 0 and _on_segment(q1, q2, p1)) or (o4 == 0 and _on_segment(q1, q2, p2)))


def cut(outer: _t.Sequence[int], holes: _t.Sequence[tuple[_t.Any, _t.Sequence[int]]],
        coords: _t.Mapping[int, tuple[float, float, float | None]],
        a: int, b: int, gap: float = GAP_M) -> Cut:
    """Slice the shape ``outer`` (an OPEN ring of node ids) with ``holes``
    (``(key, open ring)`` pairs; only the ones the cut crosses matter)
    along a -> b.  ``coords`` maps every id to ``(lat, lon, alt|None)``.
    Raises :class:`SliceRefused`."""
    n = len(outer)
    if outer.count(a) != 1 or outer.count(b) != 1:
        raise SliceRefused("Slice needs two nodes that are each on the shape's outline once.")
    ia, ib = outer.index(a), outer.index(b)
    if a == b or (ia - ib) % n in (1, n - 1):
        raise SliceRefused("Slice needs two nodes that are not neighbours on the shape.")
    lat0 = (coords[a][0] + coords[b][0]) / 2.0
    lon0 = (coords[a][1] + coords[b][1]) / 2.0
    m_lon = _M_PER_DEG_LAT * max(math.cos(math.radians(lat0)), 1.0e-6)

    def xy(nid: int) -> tuple[float, float]:
        lat, lon = coords[nid][0], coords[nid][1]
        return ((lon - lon0) * m_lon, (lat - lat0) * _M_PER_DEG_LAT)

    A, B = xy(a), xy(b)
    length = math.hypot(B[0] - A[0], B[1] - A[1])
    if length == 0.0:
        raise SliceRefused("The two nodes are at the same place.")
    area = ring_area([xy(i) for i in outer])
    if area == 0.0:
        raise SliceRefused("The shape has no area.")
    ccw = area > 0.0
    ring = list(outer) if ccw else list(reversed(outer))
    pts = [xy(i) for i in ring]
    m = len(ring)

    leaves = "The cut line leaves the shape."
    for i in range(m):
        u, v = ring[i], ring[(i + 1) % m]
        U, V = pts[i], pts[(i + 1) % m]
        ends = {u, v} & {a, b}
        if ends:
            x = a if a in ends else b
            X, Y = (U, V) if x == u else (V, U)
            far = B if x == a else A
            if _orient(A, B, Y) == 0.0 and \
                    (Y[0] - X[0]) * (far[0] - X[0]) + (Y[1] - X[1]) * (far[1] - X[1]) > 0.0:
                raise SliceRefused("The cut line runs along the shape's edge.")
        elif _touch(A, B, U, V):
            raise SliceRefused(leaves)
    if not _inside(((A[0] + B[0]) / 2.0, (A[1] + B[1]) / 2.0), pts):
        raise SliceRefused(leaves)

    # Hole crossings: (t along a->b, hole index, edge start, edge end, s).
    hole_rings: list[list[int]] = []
    crossings: list[tuple[float, int, int, int, float]] = []
    keys = []
    for key, hole in holes:
        h = list(hole)
        if len(h) < 3:
            continue
        hp = [xy(i) for i in h]
        if ring_area(hp) > 0.0:
            h.reverse()
            hp.reverse()
        found = []
        for i in range(len(h)):
            U, V = hp[i], hp[(i + 1) % len(h)]
            if not _touch(A, B, U, V):
                continue
            o1, o2 = _orient(A, B, U), _orient(A, B, V)
            o3, o4 = _orient(U, V, A), _orient(U, V, B)
            if not (o1 * o2 < 0.0 and o3 * o4 < 0.0):
                raise SliceRefused("The cut line passes through a corner of a hole; "
                                   "move a node slightly.")
            found.append((o3 / (o3 - o4), len(hole_rings), h[i], h[(i + 1) % len(h)],
                          o1 / (o1 - o2)))
        if not found:
            continue
        if a in h or b in h or not all(_inside(p, pts) for p in hp):
            raise SliceRefused("The cut line crosses a hole that is not inside this shape.")
        hole_rings.append(h)
        keys.append(key)
        crossings.extend(found)
    crossings.sort(key=lambda c: c[0])
    if len(crossings) % 2 or any(crossings[j][0] == crossings[j + 1][0]
                                 for j in range(len(crossings) - 1)) \
            or any(crossings[j][1] != crossings[j + 1][1] for j in range(0, len(crossings), 2)):
        raise SliceRefused("The cut line crosses holes that overlap.")

    # The cut points: a, the crossings in order, b.
    last = len(crossings) + 1
    points = [coords[a]]
    for _tc, _h, u, v, s in crossings:
        cu, cv = coords[u], coords[v]
        alt = None if cu[2] is None or cv[2] is None else cu[2] + s * (cv[2] - cu[2])
        points.append((cu[0] + s * (cv[0] - cu[0]), cu[1] + s * (cv[1] - cu[1]), alt))
    points.append(coords[b])

    # The directed boundary, one successor per entry.
    succ: dict = {}

    def link(src, dst) -> None:
        if src in succ:
            raise SliceRefused("The shape's outline and a hole share a node; "
                               "the cut cannot be traced.")
        succ[src] = dst

    out_of = {a: (0, "R"), b: (last, "L")}
    into = {a: (0, "L"), b: (last, "R")}
    for i in range(m):
        u, v = ring[i], ring[(i + 1) % m]
        link(out_of.get(u, u), into.get(v, v))

    def side(nid: int) -> str:
        return "L" if _orient(A, B, xy(nid)) > 0.0 else "R"

    on_edge = {(c[2], c[3]): k + 1 for k, c in enumerate(crossings)}
    for h in hole_rings:
        for i in range(len(h)):
            u, v = h[i], h[(i + 1) % len(h)]
            k = on_edge.get((u, v))
            if k is None:
                link(u, v)
            else:
                link(u, (k, side(u)))
                link((k, side(v)), v)
    for p in range(0, last, 2):
        link((p, "L"), (p + 1, "L"))
        link((p + 1, "R"), (p, "R"))

    cycles = []
    seen: set = set()
    for start in [(0, "L"), (0, "R"), *succ]:
        if start in seen:
            continue
        cyc = []
        x = start
        while x not in seen:
            seen.add(x)
            cyc.append(x)
            x = succ.get(x)
            if x is None:
                raise SliceRefused("The cut cannot be traced through this shape.")
        if x != start:
            raise SliceRefused("The cut cannot be traced through this shape.")
        cycles.append(tuple(cyc))
    if len(cycles) != 2 or (last, "L") not in cycles[0] or (last, "R") not in cycles[1]:
        raise SliceRefused("The cut would leave more than two pieces.")

    # The copies, half the gap either side of the cut line.
    nx, ny = -(B[1] - A[1]) / length, (B[0] - A[0]) / length
    half = gap / 2.0
    copies = {}
    for k, (lat, lon, _alt) in enumerate(points):
        for sd, sign in (("L", 1.0), ("R", -1.0)):
            copies[(k, sd)] = (lat + sign * half * ny / _M_PER_DEG_LAT,
                               lon + sign * half * nx / m_lon)

    def area_of(cyc) -> float:
        def at(x):
            if isinstance(x, tuple):
                lat, lon = copies[x]
                return ((lon - lon0) * m_lon, (lat - lat0) * _M_PER_DEG_LAT)
            return xy(x)
        return ring_area([at(x) for x in cyc])

    return Cut(cycles[0], cycles[1], tuple(points), copies,
               area_of(cycles[0]), area_of(cycles[1]), ccw, tuple(keys))
