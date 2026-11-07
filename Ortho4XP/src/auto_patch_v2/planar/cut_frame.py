"""A PACK DECK OVER THE PACK'S OWN CUT FRAMES THAT CUT (#1331 / #1883; owner
ruling 2026-11-05T00:39Z, recorded as spec ``pack cut objects`` §0.5 — "a
structure member that walls a re-seated pack deck RIDES that deck, and its
cut is re-read at the deck's level"; amends RULINGS 2026-08-26 "trench
senior" / 2026-09-09q (1) for that case; with 2026-10-26d Q142 b).

A pack OBJECT cut (``Tunnel.source == "object"``: a shell the planar map
read, ``airport/object_cut``) whose placement shares its frame — one
anchor, one heading (``deck_bridge.co_placed``) — with a FLAG (or signature) hard deck
whose piece stands at least ``[deck] on_fraction`` over the cut's
footprint is that deck's cut.  The object stage seats the deck flush with
what it carries at its two END LINES (``airport/cut_deck_seat``, 26d) and
the cut's walls ride it, so the cut's FLOOR is read at the same frame: the
deck's seated zero plus the shell's floor plate.  The end lines are the
object stage's own reading (``cut_deck_seat.end_ground``: the pavement or
road the deck carries, one step outside its edge), made here on the
classification's roles BEFORE the cuts (the cut's own trench and walls
stand where the deck's ends meet the pavement) and the DEM (:class:`_PlanarSurface`), the deck
tops there as a hard-deck bridge's (``deck_bridge``), and the floor
(``Tunnel.mouth_z``, pinned as every object cut's is) stands at that zero
plus the shell's floor plate.  The object stage re-reads the zero on the
solved surface; the residual is published on the cut's seat record
(``pipeline/rebake_inputs``, ``cut_frame_z``) and the riding walls'
anchor reason.  NOT a solve tie to the carried surface: measured LGAV, a
two-sided tie to the groundside pavement the deck carries dragged that
pavement 10 m into the channel beside the cut.  MEASURED LGAV (FlyTampa): the
``Trench_02`` shell's floor 73.74 = the stack's zero 77.72 − 3.98 under a
deck seated at 80.02 — walls and floor 2.3 m under the deck.

A deck over an OSM cut is ``planar/deck_bridge``'s (30a); nothing here
names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import Polygon

from ..airport.cut_deck_seat import end_ground
from ..airport.tunnel_objects import _seat
from .deck_bridge import CellRoles, _plate, _top_at, co_placed

__all__ = ["frame_cuts", "FRAME_NOTE"]

#: the ``Tunnel.notes`` line this reading writes opens with
FRAME_NOTE = "cut framed by the pack deck over it"


class _PlanarSurface:
    """The object stage's ``Surface`` read at planar time: the
    classification's roles (``deck_bridge.CellRoles``) and the DEM — the
    end lines ``cut_deck_seat.end_ground`` reads on the solved surface,
    read here before the solve."""

    def __init__(self, classification, airport) -> None:
        self.roles = CellRoles(classification, airport)
        self._dem = airport.dem
        self._to_xy = airport.frame.transformers()[0]

    def __call__(self, lat: float, lon: float) -> "float | None":
        z = float(self._dem.z(*self._to_xy(lon, lat)))
        return None if math.isnan(z) else z


def _piece_over(decks, footprint: Polygon, on_fraction: float):
    """``(deck placement, piece)``: the deck piece standing the most over
    ``footprint`` — at least ``on_fraction`` of its own area — each deck
    placement's ``hard_deck`` read on its own (a liner's cover over the
    whole channel is no piece over one cut), else ``None``."""
    best = None
    for d in decks:
        for p in getattr(d.hard_deck, "geoms", [d.hard_deck]):
            if p.geom_type != "Polygon" or p.area < 1.0:
                continue
            f = p.intersection(footprint).area / p.area
            if f >= on_fraction and (best is None or f > best[0]):
                best = (f, d, p)
    return None if best is None else best[1:]


def frame_cuts(tunnels: _t.Sequence, objects, cache, classification, airport, law,
               covers: _t.Iterable[tuple[str, str]] = ()) -> tuple[list, list[str]]:
    """``(tunnels, notes)``: every object cut a co-placed flag deck stands
    over carries that deck's frame (module doc); every other tunnel as it
    was.  ``covers`` (``TunnelObjectStats.shell_covers``) names each cut's
    own COVER — its roof, the signature-B pair (VHHH, EGLL), never a deck
    that frames it."""
    own_cover = dict(covers)
    if not objects or cache is None or classification is None:
        return list(tunnels), []
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    on = float(law.tables.structures.deck.on_fraction)
    msl = {o.id: o.y_offset_m for o in getattr(airport, "dsf_objects", ())
           if o.kind == "OBJECT_MSL"}
    by_id = {str(o.id): o for o in objects}
    decks = [o for o in objects if str(getattr(o, "deck_kind", "") or "") in ("flag", "signature")
             and getattr(o, "hard_deck", None) is not None and not o.hard_deck.is_empty]
    surf = None
    to_xy, to_ll = airport.frame.transformers()
    out, notes = [], []
    for tn in tunnels:
        P = by_id.get(str(tn.objects[0])) if getattr(tn, "source", "") == "object" \
            and tn.objects else None
        # the cut's DECK is another member of its frame: never its own plate
        mine = [d for d in decks if P is not None and str(d.id) not in tn.objects
                and str(d.id) != own_cover.get(tn.id) and co_placed(d, P, tol)]
        fp = Polygon(tn.footprint) if len(getattr(tn, "footprint", ()) or ()) >= 3 else None
        got = None if not mine or fp is None else _piece_over(
            mine, fp if fp.is_valid else fp.buffer(0.0), on)
        # #1903: no other deck frames it, but its OWN cover is a hard deck
        # the object stage seats flush at its end lines (RULINGS 2026-10-22n;
        # EGLL ``3.obj`` over ``3a.obj``): the floor rides THAT zero — a
        # floor read under the anchor's uncut ground (25.36) left the walls
        # 2.1 m under the cut once the cover sat on its end lines (23.22)
        own = [d for d in decks if P is not None and str(d.id) == own_cover.get(tn.id)
               and co_placed(d, P, tol)]
        if got is None and own and fp is not None:
            got = _piece_over(own, fp if fp.is_valid else fp.buffer(0.0), on)
            mine = own if got is not None else mine
        own_frame = got is not None and str(got[0].id) == own_cover.get(tn.id)
        if got is None:
            if mine:
                notes.append(f"{tn.id}: no piece of its frame's {len(mine)} pack deck(s) stands "
                             f"{on:.0%} over it — the cut keeps the pack's zero")
            out.append(tn)
            continue
        d, piece = got
        surf = surf or _PlanarSurface(classification, airport)
        ring_ll = [to_ll(x, y) for x, y in piece.exterior.coords[:-1]]
        ends = end_ground(ring_ll, surf, step)
        if ends is None:
            notes.append(f"{tn.id}: the pack deck {d.id} over it carries no pavement onto "
                         f"both its ends — the cut keeps the pack's zero")
            out.append(tn)
            continue
        (g1, g2), (l1, l2) = ends
        sa, sb = (tuple(to_xy(lo, la) for la, lo, _z in e) for e in (l1, l2))
        slab = _plate(cache, [d])
        top = max(y for _x, _y, y in slab)
        reach = max(2.0 * step, 3.0)
        ta, tb = _top_at(slab, sa, reach, top), _top_at(slab, sb, reach, top)
        # one frame, one zero: the shell's floor plate under the deck's zero
        floor_y = float(tn.mouth_z) - _seat(P, msl) + (_seat(P, msl) - _seat(d, msl))
        frame = 0.5 * ((g1 - ta) + (g2 - tb))
        # THE FRAME RAISES A CUT, NEVER SINKS IT under the pack's own floor:
        # the end lines are read on the DEM before the solve, which LGAV's
        # taxiways leave 0.3-1.0 m off (four readings of one deck 77.07 /
        # 77.45 / 76.09 / 76.88 seated); a floor read low strands the riding
        # walls' bottom over it (a gap), one read high only buries it
        # ...save under its OWN cover: the object it seats is the cut's own
        # walls, so the floor is where they end in the frame they are drawn
        z0 = frame + floor_y if own_frame else max(frame + floor_y, float(tn.mouth_z))
        # the object's own floor per station (#1903) rides the same frame
        lift = z0 - float(tn.mouth_z)
        out.append(_dc.replace(
            # (its own cover is seated by the object stage's own end-line
            # rule, 10-22n — no frame zero is laid on it)
            tn, mouth_z=z0, cut_frame=() if own_frame else (str(d.id), frame),
            profile=tuple((s, z + lift) for s, z in (getattr(tn, "profile", ()) or ())),
            notes=(*tn.notes, f"{FRAME_NOTE} {d.id} (owner 2026-11-05 §0.5): floor {z0:.2f} = "
                              f"the deck's zero {frame:.2f} flush at its end lines "
                              f"{g1:.2f} / {g2:.2f} (deck top {ta:+.2f} / {tb:+.2f}) "
                              f"{floor_y:+.2f}, " + (
                                  f"its own cover: the walls' bottom in the frame they are "
                                  f"drawn in, read {tn.mouth_z:.2f}" if own_frame else
                                  f"never under the pack's floor {tn.mouth_z:.2f}"))))
        notes.append(f"{tn.id}: {out[-1].notes[-1]}")
    return out, notes
