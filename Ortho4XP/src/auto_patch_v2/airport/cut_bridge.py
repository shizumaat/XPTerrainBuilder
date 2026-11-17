"""A BRIDGE OVER A PORTAL'S CUT stands its deck flush with the cover at the
end on the cover side (#2120 S; spec ``sim-review/2120-S.md`` §1; owner
RULINGS 2026-10-22c/d/m, 2026-10-27c, 2026-11-16l / 16t, 2026-11-13u (1)).

A pack may span the open cut beyond a portal in a cut (``airport/
cut_portal``) with a deck of its own -- a service road over the motorway
beside the portal's mouth.  Its deck is no flag deck and no mapped bridge
way crosses it, so the deck signature leaves it a ``candidate`` and the
rebake plan promotes it by the portal's cut alone; nothing then reads it
as a bridge, and its frame was seated by its piers' feet on the cut floor.
MEASURED KATL (owner build 1.0.547, Orbx): one frame of 7 bodies, a curved
deck 312 m x 11.8 m authored 19.3-21.9 m over its zero, drawn 10.6 m over
its east abutment and 14.4 m over the cover at its west end.

THE WITNESS.  A FRAME (one anchor spelling, ``deck_signature.family_key``)
is a bridge over a portal's cut when ALL hold:

T1 a plated member (``deck_kind`` candidate or signature, never flag) has
   its plate footprint crossing an open-cut region (``rebake_inputs.
   _portal_cuts``) -- ``deck_signature.promote``'s test; the region's owner
   is the frame's PORTAL;
T2 the frame is a deck and the structure riding it: every member plated,
   or ``deck_riders.objects_ride`` with the kinds ``_rider_surfaces``
   builds -- never a frame with a part off every deck;
T3 its LEAD deck (the largest plate, read on its connected surface where
   one grows) has an end line with stations on the portal's COVER SIDE
   (``cut_portal_seat.cover_side``) and the DEM between its ends stands
   under that level somewhere (it spans the cut).  End-line stations are
   ``rebake_plan.end_line_stations`` kept where they lie on the deck's own
   surface;
T4 less than half the frame's plated plan lies over the airport's paved
   surfaces (``cut_portal._paved``): a deck an aircraft uses is class A's;
T5 no member is already seated by another rule (``taken``).

THE SEAT: the deck top AT the cover-side end (``deck_riders.end_tops``,
any vertex) on the ground at that end's cover-side stations; with two
cover-side ends, the end whose ``ground - top`` is higher (22m), the
ground read on the airport DEM (the solved surface carries no vertex off
the graded airside).  ONE plate ``(top_y, stations, 0.0, CUT_BRIDGE_PLATE)``
for every member, plated or riding (``rebake_inputs._cut_bridge_plates``)
-- one authored zero, and the plate LEADS its §16g unit and its
connected group (``open_frame_seat.LEAD_PLATES``) -- the frame moves as
one at its deck's zero (22c/d).  MEASURED (replay): the
``airside_deck_seat.refused_bridge`` route took the frame zero off the lead
deck's bodies, which the unit pass had already put on the cut floor.

Nothing here names a pack, a resource or an airport; the grid and the step
are the caller's ``structures.toml`` / ``emit`` keys."""
from __future__ import annotations

import dataclasses as _dc
import types as _types
import typing as _t

import numpy as np
import shapely

from .cut_portal_seat import _outline_points, cover_side

__all__ = ["cut_bridges"]

#: the plated deck verdicts the witness reads (a flag deck is class A's)
_PLATED = ("candidate", "signature")


@_dc.dataclass(frozen=True)
class _CutBridge:
    """One admitted frame: its plated members' ids, the deck top put on the
    ground at the cover-side end, those stations (frame xy) and its portal."""

    members: tuple[str, ...]
    plated: tuple[str, ...]
    top_y: float
    stations: tuple
    portal: str
    resource: str = ""


def _is_plated(o) -> bool:
    return getattr(o, "deck_kind", "") in _PLATED and getattr(o, "deck_plate", None) is not None


def _plate(o):
    """The member's plate on its connected surface, else its plane plate."""
    pl = o.deck_plate
    return pl if getattr(pl, "surface", None) is None else pl.surface


def _families(objects) -> dict:
    from .deck_signature import family_key
    fams: dict = {}
    for o in objects:
        if getattr(o, "resolved", None):
            fams.setdefault(family_key(o), []).append(o)
    return fams


def _portal_of(fp, regions, portals):
    """T1: the portal whose open cut ``fp`` crosses (the nearest owner)."""
    owners = {oid for g, ids in regions if g.intersects(fp) for oid in ids}
    near = [p for p in portals if p.object_id in owners]
    return min(near, key=lambda p: p.plan.distance(fp)) if near else None


def _rides(members, cache) -> bool:
    """T2: every member plated, or the frame is a deck and its riders."""
    from .deck_riders import FAMILY_KIND, objects_ride
    plated = [_is_plated(o) for o in members]
    if all(plated):
        return True
    kinds = ["signature" if p else FAMILY_KIND for p in plated]
    return bool(objects_ride(members, kinds, cache))


def _end_stations(pl, to_ll, to_xy, step_m: float, grid_m: float) -> list:
    """Each end line's stations (frame xy) on the deck's own surface: the
    line's ``rebake_plan.end_line_stations`` that lie on it, and its
    outline points (``cut_portal_seat``'s, ``grid_m`` out, every
    ``step_m``) within ``step_m`` of the outline's
    nearest approach to the line -- a curved deck meets its rectangle's
    end side at a corner only (KATL's: one of a 46 m side), its end edge
    slanted off it."""
    from shapely.geometry import LineString

    from .rebake_plan import end_line_stations
    fp = pl.footprint
    on = fp.buffer(float(grid_m))
    rim = _outline_points(fp, grid_m, step_m)
    out = []
    for a, b in pl.ends[:2]:
        ll = end_line_stations([(to_ll(*a), to_ll(*b))], step_m)
        pts = np.array([to_xy(lon, lat) for lat, lon in ll], dtype=float).reshape(-1, 2)
        pts = pts[shapely.contains_xy(on, pts[:, 0], pts[:, 1])]
        d = shapely.distance(shapely.points(rim), LineString([a, b]))
        out.append(np.concatenate([pts, rim[d <= float(d.min()) + float(step_m)]]))
    return out


def _spans(pl, portal, dem, step_m: float) -> bool:
    """T3's span: the DEM between the end midpoints stands under the cut's
    mid level somewhere."""
    (a0, a1), (b0, b1) = pl.ends[0], pl.ends[1]
    p = 0.5 * (np.asarray(a0, dtype=float) + np.asarray(a1, dtype=float))
    q = 0.5 * (np.asarray(b0, dtype=float) + np.asarray(b1, dtype=float))
    n = max(2, int(np.ceil(np.hypot(*(q - p)) / max(float(step_m), 1e-6))))
    pts = p + np.linspace(0.0, 1.0, n + 1)[:, None] * (q - p)
    return not cover_side(portal, dem, pts).all()


def _seat(lead, pl, ends, keeps, dem, to_ll):
    """``(top_y, stations)`` at the cover-side end (22m), or None."""
    from .deck_riders import end_tops
    from .dem import dem_z_many
    deck = _types.SimpleNamespace(authored_path=lead.resolved, heading_deg=lead.heading_deg)
    tops = end_tops(deck, [(to_ll(*a), to_ll(*b)) for a, b in pl.ends[:2]], to_ll(*lead.xy))
    if tops is None:
        return None
    best = None
    for i, (pts, keep) in enumerate(zip(ends, keeps, strict=True)):
        if not keep.any():
            continue
        st = pts[keep]
        z = dem_z_many(dem, st[:, 0], st[:, 1])
        z = z[np.isfinite(z)]
        if not len(z):
            continue
        rise = float(np.median(z)) - float(tops[i])
        if best is None or rise > best[0]:
            best = (rise, float(tops[i]), tuple((float(x), float(y)) for x, y in st))
    return None if best is None else best[1:]


def _witness(members, regions, portals, paved, dem, cache, to_ll, to_xy,
             step_m: float, grid_m: float) -> "_CutBridge | None":
    """The frame ``members`` read by T1-T4 (module doc), or None."""
    from . import frame_entry as _fe
    plated = [o for o in members if _is_plated(o)]
    fp = _fe.union([o.deck_plate.footprint for o in plated], "cut_bridge.plates")
    portal = _portal_of(fp, regions, portals)                          # T1
    if portal is None or not _rides(members, cache):                   # T2
        return None
    lead = max(plated, key=lambda o: float(_plate(o).area_m2))
    pl = _plate(lead)
    if pl.ends is None or len(pl.ends) < 2:
        return None
    ends = _end_stations(pl, to_ll, to_xy, step_m, grid_m)
    keeps = [cover_side(portal, dem, e) for e in ends]
    if not any(k.any() for k in keeps) or not _spans(pl, portal, dem, step_m):  # T3
        return None
    plan = _fe.union([_plate(o).footprint for o in plated], "cut_bridge.plan")
    if (not paved.is_empty and plan.area > 0.0
            and plan.intersection(paved).area >= 0.5 * plan.area):     # T4
        return None
    got = _seat(lead, pl, ends, keeps, dem, to_ll)
    if got is None:
        return None
    return _CutBridge(tuple(o.id for o in members), tuple(o.id for o in plated),
                     got[0], got[1], portal.object_id, str(lead.path))


def cut_bridges(airport, objects, regions, cache, grid_m: float, step_m: float,
                taken: _t.Container[str] = frozenset()) -> tuple[_CutBridge, ...]:
    """Every frame of ``objects`` the witness admits (module doc).
    ``regions`` are ``rebake_inputs._portal_cuts``' ``(polygon, owner
    ids)``; with no portal in a cut, nothing is read."""
    portals = tuple(getattr(airport, "cut_portals", ()) or ())
    regions = [(g, ids) for g, ids in regions if g is not None and not g.is_empty]
    dem = getattr(airport, "dem", None)
    if not portals or not regions or dem is None:
        return ()
    from .cut_portal import _paved
    to_xy, to_ll = airport.frame.transformers()[:2]
    box = shapely.unary_union([g for g, _ids in regions]).envelope
    paved = None
    out = []
    for members in _families(objects).values():
        if any(o.id in taken for o in members):                        # T5
            continue
        if not any(_is_plated(o) and box.intersects(o.deck_plate.footprint)
                   for o in members):
            continue
        paved = _paved(airport) if paved is None else paved
        got = _witness(members, regions, portals, paved, dem, cache, to_ll, to_xy,
                       step_m, grid_m)
        if got is not None:
            out.append(got)
    return tuple(out)
