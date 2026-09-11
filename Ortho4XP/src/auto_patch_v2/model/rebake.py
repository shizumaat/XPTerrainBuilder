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
#: flat-site datum and its region (08d); 6: the parts' FEET (09s — the
#: per-component ground reading); 7: the LINE OBJECT verdict per part and
#: its widened DRAPE STATIONS (10bb, spec §16); 8: the AUTHORED-FRAME
#: ABUTMENTS (10ay, spec §17 — cross-placement grouping inside one
#: anchor plane).
PLAN_VERSION = 8
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
    graph.

    ``feet`` (RULINGS 2026-09-09s (2)) are the component's own GROUND
    FEET — its lowest solid vertices within ``[basin] contact_band_m`` of
    its own minimum, ``(lat, lon, authored y)``, at most
    ``[rebake] foot_samples_max`` spread over the plan.  The seat reads
    the mesh at each and takes the median of ``z − y`` as the part's seat
    target.  EMPTY means the plan judged the part ELEVATED (its
    ``base_y`` stands more than ``elevated_base_m`` above the minimum of
    its contact structure) — or that the plan predates 09s, in which case
    ``emit/clusters`` falls back to one foot at the centroid carrying
    ``base_y``, which is the pre-09s reading exactly."""

    pid: int
    comp: int
    lat: float
    lon: float
    base_y: float
    area_m2: float
    box: tuple[float, float, float, float]
    feet: tuple[tuple[float, float, float], ...] = ()
    #: THE LINE OBJECT (owner RULINGS 2026-09-10bb; ``airport/line_object``,
    #: spec §16): a component of a fence / kerb / jet-blast line / light
    #: string.  It forms NO body with what it touches and founds NO foot
    #: for one; its ``feet`` are its DRAPE STATIONS and it is seated per
    #: SEGMENT — every vertex takes the delta of the nearest station.
    line: bool = False


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
    #: THE FOUNDATION SKIRT (owner RULINGS 2026-09-10ag; spec §22.3):
    #: this member's resource carries a uniform below-zero extent across
    #: its footprint (``airport/skirt.is_skirt``).  A body EVERY one of
    #: whose members is skirted seats at its LOW-side foot instead of
    #: 10i's median, so the low side touches the ground and the high side
    #: buries into the skirt.  Absent from an older plan = ``False`` =
    #: the pre-10ag law exactly.
    skirted: bool = False


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
    #: THE AUTHORED-FRAME ABUTMENTS (owner RULINGS 2026-09-10ay; spec
    #: §17): ``(pid, pid)`` pairs of ONE anchor plane whose plan
    #: footprints overlap and whose authored z lies within ``[rebake]
    #: plate_gap_max_m``, carrying no ε-contact edge.  They bind no body
    #: — they GROUP the bodies they fall in, which take the senior
    #: body's delta.  Empty in a plan written before 10ay.
    abutments: tuple[tuple[int, int], ...] = ()

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
            "abutments": [[a, b] for a, b in self.abutments],
            "flat": None if self.flat is None else self.flat.to_dict(),
            "units": [{
                "id": u.id, "anchor": [u.anchor[0], u.anchor[1]], "agl_m": u.agl_m,
                "members": [{
                    "id": m.id, "resource": m.resource,
                    "authored_path": m.authored_path, "live_path": m.live_path,
                    "heading_deg": m.heading_deg,
                    "parts": [[p.pid, p.comp, p.lat, p.lon, p.base_y, p.area_m2, *p.box,
                               [list(f) for f in p.feet], p.line] for p in m.parts],
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
                    "skirted": m.skirted,
                } for m in u.members],
            } for u in self.units],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "RebakePlan":
        # Version 8 is version 7 plus ``RebakePlan.abutments`` (RULINGS
        # 2026-09-10ay) and version 7 is version 6 plus ``Part.line``
        # (2026-09-10bb): an older plan reads as the current one with no
        # abutment and no line object in it — the pre-10ay / pre-10bb seat
        # exactly — so an OWNER's plan from an earlier build still replays
        # offline (``tools/v2_rebake_replay.py``).  Nothing earlier is
        # accepted: those versions changed fields the seat reads.
        if d.get("version") not in (PLAN_VERSION, PLAN_VERSION - 1, PLAN_VERSION - 2):
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
                                               float(p[9])),
                                 tuple((float(a), float(b), float(c))
                                       for a, b, c in (p[10] if len(p) > 10 else ())),
                                 bool(p[11]) if len(p) > 11 else False)
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
                skirted=bool(m.get("skirted", False)),
            ) for m in u["members"])) for u in d["units"])
        return cls(icao=str(d["icao"]), pack_name=str(d["pack_name"]),
                   pack_root=str(d["pack_root"]), units=units,
                   skipped=tuple((str(a), str(b)) for a, b in d.get("skipped", ())),
                   counts=dict(d.get("counts", {})),
                   contacts=tuple((int(a), int(b)) for a, b in d.get("contacts", ())),
                   abutments=tuple((int(a), int(b)) for a, b in d.get("abutments", ())),
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
    #: The GROUND under the member's measured ground parts: the median
    #: SEAT TARGET (09s (2) — the y = 0 plane its feet found).
    ground_m: float | None = None
    part_deltas: tuple[tuple[int, int, float | None], ...] = ()
    #: THE SEGMENT SEAT of a LINE OBJECT (owner RULINGS 2026-09-10bb, spec
    #: §16.1 rule 3): rows ``(comp, lat, lon, delta)`` — every VERTEX of
    #: that component takes the delta of the station NEAREST it in plan,
    #: so a fence drapes instead of taking one delta over kilometres.
    #: The component's entry in ``part_deltas`` carries the MEDIAN of
    #: them, which is what a consumer with no plan position reads.
    line_stations: tuple[tuple[int, float, float, float], ...] = ()

    @property
    def bakes(self) -> bool:
        """Some vertex of this member moves."""
        return self.delta_m is not None or any(d is not None for _c, _k, d in self.part_deltas)


@_dc.dataclass(frozen=True)
class ClusterSeat:
    """One contact cluster (06g): ``ground_m`` the median SEAT TARGET of
    its measured ground parts (09s (2): the ``y = 0`` plane their own
    feet found), ``lift_m`` the median of their seat deltas
    (``target − base``: positive = the parts stand under the mesh),
    ``span_m`` the relief across those targets.  ``delta_m`` is per
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
    #: THE FEET ACROSS THE BODY (RULINGS 2026-09-10i (2)): one residual
    #: per measured ground part — its own feet-founded target minus the
    #: body's median ``ground_m`` — rounded to the millimetre, and their
    #: largest absolute value.  ``feet_sampled`` counts the additional
    #: feet the seat had to SAMPLE off the design surface because the
    #: body was wider than ``body_feet_span_m`` per measured foot.
    foot_residuals: tuple[float, ...] = ()
    foot_residual_max_m: float = 0.0
    feet_sampled: int = 0
    #: RULINGS 2026-09-10bb: this body is ONE LINE OBJECT component,
    #: draped on its own stations (spec §16) — it bound nothing and
    #: founded no foot for anything else.
    line_object: bool = False
    #: ...and the ORPHAN (§16.1 rule 4): a body with no ground part at
    #: all, seated by sampling the design surface under its parts.
    orphan: bool = False
    #: THE ABUTMENT GROUP (owner RULINGS 2026-09-10ay; spec §17): the id
    #: of the SENIOR body of the group this body abuts into, or ``None``
    #: when it is in no group.  A body whose ``group`` is not its own id
    #: is a JUNIOR: it took the senior's ground, not its own feet's.
    group: int | None = None

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
    #: RULINGS 2026-09-10i (1)/(3): intra-placement ground edges KEPT
    #: despite disagreeing feet, and parts held for touching no body.
    intra_placement_kept: int = 0
    held_parts: int = 0
    #: RULINGS 2026-09-10u (1): elevated cohesion groups assigned as one,
    #: and those that resolved with no plan overlap (the body-id tie).
    elevated_groups: int = 0
    group_ties: int = 0
    #: RULINGS 2026-09-10bb (spec §16): LINE-OBJECT bodies, the contact
    #: edges their rule refused to bind, and the ORPHAN bodies seated by
    #: sampling because everything they touched was a line object.
    line_bodies: int = 0
    line_edges_dropped: int = 0
    orphan_bodies_seated: int = 0
    #: owner RULINGS 2026-09-10ay (spec §17): the ABUTMENT GROUPS formed
    #: in the authored frame, the JUNIOR bodies that took a senior's
    #: ground instead of their own feet's, and the abutment pairs a rule
    #: refused (a line body, a structure seat, a facility, a held body).
    abutment_groups: int = 0
    grouped_bodies: int = 0
    group_pairs_refused: int = 0

    def counts(self) -> dict[str, int]:
        c = {"units": len(self.units), "baked": 0, "below_threshold": 0,
             "held": 0, "skipped": 0, "resources_baked": 0, "findings": 0,
             "deck_units": 0, "facility_members": 0, "plate_units": 0,
             "structures": self.structures, "clusters": len(self.clusters),
             "clusters_baked": 0, "clusters_below_threshold": 0, "clusters_refused": 0,
             "clusters_facility": 0, "clusters_held": 0, "clusters_padded": 0,
             "cut_edges": self.cut_edges, "pad_requests": len(self.pad_requests),
             "intra_placement_kept": self.intra_placement_kept,
             "held_parts": self.held_parts, "feet_sampled": 0,
             "elevated_groups": self.elevated_groups, "group_ties": self.group_ties,
             "parts": 0, "ground_parts": 0, "members_multi_delta": 0,
             "line_objects": 0, "line_stations": 0, "orphan_bodies": 0,
             "line_bodies": self.line_bodies,
             "line_edges_dropped": self.line_edges_dropped,
             "abutment_groups": self.abutment_groups,
             "grouped_bodies": self.grouped_bodies,
             "group_pairs_refused": self.group_pairs_refused}
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
            c["feet_sampled"] += k.feet_sampled
            c["line_objects"] += int(k.line_object)
            c["orphan_bodies"] += int(k.orphan)
        for u in self.units:
            for m in u.members:
                c["line_stations"] += len(m.line_stations)
        return c

    def to_dict(self) -> dict[str, _t.Any]:
        return {"icao": self.icao, "counts": self.counts(),
                "cut_edges": self.cut_edges, "structures": self.structures,
                "intra_placement_kept": self.intra_placement_kept,
                "held_parts": self.held_parts,
                "elevated_groups": self.elevated_groups, "group_ties": self.group_ties,
                "line_bodies": self.line_bodies,
                "line_edges_dropped": self.line_edges_dropped,
                "orphan_bodies_seated": self.orphan_bodies_seated,
                "abutment_groups": self.abutment_groups,
                "grouped_bodies": self.grouped_bodies,
                "group_pairs_refused": self.group_pairs_refused,
                "units": [_dc.asdict(u) for u in self.units],
                "clusters": [_dc.asdict(k) for k in self.clusters],
                "pad_requests": [_dc.asdict(p) for p in self.pad_requests]}
