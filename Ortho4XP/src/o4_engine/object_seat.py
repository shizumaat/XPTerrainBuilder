"""``object_seat`` — what the patch editor's object inspector shows for one
placed pack object (protocol 1.24, issue #1702): its height and the
elevations (m MSL) of its top and bottom AS SEATED BY THE LAST BUILD, and
how that seat was chosen.

The seat is READ, never recomputed:

* the placement plan the object stage wrote beside the patch,
  ``o4_v2_placement_<ICAO>.json`` (``placement_write.apply_plan`` step 5),
  keyed by the placement's DSF row (``pack_objects``' ``index``): a SPLIT
  placement's bodies stand at ``placement_coherence.plan_body_zero``; a
  row seat (``msl_seats``) and a rider written ``OBJECT_MSL`` at their
  elevation; a CONVERTED row on the ground; anything else keeps its row
  as the pack wrote it (on the ground, plus its ``OBJECT_AGL`` lift);
* "the ground" is what X-Plane drapes such a row on: the last build's
  mesh at the anchor, else the DEM — the ``cursor_elevation`` answer,
  which says ``pending`` while that source loads (ask again).

The object's height range (``y_min`` / ``y_max``, authored metres from
its zero) is the ``pack_objects`` model's, sent back by the client:
bottom = zero + ``y_min``, top = zero + ``y_max``.  A split whose bodies
stand at different zeros reports the lowest bottom and the highest top.

``lines`` is the inspector's text, one sentence per line, so the Mac app
and the Qt window show the same words.  The record also carries the
plan's own fields (``seat``, ``zero_m``, ``bodies``) for the editor's next
steps on the same selection (#1703 manual elevation, #1697 role override).
Synchronous: one JSON read per plan file version (cached by mtime and
size), then dictionary lookups.
"""
from __future__ import annotations

import json
import math
import os
import threading
import typing as _t

import O4_File_Names as FNAMES
from auto_patch_v2.airport.apt_dat import _file_identity as _stamp  # (mtime_ns, size) or None

__all__ = ["object_seat"]

#: plan path -> (file stamp, {row: (kind, record)})
_PLANS: dict[str, tuple] = {}
_LOCK = threading.Lock()

#: Which plan section seats a row, strongest first: a split row is
#: replaced outright; a row seat, a written rider and a conversion edit the
#: row; ``kept`` only says why the placement was not split.
_SECTIONS = (("splits", "split"), ("msl_seats", "row"), ("riders", "rider"),
             ("conversions", "converted"), ("kept", "kept"))


def _plan_path(tile: str, icao: str) -> str:
    """The tile's placement plan for ``icao`` (beside the patch)."""
    from auto_patch_v2.model.placement import PLAN_FILENAME
    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"object_seat: {tile!r} is not a tile key like +45-123.")
    return os.path.join(FNAMES.patch_dir(*parsed),
                        PLAN_FILENAME.format(icao=str(icao).upper()))


def _plan_entries(plan: _t.Mapping[str, _t.Any]) -> dict[int, tuple[str, dict]]:
    """``{row: (kind, record)}`` over a plan's ``to_dict`` sections, each row
    under the strongest section that names it (:data:`_SECTIONS`)."""
    out: dict[int, tuple[str, dict]] = {}
    for section, kind in reversed(_SECTIONS):
        for rec in plan.get(section) or ():
            row = ((rec.get("placement") or {}).get("index") if section == "splits"
                   else rec.get("index"))
            if row is not None:
                out[int(row)] = (kind, rec)
    return out


def _entries(path: str) -> dict[int, tuple[str, dict]] | None:
    """The plan at ``path``, indexed; ``None`` when there is none."""
    stamp = _stamp(path)
    if stamp is None:
        return None
    with _LOCK:
        hit = _PLANS.get(path)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    with open(path, encoding="utf-8") as fh:
        entries = _plan_entries(json.load(fh))
    with _LOCK:
        _PLANS.clear()                  # one airport is open at a time
        _PLANS[path] = (stamp, entries)
    return entries


def _m(z: float) -> str:
    return f"{z:,.1f} m"


def _seat(kind: str, rec: _t.Mapping, agl_m: float) -> tuple[list[float], bool, float, str]:
    """``(zeros from the plan, stands on the ground, lift over it, why)``."""
    from auto_patch_v2.airport.placement_coherence import plan_body_zero
    if kind == "split":
        bodies = list(rec.get("bodies") or ())
        zeros = [z for z in (plan_body_zero(b) for b in bodies) if z is not None]
        return zeros, False, 0.0, (f"Cut into {len(bodies)} bodies by the placement plan"
                                   if len(bodies) > 1 else "Re-seated by the placement plan")
    if kind == "row":
        z = float(rec["elevation"])
        return [z], False, 0.0, f"Seated on its DSF row at {_m(z)} MSL"
    written = kind == "rider" and rec.get("seat_why") == "msl_written" \
        and rec.get("seat_z") is not None
    if written:
        z = float(rec["seat_z"])
        return [z], False, 0.0, f"Rides its gate's unit at {_m(z)} MSL"
    if kind == "converted" or (kind == "rider" and rec.get("seat_why") == "on_ground"):
        return [], True, 0.0, "Placed on the ground by the placement plan"
    lift = f", {_m(agl_m)} above the ground" if agl_m else ", on the ground"
    return [], True, agl_m, "Kept as the pack places it" + lift


def _needs_ground(entry: tuple[str, dict] | None) -> bool:
    """Whether the seat of ``entry`` is the drape at its anchor."""
    kind, rec = entry if entry is not None else ("authored", {})
    return _seat(kind, rec, 0.0)[1]


def _seat_record(entry: tuple[str, dict] | None, *, agl_m: float, ground_m: float | None,
                y_min: float | None, y_max: float | None, have_plan: bool = True,
                pending: bool = False) -> dict:
    """The inspector record for one placement (pure): ``entry`` is its
    :func:`_plan_entries` value (``None``: the plan does not name it),
    ``ground_m`` the drape at its anchor (``pending``: its source is still
    loading), ``y_min`` / ``y_max`` its authored height range."""
    kind, rec = entry if entry is not None else ("authored", {})
    zeros, on_ground, lift, why = _seat(kind, rec, agl_m)
    if not have_plan:
        why = "No placement plan from the last build: " + why[0].lower() + why[1:]
    if on_ground and ground_m is not None:
        zeros = [ground_m + lift]
    out: dict[str, _t.Any] = {
        "seat": kind, "bodies": len(rec.get("bodies") or ()) if kind == "split" else 0,
        "pending": bool(pending),
        "zero_m": min(zeros) if zeros else None, "zero_max_m": max(zeros) if zeros else None,
        "ground_m": ground_m, "height_m": None, "bottom_m": None, "top_m": None}
    if y_min is not None and y_max is not None and math.isfinite(y_min) and math.isfinite(y_max):
        out["height_m"] = round(y_max - y_min, 3)
        if zeros:
            out["bottom_m"] = round(min(zeros) + y_min, 3)
            out["top_m"] = round(max(zeros) + y_max, 3)
    lines = [] if out["height_m"] is None else [f"Height {_m(out['height_m'])}"]
    if out["top_m"] is not None:
        lines += [f"Top {_m(out['top_m'])} MSL", f"Bottom {_m(out['bottom_m'])} MSL"]
    elif out["pending"]:
        lines.append("Reading the ground under it…")
    elif not zeros:
        lines.append("Its elevation is not known here.")
    if len(zeros) > 1 and max(zeros) - min(zeros) >= 0.05:
        why += f" (seats {_m(min(zeros))} to {_m(max(zeros))} MSL)"
    out["why"] = why
    out["lines"] = lines + [why + "."]
    return out


def object_seat(tile: str, icao: str, index: int, lat: float, lon: float,
                agl_m: float = 0.0, y_min: float | None = None,
                y_max: float | None = None, build_dir: str | None = None) -> dict:
    """ENGINE COMMAND ``object_seat``: the :func:`_seat_record` of the
    placement on DSF row ``index`` at ``(lat, lon)``, plus ``index`` and
    ``plan`` (the plan file's name, or ``None``).  Ask again while
    ``pending``."""
    from .elevation_commands import cursor_elevation
    try:
        row = int(index)
        lat, lon, agl = float(lat), float(lon), float(agl_m or 0.0)
        lo = None if y_min is None else float(y_min)
        hi = None if y_max is None else float(y_max)
    except (TypeError, ValueError):
        raise ValueError("object_seat: index must be a row number and lat, lon, "
                         "agl_m, y_min, y_max numbers.") from None
    path = _plan_path(tile, icao)
    entries = _entries(path)
    entry = None if entries is None else entries.get(row)
    ground, pending = None, False
    if _needs_ground(entry):
        reply = cursor_elevation(lat, lon, build_dir=build_dir)
        ground, pending = reply.get("elevation_m"), bool(reply.get("pending"))
    rec = _seat_record(entry, agl_m=agl, ground_m=ground, y_min=lo, y_max=hi,
                      have_plan=entries is not None, pending=pending)
    rec["index"] = row
    rec["plan"] = os.path.basename(path) if entries is not None else None
    return rec
