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

import math
import os as _os
import typing as _t

from ..model.rebake import Member, Part, Unit
from . import anchor_rule as _ar
from . import line_object as _lo
from . import placement_carrier as _pc

__all__ = ["authored_latlon", "segment_anchor", "pristine_path",
           "GROUND_CELL_M", "_Raw"]

from .placement_carrier import is_elevated            # noqa: E402  (§13)

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
                 lat: float, lon: float) -> None:
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
                       tol_m: float, cap: int
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

        Returns ``[]`` when the body reads one terrain group, when the
        surface reads nowhere, or when the file cannot be parsed."""
        if tol_m <= 0.0 or cap <= 0 or not parts or not self._read():
            return []
        import numpy as np
        tri_list = [self._comps[p.comp].tris for p in parts
                    if 0 <= p.comp < len(self._comps)]
        if not tri_list:
            return []
        tris = np.concatenate(tri_list)
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

        buckets: list[list[int]] = []
        levels: list[float] = []
        order = sorted(range(tris.shape[0]), key=lambda i: float(ys[i]))
        for i in order:
            la, lo = authored_latlon(float(xs[i]), float(zs[i]), self.lat,
                                     self.lon, self.m.heading_deg)
            z = _ground(la, lo)
            zero = None if z is None else float(z) - float(ys[i])
            placed = False
            for bi, lv in enumerate(levels):
                if (zero is None) == (lv is None) and (
                        zero is None or abs(zero - lv) <= tol_m):
                    buckets[bi].append(i)
                    placed = True
                    break
            if not placed:
                if len(buckets) >= cap:
                    # the cap is reached: the triangle joins the nearest
                    # level rather than founding a group nothing bounds
                    known = [(abs(zero - lv), bi) for bi, lv in enumerate(levels)
                             if lv is not None and zero is not None]
                    buckets[min(known)[1] if known else 0].append(i)
                    continue
                buckets.append([i])
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
#: feet, elevated, segment triangles)``.
_Raw = _t.Tuple[list, str, _ar.Anchor, tuple, bool, tuple]


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
                          tol_m: float) -> list[list[Part]]:
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
    groups = _pc.coarsen(keys, tol_m)
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



# ── the cuts (``placement_cut``) ─────────────────────────────────────────
# §10's segment cut and §16 (2)'s terrain cut live next door (the
# 1,000-line law); they are re-exported here because every caller and
# every twin reads them as this module's.
from .placement_cut import (GROUND_CELL_M, _cut_parts_by_terrain,  # noqa: E402
                            _LineCutter, _part_zero, _plan_span_m,
                            authored_latlon, pristine_path, segment_anchor)


#: one member's raw bodies before coarsening: ``(parts, class, anchor,
#: feet, elevated, segment triangles)``.
_Raw = _t.Tuple[list, str, _ar.Anchor, tuple, bool, tuple]

def _raw_bodies(m: Member, u: Unit, edges: _t.Sequence[tuple[int, int]],
                surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                rims: _t.Sequence[_ar.RimRing], counts: dict[str, int],
                *, split_tol_m: float, elevated_base_m: float,
                line_segment_m: float, line_stations_max: int,
                line_ratio: float, line_max_h: float,
                foot_band_m: float) -> list[_Raw]:
    """One member's bodies, classed and anchored — the per-placement half,
    unchanged by §14 except that the basin's rim anchor is now wired
    (``anchor_rule``) and the segment cut still never touches an elevated
    body (§13 (1))."""
    groups = _bodies_of(m, edges)
    pid_of = {p.pid: p for p in m.parts}
    cutter = _LineCutter(m, line_segment_m, line_stations_max, foot_band_m,
                         line_ratio, line_max_h, u.anchor[0], u.anchor[1])
    raw: list[_Raw] = []
    for g in groups:
        parts = [pid_of[q] for q in g]
        base_min = min(p.base_y for p in parts)
        # §13 (1): the line-segment cut NEVER applies to an elevated body
        # — a 65 m tower part that happens to read line-shaped (LEMD's
        # `-ZNTWR`) is not a fence
        pieces = ([] if (elevated_base_m > 0.0 and base_min > elevated_base_m)
                  else cutter.segments(parts))
        if pieces:
            # 11f (2): the body IS the line, cut into its stations
            counts["line_bodies_segmented"] = \
                counts.get("line_bodies_segmented", 0) + 1
            counts["line_segments"] = counts.get("line_segments", 0) + len(pieces)
            for si, (tris, feet) in enumerate(pieces):
                sa = segment_anchor(feet, surface, si, len(pieces))
                raw.append((parts, _ar.LINE_SEGMENT, sa, feet,
                            is_elevated(min(f[2] for f in feet), sa,
                                        elevated_base_m), tris))
            continue
        # §16 (2): EVERY BODY IS RE-CUT BY TERRAIN — the ε-contact body is
        # asked the same question §15 (2) asks a plan-overlap bond, one
        # level down, on its own parts.  A BASIN body is exempt for §14
        # (2)'s reason (the pit was cut TO the object, so its floor plate
        # standing 7 m under its rim is the authoring, not two bodies).
        lowest0 = min(parts, key=lambda p: p.base_y)
        is_basin = _rim_of(rims, lowest0.lat, lowest0.lon, lowest0.base_y)
        pieces_p = ([list(parts)] if is_basin
                    else _cut_parts_by_terrain(parts, surface, split_tol_m))
        if len(pieces_p) > 1:
            counts["bodies_re_cut_by_terrain"] = \
                counts.get("bodies_re_cut_by_terrain", 0) + 1
            counts["terrain_body_groups"] = \
                counts.get("terrain_body_groups", 0) + len(pieces_p)
        for parts in pieces_p:
            base_min = min(p.base_y for p in parts)
            lowest = min(parts, key=lambda p: p.base_y)
            # §16 (2) BY TRIANGLE: the part cut has nothing to divide in a
            # body authored as ONE welded component (LEMD's `green-TEJ3`,
            # a roof-panel resource over 1 x 2 km).  Where the ground
            # under the body's own parts still spans more than the
            # tolerance, the TRIANGLES are grouped by the ground under
            # them.  The pre-test is five samples; the cut itself only
            # runs on a body that fails it.
            hull = _pc.hull_of([p.box for p in parts])
            zs = _pc.ground_samples(surface, [p.box for p in parts], hull) \
                + _pc.ground_samples(surface, (), hull)
            tri_pieces = (cutter.terrain_groups(parts, surface, split_tol_m,
                                                line_stations_max)
                          if (not is_basin and split_tol_m > 0.0 and zs
                              and max(zs) - min(zs) > split_tol_m) else [])
            if tri_pieces:
                counts["bodies_re_cut_by_triangle"] = \
                    counts.get("bodies_re_cut_by_triangle", 0) + 1
                counts["terrain_triangle_groups"] = \
                    counts.get("terrain_triangle_groups", 0) + len(tri_pieces)
                for tris, tfeet in tri_pieces:
                    tlow = min(tfeet, key=lambda f: f[2])
                    tcls = _ar.classify_body(
                        skirted=m.skirted,
                        basin_member=False,
                        line=all(p.line for p in parts),
                        deck=m.deck_kind in ("flag", "signature"),
                        plate=m.plate_y is not None,
                        has_pad=_ar._pad_of(pads, tlow[0], tlow[1]) is not None)
                    tgeom = _ar.BodyGeometry(
                        ((tlow[0], tlow[1], tlow[2],
                          tuple((f[0], f[1], f[2]) for f in tfeet)),),
                        u.anchor[0], u.anchor[1])
                    ta = _ar.anchor_for(tcls, tgeom, surface, pads, rims,
                                        tol_m=split_tol_m)
                    # §16 (1): a triangle group of a body with no ground
                    # contact has none either (the VOR-marker class)
                    tfootless = (not any(p.feet for p in parts)
                                 and ta.body_class not in (_ar.BASIN,
                                                           _ar.PLATE_ONLY,
                                                           _ar.DECK))
                    raw.append((list(parts), ta.body_class, ta, tuple(tfeet),
                                is_elevated(tlow[2], ta, elevated_base_m)
                                or tfootless, tris))
                continue
            cls = _ar.classify_body(
                skirted=m.skirted,
                basin_member=_rim_of(rims, lowest.lat, lowest.lon, lowest.base_y),
                line=all(p.line for p in parts),
                deck=m.deck_kind in ("flag", "signature"),
                plate=m.plate_y is not None,
                has_pad=_ar._pad_of(pads, lowest.lat, lowest.lon) is not None)
            geom = _ar.BodyGeometry(
                tuple((p.lat, p.lon, p.base_y,
                       tuple((f[0], f[1], f[2]) for f in p.feet)) for p in parts),
                u.anchor[0], u.anchor[1])
            a = _ar.anchor_for(cls, geom, surface, pads, rims, tol_m=split_tol_m)
            feet = tuple((f[0], f[1], f[2]) for p in parts for f in p.feet) \
                or tuple((p.lat, p.lon, p.base_y) for p in parts)
            # §16 (1): A BODY WITH NO GROUND CONTACT AT ALL IS FOOTLESS.
            # The fallback above gives a body with no part feet its parts'
            # own positions so that it still has a box — read as FEET they
            # make a ground body out of geometry that never met the
            # ground.  The resources §16 (1) admits are exactly that (no
            # genuine solid, so the partition strips their feet), and one
            # of them — a two-triangle VOR marker reaching 50 m below its
            # own zero — was offered to the carrier search as ground and
            # read by the census as something to stand over.  The
            # structure-seated classes are excluded: a plate, a deck and a
            # basin member carry drape stations rather than feet, and
            # another law governs their elevation (14.1 rule 4).
            footless = (not any(p.feet for p in parts)
                        and a.body_class not in (_ar.BASIN, _ar.PLATE_ONLY,
                                                 _ar.DECK))
            raw.append((list(parts), a.body_class, a, feet,
                        is_elevated(base_min, a, elevated_base_m) or footless, ()))
    return raw


