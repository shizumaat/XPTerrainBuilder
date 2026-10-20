"""AIRCRAFT REACHABILITY DECIDES THE SIDE (owner RULINGS 2026-10-19ag,
issue #808; refines §27 (2026-09-12c) within one author polygon).

The owner: "the strongest indication is whether aircraft have enough
room to maneuver around a building, if the pavement on either side is too
narrow, than any amount of pavement on the other side is unreachable by
aircraft and thus must be groundside."  RULED: pavement aircraft can reach
only through a passage too narrow to manoeuvre is groundside, however much
of it lies beyond; a building with taxiable pavement around it divides
nothing.

THE READING, pure geometry over the scored faces (``roles.classify``'s
``final``), run ONCE after §27's airside-edge flip:

* the AIRCRAFT an apron face is judged for is the one the taxiway serving
  it is built for: the code letter of the NEAREST taxi-family face, and
  its pavement width (``rulesets.<authority>.taxi.width_m`` through
  ``law.tables.taxi_half_width_m``; an unlettered taxiway reads the law's
  default).  No new number: "too narrow" is narrower than that taxiway;
* where it can STAND is the airside pavement, closed by the identity weld
  (``emit.identity.weld_spacing_m``: a seam between two pages is no kerb)
  and eroded by that half-width — a building, a hole or a pavement edge
  closer than it leaves no room.  Each connected piece of that room is
  REACHABLE when the area it sweeps (the piece dilated back by the
  half-width) meets a taxi-family face or a runway: an aircraft taxis in;
* an APRON face with room, none of it reachable, is groundside
  (``open_default.unclassified_groundside_role`` names the role — the one
  derivation site of that verdict) — when it is joined to the taxi
  network by pavement at all (a detached island is the touch-chain
  ladder's to judge) and it is a LOT: at least half of it
  is room for the law's default taxiway (a road network one page draws as
  apron, wide only at a junction or two, is passages).  A face with no
  room at all (a strip
  narrower than the aircraft) keeps its role: it is a passage or a fringe,
  never "beyond" anything.  A face carrying an apt.dat startup is never
  demoted: a stand IS evidence aircraft get there.

OSM parking areas and fences are confirmation only (19ag) and are not read.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import role_side, taxi_half_width_m
from .rules import Rules

__all__ = ["unreachable_aprons"]

#: the faces an aircraft taxis on to reach an apron (``roles.TAXI_FAMILY``;
#: the runways are handed in beside them)
_TAXI_ROLES = frozenset(("primary_parallel", "secondary_parallel", "stub",
                         "cross_connector", "junction"))


class _Room:
    """The room an aircraft of one half-width has, and which of it is
    reachable from the taxi network (module docstring)."""

    def __init__(self, air, taxi, r: float, weld: float):
        room = air.buffer(weld).buffer(-(r + weld))
        self.r = float(r)
        self.pieces = [p for p in getattr(room, "geoms", [room]) if not p.is_empty]
        self.tree = STRtree(self.pieces) if self.pieces else None
        self.reach = {i for i, p in enumerate(self.pieces)
                      if p.buffer(r).intersects(taxi)}

    def mine(self, face) -> list[int]:
        """The room pieces standing in ``face``."""
        if self.tree is None:
            return []
        return [int(j) for j in self.tree.query(face, predicate="intersects")
                if self.pieces[int(j)].intersection(face).area > 0.0]

    def verdict(self, face) -> str:
        """``"none"`` (no room in the face), ``"reach"`` or ``"beyond"``."""
        mine = self.mine(face)
        if not mine:
            return "none"
        return "reach" if any(j in self.reach for j in mine) else "beyond"

    def swept(self, face) -> float:
        """The share of ``face`` the room in it sweeps."""
        mine = self.mine(face)
        if not mine or face.area <= 0.0:
            return 0.0
        return unary_union([self.pieces[j].buffer(self.r) for j in mine]
                           ).intersection(face).area / face.area


def unreachable_aprons(final: list[list], runways, law: Law, rules: Rules,
                       startups: _t.Sequence[tuple[float, float]] = ()
                       ) -> dict[str, float]:
    """Demote every apron face of ``final`` aircraft cannot reach (module
    docstring), in place.  ``runways`` are the runway polygons, ``startups``
    the apt.dat 1300 positions in the frame.  Returns the report counters."""
    from .open_default import unclassified_groundside_role
    out = {"reach_demoted": 0, "reach_demoted_m2": 0.0, "reach_kept_passage": 0}
    aprons = [f for f in final if f[0] == "apron"]
    taxis = [f for f in final if f[0] in _TAXI_ROLES]
    if not aprons or not (taxis or runways):
        return out
    air = unary_union([f[2] for f in final if role_side(law, f[0]) == "airside"])
    taxi = unary_union([f[2] for f in taxis] + list(runways))
    weld = float(law.tables.emit.identity.weld_spacing_m)
    ttree = STRtree([f[2] for f in taxis]) if taxis else None
    stands = [Point(xy) for xy in startups]
    stree = STRtree(stands) if stands else None
    # only pavement JOINED to the taxi network can lie beyond a passage: a
    # detached island is the touch-chain ladder's (``roles.classify``)
    closed = air.buffer(weld)
    joined = unary_union([g for g in getattr(closed, "geoms", [closed])
                          if g.intersects(taxi)])
    rooms: dict[float, _Room] = {}
    r0 = taxi_half_width_m(law, None)
    if not r0 or r0 <= 0.0:
        return out
    lot_room = rooms[float(r0)] = _Room(air, taxi, float(r0), weld)
    for f in aprons:
        face = f[2]
        if not face.intersects(joined):
            continue
        if stree is not None and len(stree.query(face, predicate="contains")):
            continue
        letter = (taxis[int(ttree.query_nearest(face)[0])][3]
                  if ttree is not None else None)
        r = taxi_half_width_m(law, letter)
        if not r or r <= 0.0:
            continue
        room = rooms.get(float(r))
        if room is None:
            room = rooms[float(r)] = _Room(air, taxi, float(r), weld)
        if room.verdict(face) != "beyond":
            continue
        # A LOT, NOT A ROAD NETWORK: most of the face must be wide pavement
        # for the law's default taxiway (``taxi_half_width_m(law, None)``) —
        # HECA ``dsf:objpav1``'s perimeter roads, one page drawn as apron,
        # have 16-58 m2 of room at their junctions and are passages
        if lot_room.swept(face) * 2.0 < 1.0:
            out["reach_kept_passage"] += 1
            continue
        role, evid = unclassified_groundside_role(face, rules, road_reached=False)
        f[0] = role
        f[4] = {**dict(f[4]), **evid, "unreachable_by_aircraft_half_width_m": float(r),
                "serving_letter": str(letter or "-")}
        out["reach_demoted"] += 1
        out["reach_demoted_m2"] += float(face.area)
    return out
