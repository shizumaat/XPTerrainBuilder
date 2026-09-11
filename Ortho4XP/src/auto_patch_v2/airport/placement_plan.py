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

__all__ = ["Body", "Split", "Kept", "SplitSet", "read_plan", "build_splits", "coarsen",
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
                "merged_into": self.merged_into or None}


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


def coarsen(bodies: _t.Sequence[tuple[int, _ar.Anchor, int]], tol_m: float,
            elevated: _t.AbstractSet[int] = frozenset()) -> list[list[int]]:
    """BODY COARSENING (owner RULINGS 2026-09-11e (1); spec §9).

    ``bodies`` are ``(body index, its anchor, its ground-contact vertex
    count)``; the answer is the groups of indices that become ONE file.
    Two bodies of the same placement are one file when their INTENDED-ZERO
    TERRAIN HEIGHTS — the design surface at each body's anchor minus its
    ``y_zero``, i.e. each body's own zero plane in world height — agree
    within ``tol_m``: a split exists only where the terrain DIFFERS under
    the object.  The group is anchored by its SENIOR body (the most
    ground-contact vertices; ties by body order), and the walk is
    senior-first so that "agree" is always measured against the anchor the
    group will actually take — never a chain of pairwise steps that lets a
    group span many times the tolerance.

    A body whose surface reads NOWHERE has no zero plane to compare: all
    of a placement's off-surface bodies are ONE group (no reading is no
    evidence that the terrain differs).  ``tol_m <= 0`` restores round
    one's reading: one file per body.

    ``elevated`` are the bodies standing wholly above
    ``[rebake] elevated_base_m`` — a terminal's interior clutter on a
    mezzanine, a sign on a gantry.  The seat law has always held that such
    a part never votes on a seat and inherits the body it stands over
    (``elevated_base_m``, v1 I-8); at PLACEMENT level that reading is the
    same sentence as 11e (1)'s own: there is no terrain under an elevated
    body for the terrain to DIFFER under, so it never founds a group of
    its own — it joins the group whose anchor is nearest it in plan (and,
    with no ground body in the placement at all, they coarsen among
    themselves like any other).  Measured at OTHH: without this the
    terminals' interior clutter alone made the pack 3.09 files per
    placement against 11e's bar of 2."""
    ground = [i for i in range(len(bodies)) if i not in elevated]
    if not ground:
        ground = list(range(len(bodies)))
        elevated = frozenset()
    order = sorted(ground, key=lambda i: (-bodies[i][2], bodies[i][0]))
    groups: list[list[int]] = []
    zeros: list[float | None] = []
    for i in order:
        _bi, a, _n = bodies[i]
        z = None if a.surface_z is None else float(a.surface_z) - float(a.y_zero)
        placed = False
        if tol_m > 0.0:
            for gi, g0 in enumerate(zeros):
                if (z is None) == (g0 is None) and (
                        z is None or abs(z - g0) <= tol_m):
                    groups[gi].append(i)
                    placed = True
                    break
        elif z is None:
            # no tolerance at all: only the off-surface bodies still merge
            for gi, g0 in enumerate(zeros):
                if g0 is None:
                    groups[gi].append(i)
                    placed = True
                    break
        if not placed:
            groups.append([i])
            zeros.append(z)
    for i in sorted(elevated):
        a = bodies[i][1]
        ml, mo = _ar._m_per_deg(a.lat)
        gi = min(range(len(groups)),
                 key=lambda k: ((bodies[groups[k][0]][1].lat - a.lat) * ml) ** 2
                 + ((bodies[groups[k][0]][1].lon - a.lon) * mo) ** 2)
        groups[gi].append(i)
    return [sorted(g) for g in sorted(groups, key=min)]


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


def build_splits(plan: RebakePlan, surface: _ar.Surface,
                 pads: _t.Sequence[_ar.PadRing] = (),
                 rims: _t.Sequence[_ar.RimRing] = (),
                 *, write: bool = True, split_tol_m: float = 0.0,
                 elevated_base_m: float = 0.0, line_segment_m: float = 0.0,
                 line_stations_max: int = 0, line_ratio: float = 0.0,
                 line_max_h: float = 0.0, foot_band_m: float = 0.0) -> SplitSet:
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
    stands."""
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

    splits: list[Split] = []
    kept: list[Kept] = []
    whole: list[Split] = []
    counts: dict[str, int] = {"placements": 0, "split": 0, "kept": 0, "bodies": 0,
                              "files": 0, "one_body": 0, "anim": 0, "unparsable": 0,
                              "no_bodies": 0, "write_error": 0}
    by_class: dict[str, int] = {}
    for ui, u in enumerate(plan.units):
        for mi, m in enumerate(u.members):
            counts["placements"] += 1
            groups = _bodies_of(m, intra.get(id_of((ui, mi)), []))
            pid_of = {p.pid: p for p in m.parts}
            cutter = _LineCutter(m, line_segment_m, line_stations_max, foot_band_m,
                                 line_ratio, line_max_h, u.anchor[0], u.anchor[1])
            raw: list[tuple[list, str, _ar.Anchor, tuple, bool, tuple]] = []
            for g in groups:
                parts = [pid_of[q] for q in g]
                pieces = cutter.segments(parts)
                if pieces:
                    # 11f (2): the body IS the line, cut into its stations
                    counts["line_bodies_segmented"] = \
                        counts.get("line_bodies_segmented", 0) + 1
                    counts["line_segments"] = \
                        counts.get("line_segments", 0) + len(pieces)
                    for si, (tris, feet) in enumerate(pieces):
                        raw.append((parts, _ar.LINE_SEGMENT,
                                    segment_anchor(feet, surface, si, len(pieces)),
                                    feet, False, tris))
                    continue
                lowest = min(parts, key=lambda p: p.base_y)
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
                raw.append((parts, a.body_class, a, feet,
                            min(p.base_y for p in parts) > elevated_base_m
                            if elevated_base_m > 0.0 else False, ()))
            counts["bodies_uncoarsened"] = counts.get("bodies_uncoarsened", 0) + len(raw)
            elevated = frozenset(i for i, r in enumerate(raw) if r[4])
            counts["bodies_elevated"] = counts.get("bodies_elevated", 0) + len(elevated)
            merged = coarsen([(i, r[2], len(r[3])) for i, r in enumerate(raw)],
                             split_tol_m, elevated)
            if len(merged) < len(raw):
                counts["placements_coarsened"] = counts.get("placements_coarsened", 0) + 1
            bodies: list[Body] = []
            for k, grp in enumerate(merged):
                # the SENIOR body carries the group's anchor (11e (1))
                cands = [i for i in grp if not raw[i][4]] or list(grp)
                senior = max(cands, key=lambda i: (len(raw[i][3]), -i))
                parts = [p for i in grp for p in raw[i][0]]
                a = raw[senior][2]
                off = authored_offset(a.lat, a.lon, a.y_zero, u.anchor[0], u.anchor[1],
                                      m.heading_deg)
                a = _dc.replace(a, offset=off)
                by_class[a.body_class] = by_class.get(a.body_class, 0) + 1
                feet = tuple(f for i in grp for f in raw[i][3])
                if a.reason.startswith("low-side foot ("):
                    counts["anchor_residual"] = counts.get("anchor_residual", 0) + 1
                elif a.surface_z is None:
                    counts["anchor_off_surface"] = counts.get("anchor_off_surface", 0) + 1
                # a SEGMENT is cut by TRIANGLE; its parent component must
                # NOT also be handed to the cutter as a whole component,
                # or this file would claim the whole fence (11f (2))
                tris = tuple(t for i in grp for t in raw[i][5])
                cut_comps = tuple(sorted({p.comp for i in grp if not raw[i][5]
                                          for p in raw[i][0]}))
                bodies.append(Body(k, a.body_class, tuple(sorted(p.comp for p in parts)),
                                   a, _split.body_resource_name(m.resource, k),
                                   tuple(sorted(p.pid for p in parts)), feet=feet,
                                   cut_components=cut_comps, tris=tris))
            counts["bodies"] += len(bodies)
            index = _index_of(m.id)
            record = Split(index, m.id, m.resource, m.authored_path,
                           u.anchor[0], u.anchor[1], m.heading_deg, tuple(bodies))
            if len(bodies) < 2:
                counts["kept"] += 1
                counts["one_body"] += 1
                kept.append(Kept(index, m.id, m.resource, "one_body"))
                whole.append(record)
                continue
            files: tuple[_split.SplitFile, ...] = ()
            err = ""
            if write:
                cuts = [_split.BodyCut(b.body_id, b.cut_components, b.anchor.offset,
                                       b.tris) for b in bodies]
                try:
                    res = _split.split_obj8(pristine_path(m), cuts, m.resource)
                except (OSError, ValueError, IndexError) as exc:
                    counts["write_error"] += 1
                    err = f"{type(exc).__name__}: {exc}"
                else:
                    if res.kept_whole:
                        counts["kept"] += 1
                        counts[res.kept_whole] = counts.get(res.kept_whole, 0) + 1
                        kept.append(Kept(index, m.id, m.resource, res.kept_whole))
                        whole.append(record)
                        continue
                    files = res.files
            if err:
                kept.append(Kept(index, m.id, m.resource, err))
                counts["kept"] += 1
                whole.append(record)
                continue
            counts["split"] += 1
            counts["files"] += len(files) or len(bodies)
            splits.append(_dc.replace(record, files=files))
    for k, v in sorted(by_class.items()):
        counts[f"class_{k}"] = v
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
            authored_offset=tuple(b.anchor.offset)) for b in s.bodies))
        for s in ss.splits)
    kept = tuple(_pm.Kept(k.index, k.resource, k.reason) for k in ss.kept)
    return splits, kept
