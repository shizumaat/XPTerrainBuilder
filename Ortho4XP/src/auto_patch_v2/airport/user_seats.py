"""HAND-SET OBJECT SEATS (issue #1703): the elevations a user gave pack
objects in the patch editor, and the one rule the object stage applies
them by.

A hand-set seat is a USER EDIT (owner RULINGS 2026-10-15d: what the user
edits is what gets built): the object stage never overrides it.  Owner
decision on #1703 (1)(b): it moves ONLY the object — the ground stays as
solved, nothing is regraded.

The file, beside the patch: ``o4_user_object_seats_<ICAO>.json``::

    {"version": 1, "icao": "KXYZ",
     "seats": [{"index": 812, "model": "objects/terminal.obj",
                "lat": 45.1, "lon": -123.2, "zero_m": 61.5}, ...]}

``index`` is the placement's DSF row (the key the placement plan names it
by), ``model`` / ``lat`` / ``lon`` the row as the user saw it: a seat whose
row no longer says that (the pack was updated) is NOT applied, and is
reported.  ``zero_m`` is where the object's authored zero stands, m MSL.

THE SEATS ARE A LAYER OF THE PACK DSF'S WRITE (owner on #1703,
2026-11-03: "yes, apply only the objects you set by hand"), like the 3D
forest upgrade (#1360) and the accepted missing-art omission (#433):
``dsf_write.write_pack(seats=)`` applies them over every airport's
composed placement edits (:func:`apply`) and records them in the DSF's
``o4_placement_provenance.json`` entry (:data:`RECORD_KEY`), so every
later write of that DSF — a placement, a forest upgrade, an omission —
keeps them, and the airport's own recorded edits stay as the placement
plan built them (an Automatic puts the row back exactly).  A build that
uses an edited patch re-places the pack against its mesh like any other
(owner RULINGS 2026-11-03e, #1637), the seats layered on that write.

:func:`apply` is pure: a placement plan with every seated row taken out
of the conversions, splits, riders and kept list and written
``OBJECT_MSL`` at its hand-set zero (an ``MslSeat`` whose ``why`` is
:data:`WHY`).  A split row is placed WHOLE: the user moved the object,
not its cut bodies (which stay in the pack, recorded, for the Undo).
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import json
import os
import tempfile
import typing as _t

from ..model.placement import MslSeat

__all__ = ["RECORD_KEY", "SEATS_FILENAME", "WHY", "UserSeat", "seats_path", "read",
           "set_seat", "digest", "apply", "placements", "record", "recorded",
           "merged", "union"]

#: ``<patch dir>/o4_user_object_seats_<ICAO>.json``.
SEATS_FILENAME = "o4_user_object_seats_{icao}.json"
#: ``MslSeat.why`` of a hand-set seat (what ``object_seat`` reports as
#: "Set by hand").
WHY = "user"
#: the pack DSF's record row of the seats its last write applied
RECORD_KEY = "user_seats"
_VERSION = 1
#: A row still says what the user saw within this (the DSF pool quantum
#: is ~5e-7 deg; the editor reads the same dump the stage does).
_SAME_DEG = 2.0e-6


@_dc.dataclass(frozen=True)
class UserSeat:
    """One hand-set seat."""

    index: int
    model: str
    lat: float
    lon: float
    zero_m: float

    def to_dict(self) -> dict:
        return {"index": self.index, "model": self.model, "lat": self.lat,
                "lon": self.lon, "zero_m": self.zero_m}

    @classmethod
    def from_dict(cls, d: _t.Mapping) -> "UserSeat":
        return cls(int(d["index"]), str(d.get("model", "")), float(d["lat"]),
                   float(d["lon"]), float(d["zero_m"]))


def seats_path(patch_dir: str, icao: str) -> str:
    return os.path.join(patch_dir, SEATS_FILENAME.format(icao=str(icao).upper()))


def read(patch_dir: str, icao: str) -> dict[int, UserSeat]:
    """``{row: seat}``; empty when there is no file.  Raises ``ValueError``
    on a file this version cannot read."""
    path = seats_path(patch_dir, icao)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("version") != _VERSION:
        raise ValueError(f"{os.path.basename(path)}: version {doc.get('version')!r} "
                         f"is not {_VERSION}")
    return {s.index: s for s in (UserSeat.from_dict(d) for d in doc.get("seats") or ())}


def _write(patch_dir: str, icao: str, seats: _t.Mapping[int, UserSeat]) -> str:
    """Write ``seats`` atomically (no seat left: the file is removed);
    returns the path."""
    path = seats_path(patch_dir, icao)
    if not seats:
        if os.path.isfile(path):
            os.remove(path)
        return path
    os.makedirs(patch_dir, exist_ok=True)
    doc = {"version": _VERSION, "icao": str(icao).upper(),
           "seats": [seats[k].to_dict() for k in sorted(seats)]}
    fd, tmp = tempfile.mkstemp(prefix=".seats-", suffix=".tmp", dir=patch_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def set_seat(patch_dir: str, icao: str, seat: UserSeat | None, *,
             index: int) -> UserSeat | None:
    """Set (``seat``) or clear (``None``) row ``index``'s hand-set seat;
    returns the one it replaced."""
    seats = read(patch_dir, icao)
    previous = seats.pop(int(index), None)
    if seat is not None:
        seats[int(index)] = seat
    _write(patch_dir, icao, seats)
    return previous


def digest(patch_dir: str, icao: str) -> str:
    """The seats' content digest ("" with none): the object stage's reuse
    key carries it, so a changed seat re-runs the stage."""
    path = seats_path(patch_dir, icao)
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _refusal(seat: UserSeat, rows: _t.Sequence) -> str | None:
    """Why ``seat`` does not name its row any more, or ``None``."""
    if not 0 <= seat.index < len(rows):
        return f"row {seat.index} is past the pack's {len(rows)} placements"
    row = rows[seat.index]
    if seat.model and str(row.def_path) != seat.model:
        return f"row {seat.index} now places {row.def_path}, not {seat.model}"
    if abs(float(row.lat) - seat.lat) > _SAME_DEG or abs(float(row.lon) - seat.lon) > _SAME_DEG:
        return f"row {seat.index} ({seat.model}) has moved since its elevation was set"
    return None


def apply(plan: _t.Any, seats: _t.Mapping[int, UserSeat], rows: _t.Sequence
          ) -> tuple[_t.Any, tuple[int, ...], tuple[str, ...]]:
    """``(plan, rows seated, refusals)``: ``plan`` (a ``PlacementPlan``)
    with every seat whose row (``rows``, the pristine dump's placements)
    still matches written at its hand-set zero, and no other row
    touched."""
    take: dict[int, UserSeat] = {}
    refused: list[str] = []
    for idx in sorted(seats):
        why = _refusal(seats[idx], rows)
        if why is None:
            take[idx] = seats[idx]
        else:
            refused.append(why)
    if not take:
        return plan, (), tuple(refused)
    msl = tuple(m for m in plan.msl_seats if m.index not in take) + tuple(
        MslSeat(i, str(rows[i].def_path), float(rows[i].lon), float(rows[i].lat),
                float(rows[i].heading_deg), float(s.zero_m), WHY)
        for i, s in take.items())
    plan = _dc.replace(
        plan, msl_seats=msl,
        splits=tuple(s for s in plan.splits if s.placement.index not in take),
        conversions=tuple(c for c in plan.conversions if c.index not in take),
        riders=tuple(r for r in plan.riders if r.index not in take),
        kept=tuple(k for k in plan.kept if k.index not in take))
    return plan, tuple(sorted(take)), tuple(refused)


def placements(dump_text_path: str) -> list:
    """The placement rows of a DSF text dump (``dsf.read_dump``'s, whose
    ordinals are the plan's and the seats' ``index``)."""
    from .dsf import read_dump
    return list(read_dump(dump_text_path, lambda _p: False).placements)


# ── the pack DSF's record ───────────────────────────────────────────────

ByAirport = _t.Mapping[str, _t.Mapping[int, UserSeat]]


def union(by_airport: ByAirport) -> dict[int, UserSeat]:
    """Every airport's seats as one ``{row: seat}`` (rows are the DSF's)."""
    out: dict[int, UserSeat] = {}
    for icao in sorted(by_airport):
        out.update(by_airport[icao])
    return out


def merged(prior: ByAirport, given: ByAirport | None,
           drop: _t.Collection[str] = ()) -> dict[str, dict[int, UserSeat]]:
    """The seats a write applies: the recorded ones (``prior``) with each
    airport in ``given`` replaced by its seats there, every airport in
    ``drop`` removed (RULINGS 2026-10-12d: an airport left without a patch
    is no longer seated), and no airport without a seat."""
    out = {str(k).upper(): dict(v) for k, v in prior.items()}
    out.update({str(k).upper(): dict(v) for k, v in (given or {}).items()})
    for icao in drop:
        out.pop(str(icao).upper(), None)
    return {k: v for k, v in out.items() if v}


def record(pristine_sha256: str, by_airport: ByAirport,
           applied: _t.Sequence[int], time: str) -> dict:
    """The :data:`RECORD_KEY` row: the seats, per airport, and the rows
    the write placed by them."""
    return {"pristine_sha256": pristine_sha256, "time": time,
            "applied": sorted(int(i) for i in applied),
            "airports": {icao: [by_airport[icao][k].to_dict()
                                for k in sorted(by_airport[icao])]
                         for icao in sorted(by_airport)}}


def recorded(entry: _t.Mapping[str, _t.Any] | None,
             pristine_sha256: str | None) -> dict[str, dict[int, UserSeat]]:
    """The seats the DSF's last write applied, per airport; ``{}`` when
    none is recorded, when they belong to another pristine file (with
    ``pristine_sha256=None`` that is not asked), or when the row does not
    read."""
    row = (entry or {}).get(RECORD_KEY)
    if not isinstance(row, dict) or (pristine_sha256 is not None
                                     and row.get("pristine_sha256") != pristine_sha256):
        return {}
    try:
        return {str(icao): {s.index: s for s in map(UserSeat.from_dict, seats)}
                for icao, seats in (row.get("airports") or {}).items()}
    except (KeyError, TypeError, ValueError, AttributeError):
        return {}
