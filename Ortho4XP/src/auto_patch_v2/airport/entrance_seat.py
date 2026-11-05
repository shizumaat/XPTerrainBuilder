"""AN ENTRANCE OBJECT'S FACE IS SEATED ON ITS PORTAL'S FLOOR (#1747; owner
RULINGS 2026-11-03e (15) "the ramp grades to the entrance object's bottom;
the houses stay", Q-A 2026-11-05 "the floor at the PORTAL").

The planar map reads an entrance object's face at each mapped bore end
(``trench_objects.mouth_portals``): its top on the ground over it, its
bottom the mouth's floor.  The structure pass publishes that zero with the
end (``Tunnel.portal_seat``; the seat record ``terrain_shaped.ENTRANCE_SEAT``)
and here every BODY of the placement standing within the record's reach
of that end takes it.  A body elsewhere in the object — the houses an
entrance object may carry, the other portal's face — keeps its own seat:
the object is seated face by face, never as one row.  MEASURED LOWS
(``domiki_lows_48.obj``, 1.0.465): the west face's body was seated on the
apron by its bottom (5 m proud of the ground), the floor read 4 m over the
ground at the pack's zero.  Nothing here names a pack or an airport.
"""
from __future__ import annotations

import typing as _t

from ..model.frame import m_per_deg_exact as _mpd
from .terrain_shaped import ENTRANCE_SEAT

__all__ = ["entrance_zeros", "seat_faces", "SEAT_REASON"]

#: the anchor reason a face this reading seated opens with
SEAT_REASON = "entrance face on its portal's floor"


def entrance_zeros(records: _t.Iterable[_t.Mapping[str, _t.Any]]
                   ) -> dict[str, list[tuple[float, float, float, float]]]:
    """Placement id -> ``[(lat, lon, reach m, zero), ...]``, one per bore end
    an entrance face of it stands at."""
    out: dict[str, list[tuple[float, float, float, float]]] = {}
    for r in records or ():
        if not hasattr(r, "get") or r.get("seat") != ENTRANCE_SEAT or not r.get("end"):
            continue
        la, lo = r["end"]
        out.setdefault(str(r.get("id")), []).append(
            (float(la), float(lo), float(r.get("reach_m") or 0.0), float(r["elevation"])))
    return out


def _near(b: _t.Any, la: float, lo: float, reach: float) -> bool:
    box = getattr(b, "geom_box", None) or getattr(b, "plan_box", None)
    if box is None:
        return False
    ml, mo = _mpd(la)
    return (box[0] - reach / ml <= la <= box[2] + reach / ml
            and box[1] - reach / mo <= lo <= box[3] + reach / mo)


def seat_faces(record: _t.Any, m: _t.Any, zeros: _t.Mapping[str, _t.Sequence[tuple]],
               at_zero: _t.Callable) -> _t.Any:
    """``record`` with each body of placement ``m`` that stands within reach
    of an entrance end of it at that end's zero (``at_zero`` is
    ``open_frame_seat.at_zero``); every other body as it was."""
    ends = zeros.get(str(getattr(m, "id", "")), ())
    for la, lo, reach, zero in ends:
        record = at_zero(record, m, zero,
                         lambda b, _a=la, _o=lo, _r=reach: _near(b, _a, _o, _r),
                         f"{SEAT_REASON} at zero {zero:.2f} (#1747, RULINGS 2026-11-03e (15))")
    return record
