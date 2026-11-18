"""THE ELEVATED END OF A UNIT'S DECK — the third landing kind, ``end``
(#2129; spec ``docs/specs/2129-deck-ends-spec.md``; owner RULINGS
2026-10-22m (2) "the terrain must grade to the other end", 2026-10-03e,
2026-10-14c (5), 2026-11-14d/e/f).

A deck of a terminal unit (``bridge_family.viaduct_units``, the one 10-03e
relation) is seated at the unit's level.  10-03e grades the ground up to
its LOWEST band (``planar/landing``); a stub or ramp strip of the deck that
ends in the air elsewhere had nothing under it — the owner's floating deck
ends (EDDH).  Here every such END is read off the deck's own geometry:

R2 THE DRIVEN SURFACE ``S``: the plan union of the deck's near-horizontal
   up-faces (``bridge_witness.up_faces``) at any ``y``.
R3 AN END EDGE of ``S``: a straight run of its outline (simplified within
   ``[bridge] deck_flush_m``) no longer than ``2 x free_route_half_width_m``
   whose two neighbours turn back by at least 60 degrees and run at least
   its own length behind it (a ribbon's tip), and which is OPEN (no up-face
   of the frame within ``abutment_sample_step_m`` outward near its level:
   else a JOINT), UNSUPPORTED (no standing wall of the frame under it down
   to the ground: else ``end_on_own_abutment``) and ELEVATED (its top
   ``y_e`` over the deck's lowest ``y`` + ``BAND_M``, and the gap from the
   block's predicted datum to the DEM 1.5 m out over ``[cockpit]
   visual_m``).
R4 THE PATH: a mapped route way (``layer >= 1`` or ``bridge != no``, no
   tunnel) inside ``S`` crossing the edge is CARRIED — a ROUTE end; else a
   STUB end along the edge's outward normal.
R5 THE STATE: ``airport/bridge_end_state.end_state`` unchanged, at the
   block's HIGH zero (``datum_pred`` + ``widest_reach``).

Only shape and state are decided here; ``planar/landing`` mints a GRADED
end's landing (R6), its run-out (R7) and lists every other end (R10).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..model.platform import LANDING_SEP

__all__ = ["DeckEnd", "deck_ends", "end_landings", "end_row", "end_platform", "end_foot",
           "other_roads", "END_KIND"]

XY = tuple[float, float]
#: the landing record's ``kind`` of an end fill
END_KIND = "end"


@_dc.dataclass(frozen=True)
class DeckEnd:
    """One end edge of a unit deck's driven surface (module doc)."""

    deck: str
    block: str
    stations: tuple[XY, XY]
    out: XY
    length_m: float
    y_e: float
    y_low: float
    ground: float = math.nan
    gap: float = math.nan
    kind: str = "stub"                 # "route" | "stub"
    carried: tuple[int, ...] = ()
    state: str = ""
    why: str = ""
    end: _t.Any = None                 # the ``StackEnd`` (R5), None when not read
    finding: str = ""

    @property
    def mid(self) -> XY:
        (ax, ay), (bx, by) = self.stations
        return (0.5 * (ax + bx), 0.5 * (ay + by))


class _Frames:
    """The faces of a deck's frame near an edge (R3 (a)/(b)): each member of
    the placement frame whose parts meet the box, parsed once."""

    def __init__(self, part, to_xy) -> None:
        self.part, self.to_xy = part, to_xy
        self._faces: dict[tuple[int, int], np.ndarray] = {}

    def near(self, frame, box) -> np.ndarray:
        from ..airport.bridge_family import frame_of
        from ..airport.deck_end_witness import member_faces, part_meets
        got = []
        for ui, u in enumerate(self.part.units):
            for mi, m in enumerate(u.members):
                if frame_of(m) != frame or not any(
                        part_meets(q.box, box, self.to_xy) for q in m.parts):
                    continue
                if (ui, mi) not in self._faces:
                    self._faces[(ui, mi)] = member_faces(self.part, ui, mi, self.to_xy)
                if len(self._faces[(ui, mi)]):
                    got.append(self._faces[(ui, mi)])
        return np.concatenate(got) if got else np.zeros((0, 3, 3))


def _shape(e: DeckEnd, f: np.ndarray, up: np.ndarray, frame, frames: _Frames,
           datum: float, law) -> "DeckEnd | None":
    """R3 (a) / (b): ``e`` refused as a JOINT or on its own ABUTMENT, else
    ``None`` (the end stands open and unsupported)."""
    from ..airport.bridge_witness import up_faces
    from ..airport.deck_end_witness import is_joint, on_abutment
    br = law.tables.structures.bridge
    step, nmin = float(br.abutment_sample_step_m), float(br.deck_plate_normal_y_min)
    tol = float(br.deck_flush_m) + float(law.tables.emit.road_contact.ramp_grade) * step
    (a, b) = e.stations
    ff = frames.near(frame, LineString([a, b]).buffer(step + 1.0).bounds)
    fup = up_faces(ff, nmin) if len(ff) else ff
    cand = np.concatenate([x for x in (fup, up) if len(x)])
    if is_joint(cand, a, b, e.out, e.y_e, step, tol):
        return _dc.replace(e, state="joint", why="end_is_joint")
    floor_y = e.ground - datum + float(law.tables.emit.cockpit.visual_m)
    if on_abutment(np.concatenate([x for x in (f, ff) if len(x)]), a, b, floor_y, law):
        return _dc.replace(e, state="held", why="end_on_own_abutment")
    return None


def deck_ends(vias: _t.Mapping[str, tuple], part, to_xy, held: _t.Mapping[str, dict],
              airport, law, counts: dict) -> list[DeckEnd]:
    """Every elevated end edge of every unit deck in ``vias``
    (``bridge_family.viaduct_units``: ``key -> (block, voters, frame,
    print)``) with its state (module doc).  Ends at the 10-03e band or at
    grade are counted, not returned."""
    from ..airport.bridge_end_state import Obstacles, end_state
    from ..airport.bridge_witness import up_faces
    from ..airport.deck_end_witness import (carried_ways, driven_surface, edge_top, end_edges,
                                            offset_finding, xy_faces)
    from ..airport.deck_stack import _end_ground
    from ..model.platform import LANDING_BAND_M, widest_reach
    if not vias:
        return []
    br = law.tables.structures.bridge
    flush, step = float(br.deck_flush_m), float(br.abutment_sample_step_m)
    nmin = float(br.deck_plate_normal_y_min)
    cap = 2.0 * float(br.free_route_half_width_m)
    least = float(law.tables.structures.tunnel.lane_width_m)
    band = float(law.tables.emit.cockpit.visual_m)
    ways = list(getattr(airport, "osm_ways_mapped", None) or getattr(airport, "osm_ways", ()))
    frames = _Frames(part, to_xy)
    obs = None
    stat: dict[str, int] = {}
    found: list[DeckEnd] = []
    for key, (bref, _voters, frame, p) in sorted(vias.items()):
        f = xy_faces(p, to_xy)
        up = up_faces(f, nmin) if len(f) else f
        if not len(up):
            continue
        S = driven_surface(up)
        y_low = float(f[:, :, 2].min())
        hb = held.get(bref) or {}
        datum = hb.get("datum_pred")
        for a, b, out, L in end_edges(S, flush, cap, least):
            y_e = edge_top(up, a, b)
            if not math.isfinite(y_e) or y_e <= y_low + LANDING_BAND_M:
                stat["end_at_landing_band"] = stat.get("end_at_landing_band", 0) + 1
                continue
            e = DeckEnd(deck=key, block=bref, stations=(a, b), out=out, length_m=L,
                        y_e=y_e, y_low=y_low)
            if datum is None:
                found.append(_dc.replace(e, state="listed", why="end_no_datum"))
                continue
            G = _end_ground(airport, (a, b), out, float(br.free_end_ground_out_m))
            e = _dc.replace(e, ground=G, gap=float(datum) + y_e - G)
            if not math.isfinite(G):
                found.append(_dc.replace(e, state="listed", why="end_off_dem"))
                continue
            if e.gap <= band:
                stat["end_at_grade"] = stat.get("end_at_grade", 0) + 1
                continue
            refused = _shape(e, f, up, frame, frames, float(datum), law)
            if refused is not None:
                found.append(refused)
                continue
            carried = carried_ways(ways, S, a, b)
            obs = obs or Obstacles(airport, (), None, law, {})
            st = end_state(oid=key, side="end", stations=(a, b), top=y_e, out=out,
                           ground=G, zero=float(datum) + widest_reach(hb), carried=carried,
                           stub=not carried, own=(), obs=obs, law=law)
            find = "" if carried else offset_finding(ways, e.mid, out, L, max(st.run, step))
            found.append(_dc.replace(e, kind="route" if carried else "stub",
                                     carried=carried, state=st.state, why=st.why,
                                     end=st, finding=find))
    for k, v in stat.items():
        counts[k] = counts.get(k, 0) + v
    return found


def end_platform(e: DeckEnd, step: float) -> Polygon:
    """R6: the end edge swept one ``step`` outward (A3's slab)."""
    (ax, ay), (bx, by) = e.stations
    ox, oy = e.out[0] * step, e.out[1] * step
    return Polygon([(ax, ay), (bx, by), (bx + ox, by + oy), (ax + ox, ay + oy)])


class _Foot(_t.NamedTuple):
    """A ramp-foot-shaped record (``airport/ramp_feet.RampFoot``'s fields
    ``planar/landing_runout`` reads) for an end's run-out (R7)."""

    lip: XY
    direction: XY
    width_m: float
    path: tuple[XY, ...] = ()


def end_foot(e: DeckEnd, step: float) -> _Foot:
    """R7: the foot of an end's run-out — at the platform's outer edge, the
    end's width, outward; a ROUTE end's path beyond it."""
    mx, my = e.mid
    lip = (mx + e.out[0] * step, my + e.out[1] * step)
    path: tuple[XY, ...] = ()
    if e.kind == "route" and e.end is not None and len(e.end.path) > 1:
        line = LineString(e.end.path)
        s0 = line.project(Point(lip))
        from shapely.ops import substring
        rest = substring(line, s0, line.length)
        if rest.length > 0.0:
            path = tuple((float(x), float(y)) for x, y in rest.coords)
    return _Foot(lip=lip, direction=e.out, width_m=e.length_m, path=path)


def end_row(e: DeckEnd, to_ll) -> dict[str, _t.Any]:
    """R10: one end's published row — its stations (lat, lon), ``y_e``,
    ``G_e``, gap, state / why, path kind and run."""
    st = e.end
    return {"deck": e.deck, "stations": [list(map(lambda v: round(v, 7), to_ll(*p)))
                                         for p in e.stations],
            "length_m": round(e.length_m, 2), "y_e": round(e.y_e, 3),
            "ground": None if not math.isfinite(e.ground) else round(e.ground, 3),
            "gap": None if not math.isfinite(e.gap) else round(e.gap, 3),
            "state": e.state, "why": e.why, "path": e.kind, "carried": list(e.carried),
            "run_m": round(float(st.run), 1) if st is not None else None,
            **({"finding": e.finding} if e.finding else {})}


def other_roads(airport, law, e: DeckEnd):
    """Q2 (a) (the spec default): the ribbons of every at-grade mapped road
    but the end's own carried way (``airport/road_ways.road_ways``, each at
    ``planar/terrain_edge.road_half_width_m``) — ground an end's platform,
    run-out and banks never take: that road keeps its ground."""
    from ..airport.road_ways import road_ways
    from .terrain_edge import road_half_width_m
    own = {int(w) for w in e.carried}
    return unary_union([ln.buffer(road_half_width_m(law, w.tags or {}), cap_style=2)
                        for w, ln in road_ways(getattr(airport, "osm_ways", ()))
                        if int(w.id) not in own])


def end_landings(ends: _t.Sequence[DeckEnd], plats: list, n_by_unit: dict, held, template_of,
                 taken, grid: float, reach: float, law, to_ll, airport, counts: dict
                 ) -> tuple[_t.Any, list, dict, dict]:
    """R6 / R7: each GRADED end's landing appended to ``plats``
    (``planar/landing``'s PASS 1 tuples) with its run-out — the end edge
    swept one ``abutment_sample_step_m`` outward, widened by ``reach``
    (``[basin] contact_band_m``), less what is ``taken`` and every other
    road (:func:`other_roads`).  An end whose run-out finds its ground held
    ahead (Q2 (a): the road it would cross keeps its ground) mints nothing
    and is listed.  Every end's row is kept on its block's held record
    (``deck_ends``, R10).  ``(taken, [(ref, end)], run-outs, {ref: the
    roads its banks yield to})``."""
    from .landing import _free_pieces
    from .landing_runout import landing_runouts
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    mints: list = []
    runs: dict = {}
    holds: dict = {}
    for e in ends:
        row = end_row(e, to_ll)
        hb = held.get(e.block)
        if hb is not None:
            hb.setdefault("deck_ends", []).append(row)
        tmpl = template_of(e.block)
        if e.state != "graded" or tmpl is None or hb is None:
            continue
        roads = other_roads(airport, law, e)
        hold = unary_union([taken, roads])
        Ls = _free_pieces(end_platform(e, step).buffer(reach, join_style=2), hold, grid)
        if not Ls:
            row.update(state="listed", why="end_taken: the ground beyond the edge is held")
            continue
        unit = str(hb.get("unit", e.block))
        k = n_by_unit.get(unit, 0)
        ref = f"{unit}{LANDING_SEP}{k}"
        Lu = unary_union(Ls)
        plat = (ref, Ls, Lu, e.y_e, f"end:{e.deck}#{len(mints)}", e.block, 1, unit, tmpl)
        got = landing_runouts([plat], held, airport, law, unary_union([hold, Lu]),
                              reach + grid, grid, counts, feet=[end_foot(e, step)], tag="end")
        why = counts.get("end_runout_feet", {})
        if not got and not why.get("at_grade"):
            row.update(state="listed", why="end_run_held: the run-out meets held ground "
                                            "or another road (Q2 (a))")
            continue
        n_by_unit[unit] = k + 1
        taken = unary_union([taken, Lu, *(q for r in got.values() for q in r["polys"])])
        row["landing"] = ref
        plats.append(plat)
        mints.append((ref, e))
        runs.update(got)
        holds[ref] = roads
        holds.update((r, roads) for r in got)
    return taken, mints, runs, holds
