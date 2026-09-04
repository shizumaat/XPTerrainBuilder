"""THE RE-SEAT PLAN AND RESULT — data only (RULINGS 2026-09-04i 04f-1).

A :class:`RebakePlan` is what the tile build writes beside the patch
(``o4_v2_rebake_<ICAO>.json``) and the post-mesh seat reads: the rigid
UNITS — one per anchor spelling ``(lat, lon, AGL)``, so a shared-datum
family (memory ``shared-datum-pack-authoring``) is ONE unit with ONE
delta — and per member the witnesses its seat is read from (the FEET:
the object's own lowest band, authored ``y`` + world position; for a
hard-deck object the deck ring, its deck-top ``y`` and the SOLVED
surface's value at the deck).  Built by ``airport/rebake_plan.py``,
seated by ``emit/rebake.py``.  No numpy, no shapely, no I/O here.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import typing as _t

from .frame import LL

__all__ = ["Foot", "Member", "Unit", "RebakePlan", "MemberSeat", "UnitSeat",
           "SeatResult", "PLAN_VERSION", "PLAN_FILENAME", "DATUM_FEET",
           "DATUM_DECK_TOP"]

PLAN_VERSION = 2       # 2: the deck signature's end lines / profile (04k, M6b)
#: ``<patch dir>/o4_v2_rebake_<ICAO>.json`` — beside v1's worklist.
PLAN_FILENAME = "o4_v2_rebake_{icao}.json"

DATUM_FEET = "feet"
DATUM_DECK_TOP = "deck_top"


# ── the plan ─────────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Foot:
    """One contact witness: world position and authored ``y``."""

    lat: float
    lon: float
    y: float


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
    feet: tuple[Foot, ...]
    deck_ring: tuple[LL, ...] | None = None
    deck_top_y: float | None = None
    deck_datum_z: float | None = None
    #: THE DECK SIGNATURE (04k; ``airport/deck_signature.py``): ``"flag"``
    #: (``ATTR_hard_deck``), ``"signature"`` (a plate spanning a bridge
    #: way / below-grade region), ``"family"`` (a member of a deck family
    #: without a plate: it seats WITH the deck), else ``""``.
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


@_dc.dataclass(frozen=True)
class Unit:
    """One rigid unit: every placement sharing one anchor spelling."""

    id: str
    anchor: LL
    agl_m: float
    members: tuple[Member, ...]


@_dc.dataclass(frozen=True)
class RebakePlan:
    """What the post-mesh seat reads; JSON round-trips exactly."""

    icao: str
    pack_name: str
    pack_root: str
    units: tuple[Unit, ...]
    skipped: tuple[tuple[str, str], ...]
    counts: _t.Mapping[str, int]

    def bounds(self) -> tuple[float, float, float, float]:
        """``(min_lon, min_lat, max_lon, max_lat)`` over every witness."""
        lats: list[float] = []
        lons: list[float] = []
        for u in self.units:
            lats.append(u.anchor[0]); lons.append(u.anchor[1])
            for m in u.members:
                for f in m.feet:
                    lats.append(f.lat); lons.append(f.lon)
                for la, lo in (m.deck_ring or ()):
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
            "units": [{
                "id": u.id, "anchor": [u.anchor[0], u.anchor[1]], "agl_m": u.agl_m,
                "members": [{
                    "id": m.id, "resource": m.resource,
                    "authored_path": m.authored_path, "live_path": m.live_path,
                    "heading_deg": m.heading_deg,
                    "feet": [[f.lat, f.lon, f.y] for f in m.feet],
                    "deck_ring": None if m.deck_ring is None
                    else [[a, b] for a, b in m.deck_ring],
                    "deck_top_y": m.deck_top_y, "deck_datum_z": m.deck_datum_z,
                    "deck_kind": m.deck_kind,
                    "deck_ends": None if m.deck_ends is None
                    else [[[a, b] for a, b in e] for e in m.deck_ends],
                    "deck_profile": [[s, y] for s, y in m.deck_profile],
                    "deck_evidence": list(m.deck_evidence),
                    "deck_stations": [list(st) for st in m.deck_stations],
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
                feet=tuple(Foot(float(a), float(b), float(c)) for a, b, c in m["feet"]),
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
            ) for m in u["members"])) for u in d["units"])
        return cls(icao=str(d["icao"]), pack_name=str(d["pack_name"]),
                   pack_root=str(d["pack_root"]), units=units,
                   skipped=tuple((str(a), str(b)) for a, b in d.get("skipped", ())),
                   counts=dict(d.get("counts", {})))

    @classmethod
    def from_json(cls, text: str) -> "RebakePlan":
        return cls.from_dict(json.loads(text))



# ── the seat ─────────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class MemberSeat:
    """One member's own seat (before the unit's one delta)."""

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
    #: Whether this member FOUNDED the unit's seat (a deck plate with a
    #: measured abutment grade; a foot member over the witness floor).
    founding: bool = False


@_dc.dataclass(frozen=True)
class UnitSeat:
    """The unit's ONE delta, or why it has none."""

    unit_id: str
    resources: tuple[str, ...]
    anchor_ground_m: float | None
    datum: str
    delta_m: float | None
    seat_datum_m: float | None
    members: tuple[MemberSeat, ...]
    skip_reason: str | None = None
    findings: tuple[str, ...] = ()
    #: HELD: v2 cannot judge the unit (no founding witness on land) — the
    #: pack's CURRENT bytes are kept, neither seated nor reverted; a
    #: finding, never a silent change to an owner-accepted state.
    held: bool = False

    @property
    def bakes(self) -> bool:
        return self.delta_m is not None and self.skip_reason is None


@_dc.dataclass(frozen=True)
class SeatResult:
    icao: str
    units: tuple[UnitSeat, ...]

    def counts(self) -> dict[str, int]:
        c = {"units": len(self.units), "baked": 0, "below_threshold": 0,
             "held": 0, "skipped": 0, "resources_baked": 0, "findings": 0,
             "deck_units": 0}
        for u in self.units:
            c["findings"] += len(u.findings)
            if u.datum == DATUM_DECK_TOP:
                c["deck_units"] += 1
            if u.bakes:
                c["baked"] += 1
                c["resources_baked"] += len(u.resources)
            elif u.skip_reason and u.skip_reason.startswith("below_threshold"):
                c["below_threshold"] += 1
            elif u.held:
                c["held"] += 1
            else:
                c["skipped"] += 1
        return c

    def to_dict(self) -> dict[str, _t.Any]:
        return {"icao": self.icao, "counts": self.counts(),
                "units": [_dc.asdict(u) for u in self.units]}
