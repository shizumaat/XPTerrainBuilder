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
  the only rule reading a seat target, does not apply to a file cut;
* a LINE OBJECT binds nothing (10bb): each line component is its own
  body anchored at its own mid-foot, so a fence drapes segment by
  segment instead of chaining 38 parts onto one foot;
* an ELEVATED DECK abutting a kerb (10ay/11a) takes no anchor of its own
  (§6): inside the placement it is already the same body, and across
  placements this reports the merge target and keeps the deck's
  placement as authored — moving geometry BETWEEN two authored files is
  not §4's writer.

THE CLASS OF A BODY (§6) is read off the plan and the emitted surface:
``basin`` when the body's lowest component stands inside an emitted
``structure_rim`` ring (the basin was cut to these members, 10ba, so
containment IS the membership test at this stage; §14a then asks which
of those members FORM the pit and which merely stand in it); ``deck``
from the member's deck verdict; ``plate_only`` from its wall-plate seat
(05n-4); ``line_segment`` from the part's own 10bb verdict; ``skirted``
from 10ag's reader; ``building`` when a skirt-less body stands inside an
emitted object pad; else ``other``.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import math
import os as _os
import typing as _t

from ..model.rebake import Member, Part, RebakePlan, Unit
from . import anchor_rule as _ar
from . import basin_ring as _br
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
    # §14a: the ring carries its HEIGHTS (§24 (1) makes them the apron's)
    z_id = {v[0]: v[3] for v in d["vertices"]}
    pads = tuple(_ar.PadRing(f["ref"],
                             tuple(by_id[i] for i in f["ring"] if i in by_id))
                 for f in d["faces"]
                 if f["role"] == PAD_FACE_ROLE and len(f["ring"]) >= 3)
    rims = tuple(_ar.RimRing(b["ref"],
                             tuple(by_id[i] for i in b["vertices"] if i in by_id),
                             tuple(float(z_id[i]) for i in b["vertices"]
                                   if i in by_id))
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
    #: §16a (2): how far this body's own zero stands from the ground
    #: under its own feet — what says whether the law would let it CARRY
    #: anything, and therefore whether the census may call it "the body
    #: beneath" (one relation, one reading).  ``None`` off-sheet.
    ground_off: float | None = None
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
                "ground_off": self.ground_off,
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


# ── the cuts and the bodies of one placement (``placement_cut``) ─────────
# §10's segment cut, §16 (2)'s terrain cut and the body formation they
# feed live next door (the 1,000-line law); they are re-exported here
# because every caller and every twin reads them as this module's.
from .placement_cut import (GROUND_CELL_M, _bodies_of,  # noqa: E402
                            _cut_parts_by_terrain, _LineCutter, _part_zero,
                            _plan_span_m, _Raw, _raw_bodies, _rim_of,
                            authored_latlon, pristine_path, segment_anchor)


def _group_bodies(raw: _t.Sequence[_Raw], merged: _t.Sequence[_t.Sequence[int]],
                  m: Member, u: Unit, counts: dict[str, int],
                  by_class: dict[str, int],
                  part_boxes: _t.Sequence[_t.Sequence[tuple]] = (),
                  ground_off: _t.Sequence["float | None"] = ()) -> list[Body]:
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
                           # §16a (2): what the law would ask of this body
                           # before letting it carry anything — the census
                           # asks the same before calling it "beneath"
                           ground_off=(ground_off[k]
                                       if k < len(ground_off) else None),
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
    #: §16 (2): did the TERRAIN CUT divide this member's bodies?
    #: Reported; §16a (1) took the decision it used to carry (a carried
    #: body is cut by its CARRIER, never by the ground under itself).
    terrain_cut: bool = False
    #: the member's ONE cutter — pass 1's segment and terrain cuts and
    #: §16a (1)'s carrier cut read the same parsed OBJ8 through it
    cutter: _t.Any = None
    #: the member's own GROUND groups (each becomes a body file)
    groups: list[list[int]] = _dc.field(default_factory=list)
    #: §16a (2): one per ``groups`` entry — how far that group's own zero
    #: stands from the ground under its own feet (``Candidate.ground_off``).
    #: Published on the body so the CENSUS reads the same population the
    #: carrier search does: a candidate the law refuses to carry anything
    #: is not something the instrument may call "the body beneath".
    ground_off: list[float | None] = _dc.field(default_factory=list)
    #: ``(body indices, carrier, why)`` — the elevated bodies that ride a
    #: file of ANOTHER member (or, for a footless placement, all of them)
    carried: list[tuple[list[int], _pc.Candidate, str]] = \
        _dc.field(default_factory=list)
    #: §16 (3): body indices with NO carrier the law accepts — each is
    #: written as its own file anchored on the ground under its own
    #: footprint, its authored y kept (``footless_own_ground``)
    own_ground: list[int] = _dc.field(default_factory=list)


def _carrier_pieces(st: "_Staged", grp: list[int],
                    over: _t.Sequence[tuple[_pc.Candidate, str]],
                    counts: dict[str, int], tol_m: float = 0.0
                    ) -> list[tuple[list[int], _pc.Candidate, str]]:
    """§16a (1): A CARRIED BODY IS CUT WHERE ITS CARRIER IS CUT.

    ``over`` is :func:`placement_carrier.carriers_for`'s ranked list of
    the carrier groups this body stands over.  With one of them the body
    is not cut at all (§14 (1)'s rigid span).  With several — a roof over
    walls the terrain re-cut into three groups, a roof over two buildings
    — the body's TRIANGLES are assigned to the carrier group each stands
    over and one piece is made per group, each riding that group's zero
    at the authored offset.  The ground under the carried body is never
    read: that was §16 (3)'s reading, and it put the garage pavilions
    −1.27 … +3.70 m against the slab they sit on.

    New pieces are appended to ``st.raw`` / ``st.boxes`` /
    ``st.part_boxes`` (the three parallel lists every later pass reads by
    index) and the source body's own index is left behind, referenced by
    nothing."""
    if len(over) < 2:
        return [(list(grp), over[0][0], over[0][1])]
    # §9 STILL RULES THE FILE: carriers standing at ONE zero (within
    # ``split_tol_m``) are one reading of the terrain, and cutting the
    # body against them would make pieces ``merge_rides`` puts straight
    # back into one file.  Dropping them before the cut changes no
    # answer and is most of the cut's cost at a FLAT airport — OTHH
    # asked for 3,869 cuts and needs 319 of them.
    if tol_m > 0.0:
        keep, zeros = [], []
        for c, why in over:
            z = (None if c.anchor.surface_z is None
                 else float(c.anchor.surface_z) - float(c.anchor.y_zero))
            if z is not None and any(abs(z - q) <= tol_m for q in zeros):
                continue
            keep.append((c, why))
            if z is not None:
                zeros.append(z)
        over = keep
        if len(over) < 2:
            return [(list(grp), over[0][0], over[0][1])]
    parts = [p for i in grp for p in st.raw[i][0]]
    pieces = st.cutter.carrier_groups(parts, [c.part_boxes for c, _w in over])
    if not pieces:
        return [(list(grp), over[0][0], over[0][1])]
    counts["carried_bodies_cut_by_carrier"] = \
        counts.get("carried_bodies_cut_by_carrier", 0) + 1
    counts["carrier_pieces"] = counts.get("carrier_pieces", 0) + len(pieces)
    senior = st.raw[max(grp, key=lambda i: len(st.raw[i][0]))]
    out: list[tuple[list[int], _pc.Candidate, str]] = []
    for k, tris, box in pieces:
        bi = len(st.raw)
        st.raw.append(([p for p in parts], senior[1], senior[2], (), True, tris))
        st.boxes.append(box)
        st.part_boxes.append([box])
        out.append(([bi], over[k][0], over[k][1]))
    return out


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
       (§15 (1)); a §14a (2) FLOOR member takes none.  A carrier in the
       same member is a group the body JOINS; one in another member is a
       file the body RIDES, at that file's anchor and ``y_zero``;
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
        # §14a (2): each basin ring's DEPTH, read ONCE per unit — a pit is
        # authored as several resources on one row, so no member can read
        # it from its own parts
        staged: list[_Staged] = []
        for mi, m in enumerate(u.members):
            counts["placements"] += 1
            _cut0 = (counts.get("bodies_re_cut_by_terrain", 0)
                     + counts.get("bodies_re_cut_by_triangle", 0))
            cutter = _LineCutter(m, line_segment_m, line_stations_max,
                                 foot_band_m, line_ratio, line_max_h,
                                 u.anchor[0], u.anchor[1])
            raw = _raw_bodies(m, u, intra.get(id_of((ui, mi)), []), surface,
                              pads, rims, counts, cutter=cutter,
                              split_tol_m=split_tol_m,
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
                                  bool(raw) and len(elevated) == len(raw),
                                  cutter=cutter,
                                  terrain_cut=(counts.get("bodies_re_cut_by_terrain", 0)
                                               + counts.get("bodies_re_cut_by_triangle", 0)
                                               ) > _cut0))
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
            # §14a (1): a basin's ARC pieces are held apart by their rim
            bind_keys = [_br.bind_key_of(r[2].reason) for r in raw]
            bound = _pc.bind_plan_overlaps(merged, part_boxes, classes,
                                           bind_keys=bind_keys)
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
                _hull = _pc.hull_of(b for i in g for b in part_boxes[i]) \
                    or _pc.box_of(feet, parts)
                _fb = _pc.foot_boxes([b for i in g for b in part_boxes[i]])
                # §16a (2): THE GROUND CHECK IS ON THE CARRIER, read ONCE
                # here — how far this body's own zero stands from the
                # ground under its OWN feet.  A body that fails it is
                # mis-anchored and would carry its error to whatever
                # rides it; the ground under the CARRIED body is never
                # compared (§16 (3)'s reading, deleted by 11aj).
                _anc = raw[_pc.senior_of(raw, g)][2]
                _off = _pc.anchor_ground_off(_anc, feet, surface)
                st.ground_off.append(_off)
                # THE FOOTPRINT, NOT THE FEET: a body's feet are SAMPLES
                # (``foot_samples_max``), and a 60 m hangar whose plan
                # recorded two of them has a two-point box — LEMD's
                # ``LEMD41`` b0, under which the T3 roof then "stood
                # over" nothing.  What a body covers in plan is its
                # PARTS' boxes (a SEGMENT's is its own station span).
                cands.append(_pc.Candidate(
                    st.mi, _split.body_resource_name(st.m.resource, gi),
                    _anc, frozenset(p.pid for p in parts), len(feet),
                    _hull, part_boxes=_fb, ground_off=_off,
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
            # §14 (1): a FOOTLESS placement is ONE body — a footbridge is
            # a rigid span and a terminal roof a rigid plate.  §16a (1):
            # and the only thing that divides either of them is their
            # CARRIER — the pieces are the carrier's terrain groups
            # intersected with the body's own footprint, one per group,
            # each riding that group's zero at the authored offset.
            # §14a (2): a FLOOR member takes NO carrier
            targets, floor = _br.carrier_targets(
                st.raw, st.part_boxes, st.elevated, st.footless)
            if floor:
                counts["basin_floor_own_ground"] = \
                    counts.get("basin_floor_own_ground", 0) + len(floor)
            st.own_ground.extend(i for i in sorted(floor)
                                 if st.footless or i in st.elevated)
            rides: dict[tuple[int, int], tuple[list[int], str]] = {}
            for grp, gboxes in targets:
                bx = _pc.hull_of(gboxes)
                over = _pc.carriers_for(
                    frozenset(p.pid for i in grp for p in st.raw[i][0]),
                    bx, cands, adj, _pc.foot_boxes(gboxes),
                    fill_min=carrier_fill_min, tol_m=split_tol_m,
                    refusals=refused)
                if not over:
                    # §16 (3): no carrier the law will accept — the body
                    # anchors on the ground under its OWN footprint with
                    # its authored y kept, never dropped from the plan
                    # (before §16 it was silently left out of every file).
                    # A FOOTLESS placement takes pass 4's own branch.
                    if not st.footless:
                        st.own_ground.extend(grp)
                    continue
                # the same cap the terrain cut takes (``[rebake]
                # line_object_stations_max``); 0 means uncapped
                for bi, c, why in _carrier_pieces(
                        st, grp,
                        over[:line_stations_max] if line_stations_max > 0 else over,
                        counts, split_tol_m):
                    if c.member == st.mi:
                        st.groups[c.group].extend(bi)   # its own file carries it
                        continue
                    # §9 STILL RULES THE FILE: a carrier in another member
                    # decides the body's ZERO, and where one of this
                    # member's own groups already stands at that zero
                    # (within ``split_tol_m``) the body joins it — same
                    # height, one file fewer.  A split exists only where
                    # the terrain differs under the object; §15 (1) says
                    # WHICH terrain reading is the body's, not that it
                    # must be written alone.
                    cz = (None if c.anchor.surface_z is None
                          else float(c.anchor.surface_z) - float(c.anchor.y_zero))
                    same = _pc.group_at_zero(st.groups, st.raw, cz, split_tol_m,
                                             _pc.senior_of)
                    if same >= 0:
                        counts["elevated_ride_own_file_same_zero"] = \
                            counts.get("elevated_ride_own_file_same_zero", 0) + 1
                        st.groups[same].extend(bi)
                        continue
                    if not st.footless:
                        counts["elevated_ride_other_file"] += 1
                    rides.setdefault((c.member, c.group), ([], why))[0].extend(bi)
            st.carried = _pc.merge_rides(rides, by_key, split_tol_m)

        # ── PASS 4: the cut, carriers first ──────────────────────────
        by_mi = {st.mi: st for st in staged}
        written_of: dict[int, bool] = {}
        deps = {st.mi: {c.member for _g, c, _w in st.carried
                        if c.member != st.mi} for st in staged}
        for mi in _pc.cut_order(deps):
            st = by_mi[mi]
            m = st.m
            if st.footless and not st.carried and not st.own_ground:
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
                                         by_class, st.part_boxes,
                                         st.ground_off))
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
            ground_off=b.ground_off,
            feet=len(b.feet)) for b in s.bodies))
        for s in ss.splits)
    kept = tuple(_pm.Kept(k.index, k.resource, k.reason) for k in ss.kept)
    return splits, kept
