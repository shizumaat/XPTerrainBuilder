"""THE PLACEMENT PLAN — data only (spec ``docs/specs/auto-patch-v2/
object-placement-spec.md`` §2; owner RULINGS 2026-09-11b).

X-Plane places an object's ORIGIN on the terrain under its placement
anchor.  The plan is therefore everything the two writers need and
nothing else:

* ``conversions`` (§3, §5) — the ``OBJECT_MSL`` / ``OBJECT_AGL``
  placements of PACK resources that become plain ``OBJECT`` ("on
  ground") rows in the DSF text.  Stock/library resources are never
  converted (09z (2): X-Plane places them exactly as authored).
* ``splits`` (§4, §6) — one authored placement replaced by N bodies,
  each a new ``.obj`` beside the original with its OWN anchor placed
  where the design surface equals that body's intended zero.
* ``kept`` — placements left exactly as authored, with the reason
  (stock resource, no genuine solid, a body that cannot be cut: §4.4).

``index`` is the placement's ORDINAL in the dump (0-based, dump order —
the identity ``airport/dsf.read_dump`` and ``airport/dsf_write`` both
count in), NOT the ``OBJECT_DEF`` index: def indices are shared by many
placements and are renumbered by nothing, so they identify no row.

The plan is written beside the patch as ``o4_v2_placement_<ICAO>.json``
(it replaces ``o4_v2_rebake_<ICAO>.json``).  JSON round-trips exactly.
No numpy, no shapely, no I/O here.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import typing as _t

__all__ = [
    "PLAN_VERSION", "PLAN_FILENAME", "BACKUP_SUFFIX", "PROVENANCE_FILENAME",
    "CUT_MARK",
    "KIND_ON_GROUND", "KIND_MSL", "KIND_AGL", "CONVERTIBLE_KINDS",
    "BODY_CLASSES", "Provenance", "Conversion", "Anchor", "PlacementRef",
    "Body", "Split", "Kept", "PlacementPlan", "MslSeat", "Rider",
]

#: 1: the first plan (11b — conversions, splits, kept).
PLAN_VERSION = 1
#: ``<patch dir>/o4_v2_placement_<ICAO>.json``.
PLAN_FILENAME = "o4_v2_placement_{icao}.json"
#: The pristine DSF kept beside the written one (the OBJ discipline of
#: v1's ``object_rebake``: a rerun reads the BACKUP, never the
#: already-edited file, so the write is idempotent).
BACKUP_SUFFIX = ".anchor_bak"
#: Written beside the DSF by ``airport/dsf_write.write_pack``.
PROVENANCE_FILENAME = "o4_placement_provenance.json"
#: Every cut body file this writer makes carries it (``obj8_split``'s
#: provenance line); it is what says a file on a split's name is OURS to
#: replace or remove.  Lives here so both the write half
#: (``placement_write``) and the DSF writer (``dsf_write``) read ONE
#: definition without an import cycle.
CUT_MARK = "# o4 split of "

#: The DSF row keywords.  ``OBJECT`` is X-Plane's "on ground": no
#: elevation column, the origin sits on the terrain under the anchor.
KIND_ON_GROUND = "OBJECT"
KIND_MSL = "OBJECT_MSL"
KIND_AGL = "OBJECT_AGL"
#: What §5 converts (both carry an elevation column).
CONVERTIBLE_KINDS = (KIND_MSL, KIND_AGL)

#: ``Body.body_class`` (§2, §6).  Serialised under the JSON key
#: ``"class"`` — ``class`` is a Python keyword, so the field is not.
BODY_CLASSES = ("building", "skirted", "basin", "line_segment", "deck",
                "plate_only", "other")


def _f(x: _t.Any) -> float:
    return float(x)


@_dc.dataclass(frozen=True)
class Provenance:
    """What the write recorded about its input (§3.3): the sha256 of the
    dump text it edited, the engine version, the law digest of the
    configuration the plan was built under, and the counts."""

    dump_sha: str
    engine_version: str
    law_digest: str
    counts: _t.Mapping[str, int] = _dc.field(default_factory=dict)

    def to_dict(self) -> dict[str, _t.Any]:
        return {"dump_sha": self.dump_sha, "engine_version": self.engine_version,
                "law_digest": self.law_digest, "counts": dict(self.counts)}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Provenance":
        return cls(str(d.get("dump_sha", "")), str(d.get("engine_version", "")),
                   str(d.get("law_digest", "")),
                   {str(k): int(v) for k, v in dict(d.get("counts", {})).items()})


@_dc.dataclass(frozen=True)
class MslSeat:
    """§16g (5) (owner RULINGS 2026-09-13bw; owner 2026-09-11a/b "you can
    just change the elevation of each placement"): one placement seated
    by its DSF ROW — ``OBJECT_MSL lat lon heading elevation``.

    This is how a MULTI-ANCHOR resource is seated: one file placed at N
    anchors that need N different seats cannot carry a per-placement
    offset in the OBJ8, so the offset goes where it belongs, on the row.
    KCLT's passengers and seats (owner 13bj item 1) are 205 such
    placements the plan DROPS, and no family law reaches them."""

    index: int
    resource: str
    lon: float
    lat: float
    heading_deg: float
    #: the absolute MSL elevation written into the row
    elevation: float
    #: what chose it — ``unit`` (a footprint unit's plane) or ``surface``
    why: str = ""

    def to_dict(self) -> dict[str, _t.Any]:
        return {"index": self.index, "resource": self.resource,
                "lon": self.lon, "lat": self.lat,
                "heading": self.heading_deg,
                "elevation": self.elevation, "why": self.why}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "MslSeat":
        return cls(int(d["index"]), str(d["resource"]), _f(d["lon"]),
                   _f(d["lat"]), _f(d.get("heading", 0.0)),
                   _f(d.get("elevation", 0.0)), str(d.get("why", "")))


@_dc.dataclass(frozen=True)
class Rider:
    """jetway-strip spec §4 (issue #31): a placement the plan holds NO
    geometry for (an ``.agp``, a dropped multi-anchor resource, a ``lib/``
    resource) that RIDES the unit whose outline it stands within
    ``reach_m`` of.  No body; a SEAT RECORD on its carrier.

    ``seat_z`` = the host unit's datum + the authored offset (the 11b
    conversion); ``seat_why``: ``on_ground`` (the terrain at the anchor
    IS the datum, or an ``.agp``, whose MSL row is unverified — §4 (3)),
    ``msl_written`` (a clamped gate: the row carries ``seat_z``) or
    ``no_host``.  ``terrain_z`` is the design surface at the anchor."""

    index: int
    resource: str
    lon: float
    lat: float
    heading_deg: float
    kind_before: str
    host_unit: str
    host_pid: str
    anchor_gap_m: float
    reach_m: float
    strip_id: str
    seat_z: float | None
    seat_why: str
    terrain_z: float | None = None

    def to_dict(self) -> dict[str, _t.Any]:
        return {"index": self.index, "resource": self.resource,
                "lon": self.lon, "lat": self.lat, "heading": self.heading_deg,
                "kind_before": self.kind_before, "host_unit": self.host_unit,
                "host_pid": self.host_pid, "anchor_gap_m": self.anchor_gap_m,
                "reach_m": self.reach_m, "strip_id": self.strip_id,
                "seat_z": self.seat_z, "seat_why": self.seat_why,
                "terrain_z": self.terrain_z}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Rider":
        sz, tz = d.get("seat_z"), d.get("terrain_z")
        return cls(int(d["index"]), str(d["resource"]), _f(d["lon"]),
                   _f(d["lat"]), _f(d.get("heading", 0.0)),
                   str(d.get("kind_before", "OBJECT")),
                   str(d.get("host_unit", "")), str(d.get("host_pid", "")),
                   _f(d.get("anchor_gap_m", 0.0)), _f(d.get("reach_m", 0.0)),
                   str(d.get("strip_id", "")),
                   None if sz is None else _f(sz), str(d.get("seat_why", "")),
                   None if tz is None else _f(tz))


@_dc.dataclass(frozen=True)
class Conversion:
    """One placement that becomes an on-ground ``OBJECT`` row (§3.2a).
    ``z_before`` is the elevation column dropped: an absolute MSL height
    for ``OBJECT_MSL``, an AGL offset for ``OBJECT_AGL``."""

    index: int
    resource: str
    lon: float
    lat: float
    heading_deg: float
    kind_before: str
    z_before: float

    def to_dict(self) -> dict[str, _t.Any]:
        return {"index": self.index, "resource": self.resource, "lon": self.lon,
                "lat": self.lat, "heading": self.heading_deg,
                "kind_before": self.kind_before, "z_before": self.z_before}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Conversion":
        return cls(int(d["index"]), str(d["resource"]), _f(d["lon"]), _f(d["lat"]),
                   _f(d.get("heading", 0.0)), str(d["kind_before"]),
                   _f(d.get("z_before", 0.0)))


@_dc.dataclass(frozen=True)
class Anchor:
    """A placed anchor: where X-Plane samples the terrain for the body
    (§6).  ``heading_deg`` is the placement heading (unchanged by the
    split: X-Plane rotates about the anchor)."""

    lon: float
    lat: float
    heading_deg: float

    def to_dict(self) -> dict[str, float]:
        return {"lon": self.lon, "lat": self.lat, "heading": self.heading_deg}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Anchor":
        return cls(_f(d["lon"]), _f(d["lat"]), _f(d.get("heading", 0.0)))


@_dc.dataclass(frozen=True)
class PlacementRef:
    """The ORIGINAL placement a split replaces."""

    index: int
    resource: str
    lon: float
    lat: float
    heading_deg: float

    def to_dict(self) -> dict[str, _t.Any]:
        return {"index": self.index, "resource": self.resource, "lon": self.lon,
                "lat": self.lat, "heading": self.heading_deg}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "PlacementRef":
        return cls(int(d["index"]), str(d["resource"]), _f(d["lon"]), _f(d["lat"]),
                   _f(d.get("heading", 0.0)))


@_dc.dataclass(frozen=True)
class Body:
    """One rigid body cut out of an authored file (§4).  ``components``
    are indices into ``auto_patch_v2.airport.obj8.solid_components`` of
    the AUTHORED file; ``authored_offset`` is the rigid translation
    ``(dx, dy, dz)`` applied to its vertices in the authored frame so
    that the body's foot lands on the terrain at ``anchor`` (§4.3, §6).
    ``new_resource`` is pack-relative, as an ``OBJECT_DEF`` spells it."""

    body_id: str
    body_class: str
    components: tuple[int, ...]
    anchor: Anchor
    anchor_reason: str
    new_resource: str
    authored_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    #: §13: how many ELEVATED bodies this file CARRIES at their authored
    #: offset (a roof, a deck, a tower part — they keep their height
    #: relative to the carrier and never take an anchor of their own)
    elevated_members: int = 0
    #: §14 (1): this whole file is FOOTLESS — it stands on no ground
    #: contact and rides its carrier's anchor and zero
    elevated: bool = False
    #: §14 (1): the CARRIER's file, when this one is carried ("" if not).
    #: The §14 (4) census reads it: a footless body with no carrier is
    #: either at the datum or on the ground, and both bars are 0.
    merged_into: str = ""
    #: the design surface under the anchor (``None`` outside every graded
    #: face) and the body's intended zero in its authored frame — the two
    #: numbers the §14 (4) SPREAD reads (``surface_z - y_zero`` is the
    #: file's zero plane in world height)
    surface_z: float | None = None
    y_zero: float = 0.0
    #: §15 (3): the body's PLAN box ``(lat0, lon0, lat1, lon1)`` and how
    #: many GROUND-CONTACT FEET it holds.  The stands-over census reads
    #: both: which footed body of another placement lies under this one's
    #: footprint, and whether this one is footed at all.  A foot census
    #: cannot see the class — a carried body has no feet, and a body on
    #: its own low-side foot reads every foot of its own as lawful.
    plan_box: tuple[float, float, float, float] | None = None
    feet: int = 0
    #: §16 (2): the body's OWN GEOMETRY box — the hull of every part it
    #: holds, elevated parts included, where ``plan_box`` is the GROUND
    #: footprint the stands-over relation reads.  The §16 census reads
    #: ``float = zero - ground_under_geometry`` here: the ground under a
    #: carried roof is the roof's own ground, never its carrier's box.
    geom_box: tuple[float, float, float, float] | None = None
    #: §16 (3): the body's FOOTPRINT boxes (its largest part boxes, at
    #: most :data:`FOOT_BOXES_MAX`) — the geometry the stands-over
    #: relation is measured on by BOTH the carrier search and the census,
    #: because a body's hull box is a crude proxy for its footprint (a
    #: fence segment's box contains a garage roof its footprint never
    #: touches).  Bounded because a plan carrying every part box of every
    #: body doubles its own size.
    foot_boxes: tuple[tuple[float, float, float, float], ...] = ()
    #: §16 (3): the body's FOOTPRINT FILL — whether it is a SOLID that may
    #: carry another body's zero (and therefore, for the census, whether
    #: it is a body another body can be said to STAND OVER at all)
    fill: float = 1.0
    #: §16a (2): how far this body's own zero stands from the ground
    #: under its OWN feet — the law's carrier test, published so the
    #: census asks it too before calling this body "the body beneath".
    #: ``None`` off-sheet, and for a body that is itself carried.
    ground_off: float | None = None
    #: §16b (4): THE WRITTEN GEOMETRY, sampled — ``(lat, lon, lowest y)``
    #: per cell of the body's own triangles.  Every §16 / §16a number is
    #: read here and never on ``geom_box``: a carried body's box is its
    #: CARRIER's patch, which is why every bar read 0 while the eye read
    #: +16 m over the ground (11ap).
    geom_pts: tuple[tuple[float, float, float], ...] = ()
    #: §16e: this body is anchored on a DATUM — a crest plate or a deck
    #: top, an authored height the law puts AT the ground.  Published
    #: because its ``y_zero`` is +5 … +10 m BY CONSTRUCTION and every
    #: reader that judges a high ``y_zero`` (§13's "elevated bodies as
    #: own files", bar 0) would otherwise count the law as its defect.
    datum: bool = False
    #: §16e (3): THE BRIDGE THIS BODY BELONGS TO — the DECK resource
    #: whose model footprint polygon contains its plan centroid (or comes
    #: within 0.5 m of it), else ``""``.  Published because nothing else
    #: in either plan names a bridge (``airport/bridge_family``): the ROW
    #: puts three of OTHH's on one AGL and the deck's RING is a bbox.
    bridge_of: str = ""
    #: §16f (1): THE FAMILY THIS BODY'S ZERO PLANE BELONGS TO — the
    #: connected plan cluster of one shared-datum unit whose members take
    #: one zero (``airport/placement_family``), else ``""``.  A carried
    #: body takes its carrier's anchor and so publishes its family.
    family_of: str = ""
    #: §16g (1) (owner RULINGS 2026-09-13bo): the FOOTPRINT UNIT
    unit_of: str = ""
    #: §16g (6) (owner RULINGS 2026-09-13cn): ``"<unit a>|<unit b>"`` where
    #: this body CONNECTS two footprint units (an empty side is open
    #: ground).  It is seated on its HIGH end's unit datum until §10's
    #: station cut is written for it; the pair is published because the
    #: census has to be able to name the two units the piece must reach.
    connector_of: str = ""

    def to_dict(self) -> dict[str, _t.Any]:
        return {"body_id": self.body_id, "class": self.body_class,
                "components": list(self.components), "anchor": self.anchor.to_dict(),
                "anchor_reason": self.anchor_reason, "new_resource": self.new_resource,
                "authored_offset": list(self.authored_offset),
                "elevated_members": self.elevated_members,
                "elevated": self.elevated, "merged_into": self.merged_into or None,
                "surface_z": self.surface_z, "y_zero": self.y_zero,
                "plan_box": None if self.plan_box is None else list(self.plan_box),
                "feet": self.feet,
                "geom_box": None if self.geom_box is None else list(self.geom_box),
                "foot_boxes": [list(b) for b in self.foot_boxes],
                "fill": self.fill, "ground_off": self.ground_off,
                "datum": self.datum, "bridge_of": self.bridge_of or None,
                "family_of": self.family_of or None,
                "unit_of": self.unit_of or None,
                "connector_of": self.connector_of or None,
                "geom_pts": [[round(q[0], 8), round(q[1], 8), round(q[2], 3)]
                             for q in self.geom_pts]}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Body":
        off = d.get("authored_offset", (0.0, 0.0, 0.0))
        sz = d.get("surface_z")
        return cls(str(d["body_id"]), str(d.get("class", "other")),
                   tuple(int(c) for c in d.get("components", ())),
                   Anchor.from_dict(d["anchor"]), str(d.get("anchor_reason", "")),
                   str(d["new_resource"]),
                   (_f(off[0]), _f(off[1]), _f(off[2])),
                   int(d.get("elevated_members", 0)),
                   bool(d.get("elevated", False)),
                   str(d.get("merged_into") or ""),
                   None if sz is None else _f(sz), _f(d.get("y_zero", 0.0)),
                   None if d.get("plan_box") is None
                   else tuple(_f(q) for q in d["plan_box"]),
                   int(d.get("feet", 0)),
                   None if d.get("geom_box") is None
                   else tuple(_f(q) for q in d["geom_box"]),
                   tuple(tuple(_f(q) for q in b)
                         for b in d.get("foot_boxes", ())),
                   _f(d.get("fill", 1.0)),
                   None if d.get("ground_off") is None
                   else _f(d["ground_off"]),
                   tuple((_f(q[0]), _f(q[1]), _f(q[2]))
                         for q in d.get("geom_pts", ()) or ()),
                   bool(d.get("datum", False)),
                   str(d.get("bridge_of") or ""),
                   str(d.get("family_of") or ""),
                   str(d.get("unit_of") or ""),
                   str(d.get("connector_of") or ""))


@_dc.dataclass(frozen=True)
class Split:
    """One authored placement replaced by its bodies' placements."""

    placement: PlacementRef
    bodies: tuple[Body, ...]

    def to_dict(self) -> dict[str, _t.Any]:
        return {"placement": self.placement.to_dict(),
                "bodies": [b.to_dict() for b in self.bodies]}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Split":
        return cls(PlacementRef.from_dict(d["placement"]),
                   tuple(Body.from_dict(b) for b in d.get("bodies", ())))


@_dc.dataclass(frozen=True)
class Kept:
    """A placement left exactly as authored, and why."""

    index: int
    resource: str
    reason: str

    def to_dict(self) -> dict[str, _t.Any]:
        return {"index": self.index, "resource": self.resource, "reason": self.reason}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "Kept":
        return cls(int(d["index"]), str(d["resource"]), str(d.get("reason", "")))


@_dc.dataclass(frozen=True)
class PlacementPlan:
    """The whole plan for ONE pack DSF.  ``dsf_path`` and
    ``dsf_backup_path`` are absolute; ``pack_root`` is the pack folder
    the two are under (parameterised so a lane writes a COPY — §3.5: a
    lane NEVER writes the real X-Plane install)."""

    icao: str
    pack_name: str
    pack_root: str
    dsf_path: str
    dsf_backup_path: str
    provenance: Provenance
    conversions: tuple[Conversion, ...] = ()
    #: §16g (5): the placements seated by their DSF row (``MslSeat``)
    msl_seats: tuple[MslSeat, ...] = ()
    splits: tuple[Split, ...] = ()
    kept: tuple[Kept, ...] = ()
    #: jetway-strip spec §4 (2) / C18 (issue #31): the riders' seat
    #: records and the strips the design surface levelled (the published
    #: ``jetway_strips`` records, carried verbatim)
    riders: tuple[Rider, ...] = ()
    jetway_strips: tuple[_t.Mapping[str, _t.Any], ...] = ()

    # ── views the writers use ───────────────────────────────────────────
    def conversion_indices(self) -> frozenset[int]:
        return frozenset(c.index for c in self.conversions)

    def split_indices(self) -> frozenset[int]:
        return frozenset(s.placement.index for s in self.splits)

    def new_resources(self) -> tuple[str, ...]:
        """Every ``new_resource`` a split needs an ``OBJECT_DEF`` for, in
        first-appearance order and de-duplicated (two bodies may share a
        resource only by construction error, but the def list must not
        gain it twice)."""
        seen: dict[str, None] = {}
        for s in self.splits:
            for b in s.bodies:
                seen.setdefault(b.new_resource, None)
        return tuple(seen)

    def counts(self) -> dict[str, int]:
        per_kind: dict[str, int] = {}
        for c in self.conversions:
            per_kind[c.kind_before] = per_kind.get(c.kind_before, 0) + 1
        return {"conversions": len(self.conversions),
                "conversions_msl": per_kind.get(KIND_MSL, 0),
                "conversions_agl": per_kind.get(KIND_AGL, 0),
                "splits": len(self.splits),
                "bodies": sum(len(s.bodies) for s in self.splits),
                "new_resources": len(self.new_resources()),
                "kept": len(self.kept),
                # §16g (5): placements seated by their DSF row
                "msl_seats": len(self.msl_seats)}

    # ── the shared DSF (#25) ────────────────────────────────────────────
    def claimed_indices(self) -> frozenset[int]:
        """Every placement ordinal this plan edits: converted, row-seated
        or split.  What ``compose`` lets this plan WIN over a sibling's."""
        return (self.conversion_indices() | self.split_indices()
                | frozenset(m.index for m in self.msl_seats))

    def edit_rows(self) -> dict[str, _t.Any]:
        """The COMPACT edit set — exactly what ``dsf_write.edit_dump``
        reads and nothing else: the conversions, the row seats and, per
        split, the placement plus each body's ``new_resource`` and
        anchor.  Round-trips through ``from_dict`` (the body fields that
        do not shape a DSF row take their defaults).  This is what the
        pack record keeps per airport so a SIBLING airport's edits can be
        re-applied when another airport writes the same DSF."""
        return {"version": PLAN_VERSION, "icao": self.icao,
                "conversions": [c.to_dict() for c in self.conversions],
                "msl_seats": [m.to_dict() for m in self.msl_seats],
                "splits": [{"placement": s.placement.to_dict(),
                            "bodies": [{"body_id": b.body_id,
                                        "class": b.body_class,
                                        "new_resource": b.new_resource,
                                        "anchor": b.anchor.to_dict()}
                                       for b in s.bodies]}
                           for s in self.splits]}

    def compose(self, others: _t.Iterable["PlacementPlan"]) -> "PlacementPlan":
        """THIS plan plus every sibling's edits for the SAME DSF (#25:
        TNCM + TFFG are served by one pack DSF, and a write that carried
        only its own airport's plan erased the other's rows and orphaned
        its body files).

        This plan wins every ordinal it claims; among the siblings the
        first one given wins (callers pass them in a fixed order).  The
        result carries this plan's identity, provenance and ``kept``
        list — it is the DSF edit, not a new plan of record."""
        conv = list(self.conversions)
        msl = list(self.msl_seats)
        spl = list(self.splits)
        taken = set(self.claimed_indices())
        for o in others:
            for c in o.conversions:
                if c.index not in taken:
                    conv.append(c)
                    taken.add(c.index)
            for m in o.msl_seats:
                if m.index not in taken:
                    msl.append(m)
                    taken.add(m.index)
            for s in o.splits:
                if s.placement.index not in taken:
                    spl.append(s)
                    taken.add(s.placement.index)
        return _dc.replace(self, conversions=tuple(conv), msl_seats=tuple(msl),
                           splits=tuple(spl))

    # ── JSON ────────────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, _t.Any]:
        return {"version": PLAN_VERSION, "icao": self.icao,
                "pack_name": self.pack_name, "pack_root": self.pack_root,
                "dsf_path": self.dsf_path, "dsf_backup_path": self.dsf_backup_path,
                "provenance": self.provenance.to_dict(),
                "counts": self.counts(),
                "conversions": [c.to_dict() for c in self.conversions],
                "splits": [s.to_dict() for s in self.splits],
                "kept": [k.to_dict() for k in self.kept],
                "msl_seats": [m.to_dict() for m in self.msl_seats],
                "riders": [r.to_dict() for r in self.riders],
                "jetway_strips": [dict(j) for j in self.jetway_strips]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "PlacementPlan":
        if d.get("version") != PLAN_VERSION:
            raise ValueError(f"placement plan version {d.get('version')!r} "
                             f"!= {PLAN_VERSION}")
        return cls(icao=str(d["icao"]), pack_name=str(d.get("pack_name", "")),
                   pack_root=str(d.get("pack_root", "")),
                   dsf_path=str(d.get("dsf_path", "")),
                   dsf_backup_path=str(d.get("dsf_backup_path", "")),
                   provenance=Provenance.from_dict(d.get("provenance", {})),
                   conversions=tuple(Conversion.from_dict(c)
                                     for c in d.get("conversions", ())),
                   splits=tuple(Split.from_dict(s) for s in d.get("splits", ())),
                   kept=tuple(Kept.from_dict(k) for k in d.get("kept", ())),
                   msl_seats=tuple(MslSeat.from_dict(m)
                                   for m in d.get("msl_seats", ())),
                   riders=tuple(Rider.from_dict(r) for r in d.get("riders", ())),
                   jetway_strips=tuple(dict(j) for j in d.get("jetway_strips", ())))

    @classmethod
    def from_json(cls, text: str) -> "PlacementPlan":
        return cls.from_dict(json.loads(text))
