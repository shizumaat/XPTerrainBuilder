"""THE OPEN MOUTH OF A WALL CORRIDOR, read against the WHOLE PACK and the
field (Law C's three general clauses; owner RULINGS 2026-10-05e / 05g /
05h; spec ``othh-terminal-ramps-spec.md`` §12h (1), (4), (5)).

A kerb-wall candidate that passed rules 1-6 of ``airport/wall_corridors``
is ADMITTED iff, in the object's SEATED frame (RULINGS 2026-09-10ad):

* **FIELD** — an open mouth stands within ``[tunnel] mouth_standoff_m`` of
  the CLASSIFIED COVER (:class:`WallField`, the cells' polygons; the cover
  half of §29 (1)'s mapped-tunnel test).  Without a field the clause is
  NOT READ and every line says so;
* **W1s** — it has an OPEN MOUTH: an end rule 4 left open whose mouth
  segment is covered under ``[cutout.wall_corridor] end_cap_cover_min`` by
  the geometry of ANY placement of the pack, in the BELOW-GRADE band (floor
  + ε .. ground − ε) and in the AT-GRADE band (ground + ε .. ground +
  ``min_headroom_m``) alike.  THE AT-GRADE CEILING IS MEASURED FROM THE
  GROUND at the mouth: a wall, door, fence, kerb, ground slab OR DECK
  standing across the mouth window under it closes the mouth — a roof under
  ``min_headroom_m`` over the ground at the mouth is a dock's cover, not a
  canopy; a face whose lowest rendered point stands at or above that
  ceiling is a canopy or deck overhead and closes nothing.  A corridor's
  OWN deck (rule 5, measured from the FLOOR) closes its mouth only if it
  reaches the mouth window under that ceiling — the arms of a corridor run
  OUT beyond the deck; a pit roofed to its mouth is a dock;
* **W3** — its arms run out from a BUILT STRUCTURE: rule 5 found a deck
  plate over the trench, or an above-grade WALL (faces reaching ``[basin]
  contact_band_m`` over the ground) covers ``end_cap_cover_min`` of an end.

ε is ``[rebake] plate_seat_min_delta_m``, the smallest step the engine
treats as visible; the window along the axis is ``[tunnel.object]
end_cap_open_m``.  No value lives here.

THE MOUTH SEGMENT M_k is rule 4's own ``end_line`` (``wall_family``): it
stands at the end of the pair's MIDLINE — for arms of unequal length half
the longer arm's run-on beyond the terminal STATION, where the records end
(spec §12h (3)).

:class:`MouthIndex` is the pack-wide reading (§12h (5)): ONE STRtree over
every placed, non-stock object's plan extent, built on the first mouth
query of a process and held on the ``WallReader``; a query walks only the
components of the placements it returns.  :func:`admit` is the three
clauses for one candidate, called from the ONE admission site
(``wall_family.read_family``) — nothing here is read anywhere else.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from ..law import Law
from ..model.frame import XY
from . import obj8 as _obj8
from .wall_geometry import (_plan_segments_indexed, _seat_base, _tri_normals_y,
                            _union_length)

__all__ = ["WallField", "FieldCover", "MouthIndex", "MouthEnd", "Closer", "MouthVerdict",
           "admit", "FIELD", "W1S", "W3"]

#: the clause that refused a candidate (:attr:`MouthVerdict.refused_by`)
FIELD, W1S, W3 = "FIELD", "W1s", "W3"


@_dc.dataclass(frozen=True)
class WallField:
    """THE FIELD a kerb corridor's mouth must stand on, as it crosses to a
    reader (and to a pool worker): the classified cover's polygons
    (``planar/structure_approach.cover_polygons``) and ``[tunnel]
    mouth_standoff_m``.  The tree over them is built per process
    (:class:`FieldCover`) — an STRtree does not cross a pool."""

    polys: tuple
    standoff_m: float


class FieldCover:
    """One process's index of a :class:`WallField`: is a point within the
    standoff of the cover, and how far the cover stands from it."""

    def __init__(self, field: WallField) -> None:
        self.standoff_m = float(field.standoff_m)
        self.cells = len(field.polys)
        self._polys = list(field.polys)
        self._tree = STRtree(self._polys) if self._polys else None

    def holds(self, xy: XY) -> bool:
        """The cover ⊕ ``mouth_standoff_m`` — the very predicate of
        ``structure_approach.FieldRegion.on_cover``."""
        return self.reaches(Point(xy))

    def distance_m(self, xy: XY) -> float:
        """Metres from ``xy`` to the nearest cover polygon (``inf`` with no
        cover) — the line's figure, never the verdict."""
        return self.distance_to(Point(xy))

    def reaches(self, geom, margin_m: float = 0.0) -> bool:
        """:meth:`holds` for a REGION: some cover polygon stands within the
        standoff + ``margin_m`` of ``geom`` (polygon distance) — so within
        the standoff of no point ``margin_m`` or less from it when this is
        False (the family gate of ``wall_family.read_family``, §12h (4)
        step 0)."""
        if self._tree is None:
            return False
        return len(self._tree.query(geom, predicate="dwithin",
                                    distance=self.standoff_m + margin_m)) > 0

    def distance_to(self, geom) -> float:
        """Metres from ``geom`` to the nearest cover polygon (``inf`` with
        no cover)."""
        if self._tree is None:
            return math.inf
        return float(self._polys[int(self._tree.nearest(geom))].distance(geom))


@_dc.dataclass(frozen=True)
class Closer:
    """The placement with the largest projected span across a mouth in one
    height band: its resource, its id, the share of the mouth's width it
    covers alone and its rendered z range there."""

    resource: str
    placement: str
    frac: float
    z_min: float
    z_max: float

    def text(self) -> str:
        return (f"{self.resource}@{self.placement} {self.frac:.2f} of W, "
                f"z {self.z_min:.2f}..{self.z_max:.2f}")


@_dc.dataclass(frozen=True)
class MouthEnd:
    """One end's mouth reading: the cover fraction of its segment in the
    below-grade band, in the at-grade band, and by the at-grade faces that
    are a WALL (W3); the closer per band; the wall's top over the ground."""

    width_m: float
    floor_z: float
    ground_z: float
    below: float = 0.0
    at_grade: float = 0.0
    wall: float = 0.0
    wall_top_m: float = 0.0
    closer_below: Closer | None = None
    closer_at_grade: Closer | None = None

    @property
    def closer(self) -> Closer | None:
        """The larger of the two bands' closers (the line names one)."""
        both = [c for c in (self.closer_below, self.closer_at_grade) if c is not None]
        return max(both, key=lambda c: c.frac, default=None)

    def text(self, k: int) -> str:
        c = self.closer
        return (f"end {k} below {self.below:.2f} / at-grade {self.at_grade:.2f} "
                f"(closer {'none' if c is None else c.text()})")


class MouthIndex:
    """THE PACK-WIDE MOUTH INDEX (§12h (5)): every placed, non-stock object
    of the pack by its plan extent.  :meth:`read` is one mouth query —
    rule 4's window (the flat buffer of the mouth segment by
    ``end_cap_open_m``) against every component meeting it in plan and in
    seated z, its triangles split into the two height bands and projected
    onto the segment.  Nothing is kept across queries but the tree."""

    def __init__(self, objects: _t.Sequence[_obj8.PlacedObject],
                 cache: _obj8.ResourceCache, dem_z, law: Law) -> None:
        st = law.tables.structures
        self.cache, self.dem_z = cache, dem_z
        self.tol = st.tunnel.object.end_cap_open_m
        self.normal_min = st.tunnel.object.plate_normal_y_min
        self.eps = st.rebake.plate_seat_min_delta_m
        self.ceiling = st.cutout.wall_corridor.min_headroom_m
        self.wall_band = st.basin.contact_band_m
        self.placed = [o for o in objects if o.resolved is not None
                       and o.plan_bbox is not None
                       and not _obj8.is_stock_library_resource(o.path)]
        self._tree = STRtree([o.plan_bbox for o in self.placed]) if self.placed else None
        self.queries = 0

    def _hits(self, o: _obj8.PlacedObject, window, bands: tuple) -> list[tuple]:
        """``(lo, hi, z_min, z_max, in below, in at-grade)`` on the mouth
        segment for every triangle of ``o`` meeting the window in a band."""
        (a, u, L), (b_lo, b_hi), (g_lo, g_hi) = bands
        cache = self.cache
        # the components' authored bounds FIRST: they are the one reading a
        # pool worker is seeded with, so a placement whose extent meets the
        # window but none of whose components does is never parsed here
        bounds = cache.component_bounds(o.resolved)
        if bounds.shape[0] == 0:
            return []
        mat = _obj8.placement_affine(o.xy, o.heading_deg)
        ca, cb, cd, ce, xoff, yoff = mat
        # the components' authored bounds in the frame (four corners each)
        cx = np.stack([ca * bounds[:, i] + cb * bounds[:, j] + xoff
                       for i in (0, 1) for j in (2, 3)], axis=1)
        cy = np.stack([cd * bounds[:, i] + ce * bounds[:, j] + yoff
                       for i in (0, 1) for j in (2, 3)], axis=1)
        minx, miny, maxx, maxy = window.bounds
        near = ((cx.min(1) <= maxx) & (cx.max(1) >= minx)
                & (cy.min(1) <= maxy) & (cy.max(1) >= miny))
        if not near.any():
            return []
        g = cache.geometry(o.resolved)
        comps = cache.components(o.resolved)
        if g is None or not comps:
            return []
        v = g.vertices
        out: list[tuple] = []
        for ci in np.nonzero(near)[0].tolist():
            if ci >= len(comps):
                break
            comp = comps[ci]
            base = _seat_base(o, _obj8._to_frame(o.xy, o.heading_deg, comp.cx, comp.cz),
                              self.dem_z)
            if base + comp.max_y < min(b_lo, g_lo) or base + comp.min_y > g_hi:
                continue
            ys = base + v[comp.tris][:, :, 1]
            zmn, zmx = ys.min(axis=1), ys.max(axis=1)
            in_b = (zmx >= b_lo) & (zmn <= b_hi) if b_hi > b_lo else np.zeros(len(zmn), bool)
            in_g = (zmx >= g_lo) & (zmn <= g_hi)
            keep = np.nonzero(in_b | in_g)[0]
            if not len(keep):
                continue
            tris = comp.tris[keep]
            vert = _tri_normals_y(v, tris) < self.normal_min
            geoms: list = []
            rows: list[int] = []
            if vert.any():
                vrows = np.nonzero(vert)[0]
                for seg, k in _plan_segments_indexed(v, tris[vert], mat):
                    geoms.append(seg)
                    rows.append(int(vrows[k]))
            if not vert.all():
                hrows = np.nonzero(~vert)[0]
                pts = v[tris[hrows]][:, :, [0, 2]]
                polys = shapely.polygons(np.stack(
                    [ca * pts[:, :, 0] + cb * pts[:, :, 1] + xoff,
                     cd * pts[:, :, 0] + ce * pts[:, :, 1] + yoff], axis=2))
                ok = shapely.is_valid(polys)
                geoms.extend(polys[ok].tolist())
                rows.extend(hrows[ok].tolist())
            if not geoms:
                continue
            cut = shapely.intersection(np.asarray(geoms, dtype=object), window)
            for x, k in zip(cut.tolist(), rows):
                if x.is_empty:
                    continue
                xy = shapely.get_coordinates(x)
                ts = (xy[:, 0] - a[0]) * u[0] + (xy[:, 1] - a[1]) * u[1]
                lo, hi = max(0.0, float(ts.min())), min(L, float(ts.max()))
                if hi > lo:
                    r = int(keep[k])
                    out.append((lo, hi, float(zmn[r]), float(zmx[r]),
                                bool(in_b[r]), bool(in_g[r])))
        return out

    def read(self, end: tuple[XY, XY], floor_z: float, ground_z: float) -> MouthEnd:
        """The mouth reading of one end (module doc): ``end`` its segment
        from the left inner face to the right, ``floor_z`` the seated floor
        at its station, ``ground_z`` the ground at its midpoint."""
        a, b = end
        L = math.dist(a, b)
        if self._tree is None or L < 1e-9:
            return MouthEnd(L, floor_z, ground_z)
        self.queries += 1
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        window = LineString([a, b]).buffer(self.tol, cap_style="flat")
        bands = ((a, u, L), (floor_z + self.eps, ground_z - self.eps),
                 (ground_z + self.eps, ground_z + self.ceiling))
        wall_z = ground_z + self.wall_band
        below: list[tuple[float, float]] = []
        grade: list[tuple[float, float]] = []
        wall: list[tuple[float, float]] = []
        wall_top = -math.inf
        closers: list[Closer | None] = [None, None]
        # placements in ``objects`` order: the reading is the same whatever
        # order the tree answers in
        for j in sorted(int(j) for j in self._tree.query(window, predicate="intersects")):
            o = self.placed[j]
            hits = self._hits(o, window, bands)
            for band, (ivals, col) in enumerate(((below, 4), (grade, 5))):
                mine = [h for h in hits if h[col]]
                if not mine:
                    continue
                ivals.extend((h[0], h[1]) for h in mine)
                frac = _union_length((h[0], h[1]) for h in mine) / L
                if closers[band] is None or frac > closers[band].frac:
                    closers[band] = Closer(os.path.basename(o.path), o.id, frac,
                                           min(h[2] for h in mine), max(h[3] for h in mine))
            tall = [h for h in hits if h[5] and h[3] >= wall_z]
            wall.extend((h[0], h[1]) for h in tall)
            wall_top = max([wall_top] + [h[3] for h in tall])
        return MouthEnd(L, floor_z, ground_z, _union_length(below) / L,
                        _union_length(grade) / L, _union_length(wall) / L,
                        wall_top - ground_z if wall else 0.0, closers[0], closers[1])


@_dc.dataclass
class MouthVerdict:
    """:func:`admit`'s answer for one candidate: the clause that refused it
    (``""`` = admitted), the COMPOSED-open ends (rule 4 ∧ W1s) the class
    reads, the line's text from the FIELD clause on, the refusal's own
    words (what ``stats.refused`` says after "REFUSED by <clause>") and the
    numbers for a ``narrow_cut`` row."""

    refused_by: str
    open_ks: list[int]
    text: str
    refusal: str
    ends: tuple[MouthEnd, MouthEnd] | None
    row: dict


def _nearest(cover: FieldCover, mids: _t.Sequence[XY], ks: _t.Sequence[int]
             ) -> tuple[int, float]:
    return min(((k, cover.distance_m(mids[k])) for k in ks), key=lambda kd: (kd[1], kd[0]))


def admit(cover: FieldCover | None, mouths: _t.Callable[[], MouthIndex],
          end_lines: _t.Sequence[tuple[XY, XY]], mouth_ks: _t.Sequence[int],
          floors: _t.Sequence[float], grounds: _t.Sequence[float],
          plate_witness: str | None, cover_min: float) -> MouthVerdict:
    """FIELD, W1s and W3 for one candidate, cheapest refusal first (§12h
    (4)): ``end_lines`` its two mouth segments, ``mouth_ks`` the ends rule 4
    left open (a garage's shallow end), ``floors`` / ``grounds`` the seated
    floor and the ground at each end, ``plate_witness`` rule 5's deck plate
    (``None`` = open air).  ``mouths`` hands the process's
    :class:`MouthIndex` — asked only when a candidate reaches the query."""
    mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in end_lines]
    row: dict = {"field": None, "field_m": None, "w1s": None, "w3": None}
    # FIELD-pre: one query per rule-4-open end, before any mouth is read
    if cover is None:
        field_txt = "FIELD not read (no cover handed)"
        on_field = list(mouth_ks)
    else:
        on_field = [k for k in mouth_ks if cover.holds(mids[k])]
        k_near, dist = _nearest(cover, mids, mouth_ks)
        row["field_m"] = round(dist, 1)
        row["field"] = bool(on_field)
        if not on_field:
            why = (f"nearest cover {dist:.1f} m from end {k_near} "
                   f"(> mouth_standoff_m {cover.standoff_m:g})")
            return MouthVerdict(FIELD, [], f"FIELD REFUSED — {why}", why, None, row)
        field_txt = f"FIELD end {k_near} {dist:.1f} m of cover"
    # THE MOUTH QUERY, once per end — BOTH ends: W3 reads the closed one too
    index = mouths()
    ends = (index.read(end_lines[0], floors[0], grounds[0]),
            index.read(end_lines[1], floors[1], grounds[1]))
    mouth_txt = f"{ends[0].text(0)}, {ends[1].text(1)}"
    row.update(
        mouth_below=[round(e.below, 3) for e in ends],
        mouth_at_grade=[round(e.at_grade, 3) for e in ends],
        mouth_wall=[round(e.wall, 3) for e in ends],
        mouth_closers=[{band: None if c is None else _dc.asdict(c)
                        for band, c in (("below", e.closer_below),
                                        ("at_grade", e.closer_at_grade))} for e in ends])
    # W1s: the composed-open ends
    open_ks = [k for k in mouth_ks
               if ends[k].below < cover_min and ends[k].at_grade < cover_min]
    row["w1s"] = bool(open_ks)
    if not open_ks:
        why = f"no open mouth: {mouth_txt}"
        return MouthVerdict(W1S, [], f"{field_txt}; W1s REFUSED — {why}", why, ends, row)
    # FIELD on the composed mouth (the FIELD-pre set is a superset)
    if cover is not None and not any(k in on_field for k in open_ks):
        k_near, dist = _nearest(cover, mids, open_ks)
        row["field"], row["field_m"] = False, round(dist, 1)
        why = (f"nearest cover {dist:.1f} m from open end {k_near} "
               f"(> mouth_standoff_m {cover.standoff_m:g})")
        return MouthVerdict(FIELD, [], f"MOUTH {mouth_txt}; FIELD REFUSED — {why}", why,
                            ends, row)
    head = (f"{field_txt}; MOUTH {mouth_txt}; W1s open end"
            f"{'s' if len(open_ks) > 1 else ''} {', '.join(str(k) for k in open_ks)}")
    # W3: a deck over the trench (free), else an above-grade wall at an end
    walled = [k for k in (0, 1) if ends[k].wall >= cover_min]
    row["w3"] = bool(plate_witness is not None or walled)
    if plate_witness is not None:
        w3 = f"W3 plate ({plate_witness})"
    elif walled:
        k = max(walled, key=lambda k: (ends[k].wall, -k))
        w3 = (f"W3 wall at end {k} {ends[k].wall:.2f} of W, z_max "
              f"{ends[k].wall_top_m:+.2f} m over ground")
    else:
        why = (f"open air, no wall at either end (at-grade wall cover "
               f"{ends[0].wall:.2f} / {ends[1].wall:.2f})")
        return MouthVerdict(W3, [], f"{head}; W3 REFUSED — {why}", why, ends, row)
    return MouthVerdict("", open_ks, f"{head}; {w3}", "", ends, row)
