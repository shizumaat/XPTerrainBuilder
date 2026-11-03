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
"""
from __future__ import annotations

import math
import os
import typing as _t

import O4_File_Names as FNAMES

__all__ = ["object_seat_set", "placed_zero", "user_seat_for"]


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
    seat = _us.union(_us.recorded(entry, None)).get(int(index))
    return None if seat is None else seat.zero_m


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


def object_seat_set(tile: str, icao: str, index: int, model: str, lat: float,
                    lon: float, bottom_m: float | None = None,
                    y_min: float | None = None, zero_m: float | None = None) -> dict:
    """ENGINE COMMAND ``object_seat_set``: row ``index``'s hand-set seat
    becomes ``zero_m``, or ``bottom_m - y_min``; neither clears it (the
    object stage seats it again).  Replies ``{index, zero_m,
    previous_zero_m, path}`` — ``previous_zero_m`` is what an Undo sends."""
    from auto_patch_v2.airport import user_seats as _us
    try:
        row = int(index)
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("object_seat_set: index must be a row number and lat, lon "
                         "numbers.") from None
    zero = _number("zero_m", zero_m)
    bottom = _number("bottom_m", bottom_m)
    if zero is None and bottom is not None:
        zero = bottom - (_number("y_min", y_min) or 0.0)
    seat = None if zero is None else _us.UserSeat(row, str(model or ""), la, lo,
                                                  round(zero, 3))
    patch_dir = _patch_dir(tile)
    previous = _us.set_seat(patch_dir, icao, seat, index=row)
    return {"index": row, "zero_m": None if seat is None else seat.zero_m,
            "previous_zero_m": None if previous is None else previous.zero_m,
            "path": os.path.basename(_us.seats_path(patch_dir, icao))}
