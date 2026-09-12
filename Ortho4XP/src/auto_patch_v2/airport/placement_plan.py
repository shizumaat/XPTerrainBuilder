"""THE PLACEMENT PLAN'S SPLIT HALF (spec ``object-placement-spec.md`` §2
``splits`` / ``kept``, from §4's writer and §6's anchor rule).

This is the wiring the two lanes meet at.  Lane ``v2dsfagl`` owns §2's
``model/placement.py`` and §3's DSF round-trip; what lives here is the
half §4 / §6 own: given the re-seat plan the pipeline already writes
(``<ICAO>.rebake.json`` — the pack read once, its welded PARTS and the
pack-wide ε-CONTACT graph) and the emitted DESIGN SURFACE, produce the
``Split`` records — bodies, classes, anchors, offsets, the files that
would be written — and the ``kept`` records for the placements that stay
exactly as authored.

NOTHING IS WRITTEN HERE.  The write half is the join with ``v2dsfagl``
(§3 step 2b assigns the new ``OBJECT_DEF`` indices), and the spawner
wires it; this module's product is data, and ``tools/obj8_split_report.py``
renders it.

BODY FORMATION IS ``emit/clusters``' LAW, WITHOUT THE MESH
----------------------------------------------------------

The bodies ARE the split, so nothing new is derived here.  The one thing
that changes is that the split is a CUT OF A FILE, and a file's bodies
are per PLACEMENT — so only the intra-placement half of 10i/10u is in
play, and that half needs no mesh at all:

* an ε-contact edge INSIDE one placement is NEVER cut (10i (1)) — ground
  to ground, ground to elevated, elevated to elevated (10u (1)): one
  placement's touching set is ONE body.  The seat's cross-placement cut,
  the only rule that reads a seat target, does not apply to a file cut;
* a LINE OBJECT binds nothing (10bb): each line component is its own
  body, and each is anchored at its own mid-foot, so a fence drapes
  segment by segment instead of chaining 38 parts onto one foot;
* an ELEVATED DECK abutting a kerb (10ay/11a) takes no anchor of its own
  (§6): where the abutment is INSIDE the placement it is already the same
  body, and where it crosses placements this reports the merge target and
  keeps the deck's placement as authored — moving geometry BETWEEN two
  authored files is not §4's writer and is not done here.

THE CLASS OF A BODY (§6) is read off the plan and the emitted surface:
``basin`` when the body's lowest component stands inside an emitted
``structure_rim`` ring (the basin was cut to these members, 10ba, so
containment IS the membership test at this stage); ``deck`` from the
member's deck verdict; ``plate_only`` from its wall-plate seat (05n-4);
``line_segment`` from the part's own 10bb verdict; ``skirted`` from
10ag's reader, whose result the plan already carries; ``building`` when a
skirt-less body stands inside an emitted object pad; else ``other``.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import math
import os as _os
import typing as _t

from ..model.rebake import Member, Part, RebakePlan, Unit
from . import anchor_rule as _ar
from . import line_object as _lo
from . import obj8_split as _split
from . import placement_carrier as _pc
from .placement_carrier import coarsen, is_elevated   # noqa: F401  (§9 / §13)

__all__ = ["Body", "Split", "Kept", "SplitSet", "read_plan", "build_splits", "coarsen",
           "is_elevated",
           "authored_offset", "pads_rims_from_graded", "pads_rims_from_graded_doc"]


# ── reading a plan this tree did not write ───────────────────────────────

def read_plan(path: str) -> tuple[RebakePlan, tuple[tuple[int, int], ...]]:
    """The re-seat plan plus its ABUTMENT pairs (10ay).

    ``RebakePlan.from_dict`` is the ONE reader — a second one is the
    census-wrapper defect at one remove — but a plan written by a tree
    carrying a LATER additive version (8 added ``abutments`` to 7's
    fields, exactly as 7 added ``Part.line`` to 6's) is refused by its
    version check alone.  So the abutments are lifted out here and the
    version is presented as this tree's, which is what "additive" means;
    anything that is NOT purely additive still fails, because the fields
    the reader needs would not be there."""
    d = json.loads(open(path, encoding="utf-8").read())
    abut = tuple((int(a), int(b)) for a, b in d.get("abutments", ()))
    from ..model.rebake import PLAN_VERSION
    if int(d.get("version", 0)) > PLAN_VERSION:
        d = dict(d, version=PLAN_VERSION)
    return RebakePlan.from_dict(d), abut


#: The graded roles §6's class rule reads: the emitted object PADS and the
#: emitted structure RIMS.  One derivation, two callers — the shipped
#: engine path (``auto_patch/engine_v2._place_objects``) and the dry run
#: (``tools/obj8_split_report.surface_from_graded``).  A second copy is the
#: census-wrapper defect: the engine ran for weeks with ``pads=()`` and
#: ``rims=()`` — nothing shipped could ever classify ``building`` or
#: ``basin`` — while the tool, deriving them, classified both.
PAD_FACE_ROLE = "building"
RIM_BREAKLINE_KIND = "structure_rim"


def pads_rims_from_graded_doc(d: _t.Mapping[str, _t.Any]
                              ) -> tuple[tuple[_ar.PadRing, ...],
                                         tuple[_ar.RimRing, ...]]:
    """``(pads, rims)`` from a parsed ``<ICAO>.graded.json`` document: the
    ``building`` faces' rings and the ``structure_rim`` breaklines, each
    as its ``(lat, lon)`` ring.  A ring shorter than 3 kept vertices is
    not a ring and is dropped (the same floor both callers used)."""
    by_id = {v[0]: (v[1], v[2]) for v in d["vertices"]}
    pads = tuple(_ar.PadRing(f["ref"],
                             tuple(by_id[i] for i in f["ring"] if i in by_id))
                 for f in d["faces"]
                 if f["role"] == PAD_FACE_ROLE and len(f["ring"]) >= 3)
    rims = tuple(_ar.RimRing(b["ref"],
                             tuple(by_id[i] for i in b["vertices"] if i in by_id))
                 for b in d["breaklines"]
                 if b["kind"] == RIM_BREAKLINE_KIND and len(b["vertices"]) >= 3)
    return pads, rims


def pads_rims_from_graded(path: str) -> tuple[tuple[_ar.PadRing, ...],
                                              tuple[_ar.RimRing, ...]]:
    """:func:`pads_rims_from_graded_doc` of the file at ``path``."""
    with open(path, encoding="utf-8") as fh:
        return pads_rims_from_graded_doc(json.loads(fh.read()))


# ── the product ──────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Body:
    """§2's ``Body``."""

    body_id: int
    body_class: str
    components: tuple[int, ...]
    anchor: _ar.Anchor
    new_resource: str
    #: the part ids the body holds (the census reads their feet)
    pids: tuple[int, ...] = ()
    merged_into: str = ""
    #: §14 (1): was the CARRIER itself written at its own anchor?  A
    #: carrier kept whole keeps its AUTHORED row, so the two files then
    #: stand at different heights — reported, never silent.
    merged_into_written: bool = True
    #: every ground-contact FOOT the body holds, ``(lat, lon, authored y)``
    #: — §7's census reads the design surface under each of these against
    #: the surface at the anchor
    feet: tuple[tuple[float, float, float], ...] = ()
    #: the components the CUT takes whole (``components`` also names the
    #: parent component of a SEGMENT, which the cut takes by triangle)
    cut_components: tuple[int, ...] = ()
    #: a SEGMENT's own authored triangles (11f (2)); empty for a body that
    #: is a set of whole components
    tris: tuple[tuple[int, int, int], ...] = _dc.field(default=(), repr=False)
    #: §13: this file's whole content is ELEVATED — it stands on no
    #: ground contact.  The law forbids it for a SPLIT body (the census
    #: bar ``elevated bodies as own files`` is 0); it is true only of the
    #: single record standing in for a FOOTLESS placement kept whole.
    elevated: bool = False
    #: how many of the group's bodies were elevated and are CARRIED here
    elevated_members: int = 0
    #: §15 (3): the body's PLAN box ``(lat0, lon0, lat1, lon1)`` — what
    #: the stands-over census asks "which footed body is under this one"
    #: with, and the box §15 (1)'s carrier search itself reads
    plan_box: tuple[float, float, float, float] | None = None
    #: §16 (2): the body's OWN GEOMETRY box (every part it holds, the
    #: carried ones included) — what the §16 census reads the ground
    #: under.  ``plan_box`` stays the GROUND footprint §15 (3) reads.
    geom_box: tuple[float, float, float, float] | None = None
    #: §16 (3): the body's bounded FOOTPRINT boxes, the geometry the
    #: stands-over relation is measured on by the law and the census
    #: alike (``placement_carrier.foot_boxes``)
    foot_boxes: tuple[tuple[float, float, float, float], ...] = ()
    #: §16 (3): the body's FOOTPRINT FILL (``placement_carrier.fill_of``)
    #: — what says whether it is a SOLID that may carry another body's
    #: zero, and what the census must read to judge the same relation
    fill: float = 1.0

    def to_dict(self) -> dict[str, _t.Any]:
        a = self.anchor
        return {"body_id": self.body_id, "class": self.body_class,
                "components": list(self.components),
                "anchor": {"lat": a.lat, "lon": a.lon},
                "anchor_reason": a.reason, "new_resource": self.new_resource,
                "authored_offset": {"dx": a.offset[0], "dy": a.offset[1],
                                    "dz": a.offset[2]},
                "surface_z": a.surface_z, "y_zero": a.y_zero,
                "segment_tris": len(self.tris),
                "elevated": self.elevated,
                "elevated_members": self.elevated_members,
                "merged_into": self.merged_into or None,
                "plan_box": None if self.plan_box is None else list(self.plan_box),
                "geom_box": None if self.geom_box is None else list(self.geom_box),
                "foot_boxes": [list(b) for b in self.foot_boxes],
                "fill": self.fill,
                "feet": len(self.feet)}


@_dc.dataclass(frozen=True)
class Split:
    """§2's ``Split``: one original placement and the bodies replacing it."""

    index: int
    placement_id: str
    resource: str
    authored_path: str
    lat: float
    lon: float
    heading: float
    bodies: tuple[Body, ...]
    files: tuple[_split.SplitFile, ...] = ()
    write_error: str = ""

    def to_dict(self) -> dict[str, _t.Any]:
        return {"placement": {"index": self.index, "id": self.placement_id,
                              "resource": self.resource, "lat": self.lat,
                              "lon": self.lon, "heading": self.heading},
                "bodies": [b.to_dict() for b in self.bodies],
                "files": [f.resource for f in self.files]}


@_dc.dataclass(frozen=True)
class Kept:
    index: int
    placement_id: str
    resource: str
    reason: str

    def to_dict(self) -> dict[str, _t.Any]:
        return {"index": self.index, "id": self.placement_id,
                "resource": self.resource, "reason": self.reason}


@_dc.dataclass(frozen=True)
class SplitSet:
    splits: tuple[Split, ...]
    kept: tuple[Kept, ...]
    counts: _t.Mapping[str, int]
    #: the KEPT-whole placements as single-body records — §7's census is
    #: over the whole pack, and a placement that stays whole is still an
    #: AGL placement standing on its anchor's surface
    whole: tuple[Split, ...] = ()

    @property
    def all(self) -> tuple[Split, ...]:
        return self.splits + self.whole

    def to_dict(self) -> dict[str, _t.Any]:
        return {"splits": [s.to_dict() for s in self.splits],
                "kept": [k.to_dict() for k in self.kept],
                "counts": dict(self.counts)}


# ── the authored frame ───────────────────────────────────────────────────

def authored_offset(anchor_lat: float, anchor_lon: float, y_zero: float,
                    placement_lat: float, placement_lon: float,
                    heading_deg: float) -> tuple[float, float, float]:
    """§4.3 / §6: the offset SUBTRACTED from every vertex — the anchor
    point's AUTHORED ``(x, z)`` and the body's intended zero ``y``.

    OBJ8 is x east, y up, z SOUTH, rotated by the heading (clockwise from
    north) about y — ``obj8.placement_affine``'s own convention:
    ``east = x·cos h − z·sin h``, ``north = −(x·sin h + z·cos h)``.  This
    is that map inverted."""
    ml, mo = _ar._m_per_deg(placement_lat)
    e = (anchor_lon - placement_lon) * mo
    n = (anchor_lat - placement_lat) * ml
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    return (e * c - n * s, y_zero, -e * s - n * c)


# ── the bodies of one placement ──────────────────────────────────────────

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
        buckets: list[list[int]] = []
        levels: list[float] = []
        order = sorted(range(tris.shape[0]), key=lambda i: float(ys[i]))
        for i in order:
            la, lo = authored_latlon(float(xs[i]), float(zs[i]), self.lat,
                                     self.lon, self.m.heading_deg)
            z = surface(la, lo)
            if z is None:
                zero = None
            else:
                zero = float(z) - float(ys[i])
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


def _group_bodies(raw: _t.Sequence[_Raw], merged: _t.Sequence[_t.Sequence[int]],
                  m: Member, u: Unit, counts: dict[str, int],
                  by_class: dict[str, int],
                  part_boxes: _t.Sequence[_t.Sequence[tuple]] = ()) -> list[Body]:
    """The groups of one member as :class:`Body` records, each on its
    SENIOR body's anchor (:func:`placement_carrier.senior_of`)."""
    bodies: list[Body] = []
    for k, grp in enumerate(merged):
        senior = _pc.senior_of(raw, grp)
        parts = [p for i in grp for p in raw[i][0]]
        a = raw[senior][2]
        off = authored_offset(a.lat, a.lon, a.y_zero, u.anchor[0], u.anchor[1],
                              m.heading_deg)
        a = _dc.replace(a, offset=off)
        by_class[a.body_class] = by_class.get(a.body_class, 0) + 1
        # §13 (3): an elevated member's vertices are NOT feet — they never
        # stood on the ground, and counting them is what made the 218
        # census green while the sim was broken
        n_elev = sum(1 for i in grp if raw[i][4])
        if n_elev:
            counts["bodies_elevated_carried"] = \
                counts.get("bodies_elevated_carried", 0) + n_elev
        if n_elev == len(grp):
            counts["elevated_own_files"] = counts.get("elevated_own_files", 0) + 1
        feet = tuple(f for i in grp if not raw[i][4] for f in raw[i][3])
        if a.reason.startswith("low-side foot ("):
            counts["anchor_residual"] = counts.get("anchor_residual", 0) + 1
        elif a.surface_z is None:
            counts["anchor_off_surface"] = counts.get("anchor_off_surface", 0) + 1
        # a SEGMENT is cut by TRIANGLE; its parent component must NOT also
        # be handed to the cutter as a whole component, or this file would
        # claim the whole fence (11f (2))
        tris = tuple(t for i in grp for t in raw[i][5])
        cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                                  for p in raw[i][0]}))
        bodies.append(Body(k, a.body_class, tuple(sorted(p.comp for p in parts)),
                           a, _split.body_resource_name(m.resource, k),
                           tuple(sorted(p.pid for p in parts)), feet=feet,
                           cut_components=cut_comps, tris=tris,
                           elevated=n_elev == len(grp),
                           elevated_members=n_elev,
                           # THE GROUND FOOTPRINT (§15 (3)): a carried
                           # roof does not widen what its file STANDS ON,
                           # and the §15 (1) search read the group before
                           # any roof joined it — one box, one relation
                           plan_box=_pc.hull_of(
                               b for i in grp if not raw[i][4]
                               for b in part_boxes[i])
                           or _pc.hull_of(b for i in grp for b in part_boxes[i])
                           if part_boxes else _pc.box_of(feet, parts),
                           # §16 (2)/(3): the body's OWN geometry, and the
                           # bounded footprint the stands-over relation reads
                           geom_box=(_pc.hull_of(b for i in grp
                                                 for b in part_boxes[i])
                                     if part_boxes else _pc.box_of(feet, parts)),
                           foot_boxes=(_pc.foot_boxes(
                               [b for i in grp if not raw[i][4]
                                for b in part_boxes[i]]
                               or [b for i in grp for b in part_boxes[i]])
                               if part_boxes else ()),
                           fill=(_pc.fill_of(
                               _pc.hull_of(b for i in grp if not raw[i][4]
                                           for b in part_boxes[i])
                               or _pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                               [b for i in grp if not raw[i][4]
                                for b in part_boxes[i]]
                               or [b for i in grp for b in part_boxes[i]])
                               if part_boxes else 1.0)))
    return bodies


def _carried_file(raw: _t.Sequence[_Raw], grp: _t.Sequence[int], m: Member,
                  u: Unit, c: _pc.Candidate, why: str, carrier_res: str,
                  written: bool, body_id: int, counts: dict[str, int],
                  by_class: dict[str, int],
                  part_boxes: _t.Sequence[_t.Sequence[tuple]] = ()) -> Body:
    """§14 (1) / §15 (1): the bodies of ``grp`` as ONE file written at
    their CARRIER's anchor with the carrier's ``y_zero``.

    One zero plane for the two of them — which is what "the roof stays
    on its walls" means when the walls are the only thing either of them
    can read.  The translation is computed in THIS member's own authored
    frame (the offset every body file already carries), so the carried
    file lands exactly where the unit authored it relative to the
    carrier; with one unit, one row and one heading that is numerically
    the carrier's own :func:`authored_offset`.

    Bodies sharing a carrier share a file: one carrier, one zero, one
    cut.  §15 (1) is why the carrier may belong to ANOTHER RESOURCE of
    the unit — this pack names its roofs as their own resources, and the
    walls a roof stands over are almost never its own file."""
    parts = [p for i in grp for p in raw[i][0]]
    cls = raw[max(grp, key=lambda i: len(raw[i][0]))][1]
    off = authored_offset(c.anchor.lat, c.anchor.lon, c.anchor.y_zero,
                          u.anchor[0], u.anchor[1], m.heading_deg)
    a = _dc.replace(c.anchor, body_class=cls, offset=off,
                    reason=f"carried by {carrier_res} ({why})"
                    + ("" if written else " [carrier kept whole on its "
                       "authored row]"))
    by_class[cls] = by_class.get(cls, 0) + 1
    counts["bodies_elevated_carried"] = \
        counts.get("bodies_elevated_carried", 0) + len(grp)
    tris = tuple(t for i in grp for t in raw[i][5])
    cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                              for p in raw[i][0]}))
    return Body(body_id, cls, tuple(sorted(p.comp for p in parts)), a,
                _split.body_resource_name(m.resource, body_id),
                tuple(sorted(p.pid for p in parts)), feet=(),
                merged_into=carrier_res, merged_into_written=written,
                cut_components=cut_comps, tris=tris, elevated=True,
                elevated_members=len(grp),
                plan_box=_pc.hull_of(b for i in grp for b in part_boxes[i])
                if part_boxes else _pc.box_of((), parts),
                geom_box=(_pc.hull_of(b for i in grp for b in part_boxes[i])
                          if part_boxes else _pc.box_of((), parts)),
                foot_boxes=(_pc.foot_boxes([b for i in grp for b in part_boxes[i]])
                            if part_boxes else ()),
                fill=(_pc.fill_of(_pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                                  [b for i in grp for b in part_boxes[i]])
                      if part_boxes else 1.0))


#: §16 (3)'s named residual: a body with no carrier the law will accept,
#: anchored on the ground under its own footprint with its authored y
#: kept.  Never at the datum, never dropped from the plan.
OWN_GROUND = "footless_own_ground"


def _own_ground_file(raw: _t.Sequence[_Raw], grp: _t.Sequence[int], m: Member,
                     u: Unit, surface: _ar.Surface, body_id: int,
                     counts: dict[str, int], by_class: dict[str, int],
                     part_boxes: _t.Sequence[_t.Sequence[tuple]] = ()) -> Body:
    """§16 (3): the body written at the GROUND UNDER ITS OWN FOOTPRINT.

    §14 (1) left a footless placement whose unit held no footed body on
    its authored row (``footless_no_carrier``), and §15's search silently
    dropped an elevated body it could find no carrier for — its geometry
    was in no file at all.  §16 (3) gives both the same answer: the file
    is anchored at its footprint centroid, where the design surface is
    read like any other body's, and its AUTHORED y is kept (``y_zero``
    0), so a roof authored 12 m up renders 12 m over the ground it stands
    on instead of on it."""
    parts = [p for i in grp for p in raw[i][0]]
    cls = raw[max(grp, key=lambda i: len(raw[i][0]))][1]
    box = (_pc.hull_of(b for i in grp for b in part_boxes[i]) if part_boxes
           else _pc.box_of((), parts))
    clat, clon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
    z = _pc.ground_under(surface, _pc.foot_boxes(
        [b for i in grp for b in part_boxes[i]]) if part_boxes else (), box)
    off = authored_offset(clat, clon, 0.0, u.anchor[0], u.anchor[1], m.heading_deg)
    a = _ar.Anchor(cls, clat, clon, 0.0,
                   f"{OWN_GROUND}: no carrier the law accepts — the ground "
                   f"under its own footprint, authored y kept", z, off)
    by_class[cls] = by_class.get(cls, 0) + 1
    counts["footless_own_ground"] = counts.get("footless_own_ground", 0) + 1
    tris = tuple(t for i in grp for t in raw[i][5])
    cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                              for p in raw[i][0]}))
    return Body(body_id, cls, tuple(sorted(p.comp for p in parts)), a,
                _split.body_resource_name(m.resource, body_id),
                tuple(sorted(p.pid for p in parts)), feet=(),
                cut_components=cut_comps, tris=tris, elevated=True,
                elevated_members=len(grp), plan_box=box, geom_box=box,
                foot_boxes=(_pc.foot_boxes([b for i in grp for b in part_boxes[i]])
                            if part_boxes else ()),
                fill=(_pc.fill_of(_pc.hull_of(b for i in grp
                                              for b in part_boxes[i]),
                                  [b for i in grp for b in part_boxes[i]])
                      if part_boxes else 1.0))


def _cut_and_file(record: Split, m: Member, write: bool, counts: dict[str, int],
                  splits: list[Split], kept: list[Kept], whole: list[Split],
                  *, always_write: bool) -> None:
    """The OBJ8 cut for one member's bodies, and where the record lands.

    ``always_write`` is §14 (1)'s change: a CARRIED footless placement is
    written even when it is one body, because its row must MOVE to the
    carrier's anchor — where the pre-§14 reading left a one-body placement
    exactly as authored (``one_body``), which for a shared-datum unit is
    the datum point 15.7 m under the building."""
    bodies = record.bodies
    index = record.index
    if len(bodies) < 2 and not always_write:
        counts["kept"] += 1
        counts["one_body"] += 1
        kept.append(Kept(index, m.id, m.resource, "one_body"))
        whole.append(record)
        return
    files: tuple[_split.SplitFile, ...] = ()
    err = ""
    if write:
        cuts = [_split.BodyCut(b.body_id, b.cut_components, b.anchor.offset,
                               b.tris) for b in bodies]
        try:
            res = _split.split_obj8(pristine_path(m), cuts, m.resource,
                                    allow_single=always_write)
        except (OSError, ValueError, IndexError) as exc:
            counts["write_error"] += 1
            err = f"{type(exc).__name__}: {exc}"
        else:
            if res.kept_whole:
                counts["kept"] += 1
                counts[res.kept_whole] = counts.get(res.kept_whole, 0) + 1
                kept.append(Kept(index, m.id, m.resource, res.kept_whole))
                whole.append(record)
                return
            files = res.files
    if err:
        kept.append(Kept(index, m.id, m.resource, err))
        counts["kept"] += 1
        whole.append(record)
        return
    counts["split"] += 1
    counts["files"] += len(files) or len(bodies)
    splits.append(_dc.replace(record, files=files))


@_dc.dataclass
class _Staged:
    """One member of a unit, bodied but not yet cut — §15 (1) makes the
    carrier search a UNIT-WIDE question, so every member's bodies exist
    before any member's file is decided."""

    mi: int
    m: Member
    raw: list[_Raw]
    #: one HULL box per body (feet where it has them, else its parts')
    boxes: list[tuple[float, float, float, float]]
    #: one body's PART boxes — what it actually covers in plan (§14 (3):
    #: the hull is a crude proxy, and the carrier search reads both)
    part_boxes: list[list[tuple[float, float, float, float]]]
    elevated: frozenset[int]
    footless: bool
    #: the member's own GROUND groups (each becomes a body file)
    groups: list[list[int]] = _dc.field(default_factory=list)
    #: ``(body indices, carrier, why)`` — the elevated bodies that ride a
    #: file of ANOTHER member (or, for a footless placement, all of them)
    carried: list[tuple[list[int], _pc.Candidate, str]] = \
        _dc.field(default_factory=list)
    #: §16 (3): body indices with NO carrier the law accepts — each is
    #: written as its own file anchored on the ground under its own
    #: footprint, its authored y kept (``footless_own_ground``)
    own_ground: list[int] = _dc.field(default_factory=list)


def build_splits(plan: RebakePlan, surface: _ar.Surface,
                 pads: _t.Sequence[_ar.PadRing] = (),
                 rims: _t.Sequence[_ar.RimRing] = (),
                 *, write: bool = True, split_tol_m: float = 0.0,
                 elevated_base_m: float = 0.0, line_segment_m: float = 0.0,
                 line_stations_max: int = 0, line_ratio: float = 0.0,
                 line_max_h: float = 0.0, foot_band_m: float = 0.0,
                 carrier_fill_min: float = 0.0,
                 abutments: _t.Sequence[tuple[int, int]] = ()) -> SplitSet:
    """Every placement of ``plan`` cut into its bodies (module doc), the
    bodies COARSENED by ``split_tol_m`` (``[placement] split_tol_m``, 11e
    (1)) and each anchored by the generic rule of 11e (2).
    ``write`` False skips the OBJ8 cut itself and reports bodies only —
    the cheap pass when the question is the body COUNTS.

    A LINE OBJECT whose body spans more than ``line_segment_m``
    (``[placement] line_segment_m``) is first cut into SEGMENTS by
    triangle station (11f (2), :class:`_LineCutter`) — the segments are
    bodies like any other and go on to coarsen and be cut with them, so a
    fence over flat ground still lands in one file.  ``line_ratio`` /
    ``line_max_h`` are 10bb's own ``[rebake]`` shape keys and
    ``foot_band_m`` the plan's ``[basin] contact_band_m``; with any of
    them zero the segment cut is not armed and the pre-11f reading
    stands.

    §13 (owner RULINGS 2026-09-11r/s) rules the ELEVATED body: one whose
    file's intended zero is not the ground (:func:`is_elevated`) NEVER has
    a file of its own — it joins its CARRIER at its authored offset, no
    vertex rewrite, relative heights intact.  §14 (11u/11v) rules the
    FOOTLESS placement the same way.

    §15 (owner RULINGS 2026-09-11ae) rules WHICH body is the carrier, and
    that makes the whole walk one UNIT-WIDE question in four passes:

    1. every member is BODIED — its parts classed, anchored, judged
       elevated or footed;
    2. every FOOTED member's ground bodies are coarsened (§9),
       PLAN-OVERLAP BOUND (§14 (3)) and the bond RE-CUT where the bound
       group's terrain spans more than ``split_tol_m`` (§15 (2)); each
       resulting group is a carrier CANDIDATE;
    3. every ELEVATED body and every FOOTLESS placement takes the
       candidate it STANDS OVER — largest plan overlap, else largest
       contact, else nearest, across the unit and every resource alike
       (§15 (1)).  A carrier in the same member is a group the body
       JOINS; a carrier in another member is a file the body RIDES, at
       that file's anchor and ``y_zero``;
    4. the members are CUT, carriers first.

    Only a unit holding NO footed body at all still keeps a placement
    whole, with the reason ``footless_no_carrier`` — counted and reported
    by name rather than guessed at.

    ``abutments`` are the plan's own 10ay pairs when the caller lifted
    them out of a later-versioned plan (``read_plan``); by default the
    plan's own are used."""
    intra: dict[int, list[tuple[int, int]]] = {}
    member_of_pid: dict[int, tuple[int, int]] = {}
    for ui, u in enumerate(plan.units):
        for mi, m in enumerate(u.members):
            for p in m.parts:
                member_of_pid[p.pid] = (ui, mi)
    for a, b in plan.contacts:
        ka, kb = member_of_pid.get(a), member_of_pid.get(b)
        if ka is not None and ka == kb:
            intra.setdefault(id_of(ka), []).append((a, b))
    pairs = tuple(abutments) or tuple(getattr(plan, "abutments", ()) or ())
    pairs = tuple(plan.contacts) + pairs

    splits: list[Split] = []
    kept: list[Kept] = []
    whole: list[Split] = []
    counts: dict[str, int] = {"placements": 0, "split": 0, "kept": 0, "bodies": 0,
                              "files": 0, "one_body": 0, "anim": 0, "unparsable": 0,
                              "no_bodies": 0, "write_error": 0,
                              # §13 (3) / §14 (4) / §15's reported classes
                              "footless": 0, "elevated_own_files": 0,
                              "footless_carried": 0, "footless_no_carrier": 0,
                              "basin_bodies_bound": 0, "bodies_plan_bound": 0,
                              "groups_re_cut": 0, "elevated_ride_other_file": 0,
                              "footless_own_ground": 0}
    refused: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for ui, u in enumerate(plan.units):
        # ── PASS 1: every member's bodies ────────────────────────────
        staged: list[_Staged] = []
        for mi, m in enumerate(u.members):
            counts["placements"] += 1
            raw = _raw_bodies(m, u, intra.get(id_of((ui, mi)), []), surface,
                              pads, rims, counts, split_tol_m=split_tol_m,
                              elevated_base_m=elevated_base_m,
                              line_segment_m=line_segment_m,
                              line_stations_max=line_stations_max,
                              line_ratio=line_ratio, line_max_h=line_max_h,
                              foot_band_m=foot_band_m)
            counts["bodies_uncoarsened"] = \
                counts.get("bodies_uncoarsened", 0) + len(raw)
            elevated = frozenset(i for i, r in enumerate(raw) if r[4])
            counts["bodies_elevated"] = \
                counts.get("bodies_elevated", 0) + len(elevated)
            boxes = [_pc.box_of(r[3], r[0]) for r in raw]
            # a SEGMENT covers its own station span, not its parent
            # line's: its box IS its footprint (11f (2))
            part_boxes = [([boxes[i]] if r[5] else [p.box for p in r[0]])
                          for i, r in enumerate(raw)]
            staged.append(_Staged(mi, m, list(raw), boxes, part_boxes, elevated,
                                  bool(raw) and len(elevated) == len(raw)))
            if staged[-1].footless:
                counts["footless"] += 1

        # ── PASS 2: the footed members' ground groups = the candidates ─
        cands: list[_pc.Candidate] = []
        for st in staged:
            if st.footless:
                continue
            raw, boxes, part_boxes = st.raw, st.boxes, st.part_boxes
            keys = [(i, r[2], len(r[3])) for i, r in enumerate(raw)]
            classes = [r[1] for r in raw]
            merged = coarsen(keys, split_tol_m, st.elevated, boxes,
                             attach_elevated=False)
            # §14 (2)/(3): ONE RIGID OBJECT IS ONE BODY — every BASIN
            # body of the resource binds (its floor, walls and parapet
            # share the rim's one zero however far the pit's own depth
            # separates their terrain), and so does every pair of bodies
            # that OVERLAP IN PLAN, whatever the contact graph said.
            # the PART boxes, not the body hull: what stands over what
            bound = _pc.bind_plan_overlaps(merged, part_boxes, classes)
            if len(bound) < len(merged):
                counts["bodies_plan_bound"] += len(merged) - len(bound)
                if any(c == _ar.BASIN for c in classes):
                    counts["basin_bodies_bound"] += 1
            # §15 (2): ...and a bond wider than the terrain it stands on
            # is re-cut by §9's own rule
            bound, n_recut = _pc.re_cut_by_terrain(bound, keys, split_tol_m,
                                                  classes)
            counts["groups_re_cut"] += n_recut
            st.groups = bound
            if len(bound) < len(raw) - len(st.elevated):
                counts["placements_coarsened"] = \
                    counts.get("placements_coarsened", 0) + 1
            for gi, g in enumerate(bound):
                feet = tuple(f for i in g for f in raw[i][3])
                parts = [p for i in g for p in raw[i][0]]
                # THE FOOTPRINT, NOT THE FEET: a body's feet are SAMPLES
                # (``foot_samples_max``), and a 60 m hangar whose plan
                # recorded two of them has a two-point box — LEMD's
                # ``LEMD41`` b0, under which the T3 roof then "stood
                # over" nothing.  What a body covers in plan is its
                # PARTS' boxes (a SEGMENT's is its own station span).
                cands.append(_pc.Candidate(
                    st.mi, _split.body_resource_name(st.m.resource, gi),
                    raw[_pc.senior_of(raw, g)][2],
                    frozenset(p.pid for p in parts), len(feet),
                    _pc.hull_of(b for i in g for b in part_boxes[i])
                    or _pc.box_of(feet, parts),
                    part_boxes=_pc.foot_boxes(
                        [b for i in g for b in part_boxes[i]]),
                    group=gi,
                    # §16 (3): A CARRIER IS A SOLID — the class and the
                    # footprint fill decide whether this body may carry
                    # another body's zero at all
                    body_class=raw[_pc.senior_of(raw, g)][1],
                    fill=_pc.fill_of(
                        _pc.hull_of(b for i in g for b in part_boxes[i]),
                        [b for i in g for b in part_boxes[i]])))

        # ── PASS 3: what does each elevated body STAND OVER? ──────────
        adj = _pc.unit_edges(pairs, {p.pid for m in u.members for p in m.parts})
        by_key = {(c.member, c.group): c for c in cands}
        for st in staged:
            if st.footless:
                # §14 (1): a footless placement is ONE body — a footbridge
                # is a rigid span and a terminal roof a rigid plate, and
                # splitting one across two carriers would give its halves
                # two zeros, the very scatter §14 (3) closes
                box = _pc.hull_of(b for bs in st.part_boxes for b in bs)
                c, why = _pc.carrier_for(
                    frozenset(p.pid for r in st.raw for p in r[0]), box, cands,
                    adj, _pc.foot_boxes([b for bs in st.part_boxes for b in bs]),
                    fill_min=carrier_fill_min,
                    ground_under=_pc.ground_under(
                        surface, _pc.foot_boxes(
                            [b for bs in st.part_boxes for b in bs]), box),
                    tol_m=split_tol_m, refusals=refused)
                if c is not None:
                    st.carried = [(list(range(len(st.raw))), c, why)]
                continue
            rides: dict[tuple[int, int], tuple[list[int], str]] = {}
            for i in sorted(st.elevated):
                bx = _pc.hull_of(st.part_boxes[i])
                c, why = _pc.carrier_for(
                    frozenset(p.pid for p in st.raw[i][0]),
                    bx, cands, adj, _pc.foot_boxes(st.part_boxes[i]),
                    fill_min=carrier_fill_min,
                    ground_under=_pc.ground_under(
                        surface, _pc.foot_boxes(st.part_boxes[i]), bx),
                    tol_m=split_tol_m, refusals=refused)
                if c is None:
                    # §16 (3): no carrier the law will accept — the body
                    # anchors on the ground under its OWN footprint with
                    # its authored y kept, never dropped from the plan
                    # (before §16 it was silently left out of every file)
                    st.own_ground.append(i)
                    continue
                if c.member == st.mi:
                    st.groups[c.group].append(i)    # its own file carries it
                    continue
                # §9 STILL RULES THE FILE: a carrier in another member
                # decides the body's ZERO, and where one of this member's
                # own groups already stands at that zero (within
                # ``split_tol_m``) the body joins it — same height, one
                # file fewer.  A split exists only where the terrain
                # differs under the object; §15 (1) says WHICH terrain
                # reading is the body's, not that it must be written
                # alone.
                cz = (None if c.anchor.surface_z is None
                      else float(c.anchor.surface_z) - float(c.anchor.y_zero))
                same = _pc.group_at_zero(st.groups, st.raw, cz, split_tol_m,
                                         _pc.senior_of)
                if same >= 0:
                    counts["elevated_ride_own_file_same_zero"] = \
                        counts.get("elevated_ride_own_file_same_zero", 0) + 1
                    st.groups[same].append(i)
                    continue
                counts["elevated_ride_other_file"] += 1
                rides.setdefault((c.member, c.group), ([], why))[0].append(i)
            st.carried = _pc.merge_rides(rides, by_key, split_tol_m)

        # ── PASS 4: the cut, carriers first ──────────────────────────
        by_mi = {st.mi: st for st in staged}
        written_of: dict[int, bool] = {}
        deps = {st.mi: {c.member for _g, c, _w in st.carried
                        if c.member != st.mi} for st in staged}
        for mi in _pc.cut_order(deps):
            st = by_mi[mi]
            m = st.m
            if st.footless and not st.carried:
                # §16 (3): no carrier the law accepts anywhere in this
                # unit — the placement is written at the GROUND UNDER ITS
                # OWN FOOTPRINT with its authored y kept, never left on
                # its unit's shared-datum row (§14 (1)'s
                # ``footless_no_carrier`` keep is superseded)
                counts["footless_no_carrier"] += 1
                body = _own_ground_file(st.raw, list(range(len(st.raw))), m, u,
                                        surface, 0, counts, by_class,
                                        st.part_boxes)
                counts["bodies"] += 1
                record = Split(_index_of(m.id), m.id, m.resource,
                               m.authored_path, u.anchor[0], u.anchor[1],
                               m.heading_deg, (body,))
                before = len(splits)
                _cut_and_file(record, m, write, counts, splits, kept, whole,
                              always_write=True)
                written_of[mi] = len(splits) > before
                continue
            bodies = ([] if st.footless
                      else _group_bodies(st.raw, st.groups, m, u, counts,
                                         by_class, st.part_boxes))
            for i in st.own_ground:
                bodies.append(_own_ground_file(st.raw, [i], m, u, surface,
                                               len(bodies), counts, by_class,
                                               st.part_boxes))
            for grp, c, why in st.carried:
                cw = written_of.get(c.member, True)
                bodies.append(_carried_file(
                    st.raw, grp, m, u, c, why,
                    c.resource if cw else by_mi[c.member].m.resource, cw,
                    len(bodies), counts, by_class, st.part_boxes))
            counts["bodies"] += len(bodies)
            record = Split(_index_of(m.id), m.id, m.resource, m.authored_path,
                           u.anchor[0], u.anchor[1], m.heading_deg, tuple(bodies))
            before = len(splits)
            if st.footless:
                counts["footless_carried"] += 1
                if not all(b.merged_into_written for b in bodies):
                    counts["footless_carrier_kept_whole"] = \
                        counts.get("footless_carrier_kept_whole", 0) + 1
                _cut_and_file(record, m, write, counts, splits, kept, whole,
                              always_write=True)
            else:
                # §14 (1)'s own sentence, read on the case §14 (3) creates.
                # A ONE-BODY placement is KEPT — its row untouched — and on a
                # SHARED-DATUM row that row is the datum: LEMD's unit:25 puts
                # 171 resources on one point, and 73 of the airport's 104
                # one-body keeps then drape more than 3 m (worst 31.0 m,
                # `Munoza-LEMD73`) from where their own anchor says their
                # zero is.  Binding bodies in plan makes MORE such
                # placements, so the keep is admitted only where the row and
                # the anchor read the SAME surface: otherwise the placement is
                # written at its anchor like any other body file.
                z_row = surface(u.anchor[0], u.anchor[1])
                z_anchor = bodies[0].anchor.surface_z if bodies else None
                off_row = (z_row is not None and z_anchor is not None
                           and abs(float(z_row) - float(z_anchor)) > split_tol_m)
                if off_row and len(bodies) < 2:
                    counts["one_body_off_row"] = counts.get("one_body_off_row", 0) + 1
                _cut_and_file(record, m, write, counts, splits, kept, whole,
                              always_write=off_row)
            written_of[mi] = len(splits) > before
    for k, v in sorted(by_class.items()):
        counts[f"class_{k}"] = v
    # §16 (3): why a candidate was refused the carry — reported, never
    # silent (a refusal that nobody counts is a body quietly on its own
    # ground for a reason no report names)
    for k, v in sorted(refused.items()):
        counts[f"carrier_refused_{k}"] = v
    return SplitSet(tuple(splits), tuple(kept), counts, tuple(whole))


def pristine_path(m: Member) -> str:
    """§4.1's restore-before-read: the ``.anchor_bak`` original when v1's
    y-bake left one, else the member's own authored file.  A split never
    reads a BAKED file — the deltas it carries are the very machinery §8
    retires."""
    bak = m.live_path + ".anchor_bak"
    if _os.path.isfile(bak):
        return bak
    return m.authored_path if _os.path.isfile(m.authored_path) else m.live_path


def id_of(key: tuple[int, int]) -> int:
    return key[0] * 100_000 + key[1]


def _index_of(placement_id: str) -> int:
    """``dsf:obj2950`` -> 2950; ``-1`` when the id does not carry one."""
    digits = "".join(ch for ch in placement_id if ch.isdigit())
    return int(digits) if digits else -1


# ── the join with lane ``v2dsfagl`` (§2's model) ─────────────────────────

def to_placement_records(ss: SplitSet) -> tuple[tuple, tuple]:
    """This lane's :class:`SplitSet` as §2's own ``Split`` / ``Kept``
    records — ``model/placement.py``'s dataclasses, which lane
    ``v2dsfagl`` owns and the DSF writer consumes.

    The two halves meet HERE and only here: §4/§6 decide what the bodies
    are, where each anchor goes and what offset the vertices take; §3
    assigns the new ``OBJECT_DEF`` indices and writes the DSF.  Nothing in
    this function decides anything — a translation, so that neither lane
    grows a copy of the other's model."""
    from ..model import placement as _pm
    splits = tuple(_pm.Split(
        placement=_pm.PlacementRef(s.index, s.resource, s.lon, s.lat, s.heading),
        bodies=tuple(_pm.Body(
            body_id=f"b{b.body_id}", body_class=b.body_class,
            components=tuple(b.components),
            anchor=_pm.Anchor(b.anchor.lon, b.anchor.lat, s.heading),
            anchor_reason=b.anchor.reason, new_resource=b.new_resource,
            authored_offset=tuple(b.anchor.offset),
            elevated_members=b.elevated_members, elevated=b.elevated,
            merged_into=b.merged_into, surface_z=b.anchor.surface_z,
            y_zero=b.anchor.y_zero, plan_box=b.plan_box,
            geom_box=b.geom_box, foot_boxes=b.foot_boxes, fill=b.fill,
            feet=len(b.feet)) for b in s.bodies))
        for s in ss.splits)
    kept = tuple(_pm.Kept(k.index, k.resource, k.reason) for k in ss.kept)
    return splits, kept
