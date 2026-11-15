"""A BRIDGE DECK JOINED TO AN AGP FOLLOWER'S FLOOR (#2090; spec
``2090-agp-group-groundside-spec.md`` B1-B3; owner 2026-11-14T20:41Z: "the
nearby bridge connects the elevated access road ... to the garage's second
level, so a road passes under the bridge").

At the pack stage, after a kept deck's predicted seat (``airport/
bridge_stack._kept_one``), each LAND END of the deck is read against the
connector floors (``[agp] connector_floor_m`` or more over the datum) of
every FOLLOWER of a governed AGP group (``model/agp_group.AgpGroup.
followers``) whose tile reaches the end line: the floors under the end
line's stations (``agp_ground._over``, ``[agp] contact_m``).  The floor
nearest in level to the deck's predicted top there JOINS —

    ``D_k = zero_pred(m) + y_k - (seat + top_e)``

— when ``|D| <= [agp] deck_join_reach_m`` and the next floor's ``|D|`` is
at least ``[agp] deck_join_margin_m`` larger.  KDEN west: the garage's
second level (y 3.45) against the predicted 1631.3, D about +2; the next
floor (6.75) D about +5.

No predicted seat, no datum, two ends that join, or a lone / governor
member: no join, listed with the numbers.  Nothing here names a pack, a
resource or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..model.agp_group import AgpGroup, DeckJoin
from .agp_group import members_of

__all__ = ["DeckFloors", "end_joins"]


class DeckFloors:
    """The followers' connector floors, read once per pack stage and only
    for a follower whose tile reaches a deck end (D2)."""

    def __init__(self, airport, law) -> None:
        self.law = law
        self.agp = law.tables.structures.agp
        self.groups: tuple[AgpGroup, ...] = tuple(
            g for g in getattr(airport, "agp_groups", ()) or () if g.governor is not None)
        self.to_xy, self.to_ll = airport.frame.transformers()
        self._members: dict[str, _t.Any] | None = None
        self._airport = airport
        self._floors: dict[str, np.ndarray] = {}
        self._boxes: dict[str, tuple | None] = {}
        self._memo: dict = {}
        lat0, lon0 = self.to_ll(0.0, 0.0)
        self.lat0, self.lon0 = float(lat0), float(lon0)

    def _member(self, row: str):
        if self._members is None:
            self._members = {m.row: m for m in members_of(self._airport)}
        return self._members.get(row)

    def _en(self, xy) -> tuple[float, float]:
        """Frame ``xy`` in the floors' local east / north metres."""
        from .anchor_rule import _m_per_deg
        lat, lon = self.to_ll(*xy)
        ml, mo = _m_per_deg(self.lat0)
        return ((lon - self.lon0) * mo, (lat - self.lat0) * ml)

    def _box(self, row: str) -> "tuple | None":
        if row not in self._boxes:
            from .anchor_rule import _m_per_deg
            from .riders import agp_footprint_xy
            m = self._member(row)
            box = None
            if m is not None and m.agp.deltas:
                ml, mo = _m_per_deg(self.lat0)
                ring = agp_footprint_xy(m.agp.path, ((m.lon - self.lon0) * mo,
                                                     (m.lat - self.lat0) * ml), m.heading_deg)
                if ring:
                    box = (min(p[0] for p in ring), min(p[1] for p in ring),
                           max(p[0] for p in ring), max(p[1] for p in ring))
            self._boxes[row] = box
        return self._boxes[row]

    def floors(self, row: str) -> np.ndarray:
        """``(k, 3, 3)`` connector-floor triangles of follower ``row`` in the
        local frame, ``y`` over its datum."""
        if row not in self._floors:
            from .agp_ground import _connector_floors
            m = self._member(row)
            self._floors[row] = (np.zeros((0, 3, 3)) if m is None else
                                 _connector_floors(m, self.lat0, self.lon0, self._memo,
                                                   self.agp))
        return self._floors[row]

    def near(self, stations) -> list[tuple[AgpGroup, str]]:
        """``[(group, follower row)]`` whose tile reaches the end line (D2)."""
        pts = [self._en(p) for p in stations]
        c = float(self.agp.contact_m)
        out = []
        for g in self.groups:
            for m in g.followers():
                b = self._box(m.row)
                if b is not None and any(b[0] - c <= e <= b[2] + c and b[1] - c <= n <= b[3] + c
                                         for e, n in pts):
                    out.append((g, m.row))
        return out

    def levels_under(self, row: str, stations) -> list[float]:
        """The distinct floor heights (``y``, 0.01 m) of ``row`` under the
        end line's stations."""
        from .agp_ground import _over
        tris = self.floors(row)
        if not tris.shape[0]:
            return []
        pts = np.array([[*self._en(p), 0.0] for p in stations], float)
        got = _over(pts, tris, float(self.agp.contact_m))
        return sorted({round(yf, 2) for _y, yf, _e, _n in got})


def end_joins(floors: "DeckFloors | None", *, stack_id: str, object_id: str,
              ends: _t.Sequence[tuple[str, _t.Sequence, float]], seat_zero: float
              ) -> tuple[list[DeckJoin], list[str]]:
    """``(joins, notes)`` of one kept deck's land ends ``ends`` = ``[(side,
    stations, top)]`` against the followers' floors (module doc).  Two ends
    that join is no join (listed)."""
    if floors is None or not floors.groups:
        return [], []
    agp = floors.agp
    reach, margin = float(agp.deck_join_reach_m), float(agp.deck_join_margin_m)
    out, notes = [], []
    for side, stations, top in ends:
        if not stations:
            continue
        best = None
        for g, row in floors.near(stations):
            zp = g.zero_pred(row)
            if zp is None:
                continue
            # the connector floors only (a ground slab is the plate's, C1)
            ds = sorted((zp + y - (float(seat_zero) + float(top)), y)
                        for y in floors.levels_under(row, stations)
                        if y >= float(agp.connector_floor_m))
            ds.sort(key=lambda t: abs(t[0]))
            if not ds:
                continue
            d, y = ds[0]
            d_next = ds[1][0] if len(ds) > 1 else None
            tag = (f"{object_id} {side} -> {row} floor y {y:.2f}: D {d:+.2f}"
                   + ("" if d_next is None else f", next D {d_next:+.2f}"))
            if abs(d) > reach:
                notes.append(f"{tag} — no join (|D| > deck_join_reach_m {reach:.1f})")
                continue
            if d_next is not None and abs(d_next) < abs(d) + margin:
                notes.append(f"{tag} — no join (the next floor within deck_join_margin_m)")
                continue
            if best is None or abs(d) < abs(best[0]):
                mid = (sum(p[0] for p in stations) / len(stations),
                       sum(p[1] for p in stations) / len(stations))
                lat, lon = floors.to_ll(*mid)
                best = (d, DeckJoin(g.id, stack_id, object_id, side, row, float(y), float(top),
                                    float(d), None if d_next is None else float(d_next),
                                    (float(mid[0]), float(mid[1])),
                                    (round(float(lat), 8), round(float(lon), 8))), tag)
        if best is not None:
            out.append(best[1])
            notes.append(f"{best[2]} — JOINED")
    if len(out) > 1:
        notes.append(f"{object_id}: both ends join a floor — no join, listed")
        return [], notes
    return out, notes


