"""AN APPROACH-LIGHT SET ON A RUNWAY'S EXTENDED CENTRELINE IS SEATED AT THE
RUNWAY END (owner RULINGS 2026-11-10i, #1977 item 2; narrows owner Q54
of 2026-10-20 for this class).

Owner Q54 keeps an ORIGIN-BUILT ``OBJECT_MSL`` set — one whose geometry
reaches below its origin (``msl_feet``: "the author built that model
around its origin") — on the on-ground conversion: X-Plane drapes its
origin on the mesh.  An approach-lighting structure built off a runway
end over falling ground (KCRW 23: piers standing in the valley, the light
plane at the runway's height) is such a set, and the drape at its origin
(the valley floor 27 m past the end) buries its light plane metres deep.

So a converted origin-built set whose ORIGIN stands on a runway's
extended centreline BEYOND ITS END, heading along it, is seated by its
ROW with its origin — its light plane — at the SOLVED runway-end
elevation (the design surface at the end point).  The witnesses, each a
reading of the geometry and the runway, none an airport (RULINGS
2026-10-05e):

* ORIGIN-BUILT: some member's static geometry reaches more than ``tol_m``
  below its origin (``msl_feet``'s guard), every member readable;
* ON THE EXTENDED CENTRELINE: the origin lies past the end along the
  runway's axis, at most ``runway_ends.approach_reach_m`` beyond it, and
  within the runway's half width of the axis;
* HEADING ALONG IT: the row's heading agrees with the runway's axis (either
  way) within ``runway_ends.peer_parallel_deg``.

The runway ends ride the graded surface's provenance
(:func:`runway_ends_ll`), so the object stage reads them with the surface.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["CENTRELINE_END", "runway_ends_ll", "on_extended_centreline",
           "centreline_seats"]

#: the ``MslSeat.why`` of :func:`centreline_seats`
CENTRELINE_END = "centreline_end"


def runway_ends_ll(airport: _t.Any) -> list[dict[str, _t.Any]]:
    """The graded surface's ``runway_ends`` key: one record per runway end,
    ``{runway, end, lat, lon, far_lat, far_lon, half_width_m}`` — the end
    point, the runway's other end (the axis) and its half width."""
    out = []
    for rw in getattr(airport, "runways", ()) or ():
        ends = tuple(getattr(rw, "ends", ()) or ())
        if len(ends) != 2:
            continue
        hw = 0.5 * float(getattr(rw, "width_m", 0.0) or 0.0)
        for e, far in ((ends[0], ends[1]), (ends[1], ends[0])):
            out.append({"runway": str(rw.id), "end": str(e.name),
                        "lat": float(e.ll[0]), "lon": float(e.ll[1]),
                        "far_lat": float(far.ll[0]), "far_lon": float(far.ll[1]),
                        "half_width_m": hw})
    return out


def _local(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """``(east, north)`` metres of ``(lat, lon)`` from ``(lat0, lon0)``."""
    from .anchor_rule import _m_per_deg
    ml, mo = _m_per_deg(lat0)
    return (lon - lon0) * mo, (lat - lat0) * ml


def on_extended_centreline(end: _t.Mapping[str, _t.Any], lat: float, lon: float,
                           heading_deg: float, reach_m: float,
                           heading_tol_deg: float) -> "float | None":
    """How far beyond ``end`` the point stands on its runway's extended
    centreline, heading along it; ``None`` where it does not."""
    ax, ay = _local(end["lat"], end["lon"], end["far_lat"], end["far_lon"])
    d = math.hypot(ax, ay)
    if d <= 0.0:
        return None
    ux, uy = -ax / d, -ay / d                      # outward, away from the runway
    px, py = _local(end["lat"], end["lon"], lat, lon)
    s, t = px * ux + py * uy, px * uy - py * ux
    if not (0.0 < s <= reach_m) or abs(t) > float(end["half_width_m"]):
        return None
    axis = math.degrees(math.atan2(ux, uy))       # compass bearing
    off = abs((float(heading_deg) - axis + 90.0) % 180.0 - 90.0)
    return s if off <= heading_tol_deg else None


def centreline_seats(dump: _t.Any, conversions: _t.Sequence[_t.Any],
                     surface: _t.Callable[[float, float], "float | None"],
                     pack_root: str, runway_ends: _t.Sequence[_t.Mapping], *,
                     reach_m: float, heading_tol_deg: float, tol_m: float,
                     counts: "dict[str, int] | None" = None) -> tuple[tuple, tuple]:
    """``(msl seats, conversions left)``: each converted origin-built
    ``OBJECT_MSL`` set on a runway's extended centreline (the module
    docstring) seated with its origin at that runway end's design-surface
    elevation; every other conversion returned as it was."""
    from ..model.placement import KIND_MSL, MslSeat
    from .msl_feet import _feet_reader, origin_of_row
    c = counts if counts is not None else {}
    rows = list(getattr(dump, "placements", ()) or ())
    if not runway_ends or reach_m <= 0.0:
        return (), tuple(conversions)
    sets: dict[tuple, list] = {}
    for cv in conversions:
        if cv.kind_before == KIND_MSL and 0 <= cv.index < len(rows):
            sets.setdefault(origin_of_row(rows[cv.index]), []).append(cv)
    feet = _feet_reader(pack_root, tol_m)
    seats: list = []
    for members in sets.values():
        f = [feet(m.resource) for m in members]
        if any(x is None for x in f) or min(float(x[:, 1].min()) for x in f) >= -tol_m:
            continue                                # not origin-built: msl_feet's
        p = rows[members[0].index]
        hits = [(s, e) for e in runway_ends
                for s in (on_extended_centreline(e, float(p.lat), float(p.lon),
                                                 float(p.heading_deg), reach_m,
                                                 heading_tol_deg),) if s is not None]
        if not hits:
            continue
        end = min(hits, key=lambda h: h[0])[1]
        z = surface(float(end["lat"]), float(end["lon"]))
        if z is None:
            c["centreline_end_off_sheet"] = c.get("centreline_end_off_sheet", 0) + 1
            continue
        c["centreline_end_sets"] = c.get("centreline_end_sets", 0) + 1
        seats += [MslSeat(m.index, m.resource, float(rows[m.index].lon),
                          float(rows[m.index].lat), float(rows[m.index].heading_deg),
                          float(z), CENTRELINE_END) for m in members]
    moved = {s.index for s in seats}
    c["centreline_end_seated"] = c.get("centreline_end_seated", 0) + len(seats)
    return tuple(seats), tuple(cv for cv in conversions if cv.index not in moved)
