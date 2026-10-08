"""THE FRONTAGE WARNING — the fixed words a released frontage weld is said in.

Spec §56 (3), owner RULINGS 2026-10-07c (6): "pads still have to be seated
so aprons can weld to them along their frontage without violating grade
caps.  If you find a case that can't be solved, warn and explain."

The seat is the stage-1 solve (the free datum, the hard welds); a weld the
elastic LP releases IS the case that cannot be solved, and it is read AFTER
the solve in the block's record (``constraints.platform._datum_record``).
This module turns that record into the user's line and nothing else: no
geometry, no law but the bar.  A block whose worst released contact stands
off its datum by more than ``[building_pad] frontage_hold_margin_m`` is
WARNED; under the bar the sidecar and the census carry the step and nothing
is said.

THE COPY IS FIXED (the owner reads it; the twin asserts it byte for byte):
every slot is a field of the record, and a record that lacks a slot the
copy needs gives NO sentence about it — the record never says what it did
not measure."""
from __future__ import annotations

import typing as _t

__all__ = ["COPY", "WHY_NO_LEVEL", "WHY_NO_BLEND", "ONE_LEVEL", "frontage_warning",
           "stamp_warning", "warnings_of"]

#: The line, one per warned block.
COPY = ("Building pad {unit} at {lat:.5f}, {lon:.5f} ({area:,.0f} m²): the apron "
        "cannot be welded to it along its whole frontage within the grade caps. "
        "The pad is seated flat at {datum:.2f} m, the apron's own level there; "
        "{n_rel} of {n_contacts} frontage contacts are released, the worst by "
        "{de:.2f} m at {wlat:.5f}, {wlon:.5f}. Why: {why}. The apron keeps its "
        "caps; the pad's rim steps there; the building is not moved.")
#: ``{why}`` where the contacts' reach bands share no level
#: (``reach_isect_empty``).
WHY_NO_LEVEL = ("no single level is within the apron's reach of every frontage "
                "contact from the fixed taxiways and runways: the lowest contact "
                "can be reached only up to {r_hi:.2f} m and the highest only down "
                "to {r_lo:.2f} m")
#: ``{why}`` where they do.
WHY_NO_BLEND = ("a common level within reach exists ({r_lo:.2f}–{r_hi:.2f} m), "
                "but the apron around those contacts cannot blend to it under "
                "its caps and the fixed airside")
#: Appended to ``{why}`` for a one-block unit the record says needs a split.
ONE_LEVEL = "; the unit reads one level, so it is not split into blocks"

#: The record's fields the line reads, in the copy's order.
SLOTS = ("ref", "centroid_ll", "pad_m2", "datum", "released", "welded",
         "released_max_m", "released_ll", "reach_isect")


def missing_slots(rec: _t.Mapping[str, _t.Any]) -> tuple[str, ...]:
    """The slots of the copy ``rec`` does not carry (``reach_isect`` counts
    as carried only with BOTH its bounds)."""
    out = [k for k in SLOTS if rec.get(k) in (None, [], ())]
    rl = rec.get("reach_isect")
    if rl is not None and (len(rl) != 2 or rl[0] is None or rl[1] is None):
        out.append("reach_isect")
    return tuple(dict.fromkeys(out))


def frontage_warning(rec: _t.Mapping[str, _t.Any], margin_m: float) -> str | None:
    """The line for the block record ``rec`` (``platforms[]``), or ``None``
    where nothing is said: no released weld, the worst release within
    ``margin_m``, or a record with a slot missing (:func:`missing_slots` —
    the caller reports it, ``warning_unsaid``)."""
    if not int(rec.get("released") or 0):
        return None
    de = float(rec.get("released_max_m") or 0.0)
    if de <= float(margin_m) or missing_slots(rec):
        return None
    r_lo, r_hi = (float(x) for x in rec["reach_isect"])
    why = (WHY_NO_LEVEL if rec.get("reach_isect_empty") else WHY_NO_BLEND
           ).format(r_lo=r_lo, r_hi=r_hi)
    if int(rec.get("blocks") or 1) == 1 and rec.get("needs_split"):
        why += ONE_LEVEL
    lat, lon = rec["centroid_ll"][:2]
    wlat, wlon = rec["released_ll"][0][:2]
    n_rel = int(rec["released"])
    return COPY.format(unit=rec["ref"], lat=float(lat), lon=float(lon),
                       area=float(rec["pad_m2"]), datum=float(rec["datum"]),
                       n_rel=n_rel, n_contacts=n_rel + int(rec["welded"]),
                       de=de, wlat=float(wlat), wlon=float(wlon), why=why)


def stamp_warning(rec: dict, margin_m: float) -> dict:
    """``rec`` with ``warned`` / ``warning`` (spec §56 (3)) — and, for a
    block over the bar whose record lacks a slot, ``warning_unsaid`` naming
    the slots (never a silent class)."""
    text = frontage_warning(rec, margin_m)
    rec["warned"] = text is not None
    rec["warning"] = text
    if (text is None and int(rec.get("released") or 0)
            and float(rec.get("released_max_m") or 0.0) > float(margin_m)):
        rec["warning_unsaid"] = list(missing_slots(rec))
    return rec


def warnings_of(platforms: _t.Iterable[_t.Mapping[str, _t.Any]]) -> list[str]:
    """The lines of the warned blocks of a ``platforms`` key, in its order."""
    return [str(r["warning"]) for r in platforms or ()
            if isinstance(r, _t.Mapping) and r.get("warned") and r.get("warning")]
