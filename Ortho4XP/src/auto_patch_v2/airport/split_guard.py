"""THE SPLIT GUARD — which splits a DSF can carry (issue #1246).

A split re-anchors each body at its own point.  ``DSFTool --text2dsf``
refuses an object placed outside the DSF's tile (``ERROR: could not
place object LON, LAT``) and then refuses the WHOLE file, so one body of
a long object family that reached past the tile edge left every pack
object unconverted and unseated.  Two rules, both general:

* a split with a body anchor outside the tile box (the dump's
  ``PROPERTY sim/west|east|south|north``) is NOT made: the placement is
  written whole, as authored, and is listed as ``Kept``;
* a split whose body DSFTool still refuses is undone the same way and
  the write is tried again — one object never fails the pack;
* a split whose body file the pack cannot hold (a read-only folder, as
  vendor archives ship ``Vehicles/GPUs``) is undone BEFORE anything is
  written: :func:`write_files` raised half-way through, after the
  restore had removed the previous write's bodies, and the live DSF
  still named them (KLAX 1.0.464: 165 of 195 bodies missing in the sim).

ONE AUTHORITY FOR A SEAT AFTER THE WRITE (#1903).  Undoing a split draws
EVERY body at the authored row, so a body whose seat a cut was built to
(an entrance face on its portal's floor) was drawn 4-5 m from that floor
(LOWS ``domiki_lows_48.obj``: the east face stands past the tile edge, the
whole object went back to its shared anchor 650 m away).  The plan now
asks first (:func:`on_tile`): a body off the tile whose zero the plan
KNOWS is anchored on the tile and written ``OBJECT_MSL`` at that zero, so
the split stands and every body keeps its seat.  Only a split with an
off-tile body of UNKNOWN zero is left for the undo above.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import re
import typing as _t

from ..model.placement import Kept, PlacementPlan

__all__ = ["tile_box", "off_tile_splits", "refused_point", "split_at",
           "without_splits", "unwritable_splits", "box_of_tile", "on_tile",
           "ON_TILE_REASON"]

_REFUSED = re.compile(r"could not place object\s+(-?[\d.]+)\s*,\s*(-?[\d.]+)")
#: a refused point is matched to a body anchor within this (deg, ~1 m)
_MATCH_DEG = 1e-5
#: how far inside the tile edge an off-tile body is anchored (deg, ~1 m):
#: well clear of the pool's requantisation (``model.placement.TOL_DEG``)
_INSIDE_DEG = 1e-5
#: the anchor reason a body :func:`on_tile` re-anchored opens with
ON_TILE_REASON = "off the tile: anchored on it, seated by its row (#1903)"


def tile_box(text: str) -> tuple[float, float, float, float] | None:
    """``(west, south, east, north)`` from the dump's properties."""
    got: dict[str, float] = {}
    for raw in text.splitlines():
        toks = raw.split()
        if len(toks) == 3 and toks[0] == "PROPERTY" and toks[1] in (
                "sim/west", "sim/south", "sim/east", "sim/north"):
            got[toks[1][4:]] = float(toks[2])
    if len(got) != 4:
        return None
    return got["west"], got["south"], got["east"], got["north"]


def off_tile_splits(plan: PlacementPlan, box: _t.Sequence[float] | None
                    ) -> list[int]:
    """The placement indices of splits with a body anchor off the tile."""
    if box is None:
        return []
    w, s, e, n = box
    return [sp.placement.index for sp in plan.splits
            if any(not (w <= b.anchor.lon <= e and s <= b.anchor.lat <= n)
                   for b in sp.bodies)]


def box_of_tile(tile: _t.Sequence[int] | None, dsf_path: str = ""
                ) -> tuple[float, float, float, float] | None:
    """``(west, south, east, north)`` of the ``(lat, lon)`` tile, else of
    the tile ``dsf_path`` is named for (``+47+012.dsf``), else ``None``."""
    if tile is None:
        m = re.search(r"([+-]\d{2})([+-]\d{3})\.dsf$", os.path.basename(dsf_path or ""))
        if m is None:
            return None
        tile = (int(m.group(1)), int(m.group(2)))
    la, lo = int(tile[0]), int(tile[1])
    return float(lo), float(la), float(lo + 1), float(la + 1)


def _inside(box: _t.Sequence[float], lat: float, lon: float) -> bool:
    w, s, e, n = box
    return w <= lon <= e and s <= lat <= n


def on_tile(record: _t.Any, box: _t.Sequence[float] | None,
            zero_of: _t.Callable[[_t.Any], float | None]) -> _t.Any:
    """``record`` (a ``placement_record.Split``) with each body anchored
    off ``box`` moved onto it and seated by its ROW (module doc, #1903).

    A body's zero is ``zero_of(body)`` (the seat a reader gave it with no
    ground under it to carry it) or the plan's own ``surface_z - y_zero``.
    The body keeps its geometry and its ``y_zero``: its anchor is the
    nearest point inside the tile, its offset is re-read from the
    placement's frame there, and its row is ``OBJECT_MSL`` at
    ``zero + y_zero`` (``Body.msl_z``) — also its ``surface_z``, so every
    reader of ``surface_z - y_zero`` reads the seat the row draws.  When any off-tile body has no
    known zero, when one carries a baked seat tilt, or when the frame's own
    origin is off the tile, the record is returned UNCHANGED and the
    writer undoes the split as before (:func:`off_tile_splits`)."""
    if box is None or not _inside(box, record.lat, record.lon):
        return record
    zeros: dict[int, float] = {}
    for k, b in enumerate(record.bodies):
        a = b.anchor
        if _inside(box, a.lat, a.lon):
            continue
        z = zero_of(b)
        if z is None and a.surface_z is not None:
            z = float(a.surface_z) - float(a.y_zero)
        seat = getattr(b, "seat", None)
        if z is None or (seat is not None and getattr(seat, "applied", False)):
            return record
        zeros[k] = z
    if not zeros:
        return record
    # lazy: placement_file reads the records this module's writer side
    # never needs (dsf_write imports this module)
    from .placement_file import authored_offset
    w, s, e, n = box
    out = []
    for k, b in enumerate(record.bodies):
        if k not in zeros:
            out.append(b)
            continue
        a = b.anchor
        la = min(max(a.lat, s + _INSIDE_DEG), n - _INSIDE_DEG)
        lo = min(max(a.lon, w + _INSIDE_DEG), e - _INSIDE_DEG)
        y0 = float(a.y_zero)
        row = zeros[k] + y0
        a2 = _dc.replace(a, lat=la, lon=lo, surface_z=row,
                         offset=authored_offset(la, lo, y0, record.lat,
                                                record.lon, record.heading),
                         reason=f"{ON_TILE_REASON} at zero {zeros[k]:.2f}; "
                                f"was: {a.reason}")
        out.append(_dc.replace(b, anchor=a2, msl_z=row, lift_m=0.0))
    return _dc.replace(record, bodies=tuple(out))


def refused_point(message: str) -> tuple[float, float] | None:
    """``(lon, lat)`` of the object DSFTool said it could not place."""
    m = _REFUSED.search(message or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def split_at(plan: PlacementPlan, lon: float, lat: float) -> int | None:
    """The split whose body is anchored at ``(lon, lat)``, if any."""
    for sp in plan.splits:
        for b in sp.bodies:
            if (abs(b.anchor.lon - lon) <= _MATCH_DEG
                    and abs(b.anchor.lat - lat) <= _MATCH_DEG):
                return sp.placement.index
    return None


def without_splits(plan: PlacementPlan, indices: _t.Collection[int],
                   reason: str) -> PlacementPlan:
    """``plan`` with those splits undone: each placement is ``Kept``."""
    idx = set(indices)
    gone = [sp for sp in plan.splits if sp.placement.index in idx]
    if not gone:
        return plan
    return _dc.replace(
        plan, splits=tuple(sp for sp in plan.splits
                           if sp.placement.index not in idx),
        kept=plan.kept + tuple(Kept(sp.placement.index, sp.placement.resource,
                                    reason) for sp in gone))


def _can_write(path: str) -> bool:
    """May this process create (or replace) the file at ``path``?  The
    file itself when it exists, else its nearest existing folder."""
    if os.path.exists(path):
        return os.access(path, os.W_OK)
    d = os.path.dirname(path)
    while d and not os.path.isdir(d):
        up = os.path.dirname(d)
        if up == d:
            return False
        d = up
    return bool(d) and os.access(d, os.W_OK | os.X_OK)


def unwritable_splits(plan: PlacementPlan, pack_root: str) -> list[int]:
    """The placement indices of splits with a body file the pack cannot
    hold (its folder is read-only): written whole instead, so one locked
    folder never tears the pack."""
    out: list[int] = []
    for sp in plan.splits:
        if any(not _can_write(os.path.join(
                pack_root, *b.new_resource.replace("\\", "/").split("/")))
               for b in sp.bodies):
            out.append(sp.placement.index)
    return out
