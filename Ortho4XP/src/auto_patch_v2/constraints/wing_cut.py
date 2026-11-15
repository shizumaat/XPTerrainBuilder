"""THE WING CUT'S ROWS (#2099 R2 / R3; specs ``docs/specs/2099-R2-wing-cut.md``,
``docs/specs/2099-R3.md`` D4 / D5): the ground on the road side of a grouped
mouth's walls stands on their feet, the strip behind them meets their tops
(``model/wing_cut``; the cells: ``planar/wing_cut``).

Every vertex of the cut's own ground (``wing_cut:<mouth>`` faces) and every
other vertex inside its region -- the ground, a trench's rim, and the road:
"the road corridor between the wings follows the same floor" -- is held at the mouth's floor plus the
foot under it, read along the wall line it faces (``model/wing_cut.wing_floor_y``);
every vertex of the strip behind a line (``wing_back:<mouth>`` faces) at the
wall's top there (``wing_top_y``), in the mouth's own seat:

* a HARD DECK (plate-seated): ``z[v] = ½(mean z[A] + mean z[B]) −
  (½(top_A + top_B) − floor_y − foot)`` -- the end lines' seat set of
  ``constraints/edge_floor`` (the deck's zero is the solved surface there
  less its top, the object stage's plate), so the cut moves with the deck
  the wings ride;
* a ROW-SEATED portal: ``z[v] = floor_z + foot``.

Each is a two-sided pair (head ``structures.wing_cut floor``: HARD, a
constraint of the design solve's active set, and ONE-WAY -- ``follows`` the
held vertex, so the deck's seat enters at its solved value: the cut follows
the deck and never pulls the airside; measured, the two-way pair moved the
CYYZ decks 0.07 / 0.14 m).
A vertex an AIRSIDE pavement face or a ramp floor carries is never held
(airside is king; the trench floor is the trench's law).  The DEM pins and
road ramps the held vertices carried are shed by ``edge_deck.
release_governed`` (the pair is the level).  Nothing here names an airport.
"""
from __future__ import annotations

import dataclasses as _dc

from ..law import Law
from ..law.tables import is_value_role, role_side
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from ..model.wing_cut import WingCut, wing_floor_y, wing_top_y
from .edge_floor import _mean_terms, seat_pair

__all__ = ["GEN", "RULING", "wing_cut_rows", "STATS"]

GEN = "wing_cut"
RULING = "structures.wing_cut floor (#2099 R2: a grouped mouth's wings state the floor beside them)"
#: the generator's own statistics (``constraints.run_generator``)
STATS: dict[str, dict[str, int]] = {}


def _structure(law: Law, role: str) -> bool:
    return bool(getattr(law.tables.precedence.roles[role], "structure", False))


def _never_roles(planar: PlanarMap, law: Law) -> set[str]:
    """The roles whose vertex is never held: airside pavement (a value role
    on the airside) and a ramp floor (a value structure role)."""
    return {role for role in {f.role for f in planar.faces.values()}
            if role in law.tables.precedence.roles and is_value_role(law, role)
            and (role_side(law, role) == "airside" or _structure(law, role))}


def _seat(planar: PlanarMap, law: Law, cut: WingCut, near) -> "tuple | None":
    """The deck's seat set ``(terms, top)``: each end line the mean of its
    stations' nearest airside vertices, the two ends weighted one half."""
    if near is None or len(cut.seats) != 2:
        return None
    ends = [_mean_terms([near(x, y) for x, y in st]) for st in cut.seats if st]
    if len(ends) != 2:
        return None
    return _mean_terms([], ((ends[0], 0.5), (ends[1], 0.5))), 0.5 * sum(cut.tops)


def wing_cut_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The module doc's pairs, one per held vertex."""
    stats = STATS.setdefault("wing_cut_rows", {})
    stats.clear()
    cuts = tuple(getattr(planar, "wing_cuts", ()) or ())
    if not cuts:
        return []
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep

    from ..model.platform import stage_air_vertices
    from .geometry import nearest_vertex_fn
    never = _never_roles(planar, law)
    near = nearest_vertex_fn(planar, stage_air_vertices(planar, law)) \
        if any(c.seats for c in cuts) else None
    rows: list[Row] = []
    done: set[int] = set()
    for cut in cuts:
        region = unary_union([Polygon(q).buffer(0.0) for q in cut.region])
        inside = prep(region.buffer(1e-6))
        own = [f for f in planar.faces.values()
               if f.ref == cut.ref or f.ref.startswith(cut.ref + "#")]
        cand = {v for f in own for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
        cand.update(v for v, vx in planar.vertices.items() if inside.contains(Point(vx.xy)))
        # R3 D5: the strip behind a wall line meets the wall's top
        behind = {v for f in planar.faces.values()
                  if f.ref == cut.back_ref or f.ref.startswith(cut.back_ref + "#")
                  for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)} - cand
        seat = _seat(planar, law, cut, near) if cut.seats else None
        if cut.seats and seat is None:
            stats["no_seat"] = stats.get("no_seat", 0) + 1
            continue
        src = Source(GEN, RULING, (cut.mouth, cut.ref))
        held = 0
        for v in sorted((cand | behind) - done):
            if any(planar.faces[fid].role in never for fid in planar.vertices[v].incident_faces):
                continue
            xy = planar.vertices[v].xy
            foot = wing_top_y(cut, xy) if v in behind else wing_floor_y(cut, xy)
            if seat is not None:
                rows.extend(_dc.replace(r, follows=v) for r in
                            seat_pair(v, (seat[0], seat[1] - cut.floor_y - foot), src))
            else:
                z = float(cut.floor_z) + foot
                rows.append(Linear(((v, 1.0),), None, z, src, follows=v))
                rows.append(Linear(((v, -1.0),), None, -z, src, follows=v))
            done.add(v)
            held += 1
        stats["held"] = stats.get("held", 0) + held
    stats["cuts"] = len(cuts)
    return rows
