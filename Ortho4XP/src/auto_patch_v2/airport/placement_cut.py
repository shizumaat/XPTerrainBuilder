"""THE CUTS (spec ``object-placement-spec.md`` §10, §16 (2); owner
RULINGS 2026-09-11f (2) / 11ai).

Where ``placement_plan`` decides what a body IS and where it stands, this
module divides one: the SEGMENT cut of a line object (a 2 km fence
authored as one component becomes stations of ``[placement]
line_segment_m``, each on its own mid-foot) and §16 (2)'s TERRAIN cut
(the parts, else the triangles, of a body grouped by the ground under
them — a rigid body is never wider than the terrain it can stand on).

Also the authored-frame plan map both cuts read, and the
restore-before-read resolver every cut opens its file through.

NO LAW CONSTANT LIVES HERE: ``line_segment_m``, ``split_tol_m`` and the
station cap are passed in.  ``GROUND_CELL_M`` is a SAMPLING RESOLUTION,
documented where it stands.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os as _os
import typing as _t

from ..model.rebake import Member, Part, Unit
from . import anchor_rule as _ar
from . import basin_ring as _br
from . import line_object as _lo
from . import placement_atom as _atom
from . import placement_carrier as _pc

__all__ = ["authored_latlon", "segment_anchor", "pristine_path",
           "GROUND_CELL_M", "GEOM_CELL_M", "GEOM_PTS_MAX", "thin_points",
           "_Raw"]

from .placement_carrier import is_elevated            # noqa: E402  (§13)
# §16b's WRITTEN-GEOMETRY reading lives next door (the 1,000-line law);
# every caller and every twin reads it as this module's.
from .placement_geom import (GEOM_CELL_M, GEOM_PTS_MAX,  # noqa: E402,F401
                             _geom_ground, _geom_span, surface_many,
                             thin_points)

# ── THE LINE SEGMENT (owner RULINGS 2026-09-11f (2); spec §10) ───────────

def authored_latlon(x: float, z: float, placement_lat: float,
                    placement_lon: float, heading_deg: float
                    ) -> tuple[float, float]:
    """The inverse of :func:`authored_offset`'s plan half: the authored
    point ``(x, z)`` of a placement as ``(lat, lon)``.

    The map ``(e, n) -> (x, z)`` of ``authored_offset`` is a REFLECTION
    (its determinant is −1), so it is its own inverse — the same two
    lines, read the other way."""
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    e = x * c - z * s
    n = -x * s - z * c
    ml, mo = _ar._m_per_deg(placement_lat)
    return (placement_lat + n / ml, placement_lon + e / mo)


class _LineCutter:
    """The SEGMENT CUT of one member (11f (2)).

    A LINE OBJECT authored as one component — LEMD's ``Munoza-LEMDzaun``
    is the whole 2 km perimeter fence in ONE component — has exactly one
    body, so the body split cannot touch it and the placement is kept
    whole on a single anchor: the far end of the fence floats by whatever
    the terrain does over the run (14.68 m, the airport's worst row,
    11f).  10bb's drape answered this with a per-station VERTEX REWRITE,
    which dies with the seat.  The placement law's own answer is to cut
    the fence into SEGMENTS — triangles assigned by centroid to stations
    of ``[placement] line_segment_m`` — and give each segment its own
    file, its own placement and its own MID-FOOT anchor (§6's line row).

    The verdict is 10bb's, unchanged and per RESOURCE: every genuine
    component of the file line-shaped (per component the reader swallows
    building walls — 4,207 of LEMD's 9,423 ground parts).  The plan's
    PARTS are that genuine set, so the test runs over them and needs no
    thickness constant of its own.  Nothing is parsed until a member
    actually spans more than one segment."""

    def __init__(self, m: Member, segment_m: float, stations_max: int,
                 foot_band_m: float, ratio: float, max_h: float,
                 lat: float, lon: float, contact_eps_m: float = 0.0,
                 contact_pairs: _t.Sequence[tuple[int, int]] = (),
                 rigid_reach_m: float = 0.0,
                 rigid_span_max_m: float = 0.0) -> None:
        self.m = m
        self.segment_m = segment_m
        self.stations_max = stations_max
        self.foot_band_m = foot_band_m
        self.law = _lo.LineLaw(ratio, max_h)
        self.lat = lat
        self.lon = lon
        self._geom: _t.Any = False        # False = not parsed yet
        self._comps: list = []
        self._is_line: bool | None = None
        #: §16c (1): authored triangle -> component index, built once
        #: (packed keys, sorted, for a vectorised lookup)
        self._tri_keys: _t.Any = None
        self._tri_ids: _t.Any = None
        self._tri_base: _t.Any = 1
        #: §16c (6): components of ONE resource that TOUCH are one atom
        self.contact_eps_m = contact_eps_m
        self.contact_pairs = tuple(contact_pairs)
        #: §16c (7): SOLID components within this CHAIN into one rigid
        #: cluster (line classes excluded — §10 cuts those on purpose)
        self.rigid_reach_m = rigid_reach_m
        #: §16c (8): a rigid cluster never grows wider than this in plan
        self.rigid_span_max_m = rigid_span_max_m
        self._clusters: _t.Any = None

    @property
    def armed(self) -> bool:
        return (self.segment_m > 0.0 and self.stations_max > 0
                and self.law.line_object_ratio > 0.0)

    def _read(self) -> bool:
        if self._geom is False:
            from . import obj8 as _obj8
            try:
                self._geom = _obj8.parse_obj8(pristine_path(self.m))
            except (OSError, ValueError):
                self._geom = None
            self._comps = (_obj8.solid_components(self._geom)
                           if self._geom is not None else [])
        return self._geom is not None and bool(self._comps)

    def comp_of(self, tris) -> "list[int]":
        """§16c (1): the COMPONENT of each triangle (``placement_atom``)."""
        return _atom.comp_of(self, tris)

    def comp_cluster(self) -> "list[int]":
        """§16c (6)/(8): the RIGID CLUSTER of each component
        (``placement_atom.comp_cluster`` — the law and its reading)."""
        return _atom.comp_cluster(self)

    def _comp_blocks(self, tris) -> "list[list[int]]":
        """§16c (1): ``tris`` grouped by the ATOM each belongs to."""
        return _atom.comp_blocks(self, tris)

    def is_line_object(self) -> bool:
        """10bb's RESOURCE verdict over the plan's own genuine set."""
        if self._is_line is None:
            self._is_line = False
            if self._read() and self.m.parts:
                self._is_line = all(
                    0 <= p.comp < len(self._comps)
                    and _lo.is_line_shaped(self._geom, self._comps[p.comp], self.law)
                    for p in self.m.parts)
        return self._is_line

    def segments(self, parts: _t.Sequence[Part]
                 ) -> list[tuple[tuple[tuple[int, int, int], ...],
                                 tuple[tuple[float, float, float], ...]]]:
        """One body's ``(triangles, feet)`` per segment, or ``[]`` when
        the body is not a line object or is shorter than one segment."""
        if not self.armed or not parts:
            return []
        span = _plan_span_m(parts)
        if span <= self.segment_m or not self.is_line_object():
            return []
        import numpy as np
        tris = [self._comps[p.comp].tris for p in parts
                if 0 <= p.comp < len(self._comps)]
        if not tris:
            return []
        segs = _lo.segment_by_station(self._geom, np.concatenate(tris),
                                      self.segment_m, self.stations_max)
        if len(segs) < 2:
            return []
        v = self._geom.vertices
        out = []
        for sg in segs:
            ids = np.unique(np.asarray(sg.tris).reshape(-1))
            ys = v[ids, 1]
            # the segment's GROUND CONTACTS, the plan's own band, thinned
            # by the same farthest-point walk so one segment's feet never
            # outweigh a building's in the coarsening's seniority
            foot = ids[ys <= float(ys.min()) + self.foot_band_m]
            if foot.shape[0] == 0:
                foot = ids[:1]
            if foot.shape[0] > self.stations_max:
                pick = _lo.farthest_point_stations(
                    v[foot][:, [0, 2]], self.stations_max)
                foot = foot[pick]
            feet = tuple(authored_latlon(float(v[i, 0]), float(v[i, 2]),
                                         self.lat, self.lon, self.m.heading_deg)
                         + (float(v[i, 1]),) for i in foot.tolist())
            out.append((tuple(tuple(int(q) for q in row)
                              for row in np.asarray(sg.tris).tolist()), feet))
        return out


    def terrain_groups(self, parts: _t.Sequence[Part], surface: _ar.Surface,
                       tol_m: float, cap: int, *, by_ground: bool = False,
                       tris_in: _t.Sequence[_t.Sequence[int]] = ()
                       ) -> list[tuple[tuple[tuple[int, int, int], ...],
                                       tuple[tuple[float, float, float], ...]]]:
        """§16 (2) BY TRIANGLE: one body's ``(triangles, feet)`` per TERRAIN
        GROUP — the cut for a body the PART cut cannot touch.

        LEMD's ``Terminal4_green-TEJ3`` is a roof-panel resource scattered
        over 1 x 2 km of the terminal authored as ONE welded component:
        one part, one body, one zero, and every panel away from the anchor
        floats or buries by whatever the ground does over two kilometres
        (11ai (A): its own ground spans 5.02 m).  The part cut has nothing
        to divide.  So the triangles themselves are grouped by the GROUND
        UNDER THEM — the intended zero of a triangle is the design surface
        under its plan centroid minus its own lowest ``y`` — by §9's own
        greedy rule at ``tol_m``, capped at ``cap`` groups (``[rebake]
        line_object_stations_max``, the same cap the segment cut takes).

        §16b (1): ``by_ground`` groups by the DESIGN SURFACE under the
        triangle instead of by its intended zero.  The zero reading asks
        "where would this triangle's own lowest vertex have to sit" and
        folds the object's authored relief into the terrain's — a roof
        with 3 m of authored fall over ground that never moves comes out
        in three groups, and a plate over 3 m of fall comes out in one.
        What the bar reads (and what "the terrain it can stand on"
        means) is the GROUND, so the cut that has to satisfy it reads
        the ground.

        Returns ``[]`` when the body reads one terrain group, when the
        surface reads nowhere, or when the file cannot be parsed."""
        if tol_m <= 0.0 or cap <= 0 or not parts or not self._read():
            return []
        import numpy as np
        if len(tris_in):
            tris = np.asarray(tris_in, dtype=np.int64)
        else:
            tri_list = [self._comps[p.comp].tris for p in parts
                        if 0 <= p.comp < len(self._comps)]
            if not tri_list:
                return []
            tris = np.concatenate(tri_list)
        if tris.size == 0:
            return []
        # §16b (1): IN GROUND MODE THE RADIUS IS HALF THE TOLERANCE.  The
        # greedy walk admits a triangle within ``radius`` of the group's
        # founding level, so a group's own SPAN is twice that — and the
        # bar the cut has to satisfy is the span (0.3 m), not the radius.
        radius = 0.5 * tol_m if by_ground else tol_m
        v = self._geom.vertices
        xs = v[tris, 0].mean(axis=1)
        zs = v[tris, 2].mean(axis=1)
        ys = v[tris, 1].min(axis=1)
        ml, mo = _ar._m_per_deg(self.lat)
        # THE GROUND IS SAMPLED PER CELL, not per triangle.  A roof of
        # 40,000 panels asks the design surface 40,000 times and the
        # LEMD plan stage grew 6.5 s for it; the surface is a graded mesh
        # whose faces are metres across, so one reading per
        # ``GROUND_CELL_M`` of plan is the same reading.  This is a
        # sampling resolution, not a law: it cannot move a triangle
        # across a level except within one cell of a boundary.
        cell: dict[tuple[int, int], "float | None"] = {}

        def _ground(la: float, lo: float) -> "float | None":
            k = (int(round(la * ml / GROUND_CELL_M)),
                 int(round(lo * mo / GROUND_CELL_M)))
            if k not in cell:
                cell[k] = surface(la, lo)
            return cell[k]

        # §16c (1): THE ATOM IS THE COMPONENT, not the triangle.  A
        # boundary drawn between two triangles of ONE welded solid writes
        # its halves at two zeros — the torn vault, the torn deck slab,
        # the torn canopy of the owner's 1.0.320 read (12d).  So the
        # walk below places WHOLE components, each keyed by the design
        # surface under its OWN geometry (the median of its triangles'
        # readings, so one stray panel cannot carry a hangar), and a
        # component wider than its terrain stays whole.
        atoms = self._comp_blocks(tris)
        keys: list["float | None"] = []
        lows: list[float] = []
        for blk in atoms:
            vals: list[float] = []
            for i in blk:
                la, lo = authored_latlon(float(xs[i]), float(zs[i]), self.lat,
                                         self.lon, self.m.heading_deg)
                z = _ground(la, lo)
                if z is not None:
                    vals.append(float(z) - (0.0 if by_ground else float(ys[i])))
            keys.append(None if not vals else
                        float(sorted(vals)[len(vals) // 2]))
            lows.append(min(float(ys[i]) for i in blk))
        buckets: list[list[int]] = []
        levels: list[float] = []
        order = sorted(range(len(atoms)),
                       key=lambda k: (lows[k], keys[k] if keys[k] is not None
                                      else float("inf")))
        for k in order:
            zero = keys[k]
            placed = False
            for bi, lv in enumerate(levels):
                if (zero is None) == (lv is None) and (
                        zero is None or abs(zero - lv) <= radius):
                    buckets[bi].extend(atoms[k])
                    placed = True
                    break
            if not placed:
                if len(buckets) >= cap:
                    # the cap is reached: the component joins the nearest
                    # level rather than founding a group nothing bounds
                    known = [(abs(zero - lv), bi) for bi, lv in enumerate(levels)
                             if lv is not None and zero is not None]
                    buckets[min(known)[1] if known else 0].extend(atoms[k])
                    continue
                buckets.append(list(atoms[k]))
                levels.append(zero)
        if len(buckets) < 2:
            return []
        out = []
        for b in buckets:
            sub = tris[b]
            ids = np.unique(np.asarray(sub).reshape(-1))
            yv = v[ids, 1]
            foot = ids[yv <= float(yv.min()) + self.foot_band_m]
            if foot.shape[0] == 0:
                foot = ids[:1]
            if foot.shape[0] > self.stations_max:
                pick = _lo.farthest_point_stations(v[foot][:, [0, 2]],
                                                   self.stations_max)
                foot = foot[pick]
            feet = tuple(authored_latlon(float(v[i, 0]), float(v[i, 2]),
                                         self.lat, self.lon, self.m.heading_deg)
                         + (float(v[i, 1]),) for i in foot.tolist())
            out.append((tuple(tuple(int(q) for q in row)
                              for row in np.asarray(sub).tolist()), feet))
        return out


    def foot_groups(self, parts: _t.Sequence[Part], surface: _ar.Surface,
                    tol_m: float, cap: int
                    ) -> list[tuple[tuple[tuple[int, int, int], ...],
                                    tuple[tuple[float, float, float], ...]]]:
        """§16 (2) BY FOOT (11ak (2)): one FOOTED body's ``(triangles,
        feet)`` per group of feet that meet the ground at ONE zero.

        §16 (2)'s existing cuts ask what the GROUND under a body does —
        the part cut reads one zero per part, the triangle cut the ground
        under each triangle.  Neither sees the body whose own FEET
        disagree over ground that barely moves: ``Terminal4_green-PKT4``
        b8 stands on 0.5 m of relief and its feet are authored over 7.4 m
        of it, so the anchor rule drops the whole body to its low-side
        foot and every other foot floats.  That is exactly the body
        §16a (2) then REFUSES as a carrier (LEMD 117 of them), and a
        refused carrier is a body the roofs over it cannot ride.

        So the feet themselves are grouped, by the zero each of them
        SAYS the body has (``surface(foot) - y_foot``, §7's own reading
        and :func:`placement_carrier.anchor_ground_off`'s), at ``tol_m``
        by the same greedy rule the ground cut uses; each triangle joins
        the group of the foot NEAREST it in plan, so a wall stays with
        the floor it stands on rather than with whatever height its own
        vertices reach.  Each piece then anchors on feet that meet the
        ground.

        Returns ``[]`` when the feet read one level, when fewer than two
        feet read at all, or when the file cannot be parsed."""
        if tol_m <= 0.0 or cap <= 0 or not parts or not self._read():
            return []
        feet = [(float(f[0]), float(f[1]), float(f[2]))
                for p in parts for f in p.feet]
        if len(feet) < 2:
            return []
        import numpy as np
        ml, mo = _ar._m_per_deg(self.lat)
        # the same per-cell sampling the triangle cut uses, and for the
        # same reason: the design surface's faces are metres across
        cell: dict[tuple[int, int], "float | None"] = {}

        def _ground(la: float, lo: float) -> "float | None":
            k = (int(round(la * ml / GROUND_CELL_M)),
                 int(round(lo * mo / GROUND_CELL_M)))
            if k not in cell:
                cell[k] = surface(la, lo)
            return cell[k]

        zeros: list[float] = []
        pick: list[tuple[float, float, float]] = []
        for f in feet:
            z = _ground(f[0], f[1])
            if z is None:
                continue
            zeros.append(float(z) - f[2])
            pick.append(f)
        if len(pick) < 2 or max(zeros) - min(zeros) <= tol_m:
            return []
        buckets: list[list[int]] = []
        levels: list[float] = []
        for i in sorted(range(len(pick)), key=lambda q: zeros[q]):
            for bi, lv in enumerate(levels):
                if abs(zeros[i] - lv) <= tol_m:
                    buckets[bi].append(i)
                    break
            else:
                if len(buckets) >= cap:
                    buckets[min(range(len(levels)),
                               key=lambda bi: abs(zeros[i] - levels[bi]))
                            ].append(i)
                    continue
                buckets.append([i])
                levels.append(zeros[i])
        if len(buckets) < 2:
            return []
        tri_list = [self._comps[p.comp].tris for p in parts
                    if 0 <= p.comp < len(self._comps)]
        if not tri_list:
            return []
        tris = np.concatenate(tri_list)
        v = self._geom.vertices
        xs = v[tris, 0].mean(axis=1)
        zz = v[tris, 2].mean(axis=1)
        h = math.radians(self.m.heading_deg)
        sn, cs = math.sin(h), math.cos(h)
        e = xs * cs - zz * sn
        n = -(xs * sn + zz * cs)
        tla = (self.lat + n / ml) * ml
        tlo = (self.lon + e / mo) * mo
        fla = np.array([f[0] for f in pick]) * ml
        flo = np.array([f[1] for f in pick]) * mo
        of_foot = np.empty(len(pick), dtype=np.int64)
        for bi, b in enumerate(buckets):
            for i in b:
                of_foot[i] = bi
        who = np.empty(tris.shape[0], dtype=np.int64)
        # chunked so a 40k-triangle body against 250 feet never builds
        # one 10M-cell matrix
        step = max(1, 1 << 20 // max(1, len(pick)))
        for a in range(0, tris.shape[0], step):
            b = min(a + step, tris.shape[0])
            d = ((tla[a:b, None] - fla[None, :]) ** 2
                 + (tlo[a:b, None] - flo[None, :]) ** 2)
            who[a:b] = of_foot[d.argmin(axis=1)]
        # §16c (1): THE ATOM IS THE COMPONENT.  The per-triangle vote
        # above is what a welded solid gets torn by, so the component
        # takes the group MOST of its triangles voted for, whole.
        for blk in self._comp_blocks(tris):
            if len(blk) < 2:
                continue
            vote: dict[int, int] = {}
            for i in blk:
                vote[int(who[i])] = vote.get(int(who[i]), 0) + 1
            win = max(vote.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            for i in blk:
                who[i] = win
        out = []
        for bi, b in enumerate(buckets):
            sel = np.nonzero(who == bi)[0]
            if sel.shape[0] == 0:
                continue
            sub = tris[sel]
            out.append((tuple(tuple(int(q) for q in row)
                              for row in np.asarray(sub).tolist()),
                        tuple(pick[i] for i in b)))
        return out if len(out) > 1 else []


    # ── §14a: THE BASIN BODY FOLLOWS ITS RING ────────────────────────
    # The law itself is ``basin_ring`` (a ring is not a cut of a line and
    # has no business in the line cutter); these two hand it the parsed
    # geometry this cutter already holds.

    def ring_reading(self, parts: _t.Sequence[Part], rim: _ar.RimRing
                     ) -> "tuple[float, float] | None":
        """``(interior fraction, base y)`` of one basin body against its
        ring — §14a (2)'s own two numbers."""
        if not parts or not self._read():
            return None
        return _br.ring_reading(self._geom, self._comps, parts, rim,
                                self.lat, self.lon, self.m.heading_deg)

    def ring_arcs(self, parts: _t.Sequence[Part], rim: _ar.RimRing,
                  arcs: _t.Sequence["_br.Arc"], band_m: float
                  ) -> "tuple[list, tuple[int, ...]]":
        """§14a (1): ``(pieces, wall arcs)`` — one basin body's
        ``(arc index, triangles, feet)`` per piece (``basin_ring``)."""
        if not parts or not self._read():
            return ([], ())
        return _br.ring_arcs(self._geom, self._comps, parts, rim, arcs,
                             band_m, self.lat, self.lon, self.m.heading_deg,
                             self.foot_band_m, self.stations_max)

    def carrier_groups(self, parts: _t.Sequence[Part],
                       carrier_boxes: _t.Sequence[
                           _t.Sequence[tuple[float, float, float, float]]],
                       tris_in: _t.Sequence[_t.Sequence[int]] = ()
                       ) -> list[tuple[int, tuple[tuple[int, int, int], ...],
                                       tuple[float, float, float, float]]]:
        """§16a (1): ONE BODY'S TRIANGLES ASSIGNED TO THE CARRIER GROUP
        EACH STANDS OVER — ``(carrier index, triangles, plan box)`` per
        piece, best-ranked carrier first.

        ``carrier_boxes`` are the ranked candidates' FOOTPRINT boxes
        (``placement_carrier.Candidate.part_boxes``, the same geometry
        the stands-over relation is measured on): a triangle belongs to
        the first carrier whose footprint its plan centroid falls in,
        and one over no carrier's footprint at all joins the winner —
        the body stands over the winner as a whole, and inventing a
        piece with no carrier would be the very drop §16 (3) closed.

        Returns ``[]`` where the body reads ONE carrier (it is not cut
        at all then — §14 (1)'s rigid span is unbroken), or where the
        file cannot be parsed.  No surface is sampled here: §16a (1)'s
        whole point is that the ground under a carried body is never
        read."""
        if len(carrier_boxes) < 2 or not parts or not self._read():
            return []
        import numpy as np
        # §16c (1): the piece's OWN WRITTEN triangles where the cut made
        # one, else everything the file will contain
        if len(tris_in):
            tris = np.asarray(tris_in, dtype=np.int64)
        else:
            tri_list = [self._comps[p.comp].tris for p in parts
                        if 0 <= p.comp < len(self._comps)]
            if not tri_list:
                return []
            tris = np.concatenate(tri_list)
        if tris.size == 0:
            return []
        v = self._geom.vertices
        xs = v[tris, 0].mean(axis=1)
        zs = v[tris, 2].mean(axis=1)
        # the authored (x, z) -> (lat, lon) map of :func:`authored_latlon`,
        # vectorised: one reflection and one rotation, no per-triangle call
        ml, mo = _ar._m_per_deg(self.lat)
        h = math.radians(self.m.heading_deg)
        s, c = math.sin(h), math.cos(h)
        e = xs * c - zs * s
        n = -(xs * s + zs * c)
        la = self.lat + n / ml
        lo = self.lon + e / mo
        who = np.full(tris.shape[0], -1, dtype=np.int64)
        for k, boxes in enumerate(carrier_boxes):
            free = who < 0
            if not free.any():
                break
            for b in boxes:
                hit = (free & (la >= b[0]) & (la <= b[2])
                       & (lo >= b[1]) & (lo <= b[3]))
                if hit.any():
                    who[hit] = k
                    free = who < 0
        who[who < 0] = 0
        # §16c (1): THE ATOM IS THE COMPONENT — a welded solid rides ONE
        # carrier, whatever its triangles' centroids fall in.
        for blk in self._comp_blocks(tris):
            if len(blk) < 2:
                continue
            vote: dict[int, int] = {}
            for i in blk:
                vote[int(who[i])] = vote.get(int(who[i]), 0) + 1
            win = max(vote.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            for i in blk:
                who[i] = win
        out = []
        for k in range(len(carrier_boxes)):
            sel = np.nonzero(who == k)[0]
            if sel.shape[0] == 0:
                continue
            sub = tris[sel]
            ids = np.unique(np.asarray(sub).reshape(-1))
            # the same reflection, VECTORISED: the per-vertex call cost
            # 2.8 M invocations and 3.5 s of the LEMD plan stage
            vx = v[ids, 0]
            vz = v[ids, 2]
            ve = vx * c - vz * s
            vn = -(vx * s + vz * c)
            pla = self.lat + vn / ml
            plo = self.lon + ve / mo
            out.append((k, tuple(tuple(int(q) for q in row)
                                 for row in np.asarray(sub).tolist()),
                        (float(pla.min()), float(plo.min()),
                         float(pla.max()), float(plo.max()))))
        return out if len(out) > 1 else []


    def top_y(self, parts: _t.Sequence[Part]) -> "float | None":
        """§16c (4): THE TOP OF A BODY in the authored frame — the
        highest authored ``y`` of its components.

        The unit's members share ONE authored datum (§14's premise: the
        shared-datum pack authored every object against one flat plane),
        so a body's base and a candidate's top are directly comparable,
        and their authored difference IS their world difference whichever
        carrier is chosen (a carried body is written at the carrier's
        anchor with the carrier's own offset, which cancels)."""
        if not self._read():
            return None
        ys = [self._comps[p.comp].max_y for p in parts
              if 0 <= p.comp < len(self._comps)]
        return max(ys) if ys else None

    def part_tops(self, raw: _t.Sequence[_t.Any]) -> "list[list[float]]":
        """§16c (4): one authored TOP per PART of every raw body — the
        highest authored ``y`` of that part's component, or of the
        piece's own triangles where a cut made one.

        A candidate's top is asked UNDER THE OVERLAP: a coarsened
        carrier group spans a terminal, and its tallest part a hundred
        metres away says nothing about what a roof twenty metres off
        rests on."""
        out: list[list[float]] = []
        if not self._read():
            return [[0.0] * len(r[0]) for r in raw]
        import numpy as np
        v = self._geom.vertices
        for r in raw:
            if r[5]:
                ids = np.unique(np.asarray(r[5], dtype=np.int64).reshape(-1))
                ids = ids[ids < v.shape[0]]
                out.append([float(v[ids, 1].max()) if ids.size else 0.0])
                continue
            out.append([float(self._comps[p.comp].max_y)
                        if 0 <= p.comp < len(self._comps) else 0.0
                        for p in r[0]])
        return out

    def all_tris(self) -> tuple:
        """EVERY triangle of the member's file — what the WRITER puts in
        a body's file when the plan's bodies do not own it.

        ``obj8_split.split_obj8`` assigns a triangle the plan never saw
        (a thin sheet the thickness gate stripped, an exporter's ground
        paint) to the NEAREST body, and a placement the plan reads as ONE
        body therefore gets the WHOLE object.  LEMD's
        ``Terminal4_green-TEJ3`` is exactly that: its member carries ONE
        part of 4 triangles, and the file written for it is 53 triangles
        over 1,025 x 2,106 m — which is why every reading of the plan's
        own parts (``geom_box``, and this lane's first geometry samples
        alike) said 0.22 m of ground while the eye read +16.22 m."""
        if not self._read():
            return ()
        import numpy as np
        tl = [c.tris for c in self._comps if len(c.tris)]
        if not tl:
            return ()
        return tuple(tuple(int(q) for q in row)
                     for row in np.concatenate(tl).tolist())

    def written_components(self) -> "list[tuple[int, tuple, tuple]]":
        """§16d (1): EVERY connected component the WRITER will emit, as
        ``(solid_index, triangles, plan box)``.

        ``solid_index`` is the index into ``obj8.solid_components`` — the
        number a ``Part.comp`` names — or ``-1`` for a DRAPED component,
        which no part can ever name because ``parse_obj8`` keeps the
        draped triangles out of ``geom.solid`` altogether.  Both are
        written into some body's file by ``obj8_split``, so both are
        this law's population: a component is a body's only when it lies
        within reach of that body's parts (§16d (1)).

        The plan box is ``(lat0, lon0, lat1, lon1)`` in the placement's
        own frame, the spelling every other plan box carries.  The
        triangles come back as the NUMPY array the components hold: a
        clutter object publishes thousands of components over tens of
        thousands of triangles, and building a Python triple for every
        one of them costs more than the pass — the caller converts only
        the components it actually places (owner RULINGS 2026-09-13h)."""
        if not self._read():
            return []
        import numpy as np
        _box = self.plan_box_of_tris
        out: list[tuple[int, _t.Any, tuple]] = []
        for ci, comp in enumerate(self._comps):
            if not len(comp.tris):
                continue
            out.append((ci, comp.tris, _box(comp.tris)))
        drp = getattr(self._geom, "draped", None)
        if drp is not None and getattr(drp, "shape", (0,))[0]:
            # A DRAPED triangle whose sorted vertex triple is ALSO a solid
            # triangle's is the SAME FACE authored twice — a double-sided
            # panel, one copy draped.  ``obj8_split`` keys a body's own
            # triangles on that triple, so admitting the draped copy as an
            # orphan would make it SENIOR over the solid component's owner
            # and steal the face: LEMD's `OldTerminal_FSX-DCNEUN` lost
            # every triangle of its 18 components that way and its file
            # was never written.  A duplicate face belongs with the solid
            # it duplicates, which is where the component path puts it.
            sol = (np.concatenate([c.tris for c in self._comps if len(c.tris)])
                   if any(len(c.tris) for c in self._comps)
                   else np.zeros((0, 3), dtype=np.int64))
            base = np.int64(int(self._geom.vertices.shape[0]) + 1)

            def _keys(t):
                q = np.sort(np.asarray(t, dtype=np.int64).reshape(-1, 3), axis=1)
                return (q[:, 0] * base + q[:, 1]) * base + q[:, 2]

            solk = np.unique(_keys(sol)) if sol.shape[0] else \
                np.zeros(0, dtype=np.int64)
            for t in self._draped_components(drp):
                if solk.shape[0]:
                    t = t[~np.isin(_keys(t), solk)]
                if t.shape[0] == 0:
                    continue
                out.append((-1, t, _box(t)))
        return out

    def plan_box_of_tris(self, tris) -> "tuple | None":
        """§16d (1): the PLAN BOX of a set of authored triangles.

        A raw body the cut made carries its triangles, and its ``box`` is
        its FEET's (11f (2): a segment covers its own station span).
        That is the right PLAN footprint and the wrong GEOM box — the
        writer puts the triangles in the file, and 115 of LEMD's line
        segments reached beyond a box drawn round their feet."""
        if not self._read() or tris is None or len(tris) == 0:
            return None
        import numpy as np
        v = self._geom.vertices
        p = v[np.asarray(tris, dtype=np.int64).reshape(-1)]
        ml, mo = _ar._m_per_deg(self.lat)
        h = math.radians(self.m.heading_deg)
        s, c = math.sin(h), math.cos(h)
        e = p[:, 0] * c - p[:, 2] * s
        n = -(p[:, 0] * s + p[:, 2] * c)
        la = self.lat + n / ml
        lo = self.lon + e / mo
        return (float(la.min()), float(lo.min()),
                float(la.max()), float(lo.max()))

    def _draped_components(self, drp) -> "list":
        """The DRAPED triangles' own connected components, welded on the
        same millimetre key ``obj8.solid_components`` uses.  An exporter's
        ground paint is not one body because it is one ``TRIS`` range."""
        import numpy as np
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        keyed = np.round(self._geom.vertices, 3)
        _u, canon = np.unique(keyed, axis=0, return_inverse=True)
        canon = np.asarray(canon).reshape(-1)
        nk = int(canon.max()) + 1 if canon.size else 1
        t = canon[drp]
        g = coo_matrix((np.ones(t.shape[0] * 2, dtype=np.int8),
                        (np.concatenate([t[:, 0], t[:, 1]]),
                         np.concatenate([t[:, 1], t[:, 2]]))), shape=(nk, nk))
        _n, label = connected_components(g, directed=False)
        lab = label[t[:, 0]]
        order = np.argsort(lab, kind="stable")
        cuts = np.flatnonzero(lab[order][1:] != lab[order][:-1]) + 1
        return [drp[idx] for idx in np.split(order, cuts) if idx.size]

    def geom_points(self, parts: _t.Sequence[Part],
                    tris: _t.Sequence[_t.Sequence[int]] = (),
                    cap: int = 0) -> tuple[tuple[float, float, float], ...]:
        """§16b (4): THE BODY'S OWN WRITTEN GEOMETRY, as ``(lat, lon,
        lowest y)`` samples — one per :data:`GEOM_CELL_M` cell of plan,
        thinned to ``cap`` (:data:`GEOM_PTS_MAX`).

        Every §16 / §16a number was read on the plan's ``geom_box`` (the
        hull of the body's PART boxes) or on the carrier's box.  For a
        body the cut left whole that is a box over the CARRIER — 124 m
        for ``Terminal4_green-TEJ3`` whose written file spans 2,342 m —
        so the census was blind to what the eye reads (11ap).  These are
        the written triangles themselves: what the file actually covers,
        and the lowest thing it puts over each patch of ground.

        ``tris`` are the piece's own triangles when the cut made one
        (a segment, a terrain group, a carrier piece); with none given
        the body's whole parts are read."""
        if not self._read():
            return ()
        import numpy as np
        if tris:
            t = np.asarray(tris, dtype=np.int64)
        else:
            tl = [self._comps[p.comp].tris for p in parts
                  if 0 <= p.comp < len(self._comps)]
            if not tl:
                return ()
            t = np.concatenate(tl)
        if t.size == 0:
            return ()
        v = self._geom.vertices
        xs = v[t, 0].mean(axis=1)
        zs = v[t, 2].mean(axis=1)
        ys = v[t, 1].min(axis=1)
        ml, mo = _ar._m_per_deg(self.lat)
        h = math.radians(self.m.heading_deg)
        s, c = math.sin(h), math.cos(h)
        e = xs * c - zs * s
        n = -(xs * s + zs * c)
        la = self.lat + n / ml
        lo = self.lon + e / mo
        # ONE POINT PER CELL, the LOWEST triangle in it: a roof of 40,000
        # panels says nothing 40,000 times, and the reading the census
        # makes (the ground under this patch, the thing standing lowest
        # over it) is a per-place question.
        kla = np.round(la * ml / GEOM_CELL_M).astype(np.int64)
        klo = np.round(lo * mo / GEOM_CELL_M).astype(np.int64)
        key = (kla + (1 << 20)) * (1 << 22) + (klo + (1 << 20))
        order = np.argsort(ys, kind="stable")
        _u, first = np.unique(key[order], return_index=True)
        sel = order[first]
        return thin_points(tuple((float(la[i]), float(lo[i]), float(ys[i]))
                                 for i in sel.tolist()), cap or GEOM_PTS_MAX)


def _plan_span_m(parts: _t.Sequence[Part]) -> float:
    """The plan diagonal of the parts' own boxes, in metres."""
    lo_la = min(p.box[0] for p in parts)
    lo_lo = min(p.box[1] for p in parts)
    hi_la = max(p.box[2] for p in parts)
    hi_lo = max(p.box[3] for p in parts)
    ml, mo = _ar._m_per_deg(0.5 * (lo_la + hi_la))
    return math.hypot((hi_la - lo_la) * ml, (hi_lo - lo_lo) * mo)


def segment_anchor(feet: _t.Sequence[tuple[float, float, float]],
                   surface: _ar.Surface, index: int, total: int) -> _ar.Anchor:
    """A SEGMENT's anchor: its MID-FOOT (§6's line row) — the segment's
    own ground contact nearest the plan centre of its feet, so the drape
    reads the terrain in the MIDDLE of the segment and the two ends float
    by half a segment's relief each instead of a whole run's."""
    ml, mo = _ar._m_per_deg(feet[0][0])
    clat = sum(f[0] for f in feet) / len(feet)
    clon = sum(f[1] for f in feet) / len(feet)
    best = min(feet, key=lambda f: (round(((f[0] - clat) * ml) ** 2
                                          + ((f[1] - clon) * mo) ** 2, 6),
                                    f[0], f[1]))
    return _ar.Anchor(_ar.LINE_SEGMENT, best[0], best[1], best[2],
                      f"line segment {index + 1}/{total}: mid-foot",
                      surface(best[0], best[1]))


#: §16 (2): the plan-grid cell the TRIANGLE cut reads the ground on — a
#: sampling resolution (the design surface's own faces are metres
#: across), never a law.  One reading per cell instead of one per
#: triangle: LEMD's plan stage measured 913k surface reads with the
#: per-triangle form and 6.5 s of the stage in them.
GROUND_CELL_M = 5.0



#: one member's raw bodies before coarsening: ``(parts, class, anchor,
#: feet, elevated, segment triangles, geometry samples, terrain ground)``
#: — the last two are §16b's: what the body WRITES, and the design
#: surface under it (its terrain group's own height).
_Raw = _t.Tuple[list, str, _ar.Anchor, tuple, bool, tuple, tuple,
                "float | None"]


def _part_zero(p: Part, surface: _ar.Surface) -> float | None:
    """§16 (2): the INTENDED ZERO of one part, in world height — the
    design surface under the part minus the authored ``y`` that stands
    there.  A part with ground-contact feet reads the surface under its
    LOWEST foot (the ground it meets); a part with none — a roof panel, a
    deck slab — reads the ground under its own plan position, which is
    what "the ground under its own triangles" names.  ``None`` off-sheet:
    no reading is no evidence that the terrain differs."""
    if p.feet:
        f = min(p.feet, key=lambda q: q[2])
        z = surface(f[0], f[1])
        return None if z is None else float(z) - float(f[2])
    z = surface(p.lat, p.lon)
    return None if z is None else float(z) - float(p.base_y)


def _cut_parts_by_terrain(parts: _t.Sequence[Part], surface: _ar.Surface,
                          tol_m: float, reach_m: float = 0.0) -> list[list[Part]]:
    """§16 (2): EVERY BODY IS RE-CUT BY TERRAIN.

    §15 (2) gave the terrain check to the groups :func:`bind_plan_overlaps`
    welds; the body the ε-contact graph itself formed was never asked.
    LEMD 1.50.1763: ``Terminal4_green-PKT4__b0`` is ONE skirted body 667 m
    long standing on ground that spans 8.30 m, and ``green-TEJ3`` is ONE
    carried roof-panel body scattered over 1 x 2 km of terminal — one
    zero for each, and every panel away from the anchor floats or buries
    by whatever the ground does in between.  A rigid body is never wider
    than the terrain it can stand on (§15 (2)'s own sentence), so the cut
    runs on the PARTS: the intended zeros of a body's parts that agree
    within ``tol_m`` are one body, and a body whose parts read further
    apart than that is cut into terrain groups.

    The grouping is :func:`placement_carrier.coarsen` — §9's own rule, one
    implementation, read one level down — so a part group is formed the
    same way a body group is.  ``tol_m <= 0`` disarms the cut."""
    if tol_m <= 0.0 or len(parts) < 2:
        return [list(parts)]
    keys = [(i, _ar.Anchor(_ar.OTHER, p.lat, p.lon, 0.0, "", z), len(p.feet))
            for i, (p, z) in enumerate((q, _part_zero(q, surface)) for q in parts)]
    # §16b (1): §9's rule WHOLE, contiguity included — parts of one body
    # that agree in zero but stand a kilometre apart are not one piece
    groups = _pc.coarsen(keys, tol_m, boxes=[p.box for p in parts],
                         reach_m=reach_m)
    return [[parts[i] for i in g] for g in groups]



def pristine_path(m: Member) -> str:
    """§4.1's restore-before-read: the ``.anchor_bak`` original when v1's
    y-bake left one, else the member's own authored file.  A split never
    reads a BAKED file — the deltas it carries are the very machinery §8
    retires."""
    bak = m.live_path + ".anchor_bak"
    if _os.path.isfile(bak):
        return bak
    return m.authored_path if _os.path.isfile(m.authored_path) else m.live_path

def _bodies_of(member: Member, edges: _t.Sequence[tuple[int, int]]
               ) -> list[list[int]]:
    """The member's parts grouped into bodies: every intra-placement
    ε-contact edge binds, a LINE part binds nothing (10bb).  Returns
    lists of part ids, deterministic in the plan's own part order."""
    pid_of = {p.pid: p for p in member.parts}
    parent = {p.pid: p.pid for p in member.parts}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        if a in parent and b in parent and not pid_of[a].line and not pid_of[b].line:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
    groups: dict[int, list[int]] = {}
    for p in member.parts:
        groups.setdefault(find(p.pid), []).append(p.pid)
    return [groups[k] for k in sorted(groups, key=lambda k: min(groups[k]))]


def _floor_member(r: _Raw, ref: str) -> _Raw:
    """§14a (2): one raw body marked as a FLOOR member of ``ref``.

    The mark rides the anchor's REASON — the plan's own wire between the
    cut and everything downstream — so pass 3 sends the body to §16 (3)'s
    own-ground anchor instead of a carrier, pass 2's bind keys
    (``basin_ring.bind_key_of``) hold it out of the pit's group, and the
    report says why it is where it is.  Nothing else changes: the anchor
    itself is the generic rule's, computed with no ring at all."""
    a = r[2]
    return (r[0], r[1], _dc.replace(a, reason=f"{a.reason}{_br.FLOOR_MARK}{ref})"),
            *r[3:])


def _basin_floor_member(cutter: "_LineCutter", parts: _t.Sequence[Part],
                        rim: _ar.RimRing, tol_m: float) -> bool:
    """§14a (2): does this body merely STAND IN the pit rather than form
    it (``basin_ring.member_kind``)?  A body the cutter cannot read is
    never moved."""
    r = cutter.ring_reading(parts, rim)
    if r is None:
        return False
    frac, base_y = r
    return _br.member_kind(frac, base_y, tol_m) == _br.FLOOR


def _rim_ring_of(rims: _t.Sequence[_ar.RimRing], lat: float, lon: float,
                 base_y: float) -> "_ar.RimRing | None":
    """:func:`_rim_of`'s own verdict with the RING it found — §14a needs
    the ring itself (its nodes, their heights and its ref), and reading
    it twice would be two answers waiting to disagree."""
    if base_y >= 0.0:
        return None
    return _ar.rim_of(rims, lat, lon)


def _rim_of(rims: _t.Sequence[_ar.RimRing], lat: float, lon: float,
            base_y: float) -> bool:
    """A BASIN body: its lowest component stands BELOW the authored zero
    and inside an emitted basin-wall ring.

    Containment alone is not the test and must not be — a terminal whose
    ground floor happens to sit over a cut pit would be read as the pit
    (measured at LEMD: ``Terminal4sBlue-LEMD35`` classed ``basin``, its
    zero snapped to the rim and its roof feet censused 54 m off).  The pit
    objects are the ones authored BELOW their own zero; 10ba cut the basin
    to that depth, so the two readings agree by construction."""
    if base_y >= 0.0:
        return False
    return any(len(r.ring) >= 3 and _ar._inside(r.ring, lat, lon) for r in rims)


# ── the bodies of one placement (``placement_body``) ─────────────────────
# §14/§14a/§16/§16a/§16b's BODY FORMATION lives next door (the 1,000-line
# law); it is re-exported here because every caller and every twin reads
# these names as this module's.
from .placement_body import (_carrier_pieces,  # noqa: E402,F401
                             _footless_targets, _Raw, _raw_bodies,
                             _whole_body)
