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

AN OBJECT GROUP MOVES AS ONE (issue #1970, owner 2026-11-08: "it should
select, and only allow movement of entire object groups"): a seat may
carry ``offset_m`` instead of ``zero_m`` — a SPLIT row whose every body
the write lifts by that many metres over the seat its placement plan
gave it (``OBJECT_MSL`` at the body's planned zero + ``offset_m``).  The
editor writes one such seat, with one offset, for every row of a group
(``o4_engine/object_group``: the rows cut into bodies of the same §16g
units), so the group moves rigidly and no part moves alone.  A KEPT-whole
row of the group (owner RULINGS 2026-11-09a (15), "stay and move
together") is written ``OBJECT_MSL`` at the zero its authored row lands
at (the plan's ``kept`` ``zero_m``) plus the same offset.

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
           "set_seat", "set_seats", "digest", "apply", "placements", "record", "recorded",
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
    zero_m: float | None
    #: #1970: a group's rigid lift of this split row's bodies (instead of
    #: ``zero_m``, which is then ``None``)
    offset_m: float | None = None

    def to_dict(self) -> dict:
        d = {"index": self.index, "model": self.model, "lat": self.lat,
             "lon": self.lon, "zero_m": self.zero_m}
        if self.offset_m is not None:
            d["offset_m"] = self.offset_m
        return d

    @classmethod
    def from_dict(cls, d: _t.Mapping) -> "UserSeat":
        zero, off = d.get("zero_m"), d.get("offset_m")
        if (zero is None) == (off is None):
            raise ValueError(f"seat on row {d.get('index')}: give zero_m or offset_m")
        return cls(int(d["index"]), str(d.get("model", "")), float(d["lat"]),
                   float(d["lon"]), None if zero is None else float(zero),
                   None if off is None else float(off))


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
    return set_seats(patch_dir, icao, {int(index): seat})[int(index)]


def set_seats(patch_dir: str, icao: str, given: _t.Mapping[int, UserSeat | None]
              ) -> dict[int, UserSeat | None]:
    """Set or clear (``None``) several rows' seats in ONE write (a group,
    #1970); returns ``{row: the seat it replaced}``."""
    seats = read(patch_dir, icao)
    previous = {int(i): seats.pop(int(i), None) for i in given}
    seats.update({int(i): s for i, s in given.items() if s is not None})
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


def _lifted(split: _t.Any, offset_m: float) -> _t.Any:
    """``split`` with every body that has a planned zero written
    ``OBJECT_MSL`` at it plus ``offset_m`` (#1970); a body off every graded
    face (no ``surface_z``) and without a row seat stays as planned."""
    out = []
    for b in split.bodies:
        if b.msl_z is not None:
            zero = float(b.msl_z)
        elif b.surface_z is not None:
            zero = float(b.surface_z) - float(b.y_zero) + float(b.lift_m or 0.0)
        else:
            out.append(b)
            continue
        out.append(_dc.replace(b, msl_z=round(zero + offset_m, 4)))
    return _dc.replace(split, bodies=tuple(out))


def _kept_lifted(plan: _t.Any, offsets: _t.Mapping[int, UserSeat], rows: _t.Sequence
                 ) -> tuple[tuple, tuple[MslSeat, ...]]:
    """The group's KEPT-whole rows (owner RULINGS 2026-11-09a (15)): each
    moved as one whole, ``OBJECT_MSL`` at the zero its authored row lands
    at plus the offset — ``(kept left, the rows' seats)``."""
    kept, msl = [], []
    for k in plan.kept:
        seat = offsets.get(k.index)
        if seat is None or k.zero_m is None:
            kept.append(k)
            continue
        r = rows[k.index]
        msl.append(MslSeat(k.index, str(r.def_path), float(r.lon), float(r.lat),
                           float(r.heading_deg),
                           round(float(k.zero_m) + float(seat.offset_m), 4), WHY))
    return tuple(kept), tuple(msl)


def _apply_offsets(plan: _t.Any, offsets: _t.Mapping[int, UserSeat], rows: _t.Sequence
                   ) -> tuple[_t.Any, tuple[int, ...], tuple[str, ...]]:
    """The group seats (#1970): each split row's bodies lifted rigidly, each
    kept-whole row of the group moved whole by the same offset."""
    splits, seated = [], []
    for s in plan.splits:
        seat = offsets.get(s.placement.index)
        if seat is not None:
            s = _lifted(s, float(seat.offset_m))
            seated.append(s.placement.index)
        splits.append(s)
    kept, msl = _kept_lifted(plan, offsets, rows)
    seated += [m.index for m in msl]
    refused = tuple(f"row {i} ({offsets[i].model}) is no longer in its group; "
                    f"its group's elevation is not applied"
                    for i in sorted(set(offsets) - set(seated)))
    plan = _dc.replace(plan, splits=tuple(splits), kept=kept,
                       msl_seats=tuple(plan.msl_seats) + msl)
    return plan, tuple(sorted(seated)), refused


def apply(plan: _t.Any, seats: _t.Mapping[int, UserSeat], rows: _t.Sequence
          ) -> tuple[_t.Any, tuple[int, ...], tuple[str, ...]]:
    """``(plan, rows seated, refusals)``: ``plan`` (a ``PlacementPlan``)
    with every seat whose row (``rows``, the pristine dump's placements)
    still matches written at its hand-set zero — or, a group seat, its
    bodies lifted by its offset — and no other row touched."""
    take: dict[int, UserSeat] = {}
    offsets: dict[int, UserSeat] = {}
    refused: list[str] = []
    for idx in sorted(seats):
        why = _refusal(seats[idx], rows)
        if why is not None:
            refused.append(why)
        elif seats[idx].offset_m is not None:
            offsets[idx] = seats[idx]
        else:
            take[idx] = seats[idx]
    lifted: tuple[int, ...] = ()
    if offsets:
        plan, lifted, more = _apply_offsets(plan, offsets, rows)
        refused.extend(more)
    if not take:
        return plan, lifted, tuple(refused)
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
    return plan, tuple(sorted((*take, *lifted))), tuple(refused)


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
