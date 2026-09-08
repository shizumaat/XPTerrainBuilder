"""THE RE-SEAT PLAN AND RESULT — data only (RULINGS 2026-09-04i 04f-1;
the CONTACT-CLUSTER law 2026-09-06g).

A :class:`RebakePlan` is what the tile build writes beside the patch
(``o4_v2_rebake_<ICAO>.json``) and the post-mesh seat reads.  Since 06g
the seat's unit is no longer the anchor family but the CONTACT CLUSTER
(v1's law as v2 code): every member carries its welded solid PARTS —
one per genuine component of the authored file: the plan-centroid the
mesh is read under, the part's lowest authored ``y`` (``base_y``), its
plan area and box — and the plan carries the ε-CONTACT EDGES among all
parts of the pack (``airport/contact.py``).  After the mesh
``emit/clusters.py`` cuts the ground-to-ground edges whose seat targets
disagree by more than ``cluster_seat_tolerance_m`` and seats every
cluster on the median ground under its ground parts, PER VERTEX — one
file may carry several deltas.  Anchor families (``Unit``) survive as
the SUBTRAHEND (a member's rendered ``y = 0`` plane is the mesh at its
anchor + AGL) and as the scope of the STRUCTURE seats: a deck plate at
its abutment grade (R12), a tunnel wall / basin floor plate (05n-4 /
06b-3).  Built by ``airport/rebake_plan.py``, seated by
``emit/rebake.py``.  No numpy, no shapely, no I/O here.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import typing as _t

from .frame import LL

__all__ = ["Part", "Member", "Unit", "FlatDatum", "RebakePlan", "MemberSeat", "UnitSeat",
           "ClusterSeat", "PadRequest", "SeatResult", "PLAN_VERSION", "PLAN_FILENAME",
           "DATUM_CLUSTER", "DATUM_DECK_TOP", "DATUM_PLATE"]

#: 2: the deck signature's end lines / profile (04k, M6b); 3: tunnel wall
#: plates (05n-4); 4: parts and contact edges, feet retired (06g); 5: the
#: flat-site datum and its region (08d).
PLAN_VERSION = 5
#: ``<patch dir>/o4_v2_rebake_<ICAO>.json`` — beside v1's worklist.
PLAN_FILENAME = "o4_v2_rebake_{icao}.json"

#: A ground object seats by its CONTACT CLUSTERS (06g; v1 ``form_clusters``).
DATUM_CLUSTER = "cluster"
DATUM_DECK_TOP = "deck_top"
#: A tunnel wall object seats its top PLATE on the ground at its wall band
#: (RULINGS 2026-09-05n-4; ``tunnel.object.plate_datum = "ground"``).
DATUM_PLATE = "plate"


# ── the plan ─────────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Part:
    """One welded solid part of a member (a genuine component of the
    authored file, index ``comp`` into ``obj8.solid_components``): the
    world position of its plan centroid (the mesh is read there), its
    lowest authored ``y``, plan area and plan box ``(min_lat, min_lon,
    max_lat, max_lon)``.  ``pid`` is its index in the plan's contact
    graph."""

    pid: int
    comp: int
    lat: float
    lon: float
    base_y: float
    area_m2: float
    box: tuple[float, float, float, float]


@_dc.dataclass(frozen=True)
class Member:
    """One resource of a unit.  ``authored_path`` is what was read
    (``.anchor_bak`` where one exists); ``live_path`` what a bake writes.
    ``resource`` is the pack-relative path the writer keys on."""

    id: str
    resource: str
    authored_path: str
    live_path: str
    heading_deg: float
    parts: tuple[Part, ...] = ()
    deck_ring: tuple[LL, ...] | None = None
    deck_top_y: float | None = None
    deck_datum_z: float | None = None
    #: THE DECK SIGNATURE (04k; ``airport/deck_signature.py``): ``"flag"``
    #: (``ATTR_hard_deck``), ``"signature"`` (a plate spanning a bridge
    #: way / below-grade region), ``"family"`` (a member of a deck family
    #: without a plate: its parts in contact with the deck seat WITH it,
    #: 06g), else ``""``.
    deck_kind: str = ""
    #: A signature deck's abutment END LINES ``((a, b), (c, d))`` in
    #: ``(lat, lon)`` — where the seat reads the ground (R12: deck top at
    #: the abutment grade; the landward walk starts here).
    deck_ends: tuple[tuple[LL, LL], tuple[LL, LL]] | None = None
    #: ...and its deck-top PROFILE ``(s, y)``: ``s`` metres from the
    #: start end's midpoint along the axis, ``y`` the authored top there
    #: (what the mid-span clearance test reads).
    deck_profile: tuple[tuple[float, float], ...] = ()
    #: The evidence the signature recorded (one line per fact).
    deck_evidence: tuple[str, ...] = ()
    #: The plate's STATIONS ``(lat, lon, authored y)``: near-horizontal
    #: faces of its own components spread along the axis — the clearance
    #: test's witnesses (``deck_min_clearance_under_m``).
    deck_stations: tuple[tuple[float, float, float], ...] = ()
    #: THE WALL PLATE (05n-4; ``airport/tunnel_objects``): a tunnel wall
    #: object's authored plate height and the STATIONS ``(lat, lon)`` along
    #: its wall band where the seat reads the ground — the member seats
    #: so that ``base + plate_y`` equals the ground there.  ``None`` / empty
    #: for every other member.
    plate_y: float | None = None
    plate_stations: tuple[LL, ...] = ()


@_dc.dataclass(frozen=True)
class Unit:
    """One anchor family: every placement sharing one anchor spelling.
    The SUBTRAHEND of its members' deltas and the scope of a structure
    seat (06g) — no longer the seat's rigid unit."""

    id: str
    anchor: LL
    agl_m: float
    members: tuple[Member, ...]


#: A ring of ``(lat, lon)`` points.
RingLL = tuple[LL, ...]


@_dc.dataclass(frozen=True)
class FlatDatum:
    """THE FLAT-SITE DATUM AT THE SEAT (RULINGS 2026-09-08d; spec
    ``othh-seat-artefacts-spec.md``): the verdict the pipeline measured
    (``airport/flat_site.py``, 05k-2), its datum ``z0_m`` and the REGION
    the datum is priced over (pavement ∪ boundary ⊕ margin) as
    ``(outer, holes)`` rings in ``(lat, lon)``.  ``substitutes`` mirrors
    ``FlatVerdict.substitutes``: only then does the datum reach the
    anchor and the ground the seat reads."""

    verdict: str
    z0_m: float | None
    source: str
    region: tuple[tuple[RingLL, tuple[RingLL, ...]], ...] = ()

    @property
    def substitutes(self) -> bool:
        return self.z0_m is not None and self.verdict in ("flat_candidate", "flat_declared")

    def to_dict(self) -> dict[str, _t.Any]:
        return {"verdict": self.verdict, "z0_m": self.z0_m, "source": self.source,
                "region": [[[list(p) for p in outer], [[list(p) for p in h] for h in holes]]
                           for outer, holes in self.region]}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "FlatDatum":
        ring = lambda r: tuple((float(a), float(b)) for a, b in r)      # noqa: E731
        return cls(str(d["verdict"]), None if d.get("z0_m") is None else float(d["z0_m"]),
                   str(d.get("source", "")),
                   tuple((ring(outer), tuple(ring(h) for h in holes))
                         for outer, holes in d.get("region", ())))


@_dc.dataclass(frozen=True)
class RebakePlan:
    """What the post-mesh seat reads; JSON round-trips exactly.
    ``contacts`` are the ε-contact edges ``(pid, pid)`` over every
    member's parts (``[rebake] contact_epsilon_m``); ``flat`` the
    flat-site datum the seat honours (08d), ``None`` when the pipeline
    measured none."""

    icao: str
    pack_name: str
    pack_root: str
    units: tuple[Unit, ...]
    skipped: tuple[tuple[str, str], ...]
    counts: _t.Mapping[str, int]
    contacts: tuple[tuple[int, int], ...] = ()
    flat: FlatDatum | None = None

    def bounds(self) -> tuple[float, float, float, float]:
        """``(min_lon, min_lat, max_lon, max_lat)`` over every witness."""
        lats: list[float] = []
        lons: list[float] = []
        for u in self.units:
            lats.append(u.anchor[0]); lons.append(u.anchor[1])
            for m in u.members:
                for p in m.parts:
                    lats.extend((p.box[0], p.box[2])); lons.extend((p.box[1], p.box[3]))
                for la, lo in (m.deck_ring or ()):
                    lats.append(la); lons.append(lo)
                for la, lo in m.plate_stations:
                    lats.append(la); lons.append(lo)
        if not lats:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(lons), min(lats), max(lons), max(lats))

    def to_dict(self) -> dict[str, _t.Any]:
        return {
            "version": PLAN_VERSION, "icao": self.icao,
            "pack_name": self.pack_name, "pack_root": self.pack_root,
            "counts": dict(self.counts),
            "skipped": [list(s) for s in self.skipped],
            "contacts": [[a, b] for a, b in self.contacts],
            "flat": None if self.flat is None else self.flat.to_dict(),
            "units": [{
                "id": u.id, "anchor": [u.anchor[0], u.anchor[1]], "agl_m": u.agl_m,
                "members": [{
                    "id": m.id, "resource": m.resource,
                    "authored_path": m.authored_path, "live_path": m.live_path,
                    "heading_deg": m.heading_deg,
                    "parts": [[p.pid, p.comp, p.lat, p.lon, p.base_y, p.area_m2, *p.box]
                              for p in m.parts],
                    "deck_ring": None if m.deck_ring is None
                    else [[a, b] for a, b in m.deck_ring],
                    "deck_top_y": m.deck_top_y, "deck_datum_z": m.deck_datum_z,
                    "deck_kind": m.deck_kind,
                    "deck_ends": None if m.deck_ends is None
                    else [[[a, b] for a, b in e] for e in m.deck_ends],
                    "deck_profile": [[s, y] for s, y in m.deck_profile],
                    "deck_evidence": list(m.deck_evidence),
                    "deck_stations": [list(st) for st in m.deck_stations],
                    "plate_y": m.plate_y,
                    "plate_stations": [[a, b] for a, b in m.plate_stations],
                } for m in u.members],
            } for u in self.units],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "RebakePlan":
        if d.get("version") != PLAN_VERSION:
            raise ValueError(f"rebake plan version {d.get('version')!r} != {PLAN_VERSION}")
        units = tuple(Unit(
            id=str(u["id"]), anchor=(float(u["anchor"][0]), float(u["anchor"][1])),
            agl_m=float(u["agl_m"]),
            members=tuple(Member(
                id=str(m["id"]), resource=str(m["resource"]),
                authored_path=str(m["authored_path"]), live_path=str(m["live_path"]),
                heading_deg=float(m["heading_deg"]),
                parts=tuple(Part(int(p[0]), int(p[1]), float(p[2]), float(p[3]), float(p[4]),
                                 float(p[5]), (float(p[6]), float(p[7]), float(p[8]),
                                               float(p[9])))
                            for p in m.get("parts", ())),
                deck_ring=None if m.get("deck_ring") is None
                else tuple((float(a), float(b)) for a, b in m["deck_ring"]),
                deck_top_y=None if m.get("deck_top_y") is None else float(m["deck_top_y"]),
                deck_datum_z=None if m.get("deck_datum_z") is None
                else float(m["deck_datum_z"]),
                deck_kind=str(m.get("deck_kind", "")),
                deck_ends=None if m.get("deck_ends") is None
                else tuple(tuple((float(a), float(b)) for a, b in e)   # type: ignore[misc]
                           for e in m["deck_ends"]),
                deck_profile=tuple((float(s), float(y)) for s, y in m.get("deck_profile", ())),
                deck_evidence=tuple(str(x) for x in m.get("deck_evidence", ())),
                deck_stations=tuple((float(a), float(b), float(c))
                                    for a, b, c in m.get("deck_stations", ())),
                plate_y=None if m.get("plate_y") is None else float(m["plate_y"]),
                plate_stations=tuple((float(a), float(b)) for a, b in m.get("plate_stations", ())),
            ) for m in u["members"])) for u in d["units"])
        return cls(icao=str(d["icao"]), pack_name=str(d["pack_name"]),
                   pack_root=str(d["pack_root"]), units=units,
                   skipped=tuple((str(a), str(b)) for a, b in d.get("skipped", ())),
                   counts=dict(d.get("counts", {})),
                   contacts=tuple((int(a), int(b)) for a, b in d.get("contacts", ())),
                   flat=None if d.get("flat") is None else FlatDatum.from_dict(d["flat"]))

    @classmethod
    def from_json(cls, text: str) -> "RebakePlan":
        return cls.from_dict(json.loads(text))


# ── the seat ─────────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class MemberSeat:
    """One member's seat.  ``delta_m`` is the ONE delta applied to the
    whole file when it has one (a structure seat, or every part in one
    cluster), else ``None`` with the per-part map in ``part_deltas``:
    ``(comp, cluster id, delta | None)`` — ``None`` = that part keeps its
    authored y (its cluster stayed: below threshold, refused, facility,
    held).  ``witnesses`` counts the member's MEASURED ground parts."""

    resource: str
    datum: str
    delta_m: float | None
    witnesses: int
    water: int
    off_mesh: int
    outliers: int
    note: str = ""
    #: The abutment records of a signature deck (per end: walked metres,
    #: land samples, samples over water, found) and the mid-span
    #: clearance reading — the evidence trail per member (04k).
    records: tuple[str, ...] = ()
    #: Whether this member FOUNDED the unit's structure seat (a deck plate
    #: with a measured abutment grade, a wall plate on its band).
    founding: bool = False
    #: A FACILITY member (RULINGS 2026-09-05p, at cluster level 06g): every
    #: one of its ground parts lies in a facility cluster — it keeps its
    #: authored y (the terrain's cutout is the basin pass's affair).
    facility: bool = False
    #: The GROUND under the member's measured ground parts (median mesh z).
    ground_m: float | None = None
    part_deltas: tuple[tuple[int, int, float | None], ...] = ()

    @property
    def bakes(self) -> bool:
        """Some vertex of this member moves."""
        return self.delta_m is not None or any(d is not None for _c, _k, d in self.part_deltas)


@_dc.dataclass(frozen=True)
class ClusterSeat:
    """One contact cluster (06g): ``ground_m`` the median mesh under its
    measured ground parts, ``lift_m`` the median of their seat deltas
    (``ground − base_y − base``: positive = the parts stand under the
    mesh), ``span_m`` the ground relief across them.  ``delta_m`` is per
    RESOURCE (``ground_m − base(member)``) and lives in the members'
    ``part_deltas``; ``skip_reason`` says why the cluster stays."""

    id: int
    structure: int
    resources: tuple[str, ...]
    n_parts: int
    n_ground: int
    n_measured: int
    ground_m: float | None
    lift_m: float | None
    span_m: float
    diameter_m: float
    needs_pad: bool = False
    facility: bool = False
    held: bool = False
    skip_reason: str | None = None
    residual_parts: int = 0

    @property
    def bakes(self) -> bool:
        return self.ground_m is not None and self.skip_reason is None and not self.held


@_dc.dataclass(frozen=True)
class PadRequest:
    """A maximal connected group of a cluster's ground parts the seat
    still leaves further than ``cluster_residual_pad_m`` off the mesh
    (v1 ``ClusterPadRequest``, spec §5.3): the terrain's to close —
    REPORTED here, consumed by no v2 pass yet (06g)."""

    cluster: int
    resource: str
    lat: float
    lon: float
    residual_m: float
    target_ground_m: float
    part_count: int
    over_relief_cap: bool
    seated: bool


@_dc.dataclass(frozen=True)
class UnitSeat:
    """The unit's structure seat (a deck top, a wall plate: ONE delta for
    the members it founds), or ``DATUM_CLUSTER``: its members seat by
    their contact clusters and ``delta_m`` is ``None``."""

    unit_id: str
    resources: tuple[str, ...]
    anchor_ground_m: float | None
    datum: str
    delta_m: float | None
    seat_datum_m: float | None
    members: tuple[MemberSeat, ...]
    skip_reason: str | None = None
    findings: tuple[str, ...] = ()
    #: HELD: v2 cannot judge the unit (its anchor is off the mesh, or a
    #: one-file-several-anchors disagreement) — the pack's CURRENT bytes
    #: are kept, neither seated nor reverted.
    held: bool = False

    @property
    def bakes(self) -> bool:
        """Some member of the unit moves."""
        if self.skip_reason is not None or self.held:
            return False
        return self.delta_m is not None or any(m.bakes for m in self.members)


@_dc.dataclass(frozen=True)
class SeatResult:
    icao: str
    units: tuple[UnitSeat, ...]
    clusters: tuple[ClusterSeat, ...] = ()
    pad_requests: tuple[PadRequest, ...] = ()
    cut_edges: int = 0
    structures: int = 0

    def counts(self) -> dict[str, int]:
        c = {"units": len(self.units), "baked": 0, "below_threshold": 0,
             "held": 0, "skipped": 0, "resources_baked": 0, "findings": 0,
             "deck_units": 0, "facility_members": 0, "plate_units": 0,
             "structures": self.structures, "clusters": len(self.clusters),
             "clusters_baked": 0, "clusters_below_threshold": 0, "clusters_refused": 0,
             "clusters_facility": 0, "clusters_held": 0, "clusters_padded": 0,
             "cut_edges": self.cut_edges, "pad_requests": len(self.pad_requests),
             "parts": 0, "ground_parts": 0, "members_multi_delta": 0}
        for u in self.units:
            c["findings"] += len(u.findings)
            c["facility_members"] += sum(1 for m in u.members if m.facility)
            c["resources_baked"] += sum(1 for m in u.members if m.bakes and not u.held)
            c["members_multi_delta"] += sum(
                1 for m in u.members if m.delta_m is None
                and len({d for _c, _k, d in m.part_deltas if d is not None}) > 1)
            if u.datum == DATUM_DECK_TOP:
                c["deck_units"] += 1
            if u.datum == DATUM_PLATE:
                c["plate_units"] += 1
            if u.bakes:
                c["baked"] += 1
            elif u.skip_reason and u.skip_reason.startswith("below_threshold"):
                c["below_threshold"] += 1
            elif u.held:
                c["held"] += 1
            else:
                c["skipped"] += 1
        for k in self.clusters:
            c["parts"] += k.n_parts
            c["ground_parts"] += k.n_ground
            if k.bakes:
                c["clusters_baked"] += 1
            elif k.held:
                c["clusters_held"] += 1
            elif k.facility:
                c["clusters_facility"] += 1
            elif k.skip_reason and k.skip_reason.startswith("below_threshold"):
                c["clusters_below_threshold"] += 1
            else:
                c["clusters_refused"] += 1
            if k.needs_pad:
                c["clusters_padded"] += 1
        return c

    def to_dict(self) -> dict[str, _t.Any]:
        return {"icao": self.icao, "counts": self.counts(),
                "cut_edges": self.cut_edges, "structures": self.structures,
                "units": [_dc.asdict(u) for u in self.units],
                "clusters": [_dc.asdict(k) for k in self.clusters],
                "pad_requests": [_dc.asdict(p) for p in self.pad_requests]}
