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

:func:`apply` is pure: the placement plan the stage built, with every
seated row taken out of the conversions, splits, riders and kept list and
written ``OBJECT_MSL`` at its hand-set zero (an ``MslSeat`` whose ``why``
is :data:`WHY`).  A split row is placed WHOLE: the user moved the object,
not its cut bodies.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import json
import os
import tempfile
import typing as _t

from ..model.placement import MslSeat

__all__ = ["SEATS_FILENAME", "WHY", "UserSeat", "seats_path", "read", "set_seat",
           "digest", "apply"]

#: ``<patch dir>/o4_user_object_seats_<ICAO>.json``.
SEATS_FILENAME = "o4_user_object_seats_{icao}.json"
#: ``MslSeat.why`` of a hand-set seat (what ``object_seat`` reports as
#: "Set by hand").
WHY = "user"
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


def apply(plan: _t.Any, files: _t.Sequence, seats: _t.Mapping[int, UserSeat],
          dump: _t.Any) -> tuple[_t.Any, tuple, tuple[int, ...], tuple[str, ...]]:
    """``(plan, files, rows seated, refusals)``: ``plan`` (a
    ``PlacementPlan``) with every seat whose row still matches written at
    its hand-set zero, and ``files`` without the cut bodies of the splits
    that seat replaced."""
    rows = list(getattr(dump, "placements", ()) or ())
    take: dict[int, UserSeat] = {}
    refused: list[str] = []
    for idx in sorted(seats):
        why = _refusal(seats[idx], rows)
        if why is None:
            take[idx] = seats[idx]
        else:
            refused.append(why)
    if not take:
        return plan, tuple(files), (), tuple(refused)
    msl = tuple(m for m in plan.msl_seats if m.index not in take) + tuple(
        MslSeat(i, str(rows[i].def_path), float(rows[i].lon), float(rows[i].lat),
                float(rows[i].heading_deg), float(s.zero_m), WHY)
        for i, s in take.items())
    splits = tuple(s for s in plan.splits if s.placement.index not in take)
    kept_bodies = {b.new_resource for s in splits for b in s.bodies}
    dropped = {b.new_resource for s in plan.splits if s.placement.index in take
               for b in s.bodies} - kept_bodies
    plan = _dc.replace(
        plan, msl_seats=msl, splits=splits,
        conversions=tuple(c for c in plan.conversions if c.index not in take),
        riders=tuple(r for r in plan.riders if r.index not in take),
        kept=tuple(k for k in plan.kept if k.index not in take))
    files = tuple(f for f in files if getattr(f, "resource", None) not in dropped)
    return plan, files, tuple(sorted(take)), tuple(refused)
