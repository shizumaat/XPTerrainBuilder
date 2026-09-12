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
    "KIND_ON_GROUND", "KIND_MSL", "KIND_AGL", "CONVERTIBLE_KINDS",
    "BODY_CLASSES", "Provenance", "Conversion", "Anchor", "PlacementRef",
    "Body", "Split", "Kept", "PlacementPlan",
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
                "fill": self.fill}

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
                   _f(d.get("fill", 1.0)))


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
    splits: tuple[Split, ...] = ()
    kept: tuple[Kept, ...] = ()

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
                "kept": len(self.kept)}

    # ── JSON ────────────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, _t.Any]:
        return {"version": PLAN_VERSION, "icao": self.icao,
                "pack_name": self.pack_name, "pack_root": self.pack_root,
                "dsf_path": self.dsf_path, "dsf_backup_path": self.dsf_backup_path,
                "provenance": self.provenance.to_dict(),
                "counts": self.counts(),
                "conversions": [c.to_dict() for c in self.conversions],
                "splits": [s.to_dict() for s in self.splits],
                "kept": [k.to_dict() for k in self.kept]}

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
                   kept=tuple(Kept.from_dict(k) for k in d.get("kept", ())))

    @classmethod
    def from_json(cls, text: str) -> "PlacementPlan":
        return cls.from_dict(json.loads(text))
