"""Canonical-point registry for shared-vertex management.

The pavement builder constructs many shapes (rects, junctions, aprons,
boundary pieces) whose perimeters meet at intersection points.  Each
of those meeting points should be a SINGLE geometric vertex shared
by every adjacent shape — at exact floating-point equality, so that
``pav_union.difference(rects)`` and the OSM emitter's vertex
bucketing produce one node ID per real-world point.

Without a shared registry, each shape's corner is snapped
independently to ``pav.boundary`` and ends up at a slightly
different location than its neighbour's "same" corner.  The
sub-millimetre to multi-metre drift cascades downstream:
``buffer(0)`` validity repairs, sliver-corner removal, T-junction
splits, and merge-corner-junctions all exist as workarounds for
this single root cause.

A canonical-point registry replaces independent snapping with a
deterministic ``get_or_add`` lookup.  Every shape that needs a
corner near (x, y) queries the registry; if any prior shape has
already registered a canonical point within
``SHARED_VERTEX_TOL_M``, the same coordinates are returned.
Otherwise (x, y) becomes the new canonical point for that bucket.

Seeded with the input fixed-geometry vertices (apt.dat row-110
pavement polygon vertices + runway corners) so the canonical
set is anchored to real apt.dat data rather than to whatever
rect happened to register a point first.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union


__all__ = ["CanonicalPointRegistry", "snap_polygon_through_registry",
           "snap_polygon_parts_through_registry", "weld_layout_vertices",
           "settled_vertex_lattice", "snap_polygon_to_lattice",
           "add_polygon_to_lattice", "coarsen_to_lattice_spacing"]


_GEOM_EXC = (ValueError, TypeError,
             GEOSException, TopologicalError, IndexError)

# A cut vertex this close to a keep-out boundary IS on it — it was
# planted there by the ``.difference(cover)`` the cut was born with, and
# it must stay put (see :func:`snap_polygon_to_lattice`).
_KEEPOUT_EDGE_EPS_M = 1e-6


class CanonicalPointRegistry:
    """Spatial-index registry of canonical (x, y) points.

    All shape corners that should be SHARED must go through
    ``get_or_add`` so they pick up the same exact coordinates.

    ``tol_m`` is the bucket radius — points within ``tol_m`` of an
    existing entry resolve to that entry.  Default matches
    ``layout.SHARED_VERTEX_TOL_M`` so registry sharing aligns with
    the OSM emitter's vertex bucketing.
    """

    def __init__(self, tol_m: float = 0.5):
        self.tol_m = tol_m
        # Cell size = tol so neighbours-of-neighbours covers the
        # full lookup radius.
        self._cell = max(tol_m, 0.1)
        self._points: list[tuple[float, float]] = []
        # cell key (ix, iy) → list of indices into self._points
        self._index: dict = {}

    # ── public API ────────────────────────────────────────────────

    def seed(self, points) -> int:
        """Bulk-add anchor points (apt.dat row-110 + runway corners).

        Duplicates within ``tol_m`` collapse to a single entry.
        Returns the number of NEW canonical points added.
        """
        before = len(self._points)
        for p in points:
            self.get_or_add(float(p[0]), float(p[1]))
        return len(self._points) - before

    def get_or_add(self, x: float, y: float
                    ) -> tuple[float, float]:
        """Return the canonical (x, y) for the given input point.

        If an existing canonical point sits within ``tol_m`` of
        (x, y), return its coordinates exactly.  Otherwise insert
        (x, y) as a new canonical point and return it.
        """
        nearby = self._find_nearest(x, y, self.tol_m)
        if nearby is not None:
            return nearby
        return self._add(x, y)

    def add_exact(self, x: float, y: float) -> tuple[float, float]:
        """Register (x, y) as its OWN entry, never merging it into a
        neighbouring bucket.

        ``get_or_add`` implements node IDENTITY (points within ``tol_m``
        ARE one node, and the first one registered owns the coordinate).
        This is the other job: recording the vertices that actually
        EXIST, so a later query can snap a freshly-minted point onto the
        nearest REAL one instead of onto a bucket representative that
        may itself sit up to ``tol_m`` away in the other direction —
        which would move the new point by up to ``2·tol_m`` and bend the
        geometry it belongs to.  See :func:`settled_vertex_lattice`.
        """
        return self._add(x, y)

    def get(self, x: float, y: float) -> tuple[float, float] | None:
        """The READ-ONLY half of ``get_or_add``: the canonical (x, y)
        already registered for this point, or ``None`` when the bucket
        is unclaimed.  Never inserts.

        This is the query a MEASUREMENT INSTRUMENT must use (probe-spec
        §1x).  ``get_or_add`` is not merely "add if missing": because
        the registry snaps within ``tol_m``, an extra insertion changes
        which LATER points intern together, and the registry feeds the
        emit-side consensus — so a probe that interns anything moves
        the emitted surface (round 6: SPJC, +1 node, 86 altitudes).
        """
        return self._find_nearest(x, y, self.tol_m)

    def find_nearest(self, x: float, y: float,
                      max_d: float) -> tuple[float, float] | None:
        """Find the nearest canonical point within ``max_d`` of
        (x, y).  Does NOT add.  Returns None if no entry qualifies.
        """
        return self._find_nearest(x, y, max_d)

    @property
    def size(self) -> int:
        return len(self._points)

    def points(self) -> list[tuple[float, float]]:
        """Return a snapshot of every canonical point (insertion
        order).  Caller-owned list."""
        return list(self._points)

    # ── internals ─────────────────────────────────────────────────

    def _cell_key(self, x: float, y: float) -> tuple[int, int]:
        return (int(math.floor(x / self._cell)),
                int(math.floor(y / self._cell)))

    def _add(self, x: float, y: float) -> tuple[float, float]:
        idx = len(self._points)
        coords = (float(x), float(y))
        self._points.append(coords)
        self._index.setdefault(
            self._cell_key(x, y), []).append(idx)
        return coords

    def _find_nearest(self, x: float, y: float,
                       max_d: float) -> tuple[float, float] | None:
        # Number of cells in each direction we have to scan to cover
        # the lookup radius.  +1 to be safe at cell boundaries.
        n_cells = int(math.ceil(max_d / self._cell)) + 1
        cx, cy = self._cell_key(x, y)
        best: tuple[float, float] | None = None
        best_d = max_d
        for dx in range(-n_cells, n_cells + 1):
            for dy in range(-n_cells, n_cells + 1):
                key = (cx + dx, cy + dy)
                bucket = self._index.get(key)
                if not bucket:
                    continue
                for idx in bucket:
                    px, py = self._points[idx]
                    d = math.hypot(px - x, py - y)
                    if d < best_d:
                        best_d = d
                        best = (px, py)
        return best


def snap_polygon_through_registry(
        poly: Polygon | None,
        registry: CanonicalPointRegistry | None,
        *,
        readonly: bool = False,
) -> Polygon | None:
    """Route every vertex of ``poly``'s exterior + interior rings
    through ``registry.get_or_add`` so drift introduced by
    ``buffer(0)`` / ``unary_union`` / ``simplify`` resolves to
    canonical (x, y) coordinates shared with adjacent shapes.

    ``readonly=True`` resolves through ``registry.get`` instead — the
    query a MEASUREMENT INSTRUMENT must use (probe-spec §1x: an
    instrument that interns anything moves the emitted surface).  A
    vertex whose bucket is unclaimed keeps its own coordinates,
    exactly what ``get_or_add`` would have returned for it at emit.

    Returns the snapped polygon (a new ``Polygon`` if any vertex
    moved, the input otherwise), or ``None`` if the snap produces
    a degenerate shape.  If either input is ``None`` / empty, the
    input is returned unchanged.
    """
    parts = snap_polygon_parts_through_registry(
        poly, registry, readonly=readonly)
    if poly is None or poly.is_empty:
        return poly
    if not parts:
        return None
    return max(parts, key=lambda g: g.area)


def snap_polygon_parts_through_registry(
        poly: Polygon | None,
        registry: CanonicalPointRegistry | None,
        *,
        readonly: bool = False,
) -> list:
    """Parts-preserving variant of ``snap_polygon_through_registry``:
    when the snap pinches the ring into a self-intersection and the
    ``buffer(0)`` validity repair splits it into a MultiPolygon, return
    EVERY Polygon part instead of silently keeping only the largest
    (the discarded siblings are real pavement — at KGYR a 26 000 m²
    junction piece vanished this way, leaving taxi rect ends in
    mid-air over covered source pavement).  Returns ``[poly]``
    unchanged when there is nothing to snap, ``[]`` when the snap
    degenerates.

    ``readonly=True``: see :func:`snap_polygon_through_registry` —
    resolve via ``registry.get`` (never inserts), unclaimed vertices
    keep their own coordinates."""
    if registry is None or poly is None or poly.is_empty:
        return [] if poly is None or poly.is_empty else [poly]

    if readonly:
        def _lookup(x: float, y: float) -> tuple[float, float]:
            cp = registry.get(x, y)
            return cp if cp is not None else (x, y)
    else:
        _lookup = registry.get_or_add

    def _snap_ring(coords):
        snapped = []
        for x, y in coords:
            cp = _lookup(float(x), float(y))
            snapped.append(cp)
        return snapped

    try:
        ext = _snap_ring(poly.exterior.coords)
        if len(set(ext)) < 3:
            return []
        interiors = []
        for ring in poly.interiors:
            ri = _snap_ring(ring.coords)
            if len(set(ri)) < 3:
                continue
            interiors.append(ri)
        snapped_poly = Polygon(ext, interiors)
        if not snapped_poly.is_valid:
            snapped_poly = snapped_poly.buffer(0)
            if (snapped_poly.is_empty
                    or snapped_poly.geom_type not in (
                        "Polygon", "MultiPolygon")):
                return []
        if snapped_poly.geom_type == "MultiPolygon":
            return [g for g in snapped_poly.geoms
                    if g.geom_type == "Polygon" and not g.is_empty]
        return [snapped_poly]
    except _GEOM_EXC:
        return []


def settled_vertex_lattice(layout, roles=None,
                           tol_m: float = 0.5) -> "CanonicalPointRegistry":
    """The SETTLED VERTEX LATTICE: every ring vertex the layout's shapes
    currently carry, registered EXACTLY (no merging), for use as a snap
    target by a pass that mints geometry afterwards.

    THE LAW (cycle-5, ``docs/specs/cycle5-node-identity-spec.md``): a
    canonical solve node has exactly ONE plan coordinate.  The pre-solve
    settle (``pipeline._unify_airside_geometry``) fixes the airside node
    set; a construction that runs after it and mints a vertex within the
    canonical weld tolerance of a settled one has created a node with
    two ring coordinates — the solver binds the strictest law at the
    shared node while the coordinate-keyed validator reads each ring's
    own law, and the two disagree on the same pair.

    The answer is to cut ON the lattice, never to weld after cutting:
    snapping the CUT GEOMETRY before the boolean difference makes the
    resulting boundary shared by construction, where welding the pieces
    afterwards moves them independently and tears the partition
    (measured: 0.1384 m² of CYXY apron∩apron self-overlap).

    ``roles`` restricts which shapes contribute (``None`` ⇒ every shape
    with a simple polygon).  Vertices go in through
    :meth:`CanonicalPointRegistry.add_exact`, so a query returns a
    coordinate that a shape genuinely has.
    """
    reg = CanonicalPointRegistry(tol_m=tol_m)
    for s in getattr(layout, "shapes", ()):
        if roles is not None and getattr(s, "role", None) not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if (poly is None or poly.is_empty
                or poly.geom_type != "Polygon"):
            continue
        try:
            for (x, y) in poly.exterior.coords:
                reg.add_exact(float(x), float(y))
            for ring in poly.interiors:
                for (x, y) in ring.coords:
                    reg.add_exact(float(x), float(y))
        except _GEOM_EXC:                                  # pragma: no cover
            continue
    return reg


def add_polygon_to_lattice(poly, lattice) -> None:
    """Register ``poly``'s vertices into ``lattice`` so a LATER cut in the
    same pass snaps to the pieces this one already minted."""
    if lattice is None or poly is None or poly.is_empty:
        return
    try:
        rings = [poly.exterior] + list(poly.interiors)
    except _GEOM_EXC:                                      # pragma: no cover
        return
    for ring in rings:
        for (x, y) in ring.coords:
            lattice.add_exact(float(x), float(y))


def coarsen_to_lattice_spacing(geom, tol_m: float = 0.5):
    """Rebuild ``geom`` so that NO TWO of its boundary vertices are closer
    together than ``tol_m``.  Returns the rebuilt geometry, or ``None``
    if it degenerates.

    The guarantee is structural, not statistical: every vertex is
    interned through ONE :class:`CanonicalPointRegistry` at ``tol_m``,
    and that registry never stores two entries within ``tol_m`` of each
    other — so the retained vertex set is ``tol_m``-separated by
    construction, whatever the input looked like.  One registry for all
    rings and all parts, so a boundary two parts share is coarsened the
    same way on both sides.

    THIS IS THE FIX FOR GEOMETRY THAT IS USED AS A CUTTER (cycle-5 node
    identity, ``docs/specs/cycle5-node-identity-spec.md``): a cutter
    whose own boundary carries vertex pairs closer than the weld
    tolerance hands every one of them to BOTH sides of the cut, and the
    canonical registry then interns each pair onto ONE node with two
    ring coordinates.  A ``buffer()`` is exactly such a cutter — its arc
    vertices are spaced at roughly the weld tolerance.

    NOTE the direction of movement is unconstrained: a vertex may move
    up to ``tol_m`` either way, so a caller that needs the result to
    CONTAIN the input must grow it first and then verify (see
    ``apron_terrace.lattice_coarse_cover``).
    """
    if geom is None or geom.is_empty:
        return geom
    reg = CanonicalPointRegistry(tol_m=tol_m)

    def _ring(coords):
        out: list = []
        for (x, y) in coords:
            p = reg.get_or_add(float(x), float(y))
            if out and out[-1] == p:
                continue
            out.append(p)
        while len(out) > 1 and out[0] == out[-1]:
            out.pop()
        return out

    parts = ([geom] if geom.geom_type == "Polygon"
             else [g for g in getattr(geom, "geoms", ())
                   if g.geom_type == "Polygon" and not g.is_empty])
    if not parts:
        return None
    rebuilt = []
    try:
        for p in parts:
            ext = _ring(p.exterior.coords)
            if len(ext) < 3:
                continue
            holes = []
            for r in p.interiors:
                ri = _ring(r.coords)
                if len(ri) >= 3:
                    holes.append(ri)
            q = Polygon(ext, holes)
            if not q.is_valid:
                q = q.buffer(0)
            if q.is_empty:
                continue
            rebuilt.append(q)
        if not rebuilt:
            return None
        out = rebuilt[0] if len(rebuilt) == 1 else unary_union(rebuilt)
        return None if out.is_empty else out
    except _GEOM_EXC:
        return None


def snap_polygon_to_lattice(poly, lattice, tol_m: float = 0.5, avoid=None):
    """Make ``poly`` LATTICE-CLEAN: every vertex is either a SETTLED
    vertex or a fresh point no closer than ``tol_m`` to any other vertex
    of the result.  Returns ``(cleaned_polygon_or_None, n_moved)``.

    Used on CUT GEOMETRY before the boolean difference that applies it
    (see :func:`settled_vertex_lattice` for why).  Two jobs, and BOTH are
    required — measured at CYXY, the first alone leaves 884 of the 884:

    1. SNAP TO THE SETTLED SET.  A cut vertex within ``tol_m`` of a
       settled vertex IS that node; moved onto it, the cut inherits the
       existing geometry's vertex instead of minting a second coordinate
       for the same node.
    2. COLLAPSE THE CUT'S OWN NEAR-TWINS.  A fan zone is a union of
       overlapping buffered hulls and a terrace band a station row, so
       the cut arrives carrying vertex pairs of its OWN that are closer
       together than the weld tolerance.  The difference hands every one
       of them to BOTH the ramp piece and the remainder panel, and the
       canonical registry then interns each pair onto ONE node: the
       solver prices the pair from the node (strictest cap wins — the
       1 % panel) while the coordinate-keyed validator reads each ring's
       own coordinates (5 % on the ramp's key).  That is the whole
       193-edge lockstep failure.  Measured at CYXY: aprons carry ZERO
       such pairs before the cut and 884 after it, so they are minted
       here, not inherited.

    Interning through a fresh registry is exactly the identity the
    canonical registry would impose anyway — the cut is being born, has
    no altitudes and no node identity yet, so collapsing costs nothing
    and no sub-tolerance distinction was ever load-bearing.

    ``avoid`` — a KEEP-OUT geometry (the aircraft-movement corridor
    cover).  Node identity never outranks a structural law: the owner's
    fan-ramp ruling forbids a ramp piece touching a movement surface
    outright.  THE RULE IS TO FREEZE, NOT TO REPAIR: every vertex
    already lying ON the keep-out boundary keeps its exact coordinate
    and owns its bucket, so the linework the cut shares with the
    corridor is reproduced identically and cannot move.  The two
    repair-shaped alternatives were both measured and both fail — a
    corridor cover is a BUFFER, its boundary arc vertices are spaced at
    about the weld tolerance, and a collapse there chords across the
    arc INTO the corridor:

    * decline the component when the result overlaps — the pieces are
      cut flush against the corridor, so any sub-millimetre move trips
      it: 6 of 6 components declined, CYXY back to 198 mismatches;
    * re-clip the result with ``.difference(cover)`` — the clip re-nodes
      the whole corridor boundary and hands every arc vertex back:
      830 of the 884 near-duplicate pairs returned, CYXY 203.

    ``None`` when the result degenerates, is not a single simple
    polygon, or still enters ``avoid``; the caller then keeps its
    unsnapped input rather than losing the cut.
    """
    if lattice is None or poly is None or poly.is_empty:
        return poly, 0
    if poly.geom_type != "Polygon":
        return None, 0
    moved = 0
    strict = None
    edge = None
    if avoid is not None:
        try:
            if avoid.is_empty:
                avoid = None
            else:
                # An epsilon shrink so ABUTTING the corridor — which
                # every zone does — is not read as entering it; the same
                # predicate the fan-ramp law's twin uses.
                strict = avoid.buffer(-1e-9)
                edge = avoid.boundary
                if poly.intersects(strict):
                    # Already overlapping: this pass cannot tell "the
                    # snap did it" from "it was already so".
                    avoid = strict = edge = None
        except _GEOM_EXC:                                  # pragma: no cover
            avoid = strict = edge = None

    def _frozen(px, py) -> bool:
        """On the keep-out boundary ⇒ immovable."""
        if edge is None:
            return False
        try:
            return edge.distance(Point(px, py)) <= _KEEPOUT_EDGE_EPS_M
        except _GEOM_EXC:                                  # pragma: no cover
            return False

    own = CanonicalPointRegistry(tol_m=tol_m)
    try:
        all_rings = [list(poly.exterior.coords)] + [
            list(r.coords) for r in poly.interiors]
    except _GEOM_EXC:                                      # pragma: no cover
        return None, 0
    # PASS 0 — the FROZEN vertices (on the keep-out boundary) claim
    # their buckets before anything else: they cannot move, so nothing
    # may take a bucket out from under them.
    frozen = set()
    if edge is not None:
        for coords in all_rings:
            for (x, y) in coords:
                fx, fy = float(x), float(y)
                if _frozen(fx, fy):
                    frozen.add((fx, fy))
        for pt in frozen:
            own.get_or_add(*pt)

    # PASS 1 — then the SETTLED points this cut touches, so a fresh cut
    # vertex can never own a bucket a settled vertex belongs in (order
    # would otherwise decide, and the cut would be born beside the
    # lattice instead of on it).
    for coords in all_rings:
        for (x, y) in coords:
            cp = lattice.find_nearest(float(x), float(y), tol_m)
            if cp is not None:
                own.get_or_add(*cp)

    # PASS 2 — every vertex resolves to its bucket's owner.
    def _snap_ring(coords):
        nonlocal moved
        out: list = []
        for (x, y) in coords:
            fx, fy = float(x), float(y)
            if (fx, fy) in frozen:
                if not out or out[-1] != (fx, fy):
                    out.append((fx, fy))
                continue
            cp = lattice.find_nearest(fx, fy, tol_m)
            nx, ny = own.get_or_add(*(cp if cp is not None else (fx, fy)))
            if (nx, ny) != (fx, fy):
                moved += 1
            fx, fy = nx, ny
            if out and out[-1] == (fx, fy):
                continue          # collapsed onto its predecessor
            out.append((fx, fy))
        while len(out) > 1 and out[0] == out[-1]:
            out.pop()
        return out

    try:
        ext = _snap_ring(poly.exterior.coords)
        if len(ext) < 3:
            return None, moved
        interiors = []
        for ring in poly.interiors:
            ri = _snap_ring(ring.coords)
            if len(ri) >= 3:
                interiors.append(ri)
        snapped = Polygon(ext, interiors)
        if not snapped.is_valid:
            snapped = snapped.buffer(0)
        if snapped.is_empty:
            return None, moved
        if snapped.geom_type == "MultiPolygon":
            # The ring came back within ``tol_m`` of itself and the
            # collapse pinched it in two.  DECLINE rather than keep the
            # largest part: silently dropping the smaller one loses
            # pavement, and the caller's fallback (the unsnapped cut) is
            # strictly better than a shrunken one.
            return None, moved
        if snapped.geom_type != "Polygon" or snapped.is_empty:
            return None, moved
        if strict is not None and snapped.intersects(strict):
            # The frozen boundary should make this unreachable; if some
            # other edge still swept in, the unsnapped cut is lawful and
            # this one is not.
            return None, moved
        return snapped, moved
    except _GEOM_EXC:
        return None, moved


def weld_layout_vertices(layout, roles, tol_m: float = 0.5) -> int:
    """Weld near-coincident vertices across the given shape ``roles`` to
    a single shared coordinate.

    Adjacent shapes (a taxi rect and the junction carved beside it) are
    snapped to ``pav.boundary`` at different pipeline stages, and
    post-emit passes (conformance T-junction insertion, absorption clips)
    add fresh vertices that were never routed through the build-time
    registry.  Two such "same point" vertices then sit up to ``tol_m``
    apart, and their edges cross by a sub-tol sliver — the residue model
    is seamless as a set operation, but the per-shape vertex coordinates
    drift.  This pass re-welds them.

    A FRESH registry is built (so it can't carry stale near-duplicate
    canonical points from earlier stages): pass 1 registers every
    target-shape vertex — the first occurrence within ``tol_m`` wins, so
    a rect corner and the junction vertex beside it collapse to ONE
    canonical coordinate.  Pass 2 snaps each shape's vertices to those
    welded points.

    Only snaps that PRESERVE a shape's vertex count are applied, so any
    ``node_altitudes`` list stays index-aligned with the ring (snapping
    moves coordinates in place; it never reorders or drops a vertex).

    Returns the number of shapes modified.
    """
    reg = CanonicalPointRegistry(tol_m=tol_m)
    targets = [s for s in layout.shapes
               if s.role in roles and s.polygon is not None
               and not s.polygon.is_empty
               and s.polygon.geom_type == "Polygon"]
    # Pass 1: register every vertex (welds near-coincident to first seen).
    for s in targets:
        try:
            for (x, y) in s.polygon.exterior.coords:
                reg.get_or_add(float(x), float(y))
            for ring in s.polygon.interiors:
                for (x, y) in ring.coords:
                    reg.get_or_add(float(x), float(y))
        except _GEOM_EXC:
            continue
    # Pass 2: snap each shape's vertices to the welded canonical points.
    modified = 0
    for s in targets:
        try:
            n_before = len(s.polygon.exterior.coords)
            snapped = snap_polygon_through_registry(s.polygon, reg)
        except _GEOM_EXC:
            continue
        if (snapped is None or snapped.is_empty
                or snapped.geom_type != "Polygon"):
            continue
        # Vertex collapsed (two ring points welded together) — skip so
        # node_altitudes alignment is preserved.
        if len(snapped.exterior.coords) != n_before:
            continue
        if snapped.equals(s.polygon):
            continue
        s.polygon = snapped
        modified += 1
    return modified
