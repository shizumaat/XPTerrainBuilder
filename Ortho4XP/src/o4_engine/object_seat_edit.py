"""``object_seat_set`` — the patch editor's hand-set object elevation
(protocol 1.30, issue #1703): store, change or clear the seat a user gave
one placed pack object, as a user edit the object stage honours on every
rebuild it places the airport's objects (``airport/user_seats``).

Owner decision on #1703 (1)(b): only the object moves; the ground stays as
solved.  The seat is written at once (it is not part of the patch file, so
saving or reverting the patch neither writes nor drops it); the editor's
Undo sends the previous ``zero_m`` back.

The user gives the object's BOTTOM (m MSL), or its zero for an undo; the
engine turns a bottom into the zero the DSF row carries with the model's
authored ``y_min`` (bottom = zero + ``y_min``).

AN OBJECT THE PLAN CUT INTO PARTS MOVES WITH ITS GROUP (issue #1970,
``object_group``; a kept-whole row seated in a group's structure unit
with it, RULINGS 2026-11-09a (15)): a bottom given for a group row becomes ONE offset over
the build's seat for every row of its group (the group's bottom is its
lowest part's zero), written in one go; ``offset_m`` is the undo's.  No
part of a group is ever seated alone.
"""
from __future__ import annotations

import math
import os
import typing as _t

import O4_File_Names as FNAMES

__all__ = ["object_seat_set", "placed_seat", "placed_zero", "user_seat_for"]


def _patch_dir(tile: str) -> str:
    """The tile's Patches folder (where the patch and its plans live)."""
    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"object_seat_set: {tile!r} is not a tile key like +45-123.")
    return FNAMES.patch_dir(*parsed)


def user_seat_for(tile: str, icao: str, index: int):
    """Row ``index``'s hand-set seat (a ``UserSeat``), or ``None``; an
    unreadable file reads as none."""
    from auto_patch_v2.airport import user_seats as _us
    try:
        return _us.read(_patch_dir(tile), icao).get(int(index))
    except (OSError, ValueError):
        return None


def _pack_dsf(tile: str, icao: str) -> str:
    """The tile DSF of the pack serving ``icao`` (``pack_objects``'s), or ""."""
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import pack as _pack

    from .pack_objects import _tile, xplane_root_for
    lat, lon = _tile(tile)
    xroot = xplane_root_for(lat, lon)
    sel = _pack.select_pack(xroot, str(icao)) if xroot else None
    return _dsf.dsf_path_in_pack(sel.root, lat, lon) if sel is not None else ""


def placed_zero(tile: str, icao: str, index: int, dsf_path: str = "") -> float | None:
    """The zero the pack DSF's last write placed row ``index`` at by hand
    (its record's ``user_seats``), or ``None``.  ``dsf_path``: the DSF the
    placement plan names; without one the pack serving ``icao`` is found."""
    seat = placed_seat(tile, icao, index, dsf_path)
    return None if seat is None else seat.zero_m


def placed_seat(tile: str, icao: str, index: int, dsf_path: str = ""):
    """The hand-set seat (a ``UserSeat``) the pack DSF's last write applied
    to row ``index``, or ``None`` (:func:`placed_zero`'s record read)."""
    from auto_patch_v2.airport import backup_state as _bs
    from auto_patch_v2.airport import user_seats as _us
    try:
        path = dsf_path or _pack_dsf(tile, icao)
    except (OSError, ValueError):
        return None
    if not path:
        return None
    entry = _bs.dsf_entry(_bs.read_record(path), os.path.basename(path))
    row = entry.get(_us.RECORD_KEY)
    if not isinstance(row, dict) or int(index) not in set(row.get("applied") or ()):
        return None
    return _us.union(_us.recorded(entry, None)).get(int(index))


def _number(name: str, v: _t.Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"object_seat_set: {name} must be a number.") from None
    if not math.isfinite(f):
        raise ValueError(f"object_seat_set: {name} must be a finite number.")
    return f


def _group_set(patch_dir: str, icao: str, entries, row: int, zero: float | None,
               bottom: float | None, offset: float | None) -> dict:
    """#1970: ``object_seat_set`` on a row of a group: every row of its
    group takes one offset (from ``offset``, or ``bottom`` over the group's
    lowest part), or none (cleared); ``zero`` (an Undo back to a whole-row
    seat) clears the group and seats ``row`` alone, as it was."""
    from auto_patch_v2.airport import user_seats as _us

    from .object_group import group_rows, group_zeros
    rows = group_rows(entries, row)
    if offset is None and bottom is not None and zero is None:
        zeros = group_zeros(entries, rows)
        if not zeros:
            raise ValueError("object_seat_set: the elevation of this group's parts is "
                             "not known; rebuild the tile first.")
        offset = bottom - min(zeros)

    def seat(r: int, z: float | None, off: float | None):
        ref = entries[r][1].get("placement") or entries[r][1]  # a kept row: its own
        return _us.UserSeat(r, str(ref.get("resource") or ""), float(ref["lat"]),
                            float(ref["lon"]), z, off)
    given = {r: (None if offset is None or zero is not None
                 else seat(r, None, round(offset, 3))) for r in rows}
    if zero is not None:
        given[row] = seat(row, round(zero, 3), None)
    prev = _us.set_seats(patch_dir, icao, given)[row]
    now = given[row]
    return {"index": row, "zero_m": None if now is None else now.zero_m,
            "previous_zero_m": None if prev is None else prev.zero_m,
            "offset_m": None if now is None else now.offset_m,
            "previous_offset_m": None if prev is None else prev.offset_m,
            "rows": list(rows), "path": os.path.basename(_us.seats_path(patch_dir, icao))}


def _plan_entries(tile: str, icao: str):
    """The last build's placement plan for the tile, indexed, or ``None``."""
    from .object_seat import _entries, _plan_path
    try:
        return _entries(_plan_path(tile, icao))
    except (OSError, ValueError):
        return None


def object_seat_set(tile: str, icao: str, index: int, model: str, lat: float,
                    lon: float, bottom_m: float | None = None,
                    y_min: float | None = None, zero_m: float | None = None,
                    offset_m: float | None = None) -> dict:
    """ENGINE COMMAND ``object_seat_set``: row ``index``'s hand-set seat
    becomes ``zero_m``, or ``bottom_m - y_min``; neither clears it (the
    object stage seats it again).  Replies ``{index, zero_m,
    previous_zero_m, offset_m, previous_offset_m, path}`` — the two
    ``previous_*`` are what an Undo sends.  A row the last build's plan cut
    into parts moves with its group (:func:`_group_set`, #1970; the reply
    adds its ``rows``)."""
    from auto_patch_v2.airport import user_seats as _us
    try:
        row = int(index)
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("object_seat_set: index must be a row number and lat, lon "
                         "numbers.") from None
    zero = _number("zero_m", zero_m)
    bottom = _number("bottom_m", bottom_m)
    offset = _number("offset_m", offset_m)
    patch_dir = _patch_dir(tile)
    entries = _plan_entries(tile, icao)
    from .object_group import in_group
    if entries is not None and in_group(entries, row):
        return _group_set(patch_dir, icao, entries, row, zero, bottom, offset)
    if zero is None and bottom is not None:
        zero = bottom - (_number("y_min", y_min) or 0.0)
    seat = None if zero is None else _us.UserSeat(row, str(model or ""), la, lo,
                                                  round(zero, 3))
    previous = _us.set_seat(patch_dir, icao, seat, index=row)
    return {"index": row, "zero_m": None if seat is None else seat.zero_m,
            "previous_zero_m": None if previous is None else previous.zero_m,
            "offset_m": None,
            "previous_offset_m": None if previous is None else previous.offset_m,
            "path": os.path.basename(_us.seats_path(patch_dir, icao))}
