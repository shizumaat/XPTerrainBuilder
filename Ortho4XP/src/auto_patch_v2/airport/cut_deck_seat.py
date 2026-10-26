"""A PACK HARD DECK OVER THE PACK'S OWN CUT SITS FLUSH WITH THE SOLVED
SURFACE IT CARRIES (owner RULINGS 2026-10-26d, Q142 "b"; #1331, the #1298 /
#1343 family).

A pack that states its own tunnel — a shell or a wall object the planar map
reads as an OBJECT cut (``Tunnel.source == "object"``) — keeps that cut
(19p, 19e (3)).  The pack's HARD DECK over it (an ``ATTR_hard_deck`` slab:
the taxiway or the road the pack carries across the trench) is seated so
its top meets the SOLVED surface where that taxiway or road drives onto it,
at its two END LINES — the same reading class A makes for a whole bridge
frame (``airside_deck_seat``, 10-22n) — and never stays at the pack's own
shared zero.  Measured LGAV (FlyTampa): ``Trench_00``'s deck piece over the
``Trench_02`` cut stood 2.2 m under the taxiway, because its frame is a
stack of nine trench objects on one anchor 1.3 km away and class A only
reads a frame that IS one bridge.

THE WITNESS IS THE CUT, never a name: a body of a FLAG deck member whose
slab's plan hull stands at least ``[deck] on_fraction`` over the footprint
of a pack object cut (``authored_seats`` records carry each cut's ring,
:data:`CUT_RING`; ``pipeline/rebake_inputs`` stamps them).  A deck over an
OSM cut (KBNA's taxiway-L bridge in its terminal's frame, 22n (2)) has no
such ring and is left as it was.  Only the deck BODY moves: the shell keeps
the cut it was read for (the ruling's "keep the pack's trench cut").
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

from ..model.frame import m_per_deg_exact as _mpd
from ..model.planar import ROAD_ROLES
from . import airside_deck_seat as _ads
from .placement_file import authored_offset, named_body

__all__ = ["CUT_RING", "cut_rings", "carries_airside", "carries_road", "end_ground",
           "seat_cut_decks"]

#: The ``authored_seats`` record key carrying a pack object cut's
#: footprint ring as ``[[lat, lon], ...]``.
CUT_RING = "cut_ring"


def cut_rings(records: _t.Iterable[_t.Mapping[str, _t.Any]]
              ) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Every distinct pack-cut ring the seat records carry."""
    out: list[tuple[tuple[float, float], ...]] = []
    seen: set = set()
    for r in records or ():
        ring = r.get(CUT_RING) if hasattr(r, "get") else None
        if not ring or len(ring) < 3:
            continue
        key = tuple((float(a), float(b)) for a, b in ring)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return tuple(out)


_STRUCTURE: dict[str, bool] = {}


def _structure(role: str) -> bool:
    """Is this a STRUCTURE role (a trench, a ramp — the cut itself, which a
    deck stands over and never carries)?  Memoised per role."""
    if role not in _STRUCTURE:
        from ..law import Law
        from ..law import tables as _T
        try:
            _STRUCTURE[role] = bool(_T.is_structure_role(Law.load(), role))
        except Exception:
            _STRUCTURE[role] = False
    return _STRUCTURE[role]


def carries_airside(role: "str | None") -> bool:
    """AIRSIDE pavement a pack deck carries over its cut (a taxiway bridge)
    — never the cut's own trench, which the law registers airside too."""
    return bool(role) and _ads.airside_role(role) and not _structure(role)


def carries_road(role: "str | None") -> bool:
    """A ROAD a pack deck carries over its cut (a road deck)."""
    return bool(role) and role in ROAD_ROLES


def end_ground(ring: _t.Sequence[tuple[float, float]], surface: _t.Any, step_m: float):
    """The deck's two END LINES on the surface it CARRIES — the airside
    where the taxiway drives onto it, else the road — read one step
    OUTSIDE the edge (the trench is under the edge); ``None`` where
    neither gives two ends (``airside_deck_seat.airside_end_ground``)."""
    return (_ads.airside_end_ground(ring, surface, step_m, carried=carries_airside,
                                    outside=True)
            or _ads.airside_end_ground(ring, surface, step_m, carried=carries_road,
                                       outside=True))


def _poly_m(ring: _t.Sequence[tuple[float, float]], ml: float, mo: float):
    p = Polygon([(lo * mo, la * ml) for la, lo in ring])
    return p if p.is_valid else p.buffer(0)


def _hull(pts: _t.Sequence[tuple[float, float, float]], ml: float, mo: float):
    h = MultiPoint([(lo * mo, la * ml) for la, lo, _y in pts]).convex_hull
    return h if h.geom_type == "Polygon" else None


def _in_box(p: tuple[float, float, float], box, pad: float) -> bool:
    return (box[0] - pad <= p[0] <= box[2] + pad
            and box[1] - pad <= p[1] <= box[3] + pad)


def seat_cut_decks(record: _t.Any, m: _t.Any, origin: "tuple[float, float] | None",
                   surface: _t.Any, cuts: _t.Sequence, step_m: float,
                   on_fraction: float, counts: dict) -> _t.Any:
    """``record`` with every deck body of ``m`` that stands over a pack cut
    seated flush with the surface it carries at its end lines (module doc);
    every other body, and every other member, as it was."""
    if (not cuts or step_m <= 0.0 or str(getattr(m, "deck_kind", "") or "") != "flag"
            or getattr(m, "deck_top_y", None) is None):
        return record
    slab = _ads.slab_points(m, origin)
    if len(slab) < 3:
        return record
    out, moved = [], False
    for b in record.bodies:
        nb = _seat_body(record, m, b, slab, origin, surface, cuts, step_m,
                        on_fraction, counts)
        moved = moved or nb is not b
        out.append(nb)
    return _dc.replace(record, bodies=tuple(out)) if moved else record


def _seat_body(record, m, b, slab, origin, surface, cuts, step_m, on_fraction, counts):
    """One body: its slab's hull over the cut, its end lines on the surface
    it carries, its zero flush there — or the body unchanged."""
    box = getattr(b, "geom_box", None) or getattr(b, "plan_box", None)
    a = b.anchor
    if box is None or a.surface_z is None:
        return b
    lat0 = 0.5 * (box[0] + box[2])
    ml, mo = _mpd(lat0)
    pad = 0.5 / ml
    pts = [p for p in slab if _in_box(p, box, pad)]
    hull = _hull(pts, ml, mo) if len(pts) >= 3 else None
    if hull is None or hull.area < 1.0:
        return b
    cut = unary_union([_poly_m(r, ml, mo) for r in cuts])
    if hull.intersection(cut).area < on_fraction * hull.area:
        return b
    ring = [(y / ml, x / mo) for x, y in list(hull.exterior.coords)[:-1]]
    ends = end_ground(ring, surface, step_m)
    if ends is None:
        counts["cut_deck_no_end_lines"] = counts.get("cut_deck_no_end_lines", 0) + 1
        return b
    (z1, z2), lines = ends
    t1, t2 = _ads.end_tops(m, lines, origin, step_m)
    zero = 0.5 * ((z1 - t1) + (z2 - t2))
    c = hull.centroid
    la, lo = c.y / ml, c.x / mo
    sz = surface(la, lo)
    if sz is None:
        return b
    y0 = float(sz) - zero
    off = authored_offset(la, lo, y0, record.lat, record.lon, record.heading)
    a2 = _dc.replace(a, lat=la, lon=lo, surface_z=float(sz), y_zero=y0, offset=off,
                     datum=True,
                     reason=(f"pack deck over the pack's cut: flush with the solved surface "
                             f"at its end lines {z1:.2f} / {z2:.2f} (deck top y {t1:+.2f} / "
                             f"{t2:+.2f}), zero {zero:.2f} (RULINGS 2026-10-26d; was: "
                             f"{a.reason})"))
    counts["cut_deck_bodies"] = counts.get("cut_deck_bodies", 0) + 1
    return named_body(m, b, anchor=a2, merged_into="")
