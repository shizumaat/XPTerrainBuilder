"""THE OBJECT-STAGE PLAN — data only (RULINGS 2026-09-04i 04f-1; the
CONTACT-CLUSTER law 2026-09-06g; THE SEAT RETIRED 2026-09-12s, spec §8).

A :class:`RebakePlan` is what the tile build writes beside the patch
(``o4_v2_rebake_<ICAO>.json``) and the post-mesh object stage reads.
Every member carries its welded solid PARTS — one per genuine component
of the authored file: the plan-centroid the mesh is read under, the
part's lowest authored ``y`` (``base_y``), its plan area and box — and
the plan carries the ε-CONTACT EDGES among all parts of the pack
(``airport/contact.py``).  Anchor families (``Unit``) carry the
SUBTRAHEND (a member's rendered ``y = 0`` plane is the mesh at its
anchor + AGL).  Built by ``airport/rebake_plan.py``, consumed by the
PLACEMENT path (``airport/placement_*.py``, spec §4/§6).

THE SEAT'S RESULT TYPES ARE DELETED (2026-09-12s): ``MemberSeat``,
``UnitSeat``, ``ClusterSeat``, ``PadRequest``, ``SeatResult`` and the
``DATUM_*`` constants belonged to v1's vertex rewrite, a refuted
mechanism — deleted, not gated.  No numpy, no shapely, no I/O here.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import typing as _t

from .frame import LL


__all__ = ["Part", "Member", "Unit", "FlatDatum", "RebakePlan",
           "PLAN_VERSION", "PLAN_FILENAME"]

#: 2: the deck signature's end lines / profile (04k, M6b); 3: tunnel wall
#: plates (05n-4); 4: parts and contact edges, feet retired (06g); 5: the
#: flat-site datum and its region (08d); 6: the parts' FEET (09s — the
#: per-component ground reading); 7: the LINE OBJECT verdict per part and
#: its widened DRAPE STATIONS (10bb, spec §16); 8: the AUTHORED-FRAME
#: ABUTMENTS (10ay, spec §17 — cross-placement grouping inside one
#: anchor plane).
PLAN_VERSION = 9
#: ``<patch dir>/o4_v2_rebake_<ICAO>.json`` — beside v1's worklist.
PLAN_FILENAME = "o4_v2_rebake_{icao}.json"



# ── the plan ─────────────────────────────────────────────────────────────

def _rings(raw) -> tuple:
    """§16g (7) (1)'s footprint rings from the plan.  A plan written
    before RULINGS 2026-09-14j carries ONE FLAT ring (a list of
    ``[lat, lon]`` pairs); one written after carries a LIST of rings, one
    per blob.  Both shapes are read, so an older frame is never silently
    mis-parsed into nonsense."""
    if not raw:
        return ()
    head = raw[0]
    if len(head) == 2 and not isinstance(head[0], (list, tuple)):
        return (tuple((float(a), float(b)) for a, b in raw),)
    return tuple(tuple((float(a), float(b)) for a, b in r) for r in raw if r)


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
    #: §16g (7) (1) THE FOOTPRINT POLYGON (owner RULINGS 2026-09-14c item
    #: 1, amended 14j): this component's plan OUTLINE — the union of its
    #: projected triangles, simplified OUTWARD — as ``(lat, lon)``
    #: vertices, at most ``contact.FOOTPRINT_RING_MAX`` of them.  §16g (1)'s unit
    #: chains on THIS, never on ``box`` — a rotated building's lat/lon box
    #: overlaps a neighbour whose footprint is 20 m away, and that chain
    #: handed a rail deck's datum to 1,509 HECA bodies (14g).  EMPTY in a
    #: plan written before the field, and the reader then falls back to
    #: ``box`` and SAYS SO.
    rings: tuple[tuple[tuple[float, float], ...], ...] = ()


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
    #: §16e (2): the deck END LINES sampled at ``[bridge]
    #: abutment_sample_step_m`` — the STATIONS whose ground the deck top
    #: is the datum of, in ``(lat, lon)``, the same shape
    #: ``plate_stations`` carries.  Stamped for a FLAG deck standing over
    #: no graded face (``deck_datum_z`` None); empty for every other
    #: member, and empty in every plan written before §16e.
    deck_end_stations: tuple[LL, ...] = ()
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
    #: THE BASIN FLOOR'S CLEARANCE (owner RULINGS 2026-09-11t, spec §24 (2);
    #: ``[basin] floor_clearance_m``): the plate stands this far ABOVE the
    #: ground its stations read.  The stations of a basin member lie on the
    #: TRENCH FLOOR, which the floor row now puts ``floor_clearance_m``
    #: under the plate — without this the seat would read that lowered
    #: floor as the plate's ground and chase the object down with it, and
    #: the terrain would be coplanar with the plate again.  0.0 for a
    #: tunnel wall plate (its stations read at-grade ground) and for every
    #: plan written before 11t — the pre-11t law exactly.
    plate_clearance_m: float = 0.0
    #: THE FOUNDATION SKIRT (owner RULINGS 2026-09-10ag; spec §22.3):
    #: this member's resource carries a uniform below-zero extent across
    #: its footprint (``airport/skirt.is_skirt``).  A body EVERY one of
    #: whose members is skirted seats at its LOW-side foot instead of
    #: 10i's median, so the low side touches the ground and the high side
    #: buries into the skirt.  Absent from an older plan = ``False`` =
    #: the pre-10ag law exactly.
    skirted: bool = False
    #: THE ELEVATED DECK (owner RULINGS 2026-09-11a; spec §17.5;
    #: ``airport/deck_signature.elevated_deck``): this member's resource
    #: carries a PLATE on PIERS — a plate elevated over its own floor
    #: whose ground-contact footprint is a small fraction of it.  It is
    #: the GATE on the cross-placement abutment group: only an elevated
    #: deck may become the JUNIOR of a body in another placement (a
    #: building seats on its own feet, 10i).  Absent from an older plan
    #: = ``False`` = no cross-placement group at all.
    elevated_deck: bool = False


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
                               [list(f) for f in p.feet], p.line,
                               [[list(v) for v in r] for r in p.rings]]
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
                    "deck_end_stations": [[a, b] for a, b in m.deck_end_stations],
                    "plate_y": m.plate_y,
                    "plate_clearance_m": m.plate_clearance_m,
                    "plate_stations": [[a, b] for a, b in m.plate_stations],
                    "skirted": m.skirted,
                    "elevated_deck": m.elevated_deck,
                } for m in u.members],
            } for u in self.units],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "RebakePlan":
        # Version 9 is version 8 plus ``Member.elevated_deck`` (owner
        # RULINGS 2026-09-11a), version 8 is version 7 plus
        # ``RebakePlan.abutments`` (RULINGS
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
                                 bool(p[11]) if len(p) > 11 else False,
                                 _rings(p[12] if len(p) > 12 else ()))
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
                deck_end_stations=tuple((float(a), float(b)) for a, b
                                        in m.get("deck_end_stations", ())),
                plate_y=None if m.get("plate_y") is None else float(m["plate_y"]),
                plate_stations=tuple((float(a), float(b)) for a, b in m.get("plate_stations", ())),
                plate_clearance_m=float(m.get("plate_clearance_m") or 0.0),
                skirted=bool(m.get("skirted", False)),
                elevated_deck=bool(m.get("elevated_deck", False)),
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
