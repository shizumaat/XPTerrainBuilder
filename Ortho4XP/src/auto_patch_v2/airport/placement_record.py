"""§2's RECORDS: the placement plan's own product (spec
``object-placement-spec.md`` §2 ``splits`` / ``kept``).

``Body`` / ``Split`` / ``Kept`` / ``SplitSet`` — what ``placement_plan``
computes and ``tools/obj8_split_report`` renders, with the ``to_dict``
shape both censuses read.  Data only: no rule of the placement law lives
here, and the module exists apart from ``placement_plan`` for the
1,000-line law.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import footprint_unit as _fu
from . import obj8_split as _split
from ..model.rebake import Member

__all__ = ["Body", "Split", "Kept", "SplitSet", "Staged"]


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
    #: §16b (4): THE WRITTEN GEOMETRY, sampled — ``(lat, lon, lowest y)``
    #: per :data:`placement_cut.GEOM_CELL_M` cell of the body's own
    #: triangles, thinned to :data:`placement_cut.GEOM_PTS_MAX`.  Every
    #: §16 / §16a number is read HERE and never on ``geom_box``: the box
    #: of a carried body the cut left whole is its CARRIER's patch
    #: (124 m for ``green-TEJ3``, whose written file spans 2,342 m), so
    #: every bar read 0 while the eye read +16 m (11ap).
    geom_pts: tuple[tuple[float, float, float], ...] = ()
    #: §16e (3): THE BRIDGE THIS BODY BELONGS TO — the resource of the
    #: DECK whose model footprint polygon contains its plan centroid (or
    #: comes within 0.5 m of it), else ``""``.  A DERIVED relation, one
    #: per plan (``bridge_family``), published because nothing else in
    #: the plan names a bridge: the ROW puts three of OTHH's on one AGL
    #: and the deck's RING is a bbox that swallows a neighbour's clutter.
    #: The bodies sharing one value are ONE RIGID CLUSTER and rest only
    #: on each other.
    bridge_of: str = ""

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
                "family_of": a.family,
                # §16g (1) (owner RULINGS 2026-09-13bo): the FOOTPRINT
                # UNIT this body belongs to.  The same value as
                # ``family_of`` — one relation with two names while the
                # readers of §16f's are still on the tree — published
                # apart so a census can tell which law seated the body.
                "unit_of": (a.family
                            if str(a.reason).startswith(_fu.UNIT_REASON)
                            else ""),
                # §16g (6) (owner RULINGS 2026-09-13cn): the two units
                # this body CONNECTS, or "" — an identified connector is
                # seated on its HIGH end's unit datum and never falls to
                # §16c's low-side foot.
                "connector_of": a.connector_of,
                "fill": self.fill,
                "geom_pts": [[round(q[0], 8), round(q[1], 8), round(q[2], 3)]
                             for q in self.geom_pts],
                "bridge_of": self.bridge_of or None,
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
    #: §16f (3): the object FAMILIES derived from this plan, each with
    #: its members, its one zero plane and the pad or ground it took —
    #: a censused fact, published beside the splits
    families: tuple[_t.Any, ...] = ()
    #: §16g (5) (owner RULINGS 2026-09-13bw): the PLAN-WIDE footprint
    #: units as ``(lat0, lon0, lat1, lon1, zero)`` — the plane a placement
    #: standing inside one is seated at by its DSF row.  Published here
    #: because the WRITER is where a dropped multi-anchor placement is
    #: first seen beside the plan (``placement_write.build_plan``).
    unit_seats: tuple[tuple[float, float, float, float, float], ...] = ()

    @property
    def all(self) -> tuple[Split, ...]:
        return self.splits + self.whole

    def to_dict(self) -> dict[str, _t.Any]:
        return {"splits": [s.to_dict() for s in self.splits],
                "kept": [k.to_dict() for k in self.kept],
                "counts": dict(self.counts)}




@_dc.dataclass
class Staged:
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
    #: §16c (4): one authored TOP per entry of ``part_boxes``
    part_tops: list[list[float]] = _dc.field(default_factory=list)
    #: the design surface, so a piece §16a (1)'s carrier cut makes reads
    #: its own terrain group like every other body (§16b (1))
    surface: _t.Any = None
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
    #: §16 (3): the body GROUPS with no carrier the law accepts — each
    #: is written as ONE file anchored on the ground under its own
    #: footprint, its authored y kept (``footless_own_ground``).  A GROUP
    #: and not a body since §16b (2): the carrier question is asked per
    #: terrain group, so the answer "nobody" is given per group too.
    own_ground: list[list[int]] = _dc.field(default_factory=list)
    #: §16e (3): one BRIDGE key per raw body — the deck whose model
    #: footprint contains it, or ``""``.  §16e (3) is WITHDRAWN (RULINGS
    #: 2026-09-13ae): nothing BINDS or FILTERS on it, and it is carried
    #: here only so the body can PUBLISH it (``Body.bridge_of``) and the
    #: census read it.
    bridge: list[str] = _dc.field(default_factory=list)
    #: §16d (1): one per ``raw`` entry — the PLAN HULL OF ITS OWN
    #: TRIANGLES where a cut gave it any, else ``None``.  A raw body the
    #: cut made carries its ``box`` from its FEET (11f (2): a segment
    #: covers its own station span), which is the right plan footprint
    #: and the wrong GEOM box: the writer puts the TRIANGLES in the file,
    #: so ``geom_box`` is hulled over these as well as the part boxes.
    geom_boxes: list[tuple | None] = _dc.field(default_factory=list)


